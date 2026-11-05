package io.github.hackermanx.focuslock.core

import java.time.LocalDate
import java.time.YearMonth

/**
 * The phone's one way out of a lock: type [PHRASE] exactly and the lock ends.
 * Once per calendar month; using it resets the streak and is logged in history.
 */
object EmergencySwitch {
    const val PHRASE = "I am choosing to end my focus lock early."

    fun matches(typed: String) = typed == PHRASE

    /**
     * Available unless it was already used this month. A month later than
     * today (the clock was turned back after using it) also counts as used.
     */
    fun isAvailable(lastUsed: YearMonth?, today: LocalDate) =
        lastUsed == null || YearMonth.from(today).isAfter(lastUsed)

    /** The first day it can be used again, or null if it can be used now. */
    fun nextAvailable(lastUsed: YearMonth?, today: LocalDate): LocalDate? =
        if (isAvailable(lastUsed, today)) null else lastUsed!!.plusMonths(1).atDay(1)

    /**
     * Whether a change to the typed text could have come from typing: one
     * character added, or text removed. Anything bigger is a paste (from the
     * keyboard's clipboard or a suggestion) and is refused.
     */
    fun acceptsEdit(old: String, new: String) = new.length <= old.length + 1
}
