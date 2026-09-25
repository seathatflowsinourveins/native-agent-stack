#!/usr/bin/env python3
"""Confirmatory evaluation of the news-LLM direction study (runs only after the freeze).

  python evaluate.py [--data-root ROOT] [--freeze-record PATH] [--protocol-sha256 SHA] [--out RESULT.json]
  python evaluate.py --print-pins [--data-root ROOT]     # hashes only, no data read

run() refuses (exit 2) before it opens any event, score or price unless all of these hold
(the standard of blueprints/us-equities/sota-mover/eap/evaluate.py):
* receipts/freeze-record.json names the sha256 of protocol.json and the full commit that
  froze it (--protocol-sha256, when given, must equal the record);
* protocol.json hashes to that sha256, has status 'frozen_pre_outcome',
  frozen_before_outcomes true and frozen_at set;
* the freeze commit is an ancestor of HEAD and protocol.json at that commit hashes to the
  recorded sha256;
* every pin in protocol.json#/pins matches: code (news_signal.py, evaluate.py, prepare.py,
  score.py, collect_auctions.py, receipts.py), reference data (fees, session calendar,
  checkpoints.json) and private inputs (events, every scores file, auctions, entry quotes);
* ``git status --porcelain`` is empty for the study directory; HEAD is recorded.
Only authorize() runs that whole chain, and only it issues the Authorization token that
data_pass() and every loader require; each loader also re-runs guard() on the protocol and
reads only the pinned files under the authorized data root. guard() alone (protocol checks
only) cannot open the data.

Positions use the operative score (news_signal.operative_score, D22); the model authors'
strict label rule is evaluated alongside as a descriptive sensitivity for every item.

Families: primary fixed sequence at alpha 0.05, NEWS-1 then NEWS-4 (long-short gate);
secondary Holm at alpha 0.05 over three members: NEWS-1, the long-only pair (NEWS-2B and
NEWS-2 as one intersection-union member, p = max of the two) and NEWS-3. Each family
bounds its false rejections at 0.05, so the chance of any false gate is at most 0.10.
Non-rejection is read through the one-sided 95% upper bound of the mean against 3 bps/day
(the model authors' estimate) and 34 bps/day (the paper).
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_news_signal():
    spec = importlib.util.spec_from_file_location("news_signal", HERE / "news_signal.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["news_signal"] = module
    spec.loader.exec_module(module)
    return module


sig = load_news_signal()

REPO = HERE.parents[3]
PROTOCOL_PATH = HERE / "protocol.json"
FREEZE_RECORD_PATH = HERE / "receipts" / "freeze-record.json"
FROZEN_STATUS = "frozen_pre_outcome"
PRIVATE_ROOT = Path(os.path.expanduser("~/.local/state/native-agent-stack/research/sota-mover/news-llm"))
CODE_PINS = ("news_signal.py", "evaluate.py", "prepare.py", "score.py", "collect_auctions.py", "receipts.py")
REFERENCE_PINS = {
    "fees-v3.json": "blueprints/us-equities/mover-v3/data/fees-v3.json",
    "session-calendar.json": "blueprints/us-equities/mover-v3/data/session-calendar.json",
    "checkpoints.json": "blueprints/us-equities/sota-mover/news-llm/checkpoints.json",
}
PRIVATE_INPUTS = ("events.jsonl.gz", "auctions/auctions.jsonl.gz", "spreads/quotes.jsonl") + tuple(
    f"scores/scores-{y}1231.jsonl" for y in range(sig.FIRST_CHECKPOINT_YEAR, sig.LAST_CHECKPOINT_YEAR + 1))
PRIOR_BPS = {"model_authors_3bps": 0.0003, "paper_34bps": 0.0034}
Z95 = 1.6448536269514722
_TOKEN = object()
_RUN_TOKEN = object()


class Refusal(SystemExit):
    def __init__(self, reason):
        super().__init__(2)
        self.reason = reason

    def __str__(self):
        return f"refusing: {self.reason}"


class FrozenProtocol:
    """Proof that guard() accepted the protocol; cannot be built without the module token."""

    def __init__(self, protocol, sha256, path, token):
        if token is not _TOKEN:
            raise Refusal("FrozenProtocol can only be created by guard()")
        self.protocol, self.sha256, self.path, self._token = protocol, sha256, Path(path), token


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def _hex(value, length):
    v = str(value or "").strip().lower()
    return v if len(v) == length and all(c in "0123456789abcdef" for c in v) else None


def read_freeze_record(path):
    try:
        rec = json.loads(Path(path).read_text())
    except FileNotFoundError:
        raise Refusal(f"freeze record missing: {path}") from None
    except ValueError:
        raise Refusal("freeze record is not valid JSON") from None
    sha = _hex(rec.get("protocol_sha256"), 64)
    if sha is None:
        raise Refusal("freeze record has no protocol_sha256")
    commit = _hex(rec.get("protocol_commit"), 40)
    if commit is None:
        raise Refusal("freeze record has no full protocol_commit")
    return sha, commit


def guard(protocol_path, expected_sha256):
    """The parsed protocol, only when frozen and its bytes hash to ``expected_sha256``."""
    raw = Path(protocol_path).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if _hex(expected_sha256, 64) != actual:
        raise Refusal(f"protocol sha256 mismatch: expected {expected_sha256!r}, file has {actual}")
    p = json.loads(raw)
    if p.get("status") != FROZEN_STATUS or p.get("frozen_before_outcomes") is not True or not p.get("frozen_at"):
        raise Refusal(f"protocol is not frozen (status={p.get('status')!r}, "
                      f"frozen_before_outcomes={p.get('frozen_before_outcomes')!r}, frozen_at={p.get('frozen_at')!r})")
    return FrozenProtocol(p, actual, protocol_path, _TOKEN)


class Authorization:
    """Issued only by authorize() after the freeze record, frozen protocol, pins, clean tree
    and freeze-commit checks; the only key to data_pass() and the loaders."""

    def __init__(self, frozen, head, study_dir, data_root, repo_root, token):
        if token is not _RUN_TOKEN:
            raise Refusal("an Authorization can only be issued by authorize()")
        if not isinstance(frozen, FrozenProtocol) or frozen._token is not _TOKEN:
            raise Refusal("an Authorization needs the FrozenProtocol returned by guard()")
        self.frozen, self.head, self._token = frozen, head, token
        self.study_dir, self.data_root, self.repo_root = Path(study_dir), Path(data_root), Path(repo_root)


def require(auth):
    """Every loader and data_pass() call this first: an authorize()-issued token, and a
    protocol file still byte-identical to the one authorized."""
    if not isinstance(auth, Authorization) or auth._token is not _RUN_TOKEN:
        raise Refusal("data access requires the Authorization issued by authorize() "
                      "(freeze record, pins, clean tree and freeze commit checked)")
    guard(auth.frozen.path, auth.frozen.sha256)
    return auth


def git(directory, *args):
    return subprocess.run(["git", *args], cwd=directory, capture_output=True, text=True)


def git_clean_head(directory):
    st = git(directory, "status", "--porcelain", "--", ".")
    if st.returncode != 0:
        raise Refusal("not a git checkout: " + st.stderr.strip())
    if st.stdout.strip():
        raise Refusal("study directory has uncommitted changes")
    head = git(directory, "rev-parse", "HEAD")
    if head.returncode != 0:
        raise Refusal("git rev-parse HEAD failed")
    return head.stdout.strip()


def verify_freeze_commit(directory, commit, expected_sha256):
    """The freeze commit is an ancestor of HEAD and its protocol.json hashes to the record."""
    anc = subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=directory, capture_output=True)
    if anc.returncode != 0:
        raise Refusal(f"freeze commit {commit} is not an ancestor of HEAD")
    shown = subprocess.run(["git", "show", f"{commit}:./protocol.json"], cwd=directory, capture_output=True)
    if shown.returncode != 0 or hashlib.sha256(shown.stdout).hexdigest() != expected_sha256:
        raise Refusal("protocol.json at the freeze commit does not match the freeze record")


def pin_paths(study_dir, data_root, repo_root):
    return {
        "code": {n: Path(study_dir) / n for n in CODE_PINS},
        "reference": {n: Path(repo_root) / rel for n, rel in REFERENCE_PINS.items()},
        "private_inputs": {n: Path(data_root) / n for n in PRIVATE_INPUTS},
    }


def compute_pins(study_dir, data_root, repo_root):
    return {g: {n: (sha256_file(p) if p.exists() else None) for n, p in d.items()}
            for g, d in pin_paths(study_dir, data_root, repo_root).items()}


def verify_pins(protocol, study_dir, data_root, repo_root):
    pins = protocol.get("pins") or {}
    for group, files in pin_paths(study_dir, data_root, repo_root).items():
        want = pins.get(group) or {}
        for name, path in files.items():
            if not _hex(want.get(name), 64):
                raise Refusal(f"pin missing: {group}/{name}")
            if not path.exists():
                raise Refusal(f"pinned file missing: {group}/{name}")
            if sha256_file(path) != want[name]:
                raise Refusal(f"pin mismatch: {group}/{name}")


# --------------------------------------------------------------------------------------
# Loaders: authorize()-issued token only; they read the pinned files under its data root
# --------------------------------------------------------------------------------------


def read_jsonl(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def load_events(auth):
    require(auth)
    return list(read_jsonl(auth.data_root / "events.jsonl.gz"))


def load_score_rows(auth):
    require(auth)
    rows = defaultdict(list)
    for rel in PRIVATE_INPUTS:
        if rel.startswith("scores/"):
            for row in read_jsonl(auth.data_root / rel):
                rows[row["event_id"]].append(row)
    return rows


def load_auction_prices(auth, events):
    """(symbol, session) -> official open / close by news_signal.select_auction_price."""
    require(auth)
    listing = {(ev["symbol"], ev["session"]): ev.get("exchange") for ev in events}
    opens, closes, seen = {}, {}, set()
    for row in read_jsonl(auth.data_root / "auctions" / "auctions.jsonl.gz"):
        key = (row["symbol"], row["session"])
        if key in seen:
            raise Refusal(f"duplicate auction row for {key}")
        seen.add(key)
        venue = listing.get(key)
        o = sig.select_auction_price(row["o"], "open", venue)
        c = sig.select_auction_price(row["c"], "close", venue)
        if o:
            opens[key] = o[0]
        if c:
            closes[key] = c[0]
    return opens, closes


def load_rth_quotes(auth, events):
    """event_id -> entry quote {bid, ask, t} (news_signal.rth_entry_quote), RTH events only."""
    require(auth)
    entries = {ev["event_id"]: ev["entry_utc"] for ev in events if ev["window"] == sig.RTH}
    out = {}
    for row in read_jsonl(auth.data_root / "spreads" / "quotes.jsonl"):
        eid = row["event_id"]
        if eid in entries and eid not in out:
            q = sig.rth_entry_quote(row.get("quotes"), entries[eid])
            if q is not None:
                out[eid] = q
    return out


# --------------------------------------------------------------------------------------
# Pure evaluation
# --------------------------------------------------------------------------------------


def check_scores(events, score_rows, protocol, pins):
    """Exactly one valid score row per confirmatory-lane event; returns event_id -> row.

    Refuses when a confirmatory (liquid) event has no row, when any event has more than
    one row, or when a used row disagrees with the event or the pinned scoring settings.
    Small-lane events without a row are left out (descriptive lane).
    """
    settings = protocol["scoring"]["pinned_settings"]
    confirmatory = set(protocol["confirmatory_lanes"])
    chosen, missing_small = {}, 0
    for ev in events:
        rows = score_rows.get(ev["event_id"], [])
        if len(rows) > 1:
            raise Refusal(f"{len(rows)} score rows for event {ev['event_id']}")
        if not rows:
            if ev["lane"] in confirmatory:
                raise Refusal(f"confirmatory event {ev['event_id']} is unscored")
            missing_small += 1
            continue
        row = rows[0]
        year = sig.checkpoint_year(ev["created_at"])
        entry = pins["checkpoints"].get(str(year), {})
        expected = {
            "checkpoint_year": year,
            "revision": entry.get("revision"),
            "weights_sha256": entry.get("files", {}).get("pytorch_model.bin", {}).get("sha256"),
            "code_sha256": pins["reviewed_code"]["sha256"],
            "variant": settings["variant"],
            "template_sha256": settings["template_sha256"],
            "dtype": settings["dtype"],
            "matmul": settings["matmul"],
            "decoder": settings["decoder"],
            "prompt_sha256": sig.sha256_text(sig.model_input(ev["company"], ev["headline"], settings["variant"])),
        }
        for key, value in expected.items():
            if row.get(key) != value:
                raise Refusal(f"score row {ev['event_id']} has {key}={row.get(key)!r}, expected {value!r}")
        label, score, _ = sig.parse_label(row["raw_output"], settings["variant"]) if row.get("stop") != "context_overflow" \
            else ("PARSE_FAIL", 0, False)
        if (row.get("label"), row.get("score")) != (label, score):
            raise Refusal(f"score row {ev['event_id']} label does not match its raw output")
        chosen[ev["event_id"]] = row
    return chosen, {"small_lane_unscored": missing_small}


def cost_fractions(ev, costs):
    exit_cost = costs["auction_slippage_bps_per_side"][ev["lane"]] / 1e4
    if ev["window"] == sig.RTH:
        return costs["rth_entry_allowance_bps"] / 1e4, exit_cost
    return costs["auction_slippage_bps_per_side"][ev["lane"]] / 1e4, exit_cost


SCORE_RULES = ("operative", "strict")


def position_side(row, rule):
    """(label, side) of a validated score row: the operative prefix rule (D22) or the
    model authors' strict rule (the stored label, kept as a descriptive sensitivity)."""
    if rule == "operative":
        label, side, _ = sig.operative_score(row.get("raw_output"), row.get("stop"))
        return label, side
    if rule == "strict":
        return row["label"], int(row["score"])
    raise ValueError(f"unknown score rule {rule!r}")


