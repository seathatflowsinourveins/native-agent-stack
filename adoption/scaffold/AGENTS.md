# Agent instructions

<!-- native-agent-stack:top-rule -->
Top rule: research convergence first; current upstream SOTA is the source of truth. The installed client is also a source of truth; never self-write without a SOTA source. The ecosystem compounds: each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one.
Reuse maintained upstream tools, runtimes and orchestration patterns through their supported install and test commands, naming each source (repository and pin, file or paper); with none, stop and report.
Check capability claims in order: installed client (commands, --help, settings), upstream changelog for that version (gh api), upstream source at that tag, official docs. Absence claims need the first two, else say "not found in X, Y".
Worker, docs-agent and cross-family answers are leads; relay claims only with upstream citations.
Process large output outside the model.
When a claim proves wrong, record the correction and its verification path that turn.

<!-- native-agent-stack:repository-expectations -->
## Repository expectations

<!-- Replace each <placeholder> with this repository's own facts, and keep only what an agent cannot derive from the tree. -->
- Checks: run `<test command>` before committing; a change is done when it passes.
- Pull requests: fill in every section of `.github/pull_request_template.md`. The `sota-sources` check fails a description without a non-empty `## SOTA sources` section naming the repository, pin and file, or the published reference, behind each change.
- Scope: <what this repository owns, and what it leaves to other repositories>.
- Skills: skills only this repository needs go in `.agents/skills/`; skills every repository uses come from the host profile, never as copies here.
