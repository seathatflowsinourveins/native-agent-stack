"""Evidence-gated auto-leverage for the news-forward runner (pure, standard library only).

Daily decision, logged with every input:

  1. Input: the strategy's daily net returns on gross notional, from counted sessions
     only (rows whose evidence label is not ``pilot``).
  2. Shrunk mean  mu = n * xbar / (n + 60)   (a 60-session prior centred on 0);
     sigma: EWMA standard deviation with a 20-session half-life (deviations from xbar,
     weights 0.5 ** (age / 20), age 0 = the latest session).
  3. Fractional Kelly  L_k = 0.25 * mu / sigma**2.
  4. Evidence gate: n >= 20 sessions, round trips >= 100 and the one-sided 95% lower
     bound of the mean, xbar - 1.645 * s / sqrt(n) with the sample standard deviation s,
     above 0. Only then may L exceed the floor: L = max(1.0, L_k).
  5. Otherwise L = L_floor = 1.0 (the paper evidence-gathering floor).
  6. Cap: L <= the adaptive-paper leverage.py ceiling (session schedule, overnight Reg T
     cap, drawdown ladder, kill switch, account multiplier).

Regime mapping (leverage.py needs a regime; this strategy has no regime model): the
policy's regime-independent ``envelope()`` is used, the bound leverage.py itself
defines for a caller without a regime input (safety.py's ledger). It still applies
the session cell maximum (RTH 4, PRE/POST 1, CLOSED 0), the overnight cap and the
drawdown ladder; the kill switch (0) and the account multiplier are applied on top
exactly as ``ceiling()`` applies them. Using "unavailable" would map every session to
0 (no trading at all), which leverage.py reserves for a failed regime model.
"""

import math
import os
from decimal import Decimal

import common

leverage = common.load_by_path(
    "adaptive_paper_leverage", os.path.join(common.REPO, "blueprints/us-equities/adaptive-paper/leverage.py"))

L_FLOOR = Decimal("1.0")
PRIOR_SESSIONS = 60
EWMA_HALFLIFE = 20
KELLY_FRACTION = 0.25
MIN_SESSIONS = 20
MIN_ROUND_TRIPS = 100
Z_95_ONE_SIDED = 1.645


def counted(rows):
    """Daily rows that count as evidence, one per session in session order (M8).

    The last row written for a session wins (a restart can reconcile twice); rows labelled
    pilot and days whose core arm was not flat at the reconciliation are excluded.
    """
    by_session = {}
    for r in rows:
        by_session[r["session"]] = r
    return [r for _, r in sorted(by_session.items())
            if r.get("evidence_label") != "pilot" and r.get("core_flat", False) is True]


def shrunk_mean(xs):
    n = len(xs)
    return 0.0 if n == 0 else n * (sum(xs) / n) / (n + PRIOR_SESSIONS)


def ewma_sigma(xs, halflife=EWMA_HALFLIFE):
    """EWMA standard deviation (deviations from the sample mean; latest weight 1)."""
    n = len(xs)
    if n < 2:
        return None
    mean = sum(xs) / n
    weights = [0.5 ** ((n - 1 - i) / halflife) for i in range(n)]
    var = sum(w * (x - mean) ** 2 for w, x in zip(weights, xs)) / sum(weights)
    return math.sqrt(var) if var > 0 else None


def lower_bound_95(xs):
    n = len(xs)
    if n < 2:
        return None
    mean = sum(xs) / n
    s = math.sqrt(sum((x - mean) ** 2 for x in xs) / (n - 1))
    return mean - Z_95_ONE_SIDED * s / math.sqrt(n)


def kelly_leverage(rows):
    """(L_autolev, inputs) before the leverage.py cap."""
    rows = counted(rows)
    xs = [float(r["net_return_on_gross"]) for r in rows]
    trips = sum(int(r.get("round_trips", 0)) for r in rows)
    n = len(xs)
    mu = shrunk_mean(xs)
    sigma = ewma_sigma(xs)
    lb = lower_bound_95(xs)
    lk = KELLY_FRACTION * mu / sigma ** 2 if sigma else None
    gate = {"n_ge_20": n >= MIN_SESSIONS, "round_trips_ge_100": trips >= MIN_ROUND_TRIPS,
            "lower_bound_95_gt_0": lb is not None and lb > 0}
    passed = all(gate.values()) and lk is not None
    level = max(L_FLOOR, Decimal(str(round(lk, 6)))) if passed else L_FLOOR
    return level, {"n_sessions": n, "round_trips": trips, "mean": (sum(xs) / n) if n else None,
                   "shrunk_mean": mu, "ewma_sigma": sigma, "lower_bound_95": lb, "kelly_quarter": lk,
                   "gate": gate, "gate_passed": passed, "l_autolev": str(level)}


def _config(capital, overnight):
    """A config leverage.validate_leverage_policy accepts, carrying the canonical block."""
    cap = Decimal(str(capital))
    gross = cap * (leverage.OVERNIGHT_MAX if overnight else leverage.INTRADAY_MAX)
    return ({"max_leverage": str(leverage.INTRADAY_MAX), "capital_usd": str(cap.quantize(Decimal("0.01"))),
             "max_gross_exposure_usd": str(gross.quantize(Decimal("0.01"))), "leverage_policy": dict(leverage.CANONICAL_V1_BLOCK)},
            {"overnight_holds": overnight, "overnight_gross_multiple": 1})


def policy_ceiling(*, equity, session, drawdown_fraction, kill_switch, account_multiplier, overnight):
    """leverage.py cap for a regime-less caller (see the module docstring)."""
    config, session_policy = _config(equity, overnight)
    policy = leverage.validate_leverage_policy(config, session_policy)
    if kill_switch:
        return Decimal("0")
    c = policy.envelope(session=session, drawdown_fraction=Decimal(str(drawdown_fraction)))
    if account_multiplier is not None:
        c = min(c, Decimal(str(account_multiplier)))
    return max(c, Decimal("0"))


def decide(rows, *, equity, session, drawdown_fraction, kill_switch, account_multiplier, overnight=False):
    """The day's L = min(L_autolev, leverage.py cap), with every input for the journal."""
    level, inputs = kelly_leverage(rows)
    cap = policy_ceiling(equity=equity, session=session, drawdown_fraction=drawdown_fraction,
                         kill_switch=kill_switch, account_multiplier=account_multiplier, overnight=overnight)
    final = min(level, cap)
    return final, {**inputs, "policy_version": leverage.LEVERAGE_POLICY_VERSION, "session": session,
                   "overnight": overnight, "drawdown_fraction": str(drawdown_fraction), "kill_switch": kill_switch,
                   "account_multiplier": None if account_multiplier is None else str(account_multiplier),
                   "policy_cap": str(cap), "l_final": str(final), "equity": str(equity)}


def drawdown_fraction(peak_equity, equity):
    peak, eq = Decimal(str(peak_equity)), Decimal(str(equity))
    if peak <= 0:
        return Decimal("0")
    return max(Decimal("0"), (peak - eq) / peak)
