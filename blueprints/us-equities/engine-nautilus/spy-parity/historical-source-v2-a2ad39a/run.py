#!/usr/bin/env python3
"""Replay the frozen ``one_zero`` SPY case twice on native NautilusTrader 2.0.0rc5.

Both runs use the same seed and the same venue/instrument configuration in fresh
engines. The receipt records the native intents, the native OCO pairs and every
order event, the fills, the DistributionModule's emissions and acknowledgements,
the native account events, the independent ``Decimal`` cash ledger, the native
end cash, the buying-power and latch event lists, an ERROR-level engine log scan,
raw and normalized output hashes for both runs, and the evidence class ``HIST``.
This runner applies no numeric tolerance of its own: its own checks are exact. It
records ``tolerances.json`` and its hash in the receipt, and ``compare.py`` is the
component that reads and applies every limit the sheet declares.

The run is bound to ``mapping-manifest-v2.json`` (the sealed v2
preregistration). Rows v2 carries unchanged from v1, including the declared
short sessions, are read from ``mapping-manifest.json`` after checking it against
the sha256 the v2 manifest records for it; this file never restates them.

No network, no broker client and no credential store is used. Raw native reports
and the captured engine log stay in the private output directory; the receipt
publishes hashes and the economic ledger only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import random
import re
import socket
import sys
import time

SOURCE = Path(__file__).resolve().parent
REPO = SOURCE.parents[3]
HISTORICAL = SOURCE.parent.parent / "historical-simulation"
FROZEN_PLAN_SHA256 = "60959a050a3b004abf5346d376930b3b2f563096c725dc96e5427703ea203632"
EVIDENCE_CLASS = "HIST"
SEED = 20260922
MANIFEST_V2 = "mapping-manifest-v2.json"
MANIFEST_V1 = "mapping-manifest.json"
EXTENSION = "_libnautilus.cpython-312-x86_64-linux-gnu.so"
# Explicit venue settings from the v2 manifest's case_configuration, passed to
# add_venue instead of relied on as defaults. fill_model, fee_model and
# latency_model stay None, as preregistered.
VENUE = {"oms_type": "NETTING", "account_type": "CASH", "use_random_ids": False,
         "fill_model": None, "fee_model": None, "latency_model": None, "bar_execution": True,
         "bar_adaptive_high_low_ordering": False, "reject_stop_orders": True,
         "support_contingent_orders": True, "frozen_account": False}
NEGATIVE_CASH_TEXT = "Cash account balance would become negative"
# Copied verbatim into every receipt. The first version of this list was written
# after the unisolated development replays and the db8bad7 bwrap replay had run
# and their results were known (replay-history-v2.json lists every replay); the
# 2026-09-23 review-fix round revised it. None changes a sealed file, a tolerance,
# an input or a LEAN-side value; each is a point where the sealed text could not
# be followed literally or left a choice.
PREREGISTRATION_DEVIATIONS = [
    {"id": "review_before_first_run",
     "sealed_text": "acceptance_criteria.preconditions[0]: the harness changes are implemented and "
                    "independently reviewed before the first v2 run; the review record is retained.",
     "deviation": "No independent review preceded any replay in preconditions.prior_v2_replays. "
                  "compare.py evaluates this precondition as a check: unless preconditions.review "
                  "names a retained review record whose sha256 still matches at comparison time, "
                  "whose reviewed harness file hashes equal this run's local_source_sha256, whose "
                  "completion precedes started_utc and which leaves no finding unresolved, the check "
                  "fails and, under the sealed verdict rule, so does the comparison.",
     "effect": "A run without a qualifying review record is published with verdict FAIL and "
               "preregistration_qualifying false even when every execution check passes; it moves "
               "no mapping and no gate."},
    {"id": "first_v2_run_preceded_review",
     "sealed_text": "acceptance_criteria.preconditions[0]: '... before the first v2 run'.",
     "deviation": "Read literally, no run can meet this any more: the first v2 replays on the frozen "
                  "data ran before any review (preconditions.prior_v2_replays). The reading the "
                  "2026-09-23 independent review proposed is that the qualifying run is the first run "
                  "from a harness whose exact files were reviewed before that run, with every earlier "
                  "replay published as superseded. compare.py applies that reading only when the gate "
                  "owner has accepted this deviation: while any recorded earlier replay has "
                  "reviewed_before_run other than true, precondition_review fails unless "
                  "deviation-acceptance-v2.json (schema_version 1: deviation_id, accepted_by, "
                  "accepted_utc, reviewed_harness_local_source_sha256, statement) existed at run time "
                  "(preconditions.deviation_acceptance), is unchanged at comparison time, names this "
                  "deviation, binds exactly the reviewed harness files that ran and is dated before "
                  "started_utc. The harness never writes that file.",
     "effect": "Without the gate owner's acceptance no v2 run can pass, and a new dated "
               "preregistration is required."},
    {"id": "sealed_status_fields_not_updated",
     "sealed_text": "mapping-manifest-v2.json run_status 'preregistered_not_run' and "
                    "harness_changes_required.implemented false.",
     "deviation": "Both fields stay as sealed because the manifest must not be edited; they no "
                  "longer describe the tree once this receipt exists.",
     "effect": "A later dated manifest revision must record the run; the rows stay 'preregistered'."},
    {"id": "late_emission_refusal_is_post_run",
     "sealed_text": "distributions_and_cash.mechanism_rules.timing: a late emission is a module error "
                    "that aborts the run.",
     "deviation": "The module never posts a late event and records the error; the runner then "
                  "refuses the run after engine.run() returns, before any receipt is written, "
                  "instead of stopping the engine mid-run (an exception inside process() is not "
                  "guaranteed to propagate out of the pinned engine).",
     "effect": "Same outcome for publication: no receipt exists for a run with a late emission."},
    {"id": "venue_module_count_not_engine_observable",
     "sealed_text": "acceptance_criteria.distributions_and_cash[0]: the venue has exactly one module, "
                    "a DistributionModule instance.",
     "deviation": "The pinned engine exposes no accessor for a venue's modules. venue_module_count is "
                  "the length of the modules list the runner passed to add_venue (harness "
                  "configuration, labelled as such). compare.py adds the engine-observed check that "
                  "every reported AccountState after the initial one sits at a DistributionModule "
                  "emission instant with exactly the emitted delta.",
     "effect": "A second cash-posting module would surface as an unexplained reported AccountState; "
               "a second module that posts nothing would not be detected."},
    {"id": "bars_mode_cannot_rehash_inputs",
     "sealed_text": "acceptance_criteria.preconditions[1]: the five frozen inputs hash-match at run "
                    "and at comparison time.",
     "deviation": "compare.py --bars has no data root, so it cannot re-hash the frozen inputs; it "
                  "reports that precondition check SKIPPED, and under v2 any skipped check makes the "
                  "verdict FAIL. The v2 verdict is published from --lean-data, which re-hashes them.",
     "effect": "--bars can no longer produce a v2 PASS; the README mode table describes v1."},
    {"id": "isolation_partially_observed",
     "sealed_text": "acceptance_criteria.preconditions[2]: isolation as v1 (bwrap --unshare-all, "
                    "cleared environment, read-only mounts, no network).",
     "deviation": "The run records, and compare.py checks, what the process can observe of that "
                  "isolation from inside: the network interfaces, the environment names and the "
                  "values of the documented variables, python -I (sys.flags.isolated), read-only "
                  "mounts for the harness source, the data root and the interpreter prefix, a user "
                  "namespace uid_map other than the initial one, and bwrap as pid 1 of the pid "
                  "namespace. The ipc, uts and cgroup namespace links are recorded but cannot be "
                  "compared with the host's from inside, and mounts other than those three are not "
                  "individually observed.",
     "effect": "An ipc, uts or cgroup namespace left shared, or a writable mount outside the three "
               "observed, would not be detected; those rest on the documented bwrap command."},
    {"id": "v2_output_paths",
     "sealed_text": "Neither README.md nor mapping-manifest-v2.json names paths for the v2 receipt "
                    "and verdict; the manifest keeps v1 bound to verdict.json.",
     "deviation": "The v2 results are published as receipt-v2.json and verdict-v2.json, and the "
                  "replay list as replay-history-v2.json; the v1 receipt.json and verdict.json are "
                  "kept unchanged.",
     "effect": "The gate row reading verdict.json is untouched by this run."},
    {"id": "manifest_evidence_class_token",
     "sealed_text": "mapping-manifest-v2.json evidence_class 'HIST (for the future replay); ...'.",
     "deviation": "compare.py binds the receipt's 'HIST' to the first token of that annotated value.",
     "effect": "None on the result."},
    {"id": "engine_log_level_info",
     "sealed_text": "acceptance_criteria.market_on_open_proxy[4]: no ERROR-level engine log line in "
                    "either run.",
     "deviation": "The engine logs at INFO (v1 used ERROR-only stdout) into a captured file, drained "
                  "with a sentinel line, so the scan is demonstrably non-empty and complete.",
     "effect": "None on execution; more log text is kept privately with its sha256."},
    {"id": "operator_declared_commit",
     "sealed_text": "README.md replay command.",
     "deviation": "The documented bwrap command gains --harness-commit, because the isolated run "
                  "cannot read Git, and --review-record when a retained review record exists; "
                  "local_source_sha256 remains the binding record.",
     "effect": "None on execution."},
]
REVIEW_RECORD_SCHEMA = "spy-parity-v2-harness-review/1"
REVIEWED_HARNESS_FILES = ("convert.py", "fixture_strategy.py", "distribution_module.py", "run.py",
                          "compare.py")
REPLAY_HISTORY = "replay-history-v2.json"
REPLAY_HISTORY_SCHEMA = "spy-parity-v2-replay-history/1"
DEVIATION_ACCEPTANCE = "deviation-acceptance-v2.json"
DEVIATION_ACCEPTANCE_FIELDS = ("schema_version", "deviation_id", "accepted_by", "accepted_utc",
                               "reviewed_harness_local_source_sha256", "statement")
# The values the documented bwrap replay sets. A value is recorded only when it
# equals the documented one; any other value (for example a host PATH naming a
# home directory) is replaced by UNDOCUMENTED_VALUE and fails compare.py.
ISOLATED_ENVIRONMENT_VALUES = {"LANG": "C.UTF-8", "PATH": "/usr/bin:/bin",
                               "PYTHONDONTWRITEBYTECODE": "1", "OPENBLAS_NUM_THREADS": "1",
                               "OMP_NUM_THREADS": "1"}
UNDOCUMENTED_VALUE = "<differs from the documented value; not recorded>"
LOG_LEVEL_RE = re.compile(r"\[(TRACE|DEBUG|INFO|WARN|WARNING|ERROR)\]")

WINDOW = {"symbol": "SPY", "start": "2019-12-02", "end": "2020-04-30"}
INSTRUMENT = {"instrument_id": "SPY.SIM", "symbol": "SPY", "venue": "SIM", "currency": "USD",
              "price_precision": 4, "price_increment": "0.0001", "size_precision": 0,
              "lot_size": 1, "bar_type": "SPY.SIM-1-HOUR-LAST-EXTERNAL"}
CASE = {"id": "one_zero", "initial_cash_usd": "100000", "target": "1", "sizing_buffer": "0.98",
        "entry_decision_date": "2019-12-31", "exit_decision_date": "2020-04-29",
        "fee_usd": "0", "slippage": "0", "currency": "USD"}
# Declared before execution as the authorized maximum. Only the fields that
# actually carry a freshly generated UUID4 are normalized; every other declared
# identity is retained raw and proved equal across the two runs.
DECLARED_ID_FIELDS = ("client_order_id", "venue_order_id", "init_id", "event_id", "last_trade_id",
                      "trade_id", "position_id", "account_id", "trader_id", "strategy_id",
                      "order_list_id", "exec_spawn_id")
APPLIED_ID_FIELDS = ("init_id", "event_id")
UUID4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CONVERT = _load("spy_parity_convert", SOURCE / "convert.py")
FIXTURE = _load("spy_parity_fixture", SOURCE / "fixture_strategy.py")
DISTRIBUTION = _load("spy_parity_distribution", SOURCE / "distribution_module.py")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def save(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n")


def number(value) -> Decimal:
    """Parse a native report value, including a currency suffix."""
    return Decimal(str(value).split()[0].replace(",", "").replace("_", ""))


def load_manifest(path: Path | None = None) -> dict:
    return json.loads(Path(path or SOURCE / MANIFEST_V2).read_text())


def effective_manifest(v2: dict, v1: dict) -> dict:
    """v2 rows plus the v1 rows v2 declares carried unchanged, by id."""
    carried = set(v2["carried_unchanged_from_v1"])
    rows = [row for row in v1["mappings"] if row["id"] in carried]
    if sorted(row["id"] for row in rows) != sorted(carried):
        raise ValueError("carried_v1_rows_missing")
    overlap = carried & {row["id"] for row in v2["mappings"]}
    if overlap:
        raise ValueError("carried_rows_overlap_v2:" + ",".join(sorted(overlap)))
    return {**v2, "mappings": rows + list(v2["mappings"])}


def load_bound_manifests() -> tuple[dict, dict]:
    """The sealed v2 manifest, and the v1 file checked against v2's record of it."""
    v2 = load_manifest(SOURCE / MANIFEST_V2)
    if v2.get("schema_version") != 2:
        raise ValueError("manifest_not_v2")
    v1_path = SOURCE / MANIFEST_V1
    if digest(v1_path) != v2["supersedes"]["sha256"]:
        raise ValueError("superseded_manifest_sha256_mismatch")
    return v2, effective_manifest(v2, json.loads(v1_path.read_text()))


