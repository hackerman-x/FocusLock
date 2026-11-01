package io.github.hackermanx.focuslock.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import io.github.hackermanx.focuslock.app
import io.github.hackermanx.focuslock.core.Blocklist
import io.github.hackermanx.focuslock.core.EmergencySwitch
import io.github.hackermanx.focuslock.core.Format
import io.github.hackermanx.focuslock.data.AppState
import io.github.hackermanx.focuslock.lock.Permissions
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.YearMonth

@Composable
fun SettingsScreen(st: AppState, lockActive: Boolean, onSetup: () -> Unit) {
    val ctx = LocalContext.current
    val c = FL.colors
    val scope = rememberCoroutineScope()
    var newSite by remember { mutableStateOf("") }
    var refresh by remember { mutableIntStateOf(0) }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { refresh++ }
    val admin = remember(refresh) { Permissions.adminOn(ctx) }
    val version = remember {
        runCatching { ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName }.getOrNull() ?: "?"
    }
    fun update(transform: (AppState) -> AppState) = scope.launch { ctx.app.repo.update(transform) }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Header("SETTINGS", c.yellow)

        Panel("Theme") {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("system" to "System", "dark" to "Dark", "light" to "Light").forEach { (key, label) ->
                    Chip(label, st.theme == key) { update { it.copy(theme = key) } }
                }
            }
        }

        Panel("Your websites") {
            Body("Added to the website list on the Lock tab. Subdomains are blocked too. Changes don't affect a lock that's already running.")
            st.customSites.forEach { site ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(site, color = c.ink, fontSize = 15.sp, modifier = Modifier.weight(1f))
                    TextButton(onClick = { update { s -> s.copy(customSites = s.customSites - site, lastSites = s.lastSites - site) } }) {
                        Text("REMOVE", fontFamily = Mono, fontSize = 12.sp, color = c.pink)
                    }
                }
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = newSite, onValueChange = { newSite = it }, singleLine = true,
                    label = { Text("reddit.com") }, colors = fieldColors(), modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(8.dp))
                GhostButton("Add", enabled = Blocklist.normalizeSite(newSite) != null) {
                    val site = Blocklist.normalizeSite(newSite) ?: return@GhostButton
                    newSite = ""
                    update { s -> if (site in s.customSites) s else s.copy(customSites = s.customSites + site) }
                }
            }
        }

        Panel("Permissions") {
            Body("Accessibility, uninstall protection, the website filter and battery.")
            GhostButton("Check permissions", onClick = onSetup)
        }

        Panel("Uninstalling FocusLock") {
            when {
                lockActive -> Body("Uninstall protection stays on until the lock ends.")
                admin -> {
                    Body("Uninstall protection is on. Turn it off here first, then uninstall as usual. Starting a lock needs it on again.")
                    GhostButton("Allow uninstall", color = c.pink) {
                        Permissions.removeAdmin(ctx)
                        refresh++
                    }
                }
                else -> Body("Uninstall protection is off. FocusLock can be uninstalled.")
            }
        }

        Panel("Emergency switch") {
            val lastUsed = st.emergencyMonth?.let { runCatching { YearMonth.parse(it) }.getOrNull() }
            val next = EmergencySwitch.nextAvailable(lastUsed, LocalDate.now())
            Body(
                "During a lock, typing \"${EmergencySwitch.PHRASE}\" ends it at once. " +
                    "Once per calendar month; it resets your streak and is saved in your history.",
            )
            Text(
                if (next == null) "Available" else "Used this month. Next available: ${Format.day(next)}",
                fontFamily = Mono, fontSize = 13.sp, color = if (next == null) c.cyan else c.yellow,
            )
        }

        Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
            Text("FocusLock $version for Android", fontFamily = Mono, fontSize = 11.sp, color = c.inkFaint)
        }
        Spacer(Modifier.height(24.dp))
    }
}
