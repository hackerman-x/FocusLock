package io.github.hackermanx.focuslock.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate
import java.time.YearMonth

class EmergencySwitchTest {
    private val nov = YearMonth.of(2026, 11)

    @Test
    fun availableWhenNeverUsed() {
        assertTrue(EmergencySwitch.isAvailable(null, LocalDate.of(2026, 11, 1)))
        assertNull(EmergencySwitch.nextAvailable(null, LocalDate.of(2026, 11, 1)))
    }

    @Test
    fun onceUsedItIsRefusedForTheRestOfTheMonth() {
        assertFalse(EmergencySwitch.isAvailable(nov, LocalDate.of(2026, 11, 1)))
        assertFalse(EmergencySwitch.isAvailable(nov, LocalDate.of(2026, 11, 30)))
        assertEquals(LocalDate.of(2026, 12, 1), EmergencySwitch.nextAvailable(nov, LocalDate.of(2026, 11, 15)))
    }

    @Test
    fun comesBackOnTheFirstOfNextMonth() {
        assertTrue(EmergencySwitch.isAvailable(nov, LocalDate.of(2026, 12, 1)))
        assertTrue(EmergencySwitch.isAvailable(nov, LocalDate.of(2027, 3, 10)))
    }

    @Test
    fun decemberRollsOverToJanuary() {
        val dec = YearMonth.of(2026, 12)
        assertFalse(EmergencySwitch.isAvailable(dec, LocalDate.of(2026, 12, 31)))
        assertEquals(LocalDate.of(2027, 1, 1), EmergencySwitch.nextAvailable(dec, LocalDate.of(2026, 12, 31)))
        assertTrue(EmergencySwitch.isAvailable(dec, LocalDate.of(2027, 1, 1)))
    }

    @Test
    fun turningTheClockBackDoesNotGiveItBack() {
        assertFalse(EmergencySwitch.isAvailable(nov, LocalDate.of(2026, 10, 20)))
        assertEquals(LocalDate.of(2026, 12, 1), EmergencySwitch.nextAvailable(nov, LocalDate.of(2026, 10, 20)))
    }

    @Test
    fun phraseMustMatchExactly() {
        assertTrue(EmergencySwitch.matches("I am choosing to end my focus lock early."))
        assertFalse(EmergencySwitch.matches("I am choosing to end my focus lock early"))
        assertFalse(EmergencySwitch.matches("i am choosing to end my focus lock early."))
        assertFalse(EmergencySwitch.matches(" I am choosing to end my focus lock early."))
    }

    @Test
    fun pastingIsRefused() {
        assertTrue(EmergencySwitch.acceptsEdit("I am", "I am "))
        assertTrue(EmergencySwitch.acceptsEdit("I am", "I a"))
        assertTrue(EmergencySwitch.acceptsEdit("I am", ""))
        assertFalse(EmergencySwitch.acceptsEdit("", EmergencySwitch.PHRASE))
        assertFalse(EmergencySwitch.acceptsEdit("I am", "I am choosing"))
    }

    @Test
    fun emergencyResetsTheStreak() {
        val today = LocalDate.of(2026, 11, 10)
        val before = Stats(streak = 6, longestStreak = 9, totalSessions = 20, lastUnlockDate = today, lastStartDate = today)
        val after = Streak.onEmergency(before, today)
        assertEquals(0, after.streak)
        assertEquals(9, after.longestStreak)
        assertEquals(0, Streak.current(after, today))
        // The next lock, even the same day, starts the streak again at 1.
        assertEquals(1, Streak.onLockStarted(after, today, today).streak)
    }

    @Test
    fun streakFollowsTheDesktopRules() {
        val d1 = LocalDate.of(2026, 11, 1)
        var s = Streak.onLockStarted(Stats(), d1, d1)
        assertEquals(1, s.streak)
        s = Streak.onLockStarted(s, d1, d1) // same day: a session, not a streak day
        assertEquals(1, s.streak)
        assertEquals(2, s.totalSessions)
        s = Streak.onLockStarted(s, d1.plusDays(1), d1.plusDays(1))
        assertEquals(2, s.streak)
        s = Streak.onLockStarted(s, d1.plusDays(5), d1.plusDays(5)) // a gap
        assertEquals(1, s.streak)
        assertEquals(2, s.longestStreak)
    }
}
