package io.github.hackermanx.focuslock.core

/** One launchable app, as the scan sees it. */
data class ScanCandidate(
    val pkg: String,
    val label: String,
    /** ApplicationInfo.category, or [AppScan.CATEGORY_UNDEFINED]. */
    val category: Int,
    /** Preinstalled with the phone (ApplicationInfo.FLAG_SYSTEM). */
    val isSystem: Boolean,
)

data class Suggestion(val pkg: String, val label: String, val reason: String)

/**
 * The app scan: which installed apps look like entertainment. Read-only, like
 * focuslock_scan.py on the desktop: it only suggests, and nothing is blocked
 * until the user taps Add.
 */
object AppScan {
    // ApplicationInfo.CATEGORY_* values, copied so this stays testable without Android.
    const val CATEGORY_UNDEFINED = -1
    const val CATEGORY_GAME = 0
    const val CATEGORY_AUDIO = 1
    const val CATEGORY_VIDEO = 2
    const val CATEGORY_IMAGE = 3
    const val CATEGORY_SOCIAL = 4

    private const val GAME = "game"
    private const val SOCIAL = "social app"
    private const val VIDEO = "video app"
    private const val MUSIC = "music app"

    /** Well-known distractions, whether or not they tag their category. */
    val KNOWN: Map<String, String> = buildMap {
        listOf(
            "com.zhiliaoapp.musically", "com.ss.android.ugc.trill", // TikTok
            "com.snapchat.android", "com.reddit.frontdoor", "com.twitter.android", "com.facebook.katana",
            "com.facebook.lite", "com.discord", "com.pinterest", "com.tumblr", "com.instagram.barcelona",
            "com.instagram.android", "com.bereal.ft",
        ).forEach { put(it, SOCIAL) }
        listOf(
            "com.google.android.youtube", "com.google.android.apps.youtube.kids", "app.revanced.android.youtube",
            "org.schabi.newpipe", "com.netflix.mediaclient", "tv.twitch.android.app",
            "com.amazon.avod.thirdpartyclient", "com.disney.disneyplus", "in.startv.hotstar",
            "com.jio.media.ondemand", "com.wbd.stream", "com.hulu.plus", "com.crunchyroll.crunchyroid",
        ).forEach { put(it, VIDEO) }
        listOf(
            "com.spotify.music", "com.google.android.apps.youtube.music", "com.soundcloud.android",
            "com.jio.media.jiobeats",
        ).forEach { put(it, MUSIC) }
        listOf(
            "com.roblox.client", "com.mojang.minecraftpe", "com.valvesoftware.android.steam.community",
            "com.supercell.clashofclans", "com.supercell.clashroyale", "com.supercell.brawlstars",
            "com.kiloo.subwaysurf", "com.dts.freefireth", "com.dts.freefiremax", "com.tencent.ig",
            "com.pubg.imobile", "com.activision.callofduty.shooter", "com.miHoYo.GenshinImpact",
            "com.king.candycrushsaga", "com.innersloth.spacemafia", "com.epicgames.fortnite",
        ).forEach { put(it, GAME) }
    }

    /** Parts of a package name that mark a phone essential, never suggested. */
    private val ESSENTIAL_PARTS = listOf(
        "dialer", "phone", "telecom", "contacts", "mms", "sms", "messaging", "settings", "maps", "waze",
        "camera", "inputmethod", "keyboard", "honeyboard", "launcher", "clock", "calculator", "calendar",
        "documentsui", "filemanager", "myfiles", "gallery", "photos",
    )
    private val ESSENTIAL_LABELS = setOf(
        "phone", "messages", "settings", "maps", "camera", "keyboard", "contacts", "clock", "calculator",
        "calendar", "files", "gallery", "photos",
    )

    /** Photo-tagged apps that are tools, not feeds. */
    private val IMAGE_TOOLS = listOf("edit", "scan", "lens", "pdf", "document")

    fun isEssential(pkg: String, label: String): Boolean {
        val parts = pkg.lowercase().split('.')
        return parts.any { part -> ESSENTIAL_PARTS.any { it in part } } || label.trim().lowercase() in ESSENTIAL_LABELS
    }

    /** A suggestion with its reason, or null if the app shouldn't be suggested. */
    fun classify(app: ScanCandidate, ownPackage: String): Suggestion? {
        if (app.pkg == ownPackage || isEssential(app.pkg, app.label)) return null
        KNOWN[app.pkg]?.let { kind ->
            return Suggestion(app.pkg, app.label, if (kind == GAME) "A well-known game" else "A well-known $kind")
        }
        if (app.isSystem) return null
        val reason = when (app.category) {
            CATEGORY_GAME -> "Tagged as a game"
            CATEGORY_VIDEO -> "Tagged as a video app"
            CATEGORY_SOCIAL -> "Tagged as a social app"
            CATEGORY_AUDIO -> "Tagged as a music or audio app"
            CATEGORY_IMAGE -> {
                val text = (app.pkg + " " + app.label).lowercase()
                if (IMAGE_TOOLS.any { it in text }) return null
                "Tagged as a photo app"
            }
            else -> return null
        }
        return Suggestion(app.pkg, app.label, reason)
    }

    /**
     * Suggestions from a scan, leaving out ignored apps and apps already in the
     * Apps list ([listed]), sorted by name.
     */
    fun suggestions(apps: List<ScanCandidate>, ownPackage: String, ignored: Set<String>, listed: Set<String>): List<Suggestion> =
        apps.asSequence()
            .filter { it.pkg !in ignored && it.pkg !in listed }
            .mapNotNull { classify(it, ownPackage) }
            .distinctBy { it.pkg }
            .sortedBy { it.label.lowercase() }
            .toList()

    /** The suggestions not shown before, to mark as new. */
    fun newSince(suggestions: List<Suggestion>, seen: Set<String>): Set<String> =
        suggestions.map { it.pkg }.filter { it !in seen }.toSet()
}
