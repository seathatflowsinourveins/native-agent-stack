# news-reversal: preregistered forward paper test of the NEWS-3 reversal

Status: **draft pending independent pre-outcome review**. It is not frozen, and no session
counts yet. Paper only; never live.

## Origin

The frozen NEWS-PIT-LLM study found item NEWS-3 (`../news-llm/receipts/RESULTS.md`; protocol
sha256 `bba1b157…`, frozen at `70bd2b84`, result `baf158eb`). Entering 15 minutes after a
regular-hours single-name headline, in the direction of the point-in-time label, and holding to
the close lost money:

- gross −11.0 bps/day long-short (t −7.16, 2,618 days, sample sd 69.9 bps, Newey-West-effective
  sd 78.7 bps);
- net −19.4 bps/day, so the modelled costs are 8.4 bps/day.

This protocol tests the **reversal**: trade against the label. The hypothesis was generated from
that run, after all five frozen items had been seen, so no historical data is clean for it. Only
prospective sessions count. The direction is fixed: reversal > 0.

**Spread caveat.** NEWS-3's gross already pays the entry half-spread (longs at the ask, shorts at
the bid, exit at the official close). The mirrored trade pays the spread as well. Its in-sample
gross is therefore about 11 − S bps/day, where S is the mean full entry spread of the two legs
(not reported by the frozen summary). The in-sample net is about 2.6 − S. See
`forward-protocol.json#/origin/spread_caveat`.

**Label skew.** The live checkpoint (2024-12-31) labels about 80–90% of directional liquid
headlines UNFAVORABLE under D22. So the reversal trades mostly longs, and the 0.10 E net cap
binds the long leg: the 2026-09-25 dry run skipped 2 of 5 eligible longs for it. Sessions with
≥ 2 short names may be rare, which would stretch the looks (limitation L-SKEW).

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
- **Exit.** CLS, with the existing 15:55 market flatten and all kill and exit machinery.
- **Sizing and caps.** As the runner has them: section-A size, 5% E per order, 12 names per leg,
  gross cap 1.0 × E (the autolev floor), net cap 0.10 E.
- **Other arms.** The momentum RTH arm becomes a shadow (journaled, never sent). The overnight
  OPG/CLS core arm keeps running, labelled `execution_test`.

## Estimands, plan and gates

- **Primary estimand.** Mean daily long-short **gross** from actual paper fills. Legs are
  equal-weight and need ≥ 2 names each; both legs are required (`news_signal.daily_portfolios`).
