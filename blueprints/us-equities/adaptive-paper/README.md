# Adaptive equity research and paper practice

This lane wires five deterministic policy families into NautilusTrader2.0.0rc5
`LiveNode`, with the official Alpaca SDK0.44.0 carrying quotes, order updates and
paper REST requests. The native strategy, risk/execution engines and portfolio
are in the order path. It extends the separate, previously accepted one-SPY
paper smoke without changing that trial's source, limits or results.

Current operational status and source hashes belong in `receipt.json`.
The local capacity fixture is synthetic. It does not establish broker throughput
or strategy profitability. The September21 regular session closed while the new
integration was being built; the retained native paper smoke remains the only
actual order result until a subsequent open-session receipt says otherwise.

## Policies and portfolio behavior

| Family | Observed inputs and entry condition | Exit / allocation |
| --- | --- | --- |
| Trend momentum | Fast quote midpoint mean above slow mean; rising benchmark basket; cost hurdle | Loss, trailing, profit, time or portfolio rotation |
| Range breakout | Current midpoint exceeds prior observed rolling high by cost hurdle | Same explicit exits; no future bar used |
| Mean reversion | Below rolling mean with an observed upward turn in a range regime | Same exits; no automatic falling-price entry |
| Relative strength | Positive momentum outperforming the benchmark basket over matched time windows | Ranked common portfolio budget |
| Defensive cash | Observed broad decline or extreme volatility | Reduce exposure; missing benchmark data pauses entries |

SPY,QQQ,IWM,DIA represent tradable US index proxies. The explicit24-name universe
includes liquid stocks from the requested watchlist, subject to fresh native
asset/quote qualification. The user-provided market table is not an executable
price feed. Foreign indices, penny-stock extremes, shorting and predictive catalyst
pre-positioning remain unqualified. Leverage above 1x is unqualified until a
validated `leverage-schedule-v1-20260922` policy (see README-safety.md) is
present in config, a preflight-proven account multiplier at least equal to the
requested leverage has been confirmed, and this ladder's gate rows
(`leverage-ladder-1x/2x/4x` in `catalogs/us-equities/gates-20260922.json`) each
show `needs_attention == 0` together with a recorded peak achieved leverage and
time above the next-lower rung's cap (0.5x for the 1x rung).

The allocator uses one portfolio owner across all families, explicit cost
hurdles, an exposure reserve below the ledger cap, a cooldown and minimum hold.
It can choose no position. Its family-selection counters count policy decisions;
submitted intents, accepted orders, native fill events and completed roundtrips
are separate metrics. No strategy manufactures trades to hit a throughput target.

These transparent baselines are wired research policies, not an empirical claim
to the best strategy. Comparative historical evaluation needs point-in-time
universes/news, realistic costs, unseen chronological segments and the existing
corporate-action acceptance work. A favorable paper run would not replace that.

## Frozen first trial

`config.json` defines five minutes in the regular session, plus120seconds cleanup;
$10,000 paper capital, $5,000 maximum gross exposure, $1,000/one share per entry,
ten held symbols, twenty outstanding orders, and $25 observed loss/drawdown
thresholds. The policy holds additional allocation headroom below the ledger cap.
Quotes must be <=3seconds old, future-clock tolerance250ms, entry spread<=15bps.
Entries stop at least300seconds before close. Marketable limit exits may remain
unfilled during gaps; these limits cannot guarantee a maximum realized loss.

`config.json` selects the `iex` feed. `config-sip.json` is the same frozen
trading configuration with `feed: "sip"`, for an account whose SIP entitlement
has been separately confirmed; the single `feed` value drives both the REST
quote/snapshot requests and the quote stream endpoint. No SIP run has been
executed, so nothing here qualifies SIP data quality, entitlement or cost.

Trial continuity is keyed by the SHA-256 of the selected config file, recorded
as `config_sha256` in the state directory's `trial.json`. `config.json` and
`config-sip.json` hash differently even though only the feed differs, so
pointing `--config` at `config-sip.json` under a state directory created for
`config.json` refuses with `next_trial_config_differs_from_frozen_limits`, and
`recover` refuses with `recovery_config_differs_from_frozen_trial`. A new
`--trial` identifier does not avoid this, because the state directory is keyed
by the account fingerprint alone.

