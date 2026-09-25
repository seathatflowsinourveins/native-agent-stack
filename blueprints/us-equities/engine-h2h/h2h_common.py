"""Engine-independent parts of the Alpaca paper engine head-to-head.

Loads and validates the frozen order script, derives every price with Decimal
arithmetic, guards each engine's dedicated paper credential file, evaluates a
step's expectation against a normalized observation, and computes the
preregistered metrics and decision. Stdlib only: the three runners import it from
their own engine runtimes, and the unit tests import it with no engine installed.

Paper only. No function here contacts a broker; the credential loader reads one
private file through the adaptive-paper blueprint's fail-closed guard and returns
values that are never logged or written.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import sys
import time
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

HERE = Path(__file__).resolve().parent
SCRIPT_PATH = HERE / "order_script.json"
PROTOCOL_PATH = HERE / "protocol.json"
ADAPTIVE_PAPER = HERE.parent / "adaptive-paper"

SCRIPT_SCHEMA = "engine-h2h-order-script/v1"
ENGINES = ("nautilus", "lean", "lumibot")
INCUMBENT = "nautilus"
PAPER_BASE_URL = "https://paper-api.alpaca.markets"
KEY_ID_VARIABLE = "APCA_API_KEY_ID"
SECRET_KEY_VARIABLE = "APCA_API_SECRET_KEY"
BASE_URL_VARIABLE = "APCA_API_BASE_URL"
# Paper accounts already owned by other lanes (alpaca-paper(-1), paper-2..4).
_SHARED_ACCOUNT_NAME = re.compile(r"^alpaca-paper(-[1-4])?\.env$|paper-[1-4](?![0-9])")

STEP_KINDS = frozenset({"submit", "replace", "cancel", "cancel_if_open", "flatten", "await",
                        "kill", "stop", "restart", "reconcile", "drop_stream"})
PAPER_ONLY_STEP_KINDS = frozenset({"kill", "stop", "restart", "drop_stream"})
EXPECTATIONS = frozenset({"open", "filled", "canceled", "refused", "refused_or_rounded",
                          "canceled_or_refused", "entry_filled_legs_open", "legs_open", "flat",
                          "submitted", "adopted_once", "filled_once"})
ORDER_TYPES = frozenset({"limit", "market", "stop", "stop_limit", "trailing_stop"})
ORDER_CLASSES = frozenset({"simple", "bracket", "oto", "oco"})
TIME_IN_FORCE = frozenset({"day", "opg", "cls"})
NORMALIZED_STATES = frozenset({"submitted", "open", "partially_filled", "filled", "canceled",
                               "expired", "refused", "unknown"})

# Case outcome statuses. Only the first two count as coverage.
PASSED, DEVIATION = "passed", "passed_with_deviation"
REFUSED, UNSUPPORTED, FAILED = "refused_explicit", "unsupported", "failed"
NOT_RUN_OFFLINE, NOT_OBSERVABLE = "not_run_offline", "not_observable"
STATUSES = (PASSED, DEVIATION, REFUSED, UNSUPPORTED, FAILED, NOT_RUN_OFFLINE, NOT_OBSERVABLE)
COVERED = frozenset({PASSED, DEVIATION})
CORRECTNESS_FAILURES = ("reconciliation_mismatch", "duplicate_order", "orphan_order",
                        "unintended_execution", "fill_booking_mismatch")

# The offline backtest plan both backtesting engines share: LEAN's bundled SPY
# minute data (trade and quote bars, 04:00-20:00 ET) covers exactly these five
# sessions. The fault phase needs a live process and a broker; it is paper-only.
BACKTEST_PLAN = {
    "2013-10-07": ("extended_pre", "pre_open", "regular", "close", "reconcile"),
    "2013-10-08": ("pre_open", "regular", "close", "reconcile", "extended_post"),
    "2013-10-09": ("pre_open", "regular", "close", "reconcile"),
    "2013-10-10": ("pre_open", "regular", "close", "reconcile"),
    "2013-10-11": ("pre_open", "regular", "close", "reconcile"),
}


class H2HRefusal(RuntimeError):
    """A run was refused. The message is always a fixed reason code, never a
    value, a path or upstream exception text."""


# -- order script ---------------------------------------------------------------

def file_sha256(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_script(path=SCRIPT_PATH):
    script = json.loads(Path(path).read_text())
    validate_script(script)
    return script


def validate_script(script):
    """Structural validation; raises ValueError('script:<reason>')."""
    def bad(reason):
        raise ValueError("script:" + reason)
    if script.get("schema") != SCRIPT_SCHEMA:
        bad("schema")
    rules, constants, cases = script.get("price_rules", {}), script.get("constants", {}), script.get("cases", {})
    for name, rule in rules.items():
        if rule.get("side_of_book") not in ("bid", "ask") or rule.get("rounding") not in ("floor_cent", "ceil_cent"):
            bad("rule_" + name)
        Decimal(rule["multiplier"]), Decimal(rule.get("add", "0"))
    for phase, spec in script.get("phases", {}).items():
        if not re.fullmatch(r"\d\d:\d\d", spec.get("at_et", "")) or spec.get("session") not in ("regular", "extended"):
            bad("phase_" + phase)
        for case_id in spec.get("cases", []):
            if case_id not in cases:
                bad("phase_case_" + case_id)
    for case_id, case in cases.items():
        if not case.get("steps"):
            bad("steps_" + case_id)
        if "repeat" in case and case["repeat"] not in constants:
            bad("repeat_" + case_id)
        refs = set()
        for step in case["steps"]:
            kind = step.get("do")
            if kind not in STEP_KINDS:
                bad("step_kind_" + case_id)
            if kind in PAPER_ONLY_STEP_KINDS and not case.get("paper_only"):
                bad("paper_only_step_" + case_id)
            if "expect" in step and step["expect"] not in EXPECTATIONS:
                bad("expect_" + case_id)
            if kind == "submit":
                order = step.get("order", {})
                if (order.get("type") not in ORDER_TYPES or order.get("side") not in ("buy", "sell")
                        or order.get("tif") not in TIME_IN_FORCE
                        or order.get("class", "simple") not in ORDER_CLASSES):
                    bad("order_" + case_id)
                for key in ("limit", "stop", "take_profit", "stop_loss"):
                    if key in order and order[key] not in rules:
                        bad("order_rule_" + case_id)
                if "trail_percent" in order and order["trail_percent"] not in constants:
                    bad("order_trail_" + case_id)
                qty = order.get("qty")
                if not (isinstance(qty, int) and qty > 0) and qty not in constants:
                    bad("order_qty_" + case_id)
                refs.add(step["ref"])
            elif kind in ("replace", "cancel", "cancel_if_open", "await") and step.get("ref") not in refs:
                bad("step_ref_" + case_id)
    return script


def price(rule_name, bid, ask, script):
    """The deterministic price for one rule from a reference bid/ask (Decimal)."""
    rule = script["price_rules"][rule_name]
    base = Decimal(str(bid if rule["side_of_book"] == "bid" else ask))
    if not base.is_finite() or base <= 0:
        raise ValueError("invalid_reference_quote")
    raw = base * Decimal(rule["multiplier"])
    rounding = ROUND_FLOOR if rule["rounding"] == "floor_cent" else ROUND_CEILING
    return raw.quantize(Decimal("0.01"), rounding=rounding) + Decimal(rule.get("add", "0"))


def constant(value, script):
    return script["constants"][value] if isinstance(value, str) else value


def resolve_order(order, bid, ask, script):
    """A submit step's order with every rule and constant resolved (Decimal prices)."""
    out = {"class": order.get("class", "simple"), "type": order["type"], "side": order["side"],
           "qty": int(constant(order["qty"], script)), "tif": order["tif"],
           "extended_hours": bool(order.get("extended_hours", False))}
    for key in ("limit", "stop", "take_profit", "stop_loss"):
        if key in order:
            out[key] = price(order[key], bid, ask, script)
    if "trail_percent" in order:
        out["trail_percent"] = Decimal(constant(order["trail_percent"], script))
    return out


