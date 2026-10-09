# Decision: carry token lanes through SubagentStart (2026-09-27)

**Decided by:** unit `token-lanes-subagent-start`, branch
`claude/token-lanes-subagent-carrier-20260927`, implementing the owner's
SubagentStart carrier task for Ultracode workflow children.
The UTC date was read with `date -u +%F`.

**Scope:** the portable Claude hook and sibling text, the existing profile
installer's `HOOKS` map, one additional settings-template hook group, the
handbook, bootstrap instructions and local subprocess/integration tests. The
implementation follows the official [SubagentStart JSON contract](https://code.claude.com/docs/en/hooks#subagentstart)
and this repository's [effort guard fail-open/output pattern](../../adoption/hooks/claude/effort-default-guard.py).
No host installation or service change is part of this unit.

## Evidence

**WP1 scope.** The [retained baseline README](../../evidence/artifacts/child-lane-baseline-20260926/README.md)
and [`claude-lanes.json` `groups.by_spawn`](../../evidence/artifacts/child-lane-baseline-20260926/claude-lanes.json)
cover 639 children: 597 through Workflow and 42 through the Agent tool. Workflow
children received the block in 0/597 prompts and 0/597 SubagentStart contexts;
Agent-tool children received it in 42/42 prompts and 0/42 SubagentStart contexts.
All 30 `subagent_start` aggregates in that JSON have `additional_context: 0`.
The brief also reports "only 22 of 1,010 Ultracode workflow children" received
guidance; those totals are not supported by these retained files and are not
treated as the verified WP1 denominator.

**Upstream gap.** Context-mode 1.0.169's [hook manifest at
`589d8214d56740a28b5f7bf63167743d586b0b40`](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/hooks/hooks.json)
registers no SubagentStart hook. Its [child prompt-rewrite route](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/hooks/core/routing.mjs#L892)
uses `PreToolUse:Agent`; [SessionStart also injects routing context](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/hooks/sessionstart.mjs#L166).
Therefore "only via PreToolUse:Agent" would overstate the source. Both cited
issues were independently read: [#64](https://github.com/mksglu/context-mode/issues/64)
concerns obsolete Task matching missing Agent calls, while [#233](https://github.com/mksglu/context-mode/issues/233)
concerns user-facing commands reaching subagents in 1.0.75 and describes
SessionStart injection; it is not evidence that every other injection path is absent.

Read-only inspection of both installed plugin metadata files returned 1.0.169;
the installed Claude `hooks/hooks.json` registered `PreToolUse:Agent` and no
SubagentStart event. Its `hooks/pretooluse.mjs` delegates to
`hooks/core/routing.mjs`, whose Agent branch builds the child block with
`includeCommands: false` and the ToolSearch bootstrap. The
[v1.0.169 release notes](https://github.com/mksglu/context-mode/releases/tag/v1.0.169)
describe accounting changes, not a new child carrier. Installed `claude --version`
returned `2.1.283 (Claude Code)`; the [upstream changelog at `7779afb1`](https://github.com/anthropics/claude-code/blob/7779afb12e3635f46f56ec823979d68350ae000b/CHANGELOG.md)
records SubagentStart's introduction at 2.0.43, command-type-only SubagentStart
hooks at 2.1.142, and at 2.1.265 a fix that keeps SubagentStart context in a
resumed subagent's prompt prefix. These source/version checks are not a native
child execution; the probe under Limitations is.

**Native event contract.** The [official hooks reference](https://code.claude.com/docs/en/hooks#subagentstart)
names `agent_type` in the input and uses the agent name for matching; an omitted
matcher or `"*"` matches every occurrence, and the template's `""` matcher matched
in the native probe under Limitations. `hookSpecificOutput.additionalContext` is
added to the subagent's context before its first prompt. When a later hook run
finds the earlier copy still in context, Claude Code keeps that copy and the prompt
cache; after auto-compaction discards it, the next run's context is injected again.
For a plugin-shipped agent, `agent_type` is the plugin-scoped name, such as
`my-plugin:reviewer`.

The [context-output section](https://code.claude.com/docs/en/hooks#add-context-for-claude)
specifies that values over 10,000 characters go to a session file and Claude Code
"passes Claude the file path with a preview of up to the first 2,000 characters instead."
This is an inline-output threshold, not a hard rejection limit or a guarantee
that the subagent reads the file. The carrier has a stricter local budget of
3,500 bytes, checked by the [text contract test](../../tests/test_token_lanes_subagent_start.py).

**Research and adoption.** The existing upstream plugin and its published hook
manifest were reviewed before selecting this small adapter. The supplied skill
catalog exposes `search-first`, TDD and `verification-before-completion`; no
separate skill-discovery tool was exposed, and no package installation is needed.
Already installed: [`skillOverrides` in `adoption/templates/claude.settings.template.json`](../../adoption/templates/claude.settings.template.json)
sets `verification-before-completion` to `on` and `search-first` to `name-only`,
not both to `on`. The [handbook subsection](../token-session-handbook.md#token-lanes-carried-into-subagents)
cites the RTK 0.50.0 source and rewrite PR, TOON README, jCodeMunch's three-verb front door,
codebase-memory schemas and other selected tool sources for each routing rule.

Jcodemunch and ToolSearch were not exposed in the builder sandbox, so its
`route`/`menu`/`order` descriptions were read in upstream `server.py` at the
pinned v1.108.319 (`8f7b34ab`, lines 341-343). The codebase-memory evidence
parameter was checked against the connected MCP schema and upstream `mcp.c` at
the pinned v0.11.0, where `include_evidence` (L557) sits in the `trace_path`
schema (from L532), not in `search_graph` (L483).
The [adopted skills manifest](../../adoption/skills/manifest.json) and its
[pinned find-skills reference](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/skills/find-skills/SKILL.md)
provided discovery; no registry install was needed.

### Anti-pattern log

| Proven mistake | Correction and source |
| --- | --- |
| Passing `include_evidence` to `search_graph` | The exposed schema puts it on `trace_path`. Discover nodes first, then request path evidence. |
| Attributing a five-record TOON threshold to upstream | Its README describes uniform shared-field records but specifies no five-record minimum. Five is a local eligibility rule, not a measured break-even. |
| Claiming RTK never rewrites multiple lines | RTK 0.50.0 rewrites a multi-line block per line (`rewrite_multiline_block`, rtk-ai/rtk#3319); `rtk hook check` and the `rtk hook claude` hook both returned `rtk git status` and `rtk git diff --stat` for those two lines. The earlier negative came from a block of `echo` lines, which RTK never rewrites. The block states the measured rule. |

## Decision

Ship [`token-lanes-subagent-start.py`](../../adoption/hooks/claude/token-lanes-subagent-start.py)
and its [sibling block](../../adoption/hooks/claude/token-lanes-block.md) as the
default routing carrier for every non-blind subagent, including Workflow and
Agent-tool children. The [settings template](../../adoption/templates/claude.settings.template.json)
adds its own empty-matcher group alongside ai-memory; exclusion belongs inside
the hook. All `blind-*` roles receive zero bytes from this carrier, including
`blind-lane-reviewer`, `blind-judge` and `blind-adjudicator`. The
[blind judge leak rules](../../adoption/agents/claude/blind-judge.md) and
[blind comparison protocol](../../blueprints/blind-catalog-convergence/README.md)
require that boundary: tool identities and routing text would contaminate a
sealed comparison. This gate covers this hook, not unrelated installed hooks.

Keep the [existing installer](../../tools/adoption/install_claude_profile.py)
generic over `HOOKS`; both files are checksum-pinned, installed together and
skipped when byte-identical. The hook resolves the block beside itself, remains
silent for unavailable/empty/unreadable text or malformed input, and exits zero.
Its output contract follows the [official JSON example](https://code.claude.com/docs/en/hooks#subagentstart);
its exception and unbuffered-write handling follow the existing effort guard.

Use the [handbook](../token-session-handbook.md#token-lanes-carried-into-subagents)
as the text's source of truth. The local tests require its sentences and distinctive
key tool phrases to match the block, exercise the script through subprocesses,
and verify installation plus repeated merging against an existing ai-memory
entry. The merge behavior is defined by [`merge_hooks`](../../tools/adoption/apply_claude_settings.py):
commands are deduplicated across each event, and unseen commands join the first
group with the same matcher. This is local integration evidence, not an upstream
test suite or a new native model run.

## Alternatives considered

- **Per-prompt blocks.** WP1 observed 42/42 Agent-tool prompts carrying guidance
  and 0/597 Workflow prompts doing so. They remain possible, but leave delivery
  dependent on each prompt author. Source: the retained WP1 README and JSON above.
- **PR-B role preloads.** The brief's role-specific skill preload proposal is
  complementary: selected named roles can receive their core skills, while the
  carrier addresses a per-child routing instruction across non-blind roles.
  The distinction follows the [native subagent skill-preload contract](https://code.claude.com/docs/en/sub-agents#preload-skills-into-subagents)
  and the SubagentStart event contract, not measured acceptance of PR-B here.
  This in-flight change was not inspected; ad-hoc Workflow stages without an
  agent definition remain outside named-role preload coverage.
- **Context-mode's PreToolUse:Agent route.** Its pinned routing source handles
  Agent prompt input. In this WP1 measurement, that path delivered no block to
  Workflow children. The separate SessionStart path prevents claiming this is
  the plugin's only injection capability. Sources: the pinned routing and
  SessionStart files and WP1 above.
- **PreToolUse on Workflow.** By the [PreToolUse contract](https://code.claude.com/docs/en/hooks#pretooluse),
  that hook runs at a tool invocation. Inference: matching a Workflow launch
  targets the launch request, not each child created inside it; it could inspect
  or modify supported launch input but would need further prompt wiring to
  reach each child. SubagentStart is the documented per-subagent injection point.

## Overturn conditions

- Reassess this adapter when an upstream context-mode release supplies a
  SubagentStart carrier with an equivalent blind-role exclusion and routing
  contract; remove duplicate delivery after qualifying that release. Compare
  against the pinned manifest cited above.
- Repeat WP1's lane-usage sweep after native acceptance, preserving spawn path
  and task mix. Define gain as higher verified context delivery and a higher
  share of eligible children using the task-appropriate lanes, without lower
  output quality. If delivery works but there is no lane shift, reconsider the
  default; count complete provider use separately and make no savings claim
  from presence or tool counts alone. The baseline is the retained WP1 JSON.

## Limitations

- WP1 is a single-host observation, not a controlled comparison across hosts
  or a causal savings experiment; see its retained README's scope.
- This unit's subprocess and temp-HOME checks are local integration checks.
- **Native probe (Claude Code 2.1.283, 2026-09-27 02:37Z to 02:53Z).** Each run was
  one `claude -p` session in this checkout (main model Opus 5.5) that launched one
  Haiku 4.5 subagent through the Agent tool. The positive arm added a settings file
  whose `SubagentStart` group (matcher `""`) ran this branch's hook; the negative
  arm used the host's live settings, which have no such hook. A first question,
  whether a block whose first line starts with `TOKEN LANES` was present, returned
  `NO` in both arms, although the positive subagent's transcript held the block as
  a `SubagentStart` `hook_additional_context` attachment, so that question did not
  discriminate. The likely reason is that Claude Code frames attached context
  (`contextRendering: announced`); the child's reasoning was redacted, so that cause
  is not observed. A
  second question (find text containing the phrase, other than the task, and quote
  the 60 characters that begin with it) returned `NOT FOUND` for the negative
  `general-purpose` child and `FOUND` with the block's exact first 60 characters
  for the positive one, and `NOT FOUND` for a `blind-judge` child with the hook
  enabled. The transcripts agree: one `hook_additional_context` attachment in the
  positive `general-purpose` child, none in the other two. This is one native
  operation per arm on Agent-tool children. It does not cover Workflow children,
  which WP1 shows also reach SubagentStart, nor lane use, compliance or savings.
  The [carrier receipt](../../evidence/artifacts/token-lanes-subagent-start-20260927/README.md)
  retains the prompts, replies, transcript counts, usage and the RTK hook checks.
- The blind gate matches `agent_type` values starting `blind-`, which is how
  [`install_claude_profile.py`](../../tools/adoption/install_claude_profile.py)
  installs the blind agents (user agents). A plugin-shipped blind agent would
  report a plugin-scoped `agent_type` and would receive the block.
- The block is 3,159 bytes and starts literally `TOKEN LANES`, within the 3,500-byte
  budget and below the documented 10,000-character
  inline-output threshold. A size check cannot prove model compliance. Source:
  the official context-output reference and local text test above.
- The new files are absent at the pinned `v2026.09.26.2` release; the
  [bootstrap guard step](../../adoption/bootstrap.md) marks both their addition
  and the changed hook directory. A new release is a separate step.

This record claims no after measurement, token savings or live installation.
A native Workflow-child run remains open; text delivery alone does not prove
tool access, compliance or improved outcomes.

## Addendum 2026-09-27: measured fetch and containment gaps

Repair-round erratum, 2026-09-27: the initial version of this addendum trusted
stale schema text about `cwd`, mislabelled an out-of-population fetch count as
M4, and overstated current source/copy equality. The corrections below cite the
executor, mark the measurement boundaries, and preserve the original count
tables and counter copies. The decision preceding this addendum is unchanged.

The coordinator's later measurement changes what needs to be instructed, not the
carrier's delivery mechanism. The [retained result tables and counter records](../../evidence/artifacts/token-lanes-subagent-start-20260927/measured-gaps.md)
are **local measurement of native transcripts**, copied from the supplied
`scratchpad/units/w3/lanes-facts.md` report. No workflow was rerun for this unit;
no prompts, tool inputs or workflow identifiers are published with these counts.
The original native-probe receipt above remains unchanged.

**M4-style fetch count, outside the preregistered population.** The
[#381 preregistration](../../evidence/artifacts/token-adoption-e2e-20260926/preregistration.json)
defines M4 for stack-researcher and Codex B, including nested and unclassifiable
fetches, with routed rate at least 0.9. Smoke-2 discover/refute-facts are outside
that population; the following is not a #381 evaluation. Landscape-sweep peer smoke 2 had five agents and the
original carrier active (installed 08:26:32Z from `main` at `5f3a7c21`). Its
discover role made five WebFetch calls and refute-facts made ten; all agents
made zero `ctx_fetch_and_index` calls: **0/15 remote fetches routed through
context-mode**. Whether each child had `ctx_fetch_and_index` exposed was not
recorded, so 0/15 is a descriptive tool count, not an access-qualified routing
or compliance score. Four WebSearch calls are excluded from that count.
The original block never specified page fetching. The two
Sonnet wrappers still passed the reported verbatim-return copy check, **2/2**.

**M3/M5, containment.** Each coordinator wave had twelve agents and started before
installation; smoke 2 ran with the original block. The counts are descriptive,
with differing workloads and no controlled causal comparison:

| Run | Results | Results over 5,120 bytes | Share of result bytes from those results | ctx_execute results over 5,120 bytes |
| --- | ---: | ---: | ---: | ---: |
| Coordinator wave 1 (no block) | 1,452 | 198 (13.6%) | 61.4% | 40/119 (34%) |
| Coordinator wave 2 (no block) | 1,589 | 314 (19.8%) | 70.7% | 78/214 (36%) |
| Peer smoke 2 (block) | 126 | 30 (23.8%) | 74.7% | 16/34 (47%) |

The preregistration #381 targets are at most 20% of bytes from results over 5 KB
(M3) and at most 10% of context-mode results over 5 KB (M5). The table shows
`ctx_execute` specifically. It also includes legitimate `Read`-before-edit
exceptions, so these counts are not an adjudicated M3 result or an E2E execution
of #381. `Read`, `Bash` and `ctx_execute` dominate oversized-result bytes in the
supplied report. Tool choice alone did not contain what agents printed.

**Upstream verification and selection.** The connected context-mode 1.0.169 tool
schemas expose `requests`, `concurrency`, `intent` and `cwd`; the executor,
not the stale shell-only schema description, defines the working directory.
`claude --version` returned `2.1.283 (Claude Code)`. The
[context-mode v1.0.169 release notes](https://github.com/mksglu/context-mode/releases/tag/v1.0.169)
were checked via `gh api`; they describe accounting fixes, not a routing outcome.
The [Claude changelog at `7779afb1`](https://github.com/anthropics/claude-code/blob/7779afb12e3635f46f56ec823979d68350ae000b/CHANGELOG.md)
was checked for WebFetch and SubagentStart. The contracts that settle the change
are:

- [mksglu/context-mode `589d8214d56740a28b5f7bf63167743d586b0b40` (1.0.169), `src/server.ts` L3423-3478](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/server.ts#L3423-L3478): `ctx_fetch_and_index` retains fetched page content for `ctx_search`; multiple URLs use `requests` with `concurrency` (1-8). This is HTTP fetching, not JavaScript rendering.
- [Claude Code's WebFetch contract](https://code.claude.com/docs/en/tools-reference#webfetch-tool-behavior), read 2026-09-27, agrees with the supplied installed 2.1.283 description: ordinary results answer the extraction prompt through a small fast model. They are not authoritative page quotations. The page-evidence rule is our routing policy based on that distinction.
- [The same context-mode revision, `src/executor.ts` L295-312](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/executor.ts#L295-L312) runs every language except Rust at `cwdOverride ?? projectRoot` (#788); the [handler, L1822](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/server.ts#L1822) passes `cwd` for every language, and [routing.mjs L939-941](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/hooks/core/routing.mjs#L939-L941) already pins shell calls. Pass `cwd` for every language; non-shell child calls without it use the coordinator's checkout and writes persist. Only script files are temporary. [Rust, L290-292](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/executor.ts#L290-L292), runs in temp regardless of `cwd`, so use absolute project paths.
- [`src/server.ts` L1733-1740](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/server.ts#L1733-L1740): `intent` indexes sufficiently large output and returns section titles/previews for later search. Its [execution guidance](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/server.ts#L1675-L1690) still requires deriving answers in code. The [threshold constant](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/server.ts#L1979-L1980) is 5,000 bytes; the historical counter deliberately remains at 5,120. Neither is a hard cap on every response.
- [`ctx_search` schema, L88-94](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/search/ctx-search-schema.ts#L88-L94) defaults to 3 results per query. Specific queries with limit <=3 are local retrieval policy; the coordinator's later peer smoke 3 still had 11/20 search and 27/52 execute results over 5 KB ([separate observations](../../evidence/artifacts/token-lanes-subagent-start-20260927/measured-gaps.md#repair-round-observations-2026-09-27)).

Research used the installed `search-first` quick workflow, the visible skill
catalog and the [adopted find-skills reference at `7407f389`](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/skills/find-skills/SKILL.md).
The supported installed tools already provide these controls, so no new runtime,
skill installation or custom fetch mechanism is needed. The tool schemas and
official docs were checked directly; the coordinator's claims remain separately
attributed measurement evidence.

**Change and size (repair-round measurement, 2026-09-27).** The block adds
`ctx_fetch_and_index` and exact task-selected lane ids to its single ToolSearch
bootstrap, states the tool-grant boundary, routes page fetches and quotations,
uses specific search queries with limit <=3, requests `intent` while retaining
“print derived answers”, and passes `cwd` explicitly for every language with the
Rust exception. The
[handbook source section](../token-session-handbook.md#token-lanes-carried-into-subagents)
contains every guidance line and its sources. The block now says agents told
to return output unmodified skip both output-routing and footer rules, following
[`sweep.js` L83-87 at `5f3a7c21`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/5f3a7c21/tools/sota-convergence/landscape-sweep/sweep.js#L83-L87).
For all other agents the footer is again at the end of the return; that position
had been dropped in the first measured-gap build.

The carrier measures **4,051 UTF-8 bytes**. The former **3,500-byte** local bound
rejects it, so the bound becomes **4,100 bytes**, leaving 49 bytes of headroom.
The required safety, tool-grant and retrieval instructions cannot fit the prior
build's 10 spare bytes. The bound grows only by the measured need, and the block stays as short as its rules allow;
unrelated lane guidance is unchanged. Relative to the 3,490-byte build:

| Required change | Additional UTF-8 bytes |
| --- | ---: |
| Exact lane tool ids and exposure/grant boundary | 316 |
| Executor-backed cwd rule and Rust exception | 122 |
| Specific search queries and limit <=3 | 54 |
| Full wrapper exemption and footer position | 69 |
| Total | 561 |

The original carrier's 3,159 bytes remain historical evidence. The checksum is
refreshed; `hook_additional_context` delivery to every non-blind child, the
blind-role gate and fail-open implementation are unchanged. The text test covers
all seven shipped non-blind roles plus general-purpose, workflow, teammate and
unknown roles; it verifies the exact additionalContext object, not tool access.

### Dated errata and anti-patterns

| Earlier assumption or omission | Correction and verification path |
| --- | --- |
| Trusting the cwd schema text (`server.ts:1731`) over the executor | The executor (`executor.ts:295-312`, #788) uses `cwdOverride ?? projectRoot`; the handler passes cwd for every language and `routing.mjs:939-941` already pins shell calls. Pass cwd explicitly; Rust uses absolute project paths. The original "server is bound to the main checkout" sentence is correct for non-shell child calls without cwd. The first build's shell-only rule and claimed correction were wrong. |
| Naming `ctx_execute` alone contains large printed output | State `intent` and continue printing derived answers. The connected schema and L1736-1738 document preview/index behavior; M5's smoke-2 16/34 demonstrates the unclosed measured gap. |
| A WebFetch extraction is page text suitable as quotation evidence | Retrieve page text through `ctx_fetch_and_index` and `ctx_search`, citing both upstream contracts. The descriptive M4-style 0/15 count motivates the rule but cannot score compliance without tool-exposure evidence. |

The earlier size statement describes the original artifact, not this revision.
The retained counters are unchanged `.txt` records of the copied revisions; the
tool-profile source later added a ctxSrch column (see the dated provenance erratum
in measured-gaps.md). Adding the records does
not turn local measurement into an unchanged upstream test. New text controls
failed first at the hook's injected-context boundary, including web routing,
`intent`/`cwd` and the wrapper exemption. The unchanged blind and fail-open tests
and installer temp-directory checks cover integration, not model compliance.

**Overturn condition.** Re-measure **M4-style routing and M5-style containment
on the next sweep run and on the next coordinator waves**. For each child,
record an alias, role/task mix, carrier revision, whether `ctx_fetch_and_index`
and WebFetch were exposed (yes/no/unknown), the native tool-list or ToolSearch
evidence for each flag, fetch counts, containment counts and wrapper copy checks.
Count only fetches by children with confirmed `ctx_fetch_and_index` exposure in
the routing denominator; report absent and unknown exposure separately rather
than calling them non-compliant. Include nested/unclassifiable fetches and mark
their uncertainty. Keep out-of-population results separate from #381's
stack-researcher/Codex B metric and its >=0.9 threshold. Smoke 2 cannot provide an
access-qualified baseline retroactively. If routing remains poor in children
with the tool available, enforce research routing by agent type: dispatch through
[`stack-researcher`](../../adoption/agents/claude/stack-researcher.md), whose tools
list includes WebSearch and `ctx_fetch_and_index` and excludes WebFetch. The
[role-dispatch decision](2026-09-26-stack-agents-role-dispatch.md) supplies that
existing option. Revisit containment if M5 remains above its target; merely
delivering the text cannot close it. No after-change native workflow run, live
installation, provider usage or token savings is claimed here.

## Addendum 2026-09-27: qmd scope in the carrier

**Need.** The named QMD index `native-agent-stack-catalog` gained two collections on the workstation on
2026-09-27: `foundation-docs` (docs/, with `ecosystem/**` ignored because it holds the generated guide) and
`foundation-adoption` (adoption/). The token E2E session's E1 task needed `adoption/update.md`, which neither
us-equities collection contains. A QMD MCP server reads its default collection list once, when it is created
([qmd v2.8.3 `src/mcp/server.ts` L189](https://github.com/tobi/qmd/blob/v2.8.3/src/mcp/server.ts#L189)), and a `query` without `collections` searches only that list
([L355](https://github.com/tobi/qmd/blob/v2.8.3/src/mcp/server.ts#L355)). An explicit filter ([L330](https://github.com/tobi/qmd/blob/v2.8.3/src/mcp/server.ts#L330)) reaches collections added later. On 2026-09-27 a lexical
`query` with `collections: ["foundation-adoption"]` and `rerank: false`, sent through this workstation's QMD MCP
server, returned `foundation-adoption/update.md` as its top hit. That server's start-up instructions still listed
only the two us-equities collections and 121 documents.

**Change.** The carrier's QMD line now reads: "Use qmd query with collections (foundation-docs,
foundation-adoption, us-equities-foundation, us-equities-catalog), then get a line window." The window follows the
query tool's own recipe, `get(file, fromLine = max(1, line - 20), maxLines = 80, lineNumbers = true)`
([L257](https://github.com/tobi/qmd/blob/v2.8.3/src/mcp/server.ts#L257); `get` parameters at [L412-413](https://github.com/tobi/qmd/blob/v2.8.3/src/mcp/server.ts#L412-L413)). It is a bounded read, like Read with an offset
and a limit, not a lossless transform, and line numbers stay on for `file:line` citations. The handbook mirror and
its sources line changed with it. The portable setup in
[native-workflows.md](../../catalogs/us-equities/native-workflows.md#use-the-catalog-without-loading-all-of-it) and
[adoption/update.md](../../adoption/update.md#refresh-only-adopted-retrieval) now creates the two foundation
collections, so the four names resolve on any host that follows it.

**Size.** The block measures **4,094 UTF-8 bytes**, within the existing **4,100-byte** bound, which does not
move. Relative to the 4,051-byte block:

| Change | Additional UTF-8 bytes |
| --- | ---: |
| Four collection names and the explicit `collections` wording | 29 |
| "a line window" | 14 |
| Total | 43 |

**Alternatives rejected.**
- Keep the two-collection line and restart every QMD MCP server after a collection change. A server's default
  list is fixed at creation, and long-lived sessions on any host would silently search the old scope.
- Look up collections with the `status` tool before each search. That adds a call to every task; keep it for
  troubleshooting.
- `lineNumbers:false` on `get` and `multi_get` with `maxLines`, from an unmerged first build of this change. The
  independent review found three problems: `multi_get` is outside the carrier's single ToolSearch list and the
  `stack-researcher` grant; `maxLines` truncates each file although the first build called it lossless; and those
  two items pushed the block to 4,152 bytes and the bound to 4,200 without a measured need. Line numbers also
  serve `file:line` citations. All were withdrawn.

**Overturn.** Revisit if QMD refreshes its default collection list per call (an upstream change at L189 or L355),
if the index's collections change, or if a measured child run shows the four-name scope missing documents that a
`status` lookup would have found.

**#381.** The carrier hash changes. #381 freezes carrier and skill hashes at execution
([sources, boundaries and freeze, step 2](../../evidence/artifacts/token-adoption-e2e-20260926/README.md#sources-boundaries-and-freeze)),
so its run records the installed hash and install time. No other carrier rule changed, and no child run with this
block is claimed.

## Addendum 2026-09-27: role-matched blocks

**Need: instructions must match grants.** A subagent whose `tools` field is an explicit allowlist can use only the
tools it lists; an omitted field inherits the parent's tools ([sub-agents](https://code.claude.com/docs/en/sub-agents)).
ToolSearch returns only granted tools
([measured gaps](../../evidence/artifacts/token-lanes-subagent-start-20260927/measured-gaps.md#repair-round-observations-2026-09-27)).
The Decision above sent the same 4,094-byte block, which names 17 MCP tool ids, to every non-blind child. Seven of
the eight shipped non-blind roles therefore received instructions to load or use tools they cannot call. The table
compares each [`adoption/agents/claude/*.md`](../../adoption/agents/claude/) `tools:` line at base `e82e6be7` with
that block:

| `agent_type` | Ungranted ids named | Lines needing a tool the role lacks |
| --- | ---: | --- |
| `stack-researcher` | 5 of 17 | SocratiCode clause, codebase-memory, Headroom; both skills (no Skill tool or `skills:` preload) |
| `stack-verifier` | 14 of 17 | fetch, code navigation, codebase-memory, QMD and ai-memory, Headroom; both skills |
| `evidence-reviewer` | 8 of 17 | fetch, RTK (no Bash), jCodeMunch `menu`, codebase-memory, QMD, Headroom; both skills |
| `security-reviewer` | 8 of 17 | as `evidence-reviewer` (its only preload is `security-best-practices`) |
| `isolated-builder` | 8 of 17 | fetch, jCodeMunch `menu`, codebase-memory, QMD MCP, Headroom; `search-first` |
| `source-scout` | 17 of 17 | bootstrap (no ToolSearch), every MCP line, the RTK line's `ctx_execute` clause; both skills |
| `semantic-evidence-reviewer` | 17 of 17 | every line except TOON and one-lane accounting (no Bash, ToolSearch or Skill) |
| `landscape-sweep-worker` | 0 | none: it has no `tools:` line and inherits every tool except WebFetch |

The three `blind-*` roles already received 0 bytes.

**Change.** The [hook](../../adoption/hooks/claude/token-lanes-subagent-start.py) keeps the `blind-*` gate and
adds a literal map from the exact `agent_type` to a sibling block. It never builds a path from `agent_type`:
`stack-researcher`, `stack-verifier`, `evidence-reviewer` and `security-reviewer` (one shared reviewer block),
`isolated-builder` and `source-scout` get role blocks; `semantic-evidence-reviewer` joins an exact-name set that
receives nothing; every other value keeps [`token-lanes-block.md`](../../adoption/hooks/claude/token-lanes-block.md)
unchanged. A missing, empty or unreadable role block is silent and does not fall back to the default, because the
default would restore the ungranted ids. Each role block copies its lines from the default block. Where a line
names ungranted tools, a variant replaces it; the variants are stated verbatim in the
[handbook](../token-session-handbook.md#token-lanes-carried-into-subagents), with the agent-type table.
Two corrections from the design's verification apply. The builder's output line says `cwd = the owned worktree
your brief names`, since [`isolated-builder.md`](../../adoption/agents/claude/isolated-builder.md) starts in the
coordinator's directory, which is not its to edit. The builder keeps only the verification sentence: that skill
is preloaded in its frontmatter, and `search-first` would need the Skill tool it lacks.

| Block | UTF-8 bytes | MCP ids named |
| --- | ---: | ---: |
| `token-lanes-block.md` (default, unchanged) | 4,094 | 17 |
| `token-lanes-block.researcher.md` | 3,075 | 12 |
| `token-lanes-block.builder.md` | 2,883 | 9 |
| `token-lanes-block.verifier.md` | 2,186 | 4 |
| `token-lanes-block.reviewer.md` | 2,088 | 9 |
| `token-lanes-block.scout.md` | 1,089 | 0 |
| `semantic-evidence-reviewer` | 0 | 0 |

Every block stays within the unchanged 4,100-byte bound. The
[installer](../../tools/adoption/install_claude_profile.py) `HOOKS` map and
[`SHA256SUMS`](../../adoption/hooks/claude/SHA256SUMS) add the five role blocks, listed before the script, so an
upgrade installs a new script after its siblings.

**Tests.** The [text contract test](../../tests/test_token_lanes_subagent_start.py) now expects each type's own
block, keeps the full-block key phrases on the default and gives each role block its own phrase set. It applies
the budget, host-path and verbatim-handbook checks to all six files, and adds a grant-agreement test. For each
shipped agent with a `tools:` line, every `mcp__` id the hook injects for its `agent_type` must be in that line.
So must every tool a line names or needs: ToolSearch, Bash for the RTK line, `ctx_fetch_and_index` and the other
bare lane tool names. A named skill must be invocable through the Skill tool or preloaded through `skills:`. As a
failing-first control, run against the unchanged hook, that test failed for 7 of the 10 allowlisted agents (every
row above except `landscape-sweep-worker`; the blind roles passed with 0 bytes); it passes after the change. This
is text-versus-allowlist agreement checked by local subprocess tests, not a native child run, observed tool
exposure, compliance or a token saving.

**Supersedes.** The Decision's "default routing carrier for every non-blind subagent" now means the default for
every non-blind type that neither the map nor the silent set (`semantic-evidence-reviewer`) names. Exclusion stays inside the hook. The measured-gap addendum's coverage
sentence ("covers all seven shipped non-blind roles ... not tool access") is superseded by the per-role
expectations and the grant-agreement test above.

**No grant in this change.** The repository's own rules reject adding a tool to these roles now:
- the [role-dispatch record, alternative 5](2026-09-26-stack-agents-role-dispatch.md#alternatives) (L82-83)
  grants a lane only with a written route in the body and prunes it by measured use;
- the [harness-settings record, `codebase-memory-mcp#2`](2026-09-27-claude-harness-settings.md#codebase-memory-mcp-codebase-memory-mcp2)
  (L75-84) says no shipped agent's exact tool list gains codebase-memory tools until each platform has a pinned
  install and each intended agent has a recorded useful call;
- the [workflow role-routing notes](../../examples/claude-native/workflows/README.md#role-routing-and-child-prompt-size-2026-09-21) (L494)
  keeps guarded Headroom coordinator-side;
- #381's [preregistration](../../evidence/artifacts/token-adoption-e2e-20260926/preregistration.json) says of
  Headroom "No default role grant; report M10 N/A and explain any invocation."

The five role bodies sealed for #381 are unchanged, so no amendment is needed. A later `stack-researcher` grant of
the read-only codebase-memory tools remains possible. It would need #381 to have executed or an Amendment 3, the
`codebase-memory-mcp#2` overturn condition, a written body route and a role-dispatch addendum.

**Alternatives rejected.**
- Native per-agent `SubagentStart` matchers. Upstream supports a matcher on the agent name. They would add one
  settings group per role to the template's single empty-matcher group, which the installer merge test pins.
- One block with "where granted" qualifiers. It would exceed the 4,100-byte bound and still name ungranted ids.
- Skipping every named role. That would drop carrier-only rules the sealed bodies do not state: `intent`, `cwd`
  for every language and the RTK rewrite details.
- Falling back to the default block when a role block is missing. That restores the ungranted ids.

**#381.** The carrier is now the hook and six block files. #381 freezes "carrier and skill hashes" at execution
([step 2](../../evidence/artifacts/token-adoption-e2e-20260926/README.md#procedure--aa-84)), so its run records
the installed hash of the hook and of every block file. `SHA256SUMS` lists all seven together. In arm B the frozen
named roles now receive their role blocks instead of the default block.

**Limitations and open items.** A plugin-scoped `agent_type` such as `my-plugin:stack-verifier` receives the
default block, as the blind gate already documents for plugin-shipped roles; the installer copies user agents
with bare names. The map also matches a same-named agent in any other project, because the hook runs from user settings for every project and a project-scope definition overrides the user-scope one; that agent receives the role block written for the shipped allowlist whatever its own `tools:` line grants, and the grant-agreement test checks only the shipped definitions. A new shipped agent with a `tools:` line and no map entry receives the default block, and the
grant-agreement test fails for it unless its allowlist covers every line. The Codex stack-worker profile's
codebase-memory and Headroom exposure is outside this Claude carrier and is not reconciled here.

**Overturn.** Revisit a role block when its agent's `tools:` line changes, though the grant-agreement test
fails only when a block still names a tool the line no longer grants; a new grant or a `disallowedTools` entry fails no test. Also revisit when a native child run shows a role block without a lane that the role uses and is
granted, or when a SubagentStart hook can read the child's resolved tool list, which would let one block be
filtered at run time.

| Earlier assumption | Correction and verification path |
| --- | --- |
| One carrier text fits every non-blind child | Allowlisted roles receive only lanes their `tools:` line grants; the grant-agreement test compares each shipped allowlist with the injected text. |

## Addendum 2026-09-28: verification line

**Need.** Since the original carrier ([#378](https://github.com/seathatflowsinourveins/native-agent-stack/pull/378),
merged 2026-09-27T06:11:54Z), its last line has told every child that receives the default block: "Before claiming a
task done, follow the installed verification-before-completion skill: real command output before any success claim."
The role-matched blocks kept that sentence for `isolated-builder`. It is an explicit verification instruction. The
[Opus 5 prompting guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5.md),
read 2026-09-28, says at L61 that Claude Opus 5 "verifies its own work without being told to", that explicit
verification instructions "cause over-verification" and should be removed, and that "The same applies to legacy
harness scaffolding that adds separate verification steps." At L81, re-check instructions "compound with the model's
own behavior and add cost without improving results." The
[Opus 5.5 guide, L9](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5.md)
keeps the Opus 5 patterns as "a reasonable starting point", and
[prompting best practices, L780](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices.md)
makes Opus 5 the exception to its self-check advice: "remove these instructions rather than rewriting them." The
sentence also assumes a command runner. A child whose tools include neither Bash nor Context Mode's `ctx_execute`,
such as a plugin-scoped or unmapped allowlisted agent (role-matched addendum, limitations), still receives the
default block and cannot return command output. A role without Bash but with `ctx_execute`, such as
[`security-reviewer`](../../adoption/agents/claude/security-reviewer.md), can. This
carrier's own unit wrote the line, so, as with the qmd scope, a dated addendum changes it. Each documentation quote
in this addendum was re-read at its cited line of the page's Markdown source at 08:55Z on 2026-09-28.

**Change: default block.** Line 13 of [`token-lanes-block.md`](../../adoption/hooks/claude/token-lanes-block.md) now
reads: "Show evidence before a success claim: the command and what it returned (code.claude.com best practices), or
the file:line read. Research upstream first with the installed search-first skill before writing custom code.
Source: skillOverrides in adoption/templates/claude.settings.template.json." The first sentence follows
[Claude Code best practices, L52](https://code.claude.com/docs/en/best-practices.md): "Have Claude show evidence
rather than asserting success: the test output, the command it ran and what it returned, or a screenshot of the
result." The tag follows the item L52 names. The file:line alternative is local policy, not in L52: a file:line
read is evidence that a child without Bash can give. The sentence asks for the evidence of work already done; it
adds no verification step and names no skill. The `search-first` sentence and its source are unchanged. The
[handbook](../token-session-handbook.md#token-lanes-carried-into-subagents) mirrors the line, and its sources
paragraph now names only `search-first` under `skillOverrides`, with the sources above and the local-policy note.

**Builder line, decided on its own merits: removed.** `isolated-builder` has Bash, so the argument about children
without Bash does not apply to it. Its line goes for another reason: it was the third copy of one instruction. The
unchanged [`isolated-builder.md`](../../adoption/agents/claude/isolated-builder.md) preloads
`verification-before-completion` in its frontmatter (L7-9), and "The full content of each listed skill is injected
into the subagent's context at startup" ([sub-agents reference, L600](https://code.claude.com/docs/en/sub-agents.md)).
Its body at L12 says "Use the preloaded verification-before-completion skill before claiming success". It runs
`model: opus` (L5), which on this host has resolved to Opus 5.5 since September 22
([grand catalog handbook, L242-244](../grand-catalog-handbook.md#runtime-workers-sdks-and-research-applications)),
so the Opus 5 advice reaches it through the 5.5 guide's L9 carry-forward. Before
[#402](https://github.com/seathatflowsinourveins/native-agent-stack/pull/402) (`d022295a`, merged
2026-09-27T14:04:25Z) it ran `model: sonnet`. The role-matched addendum kept the sentence because the role could
follow it: the skill is preloaded, while `search-first` would need a Skill tool the role lacks. That makes a line
admissible, not needed. The frontmatter preload and the body line stay as they are; agent
definitions are outside this change, which also leaves the skill's `on` listing unchanged. The handbook drops the
builder-verification variant and that item from the builder's table row.

| Block | Before (UTF-8 bytes) | After | Change |
| --- | ---: | ---: | --- |
| `token-lanes-block.md` | 4,094 | 4,088 | line 13 goes from 301 to 295 bytes |
| `token-lanes-block.builder.md` | 2,883 | 2,747 | the 135-byte verification line and its newline are removed |

The 4,100-byte bound does not move, and the other four role blocks are unchanged.
[`SHA256SUMS`](../../adoption/hooks/claude/SHA256SUMS) lists both new hashes.

**Tests.** In the [text contract test](../../tests/test_token_lanes_subagent_start.py), the default block's key phrase
`verification-before-completion` becomes `Show evidence before a success claim`, and the builder's phrase set drops
the skill name. A new withdrawn-phrase check requires that no block file names `verification-before-completion`; the
grant-agreement test's skill guard is unchanged. As a failing-first control, the new module ran against the base
(`f508ffba`) default block, builder block and handbook together, so the verbatim-handbook check still held.
`python3 -m unittest tests.test_token_lanes_subagent_start` returned "FAILED (failures=19)": the withdrawn phrase in
both blocks, and the new key phrase missing from the default block file and from each of the 16 hook payloads that
receive the default block. With this change the same command returns "Ran 17 tests" and "OK". This is local text
agreement, not a native child run, compliance or a measured saving.

**Boundary.** The upstream removal advice is written for Claude Opus 5 and carried forward to Opus 5.5. For other
models, best practices L780 still says a self-check "catches errors reliably, especially for coding and math". The
default block also reaches children on other models, such as the Haiku probe and the Sonnet wrappers above; for them
the evidence sentence is what remains, and the overturn conditions below give them their own comparison.

**Alternatives rejected.**
- Keep the default line with a model or tool qualifier. Best practices L780 says to remove such instructions on
  Opus 5 rather than rewrite them, and the carrier text cannot see the child's model or tools.
- Reword the builder line to the evidence sentence (2,877 bytes). The preloaded skill's core principle is already
  "Evidence before claims, always"
  ([obra/superpowers `8ca22db`, `skills/verification-before-completion/SKILL.md` L10](https://github.com/obra/superpowers/blob/8ca22dba9a94f28898bbce59f2537ff4d87c747d/skills/verification-before-completion/SKILL.md#L10);
  the installed copy on this host matched the manifest's `skill_md_sha256` under `sha256sum` on 2026-09-28), so the
  line would still duplicate the preload.
- Remove the builder's preload or its body line as well. Agent definitions are outside this change; the
  [skills-trial record](2026-09-25-skills-trial-and-usage.md#addendum-2026-09-28-carrier-conditions-and-the-verification-review-rule)
  adds a with/without comparison of that preload to the skill's review.
- Follow the community setups that keep standing self-verify instructions, such as superpowers, this skill's source.
  Their popularity is not evidence, and the primary sources above point the other way.

**#381.** The carrier hash changes again. #381 freezes carrier and skill hashes at execution
([procedure, step 2](../../evidence/artifacts/token-adoption-e2e-20260926/README.md#procedure--aa-84)), so its run
records the hash of the hook and of every block file. Step 2 records no install time, and the installer writes none:
[`install_claude_profile.py`](../../tools/adoption/install_claude_profile.py) copies with `shutil.copy2` (L113),
which keeps the source file's modification time. At `f508ffba`, and at `origin/main` `4f31ef46` on 2026-09-28, its
README reads "frozen protocol, not executed or accepted"; that is the committed record, not live state, and this
change lands only if the E2E has not started. A host receives the new text at its next
`python3 tools/adoption/install_claude_profile.py --only guard`; this change runs no installer, and no child run with
this text is claimed.

**Supersedes.** In the [role-matched addendum](#addendum-2026-09-27-role-matched-blocks), "The builder keeps only the
verification sentence" and the byte counts 4,094 (default) and 2,883 (builder) describe the previous revision. The
[qmd addendum](#addendum-2026-09-27-qmd-scope-in-the-carrier)'s "#381" paragraph says the run records "the installed
hash and install time"; step 2 freezes hashes, not an install time, as above.

**Overturn.** Each condition names what it varies. Each comparison runs through an upstream evaluation harness named
with its pin before the run, on frozen tasks, and counts review-found defects, tokens and elapsed time.
- Default block: restore an explicit verification instruction if a comparison that varies line 13 alone (the removed
  sentence against the evidence sentence), with `general-purpose` or Workflow children on the coordinator's model,
  shows fewer defects with the instruction at no larger token or time cost.
- Other models: run the same comparison with children on a non-Opus model, such as Haiku or Sonnet. A gain there
  alone supports a line in a role block for an agent type on that model, not in the default block, because the
  carrier cannot see a child's model.
- Builder: the skills-trial comparison varies the builder's preload, not a carrier line, so it cannot overturn this
  removal. Restore the builder line only if a comparison that varies that line, with the preload held on, shows the
  same gain.
- Any child: a Claude prompting guide for the running model reverses the L61 and L81 advice.

| Earlier assumption | Correction and verification path |
| --- | --- |
| A standing instruction to follow the verification skill belongs in every child's start context | The Opus 5 guide (L61, L81), carried forward by the 5.5 guide (L9), says to remove explicit verification instructions. The carrier now asks only for evidence, the builder gets the skill from its own preload, and the withdrawn-phrase test keeps the skill name out of every block. |

## Addendum 2026-09-28: builder evidence sentence

**Need.** The [verification-line addendum](#addendum-2026-09-28-verification-line) removed the builder's line for one
reason: "Its line goes for another reason: it was the third copy of one instruction." It rejected the evidence
sentence as the builder's line for the same reason: "so the line would still duplicate the preload." Both rest on the
builder's `verification-before-completion` preload and the body line that named it. On 2026-09-28 the skills trial
removed that skill under its conflict rule, and with it the preload and the body line in all three copies of
`isolated-builder.md` ([removal addendum](2026-09-25-skills-trial-and-usage.md#addendum-2026-09-28-verification-before-completion-removed-conflict-rule)).
The hook gives `isolated-builder` its role block instead of the default block
([role-matched addendum](#addendum-2026-09-27-role-matched-blocks)), so the default block's line 13 does not reach it.
Its body still says "Run the appropriate existing checks and report their outcomes", which names no form of evidence.
Without a change here, the builder's definition and role block would carry no evidence rule.

**Change.** [`token-lanes-block.builder.md`](../../adoption/hooks/claude/token-lanes-block.builder.md) gains, as its
last line, the first sentence of the default block's line 13: "Show evidence before a success claim: the command and
what it returned (code.claude.com best practices), or the file:line read." This is the builder text the
verification-line addendum weighed and rejected as a duplicate, at the size it gave: the block goes from 2,747 to
2,877 UTF-8 bytes and from 9 to 10 lines. The `search-first` and Source sentences stay out because the builder has no
Skill tool; C2 gave the builder the verification sentence alone for the same reason. As in the default block, the
sentence asks for the evidence of work already done, adds no verification step and names no skill, so the Opus 5
advice to remove explicit verification instructions (L61, L81) does not apply to it.
[`SHA256SUMS`](../../adoption/hooks/claude/SHA256SUMS) lists the new hash: `c665c230…` becomes `c81a91c4…`. The
[handbook](../token-session-handbook.md#token-lanes-carried-into-subagents) adds "builder evidence" to the builder's
table row and a builder-evidence variant that gives the reason.

**The verification-line addendum's builder overturn.** It reads "Restore the builder line only if a comparison that
varies that line, with the preload held on, shows the same gain." This change neither meets nor relies on it. That condition
governs the removed verification line and presupposes the preload, which no longer exists. The new line is the
evidence sentence, which the verification-line addendum turned down for the builder only because it duplicated the
preload.

**Tests.** In the [text contract test](../../tests/test_token_lanes_subagent_start.py), the builder's key phrases gain
`Show evidence before a success claim`. The withdrawn-phrase check and the grant-agreement test's skill guard are
unchanged; the check's comment now says that no agent preloads the skill and that the builder block carries the
evidence sentence instead. As a failing-first control, the changed module ran against the base (`3058b237`) builder
block with this change's handbook, so the verbatim-handbook check still held.
`python3 -m unittest tests.test_token_lanes_subagent_start` returned "Ran 17 tests" and "FAILED (failures=2)": the
builder block file and the hook's `isolated-builder` payload each lacked the new key phrase. With this change the same
command returns "Ran 17 tests" and "OK". This is local text agreement, not a native child run, compliance or a
measured saving.

**#381.** The builder block hash changes again, and #381 records each block file's hash at execution
([procedure, step 2](../../evidence/artifacts/token-adoption-e2e-20260926/README.md#procedure--aa-84)). The
preload removal also changes the builder's role body, which #381 pins by hash:
[its Amendment 3](../../evidence/artifacts/token-adoption-e2e-20260926/README.md#amendment-3-2026-09-28-the-isolated-builder-body-without-verification-before-completion-before-execution)
replaces the `isolated-builder.md` row before execution. A host receives the new block and body at its next
`python3 tools/adoption/install_claude_profile.py --only guard --only agents`; this change runs no installer, and no
child run with this text is claimed.

**Supersedes.** In the verification-line addendum, "The frontmatter preload and the body line stay as they are", the
rejected alternatives "Reword the builder line to the evidence sentence (2,877 bytes)" and "Remove the builder's
preload or its body line as well", and the table cell "the builder gets the skill from its own preload" describe the
previous revision.

**Overturn.**
- Remove the builder's evidence line if the builder again receives the same rule at start from another source, such
  as a re-pinned skill preload or a body line, since the verification-line addendum's duplication reason then returns.
- Remove it if a comparison that varies this line alone, run as the verification-line addendum's overturn conditions
  describe, shows no fewer review-found defects with the line and a larger token or time cost.

| Earlier assumption | Correction and verification path |
| --- | --- |
| The builder's own preload gives it the evidence rule, so a block line would only duplicate it | Since 2026-09-28 no agent preloads the skill. The builder block's last line carries the evidence sentence, and the builder's key-phrase test keeps it there. |

## Addendum 2026-09-27: jCodeMunch route arguments

Ported 2026-10-03 by session native-agent-stack-0c from #435 (head 319af22d)

**Need.** The four carriers that name jCodeMunch offered `route(task, repo?, execute?)` and
`order(action, args)`. The default and researcher also named `menu(query?)`. In jcodemunch-mcp
1.108.319, `route` builds an action's arguments from its own inputs. The installed package's
`counter.py` and `server.py` are byte-identical to upstream
[`8f7b34ab`](https://github.com/jgravelle/jcodemunch-mcp/tree/8f7b34abe16fb459e0bf1c04747d584216dfe32e):

- `_QUERY_ARG` maps `search_symbols` and `search_text` to `query`
  ([`counter.py` L584-590](https://github.com/jgravelle/jcodemunch-mcp/blob/8f7b34abe16fb459e0bf1c04747d584216dfe32e/src/jcodemunch_mcp/counter.py#L584-L590)).
- `shape_execute_args` returns `{"repo": repo, qarg: task}`, and returns None when repo is empty
  ([L616-630](https://github.com/jgravelle/jcodemunch-mcp/blob/8f7b34abe16fb459e0bf1c04747d584216dfe32e/src/jcodemunch_mcp/counter.py#L616-L630)).
- `_handle_route` uses that shape for each recommendation's `args_template` (L5549) and, with
  `execute`, for the dispatched call (L5562)
  ([`server.py` L5535-5580](https://github.com/jgravelle/jcodemunch-mcp/blob/8f7b34abe16fb459e0bf1c04747d584216dfe32e/src/jcodemunch_mcp/server.py#L5535-L5580)).

The October 3 source check also compared `counter.py` at
[v1.108.327](https://github.com/jgravelle/jcodemunch-mcp/blob/v1.108.327/src/jcodemunch_mcp/counter.py#L616-L630)
(published October 2) and upstream main. All three revisions have Git blob
`0605443d87ed6ec035b14831e99fb7c6540f7b12`, 33,194 bytes and SHA-256
`d56ba52f8ed5716f6ec9e2d79ab53d4333972fe1ad2a36cb981ff4752c0c97aa`. This port changes no component pin.
A symbol search run through `route(execute=true)` therefore searches for the whole task text.

The coordinator's native probes on 2026-09-27
([record](../../evidence/artifacts/jcodemunch-route-args-20260927/README.md)) showed three results:

- `order search_symbols {repo: ".", query: "register_file", kind: "function", max_results: 1}`
  returned the target in one call.
- `route("register_file", repo: ".", execute: true)` ranked the state-changing `register_edit`
  first and executed nothing.
- `route(<sentence>, repo: ".")` recommended `search_symbols` with the whole sentence as its
  template query.

Another session's Codex-lane gate,
[PR #433](https://github.com/seathatflowsinourveins/native-agent-stack/pull/433)
(`tools/capability-gate`, merged on 2026-09-27 as `55fc8d17`), measured the same failure. In its first
smoke (run 2026-09-27T20:09:50Z), `route` with the sentence and `execute: true` returned neither
target symbol in 6 of 6 runs. Its gate case, `order search_symbols` with the identifier, passed 6
of 6 rows with exactly one completed call each (run 2026-09-27T20:16:19Z, promptfoo 0.123.1
`openai:codex-sdk`). Under the gate's repaired scoring its rows passed again, 6 of 6, each with
exactly one completed `order search_symbols` that returned the signature. PR #433 classes all
these runs as workstation smoke, not receipts, and lists its pre-repair smokes (20:09Z-20:31Z)
as superseded by the repaired-scoring rows. These are dated observations, not new executions.

**Change.** Only the jCodeMunch clause changes in each of the four carrier blocks:

- Default: `jcodemunch route(task, repo: ".") (no execute), menu(query?), order(action, own args) on indexed repos;`
- Researcher: the same clause, ending `on indexed repos.` Its line has no SocratiCode clause and
  still ends with "Open original source before judging or editing."
- Builder and reviewer: `jcodemunch route(task, repo: ".") (no execute), order(action, own args) on indexed repos;`

Serena `find_symbol`, earlier on the same line, already covers a known name for Claude
subagents. The jCodeMunch clause serves open tasks: `route` recommends, and the caller writes
the `order` arguments. The default and researcher retain `menu(query?)`; builder and reviewer
have no menu grant and name no `menu(` call. All ToolSearch ids and every other carrier line
stay as they were. The handbook mirrors all three line variants verbatim, cites the source
lines and probes, and gives `order("search_symbols", {repo, query: NAME})` for a known name.
The scout and verifier blocks name no jCodeMunch tool and remain unchanged.

Two comment lines beside the jcodemunch approval list in
[`project.codex.config.template.toml`](../../adoption/templates/project.codex.config.template.toml)
repeat the rule, cite `counter.py` L616-630 and identify the identical blob at v1.108.327.
The parsed TOML stays unchanged. The two probe files are copied byte for byte from #435's pinned
head; their README describes that original change, including its original Codex scope. The
residuals below define what this port actually carries.

**Size at the port base.** The sizes were measured at `1f5a791b02a230aced670c88bab3d3d0ebcf401a`,
the builder's worktree base. The four blocks and every other port path are byte-identical between
it and the PR base `463a57b983eec540ae90eb45c2b1a7c6fc469aed`, so the figures hold there.
Each block keeps the existing **4,100-byte** bound. Clause bytes include the terminating
semicolon or period; default/researcher clauses have the menu form, builder/reviewer omit it.

| Block | Former clause bytes | Former block bytes | New clause bytes | New block bytes | Bytes below bound |
| --- | ---: | ---: | ---: | ---: | ---: |
| Default | 92 | 4,088 | 103 | 4,099 | 1 |
| Researcher | 92 | 3,075 | 103 | 3,086 | 1,014 |
| Builder | 78 | 2,877 | 89 | 2,888 | 1,212 |
| Reviewer | 78 | 2,088 | 89 | 2,099 | 2,001 |

**Alternatives rejected.** These retain #435's alternatives but recompute their sizes on this
base. For a common alternative clause, block bytes are former block bytes minus former clause
bytes plus alternative clause bytes. Numbers do not authorize changing a role's tool set.

| Alternative clause | Clause bytes | Default bytes | Researcher bytes | Builder bytes | Reviewer bytes | Reason |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `jcodemunch order(search_symbols, {repo: ".", query: NAME}) or route(task, repo: ".") on indexed repos;` | 102 | 4,098 | 3,085 | 2,901 | 2,112 | It now fits the default, but drops its required menu call and does not say execute stays off or that the caller writes order's arguments. Serena on the same line already covers known names. |
| `jcodemunch order(search_symbols, {repo: ".", query: NAME}) for a known name, else route(task, repo: ".") then order on indexed repos;` | 133 | 4,129 | 3,116 | 2,932 | 2,143 | Default exceeds the bound; default/researcher lose menu. |
| `jcodemunch order(search_symbols, {repo: ".", query: NAME}) for a known name; for open tasks route(task, repo: ".") (no execute), then order(action, own args) on indexed repos;` | 175 | 4,171 | 3,158 | 2,974 | 2,185 | Default exceeds the bound; default/researcher lose menu. |
| `jcodemunch route(task, repo: ".") (no execute), menu(query?), then order(action, own args) on indexed repos;` | 108 | 4,104 | 3,091 | 2,907 | 2,118 | Keeping menu and "then" exceeds the default bound; menu is ungranted to builder/reviewer. Removing "then" gives the accepted 103-byte menu clause. |
| #435's `jcodemunch route(task, repo: ".") (no execute) then order(action, own args) on indexed repos;` | 93 | 4,089 | 3,076 | 2,892 | 2,103 | Fits, but drops the default/researcher menu call. |
| Keep the former role-specific clause with `execute?` | 92 / 78 | 4,088 | 3,075 | 2,877 | 2,088 | `route(execute)` returned neither target symbol in 6 of 6 runs of #433's first smoke. |
| Pass the identifier alone as the task | n/a | n/a | n/a | n/a | n/a | Misroutes: `route("register_file", repo: ".", execute: true)` ranked the state-changing `register_edit` first and executed nothing. |

The accepted default retains menu because the later base is six bytes smaller than #435's
4,094-byte pre-change default, and this port omits the five-byte "then " connector. No other
line is shortened and the budget is not raised.

**Dated erratum and anti-pattern (2026-09-27).**

| Earlier assumption or omission | Correction and verification path |
| --- | --- |
| The carrier offered a tool's auto-execute mode from its signature, `route(task, repo?, execute?)` (the handler's docstring at `server.py` L5536), without reading how the tool shapes arguments. | `shape_execute_args` (`counter.py` L616-630) passes the whole task as the query, and the probes and #433's first smoke confirmed wrong targets. Read the argument-shaping code before recommending an execute or auto mode. The carrier now leaves `execute` off; `test_injected_jcodemunch_rule_leaves_execute_off` checks the five injected role contexts and their corrected clauses, and `test_jcodemunch_carriers_and_handbook_omit_execute_option` checks all carrier files and the entire handbook. |

The general lesson is also ported as one row in the anti-pattern log of
[harness defaults](../harness-defaults.md#anti-pattern-log). The new tests failed against the
old text first: `python3 -m unittest tests.test_token_lanes_subagent_start` returned exit 1,
`Ran 19 tests`, `FAILED (failures=10)`. Five failing subtests covered the required role
contexts, four covered the old carrier files and one covered the handbook. With the corrected
text at `e0c6b38d`, the same module ran 19 tests, OK, and the targeted suite ran 739 tests, OK
(12 skips).

**Evidence classes.**

- Upstream source read at a pinned commit, with the installed package byte-identical to it;
  the October 3 comparison also verifies the unchanged counter blob at v1.108.327 and main.
- The coordinator's historical native tool probes: one call each, against a local index.
- Another session's historical workstation smoke (#433).
- This port's structural and local integration tests, run failing first and then with corrected text.

No subagent or Codex worker run with the changed text is claimed, and no token saving or new
native probe execution. Installing changed carriers on a host is a separate step, not done here.

**Freeze and carrier hashes.** The old #381 hash note is replaced by the October 1 program's
explicit current-distro freeze lift
([decision, L10-12 and L408](2026-10-01-definitive-sota-wsl-program.md#decision)). The new
distribution leaves these carriers unwired
([map, L138-149](../../adoption/new-wsl/client-config-map.json)); this port changes none of its
map, records, generated blocks or tests. The four new
[`SHA256SUMS`](../../adoption/hooks/claude/SHA256SUMS) rows are:

```text
dcd6996e9247f3c8f3d543545eb958518236b21449492ddf92721590aa3f60c8  token-lanes-block.md
2f7a53031e6eabf6b9d08989b619b74204fa36dac2559e520fb72b06225a81d3  token-lanes-block.builder.md
149ac69352a788ad67c84b4d545cab461015c4e73a9ba4c8675259402c955e4a  token-lanes-block.researcher.md
ec7c6b2a80c58e0156daab25b7cfd4eea6f2e3eac77137067051601045f9d2f8  token-lanes-block.reviewer.md
```

**Residuals and overturn.**

- The Codex managed-block section is not ported. The configuration-owner coupling in
  `tests/test_new_wsl_client_config.py` L2861-2869 at this base (L2828-2838 at `dcae68bd`)
  requires that owner's record to describe
  its dropped template clauses. The decision belongs to the configuration owner or token
  lane. The two original Codex test edits and the two instruction templates stay unchanged.
- The three custom Codex agents and host rollout are out of scope. Installed carriers keep
  the old text until the host owner runs `install_claude_profile.py --only guard`. No installer
  or host managed-block writer ran in this port.
- A merged decision that removes jCodeMunch from the carriers, or an upstream change to
  `shape_execute_args`, overturns this port. The wave-2 "context-mode-only lane sentence"
  is a coordination draft, not a decision on this base. Restore an execute form only after
  upstream extracts identifiers or otherwise shapes search queries from tasks (a change
  at `counter.py` L616-630 or `_handle_route`), or a gate returns the target symbol using
  `route(execute=true)` in #433's fixture. Revisit wording if the carrier byte bound changes.

## Addendum 2026-10-04: main-session carrier

On 2026-10-04, the owner directed the WSL architecture-design coordinator and session 99 to complete the token-efficiency rollout:

The request requires clean upstream installation and seamless native-workflow defaults for future sessions, using each repository's upstream invocation and lifecycle commands; token-saving practice remains an essential layer.
[Claude's hooks contract](https://code.claude.com/docs/en/hooks#sessionstart) places SessionStart context in main sessions and SubagentStart context in child sessions.
Context Mode v1.0.169 provides its own [SessionStart implementation at 589d8214](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/hooks/sessionstart.mjs) and [event registration at the same pin](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/hooks/hooks.json#L120), source evidence separate from observed native loading.
The owner requested reporting the main session ready only after a real fresh-session E2E measures upstream invocation rates and provider token usage through the relevant lifecycle skills.
The requested scope includes main sessions, Ultracode subagents and experimental agent teams, where the relevant client's native lifecycle supports them.
The request remains open until upstream integration and fresh-session qualification are complete; clean installation alone establishes neither an accepted rollout nor measured savings.
The carrier implementation and unchanged E2E overturn below define this addendum's delivered scope; they supply no new measured savings or lifecycle acceptance.

The SubagentStart carrier reaches subagents only, and main sessions were reported reading whole files and choosing Bash
over the lanes (reported to this unit, not re-run here). [`token-lanes-session-start.py`](../../adoption/hooks/claude/token-lanes-session-start.py)
now returns [`token-lanes-block.main.md`](../../adoption/hooks/claude/token-lanes-block.main.md) (1,842 of 2,600 bytes)
as SessionStart `additionalContext` for startup, resume, clear, compact and fork (a separate source since v2.1.214 that
runs SessionStart hooks again); `blind-*` and silent roles get nothing, as in this carrier. The template gains one
group, and `HOOKS` and `SHA256SUMS` list both files. The text is advisory, not enforcement
([handbook](../token-session-handbook.md#token-lanes-carried-into-the-main-session)). Overturn: drop or rewrite it if
session 99's E2E shows no rise in main-session lane calls against a run without it, or once a client enforces lanes.
