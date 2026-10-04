# October 2 paper dispositions and October 3 reconciliation

The original Account 2 ledger and lineage remain permanently halted. Its October 2 pre-market trials 1 and 2 each submitted six orders and returned raw `passed` execution receipts. Trial 2 failed the frozen acceptance requirement of **no ledger halt**: lifetime gross loss reached **$481.3200 against the unchanged $480 cap**. The October 3 read-only broker observation reconciles the existing flat account; it does not qualify the strategy, clear the halt or constitute an engine recovery run.

| Original operation | Actual result | Frozen disposition |
| --- | --- | --- |
| `pre-20261002-1`, account 2 | Paper exit 0; raw `passed`; six orders; flat; cash/positions match; no halt | Recorded execution criteria satisfied; strategy qualification remains unestablished |
| `pre-20261002-2`, account 2 | Paper exit 0; raw `passed`; six orders; flat; cash/positions match; `gross_loss_cap_reached` | **Failed**: no-halt criterion; four recorded average-invariant mismatches retained without asserting a defect |
| `pre-20261002-3`, account 2 | Paper exit 2; `not_started`; zero orders; `next_trial_cannot_clear_risk_halt` | Refused; pre-market series process exit **3** |
| `ext-20261002-1`, account 2 | Paper exit 2; `not_started`; zero orders; same risk-halt refusal | Refused; after-hours series process exit **3** |
| `rth-20261002`, account 1 | 171 runtime admission probes returned HTTP **401**; zero trials; series process exit **5** | Admission failed; trigger behavior was not exercised |

[receipt.json](receipt.json) retains selected original outcome fields, native returned output, exact private source hashes, process-journal terminal messages and independent read-only ledger observations. The original failed and inconclusive artifacts remain private and unchanged. Raw outcome statuses are preserved alongside the acceptance verdicts.

## Fresh read-only observations

On **2026-10-03 UTC**, account 2's native SDK snapshot exited **0**: `ACTIVE`, zero positions, zero open orders and cash/equity **$99,734.61**. Independently reading the original SQLite ledger with `mode=ro` and its trial metadata gives **$99,926.34 − $191.73 = $99,734.61**, with zero cash difference. The five booked fee rows total **−$0.64** and are already included in the cash delta. Zero-quantity position rows are excluded when counting holdings. The account lock was held for the observation; the original root and halt were retained, with zero submitted orders. The coordinator recorded the observation date; the snapshot CLI printed no timestamp.

Account 1's bounded `GET /v2/account` admission recheck at **2026-10-03T03:26:45.048640+00:00** again returned HTTP **401**. The coordinator observed native process exit **1**; the probe JSON itself has no exit-code field. For that admission recheck only, existing stored credentials were reused, with no rotation or remapping. The cause of authentication failure remains undetermined; this evidence does not establish revocation or a strategy no-trigger result.

## Sources and claim boundaries

