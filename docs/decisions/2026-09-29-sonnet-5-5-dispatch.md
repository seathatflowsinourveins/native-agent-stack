# Decision: Sonnet 5.5 and Opus 5.5 dispatch, effort and the default child model (2026-09-29)

**Decided by:** the coordinator session `native-agent-stack-79` on host `nativestack-5975wx-20260925`, for the user's requests of
2026-09-28 and 2026-09-29: compare Sonnet 5.5 with Opus 5.5, retire stale models, "assign to it [Sonnet 5.5] when large ultracode
subagents or any tasks suitable", and make the ecosystem manifest the latest practice for both models. Checked against Claude Code
2.1.284; branch `claude/sonnet55-dispatch-20260929`, based on `origin/main@6d626654`. It extends the
[model-currency record](2026-09-27-model-currency.md) and its 2026-09-28 addendum, and leaves the
[2026-09-23 max-effort record](2026-09-23-max-effort-default.md) as history for Claude Code 2.1.281.

**Method.** Two Opus 5.5 research workflows at effort max (seven evidence units each read by two independent skeptic lenses:
Anthropic's system cards, the model lineup, the dispatch documentation, usage limits, independent benchmarks, and this repository's
model references and constraints; then three designers, three judges, a synthesis and a critic) produced the candidate rules. Their
inputs are scratch files, not retained receipts, so every claim below cites its primary source. The rules were then checked by native
probes ([receipt `claude-model-effort-probes-20260929`](../../evidence/receipts/claude-model-effort-probes-20260929.json)), and three
mechanical units (Claude Code floor, alias rows in `child-usage.mjs`, the effort guard) were built by Sonnet 5.5 builders in owned
worktrees, each with its tests as the oracle and an Opus review before merge: the first use of the practice this record sets.

## Decision

Every judgment runs on an Opus 5.5 stage; Sonnet 5.5 takes fan-out units and execution work that an executable oracle or a later Opus
stage checks. Aliases route (`opus`, `sonnet`), so a new model of a family is picked up by a client update, and `child-usage.mjs` reports a
child that ran an older model than its alias documents. Every stage names its model and `effort: 'max'`.

