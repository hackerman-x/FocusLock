package io.github.hackermanx.focuslock.core

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayOutputStream

class DnsPacketTest {
    /** A standard query: id, RD set, one question, plus an EDNS OPT record like real resolvers send. */
    private fun query(name: String, type: Int, id: Int = 0x1234, edns: Boolean = true): ByteArray {
        val out = ByteArrayOutputStream()
        fun w16(v: Int) {
            out.write(v ushr 8 and 0xFF)
            out.write(v and 0xFF)
        }
        w16(id)
        w16(0x0100) // RD
        w16(1)
        w16(0)
        w16(0)
        w16(if (edns) 1 else 0)
        name.split('.').forEach {
            out.write(it.length)
            out.write(it.toByteArray())
        }
        out.write(0)
        w16(type)
        w16(1)
        if (edns) {
            out.write(0) // root name
            w16(41)
            w16(1232)
            w16(0)
            w16(0)
            w16(0)
        }
        return out.toByteArray()
    }

    private fun u16(b: ByteArray, off: Int) = DnsPacket.u16(b, off)

    /** Wraps a DNS payload in IPv4/UDP from 10.111.222.1:40000 to the fake DNS address. */
    private fun ipPacket(payload: ByteArray): ByteArray {
        val req = DnsPacket.Udp(
            srcAddr = byteArrayOf(10, 111, 222.toByte(), 2),
            dstAddr = byteArrayOf(10, 111, 222.toByte(), 1),
            srcPort = 53,
            dstPort = 40000,
            payload = ByteArray(0),
        )
        // buildUdpResponse swaps the addresses, so this yields 10.111.222.1:40000 -> 10.111.222.2:53.
        return DnsPacket.buildUdpResponse(req, payload)
    }

    @Test
    fun parsesQuestionNameAndType() {
        val q = DnsPacket.parseQuery(query("WWW.Instagram.com", DnsPacket.TYPE_A))
        assertNotNull(q)
        assertEquals(0x1234, q!!.id)
        assertEquals("www.instagram.com", q.name)
        assertEquals(DnsPacket.TYPE_A, q.type)
        assertEquals(12 + 19 + 4, q.questionEnd)
    }

    @Test
    fun rejectsResponsesAndTruncatedPackets() {
        val response = query("poki.com", 1).also { it[2] = (it[2].toInt() or 0x80).toByte() }
        assertNull(DnsPacket.parseQuery(response))
        assertNull(DnsPacket.parseQuery(ByteArray(5)))
        val full = query("poki.com", 1, edns = false)
        assertNull(DnsPacket.parseQuery(full.copyOf(full.size - 3)))
        // A label length running past the end.
        val bad = full.copyOf().also { it[12] = 60 }
        assertNull(DnsPacket.parseQuery(bad))
    }

    @Test
    fun rejectsCompressedQuestionNames() {
        val q = query("poki.com", 1, edns = false).also { it[12] = 0xC0.toByte() }
        assertNull(DnsPacket.parseQuery(q))
    }

    @Test
    fun blockedAQueryGetsZeroAddress() {
        val req = query("youtube.com", DnsPacket.TYPE_A)
        val q = DnsPacket.parseQuery(req)!!
        val resp = DnsPacket.blockedAnswer(req, q)
        assertEquals(0x1234, u16(resp, 0))
        val flags = u16(resp, 2)
        assertTrue("QR set", flags and 0x8000 != 0)
        assertTrue("RD copied", flags and 0x0100 != 0)
        assertTrue("RA set", flags and 0x0080 != 0)
        assertEquals("NOERROR", 0, flags and 0xF)
        assertEquals(1, u16(resp, 4))
        assertEquals(1, u16(resp, 6))
        assertEquals(0, u16(resp, 8))
        assertEquals("EDNS record dropped", 0, u16(resp, 10))
        // The question is copied unchanged.
        assertArrayEquals(req.copyOfRange(12, q.questionEnd), resp.copyOfRange(12, q.questionEnd))
        val a = q.questionEnd
        assertEquals(0xC00C, u16(resp, a))
        assertEquals(DnsPacket.TYPE_A, u16(resp, a + 2))
        assertEquals(DnsPacket.CLASS_IN, u16(resp, a + 4))
        assertEquals(DnsPacket.BLOCKED_TTL, (u16(resp, a + 6) shl 16) or u16(resp, a + 8))
        assertEquals(4, u16(resp, a + 10))
        assertArrayEquals(ByteArray(4), resp.copyOfRange(a + 12, a + 16))
        assertEquals(a + 16, resp.size)
    }

