# Decision: the landscape-sweep GPT-6 route is settled by the user's direction, and the Gate B preregistration draft (#488) is retired (2026-10-03)

Lane: `lane:foundation`. North-star action served: clear the obsolete foundation route-selection dependency while preserving the comparison design and independent experiment gates. The foundation/trading boundary and hash-only registration rule remain `docs/lanes.md:145-150` ([lane policy](../lanes.md)).

**Source base:** `9b0b8d6d25f9e3fb8f71770500e774170423315e`, observed as HEAD and origin/main on 2026-10-03. Every repository `path:line` below refers to that base, and each was re-verified unchanged at main `4ced2923063db6a6dcafa9f25af5ee05a4153c75`, which differs from it only by an in-place edit of `AGENTS.md` line 26 and by `manifests/evidence.json`. Explicit #488 head links refer to the preserved draft instead. The [custody notice](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488#issuecomment-5967135277) and [coordination announcement](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5967137495) define retirement and the objection window.

## Decided by

The custodian, Claude session `native-agent-stack-0c`, under the user's delegation at `docs/decisions/2026-09-28-delegated-decisions.md:3` ([delegation](2026-09-28-delegated-decisions.md)), which the roadmap applies to the Gate B criterion at `docs/decisions/2026-09-28-ecosystem-roadmap.md:311` ([roadmap](2026-09-28-ecosystem-roadmap.md)). That is one of two readings of who confirms the criterion (the last row of the table below); the route rests on the user's direction under either. This notice records what the user already settled, and the user can take it back. It does not exercise the draft's sixteen unrecorded choices ([preserved draft authority](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/PREREGISTRATION.md#L13)).

The two-hour window began at 2026-10-03T08:22:03Z and expired at 10:22:03Z. Before editing, #488's comments, the coordination folder newest first and #608's newest comments were read; no objection or ownership claim was found. The [custody notice](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488#issuecomment-5967135277) supplies the window and stop condition. Publication follows the Codex root lane's read at the reviewed head and the custodian's reviews: Opus 5.5/max evidence review, one Astra/max consequential judgment and one repair round, with the gateway runtime lane informed. Those new reviews and root consensus are **pending at preparation**; their actual results must be recorded in the successor PR before merge. An objection stops this retirement and returns it to the custodian. The [coordination announcement](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5967137495) records custody, and `AGENTS.md:38` ([instructions](../../AGENTS.md)) supplies the judgment/routing rule.

## The readings that looked conflicting

Each reading retains its own source and scope.

