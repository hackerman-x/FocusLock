#!/usr/bin/env bash
# Daily YouTube exception for an active FocusLock.
# Unblocks youtube.com for exactly 1 hour, then a systemd timer re-blocks
# it automatically -- no self-report, no manual re-lock, no way to extend.
# Usable once per calendar day for the life of the lock; resets at midnight.
set -euo pipefail

LOCKDIR=/etc/focuslock
UNLOCK_AT_FILE="$LOCKDIR/unlock_at"
LAST_USED_FILE="$LOCKDIR/youtube_break_last_used"
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPLY_SCRIPT="$SELF_DIR/focuslock-youtube-break-apply.sh"
TODAY=$(date +%Y-%m-%d)

if [[ ! -f "$UNLOCK_AT_FILE" ]]; then
  echo "No FocusLock is currently active -- YouTube isn't blocked right now. Nothing to do."
  exit 0
fi

if [[ -f "$LAST_USED_FILE" && "$(cat "$LAST_USED_FILE")" == "$TODAY" ]]; then
  echo "Today's YouTube break has already been used. Resets at midnight."
  exit 1
fi

if [[ ! -f "$APPLY_SCRIPT" ]]; then
  echo "Cannot find focuslock-youtube-break-apply.sh next to this script. Aborting." >&2
  exit 1
fi

echo "==================================================================="
echo " Daily YouTube exception:"
echo "   - Unblocks youtube.com for exactly 1 hour, starting now"
echo "   - Re-blocks itself automatically in 1 hour, no further action needed"
echo "   - Usable once per calendar day; resets at midnight, no extensions"
echo "==================================================================="
echo

sudo -v

read -r -p "Type YOUTUBE1H to confirm: " confirm
if [[ "$confirm" != "YOUTUBE1H" ]]; then
  echo "Confirmation did not match. Aborting, nothing changed."
  exit 1
fi

REBLOCK_HUMAN=$(date -d "+1 hour" +"%A, %Y-%m-%d %H:%M:%S %Z")
REBLOCK_CALENDAR=$(date -d "+1 hour" +"%Y-%m-%d %H:%M:%S")

sudo bash "$APPLY_SCRIPT" "$REBLOCK_HUMAN" "$REBLOCK_CALENDAR"

echo
echo "YouTube is unblocked now. It re-blocks itself automatically at: $REBLOCK_HUMAN"
echo "You can use this again tomorrow."
