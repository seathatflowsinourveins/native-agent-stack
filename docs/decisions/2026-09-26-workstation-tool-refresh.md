# Decision: workstation tool refresh, second round (2026-09-26)

**Decided by:** a worker session of the workstation lane on host `nativestack-5975wx-20260925`,
continuing the [2026-09-25 refresh](2026-09-25-workstation-sota-refresh.md) with the same rule:
a newer release replaces an accepted version only after a clean install into a fresh prefix
passes a discriminating acceptance on this host, matched against the installed version. A
release being newer is not evidence. A review round of the refresh coordinator (Claude Opus
and GPT-6 Astra reviewers) reported two findings: the Codex rollback ignored the background
server that 0.157.x starts, and the Prometheus switch script did not gate the link change on
its checks. Both are repaired below; the repair has not been re-reviewed.

**Scope:** MCP Inspector, Prometheus and the Codex CLI on this host. The landscape winner pins
in `catalogs/landscape/foundation.json` do not change (they come from the sealed 2026-09-22
layer-verdict packets), so receipts at the new versions stay unbound until a verdict wave
re-records those layers. Nothing here is macOS evidence.

## Summary

| Unit | Decision | Version after this record | Evidence of record |
| --- | --- | --- | --- |
| MCP Inspector | Qualified and switched | 2.8.0 | [`mcp-inspector-280-qualification-20260926.json`](../../evidence/receipts/mcp-inspector-280-qualification-20260926.json) |
| Prometheus | Qualified and switched (service restarted) | 3.15.0 | [`prometheus-3150-qualification-20260926.json`](../../evidence/receipts/prometheus-3150-qualification-20260926.json) |
| Codex CLI | Qualified and staged; switch after the running sweep | 0.155.1 (0.157.1 staged) | [`codex-01571-qualification-20260926.json`](../../evidence/receipts/codex-01571-qualification-20260926.json) |

## MCP Inspector 2.7.0 to 2.8.0

**Decision.** 2.8.0 serves `bin/mcp-inspector`; 2.7.0 stays installed for rollback.

