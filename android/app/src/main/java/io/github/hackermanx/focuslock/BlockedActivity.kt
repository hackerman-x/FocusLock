package io.github.hackermanx.focuslock

import android.content.Context
import android.content.Intent
import android.net.VpnService
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.addCallback
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import io.github.hackermanx.focuslock.block.DnsVpnService
import io.github.hackermanx.focuslock.core.Format
import io.github.hackermanx.focuslock.data.Attempt
import io.github.hackermanx.focuslock.lock.LockManager
import io.github.hackermanx.focuslock.ui.Body
import io.github.hackermanx.focuslock.ui.FL
import io.github.hackermanx.focuslock.ui.FocusLockTheme
import io.github.hackermanx.focuslock.ui.Header
import io.github.hackermanx.focuslock.ui.Mono
import io.github.hackermanx.focuslock.ui.Panel
import io.github.hackermanx.focuslock.ui.PinkButton

/** "X is blocked until …", shown over whatever was blocked. */
class BlockedActivity : ComponentActivity() {
    companion object {
        private const val EXTRA_KIND = "kind"
        private const val EXTRA_LABEL = "label"

        fun intent(ctx: Context, kind: String, label: String): Intent =
            Intent(ctx, BlockedActivity::class.java)
                .putExtra(EXTRA_KIND, kind)
                .putExtra(EXTRA_LABEL, label)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    }

    private var kind by mutableStateOf("")
    private var label by mutableStateOf("")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        read(intent)
        onBackPressedDispatcher.addCallback(this) { goHome() }
        setContent { BlockedScreen(kind, label, onHome = ::goHome, onClose = ::finish) }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        read(intent)
    }

    private fun read(intent: Intent) {
        kind = intent.getStringExtra(EXTRA_KIND).orEmpty()
        label = intent.getStringExtra(EXTRA_LABEL).orEmpty()
    }

    private fun goHome() {
        launchSafely(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        finish()
    }
}

@Composable
private fun BlockedScreen(kind: String, label: String, onHome: () -> Unit, onClose: () -> Unit) {
    val ctx = LocalContext.current
    val st by ctx.app.repo.state.collectAsStateWithLifecycle()
    val now = rememberClocks()
    val lock = LockManager.activeLock(st, now)
    val vpnLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        DnsVpnService.start(ctx)
        if (VpnService.prepare(ctx) == null) onClose()
    }
    FocusLockTheme(st.theme) {
        SystemBarIcons()
        val c = FL.colors
        Column(
            Modifier.fillMaxSize().background(c.bg).windowInsetsPadding(WindowInsets.safeDrawing).padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp, Alignment.CenterVertically),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            if (lock == null) {
                Header("UNLOCKED", c.cyan)
                Body("The lock has ended. Everything is unblocked.", color = c.ink)
                PinkButton("Back to home", onClick = onHome)
                return@Column
            }
            Header("BLOCKED", c.pink)
            val headline = when (kind) {
                Attempt.KIND_VPN -> "Website blocking was switched off"
                Attempt.KIND_SETTINGS -> "$label is closed during a lock"
                else -> "$label is blocked"
            }
            Text(headline, color = c.ink, fontSize = 22.sp, fontWeight = FontWeight.SemiBold, textAlign = TextAlign.Center)
            Body("until ${Format.end(lock.timing.endsAtWall(now))}", color = c.inkDim)
            Text(Format.countdown(lock.timing.remaining(now)), fontFamily = Mono, fontWeight = FontWeight.Bold, fontSize = 30.sp, color = c.cyan)
            if (lock.note.isNotBlank()) Panel("Your focus") { Text(lock.note, color = c.ink, fontSize = 16.sp) }
            if (kind == Attempt.KIND_VPN) {
                Body("FocusLock needs its website filter until the lock ends. Tap below and allow it.", color = c.inkDim)
                PinkButton("Turn it back on") {
                    val ask = VpnService.prepare(ctx)
                    if (ask != null) {
                        vpnLauncher.launch(ask)
                    } else {
                        DnsVpnService.start(ctx)
                        onClose()
                    }
                }
            } else {
                PinkButton("Back to home", onClick = onHome)
            }
        }
    }
}
