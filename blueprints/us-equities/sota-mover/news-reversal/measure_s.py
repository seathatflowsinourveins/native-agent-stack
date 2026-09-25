#!/usr/bin/env python3
"""Return-free planning measurement for the rth_reversal protocol (forward-protocol.json#/planning_measurement).

  python measure_s.py [--data-root ROOT] [--out RESULT.json]

Reads the frozen NEWS-PIT-LLM study's private inputs and refuses (exit 2) unless every one hashes to the study's
own pin (../news-llm/protocol.json#/pins/private_inputs). It computes only:

* S, the entry-spread term that separates NEWS-3's in-sample gross from the mirrored (reversal) trade: the mean
  over NEWS-3's long-short days of (the mean full quoted spread of the day's FAVORABLE long positions + that of its
  UNFAVORABLE short positions), in bps of the entry quote's mid. Per position the momentum and reversal gross sum
  to about minus the full spread, so the in-sample reversal gross is about 11.0 - S bps/day;
* the both-legs->=2 rate and names per leg of the reversal's legs, for 2025-01-02..2026-09-18 (every headline
  scored by the 2024-12-31 checkpoint, the one the forward test uses) and for the whole NEWS-3 segment, both
  study-consistent and forward-like (forward_like_legs);
* the count-based sd scaling E_fwd[1/n_long + 1/n_short] / E_news3[1/n_long + 1/n_short] over long-short days.

No exit price, return or P&L is computed or printed: labels, lanes, sessions, Rule 201 inputs and entry quotes are
read, and from the auction file only whether an official close exists (news_signal.select_auction_price is not
None), because NEWS-3 required one.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import math
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent / "news-llm"


def load_news_signal():
    spec = importlib.util.spec_from_file_location("news_signal", STUDY / "news_signal.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["news_signal"] = module
    spec.loader.exec_module(module)
    return module


sig = load_news_signal()

DEFAULT_DATA_ROOT = Path(os.path.expanduser("~/.local/state/native-agent-stack/research/sota-mover/news-llm"))
NEWS3_SEGMENT = ("2016-02-02", "2026-09-18")  # the study's rth_full segment
FORWARD_CHECKPOINT_SEGMENT = ("2025-01-02", "2026-09-18")  # 2025-2026 headlines map to the 2024-12-31 checkpoint
FORWARD_MAX_SPREAD_BPS = 50.0
FORWARD_MAX_NAMES_PER_LEG = 12
IN_SAMPLE_GROSS_BPS = 11.0083  # minus NEWS-3's gross mean (evaluation-summary.json)
CONFIRMATORY_MIN_EFFECT_BPS = 5.0
NEWS3_DAYS = 2618


class Refusal(SystemExit):
    def __init__(self, reason):
        super().__init__(2)
        self.reason = reason


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def spread_bps(quote):
    """Full quoted spread in bps of mid for {"bid", "ask"}."""
    bid, ask = float(quote["bid"]), float(quote["ask"])
    return (ask - bid) / ((ask + bid) / 2.0) * 1e4


def in_segment(session, segment):
    return segment[0] <= session <= segment[1]


def news3_positions(events, sides, quotes, has_close):
    """NEWS-3's liquid RTH positions in the momentum direction, as evaluate.build_positions selects them
    (operative side, entry quote, official close, Rule 201-flagged shorts excluded), without any price
    beyond the entry quote. Returns [{session, side, spread_bps}]."""
    out = []
    for ev in events:
        side = sides.get(ev["event_id"], 0)
        if side == 0 or not in_segment(ev["session"], NEWS3_SEGMENT):
            continue
        quote = quotes.get(ev["event_id"])
        if quote is None or not has_close.get((ev["symbol"], ev["session"]), False):
            continue
        if side == -1 and sig.ssr_flag(ev, quote):
            continue
        out.append({"session": ev["session"], "side": side, "spread_bps": spread_bps(quote)})
    return out


def long_short_days(positions):
    """{session: {1: [...], -1: [...]}} for days where both legs have >= news_signal.MIN_NAMES_PER_LEG names."""
    by_day = defaultdict(lambda: {1: [], -1: []})
    for p in positions:
        by_day[p["session"]][p["side"]].append(p)
    return {d: legs for d, legs in by_day.items()
            if len(legs[1]) >= sig.MIN_NAMES_PER_LEG and len(legs[-1]) >= sig.MIN_NAMES_PER_LEG}


def spread_term(days, segment=None):
    """S: mean over long-short days of (the long leg's mean spread + the short leg's mean spread), bps."""
    vals = [sum(p["spread_bps"] for p in legs[1]) / len(legs[1]) + sum(p["spread_bps"] for p in legs[-1]) / len(legs[-1])
            for d, legs in days.items() if segment is None or in_segment(d, segment)]
    return (sum(vals) / len(vals) if vals else None), len(vals)


def inverse_size_mean(days, segment=None):
    """E[1/n_long + 1/n_short] over long-short days (the count-based variance factor)."""
    vals = [1.0 / len(legs[1]) + 1.0 / len(legs[-1]) for d, legs in days.items() if segment is None or in_segment(d, segment)]
    return (sum(vals) / len(vals) if vals else None), len(vals)


def reversal_legs(events, sides, quotes, has_close, segment, *, forward_like):
    """The reversal's positions per session: FAVORABLE -> short (-1), UNFAVORABLE -> long (+1).

    study-consistent: NEWS-3's selection with the sides flipped (entry quote and official close required,
    Rule 201-flagged reversal shorts excluded). forward_like: the forward rule's in-sample-computable parts
    (entry quote with spread <= 50 bps, Rule 201 on the reversal's shorts, at most 12 names per leg by entry
    time; no close requirement, since forward exits are CLS fills). Shortable/easy-to-borrow and the live
    session-low check are not computable historically (limitation L5 of the study)."""
    rows = []
    for ev in events:
        side = -sides.get(ev["event_id"], 0)
        if side == 0 or not in_segment(ev["session"], segment):
            continue
        quote = quotes.get(ev["event_id"])
        if quote is None:
            continue
        if forward_like:
            if spread_bps(quote) > FORWARD_MAX_SPREAD_BPS:
                continue
        elif not has_close.get((ev["symbol"], ev["session"]), False):
            continue
        if side == -1 and sig.ssr_flag(ev, quote):
            continue
        rows.append((ev["session"], ev["entry_utc"], int(ev["news_id"]) if str(ev["news_id"]).isdigit() else 0, side,
                     spread_bps(quote)))
    legs = defaultdict(lambda: {1: [], -1: []})
    for session, _entry, _nid, side, spread in sorted(rows):
        leg = legs[session][side]
        if forward_like and len(leg) >= FORWARD_MAX_NAMES_PER_LEG:
            continue
        leg.append({"session": session, "side": side, "spread_bps": spread})
    return legs


def leg_statistics(legs, sessions):
    """Both-legs->=2 rate over `sessions` (every XNYS session of the period) and names-per-leg summaries."""
    n_long = [len(legs.get(s, {1: []})[1]) for s in sessions]
    n_short = [len(legs.get(s, {-1: []})[-1]) for s in sessions]
    both = [s for s, a, b in zip(sessions, n_long, n_short) if a >= sig.MIN_NAMES_PER_LEG and b >= sig.MIN_NAMES_PER_LEG]

    def summary(xs):
        ordered = sorted(xs)
        q = lambda p: ordered[min(len(ordered) - 1, int(p * (len(ordered) - 1)))] if ordered else None  # noqa: E731
        return {"mean": sum(xs) / len(xs) if xs else None, "median": statistics.median(xs) if xs else None,
                "p10": q(0.10), "p90": q(0.90), "share_ge_2": sum(1 for x in xs if x >= 2) / len(xs) if xs else None,
                "share_at_12": sum(1 for x in xs if x >= FORWARD_MAX_NAMES_PER_LEG) / len(xs) if xs else None}

    return {"sessions": len(sessions), "both_legs_ge_2_sessions": len(both),
            "both_legs_ge_2_rate": len(both) / len(sessions) if sessions else None,
            "names_long": summary(n_long), "names_short": summary(n_short)}


def planning_label(s_bps):
    """confirmatory when 11.0 - S >= 5 bps/day, else exploratory (forward-protocol.json#/planning_measurement)."""
    if s_bps is None:
        return None, None
    effect = IN_SAMPLE_GROSS_BPS - s_bps
    return effect, ("confirmatory" if effect >= CONFIRMATORY_MIN_EFFECT_BPS else "exploratory")


# --------------------------------------------------------------------------------------------------------------
# I/O (pinned private inputs; streamed; nothing outside entry quotes and close existence is kept)
# --------------------------------------------------------------------------------------------------------------


def verify_inputs(data_root):
    pins = json.loads((STUDY / "protocol.json").read_text())["pins"]["private_inputs"]
    hashes = {}
    for name, want in sorted(pins.items()):
        path = Path(data_root) / name
        if not path.exists():
            raise Refusal(f"private input missing: {name}")
        got = sha256_file(path)
        if got != want:
            raise Refusal(f"private input differs from the frozen study's pin: {name}")
        hashes[name] = got
    return hashes


def read_jsonl(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def load(data_root):
    root = Path(data_root)
    events = [ev for ev in read_jsonl(root / "events.jsonl.gz") if ev["window"] == sig.RTH and ev["lane"] == sig.LIQUID]
    wanted = {ev["event_id"] for ev in events}
    sides = {}
    for year in range(sig.FIRST_CHECKPOINT_YEAR, sig.LAST_CHECKPOINT_YEAR + 1):
        for row in read_jsonl(root / "scores" / f"scores-{year}1231.jsonl"):
            if row["event_id"] in wanted:
                if row["event_id"] in sides:
                    raise Refusal(f"two score rows for {row['event_id']}")
                sides[row["event_id"]] = sig.operative_score(row.get("raw_output"), row.get("stop"))[1]
    entries = {ev["event_id"]: ev["entry_utc"] for ev in events}
    quotes = {}
    for row in read_jsonl(root / "spreads" / "quotes.jsonl"):
        eid = row["event_id"]
        if eid in entries and eid not in quotes:
            q = sig.rth_entry_quote(row.get("quotes"), entries[eid])
            if q is not None:
                quotes[eid] = q
    venue = {(ev["symbol"], ev["session"]): ev.get("exchange") for ev in events}
    has_close = {}
    for row in read_jsonl(root / "auctions" / "auctions.jsonl.gz"):
        key = (row["symbol"], row["session"])
        if key in venue:
            has_close[key] = sig.select_auction_price(row.get("c"), "close", venue[key]) is not None
    return events, sides, quotes, has_close


def sessions_between(segment):
    with open(HERE.parents[1] / "mover-v3/data/session-calendar.json", encoding="utf-8") as handle:
        cal = sig.Calendar.from_calendar_json(json.load(handle))
    return [s.session.isoformat() for s in cal.sessions if in_segment(s.session.isoformat(), segment)]


def measure(events, sides, quotes, has_close):
    news3 = long_short_days(news3_positions(events, sides, quotes, has_close))
    s_all, days_all = spread_term(news3)
    s_fwd_seg, days_fwd_seg = spread_term(news3, FORWARD_CHECKPOINT_SEGMENT)
    inv_news3, _ = inverse_size_mean(news3)
    out = {"news3": {"long_short_days": days_all, "matches_frozen_news3_days": days_all == NEWS3_DAYS,
                     "S_bps": s_all, "S_bps_2025_2026": s_fwd_seg, "long_short_days_2025_2026": days_fwd_seg,
                     "mean_position_full_spread_bps": (sum(p["spread_bps"] for legs in news3.values() for side in (1, -1)
                                                           for p in legs[side]) /
                                                       sum(len(legs[1]) + len(legs[-1]) for legs in news3.values())) if news3 else None,
                     "inverse_size_mean": inv_news3}}
    effect, label = planning_label(s_all)
    out["planning"] = {"in_sample_gross_bps": IN_SAMPLE_GROSS_BPS, "S_bps": s_all, "planning_effect_bps": effect,
                       "mid_based_effect_bps": None if s_all is None else IN_SAMPLE_GROSS_BPS - s_all / 2.0,
                       "confirmatory_min_effect_bps": CONFIRMATORY_MIN_EFFECT_BPS, "label": label}
    for name, segment in (("2025_2026", FORWARD_CHECKPOINT_SEGMENT), ("news3_segment", NEWS3_SEGMENT)):
        sessions = sessions_between(segment)
        block = {}
        for variant, forward_like in (("study_consistent", False), ("forward_like", True)):
            legs = reversal_legs(events, sides, quotes, has_close, segment, forward_like=forward_like)
            stats = leg_statistics(legs, sessions)
            ls = {d: v for d, v in legs.items() if len(v[1]) >= sig.MIN_NAMES_PER_LEG and len(v[-1]) >= sig.MIN_NAMES_PER_LEG}
            stats["inverse_size_mean"], _ = inverse_size_mean(ls)
            stats["S_bps_reversal_legs"], _ = spread_term(ls)
            block[variant] = stats
        out[name] = block
    fwd = out["2025_2026"]["forward_like"]["inverse_size_mean"]
    ratio = None if (fwd is None or not inv_news3) else fwd / inv_news3
    out["sd_scaling"] = {"rule": "var_forward = var_news3 x E_fwd[1/n_long + 1/n_short] / E_news3[...] (idiosyncratic variance "
                                 "only; the common part of daily variance is not modelled)",
                         "ratio": ratio, "sd_factor": None if ratio is None else math.sqrt(ratio),
                         "forward_sd_bps_sample": None if ratio is None else 69.91 * math.sqrt(ratio),
                         "forward_sd_bps_nw_effective": None if ratio is None else 78.67 * math.sqrt(ratio)}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--out", type=Path)
    a = parser.parse_args(argv)
    try:
        hashes = verify_inputs(a.data_root)
    except Refusal as r:
        print(f"REFUSED: {r.reason}", file=sys.stderr)
        return 2
    result = measure(*load(a.data_root))
    result = {"schema": "news-reversal-s-measurement/1", "script_sha256": sha256_file(__file__),
              "inputs": {"root": "~/.local/state/native-agent-stack/research/sota-mover/news-llm", "sha256": hashes,
                         "pins_equal_frozen_study": True},
              "return_free": "entry quotes, labels, lanes, sessions, Rule 201 inputs and close existence only; no exit price, return or P&L",
              **result}
    text = json.dumps(result, indent=1, sort_keys=True)
    if a.out:
        a.out.write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
