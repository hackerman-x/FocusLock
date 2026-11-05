package io.github.hackermanx.focuslock.ui

import android.net.VpnService
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import io.github.hackermanx.focuslock.app
import io.github.hackermanx.focuslock.core.Blocklist
import io.github.hackermanx.focuslock.core.Clocks
import io.github.hackermanx.focuslock.core.Format
import io.github.hackermanx.focuslock.data.AppState
import io.github.hackermanx.focuslock.lock.AppCatalog
import io.github.hackermanx.focuslock.lock.AppInfo
import io.github.hackermanx.focuslock.lock.LockManager
import io.github.hackermanx.focuslock.lock.Permissions
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private val PRESETS = listOf(25L, 60L, 120L, 240L, 480L, 1440L, 4320L, 10080L)

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun LockScreen(st: AppState, now: Clocks, onSetup: () -> Unit) {
    val ctx = LocalContext.current
    val c = FL.colors
    val scope = rememberCoroutineScope()

    var minutes by remember { mutableLongStateOf(60L) }
    var apps by remember { mutableStateOf(st.lastApps) }
    var groups by remember { mutableStateOf(st.lastGroups) }
    var sites by remember { mutableStateOf(st.lastSites.intersect(st.customSites.toSet())) }
    var note by remember { mutableStateOf("") }
    var search by remember { mutableStateOf("") }
    var showAllApps by remember { mutableStateOf(false) }
    var newSite by remember { mutableStateOf("") }
    var confirming by remember { mutableStateOf(false) }
    var refresh by remember { mutableIntStateOf(0) }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { refresh++ }

    val installed by produceState(emptyList<AppInfo>()) {
        value = withContext(Dispatchers.IO) { AppCatalog.launchable(ctx) }
    }
    val byPkg = remember(installed) { installed.associateBy { it.pkg } }
    val suggested = remember(installed) { Blocklist.SUGGESTED_PACKAGES.mapNotNull { byPkg[it] } }
    val ready = remember(refresh) { Permissions.accessibilityOn(ctx) && Permissions.adminOn(ctx) }
    val privateDns = remember(refresh) { Permissions.privateDnsBypassesVpn(ctx) }
    val wantsSites = groups.isNotEmpty() || sites.isNotEmpty()

    val vpnLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        if (VpnService.prepare(ctx) == null) confirming = true
    }

    fun toggle(set: Set<String>, item: String, on: Boolean) = if (on) set + item else set - item

    LazyColumn(
        Modifier.fillMaxSize().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item { Header("FOCUSLOCK", c.yellow, "lock away distractions") }

        if (!ready) {
            item {
                Panel("Setup needed", accent = c.yellow) {
                    Body("Turn on Accessibility and Uninstall protection before starting a lock.")
                    GhostButton("Finish setup", onClick = onSetup)
                }
            }
        }

        item {
            Panel("How long") {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    PRESETS.forEach { m -> Chip(Format.duration(m), minutes == m) { minutes = m } }
                }
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Stepper("d", minutes / 1440, 0..30) { minutes = it * 1440 + minutes % 1440 }
                    Stepper("h", minutes % 1440 / 60, 0..23) { minutes = minutes / 1440 * 1440 + it * 60 + minutes % 60 }
                    Stepper("m", minutes % 60, 0..55, step = 5) { minutes = minutes / 60 * 60 + it }
                }
                Body("Ends ${Format.end(now.wall + minutes * 60_000)}", color = c.cyan)
            }
        }

        item {
            Panel("Apps") {
                if (installed.isEmpty()) Body("Loading apps…")
                suggested.forEach { a -> CheckRow(a.label, a.pkg in apps) { apps = toggle(apps, a.pkg, it) } }
                // Picked earlier from the full list.
                apps.filter { p -> suggested.none { it.pkg == p } }.mapNotNull { byPkg[it] }.forEach { a ->
                    CheckRow(a.label, true) { apps = toggle(apps, a.pkg, it) }
                }
                GhostButton(if (showAllApps) "Hide app list" else "Choose from all apps") { showAllApps = !showAllApps }
                if (showAllApps) {
                    OutlinedTextField(
                        value = search, onValueChange = { search = it }, singleLine = true,
                        label = { Text("Search apps") }, colors = fieldColors(), modifier = Modifier.fillMaxWidth(),
                    )
                }
            }
        }
        if (showAllApps) {
            val q = search.trim().lowercase()
            items(installed.filter { q.isEmpty() || q in it.label.lowercase() }, key = { it.pkg }) { a ->
                CheckRow(a.label, a.pkg in apps, sub = a.pkg) { apps = toggle(apps, a.pkg, it) }
            }
        }

        item {
            Panel("Websites") {
                Blocklist.DOMAIN_GROUPS.keys.forEach { g ->
                    CheckRow(Blocklist.label(g), g in groups) { groups = toggle(groups, g, it) }
                }
                st.customSites.forEach { s -> CheckRow(s, s in sites) { sites = toggle(sites, s, it) } }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = newSite, onValueChange = { newSite = it }, singleLine = true,
                        label = { Text("Add a site (reddit.com)") }, colors = fieldColors(), modifier = Modifier.weight(1f),
                    )
                    Spacer(Modifier.width(8.dp))
                    GhostButton("Add", enabled = Blocklist.normalizeSite(newSite) != null) {
                        val site = Blocklist.normalizeSite(newSite) ?: return@GhostButton
                        newSite = ""
                        sites = sites + site
                        scope.launch {
                            ctx.app.repo.update { s -> if (site in s.customSites) s else s.copy(customSites = s.customSites + site) }
                        }
                    }
                }
                if (wantsSites && privateDns) {
                    Body(
                        "Private DNS is set to a provider, so lookups skip FocusLock's filter. Set it to Automatic or Off " +
                            "(Settings → Network & internet → Private DNS) first. It can't be changed during a lock.",
                        color = c.yellow,
                    )
                }
            }
        }

        item {
            Panel("Focus note (optional)") {
                OutlinedTextField(
                    value = note, onValueChange = { if (it.length <= 200) note = it },
                    placeholder = { Text("What are you focusing on?") }, colors = fieldColors(), modifier = Modifier.fillMaxWidth(),
                )
            }
        }

        item {
            val nothing = apps.isEmpty() && !wantsSites
            if (nothing) Body("Pick at least one app or website.", modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(6.dp))
            PinkButton("Start lock", enabled = ready && !nothing && minutes > 0) {
                val ask = if (wantsSites) VpnService.prepare(ctx) else null
                if (ask != null) vpnLauncher.launch(ask) else confirming = true
            }
            Spacer(Modifier.height(24.dp))
        }
    }

    if (confirming) {
        ConfirmLockDialog(
            summary = "Blocks ${apps.size} app(s) and ${groups.size + sites.size} website group(s) until " +
                "${Format.end(System.currentTimeMillis() + minutes * 60_000)}.\n\nThere's no early unlock, apart from " +
                "the emergency switch (once a month, and it resets your streak).",
            onCancel = { confirming = false },
            onConfirm = {
                confirming = false
                val durationMs = minutes * 60_000
                val pick = Triple(apps, groups, sites)
                val focus = note
                scope.launch { LockManager.start(ctx, durationMs, pick.first, pick.second, pick.third, focus) }
            },
        )
    }
}

