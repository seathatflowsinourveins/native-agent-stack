"""statistics, multiple_testing, minimum_sample, minimum_detectable_effect and outcome_reporting.

Bootstrap: circular session block bootstrap over the stage's kept sessions in date order. For each draw, start
indices come from Generator.integers(0, n, size=(rows, ceil(n / L))) in consecutive chunks of 10,000 rows; each
start i contributes sessions i, i+1, ..., i+L-1 (mod n), and the concatenation is cut to n sessions. The draw's
statistic is the trade-level mean over the drawn sessions' trades (H1-D: high mean minus low mean, sessions drawn
jointly). Review round 8, R8-11: the null side is closed (stat_b <= 0 for 'greater', >= 0 for 'less'), and a draw
with an empty group or cell has no statistic and counts as a null-side draw (for both sides of H3-c). Percentile
bounds and the normal-tail sd use the draws that have a statistic.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np

from core.params import ALTERNATIVE, BOOT, ITEM_IDS, MDE, MIN_SAMPLE, TEST, TRADABLE


# ---------------------------------------------------------------- seeded streams

def stage_children(protocol_id: str, stage: str):
    entropy = int.from_bytes(hashlib.sha256(protocol_id.encode("utf-8")).digest()[:8], "big")
    return np.random.SeedSequence(entropy=entropy, spawn_key=(BOOT["stage_index"][stage],)).spawn(len(ITEM_IDS))


def generator(protocol_id: str, stage: str, item_id: str) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(stage_children(protocol_id, stage)[ITEM_IDS.index(item_id)]))


# ---------------------------------------------------------------- per-session aggregates

def session_arrays(sessions: list, trades: list, group=None):
    """(sum, count) arrays aligned to sessions for trades {'session', 'value'[, 'group']}."""
    idx = {s: i for i, s in enumerate(sessions)}
    sums, cnts = np.zeros(len(sessions)), np.zeros(len(sessions))
    for tr in trades:
        if group is not None and tr.get("group") != group:
            continue
        i = idx.get(tr["session"])
        if i is None:
            raise ValueError(f"trade session {tr['session']} is not a kept session of the stage")
        sums[i] += tr["value"]
        cnts[i] += 1
    return sums, cnts


def _draw_indices(rng, n: int, L: int, rows: int):
    nb = math.ceil(n / L)
    starts = rng.integers(0, n, size=(rows, nb))
    idx = (starts[:, :, None] + np.arange(L)[None, None, :]) % n
    return idx.reshape(rows, nb * L)[:, :n]


def bootstrap(sessions: list, groups: list, rng, L: int, B: int | None = None, chunk: int | None = None):
    """B bootstrap statistics. groups is [(sums, cnts)] for a one-sample mean or [(high), (low)] for a
    difference; NaN marks a draw with an empty group."""
    B = BOOT["B"] if B is None else B
    chunk = BOOT["chunk_rows"] if chunk is None else chunk
    n = len(sessions)
    out = np.empty(B)
    done = 0
    while done < B:
        rows = min(chunk, B - done)
        idx = _draw_indices(rng, n, L, rows)
        means = []
        for sums, cnts in groups:
            s, c = sums[idx].sum(axis=1), cnts[idx].sum(axis=1)
            with np.errstate(invalid="ignore", divide="ignore"):
                means.append(np.where(c > 0, s / np.where(c > 0, c, 1), np.nan))
        out[done: done + rows] = means[0] if len(means) == 1 else means[0] - means[1]
        done += rows
    return out


# ---------------------------------------------------------------- p-values

def p_one_sided(stats, alternative: str) -> float:
    B = len(stats)
    undefined = np.isnan(stats)
    if alternative == "greater":
        null = undefined | (np.nan_to_num(stats, nan=0.0) <= 0.0)
    elif alternative == "less":
        null = undefined | (np.nan_to_num(stats, nan=0.0) >= 0.0)
    else:
        raise ValueError(alternative)
    return (1.0 + float(null.sum())) / (B + 1.0)


def p_value(stats, alternative: str) -> float:
    if alternative == "two-sided":
        return min(1.0, 2.0 * min(p_one_sided(stats, "greater"), p_one_sided(stats, "less")))
    return p_one_sided(stats, alternative)


def phi(z: float) -> float:
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def normal_tail_p(estimate: float, stats, alternative: str) -> float:
    defined = stats[~np.isnan(stats)]
    sd = float(np.std(defined, ddof=1)) if len(defined) > 1 else 0.0
    if sd == 0.0 or estimate is None:
        return 1.0
    z = estimate / sd
    if alternative == "greater":
        return 1.0 - phi(z)
    if alternative == "less":
        return phi(z)
    return min(1.0, 2.0 * min(phi(z), 1.0 - phi(z)))


def bound(stats, q: float):
    defined = stats[~np.isnan(stats)]
    return float(np.quantile(defined, q, method="linear")) if len(defined) else None


# ---------------------------------------------------------------- Holm

def holm(pvals: dict, normal_p: dict | None = None) -> dict:
    """Holm-adjusted p per item over the 5-item family (an item not carried or not tested has p = 1). Ties are
    broken by the normal-tail p, then by item id in bytewise ASCII order."""
    normal_p = normal_p or {}
    m = len(ITEM_IDS)
    if set(pvals) != set(ITEM_IDS):
        raise ValueError("the Holm family is exactly the 5 item_ids")
    order = sorted(ITEM_IDS, key=lambda i: (pvals[i], normal_p.get(i, 1.0), i.encode("ascii")))
    adj, running = {}, 0.0
    for rank, item in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[item]))
        adj[item] = running
    return adj


# ---------------------------------------------------------------- robustness

def winsorised_mean(values) -> float:
    x = np.asarray(values, dtype=float)
    lo, hi = np.quantile(x, TEST["winsor_quantiles"], method="linear")
    return float(np.clip(x, lo, hi).mean())


def mean_without_top_sessions(trades: list) -> float | None:
    """Drop the 5 entry sessions with the largest summed net return (ties: the earlier session first), then take
    the trade-level mean of the remaining trades."""
    sums = {}
    for tr in trades:
        sums[tr["session"]] = sums.get(tr["session"], 0.0) + tr["value"]
    drop = set(s for s, _ in sorted(sums.items(), key=lambda kv: (-kv[1], kv[0]))[: TEST["top_sessions_dropped"]])
    rest = [tr["value"] for tr in trades if tr["session"] not in drop]
    return float(np.mean(rest)) if rest else None


def mean_of_session_means(trades: list) -> float | None:
    by = {}
    for tr in trades:
        by.setdefault(tr["session"], []).append(tr["value"])
    return float(np.mean([np.mean(v) for v in by.values()])) if by else None


def robustness(trades: list) -> dict:
    vals = [tr["value"] for tr in trades]
    out = {"winsorised_mean": winsorised_mean(vals) if vals else None,
           "mean_without_top5_sessions": mean_without_top_sessions(trades),
           "mean_of_session_means": mean_of_session_means(trades)}
    out["all_positive"] = all(v is not None and v > 0 for v in out.values())
    return out


# ---------------------------------------------------------------- sample size and MDE

def minimum_met(item: str, stage: str, n: int, n_high: int | None = None, n_low: int | None = None) -> bool:
    """Review round 8, R8-8: n is the number of trades (events, for H3-c) that enter the statistic."""
    if item == "H1-D":
        m = MIN_SAMPLE["difference_test_per_group"][stage]
        return (n_high or 0) >= m and (n_low or 0) >= m
    return n >= MIN_SAMPLE["tradable_cell"][stage]


def mde(item: str, n: int | None = None, n1: int | None = None, n2: int | None = None) -> float | None:
    sigma, form = MDE["sigma_by_item"][item]
    z = MDE["z_sum_two_sided"] if item == "H3-c" else MDE["z_sum_one_sided"]
    if form == "difference":
        if not n1 or not n2:
            return None
        root = math.sqrt(1.0 / n1 + 1.0 / n2)
    else:
        if not n:
            return None
        root = math.sqrt(1.0 / n)
    return z * sigma * math.sqrt(MDE["design_effect_DEFF"]) * root


def mde_excluded(item: str, stats, mde_value) -> bool:
    if mde_value is None:
        return False
    alt = ALTERNATIVE[item]
    if alt == "two-sided":
        a = TEST["alpha"] / (2 * TEST["m"])
        lo, hi = bound(stats, a), bound(stats, 1.0 - a)
        return lo is not None and hi is not None and lo > -mde_value and hi < mde_value
    a = TEST["alpha"] / TEST["m"]
    if alt == "less":
        lo = bound(stats, a)
        return lo is not None and lo > -mde_value
    hi = bound(stats, 1.0 - a)
    return hi is not None and hi < mde_value


LINEAGE_LEVEL = TEST["alpha"] / TEST["lineage_trials"]


def lineage_confirmed(p_boot: float, p_norm: float) -> bool:
    return p_boot <= LINEAGE_LEVEL and p_norm <= LINEAGE_LEVEL


# ---------------------------------------------------------------- labels and verdicts

PASS_NAME = {"development": "development pass", "validation": "screened", "holdout": "supported (confirmatory)"}


def item_label(stage: str, item: str, *, p_stage: float, n_ok: bool, robust_ok: bool, mde_ok: bool,
               void: bool = False, sign_ok: bool = True, contaminated: bool = False, carried: bool = True) -> str:
    """outcome_reporting.labels: the stage pass name, 'not_supported_mde_excluded' or 'underpowered'.
    p_stage is the unadjusted p at development and the Holm-adjusted p at validation and the holdout. At the holdout
    an item that was not carried is 'not carried' whatever its sample (review round 9, M-1)."""
    if stage == "holdout" and not carried:
        return "not carried"
    if void or not n_ok:
        return "underpowered"
    # the robustness means are required for a tradable cell's validation and holdout pass, not at development
    passes = p_stage <= TEST["alpha"] and (robust_ok or item not in TRADABLE or stage == "development")
    if stage == "holdout" and item == "H3-c":
        passes = passes and sign_ok
    if passes:
        if stage == "holdout" and contaminated:
            return "screened (contaminated holdout)"
        return PASS_NAME[stage]
    if mde_ok:
        return "not_supported_mde_excluded"
    return "underpowered"


def qualifiers(stage: str, label: str, lineage_ok: bool, stage_qualifiers=()) -> list:
    """outcome_reporting.qualifiers attached to one item's label (review round 9, M-8): 'transport-deviation' for a
    stage fetched, collected or run under a transport deviation, and 'lineage-unconfirmed' for a 'supported
    (confirmatory)' item that is not lineage-confirmed (multiple_testing.lineage_sensitivity). Contamination is in
    the label itself ('screened (contaminated holdout)')."""
    out = list(stage_qualifiers)
    if stage == "holdout" and label == PASS_NAME["holdout"] and not lineage_ok:
        out.append("lineage-unconfirmed")
    return out


def hypothesis_verdict(stage: str, labels: dict, item_qualifiers: dict | None = None) -> dict:
    """outcome_reporting.hypothesis_verdict for H1 (H1-D, H1-D-b_lane-low) and H3 (H3-a, H3-b, H3-c). A pass
    verdict carries the qualifiers of its passing items."""
    out = {}
    item_qualifiers = item_qualifiers or {}
    groups = {"H1": ("H1-D", "H1-D-b_lane-low"), "H3": ("H3-a", "H3-b", "H3-c")}
    for h, items in groups.items():
        passing = [i for i in items if labels.get(i) == PASS_NAME[stage]]
        if passing:
            quals = sorted({q for i in passing for q in item_qualifiers.get(i, ())})
            out[h] = {"verdict": PASS_NAME[stage], "items": passing, "qualifiers": quals}
            continue
        if stage == "holdout":
            carried = [i for i in items if labels.get(i) not in (None, "not carried")]
            if carried and all(labels[i] == "not supported (holdout not read)" for i in carried):
                out[h] = {"verdict": "not supported (holdout not read)", "items": carried}
                continue
        if h == "H1":
            ns = labels.get("H1-D") == "not_supported_mde_excluded"
        else:
            ns = labels.get("H3-c") == "not_supported_mde_excluded"
        out[h] = {"verdict": "not supported" if ns else "inconclusive", "items": list(items)}
    return out


# ---------------------------------------------------------------- reported diagnostics (never gating)

def break_even_multiple(trades: list, fees, hi: float = 64.0, tol: float = 1e-6):
    """cost_model.break_even: the multiple k of the per-side costs (c_in, c_out) at which the cell's mean net return
    is 0; terminal-zero trades stay at -1. None if the mean is not positive at k = 0; hi if still positive at hi."""
    from core.costs import trade_net_return

    def mean_at(k):
        vals = []
        for tr in trades:
            p = tr.get("primary_parts")
            if p is None:
                vals.append(tr["nets"]["primary"])
            else:
                n, e, x, F, cash, c_in, c_out, day = p
                vals.append(trade_net_return(n, e, x, F, cash, k * c_in, k * c_out, fees, day))
        return float(np.mean(vals)) if vals else None

    m0 = mean_at(0.0)
    if m0 is None or m0 <= 0.0:
        return None
    if mean_at(hi) > 0.0:
        return hi
    lo, up = 0.0, hi
    while up - lo > tol:
        mid = (lo + up) / 2.0
        if mean_at(mid) > 0.0:
            lo = mid
        else:
            up = mid
    return (lo + up) / 2.0


def two_way_cluster(values, sessions, symbols) -> dict:
    """The sensitivity 'two-way (session, symbol) clustering': the mean with a Cameron-Gelbach-Miller two-way
    cluster-robust standard error, V = V_session + V_symbol - V_session x symbol (floored at the larger one-way V)."""
    x = np.asarray(values, dtype=float)
    n = len(x)
    if n < 2:
        return {"mean": float(x.mean()) if n else None, "se": None}
    u = x - x.mean()

    def v(keys):
        sums = {}
        for k, e in zip(keys, u):
            sums[k] = sums.get(k, 0.0) + e
        return sum(s * s for s in sums.values()) / (n * n)
    vs, vy, vb = v(sessions), v(symbols), v(list(zip(sessions, symbols)))
    var = max(vs + vy - vb, vs, vy)
    return {"mean": float(x.mean()), "se": math.sqrt(var)}


def benjamini_hochberg(pvals: dict, q: float = 0.10) -> dict:
    """tests_not_in_family: BH at q over the diagnostic splits; reported only, it can never open the holdout."""
    items = sorted(pvals.items(), key=lambda kv: (kv[1], kv[0]))
    m = len(items)
    cut = 0
    for i, (_, p) in enumerate(items, start=1):
        if p <= q * i / m:
            cut = i
    return {k: (i < cut) for i, (k, _) in enumerate(items)}


def split_p(values, alternative: str) -> float:
    """A diagnostic split's p: the normal approximation of its trade-level mean (mean / (sd / sqrt(n)))."""
    x = np.asarray(values, dtype=float)
    if len(x) < 2 or float(np.std(x, ddof=1)) == 0.0:
        return 1.0
    z = float(x.mean()) / (float(np.std(x, ddof=1)) / math.sqrt(len(x)))
    if alternative == "greater":
        return 1.0 - phi(z)
    if alternative == "less":
        return phi(z)
    return min(1.0, 2.0 * min(phi(z), 1.0 - phi(z)))
