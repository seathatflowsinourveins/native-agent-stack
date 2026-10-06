# Upstream evidence selects foundation components; local checks prove our wiring

Date: 2026-10-06. Lane: foundation. Status: decided on the owner's direction;
repository record awaiting independent GPT review and CC acknowledgement.

## Context and authority

Long local comparisons had become prerequisites for finishing the native
foundation, including comparisons of upstream components already selected and
installed. The owner changed that evaluation rule on 2026-10-06. This record
paraphrases the command center's interpretation in
`coordination/command-center/ITEM-ns2604-coop-20261006T190307Z.md`
(SHA256 `425a46312a9dae9a2234e2ec64951f802b389bbb0c11cf744ac120dcce2f4734`).
That private interpretation supplies the five rules and the named supersessions;
this document contains no verbatim quotation of the owner.

The action served is completing the native foundation for US-equities research
and historical simulation, followed by the separately qualified paper lanes.
The [trading rules](../../blueprints/us-equities/AGENTS.md) and
[paper policy](../paper-lane-policy.md) retain their own gates.

## Decision

1. **Select from upstream evidence.** Where upstream evidence can establish a
   component's quality, compare the maintainer's organization, release discipline,
   tests, published benchmarks and client fit. For models, include release
   evidence and relevant leaderboard results. Local head-to-head runs, trial
   matrices and A/B campaigns cease to determine these component choices.
2. **Install the maintained release.** Use the clean upstream release and its
   documented installation and configuration, meeting or exceeding its baseline.
   Record the repository, revision, supported client integration and installation
   state.
3. **Collect two kinds of local evidence.** An integration smoke check shows
   that the component starts, registers and answers a real call in each client
   that uses it. Organic native counters come from the clients' records during
   ordinary work after installation. Record their actual scope; missing use or
   missing counters remain explicit.
4. **Close from the recorded evidence.** READY requires the source-backed
   selection, installation and the two evidence types above. Otherwise the
   disposition is BY_DESIGN or a dated exclusion, with its reason. A smoke check
   is labelled as a smoke check; its result does not become an acceptance or
   benchmark claim.
5. **Revisit when upstream changes.** A new release or a better-evidenced
   candidate reopens the source comparison. A recurring local re-measurement
   schedule does not reopen the component choice.

The readiness owner records row dispositions and outstanding installation or
user actions. This decision establishes the rule; individual rows require their
own source and result records. Existing failures, unknown counters and bounded
historical results remain in the evidence history.

## Gates superseded on 2026-10-06

The following comparisons cease to gate component selection or readiness.
Their recorded artifacts retain their original scope.

