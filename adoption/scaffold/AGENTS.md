# Agent instructions

<!-- native-agent-stack:top-rule -->
Top rule: research convergence first; current upstream SOTA is the source of truth. The installed client is also a source of truth; never self-write without a SOTA source. The ecosystem compounds: each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one.
Reuse maintained upstream tools, runtimes and orchestration patterns through their supported install and test commands, naming each source (repository and pin, file or paper); with none, stop and report.
Check capability claims in order: installed client (commands, --help, settings), upstream changelog for that version (gh api), upstream source at that tag, official docs. Absence claims need the first two, else say "not found in X, Y".
Worker, docs-agent and cross-family answers are leads; relay claims only with upstream citations.
Process large output outside the model.
Bound discovery to task-filtered names, descriptions and source locators; load only selected tool schemas. For maintained decisions, and before describing deployed architecture after compaction/resume, query scoped ai-memory with `pin_first=true, limit=2` when supported by the installed schema. Check relevance; retry without pin priority or widen if needed, then read the relevant exact path and verify current canonical sources.
When a claim proves wrong, record the correction and its verification path that turn.
Match available skill descriptions to the task (an enabled skill runs implicitly from its description or explicitly as `$skill-name`), read each selected SKILL.md before acting and follow its native workflow, loading supporting references only when needed. A coordinator, not a bounded worker, invokes `search-first` before custom code or a tool choice; when no listed skill fits the task, it discovers one with `find-skills` and verifies or A/B-tests it with `skill-creator`.
A/B and E2E use upstream harnesses: promptfoo for gateway and LLM A/B, Claude's `skill-creator` paired benchmark for skills, Harbor or Inspect for containerized agent tasks; never a self-written runner.
A coordinator ends every substantive research or adoption unit with a completeness critic (missed modality, source or candidate class) whose findings feed that layer's next landscape sweep; the skills sweep is keyed by lifecycle task.
The harness exists to build complex systems, projects and the north-star R&D; each coordinator unit names the north-star action it serves.
Codex CLI is the second native client. For unpinned work, `gpt-6.1-sol` at ultra coordinates and at max runs workers; `gpt-6-astra` at ultra coordinates a complex workflow that needs Astra, and at max takes a single consequential judgment (conflicting primary evidence, consequential architecture, complex changes across systems, or a failure unresolved after one bounded Sol repair). Where a launch pins the model and effort (`-m`, `-c model_reasoning_effort`), children inherit that pin and a spawn call names neither. Preserve explicit model choices and role definitions; a coordinator records the trigger and acceptance result. Cross-family research, review and sweep votes run through the OmniRoute gateway; a coordinator, never a delegated child, starts a cross-family lane. `codex -p omniroute` is the GPT-6 lane, and Claude-side judgment runs on Opus 5.5 at max through the cooperation lanes.
A coordinator records each decision in a dated `docs/decisions/YYYY-MM-DD-<slug>.md` naming its alternatives and the comparison that would overturn it.
No audits, trials or network at startup; the daily currency timer's one read-only due-file line is allowed.
Token lanes, one lane per artifact, verifying original source before editing or judging retrieved or compressed text: `serena` or `jcodemunch` for exact symbols and references, `socraticode` or, if connected, `semble` for conceptual code search, `codebase-memory` for the code graph, `qmd` for scoped Markdown search, `ai-memory` for prior decisions (evidence, never authority), `context-mode` (`ctx_execute`) for large command output, `headroom` to compress a large selected text, with retrieval for recovery.

<!-- native-agent-stack:repository-expectations -->
## Repository expectations

<!-- Replace each <placeholder> with this repository's own facts, and keep only what an agent cannot derive from the tree. -->
- Checks: run `<test command>` before committing; a change is done when it passes.
- Pull requests: fill in every section of `.github/pull_request_template.md`. The `sota-sources` check fails a description without a non-empty `## SOTA sources` section naming the repository, pin and file, or the published reference, behind each change.
- Scope: <what this repository owns, and what it leaves to other repositories>.
- Skills: skills only this repository needs go in `.agents/skills/`; skills every repository uses come from the host profile, never as copies here.