def build_positions(events, scores, opens, closes, rth_quotes, fees, costs, rule="operative"):
    """Positions (with gross/net returns and Rule 201 flags), benchmark rows, exclusions.

    Overnight: official open to official close. RTH: long at the entry quote's ask, short at
    its bid (news_signal.rth_entry_price), exit at the official close. Benchmark rows: every
    scored liquid overnight event held long open to close (NEWS-2B), whatever its label.
    rule selects how a row's raw output becomes a side (position_side).
    """
    positions, bench = [], []
    excluded = Counter()
    for ev in events:
        row = scores.get(ev["event_id"])
        if row is None:
            excluded["no_score"] += 1
            continue
        label, side = position_side(row, rule)
        key = (ev["symbol"], ev["session"])
        exit_price = closes.get(key)
        day = date.fromisoformat(ev["session"])
        entry_cost, exit_cost = cost_fractions(ev, costs)
        if ev["window"] == sig.OVERNIGHT and ev["lane"] == sig.LIQUID:
            o = opens.get(key)
            if o is not None and exit_price is not None:
                bench.append({"session": ev["session"],
                              "net": sig.position_net_return(1, o, exit_price, day, fees, costs["notional_usd"], entry_cost, exit_cost),
                              "gross": sig.gross_return(1, o, exit_price)})
        if side == 0:
            excluded[f"no_position_{label}"] += 1
            continue
        quote = rth_quotes.get(ev["event_id"]) if ev["window"] == sig.RTH else None
        if ev["window"] == sig.OVERNIGHT:
            entry_price = opens.get(key)
        else:
            entry_price = sig.rth_entry_price(quote, side)
        if entry_price is None:
            excluded[f"missing_entry_{ev['window']}"] += 1
            continue
        if exit_price is None:
            excluded[f"missing_exit_{ev['window']}"] += 1
            continue
        net = sig.position_net_return(side, entry_price, exit_price, day, fees, costs["notional_usd"], entry_cost, exit_cost)
        gross = sig.gross_return(side, entry_price, exit_price)
        ssr = side == -1 and sig.ssr_flag(ev, quote)
        positions.append({"event_id": ev["event_id"], "symbol": ev["symbol"], "session": ev["session"],
                          "window": ev["window"], "lane": ev["lane"], "side": side, "gross": gross, "net": net,
                          "cost": gross - net, "ssr": ssr})
        if ssr:
            excluded[f"ssr_short_{ev['window']}"] += 1
    return positions, bench, excluded


