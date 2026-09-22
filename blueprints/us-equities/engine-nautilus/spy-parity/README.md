# SPY/LEAN parity replay (gate G-a, case `one_zero`)

This harness reproduces the frozen `one_zero` scenario of the
[SPY stress plan](../../historical-simulation/plan.json) on native
**NautilusTrader 2.0.0rc5** and compares it against the dated LEAN receipt
`native-historical-leverage-stress-20260919`. It exists to answer one question
with measured evidence: which parts of the LEAN result the pinned Nautilus
engine can express, and which it cannot.

It is **evidence class `HIST`**: a local historical replay over retained bundled
sample bytes. It is not an unchanged upstream test, not a point-in-time or
market-wide dataset, not a strategy result, and not broker execution.

The current verdict is **BLOCKED**, not pass. See
[`verdict.json`](verdict.json) and the unsupported rows in
[`mapping-manifest.json`](mapping-manifest.json).

## Files

| File | Purpose |
| --- | --- |
| `mapping-manifest.json` | Every mapping row from acceptance-plan section 2 with status `resolved`, `unsupported` or `blocked`. The single source of truth for the unsupported list and for declared short sessions. |
| `tolerances.json` | The numeric limits. Defaults only; a preregistered sheet replaces this file with no code change. `compare.py` reads and applies every limit it declares. |
| `convert.py` | Hash-checks the retained LEAN inputs and decodes SPY hourly bars into Nautilus `Bar` objects. No forward fill, no adjusted-price substitution. |
| `fixture_strategy.py` | The minimal native strategy, plus the pure decision, causality, commission and ledger helpers. |
| `run.py` | Runs the replay twice in fresh engines and writes `receipt.json`. Applies no tolerance of its own; its checks are exact. |
| `compare.py` | Independent `Decimal` comparator against the LEAN oracle. Pure standard library; no engine or model call. |
| `receipt.json` | The published replay receipt (hashes and economic ledger only). |
| `verdict.json` | The published comparison verdict. |
| `probes/` | Retained engine-probe scripts and their transcripts: the evidence behind the two `unsupported` rows. Each artifact's sha256 is recorded in `mapping-manifest.json` under `probes.artifacts`. |

Raw native reports and the converted rows stay in the private run directory and
are not published.

## What is hash-bound to what

Nothing in the comparison is taken on trust:

* the five frozen LEAN inputs, against the acceptance-plan table, before any row
  is read;
* `tolerances.json` and `mapping-manifest.json`, against the digests the receipt
  recorded;
* the dated LEAN oracle receipt, against `oracle.receipt_sha256` in the manifest,
  which is the acceptance plan's own frozen `Published baseline receipt` value;
* the converted bars used for attribution, against
  `attribution_evidence.converted_rows_sha256` in the receipt — whether supplied
  with `--bars` or re-derived with `--lean-data`;
* the receipt's `unsupported_mappings`, `engine.version` and `evidence_class`,
  against the bound manifest;
* the frozen `historical-simulation/plan.json`, against `oracle.plan_sha256`, and
  the receipt's own recorded plan digest against the same value;
* `case_configuration`: `initial_cash_usd`, `sizing_buffer`, `target`, `fee_usd`
  and `slippage` against that plan, and `seed`, `account_type`,
  `use_random_ids`, `fill_model`, `fee_model` and `window` against the manifest's
  preregistered `case_configuration` block;
* every entry of the receipt's `local_source_sha256`, against the harness files
  as they are on disk at comparison time.

Any mismatch refuses the comparison rather than downgrading it.

Separately, the comparator rebuilds the whole cash path from the receipt's own
fills and distributions and reconciles both headline balances against it
(`end_cash_internal`, `native_end_cash_internal`). A receipt whose published end
cash contradicts its own ledger fails those named checks, and that failure is
never attributable to a mapping gap.

## Environment

* Pinned interpreter: `~/.local/share/codex-ecosystem/tools/nautilus-2.0.0rc5/bin/python`
  (`nautilus_trader 2.0.0rc5`, CPython 3.12.3). Do not resolve `bin/python`
  through its symlink: that reaches system Python and loses the installed
  native distribution.
* Data root: `~/.local/share/codex-ecosystem/tools/lean-985ef30/Data`.
  All five frozen input hashes from acceptance-plan section 1 must match; the
  run refuses to start otherwise. The retained LEAN source pin is
  `985ef30ad3ac774218c5ac516b4cb0aa2655730f`.
* No network, no broker client, no credential store. `exchange_calendars` is not
  installed and is not required.

## Reproduce `receipt.json`

Run inside the isolation the earlier upstream acceptance used: a mandatory new
network namespace, cleared environment, read-only runtime, repository and data,
and one owned output mount.

