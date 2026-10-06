# Apply the two upkeep timers on NativeStack2604

The co-op is the host writer. Run these reviewed operator blocks in order,
using one private batch directory outside /tmp. Each block is fail-closed.
Keep every attempt, including an interrupted or failed gate. No installed
launcher, collector replacement or additional install-plan default is created.

[The decision](../../../docs/decisions/2026-10-06-2604-upkeep-timer-transfer.md)
records source hashes and deviations. NativeStack's old Loki/ai-memory/Qdrant
origins are unsuitable here. Destination origins are exactly Loki 21300,
ai-memory 29374, and Qdrant 21633 when explicitly selected. The canonical
host template at repository@ecfa11276:adoption/templates/wsl/host.new-distro.json.template:8-9
and that pin's Loki config:3-8 supply these values.

## Prepare the pinned checkout and reviewed configuration

Set the exact commit the command center reviewed, not a branch name. The object
store checkout is read only; native git worktree add creates a separate lasting
checkout. Existing live paths must already match the approved pin and be clean:
do not reset or replace them. The private config source is prepared from
[config.ns2604.example.json](../../../observability/native-data/config.ns2604.example.json)
with reviewed non-secret native binary/data/project paths and report scopes.
The [observer configuration recipe](../../../observability/native-data/README.md)
describes those private bindings. Use the destination example here; the manifest
install below creates the previously absent config/state directories privately.
Never copy a credential store or the old distribution's configuration.
All three endpoint bindings are enforced before install and before a green run.

```sh
set -euo pipefail
: "${UPKEEP_APPROVED_SHA:?set the exact reviewed 40-hex commit}"
: "${UPKEEP_CONFIG_SOURCE:?set the reviewed non-secret config file}"
: "${UPKEEP_NODE_DIRECTORY:?set the directory containing Node 22+}"
: "${UPKEEP_TRANSFER_DIR:?set a new private batch directory outside /tmp}"
export UPKEEP_APPROVED_SHA UPKEEP_CONFIG_SOURCE UPKEEP_NODE_DIRECTORY UPKEEP_TRANSFER_DIR
rtk proxy python3 -B - <<'PY'
from pathlib import Path
import datetime as dt, json, os, re, subprocess
now = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M')
if '202610061015' <= now < '202610061345' or '202610061930' <= now < '202610070010':
    raise SystemExit('pause: paper window')
home = Path.home()
batch = Path(os.environ['UPKEEP_TRANSFER_DIR'])
approved = os.environ['UPKEEP_APPROVED_SHA']
if not re.fullmatch(r'[0-9a-f]{40}', approved):
    raise SystemExit('exact reviewed commit required')
if (not batch.is_absolute() or '..' in batch.parts or batch.resolve() != batch
        or not batch.is_relative_to(home) or batch.is_relative_to(Path('/tmp'))
        or any(parent.is_symlink() for parent in batch.parents)):
    raise SystemExit('private batch must be under HOME and outside /tmp')
if batch.exists() or batch.is_symlink():
    raise SystemExit('new batch required; retain previous attempts')
batch.mkdir(parents=True, mode=0o700)
os.chmod(batch, 0o700)
config_root = Path(os.environ.get('XDG_CONFIG_HOME', str(home / '.config')))
runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
if (not config_root.is_absolute() or not config_root.is_relative_to(home)
        or config_root.resolve() != config_root or any(p.is_symlink() for p in config_root.parents)
        or not runtime.is_absolute() or runtime.resolve() != runtime
        or (not runtime.is_relative_to(home) and runtime != Path(f'/run/user/{os.getuid()}'))):
    raise SystemExit('canonical owned config/runtime roots required before staging')
live = home / 'code/native-agent-stack-live'
store = home / 'code/native-agent-stack'
created = not live.exists() and not live.is_symlink()
manifest = {'schema_version': 1, 'approved_sha': approved, 'home': str(home),
            'batch': str(batch), 'config_root': str(config_root),
            'runtime_root': str(runtime), 'ops': str(home / '.local/state/native-agent-stack/ops'),
            'live_repo': str(live), 'object_store': str(store), 'live_created': created,
            'paths': [], 'created_directories': [], 'timers': {}, 'timer_actions': {}}
(batch / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
os.chmod(batch / 'manifest.json', 0o600)
if created:
    subprocess.run(['rtk', 'proxy', 'git', '-C', str(store), 'worktree', 'add',
                    '--detach', str(live), approved], check=True)
actual = subprocess.check_output(['git', '-C', str(live), 'rev-parse', 'HEAD'], text=True).strip()
dirty = subprocess.check_output(['git', '-C', str(live), 'status', '--porcelain'], text=True)
if actual != approved or dirty:
    raise SystemExit('needs_owner: live checkout pin or clean-state mismatch')
for name in ('rendered', 'baseline'):
    (batch / name).mkdir(mode=0o700)
print('pinned live checkout verified; object-store checkout unchanged')
PY
```