def daily_series(positions, window, lane, field, include_ssr=False):
    chosen = [{"session": p["session"], "side": p["side"], "ret": p[field]}
              for p in positions if p["window"] == window and p["lane"] == lane and (include_ssr or not p["ssr"])]
    return sig.daily_portfolios(chosen)


def bench_daily(bench, field):
    days = defaultdict(list)
    for b in bench:
        days[b["session"]].append(b[field])
    return {d: sum(v) / len(v) for d, v in days.items()}


def in_segment(session_iso, segment):
    return segment["first_session"] <= session_iso <= segment["last_session"]


def item_values(item, positions, bench, field, segment):
    """The daily series an item tests: long_short (both legs), long, or long_bench."""
    daily = daily_series(positions, item["window"], item["lane"], field)
    if item["series"] == "long_bench":
        b = bench_daily(bench, field)
        return [v["long"] - b[d] for d, v in sorted(daily.items())
                if in_segment(d, segment) and v["long"] is not None and d in b]
    return [v[item["series"]] for d, v in sorted(daily.items()) if in_segment(d, segment) and v[item["series"]] is not None]


def series_stats(values, lags):
    values = [v for v in values if v is not None]
    n = len(values)
    if n < 2:
        return {"n_days": n, "mean": values[0] if values else None, "t_nw": None, "p_one_sided": None,
                "upper_bound_95_one_sided": None}
    t, se = sig.newey_west_t(values, lags)
    mu = sum(values) / n
    sd = math.sqrt(sum((v - mu) ** 2 for v in values) / (n - 1))
    ok = not math.isnan(t)
    return {
        "n_days": n, "mean": mu, "sd": sd, "se_nw": se if ok else None, "t_nw": t if ok else None,
        "p_one_sided": sig.normal_sf(t) if ok else None,
        "upper_bound_95_one_sided": mu + Z95 * se if ok else None,
        "sharpe_annualized": (mu / sd * math.sqrt(252)) if sd > 0 else None,
        "hit_rate": sum(1 for v in values if v > 0) / n,
    }


