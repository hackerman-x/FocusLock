package io.github.hackermanx.focuslock.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily

/** The desktop app's "dark" and "light" palettes (focuslock-gui.py _THEMES). */
data class FocusColors(
    val bg: Color,
    val surface: Color,
    val surface2: Color,
    val border: Color,
    val borderStrong: Color,
    val ink: Color,
    val inkDim: Color,
    val inkFaint: Color,
    val pink: Color,
    val cyan: Color,
    val yellow: Color,
    val onPink: Color,
    val onCyan: Color,
    val isDark: Boolean,
)

val DarkColors = FocusColors(
    bg = Color(0xFF242424), surface = Color(0xFF2D2D2D), surface2 = Color(0xFF383838),
    border = Color(0xFF4A4A4A), borderStrong = Color(0xFF5C5C5C),
    ink = Color(0xFFF0F0F0), inkDim = Color(0xFFB0B0B0), inkFaint = Color(0xFF828282),
    pink = Color(0xFFFF2E9A), cyan = Color(0xFF00D0E8), yellow = Color(0xFFFFE156),
    onPink = Color(0xFF1A0512), onCyan = Color(0xFF031418), isDark = true,
)

val LightColors = FocusColors(
    bg = Color(0xFFF0F0F0), surface = Color(0xFFFFFFFF), surface2 = Color(0xFFE6E6E6),
    border = Color(0xFFCFCFCF), borderStrong = Color(0xFFB5B5B5),
    ink = Color(0xFF202020), inkDim = Color(0xFF555555), inkFaint = Color(0xFF828282),
    pink = Color(0xFFD81B78), cyan = Color(0xFF00838F), yellow = Color(0xFFA87900),
    onPink = Color(0xFFFFFFFF), onCyan = Color(0xFFFFFFFF), isDark = false,
)

val LocalFocusColors = staticCompositionLocalOf { DarkColors }

val Mono = FontFamily.Monospace

object FL {
    val colors: FocusColors
        @Composable get() = LocalFocusColors.current
}

@Composable
fun isDarkTheme(theme: String) = when (theme) {
    "dark" -> true
    "light" -> false
    else -> isSystemInDarkTheme()
}

@Composable
fun FocusLockTheme(theme: String, content: @Composable () -> Unit) {
    val c = if (isDarkTheme(theme)) DarkColors else LightColors
    val base = if (c.isDark) darkColorScheme() else lightColorScheme()
    val scheme = base.copy(
        primary = c.pink, onPrimary = c.onPink,
        secondary = c.cyan, onSecondary = c.onCyan,
        tertiary = c.yellow,
        background = c.bg, onBackground = c.ink,
        surface = c.surface, onSurface = c.ink,
        surfaceVariant = c.surface2, onSurfaceVariant = c.inkDim,
        surfaceContainer = c.surface, surfaceContainerHigh = c.surface2, surfaceContainerHighest = c.surface2,
        outline = c.border, outlineVariant = c.border,
        error = c.pink,
    )
    MaterialTheme(colorScheme = scheme) {
        CompositionLocalProvider(LocalFocusColors provides c, content = content)
    }
}
