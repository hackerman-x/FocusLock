package io.github.hackermanx.focuslock.block

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.VpnService
import android.os.Build
import android.os.ParcelFileDescriptor
import android.system.ErrnoException
import android.system.Os
import android.system.OsConstants
import android.system.StructPollfd
import io.github.hackermanx.focuslock.BlockedActivity
import io.github.hackermanx.focuslock.MainActivity
import io.github.hackermanx.focuslock.app
import io.github.hackermanx.focuslock.core.Blocklist
import io.github.hackermanx.focuslock.core.DnsPacket
import io.github.hackermanx.focuslock.data.AppState
import io.github.hackermanx.focuslock.data.Attempt
import io.github.hackermanx.focuslock.lock.LockManager
import io.github.hackermanx.focuslock.lock.clocksNow
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.IOException
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.RejectedExecutionException

/**
 * Website blocking. A DNS-only VPN: the tunnel claims a made-up DNS server
 * address and routes nothing else, so only DNS lookups enter it. Blocked names
 * get 0.0.0.0; everything else goes to the real DNS server through a socket
 * that bypasses the tunnel.
 */
class DnsVpnService : VpnService() {
    companion object {
        private const val TUN_ADDRESS = "10.111.222.1"
        const val DNS_ADDRESS = "10.111.222.2"

        @Volatile
        var running = false
            private set

        /** Starts the VPN if the user has allowed it; otherwise BlockedActivity asks again. */
        fun start(ctx: Context) {
            if (prepare(ctx) != null) return
            try {
                ctx.startService(Intent(ctx, DnsVpnService::class.java))
            } catch (_: IllegalStateException) {
                // Not allowed from the background right now; the accessibility service retries.
            } catch (_: SecurityException) {
            }
        }
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var watcher: Job? = null
    private var tunnel: Tunnel? = null
    private var domains: Set<String> = emptySet()

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (watcher == null) {
            watcher = scope.launch {
                launch {
                    while (isActive) {
                        delay(30_000)
                        LockManager.tick(this@DnsVpnService)
                    }
                }
                app.repo.state.collect { apply(it) }
            }
        }
        return START_STICKY
    }

    private fun apply(st: AppState) {
        val wanted = LockManager.blockedDomains(st, clocksNow(this))
        if (wanted.isEmpty()) {
            shutdown()
            return
        }
        if (wanted == domains && tunnel != null) return
        // A new interface each time the list changes: the system drops its
        // DNS cache with the old network, so a change applies straight away.
        val fd = try {
            Builder()
                .setSession("FocusLock")
                .addAddress(TUN_ADDRESS, 32)
                .addDnsServer(DNS_ADDRESS)
                .addRoute(DNS_ADDRESS, 32)
                .allowFamily(OsConstants.AF_INET6)
                .setConfigureIntent(
                    PendingIntent.getActivity(
                        this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE,
                    ),
                )
                .apply { if (Build.VERSION.SDK_INT >= 29) setMetered(false) }
                .establish()
        } catch (_: Exception) {
            null
        }
        if (fd == null) { // permission withdrawn
            shutdown()
            return
        }
        tunnel?.close()
        domains = wanted
        tunnel = Tunnel(fd, wanted, this).also { it.start() }
        running = true
    }

    private fun shutdown() {
        tunnel?.close()
        tunnel = null
        domains = emptySet()
        running = false
        stopSelf()
    }

    /** The VPN was switched off or another VPN took over. During a lock, ask for it back at once. */
    override fun onRevoke() {
        tunnel?.close()
        tunnel = null
        domains = emptySet()
        running = false
        val st = app.repo.state.value
        if (LockManager.blockedDomains(st, clocksNow(this)).isNotEmpty()) {
            app.scope.launch {
                app.db.dao().insertAttempt(
                    Attempt(time = System.currentTimeMillis(), kind = Attempt.KIND_VPN, target = "vpn", label = "VPN switched off"),
                )
            }
            startActivity(BlockedActivity.intent(this, Attempt.KIND_VPN, ""))
        }
        super.onRevoke()
    }

