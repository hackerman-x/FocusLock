package io.github.hackermanx.focuslock.core

import java.io.ByteArrayOutputStream

/**
 * Just enough IPv4, UDP and DNS to answer the queries the VPN tunnel receives:
 * blocked names get 0.0.0.0 (or ::), everything else is forwarded as is.
 */
object DnsPacket {
    const val TYPE_A = 1
    const val TYPE_AAAA = 28
    const val CLASS_IN = 1
    const val BLOCKED_TTL = 60

    /** A UDP datagram read from the tunnel. Addresses are 4-byte IPv4. */
    class Udp(
        val srcAddr: ByteArray,
        val dstAddr: ByteArray,
        val srcPort: Int,
        val dstPort: Int,
        val payload: ByteArray,
    )

    class Query(val id: Int, val name: String, val type: Int, val questionEnd: Int)

    /** The UDP datagram in an IPv4 packet, or null for anything else (IPv6, TCP, fragments, junk). */
    fun parseUdp(packet: ByteArray, length: Int = packet.size): Udp? {
        if (length < 28) return null
        if ((packet[0].toInt() ushr 4) and 0xF != 4) return null
        val ihl = (packet[0].toInt() and 0xF) * 4
        if (ihl < 20 || length < ihl + 8) return null
        if (packet[9].toInt() and 0xFF != 17) return null
        val total = u16(packet, 2)
        if (total > length || total < ihl + 8) return null
        if (u16(packet, 6) and 0x3FFF != 0) return null // a fragment
        val udpLen = u16(packet, ihl + 4)
        if (udpLen < 8 || ihl + udpLen > total) return null
        return Udp(
            srcAddr = packet.copyOfRange(12, 16),
            dstAddr = packet.copyOfRange(16, 20),
            srcPort = u16(packet, ihl),
            dstPort = u16(packet, ihl + 2),
            payload = packet.copyOfRange(ihl + 8, ihl + udpLen),
        )
    }

    /** The first question of a DNS query, with the name lowercased and no trailing dot. */
    fun parseQuery(msg: ByteArray): Query? {
        if (msg.size < 12) return null
        if (u16(msg, 2) and 0x8000 != 0) return null // a response, not a query
        if (u16(msg, 4) < 1) return null
        var pos = 12
        val labels = ArrayList<String>()
        var nameLen = 0
        while (true) {
            if (pos >= msg.size) return null
            val len = msg[pos].toInt() and 0xFF
            if (len == 0) {
                pos++
                break
            }
            if (len and 0xC0 != 0) return null // compression never appears in a question
            if (pos + 1 + len > msg.size) return null
            nameLen += len + 1
            if (nameLen > 255) return null
            labels += String(msg, pos + 1, len, Charsets.ISO_8859_1).lowercase()
            pos += 1 + len
        }
        if (pos + 4 > msg.size) return null
        return Query(u16(msg, 0), labels.joinToString("."), u16(msg, pos), pos + 4)
    }

    /**
     * The answer for a blocked name: 0.0.0.0 for A, :: for AAAA, and an empty
     * answer for every other type (so browsers asking for HTTPS records fall back to A).
     */
    fun blockedAnswer(query: ByteArray, q: Query): ByteArray {
        val rdata = when (q.type) {
            TYPE_A -> ByteArray(4)
            TYPE_AAAA -> ByteArray(16)
            else -> null
        }
        val out = ByteArrayOutputStream()
        out.write(query, 0, q.questionEnd)
        if (rdata != null) {
            out.write(byteArrayOf(0xC0.toByte(), 0x0C)) // name: pointer to the question
            out.write16(q.type)
            out.write16(CLASS_IN)
            out.write16(BLOCKED_TTL ushr 16)
            out.write16(BLOCKED_TTL and 0xFFFF)
            out.write16(rdata.size)
            out.write(rdata)
        }
        val msg = out.toByteArray()
        val reqFlags = u16(query, 2)
        // QR, the request's opcode and RD, RA; RCODE 0.
        put16(msg, 2, 0x8000 or (reqFlags and 0x7800) or (reqFlags and 0x0100) or 0x0080)
        put16(msg, 4, 1)
        put16(msg, 6, if (rdata != null) 1 else 0)
        put16(msg, 8, 0)
        put16(msg, 10, 0)
        return msg
    }

    /** An IPv4/UDP packet carrying [payload] back to whoever sent [request]. */
    fun buildUdpResponse(request: Udp, payload: ByteArray): ByteArray {
        val udpLen = 8 + payload.size
        val total = 20 + udpLen
        val p = ByteArray(total)
        p[0] = 0x45
        put16(p, 2, total)
        put16(p, 6, 0x4000) // don't fragment
        p[8] = 64
        p[9] = 17
        request.dstAddr.copyInto(p, 12)
        request.srcAddr.copyInto(p, 16)
        put16(p, 10, fold(sum16(p, 0, 20)))
        put16(p, 20, request.dstPort)
        put16(p, 22, request.srcPort)
        put16(p, 24, udpLen)
        payload.copyInto(p, 28)
        val pseudo = sum16(p, 12, 8) + 17 + udpLen
        val udpSum = fold(pseudo + sum16(p, 20, udpLen))
        put16(p, 26, if (udpSum == 0) 0xFFFF else udpSum)
        return p
    }

    /** One's-complement sum of 16-bit words (an odd last byte is padded with zero). */
    internal fun sum16(b: ByteArray, off: Int, len: Int): Long {
        var sum = 0L
        var i = off
        while (i + 1 < off + len) {
            sum += u16(b, i)
            i += 2
        }
        if (i < off + len) sum += (b[i].toInt() and 0xFF) shl 8
        return sum
    }

    private fun fold(sum: Long): Int {
        var s = sum
        while (s ushr 16 != 0L) s = (s and 0xFFFF) + (s ushr 16)
        return s.toInt().inv() and 0xFFFF
    }

    internal fun u16(b: ByteArray, off: Int) = ((b[off].toInt() and 0xFF) shl 8) or (b[off + 1].toInt() and 0xFF)

    private fun put16(b: ByteArray, off: Int, v: Int) {
        b[off] = (v ushr 8).toByte()
        b[off + 1] = v.toByte()
    }

    private fun ByteArrayOutputStream.write16(v: Int) {
        write(v ushr 8 and 0xFF)
        write(v and 0xFF)
    }
}
