# Workstation upkeep jobs

Seven definitions include the original six ports and the missing native-data
collector identified by the Oct8 retirement inventory. Read
[RETIREMENT-20261008.md](RETIREMENT-20261008.md) before the historical apply steps:
it selects only missing functions, preserves the current progress/disk owners,
and carries the current freeze and quiet-window direction.
See [source-map.md](source-map.md) for the native times/hashes, commands and timer
differences, and the [dated decision](../../../docs/decisions/2026-10-06-upkeep-dagu.md)
for the hindsight-ensure not-needed row. The co-op installs and measures them;
authoring/fixture checks do not establish host acceptance.

| Job | Function | Bound |
| --- | --- | --- |
| ecosystem-upkeep | Native Claude opus/max/auto, one qualified upkeep cycle | 48 min overall; 45 min Claude |
| ecosystem-research-progress | Two source-derived public checkpoint checks, 30 s apart, Loki 21300 | 75 s; 20 s per check |
| stack-currency | Maintained due-file checks | 15 min |
| token-report-refresh | Maintained native lifetime refresh with private config pointer | 15 min |
| host-requests-workstation | Read-only GitHub polling and Alertmanager notices | 2 min |
| native-agent-stack-sync | Main pin, live clone, scoped QMD text update | 6 min |
| ecosystem-native-data | Existing bounded native-data collector and Loki publish with a private config pointer | 90 s |

