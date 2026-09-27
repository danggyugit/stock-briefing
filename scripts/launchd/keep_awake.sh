#!/bin/bash
# Runs at 06:56 right after the daily 06:55 pmset wake. Holds the Mac awake
# for 75 minutes so the whole morning batch gets through before it can sleep:
#   07:00-07:30 stock-dashboard jobs (fetch-cache, macro, sec-intelligence,
#   portfolio-alert) and 08:00 stock-briefing morning.
# -i: no idle sleep, -s: no system sleep (AC only), -t: seconds.
exec /usr/bin/caffeinate -i -s -t 4500
