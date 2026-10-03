# Decision: retire the gateway A/B R02 preregistration draft (PR #445) and record the R02 freeze on 20128 as overtaken (2026-10-03)

**Status: decided by session native-agent-stack-0c under the user's 2026-10-03 custody direction for unowned PRs.**
The [custody notice on #445](https://github.com/seathatflowsinourveins/native-agent-stack/pull/445#issuecomment-5967135175)
was posted at 08:22:02Z. Its two-hour objection window ended at 10:22:02Z without an objection or a lane claiming
R02. The post-window read checked #445, the newest #608 comments and coordination files newer than the notice;
the PR head remained `bddb00724d8e943e93cc597197efbfa38df9f6a5`. This is platform/coordination observation,
classified as `source_review`, not a new gateway acceptance run.[^custody]

**Scope:** retire the preregistration draft with its design and history retained. This record changes no host
and releases nothing. It serves the foundation's effort-evidence work for complex systems and the US-equities
research and historical-simulation north star by preserving a reusable comparison design without treating an
unrun study as measured evidence. The evidence boundaries follow
[`docs/acceptance-evidence-policy.md`](../acceptance-evidence-policy.md); classes below retain their historical
scope.[^policy]

`bddb0072` locators name the pinned PR head above. `main` locators name the original files at the builder's base,
`9b0b8d6d25f9e3fb8f71770500e774170423315e`. Later append-only addenda do not change those cited lines.

## What R02 was

The question was whether GPT-6 at max effort beat the gateway's default medium effort for framework (FW)
chat/completions roles by enough to pay for its reasoning tokens. The two arms were:[^arms]

| Arm | Model and treatment | Evidence class |
| --- | --- | --- |
| A | `cx/gpt-6-astra`; no `reasoning_effort` sent; the gateway default, medium per the gateway owner's #423 measurement | `source_review`; the owner's effort measurement is relayed |
| B | `cx/gpt-6-astra-max`; OmniRoute@dd6e9607e's built-in `-max` suffix alias, traced in `open-sse/executors/codex.ts:1424-1431` | `source_review` of the pinned design and its recorded upstream source |

The li26 subset selected 60 of 360 labelled 8-K filings, with seed `20260927`. Its four strata selected
14/81, 33/198, 8/49 and 5/32. Selection alternated between an AB run and a BA run of 30 filings each, with
three repeats per arm, for 360 planned calls. The original hashes were:[^subset]

| Input | SHA-256 | Evidence class |
| --- | --- | --- |
| li26 inputs | `2a5c8c9bd1650bc20a3e7364defef2d725904f6eb1ef509a511a49526a32bfe0` | `source_review` of the declared hash |
| `tests-ab.jsonl` | `54aaaa88d6dc227ec76e96a5139baba8e49300a06328712c0b8128f822d9b0a4` | `source_review` of the declared hash |
| `tests-ba.jsonl` | `de3e46ddd7bc5c5a140f51897b884419fb2755bce2b3a40132befe172e2de4e1` | `source_review` of the declared hash |

The decision rule first voided any run with an integrity problem: `analyze_r02.py` would compute no statistic
and exit 2. Otherwise it would adopt max if the one-sided 95% lower bound of micro-F1(B) minus micro-F1(A)
was above 0. Failing that, it would keep medium if A was non-inferior within 0.02 and the supported paired cost
leg showed A's completion tokens below B's. The cost leg required usage from all 360 calls and paired the
per-filing means over the three repeats. Otherwise the decision was inconclusive. These are declared rules,
class `source_review`, not observed outcomes.[^rule]

Statistics used scipy 1.18.1's paired bootstrap and `permutation_test`, in Python 3.14 with numpy 2.5.3 and
statsmodels 0.15.0. The bootstrap used 10,000 resamples, the percentile method and seed `20260927`; the
permutation test was secondary. Holm was reserved for a family of roles and was not applied to this one-role
comparison. This is `source_review` of the pinned analysis environment and procedure.[^statistics]

The gateway owner, rather than the runner, performed the fingerprint read-back. `plan.json` declared the eight
fields and their admissible values, including build `dd6e9607e`, the arm-model mappings, effort-related settings,
compression and timeouts. Before freezing, one dry read-back had to pass. Immediately before and after each run
half, the owner would return four sanitized objects; the analyzer would reject a missing field, an inadmissible
value or a difference between them. This is `source_review` of the protocol; its residuals remain below.[^fingerprint]

## What ran

**No scored R02 call was ever made.** The pinned head remained `draft-not-frozen-not-run`; main's routing record
also recorded that the scored run had not started and its owner was inactive. This is `source_review` of the
retained status and decision record, not a new inspection of private gateway logs.[^not-run]

| Historical operation | Result and boundary | Evidence class and locator |
| --- | --- | --- |
| First bounded wire check, 2026-09-27 19:49Z | Two calls; request-shape evidence only | Historical `native_proven`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:401-444`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:549-550` |
| Wire re-check, 2026-09-27 21:16Z | Two more calls, four in all; request-shape evidence only | Historical `native_proven`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:473-525`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:549-550` |
| Echo check against local go-httpbin | Configs at `9d03c1ea`; no gateway call | Historical `local_integration`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:445-472`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:551-553` |
| 80 offline tests in the pinned environment | Reported historical checks on fixtures; the pinned test module contains 80 test methods, which does not itself prove their execution | `synthetic`; `bddb0072:tests/test_gateway_ab_r02_20260927.py:115-1724`; fixture boundary at `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:554-557`; reported run count in the custody account[^reported-history] |
| Dry read-back, 2026-09-28T01:23:33Z at `00a94b52` | Exit 2: `/api/monitoring/health` needed management auth | `source_review` of reported native execution; `main:evidence/artifacts/omniroute-routing-20260928/decisions.json:65-68`; `main:blueprints/convergence-practice/omniroute-routing-20260928/experiment.json:370-383` |
| Dry read-back, 2026-09-28T01:29:29Z at `bddb0072` | Exit 0, admissible, with the keyless sources `GET /api/system/version` and the BUILD_SHA sentinel | `source_review` of reported native execution; `main:evidence/artifacts/omniroute-routing-20260928/decisions.json:71-74`; `main:blueprints/convergence-practice/omniroute-routing-20260928/experiment.json:386-395` |

The dry read-back outputs are private. Their exit statuses come from main's decision extract and experiment
record, which explicitly attribute them to the coordinator's log. Neither read-back was repeated for this
retirement.[^readbacks]

## Review history and residuals

The custody account reports three read-only GPT-6 rounds (`gpt-6-astra`, max): eight findings at `fae72c37`,
repaired in `f58a4a65` and `4b7c58de`; four findings at `4b7c58de`, repaired in `2c584098` and `af85abec`;
then none at `af85abec`, with the verdict "freeze-ready pending the owner's dry read-back". Class:
`source_review` of a reported review history. The pinned README directly documents the first eight and second
four findings; it does not retain the third-round verdict or a historical offline-test output. The reported
model/effort, first review head and final verdict are preserved as custody-report facts, rather than presented
as independently observed review executions.[^reviews][^reported-history]

The builder's ninth defect was promptfoo 0.123.1's results sanitizer compacting JSON-looking vars
(`dist/src/logger-ChlKG5Wv.js:1049-1057`). The repaired analysis compared `labels_json` as parsed JSON.
Class: `source_review` of the recorded source finding, with `synthetic` offline persistence checks.[^sanitizer]

The OAuth occupancy override was recorded as a shared account-selection condition. Every chat request asked
for `reserveOAuthSession: true` (OmniRoute@dd6e9607e `src/sse/handlers/chat.ts:1711`), and the selection could
move to another connection with more session availability (`src/sse/services/auth.ts:2159-2176`). R02's
single-call conversations exposed both arms to it. Class: `source_review` of the pinned design's recorded
source trace; no account-selection measurement was reproduced by this retirement.[^occupancy]

Five residuals remain, all `source_review` of the design's evidence limits:

1. The admissible values are a declaration, not an observation of all the required settings for the scored run;
   their provenance distinguishes historical observations, documented configuration and declared intent.[^fingerprint]
2. The private `server.env` can override the timeouts; it was not read.[^timeouts]
3. The read-backs are the gateway owner's report, rather than an independent observation.[^owner-report]
4. The call_logs snapshots contain observed lower bounds, with late or permanently failed saves undetectable.[^snapshot]
5. Whole-call duration was not recorded; the wire checks recorded time to response headers.[^duration]

## Why retired

**Bindings.** The arms and admissible values were bound to build `dd6e9607e` and the GPT-6 Astra model line.
The recorded 2026-09-30 rebuild overtook that binding: its target was `2f42a9ac1`, with the 20128 affinity patch
`045aa81f3`, build `ae5539a56`, switched over between 00:02:41Z and 00:03:00Z. That is a historical rebuild
statement, class `source_review` of the owner's published native operation, not a statement of the current
gateway build. The current build is the gateway owner's to state.[^bindings][^rebuild]

**Freeze.** Two recorded decisions were affected:

- The 2026-09-28T01:29:29Z freeze, `r02-freeze-20128`: "No routing change is applied to 20128 in that period."
  (`main:evidence/artifacts/omniroute-routing-20260928/decisions.json:29-33`).
- The occupancy patch's apply-after-R02 order, including the user quote "Full patch after R02"
  (`main:evidence/artifacts/omniroute-routing-20260928/decisions.json:36-41`).

Both ended **in fact** when the gateway owner, under the user's 2026-09-29/30 directions, rebuilt and restarted
20128 and applied `045aa81f3`. The rebuild record names neither R02 nor #445. The roadmap's F-WK-3 items asking
for the user's R02 freeze release and re-derived #445 admissible values were not carried by that record.
These are `source_review` findings from comparing the preserved decisions, the rebuild record and the roadmap;
they do not establish an explicit user release.[^rebuild][^roadmap]

**No explicit release by the user is on record. This record neither claims nor supplies one, and it releases
nothing.** It records the historical conflict without rewriting the freeze, its ordering condition or any
pinned artifact.[^freeze]

**Owner.** Main's `decisions.json:33` recorded the run owner as inactive. Before the custody notice, #445 had
had no comment or review since 2026-09-28T01:28:20Z, according to the custody account. Session 0c's
2026-10-02T23:58Z triage found no live owner, and no lane claimed R02 during the objection window. Class:
`source_review` of the historical decision and the custody/platform records.[^not-run][^custody][^reported-history]

**Use.** The 2026-10-03 #608 coexistence records treat 20128 as a shared pool with bounded windows and separate
lane acknowledgements. Those records establish coordination, not effort or model acceptance. Class:
`source_review` of the original platform comments.[^coexistence]

## Alternatives considered

These are the retirement decision's alternatives, based on the design bindings, the historical rebuild and
the absence of a claimed owner; their evidence class is `source_review`.[^bindings][^rebuild][^custody]

- **Land as written.** Rejected: the preserved bindings cannot qualify the rebuilt gateway, and landing the
  draft would put a misleading executable plan on main.
- **Re-derive now as R02.** Rejected without an owner or consumer. This would be a new preregistration needing
  a new freeze, new admissible values, GPT-6.1 arms, declared capacity bounds and a fresh review.
- **Port the harness.** Rejected because no main consumer is identified; its design and code remain retrievable.

## Reopen or overturn conditions

- If the user or gateway owner says the freeze or R02 must stand, reopen #445 as a user decision.
- If a lane needs framework-role effort evidence on the current gateway, it writes a new preregistration with
  a new id, bound to the then-current build fingerprint, model line and declared capacity bounds. It can reuse
  R02's retained design and code, with its own freeze and review.

These are prospective decision conditions, not a new run authorization or a release of the historical freeze.

## Retained

The branch `claude/gateway-ab-r02-prereg-20260927` at `bddb00724d8e943e93cc597197efbfa38df9f6a5` and
`refs/pull/445/head` are retained. A read-only remote-ref observation on 2026-10-03 returned that SHA for both
refs; this record does not delete or rewrite either. Class: `source_review` / independent platform observation.
Main cites commits `00a94b52` and `bddb0072`, rather than the branch name, so those objects remain the retrieval
locators.[^retained]

The private R02 state directory is untouched and stays unpublished. Every evidence artifact and the routing
experiment remain byte-identical; this retirement adds a decision and append-only addenda, then re-registers
their hashes through the existing hot-file protocol. No gateway call, read-back, restart or setting change is
part of this decision.[^policy]

## Source locators and evidence boundaries

[^custody]: Original #445 custody notice [5967135175](https://github.com/seathatflowsinourveins/native-agent-stack/pull/445#issuecomment-5967135175) and #608 mirror [5967137495](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5967137495); post-window read-only platform and coordination observations retained in the builder handoff. Class: `source_review` / independent observation. The notice reports the user's custody direction and the unowned-PR finding.
[^policy]: `main:docs/acceptance-evidence-policy.md:24-33,46-61`; `main:docs/lanes.md:94-148`; repository evidence-preserving retirement precedent `main:docs/decisions/2026-09-25-retire-vela-velanext.md:32-46`. This record follows those policies and the assigned custody scope; it adds no native execution claim.
[^arms]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:12-23`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:5-18`. Class: `source_review`.
[^subset]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:87-114,181-199`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:25-38`. Class: `source_review`; private inputs were not read or rehashed.
[^rule]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:250-258`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:353-370`. Class: `source_review`.
[^statistics]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:259-295`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:374-389`. Class: `source_review`.
[^fingerprint]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:296-307,319-373`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:501-538`. Class: `source_review`; declaration and historical provenance are separate.
[^not-run]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:3-8`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:3`; `main:evidence/artifacts/omniroute-routing-20260928/decisions.json:33`; `main:blueprints/convergence-practice/omniroute-routing-20260928/experiment.json:489`. Class: `source_review` of reported run status.
[^readbacks]: `main:evidence/artifacts/omniroute-routing-20260928/decisions.json:65-74`; `main:blueprints/convergence-practice/omniroute-routing-20260928/experiment.json:114-115,376-395,494`. Class: `source_review`; the experiment calls these `native_cli_execution`, but its scope says the exits are from the coordinator's log and the outputs are private.
[^reported-history]: Session native-agent-stack-0c's 2026-10-03 custody account, `contract-PR445.md:68,74-78,93`, retained privately. It supplies the reported historical test execution, review model/effort and third verdict, and precise triage/last-activity times. These details are report evidence; the pinned blobs do not retain their original execution outputs. No stronger independent-execution claim is made here.
[^reviews]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:665-714`; repair commit objects `f58a4a655f0b69d07cdc0454adb02f0285ee41b3`, `4b7c58de8a641e93ed0dd7fe7795a90bf379ee49`, `2c584098c7d8d3e7307be51b94f4ee738181aed0` and `af85abec7e5a121eaf2882e0e0d43078a6656460`, read without changing refs. Class: `source_review`; see the custody-report boundary above.
[^sanitizer]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:168-175`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:243`. Class: `source_review`; persistence fixtures remain `synthetic`.
[^occupancy]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:581-596`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:533`. Class: `source_review` of the recorded upstream trace.
[^timeouts]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:488-491,518`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:371,374`. Class: `source_review`.
[^owner-report]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:626-632`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:374`. Class: `source_review`.
[^snapshot]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:634-636,710-712`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:245,539`. Class: `source_review`.
[^duration]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:573,623-625`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:206`. Class: `source_review`.
[^bindings]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:7-18,319-330`. Class: `source_review`.
[^rebuild]: `main:docs/decisions/2026-09-30-omniroute-rebuild.md:3-8,33-36,43-55`; the entire original record was checked for R02/#445 references. Class: `source_review` of the owner's historical native-operation record; no current-build observation.
[^roadmap]: `main:docs/decisions/2026-09-28-ecosystem-roadmap.md:185-189,237-238`. Class: `source_review` of requirements not carried by the rebuild record.
[^freeze]: `main:evidence/artifacts/omniroute-routing-20260928/decisions.json:29-41`; `main:blueprints/convergence-practice/omniroute-routing-20260928/README.md:103-110,163-167,192`; `main:blueprints/convergence-practice/omniroute-routing-20260928/experiment.json:489`. Class: `source_review`; the historical instructions remain unchanged.
[^coexistence]: Original #608 comments [5966185450](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5966185450), [5966191333](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5966191333), [5966225109](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5966225109) and [5966289633](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5966289633), read in full. Class: `source_review` / platform observation of coordination only.
[^retained]: `main:blueprints/convergence-practice/omniroute-routing-20260928/experiment.json:114-115,376,393`; `main:evidence/artifacts/omniroute-routing-20260928/decisions.json:67,73`; read-only `git ls-remote origin refs/heads/claude/gateway-ab-r02-prereg-20260927 refs/pull/445/head` on 2026-10-03. Class: `source_review` / independent platform observation; no ref mutation.
