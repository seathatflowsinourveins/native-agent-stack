#!/usr/bin/env bash
# G1 host apply: one writer per Prometheus token series (writer-identity profile) on an existing Linux host.
#
#   apply.sh [--dry-run]   (default) render, validate and diff every change; touch nothing
#   apply.sh --apply       back up, install, restart the two affected services and read them back
#   options: --repo DIR (checkout with the change; default: the checkout that holds this script),
#            --only STEP[,STEP...]   steps: prometheus, dashboards, collector, codex-launcher, claude-setting
#   env:     PY, a python with PyYAML (default python3)
#
# Native mechanisms used: observability/backends/configure.py and grand-dashboard/render.py (the repository
# renderers) with this host's port overrides; otelcol-contrib validate; promtool check rules/config;
# systemd-analyze verify; systemctl --user daemon-reload/restart; Grafana file provisioning (polls every 30 s, no
# restart). Three local-integration helpers sit beside this script: merge_collector.py and merge_prometheus.py
# move only the owned parts into the host's collector.yaml and ecosystem-prometheus.yml, keeping host ports and
# receivers, and claude_setting.py sets exactly one settings key. The codex launcher is
# observability/collector/codex-identity-launcher.sh.example, rendered.
# Any failed validation stops before the first change. Every file it replaces is first copied to a private
# backup, ${XDG_STATE_HOME:-~/.local/state}/native-agent-stack/g1-writer-identity/backup-<UTC>/ (mode 0700, kept
# outside /tmp, which the host empties at boot), with manifest.json; rollback.sh restores the newest one. Every
# --apply reads the running Prometheus and Collector back, also when their files are already in place (a rerun
# after a failed restart or read-back): one that differs (started or last loaded before its installed files, or a
# feature, rule group or pipeline missing) is restarted, and one that still differs stops the script with the
# rollback command. Prometheus is read at the --web.listen-address of the rendered unit, which carries this
# host's port overrides. No credential or auth store is read; the Grafana env file configure.py generates in the
# scratch render root is deleted unread.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(cd "$HERE/../../../.." && pwd)}"
PY="${PY:-python3}"
MODE=dry-run
ONLY=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) MODE=apply ;;
    --dry-run) MODE=dry-run ;;
    --repo) REPO="$2"; shift ;;
    --only) ONLY="$2"; shift ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

ECO="$HOME/.local/share/codex-ecosystem"
TOOLS="$ECO/tools"
CFG="$HOME/.config/ecosystem-observability"
DATA="$ECO/observability"
UNITS="$HOME/.config/systemd/user"
OTELCOL="$TOOLS/otelcol-0.161.0/otelcol-contrib"
PROMTOOL="$TOOLS/ecosystem-prometheus-3.15.0/promtool"
PROM_URL=""   # from the rendered unit's --web.listen-address, below
FEATURES="created-timestamp-zero-ingestion,promql-extended-range-selectors"
BUCKET_DROP='ecosystem_codex_.+_bucket;'
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/g1-writer-identity"
BACKUP="$STATE_DIR/backup-$STAMP"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/g1-apply-$STAMP.XXXXXX")"

want() { [[ -z "$ONLY" || ",$ONLY," == *",$1,"* ]]; }
say() { printf '%s\n' "$*"; }
die() { printf 'apply.sh: %s\n' "$*" >&2; exit 1; }
newest_backup() {  # what rollback.sh restores by default: the newest backup with a manifest
  local found="" candidate
  for candidate in "$STATE_DIR"/backup-*; do
    if [[ -f "$candidate/manifest.json" ]]; then found="$candidate"; fi
  done
  printf '%s' "$found"
}
# After a change or a restart: stop and name the rollback. This run's backup when it changed a file; otherwise the
# newest earlier one, whose files a rerun found in place.
fail_after_change() {
  local newest
  if [[ -f "$BACKUP/manifest.json" ]]; then die "$*; roll back with: $HERE/rollback.sh --apply $BACKUP"; fi
  newest="$(newest_backup)"
  if [[ -n "$newest" ]]; then
    die "$*; this run changed no file; roll back the apply that installed them with: $HERE/rollback.sh --apply $newest"
  fi
  die "$*; no apply has changed a file here (no backup), so there is nothing to roll back"
}
prom_url() {  # unit file: the loopback URL of its --web.listen-address (Prometheus listens on :9090 without one)
  local address host
  address="$(grep -o -e "--web\.listen-address=[^[:space:]\"']*" "$1" | tail -n 1 | cut -d= -f2- || true)"
  address="${address:-:9090}"
  host="${address%:*}"
  case "$host" in ''|0.0.0.0) host=127.0.0.1 ;; '[::]') host='[::1]' ;; esac
  printf 'http://%s:%s\n' "$host" "${address##*:}"
}
act() { if [[ $MODE == apply ]]; then say "  + $*"; "$@"; else say "  would: $*"; fi; }
sha() { if [[ -e "$1" ]]; then sha256sum "$1" | cut -c1-64; else echo absent; fi; }