def phase_steps(script, phase, *, offline):
    """(case_id, repeat_index, step_index, step) in execution order; paper-only
    cases are skipped offline (the caller records them as not_run_offline)."""
    for case_id in script["phases"][phase]["cases"]:
        case = script["cases"][case_id]
        if offline and case.get("paper_only"):
            continue
        repeats = int(constant(case["repeat"], script)) if "repeat" in case else 1
        for repeat in range(repeats):
            for index, step in enumerate(case["steps"]):
                yield case_id, repeat, index, step


def evaluate(expect, observed, *, requested_price=None):
    """(satisfied, final, deviation, correctness_flag) for one step.

    ``observed`` is a normalized view the runner builds from its engine's own order
    state: {"state", "filled_qty", "qty", "legs_open", "position", "open_orders",
    "accepted_price", "refusal": "engine" | "broker" | None}. ``final`` means the
    observation cannot improve by waiting; ``correctness_flag`` names a
    CORRECTNESS_FAILURES entry when the observation is itself a correctness failure."""
    state = observed.get("state", "unknown")
    if state not in NORMALIZED_STATES:
        raise ValueError("unknown_normalized_state")
    filled = Decimal(str(observed.get("filled_qty") or 0))
    if expect == "submitted":
        return state in ("submitted", "open", "partially_filled", "filled"), state in ("refused", "canceled", "expired"), None, None
    if expect == "open":
        if state == "open" and filled == 0:
            return True, True, None, None
        if state in ("filled", "partially_filled") or filled > 0:
            return False, True, None, "unintended_execution"
        return False, state in ("canceled", "expired", "refused"), None, None
    if expect in ("filled", "filled_once"):
        if state == "filled":
            return True, True, None, None
        return False, state in ("canceled", "expired", "refused"), None, None
    if expect == "canceled":
        if state == "canceled" and filled == 0:
            return True, True, None, None
        if filled > 0:
            return False, True, None, "unintended_execution"
        return False, state in ("expired", "refused"), None, None
    if expect in ("refused", "canceled_or_refused"):
        ok = state == "refused" or (expect == "canceled_or_refused" and state == "canceled")
        if filled > 0:
            return False, True, None, "unintended_execution"
        return ok, ok, None, None
    if expect == "refused_or_rounded":
        if filled > 0:
            return False, True, None, "unintended_execution"
        if state == "refused":
            return True, True, None, None
        accepted = observed.get("accepted_price")
        if state == "open" and accepted is not None and requested_price is not None:
            accepted = Decimal(str(accepted))
            if accepted != requested_price and accepted == accepted.quantize(Decimal("0.01")):
                return True, True, "rounded_in_engine_state", None
        return False, False, None, None
    if expect == "entry_filled_legs_open":
        need = int(observed.get("legs_expected", 1))
        return state == "filled" and int(observed.get("legs_open", 0)) >= need, state in ("canceled", "refused"), None, None
    if expect == "legs_open":
        return int(observed.get("legs_open", 0)) >= 2, state in ("canceled", "refused", "filled"), None, None
    if expect == "flat":
        return (Decimal(str(observed.get("position", 0))) == 0 and int(observed.get("open_orders", 0)) == 0), False, None, None
    if expect == "adopted_once":
        return observed.get("adopted") == 1, observed.get("adopted", 0) > 1, None, (
            "duplicate_order" if observed.get("adopted", 0) > 1 else None)
    raise ValueError("unknown_expectation")


