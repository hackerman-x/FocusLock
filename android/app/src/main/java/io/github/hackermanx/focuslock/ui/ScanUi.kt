package io.github.hackermanx.focuslock.ui

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import io.github.hackermanx.focuslock.data.AppState
import io.github.hackermanx.focuslock.lock.ScanResult
import io.github.hackermanx.focuslock.lock.Scanner
import kotlinx.coroutines.launch

private fun announce(ctx: android.content.Context, result: ScanResult?) {
    val new = result?.suggestions?.filter { it.pkg in result.new }.orEmpty()
    if (new.isEmpty()) return
    val names = new.take(3).joinToString(", ") { it.label } + if (new.size > 3) " and more" else ""
    Toast.makeText(ctx, "Found ${new.size} app(s) that look like distractions ($names). See Lock → Apps.", Toast.LENGTH_LONG).show()
}

/**
 * Asks "Find distractions for you?" the first time the app opens, and scans on
 * every start once allowed (like the desktop app's _scan_on_startup).
 */
@Composable
fun ScanOnStart(st: AppState) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var scannedThisLaunch by rememberSaveable { mutableStateOf(false) }
    LaunchedEffect(st.scanConsent) {
        if (st.scanConsent == true && !scannedThisLaunch) {
            scannedThisLaunch = true
            announce(ctx, Scanner.scan(ctx))
        }
    }
    if (st.scanConsent != null) return
    val c = FL.colors
    AlertDialog(
        onDismissRequest = {}, // needs an answer
        containerColor = c.surface,
        title = { Text("FIND DISTRACTIONS FOR YOU?", fontFamily = Mono, fontWeight = FontWeight.Bold, color = c.yellow) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Body("FocusLock can look through the apps on this phone and suggest games, video, social and music apps to block.", color = c.ink)
                Column(
                    Modifier.fillMaxWidth().background(c.surface2, RoundedCornerShape(10.dp)).padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Label("It would read", color = c.cyan)
                    Body("•  The list of apps in your app drawer")
                    Body("•  Each app's category (game, video, social…)")
                }
                Body("It only reads the list of installed apps. Nothing leaves your phone, and nothing is blocked unless you tap Add.")
            }
        },
        confirmButton = {
            TextButton(onClick = {
                scannedThisLaunch = true
                scope.launch { announce(ctx, Scanner.setConsent(ctx, true)) }
            }) { Text("ALLOW SCAN", fontFamily = Mono, fontWeight = FontWeight.Bold, color = c.pink) }
        },
        dismissButton = {
            TextButton(onClick = { scope.launch { Scanner.setConsent(ctx, false) } }) {
                Text("NOT NOW", fontFamily = Mono, color = c.inkDim)
            }
        },
    )
}

/** The scan's suggestions in the Apps panel, each with Add and Ignore. */
@Composable
fun ScanSuggestions(st: AppState, onAdd: (String) -> Unit) {
    val ctx = LocalContext.current
    val c = FL.colors
    val scope = rememberCoroutineScope()
    val result by Scanner.result.collectAsStateWithLifecycle()
    val running by Scanner.running.collectAsStateWithLifecycle()
    val scan = { scope.launch { if (st.scanConsent == true) Scanner.scan(ctx) else Scanner.setConsent(ctx, true) } }
    val shown = result?.suggestions.orEmpty()

    Label(if (shown.isEmpty()) "Suggested by scan" else "Suggested by scan (${shown.size})", color = c.cyan)
    when {
        running -> Body("Looking through your apps…")
        result == null -> {
            Body("Scan your apps to find games, video, social and music apps to add. It only reads the app list.")
            GhostButton("Scan now") { scan() }
        }
        else -> {
            if (shown.isEmpty()) Body("No new suggestions.")
            shown.forEach { s ->
                Column(Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(s.label, fontSize = 15.sp, color = c.ink)
                        if (s.pkg in result!!.new) {
                            Spacer(Modifier.width(8.dp))
                            Text(
                                "NEW", fontFamily = Mono, fontSize = 10.sp, fontWeight = FontWeight.Bold, color = c.onPink,
                                modifier = Modifier.background(c.pink, RoundedCornerShape(4.dp)).padding(horizontal = 5.dp, vertical = 1.dp),
                            )
                        }
                    }
                    Text(s.reason, fontSize = 12.sp, color = c.inkFaint)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 4.dp)) {
                        GhostButton("Add", color = c.pink) {
                            onAdd(s.pkg)
                            scope.launch { Scanner.add(ctx, s.pkg) }
                        }
                        GhostButton("Ignore") { scope.launch { Scanner.ignore(ctx, s.pkg) } }
                    }
                }
            }
            GhostButton("Rescan") { scan() }
        }
    }
}
