# Decision: workstation tool refresh, second round (2026-09-26)

**Decided by:** a worker session of the workstation lane on host `nativestack-5975wx-20260925`,
continuing the [2026-09-25 refresh](2026-09-25-workstation-sota-refresh.md) with the same rule:
a newer release replaces an accepted version only after a clean install into a fresh prefix
passes a discriminating acceptance on this host, matched against the installed version. A
release being newer is not evidence. The refresh coordinator owns the independent review of
this round; none has run yet.

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

**Alternatives.** Keep 3.14.0 (no defect of it is known to affect this host, but the TSDB
fixes cover data-loss paths on the head and WAL); wait for 3.15.1 (no patch release existed
at switch time).

**Overturn when.** 3.15.0 shows a compaction, WAL or rule-evaluation fault here, a 3.15.x
patch fixes a defect that matters to this host, or a verdict wave selects another store.
A rollback after 3.15.0 has compacted its own blocks is untested.

## Codex CLI 0.155.1 to 0.157.1 (staged)

**Decision.** 0.157.1 is installed in `tools/codex-0.157.1` and qualified without a model
call; `bin/codex` stays on 0.155.1 while the sweep's GPT-6 lanes run. The receipt holds the
switch, probe and rollback commands for the coordinator. Pins move only after the switch.

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

**Alternatives.** Switch now (would change the binary under a running sweep and migrate the
shared `~/.codex` mid-run); skip 0.156.x/0.157.x (0.156.1 adds GPT-6 Sol and Luna to the
model catalog, and the exec contract the lanes depend on is unchanged).

**Overturn when.** The post-switch live GPT-6 probe fails or differs from 0.155.1, a later
stable release changes exec events or lane flags, or an advisory lands against 0.157.1.

## Limits

One host and one run per arm. The worker made no live model call and read no credential. The
Prometheus trading-catalog entry (`catalogs/us-equities/agents-operations.json`) still names
3.14.0 and needs its own alignment. Upstream test suites were not run on this host.