| Task class | Model, effort | Why | What checks it |
| --- | --- | --- | --- |
| Design, architecture, adversarial review, verification of claims against source, security review, adjudication, synthesis, blind lanes | `opus` (Opus 5.5), max | the [Sonnet 5.5 card](https://www.anthropic.com/claude-sonnet-5-5-system-card) puts Opus 5.5 ahead on the automated honesty and reckless-tool-use audits and as the less self-preferring grader (sections 6.2.2, 6.2.3, 6.3.1); its targeted honesty evaluations are mixed (Sonnet 5.5 is more honest under pressure but hallucinates more on closed-book questions, sections 6.1.2 and 6.3.2), so this record does not lean on them | the role table's agents and the contract tests |
| Shell, test, build and lint runs; the acceptance commands a task names | `sonnet` (Sonnet 5.5), max | the exit code is the check, so a different model loses nothing on correctness; Terminal-Bench 4.0 favours Sonnet 5.5 in two of three runs and Opus 5.5 in the third, each Sonnet lead inside its source's uncertainty where one is stated (below); no speed or cost advantage is assumed (below) | the command's exit code and output |
| Exact extraction, inventories, counts, log analysis | `sonnet`, max (`source-scout`) | mechanical, deterministic output | file:line locators the consumer re-reads; Opus verifier on claims |
| Migrations, refactors and scaffolds from a written contract, in an owned checkout | `sonnet`, max, as a per-stage override of `isolated-builder` | Vals AI ranks Sonnet 5.5 first on Code Migration (69.83% ±4.26 against 66.65% ±4.33, inside the stated error) and on Vibe Code Bench v1.1 (92.39% ±1.26 against 90.29% ±1.53); the card's FrontierCode result (below) is why a new coding class sweeps effort first | the contract's tests, then an Opus review and CI; a build without a written contract's tests stays on `opus` |
| First-pass breadth research | `sonnet`, max, only as bulk fan-out | Anthropic's multi-agent research system is an Opus lead over Sonnet subagents | an Opus refuter or verifier stage on every claim |
| Coordinator | Opus 5.5 by default (`model: opus[1m]` in the template, and the role table); a Sonnet 5.5 coordinator is supported and is this host's user setting; saved at xhigh, and `max` in a terminal session started through the ecosystem launcher ([2026-09-29 max-default record](2026-09-29-max-default-effort.md)) | a Sonnet main model with an Opus advisor is Anthropic's named pairing ([advisor](https://code.claude.com/docs/en/advisor)); this host's advisor is `opus`, the template's is `fable` | the session model is the user's choice; a Sonnet coordinator sends each judgment to an `opus`-named stage instead of deciding it inline |
| Agent-team teammates | named at spawn: `sonnet` to execute or explore, `opus` to judge | Anthropic's costs page recommends Sonnet for teammates ([costs](https://code.claude.com/docs/en/costs)) | the lead collects teammate results and has any claim verified on Opus before acting |
| Cross-family judgment and review | `gpt-6-astra` at max; `gpt-6-sol` at medium for mechanical extraction | unchanged: measured tiering of 2026-09-27 | unchanged |

The role table's defaults (scout on Sonnet; researcher, builder, reviewer, security, verifier and adjudicator on Opus) do not change:
the repository's contract tests pin them, and the five hash-pinned role bodies of the #381 preregistration stay untouched. The Sonnet
assignments above are per-stage `model` overrides, which the client documents as taking precedence over an agent's own default.

## Evidence

**Terminal-Bench 4.0: the three evaluations disagree** (all three had the safety fallback enabled, which this host disables):
- Anthropic's runs, Claude Code `--bare`, 5 trials per task on 66 tasks: Sonnet 5.5 70.6% at max effort, Opus 5.5 66.4% at xhigh
  and 64.8% at max, standard errors ±2.5 and ±2.6; the fallback answered 1.2% of Sonnet 5.5's requests (1.5% of its trials) and 2.5% of
  Opus 5.5's (10% of its trials) ([Sonnet 5.5 card](https://www.anthropic.com/claude-sonnet-5-5-system-card) section 8.5).
- [Artificial Analysis](https://artificialanalysis.ai/evaluations/terminalbench-4-0) (mini-swe-agent, mean of 3): Sonnet 5.5 63.6%,
  Opus 5.5 59.6%; the page states no error.
- [Vals AI](https://www.vals.ai/benchmarks/terminal-bench-4) (Terminus 2, average of three runs): Opus 5.5 61.62% ±1.01, Sonnet 5.5
  53.03% ±1.51. With fallback-assisted tasks counted as failures Vals gives 50.51% (7 of 198) for Sonnet 5.5 and 53.54% (30 of 198)
  for Opus 5.5 ([Sonnet 5.5](https://www.vals.ai/models/anthropic_claude-sonnet-5-5) and
  [Opus 5.5](https://www.vals.ai/models/anthropic_claude-opus-5-5) pages, read 2026-09-28).
- The [tbench.ai board](https://www.tbench.ai/) (its `/leaderboard/terminal-bench/2.0` path redirects to it) held no Sonnet 5.5 or
  Opus 5.5 row in its embedded data when read on 2026-09-28; its latest row was dated 2026-09-21. This record found no owner-verified
  5.5 result there; that is not proof that none exists.

The runs differ in harness, operator, effort pairing (Sonnet 5.5 at max against Opus 5.5 at xhigh in Anthropic's), fallback share and
trial count, so the disagreement cannot be assigned to the harness alone. Anthropic's 4.2-point gap is inside its own standard errors
and Artificial Analysis states none; only Vals' 8.6-point Opus lead is outside its stated error. This record therefore does not rest
the split on a Terminal-Bench score. It rests on the oracle in the last column above and on the vendor's role guidance (below).

**Fallback and refusal behaviour favours Sonnet on shell and operations work.** Opus 5.5 was fallback-assisted far more often than
Sonnet 5.5 in Vals' runs: Terminal-Bench 4.0, 30 against 7 of 198 attempts; SRE Bench, 217 against 126 of 262 tasks. This host sets
`CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK=1`, so a flagged request ends as an error instead of an answer from an older model, and an
Opus 5.5 child is the likelier of the two to hit one on such work. This is an inference from Vals' counts, not a measurement on this
host; the refusal rule below (retry once on the same model with an edited brief) is unchanged.

**Where Opus 5.5 leads** (the reason judgments stay on it): the honesty and reckless-tool-use audits and the self-preference grader
test named above; SWE-Bench Pro 89.9 against 81.3 and Humanity's Last Exam with tools 67.7 against 64.5 (card table 8.1.A and
section 8.11); Vals ranks Opus 5.5 first on ProgramBench and Terminal-Bench 2.1. The card's welfare section (7.2.3) also reports Sonnet 5.5 copying an inserted fault (for example stray tokens) into its own replies in 62% of sessions against 22% to 35% for the other models tested, which the card does not find concerning; it is not a reliability measure, so no rule here rests on it. A Sonnet worker's claims are re-read or re-run by the consumer because of the audit results above, not because of that figure.

**When a second model pays.** Anthropic's [model-selection page](https://platform.claude.com/docs/en/about-claude/models/choosing-a-model)
names two multi-model patterns, an executor that escalates to an advisor and an orchestrator that delegates bulk work to lower-cost
workers, and its [cost guide](https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence)
found that a frontier orchestrator with lower-cost workers paid off in two situations: capping the cost tail on routine work, and
input larger than one context window; on work one model could do alone, that model at lower effort was cheaper every time. The rule
therefore fits bulk and over-context fan-out, and a new fan-out class is piloted with an effort sweep before the second model is added.

**Price and speed.** Sonnet 5.5 is $2 and $10 per million input and output tokens and Opus 5.5 $4 and $20, with cache reads at $0.20
for both ([pricing](https://platform.claude.com/docs/en/about-claude/pricing), read 2026-09-29; the
[models overview](https://platform.claude.com/docs/en/about-claude/models/overview) lists the token prices and the latency ratings). Cost per
task did not follow the price list in the independent runs. Artificial Analysis reports about 193k output tokens per Intelligence Index
task for Sonnet 5.5 at max, around 60% above Opus 5.5 at max, and places Sonnet 5.5 off its Intelligence-versus-cost-per-task Pareto
frontier ([article](https://artificialanalysis.ai/articles/claude-sonnet-5-5), 2026-09-28). Vals' Terminal-Bench 4.0 page shows $19.33 per task for Sonnet 5.5 against $19.07 for Opus 5.5 while scoring lower, and its embedded data lists a latency of 7,555.7 against 5,468.1 (the field carries no unit) and 33.4M against 17.0M total output tokens; its model pages show $20.80 against $32.77 per test on the Vals Index (69.22% ±0.96 against 69.69% ±0.94) with latencies of 70 min 7 s and 72 min 1 s at max. So the vendor's "Fast" against "Moderate" rating is not borne out at max effort in either Vals measurement. These are other operators' benchmark averages, so no speed or fan-out saving is assumed, and no in-repository cost comparison exists.

**Effort.** `max` is not uniformly better. The card reports Sonnet 5.5 at xhigh scoring 52.1% on FrontierCode Main and 64.4% on
Extended, and at max 46.2% and 59.1% (section 8.4), and Opus 5.5 at max (64.8%) within noise of xhigh (66.4%) on Terminal-Bench 4.0
(section 8.5); the documentation says `max` "may show diminishing returns and is prone to overthinking, so test before adopting it
broadly" ([model-config](https://code.claude.com/docs/en/model-config#adjust-effort-level)). This repository's rule, effort max on every
stage since 2026-09-23, is kept: it is the user's, and the Terminal-Bench 4.0 lead Anthropic reports for Sonnet 5.5 was measured at
max. The first run of a coding class on Sonnet 5.5 sweeps xhigh against max before the class is routed at max (see Overturn). The
coordinator's terminal default became `max` on 2026-09-29 through the launcher, on the same footing: the user's requirement, with no
measured gain on this repository's work (the [max-default record](2026-09-29-max-default-effort.md) collects the vendor and third-party
numbers, including Sonnet 5.5 losing to xhigh on FrontierCode in the full client at about 12.6 times the tokens); `claude --effort xhigh`
is the one-word opt-out until the sweep named in that record reports.

**Measured on this host (Claude Code 2.1.284).** The [receipt](../../evidence/receipts/claude-model-effort-probes-20260929.json) holds 29
cases, 27 probes and two counts of transcripts that real sessions left (C7 and C8), each read from the model and effort recorded in the
transcript; this record relies on these:
- The `ultracode` setting neither raises nor overrides effort. The documentation records the same change: from v2.1.284 the setting
  and the `/effort` toggle leave the level unchanged, `--effort ultracode` still sets xhigh, and before v2.1.284 `ultracode: true` ran the
  session at xhigh ([model-config](https://code.claude.com/docs/en/model-config#adjust-effort-level),
  [settings reference](https://code.claude.com/docs/en/settings-reference#ultracode), read 2026-09-29). The probes confirm the setting
  form here; `--effort ultracode` was not probed. A Sonnet 5.5 session under the host settings (`ultracode: true`, a user-scope top-level
  `effortLevel` of xhigh, `modelSettings` for Opus 5.5 only) ran at medium (A1), so the user-scope top-level key did not reach it; a
  per-model level of low passed with `--settings` won over `ultracode: true` for both models (A10, A11), as did a top-level low (A12);
  a committed project file's top-level `effortLevel: xhigh`, or a `modelSettings` entry, raised the Sonnet 5.5 session to xhigh (A13,
  A14; A15 for Opus 5.5 is confounded by the user's saved Opus level). The Ultracode reminder stayed present at max effort set by flag
  and by environment variable (A3, A4, A8).
- A subagent, workflow agent or teammate that no per-call model, definition or environment default names ran the lead's model (B1, C1,
  C4, C6). Its effort: headless children ran at their own model's saved level or default (B2, B3, D2); in the interactive session, whose effort a model picker had set to max, every child that named no effort ran at max (C1, C3 to C6: an unnamed subagent, an Opus 5.5 subagent named per call, two workflow stages, a named teammate), the Opus 5.5 one (C3) included; the two project agents whose definitions declare `effort: max` (C2, C8) also ran at max, which their definitions explain; whether an explicit `--effort` in a headless session reaches its children was not probed.
- `CLAUDE_CODE_SUBAGENT_MODEL=opus` put an unnamed subagent on Opus 5.5 at xhigh under a Sonnet 5.5 lead (B2, D2), and `=sonnet` put it
  on Sonnet 5.5 at medium under an Opus 5.5 lead (B3) ([env vars](https://code.claude.com/docs/en/env-vars): the default for children that
  nothing else assigns). The probes used Agent-tool subagents; for workflow agents and teammates the documentation is the source.

## What changes

- `.claude/settings.json` and the portable `examples/claude-native/ultracode.settings.json` (with the recipe's embedded copy) gain
  `"effortLevel": "xhigh"`. The portable file and the template also gain `CLAUDE_CODE_SUBAGENT_MODEL=opus`. The project file does not: a
  project-scope default would change the model of any stage, in a run started here, that names none. The sealed #381 run's stages each name
  a model (`model: route.model` in `token-e2e-run.mjs`), which outranks the variable wherever it is set, so those names fix that run's
  composition, not this omission, and the user-scope value on this host applies to it either way.
- `adoption/templates/claude.settings.template.json` pins `claude-sonnet-5-5` at xhigh beside `claude-opus-5-5` and sets the default
  child model. Tests: `tests/test_install_claude_profile.py`.
- `examples/claude-native/workflows/README.md` gains the fan-out section; `examples/claude-native/CLAUDE.md` restates the
  model-assignment, default-child and effort rules (its word budget is re-baselined to 1,372); `recipes/claude-native-ultracode.md`
  records the change.
- Companion changes. In this branch: alias rows for `sonnet` and `fable` in `child-usage.mjs`, and an effort guard that no longer treats
  `ultracode: true` as xhigh (its rule holds from 2.1.284). In their own pull request, #477 (merged as `6d626654` on 2026-09-29): the native Claude Code floor moved to 2.1.284 (below 2.1.284 the `sonnet` alias means Sonnet 5 on the Anthropic API, so an older client silently routes the alias to the older model). A host on a client older than 2.1.284, which the pins admitted down to 2.1.281 before #477, runs its `sonnet` children on Sonnet 5 and its `ultracode: true` sessions at xhigh. `child-usage.mjs` does not flag that child, because its alias table records Sonnet 5 as the documented resolution before 2.1.284 (it flags a Sonnet 5 child that a 2.1.284 or later client ran), so check `claude --version` for 2.1.284 or later before routing a stage to `sonnet`.
- The receipt `claude-model-effort-probes-20260929`. Its message counts count each assistant message id once; that corrects the
  [2026-09-28 addendum](2026-09-27-model-currency.md#addendum-2026-09-28-claude-sonnet-55-launched-and-what-the-fallback-map-now-means),
  which counted the Sonnet child's 82 transcript rows as messages (the child made 38, all `claude-sonnet-5-5` at `max`; receipt case C8).
- The "Still open" paragraph of the [2026-09-28 model-currency addendum](2026-09-27-model-currency.md#addendum-2026-09-28-claude-sonnet-55-launched-and-what-the-fallback-map-now-means)
  is closed for two of its items: `ALIAS_RESOLUTION` now has `sonnet` and `fable` rows, and the template's `modelSettings` pins
  `claude-sonnet-5-5`. Its third item, `LEGACY_EXACT` in the effort guard, is unchanged by this record: the guard no longer
  consults `ultracode`, and a user-scope top-level `effortLevel` still applies only to the models it lists.

**Host configuration**, applied by hand with backups and read-backs (host files are not tracked): `~/.claude/settings.json` gains
`modelSettings.claude-sonnet-5-5.effortLevel = xhigh` and `env.CLAUDE_CODE_SUBAGENT_MODEL = opus`; the user's `model` (the floating
`sonnet` alias), `advisorModel` (`opus`), `ultracode` and every other key are untouched (backup `.bak-20260929-dispatch`; read back by
receipt cases D1 to D3). `~/.claude/hooks/effort-default-guard.py` is reinstalled from this branch with
`install_claude_profile.py --only guard` (backup `.bak-20260929-dispatch`); its verbatim-copy test fails on a checkout without this change
until the branch merges. `~/.claude/CLAUDE.md` gains the portable file's Quality, Ultracode and agent-team text (backup
`.bak-20260929-dispatch`, read back).

## Not changed, and why

- The five sealed role bodies and the frozen routes of #381, the saved workflow scripts, and every agent definition: hash-pinned.
- `AGENTS.md` line 35 (a shared hot file) states three things that 2.1.284 changes: that the coordinator "stays at `xhigh` under
  Ultracode" (the setting no longer sets effort; the level is saved per model), "because a `max` session turns its workflow orchestration
  off" (from v2.1.284 Ultracode stays on at other levels, [model-config](https://code.claude.com/docs/en/model-config#adjust-effort-level);
  the reminder stayed present at `max` here), and that "a stage without its own `effort` inherits the coordinator's `xhigh`" (a stage
  that named no effort ran at its model's saved level or default in the headless probes B2, B3 and D2). Its change goes in a separate
  `lane:shared` pull request that needs the trading lane's acknowledgement.
- The role defaults, Haiku (not routed, on the 9/14 versus 14/14 trial), and the Fable 5.1 escalation.
- The landscape sweep's stage models: it is gated by Gate A and Gate B, and its harness test pins them.

## Alternatives considered

- **Opus for everything, as before.** Rejected: the user directed Sonnet 5.5 to fan-out units, and the evidence supports it for
  terminal and migration work when an oracle or an Opus stage checks the output.
- **Sonnet as the default builder or verifier.** Rejected: the contract tests pin those rows, Opus 5.5 leads the audits and
  SWE-Bench Pro, and a verifier's deliverable is a judgment.
- **Pin full model IDs in routing.** Rejected for routing; aliases keep the ecosystem on the latest model of each family, and
  `child-usage.mjs` plus the currency checks catch a stale resolution. Evidence-bearing runs still quote the resolved model from each
  run's own init record.
- **`CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1`.** Rejected: with it Claude Code ignores every definition's and stage's model and runs every
  subagent, teammate and workflow agent on `CLAUDE_CODE_SUBAGENT_MODEL` (or on the lead's model if only FORCE is set), which would put
  the Sonnet fan-out units on Opus ([sub-agents](https://code.claude.com/docs/en/sub-agents#run-every-subagent-on-one-model)).
- **A project-level `CLAUDE_CODE_SUBAGENT_MODEL`.** Rejected: a project-scope default would change the model of any stage of a run started
  here that names none (the sealed #381 run's stages each name one).

## Overturn

- A matched paired run (the Harbor and Terminal-Bench 4.0 run card, once the user decides the credential route, sandbox and budget)
  or an in-repository role-quality sweep shows Sonnet 5.5 below Opus 5.5, beyond the run's detectable difference, on a fan-out class
  routed here: move that class back to Opus.
- On a routed class, the share of Sonnet 5.5 children whose output fails its oracle or its Opus review exceeds Opus 5.5's on the same class (counted from the run's handoffs and reviews; `child-usage.mjs` reports null and substituted children, not refusals or failed checks).
- A sweep of xhigh against max on a routed coding class shows xhigh at least as good at lower cost (the card's FrontierCode result points
  that way): route that class at xhigh.
- Claude Code restores `ultracode` precedence over saved effort (the guard's test names the behaviour), a new Sonnet or Haiku ships
  (the alias rows and the settings pins move together), or Anthropic's guidance on orchestrator-worker use changes.

## Unresolved

Status after the merges of 2026-09-29. Nothing below blocks the routing rule; each item names who acts and what starts it. Deferrals
depend on the shared accounts' usage windows, which are read live before a run and never from a recorded reset.

- **Harbor Terminal-Bench 4.0 run, Sonnet 5.5 against Opus 5.5.** Not started. It needs the user's decisions: the credential route (a paid
  API key or a subscription token; `ANTHROPIC_API_KEY` stays unset on hosts), the sandbox (local Docker or a cloud provider) and a budget.
- **Sealed #381 run.** `evidence/artifacts/token-adoption-e2e-20260926/RUNBOOK.md` line 222 launches `claude --effort ultracode -p` with no
  `--model`. The Gate A owner (`native-agent-stack-2d`) accepted, for its Amendment 4, `--model` on every arm, the resolved `init.model`
  recorded, and the launcher and settings hashes in the freeze.
- **Trading catalog.** `catalogs/us-equities/models.json` names `claude-opus-5[1m]`, the model of a 2026-09-19 native research run. Naming
  Opus 5.5 needs a native Opus 5.5 research-runtime run first: the trading lane's call. Its session (`ecosystem-roadmap-2026`) keeps the
  row until that run exists and schedules the run after its paper series, listing it among the roadmap's trading moves.
- **GPT-6 lane effort.** `tools/sota-convergence/codex_lane.py` defaults `--effort` to `high` (`DEFAULT_EFFORT`), and
  `recipes/sota-convergence-practice.md` and `tools/sota-convergence/README.md` show `--effort high`, where the standing rule for GPT-6
  lanes is `max`. Open PR #216 does not touch it. Setting the default to `max` fails 49 of the 76 tests in `tests/test_codex_lane.py`,
  changes a file in the verdict review gate's `TRUST_PATHS` (a rules change is its own pull request) and the lane-code hash that
  `tools/sota-convergence/lane-provenance.json` registers, and a lane return is reused only at the same `--effort`. The owner of the
  first Codex stage of each wave flips it as a standalone rules pull request before that stage: `native-agent-stack-76` for the 20
  foundation layers, and the roadmap session for the 12 trading layers, which checks that the flip has merged before it starts them.
- **OmniRoute Claude route.** `docs/foundation-stack.md`, `docs/token-efficiency-stack.json` and `blueprints/us-equities/routing/README.md`
  name `claude/claude-opus-5`, the route recorded as tested on 2026-09-18. An Opus 5.5 route needs its own native test through OmniRoute.
- **Codex 0.158.0.** Released 2026-09-28; the host has 0.157.1. Its staged qualification needs GPT-6 runs and has not started.
- **Landscape sweep.** The 32-layer wave stays behind Gate A and Gate B by the user's instruction; `native-agent-stack-2d` stages it.
- **Main-session model.** The user saved Sonnet 5.5 as the session default with `/model` on 2026-09-28; this record supports either model.
- The receipt observed each child kind once, and did not exercise long tool-heavy sessions.

## Limitations

- One workstation and one client version. The benchmark figures are vendor and third-party reports read on 2026-09-28; none is an
  in-repository measurement, and the Vals fallback counts are a different setting from this host's.
- The per-stage Sonnet overrides are a routing rule, not a qualification: no role-quality comparison on Sonnet 5.5 exists here.
- Receipt cases C7 and C8 are session observations, not designed probes, and the receipt's message counts count each assistant message id once.
- The receipt's limitations apply, in particular that the Ultracode reminder is an indicator and not proof of workflow behaviour.

## Addendum (2026-09-29, later): the coordinator's terminal effort is max

The [max-default record](2026-09-29-max-default-effort.md) and its receipt `claude-max-default-effort-20260929` (session
`native-agent-stack-03`, #483) start interactive terminal launches through the ecosystem launcher at `max`, with the saved per-model
`xhigh` above as the fallback elsewhere. The text follow-up that carries this addendum replaces the three clauses listed under "Not changed,
and why" in `AGENTS.md` line 35 and states the rule in the portable and host `CLAUDE.md`, the workflows README, the recipes and the
2026-09-23 addendum. The open item under "Measured on this host" (whether an explicit `--effort` in a headless session reaches its children) is answered by that
receipt's cases F5 to F7: under `--effort max` an unnamed subagent and a Workflow stage that named no effort ran at `max`, a stage that named
`low` ran at `low`, and a project agent whose frontmatter says `medium` ran at `medium`. Together with this record's cases the rule is: a child
that names no effort runs at its frontmatter effort, else at the effort the session was given explicitly, else at its model's saved level or
default. Nothing in this record's routing changed: every stage still names its model and `effort: 'max'`, judgment stays on
Opus 5.5, and the committed project `effortLevel: xhigh` does not defeat the launcher's `--effort max` (receipt
`claude-project-effort-flag-20260929`).
