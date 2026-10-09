# Token practice and measured native results

Foundation-component selection and readiness follow the [2026-10-06 upstream-evidence rule](decisions/2026-10-06-upstream-evidence-over-local-evaluation.md); upstream evidence selects components and native counters record organic use, while accounting boundaries and the evidence needed to claim savings below remain.

For a new PC or a separate local ledger, use the [portable upstream counter collector](../tools/token-report/README.md). It produces local JSON/HTML reports, retains failed refreshes and never adds overlapping lifetime snapshots.

Updated September 21, 2026. The [current full-stack convergence](full-stack-convergence.md)
attaches native results, dashboard screenshots and complete component coverage.
Read this guide on demand when selecting a context
lane, interpreting native counters, or designing a measured comparison.

The [foundation setup and evidence](foundation-stack.md) adds the repaired
Python/JavaScript retrieval configuration, fresh native client checks and the
optional pinned OmniRoute install. It includes the exact returned counters,
failed comparisons and bounded telemetry-readiness method for future hosts.

The current selection has **68 component records**. The broader catalog has
**513 repository identities: 342 public stars and 171 beyond stars, with 1,072
typed references**. The earlier audit retains its 52-component scope, and the
full-catalog TOON receipt retains the 502-repository input actually measured.
These are bounded catalog counts, not a universal ranking, 68 successful full
E2E runs, or savings from every repository. Supporting runtimes and historical
alternative installations retain separate scope.

The offline HTML setup guide (`ecosystem/index.html`, generated with
`python3 scripts/build_ecosystem.py --write` -- not committed, or download it
from a `publish-catalog.yml` workflow artifact (7-day retention, `workflow_dispatch`/`v*`-tag runs only)) brings the selected stack,
layer/profile filters, native recipes, lifecycle stages and baseline choices
together. Its historical results do not become a new PC's acceptance. Use the
[lifecycle guide](../adoption/lifecycle.md) for installation ownership, restart,
recovery and rollback; collect that PC's counters with the portable reporter.

The [session observation guide](current-session-observation.md) distinguishes
directly loaded tools, explicit native commands and observed telemetry. Its
September 20 checks correlate this Desktop task's returned tool results with
the same task's Loki records; installed services alone do not establish that.

## Default practice

Carry out authorized work directly. Keep the plan and verification proportional
to the change; reuse passing evidence when its inputs and scope still match.
Do not turn a bounded fix or setup into repeated intake, planning approvals,
catalog audits or restarts. An optional component is activated when the task needs
it. Repair a failed connection individually while continuing independent work.

