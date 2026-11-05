package io.github.hackermanx.focuslock.core

import java.time.LocalDate
import java.time.temporal.ChronoUnit

data class Stats(
    val streak: Int = 0,
    val longestStreak: Int = 0,
    val totalSessions: Int = 0,
    val lastUnlockDate: LocalDate? = null,
    val lastStartDate: LocalDate? = null,
)

/** The same streak rules as the desktop app's bump_streak (focuslock_core.py). */
object Streak {
    /**
     * Call once, when a lock starts. The streak counts calendar days on which
     * a lock was started, with at most a one-day gap since the previous lock
     * ended, and goes up at most once a day (several short locks in one day
     * still each count as a session).
     */
    fun onLockStarted(stats: Stats, endDate: LocalDate, today: LocalDate): Stats {
        if (stats.lastStartDate == today) {
            return stats.copy(totalSessions = stats.totalSessions + 1, lastUnlockDate = endDate)
        }
        val last = stats.lastUnlockDate
        val streak = if (last != null && ChronoUnit.DAYS.between(last, today) <= 1) stats.streak + 1 else 1
        return stats.copy(
            streak = streak,
            longestStreak = maxOf(stats.longestStreak, streak),
            totalSessions = stats.totalSessions + 1,
            lastUnlockDate = endDate,
            lastStartDate = today,
        )
    }

    /** The emergency switch breaks the streak; the next lock starts it again at 1. */
    fun onEmergency(stats: Stats, today: LocalDate) =
        stats.copy(streak = 0, lastUnlockDate = today, lastStartDate = null)

    /** The streak as it stands today: gone if more than a day has passed since the last lock ended. */
    fun current(stats: Stats, today: LocalDate): Int {
        val last = stats.lastUnlockDate ?: return 0
        return if (ChronoUnit.DAYS.between(last, today) <= 1) stats.streak else 0
    }
}
