package io.github.hackermanx.focuslock.data

import android.content.Context
import androidx.datastore.core.handlers.ReplaceFileCorruptionHandler
import androidx.datastore.preferences.core.MutablePreferences
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.emptyPreferences
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.stringSetPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import io.github.hackermanx.focuslock.core.LockTiming
import io.github.hackermanx.focuslock.core.Stats
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.runBlocking
import java.io.IOException
import java.time.LocalDate

private val Context.dataStore by preferencesDataStore(
    name = "focuslock",
    corruptionHandler = ReplaceFileCorruptionHandler { emptyPreferences() },
)

/** The lock that is running. Its block lists are a snapshot taken at the start. */
data class ActiveLock(
    val timing: LockTiming,
    val startedAtWall: Long,
    /** Package names. */
    val apps: Set<String>,
    /** Keys of Blocklist.DOMAIN_GROUPS. */
    val groups: Set<String>,
    /** The user's own domains. */
    val sites: Set<String>,
    val note: String,
    val historyId: Long,
)

/** Everything kept in DataStore: lock state, settings and stats. */
data class AppState(
    val lock: ActiveLock? = null,
    val ytBreak: LockTiming? = null,
    /** The day the YouTube break was last used (ISO date). */
    val ytBreakDay: String? = null,
    /** The month the emergency switch was last used ("2026-11"). */
    val emergencyMonth: String? = null,
    val stats: Stats = Stats(),
    val customSites: List<String> = emptyList(),
    val lastApps: Set<String> = emptySet(),
    val lastGroups: Set<String> = emptySet(),
    val lastSites: Set<String> = emptySet(),
    /** "system", "dark" or "light". */
    val theme: String = "system",
    val onboardingDone: Boolean = false,
)

class Repo(context: Context, scope: CoroutineScope) {
    private val store = context.dataStore

    private val data: Flow<AppState> = store.data
        .catch { if (it is IOException) emit(emptyPreferences()) else throw it }
        .map { it.toAppState() }

    /**
     * Always loaded, so the accessibility service can check every screen
     * change without waiting on disk.
     */
    val state: StateFlow<AppState> =
        data.stateIn(scope, SharingStarted.Eagerly, runBlocking { data.first() })

    /** The state on disk right now (state.value can lag a write by a moment). */
    suspend fun current(): AppState = data.first()

    suspend fun update(transform: (AppState) -> AppState): AppState {
        var result = AppState()
        store.edit { prefs ->
            result = transform(prefs.toAppState())
            prefs.clear()
            prefs.write(result)
        }
        return result
    }
}

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

private fun Preferences.toAppState(): AppState {
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
    )
}

private fun MutablePreferences.write(s: AppState) {
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
}
