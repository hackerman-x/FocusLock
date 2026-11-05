package io.github.hackermanx.focuslock.ui

import android.Manifest
import android.net.VpnService
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import io.github.hackermanx.focuslock.launchSafely
import io.github.hackermanx.focuslock.lock.Permissions

@Composable
fun OnboardingScreen(onDone: () -> Unit) {
    val ctx = LocalContext.current
    val c = FL.colors
    var refresh by remember { mutableIntStateOf(0) }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { refresh++ }
    val notifications = remember(refresh) { Permissions.notificationsOn(ctx) }
    val accessibility = remember(refresh) { Permissions.accessibilityOn(ctx) }
    val admin = remember(refresh) { Permissions.adminOn(ctx) }
    val vpn = remember(refresh) { Permissions.vpnAllowed(ctx) }
    val battery = remember(refresh) { Permissions.batteryUnrestricted(ctx) }

    val onResult: (Any?) -> Unit = { refresh++ }
    val notifLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission(), onResult)
    val activityLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult(), onResult)

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Header("FOCUSLOCK", c.yellow, "set up your phone")
        Body(
            "FocusLock needs a few permissions to block apps and websites, and to stay on until your lock ends. " +
                "Nothing you do leaves your phone.",
        )

        Step(1, "Notifications", notifications, "Shows that a lock is on and tells you when it ends.") {
            GhostButton("Allow") {
                if (Build.VERSION.SDK_INT >= 33) notifLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                else ctx.launchSafely(Permissions.notificationSettings(ctx))
            }
        }

        Step(
            2, "Accessibility", accessibility,
            "Blocks apps. It sees which app is open, reads browser address bars for blocked sites, " +
                "and closes FocusLock's own settings during a lock.",
        ) {
            if (Build.VERSION.SDK_INT >= 33 && !accessibility) {
                Column(
                    Modifier.fillMaxWidth().background(c.surface2, RoundedCornerShape(10.dp)).padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Label("Greyed out? Allow restricted settings", color = c.yellow)
                    Body(
                        "Android 13 and newer block this switch for apps installed from an APK. To allow it:\n" +
                            "1. Tap ACCESSIBILITY, find FocusLock (maybe under \"Downloaded apps\") and try to turn it on. " +
                            "Android says \"Restricted setting\". Close that.\n" +
                            "2. Tap APP INFO, then ⋮ in the top-right corner → Allow restricted settings, and confirm.\n" +
                            "3. Tap ACCESSIBILITY again and turn FocusLock on.",
                    )
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                GhostButton("Accessibility") { ctx.launchSafely(Permissions.accessibilitySettings()) }
                if (Build.VERSION.SDK_INT >= 33) GhostButton("App info") { ctx.launchSafely(Permissions.appInfo(ctx)) }
            }
        }

        Step(3, "Uninstall protection", admin, "Device admin, so FocusLock can't be uninstalled during a lock. It asks for nothing else.") {
            GhostButton("Activate") { activityLauncher.launch(Permissions.addAdmin(ctx)) }
        }

        Step(4, "Website filter", vpn, "A VPN that only answers DNS lookups, so blocked sites don't load. Your other traffic doesn't go through it.") {
            GhostButton("Allow") {
                val ask = VpnService.prepare(ctx)
                if (ask != null) activityLauncher.launch(ask) else refresh++
            }
        }

        Step(5, "Battery (recommended)", battery, "Stops Android from putting FocusLock to sleep in the background.") {
            GhostButton("Allow") { ctx.launchSafely(Permissions.batterySettings(ctx)) }
        }

        Spacer(Modifier.height(4.dp))
        if (!accessibility || !admin) Body("Steps 2 and 3 are needed before you can start a lock.", color = c.yellow)
        PinkButton(if (accessibility && admin) "Done" else "Finish later", onClick = onDone)
        Spacer(Modifier.height(16.dp))
    }
}

@Composable
private fun Step(n: Int, title: String, done: Boolean, text: String, actions: @Composable () -> Unit) {
    val c = FL.colors
    Panel(accent = if (done) null else c.borderStrong) {
        Row {
            Text("$n. ", fontFamily = Mono, fontWeight = FontWeight.Bold, color = c.pink, fontSize = 15.sp)
            Text(title, fontWeight = FontWeight.SemiBold, color = c.ink, fontSize = 15.sp, modifier = Modifier.weight(1f))
            Text(if (done) "DONE" else "TO DO", fontFamily = Mono, fontSize = 12.sp, color = if (done) c.cyan else c.yellow)
        }
        Body(text)
        if (!done) actions()
    }
}