def unsupported_mappings(manifest: dict) -> list:
    """The single source of truth: manifest rows whose status is unsupported."""
    return sorted(row["id"] for row in manifest["mappings"] if row["status"] == "unsupported")


def preregistered_mappings(manifest: dict) -> list:
    return sorted(row["id"] for row in manifest["mappings"] if row["status"] == "preregistered")


def known_short_sessions(manifest: dict) -> dict:
    row = next(r for r in manifest["mappings"] if r["id"] == "sessions_and_time")
    return row["known_short_sessions"]


def check_engine_binary(manifest: dict) -> dict:
    """The installed extension must be the one the manifest pins."""
    import nautilus_trader

    path = Path(nautilus_trader.__file__).resolve().parent / EXTENSION
    found = digest(path)
    if found != manifest["engine"]["extension_sha256"][EXTENSION]:
        raise ValueError("engine_extension_sha256_mismatch")
    return {EXTENSION: found}


def check_bound_inputs(manifest: dict, tolerances_path: Path) -> None:
    """Tolerances and frozen inputs must be the ones the v2 manifest froze."""
    if digest(tolerances_path) != manifest["tolerances"]["sha256"]:
        raise ValueError("tolerances_sha256_disagrees_with_manifest")
    if manifest["inputs"]["frozen_sha256"] != CONVERT.FROZEN_INPUT_SHA256:
        raise ValueError("frozen_inputs_disagree_with_manifest")