    override fun onDestroy() {
        tunnel?.close()
        tunnel = null
        running = false
        scope.cancel()
        super.onDestroy()
    }
}

/** Reads DNS queries from one tunnel interface and answers them. */
private class Tunnel(
    private val fd: ParcelFileDescriptor,
    private val blocked: Set<String>,
    private val service: VpnService,
) {
    @Volatile
    private var alive = true
    private val output = FileOutputStream(fd.fileDescriptor)
    private val upstream: ExecutorService = Executors.newFixedThreadPool(4)
    private val thread = Thread(::readLoop, "focuslock-dns")

    fun start() = thread.start()

    fun close() {
        alive = false
        upstream.shutdownNow()
        try {
            fd.close()
        } catch (_: IOException) {
        }
    }

    private fun readLoop() {
        val input = FileInputStream(fd.fileDescriptor)
        val buf = ByteArray(32767)
        val poll = StructPollfd().apply {
            this.fd = this@Tunnel.fd.fileDescriptor
            events = OsConstants.POLLIN.toShort()
        }
        while (alive) {
            try {
                if (Os.poll(arrayOf(poll), 1000) <= 0) continue
                val n = input.read(buf)
                if (n > 0) handle(buf.copyOf(n))
            } catch (e: ErrnoException) {
                if (e.errno != OsConstants.EINTR && e.errno != OsConstants.EAGAIN) break
            } catch (_: IOException) {
                if (!alive) break
            }
        }
    }

    private fun handle(packet: ByteArray) {
        val udp = DnsPacket.parseUdp(packet) ?: return
        if (udp.dstPort != 53) return
        val query = DnsPacket.parseQuery(udp.payload) ?: return
        if (Blocklist.isBlocked(query.name, blocked)) {
            write(DnsPacket.buildUdpResponse(udp, DnsPacket.blockedAnswer(udp.payload, query)))
            return
        }
        try {
            upstream.execute { forward(udp) }
        } catch (_: RejectedExecutionException) {
        }
    }

    private fun forward(udp: DnsPacket.Udp) {
        for ((network, server) in Upstream.servers(service)) {
            if (!alive) return
            try {
                DatagramSocket().use { socket ->
                    service.protect(socket)
                    network?.bindSocket(socket)
                    socket.soTimeout = 4000
                    socket.send(DatagramPacket(udp.payload, udp.payload.size, InetSocketAddress(server, 53)))
                    val resp = ByteArray(4096)
                    val p = DatagramPacket(resp, resp.size)
                    socket.receive(p)
                    write(DnsPacket.buildUdpResponse(udp, resp.copyOf(p.length)))
                }
                return
            } catch (_: IOException) {
                // try the next server
            }
        }
    }

    private fun write(packet: ByteArray) {
        if (!alive) return
        synchronized(output) {
            try {
                output.write(packet)
            } catch (_: IOException) {
            }
        }
    }
}

/** The real DNS servers, from the networks underneath the VPN. */
private object Upstream {
    private val FALLBACK = listOf("1.1.1.1", "8.8.8.8").map { InetAddress.getByName(it) }
    private var cached: List<Pair<Network?, InetAddress>> = emptyList()
    private var cachedAt = 0L

    @Synchronized
    fun servers(ctx: Context): List<Pair<Network?, InetAddress>> {
        val now = System.currentTimeMillis()
        if (cached.isNotEmpty() && now - cachedAt < 10_000) return cached
        val cm = ctx.getSystemService(ConnectivityManager::class.java)
        val found = ArrayList<Pair<Network?, InetAddress>>()
        @Suppress("DEPRECATION")
        val networks = cm.allNetworks.mapNotNull { n -> cm.getNetworkCapabilities(n)?.let { n to it } }
            .filter { (_, caps) ->
                !caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN) &&
                    caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            }
            .sortedByDescending { (_, caps) -> caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED) }
        for ((network, _) in networks) {
            cm.getLinkProperties(network)?.dnsServers?.forEach { found += network to it }
        }
        found.removeAll { it.second.hostAddress == DnsVpnService.DNS_ADDRESS }
        FALLBACK.forEach { found += null to it }
        cached = found
        cachedAt = now
        return found
    }
}
