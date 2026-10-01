"""coverage_rule.decided_by_code: the count-only code applies year_rule and item_rule itself, with the thresholds
read from the hashed coverage_rule object (review round 8, R8-9: every freeze-deciding threshold is in that
object), and refuses to run if the protocol's coverage_rule hashes differently from COVERAGE_RULE_SHA256.
"""
from __future__ import annotations

from core.canon import sha256_obj
from core.params import COVERAGE_RULE_SHA256


class CoverageRuleChanged(Exception):
    pass


def rule_sha256(protocol: dict) -> str:
    return sha256_obj(protocol["coverage_rule"])


def checked_thresholds(protocol: dict) -> dict:
    if rule_sha256(protocol) != COVERAGE_RULE_SHA256:
        raise CoverageRuleChanged("coverage_rule differs from the object this count-only code was committed with")
    return protocol["coverage_rule"]["thresholds"]


def year_decision(rates: dict, th: dict) -> dict:
    """rates: official_close_rate, eligible_quote_rate, identity_unreached_rate, minute_bar_rate (None if the
    denominator is 0, which drops the year: nothing measured is not coverage)."""
    reasons = []
    checks = (("official_close_rate", "official_close_rate_min", "below"),
              ("eligible_quote_rate", "eligible_quote_rate_min", "below"),
              ("identity_unreached_rate", "identity_unreached_rate_max", "above"),
              ("minute_bar_rate", "minute_bar_rate_min", "below"))
    for key, tkey, side in checks:
        v = rates.get(key)
        if v is None:
            reasons.append(f"{key}: not measured")
        elif side == "below" and v < th[tkey]:
            reasons.append(f"{key} {v:.6f} < {th[tkey]}")
        elif side == "above" and v > th[tkey]:
            reasons.append(f"{key} {v:.6f} > {th[tkey]}")
    return {"kept": not reasons, "reasons": reasons}


def item_rule(decisions: dict) -> dict:
    """If 2020 is dropped, no item is tested (p = 1 at validation and the holdout, permanently)."""
    tested = decisions.get(2020, {}).get("kept", False)
    dev_kept = [y for y in (2017, 2018, 2019) if decisions.get(y, {}).get("kept")]
    return {"items_tested": tested, "H1": "data in hand, tested" if tested else "not tested, p = 1 at every stage, permanently",
            "H3": "data in hand, tested" if tested else "not tested, p = 1 at every stage, permanently",
            "development_computed": bool(dev_kept),
            "dropped_years": sorted(y for y, d in decisions.items() if not d["kept"])}


def identity_limited(rate_2020, th: dict) -> bool:
    return rate_2020 is None or rate_2020 > th["identity_limited_validation_rate"]


def probe_decision(probe: dict, th: dict) -> dict:
    """The identity-probe freeze decision (coverage_rule.thresholds.identity_probe). Review round 15, N07: an observed
    ticker-reuse failure (a case whose late asof returned the old issuer's identical bar, count_only.probe_counts)
    fails the gate once the failed cases exceed ticker_reuse_failed_cases_max (0); at e7529b47 'failed' was only
    reported and passes depended on the rename rates alone. Zero-case policy: with no conclusive reuse case (none
    listed, or every case inconclusive: a fetch-incomplete request or no bar of the old issuer) ticker reuse is
    'unverified for 2016-2020', which does not fail the gate and is recorded with the count-only output."""
    p = th["identity_probe"]
    n = probe["rename_probes"]
    rate = lambda k: (probe[f"{k}_match"] / n) if n else None  # noqa: E731
    failed, verified = probe.get("reuse_failed", 0), probe.get("reuse_differ", 0)
    reuse = "failed" if failed else ("verified" if verified else "unverified for 2016-2020")
    ok = (n >= p["min_rename_probes"] and rate("bars") is not None and rate("bars") >= p["bars_match_min"]
          and rate("auctions") >= p["auctions_match_min"] and rate("quotes") >= p["quotes_match_min"]
          and failed <= p["ticker_reuse_failed_cases_max"])
    return {"passes": bool(ok), "rename_probes": n, "bars_rate": rate("bars"), "auctions_rate": rate("auctions"),
            "quotes_rate": rate("quotes"), "ticker_reuse": reuse,
            "reuse_cases": {"listed": probe.get("reuse_cases", 0), "verified": verified, "failed": failed,
                            "inconclusive": probe.get("reuse_inconclusive", 0)}}


def fetch_margin(estimate_seconds: float, th: dict) -> dict:
    """The fetch-time estimate must leave at least the margin under the 40 sessions before N0, counted as
    available_seconds (40 x 86,400 s, which ignores weekends and holidays and so understates the time)."""
    avail = th["fetch_estimate"]["available_seconds"]
    return {"estimate_seconds": estimate_seconds, "available_seconds": avail,
            "passes": estimate_seconds <= (1.0 - th["fetch_margin_min"]) * avail}
