package io.github.hackermanx.focuslock.ui

import android.net.VpnService
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalTextToolbar
import androidx.compose.ui.platform.TextToolbar
import androidx.compose.ui.platform.TextToolbarStatus
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.hackermanx.focuslock.block.DnsVpnService
import io.github.hackermanx.focuslock.block.GuardService
import io.github.hackermanx.focuslock.core.Blocklist
import io.github.hackermanx.focuslock.core.Clocks
import io.github.hackermanx.focuslock.core.EmergencySwitch
import io.github.hackermanx.focuslock.core.Format
import io.github.hackermanx.focuslock.data.ActiveLock
import io.github.hackermanx.focuslock.data.AppState
import io.github.hackermanx.focuslock.lock.AppCatalog
import io.github.hackermanx.focuslock.lock.LockManager
import io.github.hackermanx.focuslock.lock.Permissions
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.YearMonth

@Composable
fun ActiveLockScreen(st: AppState, lock: ActiveLock, now: Clocks) {
    val c = FL.colors
    val ctx = LocalContext.current
    val remaining = lock.timing.remaining(now)
    val endsAt = lock.timing.endsAtWall(now)
    val total = (endsAt - lock.startedAtWall).coerceAtLeast(1)

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Header("FOCUSLOCK ACTIVE", c.pink)
        Panel {
            Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
                Label("Unlocks")
                Text(Format.end(endsAt), color = c.ink, fontSize = 15.sp, modifier = Modifier.padding(top = 6.dp))
                Text(
                    Format.countdown(remaining), fontFamily = Mono, fontWeight = FontWeight.Bold,
                    fontSize = 34.sp, color = c.cyan, modifier = Modifier.padding(vertical = 8.dp),
                )
                LinearProgressIndicator(
                    progress = { 1f - remaining.toFloat() / total },
                    color = c.pink, trackColor = c.surface2, modifier = Modifier.fillMaxWidth(),
                )
            }
        }
        if (lock.note.isNotBlank()) {
            Panel("Your focus") { Text(lock.note, color = c.ink, fontSize = 16.sp) }
        }
        Panel("Blocked") {
            val appNames = remember(lock.apps) { lock.apps.map { AppCatalog.label(ctx, it) }.sorted() }
            val siteNames = lock.groups.map { Blocklist.label(it) } + lock.sites.sorted()
            if (appNames.isNotEmpty()) Body("Apps: " + appNames.joinToString(", "), color = c.ink)
            if (siteNames.isNotEmpty()) Body("Websites: " + siteNames.joinToString(", "), color = c.ink)
        }
        ProtectionPanel(st, now)
        if (LockManager.blocksYoutube(lock)) YoutubePanel(st, now)
        EmergencyPanel(st)
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun ProtectionPanel(st: AppState, now: Clocks) {
    val ctx = LocalContext.current
    val tick = now.wall / 3000 // re-check every few seconds, not every frame
    val guard = remember(tick) { GuardService.running && Permissions.accessibilityOn(ctx) }
    val admin = remember(tick) { Permissions.adminOn(ctx) }
    val needsVpn = LockManager.blockedDomains(st, now).isNotEmpty()
    val vpn = remember(tick) { DnsVpnService.running }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        DnsVpnService.start(ctx)
    }
    Panel("Protection") {
        StatusLine(guard, if (guard) "App blocking is on" else "App blocking is OFF: turn FocusLock on in Accessibility")
        if (needsVpn) StatusLine(vpn, if (vpn) "Website filter is on" else "Website filter is off")
        StatusLine(admin, if (admin) "Uninstall protection is on" else "Uninstall protection is off")
        if (needsVpn && !vpn) {
            GhostButton("Turn website filter on") {
                val ask = VpnService.prepare(ctx)
                if (ask != null) launcher.launch(ask) else DnsVpnService.start(ctx)
            }
        }
    }
}

