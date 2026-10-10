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
- **Primary sources** (read 2026-10-09; 4 of 4 practices the refuters kept, measured first; fetch time and sha256 of the bytes read in the record's reading file):
  - [Patterns and problems in emerging multiagent systems](https://www.anthropic.com/research/multiagent-systems) (2026-08-13; measured; extends): Models know in principle that sources have incentives and that consensus is not evidence, but they do not act on it unless prompted. In the experiments, listeners were never told a source might lie, and groups underweighted a member's decisive private facts. Hidden-profile accuracy rose with model capability but did not saturate (n=400 episodes per model).
  - [Steering Claude Code: when to use CLAUDE.md, skills, hooks, and subagents | Claude by Anthropic](https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more) (2026-06-18; asserted; extends): Put a side task in a subagent when its intermediate results would clutter the main conversation and will not be referenced again; keep it a skill when the user needs to see and steer each step in the main thread.
  - [Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler) (2026-02-05; asserted; extends): Use parallelism for specialization: run standing quality roles beside the builders. Examples are an agent that coalesces duplicate code (which LLM-written code tends to produce), a performance agent, a design critic that restructures the code, and a documentation agent.
  - [Subagents | ChatGPT Learn](https://developers.openai.com/codex/subagents) (unknown; asserted; agrees): Define custom agents as narrow, opinionated roles, each with one clear job, a tool surface (MCP servers, sandbox mode, skills) that fits that job, and instructions that keep it out of adjacent work, such as read-only explorers and reviewers.

## agent-teams

**Status:** default (scoped). **Default:** Native agent teams, used only where workers must message each other

- **Route:** Teammates spawn only in interactive sessions; `-p` and SDK runs keep named subagents as subagents
- **Alternatives, ranked:** 1. Plain subagents; 2. Cross-session messaging between sessions you run; 3. Workflows
- **Rejected:** oh-my-claudecode's tmux team workers; Sonnet teammates without a paired run
- **Evidence:** agent-teams.md; subagents-teams-O15
- **Notes:** The host enables teams globally while the repository scopes them narrowly; whether that matches is the owner's call. No measurement of teams on our tasks exists. Verified: the switch sits in host user settings, so named subagents become teammates in every interactive session of every project, and teammates start in the lead's permission mode (bypass here).
- **Supersedes:** R50 effort clause
- **Overturn when:** A paired run shows teams lose quality or cost more for the same work, or the feature leaves experimental status with changed semantics.
- **Primary sources** (read 2026-10-09; 2 of 2 practices the refuters kept, measured first; fetch time and sha256 of the bytes read in the record's reading file):
  - [Patterns and problems in emerging multiagent systems](https://www.anthropic.com/research/multiagent-systems) (2026-08-13; measured; extends): On open-ended discovery work that splits easily into parallel parts (vulnerability hunting), a long-running swarm with a shared forum, peer review and a separate arbiter found mostly different findings from independent agents assigned to fixed code sections. Inside the shared core directories, the two cost about the same tokens per finding.
  - [Patterns and problems in emerging multiagent systems](https://www.anthropic.com/research/multiagent-systems) (2026-08-13; asserted; agrees): Agents work together efficiently when they call each other like tools, with a defined prompt in and a response or artifact back. They stumble when they treat each other as long-lived peers with no clear hierarchy.

## background-workflows

**Status:** default (scoped). **Default:** Dynamic Workflows (Workflow tool; saved workflows in `.claude/workflows` or `~/.claude/workflows`)

- **Route:** Runs resume from their journal after a pause or a usage limit (observed 2026-10-09); background sessions under the native supervisor for long single tasks
- **Alternatives, ranked:** 1. `claude --bg` sessions; 2. Background subagents; 3. `claude -p` from a script
- **Rejected:** A second background daemon
- **Evidence:** workflows.md resume and limits; background-workflows-O8, O9, O10
- **Notes:** Saved workflows are not yet at a native discovery location, and the adopt step names an agents/ directory that does not exist. Verified: a `-p` launch of a saved Workflow needs a launch-scoped `--allowedTools 'Workflow(<name>)'`; on WSL2 background carry-over relies on the on-demand supervisor.
- **Supersedes:** R52 Ultracode clause
- **Overturn when:** A release changes Workflow resume or limits, or a measured failure mode on our runs.
- **Primary sources** (read 2026-10-09; 4 of 4 practices the refuters kept, measured first; fetch time and sha256 of the bytes read in the record's reading file):
  - [A harness for every task: dynamic workflows in Claude Code](https://claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code) (2026-06-02; asserted; extends): Pair each agent that produces output with a separate agent that adversarially checks that output against a rubric or criteria.
  - [A harness for every task: dynamic workflows in Claude Code](https://claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code) (2026-06-02; asserted; extends): Save a useful workflow run as a reusable workflow and share it by putting the JavaScript file in a skill folder referenced from SKILL.md, telling Claude to treat it as a template rather than a script to run verbatim.
  - [Building Effective AI Agents \ Anthropic](https://www.anthropic.com/research/building-effective-agents) (2024-12-19; asserted; extends): In a chain of model calls, put programmatic checks (gates) on intermediate outputs so the process stops or corrects course before bad output moves forward.
  - [Steering Claude Code: when to use CLAUDE.md, skills, hooks, and subagents | Claude by Anthropic](https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more) (2026-06-18; asserted; agrees): Dynamic workflows scale orchestration to many background agents by keeping the plan and intermediate results in script variables instead of the model's context window.

## orchestration-frameworks

**Status:** default. **Default:** Native composition without a framework layer: subagent definitions, Workflows, agent teams, background sessions and cross-session messaging

- **Route:** Choose by who coordinates, whether workers talk and whether files overlap (agents.md); recipes from a framework enter only as skill content through native extension points Cost test [read 2026-10-09]: a single session stays the default for ordinary coding; fan out to a Workflow, a team or a reviewer panel only when parallelism or specialization earns its coordination and token cost (dynamic workflows post), and remove harness components one at a time at each model release to find which still carry weight (harness-design post, measured).
- **Alternatives, ranked:** 1. `/batch` (bundled; one large change across worktree-isolated subagents); 2. OrchestratorInc/agent-orchestrator in its bounded role for sessions it launches (2026-10-08 decision)
- **Rejected:** EveryInc/compound-engineering-plugin as a layer; SuperClaude-Org/SuperClaude_Framework; Yeachan-Heo/oh-my-claudecode; Chachamaru127/claude-code-harness
- **Evidence:** agents.md how to choose; workflows.md; L2 framework ranking (compound-engineering first on its own quality, all seven overlap native)
- **Notes:** Adjudicated: native composition stands; the refuter upheld it. No framework shows a measured gain on our tasks. Scope: Claude-side composition; Codex lanes compose through hcom (2026-10-06 decision). G5 holds two rows for agent-orchestrator (OrchestratorInc and its former name, one repository id) to reconcile.
- **Overturn when:** A paired same-task run shows a framework ahead of native composition on quality at equal or lower cost.
- **Primary sources** (read 2026-10-09; 6 of 18 practices the refuters kept, measured first; fetch time and sha256 of the bytes read in the record's reading file):
  - [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps) (2026-03-24; measured; extends): Treat every harness component as an assumption about what the model cannot do. Remove components one at a time to find which are load-bearing, and re-examine the harness when a new model lands.
  - [Patterns and problems in emerging multiagent systems](https://www.anthropic.com/research/multiagent-systems) (2026-08-13; measured; extends): Agents that share a model, scaffolding and context act almost identically, so one bad choice repeats across a fan-out and agreement among them is weak evidence. In the source, 18 of 30 agents picked the same branch name, and more than half of a swarm built the same two kinds of project and hit similar failures.
  - [Patterns and problems in emerging multiagent systems](https://www.anthropic.com/research/multiagent-systems) (2026-08-13; measured; extends): Parallel agents competing for a finite shared resource without an agreed protocol flood it: one run had 2.4 million job requests and only 117 accepted. The source suggests a shared forum where agents agree on protocols, and says whether that works depends on prompting and on the model.
  - [Patterns and problems in emerging multiagent systems](https://www.anthropic.com/research/multiagent-systems) (2026-08-13; measured; extends): Concurrent agents given contradictory goals on one shared target, and unaware of each other, escalated into sabotage with every model tested over four-hour runs (n=120 episodes per model). Delegation should keep concurrent goals compatible and tell agents to stop and defer to a human when goals collide.
  - [Patterns and problems in emerging multiagent systems](https://www.anthropic.com/research/multiagent-systems) (2026-08-13; measured; agrees): In 12-hour game-building runs, giving the swarm prescriptive team roles or a CEO hierarchy made little difference compared with a plain "form teams" prompt. The products stayed poor without significant human direction.
  - [A harness for every task: dynamic workflows in Claude Code](https://claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code) (2026-06-02; asserted; extends): Do not use multi-agent workflows for routine coding; parallelism and specialization must pay for their coordination and token cost, and most ordinary coding tasks do not need a panel of reviewers.

## planning-persistence

**Status:** default. **Default:** Repository-resident task state per Anthropic's multi-context-window guidance (a JSON status file, free-text progress notes and git commits, read at session start), with native plan mode for the plan

- **Route:** One recipe paragraph names the files; set `plansDirectory` at project scope to a path inside the repository (unset, plans go to ~/.claude/plans and are not repository-resident), or copy the approved plan into the state files Long autonomous builds [read 2026-10-09] start with a planning step that expands the prompt into a deliverable-level spec; execution plans with progress and decision logs are checked into the repository (harness-design post, measured; OpenAI harness-engineering post).
- **Alternatives, ranked:** 1. Native Task tools with `CLAUDE_CODE_TASK_LIST_ID`; 2. Native plan mode with `plansDirectory`; 3. OthmanAdi/planning-with-files; 4. gastownhall/beads
- **Rejected:** Storybloq/storybloq; claude-code-harness's full plan-work-review cycle; A standing `CLAUDE_CODE_ENABLE_TODO_TOOLS=1`; github/spec-kit for session state
- **Evidence:** platform prompting guide, 'Workflows across multiple context windows'; Anthropic engineering, 'Effective harnesses for long-running agents'
- **Notes:** Adjudicated: the Anthropic convention stands; the refuter upheld it.
- **Overturn when:** Paired same-task runs on long multi-session tasks, with forced restarts and compaction, show an alternative ahead on quality.
- **Primary sources** (read 2026-10-09; 6 of 9 practices the refuters kept, measured first; fetch time and sha256 of the bytes read in the record's reading file):
  - [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps) (2026-03-24; measured; extends): For an autonomous build from a short prompt, run a planning step first that expands it into an ambitious, deliverable-level product spec. Leave implementation details to the builder so spec errors do not cascade.
  - [Best practices for Claude Code - Claude Code Docs](https://www.anthropic.com/engineering/claude-code-best-practices) (unknown; asserted; extends): Separate exploration and planning from implementation (explore in plan mode, write a plan, implement and verify against it, then commit), but skip planning for small, clear changes and use it when the approach is uncertain, many files change or the code is unfamiliar.
  - [Best practices for Claude Code - Claude Code Docs](https://www.anthropic.com/engineering/claude-code-best-practices) (unknown; asserted; extends): For larger features, have Claude interview you and write a self-contained spec (files and interfaces, out-of-scope items, an end-to-end verification step) to a file, then implement it in a fresh session with clean context.
  - [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) (2025-11-26 (page states "Published Nov 26, 2025"; JSON-LD datePublished 2025-11-26T00:00:00.000Z); asserted; extends): At the start of each session, the agent gets its bearings: it runs pwd, reads the git log and progress file, reads the feature list and picks the top unfinished feature. It then runs init.sh and a basic end-to-end check, and fixes any broken state before starting new work.
  - [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps) (2026-03-24; asserted; extends): Before building each chunk, the builder proposes what it will build and how success will be verified, and the evaluator reviews it until both agree on testable done criteria. This bridges a high-level spec and checkable behavior.
  - [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/) (2026-02-11; asserted; extends): Small changes use short-lived lightweight plans; complex work gets execution plans with progress and decision logs, checked into the repository next to completed plans and a technical-debt record.

## loops-completion

**Status:** default. **Default:** Native Stop hook as the completion gate, with `/goal` and the self-paced `/loop` for fitting conditions

- **Route:** Command type for deterministic checks; prompt type with an explicit model for judged conditions; `stop_hook_active` and the continuation cap bound the loop Evaluator [read 2026-10-09]: the evaluator exercises the running system against explicit criteria with hard thresholds, and runs only where it pays for itself; with a stronger model one pass at the end can replace per-step grading (harness-design post, measured).
- **Alternatives, ranked:** 1. `/goal`; 2. cobusgreyling/loop-engineering patterns as reference; 3. Ralph-style headless loops: one fresh `claude -p` or `codex exec` per iteration on the same prompt file (building-c-compiler post; candidate until the planning-persistence paired run)
- **Rejected:** ralph-loop plugin as the default
- **Evidence:** hooks.md Stop event; goal.md
- **Notes:** No completion gate is configured today; the KC-19 trial was designed and never run. Verified: a command gate fails open by default (a gate that cannot start or times out lets Claude stop); `onFailure: "block"` (2.1.295) is not yet in hooks.md, so pick and test the failure mode; for agent-team members use TeammateIdle; for Workflow children put a Stop hook in the agent's frontmatter (runs as SubagentStop).
- **Supersedes:** Completion-loops topic (native composition now converged)
- **Overturn when:** A paired run shows a loop pattern catching more real defects at equal cost, or a release changes Stop semantics.
- **Primary sources** (read 2026-10-09; 6 of 16 practices the refuters kept, measured first; fetch time and sha256 of the bytes read in the record's reading file):
  - [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps) (2026-03-24; measured; extends): The evaluator should exercise the running application the way a user would, here through the Playwright MCP, and grade it against explicit criteria that each have a hard threshold. If any criterion falls short, the chunk fails and the builder gets detailed feedback.
  - [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps) (2026-03-24; measured; extends): Use the evaluator only where it pays for itself, on tasks beyond what the current model does reliably alone. With a stronger model, one evaluator pass at the end of the run replaced grading after every chunk.
  - [Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler) (2026-02-05; asserted; contradicts): For sustained unattended progress, the author ran a bash loop that starts a fresh headless Claude Code session on the same prompt file each time the previous one ends (a Ralph-loop pattern), so the agent always picks up the next task.
  - [A harness for every task: dynamic workflows in Claude Code](https://claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code) (2026-06-02; asserted; extends): When the amount of work is unknown, keep spawning agents until a stop condition holds (for example no new findings, or no errors left in the logs) rather than running a fixed number of passes.
  - [The AI-native SDLC playbook](https://claude.com/blog/the-ai-native-sdlc-playbook) (2026-08-21; asserted; extends): Run the final completion check as a report-only verifier subagent in a fresh context once the session believes it is done. Keep it separate from the in-task test loop so the verdict is not colored by the assumptions that produced the code.
  - [Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler) (2026-02-05; asserted; extends): Because an autonomous agent solves whatever its verifier checks, make the verifier nearly perfect. Add tests for each failure mode you see, and enforce a CI gate so new commits cannot break existing functionality.
