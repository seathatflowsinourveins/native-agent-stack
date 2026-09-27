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
`<assigned-worktree>`, `<retained-input>` and `<run-token>` to pre-recorded
neutral paths and the run token; no instructions are appended. Identical source
bytes and observation contracts apply across arms. Freeze all six distinct
builder checkouts plus the per-arm observation checkouts and disposable clones.
These are prepared bindings: B's `isolation: worktree` may create another tree.
For builder tasks, derive the actual tree and starting revision from the child's
native transcript and `meta.json`, and read the diff there, per
`builder_worktree_policy`. Missing or conflicting identity blocks grading.
A/A0 use their prepared control trees when the harness creates no separate tree.
Keep the role's isolation; RUNBOOK's builder section freezes the hooks preflight
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
is the preregistered experimental exception to AA §9's ordinary dispatch rule.

| Frozen role in B | Explicit model | Explicit effort | Carrier |
| --- | --- | --- | --- |
| stack-researcher | opus | max | #376 role body, after merge/install proof |
| stack-verifier | sonnet | max | #376 role body, after merge/install proof |
| isolated-builder | sonnet | max | Existing role plus #376 additions |
| evidence-reviewer | opus | max | Existing role body |
| source-scout | sonnet | max | Existing role plus #376 additions |
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
