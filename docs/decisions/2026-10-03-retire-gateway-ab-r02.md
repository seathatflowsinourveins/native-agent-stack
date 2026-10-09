# Decision: retire the gateway A/B R02 preregistration draft (PR #445) and record the R02 freeze on 20128 as overtaken (2026-10-03)

**Status: retired by the 2026-10-03 custody review; this dated decision follows [versioned upstream evaluation interfaces](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/README.md) and retains source-only R02 evidence.**
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

The pinned README asked: "Does GPT-6 at max effort beat the gateway's default medium effort for framework (FW)
chat/completions roles by enough to pay for its reasoning tokens?" Cost entered only the keep-medium branch of the
decision rule below; the adopt-max branch, in `plan.json`'s words, "does not depend on cost".[^rule] The two arms
were:[^arms]

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

**No scored R02 call is on record.** The pinned head remained `draft-not-frozen-not-run`, and main's routing
record says that, as of the coordinator log's 03:3xZ entry on 2026-09-28, the scored run had not started and its
owner was no longer active. This is `source_review` of the retained status and decision records, not a new
inspection of private gateway logs. It shows that no scored run was recorded, not that no call could ever have
been made.[^not-run]

| Historical operation | Result and boundary | Evidence class and locator |
| --- | --- | --- |
| First bounded wire check, 2026-09-27 19:49Z | Two calls; request-shape evidence only | Historical `native_proven`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:401-444`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:549-550` |
| Wire re-check, 2026-09-27 21:16Z | Two more calls, four in all; request-shape evidence only | Historical `native_proven`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:473-525`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:549-550` |
| Echo check against local go-httpbin | Configs at `9d03c1ea`; no gateway call | Historical `local_integration`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:445-472`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:551-553` |
| 80 offline tests in the pinned environment | Reported historical checks on fixtures; the pinned test module contains 80 test methods, which does not itself prove their execution | `synthetic`; `bddb0072:tests/test_gateway_ab_r02_20260927.py:115-1724`; fixture boundary at `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:554-557`; reported run count in the #445 PR description[^reported-history] |
| Dry read-back, 2026-09-28T01:23:33Z at `00a94b52` | Exit 2: `/api/monitoring/health` needed management auth | `source_review` of reported native execution; `main:evidence/artifacts/omniroute-routing-20260928/decisions.json:65-68`; `main:blueprints/convergence-practice/omniroute-routing-20260928/experiment.json:370-383` |
| Dry read-back, 2026-09-28T01:29:29Z at `bddb0072` | Exit 0, admissible, with the keyless sources `GET /api/system/version` and the BUILD_SHA sentinel | `source_review` of reported native execution; `main:evidence/artifacts/omniroute-routing-20260928/decisions.json:71-74`; `main:blueprints/convergence-practice/omniroute-routing-20260928/experiment.json:386-395` |

The dry read-back outputs are private. Their exit statuses come from main's decision extract and experiment
record, which explicitly attribute them to the coordinator's log. Neither read-back was repeated for this
retirement.[^readbacks]

## Review history and residuals

The #445 PR description reports three read-only GPT-6 rounds (`gpt-6-astra` at max, on one Codex thread): eight
findings at `fae72c37`, repaired in `f58a4a65` and `4b7c58de`; four findings at `4b7c58de`, repaired in `2c584098`
and `af85abec`; then none at `af85abec`, with the verdict "freeze-ready pending the owner's dry read-back". It adds
that the third round's sandbox lacked numpy and scipy, so that round ran 76 tests and skipped the 4 statistical
ones, while all 80 passed in the pinned environment. Class: `source_review` of a reported review history. The
pinned README directly documents the first eight and second four findings; the third-round verdict and the
offline-test runs are retained only in the PR description. The model and effort, the first review head, the final
verdict and the test runs are preserved as author-reported facts, not as independently observed review or test
executions.[^reviews][^reported-history]