def daily_sessions(data_root: Path) -> list:
    """Every retained daily session (ISO dates), not only the replay window."""
    lines = CONVERT.read_zip_member(Path(data_root) / "equity/usa/daily/spy.zip", "spy.csv")
    return CONVERT.parse_daily_sessions(lines, "0001-01-01", "9999-12-31")


def distribution_events(data_root: Path) -> list:
    factor_rows = CONVERT.parse_factor_rows(
        (Path(data_root) / "equity/usa/factor_files/spy.csv").read_text())
    return DISTRIBUTION.derive_events(factor_rows, daily_sessions(data_root),
                                      WINDOW["start"], WINDOW["end"])


def load_review_record(path) -> dict | None:
    """The retained independent-review record named on the command line, if any.

    It must sit inside this checkout so compare.py can re-hash it later. The
    receipt records its path, sha256 and declared fields; compare.py judges it.
    """
    if path is None:
        return None
    resolved = Path(path).resolve()
    if REPO not in resolved.parents:
        raise ValueError("review_record_outside_checkout")
    blob = resolved.read_bytes()
    record = json.loads(blob.decode("utf-8"))
    if record.get("schema") != REVIEW_RECORD_SCHEMA:
        raise ValueError("review_record_schema")
    for field in ("reviewer", "completed_utc", "reviewed_commit", "reviewed_local_source_sha256",
                  "unresolved_findings"):
        if field not in record:
            raise ValueError("review_record_missing:" + field)
    return {"path": str(resolved.relative_to(REPO)), "sha256": hashlib.sha256(blob).hexdigest(),
            **{k: record[k] for k in ("reviewer", "completed_utc", "reviewed_commit",
                                      "reviewed_local_source_sha256", "unresolved_findings")}}


def load_replay_history() -> dict:
    """Every earlier v2 replay on the frozen inputs, copied into the receipt."""
    path = SOURCE / REPLAY_HISTORY
    history = json.loads(path.read_text())
    if history.get("schema") != REPLAY_HISTORY_SCHEMA or not isinstance(history.get("replays"), list):
        raise ValueError("replay_history_schema")
    return {"path": REPLAY_HISTORY, "sha256": digest(path), "replays": history["replays"]}


