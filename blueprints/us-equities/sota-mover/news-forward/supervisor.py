#!/usr/bin/env python3
"""Session-aware supervisor for the news-LLM paper pilot (one trade date per run).

Timeline (America/New_York, from the XNYS calendar, DST-aware; early closes shift the
close-relative steps):
  start (03:55 by timer)  backfill news from the previous close - 24 h (novelty warm-up)
  every 15 s              poll news, screen with the study's guards, look up the lane,
                          queue eligible headlines for the scorer
  GPU schedule            scorer on the GPU only with >= 9 GB free VRAM and not before
                          08:30 unless <state>/gpu-early-ok exists and no other
                          sota-news-* unit is active; CPU fallback from 09:00
  09:15 - 09:27           open-auction basket (after-hours/overnight headlines), OPG orders
  09:30 - 15:45           RTH headlines: marketable limit at release + 15 min
  15:40 - 15:45           CLS exits for every nf1 position
  15:55                   day market order for any position without an exit
  16:02 - 20:00           extended-hours limit flatten (bid/ask -/+0.5%), every 10 min
  after the close         reconciliation, then the daily summary receipt at 20:05
  04:00-09:30, 16:00-20:00 headlines and the small-cap lane: shadow quotes only

Modes: ``dry-run`` (default; no trading client is constructed, intended orders are
validated and journaled) and ``paper`` (config.json "mode": "paper" or --mode paper,
plus a verified alpaca-paper-3.env). A paper-mode start that fails any account check
is journaled and continues as dry-run. <state>/STOP halts all order activity.
"""
import argparse
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
import common  # noqa: E402
import executor as ex  # noqa: E402
import live_news  # noqa: E402
import planner  # noqa: E402
import shadow  # noqa: E402

