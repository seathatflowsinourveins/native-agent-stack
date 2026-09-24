"""holdout_gate: which items the holdout opens for, the access log, the evaluator's refusals and the
authorization decision by rule.

Access log (blueprints/us-equities/mover-v3/holdout-access-log.jsonl): an 'authorization' record is committed and
pushed before its action; a 'completion' record after it, before any later authorization. Review round 8, R8-6: a
'count' may be retried under the same conditions as a 'read' (its completion reports failed with a null
results_sha256, the tree is the same, the sealed input is the same if one exists, and the deadline has not passed).
"""
from __future__ import annotations

from core.params import ITEM_IDS

AUTH_FIELDS = ("utc", "record_kind", "authorization_id", "actor_role", "protocol_id", "protocol_sha256",
               "code_revision", "study_code_tree", "runtime_lock_sha256", "data_file_sha256s",
               "validation_results_sha256", "requested_items", "purpose", "decision", "refusal", "retry_of")
COMPLETION_FIELDS = ("utc", "record_kind", "authorization_id", "status", "snapshot_sha256", "rows_read",
                     "results_sha256", "exposed_symbol_sessions")
PURPOSES = ("collect", "amend", "count", "read")


# ---------------------------------------------------------------- the gate

def validated_items(validation_results: dict) -> list:
    """Items whose validation label is 'screened' (Holm p <= 0.05, the minimum sample and, for a tradable cell,
    the three robustness statistics). There is no cap."""
    return [i for i in ITEM_IDS if validation_results["labels"].get(i) == "screened"]


def validation_complete(validation_results) -> bool:
    """multiple_testing.procedure (review round 10, F5): the validation results file holds all 5 validation p-values
    keyed by item_ids, each a number in [0, 1], and a label for each."""
    if not isinstance(validation_results, dict):
        return False
    items, labels = validation_results.get("items"), validation_results.get("labels")
    if not isinstance(items, dict) or set(items) != set(ITEM_IDS) or not isinstance(labels, dict) or \
            set(labels) != set(ITEM_IDS):
        return False
    for i in ITEM_IDS:
        p = (items[i] or {}).get("p_stage") if isinstance(items[i], dict) else None
        if isinstance(p, bool) or not isinstance(p, (int, float)) or not 0.0 <= p <= 1.0:
            return False
    return True


def classify_activity(kind: str) -> str:
    """chronology.holdout.holdout_read: only computing a v3-defined outcome from holdout data is a read."""
    not_reads = {"collection", "batch_sha256", "paper_decision", "paper_order", "dashboard_metadata",
                 "membership_only"}
    if kind in not_reads:
        return "not a read"
    if kind in ("exit_price_paired_with_entry", "forward_return", "net_return", "leg_return", "terminal_booking",
                "statistic_from_outcomes"):
        return "read"
    raise ValueError(f"unclassified activity {kind!r}")


# ---------------------------------------------------------------- access-log sequence

def check_records(records: list) -> list:
    problems = []
    for i, r in enumerate(records):
        need = AUTH_FIELDS if r.get("record_kind") == "authorization" else COMPLETION_FIELDS
        if r.get("record_kind") not in ("authorization", "completion"):
            problems.append(f"record {i}: unknown record_kind")
            continue
        missing = [f for f in need if f not in r]
        if missing:
            problems.append(f"record {i}: missing {missing}")
        if r.get("record_kind") == "authorization" and r.get("purpose") not in PURPOSES:
            problems.append(f"record {i}: unknown purpose")
    return problems


def sequence(records: list) -> dict:
    """Walk the log: {"problems": [...], "open": authorization_id or None, "granted": {id: auth},
    "completions": {id: completion}}."""
    granted, completions, problems = {}, {}, check_records(records)
    open_id = None
    for i, r in enumerate(records):
        if r.get("record_kind") == "authorization":
            if open_id is not None:
                problems.append(f"record {i}: authorization while {open_id} has no completion")
            if r.get("decision") == "granted":
                granted[r["authorization_id"]] = r
                open_id = r["authorization_id"]
        elif r.get("record_kind") == "completion":
            aid = r.get("authorization_id")
            if aid not in granted:
                problems.append(f"record {i}: completion of {aid}, which is not a granted authorization")
            elif aid in completions:
                problems.append(f"record {i}: second completion of {aid}")
            else:
                completions[aid] = r
                if open_id == aid:
                    open_id = None
    return {"problems": problems, "open": open_id, "granted": granted, "completions": completions}


def failed_without_results(completion) -> bool:
    return completion is not None and completion.get("status") == "failed" and completion.get("results_sha256") is None


def retry_allowed(prev_auth: dict, prev_completion: dict, new: dict, *, same_snapshot: bool, before_deadline: bool) -> bool:
    return (failed_without_results(prev_completion) and new.get("retry_of") == prev_auth["authorization_id"]
            and new.get("study_code_tree") == prev_auth.get("study_code_tree") and same_snapshot and before_deadline)


# ---------------------------------------------------------------- evaluator refusals