    @Test
    fun blockedAaaaQueryGetsUnspecifiedAddress() {
        val req = query("m.youtube.com", DnsPacket.TYPE_AAAA)
        val q = DnsPacket.parseQuery(req)!!
        val resp = DnsPacket.blockedAnswer(req, q)
        assertEquals(1, u16(resp, 6))
        assertEquals(16, u16(resp, q.questionEnd + 10))
        assertArrayEquals(ByteArray(16), resp.copyOfRange(q.questionEnd + 12, resp.size))
    }

    @Test
    fun otherTypesGetAnEmptyAnswer() {
        val req = query("www.youtube.com", 65) // HTTPS record
        val q = DnsPacket.parseQuery(req)!!
        val resp = DnsPacket.blockedAnswer(req, q)
        assertEquals(0, u16(resp, 6))
        assertEquals(q.questionEnd, resp.size)
        assertEquals(0, u16(resp, 2) and 0xF)
    }

    @Test
    fun udpRoundTripSwapsEndsAndHasValidChecksums() {
        val payload = query("discord.com", DnsPacket.TYPE_A)
        val packet = ipPacket(payload)
        val udp = DnsPacket.parseUdp(packet)
        assertNotNull(udp)
        assertArrayEquals(byteArrayOf(10, 111, 222.toByte(), 1), udp!!.srcAddr)
        assertArrayEquals(byteArrayOf(10, 111, 222.toByte(), 2), udp.dstAddr)
        assertEquals(40000, udp.srcPort)
        assertEquals(53, udp.dstPort)
        assertArrayEquals(payload, udp.payload)

        val answer = DnsPacket.buildUdpResponse(udp, byteArrayOf(1, 2, 3))
        val back = DnsPacket.parseUdp(answer)!!
        assertArrayEquals(udp.dstAddr, back.srcAddr)
        assertArrayEquals(udp.srcAddr, back.dstAddr)
        assertEquals(53, back.srcPort)
        assertEquals(40000, back.dstPort)
        assertArrayEquals(byteArrayOf(1, 2, 3), back.payload)

        // Summing a header with its checksum in place gives 0xFFFF.
        assertEquals(0xFFFF, fold(DnsPacket.sum16(answer, 0, 20)))
        val udpLen = answer.size - 20
        val pseudo = DnsPacket.sum16(answer, 12, 8) + 17 + udpLen
        assertEquals(0xFFFF, fold(pseudo + DnsPacket.sum16(answer, 20, udpLen)))
    }

    @Test
    fun ignoresNonUdpAndFragments() {
        val packet = ipPacket(query("poki.com", 1))
        assertNull(DnsPacket.parseUdp(packet.copyOf().also { it[9] = 6 })) // TCP
        assertNull(DnsPacket.parseUdp(packet.copyOf().also { it[0] = 0x60 })) // IPv6
        assertNull(DnsPacket.parseUdp(packet.copyOf().also { it[6] = 0x20 })) // more fragments
        assertNull(DnsPacket.parseUdp(packet, 20))
    }

    @Test
    fun matchesBlockedDomainsAndSubdomainsOnly() {
        val blocked = Blocklist.domainsFor(setOf("instagram", "youtube"), setOf("reddit.com"))
        assertTrue(Blocklist.isBlocked("instagram.com", blocked))
        assertTrue(Blocklist.isBlocked("i.instagram.com", blocked))
        assertTrue(Blocklist.isBlocked("WWW.YouTube.com.", blocked))
        assertTrue(Blocklist.isBlocked("old.reddit.com", blocked))
        assertFalse(Blocklist.isBlocked("notinstagram.com", blocked))
        assertFalse(Blocklist.isBlocked("instagram.com.example.net", blocked))
        assertFalse(Blocklist.isBlocked("discord.com", blocked))
        assertFalse(Blocklist.isBlocked("com", blocked))
    }

    @Test
    fun readsHostsFromAddressBars() {
        assertEquals("instagram.com", Blocklist.hostFromUrl("instagram.com/explore"))
        assertEquals("www.youtube.com", Blocklist.hostFromUrl("https://www.youtube.com/watch?v=x"))
        assertEquals("poki.com", Blocklist.hostFromUrl("http://user@poki.com:8080/games"))
        assertNull(Blocklist.hostFromUrl("how to focus"))
        assertNull(Blocklist.hostFromUrl("localhost"))
        assertEquals("reddit.com", Blocklist.normalizeSite("  https://www.Reddit.com/r/android "))
        assertNull(Blocklist.normalizeSite("not a site"))
    }

    private fun fold(sum: Long): Int {
        var s = sum
        while (s ushr 16 != 0L) s = (s and 0xFFFF) + (s ushr 16)
        return s.toInt()
    }
}
