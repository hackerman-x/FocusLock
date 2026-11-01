package io.github.hackermanx.focuslock

import android.app.Application
import android.content.Context
import io.github.hackermanx.focuslock.data.HistoryDb
import io.github.hackermanx.focuslock.data.Repo
import io.github.hackermanx.focuslock.lock.Notifications
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob

class FocusLockApp : Application() {
    /** For work that must outlive a screen or a broadcast (writing state, logging attempts). */
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    lateinit var repo: Repo
        private set
    lateinit var db: HistoryDb
        private set

    override fun onCreate() {
        super.onCreate()
        repo = Repo(this, scope)
        db = HistoryDb.open(this)
        Notifications.createChannels(this)
    }
}

val Context.app: FocusLockApp get() = applicationContext as FocusLockApp
