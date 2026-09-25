# news-reversal: preregistered forward paper test of the NEWS-3 reversal

Status: **draft, pending independent pre-outcome review.** It is not frozen and no session counts
yet. It is labelled **exploratory** by its own pre-committed rule. Paper only; never live.

## Origin and the measured spread

The frozen NEWS-PIT-LLM study found item NEWS-3 (`../news-llm/receipts/RESULTS.md`; protocol
sha256 `bba1b157…`, frozen at `70bd2b84`, result `baf158eb`). Entering 15 minutes after a
regular-hours single-name headline, in the direction of the point-in-time label, and holding to
the close lost 11.0 bps/day gross (t −7.16, 2,618 days) and 19.4 bps/day net. The reversal (trade
against the label) was chosen after all five frozen items had been seen, so only prospective
sessions can test it. The direction is fixed: reversal > 0.

NEWS-3's gross already paid the entry half-spread: longs at the ask, shorts at the bid, exit at
the official close. The mirrored trade pays the spread too.

**Measuring S.** The rule was committed first, in `e8a3ca6a`: confirmatory only if 11.0 − S ≥ 5
bps/day, otherwise exploratory. `measure_s.py` then ran once, return-free, on the frozen study's
pinned private inputs. The results are in `receipts/s-measurement.json`:

- **S = 21.68 bps.** This is the mean over NEWS-3's 2,618 long-short days, reproduced from counts
  alone, of the two legs' mean full entry spread.
- **The planning effect is 11.01 − 21.68 = −10.67 bps/day,** and the mid-based effect about
  +0.17 bps/day. NEWS-3's loss was the entry half-spread (about 10.8 bps/day over two legs), not
  a price reversal.
- **The test is exploratory.**
- **Leg counts.** In 2025–26 (the live 2024-12-31 checkpoint), forward-like, both legs had ≥ 2
  names on 99.8% of sessions. The long leg was always at 12 names; the short leg had a median of
  12 and a mean of 10.7.
- **Forward sd.** Scaled by leg sizes, the forward daily sd is 85.1 bps (Newey-West-effective).

## Runtime (coordinator decision, 2026-09-25)

- **Why a new runtime.** The incentive engine owns paper-3 and embeds an older news-forward runner
  (`1eee5083`). The counted test therefore runs in its own runtime.
- **Config.** `runtime-config.json`: rev-only (`arms_enabled: ["rev"]`, so core, pm and ah plan and
  send nothing).
- **Account.** It trades on the dedicated `alpaca-paper-4.env` (trading and data), created by the
  user. It refuses paper-2 and paper-3 by file name and by a copied key id.
- **State root.** `~/.local/state/native-agent-stack/research/sota-mover/news-reversal`.
- **Units.** `systemd/news-reversal.service` and `.timer` point at this worktree and have their own
  scorer unit `news-reversal-scorer`. They are written, not installed.

## Rule (summary; `forward-protocol.json#/rule` is authoritative)

Scope: each liquid-lane single-name Benzinga headline released 09:30–15:30 ET that passes the
frozen filters (F1–F13, guard B on our own `received_at`) and is the first of its symbol in the
window.

- **Direction.** Trade against the operative D22 label: FAVORABLE → short, UNFAVORABLE → long.
  UNCLEAR and PARSE_FAIL → no trade.
- **Entry.** At release + 15 min, on the first quote stamped in [+15, +16] min: a marketable limit
  at the ask for a buy or the bid for a sell. Skip if the spread is over 50 bps. Cancel after 60 s.
- **Shorts.** Need shortable, easy-to-borrow and no Rule 201 flag. The flag is the study's rule
  plus today's session low; missing data fails closed.
- **Size.** Leg-balanced: per name min(section A, 0.10 E / 12). Each leg fills toward 12 names
  and the net cap cannot bind.
- **Exit.** CLS, with the 15:55 market flatten and every kill and exit path.
- **Cross-arm guard.** Rev skips any symbol another arm holds or has working, and journals a
  deviation row. It is not expected to fire on paper-4.
- **Benchmark.** Every first-in-window liquid event gets a benchmark quote and a close mark (the
  news-day benchmark).

## Estimands, plan and gates

- **Primary estimand.** Mean daily long-short **gross** from actual paper fills. Legs are
  equal-weight and need ≥ 2 names each; both legs are required. One-sided.
- **Secondary estimands** (none of them decides anything):
  - net;
  - each leg;
  - intent to treat (decision-time touch to the close mark);
  - mid-based (≈ 11 − S/2 in sample);
  - fill rate by leg;
  - long leg minus the news-day benchmark;
  - execution cost;
  - the momentum shadow.
- **Sequential plan.**
  - Looks at 60, 125, 250 and 375 counted long-short sessions.
  - Lan–DeMets O'Brien-Fleming spending at one-sided α 0.05: z ≥ 4.762, 3.200, 2.141, 1.695 at the
    planned fractions.
  - Non-binding futility (t ≤ 0) at looks 2 and 3.
  - Calendar end 2028-09-29: if 375 sessions are not reached by then, the next look is final and
    spends all remaining α.
- **Power at the planning effect (−10.67 bps/day): about 0.** Futility stops the test at look 2
  with 98.5% probability.
  - Mid-based effect (+0.17): 5.4%.
  - Confirmatory threshold (+5): 30%.
  - Spread-ignoring +11: 80%.
