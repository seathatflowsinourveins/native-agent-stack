# Workers (`workers`)

Client 2.1.295, checked 2026-10-09. Index: [slots.md](slots.md).

## subagent-definitions

**Status:** default (scoped). **Default:** File-based subagent definitions at project scope (`.claude/agents`), installed to `~/.claude/agents` by the profile installer

- **Route:** Each role carries its `tools` allowlist, model and effort; under `-p` or the Agent SDK a named spawn stays a subagent, while an interactive named spawn can become a teammate
- **Alternatives, ranked:** 1. `--agents` JSON per session; 2. Ad-hoc stages with per-call model and effort
- **Rejected:** Plugin-packaged copies of our definitions; VoltAgent/awesome-claude-code-subagents as a source; `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`
- **Evidence:** sub-agents.md frontmatter and priority; subagents-teams-O2, O3, O15
- **Notes:** Four host copies differ from adoption/agents/claude and four host-only definitions exist (G6b). Portability: the user-scope copies run in other projects, where 4 are stale and 4 of 11 bodies point at native-agent-stack-only paths; the north star needs repository-neutral bodies before relying on them.
- **Overturn when:** A release changes definition scope or priority, or a measured role-quality gap.

## agent-teams

**Status:** default (scoped). **Default:** Native agent teams, used only where workers must message each other

- **Route:** Teammates spawn only in interactive sessions; `-p` and SDK runs keep named subagents as subagents
- **Alternatives, ranked:** 1. Plain subagents; 2. Cross-session messaging between sessions you run; 3. Workflows
- **Rejected:** oh-my-claudecode's tmux team workers; Sonnet teammates without a paired run
- **Evidence:** agent-teams.md; subagents-teams-O15
- **Notes:** The host enables teams globally while the repository scopes them narrowly; whether that matches is the owner's call. No measurement of teams on our tasks exists. Verified: the switch sits in host user settings, so named subagents become teammates in every interactive session of every project, and teammates start in the lead's permission mode (bypass here).
- **Supersedes:** R50 effort clause
- **Overturn when:** A paired run shows teams lose quality or cost more for the same work, or the feature leaves experimental status with changed semantics.

## background-workflows

**Status:** default (scoped). **Default:** Dynamic Workflows (Workflow tool; saved workflows in `.claude/workflows` or `~/.claude/workflows`)

- **Route:** Runs resume from their journal after a pause or a usage limit (observed 2026-10-09); background sessions under the native supervisor for long single tasks
- **Alternatives, ranked:** 1. `claude --bg` sessions; 2. Background subagents; 3. `claude -p` from a script
- **Rejected:** A second background daemon
- **Evidence:** workflows.md resume and limits; background-workflows-O8, O9, O10
- **Notes:** Saved workflows are not yet at a native discovery location, and the adopt step names an agents/ directory that does not exist. Verified: a `-p` launch of a saved Workflow needs a launch-scoped `--allowedTools 'Workflow(<name>)'`; on WSL2 background carry-over relies on the on-demand supervisor.
- **Supersedes:** R52 Ultracode clause
- **Overturn when:** A release changes Workflow resume or limits, or a measured failure mode on our runs.

## orchestration-frameworks

**Status:** default. **Default:** Native composition without a framework layer: subagent definitions, Workflows, agent teams, background sessions and cross-session messaging

- **Route:** Choose by who coordinates, whether workers talk and whether files overlap (agents.md); recipes from a framework enter only as skill content through native extension points
- **Alternatives, ranked:** 1. `/batch` (bundled; one large change across worktree-isolated subagents); 2. OrchestratorInc/agent-orchestrator in its bounded role for sessions it launches (2026-10-08 decision)
- **Rejected:** EveryInc/compound-engineering-plugin as a layer; SuperClaude-Org/SuperClaude_Framework; Yeachan-Heo/oh-my-claudecode; Chachamaru127/claude-code-harness
- **Evidence:** agents.md how to choose; workflows.md; L2 framework ranking (compound-engineering first on its own quality, all seven overlap native)
- **Notes:** Adjudicated: native composition stands; the refuter upheld it. No framework shows a measured gain on our tasks. Scope: Claude-side composition; Codex lanes compose through hcom (2026-10-06 decision). G5 holds two rows for agent-orchestrator (OrchestratorInc and its former name, one repository id) to reconcile.
- **Overturn when:** A paired same-task run shows a framework ahead of native composition on quality at equal or lower cost.

## planning-persistence

**Status:** default. **Default:** Repository-resident task state per Anthropic's multi-context-window guidance (a JSON status file, free-text progress notes and git commits, read at session start), with native plan mode for the plan

- **Route:** One recipe paragraph names the files; set `plansDirectory` at project scope to a path inside the repository (unset, plans go to ~/.claude/plans and are not repository-resident), or copy the approved plan into the state files
- **Alternatives, ranked:** 1. Native Task tools with `CLAUDE_CODE_TASK_LIST_ID`; 2. Native plan mode with `plansDirectory`; 3. OthmanAdi/planning-with-files; 4. gastownhall/beads
- **Rejected:** Storybloq/storybloq; claude-code-harness's full plan-work-review cycle; A standing `CLAUDE_CODE_ENABLE_TODO_TOOLS=1`; github/spec-kit for session state
- **Evidence:** platform prompting guide, 'Workflows across multiple context windows'; Anthropic engineering, 'Effective harnesses for long-running agents'
- **Notes:** Adjudicated: the Anthropic convention stands; the refuter upheld it.
- **Overturn when:** Paired same-task runs on long multi-session tasks, with forced restarts and compaction, show an alternative ahead on quality.

## loops-completion

**Status:** default. **Default:** Native Stop hook as the completion gate, with `/goal` and the self-paced `/loop` for fitting conditions

- **Route:** Command type for deterministic checks; prompt type with an explicit model for judged conditions; `stop_hook_active` and the continuation cap bound the loop
- **Alternatives, ranked:** 1. `/goal`; 2. cobusgreyling/loop-engineering patterns as reference
- **Rejected:** Ralph-style bash loops; ralph-loop plugin as the default
- **Evidence:** hooks.md Stop event; goal.md
- **Notes:** No completion gate is configured today; the KC-19 trial was designed and never run. Verified: a command gate fails open by default (a gate that cannot start or times out lets Claude stop); `onFailure: "block"` (2.1.295) is not yet in hooks.md, so pick and test the failure mode; for agent-team members use TeammateIdle; for Workflow children put a Stop hook in the agent's frontmatter (runs as SubagentStop).
- **Supersedes:** Completion-loops topic (native composition now converged)
- **Overturn when:** A paired run shows a loop pattern catching more real defects at equal cost, or a release changes Stop semantics.