**Evidence.** [Release 2.8.0](https://github.com/modelcontextprotocol/inspector/releases/tag/2.8.0)
(tag commit `1e31c78f`). [PR #2390](https://github.com/modelcontextprotocol/inspector/pull/2390)
replaced `!!process.env.DANGEROUSLY_OMIT_AUTH` with a parser that accepts only `true` or `1`.
In a sandbox with a private network, the 2.7.0 web server served `/api/config` without its
token when the variable was `false`, `0` or `yes`; 2.8.0 answered 401. Fifteen gated CLI
steps (stdio and streamable HTTP against a scratch QMD server) passed on both versions with
identical outputs, and the launcher file is byte-identical. The tarball matched npm
`dist.integrity` and its SLSA provenance names the tag commit.

**Alternatives.** Keep 2.7.0: the recipes use only `--cli`, and this host never sets the
variable, so the fix changes no live exposure here; but 2.8.0 costs nothing measurable on the
paths the stack uses and removes a fail-open parse.

**Overturn when.** A later release regresses a CLI call the recipes use, an advisory lands
against 2.8.0, or a verdict wave selects another inspector. 2.8.0 also moves its license
statement to an MIT-to-Apache-2.0 transition (`SEE LICENSE IN LICENSE`); a licensing
constraint would reopen the choice.

## Prometheus 3.14.0 to 3.15.0

**Decision.** `ecosystem-prometheus.service` runs 3.15.0 (restarted 2026-09-26T04:56:49Z);
3.14.0 stays installed for rollback. `observability/backends/pins.json` names 3.15.0.

**Evidence.** [Release v3.15.0](https://github.com/prometheus/prometheus/releases/tag/v3.15.0)
(tag commit `5241a27f`): about 50 fixes, many in TSDB and PromQL; `--log.level` is deprecated
(the unit does not use it); XOR2 chunks and OM 2.0 scraping are opt-in, and the default scrape
protocols are unchanged. The archive matched the release `sha256sums.txt`. On copies of the
live TSDB, 3.14.0 and 3.15.0 side by side gave the same targets, rules and six-hour history,
and 3.14.0 reopened the data 3.15.0 wrote. After the switch the history before the restart
read back identical, and the firing alerts were restored without a new notification.

**Procedure.** The cutover script (`switch.py`, kept as run) logged its verify, reload and
restart exit codes and its post-switch comparisons but repointed the `bin/` links regardless;
here all of them had passed first. Its replacement `switch_gated.py` moves the links only after
every gate passes and otherwise restores the previous unit, with `reset-failed` before the
restart because a crash-looping server exhausts the unit's start limit. On a scratch unit with
the live unit's restart settings it switched to 3.15.0 and back, and restored 3.14.0 without
moving the links when `daemon-reload` failed, when it silently did not reload, when the new
server could not start, and when the restarted server still reported 3.14.0. It has not run
against the production unit.

**Alternatives.** Keep 3.14.0 (no defect of it is known to affect this host, but the TSDB
fixes cover data-loss paths on the head and WAL); wait for 3.15.1 (no patch release existed
at switch time).

**Overturn when.** 3.15.0 shows a compaction, WAL or rule-evaluation fault here, a 3.15.x
patch fixes a defect that matters to this host, or a verdict wave selects another store.
A rollback after 3.15.0 has compacted its own blocks is untested.

## Codex CLI 0.155.1 to 0.157.1 (staged)

**Decision.** 0.157.1 is installed in `tools/codex-0.157.1` and qualified without a model
call; `bin/codex` stays on 0.155.1 while the sweep's GPT-6 lanes run. The receipt holds the
switch, probe and rollback commands for the coordinator: the switch turns the background
server's automatic start off before any interactive 0.157.1 launch, and the rollback stops
such a server and its updater loop before relinking. Pins move only after the switch.

**Evidence.** [Release rust-v0.157.1](https://github.com/openai/codex/releases/tag/rust-v0.157.1)
(tag commit `36650394`). Every flag the sweep lanes use is present and `codex exec --help` is
byte-identical; the exec `--json` event names and usage fields are unchanged, and web-search
items gain an optional `results` field and a precise `open_page` action. Against a loopback
fake provider both versions produced the same events, `-o` file, output-schema request and
429 usage-limit events. A home migrated by 0.157.1 (two state migrations, one history
migration) still served a 0.155.1 exec turn.

**Finding for the sweep.** `codex --search exec` does not turn on live search in either
version: the search requests carried `external_web_access: false`, the same as without the
flag, while `-c web_search="live"` sent `true`. The GPT-6 lanes have searched in cached mode.

**Background server.** 0.157.0 turned on automatic startup of a local app-server for
interactive launches. In the sandbox, a plain 0.157.1 launch copied its 391 MB package into
`~/.codex/packages/app-server-daemon` and started the server and an updater loop from that
copy, outside the pinned prefix; both outlived the session, and a 0.155.1 session started
afterwards connected to that server. `codex app-server daemon stop` left the updater loop
running. By source, that loop fetches and runs `https://chatgpt.com/codex/install.sh` five
minutes after start and then hourly, to move the copy to the latest release. `--no-daemon`, or `codex features disable
daemon_auto_start`, prevented the copy and both processes, and 0.155.1 accepts the resulting
`config.toml`. `codex exec`, which the lanes use, never starts the server.

**Alternatives.** Switch now (would change the binary under a running sweep and migrate the
shared `~/.codex` mid-run); skip 0.156.x/0.157.x (0.156.1 adds GPT-6 Sol and Luna to the
model catalog, and the exec contract the lanes depend on is unchanged).

**Overturn when.** The post-switch live GPT-6 probe fails or differs from 0.155.1, a later
stable release changes exec events, lane flags or the background server's start or update
defaults, or an advisory lands against 0.157.1.

## Limits

One host and one run per arm. The worker made no live model call and read no credential. The
Prometheus trading-catalog entry (`catalogs/us-equities/agents-operations.json`) still names
3.14.0 and needs its own alignment. Upstream test suites were not run on this host.
