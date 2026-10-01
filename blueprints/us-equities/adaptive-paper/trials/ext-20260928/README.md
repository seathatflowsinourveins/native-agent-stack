# Extended-hours mover paper series `ext-20260928`, 2026-09-28 POST: 2 of 8 attempts passed, flat

This is the sanitized receipt of an extended-hours mover paper series on the second Alpaca paper account
(credential inventory id `alpaca-paper-2`). It ran in the POST session of 2026-09-28, from 16:23 to 18:29 ET.
`receipt.json` holds the figures. This directory also holds the reconciliation tool and its stdout, sanitized copies
of the seven engine receipts, the four series consoles and the freeze SHA256SUMS ([Files](#files)). The engine
ledger, the scan caches and the rest of the trial workspace stay private.

It is metadata plus broker-reconciled evidence, not a frozen gate run. It qualifies no gate, and the
`alpaca-paper-extended-hours` gate row is unchanged. The run was a mechanics-only test with no validated edge:
the protocol's development study passed 0 of 768 rule-exits
([`mover-early-entry`](../../../mover-early-entry/README.md)). No credential, account id, account number, account
fingerprint, broker order id or ref, activity id, execution id or host path is recorded.

## Setup

**Code.** Main `3058b237`, run from a detached checkout of that SHA in a session scratch directory.
- The `pc-20260928` run script (modified 16:02:44Z) and the retained copy of this series' run script name the same
  checkout path. The `pc-20260928` freeze note does not name the path it hashed.
- The evidence for that checkout's content is the `pc-20260928` freeze's `frozen-3058b237.SHA256SUMS`, committed
  here. This series' freeze adopts it by reference. It was written at 15:59:26Z, about 4.4 hours before attempt 1.
- It lists 60 of the 196 files that `adaptive-paper/` and `mover-early-entry/` hold at `3058b237`: exactly their
  top-level non-README files. All 60 equal `git show 3058b237`. They include the 26 `adaptive-paper/*.py` sources
  and `mover-early-entry/mover_scan.py`, whose hashes are in `receipt.json` (`code.engine_sources_sha256`).
- Not excluded: a change to those 60 files after 15:59Z, and the state of the other 136 files, 99 of which are
  committed trial records. The checkout was later removed, so it was not re-hashed at run time.

**Runtime.** NautilusTrader LiveNode 2.0.0rc5 and alpaca-py 0.44.0 on Python 3.12.3, from the pinned adaptive-paper
virtual environment, run with `python -B`. The engine name comes from the trial receipts. The alpaca-py and Python
versions were read from the same environment on 2026-09-29, not at run time.

**Credential route.** Kernel keyring wrapper; since 2026-09-29 the 0600 env file store
([docs/secret-storage.md](../../../../../docs/secret-storage.md)). The series received the key pair through the
kernel keyring wrapper. The 2026-09-29 reconciliation below read the env file store through its pointer variable.

**Config.** Frozen before any broker I/O, sha256 `768957da790acabe…`:
- protocol `mover-early-entry-v1-20260924`, section `paper_e2e`;
- rule `10:00|G20|V1000000|any` (gain in percent points), exit X2 (a 3,600 s hold);
- SIP feed, extended hours on, no overnight holds, benchmark SPY only;
- capital 5,000 USD, at most 5 symbols;
- entry cap 1,000 USD per symbol; ledger caps of 10,000 USD per order, 100 shares and 10,000 USD gross;
- lifetime gross loss and drawdown of 500 USD each;
- rung 4 under `leverage-schedule-v1-20260922`. Its POST cell holds the envelope at 1x, so the gross budget was
  5,000 USD;
- at most 200 requests and 180 submits per minute, and at most 20 outstanding orders;
- quotes at most 3 s old, spreads at most 100 bps, limit caps of 50 bps;
- an entry window of 30 s, and `stream_quote_timeout_seconds` 30.

**Procedure.** Each attempt ran four steps: `mover_scan.py`, then `mover_runner.py check`, then a synthetic run
(SYN), then `paper`. `recover` was to run on `needs_attention`, but no attempt needed it.
- **The freeze fixed no trial count.** It runs trials in sequence, each only after the previous one passed or
  recovered, with the last start at 18:30 ET. It stops the series on a ledger halt, a failed recovery, a preflight
  refusal or 18:30 ET. Eight attempts ran.
- **`chain-next.sh`** started the next unit only after the previous unit had ended and its trial had passed. It
  checked the 18:30 ET last start once, before handing over to `retry-benchmark.sh`, which does not check the
  clock. The last attempt started at 17:28:55 ET.

## Attempts

| # | ET | Result | Orders | Fills (engine = ledger = broker) | Realized P&L | Flat at end |
|---|---|---|---|---|---|---|
| 1 | 16:23:35-16:23:40 | refused at `check`: `scan_rule_differs_from_config` | 0 | 0 | 0 | yes |
| 2 | 16:24:45-16:24:57 | `not_started`: preflight `benchmark_quotes_not_ready` | 0 | 0 | 0 | yes |
| 3 | 16:25:58-17:26:43 | **passed** | 6 | 17 | +3.09 USD | yes |
| 4-7 | 17:26:49-17:28:35 | `not_started`: preflight `benchmark_quotes_not_ready`, four times | 0 | 0 | 0 | yes |
| 8 | 17:28:55-18:29:36 | **passed** | 4 | 6 | -12.00 USD | yes |

Flat at end means the following:
- For the passed trials, the engine's end reconciliation showed `cash_match` and `positions_match` true, 0 open
  orders and 0 positions.
- For attempts 2 and 4 to 7, the preflight saw 0 positions and 0 open orders, and no order was sent.
- For attempt 1, no paper stage ran. Attempt 2's preflight one minute later saw the account flat.

**Trial 3.** The scan fired 7 symbols. The top 5 were KOD, CLRO, NAMI, MEDS and KNRX.

| Symbol | Entry | Exit (`x2_time`, about 60 min later) | Realized |
|---|---|---|---|
| KNRX | 100 @ 1.01, limit 1.01, 4 fills | 100 @ 0.9433, limit 0.9386, 4 fills | -6.67 |
| KOD | 11 @ 88.00, limit 88.44, 2 fills | 11 @ 88.16, limit 87.72, 1 fill | +1.76 |
| CLRO | 100 @ 5.12, limit 5.14, 2 fills | 100 @ 5.20, limit 5.18, 4 fills | +8.00 |

NAMI and MEDS were skipped when the 30 s entry window closed. Their last wait reason was `entries_not_enabled`.

**Trial 8.** The scan fired 6 symbols. The top 5 were KOD, CLRO, NAMI, MEDS and LFCR. Sizing equity was
5,003.09 USD, carried from trial 3.

| Symbol | Entry | Exit (`x2_time`) | Realized |
|---|---|---|---|
| CLRO | 100 @ 5.23, limit 5.25, 1 fill | 100 @ 5.11, limit 5.09, 2 fills | -12.00 |
| KOD | 11 @ 88.20, limit 88.64, 2 fills | 11 @ 88.20, limit 87.76, 1 fill | 0.00 |

NAMI, MEDS and LFCR were skipped with `entries_not_enabled`.

**Series totals.**
- 10 orders: 5 entries and 5 exits. All were `limit`, `day`, `extended_hours` true, and all ended `filled`.
- 23 fill events.
- Realized P&L -8.91 USD. The ledger, the sum of the two engine receipts and the broker recompute agree.
- The ledger's gross loss was 18.67 USD. This is `realized_loss`, the sum of each fill's realized loss; here it
  equals the two losing legs, KNRX -6.67 and CLRO -12.00.
- The ledger's peak P&L was 14.89 USD. This is `safety.py`'s `peak_pnl`: the mark-to-market peak of realized plus
  unrealized P&L, with open positions marked at the bid. It is not a realized figure, and no second source can
  recompute it.
- Every one of the 23 fills was at its order's reference quote: the ask for buys, the bid for sells. The
  reconciliation matched each ledger execution to a broker FILL activity on `cum_qty`, `qty` and `price`, and each
  execution price equals the quote in the engine events. That is what Alpaca's paper simulation does, not evidence
  about live slippage.

## Broker reconciliation (2026-09-29 07:29Z)

This was a fresh read-only read of the second account, GET requests only, on the paper endpoint. The tool is
`reconcile_ext_series.py`. Its stdout is kept byte-identical as `reconcile-ext-series.stdout.json`; the
private-detail scan found nothing to redact.
- **Run.** It ran once, with exit code 0, from this directory inside `bash -ic`:
  `python -B reconcile_ext_series.py --env-file "$PAPER_ENV_FILE_2" --ledger "$MOVER_LEDGER" --prefix
  mvr-ext-20260928- --after 2026-09-28T20:00:00+00:00 --until 2026-09-29T00:30:00+00:00`.
- **Variables.** `PAPER_ENV_FILE_2` is the inventory pointer of `alpaca-paper-2`. `MOVER_LEDGER` was set in the same
  shell to the one mover ledger under the paper state root, from a glob that had to match exactly one file. Only
  the variable names are recorded.
- **Runtime and stderr.** `python` is the pinned adaptive-paper interpreter (alpaca-py 0.44.0). The tool's stderr
  was empty.
- **Hashes.** `receipt.json` (`broker_reconciliation`) holds the tool and stdout sha256 values.
- **Window.** The window ran from 2026-09-28T20:00Z (16:00 ET) to 2026-09-29T00:30Z.

The tool reads the ledger first (sqlite `mode=ro`), so a wrong ledger path fails before any broker request. It then
made these reads:
- orders with `status=all`;
- FILL activities, paged with `page_token` (1 page);
- positions;
- open orders.

It joined the results in memory to the ledger:
- 10 orders were listed in the window. All 10 carry the series prefix `mvr-ext-20260928-`, and there were 0 foreign
  orders.
- There were 23 FILL activities, none foreign.
- All 23 ledger executions match an activity on `cum_qty`, `qty` and `price`, and also on execution id. The largest
  time difference was 0.004 s.
- **0 unconfirmed fills.** Any ledger execution without a matching activity would have been listed as unconfirmed.
- All 10 orders agree with the ledger intents on symbol, side, quantity, limit, final status, filled quantity and
  average price. The engine, the ledger and the broker all say `filled`.
- P&L recomputed from the broker's activities is +3.09 for trial 3, -12.00 for trial 8 and -8.91 in total. This
  equals the engine and ledger figures.
- 0 positions and 0 open orders at the time of the read.

**Earlier read.** A scratch version of the same tool read the broker at 06:24:16Z. It located the ledger by a glob
inside the script and read the broker before the ledger. It returned the same values except `observed_at` and one
broker timestamp: the `submitted_at` of `mvr-ext-20260928-8-0000004` was 22:29:35.588917Z then and 22:29:35.588918Z
at 07:29Z. `receipt.json` holds that earlier stdout's sha256; the stdout itself is not committed.

The read is separate from the engine code and ledger writer. It uses the same broker API and account, so it is
independent of the engine but not of the broker.

## Errors, rejects and retries

- **Rejects, cancels and engine errors.** There were no native rejections, pre-wire refusals or cancels. There
  were also no adapter errors, callback faults, average-invariant mismatches or duplicate executions. No fill gap
  was open at stop, and no halts occurred; the halt seed held 95 items, none for these symbols. These figures come
  from the engine receipts alone (`field_provenance`).
- **`benchmark_quotes_not_ready`.** This refusal came five times, on attempts 2, 4, 5, 6 and 7. The preflight found
  no SPY quote within the engine's freshness bounds: at most 3 s old and no more than 0.25 s ahead. Each refused
  attempt stopped before any order.
  - After the refusals of attempts 4, 5, 6 and 7, `retry-benchmark.sh`, inside the `chain4` unit, started the next
    attempt 20 s later.
  - After attempt 2's refusal, the operator started the `r3` unit 61 s after unit 2 stopped.
  - This is the same after-hours quote-age limit recorded on 2026-09-23 in
    [`../20260923-post-extended-hours/`](../20260923-post-extended-hours/README.md).
- **Rule argument.** `mover_scan.py` reads G as a ratio but writes the engine scan file in percent points, so
  attempt 1's argument `G20` became `G2000`. That scan fired 0 symbols, and `check` refused it. From attempt 2 on,
  the argument was `G0.20`, which is 20 percent and matches the frozen config rule. The config and its sha256 were
  unchanged.
- **Websocket restart lines.** Each passed trial logged one data-stream and one trading-stream line: `websocket
  error, restarting ... sent 1000 (OK)`. These are normal-close records. The 2026-09-23 isolation check
  ([`../20260923b-needs-attention/`](../20260923b-needs-attention/README.md)) found such lines only after the
  engine's `stop()`. These logs carry no timestamp, so this series neither confirms nor rules that out.
- **Crossed quotes.** Crossed quotes were dropped and counted: 546 in trial 3 (528 of them KNRX) and 5 in trial 8.
- **`entries_not_enabled`.** Five legs across the two passed trials were skipped this way. The wait reason means
  the engine's per-tick entry enable was false whenever those legs were evaluated before the window closed. The
  receipt does not record which enable condition was false.
- **Request peaks.** The busiest 60 s held 21 requests in trial 3 and 20 in trial 8, against 200 per minute allowed.
  Submits peaked at 3 and 2, against 180 allowed.

## Deviations from the freeze

1. **The scanner argument was corrected after attempt 1,** as described above. Attempt 1 sent no order.
2. **Bounded retries replaced the freeze's stop on a preflight refusal.** The operator started the `r3` unit after
   attempt 2's refusal. Within the `chain4` unit, the refusals of attempts 4 to 7 were retried automatically. No
   limit, gate or config changed.
3. **The series scripts, including `chain-next.sh`, were not part of the freeze.**
   - The freeze names and hashes no script.
   - `run-series-trial.sh` (retained copy modified 20:23:19Z), `retry-benchmark.sh` (20:25:56Z) and
     `chain-next.sh` (20:38:43Z) were all written after `FREEZE.md` (20:23:08Z).
   - `chain-next.sh` chained attempts 4 to 8. It implements the freeze's start rule, but it checks the 18:30 ET
     last start once rather than per trial. Every attempt started by 17:28:55 ET.

## Units (systemd user journal)

| Unit | Start (UTC) | Stop (UTC) | Journal result |
|---|---|---|---|
| `paper-ext-20260928-1` | 20:23:34 | 20:23:40 | exit status 2 (`exit-code`) |
| `paper-ext-20260928-2` | 20:24:45 | 20:24:57 | exit status 2 (`exit-code`) |
| `paper-ext-20260928-r3` | 20:25:58 | 21:26:43 | no exit record; success inferred |
| `paper-ext-20260928-chain4` | 20:38:45 | 22:29:36 | no exit record; success inferred |
| `incentive-monitor-20260928` | 20:28:10 | 00:00:19 (09-29) | no exit record; success inferred |

The journal was queried on 2026-09-29 with `journalctl --user -o json USER_UNIT=<unit>.service` (systemd 255).
- Units 1 and 2 each have an exit record (`EXIT_STATUS` 2) and a result record (`exit-code`).
- The `r3`, `chain4` and `incentive-monitor` units each have only a start record and a resource-accounting record.
  None has an `EXIT_STATUS`, `EXIT_CODE` or `UNIT_RESULT` record or a success record.
- Their success is inferred from the absence of a failure record, not observed. The last attempt of `r3` and of
  `chain4` logged `paper rc=0`.

The incentive monitor ran on the first paper account's key pair and is data only. Its docstring says it never
places, changes or cancels an order. The second account's listing shows no order outside the series.

The series scripts are private and hashed in `receipt.json`. `run-series-trial.sh` was edited again on 2026-09-29
for a later series. Its retained copy `run-series-trial.20260928.sh` has a modification time before attempt 1. That
copy matches by time, not by proof.

## Limitations

- **Volatile scratch checkout.** The checkout no longer exists. Code identity rests on the `pc-20260928` freeze's
  SHA256SUMS (60 of 196 files, written 4.4 hours before attempt 1) and `git show`, not on a hash taken at run time.
- **Metadata plus broker-reconciled evidence, not a frozen gate run.** Unconfirmed fills would have been marked
  unconfirmed; there were none.
- **Simulated fills.** Alpaca paper fills are simulated from quotes. They say nothing about live slippage, queue
  position or partial fills.
- **Not a strategy evaluation.** Two passed trials in one POST session do not evaluate a strategy. The scanner
  measures gain against the previous official close, so in POST it selects the day's movers and holds them into
  after-hours. It does not find after-hours-only catalysts.
- **Account designation.**
  - The series kept its own engine ledger: the default paper state root's directory for this account, which holds
    only this series' two trials.
  - It traded broker account `alpaca-paper-2`. Two records designate that account as the isolated
    incentive-monitor study account:
    [`forward-protocol-v1.json`](../../../incentive-monitor/forward-protocol-v1.json) (line 63) and
    [docs/secret-storage.md](../../../../../docs/secret-storage.md) (line 17).
  - The broker account's orders, fills and cash are shared even where the engine ledgers are not.
  - Whether this use fits the forward study's isolation is referred to the forward protocol's owner, the trading
    lane. This receipt does not decide it.
- **Single-source fields.** Some figures come from one source only. Examples are the halt seed count, the
  crossed-quote drops, the native quote count, the websocket lines, the preflight fields, the request peaks and
  the ledger's peak P&L. `receipt.json` `field_provenance` lists every field as asserted across sources, single
  source, derived or literal.

## Paper lane row

The grand-dashboard `paper` row cites this receipt for account 2. Its account 1 part is a dated fact from other
records:
- On 2026-09-28 the `pc-20260928` series on account 1 did not start. Its key probes returned HTTP 401 until the
  15:00 ET stop.
- The trading-lane coordinator records that new keys were stored at about 16:15 ET that day.
- A read-only check at 2026-09-29T00:3xZ returned HTTP 200 on both accounts, with 0 positions and 0 open orders.
  A regular-hours series on account 1 is frozen for 10:00 ET on 2026-09-29; the private series index names it
  `rth-20260929`. Both facts are in the 2026-09-29 updates of
  [`2026-09-28-ecosystem-roadmap.md`](../../../../../docs/decisions/2026-09-28-ecosystem-roadmap.md).

"Flat" in the row holds as of those reads, not later.

## Files

| File | What it is |
|---|---|
| `receipt.json` | The series receipt: code identity, config, per-attempt results, 10 orders, broker reconciliation, units, totals, field provenance, and hashes of the committed copies and of retained private files that carry no account fingerprint |
| `README.md` | This summary |
| `reconcile_ext_series.py`, `reconcile-ext-series.stdout.json` | Independent broker reconciliation: the tool and its stdout, byte-identical |
| `frozen-3058b237.SHA256SUMS` | The `pc-20260928` freeze's hashes of the 60 engine and scanner files, byte-identical |
| `mover-paper-2.json` to `mover-paper-8.json` | Engine receipts of attempts 2 to 8. Each `broker_order_ref` value (6 in trial 3, 4 in trial 8) is replaced by `withheld`; every other byte is unchanged |
| `trial-1.console`, `trial-2.console`, `trial-r3.console`, `chain-4.console` | The series consoles (run logs), byte-identical |

Attempt 1 has no `mover-paper.json`: `check` refused it before the paper stage, and `trial-1.console` records the
refusal.

Private and not committed:
- the freeze note and the outcome note, which name account fingerprints;
- the config file and rule file, whose content is in `receipt.json`;
- attempt 1's scan and check files;
- the engine events;
- the three series scripts;
- the scan caches;
- the engine ledger;
- the NautilusTrader logs.