Before the first block that contacts the manager, define these native gates in
that shell. The same code is repeated in the self-contained rollback.
The window gate uses the corrected dated paper intervals with the reviewer's
20-minute lead-in: 10:15-13:45Z and19:30Z-00:10Z on the specified dates.
This retains common.sh:7-9's protection while scoping it to the announced runs.
It starts no heavy
phase during them and stops between steps; it never kills a running case.
The reload gate covers other *loaded* units, not unknown unloaded files or a
concurrent writer. Co-op custody must keep other configuration writers quiescent.

<!-- upkeep:manager-gates -->
```sh
set -euo pipefail
window_gate() {
  local stamp
  stamp=$(rtk proxy date -u +%Y%m%d%H%M)
  if { [ "$stamp" -ge 202610061015 ] && [ "$stamp" -lt 202610061345 ]; } ||
     { [ "$stamp" -ge 202610061930 ] && [ "$stamp" -lt 202610070010 ]; }; then
    printf 'pause: paper window; leave running cases alone\n' >&2; return 78
  fi
}
reload_gate() {
  local pending
  pending=$(rtk proxy systemctl --user show '*' --property=Id,NeedDaemonReload |
    awk -v RS= '/NeedDaemonReload=yes/ {
      for (i=1;i<=NF;i++) if ($i ~ /^Id=/) {
        id=substr($i,4)
        if (id !~ /^(disk-headroom-guard|ecosystem-native-data)\.(service|timer)$/) print id
      }
    }')
  [ -z "$pending" ] || { printf 'needs_owner: pending reload in other loaded units\n' >&2; return 78; }
}
window_gate
reload_gate
```

## Validate destination inputs and render

This gate executes the chosen Node's native --version, uses the existing
observer schema without collecting anything, checks the selected paths, and
rejects old/cross-host origins. Qdrant may remain null. Unknown native-tool rows
after collection remain unknown; passing the transfer does not qualify every tool.

<!-- upkeep:render -->
```sh
set -euo pipefail
: "${UPKEEP_TRANSFER_DIR:?batch directory required}"
rtk proxy python3 -B - "$HOME/code/native-agent-stack-live" "$UPKEEP_CONFIG_SOURCE" "$UPKEEP_NODE_DIRECTORY" "$UPKEEP_TRANSFER_DIR/rendered" <<'PY'
from pathlib import Path
import importlib.util, json, os, re, stat, subprocess, sys
repo, source, node, output = map(Path, sys.argv[1:])
for name, value in (('repository', repo), ('config', source), ('Node directory', node), ('output', output)):
    if not value.is_absolute() or any(c in str(value) for c in '\x00\n\r"\\$%'):
        raise SystemExit('unsupported absolute path: ' + name)
if ':' in str(node):
    raise SystemExit('Node directory contains PATH separator')
approved = os.environ.get('UPKEEP_APPROVED_SHA', '')
actual = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
dirty = subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain'], text=True)
if not re.fullmatch(r'[0-9a-f]{40}', approved) or actual != approved or dirty:
    raise SystemExit('approved clean checkout required before import')
spec = importlib.util.spec_from_file_location('approved_native_data', repo / 'observability/native-data/snapshot.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
config = module.validate_config(module.strict_json(source.read_bytes()))
if config['loki_url'] != 'http://127.0.0.1:21300/loki/api/v1/push':
    raise SystemExit('Loki 21300 required for NativeStack2604')
if config['ai_memory'].get('server_url') != 'http://127.0.0.1:29374':
    raise SystemExit('ai-memory 29374 required for NativeStack2604')
if config.get('qdrant') is not None and config['qdrant']['url'] != 'http://127.0.0.1:21633':
    raise SystemExit('Qdrant 21633 required for NativeStack2604')
for value in (config['rtk'], config['ai_memory']['binary'], config['qmd']['binary']):
    if not Path(value).is_file() or not os.access(value, os.X_OK):
        raise SystemExit('selected native executable is missing')
if not Path(config['token_report']).is_file():
    raise SystemExit('selected token report is missing')
for value in (config['project'], config['ai_memory']['data_dir']):
    if not Path(value).is_dir():
        raise SystemExit('selected project or native data directory is missing')
if not config.get('report_scopes'):
    raise SystemExit('explicit reviewed report scopes required')
version = subprocess.check_output([str(node / 'node'), '--version'], text=True, timeout=10).strip()
match = re.fullmatch(r'v(\d+)\.\d+\.\d+', version)
if not match or int(match[1]) < 22:
    raise SystemExit('Node 22 or later required')
config_root = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
destination = config_root / 'ecosystem-observability/native-data.json'
for value in (destination.parent, Path(config['state_dir'])):
    if value.is_symlink() or (value.exists() and not value.is_dir()):
        raise SystemExit('owned nonsymlink private directory required')
    if value.exists() and (value.stat().st_uid != os.getuid() or stat.S_IMODE(value.stat().st_mode) != 0o700):
        raise SystemExit('existing private directory must be owned mode 0700')
# State/config directories are created by the manifest-backed install, not this gate.
output.mkdir(parents=True, exist_ok=True)
(output / 'native-data.json').write_text(json.dumps(config, indent=2) + '\n')
for name in ('disk-headroom-guard.service', 'disk-headroom-guard.timer',
             'ecosystem-native-data.service', 'ecosystem-native-data.timer'):
    text = (repo / 'adoption/templates/systemd' / name).read_text()
    for token, value in {'@REPOSITORY@': str(repo), '@PRIVATE_CONFIG@': str(destination),
                         '@NODE_DIRECTORY@': str(node)}.items():
        text = text.replace(token, value)
    (output / name).write_text(text)
(output / 'disk-headroom-guard.sh').write_bytes((repo / 'tools/maintenance/disk-headroom-guard.sh').read_bytes())
print('destination endpoints, selected prerequisites, Node and clean pin verified')
PY
```

