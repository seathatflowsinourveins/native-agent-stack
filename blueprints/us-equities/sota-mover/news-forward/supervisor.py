#!/usr/bin/env python3
"""Session-aware supervisor for the news-LLM paper pilot (one trade date per run).

Timeline (America/New_York, from the XNYS calendar, DST-aware; early closes shift the
close-relative steps):
  start (03:55 by timer)  backfill news from the previous close - 24 h (novelty warm-up);
                          start-of-day equity E and the day's run state (kill, rounds)
                          persisted per date; the day's leverage decision (autolev.py,
                          capped by adaptive-paper leverage.py)
  every 15 s              poll news, screen with the study's guards, look up the lane,
                          sigma and MDV20, queue eligible headlines for the scorer
  every 30 s (paper)      rebuild exposure from the broker's orders (fill-based, M4) and
                          check the daily-loss kill (2% of E)
  GPU schedule            scorer on the GPU only with >= 9 GB free VRAM and not before
                          08:30 unless <state>/gpu-early-ok exists and no other
                          sota-news-* unit is active; CPU fallback from 09:00
  04:15 - 09:15           pm arm: extended-hours entries at release + 15 min
  09:15 - 09:27           carry-over exits (any holding entered on an earlier date) as OPG
                          orders, then the core open-auction basket (OPG)
  09:31 - 15:40           carry-over fallback (marketable limits, every 60 s) and net-cap
                          trims (every 60 s); core RTH entries until 15:40 (M2) on pilot days
  09:45 - 15:46           from config rth_reversal.from: the preregistered rth_reversal arm
                          (../news-reversal/forward-protocol.json) instead: against the operative
                          label at release + 15 min on the first quote stamped in the entry
                          minute (releases 09:30-15:30, entries until 15:45 + 60 s); the momentum
                          decision on the same quote is journaled as a shadow, never sent
  15:40 - 15:49           CLS exits, retried every 30 s until every holding is covered (M1)
  15:55 - 16:00           a day market order for any holding still uncovered (retried)
  16:02 - 20:00           extended-hours limit flatten (bid/ask -/+0.5%, last-trade fallback)
  16:15 - 19:45           ah arm entries (only when the next session is the next day)
  after the close         reconciliation, then the daily summary receipt at 20:05
Kill (B1): once triggered, the kill is persisted for the date; every kill cycle cancels
our orders, waits for their final states and re-flattens with a new round id until the
broker shows none of our positions. Exits keep running while killed.

Modes: ``dry-run`` (no trading client; intended orders are validated, journaled and
filled in simulation at their reference price) and ``paper`` (config.json "mode":
"paper" or --mode paper, plus a verified alpaca-paper-3.env). A paper start whose account
check fails runs exit-only (exits and kill, no entries) while any of our positions is
open (M6), else as dry-run. No paper order is sent before "first_order_not_before". An
arm whose "orders_from" date is later than the trade date journals its entries only.
<state>/STOP halts all order activity; <state>/HALT-rth_reversal (written by
news-reversal/analyze.py monitor --apply on a harm stop) refuses new rth_reversal entries only.
Scores use the study's operative D22 prefix rule (news_signal.operative_score), never the
stored strict label.
"""
import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import autolev  # noqa: E402
import common  # noqa: E402
import executor as ex  # noqa: E402
import live_news  # noqa: E402
import planner  # noqa: E402
import shadow  # noqa: E402

sig = planner.sig
CORE, PM, AH, REV = planner.CORE, planner.PM, planner.AH, planner.REV
SHADOW_ARM = "core_shadow"  # journal arm of the momentum RTH decisions once the reversal runs (no orders)
HALT_REVERSAL = "HALT-rth_reversal"
STALE_EVERY_REVERSAL = timedelta(seconds=5)  # rev entries live at most REV_ENTRY_TTL (60 s)
CLOSE_MARK_TIMES = (timedelta(minutes=5), timedelta(minutes=20), timedelta(minutes=45))  # after the close
VLLM_PYTHON = os.path.expanduser("~/.local/share/codex-ecosystem/tools/vllm-0.30.0/bin/python")
GPU_MIN_FREE_MIB = 9 * 1024
KILL_CHECK_SECONDS = 30
KILL_CYCLE_RTH = timedelta(seconds=20)
KILL_CYCLE_EXT = timedelta(seconds=45)
REFRESH_EVERY = timedelta(seconds=30)
PASS_EVERY = timedelta(seconds=30)      # CLS, 15:55 market, carry-over OPG and stale-entry passes
ROUND_EVERY = timedelta(seconds=60)     # carry-over fallback and net-cap trim rounds
EXT_RETRY = timedelta(minutes=10)
ORDERS_TTL_SECONDS = 5.0
CANCEL_POLLS = 15                       # final-state polls (1 s apart) after a cancel
DEFAULT_LEDGER_EPOCH = "2026-09-24T00:00:00Z"
NEWS_FIELDS = ("id", "headline", "symbols", "source", "author", "created_at", "updated_at", "url", "received_at")
TERMINAL = planner.TERMINAL_STATUSES
STOP_REQUESTED = False


def _on_signal(*_):
    global STOP_REQUESTED
    STOP_REQUESTED = True


def load_config(path):
    with open(path, encoding="utf-8") as handle:
        cfg = json.load(handle)
    if cfg.get("mode") not in ("dry-run", "paper"):
        raise SystemExit("config mode must be dry-run or paper")
    return cfg


def reversal_active(cfg, day):
    """True when the RTH window runs the preregistered rth_reversal arm on `day`.

    config.json "rth_reversal": {"from": "YYYY-MM-DD", "enabled": true}. From that date the
    momentum RTH entries are shadow-only; before it (pilot days) the momentum arm runs as
    before. Counted sessions are decided by news-reversal/analyze.py, not by this switch.
    """
    rr = cfg.get("rth_reversal") or {}
    start = rr.get("from")
    return bool(rr.get("enabled", True)) and bool(start) and date.fromisoformat(start) <= day


def arm_orders_enabled(cfg, arm, day):
    """An arm sends entries from its configured date on; the core arm always does; the rev arm
    from rth_reversal.from."""
    if arm == CORE:
        return True
    if arm == REV:
        return reversal_active(cfg, day)
    start = ((cfg.get("arms") or {}).get(arm) or {}).get("orders_from")
    return bool(start) and date.fromisoformat(start) <= day


def protocol_sha256():
    """sha256 of news-reversal/forward-protocol.json as deployed, or None."""
    try:
        return common.sha256_file(common.REVERSAL_PROTOCOL)
    except OSError:
        return None


def git_head(path):
    """(HEAD commit, dirty flag for this directory) of the running checkout, or (None, None)."""
    try:
        head = subprocess.run(["git", "-C", path, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "-C", path, "status", "--porcelain", "--", "."], capture_output=True, text=True,
                               timeout=10).stdout.strip()
        return head or None, bool(dirty)
    except (OSError, subprocess.SubprocessError):
        return None, None


def code_digests():
    return {n: common.sha256_file(os.path.join(HERE, n)) for n in sorted(os.listdir(HERE)) if n.endswith(".py")}


def interleave(intents, refs):
    """Submission order for a basket: next from the leg that pulls the running net toward zero.

    The executor's gate checks the window's net after every single order; submitting one
    leg entirely before the other would breach the net cap mid-basket even when the final
    basket is balanced. Greedy balancing keeps the running |net| at or below the larger
    of one order's notional and the basket's final |net|.
    """
    legs = {"buy": [i for i in intents if i["side"] == "buy"], "sell": [i for i in intents if i["side"] == "sell"]}
    notional = lambda i: Decimal(i["qty"]) * refs[i["client_order_id"]]  # noqa: E731
    net, out = Decimal("0"), []
    while legs["buy"] or legs["sell"]:
        if net > 0 and legs["sell"]:
            side = "sell"
        elif net < 0 and legs["buy"]:
            side = "buy"
        elif legs["buy"] and legs["sell"]:
            side = "buy" if sum(map(notional, legs["buy"])) >= sum(map(notional, legs["sell"])) else "sell"
        else:
            side = "buy" if legs["buy"] else "sell"
        intent = legs[side].pop(0)
        net += notional(intent) if side == "buy" else -notional(intent)
        out.append(intent)
    return out


# ---------------------------------------------------------------------------------------
# GPU / scorer management (subprocess boundary; the scorer runs in its own systemd unit)
# ---------------------------------------------------------------------------------------