def prior_reading(upper_bound):
    """Which prior effect sizes the one-sided 95% upper bound excludes."""
    if upper_bound is None:
        return None
    return {name: {"prior_per_day": x, "excluded_by_upper_bound": upper_bound < x} for name, x in PRIOR_BPS.items()}


def evaluate_items(protocol, positions, bench):
    """Items, multiplicity families, gates. Pure (tested on synthetic positions)."""
    lags = protocol["inference"]["newey_west_lags"]
    segments = protocol["segments"]
    mult = protocol["multiplicity"]
    results = {}
    for item in protocol["items"]:
        seg = segments[item["segment"]]
        net = series_stats(item_values(item, positions, bench, "net", seg), lags)
        gross = series_stats(item_values(item, positions, bench, "gross", seg), lags)
        net["sample_ok"] = net["n_days"] >= item["min_days"]
        results[item["id"]] = {
            "net": net, "gross": gross, "min_days": item["min_days"],
            "p": net["p_one_sided"] if net["sample_ok"] else None,
            "reading": {"net": prior_reading(net["upper_bound_95_one_sided"]),
                        "gross": prior_reading(gross["upper_bound_95_one_sided"])},
        }
    prim = mult["primary"]
    seq = sig.fixed_sequence([(k, results[k]["p"]) for k in prim["items"]], prim["alpha"])
    sec = mult["secondary"]
    member_p = {}
    for member, ids in sec["members"].items():
        ps = [results[i]["p"] for i in ids]
        # intersection-union member: rejected only if every item in it is (p = max)
        member_p[member] = None if any(p is None for p in ps) else max(ps)
    holm = sig.holm_reject(member_p, sec["alpha"])
    for member, ids in sec["members"].items():
        for i in ids:
            results[i]["secondary_member"] = member
            results[i]["secondary_member_p"] = member_p[member]
            results[i]["rejected_secondary_holm"] = holm[member]
    for k, r in results.items():
        r["rejected_primary_sequence"] = seq.get(k)
        rejected = bool(seq.get(k) or r.get("rejected_secondary_holm"))
        r["verdict"] = "insufficient_sample" if not r["net"]["sample_ok"] else ("rejected" if rejected else "not_rejected")
    recent = segments[protocol["gates"]["recent_segment"]]
    recent_long = item_values({"window": sig.OVERNIGHT, "lane": sig.LIQUID, "series": "long"}, positions, bench, "net", recent)
    recent_mean = sum(recent_long) / len(recent_long) if recent_long else None
    g = protocol["gates"]
    gates = {
        "long_only_paper_candidate": bool(holm[g["long_only_member"]] and recent_mean is not None and recent_mean > 0),
        "long_short_candidate": all(seq.get(k) for k in prim["items"]),
        "rth_candidate": bool(holm[g["rth_member"]]),
        "recent_long_leg_mean_net": recent_mean,
        "recent_long_leg_days": len(recent_long),
    }
    return results, gates