The preferred path is to finish or recover the open IEX trial and start the SIP
trial in the same state root, so one durable ledger keeps the account-level risk
and request history. That path is currently refused: continuity is pinned to the
config file's bytes, not to its trading fields, so
`next_trial_config_differs_from_frozen_limits` still fires even though
`config-sip.json` changes only the feed. Comparing the frozen trading fields
instead of the file hash would unblock it; that change is not made here.

A separate `--state-root` is the remaining option and is not a neutral switch. It
creates a second, fully independent durable ledger
(`<state-root>/<account-fingerprint>/adaptive/ledger.sqlite3`) for the *same*
paper account. Its intent, fill, request, event and trial tables start empty, so
the account-level gross-loss and drawdown budgets, the baseline cash and the
durable request-rate history all restart from zero, while the broker account and
its shared 200/minute limit do not. Within one ledger these are deliberately
never reset between trials. A second ledger is therefore acceptable only when the
SIP trial is itself the first trial in that ledger and a fresh risk budget is
intended; two ledgers driving one account would each believe they hold the full
loss, drawdown and request budget.

`receipt.json` stays the dated 2026-09-21 record, so some of its counts now
understate the suites, and it is not restated here. `full_repository_suite.run`
is 895 against 1,084 today. `independent_review` names 20 runner/strategy tests,
now 23 (runner 7 to 10; strategies unchanged at 13), and 20 market-research
tests, now 28. Its safety 46 and recovery 21 are unchanged. The receipt states no
transport or native per-suite count: the transport suite is 36 to 48, and the
native suite is 8, which already differed from the "Seven local checks" sentence
in `README-native.md` before this change. The 42 unchanged upstream adapter tests
were not rerun.

Every Trading REST attempt counts against the shared durable200/minute budget.
Buys and sells share a180/minute submission ceiling, reserving at least20 calls
for account management. Delayed entry admission releases locks immediately so
cancels can use that reserve. Even ideal full fills allow at most90 two-order
roundtrips/minute at this ceiling. Elite advertised1000 API calls/minute is not
this account's observed entitlement or a1000-trades guarantee.

## Lifecycle and native boundaries

The SQLite ledger fsyncs intent and request reservations before sending. Stable
IDs, per-execution fill accounting (cumulative averages only where an execution is
missing) and an account-specific exclusive lock prevent blind retries and competing
writers. Shared STOP blocks new entries; confirmed owned exits remain available. Fresh
startup requires a flat account with no open orders. Periodic and final snapshots
compare positions and cash to the ledger.

Engine release of 2026-09-24 (items 2-4 of the data and execution convergence
record): each broker execution is booked at its own quantity and price, with fill gaps
closed from the order's FILL activities (README-native.md, README-safety.md); every
strategy order and position callback is guarded, because rc5 discards an exception
raised there (README-native.md); and on SIP the engine tracks per-symbol trading halts,
LULD pauses and quotation-only periods from the status stream plus a startup seed, and
while a symbol is halted neither lane sends it an entry or a new exit (stop, trailing,
gap-risk and forced exits wait for the resume) nor re-prices its resting exit
(README-native.md, README-transport.md, README-mover.md). The quote's own condition
flag blocks entries only, and a halt only the startup seed asserts expires (at its
resumption time, or 12 minutes after a LULD pause began). The evidence is synthetic
fixtures and local integration against the real rc5 `LiveNode`; no paper session has
run this release yet. It changes engine files
that a forward protocol pins, so such a protocol needs a new version before it counts
sessions run on this release.

Stream authentication/subscription acknowledgement, queue integrity, per-symbol
freshness and connection generations are observed explicitly. Models never own
numeric risk, request budgets, order retries or liquidation rules. SDK automatic
HTTP retries and redirects are disabled; only explicit paper endpoints are allowed.

The current native Equity model is whole-share-only. An actual fractional fill
freezes the native node and preserves its exact quantity. A separate bounded
official-SDK recovery path adopts the durable order state, confirms cancellations
before selling owned residuals, supports nine-decimal quantities and requires a
fresh cash/position proof. This is not a native strategy restart. Uncertain POSTs
stay uncertain until broker evidence resolves them;404 alone is not proof of no fill.

Use the same account state directory for recovery and subsequent trials. Never
delete the ledger or change state roots to evade a halt, loss budget or unresolved
order. All receipts distinguish failure, no-signal completion, simulation and
observed broker acceptance.

## Native usage

Install `requirements.txt` in an isolated Python3.12 environment. The ordinary
entrypoint uses an explicitly selected private Alpaca paper env file; it reads
only `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`. Never put keys in a command line,
repository, prompt, artifact or browser code.

