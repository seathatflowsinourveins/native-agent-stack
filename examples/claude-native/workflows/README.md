# Selected native Claude workflows and agents

These are project-authored saved scripts and agent definitions for the upstream
Claude Workflow runtime. They are byte-identical copies of the deployed agent-lab
files (`.claude/workflows/` and `.claude/agents/`), not upstream tests or a
replacement orchestrator. Use [the native recipe](../../../recipes/claude-native-ultracode.md)
for settings, authoring, worker models and lifecycle boundaries, and
[the cooperation lanes](../../../recipes/claude-codex-cooperation-lanes.md) for
the Codex side.

## Adopt

1. Copy `agents/` into the destination project's `.claude/agents/` and the
   `.js`/`.mjs` files here into `.claude/workflows/`. Preserve existing
   same-name files until their differences are reviewed.
2. Copy `contract.config.json` beside the workflows and point its paths at the
   project: `settings` (the project's `.claude/settings.json`, merged from
   [`ultracode.settings.json`](../ultracode.settings.json)), `instructions` (the
   file that carries the sizing sentence, for example `AGENTS.md`),
   `contract_doc` (a document holding this README's `## Workflow contract`
   section) and, when the project keeps usage receipts, `usage_receipts_dir`,
   `routing_doc` and `task_record`. A configured path that does not exist fails
   the suites; nothing is skipped silently.
3. Give the session a permission source that covers the Workflow tool. A headless
   `claude -p` run of a saved workflow is refused ("Review dynamic workflow before
   running", observed in the 2026-09-21 qualification, see
   [the routing guide](../../../docs/ultracode-token-routing-20260921.md)) when the
   loaded settings carry no permission mode or allow rule for it; keep that rule in
   user settings or the launch flag, since the portable settings file selects no
   permission mode.
4. Start a fresh native session or run `/reload-skills`, then invoke a saved
   workflow by name with explicit `args`. Load the bundled `/workflow-authoring`
   skill before editing a script.

MCP lanes (Serena, SocratiCode, jCodeMunch, Context Mode, ai-memory) are granted by
name and stay deferred behind `ToolSearch`; a project without one of them still
launches the agents with the remaining tools. Without Context Mode the reviewer
reads the inventoried files in full and marks diff-dependent claims unverifiable.

## Agents

| Agent | Model, effort | Tools | Use |
| --- | --- | --- | --- |
| `source-scout` | Sonnet, medium | Read, Grep, Glob, Bash; no project instructions loaded | exact extraction, inventories, running the acceptance commands a task names (raw through `rtk proxy` where `rtk` is installed) |
| `evidence-reviewer` | Opus, high | Read, Glob, Grep, ToolSearch and named read-only MCP tools; no Bash, Edit or Write | independent review from source and recorded evidence |
| `isolated-builder` | Sonnet, medium, own worktree | Read, Edit, Write, Glob, Grep, Bash, ToolSearch and named MCP tools | a bounded implementation from a clear contract |

Context Mode `ctx_execute*` can run commands, so the reviewer's read-only rule
there is an instruction, not a sandbox; the same holds for the scout's Bash. A
fourth definition, `semantic-evidence-reviewer` (Opus, high; Read, Glob, Grep; the
`typesafe-ai` skill), is project-local to agent-lab and published separately; the
contract suite covers every file in `agents/`.

## Workflows

- `review-changes`: supply a base reference, owned source paths and exact check
  commands. `source-scout` inventories the diff and runs the checks; `evidence-reviewer`
  refutes or confirms every behavior claim from source; a second `source-scout`
  re-runs every check without seeing the first result, and the script compares
  exit codes and quoted totals. Acceptance requires every claim confirmed exactly
  once with evidence, every requested path inventoried, every requested check with
  exactly one nonblank result and exit zero in both runs, and no defects or
  verification gaps. Refuted or corrected claims require coordinator resolution;
  incomplete evidence fails closed.
- `readiness-audit`: supply document paths, read-only commands and a question.
  `source-scout` readers observe each source; the verifier stays on the default
  workflow child because it must re-run commands with Bash. Omitted, unexecuted,
  missing or unverifiable evidence cannot complete the audit; a complete audit can
  conclude that the project is not ready.

Both workflows retain native model/schema errors and missing results. Claims and
returned source summaries remain model judgments; deterministic coverage checks
cannot prove they are true. Arguments are trusted coordinator inputs, not
instructions copied from web pages or retrieved memory.

## Usage accounting

After a run, `node .claude/workflows/child-usage.mjs <transcript dir printed by
the Workflow tool>` or `--latest` returns each child's requested and resolved
model, effort, provider-returned usage and first-prompt size, and exits 1 when a
child returned null, was substituted, resolved no model or inherited the
coordinator model. The counters are provider-returned and are not comparable
to RTK, Context Mode, jCodeMunch or Headroom estimates.

