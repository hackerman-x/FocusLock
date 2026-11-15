package io.github.hackermanx.focuslock.lock

import android.content.Context
import io.github.hackermanx.focuslock.app
import io.github.hackermanx.focuslock.core.AppScan
import io.github.hackermanx.focuslock.core.Blocklist
import io.github.hackermanx.focuslock.core.Suggestion
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/** The latest scan: suggestions, and which of them weren't suggested before. */
data class ScanResult(val suggestions: List<Suggestion>, val new: Set<String>)

/** Runs the app scan and keeps its result for the Apps panel. Only reads the app list. */
object Scanner {
    private val mutex = Mutex()
    private val _result = MutableStateFlow<ScanResult?>(null)
    val result: StateFlow<ScanResult?> = _result
    private val _running = MutableStateFlow(false)
    val running: StateFlow<Boolean> = _running

    /** Scans now; returns the result (also kept in [result]). */
    suspend fun scan(ctx: Context): ScanResult = mutex.withLock {
        _running.value = true
        try {
            val apps = withContext(Dispatchers.IO) { AppCatalog.scanCandidates(ctx) }
            val repo = ctx.app.repo
            val st = repo.current()
            val listed = Blocklist.SUGGESTED_PACKAGES.toSet() + st.addedApps
            val found = AppScan.suggestions(apps, ctx.packageName, st.scanIgnored, listed)
            val new = AppScan.newSince(found, st.scanSeen)
            if (new.isNotEmpty()) repo.update { it.copy(scanSeen = it.scanSeen + new) }
            ScanResult(found, new).also { _result.value = it }
        } finally {
            _running.value = false
        }
    }

    /** The user's answer to the first-start question. Allowing it scans straight away. */
    suspend fun setConsent(ctx: Context, allowed: Boolean): ScanResult? {
        ctx.app.repo.update { it.copy(scanConsent = allowed) }
        if (!allowed) {
            _result.value = null
            return null
        }
        return scan(ctx)
    }

    /** Add: list the app in the Apps panel, unticked. Nothing is blocked until the user ticks it and starts a lock. */
    suspend fun add(ctx: Context, pkg: String) {
        ctx.app.repo.update { it.copy(addedApps = it.addedApps + pkg) }
        drop(pkg)
    }

    /** Ignore: never suggest this app again. */
    suspend fun ignore(ctx: Context, pkg: String) {
        ctx.app.repo.update { it.copy(scanIgnored = it.scanIgnored + pkg) }
        drop(pkg)
    }

    private fun drop(pkg: String) {
        _result.value = _result.value?.let { r -> ScanResult(r.suggestions.filter { it.pkg != pkg }, r.new - pkg) }
    }
}
