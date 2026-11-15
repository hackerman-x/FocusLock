package io.github.hackermanx.focuslock.core

import io.github.hackermanx.focuslock.core.AppScan.CATEGORY_AUDIO
import io.github.hackermanx.focuslock.core.AppScan.CATEGORY_GAME
import io.github.hackermanx.focuslock.core.AppScan.CATEGORY_IMAGE
import io.github.hackermanx.focuslock.core.AppScan.CATEGORY_SOCIAL
import io.github.hackermanx.focuslock.core.AppScan.CATEGORY_UNDEFINED
import io.github.hackermanx.focuslock.core.AppScan.CATEGORY_VIDEO
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Test

class AppScanTest {
    private val me = "io.github.hackermanx.focuslock"

    private fun reason(pkg: String, label: String, category: Int = CATEGORY_UNDEFINED, isSystem: Boolean = false) =
        AppScan.classify(ScanCandidate(pkg, label, category, isSystem), me)?.reason

    @Test
    fun defaultsAreOnlyYoutubeAndInstagram() {
        assertEquals(listOf("com.google.android.youtube", "com.instagram.android"), Blocklist.SUGGESTED_PACKAGES)
    }

    @Test
    fun knownAppsAreSuggestedEvenUntaggedOrPreinstalled() {
        assertEquals("A well-known social app", reason("com.zhiliaoapp.musically", "TikTok"))
        assertEquals("A well-known game", reason("com.roblox.client", "Roblox"))
        assertEquals("A well-known video app", reason("com.netflix.mediaclient", "Netflix", isSystem = true))
        assertEquals("A well-known music app", reason("com.spotify.music", "Spotify"))
        assertEquals("A well-known chat app", reason("com.discord", "Discord"))
    }

    @Test
    fun knownListIsExactlyTheChosenOne() {
        val chosen = setOf(
            "com.google.android.youtube", "com.netflix.mediaclient", "com.amazon.avod.thirdpartyclient",
            "in.startv.hotstar", "com.disney.disneyplus", "tv.twitch.android.app",
            "com.instagram.android", "com.zhiliaoapp.musically", "com.ss.android.ugc.trill", "com.snapchat.android",
            "com.facebook.katana", "com.twitter.android", "com.reddit.frontdoor", "com.pinterest",
            "com.instagram.barcelona",
            "com.discord",
            "com.spotify.music", "com.google.android.apps.youtube.music",
            "com.roblox.client", "com.mojang.minecraftpe", "com.dts.freefireth", "com.dts.freefiremax",
            "com.pubg.imobile", "com.tencent.ig", "com.activision.callofduty.shooter", "com.supercell.clashofclans",
            "com.supercell.clashroyale", "com.supercell.brawlstars", "com.kiloo.subwaysurf",
            "com.king.candycrushsaga", "com.miHoYo.GenshinImpact", "com.innersloth.spacemafia",
            "com.valvesoftware.android.steam.community",
        )
        assertEquals(chosen, AppScan.KNOWN.keys)
    }

    @Test
    fun messagingAppsOnlyWhenTaggedSocialWithASofterReason() {
        assertNull(reason("com.whatsapp", "WhatsApp"))
        assertNull(reason("org.telegram.messenger", "Telegram", CATEGORY_VIDEO))
        assertEquals("Messaging app, only if it distracts you", reason("com.whatsapp", "WhatsApp", CATEGORY_SOCIAL))
        assertEquals("Messaging app, only if it distracts you", reason("org.telegram.messenger", "Telegram", CATEGORY_SOCIAL))
    }

    @Test
    fun categoriesGiveTheReason() {
        assertEquals("Tagged as a game", reason("com.example.racer", "Turbo Racer", CATEGORY_GAME))
        assertEquals("Tagged as a video app", reason("com.example.tv", "StreamBox", CATEGORY_VIDEO))
        assertEquals("Tagged as a social app", reason("com.example.chirp", "Chirp", CATEGORY_SOCIAL))
        assertEquals("Tagged as a music or audio app", reason("com.example.tunes", "Tunes", CATEGORY_AUDIO))
        assertEquals("Tagged as a photo app", reason("com.example.snapfeed", "SnapFeed", CATEGORY_IMAGE))
    }

    @Test
    fun photoToolsAndOtherCategoriesAreNotSuggested() {
        assertNull(reason("com.example.photoeditor", "Photo Editor Pro", CATEGORY_IMAGE))
        assertNull(reason("com.example.docscan", "Doc Scanner", CATEGORY_IMAGE))
        assertNull(reason("com.example.notes", "Notes", 7)) // productivity
        assertNull(reason("com.example.news", "Daily News", 5))
        assertNull(reason("com.example.untagged", "Something", CATEGORY_UNDEFINED))
    }

    @Test
    fun preinstalledAppsNeedToBeWellKnown() {
        assertNull(reason("com.vendor.music", "Music", CATEGORY_AUDIO, isSystem = true))
        assertNull(reason("com.vendor.videoplayer", "Videos", CATEGORY_VIDEO, isSystem = true))
    }

    @Test
    fun essentialsAreNeverSuggested() {
        assertNull(reason("com.google.android.dialer", "Phone", CATEGORY_SOCIAL))
        assertNull(reason("com.google.android.apps.messaging", "Messages", CATEGORY_SOCIAL))
        assertNull(reason("com.android.settings", "Settings"))
        assertNull(reason("com.google.android.apps.maps", "Maps", CATEGORY_VIDEO))
        assertNull(reason("com.android.camera2", "Camera", CATEGORY_IMAGE))
        assertNull(reason("com.google.android.inputmethod.latin", "Gboard"))
        assertNull(reason("com.google.android.apps.nexuslauncher", "Pixel Launcher", CATEGORY_GAME))
        assertNull(reason("com.google.android.apps.photos", "Photos", CATEGORY_IMAGE))
        assertNull(reason("com.example.anything", "Camera", CATEGORY_GAME))
        assertNull(reason(me, "FocusLock", CATEGORY_GAME))
    }

    @Test
    fun noKnownAppLooksLikeAnEssential() {
        AppScan.KNOWN.keys.forEach { assertFalse(it, AppScan.isEssential(it, "")) }
    }

    @Test
    fun ignoredAndListedAppsAreLeftOut() {
        val apps = listOf(
            ScanCandidate("com.roblox.client", "Roblox", CATEGORY_GAME, false),
            ScanCandidate("com.discord", "Discord", CATEGORY_SOCIAL, false),
            ScanCandidate("com.google.android.youtube", "YouTube", CATEGORY_VIDEO, true),
            ScanCandidate("com.example.chess", "Chess", CATEGORY_GAME, false),
            ScanCandidate("com.example.chess", "Chess", CATEGORY_GAME, false),
        )
        val found = AppScan.suggestions(
            apps, me,
            ignored = setOf("com.discord"),
            listed = Blocklist.SUGGESTED_PACKAGES.toSet(),
        )
        assertEquals(listOf("Chess", "Roblox"), found.map { it.label })
    }

    @Test
    fun onlyUnseenSuggestionsAreNew() {
        val found = listOf(Suggestion("a", "A", "x"), Suggestion("b", "B", "x"))
        assertEquals(setOf("b"), AppScan.newSince(found, seen = setOf("a")))
        assertEquals(emptySet<String>(), AppScan.newSince(found, seen = setOf("a", "b")))
    }
}
