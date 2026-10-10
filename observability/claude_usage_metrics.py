#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["prometheus-client==0.26.0"]
# ///
"""Publish CC-recorded Claude limits and API ledger amounts to a node_exporter textfile.

This adapter only reads explicitly named data files. It never launches a model,
loads a credential/configuration file, or retains stream text or ledger identities.
See docs/claude-usage-observability.md for the CC-owned sampling contract.
"""
import argparse
import copy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time

from prometheus_client import CollectorRegistry, Gauge, write_to_textfile

WINDOWS = ("five_hour", "seven_day")
STATUSES = ("allowed", "allowed_warning", "rejected")
ACCOUNT = re.compile(r"acct-[1-9][0-9]*\Z")
KEY_INDEX = re.compile(r"key-[1-9][0-9]*\Z")
KEY_HASH = re.compile(r"[a-f0-9]{64}\Z")
EDGE_USD = 200.0


class InputError(ValueError):
    """A bounded error message that never includes raw input or a private path."""


def number(value, *, signed=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        parsed = float(value)
    except OverflowError:
        return None
    return parsed if math.isfinite(parsed) and (signed or parsed >= 0) else None


def read_data(path, limit):
    # api-actions' producer takes LOCK_EX on the ledger while appending a row.
    with path.open("rb") as source:
        fcntl.flock(source, fcntl.LOCK_SH)
        data = source.read(limit + 1)
        stamp = os.fstat(source.fileno()).st_mtime
    if len(data) > limit:
        raise InputError("input exceeds size bound")
    try:
        return data.decode("utf-8"), stamp
    except UnicodeDecodeError:
        raise InputError("input is not UTF-8") from None


def parse_capture(text, observed_at, previous=None):
    """Merge native transition events without refreshing fields absent from an event.

Official events name one rateLimitType. The CC's recorded unifiedWindows shape
can name both windows. A rejection without a supported scope conservatively
marks both as exhausted; `assumed` distinguishes this from measured utilization.
"""
    result = copy.deepcopy(previous or {})
    errors = seen = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except (ValueError, RecursionError):
            errors += 1
            continue
        if not isinstance(event, dict):
            errors += 1
            continue
        if event.get("type") != "rate_limit_event":
            continue
        info = event.get("rate_limit_info")
        if not isinstance(info, dict) or info.get("status") not in STATUSES:
            errors += 1
            continue
        seen += 1
        unified = info.get("unifiedWindows", {})
        if not isinstance(unified, dict):
            errors += 1
            unified = {}
        updates = {}
        for window in WINDOWS:
            if window in unified:
                if isinstance(unified[window], dict):
                    updates[window] = unified[window].copy()
                else:
                    errors += 1
        scope = info.get("rateLimitType")
        if scope in WINDOWS:
            updates.setdefault(scope, {}).update({k: info[k] for k in ("utilization", "resetsAt") if k in info})
        rejected = info["status"] == "rejected"
        unknown_scope = rejected and scope not in WINDOWS
        forced = WINDOWS if unknown_scope else ((scope,) if rejected else ())
        for window in forced:
            updates.setdefault(window, {})
        for window, update in updates.items():
            local_status = update.get("status", "allowed")
            if local_status not in STATUSES:
                errors += 1
                if window not in forced:
                    continue
            exhausted = window in forced or local_status == "rejected"
            current = result.setdefault(window, {})
            utilization = number(update.get("utilization"))
            if "utilization" in update and update["utilization"] is not None and utilization is None:
                errors += 1
            if exhausted:
                utilization = 1.0
            if utilization is not None and observed_at >= current.get("observed_at", 0):
                current.update(utilization=min(utilization, 1.0), observed_at=observed_at,
                               assumed=int(unknown_scope))
            reset = number(update.get("resetsAt"))
            if "resetsAt" in update and update["resetsAt"] is not None and (reset is None or reset == 0):
                errors += 1
            if reset and observed_at >= current.get("reset_observed_at", 0):
                current.update(reset=reset, reset_observed_at=observed_at)
    return result, errors, seen


def alias_hash(alias):
    """Hash the ledger's non-secret key alias immediately; never persist the alias."""
    if alias is None:
        return None
    if (not isinstance(alias, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", alias)
            or alias.lower().startswith("sk-")):
        raise InputError("invalid ledger alias")
    return hashlib.sha256(alias.encode("utf-8")).hexdigest()


def ledger_totals(text, legacy_key_alias=None):
    """Follow api-actions harness/common.py totals, without importing its runtime.

Debit refs own settlement attribution. max_usd is an open reservation; settle
actual_usd includes any outcome=unknown amount held pending reconciliation.
Provider snapshots/notes are separate evidence and never additional charges.
"""
    legacy = alias_hash(legacy_key_alias)
    totals, debit_keys, pending = {}, {}, {}

    def column(key):
        return totals.setdefault(key, {"spend": 0.0, "pending": 0.0, "uncertain": 0.0})

    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except (ValueError, RecursionError):
            raise InputError("invalid ledger JSON") from None
        if not isinstance(row, dict):
            raise InputError("invalid ledger row")
        kind = row.get("kind")
        if kind not in ("debit", "settle", "void"):
            continue
        ref = row.get("ref")
        if not isinstance(ref, str) or not ref or len(ref) > 512:
            raise InputError("invalid ledger reference")
        if kind == "debit":
            key = alias_hash(row.get("key")) or legacy
            amount = number(row.get("max_usd"))
            if amount is None:
                raise InputError("invalid ledger amount")
            debit_keys[ref] = key
            pending[ref] = (key, amount)
            column(key)
        else:
            key = debit_keys[ref] if ref in debit_keys else (alias_hash(row.get("key")) or legacy)
            # Reconciliation settlements can be negative credits; debits cannot.
            amount = number(row.get("actual_usd"), signed=True)
            if amount is None:
                raise InputError("invalid ledger amount")
            column(key)["spend"] += amount
            if row.get("outcome") == "unknown":
                column(key)["uncertain"] += amount
            pending.pop(ref, None)
    for key, amount in pending.values():
        column(key)["pending"] += amount
    if any(not math.isfinite(value) for values in totals.values() for value in values.values()):
        raise InputError("invalid ledger total")
    return totals


def load_state(path):
    if not path.exists():
        return {"version": 1, "windows": {}, "key_indexes": {}}
    try:
        raw = json.loads(read_data(path, 1024 * 1024)[0])
        if raw["version"] != 1:
            raise InputError("unsupported state version")
        indexes = raw["key_indexes"]
        windows = raw["windows"]
        if not isinstance(indexes, dict) or not isinstance(windows, dict):
            raise InputError("invalid usage state")
        if any(not KEY_HASH.fullmatch(k) or not isinstance(v, str) or not KEY_INDEX.fullmatch(v)
               for k, v in indexes.items()) or len(set(indexes.values())) != len(indexes):
            raise InputError("invalid usage state")
        clean = {"version": 1, "windows": {}, "key_indexes": indexes}
        for account, observations in windows.items():
            if not ACCOUNT.fullmatch(account) or not isinstance(observations, dict):
                raise InputError("invalid usage state")
            clean["windows"][account] = {}
            for window, values in observations.items():
                if window not in WINDOWS or not isinstance(values, dict):
                    raise InputError("invalid usage state")
                kept = {k: v for k, v in values.items()
                        if k in ("utilization", "observed_at", "assumed", "reset", "reset_observed_at")}
                if any(number(v) is None for v in kept.values()):
                    raise InputError("invalid usage state")
                if "utilization" in kept and (kept["utilization"] > 1 or "observed_at" not in kept):
                    raise InputError("invalid usage state")
                if "reset" in kept and "reset_observed_at" not in kept:
                    raise InputError("invalid usage state")
                clean["windows"][account][window] = kept
        return clean
    except (ValueError, KeyError, TypeError, RecursionError):
        raise InputError("invalid usage state") from None


def save_state(path, state):
    # Only numeric observations and the hash->opaque-index registry reach disk.
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=path.name + ".", delete=False) as target:
        temporary = Path(target.name)
        try:
            json.dump(state, target, sort_keys=True, allow_nan=False)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def collect(captures, ledger_path, state_path, output_path, *, now=None, legacy_key_alias=None):
    """Read a complete snapshot, retain numeric state, publish native atomic exposition."""
    if not captures or any(not isinstance(a, str) or not ACCOUNT.fullmatch(a) for a in captures):
        raise InputError("accounts must be opaque acct-N indexes")
    if output_path.suffix != ".prom":
        raise InputError("output must be a .prom textfile")
    inputs = {Path(p).resolve() for p in captures.values()} | {ledger_path.resolve()}
    if state_path.resolve() in inputs or output_path.resolve() in inputs or state_path.resolve() == output_path.resolve():
        raise InputError("data and output paths must differ")
    now = time.time() if now is None else now
    if number(now) is None or now == 0:
        raise InputError("invalid collection time")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Serialize key-index assignment and state replacement across collector invocations.
    with state_path.with_suffix(state_path.suffix + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load_state(state_path)
        registry = CollectorRegistry()  # no Python/process/platform or arbitrary source labels

        def gauge(name, help_text, labels=()):
            return Gauge(name, help_text, labels, registry=registry)

        utilization = gauge("claude_max_utilization_ratio", "Last observed Max limit fraction; rejected is one.", ("account", "window"))
        observed = gauge("claude_max_observed_timestamp_seconds", "Unix seconds of the utilization observation.", ("account", "window"))
        reset = gauge("claude_max_reset_timestamp_seconds", "Native reset time as Unix seconds, not a sample timestamp.", ("account", "window"))
        reset_observed = gauge("claude_max_reset_observed_timestamp_seconds", "Unix seconds of the reset observation.", ("account", "window"))
        assumed = gauge("claude_max_rejection_assumed", "One when an unscoped rejection conservatively exhausts both windows.", ("account", "window"))
        capture_at = gauge("claude_max_capture_timestamp_seconds", "Recorded capture mtime as Unix seconds.", ("account",))
        capture_success = gauge("claude_max_capture_success", "One when a valid native rate limit event was read.", ("account",))
        input_errors = gauge("claude_usage_input_errors", "Bounded input error count in this collection.", ("source",))
        errors = 0
        for account, path in captures.items():
            success = 0
            previous = state["windows"].get(account, {})
            try:
                text, stamp = read_data(Path(path), 2 * 1024 * 1024)
                if stamp <= 0 or stamp > now:
                    raise InputError("invalid capture time")
                previous, failures, seen = parse_capture(text, stamp, previous)
                errors += failures
                success = int(seen > 0)
                capture_at.labels(account).set(stamp)
            except (OSError, InputError):
                errors += 1
            state["windows"][account] = previous
            capture_success.labels(account).set(success)
            for window, values in previous.items():
                if "utilization" in values:
                    utilization.labels(account, window).set(values["utilization"])
                    observed.labels(account, window).set(values["observed_at"])
                    assumed.labels(account, window).set(values.get("assumed", 0))
                if "reset" in values:
                    reset.labels(account, window).set(values["reset"])
                    reset_observed.labels(account, window).set(values["reset_observed_at"])
        input_errors.labels("capture").set(errors)
        ledger_success = gauge("claude_usage_ledger_success", "One when all financial rows parsed successfully.")
        try:
            totals = ledger_totals(read_data(ledger_path, 32 * 1024 * 1024)[0], legacy_key_alias)
        except (OSError, InputError):
            input_errors.labels("ledger").set(1)
            ledger_success.set(0)
        else:
            input_errors.labels("ledger").set(0)
            ledger_success.set(1)
            spend = gauge("claude_api_spend_usd", "Ledger accounted charges including uncertain amounts.", ("key",))
            pending = gauge("claude_api_pending_usd", "Open debit reservations, separate from charges.", ("key",))
            uncertain = gauge("claude_api_uncertain_usd", "Subset of charges retained pending reconciliation.", ("key",))
            edge = gauge("claude_api_edge_usd", "Per-key owner-directed API spend edge in USD.", ("key",))
            unattributed = totals.get(None, {"spend": 0, "pending": 0, "uncertain": 0})
            for field in ("spend", "pending", "uncertain"):
                gauge(f"claude_api_unattributed_{field}_usd", f"Ledger {field} without a known key attribution.").set(unattributed[field])
            indexes = state["key_indexes"]
            next_index = max((int(v.split("-")[1]) for v in indexes.values()), default=0) + 1
            for key_hash in sorted(k for k in totals if k is not None):
                if key_hash not in indexes:
                    indexes[key_hash] = f"key-{next_index}"
                    next_index += 1
                label = indexes[key_hash]
                spend.labels(label).set(totals[key_hash]["spend"])
                pending.labels(label).set(totals[key_hash]["pending"])
                uncertain.labels(label).set(totals[key_hash]["uncertain"])
                edge.labels(label).set(EDGE_USD)
        gauge("claude_usage_collection_timestamp_seconds", "Unix seconds when these data files were collected.").set(now)
        save_state(state_path, state)
        write_to_textfile(str(output_path), registry)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="append", required=True, metavar="acct-N=PATH",
                        help="CC-owned opaque account index and recorded stream-json file; repeat per account")
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True, help="Persistent numeric state and hashed key index registry")
    parser.add_argument("--output", type=Path, required=True, help="node_exporter collector .prom path")
    parser.add_argument("--legacy-key-alias", help="Optional non-secret producer alias for pre-key ledger rows")
    args = parser.parse_args()
    try:
        captures = {}
        for entry in args.capture:
            account, separator, path = entry.partition("=")
            if not separator or not path or not ACCOUNT.fullmatch(account) or account in captures:
                raise InputError("captures require distinct opaque acct-N=PATH entries")
            captures[account] = Path(path)
        collect(captures, args.ledger, args.state, args.output, legacy_key_alias=args.legacy_key_alias)
    except (InputError, OSError):
        print("Claude usage collection failed; check the named data inputs and writable output/state directories.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