# -- step machine (Python engines; LEAN's C# algorithm mirrors it) ----------------

class Unsupported(Exception):
    """The engine offers no API for this step; nothing was submitted."""


class NoQuote(Exception):
    """No usable reference quote yet; the step is deferred (at most 60 s)."""


class Work:
    __slots__ = ("run", "phase", "case", "session", "repeat", "index", "step")

    def __init__(self, run, phase, case, session, repeat, index, step):
        self.run, self.phase, self.case, self.session = run, phase, case, session
        self.repeat, self.index, self.step = repeat, index, step

    @property
    def instance(self):
        return f"{self.run}|{self.phase}|{self.case}|{self.repeat}"

    @property
    def tag(self):
        return f"h2h:{self.phase}:{self.case}:{self.repeat}:{self.index}"


class StepMachine:
    """Runs script phases through an engine's ``ops`` object, one step at a time.

    ``ops`` supplies: now() (tz-aware engine clock), quote() -> (bid, ask) or raises
    NoQuote, position(), open_orders(), submit(tag, order) -> handle or raises
    Unsupported, replace(handle, price), cancel(handle), is_open(handle),
    flatten(session), cleanup(session), observe(handle) -> normalized dict (see
    evaluate()), and fault_point(kind, tag) for the paper orchestrator."""

    def __init__(self, script, ops, journal, *, offline):
        self.script, self.ops, self.journal, self.offline = script, ops, journal, offline
        self.queue, self.active, self.active_since, self.started = [], None, None, False
        self.refs, self.aborted, self.results, self.runs = {}, set(), {}, 0

    def enqueue_phase(self, phase):
        self.runs += 1
        session = self.script["phases"][phase]["session"]
        for case_id in self.script["phases"][phase]["cases"]:
            case = self.script["cases"][case_id]
            if self.offline and case.get("paper_only"):
                self.result(case_id, NOT_RUN_OFFLINE, "fault case needs a live process and a broker")
                continue
            repeats = int(constant(case["repeat"], self.script)) if "repeat" in case else 1
            for repeat in range(repeats):
                for index, step in enumerate(case["steps"]):
                    self.queue.append(Work(self.runs, phase, case_id, session, repeat, index, step))
        self.journal.event("phase_enqueued", phase=phase, run=self.runs, queued=len(self.queue))

    def idle(self):
        return self.active is None and not self.queue

    def _key(self, work):
        return f"{work.instance}|{work.step['ref']}" if "ref" in work.step else None

    def advance(self):
        while True:
            if self.active is None:
                if not self.queue:
                    return
                self.active = self.queue.pop(0)
                if self.active.instance in self.aborted:
                    self.active = None
                    continue
                self.active_since, self.started = self.ops.now(), False
            work = self.active
            if not self.started:
                self.started = True
                case = self.script["cases"][work.case]
                if work.index == 0 and "requires_position" in case and self.ops.position() != case["requires_position"]:
                    self._finish(False, FAILED, f"precondition_position:{self.ops.position()}")
                    continue
                try:
                    self._execute(work)
                except NoQuote:
                    self.started = False
                    if self._elapsed() <= 60:
                        return
                    self._finish(False, FAILED, "no_quote")
                    continue
                except Unsupported as reason:
                    self._finish(False, UNSUPPORTED, str(reason))
                    continue
            done, ok, status, detail = self._check(work)
            if not done and self._elapsed() <= work.step.get("timeout_s", 60):
                return
            if not done:
                ok, status, detail = False, FAILED, "timeout:" + str(detail or self._observe(work).get("state"))
            self._finish(ok, status, detail)

    def _elapsed(self):
        return (self.ops.now() - self.active_since).total_seconds()

    def _observe(self, work):
        key = self._key(work)
        return self.ops.observe(self.refs[key]["handle"]) if key in self.refs else {"state": "unknown"}

    def _execute(self, work):
        step, kind, key = work.step, work.step["do"], self._key(work)
        if kind == "submit":
            bid, ask = self.ops.quote()
            order = resolve_order(step["order"], bid, ask, self.script)
            handle = self.ops.submit(work.tag, order)
            self.refs[key] = {"handle": handle, "requested": order.get("limit"), "order": order}
            self.journal.event("submit", tag=work.tag, order=order)
        elif kind == "replace":
            bid, ask = self.ops.quote()
            new = price(step["limit"], bid, ask, self.script)
            self.refs[key]["requested"] = new
            self.ops.replace(self.refs[key]["handle"], new)
            self.journal.event("replace", tag=work.tag, limit=new)
        elif kind in ("cancel", "cancel_if_open"):
            ref = self.refs.get(key)
            if ref is not None and (kind == "cancel" or self.ops.is_open(ref["handle"])):
                self.ops.cancel(ref["handle"])
                self.journal.event("cancel", tag=work.tag)
        elif kind == "flatten":
            self.ops.flatten(work.session)
            self.journal.event("flatten", tag=work.tag)
        elif kind in PAPER_ONLY_STEP_KINDS:
            self.ops.fault_point(kind, work.tag)
            self.journal.event("fault_point", tag=work.tag, kind=kind)

    def _check(self, work):
        kind, expect = work.step["do"], work.step.get("expect")
        if kind in ("kill", "stop"):
            return False, False, None, "awaiting_orchestrator"
        if expect is None:
            return True, True, None, None
        if expect == "flat":
            position, open_orders = self.ops.position(), self.ops.open_orders()
            flat = position == 0 and open_orders == 0
            return flat, flat, None, None if flat else f"position={position};open_orders={open_orders}"
        key = self._key(work)
        if kind == "cancel_if_open" and key not in self.refs:
            return True, True, None, None
        observed = self._observe(work)
        requested = self.refs.get(key, {}).get("requested")
        if kind == "replace":
            # A replace passes only when the new price is live in the engine's own order state.
            if observed.get("modify_rejected"):
                return True, False, REFUSED, str(observed["modify_rejected"])
            accepted, state = observed.get("accepted_price"), observed.get("state")
            if state == "open" and accepted is not None and Decimal(str(accepted)) == requested:
                return True, True, None, None
            if state in ("filled", "partially_filled", "canceled", "expired", "refused"):
                return True, False, FAILED, state
            return False, False, None, None
        satisfied, final, deviation, flag = evaluate(expect, observed, requested_price=requested)
        order = self.refs.get(key, {}).get("order", {})
        if satisfied and order.get("tif") in ("opg", "cls") and observed.get("filled_before_auction"):
            deviation = "auction_time_not_modelled"
        if satisfied:
            return True, True, DEVIATION if deviation else None, deviation or observed.get("detail")
        if flag:
            return True, False, FAILED, flag
        if final:
            refused = observed.get("state") == "refused" and expect not in ("refused", "canceled_or_refused")
            return True, False, REFUSED if refused else FAILED, observed.get("detail") or observed.get("state")
        return False, False, None, None

    def _finish(self, ok, status, detail):
        work, self.active = self.active, None
        last = work.index == len(self.script["cases"][work.case]["steps"]) - 1
        self.journal.event("step_done", phase=work.phase, case=work.case, repeat=work.repeat, step=work.index,
                           ok=ok, status=status, detail=detail)
        if not ok:
            self.aborted.add(work.instance)
            self.ops.cleanup(work.session)
            self.result(work.case, status or FAILED, detail)
        elif last or status == DEVIATION:
            self.result(work.case, status or PASSED, detail)

    def result(self, case_id, status, detail=None):
        previous = self.results.get(case_id)
        if previous is None or STATUSES.index(status) > STATUSES.index(previous["status"]):
            self.results[case_id] = {"status": status, "detail": detail}
        self.journal.event("case_result", case=case_id, status=status, detail=detail)