## Capture custody, install and reload

The manifest is write-ahead: it records each exact target, prior kind/bytes/mode,
backup, and expected candidate identity before mutation. A later operator edit
stops restoration. Existing private config with different bytes needs the owner;
it is not silently replaced. New config/state directories are private, while
existing directory modes are preserved. No real pruning is forced.

The source checkout/config/node checks above must pass first. Stop only the two
owned timers. If an owned service is running, pause and let it finish; do not stop
that case. Run the window/reload gates again immediately before daemon-reload.
The strict native verifier checks the candidate guard executable after install.

<!-- upkeep:install -->
```sh
set -euo pipefail
: "${UPKEEP_TRANSFER_DIR:?batch directory required}"
window_gate
reload_gate
rtk proxy python3 -B - "$UPKEEP_TRANSFER_DIR" <<'PY'
from pathlib import Path
import hashlib, json, os, stat, subprocess, sys
batch = Path(sys.argv[1])
manifest_path = batch / 'manifest.json'
manifest = json.loads(manifest_path.read_text())
if manifest.get('schema_version') != 1 or manifest.get('batch') != str(batch) or manifest.get('home') != str(Path.home()):
    raise SystemExit('validated batch manifest required')
if manifest['paths']:
    raise SystemExit('needs_owner: retain and restore/review previous mutation attempt')
def call(*args):
    return subprocess.run(['rtk', 'proxy', *args], check=True)
def show(unit, fields):
    raw = subprocess.check_output(['systemctl', '--user', 'show', unit, '--property=' + fields], text=True)
    return dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
def save():
    temporary = batch / 'manifest.pending'
    temporary.write_text(json.dumps(manifest, indent=2) + '\n')
    os.chmod(temporary, 0o600)
    temporary.replace(manifest_path)
def fingerprint(path):
    if path.is_symlink():
        return {'kind': 'link', 'target': os.readlink(path)}
    if not path.exists():
        return {'kind': 'absent'}
    s = path.stat()
    if not stat.S_ISREG(s.st_mode):
        raise SystemExit('needs_owner: managed path is not a regular file or symlink')
    return {'kind': 'file', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'mode': stat.S_IMODE(s.st_mode)}
units = Path(manifest['config_root']) / 'systemd/user'
ops = Path(manifest['ops'])
runtime = Path(manifest['runtime_root']) / 'systemd/user'
config_path = Path(manifest['config_root']) / 'ecosystem-observability/native-data.json'
rendered = batch / 'rendered'
config = json.loads((rendered / 'native-data.json').read_text())
for name in ('disk-headroom-guard.timer', 'ecosystem-native-data.timer'):
    p = show(name, 'ActiveState,UnitFileState')
    if p.get('ActiveState') not in ('active', 'inactive') or p.get('UnitFileState', 'not-found') not in ('enabled', 'enabled-runtime', 'disabled', '', 'not-found'):
        raise SystemExit('needs_owner: unsupported prior timer state')
    manifest['timers'][name] = p
    manifest['timer_actions'][name] = {'stop_prepared': False, 'enable_prepared': False}
save()
for parent in (units, ops, config_path.parent, Path(config['state_dir'])):
    if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
        raise SystemExit('owned nonsymlink managed directory required')
    if parent.exists() and parent.stat().st_uid != os.getuid():
        raise SystemExit('managed directory owner mismatch')
    if not parent.exists():
        manifest['created_directories'].append(str(parent))
        save()
        call('install', '-d', '-m', '0700', str(parent))
for name in manifest['timers']:
    if manifest['timers'][name]['ActiveState'] == 'active':
        manifest['timer_actions'][name]['stop_prepared'] = True
        save()
        call('systemctl', '--user', 'stop', name)
for name in ('disk-headroom-guard.service', 'ecosystem-native-data.service'):
    if show(name, 'ActiveState').get('ActiveState') not in ('inactive', 'failed'):
        raise SystemExit('pause: owned case is running; let it finish')
targets = [(ops / 'disk-headroom-guard.sh', rendered / 'disk-headroom-guard.sh', 0o755),
           (config_path, rendered / 'native-data.json', 0o600)]
targets.extend((units / name, rendered / name, 0o600) for name in
               ('disk-headroom-guard.service', 'disk-headroom-guard.timer',
                'ecosystem-native-data.service', 'ecosystem-native-data.timer'))
for path, candidate, mode in targets:
    before = fingerprint(path)
    expected = {'kind': 'file', 'sha256': hashlib.sha256(candidate.read_bytes()).hexdigest(), 'mode': mode}
    if path == config_path and before not in ({'kind': 'absent'}, expected):
        raise SystemExit('needs_owner: existing private config differs, preserve it')
    record = {'path': str(path), 'before': before, 'expected': expected,
              'candidate': str(candidate), 'backup': str(batch / 'baseline' / path.name), 'prepared': True, 'phase': 'prepared'}
    if before['kind'] != 'absent':
        call('cp', '-a', '--', str(path), record['backup'])
    manifest['paths'].append(record)
    save()
    if fingerprint(path) != before:
        raise SystemExit('needs_owner: path changed after capture')
    record['phase'] = 'remove_prepared'
    save()
    call('rm', '-f', '--', str(path))
    record['phase'] = 'install_prepared'
    save()
    call('install', '-m', format(mode, 'o'), str(candidate), str(path))
    if fingerprint(path) != expected:
        raise SystemExit('installed identity mismatch')
    call('cmp', '--', str(candidate), str(path))
    record['phase'] = 'installed'
    save()
for base in (units, runtime):
    for name in manifest['timers']:
        path = base / 'timers.target.wants' / name
        before = fingerprint(path)
        if before['kind'] not in ('absent', 'link'):
            raise SystemExit('needs_owner: expected enablement symlink is a regular file')
        expected = {'kind': 'link', 'target': str(units / name)} if base == units else before
        record = {'path': str(path), 'before': before, 'expected': expected,
                  'backup': str(batch / 'baseline' / ('config-' if base == units else 'runtime-') / name),
                  'prepared': True, 'phase': 'enable_prepared'}
        if before['kind'] != 'absent':
            Path(record['backup']).parent.mkdir(mode=0o700, exist_ok=True)
            call('cp', '-a', '--', str(path), record['backup'])
        manifest['paths'].append(record)
        save()
call('systemd-analyze', '--user', '--man=no', '--generators=no', '--recursive-errors=no', 'verify',
     *(str(rendered / name) for name in ('disk-headroom-guard.service', 'disk-headroom-guard.timer',
                                        'ecosystem-native-data.service', 'ecosystem-native-data.timer')))
print('manifest-backed install and strict native verification passed')
PY
window_gate
reload_gate
rtk proxy systemctl --user daemon-reload
```

