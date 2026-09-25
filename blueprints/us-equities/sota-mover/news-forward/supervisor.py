#!/usr/bin/env python3
"""Session-aware supervisor for the news-LLM paper pilot (one trade date per run).

Timeline (America/New_York, from the XNYS calendar, DST-aware; early closes shift the
close-relative steps):
  start (03:55 by timer)  backfill news from the previous close - 24 h (novelty warm-up);
                          start-of-day equity E (persisted per date), the day's leverage
                          decision (autolev.py, capped by adaptive-paper leverage.py)
  every 15 s              poll news, screen with the study's guards, look up the lane,
                          sigma and MDV20, queue eligible headlines for the scorer
  GPU schedule            scorer on the GPU only with >= 9 GB free VRAM and not before
                          08:30 unless <state>/gpu-early-ok exists and no other
                          sota-news-* unit is active; CPU fallback from 09:00
  04:15 - 09:15           pm arm: extended-hours entries at release + 15 min (04:00-09:00
                          liquid headlines), only when the arm is enabled for orders
  09:15 - 09:27           ah-arm OPG exits (yesterday's overnight holds), then the core
                          open-auction basket (OPG)
  09:30 - 15:45           core RTH headlines: marketable limit at release + 15 min
  15:40 - 15:45           CLS exits for core and pm holdings
  15:55                   day market order for any core/pm holding without a live exit
  16:02 - 20:00           extended-hours limit flatten of core/pm (bid/ask -/+0.5%)
  16:15 - 19:45           ah arm: extended-hours entries at release + 15 min (16:00-19:30
                          headlines), corporate-action guard, held to the next OPG
  after the close         reconciliation, then the daily summary receipt at 20:05
  04:00-09:30, 16:00-20:00 headlines and the small-cap lane: shadow quotes as well

Modes: ``dry-run`` (no trading client is constructed, intended orders are validated and
journaled) and ``paper`` (config.json "mode": "paper" or --mode paper, plus a verified
alpaca-paper-3.env). A paper-mode start that fails any account check is journaled and
continues as dry-run. No paper order is sent before config "first_order_not_before".
An arm whose "orders_from" date is later than the trade date journals intents only.
<state>/STOP halts all order activity.
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
CORE, PM, AH = planner.CORE, planner.PM, planner.AH
VLLM_PYTHON = os.path.expanduser("~/.local/share/codex-ecosystem/tools/vllm-0.30.0/bin/python")
GPU_MIN_FREE_MIB = 9 * 1024
KILL_CHECK_SECONDS = 30
EXT_RETRY = timedelta(minutes=10)
NEWS_FIELDS = ("id", "headline", "symbols", "source", "author", "created_at", "updated_at", "url", "received_at")
TERMINAL = ("canceled", "rejected", "expired", "done_for_day", "replaced")
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


def arm_orders_enabled(cfg, arm, day):
    """An arm sends orders from its configured date on; the core arm always does."""
    if arm == CORE:
        return True
    start = ((cfg.get("arms") or {}).get(arm) or {}).get("orders_from")
    return bool(start) and date.fromisoformat(start) <= day


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
# Supervisor
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
        self.journal = common.Journal(self.state, self.trade_date, clock=clock)
        key, secret = live_news.read_credentials(common.DATA_ENV)
        self.data = live_news.DataClient(key, secret, limiter=live_news.RateLimiter(args.rate))
        self._ca_keys = (key, secret)  # corporate-action lookups (alpaca-py data client)
        del key, secret
        self.requested_mode = args.mode or cfg["mode"]
        self.account_verdict = "not_checked"
        broker, account = None, None
        mode = "dry-run"
        if self.requested_mode == "paper":
            try:
                k, s = ex.trading_credentials()
                broker = ex.AlpacaBroker(ex.make_trading_client(k, s))
                del k, s
                account = ex.start_check(broker)
                mode = "paper"
                self.account_verdict = "ready_for_paper"
            except ex.AccountRefused as error:
                self.account_verdict = f"refused:{error}"
                broker = None
        not_before = cfg.get("first_order_not_before")
        not_before = sig.as_utc(not_before) if not_before else None
        self.executor = ex.Executor(mode, self.journal, self.state, broker=broker, clock=clock, not_before=not_before)
        self.mode = mode
        self.sod = self.start_of_day(account)
        self.equity = Decimal(str(self.sod["equity"]))
        self.leverage_decisions()
        self.exposures = {arm: planner.Exposure() for arm in planner.ARM_PREFIX}
        assets = self.data.assets()
        self.assets = assets
        self.screener = planner.Screener(self.calendar, assets)
        backfill_from = self.prev_session.close_utc - timedelta(hours=24)
        self.poller = live_news.NewsPoller(self.data, backfill_from, clock=clock)
        self.first_poll = True
        self.queue_path = os.path.join(self.state, "score-queue.jsonl")
        self.scores_path = os.path.join(self.state, "scores.jsonl")
        self.scores_offset = 0
        self.scores = {}
        for row in common.read_jsonl(self.scores_path):
            self.scores[row["event_id"]] = row
        self.queued = {r["event_id"] for r in common.read_jsonl(self.queue_path) if "event_id" in r}
        self.candidates = {}
        self.bars = {}
        self.lanes = {}
        self.sigmas = {}
        self.announced = set()
        self.shadow = shadow.ShadowTracker()
        self.open_pool = {}
        self.rth_pending = {}
        self.arm_pending = {PM: {}, AH: {}}
        self.done_steps = set()
        self.ext_round = 0
        self.last_ext = None
        self.last_kill_check = None
        self.last_stale_check = None
        self.last_news = None
        self.halted_logged = False
        self.counts = Counter()
        if self.mode == "paper":
            self.rebuild_exposure()
        cpu_at = args.cpu_fallback_at or planner.local_at(self.trade_date, 9, 0)
        self.scorers = ScorerManager(self.state, args.scorer_unit, self.journal, cpu_at, enabled=not args.no_scorer)
        config_path = args.config
        self.journal.write("lifecycle", event="start", trade_date=self.trade_date.isoformat(),
                           requested_mode=self.requested_mode, mode=self.mode, account_verdict=self.account_verdict,
                           end=common.iso(self.end), assets=len(assets),
                           schedule={k: common.iso(v) if isinstance(v, datetime) else str(v) for k, v in self.schedule.__dict__.items()},
                           config=cfg, config_sha256=common.sha256_file(config_path),
                           arms_orders_enabled={a: arm_orders_enabled(cfg, a, self.trade_date) for a in planner.ARM_PREFIX},
                           code_sha256={n: common.sha256_file(os.path.join(HERE, n)) for n in sorted(os.listdir(HERE)) if n.endswith(".py")},
                           news_signal_sha256=common.sha256_file(os.path.join(common.NEWS_LLM, "news_signal.py")),
                           score_py_sha256=common.sha256_file(os.path.join(common.NEWS_LLM, "score.py")),
                           strategy=common.STRATEGY_ID, sod=self.sod)
        if self.mode == "paper":
            self.journal.write("lifecycle", event="paper_mode_enabled", switched_at=common.iso(now),
                               flag="config.json mode=paper" if not args.mode else "--mode paper",
                               config_sha256=common.sha256_file(config_path),
                               first_order_not_before=common.iso(not_before), account_verdict=self.account_verdict)

    # -- equity, drawdown and leverage -------------------------------------------------

    def start_of_day(self, account):
        """E: persisted once per trade date (paper), so a restart keeps the same E and kill base."""
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
                                                  kill_switch=False, account_multiplier=mult, overnight=False)
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
        }
        self.journal.write("leverage_decision", trade_date=self.trade_date.isoformat(), peak_equity=str(peak),
                           autolev=core_inputs, account_ceiling=str(account_ceiling), pre_ceiling=str(pre_ceiling),
                           post_overnight_ceiling=str(post_overnight), account_gross_cap=str(self.account_gross_cap),
                           limits={a: {"gross_cap": str(v.gross_cap), "per_order_cap": str(v.per_order_cap)}
                                   for a, v in self.limits.items()},
                           kill_loss_fraction=str(planner.KILL_LOSS_FRACTION))

    def account_gross(self):
        return [sum((e.gross for e in self.exposures.values()), Decimal("0")), self.account_gross_cap]

    def rebuild_exposure(self):
        """After a restart: today's entries per arm (names, symbols, gross) from the broker."""
        broker = self.executor.broker
        orders = broker.orders("all", after=planner.local_at(self.trade_date, 0))
        for o in orders:
            info = planner.parse_cid(o.get("client_order_id"))
            if not info or info["date"] != self.trade_date or info["stage"] not in planner.ENTRY_STAGES:
                continue
            self.executor.submitted[o["client_order_id"]] = o
            if o.get("status") in TERMINAL and Decimal(str(o.get("filled_qty") or 0)) == 0:
                continue
            label = {"opg": planner.OPEN_AUCTION, "rth": planner.RTH}.get(info["stage"],
                                                                          planner.EXT_PRE if info["arm"] == PM else planner.EXT_POST)
            price = o.get("filled_avg_price") or o.get("limit_price")
            qty = Decimal(str(o.get("qty") or 0))
            notional = qty * Decimal(str(price)) if price else self.limits[info["arm"]].per_order_cap
            planner.commit_entry(self.exposures[info["arm"]], notional, label, info["leg"], info["symbol"])
        self.journal.write("lifecycle", event="exposure_rebuilt",
                           gross={a: str(e.gross) for a, e in self.exposures.items()})

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
            for s in syms:
                self.bars[(s, sess)] = bars.get(s, [])
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
        if fresh:
            self.ensure_lanes(fresh)
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

    def read_scores(self, now):
        if os.path.exists(self.scores_path):
            with open(self.scores_path, encoding="utf-8") as handle:
                handle.seek(self.scores_offset)
                data = handle.read()
            cut = data.rfind("\n") + 1
            self.scores_offset += len(data[:cut].encode("utf-8"))
            for line in data[:cut].splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                self.scores[row["event_id"]] = row
        for eid, cand in self.candidates.items():
            if eid in self.announced or eid not in self.scores:
                continue
            self.announced.add(eid)
            row = self.scores[eid]
            cand["label"] = row["label"]
            cand["score"] = row["score"]
            self.counts["scored"] += 1
            self.counts[f"label:{cand['session_label']}:{cand['lane']}:{row['label']}"] += 1
            received = sig.as_utc(cand["received_at"])
            self.journal.write("score", event_id=eid, symbol=cand["symbol"], session_label=cand["session_label"],
                               ext_segment=cand["ext_segment"], arm_release=cand["arm_release"], lane=cand["lane"],
                               label=row["label"], score=row["score"], device=row.get("device"),
                               raw_output=row.get("raw_output"), stop=row.get("stop"), revision=row.get("revision"),
                               variant=row.get("variant"), seconds_after_receipt=round((now - received).total_seconds(), 1))
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
        bars = self.bars.get((cand["symbol"], cand["session"]), [])
        return planner.ssr_active(self.calendar, date.fromisoformat(cand["session"]), bars, today_low)

    def target(self, cand, fraction=Decimal("1")):
        return planner.risk_notional(self.equity, cand.get("sigma"), cand.get("prior_median_dollar_volume_20"), fraction)

    # -- positions: per-arm ledgers ------------------------------------------------------

    def book(self):
        """{(arm, entry_date, symbol): signed qty} from the broker (paper) or the intents (dry-run)."""
        if self.mode == "paper":
            orders = self.executor.broker.orders("all", after=planner.local_at(self.prev_session.session, 0))
        else:
            orders = [o for o in self.executor.submitted.values() if o.get("side")]
        return planner.ledger(orders)

    def open_exit_keys(self):
        """(arm, symbol) pairs with a live exit order."""
        if self.mode == "paper":
            orders = self.executor.broker.orders("open")
        else:
            orders = list(self.executor.submitted.values())
        keys = set()
        for o in orders:
            info = planner.parse_cid(o.get("client_order_id"))
            if info and info["stage"] not in planner.ENTRY_STAGES:
                keys.add((info["arm"], info["symbol"]))
        return keys

    def send(self, intent, context, arm=CORE):
        dry = not arm_orders_enabled(self.cfg, arm, self.trade_date)
        order = self.executor.send(intent, {**context, "arm": arm, "arm_label": planner.ARM_LABEL[arm]}, dry_run=dry)
        if order is not None:
            self.counts[f"orders_{'dry-run' if dry else self.mode}:{arm}:{context.get('session_label')}:{context.get('purpose')}"] += 1
        return order

    # -- trading steps -------------------------------------------------------------------

    def run_ah_opg_exits(self):
        exits = planner.plan_ah_opg_exits(self.book(), self.trade_date, self.calendar)
        for intent in exits:
            self.send(intent, {"purpose": "exit", "session_label": "open_auction", "stage": "opg"}, arm=AH)
        return {i["symbol"] for i in exits}

    def run_open_basket(self, now):
        pool = list(self.open_pool.values())
        unscored = [c for c in self.candidates.values() if c["session"] == self.trade_date.isoformat()
                    and c["session_label"] == planner.OPEN_AUCTION and c["event_id"] not in self.scores]
        if unscored and now < self.schedule.opg_submit_by - timedelta(minutes=3):
            return False  # wait for the backlog, up to 09:24
        blocked = self.run_ah_opg_exits() if "ah_opg_exits" not in self.done_steps else set()
        self.done_steps.add("ah_opg_exits")
        for c in unscored:
            self.journal.write("decision", event_id=c["event_id"], symbol=c["symbol"], session_label=planner.OPEN_AUCTION,
                               lane=c["lane"], action="skip", reason="unscored_at_basket_cutoff", arm=CORE)
        symbols = sorted({c["symbol"] for c in pool if c.get("lane") == sig.LIQUID})
        snaps = self.data.snapshots(symbols) if symbols else {}
        events = []
        for c in pool:
            snap = snaps.get(c["symbol"]) or {}
            quote = snap.get("latestQuote") or {}
            trade = snap.get("latestTrade") or {}
            ref = None
            if quote.get("bp") and quote.get("ap") and planner.spread_bps(quote["bp"], quote["ap"]) is not None:
                ref = (Decimal(str(quote["bp"])) + Decimal(str(quote["ap"]))) / 2
            elif trade.get("p"):
                ref = Decimal(str(trade["p"]))
            asset = self.fresh_asset(c["symbol"]) if c.get("lane") == sig.LIQUID else None
            events.append({**c, "ref_price": ref, "asset": asset or {}, "ssr": self.ssr_for(c), "target_notional": self.target(c)})
        account = self.account_gross()
        decisions, intents = planner.build_open_basket(events, self.trade_date, self.exposures[CORE], self.limits[CORE],
                                                       account_gross=account, blocked=blocked)
        for d in decisions:
            self.journal.write("decision", **d)
            self.counts[f"decision:core:{d['session_label']}:{d['action']}"] += 1
        for intent in intents:
            if now > self.schedule.opg_submit_by:
                self.journal.write("order_refused", reason="opg_cutoff_passed", intent=intent, arm=CORE)
                continue
            leg = planner.LEG_LONG if intent["side"] == "buy" else planner.LEG_SHORT
            self.send(intent, {"purpose": "entry", "session_label": planner.OPEN_AUCTION, "lane": sig.LIQUID, "leg": leg})
        return True

    def run_rth_entries(self, now):
        due = [c for c in self.rth_pending.values() if sig.as_utc(c["entry_utc"]) <= now]
        if not due:
            return
        snaps = self.data.snapshots(sorted({c["symbol"] for c in due}))
        for c in due:
            del self.rth_pending[c["event_id"]]
            snap = snaps.get(c["symbol"]) or {}
            ev = {**c, "asset": (self.fresh_asset(c["symbol"]) if c.get("lane") == sig.LIQUID else None) or {},
                  "ssr": self.ssr_for(c, self.today_low(snap)), "target_notional": self.target(c)}
            decision, intent = planner.plan_rth_entry(ev, snap.get("latestQuote"), now, self.trade_date,
                                                      self.exposures[CORE], self.limits[CORE], self.account_gross())
            self.journal.write("decision", **decision)
            self.counts[f"decision:core:rth:{decision['action']}"] += 1
            if intent:
                self.send(intent, {"purpose": "entry", "session_label": planner.RTH, "lane": c["lane"], "leg": decision["leg"]})

    def today_low(self, snap):
        bar = (snap or {}).get("dailyBar") or {}
        if bar.get("t") and sig.as_utc(bar["t"]).astimezone(common.NY).date() == self.trade_date:
            return bar.get("l")
        return None

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
        snaps = self.data.snapshots(sorted({c["symbol"] for c in due}))
        guard = self.corporate_action_block([c["symbol"] for c in due]) if arm == AH else {}
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
            ev = {**c, "asset": self.fresh_asset(c["symbol"]) or {}, "ssr": self.ssr_for(c, self.today_low(snap)),
                  "target_notional": self.target(c, planner.ARM_SIZE_FRACTION)}
            decision, intent = planner.plan_ext_entry(ev, snap.get("latestQuote"), now, self.trade_date,
                                                      self.exposures[arm], self.limits[arm], arm, self.account_gross())
            self.journal.write("decision", **decision, orders_enabled=arm_orders_enabled(self.cfg, arm, self.trade_date))
            self.counts[f"decision:{arm}:{decision['action']}"] += 1
            if intent:
                self.send(intent, {"purpose": "entry", "session_label": base["session_label"], "lane": c["lane"],
                                   "leg": decision["leg"]}, arm=arm)

    def cancel_orders(self, now, entries_only=False, older_than=None, arms=None):
        """Paper: cancel our open orders (filters: entries only, age, arms)."""
        if self.mode != "paper":
            return
        for o in self.executor.broker.orders("open"):
            info = planner.parse_cid(o.get("client_order_id"))
            if not info or (arms and info["arm"] not in arms):
                continue
            if entries_only and info["stage"] not in planner.ENTRY_STAGES:
                continue
            if older_than is not None:
                if info["stage"] == "opg":
                    continue  # OPG orders resolve in the opening auction
                submitted = o.get("submitted_at")
                if submitted is None:
                    continue
                submitted = submitted if isinstance(submitted, datetime) else sig.as_utc(str(submitted))
                if now - submitted < older_than:
                    continue
            try:
                self.executor.broker.cancel(o["id"])
                self.journal.write("order_cancel", client_order_id=o["client_order_id"], symbol=o.get("symbol"),
                                   reason="stale_entry" if older_than is not None else "before_exits", arm=info["arm"])
            except Exception as error:  # noqa: BLE001
                self.journal.write("order_cancel_failed", client_order_id=o["client_order_id"], error=str(error)[:200])

    def run_exits(self, now):
        sch = self.schedule
        if self.mode == "paper" and (self.last_stale_check is None or now - self.last_stale_check >= timedelta(seconds=30)):
            self.last_stale_check = now
            self.cancel_orders(now, entries_only=True, older_than=planner.RTH_ENTRY_GRACE)
        if "cls" not in self.done_steps and planner.cls_submission_allowed(sch, now):
            self.done_steps.add("cls")
            self.cancel_orders(now, entries_only=True, arms=(CORE, PM))
            for intent in planner.plan_cls_exits(self.book(), self.trade_date, self.open_exit_keys()):
                arm = planner.parse_cid(intent["client_order_id"])["arm"]
                self.send(intent, {"purpose": "exit", "session_label": "close", "stage": "cls"}, arm=arm)
        if "mkt" not in self.done_steps and sch.market_flatten_at <= now < sch.close_utc:
            self.done_steps.add("mkt")
            for intent in planner.plan_market_flatten(self.book(), self.trade_date, self.open_exit_keys()):
                arm = planner.parse_cid(intent["client_order_id"])["arm"]
                self.send(intent, {"purpose": "exit", "session_label": "close", "stage": "mkt"}, arm=arm)
        if self.mode == "paper" and sch.ext_flatten_at <= now < sch.ext_end and (
                self.last_ext is None or now - self.last_ext >= EXT_RETRY):
            self.last_ext = now
            book = self.book()
            if any(arm in (CORE, PM) and day == self.trade_date for (arm, day, _s) in book):
                self.ext_round += 1
                self.cancel_orders(now, arms=(CORE, PM))
                syms = sorted({s for (arm, day, s) in book if arm in (CORE, PM) and day == self.trade_date})
                quotes = self.data.latest_quotes(syms)
                intents, missing = planner.plan_ext_flatten(book, quotes, self.trade_date, stage=f"ext{self.ext_round}")
                for sym in missing:
                    self.journal.write("risk", event="ext_flatten_no_quote", symbol=sym)
                for intent in intents:
                    arm = planner.parse_cid(intent["client_order_id"])["arm"]
                    self.send(intent, {"purpose": "exit", "session_label": "after_close", "stage": f"ext{self.ext_round}"}, arm=arm)
        if "ah_guard" not in self.done_steps and now >= sch.ext_end - timedelta(minutes=10):
            self.done_steps.add("ah_guard")
            held = sorted({s for (arm, day, s) in self.book() if arm == AH and day == self.trade_date})
            if held:
                decisions = self.corporate_action_block([], held=held)
                flatten = {s for s, d in decisions.items() if d.must_flatten}
                self.journal.write("risk", event="ah_overnight_guard", held=held, must_flatten=sorted(flatten),
                                   needs_attention=sorted(s for s, d in decisions.items() if d.needs_attention))
                if flatten:
                    book = {k: v for k, v in self.book().items() if k[0] == AH and k[2] in flatten}
                    quotes = self.data.latest_quotes(sorted(flatten))
                    intents, _ = planner.plan_ext_flatten(book, quotes, self.trade_date, stage="xca", arms=(AH,))
                    for intent in intents:
                        self.send(intent, {"purpose": "exit", "session_label": "after_close", "stage": "xca"}, arm=AH)

    def kill_check(self, now):
        if self.mode != "paper" or self.executor.killed:
            return
        if self.last_kill_check and now - self.last_kill_check < timedelta(seconds=KILL_CHECK_SECONDS):
            return
        self.last_kill_check = now
        account = self.executor.broker.account()
        if planner.kill_switch_triggered(self.sod.get("equity"), account.get("equity")):
            self.executor.killed = True
            self.journal.write("risk", event="kill_switch", sod_equity=self.sod.get("equity"), equity=account.get("equity"),
                               threshold=str(planner.KILL_LOSS_FRACTION))
            self.cancel_orders(now)
            book = self.book()
            rth = self.schedule.open_utc <= now < self.schedule.close_utc
            quotes = {} if rth else self.data.latest_quotes(sorted({s for (_a, _d, s) in book}))
            for (arm, day, sym), qty in sorted(book.items()):
                if rth:
                    intent = planner.exit_intent(day, "kill", sym, qty, arm=arm)
                else:
                    intents, _ = planner.plan_ext_flatten({(arm, day, sym): qty}, quotes, day, stage="kill", arms=(arm,))
                    if not intents:
                        continue
                    intent = intents[0]
                self.executor.send(intent, {"purpose": "kill_flatten", "session_label": "kill", "arm": arm})

    def reconcile(self):
        if self.mode != "paper":
            rec = {"ok": True, "mode": "dry-run", "problems": [], "note": "no orders sent; nothing to reconcile",
                   "intended_orders": len(self.executor.submitted)}
            self.journal.write("reconciliation", **rec)
            return rec
        broker = self.executor.broker
        closed = broker.orders("closed", after=planner.local_at(self.trade_date, 0))
        fills = [o for o in closed if planner.is_nf1(o.get("client_order_id")) and Decimal(str(o.get("filled_qty") or 0)) > 0]
        for f in fills:
            self.journal.write("fill", **f, arm=(planner.parse_cid(f["client_order_id"]) or {}).get("arm"))
        account = broker.account()
        book = self.book()
        expected = {}
        for (arm, day, sym), qty in book.items():
            if arm == AH and day == self.trade_date:
                expected[sym] = expected.get(sym, Decimal("0")) + qty
        rec = planner.reconcile(self.sod["cash"], account["cash"], fills, broker.positions(), broker.orders("open"), expected)
        self.journal.write("reconciliation", mode="paper", **rec)
        core = [f for f in fills if (planner.parse_cid(f["client_order_id"]) or {}).get("arm") == CORE]
        flow, _ = planner.cash_flows(core)
        gross = sum(Decimal(str(f["filled_qty"])) * Decimal(str(f["filled_avg_price"])) for f in core
                    if planner.parse_cid(f["client_order_id"])["stage"] in planner.ENTRY_STAGES)
        row = {"session": self.trade_date.isoformat(), "evidence_label": common.EVIDENCE_LABEL, "arm": CORE,
               "net_return_on_gross": float(flow / gross) if gross else 0.0, "gross_entry_notional": str(gross),
               "round_trips": sum(1 for f in core if planner.parse_cid(f["client_order_id"])["stage"] in planner.ENTRY_STAGES),
               "core_flat": not any(k[0] == CORE for k in book), "recorded_at": common.iso(self.clock())}
        common.append_jsonl(os.path.join(self.state, f"autolev-daily-{self.mode}.jsonl"), row)
        peak_path = os.path.join(self.state, f"equity-peak-{self.mode}.json")
        peak = Decimal(str((_json_file(peak_path) or {}).get("peak", self.sod["equity"])))
        _write_json(peak_path, {"peak": str(max(peak, Decimal(str(account["equity"])))), "at": common.iso(self.clock())})
        self.journal.write("autolev_daily_row", **row)
        return rec

    # -- main loop -------------------------------------------------------------------------

    def status(self, now):
        payload = {"at": common.iso(now), "trade_date": self.trade_date.isoformat(), "mode": self.mode,
                   "account_verdict": self.account_verdict, "counts": dict(self.counts),
                   "pending_scores": self.pending_scores(), "scorer_device": self.scorers.device,
                   "open_pool": len(self.open_pool), "rth_pending": len(self.rth_pending),
                   "arm_pending": {a: len(v) for a, v in self.arm_pending.items()}, "shadow_pending": len(self.shadow),
                   "equity": str(self.equity), "l_core": str(self.l_core),
                   "gross": {a: str(e.gross) for a, e in self.exposures.items()},
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
        self.kill_check(now)
        if self.executor.killed:
            return
        if (self.args.preview_basket and self.mode == "dry-run" and "preview" not in self.done_steps
                and now < self.schedule.basket_at and self.open_pool and self.pending_scores() == 0):
            self.done_steps.add("preview")
            self.journal.write("lifecycle", event="basket_preview", note="verification only: the 09:15 basket built early from the current pool; dry-run, nothing sent")
            self.run_open_basket(self.schedule.opg_submit_by - timedelta(minutes=3))
            self.exposures = {arm: planner.Exposure() for arm in planner.ARM_PREFIX}
            self.executor.submitted = {}
            self.done_steps.discard("ah_opg_exits")
            self.journal.write("lifecycle", event="basket_preview_end")
        if self.arm_pending[PM] and now < self.schedule.basket_at:
            self.run_arm_entries(now, PM)
        if "basket" not in self.done_steps and self.schedule.basket_at <= now <= self.schedule.opg_submit_by:
            if self.run_open_basket(now):
                self.done_steps.add("basket")
        if self.schedule.open_utc <= now < self.schedule.cls_end:
            self.run_rth_entries(now)
        if self.arm_pending[AH] and self.schedule.close_utc <= now < self.schedule.ext_end:
            self.run_arm_entries(now, AH)
        self.run_exits(now)
        if "reconcile" not in self.done_steps and now >= self.schedule.close_utc + timedelta(minutes=10):
            core_pm_open = any(arm in (CORE, PM) and day == self.trade_date for (arm, day, _s) in self.book())
            if not core_pm_open or now >= self.schedule.ext_end:
                self.done_steps.add("reconcile")
                self.reconcile()

    def summary(self, final):
        if final and "reconcile" not in self.done_steps:
            self.done_steps.add("reconcile")
            self.reconcile()
        path = os.path.join(self.state, "receipts", f"{self.trade_date.isoformat()}-summary.json")
        receipt = {"schema": "news-forward-daily-summary/2", "evidence_label": common.EVIDENCE_LABEL,
                   "strategy": common.STRATEGY_ID, "trade_date": self.trade_date.isoformat(), "mode": self.mode,
                   "final": final, "requested_mode": self.requested_mode, "account_verdict": self.account_verdict,
                   "equity": str(self.equity), "l_core": str(self.l_core),
                   "limits": {a: {"gross_cap": str(v.gross_cap), "per_order_cap": str(v.per_order_cap)} for a, v in self.limits.items()},
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
    parser.add_argument("--state", default=common.STATE_ROOT)
    parser.add_argument("--date", type=date.fromisoformat, help="trade date (default: today in New York)")
    parser.add_argument("--until", help="stop at this HH:MM New York time (default: 20:05, or close + 4 h + 5 min)")
    parser.add_argument("--cpu-fallback-at", help="HH:MM New York time from which the CPU scorer may run (default 09:00)")
    parser.add_argument("--scorer-unit", default="news-forward-scorer")
    parser.add_argument("--no-scorer", action="store_true")
    parser.add_argument("--keep-scorer", action="store_true", help="leave the scorer unit running at exit")
    parser.add_argument("--rate", type=int, default=150,
                        help="data requests per minute for this process (max 300; 150 keeps two concurrent runs within 300)")
    parser.add_argument("--preview-basket", action="store_true",
                        help="dry-run verification only: build the open-auction basket early once the pool is scored")
    args = parser.parse_args(argv)
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
