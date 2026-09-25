#!/usr/bin/env python3
"""Guarded group-sequential analysis of the preregistered rth_reversal forward paper test.

  python analyze.py design [--harm-simulation] [--out PATH]  # boundaries, error rates, power (and the drawdown
                                                             # trigger simulation); no data
  python analyze.py pins                           # sha256 of every file forward-protocol.json#/pins names
  python analyze.py look [--state ROOT]            # the next due look (receipts/look-<k>.json); guarded
  python analyze.py monitor [--state ROOT] [--apply]   # harm stops only; --apply writes <state>/HALT-rth_reversal
  python analyze.py resume --finding F --note N --after-session D   # the pre-stated resume after a harm halt

look, monitor and resume refuse (exit 2) before they open any journal unless all of these hold (the
standard of ../news-llm/evaluate.py):
* receipts/freeze-record.json names the sha256 of forward-protocol.json and the full commit
  that froze it (--protocol-sha256, when given, must equal the record);
* forward-protocol.json hashes to that sha256, has status 'frozen_pre_outcome',
  frozen_before_outcomes true and frozen_at set;
* the freeze commit is an ancestor of HEAD and forward-protocol.json at that commit hashes
  to the recorded sha256;
* receipts/deployment-record.json names deployed_at and a full deployed_commit that
  descends from the freeze commit;
* every pin in forward-protocol.json#/pins matches the files at HEAD (runner, study and
  analysis code, reference data);
* ``git status --porcelain`` is empty for this directory; HEAD is recorded.
Only authorize() runs that chain and issues the Authorization every loader requires.

Counted sessions (protocol counted_sessions): XNYS sessions from the first one whose open is
after both frozen_at and deployed_at. Journals of earlier sessions (pilot and pre-freeze
shakedown days) are never opened. A later session counts only when every start record of the
day (restarts included) shows paper mode on the dedicated paper-4 account, the rth_reversal arm
active, the reversal run label, the frozen protocol's sha256 and the pinned runner and study
code; otherwise it is excluded with its reason and nothing is computed from it except the exit
fills of earlier counted positions. Boundaries follow the Lan-DeMets O'Brien-Fleming spending
function at the actual information, with a final look at the protocol's calendar end date.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
import random
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
NEWS_LLM = HERE.parent / "news-llm"
NEWS_FORWARD = HERE.parent / "news-forward"


def load_news_signal():
    spec = importlib.util.spec_from_file_location("news_signal", NEWS_LLM / "news_signal.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["news_signal"] = module
    spec.loader.exec_module(module)
    return module


sig = load_news_signal()

PROTOCOL_PATH = HERE / "forward-protocol.json"
FREEZE_RECORD_PATH = HERE / "receipts" / "freeze-record.json"
DEPLOYMENT_RECORD_PATH = HERE / "receipts" / "deployment-record.json"
FROZEN_STATUS = "frozen_pre_outcome"
DEFAULT_STATE = Path(os.path.expanduser("~/.local/state/native-agent-stack/research/sota-mover/news-forward"))
RUNNER_CODE = ("autolev.py", "common.py", "executor.py", "live_news.py", "live_score.py", "planner.py", "shadow.py",
               "supervisor.py")
STUDY_CODE = ("news_signal.py", "score.py")
ANALYSIS_CODE = ("analyze.py", "measure_s.py")
REFERENCE = {
    "fees-v3.json": "blueprints/us-equities/mover-v3/data/fees-v3.json",
    "session-calendar.json": "blueprints/us-equities/mover-v3/data/session-calendar.json",
    "checkpoints.json": "blueprints/us-equities/sota-mover/news-llm/checkpoints.json",
}
REV_ARM, REV_PREFIX = "rev", "nf1r-"
RUN_LABEL = "reversal_forward"  # common.REVERSAL_RUN_LABEL of the runner
RUNTIME_ACCOUNT = "paper-4"  # forward-protocol.json#/runtime: the dedicated, rev-only account
HALT_FILE = "HALT-rth_reversal"
Z95 = 1.6448536269514722
Z80 = 0.8416212335729143
_TOKEN = object()
_RUN_TOKEN = object()


class Refusal(SystemExit):
    def __init__(self, reason):
        super().__init__(2)
        self.reason = reason

    def __str__(self):
        return f"refusing: {self.reason}"


# --------------------------------------------------------------------------------------
# Group-sequential numerics (Jennison & Turnbull 2000, ch. 19: grid and recursive integration)
# --------------------------------------------------------------------------------------


def norm_cdf(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def norm_ppf(p):
    """Inverse standard normal cdf by bisection on erfc (|error| < 1e-12; enough for design numbers)."""
    if not 0.0 < p < 1.0:
        raise ValueError("p must lie in (0, 1)")
    lo, hi = -40.0, 40.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def grid(m, mu, a, b):
    """Points and Simpson weights for a normal density centred at mu, restricted to [a, b]
    (Jennison & Turnbull 2000, section 19.2.1; a = -inf and b = +inf allowed)."""
    x = []
    for i in range(1, 6 * m):
        if i < m:
            x.append(mu - 3.0 - 4.0 * math.log(m / i))
        elif i <= 5 * m:
            x.append(mu - 3.0 + 3.0 * (i - m) / (2.0 * m))
        else:
            x.append(mu + 3.0 + 4.0 * math.log(m / (6 * m - i)))
    lo = max(a, x[0])
    hi = min(b, x[-1])
    if hi <= lo:
        return [], []
    odd = [lo] + [v for v in x if lo < v < hi] + [hi]
    z, w = [], []
    for i, v in enumerate(odd):
        z.append(v)
        left = (v - odd[i - 1]) / 6.0 if i > 0 else 0.0
        right = (odd[i + 1] - v) / 6.0 if i + 1 < len(odd) else 0.0
        w.append(left + right)
        if i + 1 < len(odd):
            z.append((v + odd[i + 1]) / 2.0)
            w.append(4.0 * (odd[i + 1] - v) / 6.0)
    return z, w


def crossing_probs(fractions, upper, lower=None, theta=0.0, m=32):
    """Per-look probabilities of stopping above `upper` or below `lower` (Z scale).

    fractions: information fractions t_1 < ... < t_K = 1; Z_k ~ N(theta sqrt(t_k), 1) with
    the canonical joint distribution (independent increments). lower: None or a list with
    -inf where there is no lower (futility) bound; the final look's lower bound is ignored
    (the procedure stops there anyway). Returns (p_upper[k], p_lower[k]).
    """
    k_n = len(fractions)
    lower = lower or [-math.inf] * k_n
    p_up, p_lo = [], []
    prev = None  # (z, w * density) on the continuation region of the previous look
    for k in range(k_n):
        t = fractions[k]
        mu = theta * math.sqrt(t)
        b = upper[k]
        a = lower[k] if k < k_n - 1 else -math.inf
        if prev is None:
            p_up.append(1.0 - norm_cdf(b - mu))
            p_lo.append(norm_cdf(a - mu) if a > -math.inf else 0.0)
            z, w = grid(m, mu, a, b)
            prev = (z, [wi * norm_pdf(zi - mu) for zi, wi in zip(z, w)])
            continue
        t_prev = fractions[k - 1]
        delta = t - t_prev
        sd = math.sqrt(delta)
        inv = 1.0 / sd
        zs, hs = prev
        drift = theta * delta
        root_t, root_prev = math.sqrt(t), math.sqrt(t_prev)
        bases = [zj * root_prev + drift for zj in zs]  # mean of S_k given Z_{k-1} = z_j
        up = lo = 0.0
        for base, hj in zip(bases, hs):
            up += hj * (1.0 - norm_cdf((b * root_t - base) * inv))
            if a > -math.inf:
                lo += hj * norm_cdf((a * root_t - base) * inv)
        p_up.append(up)
        p_lo.append(lo)
        if k == k_n - 1:
            break
        z, w = grid(m, mu, a, b)
        dens = []
        exp = math.exp
        scale = root_t * inv / math.sqrt(2.0 * math.pi)
        pairs = list(zip(bases, hs))
        for zi, wi in zip(z, w):
            target = zi * root_t
            s = 0.0
            for base, hj in pairs:
                x = (target - base) * inv
                s += hj * exp(-0.5 * x * x)
            dens.append(wi * s * scale)
        prev = (z, dens)
    return p_up, p_lo


def obf_boundaries(fractions, alpha, m=32, tol=1e-7):
    """O'Brien-Fleming efficacy boundaries c_k = C / sqrt(t_k) with the one-sided upper-crossing
    probability under H0 equal to alpha (no futility bound: a non-binding futility rule leaves
    the type I error at or below alpha)."""
    def excess(c):
        up, _ = crossing_probs(fractions, [c / math.sqrt(t) for t in fractions], None, 0.0, m)
        return sum(up) - alpha

    lo, hi = norm_ppf(1.0 - alpha), norm_ppf(1.0 - alpha) + 1.0  # C is at least the fixed-sample critical value
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if excess(mid) > 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    c = (lo + hi) / 2.0
    return c, [c / math.sqrt(t) for t in fractions]


def ld_obf_spending(t, alpha):
    """Lan-DeMets O'Brien-Fleming-type alpha spending (one-sided): alpha(t) = 2 - 2 Phi(z_{1-alpha/2} / sqrt(t)),
    0 at t = 0 and alpha at t >= 1 (Lan & DeMets 1983)."""
    if t <= 0:
        return 0.0
    if t >= 1:
        return alpha
    return 2.0 * (1.0 - norm_cdf(norm_ppf(1.0 - alpha / 2.0) / math.sqrt(t)))


def ld_boundaries(fractions, alpha, m=32, final=False, tol=1e-9):
    """Efficacy boundaries (Z) for looks at information `fractions`, spending ld_obf_spending cumulatively:
    c_k solves P(no earlier crossing, Z_k >= c_k) = alpha(t_k) - alpha(t_{k-1}) given the earlier c's (no
    futility bound: non-binding). With final=True the last look spends all remaining alpha, as the
    calendar-end look does when it comes before full information."""
    bounds, spent = [], 0.0
    for k, t in enumerate(fractions):
        target = alpha if (final and k == len(fractions) - 1) else ld_obf_spending(t, alpha)
        increment = target - spent
        if increment <= 1e-15:
            bounds.append(math.inf)
            continue
        lo, hi = -2.0, 15.0
        for _ in range(200):
            mid = (lo + hi) / 2.0
            up, _ = crossing_probs(fractions[:k + 1], bounds + [mid], None, 0.0, m)
            if up[k] > increment:
                lo = mid
            else:
                hi = mid
            if hi - lo < tol:
                break
        bounds.append((lo + hi) / 2.0)
        spent = target
    return bounds


def fixed_sample_sessions(delta, sigma, alpha=0.05, power=0.80):
    """Sessions for a one-sided fixed-sample z test: ((z_{1-alpha} + z_power) sigma / delta)^2."""
    if delta <= 0:
        return None
    return ((norm_ppf(1.0 - alpha) + norm_ppf(power)) * sigma / delta) ** 2


def futility_bounds(plan):
    """Planned futility bounds (Z) per look: the plan's z_at_or_below at its futility looks, else -inf."""
    return [plan["futility"]["z_at_or_below"] if (k + 1) in plan["futility"]["looks"] else -math.inf
            for k in range(len(plan["looks_sessions"]))]


