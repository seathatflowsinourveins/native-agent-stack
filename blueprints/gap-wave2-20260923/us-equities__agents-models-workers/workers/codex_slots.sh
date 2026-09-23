#!/usr/bin/env bash
# Print the number of running real `codex exec` processes (argv[1] == exec), and optionally wait
# until fewer than 2 are running (the brief's concurrency rule). Usage: codex_slots.sh [--wait]
count() { for p in /proc/[0-9]*; do a=$(tr "\0" " " < $p/cmdline 2>/dev/null) || continue; set -- $a; [ "${1##*/}" = codex ] && [ "$2" = exec ] && echo x; done | wc -l; }
if [ "$1" = --wait ]; then for i in $(seq 1 120); do n=$(count); [ "$n" -lt 2 ] && { echo "codex exec running: $n"; exit 0; }; sleep 10; done; echo "still >=2 after 20 min"; exit 1; fi
count