| Reading | Source and what it says |
| --- | --- |
| **The sweep route, by the user's direct direction** | `docs/decisions/2026-09-27-omniroute-account-pool.md:3-5` records user selection and installation on September 27; `docs/decisions/2026-09-27-omniroute-account-pool.md:304-305` separately directs the landscape sweep through `--gpt6-provider omniroute` ([account pool](2026-09-27-omniroute-account-pool.md)). |
| **Cross-family research and review** | `AGENTS.md:38` routes cross-family research, review and sweep votes through OmniRoute. `docs/decisions/2026-09-30-rule-text-every-layer.md:3` attributes the standing rule to the user's September 30 request and its final wording to the Gate A owner's ACCEPT-WITH-CHANGES review of PR #557; `docs/decisions/2026-09-30-rule-text-every-layer.md:20` states the routing clause; `docs/decisions/2026-09-30-rule-text-every-layer.md:61` names `codex -p omniroute` ([standing rule](2026-09-30-rule-text-every-layer.md)). |
| **The gateway pin** | `docs/decisions/2026-10-01-new-wsl-definitive-defaults.md:116` places the gateway row outside the combination rule; `docs/decisions/2026-10-01-new-wsl-definitive-defaults.md:390-393` quotes the user's directives and says it was "never judged blind" ([gateway row](2026-10-01-new-wsl-definitive-defaults.md)). |
| **The native-default statements** | `docs/decisions/2026-09-27-omniroute-account-pool.md:318` keeps native as the max-quality default pending a preregistered comparison. `adoption/templates/codex.omniroute.config.toml:21-22` preserves that default ([profile](../../adoption/templates/codex.omniroute.config.toml)); `tools/sota-convergence/landscape-sweep/build_args.py:621` defaults to `native` ([builder](../../tools/sota-convergence/landscape-sweep/build_args.py)); `docs/decisions/2026-09-30-task-model-routing.md:84-85` describes static assignments and the opt-in profile ([routing](2026-09-30-task-model-routing.md)). |
| **Who confirms the criterion** | `docs/decisions/2026-09-28-ecosystem-roadmap.md:311` lists the Gate B criterion among the "owner decisions made with evidence under the user's delegation". `docs/decisions/2026-09-28-ecosystem-roadmap.md:3` says the roadmap "changes no authority"; `docs/decisions/2026-09-28-ecosystem-roadmap.md:244` and `docs/decisions/2026-09-28-ecosystem-roadmap.md:252` keep "Confirm the Gate B criterion once it is drafted" under the user-only actions; and `docs/decisions/2026-09-28-delegated-decisions.md:5-8` lists the items that record decided, without Gate B. #488's draft therefore treated line 311 as "a recorded reading, not a verified grant" ([PREREGISTRATION.md L9–13](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/PREREGISTRATION.md#L9)). The route is user-directed under either reading (`docs/decisions/2026-09-27-omniroute-account-pool.md:304-305`), and the user can take this notice back. |

## Decision

**(a) Route.** The landscape sweep's GPT-6 lane runs through the OmniRoute gateway on the user's direction (`docs/decisions/2026-09-27-omniroute-account-pool.md:304-305`). The explicit command is `build_args.py --gpt6-provider omniroute --codex-host <HOST>` (`tools/sota-convergence/landscape-sweep/README.md:297-299`, [sweep recipe](../../tools/sota-convergence/landscape-sweep/README.md)). Cross-family research and review separately use the gateway under `AGENTS.md:38` and `docs/decisions/2026-09-30-rule-text-every-layer.md:20`. Their Codex command is `codex -p omniroute` (`docs/decisions/2026-09-30-rule-text-every-layer.md:61`; `adoption/templates/codex.AGENTS.template.md:14`, [Codex rule block](../../adoption/templates/codex.AGENTS.template.md)).

**(b) Defaults unchanged.** Native Codex stays the `build_args.py` CLI default (`tools/sota-convergence/landscape-sweep/build_args.py:621-624`), Codex's base-config provider, and the account-pool max-quality default for GPT-6 work outside (a). The opt-in gateway template expressly preserves that default (`adoption/templates/codex.omniroute.config.toml:21-22`); the base template and static-routing description remain as recorded (`adoption/templates/codex.config.template.toml:1-15`, [base template](../../adoption/templates/codex.config.template.toml); `docs/decisions/2026-09-30-task-model-routing.md:84-85`). Line 318 of the account-pool record remains true for that scope. This notice supersedes only the reading that the sweep's route waits for a preregistered comparison. A job's `inputs.json` records its provider (`tools/sota-convergence/landscape-sweep/README.md:341`), so a native vote stays attributable to native. The explicit gateway option still requires `--codex-host` (`tools/sota-convergence/landscape-sweep/build_args.py:679-681`); no default changes.

**(c) Gate B: settled by the user's direction, unmeasured.** The user settled the sweep route on September 27 (`docs/decisions/2026-09-27-omniroute-account-pool.md:304-305`). Cross-family research and review follow the user-requested standing rule of September 30 (`docs/decisions/2026-09-30-rule-text-every-layer.md:3`), whose routing clause is `docs/decisions/2026-09-30-rule-text-every-layer.md:20`. Per `native-agent-stack-76`, relayed at `docs/decisions/2026-09-28-ecosystem-roadmap.md:331` and **not independently verified**, the user lifted the foundation sweep hold on September 29. The measured F-WK-2 criterion (`docs/decisions/2026-09-28-ecosystem-roadmap.md:176` and `docs/decisions/2026-09-28-ecosystem-roadmap.md:180-183`) is retired as moot; item 5 (`docs/decisions/2026-09-28-ecosystem-roadmap.md:252`) needs no confirmation. The [custody notice](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488#issuecomment-5967135277) names this disposition.