```sh
NENV=~/.local/share/codex-ecosystem/tools/nautilus-2.0.0rc5
REPO=<this checkout>
LEAN=~/.local/share/codex-ecosystem/tools/lean-985ef30/Data
OUT=<fresh private directory>

bwrap --unshare-all --die-with-parent --new-session --clearenv \
  --ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/lib /lib \
  --symlink usr/lib64 /lib64 --proc /proc --dev /dev --tmpfs /tmp \
  --ro-bind "$NENV" "$NENV" --ro-bind "$REPO" /repo --ro-bind "$LEAN" /data \
  --bind "$OUT" /out --chdir /repo \
  --setenv LANG C.UTF-8 --setenv PATH /usr/bin:/bin \
  --setenv PYTHONDONTWRITEBYTECODE 1 \
  --setenv OPENBLAS_NUM_THREADS 1 --setenv OMP_NUM_THREADS 1 \
  "$NENV/bin/python" -I \
  /repo/blueprints/us-equities/engine-nautilus/spy-parity/run.py \
  --lean-data /data --out /out/native
```

`run.py` exits 0 and writes `$OUT/native/receipt.json`, the two run directories
and `$OUT/native/converted-rows.private.json`. Copy the receipt here to publish
it; leave everything else private.

## Reproduce `verdict.json`

The comparator needs the converted bars to attribute a deviation by measurement.
Pass the run's own rows, or re-derive them from the data root:

```sh
python3 blueprints/us-equities/engine-nautilus/spy-parity/compare.py \
  --receipt blueprints/us-equities/engine-nautilus/spy-parity/receipt.json \
  --bars "$OUT/native/converted-rows.private.json" \
  --verdict blueprints/us-equities/engine-nautilus/spy-parity/verdict.json
# or, instead of --bars:
#   --lean-data ~/.local/share/codex-ecosystem/tools/lean-985ef30/Data
```

Only a complete comparison with no failing check exits **0**. With no bars
supplied it still runs, but the `attribution_evidence` check is reported
`SKIPPED` (never `PASS`), nothing can be attributed, and every deviation is an
unattributed `FAIL`. The three modes were observed as:

| Mode | Exit | Verdict |
| --- | --- | --- |
| `--bars` | 1 | `BLOCKED`, 25 passed / 4 failed, `complete true`, `unattributed_failures []` |
| `--lean-data` | 1 | identical verdict, rows re-derived and re-hashed |
| neither | 1 | `FAIL`, 4 unattributed, 1 `SKIPPED`, `complete false` |

The verdict vocabulary is:

| Verdict | Meaning | Exit |
| --- | --- | --- |
| `PASS` | every check passed and the comparison was complete | 0 |
| `BLOCKED` | every failure is a measured deviation matching an `unsupported` mapping | 1 |
| `BLOCKED-INCOMPLETE` | a check was skipped or an attribution rejected, so the comparison did not finish — whether or not anything failed | 1 |
| `FAIL` | at least one failure is unattributed or an attribution was rejected | 1 |

A skipped check can never leave a `PASS`: missing attribution evidence turns an
otherwise clean run into `BLOCKED-INCOMPLETE`, not a pass.

`compare.py` compares the receipt's own case rather than a case named on the
command line.

## Reproduce the probe transcripts

```sh
"$NENV/bin/python" -I .../spy-parity/probes/fill_semantics_probe.py {plain|atopen|on_start}
"$NENV/bin/python" -I .../spy-parity/probes/dividend_symbol_scan.py
```

Run them under the same bwrap wrapper as the replay. The fill-semantics probe
renders freshly generated UUID4 identities as `<uuid4>` so its transcript is
stable; nothing else is filtered.

## Tests

```sh
python3 -m unittest tests.test_spy_parity -v
python3 -m unittest tests.test_nautilus_equity_replay -v
```

These are synthetic boundary fixtures plus checks against the real retained LEAN
receipt schema. They do not run the engine and do not establish parity.

## What is blocked

`market_on_open_proxy` and `distributions_and_cash` are `unsupported` on the
pinned engine, and `margin_and_adaptive_state` plus the stressed cost mapping are
`blocked`. The comparator proves each blocked cash deviation arithmetically
rather than trusting the receipt: an attributed fill price must equal its
session's first-bar close while the oracle equals that bar's open, and any cash
residue those deltas do not explain exactly stays an unattributed `FAIL`.

Closing either mapping needs a mechanism the pinned engine supports natively,
or a newly preregistered mapping manifest. The manifest injects no balancing
cash entry (the acceptance plan forbids an invented one) and states that
synthetic open-priced data would fabricate the mapping, so neither is
attempted here.

## Review findings carried (2026-09-22)

An independent review of this harness (recorded in the agent-lab task record
`docs/tasks/2026-09-22-executed-comparisons.md`, "Parity final review")
confirmed 21 of 24 claims and recorded six non-blocking items. None changes the BLOCKED verdict; they are carried
into the next harness round:

1. `fixture_strategy.py` substitutes a zero commission when a native fill
   event carries none, instead of refusing; the published run did not hit
   this branch (its fills record fee `0.00 USD`).
2. `convert.py` validates price decoding, integral volume and OHLC
   consistency only on in-window rows; out-of-window rows get the whole-file
   field-count, duplicate and monotonicity checks only (all five inputs are
   hash-pinned).
3. `fixture_strategy.check_run_integrity` checks engine iterations only when
   the engine reports a value.
4. `convert.py` drops a nonpositive derived distribution silently instead of
   refusing or recording it.
5. The comparator mode table documents the `--bars` and no-evidence modes as
   observed; the acceptance set exercises only the `--lean-data` mode.
6. The review inventory miscounted the test classes (17, not 13).