## Two fresh green runs, independent publication, then enable

The live ExecMainStartTimestamp/InvocationID can disappear when systemd unloads
an inactive unit. They are observations, not the freshness gate. For each idle
service, capture the native user-journal cursor, start once synchronously, and
require a successful start-job after that boundary, joined to fresh artifact
content. The start is never automatically retried on a gate failure.

Source: systemd@b3d8fc43 man/systemd.unit.xml:558-586; src/core/job.c:812-821;
src/core/unit.c:6834-6839; man/journalctl.xml:262-266,667-675.
Do not require a Deactivated-successfully message: user managers log that at DEBUG.

<!-- upkeep:green -->
```sh
set -euo pipefail
: "${UPKEEP_TRANSFER_DIR:?batch directory required}"
window_gate
rtk proxy python3 -B - "$UPKEEP_TRANSFER_DIR" <<'PY'
from pathlib import Path
import datetime as dt, hashlib, json, os, re, subprocess, sys, time
batch = Path(sys.argv[1])
manifest = json.loads((batch / 'manifest.json').read_text())
config_path = Path(manifest['config_root']) / 'ecosystem-observability/native-data.json'
config = json.loads(config_path.read_text())
if (config['loki_url'] != 'http://127.0.0.1:21300/loki/api/v1/push'
        or config['ai_memory'].get('server_url') != 'http://127.0.0.1:29374'
        or (config.get('qdrant') is not None and config['qdrant']['url'] != 'http://127.0.0.1:21633')):
    raise SystemExit('destination endpoints changed; no start')
for record in manifest['paths']:
    path = Path(record['path'])
    if record['expected']['kind'] == 'file':
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != record['expected']['sha256']:
            raise SystemExit('installed bytes changed; no start')
def output(*args):
    return subprocess.check_output(list(args), text=True)
def json_lines(raw):
    return [json.loads(line) for line in raw.splitlines() if line.startswith('{')]
units = ('disk-headroom-guard.service', 'ecosystem-native-data.service')
receipts = {}
for unit in units:
    now = int(dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M'))
    if 202610061015 <= now < 202610061345 or 202610061930 <= now < 202610070010:
        raise SystemExit('pause between cases: paper window')
    state = output('systemctl', '--user', 'show', unit, '--property=ActiveState', '--value').strip()
    if state not in ('inactive', 'failed'):
        raise SystemExit('pause: owned service is running')
    cursor_rows = json_lines(output('journalctl', '--user', '--no-pager', '-n', '1', '-o', 'json', '--output-fields=__CURSOR'))
    if len(cursor_rows) != 1 or not cursor_rows[0].get('__CURSOR'):
        raise SystemExit('native journal cursor required before start')
    cursor = cursor_rows[0]['__CURSOR']
    artifact = Path(manifest['ops']) / 'disk-headroom.csv' if unit.startswith('disk-') else Path(config['state_dir']) / 'snapshot.json'
    before_hash = hashlib.sha256(artifact.read_bytes()).hexdigest() if artifact.is_file() else None
    started = time.time_ns()
    subprocess.run(['rtk', 'proxy', 'systemctl', '--user', 'start', unit], check=True)
    properties = dict(line.split('=', 1) for line in output('systemctl', '--user', 'show', unit,
                      '--property=Result,ExecMainStatus').splitlines() if '=' in line)
    if properties.get('Result') != 'success' or properties.get('ExecMainStatus') != '0':
        raise SystemExit('native service result failed')
    raw = output('journalctl', '--user', '--user-unit=' + unit, '--after-cursor=' + cursor,
                 '--no-pager', '-o', 'json',
                 '--output-fields=MESSAGE_ID,USER_UNIT,USER_INVOCATION_ID,JOB_ID,JOB_TYPE,JOB_RESULT')
    (batch / (unit + '.jobs.jsonl')).write_text(raw)
    jobs = [row for row in json_lines(raw) if row.get('MESSAGE_ID') == '39f53479d3a045ac8e11786248231fbf'
            and row.get('USER_UNIT') == unit and row.get('JOB_TYPE') == 'start' and row.get('JOB_RESULT') == 'done'
            and re.fullmatch(r'[0-9a-f]{32}', row.get('USER_INVOCATION_ID', ''))
            and int(row.get('__REALTIME_TIMESTAMP', '0')) * 1000 >= started]
    if len(jobs) != 1 or not artifact.is_file():
        raise SystemExit('no unique fresh successful start job/artifact')
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if digest == before_hash:
        raise SystemExit('artifact unchanged since start boundary')
    if unit.startswith('disk-'):
        timestamp, free = artifact.read_text().splitlines()[-1].split(',')
        observed = dt.datetime.fromisoformat(timestamp.replace('Z', '+00:00')).timestamp()
        if observed < started // 1000000000 or not free.isdigit():
            raise SystemExit('fresh valid guard sample required')
    else:
        snapshot = json.loads(artifact.read_text())
        observed = snapshot['observed_unix']
        if observed * 1000000000 < started or snapshot['loki']['http_status'] != 204 or snapshot['loki']['error']:
            raise SystemExit('fresh snapshot and returned HTTP204 required')
        # Whitelisted stdout summary is read separately; never print config or command records.
        summary_raw = output('journalctl', '--user', '--user-unit=' + unit, '--after-cursor=' + cursor,
                             '--invocation=' + jobs[0]['USER_INVOCATION_ID'], '--no-pager', '-o', 'cat')
        summaries = [row for row in json_lines(summary_raw) if row.get('snapshot_sha256') == digest]
        if len(summaries) != 1 or summaries[0].get('observed_unix') != observed:
            raise SystemExit('journal summary/snapshot hash join failed')
        ended = time.time_ns()
        response_path = batch / 'loki21300-query-range.json'
        result = subprocess.run(['curl', '--noproxy', '*', '--max-time', '10', '--fail', '--silent',
                    '--show-error', '--get', 'http://127.0.0.1:21300/loki/api/v1/query_range',
                    '--data-urlencode', 'query={service_name=\"agent-stack-native-data\",record_kind=\"snapshot\"}',
                    '--data-urlencode', 'start=' + str(started), '--data-urlencode', 'end=' + str(ended),
                    '--data-urlencode', 'limit=100', '--data-urlencode', 'direction=forward',
                    '--output', str(response_path), '--write-out', '%{http_code}'], capture_output=True, text=True, check=True)
        if result.stdout != '200':
            raise SystemExit('independent21300 query HTTP200 required')
        response = json.loads(response_path.read_text())
        data = response.get('data', {})
        if response.get('status') != 'success' or data.get('resultType') != 'streams':
            raise SystemExit('independent21300 query shape failed')
        marker = snapshot['rows'][-1]
        found = []
        for stream in data.get('result', []):
            if stream.get('stream', {}).get('service_name') != 'agent-stack-native-data' or stream['stream'].get('record_kind') != 'snapshot':
                continue
            for nanoseconds, line in stream.get('values', []):
                if started <= int(nanoseconds) < ended and json.loads(line) == marker:
                    found.append(line)
        if len(found) != 1:
            raise SystemExit('exact generated marker missing/ambiguous on Loki21300')
        (batch / 'native-data-proof.json').write_text(json.dumps({
            'observed_unix': observed, 'snapshot_sha256': digest, 'loki_query_http_status': 200,
            'unknown_count': marker['unknown_count'], 'stale_count': marker['stale_count']}, sort_keys=True) + '\n')
    receipts[unit] = {'job': jobs[0], 'artifact_sha256': digest, 'observed_unix': observed}
    (batch / (unit + '.green.json')).write_text(json.dumps(receipts[unit], indent=2) + '\n')
print('two fresh runs and independent Loki21300 marker join passed')
PY
# Enable only after both green files exist and the gate before its native implicit reload.
window_gate
reload_gate
rtk proxy test -s "$UPKEEP_TRANSFER_DIR/disk-headroom-guard.service.green.json"
rtk proxy test -s "$UPKEEP_TRANSFER_DIR/ecosystem-native-data.service.green.json"
rtk proxy python3 -B - "$UPKEEP_TRANSFER_DIR/manifest.json" <<'PY'
from pathlib import Path
import json, os, sys
path = Path(sys.argv[1])
manifest = json.loads(path.read_text())
for name in ('disk-headroom-guard.timer', 'ecosystem-native-data.timer'):
    manifest['timer_actions'][name]['enable_prepared'] = True
temporary = path.with_name('manifest.pending')
temporary.write_text(json.dumps(manifest, indent=2) + '\n')
os.chmod(temporary, 0o600)
temporary.replace(path)
PY
window_gate
reload_gate
rtk proxy systemctl --user enable --now disk-headroom-guard.timer ecosystem-native-data.timer
```

