#!/usr/bin/env bash
# Roll back one G1 apply run from its backup manifest.
#
#   rollback.sh [BACKUP_DIR] [--dry-run]   (default) show what would be restored; touch nothing
#   rollback.sh [BACKUP_DIR] --apply        restore, then daemon-reload and restart the affected services
#   --force                                 also restore a path someone changed after the apply
#
# BACKUP_DIR defaults to the newest backup-* with a manifest in
# ${XDG_STATE_HOME:-~/.local/state}/native-agent-stack/g1-writer-identity/, where apply.sh keeps them. All or
# nothing: the rollback is refused before any change when a recorded path no longer holds exactly what apply
# wrote (sha256 in the manifest, or the settings key's written value; --force overrides) or a backup copy is
# missing. The codex link is put back as the recorded symlink; the one Claude settings key returns to its previous
# value (or is removed); nothing else in settings.json is touched. Prometheus is read back at the
# --web.listen-address of the restored unit.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PY:-python3}"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/g1-writer-identity"
MODE=dry-run
FORCE=0
BACKUP=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) MODE=apply ;;
    --dry-run) MODE=dry-run ;;
    --force) FORCE=1 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    -*) echo "unknown option: $1" >&2; exit 2 ;;
    *) BACKUP="$1" ;;
  esac
  shift
done
if [[ -z "$BACKUP" ]]; then
  for candidate in "$STATE_DIR"/backup-*; do
    if [[ -f "$candidate/manifest.json" ]]; then BACKUP="$candidate"; fi
  done
fi
[[ -n "$BACKUP" && -f "$BACKUP/manifest.json" ]] || {
  echo "no backup manifest found in $STATE_DIR (apply.sh --apply writes one)" >&2; exit 2; }
echo "G1 rollback ($MODE) from $BACKUP"

plan="$("$PY" - "$BACKUP/manifest.json" "$FORCE" <<'PYEOF'
import hashlib, json, os, sys
entries = json.load(open(sys.argv[1]))
force = sys.argv[2] == '1'


def settings_value(where):
    """'~/.claude/settings.json#env.KEY' -> the key's value now (None when unset); reads nothing else out."""
    file, _, dotted = where.partition('#')
    section, _, name = dotted.partition('.')
    try:
        block = json.load(open(os.path.expanduser(file))).get(section)
    except (OSError, ValueError, AttributeError):
        return '(unreadable)'
    return block.get(name) if isinstance(block, dict) else None


for entry in reversed(entries):
    path, kind = entry['path'], entry['kind']
    if kind == 'settings-key':
        current, written = settings_value(path), entry.get('written', 'true')
        if current != written and not force:
            now = 'unset' if current is None else json.dumps(current)[:40]
            print('\t'.join(['refuse', path, f'changed since apply (now {now}, apply wrote {json.dumps(written)}; '
                                             'use --force to restore anyway)']))
        else:
            print('\t'.join(['key', path, entry['previous'] or '']))
        continue
    current = hashlib.sha256(open(path, 'rb').read()).hexdigest() if os.path.isfile(path) else None
    if current != entry.get('written_sha256') and not force:
        print('\t'.join(['refuse', path, 'changed since apply (use --force to restore anyway)']))
    elif kind == 'symlink':
        print('\t'.join(['link', path, entry['link_target']]))
    elif entry['backup'] and not os.path.isfile(entry['backup']):
        print('\t'.join(['missing', path, entry['backup']]))
    elif entry['backup']:
        print('\t'.join(['file', path, entry['backup']]))
    else:
        print('\t'.join(['remove', path, '']))
PYEOF
)"
prom_url() {  # unit file: the loopback URL of its --web.listen-address (Prometheus listens on :9090 without one)
  local address host
  address="$(grep -o -e "--web\.listen-address=[^[:space:]\"']*" "$1" 2>/dev/null | tail -n 1 | cut -d= -f2- || true)"
  address="${address:-:9090}"
  host="${address%:*}"
  case "$host" in ''|0.0.0.0) host=127.0.0.1 ;; '[::]') host='[::1]' ;; esac
  printf 'http://%s:%s\n' "$host" "${address##*:}"
}
unit="$HOME/.config/systemd/user/ecosystem-prometheus.service"   # where apply.sh installs it
restart_prom=0; restart_otel=0; refused=0; missing=0
while IFS=$'\t' read -r action path source; do
  [[ -z "$action" ]] && continue
  case "$action" in
    refuse) echo "  refused: $path: $source"; refused=1 ;;
    missing) echo "  missing backup copy: $path would come from $source"; missing=1 ;;
    key) echo "  settings key: $path -> ${source:-(unset)}" ;;
    link) echo "  symlink: $path -> $source" ;;
    file) echo "  restore: $path from $source" ;;
    remove) echo "  remove: $path (it did not exist before apply)" ;;
  esac
  case "$path" in
    */ecosystem-prometheus.service|*/ecosystem-prometheus-rules.yml|*/ecosystem-prometheus.yml) restart_prom=1 ;;
    */collector.yaml) restart_otel=1 ;;
  esac
  case "$path" in */ecosystem-prometheus.service) unit="$path" ;; esac
done <<< "$plan"
if [[ $missing == 1 ]]; then echo "nothing restored: a backup copy is missing" >&2; exit 2; fi
if [[ $refused == 1 ]]; then echo "nothing restored: resolve the refused paths or rerun with --force" >&2; exit 1; fi
if [[ $MODE != apply ]]; then
  echo "dry run only; would restart:$([[ $restart_prom == 1 ]] && echo ' ecosystem-prometheus.service (after daemon-reload)')$([[ $restart_otel == 1 ]] && echo ' ecosystem-otelcol.service')"
  exit 0
fi
while IFS=$'\t' read -r action path source; do
  case "$action" in
    key) if [[ -n "$source" ]]; then "$PY" "$HERE/claude_setting.py" --set "$source"; else "$PY" "$HERE/claude_setting.py" --unset; fi ;;
    link) ln -sfn "$source" "$path.g1-old" && mv -Tf "$path.g1-old" "$path" ;;
    file) cp -p "$source" "$path.g1-old" && mv -f "$path.g1-old" "$path" ;;
    remove) rm -f "$path" ;;
  esac
done <<< "$plan"
status=0
if [[ $restart_prom == 1 ]]; then
  systemctl --user daemon-reload
  systemctl --user restart ecosystem-prometheus.service
  prom="$(prom_url "$unit")"   # the restored unit's listen address
  ready=0
  for _ in $(seq 1 180); do
    if curl -fsS --max-time 2 -o /dev/null "$prom/-/ready"; then ready=1; break; fi
    sleep 1
  done
  state="$(systemctl --user is-active ecosystem-prometheus.service || true)"
  echo "  prometheus: $state, $([[ $ready == 1 ]] && echo "ready at $prom" || echo "NOT ready at $prom after 180 s")"
  [[ $ready == 1 && $state == active ]] || status=1
fi
if [[ $restart_otel == 1 ]]; then
  systemctl --user restart ecosystem-otelcol.service
  sleep 3
  state="$(systemctl --user is-active ecosystem-otelcol.service || true)"
  echo "  otelcol: $state"
  [[ $state == active ]] || status=1
fi
exit "$status"
