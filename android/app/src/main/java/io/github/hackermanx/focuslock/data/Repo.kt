package io.github.hackermanx.focuslock.data

import android.content.Context
import androidx.datastore.core.handlers.ReplaceFileCorruptionHandler
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.emptyPreferences
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
    /** The answer to "Find distractions for you?": null until asked. */
    val scanConsent: Boolean? = null,
    /** Packages the user tapped Ignore on; never suggested again. */
    val scanIgnored: Set<String> = emptySet(),
    /** Packages already suggested once, so later scans can mark only new finds. */
    val scanSeen: Set<String> = emptySet(),
    /** Packages added from the scan; listed in the Apps panel next to the defaults. */
    val addedApps: Set<String> = emptySet(),
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
