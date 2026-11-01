package io.github.hackermanx.focuslock.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LockTimingTest {
    private val hour = 3_600_000L
    private val start = Clocks(wall = 1_700_000_000_000, elapsed = 50_000, bootCount = 7)

    private fun Clocks.later(ms: Long, wallShift: Long = 0) = copy(wall = wall + ms + wallShift, elapsed = elapsed + ms)

    @Test
    fun activeUntilTheEnd() {
        val t = LockTiming.start(2 * hour, start)
        assertEquals(start.wall + 2 * hour, t.unlockAtWall)
        assertTrue(t.isActive(start))
        assertEquals(hour, t.remaining(start.later(hour)))
        assertTrue(t.isActive(start.later(2 * hour - 1)))
        assertFalse(t.isActive(start.later(2 * hour)))
        assertEquals(0, t.remaining(start.later(5 * hour)))
    }

    @Test
    fun movingTheClockForwardDoesNotEndTheLock() {
        val t = LockTiming.start(2 * hour, start)
        val now = start.later(10 * 60_000, wallShift = 30 * 24 * hour)
        assertTrue(t.isActive(now))
        assertEquals(2 * hour - 10 * 60_000, t.remaining(now))
    }

    @Test
    fun movingTheClockBackDoesNotStretchTheLock() {
        val t = LockTiming.start(2 * hour, start)
        assertFalse(t.isActive(start.later(2 * hour, wallShift = -5 * hour)))
    }

    @Test
    fun reanchorMovesTheWallClockEndAfterAClockChange() {
        val t = LockTiming.start(2 * hour, start)
        val shifted = start.later(hour, wallShift = 3 * hour)
        val fixed = t.reanchor(shifted)
        assertEquals(hour, fixed.remaining(shifted))
        assertEquals(shifted.wall + hour, fixed.unlockAtWall)
        // A reboot after that ends at the right moment on the new wall clock.
        val rebooted = Clocks(wall = shifted.wall + 30 * 60_000, elapsed = 20_000, bootCount = 8)
        assertEquals(30 * 60_000L, fixed.afterReboot(rebooted).remaining(rebooted))
    }

    @Test
    fun afterARebootTheWallClockEndCounts() {
        val t = LockTiming.start(2 * hour, start)
        // Rebooted 90 minutes in; the monotonic clock started over.
        val rebooted = Clocks(wall = start.wall + 90 * 60_000, elapsed = 15_000, bootCount = 8)
        assertEquals(30 * 60_000L, t.remaining(rebooted))
        val anchored = t.afterReboot(rebooted)
        assertEquals(rebooted.elapsed, anchored.anchorElapsed)
        assertEquals(8, anchored.bootCount)
        // From then on the monotonic clock rules again.
        assertEquals(20 * 60_000L, anchored.remaining(rebooted.later(10 * 60_000, wallShift = 5 * hour)))
    }

    @Test
    fun aRebootWithMoreUptimeThanBeforeIsStillNoticed() {
        val t = LockTiming.start(2 * hour, start)
        // Same elapsed time going up, but a different boot count: use the wall clock.
        val other = Clocks(wall = start.wall + hour, elapsed = start.elapsed + 10 * hour, bootCount = 8)
        assertEquals(hour, t.remaining(other))
    }

    @Test
    fun endsAtWallFollowsTheCurrentClock() {
        val t = LockTiming.start(hour, start)
        val now = start.later(0, wallShift = -2 * hour)
        assertEquals(now.wall + hour, t.endsAtWall(now))
    }
}
