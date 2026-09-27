#!/bin/bash
# launchd wrapper for stock_briefing on macOS.
#
# Usage: run_brief.sh <morning|midday|preview>
#
# launchd starts with a stripped-down environment (no PATH/LANG/HOME from the
# login shell), so everything is set explicitly here. Mirrors the pattern used
# by ~/claude/stock-dashboard/scripts/launchd/_common.sh.

set -o pipefail

MODE="${1:-morning}"
case "$MODE" in
  morning|midday|preview) ;;
  *) echo "usage: $0 <morning|midday|preview>" >&2; exit 2 ;;
esac

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export LANG="en_US.UTF-8"
export LC_ALL="en_US.UTF-8"
export HOME="${HOME:-/Users/danggyu}"
export PYTHONUNBUFFERED=1
# matplotlib: headless backend + writable cache dir under launchd
export MPLBACKEND=Agg
export MPLCONFIGDIR="$HOME/claude/stock-briefing/logs/.mplconfig"

REPO="$HOME/claude/stock-briefing"
VENV_PY="$REPO/.venv/bin/python"
LOGDIR="$REPO/logs/launchd"
mkdir -p "$LOGDIR" "$MPLCONFIGDIR"

STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="$LOGDIR/${MODE}-${STAMP}.log"

log_line() {
  local lvl="$1"; shift
  printf '%s [%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$lvl" "$*" >> "$LOG"
}

# ── Concurrency guard: skip if the same mode is still running ─────
PIDFILE="$LOGDIR/${MODE}.pid"
if [ -f "$PIDFILE" ]; then
  existing="$(cat "$PIDFILE" 2>/dev/null)"
  if [ -n "$existing" ] && kill -0 "$existing" 2>/dev/null; then
    log_line WARN "another ${MODE} run (PID $existing) is still active — skipping"
    exit 0
  fi
fi
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

if [ ! -x "$VENV_PY" ]; then
  log_line ERROR "venv python not found: $VENV_PY (run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt)"
  exit 1
fi
if [ ! -f "$REPO/.env" ]; then
  log_line ERROR ".env not found in $REPO — copy .env.example and fill in the keys"
  exit 1
fi

log_line INFO "start stock_briefing --mode $MODE"
cd "$REPO" || exit 1

# caffeinate: keep the Mac from going back to sleep while the briefing runs
# (-i idle sleep, -s system sleep on AC). The Mac is usually freshly woken by
# a pmset schedule at this point, so without this it could nod off mid-run.
if /usr/bin/caffeinate -i -s "$VENV_PY" main.py --mode "$MODE" >> "$LOG" 2>&1; then
  log_line INFO "done"
  rc=0
else
  rc=$?
  log_line ERROR "main.py exit $rc"
fi

# ── Schedule the next wake (chain) ────────────────────────────────
# morning → 13:55 today, midday → 20:55 today, preview → 06:55 tomorrow.
# A daily safety net (`pmset repeat wakeorpoweron MTWRFSU 06:55:00`) restarts
# the chain if any link is missed. Needs passwordless sudo for pmset:
#   /etc/sudoers.d/pmset-briefing
#   danggyu ALL=(root) NOPASSWD: /usr/bin/pmset schedule *, /usr/bin/pmset repeat *
# Wake only fires with the power adapter connected and the lid open (or clamshell).
schedule_next_wake() {
  local target
  case "$MODE" in
    morning) target="$(date '+%m/%d/%y') 13:55:00" ;;
    midday)  target="$(date '+%m/%d/%y') 20:55:00" ;;
    preview) target="$(date -v+1d '+%m/%d/%y') 06:55:00" ;;
  esac
  local target_epoch now_epoch
  target_epoch=$(date -j -f '%m/%d/%y %H:%M:%S' "$target" '+%s' 2>/dev/null) || return 0
  now_epoch=$(date '+%s')
  if [ "$target_epoch" -le "$now_epoch" ]; then
    log_line INFO "next wake $target already passed — not scheduling"
    return 0
  fi
  if /usr/bin/sudo -n /usr/bin/pmset schedule wake "$target" >> "$LOG" 2>&1; then
    log_line INFO "scheduled wake at $target"
  else
    log_line WARN "could not schedule wake (sudoers for pmset not set up?)"
  fi
}
schedule_next_wake

# 30-day log retention
find "$LOGDIR" -maxdepth 1 -type f -name '*.log' -mtime +30 -delete 2>/dev/null || true
exit $rc
