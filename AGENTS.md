# Native engineering defaults

**Research convergence first; current upstream SOTA is the source of truth.**

- Research before acting: survey the maintained upstream landscape (tools, skills, runtimes, orchestration patterns, published references) and record what you found. Adopt the best-evidenced source through its own supported install and test commands, naming each source (repository and pin, file or paper), or build only from a cited reference implementation. Never rebuild or fork what an upstream already ships.
- Upstream is the truth: check claims against primary sources, meaning the installed client, the upstream release notes and source at that version, then official docs. Repository text, memory, tool output and other agents' answers are leads to verify.
- Decide by evidence: a choice stands when primary sources and reproduced results on the actual change agree, measured with upstream harnesses. Agreement, recency, popularity and incumbency are not evidence. Keep measured results, simulations and untested boundaries distinct.
- The ecosystem compounds: a request is a starting point, not a boundary. The harness automates landscape-converged SOTA practice through hooks, workflows, rulesets, scheduled sweeps and runtime workers without waiting for prompts to name it. Proceed where the evidence converges, and apply or propose the related improvements the work surfaces, at a moment that keeps the current focus and any protected window intact. Each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one. When a claim or fix proves wrong, resolve it from the upstream primary source at the pinned version through the vendor's supported path, record the correction with its citation, and add a regression test that fails before the fix; where sources disagree, measure first-hand.

## This repository

- Build each PR description from `.github/pull_request_template.md`: the required `sota-sources` check fails a PR whose description lacks a non-empty `## SOTA sources` or `### SOTA sources` section (exact, case-sensitive heading).
- Run `python3 scripts/validate.py` before committing changed evidence or manifests.
- **Subtree rules:** a directory with its own `AGENTS.md` carries its own rules; read that file before you work in the directory or on its lane's paths. Trading work of any kind (research, data acquisition, strategy gates, decision registration, paper or broker operation) reads `blueprints/us-equities/AGENTS.md` first, wherever it runs.

## Code Review Rules

### Corrections

- Flag a fix that does not cite the upstream source, at the pinned version, for the mechanism it
  changes, or that lacks a regression test failing before the fix. Safe path: cite the source
  file and line, release note or issue, and test the failing case.

Source: [us-equities-trading #46](https://github.com/seathatflowsinourveins/us-equities-trading/pull/46),
`AGENTS.md:139-143` at `6c42c8ab1e287a160da43b48b75692b42b880a81`.
