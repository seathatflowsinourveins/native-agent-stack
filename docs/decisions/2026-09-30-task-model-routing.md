# Decision: task-to-model routing across Claude Code and Codex, and where each route is enforced (2026-09-30)

**Decided by:** unit A4 of the 2026-09-30 SOTA-defaults wave (coordinator session `native-agent-stack-c5`), on branch
`claude/sota-defaults-a4-20260930` based on `origin/main@e45328d3`. The record gathers the routing rules of the earlier
records and the workflows README into one table. It changes no route: no agent definition, settings file, template,
workflow or lane script is edited.

## Context

Task-to-model routing is decided in several places and enforced in more:

- The workflows README's workflow contract, role table, Sonnet 5.5 section and role-routing table
  (`examples/claude-native/workflows/README.md:835`, `:844-858`, `:860-876`, `:894-909`).
- The model-currency record's decision table (`docs/decisions/2026-09-27-model-currency.md:39-54`), with the Codex
  judgment, mechanical and interactive rows at `:46-48` and the note that no code pins GPT-6 Sol at medium (`:284`). Its
  2026-09-28 addendum moves the wrapper row to Sonnet 5.5 through the `sonnet` alias (`:334-338`).
- The Sonnet 5.5 dispatch record (`docs/decisions/2026-09-29-sonnet-5-5-dispatch.md:18-37`) and the max-default effort
  record (`docs/decisions/2026-09-29-max-default-effort.md:33`).
- Two open pull requests that are not on main. #423 resolves every OmniRoute feature of the gateway on port 20128 (its
  record, line 5) and notes a framework-only instance (line 137), which the landscape-sweep README stages on port 20129
  (`tools/sota-convergence/landscape-sweep/README.md:155`). #508's token-stack record keeps role dispatch as a run-shape
  lever that Gate A per-row results decide (lines 90 and 93).

Several routes bind nothing in a file: a Sonnet 5.5 stage override, a design or synthesis stage, and GPT-6 Sol at medium
are instructions to whoever dispatches. GPT-6.1 Sol is absent from main: the only `gpt-6.1` string is the model-name
fixture `my_gw/gpt-6.1` in `tests/test_landscape_sweep_harness.py:754`.

## Alternatives

- **A gateway-side router now.** OmniRoute can choose the model per request through its task-aware router (#423
  feature D11), its combos and auto-combos (D04) and its model aliases (D06). Not now. #423's verdict holds D11 because
  "Keyword matching can silently replace explicit lane identity with an auto intent, including cheap/fast routes"
  (verdict lines 1437-1441 at the PR head), and gives D04 singleton combos and D06 lane aliases the state
  `enable_after_ab` (lines 1120 and 1227), with an A/B design that keeps "Astra/max as the judgment control" (line 1123).
  That A/B has not run. The gateway also served no `claude-opus-5-5` on 2026-09-27
  (`docs/decisions/2026-09-27-model-currency.md:45`), so it could not carry the Claude rows.
- **A per-repository router skill.** A skill or instruction block that assigns models by task would be a third copy of
  the rules, next to the role table and the agent definitions, and it would still bind nothing: a model binds only
  where a stage or a definition names it, and otherwise falls back to `CLAUDE_CODE_SUBAGENT_MODEL`, then to the lead's
  model (`examples/claude-native/workflows/README.md:873`). No measured result favours one.
- **Status quo, recorded in one table (chosen).** Keep each assignment where it is enforced today, and list them
  together with their enforcement points, so that a change to any one of them has one place to restate.

## Decision

No automatic router exists. Each route below is a static assignment: an agent definition, a workflow stage, a settings
key, a Codex profile or a lane script names the model and the effort, or the row is an instruction to whoever
dispatches. No repository configuration picks a model by task; even the opt-in Codex OmniRoute profile names its model
and effort (`adoption/templates/codex.omniroute.config.toml:23,25`). Claude Code's own content-based fallback, which
re-runs a flagged request on an older model, is switched off in this repository's settings and in the user-settings
template: `.claude/settings.json:7` says `"switchModelsOnFlag": false`, `.claude/settings.json:11` says
`"CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK": "1"`, and the template sets both
(`adoption/templates/claude.settings.template.json:26,318`). The model-currency addendum leaves their coverage of every
flagged route unverified, and availability fallback chains are a separate mechanism that these keys do not touch
(`docs/decisions/2026-09-27-model-currency.md:341-361`). OmniRoute's D04 singleton combos, D06 lane aliases and
task-aware router (D11) stay off until the promptfoo A/B of wave unit D3 reports. That unit label belongs to this
wave; it is not #423's feature D03 (prompt-cache affinity).

