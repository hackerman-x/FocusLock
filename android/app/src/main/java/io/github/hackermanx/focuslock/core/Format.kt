package io.github.hackermanx.focuslock.core

import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

object Format {
    private val endFormat = DateTimeFormatter.ofPattern("EEE d MMM, HH:mm", Locale.getDefault())
    private val timeFormat = DateTimeFormatter.ofPattern("HH:mm", Locale.getDefault())
    private val dayFormat = DateTimeFormatter.ofPattern("d MMM", Locale.getDefault())
    private val dateFormat = DateTimeFormatter.ofPattern("EEE d MMM yyyy", Locale.getDefault())

    private fun zoned(epochMs: Long) = Instant.ofEpochMilli(epochMs).atZone(ZoneId.systemDefault())

    /** "Sat 1 Nov, 18:30" */
    fun end(epochMs: Long): String = endFormat.format(zoned(epochMs))

    /** "18:30" */
    fun time(epochMs: Long): String = timeFormat.format(zoned(epochMs))

    /** "1 Dec" */
    fun day(date: LocalDate): String = dayFormat.format(date)

    /** "Sat 1 Nov 2026" */
    fun date(epochMs: Long): String = dateFormat.format(zoned(epochMs))

    fun localDate(epochMs: Long): LocalDate = zoned(epochMs).toLocalDate()

    /** "2d 03:04:05", or "03:04:05" under a day. */
    fun countdown(ms: Long): String {
        val total = (ms + 999) / 1000
        val d = total / 86_400
        val h = total % 86_400 / 3600
        val m = total % 3600 / 60
        val s = total % 60
        val clock = "%02d:%02d:%02d".format(h, m, s)
        return if (d > 0) "${d}d $clock" else clock
    }

    /** "1d 2h", "1h 30m", "25m" */
    fun duration(minutes: Long): String {
        val d = minutes / 1440
        val h = minutes % 1440 / 60
        val m = minutes % 60
        return listOfNotNull(
            if (d > 0) "${d}d" else null,
            if (h > 0) "${h}h" else null,
            if (m > 0 || minutes == 0L) "${m}m" else null,
        ).joinToString(" ")
    }
}