The execution source remains [`native-agent-stack` at `dca821cca85dce3647fa7b488d5a23fbe5b85d4a`](https://github.com/seathatflowsinourveins/native-agent-stack/tree/dca821cca85dce3647fa7b488d5a23fbe5b85d4a). Its [`safety.py:646`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/dca821cca85dce3647fa7b488d5a23fbe5b85d4a/blueprints/us-equities/adaptive-paper/safety.py#L646) refuses another trial under a numeric halt and only clears `recovery_only`; [`safety.py:597`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/dca821cca85dce3647fa7b488d5a23fbe5b85d4a/blueprints/us-equities/adaptive-paper/safety.py#L597) preserves history during explicit recovery. [`recovery.py:260`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/dca821cca85dce3647fa7b488d5a23fbe5b85d4a/blueprints/us-equities/adaptive-paper/recovery.py#L260) requires a fresh broker proof and checks flatness/errors; the supported recovery entrypoint is [`mover_runner.py:868`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/dca821cca85dce3647fa7b488d5a23fbe5b85d4a/blueprints/us-equities/adaptive-paper/mover_runner.py#L868). That entrypoint was not run for this observation.

The installed snapshot runtime reports **alpaca-py 0.44.0**. The official [`TradingClient` source at tag `v0.44.0`, commit `cc4cb3b7ba50ae250e621983c2779047fb16bb28`](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/trading/client.py) supports the account, positions and open-order reads used here. [Alpaca authentication documentation](https://docs.alpaca.markets/us/v1.1/docs/authentication-1) supplies the authentication reference. These are supported native operations and local integration evidence, not unchanged official upstream test acceptance.

The binding October 2 freezes retain all original caps, session limits and acceptance conditions. This reconciliation created no new root and cleared no halt in the original Account 2 ledger and lineage; it records no capital increase for that lineage, strategy qualification or current model trial. Historical source review and previously recorded offline tests are not new model or engine runs; provider usage is unmeasured here. Alpaca paper fills remain broker simulation and cannot establish exchange execution quality or live trading performance.

## Correction and verification path

Disposition summaries must distinguish the **two executed pre-market trials**, the **risk-halt refusals** and **account 1 admission failure**. Original `mover-paper.json` files and `paper.log`/`series.console` output establish the first two; all 171 runtime probe JSONs and the independent systemd journals establish HTTP 401 and process exits 3/3/5. The new snapshot output and separate SQLite read corroborate cash and flatness. The four average-invariant observations are retained as observations; the no-halt acceptance failure is independently decisive.

Public sanitization removes account references, host identity, process identifiers, credential pointers and personal paths. Selected JSON values and native log messages otherwise preserve their original values. Both SDK helper snapshots are **Local integration checks** retaining native operation output. The separate SQLite read and process-journal reads are **Independent observations**. Source hashes identify retained private bytes; hashes and repository checks are **Structural validation** of consistency, not successful trading acceptance.

## Follow-up: October 3 readmission and October 5 scheduling

A later retained account 1 paper admission probe returned HTTP **200** at **2026-10-03T04:06:07.156554+00:00**, with native `x-ratelimit-limit: 200`. The HTTP 200 followed a user credential store through the secure terminal; the probe filename records session launch at **2026-10-03T04:05:05Z**, not an exact credential-store completion time. The original 171 HTTP 401 probes and the 03:26:45 recheck remain recorded above. The probe timestamp does not timestamp the subsequent SDK snapshot.

The first frozen snapshot invocation failed during import with **`ModuleNotFoundError: No module named 'collect'`**, process exit **1**, and **zero broker requests**. Its failure receipt was retained. A separate correction freeze authorized one invocation with the source directory expected by the unchanged helper. That corrected read-only SIP snapshot exited **0** on **2026-10-03 UTC**: the identity matched original account 1 and differed from account 2; the account was `ACTIVE`, not blocked, with zero positions, zero open orders and `sip_snapshot: 'ok'`. The snapshot printed no exact timestamp. The [receipt follow-up](receipt.json) preserves its native output with only the account reference removed.

The frozen scope contained **four logical SDK calls**, a **120-second process bound**, and at most **16 HTTP attempts under the SDK's default retries**. These are bounds, not measured request or retry counts; actual HTTP attempts and usage remain unknown. The retry reference is the official alpaca-py `v0.44.0` source at `cc4cb3b7ba50ae250e621983c2779047fb16bb28`: [`common/constants.py`](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/common/constants.py) and [`common/rest.py`](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/common/rest.py).

Native RTH timer enable and show commands both exited **0**, returning `UnitFileState=enabled`, `ActiveState=active` and `NextElapseUSecRealtime=Mon 2026-10-05 10:00:05 EDT`. The retained follow-up is dated **2026-10-03 UTC**; that date does not timestamp the original enable/show commands. Their argv and exact observation time were not supplied with this repair and remain explicitly unknown in the receipt. The retained Monday index records the following schedule; the RTH entry is also supported by that native observation.

| Monday, October 5, EDT | Retained scheduled unit | Recorded condition |
| --- | --- | --- |
| 06:45:05 | `paper-recover-a2-gate-20261005` | Account 2 old-lineage recovery gate |
| 07:00:05 | `paper-pre-20261005` | Requires the dated native recovery gate |
| 10:00:05 | `paper-rth-20261005` | Enabled after account 1 readmission |
| 16:00:05 | `paper-ext-20261005` | Requires terminal, unhalted successor state |

The Monday index records all four timers as enabled and active. The permanent numerical halt remains on the original Account 2 ledger and lineage. The recovery gate and successor lineage come only from the retained `SERIES-INDEX-20261005.md`, bound by SHA256 `34d206820c0032ca7cb0c3fd8488c552a2c16c36ffbf4f13b327908c52b535a1`; neither was performed or verified here. Successor-root existence, the freeze authorizing that successor and its caps are out of scope. **No Monday orders or execution results are recorded here.** Account 1 readmission establishes the observed identity, flatness and SIP admission only. The assembled receipt and both helper snapshots are Local integration checks retaining native operation output, and do not constitute unchanged upstream test acceptance or promote paper or strategy qualification.
