"""Read-only projection of registered historical organic-use observations.

Extends native-agent-stack@1796303f:scripts/validate.py:432 and the existing
schema helper at scripts/host_receipts.py:308; confined paths and duplicate-key
checks reuse scripts/catalog_decisions.py:57. No CLI, provider call or statistical
estimator is added. The matrix and age reporter remain separate as documented
in scripts/receipt_staleness.py:35.

Method: organic-e2e-v1-20261005 metrics M1/M2/M10 and the pilot prohibition on
verdicts; amendment U1:15-20 requires the native arm. Receipt sources retain the
exact method hashes. Validation checks declarations, not the truth of a trial,
independent review, exclusion authority or upstream acceptance.
"""

from __future__ import annotations

import copy
import hashlib
import math
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

try:
    from . import host_receipts
    from .catalog_decisions import load, safe_file
except ImportError:
    import host_receipts
    from catalog_decisions import load, safe_file


SCHEMA_PATH = "catalogs/landscape/organic-use.schema.json"
REGISTRY_PATH = "manifests/evidence.json"
STACK_PATH = "manifests/stack.json"
PHASES = ("P1", "P2", "pooled")
COUNTS = (
    "assigned", "exposed", "valid", "eligible_exposed", "unavailable", "censored",
    "telemetry_invalid", "contamination_excluded", "quota_deferred", "uses", "selections",
)
RATES = ("oir", "wilson95_low", "wilson95_high", "selection_rate")


def _schema(root: Path | None = None) -> dict:
    source_root = Path(__file__).resolve().parents[1]
    if root is not None and (Path(root) / SCHEMA_PATH).exists():
        source_root = Path(root)
    return load(source_root, SCHEMA_PATH)


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not value.endswith("Z") or parsed.tzinfo is None:
        raise ValueError("timestamp must be UTC")
    return parsed