The Claude rows assume Claude Code 2.1.284 or later, where the `sonnet` alias resolves to Sonnet 5.5 and `opus` to
Opus 5.5 (`examples/claude-native/workflows/README.md:862`); the Codex rows are for codex-cli 0.157.1. In the "Enforced
today" column, "`path:line` says `value`" quotes that file.

| Task class | Client | Model | Effort | Enforced today | Rule source |
| --- | --- | --- | --- | --- | --- |
| Coordinator: requirements, decomposition, integration | Claude Code | Opus 5.5 (`opus[1m]`); a Sonnet 5.5 coordinator is supported and hands each judgment to an `opus` stage | max in a terminal session started through the ecosystem launcher; otherwise the saved xhigh | **Client settings and launcher**: `adoption/templates/claude.settings.template.json:124` says `"model": "opus[1m]"`; `adoption/templates/claude.settings.template.json:300` says `"effortLevel": "xhigh"`; `.claude/settings.json:5` says `"effortLevel": "xhigh"`; the launcher adds its flag only when nothing chose an effort (`adoption/bootstrap-linux.sh:395`), and `adoption/bootstrap-linux.sh:408` says `--effort max` | `examples/claude-native/workflows/README.md:896`; `docs/decisions/2026-09-29-sonnet-5-5-dispatch.md:31`; `docs/decisions/2026-09-29-max-default-effort.md:33` |
| Escalation advisor (`/advisor`) for hard calls | Claude Code | Fable 5.1 (`fable`) | no template key | **Client settings**: `adoption/templates/claude.settings.template.json:125` says `"advisorModel": "fable"` | `docs/decisions/2026-09-27-model-currency.md:42`; `examples/claude-native/workflows/README.md:896` |
| Design and architecture | Claude Code | Opus 5.5 (`opus`) | max | **Instruction only** for the coordinator and ad-hoc stages; a stage that names no model and has no definition falls back to **`CLAUDE_CODE_SUBAGENT_MODEL`**, and `adoption/templates/claude.settings.template.json:27` says `"CLAUDE_CODE_SUBAGENT_MODEL": "opus"` | `examples/claude-native/workflows/README.md:835`; `examples/claude-native/workflows/README.md:869`; `docs/decisions/2026-09-29-sonnet-5-5-dispatch.md:26` |
| Research, first-pass breadth | Claude Code | Sonnet 5.5 (`sonnet`) as a per-stage override | max | **Instruction only**: a stage's own `model: 'sonnet'`, with every claim checked by a later Opus stage | `examples/claude-native/workflows/README.md:867`; `docs/decisions/2026-09-29-sonnet-5-5-dispatch.md:30` |
| Research, judgment: web, documentation, repository and catalog research | Claude Code | Opus 5.5 (`opus`) | max | **Agent frontmatter**: `.claude/agents/stack-researcher.md:5-6` says `model: opus` and `effort: max` | `examples/claude-native/workflows/README.md:851`; `examples/claude-native/workflows/README.md:898` |
| Build with a written contract's tests: migration, refactor or scaffold in an owned checkout | Claude Code | Sonnet 5.5 (`sonnet`) as a per-stage override of `isolated-builder`, followed by an Opus review | max | **Instruction only** for the override; without it the definition runs Opus, and `.claude/agents/isolated-builder.md:5-6` says `model: opus` and `effort: max` | `examples/claude-native/workflows/README.md:866`; `docs/decisions/2026-09-29-sonnet-5-5-dispatch.md:29` |
| Build without a written contract's tests | Claude Code | Opus 5.5 (`opus`) | max | **Agent frontmatter**: `.claude/agents/isolated-builder.md:5-6` says `model: opus` and `effort: max` | `examples/claude-native/workflows/README.md:852`; `examples/claude-native/workflows/README.md:869` |
| Review from source and recorded evidence | Claude Code | Opus 5.5 (`opus`) | max | **Agent frontmatter**: `.claude/agents/evidence-reviewer.md:5-6` says `model: opus` and `effort: max` | `examples/claude-native/workflows/README.md:853`; `examples/claude-native/workflows/README.md:900` |
| Security review | Claude Code | Opus 5.5 (`opus`) | max | **Agent frontmatter**: `.claude/agents/security-reviewer.md:5-6` says `model: opus` and `effort: max` | `examples/claude-native/workflows/README.md:854`; `examples/claude-native/workflows/README.md:901` |
| Verification that re-runs commands | Claude Code | Opus 5.5 (`opus`) | max | **Agent frontmatter**: `.claude/agents/stack-verifier.md:5-6` says `model: opus` and `effort: max` | `examples/claude-native/workflows/README.md:855`; `examples/claude-native/workflows/README.md:905` |
| Adjudication of one anonymous two-return disagreement | Claude Code | Opus 5.5 (`opus`) | max | **Agent frontmatter**: `.claude/agents/blind-adjudicator.md:5-6` says `model: opus` and `effort: max` | `examples/claude-native/workflows/README.md:856`; `examples/claude-native/workflows/README.md:904` |
| Synthesis | Claude Code | Opus 5.5 (`opus`) | max | **Instruction only** for the coordinator and ad-hoc stages, with the same **`CLAUDE_CODE_SUBAGENT_MODEL`** fallback as design; a saved workflow binds each stage as a **workflow stage**, which CI checks: `.github/workflows/validate.yml:53` says `node test-envelope.mjs`; `examples/claude-native/workflows/test-envelope.mjs:365` says `sets an explicit model and effort on every reached agent() call` | `examples/claude-native/workflows/README.md:835`; `docs/decisions/2026-09-29-sonnet-5-5-dispatch.md:26` |
| Exact extraction, inventories and the acceptance commands a task names (scout) | Claude Code | Sonnet 5.5 (`sonnet`) | max | **Agent frontmatter**: `.claude/agents/source-scout.md:5-6` says `model: sonnet` and `effort: max`; saved workflows bind the same stage by stage, and `examples/claude-native/workflows/review-changes.js:59` says `agentType: 'source-scout', model: 'sonnet', effort: 'max'` | `examples/claude-native/workflows/README.md:850`; `examples/claude-native/workflows/README.md:897`; `docs/decisions/2026-09-29-sonnet-5-5-dispatch.md:28` |
| Command wrappers: shell, test, build and lint runs, and Codex-wrapper stages | Claude Code | Sonnet 5.5 (`sonnet`) | max | **Workflow stage** for the landscape sweep's Codex-wrapper stages: `tools/sota-convergence/landscape-sweep/sweep.js:110` says `model: 'sonnet', effort: 'max'`; `tools/sota-convergence/landscape-sweep/sweep.js:122` says `model: 'sonnet', effort: 'max'`; **instruction only** for ad-hoc shell, test, build and lint stages | `examples/claude-native/workflows/README.md:864`; `docs/decisions/2026-09-29-sonnet-5-5-dispatch.md:27`; `docs/decisions/2026-09-27-model-currency.md:43`; `docs/decisions/2026-09-27-model-currency.md:334-338` |
| Cross-family review of a diff or PR head | Codex CLI 0.157.1 | GPT-6 Astra (`gpt-6-astra`) | max | **Instruction only**: in the recipe's read-only command, `recipes/claude-codex-cooperation-lanes.md:43` says `-m gpt-6-astra -c model_reasoning_effort="max"`; the cross-review wrapper pins neither and passes the flags through only when given, where `examples/claude-native/workflows/codex-cross-review.mjs:92` says `for (const flag of ['--model', '--effort'])` | `examples/claude-native/workflows/README.md:838`; `examples/claude-native/workflows/README.md:907`; `docs/decisions/2026-09-29-sonnet-5-5-dispatch.md:33` |
| GPT-6 judgment workers: research, discovery, refutation, review and verdicts through `-p stack-worker` | Codex CLI 0.157.1 | GPT-6 Astra (`gpt-6-astra`) | max | **Codex config**: `adoption/templates/codex.stack-worker.config.toml:12` says `model = "gpt-6-astra"`; `adoption/templates/codex.stack-worker.config.toml:17` says `model_reasoning_effort = "max"`; the Codex role carriers bind the same as **lane code**, and `tools/adoption/codex_roles.py:52-53` says `ROLE_MODEL = "gpt-6-astra"` and `ROLE_EFFORT = "max"` | `docs/decisions/2026-09-27-model-currency.md:46` |
| Sweep and layer-verdict votes, Claude side: discovery, refutation and critique | Claude Code | Opus 5.5 (`opus`) | max | **Agent frontmatter**: `.claude/agents/landscape-sweep-worker.md:4-5` says `model: opus` and `effort: max`; `.claude/agents/blind-lane-reviewer.md:5-6` says `model: opus` and `effort: max`; the sweep's stage aliases are **lane code**, and `tools/sota-convergence/landscape-sweep/convert.py:61` says `"discover": "opus", "refute-facts": "opus", "refute-fit": "opus", "critic": "opus"` | `examples/claude-native/workflows/README.md:903`; `tools/sota-convergence/landscape-sweep/sweep.js:6` |
| Sweep votes, GPT-6 side: discovery and fit refutation | Codex CLI 0.157.1 | GPT-6 Astra (`gpt-6-astra`) | max | **Lane code** on the Codex command line: `tools/sota-convergence/landscape-sweep/codex_job.py:94-95` says `DEFAULT_MODEL = "gpt-6-astra"` and `EFFORT = "max"`; `tools/sota-convergence/landscape-sweep/convert.py:62` says `GPT6_DEFAULT = {"model": "gpt-6-astra", "effort": "max"}` | `docs/decisions/2026-09-27-model-currency.md:46`; `tools/sota-convergence/landscape-sweep/sweep.js:6` |
| Mechanical, deterministically scored extraction (GPT-6) | Codex CLI 0.157.1 | GPT-6 Sol (`gpt-6-sol`) | medium | **Instruction only**: a preregistration binding of the #359 experiment (arm S1) that no other lane sets, and `docs/decisions/2026-09-27-model-currency.md:284` says `No code pin sets` | `docs/decisions/2026-09-27-model-currency.md:47` |
| Interactive Codex | Codex CLI 0.157.1 | GPT-6 Astra (`gpt-6-astra`) | ultra; lanes override it to max | **Codex config**: `adoption/templates/codex.config.template.toml:1-2` says `model = "gpt-6-astra"` and `model_reasoning_effort = "ultra"` | `docs/decisions/2026-09-27-model-currency.md:48` |
| None: not routed | Codex CLI | `gpt-6.1-sol` | n/a | pending unit D4 qualification (Codex >= 0.159.x pin) | none on main |

