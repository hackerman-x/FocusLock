# FocusLock for Android

Lock away distracting apps and websites on your phone for a set time. It looks
and works like the desktop app, with one difference: the phone has an
**emergency switch** you can use once a month (see below).

The phone and your computers don't sync. Each device has its own locks and stats.

## Install

Get `FocusLock.apk` from the
[Releases](https://github.com/hackerman-x/FocusLock/releases) page (the newest
one is always at
<https://github.com/hackerman-x/FocusLock/releases/latest/download/FocusLock.apk>),
or the debug APK from the latest run of the **Android** workflow (Actions tab,
`focuslock-debug-apk`).

**On the phone:** open the APK and allow installs from your browser or file
manager when Android asks.

**From a computer over USB** (turn on *Developer options → USB debugging* first):

```bash
adb install -r FocusLock.apk
```

Needs Android 8.0 or newer.

## Set up (permissions)

The first time you open it, FocusLock walks you through these:

| Permission | Why |
|---|---|
| **Notifications** | Shows that a lock is on, and tells you when it ends. |
| **Accessibility** | Blocks apps: it sees which app is in front and sends blocked ones back to the home screen. It also reads the address bar in Chrome, Firefox and Samsung Internet, and closes FocusLock's own settings during a lock. |
| **Device admin** ("Uninstall protection") | While FocusLock is a device admin, Android won't uninstall it. It asks for no other admin powers. |
| **VPN** ("Website filter") | Blocks websites (see below). |
| **Battery: unrestricted** (recommended) | Stops Android putting FocusLock to sleep in the background. |

Accessibility and device admin are required before you can start a lock.

### "Restricted setting" on Android 13 and newer

Android greys out the Accessibility switch for apps installed from an APK
instead of the Play Store. To allow it:

1. Open **Settings → Accessibility**, find FocusLock (it may be under
   *Downloaded apps*) and try to turn it on. Android says *Restricted setting*.
   Close that message.
2. Open **Settings → Apps → FocusLock** (the *App info* button in FocusLock's
   setup does this), tap **⋮** in the top-right corner, then **Allow restricted
   settings**, and confirm with your PIN or fingerprint.
3. Go back to **Accessibility → FocusLock** and turn it on.

## Using it

- **Lock tab:** pick how long (presets or days/hours/minutes), the apps, the
  websites, and an optional focus note, then type `LOCK` to confirm.
  FocusLock, the home screen, the phone app and Settings can't be blocked.
- **During a lock:** the Lock tab shows the countdown, what's blocked, whether
  each kind of protection is on, the YouTube break and the emergency switch.
  Opening a blocked app or site sends you home and shows *"… is blocked until …"*.
  Every attempt is counted.
- **YouTube break:** if the lock blocks YouTube, you can open it for one hour,
  once per calendar day. It blocks again by itself.
- **Stats tab:** current and best streak, number of locks, total focus time,
  blocked attempts (today, all time, and which apps/sites/screens), and history.
- **Settings tab:** theme, your own websites, permissions, and *Allow uninstall*.

### Streaks
The same rules as the desktop app: the streak goes up by one each calendar day
you start a lock, as long as no more than one day has passed since your
previous lock ended.

## Strict mode

While a lock runs, FocusLock makes itself hard to switch off:

- **Uninstalling is blocked** (device admin). Outside a lock, use
  *Settings tab → Allow uninstall*, then uninstall as usual.
- **These screens close as soon as they open:** FocusLock's *App info* page
  (uninstall, force stop, clear storage), *Device admin apps*, FocusLock in
  *Accessibility*, *VPN* settings, *Private DNS* and *Date & time*.
- **If the VPN is turned off** (or another VPN app takes over), FocusLock shows
  its blocked screen straight away and asks to turn the filter back on, and it
  keeps asking while you use the phone.
- **Changing the clock doesn't help.** The lock counts down on the phone's
  internal clock (time since boot), which can't be changed. After a reboot it
  goes by the end time, and FocusLock starts again by itself.

### The emergency switch

On the Lock tab during a lock, type this sentence exactly (pasting is turned off):

> I am choosing to end my focus lock early.

The lock ends at once. You can use it **once per calendar month**. After that
the button shows *Next available: 1 Dec* (the first of next month). Using it
**resets your streak to 0** and adds an *Emergency* entry to your history.

### Limits

FocusLock is a commitment tool, not parental control. Someone determined can get round it:

- **Safe mode** (hold power, then long-press *Power off*) starts Android
  without any downloaded apps, so nothing is blocked until you restart.
- A computer with **ADB** can change settings directly. Uninstalling over ADB
  is still refused while FocusLock is a device admin.
- Screen detection reads Settings text in **English**. With the phone in
  another language, the website and app blocking still work, but the protected
  Settings screens may not close.
- The website filter works through DNS. Browsers with their own *secure DNS*
  (DNS over HTTPS) skip it. The address-bar check covers Chrome, Firefox and
  Samsung Internet; other browsers aren't covered.
- Sites you open just before a lock may stay reachable for a minute while
  the phone's DNS cache expires.

## How it works

| Part | File |
|---|---|
| App blocking, address bars, strict mode | `block/GuardService.kt` (an `AccessibilityService`) |
| Website filter | `block/DnsVpnService.kt`: a `VpnService` that routes only a made-up DNS server address (`10.111.222.2`) into the tunnel. Blocked names (and their subdomains) get `0.0.0.0` / `::`; everything else is forwarded to your normal DNS server through a socket that bypasses the VPN. No other traffic goes through it. |
| DNS packets | `core/DnsPacket.kt` |
| Website groups | `core/Blocklist.kt`, copied from `DOMAIN_GROUPS` in `focuslock_core.py` |
| Lock timing | `core/LockTiming.kt`: active while now is before the end, counted on `elapsedRealtime` within a boot |
| Starting and ending locks, YouTube break, emergency switch | `lock/LockManager.kt`, `core/EmergencySwitch.kt`, `core/Streak.kt` |
| Reboots, clock changes, end-of-lock alarm | `lock/Receivers.kt` |
| Settings, lock state, stats | DataStore (`data/Repo.kt`) |
| History and blocked attempts | Room (`data/HistoryDb.kt`) |
| Screens | `ui/` (Jetpack Compose), plus `BlockedActivity.kt` |

## Building

Needs JDK 17 or newer and the Android SDK (platform 35).

```bash
cd android
echo "sdk.dir=$HOME/Android/Sdk" > local.properties   # or set ANDROID_HOME
./gradlew testDebugUnitTest      # unit tests
./gradlew assembleDebug          # app/build/outputs/apk/debug/app-debug.apk
```

On Arch Linux: `sudo pacman -S jdk21-openjdk`, then the
[command-line tools](https://developer.android.com/studio#command-line-tools-only)
in `~/Android/Sdk/cmdline-tools/latest` and
`sdkmanager "platforms;android-35" "build-tools;35.0.0"`.

### CI and releases

`.github/workflows/android.yml` runs the unit tests and builds a debug APK on
every push. Pushing a `v*` tag also builds a **signed release APK** and attaches
it to the GitHub release. The signing key comes from repository secrets and is
never stored in the repo:

| Secret | Value |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | `base64 -w0 release.jks` |
| `ANDROID_KEYSTORE_PASSWORD` | keystore password |
| `ANDROID_KEY_ALIAS` | key alias |
| `ANDROID_KEY_PASSWORD` | key password |

To make a key (keep it somewhere safe: updates must be signed with the same one):

```bash
keytool -genkeypair -v -keystore release.jks -keyalg RSA -keysize 4096 -validity 10000 -alias focuslock
```