| Superseded gate | Record or PR carrying it | Resulting work |
| --- | --- | --- |
| D3r4 memory head-to-head, step 8 onward | The private D3r4 protocol and Amendment 1, identified by `coordination/command-center/ITEM-ns2604-coop-20261005T053703Z.md` and the step-8 binding in `ITEM-ns2604-coop-20261005T041934Z.md`; repository settling exceptions in [repository-quality rule](2026-10-04-repository-quality-rule.md) and [final architecture, round 2](2026-10-04-final-architecture-round2.md) | Compare candidates' upstream releases, published evaluations and client fit. The installed owner remains an installation fact; the memory recommendation and CC decision use upstream evidence. |
| Harbor A/B for the 11 token rows | [Token layer default](2026-10-04-new-wsl-token-layer-default.md), [full-stack owner default](2026-10-04-token-full-stack-owner-default.md), the comparison/overturn rules in [definitive defaults](2026-10-01-new-wsl-definitive-defaults.md), and private `coordination/ns2604-coop/organic-e2e-20261005/protocol-v1-adjudicated.json` with `suite-v1.json` and `AMENDMENT-U1-native-arm.md` | Record each row's upstream source/release, installation, client smoke result and organic before/after counters as they become available. |
| Code-navigation trial matrix | [PR #786](https://github.com/seathatflowsinourveins/native-agent-stack/pull/786), carrying `evidence/artifacts/organic-e2e-20261005/PROTOCOL-v1.1.md`, `PILOT-SPEC-v1.1.md` and `AMENDMENT-v1.1-20261006.md`; repository code-search exceptions in the two October 4 selection records above | Finish round 6e as a clean, pushed draft. Start no pilot or trial runs. |
| Skills S1 promptfoo skill-used assertions | [PR #795](https://github.com/seathatflowsinourveins/native-agent-stack/pull/795); [promptfoo-skills configuration](../../evidence/artifacts/new-wsl-install-plan-20261002/config/promptfoo-skills.json), [round-2 G4 plan](2026-10-04-round2-plan-g4-config.md), and the skills acceptance function in [accept.sh](../../evidence/artifacts/new-wsl-install-plan-20261002/accept.sh) | Use upstream skill evidence, installation/client wiring smoke checks and organic counters. The campaign's skill-used and not-skill-used assertions cease to gate selection or readiness. |
| mcp-grafana promptfoo A/B | Private `coordination/e2e-truth-20261006/monitor-finalize-wf_d5f9d1db-859.json#/gaps/0/checks/27`, `#/gaps/0/exact_changes/8` and `#/plan/open/13`; predecessor `monitor-gaps-wf_1765cb57-995.json` | Keep the actual Grafana/client wiring checks; use organic counters or the S4 smoke for an unused slot. |
| Re-measurement campaigns behind the 13 rows citing #723 | [PR #723](https://github.com/seathatflowsinourveins/native-agent-stack/pull/723) and private `coordination/e2e-truth-20261006/foundation-eta-rerun-wf_91416191-566.json#/result/units/0/result/items` | Repair the plan, re-apply the installation, and record a smoke result and counters. The 13-row cohort is listed below. |

The #723 cohort is `skill-discovery`, `mcp-inspector`, `agent-messaging`,
`agent-runtime-worker`, `research-harnesses`, `code-search`, `alerting`,
`session-analytics`, `inspect-ai`, `harbor-containerized-agent-e2e-runner`,
`promptfoo`, `cross-family-review` and `sandbox-runtime-srt`. These are the
13 matching items in that dated readiness source, rather than a claim that all
13 installations or checks have completed. Its item indices are
6, 10, 11, 13, 14, 18, 46, 48, 49, 50, 51, 64 and 70.

Private protocols and draft PRs in this table are source locators, not files
added to this PR or landed repository evidence. A superseded comparison is
recorded as superseded, preserving any earlier failed or incomplete attempt.
The 11-token-row count is the CC's declared campaign scope; historical inventories
have different scopes, so this record supplies no invented 11-member mapping.

## Retained checks and S4

Integration checks of our own wiring, the paper lane's gates, CI and independent
review of substantive changes continue. An installation failure, refused call,
incorrect registration or broken local integration still needs repair and an
honest result. Provenance, discriminating controls for claims about our own
wiring, and the boundary between source review, native operation and structural
validation remain in the [acceptance evidence policy](../acceptance-evidence-policy.md).
The named skills and Grafana A/B campaigns above are superseded even where their
configuration contains integration assertions; this is not a blanket deletion
of wiring tests.

S4 becomes one read-back after **one working day of normal lane work following
both tools windows**. Read organic counters from native client records; give
each slot without organic use, including services, timers and dashboards, one
integration smoke check. Consolidate the observation and smoke results into
one receipt and obtain independent review. Today's relaunched lanes are the
CC-designated fresh-session cohort for this observation. The cohort designation
does not assert that a resumed thread acquired a new canonical session ID.

This replaces the staged S4 campaign in the
[foundation requalification record](2026-10-05-ns2604-foundation-requalification.md)
and the draft [north-star start-line PR #801](https://github.com/seathatflowsinourveins/native-agent-stack/pull/801).
That working day begins after both windows, rather than after the Codex-side
relaunch alone. The receipt retains versions, counter scope, observation bounds,
unknowns and smoke results. Cumulative snapshots and overlapping usage are
counted once; organic counts alone establish neither causal savings nor a
candidate's comparative quality.

## Policy precedence and cross-references

For upstream foundation-component selection and readiness, this dated decision
takes precedence over the local-comparison requirements in:

- [Acceptance evidence policy](../acceptance-evidence-policy.md):
  behavior-check prerequisites and the matching-comparison replacement rule.
- [Harness defaults](../harness-defaults.md): reproduced-result selection,
  candidate head-to-head comparisons and adoption qualification.
- [Convergence architecture](../convergence-architecture.md): the baseline and
  alternative comparison for selecting a component.
- [Repository-quality rule](2026-10-04-repository-quality-rule.md):
  memory/code-search exceptions and the locally measured overturn route.
- [Final architecture, round 2](2026-10-04-final-architecture-round2.md):
  memory/code-search settling measurements and comparison-based removal checks.
- [Full-stack token owner default](2026-10-04-token-full-stack-owner-default.md):
  measured retention/pruning and confirmatory code-search selection.
- [E2E fix-wave integration](2026-10-04-2604-e2e-fix-wave.md):
  component-removal comparisons, including promptfoo versus Harbor/Inspect.
- [Definitive WSL program](2026-10-01-definitive-sota-wsl-program.md),
  [U11 merit-neutral design](2026-10-01-u11-merit-neutral-selection.md) and
  [definitive defaults](2026-10-01-new-wsl-definitive-defaults.md):
  measured merit/closure and future comparison gates. U11's v2 design was a
  proposal, not an implemented selection policy.
- [Token practice](../token-practice.md) and
  [native saturation](../token-native-saturation.md): future component-evaluation
  requirements. Their historical result labels and constraints on savings claims
  remain.

The acceptance policy, harness defaults, convergence guide and token-practice
guide gain pointer lines. The older dated decisions remain historical records.
The quality-rule and token-owner records have live hashes in
`evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json`
(`/wave4/records/quality_rule`, `/wave5/records/quality_rule`,
`/wave3/records/decision_record`); their owner must coordinate any reverse pointer
with those hashes. This PR changes neither the consensus nor #723's install
plan. Application engineering, strategy research and paper operation retain
their separately stated checks.

### Instruction-carrier handoff to the CC

Instruction files and their templates are unchanged. The CC owns these sentence
updates; the descriptions below identify the existing requirements without
quoting the owner's new rule.

| Existing instruction location | Sentence needing scope clarification |
| --- | --- |
| `AGENTS.md:9`, documented-gap candidate-choice sentence | Its foundation-selection reference to `2026-10-04-repository-quality-rule.md` should point to this [October 6 upstream-evidence rule](2026-10-06-upstream-evidence-over-local-evaluation.md), replacing the memory/code-search settling-measurement exception and locally measured overturn route. The CC owns the instruction edit. |
| `examples/claude-native/CLAUDE.md`, opening top rule | The candidate-selection sentence requiring measured head-to-head quality/security/maintenance should use upstream evidence. |
| `AGENTS.md`, `examples/claude-native/CLAUDE.md`, `adoption/templates/codex.AGENTS.template.md`, `adoption/scaffold/AGENTS.md` | The sentence assigning promptfoo, skill-creator and Harbor/Inspect to A/B/E2E needs application-evaluation scope; it cannot imply a component-selection campaign. |
| The same four carriers, search-first sentence | The fallback skill-verification/A/B clause should distinguish source-backed skill choice and client smoke checks from a local selection campaign. |
| `adoption/templates/codex.AGENTS.template.md` and `adoption/scaffold/AGENTS.md`, dated-decision sentence | The overturn comparison should compare changed upstream evidence, rather than require a scheduled local trial. |
| `examples/claude-native/CLAUDE.md`, core convergence sentence | Reproduced results remain evidence for our changed wiring and application behavior; upstream sources determine component selection. |
| `AGENTS.md`, evidence/completion native-command sentence; `adoption/templates/codex.AGENTS.template.md`, `adoption/scaffold/AGENTS.md` and `examples/claude-native/CLAUDE.md`, top rule | The supported installation/native-test-command sentence needs component-selection scope: upstream tests inform selection and our client smoke/wiring checks supply local evidence. |
| `AGENTS.md`, token-practice representation sentence | The cheapest-measured-representation requirement applies to a task's information contract without requiring a new component-selection campaign; accounting and correctness constraints remain. |

Root `CLAUDE.md` and `adoption/scaffold/CLAUDE.md` import `AGENTS.md`;
they have no separate selection mandate to rewrite. Host-level deployed copies
follow their maintained carriers through the CC's configuration workflow.

## Alternatives and overturn condition

Retaining every local campaign would keep upstream-component choices dependent
on lengthy runs despite source-backed releases and published evidence. Keeping
the October 4 rule with memory/code-search exceptions would preserve that same
dependency for those slots. Closing rows from source quality or a version print
alone would omit our actual client integration and organic observation.

The selected rule combines upstream choice with bounded wiring evidence and
normal-work counters. Reopen a component choice when a newer upstream release
or better-evidenced candidate changes the source comparison: compare relevant
published results, supported clients, maintenance and clean-release integration
against the selected owner. Record the resulting retain, replace or exclusion
decision with its sources. Local wiring failures prompt integration repair;
a scheduled re-measurement does not initiate selection. Changing this evaluation
rule itself requires a new dated owner decision.

## Upstream references and evidence boundary

- [ECC search-first](https://github.com/affaan-m/ECC/blob/2b6e839771e53096d8451a213d40dc64ec8acac0/skills/search-first/SKILL.md),
  commit `2b6e839771e53096d8451a213d40dc64ec8acac0`, Workflow and Decision Matrix:
  research maintained existing solutions before choosing implementation.
- [MCP lifecycle](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/38c84e9f93ad191d9eb26d92b945d17bd0efcaf3/docs/specification/2025-11-25/basic/lifecycle.mdx),
  protocol revision `2025-11-25`, Initialization and Operation: client/server
  capability negotiation and operation are separate from configuration text.
- [promptfoo README](https://github.com/promptfoo/promptfoo/blob/0.123.1/README.md),
  tag `0.123.1`: a maintained evaluation tool remains available for appropriate
  application tests; the owner's rule determines whether a campaign gates this
  foundation.

These references inform research and integration methods. They do not assert
that an upstream maintainer endorses this owner-specific readiness policy.
This PR records a decision and pointers, with structural checks and source
review; it installs nothing and provides no new benchmark, causal token saving,
native smoke result or row closure.