def evaluator_refusals(ctx: dict) -> list:
    """Every applicable refusal for a requested holdout action. ctx keys (all required for count and read):
    protocol_status, protocol_sha256, frozen_protocol_sha256, validation_present, validation_sha256,
    validation_committed_sha256, validation_reachable_before_n0, validation_run_tree, validation_run_protocol_sha256,
    frozen_tree, running_tree, fetch_only_deviation_passed, runtime_ok, data_files_ok, amendment_refusals,
    validated_items, requested_items, access_log (records), accrual_logs_complete, purpose, count_due,
    same_snapshot, before_deadline, retry_of; and (review round 10) validation_complete (F5), validation_void and
    holdout_void (F4).

    Refusals raised before this function runs (core.runner.context: the study tree, the logs on origin/main, the
    runtime, the data files and the amendment lines) stop the command before any authorization record is written,
    so they are not logged as 'refused' records: the committed state such a record would cite is not established
    (review round 10, F10). runtime_ok, data_files_ok and amendment_refusals are therefore always clean here."""
    out = []
    purpose = ctx["purpose"]
    if ctx["protocol_status"] != "frozen" or ctx["protocol_sha256"] != ctx["frozen_protocol_sha256"]:
        out.append("the protocol status is not frozen, or its sha256 differs from the frozen commit")
    if purpose in ("collect", "amend"):
        seq = sequence(ctx["access_log"])
        if seq["open"] is not None:
            out.append("an earlier granted authorization has no committed completion record")
        return out
    if not ctx["validation_present"] or ctx["validation_sha256"] != ctx["validation_committed_sha256"] \
            or not ctx["validation_reachable_before_n0"]:
        out.append("the validation results file is missing, differs from the committed sha256, or was not "
                   "reachable from origin/main before 09:30 ET on N0")
    if ctx["validation_run_tree"] != ctx["frozen_tree"] or ctx["validation_run_protocol_sha256"] != ctx["frozen_protocol_sha256"]:
        out.append("the validation results file is not from the governing validation run (tree or protocol sha256)")
    if ctx["validation_present"] and not ctx.get("validation_complete", False):
        out.append("the validation results file does not hold all 5 validation p-values keyed by item_ids")
    if ctx.get("validation_void"):
        out.append("validation is void: a recorded pre-freeze read (exposure_registry.update_rule)")
    if ctx.get("holdout_void"):
        out.append("the holdout is void: a recorded read in the holdout window before the gate opened "
                   "(exposure_registry.update_rule)")
    if ctx["running_tree"] != ctx["frozen_tree"] and not ctx["fetch_only_deviation_passed"]:
        out.append("the holdout action runs from a study tree other than the frozen tree or a passing transport deviation")
    if not ctx["runtime_ok"]:
        out.append("the Python, numpy, pandas, exchange_calendars or duckdb version differs from study/runtime.lock")
    if not ctx["data_files_ok"] or ctx["amendment_refusals"]:
        out.append("a data file differs from its frozen sha256, or an amendment file or line is refused: "
                   + "; ".join(ctx["amendment_refusals"]))
    if not ctx["validated_items"] or any(i not in ctx["validated_items"] for i in ctx["requested_items"]):
        out.append("the list of validated items is empty, or a requested item is not in it")
    seq = sequence(ctx["access_log"])
    if seq["open"] is not None:
        out.append("an earlier granted authorization has no committed completion record")
    if not ctx["accrual_logs_complete"]:
        out.append("a collection batch lacks its committed accrual log")
    prior = [a for a in seq["granted"].values() if a["purpose"] == purpose]
    if purpose == "read" and prior:
        last = prior[-1]
        if not retry_allowed(last, seq["completions"].get(last["authorization_id"]), ctx,
                             same_snapshot=ctx["same_snapshot"], before_deadline=ctx["before_deadline"]):
            out.append("a previous granted 'read' exists and this is not a permitted retry")
    if purpose == "count":
        last = prior[-1] if prior else None
        retry = last is not None and ctx.get("retry_of") == last["authorization_id"]
        if retry:
            if not retry_allowed(last, seq["completions"].get(last["authorization_id"]), ctx,
                                 same_snapshot=ctx["same_snapshot"], before_deadline=ctx["before_deadline"]):
                out.append("a 'count' retry that the retry rule does not permit")
        elif not ctx["count_due"]:
            out.append("a 'count' other than once at the end of the 252 sessions and once at the end of each block")
        if set(ctx.get("count_outputs", ())) - {"H1-D:high", "H1-D:low", "H1-D-b_lane-low", "H3-a", "H3-b", "H3-c"}:
            out.append("a 'count' request asks for anything beyond count_unit")
    return out


def authorization(ctx: dict, authorization_id: str, utc: str, fields: dict) -> dict:
    """The authorization record, granted by rule unless a refusal applies (then 'refused' with the refusal)."""
    ref = evaluator_refusals(ctx)
    return {"utc": utc, "record_kind": "authorization", "authorization_id": authorization_id,
            "actor_role": "committed automation", **fields, "purpose": ctx["purpose"],
            "requested_items": list(ctx.get("requested_items", [])),
            "decision": "refused" if ref else "granted", "refusal": "; ".join(ref) if ref else None,
            "retry_of": ctx.get("retry_of")}


def completion(authorization_id: str, utc: str, status: str, snapshot_sha256, rows_read: int, results_sha256,
               exposed) -> dict:
    if status not in ("complete", "failed", "partial"):
        raise ValueError(status)
    return {"utc": utc, "record_kind": "completion", "authorization_id": authorization_id, "status": status,
            "snapshot_sha256": snapshot_sha256, "rows_read": rows_read, "results_sha256": results_sha256,
            "exposed_symbol_sessions": exposed}


class NoAuthorization(Exception):
    pass


def require_granted(records: list, authorization_id: str, purpose: str) -> dict:
    """A holdout count, read, collection or amendment runs only under its own committed granted authorization that
    has no completion yet; a read without one voids the holdout for every item (access_log.rule)."""
    seq = sequence(records)
    a = seq["granted"].get(authorization_id)
    if a is None or a["purpose"] != purpose:
        raise NoAuthorization(f"no committed granted '{purpose}' authorization {authorization_id}")
    if authorization_id in seq["completions"]:
        raise NoAuthorization(f"authorization {authorization_id} is already completed")
    return a