## Read-back and rollback

Native enable performs a daemon-reload, not a manager restart; check the reload
gate immediately before it as well as before the explicit install/restore reloads.
Keeping --no-reload would leave systemd's global unit-file-state cache dirty and
make unrelated units report NeedDaemonReload=yes, so it is not used here.
Sources: systemd@b3d8fc43 man/systemctl.xml:883-889;
src/core/manager.h:278-281; dbus-manager.c:2294-2304; unit.c:3852-3853.

Read-back compares, rather than merely printing, hashes. Require enabled/active
timers, the source cadence, exact candidate bytes, both green receipts and the
independent21300 marker receipt. Counts may remain unknown/stale.

```sh
set -euo pipefail
: "${UPKEEP_TRANSFER_DIR:?batch directory required}"
for name in disk-headroom-guard.timer ecosystem-native-data.timer; do
  rtk proxy systemctl --user is-enabled "$name"
  rtk proxy systemctl --user is-active "$name"
done
rtk proxy python3 -B - "$UPKEEP_TRANSFER_DIR" <<'PY'
from pathlib import Path
import hashlib, json, os, re, stat, subprocess, sys
batch = Path(sys.argv[1])
manifest = json.loads((batch / 'manifest.json').read_text())
for name, boot, accuracy in (('disk-headroom-guard.timer', '2min', '15s'),
                              ('ecosystem-native-data.timer', '45s', '10s')):
    raw = subprocess.check_output(['systemctl', '--user', 'show', name,
        '--property=Unit,TimersMonotonic,AccuracyUSec,NeedDaemonReload,DropInPaths,FragmentPath,UnitFileState,ActiveState'], text=True)
    p = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
    enabled = subprocess.check_output(['systemctl', '--user', 'is-enabled', name], text=True).strip()
    expected_fragment = str(Path(manifest['config_root']) / 'systemd/user' / name)
    timing_text = ' '.join(line.split('=', 1)[1] for line in raw.splitlines() if line.startswith('TimersMonotonic='))
    timings = dict(re.findall(r'(OnBootUSec|OnUnitActiveUSec)=([^ ;}]+)', timing_text))
    if (p.get('Unit') != name.replace('.timer', '.service') or p.get('AccuracyUSec') != accuracy
            or timings != {'OnBootUSec': boot, 'OnUnitActiveUSec': '2min'}
            or p.get('NeedDaemonReload') != 'no' or p.get('DropInPaths')
            or p.get('FragmentPath') != expected_fragment or enabled != 'enabled'
            or p.get('ActiveState') != 'active'):
        raise SystemExit('effective timer binding/cadence/state differs')
for record in manifest['paths']:
    path = Path(record['path'])
    expected = record['expected']
    if expected['kind'] == 'file':
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected['sha256'] or stat.S_IMODE(path.stat().st_mode) != expected['mode']:
            raise SystemExit('read-back file identity mismatch')
    elif expected['kind'] == 'link':
        if not path.is_symlink() or os.readlink(path) != expected['target']:
            raise SystemExit('read-back enablement link mismatch')
for name in ('disk-headroom-guard.service.green.json', 'ecosystem-native-data.service.green.json', 'native-data-proof.json'):
    if not (batch / name).is_file():
        raise SystemExit('read-back receipt missing')
proof = json.loads((batch / 'native-data-proof.json').read_text())
print(json.dumps(proof, sort_keys=True))
PY
```