For profiles that select RTK global awareness, use the
[upstream installation recipe](../recipes/README.md#native-context-mode-and-hooks)
once per profile, then prove use through returned native task results. Stable
Codex uses explicit RTK commands; native Claude supports Bash rewriting. A Codex
home gets RTK's instructions from the global `AGENTS.md` block of the
[Codex worker lane](../recipes/README.md#codex-worker-lane)
(changed after `v2026.09.26.2`), because Codex does not expand the `@RTK.md`
pointer that `rtk init` writes. An installed executable alone does not prove
either behavior.
A host that runs the Claude hook at RTK 0.50.0 also needs the recipe's five
`exclude_commands` entries, which keep blob reads, `git branch`, `diff` and
standalone `jq` native. The recipe explains how RTK anchors each entry. On
2026-09-26 it grew from two entries to four: `^git show [^ ]*:` alone missed
spellings such as `git -C . show HEAD:x`. On 2026-09-27 standalone `jq` became
the fifth. Confirm the file with `rtk hook check`, since RTK can ignore
a TOML-valid file. The exclusions cover only hook rewrites, never an explicit `rtk`
command.
Preserve canonical generated instructions and the host's hook policy; historical
hook acceptance is not authorization to enable capture on every runtime.

The measured RTK caveats below moved verbatim from the Codex user-level block on
2026-10-08. The Codex role carriers in `adoption/agents/codex/` still carry the
same lines, and `tools/adoption/codex_roles.py` reads them from this section.

<!-- native-agent-stack:rtk-exceptions -->

RTK prefix/output/exit exceptions:
rtk 0.51.0 needs `--shell` for positional expansion; explicit `rtk` prefix bypasses exclusions. For the forms below use native commands or `rtk proxy <command>`:
- A skill's `SKILL.md`: read it with plain `sed -n '1,400p' <path>` (no `rtk` prefix, not `cat`/`head`/`tail`) so Codex counts the load as `codex.skill.injected`.
- `git show REV:path` (any; `git -C DIR show REV:path` too): ~8 KiB cap.
- `diff`: rtk 0.51.0 read errors exit 2 (bf23cff); 0.50.0: 1.
- `git branch`: may mark other-worktree branches remote-only.
- `git log` full: silent 10-commit cap; no merges.
- `jq`: <=40 lines of <=120 chars.
- `find`, path may be absent: exit 0, no output.

Never `rtk` shell builtins (`cd`/`export`/`source`): exit 127 stops `&&`.
<!-- native-agent-stack:rtk-exceptions:end -->

1. Retrieve what the current decision needs: exact code with rg/Serena,
   structural patterns with ast-grep, conceptual code with SocratiCode, selected
   Markdown with scoped QMD, and durable decisions with scoped ai-memory.
   For maintained decisions, including deployed architecture after compaction or
   resume, follow the scoped query and exact-path read in
   [the memory lifecycle guide](native-memory-rag-lifecycle.md#maintained-decision-routing).
2. Choose one suitable lane per artifact. RTK formats supported command output;
   Context Mode processes or retrieves bounded results; TOON suits some
   structured data only when the measured representation helps; Repomix outlines selected source; the local Headroom guard
   retains the original. Do not stack transformations to increase a counter.
3. Preserve raw output, errors, input identity and source for recovery. Read
   original implementation before correctness decisions. Lossy retrieval and
   compression can omit necessary information.
4. Preserve native caching, compaction, tool discovery, accounts and model
   behavior. Shared PATH is not host acceptance. Our own SessionStart notices print
   at most one line of 160 characters or less; they do not add schedulers,
   override providers, run audits or network checks, or rerun model trials.
   The read-only currency hook prints the `summary_line` of the due-file a
   daily user timer writes, and prints nothing when the file is absent or
   unreadable (fail-open). Its checks run in that timer, never at startup
   ([session currency notice](decisions/2026-09-30-session-currency-notice.md)).
   The repository-owned SubagentStart context carrier
   `adoption/hooks/claude/token-lanes-block.md` is a separate child-launch surface,
   not a SessionStart notice. The October 5 budget record names its 4,099 bytes
   and role variants as exempt from the main-session instruction-file ceiling;
   measure the selected child block separately, without adding it to every startup.
   Upstream plugins may inject their own documented startup blocks: preserve
   the native integration and measure its actual bytes separately from our
   hooks and instruction-file budget. For example, Context Mode documents
   its SessionStart routing injection in its
   [upstream README](https://github.com/mksglu/context-mode/blob/v1.0.169/README.md),
   and Claude documents [plugin hooks](https://code.claude.com/docs/en/plugins-reference#hooks).
   The [October 5 budget record](decisions/2026-10-05-harness-context-budget.md)
   separates these surfaces and their observed costs.
5. Count once at the proper boundary. Missing measurements are unknown.
   Never add cumulative snapshots, cache subsets, provider usage and artifact
   differences, or multiply a measured difference by repository count.

Before adopting a transformation, compare it with the cheapest adequate native
baseline for that task and verify required information. The HTML's structured
selection table keeps these decisions visible: focused known-source reads beat
an extra search; code discovery may benefit from an index; compact JSON wins
when TOON expands it; full-original tasks bypass compression followed by full
recovery. A rejected representation remains recorded but is not the default.
Supporting runtimes, security checks and recovery tools are evaluated for their
own role, not assigned invented token savings.

### Bounded metadata discovery

For native deferred tool search, use a small supported result limit and accept
the selected schemas it loads. For broad inventory reads, filter metadata outside
the model and initially return at most eight matching names, brief descriptions
and source locators, then load complete schemas only for selected tools. Report
returned counts, matched/omitted counts when known, and the next filter or
supported cursor when available; mark unavailable counts explicitly. This is a
local context budget, not an API limit: widen the selection when
ambiguity, an absence claim or the task's information contract requires it. Use
only pagination and projection fields the installed tool supports.

Keep the complete inventory/output recoverable outside the model and preserve
errors and truncation notices. Do not dump every server's schemas, skill bodies
or catalog rows into discovery, startup instructions or each worker. Native
deferred discovery, caching and compaction remain in place; this policy selects
what to return, without replacing those mechanisms or changing tool grants.
Project registration metadata to safe names/status before returning it; client
configuration can contain environment/header credentials. Configuration listings
establish registration, not a connected tool's schema or successful use.

### Shared files and native discovery

For files outside the selected worktree, process the known path inside
`ctx_execute` or `ctx_batch_execute`. Keep `ctx_execute_file` for worktree
paths. context-mode 1.0.169 documents its file boundary at
[mksglu/context-mode@6f0cc684:README.md:1561](https://github.com/mksglu/context-mode/blob/6f0cc6841c687e754059f36714a11233fda1a02b/README.md#L1561)
and execution-tool access at
[README.md:1575](https://github.com/mksglu/context-mode/blob/6f0cc6841c687e754059f36714a11233fda1a02b/README.md#L1575).
For a batch command whose first word is `for`, wrap the loop in
`bash -c '...'`: the installed batch builder prefixes POSIX commands with
an environment assignment
([src/server.ts:1456](https://github.com/mksglu/context-mode/blob/6f0cc6841c687e754059f36714a11233fda1a02b/src/server.ts#L1456)).
Use the execution tool to return the derived answer instead of a whole file.

In Codex code mode, filter `ALL_TOOLS` before returning its metadata and retain
only the selected complete schemas. Deferred nested tools can be omitted from
the exec description
([openai/codex@979011409:codex-rs/code-mode-protocol/src/description.rs:16](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/code-mode-protocol/src/description.rs#L16)).
An inventory count alone does not measure request-schema tokens, and code mode
still renders descriptions for enabled tools. Keep measured input and returned
artifact characters separate. Reuse each selected skill body within a thread.

Select a parent's MCP set through its native launch configuration.
`mcp_servers.<id>.enabled=false` is the documented setting
([OpenAI configuration reference](https://developers.openai.com/codex/config-reference/)).
The selected `<name>.config.toml` layer loads after the user layer
([codex-rs/config/src/loader/mod.rs:130](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/config/src/loader/mod.rs#L130)).
Agent-role files project a narrower set of overrides; the role model fields are
listed at
[codex-rs/core/src/agent/role.rs:36](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/core/src/agent/role.rs#L36).
Measure token effects and server-start resource costs independently.

For a selected skill, finish its first required body read, then reuse that body
within the thread while its source still matches. Count raw read calls, partial
windows and repeated complete bodies separately.

RTK 0.51.0 documents shell `cat`, `head` and `tail` rewrite coverage
([rtk-ai/rtk@e001f773:README.md:153](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/README.md#L153)).
A `sed -n` range can pass through without an RTK equivalent; that is distinct
from a broken hook. Use a supported exact window for a prefix/tail read, or an
execution tool for range analysis. `rtk read` defaults to level `none`; supported
head/tail windows preserve the selected bytes and do not imply additional token
savings. When `rtk rewrite` returns command text with exit 3, that status means
its ask/default permission classification, not missing command coverage
([src/hooks/rewrite_cmd.rs:71](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/hooks/rewrite_cmd.rs#L71)).
This workflow does not modify the hook or its permission policy.

Serena activation requires both `project` and the session identifier returned
by `initial_instructions`
([oraios/serena@c6fbd1c5:src/serena/tools/config_tools.py:44](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/tools/config_tools.py#L44)).
Retain that identifier, and pass `session_id` if activation is required.
If the manual already reports the required project active, reuse that state.
A prior validation failure does not justify omitting a required field again.

### Cache and terminal attribution

Group gateway observations by the returned session and connection fields,
then describe request position only within the available collection page.
A clipped page can begin mid-session. Unknown cache counts remain unknown.
A rate-limit reset identifier is an account-meter observation; it does not
identify the account that served a particular response.

When a spawn call selects no model, `agents.default_subagent_model` can replace
the constructor's parent-derived `model_info.slug`. Leaving the effective key
unset retains that constructor value
([codex-rs/core/src/agent/child_config.rs:109](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/core/src/agent/child_config.rs#L109),
[override at :204](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/core/src/agent/child_config.rs#L204)).
Explicit roles and per-spawn selections retain their native precedence. The key
must be unset across contributing layers; omitting a higher profile entry cannot
mask a lower value. Verify root/child request models before claiming raw alias
parity, then qualify provider routing and cache effects independently.

For direct-provider cache continuity, OmniRoute ships session affinity:
`sessionAffinityTtlMs` selects its lifetime, and the documented default is zero
([diegosouzapw/OmniRoute@c1e30b76:docs/guides/CODEX-CLI-CONFIGURATION.md:470](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/docs/guides/CODEX-CLI-CONFIGURATION.md#L470)).
An available affinity connection is selected before round-robin routing
([src/sse/services/auth.ts:1985](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/src/sse/services/auth.ts#L1985)).
Recorded historical settings do not establish the running settings or a
measured repair. Preserve a bounded before/after native observation before
claiming reduced cache rebuilds.

Treat hcom `pty:approval` as an inferred action-required terminal state.
hcom 0.7.28 detects a title containing `Action Required` or visible prompt
patterns
([aannoo/hcom@b2a7c192:src/pty/screen.rs:309](https://github.com/aannoo/hcom/blob/b2a7c192003e7fd67ed93265289e4ac36276f965/src/pty/screen.rs#L309),
[screen.rs:439](https://github.com/aannoo/hcom/blob/b2a7c192003e7fd67ed93265289e4ac36276f965/src/pty/screen.rs#L439)).
Its emitted event retains prior status-detail text
([src/pty/shared.rs:394](https://github.com/aannoo/hcom/blob/b2a7c192003e7fd67ed93265289e4ac36276f965/src/pty/shared.rs#L394)).
A retained command preview therefore does not identify the detector input.
Native approval, interactive hooks and classifier false positives require
their own evidence.

The [reported Mac rollout](decisions/2026-09-30-bounded-native-decision-routing.md)
retained an oversized initial discovery and a missed current decision. These
rules address those observed failure modes; semantic answer quality and complete
task savings still require their own acceptance and usage evidence.

## Four accepted native coding trials

All four trials passed shared visible tests, hidden acceptance, file-scope and
workflow checks on fixture revision c0bb7561a9c88a98ceaa06d6fcc153f35f55dd69.
Each client ran baseline first, then explicit Context Mode use in a fresh workspace.

| Native client/model | Baseline tokens | Candidate tokens | Observed difference | Wall seconds, baseline → candidate |
| --- | ---: | ---: | ---: | ---: |
| Codex / GPT-6 Astra | 135,217 | 119,998 | 15,219 fewer (11.26%) | 56.129 → 50.207 |
| Claude Code / Claude Opus 5 | 292,561 | 368,121 | 75,560 more (25.83%) | 27.465 → 34.056 |

The candidate made two Context Mode calls in Codex and three in Claude; neither
baseline used it. Native caches were retained and their warmth was uncontrolled.
Plugin tool availability was not fully controlled. One fixed-order pair per
client does not isolate a causal Context Mode effect, establish a repeatable
saving rate, compare model quality generally, or measure the entire stack.

Codex total is input plus output; cached input and reasoning are subsets.
Claude total is ordinary input plus cache creation plus cache reads plus output;
thinking is included in output. Final cumulative task counters exclude the
coordinator, reviewers, audit tooling and report. Billed cost is unknown.
See the [native-pair receipt](../evidence/receipts/token-practice-native-pairs-20260920.json).

## Ten exact retained-artifact comparisons

Counts use gpt-tokenizer 3.4.0 with o200k_base. They describe complete retained
UTF-8 artifacts at the stated boundary, not whole-task or billed usage.

| Native operation | Before | After | Tokens removed | Information boundary |
| --- | ---: | ---: | ---: | --- |
| RTK Git log | 537 | 178 | 359 | Formatting at a fixed six-commit input |
| TOON components | 1,664 | 1,307 | 357 | Structured serialization with native strict decode |
| ast-grep selection | 1,818 | 674 | 1,144 | Selected expression versus complete source |
| QMD source window | 2,672 | 815 | 1,857 | Selected lines versus complete indexed document |
| SocratiCode retrieval | 2,731 | 491 | 2,240 | Selected result versus complete source |
| Repomix outline | 3,697 | 663 | 3,034 | Lossy outline versus complete pack |
| EdgarTools HTML | 10,322 | 1,249 | 9,073 | Offline upstream HTML fixture to Markdown |
| agent-browser snapshot | 67 | 38 | 29 | Interactive controls versus full accessibility view |
| MarkItDown HTML | 10,322 | 1,360 | 8,962 | Exact stored HTML input to Markdown |
| Syft inventory table | 471,760 | 465 | 471,295 | Package columns; other SBOM metadata omitted |

Do not sum the rows. Several share a source or supporting services. Crediting
the SocratiCode difference again to Qdrant, vLLM or MCPorter would count the same
effect repeatedly. Syft package name/version/type columns were checked for equality,
but its table does not retain the complete SBOM. The corrected MarkItDown baseline
uses the exact stored input; the earlier one-byte mismatch is not the accepted pair.

The [artifact receipt](../evidence/receipts/token-practice-artifacts-20260920.json)
publishes counts, byte sizes and hashes. Original host artifacts remain private;
CI does not independently recount those private pairs. Existing public fixture
recounts in [the evidence guide](evidence.md) retain their separate counts.

## A separate full-catalog TOON counterexample

A later conversion used all 502 repository identities. Native TOON 4.1.1
reported approximately 84,907 JSON tokens → 71,770 TOON tokens: 13,137 fewer
(15.5%) under its tokenx 1.3.0 heuristic. Its strict decode round trip passed.
The exact o200k_base comparison instead counted **59,792 compact-JSON tokens →
66,815 TOON tokens: 7,023 more**. The source representations and estimators
are different, so the native estimate is not an exact saving result.

The guard selected the original compact JSON. Keep JSON when conversion
increases the relevant measured input. This is one additional comparison,
separate from the ten retained-artifact pairs above. The [full-catalog receipt](../evidence/receipts/token-practice-catalog-toon-20260920.json)
retains sanitized upstream output, methods and artifact identities; it does not
establish provider savings.

## Native counters and their limits

The [dated native-counter receipt](../evidence/receipts/token-practice-native-counters-20260920.json)
retains returned RTK and Headroom fields, TOON comparison methods and separate
Desktop WSL, native Claude and native Codex Context Mode runtime scopes.

| Upstream command/tool | Native scope | Interpretation |
| --- | --- | --- |
| rtk gain --format json | Retained command-history estimates | Installed 0.50.0, like 0.49.0, defaults history_days to 90; this is not a forever ledger or provider accounting. |
| rtk gain --project --format json | Same history, selected project | A subset of the all-history view, not another total to add. |
| toon input.json --stats -o output.toon | One conversion | TOON 4.1.1 uses tokenx 1.3.0 estimates here; no native cross-run savings ledger. Exact o200k_base recount is separate. |
| Context Mode ctx_stats | Connection/session and reported lifetime estimates | Session estimates differ from lifetime event-count × 256-token heuristics; neither is exact provider usage. A new Inspector connection has its own session. The persisted counters and the rendered bars measure different things; see below. |
| headroom savings --json | Native usage ledger report | In 0.37.0, the field named lifetime is capped by a 30-day report lookback. Offline guard results do not populate it automatically. |
| Claude Code `/usage` "Prompt cache (main)" line; status-line `prompt_cache` object | Main conversation of one session | Native prompt-cache hit-ratio counters for the main conversation only, not subagents; Claude Code 2.1.251 or later, and the likely-miss cause 2.1.260 or later ([costs](https://code.claude.com/docs/en/costs), [status line](https://code.claude.com/docs/en/statusline), read 2026-09-28). The reset on `/clear` applies only to the `/usage` Session line. For children, read the cache counters of `examples/claude-native/workflows/child-usage.mjs` or OTel `claude_code.token.usage`, and prefer `query_source` to `agent.name` ([monitoring](https://code.claude.com/docs/en/monitoring-usage)). |

The reviewed RTK retained-history snapshot reported 46 commands, 11,509 input,
9,852 output and 1,657 estimated saved tokens (14.3974%). Its project view
reported 11 commands, 3,949 input, 3,749 output and 200 estimated saved.
These are dated upstream estimates, not maintained live counters.

RTK 0.50.0 can store negative per-command savings and clamps them to 0 when
reading. If a host rolls back to 0.49.0 while such rows exist, 0.49.0 shows
them as values near 1.8e19 in `rtk gain --history` and `--all` (including
`--all --format json|csv`); in the qualification test, plain
`rtk gain --format json` showed none
([receipt](../evidence/receipts/rtk-050-qualification-20260925.json)).

The reviewed Headroom ledger returned zero calls and zero tokens in its capped
reporting window. Its separate local guard passed seven fixtures. A zero ledger
does not establish zero guard activity, zero provider usage or zero possible
benefit. Heuristic counters and illustrative API prices are not subscription bills.

### Why the Context Mode lifetime dollar line can be small

Installed Context Mode 1.0.169 reports two different "saved" quantities. The
server's persisted status JSON holds `tokens_saved = round((bytes_indexed + bytes_sandboxed + cache_bytes_saved) / 4)`
from its own counters and `tokens_saved_lifetime = retained events × 256`
(`src/server.ts:1032-1052` at the reviewed revision `6f0cc684`); the
[token report](../tools/token-report/README.md) reads these two fields. The
rendered `ctx_stats` text computes the same session sum for its footer, and its
lifetime dollar line prices `retained events × 256 + current session estimated tokens`.
Its Without/kept-out bars and its "real" lifetime tokens instead add the session
database's `bytes_avoided` (`src/session/analytics.ts:1025-1034, 2173-2180`),
which upstream defines as measured diverted output. On Claude Code that column
also holds `read-redirected` rows booked at full file size for Reads that
context-mode only advised against and did not block (`hooks/core/routing.mjs:848-862`;
upstream #950, comment 5412624311), so quote a rendered figure only as an
upstream-rendered figure, never as verified avoidance or provider usage, and
derive no ratios from it. The renderer's fallback is $5 per million input
tokens, with an environment override; this is an illustrative value, not
avoided provider billing or subscription cost.

The native database keeps at most 1,000 events per Claude Code session, and the
session's Agent and Workflow children write into the same session. At the cap,
1.0.169 deletes the lowest `priority` value first, while its capture hooks write
1 for their most critical rows (upstream #1156). Each fresh startup removes the
project's sessions whose start time is more than seven days old, even while they
are still active (upstream #1140). Neither limit has a setting; see the
[executor and session-store notes](token-session-handbook.md#context-mode-executor-and-session-store).
Consequently, "lifetime" means retained runtime history and can
decrease. Native Codex, native Claude and Desktop data stores have separate scope.
A small dollar quote without its runtime and capture date cannot establish whole-PC
or per-repository savings. Inspect the installed `src/session/analytics.ts`
(`renderBottomLine`, session token estimate and price fallback), `src/server.ts`
(persisted status), `src/session/db.ts` and both SessionStart hooks when upgrading.

The local report preserves metadata-only event identities, timestamps and project
attribution, plus immutable upstream reports. It excludes prompts and event
content, deduplicates observed events, and never adds these archived event
estimates to overlapping native counters. Missing historical events cannot be
reconstructed. A command output comparison is not an actual-use lifetime total.

Adoption must distinguish enabled hook configuration, observed retained source
labels and completed task acceptance. Native Claude's RTK Bash rewrite is
configured; current Codex practice uses explicit RTK commands. A stale trust entry
for an absent hook file does not activate it. Per-client hook inventories should
respect disabled-hook flags and retain unobserved lifecycle paths.

RTK, Context Mode, Headroom and the newly adopted jCodeMunch expose native savings-history
estimates with different retention and counting rules. jCodeMunch includes repeated
reads and uses bytes/4; its schema estimate is payload size, not per-request savings.
TOON has per-conversion statistics; usage and
telemetry tools report consumption or state. Keep every catalog repository's
adoption and baseline availability explicit, with unknown values left null.
Run role-specific acceptance where applicable; guidance and research catalog
entries are not implied executable deployments. Preserve failed quality gates
when importing new matched-task or retrieval evaluations.

## Counts, comparisons and acceptance (2026-09-27)

These rules follow from the 2026-09-27 per-tool verdict wave and the review of the
E1 and E2 subagent receipts.

- **An invocation count is not a success rate.** A scan of native histories that
  matches command text or MCP server names counts attempts. Report each population
  with its own denominator. A subgroup, such as the children that received the
  token-lanes block, is part of its population, not another one, and its rate is
  neither general coverage nor a causal effect. Successful use on eligible tasks is
  what the [preregistered E2E](../evidence/artifacts/token-adoption-e2e-20260926/README.md)
  measures (M1, M6c, M7 and M8). It has not run, so no tool has an eligible-task
  success rate yet.
- **A comparison needs its task's acceptance.** A token difference counts only with
  the check that the smaller output still answers its task. One Context Hub fact
  does not make its document current; an ast-grep call match does not establish
  outline or rule-configuration fidelity; one MarkItDown HTML conversion says nothing
  about other formats or extensions; a Serena Python fixture does not establish
  complete references in another language. The
  [handbook's upstream limits](token-session-handbook.md#known-upstream-limits-behind-the-lanes)
  give the routing.
- **Count the recovery read.** Filtered or compressed output is not raw output. In
  the [laptop run](../evidence/artifacts/token-e2e-ultracode-laptop-20260926/README.md),
  the verifier refuted RTK's "no fact lost" claim (a misreported branch list and
  shortened recall pointers), and Headroom's compression plus its full retrieval came
  to more tokens than the original. Include recall or original reads and the response
  envelope when comparing workflow cost; the clean-prefix Headroom figures below show
  the same growth.
- **Measurement infrastructure saves nothing itself.** gpt-tokenizer 4.0.0
  (`o200k_base`) is the pinned counter behind the exact comparisons, not a reducer;
  the [ten dated comparisons](#ten-exact-retained-artifact-comparisons) were counted
  with 3.4.0. Its counting contract covers ordinary UTF-8 text under the default
  special-token policy, which disallows every special token and throws on an input
  that contains one ([4.0.0 README](https://github.com/niieani/gpt-tokenizer/blob/4.0.0/README.md#special-tokens)).
  The [4.0.0 qualification](../evidence/receipts/gpt-tokenizer-400-qualification-20260929.json)
  covers only default `encode` of `encoding/o200k_base` on UTF-8 text under Node
  v24.21.0, where 3.4.0 and 4.0.0 counted all 47 artifacts retained in the host's
  token-report ledger identically; allowed-special modes and other entry points are
  not qualified. ccusage totals
  are consumption, reported token-only while any model is unpriced
  ([recipe row](../recipes/README.md#component-catalog-install-and-check)). An
  agentsview answer observes retained history, and MCPorter is transport.
- **Receipts carry their current acceptance.** The E1 (#296) and E2 (#316) receipts
  now hold dated adjudications. Of E1's sixteen exercised tools, QMD and Repomix
  were retracted, ai-memory's check was vacuous, and the rest are partial because
  no E1 check recorded a failing run. E2 keeps Context Mode, jCodeMunch, QMD and
  ast-grep partial for the same reason
  ([E1 correction](../evidence/artifacts/token-e2e-ultracode-20260925/README.md#results),
  [E2 erratum](../evidence/artifacts/token-e2e-ultracode-laptop-20260926/README.md#erratum-2026-09-27)).
  Read `tools[].adjudication`, not `quality_check.passed`.
- **A proxy arm changes the harness too (2026-09-28).** Behind a non-first-party
  `ANTHROPIC_BASE_URL`, Claude Code turns MCP tool search off and loads every MCP
  tool into the cached prefix, so connecting a server, or deliberately disabling
  it or denying its tools, invalidates the cache, while an unexpected disconnect
  keeps it ([gateway caveat](foundation-stack.md),
  [MCP tool search](https://code.claude.com/docs/en/mcp#configure-tool-search),
  [prompt caching](https://code.claude.com/docs/en/prompt-caching)). The only
  independent billed-cost study the 2026-09-26 landscape sweep found (arXiv
  2607.12161) measured the Headroom v0.27.0 API-boundary proxy at +48.4% billed
  cost, not 0.37 or 0.39.
  An arm routed through `ANTHROPIC_BASE_URL` holds `ENABLE_TOOL_SEARCH` and the
  cache-TTL variables fixed across arms, confirms that the proxy forwards
  `tool_reference` blocks and keeps the 1M window, and reports cache creation and
  reads per arm; otherwise compression is confounded with lost tool search and a
  changed cache lifetime.

## Run shape and accounting (2026-09-29)

The [spend attribution receipt](../evidence/receipts/claude-spend-attribution-20260929.json)
counts this host's Claude Code transcripts for 2026-09-24 to 2026-09-29 (UTC dates; the files that record a version
were written by Claude Code 2.1.280 to 2.1.284) and matches ccusage 20.0.26 on input, output, cache-read and cache-creation
(5m plus 1h split) totals within 0.001%. At API list prices (a proxy for the plan meter,
which weights tokens differently), spend concentrates in how runs are shaped:

- **Children.** Agent-tool and workflow children are 81.3% of dollars, workflow
  stages alone 66.1%, and 4 of 710 session trees cover half. A child of more than
  60 calls is 23.8% of children and 53.2% of dollars (median 25 calls,
  p90 100, maximum 1,489). ccusage lists each workflow run as a session: the 303 runs
  are 68.1% of its dollars, the median run $22 and the largest $448.
- **Default-typed children.** A child with no role definition (`workflow-subagent`,
  `general-purpose`, `claude`, `Explore`) is 63.4% of children and 41.1% of dollars,
  with a median first call of 39.5K tokens; among the named role types in the receipt the
  median first call runs from 8.2K (`source-scout`) to 47.9K (`landscape-sweep-worker`).
- **Effort and thinking.** Effort `max` covers 82.2% of calls, and thinking is 61.0%
  of output tokens. Earlier thinking blocks stay in context by default on Opus 4.5+
  and Sonnet 4.6+ (the `keep` default of `clear_thinking_20251015` in
  [context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing)),
  so output is paid twice, once as output and again as carried context; no Claude
  Code setting that clears them was found in the settings reference or changelog
  on 2026-09-29. The docs say `max` "may show diminishing returns and is prone to
  overthinking, so test before adopting it broadly"
  ([model configuration](https://code.claude.com/docs/en/model-config)); the M7 arms
  in the [max-default decision](decisions/2026-09-29-max-default-effort.md) are that
  test and have no result yet.
- **Advisor.** 1,872 iterations are 14.0% of dollars (750 on `claude-fable-5-1`,
  all but 17 before 2026-09-28; 1,122 on `claude-opus-5-5`). Each call reads the
  transcript uncached, and top-level `usage` leaves it out
  ([advisor tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool#usage-and-billing)).
  ccusage counts it since v20.0.17; `child-usage.mjs` does not (see
  [claude-advisor-usage-scan-20260928](../evidence/receipts/claude-advisor-usage-scan-20260928.json)).
- **Long contexts.** Calls above 400K tokens of context are 13.4% of calls, 23.3% of
  dollars and 35.5% of cache-read tokens; above 200K they are 42.8% of calls and
  59.9% of dollars. Claude Code's guidance is to `/clear` when switching to
  unrelated work, since stale context "wastes tokens on every subsequent message"
  ([costs](https://code.claude.com/docs/en/costs)). At a task boundary, record the
  progress and git state in a file or commit, then start a fresh context; an
  incomplete handoff costs re-reads, so compare session spans and peak context
  before and after.
- **Cache.** Children wrote 844.6M tokens to the 5-minute class (their unsplit remainder priced
  as 5-minute) and show none in the 1-hour split field; main sessions show 142.7M there. Misses after
  5-minute to 1-hour gaps rewrote 168.2M of the children's tokens in 789 events, 19.9% of
  their writes (the gap includes the next call's response time, so the bin is approximate). At the
  generic price ratios (write 1.25x, 1-hour write 2x, read 0.1x the input price), a 1-hour class
  would price every remaining write at 2x (+507.3M input-equivalents) and turn the rewrites into
  reads (-193.4M), a net +313.9M; it pays only when rewrites exceed 0.39 of the 5-minute writes
  (`data.derived` in the receipt). The 5-minute default stays
  ([prompt caching](https://code.claude.com/docs/en/prompt-caching)).
- **Tools.** MCP calls are 15.1% of 210,900 tool calls and 98.6% of them are Context
  Mode. ToolSearch loads exceed later calls for serena (694 loads, 28 calls), QMD
  (519, 58), ai-memory (238, 137), SocratiCode (132, 68), Headroom (119, 26) and
  jCodeMunch (102, 81). These are attempt counts with separate denominators, not
  success rates.

The receipt does not size the always-loaded files, and it carries no quality
comparison: a saving from fewer or shorter children, a lower effort or a
different advisor policy needs its own paired result. To repeat the measurement, copy the
transcript tree (`cp -a ~/.claude/projects <copy>/projects`) so both tools read the same bytes, run
`CLAUDE_CONFIG_DIR=<copy> ccusage claude daily --json --offline` and the scan
(`cp evidence/artifacts/claude-spend-scan.py.txt claude_spend_scan.py`,
`python3 claude_spend_scan.py --root <copy>/projects`, then `--control`) without a date filter, and compare
`totals_comparable_to_ccusage` in the scan's output with ccusage's totals (the scan adds
the advisor's tokens to the executor's). For a window, pass `--since YYYY-MM-DD` to the scan
and `--since YYYYMMDD --timezone UTC` to ccusage. The
[decision record](decisions/2026-09-29-token-spend-attribution.md) gives each lever its
owner and overturn condition.

The model and effort of each task class, and the file or instruction that enforces each today, are one table in the [task-to-model routing record](decisions/2026-09-30-task-model-routing.md).

## Shared Codex quota (2026-09-26)

`scripts/codex_quota.py` reads the Codex account's usage snapshot through the
native app-server method `account/rateLimits/read` (the openai/codex app-server
protocol, the same at rust-v0.155.1 and rust-v0.157.1): one short `codex app-server`
over stdio in an empty directory, with no model turn, session transcript or
credential file. `--json` prints one object; `--gate PERCENT` exits 3 when a
window's `used_percent` reaches PERCENT, `rateLimitReachedType` is set or
`ordinaryUsageAllowed` is false, and 2 when no snapshot arrives. It prints no
server error text, since backend errors can carry account identifiers. This page
quotes no quota figure: read the current one with the probe, and cite a figure only
from a retained, sanitized `--json` read. The [host receipt](../evidence/hosts/nativestack-5975wx-20260925/nativestack-5975wx-20260925--codex--install--20260926.json)
records 0.157.1 on PATH, `daemon_auto_start` false and no daemon process or package
at 14:34Z, but not the quota read. The percentage is the backend's whole-account
figure, not a token count: every session and host signed in to the account draws
on it, so the difference between two reads does not price one task, and it is
never added to a token counter.

The user decided on 2026-09-26 to spend the GPT-6 weekly quota now, in priority
order, and to be told when the limit is hit so they can reset it. While it lasts:

- Treat the host's Codex capacity as one slot pool. Concurrent sweeps share one
  `--lock-dir`; interactive Codex, reviews and other lanes use the same budget
  without holding a slot, so lower `--slots` while they run.
- The verdict wave gets the budget first; other GPT-6 lanes take what it leaves.
- Read the probe before a large dispatch. Stage sweeps with
  `build_args.py --quota-stop-percent` when a reserve should stop jobs early (the
  [harness README](../tools/sota-convergence/landscape-sweep/README.md#coordination)).
- When the gate or a real usage-limit error writes `LIMIT`, stop dispatching and
  tell the user the reason and the reset time. Do not sign in again from a
  workflow; remove `LIMIT` only after the user's reset.

## Coverage and future acceptance

The [current component lifecycle matrix](token-native-saturation.md) links each
selected role to installation, integration, functional and lifecycle evidence.

The later [clean-prefix acceptance](../evidence/receipts/native-token-clean-prefix-20260920.json)
also proves fresh isolated upstream Headroom/jCodeMunch installation, exact use
before and after server restart, and native removal with retained evidence.
Complete Headroom compression responses used 2,732 tokens versus a 5,105-token
compact original; fetching the full original as well raised the responses to
18,777. jCodeMunch search/source responses used 324 versus a 2,484-token whole
file, while the already-known function required only 40. Indexing plus retrieval
was 593; setup/statistics outputs remain outside those retrieval-only figures.
The isolated native meters returned Headroom 7,488 and jCodeMunch 5,562 estimated
tokens for their verification calls. These are separate test ledgers; the
existing jCodeMunch ledger remained unchanged at 29,820. Keep the cheaper adequate
path and retain these growth cases alongside the reductions.

The focus wave added exact jCodeMunch retrieval, direct upstream Headroom MCP,
both-native-client project-file/symbol acceptance and explicit sandbox network
allow/deny fixtures. The [native client receipt](../evidence/receipts/native-token-focus-clients-20260920.json)
records 101,605 consumed Codex tokens and 151,528 consumed Claude tokens, with
cache/reasoning subset rules retained. They are acceptance costs, not savings.

jCodeMunch's complete search/source sequence used 861 tokens versus a 5,476-token
whole file, but exceeded an existing 601-token focused extraction. Headroom's
direct summary used 19,714 versus 36,625 tokens with exact original recovery
available; its separate guarded log fixture used 191 versus 26,529 tokens.
Keep these accepted artifact comparisons and native repeated-use estimates
separate from all lifetime provider claims. The [upstream recipes](../recipes/README.md)
show actual install, registration, retrieval and stats commands for future PCs.

### Supplemental native adoption on September 20

The [supplemental receipt](../evidence/receipts/upstream-native-tools-20260920.json)
adds three installed upstream tools to the current catalog. Beads 1.3.0 completed
23 native operations and ten checks, including persistent claims, dependency
blocking/unblocking and closing all three fixture issues. skills-ref 0.1.0 at
commit `69ef37e9424c0a7ea9dd2293b559e43ec8176379` validated a selected skill,
returned its expected properties and rendered its complete prompt metadata.
otel-tui 0.7.5 accepted one OTLP trace over loopback HTTP and displayed its service,
single span and 10 ms latency; its owned process then closed successfully.

Use the [upstream native recipes](../recipes/README.md#supplemental-native-task-and-inspection-tools)
from either client's ordinary native shell. Beads is available for tasks that
need a persistent dependency queue; initialize only the selected project with
agent-instruction and hook generation skipped. skills-ref is explicitly a
reference/demo validator and does not certify native client extensions. otel-tui
is an on-demand local viewer with no persistent producer configuration implied.
The three tools do not expose verified lifetime token-savings counters; their
installation and functional results are not evidence of provider savings.

The separate [ai-memory 2.3.2 maintenance receipt](../evidence/receipts/native-ai-memory-maintenance-20260920.json)
records an official checksum-verified update after a private upstream backup.
The running service executable, supported native status, scoped search and direct
MCP status passed. Existing hooks, client configuration and project scope were
preserved. Earlier model-task and 52-component study receipts remain unchanged;
these additions did not repeat provider trials or rewrite historical baselines.

The selected zizmor 1.30.1 analyzer also gained a [native Linux follow-up](../evidence/receipts/native-linux-zizmor-20260920.json):
official isolated `uv tool install`, zero findings on the current workflows,
expected exit 14 and three findings on an inert unsafe fixture, and two native
acceptance tests with no skips. Its earlier Mac/CI receipts remain dated. This
closes local command availability without adding a component or savings claim.

The [coverage receipt](../evidence/receipts/token-practice-coverage-20260920.json)
preserves all 52 classifications and 70 captured operations: 66 expected process
checks passed and four failed attempts remain. This is not 52 full-stack passes.

Coverage comprises ten artifact-pair entries, three native-task-pair entries,
19 bounded functional entries, ten current queries, one configuration check,
five historical-only entries, one host-blocked component and three guidance
repositories. Dependency effects overlap even where component classifications differ.

The original audit recorded Linux Playwright ENOENT failures; the then-available
Windows installation was a different host scope. A later separately scoped Linux
acceptance used @playwright/cli 0.1.21, existing Chrome 153 and a loopback HTTP
fixture: seven native commands passed and returned Hello, Playwright!. The earlier
file-URL attempt was blocked. This does not establish default-browser download
or arbitrary-site acceptance. OTel environment and Dagu environment-filter failures have
separately recorded successful corrections. Configuration checks, current alert,
backup and cache queries, renderer fixtures and native model workflows close
different gates. Guidance repositories are not executable tools.

The [later six-component follow-up](../evidence/receipts/token-practice-gap-followup-20260920.json)
retains 31 operations: 28 accepted checks and three failed attempts. In addition
to Playwright, it confirms a one-session AgentsView retrieval, offline ccusage
parsing, a synthetic HUD renderer and full public-paper retrieval with OpenResearch.
These close only their stated gates; live HUD interaction and archive auto-discovery
remain unestablished. The original 70-operation coverage receipt remains unchanged.

Its read-only bridge backend task used 44,908 input + 124 output = 45,032 native
tokens in 11.225 seconds. Cached input of 22,016 is already inside input. This is
additional usage, with no matched saving baseline or outer Claude interaction.
The separate UTC usage parser returned 2,573,385 combined tokens, including its
819,530 Codex subset. Do not add the subset, this trial or earlier task totals to
that overlapping report. Tracked source remained unchanged; native MCP startup
created untracked metadata, and owned temporary services were stopped.

For another experiment, freeze a useful task and acceptance rubric, retain exact
inputs and outputs, record native versions, commands, failures and cache conditions,
and compare final task usage including retries. Repeat or balance run order
before treating a difference as reliable. Keep model trials explicitly scoped;
normal future-session work uses selected retrieval rather than a full audit.

Use the existing [update protocol](../adoption/update.md) and native
[recipes](../recipes/README.md). Append dated sanitized receipts with reciprocal
component links, then refresh the existing catalog generator and integrity map.
Do not publish private transcripts, credentials, environment values or host paths.

The [September 21 selective-retrieval pilot](claude-selective-context-pilot-20260921.md)
adds three counterbalanced native Claude pairs with independently checked code
acceptance and native usage reconciliation. All selective runs chose native
computation and made no Context Mode calls. Their aggregate reported tokens were
2.42% higher; this is not a Context Mode treatment or a causal savings result.
The rejected setup attempt remains separate and included in campaign totals.
Keep the existing smallest-sufficient-context policy rather than forcing a tool
call or promoting this single-fixture observation into a universal default.

## Generic child model default omission

The October 9, 2026 template change removes
`agents.default_subagent_model = "${CODEX_MODEL}"` and keeps
`agents.default_subagent_reasoning_effort = "max"`. A generic child whose
spawn supplies no model now retains its parent step's `model_info.slug`.
Previously the template's model default could replace that value with the
rendered `CODEX_MODEL`. On the qualified 0.161.0/0.162.0 Codex host, a parent
on another model therefore stops receiving a forced Sol child default. This
changes model selection; no token or cache savings were measured. The older
0.155.1 macOS pin has only rendering coverage here, not a native inheritance
qualification. No claim that its forced model default ends is made.

The launcher's default client is 0.162.0
(`coordination/command-center/lane-tiers.json:39`; its two held lanes are
listed at lines 41–42). The source is
[openai/codex rust-v0.162.0, child_config.rs](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/core/src/agent/child_config.rs#L109):
the spawn constructor copies the parent step's slug at line 115, and the
full-history constructor copies the parent turn's slug at line 137. The
generic model override is selected at line 204 and applied at lines 211–240;
the effort-only path at lines 243–249 leaves the inherited model in place.
The same file at
[rust-v0.161.0](https://github.com/openai/codex/blob/rust-v0.161.0/codex-rs/core/src/agent/child_config.rs)
is byte-identical: both are 13,496 bytes with SHA-256
`33d4dd6f70e6640af1059398272c48b88e16e0005105fbd1ef13e30456d39a39`.
Explicit spawn selections and role configuration retain their native
precedence. The effective key must be absent across contributing layers;
removing this template entry does not mask an existing lower-layer value.

The effort-only path also validates Max against the parent's supported
reasoning levels at child_config.rs:243–248. A parent model whose metadata
does not support `max` can reject the spawn instead of receiving a forced
Sol/Max child. All registered Codex lanes in the cited launch inventory use
the qualified Sol parent setting, so none is identified with this unsupported
effort case. An explicit spawn effort can select a supported level; this record
does not qualify other parent models by analogy.

### Existing host application requires deletion

F9's reviewed live-apply diff must delete `agents.default_subagent_model` from
the existing host's `~/.codex/config.toml` after landing. The CC's October 9
Claude read verified that file's line 45 still sets
`default_subagent_model = "gpt-6.1-sol"`; this lane did not read the live file.
Omitting the template entry in a merge-style apply cannot remove that existing
key. The reviewed apply therefore includes its explicit deletion, with the
effective key absent across all contributing layers and the root model, Max
effort and explicit role choices preserved. The CC performs F9 from that
reviewed diff after landing; this PR neither edits the live file nor claims
the deletion has occurred.

The corresponding surface-catalog decision is `declined`: it rejects a forced
generic model default and records the pending F9 deletion. The earlier
`enabled` host observation remains dated evidence, not the selected practice.

The lane inventory below is a source review of the co-op registries at
2026-10-09 00:20 UTC. `H` means a source line in
`coordination/ns2604-coop/lanes/hcom-lanes.json`; `T` means a source line in
`coordination/ns2604-coop/lanes/threads.json`. Those snapshots have SHA-256
`fe550f1eec77ace1537e3a9546b703118cd4aafba4cbdf0d55345d78d133a830`
and `965d884240b0d6e8bceddcd4517ca16c6940bf3e488edf1f4254947b99814d63`,
respectively. They identify lanes, rather than recording each request's model.
State locators in this section are relative to the native-agent-stack state
root, normally `~/.local/state/native-agent-stack/`. The H snapshot locator is
`coordination/ns2604-coop/lanes/hcom-lanes.json`, read at the stated time with
the digest above; this registry is mutable, so its current bytes need not match
that historical read. The T locator has the same historical-read boundary.
The shared launch command supplies `-m cx/gpt-6.1-sol` at
`coordination/ns2604-coop/omniroute-canary-20261008/launch_lane_omni.sh:80`
(SHA-256 `5100497bdd1235ea9d5cc7e69e075b8f59269430b459301281695b96bc45d7bc`).
Under that launch setting, none of the 28 non-closed registered Codex root lanes changes
model family when it spawns a generic child. Inheriting the routed slug can
still differ from forcing the plain rendered model ID; this inventory does
not claim byte-identical requests or a measured routing or cache improvement.

| Codex lane on the shared Sol launch setting | Registry source lines |
| --- | --- |
| orch-records | H:2 |
| rnd-r1 | H:36 |
| layer15-build | H:65 |
| paper-open-e2e | H:89 |
| api-credit-sota | H:104 |
| github-consolidation | H:123 |
| landscape-gap | H:176 |
| landscape-mcp | H:195 |
| landscape-stars | H:212 |
| runtime-workers | H:232 |
| landscape-live-foundation | H:251 |
| landscape-live-trading | H:268 |
| harness-rules | H:293 |
| g5-fields-a | H:317 |
| g5-fields-b | H:337 |
| g5-stars-gap | H:358 |
| sdk-harness-ready | H:374 |
| ns-readiness-manifest | H:395 |
| currency | H:415, T:3 |
| codex-token-parity | H:426, T:7 |
| convergence-practice | H:441, T:8 |
| fixwave-defects | H:454, T:2 |
| github-ci-finalize | H:467, T:4 |
| grand-catalog | H:480, T:5 |
| readiness-runner | H:491, T:30 |
| skills-lifecycle | H:504, T:23 |
| memory-h2h | H:523, T:6 |
| overlap-token | H:541, T:38 |

`fixwave-mcp` (H:149) and `github-ci-finalize-read` (H:161) are registered
Claude sessions, so this Codex template does not select their child models;
the latter is marked closed. `rnd-r3` (H:22), `lm-qmd` (H:52, T:39),
`supersession-ledger` (T:24) and `overlap-codenav` (T:31) are also marked
closed; `overlap-codenav` was absorbed by `readiness-runner`.

The repository's builtin role names are `default`, `explorer` and `worker`
([codex_roles.py:67](../tools/adoption/codex_roles.py#L67)); each generic spawn
without a role model override follows the behavior above. The configured
roles have these effects:

| Role | Source | Effect of omitting the generic model default |
| --- | --- | --- |
| isolated-builder | [workers/isolated-builder.toml:18](../adoption/agents/codex/workers/isolated-builder.toml#L18), [inherited model role at codex_roles.py:74](../tools/adoption/codex_roles.py#L74) | Names no model and keeps Max. With no explicit spawn model, it now inherits its parent; a non-Sol parent can therefore change this child's model family. |
| stack-researcher | [stack-researcher.toml:12](../adoption/agents/codex/stack-researcher.toml#L12) | Its explicit Astra/Max selection remains. A generic child spawned from this Astra parent now inherits Astra rather than the template's Sol default. |
| stack-verifier | [stack-verifier.toml:12](../adoption/agents/codex/stack-verifier.toml#L12) | Its explicit Astra/Max selection remains; generic children of this Astra parent can change from forced Sol to inherited Astra. |
| evidence-reviewer | [workers/evidence-reviewer.toml:15](../adoption/agents/codex/workers/evidence-reviewer.toml#L15) | Its explicit Astra/Max selection remains; generic children of this Astra parent can change from forced Sol to inherited Astra. |
| semantic-evidence-reviewer | [workers/semantic-evidence-reviewer.toml:16](../adoption/agents/codex/workers/semantic-evidence-reviewer.toml#L16) | Its explicit Astra/Max selection remains; generic children of this Astra parent can change from forced Sol to inherited Astra. |

These nested-role effects are source-derived conditions, not observed new
spawns. The retained 0.161.0 synthetic recorder checked an unset-default root
and full-history fork using `cx/gpt-6.1-sol/max`; it did not execute a paired
default-present arm or measure provider usage. Byte-identical 0.162.0 source
does not turn that retained fixture into a new native run.

The retained fixture report is
`research/token-efficiency-20261008/model-recorder/REPORT.md`, SHA-256
`ec82a85ff4c98b5ff161c46235d607caa6a1dbf42cfb727213d94b9b0ff559c1`.
Its root and full-history child request models are both `cx/gpt-6.1-sol`, with
the unchanged 11-entry bundled catalog containing no added `cx/` alias. Native
constructors copy the active parent's `model_info.slug` at lines 115/137;
omitting the generic override leaves that slug rather than selecting a catalog
model at lines 211–240. The fixture demonstrates alias retention for its
recorded root/child path; it does not establish normalization or cache behavior
for other model aliases or providers.

The later co-op pre-cue report is
`coordination/ns2604-coop/gpt-reads/extra-902-8b151f01/BASE-TESTS-AT-HEAD-8b151f01.txt`,
SHA-256 `630c9e3244dbc138f3ceb2b3df9f2113773e37dad11333e431839d308e69d4f9`.
It is distinct from the starting-head report used for the declarations below.

The RTK statements retained at lines 191–195 follow
[rtk-ai/rtk@e001f773](https://github.com/rtk-ai/rtk/tree/e001f773f80b22b7dc4c7a79521b30e35aaef026),
version 0.51.0: native `rtk read --help` documents default level `none` and
byte-exact `--head-lines` at that level with line numbering off, and supplies
the `--tail-lines` window. Native `rtk rewrite --help` describes rewrite
coverage, while [rewrite_cmd.rs:71](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/hooks/rewrite_cmd.rs#L71)
explains exit-3 classification. These provenance pointers are added here so
the earlier 92 reviewed lines stay byte-identical.

The dated explicit `-c 'agents.default_subagent_model="gpt-6.1-sol"'` command in
[the October 2 north-star recipe](decisions/2026-10-02-two-host-north-star-architecture.md)
at line 79 is an explicit-override exception. Running that recipe keeps its
selected generic model and does not exercise the omitted-default path. Its
dated command remains historical; F9's reviewed apply uses the effective-key
absence requirement above.

The existing template-read tests now require the generic model key to be
absent while preserving the root model, Max effort and explicit role checks.
The pre-cue tool ran the base versions of the three changed modules against
head `8e1d60e231e1e290b50ca934efd17a6f0fb6a0cf` and returned rc 1. Its retained
report is
`coordination/ns2604-coop/gpt-reads/extra-902-8e1d60e2/BASE-TESTS-AT-HEAD-8e1d60e2.txt`,
2,914 bytes, SHA-256
`856315647e5f9b6f3344e7c4387efe57acf39196bc011e3af9688579b93a1493`.
It printed nine distinct methods and eleven failing entries: render_config
had five errors and one failure, task_model_routing had two errors and two
failures, and codex_roles had one error. The duplicated errors are the two
platform subcases of each rendering method. Each changed expectation is
declared below by the method name printed in that report.

| Exact unittest method | Pre-cue entry at 8e1d60e2 | Old expectation, new expectation and reason |
| --- | --- | --- |
| tests.test_render_config.RenderConfigTests.test_codex_user_template_sets_the_verified_base_keys | ERROR | Read `agents["default_subagent_model"]` and require the fixture's rendered model. The key is now absent, so the old access raises KeyError; the updated check requires absence while retaining the root fixture model and Max effort. |
| tests.test_render_config.CodexModelTests.test_the_template_names_its_models_only_through_the_placeholder | FAIL | Require both `model` and `default_subagent_model` to bind `${CODEX_MODEL}`. Only root `model` remains; the updated check requires that single placeholder binding so generic children can inherit their active parent. |
| tests.test_render_config.CodexModelTests.test_each_platform_renders_the_model_its_pinned_codex_lists | ERROR twice: `(platform='linux-x86_64')` and `(platform='macos-arm64')` | The old helper reads both rendered root and child keys and raises KeyError in each platform subcase. The updated helper requires child-key absence and still checks each platform's root model against its pin. These two entries count as one method. |
| tests.test_render_config.CodexModelTests.test_a_host_supplied_model_wins_over_the_pin | ERROR | The old helper requires the host-supplied model in both root and generic-child bindings. The updated check keeps the root override (`gpt-6-sol` in the fixture) and requires an absent child key; no template child model is forced. |
| tests.test_render_config.CodexModelTests.test_a_platform_without_a_pins_file_fails_closed_unless_the_model_is_given | ERROR | After the explicit `CODEX_MODEL=gpt-6-astra` override, the old helper reads both root and child keys. The updated check retains the missing-pin refusal and explicit root selection, while requiring an absent child key. |
| tests.test_codex_roles.WorkerRoleSourceTests.test_the_builder_takes_the_lanes_model_at_max | ERROR | Require the template pair `("${CODEX_MODEL}", "max")`. The updated check requires no generic model key and Max effort; isolated-builder still names no model and explicit Astra carriers retain their pins. |
| tests.test_task_model_routing.TaskModelRoutingRecordTests.test_every_quoted_value_is_in_its_cited_file | FAIL | The old record quotes `default_subagent_model = "${CODEX_MODEL}"` at template lines 30–31, so the missing quote fails the required match count. The record now quotes only the live Max-effort key at line 30 and states model inheritance; unconditional quoted-value verification is restored. This old method passes after the stale record is corrected. |
| tests.test_task_model_routing.TaskModelRoutingRecordTests.test_gpt_6_1_sol_is_routed_where_the_sol_primary_record_routes_it_and_nowhere_else | FAIL: `(1, 0)` against `(1, 1)` | Require one root and one generic-child model binding, plus three globally Sol-routed rows. The template now has one root binding and no child binding; the table has two rows with explicit Sol model bindings and one inherited-model child row. The updated check requires those two routes and rejects a generic model binding; the old version now fails earlier on two rows against three. |
| tests.test_task_model_routing.TaskModelRoutingRecordTests.test_the_user_template_renders_on_each_platform_the_model_its_rows_name | ERROR twice; both printed entries have the same method name, with the report clipping the long parenthesized selector | Require the rendered generic-child model to equal the root model on each platform. The updated check keeps the root model/effort check, requires the child model key absent and retains generic-child Max effort. The two entries count as one method. |

For the revised records, eight distinct base-version methods remain intentional
failures: all five render_config methods, the builder method, and the Sol-routing
and per-platform rendering methods. The quoted-value method now passes because
its stale enforcement quote is corrected. This declares the observed nine-method
pre-cue result and the revised eight-method failing set separately. The lander
must run current main's versions on a fresh merge and compare the actual set;
a new method, missing expected method or unrelated failure still requires a hold.

Three decision records are reconciled in the same head. The current generic-child
row in [task-model-routing](decisions/2026-09-30-task-model-routing.md#decision)
now names the parent slug and the remaining Max key, and the
[Sol-primary record](decisions/2026-09-30-sol-primary-quality-defaults.md#addendum-2026-10-09-generic-children-inherit-their-parent-model)
states the omission and preserves explicit worker and role selections. The
[model-currency addendum](decisions/2026-09-27-model-currency.md#addendum-2026-10-09-generic-child-template-quote-is-historical)
explains why its September 30 lines 418–419 and 450 stay: they document that
revision and its historical observations, which were not rerun or reinterpreted.
They no longer claim current generic-child enforcement. This removes the routing
test's historical-quote exception; every live enforcement quote is checked again.

At the first fold head, all 11 test modules mentioning this template ran separately under
`timeout 600`. Ten passed. The unchanged `tests.test_windows_terminal_defaults`
module failed only
`OverlayTests.test_the_installed_client_knows_no_notification_type_without_a_decision`:
the installed Claude Code 2.1.295 binary exposes `plugin_notification`, which
the existing notification decision table does not list. The same assertion
failed when executed from the original draft head's byte-identical source.
That host-dependent policy gap is retained separately from the nine deliberate
Codex checks; this change does not resolve it or claim all 11 modules passed.

This is a proposed template change. Both designated reads, the pre-cue tool,
CI and an explicit command-center cue gate landing. F9 alone applies the
landed template from a reviewed diff; this PR performs no live application.