# -- dedicated paper credentials -------------------------------------------------

def env_file_name(engine):
    if engine not in ENGINES:
        raise H2HRefusal("h2h:unknown_engine")
    return f"alpaca-paper-h2h-{engine}.env"


def check_env_file(engine, path):
    """Name-level refusal: the file must be exactly this engine's dedicated file."""
    expected = env_file_name(engine)
    if path is None:
        raise H2HRefusal("h2h:env_file_required")
    name = Path(path).name
    if name == expected:
        return
    if _SHARED_ACCOUNT_NAME.search(name):
        raise H2HRefusal("h2h:forbidden_shared_paper_account")
    if name in {env_file_name(other) for other in ENGINES}:
        raise H2HRefusal("h2h:another_engines_paper_account")
    raise H2HRefusal("h2h:not_the_dedicated_env_file")


def require_paper_base_url(value):
    if value is None or (isinstance(value, str) and value.rstrip("/") == PAPER_BASE_URL):
        return PAPER_BASE_URL
    raise H2HRefusal("h2h:not_paper_host")


def _adaptive_paper_module(name):
    """Import one stdlib-only module of the adaptive-paper blueprint by path, so the
    guard cannot drift from the engine's own loader."""
    key = "h2h_" + name
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, ADAPTIVE_PAPER / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