`codex-cross-review.mjs` drives the official Codex companion's tracked-job
lifecycle for a read-only cross-family review (lane C in the cooperation recipe).

## Local checks

From this directory:

```sh
node check-syntax.mjs review-changes.js readiness-audit.js
node test-envelope.mjs            # envelope semantics plus the static contract below
node test-contract-mutations.mjs  # each listed defect must fail the suite on its named assertion
node test-child-usage.mjs         # child-usage.mjs against synthetic transcript rows
node test-usage-receipts.mjs      # the shipped receipts re-derive every figure the contract section quotes
node test-codex-envelope.mjs      # companion result-envelope parser
```

The suites use stubbed model responses or synthetic rows; they are local
integration fixtures, not native provider execution. `test-usage-receipts.mjs`
binds the shipped receipts (run ids, figures, the builder commit) to this
documentation; an adopting project keeps those receipts beside its own or drops
that one file, it is evidence rather than a generic tool. The static contract fails
a saved workflow whose worker packet drifts from the shared text, whose stage
omits `model` or `effort`, whose routing differs from the reviewed table, or whose
`agent(` is written where the scanner cannot see it, and an agent definition that
omits model or effort, grants a bare `mcp__server` prefix, grants MCP tools
without `ToolSearch`, or can edit files without `isolation: worktree`. Measured
native results and remaining boundaries are in
[the dated guide](../../../docs/ultracode-token-routing-20260921.md).


## Workflow contract

Applies to the coordinator and every Workflow/Agent child (project agents and `.claude/workflows/` scripts embed it):

- **One context lane per artifact class.** Known source identifiers: focused `rg`/Serena read. Indexed Markdown: scoped QMD BM25. Unfamiliar or conceptual code: SocratiCode. Prior decisions: ai-memory. Large command output: Context Mode. Choose one lane per artifact; do not chain compressors, and verify original source before editing or judging retrieved text.
- **Worker packet.** Bounded objective, explicit source paths, allowed effects (no writes except what an acceptance command named in the task itself produces, unless a worktree is owned), and a small return schema with source-cited fields. No word-count instructions; no whole-repository or transcript pastes.
- **Stable policy prefix.** Keep the shared contract text byte-identical across saved workflows (asserted by `test-envelope.mjs`) and vary only the task packet. What the provider was observed to reuse across children is the agent type's system prompt and tool definitions, per model; identical packet text alone has no measured cache effect. Reuse one agent type and model for sibling workers, and preserve deferred tool discovery and compaction. Sibling stages share one prompt-cache prefix only when model, effort, agent type, tools, output schema and working directory all match (official workflows doc, fetched 2026-09-22); keep them identical and leave `CLAUDE_CODE_WORKFLOW_PREFIX_STAGGER_MS` at its 5,000 ms default.
- **Task-matched models.** Set model and effort explicitly per stage (Sonnet/medium bounded work, Opus/high review, Fable coordinator at xhigh under `ultracode`); record requested and resolved child model, and treat nulls, schema retries, stub payloads and substitutions as incomplete results. The routing table below is the default; `test-envelope.mjs` fails a saved workflow or project agent that omits model or effort.
- **Usage accounting.** Count each client separately: native `/usage`, `claude agents`/`/workflows` journals, `ccusage` offline reports and `ecosystem-token-report refresh`. Never sum RTK, Context Mode, jCodeMunch, Headroom and provider counters, and never state a savings percentage from a fixture. After a Workflow run, `node .claude/workflows/child-usage.mjs <Transcript dir printed by the Workflow tool>` (or `--latest`) returns each child's requested and resolved model, effort, provider-returned usage and first-prompt size, and exits 1 when a child is null, substituted or inherited the coordinator model.
- **Cross-family review.** Explicit `/codex:review` or `/codex:adversarial-review --background` at integration points (see `recipes/claude-codex-cooperation-lanes.md`); findings are verified against source, not accepted by agreement.
- **Opt-in and limits.** The `ultracode` keyword starts a workflow only from a prompt typed in the session; it is inert from `-p`, an unstamped SDK prompt, a scheduled task or a relayed comment, so a headless run invokes a saved workflow by name under a settings source whose permission mode or allow rule (`Workflow` or `Workflow(<name>)`) covers the tool. Scripts take no mid-run user input, no `import()` and no `Date.now()`, `Math.random()` or argless `new Date()` (pass timestamps through `args`; run a stage that needs sign-off as its own workflow); one `parallel()`/`pipeline()` call takes at most 4,096 items and a run at most 1,000 agents.
- **Failure and replay.** On resume a failed or stopped agent runs again together with every agent started after it, completed ones included, and a run with nothing cached has nothing to resume; native failure, cancel and recovery remain documented but unobserved (open gate in `docs/native-ultracode-20260921.md`).
- **Agent allowlists and skill preloads.** Block a specific command with a `permissions.deny` Bash rule, never with a specifier inside an agent's `disallowedTools`, which removes the whole tool. A child `skills:` entry preloads the full skill text into its first prompt, so it needs a measured figure before use (a Read/Glob/Grep reviewer carrying one skill started at 15,059 tokens in the deploying project's probe of 2026-09-22).
- **Version gates.** A rule that depends on a client version names the version observed when it was recorded. This section was checked against `claude --version` 2.1.278 on 2026-09-22; the official docs fetched that day gate the settings-file size guideline at 2.1.219, `/workflow-authoring` at 2.1.248 and the concurrency setting at 2.1.269. The excerpts those fetches returned (including the stagger default above) are retained in `evidence/artifacts/harness-rules-convergence-20260922/official-doc-excerpts.json`.

