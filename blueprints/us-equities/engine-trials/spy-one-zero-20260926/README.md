# SPY one_zero engine trials, 2026-09-26

Two engines replay the frozen SPY `one_zero` fixture beside the Nautilus arm of gate G-a
(`blueprints/us-equities/engine-nautilus/spy-parity`). The trial scores each engine against the
same LEAN oracle, plan, converted rows, scorer and tolerance sheet. The engines are
ml4t-backtest 0.1.12 and Lumibot 4.6.1.

- **Preregistration:** everything was fixed in [`preregistration.json`](preregistration.json)
  (commit a74ed16d) before either engine was installed. That covers the sheet, the per-arm
  manifest bindings, the scorer command, the pass definition and the failure policy.
- **Scorer:** every verdict was written by the unchanged spy-parity `compare.py` (sha256
  c70386f8…, main 5c1961e4). It used the unchanged v1 sheet `tolerances.json` (c8bc7231…) and
  each arm's own schema_version 1 manifest. It ran with `--lean-data`, so the five inputs and
  the 725 converted rows were re-hashed at scoring time.
- **Evidence class:** HIST, on bundled sample data. This trial ranks, promotes and adopts no
  engine and changes no gate status. It says nothing about `one_stress` or later cases, paper
  operation or live trading.

## Result: the 29-check v1 contract

