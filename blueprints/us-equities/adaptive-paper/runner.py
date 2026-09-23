"""Bounded paper lane: preflight, native strategy execution, durable reconciliation.

CLI credentials are loaded only from the explicitly selected private env file.
Default behavior never submits an order; `paper` is an explicit bounded trial.
"""
from __future__ import annotations

import argparse
import ast
import asyncio
from dataclasses import asdict, replace
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import time

from leverage import LeveragePolicyError, next_lower_rung_ceiling, validate_leverage_policy
from safety import Ledger, Quote, RiskLimits, SafetyError, account_lock_fingerprint, DEFAULT_STOP
from sessions import (DEFAULT_SESSION_POLICY, SessionKind, boundary_receipt, extended_session_close,
                     must_end_flat, session_at, validate_session_policy)
from strategies import AdaptivePolicy, PolicyConfig, RegimeSelector, SelectorConfig, limit_price
from transport import AlpacaPaperTransport, DATA_FEEDS, TransportError, RejectedSubmission, preflight

SOURCE = Path(__file__).resolve().parent
LAST_OUTPUT = None


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(data, stream, indent=2, sort_keys=True, default=str)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _inside_git_worktree(path):
    """Walk parents for a `.git` entry (directory in a normal clone, file in
    a linked worktree). Resolved so a symlink cannot hide the real location."""
    current = path.parent
    while True:
        if (current / ".git").exists() or (current / ".git").is_symlink():
            return True
        parent = current.parent
        if parent == current:
            return False
        current = parent


def credentials(path):
    """Fail closed on a paper-credential env file with unsafe permissions,
    ownership, or location before any content is read. File contents are
    never included in a raised error or log."""
    resolved = Path(path).resolve()
    try:
        info = resolved.stat()
    except OSError:
        raise SafetyError("credential_file_permissions: cannot stat the env file; "
                           "create it at a private path outside this repository with `chmod 600`")
    if info.st_uid != os.getuid():
        raise SafetyError("credential_file_permissions: env file is not owned by the current user; "
                           "chown it to your own account (never share a paper credential file)")
    if info.st_mode & 0o777 != 0o600:
        raise SafetyError("credential_file_permissions: env file mode must be exactly 0600; "
                           f"run `chmod 600 {resolved.name}`")
    if _inside_git_worktree(resolved):
        raise SafetyError("credential_file_permissions: env file must live outside any Git worktree; "
                           "move it to a private, non-repository path (e.g. under your home config directory)")
    result = {}
    for line in resolved.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.removeprefix("export ").split("=", 1)
        if name.strip() in {"APCA_API_KEY_ID", "APCA_API_SECRET_KEY"}:
            values = shlex.split(value, comments=True)
            if len(values) != 1:
                raise ValueError("invalid_scoped_credential")
            result[name.strip()] = values[0]
    if len(result) != 2 or not all(result.values()):
        raise ValueError("missing_paper_credentials")
    return result["APCA_API_KEY_ID"], result["APCA_API_SECRET_KEY"]


REGISTRY_REQUIRED_FIELDS = {"id", "module", "receipt_path", "receipt_sha256", "evidence_class", "sessions", "enabled"}
REGISTRY_EVIDENCE_CLASSES = {"SYN", "HIST", "PAPER"}
REGISTRY_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _source_hashes_prefix(source_hashes):
    """The repo-root-relative directory prefix this engine's files are pinned
    under in source-hashes.json, derived from the always-present runner.py
    entry rather than hardcoded, so a scratch/test source-hashes.json using
    bare "name.py" keys (prefix "") also works."""
    for key in source_hashes:
        if key.endswith("/runner.py"):
            return key[: -len("runner.py")]
    return ""


