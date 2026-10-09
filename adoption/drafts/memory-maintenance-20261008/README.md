# Memory maintenance proposals (2026-10-08)

These seven native oneshot services and seven timers are **drafts** for the
[memory-role decision](../../../docs/decisions/2026-10-07-foundation-finalization.md#nativestack2604-memory-roles-and-maintenance-2026-10-08).
They were not installed, enabled or executed. Cadences are proposed operating
choices, not vendor defaults, measured quality improvements or model-use
authorization.

The two ai-memory drafts include `EnvironmentFile=-%h/.config/ai-memory/env`,
matching the live unit's optional additive file reported by the native
`systemctl --user show ai-memory.service --property=EnvironmentFiles` read.
No environment-file content was opened. `%h` is a systemd specifier; proposed
shell commands in the [vendor wiring packets](../../../docs/decisions/memory-adoption-835/README.md)
use `$HOME`. Every client/CLI install and smoke remains OUTSTANDING for the CC.

Each service requires the operator marker
`%h/.config/native-stack/memory-maintenance.approved`, which this PR does not
create. Timers have no catch-up (`Persistent=false`), use UTC and add 15-minute
jitter. Services have a 600-second bound and reduced CPU/I/O priority.

| Unit stem (`native-memory-`) | Proposed cadence | Native operation | Activation prerequisite |
| --- | --- | --- | --- |
| `ai-lint` | Daily 03:15 UTC | `ai-memory lint --dry-run --no-llm` | Resolve exact native project scope and effective server maintenance scheduling; avoid a duplicate built-in lint job |
| `ai-retention-review` | Saturday 03:30 UTC | `ai-memory forget-sweep --dry-run` | Same scope/scheduler review; a preview does not authorize deletion |
| `hindsight-reflect` | Sunday 03:45 UTC | `hindsight memory reflect trading-research ... --budget low --max-tokens 512` | Accepted research bank: separately review this administrative reflection query, install the pinned vendor CLI and approve its model use |
| `hindsight-model-refresh` | Daily 04:00 UTC | `hindsight mental-model refresh trading-research MODEL_ID` | Accepted research bank: select an existing mental model, install the CLI, and use either this administrative timer or native `refresh_cron`/post-consolidation refresh |
| `codegraph-coverage` | Monday 04:15 UTC | Native `check_index_coverage` for registered project `home-apoth-code-native-agent-stack`, scope `docs`, bounded pages | Native project registry confirms the identity; choose relevant paths before activation. This does not rebuild or establish complete coverage |
| `qmd-update` | Daily 02:45 UTC | `qmd --index native-agent-stack-catalog-lex update` | Confirm the named index and collection roots/update hooks, coordinate its one writer, and finish the separate shared-service decision |
| `qmd-cleanup-review` | Saturday 04:30 UTC | `qmd --index native-agent-stack-catalog-lex cleanup --dry-run` | Same index/writer review; preview only |

Every unit invokes a vendor command through `/usr/bin/env`; no maintenance
runner or scheduler is implemented locally. The PATH entries are portable
installation locations and must be reconciled with the host's native install.
The live ai-memory scope is recorded in the decision; another host must substitute
its own exact names. `--data-dir` selects the existing store; these units do not
copy a database or authentication store.

Hindsight's refresh draft additionally requires the operator-owned, non-secret
`%h/.config/native-stack/hindsight-maintenance.env` containing the selected
`HINDSIGHT_MENTAL_MODEL_ID`. No such file is created here. This bank currently
has zero mental models. Refresh CLI success is operation submission; the
operator must observe native operation completion before claiming a successful
refresh. Server-owned provider credentials remain in their native service.
The research client's 15-tool allowlist is unchanged.

The canonical landscape already accepts Hindsight's research-hypothesis and
experiment-record job. The decision proposes WIRE to complete its vendor-native
research-consumer routing; its registrations, service/bank and allowlist remain.
These administrative drafts neither requalify that job nor change client routing.

The ai-memory drafts pass the same explicit native `--config` as the live user
service. The earlier timed-out inventory probes omitted that argument and do not
establish a failure of the configured service. Exact workspace/project identity
must be verified before activation: a misspelled `--workspace` can auto-create a
workspace even when the maintenance action is a preview.

Hindsight model refresh makes model calls and stores a new `reflect_response`.
It is not read-only maintenance. Its draft needs the selected model ID, reviewed
model-use authorization and native operation completion observation. The reflect
draft performs synthesis/model calls without storing a refreshed mental model.

Claude native auto-memory and context-mode use their native session lifecycle;
their weekly operator review proposals are recorded in the decision. Neither
has a fabricated unattended timer. Graphiti is deferred and receives no unit.
Existing ai-memory SessionEnd consolidation and code-graph watcher updates keep
their event-driven ownership; no timer replays sessions or rebuilds the graph.

Sources:

- [akitaonrails/ai-memory v2.6.0](https://github.com/akitaonrails/ai-memory/tree/89bd8ded3c1ab8b769cf99417d038ed0364403c8), native `lint --help`, `forget-sweep --help`, `crates/ai-memory-cli/src/config.rs`, and the vendor `ai-memory-learning-maintenance` skill.
- [vectorize-io/hindsight v0.10.2 CLI](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-cli/src/main.rs#L593) and [mental-model scheduling](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-docs/docs/developer/api/mental-models.mdx#L117).
- [DeusData/codebase-memory-mcp v0.11.0 README](https://github.com/DeusData/codebase-memory-mcp/blob/8972ea69c6ad94b1ef1d4ffbf0a92d78d2db1798/README.md), native CLI tool invocation and coverage inspection.
- [tobi/qmd v2.8.3 README](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/README.md#L1010), native `update` and maintenance help. Collection update hooks may run commands before indexing.
- Installed systemd 259.5; [systemd.service](https://www.freedesktop.org/software/systemd/man/259/systemd.service.html), [systemd.timer](https://www.freedesktop.org/software/systemd/man/259/systemd.timer.html), [systemd.exec](https://www.freedesktop.org/software/systemd/man/259/systemd.exec.html) and [systemd.unit](https://www.freedesktop.org/software/systemd/man/259/systemd.unit.html). Conditions, calendars, native execution and resource limits follow these supported formats.

Validation uses native `systemd-analyze verify` and calendar parsing only. It
does not activate units, read model-ID/authentication files or execute their
maintenance commands. Repository validation and targeted local test modules
remain structural checks. Independent head reads and the explicit landing cue
remain separate.
