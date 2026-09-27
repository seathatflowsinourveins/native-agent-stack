# Decision: carry token lanes through SubagentStart (2026-09-27)

**Decided by:** unit `token-lanes-subagent-start`, branch
`claude/token-lanes-subagent-carrier-20260927`, implementing the user's
SubagentStart build task for Ultracode workflow children.
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
