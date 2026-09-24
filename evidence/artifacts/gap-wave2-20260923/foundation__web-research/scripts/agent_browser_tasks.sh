#!/usr/bin/env bash
# Reconstruction of the ad hoc agent-browser driver used for gap 0's
# "agent_browser" results. The original run invoked these subprocess calls
# directly from the shell (each one timed individually) rather than through a
# saved script; this file was written during the fix round so the commands
# are reproducible and not just paraphrased in the receipt. Behavior matches
# the receipt's per-task table.
set -e
BASE_URL="${BASE_URL:-http://127.0.0.1:8317}"
agent-browser open "$BASE_URL/greeting.html"
agent-browser get title            # task1_read_title
agent-browser fill '#name' 'Gap Wave 2'   # task2a_fill
agent-browser click '#greet'              # task2b_click
agent-browser get text '#status'          # task2c_get_status
agent-browser click '#does-not-exist'     # task3_nonexistent_selector (expected to fail fast)
agent-browser close
