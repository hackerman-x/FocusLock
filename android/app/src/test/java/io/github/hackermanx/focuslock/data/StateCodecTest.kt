package io.github.hackermanx.focuslock.data

import androidx.datastore.preferences.core.emptyPreferences
import androidx.datastore.preferences.core.mutablePreferencesOf
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class StateCodecTest {
    private fun roundTrip(state: AppState): AppState {
        val prefs = mutablePreferencesOf()
        prefs.write(state)
        return prefs.toAppState()
    }

    @Test
    fun consentIsUnaskedUntilAnswered() {
        assertNull(emptyPreferences().toAppState().scanConsent)
        assertNull(roundTrip(AppState()).scanConsent)
    }

    @Test
    fun consentAnswersAreKept() {
        assertEquals(true, roundTrip(AppState(scanConsent = true)).scanConsent)
        assertEquals(false, roundTrip(AppState(scanConsent = false)).scanConsent)
    }

    @Test
    fun ignoredSeenAndAddedAppsAreKept() {
        val state = AppState(
            scanConsent = true,
            scanIgnored = setOf("com.discord", "com.spotify.music"),
            scanSeen = setOf("com.discord", "com.spotify.music", "com.roblox.client"),
            addedApps = setOf("com.roblox.client"),
        )
        val back = roundTrip(state)
        assertEquals(state.scanIgnored, back.scanIgnored)
        assertEquals(state.scanSeen, back.scanSeen)
        assertEquals(state.addedApps, back.addedApps)
    }

    @Test
    fun otherSettingsSurviveAScanUpdate() {
        val before = roundTrip(AppState(theme = "dark", onboardingDone = true, customSites = listOf("reddit.com")))
        val after = roundTrip(before.copy(scanIgnored = before.scanIgnored + "com.discord"))
        assertEquals("dark", after.theme)
        assertEquals(true, after.onboardingDone)
        assertEquals(listOf("reddit.com"), after.customSites)
        assertEquals(setOf("com.discord"), after.scanIgnored)
    }
}
