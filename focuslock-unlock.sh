#!/usr/bin/env bash
# FocusLock restore script. Installed to /usr/local/sbin and run by a
# systemd timer once the block duration expires. Also safe to run by
# hand as root if you ever need to fully undo a FocusLock install.
set -euo pipefail

LOCKDIR=/etc/focuslock
HOSTS=/etc/hosts
WRAPPED_FILE="$LOCKDIR/wrapped_paths"
SNAPS_FILE="$LOCKDIR/disabled_snaps"

# What locks started before the wrapped_paths manifest existed could have
# blocked. Harmless to check on every unlock: restore() is a no-op when
# there's no .focuslock-real next to the path.
LEGACY_APP_PATHS=(
  /usr/bin/discord
  /usr/bin/minecraft-launcher
  /usr/bin/steam
  /usr/bin/flatpak
  /home/shahid/OneClient/oneclient_app_2.3.1_x86_64.AppImage
)

restore() {
  if [[ -e "${1}.focuslock-real" || -L "${1}.focuslock-real" ]]; then
    mv -f "${1}.focuslock-real" "$1"
  fi
}

if grep -q "# FOCUSLOCK-START" "$HOSTS" 2>/dev/null; then
  sed -i '/# FOCUSLOCK-START/,/# FOCUSLOCK-END/d' "$HOSTS"
  command -v resolvectl >/dev/null 2>&1 && resolvectl flush-caches || true
fi

if [[ -f "$WRAPPED_FILE" ]]; then
  while IFS= read -r p; do
    if [[ -n "$p" ]]; then restore "$p"; fi
  done < <(sort -u "$WRAPPED_FILE")
fi
for p in "${LEGACY_APP_PATHS[@]}"; do restore "$p"; done

if [[ -f "$SNAPS_FILE" ]]; then
  while IFS= read -r s; do
    if [[ -n "$s" ]]; then snap enable "$s" >/dev/null 2>&1 || true; fi
  done < <(sort -u "$SNAPS_FILE")
fi

logger -t focuslock "FocusLock expired - apps and sites restored" || true
command -v notify-send >/dev/null 2>&1 && notify-send "FocusLock" "Block expired. Everything is restored." || true

systemctl disable --now focuslock-unlock.timer 2>/dev/null || true
systemctl disable --now focuslock-sitelog.service 2>/dev/null || true
rm -f /etc/systemd/system/focuslock-unlock.timer /etc/systemd/system/focuslock-unlock.service \
      /etc/systemd/system/focuslock-sitelog.service
systemctl daemon-reload || true

rm -rf "$LOCKDIR"
