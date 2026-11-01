package io.github.hackermanx.focuslock.core

object Blocklist {
    const val YOUTUBE = "youtube"

    /** Same groups as DOMAIN_GROUPS in focuslock_core.py. Subdomains are blocked too. */
    val DOMAIN_GROUPS: Map<String, List<String>> = linkedMapOf(
        "discord_web" to listOf("discord.com", "www.discord.com", "discordapp.com"),
        "crazygames" to listOf("crazygames.com", "www.crazygames.com"),
        "gxgames" to listOf("gx.games", "www.gx.games"),
        "poki" to listOf("poki.com", "www.poki.com"),
        "roblox" to listOf("roblox.com", "www.roblox.com", "web.roblox.com"),
        "instagram" to listOf("instagram.com", "www.instagram.com"),
        "youtube" to listOf("youtube.com", "www.youtube.com", "m.youtube.com"),
    )

    /** Labels from DOMAINS in focuslock_core.py. */
    val GROUP_LABELS: Map<String, String> = mapOf(
        "discord_web" to "Discord (web)",
        "crazygames" to "CrazyGames",
        "gxgames" to "GX Games",
        "poki" to "Poki",
        "roblox" to "Roblox (web)",
        "instagram" to "Instagram (web)",
        "youtube" to "YouTube",
    )

    val YOUTUBE_PACKAGES = setOf("com.google.android.youtube")

    /** Apps shown first in the app picker, when they're installed. */
    val SUGGESTED_PACKAGES = listOf(
        "com.instagram.android",
        "com.google.android.youtube",
        "com.zhiliaoapp.musically",
        "com.ss.android.ugc.trill",
        "com.discord",
        "com.roblox.client",
        "com.mojang.minecraftpe",
        "com.snapchat.android",
        "com.reddit.frontdoor",
        "com.twitter.android",
        "com.facebook.katana",
        "com.valvesoftware.android.steam.community",
    )

    /** Address-bar view ids in the browsers the accessibility service reads. */
    val BROWSER_URL_BARS: Map<String, List<String>> = mapOf(
        "com.android.chrome" to listOf("com.android.chrome:id/url_bar"),
        "org.mozilla.firefox" to listOf(
            "org.mozilla.firefox:id/mozac_browser_toolbar_url_view",
            "org.mozilla.firefox:id/url_bar_title",
        ),
        "com.sec.android.app.sbrowser" to listOf(
            "com.sec.android.app.sbrowser:id/location_bar_edit_text",
            "com.sec.android.app.sbrowser:id/custom_tab_toolbar_url_bar_text",
        ),
    )

    fun label(group: String) = GROUP_LABELS[group] ?: group

    fun domainsFor(groups: Set<String>, customSites: Set<String>): Set<String> =
        groups.flatMap { DOMAIN_GROUPS[it].orEmpty() }.toSet() + customSites

    /** Whether [host] is one of [domains] or a subdomain of one. */
    fun isBlocked(host: String, domains: Set<String>): Boolean {
        var h = host.lowercase().trimEnd('.')
        while (true) {
            if (h in domains) return true
            val dot = h.indexOf('.')
            if (dot < 0) return false
            h = h.substring(dot + 1)
        }
    }

    /**
     * The host in an address-bar text such as "instagram.com/explore" or
     * "https://www.youtube.com/watch?v=x", or null when it's a search or unfinished.
     */
    fun hostFromUrl(text: String): String? {
        var s = text.trim().lowercase()
        if (s.isEmpty() || s.any { it.isWhitespace() }) return null
        val scheme = s.indexOf("://")
        if (scheme >= 0) s = s.substring(scheme + 3)
        s = s.substringBefore('/').substringBefore('?').substringBefore('#')
        s = s.substringAfterLast('@').substringBefore(':').trimEnd('.')
        if ('.' !in s || s.startsWith('.')) return null
        if (!s.all { it in 'a'..'z' || it in '0'..'9' || it == '.' || it == '-' }) return null
        return s
    }

    /** A user-typed site ("https://www.Reddit.com/r/x") as a domain ("reddit.com"), or null if it isn't one. */
    fun normalizeSite(input: String): String? = hostFromUrl(input)?.removePrefix("www.")
}
