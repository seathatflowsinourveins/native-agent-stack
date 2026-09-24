# Mover paper trial on macOS, 2026-09-24 14:52 ET: X1 blocked by stale quotes, `needs_attention`, **not flat**

The second Alpaca paper run of the mover trial mode, on the same Mac and paper account as
`../mac-2026-09-24-mover-a/`. It is mechanics-only: the paper candidate `10:00|G0.20|V250000|any` with its own exit
X1, a marketable limit sell at 15:58 ET. It ran on the **first version** of #205's fill fix (`d7a11b3`, frozen
archive `frozen-d7a11b3.SHA256SUMS`, 578 files). An independent review later superseded that version before merge;
this run exercised no partial fills, so the fix's code path was not reached. Frozen at 14:02 ET before any broker I/O
of this trial (`FREEZE.md`). Deviations: the 10:00 rule was scanned at trial start, and entries followed at trial start.

## Run

- **Scan (14:52:00 ET).** 12 symbols fired, and the same top five as trial A were selected (`scan.log`; the scan
  files are private, with hashes in `scan.sha256`).
- **Entries.** GRML 13 at 14.94, PFSA 67 at 2.97, APUS 37 at 5.29 and SRZN 6 at 32.25 all filled exactly at the
  quoted ask; 782.44 USD bought. GCTK was skipped (`entries_not_enabled`): no admissible quote came inside the 30 s
  entry window.
- **15:49 ET.** The market-data websocket dropped and reconnected (`paper.log`). The engine's quote marks for PFSA,
  SRZN and GCTK stopped at 15:49 and stayed there until the run ended. APUS and GRML kept updating.
- **X1 at 15:58 never sent.** PFSA and SRZN waited on `no_fresh_quote`. The transport's 3 s freshness rule for
  required symbols froze it (`adapter_frozen`).
- **Hard flatten.** It latched at 16:01:22, about 74 s after its planned 16:00:08.
  - APUS's sell was refused before the wire (`adapter_frozen`, not charged).
  - GRML's sell (13 at 14.98) was reserved and its HTTP attempt recorded at 16:01:26.789. No broker observation
    followed, and the node stopped.
- **Forced recovery.** It failed with a `TransportError`. The receipt ends `needs_attention`, `flat: false`, holding
  APUS 37, SRZN 6, GRML 13 and PFSA 67.

## Recovery attempts after the close

All three ran `mover_runner.py recover` with this trial's source. None sent an order.

| Receipt | Stream timeout | Result |
| --- | --- | --- |
| `mover-recovery.json` (16:24 ET) | 3 s (trial config) | `TransportError`, not flat |
| `mover-recovery-30s.json` (16:29 ET) | 30 s, the engine maximum (`config-mover-mac-20260924c-recover30.json`, a recorded recovery-only decision; the ledger's 3 s order gate is unchanged) | `TransportError`, not flat |
| `mover-recovery-diag.json` (16:31 ET) | 30 s, run through `recover_diag.py`, which prints each `TransportError`'s fixed internal message | `owned intent absent from complete snapshot` (transport.py:949), then `snapshot incomplete; admissions remain frozen` (:956) |

Read-only observations at 16:24–16:31 ET:
- **Alpaca paper account.** Four long positions matching the ledger, and no open orders.
- **The GRML sell's client ID.** Lookup returned **404**.
- **After-hours SIP quotes over 30 s.** APUS 58; PFSA 9, with a 15.6 s gap; GRML 11, with a 16.1 s gap; SRZN **0**.

So two things block recovery:
1. **The GRML sell's ambiguous attempt.** An attempted intent with no broker record stops recovery by design: absence
   alone never retires an attempt (`README-safety.md`, `mark_not_sent`).
2. **Required-symbol freshness.** After hours, sparse movers cannot meet it even at 30 s.

## Acceptance against the frozen criteria

- **Operational pass: not met.** The status is `needs_attention`, the account is **not flat**, and no end
  reconciliation was established.
- **Met:**
  - four entries filled exactly at the quoted ask;
  - no duplicate or unexplained broker effect;
  - the broker and the ledger agree on positions (four open legs);
  - the only unresolved intent is the GRML sell, which Alpaca has no record of;
  - `verify_mover_trial.py .` confirms the artifacts are consistent.
- **Request budget.** At most 38 trading requests in any 60 s window (523 in the trial window, including the recovery
  attempts), against 200 per minute.
- **Not observed.** The X1 exit path and fill resolution on partial fills.

## Open, and needs a decision

- **Ambiguous GRML intent.** The four paper positions stay open until `mover-mac-20260924c-0000005` is resolved.
  The engine has no operator command that retires an attempted intent on broker absence. The choice belongs to the
  trading lane and the user:
  - add a reviewed operator resolution with recorded evidence (client-ID 404 and no broker order since trial start),
    then recover at the open; or
  - close the positions at the broker and record a ledger re-baseline.

  In either case, recovery also needs dense quotes, as at the open.
- **Engine gaps shown by this run** (tracked separately):
  - the 3 s freshness freeze across all required symbols lets one sparse mover near the close block every exit,
    X1 included;
  - a hard flatten under a frozen transport leaves an attempted submit whose outcome only an operator can resolve.
- **Mover v3.** 2026-09-24 lies in the gap v3 never reads. The exposure is disclosed on #190.
- Paper fills are Alpaca's simulation. This is pipeline evidence, not an edge.