backup_dir() {  # private, lasting, created on the first change only (a no-op apply leaves no empty backup)
  if [[ ! -d "$BACKUP" ]]; then
    (umask 077 && mkdir -p "$BACKUP")
    chmod 700 "$STATE_DIR" "$BACKUP"
  fi
}
manifest_add() {  # path kind(file|symlink) backup_or_empty link_target_or_empty
  backup_dir
  "$PY" - "$BACKUP/manifest.json" "$@" <<'PYEOF'
import json, sys, os
path, target, kind, backup, link = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
entries = json.load(open(path)) if os.path.exists(path) else []
entries.append({'path': target, 'kind': kind, 'backup': backup or None, 'link_target': link or None})
json.dump(entries, open(path, 'w'), indent=2)
PYEOF
}
manifest_written() {  # path: record the hash of what apply wrote, so rollback refuses to clobber later edits
  "$PY" - "$BACKUP/manifest.json" "$1" <<'PYEOF'
import json, sys, hashlib
path, target = sys.argv[1], sys.argv[2]
entries = json.load(open(path))
for entry in entries:
    if entry['path'] == target:
        entry['written_sha256'] = hashlib.sha256(open(target, 'rb').read()).hexdigest()
json.dump(entries, open(path, 'w'), indent=2)
PYEOF
}
backup_file() {  # path
  local path="$1" copy=""
  backup_dir
  if [[ -L "$path" ]]; then
    manifest_add "$path" symlink "" "$(readlink "$path")"
  else
    if [[ -e "$path" ]]; then
      copy="$BACKUP/$(echo "$path" | sed 's#^/##; s#/#__#g')"
      cp -p "$path" "$copy"
    fi
    manifest_add "$path" file "$copy" ""
  fi
}
install_file() {  # candidate target [mode]: atomic replace; default mode is the target's own (644 if new or a link)
  local candidate="$1" target="$2" mode="${3:-644}"
  if [[ -z "${3:-}" && -e "$target" && ! -L "$target" ]]; then mode="$(stat -c %a "$target")"; fi
  backup_file "$target"
  install -m "$mode" "$candidate" "$target.g1-new"
  mv -f "$target.g1-new" "$target"
  manifest_written "$target"
}
wait_http() {  # url seconds
  local url="$1" seconds="$2"
  for _ in $(seq 1 "$seconds"); do
    if curl --silent --fail --max-time 2 -o /dev/null "$url"; then return 0; fi
    sleep 1
  done
  return 1
}
show_diff() {  # old new label: returns 0 when they differ
  if cmp -s "$1" "$2"; then say "  $3: unchanged"; return 1; fi
  say "  $3: diff (first 40 lines)"
  diff -u "$1" "$2" | sed -n '3,42p' | sed 's/^/    /' || true
  return 0
}
yaml_diff() {  # old new label: normalized YAML diff; returns 0 when they differ in content
  "$PY" - "$1" "$2" > "$WORK/$3.diff" <<'PYEOF'
import sys, yaml, difflib
a = yaml.safe_dump(yaml.safe_load(open(sys.argv[1])), sort_keys=True, width=4096).splitlines()
b = yaml.safe_dump(yaml.safe_load(open(sys.argv[2])), sort_keys=True, width=4096).splitlines()
sys.stdout.write('\n'.join(difflib.unified_diff(a, b, 'host (normalized)', 'candidate (normalized)', lineterm='', n=1)))
PYEOF
  if [[ ! -s "$WORK/$3.diff" ]]; then say "  $3: already applied"; return 1; fi
  say "  $3: normalized diff (first 40 lines of $(wc -l < "$WORK/$3.diff"))"
  sed -n '1,40p' "$WORK/$3.diff" | cut -c1-220 | sed 's/^/    /'
  return 0
}