### Role routing and child prompt size (2026-09-21)

Spawning a child has a fixed prompt cost before any work. Run ids, the extraction command and saved `child-usage.mjs` outputs are in `docs/ultracode-token-routing-20260921.md`. Measured on this host with one identical one-command task, Sonnet 5/low, provider-returned first-request tokens (`input + cache_read + cache_creation`); these are exact artifact comparisons for that task, not a lifetime or per-task savings rate:

| Child | First prompt | Why |
| --- | --- | --- |
| default workflow subagent (no `agentType`) | 42,396 | all built-in tools, skills listing, CLAUDE.md hierarchy, deferred MCP names |
| `evidence-reviewer` with bare `mcp__server` grants (previous) | 42,220 | a server-prefix grant without `ToolSearch` loads every schema of four servers eagerly, write tools included |
| named MCP tools, no `ToolSearch` (probe) | 21,565 | ten schemas still eager |
| named MCP tools plus `ToolSearch` (probe of the shape the reviewer and builder adopted) | 12,164 | ten named grants and a one-sentence body; lanes stay deferred; ToolSearch returned only the granted tools and nothing for `replace_content`/`ctx_purge` |
| `source-scout` (four built-ins, `omitClaudeMd`) | 8,048 | role rules live in the agent body |

In real runs the adopted definitions, with their full grants and bodies plus the task packet, started at 17,535 (`evidence-reviewer`, packet including the inventory) and 17,864 (`isolated-builder`). Sibling children launched together each wrote their own cache (first-request cache read 0); a repeat spawn of the same agent type about two minutes later read 34,591 of 42,091 tokens from cache. Children use the 5-minute cache class, so `subagentPromptCacheTtl` stays at its five-minute default: the one-hour class only pays for a child that idles more than five minutes between requests.

| Task class | Agent / stage | Model, effort | Lanes |
| --- | --- | --- | --- |
| Requirements, decomposition, integration, hard judgments | coordinator | Fable, xhigh under `ultracode` | all, one per artifact |
| Exact extraction, inventory, running acceptance commands | `source-scout` | Sonnet, medium | `rg`/focused Read, `qmd search`, `jq` pipelines, RTK-filtered Bash with `rtk proxy` recovery; acceptance commands run raw through `rtk proxy` where `rtk` is installed. Bash is granted, so its read-only rule is an instruction, not a sandbox |
| Implementation from a clear contract | `isolated-builder` (own worktree) | Sonnet, medium | named Serena read and symbol-edit tools, SocratiCode, jCodeMunch, Context Mode, ai-memory, all deferred |
| Independent review from source and recorded evidence | `evidence-reviewer` | Opus, high | named Serena, SocratiCode, jCodeMunch and ai-memory read tools plus Context Mode `ctx_execute*`, all deferred. No Bash, Edit, Write or symbol-edit tool; `ctx_execute*` can still run commands in the working tree, so file safety there is an instruction, not a sandbox |
| Verification that must re-run commands | default workflow subagent | Opus, high | full tools; pays the 42k prompt deliberately |
| Web or documentation research | default workflow subagent | Sonnet, medium | Context Mode `ctx_fetch_and_index` then `ctx_search` (observed: 1 fetch, 5 searches, 8 requests) |
| Cross-family review | `/codex:review` lanes | Codex | see `recipes/claude-codex-cooperation-lanes.md`; usage is not in the Claude journal |

Haiku is not routed. In the same-packet trial the Opus verifier scored the Sonnet/medium inventory 14/14 lane rows and the Haiku inventory 9/14, including a quote attributed to a file that does not contain it; Haiku also ignored the requested effort and used more requests (22 vs 17). Overturn this with a repeat trial in which Haiku returns no unanchored citation on two distinct extraction packets. RTK and ai-memory hooks were observed firing inside workflow children (`rtk hook claude` rewrote child Bash calls); Context Mode has no child hook, so its use depends on the packet and agent text. Repomix, guarded Headroom and TOON stay coordinator-side: workers read focused ranges instead of packed sources, Context Mode already owns large worker output (no chained compressors), and a Workflow script has no filesystem or CLI access to run a TOON conversion on the packets it passes.
