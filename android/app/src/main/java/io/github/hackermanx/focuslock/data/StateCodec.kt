package io.github.hackermanx.focuslock.data

import androidx.datastore.preferences.core.MutablePreferences
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.stringSetPreferencesKey
import io.github.hackermanx.focuslock.core.LockTiming
import io.github.hackermanx.focuslock.core.Stats
import java.time.LocalDate

/** How AppState is stored in DataStore. Kept apart from Repo so it can be unit tested. */
private object Keys {
    val lockStarted = longPreferencesKey("lock_started")
    val lockApps = stringSetPreferencesKey("lock_apps")
    val lockGroups = stringSetPreferencesKey("lock_groups")
    val lockSites = stringSetPreferencesKey("lock_sites")
    val lockNote = stringPreferencesKey("lock_note")
    val lockHistoryId = longPreferencesKey("lock_history_id")
    val ytBreakDay = stringPreferencesKey("yt_break_day")
    val emergencyMonth = stringPreferencesKey("emergency_month")
    val streak = intPreferencesKey("streak")
    val longestStreak = intPreferencesKey("longest_streak")
    val totalSessions = intPreferencesKey("total_sessions")
    val lastUnlockDate = stringPreferencesKey("last_unlock_date")
    val lastStartDate = stringPreferencesKey("last_start_date")
    val customSites = stringPreferencesKey("custom_sites")
    val lastApps = stringSetPreferencesKey("last_apps")
    val lastGroups = stringSetPreferencesKey("last_groups")
    val lastSites = stringSetPreferencesKey("last_sites")
    val theme = stringPreferencesKey("theme")
    val onboardingDone = booleanPreferencesKey("onboarding_done")
    val scanConsent = booleanPreferencesKey("scan_consent")
    val scanIgnored = stringSetPreferencesKey("scan_ignored")
    val scanSeen = stringSetPreferencesKey("scan_seen")
    val addedApps = stringSetPreferencesKey("added_apps")
}

private fun Preferences.timing(prefix: String): LockTiming? {
    val end = this[longPreferencesKey("${prefix}_end")] ?: return null
    return LockTiming(
        unlockAtWall = end,
        anchorElapsed = this[longPreferencesKey("${prefix}_anchor_elapsed")] ?: 0,
        anchorRemaining = this[longPreferencesKey("${prefix}_anchor_remaining")] ?: 0,
        bootCount = this[intPreferencesKey("${prefix}_boot")] ?: -1,
    )
}

private fun MutablePreferences.putTiming(prefix: String, t: LockTiming?) {
    if (t == null) return
    this[longPreferencesKey("${prefix}_end")] = t.unlockAtWall
    this[longPreferencesKey("${prefix}_anchor_elapsed")] = t.anchorElapsed
    this[longPreferencesKey("${prefix}_anchor_remaining")] = t.anchorRemaining
    this[intPreferencesKey("${prefix}_boot")] = t.bootCount
}

private fun String.toDateOrNull(): LocalDate? = runCatching { LocalDate.parse(this) }.getOrNull()

internal fun Preferences.toAppState(): AppState {
    val lock = timing("lock")?.let {
        ActiveLock(
            timing = it,
            startedAtWall = this[Keys.lockStarted] ?: 0,
            apps = this[Keys.lockApps].orEmpty(),
            groups = this[Keys.lockGroups].orEmpty(),
            sites = this[Keys.lockSites].orEmpty(),
            note = this[Keys.lockNote].orEmpty(),
            historyId = this[Keys.lockHistoryId] ?: 0,
        )
    }
    return AppState(
        lock = lock,
        ytBreak = timing("yt"),
        ytBreakDay = this[Keys.ytBreakDay],
        emergencyMonth = this[Keys.emergencyMonth],
        stats = Stats(
            streak = this[Keys.streak] ?: 0,
            longestStreak = this[Keys.longestStreak] ?: 0,
            totalSessions = this[Keys.totalSessions] ?: 0,
            lastUnlockDate = this[Keys.lastUnlockDate]?.toDateOrNull(),
            lastStartDate = this[Keys.lastStartDate]?.toDateOrNull(),
        ),
        customSites = this[Keys.customSites]?.split('\n')?.filter { it.isNotBlank() }.orEmpty(),
        lastApps = this[Keys.lastApps].orEmpty(),
        lastGroups = this[Keys.lastGroups].orEmpty(),
        lastSites = this[Keys.lastSites].orEmpty(),
        theme = this[Keys.theme] ?: "system",
        onboardingDone = this[Keys.onboardingDone] ?: false,
        scanConsent = this[Keys.scanConsent],
        scanIgnored = this[Keys.scanIgnored].orEmpty(),
        scanSeen = this[Keys.scanSeen].orEmpty(),
        addedApps = this[Keys.addedApps].orEmpty(),
    )
}

internal fun MutablePreferences.write(s: AppState) {
    s.lock?.let {
        putTiming("lock", it.timing)
        this[Keys.lockStarted] = it.startedAtWall
        this[Keys.lockApps] = it.apps
        this[Keys.lockGroups] = it.groups
        this[Keys.lockSites] = it.sites
        this[Keys.lockNote] = it.note
        this[Keys.lockHistoryId] = it.historyId
    }
    putTiming("yt", s.ytBreak)
    s.ytBreakDay?.let { this[Keys.ytBreakDay] = it }
    s.emergencyMonth?.let { this[Keys.emergencyMonth] = it }
    this[Keys.streak] = s.stats.streak
    this[Keys.longestStreak] = s.stats.longestStreak
    this[Keys.totalSessions] = s.stats.totalSessions
    s.stats.lastUnlockDate?.let { this[Keys.lastUnlockDate] = it.toString() }
    s.stats.lastStartDate?.let { this[Keys.lastStartDate] = it.toString() }
    this[Keys.customSites] = s.customSites.joinToString("\n")
    this[Keys.lastApps] = s.lastApps
    this[Keys.lastGroups] = s.lastGroups
    this[Keys.lastSites] = s.lastSites
    this[Keys.theme] = s.theme
    this[Keys.onboardingDone] = s.onboardingDone
    s.scanConsent?.let { this[Keys.scanConsent] = it }
    this[Keys.scanIgnored] = s.scanIgnored
    this[Keys.scanSeen] = s.scanSeen
    this[Keys.addedApps] = s.addedApps
}