- **Secondary estimands.** Net (the study's 2 + 2 bps allowances plus fees), each leg, the
  execution cost and the momentum shadow. None of them decides anything.
- **Execution cost.** Two measures, both in bps of entry notional:
  - measured against the decision-time mid and the official close, compared with the frozen model
    for the same positions;
  - measured beyond the touch, per long-short day, compared with the historical 8.4 bps/day.
- **Sequential plan.**
  - Looks at 60, 125, 250 and 375 counted long-short sessions.
  - O'Brien-Fleming efficacy boundaries at one-sided α 0.05: z ≥ 4.274, 2.961, 2.094, 1.710.
  - Non-binding futility (t ≤ 0) at looks 2 and 3.
  - The last look is final. Each look is written to `receipts/look-<k>.json`.
- **Power, stated before any data.** A +11 bps/day gross effect needs about 320 sessions for 80%
  power (sd ≈ 79 bps). The plan has 85% power at +11 bps and 52% at +7 bps (S = 4). The net
  effect (about +2.6 bps/day) needs about 5,700 sessions (over 22 years) and is not tested.
- **Promotion.** Needs both an efficacy crossing and the live-rung paper-performance gate:
  - ≥ 20 sessions and ≥ 100 round trips;
  - a bootstrap lower bound > 0 on net;
  - drawdown ≤ 20%;
  - pinned costs.

  Otherwise the arm stays paper. Nothing here authorizes live trading.
- **Harm stops.**
  - The runner's kill switch.
  - Halt when the cumulative net drawdown is ≥ 10% of the average gross deployed.
  - From the 60th counted session, halt when the measured cost per round trip is > 2× the
    assumed cost.

  `analyze.py monitor --apply` writes `<state>/HALT-rth_reversal`, which blocks new reversal
  entries only.

## Files

| File | Purpose |
|---|---|
| `forward-protocol.json` | The preregistration (draft): origin, rule, data, estimands, cost measurement, counted sessions, power, sequential plan, design numbers, gates, harm stops, limitations, pins, freeze procedure |
| `analyze.py` | `design` (pure boundaries and power), `pins`, and the guarded `look` and `monitor` commands |
| `receipts/freeze-record.template.json` | Shape of the freeze record; `analyze.py` refuses the template |
| `receipts/deployment-record.template.json` | Shape of the deployment record; `analyze.py` refuses the template |
| `receipts/dryrun-20260925.json` | Sanitized counts of the pre-freeze dry run (intended decisions only; not evidence) |

`analyze.py look` and `monitor` refuse unless all of these hold:

- a freeze record and a frozen protocol with matching sha256;
- the freeze commit is an ancestor of HEAD, with a matching protocol at that commit;
- a deployment record whose commit descends from the freeze commit;
- every pin matches;
- a clean `news-reversal/` tree.

Counted sessions start at the first XNYS session that opens after both the freeze and the
deployment. Earlier journals (pilot days, pre-freeze shakedown) are never opened.

## Deployment plan (document only; not executed)

The live pilot runs from `~/code/sota-news-forward` today. Nothing below may start before today's
16:00 reconciliation has been journaled. Do each step at a quiet time: after 20:05 ET (the
service's own end) or at the weekend.

1. **Freeze first** (`forward-protocol.json#/freeze_procedure`):
   - independent review;
   - recompute the pins and design numbers;
   - set the frozen status;
   - commit and push;
   - write `receipts/freeze-record.json` and commit it.
2. **Wait for the pilot's day to end.** Confirm today's reconciliation and summary receipt
   exist:
   `~/.local/state/native-agent-stack/research/sota-mover/news-forward/receipts/2026-09-25-summary.json`
   and a `reconciliation` row in `journal/2026-09-25.jsonl`.
3. **Stop the service** (after 20:05 ET, or at the weekend):
   `systemctl --user stop news-forward.service news-forward-scorer.service`. Check
   `systemctl --user is-active news-forward.service` prints `inactive`.
4. **Point the unit at this code.** Use one of:
   - (a) fast-forward the pilot worktree:
     `git -C ~/code/sota-news-forward merge --ff-only claude/news-reversal-forward-20260925`.
     This works only if that branch has no commits of its own since `59ed0d0b`; otherwise
     use (b) or (c).
   - (b) re-point the worktree path to this branch's frozen commit.
   - (c) install unit files that point at `~/code/sota-news-reversal`: copy
     `../news-forward/systemd/news-forward.{service,timer}` to `~/.config/systemd/user/` and edit
     `WorkingDirectory` and `ExecStart` to the new path.

   Then check that the deployed tree's HEAD descends from the freeze commit and that
   `git status --porcelain` is empty.
5. **Reload units:** `systemctl --user daemon-reload`, then
   `systemctl --user cat news-forward.service` to confirm the path.
6. **Dry-run check** (a one-off process with a separate state root; nothing is sent). At the
   weekend, name the first reversal session with `--date` and stop the process with Ctrl-C
   after about a minute (SIGINT journals `stopping` and writes a summary):

   ```
   ~/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python <deployed>/blueprints/us-equities/sota-mover/news-forward/supervisor.py \
     --dry-run --date 2026-09-28 --no-scorer --rate 60 \
     --state ~/.local/state/native-agent-stack/research/sota-mover/news-reversal-dryrun-deploy
   ```

   Its journal `start` row must show:
   - `mode` `dry-run` and `rth_reversal_active` true;
   - `reversal_protocol_sha256` equal to the frozen sha256;
   - `code_sha256`, `news_signal_sha256` and `score_py_sha256` equal to `#/pins`.

   Delete that state root afterwards; it is never evidence.
7. **Account check (read-only):** from the deployed news-forward directory, run
   `~/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python executor.py check-account`.
   It must print `"verdict": "ready_for_paper"`, with only nf1-/nf1x-/nf1r- positions (none
   expected after the pilot's close-out).
8. **Paper.** `config.json` keeps `"mode": "paper"` and `rth_reversal.from` ≥ 2026-09-28. The
   timer starts the service at 03:55 ET on the next session, or run
   `systemctl --user start news-forward.service` on a session day. Write
   `receipts/deployment-record.json`:
   - `deployed_at`: the UTC start of the first unit run from the new code;
   - `deployed_commit`;
   - the working directory;
   - the check-account verdict;
   - the dry-run check.

   Commit it. The first counted session is the first session that opens after both records.
9. **Daily, after each reconciliation:** run `python analyze.py monitor --apply` (harm stops).
   At 60, 125, 250 and 375 counted long-short sessions, run `python analyze.py look` once and
   commit its receipt.

Rollback: stop the service and restore the previous worktree or unit files. The old runner does
not know the `nf1r-` prefix. Roll back only when flat: its start check would call open `nf1r-`
orders or positions foreign.
