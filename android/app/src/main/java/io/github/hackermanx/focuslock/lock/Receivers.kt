package io.github.hackermanx.focuslock.lock

import android.app.admin.DeviceAdminReceiver
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import io.github.hackermanx.focuslock.R
import io.github.hackermanx.focuslock.app
import kotlinx.coroutines.launch

private fun BroadcastReceiver.runAsync(ctx: Context, block: suspend () -> Unit) {
    val pending = goAsync()
    ctx.app.scope.launch {
        try {
            block()
        } finally {
            pending.finish()
        }
    }
}

/** Fires when the lock or a YouTube break is due to end. */
class AlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) = runAsync(context) { LockManager.tick(context) }
}

/** Reboots restart the VPN; clock changes re-read the remaining time. */
class SystemEventReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val afterReboot = intent.action == Intent.ACTION_BOOT_COMPLETED
        runAsync(context) { LockManager.reanchor(context, afterReboot) }
    }
}

/** Being a device admin is what stops FocusLock being uninstalled. It asks for no policies. */
class AdminReceiver : DeviceAdminReceiver() {
    override fun onDisableRequested(context: Context, intent: Intent): CharSequence =
        context.getString(R.string.admin_disable_warning)
}
