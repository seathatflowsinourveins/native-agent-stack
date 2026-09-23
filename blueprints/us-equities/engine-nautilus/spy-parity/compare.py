#!/usr/bin/env python3
"""Independent Decimal comparator: SPY parity receipt against the LEAN oracle.

Reads the replay receipt and the dated LEAN receipt, compares every reviewed
economic key for the receipt's own case with ``Decimal`` arithmetic only, prints
one PASS/FAIL line per check and a machine-readable verdict, and exits nonzero on
any deviation outside the tolerance sheet. Pure standard library: it reproduces
the comparison from retained outputs without any engine or model call.

Attribution is measured, never taken on the receipt's word. A fill-price
deviation may be labelled ``market_on_open_proxy`` only when the converted bars
show that the native fill equals that session's first-bar close while the oracle
fill equals that same bar's open. A cash deviation may be labelled only for the
part the attributed fill-price deltas (and, for the native balance, the
unposted distribution total) explain exactly. Any residue outside tolerance stays
an unattributed FAIL, and a named mapping must carry status ``unsupported`` in
the manifest the receipt was bound to or the attribution is rejected.

Under mapping manifest v2 (``schema_version`` 2) the two formerly unsupported
rows are ``preregistered``, so the bound manifest declares no unsupported row
for ``one_zero`` and no failure can be attributed: any failing check is FAIL.
The v2 comparison adds the preregistered acceptance checks: the native OCO pairs
(count, submission instant, trigger prices from the decision bar's close, legs
accepted, one full fill, one sibling cancel at the fill instant, no denial,
rejection or callback failure), the per-event ``moo_proxy_no_gap`` and
``moo_proxy_not_open`` checks against the converted bars, the ERROR-level engine
log scan, and the DistributionModule's emissions, acknowledgements and reported
``AccountState`` rows. Engine-posted distributions are part of native cash.

The v2 preconditions are checks too, because the sealed verdict rule requires
"every check above" to pass: a retained independent review of exactly the files
that ran, completed before the run, and, because earlier v2 replays ran before
any review, either no unreviewed earlier replay or the gate owner's retained
acceptance of deviation ``first_v2_run_preceded_review``
(``deviation-acceptance-v2.json``), hash-bound to the reviewed harness files and
dated before the run, plus the replay history re-hashed at comparison time
(``precondition_review``); the sealed
manifest, tolerance sheet and five frozen inputs at run time and, with
``--lean-data`` only, re-hashed at comparison time (``precondition_hashes``);
the engine pin and the run's isolation (``precondition_engine``). An unmet
precondition is a FAIL even when every execution check passes; the verdict
reports ``preregistration_qualifying`` and the execution checks separately.
Under v2 a skipped check is also FAIL (PREREGISTRATION-v2.md lists "any skipped
check" as a falsifier), and two-run determinism is recomputed from the runs'
normalized hashes rather than read from the receipt's boolean. A v2 receipt is
refused unless it is bound to the sealed manifest and preregistration by their
sha256 pinned below. The OCO structure is judged from the engine's own order
records (``engine_at_accept``/``engine_final``), and the submission instant from
the engine clock and each leg's OrderSubmitted/OrderAccepted ``ts_event``, never
from the harness's submission strings.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parent
REQUIRED_LIMITS = ("event_seconds_abs", "fill_quantity_abs", "fill_price_usd_abs", "fees_usd_abs",
                   "dividend_usd_abs", "cash_usd_abs", "end_cash_usd_abs", "final_quantity_abs")
MARKET_ON_OPEN = "market_on_open_proxy"
DISTRIBUTIONS = "distributions_and_cash"
MANIFEST_V1 = "mapping-manifest.json"
TICK = Decimal("0.0001")
V2_CONFIGURATION_FIELDS = ("seed", "account_type", "use_random_ids", "fill_model", "fee_model",
                           "window", "oms_type", "latency_model", "bar_execution",
                           "bar_adaptive_high_low_ordering", "reject_stop_orders",
                           "support_contingent_orders", "frozen_account")
# The sealed v2 preregistration. A v2 receipt bound to any other file is refused.
SEALED_V2_MANIFEST_SHA256 = "1b821d7ba42ea6121002a26a5082df08ed7a79f9a50b2edc9959503e1088ac67"
SEALED_V2_PREREGISTRATION_SHA256 = "4393a1b7d896b2f49c4091c18701bd08cfc72a8d313f0ad2a628e91db26d6f0c"
REVIEW_RECORD_SCHEMA = "spy-parity-v2-harness-review/1"
REVIEWED_HARNESS_FILES = ("convert.py", "fixture_strategy.py", "distribution_module.py", "run.py",
                          "compare.py")
# The documented bwrap replay clears the environment and sets exactly these
# (PWD is added by the shell-less exec).
ISOLATED_ENVIRONMENT = {"LANG", "PATH", "PYTHONDONTWRITEBYTECODE", "OPENBLAS_NUM_THREADS",
                        "OMP_NUM_THREADS", "PWD"}
# Values the documented bwrap replay sets; PWD is not constrained.
ISOLATED_ENVIRONMENT_VALUES = {"LANG": "C.UTF-8", "PATH": "/usr/bin:/bin",
                               "PYTHONDONTWRITEBYTECODE": "1", "OPENBLAS_NUM_THREADS": "1",
                               "OMP_NUM_THREADS": "1"}
# /proc/self/uid_map of the initial user namespace; a bwrap user namespace differs.
INITIAL_USER_NAMESPACE_UID_MAP = ["0", "0", "4294967295"]
PRECONDITION_PREFIX = "precondition_"
REPLAY_HISTORY = "replay-history-v2.json"
# The gate owner's acceptance of the declared deviation that the first v2 runs
# preceded any review. The harness never writes this file.
DEVIATION_ACCEPTANCE = "deviation-acceptance-v2.json"
DEVIATION_ACCEPTANCE_SCHEMA_VERSION = 1
DEVIATION_ACCEPTANCE_FIELDS = ("schema_version", "deviation_id", "accepted_by", "accepted_utc",
                               "reviewed_harness_local_source_sha256", "statement")
ACCEPTED_DEVIATION = "first_v2_run_preceded_review"
SHA256_HEX = frozenset("0123456789abcdef")
V2_SOURCES =("convert.py", "fixture_strategy.py", "distribution_module.py", "run.py",
              "compare.py", "mapping-manifest.json", "mapping-manifest-v2.json", "tolerances.json")


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _decimal(value) -> Decimal:
    return Decimal(str(value).split()[0].replace(",", "").replace("_", ""))


def _int(value, code: str) -> int:
    """Strict integer projection: a fractional value is refused, not truncated."""
    found = _decimal(value)
    if found != found.to_integral_value():
        raise ValueError(code + ":" + str(value))
    return int(found)


def oracle_case(oracle: dict, case_id: str) -> dict:
    """Project the dated LEAN receipt onto the reviewed economic keys.

    The LEAN receipt stores fill instants and quantities as decimal strings such
    as ``"1577977200.0"`` and ``"304.0"``; both are projected strictly.
    """
    cases = [c for c in oracle.get("cases", []) if c.get("id") == case_id]
    if len(cases) != 1:
        raise ValueError("oracle_case_not_found:" + case_id)
    case = cases[0]
    intents = [{"utc_seconds": _int(i["utc_seconds"], "non_integral_intent_time"),
                "quantity": _int(i["quantity"], "non_integral_intent_quantity"),
                "reason": i.get("reason")} for i in case["intents"]]
    fills = [{"utc_seconds": _int(f["time"], "non_integral_fill_time"),
              "quantity": _int(f["fillQuantity"], "non_integral_fill_quantity"),
              "price": _decimal(f["fillPrice"]), "fee": _decimal(f["orderFeeAmount"])}
             for f in case["fills"]]
    projected = {
        "id": case_id, "intents": intents, "fills": fills,
        "fees_usd": _decimal(case["fees_usd"]),
        "dividends_usd": _decimal(case["dividends_usd"]),
        "end_cash_usd": _decimal(case["end_cash_usd"]),
        "final_quantity": _int(case["final_quantity"], "non_integral_final_quantity"),
        "fill_count": _int(case["fill_count"], "non_integral_fill_count"),
    }
    if len(fills) != projected["fill_count"]:
        raise ValueError("oracle_fill_count_inconsistent:" + case_id)
    return projected


def receipt_case(receipt: dict) -> dict:
    return {
        "case": receipt["case"],
        "initial_cash_usd": _decimal(receipt["case_configuration"]["initial_cash_usd"]),
        "intents": [{"utc_seconds": _int(i["utc_seconds"], "non_integral_receipt_intent_time"),
                     "quantity": _int(i["quantity"], "non_integral_receipt_intent_quantity"),
                     "reason": i.get("reason")} for i in receipt["intents"]],
        "fills": [{"utc_seconds": _int(f["utc_seconds"], "non_integral_receipt_fill_time"),
                   "quantity": _int(f["quantity"], "non_integral_receipt_fill_quantity"),
                   "price": _decimal(f["price"]), "fee": _decimal(f["fee"])}
                  for f in receipt["fills"]],
        "fees_usd": _decimal(receipt["fees_usd"]),
        "dividends_usd": _decimal(receipt["dividend_cash_usd"]),
        "end_cash_usd": _decimal(receipt["reconciled_end_cash_usd"]),
        "native_end_cash_usd": _decimal(receipt["native_end_cash_usd"]),
        "final_quantity": _int(receipt["final_quantity"], "non_integral_final_quantity"),
        "cash_ledger": receipt.get("cash_ledger", []),
        "distribution_ledger": receipt.get("distribution_ledger", []),
        "two_run_records_equal": bool(receipt.get("two_run_records_equal", False)),
    }


def first_bars_by_instant(rows) -> dict:
    """Map each session's first converted bar to the UTC second it completes."""
    first = {}
    for row in rows:
        first.setdefault(row["session_date"], row)
    return {row["ts_event_ns"] // 10 ** 9: row for row in first.values()}


def serialize_rows(rows) -> str:
    """Reproduce run.py's own serialization so the digest is comparable."""
    return json.dumps(rows, indent=2, sort_keys=True, default=str) + "\n"


def _convert_module():
    spec = importlib.util.spec_from_file_location("spy_parity_convert", SOURCE / "convert.py")
    convert = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(convert)
    return convert


def load_bars(bars_path, lean_data, receipt: dict, manifest: dict):
    """Converted rows, either retained from the run or re-derived from the data.

    Either way the rows are hash-bound to the digest the receipt recorded, and a
    re-derivation first verifies the five frozen LEAN input hashes. Declared
    short sessions come from the hash-bound manifest, never from the receipt.
    """
    expected = receipt["attribution_evidence"]["converted_rows_sha256"]
    if bars_path is not None:
        blob = Path(bars_path).read_bytes()
        if hashlib.sha256(blob).hexdigest() != expected:
            raise ValueError("converted_rows_sha256_mismatch")
        return json.loads(blob.decode("utf-8"))
    if lean_data is None:
        return None
    convert = _convert_module()
    observed = convert.verify_inputs(lean_data)
    if observed != receipt["inputs"]["sha256"]:
        raise ValueError("lean_input_sha256_mismatch")
    window = receipt["case_configuration"]["window"]
    short = known_short_sessions(manifest)
    rows = convert.convert(lean_data, window["symbol"], window["start"], window["end"], short)["rows"]
    if hashlib.sha256(serialize_rows(rows).encode("utf-8")).hexdigest() != expected:
        raise ValueError("rederived_rows_sha256_mismatch")
    return rows


def known_short_sessions(manifest: dict) -> dict:
    row = next(r for r in manifest["mappings"] if r["id"] == "sessions_and_time")
    return row["known_short_sessions"]


def check_local_sources(receipt: dict, source_dir=None) -> None:
    """Every harness file the receipt hashed must still be that file on disk."""
    base = Path(source_dir or SOURCE)
    for name, recorded in sorted(receipt.get("local_source_sha256", {}).items()):
        path = base / name
        if not path.is_file():
            raise ValueError("local_source_missing:" + name)
        if digest(path) != recorded:
            raise ValueError("local_source_sha256_mismatch:" + name)


def is_v2(manifest) -> bool:
    return bool(manifest) and manifest.get("schema_version") == 2


def effective_manifest(v2: dict, v1: dict) -> dict:
    """v2 rows plus the v1 rows v2 declares carried unchanged, by id."""
    carried = set(v2["carried_unchanged_from_v1"])
    rows = [row for row in v1["mappings"] if row["id"] in carried]
    if sorted(row["id"] for row in rows) != sorted(carried):
        raise ValueError("carried_v1_rows_missing")
    if carried & {row["id"] for row in v2["mappings"]}:
        raise ValueError("carried_rows_overlap_v2")
    return {**v2, "mappings": rows + list(v2["mappings"])}


def load_effective_v2(v2: dict, manifest_dir: Path) -> dict:
    """Check the superseded v1 file against v2's record of it, then merge."""
    v1_path = Path(manifest_dir) / MANIFEST_V1
    if digest(v1_path) != v2["supersedes"]["sha256"]:
        raise ValueError("superseded_manifest_sha256_mismatch")
    return effective_manifest(v2, json.loads(v1_path.read_text()))


def manifest_evidence_class(manifest: dict) -> str:
    """v2 annotates the class ('HIST (for the future replay); ...'); use its token."""
    value = manifest["evidence_class"]
    return value.split()[0] if is_v2(manifest) else value


def check_case_configuration(receipt: dict, manifest: dict, plan: dict) -> None:
    """Bind the run's configuration to the pinned plan and the preregistered manifest.

    Numbers the frozen plan owns are compared against the plan; choices the plan
    does not express (seed, account type, identity generation, window) are
    compared against the manifest's preregistered ``case_configuration``.
    """
    configuration = receipt["case_configuration"]
    declared = manifest["case_configuration"]
    if receipt["case"] != declared["case"]:
        raise ValueError("case_disagrees_with_manifest:" + receipt["case"])
    if receipt["frozen_plan"]["sha256"] != manifest["oracle"]["plan_sha256"]:
        raise ValueError("receipt_plan_sha256_disagrees_with_manifest")
    spec = [c for c in plan["cases"] if c["id"] == receipt["case"]]
    if len(spec) != 1:
        raise ValueError("plan_case_not_found:" + receipt["case"])
    spec = spec[0]
    for field, wanted in (("initial_cash_usd", plan["initial_cash_usd"]),
                          ("sizing_buffer", plan["requested_target_sizing_multiplier"]),
                          ("target", spec["target"]), ("fee_usd", spec["fee_usd"]),
                          ("slippage", spec["slippage"])):
        if _decimal(configuration[field]) != _decimal(wanted):
            raise ValueError("case_configuration_disagrees_with_plan:" + field)
    fields = V2_CONFIGURATION_FIELDS if is_v2(manifest) else \
        ("seed", "account_type", "use_random_ids", "fill_model", "fee_model", "window")
    for field in fields:
        if configuration.get(field) != declared[field]:
            raise ValueError("case_configuration_disagrees_with_manifest:" + field)
    if is_v2(manifest):
        modules = configuration.get("venue_modules")
        if (not isinstance(modules, list) or len(modules) != 1 or len(declared["venue_modules"]) != 1
                or not declared["venue_modules"][0].startswith(str(modules[0]) + " ")):
            raise ValueError("case_configuration_disagrees_with_manifest:venue_modules")


def bind(receipt: dict, tolerances_path: Path, manifest_path: Path, oracle_path=None,
         plan_path=None, source_dir=None) -> tuple:
    """Refuse a comparison whose inputs or configuration are not the run's."""
    tolerances = json.loads(Path(tolerances_path).read_text())
    manifest = json.loads(Path(manifest_path).read_text())
    if digest(tolerances_path) != receipt["tolerances"]["sha256"]:
        raise ValueError("tolerances_sha256_mismatch")
    if digest(manifest_path) != receipt["mapping_manifest"]["sha256"]:
        raise ValueError("mapping_manifest_sha256_mismatch")
    if is_v2(manifest):
        if digest(manifest_path) != SEALED_V2_MANIFEST_SHA256 or \
                receipt["mapping_manifest"]["sha256"] != SEALED_V2_MANIFEST_SHA256:
            raise ValueError("v2_receipt_not_bound_to_the_sealed_manifest")
        prereg = Path(manifest_path).parent / "PREREGISTRATION-v2.md"
        if receipt.get("preregistration", {}).get("sha256") != SEALED_V2_PREREGISTRATION_SHA256 or \
                not prereg.is_file() or digest(prereg) != SEALED_V2_PREREGISTRATION_SHA256:
            raise ValueError("v2_receipt_not_bound_to_the_sealed_preregistration")
        if digest(tolerances_path) != manifest["tolerances"]["sha256"]:
            raise ValueError("tolerances_sha256_disagrees_with_manifest")
        if receipt.get("schema_version") != 2:
            raise ValueError("receipt_is_not_a_v2_receipt")
        manifest = load_effective_v2(manifest, Path(manifest_path).parent)
        missing = [name for name in V2_SOURCES if name not in receipt.get("local_source_sha256", {})]
        if missing:
            raise ValueError("local_source_not_recorded:" + ",".join(missing))
        module = receipt.get("distribution_module", {})
        if module.get("source_sha256") != receipt["local_source_sha256"]["distribution_module.py"]:
            raise ValueError("distribution_module_source_sha256_mismatch")
    elif receipt.get("schema_version", 1) != 1:
        raise ValueError("v2_receipt_bound_to_a_v1_manifest")
    if oracle_path is not None and digest(oracle_path) != manifest["oracle"]["receipt_sha256"]:
        raise ValueError("oracle_receipt_sha256_mismatch")
    limits = tolerances["limits"]
    if set(limits) != set(REQUIRED_LIMITS):
        raise ValueError("tolerance_sheet_keys:" + ",".join(sorted(set(limits) ^ set(REQUIRED_LIMITS))))
    if receipt["unsupported_mappings"] != sorted(_unsupported_ids(manifest)):
        raise ValueError("receipt_unsupported_mappings_disagree_with_manifest")
    if receipt["engine"]["version"] != manifest["engine"]["version"]:
        raise ValueError("engine_version_disagrees_with_manifest:" + receipt["engine"]["version"])
    if receipt["evidence_class"] != manifest_evidence_class(manifest):
        raise ValueError("evidence_class_disagrees_with_manifest:" + receipt["evidence_class"])
    check_local_sources(receipt, source_dir)
    if plan_path is not None:
        if digest(plan_path) != manifest["oracle"]["plan_sha256"]:
            raise ValueError("plan_sha256_mismatch")
        check_case_configuration(receipt, manifest, json.loads(Path(plan_path).read_text()))
    return limits, manifest


def _record(checks, entry):
    """Every check carries a unique key so a failure can never be ambiguous."""
    entry["ordinal"] = len(checks) + 1
    entry["key"] = entry["id"] + "." + entry["field"] + "#" + str(entry["ordinal"])
    checks.append(entry)
    return entry


def _check(checks, key, field, expected, observed, limit, blocked_by=None):
    expected_d, observed_d = Decimal(expected), Decimal(observed)
    delta = observed_d - expected_d
    status = "PASS" if abs(delta) <= Decimal(limit) else "FAIL"
    return _record(checks, {"id": key, "field": field, "expected": str(expected_d),
                            "observed": str(observed_d), "delta": str(delta),
                            "tolerance": str(Decimal(limit)), "status": status,
                            "blocked_by": blocked_by if status == "FAIL" else None})


def _event_name(kind: str, index: int, reason) -> str:
    return (str(reason) + "_" + kind) if reason else (kind + "_" + str(index + 1))


def _unsupported_ids(manifest) -> set:
    if not manifest:
        return set()
    return {row["id"] for row in manifest.get("mappings", []) if row.get("status") == "unsupported"}


def _attribution(mappings, declared: set):
    """A mapping may only be named if the bound manifest declares it unsupported."""
    named = sorted({m for m in mappings if m})
    if not named or any(m not in declared for m in named):
        return None, sorted(m for m in named if m not in declared)
    return ",".join(named), []


def recompute_cash_ledger(initial: Decimal, fills, distributions) -> list:
    """Independent reconstruction of the cash path from fills and distributions."""
    events = [{"kind": "fill", "utc_seconds": f["utc_seconds"],
               "delta": -Decimal(f["quantity"]) * Decimal(f["price"]) - Decimal(f["fee"])}
              for f in fills]
    events += [{"kind": "distribution", "utc_seconds": int(d["utc_seconds"]),
                "delta": Decimal(str(d["amount"]))} for d in distributions]
    events.sort(key=lambda e: (e["utc_seconds"], 0 if e["kind"] == "distribution" else 1))
    cash, ledger = Decimal(initial), []
    for event in events:
        cash += event["delta"]
        ledger.append({"kind": event["kind"], "utc_seconds": event["utc_seconds"], "cash": cash})
    return ledger


def _exact(checks, key, field, expected, observed, ok=None):
    """An exact, non-numeric or structural check. ``ok`` overrides equality."""
    passed = (expected == observed) if ok is None else bool(ok)
    return _record(checks, {"id": key, "field": field, "expected": str(expected),
                            "observed": str(observed), "delta": "-", "tolerance": "exact",
                            "status": "PASS" if passed else "FAIL", "blocked_by": None})


def _skip(checks, key, field, reason):
    return _record(checks, {"id": key, "field": field, "expected": "available", "observed": "absent",
                            "delta": "-", "tolerance": "exact", "status": "SKIPPED",
                            "blocked_by": None, "reason": reason})


def _maybe_decimal(value):
    """A Decimal for a numeric engine field, or None when it is absent or not numeric."""
    try:
        return _decimal(value) if value is not None else None
    except ArithmeticError:
        return None


def _oco_structure_ok(pair, side: str, quantity: int) -> bool:
    """The native OCO structure as the engine's cache recorded each accepted leg.

    Judged only from ``engine_at_accept`` (``order.to_dict()`` of the order read
    back from the engine's cache at OrderAccepted), never from the harness's own
    submission strings; a leg without that engine record fails.
    """
    legs = pair.get("legs", [])
    if len(legs) != 2:
        return False
    ids = [leg["client_order_id"] for leg in legs]
    for leg, sibling in zip(legs, reversed(ids)):
        view = leg.get("engine_at_accept")
        if not isinstance(view, dict):
            return False
        if (view.get("client_order_id") != leg["client_order_id"]
                or view.get("type") != leg.get("order_type") or view.get("status") != "ACCEPTED"
                or view.get("side") != side or _maybe_decimal(view.get("quantity")) != abs(quantity)
                or view.get("contingency_type") != "OCO"
                or view.get("order_list_id") != pair["order_list_id"]
                or view.get("time_in_force") != "GTC" or view.get("trigger_type") != "DEFAULT"
                or view.get("is_reduce_only") is not False
                or view.get("linked_order_ids") != [sibling]
                or _maybe_decimal(view.get("trigger_price")) is None
                or _maybe_decimal(view.get("trigger_price")) != _maybe_decimal(leg.get("trigger_price"))):
            return False
    return True


def _engine_final_statuses(pair, filled_id) -> dict:
    """Each leg's terminal status and filled quantity from the engine's cache at run end."""
    found = {}
    for leg in pair.get("legs", []):
        view = leg.get("engine_final")
        role = "filled" if leg["client_order_id"] == filled_id else "sibling"
        found[role] = (view.get("status"), str(_maybe_decimal(view.get("filled_qty")))) \
            if isinstance(view, dict) else None
    return found


def _as_int(value):
    """An exact integer, or None for anything else (bool, fraction, text, absent)."""
    if isinstance(value, bool):
        return None
    try:
        found = _decimal(value)
    except (ArithmeticError, ValueError, IndexError):
        return None
    return int(found) if found == found.to_integral_value() else None


def expected_filled_leg(quantity: int, close: Decimal, tested_open: Decimal):
    """mechanism_rules.fill_rule_by_open: the leg type that must fill at the open.

    open >= C + tick: STOP for a BUY, MIT for a SELL. open <= C - tick: MIT for a
    BUY, STOP for a SELL. Strictly between, no leg is faithful (``None``).
    """
    if tested_open >= close + TICK:
        return "STOP_MARKET" if quantity > 0 else "MARKET_IF_TOUCHED"
    if tested_open <= close - TICK:
        return "MARKET_IF_TOUCHED" if quantity > 0 else "STOP_MARKET"
    return None


def v2_oco_checks(checks, receipt: dict, expected: dict, bars) -> None:
    """market_on_open_proxy acceptance criteria, per preregistered OCO pair."""
    evidence = bars is not None and len(bars) > 0
    by_ts = {row["ts_event_ns"]: row for row in bars} if evidence else {}
    sessions, first = [], {}
    for row in bars or []:
        if row["session_date"] not in first:
            first[row["session_date"]] = row
            sessions.append(row["session_date"])
    pairs = receipt.get("oco_pairs", [])
    events = receipt.get("order_events", [])
    intents = {i.get("order_ref"): i for i in receipt["intents"]}
    wanted_orders = 2 * len(expected["intents"])
    _exact(checks, "oco_pairs", "count", len(expected["intents"]), len(pairs))
    _exact(checks, "oco_orders", "count", wanted_orders,
           sum(len(pair.get("legs", [])) for pair in pairs))
    # One pair per intent, each intent once; four distinct legs; nothing else
    # in the order stream; no denial or rejection anywhere in it.
    intent_refs = [i.get("order_ref") for i in receipt["intents"]]
    pair_refs = [pair.get("order_ref") for pair in pairs]
    _exact(checks, "oco_pairs", "order_refs_unique_and_equal_to_intents",
           sorted(map(str, intent_refs)), sorted(map(str, pair_refs)),
           ok=(len(set(pair_refs)) == len(pair_refs) and len(set(intent_refs)) == len(intent_refs)
               and set(pair_refs) == set(intent_refs)))
    all_leg_ids = [leg.get("client_order_id") for pair in pairs for leg in pair.get("legs", [])]
    _exact(checks, "oco_orders", "distinct_client_order_ids", wanted_orders, len(set(all_leg_ids)),
           ok=len(set(all_leg_ids)) == wanted_orders == len(all_leg_ids))
    _exact(checks, "order_events", "client_order_ids_beyond_the_legs", [],
           sorted({str(e.get("client_order_id")) for e in events} - {str(i) for i in all_leg_ids}))
    _exact(checks, "order_events", "denied_or_rejected", 0,
           sum(1 for e in events if e.get("event") in ("OrderDenied", "OrderRejected")))
    for index, pair in enumerate(pairs):
        intent = intents.get(pair.get("order_ref"))
        name = (str(intent.get("reason")) + "_oco") if intent and intent.get("reason") \
            else "oco_" + str(index + 1)
        if intent is None:
            _exact(checks, name, "intent", "present", "absent")
            continue
        quantity = int(intent["quantity"])
        side = "BUY" if quantity > 0 else "SELL"
        decision_ts = int(intent["ts_event_ns"])
        # The submission instant from the engine: the strategy clock when the
        # pair was built, and each leg's OrderSubmitted and OrderAccepted
        # ts_event. probes/v2/probe_oco_moo_p4 observed OrderAccepted at the
        # decision bar's ts_event for every leg (96 of 96 across its four runs).
        _exact(checks, name, "submitted_clock_ns", decision_ts, pair.get("submitted_clock_ns"),
               ok=_as_int(pair.get("submitted_clock_ns")) == decision_ts)
        leg_ids = {leg["client_order_id"] for leg in pair.get("legs", [])}
        pair_events = [e for e in events if e.get("client_order_id") in leg_ids]
        for event_name, field in (("OrderSubmitted", "legs_submitted_at_decision_ts"),
                                  ("OrderAccepted", "legs_accepted_at_decision_ts")):
            found = {cid: sorted(_as_int(e.get("ts_event_ns")) or 0 for e in pair_events
                                 if e["event"] == event_name and e["client_order_id"] == cid)
                     for cid in sorted(leg_ids)}
            want = {cid: [decision_ts] for cid in sorted(leg_ids)}
            _exact(checks, name, field, want, found, ok=len(leg_ids) == 2 and found == want)
        _exact(checks, name, "leg_types", ["MARKET_IF_TOUCHED", "STOP_MARKET"],
               sorted(leg["order_type"] for leg in pair.get("legs", [])))
        _exact(checks, name, "oco_structure", "native OCO, full quantity, reciprocal links",
               "as expected" if _oco_structure_ok(pair, side, quantity) else "differs",
               ok=_oco_structure_ok(pair, side, quantity))
        close = tested = None
        if evidence:
            bar = by_ts.get(decision_ts)
            if bar is None:
                _exact(checks, name, "decision_bar", "present", "absent")
            else:
                close = Decimal(bar["c"])
                _exact(checks, name, "reference_close", close, Decimal(pair["reference_close"]))
                want = {"STOP_MARKET": close + TICK if quantity > 0 else close - TICK,
                        "MARKET_IF_TOUCHED": close - TICK if quantity > 0 else close + TICK}
                for leg in pair.get("legs", []):
                    if leg["order_type"] in want:
                        _exact(checks, name, leg["order_type"].lower() + "_trigger",
                               want[leg["order_type"]], Decimal(leg["trigger_price"]))
                position = sessions.index(bar["session_date"])
                tested = first[sessions[position + 1]] if position + 1 < len(sessions) else None
                if tested is None:
                    _exact(checks, name, "tested_bar", "present", "absent")
        else:
            _skip(checks, name, "trigger_and_gap_evidence",
                  "No converted bars: triggers, the gap, the open price and the filled leg "
                  "cannot be checked.")
        accepted = {e["client_order_id"] for e in pair_events if e["event"] == "OrderAccepted"}
        _exact(checks, name, "legs_accepted", 2, len(accepted))
        _exact(checks, name, "denied_or_rejected", 0,
               sum(1 for e in pair_events if e["event"] in ("OrderDenied", "OrderRejected")))
        fills = [e for e in pair_events if e["event"] == "OrderFilled"]
        _exact(checks, name, "fill_events", 1, len(fills))
        if len(fills) != 1:
            continue
        fill = fills[0]
        _exact(checks, name, "fill_quantity", abs(quantity), int(_decimal(fill["last_qty"])))
        _exact(checks, name, "look_ahead_fill", "after " + str(decision_ts), fill["ts_event_ns"],
               ok=int(fill["ts_event_ns"]) > decision_ts)
        cancels = [e for e in pair_events if e["event"] == "OrderCanceled"]
        _exact(checks, name, "sibling_cancels", 1, len(cancels))
        sibling_ok = (len(cancels) == 1 and cancels[0]["client_order_id"] in leg_ids - {fill["client_order_id"]}
                      and cancels[0]["ts_event_ns"] == fill["ts_event_ns"])
        _exact(checks, name, "sibling_canceled_at_fill_instant", fill["ts_event_ns"],
               cancels[0]["ts_event_ns"] if cancels else None, ok=sibling_ok)
        final = _engine_final_statuses(pair, fill["client_order_id"])
        _exact(checks, name, "engine_final_status",
               {"filled": ("FILLED", str(abs(quantity))), "sibling": ("CANCELED", "0")},
               final, ok=final == {"filled": ("FILLED", str(abs(quantity))),
                                   "sibling": ("CANCELED", "0")})
        if close is not None and tested is not None:
            _exact(checks, name, "fill_in_tested_bar", tested["ts_event_ns"], fill["ts_event_ns"])
            gap = abs(Decimal(tested["o"]) - close)
            _exact(checks, name, "moo_proxy_no_gap", ">= " + str(TICK), gap, ok=gap >= TICK)
            _exact(checks, name, "moo_proxy_not_open", Decimal(tested["o"]), _decimal(fill["last_px"]))
            # Which leg fills is preregistered too: judged from the engine's own
            # record of the filled order, not from the harness's leg label.
            want_leg = expected_filled_leg(quantity, close, Decimal(tested["o"]))
            if want_leg is not None:
                filled = [leg for leg in pair.get("legs", [])
                          if leg["client_order_id"] == fill["client_order_id"]]
                view = filled[0].get("engine_at_accept") if len(filled) == 1 else None
                _exact(checks, name, "filled_leg_by_open_rule", want_leg,
                       view.get("type") if isinstance(view, dict) else None)


def v2_run_checks(checks, receipt: dict) -> None:
    """Callback failures and the ERROR-level engine log scan, for both runs."""
    runs = receipt.get("runs", [])
    _exact(checks, "runs", "count", 2, len(runs))
    for run in runs:
        label = str(run.get("label"))
        _exact(checks, "run_integrity", label + ".strategy_callback_errors", 0,
               len(run.get("strategy_callback_errors", [])))
        scan = run.get("engine_log_scan")
        if scan is None:
            _exact(checks, "engine_log", label + ".scan", "present", "absent")
            continue
        _exact(checks, "engine_log", label + ".captured_lines", "> 0", scan["lines"],
               ok=scan["lines"] > 0)
        _exact(checks, "engine_log", label + ".error_lines", 0, scan["error_lines"])
        _exact(checks, "engine_log", label + ".negative_cash_lines", 0, scan["negative_cash_lines"])


def v2_distribution_checks(checks, receipt: dict, manifest: dict, limits: dict) -> None:
    """distributions_and_cash acceptance criteria against the sealed predictions."""
    module = receipt.get("distribution_module", {})
    predictions = manifest["one_zero_predictions"]["distributions"]
    _exact(checks, "distribution_module", "class", "DistributionModule", module.get("class"))
    _exact(checks, "distribution_module", "venue_module_count", 1, module.get("venue_module_count"))
    _exact(checks, "distribution_module", "errors", 0, len(module.get("errors", [])))
    emissions = module.get("emissions", [])
    _exact(checks, "distribution_module", "emissions", len(predictions), len(emissions))
    calls = set(module.get("calls_at_event_instants_ns", []))
    rows = receipt.get("native_account_event_rows", [])
    acknowledged = {}
    for record in module.get("acknowledgements", []):
        ok = bool(record["outcomes"]) and all(o["applied"] and o["error"] is None
                                              for o in record["outcomes"])
        for ex_date in record["ex_dates"]:
            acknowledged[ex_date] = acknowledged.get(ex_date, True) and ok
    for index, want in enumerate(predictions):
        name = "distribution_" + str(index + 1)
        instant = int(want["ex_instant_utc_seconds"]) * 10 ** 9
        _exact(checks, name, "process_called_at_ex_instant", instant,
               instant if instant in calls else None)
        got = emissions[index] if index < len(emissions) else None
        if got is None:
            _exact(checks, name, "emission", "present", "absent")
            continue
        _exact(checks, name, "emitted_at_ns", instant, int(got["ts_now_ns"]))
        _exact(checks, name, "on_time", True, got["on_time"])
        _exact(checks, name, "eligible_quantity", int(want["eligible_quantity"]),
               int(got["eligible_quantity"]))
        _exact(checks, name, "per_share", Decimal(want["per_share"]), Decimal(got["per_share"]))
        _check(checks, name, "amount_usd", want["amount_usd"], got["amount"], limits["dividend_usd_abs"])
        _exact(checks, name, "acknowledged_applied", True, acknowledged.get(got["ex_date"], False))
        reported = [i for i, row in enumerate(rows)
                    if row["reported"] and int(row["ts_event_ns"]) == instant]
        delta = None
        if len(reported) == 1 and reported[0] > 0:
            j = reported[0]
            delta = Decimal(rows[j]["total"]) - Decimal(rows[j - 1]["total"])
        _exact(checks, name, "reported_account_state_delta", Decimal(got["amount"]), delta,
               ok=delta is not None and delta == Decimal(got["amount"]))
    # Engine-observed: after the initial state, every reported AccountState sits
    # at an emission instant with exactly the emitted delta, so no other module
    # or source adjusted the account.
    emitted = {int(e["ts_now_ns"]): Decimal(e["amount"]) for e in emissions}
    unexplained = []
    for j, row in enumerate(rows):
        if not row["reported"] or j == 0:
            continue
        delta = Decimal(row["total"]) - Decimal(rows[j - 1]["total"])
        if emitted.get(int(row["ts_event_ns"])) != delta:
            unexplained.append(int(row["ts_event_ns"]))
    _exact(checks, "distribution_module", "unexplained_reported_account_states", [], unexplained)
    ledger = receipt.get("distribution_ledger", [])
    _exact(checks, "distribution_ledger", "engine_posted", True,
           bool(ledger) and len(ledger) == len(predictions)
           and all(d.get("engine_posted") is True for d in ledger))


def _parse_utc(text):
    from datetime import datetime
    try:
        value = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if value.tzinfo is not None else None


def v2_precondition_checks(checks, receipt: dict, manifest: dict, context: dict) -> None:
    """acceptance_criteria.preconditions, evaluated as checks.

    ``context`` carries what only the comparison run can observe: whether the
    frozen inputs were re-hashed now (``--lean-data``) and the review record as
    it is on disk now (``{"sha256", "content"}`` or ``None``).
    """
    # [0] Independent review of exactly these harness files, before this run.
    review = (receipt.get("preconditions") or {}).get("review")
    name = PRECONDITION_PREFIX + "review"
    if not review:
        _exact(checks, name, "retained_record_before_run", "a retained review record",
               "absent: no independent review preceded this run", ok=False)
    else:
        on_disk = context.get("review_record")
        disk_sha = on_disk.get("sha256") if on_disk else None
        _exact(checks, name, "record_sha256_at_comparison", review.get("sha256"), disk_sha)
        content = on_disk.get("content") if on_disk and disk_sha == review.get("sha256") else None
        if not isinstance(content, dict):
            _exact(checks, name, "record_content", "readable", "absent", ok=False)
        else:
            _exact(checks, name, "schema", REVIEW_RECORD_SCHEMA, content.get("schema"))
            _exact(checks, name, "reviewed_files_are_the_files_that_ran", [],
                   _harness_files_differing(content.get("reviewed_local_source_sha256"), receipt))
            _exact_before_run(checks, name, "completed_before_run_started",
                              content.get("completed_utc"), receipt)
            _exact(checks, name, "unresolved_findings", 0, content.get("unresolved_findings"))
    # [0, continued] "... before the first v2 run": earlier v2 replays ran before
    # any review, so the qualifying reading needs the gate owner's acceptance.
    _replay_history_checks(checks, name, receipt, context)
    # [1] Sealed files and frozen inputs, at run time and at comparison time.
    name = PRECONDITION_PREFIX + "hashes"
    _exact(checks, name, "sealed_manifest_sha256", SEALED_V2_MANIFEST_SHA256,
           receipt["mapping_manifest"]["sha256"])
    _exact(checks, name, "tolerances_sha256", manifest["tolerances"]["sha256"],
           receipt["tolerances"]["sha256"])
    frozen = manifest["inputs"]["frozen_sha256"]
    _exact(checks, name, "inputs_at_run", "frozen_sha256 of the manifest",
           "equal" if receipt["inputs"]["sha256"] == frozen else "differs",
           ok=receipt["inputs"]["sha256"] == frozen)
    if context.get("inputs_rehashed_at_comparison"):
        _exact(checks, name, "inputs_at_comparison", "re-hashed equal", "re-hashed equal")
    else:
        _skip(checks, name, "inputs_at_comparison",
              "Only --lean-data re-hashes the five frozen inputs at comparison time.")
    # [2] Engine pin and isolation.
    name = PRECONDITION_PREFIX + "engine"
    _exact(checks, name, "version", manifest["engine"]["version"], receipt["engine"]["version"])
    _exact(checks, name, "extension_sha256", manifest["engine"]["extension_sha256"],
           receipt["engine"].get("extension_sha256"))
    isolation = receipt.get("isolation", {})
    interfaces = [list(i) for i in isolation.get("network_interfaces", [])]
    _exact(checks, name, "network_interfaces", [[1, "lo"]], interfaces)
    extra = sorted(set(isolation.get("environment_names", [])) - ISOLATED_ENVIRONMENT)
    _exact(checks, name, "environment_beyond_cleared_set", [], extra)
    values = isolation.get("environment_values") or {}
    _exact(checks, name, "environment_values", ISOLATED_ENVIRONMENT_VALUES,
           {k: values.get(k) for k in ISOLATED_ENVIRONMENT_VALUES})
    mounts = isolation.get("read_only") or {}
    _exact(checks, name, "read_only_mounts",
           {"data_root": True, "harness_source": True, "python_prefix": True},
           {"data_root": mounts.get("data_root"), "harness_source": mounts.get("harness_source"),
            "python_prefix": mounts.get("python_prefix")})
    _exact(checks, name, "python_isolated_flag", 1, isolation.get("python_flags_isolated"),
           ok=isolation.get("python_flags_isolated") == 1
           and not isinstance(isolation.get("python_flags_isolated"), bool))
    namespaces = isolation.get("namespaces") or {}
    uid_map = namespaces.get("uid_map")
    _exact(checks, name, "user_namespace", "a uid_map other than the initial namespace's", uid_map,
           ok=isinstance(uid_map, str) and bool(uid_map.split())
           and uid_map.split() != INITIAL_USER_NAMESPACE_UID_MAP)
    _exact(checks, name, "pid_namespace_pid1", "bwrap", namespaces.get("pid1_comm"))


def _harness_files_differing(reviewed, receipt: dict) -> list:
    """Reviewed harness files whose recorded hash is absent or not the file that ran."""
    reviewed = reviewed if isinstance(reviewed, dict) else {}
    recorded = receipt.get("local_source_sha256", {})
    return sorted(f for f in REVIEWED_HARNESS_FILES
                  if not reviewed.get(f) or reviewed.get(f) != recorded.get(f))


def _exact_before_run(checks, name, field, stamp, receipt: dict):
    """A timezone-aware ``stamp`` strictly before the receipt's started_utc."""
    moment, started = _parse_utc(stamp), _parse_utc(receipt.get("started_utc"))
    return _exact(checks, name, field, "< " + str(receipt.get("started_utc")), stamp,
                  ok=moment is not None and started is not None and moment < started)


def _on_disk(context: dict, key: str, recorded_sha):
    """The context's record for ``key`` when its sha256 still equals ``recorded_sha``."""
    record = context.get(key)
    disk_sha = record.get("sha256") if isinstance(record, dict) else None
    content = record.get("content") if disk_sha is not None and disk_sha == recorded_sha else None
    return disk_sha, content


def _replay_history_checks(checks, name, receipt: dict, context: dict) -> None:
    """The replay history the run recorded, and the deviation it forces.

    The history is re-hashed at comparison time: the file may only have grown by
    appended replays since the run. Any earlier replay not reviewed before it
    ran requires the gate owner's acceptance of ``first_v2_run_preceded_review``.
    """
    preconditions = receipt.get("preconditions") or {}
    history = preconditions.get("prior_v2_replays")
    replays = history.get("replays") if isinstance(history, dict) else None
    if not isinstance(replays, list):
        _exact(checks, name, "prior_v2_replays_recorded", "the replay history", "absent", ok=False)
        replays = []
    else:
        record = context.get("replay_history")
        disk_sha = record.get("sha256") if isinstance(record, dict) else None
        content = record.get("content") if isinstance(record, dict) else None
        on_disk = content.get("replays") if isinstance(content, dict) else None
        prefix = isinstance(on_disk, list) and on_disk[:len(replays)] == replays
        same = disk_sha is not None and disk_sha == history.get("sha256")
        grown = prefix and isinstance(on_disk, list) and len(on_disk) > len(replays)
        _exact(checks, name, "replay_history_at_comparison",
               str(history.get("sha256")) + " or an append-only extension of it",
               disk_sha if not prefix or same else "extended by " + str(len(on_disk) - len(replays)),
               ok=prefix and (same or grown))
    reran = sorted(str(r.get("id")) for r in replays
                   if isinstance(r, dict) and isinstance(r.get("harness_local_source_sha256"), dict)
                   and not _harness_files_differing(r["harness_local_source_sha256"], receipt))
    _exact(checks, name, "no_prior_replay_ran_the_reviewed_harness", [], reran)
    unreviewed = [str(r.get("id")) if isinstance(r, dict) else str(r) for r in replays
                  if not isinstance(r, dict) or r.get("reviewed_before_run") is not True]
    if not unreviewed:
        _exact(checks, name, "prior_v2_replays_not_reviewed_before_run", [], [])
        return
    recorded = preconditions.get("deviation_acceptance")
    if not isinstance(recorded, dict) or not recorded:
        _exact(checks, name, "deviation_acceptance_before_run",
               "the gate owner's acceptance of " + ACCEPTED_DEVIATION,
               "absent: " + str(len(unreviewed)) + " earlier v2 replays ran before any review ("
               + ",".join(unreviewed) + ")", ok=False)
        return
    field = "deviation_acceptance."
    expected_path = "blueprints/us-equities/engine-nautilus/spy-parity/" + DEVIATION_ACCEPTANCE
    _exact(checks, name, field + "path", expected_path, recorded.get("path"))
    disk_sha, content = _on_disk(context, "deviation_acceptance", recorded.get("sha256"))
    _exact(checks, name, field + "sha256_at_comparison", recorded.get("sha256"), disk_sha,
           ok=disk_sha is not None and disk_sha == recorded.get("sha256"))
    if not isinstance(content, dict):
        _exact(checks, name, field + "content", "readable", "absent", ok=False)
        return
    _exact(checks, name, field + "fields", sorted(DEVIATION_ACCEPTANCE_FIELDS), sorted(content))
    _exact(checks, name, field + "schema_version", DEVIATION_ACCEPTANCE_SCHEMA_VERSION,
           content.get("schema_version"),
           ok=content.get("schema_version") == DEVIATION_ACCEPTANCE_SCHEMA_VERSION
           and not isinstance(content.get("schema_version"), bool))
    _exact(checks, name, field + "deviation_id", ACCEPTED_DEVIATION, content.get("deviation_id"))
    declared = [d.get("id") for d in receipt.get("preregistration_deviations", []) if isinstance(d, dict)]
    _exact(checks, name, field + "deviation_declared_in_receipt", True, ACCEPTED_DEVIATION in declared)
    for text_field in ("accepted_by", "statement"):
        value = content.get(text_field)
        _exact(checks, name, field + text_field, "non-empty text", value,
               ok=isinstance(value, str) and bool(value.strip()))
    _exact(checks, name, field + "reviewed_harness_is_the_harness_that_ran", [],
           _harness_files_differing(content.get("reviewed_harness_local_source_sha256"), receipt))
    _exact_before_run(checks, name, field + "accepted_before_run_started",
                      content.get("accepted_utc"), receipt)


def v2_determinism(receipt: dict) -> tuple:
    """Two-run determinism recomputed from the runs, never from the receipt's boolean.

    Exactly two runs, each with a sha256 of its normalized economic record, the
    two equal, an empty ``undeclared_differing_fields`` list, and the receipt's
    own ``two_run_records_equal`` agreeing with that recomputation.
    """
    runs = receipt.get("runs", [])
    hashes = [r.get("normalized_economic_sha256") if isinstance(r, dict) else None for r in runs]
    well_formed = all(isinstance(h, str) and len(h) == 64 and set(h) <= SHA256_HEX for h in hashes)
    undeclared = (receipt.get("two_run_determinism") or {}).get("undeclared_differing_fields")
    equal = len(runs) == 2 and well_formed and hashes[0] == hashes[1]
    ok = equal and undeclared == [] and receipt.get("two_run_records_equal") is True
    detail = ("equal" if ok else
              "differs: runs=" + str(len(runs)) + " hashes_equal=" + str(equal)
              + " undeclared_differing_fields=" + json.dumps(undeclared)
              + " two_run_records_equal=" + str(receipt.get("two_run_records_equal")))
    return ok, detail


def compare(receipt: dict, oracle: dict, limits: dict, manifest=None, bars=None,
            preconditions=None) -> dict:
    """Compare reviewed economic keys. Returns a machine-readable verdict."""
    observed, expected = receipt_case(receipt), oracle
    if observed["case"] != expected["id"]:
        raise ValueError("case_mismatch:" + observed["case"] + "!=" + expected["id"])
    declared = _unsupported_ids(manifest)
    # An empty bar list is evidence that cannot attribute anything, exactly like
    # no bar list at all; both take the SKIPPED path rather than silently
    # behaving as if attribution had been attempted.
    evidence_available = bars is not None and len(bars) > 0
    first_bars = first_bars_by_instant(bars) if evidence_available else None
    checks: list[dict] = []
    rejected: list[str] = []

    _check(checks, "intent_count", "count", len(expected["intents"]), len(observed["intents"]), "0")
    _check(checks, "fill_count", "count", expected["fill_count"], len(observed["fills"]), "0")
    _check(checks, "extra_fills", "fills_beyond_oracle", 0,
           max(0, len(observed["fills"]) - expected["fill_count"]), "0")
    _check(checks, "missing_fills", "oracle_fills_absent", 0,
           max(0, expected["fill_count"] - len(observed["fills"])), "0")

    for index in range(min(len(expected["intents"]), len(observed["intents"]))):
        want, got = expected["intents"][index], observed["intents"][index]
        name = _event_name("intent", index, want.get("reason"))
        _check(checks, name, "utc_seconds", want["utc_seconds"], got["utc_seconds"],
               limits["event_seconds_abs"])
        _check(checks, name, "signed_quantity", want["quantity"], got["quantity"],
               limits["fill_quantity_abs"])

    explained_fill = Decimal(0)
    unexplained_fill = Decimal(0)
    fill_attributions = set()
    for index in range(min(len(expected["fills"]), len(observed["fills"]))):
        want, got = expected["fills"][index], observed["fills"][index]
        reason = expected["intents"][index].get("reason") if index < len(expected["intents"]) else None
        name = _event_name("fill", index, reason)
        _check(checks, name, "utc_seconds", want["utc_seconds"], got["utc_seconds"],
               limits["event_seconds_abs"])
        quantity_ok = _check(checks, name, "signed_quantity", want["quantity"], got["quantity"],
                             limits["fill_quantity_abs"])["status"] == "PASS"
        fee_ok = _check(checks, name, "fee_usd", want["fee"], got["fee"],
                        limits["fees_usd_abs"])["status"] == "PASS"

        # Measured attribution: the native fill must be this session's first-bar
        # close and the oracle fill that same bar's open. Nothing else qualifies,
        # and only a failing price is attributed at all: a correct fill on a bar
        # whose open equals its close must never raise a rejected attribution.
        measured = None
        price_fails = abs(got["price"] - want["price"]) > Decimal(limits["fill_price_usd_abs"])
        bar = first_bars.get(got["utc_seconds"]) if first_bars and price_fails else None
        if bar is not None and got["price"] == Decimal(bar["c"]) and want["price"] == Decimal(bar["o"]):
            measured = MARKET_ON_OPEN
        label, bad = _attribution([measured], declared)
        rejected += bad
        price_check = _check(checks, name, "fill_price_usd", want["price"], got["price"],
                             limits["fill_price_usd_abs"], blocked_by=label)
        if price_check["blocked_by"]:
            price_check["evidence"] = {"session_date": bar["session_date"],
                                       "first_bar_open": bar["o"], "first_bar_close": bar["c"]}
        contribution = (-Decimal(got["quantity"]) * got["price"] - got["fee"]) - \
                       (-Decimal(want["quantity"]) * want["price"] - want["fee"])
        if price_check["blocked_by"] and quantity_ok and fee_ok:
            explained_fill += contribution
            fill_attributions.add(MARKET_ON_OPEN)
        else:
            unexplained_fill += contribution

    _check(checks, "fees_total", "fees_usd", expected["fees_usd"], observed["fees_usd"],
           limits["fees_usd_abs"])
    _check(checks, "distributions_total", "dividend_cash_usd", expected["dividends_usd"],
           observed["dividends_usd"], limits["dividend_usd_abs"])

    # Independent reconstruction of the cash path from the receipt's own fills
    # and distributions. Every headline balance is reconciled against it before
    # it is allowed to stand in for the run against the oracle.
    rebuilt = recompute_cash_ledger(observed["initial_cash_usd"], observed["fills"],
                                    observed["distribution_ledger"])
    rebuilt_end = rebuilt[-1]["cash"] if rebuilt else observed["initial_cash_usd"]
    ledger = observed["distribution_ledger"]
    ledger_sum = sum((Decimal(str(d["amount"])) for d in ledger), Decimal(0))
    unposted_sum = sum((Decimal(str(d["amount"])) for d in ledger
                        if d.get("engine_posted") is False), Decimal(0))
    _check(checks, "end_cash_internal", "reconciled_vs_rebuilt_ledger", rebuilt_end,
           observed["end_cash_usd"], limits["cash_usd_abs"])
    # The native balance is the reconciled path minus whatever the engine did
    # not post. This identity holds for an empty, fully unposted or mixed ledger.
    _check(checks, "native_end_cash_internal", "native_vs_rebuilt_ledger",
           rebuilt_end - unposted_sum, observed["native_end_cash_usd"], limits["cash_usd_abs"])

    # Reconciled cash: only the attributed fill-price deltas may explain it.
    end_tolerance = Decimal(limits["end_cash_usd_abs"])
    delta_end = observed["end_cash_usd"] - expected["end_cash_usd"]
    residue_end = delta_end - explained_fill
    label_end, bad = _attribution(sorted(fill_attributions) if abs(residue_end) <= end_tolerance
                                  else [], declared)
    rejected += bad
    end_check = _check(checks, "end_cash", "reconciled_end_cash_usd", expected["end_cash_usd"],
                       observed["end_cash_usd"], limits["end_cash_usd_abs"], blocked_by=label_end)
    end_check["explained_by_fill_prices"] = str(explained_fill)
    end_check["unexplained_residue"] = str(residue_end)

    # Native balance: distributions_and_cash may claim the unposted total only
    # when the ledger says every entry is unposted and its sum matches exactly.
    all_unposted = bool(ledger) and all(d.get("engine_posted") is False for d in ledger)
    unposted_total = ledger_sum if all_unposted and ledger_sum == observed["dividends_usd"] \
        else Decimal(0)
    delta_native = observed["native_end_cash_usd"] - expected["end_cash_usd"]
    residue_native = delta_native - explained_fill + unposted_total
    native_parts = sorted(fill_attributions)
    if unposted_total != 0:
        native_parts = native_parts + [DISTRIBUTIONS]
    label_native, bad = _attribution(native_parts if abs(residue_native) <= end_tolerance else [],
                                     declared)
    rejected += bad
    native_check = _check(checks, "native_end_cash", "native_end_cash_usd", expected["end_cash_usd"],
                          observed["native_end_cash_usd"], limits["end_cash_usd_abs"],
                          blocked_by=label_native)
    native_check["explained_by_fill_prices"] = str(explained_fill)
    native_check["explained_by_unposted_distributions"] = str(-unposted_total)
    native_check["distribution_ledger_all_unposted"] = all_unposted
    native_check["distribution_ledger_sum_matches"] = ledger_sum == observed["dividends_usd"]
    native_check["unexplained_residue"] = str(residue_native)

    _check(checks, "final_quantity", "shares", expected["final_quantity"], observed["final_quantity"],
           limits["final_quantity_abs"])

    _check(checks, "cash_ledger_events", "count", len(rebuilt), len(observed["cash_ledger"]), "0")
    for index in range(min(len(rebuilt), len(observed["cash_ledger"]))):
        entry = observed["cash_ledger"][index]
        _check(checks, "cash_ledger[" + str(index) + "]", rebuilt[index]["kind"] + "@" +
               str(rebuilt[index]["utc_seconds"]), rebuilt[index]["cash"], _decimal(entry["cash"]),
               limits["cash_usd_abs"])
        if int(entry["utc_seconds"]) != rebuilt[index]["utc_seconds"] or \
                entry["kind"] != rebuilt[index]["kind"]:
            _record(checks, {"id": "cash_ledger[" + str(index) + "]", "field": "event_identity",
                             "expected": rebuilt[index]["kind"] + "@" + str(rebuilt[index]["utc_seconds"]),
                             "observed": str(entry["kind"]) + "@" + str(entry["utc_seconds"]),
                             "delta": "-", "tolerance": "exact", "status": "FAIL",
                             "blocked_by": None})

    if is_v2(manifest):
        v2_precondition_checks(checks, receipt, manifest, preconditions or {})
        v2_oco_checks(checks, receipt, expected, bars if evidence_available else None)
        v2_run_checks(checks, receipt)
        v2_distribution_checks(checks, receipt, manifest, limits)

    if is_v2(manifest):
        deterministic, detail = v2_determinism(receipt)
    else:
        deterministic = observed["two_run_records_equal"]
        detail = "equal" if deterministic else "differs"
    _record(checks, {"id": "two_run_determinism", "field": "normalized_economic_sha256",
                     "expected": "equal", "observed": detail,
                     "delta": "-", "tolerance": "exact",
                     "status": "PASS" if deterministic else "FAIL",
                     "blocked_by": None})
    if not evidence_available:
        # Not a PASS: the check could not be performed, and saying otherwise
        # would read as evidence that attribution had been verified.
        _record(checks, {"id": "attribution_evidence", "field": "converted_bars",
                         "expected": "available",
                         "observed": "absent" if bars is None else "empty", "delta": "-",
                         "tolerance": "exact", "status": "SKIPPED", "blocked_by": None,
                         "reason": ("No converted bars supplied" if bars is None else
                                    "Converted bar list is empty") +
                                   ", so no deviation could be attributed; every deviation is "
                                   "an unattributed FAIL."})

    failures = [c for c in checks if c["status"] == "FAIL"]
    skipped = [c["key"] for c in checks if c["status"] == "SKIPPED"]
    blocked = sorted({m for c in failures if c["blocked_by"] for m in c["blocked_by"].split(",")})
    unattributed = [c["key"] for c in failures if not c["blocked_by"]]
    # A skipped check or a rejected attribution means the comparison was not
    # completed, so it can never reach PASS however few checks failed. Under v2
    # the sealed falsifiers name "any skipped check", so it is a FAIL outright.
    if failures and (unattributed or rejected):
        outcome = "FAIL"
    elif is_v2(manifest) and (skipped or rejected):
        outcome = "FAIL"
    elif failures:
        outcome = "BLOCKED-INCOMPLETE" if skipped else "BLOCKED"
    elif skipped or rejected:
        outcome = "BLOCKED-INCOMPLETE"
    else:
        outcome = "PASS"
    summary = {}
    if is_v2(manifest):
        pre = [c for c in checks if c["id"].startswith(PRECONDITION_PREFIX)]
        rest = [c for c in checks if not c["id"].startswith(PRECONDITION_PREFIX)]
        conditions = receipt.get("preconditions") or {}
        history = conditions.get("prior_v2_replays") or {}
        replays = history.get("replays") if isinstance(history.get("replays"), list) else []
        summary = {
            "preconditions": {c["key"]: c["status"] for c in pre},
            "preregistration_qualifying": bool(pre) and all(c["status"] == "PASS" for c in pre),
            "execution_checks": {status.lower(): sum(1 for c in rest if c["status"] == status)
                                 for status in ("PASS", "FAIL", "SKIPPED")},
            "prior_v2_replays": len(replays),
            "prior_v2_replays_reviewed_before_run": sum(
                1 for r in replays if isinstance(r, dict) and r.get("reviewed_before_run") is True),
            "preregistration_deviations": [d.get("id") for d in receipt.get("preregistration_deviations", [])
                                           if isinstance(d, dict)],
            "deviation_acceptance_recorded": bool(conditions.get("deviation_acceptance")),
        }
    return {**summary, "case": expected["id"], "checks": checks, "failed": len(failures),
            "skipped": skipped, "verdict": outcome, "complete": not (skipped or rejected),
            "blocking_mappings": blocked, "unattributed_failures": unattributed,
            "rejected_attributions": sorted(set(rejected)),
            "manifest_unsupported_mappings": sorted(declared),
            "attribution_evidence": "converted bars" if evidence_available else "none",
            "native_end_cash_usd": str(observed["native_end_cash_usd"]),
            "manifest_schema_version": manifest.get("schema_version", 1) if manifest else None,
            "note": ("Mapping manifest v2 declares no unsupported row for this case, so no failure "
                     "can be attributed: any failing check is FAIL, and so is any skipped check or "
                     "rejected attribution (a sealed falsifier). The preconditions are checks "
                     "under the sealed verdict rule, so an unmet precondition fails the comparison "
                     "even when every execution check passes; preregistration_qualifying and "
                     "execution_checks report the two separately." if is_v2(manifest) else
                     "A failure is BLOCKED only when a measured deviation matches a mapping the bound "
                     "manifest declares unsupported. Any residue stays an unattributed FAIL, and a "
                     "skipped check or rejected attribution leaves the comparison incomplete.")}


def precondition_context(receipt: dict, manifest: dict, bars_path, lean_data) -> dict:
    """What only this comparison run can observe for the v2 preconditions.

    Inputs count as re-hashed only when the bars were re-derived from
    ``--lean-data``: ``load_bars`` then verified the five input hashes against
    the receipt, and the receipt's against the manifest is a separate check.
    """
    context = {"inputs_rehashed_at_comparison": bars_path is None and lean_data is not None,
               "review_record": None, "deviation_acceptance": None, "replay_history": None}
    if not is_v2(manifest):
        return context
    conditions = receipt.get("preconditions") or {}
    for key, recorded in (("review_record", conditions.get("review")),
                          ("deviation_acceptance", conditions.get("deviation_acceptance"))):
        if isinstance(recorded, dict) and recorded.get("path"):
            context[key] = read_record(SOURCE.parents[3] / recorded["path"])
    context["replay_history"] = read_record(SOURCE / REPLAY_HISTORY)
    return context


def read_record(path: Path):
    """``{"sha256", "content"}`` of a JSON record as it is on disk now, or None."""
    if not Path(path).is_file():
        return None
    blob = Path(path).read_bytes()
    try:
        content = json.loads(blob.decode("utf-8"))
    except ValueError:
        content = None
    return {"sha256": hashlib.sha256(blob).hexdigest(), "content": content}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True, help="Replay receipt.json from run.py")
    parser.add_argument("--oracle", type=Path,
                        default=SOURCE.parent.parent / "historical-simulation/receipt.json")
    parser.add_argument("--tolerances", type=Path, default=SOURCE / "tolerances.json")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="Mapping manifest; defaults to the file the receipt names in this "
                             "directory, and is always checked against the receipt's sha256")
    parser.add_argument("--plan", type=Path,
                        default=SOURCE.parent.parent / "historical-simulation/plan.json")
    parser.add_argument("--bars", type=Path,
                        help="converted-rows.private.json from the run, for measured attribution")
    parser.add_argument("--lean-data", type=Path,
                        help="Retained LEAN Data root; re-derives the bars instead of --bars")
    parser.add_argument("--case", help="Optional: must equal the receipt's own case")
    parser.add_argument("--verdict", type=Path, help="Optional path for the machine-readable verdict")
    args = parser.parse_args()

    receipt = json.loads(args.receipt.read_text())
    if args.manifest is None:
        args.manifest = SOURCE / Path(receipt["mapping_manifest"]["path"]).name
    if args.case and args.case != receipt["case"]:
        raise ValueError("requested_case_is_not_the_receipt_case:" + args.case)
    limits, manifest = bind(receipt, args.tolerances, args.manifest, args.oracle, args.plan)
    oracle = oracle_case(json.loads(args.oracle.read_text()), receipt["case"])
    bars = load_bars(args.bars, args.lean_data, receipt, manifest)
    verdict = compare(receipt, oracle, limits, manifest, bars,
                      precondition_context(receipt, manifest, args.bars, args.lean_data))

    for check in verdict["checks"]:
        suffix = "" if not check["blocked_by"] else "  blocked_by=" + check["blocked_by"]
        if check["status"] == "SKIPPED":
            suffix = "  reason=" + check.get("reason", "")
        print("{status:<7} {id:<20} {field:<26} expected={expected:<14} observed={observed:<14} "
              "delta={delta:<12} tol={tolerance}{suffix}".format(suffix=suffix, **check))
    print("VERDICT " + json.dumps({k: v for k, v in verdict.items() if k != "checks"}, sort_keys=True))
    if args.verdict:
        args.verdict.write_text(json.dumps(verdict, indent=2, sort_keys=True, default=str) + "\n")
    # Only a complete comparison with no failing check exits zero.
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
