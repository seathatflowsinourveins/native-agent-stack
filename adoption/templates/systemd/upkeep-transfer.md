# Apply the two upkeep timers on NativeStack2604

The co-op executes this runbook after the repository checks pass, using a
persistent checkout containing the approved revision. The lane executes none of
these host changes. This transfers the four templates and the guard script; it
creates no dashboard or new default install-plan row. Source hashes, alternatives
and native contracts are in the
[decision](../../../docs/decisions/2026-10-06-2604-upkeep-timer-transfer.md).

Run outside the paper windows and at a quiet point. Stop for unknown ownership,
masked units, unreviewed drop-ins, or paths containing credentials. Never copy a
credential store. The private observer config must already select
`http://127.0.0.1:21300/loki/api/v1/push`, reviewed report scopes, native binary and
project paths, and an owned nonsymlink state directory of mode 0700. Verify Node
22 or later and the existing Loki listener. A successful publish does not prove
every native tool is healthy: retain unknown and stale counts.

## Capture and render

Set these three non-secret paths to reviewed absolute paths. Do not use the
temporary lane worktree as the lasting repository. Keep the backup outside /tmp.

```sh
timer_repo=/absolute/persistent/approved/checkout
timer_config="$HOME/.config/ecosystem-observability/native-data.json"
timer_node=/absolute/directory/containing/node
timer_units="$HOME/.config/systemd/user"
timer_ops="$HOME/.local/state/native-agent-stack/ops"
timer_runtime="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/systemd/user"
timer_backup="$HOME/.local/state/native-agent-stack/upkeep-transfer-$(date -u +%Y%m%dT%H%M%SZ)"
umask 077
mkdir -p "$timer_backup/files" "$timer_backup/rendered" "$timer_backup/links/config" "$timer_backup/links/runtime"
```

Capture each existing regular file or symlink without dereferencing it, including
a dangling symlink; record absence otherwise. Review custody before overwriting.
Neither the logs nor the private config are overwritten by this runbook.

```sh
for name in disk-headroom-guard.service disk-headroom-guard.timer ecosystem-native-data.service ecosystem-native-data.timer; do
  path="$timer_units/$name"
  if [ -e "$path" ] || [ -L "$path" ]; then
    rtk proxy cp -a -- "$path" "$timer_backup/files/$name" || exit 1
    printf '%s\n' "$name" >> "$timer_backup/present"
  fi
  rtk systemctl --user show "$name" --property=FragmentPath,DropInPaths,ActiveState,SubState > "$timer_backup/$name.before" || exit 1
done
if [ -e "$timer_ops/disk-headroom-guard.sh" ] || [ -L "$timer_ops/disk-headroom-guard.sh" ]; then
  rtk proxy cp -a -- "$timer_ops/disk-headroom-guard.sh" "$timer_backup/files/disk-headroom-guard.sh" || exit 1
  printf '%s\n' disk-headroom-guard.sh >> "$timer_backup/present"
fi
for name in disk-headroom-guard.timer ecosystem-native-data.timer; do
  timer_rc=0
  rtk systemctl --user is-enabled "$name" > "$timer_backup/$name.enabled" || timer_rc=$?
  printf '%s\n' "$timer_rc" > "$timer_backup/$name.enabled.rc"
  rtk systemctl --user show "$name" --property=ActiveState --value > "$timer_backup/$name.active" || exit 1
done
for scope in config runtime; do
  case "$scope" in config) base="$timer_units" ;; runtime) base="$timer_runtime" ;; esac
  for name in disk-headroom-guard.timer ecosystem-native-data.timer; do
    link="$base/timers.target.wants/$name"
    if [ -L "$link" ]; then
      rtk proxy cp -a -- "$link" "$timer_backup/links/$scope/$name" || exit 1
    elif [ -e "$link" ]; then
      printf 'needs_owner: expected enablement link is a regular path\n' >&2; exit 1
    fi
  done
done
```

Record the exit codes of these reads. Missing or disabled timers can make
`is-enabled` nonzero. Proceed only after reviewing the baseline: timer enablement
must be enabled, enabled-runtime, disabled or not-found, and activation must be
active or inactive. Other states need the owner. Require the two services to be
idle before changing their executable or unit. The user manager must use the
recorded config/runtime roots, with nonsymlink parent directories. Capture the
two ordinary timers.target.wants links in each root, including dangling links;
other preexisting aliases are left untouched. This transfer's templates specify
only WantedBy=timers.target. Rollback restores the captured links directly: native
disable is deliberately avoided because it also removes unrelated manual links.
Preserve existing directory
ownership/mode; create absent owned unit and ops directories only.

Render by substituting the three existing parameters, with the same restrictions
as the README. This is an operator command, not another installed renderer.
Quotes support spaces; they do not suppress systemd dollar/specifier expansion.