def load_registry(path):
    """Validate the strategy-pool registry; raise ValueError on any defect.

    Never executes a byte of the referenced module: a registry entry's
    module is only checked to (a) exist as a file, (b) parse as valid Python
    via `ast.parse` (a syntax check, not execution) and (c) have its sha256
    already pinned in this engine directory's source-hashes.json -- i.e. it
    must be a file whose content someone already reviewed and hash-pinned,
    not arbitrary code a malformed registry entry could point at and run.
    """
    path = Path(path)
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise ValueError("invalid_registry_json") from error
    if not isinstance(data, dict) or data.get("schema_version") != 1 or isinstance(data.get("schema_version"), bool):
        raise ValueError("invalid_registry_schema")
    entries = data.get("strategies")
    if not isinstance(entries, list) or not entries:
        raise ValueError("invalid_registry_entries")
    source_dir = path.resolve().parent
    hashes_path = source_dir / "source-hashes.json"
    try:
        source_hashes = json.loads(hashes_path.read_text()) if hashes_path.is_file() else {}
    except (OSError, ValueError) as error:
        raise ValueError("invalid_source_hashes_json") from error
    if not isinstance(source_hashes, dict):
        raise ValueError("invalid_source_hashes_json")
    prefix = _source_hashes_prefix(source_hashes)
    seen_ids = set()
    validated = []
    for entry in entries:
        if not isinstance(entry, dict) or not REGISTRY_REQUIRED_FIELDS.issubset(entry):
            raise ValueError("invalid_registry_entry_fields")
        identifier = entry["id"]
        if not isinstance(identifier, str) or not REGISTRY_IDENTIFIER.fullmatch(identifier) or identifier in seen_ids:
            raise ValueError("invalid_or_duplicate_registry_id")
        seen_ids.add(identifier)
        module = entry["module"]
        if not isinstance(module, str) or not REGISTRY_IDENTIFIER.fullmatch(module):
            raise ValueError(f"invalid_registry_module_name:{identifier}")
        module_path = source_dir / f"{module}.py"
        if not module_path.is_file():
            raise ValueError(f"registry_module_missing:{identifier}")
        module_bytes = module_path.read_bytes()
        try:
            ast.parse(module_bytes, filename=str(module_path))
        except SyntaxError as error:
            raise ValueError(f"registry_module_not_valid_python:{identifier}") from error
        module_key = f"{prefix}{module}.py"
        pinned = source_hashes.get(module_key)
        if not isinstance(pinned, str) or not re.fullmatch(r"[0-9a-f]{64}", pinned):
            raise ValueError(f"registry_module_not_pinned:{identifier}")
        if hashlib.sha256(module_bytes).hexdigest() != pinned:
            raise ValueError(f"registry_module_hash_mismatch:{identifier}")
        digest = entry["receipt_sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"invalid_registry_receipt_hash:{identifier}")
        receipt_path = entry["receipt_path"]
        if not isinstance(receipt_path, str) or receipt_path.startswith("/") or ".." in Path(receipt_path).parts:
            raise ValueError(f"invalid_registry_receipt_path:{identifier}")
        resolved_receipt = (source_dir / receipt_path).resolve()
        if not resolved_receipt.is_relative_to(source_dir) or not resolved_receipt.is_file():
            raise ValueError(f"missing_registry_receipt:{identifier}")
        receipt_bytes = resolved_receipt.read_bytes()
        if hashlib.sha256(receipt_bytes).hexdigest() != digest:
            raise ValueError(f"registry_receipt_hash_mismatch:{identifier}")
        if entry["evidence_class"] not in REGISTRY_EVIDENCE_CLASSES:
            raise ValueError(f"invalid_registry_evidence_class:{identifier}")
        sessions = entry["sessions"]
        if not isinstance(sessions, list) or not sessions or not all(isinstance(s, str) and s for s in sessions):
            raise ValueError(f"invalid_registry_sessions:{identifier}")
        if not isinstance(entry["enabled"], bool):
            raise ValueError(f"invalid_registry_enabled:{identifier}")
        try:
            receipt = json.loads(receipt_bytes)
        except ValueError as error:
            raise ValueError(f"invalid_registry_receipt_json:{identifier}") from error
        if isinstance(receipt, dict) and receipt.get("kind") == "golden_decision_fixture":
            fixture_relative = receipt.get("golden_fixture")
            fixture_sha = receipt.get("golden_fixture_sha256")
            case_count = receipt.get("case_count")
            if (not isinstance(fixture_relative, str) or fixture_relative.startswith("/")
                    or ".." in Path(fixture_relative).parts
                    or not isinstance(fixture_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", fixture_sha)
                    or not isinstance(case_count, int) or isinstance(case_count, bool) or case_count < 1):
                raise ValueError(f"invalid_registry_golden_fixture_receipt:{identifier}")
            repo_root = source_dir.parents[2] if len(source_dir.parents) > 2 else source_dir
            fixture_path = (repo_root / fixture_relative).resolve()
            if not fixture_path.is_relative_to(repo_root) or not fixture_path.is_file():
                raise ValueError(f"missing_registry_golden_fixture:{identifier}")
            fixture_bytes = fixture_path.read_bytes()
            if hashlib.sha256(fixture_bytes).hexdigest() != fixture_sha:
                raise ValueError(f"registry_golden_fixture_hash_mismatch:{identifier}")
            try:
                fixture_data = json.loads(fixture_bytes)
            except ValueError as error:
                raise ValueError(f"invalid_registry_golden_fixture_json:{identifier}") from error
            if not isinstance(fixture_data, dict) or len(fixture_data) != case_count:
                raise ValueError(f"registry_golden_fixture_case_count_mismatch:{identifier}")
        validated.append(dict(entry))
    return validated


class RegistrySpec:
    """Minimal selector.StrategySpec built from a validated registry entry.

    `propose` is intentionally a no-op placeholder: with the single shipped
    v1 pool member, AdaptivePolicy._evaluate_pool only needs `id` to decide
    what to ask the selector about (see strategies.py); no registry entry is
    accepted as a live rotation candidate yet (registry.json's evidence_class
    stays "SYN" until an independently qualified HIST/paper receipt exists).
    """
    def __init__(self, entry):
        self.id = entry["id"]
        self.receipt_sha256 = entry["receipt_sha256"]
        self.sessions = tuple(entry["sessions"])
        self.evidence_class = entry["evidence_class"]
        self.regime_affinity = ()

    def propose(self, decision_inputs):
        return {}


def strategy_pool_and_selector(config, registry_entries, *, session="regular"):
    """Build (strategy_pool, selector) from config["rotation"] + the already
    load_registry()-validated entries. Off by default: `rotation` missing or
    `{"enabled": false}` returns `((), None)`, which is exactly the input
    that makes strategies.AdaptivePolicy take its byte-identical v1 path.
    """
    rotation = config.get("rotation", {"enabled": False})
    if not isinstance(rotation, dict) or not isinstance(rotation.get("enabled"), bool):
        raise ValueError("invalid_rotation_config")
    if not rotation["enabled"]:
        return (), None
    allow_synthetic = rotation.get("allow_synthetic", False)
    if not isinstance(allow_synthetic, bool):
        raise ValueError("invalid_rotation_config")
    pool = tuple(RegistrySpec(entry) for entry in registry_entries
                if entry["enabled"] and session in entry["sessions"])
    if not pool:
        raise ValueError("rotation_enabled_with_no_eligible_strategy")
    # HIST/PAPER entries are always eligible; a pool made up entirely of
    # unaccepted SYN entries needs an explicit, separate opt-in -- rotation
    # being on must not silently start trading through synthetic-only
    # candidates (see blueprints/us-equities/acceptance-wave/research-protocol.json's
    # regime_selector field for what "accepted" requires).
    if not allow_synthetic and all(spec.evidence_class == "SYN" for spec in pool):
        raise ValueError("rotation_enabled_with_only_synthetic_strategies")
    selector_config = rotation.get("selector", {})
    if not isinstance(selector_config, dict):
        raise ValueError("invalid_rotation_selector_config")
    try:
        selector = RegimeSelector(SelectorConfig(**selector_config))
    except TypeError as error:
        raise ValueError("invalid_rotation_selector_config") from error
    return pool, selector


def load_config(path, *, registry_path=None):
    c = json.loads(Path(path).read_text())
    if c["feed"] not in DATA_FEEDS:
        raise ValueError("unqualified_data_feed")
    # G-e: leverage above 1x is refused exactly as before UNLESS a
    # "leverage_policy" block is present, in which case it is deferred to
    # validate_leverage_policy below (which raises its own, more specific
    # LeveragePolicyError reason codes) instead of the blanket refusal
    # here. Every shipped config as of bdd04ca has no "leverage_policy"
    # key, so `lev_block_present` is False and this condition is
    # byte-identical to before G-e for both of them.
    lev_block_present = "leverage_policy" in c
    if (c["endpoint"] != "https://paper-api.alpaca.markets"
            or c["catalyst_orders_enabled"] is not False
            or (Decimal(c["max_leverage"]) > 1 and not lev_block_present)):
        raise ValueError("unqualified_lane_configuration")
    # Single consolidated session-policy gate (replaces the previous ad-hoc
    # regular_session_only/extended_hours_enabled check in place here); with
    # the default config (no "sessions" block, or one matching today's
    # defaults) this enforces exactly the same invariant as before.
    session_policy = validate_session_policy(c)
    # G-e: opt-in leverage-schedule validation. Absent (every shipped
    # config) -> leverage stays None and every downstream private key/kwarg
    # below is skipped entirely, so the rest of load_config's output is
    # byte-identical to before G-e. Present -> validate_leverage_policy
    # raises its own LeveragePolicyError (a ValueError) reason code on any
    # defect; a passing block is threaded through as "_leverage_policy" and
    # into RiskLimits.leverage / PolicyConfig.leverage_policy_id below.
    leverage = validate_leverage_policy(c, session_policy) if lev_block_present else None
    if leverage is not None:
        c["_leverage_policy"] = leverage
    # G-f round 5: the entire gap-risk hook is opt-in. "sessions.gap_stop"
    # is optional and, when absent (every shipped config), "enabled"
    # defaults to False -- validate_session_policy's own "sessions" block
    # is left untouched (and its well-tested return shape/equality checks
    # with it) by reading this sibling key separately here instead.
    gap_stop_cfg = c.get("sessions", {}).get("gap_stop", {})
    if not isinstance(gap_stop_cfg, dict):
        raise ValueError("unqualified_lane_configuration")
    gap_stop_enabled = gap_stop_cfg.get("enabled", False)
    if type(gap_stop_enabled) is not bool:
        raise ValueError("unqualified_lane_configuration")
    # G-f round 8: cancel-then-replace itself is opt-in the same way,
    # via optional "exits.replace_enabled" (absent, every shipped config,
    # defaults to False).
    exits_cfg = c.get("exits", {})
    if not isinstance(exits_cfg, dict):
        raise ValueError("unqualified_lane_configuration")
    exit_replace_enabled = exits_cfg.get("replace_enabled", False)
    if type(exit_replace_enabled) is not bool:
        raise ValueError("unqualified_lane_configuration")
    resolved_registry_path = registry_path if registry_path is not None else SOURCE / "registry.json"
    registry_entries = load_registry(resolved_registry_path)
    strategy_pool_and_selector(c, registry_entries)  # fail fast on a malformed rotation block
    # R5: run_native previously reloaded SOURCE/registry.json unconditionally,
    # ignoring any registry_path override this call already validated (and
    # doing a redundant, potentially different, file read). Thread the exact
    # already-validated entries/path through on the config dict itself so
    # run_native uses the same registry load_config just checked -- private
    # keys (leading "_") are not part of the validated config schema and are
    # never serialized into a receipt.
    c["_registry_entries"] = registry_entries
    c["_registry_path"] = str(resolved_registry_path)
    # G-f deliverable 3: config.json may opt a RiskLimits into "notional"
    # max_order_qty mode via an optional "max_order_qty_mode" key; its
    # absence (every shipped config) keeps the pre-G-f "fixed" literal-qty
    # behavior. max_order_quantity itself is unchanged/untouched either way
    # (PolicyConfig.max_shares still comes from it, same as before G-f).
    risk = RiskLimits(capital_usd=c["capital_usd"], max_gross_exposure_usd=c["max_gross_exposure_usd"],
                      max_order_notional_usd=c["max_order_notional_usd"], max_order_qty=str(c["max_order_quantity"]),
                      max_order_qty_mode=c.get("max_order_qty_mode", "fixed"),
                      max_gross_loss_usd=c["max_gross_loss_usd"], max_drawdown_usd=c["max_drawdown_usd"],
                      max_spread_bps=c["max_spread_bps"], max_held_symbols=c["max_held_symbols"],
                      max_outstanding_orders=c["max_outstanding_orders"], max_rest_per_minute=c["max_api_requests_per_minute"],
                      max_submits_per_minute=c["max_submit_requests_per_minute"],
                      quote_max_age_seconds=c["quote_max_age_seconds"], trial_seconds=c["duration_seconds"],
                      cleanup_seconds=c["cleanup_seconds"], min_entry_close_seconds=c["min_entry_close_seconds"],
                      overnight_gross_multiple=session_policy["overnight_gross_multiple"],
                      **({"leverage": leverage} if leverage is not None else {}))
    policy = PolicyConfig(symbols=tuple(c["symbols"]), benchmarks=tuple(c["benchmarks"]),
                          max_positions=c["max_held_symbols"], capital=float(c["capital_usd"]),
                          gross_cap=float(c["max_gross_exposure_usd"]), max_leverage=float(c["max_leverage"]),
                          max_shares=c["max_order_quantity"], max_spread_bps=float(c["max_spread_bps"]),
                          # CX-P2 (2026-09-22 leverage fix round 1): PolicyConfig's
                          # own order-notional cap used to silently keep its
                          # 1000 default regardless of this config's
                          # max_order_notional_usd (RiskLimits already
                          # receives it above) -- a leveraged rung's larger
                          # configured per-order sizing (2000/4000) never
                          # reached strategies_v1._decide_core's allocation
                          # clamp, so entries could never actually size up
                          # to what the rung's ledger-side cap would allow.
                          max_order_notional=float(c["max_order_notional_usd"]),
                          warmup_samples=c["warmup_samples"], warmup_seconds=c["warmup_seconds"],
                          minimum_edge_bps=c["minimum_edge_bps"], quote_age_seconds=c["quote_max_age_seconds"],
                          min_hold_seconds=c["min_hold_seconds"], max_hold_seconds=c["max_hold_seconds"],
                          stop_bps=c["stop_bps"], take_profit_bps=c["take_profit_bps"], trailing_bps=c["trailing_bps"],
                          gap_stop_enabled=gap_stop_enabled, exit_replace_enabled=exit_replace_enabled,
                          **({"leverage_policy_id": leverage.version} if leverage is not None else {}))
    if set(c["strategy_scope"]) != set(AdaptivePolicy.families):
        raise ValueError("unsupported_strategy_scope")
    return c, risk, policy


def public_preflight(observation, config):
    account = observation["account"]
    return {"observed_at": datetime.now(timezone.utc).isoformat(),
            "endpoint": "https://paper-api.alpaca.markets", "feed": config["feed"],
            "account_status": account.get("status"),
            "capital_available": Decimal(account["cash"]) >= 10000,
            "clock": observation["clock"], "asset_count": len(observation["assets"]),
            "position_count": len(observation["positions"]), "open_order_count": len(observation["orders"]),
            "orders_submitted": 0, "quote_count": len(observation["quotes"]),
            "quote_errors": observation.get("quote_errors", {})}


_GATE_REQUIRED_KEYS = ("status", "input_sha256", "row_count", "checks", "versions", "checked_at")
_GATE_ACCEPTED_SNAPSHOT_EXTENSIONS = (".csv", ".parquet")
# Must equal promotion_gate.CHECK_NAMES (blueprints/us-equities/data/promotion_gate.py);
# tests/test_adaptive_paper_runner.py parses that module and asserts the two agree.
_GATE_CHECK_NAMES = frozenset((
    "rows_present", "symbol_nonempty", "valid_trading_session", "open_positive", "high_positive",
    "low_positive", "close_positive", "volume_integral_non_negative", "observed_at_not_future",
    "high_ge_max_open_close", "low_le_min_open_close", "unique_symbol_session",
))


def _check_promotion_gate(gate_result_path, snapshot_path):
    """Fail closed unless a promotion-gate result file (written by the
    separately venv'd `blueprints/us-equities/data/promotion_gate.py`)
    reports a complete, fully-passing result for the exact snapshot bytes
    this run consumes.

    This runtime has no live market-data snapshot concept of its own (Alpaca
    quotes are fetched fresh at preflight time, never read from a stored
    file), and `config.json` itself cannot be the gated snapshot: the gate
    only accepts `.parquet`/`.csv`/`duckdb://` input, so a JSON config always
    fails closed with `unsupported_input_format`. The gated "snapshot" is
    therefore an explicit, separately supplied bars/universe input file (the
    `--snapshot` CLI argument) that was actually run through
    `promotion_gate.py`; see `blueprints/us-equities/data/README.md` for the
    current state of that ingest.

    Validates the full gate-result contract, not just `status`/`input_sha256`
    (a review finding: a gate result whose top-level `status` was "pass" and
    whose `input_sha256` matched used to be accepted even when it declared
    `row_count: 0` or carried a failed check):

    * every key in `_GATE_REQUIRED_KEYS` is present, else
      `promotion_gate_incomplete`;
    * `checks` names every entry of `_GATE_CHECK_NAMES` exactly once (no
      missing, extra, unnamed or duplicate checks), `versions` is a non-empty
      object of non-empty version strings and `checked_at` a timezone-aware
      ISO-8601 date-time, else
      `promotion_gate_incomplete`;
    * a synthetic `unmapped_failures` check (pandera failures the gate could
      not map to a named check) raises `promotion_gate_unmapped_failures`;
    * `checks` is a non-empty list and every entry's `status == "pass"`,
      else `promotion_gate_incomplete` (malformed/missing `checks`) or
      `promotion_gate_failed_check` (a real failing check);
    * `row_count` is a positive integer, else `promotion_gate_empty`;
    * top-level `status == "pass"`, else `promotion_gate_failed`;
    * `snapshot_path` is a regular file with an extension the gate accepts
      (`.csv`/`.parquet`) whose sha256 equals `input_sha256`, else
      `promotion_gate_missing` (unusable snapshot) or
      `promotion_gate_mismatch` (hash disagreement, or for a `.csv` snapshot a
      `row_count` different from the file's data rows).
    """
    if gate_result_path is None or snapshot_path is None:
        raise SafetyError("promotion_gate_missing")
    try:
        gate = json.loads(Path(gate_result_path).read_text())
    except (OSError, ValueError):
        raise SafetyError("promotion_gate_missing")
    if not isinstance(gate, dict) or any(key not in gate for key in _GATE_REQUIRED_KEYS):
        raise SafetyError("promotion_gate_incomplete")
    checks = gate.get("checks")
    if not isinstance(checks, list) or not checks:
        raise SafetyError("promotion_gate_incomplete")
    # Every check the gate emits must be reported exactly once: a result that lists
    # only some checks (or unnamed ones) has not shown that the snapshot passed the gate.
    names = [check["name"] if isinstance(check, dict) and isinstance(check.get("name"), str) else None
             for check in checks]
    # promotion_gate.py reports pandera failures it cannot map to a named check under a
    # synthetic "unmapped_failures" entry (status "fail"): name that case explicitly.
    if "unmapped_failures" in names:
        raise SafetyError("promotion_gate_unmapped_failures")
    if len(set(names)) != len(names) or set(names) != _GATE_CHECK_NAMES:
        raise SafetyError("promotion_gate_incomplete")
    versions, checked_at = gate.get("versions"), gate.get("checked_at")
    if (not isinstance(versions, dict) or not versions
            or any(not isinstance(value, str) or not value for value in versions.values())
            or not isinstance(checked_at, str)):
        raise SafetyError("promotion_gate_incomplete")
    try:
        checked = datetime.fromisoformat(checked_at)
    except ValueError:
        raise SafetyError("promotion_gate_incomplete")
    if "T" not in checked_at or checked.tzinfo is None:
        raise SafetyError("promotion_gate_incomplete")
    if any(check.get("status") != "pass" for check in checks):
        raise SafetyError("promotion_gate_failed_check")
    row_count = gate.get("row_count")
    if not isinstance(row_count, int) or isinstance(row_count, bool) or row_count <= 0:
        raise SafetyError("promotion_gate_empty")
    if gate.get("status") != "pass":
        raise SafetyError("promotion_gate_failed")
    snapshot = Path(snapshot_path)
    if not snapshot.is_file() or snapshot.suffix.lower() not in _GATE_ACCEPTED_SNAPSHOT_EXTENSIONS:
        raise SafetyError("promotion_gate_missing")
    try:
        snapshot_bytes = snapshot.read_bytes()
    except OSError:
        raise SafetyError("promotion_gate_missing")
    if gate.get("input_sha256") != hashlib.sha256(snapshot_bytes).hexdigest():
        raise SafetyError("promotion_gate_mismatch")
    if snapshot.suffix.lower() == ".csv":
        # Bind row_count to the same hashed bytes: data rows after the header line.
        # A quoted field containing a newline would count high and refuse (never pass);
        # Parquet row counts would need a reader this runtime does not carry.
        data_rows = sum(1 for line in snapshot_bytes.splitlines()[1:] if line.strip())
        if data_rows != row_count:
            raise SafetyError("promotion_gate_mismatch")


def intraday_buying_power(account):
    """(value, field) for the account's intraday buying power, or None.

    Alpaca's responses dropped ``daytrading_buying_power``, ``pattern_day_trader`` and
    ``daytrade_count`` on 2026-07-06 (alpaca-py 0.44.0 models), after FINRA's intraday
    margin rule ended the PDT designation; buying power is now computed in real time
    (docs.alpaca.markets/us/docs/the-intraday-margin-rule, 2026-07-07). A read-only
    paper account read on 2026-09-23 showed, at multiplier 4,
    ``buying_power == 4 * (equity - maintenance_margin)`` on current equity (not the
    prior-close formula the older schema page still gives). The legacy field is
    preferred when a broker still reports it; otherwise ``buying_power`` is used,
    bounded by ``multiplier * (equity - maintenance_margin)`` whenever those fields are
    present, so a stale or prior-close figure can never admit more than current equity
    supports."""
    field = "daytrading_buying_power" if account.get("daytrading_buying_power") is not None else "buying_power"
    if account.get(field) is None or any(account.get(k) is None for k in ("multiplier", "equity")):
        return None
    if account.get("maintenance_margin") is None and field == "buying_power":
        return None  # the current-schema figure is only trusted with its equity bound: fail closed
    value = Decimal(str(account[field]))
    margin = Decimal(str(account.get("maintenance_margin") or 0))
    bound = Decimal(str(account["multiplier"])) * max(Decimal(str(account["equity"])) - margin, Decimal(0))
    if bound < value:
        return str(bound), "multiplier*(equity-maintenance_margin)"
    return str(value), field


def _check_margin_entitlement(account, config, lev, session_policy):
    """G-e: only called (from validate_preflight, below) when
    ``config.get("_leverage_policy")`` is set -- i.e. `account` was fetched
    with ``include_margin=True`` (see transport.normalize_account/preflight).
    Raises ``SafetyError`` with a bounded reason code on any missing field
    or insufficient broker entitlement; never raises for the default,
    non-leverage path (validate_preflight never calls this function then).
    """
    need = lev.max_leverage
    if any(key not in account for key in ("multiplier", "regt_buying_power")) or intraday_buying_power(account) is None:
        raise SafetyError("account_margin_fields_missing")
    # Tolerated legacy signal: Alpaca no longer sends pattern_day_trader (2026-07-06), but
    # a broker that still flags an account PDT under the old rule is refused below 25,000.
    if account.get("pattern_day_trader") is True and Decimal(account["equity"]) < 25000:
        raise SafetyError("account_restricted")
    mult = Decimal(account["multiplier"])
    if not mult.is_finite() or mult < need:
        raise SafetyError("account_multiplier_below_requested_leverage")
    if Decimal(intraday_buying_power(account)[0]) < Decimal(config["max_gross_exposure_usd"]):
        raise SafetyError("account_daytrading_buying_power_insufficient")
    if session_policy["overnight_holds"]:
        overnight_cap = Decimal(config["capital_usd"]) * lev.overnight_max_leverage
        if Decimal(account["regt_buying_power"]) < overnight_cap:
            raise SafetyError("account_regt_buying_power_insufficient")
    return mult


def validate_preflight(observation, config, *, require_open, allow_existing=False,
                       allow_existing_positions=None, session_policy=None,
                       mode=None, gate_result_path=None, snapshot_path=None):
    """``mode="paper"`` additionally requires a passing, hash-matched promotion
    gate (see ``_check_promotion_gate``); ``mode=None`` (the default) preserves
    prior behavior exactly for existing preflight/recover call sites.

    ``allow_existing`` (recovery mode, only set by ``--command recover``)
    relaxes the cash/equity floor, the full-universe/benchmark-quote checks
    and the fixed trial-length window requirement. ``allow_existing_positions``
    is the narrower, separate gate for deliverable D4: it only relaxes the
    flat-account/no-open-orders requirement (main() sets it for ``--command
    recover`` or to resume a trial whose persisted phase is
    ``held_overnight`` while overnight_holds is enabled), leaving the other
    four guards enforced exactly as for a normal fresh start. Defaults to ``allow_existing`` when not given, so recovery's
    existing behaviour is unchanged."""
    if mode == "paper":
        _check_promotion_gate(gate_result_path, snapshot_path)
    if allow_existing_positions is None:
        allow_existing_positions = allow_existing
    if session_policy is None:
        session_policy = DEFAULT_SESSION_POLICY
    account, clock = observation["account"], observation["clock"]
    if (account.get("status") != "ACTIVE" or account.get("currency") != "USD" or any(account.get(k) is not False for k in
            ("trading_blocked", "account_blocked", "trade_suspended_by_user"))
            or (not allow_existing and (Decimal(account["cash"]) < Decimal(config["capital_usd"])
            or Decimal(account["equity"]) < PROJECT_EQUITY_FLOOR_USD))):
        raise SafetyError("account_not_ready")
    # G-e: margin-entitlement preflight, only under a validated leverage
    # policy (config["_leverage_policy"], set by load_config). Runs after
    # the ordinary account-restriction checks above (which apply
    # unconditionally, leverage or not) and before every other guard below,
    # so a preflight that later fails a session/window/universe check under
    # the policy still surfaces the more actionable margin-entitlement
    # reason first when both would fail. config is mutated in place with
    # the broker-proven multiplier ("_account_multiplier", a private key,
    # same pattern as load_config's "_registry_entries") so main() can
    # thread it into AdaptiveStrategy/the "margin" preflight summary
    # without a second, duplicate broker-account check.
    leverage_policy = config.get("_leverage_policy")
    if leverage_policy is not None and not allow_existing:
        # ``allow_existing`` (--command recover) only ever submits sells
        # (recovery.recover, recovery.py:168, "buy_submissions": 0) --
        # broker margin/DTBP/multiplier entitlement gates new buys, so it
        # must not block a sell-only recovery from flattening an
        # over-leveraged position. README-safety.md: sells and exits are
        # never refused by the leverage ceiling.
        config["_account_multiplier"] = _check_margin_entitlement(account, config, leverage_policy, session_policy)
    server = clock["timestamp_ns"] / 1e9
    close = clock["next_close_ns"] / 1e9
    if abs(clock["received_at_ns"] / 1e9 - server) > .25:
        raise SafetyError("clock_drift")
    required_window = 1 if allow_existing else config["duration_seconds"] + config["cleanup_seconds"] + 60
    # Default policy (extended_hours False): unchanged, uses the broker's own
    # is_open flag (RTH-only) and next_close (also RTH). extended_hours True:
    # is_open is only ever True during RTH, so it can never be used to allow
    # a PRE/POST start; use our own session clock against the broker's
    # server timestamp instead (D9). S7: the broker's next_close is also
    # RTH-only -- under extended_hours the required-window guard must compare
    # against the actual (extended) session close, or a PRE/POST start with
    # plenty of time left before the extended close (but less than
    # required_window before the next RTH close) is wrongly refused.
    if session_policy.get("extended_hours"):
        now_dt = datetime.fromtimestamp(server, timezone.utc)
        session_open_ok = session_at(now_dt).kind in (SessionKind.PRE, SessionKind.RTH, SessionKind.POST)
        try:
            close = extended_session_close(now_dt).astimezone(timezone.utc).timestamp()
        except ValueError:
            # CLOSED (no active extended session): session_open_ok is
            # already False above, which alone fails the require_open check
            # below regardless of `close`; leave the broker's own
            # (irrelevant, RTH-only) next_close_ns rather than raising here.
            pass
    else:
        session_open_ok = clock["is_open"] is True
    if require_open and (session_open_ok is not True or close - server < required_window):
        raise SafetyError("regular_session_window_unavailable")
    if not allow_existing_positions and (observation["positions"] or observation["orders"]):
        raise SafetyError("clean_native_start_requires_flat_account")
    assets = {a["symbol"]: a for a in observation["assets"]}
    required_assets = {p["symbol"] for p in observation["positions"]} if allow_existing else set(config["symbols"])
    if not required_assets.issubset(assets) or any(assets[s].get("status") != "active" or assets[s].get("tradable") is not True
                                                   for s in required_assets):
        raise SafetyError("universe_not_tradable")
    if require_open and not allow_existing:
        quotes = {q["symbol"]: q for q in observation["quotes"]}
        if any(s not in quotes or not -.25 <= time.time() - quotes[s]["ts_ns"] / 1e9 <= config["quote_max_age_seconds"]
               for s in config["benchmarks"]):
            raise SafetyError("benchmark_quotes_not_ready")
    return close


def reconcile(ledger, snapshot, baseline_cash):
    """Only invoke with admissions stopped and no in-flight submit tasks."""
    if snapshot.get("complete") is not True:
        raise SafetyError("incomplete_snapshot")
    intents = {i.client_id: i for i in ledger.intents()}
    seen = set()
    for order in snapshot["orders"]:
        cid = order["client_order_id"]
        if cid not in intents:
            raise SafetyError("external_order_detected")
        intent = intents[cid]
        if (order["symbol"] != intent.symbol or order["side"] != intent.side
                or Decimal(order["qty"]) != intent.qty):
            raise SafetyError("broker_intent_mismatch")
        ledger.record_order(cid, order["id"], order["status"], order["filled_qty"], order.get("filled_avg_price"),
                            timestamp=order["updated_at_ns"] / 1e9)
        seen.add(cid)
    if any(i.submit_attempted and i.status not in ("not_sent", "broker_refused")
           and i.client_id not in seen for i in ledger.intents()):
        raise SafetyError("submitted_intent_absent")
    actual = {p["symbol"]: Decimal(p["qty"]) for p in snapshot["positions"] if Decimal(p["qty"])}
    expected = {p.symbol: p.qty for p in ledger.positions().values() if p.qty}
    if actual != expected:
        raise SafetyError("position_mismatch")
    cash_delta = Decimal(snapshot["account"]["cash"]) - Decimal(baseline_cash)
    if abs(cash_delta - ledger.accounting().cash_delta_usd) > Decimal("0.01"):
        raise SafetyError("cash_mismatch_or_unmodeled_fees")
    return {"positions_match": True, "cash_match": True, "cash_delta_usd": str(cash_delta),
            "open_orders": len(ledger.unresolved()), "positions": len(expected)}


def held_resume_matches_ledger(ledger, observation):
    """A resumed held_overnight trial may carry only what its own ledger
    holds: broker positions must equal the ledger's held positions symbol for
    symbol and quantity for quantity (a short or fractional foreign position
    counts), and every open broker order must be one of the ledger's own
    intents. A position or order created outside the trial between sessions
    refuses the resume instead of being adopted by the startup broker-snapshot
    seed (Ledger.adopt_broker_snapshot inserts positions the ledger lacks)."""
    actual = {p["symbol"]: Decimal(p["qty"]) for p in observation["positions"] if Decimal(p["qty"])}
    expected = {p.symbol: p.qty for p in ledger.positions().values() if p.qty}
    if actual != expected:
        raise SafetyError("held_resume_position_mismatch")
    known = {i.client_id for i in ledger.intents()}
    if any(order.get("client_order_id") not in known for order in observation["orders"]):
        raise SafetyError("held_resume_external_order")


class LiveEventLog(list):
    """The controller's event list that also appends each event to a JSON-lines file as
    it happens (``--live-dir``), for a live view of decisions and intents. Observation
    only: a write failure is counted and never interrupts trading."""

    def __init__(self, path):
        super().__init__()
        self.path, self.write_errors = Path(path), 0
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    def append(self, event):
        super().append(event)
        try:
            with self.path.open("a") as f:
                f.write(json.dumps({"at": time.time(), **event}, default=str, sort_keys=True) + "\n")
        except (OSError, TypeError, ValueError):
            self.write_errors += 1


class Controller:
    def __init__(self, ledger, close, *, market_open, clock=time.time):
        self.ledger, self.close, self.market_open, self.clock = ledger, close, market_open, clock
        self.port = None
        self.quotes = {}
        self.requests = []
        self.events = []
        self.stop = False
        self.defer_until = 0
        self.halted_symbols = set()
        self.last_status_ts = {}

    async def before_request(self, kind, client_id=None):
        if kind == "data_read":
            return
        deadline = self.clock() + 65
        while self.clock() < deadline:
            if kind == "submit":
                intent = next((i for i in self.ledger.intents() if i.client_id == client_id), None)
                if intent is None:
                    raise SafetyError("submit_without_intent")
                self.ledger.validate_pending(client_id, quote=self.quotes[intent.symbol], now=self.clock(),
                                             market_open=self.market_open, session_close=self.close)
                if intent.side == "buy" and (self.stop or not self.port.ready):
                    raise SafetyError("admissions_not_ready")
            wait = self.ledger.request_budget(self.clock(), kind, client_id=client_id)
            if not wait:
                self.requests.append({"timestamp": self.clock(), "kind": kind})
                return
            if kind == "submit":
                self.defer_until = max(self.defer_until, self.clock() + wait)
                raise SafetyError("submission_rate_deferred")
            await asyncio.sleep(min(wait + .002, 1))
        raise SafetyError("request_budget_wait_exceeded")

    def before_submit(self, order):
        from native_adapter import NativeOrderRejected
        try:
            if order["side"] == "buy" and (self.stop or not self.port.ready):
                raise SafetyError("admissions_not_ready")
            quote = self.quotes.get(order["symbol"])
            if quote is None:
                raise SafetyError("no_current_quote")
            intent = self.ledger.reserve_intent(order["client_order_id"], order["symbol"], order["side"],
                                                order["qty"], order["limit_price"], quote=quote,
                                                now=self.clock(), market_open=self.market_open,
                                                session_close=self.close)
            if not intent.newly_reserved:
                raise SafetyError("duplicate_intent_not_resubmitted")
        except SafetyError as exc:
            raise NativeOrderRejected(str(exc)) from None
        self.events.append({"type": "intent", "client_id": intent.client_id, "symbol": intent.symbol,
                            "side": intent.side, "strategy": order.get("strategy"), "reason": order.get("reason")})

    def observe(self, order):
        known = {i.client_id for i in self.ledger.intents()}
        if order["client_order_id"] not in known:
            self.stop = True
            self.ledger.freeze("external_order_detected")
            raise SafetyError("external_order_detected")
        self.ledger.record_order(order["client_order_id"], order["id"], order["status"], order["filled_qty"],
                                 order.get("filled_avg_price"), timestamp=order["updated_at_ns"] / 1e9)

    def quote(self, quote):
        # halted merges the per-quote signal (transport.normalize_quote's
        # best-effort condition-code mapping) with any standing halt recorded
        # from a trading_status message (see trading_status() below); either
        # source marks the symbol halted until trading_status clears it.
        halted = bool(quote.get("halted", False)) or quote["symbol"] in self.halted_symbols
        q = Quote(quote["symbol"], quote["bid"], quote["ask"], quote["ts_ns"] / 1e9, halted=halted)
        old = self.quotes.get(q.symbol)
        if old is None or q.timestamp > old.timestamp:
            self.quotes[q.symbol] = q

    def trading_status(self, status):
        """Consume a normalize_trading_status(...) result (deliverable D3).
        Not yet driven by a live websocket subscription in this change; see
        the task handoff. Kept separate from quote() so a future subscription
        only needs to call this, not touch the quote path.

        D6: a halt must take effect immediately, not only once a strictly
        newer quote update arrives (quote() only ever replaces the stored
        quote for a newer timestamp, so between here and the next quote tick
        there would otherwise be a fail-open window where reserve_intent's
        halted gate still sees the old, unhalted stored quote). Re-stamp the
        already-stored quote in place, at its existing timestamp, so it is
        visible to any reader immediately.

        D3: applied only when this message's own ``ts_ns`` is strictly newer
        than the last status message actually applied for this symbol --
        exactly the same out-of-order/replay guard quote() already applies
        via each Quote's own timestamp. Without this, a replayed or
        out-of-order older "resumed" (not halted) message arriving after a
        genuinely newer halt would clear that halt (both halted_symbols and
        the re-stamped stored quote), reopening admissions for a symbol
        that is, per the most recent real status, still halted.

        D7 (round 2): the replay guard above only ever activated when BOTH
        this message's ``ts_ns`` and a prior ``last_ts`` were present --
        a message with a missing or invalid ``ts_ns`` (``None``, non-int,
        zero, or negative) bypassed the guard entirely and was applied
        unconditionally, so it could clear a genuinely newer halt exactly
        the way a stale replayed message could. Refuse (ignore, recorded as
        an event, not silently dropped) any status whose ``ts_ns`` is not a
        valid positive integer instead."""
        symbol = status["symbol"]
        ts_ns = status.get("ts_ns")
        if type(ts_ns) is not int or ts_ns <= 0:
            self.events.append({"type": "trading_status_ignored", "symbol": symbol,
                               "reason": "missing_or_invalid_ts_ns"})
            return
        last_ts = self.last_status_ts.get(symbol)
        if last_ts is not None and ts_ns <= last_ts:
            return
        self.last_status_ts[symbol] = ts_ns
        halted = bool(status.get("halted"))
        if halted:
            self.halted_symbols.add(symbol)
        else:
            self.halted_symbols.discard(symbol)
        stored = self.quotes.get(symbol)
        if stored is not None and stored.halted != halted:
            self.quotes[symbol] = replace(stored, halted=halted)

    def bind(self, port):
        """Retain proven negative outcomes before native/recovery callbacks."""
        submit = port.submit
        async def observed_submit(order):
            try:
                return await submit(order)
            except Exception as exc:
                intent = next((i for i in self.ledger.intents() if i.client_id == order["client_order_id"]), None)
                if intent and intent.status == "reserved" and intent.broker_id is None and not intent.filled_qty:
                    if getattr(exc, "not_sent", False) is True:
                        self.ledger.mark_not_sent(intent.client_id, "transport_proven_not_sent")
                    elif isinstance(exc, RejectedSubmission):
                        self.ledger.mark_broker_refused(intent.client_id, exc.status_code)
                        self.stop = True
                raise
        port.submit = observed_submit
        return port


def _leverage_achievement_step(state, *, dt_seconds, achieved_leverage, ceiling, next_lower_ceiling):
    """F2 (residual review, reachability): one pure state-update step of the
    per-run achieved-leverage receipt, factored out (D1 pattern) so it is
    directly testable without driving run_native's full tick loop.

    `state` is the previous return value of this function (or
    `_INITIAL_LEVERAGE_ACHIEVEMENT_STATE`); `achieved_leverage` is this
    tick's gross exposure / equity (mark-to-market, not the fixed-capital
    denominator `peak_effective_leverage` already in `outcome["leverage"]`
    uses); `ceiling` is the policy layer's ceiling in force this tick;
    `next_lower_ceiling` is `leverage.next_lower_rung_ceiling(config's
    max_leverage)` (None for the 1x rung, which has no lower rung).
    `dt_seconds` is the wall-clock gap since the previous tick this function
    was called for (0 on the first call).

    Records: the peak achieved leverage seen so far, the ceiling that was in
    force at the tick that peak was recorded (a receipt with a high peak but
    a ceiling that never actually allowed it would itself be suspicious),
    and the cumulative time spent with achieved leverage above the
    next-lower rung's own ceiling -- evidence a '4x' run actually needed 4x
    and did not merely stay inside 2x's proportional room the whole time.
    Attributes the whole `dt_seconds` gap to "above" when THIS tick's
    achieved leverage exceeds the threshold (a per-tick approximation, not a
    continuous integral); ticks are ~0.1s apart in practice so the error is
    bounded by the tick cadence.
    """
    peak = state["peak_achieved_leverage"]
    ceiling_at_peak = state["ceiling_at_peak"]
    if achieved_leverage > peak:
        peak = achieved_leverage
        ceiling_at_peak = ceiling
    seconds_above = state["seconds_above_next_lower_rung_ceiling"]
    if next_lower_ceiling is not None and dt_seconds > 0 and achieved_leverage > next_lower_ceiling:
        seconds_above += dt_seconds
    return {"peak_achieved_leverage": peak, "ceiling_at_peak": ceiling_at_peak,
            "seconds_above_next_lower_rung_ceiling": seconds_above}


_INITIAL_LEVERAGE_ACHIEVEMENT_STATE = {"peak_achieved_leverage": Decimal("0"), "ceiling_at_peak": Decimal("0"),
                                       "seconds_above_next_lower_rung_ceiling": 0.0}


# A deliberate project capital floor for a fresh paper start. It began as the PDT day-trading
# minimum; FINRA's intraday margin rule removed that minimum (Reg T margin needs 2,000), and the
# floor is kept on purpose as a conservative project limit, not as a broker rule (2026-09-23).
PROJECT_EQUITY_FLOOR_USD = 25000

RECONCILE_EVERY_SECONDS = 30  # periodic broker snapshot and reconciliation during a run


async def run_native(controller, policy_config, assets, trial_id, config, baseline_cash, *, account_fingerprint="simulation",
                     log_directory=None):
    from native_adapter import build_node
    from native_strategy import AdaptiveStrategy
    # R5: use the same registry entries load_config already validated (and
    # threaded onto config via "_registry_entries"/"_registry_path") instead
    # of unconditionally reloading SOURCE/registry.json, which would silently
    # diverge from a registry_path override. Fall back to the default
    # registry only for callers that construct `config` without going
    # through load_config (e.g. direct/legacy test fixtures).
    registry_entries = config.get("_registry_entries")
    if registry_entries is None:
        registry_entries = load_registry(Path(config.get("_registry_path", SOURCE / "registry.json")))
    pool, selector = strategy_pool_and_selector(config, registry_entries)
    leverage_policy = config.get("_leverage_policy")
    policy = AdaptivePolicy(policy_config, strategy_pool=pool, selector=selector, leverage_policy=leverage_policy)
    strategy = AdaptiveStrategy(policy, controller.ledger, trial_id,
                                event_sink=controller.events.append, transport=controller.port,
                                account_multiplier=config.get("_account_multiplier"))
    # Capture actual streaming quotes before native conversion. Every native
    # strategy event still arrives through the data engine's ordinary path.
    port = controller.port
    start = port.start
    async def start_with_quotes(on_quote, on_order):
        async def quote_sink(q):
            controller.quote(q)
            result = on_quote(q)
            if hasattr(result, "__await__"):
                await result
        return await start(quote_sink, on_order)
    port.start = start_with_quotes
    metadata = [{"symbol": a["symbol"], "price_precision": 2, "price_increment": "0.01", "lot_size": "1"}
                for a in assets]
    session_policy = validate_session_policy(config)
    session = build_node(port, metadata, [strategy], account_id="ALPACA-PAPER-" + account_fingerprint[:16],
                         max_order_submit_rate="180/00:01:00", session_policy=session_policy,
                         log_directory=log_directory)
    task = asyncio.create_task(session.run_async())
    started = time.monotonic()
    last_reconciliation = started
    cleanup_started = None
    reconciliation = None
    boundary_receipts = []
    ledger_adopted = False  # D1: one-shot seed of the local ledger from the
    # adapter's accepted broker snapshot, once native startup has actually
    # populated it (see the strategy.started gate below).
    # Tracks the NYSE session kind as of the previous tick so a boundary
    # receipt (D6) is only written on an actual PRE/RTH/POST/CLOSED crossing,
    # never on every ~30s reconciliation tick.
    # S3: this used to run unconditionally, on every paper run, before the
    # try block below -- so the DEFAULT policy (extended_hours False,
    # overnight_holds False) depended on session_at's frozen calendar table
    # and would raise session_calendar_out_of_range for any run whose
    # wall-clock year falls outside it (exchange_calendars is not installed
    # in this deployment, so there is no fallback). last_session_kind is
    # only ever consulted below inside the `if session_policy["overnight_holds"]`
    # boundary-receipt block, so the default policy must never call the
    # session calendar to compute it at all.
    last_session_kind = (session_at(datetime.fromtimestamp(time.time(), timezone.utc)).kind
                        if (session_policy["overnight_holds"] or session_policy["extended_hours"]) else None)
    # G-e receipt tracking (only meaningful/consulted when leverage_policy is
    # not None; harmless, unread overhead otherwise). peak_gross_exposure_usd
    # observes the ledger's own accounted FILLED-position gross exposure
    # each tick -- EH-1 (2026-09-22 leverage fix round 1): the ledger's raw
    # `accounting().gross_exposure_usd` is `gross + pending`
    # (safety.Ledger._state), i.e. it also counts every still-resting,
    # unfilled buy intent, so using it directly here used to let a run's
    # "achieved" leverage/margin figures reflect capital that was never
    # actually deployed into a filled position. peak_pending_buy_notional_usd
    # records that unfilled-order notional separately instead of folding it
    # into the achieved-exposure figures.
    # ceiling_changes records the policy layer's last_leverage_ceiling only
    # on an actual change, not every tick.
    peak_gross_exposure_usd = Decimal("0")
    peak_pending_buy_notional_usd = Decimal("0")
    ceiling_changes = []
    last_recorded_ceiling = None
    # F2 (residual review, reachability): the achieved-leverage receipt.
    # next_lower_ceiling is fixed for the whole run (the rung the loaded
    # config's own max_leverage sits at does not change mid-run); None for
    # the 1x rung, which has no lower rung to compare against.
    achievement_state = _INITIAL_LEVERAGE_ACHIEVEMENT_STATE
    next_lower_ceiling = next_lower_rung_ceiling(leverage_policy.max_leverage) if leverage_policy is not None else None
    last_achievement_tick = None
    try:
        while time.monotonic() - started < config["duration_seconds"] + config["cleanup_seconds"]:
            now = time.time()
            if task.done():
                break
            elapsed = time.monotonic() - started
            # D1: seed the local ledger from the broker snapshot the adapter
            # accepted at startup (native_adapter._connect, overnight_holds
            # path), exactly once, as soon as it is actually available.
            # strategy.started only flips True after every client (including
            # this execution client) has connected, so session.snapshot_state
            # / session.reconciliation are guaranteed populated by then.
            if (not ledger_adopted and strategy.started and session_policy["overnight_holds"]
                    and session.reconciliation is not None):
                ledger_delta = controller.ledger.adopt_broker_snapshot(session.snapshot_state, now)
                session.reconciliation["ledger_delta"] = ledger_delta
                ledger_adopted = True
            state = controller.ledger.accounting()
            force_exit = (controller.stop or DEFAULT_STOP.exists() or bool(session.errors)
                          or bool(state.halted_reason) or elapsed >= config["duration_seconds"]
                          or controller.close - now <= config["cleanup_seconds"])
            if force_exit and cleanup_started is None:
                cleanup_started = time.monotonic()
            # A connection or integrity gap ends this bounded run. Quote silence
            # pauses admissions; it requires a fresh reconciled snapshot to thaw.
            health = getattr(port, "health", {})
            serious_gap = any("stale" not in str(reason) for reason in health.get("reasons", []))
            if strategy.started and serious_gap:
                controller.stop = True
                force_exit = True
            strategy.enabled = (strategy.started and port.ready and not force_exit
                                and now >= controller.defer_until)
            fresh_quotes = [q for q in controller.quotes.values()
                            if -.25 <= now - q.timestamp <= config["quote_max_age_seconds"]]
            try:
                controller.ledger.mark_to_market(fresh_quotes, now)
            except SafetyError as exc:
                strategy.enabled = False
                if str(exc) != "held_position_mark_stale":
                    controller.stop = True
                    force_exit = True
            if (strategy.started and not force_exit and time.monotonic() - last_reconciliation >= RECONCILE_EVERY_SECONDS
                    and not controller.ledger.unresolved() and not strategy.pending):
                strategy.enabled = False
                snapshot = await port.snapshot()
                reconcile(controller.ledger, snapshot, baseline_cash)
                # Re-read health after the snapshot await: a gap that arose meanwhile must
                # stop the run, never be thawed by this periodic acknowledgement.
                health = getattr(port, "health", {})
                if any("stale" not in str(reason) for reason in health.get("reasons", [])):
                    controller.stop = True
                elif health.get("fresh_quotes") and hasattr(port, "mark_reconciled"):
                    port.mark_reconciled()
                last_reconciliation = time.monotonic()
            # Boundary receipts (D6): independent of the 30s reconciliation
            # cadence above, only emitted on a real session-kind crossing.
            if session_policy["overnight_holds"]:
                now_kind = session_at(datetime.fromtimestamp(now, timezone.utc)).kind
                if now_kind != last_session_kind:
                    state_now = controller.ledger.accounting()
                    boundary_receipts.append(boundary_receipt(
                        datetime.fromtimestamp(now, timezone.utc),
                        positions=[{"symbol": p.symbol, "qty": str(p.qty)}
                                   for p in controller.ledger.positions().values() if p.qty],
                        cash=Decimal(baseline_cash) + state_now.cash_delta_usd,
                        cash_delta=state_now.cash_delta_usd,
                        open_orders=len(controller.ledger.unresolved()), reconciled_at_boundary=True))
                last_session_kind = now_kind
            if strategy.started:
                strategy.cancel_expired(now, config["order_timeout_seconds"], all_entries=force_exit)
                strategy.rebalance(now, force_exit=force_exit)
                if leverage_policy is not None:
                    acct_now = controller.ledger.accounting()
                    # EH-1: filled_gross_exposure_usd excludes every
                    # not-yet-filled buy intent's notional (acct_now.gross_
                    # exposure_usd includes it; acct_now.pending_buy_
                    # notional_usd is exactly that included amount -- see
                    # safety.Ledger._state) so peak_gross_exposure_usd,
                    # achieved_leverage_now and broker_margin_used below only
                    # ever reflect capital actually deployed into a filled
                    # position, never a resting or partially-filled order.
                    filled_gross_exposure_usd = acct_now.gross_exposure_usd - acct_now.pending_buy_notional_usd
                    peak_gross_exposure_usd = max(peak_gross_exposure_usd, filled_gross_exposure_usd)
                    peak_pending_buy_notional_usd = max(peak_pending_buy_notional_usd,
                                                        acct_now.pending_buy_notional_usd)
                    current_ceiling = policy.last_leverage_ceiling
                    # F2: gross-to-equity, mark-to-market (equity moves with
                    # realized+unrealized pnl each tick) -- distinct from
                    # peak_gross_exposure_usd/capital below, which is fixed
                    # to starting capital and cannot fall from paper losses.
                    equity_now = (controller.ledger.limits.capital_usd + acct_now.realized_pnl_usd
                                 + acct_now.unrealized_pnl_usd)
                    achieved_leverage_now = (filled_gross_exposure_usd / equity_now
                                             if equity_now > 0 else Decimal("0"))
                    dt = 0.0 if last_achievement_tick is None else max(0.0, now - last_achievement_tick)
                    achievement_state = _leverage_achievement_step(
                        achievement_state, dt_seconds=dt, achieved_leverage=achieved_leverage_now,
                        ceiling=current_ceiling if current_ceiling is not None else Decimal("0"),
                        next_lower_ceiling=next_lower_ceiling)
                    last_achievement_tick = now
                    if current_ceiling != last_recorded_ceiling:
                        # G-e receipt (S6): regime is read back from this
                        # tick's own decision event (controller.events),
                        # rather than re-deriving it, so a throttled tick
                        # (no fresh decision -> no event appended) simply
                        # keeps the last known ceiling change unlogged for
                        # regime rather than guessing.
                        last_event = controller.events[-1] if controller.events else {}
                        try:
                            observed_session = session_at(datetime.fromtimestamp(now, timezone.utc)).kind.value
                        except ValueError:
                            observed_session = None
                        ceiling_changes.append({
                            "t": now, "session": observed_session, "regime": last_event.get("regime"),
                            "drawdown_fraction": str(acct_now.drawdown_usd / controller.ledger.limits.max_drawdown_usd),
                            "ceiling": str(current_ceiling)})
                        last_recorded_ceiling = current_ceiling
            if force_exit and not controller.ledger.unresolved() and not controller.ledger.positions() and not strategy.pending:
                break
            await asyncio.sleep(.1)
        strategy.enabled = False
        controller.stop = True
        # Native lifecycle has to settle before a read-only final comparison.
        if not controller.ledger.unresolved() and not strategy.pending:
            snap = await port.snapshot()
            reconciliation = reconcile(controller.ledger, snap, baseline_cash)
    finally:
        strategy.enabled = False
        controller.stop = True
        session.stop()
        try:
            await asyncio.wait_for(task, 20)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await port.stop()
    state = asdict(controller.ledger.accounting())
    is_flat = not controller.ledger.positions() and not controller.ledger.unresolved()
    port_health = getattr(port, "health", {})
    outcome = {"engine": "NautilusTrader LiveNode 2.0.0rc5", "native_quotes": strategy.received_quotes,
              "dropped_quotes": {"by_reason": {str(k): int(v) for k, v in port_health.get("dropped_quotes", {}).items()},
                                 "by_symbol": {str(k): int(v) for k, v in port_health.get("dropped_quotes_by_symbol", {}).items()}},
              "native_fill_events": strategy.native_fills, "native_rejections": strategy.native_rejections,
              "policy_selections": strategy.policy.counts, "accounting": state,
              "reconciliation": reconciliation, "startup_reconciliation": session.reconciliation,
              "adapter_errors": list(session.errors), "flat": is_flat,
              "requests": controller.requests, "events": controller.events,
              "session_policy": {"extended_hours": session_policy["extended_hours"],
                                 "overnight_holds": session_policy["overnight_holds"]},
              "boundary_receipts": boundary_receipts,
              "elapsed_seconds": time.monotonic() - started}
    if leverage_policy is not None:
        capital = Decimal(config["capital_usd"])
        peak_effective_leverage = (peak_gross_exposure_usd / capital) if capital else Decimal("0")
        outcome["leverage"] = {
            "policy_version": leverage_policy.version,
            "config_max_leverage": str(leverage_policy.max_leverage),
            "account_multiplier": (str(config["_account_multiplier"])
                                   if config.get("_account_multiplier") is not None else None),
            "peak_gross_exposure_usd": str(peak_gross_exposure_usd),
            # EH-1: the peak notional of not-yet-filled buy intents seen
            # this run, tracked separately from peak_gross_exposure_usd
            # above (which is now filled-position-only) rather than folded
            # into it.
            "peak_pending_buy_notional_usd": str(peak_pending_buy_notional_usd),
            "peak_effective_leverage": str(peak_effective_leverage),
            "ceiling_changes": ceiling_changes,
            "broker_cash_at_start": str(baseline_cash),
            "broker_margin_used": peak_gross_exposure_usd > Decimal(str(baseline_cash)),
            # F2 (residual review, 2026-09-22, reachability): the achieved
            # (not merely permitted) leverage this run actually reached,
            # gross-to-equity and mark-to-market -- unlike
            # peak_effective_leverage above (fixed-capital-denominated), this
            # falls if paper losses shrink equity. This is a receipt only:
            # no gate row in catalogs/us-equities/gates-20260922.json
            # currently reads peak_achieved_leverage or
            # seconds_above_next_lower_rung_ceiling, so a rung's gate row
            # CAN still flip to established on a receipt whose achieved
            # exposure never exceeded a lower rung's own ceiling -- see
            # README-safety.md's Leverage schedule section (2026-09-22
            # leverage fix round 2, N1-1) and the rung configs' notes for
            # what this field establishes and does not establish (achieved
            # exposure may stay below the cap; a rung sets the safety
            # envelope, not a target).
            "next_lower_rung_ceiling": (str(next_lower_ceiling) if next_lower_ceiling is not None else None),
            "peak_achieved_leverage": str(achievement_state["peak_achieved_leverage"]),
            "ceiling_at_peak_achieved_leverage": str(achievement_state["ceiling_at_peak"]),
            "seconds_above_next_lower_rung_ceiling": achievement_state["seconds_above_next_lower_rung_ceiling"]}
    outcome["status"] = _run_native_status(reconciliation, session.errors, strategy.native_fills,
                                           outcome, session_policy, time.time())
    return outcome


def _run_native_status(reconciliation, session_errors, native_fills, outcome, session_policy, now):
    """D1: status is decided by exactly one authority, factored out so it is
    directly testable without driving a full native node/port. A clean,
    reconciled, flat end is "passed"/"completed_no_signals" regardless of
    overnight_holds. Any other non-flat end is "held_overnight" only when
    _honest_overnight_hold agrees it is a genuine, reconciled,
    error/halt-free session-boundary hold -- main() reuses this status for
    is_final_boundary (``_final_boundary_from_run_status``) instead of
    deciding again, so a mid-RTH non-flat end (or an
    unreconciled/errored/halted one) is never recorded as held_overnight
    (exit 0, resumable phase) by this function.

    D4 (round 6): this is run_native's OWN status, from its own
    reconciliation snapshot -- it is not necessarily main()'s FINAL status.
    main()'s wrapper takes a fresh, independent ledger/unresolved-orders
    reading after this returns and, whenever that reading disagrees (e.g. an
    order settles between this snapshot and that check) or the session
    policy does not honor this status as a legitimate hold, forces a
    liquidation (recover()) and composes this function's status with
    recover()'s own post-recovery status via _apply_forced_recovery_outcome's
    two-tier rule (round 8): a pre-recovery status of "needs_attention" or
    "failed" is STICKY and survives regardless of how the forced
    liquidation went; any other pre-recovery status (including this
    function's own "held_overnight") is fully replaced by recover()'s own
    status ("passed" if the liquidation actually flattened/reconciled the
    account cleanly, else "needs_attention") -- never left in place
    unconditionally, and never allowed to outrank a failed liquidation's
    real outcome.
    """
    if reconciliation and reconciliation["positions"] == 0 and reconciliation["open_orders"] == 0 and not session_errors:
        return "passed" if native_fills else "completed_no_signals"
    if _honest_overnight_hold(outcome, session_policy, now):
        return "held_overnight"
    return "needs_attention"


def _honest_overnight_hold(outcome, session_policy, now):
    """S1: whether a non-flat run end under overnight_holds is a genuine,
    resumable session-boundary hold, decided from the run's own outcome
    fields -- not merely "overnight_holds is enabled and the ledger is
    non-flat" (that used to relabel ANY non-flat end, including a genuine
    mid-RTH error or risk halt, as "held_overnight").

    True only when all of:
      - the session clock at ``now`` shows a boundary was actually reached
        (POST or CLOSED -- the trial's own deadline landing inside a
        non-RTH session), not merely "duration_seconds elapsed mid-RTH
        with positions still open";
      - run_native's own reconciliation succeeded (its outcome carries a
        non-None ``reconciliation``);
      - there were no adapter errors and no risk halt.

    Any other non-flat end must stay "needs_attention" (routed through the
    force-flat/recover path below) so a genuine failure is never silently
    masked as an intentional overnight hold.
    """
    if not session_policy.get("overnight_holds"):
        return False
    try:
        kind = session_at(datetime.fromtimestamp(now, timezone.utc)).kind
    except ValueError:
        return False
    boundary_reached = kind in (SessionKind.POST, SessionKind.CLOSED)
    return (boundary_reached and outcome.get("reconciliation") is not None
            and not outcome.get("adapter_errors")
            and not (outcome.get("accounting") or {}).get("halted_reason"))


# D6 (round 8): the failed/sticky pre-recovery statuses -- see
# _apply_forced_recovery_outcome's docstring. "failed" is included
# defensively (the synthetic run_native-exception fallback outcome always
# uses "needs_attention", not "failed", but a future caller of
# _apply_forced_recovery_outcome should not have to know that to stay
# safe).
_STICKY_FAILED_STATUSES = {"needs_attention", "failed"}


def _apply_forced_recovery_outcome(outcome, recovery):
    """D4 (round 6)/D1 (round 7)/D6 (round 8): merge a forced
    liquidation's (recover()'s) own post-recovery result into `outcome`,
    so a subsequent trial_phase_and_exit_code() call reads the REAL
    post-recovery flat state and a correctly composed status, not
    run_native's own (now-stale) pre-recovery snapshot overwritten
    unconditionally.

    `flat` is always taken from recovery (the actual, current,
    post-recovery ledger state). `status` is composed by an explicit
    TWO-TIER rule, not a single severity ranking:

    1. If the pre-recovery status is already one of
       _STICKY_FAILED_STATUSES ("needs_attention"/"failed" -- a real
       mid-RTH error, halt, or reconciliation mismatch run_native itself
       already detected), it is STICKY: it survives regardless of how
       the forced liquidation that followed went, successful or not. A
       liquidation that happens to work afterwards must never silently
       UPGRADE a genuinely failed session to "passed"/exit 0.
    2. Otherwise (the pre-recovery status was some non-failed value --
       "held_overnight", "passed", "completed_no_signals", or anything
       unrecognized), the composed status is recovery's OWN status
       exactly ("passed" if the liquidation actually flattened/
       reconciled the account cleanly, else "needs_attention" -- see
       recovery.recover's own return). In particular a pre-recovery
       status of "held_overnight" -- which only exists because
       run_native's own end-of-run reconciliation deferred to a legitimate
       overnight hold, not because anything failed -- never survives a
       successful flatten; forcing a flatten at all already means this
       run is no longer treated as an overnight hold.

    round 6's version unconditionally overwrote status with recovery's
    (equivalent to always taking branch 2, including for a failed
    pre-status -- the upgrade bug branch 1 above fixes). round 7's single
    severity-table version fixed that upgrade case but, by ranking
    "held_overnight" ABOVE "passed"/"completed_no_signals", let a
    SUCCESSFUL forced liquidation following a "held_overnight"
    pre-status keep reporting "held_overnight" (with flat=True) instead
    of recovery's own "passed" -- branch 2 above fixes that too, since
    "held_overnight" is not sticky and always defers to recovery's
    status.

    Both the pre-recovery status (outcome["status_before_recovery"]) and
    the post-recovery recovery dict (outcome["recovery"], carrying its
    own "status") are retained on `outcome` so neither input to this
    composition is lost."""
    pre_status = outcome.get("status")
    recovery_status = recovery["status"]
    outcome["status_before_recovery"] = pre_status
    outcome["recovery"] = recovery
    outcome["flat"] = recovery["flat"]
    outcome["status"] = pre_status if pre_status in _STICKY_FAILED_STATUSES else recovery_status
    return outcome


def _final_boundary_from_run_status(outcome):
    """True unless run_native itself ended the run as a legitimate hold.

    main() must not re-evaluate the session clock after run_native returns: a
    needs_attention end that crosses into POST before main() reaches this
    decision would otherwise be relabelled held_overnight (rebase review D2).
    """
    return outcome.get("status") != "held_overnight"


def trial_phase_and_exit_code(result):
    """D1: the single authority for deriving the durable trial-state
    ``phase`` and the CLI exit code from a run's own ``result`` (run_native's
    outcome dict, or the synthetic ``{"status": "needs_attention", ...}``
    result built when run_native itself raised). ``result["status"]`` is
    itself already the single authority for whether a non-flat end is a
    genuine "held_overnight" (run_native decides it once via
    ``_honest_overnight_hold`` and main() reuses that decision through
    ``_final_boundary_from_run_status`` rather than re-reading the clock) --
    this helper only turns that already-
    honest status into the two durable/observable outputs, so there is
    exactly one place either can diverge from ``result["status"]``.

    D5 (round 8): ``phase`` is derived from ``result["status"]`` FIRST, not
    from ``flat`` first. A round-7 version checked ``flat`` before
    ``status``, so a FAILED session that a forced liquidation nonetheless
    successfully flattened (status stays "needs_attention"/"failed" --
    sticky, see _apply_forced_recovery_outcome -- but flat is True) was
    recorded as phase "finished", silently bypassing every downstream
    resume/needs-attention guard that keys off phase (e.g. the
    ``resumable_hold`` check in ``main()``) even though the run itself was
    never anything but a failure that merely got tidied up afterwards.
    Status-first fixes that: needs_attention/failed status is phase
    "needs_attention" REGARDLESS of flat; held_overnight status is phase
    "held_overnight"; only an actually-passing status ("passed"/
    "completed_no_signals") together with flat=True is phase "finished" --
    a passing status that is somehow not flat (should not happen given
    run_native's/recover's own contracts, but this function does not
    trust that blindly) defensively falls through to "needs_attention"
    rather than mislabeling an inconsistent result as finished.

    "held_overnight" is its own terminal phase, distinct from
    "needs_attention" -- it is what makes the state resumable by the next
    overnight_holds invocation (see the ``resumable_hold`` check in
    ``main()``) instead of requiring an operator-driven recovery.
    """
    status = result["status"]
    if status in _STICKY_FAILED_STATUSES:
        phase = "needs_attention"
    elif status == "held_overnight":
        phase = "held_overnight"
    elif result.get("flat"):
        phase = "finished"
    else:
        phase = "needs_attention"
    exit_code = 0 if status in ("passed", "completed_no_signals", "held_overnight") else 3
    return phase, exit_code


def main():
    global LAST_OUTPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight", "paper", "recover"])
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=SOURCE / "config.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trial", default="adaptive-20260921")
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STOP.parent)
    parser.add_argument("--gate-result", type=Path, default=None,
                         help="promotion-gate result JSON from "
                              "blueprints/us-equities/data/promotion_gate.py; "
                              "required (status pass, hash-matched) for `paper`")
    parser.add_argument("--snapshot", type=Path, default=None,
                         help="the exact bars/universe input file the promotion "
                              "gate validated (its hash must match --gate-result's "
                              "input_sha256); required for `paper`")
    parser.add_argument("--live-dir", type=Path, default=None,
                         help="optional directory for a live record of this run: events.jsonl "
                              "(decisions and intents as they happen) and NautilusTrader's own "
                              "JSON log under nautilus/; observation only")
    args = parser.parse_args()
    LAST_OUTPUT = args.output
    if not re.fullmatch(r"[a-z0-9-]{1,24}", args.trial):
        raise ValueError("invalid_trial_id")
    config, limits, policy_config = load_config(args.config)
    session_policy = validate_session_policy(config)
    key, secret = credentials(args.env_file)
    attempts, responses = [], []
    def observe_request(kind, **kwargs):
        attempts.append({"timestamp": time.time(), "kind": kind})
        if len(attempts) > 50:
            raise SafetyError("preflight_request_bound")
    # G-e: only a validated leverage policy widens the preflight account
    # read to include margin fields (transport.normalize_account); the
    # default (no "leverage_policy" block) preflight is unchanged.
    include_margin = config.get("_leverage_policy") is not None
    try:
        observation = preflight(key, secret, config["symbols"], feed=config["feed"],
                                before_request=observe_request, request_observer=responses.append,
                                include_margin=include_margin)
    except TransportError as exc:
        result = {"status": "not_started", "stage": "preflight", "reason": str(exc),
                  "feed": config["feed"], "orders_submitted": 0, "http": responses,
                  "attempts": attempts}
        save(args.output, result)
        print(json.dumps({k: result[k] for k in ("status", "stage", "reason", "orders_submitted")}))
        return 2
    summary = public_preflight(observation, config)
    summary["http"] = responses
    summary["config_sha256"] = hashlib.sha256(args.config.read_bytes()).hexdigest()
    if args.command == "preflight":
        try:
            validate_preflight(observation, config, require_open=True, session_policy=session_policy)
            summary["status"] = "ready"
            # G-e: only set once validate_preflight's margin-entitlement
            # check (above) has already passed under the policy.
            leverage_policy = config.get("_leverage_policy")
            if leverage_policy is not None:
                summary["margin"] = {
                    "multiplier": str(config["_account_multiplier"]),
                    "intraday_buying_power": intraday_buying_power(observation["account"])[0],
                    "intraday_buying_power_field": intraday_buying_power(observation["account"])[1],
                    "regt_buying_power": observation["account"]["regt_buying_power"],
                    "requested_max_leverage": str(leverage_policy.max_leverage),
                    "policy_version": leverage_policy.version}
        except SafetyError as exc:
            summary.update(status="not_ready", reason=str(exc))
        save(args.output, summary)
        print(json.dumps({k: summary[k] for k in ("status", "orders_submitted")}, default=str))
        return 0 if summary["status"] == "ready" else 2
    gate_mode = "paper" if args.command == "paper" else None
    # Rebase review D1: overnight_holds relaxes the flat-account/no-open-orders
    # gate only to resume a trial this engine itself left "held_overnight".
    # A first trial (or any other prior phase) still requires a flat account,
    # so positions or orders created outside a trial are never adopted. The
    # phase is re-read under the account lock below and must still agree.
    prior_path = args.state_root / observation["account_identity_sha256"] / "adaptive" / "trial.json"
    try:
        prior_metadata = json.loads(prior_path.read_text()) if prior_path.exists() else None
    except (OSError, ValueError):
        prior_metadata = None
    # A non-object state file (e.g. [] or null) is treated as no resumable phase,
    # so the strict flat-account gate applies.
    prior_phase = prior_metadata.get("phase") if isinstance(prior_metadata, dict) else None
    prior_hold = bool(session_policy["overnight_holds"] and prior_phase == "held_overnight")
    try:
        # allow_existing (recovery mode) stays scoped to --command recover
        # only; overnight_holds must not relax the cash/equity floor, window
        # sizing or universe/benchmark checks (D4) -- it only relaxes the
        # separate flat-account/no-open-orders gate below, and only for a
        # resumable held trial (see prior_hold above).
        close = validate_preflight(observation, config, require_open=True,
                                   allow_existing=args.command == "recover",
                                   allow_existing_positions=(args.command == "recover" or prior_hold),
                                   session_policy=session_policy,
                                   mode=gate_mode, gate_result_path=args.gate_result, snapshot_path=args.snapshot)
    except SafetyError as exc:
        summary.update(status="not_started", reason=str(exc))
        save(args.output, summary)
        print(json.dumps({"status": "not_started", "reason": str(exc), "orders_submitted": 0}))
        return 2
    leverage_policy = config.get("_leverage_policy")
    # G-e/LEV-RI-1: --command recover skips _check_margin_entitlement (it is
    # sell-only, see validate_preflight above), so config["_account_multiplier"]
    # is never set on that path -- report the "margin" summary only when the
    # broker-proven multiplier actually exists.
    if leverage_policy is not None and config.get("_account_multiplier") is not None:
        summary["margin"] = {
            "multiplier": str(config["_account_multiplier"]),
            "intraday_buying_power": intraday_buying_power(observation["account"])[0],
            "intraday_buying_power_field": intraday_buying_power(observation["account"])[1],
            "regt_buying_power": observation["account"]["regt_buying_power"],
            "requested_max_leverage": str(leverage_policy.max_leverage),
            "policy_version": leverage_policy.version}
    fingerprint = observation["account_identity_sha256"]
    with account_lock_fingerprint(fingerprint):
        state_dir = args.state_root / fingerprint / "adaptive"
        metadata_path = state_dir / "trial.json"
        previous_metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else None
        # D2: a prior run that ended "held_overnight" (a reconciled, non-flat,
        # intentional hold, not a fault) is a resumable start for the next
        # overnight_holds invocation -- the D1 ledger-adoption path handles
        # picking the held position back up -- while every other non-finished
        # phase still requires explicit --command recover, unchanged.
        resumable_hold = bool(previous_metadata and previous_metadata.get("phase") == "held_overnight"
                              and session_policy["overnight_holds"])
        if resumable_hold != prior_hold:
            raise SafetyError("trial_state_changed_during_preflight")
        if (previous_metadata and args.command != "recover"
                and previous_metadata.get("phase") != "finished" and not resumable_hold):
            raise SafetyError("existing_trial_requires_explicit_recovery")
        if args.command == "recover" and not metadata_path.exists():
            raise SafetyError("no_owned_trial_to_recover")
        ledger = Ledger(state_dir / "ledger.sqlite3", limits)
        try:
            now = time.time()
            for attempt in attempts:
                if attempt["kind"] != "data_read":
                    if ledger.request_budget(attempt["timestamp"], "read"):
                        raise SafetyError("preflight_budget_inconsistent")
            # D4: under the default policy, close/market_open keep exactly
            # today's behaviour (the broker's own RTH close, always open).
            # Under extended_hours, entries must be bounded by the actual
            # continuous PRE->RTH->POST window close (20:00 ET), not the
            # broker's RTH-only close, and market_open must reflect whether
            # the session clock currently sees an active window at all.
            controller_close, controller_market_open = close, True
            if session_policy["extended_hours"]:
                now_dt = datetime.fromtimestamp(now, timezone.utc)
                info_now = session_at(now_dt)
                controller_market_open = info_now.kind != SessionKind.CLOSED
                if controller_market_open:
                    controller_close = extended_session_close(now_dt).astimezone(timezone.utc).timestamp()
            controller = Controller(ledger, controller_close, market_open=controller_market_open)
            if args.live_dir is not None:
                controller.events = LiveEventLog(args.live_dir / "events.jsonl")
                # Binds this run's live record to its own ledger and kill switch for
                # live_manifest.py (local state; the manifest never displays these paths).
                import safety as _safety
                (args.live_dir / "run.json").write_text(json.dumps(
                    {"trial": args.trial, "ledger": str(state_dir / "ledger.sqlite3"),
                     "stop_file": str(_safety.DEFAULT_STOP)}) + "\n")
            if args.command == "recover":
                metadata = previous_metadata
                if metadata["config_sha256"] != summary["config_sha256"]:
                    raise SafetyError("recovery_config_differs_from_frozen_trial")
            else:
                if previous_metadata:
                    if previous_metadata["config_sha256"] != summary["config_sha256"]:
                        raise SafetyError("next_trial_config_differs_from_frozen_limits")
                    if (ledger.positions() or ledger.unresolved()) and not resumable_hold:
                        raise SafetyError("next_trial_requires_recovery")
                    if not resumable_hold:
                        expected_cash = Decimal(previous_metadata["baseline_cash"]) + ledger.accounting().cash_delta_usd
                        if abs(Decimal(observation["account"]["cash"]) - expected_cash) > Decimal("0.01"):
                            raise SafetyError("next_trial_cash_mismatch")
                # S2: the resumable-hold path above already bypasses the
                # ordinary flat/cash-reconciliation guards (its state is
                # expected to be non-flat, adopted via D1's broker-snapshot
                # path once run_native starts); begin_next_trial's own
                # internal flat check would otherwise raise
                # next_trial_requires_flat_and_terminal against exactly
                # that, defeating the bypass above.
                if resumable_hold:
                    held_resume_matches_ledger(ledger, observation)
                    ledger.resume_held_trial(now, args.trial)
                else:
                    ledger.begin_next_trial(now, args.trial)
                metadata = {"trial_id": args.trial,
                            "started_at": previous_metadata["started_at"] if previous_metadata else now,
                            "current_trial_started_at": now, "config_sha256": summary["config_sha256"],
                            "baseline_cash": previous_metadata["baseline_cash"] if previous_metadata else observation["account"]["cash"],
                            "phase": "starting"}
                save(metadata_path, metadata)
            def fresh_port(recovering=False):
                needed = sorted(set(ledger.positions()) | {i.symbol for i in ledger.unresolved()})
                return controller.bind(AlpacaPaperTransport(key, secret, config["symbols"],
                    before_request=controller.before_request, before_submit=controller.before_submit,
                    sink_observation=controller.observe, request_observer=responses.append,
                    quote_timeout=config["quote_max_age_seconds"], feed=config["feed"],
                    required_quote_symbols=needed if recovering and needed else config["benchmarks"],
                    history_start=datetime.fromtimestamp(metadata["started_at"], timezone.utc),
                    extended_hours_allowed=session_policy["extended_hours"],
                    include_margin=leverage_policy is not None))
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, lambda *_: setattr(controller, "stop", True))
            async def execute():
                from recovery import recover
                if args.command == "recover":
                    controller.port = fresh_port(True)
                    return await recover(controller, metadata, config)
                controller.port = fresh_port()
                try:
                    outcome = await run_native(controller, policy_config, observation["assets"], args.trial,
                                               config, metadata["baseline_cash"], account_fingerprint=fingerprint,
                                               log_directory=None if args.live_dir is None else args.live_dir / "nautilus")
                except Exception as exc:
                    outcome = {"status": "needs_attention", "flat": False, "native_fill_events": 0,
                               "error_type": type(exc).__name__}
                    port_health = getattr(controller.port, "health", {})
                    outcome["dropped_quotes"] = {
                        "by_reason": {str(k): int(v) for k, v in port_health.get("dropped_quotes", {}).items()},
                        "by_symbol": {str(k): int(v) for k, v in port_health.get("dropped_quotes_by_symbol", {}).items()}}
                if isinstance(controller.events, LiveEventLog):
                    outcome["live_event_write_errors"] = controller.events.write_errors
                if ledger.positions() or ledger.unresolved():
                    controller.stop = True
                    # This CLI invocation cannot yet tell whether it is the
                    # final boundary of a *multi-day* overnight-holds trial
                    # (no scheduling mechanism spans invocations in this
                    # round -- documented as unresolved in the task
                    # handoff); a genuine, reconciled, error-free end at an
                    # actual session boundary defaults to not-final so it
                    # can hold rather than force-liquidate. S1: that default
                    # must not extend to every non-flat end -- a mid-RTH
                    # error, an unreconciled state, or a risk halt is not a
                    # legitimate hold and must still force through the
                    # flat/recover path below, regardless of
                    # overnight_holds. The default policy is unaffected:
                    # must_end_flat always requires flat regardless of
                    # is_final_boundary when overnight_holds is False (D5).
                    # Rebase review D2: run_native already decided the hold at
                    # the moment its run ended (_run_native_status). Reuse
                    # that decision instead of re-reading the clock here, so
                    # a needs_attention end that crosses into POST before this
                    # line runs can never be relabelled held_overnight.
                    is_final_boundary = _final_boundary_from_run_status(outcome)
                    if must_end_flat(session_policy, is_final_boundary=is_final_boundary):
                        controller.port = fresh_port(True)
                        recovery = await recover(controller, metadata, config)
                        outcome = _apply_forced_recovery_outcome(outcome, recovery)
                    else:
                        state_now = controller.ledger.accounting()
                        receipt = boundary_receipt(
                            datetime.fromtimestamp(time.time(), timezone.utc),
                            positions=[{"symbol": p.symbol, "qty": str(p.qty)}
                                      for p in controller.ledger.positions().values() if p.qty],
                            cash=Decimal(metadata["baseline_cash"]) + state_now.cash_delta_usd,
                            cash_delta=state_now.cash_delta_usd,
                            open_orders=len(controller.ledger.unresolved()), reconciled_at_boundary=True)
                        outcome.setdefault("boundary_receipts", []).append(receipt)
                        outcome["flat"] = False
                        outcome["status"] = "held_overnight"
                return outcome
            result = asyncio.run(execute())
            result.update(preflight=summary, mode="adaptive_paper", feed=config["feed"],
                          config_sha256=summary["config_sha256"])
            phase, exit_code = trial_phase_and_exit_code(result)
            metadata["phase"] = phase
            metadata["status"] = result["status"]
            save(metadata_path, metadata)
            save(args.output, result)
            print(json.dumps({k: result.get(k) for k in ("status", "flat", "native_fill_events")}, default=str))
            return exit_code
        finally:
            ledger.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Never serialize arbitrary provider exception text or request headers.
        failure = {"status": "failed", "error_type": type(exc).__name__,
                   "reconciliation": "not_established"}
        if LAST_OUTPUT is not None:
            save(LAST_OUTPUT, failure)
        print(json.dumps(failure))
        raise SystemExit(3)
