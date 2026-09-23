# Native research workflow hosting

**Latest:** [Cited research runtime](../research-runtime/README.md) adds a fresh
two-step native Dagu packet/Parquet acceptance and a standalone Claude Opus 5
report with reconciled telemetry. The paired Astra → Claude recipe is validated
but allowance-blocked. [Native restic acceptance](backup/README.md) demonstrates
encrypted backup and byte-identical restore of 22 selected public reference files.
Neither adds a scheduled broker service or off-host durability.

Dagu 2.16.6 now hosts local research run history on loopback port 18525. Its
upstream CLI completed the three-step [workflow](research-evidence.yaml): DuckDB
summarized six LEAN simulated events into three orders, then both evidence
validators passed. The native history retained successful, failed and cancelled
runs after a service restart. This is local research hosting, not broker recovery
or a hosted autonomous trading system.

The pinned Linux amd64 release archive matched the publisher's SHA-256:
`06c3ed951fb58408313b1db25bc9f90ff2f427cbdbe68aaff55cd5465c167717`.
The [receipt](receipt.json) retains the initial schema/environment failures and
the corrected run. Dagu step IDs require underscores; execution requires explicit
environment passthrough in this version. No model inference was needed.

## Native commands

Set `DAGU`, `RESEARCH_HOME`, `STACK_REPO`, `SDK_ENV`, `LEAN_EVENTS` and a fresh
`RESEARCH_OUTPUT` directory to your own installed paths. The environment names are
explicitly allowed in [config.yaml.example](config.yaml.example). Install that
configuration privately with mode 0600. Its upstream `auth.mode: none` serves a
passwordless dashboard on `127.0.0.1` only, with DAG write/run permissions disabled.
Do not expose this local mode through a network listener or tunnel. The release contains the binary,
license and current workflow schema. No Docker or cloud account is required.

```sh
gh release download v2.16.6 --repo dagucloud/dagu \
  --pattern dagu_2.16.6_linux_amd64.tar.gz --pattern checksums.txt
sha256sum dagu_2.16.6_linux_amd64.tar.gz
awk '$2 == "dagu_2.16.6_linux_amd64.tar.gz"' checksums.txt | sha256sum --check --strict
"$DAGU" version
mkdir -p "$RESEARCH_OUTPUT"
env -i HOME="$HOME" PATH=/usr/bin:/bin \
  STACK_REPO="$STACK_REPO" SDK_ENV="$SDK_ENV" \
  LEAN_EVENTS="$LEAN_EVENTS" RESEARCH_OUTPUT="$RESEARCH_OUTPUT" \
  "$DAGU" start --context local --dagu-home "$RESEARCH_HOME" \
  --run-id "$RUN_ID" "$STACK_REPO/blueprints/us-equities/hosting/research-evidence.yaml"
"$DAGU" history --context local --dagu-home "$RESEARCH_HOME" --format json
```

For a new host, adapt the binary/home paths in the example user unit, install it
as `~/.config/systemd/user/dagu-equities.service`, and then run:

```sh
systemctl --user daemon-reload
systemctl --user enable --now dagu-equities.service
systemctl --user restart dagu-equities.service
"$DAGU" history --context local --dagu-home "$RESEARCH_HOME" --format json
```

Choose a new `RUN_ID` and output directory for each run. The summarizer refuses
to overwrite an existing Parquet. Native `dagu stop --run-id ... <dag-name>`
cancelled an intentionally long local step; `history` reported `aborted` even
though that cancelled CLI process returned zero. Consumers must inspect native
status, not only process exit codes. A separate exit-23 fixture recorded `failed`
and aborted its dependent step.

## Service boundary

The installed [user service](dagu-equities.service.example) runs `dagu server`,
not the scheduler, with a minimal inherited environment and no provider or broker
credentials. It is enabled for future user-service sessions. The current local
dashboard uses upstream `auth.mode: none`: anonymous API reads return 200 without
a Basic-auth challenge. The previous Basic mode returned 401 and repeatedly
prompted the browser. Remove its `auth.basic` subsection when changing modes:
upstream config validation rejects an `auth.basic` block under `none`, and the
server refuses to start (re-observed on 2.16.6 on 2026-09-23). Basic headers on
requests are a separate matter: under `none` they are ignored. On 2026-09-23 the
running service served `authMode: "none"` and answered 200 to both an anonymous
and a dummy-Basic GET of `/api/v1/dags`, while loopback control instances of the
same binary returned 401 anonymous under `basic`; that
[dated receipt](../../../evidence/artifacts/gap-wave2-20260923/us-equities__data-quality-orchestration/2-dashboard-auth-mode.json)
supersedes the 2026-09-19 basic-auth status codes in [receipt.json](receipt.json).

DAG execution and DAG/wiki writes remain disabled by `run_dags: false` and
`write_dags: false`. These are not blanket read-only controls: base configuration,
views and managed-secret administration use separate role checks and remain
available to trusted local users without authentication. Keep this configuration
on loopback. Use upstream builtin/OIDC authentication for access beyond this PC.
Manual native CLI commands remain the workflow execution lane. Private
configuration and history are stored beneath the user's local application data.

`systemctl --user disable --now dagu-equities.service` stops and disables it
without deleting evidence. The service restarts on process failure; the accepted
restart check establishes history persistence, not resumption of in-flight work.
Windows/WSL shutdown stops this host. No availability guarantee, remote access,
automatic schedule, cloud deployment, recurring model dispatch or broker order
writer is implied. Same-user host commands are not a security sandbox.

Upstream: [release](https://github.com/dagucloud/dagu/releases/tag/v2.16.6),
[pinned schema](https://github.com/dagucloud/dagu/blob/v2.16.6/README_SCHEMA.md),
[native CLI](https://docs.dagu.sh/getting-started/cli),
[systemd deployment](https://docs.dagu.sh/server-admin/deployment/systemd).
