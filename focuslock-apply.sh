#!/usr/bin/env bash
# FocusLock privileged apply step. Run only via sudo, from lock.sh or the GUI.
# Args: $1 = unlock time, human-readable
#       $2 = unlock time, systemd OnCalendar format
#       $3 = comma-separated app keys to block, or "all" (default: all)
#       $4 = comma-separated domain-group keys to block, or "all" (default: all)
#       $5 = optional free-text intent for this session
#       $6 = optional custom apps, one per line: key<TAB>name<TAB>path|flatpak<TAB>target
#            (only those whose key is also listed in $3 are blocked)
#       $7 = optional custom websites, one per line: key<TAB>name<TAB>space-separated domains
#            (only those whose key is also listed in $4 are blocked)
set -euo pipefail

UNLOCK_HUMAN="$1"
UNLOCK_CALENDAR="$2"
SELECTED_APPS="${3:-all}"
SELECTED_DOMAINS="${4:-all}"
INTENT="${5:-}"
CUSTOM_DEFS="${6:-}"
CUSTOM_SITES="${7:-}"

LOCKDIR=/etc/focuslock
UNLOCK_AT_FILE="$LOCKDIR/unlock_at"
HOSTS=/etc/hosts
RESTORE_SCRIPT_DST=/usr/local/sbin/focuslock-unlock.sh
# Blocked sites point here instead of 0.0.0.0; focuslock-sitelog.py listens on
# it to count attempts to open them (it never serves anything, and with it
# not running the connection is simply refused -- blocked either way).
SITELOG_ADDR=127.83.76.1
SITELOG_DST=/usr/local/sbin/focuslock-sitelog.py
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# key:Display Name:Binaries:Snaps:PassthroughArg:Flatpaks
#   Binaries     '|'-separated paths, swapped for a blocking wrapper. Globs are
#                expanded at lock time, so e.g. a newly downloaded Godot
#                version is covered without editing this list.
#   Snaps        '|'-separated snap names, blocked with `snap disable` (a
#                swapped /snap/bin symlink would be restored by snapd).
#   PassthroughArg (optional) is a single argument that, if present anywhere
#                in the invocation, is let through to the real binary
#                untouched -- for calls system services make automatically.
#   Flatpaks     (optional) '|'-separated Flatpak app IDs, refused by the
#                selective /usr/bin/flatpak wrapper below (same as custom
#                Flatpaks). Only counted if installed system-wide or for you.
# Paths are absolute: this runs as root, so ~ would be /root.
STARDEW="/home/shahid/.local/share/Steam/steamapps/common/Stardew Valley"
APP_DEFS=(
  "discord:Discord:/usr/bin/discord::"
  "minecraft:Minecraft Launcher:/usr/bin/minecraft-launcher:::com.mojang.Minecraft"
  "modrinth:Modrinth App:/usr/bin/ModrinthApp:::com.modrinth.ModrinthApp"
  "steam:Steam:/usr/bin/steam:steam:"
  "stardew:Stardew Valley (SMAPI):$STARDEW/StardewModdingAPI|$STARDEW/StardewValley|$STARDEW/Stardew Valley|$STARDEW/StardewValley-original::"
  "xonotic:Xonotic::xonotic:"
  "nexuiz:Nexuiz:/usr/games/nexuiz|/usr/games/darkplaces::"
  "openspades:OpenSpades::openspades:"
  "oneclient:OneClient:/home/shahid/OneClient/oneclient_app_*.AppImage::"
  "flatpak:Flatpak:/usr/bin/flatpak::--print-updated-env"
  "godot:Godot:/usr/bin/godot3|/home/shahid/Godot/Godot*::"
  "unityhub:Unity Hub:/opt/unityhub/unityhub|/opt/unityhub/unityhub-bin|/home/shahid/Unity/Hub/Editor/*/Editor/Unity:::com.unity.UnityHub"
  "aseprite:Aseprite:/home/shahid/.local/bin/Aseprite*.AppImage::"
)