def load_paper_env(engine, path, *, environ=None):
    """The dedicated file's key pair, read once through credential_guard.open_verified
    (0600, owner, no symlink component, outside every Git worktree). Refuses any
    base URL other than the paper host, in the file or in the process environment.
    Returns {"key_id", "secret", "base_url"}; callers must never log the values."""
    check_env_file(engine, path)
    environ = os.environ if environ is None else environ
    require_paper_base_url(environ.get(BASE_URL_VARIABLE))
    guard = _adaptive_paper_module("credential_guard")
    reason = None
    try:
        with guard.open_verified(os.fspath(path), follow_symlinks=False) as handle:
            raw = handle.read(guard.MAX_CREDENTIAL_BYTES + 1)
    except guard.CredentialGuardError as error:
        reason = str(error)
    if reason is not None:
        raise H2HRefusal(reason)
    if len(raw) > guard.MAX_CREDENTIAL_BYTES:
        raise H2HRefusal(guard.REASON_SIZE)
    if not raw.isascii():
        raise H2HRefusal(guard.REASON_ENCODING)
    values, base_url = {}, None
    for line in raw.decode("ascii").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.removeprefix("export ").split("=", 1)
        name = name.strip()
        if name in (KEY_ID_VARIABLE, SECRET_KEY_VARIABLE, BASE_URL_VARIABLE):
            parsed = shlex.split(value, comments=True)
            if len(parsed) != 1 or not parsed[0]:
                raise H2HRefusal("h2h:invalid_credential_line")
            if name == BASE_URL_VARIABLE:
                base_url = parsed[0]
            else:
                values[name] = parsed[0]
    if set(values) != {KEY_ID_VARIABLE, SECRET_KEY_VARIABLE}:
        raise H2HRefusal("h2h:missing_paper_credentials")
    return {"key_id": values[KEY_ID_VARIABLE], "secret": values[SECRET_KEY_VARIABLE],
            "base_url": require_paper_base_url(base_url)}