**Agent frontmatter** is the `model:` and `effort:` of a `.claude/agents/<name>.md` definition; a stage's own `model`
and `effort` override it. **Workflow stage** is an `agent()` call's own binding; in CI, `node test-envelope.mjs` checks
the stages of the saved workflows under `examples/claude-native/workflows/` and the agents they name.
**`CLAUDE_CODE_SUBAGENT_MODEL`** is the template's user-scope default for a stage that names no model and has no
definition, so it holds only on a host that applied the template. **Codex config** is a Codex profile or template key,
and **lane code** is a constant that a lane script passes to Codex or to a stage. **Instruction only** means no file
binds the choice: the coordinator makes it under the cited rule.

## Overturn condition

- **Unit D3's promptfoo A/B reports.** Where a D04 singleton combo or a D06 lane alias matches its lane's direct route
  on the checks of #423's A/B design (resolved model and effort; preserved instructions, tools and schema; account
  continuity; cached-input share; billed tokens, attempts and latency; verdict lines 1123 and 1230), adopt it for the
  lanes tested and restate their rows. D11 stays held until a result answers its hold reason.
- **A measured quality regression on any row.** For the Sonnet rows, the conditions in
  `docs/decisions/2026-09-29-sonnet-5-5-dispatch.md:171-180`; for GPT-6 Sol, a rerun of the #359 tiering with an arm
  outside its frozen 0.02 micro-F1 bound (`docs/decisions/2026-09-27-model-currency.md:47`); for any other row, a paired
  result on the same task class that puts the routed model below its alternative.