@Composable
private fun YoutubePanel(st: AppState, now: Clocks) {
    val c = FL.colors
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var asking by remember { mutableStateOf(false) }
    val active = LockManager.ytBreakActive(st, now)
    Panel("YouTube break") {
        when {
            active -> {
                val brk = st.ytBreak!!
                Body("YouTube is open until ${Format.time(brk.endsAtWall(now))}. It blocks again by itself.")
                Text(Format.countdown(brk.remaining(now)), fontFamily = Mono, fontWeight = FontWeight.Bold, fontSize = 20.sp, color = c.yellow)
            }
            st.ytBreakDay == LocalDate.now().toString() -> Body("Today's hour is used up. You get another one tomorrow.")
            else -> {
                Body("One hour of YouTube, once a day. It blocks again automatically and can't be extended.")
                GhostButton("Start 1-hour break", color = c.yellow) { asking = true }
            }
        }
    }
    if (asking) {
        AlertDialog(
            onDismissRequest = { asking = false },
            containerColor = c.surface,
            title = { Text("OPEN YOUTUBE FOR AN HOUR?", fontFamily = Mono, fontWeight = FontWeight.Bold, color = c.yellow) },
            text = { Body("You get one break a day. The hour starts now, even if you close YouTube early.", color = c.ink) },
            confirmButton = {
                TextButton(onClick = {
                    asking = false
                    scope.launch { LockManager.startYoutubeBreak(ctx) }
                }) { Text("START", fontFamily = Mono, color = c.yellow) }
            },
            dismissButton = { TextButton(onClick = { asking = false }) { Text("CANCEL", fontFamily = Mono, color = c.inkDim) } },
        )
    }
}

/** No copy/paste menu on the emergency field: the sentence has to be typed. */
private object NoTextToolbar : TextToolbar {
    override val status = TextToolbarStatus.Hidden
    override fun hide() {}
    override fun showMenu(
        rect: Rect,
        onCopyRequested: (() -> Unit)?,
        onPasteRequested: (() -> Unit)?,
        onCutRequested: (() -> Unit)?,
        onSelectAllRequested: (() -> Unit)?,
    ) {}
}

@Composable
private fun EmergencyPanel(st: AppState) {
    val c = FL.colors
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var open by remember { mutableStateOf(false) }
    var typed by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val lastUsed = st.emergencyMonth?.let { runCatching { YearMonth.parse(it) }.getOrNull() }
    val next = EmergencySwitch.nextAvailable(lastUsed, LocalDate.now())

    Panel("Emergency switch", accent = if (open) c.pink else null) {
        when {
            next != null -> {
                Body("Already used this month.")
                GhostButton("Next available: ${Format.day(next)}", enabled = false) {}
            }
            !open -> {
                Body("Ends the lock right now. Usable once a month. It resets your streak and is saved in your history.")
                GhostButton("End lock early…", color = c.pink) { open = true }
            }
            else -> {
                Body("Type this sentence exactly. Pasting is turned off.")
                Text(EmergencySwitch.PHRASE, fontFamily = Mono, fontWeight = FontWeight.Bold, color = c.ink, fontSize = 15.sp)
                CompositionLocalProvider(LocalTextToolbar provides NoTextToolbar) {
                    OutlinedTextField(
                        value = typed,
                        onValueChange = { if (EmergencySwitch.acceptsEdit(typed, it)) typed = it },
                        keyboardOptions = KeyboardOptions(
                            capitalization = KeyboardCapitalization.None,
                            autoCorrectEnabled = false,
                            keyboardType = KeyboardType.Password,
                        ),
                        colors = fieldColors(),
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                val matches = EmergencySwitch.matches(typed)
                if (typed.isNotEmpty() && !EmergencySwitch.PHRASE.startsWith(typed)) {
                    Body("That doesn't match yet.", color = c.pink)
                }
                error?.let { Body(it, color = c.pink) }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    GhostButton("Cancel") {
                        open = false
                        typed = ""
                    }
                    PinkButton("End lock now", enabled = matches && !busy, modifier = Modifier.weight(1f)) {
                        busy = true
                        scope.launch {
                            error = when (LockManager.emergency(ctx, typed)) {
                                LockManager.EmergencyResult.ENDED -> null
                                LockManager.EmergencyResult.USED_THIS_MONTH -> "Already used this month."
                                LockManager.EmergencyResult.NO_LOCK -> "The lock has already ended."
                                LockManager.EmergencyResult.WRONG_PHRASE -> "The sentence doesn't match."
                            }
                            busy = false
                        }
                    }
                }
                Text(
                    "Your streak goes back to 0.", fontSize = 12.sp, color = c.inkFaint,
                    textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth(),
                )
            }
        }
    }
}