All fields use the [Dagu 2.18.2 embedded schema](https://github.com/dagucloud/dagu/blob/5ca5c59f6b67734c9f0ae186bd59f5e0bb5846f4/internal/cmn/schema/dag.schema.json):
description, schedule, catchup_window, overlap_policy, hist_retention_days,
timeout_sec, working_dir, env, preconditions, and steps with run, depends,
with.shell and continue_on.failure. The ignored local-queue max_active_runs is
omitted. Catch-up does not promise a universal process lock.

## Prerequisites and native definition check

Apply the Phase 1 environment/clone jobs first. Main/live clones, native CLI
sign-ins and the QMD native-agent-stack-catalog index must be ready. No GPU
embedding command, credential transfer or server/auth change is part of this
procedure.

The dashboards owner supplies its reviewed emitter with --loki-url; it retains
progress.py and its tests. This branch changes neither. Until reviewed code is
on main, install the owner's committed emitter copy in the owned runtime prefix.
Never substitute an uncommitted builder file.

Dagu [validate](https://github.com/dagucloud/dagu/blob/5ca5c59f6b67734c9f0ae186bd59f5e0bb5846f4/internal/cmd/validate.go#L75-L84)
uses WithoutEval(), so this check does not execute the jobs:

```bash
P1_CHECK_HOME="${XDG_CACHE_HOME:-$HOME/.cache}/ns2604-supersession/dagu-validation"
mkdir -p "$P1_CHECK_HOME"
printf '{}\n' > "$P1_CHECK_HOME/config.yaml"
for spec in adoption/templates/dagu/*.yaml; do
  nice -n 19 dagu validate --config "$P1_CHECK_HOME/config.yaml" --dagu-home "$P1_CHECK_HOME" "$spec"
done
bash -n adoption/templates/dagu/helpers/main-pin.sh
bash -n adoption/templates/dagu/helpers/live-clone-sync.sh
bash -n adoption/templates/dagu/helpers/heavy-window-check.sh
```

## Co-op apply, one GREEN run each, then read-back

Set P1_HEAD/P1_EMITTER_HEAD from the exact reviewed PR heads. The source
checkouts are read-only in this apply. Runtime paths are portable and stable.
Run one heavy command at a time, nice 19. On 2026-10-06 heavy phases must stay
outside 10:35-13:45Z and 19:50-00:10Z on 2026-10-07, including their maximum duration. Upkeep
needs a 48-minute margin.

Stage definitions outside Dagu's watched directory for the first invocations;
activate schedules only after all six invocations pass. Only the selected
definitions, owned runtime helpers and upkeep task are changed.

```bash
P1_SOURCE="$HOME/code/native-agent-stack-ns2604-p1-dagu"
P1_EMITTER_SOURCE="$HOME/code/native-agent-stack-ns2604-dashboards"
test "$(git -C "$P1_SOURCE" rev-parse HEAD)" = "$P1_HEAD"
test "$(git -C "$P1_EMITTER_SOURCE" rev-parse HEAD)" = "$P1_EMITTER_HEAD"
git -C "$P1_SOURCE" diff --quiet
git -C "$P1_SOURCE" diff --cached --quiet
git -C "$P1_EMITTER_SOURCE" diff --quiet -- observability/grand-dashboard/progress.py
git -C "$P1_EMITTER_SOURCE" diff --cached --quiet -- observability/grand-dashboard/progress.py

P1_STAGE="$HOME/.cache/ns2604-supersession/apply-$(date -u +%Y%m%dT%H%M%SZ)"
P1_RUNTIME="$HOME/.local/lib/native-agent-stack/dagu-upkeep"
P1_DAGS="$HOME/.dagu/dags"
P1_TASK="$HOME/.config/native-agent-stack/upkeep-task.md"
umask 0077
mkdir -p "$P1_STAGE/dags" "$P1_STAGE/backup/dags"
if test -d "$P1_RUNTIME"; then
  cp -a "$P1_RUNTIME" "$P1_STAGE/backup/runtime"
else
  touch "$P1_STAGE/backup/runtime.absent"
fi
if test -f "$P1_TASK"; then
  cp -a "$P1_TASK" "$P1_STAGE/backup/upkeep-task.md"
else
  touch "$P1_STAGE/backup/upkeep-task.absent"
fi
mkdir -p "$P1_RUNTIME/scripts" "$P1_DAGS"
for job in ecosystem-upkeep ecosystem-research-progress stack-currency token-report-refresh host-requests-workstation native-agent-stack-sync; do
  if test -f "$P1_DAGS/$job.yaml"; then
    cp -a "$P1_DAGS/$job.yaml" "$P1_STAGE/backup/dags/$job.yaml"
  else
    touch "$P1_STAGE/backup/dags/$job.absent"
  fi
  install -m 600 "$P1_SOURCE/adoption/templates/dagu/$job.yaml" "$P1_STAGE/dags/$job.yaml"
done
install -m 600 "$P1_SOURCE/adoption/templates/dagu/helpers/main-pin.sh" "$P1_RUNTIME/main-pin.sh"
install -m 600 "$P1_SOURCE/adoption/templates/dagu/helpers/live-clone-sync.sh" "$P1_RUNTIME/live-clone-sync.sh"
install -m 600 "$P1_SOURCE/adoption/templates/dagu/helpers/heavy-window-check.sh" "$P1_RUNTIME/heavy-window-check.sh"
install -m 600 "$P1_SOURCE/scripts/host_requests.py" "$P1_RUNTIME/scripts/host_requests.py"
install -m 600 "$P1_SOURCE/scripts/validate.py" "$P1_RUNTIME/scripts/validate.py"
install -m 600 "$P1_EMITTER_SOURCE/observability/grand-dashboard/progress.py" "$P1_RUNTIME/progress.py"
mkdir -p "$(dirname "$P1_TASK")"
install -m 600 "$P1_SOURCE/adoption/templates/dagu/upkeep-task.md" "$P1_TASK"
install -d -m 700 "$HOME/.local/state/native-agent-stack/host-requests"
python3 "$P1_RUNTIME/progress.py" --help
python3 "$P1_RUNTIME/scripts/host_requests.py" poll --help
```

The runtime host-request copy imports its reviewed validate.py privacy patterns;
--stack-root selects the live repository's current public roles. Its native
Alertmanager mode preserves the existing ntfy option.

Initialize token-report only when its documented config is absent. The
supported initializer refuses overwrite. An existing config needs its owner's
clone verification; no credential or native sign-in store is inspected.

```bash
P1_REPORT_STATE="$HOME/.local/state/native-token-report"
if ! test -f "$P1_REPORT_STATE/config.json"; then
  mkdir -p "$P1_REPORT_STATE"
  nice -n 19 python3 "$HOME/code/native-agent-stack-live/tools/token-report/token_manifest.py" init-config \
    --config "$P1_REPORT_STATE/config.json" --state-dir "$P1_REPORT_STATE" \
    --project "$HOME/code/native-agent-stack" --rtk rtk --headroom headroom \
    --jcodemunch jcodemunch-mcp --mcporter mcporter
fi
```

Keep P1_STAGE in the co-op receipt. Use the scheduler's Dagu home/config for
both invocation and read-back. Run IDs are unique; retain actual exits.
Do not activate schedules after a failed run or missing prerequisite.

```bash
for job in native-agent-stack-sync ecosystem-research-progress stack-currency token-report-refresh host-requests-workstation ecosystem-upkeep; do
  run_id="p1-$job-$(date -u +%Y%m%dT%H%M%SZ)"
  printf '%s\n' "$run_id" > "$P1_STAGE/$job.run-id"
  date -u +%Y-%m-%dT%H:%M:%SZ
  nice -n 19 dagu start --run-id "$run_id" "$P1_STAGE/dags/$job.yaml" || exit
done
for job in ecosystem-upkeep ecosystem-research-progress stack-currency token-report-refresh host-requests-workstation native-agent-stack-sync; do
  install -m 600 "$P1_STAGE/dags/$job.yaml" "$P1_DAGS/$job.yaml"
  run_id=$(cat "$P1_STAGE/$job.run-id")
  date -u +%Y-%m-%dT%H:%M:%SZ
  dagu status --run-id "$run_id" "$job"
  dagu history "$job" --run-id "$run_id" --format json --limit 10
done
```

[History](https://github.com/dagucloud/dagu/blob/5ca5c59f6b67734c9f0ae186bd59f5e0bb5846f4/internal/cmd/history.go#L568-L602)
is a JSON array; verify exact name/dagRunId and status=succeeded, not merely
a passing status-query exit or partial run-ID match. Retain bounded native
start/end/status fields, not raw model output or configuration.

Also verify expected outputs: both sync HEADs equal their origin/main and QMD
update passed; both progress checks used the new endpoint/scoped cache; due-file,
manifest and poll timestamps are fresh; upkeep status.json has its actual
decision. A dirty-main skip does not prove advancement. Polling remains
best-effort for notices, so a passing poll does not prove delivery.

For the co-op's notice acceptance, submit a bounded integration alert with the
reviewed sender and verify that it appears in the native API/amtool. Do not use
a Telegram message or inspect its receiver secrets as the oracle.
[Alertmanager's pinned API schema](https://github.com/prometheus/alertmanager/blob/73c6bfe7393929211294c1954f30d8ed78e4d0ad/api/v2/openapi.yaml)
defines the JSON contract; labels follow the command center's value-free unit.

```bash
date -u +%Y-%m-%dT%H:%M:%SZ
python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import host_requests; host_requests.send_alertmanager_notice("http://127.0.0.1:21093/api/v2/alerts", "host-request transport integration check")' "$P1_RUNTIME/scripts"
curl --fail --silent --show-error --noproxy '*' --get \
  --data-urlencode 'filter=alertname="NativeStackHostRequest"' http://127.0.0.1:21093/api/v2/alerts
```

Retain only matching public labels/state/time in the receipt.

## Rollback for each job

Coordinate any active run, then restore its saved definition or remove the
new definition where JOB.absent records no predecessor. No global scheduler
restart is needed. Use the exact paths retained by the apply receipt.

```bash
for job in ecosystem-upkeep ecosystem-research-progress stack-currency token-report-refresh host-requests-workstation native-agent-stack-sync; do
  if test -f "$P1_STAGE/backup/dags/$job.absent"; then
    rm -f "$P1_DAGS/$job.yaml"
  else
    install -m 600 "$P1_STAGE/backup/dags/$job.yaml" "$P1_DAGS/$job.yaml"
  fi
done
if test -d "$P1_STAGE/backup/runtime"; then
  cp -a "$P1_STAGE/backup/runtime/." "$P1_RUNTIME/"
fi
if test -f "$P1_STAGE/backup/upkeep-task.absent"; then
  rm -f "$P1_TASK"
else
  install -m 600 "$P1_STAGE/backup/upkeep-task.md" "$P1_TASK"
fi
```

Keep a newly installed runtime prefix for inspection if there was no predecessor;
removing its six definitions removes scheduled consumers. Keep data/run history,
poll state, counters, token config, indexes and branches. Definition rollback
does not undo a real adoption or Git update: reconcile those actual effects
from upkeep status and the native recipe/retained refs.