def account_fingerprint(account_number):
    return hashlib.sha256(("alpaca-paper-h2h:" + str(account_number)).encode()).hexdigest()


def assert_distinct_accounts(fingerprints, *, forbidden=()):
    """Every engine on its own paper account, never one of the other lanes'."""
    seen = {}
    for engine, fingerprint in fingerprints.items():
        if fingerprint in forbidden:
            raise H2HRefusal("h2h:forbidden_shared_paper_account")
        if fingerprint in seen:
            raise H2HRefusal("h2h:paper_account_shared_between_engines")
        seen[fingerprint] = engine


def scrubbed_environment(environ=None):
    """A child environment without any credential or vendor-telemetry variable."""
    environ = dict(os.environ if environ is None else environ)
    for name in list(environ):
        if (name.startswith(("APCA_", "ALPACA_", "LUMIWEALTH_", "QC_", "QUANTCONNECT_"))
                or name in ("PAPER", "LIVE_CONFIG", "BROKER")):
            environ.pop(name)
    return environ


# -- journal ----------------------------------------------------------------------

class Journal:
    """Append-only JSON lines: every event carries wall and monotonic nanoseconds (the
    wall clock is what paper latency uses; the host clock offset is recorded per session)."""

    def __init__(self, path, *, engine, mode, script_sha256):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a", buffering=1)
        self.event("run_start", engine=engine, mode=mode, script_sha256=script_sha256)

    def event(self, kind, **fields):
        row = {"kind": kind, "t_wall_ns": time.time_ns(), "t_mono_ns": time.monotonic_ns(), **fields}
        self.stream.write(json.dumps(row, default=str, sort_keys=True) + "\n")
        return row

    def close(self):
        self.stream.close()


# -- metrics and decision ----------------------------------------------------------

