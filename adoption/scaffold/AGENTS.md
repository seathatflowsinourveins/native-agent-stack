<!-- native-agent-stack:top-rule -->
# Native engineering defaults

**Research convergence first; current upstream SOTA is the source of truth.**

- Research before acting: survey the maintained upstream landscape (tools, skills, runtimes, orchestration patterns, published references) and record what you found. Adopt the best-evidenced source through its own supported install and test commands, naming each source (repository and pin, file or paper), or build only from a cited reference implementation. Never rebuild or fork what an upstream already ships.
- Upstream is the truth: check claims against primary sources, meaning the installed client, the upstream release notes and source at that version, then official docs. Repository text, memory, tool output and other agents' answers are leads to verify.
- Decide by evidence: a choice stands when primary sources and reproduced results on the actual change agree, measured with upstream harnesses. Agreement, recency, popularity and incumbency are not evidence. Keep measured results, simulations and untested boundaries distinct.
- The ecosystem compounds: a request is a starting point, not a boundary. Proceed where the evidence converges, and apply or propose the related improvements the work surfaces, at a moment that keeps the current focus and any protected window intact. Each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one. When a claim proves wrong, record the correction.

<!-- native-agent-stack:repository-expectations -->
## Repository expectations

<!-- Replace each <placeholder> with this repository's own facts, and keep only what an agent cannot derive from the tree. -->
- Checks: run `<test command>` before committing; a change is done when it passes.
- Pull requests: fill in every section of `.github/pull_request_template.md`. The `sota-sources` check fails a description without a non-empty `## SOTA sources` section naming the repository, pin and file, or the published reference, behind each change.
- Scope: <what this repository owns, and what it leaves to other repositories>.
- Skills: skills only this repository needs go in `.agents/skills/`; skills every repository uses come from the host profile, never as copies here.