def _source_refs(value, path: str, errors: list[str]) -> None:
    """Check portable locators without opening private proof files or fetching URLs."""
    if isinstance(value, dict):
        ref = value.get("ref")
        if isinstance(ref, str):
            invalid = (ref != ref.strip() or ref.startswith(("/", "~", "file:"))
                       or "\\" in ref or any(ord(c) < 32 for c in ref)
                       or ".." in ref.split("/"))
            if "://" in ref:
                try:
                    parsed = urlsplit(ref)
                    invalid = invalid or parsed.scheme != "https" or bool(parsed.username or parsed.password)
                except ValueError:
                    invalid = True
            if invalid:
                errors.append(f"{path}.ref: source locator must be sanitized and portable")
        for key, child in value.items():
            _source_refs(child, f"{path}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _source_refs(child, f"{path}[{index}]", errors)


def _review_ref(item: dict, path: str, errors: list[str]) -> None:
    if (item["ref"] is None) != (item["sha256"] is None):
        errors.append(f"{path}: source ref and hash must be present together")
    if item["status"] not in {"pending", "not_required"} and item["ref"] is None:
        errors.append(f"{path}: completed review or qualification needs retained proof")


def _metric(cell: dict, path: str, errors: list[str]) -> None:
    # Breakdown categories may overlap. There is deliberately no asserted partition.
    assigned = cell["assigned"]
    for field in COUNTS[1:]:
        if cell[field] > assigned:
            errors.append(f"{path}.{field}: count exceeds assigned trials")
    eligible = cell["eligible_exposed"]
    if eligible > min(cell["exposed"], cell["valid"]):
        errors.append(f"{path}.eligible_exposed: exceeds exposed or valid trials")
    if not cell["uses"] <= cell["selections"] <= eligible:
        errors.append(f"{path}: uses <= selections <= eligible_exposed is required")

    valid_rates = True
    for field in RATES:
        value = cell[field]
        if value is not None and (not math.isfinite(value) or not 0 <= value <= 1):
            errors.append(f"{path}.{field}: rate must be finite and between zero and one")
            valid_rates = False
    if eligible == 0:
        if any(cell[field] is not None for field in RATES):
            errors.append(f"{path}: zero eligible denominator requires null rates and bounds")
        return
    if any(cell[field] is None for field in RATES):
        errors.append(f"{path}: positive eligible denominator requires declared rates and bounds")
        return
    if not valid_rates:
        return
    for rate, numerator in (("oir", "uses"), ("selection_rate", "selections")):
        if not math.isclose(cell[rate], cell[numerator] / eligible, rel_tol=1e-9, abs_tol=1e-12):
            errors.append(f"{path}.{rate}: ratio disagrees with declared eligible denominator")
    # Owner-computed Wilson bounds are retained, never recomputed or certified here.
    if not cell["wilson95_low"] <= cell["oir"] <= cell["wilson95_high"]:
        errors.append(f"{path}: interval does not contain the declared OIR")


def _record(record: dict, path: str, errors: list[str]) -> None:
    try:
        observed = _utc(record["observed_at_utc"])
    except ValueError:
        errors.append(f"{path}.observed_at_utc: invalid UTC timestamp")
        observed = None
    if len(set(record["layer_ids"])) != len(record["layer_ids"]):
        errors.append(f"{path}.layer_ids: duplicate layer scope")
    recheck_data = record["recheck"]
    if recheck_data["tool_pin"] != record["component_pin"]:
        errors.append(f"{path}.recheck.tool_pin: must bind the observed component pin")
    if recheck_data["client_version"] != record["client"]["version"]:
        errors.append(f"{path}.recheck.client_version: must bind the observed client version")
    if (recheck_data["sweep_id"] is None) != (recheck_data["sweep_date_utc"] is None):
        errors.append(f"{path}.recheck: sweep id and date must be present together")
    if recheck_data["sweep_date_utc"] is not None:
        try:
            date.fromisoformat(recheck_data["sweep_date_utc"])
        except ValueError:
            errors.append(f"{path}.recheck.sweep_date_utc: invalid date")

    run_ids = set()
    for index, run in enumerate(record["runs"]):
        run_path = f"{path}.runs[{index}]"
        if run["run_id"] in run_ids:
            errors.append(f"{run_path}.run_id: duplicate run within record")
        run_ids.add(run["run_id"])
        try:
            started = _utc(run["started_at_utc"])
            ended = _utc(run["ended_at_utc"]) if run["ended_at_utc"] is not None else None
            if ended is not None and ended < started:
                errors.append(f"{run_path}: end precedes start")
            if observed is not None and (ended or started) > observed:
                errors.append(f"{run_path}: run lies after observation-window end")
        except ValueError:
            errors.append(f"{run_path}: invalid UTC timestamp")
        if run["rc"] is not None and run["ended_at_utc"] is None:
            errors.append(f"{run_path}: terminal rc needs an end timestamp")

    for name in ("qualification", "review", "adjudication"):
        _review_ref(record[name], f"{path}.{name}", errors)
    _review_ref(record["qualification"]["negative_control"],
                f"{path}.qualification.negative_control", errors)
    availability_failure = (record["qualification"]["rule"] == "U1:61"
                            and record["client"]["id"] == "codex"
                            and record["protocol_status"] == "UNAVAILABLE")
    if availability_failure and record["qualification"]["status"] == "complete":
        if record["arm"] != "native" or record["evidence_class"] != "native_proven":
            errors.append(f"{path}.qualification: U1:61 needs native-arm native evidence")
        if record["context_proof"] is None:
            errors.append(f"{path}.qualification: U1:61 needs the native failure criterion and owner context proof")
    if record["state"] == "pending":
        if any(record["phases"][phase] is not None for phase in PHASES):
            errors.append(f"{path}.phases: pending records require all metric cells null")
        if record["verdict"] is not None:
            errors.append(f"{path}.verdict: pending observations cannot issue a verdict")
    else:
        if record["component_pin"] is None:
            errors.append(f"{path}.component_pin: completed observations need the actual tool pin")
        if not record["runs"] or any(run["rc"] is None for run in record["runs"]):
            errors.append(f"{path}.runs: completed observations need terminal run metadata")
        for phase in PHASES:
            cell = record["phases"][phase]
            if cell is None:
                if not availability_failure:
                    errors.append(f"{path}.phases.{phase}: completed observations need a metric cell")
            else:
                _metric(cell, f"{path}.phases.{phase}", errors)
        if all(record["phases"][phase] is not None for phase in PHASES):
            for field in COUNTS:
                cells = record["phases"]
                if cells["pooled"][field] != cells["P1"][field] + cells["P2"][field]:
                    errors.append(f"{path}.phases.pooled.{field}: disagrees with phase counts")

    verdict = record["verdict"]
    if (record["qualification"]["rule"] == "U1:61"
            and (record["client"]["id"] != "codex" or record["protocol_status"] != "UNAVAILABLE")):
        errors.append(f"{path}.qualification.rule: U1:61 requires an evidenced Codex availability failure")
    if (record["protocol_status"] in {"UNKNOWN", "DEFERRED"}
            and (record["qualification"]["status"] == "complete" or verdict is not None)):
        errors.append(f"{path}.protocol_status: unresolved observations cannot complete qualification or issue a verdict")
    if record["stage"] == "pilot" and verdict is not None:
        errors.append(f"{path}.verdict: the protocol pilot issues no verdicts")
    if verdict is not None:
        if record["stage"] != "qualification" or record["state"] != "complete":
            errors.append(f"{path}.verdict: needs a completed final qualification")
        if (record["qualification"]["status"] != "complete"
                or record["review"]["status"] != "reviewed"
                or record["adjudication"]["status"] != "adjudicated"):
            errors.append(f"{path}.verdict: final qualification needs review and adjudication")
    if verdict == "READY":
        if record["arm"] != "native" or record["evidence_class"] != "native_proven":
            errors.append(f"{path}.verdict: READY needs native-arm native evidence")
        if record["qualification"]["negative_control"]["status"] != "passed":
            errors.append(f"{path}.qualification: READY needs the negative-control evidence")
        if record["qualification"]["rule"] != "T6" or record["context_proof"] is None:
            errors.append(f"{path}.qualification: READY needs retained T6/native-arm context proof")
        expected_status = {"codex": "SCREEN_PASS", "claude-code": "ORGANIC_OBSERVED"}.get(record["client"]["id"])
        if expected_status is None or record["protocol_status"] != expected_status:
            errors.append(f"{path}.protocol_status: READY needs the applicable client-specific T6 status")
        for field in ("model", "requested_effort", "effective_effort", "effective_tier", "route", "config_sha256"):
            if record["client"][field] is None:
                errors.append(f"{path}.client.{field}: READY requires witnessed runtime identity")
        if record["phases"]["pooled"] is None or record["phases"]["pooled"]["uses"] == 0:
            errors.append(f"{path}.verdict: READY cannot follow zero or unmeasured organic use")

    if verdict == "NOT-READY":
        if record["arm"] != "native" or record["evidence_class"] != "native_proven":
            errors.append(f"{path}.verdict: NOT-READY needs native-arm native evidence")
        if record["qualification"]["rule"] not in {"T6", "U1:61"} or record["context_proof"] is None:
            errors.append(f"{path}.qualification: NOT-READY needs a retained native failure criterion and owner context proof")

    exclusion = record["exclusion"]
    if verdict == "EXCLUDED" and exclusion is None:
        errors.append(f"{path}.exclusion: EXCLUDED needs rule-c authority and all predicates")
    if verdict == "EXCLUDED":
        pooled = record["phases"]["pooled"]
        if (record["arm"] != "native" or record["evidence_class"] != "native_proven"
                or pooled is None or pooled["selections"] != 0):
            errors.append(f"{path}.exclusion: EXCLUDED needs never-selected full native evidence")
        if record["qualification"]["rule"] != "T6" or record["context_proof"] is None:
            errors.append(f"{path}.exclusion: EXCLUDED needs retained T6/native-arm context proof")
        if record["protocol_status"] in {"UNAVAILABLE", "WIRING", "UNKNOWN", "DEFERRED"}:
            errors.append(f"{path}.exclusion: unavailable or unknown observations cannot justify exclusion")
    if exclusion is not None:
        rule = exclusion["rule_c"]
        if rule["component_id"] != record["component_id"] or rule["task_scope"] != record["task_scope"]:
            errors.append(f"{path}.exclusion.rule_c: authority must cover this tool and task scope")
        for name, predicate in exclusion["predicates"].items():
            if predicate["client_id"] != record["client"]["id"]:
                errors.append(f"{path}.exclusion.predicates.{name}: proof must cover this client")
        overlap = exclusion["predicates"]["overlap_with_selected"]
        if (overlap["selected_cover_component_id"] == record["component_id"]
                or overlap["task_scope"] != record["task_scope"]):
            errors.append(f"{path}.exclusion: covering-tool proof must match this task scope")
        if verdict != "EXCLUDED":
            errors.append(f"{path}.exclusion: an exclusion object requires an EXCLUDED verdict")


def validate_payload(payload, *, component_ids=None, receipt_component_ids=None,
                     schema: dict | None = None) -> list[str]:
    """Validate the optional block; no block is implied when callers omit it.

    Canonical and receipt-covered IDs are supplied by the existing manifest
    validator or loader. Schema violations return first, avoiding typed semantic
    checks over malformed values.
    """
    schema = _schema() if schema is None else schema
    errors: list[str] = []
    host_receipts.validate_against_schema(payload, schema, "data.organic_use", errors)
    if errors:
        return errors
    _source_refs(payload, "data.organic_use", errors)
    keys = set()
    for index, record in enumerate(payload["records"]):
        path = f"data.organic_use.records[{index}]"
        component_id = record["component_id"]
        if component_ids is not None and component_id not in component_ids:
            errors.append(f"{path}.component_id: not a canonical stack component")
        if receipt_component_ids is not None and component_id not in receipt_component_ids:
            errors.append(f"{path}.component_id: outside receipt component coverage")
        if component_ids is not None and record["exclusion"] is not None:
            cover = record["exclusion"]["predicates"]["overlap_with_selected"]["selected_cover_component_id"]
            if cover not in component_ids:
                errors.append(f"{path}.exclusion: covering tool is not a canonical stack component")
        key = record["record_id"]
        if key in keys:
            errors.append(f"{path}.record_id: duplicate observation identity")
        keys.add(key)
        _record(record, path, errors)
    return errors


def load_records(root: Path) -> list[dict]:
    """Load only registered historical receipt blocks, retaining exact ID scopes.

    An absent registry preserves existing fixture/generator behavior. Malformed
    published blocks, registration mismatches and changed hashes fail visibly.
    Source proof locators are retained, not opened or treated as acceptance.
    """
    root = Path(root)
    registry_file = safe_file(root, REGISTRY_PATH)
    if not registry_file.exists():
        return []
    registry = load(root, REGISTRY_PATH)
    if not isinstance(registry, dict) or not isinstance(registry.get("receipts"), list):
        raise ValueError("organic-use evidence registry must contain a receipts list")
    if not isinstance(registry.get("files"), list):
        raise ValueError("organic-use evidence registry must contain a files list")
    files = {}
    for item in registry["files"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("organic-use registry has an invalid file entry")
        if item["path"] in files:
            raise ValueError("organic-use registry has a duplicate file entry")
        files[item["path"]] = item
    records = []
    ids = None
    for entry in registry["receipts"]:
        if not isinstance(entry, dict):
            raise ValueError("organic-use registry has an invalid receipt entry")
        if entry.get("kind") != "historical_inventory":
            continue
        relative = entry.get("path")
        # Generic historical receipts are repository files, never private state.
        path = safe_file(root, relative)
        detail = load(root, relative)
        if not isinstance(detail, dict):
            raise ValueError("registered historical receipt must be an object")
        data = detail.get("data")
        if not isinstance(data, dict) or "organic_use" not in data:
            continue
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if relative not in files or files[relative].get("sha256") != digest:
            raise ValueError(f"organic-use receipt hash mismatch: {relative}")
        for key in ("id", "kind", "component_ids", "claim", "limitations"):
            if detail.get(key) != entry.get(key):
                raise ValueError(f"organic-use receipt registry metadata mismatch: {relative}")
        covered = detail.get("component_ids")
        if not isinstance(covered, list) or not covered or not all(isinstance(x, str) for x in covered):
            raise ValueError(f"organic-use receipt component coverage is invalid: {relative}")
        if ids is None:
            stack = load(root, STACK_PATH)
            if not isinstance(stack, dict) or not isinstance(stack.get("components"), list):
                raise ValueError("organic-use stack manifest has invalid components")
            ids = {component.get("id") for component in stack["components"] if isinstance(component, dict)}
        if any(component not in ids for component in covered):
            raise ValueError(f"organic-use receipt has noncanonical component coverage: {relative}")
        block = data["organic_use"]
        errors = validate_payload(block, component_ids=ids, receipt_component_ids=covered,
                                  schema=_schema(root))
        if errors:
            raise ValueError(f"invalid organic-use receipt {relative}: " + "; ".join(errors))
        for index, record in enumerate(block["records"]):
            projected = copy.deepcopy(record)
            projected.update(receipt_ref=relative, receipt_sha256=digest,
                             block_ref=f"{relative}#/data/organic_use/records/{index}",
                             protocol_id=block["protocol_id"], amendment=block["amendment"],
                             protocol_sources=copy.deepcopy(block["sources"]))
            records.append(projected)
    return records


def recheck(record: dict, current_pin: str | None, current_client_version: str | None,
            now: datetime, landscape_reopened: bool = False) -> list[str]:
    """Return known recheck triggers; an unknown comparison is not a change.

    The caller supplies now to the runtime reporter, never during generation.
    observed_at_utc is the observation-window end, not publication time.
    """
    if now.tzinfo is None:
        raise ValueError("organic-use recheck needs an aware current timestamp")
    flags = []
    observed_pin = record["recheck"]["tool_pin"]
    if observed_pin is not None and current_pin is not None and observed_pin != current_pin:
        flags.append("organic_tool_version_changed")
    observed_client = record["recheck"]["client_version"]
    if (observed_client is not None and current_client_version is not None
            and observed_client != current_client_version):
        flags.append("organic_client_version_changed")
    if landscape_reopened:
        flags.append("organic_landscape_reopened")
    age = now.astimezone(timezone.utc) - _utc(record["observed_at_utc"])
    if age.total_seconds() > record["recheck"]["max_age_days"] * 86400:
        flags.append("organic_age_limit")
    return flags