```sh
python runner.py preflight --env-file "$PAPER_ENV_FILE" --output "$PRIVATE_OUTPUT/preflight.json"
python runner.py paper --trial dated-unique-trial --env-file "$PAPER_ENV_FILE" --output "$PRIVATE_OUTPUT/paper.json"
python runner.py recover --env-file "$PAPER_ENV_FILE" --output "$PRIVATE_OUTPUT/recovery.json"
python benchmark.py --output "$PRIVATE_OUTPUT/synthetic-capacity.json"
```

On macOS the key pair can live in the login Keychain instead (store it once with
`secret set APCA_API_KEY_ID` and `secret set APCA_API_SECRET_KEY`). `secret run`
hands it to that one command, which removes it from its own environment as it reads it:

```sh
secret run APCA_API_KEY_ID APCA_API_SECRET_KEY -- python runner.py preflight --credentials keychain-env --output "$PRIVATE_OUTPUT/preflight.json"
```

`market_research.py` takes the same `--credentials keychain-env`. Both sources are
paper-only: an `APCA_API_BASE_URL` in the environment or env file that is not
`https://paper-api.alpaca.markets` is refused before any request. See the
2026-09-25 addendum to `docs/decisions/2026-09-22-broker-credential-handling.md`.

`paper` is bounded and fails closed when the regular session, account, data,
frozen configuration or durable state is not ready. No live endpoint is exposed.
The benchmark imports the real native engine but uses a local fake broker port.
Run the corresponding `tests/test_adaptive_paper_*.py` in the combined pinned
runtime. Standalone source receipts describe their exact historical test scope;
the integrated receipt binds the final reviewed source versions.

## Research and evidence selection

Use `market_research.py` for a dated, read-only news/snapshot watchlist. News
urgency, sentiment or a high percentage mover is not a return forecast. Keep
source publication/update/observation timestamps and partial-coverage flags.
Claude and Codex review the retrieved evidence and compare candidate policies;
TypeSafe judgments remain advisory until task-specific calibration and
point-in-time historical evaluation qualify them. No current news label changes
paper-order eligibility by itself.

