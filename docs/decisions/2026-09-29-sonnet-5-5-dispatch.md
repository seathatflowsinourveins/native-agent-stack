# Decision: Sonnet 5.5 and Opus 5.5 dispatch, effort and the default child model (2026-09-29)

**Decided by:** the coordinator session `native-agent-stack-79` on host `nativestack-5975wx-20260925`, for the user's requests of
2026-09-28 and 2026-09-29: compare Sonnet 5.5 with Opus 5.5, retire stale models, "assign to it [Sonnet 5.5] when large ultracode
subagents or any tasks suitable", and make the ecosystem manifest the latest practice for both models. Checked against Claude Code
2.1.284; branch `claude/sonnet55-dispatch-20260929`, based on `origin/main@bab06007`. It extends the
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

Opus 5.5 keeps every judgment; Sonnet 5.5 takes fan-out units and execution work that an executable oracle or a later Opus stage
checks. Aliases route (`opus`, `sonnet`), so a new model of a family is picked up by a client update, and `child-usage.mjs` reports a
child that ran an older model than its alias documents. Every stage names its model and `effort: 'max'`.

| Task class | Model, effort | Why | What checks it |
| --- | --- | --- | --- |
| Design, architecture, adversarial review, verification of claims against source, security review, adjudication, synthesis, blind lanes | `opus` (Opus 5.5), max | Opus 5.5 is ahead on the honesty and reckless-tool-use audits and is the less self-preferring grader; Sonnet 5.5 "hallucinates more" ([Sonnet 5.5 card](https://www.anthropic.com/claude-sonnet-5-5-system-card) sections 6.1.2, 6.2.2, 6.2.3, 6.3.1) | the role table's agents and the contract tests |
| Shell, test, build and lint runs; the acceptance commands a task names | `sonnet` (Sonnet 5.5), max | Terminal-Bench 4.0 in two of three measurements (below); the vendor rates it Fast against Moderate for Opus 5.5 | the command's exit code and output |
| Exact extraction, inventories, counts, log analysis | `sonnet`, max (`source-scout`) | mechanical, deterministic output | file:line locators the consumer re-reads; Opus verifier on claims |
| Migrations, refactors and scaffolds from a written contract, in an owned checkout | `sonnet`, max, as a per-stage override of `isolated-builder` | Vals AI ranks Sonnet 5.5 first on Code Migration (69.83% against 66.65%) and Vibe Code Bench (92.39% against 90.29%) | the contract's tests, then an Opus review and CI; a build without a test oracle stays on `opus` |
| First-pass breadth research | `sonnet`, max, only as bulk fan-out | Anthropic's multi-agent research system is an Opus lead over Sonnet subagents | an Opus refuter or verifier stage on every claim |
| Coordinator | the user's session model, either Sonnet 5.5 or Opus 5.5, saved at xhigh | a Sonnet main model with an Opus advisor is Anthropic's named pairing ([advisor](https://code.claude.com/docs/en/advisor)) | the advisor stays `opus`; a Sonnet coordinator sends any judgment to `opus`-named children |
| Agent-team teammates | named at spawn: `sonnet` to execute or explore, `opus` to judge | Anthropic's costs page recommends Sonnet for teammates ([costs](https://code.claude.com/docs/en/costs)) | the lead verifies teammate results before acting |
| Cross-family judgment and review | `gpt-6-astra` at max; `gpt-6-sol` at medium for mechanical extraction | unchanged: measured tiering of 2026-09-27 | unchanged |

The role table's defaults (scout on Sonnet; researcher, builder, reviewer, security, verifier and adjudicator on Opus) do not change:
the repository's contract tests pin them, and the five hash-pinned role bodies of the #381 preregistration stay untouched. The Sonnet
assignments above are per-stage `model` overrides, which the client documents as taking precedence over an agent's own default.

## Evidence

**Terminal-Bench 4.0 depends on who runs it** (all three runs had the safety fallback enabled, which this host disables):
- Anthropic's runs, Claude Code `--bare`, 5 trials per task on 66 tasks: Sonnet 5.5 70.6% at max effort, Opus 5.5 66.4% at xhigh
  and 64.8% at max, standard errors +-2.5 and +-2.6 ([Sonnet 5.5 card](https://www.anthropic.com/claude-sonnet-5-5-system-card) section 8.5).
- [Artificial Analysis](https://artificialanalysis.ai/evaluations/terminalbench-4-0) (mini-swe-agent, mean of 3): Sonnet 5.5 63.6%,
  Opus 5.5 59.6%.
- [Vals AI](https://www.vals.ai/benchmarks/terminal-bench-4) (Terminus 2, average of three runs): Opus 5.5 61.62%, Sonnet 5.5 53.03%.
  With fallback-assisted tasks counted as failures Vals gives 50.51% (7 of 198) for Sonnet 5.5 and 53.54% (30 of 198) for Opus 5.5
  ([Sonnet 5.5](https://www.vals.ai/models/anthropic_claude-sonnet-5-5) and
  [Opus 5.5](https://www.vals.ai/models/anthropic_claude-opus-5-5) pages, read 2026-09-28).
- The official [tbench.ai board](https://www.tbench.ai/leaderboard/terminal-bench/2.0) showed no Sonnet 5.5 or Opus 5.5 row in the
  data embedded in its page when read on 2026-09-28 (its rows were dated 2026-09-21), and community submissions are closed. So no
  owner-verified 5.5 result exists.

The order of the two models flips with the harness, so this record does not rest the split on one score. It rests on the terminal
and app-building results together, on the vendor's own role guidance, and on the checks in the last column above.

**Fallback and refusal behaviour favours Sonnet on shell and operations work.** Opus 5.5 was fallback-assisted far more often than
Sonnet 5.5 in Vals' runs: Terminal-Bench 4.0, 30 against 7 of 198 attempts; SRE Bench, 217 against 126 of 262 tasks. This host sets
`CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK=1`, so a flagged request ends as an error instead of an answer from an older model, and an
Opus 5.5 child is the likelier of the two to hit one on such work. This is an inference from Vals' counts, not a measurement on this
host; the refusal rule below (retry once on the same model with an edited brief) is unchanged.

**Where Opus 5.5 leads** (the reason judgments stay on it): the honesty and reckless-tool-use audits and the self-preference grader
test named above; SWE-Bench Pro 89.9 against 81.3 and Humanity's Last Exam with tools 67.7 against 64.5 (card table 8.1.A and
section 8.11); Vals ranks Opus 5.5 first on ProgramBench and Terminal-Bench 2.1. In a simulated subagent task, Sonnet 5.5 copied a
planted fault into its messages to a coordinator in 62% of sessions, against 22% to 35% for the other models tested (card section
7.2.3), so a Sonnet worker's claims are re-read or re-run by the consumer.

**When a second model pays.** Anthropic's [model-selection page](https://platform.claude.com/docs/en/about-claude/models/choosing-a-model)
names two multi-model patterns, an executor that escalates to an advisor and an orchestrator that delegates bulk work to lower-cost
workers, and its [cost guide](https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence)
found that a frontier orchestrator with lower-cost workers paid off in two situations: capping the cost tail on routine work, and
input larger than one context window; on work one model could do alone, that model at lower effort was cheaper every time. The rule
therefore fits bulk and over-context fan-out, and a new fan-out class is piloted with an effort sweep before the second model is added.

**Price and speed.** Sonnet 5.5 is $2 and $10 per million input and output tokens and Opus 5.5 $4 and $20, with cache reads at $0.20
for both ([models overview](https://platform.claude.com/docs/en/about-claude/models/overview), read 2026-09-28). At max effort Sonnet
5.5 emits more output tokens per task, so its cost per task is not half of Opus 5.5's; no in-repository cost comparison exists.

**Measured on this host (Claude Code 2.1.284).** The receipt above holds 26 probes; this record relies on these:
- Ultracode neither raises nor overrides effort. A Sonnet 5.5 session under the host settings (`ultracode: true`, a user-scope
  top-level `effortLevel` of xhigh, `modelSettings` for Opus 5.5 only) ran at medium; a saved per-model level of low won over
  `ultracode: true` for both models; a committed project file's top-level `effortLevel: xhigh`, or a `modelSettings` entry, raised the
  Sonnet 5.5 session to xhigh. The Ultracode reminder stayed present at max effort set by flag and by environment variable.
- A subagent, workflow agent or teammate that no per-call model or definition names ran the lead's model, at the session's effort in
  the interactive case and at its own model's saved level or default in the headless case.
- `CLAUDE_CODE_SUBAGENT_MODEL=opus` put an unnamed subagent on Opus 5.5 at xhigh under a Sonnet 5.5 lead, and `=sonnet` put it on
  Sonnet 5.5 at medium under an Opus 5.5 lead ([env vars](https://code.claude.com/docs/en/env-vars): the default for children that
  nothing else assigns).

## What changes

- `.claude/settings.json` and the portable `examples/claude-native/ultracode.settings.json` (with the recipe's embedded copy) gain
  `"effortLevel": "xhigh"`. The portable file and the template also gain `CLAUDE_CODE_SUBAGENT_MODEL=opus`; the project file does not,
  so a sealed measurement run in this repository keeps its own model composition.
- `adoption/templates/claude.settings.template.json` pins `claude-sonnet-5-5` at xhigh beside `claude-opus-5-5` and sets the default
  child model. Tests: `tests/test_install_claude_profile.py`.
- `examples/claude-native/workflows/README.md` gains the fan-out section; `examples/claude-native/CLAUDE.md` restates the
  model-assignment, default-child and effort rules (its word budget is re-baselined to 1,310); `recipes/claude-native-ultracode.md`
  records the change.
- Companion changes merged with this record's branch or by their own pull requests: alias rows for `sonnet` and `fable` in
  `child-usage.mjs`; the effort guard no longer treats `ultracode: true` as xhigh; the native Claude Code floor moves to 2.1.284
  (below 2.1.284 the `sonnet` alias means Sonnet 5, so an older client silently routes the alias to the older model).
- The receipt `claude-model-effort-probes-20260929`.

**Host configuration**, applied by hand with a backup and a read-back (host files are not tracked): `~/.claude/settings.json` gains
`modelSettings.claude-sonnet-5-5.effortLevel = xhigh` and `env.CLAUDE_CODE_SUBAGENT_MODEL = opus`; the user's `model` (the floating
`sonnet` alias), `advisorModel` (`opus`), `ultracode`, and every other key are untouched. `~/.claude/CLAUDE.md`'s Quality and
Ultracode bullets take the same text as the portable file.

## Not changed, and why

- The five sealed role bodies and the frozen routes of #381, the saved workflow scripts, and every agent definition: hash-pinned.
- `AGENTS.md` line 35 ("stays at xhigh under Ultracode, because a `max` session turns its workflow orchestration off"): a shared hot
  file. Its second half is now unsupported on 2.1.284 (the reminder stayed present at max), and its first half is what the settings
  now save per model. The change goes in a separate `lane:shared` pull request that needs the trading lane's acknowledgement.
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
- **`CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1`.** Rejected: it would put every Opus-named role on the lead's model.
- **A project-level `CLAUDE_CODE_SUBAGENT_MODEL`.** Rejected: it would change the model composition of a sealed #381 run started here.

## Overturn

- A matched paired run (the Harbor and Terminal-Bench 4.0 run card, once the user decides the credential route, sandbox and budget)
  or an in-repository role-quality sweep shows Sonnet 5.5 below Opus 5.5, beyond the run's detectable difference, on a fan-out class
  routed here: move that class back to Opus.
- A Sonnet child's refusal or fault-copy rate, read from `child-usage.mjs` and the run transcripts, exceeds Opus 5.5's on a routed
  class.
- Claude Code restores `ultracode` precedence over saved effort (the guard's test names the behaviour), a new Sonnet or Haiku ships
  (the alias rows and the settings pins move together), or Anthropic's guidance on orchestrator-worker use changes.

## Unresolved

- The Harbor run needs the user's credential route, sandbox and budget; none was started.
- Hand-offs, not edited here: `evidence/artifacts/token-adoption-e2e-20260926/RUNBOOK.md` line 219 launches `claude --effort
  ultracode -p` with no `--model`, so under this host's `sonnet` default the sealed run's lead is Sonnet 5.5; the owner of Gate A
  should pass `--model` and record the resolved model. `catalogs/us-equities/models.json` still defaults to `claude-opus-5[1m]`
  (trading lane). `tools/sota-convergence/codex_lane.py` defaults its effort to `high` where the rule is max (open PR #216).
- The receipt observed each child kind once, and did not exercise long tool-heavy sessions.

## Limitations

- One workstation and one client version. The benchmark figures are vendor and third-party reports read on 2026-09-28; none is an
  in-repository measurement, and the Vals fallback counts are a different setting from this host's.
- The per-stage Sonnet overrides are a routing rule, not a qualification: no role-quality comparison on Sonnet 5.5 exists here.
- The receipt's limitations apply, in particular that the Ultracode reminder is an indicator and not proof of workflow behaviour.
