#!/bin/bash
# Wake chain for the Mac that runs stock-briefing + stock-dashboard launchd jobs.
#
#   wake_chain.sh <grace-minutes>     # keeper mode (run by launchd at each slot)
#   wake_chain.sh --schedule-only     # just schedule the next wake and exit
#
# Keeper mode, at slot start:
#   1. schedule the next slot with `sudo -n pmset schedule wake` (chain link)
#   2. hold the Mac awake (caffeinate) for <grace-minutes> so every job in this
#      slot gets to start, then keep holding while any tracked python job runs
#      (backtests run 5h+), then exit and let the Mac sleep normally.
#
# Slots (KST) and what they cover:
#   01:55  02:00 backtest-data, 02:30 preset-backtests (~5.5h)
#   03:55  Sun 04:00 forward-returns
#   06:55  07:00-07:30 dashboard batch, 08:00 briefing morning, monthly 08:00 rebalancing
#   10:25  10:30 rotation-backtest
#   13:55  14:00 briefing midday
#   20:55  21:00 briefing preview
#
# Safety net (user-installed, once): sudo pmset repeat wakeorpoweron MTWRFSU 06:55:00
# Wake needs power adapter + lid open (or clamshell). Passwordless sudo for pmset:
#   /etc/sudoers.d/pmset-briefing  (see scripts/launchd/sudoers-pmset-briefing)

set -o pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export HOME="${HOME:-/Users/danggyu}"

SLOTS=("01:55" "03:55" "06:55" "10:25" "13:55" "20:55")
# command-line patterns of jobs that must finish before the Mac may sleep.
# NOTE: match on the script path, not the venv interpreter — the venv's python
# execs the Framework binary, so "…/.venv/bin/python" never shows up in ps.
TRACKED=(
  "streamlit_app/scripts/"     # stock-dashboard launchd jobs (cd $REPO; python streamlit_app/scripts/x.py)
  "main.py --mode "            # stock-briefing (cd $REPO; python main.py --mode x)
)

RECHECK_SEC="${WAKE_CHAIN_RECHECK_SEC:-300}"   # how often to re-check tracked jobs
LOGDIR="$HOME/claude/stock-briefing/logs/launchd"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/wake-$(date +%Y%m%d).log"
log_line() { printf '%s [%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" "${*:2}" >> "$LOG"; }

next_slot() {
  # prints "MM/dd/yy HH:MM:SS" of the first slot more than 2 minutes from now
  local now=$(( $(date +%s) + 120 )) day slot t
  for day in 0 1; do
    for slot in "${SLOTS[@]}"; do
      t=$(date -j -v+${day}d -f '%H:%M:%S' "$slot:00" '+%s')
      if [ "$t" -gt "$now" ]; then
        date -j -r "$t" '+%m/%d/%y %H:%M:%S'; return 0
      fi
    done
  done
  return 1
}

schedule_next() {
  local target; target=$(next_slot) || { log_line ERROR "no next slot"; return 1; }
  if /usr/bin/sudo -n /usr/bin/pmset schedule wake "$target" >> "$LOG" 2>&1; then
    log_line INFO "scheduled wake at $target"
  else
    log_line WARN "could not schedule wake at $target (sudoers for pmset not set up?)"
    return 1
  fi
}

tracked_running() {
  local pat
  for pat in "${TRACKED[@]}"; do
    pgrep -f "$pat" >/dev/null 2>&1 && return 0
  done
  return 1
}

if [ "$1" = "--schedule-only" ]; then
  schedule_next; exit $?
fi

GRACE_MIN="${1:-10}"
log_line INFO "keeper start (grace ${GRACE_MIN}m)"
schedule_next || true

# phase 1: grace window so every job in this slot has a chance to launch
[ "$GRACE_MIN" -gt 0 ] && /usr/bin/caffeinate -i -s -t $(( GRACE_MIN * 60 ))
# phase 2: stay awake while tracked jobs run (re-check every RECHECK_SEC)
while tracked_running; do
  /usr/bin/caffeinate -i -s -t "$RECHECK_SEC"
done
log_line INFO "keeper end — no tracked jobs running, Mac may sleep"