def attach_strict_sensitivity(items, items_strict, gates_strict):
    """Report the strict-rule (authors') version beside every operative item; never a gate."""
    for k, r in items.items():
        s = items_strict[k]
        r["strict_rule_sensitivity"] = {"net": s["net"], "gross": s["gross"], "p": s["p"], "verdict": s["verdict"]}
    return {"gates_if_strict_rule_descriptive_only": gates_strict}


def break_even(daily_gross, leg, segment):
    """Per-position round-trip cost that sets the mean of a gross leg series to zero."""
    num, legs, days = 0.0, 0, 0
    for d, v in daily_gross.items():
        if not in_segment(d, segment) or v[leg] is None:
            continue
        days += 1
        num += v[leg]
        legs += 2 if leg == "long_short" else 1
    return (num / days) / (legs / days) if days else None


def descriptive(protocol, positions, bench):
    """Legs, the paper's single-leg long-short, Rule 201 counts, break-evens, years, lanes."""
    lags = protocol["inference"]["newey_west_lags"]
    out = {}
    for window in (sig.OVERNIGHT, sig.RTH):
        for lane in (sig.LIQUID, sig.SMALL):
            chosen = [p for p in positions if p["window"] == window and p["lane"] == lane]
            if not chosen:
                continue
            net = daily_series(positions, window, lane, "net")
            gross = daily_series(positions, window, lane, "gross")
            with_ssr = daily_series(positions, window, lane, "net", include_ssr=True)
            block = {"positions": len(chosen), "ssr_shorts_excluded": sum(p["ssr"] for p in chosen),
                     "mean_cost_per_position": sum(p["cost"] for p in chosen) / len(chosen)}
            for seg_name, seg in protocol["segments"].items():
                if not isinstance(seg, dict):
                    continue
                days = [d for d in net if in_segment(d, seg)]
                block[seg_name] = {
                    **{f"{f}_{leg}": series_stats([s[d][leg] for d in days if d in s and s[d][leg] is not None], lags)
                       for f, s in (("net", net), ("gross", gross)) for leg in ("long", "short", "long_short", "long_short_paper")},
                    "net_long_short_including_ssr_shorts": series_stats(
                        [with_ssr[d]["long_short"] for d in with_ssr if in_segment(d, seg) and with_ssr[d]["long_short"] is not None], lags),
                    "single_leg_days": sum(1 for d in days if net[d]["single_leg"]),
                    "break_even_round_trip_long_short": break_even(gross, "long_short", seg),
                    "break_even_round_trip_long": break_even(gross, "long", seg),
                }
            block["by_year_net_long_short"] = {
                y: series_stats([v["long_short"] for d, v in net.items() if d[:4] == y and v["long_short"] is not None], lags)
                for y in sorted({d[:4] for d in net})}
            out[f"{window}:{lane}"] = block
    out["benchmark_days"] = len(bench_daily(bench, "net"))
    return out