Reused sources: [Nautilus Python adapters](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/developer_guide/python_adapters.md),
[official adapter tests](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/tests/integration/test_python_adapter_template.py),
[Alpaca SDK0.44.0](https://github.com/alpacahq/alpaca-py/tree/cc4cb3b7ba50ae250e621983c2779047fb16bb28),
[Trading request limit](https://alpaca.markets/support/usage-limit-api-calls),
[paper simulation limitations](https://docs.alpaca.markets/us/docs/paper-trading),
[fractional DAY orders](https://docs.alpaca.markets/us/docs/fractional-trading).

The old `example-hftish` submit/cancel loop doubles request use per attempt and
does not close this native engine gap. Smart Router TWAP/VWAP paper acceptance
does not simulate the algorithms, so neither is adopted into this paper lane.
No new engine replacement is justified by repository popularity alone.

## Broker-path metrics and alerts

`metrics.py` is a separate, read-only Prometheus exporter for the durable
ledger this lane already writes (`ledger.sqlite3`, plus the sibling
`trial.json`). It never imports `safety.Ledger` (which opens the database for
writes), never reads an env file or broker credentials, and never talks to
Alpaca. It binds loopback-only and serves `/metrics`:

```sh
python metrics.py --ledger "$STATE_ROOT/<account-fingerprint>/adaptive/ledger.sqlite3"
```

`--port` overrides the default `18890`; the host is always `127.0.0.1`.
`--trial-json` overrides the default sibling `trial.json` path if state is
laid out differently. See the module docstring for the exact source of every
metric and the two gaps documented below.

Exported: `paper_trial_active`, `paper_needs_attention`,
`paper_reconciliation_status{result}`, `paper_order_state_divergence_total`,
`paper_ledger_frozen{reason}`, `paper_request_budget_remaining{kind}`,
`paper_request_budget_limit{kind}`, and `paper_ledger_readable` (1/0, always
exported: this scrape's read-only ledger open succeeded or not -- it is the
exporter's own operational status, not a value read from the ledger, and is
the only signal for the conditionally-emitted metrics above going silently
absent on a bad `--ledger` path or a permissions problem). **Not exported**
(not durably recorded by the current ledger/`trial.json` schema; see
`metrics.py`'s module docstring for why, rather than inventing new
`safety.py` fields to support them):
`paper_reconciliation_last_success_timestamp_seconds` and
`paper_request_budget_wait_exceeded_total`.

The observability backend profile's Prometheus scrapes `127.0.0.1:18890` as
job `adaptive-paper`, and its rules add the `equities-broker-path` alert
group (`EquitiesOrderStateDivergence`, `EquitiesReconciliationFailed`,
`EquitiesRequestBudgetExhausted`, `EquitiesLedgerFrozen`,
`EquitiesPaperMetricsMissing`, `EquitiesLedgerUnreadable`), routed to the
existing local ntfy receiver by `scope: equities-broker`. It also excludes
this job from the pre-existing `EcosystemServiceUnavailable` rule, since this
exporter is a separate process not started by `install.py`/`configure.py`
and would otherwise leave that generic rule firing permanently whenever no
paper trial is running. See
[`observability/backends/README.md`](../../../observability/backends/README.md#adaptive-paper-broker-path-alerts)
and the templates under `observability/backends/templates/`. Run `metrics.py`
as its own process alongside a trial; it is not started by `runner.py` and
does not affect the trial's risk decisions or request budget.

## Codex cross-family review fixes (PR-4 follow-up)

Five findings from a Codex cross-family review of PR-4 are resolved, each with
a regression test in `tests/` that fails against the pre-fix source and passes
after (see `tests/test_promotion_gate.py`, `tests/test_adaptive_paper_runner.py`,
`tests/test_adaptive_paper_metrics.py`):

* **`promotion_gate.py`: empty snapshot silently passed.** An all-required-
  columns, zero-row snapshot used to report `status: "pass"`, `row_count: 0`.
  A named `rows_present` check now fails closed whenever `row_count == 0`,
  independent of every other check. See `blueprints/us-equities/data/README.md`.
* **`promotion_gate.py`: `volume=-0.5` passed via lossy coercion.** `.astype
  ('int64')` truncated a raw fractional/negative volume (e.g. `-0.5` -> `0`)
  BEFORE the old `volume_non_negative` check ran on the coerced column. Volume
  is now validated on the RAW column, before any coercion, via a named
  `volume_integral_non_negative` check (rejects non-finite, non-integral, or
  negative raw values); `_prepare()`'s coercion is now purely a safe
  downstream-typing substitution that can never itself raise. See
  `blueprints/us-equities/data/README.md`.
* **`runner.py` `validate_preflight(mode="paper")`: accepted an incomplete/
  empty/partially-failing gate result.** A gate result whose top-level
  `status` was `"pass"` and whose `input_sha256` matched used to be accepted
  even when it declared `row_count: 0` or carried a failed check.
  `_check_promotion_gate` now validates the full contract: every key in
  `status, input_sha256, row_count, checks, versions, checked_at` is present;
  every `checks[].status == "pass"`; `row_count > 0`; the referenced
  `--snapshot` is a regular file with a gate-accepted extension (`.csv`/
  `.parquet`) whose sha256 matches `input_sha256`. New `SafetyError` kinds:
  `promotion_gate_incomplete` (missing/malformed required keys or an empty
  `checks` list), `promotion_gate_failed_check` (a named check failed despite
  a "pass" top-level status), `promotion_gate_empty` (`row_count <= 0`
  despite a "pass" top-level status) -- alongside the pre-existing
  `promotion_gate_missing`/`promotion_gate_failed`/`promotion_gate_mismatch`.
* **`metrics.py`: `--trial-json` (and any other path argument) accepted
  arbitrary paths.** `_read_trial_json` read whatever path it was given, with
  no restriction. Every readable path (`--ledger`, `--trial-json`) is now
  confined to the resolved ledger directory (the resolved parent of
  `--ledger`) via `Path.resolve(strict=True)` plus a containment check; a
  path outside that directory, or a symlink escaping it, is refused before
  any attempt to read its contents (refused paths are treated exactly like a
  missing file -- the relevant gauge reads `0`/absent, never the escaped
  file's content).
* **`metrics.py`: the read-only SQLite URI was built by string
  concatenation.** `"file:" + str(path) + "?mode=ro"` let a filename
  containing `?`/`#` override `mode=ro` (a probe path of
  `/synthetic/probe?mode=memory&ignored=` yielded a writable connection). The
  URI is now built from `urllib.parse.quote` of the resolved path plus
  `?mode=ro&immutable=1`, and any ledger path containing `?`/`#` is refused
  outright as a second, independent guard.
