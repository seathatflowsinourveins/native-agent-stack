# Decision: the token-efficiency winner is one full stack, chosen on recorded evidence and provisional until Gate A (2026-09-29)

**Decided by:** the user, on 2026-09-29, in answers to the Claude Code session `os-b4` on host `mac-coordinator-64gb-20260925` (the Mac
coordinator). The request: "how about token effiency repos,note just one winner can be full stacks for each,and retire,clean install new with
evidances,sota upstream skills used e2e". Decisions 1 to 5 record the user's answers of the same day as their choices, not as measured
results. Decision 6 is the default in the plan the user approved; the user did not select a retire depth.

**Scope:** this record only. It changes no verdict row, catalog, pin (`manifests/stack.json`, `adoption/pins-*.json`), client setting, carrier text,
role body or install, and it starts or stops no service. It leaves the frozen treatment of Gate A (#381, owner `native-agent-stack-2d`), the
memory head-to-head (S3, #390) and the 32-layer wave (F-LT-1) as recorded. Follow-on work, each its own change: upstream recipe cards for the
top five members, a release review with the refreshed Mac pin file, and then the clean install under host requests #382 and #276. Lane:
`lane:foundation`.

## Context

- **Recorded state.** The `token-efficiency` layer is `recorded_reopened`. Its verdict winners are rtk 0.49.0, headroom 0.37.0 and ccusage
  20.0.24, all `synthetic` (`catalogs/sota-convergence/layer-verdicts-20260922.json:4134`). The component matrix reports 0 of 8 in-use rows
  converged (`catalogs/landscape/component-evidence-matrix.json`, `summary.convergence` and the layer's `convergence`). The roadmap says Gate A
  per-row results confirm the layer (`docs/decisions/2026-09-28-ecosystem-roadmap.md:75`).
- **Verdict unit.** The 2026-09-22 verdict records per-tool winners. The user's direction is that a winner can be a full stack.
- **Where spend goes.** Agent-tool and workflow children are 81.3% of dollars, default-typed children 41.1%, effort `max` 82.2% of calls, and
  Context Mode is 98.6% of MCP calls (`docs/decisions/2026-09-29-token-spend-attribution.md:23-30`). Tool choice is one lever; run shape is
  the larger one, so the stack carries run-shape levers as members.
- **This Mac.** A read-only coverage check on 2026-09-29 (`scripts/adoption_status.py --profile token-efficiency --client-wiring`) found all
  13 profile commands present and `client_wiring.complete: true`. The overall status read `prerequisites_missing` only because `macos-arm64`
  is not a supported platform in `adoption/manifest.json`. The tools resolve from an earlier ecosystem install prefix
  (`$HOME/.local/share/codex-ecosystem/bin`), not from pinned installs of this repository, and the Mac's `use` receipts were recorded against
  that earlier install (`docs/decisions/2026-09-27-mac-single-writer-staged.md:21`). 60 of 66 recorded winner slots are `untested` on
  `macos-arm64` (the matrix).
- **Upstream-alignment gaps recorded before this decision.**
  - `adoption/pins-macos-arm64.json` was "drafted ... from a Linux workstation: no macOS host executed anything here" and lags upstream:
    mcporter 0.13.13 against v0.14.1, socraticode 1.14.0 against v1.16.0, headroom 0.37.0 against v0.39.x, ai-memory 2.3.2 against v2.4.1.
  - Serena is pinned to an unreleased dev commit (`2.0.0.dev0 @ c6fbd1c5`); the upstream release is v1.7.0.
  - The Mac's production ai-memory is a local `cargo build` of `release/2.5`, and the memory-stack catalog says its binary provenance
    "conflicts with the official-artifact rule" (`catalogs/foundation/memory-stack-20260925.json`, the ai-memory row).
  - jCodeMunch is installed but wired into neither client on this Mac, and the SubagentStart carrier still advertises `route(task, repo?,
    execute?)`, which missed 6 of 6 in the 2026-09-27 smoke (`docs/decisions/2026-09-28-ecosystem-roadmap.md:52`).

## Decisions

1. **One winner can be a full stack.** For the `token-efficiency` layer the winner is the lane-owned token and context stack below. A member is
   a lane owner, an on-demand tool or a run-shape lever. Per-tool rows remain the evidence; they are no longer this layer's verdict unit.
   Applying the rule to other layers is a separate decision.
2. **Chosen on recorded evidence now, and provisional.** The stack is the stack of record for the Mac coordinator until Gate A per-row
   results, the paired comparison this stack still owes, or the 32-layer wave confirm or overturn it. It edits no verdict row.
3. **Memory is a slot decided on merit, per host.** S3 (#390) decides it. Candidates on the Mac are agentmemory 0.9.29, MemPalace 3.10.0,
   Hindsight 0.10.1 and any macOS-capable repository a fresh scan finds, with ai-memory as the reference arm. The user: "add the
   agentmemory,hindsight etc for whatever best macos memory repos at current landscape should be". Until S3's rule is met (a challenger beats
   both C3 and C4 by at least 5 pp under Holm, then passes the deployable-artifact gate and the memory-lane acceptance), the running
   ai-memory stays the production control and the candidates are isolated trials with no production wiring.
4. **Upstream is the source of truth.** Each member is installed from its upstream's supported channel at a release-reviewed pin with the
   publisher's digest. Upstream's own tests and evals are the standard where they exist; where they do not, the missing eval is a recorded
   gap. An integration that departs from upstream's supported path is recorded as an adaptation with its reason. The user: "the repos
   upstream itself is sourceof truth ... otherwise the trail e2e practice itself cannot be the evidance", so results from a departed path are
   not evidence about the upstream tool.
5. **Under-invoked skills and tools get an exact cause before any change.** Classify each as not needed by the task set, not discoverable
   (listing state or description budget), not triggered (description), or blocked by the harness (role allowlist, preload rule, deferred
   tool schema, a carrier advertising a missing operation). Fix at the layer that owns the cause: an upstream-aligned adaptation, a
   listing state, a role grant, or an upstream issue or pull request. Record harness gaps in a gap ledger. Nothing is demoted or removed on
   zero invocations alone. The user: "not blindly delete, but improve the sota repos, skills use adapt them natively, the evl of the sota
   repos, skills themself should be the standard". The skills trial's prune rule (`adoption/skills/manifest.json`, `trial.prune_rule`) is left
   as recorded; an amendment that requires a recorded cause before demotion is proposed to its owner. Fresh discovery of token-saving
   skills is in scope; a new skill is adopted only through the skills manifest at a pinned ref and within the listing budget.
6. **Retirement is last and gated (the approved plan's default).** After a member's replacement passes its clean install and e2e, the
   superseded hook, MCP, plugin or skill entry is unwired and the old prefix is kept until a set number of days pass without regression. Deleting the
   old prefix needs a separate go from the user. Retiring the earlier ecosystem install on this Mac gets a notice on agent-ecosystem#28.
   Retirement criteria are a superseded install path, or a lane fully covered by another member with a recorded cause. No retirement
   happens in the first slice.

Not decided here: whether the Mac's production ai-memory stays the local build under Stage 1's no-service-change rule until the first
official 2.5 release, or moves by a cold-copy cutover to official v2.4.1 with a rehearsed rollback.

## The stack

Lane owners. Counts are call counts from the workstation's transcripts over 2026-09-25T11:37Z to 2026-09-26T23:37Z
(`evidence/artifacts/token-stack-cards-20260927/invoke-by-tool.json`, `local_integration`): the number of workflow children of 1,010 and Codex
exec workers of 301 that used the tool at least once. They measure adoption, not benefit.

| Lane | Owner and client wiring | Recorded basis |
| --- | --- | --- |
| Shell output | RTK 0.50.0. Claude: `rtk hook claude` on Bash with the five `exclude_commands` entries. Codex: explicit `rtk` commands from the Codex worker lane's global `AGENTS.md` block (`docs/token-practice.md:44-62`) | 192 of 1,010 workflow children, 150 of 301 Codex workers; `host_verified` on Linux and on the Mac (matrix) |
| Large output, logs, files | Context Mode 1.0.169 plugin (`ctx_execute`, `ctx_search`) | 162 and 265 of the same populations; verdict alternative with a measured trade-off; `host_verified` on Linux, not run on the Mac |
| Exact code | Serena | layer `code-navigation` winner, `native_proven`; 37 and 21; `host_verified` on Linux, `untested` on the Mac; pin decision in the release review |
| Conceptual code | SocratiCode with Qdrant | layer `semantic-rag` winner, `native_proven`; upstream-suite receipts at 1.15.0 (#446); 96 and 11 |
| Structural code | ast-grep | `native_proven` alternative in `code-navigation`; 44 and 2 |
| Symbol index | jCodeMunch, once wired | measured-trade-off alternative in `code-navigation`; 64 and 3; owner only after its route operation is repaired |
| Documents | QMD 2.8.3 with MarkItDown 0.1.8 | layer `document-retrieval` winners, `local_integration`; 64 and 67; QMD reported 29 unembedded documents on 2026-09-28 (`docs/decisions/2026-09-28-ecosystem-roadmap.md:55`) |
| MCP bridge, accounting | MCPorter; ccusage 20.0.26 with token-report and the Loki invoke-rate series | 111 and 63; ccusage counts the advisor from 20.0.17 |
| Memory | slot decided by S3 (decision 3) | no winner recorded |
| Run-shape levers | role dispatch, `maxTurns`, `omitClaudeMd`, a query limit of about three per `ctx_batch_execute`, serena ids out of the mandatory select, output caps | the practice-status table and lever list in `docs/decisions/2026-09-29-token-spend-attribution.md:59-95`; owned by the Gate A owner after #381 closes |

On-demand members keep their recorded role: activate when the task needs them, do not stack transformations (`docs/token-practice.md:70`).
Nothing about them changes in this decision; Gate A per-row results decide any change.

- **Repomix 1.18.1:** explicit-file outlines only. Its MCP compress comparison was superseded: the records `repomix-08-mcp-grep-full` and
  `repomix-09-mcp-grep-compress` return 1 and 0 matches for `status_body` (`evidence/artifacts/token-stack-cards-20260927/README.md:104`).
- **TOON 4.1.1:** only where a measured comparison shows a gain. On the full catalog compact JSON is 59,792 tokens and TOON 66,815
  (`docs/token-efficiency-stack.md:46`).
- **Headroom:** the guarded compressor that retains the original. It is a verdict winner on fixtures only, its default ledger showed 0 calls
  (`docs/token-efficiency-stack.md:39`), and the transcripts show 6 MCP calls and 135 command matches across 58 workflow children. Codex keeps
  its existing `headroom` MCP registration meanwhile.

Not members, unchanged by this record: codebase-memory-mcp, Context Hub, AgentsView and gpt-tokenizer, which stay under their own rows.

## Alternatives considered

- **Per-tool winners, the 2026-09-22 shape.** Not chosen: the user directed that one winner can be a full stack.
- **A paired stack-level comparison first** (native baseline, current stack, lean stack, full profile). Not chosen now: the user chose recorded
  evidence, and the roadmap update of 2026-09-29 records Claude weekly capacity at about 75% until its 2026-09-30 reset. It remains the owed
  comparison for this stack.
- **Wait for Gate A before choosing.** Not chosen; Gate A confirms or overturns the rows afterward.
- **Retire first, then install.** Not chosen: the clean install and its e2e come first (decision 6).

## What would overturn this

- A Gate A per-row result that fails a required row for a member, or shows that children in the roles that need a lane owner do not adopt it.
- A paired stack comparison in which another composition matches quality at lower complete provider usage than this stack, each measured
  against the cheapest adequate native baseline (`docs/token-practice.md:81`).
- S3 or the 32-layer wave recording a different memory system or a different token-layer winner.
- An upstream release or eval showing that a member's supported integration differs from the wiring here in a way that changes results.
- A decision-5 finding that a lane owner is under-invoked because of the stack itself and not the harness.

## Limitations

- The evidence is mostly fixtures and local integration: the verdict rows for rtk, headroom and ccusage are `synthetic`. Invoke counts are
  command-text and MCP-call counts from one host's transcripts, and a `cli_calls` match can count for several tools.
- No provider-savings result exists for the stack. The counters in the token stack cards are upstream estimates in each tool's own unit and are
  never summed.
- The Mac has no `use` receipt at a pinned, upstream-aligned install, and 60 of 66 winner slots are `untested` there. Its pin file was drafted
  from a Linux host.
- The spend attribution covers one host and one six-day window, and dollars are a proxy.
- The composition is the coordinator's reading of recorded evidence. It is not a blind cross-family convergence and not a verdict.

## Sources

- Repository at `origin/main` `df412368`: the paths cited above; `docs/token-efficiency-stack.md`, `docs/token-practice.md`,
  `adoption/manifest.json` (`token-efficiency` profile), `adoption/pins-macos-arm64.json`, `adoption/skills/manifest.json`,
  `adoption/lifecycle.md`, `evidence/artifacts/token-adoption-e2e-20260926/README.md` (Gate A preregistration, capability gate).
- Host requests [#382](https://github.com/seathatflowsinourveins/native-agent-stack/issues/382) and
  [#276](https://github.com/seathatflowsinourveins/native-agent-stack/issues/276); S3
  [#390](https://github.com/seathatflowsinourveins/native-agent-stack/pull/390); Gate A
  [#381](https://github.com/seathatflowsinourveins/native-agent-stack/issues/381).
- Upstream repositories of the members, at the pins recorded in `manifests/stack.json` and `adoption/pins-macos-arm64.json`:
  [rtk-ai/rtk](https://github.com/rtk-ai/rtk), [mksglu/context-mode](https://github.com/mksglu/context-mode),
  [oraios/serena](https://github.com/oraios/serena), [giancarloerra/SocratiCode](https://github.com/giancarloerra/SocratiCode),
  [tobi/qmd](https://github.com/tobi/qmd), [microsoft/markitdown](https://github.com/microsoft/markitdown),
  [openclaw/mcporter](https://github.com/openclaw/mcporter), [ccusage/ccusage](https://github.com/ccusage/ccusage),
  [jgravelle/jcodemunch-mcp](https://github.com/jgravelle/jcodemunch-mcp), [ast-grep/ast-grep](https://github.com/ast-grep/ast-grep),
  [yamadashy/repomix](https://github.com/yamadashy/repomix), [toon-format/toon](https://github.com/toon-format/toon),
  [headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom).
- Memory candidates: [rohitg00/agentmemory](https://github.com/rohitg00/agentmemory) v0.9.29,
  [mempalace/mempalace](https://github.com/mempalace/mempalace) v3.10.0,
  [vectorize-io/hindsight](https://github.com/vectorize-io/hindsight) v0.10.1, and the memory-stack catalog
  (`catalogs/foundation/memory-stack-20260925.json`).