# --------------------------------------------------------------------------------------
# Guarded run
# --------------------------------------------------------------------------------------


def authorize(a, study_dir=HERE, repo_root=REPO):
    """The full check chain; the only issuer of the Authorization the data pass needs."""
    record = Path(getattr(a, "freeze_record", None) or Path(study_dir) / "receipts" / "freeze-record.json")
    expected, commit = read_freeze_record(record)
    given = getattr(a, "protocol_sha256", None)
    if given and given.strip().lower() != expected:
        raise Refusal("--protocol-sha256 differs from the freeze record")
    frozen = guard(Path(study_dir) / "protocol.json", expected)
    verify_pins(frozen.protocol, study_dir, a.data_root, repo_root)
    head = git_clean_head(study_dir)
    verify_freeze_commit(study_dir, commit, expected)
    return Authorization(frozen, head, study_dir, a.data_root, repo_root, _RUN_TOKEN)


def run(a, study_dir=HERE, repo_root=REPO):
    auth = authorize(a, study_dir, repo_root)
    result = data_pass(auth)
    protocol = auth.frozen.protocol
    result.update(git_head=auth.head, protocol_sha256=auth.frozen.sha256, protocol_id=protocol["id"],
                  evidence_label="HIST", scope=protocol["scope"])
    return result