| Arm | Engine and pin | Verdict | Pass / fail / skipped | Native end cash (oracle 90734.080) | Distribution posting | Market-on-open mechanism | Declared deviations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Nautilus v1 (dated, context) | nautilus_trader 2.0.0rc5, upstream 1b0a49d2 | BLOCKED | 25 / 4 / 0 | 90078.96 | external ledger, not posted | first-bar close proxy | none (the gate's own arm) |
| ml4t-backtest | 0.1.12, wheel 8f5dfe7c…, tag v0.1.12 = 672804b3; ml4t-specs 0.1.5 | **PASS** | 29 / 0 / 0 | 90734.0800 | engine-posted through `funding_df` at each ex-date's first bar end | NEXT_BAR market order at the next session's first bar open | D1, D2, D4 |
| Lumibot (primary) | 4.6.1, wheel d06b8feb…, tag v4.6.1 = 2dfdda10; GPL-3.0, evaluation only | **FAIL** | 23 / 6 / 0 | 91807.2000 | external ledger, not posted | GTC market order from `after_market_closes` fills at the decision instant, at the decision bar's own open | D1, D2, D3 |

Across the three rows:

- The check ids are the same 29, in the same order.
- Two cash-ledger check labels embed each arm's own event instants, so they differ between arms.
- No arm has a skipped check or a rejected attribution, and every comparison is complete, with
  converted bars as attribution evidence.

**Nautilus v1 is a dated verdict.** It was scored on 2026-09-22 by an earlier `compare.py`
(fc0ed683). The pinned `compare.py` refuses to re-score it (`local_source_sha256_mismatch`).

**Nautilus v2 is context only.** [`verdict-v2.json`](../../engine-nautilus/spy-parity/verdict-v2.json)
is PASS on 136 of 136 checks (106 execution checks plus 30 preconditions). That is a different
contract, under the sealed Nautilus v2 manifest, and was re-scored PASS at this pin on
2026-09-26. It is never compared like-for-like with the rows above.

### Failing checks

| Arm | Check | Expected | Observed | Delta | Attribution |
| --- | --- | --- | --- | --- | --- |
| Nautilus v1 | entry_fill.fill_price_usd#12 | 323.58 | 323.8700 | +0.2900 | blocked: market_on_open_proxy |
| Nautilus v1 | exit_fill.fill_price_usd#16 | 291.69 | 291.2350 | -0.4550 | blocked: market_on_open_proxy |
| Nautilus v1 | end_cash.reconciled_end_cash_usd#21 | 90734.080 | 90507.6000 | -226.4800 | blocked: market_on_open_proxy |
| Nautilus v1 | native_end_cash.native_end_cash_usd#22 | 90734.080 | 90078.96 | -655.120 | blocked: distributions_and_cash, market_on_open_proxy |
| ml4t-backtest | none | | | | |
| Lumibot | entry_fill.utc_seconds#9 | 1577977200 | 1577826000 | -151200 | unattributed |
| Lumibot | entry_fill.fill_price_usd#12 | 323.58 | 320.9400 | -2.6400 | unattributed |
| Lumibot | exit_fill.utc_seconds#13 | 1588255200 | 1588190400 | -64800 | unattributed |
| Lumibot | exit_fill.fill_price_usd#16 | 291.69 | 293.9900 | +2.3000 | unattributed |
| Lumibot | end_cash.reconciled_end_cash_usd#21 | 90734.080 | 92235.8400 | +1501.7600 | unattributed |
| Lumibot | native_end_cash.native_end_cash_usd#22 | 90734.080 | 91807.2000 | +1073.1200 | unattributed |

- **Blocking mappings.** Nautilus v1: distributions_and_cash and market_on_open_proxy.
  ml4t-backtest: none. Lumibot: none.
- **Unattributed failures.** Nautilus v1: none. ml4t-backtest: none. Lumibot: all six.
- **Rejected attributions.** None in any arm.

## Why the Lumibot primary attempt failed

The Lumibot arm reads the completed 16:00 New York decision bar in `after_market_closes`, the
hook the preregistration gives as its example. There it submits one GTC market order. The
bars are indexed at their end instant, as preregistered.

A synthetic probe run before the first attempt showed how the engine handles that order
([`lumibot/probes/hook-probe.json`](lumibot/probes/hook-probe.json)):

- When the strategy next awaits the market open, the backtesting broker processes pending
  orders at the current clock, before the clock advances.
- It prices a market order at the open of the bar indexed at that clock.
- With end-indexed bars, the bar indexed at 16:00 is the decision bar itself.

The order therefore fills at 16:00, at a price printed an hour before the decision. On the
frozen rows:

- the entry filled +304 at 320.94, the open of the 2019-12-31 15:00 row, stamped 1577826000;
- the exit filled -304 at 293.99, the open of the 2020-04-29 15:00 row, stamped 1588190400.

The oracle's market-on-open fills are 323.58 at 1577977200 and 291.69 at 1588255200. The
earlier prices raise the reconciled end cash by 1501.76, which is 304 x 2.64 on the entry plus
304 x 2.30 on the exit. Native cash also lacks the 428.64 of distributions, which the engine
does not post under this configuration.

The preregistration had predicted BLOCKED, 28 of 29, with only native_end_cash failing and
attributed to distributions_and_cash. The run falsifies that prediction on four counts:

- both fill instants are wrong;
- both fill prices are wrong;
- five further checks fail, and none of the failures can be attributed;
- three guards fail in both runs: causality, submission_clock and fill_at_next_session_first_bar.

The market_on_open_proxy row stays `resolved`, as the frozen binding requires. The finding,
the hook choice and the reasons are recorded before the attempt:

- in the port header;
- in the manifest's `market_on_open_proxy.pre_run_finding`;
- in the receipt's `pre_run_findings`;
- in [`lumibot/run.json`](lumibot/run.json).

The probes found no hook that satisfies the port contract and still fills on the next
session's first bar. The contract requires submission at or after the decision bar's end and
before the fill.

### Post-hoc variants (failure policy F5, reported beside the primary, never instead of it)

| Id | Decision hook | Verdict | Pass / fail | Failing checks | Failed guards (both runs) | Native end cash |
| --- | --- | --- | --- | --- | --- | --- |
| post-hoc-01 | `before_starting_trading` (next session, 10:00) | BLOCKED | 28 / 1 | native_end_cash -428.64, blocked by distributions_and_cash | submission_clock | 90305.4400 |
| post-hoc-02 | `before_market_opens` (next session, 09:00) | FAIL | 25 / 4 | exit_fill.utc_seconds -3600, exit_fill.fill_price_usd +2.30, end_cash +699.20, native_end_cash +270.56 | submission_clock, fill_at_next_session_first_bar, fill_price_is_open_of_bar_indexed_at_fill_instant | 91004.6400 |

**post-hoc-01** reproduces the oracle's fill instants, prices and reconciled end cash exactly.
Only the preregistered distribution gap remains, which is the predicted BLOCKED shape. It gets
there only by submitting the order at the instant it fills. The fill price is then the 09:30
open of a bar that has already completed, which the port contract excludes. It is not a pass
of the preregistered strategy.

**post-hoc-02** fills the entry on the right bar only because the 2019-12-31 to 2020-01-02 gap
exceeds the broker's one-day fill-distance guard. The exit, after an 18-hour gap, fills at
09:00 at the decision bar's open.

Both variants use the same receipt contract, scorer command, sheet and arm manifest as the
primary. Their files are `lumibot/receipt.post-hoc-NN.json` and `lumibot/verdict.post-hoc-NN.json`.

### Other pre-run findings (Lumibot)

- **Yahoo lookups.** Left unset, the strategy's `risk_free_rate` asks Yahoo for ^IRX when it
  dumps its statistics. The sandbox refused each lookup. The port passes `risk_free_rate=0.0`,
  which feeds statistics only; cash financing is off. From probe-02 onward no lookup and no
  stray home directory occurs.
- **Order identifiers.** In backtests they are sequential (`bt_<n>`), not the uuid4 the
  preregistration expected. Under the preregistered determinism rule they stay raw, and
  published files carry order ordinals only.
- **Dividends.** Hour data with a `dividend` column credits nothing either. This is consistent
  with the preregistered unsupported status.

## Predictions against outcomes

| Arm | Preregistered prediction | Outcome |
| --- | --- | --- |
| ml4t-backtest | PASS, 29 of 29 | PASS, 29 of 29; no falsifier observed |
| Lumibot | BLOCKED, 28 of 29 (native_end_cash by distributions_and_cash) | FAIL, 23 of 29; falsified by the fill instants and prices, five further failures and three guards |

## How the arms ran

| | ml4t-backtest | Lumibot |
| --- | --- | --- |
| Environment | `~/.local/share/codex-ecosystem/engine-trials-20260926/ml4t-backtest-0.1.12`, uv venv over `/usr/bin/python3.12` | `~/.local/share/codex-ecosystem/engine-trials-20260926/lumibot-4.6.1`, uv venv over `/usr/bin/python3.12` |
| Lock | `ml4t-backtest/lockcheck/ml4t.lock` e168a18f…, 15 packages, binary only | `lumibot/lockcheck/lumibot.lock` a8dce0af…, 264 packages, binary only apart from one dependency built offline, reproducibly, from its hash-checked sdist (`lumibot/lockcheck/ibapi-build/`) |
| Freeze commit (port and manifest) | 05412af4 | 681b458b |
| Primary attempt | attempt-01, 2026-09-26T05:36:10Z, 4.1 s, exit 0 | attempt-01, 2026-09-26T06:26:48Z, 6.5 s, exit 0 |
| Guards | 47, none failed | 54; causality, submission_clock and fill_at_next_session_first_bar failed in both runs |
| Two-run records | equal (byte-identical raw reports) | equal (byte-identical raw reports) |
| Largest float projection adjustment | 0 | 0.00000000001 (float noise in the engine-reported portfolio value at the exit decision; noise limit 0.000001) |
| Run record | [`ml4t-backtest/run.json`](ml4t-backtest/run.json) | [`lumibot/run.json`](lumibot/run.json) |

Each engine ran offline under the preregistered bwrap template from the spy-parity README. The
template unshares every namespace, including the network (only `lo` is visible), clears the
environment and mounts the environment, the checkout and the LEAN data read-only. It also sets
`--dev /dev` with no GPU and runs `python -I`.

Lumibot adds `LUMIBOT_DISABLE_DOTENV=1` and `LUMIBOT_CACHE_FOLDER=/tmp/lumibot-cache`. Each run
also gets its own cache subdirectory and working directory under `/out`, set by the port.
These additions are declared deviation D3.

Each port:

- runs two engine runs in fresh child processes;
- verifies the five frozen input hashes and the 725-row hash before constructing an engine;
- reads every economic value from the engine's own records;
- projects engine floats to the 0.0001 tick.

Converted rows, raw reports and logs stay in private attempt directories under
`~/.local/state/native-agent-stack/engine-trials-20260926/<arm>/`, outside every checkout.
Only their hashes are published.

## Reproduce

Run from a checkout of this branch. The placeholders are `$ENV` (the arm environment), `$REPO`
(the checkout at the arm's freeze commit), `$LEAN` (the retained LEAN `Data` root) and `$OUT`
(a fresh private directory).

```sh
# Lumibot arm (ml4t-backtest: drop the two LUMIBOT variables and use its fixture_port.py)
bwrap --unshare-all --die-with-parent --new-session --clearenv --ro-bind /usr /usr \
  --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib64 /lib64 --proc /proc --dev /dev \
  --tmpfs /tmp --ro-bind "$ENV" "$ENV" --ro-bind "$REPO" /repo --ro-bind "$LEAN" /data \
  --bind "$OUT" /out --chdir /repo --setenv LANG C.UTF-8 --setenv PATH /usr/bin:/bin \
  --setenv PYTHONDONTWRITEBYTECODE 1 --setenv OPENBLAS_NUM_THREADS 1 --setenv OMP_NUM_THREADS 1 \
  --setenv LUMIBOT_DISABLE_DOTENV 1 --setenv LUMIBOT_CACHE_FOLDER /tmp/lumibot-cache \
  "$ENV/bin/python" -I /repo/blueprints/us-equities/engine-trials/spy-one-zero-20260926/lumibot/fixture_port.py \
  --lean-data /data --out /out/port

# Scoring (repository root; standard library only)
python3 -B blueprints/us-equities/engine-nautilus/spy-parity/compare.py \
  --receipt blueprints/us-equities/engine-trials/spy-one-zero-20260926/lumibot/receipt.json \
  --manifest blueprints/us-equities/engine-trials/spy-one-zero-20260926/lumibot/mapping-manifest.json \
  --tolerances blueprints/us-equities/engine-nautilus/spy-parity/tolerances.json \
  --lean-data "$LEAN" \
  --verdict blueprints/us-equities/engine-trials/spy-one-zero-20260926/lumibot/verdict.json
```

The environment build commands, the locks and the private-output hashes are in each arm's
`run.json`. A new host must build its own environments and collect its own evidence. These
records are historical receipts for `nativestack-5975wx-20260925`, not a passed status on
another machine.

## Evidence classes and limits

- **Parity runs (HIST).** Local historical replays on retained bundled sample bytes, scored by
  the unchanged scorer. They are not unchanged upstream tests, a point-in-time dataset, a
  strategy result or any broker execution.
- **Probes (synthetic fixture).** The files under each arm's `probes/` ran the pinned engines on
  made-up bars under the same sandbox. They are not parity evidence.
- **Mechanism statements.** Engine behavior is cited from pinned documentation and pinned
  wheel source. For Lumibot the citations point to pinned locations and never quote GPL-3.0
  code; Lumibot is evaluated only, never vendored, and imported from the isolated environment.
- **Arm-specific limits.** ml4t runs the `lean` profile outside its documented daily-equity
  scope and posts distributions through an input documented for perpetual-futures funding
  (both declared). Lumibot runs PandasData with the `hour` timestep, which is not one of the
  documented raw timesteps (declared).
- **No paper step.** No broker client, adapter, endpoint or credential was constructed,
  configured, contacted or read.

## Repository checks (review round 1)

An independent review found two repository unit tests that these files fail. Each needs an
entry in a repository file outside this directory; changing the files here instead would
unbind frozen evidence. [`repository-checks.json`](repository-checks.json) gives the exact
entries and the retained results. No engine ran for this round, and no port, manifest, lock,
receipt, verdict, scorer or tolerance sheet changed.

- **Label classification.** `tests/test_blind_checkout.py` requires every string under a
  `decision` key in `blueprints/` to be classified. The 16 `mappings[*].decision` strings of the
  two arm manifests state how each arm maps a mechanism. They are data, like the spy-parity
  manifest's eight, so their sha256 values belong in `DATA_VALUE_SHA256` in
  `tools/sota-convergence/blind_checkout.py`. The strings cannot change here, because
  `compare.py` checks each manifest's sha256 against its receipts.
- **OSV inventory.** `tests/test_osv_lockfile_coverage.py` requires the three tracked locks in
  `.github/osv-scanner-lockfiles.json`, each with the `requirements.txt` parser. Once they are
  listed, the required osv-scanner job scans them. The pinned OSV-Scanner 2.6.0 found nothing in
  `ml4t.lock` or `build.lock`, and two advisories in `lumibot.lock`:
  - nltk 3.10.3, GHSA-8mgp-746c-j5xp (high), with no patched release. google-adk and
    llama-index-core require it; no trial code calls nltk.
  - setuptools 80.10.2, GHSA-h35f-9h28-mq5c (moderate), fixed in 83.0.0. It affects building a
    source distribution on macOS file systems. This environment was installed from wheels only,
    and its one source build used setuptools 84.0.0.

  The lock records the environment that ran, so it is not relocked after the run. The job
  therefore needs time-boxed ignores for the two ids, or an explicit policy decision instead.
  A scratch scan of the whole inventory with the three locks and the two ignores exited 0.
- **Evidence hash.** `manifests/evidence.json` records the inventory's sha256 and byte count,
  so listing the locks also needs that entry updated. The simulation found this third
  registration: without it, `scripts/validate.py` reports a mismatch.
- **Full suite.** On commit fee2d6d8 the CI-style suite ran 5805 tests with four failures: the
  two above, and two host-contention failures that passed when rerun. One hit the per-user
  gitleaks lock while another scan held it; the other was an exporter timing test under load.
  With the classification entries, the inventory entries and the two ignores applied in a
  scratch worktree, one test failed: it runs `scripts/validate.py`, which reported the inventory
  hash mismatch. With the `manifests/evidence.json`
  update as well, the 5805 tests ran with no failure (667 skipped) and `scripts/validate.py`
  passed. These runs simulate the coordinator's change; they are not the state of this branch.

## Files

| Path | What it is |
| --- | --- |
| `preregistration.json` | frozen plan for both arms (sheet, bindings, scorer, predictions, failure policy) |
| `ml4t-backtest/` | port, arm manifest, lock, probes and probe reports, receipt, verdict (PASS) and run record |
| `lumibot/fixture_port.py` | Lumibot port, frozen at 681b458b; header cites the pinned docs and wheel |
| `lumibot/mapping-manifest.json` | arm manifest; its projection equals `arm_manifests.lumibot.binding` |
| `lumibot/lockcheck/` | hashed uv lock, requirements input and the offline dependency build inputs |
| `lumibot/probes/` | hook probe, port mechanism probe and orchestration smoke test, with the reports from the freeze commit |
| `lumibot/receipt.json`, `lumibot/verdict.json` | primary attempt: receipt published unchanged; verdict written by compare.py (FAIL) |
| `lumibot/receipt.post-hoc-01.json`, `lumibot/verdict.post-hoc-01.json` | post-hoc `before_starting_trading` (BLOCKED) |
| `lumibot/receipt.post-hoc-02.json`, `lumibot/verdict.post-hoc-02.json` | post-hoc `before_market_opens` (FAIL) |
| `lumibot/run.json` | pins, environment build, probes, findings, every attempt, scorer runs and private-output hashes |
| `repository-checks.json` | review round 1: the two failing repository tests, the entries they need outside this directory, and the OSV-Scanner result for the three locks |

These files are not yet registered in `manifests/evidence.json`. The coordinator registers them
with sha256 and byte counts, as it registered the spy-parity files. The entries listed in
`repository-checks.json` also belong to that registration.
