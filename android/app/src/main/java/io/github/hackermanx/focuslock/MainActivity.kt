package io.github.hackermanx.focuslock

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.TabRowDefaults
import androidx.compose.material3.TabRowDefaults.tabIndicatorOffset
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import io.github.hackermanx.focuslock.core.Clocks
import io.github.hackermanx.focuslock.lock.LockManager
import io.github.hackermanx.focuslock.lock.clocksNow
import io.github.hackermanx.focuslock.ui.ActiveLockScreen
import io.github.hackermanx.focuslock.ui.FL
import io.github.hackermanx.focuslock.ui.FocusLockTheme
import io.github.hackermanx.focuslock.ui.LockScreen
import io.github.hackermanx.focuslock.ui.Mono
import io.github.hackermanx.focuslock.ui.OnboardingScreen
import io.github.hackermanx.focuslock.ui.SettingsScreen
import io.github.hackermanx.focuslock.ui.StatsScreen
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { FocusLockRoot() }
    }

    override fun onResume() {
        super.onResume()
        app.scope.launch { LockManager.tick(this@MainActivity) }
    }
}

/** Opens a system screen, ignoring phones that don't have it. */
fun Context.launchSafely(intent: Intent) {
    try {
        startActivity(if (this is Activity) intent else intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    } catch (_: ActivityNotFoundException) {
    } catch (_: SecurityException) {
    }
}

/** The clocks, re-read every second for countdowns. */
@Composable
fun rememberClocks(): Clocks {
    val ctx = LocalContext.current
    var now by remember { mutableStateOf(clocksNow(ctx)) }
    LaunchedEffect(Unit) {
        while (true) {
            delay(1000)
            now = clocksNow(ctx)
        }
    }
    return now
}

/** Matches the status-bar icons to the app's theme rather than the system's. */
@Composable
fun SystemBarIcons() {
    val view = LocalView.current
    val dark = FL.colors.isDark
    SideEffect {
        val window = (view.context as? Activity)?.window ?: return@SideEffect
        WindowCompat.getInsetsController(window, view).apply {
            isAppearanceLightStatusBars = !dark
            isAppearanceLightNavigationBars = !dark
        }
    }
}

@Composable
private fun FocusLockRoot() {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    val st by ctx.app.repo.state.collectAsStateWithLifecycle()
    var showSetup by rememberSaveable { mutableStateOf(false) }
    FocusLockTheme(st.theme) {
        SystemBarIcons()
        Box(Modifier.fillMaxSize().background(FL.colors.bg).windowInsetsPadding(WindowInsets.safeDrawing)) {
            if (!st.onboardingDone || showSetup) {
                OnboardingScreen(onDone = {
                    showSetup = false
                    scope.launch { ctx.app.repo.update { it.copy(onboardingDone = true) } }
                })
            } else {
                MainTabs(onSetup = { showSetup = true })
            }
        }
    }
}

@Composable
private fun MainTabs(onSetup: () -> Unit) {
    val ctx = LocalContext.current
    val st by ctx.app.repo.state.collectAsStateWithLifecycle()
    val now = rememberClocks()
    var tab by rememberSaveable { mutableIntStateOf(0) }
    val c = FL.colors
    val lock = LockManager.activeLock(st, now)
    Column(Modifier.fillMaxSize()) {
        TabRow(
            selectedTabIndex = tab,
            containerColor = c.bg,
            contentColor = c.ink,
            indicator = { positions ->
                TabRowDefaults.SecondaryIndicator(Modifier.tabIndicatorOffset(positions[tab]), color = c.pink)
            },
            divider = {},
        ) {
            listOf(if (lock != null) "LOCKED" else "LOCK", "STATS", "SETTINGS").forEachIndexed { i, label ->
                Tab(selected = tab == i, onClick = { tab = i }, text = {
                    Text(
                        label, fontFamily = Mono, fontWeight = FontWeight.Bold, fontSize = 13.sp,
                        color = if (tab == i) c.ink else c.inkFaint,
                    )
                })
            }
        }
        when (tab) {
            0 -> if (lock != null) ActiveLockScreen(st, lock, now) else LockScreen(st, now, onSetup)
            1 -> StatsScreen(st, now)
            else -> SettingsScreen(st, lockActive = lock != null, onSetup = onSetup)
        }
    }
}
