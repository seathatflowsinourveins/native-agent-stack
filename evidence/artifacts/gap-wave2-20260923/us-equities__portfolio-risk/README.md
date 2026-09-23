# us-equities / portfolio-risk: gap wave 2 (2026-09-23)

The gap list came from the crosswalk at main 92bb279 (PR #85). This unit started from
base 41d39b3 on branch `claude/g2-portfolio-risk-20260923`. All receipt
preregistrations were written at 2026-09-23T06:32:44Z and committed in acfccf2, before any
check's measurement ran. Environment setup came first: venv-lock (06:30:05Z), venv-nautilus (06:30:13Z), the gap 1
lock compile and hash-locked venv-libs sync (06:30:20Z-06:30:26Z, the first step of gap 1's next_check, with the
network downloads listed below) and the skfolio clone (06:30:31Z). Those times come from file birth and modify times
([raw/setup/setup-timeline.txt](raw/setup/setup-timeline.txt)). The creation commands of venv-lock and venv-nautilus
were not retained; their package sets equal the research-evaluation lock and the accepted Nautilus 2.0.0rc5 install
([raw/setup/package-set-comparison.txt](raw/setup/package-set-comparison.txt)). The gap 4 dividend addendum is a late preregistration, written at 06:48:07Z. It is
labelled as late in its receipt. Fix-round addenda (07:12:07Z, 07:22:02Z, after the first Opus review 07:31:52Z for gaps 1 and 4, after the second Opus review 16:01:45Z for gaps 11 and 14, committed in 21899c4, and 16:33:32Z for the Codex-review reruns, committed in 81e1c86) were each written before their runs. `results.json` is generated from the receipts by
[`finish_receipts.py`](../../../../blueprints/gap-wave2-20260923/us-equities__portfolio-risk/finish_receipts.py).

| Gap | Outcome | What was run |
| ---: | --- | --- |
| 0 | settled | skfolio 1.2.9 `CombinatorialPurgedCV` produced 45 splits and 9 paths. It ran with `MeanRisk` over explicit `EmpiricalPrior` priors, one with `LedoitWolf` and one with `ShrunkCovariance`. |
| 1 | settled | A hash-locked venv held cvxportfolio 1.5.1, empyrical-reloaded 0.5.12 and quantstats 0.0.81. Each library ran on the frozen returns and exited 0. In fix round 3 the committed runner reproduced all three outputs byte for byte. The venv was created before the preregistration (see above), and the NoCash constraint deviation is disclosed; the settled criteria depend on neither. |
| 2 | settled | The installed `_walk_forward.py`, the receipt value and `git show c99fcf71` (tag v1.2.9) all hash to `f85cbe8b…`. A negative-control revision differs. The result is now also recorded in the original research-evaluation receipt (`later_checks`), which links this receipt. |
| 3 | advanced | evaluate.py was re-run. All 26 run-1 scoring artifacts reproduce the retained hashes; freeze and results needed the retained timestamp substituted. They are now committed. Remaining: 4 setup logs with no recorded command, and the unknown input of the initial compile. |
| 4 | advanced | Native Nautilus 2.0.0rc5 ran the fold weights with `FixedFeeModel`. Cash, fills, fees, decisions and P&L reconcile exactly, and the mutation and fee self-tests are all detected. A second arm vendored the peer's `DistributionModule` unchanged, and its dividend cash reconciles too. That arm's 12 mutation self-tests and fee perturbation were added in fix round 3 and were all detected. Remaining: financing and liquidity/fill realism. |
| 5 | advanced | A new window (2012-10-01..2013-09-30) was frozen, then scored once. Every candidate completed 49 episodes. The predeclared paired t-test gave p=0.979, so no difference is shown. Remaining: the scoring used a new driver around evaluate.py's functions rather than evaluate.py itself. |
| 6 | advanced | RiskEngine denied an oversized order for notional (45000 USD limit) and burst orders for rate (4/s), and the control arm filled both. Positions reconcile. Reconciliation against broker-reported fills remains, in the peer's paper lane. |
| 7 | covered_elsewhere | `sota-refresh-20260923/pins-runtime/skfolio.json` (#87) covers the 1.3.0 rerun. A hash-locked install and the README tag update remain with that lane. |
| 9 | advanced | One preregistered matched run covered skfolio and cvxportfolio minimum variance on the same folds and 20bp cost. The series were scored by skfolio.measures, empyrical-reloaded and quantstats. A later rerun reproduced the output byte for byte. Remaining: an unread scratch dry run broke the preregistered single-execution condition. |
| 10 | settled | MeanRisk and HRP P&L reconciled in native Nautilus, reported beside skfolio's descriptive returns with a decomposition. |
| 11 | advanced | The 905 invested episodes of four candidates ran in native Nautilus (the cash candidate's 260 episodes have no orders and skip the engine) in three cases: fixed fee, fixed fee with one-tick slippage, and per-share fee. They were compared with the 20bp proxy; the native effective cost was about 0.2–1.2 bp. In fix round 4 the fixed-fee case also ran with native dividend credits (vendored peer `DistributionModule`). Every fill, emission and cash transition reconciled, all mutations were detected, and the credited cash equals the cent-rounded estimate exactly. Remaining: a financing model, and realistic fills and liquidity. |
| 14 | advanced | Fix round 4 ran the LEAN arm. Native LEAN 985ef30 replayed the gap 4/10 weight schedule in a Bubblewrap sandbox, with a 1 USD fee and a declared close-fill model. Its fills, decisions, cash sequence, fees and ending cash equal the native Nautilus reports exactly for both optimizers, both without dividends and with them (LEAN native dividends versus the peer `DistributionModule`). A fee-2 control and every mutation were detected. Remaining: Alpaca paper orders with RiskEngine limits and broker-fill reconciliation. That lane is owned by peer sota-workflow-resolution, which is the blocker. |

Isolation: the venvs, clones and scratch runs are under `$HOME/.cache/gap-wave2-20260923/portfolio-risk/`.
Library runs used a temporary HOME. The fix-round-4 LEAN runs used the existing Bubblewrap sandbox (no network namespace access, read-only engine, SDK and data, empty environment) and downloaded nothing. There was no broker contact, credential read, service
change or paid API use. Network downloads were the skfolio partial git clone (820 KB) and
four wheels (scs 41.2 MiB, curl-cffi 12.9 MiB, highspy 4.8 MiB, cvxpy 4.2 MiB). Raw outputs
are under `raw/`, with host paths replaced by `$HOME`. Every receipt lists its raw artifacts
with sha256. Compressed outputs were decompressed and engine event UUIDs were redacted
for publication; [raw/REDACTIONS.json](raw/REDACTIONS.json) records every pre- and post-change hash.

Independent review: two read-only Codex calls (gpt-6-astra) reviewed this work.
[Round 1](raw/review/codex-review-round1.md) raised 8 major and 3 minor findings.
[Round 2](raw/review/codex-review-round2.md) confirmed most fixes but left two major findings open. First, fill times
were checked by date only, which is now fixed with exact times in fix round 2. Second, gap 9's single-run condition was
broken, so gap 9 is now advanced. It also left open one minor finding: the runner label was kept, and the receipt
carries the correction. Each receipt's `independent_review` field states the resolution. An independent Opus review then raised 1 major and 5
minor findings ([record](raw/review/opus-review-round3.json)), which fix round 3 resolved: the dividend runner got mutation and
fee self-tests and was rerun, gap 1 was reproduced with the committed runner, gap 5 moved to advanced, and gaps 11 and 14 were
relabelled. A second independent Opus review raised 1 major and 5 minor findings ([record](raw/review/opus-review-round4.json)).
Fix round 4 resolved them: it ran the gap 14 LEAN arm and the gap 11 dividend episodes, recorded the setup order and venv
provenance for gap 1 and moved its checked_at, linked gap 2's result from the original receipt, and relabelled gap 9
local_integration. The Nautilus outputs in `raw/` come from fix round 2 (07:22Z), except the dividend arm, which comes from fix round 3
(07:32Z), and the fix-round-4 dividend episodes (review rerun at 16:34Z; the first run at 16:07Z is kept as history).
A bounded read-only Codex review of fix round 4 ([record](raw/review/codex-review-round4.md)) raised two P2 findings and one P3 finding.
First, a broken fee-2 control could have counted as a detection. Second, the dividend episodes compared balances but not
timestamps. Third, the receipt misstated the hashed input count. Preregistered review reruns (16:33:32Z, 81e1c86) fixed all three
with identical economics. The gap 4 receipt now names the LEAN comparison as its timestamp evidence. Economic results are identical across rounds. Round-1 outputs are in git at b482b86, fix-round-1 outputs at
8bab001 and the fix-round-2 dividend outputs at dbcfef1.