@Composable
private fun Stepper(unit: String, value: Long, range: IntRange, step: Int = 1, onChange: (Long) -> Unit) {
    val c = FL.colors
    Row(verticalAlignment = Alignment.CenterVertically) {
        TextButton(onClick = { onChange((value - step).coerceAtLeast(range.first.toLong())) }) {
            Text("−", color = c.pink, fontSize = 18.sp)
        }
        Text("$value$unit", fontFamily = Mono, fontWeight = FontWeight.Bold, color = c.ink, textAlign = TextAlign.Center, modifier = Modifier.width(36.dp))
        TextButton(onClick = { onChange((value + step).coerceAtMost(range.last.toLong())) }) {
            Text("+", color = c.pink, fontSize = 18.sp)
        }
    }
}

@Composable
private fun ConfirmLockDialog(summary: String, onCancel: () -> Unit, onConfirm: () -> Unit) {
    val c = FL.colors
    var typed by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onCancel,
        containerColor = c.surface,
        title = { Text("START THE LOCK?", fontFamily = Mono, fontWeight = FontWeight.Bold, color = c.pink) },
        text = {
            androidx.compose.foundation.layout.Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Body(summary, color = c.ink)
                OutlinedTextField(
                    value = typed, onValueChange = { typed = it }, singleLine = true,
                    label = { Text("Type LOCK to confirm") }, colors = fieldColors(),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = onConfirm, enabled = typed.trim() == "LOCK") {
                Text("LOCK IT", fontFamily = Mono, fontWeight = FontWeight.Bold, color = if (typed.trim() == "LOCK") c.pink else c.inkFaint)
            }
        },
        dismissButton = {
            TextButton(onClick = onCancel) { Text("CANCEL", fontFamily = Mono, color = c.inkDim) }
        },
    )
}