- **Unit D4 qualifies `gpt-6.1-sol`** on a Codex 0.159.x or later pin: add the row it earns, with its enforcement point.
- **An enforcement point changes** (an agent's frontmatter, a settings key, a Codex profile, a lane constant): restate
  its row in the same change.

## Sources

Records and files on main (`origin/main@e45328d3`):

- `examples/claude-native/workflows/README.md`: workflow contract `:827-842`, dispatch by role `:844-858`, Sonnet 5.5
  fan-out units `:860-876`, role routing `:878-909`.
- `docs/decisions/2026-09-27-model-currency.md`: decision table `:39-54`, unresolved `:278-299`, 2026-09-28 addendum
  `:310-373`.
- `docs/decisions/2026-09-29-sonnet-5-5-dispatch.md`: decision `:18-37`, alternatives `:156-169`, overturn `:171-180`.
- `docs/decisions/2026-09-29-max-default-effort.md`: decision `:33`.
- The enforcement points the table quotes: `.claude/agents/`, `.claude/settings.json`,
  `adoption/templates/claude.settings.template.json`, `adoption/templates/codex.config.template.toml`,
  `adoption/templates/codex.stack-worker.config.toml`, `adoption/templates/codex.omniroute.config.toml`,
  `adoption/bootstrap-linux.sh`, `tools/adoption/codex_roles.py`, `tools/sota-convergence/landscape-sweep/`,
  `examples/claude-native/workflows/`, `recipes/claude-codex-cooperation-lanes.md` and `.github/workflows/validate.yml`.
- promptfoo 0.123.1, the pinned evaluation harness for unit D3 (`manifests/stack.json:698`).

Open pull requests, not on main, cited at their head commits:

- #423, "OmniRoute feature resolution: all 55 gateway features resolved with GPT-6 cross-family refutation; qmd scope
  and embeddings evidence", head `e2e048053b151ac9c2ba269864cb4adf035058d3`:
  [record](https://github.com/seathatflowsinourveins/native-agent-stack/blob/e2e048053b151ac9c2ba269864cb4adf035058d3/docs/decisions/2026-09-27-omniroute-feature-resolution.md)
  lines 5, 54-58, 66 and 137, and
  [verdict](https://github.com/seathatflowsinourveins/native-agent-stack/blob/e2e048053b151ac9c2ba269864cb4adf035058d3/evidence/artifacts/omniroute-features-20260927/omniroute-feature-verdict.json)
  rows D04 (lines 1117-1125), D06 (1224-1230) and D11 (1434-1442).
- #508, "Token stack winner: one full stack chosen on recorded evidence, provisional until Gate A (decision record)",
  head `b7fcc2196c9ff5557f30486468f614fc0dc9d8b5`:
  [record](https://github.com/seathatflowsinourveins/native-agent-stack/blob/b7fcc2196c9ff5557f30486468f614fc0dc9d8b5/docs/decisions/2026-09-29-token-stack-winner.md)
  lines 90 and 93.

Anthropic, as the workflows README cites them (`:869`, `:872`, `:873`); each returned HTTP 200 on 2026-09-30:

- [Claude Sonnet 5.5 system card](https://www.anthropic.com/claude-sonnet-5-5-system-card), sections 6.2.2, 6.2.3 and
  6.3.1: Opus 5.5 ahead on the honesty and reckless-tool-use audits and the less self-preferring grader.
- [Optimizing for cost and intelligence](https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence):
  in Anthropic's measured orchestrator and worker configurations, a second model paid off only to cap the cost tail on
  routine work and for input larger than one context.
- [Sub-agents](https://code.claude.com/docs/en/sub-agents#run-every-subagent-on-one-model) and
  [environment variables](https://code.claude.com/docs/en/env-vars): a stage's model, then the definition's, then
  `CLAUDE_CODE_SUBAGENT_MODEL`, then the lead's.