def design(protocol):
    """Every design number in the protocol, from the sequential plan and the power inputs only:
    Lan-DeMets O'Brien-Fleming boundaries at the planned information fractions, error rates and power
    at the forward sd for each planning effect."""
    plan = protocol["sequential_plan"]
    power = protocol["power"]
    looks = plan["looks_sessions"]
    n_max = looks[-1]
    fractions = [n / n_max for n in looks]
    alpha = plan["alpha_one_sided"]
    m = plan["grid_points_m"]
    upper = ld_boundaries(fractions, alpha, m)
    futility = futility_bounds(plan)
    sigma = power["forward_daily_sd_bps_nw_effective"]
    out = {"spending": "Lan-DeMets O'Brien-Fleming", "information_fractions": fractions,
           "alpha_spent_cumulative": [ld_obf_spending(t, alpha) for t in fractions], "efficacy_z": upper,
           "futility_z": [None if f == -math.inf else f for f in futility], "sd_bps": sigma}
    up0, _ = crossing_probs(fractions, upper, None, 0.0, m)
    up0f, lo0f = crossing_probs(fractions, upper, futility, 0.0, m)
    out["type_i_error"] = {"without_futility": sum(up0), "if_futility_followed": sum(up0f),
                           "futility_stop_probability_h0": sum(lo0f)}
    scenarios = {}
    for name, delta in power["effect_scenarios_bps"].items():
        theta = delta / sigma * math.sqrt(n_max)
        up, _ = crossing_probs(fractions, upper, None, theta, m)
        upf, lof = crossing_probs(fractions, upper, futility, theta, m)
        stop = [u + lo for u, lo in zip(upf, lof)]
        expected = sum(n * p for n, p in zip(looks, stop)) + n_max * (1.0 - sum(stop))
        fixed = fixed_sample_sessions(delta, sigma, alpha, 0.80)
        scenarios[name] = {"delta_bps": delta, "drift_theta": theta, "power_without_futility": sum(up),
                           "power_if_futility_followed": sum(upf), "futility_stop_probability": sum(lof),
                           "expected_sessions_if_futility_followed": expected,
                           "fixed_sample_sessions_80pct": None if fixed is None else math.ceil(fixed)}
    out["scenarios"] = scenarios
    return out