def gpu_free_mib():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=20, check=True).stdout
        return int(out.strip().splitlines()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def other_gpu_jobs_active():
    """Names of active sota-news-* user units (the batch scorer and any delta pass)."""
    try:
        out = subprocess.run(["systemctl", "--user", "list-units", "--state=active", "--plain", "--no-legend", "sota-news-*"],
                             capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return ["unknown"]
    return [line.split()[0] for line in out.splitlines() if line.strip()]


def unit_active(unit):
    try:
        return subprocess.run(["systemctl", "--user", "is-active", "--quiet", unit], timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def gpu_allowed(now, schedule, state_root, scorer_on_gpu):
    """(allowed, reason) under the brief's GPU schedule."""
    if scorer_on_gpu:
        return True, "already_loaded"
    before_0830 = now < planner.local_at(schedule.session, 8, 30)
    if before_0830:
        if not os.path.exists(os.path.join(state_root, "gpu-early-ok")):
            return False, "before_0830_without_gpu_early_ok"
        others = other_gpu_jobs_active()
        if others:
            return False, "other_gpu_jobs_active"
    free = gpu_free_mib()
    if free is None:
        return False, "nvidia_smi_unavailable"
    if free < GPU_MIN_FREE_MIB:
        return False, f"gpu_free_{free}_mib_below_9216"
    return True, "ok"


class ScorerManager:
    def __init__(self, state_root, unit, journal, cpu_fallback_at, enabled=True):
        self.state_root = state_root
        self.unit = unit
        self.journal = journal
        self.cpu_fallback_at = cpu_fallback_at
        self.enabled = enabled
        self.device = None
        self.last_check = None
        self.last_reason = None

    def stop(self):
        if self.device and unit_active(self.unit):
            subprocess.run(["systemctl", "--user", "stop", self.unit], timeout=60)
        self.device = None

    def launch(self, device, idle_exit):
        if not shutil.which("systemd-run"):
            self.journal.write("lifecycle", event="scorer_launch_failed", reason="systemd_run_missing")
            return
        cmd = ["systemd-run", "--user", "--collect", "--unit", self.unit,
               "-p", "MemoryMax=9G", "-p", "MemoryHigh=8G", "-p", "MemorySwapMax=0", "-p", "Nice=5",
               VLLM_PYTHON, os.path.join(HERE, "live_score.py"), "--state", self.state_root,
               "--device", device, "--idle-exit", str(idle_exit)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        self.device = device if result.returncode == 0 else None
        self.journal.write("lifecycle", event="scorer_launch", device=device, idle_exit=idle_exit,
                           unit=self.unit, returncode=result.returncode, stderr=result.stderr[-300:])

    def tick(self, now, schedule, pending):
        if not self.enabled:
            return
        if self.last_check and now - self.last_check < timedelta(seconds=30):
            return
        self.last_check = now
        running = self.device is not None and unit_active(self.unit)
        if not running:
            self.device = None
        if pending == 0 and not running:
            return
        allowed, reason = gpu_allowed(now, schedule, self.state_root, self.device == "cuda" and running)
        if reason != self.last_reason:
            self.journal.write("lifecycle", event="gpu_gate", allowed=allowed, reason=reason, pending=pending)
            self.last_reason = reason
        resident = now >= planner.local_at(schedule.session, 8, 30)
        if allowed and self.device != "cuda":
            if running:
                self.stop()
            self.launch("cuda", 0 if resident else 120)
        elif not allowed and not running and pending and now >= self.cpu_fallback_at:
            self.launch("cpu", 600)


# ---------------------------------------------------------------------------------------
# Persistent per-date state
# ---------------------------------------------------------------------------------------


def _json_file(path, default=None):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def _write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True, default=str)
    os.replace(tmp, path)


class RunState:
    """Per-date, per-mode state that survives a restart (B1 kill, m2 round counters)."""

    DEFAULTS = {"killed": False, "killed_at": None, "kill_reason": None, "kill_round": 0, "cls_round": 0,
                "mkt_round": 0, "ext_round": 0, "xopg_round": 0, "cof_round": 0, "trim_round": 0, "xca_round": 0}

    def __init__(self, path):
        self.path = path
        self.data = {**self.DEFAULTS, **(_json_file(path) or {})}

    def get(self, key):
        return self.data[key]

    def update(self, **fields):
        self.data.update(fields)
        _write_json(self.path, self.data)

    def bump(self, key):
        self.update(**{key: int(self.data[key]) + 1})
        return self.data[key]


# ---------------------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------------------


class Supervisor:
    def __init__(self, args, cfg, clock=common.utc_now):
        self.args = args
        self.cfg = cfg
        self.clock = clock
        self.state = args.state
        os.makedirs(self.state, exist_ok=True)
        self.calendar = common.load_calendar()
        now = clock()
        self.trade_date = args.date or now.astimezone(common.NY).date()
        if not planner.is_session(self.calendar, self.trade_date):
            raise SystemExit(f"{self.trade_date} is not an XNYS session; nothing to do")
        self.schedule = planner.day_schedule(self.calendar, self.trade_date)
        self.prev_session = self.calendar.previous(self.trade_date)
        self.end = args.until or self.schedule.service_end
        self.reversal = reversal_active(cfg, self.trade_date)
        self.journal = common.Journal(self.state, self.trade_date, clock=clock,
                                      evidence_label=common.REVERSAL_RUN_LABEL if self.reversal else common.EVIDENCE_LABEL)
        self.ledger_epoch = sig.as_utc(cfg.get("ledger_epoch", DEFAULT_LEDGER_EPOCH))
        key, secret = live_news.read_credentials(common.DATA_ENV)
        self.data = live_news.DataClient(key, secret, limiter=live_news.RateLimiter(args.rate))
        self._ca_keys = (key, secret)  # corporate-action lookups (alpaca-py data client)
        del key, secret
        self.requested_mode = args.mode or cfg["mode"]
        broker, account, exit_only, mode, verdict = self.open_account()
        self.mode = mode
        self.account_verdict = verdict
        self.runstate = RunState(os.path.join(self.state, "runstate", f"{self.trade_date.isoformat()}-{mode}.json"))
        self.sod = self.start_of_day(account)
        self.equity = Decimal(str(self.sod["equity"]))
        self.leverage_decisions()
        not_before = cfg.get("first_order_not_before")
        not_before = sig.as_utc(not_before) if not_before else None
        gate = ex.RiskGate(self.limits, self.account_gross_cap)
        self.executor = ex.Executor(mode, self.journal, self.state, broker=broker, clock=clock, not_before=not_before,
                                    gate=gate, exit_only=exit_only)
        self.executor.killed = bool(self.runstate.get("killed"))
        self.ref_path = os.path.join(self.state, "ref-prices", f"{self.trade_date.isoformat()}-{mode}.json")
        self.executor.ref_prices = _json_file(self.ref_path, {}) or {}
        self.exposures = {arm: planner.Exposure() for arm in planner.ARM_PREFIX}
        self._init_runtime()
        assets = self.data.assets()
        self.assets = assets
        self.screener = planner.Screener(self.calendar, assets)
        backfill_from = self.prev_session.close_utc - timedelta(hours=24)
        self.poller = live_news.NewsPoller(self.data, backfill_from, clock=clock, first_received=self.first_received_today())
        self.queue_path = os.path.join(self.state, "score-queue.jsonl")
        self.scores_path = os.path.join(self.state, "scores.jsonl")
        # dry-run verification only: score rows read (never written) from another state, e.g. the running service's
        self.extra_scores_path = getattr(args, "scores_from", None)
        for row in common.read_jsonl(self.scores_path):
            self.scores[row["event_id"]] = row
        self.queued = {r["event_id"] for r in common.read_jsonl(self.queue_path) if "event_id" in r}
        cpu_at = args.cpu_fallback_at or planner.local_at(self.trade_date, 9, 0)
        self.scorers = ScorerManager(self.state, args.scorer_unit, self.journal, cpu_at, enabled=not args.no_scorer)
        self.git_head, self.git_dirty = git_head(HERE)
        self.code_sha256 = code_digests()
        self.refresh(now, force=True)  # M4/m4: exposure rebuilt from the broker's orders at start
        config_path = args.config
        self.journal.write("lifecycle", event="start", trade_date=self.trade_date.isoformat(),
                           requested_mode=self.requested_mode, mode=self.mode, account_verdict=self.account_verdict,
                           exit_only=self.executor.exit_only, killed=self.executor.killed, runstate=self.runstate.data,
                           end=common.iso(self.end), assets=len(assets),
                           schedule={k: common.iso(v) if isinstance(v, datetime) else str(v) for k, v in self.schedule.__dict__.items()},
                           config=cfg, config_sha256=common.sha256_file(config_path),
                           arms_orders_enabled={a: arm_orders_enabled(cfg, a, self.trade_date) for a in planner.ARM_PREFIX},
                           arm_labels=dict(planner.ARM_LABEL),
                           git_head=self.git_head, git_dirty=self.git_dirty, code_sha256=self.code_sha256,
                           news_signal_sha256=common.sha256_file(os.path.join(common.NEWS_LLM, "news_signal.py")),
                           score_py_sha256=common.sha256_file(os.path.join(common.NEWS_LLM, "score.py")),
                           rth_reversal_active=self.reversal, reversal_protocol_sha256=protocol_sha256(),
                           scores_from=self.extra_scores_path,
                           strategy=common.REVERSAL_STRATEGY_ID if self.reversal else common.STRATEGY_ID, sod=self.sod,
                           exposure={a: str(x.gross) for a, x in self.exposures.items()})
        if self.executor.killed:
            self.journal.write("risk", event="kill_restored", killed_at=self.runstate.get("killed_at"),
                               kill_round=self.runstate.get("kill_round"))
        if self.mode == "paper":
            self.journal.write("lifecycle", event="paper_mode_enabled", switched_at=common.iso(now),
                               flag="config.json mode=paper" if not args.mode else "--mode paper",
                               exit_only=self.executor.exit_only, config_sha256=common.sha256_file(config_path),
                               first_order_not_before=common.iso(not_before), account_verdict=self.account_verdict)

    def _init_runtime(self):
        """Caches, timers and per-run bookkeeping (also used by tests to build a bare supervisor)."""
        self.sleep = time.sleep
        self.cancel_polls = CANCEL_POLLS
        self.orders_cache, self.orders_at = None, None
        self.hs = {}
        self.first_poll = True
        self.scores_offset = 0
        self.extra_scores_offset = 0
        self.extra_scores_path = getattr(self, "extra_scores_path", None)
        self.reversal = getattr(self, "reversal", False)
        self.l_rev = getattr(self, "l_rev", autolev.L_FLOOR)
        self.shadow_exposure = planner.Exposure()  # the momentum shadow's own caps (never the real arms')
        self.rev_state = {}           # event_id -> {"done": {arm, ...}, "asset", "target"} while an RTH event is evaluated
        self.rev_working_until = None  # rev entries may be working until then: stale checks every 5 s
        self.close_marks_done = set()
        self.scores = {}
        self.candidates = {}
        self.bars, self.lanes, self.sigmas = {}, {}, {}
        self.adj_bars = {}  # (symbol, session) -> split-adjusted bars of the two prior sessions (Rule 201 carry-over)
        self.lane_retry = []
        self.announced = set()
        self.shadow = shadow.ShadowTracker()
        self.open_pool, self.rth_pending = {}, {}
        self.arm_pending = {PM: {}, AH: {}}
        self.done_steps = set()
        self.notes_logged = set()
        self.last = {}
        self.last_news = None
        self.halted_logged = False
        self.entries_cancelled_for_close = False
        self.kill_flat_logged = False
        self.last_net_actual = None
        self.counts = Counter()

    def first_received_today(self):
        """news id -> the first received_at journaled today (restart-safe input to guard B)."""
        out = {}
        for r in common.read_jsonl(self.journal.path):
            if r.get("kind") == "news" and r.get("received_at") and r.get("id") is not None:
                out.setdefault(str(r["id"]), r["received_at"])
        return out

    # -- account binding (M6) --------------------------------------------------------

    def open_account(self):
        """(broker, account, exit_only, mode, verdict) for the requested mode.

        A failed start check with any of our positions open (or unknowable) runs exit-only
        paper: exits and the kill stay active, entries are refused. Without our positions
        it falls back to dry-run, journaled. Refused credentials cannot see the account at
        all: dry-run, with a risk record that positions are unknown.
        """
        if self.requested_mode != "paper":
            return None, None, False, "dry-run", "not_checked"
        try:
            k, s = ex.trading_credentials()
            broker = ex.AlpacaBroker(ex.make_trading_client(k, s))
            del k, s
        except ex.AccountRefused as error:
            self.journal.write("risk", event="paper_requested_but_account_unavailable", reason=str(error),
                               note="positions unknown; running dry-run")
            return None, None, False, "dry-run", f"refused:{error}"
        try:
            return broker, ex.start_check(broker), False, "paper", "ready_for_paper"
        except ex.AccountRefused as error:
            try:
                hs = planner.holdings(broker.all_orders(self.ledger_epoch))
                ours = planner.nf1_positions(hs, broker.positions())
                known = True
            except Exception:  # noqa: BLE001 - unknowable: fail closed to exit-only
                ours, known = [], False
            if ours or not known:
                self.journal.write("risk", event="exit_only_mode", reason=str(error), positions_known=known,
                                   our_positions=[{"arm": k[0], "entry_date": k[1].isoformat(), "symbol": k[2], "qty": str(q)}
                                                  for k, q in ours])
                return broker, broker.account(), True, "paper", f"exit_only:{error}"
            self.journal.write("risk", event="paper_refused_no_positions", reason=str(error))
            return None, None, False, "dry-run", f"refused:{error}"

    # -- equity, drawdown and leverage -------------------------------------------------

    def start_of_day(self, account):
        """E: persisted once per trade date and mode, so a restart keeps the same E and kill base."""
        path = os.path.join(self.state, "sod", f"{self.trade_date.isoformat()}-{self.mode}.json")
        saved = _json_file(path)
        if saved:
            return saved
        if self.mode == "paper":
            snap = {"equity": account["equity"], "cash": account["cash"], "multiplier": account.get("multiplier"),
                    "last_equity": account.get("last_equity"), "source": "paper_account", "at": common.iso(self.clock())}
        else:
            eq = str(self.cfg.get("dry_run_equity", "100000"))
            snap = {"equity": eq, "cash": eq, "multiplier": str(self.cfg.get("dry_run_multiplier", "4")),
                    "source": "config_dry_run", "at": common.iso(self.clock())}
        _write_json(path, snap)
        return snap

    def leverage_decisions(self):
        peak_path = os.path.join(self.state, f"equity-peak-{self.mode}.json")
        peak = Decimal(str((_json_file(peak_path) or {}).get("peak", self.sod["equity"])))
        peak = max(peak, self.equity)
        dd = autolev.drawdown_fraction(peak, self.equity)
        rows = common.read_jsonl(os.path.join(self.state, f"autolev-daily-{self.mode}.jsonl"))
        mult = self.sod.get("multiplier")
        self.l_core, core_inputs = autolev.decide(rows, equity=self.equity, session="RTH", drawdown_fraction=dd,
                                                  kill_switch=bool(self.runstate.get("killed")),
                                                  account_multiplier=mult, overnight=False)
        # rth_reversal: the autolev floor (1.0) under the same leverage.py caps; no evidence rows are passed,
        # so sizing never responds to interim outcomes during the sequential test (forward-protocol.json).
        self.l_rev, rev_inputs = autolev.decide([], equity=self.equity, session="RTH", drawdown_fraction=dd,
                                                kill_switch=bool(self.runstate.get("killed")),
                                                account_multiplier=mult, overnight=False)
        account_ceiling = autolev.policy_ceiling(equity=self.equity, session="RTH", drawdown_fraction=dd,
                                                 kill_switch=False, account_multiplier=mult, overnight=False)
        pre_ceiling = autolev.policy_ceiling(equity=self.equity, session="PRE", drawdown_fraction=dd,
                                             kill_switch=False, account_multiplier=mult, overnight=False)
        post_overnight = autolev.policy_ceiling(equity=self.equity, session="POST", drawdown_fraction=dd,
                                                kill_switch=False, account_multiplier=mult, overnight=True)
        self.account_gross_cap = account_ceiling * self.equity
        self.limits = {
            CORE: planner.Limits.for_arm(CORE, self.equity, self.l_core),
            PM: planner.Limits.for_arm(PM, self.equity, self.l_core, extra_cap=pre_ceiling * self.equity),
            AH: planner.Limits.for_arm(AH, self.equity, self.l_core, extra_cap=post_overnight * self.equity),
            REV: planner.Limits.for_arm(REV, self.equity, self.l_rev),
        }
        self.journal.write("leverage_decision", trade_date=self.trade_date.isoformat(), peak_equity=str(peak),
                           autolev=core_inputs, autolev_rev=rev_inputs, rth_reversal_active=self.reversal,
                           account_ceiling=str(account_ceiling), pre_ceiling=str(pre_ceiling),
                           post_overnight_ceiling=str(post_overnight), account_gross_cap=str(self.account_gross_cap),
                           limits={a: {"gross_cap": str(v.gross_cap), "per_order_cap": str(v.per_order_cap),
                                       "net_cap": str(v.net_cap)} for a, v in self.limits.items()},
                           kill_loss_fraction=str(planner.KILL_LOSS_FRACTION))

    def account_gross(self):
        return [sum((e.gross for e in self.exposures.values()), Decimal("0")), self.account_gross_cap]

    # -- orders, holdings and exposure (M4, M5, m4, m5) ---------------------------------

    def all_orders(self, force=False):
        """Our order history (paper: paginated since the ledger epoch, cached 5 s; dry-run: simulated)."""
        if self.mode != "paper":
            return list(self.executor.submitted.values())
        tick = time.monotonic()
        if force or self.orders_cache is None or tick - self.orders_at > ORDERS_TTL_SECONDS:
            self.orders_cache = self.executor.broker.all_orders(self.ledger_epoch)
            self.orders_at = tick
        return self.orders_cache

    def invalidate(self):
        self.orders_cache = None

    def holdings(self, force=True):
        self.hs = planner.holdings(self.all_orders(force), self.executor.ref_prices)
        return self.hs

    def positions(self):
        if self.mode == "paper":
            return self.executor.broker.positions()
        return planner.simulated_positions(self.hs)

    def open_orders(self):
        if self.mode != "paper":
            return []
        return [o for o in self.executor.broker.orders("open") if planner.is_nf1(o.get("client_order_id"))]

    def refresh(self, now, force=False):
        """Fill-based exposure per arm (M4) from the order history, synced into the executor's gate."""
        if not force and self.last.get("refresh") and now - self.last["refresh"] < REFRESH_EVERY:
            return
        self.last["refresh"] = now
        hs = self.holdings(force=True)
        for arm in planner.ARM_PREFIX:
            self.exposures[arm] = planner.exposure_from(hs, arm, self.trade_date, self.limits[arm].per_order_cap)
        self.executor.gate.sync(self.exposures)
        actual = {}
        for arm, windows in ((CORE, (planner.OPEN_AUCTION, planner.RTH)), (PM, (planner.EXT_PRE,)), (AH, (planner.EXT_POST,)),
                             (REV, (planner.RTH,))):
            for window in windows:
                long_n, short_n, pending = planner.window_net_filled(hs, arm, self.trade_date, window)
                if long_n or short_n or pending:
                    actual[f"{arm}:{window}"] = {"long": str(long_n), "short": str(short_n), "net": str(long_n - short_n),
                                                 "pending_entries": pending, "net_cap": str(self.limits[arm].net_cap)}
        if actual != self.last_net_actual:
            self.last_net_actual = actual
            if actual:
                self.journal.write("net_actual", windows=actual, gross={a: str(x.gross) for a, x in self.exposures.items()})

    def save_ref_prices(self):
        _write_json(self.ref_path, self.executor.ref_prices)

    # -- news, screening, lanes, scoring queue ------------------------------------------

    def ensure_lanes(self, cands):
        need = sorted({(c["symbol"], c["session"]) for c in cands if (c["symbol"], c["session"]) not in self.lanes})
        by_session = {}
        for sym, sess in need:
            by_session.setdefault(sess, []).append(sym)
        for sess, syms in by_session.items():
            sd = date.fromisoformat(sess)
            prior = self.calendar.prior_sessions(sd, sig.LOOKBACK_SESSIONS + 1)
            if not prior:
                for s in syms:
                    self.lanes[(s, sess)] = (None, None, None, False)
                    self.sigmas[(s, sess)] = None
                continue
            bars = self.data.daily_bars(syms, prior[0], prior[-1])
            # the study's Rule 201 carry-over reads split-adjusted bars of the two prior sessions
            adjusted = self.data.daily_bars(syms, prior[-2], prior[-1], adjustment="split")
            for s in syms:
                self.bars[(s, sess)] = bars.get(s, [])
                self.adj_bars[(s, sess)] = adjusted.get(s, [])
                self.lanes[(s, sess)] = planner.lane_from_bars(self.calendar, sd, bars.get(s, []))
                self.sigmas[(s, sess)] = planner.sigma_from_bars(self.calendar, sd, bars.get(s, []))

    def poll_news(self, now):
        articles = self.poller.poll()
        backfill = self.first_poll
        self.first_poll = False
        fresh = []
        for a in articles:
            self.counts["news_received"] += 1
            if not backfill:
                self.counts["news_received_live"] += 1
            self.journal.write("news", backfill=backfill, **{k: a.get(k) for k in NEWS_FIELDS})
            cand, reason = self.screener.screen(a)
            self.journal.write("eligibility", news_id=str(a.get("id")), reason=reason,
                               symbol=(cand or {}).get("symbol"), session_label=(cand or {}).get("session_label"))
            if cand is None:
                continue
            self.counts["screen_pass"] += 1
            if date.fromisoformat(cand["session"]) < self.trade_date:
                continue  # an earlier session's window: novelty warm-up only
            cand["received_at"] = a.get("received_at")
            cand["backfill"] = backfill
            cand["ext_segment"] = planner.extended_segment(self.calendar, cand["created_at"])
            cand["arm_release"] = planner.arm_for_release(self.calendar, cand["created_at"])
            fresh.append(cand)
        fresh = self.lane_retry + fresh
        self.lane_retry = []
        if fresh:
            try:
                self.ensure_lanes(fresh)
            except RuntimeError as error:  # m5: keep the candidates and retry at the next poll
                self.lane_retry = fresh[-500:]
                self.journal.write("lifecycle", event="lane_fetch_failed", error=str(error)[:200], requeued=len(self.lane_retry))
                return
        for cand in fresh:
            key = (cand["symbol"], cand["session"])
            lane, prior_close, med20, complete = self.lanes[key]
            cand.update(lane=lane, prior_close=prior_close, prior_median_dollar_volume_20=med20,
                        prior_bars_complete=complete, sigma=self.sigmas.get(key))
            if lane is None:
                self.journal.write("eligibility", news_id=cand["news_id"], symbol=cand["symbol"], reason="drop_not_eligible_lane",
                                   session_label=cand["session_label"])
                continue
            self.counts["eligible"] += 1
            self.counts[f"eligible:{cand['session_label']}:{lane}"] += 1
            self.candidates[cand["event_id"]] = cand
            self.journal.write("candidate", **cand)
            if cand["event_id"] not in self.queued:
                common.append_jsonl(self.queue_path, cand)
                self.queued.add(cand["event_id"])

    def _read_new_rows(self, path, offset_attr):
        """Complete lines appended to `path` since the stored offset (read-only)."""
        if not path or not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as handle:
            handle.seek(getattr(self, offset_attr))
            data = handle.read()
        cut = data.rfind("\n") + 1
        setattr(self, offset_attr, getattr(self, offset_attr) + len(data[:cut].encode("utf-8")))
        rows = []
        for line in data[:cut].splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
        return rows

    def read_scores(self, now):
        for row in self._read_new_rows(self.scores_path, "scores_offset"):
            self.scores[row["event_id"]] = row
        for row in self._read_new_rows(self.extra_scores_path, "extra_scores_offset"):
            # dry-run verification: another state's rows fill only events this run has no own row for
            if row.get("event_id") and row["event_id"] not in self.scores:
                self.scores[row["event_id"]] = {**row, "score_source": "external"}
        for eid, cand in self.candidates.items():
            if eid in self.announced or eid not in self.scores:
                continue
            self.announced.add(eid)
            row = self.scores[eid]
            # the study's operative D22 prefix rule; the stored strict label is journaled beside it
            label, score, rule = planner.operative_label(row)
            cand.update(label=label, score=score, label_rule=rule, strict_label=row.get("label"))
            self.counts["scored"] += 1
            self.counts[f"label:{cand['session_label']}:{cand['lane']}:{label}"] += 1
            received = sig.as_utc(cand["received_at"])
            self.journal.write("score", event_id=eid, symbol=cand["symbol"], session_label=cand["session_label"],
                               ext_segment=cand["ext_segment"], arm_release=cand["arm_release"], lane=cand["lane"],
                               label=label, score=score, label_rule=rule, strict_label=row.get("label"),
                               strict_score=row.get("score"), device=row.get("device"),
                               raw_output=row.get("raw_output"), stop=row.get("stop"), revision=row.get("revision"),
                               variant=row.get("variant"), score_source=row.get("score_source", "own"),
                               seconds_after_receipt=round((now - received).total_seconds(), 1))
            if cand["ext_segment"] in (planner.EXT_PRE, planner.EXT_POST) or cand["lane"] == sig.SMALL:
                reason = "extended_hours" if cand["ext_segment"] in (planner.EXT_PRE, planner.EXT_POST) else "small_lane"
                self.shadow.add(cand, reason, received)
            created_day = sig.as_utc(cand["created_at"]).astimezone(common.NY).date()
            arm = cand.get("arm_release")
            if arm in (PM, AH) and created_day == self.trade_date and cand["lane"] == sig.LIQUID:
                entry = sig.as_utc(cand["created_at"]) + sig.RTH_ENTRY_DELAY
                self.arm_pending[arm][eid] = {**cand, "entry_utc": common.iso(entry)}
            if cand["session"] != self.trade_date.isoformat():
                continue  # the core trade belongs to the run for its own session
            if cand["session_label"] == planner.OPEN_AUCTION:
                self.open_pool[eid] = cand
            elif cand["session_label"] == planner.RTH:
                self.rth_pending[eid] = cand

    def pending_scores(self):
        return len([e for e in self.queued if e not in self.scores])

    # -- market data helpers -----------------------------------------------------------

    def fresh_asset(self, symbol):
        try:
            return self.data.asset(symbol)
        except RuntimeError:
            return None

    def ssr_for(self, cand, today_low=None):
        key = (cand["symbol"], cand["session"])
        return planner.ssr_active(self.calendar, date.fromisoformat(cand["session"]), self.bars.get(key, []), today_low,
                                  adj_bars=self.adj_bars.get(key))

    def ssr_state_for(self, cand, quote, today_low=None):
        key = (cand["symbol"], cand["session"])
        return planner.ssr_state(self.calendar, date.fromisoformat(cand["session"]), self.bars.get(key, []),
                                 adj_bars=self.adj_bars.get(key), entry_quote=quote, today_low=today_low)

    def session_low(self, snap):
        """Lowest same-day price in a snapshot: today's daily bar low, minute bar low and last trade (M7)."""
        lows = []
        for field, key in (("dailyBar", "l"), ("minuteBar", "l"), ("latestTrade", "p")):
            item = (snap or {}).get(field) or {}
            if item.get("t") and item.get(key) and sig.as_utc(item["t"]).astimezone(common.NY).date() == self.trade_date:
                lows.append(Decimal(str(item[key])))
        return min(lows) if lows else None

    def target(self, cand, fraction=Decimal("1")):
        return planner.risk_notional(self.equity, cand.get("sigma"), cand.get("prior_median_dollar_volume_20"), fraction)

    def exit_quotes(self, symbols):
        """{symbol: (latest quote, last trade price)} for marketable exit limits (B1 fallback)."""
        if not symbols:
            return {}
        try:
            snaps = self.data.snapshots(sorted(set(symbols)))
        except RuntimeError as error:
            self.journal.write("risk", event="exit_quote_fetch_failed", error=str(error)[:200])
            return {}
        return {s: ((snap or {}).get("latestQuote") or {}, ((snap or {}).get("latestTrade") or {}).get("p"))
                for s, snap in snaps.items()}

    # -- sending and cancelling --------------------------------------------------------

    def send(self, intent, context, arm=CORE, deadline=None):
        purpose = context.get("purpose")
        dry = purpose == "entry" and not arm_orders_enabled(self.cfg, arm, self.trade_date)
        order = self.executor.send(intent, {**context, "arm": arm, "arm_label": planner.ARM_LABEL[arm]},
                                   dry_run=dry, deadline=deadline)
        if order is not None:
            self.counts[f"orders_{'dry-run' if dry else self.mode}:{arm}:{context.get('session_label')}:{purpose}"] += 1
            self.invalidate()
            if purpose == "entry":
                self.save_ref_prices()
        return order

    def cancel_and_wait(self, orders, reason):
        """Cancel orders, then poll until none is live (B1, m3). False if any is still live."""
        if self.mode != "paper" or not orders:
            return True
        ids = set()
        for o in orders:
            ids.add(o["id"])
            try:
                self.executor.broker.cancel(o["id"])
                self.journal.write("order_cancel", client_order_id=o.get("client_order_id"), symbol=o.get("symbol"), reason=reason)
            except Exception as error:  # noqa: BLE001 - it may already be final; the poll decides
                self.journal.write("order_cancel_failed", client_order_id=o.get("client_order_id"), error=str(error)[:200])
        self.invalidate()
        for _ in range(self.cancel_polls):
            live = {o["id"] for o in self.executor.broker.orders("open")}
            if not live & ids:
                return True
            self.sleep(1.0)
        self.journal.write("risk", event="cancel_not_final", reason=reason, order_ids=sorted(live & ids))
        return False

    def note_once(self, key, kind, **fields):
        if key not in self.notes_logged:
            self.notes_logged.add(key)
            self.journal.write(kind, **fields)

    def due(self, name, now, every):
        last = self.last.get(name)
        if last is not None and now - last < every:
            return False
        self.last[name] = now
        return True

    def closeout_include(self):
        """Every holding except tonight's ah entries (the arm's one-night hold)."""
        today = self.trade_date
        return lambda key, h: not (key[0] == AH and key[1] == today)

    def send_exits(self, plan, stage, now, *, market=False, tif=None, extended=False, deadline=None, purpose="exit",
                   session_label="close"):
        """Send planned exits [(key, signed qty)]; limits price at the quote with a last-trade fallback."""
        quotes = {} if market else self.exit_quotes([k[2] for k, _ in plan])
        sent = 0
        for key, qty in plan:
            price = None
            if not market:
                quote, last_trade = quotes.get(key[2], ({}, None))
                price = planner.marketable_exit_price(qty, quote, last_trade)
                if price is None:
                    self.journal.write("risk", event="exit_no_price", stage=stage, symbol=key[2], arm=key[0])
                    continue
            intent = planner.exit_intent(key[1], stage, key[2], qty, limit_price=price, extended=extended, arm=key[0], tif=tif)
            if self.send(intent, {"purpose": purpose, "session_label": session_label, "stage": stage,
                                  "entry_date": key[1].isoformat()}, arm=key[0], deadline=deadline) is not None:
                sent += 1
        return sent

    # -- kill switch (B1) ----------------------------------------------------------------

    def kill_check(self, now):
        if self.mode != "paper":
            return
        if not self.executor.killed and self.due("kill_check", now, timedelta(seconds=KILL_CHECK_SECONDS)):
            account = self.executor.broker.account()
            if planner.kill_switch_triggered(self.sod.get("equity"), account.get("equity")):
                self.executor.killed = True
                self.runstate.update(killed=True, killed_at=common.iso(now), kill_reason="daily_loss",
                                     kill_equity=str(account.get("equity")))
                self.journal.write("risk", event="kill_switch", sod_equity=self.sod.get("equity"), equity=account.get("equity"),
                                   threshold=str(planner.KILL_LOSS_FRACTION))
        if self.executor.killed:
            self.kill_cycle(now)

    def kill_cycle(self, now):
        """Cancel our orders, wait for final states, re-flatten with a new round id; repeat until flat."""
        rth = self.schedule.open_utc <= now < self.schedule.close_utc
        if not self.due("kill_cycle", now, KILL_CYCLE_RTH if rth else KILL_CYCLE_EXT):
            return
        if not (self.schedule.premarket_start <= now < self.schedule.ext_end):
            self.note_once(f"kill_wait:{now.astimezone(common.NY).date()}", "risk", event="kill_waiting_for_trading_hours")
            return
        hs = self.holdings()
        held = planner.nf1_positions(hs, self.positions())
        live = self.open_orders()
        if not held:
            entries = [o for o in live if (lambda i: i and planner.is_entry(i, o.get("side")))(planner.parse_cid(o["client_order_id"]))]
            if entries:
                self.cancel_and_wait(entries, "kill_entries")
            if not self.kill_flat_logged:
                self.kill_flat_logged = True
                self.journal.write("risk", event="kill_flat", kill_round=self.runstate.get("kill_round"))
            return
        self.kill_flat_logged = False
        if live and not self.cancel_and_wait(live, "kill"):
            self.journal.write("risk", event="kill_cancel_pending", kill_round=self.runstate.get("kill_round"))
            return
        hs = self.holdings()
        plan, notes = planner.exit_plan(hs, self.positions(), lambda k, h: True)
        n = self.runstate.bump("kill_round")
        self.journal.write("risk", event="kill_round", kill_round=n, positions=[{"arm": k[0], "symbol": k[2], "qty": str(q)} for k, q in plan],
                           notes=notes)
        self.send_exits(plan, f"kill{n}", now, market=rth, extended=not rth, deadline=self.schedule.ext_end,
                        purpose="kill_flatten", session_label="kill")

    # -- entries -------------------------------------------------------------------------

    def run_open_basket(self, now):
        pool = list(self.open_pool.values())
        unscored = [c for c in self.candidates.values() if c["session"] == self.trade_date.isoformat()
                    and c["session_label"] == planner.OPEN_AUCTION and c["event_id"] not in self.scores]
        if unscored and now < self.schedule.opg_submit_by - timedelta(minutes=3):
            return False  # wait for the backlog, up to 09:24
        for c in unscored:
            self.journal.write("decision", event_id=c["event_id"], symbol=c["symbol"], session_label=planner.OPEN_AUCTION,
                               lane=c["lane"], action="skip", reason="unscored_at_basket_cutoff", arm=CORE)
        hs = self.holdings()
        blocked = {k[2] for k, h in hs.items() if k[1] < self.trade_date and h["qty"] != 0}  # carry-over exits
        symbols = sorted({c["symbol"] for c in pool if c.get("lane") == sig.LIQUID})
        snaps = self.data.snapshots(symbols) if symbols else {}
        events = []
        for c in pool:
            snap = snaps.get(c["symbol"]) or {}
            asset = self.fresh_asset(c["symbol"]) if c.get("lane") == sig.LIQUID else None
            events.append({**c, "quote": snap.get("latestQuote") or {}, "asset": asset or {},
                           "ssr": self.ssr_for(c, self.session_low(snap)), "target_notional": self.target(c)})
        decisions, intents, net_record = planner.build_open_basket(events, self.trade_date, self.exposures[CORE],
                                                                   self.limits[CORE], account_gross=self.account_gross(),
                                                                   blocked=blocked)
        self.journal.write("net_cap", **net_record)
        refs = {}
        for d in decisions:
            self.journal.write("decision", **d)
            self.counts[f"decision:core:{d['session_label']}:{d['action']}"] += 1
            if d["action"] == "enter":
                refs[d["client_order_id"]] = Decimal(d["ref_price"])
        for intent in interleave(intents, refs):
            leg = planner.LEG_LONG if intent["side"] == "buy" else planner.LEG_SHORT
            self.send(intent, {"purpose": "entry", "session_label": planner.OPEN_AUCTION, "lane": sig.LIQUID, "leg": leg,
                               "ref_price": str(refs[intent["client_order_id"]])}, deadline=self.schedule.opg_submit_by)
        return True

    def rth_entry_end(self):
        """Last moment for RTH entries: 15:40 (M2) for the momentum arm; for rth_reversal the study's last
        entry time (close - 15 min, releases until close - 30 min) plus its 60 s entry minute. CLS exits are
        re-planned every 30 s until 15:49 (M1), so such an entry is still covered by the close."""
        if self.reversal:
            return self.schedule.cls_end + planner.REV_QUOTE_WINDOW
        return self.schedule.cls_start

    def rth_reversal_step(self, c, snap, now):
        """Evaluate one due RTH event under the preregistered rule; True once both the rev decision
        and the momentum shadow are final (a quote stamped before the entry time waits for a fresher one)."""
        eid = c["event_id"]
        quote = snap.get("latestQuote")
        st = self.rev_state.setdefault(eid, {"done": set()})
        context = {"label_rule": c.get("label_rule"), "strict_label": c.get("strict_label"), "created_at": c.get("created_at"),
                   "received_at": c.get("received_at"), "entry_utc": c.get("entry_utc"), "exchange": c.get("exchange"),
                   "news_id": c.get("news_id"), "rule": "rth_reversal"}
        if not planner.first_in_window(list(self.candidates.values()), c):
            for arm in (REV, SHADOW_ARM):
                self.journal.write("decision", event_id=eid, symbol=c["symbol"], session_label=planner.RTH, lane=c.get("lane"),
                                   label=c.get("label"), arm=arm, action="skip", reason="not_first_in_window", **context)
                self.counts[f"decision:{arm}:rth:skip"] += 1
            return True
        if "asset" not in st:  # fetched once per event, not on every wait
            st["asset"] = (self.fresh_asset(c["symbol"]) if c.get("lane") == sig.LIQUID else None) or {}
            st["target"] = self.target(c)
        ssr = self.ssr_state_for(c, quote, self.session_low(snap))
        ev = {**c, "asset": st["asset"], "ssr": ssr["restricted"], "target_notional": st["target"]}
        if REV not in st["done"]:
            if os.path.exists(os.path.join(self.state, HALT_REVERSAL)):
                decision, intent = {"event_id": eid, "symbol": c["symbol"], "session_label": planner.RTH, "lane": c.get("lane"),
                                    "label": c.get("label"), "arm": REV, "action": "skip", "reason": "harm_halt"}, None
            else:
                decision, intent = planner.plan_rth_reversal_entry(ev, quote, now, self.trade_date, self.exposures[REV],
                                                                   self.limits[REV], self.account_gross())
            if decision["action"] == "wait":
                self.note_once(f"wait:{REV}:{eid}", "decision_wait", **decision)
            else:
                st["done"].add(REV)
                self.journal.write("decision", **decision, **context, ssr=ssr, target_notional_section_a=str(st["target"]),
                                   orders_enabled=arm_orders_enabled(self.cfg, REV, self.trade_date))
                self.counts[f"decision:rev:rth:{decision['action']}"] += 1
                if intent:
                    deadline = sig.as_utc(c["entry_utc"]) + planner.REV_QUOTE_WINDOW
                    if self.send(intent, {"purpose": "entry", "session_label": planner.RTH, "lane": c["lane"],
                                          "leg": decision["leg"], "ref_price": intent["limit_price"], "event_id": eid,
                                          "decision_quote": planner.quote_fields(quote)}, arm=REV, deadline=deadline) is not None:
                        self.rev_working_until = max(self.rev_working_until or now, now + planner.REV_ENTRY_TTL + ROUND_EVERY)
        if SHADOW_ARM not in st["done"]:
            shadow, _ = planner.plan_rth_momentum_shadow(ev, quote, now, self.trade_date, self.shadow_exposure, self.limits[CORE])
            if shadow["action"] == "wait":
                self.note_once(f"wait:{SHADOW_ARM}:{eid}", "decision_wait", **{**shadow, "arm": SHADOW_ARM})
            else:
                st["done"].add(SHADOW_ARM)
                shadow = {**shadow, "arm": SHADOW_ARM, "shadow_only": True,
                          "action": "shadow_enter" if shadow["action"] == "enter" else shadow["action"]}
                shadow.pop("client_order_id", None)  # never an order
                self.journal.write("decision", **shadow, **context, ssr=ssr)
                self.counts[f"decision:{SHADOW_ARM}:rth:{shadow['action']}"] += 1
        return {REV, SHADOW_ARM} <= st["done"]

    def run_rth_entries(self, now):
        due = [c for c in self.rth_pending.values() if sig.as_utc(c["entry_utc"]) <= now]
        if not due:
            return
        snaps = self.data.snapshots(sorted({c["symbol"] for c in due}))
        for c in due:
            snap = snaps.get(c["symbol"]) or {}
            if self.reversal:
                if self.rth_reversal_step(c, snap, now):
                    del self.rth_pending[c["event_id"]]
                continue
            del self.rth_pending[c["event_id"]]
            ev = {**c, "asset": (self.fresh_asset(c["symbol"]) if c.get("lane") == sig.LIQUID else None) or {},
                  "ssr": self.ssr_for(c, self.session_low(snap)), "target_notional": self.target(c)}
            decision, intent = planner.plan_rth_entry(ev, snap.get("latestQuote"), now, self.trade_date,
                                                      self.exposures[CORE], self.limits[CORE], self.account_gross())
            self.journal.write("decision", **decision)
            self.counts[f"decision:core:rth:{decision['action']}"] += 1
            if intent:
                self.send(intent, {"purpose": "entry", "session_label": planner.RTH, "lane": c["lane"], "leg": decision["leg"],
                                   "ref_price": intent["limit_price"]}, deadline=self.schedule.cls_start)

    def sweep_after_cls_start(self, now):
        """M2: RTH entries stop at rth_entry_end(); events still pending then are skipped."""
        if now < self.rth_entry_end() or not self.rth_pending:
            return
        arms, reason = ((REV, SHADOW_ARM), "entry_after_last_entry_minute") if self.reversal else ((CORE,), "entry_after_cls_start")
        for c in list(self.rth_pending.values()):
            del self.rth_pending[c["event_id"]]
            done = self.rev_state.get(c["event_id"], {}).get("done", set())
            for arm in arms:
                if arm not in done:
                    self.journal.write("decision", event_id=c["event_id"], symbol=c["symbol"], session_label=planner.RTH,
                                       lane=c.get("lane"), label=c.get("label"), arm=arm, action="skip", reason=reason)

    def corporate_action_block(self, symbols, held=()):
        """{symbol: GuardDecision} from adaptive-paper corporate_actions (fail closed)."""
        ca = common.load_by_path("adaptive_paper_corporate_actions",
                                 os.path.join(common.REPO, "blueprints/us-equities/adaptive-paper/corporate_actions.py"))
        nxt = self.calendar.sessions[self.calendar.index_of(self.trade_date) + 1].session
        try:
            source = ca.AlpacaCorporateActionsSource(*self._ca_keys)
            out, ambiguous = source.fetch(sorted(set(symbols) | set(held)), self.trade_date, nxt)
            results = {s: (ca.LOOKUP_AMBIGUOUS if s in ambiguous else out.get(s, ca.LOOKUP_FAILED))
                       for s in set(symbols) | set(held)}
        except ca.CorporateActionLookupError as error:
            self.journal.write("risk", event="corporate_action_lookup_failed", error=str(error)[:200])
            results = {}
        return ca.evaluate_guard(today=self.trade_date, next_session_date=nxt, held_symbols=held,
                                 candidate_symbols=symbols, lookup_results=results)

    def run_arm_entries(self, now, arm):
        pending = self.arm_pending[arm]
        due = [c for c in pending.values() if sig.as_utc(c["entry_utc"]) <= now]
        if not due:
            return
        if arm == AH and not planner.overnight_hold_allowed(self.calendar, self.trade_date):
            for c in due:  # Friday or the day before a holiday: no multi-day hold, no lookup, no order
                del pending[c["event_id"]]
                self.journal.write("decision", event_id=c["event_id"], symbol=c["symbol"], arm=AH, lane=c["lane"],
                                   label=c.get("label"), session_label=planner.EXT_POST, action="skip",
                                   reason="ah_next_session_not_next_day")
                self.counts["decision:ah:skip"] += 1
            return
        snaps = self.data.snapshots(sorted({c["symbol"] for c in due}))
        guard = self.corporate_action_block([c["symbol"] for c in due]) if arm == AH else {}
        deadline = self.schedule.basket_at if arm == PM else self.schedule.ext_end
        for c in due:
            del pending[c["event_id"]]
            base = {"event_id": c["event_id"], "symbol": c["symbol"], "arm": arm, "lane": c["lane"], "label": c.get("label"),
                    "session_label": planner.EXT_PRE if arm == PM else planner.EXT_POST}
            if arm == PM:
                first = min((x for x in self.candidates.values() if x["symbol"] == c["symbol"]
                             and x["session"] == c["session"] and x["session_label"] == planner.OPEN_AUCTION),
                            key=lambda x: (x["created_at"], int(x["news_id"]) if str(x["news_id"]).isdigit() else 0))
                if first["event_id"] != c["event_id"]:
                    self.journal.write("decision", **base, action="skip", reason="pm_event_not_core_first_in_window")
                    continue
            if arm == AH:
                g = guard.get(c["symbol"])
                if g is None or g.block_entry:
                    self.journal.write("decision", **base, action="skip",
                                       reason=(g.reason if g else "corporate_action_lookup_failed") or "corporate_action_block")
                    continue
            snap = snaps.get(c["symbol"]) or {}
            ev = {**c, "asset": self.fresh_asset(c["symbol"]) or {}, "ssr": self.ssr_for(c, self.session_low(snap)),
                  "target_notional": self.target(c, planner.ARM_SIZE_FRACTION)}
            decision, intent = planner.plan_ext_entry(ev, snap.get("latestQuote"), now, self.trade_date,
                                                      self.exposures[arm], self.limits[arm], arm, self.account_gross())
            self.journal.write("decision", **decision, orders_enabled=arm_orders_enabled(self.cfg, arm, self.trade_date))
            self.counts[f"decision:{arm}:{decision['action']}"] += 1
            if intent:
                self.send(intent, {"purpose": "entry", "session_label": base["session_label"], "lane": c["lane"],
                                   "leg": decision["leg"], "ref_price": intent["limit_price"]}, arm=arm, deadline=deadline)

    # -- exits (run every step, killed or not) -------------------------------------------

    def cancel_stale_entries(self, now):
        """Paper: cancel RTH and extended-hours entries still working 5 minutes after submission, and
        rth_reversal entries 60 s after submission (checked every 5 s while one may be working)."""
        fast = self.rev_working_until is not None and now <= self.rev_working_until
        if self.mode != "paper" or not self.due("stale", now, STALE_EVERY_REVERSAL if fast else PASS_EVERY):
            return
        stale = []
        for o in self.open_orders():
            info = planner.parse_cid(o["client_order_id"])
            if not info or not planner.is_entry(info, o.get("side")) or info["stage"] == "opg":
                continue
            submitted = o.get("submitted_at")
            if submitted is None:
                continue
            submitted = submitted if isinstance(submitted, datetime) else sig.as_utc(str(submitted))
            ttl = planner.REV_ENTRY_TTL if info["arm"] == REV else planner.RTH_ENTRY_GRACE
            if now - submitted >= ttl:
                stale.append(o)
        if stale:
            self.cancel_and_wait(stale, "stale_entry")

    def run_carry_over(self, now):
        """M5: holdings from earlier dates exit in the opening auction; after the open, a
        marketable limit replaces any exit that did not fill (rounds every 60 s)."""
        sch = self.schedule
        carry = lambda key, h: key[1] < self.trade_date  # noqa: E731
        if sch.basket_at <= now <= sch.opg_submit_by and self.due("xopg", now, PASS_EVERY):
            hs = self.holdings()
            plan, notes = planner.exit_plan(hs, self.positions(), carry)
            if notes:
                self.journal.write("risk", event="carry_over_exit_notes", notes=notes)
            if plan:
                n = self.runstate.bump("xopg_round")
                self.send_exits(plan, f"xopg{n}", now, market=True, tif="opg", deadline=sch.opg_submit_by,
                                session_label="open_auction")
        if sch.fallback_start <= now < sch.cls_start and self.due("cof", now, ROUND_EVERY):
            hs = self.holdings()
            keys = {k for k, h in hs.items() if carry(k, h) and h["qty"] != 0}
            if not keys:
                return
            stale = [o for o in self.open_orders()
                     if (lambda i: i and (i["arm"], i["date"], i["symbol"]) in keys and not planner.is_entry(i, o.get("side")))(
                         planner.parse_cid(o["client_order_id"]))]
            if stale and not self.cancel_and_wait(stale, "carry_over_fallback"):
                return
            hs = self.holdings()
            plan, notes = planner.exit_plan(hs, self.positions(), carry)
            if plan:
                n = self.runstate.bump("cof_round")
                self.journal.write("risk", event="carry_over_fallback", round=n, notes=notes,
                                   holdings=[{"arm": k[0], "entry_date": k[1].isoformat(), "symbol": k[2], "qty": str(q)} for k, q in plan])
                self.send_exits(plan, f"cof{n}", now, deadline=sch.cls_start, session_label="rth")

    def run_net_trims(self, now):
        """M4: after the open, trim any arm-window whose filled net exceeds its cap (rounds every 60 s)."""
        sch = self.schedule
        if not (sch.fallback_start <= now < sch.cls_start) or not self.due("trim", now, ROUND_EVERY):
            return
        hs = self.holdings()
        positions = None
        for arm, windows in ((CORE, (planner.OPEN_AUCTION, planner.RTH)), (PM, (planner.EXT_PRE,)), (REV, (planner.RTH,))):
            for window in windows:
                requests, record = planner.plan_net_trim(hs, arm, self.trade_date, window, self.limits[arm].net_cap)
                if record["status"] != "trim":
                    continue
                positions = positions if positions is not None else self.positions()
                plan, notes = planner.cap_exits(requests, hs, positions)
                n = self.runstate.bump("trim_round")
                self.journal.write("net_trim", **record, round=n, notes=notes,
                                   trims=[{"symbol": k[2], "qty": str(q)} for k, q in plan])
                self.send_exits(plan, f"trim{n}", now, deadline=sch.cls_start, session_label="rth")

    def run_close(self, now):
        """M1/M2: CLS from 15:40, retried every 30 s until 15:49 until every holding is covered;
        open entry orders are cancelled and final before the book is read."""
        sch = self.schedule
        include = self.closeout_include()
        if planner.cls_submission_allowed(sch, now) and self.due("cls", now, PASS_EVERY):
            if not self.entries_cancelled_for_close:
                entries = [o for o in self.open_orders()
                           if (lambda i: i and planner.is_entry(i, o.get("side")) and not (i["arm"] == AH and i["date"] == self.trade_date))(
                               planner.parse_cid(o["client_order_id"]))]
                if entries and not self.cancel_and_wait(entries, "before_close"):
                    return
                self.entries_cancelled_for_close = True
            hs = self.holdings()
            plan, notes = planner.exit_plan(hs, self.positions(), include)
            if notes:
                self.journal.write("risk", event="cls_exit_notes", notes=notes)
            if plan:
                n = self.runstate.bump("cls_round")
                self.send_exits(plan, f"cls{n}", now, market=True, tif="cls", deadline=sch.cls_retry_end)
            else:
                self.note_once("cls_complete", "lifecycle", event="cls_complete", cls_round=self.runstate.get("cls_round"))
        if sch.market_flatten_at <= now < sch.close_utc and self.due("mkt", now, PASS_EVERY):
            hs = self.holdings()
            plan, notes = planner.exit_plan(hs, self.positions(), include)
            if plan:
                n = self.runstate.bump("mkt_round")
                self.send_exits(plan, f"mkt{n}", now, market=True, tif="day", deadline=sch.close_utc)
            else:
                self.note_once("mkt_complete", "lifecycle", event="market_flatten_complete", mkt_round=self.runstate.get("mkt_round"))

    def run_after_close(self, now):
        """After 16:02: extended-hours limit flatten every 10 minutes (tonight's ah holds excepted);
        at 19:50 the ah corporate-action guard flattens any must_flatten hold."""
        sch = self.schedule
        include = self.closeout_include()
        if sch.ext_flatten_at <= now < sch.ext_end and self.due("ext", now, EXT_RETRY):
            hs = self.holdings()
            keys = {k for k, h in hs.items() if h["qty"] != 0 and include(k, h)}
            if keys:
                working = [o for o in self.open_orders()
                           if (lambda i: i and (i["arm"], i["date"], i["symbol"]) in keys)(planner.parse_cid(o["client_order_id"]))]
                if working and not self.cancel_and_wait(working, "after_close_reprice"):
                    return
                hs = self.holdings()
                plan, notes = planner.exit_plan(hs, self.positions(), include)
                if plan:
                    n = self.runstate.bump("ext_round")
                    self.journal.write("risk", event="after_close_flatten", round=n, notes=notes)
                    self.send_exits(plan, f"ext{n}", now, extended=True, deadline=sch.ext_end, session_label="after_close")
        if "ah_guard" not in self.done_steps and now >= sch.ext_end - timedelta(minutes=10):
            self.done_steps.add("ah_guard")
            hs = self.holdings()
            held = sorted({k[2] for k, h in hs.items() if k[0] == AH and k[1] == self.trade_date and h["qty"] != 0})
            if held:
                decisions = self.corporate_action_block([], held=held)
                flatten = {s for s, d in decisions.items() if d.must_flatten}
                self.journal.write("risk", event="ah_overnight_guard", held=held, must_flatten=sorted(flatten),
                                   needs_attention=sorted(s for s, d in decisions.items() if d.needs_attention))
                if flatten:
                    plan, _ = planner.exit_plan(hs, self.positions(),
                                                lambda k, h: k[0] == AH and k[1] == self.trade_date and k[2] in flatten)
                    n = self.runstate.bump("xca_round")
                    self.send_exits(plan, f"xca{n}", now, extended=True, deadline=sch.ext_end, session_label="after_close")

    def run_exits(self, now):
        """Every exit path, run every step whether or not the kill has fired (B1)."""
        self.cancel_stale_entries(now)
        self.run_carry_over(now)
        self.run_net_trims(now)
        self.run_close(now)
        self.run_after_close(now)

    # -- close marks (rth_reversal cost measurement and the momentum shadow) ---------------

    def record_close_marks(self, now):
        """After the close (at +5, +20 and +45 min): the official closing auction price
        (news_signal.select_auction_price on GET /v2/stocks/auctions, the study's exit price rule)
        of every symbol the rev arm entered or the momentum shadow would have entered today."""
        close = self.schedule.close_utc
        due = [i for i, t in enumerate(CLOSE_MARK_TIMES) if now >= close + t and f"close_marks:{i}" not in self.done_steps]
        if not due:
            return
        attempt = max(due)
        for i in due:
            self.done_steps.add(f"close_marks:{i}")
        wanted = {}
        for r in common.read_jsonl(self.journal.path):
            if r.get("kind") == "decision" and r.get("arm") in (REV, SHADOW_ARM) and r.get("action") in ("enter", "shadow_enter"):
                wanted[r["symbol"]] = r.get("exchange")
        todo = sorted(s for s in wanted if s not in self.close_marks_done)
        if not todo:
            return
        try:
            auctions = self.data.auctions(todo, self.trade_date)
        except RuntimeError as error:
            self.journal.write("risk", event="close_mark_fetch_failed", attempt=attempt, error=str(error)[:200])
            return
        final = attempt == len(CLOSE_MARK_TIMES) - 1
        for s in todo:
            picked = sig.select_auction_price((auctions.get(s) or {}).get("c"), "close", wanted[s])
            if picked is None and not final:
                continue
            self.close_marks_done.add(s)
            self.journal.write("close_mark", symbol=s, session=self.trade_date.isoformat(), listing_exchange=wanted[s],
                               official_close=picked[0] if picked else None, condition=picked[1] if picked else None,
                               venue_code=picked[2] if picked else None, source="GET /v2/stocks/auctions (sip)",
                               rule="news_signal.select_auction_price", attempt=attempt,
                               note=None if picked else "no_close_auction_print")

    # -- reconciliation -----------------------------------------------------------------

    def reconcile(self):
        if self.mode != "paper":
            rec = {"ok": True, "mode": "dry-run", "problems": [], "note": "no orders sent; nothing to reconcile",
                   "intended_orders": len(self.executor.submitted)}
            self.journal.write("reconciliation", **rec)
            return rec
        broker = self.executor.broker
        orders = self.all_orders(force=True)

        def fill_day(o):
            stamp = o.get("filled_at") or o.get("submitted_at")
            if stamp is None:
                return None
            stamp = stamp if isinstance(stamp, datetime) else sig.as_utc(str(stamp))
            return stamp.astimezone(common.NY).date()

        fills = [o for o in orders if planner.parse_cid(o.get("client_order_id")) and Decimal(str(o.get("filled_qty") or 0)) > 0
                 and fill_day(o) == self.trade_date]
        for f in fills:
            self.journal.write("fill", **f, arm=(planner.parse_cid(f["client_order_id"]) or {}).get("arm"))
        account = broker.account()
        hs = self.holdings(force=True)
        expected = {}
        for (arm, day, sym), h in hs.items():
            if arm == AH and day == self.trade_date and h["qty"]:
                expected[sym] = expected.get(sym, Decimal("0")) + h["qty"]
        rec = planner.reconcile(self.sod["cash"], account["cash"], fills, broker.positions(), broker.orders("open"), expected)
        self.journal.write("reconciliation", mode="paper", **rec)
        core = [f for f in fills if (planner.parse_cid(f["client_order_id"]) or {}).get("arm") == CORE]
        flow, _ = planner.cash_flows(core)
        entries = [f for f in core if planner.is_entry(planner.parse_cid(f["client_order_id"]), f.get("side"))]
        gross = sum((Decimal(str(f["filled_qty"])) * Decimal(str(f["filled_avg_price"])) for f in entries), Decimal("0"))
        core_flat = not any(k[0] == CORE and h["qty"] for k, h in hs.items())
        # from the reversal switch the core arm is an execution test only (its study failed): never evidence
        row = {"session": self.trade_date.isoformat(), "arm": CORE,
               "evidence_label": planner.ARM_LABEL[CORE] if self.reversal else common.EVIDENCE_LABEL,
               "net_return_on_gross": float(flow / gross) if gross else 0.0, "gross_entry_notional": str(gross),
               "round_trips": len(entries), "core_flat": core_flat, "recorded_at": common.iso(self.clock())}
        if self.reversal:
            self.journal.write("rev_daily", **self.reversal_daily(fills, hs))
        daily_path = os.path.join(self.state, f"autolev-daily-{self.mode}.jsonl")
        if any(r.get("session") == row["session"] for r in common.read_jsonl(daily_path)):
            self.journal.write("autolev_daily_row", **row, written=False, reason="session_already_recorded")  # M8
        else:
            common.append_jsonl(daily_path, row)
            self.journal.write("autolev_daily_row", **row, written=True)
        peak_path = os.path.join(self.state, f"equity-peak-{self.mode}.json")
        peak = Decimal(str((_json_file(peak_path) or {}).get("peak", self.sod["equity"])))
        _write_json(peak_path, {"peak": str(max(peak, Decimal(str(account["equity"])))), "at": common.iso(self.clock())})
        return rec

    def reversal_daily(self, fills, hs):
        """The rev arm's reconciliation summary (descriptive; news-reversal/analyze.py recomputes every
        return from the journaled fill rows)."""
        info = lambda f: planner.parse_cid(f["client_order_id"]) or {}  # noqa: E731
        rev = [f for f in fills if info(f).get("arm") == REV]
        entries = [f for f in rev if info(f).get("date") == self.trade_date and planner.is_entry(info(f), f.get("side"))]
        legs = Counter(info(f)["leg"] for f in entries)
        gross = sum((Decimal(str(f["filled_qty"])) * Decimal(str(f["filled_avg_price"])) for f in entries), Decimal("0"))
        flat = not any(k[0] == REV and k[1] == self.trade_date and h["qty"] for k, h in hs.items())
        flow, _ = planner.cash_flows(rev)
        n_long, n_short = legs.get(planner.LEG_LONG, 0), legs.get(planner.LEG_SHORT, 0)
        return {"session": self.trade_date.isoformat(), "arm": REV, "arm_label": planner.ARM_LABEL[REV],
                "entry_fills": len(entries), "names_long": n_long, "names_short": n_short,
                # the frozen study's legs (news_signal.daily_portfolios): a long-short value needs >= 2 names in each leg
                "long_short_defined": n_long >= sig.MIN_NAMES_PER_LEG and n_short >= sig.MIN_NAMES_PER_LEG,
                "gross_entry_notional": str(gross), "flat": flat,
                "fill_cash_flow": str(flow) if flat else None, "halted": os.path.exists(os.path.join(self.state, HALT_REVERSAL)),
                "protocol_sha256": protocol_sha256()}

    # -- main loop -------------------------------------------------------------------------

    def status(self, now):
        payload = {"at": common.iso(now), "trade_date": self.trade_date.isoformat(), "mode": self.mode,
                   "account_verdict": self.account_verdict, "exit_only": self.executor.exit_only,
                   "killed": self.executor.killed, "runstate": self.runstate.data, "counts": dict(self.counts),
                   "pending_scores": self.pending_scores(), "scorer_device": self.scorers.device,
                   "open_pool": len(self.open_pool), "rth_pending": len(self.rth_pending),
                   "arm_pending": {a: len(v) for a, v in self.arm_pending.items()}, "shadow_pending": len(self.shadow),
                   "equity": str(self.equity), "l_core": str(self.l_core), "l_rev": str(self.l_rev),
                   "rth_reversal_active": self.reversal,
                   "rth_reversal_halted": os.path.exists(os.path.join(self.state, HALT_REVERSAL)),
                   "gross": {a: str(e.gross) for a, e in self.exposures.items()},
                   "git_head": self.git_head, "git_dirty": self.git_dirty, "code_sha256": self.code_sha256,
                   "journal": self.journal.path, "http": dict(self.data.tally)}
        _write_json(os.path.join(self.state, "status.json"), payload)

    def step(self, now):
        if os.path.exists(os.path.join(self.state, "STOP")):
            if not self.halted_logged:
                self.journal.write("risk", event="stop_file_halt")
                self.halted_logged = True
            return
        self.halted_logged = False
        if self.last_news is None or now - self.last_news >= timedelta(seconds=live_news.POLL_SECONDS):
            self.last_news = now
            try:
                self.poll_news(now)
            except RuntimeError as error:
                self.journal.write("lifecycle", event="news_poll_error", error=str(error)[:200])
        self.read_scores(now)
        self.scorers.tick(now, self.schedule, self.pending_scores())
        due_items = self.shadow.pop_due(now)
        if due_items:
            try:
                quotes = self.data.latest_quotes(sorted({e["symbol"] for _, _, _, e in due_items}))
            except RuntimeError:
                quotes = {}
            for due, stage, reason, event in due_items:
                self.journal.write("shadow_quote", **shadow.quote_record(due, stage, reason, event, quotes.get(event["symbol"]), now))
                self.counts["shadow_quotes"] += 1
        self.refresh(now)
        self.kill_check(now)
        if not self.executor.killed and not self.executor.exit_only:
            self.run_entries(now)
        else:
            self.note_once("entries_disabled", "risk", event="entries_disabled", killed=self.executor.killed,
                           exit_only=self.executor.exit_only)
        self.sweep_after_cls_start(now)
        self.run_exits(now)
        if self.reversal:
            self.record_close_marks(now)
        if ("reconcile" not in self.done_steps and now >= self.schedule.close_utc + timedelta(minutes=10)
                and self.due("reconcile_check", now, ROUND_EVERY)):
            hs = self.holdings()
            closeable = planner.exit_plan(hs, self.positions(), self.closeout_include())[0]
            if not closeable or now >= self.schedule.ext_end:
                self.done_steps.add("reconcile")
                self.reconcile()

    def run_entries(self, now):
        sch = self.schedule
        if (self.args.preview_basket and self.mode == "dry-run" and "preview" not in self.done_steps
                and now < sch.basket_at and self.open_pool and self.pending_scores() == 0):
            self.done_steps.add("preview")
            self.journal.write("lifecycle", event="basket_preview", note="verification only: the 09:15 basket built early from the current pool; dry-run, nothing sent")
            self.run_open_basket(sch.opg_submit_by - timedelta(minutes=3))
            self.exposures = {arm: planner.Exposure() for arm in planner.ARM_PREFIX}
            self.executor.submitted = {}
            self.executor.ref_prices = {}
            self.executor.gate.sync(self.exposures)
            self.journal.write("lifecycle", event="basket_preview_end")
        if self.arm_pending[PM] and now < sch.basket_at:
            self.run_arm_entries(now, PM)
        if "basket" not in self.done_steps and sch.basket_at <= now <= sch.opg_submit_by:
            if self.run_open_basket(now):
                self.done_steps.add("basket")
        if sch.open_utc <= now < self.rth_entry_end():
            self.run_rth_entries(now)
        if self.arm_pending[AH] and sch.close_utc <= now < sch.ext_end:
            self.run_arm_entries(now, AH)

    def summary(self, final):
        if final and "reconcile" not in self.done_steps:
            self.done_steps.add("reconcile")
            self.reconcile()
        path = os.path.join(self.state, "receipts", f"{self.trade_date.isoformat()}-summary.json")
        receipt = {"schema": "news-forward-daily-summary/4", "evidence_label": self.journal.evidence_label,
                   "strategy": common.REVERSAL_STRATEGY_ID if self.reversal else common.STRATEGY_ID,
                   "arm_labels": dict(planner.ARM_LABEL),
                   "rth_reversal": {"active": self.reversal, "protocol_sha256": protocol_sha256(), "l_rev": str(self.l_rev),
                                    "halted": os.path.exists(os.path.join(self.state, HALT_REVERSAL)),
                                    "note": "counted-session status is decided only by news-reversal/analyze.py"},
                   "trade_date": self.trade_date.isoformat(), "mode": self.mode,
                   "final": final, "requested_mode": self.requested_mode, "account_verdict": self.account_verdict,
                   "exit_only": self.executor.exit_only, "killed": self.executor.killed, "runstate": self.runstate.data,
                   "equity": str(self.equity), "l_core": str(self.l_core), "git_head": self.git_head,
                   "limits": {a: {"gross_cap": str(v.gross_cap), "per_order_cap": str(v.per_order_cap),
                                  "net_cap": str(v.net_cap)} for a, v in self.limits.items()},
                   "counts": dict(sorted(self.counts.items())), "journal_kinds": dict(self.journal.counts),
                   "journal": self.journal.path, "journal_sha256": common.sha256_file(self.journal.path),
                   "http": dict(self.data.tally), "written_at": common.iso(self.clock())}
        _write_json(path, receipt)
        with open(path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        with open(path + ".sha256", "w", encoding="utf-8") as handle:
            handle.write(f"{digest}  {os.path.basename(path)}\n")
        return path

    def run(self):
        while not STOP_REQUESTED:
            now = self.clock()
            if now >= self.end:
                break
            try:
                self.step(now)
            except Exception as error:  # noqa: BLE001 - journaled; the unit restarts on a crash only
                self.journal.write("lifecycle", event="step_error", error=f"{type(error).__name__}: {str(error)[:300]}")
            self.status(now)
            time.sleep(1.0)
        final = self.clock() >= self.end
        self.journal.write("lifecycle", event="stopping", final=final, counts=dict(self.counts))
        path = self.summary(final)
        if not self.args.keep_scorer:
            self.scorers.stop()
        self.journal.write("lifecycle", event="stopped", receipt=path)
        return 0


def parse_time(text, day):
    hh, mm = (int(x) for x in text.split(":"))
    return planner.local_at(day, hh, mm)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=os.path.join(HERE, "config.json"))
    parser.add_argument("--mode", choices=("dry-run", "paper"), help="overrides config.json mode")
    parser.add_argument("--dry-run", action="store_true",
                        help="force dry-run whatever --mode or config.json say: no trading client is built, nothing is sent")
    parser.add_argument("--scores-from",
                        help="dry-run verification only: also read score rows (never written) from this scores.jsonl, e.g. "
                             "the running service's, for events this run screened itself")
    parser.add_argument("--state", default=common.STATE_ROOT)
    parser.add_argument("--date", type=date.fromisoformat, help="trade date (default: today in New York)")
    parser.add_argument("--until", help="stop at this HH:MM New York time (default: 20:05, or close + 4 h + 5 min)")
    parser.add_argument("--cpu-fallback-at", help="HH:MM New York time from which the CPU scorer may run (default 09:00)")
    parser.add_argument("--scorer-unit", default="news-forward-scorer")
    parser.add_argument("--no-scorer", action="store_true")
    parser.add_argument("--keep-scorer", action="store_true", help="leave the scorer unit running at exit")
    parser.add_argument("--rate", type=int, default=90,
                        help="data requests per minute for this process (max 300; paper-3 allows 200/min per key, "
                             "so 90 keeps the service plus one verification run within it)")
    parser.add_argument("--preview-basket", action="store_true",
                        help="dry-run verification only: build the open-auction basket early once the pool is scored")
    args = parser.parse_args(argv)
    if args.dry_run:
        args.mode = "dry-run"
    if args.scores_from and args.mode != "dry-run":
        raise SystemExit("--scores-from is a dry-run verification option; use it with --dry-run")
    if args.scores_from and os.path.realpath(os.path.dirname(args.scores_from)) == os.path.realpath(args.state):
        raise SystemExit("--scores-from must name another state's scores file")
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)
    cfg = load_config(args.config)
    day = args.date or common.utc_now().astimezone(common.NY).date()
    if not planner.is_session(common.load_calendar(), day):
        print(json.dumps({"event": "not_a_session", "date": day.isoformat()}))
        return 0
    args.until = parse_time(args.until, day) if args.until else None
    args.cpu_fallback_at = parse_time(args.cpu_fallback_at, day) if args.cpu_fallback_at else None
    return Supervisor(args, cfg).run()


if __name__ == "__main__":
    sys.exit(main())