The PR description also reports a ninth defect that the builder found and fixed: promptfoo 0.123.1's results
sanitizer compacts JSON-looking vars (`dist/src/logger-ChlKG5Wv.js:1049-1057`). The pinned README and plan record
that behaviour and the repair: `labels_json` is compared as parsed JSON. Class: `source_review` of the recorded
source finding, with `synthetic` offline persistence checks; the "ninth" count and the attribution to the builder
are author-reported.[^sanitizer][^reported-history]

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
`dd6e9607e` was a `release/v3.8.51` `a58000c7` build with PRs #14904 and #13788. The 2026-09-30 rebuild record's
account of what ran before it reads: "Two builds of `release/v3.8.51` at `81c9b6da` (20128: `5fc47d970`; 20129:
`c3fa5a15e`) since 2026-09-29 00:42Z, and before them `a58000c7` builds." So 20128 had left `dd6e9607e` no later
than 2026-09-29 00:42Z. The receipt package for the `81c9b6da` build was never published. Main's 2026-09-28 roadmap
says OmniRoute's "gateway owner reports a rebuild of both gateways on `release/v3.8.51` `81c9b6da` in progress"
(`main:docs/decisions/2026-09-28-ecosystem-roadmap.md:51`), but this record found no published statement of the basis
for that switch. The 2026-09-30 rebuild then moved 20128 to target `2f42a9ac1` with the affinity patch `045aa81f3`,
build `ae5539a56`, switched over between 00:02:41Z and 00:03:00Z.
These are historical build statements, class `source_review` of the owner's published record, not a statement of
the current gateway build. The current build is the gateway owner's to state.[^bindings][^rebuild]

**Freeze.** Two recorded decisions were affected:

- The 2026-09-28T01:29:29Z freeze, `r02-freeze-20128`: "No routing change is applied to 20128 in that period."
  (`main:evidence/artifacts/omniroute-routing-20260928/decisions.json:29-33`).
- The 2026-09-28 apply-after-R02 condition: apply the complete occupancy patch only after the R02 scored run
  (`main:evidence/artifacts/omniroute-routing-20260928/decisions.json:36-41`).

The freeze ended **in fact** no later than 2026-09-29 00:42Z. From then 20128 ran `5fc47d970` instead of the
frozen `dd6e9607e`, so it had been restarted on another build, which the extract's 03:3xZ status had ruled out
("20128 is not restarted"). The earliest user direction the rebuild record cites is dated 2026-09-29 20:00Z, after
that switch, so this record does not attribute the switch to the user's directions.

