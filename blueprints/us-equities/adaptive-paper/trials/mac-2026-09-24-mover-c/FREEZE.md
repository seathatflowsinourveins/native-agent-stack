# Freeze: mover paper trial `mover-mac-20260924c` (written before any broker I/O of this trial)

Frozen 2026-09-24 14:02 ET, after trial A ended `needs_attention` (partial-fill precision stop) and its recover proof
passed. Purpose: trial B's design on the engine with the fix, to observe it against the broker.

- Engine: a read-only `git archive` of PR #205's head `d7a11b30ca46` (`frozen-d7a11b3.SHA256SUMS`, 578 files;
  `mover-v3/` excluded). Not yet merged; the source is the published branch commit.
- Runtime, account, endpoint, state root, kill switch, numeric bounds, acceptance, shared-account and Mover v3
  notes: as in `FREEZE-mover-mac-20260924a.md`.
- Config `config-mover-mac-20260924c.json` (sha256 `5a8f941686f8…`): trial B's config with only `notes` changed:
  rule `10:00|G20|V250000|any`, `session_scope` `any_session`, `trial_end_et` `16:10`, exit `X1` (the candidate's own
  exit, a marketable limit sell at 15:58 ET).
- Start: a launcher starts the scan and trial at 14:52:00 ET. A start before 14:50:05 is refused (`mover_x1_unreachable`)
  and entries end 10 minutes before the close. Dry `check` with a synthetic scan stamped 14:52:05 ET: X1 15:58:00,
  hard flatten 16:00:05 ET. `mover_runner.py synthetic` with this config on this engine: passed, flat.
- Deviations from the candidate: the 10:00 rule is scanned at trial start, so the prefilter uses the latest trade then,
  and entries are at trial start instead of 10:00.
- Precondition (met at freeze): the mover ledger is `finished` and the account is flat (trial A's recover proof).
- Acceptance: as trial A. Additionally recorded: whether any leg filled in parts at different prices and which path
  `execution_price` took; no fill-precision stop is a pass condition only if such fills occur, otherwise it is unobserved.

---

Trial B's frozen design, which trial C reuses on the fixed engine (B itself did not start):

## Freeze: mover paper trial `mover-mac-20260924b` (written before any broker I/O of this trial)

Frozen 2026-09-24 12:46 ET, while trial A held its entries and before any of trial A's exits or P&L were read.
Everything in `FREEZE-mover-mac-20260924a.md` applies (engine archive `3699012eb6ad`, runtime lock, account,
endpoint, state root, kill switch, numeric bounds, acceptance, shared-account and Mover v3 notes), except:

- Config `config-mover-mac-20260924b.json` (sha256 `572df6f1fd2f…`): `config-mover.json` with `mover.rule`
  `10:00|G20|V250000|any`, `session_scope` `any_session`, `trial_end_et` `16:10`, `exit` `X1`, and `notes`.
- Exit X1 is the paper candidate's own exit (`10:00|G0.20|V250000|any|X1`): a marketable limit sell at 15:58 ET.
- Start window: the scan and trial start at about 14:52 ET. The plan needs the hard flatten (start + 68 min) after
  15:58, so a start before 14:50:05 is refused (`mover_x1_unreachable`), and entries end 10 minutes before the close.
  A dry `check` of this config with a synthetic scan stamped 14:52:05 ET gives X1 at 15:58:00 and the hard flatten
  at 16:00:05 ET.
- Deviations from the candidate: the 10:00 rule is scanned at trial start, so the prefilter uses the latest trade then,
  and entries are at trial start instead of 10:00.
- Precondition: trial A ended `passed` or `completed_no_signals` with the mover ledger `finished` and the account flat.
  Otherwise trial B does not start, and recovery comes first.