### Restore from a fresh shell

Set only UPKEEP_TRANSFER_DIR to the retained batch. This block reconstructs
all roots from a validated, owned mode0600 manifest before the first systemctl or
unlink. Missing/corrupt manifests fail nonzero. It restores only captured,
prepared paths whose current identity still matches the baseline or installed
candidate. A later operator edit or corrupted backup is needs_owner and remains
untouched. It stops timers, then pauses if a service case is running.
Never use blanket disable: it can remove unrelated manual links.

Source: co-op reviewed common.sh SHA2569d44983b2120bd5446e210b60100fb8e6c7e2ef08a85fc69400fad4457e65e12
and91-restore.sh SHA256852ccc9608c8686b2abb8a8a811b2a4a569da664b392651bca69d15f4786d5b3;
systemd@b3d8fc43 man/systemctl.xml:936-945 and1477-1486;
coreutils@8e075ff8 doc/coreutils.texi:8980-8989,9121-9127.
The identity manifest fills the demonstrated custody gap in the native recipe.

<!-- upkeep:restore -->
```sh
set -euo pipefail
: "${UPKEEP_TRANSFER_DIR:?explicit retained batch manifest required}"
rtk proxy python3 -B - "$UPKEEP_TRANSFER_DIR" <<'PY'
from pathlib import Path
import hashlib, json, os, re, stat, subprocess, sys
batch = Path(sys.argv[1])
manifest_path = batch / 'manifest.json'
if (not batch.is_absolute() or not batch.is_relative_to(Path.home()) or batch.is_symlink()
        or not batch.is_dir() or batch.stat().st_uid != os.getuid()
        or stat.S_IMODE(batch.stat().st_mode) != 0o700 or manifest_path.is_symlink()
        or not manifest_path.is_file() or manifest_path.stat().st_uid != os.getuid()
        or stat.S_IMODE(manifest_path.stat().st_mode) != 0o600):
    raise SystemExit('owned private batch/manifest required before rollback')
try:
    manifest = json.loads(manifest_path.read_text())
except (OSError, ValueError):
    raise SystemExit('valid manifest required before rollback')
home = Path.home()
if (manifest.get('schema_version') != 1 or manifest.get('home') != str(home)
        or manifest.get('batch') != str(batch) or not re.fullmatch(r'[0-9a-f]{40}', manifest.get('approved_sha', ''))):
    raise SystemExit('manifest identity/schema mismatch')
config_root = Path(manifest['config_root'])
runtime_root = Path(manifest['runtime_root'])
ops = Path(manifest['ops'])
units = config_root / 'systemd/user'
runtime = runtime_root / 'systemd/user'
unit_names = ('disk-headroom-guard.service', 'disk-headroom-guard.timer',
              'ecosystem-native-data.service', 'ecosystem-native-data.timer')
timer_names = ('disk-headroom-guard.timer', 'ecosystem-native-data.timer')
if (not config_root.is_absolute() or not config_root.is_relative_to(home)
        or str(ops) != str(home / '.local/state/native-agent-stack/ops')
        or not runtime_root.is_absolute()
        or (not runtime_root.is_relative_to(home) and runtime_root != Path(f'/run/user/{os.getuid()}'))):
    raise SystemExit('manifest roots outside owned scope')
allowed = {units / name for name in unit_names}
allowed |= {base / 'timers.target.wants' / name for base in (units, runtime) for name in timer_names}
allowed |= {ops / 'disk-headroom-guard.sh', config_root / 'ecosystem-observability/native-data.json'}
def fingerprint(path):
    if path.is_symlink():
        return {'kind': 'link', 'target': os.readlink(path)}
    if not path.exists():
        return {'kind': 'absent'}
    s = path.stat()
    if not stat.S_ISREG(s.st_mode):
        raise SystemExit('needs_owner: managed path changed type')
    return {'kind': 'file', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'mode': stat.S_IMODE(s.st_mode)}
records = manifest.get('paths')
timers = manifest.get('timers')
actions = manifest.get('timer_actions')
if (not isinstance(records, list) or not isinstance(timers, dict) or timers.keys() - set(timer_names)
        or not isinstance(actions, dict) or actions.keys() - timers.keys()):
    raise SystemExit('manifest actions/timers invalid')
seen = set()
restore = []
for record in records:
    path = Path(record.get('path', ''))
    backup = Path(record.get('backup', ''))
    if (path not in allowed or path in seen or record.get('prepared') is not True
            or not backup.is_absolute() or not backup.is_relative_to(batch / 'baseline')
            or any(parent.is_symlink() for parent in path.parents)):
        raise SystemExit('invalid manifest action before rollback')
    seen.add(path)
    before, expected = record.get('before'), record.get('expected')
    if not isinstance(before, dict) or not isinstance(expected, dict):
        raise SystemExit('invalid manifest identity')
    current = fingerprint(path)
    allowed_current = (before, expected)
    if record.get('phase') in ('remove_prepared', 'install_prepared', 'rollback_remove_prepared', 'rollback_copy_prepared'):
        allowed_current += ({'kind': 'absent'},)
    if current not in allowed_current:
        raise SystemExit('needs_owner: operator edit retained before any rollback operation')
    if before.get('kind') != 'absent' and fingerprint(backup) != before:
        raise SystemExit('needs_owner: saved baseline differs')
    if current != before:
        restore.append((path, backup, before))
for name, prior in timers.items():
    if prior.get('ActiveState') not in ('active', 'inactive'):
        raise SystemExit('invalid prior activation')
affected = [name for name, action in actions.items()
            if action.get('stop_prepared') is True or action.get('enable_prepared') is True]
if not affected and not restore:
    print('no recorded path or timer mutation; manager untouched')
    raise SystemExit(0)
stamp = int(subprocess.check_output(['date', '-u', '+%Y%m%d%H%M'], text=True))
if 202610061015 <= stamp < 202610061345 or 202610061930 <= stamp < 202610070010:
    raise SystemExit('pause: paper window; do not kill a running case')
def output(*args):
    return subprocess.check_output(list(args), text=True)
def call(*args):
    subprocess.run(['rtk', 'proxy', *args], check=True)
def reload_gate():
    raw = output('systemctl', '--user', 'show', '*', '--property=Id,NeedDaemonReload')
    for block in raw.strip().split('\n\n'):
        fields = dict(line.split('=', 1) for line in block.splitlines() if '=' in line)
        if fields.get('NeedDaemonReload') == 'yes' and fields.get('Id') not in unit_names:
            raise SystemExit('needs_owner: other loaded unit needs reload')
reload_gate()
for name in unit_names[:1] + unit_names[2:3]:
    active = output('systemctl', '--user', 'show', name, '--property=ActiveState', '--value').strip()
    if active not in ('inactive', 'failed'):
        raise SystemExit('pause: running service case must finish')
for name in affected:
    loaded = output('systemctl', '--user', 'show', name, '--property=LoadState', '--value').strip()
    if loaded == 'loaded':
        call('systemctl', '--user', 'stop', name)
# Recheck after stopping scheduling; do not kill a case that raced the earlier read.
for name in ('disk-headroom-guard.service', 'ecosystem-native-data.service'):
    if output('systemctl', '--user', 'show', name, '--property=ActiveState', '--value').strip() not in ('inactive', 'failed'):
        raise SystemExit('pause: case still running')
for path, backup, before in restore:
    record = next(r for r in records if r['path'] == str(path))
    allowed_current = (before, record['expected'])
    if record.get('phase') in ('remove_prepared', 'install_prepared', 'rollback_remove_prepared', 'rollback_copy_prepared'):
        allowed_current += ({'kind': 'absent'},)
    if fingerprint(path) not in allowed_current:
        raise SystemExit('needs_owner: path changed during rollback')
    record['phase'] = 'rollback_remove_prepared'
    temporary = batch / 'manifest.pending'
    temporary.write_text(json.dumps(manifest, indent=2) + '\n')
    os.chmod(temporary, 0o600)
    temporary.replace(manifest_path)
    call('rm', '-f', '--', str(path))
    if before['kind'] != 'absent':
        record['phase'] = 'rollback_copy_prepared'
        temporary.write_text(json.dumps(manifest, indent=2) + '\n')
        os.chmod(temporary, 0o600)
        temporary.replace(manifest_path)
        call('cp', '-a', '--', str(backup), str(path))
    if fingerprint(path) != before:
        raise SystemExit('restored identity mismatch')
    record['phase'] = 'rollback_complete'
    temporary.write_text(json.dumps(manifest, indent=2) + '\n')
    os.chmod(temporary, 0o600)
    temporary.replace(manifest_path)
reload_gate()
call('systemctl', '--user', 'daemon-reload')
for name in unit_names:
    if output('systemctl', '--user', 'show', name, '--property=ActiveState', '--value').strip() == 'failed':
        call('systemctl', '--user', 'reset-failed', name)
for name in affected:
    prior = timers[name]
    if prior['ActiveState'] == 'active':
        call('systemctl', '--user', 'start', name)
# The live checkout and newly created directories are retained, not recursively deleted.
# They may be reused by another owner; removal needs a separate custody check.
(batch / 'rollback.complete').write_text('captured path identities restored; prior timer activation restored\n')
print('rollback restored only recorded paths; observation state and source checkout retained')
PY
```