The approved patch had two parts. The rebuild record describes `045aa81f3` only as part (i), "a reused session pin
outranks OAuth session occupancy", and records it running on 20128 in build `ae5539a56`. So the apply-after-R02
order's timing condition was broken **in fact** no later than the 2026-09-30 switch-over (00:03:00Z), with no R02
run on record. The rebuild record also says the patch was first built in the unpublished `81c9b6da` package; it
does not say whether `5fc47d970` carried it. Part (ii), binding a fresh pin to the connection actually served, is
not recorded on main as applied. While R02 stays retired, its "after R02" trigger is dormant, not void: the reopen
conditions below allow R02 to be reopened, and if a reopened R02 completes a scored run, the original after-scored-run
predicate ([decisions.json:38](https://github.com/seathatflowsinourveins/native-agent-stack/blob/ecea28654a835fff2cc3651bab77ca0e46b9bec5/evidence/artifacts/omniroute-routing-20260928/decisions.json#L38))
can occur again. Until then, part (ii) stays an open item for the patch workflow or a user decision, with its own
acceptance gates unchanged; this record neither applies nor drops it.

Main holds an earlier label that does not fit this account. PR #425, committed on main as `f6e5a0384` at
2026-09-28T22:57:18Z, calls `045aa81f3` "the 20128 build" and `dd6e9607e` "the 20129 build"; its OpenHands
isolation record, README and `host.py` carry the same labels. These are a coordinator's labels on a 2026-09-28
source read, in a repair round that made no gateway request, not an observed version read. Read as the build
running on 20128 that day, they would place both breaks no later than 2026-09-28T22:57:18Z, and they would conflict
with the rebuild record's account that 20128 ran `a58000c7` builds until 2026-09-29 00:42Z and that the patch was
first built in the `81c9b6da` package. The sources do not settle which account holds. So 2026-09-29 00:42Z and
2026-09-30 00:03:00Z are upper bounds only, and this record neither asserts nor rules out an earlier date for either
break.[^pr425][^rebuild]

The rebuild record names neither R02 nor #445. The roadmap's F-WK-3 items asking for the user's R02 freeze release
and re-derived #445 admissible values were not carried by that record. The custody notice on #445 dated the end of
the freeze to the 2026-09-30 rebuild; the dating above corrects it from the rebuild record's own account. These are
`source_review` findings from comparing the preserved decisions, the rebuild record and the roadmap; they do not
establish an explicit user release.[^freeze][^rebuild][^roadmap]

**No explicit release by the user is on record. This record neither claims nor supplies one, and it releases
nothing.** It records the historical conflict without rewriting the freeze, its ordering condition or any
pinned artifact.[^freeze]

**Failed condition.** The unmet F-WK-3 item is a recorded condition that failed, not only a historical conflict.
The roadmap's F-WK-3 gateway record "goes in the rebuild's receipt PR" and lists "the user's R02 freeze release"
(`main:docs/decisions/2026-09-28-ecosystem-roadmap.md:185-188`). The rebuild record, which replaced the unpublished
`81c9b6da` receipt package as the published account (`main:docs/decisions/2026-09-30-omniroute-rebuild.md:30-32`),
carries no release, and the freeze it overtook was recorded as holding "with no end date"
(`main:evidence/artifacts/omniroute-routing-20260928/decisions.json:33`). This assigns no fault, since the basis of
the 2026-09-29 switch is unpublished. The rule it supports: before restarting a host or switching its build, search
the decision records, evidence decisions and roadmap for freezes and ordering conditions on that host, and record
each one's release, with the user's direction, in the switch's own record; without a release, the switch waits. A
switch that has already overtaken one is recorded as overtaken in fact, with no release supplied and its open items
carried forward, as this record does for part (ii). The general-engineering row belongs in the anti-pattern log that
`main:AGENTS.md:5` names (`main:docs/harness-defaults.md:85`). That file is outside this retirement's scope, so the
row is left to a foundation follow-up that can cite this paragraph. Class: `source_review`; no check enforces the
rule yet.[^roadmap][^rebuild][^freeze]

**Owner.** Main's `decisions.json:33` recorded the run owner as inactive. The #445 timeline shows no comment or
review before the custody notice; its last commit, `bddb0072`, is dated 2026-09-28T01:28:15Z. Session 0c reports
that its 2026-10-02T23:58Z triage found no live owner; that triage is unpublished. No lane claimed R02 during the
objection window. Class: `source_review` of the historical decision and the platform records, with the triage as
the custody session's report.[^not-run][^custody][^timeline]

**Use.** The 2026-10-03 #608 coexistence records treat 20128 as a shared pool with bounded windows and separate
lane acknowledgements. Those records establish coordination, not effort or model acceptance. Class:
`source_review` of the original platform comments.[^coexistence]

## Alternatives considered

These are the retirement decision's alternatives, based on the design bindings, the later 20128 builds and
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

[^custody]: Original #445 custody notice [5967135175](https://github.com/seathatflowsinourveins/native-agent-stack/pull/445#issuecomment-5967135175) and #608 mirror [5967137495](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5967137495); post-window read-only platform and coordination observations retained in the builder handoff. Class: `source_review` / independent observation. The notice reports the unowned-PR finding, the retirement plan and the two-hour objection window. The user's 2026-10-03 custody direction is the custody session's report; neither the notice nor the mirror contains it.
[^timeline]: The #445 issue timeline, read through the GitHub REST timeline endpoint on 2026-10-03: commits through `bddb0072` (committer date 2026-09-28T01:28:15Z), a label, cross-references and, as its first comment, the custody notice at 2026-10-03T08:22:02Z; no review event. Class: independent platform observation.
[^policy]: `main:docs/acceptance-evidence-policy.md:24-33,46-61`; `main:docs/lanes.md:94-148`; repository evidence-preserving retirement precedent `main:docs/decisions/2026-09-25-retire-vela-velanext.md:32-46`. This record follows those policies and the assigned custody scope; it adds no native execution claim.
[^arms]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:12-23`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:5-18`. Class: `source_review`.
[^subset]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:87-114,181-199`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:25-38`. Class: `source_review`; private inputs were not read or rehashed.
[^rule]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:250-258`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:353-370`. Class: `source_review`.
[^statistics]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:259-295`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:374-389`. Class: `source_review`.
[^fingerprint]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:296-307,319-373`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:501-538`. Class: `source_review`; declaration and historical provenance are separate.
[^not-run]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:3-8`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:3`; `main:evidence/artifacts/omniroute-routing-20260928/decisions.json:33`; `main:blueprints/convergence-practice/omniroute-routing-20260928/experiment.json:489`. Class: `source_review` of reported run status.
[^readbacks]: `main:evidence/artifacts/omniroute-routing-20260928/decisions.json:65-74`; `main:blueprints/convergence-practice/omniroute-routing-20260928/experiment.json:114-115,376-395,494`. Class: `source_review`; the experiment calls these `native_cli_execution`, but its scope says the exits are from the coordinator's log and the outputs are private.
[^reported-history]: The [#445 PR description](https://github.com/seathatflowsinourveins/native-agent-stack/pull/445), as last edited 2026-09-28T00:47:05Z (its edit history, read on 2026-10-03, shows no later edit), body lines 15, 55, 69-70 and 77-83. It is the PR author's report of the review rounds (model, effort, heads, finding counts and the third verdict), the ninth defect and the offline-test runs. Class: `source_review` of an author report; the pinned blobs do not retain the original review or test outputs, and neither the reviews nor the tests were re-executed for this record.
[^reviews]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:665-714`; repair commit objects `f58a4a655f0b69d07cdc0454adb02f0285ee41b3`, `4b7c58de8a641e93ed0dd7fe7795a90bf379ee49`, `2c584098c7d8d3e7307be51b94f4ee738181aed0` and `af85abec7e5a121eaf2882e0e0d43078a6656460`, read without changing refs. Class: `source_review`; see the author-report boundary above.
[^sanitizer]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:168-175`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:243`. Class: `source_review`; persistence fixtures remain `synthetic`.
[^occupancy]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:581-596`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:533`. Class: `source_review` of the recorded upstream trace.
[^timeouts]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:488-491,518`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:371,374`. Class: `source_review`.
[^owner-report]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:626-632`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:374`. Class: `source_review`.
[^snapshot]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:634-636,710-712`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:245,539`. Class: `source_review`.
[^duration]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/README.md:573,623-625`; `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:206`. Class: `source_review`.
[^bindings]: `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json:7-18,319-330`. Class: `source_review`.
[^rebuild]: `main:docs/decisions/2026-09-30-omniroute-rebuild.md:3-8,30-36,43-55,125,131-136`; `main:blueprints/convergence-practice/omniroute-routing-20260928/README.md:15` for the base of `dd6e9607e`; the entire original record was checked for R02/#445 references, and main was searched for `5fc47d970`, `81c9b6da` and `045aa81f3`. For `045aa81f3`, `git log -S` over main's history lists, oldest first, `f6e5a0384` (PR #425, 2026-09-28T22:57:18Z), `0a41bf892` (PR #531, the stack manifest's omniroute row, 2026-09-30T05:27:35Z), `b4056a355` (PR #530, the rebuild record, 2026-09-30T05:39:04Z) and `cc1f6ce1f` (PR #534); the times are committer dates. Class: `source_review` of the owner's historical native-operation record; no current-build observation.
[^pr425]: `main:blueprints/runtime-workers/openhands/evidence/repair-round-commands.json:2,17,254`; `f6e5a0384c97ac40fcc21a260217257b15b333c4:docs/decisions/2026-09-28-openhands-resolver-isolation.md:281`; `main:blueprints/runtime-workers/openhands/README.md:791`; `main:blueprints/runtime-workers/openhands/host.py:79`; PR #425's squash commit `f6e5a0384c97ac40fcc21a260217257b15b333c4` on main's first-parent line. Class: `source_review` of a coordinator's labels on a source read. The repair round made no gateway or model request (`repair-round-commands.json:2,17`), so the labels are not an observed version read, and this record does not credit them as one.
[^roadmap]: `main:docs/decisions/2026-09-28-ecosystem-roadmap.md:185-189,237-238`. Class: `source_review` of requirements not carried by the rebuild record.
[^freeze]: `main:evidence/artifacts/omniroute-routing-20260928/decisions.json:29-41`; `main:blueprints/convergence-practice/omniroute-routing-20260928/README.md:103-110,163-167,192`; `main:blueprints/convergence-practice/omniroute-routing-20260928/experiment.json:489`. Class: `source_review`; the historical instructions remain unchanged.
[^coexistence]: Original #608 comments [5966185450](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5966185450), [5966191333](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5966191333), [5966225109](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5966225109) and [5966289633](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5966289633), read in full. Class: `source_review` / platform observation of coordination only.
[^retained]: `main:blueprints/convergence-practice/omniroute-routing-20260928/experiment.json:114-115,376,393`; `main:evidence/artifacts/omniroute-routing-20260928/decisions.json:67,73`; read-only `git ls-remote origin refs/heads/claude/gateway-ab-r02-prereg-20260927 refs/pull/445/head` on 2026-10-03. Class: `source_review` / independent platform observation; no ref mutation.
