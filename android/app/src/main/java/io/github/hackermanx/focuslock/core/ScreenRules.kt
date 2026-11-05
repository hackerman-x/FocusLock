package io.github.hackermanx.focuslock.core

/**
 * Strict mode: which Settings screens the accessibility service closes during
 * a lock, judged from the text on screen. Matching is on English text.
 */
object ScreenRules {
    private val DATE_TIME = listOf(
        "set time automatically", "automatic date & time", "automatic date and time",
        "set time zone automatically", "use network-provided time", "use location to set time zone",
    )
    private val PRIVATE_DNS = listOf(
        "private dns provider hostname", "hostname of dns provider", "private dns mode",
    )
    private val VPN_DETAIL = listOf("always-on vpn", "block connections without vpn")
    private val APP_INFO = listOf("force stop", "uninstall", "clear storage", "clear data", "allow restricted settings")
    private val ADMIN = listOf("device admin", "device administrator", "phone admin")
    private val ACCESSIBILITY = listOf("downloaded apps", "installed apps", "installed services", "accessibility")

    /** Packages whose screens are checked. */
    fun watches(pkg: String) =
        pkg == "com.android.settings" || "settings" in pkg || pkg.endsWith("packageinstaller") ||
            pkg == "com.miui.securitycenter"

    /** A name for the protected screen showing, or null if it may stay open. */
    fun protectedScreen(pkg: String, texts: List<String>, appName: String): String? {
        if (!watches(pkg)) return null
        val lower = texts.map { it.lowercase() }
        val joined = lower.joinToString("\n")
        val name = appName.lowercase()
        val mentionsUs = name in joined
        if (pkg.endsWith("packageinstaller")) return if (mentionsUs) "Uninstall" else null
        if (DATE_TIME.any { it in joined }) return "Date & time"
        if (PRIVATE_DNS.any { it in joined }) return "Private DNS"
        if (VPN_DETAIL.any { it in joined }) return "VPN settings"
        if (!mentionsUs) return null
        if (APP_INFO.any { it in joined }) return "App info"
        if (ADMIN.any { it in joined }) return "Device admin apps"
        if ("use $name" in joined || "$name shortcut" in joined || ACCESSIBILITY.any { it in joined }) {
            return "Accessibility"
        }
        // The VPN list ("VPN" heading, FocusLock in it) and its disconnect dialog,
        // but not Network & internet, which also has a "VPN" row next to Private DNS.
        if ("disconnect" in joined || (lower.any { it.trim() == "vpn" } && "private dns" !in joined)) {
            return "VPN settings"
        }
        return null
    }
}