# Flatpak app IDs blocked on EVERY lock, whatever was selected, and kept out
# of APP_DEFS so they never appear in any list (GUI checklist, "currently
# blocked", or lock.sh's banner). Done by wrapping /usr/bin/flatpak so only
# these IDs are refused and everything else passes through -- unless Flatpak
# itself was selected, in which case the full Flatpak block covers them.
ALWAYS_BLOCKED_FLATPAKS=(org.vinegarhq.Sober)

# ---- custom apps ----
# These come from the user's own config, so every rule is checked here, as
# root, before anything is touched (focuslock_core.check_custom_path in the
# GUI mirrors them for friendlier errors -- keep the two in sync). The aim is
# that no custom entry can ever wrap something the system, the desktop, or
# this lock's own unlock script depends on.
USER_HOME=/home/shahid  # same assumption as the paths above
PROTECTED_NAMES=" sudo su sudoedit pkexec doas visudo passwd login bash sh dash zsh fish ksh env
  python python3 perl ruby systemctl systemd journalctl loginctl busctl dbus-daemon dbus-launch
  hyprland hyprctl hyprpm xwayland xorg x flatpak snap snapd dpkg dpkg-query apt apt-get
  mv cp rm ln install sed awk gawk mawk grep cat sort cut tr date logger notify-send resolvectl
  getent chmod chown tee head tail find xargs stat realpath readlink mkdir touch nano vim vi
  pw-play paplay aplay pipewire wireplumber pulseaudio rofi waybar kitty foot alacritty wezterm
  gnome-terminal konsole xterm i3 i3bar i3status i3lock sway swaybar swaylock dunst mako nm-applet
  blueman-applet flameshot kded5 kded6 plasmashell kwin_wayland kwin_x11 kitten picom compton
  xss-lock xautolock update-notifier "
PROTECTED_PREFIXES=(python3 systemd- hypr ibus xdg- at-spi gvfs polkit dbus fcitx pipewire
  wireplumber gnome-keyring gnome-session gnome-shell swww zeitgeist)
CUSTOM_REJECT=""

name_protected() {  # $1 = lowercase basename
  local word pre
  for word in $PROTECTED_NAMES; do
    if [[ "$1" == "$word" ]]; then return 0; fi
  done
  for pre in "${PROTECTED_PREFIXES[@]}"; do
    if [[ "$1" == "$pre"* ]]; then return 0; fi
  done
  return 1
}

core_package() {  # is $1 owned by a dpkg package of priority required/important/standard?
  local pkg prio
  if ! command -v dpkg >/dev/null 2>&1 && command -v pacman >/dev/null 2>&1; then
    # Arch: anything from the [core] repo (glibc, bash, coreutils, sudo, systemd...).
    pkg="$(pacman -Qqo "$1" 2>/dev/null | head -n1)" || true
    [[ -n "$pkg" ]] && pacman -Slq core 2>/dev/null | grep -qxF "$pkg"
    return
  fi
  pkg="$(dpkg -S "$1" 2>/dev/null | head -n1 | cut -d: -f1)" || true
  if [[ -z "$pkg" ]]; then return 1; fi
  prio="$(dpkg-query -W -f='${Priority}' "$pkg" 2>/dev/null)" || true
  [[ "$prio" == required || "$prio" == important || "$prio" == standard ]]
}