Check native is-enabled/is-active against the recorded baseline after restoration.
Retain the batch, source checkout, logs, CSV, private observation state and
receipts. Remove no dashboard, model or dataset. The observed guard run at
05:45:36Z used634GiB free and did not prune; its automated old green gate exited1
and that attempt remains a failure. The co-op's journal/CSV judgment is a separate
manual host observation, not a passing replay of that gate.

## Safe cache pruning

The guard unit selects UV_CACHE_DIR=%h/.cache/uv and UV_LOCK_TIMEOUT=10.
Only the lock wait is bounded; successful prune duration and the source's
unlimited oneshot startup remain unqualified. Without this deviation, uv waits
up to its 300-second default while other uv processes hold shared locks, then
fails; sampling can slip beyond the two-minute interval. A lock timeout records
cache-in-use/deferred and remains nonzero. Never pass --force.

Source: astral-sh/uv@70fe1196a546e49148a73b1c592b2f74c33af80e,
docs/concepts/cache.md:160-164; crates/uv/src/commands/cache_prune.rs:31-43;
crates/uv-fs/src/locked_file.rs:17-28,41-47;
crates/uv-static/src/env_vars.rs:66-69,1539-1543.
The co-op re-stages the changed guard unit/script from the new head; the old
634 GiB run did not qualify the prune branch. No synthetic disk-pressure or
shared-cache prune is part of lane acceptance.
