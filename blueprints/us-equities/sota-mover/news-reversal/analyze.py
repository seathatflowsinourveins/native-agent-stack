#!/usr/bin/env python3
"""Guarded group-sequential analysis of the preregistered rth_reversal forward paper test.

  python analyze.py design [--out PATH]            # design numbers only: boundaries, error rates, power; no data
  python analyze.py pins                           # sha256 of every file forward-protocol.json#/pins names
  python analyze.py look [--state ROOT]            # the next due look (receipts/look-<k>.json); guarded
  python analyze.py monitor [--state ROOT] [--apply]   # harm stops only; --apply writes <state>/HALT-rth_reversal

look and monitor refuse (exit 2) before they open any journal unless all of these hold (the
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
shakedown days) are never opened. A later session counts only when its first start record
shows paper mode, the rth_reversal arm active, the reversal run label, the frozen protocol's
sha256 and the pinned runner and study code; otherwise it is excluded with its reason and
nothing is computed from it except the exit fills of earlier counted positions.
"""
import argparse
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
ANALYSIS_CODE = ("analyze.py",)
REFERENCE = {
    "fees-v3.json": "blueprints/us-equities/mover-v3/data/fees-v3.json",
    "session-calendar.json": "blueprints/us-equities/mover-v3/data/session-calendar.json",
    "checkpoints.json": "blueprints/us-equities/sota-mover/news-llm/checkpoints.json",
}
REV_ARM, REV_PREFIX = "rev", "nf1r-"
RUN_LABEL = "reversal_forward"  # common.REVERSAL_RUN_LABEL of the runner
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


def fixed_sample_sessions(delta, sigma, alpha=0.05, power=0.80):
    """Sessions for a one-sided fixed-sample z test: ((z_{1-alpha} + z_power) sigma / delta)^2."""
    if delta <= 0:
        return None
    return ((norm_ppf(1.0 - alpha) + norm_ppf(power)) * sigma / delta) ** 2


def design(protocol):
    """Every design number in the protocol, from the sequential plan and the power inputs only."""
    plan = protocol["sequential_plan"]
    power = protocol["power"]
    looks = plan["looks_sessions"]
    n_max = looks[-1]
    fractions = [n / n_max for n in looks]
    alpha = plan["alpha_one_sided"]
    m = plan["grid_points_m"]
    c, upper = obf_boundaries(fractions, alpha, m)
    futility = [plan["futility"]["z_at_or_below"] if (k + 1) in plan["futility"]["looks"] else -math.inf
                for k in range(len(looks))]
    sigma = power["daily_sd_bps_nw_effective"]
    out = {"information_fractions": fractions, "obf_constant": c, "efficacy_z": upper,
           "futility_z": [None if f == -math.inf else f for f in futility]}
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
    out["fixed_sample_80pct_by_sd"] = {
        str(sd): math.ceil(fixed_sample_sessions(power["in_sample_gross_bps"], sd, alpha, 0.80))
        for sd in (power["daily_sd_bps_sample"], power["daily_sd_bps_nw_effective"], power["daily_sd_bps_rounded"])}
    return out


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


def session_qualifies(start, protocol_sha256, pins):
    """(ok, reasons) for a session's first start record (outcome-independent conditions only)."""
    if start is None:
        return False, ["no_start_record"]
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
    return not reasons, reasons


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
        first = next((r for r in rows if r.get("kind") == "lifecycle" and r.get("event") == "start"), None)
        ok, reasons = session_qualifies(first, auth.frozen.sha256, pins)
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
    unreconciled session, since the order of the first n values is not known beyond it."""
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


def harm_check(sessions_positions, harm):
    """Harm stops over counted sessions in order: cumulative net drawdown against 10% of the
    average gross deployed, and (from the configured session count) the measured execution cost
    per round trip against twice the frozen model's cost for the same positions."""
    cum = peak = 0.0
    drawdown = 0.0
    gross_by_day = []
    positions = []
    for _day, ps in sessions_positions:
        gross_by_day.append(sum(p["notional"] for p in ps))
        cum += sum(p["net"] * p["notional"] for p in ps)
        peak = max(peak, cum)
        drawdown = max(drawdown, peak - cum)
        positions.extend(ps)
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


