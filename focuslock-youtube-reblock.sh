#!/usr/bin/env bash
# Re-blocks YouTube after the one-time break's 1-hour window ends.
# Installed to /usr/local/sbin and run automatically by a systemd timer;
# cleans up its own timer/service once it has run.
set -euo pipefail

HOSTS=/etc/hosts
YT_DOMAINS=(youtube.com www.youtube.com m.youtube.com)

if grep -q "# FOCUSLOCK-END" "$HOSTS" 2>/dev/null; then
  for d in "${YT_DOMAINS[@]}"; do
    # 127.83.76.1 is the site logger's address (see focuslock-apply.sh); older locks used 0.0.0.0.
    grep -qE "^(0\.0\.0\.0|127\.83\.76\.1) ${d//./\\.}\$" "$HOSTS" || \
      sed -i "/# FOCUSLOCK-END/i 127.83.76.1 ${d}" "$HOSTS"
  done
fi

logger -t focuslock "YouTube one-time break ended - re-blocked" || true
command -v notify-send >/dev/null 2>&1 && notify-send "FocusLock" "YouTube break over - re-blocked." || true

systemctl disable --now focuslock-youtube-reblock.timer 2>/dev/null || true
rm -f /etc/systemd/system/focuslock-youtube-reblock.timer /etc/systemd/system/focuslock-youtube-reblock.service
systemctl daemon-reload || true
