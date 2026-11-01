package io.github.hackermanx.focuslock.core

/** One reading of the phone's clocks. */
data class Clocks(
    /** Wall-clock time (System.currentTimeMillis), which the user can change. */
    val wall: Long,
    /** Time since boot (SystemClock.elapsedRealtime), which nobody can change. */
    val elapsed: Long,
    /** Settings.Global.BOOT_COUNT, so a reboot (which resets [elapsed]) is noticed. */
    val bootCount: Int,
)

/**
 * When a lock (or a YouTube break) ends.
 *
 * The lock is active while now < [unlockAtWall]. Within one boot the end is
 * counted on the monotonic clock instead: [anchorRemaining] is what was left
 * at [anchorElapsed], and changing the date or time can't move that. After a
 * clock change, [reanchor] re-derives [unlockAtWall] from it, so a reboot
 * later on (when the monotonic clock starts over) still ends on time.
 */
data class LockTiming(
    val unlockAtWall: Long,
    val anchorElapsed: Long,
    val anchorRemaining: Long,
    val bootCount: Int,
) {
    private fun sameBoot(now: Clocks) = now.bootCount == bootCount && now.elapsed >= anchorElapsed

    fun remaining(now: Clocks): Long {
        val left = if (sameBoot(now)) anchorRemaining - (now.elapsed - anchorElapsed) else unlockAtWall - now.wall
        return left.coerceAtLeast(0)
    }

    fun isActive(now: Clocks) = remaining(now) > 0

    /** The end, on the wall clock as it reads right now. */
    fun endsAtWall(now: Clocks) = now.wall + remaining(now)

    /** Re-reads the remaining time (monotonic within a boot) and moves the wall-clock end to match. */
    fun reanchor(now: Clocks): LockTiming {
        val left = remaining(now)
        return LockTiming(now.wall + left, now.elapsed, left, now.bootCount)
    }

    /** Right after a reboot the monotonic clock has restarted, so only the wall-clock end is left to go on. */
    fun afterReboot(now: Clocks): LockTiming {
        val left = (unlockAtWall - now.wall).coerceAtLeast(0)
        return LockTiming(unlockAtWall, now.elapsed, left, now.bootCount)
    }

    companion object {
        fun start(durationMs: Long, now: Clocks) =
            LockTiming(now.wall + durationMs, now.elapsed, durationMs, now.bootCount)
    }
}