say "G1 writer-identity apply ($MODE) at $STAMP"
say "repo: $REPO ($(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?') $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo '?'), working tree $(git -C "$REPO" status --porcelain 2>/dev/null | wc -l) changed paths)"
for need in "$OTELCOL" "$PROMTOOL" "$REPO/observability/collector/collector.yaml" \
            "$REPO/observability/collector/codex-identity-launcher.sh.example" "$CFG/collector.yaml" \
            "$CFG/ecosystem-prometheus.yml" "$CFG/port-overrides.json"; do
  [[ -e "$need" ]] || { echo "missing: $need" >&2; exit 2; }
done
"$PY" -c 'import yaml' 2>/dev/null || { echo "$PY lacks PyYAML; set PY to a python that has it" >&2; exit 2; }
grep -q 'groupbyattrs/session' "$REPO/observability/collector/collector.yaml" || {
  echo "the repo checkout lacks the writer-identity profile" >&2; exit 2; }

# ---- render every candidate with the repository's own renderers --------------------------------------------
RENDER="$WORK/render"
"$PY" "$REPO/observability/backends/configure.py" --tools-root "$RENDER/tools" --config-root "$RENDER/config" \
  --data-root "$RENDER/data" --unit-root "$RENDER/unit" --port-overrides "$CFG/port-overrides.json" > "$WORK/configure.out"
rm -f "$RENDER/config/ecosystem-grafana.env"   # a throwaway generated secret; never read
sed -e "s#$RENDER/tools#$TOOLS#g; s#$RENDER/config#$CFG#g; s#$RENDER/data#$DATA#g" \
  "$RENDER/unit/ecosystem-prometheus.service" > "$WORK/ecosystem-prometheus.service"
PROM_URL="$(prom_url "$WORK/ecosystem-prometheus.service")"
cp "$RENDER/config/ecosystem-prometheus-rules.yml" "$WORK/ecosystem-prometheus-rules.yml"
cp "$RENDER/config/ecosystem-grafana-dashboards/ecosystem-dashboard.json" "$WORK/ecosystem-dashboard.json"
"$PY" "$REPO/observability/grand-dashboard/render.py" --output "$WORK/research-grand.json" > /dev/null
"$PY" "$HERE/merge_collector.py" --host "$CFG/collector.yaml" --repo "$REPO/observability/collector/collector.yaml" \
  --output "$WORK/collector.yaml"
"$PY" "$HERE/merge_prometheus.py" --host "$CFG/ecosystem-prometheus.yml" \
  --rendered "$RENDER/config/ecosystem-prometheus.yml" --output "$WORK/ecosystem-prometheus.yml"
codex_link="$ECO/bin/codex"
codex_real=""
if [[ -L "$codex_link" ]]; then
  codex_real="$(readlink "$codex_link")"
elif [[ -f "$codex_link" ]] && grep -q 'Codex telemetry identity launcher' "$codex_link"; then
  codex_real="$(sed -n "s/^exec '\\([^']*\\)' \"\\\$@\"$/\\1/p" "$codex_link")"