M5c is not released: Gate A and M5b gate 3, the user's per-run budget, still hold it. M5b also requires unchanged upstream tests and a labelled fixture (`docs/decisions/2026-09-25-skills-trial-and-usage.md:653-664`, [skills trial](2026-09-25-skills-trial-and-usage.md); [review finding D4-M5-RELEASE](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488#issuecomment-5883455609)). The wave's trading half belongs to the trading lane; this notice changes none of its paths or verdicts (`docs/decisions/2026-09-28-ecosystem-roadmap.md:336`; `docs/lanes.md:145-150`).

The 429 marker's overturn clause names "the Gate B settlement of the GPT-6 route" across `docs/decisions/2026-09-29-sweep-429-limit-marker.md:59-60` ([marker decision](2026-09-29-sweep-429-limit-marker.md)). This settlement keeps the gateway route for which the marker was built (`docs/decisions/2026-09-29-sweep-429-limit-marker.md:7-18`), so that decision stands. Route settlement provides no evidence against its capacity handling.

**(d) Equivalence is unmeasured.** No comparison of gateway against native Codex at the same model and effort exists in the recorded evidence cited here. #488 is unrun ([draft status](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/preregistration.json#L5)); the parity sketch was not frozen and had not run (`docs/decisions/2026-09-27-omniroute-account-pool.md:313-318`). The gateway evidence used here is mechanical. The historical [Sol-max receipt](../../evidence/artifacts/omniroute-sol-max-20260930/receipt.json) names candidate build `cf6748d04c1e0dd033fb6b6effa9bbaf5ed5466b` at `evidence/artifacts/omniroute-sol-max-20260930/receipt.json:53`. Its exact C4 claim follows:

