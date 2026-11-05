package io.github.hackermanx.focuslock.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ScreenRulesTest {
    private val settings = "com.android.settings"
    private fun screen(vararg texts: String, pkg: String = settings) = ScreenRules.protectedScreen(pkg, texts.toList(), "FocusLock")

    @Test
    fun closesFocusLocksOwnPages() {
        assertEquals("App info", screen("App info", "FocusLock", "Uninstall", "Force stop", "Notifications"))
        assertEquals("Device admin apps", screen("Device admin apps", "FocusLock", "Find My Device"))
        assertEquals("Accessibility", screen("Accessibility", "Downloaded apps", "FocusLock", "On"))
        assertEquals("Accessibility", screen("FocusLock", "Use FocusLock", "FocusLock shortcut"))
        assertEquals("VPN settings", screen("VPN", "FocusLock", "Connected"))
        assertEquals("VPN settings", screen("FocusLock", "Disconnect", "Cancel"))
        assertEquals("Uninstall", screen("Do you want to uninstall FocusLock?", pkg = "com.google.android.packageinstaller"))
    }

    @Test
    fun closesClockAndDnsSettingsForEveryone() {
        assertEquals("Date & time", screen("Date & time", "Set time automatically", "Time zone"))
        assertEquals("Private DNS", screen("Private DNS", "Off", "Automatic", "Private DNS provider hostname"))
        assertEquals("VPN settings", screen("Some VPN", "Always-on VPN", "Block connections without VPN"))
    }

    @Test
    fun leavesOrdinaryScreensOpen() {
        assertNull(screen("Settings", "Network & internet", "Accessibility", "Security"))
        assertNull(screen("Network & internet", "Internet", "VPN", "FocusLock", "Private DNS", "Automatic"))
        assertNull(screen("App info", "Instagram", "Uninstall", "Force stop"))
        assertNull(screen("Do you want to uninstall Instagram?", pkg = "com.google.android.packageinstaller"))
        assertNull(screen("FocusLock", "Uninstall", pkg = "com.android.chrome"))
    }
}
