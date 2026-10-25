#!/usr/bin/env bash
# Privileged apply step for the daily YouTube break. Run only via sudo,
# from focuslock-youtube-break.sh (CLI) or the GUI -- both handle their own
# confirmation UI first; this just does the work.
# Usable once per calendar day for the life of the lock: a 1-hour window,
# auto re-blocked by a systemd timer, no self-report, no extensions.
# Args: $1 = re-block time, human-readable   $2 = re-block time, OnCalendar format
set -euo pipefail

REBLOCK_HUMAN="$1"
REBLOCK_CALENDAR="$2"

LOCKDIR=/etc/focuslock
UNLOCK_AT_FILE="$LOCKDIR/unlock_at"
LAST_USED_FILE="$LOCKDIR/youtube_break_last_used"
UNTIL_FILE="$LOCKDIR/youtube_break_until"
HOSTS=/etc/hosts
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REBLOCK_SRC="$SELF_DIR/focuslock-youtube-reblock.sh"
REBLOCK_DST=/usr/local/sbin/focuslock-youtube-reblock.sh
TODAY=$(date +%Y-%m-%d)

if [[ ! -f "$UNLOCK_AT_FILE" ]]; then
  echo "No FocusLock is currently active." >&2
  exit 1
fi

if [[ -f "$LAST_USED_FILE" && "$(cat "$LAST_USED_FILE")" == "$TODAY" ]]; then
  echo "Today's YouTube break has already been used. Resets at midnight." >&2
  exit 1
fi

# Older locks point blocked sites at 0.0.0.0, newer ones at the site logger.
for d in youtube.com www.youtube.com m.youtube.com; do
  sed -i -E "/^(0\.0\.0\.0|127\.83\.76\.1) ${d//./\\.}\$/d" "$HOSTS"
done
command -v resolvectl >/dev/null 2>&1 && resolvectl flush-caches || true

mkdir -p "$LOCKDIR"
echo "$TODAY" > "$LAST_USED_FILE"
echo "$REBLOCK_HUMAN" > "$UNTIL_FILE"

install -m 755 "$REBLOCK_SRC" "$REBLOCK_DST"

cat > /etc/systemd/system/focuslock-youtube-reblock.service <<UNIT_EOF
[Unit]
Description=FocusLock - re-block YouTube after one-time break

[Service]
Type=oneshot
ExecStart=$REBLOCK_DST
UNIT_EOF

cat > /etc/systemd/system/focuslock-youtube-reblock.timer <<TIMER_EOF
[Unit]
Description=FocusLock YouTube re-block timer

[Timer]
OnCalendar=$REBLOCK_CALENDAR
Persistent=true
Unit=focuslock-youtube-reblock.service

[Install]
WantedBy=timers.target
TIMER_EOF

systemctl daemon-reload
systemctl enable --now focuslock-youtube-reblock.timer
