package io.github.hackermanx.focuslock.lock

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.SystemClock
import android.provider.Settings
import io.github.hackermanx.focuslock.R
import io.github.hackermanx.focuslock.app
import io.github.hackermanx.focuslock.block.DnsVpnService
import io.github.hackermanx.focuslock.core.Blocklist
import io.github.hackermanx.focuslock.core.Clocks
import io.github.hackermanx.focuslock.core.EmergencySwitch
import io.github.hackermanx.focuslock.core.Format
import io.github.hackermanx.focuslock.core.LockTiming
import io.github.hackermanx.focuslock.core.Streak
import io.github.hackermanx.focuslock.data.ActiveLock
import io.github.hackermanx.focuslock.data.AppState
import io.github.hackermanx.focuslock.data.HistoryEntry
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.time.LocalDate
import java.time.YearMonth

fun clocksNow(ctx: Context) = Clocks(
    wall = System.currentTimeMillis(),
    elapsed = SystemClock.elapsedRealtime(),
    bootCount = Settings.Global.getInt(ctx.contentResolver, Settings.Global.BOOT_COUNT, -1),
)

/** Starts and ends locks. Every check is "is now before the end?", so the alarm here only tidies up. */
object LockManager {
    private const val YT_BREAK_MS = 60 * 60 * 1000L
    private val mutex = Mutex()

    enum class EmergencyResult { ENDED, WRONG_PHRASE, USED_THIS_MONTH, NO_LOCK }

    fun activeLock(st: AppState, now: Clocks): ActiveLock? = st.lock?.takeIf { it.timing.isActive(now) }

    fun ytBreakActive(st: AppState, now: Clocks) =
        activeLock(st, now) != null && st.ytBreak?.isActive(now) == true

    /** Whether the lock blocks YouTube in any way, so the daily break means something. */
    fun blocksYoutube(lock: ActiveLock) =
        Blocklist.YOUTUBE in lock.groups || lock.apps.any { it in Blocklist.YOUTUBE_PACKAGES }

    /** Domains the DNS filter blocks right now; empty when the VPN isn't needed. */
    fun blockedDomains(st: AppState, now: Clocks): Set<String> {
        val lock = activeLock(st, now) ?: return emptySet()
        val groups = if (ytBreakActive(st, now)) lock.groups - Blocklist.YOUTUBE else lock.groups
        return Blocklist.domainsFor(groups, lock.sites)
    }

    suspend fun start(ctx: Context, durationMs: Long, apps: Set<String>, groups: Set<String>, sites: Set<String>, note: String) {
        val app = ctx.app
        val state = mutex.withLock {
            val now = clocksNow(ctx)
            if (activeLock(app.repo.current(), now) != null) return
            val timing = LockTiming.start(durationMs, now)
            val id = app.db.dao().insert(
                HistoryEntry(
                    kind = HistoryEntry.KIND_LOCK,
                    startedAt = now.wall,
                    plannedEnd = timing.unlockAtWall,
                    endedAt = null,
                    outcome = HistoryEntry.OUTCOME_ACTIVE,
                    apps = apps.joinToString(","),
                    sites = (groups + sites).joinToString(","),
                    note = note.trim(),
                ),
            )
            val endDate = Format.localDate(timing.unlockAtWall)
            app.repo.update {
                it.copy(
                    lock = ActiveLock(timing, now.wall, apps, groups, sites, note.trim(), id),
                    ytBreak = null,
                    stats = Streak.onLockStarted(it.stats, endDate, LocalDate.now()),
                    lastApps = apps,
                    lastGroups = groups,
                    lastSites = sites,
                )
            }
        }
        sync(ctx, state)
    }

    /** Ends a lock whose time is up and a YouTube break that ran out. Cheap; call it often. */
    suspend fun tick(ctx: Context) {
        val app = ctx.app
        val state = mutex.withLock {
            val now = clocksNow(ctx)
            val st = app.repo.current()
            val lockOver = st.lock != null && !st.lock.timing.isActive(now)
            val breakOver = st.ytBreak != null && (lockOver || !st.ytBreak.isActive(now))
            if (!lockOver && !breakOver) return@withLock st
            val updated = app.repo.update {
                it.copy(lock = if (lockOver) null else it.lock, ytBreak = if (breakOver) null else it.ytBreak)
            }
            if (lockOver) {
                app.db.dao().finish(st.lock!!.historyId, HistoryEntry.OUTCOME_COMPLETED, now.wall)
                Notifications.showEvent(ctx, ctx.getString(R.string.notif_done_title), ctx.getString(R.string.notif_done_text))
            }
            updated
        }
        sync(ctx, state)
    }