> the candidate cf6748d04c1e0dd033fb6b6effa9bbaf5ed5466b (the running build plus the PR's commit) built with upstream's scripts (build:release and build:cli-api from 2026-09-30T05:40:16Z to 2026-09-30T05:50:33Z, npm pack, check:pack-artifact exit 0), installed into a new unreferenced prefix (tarball sha256 5d31e2489d7e239c2a12b77693df7bd7992233a105381ba5930fbf3fdb00273c, BUILD_SHA cf6748d04), booted in a network-less namespace (health 200 after 4 s), passed upstream's check:pack-boot (two boots, persistence proven) and 147 of 147 targeted tests, equal to 147 of 147 on the running build's source with the same 14 files

Source: `evidence/artifacts/omniroute-sol-max-20260930/receipt.json:90`; its classes are unchanged upstream check and our integration check (`evidence/artifacts/omniroute-sol-max-20260930/receipt.json:85-89`). Its exact C7 claim follows:

> probe gate, same script before (05:59Z) and after (06:33Z), tiny requests, effort from 20128's call_logs: cx/gpt-6.1-sol with body max: requested max / upstream xhigh before, max / max after; cx/gpt-6.1-sol-max: HTTP 400 (not in the live catalog) before, 200 with upstream max after; cx/gpt-6.1-sol-xhigh: 400 before, 200 with xhigh after; the bare id gpt-6.1-sol-max (what the sharedgw node forwards): 401 before, 200 with max after; cx/gpt-6-astra-max: upstream max before and after; a request carrying the 0.157.1 User-Agent and Version header on cx/gpt-6-sol: 200, low / low before and after; a made-up id: 400 before and after; one request through sharedgw/gpt-6.1-sol-max, sent only because the bare id answered 200: 200

Source: `evidence/artifacts/omniroute-sol-max-20260930/receipt.json:115`; its classes are live model call and our integration check (`evidence/artifacts/omniroute-sol-max-20260930/receipt.json:110-114`). These are retained September 30 claims, not executions repeated here or a quality comparison. C1 pins upstream PR 15167 to `f5d8e150b79e0901fa18241c7f29bff889b87c14` (`evidence/artifacts/omniroute-sol-max-20260930/receipt.json:65`; [upstream commit](https://github.com/diegosouzapw/OmniRoute/commit/f5d8e150b79e0901fa18241c7f29bff889b87c14)).

**(e) Host scope.** This settles the workstation's 20128 pool. Other hosts follow their own gateway records, for example the separate Mac switch at `docs/decisions/2026-10-02-omniroute-mac-rebuild.md:3-16` ([Mac rebuild](2026-10-02-omniroute-mac-rebuild.md)), which explicitly leaves the workstation untouched.

## #488 retired, and its preserved facts

Retire [PR #488](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488), preserving its branch, head and both source comments. It closes only after this record's successor PR merges, as the [custody notice](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488#issuecomment-5967135277) requires. No draft file is ported.

**Identity.** Head `caea04f28d7dcd5d428155cf1a24b28423cba1ce` stays retrievable at `refs/pull/488/head`. The PR base is `c26800f3`, and its citations are pinned at `11648f9a`. It has **four files, +5510/-0 lines** ([PR identity and scope](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488)). Its JSON says **DRAFT**, with **frozen, run_started and execution_authorized all false** ([JSON L5–8](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/preregistration.json#L5)); the citation pin is at [JSON L13](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/preregistration.json#L13).

**Design, not executed behavior:**

- D1 takes `--gpt6-provider native|omniroute` form ([prose L29–33](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/PREREGISTRATION.md#L29)).
- Arm A is native Codex; arm B is OmniRoute GPT-6 on 20128 without headers; arm C is OpenHands via OmniRoute, a gated smoke check with `evidence_complete` hard-coded false ([arms L64–66](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/PREREGISTRATION.md#L64), [C's boundary L37–42](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/PREREGISTRATION.md#L37), [B L141](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/PREREGISTRATION.md#L141)).
- The harness is **promptfoo 0.123.1 `openai:codex-sdk` plus a launcher**, with bundled SDK 0.153.4, after the #381 precedent. Local integration components remain labelled separately ([harness L68–70](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/PREREGISTRATION.md#L68), [components L116–126](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/PREREGISTRATION.md#L116)). Maintained source: [promptfoo/promptfoo at 0.123.1, provider docs](https://github.com/promptfoo/promptfoo/blob/0.123.1/site/docs/providers/openai-codex-sdk.md).
- Stage 0 is **lane parity with discriminating controls**; Stage 1 is **A against B** ([Stage 0 L186–198](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/PREREGISTRATION.md#L186), [machine-readable stages](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/preregistration.json)).
- Statistics: **paired bootstrap with an exact-binomial fallback; δ = 0.05, planning n = 400, α′ = 0.035, n_max = 400**. These are recommended defaults, not a frozen sizing result ([branches L448–460](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/PREREGISTRATION.md#L448), [margin L2205](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/preregistration.json#L2205), [budget L2305](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/preregistration.json#L2305)).

### The sixteen decisions

Every id and recommended default is copied from the preserved head's [preregistration.json, `user_decisions`, L2175](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/preregistration.json#L2175). All recorded values remain `null`; this retirement records none of them.

| Number | Id | Recommended default in the preserved draft | Recorded |
| --- | --- | --- | --- |
| 1 | `confirm` | confirm after the GPT-6 and Claude reviews, one repair round and one objection round with live peers | `null` |
| 2 | `accountable_owner` | native-agent-stack-2d: it operates no arm, holds Gate A as the peer stated and stages the wave | `null` |
| 3 | `margin_and_sizing` | δ = 0.05, n by the frozen sizing rule (planning n = 400, α′ = 0.035) | `null` |
| 4 | `gate_a_order` | the seal waits for Gate A's recorded pass | `null` |
| 5 | `family_f2` | off | `null` |
| 6 | `detailed_logging` | yes, bodies private under the gateway owner's retention rule | `null` |
| 7 | `exclusive_window` | not required while decision 6 is yes | `null` |
| 8 | `g5_blocking` | not applied in this cohort | `null` |
| 9 | `parity_run` | yes for Stage 0 native or Stage 1 inferior on a complete, valid run; no otherwise | `null` |
| 10 | `sweep_direction` | accept the reversal for the wave | `null` |
| 11 | `capacity_use` | no | `null` |
| 12 | `budget` | pilot, Stage 0 and Stage 1 at the sized n, with n_max = 400; stop A at the reserve the owner sets | `null` |
| 13 | `exploratory_425` | allowed on a different SWE-bench row, never acceptance | `null` |
| 14 | `hosts` | this workstation only | `null` |
| 15 | `untested_native` | yes: the wave may start on the native lane, labelled untested | `null` |
| 16 | `mcp_reach` | record and report; D1 is still decided | `null` |

### The GPT-6 review

[Comment 5883455609](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488#issuecomment-5883455609) records **gpt-6-astra at max, Codex CLI 0.157.1**, read-only through `codex_call.sh`, from **2026-09-29T03:51Z to 04:06Z**, overall **changes-needed**. All eighteen findings follow; verdicts and severities are preserved, with reasons paraphrased from that comment.

| Finding id | Verdict | Severity | One-line reason |
| --- | --- | --- | --- |
| D1-TIMEBOX | refute | high | Expiration with an outstanding INCOMPLETE condition selects conflicting consumer outcomes. |
| D2-NONDEFAULT-DECISIONS | refute | high | Non-default direction and capacity choices leave consumer actions undefined or contradictory. |
| D3-LOGGING-FALLBACK | refute | high | Logging-off cannot satisfy mandatory Stage 0 and sealing prerequisites. |
| D4-M5-RELEASE | amend | medium | Clearing the route dependency does not clear M5b's budget, tests and fixture or M5c's Gate A dependency. |
| D5-DRAFT-AUTHORITY | confirm | info | Owner assignment, confirmation and freeze are unrecorded; choices and execution flags retain draft status. |
| S1-ARITHMETIC | confirm | info | The reviewer reproduced the unchanged appendix byte for byte, including sizes and the exact harm bound. |
| S2-DEGENERACY-PREDICATE | amend | high | The one-sided bootstrap's intentional infinite endpoint conflicts with the literal nonfinite-interval fallback. |
| S3-HOLM-CALIBRATION | refute | high | Optional Holm bypasses the calibrated bootstrap threshold without a combined rule. |
| S4-N40-IMPOSSIBILITY | refute | low | An exact-fallback counterexample disproves the claim that n = 40 cannot yield non-inferiority. |
| S5-M2-POWER | amend | medium | Quoted M2 powers use an uncalibrated table rather than the selected α′ = 0.035 procedure. |
| A1-ARMS-AND-RUNNERS | confirm | info | Arms and promptfoo/launcher precedent match main; missing implementations remain pre-seal work. |
| C1-JSON-F2-OMISSION | amend | medium | JSON omits the prose's frozen-revision question requirement and minimum 15% negative answers. |
| C2-CONTRACT-TEST-COVERAGE | refute | medium | Five mutations of load-bearing values still pass all ten tests, disproving the broad coverage claim. |
| R1-OPENHANDS-EXIT-CITATION | amend | low | The full function also returns 3 and 1; the broad otherwise-2 statement is unsupported. |
| R2-G5-INFERENCE | amend | medium | Model-owner listings do not establish G5 refusal without blocking-state observations. |
| R3-LOGGING-NONINTERFERENCE | amend | low | The logging README does not prove that toggling logging leaves upstream requests unchanged. |
| E1-FINGERPRINT-GUARANTEE | refute | high | Before/after fingerprints miss request-changing mutations reverted within the block. |
| E2-EVIDENCE-BOUNDARIES | confirm | info | Structural, synthetic, integration and historical evidence are separated; no live acceptance is claimed. |

S1 confirmed sizes **155, 39, 197 and 50** and the all-concordant n = 400 bound **0.0091798**. The review confirmed **159 citations, 170 ranges across 33 files**, at **c26800f3**. Those are the reviewer's September 29 confirmations, not a reproduction run here. Its disposition says none of the findings had been repaired ([full review](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488#issuecomment-5883455609)).

The comment cites the [SciPy bootstrap documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html) and the [statsmodels multipletests documentation](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html), and reproduced with SciPy 1.18.1 and statsmodels 0.15.0. The pinned source links, [SciPy v1.18.1 `scipy/stats/_resampling.py`](https://github.com/scipy/scipy/blob/v1.18.1/scipy/stats/_resampling.py) and [statsmodels v0.15.0 `statsmodels/stats/multitest.py`](https://github.com/statsmodels/statsmodels/blob/v0.15.0/statsmodels/stats/multitest.py), are added here. They explain the reviewed branches, not route equivalence.

### The foundation-lane input

[Comment 5894667242](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488#issuecomment-5894667242), from `native-agent-stack-76`, expressly supplies input, not an acknowledgement or route verdict.

1. **A body-less 429 is a capacity outcome.** Codex `rust-v0.157.1` sets `retry_429: false` in [model-provider-info L442–448](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/model-provider-info/src/lib.rs#L442); [api_bridge L159–207](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/codex-api/src/api_bridge.rs#L159) maps a 429 without a recognized usage/quota body to `RetryLimitReachedError`. The report does not distinguish pool exhaustion from a brief limit. Main records this at `docs/decisions/2026-09-29-sweep-429-limit-marker.md:20-34`.
2. **On September 29, 43 of 52 gateway sweep jobs completed; nine failed with body-less 429s.** The comment records the wrapper copy check matching on all 43. Median 677 seconds and maximum 977 seconds describe 44 completed jobs including one probe. Main sources: `evidence/artifacts/landscape-sweep-20260929-attempts/gpt6-job-outcomes.json:19-32` and `evidence/artifacts/landscape-sweep-20260929-attempts/gpt6-job-outcomes.json:148-152` ([outcomes](../../evidence/artifacts/landscape-sweep-20260929-attempts/gpt6-job-outcomes.json)); the copy check comes from [the comment](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488#issuecomment-5894667242).
3. **The run cost $425.12 at Claude list price.** Advisor inference inside workers was $101.14; Sonnet wrappers of GPT-6 jobs were $27.06. Both are within the total, not added on top. GPT-6 tokens are Codex usage, excluded from those dollars. Main sources: `evidence/artifacts/landscape-sweep-20260929-attempts/spend-scan-wf_08a5b367-311.json:10-22` and `evidence/artifacts/landscape-sweep-20260929-attempts/spend-scan-wf_08a5b367-311.json:522` ([spend receipt](../../evidence/artifacts/landscape-sweep-20260929-attempts/spend-scan-wf_08a5b367-311.json)), and [the comment](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488#issuecomment-5894667242). This is a retained list-price proxy, not backend billing or a new run.

## Alternatives considered

- **Land after repair:** rejected. A gate choosing native against gateway contradicts (a). The draft pins predate Sol-primary routing and the September 30 rebuild, so repair is a redesign ([pins L112–114](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/PREREGISTRATION.md#L112); `AGENTS.md:38`; `evidence/artifacts/omniroute-sol-max-20260930/receipt.json:53`). Merging sixteen null decisions still decides nothing ([preserved JSON](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/preregistration.json#L2175)).
- **Port it:** rejected because its head remains retrievable; the [custody notice](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488#issuecomment-5967135277) keeps it as the overturn-comparison design.
- **Ask the user:** rejected. The user already directed the route (`docs/decisions/2026-09-27-omniroute-account-pool.md:304-305`), and that holds under either reading of who confirms the criterion (the last row of the readings table). `docs/decisions/2026-09-28-ecosystem-roadmap.md:311` records it as an owner decision under the delegation; `docs/decisions/2026-09-28-ecosystem-roadmap.md:3`, `docs/decisions/2026-09-28-ecosystem-roadmap.md:252` and `docs/decisions/2026-09-28-delegated-decisions.md:5-8` support keeping it user-only, as #488's draft noted ([PREREGISTRATION.md L9–13](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/PREREGISTRATION.md#L9)). The user can take this notice back.

## Overturn

1. **A successor preregistration finds the gateway inferior by more than its margin.** Build from #488's preserved design, refreshed to **gpt-6.1-sol at max**, current Codex, promptfoo and gateway pins, and citations at then-current main. Fix all six high findings before freeze: **D1-TIMEBOX, D2-NONDEFAULT-DECISIONS, D3-LOGGING-FALLBACK, S2-DEGENERACY-PREDICATE, S3-HOLM-CALIBRATION and E1-FINGERPRINT-GUARANTEE**. Review it cross-family and freeze it before its run. Sources: [changes-needed review](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488#issuecomment-5883455609), [custody scope](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488#issuecomment-5967135277), `AGENTS.md:38`. This is a reopening condition, not run authorization.
2. **A new direction from the user**, whose direct sweep selection is at `docs/decisions/2026-09-27-omniroute-account-pool.md:304-305`.
3. **A gateway change alters model, effort or tools on the wire**, as the 3.8.50 effort cap did (`adoption/templates/codex.omniroute.config.toml:15-20`).
4. **A sweep or review defect attributable to the gateway.** The account-pool record's existing comparison overturn limits the gateway to framework traffic if a comparison favours native (`docs/decisions/2026-09-27-omniroute-account-pool.md:476-477`). Attribution requires evidence; unrelated capacity failure alone is not a quality finding ([foundation input](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488#issuecomment-5894667242)).

## Limitations

- **Equivalence is unmeasured:** #488 is unrun and the parity sketch was unfrozen/unrun ([#488](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488); `docs/decisions/2026-09-27-omniroute-account-pool.md:313-318`).
- **Capacity coupling:** body-less 429s and the pool's limits remain; historical failures say nothing about current capacity (`evidence/artifacts/landscape-sweep-20260929-attempts/gpt6-job-outcomes.json:19-32`; `docs/decisions/2026-09-29-sweep-429-limit-marker.md:32-34`).
- **No code or default changes:** the notice stays within [custody scope](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488#issuecomment-5967135277); CLI native and explicit-host requirements stay at `tools/sota-convergence/landscape-sweep/build_args.py:621-624` and `tools/sota-convergence/landscape-sweep/build_args.py:679-681`.
- **The September 29 arithmetic reproduction is the reviewer's, not rerun here** ([S1 and overall review](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488#issuecomment-5883455609)).
- **New reviews and peer consensus are pending at preparation**, to be recorded at the reviewed successor head before merge ([custody announcement](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5967137495); `AGENTS.md:38`).

## Records that name Gate B

The read-only inventory `git grep -n "Gate B" origin/main -- . ':!manifests/evidence.json'` at the stated base returned **24 references**. Historical text and receipts stay intact. Each row has its own base locator; only the roadmap/account-pool appends accompany the new notice.

| Base path:line | How this settlement bears on it |
| --- | --- |
| `docs/decisions/2026-09-25-skills-trial-and-usage.md:517` | Answer the settled-route dependency by user direction, unmeasured; retain other restrictions. |
| `docs/decisions/2026-09-25-skills-trial-and-usage.md:664` | Clear only route selection; Gate A and M5b's budget/tests/fixture still constrain M5c. |
| `docs/decisions/2026-09-25-skills-trial-and-usage.md:770` | Preserve the historical pending row and missing fixture; no M5c release. |
| `docs/decisions/2026-09-28-ecosystem-roadmap.md:25` | Preserve the September 27 hold; the later foundation-only release remains an unverified peer relay. |
| `docs/decisions/2026-09-28-ecosystem-roadmap.md:43` | Retire the proposed criterion; preserve #488 for a successor comparison. |
| `docs/decisions/2026-09-28-ecosystem-roadmap.md:53` | Preserve this architecture snapshot; no runtime-worker acceptance follows. |
| `docs/decisions/2026-09-28-ecosystem-roadmap.md:176` | F-WK-2 is retired as moot. |
| `docs/decisions/2026-09-28-ecosystem-roadmap.md:180` | No new three-arm criterion or confirmation is needed to notice the directed route. |
| `docs/decisions/2026-09-28-ecosystem-roadmap.md:202` | S3 already has no Gate B dependency; no change follows. |
| `docs/decisions/2026-09-28-ecosystem-roadmap.md:210` | Answer route selection without asserting a measurement or granting wave execution. |
| `docs/decisions/2026-09-28-ecosystem-roadmap.md:239` | The obsolete criterion supplies no hold; no worker acceptance or edits to #426–#428 follow. |
| `docs/decisions/2026-09-28-ecosystem-roadmap.md:252` | Item 5 needs no further confirmation. |
| `docs/decisions/2026-09-28-ecosystem-roadmap.md:275` | Preserve the dated hold rationale; foundation release is separately relayed at line 331. |
| `docs/decisions/2026-09-28-ecosystem-roadmap.md:283` | Gate A failure remains an independent constraint; the route notice does not repair it. |
| `docs/decisions/2026-09-28-ecosystem-roadmap.md:284` | No runtime-worker run becomes a prerequisite for this notice. |
| `docs/decisions/2026-09-28-ecosystem-roadmap.md:295` | Preserve the old drafting offer; retain #488's design rather than repair it now. |
| `docs/decisions/2026-09-28-ecosystem-roadmap.md:311` | One of two readings of who confirms the criterion (readings table); notice the user's direct choice, which holds under either. |
| `docs/decisions/2026-09-28-ecosystem-roadmap.md:312` | Answer only the route dependency; Gate A and the foundation authorization retain their provenance. |
| `docs/decisions/2026-09-29-sonnet-5-5-dispatch.md:154` | No stage-model or harness-test pin changes; answer the route dependency. |
| `docs/decisions/2026-09-29-sonnet-5-5-dispatch.md:198` | Preserve the dated wave hold; no new stage execution is supplied. |
| `docs/decisions/2026-09-29-sweep-429-limit-marker.md:60` | Answer the settlement overturn clause while retaining the gateway route and marker decision. |
| `evidence/artifacts/cloudflare-audit-skill-trial-20260927/README.md:146` | Historical receipt stays unchanged; no M5c qualification or release. |
| `evidence/artifacts/security-audit-host-install-20260928/README.md:43` | Preserve the dated budget/gate statement; Gate A and user-set per-run budget remain independent. |
| `evidence/artifacts/security-audit-host-install-20260928/receipt.json:131` | Preserve the historical gate-3 observation, without rewriting it as current acceptance. |

Completeness check covers both directives, native defaults, all sixteen null choices and eighteen findings, foundation input, host scope and every base Gate B occurrence. Remaining gaps feed the coordinator's next sweep: a successor quality comparison, current capacity/wire identity, and independent M5/worker qualifications. No new convergence measurement is asserted (`docs/acceptance-evidence-policy.md:24-40`, [evidence policy](../acceptance-evidence-policy.md)).