def simulate_drawdown(mu_bps, sd_bps, n_sessions, threshold_bps, sims=4000, seed=20260925, checkpoints=(60, 125, 250, 375)):
    """How often the drawdown harm trigger fires: daily long-short net returns N(mu, sd) in bps, cumulative
    peak-to-trough drawdown >= threshold (bps of the long-short sum; 2,000 bps is 10% of gross for balanced
    legs, since a balanced book's dollar P&L over its gross is half the long-short return). Each trigger is
    followed by the pre-stated resume (a review finding no execution fault) and the drawdown is re-based."""
    rng = random.Random(seed)
    firsts, counts = [], []
    for _ in range(sims):
        cum = peak = 0.0
        first, n = None, 0
        for t in range(1, n_sessions + 1):
            cum += rng.gauss(mu_bps, sd_bps)
            if cum > peak:
                peak = cum
            if peak - cum >= threshold_bps:
                n += 1
                first = first or t
                peak = cum
        firsts.append(first)
        counts.append(n)
    hit = sorted(f for f in firsts if f is not None)
    return {"p_first_trigger_by_session": {str(c): sum(1 for f in hit if f <= c) / sims for c in checkpoints},
            "mean_triggers_in_horizon": sum(counts) / sims,
            "median_first_trigger_session": hit[len(hit) // 2] if len(hit) * 2 > sims else None}


def harm_simulation(protocol, sims=4000, seed=20260925):
    """simulate_drawdown for every planning effect, net of the modelled cost, at the forward sd."""
    power, harm = protocol["power"], protocol["harm_stops"]
    n = protocol["sequential_plan"]["looks_sessions"][-1]
    threshold = 2.0 * harm["drawdown_fraction_of_average_gross"] * 1e4
    return {name: {"gross_bps": delta, "net_bps": delta - power["modelled_cost_bps_per_day"],
                   **simulate_drawdown(delta - power["modelled_cost_bps_per_day"], power["forward_daily_sd_bps_nw_effective"],
                                       n, threshold, sims, seed)}
            for name, delta in power["effect_scenarios_bps"].items()}


# --------------------------------------------------------------------------------------
# Guard (freeze record, frozen protocol, freeze commit, deployment record, pins, clean tree)
# --------------------------------------------------------------------------------------


class FrozenProtocol:
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


def _utc(value):
    try:
        return sig.as_utc(value)
    except (ValueError, TypeError):
        return None


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


def read_deployment_record(path):
    try:
        rec = json.loads(Path(path).read_text())
    except FileNotFoundError:
        raise Refusal(f"deployment record missing: {path}") from None
    except ValueError:
        raise Refusal("deployment record is not valid JSON") from None
    at = _utc(rec.get("deployed_at"))
    if at is None:
        raise Refusal("deployment record has no deployed_at")
    commit = _hex(rec.get("deployed_commit"), 40)
    if commit is None:
        raise Refusal("deployment record has no full deployed_commit")
    return at, commit


def guard(protocol_path, expected_sha256):
    """The parsed protocol, only when frozen and its bytes hash to ``expected_sha256``."""
    raw = Path(protocol_path).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if _hex(expected_sha256, 64) != actual:
        raise Refusal(f"protocol sha256 mismatch: expected {expected_sha256!r}, file has {actual}")
    p = json.loads(raw)
    if p.get("status") != FROZEN_STATUS or p.get("frozen_before_outcomes") is not True or not _utc(p.get("frozen_at")):
        raise Refusal(f"protocol is not frozen (status={p.get('status')!r}, "
                      f"frozen_before_outcomes={p.get('frozen_before_outcomes')!r}, frozen_at={p.get('frozen_at')!r})")
    return FrozenProtocol(p, actual, protocol_path, _TOKEN)


def git(directory, *args):
    return subprocess.run(["git", *args], cwd=directory, capture_output=True, text=True)


def git_clean_head(directory):
    st = git(directory, "status", "--porcelain", "--", ".")
    if st.returncode != 0:
        raise Refusal("not a git checkout: " + st.stderr.strip())
    if st.stdout.strip():
        raise Refusal("news-reversal directory has uncommitted changes")
    head = git(directory, "rev-parse", "HEAD")
    if head.returncode != 0:
        raise Refusal("git rev-parse HEAD failed")
    return head.stdout.strip()


def is_ancestor(directory, ancestor, descendant):
    return subprocess.run(["git", "merge-base", "--is-ancestor", ancestor, descendant], cwd=directory,
                          capture_output=True).returncode == 0


def verify_freeze_commit(directory, commit, expected_sha256):
    """The freeze commit is an ancestor of HEAD and its forward-protocol.json hashes to the record."""
    if not is_ancestor(directory, commit, "HEAD"):
        raise Refusal(f"freeze commit {commit} is not an ancestor of HEAD")
    shown = subprocess.run(["git", "show", f"{commit}:./forward-protocol.json"], cwd=directory, capture_output=True)
    if shown.returncode != 0 or hashlib.sha256(shown.stdout).hexdigest() != expected_sha256:
        raise Refusal("forward-protocol.json at the freeze commit does not match the freeze record")


def verify_deployment(directory, freeze_commit, deployed_commit):
    if not is_ancestor(directory, freeze_commit, deployed_commit):
        raise Refusal(f"deployed commit {deployed_commit} does not descend from the freeze commit {freeze_commit}")


def pin_paths(study_dir=HERE, repo_root=REPO):
    study_dir, repo_root = Path(study_dir), Path(repo_root)
    return {
        "runner_code": {n: study_dir.parent / "news-forward" / n for n in RUNNER_CODE},
        "study_code": {n: study_dir.parent / "news-llm" / n for n in STUDY_CODE},
        "analysis_code": {n: study_dir / n for n in ANALYSIS_CODE},
        "reference": {n: repo_root / rel for n, rel in REFERENCE.items()},
    }


def compute_pins(study_dir=HERE, repo_root=REPO):
    return {g: {n: (sha256_file(p) if p.exists() else None) for n, p in d.items()}
            for g, d in pin_paths(study_dir, repo_root).items()}


def verify_pins(protocol, study_dir, repo_root):
    pins = protocol.get("pins") or {}
    for group, files in pin_paths(study_dir, repo_root).items():
        want = pins.get(group) or {}
        if set(want) != set(files):
            raise Refusal(f"pin set differs: {group}")
        for name, path in files.items():
            if not _hex(want.get(name), 64):
                raise Refusal(f"pin missing: {group}/{name}")
            if not path.exists():
                raise Refusal(f"pinned file missing: {group}/{name}")
            if sha256_file(path) != want[name]:
                raise Refusal(f"pin mismatch: {group}/{name}")


class Authorization:
    """Issued only by authorize() after every check; the only key to the loaders."""

    def __init__(self, frozen, head, freeze_commit, deployed_at, deployed_commit, study_dir, state_root, repo_root, token):
        if token is not _RUN_TOKEN:
            raise Refusal("an Authorization can only be issued by authorize()")
        if not isinstance(frozen, FrozenProtocol) or frozen._token is not _TOKEN:
            raise Refusal("an Authorization needs the FrozenProtocol returned by guard()")
        self.frozen, self.head, self._token = frozen, head, token
        self.freeze_commit, self.deployed_at, self.deployed_commit = freeze_commit, deployed_at, deployed_commit
        self.study_dir, self.state_root, self.repo_root = Path(study_dir), Path(state_root), Path(repo_root)


def require(auth):
    if not isinstance(auth, Authorization) or auth._token is not _RUN_TOKEN:
        raise Refusal("journal access requires the Authorization issued by authorize() "
                      "(freeze and deployment records, pins, clean tree and freeze commit checked)")
    guard(auth.frozen.path, auth.frozen.sha256)
    return auth


def authorize(a, study_dir=HERE, repo_root=REPO):
    study_dir = Path(study_dir)
    record = Path(getattr(a, "freeze_record", None) or study_dir / "receipts" / "freeze-record.json")
    expected, commit = read_freeze_record(record)
    given = getattr(a, "protocol_sha256", None)
    if given and given.strip().lower() != expected:
        raise Refusal("--protocol-sha256 differs from the freeze record")
    frozen = guard(study_dir / "forward-protocol.json", expected)
    deployed_at, deployed_commit = read_deployment_record(
        getattr(a, "deployment_record", None) or study_dir / "receipts" / "deployment-record.json")
    verify_pins(frozen.protocol, study_dir, repo_root)
    head = git_clean_head(study_dir)
    verify_freeze_commit(study_dir, commit, expected)
    verify_deployment(study_dir, commit, deployed_commit)
    return Authorization(frozen, head, commit, deployed_at, deployed_commit, study_dir, a.state, repo_root, _RUN_TOKEN)


# --------------------------------------------------------------------------------------
# Counted sessions (pure) and journal loading (guarded)
# --------------------------------------------------------------------------------------


def load_calendar(repo_root=REPO):
    with open(Path(repo_root) / REFERENCE["session-calendar.json"], encoding="utf-8") as handle:
        return sig.Calendar.from_calendar_json(json.load(handle))


def counted_start(calendar, frozen_at, deployed_at):
    """The first XNYS session whose official open is after both the freeze and the deployment."""
    after = max(_utc(frozen_at), _utc(deployed_at))
    for s in calendar.sessions:
        if s.open_utc > after:
            return s.session
    return None


def session_qualifies(starts, protocol_sha256, pins):
    """(ok, reasons) over EVERY start record of a session (review minor: restarts included). A session counts
    only when each start shows the qualifying runtime; reasons of later starts are prefixed restart:. The
    conditions are about the running code and mode, never about outcomes. A single record is accepted too."""
    if starts is None or starts == []:
        return False, ["no_start_record"]
    reasons = []
    for i, start in enumerate([starts] if isinstance(starts, dict) else starts):
        found = _start_reasons(start, protocol_sha256, pins)
        reasons += found if i == 0 else [f"restart:{r}" for r in found]
    return not reasons, reasons


def _start_reasons(start, protocol_sha256, pins):
    reasons = []
    if start.get("evidence_label") != RUN_LABEL:
        reasons.append(f"run_label:{start.get('evidence_label')}")
    if start.get("mode") != "paper":
        reasons.append(f"mode:{start.get('mode')}")
    if start.get("rth_reversal_active") is not True:
        reasons.append("rth_reversal_inactive")
    if start.get("reversal_protocol_sha256") != protocol_sha256:
        reasons.append("protocol_sha256_mismatch")
    code = start.get("code_sha256") or {}
    runner = pins.get("runner_code") or {}
    for name in sorted(set(code) | set(runner)):
        if code.get(name) != runner.get(name):
            reasons.append(f"runner_code_pin:{name}")
    study = pins.get("study_code") or {}
    if start.get("news_signal_sha256") != study.get("news_signal.py"):
        reasons.append("study_code_pin:news_signal.py")
    if start.get("score_py_sha256") != study.get("score.py"):
        reasons.append("study_code_pin:score.py")
    if start.get("account") != RUNTIME_ACCOUNT:
        reasons.append(f"account:{start.get('account')}")
    return reasons


def read_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue  # a torn final line from a crash
    return rows


def journal_path(state_root, day):
    return Path(state_root) / "journal" / f"{day.isoformat()}.jsonl"


def load_sessions(auth, calendar, until=None):
    """(start_session, [(session, rows, ok, reasons)]) for every session from the counted start
    up to `until` (default: today in New York), in order. Earlier journals are never opened."""
    require(auth)
    start = counted_start(calendar, auth.frozen.protocol["frozen_at"], auth.deployed_at)
    until = until or datetime.now(timezone.utc).astimezone(sig.NY).date()
    out = []
    if start is None:
        return start, out
    pins = auth.frozen.protocol["pins"]
    for s in calendar.sessions:
        if s.session < start or s.session > until:
            continue
        path = journal_path(auth.state_root, s.session)
        if not path.exists():
            out.append((s.session, [], False, ["no_journal"]))
            continue
        rows = read_jsonl(path)
        starts = [r for r in rows if r.get("kind") == "lifecycle" and r.get("event") == "start"]
        ok, reasons = session_qualifies(starts, auth.frozen.sha256, pins)
        out.append((s.session, rows, ok, reasons))
    while out and out[-1][3] == ["no_journal"]:
        out.pop()  # sessions after the last journal have not run yet: neither counted nor excluded
    return start, out


# --------------------------------------------------------------------------------------
# Positions, returns and execution cost (pure)
# --------------------------------------------------------------------------------------


def parse_rev_cid(cid):
    """{date, stage, symbol, leg} of an rth_reversal client order id, else None."""
    if not isinstance(cid, str) or not cid.startswith(REV_PREFIX):
        return None
    parts = cid[len(REV_PREFIX):].split("-")
    if len(parts) != 4 or len(parts[0]) != 8 or not parts[0].isdigit():
        return None
    d = parts[0]
    return {"date": date(int(d[:4]), int(d[4:6]), int(d[6:])), "stage": parts[1], "symbol": parts[2], "leg": parts[3]}


def is_entry_fill(info, side):
    return (info["leg"] == "long") == (side == "buy")


def fills_by_holding(rows_iter):
    """{(entry_date, symbol, leg): {"entry": [...], "exit": [...]}} from journal fill rows of the rev
    arm, de-duplicated by broker order id (a restart can reconcile twice; the last row wins)."""
    by_id = {}
    for r in rows_iter:
        if r.get("kind") != "fill":
            continue
        info = parse_rev_cid(r.get("client_order_id"))
        if info is None or float(r.get("filled_qty") or 0) <= 0:
            continue
        by_id[r.get("id") or r.get("client_order_id")] = (info, r)
    out = defaultdict(lambda: {"entry": [], "exit": []})
    for info, r in by_id.values():
        key = (info["date"], info["symbol"], info["leg"])
        out[key]["entry" if is_entry_fill(info, r.get("side")) else "exit"].append(r)
    return out


def vwap(fills):
    qty = sum(float(f["filled_qty"]) for f in fills)
    if qty <= 0:
        return 0.0, None
    return qty, sum(float(f["filled_qty"]) * float(f["filled_avg_price"]) for f in fills) / qty


def bps(x):
    return None if x is None else x * 1e4


def position_costs(side, entry_price, exit_price, quote, close, fees_usd, notional, costs):
    """Execution cost of one round trip in bps of entry notional (positive = cost).

    measured_vs_mid: entry fill against the decision-time quote mid, exit fill against the
    official close, plus modelled fees; measured_beyond_touch: the same with the entry measured
    against the side of the quote the frozen study charges (ask for longs, bid for shorts);
    assumed_*: the frozen study's model for the same position (its gross already pays the touch,
    then the entry and exit allowances and fees)."""
    fees = fees_usd / notional
    out = {"fees_bps": bps(fees), "half_spread_bps": None, "entry_vs_mid_bps": None, "entry_vs_touch_bps": None,
           "exit_vs_close_bps": None}
    allowance = (costs["rth_entry_allowance_bps"] + costs["exit_allowance_bps"]) / 1e4
    if quote:
        bid, ask = float(quote["bid"]), float(quote["ask"])
        mid = (bid + ask) / 2.0
        touch = ask if side == 1 else bid
        out["half_spread_bps"] = bps((ask - bid) / 2.0 / mid)
        out["entry_vs_mid_bps"] = bps(side * (entry_price - mid) / mid)
        out["entry_vs_touch_bps"] = bps(side * (entry_price - touch) / mid)
    if close:
        out["exit_vs_close_bps"] = bps(side * (close - exit_price) / close)
    if out["entry_vs_mid_bps"] is not None and out["exit_vs_close_bps"] is not None:
        out["measured_vs_mid_bps"] = out["entry_vs_mid_bps"] + out["exit_vs_close_bps"] + out["fees_bps"]
        out["measured_beyond_touch_bps"] = out["entry_vs_touch_bps"] + out["exit_vs_close_bps"] + out["fees_bps"]
        out["assumed_vs_mid_bps"] = out["half_spread_bps"] + bps(allowance) + out["fees_bps"]
        out["assumed_beyond_touch_bps"] = bps(allowance) + out["fees_bps"]
    else:
        out.update(measured_vs_mid_bps=None, measured_beyond_touch_bps=None, assumed_vs_mid_bps=None,
                   assumed_beyond_touch_bps=None)
    return out


def session_positions(session, session_rows, holdings, fees, costs):
    """(positions, unresolved) of one counted session's rev arm from its fills (entries dated
    `session`), the decision rows (quotes) and close marks. A position is resolved when its
    exit quantity equals its entry quantity; returns come from actual fill prices only."""
    decisions = {}
    marks = {}
    for r in session_rows:
        if r.get("kind") == "decision" and r.get("arm") == REV_ARM and r.get("action") == "enter" and r.get("client_order_id"):
            decisions[r["client_order_id"]] = r
        elif r.get("kind") == "close_mark" and r.get("official_close"):
            marks[r["symbol"]] = float(r["official_close"])
    positions, unresolved = [], []
    for (entry_date, symbol, leg), fl in sorted(holdings.items()):
        if entry_date != session or not fl["entry"]:
            continue
        side = 1 if leg == "long" else -1
        qty_in, px_in = vwap(fl["entry"])
        qty_out, px_out = vwap(fl["exit"])
        cid = fl["entry"][0]["client_order_id"]
        if abs(qty_out - qty_in) > 1e-9:
            unresolved.append({"session": session.isoformat(), "symbol": symbol, "leg": leg, "entry_qty": qty_in,
                               "exit_qty": qty_out})
            continue
        d = decisions.get(cid, {})
        quote = {"bid": d["quote_bid"], "ask": d["quote_ask"]} if d.get("quote_bid") and d.get("quote_ask") else None
        notional = qty_in * px_in
        sale_price, sale_qty = (px_out, qty_in) if side == 1 else (px_in, qty_in)
        fees_usd = sig.sale_fees_usd(fees, session, sale_qty, sale_price)
        gross = sig.gross_return(side, px_in, px_out)
        net = sig.position_net_return(side, px_in, px_out, session, fees, notional, costs["rth_entry_allowance_bps"] / 1e4,
                                      costs["exit_allowance_bps"] / 1e4)
        positions.append({"session": session.isoformat(), "symbol": symbol, "event_id": d.get("event_id"), "leg": leg,
                          "side": side, "label": d.get("label"), "entry_qty": qty_in, "entry_price": px_in,
                          "exit_price": px_out, "notional": notional, "gross": gross, "net": net,
                          "exit_stages": sorted({(parse_rev_cid(f["client_order_id"]) or {}).get("stage") for f in fl["exit"]}),
                          "cost": position_costs(side, px_in, px_out, quote, marks.get(symbol), fees_usd, notional, costs)})
    return positions, unresolved


def close_marks(session_rows):
    return {r["symbol"]: float(r["official_close"]) for r in session_rows
            if r.get("kind") == "close_mark" and r.get("official_close")}


def itt_positions(session, session_rows):
    """Intent to treat (secondary): every rth_reversal entry decision, filled or not, from the decision
    quote's touch (ask for a long, bid for a short) and from its mid to the official close mark."""
    marks = close_marks(session_rows)
    out = []
    for r in session_rows:
        if r.get("kind") != "decision" or r.get("arm") != REV_ARM or r.get("action") != "enter":
            continue
        close, touch, mid = marks.get(r["symbol"]), r.get("limit_price"), r.get("quote_mid")
        if close is None or not touch or not mid:
            continue
        side = 1 if r.get("leg") == "long" else -1
        out.append({"session": session.isoformat(), "symbol": r["symbol"], "side": side, "leg": r.get("leg"),
                    "intended_qty": float(r.get("qty") or 0), "client_order_id": r.get("client_order_id"),
                    "gross_touch": sig.gross_return(side, float(touch), close),
                    "gross_mid": sig.gross_return(side, float(mid), close)})
    return out


def benchmark_mean(session_rows):
    """The news-day benchmark (secondary; NEWS-2B's analogue): the mean return of every first-in-window liquid RTH
    event held long from its entry-minute quote's ask to the official close, whatever its label; None if none."""
    marks = close_marks(session_rows)
    vals = [marks[r["symbol"]] / float(r["quote_ask"]) - 1.0 for r in session_rows
            if r.get("kind") == "benchmark_quote" and r.get("quote_ask") and r["symbol"] in marks]
    return sum(vals) / len(vals) if vals else None


def intended_entries(session_rows):
    """Every rth_reversal entry decision of a session (the fill-rate denominator), close mark or not."""
    return [{"symbol": r["symbol"], "leg": r.get("leg"), "intended_qty": float(r.get("qty") or 0),
             "client_order_id": r.get("client_order_id")}
            for r in session_rows if r.get("kind") == "decision" and r.get("arm") == REV_ARM and r.get("action") == "enter"]


def fill_rates(intended_all, holdings):
    """Per leg: intended entries, filled names and the filled share of intended quantity."""
    out = {}
    for leg in ("long", "short"):
        intended = [p for p in intended_all if p["leg"] == leg]
        filled_names = qty_in = qty_want = 0.0
        for p in intended:
            info = parse_rev_cid(p["client_order_id"]) or {}
            fl = holdings.get((info.get("date"), p["symbol"], leg)) if info else None
            got = vwap(fl["entry"])[0] if fl else 0.0
            filled_names += 1 if got > 0 else 0
            qty_in += min(got, p["intended_qty"]) if p["intended_qty"] else got
            qty_want += p["intended_qty"]
        out[leg] = {"intended": len(intended), "filled_names": int(filled_names),
                    "name_fill_rate": filled_names / len(intended) if intended else None,
                    "quantity_fill_rate": qty_in / qty_want if qty_want else None}
    return out


def shadow_positions(session, session_rows):
    """Descriptive only: the momentum shadow's hypothetical round trips (no order was sent), entered
    at the decision quote's touch (ask long, bid short) and exited at the official close mark."""
    marks = {r["symbol"]: float(r["official_close"]) for r in session_rows
             if r.get("kind") == "close_mark" and r.get("official_close")}
    out = []
    for r in session_rows:
        if r.get("kind") != "decision" or r.get("arm") != "core_shadow" or r.get("action") != "shadow_enter":
            continue
        close, entry = marks.get(r["symbol"]), r.get("limit_price")
        if close is None or not entry:
            continue
        side = 1 if r.get("leg") == "long" else -1
        out.append({"session": session.isoformat(), "symbol": r["symbol"], "side": side,
                    "gross": sig.gross_return(side, float(entry), close)})
    return out


def daily_values(positions, field):
    """{session: daily_portfolios row} on `field` (gross or net), the frozen study's legs (>= 2 names)."""
    return sig.daily_portfolios([{"session": p["session"], "side": p["side"], "ret": p[field]} for p in positions])


def names_per_leg(holdings, session):
    """(long names, short names) with a filled entry on `session` (no price is read)."""
    n = Counter(leg for (d, _s, leg), fl in holdings.items() if d == session and fl["entry"])
    return n.get("long", 0), n.get("short", 0)


def information_sessions(sessions, holdings):
    """Counted sessions, in order, that carry a primary value (both legs with >= 2 filled names),
    decided from fill counts only (no return is computed). Stops at the first unresolved or
    unreconciled session, since the order of the first n values is not known beyond it.

    Pre-stated backfill (forward-protocol.json#/counted_sessions/reconciliation_backfill): a session whose
    reconciliation never ran is completed by `supervisor.py --reconcile-only --date D` from the paper
    broker's order history (read-only); its reconciliation row carries backfill true and counts like any
    other, so a missed reconciliation delays the sequence but never removes a session."""
    out = []
    for day, rows, ok, _ in sessions:
        if not ok:
            continue
        if not any(r.get("kind") == "reconciliation" and r.get("mode") == "paper" for r in rows):
            break  # no reconciliation fill record yet (or ever): the sequence cannot be extended past it
        n_long, n_short = names_per_leg(holdings, day)
        pending = [k for k, fl in holdings.items() if k[0] == day and fl["entry"]
                   and abs(vwap(fl["exit"])[0] - vwap(fl["entry"])[0]) > 1e-9]
        if pending:
            break
        if n_long >= sig.MIN_NAMES_PER_LEG and n_short >= sig.MIN_NAMES_PER_LEG:
            out.append(day)
    return out


# --------------------------------------------------------------------------------------
# Looks and harm stops (pure)
# --------------------------------------------------------------------------------------


def look_decision(k, z, efficacy, futility, n_looks):
    """efficacy / futility / final_not_rejected / continue at look k (1-based)."""
    if z >= efficacy[k - 1]:
        return "efficacy"
    f = futility[k - 1]
    if k < n_looks and f is not None and z <= f:
        return "futility"
    if k == n_looks:
        return "final_not_rejected"
    return "continue"


def series_stats(values, lags):
    n = len(values)
    if n < 2:
        return {"n_days": n, "mean_bps": bps(values[0]) if values else None, "t_nw": None, "se_nw_bps": None}
    t, se = sig.newey_west_t(values, lags)
    mu = sum(values) / n
    sd = math.sqrt(sum((v - mu) ** 2 for v in values) / (n - 1))
    ok = not math.isnan(t)
    return {"n_days": n, "mean_bps": bps(mu), "sd_bps": bps(sd), "se_nw_bps": bps(se) if ok else None,
            "t_nw": t if ok else None}


def mean_or_none(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def cost_summary(positions, days):
    """Per round trip and per long-short day (both legs >= 2 names) execution cost, against the
    frozen model's assumption for the same positions and against the historical 8.4 bps/day."""
    costs = [p["cost"] for p in positions]
    by_day = defaultdict(lambda: {1: [], -1: []})
    for p in positions:
        if p["session"] in days and p["cost"]["measured_beyond_touch_bps"] is not None:
            by_day[p["session"]][p["side"]].append(p["cost"]["measured_beyond_touch_bps"])
    per_day = [sum(v[1]) / len(v[1]) + sum(v[-1]) / len(v[-1]) for v in by_day.values()
               if len(v[1]) >= sig.MIN_NAMES_PER_LEG and len(v[-1]) >= sig.MIN_NAMES_PER_LEG]
    return {"round_trips": len(costs),
            "round_trips_with_quote_and_close": sum(1 for c in costs if c["measured_vs_mid_bps"] is not None),
            "mean_half_spread_bps": mean_or_none(c["half_spread_bps"] for c in costs),
            "mean_entry_vs_mid_bps": mean_or_none(c["entry_vs_mid_bps"] for c in costs),
            "mean_entry_vs_touch_bps": mean_or_none(c["entry_vs_touch_bps"] for c in costs),
            "mean_exit_vs_close_bps": mean_or_none(c["exit_vs_close_bps"] for c in costs),
            "mean_fees_bps": mean_or_none(c["fees_bps"] for c in costs),
            "mean_measured_vs_mid_bps": mean_or_none(c["measured_vs_mid_bps"] for c in costs),
            "mean_assumed_vs_mid_bps": mean_or_none(c["assumed_vs_mid_bps"] for c in costs),
            "mean_measured_beyond_touch_bps": mean_or_none(c["measured_beyond_touch_bps"] for c in costs),
            "mean_assumed_beyond_touch_bps": mean_or_none(c["assumed_beyond_touch_bps"] for c in costs),
            "long_short_days_with_costs": len(per_day),
            "mean_measured_beyond_touch_bps_per_long_short_day": mean_or_none(per_day),
            "historical_assumption_bps_per_long_short_day": 8.4}


def _iso(day):
    return day.isoformat() if hasattr(day, "isoformat") else str(day)


def harm_check(sessions_positions, harm, resumes=()):
    """Harm stops over counted sessions in order: cumulative net drawdown against 10% of the
    average gross deployed, and (from the configured session count) the measured execution cost
    per round trip against twice the frozen model's cost for the same positions.

    The drawdown is measured since the last pre-stated resume (harm_stops.resume_rule): after a resume
    recorded with after_session d, the peak is re-based to the cumulative net P&L at d."""
    rebase_after = {r["after_session"] for r in resumes}
    cum = peak = 0.0
    drawdown = 0.0
    gross_by_day = []
    positions = []
    for day, ps in sessions_positions:
        gross_by_day.append(sum(p["notional"] for p in ps))
        cum += sum(p["net"] * p["notional"] for p in ps)
        peak = max(peak, cum)
        drawdown = max(drawdown, peak - cum)
        positions.extend(ps)
        if _iso(day) in rebase_after:
            peak, drawdown = cum, 0.0
    deployed = [g for g in gross_by_day if g > 0]
    avg_gross = sum(deployed) / len(deployed) if deployed else 0.0
    threshold = harm["drawdown_fraction_of_average_gross"] * avg_gross
    reasons = []
    if avg_gross > 0 and drawdown >= threshold:
        reasons.append("cumulative_net_drawdown")
    measured = mean_or_none(p["cost"]["measured_vs_mid_bps"] for p in positions)
    assumed = mean_or_none(p["cost"]["assumed_vs_mid_bps"] for p in positions)
    n_sessions = len(sessions_positions)
    cost_checked = n_sessions >= harm["cost_check_after_sessions"] and measured is not None and assumed is not None
    if cost_checked and measured > harm["cost_multiple"] * assumed:
        reasons.append("execution_cost_above_twice_assumed")
    return {"harm_stop": bool(reasons), "reasons": reasons, "counted_sessions": n_sessions,
            "cumulative_net_pnl_usd": cum, "max_net_drawdown_usd": drawdown, "average_gross_deployed_usd": avg_gross,
            "drawdown_threshold_usd": threshold, "cost_checked": cost_checked,
            "mean_measured_cost_vs_mid_bps": measured, "mean_assumed_cost_vs_mid_bps": assumed}


# --------------------------------------------------------------------------------------
# Guarded commands
# --------------------------------------------------------------------------------------


def reference_json(auth, name):
    return json.loads((auth.repo_root / REFERENCE[name]).read_text())


def collect(auth, until=None):
    """Counted sessions, the rev holdings across every journal from the counted start (exit
    fills of a counted position may land in a later journal) and the exclusions."""
    calendar = load_calendar(auth.repo_root)
    start, sessions = load_sessions(auth, calendar, until)
    holdings = fills_by_holding(r for _, rows, _, _ in sessions for r in rows)
    excluded = Counter(reason for _, _, ok, reasons in sessions if not ok for reason in reasons)
    return start, sessions, holdings, excluded


def positions_for(auth, sessions, holdings, days):
    fees = reference_json(auth, "fees-v3.json")
    costs = auth.frozen.protocol["estimands"]["net_cost_model"]
    out = []
    for day, rows, ok, _ in sessions:
        if ok and day in days:
            ps, _ = session_positions(day, rows, holdings, fees, costs)
            out.append((day, ps))
    return out


def receipts_dir(auth):
    return auth.study_dir / "receipts"


def recorded_looks(auth):
    looks = []
    for k in range(1, len(auth.frozen.protocol["sequential_plan"]["looks_sessions"]) + 1):
        path = receipts_dir(auth) / f"look-{k}.json"
        if path.exists():
            looks.append(json.loads(path.read_text()))
    return looks


def sequence_break(sessions, holdings):
    """The first counted session that is not yet reconciled or resolved (where information_sessions stops), or None."""
    for day, rows, ok, _ in sessions:
        if not ok:
            continue
        if not any(r.get("kind") == "reconciliation" and r.get("mode") == "paper" for r in rows):
            return day
        if [k for k, fl in holdings.items() if k[0] == day and fl["entry"]
                and abs(vwap(fl["exit"])[0] - vwap(fl["entry"])[0]) > 1e-9]:
            return day
    return None


def look_plan(plan, k, info_days, today, brk):
    """(sessions used, final?) for look k: its planned session count when reached; at or after the calendar end
    date, a final look with every complete counted long-short session up to that date (spending all remaining
    alpha); otherwise a Refusal."""
    looks = plan["looks_sessions"]
    end = date.fromisoformat(plan["calendar_end"])
    within = [d for d in info_days if d <= end]
    n_k = looks[k - 1]
    if len(within) >= n_k:
        return n_k, k == len(looks)
    if today >= end:
        if brk is not None and brk <= end:
            raise Refusal(f"the calendar-end look waits for session {brk.isoformat()} to be reconciled and resolved")
        if len(within) < 2:
            raise Refusal("the calendar-end look needs at least 2 counted long-short sessions")
        return len(within), True
    raise Refusal(f"look {k} needs {n_k} counted long-short sessions; {len(within)} are complete")


def run_look(auth, until=None):
    require(auth)
    protocol = auth.frozen.protocol
    plan = protocol["sequential_plan"]
    looks = plan["looks_sessions"]
    n_max, alpha, m = looks[-1], plan["alpha_one_sided"], plan["grid_points_m"]
    done = recorded_looks(auth)
    if done and done[-1]["look_decision"] != "continue":
        raise Refusal(f"the trial stopped at look {done[-1]['look']} ({done[-1]['look_decision']}); no further look")
    k = len(done) + 1
    if k > len(looks):
        raise Refusal("every planned look is recorded")
    start, sessions, holdings, excluded = collect(auth, until)
    info_days = information_sessions(sessions, holdings)
    today = until or datetime.now(timezone.utc).astimezone(sig.NY).date()
    n_use, final = look_plan(plan, k, info_days, today, sequence_break(sessions, holdings))
    days = set(info_days[:n_use])
    per_day = positions_for(auth, sessions, holdings, days)
    positions = [p for _, ps in per_day for p in ps]
    gross = daily_values(positions, "gross")
    net = daily_values(positions, "net")
    order = sorted(d.isoformat() for d in days)
    primary = [gross[d]["long_short"] for d in order]
    lags = protocol["estimands"]["newey_west_lags"]
    stats = series_stats(primary, lags)
    if stats["t_nw"] is None:
        raise Refusal("the primary series is degenerate (no Newey-West t)")
    fractions = [n / n_max for n in looks[:k - 1]] + [min(1.0, n_use / n_max)]
    efficacy = ld_boundaries(fractions, alpha, m, final=final)
    futility = [None if f == -math.inf else f for f in futility_bounds(plan)][:k]
    decision = look_decision(k, stats["t_nw"], efficacy, futility, k if final else len(looks))
    looked = [(day, rows) for day, rows, ok, _ in sessions if ok and day in days]
    shadow = [p for day, rows in looked for p in shadow_positions(day, rows)]
    shadow_daily = daily_values(shadow, "gross")
    itt = [p for day, rows in looked for p in itt_positions(day, rows)]
    itt_touch, itt_mid = daily_values(itt, "gross_touch"), daily_values(itt, "gross_mid")
    bench = {day.isoformat(): benchmark_mean(rows) for day, rows in looked}
    receipt = {
        "schema": "news-reversal-look/2", "look": k, "planned_sessions": looks[k - 1], "sessions_used_count": n_use,
        "final_look": final, "calendar_end_look": final and n_use < looks[k - 1],
        "information_fraction": fractions[-1], "alpha_spent_cumulative": alpha if final else ld_obf_spending(fractions[-1], alpha),
        "test_label": protocol["planning_measurement"]["result"]["label"],
        "protocol_id": protocol["id"], "protocol_sha256": auth.frozen.sha256, "freeze_commit": auth.freeze_commit,
        "deployed_commit": auth.deployed_commit, "deployed_at": auth.deployed_at.isoformat(), "head": auth.head,
        "counted_start": start.isoformat(), "sessions_used": {"first": order[0], "last": order[-1], "count": len(order)},
        "excluded_sessions": dict(excluded),
        # key look_decision, not decision: blueprint JSON values under a "decision" key must be classified labels
        # (tests/test_blind_checkout.py)
        "primary": {"series": "gross long-short, equal-weight legs of >= 2 names (news_signal.daily_portfolios)",
                    **stats, "efficacy_boundary_z": efficacy[-1], "futility_boundary_z": futility[-1] if not final else None,
                    "spending": "Lan-DeMets O'Brien-Fleming, one-sided"},
        "look_decision": decision,
        "secondary_reported_not_tested": {
            "net_long_short": series_stats([net[x]["long_short"] for x in order], lags),
            "gross_long_leg": series_stats([gross[x]["long"] for x in order], lags),
            "gross_short_leg": series_stats([gross[x]["short"] for x in order], lags),
            "net_long_leg": series_stats([net[x]["long"] for x in order], lags),
            "net_short_leg": series_stats([net[x]["short"] for x in order], lags),
            "intent_to_treat_touch_to_close_long_short": series_stats(
                [itt_touch[x]["long_short"] for x in order if x in itt_touch and itt_touch[x]["long_short"] is not None], lags),
            "intent_to_treat_mid_to_close_long_short": series_stats(
                [itt_mid[x]["long_short"] for x in order if x in itt_mid and itt_mid[x]["long_short"] is not None], lags),
            "long_leg_minus_news_day_benchmark_intent_to_treat": series_stats(
                [itt_touch[x]["long"] - bench[x] for x in order
                 if x in itt_touch and itt_touch[x]["long"] is not None and bench.get(x) is not None], lags),
            "long_leg_minus_news_day_benchmark_fills": series_stats(
                [gross[x]["long"] - bench[x] for x in order if gross[x]["long"] is not None and bench.get(x) is not None], lags),
            "fill_rate_by_leg": fill_rates([p for day, rows in looked for p in intended_entries(rows)], holdings)},
        "execution_cost": cost_summary(positions, set(order)),
        "momentum_shadow_descriptive": series_stats(
            [v["long_short"] for x, v in sorted(shadow_daily.items()) if v["long_short"] is not None], lags),
        "inputs": {day.isoformat(): sha256_file(journal_path(auth.state_root, day)) for day, _, _, _ in sessions
                   if journal_path(auth.state_root, day).exists()},
        "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    path = receipts_dir(auth) / f"look-{k}.json"
    path.write_text(json.dumps(receipt, indent=1, sort_keys=True, default=str) + "\n")
    Path(str(path) + ".sha256").write_text(f"{sha256_file(path)}  {path.name}\n")
    return receipt


def run_monitor(auth, apply=False, until=None):
    require(auth)
    protocol = auth.frozen.protocol
    start, sessions, holdings, excluded = collect(auth, until)
    days = set()
    for day, rows, ok, _ in sessions:
        if not ok:
            continue
        if not any(r.get("kind") == "reconciliation" and r.get("mode") == "paper" for r in rows):
            break
        days.add(day)
    per_day = positions_for(auth, sessions, holdings, days)
    result = harm_check(per_day, protocol["harm_stops"], read_jsonl(resumes_path(auth)))
    result.update(schema="news-reversal-monitor/2", protocol_sha256=auth.frozen.sha256, head=auth.head,
                  counted_start=start.isoformat() if start else None, excluded_sessions=dict(excluded),
                  last_counted_session=max(days).isoformat() if days else None,
                  computed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    out_dir = auth.state_root / "reversal-monitor"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).astimezone(sig.NY).date().isoformat()
    (out_dir / f"{stamp}.json").write_text(json.dumps(result, indent=1, sort_keys=True, default=str) + "\n")
    if apply and result["harm_stop"]:
        (auth.state_root / HALT_FILE).write_text(json.dumps({"reasons": result["reasons"], "at": result["computed_at"]}) + "\n")
    return result


def resumes_path(auth):
    return auth.state_root / "reversal-monitor" / "resumes.jsonl"


RESUME_FINDINGS = ("no_execution_fault", "execution_fault_fixed")


def run_resume(auth, finding, note, after_session):
    """The pre-stated resume (harm_stops.resume_rule): after a harm halt, a review that finds no execution
    fault (or an execution fault that has been fixed and recorded as a deviation) resumes rth_reversal entries.
    Records the review, re-bases the drawdown after `after_session` and removes the halt file."""
    require(auth)
    if finding not in RESUME_FINDINGS:
        raise Refusal(f"finding must be one of {RESUME_FINDINGS}")
    if not note or len(note.strip()) < 10:
        raise Refusal("a resume needs the review's note")
    halt = auth.state_root / HALT_FILE
    if not halt.exists():
        raise Refusal("no harm halt is in force")
    row = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "finding": finding, "note": note.strip(),
           "after_session": date.fromisoformat(after_session).isoformat(), "halt": halt.read_text().strip()}
    path = resumes_path(auth)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    halt.unlink()
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("design")
    d.add_argument("--protocol", type=Path, default=PROTOCOL_PATH)
    d.add_argument("--out", type=Path)
    d.add_argument("--harm-simulation", action="store_true", help="also simulate the drawdown trigger (seeded, a few seconds)")
    sub.add_parser("pins")
    for name in ("look", "monitor", "resume"):
        p = sub.add_parser(name)
        p.add_argument("--state", type=Path, default=DEFAULT_STATE)
        p.add_argument("--freeze-record", type=Path, default=FREEZE_RECORD_PATH)
        p.add_argument("--deployment-record", type=Path, default=DEPLOYMENT_RECORD_PATH)
        p.add_argument("--protocol-sha256")
        if name == "monitor":
            p.add_argument("--apply", action="store_true", help=f"write <state>/{HALT_FILE} when a harm stop fires")
        if name == "resume":
            p.add_argument("--finding", required=True, choices=RESUME_FINDINGS)
            p.add_argument("--note", required=True, help="the review's summary (what was checked, what was found)")
            p.add_argument("--after-session", required=True, help="last completed session before the resume (YYYY-MM-DD)")
    a = parser.parse_args(argv)
    if a.command == "design":
        protocol = json.loads(a.protocol.read_text())
        result = design(protocol)
        if a.harm_simulation:
            result["harm_simulation"] = harm_simulation(protocol)
        text = json.dumps(result, indent=1, sort_keys=True)
        if a.out:
            a.out.write_text(text + "\n")
        print(text)
        return 0
    if a.command == "pins":
        print(json.dumps(compute_pins(), indent=1, sort_keys=True))
        return 0
    try:
        auth = authorize(a)
        if a.command == "look":
            result = run_look(auth)
        elif a.command == "monitor":
            result = run_monitor(auth, apply=a.apply)
        else:
            result = run_resume(auth, a.finding, a.note, a.after_session)
    except Refusal as r:
        print(f"REFUSED: {r.reason}", file=sys.stderr)
        return 2
    print(json.dumps({k: result.get(k) for k in ("look", "look_decision", "harm_stop", "reasons")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
