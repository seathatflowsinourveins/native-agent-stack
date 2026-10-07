# Token-practice E2E preregistration — PR-H

Status: **frozen protocol, not executed or accepted**. Merge this preregistration
before any organic run. This unit supplies the preregistration half of full-save
§5 step 9; the historical receipt already merged through #369 is
[child-lane-baseline-20260926](../../../evidence/artifacts/child-lane-baseline-20260926/README.md).
It is retained measurement evidence, not a model run or a new acceptance.

**Dated scope note, 2026-09-26:** AA §6's `baseline.json` is deferred to PR-A's
remaining measurement-tool and baseline scope (full-save §5 step 4). It is not
fabricated or silently omitted here. #369 is a **pre-fix reference baseline only**;
it cannot supply the post-fix baseline required before organic execution.

## Sources, boundaries and freeze

**AA** means *Token-tool adoption in Claude children and Codex workers: one
integration plan*, 2026-09-26, including its review resolution. **full-save**
means *Full-save token foundation plan*, revision 1, 2026-09-26. These section
labels identify the supplied specifications; no machine-local location is part
of the protocol. The builder read both complete specifications. The native
script contract is the official [Workflow reference](https://code.claude.com/docs/en/workflows),
“Pass input”, “What the saved script looks like”, “Edit a saved script”,
“Prompt caching”, and “Behavior and limits” (supplied 2026-09-26 snapshot,
lines 230–238, 292–334, 348–368). AA §8.1 supplies the explicit role/model/effort
options; the public Workflow page alone does not enumerate every option.

The normative artifacts are [preregistration.json](preregistration.json), which
holds the task/arm inventory, minimum opportunities, structured M/G thresholds,
M3 exception classes, strict-blind candidate/gate, outcome rule and overturn
conditions; [the Workflow script](token-e2e-run.mjs), which enforces dispatch
and binding checks; and [RUNBOOK.md](RUNBOOK.md), which specifies collection,
independent grading and restoration. All are kept together in this evidence directory
rather than under `examples/claude-native/workflows/`: **integrator
correction.** That directory's own `test-envelope.mjs` sweeps every file
declaring `export const meta` and requires the shared, byte-identical
`PACKET` worker-prompt prefix and a hardcoded `ROUTING` table shared across
its small set of reusable coordinator-dispatched workflows
(`review-changes.js`, `readiness-audit.js`, `layer-verdict-lane.js`). This
script is a one-off, frozen, bespoke-schema E2E protocol script, not one of
those reusable packets, so it does not and should not match that contract;
placing it there without conforming would fail `test-envelope.mjs`, and
making it conform would misrepresent what it actually does. The Workflow
tool's `scriptPath` accepts any committed path — this location works
identically at launch (RUNBOOK.md's exact invocation). The integrator-supplied
source base is `34c56340`; the builder did not inspect Git state. Record the
actual merged preregistration commit, artifact hashes and execution revision
before launch
(AA §8.4). No task, eligibility rule, threshold, exception or check can be
changed after looking at organic results. Amend and merge the protocol first
if a prerequisite requires changing an input. Retain failed attempts and
unknowns. A top-up under AA's incomplete rule uses the same frozen task/check
definitions and a new recorded attempt; it is never retroactive recoding.

These are repository integration contracts and synthetic fixtures, following
[the evidence policy](../../../docs/acceptance-evidence-policy.md). Their local
tests cannot establish upstream acceptance, organic adoption, provider savings
or the complete foundation acceptance rule below.

## Task inventory and provenance — AA §5, §8.1–§8.3

There are **77 frozen definitions**: 16 reused Claude information needs, 15
reused Codex information needs, and 46 seed/control definitions. The Claude
receipt has 16 `tools[]` entries. The Codex receipt has **17 entries for 15
distinct tools**, including two retained attempts each for jcodemunch and qmd.
Both retry pointers survive; a historical retry is not another task or organic
opportunity.

Receipt sources are
[#296](../../../evidence/artifacts/token-e2e-ultracode-20260925/receipt.json) and
[#343](../../../evidence/artifacts/token-e2e-codex-20260926/receipt.json).
The JSON preserves exact array pointers, real `tool` identifiers and the
original `task` or `commands` field provenance. Receipt text is sometimes
truncated and describes historical failures. It is not silently completed or
recast as current success. The short task prompts preserve the information
needs without tool names; long answer/notes excerpts and the original
tool-prescribing commands never become child prompts. The source receipts
remain authoritative historical records, including their failure limitations.

The reused table task freezes the **60-row** array at
`catalogs/landscape/component-evidence-matrix.json#/summary/needs_host/macos-arm64`
(#296 `/tools/9`, #343 `/tools/16`) from the **preregistration commit**.
Both tasks use `<retained-input>` and the JSON's `frozen_input` serialization,
SHA256 and byte count. Extract and verify that pointer before probes; the
execution checkout's regenerated matrix is never the source or grading input.
The 24-row fixture below is for seeds only.
The command-fidelity receipts do not retain all six original command identities.
Their recoverable checker compares newest commit subject, test count and status
for `tests.test_host_requests`. Recover and seal missing source command inputs
before probes; do not select substitutes. A missing retained history report also
blocks launch. Neither limitation permits replacing a reused information need.

| Frozen id | Short information need | Receipt entry pointer (zero-based) |
| --- | --- | --- |
| `reuse-296-00` | Command-output fidelity | #296 `/tools/0 (rtk)` |
| `reuse-296-01` | Large handbook summary | #296 `/tools/1 (context-mode)` |
| `reuse-296-02` | Selected-history round trip | #296 `/tools/2 (headroom)` |
| `reuse-296-03` | Definition retrieval | #296 `/tools/3 (jcodemunch)` |
| `reuse-296-04` | Release pin decision | #296 `/tools/4 (qmd)` |
| `reuse-296-05` | Definition and references | #296 `/tools/5 (serena)` |
| `reuse-296-06` | Request trust boundary | #296 `/tools/6 (socraticode)` |
| `reuse-296-07` | Historical host-lane decision | #296 `/tools/7 (ai-memory)` |
| `reuse-296-08` | Selected-file overview | #296 `/tools/8 (repomix)` |
| `reuse-296-09` | Structured table fidelity | #296 `/tools/9 (toon)` |
| `reuse-296-10` | Structural call sites | #296 `/tools/10 (ast-grep)` |
| `reuse-296-11` | Caller graph | #296 `/tools/11 (codebase-memory)` |
| `reuse-296-12` | Documentation completeness | #296 `/tools/12 (context-hub)` |
| `reuse-296-13` | Document conversion fidelity | #296 `/tools/13 (markitdown)` |
| `reuse-296-14` | Session archive visibility | #296 `/tools/14 (agentsview)` |
| `reuse-296-15` | Scoped span visibility | #296 `/tools/15 (otel-tui)` |
| `reuse-343-00` | Session archive visibility | #343 `/tools/0 (agentsview, attempt 1)` |
| `reuse-343-01` | Historical host-lane decision | #343 `/tools/1 (ai-memory, attempt 1)` |
| `reuse-343-02` | Structural call sites | #343 `/tools/2 (ast-grep, attempt 1)` |
| `reuse-343-03` | Caller graph | #343 `/tools/3 (codebase-memory, attempt 1)` |
| `reuse-343-04` | Documentation completeness | #343 `/tools/4 (context-hub, attempt 1)` |
| `reuse-343-05` | Large handbook summary | #343 `/tools/5 (context-mode, attempt 1)` |
| `reuse-343-06` | Selected-history round trip | #343 `/tools/6 (headroom, attempt 1)` |
| `reuse-343-07` | Definition retrieval | #343 `/tools/7 (jcodemunch, attempt 1); /tools/8 (jcodemunch, attempt 2)` |
| `reuse-343-09` | Document conversion fidelity | #343 `/tools/9 (markitdown, attempt 1)` |
| `reuse-343-10` | Release pin decision | #343 `/tools/10 (qmd, attempt 1); /tools/11 (qmd, attempt 2)` |
| `reuse-343-12` | Selected-file overview | #343 `/tools/12 (repomix, attempt 1)` |
| `reuse-343-13` | Command-output fidelity | #343 `/tools/13 (rtk, attempt 1)` |
| `reuse-343-14` | Definition and references | #343 `/tools/14 (serena, attempt 1)` |
| `reuse-343-15` | Request trust boundary | #343 `/tools/15 (socraticode, attempt 1)` |
| `reuse-343-16` | Structured table fidelity | #343 `/tools/16 (toon, attempt 1)` |

Seed definitions and checks are in the same JSON:

- `seed-web-table-1..5` and `seed-codex-web-table-1..5`: two-page
  documentation questions plus eight-record uniform tables. Each family has
  five organic fetch tasks, providing at least five remote fetches in Codex B
  (AA §8.2). The selected table is a neutral-path byte copy of
  `fixtures/headroom-records.json`; its original 24 flat public records are
  preserved.
- `seed-catalog-history-1..5`: five questions in the actual indexed
  `catalogs/us-equities` corpus paired with five prior-decision questions.
  The source-only checks do not substitute for successful scoped retrieval.
  The reused release-pin task's known index gap does not count toward qmd
  eligibility (AA §5; #343 `/tools/10` and `/tools/11`).
- `seed-log-symbol-1..5`: five ranges of an 84,003-byte public synthetic log
  paired with real definition/call-site questions in `scripts/host_receipts.py`.
  The log has 640 records, ten ERROR records and a formula fixed in the JSON.
- `seed-acceptance-1..5`: explicit inventory/line-count observations and
  acceptance commands that emit the entire log plus their fixed summary.
  The raw output exceeds 5 KB; the returned answer needs the exit code and
  summary only. This is not an excuse to exclude the full output from M3.
- Two scout tasks, two isolated edit/test tasks, five small blind packets,
  one large blind positive control, a main-actor observation, and an Agent-tool
  path observation complete AA §8.2's roles and paths.
- `seed-review-diff` adds the explicit large-diff evidence-reviewer scenario:
  the existing 52,631-byte `blueprints/retrieval-quality-v2/run-efba31d5.patch`,
  with a fixed header/hunk/count and opening-contract check. The two reused
  symbol reviewer tasks remain separate, covering both AA §8.2 scenarios.
- `seed-binding-1..5` freezes the Codex lifecycle matrix: no history, bounded
  history of 2 turns, full history with the researcher role, full history
  without a role, then a resumed finished researcher child. Arm A repeats
  `seed-binding-1` (none, retaining its researcher role as requested in repair 1)
  and `seed-binding-4` (all, without a role or agent_type). Only the full-history
  A case moves; this retained none case is an explicit exception to AA §8.2's
  no-role wording. M13's separate 2-worktree × 20-repetition probe
  does not satisfy the organic minimum.
- Optional overview and HTML-conversion seeds are reported, never gating.
  full-save §1a, §2.3 and §8 finding 6 supersede AA's PDF seed with HTML:
  `fixtures/markitdown-multi-element.html`. PDF extras need separate
  qualification. The optional graph seed is **blocked until Q3 [nv]**;
  blocked is not “ineligible” or an N/A substitution.

Only `task_text` reaches a child's prompt. The only substitutions bind
`<assigned-worktree>`, `<assigned-base>`, `<retained-input>` and `<run-token>`
to pre-recorded neutral paths, the prepared tree's base revision and the run
token; no instructions are appended. Identical source
bytes and observation contracts apply across arms. Freeze all six distinct
builder checkouts plus the per-arm observation checkouts and disposable clones.
These are prepared bindings. **Amendment 2 (2026-09-27):** #402 removed the builder's frontmatter isolation,
so no arm expects a harness-created tree; each builder brief names its arm's frozen prepared path, where the child edits, and that tree's exact base (repair round).
For builder tasks, derive the actual edited tree and starting revision from the child's
native transcript and `meta.json`, require that tree to be the prepared path, and read the diff there, per
`builder_worktree_policy`. Missing or conflicting identity blocks grading. The same checks apply in A and A0;
RUNBOOK's builder section freezes the hooks preflight
and restore procedure. Retained-history, table and HTML input paths are
supplied explicitly, and resolved
prompts must pass the same denylist. Eligibility tags, receipt tool
identifiers, checks and the denylist are evaluator metadata. The explicit
denylist includes every `rows[].component_id` in
[the canonical component inventory](../../../docs/token-efficiency-stack.json) plus
[handbook lines 106–151](../../../docs/token-session-handbook.md), spelling variants
and relevant entry-point names. Both checks treat underscores as separators
using case-insensitive ASCII-alphanumeric boundaries, including qualified MCP
names. No LANES block is appended to experimental
prompts: AA §8.1's no-tool-names rule and the PR-H task contract control this
experiment; AA §9.2 remains guidance for ordinary coordinator packets.

### Counted organic arm-B opportunities

Each count is unique child-task definitions with arm B, `opportunity=organic`
and the named tag. Main, optional, blocked and positive-control tasks do not
count. These are frozen eligibility counts, not observed successful calls.
The tests independently pin the required lane set and fail below five.
Cross-cutting M rows have explicit tags too; their successful-call or error
denominators remain those in AA §8.3, not the task counts in this table.

| Required lane | Metric | B child-tasks | Eligibility source and rule |
| --- | --- | ---: | --- |
| ctx-containment | M3, M5 | 14 | Output likely over 5,120 bytes; a derived answer suffices. AA §5 excludes edit bytes, original line citations and frozen exact-byte requirements. |
| fetch | M4 | 10 | Multi-page web documentation question, AA §5; remote nested fetches remain in the denominator. |
| rtk-claude | M6 | 8 | Claude task has an RTK-supported shell observation outside the exactness exceptions; acceptance exits run raw/proxy. PR-A owns part classification. |
| rtk-codex | M6c | 6 | Codex task needs supported shell inventory/read commands; exceptions are excluded from coverage denominator. |
| toon-seeded | M7 | 10 | A seeded uniform array of at least five flat records must enter context; strict round trip is checked. |
| symbol-references | M8 | 9 | Definition/reference question in the starting client's own indexed checkout; capability/source binding must pass. |
| qmd | M8 | 5 | Answer lies in the named indexed catalog collections. The reused release-repin gap is excluded from this lane. |
| ai-memory | M8 | 7 | Prior project decision/history with a scoped source witness, checked as untrusted history. |
| adoption | M1, M2 | 44 | Non-blind, non-scout child-task with at least one eligible token lane; M1 is assessed separately per required retrieval/containment lane. |
| guidance | M11 | 71 | Any organic preregistered child launch with a frozen route/carrier; blocked loopback task excluded. |
| blind | M12 | 5 | Stripped blind packet; controls never contribute to the five organic opportunities. |
| binding | M13 | 5 | Organic Codex child-task with a per-tree sentinel; the separate 2 worktrees x 20 probe repetitions do not count here. |
| attribution | M14 | 71 | Organic child-task with client/session/call identity and native transcript; blocked loopback task excluded. |
| mcp-errors | M15 | 40 | Task with an eligible granted MCP lane; classify infrastructure failures by server independently of command exits. |

M1's ≥90% and M8's ≥80% both apply where required; the latter does not relax the
former. Report per-role and per-family populations alongside the common
minimum, and never substitute task counts for call counts (AA §8.3; full-save
§4.0/§4.3).

## Arms, roles and exact execution counts — AA §8.1/§8.2

Claude arm order is **B, A, A0**. B uses the role table; A uses
`general-purpose` on the identical task text and model; A0 omits
`agentType` on the identical task text and model. This deliberate A0 omission
is the preregistered experimental exception to AA §9's ordinary dispatch rule. **Amendment 2 (2026-09-27)** moved the verifier and builder rows to Opus and three carriers to #402. The executed role bodies must equal Amendment 2's role-body SHA256 table. **Amendment 3 (2026-09-28)** replaces its `isolated-builder.md` row with the Amendment 3 row.

| Frozen role in B | Explicit model | Explicit effort | Carrier |
| --- | --- | --- | --- |
| stack-researcher | opus | max | #376 role body, after merge/install proof; unchanged by #402 |
| stack-verifier | opus | max | #402 role body at d022295a |
| isolated-builder | opus | max | #402 role body at d022295a as changed by Amendment 3 |
| evidence-reviewer | opus | max | Existing role body; unchanged by #402 |
| source-scout | sonnet | max | #402 role body at d022295a |
| blind-lane-reviewer / blind-judge | opus | max | Existing stripped blind bodies; no skill preload |

The Workflow inventory reserves **49 B, 43 A, 43 A0 children**, in JSON order,
one active child at a time. Five organic blind packets and the positive control
run in B only; A/A0 repeat every non-blind workflow task. Outside this script
there is one B and one A Agent-tool child, one B main-actor observation, and
six strict-process repeats of the blind packets. That is **137 Claude children,
one main observation, six strict processes**. These exact counts replace
AA §8.2's approximate planning estimate; its role/path minimums remain covered.

**Blocked before launch (repair 1, 2026-09-26):** `reuse-296-15` retains the
loopback receiver information need and every arm slot, but `source-scout.md:11`
forbids network use. No equivalent permitted Sonnet/max role with the same
absence of worktree isolation is evidenced in this checkout. Its role is
unbound and its opportunity is blocked pending a dated, merged role amendment
and capability qualification. The script refuses the entire selected arm before
any child starts; it never drops this task. Thus the counts above are planned,
not presently runnable. Do not weaken source-scout's no-network rule.

The coordinator stays at **xhigh under Ultracode**. Never set
`CLAUDE_CODE_EFFORT_LEVEL`: it overrides child effort. Every child call
specifies model and max effort; M11 checks the resolved route, not just the
request ([AGENTS.md](../../../AGENTS.md), Workers; AA §3.3/§8.1/§9.1).
Matching model, effort, type, tool set, schema and cwd permit native cache
sharing; no cache or tool-discovery override is introduced (Workflow reference,
“Prompt caching in a fan-out”). The sequential schedule is a frozen bounded
choice, not a savings claim. Size guidance is advisory; do not shrink the task
list to satisfy it.

Codex order is **B, A, N**, with `gpt-6-astra`, max effort and live web search
held fixed. Each arm has **20 exec task launches**, scheduled as two concurrent
owned worktrees in waves. B also has five lifecycle child-tasks; A has two;
N has none. There are **25 B / 22 A / 20 N child-task outcomes** before retries.
The graph seed remains blocked and excluded from these scheduled counts.
These exceed AA §8.2's exec minima and keep one task identity per exec launch.

B uses the pending `stack-worker` profile and qualified custom agents.
A uses user config. N uses `--ignore-user-config -c features.hooks=false
-c features.plugins=false`; it is **config-free**, not guidance-free, unless
Q2's prompt-input plus rollout read-back passes. Until then M6c compares B
with A, not N (AA §3.2). Full-history/no-role and resumed child behavior must
be observed, not inferred from the profile. Compaction remains untested if it
does not occur (AA §10).

`source-scout` and `evidence-reviewer` are **Claude-only role lanes**. AA §6:372
names only `stack-researcher` and `stack-verifier` as Codex carriers. Shared
Codex exec information needs retain their text and receipt provenance but bind
no nonexistent Claude role name; the arm's exec profile supplies their carrier.
`codex_role_exclusions` and each affected task record this distinction.

## Identity table — AA §7, §8.1

Identity format: `<run>.<arm>.<task>.<attempt>`. Angle-bracket tokens describe
fields; they are not fabricated identities. Record actual identifiers privately.

| Field | Frozen meaning |
| --- | --- |
| run | Coordinator-supplied token for this complete experiment |
| arm | B/A/A0 for Claude; B/A/N for Codex; client column disambiguates |
| task | Exact frozen JSON id; no source retry is silently renumbered |
| attempt | Positive integer; every retry/interruption is retained |
| client / actor / parent | Claude main, Workflow child, Agent child, strict process, or Codex exec/sub-agent; explicit parent |
| workflow / transcript | Actual arm `workflow.run_id`, transcript and child metadata locator |
| thread / conversation | Actual Codex `thread.started` id and observed rollout relation |
| call join | Claude `session.id + tool_use_id`; Codex `conversation.id + call_id` |
| observation window | Start/end, exporter flush status, native route and usage source |

Arm IDs and task labels are different identifiers. Resource
`ecosystem.task.id=<run>` tags the Claude process and its in-process children
**[nv until reconciliation]**. Each arm has its own observed workflow ID.
Claude strips `OTEL_*` from subprocess environments. Codex launches therefore
set `-c otel.environment=<run>.<arm>.<task>.<attempt>` **[nv]** explicitly and
record the thread ID as fallback. Exporter configuration must also be supplied
for config-free N launches (AA §7). No unjoined event is assigned by guesswork.

## Capability gate — AA §8.1b

The following is the source gate; internal section references in this quotation
refer to AA. This gate precedes organic execution and is not performed by PR-H.

Organic adoption does not start until each capability is shown to work.

- **Explicit runs.** For each role and tool pair that §5 marks eligible, run an explicitly instructed task: two discriminating fixtures, 3 repetitions each (GPT-6 Claude side, stage 3; GPT-6 tools, stage 3).
- **What is checked.** Verify the executed call, the successful result and the source identity (a sentinel only the child's tree holds), not the model's own claim.
- **Where the capability truly exists, pass means 100%.**
- **Negative controls must fail the gate:** a disabled server, or a wrong-root binding.
- **Native harness option: `claude plugin eval`.**
  - It covers plugin-shipped tools only. On this host that is context-mode; qmd is a user-scope server (`mcp__qmd__*`).
  - Use `--mocks off` with a named grant, `--allow-tools "mcp__plugin_context-mode_context-mode__*"`. Keep evidence that the real server ran against the fixture: the sentinel in its result.
  - `--allow-real-servers` alone keeps answering mocked tools from their mock files, and real tools need the grant in either mode (plugin-evals.md:320-323, 361, 381-382 [doc]).
- **Probe.** The Agent-tool blind-lane probe from §3.1(d) runs here, in a scratch session.
- **Separation.** Capability-gate runs never count toward the organic minimums (§8.3).

Use AA §5's actual role × tool eligibility, including allowlists, tree bindings,
static memory scope and the qmd corpus. Freeze the matrix, two discriminating
fixtures and their expected source witnesses before probes. An installed
binary, tool listing, self-reported success or current-host historical receipt
cannot replace the successful executed calls. The scripted organic prompts
remain tool-name-free even though capability probes are explicitly instructed.

## Metrics and thresholds — AA §8.3, frozen here

The following copies AA §8.3, with only its three “proposed; PR-H freezes”
qualifications changed to **frozen**. The 20,480 B ceilings, B≤A byte bound and
10% unclassifiable-fetch ceiling are fixed. Source-relative section references
refer to AA. “Baseline today” denotes AA's historical populations, not this
unrun experiment or #369's different window.

**Common rules.**
- **Required lanes** (gating): ctx containment (M3, M5), fetch (M4), RTK (M6, M6c), TOON (M7 seeded), symbol references, qmd and ai-memory (M8), and M1, M2 and M11–M15.
- **Optional lanes** (reported, never gating): repomix and markitdown (M9), headroom MCP (M10), natural TOON payloads (M7), socraticode where granted, and codebase-memory if Q3 passed.
- **An opportunity** is a child-task that the preregistered eligibility rule marks eligible for a lane. It is coded from the frozen task list before the run, and checked against the transcript afterwards.
- **Minimums.** A required lane needs at least 5 eligible opportunities in arm B from the organic run; capability-gate runs never count.
  - With fewer, the lane is **incomplete**, and an incomplete required lane makes the E2E **incomplete**, never a pass.
  - An optional lane with fewer than 5 is reported as N/A.
- "Successful" means `tool_result` is not an error.

| Id | Metric | Population | Baseline today | Pass |
|---|---|---|---|---|
| M1 | Eligible-lane adoption: opportunities where the child made at least one successful call to the eligible lane | Arm B role children; required lanes | Not measurable retroactively. Proxy: `general-purpose` children with any MCP call 19.2%, with non-ctx MCP 6.2%; `workflow-subagent` 1.1% | **≥90%** per required lane |
| M2 | Children with at least one successful token-tool call, MCP or CLI lane | Arm B children except `source-scout` and blind | 19.2% (`general-purpose`, MCP only); 1.1% (`workflow-subagent`) | **≥90%** |
| M2b | MCP share of tool calls. **Descriptive only**: never a pass/fail row or an overturn condition (§0.1: no MCP-share target). | stack-researcher, stack-verifier, isolated-builder; evidence-reviewer | 1.9% (`general-purpose`); 49.1% (evidence-reviewer) | – (reported by role, beside M1 and M3) |
| M3 | **Context containment.** Tool results over 5,120 B entering context, from every carrier: Bash, `rtk proxy`, WebFetch, Read, Grep/Glob, ctx, other MCP. Preregistered exceptions are left out:<br>- a Read of a file the child then edits;<br>- original source that the answer quotes or cites by line;<br>- output whose exact bytes the frozen check requires. | Arm B children | Shell and web only: median 10 per child, p90 26 (`general-purpose`); 2 (`workflow-subagent`); 56.7% / 56.2% of Bash bytes. All-carrier figures come from PR-A. | - Median **≤1** non-exception result over 5 KB per child.<br>- **≤20%** of non-exception result bytes from results over 5 KB.<br>- **No** non-exception result over 20,480 B.<br>- B's total non-exception bytes over 5 KB **≤** A's, on the same tasks.<br>The last two bounds are frozen by PR-H.<br>`rtk proxy` results count in every measure, and PR-A counts them the same way. An acceptance command whose output may exceed 5 KB runs inside a shell `ctx_execute`, with an explicit cwd, printing its exit code and summary lines verbatim (PR-B stack-verifier body, §9.2). |
| M4 | Fetch routing: remote fetches through `ctx_fetch_and_index`. Fetches inside ctx code count in the denominator (PR-A item 8). | stack-researcher; Codex B | 9.8% (this session); 1.4% (all sessions); Codex workers 39.5%. All three leave out fetches inside ctx code. | **≥90%**. Unclassifiable fetches are listed. If they exceed 10% of fetch operations, M4 is incomplete (the 10% is frozen by PR-H). |
| M5 | ctx result discipline | All B children using ctx | 29% of results over 5 KB (`general-purpose`); 25% (evidence-reviewer) | - **≤10%** of ctx results over 5 KB.<br>- **≤20%** of ctx result bytes from results over 5 KB.<br>- **No** ctx result over 20,480 B (frozen by PR-H). |
| M6 | RTK, Claude side | All Bash children | not_logged 25 of 15,144; 451 `rtk proxy` calls, unclassified | not_logged **≤1%**; 100% of `rtk proxy` calls are acceptance or exception commands |
| M6c | RTK, Codex side | Codex B, compared with A. N is used only if its §3.2 read-back passed. | 67.4% of all commands prefixed. N: 78.6%, with the global AGENTS.md pointer present (§1.2). | **≥90%** of eligible commands; **0** exception commands wrapped in `rtk` |
| M7 | TOON on eligible payloads (uniform arrays of 5 or more rows) | All B | 4 eligible payloads, 0 encodes | - Seeded, at least 5 payloads (required): 100%.<br>- 100% strict round-trip equality.<br>- 0 encodes of non-eligible JSON.<br>- Natural payloads (optional): ≥80%, N/A under 5. |
| M8 | Code, catalog and memory lanes on eligible tasks: symbol references (serena or jcodemunch), qmd, ai-memory. socraticode where granted, and codebase-memory if Q3 passed, are optional. | Children given that lane | 0 of 19 evidence-reviewer children used serena, socraticode, jcodemunch or ai-memory; qmd 6 children | **≥80%** per required lane, with correct answers |
| M9 | Rare lanes: repomix, markitdown | Seeded tasks | – | Optional: used, with a correct answer. Reported, not gating. |
| M10 | Headroom MCP calls | All | 5 | Optional: N/A. A call in a default role is a finding to explain. |
| M11 | Guidance delivery and resolved routes | All lanes | – | 100% on each of the following: <br>- `meta.json` `agentType` equals the requested one;<br>- every Claude child's model and effort equal the preregistered ones. Effort is checked per run with `--require-effort max`; the model comes from the transcript and `subagent_completed`;<br>- Agent-tool children that received context-mode's block return inline;<br>- Codex prompt-input has the RTK body and the exceptions;<br>- across the §8.2 launch matrix, each Codex sub-agent's model, effort, developer text and tool bindings equal its role TOML. Where no role applies, they equal the parent's (D1; child_config.rs:64-91; subagents.md:354-363). |
| M12 | Blind lanes | blind-* on the Workflow path; the strict process (§3.1c) | 3 historical transcripts: 0 injected rows | - **0** MCP, Skill or Bash calls; **0** memory or index access; **0** routing markers.<br>- The first prompt has no server instructions or connector block.<br>- **Blind evidence** needs **0** `hook_additional_context` rows from any hook event.<br>- **Positive control:** the Workflow child that reads a file over 50 KB shows ≥1 PreToolUse:Read row. A 0 there means the counter is blind, and M12 is incomplete. That child's verdict is never blind evidence.<br>- The strict process replaces the Workflow blind lane only if all of this holds on it. |
| M13 | Codex binding, cm-audit row 3 | 2 concurrent worktrees × 20 repetitions, and spawned sub-agents | 17 wrong-root results historically | Each tool class reads a sentinel file that only its own tree holds, with no explicit cwd:<br>- the shell tool;<br>- `ctx_execute` without a cwd;<br>- `ctx_execute_file` with a relative path;<br>- `ctx_index`, then `ctx_search`;<br>- serena or jcodemunch, where granted.<br>**100%** own-tree sentinels and **0** wrong-root results. `pwd` alone never counts. |
| M14 | Attribution and reconciliation | All | – | Calls are reconciled by state:<br>- attempted (transcript `tool_use`);<br>- decided (`tool_decision` accept or reject);<br>- executed (`tool_result`);<br>- failed (`success` false);<br>- cancelled or unfinished (no result).<br>IDs are qualified by client and session: Claude `session.id` + `tool_use_id`, Codex `conversation.id` + `call_id`. Each call belongs to exactly one root, child or worker.<br>Pass: **≥99%** of executed calls matched transcript ↔ Loki, with 0 duplicates; every rejected call present in `tool_decision`; per-run counts agree within **2%**; unknowns listed, never zero-filled; no global counter labelled per child. |
| M15 | MCP infrastructure errors: approval, boundary, binding, timeout, module, connection | Per server | Codex ctx 7.1% of calls failed, all classes together (cm-audit FINAL §1: 182 of 203 our configuration or usage) | **≤1%** infrastructure-class errors. A non-zero exit from the command the child ran is excluded: that is `isError` by design (cm-audit row 5). Every ctx error is classified by cm-audit row, and a new class counts as our misuse until reproduced on upstream-recommended config. |

**Guardrails, all required.**
- **G-Q, correctness.** Every B task passes its frozen check, and B passes at least as many tasks as A.
- **G-C, cost.** The **priced token estimate** per successful task, B over A, is **≤1.10×**.
  - It includes cache writes, cache reads, retries, and failed or interrupted attempts, all priced at list price.
  - **Claude tokens** come from each child's transcript, and from Loki `api_request` grouped by the arm's own `workflow.run_id`.
  - **Codex tokens** come from rollout `token_count` records, differencing cumulative totals per thread and attempt. `turn.completed` carries cumulative thread totals, `turn.failed` carries none, and an interrupted turn emits neither (event_processor_with_jsonl_output.rs:118-127, 509-562).
  - This is an estimate, never billed cost: subscription usage is not billed per token (costs.md:20,23). Plan-quota use is reported separately, where the provider shows it.
  - Prometheus is not used until G1 is fixed.
- **G-T, wall time.** B is at most 1.25× A.
- **G-P, first prompt.** The stack-researcher median is below the `general-purpose` median of the same E2E (WP5 criterion).
- **G-S, security.** 0 credential-path reads, and 0 commands that escaped the secret guard through ctx execution. This is inspected until H6 is decided.

**Outcome.**
- **Pass:** every required M row and every G row passes. M2b is descriptive, and optional rows are reported.
- **Incomplete:** a required lane had fewer than 5 eligible opportunities, or its positive control failed. The E2E is then neither pass nor fail: the lane is topped up and rerun.
- **Fail:** anything else. The failing lane is recorded, defaults do not switch, and one repair round follows before a rerun.

### Measurement interpretation and exclusions — full-save §4.0/§4.3–§4.5

**Three views, never summed:** execution; each tool's own scoped window delta;
provider usage and its priced token estimate including failures, retries and
interrupted attempts. “Every baseline states its tool, window and denominator.
Numbers with different denominators are neither compared nor added.”
Unknown is not zero; global/session counters are never per-child counters.
Only exact o200k comparison via `token_manifest.py compare` establishes an
artifact reduction. These are full-save §4.0's rules.

M3 exceptions are coded only as: a Read of a subsequently edited file; original
source quoted/cited by line; exact bytes required by the frozen check. Record
the task, result and proof for each exclusion. Summarizable logs and acceptance
output are not excluded because they are large. Raw/proxy and every other
carrier still enter the measures (AA M3; full-save §4.2, quoted scope only).

The priced estimate is the sum across **all** attempts of ordinary input,
cache-write, cache-read and output tokens multiplied by the dated published
price for that model/tier, divided by tasks passing their frozen checks.
Claude categories are separate; Codex cached input is a subset, so subtract
it from total input before ordinary-input pricing. Do not add reasoning output
again when it is a subset. Missing usage stays unknown (full-save §4.5;
[convergence architecture §6](../../../docs/convergence-architecture.md)).
Subscription use is not billed per token. No numeric model price is frozen
without a dated source; freeze the applicable price sheet before the run.

**Dated baseline disposition, 2026-09-26:** `baseline.json` is deferred to PR-A's
remaining scope; #369 is a pre-fix reference baseline only. Publication of a
sanitized regenerated baseline remains a merge-before-run gate (AA §6:412;
full-save §5 step 4).

All-carrier baselines, M-R1/M-R3 and per-child token measurement belong to
PR-A. full-save §4.1/§4.2 are outside this unit's implementation scope. We
neither regenerate nor redefine them. **Integrator addendum, verified with Git
access the builder did not have:** PR-A's own base branch,
`claude/child-lane-usage-measurement-20260926` at `152f49c2`, did merge, as
**#369** — confirmed directly, not inferred: #369's real file list
(`examples/claude-native/workflows/{child-usage.mjs,test-child-usage.mjs,
README.md,SHA256SUMS}`, `tools/skill-usage/{skill_usage.py,README.md}` and
tests) matches AA §6's PR-A file list exactly, and full-save §8 (revision-1
review, finding #8) independently records the same merge. #369 delivered only
the baseline snapshot (`evidence/artifacts/child-lane-baseline-20260926/`),
measured with the **current, pre-fix** tooling:
`examples/claude-native/workflows/child-usage.mjs:277` on `main` still
examines only `SubagentStart` rows, exactly the gap AA §6 change item 1 names
as still needing a fix. No branch or PR continuing PR-A's remaining
tooling-fix scope exists (checked directly: `git branch -a`, and every open
PR's file list, as of this preregistration's build). So #369's baseline is
retained measurement evidence, but it is not proof that PR-A's remaining
measurement extensions (all-carrier M3/M5, M-R1/M-R3, nested fetches, all-hook
injection, call states, per-thread Codex usage) exist yet.

## Blind qualification and controls — AA §3.1c/d, §3.2, Q1–Q4

The selected strict candidate is **`--safe-mode` [nv]**, not an accepted route.
Q1 must observe native sign-in with no key supplied, the requested model/effort,
the exact Read/Glob/Grep inventory and effective deny rules, no marker/server
instructions/CLAUDE.md in the first prompt, zero hook rows, and verdict parity.
Its documentation's built-in-plugin allowance is specifically checked: the
installed context plugin must not load. The runbook gives the native command.

Blind Workflow verdicts require zero `hook_additional_context` rows from
**every** hook event. Keep small packets below 50 KB and consume the session's
once-only Read/Grep tips in the coordinator first; these practices never
replace the zero-row gate. Contaminated verdicts are retained and excluded,
then repeated on the qualified strict route (or a fresh checked Workflow child
until that route qualifies). Never launch an organic blind role through the
Agent tool. Its one explicitly contaminated path probe runs only in a separate
scratch capability session (AA §3.1a/d; §8.1b).

The >50 KB positive control must fire the Read injection; its verdict is never
blind evidence. Its frozen task reads only the first five records of the
84,003-byte fixture: AA §3.1 Path 2 says the advisory uses file size and fires
on every Read (context-mode v1.0.169, hooks/core/routing.mjs:848–866).
This bounds the requested result without changing the hook condition.
All its returned bytes remain in normal M3 accounting; there is no blanket
control exemption. Strict repeats must remain clean. A zero positive-control
count makes M12 incomplete, not a pass. `--bare` remains a separate API-key
route requiring the user's decision, never an automatic fallback (AA Q1).
Q2 isolation is **[nv]** until prompt-input and own-rollout show no global
instructions, skills catalog or project layer and only preregistered tools.
Q3 graph qualification is **[nv]** on a disposable clone only. Q4's model-selected
multi-agent-v2 inference remains source-read, not probed (AA D2/§10).

## Procedure — AA §8.4

1. **PR-H is merged.** Its commit time must precede the run. Resolve the
   dependency gates below, Phase 1b qualifications and coordinated windows A/B.
2. Snapshot every AA §7 counter. Freeze tool versions/pins, carrier and skill
   hashes, settings truthiness, the actual execution checkout HEAD, the private
   identity table and Q1's chosen strict process. The execution cwd is the main
   checkout and is recorded independently of the preregistration commit.
   AA's “93 commits behind” is historical context, not a current assertion.
3. Run the capability gate, including disabled-server and wrong-root negatives.
   Only after it passes, run separate Claude Workflow runs B, A, A0 and tagged
   Codex launches B, A, N; record every native workflow/thread id. Handle the
   main, Agent-path and strict controls separately as frozen above.
4. Snapshot the same counters again, at the same scopes.
5. Run `child-usage.mjs <arm run dir> --require-effort max` separately for
   each Claude arm. Then run `child-usage.mjs --lanes-sweep` and
   `skill_usage.py --lanes` over the fixed run window (commands in RUNBOOK).
6. Prove every arm's tagged events arrived and every exporter flushed before
   querying Loki by each workflow ID, `ecosystem.task.id`, and the Codex
   environment tag. Field preservation remains a prerequisite, not an assumption.
7. Reconcile call states under M14 and Codex cumulative usage per thread/attempt
   under G-C. Retain unsuccessful, interrupted and superseded attempts.
8. Write a sanitized aggregate receipt quoting retained output only. Apply the
   pass/incomplete/fail rule and the independent reviews; do not run a new E2E
   to fill this preregistration PR.

## Overturn conditions — AA §8.5

- **WP5 table:** overturned if B's correctness falls below A's, or its priced estimate exceeds A's by more than 10%.
- **Allowlist lever:** overturned if stack-researcher, which keeps Bash, does no better than `general-purpose` on M1 and M3.
- **SubagentStart-for-Workflow evidence:** withdrawn if a release note or a rerun shows a `workflow-subagent` child without `hook_additional_context`.
- **D2:** overturned by the spawn probe.
- **Strict blind process:** `--safe-mode` is withdrawn if any hook, plugin, MCP or CLAUDE.md content reaches it, or if verdict parity fails. `--bare` then waits for the user's decision on an API-key route.

## Foundation acceptance — full-save §4.6 (verbatim)

Section references inside this quotation refer to full-save (or AA where named).
The M-R1/M-R2/M-R3 clause is quoted, not redefined or implemented by this unit.

The foundation counts as accepted only when all of these hold:
- The E2E passes by AA §8.3's outcome rule:
  - every **required** M row passes: M1, M2, M3, M4, M5, M6, M6c, M7 (seeded), M8's required lanes, and M11–M15;
  - every G row passes: G-Q, G-C, G-T, G-P and G-S;
  - a required lane with fewer than 5 eligible opportunities, or a failed positive control, makes the E2E incomplete, never a pass.
- Optional rows are reported without thresholds: M7 on natural payloads, M9, M10, socraticode where granted, and codebase-memory if Q3 passed. So is M2b. An optional row's N/A never blocks acceptance, and N/A never counts as a pass of a required row.
- M-R1 ≥ 95% of eligible parts, M-R2 = 0 and M-R3 = 0.
- The capability gate (AA §8.1b) passes for every lane that §1 marks as a target.
- Every §2 switch has its receipt.
- Reviews follow AA §8.7: the Claude evidence-reviewer, then the GPT-6 cross-family review, then one repair round.

The first-full-seven-day M-R1 window and baseline remain PR-A's responsibility
(full-save §4.1; §5 step 4 supplies the continuation and regenerated baseline).
PR-H freezes M-R1 after PR-A's baseline (full-save §4.1:547); that freeze remains
pending. The ≥95% value above is the quoted foundation target. Step 13 is the
E2E and seven-day measurement, not PR-A's continuation. This adoption E2E does not establish WP8 savings:
WP8 needs at least 30 matched pairs per family, at least three repeats, cold
and warm cache separately, fixed routes, one change per arm, all overhead and
uncertainty (AA §8.6). No savings-inside-noise result is accepted.

## Merge-before-run dependencies and unverified boundaries

Statuses below were frozen at this preregistration's build, not claimed as
current host adoption. No dependent live action was run here.

| Dependency | Real build status | Required before organic execution |
| --- | --- | --- |
| [PR #376](https://github.com/seathatflowsinourveins/native-agent-stack/pull/376), `claude/stack-agents-dispatch-20260926` | **Merged** at `623d34fa` (2026-09-27T03:38:47Z) — confirmed after this preregistration's own repair round, by `origin/main`'s advancement past this unit's base. `adoption/agents/claude/{stack-researcher,stack-verifier,security-reviewer}.md` are present on `main`, mirrored under `examples/claude-native/agents/`. | Prove actual installed role bytes and real child `meta.json` types at the execution checkout's HEAD (AA §8.4 step 2) — a repo-tree merge is not yet a host install/read-back proof. This supplies B's role table. Security-reviewer is a carrier addition, not a fabricated AA §8.2 E2E role. |
| Codex `stack-worker` carrier | **Unmerged, in progress, not a PR and not pushed**. Local checkpoint `a6ed3c57` on `claude/codex-lane-token-stack-20260926` is supplied build-status evidence. Candidate files: `adoption/templates/codex.stack-worker.config.toml`, `tools/adoption/apply_codex_lane.py`, `tools/adoption/prove_codex_lane.py`, `docs/decisions/2026-09-26-codex-worker-lane.md`. | Resolve the author's recorded cleanup-liveness, pass/fail-verdict and evidence-README overclaim defects; publish, review and merge; qualify profile/custom-agent read-back and binding. It is never an accepted carrier merely because that checkpoint exists. |
| [PR #364](https://github.com/seathatflowsinourveins/native-agent-stack/pull/364), telemetry writer identity | **Merged** at `c71d66d0` (2026-09-27T02:45:15Z) — confirmed after this preregistration's own repair round. **The field-preservation gap persists after merge**: `origin/main`'s `observability/collector/collector.yaml` `keep_keys` lists (resource-level and attribute-level) still omit `workflow.run_id` and `tool_use_id`, checked directly against the merged file, not the pre-merge head this preregistration originally cited. | Prove all requested joins and exporter flushing once a follow-up adds the missing fields — merge status alone no longer blocks this row, but the field gap still does. See RUNBOOK's conditional queries and pinned sources. |
| PR-A | The builder's search (no Git access) found no PR; **integrator addendum**: PR-A's base branch (`claude/child-lane-usage-measurement-20260926` @ `152f49c2`) did merge, as **#369**, confirmed by its exact AA §6 file-list match — but only the baseline snapshot, measured with current, pre-fix tooling (`child-usage.mjs:277` still examines only `SubagentStart`). No branch/PR continues the remaining tooling-fix scope. | Merge the full-save §5 step 4 / AA §6 measurement extensions (not #369, which is already merged) and publish their baselines before relying on all-carrier containment, nested fetches, all-hook injection, call states or complete usage. |
| PR-R | Token-practice records/recipes on `claude/rtk-recipes-records-20260926`; full-save F1–F9. | Separate records work, **not PR-D**, roles or the Codex profile. No acceptance is inferred from a possible `docs/decisions/2026-09-26-token-practice-f1-f9.md`. |

The real pending-profile invocation is `codex exec -p stack-worker -m gpt-6-astra
-c model_reasoning_effort="max" -c web_search="live" -s <sandbox> ...`,
from its candidate template header line 3. That source was read as a local
candidate; this builder did not establish its commit ancestry or host acceptance.

Preserve AA §10's **[nv]** boundaries: restricted-allowlist server instructions;
plugin-scoped preload; whether profile layers carry hooks; the D2 spawn inference;
strict blind/Q2 isolation; per-key telemetry settings reload; the per-launch
Codex tag and Workflow-child resource propagation; and persistence of failed-turn
`token_count` usage. Compaction is untested if absent. Non-daemon bridge calls
and missing usage stay unknown. A sandboxed Codex worker may not write RTK
history. The secret-guard bypass through context execution remains inspected
under G-S until H6 is decided. No flag, metadata file, syntax test or old receipt
silently promotes any of these to verified behavior.

## Sealing

Repair 1 seal, **2026-09-26**, before any organic run. Recompute these SHA256
values from the merged preregistration commit before capability probes and
before launching any arm; a mismatch stops launch. A hash establishes byte
identity, not merge chronology or a completed model run. The integrator must
record the actual merge revision/time and prove it precedes execution.

| Artifact | SHA256 |
| --- | --- |
| `preregistration.json` | `e04c1a08de610356e2f24cf8d1f59a70e8b630e093c93934cd03ab0a8091bee4` |
| `token-e2e-run.mjs` | `6ca129d94d51c6c99c5a9430e2b7fb0d23b0919001acf789bf5d59d74c7cb828` |
| `RUNBOOK.md` | `a8ee0e09ce001db21269f66dc5ec4a4aa39abc3020e86e37d610a4aa9236c5a4` |
| `fixtures/table.json` | `fdf314394a9854039da18b2f827f8caf2d8ffb3651594733eb84699f74c09448` |
| `fixtures/events.jsonl` | `81ef838c18cc81006269024e7270b991dbdfcb72bf223dec324f2fba9307930e` |

The reused table pointer is separately sealed by each task's `frozen_input`;
it must be extracted from the preregistration commit, not a regenerated matrix.
The existing `receipt_sources` hashes remain historical source identities.

Any future change to this preregistration requires an **append-only, dated
Amendment section**, never a silent rewrite. Preserve prior amendments and seal
tables, identify the rules/artifacts being superseded, state the reason and
whether any results were already observed, and record the replacement hashes
and merge chronology before execution. No retroactive eligibility or threshold
recoding is permitted. Source: [retrieval-quality-v2 Sealing and Amendments](../../../blueprints/retrieval-quality-v2/PREREGISTRATION.md#sealing).

**Amendment 2 (2026-09-27):** the Repair 1 table above is kept as history; the
launch check uses the Amendment 2 seal below.

**Amendment 3 (2026-09-28):** the Amendment 2 seal is also kept as history; the
launch check uses the Amendment 3 seal below.

## Amendment 1 (2026-09-26): repair after independent reviews, before execution

This authorized repair changes the unexecuted preregistration in response to
the Claude and GPT-6 reviews. No Workflow, model, capability probe or organic
experiment ran during the repair. The new seal above covers the corrected
artifacts. The original public fixtures and all 77 information-need definitions
remain; a blocked task is retained, never deleted or credited as passed.

| Finding | Correction and source |
| --- | --- |
| 1 | JSON now holds the five-opportunity minimum, every AA §8.3 M/G criterion, three M3 exceptions, Q1 strict candidate, outcome and §8.5 overturn rules (AA §6:405–411). |
| 2 | Arm A moves from binding-3 to binding-4 for full history, with no role/agent_type; binding-1's none/role case is expressly retained by the repair request (AA §8.2:581). |
| 3 | Builder checks follow the observed child tree, preserve isolation, and require hooks preflight/restoration (`isolated-builder.md:7,10`; `test-envelope.mjs:418`; `harness-defaults.md:89`). |
| 4 | AA §6's baseline.json is explicitly deferred; #369 is pre-fix reference evidence. M-R1 freeze follows PR-A's baseline (full-save §4.1:547; §5 step 4, not step 13). |
| 5 | The runner error now names preregistration.json. |
| 6 | Python/JavaScript denylist checks recognize underscore-separated names and include the nine omitted handbook entry points (handbook 106–151; Python re lookaround semantics). |
| 7 | Denylist sources are the canonical 24-component inventory and handbook; scratch-only carrier citation removed. |
| 8 | Recursive evidence privacy and explicit model/effort/count guards now cover this standalone runner; mutation checks demonstrate their sensitivity. |
| 9 | This seal and amendment procedure follow retrieval-quality-v2's retained-history convention. |
| 10 | Reused tables bind the hashed preregistration-commit pointer through retained-input, following the existing retained-history binding. |
| 11 | Claude-only scout/reviewer role lanes are explicitly excluded from Codex bindings; shared exec needs remain (AA §6:372). |
| 12 | The loopback task is blocked until an equivalent permitted role is named and qualified; source-scout's network prohibition is unchanged. All arms refuse to start with this unresolved slot. |
| 13 | The sole main task is xhigh; every child remains max (AA §8.2 Claude main; AGENTS.md Workers). |

The task-specific anti-pattern log is this amendment table, with enforceable
contracts in `tests/test_token_e2e_preregistration.py`. It records the proven
mistakes without promoting offline checks to organic adoption evidence.

## Amendment 2 (2026-09-27): adopt the #402 role bodies before execution

This dated amendment changes the merged, unexecuted preregistration. PR-H
merged as #381 at `c7b78854` (2026-09-27T06:39:20Z). No organic run,
capability probe or Workflow of this protocol has run since, so
no result was observed before this change. **Reason:** the user's 2026-09-27
rule that every verification and build stage runs on Opus 5.5 at effort max.
#402 (`d022295a`, 2026-09-27T14:04:25Z) made the same
change to `adoption/agents/claude/{stack-verifier,isolated-builder}.md`, removed
the builder's frontmatter `isolation: worktree` and added project-scope copies
in `.claude/agents/` ([harness-settings record](../../../docs/decisions/2026-09-27-claude-harness-settings.md),
“Effect on frozen preregistrations”; [role-dispatch addendum](../../../docs/decisions/2026-09-26-stack-agents-role-dispatch.md#addendum-2026-09-27-opus-builder-and-verifier-no-frontmatter-isolation)).
A per-invocation `model` outranks the definition's `model`
([sub-agents](https://code.claude.com/docs/en/sub-agents), model resolution
order), and every task here passes one, so the definitions alone would not
change the run. The amended routes hold in B, A and A0, which share each task's
model. Tasks, eligibility, lanes, thresholds, M3 exceptions, checks and arm
order are unchanged, and so is all task text except the frozen `<assigned-base>`
placeholder that change 7 adds to the two builder tasks; nothing is recoded. Neither role's
Sonnet-era qualification carries over: the capability gate qualifies the Opus
routes. Amendment 1 and the Repair 1 seal stay above as history.

| Change | Superseded rule or artifact | Replacement and source |
| --- | --- | --- |
| 1. Role models | `stack-verifier` and `isolated-builder` at `sonnet` in the role table, in the six Claude `stack-verifier` tasks (`reuse-296-00`, `seed-acceptance-1` to `-5`) and the two `isolated-builder` tasks (`seed-builder-1`, `-2`), and in the runner's role map | `opus`, effort still `max`. Codex tasks stay on `gpt-6-astra`, including the `stack-verifier` task `reuse-343-13`. `source-scout` stays `sonnet` for pure extraction. The blocked `reuse-296-15` slot and its `role_requirement` are unchanged. Source: `adoption/agents/claude/stack-verifier.md:5` and `isolated-builder.md:5` at `d022295a`. |
| 2. Carriers | “#376 role body, after merge/install proof” (verifier); “Existing role plus #376 additions” (builder, scout) | “#402 role body at d022295a”. #402 leaves the `stack-researcher` and `evidence-reviewer` bodies unchanged; their rows stay and say so. |
| 3. Builder worktrees | README: “B's `isolation: worktree` may create another tree”, “A/A0 use their prepared control trees when the harness creates no separate tree” and “Keep the role's isolation”; the RUNBOOK builder section's Repair 1 isolation rule and its `worktree_paths` row's “prepared control binding”; Amendment 1 finding 3's “preserve isolation”; the runner comment citing `isolated-builder.md:7` | Every arm's builder brief carries the frozen prepared path from `worktree_paths` (change 7 adds its base). The grader derives the edited tree from the child transcript and `meta.json` and requires it to be that path; any other tree is a conflicting identity that blocks grading. `builder_worktree_policy` keeps its eight Repair 1 fields and adds seven. The hooks preflight/restore and per-tree sentinel checks stay. The role's base refusal stays; change 7 names the base in the brief. Sources: `isolated-builder.md:3,12` at `d022295a`; `test-envelope.mjs:418–427`; `docs/harness-defaults.md:91`; sub-agents on `isolation` and a subagent's starting directory. |
| 4. Load order | RUNBOOK freeze: agent bytes recorded without scope precedence | Project `.claude/agents/*.md` (priority 3) shadow user `~/.claude/agents/*.md` (priority 4). The freeze record retains both and requires byte identity with `adoption/agents/claude/*.md` at the execution HEAD, read back. Sources: sub-agents, “Choose the subagent scope”; decision 3 of the harness-settings record. |
| 5. Tests | `tests/test_token_e2e_preregistration.py` without these contracts | Five new and two extended tests: models, role-map/JSON and role-table/JSON agreement, carriers, builder policy and text, load order, and this seal. Against the unamended artifacts, `python3 -m unittest tests.test_token_e2e_preregistration` exited 1 (27 tests, `FAILED (failures=42)`, all in those seven tests); it passes on the amended artifacts. |
| 6. Seal | Repair 1 seal table (kept) | The Amendment 2 seal below; `manifests/evidence.json` re-registered with `register_file` from `scripts/host_receipts.py` ([hot-file protocol](../../../docs/lanes.md#hot-file-protocol)). |
| 7. Builder base binding (repair round, 2026-09-27; GPT-6 cross-family review) | `seed-builder-1` and `-2` text naming only `<assigned-worktree>`, so no B-arm builder could pass `isolated-builder.md:12`'s stop when `git -C <path> rev-parse HEAD` is not the brief's base; change 3's “task text unchanged” and its **[nv]** deferral of that refusal; the RUNBOOK builder section's “names that path but no base revision” | A **pre-execution input binding**. Both builder texts add `, prepared at the exact base <assigned-base>` directly after `<assigned-worktree>`; nothing else in them changes. A new frozen binding, `worktree_bases`, recorded privately before probes like `worktree_paths`, maps each `worktree_required` Workflow task to the full revision its prepared tree was created at; builder trees are prepared at the frozen execution revision. The runner requires a 40-hex value for each such task and the placeholder in both builder texts, binds it, and refuses to start when a value is missing or malformed or a placeholder stays unbound, following `dispatch_policy.workflow` (only frozen neutral input/worktree/run placeholders are bound). The two reused worktree tasks (`reuse-296-00`, `reuse-296-11`) get a recorded base but no text change. Arms A and A0 reuse the identical task text, so they receive the same bound placeholders. `builder_worktree_policy` adds `base_binding: worktree_bases`. The builder's base refusal stays, and its capability probe uses exactly this brief shape (change 9). No organic result was observed; this changes no eligibility, lane, threshold or check. Source: `isolated-builder.md:3,12` at `d022295a`. |
| 8. Role-body blobs (repair round; evidence-reviewer) | Carriers naming “#402 role body at d022295a” with no rule tying the executed bodies to those blobs; change 4's identity with `adoption/agents/claude/*.md` at the execution HEAD alone | The role-body SHA256 table below records each body at `d022295a`. The RUNBOOK freeze requires the executed copies in `.claude/agents/`, `~/.claude/agents/` and `adoption/agents/claude/` to equal these values; any later change to these bodies needs another dated amendment. A test checks the two repository copies. |
| 9. Capability probe shape (repair round; evidence-reviewer) | RUNBOOK capability section with no builder brief rule | The B-route `isolated-builder` probe must use exactly the frozen brief shape: the prepared path plus `<assigned-base>`, and no other base text. A refusal on that shape is a retained gate failure. |
| 10. Tests and seal (repair round) | Round-1 tests; the unmerged round-1 Amendment 2 seal | Six new tests and one extended test (`base_binding` in the builder policy) cover the builder text, the runner's base binding and refusal (source checks plus a stubbed-`agent` Node harness over an in-memory copy with `reuse-296-15` unblocked: a local synthetic check, not a Workflow run), the role-body table, the probe shape and the superseded phrases. Against the pre-repair artifacts, `python3 -m unittest tests.test_token_e2e_preregistration` exited 1 (33 tests, `FAILED (failures=52)`, all in those seven tests); it passes on the repaired artifacts. The seal below is recomputed. |

**Role-body SHA256 table (repair round).** SHA256 of
`git show d022295a:adoption/agents/claude/<file>`; #402 made each
`.claude/agents/<file>` the same blob. The RUNBOOK freeze requires every
executed copy to equal these values.

| Role body | SHA256 at `d022295a` |
| --- | --- |
| `stack-verifier.md` | `a4cc7f5024af7fdea544a0963d8ff6f712c9eb460812582fd93368870eeeabcc` |
| `isolated-builder.md` | `57452a64ca8b97996aeb35916fb1f1f4d06452857178d6ad6dc7c49723d84cf7` |
| `source-scout.md` | `f79cead4a3f9c14986bb28815d046eacf8bf79c92fe923094f66f97a64c06341` |
| `stack-researcher.md` | `a35b015fcf7e8d608b5cf60e4172c6f1033bf4d9b3b8047a008efc5e89dcb446` |
| `evidence-reviewer.md` | `3aa5e3f0aac4b43f7196cb46aee3ce1ef06e795ae93ba2a925ea53ac62f5e256` |

**Merge chronology.** #381 merged this preregistration at `c7b78854`
(2026-09-27T06:39:20Z); #402 merged at `d022295a` (2026-09-27T14:04:25Z); this
amendment was written on `d022295a` and, in the repair round, rebased onto
`f68d13c0`, which leaves the five role bodies in the table above unchanged.
Record this amendment's merge revision and time before execution: both must
precede every capability probe and organic arm, and that revision is the
`preregistration_commit` checked at launch. At `d022295a` and at `f68d13c0` the
reused table pointer still serializes to the sealed `frozen_input` bytes (6,552
bytes, 60 records, the same SHA256).

**Amendment 2 seal, 2026-09-27**, before any organic run. It replaces the
Repair 1 table for the launch check; the **Sealing** rules apply unchanged.

| Artifact | SHA256 |
| --- | --- |
| `preregistration.json` | `d41152f460c475e6dabe0d8c144e7bd0ef59c0181835afbbba58a6eed445e81a` |
| `token-e2e-run.mjs` | `eb7029f9c7f5d6672525b0c8cb59263b78a29b40bc4254cf84a666e99dc47913` |
| `RUNBOOK.md` | `33810ef7b1583163abb81f3111cfcfc9927863a1f2930d6f9f3de9bcafd2ca93` |
| `fixtures/table.json` | `fdf314394a9854039da18b2f827f8caf2d8ffb3651594733eb84699f74c09448` |
| `fixtures/events.jsonl` | `81ef838c18cc81006269024e7270b991dbdfcb72bf223dec324f2fba9307930e` |

Replacement hashes: `preregistration.json` `e04c1a08…` → `bd892944…`;
`token-e2e-run.mjs` `6ca129d9…` → `18419164…`; `RUNBOOK.md` `a8ee0e09…` →
`537eb193…`. Both fixtures are unchanged.

Repair round (2026-09-27), before merge and any execution:
`preregistration.json` `bd892944…` → `d41152f4…`; `token-e2e-run.mjs`
`18419164…` → `eb7029f9…`; `RUNBOOK.md` `537eb193…` → `33810ef7…`. The
round-1 values were never merged or used by a launch check; both fixtures are
still unchanged.

## Amendment 3 (2026-09-28): the isolated-builder body without verification-before-completion, before execution

This dated amendment changes the merged, unexecuted preregistration. Amendment 2
merged as #413 at `27bf3108` (2026-09-27T16:35:23Z). No organic run,
capability probe or Workflow of this protocol has run since, so
no result was observed before this change: at `3058b237` this README's status
still reads “frozen protocol, not executed or accepted”, and the coordinator of
this change reports that the E2E has not started. **Reason:** the skills trial
removed `verification-before-completion` (obra/superpowers `8ca22db`) under its
conflict rule, [`docs/decisions/2026-09-25-skills-trial-and-usage.md`](../../../docs/decisions/2026-09-25-skills-trial-and-usage.md#overturn-conditions)
L284-286: a trial skill that “gives instructions that conflict with
CLAUDE.md/AGENTS.md once actually read in full → remove it immediately, not at
the trial window's end”. That record's 2026-09-28 removal addendum records the
removal. The decision (M4) is in the practice-sweep session's record,
[`docs/decisions/2026-09-28-delegated-decisions.md`](../../../docs/decisions/2026-09-28-delegated-decisions.md#m4-remove-the-trial-skill)
(#462, `c1581fa2`), with the GPT-6 verdict at
[`m4/gpt6-return.md`](../delegated-decisions-20260928/m4/gpt6-return.md) and the
Claude readings in
[`coordination.md`](../delegated-decisions-20260928/coordination.md#m4-claude-readings).
The removal changes the
`isolated-builder` definition, whose `d022295a` SHA256 Amendment 2 pins, and the
builder's token-lanes block. Tasks, eligibility, lanes, thresholds, M3
exceptions, checks, arm order, task text and every route's model and effort are
unchanged; nothing is recoded. The builder body's prepared-path and base-refusal
sentences are byte-identical (the body line moves from L12 to L11 because the
frontmatter loses one line), so Amendment 2's changes 3, 7 and 9 still hold. No
capability probe has run, so the capability gate qualifies the amended body.
Arms A and A0 dispatch `general-purpose` or no `agentType`: neither loads this
definition or its role block, and the default block is unchanged. Amendments 1
and 2, the Repair 1 seal, the Amendment 2 role-body table and the Amendment 2
seal stay above as history.

| Change | Superseded rule or artifact | Replacement and source |
| --- | --- | --- |
| 1. Builder body and preload set | `isolated-builder.md` at `d022295a` (`57452a64…` in the Amendment 2 role-body table): frontmatter `skills:` `context-mode:context-mode` and `verification-before-completion`; the body's last sentence, “Use the preloaded verification-before-completion skill before claiming success; when the brief names another project skill, Read its SKILL.md path.”; the role table's builder carrier “#402 role body at d022295a” | The preload set is `context-mode:context-mode` alone, and the sentence becomes “When the brief names a project skill, Read its SKILL.md path.” The rest of the file is byte-identical. The role table's carrier reads “#402 role body at d022295a as changed by Amendment 3”. The role-body row below replaces the `57452a64…` row for the launch check; the other four rows are unchanged, and both repository copies of each still match them at `3058b237`. Source: the skills-trial record's 2026-09-28 removal addendum. |
| 2. Builder token-lanes block | `adoption/hooks/claude/token-lanes-block.builder.md` `c665c230…` (2,747 bytes), which carried no evidence rule because the preload did ([verification-line addendum](../../../docs/decisions/2026-09-27-token-lanes-subagent-start.md#addendum-2026-09-28-verification-line)) | `c81a91c4…` (2,877 bytes): the default block's line-13 first sentence, “Show evidence before a success claim: the command and what it returned (code.claude.com best practices), or the file:line read.”, appended as the last line; `adoption/hooks/claude/SHA256SUMS` lists it. [Procedure step 2](#procedure--aa-84) already freezes carrier hashes at execution, so no rule changes here. Source: the token-lanes record's “Addendum 2026-09-28: builder evidence sentence”. |
| 3. Freeze rule | RUNBOOK freeze, repair round: all three copies “must also equal the SHA256 recorded there for `d022295a`”; this README's role section: “The executed role bodies must equal Amendment 2's role-body SHA256 table.” | Both keep their text and gain a dated Amendment 3 sentence: for `isolated-builder.md` the required value is the Amendment 3 row below. |
| 4. Tests | `tests/test_token_e2e_preregistration.py` with `57452a64…` as the repository copies' current value, the #402 builder carrier as the current role-table row, and the Amendment 2 seal as the current seal | One new test (the Amendment 3 row, its phrases, both dated sentences and a builder body that names no removed skill) and two extended tests: the role-body test checks the repository copies against the current rows, and the seal test keeps the Amendment 2 seal rows as history and requires the current hashes in the Amendment 3 seal; the role-table constant carries the new carrier text. Against the unamended README and RUNBOOK, with the amended builder body, `python3 -m unittest tests.test_token_e2e_preregistration` exited 1 (34 tests, `FAILED (failures=20)`: 12 in the new test, 7 in the seal test and 1 in the role-table test); it passes on the amended artifacts. |
| 5. Seal | Amendment 2 seal table (kept) | The Amendment 3 seal below; `manifests/evidence.json` re-registered with `register_file` from `scripts/host_receipts.py` ([hot-file protocol](../../../docs/lanes.md#hot-file-protocol)). |

**Role-body SHA256 table (Amendment 3).** SHA256 of the amended
`adoption/agents/claude/isolated-builder.md`; `.claude/agents/isolated-builder.md`
and `examples/claude-native/agents/isolated-builder.md` are the same bytes. It
replaces only the `isolated-builder.md` row of the Amendment 2 table, which stays
above as history; the RUNBOOK freeze requires every executed copy of the builder
to equal this value.

| Role body | SHA256 after Amendment 3 |
| --- | --- |
| `isolated-builder.md` | `0f8e0834012ec80af39398bfb948b0fe7f0b6dff8effaf06f264d20eb3ed5db7` |

**Merge chronology.** #381 merged this preregistration at `c7b78854`
(2026-09-27T06:39:20Z); #402 merged at `d022295a` (2026-09-27T14:04:25Z);
Amendment 2 merged as #413 at `27bf3108` (2026-09-27T16:35:23Z). This amendment
was written on `3058b237` (2026-09-28T14:45:48Z). Record its merge revision and
time before execution: both must precede every capability probe and organic arm,
and that revision becomes the `preregistration_commit` checked at launch. At
`3058b237` the reused table pointer still serializes to the sealed
`frozen_input` bytes (6,552 bytes, 60 records, the same SHA256); re-verify it at
the merge revision.

**Amendment 3 seal, 2026-09-28**, before any organic run. It replaces the
Amendment 2 table for the launch check; the **Sealing** rules apply unchanged.

| Artifact | SHA256 |
| --- | --- |
| `preregistration.json` | `d41152f460c475e6dabe0d8c144e7bd0ef59c0181835afbbba58a6eed445e81a` |
| `token-e2e-run.mjs` | `eb7029f9c7f5d6672525b0c8cb59263b78a29b40bc4254cf84a666e99dc47913` |
| `RUNBOOK.md` | `135340b608e0a0229822e52508bb74f6afdbd34e5a2ba500694a67d8a0e62427` |
| `fixtures/table.json` | `fdf314394a9854039da18b2f827f8caf2d8ffb3651594733eb84699f74c09448` |
| `fixtures/events.jsonl` | `81ef838c18cc81006269024e7270b991dbdfcb72bf223dec324f2fba9307930e` |

Replacement hash: `RUNBOOK.md` `33810ef7…` → `135340b6…`.
`preregistration.json`, `token-e2e-run.mjs` and both fixtures are unchanged.

## Pre-run record (2026-09-28): Amendment 3 merge and recovered inputs

This dated record is not an amendment. No task text, information need, check,
arm or route changes, and the five sealed files are untouched. No capability
probe or organic arm has run.

**Amendment 3 merge.** #464 merged Amendment 3 at `c0966da2`
(2026-09-28T18:29:54Z). That revision is the `preregistration_commit` checked
at launch. The following were re-verified at `c0966da2`:
- The reused table pointer serializes to the sealed `frozen_input`:
  `6899e551b2bea3918b47cba1b41e27e59d8f5cb12a681f98cc77f73d66a2a2c1`, 6,552
  bytes, 60 records.
- All three copies of each of the five role bodies equal their pinned rows:
  Amendment 2's table for four of them, and Amendment 3's row for
  `isolated-builder.md`.
- `python3 -B -m unittest tests.test_token_e2e_preregistration` ran 34 tests,
  OK.

The six token-lanes blocks at that revision, for the launch's carrier check:

| Block | SHA256 | Bytes |
| --- | --- | --- |
| `token-lanes-block.md` | `d6c3c19d6e94d3f48d2788963c8c9be45ec57e6bb81cab92b2c30d9fd5c8e8d6` | 4,088 |
| `token-lanes-block.builder.md` | `c81a91c4ffb2fa906feb403d5a11bd294b6cf2db45795d80f9acd662c5004973` | 2,877 |
| `token-lanes-block.researcher.md` | `47cc80b262468557b8cfe5c243598030757270674bc7bf286fba8c0c573abc28` | 3,075 |
| `token-lanes-block.reviewer.md` | `19857a44a201948aa1d1fc9be3e24d5f3f7cc385f333ab3893411889258af4ed` | 2,088 |
| `token-lanes-block.scout.md` | `81784c2edc0cc95c0c0eb3b443b5b228dd41e970236239553c66af90ddfc7eae` | 1,089 |
| `token-lanes-block.verifier.md` | `a2eb3298126efd82622150e5717f10eb700f4aa3076d027c86ae1fe653f29eb0` | 2,186 |

On the workstation host, the installed copies of these six blocks and of the
builder body equal these bytes (read back on 2026-09-28). Another host
establishes its own read-back.

**Pre-run inputs.** Two pre-run input gates are satisfied here:
- the command-fidelity gate for `reuse-296-00` and `reuse-343-13`, whose
  `pre_run_input_gate` reads “Recover and seal the exact six original
  observation identities and inputs before capability probes”;
- the retained history report: “A missing retained history report also
  blocks launch”.

**Command identities (`reuse-296-00`, `reuse-343-13`).** Both source runs'
original work files survived in an earlier session's scratch directory. Their
SHA256 values equal the receipts' `exact_comparison` digests:

| Source | Baseline (raw) | Filtered output |
| --- | --- | --- |
| #296 `/tools/0`, run at `f5812d3f` | `765a3f2e5dc893fb0a95413d583055de47319140a8c760a07ada6c300442ecf5` | `b8b26c4238e3e8d9d3fbfeba8fe810357ea1269b27597bcc86e98bde8b2ecb07` |
| #343 `/tools/13`, run at `c09dd6df` | `9c2e4e94e8b718541271823a9f6ec42653ed2f742d9d1c688eab3700ab73f330` | `4e8cb518f78cb024e28f9ed6e31eb832e3dbf33622cb171d441ed995df00b1c4` |

The six identities, in their original order, and the information need each one
serves in the frozen task text:

| # | Command | Information need |
| --- | --- | --- |
| 1 | `git log -30` | newest commit subject |
| 2 | `git status` | branch state |
| 3 | `git diff HEAD~5 --stat` | changed-file summary over the last five revisions |
| 4 | `grep -rn "def register_file" scripts` | matches for `def register_file` under `scripts` |
| 5 | `ls -la scripts` | directory inventory |
| 6 | `python3 -m unittest tests.test_host_requests` | test count and result status |

#296's digest-verified baseline carries these six commands as its section
headers, `=== [1] git log -30 ===` through
`=== [6] python3 -m unittest tests.test_host_requests ===`. #343's run result
lists 13 commands, and the receipt's `commands` field kept only the first
eight (with the scratch path sanitized), which end at command 4. Its
digest-verified baseline has no headers, but it contains the `ls -la` listing (a `total` line and directory entries) and the
unittest result lines `Ran 49 tests` and `OK (skipped=1)`. Commands 5 and 6 are
therefore covered by hashed bytes as well.

The identity is the bare command; the channel is provenance. #296 ran each
command as plain Bash inside an Ultracode subagent: the RTK hook rewrote it, and
the baseline came from `rtk proxy`. #343 ran `timeout 60s rtk <command>`
(`timeout 180s` for the unittest) with an environment prefix and `</dev/null`,
and its baseline came from `rtk proxy`. The historical counts (49 tests,
`OK (skipped=1)`) are not the new run's expected values. The checker compares
each arm's answer with that run's own retained raw originals.

**History originals (`reuse-296-02`, `reuse-343-06`).** Each receipt's
`baseline_sha256` is reproduced exactly by
`git --no-pager log --stat -150 <revision>` at that receipt's own
`catalog_revision`. The match was found by hashing this output for all 597
commits on all refs in this checkout, with committer dates from 2026-09-24T00:00 to
2026-09-27T12:00 (host local time), with git 2.43.0:

| Task | Source entry | Revision | SHA256 | Bytes |
| --- | --- | --- | --- | --- |
| `reuse-296-02` | #296 `/tools/2` | `f5812d3f2266` | `82e9249222bafd5daee41ee74840a92d2a00feabd70f4e1149adb21a600d630b` | 891,615 |
| `reuse-343-06` | #343 `/tools/6` | `c09dd6dfc68d` | `5939b5451e55a3744b7a8f299733904979046974a5c2aea340ecb6b3b9149c2c` | 774,521 |

The reports are retained privately and not committed, because they carry commit
author identities. The byte match holds under this host's git version and
configuration. After a git upgrade, or on another host, verify the retained
bytes against these digests instead of regenerating them. Each launch maps
the tasks to the retained files in `input_paths` (RUNBOOK run-configuration
table: history originals keep identical bytes and hash across arms). Verify
those files against these digests before probes.

**Still open before launch:**
- PR-A's residual measurement scope (#432's Residuals) and its regenerated
  sanitized baseline, both merge-before-run;
- the Codex half of the collector join;
- a sealed quiet window W.

## Amendment 4 (2026-10-07): prospective current role-body replacement rows

This append-only amendment records replacement source pins for three adopted
role bodies at `3ba087b28ef4910d6208b8bc81d295badc5be087`, composed with the
landed foundation at `b59337210a7a1cdf9fada8a6c7d135d4793ad023`. These rows
are re-derived from the candidate before the authorized source push. The command
center records the actual landing head and merge chronology at landing.
It supersedes only the `isolated-builder.md`, `stack-researcher.md` and
`evidence-reviewer.md` body-hash requirements in Amendment 2, Amendment 3 and
RUNBOOK's Freeze and preflight role-body paragraph. The other two Amendment 2
body rows remain required; identity across adoption, project and installed user
copies still blocks a future launch on a missing or differing copy.

| Role body | SHA256 after Amendment 4 |
| --- | --- |
| `isolated-builder.md` | `e22c8f8d5d5239ddce211aad69e695b2952951bab7142998f0c12445cd399096` |
| `stack-researcher.md` | `5fea67ac0e615b420871b6302558dbce3025e052259545e9eeb0020991e55240` |
| `evidence-reviewer.md` | `84e7ec7b433fc6ef3506a2488c5641b9ed8d88bae8f296b197b182964fa31399` |

All prior text and seals remain history. The sealed protocol, runner, RUNBOOK
and fixture bytes are unchanged, so their existing Amendment 3 seal still
applies. Previous executions retain their original body identities and
interpretation; no earlier record is rewritten or recoded.

Current execution/result status was not established by this structural CI
repair. The owner must resolve that status before any future execution, using
the command center's landing chronology. This amendment is not a run,
qualification, result or execution authorization.