fi
[[ "$codex_real" == /* && -x "$codex_real" ]] || { echo "cannot resolve the real codex behind $codex_link" >&2; exit 2; }
sed "s#@CODEX_BIN@#$codex_real#" "$REPO/observability/collector/codex-identity-launcher.sh.example" > "$WORK/codex"
chmod 0755 "$WORK/codex"
read -r COLLECTOR_HEALTH COLLECTOR_SELF < <("$PY" - "$WORK/collector.yaml" <<'PYEOF'
import sys, yaml
c = yaml.safe_load(open(sys.argv[1]))
port = c['service']['telemetry']['metrics']['readers'][0]['pull']['exporter']['prometheus']['port']
print('http://' + c['extensions']['health_check']['endpoint'] + '/', f'http://127.0.0.1:{port}/metrics')
PYEOF
)
[[ -n "${COLLECTOR_SELF:-}" ]] || die "cannot read the Collector health and self-metrics endpoints from the candidate"
say "read-back endpoints: Prometheus $PROM_URL (rendered unit), Collector $COLLECTOR_HEALTH and $COLLECTOR_SELF"

# ---- validate candidates (read-only); any failure stops here, before the first change ----------------------------
say "validation:"
check() {  # label output-file command...: run it; on failure show its output and stop
  local label="$1" out="$2"; shift 2
  if ! "$@" > "$out" 2>&1; then
    sed 's/^/    /' "$out" >&2
    die "$label failed; nothing was changed"
  fi
}
check "otelcol-contrib validate" "$WORK/otelcol-validate.out" \
  env ECOSYSTEM_OBSERVABILITY_DATA="$DATA" "$OTELCOL" validate --config="$WORK/collector.yaml"
say "  otelcol-contrib validate: ok"
check "promtool check rules" "$WORK/promtool-rules.out" "$PROMTOOL" check rules "$WORK/ecosystem-prometheus-rules.yml"
sed 's/^/  /' "$WORK/promtool-rules.out"
check "promtool check config" "$WORK/promtool-config.out" \
  "$PROMTOOL" check config --syntax-only "$WORK/ecosystem-prometheus.yml"
say "  promtool check config: ok"
check "systemd-analyze verify" "$WORK/unit-verify.out" \
  systemd-analyze --user verify "$WORK/ecosystem-prometheus.service"
say "  systemd-analyze verify (unit): ok"
check "bash -n on the rendered launcher" "$WORK/launcher-syntax.out" bash -n "$WORK/codex"
real_version="$("$codex_real" --version 2>/dev/null | head -1 || true)"
launcher_version="$("$WORK/codex" --version 2>/dev/null | head -1 || true)"
[[ -n "$real_version" && "$launcher_version" == "$real_version" ]] || die "the rendered launcher does not run \
$codex_real (--version: '$launcher_version'; the real codex: '$real_version'); nothing was changed"
say "  launcher: runs $real_version"
check "dashboard JSON parse" "$WORK/dashboards.out" \
  "$PY" -c 'import json,sys; [json.load(open(p)) for p in sys.argv[1:]]' "$WORK/ecosystem-dashboard.json" "$WORK/research-grand.json"
say "  dashboards parse: ok"

# ---- read the running services back --------------------------------------------------------------------------
# Both run only as `if`/`||` conditions, where set -e is off, so every step checks its own status. They run on every
# --apply, also when the files are already in place: a rerun after a failed restart or read-back must not pass on
# unchanged files alone.
prom_diff=""
prometheus_matches() {  # seconds to wait for /-/ready: 0 when the running Prometheus serves the installed files,
  # else 1 with prom_diff naming the first difference
  prom_diff=""
  if ! wait_http "$PROM_URL/-/ready" "$1"; then prom_diff="Prometheus at $PROM_URL is not ready"; return 1; fi
  if ! curl -fsS -o "$WORK/prometheus-runtimeinfo.json" "$PROM_URL/api/v1/status/runtimeinfo" \
      || ! "$PY" - "$WORK/prometheus-runtimeinfo.json" "$UNITS/ecosystem-prometheus.service" \
           "$CFG/ecosystem-prometheus.yml" "$CFG/ecosystem-prometheus-rules.yml" <<'PYEOF'
import calendar, json, math, os, re, sys


def epoch(text):  # RFC 3339 as Prometheus writes it: nanoseconds, or whole seconds for lastConfigTime
    match = re.fullmatch(r'(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(\.\d+)?(Z|[+-]\d\d:\d\d)', text or '')
    if not match:
        sys.exit(f'  read back runtime: unreadable time {text!r}')
    seconds = calendar.timegm(tuple(int(part) for part in match.groups()[:6]))
    zone = match.group(8)
    if zone != 'Z':
        seconds -= (1 if zone[0] == '+' else -1) * (int(zone[1:3]) * 3600 + int(zone[4:6]) * 60)
    return seconds + float(match.group(7) or 0)


info = json.load(open(sys.argv[1]))['data']
unit, configs = sys.argv[2], sys.argv[3:]
started, loaded = epoch(info.get('startTime')), epoch(info.get('lastConfigTime'))
# The process must have started after its unit changed and loaded the config and rules after they changed.
# lastConfigTime has whole seconds, so it is compared with the whole second in which each file changed.
fresh = (info.get('reloadConfigSuccess') is True and started >= os.stat(unit).st_mtime
         and all(loaded >= math.floor(os.stat(path).st_mtime) for path in configs))
print(f"  read back runtime: started {info['startTime']}, configuration loaded {info['lastConfigTime']}, "
      f"{'after' if fresh else 'NOT after'} the installed unit, config and rules")
sys.exit(0 if fresh else 1)
PYEOF
  then
    prom_diff="the running Prometheus started, or last loaded its configuration, before the installed files"
    return 1
  fi
  if ! curl -fsS "$PROM_URL/api/v1/status/flags" | "$PY" -c 'import json,sys; f=json.load(sys.stdin)["data"]["enable-feature"]; print("  read back enable-feature:", f); sys.exit(0 if set(sys.argv[1].split(",")) <= set(f.split(",")) else 1)' "$FEATURES"; then
    prom_diff="Prometheus does not run with $FEATURES"; return 1
  fi
  if ! curl -fsS "$PROM_URL/api/v1/rules?type=alert" | "$PY" -c 'import json,sys; g=[r["name"] for x in json.load(sys.stdin)["data"]["groups"] if x["name"]=="native-telemetry-integrity" for r in x["rules"]]; print("  read back rules:", g); sys.exit(0 if {"EcosystemTokenCounterResets","EcosystemDeltaConversionDropped","EcosystemUnscopedTokenWriters"} <= set(g) else 1)'; then
    prom_diff="the native-telemetry-integrity rules are not loaded"; return 1
  fi
  if ! curl -fsS -G --data-urlencode 'query=increase(up[1m] anchored)' -o /dev/null "$PROM_URL/api/v1/query"; then
    prom_diff="Prometheus does not parse increase(up[1m] anchored)"; return 1
  fi
  say "  read back: increase(up[1m] anchored) parses"
  if ! curl -fsS "$PROM_URL/api/v1/status/config" | "$PY" -c 'import json,sys; sys.exit(0 if sys.argv[1] in json.load(sys.stdin)["data"]["yaml"] else 1)' "$BUCKET_DROP"; then
    prom_diff="the loaded Prometheus config lacks the Codex bucket drop"; return 1
  fi
  say "  read back: the loaded config drops Codex buckets ($BUCKET_DROP)"
  return 0
}
collector_diff=""
collector_stale=0
collector_matches() {  # seconds: 0 when the running Collector started after the installed collector.yaml and items
  # have passed groupbyattrs/session; else 1 with collector_diff set, and collector_stale=1 when a restart can help
  local seconds="$1" active rc _
  collector_diff=""; collector_stale=1
  if ! wait_http "$COLLECTOR_HEALTH" "$seconds"; then collector_diff="the Collector is not healthy"; return 1; fi
  active="$(systemctl --user is-active ecosystem-otelcol.service || true)"
  if [[ "$active" != active ]]; then collector_diff="ecosystem-otelcol.service is '$active'"; return 1; fi
  collector_diff="the Collector self-metrics at $COLLECTOR_SELF did not answer within $seconds s"
  for _ in $(seq 1 "$seconds"); do
    if curl -fsS --max-time 5 -o "$WORK/collector-self.txt" "$COLLECTOR_SELF" 2>/dev/null; then
      # Items pass groupbyattrs/session after one client export (Claude exports every 10 s).
      if "$PY" - "$WORK/collector-self.txt" "$CFG/collector.yaml" > "$WORK/collector-readback.txt" <<'PYEOF'
import os, re, sys, time
text = open(sys.argv[1]).read()
since = time.time() - os.stat(sys.argv[2]).st_mtime
up = re.search(r'^otelcol_process_uptime(?:\{[^}]*\})? ([0-9.eE+-]+)\s*$', text, re.M)
uptime = float(up.group(1)) if up else None
grouped = re.search(r'^otelcol_processor_incoming_items\{[^}]*processor="groupbyattrs/session"', text, re.M)
print(f'  read back otelcol: uptime {uptime} s, collector.yaml installed {since:.0f} s ago; groupbyattrs/session '
      f'items {"seen" if grouped else "not seen"}')
fresh = uptime is not None and uptime <= since + 5  # started after the installed file, so it runs that file
sys.exit(0 if fresh and grouped else (2 if fresh else 1))
PYEOF
      then rc=0; else rc=$?; fi
      if [[ $rc == 0 ]]; then cat "$WORK/collector-readback.txt"; return 0; fi
      if [[ $rc != 2 ]]; then
        cat "$WORK/collector-readback.txt"
        collector_diff="the running Collector did not start after the installed collector.yaml"
        return 1
      fi
      collector_stale=0
      collector_diff="no item passed groupbyattrs/session within $seconds s: check that a Claude or Codex process is \
exporting before rolling back"
    fi
    sleep 1
  done
  cat "$WORK/collector-readback.txt" 2>/dev/null || true
  return 1
}

# ---- plan and apply --------------------------------------------------------------------------------------------
changed_services=()
if want prometheus; then
  say "step prometheus: rules group native-telemetry-integrity; collector-native drops Codex buckets except token usage; unit --enable-feature=$FEATURES"
  rules_changed=0; config_changed=0; unit_changed=0
  if show_diff "$CFG/ecosystem-prometheus-rules.yml" "$WORK/ecosystem-prometheus-rules.yml" "rules"; then rules_changed=1; fi
  if yaml_diff "$CFG/ecosystem-prometheus.yml" "$WORK/ecosystem-prometheus.yml" "prometheus.yml"; then config_changed=1; fi
  if show_diff "$UNITS/ecosystem-prometheus.service" "$WORK/ecosystem-prometheus.service" "unit"; then unit_changed=1; fi
  if [[ $rules_changed == 1 ]]; then act install_file "$WORK/ecosystem-prometheus-rules.yml" "$CFG/ecosystem-prometheus-rules.yml"; fi
  if [[ $config_changed == 1 ]]; then act install_file "$WORK/ecosystem-prometheus.yml" "$CFG/ecosystem-prometheus.yml"; fi
  if [[ $unit_changed == 1 ]]; then act install_file "$WORK/ecosystem-prometheus.service" "$UNITS/ecosystem-prometheus.service"; fi
  prom_restart=""
  if [[ $rules_changed == 1 || $config_changed == 1 || $unit_changed == 1 ]]; then
    prom_restart="its files changed"
  elif [[ $MODE != apply ]]; then
    say "  prometheus: files already applied (--apply reads the running Prometheus back and restarts it if it differs)"
  elif prometheus_matches 10; then
    say "  prometheus: already applied; the running Prometheus serves the installed files"
  else
    prom_restart="$prom_diff"
  fi
  if [[ -n "$prom_restart" ]]; then
    say "  restart: $prom_restart"
    act systemctl --user daemon-reload || fail_after_change "systemctl --user daemon-reload failed"
    act systemctl --user restart ecosystem-prometheus.service || fail_after_change "ecosystem-prometheus.service did not restart"
    changed_services+=(ecosystem-prometheus.service)
    if [[ $MODE == apply ]]; then
      prometheus_matches 180 || fail_after_change "$prom_diff"
    fi
  fi
fi
if want dashboards; then
  say "step dashboards: ecosystem-native (rate/increase per writer, integrity panel) and research-grand (codex_exec activity); Grafana reloads provisioned files within 30 s"
  if show_diff "$CFG/ecosystem-grafana-dashboards/ecosystem-dashboard.json" "$WORK/ecosystem-dashboard.json" "ecosystem-native"; then
    act install_file "$WORK/ecosystem-dashboard.json" "$CFG/ecosystem-grafana-dashboards/ecosystem-dashboard.json"
  fi
  if show_diff "$CFG/ecosystem-grafana-dashboards/research-grand.json" "$WORK/research-grand.json" "research-grand"; then
    act install_file "$WORK/research-grand.json" "$CFG/ecosystem-grafana-dashboards/research-grand.json"
  fi
fi
if want collector; then
  say "step collector: groupbyattrs/session, session.id -> service.instance.id, aggregate_on_attributes, delta_to_cumulative"
  collector_restart=""
  if yaml_diff "$CFG/collector.yaml" "$WORK/collector.yaml" "collector.yaml"; then
    act install_file "$WORK/collector.yaml" "$CFG/collector.yaml"
    collector_restart="collector.yaml changed"
  elif [[ $MODE != apply ]]; then
    say "  (--apply reads the running Collector back and restarts it if it differs)"
  elif collector_matches 60; then
    say "  the running Collector runs the installed collector.yaml"
  elif [[ $collector_stale == 1 ]]; then
    collector_restart="$collector_diff"
  else
    fail_after_change "$collector_diff"
  fi
  if [[ -n "$collector_restart" ]]; then
    say "  restart: $collector_restart"
    act systemctl --user restart ecosystem-otelcol.service || fail_after_change "ecosystem-otelcol.service did not restart"
    changed_services+=(ecosystem-otelcol.service)
    if [[ $MODE == apply ]]; then
      collector_matches 60 || fail_after_change "$collector_diff"
    fi
  fi
fi
if want codex-launcher; then
  say "step codex-launcher: $codex_link -> identity launcher exec $codex_real"
  if [[ -f "$codex_link" && ! -L "$codex_link" ]] && cmp -s "$codex_link" "$WORK/codex"; then
    say "  launcher: already installed"
  else
    say "  now: $(if [[ -L "$codex_link" ]]; then echo "symlink -> $(readlink "$codex_link")"; else echo "file $(sha "$codex_link")"; fi)"
    act install_file "$WORK/codex" "$codex_link" 755
  fi
  if [[ $MODE == apply ]]; then  # also when already installed
    installed_version="$("$codex_link" --version 2>/dev/null | head -1 || true)"
    [[ "$installed_version" == "$real_version" ]] \
      || fail_after_change "bin/codex --version reads '$installed_version', not '$real_version'"
    say "  read back: bin/codex --version: $installed_version"
  fi
fi
if want claude-setting; then
  say "step claude-setting: ~/.claude/settings.json env.OTEL_METRICS_INCLUDE_SESSION_ID -> \"true\" (new sessions only)"
  current="$("$PY" "$HERE/claude_setting.py" | sed 's/^OTEL_METRICS_INCLUDE_SESSION_ID: //')"
  if [[ "$current" == true ]]; then
    say "  already true"
  else
    say "  now: $current"
    if [[ $MODE == apply ]]; then
      backup_dir
      "$PY" - "$BACKUP/manifest.json" "$current" <<'PYEOF'
import json, os, sys
path, previous = sys.argv[1], sys.argv[2]
entries = json.load(open(path)) if os.path.exists(path) else []
entries.append({'path': '~/.claude/settings.json#env.OTEL_METRICS_INCLUDE_SESSION_ID', 'kind': 'settings-key',
                'previous': None if previous == '(unset)' else previous, 'written': 'true'})
json.dump(entries, open(path, 'w'), indent=2)
PYEOF
      "$PY" "$HERE/claude_setting.py" --set true | sed 's/^/  /'
      [[ "$("$PY" "$HERE/claude_setting.py")" == "OTEL_METRICS_INCLUDE_SESSION_ID: true" ]] \
        || fail_after_change "the Claude settings key did not read back as true"
    else
      say "  would: $PY $HERE/claude_setting.py --set true"
    fi
  fi
fi

say ""
say "affected when applied: Prometheus restart (queries, rules and alerts pause for its WAL replay; Grafana panels"
say "  error briefly); Collector restart (a few seconds of OTLP export retries from every Claude/Codex process; the"
say "  delta_to_cumulative state restarts, one reset per Codex stream); bin/codex (every later codex launch on this"
say "  host, any session); Claude settings (sessions started afterwards; running sessions stay unscoped until they"
say "  restart). Grafana picks up dashboards within 30 s; no Loki, Alertmanager or Grafana restart."
if [[ $MODE == apply ]]; then
  say "services restarted: ${changed_services[*]:-none}; backup and manifest: $([[ -d "$BACKUP" ]] && echo "$BACKUP" || echo 'none (nothing changed)')"
  say "next: restart or end the Claude sessions that predate the change, run the scenario, then prove.sh"
else
  say "dry run only; nothing was changed. Candidates: $WORK"
fi