def load_deviation_acceptance() -> dict | None:
    """The gate owner's acceptance of ``first_v2_run_preceded_review``, if present.

    The harness never writes this file. When it exists at run time the receipt
    records its path, sha256 and fields; compare.py judges it.
    """
    path = SOURCE / DEVIATION_ACCEPTANCE
    if not path.is_file():
        return None
    blob = path.read_bytes()
    record = json.loads(blob.decode("utf-8"))
    if not isinstance(record, dict) or sorted(record) != sorted(DEVIATION_ACCEPTANCE_FIELDS):
        raise ValueError("deviation_acceptance_schema")
    return {"path": str(path.relative_to(REPO)), "sha256": hashlib.sha256(blob).hexdigest(), **record}


def read_only_mount(path) -> bool:
    """Whether ``path`` sits on a read-only mount, as the kernel reports it."""
    return bool(os.statvfs(path).f_flag & os.ST_RDONLY)


def _proc_text(path: str):
    try:
        return Path(path).read_text()
    except OSError:
        return None


def isolation_evidence(data_root: Path) -> dict:
    """What the process can observe of its own isolation (compare.py checks it).

    Records no interpreter path and no environment value other than a documented
    one, so a personal path or secret cannot enter the receipt.
    """
    links = {}
    try:
        for name in sorted(os.listdir("/proc/self/ns")):
            links[name] = os.readlink("/proc/self/ns/" + name)
    except OSError:
        links = None
    pid1 = _proc_text("/proc/1/comm")
    return {"network_interfaces": socket.if_nameindex(),
            "environment_names": sorted(os.environ),
            "environment_values": {k: (v if os.environ[k] == v else UNDOCUMENTED_VALUE)
                                   for k, v in ISOLATED_ENVIRONMENT_VALUES.items() if k in os.environ},
            "argv": sys.argv, "cwd": os.getcwd(),
            "python_flags_isolated": sys.flags.isolated,
            "read_only": {"harness_source": read_only_mount(SOURCE),
                          "data_root": read_only_mount(data_root),
                          "python_prefix": read_only_mount(sys.prefix)},
            "namespaces": {"uid_map": _proc_text("/proc/self/uid_map"), "pid": os.getpid(),
                           "pid1_comm": pid1.strip() if pid1 is not None else None,
                           "links": links},
            "unobserved": "ipc, uts and cgroup namespace separation cannot be compared with the "
                          "host from inside; see deviation isolation_partially_observed."}


def undeclared_differences(raw_differences) -> list:
    """Differing raw field paths whose leaf is not a normalized generated-id field."""
    return sorted({d for d in raw_differences
                   if d.rsplit(".", 1)[-1].split("[")[0] not in APPLIED_ID_FIELDS})


def sizing_limitation(intents, distribution_ledger) -> str:
    """The v1 sizing-rule limitation, with this run's own figures.

    Derived from the intents and the posted distribution ledger: each intent's
    decision_equity leaves out distribution cash the engine posted before it.
    """
    posted = [(int(d["utc_seconds"]), Decimal(str(d["amount"]))) for d in distribution_ledger
              if d.get("engine_posted") is True]
    parts, undersized = [], []
    for intent in intents:
        before = sum((amount for when, amount in posted if when <= int(intent["utc_seconds"])),
                     Decimal(0))
        if before == 0:
            continue
        equity = Decimal(str(intent["decision_equity"]))
        parts.append("the " + str(intent.get("reason")) + " intent records decision_equity "
                     + str(equity) + ", which leaves out " + str(before) + " of engine-posted "
                     "distributions (" + str(equity + before) + " with them)")
        if Decimal(str(intent.get("target", "0"))) != 0:
            undersized.append(str(intent.get("reason")))
    text = ("The unchanged v1 sizing rule sizes from the strategy's own fill-driven cash, which "
            "leaves out engine-posted distribution cash")
    text += (": " + "; ".join(parts) + ". " if parts else
             ": no intent of this run follows a nonzero posted distribution. ")
    text += ("Intents sized after a posted distribution are under-sized: " + ", ".join(undersized)
             + "." if undersized else
             "No nonzero-target intent follows a posted distribution, so this run's quantities are "
             "unaffected; a case that sizes after an ex-date would be under-sized.")
    return text


def scan_engine_log(text: str) -> dict:
    """Count log lines by level; any ERROR line refuses a v2 PASS in compare.py."""
    levels, errors = {}, []
    for line in text.splitlines():
        match = LOG_LEVEL_RE.search(line)
        if match:
            levels[match.group(1)] = levels.get(match.group(1), 0) + 1
            if match.group(1) == "ERROR":
                errors.append(line)
    return {"lines": len(text.splitlines()), "lines_by_level": dict(sorted(levels.items())),
            "error_lines": len(errors),
            "negative_cash_lines": sum(1 for line in text.splitlines() if NEGATIVE_CASH_TEXT in line),
            "error_line_sha256": [digest_text(line) for line in errors]}


class CapturedOutput:
    """Redirect the process's stdout and stderr file descriptors to a file.

    The engine's Rust logger writes to the file descriptors directly, so this is
    the only complete capture of its output without changing its configuration.
    """

    def __init__(self, path: Path):
        self.path = path

    def __enter__(self):
        sys.stdout.flush()
        sys.stderr.flush()
        self.handle = open(self.path, "wb")
        self.saved = (os.dup(1), os.dup(2))
        os.dup2(self.handle.fileno(), 1)
        os.dup2(self.handle.fileno(), 2)
        return self

    def __exit__(self, *exc):
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(self.saved[0], 1)
        os.dup2(self.saved[1], 2)
        for fd in self.saved:
            os.close(fd)
        self.handle.close()
        return False