- **Promotion: none from this protocol.** No gate is merged. PR #183 is open and unmerged, and
  its out-of-sample and paper-performance routes judge net results under their own rules. A gross,
  sequential, exploratory test satisfies neither route. Promotion would need a separate later
  confirmatory period under #183 as merged.
- **Harm stops.**
  - The runner's kill switch.
  - The drawdown trigger (net drawdown ≥ 10% of average gross). It is simulated to fire about 3.4
    times in 375 sessions under the planning drift, so it is halt-and-review: a review within 2
    sessions that finds no execution fault resumes entries (`analyze.py resume`), and the
    drawdown is re-based.
  - The cost stop (measured cost > 2× assumed, from session 60).

## Files

| File | Purpose |
|---|---|
| `forward-protocol.json` | The preregistration (draft) |
| `runtime-config.json` | Rev-only paper-4 runtime config |
| `systemd/news-reversal.{service,timer}` | Units for this runtime (not installed) |
| `analyze.py` | `design [--harm-simulation]`, `pins`, and the guarded `look`, `monitor` and `resume` commands |
| `measure_s.py` | The return-free planning measurement (run once) |
| `receipts/s-measurement.json` | Its result and input hashes |
| `receipts/freeze-record.template.json`, `receipts/deployment-record.template.json` | Record shapes; `analyze.py` refuses the templates |
| `receipts/dryrun-20260925.json`, `receipts/dryrun-20260925b.json` | Pre-freeze dry-run verifications (intended decisions only; never evidence) |

`analyze.py look`, `monitor` and `resume` refuse unless all of these hold:

- a freeze record and a frozen protocol with matching sha256;
- the freeze commit is an ancestor of HEAD, with a matching protocol at that commit;
- a deployment record whose commit descends from the freeze commit;
- every pin matches;
- a clean `news-reversal/` tree.

A session counts only when every start row of the day shows paper mode, account paper-4, the
reversal active, the frozen protocol and the pinned code. Earlier journals are never opened. A
missed reconciliation is backfilled from broker history with `supervisor.py --reconcile-only
--date D` (read-only).

## Deployment plan (document only; not executed)

Preconditions:

- the protocol is frozen after independent review;
- the user has created `~/.config/codex-ecosystem/secrets/alpaca-paper-4.env` (mode 0600,
  `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`, a key distinct from paper-2 and paper-3);
- the paper-4 account is funded with at least $600,000. At Alpaca's default $100,000 the
  per-name cap 0.10 E / 12 is $833, below the $1,000 minimum, so no entry could trade; the runner
  journals `rev_name_cap` at every start.

Nothing touches `incentive-engine.service`, its worktree or paper-3.

1. **Freeze** (`forward-protocol.json#/freeze_procedure`):
   - recompute the pins and design numbers;
   - set the frozen status;
   - commit and push;
   - write `receipts/freeze-record.json` and commit it.
2. **Account check (read-only):** from `news-forward/`, run
   `~/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python executor.py check-account --config ../news-reversal/runtime-config.json`.
   It must print `"account": "paper-4"` and `"verdict": "ready_for_paper"`. Today it prints
   `refused:trading_env_missing`.
3. **Dry-run check** (separate state root, nothing sent): run
   `supervisor.py --config ../news-reversal/runtime-config.json --dry-run --date <first reversal session> --no-scorer --state ~/.local/state/native-agent-stack/research/sota-mover/news-reversal-dryrun-deploy`
   and stop it with Ctrl-C after a minute. Its `start` row must show:
   - `account` paper-4 and `rth_reversal_active` true;
   - the frozen `reversal_protocol_sha256`;
   - `code_sha256`, `news_signal_sha256` and `score_py_sha256` equal to the pins.

   Delete that state root afterwards.
4. **Install the units** (after 20:05 ET or at the weekend):
   - copy `systemd/news-reversal.service` and `systemd/news-reversal.timer` to
     `~/.config/systemd/user/`;
   - run `systemctl --user daemon-reload`;
   - check `systemctl --user cat news-reversal.service` shows this worktree's paths;
   - run `systemctl --user enable --now news-reversal.timer`.

   The timer starts the service at 03:55 ET on the next session.
5. **Deployment record:** write `receipts/deployment-record.json` with:
   - `deployed_at`: the UTC start of the first run from the frozen commit;
   - `deployed_commit`;
   - the working directory;
   - the check-account verdict;
   - the dry-run check.

   Commit it. The first counted session is the first session that opens after both records.
6. **Daily, after reconciliation:** run `python analyze.py monitor --apply`. After a harm halt,
   review execution within 2 sessions, then run
   `python analyze.py resume --finding no_execution_fault|execution_fault_fixed --note "..." --after-session D`.
7. **Looks:** at 60, 125, 250 and 375 counted long-short sessions, or at the calendar end, run
   `python analyze.py look` once and commit its receipt.

Rollback:

- `systemctl --user disable --now news-reversal.timer news-reversal.service`;
- remove the two unit files;
- `daemon-reload`.

Any open `nf1r-` position on paper-4 is flattened by the runner's own exit paths before the unit
is stopped.
