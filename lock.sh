#!/usr/bin/env bash
# FocusLock - blocks distracting apps/sites for a fixed duration.
# Run as your normal user: ./lock.sh
set -euo pipefail

DURATION_LABEL="2 days"
DURATION_OFFSET="+2 days"
LOCKDIR=/etc/focuslock
UNLOCK_AT_FILE="$LOCKDIR/unlock_at"
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPLY_SCRIPT="$SELF_DIR/focuslock-apply.sh"

if [[ -f "$UNLOCK_AT_FILE" ]]; then
  echo "FocusLock is already active. It unlocks automatically at: $(cat "$UNLOCK_AT_FILE")"
  echo "There is no early-unlock option by design. Come back then."
  exit 1
fi

if [[ ! -f "$APPLY_SCRIPT" ]]; then
  echo "Cannot find focuslock-apply.sh next to this script. Aborting." >&2
  exit 1
fi

# Game-dev tools are left unblocked here, matching the GUI's defaults
# (focuslock_core.DEV_TOOLS) -- blocking them should be a deliberate choice.
DEV_TOOL_KEYS=" godot unityhub aseprite "
APP_KEYS=()
APP_LABELS=()
while IFS=: read -r key name _; do
  if [[ "$DEV_TOOL_KEYS" == *" $key "* ]]; then continue; fi
  APP_KEYS+=("$key")
  APP_LABELS+=("$name")
done < <(sed -n '/^APP_DEFS=(/,/^)/p' "$APPLY_SCRIPT" | grep -oP '^\s*"\K[^"]+')
APP_CSV=$(IFS=,; echo "${APP_KEYS[*]}")
APP_NAMES=$(IFS=,; echo "${APP_LABELS[*]}" | sed 's/,/, /g')
SITE_DOMAINS=$(sed -n '/^DOMAIN_DEFS=(/,/^)/p' "$APPLY_SCRIPT" | grep -oP '"[^:]+:\K[^:]+' | paste -sd, - | sed 's/,/, /g')

echo "==================================================================="
echo " FocusLock - about to block for $DURATION_LABEL:"
echo "   - Apps: $APP_NAMES"
echo "   - Websites: $SITE_DOMAINS"
echo
echo " There is NO manual override once this starts. It only lifts when"
echo " the $DURATION_LABEL timer expires (survives reboots)."
echo "==================================================================="
echo

echo "Step 1/3: authenticate (sudo password) to continue."
sudo -v

echo
read -r -p "Step 2/3: type LOCK to confirm you want this block applied: " confirm1
if [[ "$confirm1" != "LOCK" ]]; then
  echo "Confirmation did not match 'LOCK'. Aborting, nothing changed."
  exit 1
fi

UNLOCK_HUMAN=$(date -d "$DURATION_OFFSET" +"%A, %Y-%m-%d %H:%M:%S %Z")
read -r -p "Step 3/3: this locks until $UNLOCK_HUMAN with no early undo. Type CONFIRM to proceed: " confirm2
if [[ "$confirm2" != "CONFIRM" ]]; then
  echo "Confirmation did not match 'CONFIRM'. Aborting, nothing changed."
  exit 1
fi

UNLOCK_CALENDAR=$(date -d "$DURATION_OFFSET" +"%Y-%m-%d %H:%M:%S")

sudo bash "$APPLY_SCRIPT" "$UNLOCK_HUMAN" "$UNLOCK_CALENDAR" "$APP_CSV" all

echo
echo "FocusLock is ACTIVE. It will automatically lift on its own at: $UNLOCK_HUMAN"