sig = planner.sig
VLLM_PYTHON = os.path.expanduser("~/.local/share/codex-ecosystem/tools/vllm-0.30.0/bin/python")
GPU_MIN_FREE_MIB = 9 * 1024
KILL_CHECK_SECONDS = 30
EXT_RETRY = timedelta(minutes=10)
NEWS_FIELDS = ("id", "headline", "symbols", "source", "author", "created_at", "updated_at", "url", "received_at")
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
        self.end = args.until or self.schedule.service_end
        self.journal = common.Journal(self.state, self.trade_date, clock=clock)
        key, secret = live_news.read_credentials(common.DATA_ENV)
        self.data = live_news.DataClient(key, secret, limiter=live_news.RateLimiter(args.rate))
        del key, secret
        self.requested_mode = args.mode or cfg["mode"]
        self.account_verdict = "not_checked"
        broker, self.sod = None, None
        mode = "dry-run"
        if self.requested_mode == "paper":
            try:
                k, s = ex.trading_credentials()
                broker = ex.AlpacaBroker(ex.make_trading_client(k, s))
                del k, s
                self.sod = ex.start_check(broker)
                mode = "paper"
                self.account_verdict = "ready_for_paper"
            except ex.AccountRefused as error:
                self.account_verdict = f"refused:{error}"
                broker = None
        self.executor = ex.Executor(mode, self.journal, self.state, broker=broker, clock=clock)
        self.mode = mode
        assets = self.data.assets()
        self.assets = assets
        self.screener = planner.Screener(self.calendar, assets)
        prev = self.calendar.previous(self.trade_date)
        backfill_from = prev.close_utc - timedelta(hours=24)
        self.poller = live_news.NewsPoller(self.data, backfill_from, clock=clock)
        self.first_poll = True
        self.queue_path = os.path.join(self.state, "score-queue.jsonl")
        self.scores_path = os.path.join(self.state, "scores.jsonl")
        self.scores_offset = 0
        self.scores = {}
        for row in common.read_jsonl(self.scores_path):
            self.scores[row["event_id"]] = row
        self.queued = {r["event_id"] for r in common.read_jsonl(self.queue_path) if "event_id" in r}
        self.candidates = {}  # event_id -> candidate (with lane)
        self.bars = {}        # (symbol, session) -> bars
        self.lanes = {}       # (symbol, session) -> (lane, prior_close, med20, complete)
        self.announced = set()
        self.shadow = shadow.ShadowTracker()
        self.open_pool = {}   # event_id -> scored open-auction candidate for today
        self.rth_pending = {}
        self.exposure = planner.Exposure()
        self.sim_positions = {}  # dry-run: symbol -> signed qty of intended entries
        self.done_steps = set()
        self.exit_orders = {}    # symbol -> client_order_id of the live exit order
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
        self.journal.write("lifecycle", event="start", trade_date=self.trade_date.isoformat(),
                           requested_mode=self.requested_mode, mode=self.mode, account_verdict=self.account_verdict,
                           end=common.iso(self.end), assets=len(assets), schedule={k: common.iso(v) if isinstance(v, datetime) else str(v)
                                                                                   for k, v in self.schedule.__dict__.items()},
                           code_sha256={n: common.sha256_file(os.path.join(HERE, n)) for n in sorted(os.listdir(HERE)) if n.endswith(".py")},
                           news_signal_sha256=common.sha256_file(os.path.join(common.NEWS_LLM, "news_signal.py")),
                           score_py_sha256=common.sha256_file(os.path.join(common.NEWS_LLM, "score.py")),
                           strategy=common.STRATEGY_ID, sod_equity=(self.sod or {}).get("equity"))

    def rebuild_exposure(self):
        """After a restart: count today's nf1 entries and current gross from the broker."""
        broker = self.executor.broker
        prefix = f"{planner.ORDER_PREFIX}{self.trade_date.strftime('%Y%m%d')}-"
        orders = broker.orders("all", after=self.schedule.premarket_start - timedelta(hours=12))
        for o in orders:
            cid = str(o.get("client_order_id") or "")
            parts = cid[len(prefix):].split("-") if cid.startswith(prefix) else []
            if len(parts) < 3 or parts[0] not in ("opg", "rth") or o.get("status") in ("canceled", "rejected", "expired"):
                continue
            label = planner.OPEN_AUCTION if parts[0] == "opg" else planner.RTH
            leg = parts[-1]
            symbol = "-".join(parts[1:-1])
            key = (label, leg)
            self.exposure.names[key] = self.exposure.names.get(key, 0) + 1
            self.exposure.symbols.add(symbol)
            if o.get("status") not in ("filled",):
                self.exposure.gross += planner.NOTIONAL_PER_NAME  # open entry: count at the per-name cap
            self.executor.submitted[cid] = o
        for p in broker.positions():
            self.exposure.gross += abs(Decimal(str(p.get("market_value") or 0)))
            self.exposure.symbols.add(p["symbol"])
        self.journal.write("lifecycle", event="exposure_rebuilt", gross=str(self.exposure.gross),
                           names={f"{k[0]}:{k[1]}": v for k, v in self.exposure.names.items()})

    # -- news, screening, lanes, scoring queue ------------------------------------------

    def ensure_lanes(self, cands):
        need = sorted({(c["symbol"], c["session"]) for c in cands if (c["symbol"], c["session"]) not in self.lanes})
        by_session = {}
        for sym, sess in need:
            by_session.setdefault(sess, []).append(sym)
        for sess, syms in by_session.items():
            sd = date.fromisoformat(sess)
            prior = self.calendar.prior_sessions(sd, sig.LOOKBACK_SESSIONS)
            if not prior:
                for s in syms:
                    self.lanes[(s, sess)] = (None, None, None, False)
                continue
            bars = self.data.daily_bars(syms, prior[0], prior[-1])
            for s in syms:
                self.bars[(s, sess)] = bars.get(s, [])
                self.lanes[(s, sess)] = planner.lane_from_bars(self.calendar, sd, bars.get(s, []))

    def poll_news(self, now):
        articles = self.poller.poll()
        backfill = self.first_poll
        self.first_poll = False
        fresh = []
        for a in articles:
            self.counts["news_received"] += 1
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
            fresh.append(cand)
        if fresh:
            self.ensure_lanes(fresh)
        for cand in fresh:
            lane, prior_close, med20, complete = self.lanes[(cand["symbol"], cand["session"])]
            cand.update(lane=lane, prior_close=prior_close, prior_median_dollar_volume_20=med20, prior_bars_complete=complete)
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
        if not os.path.exists(self.scores_path):
            return
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
                               ext_segment=cand["ext_segment"], lane=cand["lane"], label=row["label"], score=row["score"],
                               device=row.get("device"), raw_output=row.get("raw_output"), stop=row.get("stop"),
                               revision=row.get("revision"), variant=row.get("variant"),
                               seconds_after_receipt=round((now - received).total_seconds(), 1))
            if cand["ext_segment"] in (planner.EXT_PRE, planner.EXT_POST) or cand["lane"] == sig.SMALL:
                reason = "extended_hours" if cand["ext_segment"] in (planner.EXT_PRE, planner.EXT_POST) else "small_lane"
                self.shadow.add(cand, reason, received)
            if cand["session"] != self.trade_date.isoformat():
                continue  # traded by the run for its own session
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

    # -- trading steps -------------------------------------------------------------------

    def run_open_basket(self, now):
        pool = list(self.open_pool.values())
        unscored = [c for c in self.candidates.values() if c["session"] == self.trade_date.isoformat()
                    and c["session_label"] == planner.OPEN_AUCTION and c["event_id"] not in self.scores]
        if unscored and now < self.schedule.opg_submit_by - timedelta(minutes=3):
            return False  # wait for the backlog, up to 09:24
        for c in unscored:
            self.journal.write("decision", event_id=c["event_id"], symbol=c["symbol"], session_label=planner.OPEN_AUCTION,
                               lane=c["lane"], action="skip", reason="unscored_at_basket_cutoff")
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
            events.append({**c, "ref_price": ref, "asset": asset or {}, "ssr": self.ssr_for(c)})
        equity = (self.sod or {}).get("equity")
        decisions, intents = planner.build_open_basket(events, self.trade_date, self.exposure, equity)
        for d in decisions:
            self.journal.write("decision", **d)
            self.counts[f"decision:{d['session_label']}:{d['action']}"] += 1
        for intent in intents:
            if now > self.schedule.opg_submit_by:
                self.journal.write("order_refused", reason="opg_cutoff_passed", intent=intent)
                continue
            leg = planner.LEG_LONG if intent["side"] == "buy" else planner.LEG_SHORT
            self.send(intent, {"purpose": "entry", "session_label": planner.OPEN_AUCTION, "lane": sig.LIQUID, "leg": leg})
        return True

    def run_rth_entries(self, now):
        due = [c for c in self.rth_pending.values() if sig.as_utc(c["entry_utc"]) <= now]
        if not due:
            return
        symbols = sorted({c["symbol"] for c in due})
        snaps = self.data.snapshots(symbols)
        for c in due:
            del self.rth_pending[c["event_id"]]
            snap = snaps.get(c["symbol"]) or {}
            today_bar = snap.get("dailyBar") or {}
            today_low = None
            if today_bar.get("t") and sig.as_utc(today_bar["t"]).astimezone(common.NY).date() == self.trade_date:
                today_low = today_bar.get("l")
            asset = self.fresh_asset(c["symbol"]) if c.get("lane") == sig.LIQUID else None
            ev = {**c, "asset": asset or {}, "ssr": self.ssr_for(c, today_low)}
            equity = (self.sod or {}).get("equity")
            decision, intent = planner.plan_rth_entry(ev, snap.get("latestQuote"), now, self.trade_date, self.exposure, equity)
            self.journal.write("decision", **decision)
            self.counts[f"decision:rth:{decision['action']}"] += 1
            if intent:
                self.send(intent, {"purpose": "entry", "session_label": planner.RTH, "lane": c["lane"], "leg": decision["leg"]})

    def send(self, intent, context):
        order = self.executor.send(intent, context)
        if order is not None:
            self.counts[f"orders_{self.mode}:{context.get('session_label')}:{context.get('purpose')}"] += 1
            if self.mode == "dry-run" and context.get("purpose") == "entry":
                sign = 1 if intent["side"] == "buy" else -1
                self.sim_positions[intent["symbol"]] = self.sim_positions.get(intent["symbol"], 0) + sign * int(intent["qty"])
            if context.get("purpose") == "exit":
                self.exit_orders[intent["symbol"]] = intent["client_order_id"]
        return order

    def positions(self):
        if self.mode == "paper":
            return [p for p in self.executor.broker.positions()]
        return [{"symbol": s, "qty": str(q)} for s, q in self.sim_positions.items() if q]

    def open_exit_symbols(self):
        if self.mode != "paper":
            return set(self.exit_orders)
        live = {o["client_order_id"] for o in self.executor.broker.orders("open")}
        return {s for s, cid in self.exit_orders.items() if cid in live}

    def cancel_entries(self, now, older_than=None):
        """Paper: cancel open nf1 entry orders (all, or those submitted more than older_than ago)."""
        if self.mode != "paper":
            return
        prefix = f"{planner.ORDER_PREFIX}{self.trade_date.strftime('%Y%m%d')}-"
        for o in self.executor.broker.orders("open"):
            cid = str(o.get("client_order_id") or "")
            if not cid.startswith(prefix) or cid[len(prefix):].split("-")[0] not in ("opg", "rth"):
                continue
            submitted = o.get("submitted_at")
            if older_than is not None and submitted is not None:
                submitted = submitted if isinstance(submitted, datetime) else sig.as_utc(str(submitted))
                if now - submitted < older_than:
                    continue
            if cid[len(prefix):].startswith("opg") and older_than is not None:
                continue  # OPG orders resolve in the opening auction
            try:
                self.executor.broker.cancel(o["id"])
                self.journal.write("order_cancel", client_order_id=cid, symbol=o.get("symbol"),
                                   reason="stale_entry" if older_than is not None else "before_close_exits")
            except Exception as error:  # noqa: BLE001
                self.journal.write("order_cancel_failed", client_order_id=cid, error=str(error)[:200])

    def run_exits(self, now):
        sch = self.schedule
        if self.mode == "paper" and sch.open_utc <= now < sch.cls_start and (
                self.last_stale_check is None or now - self.last_stale_check >= timedelta(seconds=30)):
            self.last_stale_check = now
            self.cancel_entries(now, older_than=planner.RTH_ENTRY_GRACE)
        if "cls" not in self.done_steps and planner.cls_submission_allowed(sch, now):
            self.done_steps.add("cls")
            self.cancel_entries(now)
            for intent in planner.plan_cls_exits(self.positions(), self.trade_date, self.open_exit_symbols()):
                self.send(intent, {"purpose": "exit", "session_label": "close", "stage": "cls"})
        if "mkt" not in self.done_steps and sch.market_flatten_at <= now < sch.close_utc:
            self.done_steps.add("mkt")
            for intent in planner.plan_market_flatten(self.positions(), self.trade_date, self.open_exit_symbols()):
                self.send(intent, {"purpose": "exit", "session_label": "close", "stage": "mkt"})
        if sch.ext_flatten_at <= now < sch.ext_end and (self.last_ext is None or now - self.last_ext >= EXT_RETRY):
            positions = self.positions() if self.mode == "paper" else []
            self.last_ext = now
            if positions:
                self.ext_round += 1
                self.cancel_open_nf1()
                quotes = self.data.latest_quotes(sorted(p["symbol"] for p in positions))
                intents, missing = planner.plan_ext_flatten(positions, quotes, self.trade_date, stage=f"ext{self.ext_round}")
                for sym in missing:
                    self.journal.write("risk", event="ext_flatten_no_quote", symbol=sym)
                for intent in intents:
                    self.send(intent, {"purpose": "exit", "session_label": "after_close", "stage": intent["client_order_id"].split("-")[2]})

    def cancel_open_nf1(self):
        if self.mode != "paper":
            return
        for o in self.executor.broker.orders("open"):
            if planner.is_nf1(o.get("client_order_id")):
                try:
                    self.executor.broker.cancel(o["id"])
                    self.journal.write("order_cancel", client_order_id=o["client_order_id"], symbol=o["symbol"])
                except Exception as error:  # noqa: BLE001
                    self.journal.write("order_cancel_failed", client_order_id=o["client_order_id"], error=str(error)[:200])

    def kill_check(self, now):
        if self.mode != "paper" or self.executor.killed:
            return
        if self.last_kill_check and now - self.last_kill_check < timedelta(seconds=KILL_CHECK_SECONDS):
            return
        self.last_kill_check = now
        account = self.executor.broker.account()
        if planner.kill_switch_triggered(self.sod.get("equity"), account.get("equity")):
            self.executor.killed = True
            self.journal.write("risk", event="kill_switch", sod_equity=self.sod.get("equity"), equity=account.get("equity"))
            self.cancel_open_nf1()
            positions = self.executor.broker.positions()
            if self.schedule.open_utc <= now < self.schedule.close_utc:
                for p in positions:
                    self.send(planner.exit_intent(self.trade_date, "kill", p["symbol"], p["qty"]),
                              {"purpose": "kill_flatten", "session_label": "kill"})
            else:
                quotes = self.data.latest_quotes(sorted(p["symbol"] for p in positions)) if positions else {}
                intents, _ = planner.plan_ext_flatten(positions, quotes, self.trade_date, stage="kill")
                for intent in intents:
                    self.send(intent, {"purpose": "kill_flatten", "session_label": "kill"})

    def reconcile(self):
        if self.mode != "paper":
            rec = {"ok": True, "mode": "dry-run", "problems": [], "note": "no orders sent; nothing to reconcile",
                   "intended_orders": len(self.executor.submitted)}
            self.journal.write("reconciliation", **rec)
            return rec
        broker = self.executor.broker
        prefix = f"{planner.ORDER_PREFIX}{self.trade_date.strftime('%Y%m%d')}-"
        after = self.schedule.premarket_start - timedelta(hours=12)
        closed = broker.orders("closed", after=after)
        fills = [o for o in closed if str(o.get("client_order_id", "")).startswith(prefix) and Decimal(str(o.get("filled_qty") or 0)) > 0]
        for f in fills:
            self.journal.write("fill", **f)
        account = broker.account()
        rec = planner.reconcile(self.sod["cash"], account["cash"], fills, broker.positions(), broker.orders("open"))
        self.journal.write("reconciliation", mode="paper", **rec)
        return rec

    # -- main loop -------------------------------------------------------------------------

    def status(self, now):
        payload = {"at": common.iso(now), "trade_date": self.trade_date.isoformat(), "mode": self.mode,
                   "account_verdict": self.account_verdict, "counts": dict(self.counts),
                   "pending_scores": self.pending_scores(), "scorer_device": self.scorers.device,
                   "open_pool": len(self.open_pool), "rth_pending": len(self.rth_pending), "shadow_pending": len(self.shadow),
                   "journal": self.journal.path, "http": dict(self.data.tally)}
        tmp = os.path.join(self.state, "status.json.tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=1, sort_keys=True)
        os.replace(tmp, os.path.join(self.state, "status.json"))

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
            self.exposure = planner.Exposure()
            self.sim_positions = {}
            self.executor.submitted = {}
            self.journal.write("lifecycle", event="basket_preview_end")
        if "basket" not in self.done_steps and self.schedule.basket_at <= now <= self.schedule.opg_submit_by:
            if self.run_open_basket(now):
                self.done_steps.add("basket")
        if self.schedule.open_utc <= now < self.schedule.cls_end:
            self.run_rth_entries(now)
        self.run_exits(now)
        if "reconcile" not in self.done_steps and now >= self.schedule.close_utc + timedelta(minutes=10):
            if not self.positions() or now >= self.schedule.ext_end:
                self.done_steps.add("reconcile")
                self.reconcile()

    def summary(self):
        if "reconcile" not in self.done_steps:
            self.done_steps.add("reconcile")
            self.reconcile()
        path = os.path.join(self.state, "receipts", f"{self.trade_date.isoformat()}-summary.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        receipt = {"schema": "news-forward-daily-summary/1", "evidence_label": common.EVIDENCE_LABEL,
                   "strategy": common.STRATEGY_ID, "trade_date": self.trade_date.isoformat(), "mode": self.mode,
                   "requested_mode": self.requested_mode, "account_verdict": self.account_verdict,
                   "counts": dict(sorted(self.counts.items())), "journal_kinds": dict(self.journal.counts),
                   "journal": self.journal.path, "journal_sha256": common.sha256_file(self.journal.path),
                   "http": dict(self.data.tally), "written_at": common.iso(self.clock())}
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(receipt, handle, indent=1, sort_keys=True)
        with open(path, "rb") as handle:
            import hashlib  # noqa: PLC0415
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
        self.journal.write("lifecycle", event="stopping", counts=dict(self.counts))
        path = self.summary()
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
    parser.add_argument("--rate", type=int, default=240, help="data requests per minute (max 300)")
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