def check_frozen_plan() -> dict:
    """Bind this fixture to the frozen historical plan rather than restating it."""
    plan_path = HISTORICAL / "plan.json"
    if digest(plan_path) != FROZEN_PLAN_SHA256:
        raise ValueError("frozen_plan_hash_mismatch")
    plan = json.loads(plan_path.read_text())
    spec = next(c for c in plan["cases"] if c["id"] == CASE["id"])
    if (spec["target"] != CASE["target"] or spec["fee_usd"] != CASE["fee_usd"]
            or spec["slippage"] != CASE["slippage"] or spec["adaptive"] or spec["reject"]):
        raise ValueError("case_specification_drift")
    if (plan["start"] != WINDOW["start"] or plan["end"] != WINDOW["end"]
            or plan["initial_cash_usd"] != CASE["initial_cash_usd"]
            or plan["requested_target_sizing_multiplier"] != CASE["sizing_buffer"]):
        raise ValueError("plan_window_drift")
    if CASE["entry_decision_date"].replace("-", "") not in plan["entry_decision"].replace("-", ""):
        raise ValueError("entry_decision_drift")
    if CASE["exit_decision_date"].replace("-", "") not in plan["exit_decision"].replace("-", ""):
        raise ValueError("exit_decision_drift")
    return {"path": "blueprints/us-equities/historical-simulation/plan.json",
            "sha256": FROZEN_PLAN_SHA256, "case": spec}


def normalize(value, counters, key=None):
    """Replace generated UUID4 identities with their ordinal, recursively.

    The format is validated before substitution so a non-UUID value can never be
    normalized away. Timing, prices, quantities, fees, distributions, position
    transitions and decision order are never touched.
    """
    if isinstance(value, list):
        return [normalize(item, counters, key) for item in value]
    if isinstance(value, dict):
        return {k: normalize(v, counters, k) for k, v in value.items()}
    if key in APPLIED_ID_FIELDS and value is not None:
        text = str(value)
        if not UUID4_RE.match(text):
            raise ValueError("unexpected_generated_id_format:" + key)
        bucket = counters.setdefault(key, {})
        bucket.setdefault(text, len(bucket) + 1)
        return key + "#" + str(bucket[text])
    return value


def field_differences(left, right, path="") -> list:
    """Every field path whose value differs between the two runs."""
    if isinstance(left, dict) and isinstance(right, dict):
        keys = sorted(set(left) | set(right))
        found = []
        for key in keys:
            found += field_differences(left.get(key), right.get(key),
                                       path + ("." if path else "") + str(key))
        return found
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return [path + "[len]"]
        found = []
        for index, (a, b) in enumerate(zip(left, right)):
            found += field_differences(a, b, path + "[" + str(index) + "]")
        return found
    return [] if left == right else [path]


def account_events(account, currency) -> list:
    """Every native AccountState on the venue account, in engine order."""
    found = []
    for event in account.events:
        balances = [b for b in event.balances if str(b.currency) == str(currency)]
        if len(balances) != 1:
            raise ValueError("account_event_balance_shape")
        found.append({"ts_event_ns": int(event.ts_event), "reported": bool(event.is_reported),
                      "total": str(number(balances[0].total)), "free": str(number(balances[0].free)),
                      "locked": str(number(balances[0].locked))})
    return found