def data_pass(auth):
    protocol = require(auth).frozen.protocol
    pins = json.loads((auth.repo_root / REFERENCE_PINS["checkpoints.json"]).read_text())
    fees = json.loads((auth.repo_root / REFERENCE_PINS["fees-v3.json"]).read_text())
    events = load_events(auth)
    scores, score_notes = check_scores(events, load_score_rows(auth), protocol, pins)
    opens, closes = load_auction_prices(auth, events)
    quotes = load_rth_quotes(auth, events)
    positions, bench, excluded = build_positions(events, scores, opens, closes, quotes, fees, protocol["costs"], "operative")
    strict_positions, _, strict_excluded = build_positions(events, scores, opens, closes, quotes, fees, protocol["costs"], "strict")
    items, gates = evaluate_items(protocol, positions, bench)
    sensitivity = attach_strict_sensitivity(items, *evaluate_items(protocol, strict_positions, bench))
    return {
        "schema": "sota-news-llm-results/3",
        "score_rule": "operative (news_signal.operative_score, D22); strict_rule_sensitivity beside every item",
        "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "positions": len(positions),
        "strict_rule": {"positions": len(strict_positions), "excluded": dict(strict_excluded), **sensitivity},
        "excluded": dict(excluded),
        "score_checks": score_notes,
        "items": items,
        "gates": gates,
        "descriptive": descriptive(protocol, positions, bench),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-root", type=Path, default=PRIVATE_ROOT)
    parser.add_argument("--freeze-record", type=Path, default=FREEZE_RECORD_PATH)
    parser.add_argument("--protocol-sha256")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--print-pins", action="store_true")
    a = parser.parse_args(argv)
    if a.print_pins:
        print(json.dumps(compute_pins(HERE, a.data_root, REPO), indent=1, sort_keys=True))
        return 0
    try:
        result = run(a)
    except Refusal as r:
        print(f"REFUSED: {r.reason}", file=sys.stderr)
        return 2
    out = a.out or (Path(a.data_root) / "results.json")
    out.write_text(json.dumps(result, indent=1, sort_keys=True, default=str))
    print(json.dumps({"items": {k: v["verdict"] for k, v in result["items"].items()}, "gates": result["gates"],
                      "git_head": result["git_head"]}, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
