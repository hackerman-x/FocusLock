package io.github.hackermanx.focuslock.block

import android.accessibilityservice.AccessibilityService
import android.content.pm.PackageManager
import android.os.SystemClock
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import io.github.hackermanx.focuslock.BlockedActivity
import io.github.hackermanx.focuslock.R
import io.github.hackermanx.focuslock.app
import io.github.hackermanx.focuslock.core.Blocklist
import io.github.hackermanx.focuslock.core.Clocks
import io.github.hackermanx.focuslock.core.ScreenRules
import io.github.hackermanx.focuslock.data.AppState
import io.github.hackermanx.focuslock.data.Attempt
import io.github.hackermanx.focuslock.lock.LockManager
import io.github.hackermanx.focuslock.lock.clocksNow
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * App blocking and strict mode. Watches which window comes to the front:
 * blocked apps, blocked sites in a browser's address bar and protected
 * Settings screens are sent away and the "blocked until" screen shown.
 */
class GuardService : AccessibilityService() {
    companion object {
        @Volatile
        var running = false
            private set

        private const val VPN_DIALOG_PACKAGE = "com.android.vpndialogs"
        private const val MAX_NODES = 400
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val lastLogged = HashMap<String, Long>()
    private val lastScan = HashMap<String, Long>()
    private var lastShown = 0L
    private var lastShownTarget = ""
    private var vpnMissingSince = 0L
    private var lastVpnPrompt = 0L

    override fun onServiceConnected() {
        running = true
        scope.launch {
            while (isActive) {
                LockManager.tick(this@GuardService)
                delay(30_000)
            }
        }
    }

    override fun onInterrupt() {}

    override fun onDestroy() {
        running = false
        scope.cancel()
        super.onDestroy()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent) {
        val st = app.repo.state.value
        val now = clocksNow(this)
        val lock = LockManager.activeLock(st, now) ?: return
        val pkg = event.packageName?.toString() ?: return
        if (pkg == packageName) return
        val ytOpen = LockManager.ytBreakActive(st, now)

        if (pkg in lock.apps && !(ytOpen && pkg in Blocklist.YOUTUBE_PACKAGES)) {
            block(Attempt.KIND_APP, pkg, appLabel(pkg), back = false)
            return
        }
        // Content changes come in floods; look at each app at most twice a second.
        if (event.eventType != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            val t = SystemClock.elapsedRealtime()
            if (t - (lastScan[pkg] ?: 0) < 500) return
            lastScan[pkg] = t
        }
        Blocklist.BROWSER_URL_BARS[pkg]?.let { ids ->
            if (checkBrowser(ids, LockManager.blockedDomains(st, now))) return
        }
        if (ScreenRules.watches(pkg) && checkSettings(pkg)) return
        if (pkg != VPN_DIALOG_PACKAGE) checkVpn(st, now)
    }

    /** Reads the address bar; true if it showed a blocked site. */
    private fun checkBrowser(ids: List<String>, domains: Set<String>): Boolean {
        if (domains.isEmpty()) return false
        val root = rootInActiveWindow ?: return false
        for (id in ids) {
            val bar = root.findAccessibilityNodeInfosByViewId(id).firstOrNull() ?: continue
            if (bar.isFocused) return false // still typing
            val host = Blocklist.hostFromUrl(bar.text?.toString() ?: return false) ?: return false
            if (!Blocklist.isBlocked(host, domains)) return false
            block(Attempt.KIND_SITE, host, host, back = true)
            return true
        }
        return false
    }

    /** Closes protected Settings screens; true if it closed one. */
    private fun checkSettings(pkg: String): Boolean {
        val root = rootInActiveWindow ?: return false
        val texts = ArrayList<String>()
        collectText(root, texts, 0)
        val screen = ScreenRules.protectedScreen(pkg, texts, getString(R.string.app_name)) ?: return false
        block(Attempt.KIND_SETTINGS, "settings:$screen", screen, back = false)
        return true
    }

    private fun collectText(node: AccessibilityNodeInfo, out: MutableList<String>, depth: Int) {
        if (out.size >= MAX_NODES || depth > 40) return
        node.text?.let { out += it.toString() }
        node.contentDescription?.let { out += it.toString() }
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            collectText(child, out, depth + 1)
        }
    }

    /** Website blocking needs the VPN; if it's down, start it again or ask for it. */
    private fun checkVpn(st: AppState, now: Clocks) {
        if (LockManager.blockedDomains(st, now).isEmpty() || DnsVpnService.running) {
            vpnMissingSince = 0
            return
        }
        val t = SystemClock.elapsedRealtime()
        if (vpnMissingSince == 0L) {
            vpnMissingSince = t
            DnsVpnService.start(this)
        } else if (t - vpnMissingSince > 4000 && t - lastVpnPrompt > 15_000) {
            lastVpnPrompt = t
            DnsVpnService.start(this)
            startActivity(BlockedActivity.intent(this, Attempt.KIND_VPN, ""))
        }
    }

    private fun block(kind: String, target: String, label: String, back: Boolean) {
        performGlobalAction(if (back) GLOBAL_ACTION_BACK else GLOBAL_ACTION_HOME)
        val t = SystemClock.elapsedRealtime()
        if (t - (lastLogged[target] ?: 0) > 5000) {
            lastLogged[target] = t
            app.scope.launch {
                app.db.dao().insertAttempt(Attempt(time = System.currentTimeMillis(), kind = kind, target = target, label = label))
            }
        }
        if (target != lastShownTarget || t - lastShown > 1000) {
            lastShownTarget = target
            lastShown = t
            startActivity(BlockedActivity.intent(this, kind, label))
        }
    }

    private fun appLabel(pkg: String): String = try {
        packageManager.getApplicationLabel(packageManager.getApplicationInfo(pkg, 0)).toString()
    } catch (_: PackageManager.NameNotFoundException) {
        pkg
    }
}