def run_once(rows, events, out: Path, label: str) -> dict:
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogColor, LogLevel, logger_flush, logger_log
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig
    from nautilus_trader.model import (AccountType, ClientOrderId, Currency, Equity, InstrumentId,
                                       Money, OmsType, Price, Quantity, Symbol, Venue)

    random.seed(SEED)
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    usd = Currency.from_str(INSTRUMENT["currency"])
    venue = Venue(INSTRUMENT["venue"])
    equity = Equity(InstrumentId.from_str(INSTRUMENT["instrument_id"]), Symbol(INSTRUMENT["symbol"]),
                    usd, INSTRUMENT["price_precision"], Price.from_str(INSTRUMENT["price_increment"]),
                    0, 0, lot_size=Quantity.from_int(INSTRUMENT["lot_size"]))
    bars = CONVERT.to_bars(rows, INSTRUMENT["bar_type"], INSTRUMENT["price_precision"],
                           INSTRUMENT["size_precision"])
    strategy_class = FIXTURE.build_strategy(equity.id, INSTRUMENT["bar_type"], rows, CASE,
                                            [e["ex_instant_ns"] for e in events])
    module = DISTRIBUTION.build_module(events, INSTRUMENT["instrument_id"], INSTRUMENT["currency"])
    modules = [module]
    log_path = out / "engine.log"
    # Bound before the try so an engine failure surfaces as itself, never as a
    # NameError from the post-run block, and never masked by dispose().
    strategy = raw = reports = result = native_events = None
    open_positions = open_orders = final_views = None
    failure = None
    with CapturedOutput(log_path):
        engine = BacktestEngine(BacktestEngineConfig(
            logging=LoggerConfig(stdout_level=LogLevel.INFO, is_colored=False)))
        try:
            engine.add_venue(venue, getattr(OmsType, VENUE["oms_type"]),
                             getattr(AccountType, VENUE["account_type"]),
                             [Money(Decimal(CASE["initial_cash_usd"]), usd)], base_currency=usd,
                             fill_model=VENUE["fill_model"], fee_model=VENUE["fee_model"],
                             latency_model=VENUE["latency_model"], modules=modules,
                             reject_stop_orders=VENUE["reject_stop_orders"],
                             support_contingent_orders=VENUE["support_contingent_orders"],
                             use_random_ids=VENUE["use_random_ids"],
                             bar_execution=VENUE["bar_execution"],
                             bar_adaptive_high_low_ordering=VENUE["bar_adaptive_high_low_ordering"],
                             frozen_account=VENUE["frozen_account"])
            engine.add_instrument(equity)
            engine.add_data(bars)
            strategy = strategy_class()
            engine.add_strategy(strategy)
            engine.run()
            result = engine.get_result()
            reports = {"account": engine.generate_account_report(venue=venue),
                       "positions": engine.generate_positions_report(),
                       "fills": engine.generate_order_fills_report()}
            for name, report in reports.items():
                report.to_csv(out / (name + ".csv"))
            raw = {name: json.loads(report.to_json(orient="records")) for name, report in reports.items()}
            save(out / "reports.private.json", raw)
            native_events = account_events(engine.cache.account_for_venue(venue), usd)
            open_positions = len(engine.cache.positions_open())
            open_orders = len(engine.cache.orders_open())
            final_views = {}
            for client_order_id in strategy.submitted:
                order = engine.cache.order(ClientOrderId(client_order_id))
                if order is None:
                    raise ValueError("submitted_order_not_in_cache:" + client_order_id)
                final_views[client_order_id] = FIXTURE.engine_order_view(order.to_dict())
        except BaseException as error:  # noqa: BLE001 - the original failure is re-raised
            failure = error
            raise
        finally:
            try:
                engine.dispose()
            except Exception as dispose_error:
                if failure is None:
                    raise
                failure.add_note("engine.dispose() also failed: " + repr(dispose_error))
            # The engine logs from a writer thread in order. Log one sentinel
            # after dispose and wait until it reaches the file, so every line of
            # this run is captured before the file descriptors are restored.
            logger_flush()
            sentinel = "spy-parity capture end " + label
            logger_log(LogLevel.INFO, LogColor.NORMAL, "SpyParityRunner", sentinel)
            logger_flush()
            deadline = time.monotonic() + 30
            while sentinel not in log_path.read_text(encoding="utf-8", errors="replace"):
                if time.monotonic() > deadline:
                    raise ValueError("engine_log_capture_incomplete:" + label)
                time.sleep(0.01)

    log_scan = scan_engine_log(log_path.read_text(encoding="utf-8", errors="replace"))
    if strategy is None or raw is None or result is None or final_views is None:
        raise ValueError("engine_run_incomplete:" + label)
    if module.errors:
        # A late emission or an unapplied adjustment is a module error; the
        # preregistration refuses the run rather than publishing it.
        raise ValueError("distribution_module_failed:" + ";".join(module.errors))
    FIXTURE.check_run_integrity(strategy.errors, strategy.bars_seen, len(rows), result.iterations)
    FIXTURE.check_final_state(strategy.pending, open_orders, open_positions, strategy.position)
    FIXTURE.check_causality(strategy.intents, strategy.fills)
    ledger = FIXTURE.posted_distribution_ledger(module.emissions, module.acknowledgements)
    external = FIXTURE.distribution_ledger(
        [{"ex_date": e["ex_date"], "utc_seconds": e["ex_instant_utc_seconds"],
          "per_share": e["per_share"]} for e in events], strategy.fills)
    cash = FIXTURE.cash_ledger(Decimal(CASE["initial_cash_usd"]), strategy.fills, ledger)
    oco_pairs = FIXTURE.attach_engine_views(strategy.oco_pairs, strategy.accepted_orders, final_views)
    native_balances = [str(number(row["total"])) for row in raw["account"]]
    module_record = {"class": type(module).__name__, "process_calls": module.process_calls,
                     "resets": module.resets, "venue_module_count": len(modules),
                     "calls_at_event_instants_ns": module.calls_at_event_instants,
                     "emissions": module.emissions, "acknowledgements": module.acknowledgements,
                     "errors": module.errors, "pending_at_end": [e["ex_date"] for e in module.pending]}
    counters = {}
    economic = {"intents": strategy.intents, "fills": strategy.fills,
                "oco_pairs": oco_pairs,
                "order_events": normalize(strategy.order_events, counters),
                "native_account_totals": native_balances,
                "native_account_events": native_events,
                "distribution_module": module_record,
                "alerts_fired": strategy.alerts_fired,
                "native_fills": normalize(raw["fills"], counters),
                "positions": normalize(raw["positions"], counters)}
    normalized_text = json.dumps(economic, sort_keys=True, default=str)
    record = {
        "label": label,
        "_raw_reports": raw,
        "processed_bars": result.iterations,
        "open_positions": open_positions,
        "open_orders": open_orders,
        "pending_intent": strategy.pending,
        "strategy_callback_errors": strategy.errors,
        "bars_seen": strategy.bars_seen,
        "run_integrity_checked": True,
        "final_state_checked": True,
        "final_quantity": str(strategy.position),
        "native_end_cash_usd": native_balances[-1] if native_balances else None,
        "native_account_events": len(native_balances),
        "fees_usd": str(sum((Decimal(f["fee"]) for f in strategy.fills), Decimal(0))),
        "intents": strategy.intents,
        "fills": strategy.fills,
        "oco_pairs": oco_pairs,
        "order_events": strategy.order_events,
        "alerts_registered": strategy.alerts_registered,
        "alerts_fired": strategy.alerts_fired,
        "distribution_module": module_record,
        "native_account_event_rows": native_events,
        "distribution_ledger": ledger,
        "external_distribution_cross_check": external,
        "dividend_cash_usd": str(sum((Decimal(d["amount"]) for d in ledger), Decimal(0))),
        "cash_ledger": cash,
        "reconciled_end_cash_usd": cash[-1]["cash"] if cash else CASE["initial_cash_usd"],
        "buying_power_events": strategy.buying_power_events,
        "latch_events": strategy.latch_events,
        "engine_log_scan": log_scan,
        "engine_log_sha256": digest(log_path),
        "raw_report_sha256": {name: digest(out / (name + ".csv")) for name in reports},
        "raw_reports_json_sha256": digest(out / "reports.private.json"),
        "normalized_economic_sha256": digest_text(normalized_text),
    }
    save(out / "summary.json", {k: v for k, v in record.items() if k != "_raw_reports"})
    return record