```sh
rtk proxy python3 -B - "$timer_repo" "$timer_config" "$timer_node" "$timer_backup/rendered" <<'PY'
from pathlib import Path
import sys
repo, config, node, output = sys.argv[1:]
values = {"@REPOSITORY@": repo, "@PRIVATE_CONFIG@": config, "@NODE_DIRECTORY@": node}
for token, value in values.items():
    if not Path(value).is_absolute() or any(c in value for c in '\x00\n\r"\\$%'):
        raise SystemExit(f"unsupported parameter characters: {token}")
if ':' in node:
    raise SystemExit("Node directory must not contain a PATH separator")
if not (Path(repo) / 'observability/native-data/snapshot.py').is_file():
    raise SystemExit("approved observer is missing")
if not Path(config).is_file() or not (Path(node) / 'node').is_file():
    raise SystemExit("reviewed private config or Node executable is missing")
for name in ('disk-headroom-guard.service', 'disk-headroom-guard.timer',
             'ecosystem-native-data.service', 'ecosystem-native-data.timer'):
    text = (Path(repo) / 'adoption/templates/systemd' / name).read_text()
    for token, value in values.items():
        text = text.replace(token, value)
    if any(token in text for token in values):
        raise SystemExit("unresolved template parameter")
    (Path(output) / name).write_text(text)
PY
```

## Install and green runs

First stop the two timers, retaining their prior activation for rollback. Install
the guard before verification: systemd's parser checks that ExecStart exists.
Verify all rendered units with the strict native warning gate. If verification
fails, restore the guard and prior timer activation using the rollback below;
do not install the candidate units.

```sh
for name in disk-headroom-guard.timer ecosystem-native-data.timer; do
  prior_active=$(rtk proxy cat "$timer_backup/$name.active")
  if [ "$prior_active" = active ]; then
    rtk systemctl --user stop "$name" || exit 1
  fi
done
if [ ! -e "$timer_ops" ] && [ ! -L "$timer_ops" ]; then
  rtk proxy install -d -m 0700 "$timer_ops" || exit 1
fi
rtk proxy rm -f -- "$timer_ops/disk-headroom-guard.sh" || exit 1
rtk proxy install -m 0755 "$timer_repo/tools/maintenance/disk-headroom-guard.sh" "$timer_ops/disk-headroom-guard.sh" || exit 1
rtk proxy systemd-analyze --user --man=no --generators=no --recursive-errors=no verify "$timer_backup/rendered/disk-headroom-guard.service" "$timer_backup/rendered/disk-headroom-guard.timer" "$timer_backup/rendered/ecosystem-native-data.service" "$timer_backup/rendered/ecosystem-native-data.timer" || exit 1
if [ ! -e "$timer_units" ] && [ ! -L "$timer_units" ]; then
  rtk proxy install -d -m 0700 "$timer_units" || exit 1
fi
for name in disk-headroom-guard.service disk-headroom-guard.timer ecosystem-native-data.service ecosystem-native-data.timer; do
  rtk proxy rm -f -- "$timer_units/$name" || exit 1
  rtk proxy install -m 0600 "$timer_backup/rendered/$name" "$timer_units/$name" || exit 1
done
rtk systemctl --user daemon-reload || exit 1
for name in disk-headroom-guard.service ecosystem-native-data.service; do
  rtk proxy date -u +%FT%TZ > "$timer_backup/$name.run-start" || exit 1
  rtk systemctl --user start "$name" || exit 1
  timer_rc=0
  rtk systemctl --user status "$name" --no-pager > "$timer_backup/$name.status" || timer_rc=$?
  printf '%s\n' "$timer_rc" > "$timer_backup/$name.status.rc"
  [ "$timer_rc" = 0 ] || [ "$timer_rc" = 3 ] || exit 1
  rtk systemctl --user show "$name" --property=Result,ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp,FragmentPath,DropInPaths > "$timer_backup/$name.after" || exit 1
done
rtk systemctl --user enable --now disk-headroom-guard.timer ecosystem-native-data.timer || exit 1
```

Run in a shell that checks every command's exit status; stop and roll back on an
unexpected failure. A successful oneshot normally ends inactive/dead, so status
can return 3. Do not discard that result or confuse it with a failed synchronous
start. Each green run needs start exit 0, Result=success, ExecMainStatus=0 and an
execution timestamp at or after its recorded run-start. Confirm the loaded
fragment and drop-ins match the reviewed candidate. The guard retains the
source's unlimited timeout; wait for its prune rather than launching another.

## Read-back

