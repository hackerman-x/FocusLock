package io.github.hackermanx.focuslock.lock

import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.Uri
import android.net.VpnService
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import android.telecom.TelecomManager
import androidx.core.app.NotificationManagerCompat
import io.github.hackermanx.focuslock.R
import io.github.hackermanx.focuslock.block.GuardService
import io.github.hackermanx.focuslock.core.ScreenRules

/** What FocusLock needs from Android, and the screens that grant it. */
object Permissions {
    fun admin(ctx: Context) = ComponentName(ctx, AdminReceiver::class.java)

    fun accessibilityOn(ctx: Context): Boolean {
        val enabled = Settings.Secure.getString(ctx.contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES) ?: return false
        val me = ComponentName(ctx, GuardService::class.java)
        return enabled.split(':').any { ComponentName.unflattenFromString(it) == me }
    }

    fun adminOn(ctx: Context) = ctx.getSystemService(DevicePolicyManager::class.java).isAdminActive(admin(ctx))

    fun vpnAllowed(ctx: Context) = VpnService.prepare(ctx) == null

    fun notificationsOn(ctx: Context) = NotificationManagerCompat.from(ctx).areNotificationsEnabled()

    fun batteryUnrestricted(ctx: Context) =
        ctx.getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(ctx.packageName)

    /** Private DNS set to a specific provider sends lookups around the VPN, so websites wouldn't be blocked. */
    fun privateDnsBypassesVpn(ctx: Context): Boolean {
        if (Build.VERSION.SDK_INT < 28) return false
        val cm = ctx.getSystemService(ConnectivityManager::class.java)
        @Suppress("DEPRECATION")
        return cm.allNetworks.any { cm.getLinkProperties(it)?.privateDnsServerName != null }
    }

    fun accessibilitySettings() = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)

    fun appInfo(ctx: Context) =
        Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", ctx.packageName, null))

    fun addAdmin(ctx: Context) = Intent(DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN)
        .putExtra(DevicePolicyManager.EXTRA_DEVICE_ADMIN, admin(ctx))
        .putExtra(DevicePolicyManager.EXTRA_ADD_EXPLANATION, ctx.getString(R.string.admin_explanation))

    fun removeAdmin(ctx: Context) = ctx.getSystemService(DevicePolicyManager::class.java).removeActiveAdmin(admin(ctx))

    @Suppress("BatteryLife")
    fun batterySettings(ctx: Context) =
        Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:${ctx.packageName}"))

    fun notificationSettings(ctx: Context) = Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
        .putExtra(Settings.EXTRA_APP_PACKAGE, ctx.packageName)
}

data class AppInfo(val pkg: String, val label: String)

/** Apps that can go on the block list. */
object AppCatalog {
    /** Never blockable: FocusLock, the home screen, the phone app and Settings. */
    private fun neverBlock(ctx: Context): Set<String> {
        val pm = ctx.packageManager
        val home = pm.resolveActivity(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME), PackageManager.MATCH_DEFAULT_ONLY)
            ?.activityInfo?.packageName
        val dialer = ctx.getSystemService(TelecomManager::class.java)?.defaultDialerPackage
        return setOfNotNull(ctx.packageName, home, dialer)
    }

    fun launchable(ctx: Context): List<AppInfo> {
        val pm = ctx.packageManager
        val excluded = neverBlock(ctx)
        return pm.queryIntentActivities(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER), 0)
            .map { AppInfo(it.activityInfo.packageName, it.loadLabel(pm).toString()) }
            .distinctBy { it.pkg }
            .filter { it.pkg !in excluded && !ScreenRules.watches(it.pkg) }
            .sortedBy { it.label.lowercase() }
    }

    fun label(ctx: Context, pkg: String): String = try {
        ctx.packageManager.getApplicationLabel(ctx.packageManager.getApplicationInfo(pkg, 0)).toString()
    } catch (_: PackageManager.NameNotFoundException) {
        pkg
    }
}