custom_path_ok() {  # sets CUSTOM_REJECT on failure
  local p="$1" real base
  CUSTOM_REJECT=""
  if [[ "$p" != /* || "$p" == *"/../"* || "$p" == *"/./"* || "$p" == *"//"* || "$p" == */ \
        || "$p" == */.. || "$p" == */. ]]; then
    CUSTOM_REJECT="not a plain absolute path"; return 1
  fi
  if [[ "$p" == *[\*\?\[\]\|]* || "$p" =~ [[:cntrl:]] ]]; then
    CUSTOM_REJECT="unsafe characters in path"; return 1
  fi
  if [[ "$p" == *.focuslock-real ]]; then CUSTOM_REJECT="FocusLock backup file"; return 1; fi
  case "$p" in
    /usr/bin/*|/usr/games/*|/usr/local/bin/*|/opt/*|"$USER_HOME"/*) ;;
    *) CUSTOM_REJECT="outside the allowed folders"; return 1 ;;
  esac
  case "$p" in
    "$USER_HOME"/.config/*|"$USER_HOME"/.local/bin/hypr*|"$SELF_DIR"/*)
      CUSTOM_REJECT="part of the desktop setup or FocusLock itself"; return 1 ;;
  esac
  if [[ ! -f "$p" || ! -x "$p" ]]; then CUSTOM_REJECT="not an executable file"; return 1; fi
  real="$(readlink -f "$p")"
  for base in "$(basename "$p")" "$(basename "$real")"; do
    if name_protected "${base,,}"; then CUSTOM_REJECT="protected system program"; return 1; fi
  done
  if [[ "$p" == /usr/* ]]; then
    if core_package "$p" || core_package "$real"; then
      CUSTOM_REJECT="part of a core system package"; return 1
    fi
  fi
  return 0
}

# key:Display Name:space-separated domains
DOMAIN_DEFS=(
  "discord_web:Discord (web):discord.com www.discord.com discordapp.com"
  "crazygames:CrazyGames:crazygames.com www.crazygames.com"
  "gxgames:GX Games:gx.games www.gx.games"
  "poki:Poki:poki.com www.poki.com"
  "roblox:Roblox (web):roblox.com www.roblox.com web.roblox.com"
  "instagram:Instagram (web):instagram.com www.instagram.com"
  "youtube:YouTube:youtube.com www.youtube.com m.youtube.com"
)

is_selected() {
  local key="$1" csv="$2"
  [[ "$csv" == "all" ]] && return 0
  [[ ",$csv," == *",$key,"* ]]
}

# Manifests unlock.sh restores from. Appended, never truncated, so a second
# apply during an active lock can't make unlock forget the first one's work.
WRAPPED_FILE="$LOCKDIR/wrapped_paths"
SNAPS_FILE="$LOCKDIR/disabled_snaps"

shopt -s nullglob

# Expand a '|'-separated list of paths/globs to existing files, one per line.
expand_paths() {
  local -a entries
  local entry p
  IFS='|' read -ra entries <<< "$1"
  for entry in "${entries[@]}"; do
    if [[ -z "$entry" ]]; then continue; fi
    # IFS='' keeps pathname expansion but disables word splitting, so paths
    # with spaces ("Stardew Valley") or quotes ("Godot4'6") stay whole.
    local IFS=''
    for p in $entry; do
      if [[ "$p" == *.focuslock-real || -d "$p" ]]; then continue; fi
      if [[ -e "$p" || -L "$p" ]]; then printf '%s\n' "$p"; fi
    done
  done
  return 0
}

has_real() { [[ -e "${1}.focuslock-real" || -L "${1}.focuslock-real" ]]; }

block_message_lines() {  # $1 = what to call the app in the message, $2 = app key to log ("" = don't)
  echo "UNTIL=\"\$(cat \"$UNLOCK_AT_FILE\" 2>/dev/null || echo soon)\""
  echo "MSG=\"FocusLock: $1 is blocked until \$UNTIL\""
  echo 'command -v notify-send >/dev/null 2>&1 && notify-send "FocusLock" "$MSG"'
  echo 'echo "$MSG" >&2'
  # Distraction log: one "<epoch>\t<key>" line in the launching user's own
  # state dir, for the GUI's stats. Keys are fixed or validated c_ keys;
  # re-checked here because they're written into the script.
  if [[ "$2" =~ ^[a-z0-9_]{1,48}$ ]]; then
    echo 'LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/focuslock"'
    echo "{ [[ -n \"\$HOME\" ]] && mkdir -p \"\$LOG_DIR\" && printf '%s\\t%s\\n' \"\$(date +%s)\" '$2' >> \"\$LOG_DIR/attempts.log\"; } 2>/dev/null"
  fi
  echo 'exit 1'
}

write_block_wrapper() {  # $1 path, $2 display name, $3 passthrough arg or "", $4 app key (for the log)
  local path="$1" name="$2" passthrough="$3" key="$4"
  mv "$path" "${path}.focuslock-real"
  {
    echo '#!/usr/bin/env bash'
    if [[ -n "$passthrough" ]]; then
      echo 'for arg in "$@"; do'
      echo "  if [[ \"\$arg\" == \"$passthrough\" ]]; then"
      echo "    exec \"${path}.focuslock-real\" \"\$@\""
      echo '  fi'
      echo 'done'
    fi
    block_message_lines "$name" "$key"
  } > "$path"
  chmod +x "$path"
  printf '%s\n' "$path" >> "$WRAPPED_FILE"
}

write_flatpak_selective_wrapper() {
  local path=/usr/bin/flatpak id i
  mv "$path" "${path}.focuslock-real"
  {
    echo '#!/usr/bin/env bash'
    echo 'for arg in "$@"; do'
    echo '  case "$arg" in'
    for id in "${ALWAYS_BLOCKED_FLATPAKS[@]}"; do
      echo "    $id|$id/*)"
      # Deliberately unnamed and never logged, so the app doesn't surface anywhere.
      block_message_lines "This app" "" | sed 's/^/      /'
      echo '      ;;'
    done
    # Custom Flatpaks (IDs and names were validated/sanitized when parsed).
    for i in "${!CUSTOM_FLATPAK_IDS[@]}"; do
      id="${CUSTOM_FLATPAK_IDS[$i]}"
      echo "    $id|$id/*)"
      block_message_lines "${CUSTOM_FLATPAK_NAMES[$i]}" "${CUSTOM_FLATPAK_KEYS[$i]}" | sed 's/^/      /'
      echo '      ;;'
    done
    echo '  esac'
    echo 'done'
    echo "exec \"${path}.focuslock-real\" \"\$@\""
  } > "$path"
  chmod +x "$path"
  printf '%s\n' "$path" >> "$WRAPPED_FILE"
}

flatpak_installed() {  # $1 = app ID; root can't `flatpak info` a per-user install
  [[ -d "/var/lib/flatpak/app/$1" || -d "$USER_HOME/.local/share/flatpak/app/$1" ]]
}

snap_state() {  # prints enabled | disabled | absent
  local line
  line="$(snap list "$1" 2>/dev/null | awk 'NR==2')" || true
  if [[ -z "$line" ]]; then echo absent
  elif [[ "$line" == *disabled* ]]; then echo disabled
  else echo enabled
  fi
}

mkdir -p "$LOCKDIR"
touch "$WRAPPED_FILE" "$SNAPS_FILE"

APPLIED_APP_KEYS=()
APPLIED_DOMAIN_KEYS=()
# Flatpak IDs for the selective wrapper (parallel arrays): built-in apps'
# from APP_DEFS and custom ones. FLATPAK_ONLY_KEYS are apps blocked by
# nothing but that wrapper, so they're only listed once it's in place.
CUSTOM_FLATPAK_IDS=()
CUSTOM_FLATPAK_NAMES=()
CUSTOM_FLATPAK_KEYS=()
FLATPAK_ONLY_KEYS=()
DOMAINS_TO_BLOCK=()

for def in "${DOMAIN_DEFS[@]}"; do
  key="${def%%:*}"
  rest="${def#*:}"
  domains="${rest#*:}"
  if is_selected "$key" "$SELECTED_DOMAINS"; then
    APPLIED_DOMAIN_KEYS+=("$key")
    for d in $domains; do DOMAINS_TO_BLOCK+=("$d"); done
  fi
done

# Custom websites. Each domain is re-checked here (same rule as
# focuslock_core._DOMAIN) since it's written into /etc/hosts as root.
DOMAIN_RE='^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$'
PROTECTED_DOMAINS=(localhost localdomain ubuntu.com snapcraft.io flathub.org debian.org canonical.com)
domain_ok() {
  local d="$1" p
  if (( ${#d} < 4 || ${#d} > 253 )) || ! [[ "$d" =~ $DOMAIN_RE ]]; then return 1; fi
  for p in "${PROTECTED_DOMAINS[@]}"; do
    if [[ "$d" == "$p" || "$d" == *".$p" ]]; then return 1; fi
  done
  return 0
}
while IFS=$'\t' read -r key name domains; do
  if [[ -z "$key" ]]; then continue; fi
  if ! [[ "$key" =~ ^w_[a-z0-9_]{1,40}$ ]]; then
    echo "FocusLock: skipping a custom website with an invalid key" >&2; continue
  fi
  if ! is_selected "$key" "$SELECTED_DOMAINS"; then continue; fi
  site_blocked=0
  for d in $domains; do
    if domain_ok "$d"; then
      DOMAINS_TO_BLOCK+=("$d")
      site_blocked=1
    else
      echo "FocusLock: not blocking domain '$d' (invalid or protected)" >&2
    fi
  done
  if (( site_blocked )); then APPLIED_DOMAIN_KEYS+=("$key"); fi
done <<< "$CUSTOM_SITES"

if [[ ${#DOMAINS_TO_BLOCK[@]} -gt 0 ]] && ! grep -q "# FOCUSLOCK-START" "$HOSTS" 2>/dev/null; then
  {
    echo "# FOCUSLOCK-START (auto-removed at unlock)"
    for d in "${DOMAINS_TO_BLOCK[@]}"; do
      echo "$SITELOG_ADDR $d"
    done
    echo "# FOCUSLOCK-END"
  } >> "$HOSTS"
fi

for def in "${APP_DEFS[@]}"; do
  IFS=: read -r key name bins snaps passthrough flatpaks <<< "$def"
  if ! is_selected "$key" "$SELECTED_APPS"; then continue; fi

  # Only list an app as blocked if something was actually there to block,
  # so "currently blocked" doesn't claim e.g. a not-yet-installed Unity editor.
  blocked_any=0

  while IFS= read -r p; do
    if [[ -z "$p" ]]; then continue; fi
    if ! has_real "$p"; then
      write_block_wrapper "$p" "$name" "$passthrough" "$key"
    fi
    blocked_any=1
  done < <(expand_paths "$bins")

  IFS='|' read -ra snap_names <<< "$snaps"
  for s in "${snap_names[@]}"; do
    if [[ -z "$s" ]]; then continue; fi
    case "$(snap_state "$s")" in
      enabled)
        if snap disable "$s" >/dev/null 2>&1; then
          printf '%s\n' "$s" >> "$SNAPS_FILE"
          blocked_any=1
        fi
        ;;
      disabled)
        # Only ours if an earlier apply in this lock disabled it; a snap the
        # user disabled themselves is left alone and not re-enabled later.
        if grep -qxF "$s" "$SNAPS_FILE"; then blocked_any=1; fi
        ;;
    esac
  done

  flatpak_any=0
  IFS='|' read -ra flatpak_ids <<< "$flatpaks"
  for id in "${flatpak_ids[@]}"; do
    if [[ -n "$id" ]] && flatpak_installed "$id"; then
      CUSTOM_FLATPAK_IDS+=("$id")
      CUSTOM_FLATPAK_NAMES+=("$name")
      CUSTOM_FLATPAK_KEYS+=("$key")
      flatpak_any=1
    fi
  done

  if (( blocked_any )); then
    APPLIED_APP_KEYS+=("$key")
  elif (( flatpak_any )); then
    FLATPAK_ONLY_KEYS+=("$key")
  fi
done

while IFS=$'\t' read -r key name source target; do
  if [[ -z "$key" ]]; then continue; fi
  if ! [[ "$key" =~ ^c_[a-z0-9_]{1,40}$ ]]; then
    echo "FocusLock: skipping a custom app with an invalid key" >&2; continue
  fi
  if ! is_selected "$key" "$SELECTED_APPS"; then continue; fi
  # Names go into generated scripts: keep only plain characters.
  name="$(printf '%s' "$name" | tr -cd 'A-Za-z0-9 ._()+-' | cut -c1-40)"
  if [[ -z "$name" ]]; then name="This app"; fi
  case "$source" in
    path)
      if custom_path_ok "$target"; then
        if ! has_real "$target"; then write_block_wrapper "$target" "$name" "" "$key"; fi
        APPLIED_APP_KEYS+=("$key")
      else
        echo "FocusLock: not blocking $name ($CUSTOM_REJECT)" >&2
      fi
      ;;
    flatpak)
      if [[ "$target" =~ ^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+){2,}$ ]]; then
        CUSTOM_FLATPAK_IDS+=("$target")
        CUSTOM_FLATPAK_NAMES+=("$name")
        CUSTOM_FLATPAK_KEYS+=("$key")
        FLATPAK_ONLY_KEYS+=("$key")
      else
        echo "FocusLock: not blocking $name (invalid Flatpak ID)" >&2
      fi
      ;;
    *)
      echo "FocusLock: not blocking $name (unknown source)" >&2
      ;;
  esac
done <<< "$CUSTOM_DEFS"

# Hidden always-on block plus any custom Flatpaks, via a selective wrapper.
# If Flatpak itself was selected it's already fully wrapped above (has_real
# is true), which covers all of these IDs too.
FLATPAK_COVERED=0
if has_real /usr/bin/flatpak; then
  FLATPAK_COVERED=1
elif [[ -e /usr/bin/flatpak ]]; then
  write_flatpak_selective_wrapper
  FLATPAK_COVERED=1
fi
if (( FLATPAK_COVERED )); then
  for key in "${FLATPAK_ONLY_KEYS[@]}"; do APPLIED_APP_KEYS+=("$key"); done
fi

echo "$UNLOCK_HUMAN" > "$UNLOCK_AT_FILE"
date +%s > "$LOCKDIR/locked_at"
printf '%s\n' "${APPLIED_APP_KEYS[@]}" > "$LOCKDIR/selected_apps"
printf '%s\n' "${APPLIED_DOMAIN_KEYS[@]}" > "$LOCKDIR/selected_domains"
if [[ -n "$INTENT" ]]; then
  echo "$INTENT" > "$LOCKDIR/intent"
fi

install -m 755 "$SELF_DIR/focuslock-unlock.sh" "$RESTORE_SCRIPT_DST"

cat > /etc/systemd/system/focuslock-unlock.service <<UNIT_EOF
[Unit]
Description=FocusLock - restore blocked apps and sites

[Service]
Type=oneshot
ExecStart=$RESTORE_SCRIPT_DST
UNIT_EOF

cat > /etc/systemd/system/focuslock-unlock.timer <<TIMER_EOF
[Unit]
Description=FocusLock unlock timer

[Timer]
OnCalendar=$UNLOCK_CALENDAR
Persistent=true
Unit=focuslock-unlock.service

[Install]
WantedBy=timers.target
TIMER_EOF

# Website attempt logger: a root-owned copy of the script, run with no
# privilege beyond binding ports 80/443 and a read-only system.
SITELOG=0
if grep -q "^$SITELOG_ADDR " "$HOSTS" 2>/dev/null && [[ -f "$SELF_DIR/focuslock-sitelog.py" ]]; then
  install -m 755 "$SELF_DIR/focuslock-sitelog.py" "$SITELOG_DST"
  cat > /etc/systemd/system/focuslock-sitelog.service <<SITELOG_EOF
[Unit]
Description=FocusLock - count attempts to open blocked websites
ConditionPathExists=$UNLOCK_AT_FILE

[Service]
ExecStart=/usr/bin/python3 $SITELOG_DST
Restart=on-failure
RestartSec=10
UMask=0022
StateDirectory=focuslock-sitelog
StateDirectoryMode=0755
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
AmbientCapabilities=CAP_NET_BIND_SERVICE
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictAddressFamilies=AF_INET AF_UNIX
MemoryMax=64M

[Install]
WantedBy=multi-user.target
SITELOG_EOF
  SITELOG=1
fi

systemctl daemon-reload
systemctl enable --now focuslock-unlock.timer
if (( SITELOG )); then
  # Logging is a nice-to-have: never let it fail the lock.
  systemctl enable --now focuslock-sitelog.service >/dev/null 2>&1 || \
    echo "FocusLock: website attempt logging didn't start (sites are still blocked)" >&2
fi