    /**
     * Re-reads the remaining time after the clock changed (or after a reboot,
     * when only the wall-clock end is left), then tidies up as [tick] does.
     */
    suspend fun reanchor(ctx: Context, afterReboot: Boolean) {
        mutex.withLock {
            val now = clocksNow(ctx)
            fun LockTiming.fix() = if (afterReboot) this.afterReboot(now) else this.reanchor(now)
            ctx.app.repo.update { s ->
                s.copy(lock = s.lock?.let { it.copy(timing = it.timing.fix()) }, ytBreak = s.ytBreak?.fix())
            }
        }
        tick(ctx)
    }

    /** Opens YouTube for an hour, once per calendar day. */
    suspend fun startYoutubeBreak(ctx: Context): Boolean {
        val state = mutex.withLock {
            val now = clocksNow(ctx)
            val today = LocalDate.now().toString()
            val st = ctx.app.repo.current()
            val lock = activeLock(st, now) ?: return false
            if (!blocksYoutube(lock) || st.ytBreakDay == today) return false
            val length = minOf(YT_BREAK_MS, lock.timing.remaining(now))
            ctx.app.repo.update { it.copy(ytBreak = LockTiming.start(length, now), ytBreakDay = today) }
        }
        sync(ctx, state)
        return true
    }

    suspend fun emergency(ctx: Context, typed: String): EmergencyResult {
        if (!EmergencySwitch.matches(typed)) return EmergencyResult.WRONG_PHRASE
        val app = ctx.app
        val state = mutex.withLock {
            val now = clocksNow(ctx)
            val today = LocalDate.now()
            val st = app.repo.current()
            val lock = activeLock(st, now) ?: return EmergencyResult.NO_LOCK
            val lastUsed = st.emergencyMonth?.let { runCatching { YearMonth.parse(it) }.getOrNull() }
            if (!EmergencySwitch.isAvailable(lastUsed, today)) return EmergencyResult.USED_THIS_MONTH
            val updated = app.repo.update {
                it.copy(
                    lock = null,
                    ytBreak = null,
                    emergencyMonth = YearMonth.from(today).toString(),
                    stats = Streak.onEmergency(it.stats, today),
                )
            }
            val dao = app.db.dao()
            dao.finish(lock.historyId, HistoryEntry.OUTCOME_ENDED_EARLY, now.wall)
            dao.insert(
                HistoryEntry(
                    kind = HistoryEntry.KIND_EMERGENCY,
                    startedAt = now.wall,
                    plannedEnd = lock.timing.endsAtWall(now),
                    endedAt = now.wall,
                    outcome = HistoryEntry.OUTCOME_EMERGENCY,
                    apps = lock.apps.joinToString(","),
                    sites = (lock.groups + lock.sites).joinToString(","),
                    note = lock.note,
                ),
            )
            updated
        }
        sync(ctx, state)
        return EmergencyResult.ENDED
    }

    /** Brings the alarm, the notification and the VPN in line with [st]. */
    fun sync(ctx: Context, st: AppState) {
        val now = clocksNow(ctx)
        val lock = activeLock(st, now)
        val nextChange = listOfNotNull(
            lock?.timing?.remaining(now),
            st.ytBreak?.remaining(now)?.takeIf { it > 0 },
        ).minOrNull()
        scheduleAlarm(ctx, nextChange)
        if (lock == null) {
            Notifications.cancelLock(ctx)
            return // the VPN stops itself when it sees the lock is gone
        }
        Notifications.showLock(ctx, lock.timing.endsAtWall(now))
        if (blockedDomains(st, now).isNotEmpty()) DnsVpnService.start(ctx)
    }

    private fun scheduleAlarm(ctx: Context, inMs: Long?) {
        val am = ctx.getSystemService(AlarmManager::class.java)
        val pi = PendingIntent.getBroadcast(
            ctx, 0, Intent(ctx, AlarmReceiver::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        if (inMs == null) {
            am.cancel(pi)
        } else {
            am.setAndAllowWhileIdle(AlarmManager.ELAPSED_REALTIME_WAKEUP, SystemClock.elapsedRealtime() + inMs + 1000, pi)
        }
    }
}