def run_look(auth, until=None):
    require(auth)
    protocol = auth.frozen.protocol
    plan = protocol["sequential_plan"]
    looks = plan["looks_sessions"]
    done = recorded_looks(auth)
    if done and done[-1]["look_decision"] != "continue":
        raise Refusal(f"the trial stopped at look {done[-1]['look']} ({done[-1]['look_decision']}); no further look")
    k = len(done) + 1
    if k > len(looks):
        raise Refusal("every planned look is recorded")
    start, sessions, holdings, excluded = collect(auth, until)
    info_days = information_sessions(sessions, holdings)
    n_k = looks[k - 1]
    if len(info_days) < n_k:
        raise Refusal(f"look {k} needs {n_k} counted long-short sessions; {len(info_days)} are complete")
    days = set(info_days[:n_k])
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
    d = design(protocol)
    decision = look_decision(k, stats["t_nw"], d["efficacy_z"], d["futility_z"], len(looks))
    shadow = [p for day, rows, ok, _ in sessions if ok and day in days for p in shadow_positions(day, rows)]
    shadow_daily = daily_values(shadow, "gross")
    receipt = {
        "schema": "news-reversal-look/1", "look": k, "planned_sessions": n_k, "information_fraction": n_k / looks[-1],
        "protocol_id": protocol["id"], "protocol_sha256": auth.frozen.sha256, "freeze_commit": auth.freeze_commit,
        "deployed_commit": auth.deployed_commit, "deployed_at": auth.deployed_at.isoformat(), "head": auth.head,
        "counted_start": start.isoformat(), "sessions_used": {"first": order[0], "last": order[-1], "count": len(order)},
        "excluded_sessions": dict(excluded),
        # key look_decision, not decision: blueprint JSON values under a "decision" key must be classified labels
        # (tests/test_blind_checkout.py)
        "primary": {"series": "gross long-short, equal-weight legs of >= 2 names (news_signal.daily_portfolios)",
                    **stats, "efficacy_boundary_z": d["efficacy_z"][k - 1], "futility_boundary_z": d["futility_z"][k - 1]},
        "look_decision": decision,
        "secondary_reported_not_tested": {
            "net_long_short": series_stats([net[x]["long_short"] for x in order], lags),
            "gross_long_leg": series_stats([gross[x]["long"] for x in order], lags),
            "gross_short_leg": series_stats([gross[x]["short"] for x in order], lags),
            "net_long_leg": series_stats([net[x]["long"] for x in order], lags),
            "net_short_leg": series_stats([net[x]["short"] for x in order], lags)},
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
    result = harm_check(per_day, protocol["harm_stops"])
    result.update(schema="news-reversal-monitor/1", protocol_sha256=auth.frozen.sha256, head=auth.head,
                  counted_start=start.isoformat() if start else None, excluded_sessions=dict(excluded),
                  computed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    out_dir = auth.state_root / "reversal-monitor"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).astimezone(sig.NY).date().isoformat()
    (out_dir / f"{stamp}.json").write_text(json.dumps(result, indent=1, sort_keys=True, default=str) + "\n")
    if apply and result["harm_stop"]:
        (auth.state_root / HALT_FILE).write_text(json.dumps({"reasons": result["reasons"], "at": result["computed_at"]}) + "\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("design")
    d.add_argument("--protocol", type=Path, default=PROTOCOL_PATH)
    d.add_argument("--out", type=Path)
    sub.add_parser("pins")
    for name in ("look", "monitor"):
        p = sub.add_parser(name)
        p.add_argument("--state", type=Path, default=DEFAULT_STATE)
        p.add_argument("--freeze-record", type=Path, default=FREEZE_RECORD_PATH)
        p.add_argument("--deployment-record", type=Path, default=DEPLOYMENT_RECORD_PATH)
        p.add_argument("--protocol-sha256")
        if name == "monitor":
            p.add_argument("--apply", action="store_true", help=f"write <state>/{HALT_FILE} when a harm stop fires")
    a = parser.parse_args(argv)
    if a.command == "design":
        result = design(json.loads(a.protocol.read_text()))
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
        result = run_look(auth) if a.command == "look" else run_monitor(auth, apply=a.apply)
    except Refusal as r:
        print(f"REFUSED: {r.reason}", file=sys.stderr)
        return 2
    print(json.dumps({k: result.get(k) for k in ("look", "look_decision", "harm_stop", "reasons")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