```sh
rtk systemctl --user is-enabled disk-headroom-guard.timer ecosystem-native-data.timer
rtk systemctl --user is-active disk-headroom-guard.timer ecosystem-native-data.timer
rtk systemctl --user show disk-headroom-guard.timer ecosystem-native-data.timer --property=Unit,LastTriggerUSec,NextElapseUSecMonotonic,TimersMonotonic,AccuracyUSec
rtk proxy sha256sum "$timer_units/disk-headroom-guard.service" "$timer_units/disk-headroom-guard.timer" "$timer_units/ecosystem-native-data.service" "$timer_units/ecosystem-native-data.timer" "$timer_ops/disk-headroom-guard.sh"
rtk proxy ss -ltnH 'sport = :21300'
rtk proxy tail -n 2 "$timer_ops/disk-headroom.csv"
rtk proxy journalctl --user -u ecosystem-native-data.service --since "$(rtk proxy cat "$timer_backup/ecosystem-native-data.service.run-start")" --no-pager -o cat > "$timer_backup/native-data.journal"
rtk proxy python3 -B - "$timer_backup/native-data.journal" "$timer_backup/ecosystem-native-data.service.run-start" <<'PY'
from datetime import datetime
from pathlib import Path
import json, sys
started = datetime.fromisoformat(Path(sys.argv[2]).read_text().strip().replace('Z', '+00:00')).timestamp()
summaries = []
for line in Path(sys.argv[1]).read_text().splitlines():
    try:
        item = json.loads(line)
    except ValueError:
        continue
    if isinstance(item, dict) and 'loki_http_status' in item:
        summaries.append(item)
if not summaries:
    raise SystemExit('no retained publication summary')
item = summaries[-1]
if (item.get('observed_unix', 0) < started or item.get('loki_http_status') != 204
        or item.get('publish_requested') is not True or item.get('publish_error')):
    raise SystemExit('fresh Loki publication failed')
print(json.dumps({key: item[key] for key in ('observed_unix', 'unknown_count',
      'stale_count', 'snapshot_sha256', 'loki_http_status')}, sort_keys=True))
PY
```

Retain actual exit codes and sanitized outputs. Require both timers enabled and
active with next triggers. Check the observer's fresh snapshot generation in its
reviewed private state directory, service stdout/journal publication result,
unknown_count and stale_count. The journal summary records the observer's returned
HTTP status; it is not an independent server-side ingestion observation. No
command here prints private configuration or reads
credential stores. Host acceptance stays pending until the co-op returns these
records. Source hashes and passing repository fixtures alone do not close it.

## Rollback

Stop the new scheduling and jobs. Restore each prior path with cp -a, or remove
only a path the apply created when it was absent. This preserves earlier symlinks
and bytes. The same rollback restores the guard if native verification failed.

```sh
for name in disk-headroom-guard.timer ecosystem-native-data.timer disk-headroom-guard.service ecosystem-native-data.service; do
  loaded=$(rtk systemctl --user show "$name" --property=LoadState --value) || exit 1
  if [ "$loaded" = loaded ]; then rtk systemctl --user stop "$name" || exit 1; fi
done
for name in disk-headroom-guard.service disk-headroom-guard.timer ecosystem-native-data.service ecosystem-native-data.timer; do
  rtk proxy rm -f -- "$timer_units/$name" || exit 1
  if [ -e "$timer_backup/files/$name" ] || [ -L "$timer_backup/files/$name" ]; then
    rtk proxy cp -a -- "$timer_backup/files/$name" "$timer_units/$name" || exit 1
  fi
done
rtk proxy rm -f -- "$timer_ops/disk-headroom-guard.sh" || exit 1
if [ -e "$timer_backup/files/disk-headroom-guard.sh" ] || [ -L "$timer_backup/files/disk-headroom-guard.sh" ]; then
  rtk proxy cp -a -- "$timer_backup/files/disk-headroom-guard.sh" "$timer_ops/disk-headroom-guard.sh" || exit 1
fi
for scope in config runtime; do
  case "$scope" in config) base="$timer_units" ;; runtime) base="$timer_runtime" ;; esac
  for name in disk-headroom-guard.timer ecosystem-native-data.timer; do
    link="$base/timers.target.wants/$name"
    if [ -L "$link" ]; then
      rtk proxy rm -- "$link" || exit 1
    elif [ -e "$link" ]; then
      printf 'needs_owner: enablement path changed type\n' >&2; exit 1
    fi
    if [ -L "$timer_backup/links/$scope/$name" ]; then
      rtk proxy cp -a -- "$timer_backup/links/$scope/$name" "$link" || exit 1
    fi
  done
done
rtk systemctl --user daemon-reload || exit 1
for name in disk-headroom-guard.timer ecosystem-native-data.timer; do
  prior_active=$(rtk proxy cat "$timer_backup/$name.active")
  if [ "$prior_active" = active ]; then rtk systemctl --user start "$name" || exit 1; fi
done
```

Record restoration results and compare to the saved baseline. Retain backups,
logs, CSV, private observation state and receipts. Remove no dashboard or model
data; the wider observer README's dashboard-removal recipe is outside this
transfer. Directory cleanup is optional only for an empty directory created by
this apply, after the owner confirms custody.
