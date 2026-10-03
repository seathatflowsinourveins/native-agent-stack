# October 2 paper dispositions and October 3 reconciliation

Account 2 remains permanently halted. Its October 2 pre-market trials 1 and 2 each submitted six orders and returned raw `passed` execution receipts. Trial 2 failed the frozen acceptance requirement of **no ledger halt**: lifetime gross loss reached **$481.3200 against the unchanged $480 cap**. The October 3 read-only broker observation reconciles the existing flat account; it does not qualify the strategy, clear the halt or constitute an engine recovery run.

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

Account 1's bounded `GET /v2/account` admission recheck at **2026-10-03T03:26:45.048640+00:00** again returned HTTP **401**. The coordinator observed native process exit **1**; the probe JSON itself has no exit-code field. Existing stored credentials were reused, with no rotation or remapping. The cause of authentication failure remains undetermined; this evidence does not establish revocation or a strategy no-trigger result.

## Sources and claim boundaries

The execution source remains [`native-agent-stack` at `dca821cca85dce3647fa7b488d5a23fbe5b85d4a`](https://github.com/seathatflowsinourveins/native-agent-stack/tree/dca821cca85dce3647fa7b488d5a23fbe5b85d4a). Its [`safety.py:646`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/dca821cca85dce3647fa7b488d5a23fbe5b85d4a/blueprints/us-equities/adaptive-paper/safety.py#L646) refuses another trial under a numeric halt and only clears `recovery_only`; [`safety.py:597`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/dca821cca85dce3647fa7b488d5a23fbe5b85d4a/blueprints/us-equities/adaptive-paper/safety.py#L597) preserves history during explicit recovery. [`recovery.py:260`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/dca821cca85dce3647fa7b488d5a23fbe5b85d4a/blueprints/us-equities/adaptive-paper/recovery.py#L260) requires a fresh broker proof and checks flatness/errors; the supported recovery entrypoint is [`mover_runner.py:868`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/dca821cca85dce3647fa7b488d5a23fbe5b85d4a/blueprints/us-equities/adaptive-paper/mover_runner.py#L868). That entrypoint was not run for this observation.

The installed snapshot runtime reports **alpaca-py 0.44.0**. The official [`TradingClient` source at tag `v0.44.0`, commit `cc4cb3b7ba50ae250e621983c2779047fb16bb28`](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/trading/client.py) supports the account, positions and open-order reads used here. [Alpaca authentication documentation](https://docs.alpaca.markets/us/v1.1/docs/authentication-1) supplies the authentication reference. These are supported native operations and local integration evidence, not unchanged official upstream test acceptance.

The binding October 2 freezes retain all original caps, session limits and acceptance conditions. No new root, capital increase, halt clearing, strategy qualification or current model trial is recorded. Historical source review and previously recorded offline tests are not new model or engine runs; provider usage is unmeasured here. Alpaca paper fills remain broker simulation and cannot establish exchange execution quality or live trading performance.

## Correction and verification path

Disposition summaries must distinguish the **two executed pre-market trials**, the **risk-halt refusals** and **account 1 admission failure**. Original `mover-paper.json` files and `paper.log`/`series.console` output establish the first two; all 171 runtime probe JSONs and the independent systemd journals establish HTTP 401 and process exits 3/3/5. The new snapshot output and separate SQLite read corroborate cash and flatness. The four average-invariant observations are retained as observations; the no-halt acceptance failure is independently decisive.

Public sanitization removes account references, host identity, process identifiers, credential pointers and personal paths. Selected JSON values and native log messages otherwise preserve their original values. Source hashes identify retained private bytes; hashes and repository structural validation establish consistency, not successful trading acceptance.