def percentile(values, q):
    """Nearest-rank percentile (q in (0, 100]); None for no values."""
    ordered = sorted(values)
    if not ordered:
        return None
    rank = max(1, -(-len(ordered) * q // 100))
    return ordered[int(rank) - 1]


def reconcile(engine_orders, broker_orders, *, engine_position, broker_position):
    """Compare one engine's final order view with the independent broker observer's.

    Both order views map broker order id -> {"status", "filled_qty", "intent"} where
    ``intent`` is the script step key (case/repeat/step) the order serves. Returns
    counts for mismatches (status or filled quantity), duplicates (more than one
    broker order for one intent) and orphans (broker orders the engine does not know)."""
    mismatches = sum(1 for oid, row in broker_orders.items() if oid in engine_orders and (
        engine_orders[oid]["status"] != row["status"]
        or Decimal(str(engine_orders[oid]["filled_qty"])) != Decimal(str(row["filled_qty"]))))
    mismatches += int(Decimal(str(engine_position)) != Decimal(str(broker_position)))
    intents = {}
    for row in broker_orders.values():
        if row.get("intent") is not None:
            intents[row["intent"]] = intents.get(row["intent"], 0) + 1
    duplicates = sum(count - 1 for count in intents.values() if count > 1)
    orphans = sum(1 for oid in broker_orders if oid not in engine_orders)
    return {"reconciliation_mismatch": mismatches, "duplicate_order": duplicates, "orphan_order": orphans}


def finalize_offline_results(results, script, *, partial_fills_seen):
    """The protocol's offline bookkeeping: paper-only cases are not_run_offline, and the
    observational R10 is not_observable unless a partial fill occurred somewhere in the run."""
    results = {case: dict(value) for case, value in results.items()}
    for case_id, case in script["cases"].items():
        if case.get("paper_only") and case_id not in results:
            results[case_id] = {"status": NOT_RUN_OFFLINE, "detail": "fault case needs a live process and a broker"}
    if not partial_fills_seen and results.get("R10", {}).get("status") in COVERED:
        results["R10"] = {"status": NOT_OBSERVABLE, "detail": "no partial fill occurred in this run"}
    return results


def summarize(results, *, script):
    """Coverage over the script's cases: passed cases and those covered without glue."""
    counted = [cid for cid in script["cases"] if cid != "E01"]
    covered = [cid for cid in counted if results.get(cid, {}).get("status") in COVERED]
    no_glue = [cid for cid in covered if not results[cid].get("glue_required")]
    return {"cases": len(counted), "covered": len(covered), "covered_without_glue": len(no_glue),
            "by_status": {status: sorted(c for c in counted if results.get(c, {}).get("status") == status)
                          for status in STATUSES}}


def decide(summaries, protocol):
    """The preregistered rule: a challenger wins only with zero correctness failures,
    coverage at least the incumbent's, and each p95 latency within the protocol's
    ratio of the incumbent's. Incomplete data is inconclusive, never a win."""
    rule = protocol["decision_rule"]
    incumbent = summaries.get(rule["incumbent"])
    if incumbent is None or not incumbent.get("complete"):
        return {"verdict": "inconclusive", "reason": "incumbent_incomplete", "challengers": {}}
    ratio = Decimal(rule["max_p95_ratio"])
    challengers = {}
    for engine, summary in summaries.items():
        if engine == rule["incumbent"]:
            continue
        reasons = []
        if not summary.get("complete"):
            reasons.append("incomplete")
        if sum(summary.get("correctness_failures", {}).values()) != 0:
            reasons.append("correctness_failures")
        if summary.get("covered", -1) < incumbent.get("covered", 0):
            reasons.append("coverage_below_incumbent")
        for metric in rule["p95_metrics"]:
            mine, theirs = summary.get("latency", {}).get(metric), incumbent.get("latency", {}).get(metric)
            if mine is None or theirs is None:
                reasons.append(metric + ":missing")
            elif Decimal(str(mine)) > Decimal(str(theirs)) * ratio:
                reasons.append(metric + ":over_ratio")
        challengers[engine] = {"wins": not reasons, "reasons": reasons}
    winners = sorted((e for e, r in challengers.items() if r["wins"]),
                     key=lambda e: (-summaries[e]["covered"], summaries[e]["latency"][rule["p95_metrics"][0]]))
    if not winners:
        verdict = "incumbent_retained"
    elif len(winners) > 1 and (summaries[winners[0]]["covered"], summaries[winners[0]]["latency"][rule["p95_metrics"][0]]) == (
            summaries[winners[1]]["covered"], summaries[winners[1]]["latency"][rule["p95_metrics"][0]]):
        verdict = "tie_requires_decision_record"
    else:
        verdict = "challenger_wins:" + winners[0]
    return {"verdict": verdict, "challengers": challengers,
            "incumbent_correctness_failures": sum(incumbent.get("correctness_failures", {}).values())}


def glue_lines(paths):
    """Non-blank, non-comment lines in the files we maintain for one engine path."""
    total = 0
    for path in paths:
        comment = "//" if str(path).endswith(".cs") else "#"
        for line in Path(path).read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith(comment):
                total += 1
    return total