PER_RUN_DETAIL = ("intents", "fills", "cash_ledger", "distribution_ledger", "_raw_reports",
                  "oco_pairs", "order_events", "distribution_module", "native_account_event_rows",
                  "external_distribution_cross_check", "alerts_registered", "alerts_fired")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean-data", type=Path, required=True,
                        help="Retained LEAN Data root holding the frozen SPY inputs")
    parser.add_argument("--out", type=Path, required=True, help="Fresh private output directory")
    parser.add_argument("--tolerances", type=Path, default=SOURCE / "tolerances.json")
    parser.add_argument("--review-record", type=Path, default=None,
                        help="Retained independent-review record (JSON, schema " + REVIEW_RECORD_SCHEMA +
                             ") inside this checkout; compare.py judges it")
    parser.add_argument("--harness-commit", default=None,
                        help="Commit of the checkout being run, recorded as declared by the operator "
                             "(the isolated run cannot read Git); local_source_sha256 binds the files")
    args = parser.parse_args()

    started_utc = datetime.now(timezone.utc).isoformat()
    installed = importlib.metadata.version("nautilus_trader")
    if installed != "2.0.0rc5":
        raise ValueError("native_version_mismatch:" + installed)
    os.umask(0o077)
    args.out.mkdir(mode=0o700, parents=True, exist_ok=False)

    frozen_plan = check_frozen_plan()
    review = load_review_record(args.review_record)
    acceptance = load_deviation_acceptance()
    history = load_replay_history()
    manifest_v2, manifest = load_bound_manifests()
    extension = check_engine_binary(manifest_v2)
    check_bound_inputs(manifest_v2, args.tolerances)
    conversion = CONVERT.convert(args.lean_data, WINDOW["symbol"], WINDOW["start"], WINDOW["end"],
                                 known_short_sessions(manifest))
    events = distribution_events(args.lean_data)
    rows_path = args.out / "converted-rows.private.json"
    save(rows_path, conversion["rows"])
    tolerances = json.loads(args.tolerances.read_text())
    preregistered_events = next(
        row for row in manifest_v2["mappings"] if row["id"] == "distributions_and_cash"
    )["mechanism_rules"]["window_events_for_one_zero"]
    derived_projection = [{"factor_row_date": e["factor_row_date"], "ex_date": e["ex_date"],
                           "ex_instant_utc_seconds": e["ex_instant_utc_seconds"], "pf0": e["pf0"],
                           "pf1": e["pf1"], "ref0": e["ref0"], "per_share": e["per_share"]}
                          for e in events]

    runs = [run_once(conversion["rows"], events, args.out / label, label)
            for label in ("run-1", "run-2")]
    raw_differences = field_differences(runs[0]["_raw_reports"], runs[1]["_raw_reports"])
    undeclared = undeclared_differences(raw_differences)
    determinism = {
        "normalized_economic_sha256_equal":
            runs[0]["normalized_economic_sha256"] == runs[1]["normalized_economic_sha256"],
        "raw_report_sha256_equal": runs[0]["raw_report_sha256"] == runs[1]["raw_report_sha256"],
        "raw_field_paths_differing": sorted(set(raw_differences)),
        "undeclared_differing_fields": undeclared,
        "declared_id_fields": list(DECLARED_ID_FIELDS),
        "applied_id_fields": list(APPLIED_ID_FIELDS),
        "normalization_rule": "Only freshly generated UUID4 identities are replaced by their ordinal, "
                              "after format validation. Timing, prices, quantities, fees, "
                              "distributions, transitions and decision order are never normalized.",
    }
    equal = determinism["normalized_economic_sha256_equal"] and not undeclared
    primary = runs[0]

    receipt = {
        "schema_version": 2,
        "id": "spy-parity-one-zero-v2",
        "gate": "G-a",
        "case": CASE["id"],
        "evidence_class": EVIDENCE_CLASS,
        "classification": "local historical replay on retained bundled sample data; not an unchanged "
                          "upstream test, a point-in-time dataset or any broker execution",
        "started_utc": started_utc,
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "harness_commit": {"value": args.harness_commit,
                           "source": "declared by the operator on the command line; the isolated run "
                                     "cannot read Git, so local_source_sha256 is the binding record"},
        "engine": {"package": "nautilus_trader", "version": installed,
                   "upstream_commit_pin": manifest_v2["engine"]["upstream_commit_pin"],
                   "extension_sha256": extension,
                   "python": sys.version.split()[0]},
        "frozen_plan": frozen_plan,
        "case_configuration": {**CASE, "instrument": INSTRUMENT, "window": WINDOW, "seed": SEED,
                               **VENUE, "venue_modules": [module_class_name()],
                               "determinism_note": "one_zero configures no stochastic fill, fee or "
                                                   "latency model; the seed is recorded and applied "
                                                   "but no sampled component is exercised."},
        "mapping_manifest": {"path": MANIFEST_V2, "sha256": digest(SOURCE / MANIFEST_V2),
                             "schema_version": manifest_v2["schema_version"]},
        "superseded_manifest": {"path": MANIFEST_V1, "sha256": digest(SOURCE / MANIFEST_V1),
                                "carried_rows": manifest_v2["carried_unchanged_from_v1"]},
        "preregistration": {"path": "PREREGISTRATION-v2.md",
                            "sha256": digest(SOURCE / "PREREGISTRATION-v2.md")},
        "tolerances": {"path": str(args.tolerances.name), "sha256": digest(args.tolerances),
                       "limits": tolerances["limits"], "status": tolerances["status"]},
        "local_source_sha256": {name: digest(SOURCE / name) for name in
                                ("convert.py", "fixture_strategy.py", "distribution_module.py",
                                 "run.py", "compare.py", MANIFEST_V1, MANIFEST_V2,
                                 "tolerances.json")
                                if (SOURCE / name).is_file()},
        "distribution_module": {"class": module_class_name(), "source": "distribution_module.py",
                                "source_sha256": digest(SOURCE / "distribution_module.py"),
                                "venue_module_count": primary["distribution_module"]["venue_module_count"],
                                "venue_module_count_source":
                                    "length of the modules list passed to add_venue (harness "
                                    "configuration); the pinned engine exposes no accessor for a "
                                    "venue's modules",
                                "events": events,
                                "derived_events_equal_preregistered_window_events":
                                    derived_projection == preregistered_events,
                                "process_calls": primary["distribution_module"]["process_calls"],
                                "resets": primary["distribution_module"]["resets"],
                                "calls_at_event_instants_ns":
                                    primary["distribution_module"]["calls_at_event_instants_ns"],
                                "emissions": primary["distribution_module"]["emissions"],
                                "acknowledgements": primary["distribution_module"]["acknowledgements"],
                                "errors": primary["distribution_module"]["errors"],
                                "pending_at_end": primary["distribution_module"]["pending_at_end"]},
        "inputs": {"data_root": str(args.lean_data), "sha256": conversion["input_hashes"],
                   "decoded": conversion["decoded_inputs"],
                   "price_encoding": conversion["price_encoding"],
                   "volume_encoding": conversion["volume_encoding"],
                   "session_source": conversion["session_source"],
                   "forward_filled_rows": conversion["forward_filled_rows"],
                   "map_rows": conversion["map_rows"]},
        "conversion": conversion["counts"],
        "attribution_evidence": {
            "file": rows_path.name,
            "converted_rows_sha256": digest(rows_path),
            "serialization": "json.dumps(rows, indent=2, sort_keys=True, default=str) + newline",
            "note": "compare.py refuses a --bars file whose digest differs, and re-hashes its own "
                    "re-derivation under --lean-data against this value. Under v2 the rows are "
                    "evidence for the per-event gap and open-price checks, never for an attribution.",
        },
        "derived_distributions_v1_rule": conversion["distributions"],
        "unsupported_mappings": unsupported_mappings(manifest),
        "preregistered_mappings": preregistered_mappings(manifest),
        "runs": [{k: v for k, v in run.items() if k not in PER_RUN_DETAIL} for run in runs],
        "two_run_records_equal": equal,
        "two_run_determinism": determinism,
        "intents": primary["intents"],
        "fills": primary["fills"],
        "oco_pairs": primary["oco_pairs"],
        "order_events": primary["order_events"],
        "alerts_registered": primary["alerts_registered"],
        "alerts_fired": primary["alerts_fired"],
        "native_account_event_rows": primary["native_account_event_rows"],
        "cash_ledger": primary["cash_ledger"],
        "distribution_ledger": primary["distribution_ledger"],
        "external_distribution_cross_check": primary["external_distribution_cross_check"],
        "dividend_cash_usd": primary["dividend_cash_usd"],
        "fees_usd": primary["fees_usd"],
        "native_end_cash_usd": primary["native_end_cash_usd"],
        "reconciled_end_cash_usd": primary["reconciled_end_cash_usd"],
        "final_quantity": primary["final_quantity"],
        "buying_power_events": primary["buying_power_events"],
        "latch_events": primary["latch_events"],
        "buying_power_and_latch_note": "one_zero requests 1x with no leverage and no adaptive rule, so "
                                       "empty lists are the expected observation, not evidence of "
                                       "margin-model equivalence.",
        "isolation": isolation_evidence(args.lean_data),
        "preconditions": {
            "review": review,
            "review_note": "None means no retained independent review preceded this run.",
            "deviation_acceptance": acceptance,
            "deviation_acceptance_note": "None means deviation-acceptance-v2.json (the gate owner's "
                                         "acceptance of first_v2_run_preceded_review) was absent at "
                                         "run time.",
            "prior_v2_replays": history,
        },
        "preregistration_deviations": PREREGISTRATION_DEVIATIONS,
        "limitations": [
            "The market-on-open proxy equals LEAN's MarketOnOpenFill only inside the manifest's "
            "faithfulness_domain (open differs from the decision close by at least one tick, the "
            "quantity fits the open tick and the fill does not overdraw the CASH account); "
            "compare.py checks each event.",
            "The DistributionModule posts cash only; bar prices stay raw-normalized. Payable dates, "
            "withholding and short-position debits are outside one_zero.",
            "Bundled sample bytes are not an entitled, point-in-time or market-wide dataset.",
            sizing_limitation(primary["intents"], primary["distribution_ledger"]),
            "Each OCO leg's harness submission fields are the strategy's own record; compare.py "
            "judges the native OCO structure from engine_at_accept and engine_final, the order as "
            "the engine's cache serializes it at OrderAccepted and at run end.",
        ],
    }
    save(args.out / "receipt.json", receipt)
    print(json.dumps({"case": CASE["id"], "evidence_class": EVIDENCE_CLASS,
                      "two_run_records_equal": equal,
                      "processed_bars": primary["processed_bars"],
                      "fills": len(primary["fills"]),
                      "dividend_cash_usd": primary["dividend_cash_usd"],
                      "native_end_cash_usd": primary["native_end_cash_usd"],
                      "reconciled_end_cash_usd": primary["reconciled_end_cash_usd"],
                      "engine_error_lines": [r["engine_log_scan"]["error_lines"] for r in runs],
                      "unsupported_mappings": receipt["unsupported_mappings"],
                      "receipt": str(args.out / "receipt.json")}, sort_keys=True))


def module_class_name() -> str:
    return DISTRIBUTION.MODULE_CLASS_NAME


if __name__ == "__main__":
    main()
