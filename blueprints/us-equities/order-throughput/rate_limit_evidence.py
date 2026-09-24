"""Rebuild or check rate-limit-evidence-20260924.json from committed trial receipts.

The header counts are measured from repository files (retained adaptive-paper
paper-trial outputs); the source statements are recorded as cited, and the
round-trip figures are arithmetic. Nothing here contacts a network service.

  python3 rate_limit_evidence.py --check   # exit 1 when the JSON is stale
  python3 rate_limit_evidence.py --write
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "rate-limit-evidence-20260924.json"
TRIALS = "blueprints/us-equities/adaptive-paper/trials"
UNATTRIBUTED = ("blueprints/us-equities/broad-universe/receipt.json",
                "blueprints/us-equities/broad-universe/watchlist-20260921.json")
ORIGIN = {"read": "trading", "submit": "trading", "cancel": "trading", "data_read": "data"}

SOURCES = [
    {"url": "https://alpaca.markets/support/usage-limit-api-calls",
     "stated_limit": "Trading API calls are throttled per account; default 200 calls per minute.",
     "applies_to": "trading API, per account"},
    {"url": "https://alpaca.markets/support/increase-api-rate-limit",
     "stated_limit": "Alpaca Support offers 1000 calls per minute for non-retail accounts at $0.004 per share.",
     "applies_to": "non-retail accounts, by request to Alpaca Support"},
    {"url": "https://alpaca.markets/elite",
     "stated_limit": "Alpaca Elite advertises 1000 API calls per minute.",
     "applies_to": "Elite program accounts"},
    {"url": "https://docs.alpaca.markets/docs/paper-trading",
     "stated_limit": None,
     "applies_to": "paper trading environment (cited for the paper endpoint; no limit figure was quoted from it)"},
]


def _walk_http(node, found):
    if isinstance(node, dict):
        headers = node.get("headers")
        if isinstance(headers, dict) and "x-ratelimit-limit" in headers:
            found.append((node.get("kind"), str(headers["x-ratelimit-limit"]),
                          headers.get("x-ratelimit-remaining")))
        for value in node.values():
            _walk_http(value, found)
    elif isinstance(node, list):
        for value in node:
            _walk_http(value, found)


def _walk_any(node, found):
    if isinstance(node, dict):
        if "x-ratelimit-limit" in node:
            found.append(str(node["x-ratelimit-limit"]))
        for value in node.values():
            _walk_any(value, found)
    elif isinstance(node, list):
        for value in node:
            _walk_any(value, found)


def observations(root=ROOT):
    files, totals = [], Counter()
    for path in sorted((root / TRIALS).rglob("*.json")):
        found = []
        _walk_http(json.loads(path.read_text()), found)
        if not found:
            continue
        counts = Counter("%s:%s" % (ORIGIN.get(kind, "unknown"), limit) for kind, limit, _ in found)
        by_kind = Counter("%s:%s" % (kind, limit) for kind, limit, _ in found)
        remaining = [int(r) for kind, _, r in found if ORIGIN.get(kind) == "trading" and str(r).isdigit()]
        files.append({"path": path.relative_to(root).as_posix(),
                      "counts_by_origin_and_limit": dict(sorted(counts.items())),
                      "counts_by_request_kind_and_limit": dict(sorted(by_kind.items())),
                      "min_trading_remaining": min(remaining) if remaining else None})
        totals.update(counts)
    unattributed = []
    for relative in UNATTRIBUTED:
        found = []
        _walk_any(json.loads((root / relative).read_text()), found)
        unattributed.append({"path": relative, "limits": dict(Counter(found)),
                             "note": "rate_headers_last of a session that used both trading and data hosts; "
                                     "origin not recorded, so excluded from origin totals"})
    return files, dict(sorted(totals.items())), unattributed


def arithmetic():
    rows = []
    for limit in (200, 1000):
        budget = int(limit * 0.9)
        rows.append({
            "calls_per_minute_limit": limit,
            "harness_budget_at_headroom_0_9": budget,
            "submit_cancel_pairs_per_minute_max": limit // 2,
            "submit_cancel_pairs_per_minute_at_budget": budget // 2,
            "order_actions_per_minute_at_budget": budget,
            "round_trips_per_minute_two_submits": limit // 2,
            "round_trips_per_minute_one_submit_native_bracket_exit": limit,
        })
    return {
        "class": "arithmetic (not measured)",
        "rules": [
            "Every REST submit, cancel and read is one call against the per-account trading limit.",
            "A non-marketable probe that is cancelled individually costs 2 calls (POST /v2/orders + DELETE /v2/orders/{id}).",
            "A buy+sell round trip costs at least 2 submits (2 calls), plus a cancel/replace for every unfilled leg.",
            "Only a native bracket/OCO/OTO exit leg that closes the position without a further call reduces a round trip to 1 submit; "
            "any cancel of the unfilled sibling leg, reconciliation read or retry adds calls.",
            "Order state from the trade_updates websocket costs no REST calls; polling would.",
        ],
        "by_limit": rows,
        "conclusions": [
            "At 200 calls/min the ceiling is 200 order actions/min: at most 100 submit+cancel pairs, or 100 two-submit round trips.",
            "At 1000 calls/min the ceiling is 1000 order actions/min: at most 500 submit+cancel pairs, or 500 two-submit round trips.",
            "1000 round trips/min needs at least 2000 calls/min with two submits per round trip, and more than 1000 calls/min "
            "even with a native exit leg once any cancel, read or retry is included; 1000 calls/min cannot carry it.",
            "The harness acceptance target counts order actions (submits + cancels), so 170 actions/min at a 200 limit "
            "is about 85 submits/min; 170 submits/min with individual cancels would need about 340 calls/min.",
            "Illustrative cost at the quoted non-retail rate (live accounts only; paper has no commission): "
            "1000 one-share round trips/min = 2000 shares/min x $0.004 = $8.00/min.",
        ],
    }


def build(root=ROOT):
    files, totals, unattributed = observations(root)
    return {
        "schema_version": 1,
        "recorded": "2026-09-24",
        "scope": "Alpaca request-rate limits relevant to paper execution-capacity runs at ~200 and ~1000 order actions/min",
        "sources": {"class": "cited statements (not fetched or re-verified in this change; no network access was used)",
                    "items": SOURCES},
        "repository_observations": {
            "class": "measured from committed files (headers recorded by adaptive-paper's GuardedSession observer)",
            "command": "python3 blueprints/us-equities/order-throughput/rate_limit_evidence.py --check",
            "totals_by_origin_and_limit": totals,
            "files": files,
            "unattributed": unattributed,
            "interpretation": ["trading origin (paper-api.alpaca.markets reads, submits, cancels) reported x-ratelimit-limit 200",
                               "data origin (data.alpaca.markets latest-quote read) reported x-ratelimit-limit 10000; "
                               "it is a separate limit and must not size the trading budget"]},
        "round_trip_arithmetic": arithmetic(),
        "unknowns": ["Whether a paper account's trading limit rises with Elite or a Support-granted increase is not observed; "
                     "the harness adopts whatever x-ratelimit-limit the paper endpoint reports, bounded by --cap.",
                     "Alpaca's window semantics (fixed vs rolling) are not documented here; the harness keeps a rolling "
                     "60 s count under budget and also honours x-ratelimit-remaining/reset."],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    text = json.dumps(build(), indent=2, sort_keys=False) + "\n"
    if args.write:
        OUTPUT.write_text(text)
        print(json.dumps({"status": "written", "path": OUTPUT.name}))
        return 0
    current = OUTPUT.read_text() if OUTPUT.exists() else ""
    status = "passed" if current == text else "stale"
    print(json.dumps({"status": status, "path": OUTPUT.name}))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
