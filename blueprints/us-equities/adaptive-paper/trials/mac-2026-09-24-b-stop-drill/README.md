# STOP kill-switch drill on macOS, 2026-09-24 10:30 ET: working entry canceled, recovered flat

This is the second run in the same durable ledger as `../mac-2026-09-24-a-passed/`. It used the same host, frozen tree
(`../mac-2026-09-24-a-passed/frozen-6f7a77c.SHA256SUMS`), runtime and `config-sip.json` (sha256 `3587653104e6…`),
through `scheduled_trial.sh` with trial id `mac-20260924b-stop` and `--live-dir` set.

The kill switch is the documented STOP file, `~/.local/state/native-agent-stack/alpaca-paper/STOP`
(`safety.DEFAULT_STOP`; see `../../../alpaca-paper/README.md`). Every native loop tick checks it. A present STOP
forces exit: it disables admissions, cancels every working entry and exits owned positions, and the ledger refuses
any buy reservation with `stop_blocks_entry`. `stop_drill.py` (stdlib only, no broker access) watched the live
`events.jsonl` and created STOP with `O_EXCL` as soon as the first buy intent was journaled, so the entry order would
most likely still be working at the broker. Its record is `stop-drill-trigger.json`.

Timeline, UTC, from `events.jsonl`, `ledger-readback.json` and `paper-output.json`:

| Time | Event |
|---|---|
| 14:30:11.9 | run started (preflight: 0 open orders, 0 positions) |
| 14:31:02.590 | decision: `relative_strength` target CRWV |
| 14:31:02.592 | intent `adp-mac-20260924b-stop-0000001`, CRWV buy 1 @ 87.82, journaled |
| 14:31:02.593 | submit (POST) |
| 14:31:02.605 | **STOP created** (12.6 ms after the intent) |
| 14:31:02.618 / .626 | broker `pending_new`, then `new`: the entry is working |
| 14:31:02.694 | next decision has no targets or signals; no intent follows |
| 14:31:02.696 | client-id lookup (read) |
| 14:31:02.720 | cancel (DELETE), 115 ms after STOP |
| 14:31:02.745 | broker `canceled`, 0 filled |
| 14:31:02.799 | last decision; the loop ends flat |
| 14:31:03 | `runner_rc=0` |

Result:
- Drill run: status `completed_no_signals` (no fill), rc 0, flat. It left its loop after 51.6 s of the configured
  300 s. After STOP there were 0 intents and 0 submits, and the one working entry was canceled unfilled. Totals: 1
  submit, 1 cancel, 14 reads. Reconciliation: `cash_match` and `positions_match` true, 0 open orders, 0 positions.
- `runner.py recover` (`recover-output.json`) ran at 14:31:27Z with STOP still present. It returned `passed` and
  `flat`: 0 buy submissions, 0 cancels and 0 exits needed, 0 unresolved orders, and a fresh reconciliation with 0
  open orders and 0 positions. The cash delta of −1.51 USD is the ledger's cumulative figure from trial a.
- STOP release (`stop-release.json`). No repository document prescribes a removal command; the docs only create
  STOP and state that it persists across restart. This release followed the 2026-09-23 practice
  (`../20260923j-regular-no-signals/README.md`: archived with a release record). Two conditions were checked first:
  the drill run had ended flat and reconciled, and the explicit `recover` had passed flat. The file's content was
  also confirmed to be this drill's. It was then moved out of the kill-switch path into the private run directory,
  archived and not edited.

Not covered: an exit under STOP (no position was held, because the entry never filled), a restart while STOP is
present (not re-run here; the offline suites cover `stop_blocks_entry`), and a failed cancel. `ledger-readback.json`
attributes only submits and cancels. Its window runs to the end of the ledger, so it also covers the `recover`
invocation, which sent neither; `paper-output.json` lists the run's own reads.
