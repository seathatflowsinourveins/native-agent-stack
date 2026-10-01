#!/bin/sh
# Runs reproduce-vc-search.sh <output-dir> between two observations of the host paths where
# ByteRover 3.16.1 keeps state by default: ~/.config/brv, ~/.local/share/brv,
# ~/.local/state/brv, ~/.cache/brv, ~/.config/configstore and update-notifier's
# ~/.config/configstore/update-notifier-byterover-cli.json. Each observation is `test -e` per
# path, appended to <output-dir>/host-state-observation.txt with the UTC time. When TMPDIR
# names a directory that is empty before the run, the entries left in it afterwards are
# listed too. No process list is read. The reproduction itself reports whether every process
# it recorded is gone (90-stop.stdout). Local integration glue.
#
# Usage: sh run-with-host-observation.sh <output-dir>
set -u
here=$(cd "$(dirname "$0")" && pwd)
out=${1:?usage: sh run-with-host-observation.sh <output-dir>}
mkdir -p "$out"
report="$out/host-state-observation.txt"
observe() {
  printf 'host ByteRover paths %s the run (UTC %s):\n' "$1" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  for path in .config/brv .local/share/brv .local/state/brv .cache/brv .config/configstore \
      .config/configstore/update-notifier-byterover-cli.json; do
    if [ -e "$HOME/$path" ]; then echo "present ~/$path"; else echo "absent ~/$path"; fi
  done
}
tmp_watch=no
if [ -n "${TMPDIR:-}" ] && [ -d "$TMPDIR" ] && [ -z "$(find "$TMPDIR" -mindepth 1 -maxdepth 1)" ]; then
  tmp_watch=yes
fi
observe before > "$report"
echo "dedicated TMPDIR empty before the run: $tmp_watch" >> "$report"
sh "$here/reproduce-vc-search.sh" "$out"
status=$?
observe after >> "$report"
if [ "$tmp_watch" = yes ]; then
  left=$(find "$TMPDIR" -mindepth 1 -maxdepth 1 -exec basename {} \;)
  echo "entries left in the dedicated TMPDIR after the run: $(printf '%s' "$left" | grep -c .)" >> "$report"
  [ -z "$left" ] || printf '%s\n' "$left" | sed 's/^/  /' >> "$report"
fi
echo "reproduce-vc-search.sh exit status: $status" >> "$report"
exit "$status"
