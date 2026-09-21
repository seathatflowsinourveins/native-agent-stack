#!/usr/bin/env python3
"""Project-local metadata projection of native counters; never a savings ledger."""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

LOKI = "http://127.0.0.1:13100/loki/api/v1/push"
LIMIT = 1024 * 1024
REPORT_LIMIT = 16 * LIMIT
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}\Z")
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# Dated public inventory, not arbitrary names copied from a private input file.
COVERAGE_IDS = """affaan-m/ECC agent-browser agentsview ai-memory ast-grep ccusage
claude-code claude-hud codebase-memory-mcp codex codex-for-claude context-hub
context-mode davila7/claude-code-templates difftastic gitleaks headroom
huggingface-hub-native markitdown mcp-inspector mcporter openresearch playwright-cli
promptfoo qdrant qmd repomix rtk sandbox-runtime serena
shanraisshan/claude-code-best-practice shellcheck socraticode toon vllm worktrunk
opentelemetry-collector-contrib prometheus loki grafana alertmanager ntfy duckdb
restic dagu lean syft alpaca-py systemd pandas skfolio edgartools zizmor beads
skills-ref otel-tui llama-cpp jcodemunch-mcp nextjs react fastapi postgresql poppler
apple-container playwright-test omniroute tavily-cli nautilus-trader""".split()
REPORT_SCOPES = {
    ("context-mode", "Native Codex"): ("context-mode-native-codex", "Context Mode: native Codex"),
    ("context-mode", "Native Claude"): ("context-mode-native-claude", "Context Mode: native Claude"),
    ("context-mode", "Desktop WSL"): ("context-mode-desktop-wsl", "Context Mode: Desktop WSL"),
    ("headroom", "Linux / native last 30 days"): ("headroom", "Headroom: retained 30 days"),
    ("jcodemunch", "Linux / upstream default index"): ("jcodemunch", "jCodeMunch: default index"),
}


def utc(value):
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).isoformat()


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("invalid nonnegative measurement")
    return value


def count(value):
    value = number(value)
    if int(value) != value:
        raise ValueError("invalid count")
    return int(value)


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("missing timestamp")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp lacks timezone")
    return parsed.timestamp()


def base_row(entity, title, kind, command, boundary, observed, record_kind="savings"):
    return dict(schema_version=1, record_kind=record_kind, entity_id=entity, title=title,
                state="unknown", source_updated_at=None, source_unix=None,
                observed_unix=observed, source_command=command, kind=kind, boundary=boundary)


def dated(row, source, now, stale_after, basis):
    if not math.isfinite(source) or source < 0 or source > now + 60:
        raise ValueError("invalid source time")
    row.update(source_updated_at=utc(source), source_unix=source,
               timestamp_basis=basis, state="stale" if now - source > stale_after else "ok")
    return row


def strict_json(raw):
    def reject(value):
        raise ValueError("non-finite JSON")
    return json.loads(raw, parse_constant=reject)


def validate_config(config):
    required = {"token_report", "project", "rtk", "ai_memory", "qmd", "state_dir", "loki_url"}
    if not isinstance(config, dict) or not required <= config.keys() or config.keys() - required - {"qdrant", "stale_after_seconds", "command_timeout_seconds", "coverage"}:
        raise ValueError("invalid config keys")
    def absolute(value):
        if not isinstance(value, str) or not Path(value).is_absolute() or "\x00" in value:
            raise ValueError("config requires absolute paths")
    for key in ("token_report", "project", "rtk", "state_dir"):
        absolute(config[key])
    for name, keys in (("ai_memory", {"binary", "data_dir", "workspace", "project"}), ("qmd", {"binary", "index", "collection"})):
        section = config[name]
        if not isinstance(section, dict) or set(section) != keys:
            raise ValueError("invalid native scope config")
        absolute(section["binary"])
        for key in keys - {"binary"}:
            if key == "data_dir":
                absolute(section[key])
            elif not isinstance(section[key], str) or not SAFE_NAME.fullmatch(section[key]):
                raise ValueError("invalid native scope name")
    if config["loki_url"] != LOKI:
        raise ValueError("Loki must use the fixed loopback push endpoint")
    q = config.get("qdrant")
    if q is not None:
        if not isinstance(q, dict) or set(q) != {"url", "collection"}:
            raise ValueError("invalid Qdrant config")
        if not re.fullmatch(r"http://127\.0\.0\.1:[0-9]{1,5}", q["url"]) or not 1 <= urllib.parse.urlsplit(q["url"]).port <= 65535:
            raise ValueError("Qdrant must be an exact IPv4 loopback origin")
        if not SAFE_NAME.fullmatch(q["collection"]):
            raise ValueError("invalid allowlisted Qdrant collection")
    for key, default, low, high in (("stale_after_seconds", 1800, 1, 86400), ("command_timeout_seconds", 10, 1, 30)):
        config[key] = count(config.get(key, default))
        if not low <= config[key] <= high:
            raise ValueError("invalid collection bound")
    if type(config.get("coverage", True)) is not bool:
        raise ValueError("coverage must be boolean")
    return config


def private_dir(path):
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) != 0o700 or path.resolve() != path:
        raise ValueError("state directory must be owned, mode 0700, without symlinks")
    return path


def write_private(path, data):
    # Caller owns the directory and serializes collectors with flock.
    temp = path.with_name(path.name + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    return {"file": path.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


class Recorder:
    def __init__(self, state, timeout):
        self.state, self.timeout, self.records = state, timeout, []

    def retain(self, name, record, stdout, stderr):
        record["stdout"] = write_private(self.state / (name + ".stdout"), stdout)
        record["stderr"] = write_private(self.state / (name + ".stderr"), stderr)
        self.records.append(record)

    def command(self, name, argv, cwd):
        started = time.time()
        record = {"id": name, "argv": argv, "cwd": str(cwd), "started_at": utc(started), "exit_code": None, "error": None}
        output = {"stdout": bytearray(), "stderr": bytearray()}
        process = None
        try:
            process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            with selectors.DefaultSelector() as selector:
                for stream in output:
                    selector.register(getattr(process, stream), selectors.EVENT_READ, stream)
                deadline = time.monotonic() + self.timeout
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("native command deadline")
                    for key, _ in selector.select(min(remaining, 0.2)):
                        block = os.read(key.fileobj.fileno(), 65536)
                        if not block:
                            selector.unregister(key.fileobj)
                            continue
                        target = output[key.data]
                        available = LIMIT - len(target)
                        target.extend(block[:available])
                        if len(block) > available:
                            raise OverflowError("native output limit; retained prefix only")
                process.wait(timeout=max(0.01, deadline - time.monotonic()))
                if process.returncode:
                    record["error"] = "nonzero_exit"
        except (OSError, TimeoutError, subprocess.TimeoutExpired, OverflowError) as exc:
            record["error"] = type(exc).__name__
        finally:
            if process:
                if record["error"] or process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.wait()
                record["exit_code"] = process.returncode
                process.stdout.close()
                process.stderr.close()
            record["completed_at"] = utc(time.time())
            self.retain(name, record, bytes(output["stdout"]), bytes(output["stderr"]))
        return None if record["error"] else bytes(output["stdout"])

    def get(self, name, url):
        record = {"id": name, "method": "GET", "url": url, "started_at": utc(time.time()), "http_status": None, "error": None}
        raw = b""
        try:
            status, raw = request(url, timeout=self.timeout)
            record["http_status"] = status
            if status != 200:
                raise ValueError("unexpected HTTP status")
        except (OSError, ValueError) as exc:
            record["error"] = type(exc).__name__
        record["completed_at"] = utc(time.time())
        self.retain(name, record, raw, b"")
        return None if record["error"] else raw


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(url, data=None, timeout=10):
    # Neither proxy environment variables nor redirect targets can escape loopback.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        response = opener.open(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        raw = response.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError("HTTP response exceeds limit")
        return response.status, raw


def rtk_metrics(raw):
    s = strict_json(raw)["summary"]
    fields = {key: count(s[key]) for key in ("total_commands", "total_input", "total_output", "total_saved")}
    return dict(value=fields["total_saved"], estimated_saved=fields["total_saved"], unit="estimated_tokens",
                total_commands=fields["total_commands"], input_tokens=fields["total_input"], output_tokens=fields["total_output"])


def memory_metrics(raw):
    c = strict_json(raw)["counts"]
    fields = {key: count(c[key]) for key in ("pages_latest", "pages_all", "sessions", "observations")}
    return dict(value=fields["pages_latest"], unit="pages", **fields)


def qmd_metrics(raw, collection):
    text = ANSI.sub("", raw.decode("utf-8"))
    def extract(pattern):
        matches = re.findall(pattern, text, re.MULTILINE)
        if len(matches) != 1:
            raise ValueError("ambiguous or missing QMD status field")
        return int(matches[0])
    total = extract(r"^\s+Total:\s+(\d+) files indexed\s*$")
    vectors = extract(r"^\s+Vectors:\s+(\d+) embedded\s*$")
    documents = extract(r"^  " + re.escape(collection) + r" \(qmd://" + re.escape(collection) + r"/\)\n(?:    [^\n]*\n)*?    Files:\s+(\d+)(?: [^\n]*)?$")
    return dict(value=documents, unit="files", collection_files=documents, index_files=total, index_vectors=vectors)


def qdrant_metrics(raw):
    doc = strict_json(raw)
    if doc.get("status") != "ok":
        raise ValueError("Qdrant API rejected request")
    r = doc["result"]
    if r.get("status") not in ("green", "yellow", "grey", "red"):
        raise ValueError("unknown Qdrant collection status")
    return dict(value=count(r["points_count"]), points_count=count(r["points_count"]),
                unit="points", collection_status=r["status"], segments_count=count(r["segments_count"]))


def report_rows(report, observed, stale_after, report_mtime):
    rows = []
    native = report.get("native", [])
    if not isinstance(native, list):
        native = []
    for (tool, scope), (entity, title) in REPORT_SCOPES.items():
        context = tool == "context-mode"
        boundary = ("One runtime snapshot: retained estimate = event count x 256; session estimate = kept-out bytes / 4. Different bases, not additive or provider savings. Retention can decrease counters." if context else
                    "Latest native report capture; retained tool estimate, overlapping with other counters, not avoided provider usage.")
        row = base_row(entity, title, "upstream estimate", "existing token report: native.latest", boundary, observed)
        try:
            matches = [n for n in native if isinstance(n, dict) and n.get("tool") == tool and n.get("scope") == scope]
            if len(matches) != 1:
                raise ValueError("missing or duplicate native scope")
            latest = matches[0]["latest"]
            if latest.get("success") is not True:
                raise ValueError("latest native capture failed")
            metrics = latest["metrics"]
            saved = number(metrics["saved"])
            captured = timestamp(latest["observed_at"])
            source = number(metrics["raw"]["updated_at"]) / 1000 if context else captured
            dated(row, source, observed, stale_after, "native_persisted_updated_at" if context else "native_command_capture_in_report")
            if captured > observed + 60 or report_mtime > observed + 60:
                raise ValueError("future report capture")
            row.update(value=saved, estimated_saved=saved, unit="estimated_tokens",
                       source_capture_unix=captured, report_file_unix=report_mtime)
            if context:
                row["session_estimated_saved"] = number(metrics["session_estimated_saved"])
        except (KeyError, TypeError, ValueError, OverflowError):
            row = base_row(entity, title, "upstream estimate", "existing token report: native.latest", boundary, observed)
        rows.append(row)
    return rows


def coverage_rows(report, observed):
    entries = report.get("coverage_matrix", [])
    if not isinstance(entries, list):
        return []
    try:
        source = timestamp(report["generated_at"])
        if source > observed + 60:
            return []
    except (KeyError, TypeError, ValueError):
        return []
    rows = []
    for name in COVERAGE_IDS:
        matches = [r for r in entries if isinstance(r, dict) and r.get("id") == name]
        if len(matches) != 1:
            continue
        latest = matches[0].get("latest_pass", {})
        status = latest.get("status", "") if isinstance(latest, dict) else ""
        coverage = "not_run_in_original_audit" if status == "Not executed in this pass" else "original_audit_has_record" if isinstance(status, str) and status else "unavailable"
        if status == "Evidence unavailable":
            coverage = "unavailable"
        receipts = matches[0].get("canonical_receipts") or []
        receipt_ids = {r["id"] for r in receipts if isinstance(r, dict)
                       and isinstance(r.get("id"), str) and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,127}", r["id"])
                       and r.get("path") == "evidence/receipts/" + r["id"] + ".json"
                       and isinstance(r.get("component_ids"), list)
                       and all(isinstance(component, str) for component in r["component_ids"])
                       and name in r["component_ids"]} if isinstance(receipts, list) else set()
        row = base_row("coverage-" + name.replace("/", "--"), name, "historical coverage inventory",
                       "existing token report: coverage_matrix", "Original audit and canonical receipt count are separate provenance; neither asserts a current pass. Source date is report generation, not native execution. Read receipt scope in the full report.", observed, "coverage")
        row.update(state="historical", source_unix=source, source_updated_at=utc(source), coverage_status=coverage,
                   canonical_receipt_count=len(receipt_ids), timestamp_basis="token_report_generated_at")
        rows.append(row)
    return rows


def collect(config, recorder, observed):
    rows = []
    specs = [
        ("rtk-global", "RTK: all retained projects", "upstream output estimate", [config["rtk"], "gain", "--format", "json"], "rtk gain --format json", rtk_metrics, "savings", "Retained RTK history, including this project; overlaps project and context counters; not provider usage."),
        ("rtk-project", "RTK: configured project", "upstream output estimate", [config["rtk"], "gain", "--project", "--format", "json"], "rtk gain --project --format json", rtk_metrics, "savings", "Explicit working directory; subset of global retained history, not provider usage."),
        ("ai-memory", "ai-memory: entire configured database", "native inventory", [config["ai_memory"]["binary"], "--data-dir", config["ai_memory"]["data_dir"], "status", "--json"], "ai-memory --data-dir <configured-db> status --json", memory_metrics, "memory", "Database-wide counts. CLI status has no workspace/project selector; configured project labels do not filter these counts."),
        ("qmd", "QMD: configured collection", "native inventory", [config["qmd"]["binary"], "--index", config["qmd"]["index"], "status"], "qmd --index <configured-index> status", lambda raw: qmd_metrics(raw, config["qmd"]["collection"]), "memory", "Selected collection files; vector and total counts apply to its entire index. Zero vectors can be intentional BM25 operation."),
    ]
    for entity, title, kind, argv, command, parser, record_kind, boundary in specs:
        row = base_row(entity, title, kind, command, boundary, observed, record_kind)
        raw = recorder.command(entity, argv, config["project"])
        try:
            if raw is None:
                raise ValueError("command failed")
            values = parser(raw)
            dated(row, timestamp(recorder.records[-1]["completed_at"]), time.time(), config["stale_after_seconds"], "fresh_native_command_capture")
            row.update(values)
        except (KeyError, TypeError, ValueError, UnicodeError):
            recorder.records[-1]["projection_error"] = "invalid_native_metadata" if raw is not None else "native_command_failed"
        rows.append(row)
    if config.get("qdrant"):
        row = base_row("qdrant", "Qdrant: configured collection", "native inventory", "GET /collections/<allowlisted-collection>", "Native points_count for one explicitly selected collection; vector representations are not added together.", observed, "memory")
        q = config["qdrant"]
        raw = recorder.get("qdrant", q["url"] + "/collections/" + q["collection"])
        try:
            if raw is None:
                raise ValueError("HTTP failed")
            values = qdrant_metrics(raw)
            dated(row, timestamp(recorder.records[-1]["completed_at"]), time.time(), config["stale_after_seconds"], "fresh_native_api_capture")
            row.update(values)
        except (KeyError, TypeError, ValueError, UnicodeError):
            recorder.records[-1]["projection_error"] = "invalid_native_metadata" if raw is not None else "native_api_failed"
        rows.append(row)
    report, mtime = {}, observed
    source = {"id": "token-report", "path": config["token_report"], "error": None}
    try:
        path = Path(config["token_report"])
        with path.open("rb") as handle:
            mtime = os.fstat(handle.fileno()).st_mtime
            raw = handle.read(REPORT_LIMIT + 1)
        if len(raw) > REPORT_LIMIT:
            raise ValueError("report exceeds limit")
        source.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), file_mtime=utc(mtime))
        report = strict_json(raw)
        if not isinstance(report, dict):
            raise ValueError("report must be object")
    except (OSError, ValueError):
        report = {}
        source["error"] = "unavailable_or_invalid_report"
    recorder.records.append(source)
    rows.extend(report_rows(report, observed, config["stale_after_seconds"], mtime))
    if config.get("coverage", True):
        rows.extend(coverage_rows(report, observed))
    marker = base_row("snapshot", "Native data snapshot", "collector generation", "snapshot.py --config <private-config>", "One generation; failure rows supersede earlier success. No sum across estimates or token scopes.", observed, "snapshot")
    marker.update(state="ok", source_unix=observed, source_updated_at=utc(observed), row_count=len(rows),
                  unknown_count=sum(r["state"] == "unknown" for r in rows), stale_count=sum(r["state"] == "stale" for r in rows))
    rows.append(marker)
    return {"schema_version": 1, "observed_unix": observed, "rows": rows, "commands": recorder.records}


def loki_payload(rows, now_ns):
    streams = {}
    for index, row in enumerate(rows):
        streams.setdefault(row["record_kind"], []).append([str(now_ns + index), json.dumps(row, separators=(",", ":"), allow_nan=False)])
    return {"streams": [{"stream": {"service_name": "agent-stack-native-data", "record_kind": kind}, "values": values} for kind, values in streams.items()]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    try:
        config = validate_config(strict_json(args.config.read_bytes()))
        state = private_dir(config["state_dir"])
        lock_fd = os.open(state / "collector.lock", os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(lock_fd, "wb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            observed = time.time()
            snapshot = collect(config, Recorder(state, config["command_timeout_seconds"]), observed)
            payload = json.dumps(loki_payload(snapshot["rows"], time.time_ns()), separators=(",", ":"), allow_nan=False).encode()
            snapshot["loki"] = {"requested": args.publish, "http_status": None, "payload_sha256": hashlib.sha256(payload).hexdigest(), "error": None}
            if args.publish:
                try:
                    status, response = request(config["loki_url"], payload)
                    snapshot["loki"]["http_status"] = status
                    snapshot["loki"]["response"] = write_private(state / "loki-response", response)
                    if status != 204:
                        snapshot["loki"]["error"] = "unexpected_http_status"
                except (OSError, ValueError) as exc:
                    snapshot["loki"]["error"] = type(exc).__name__
            bound = write_private(state / "snapshot.json", (json.dumps(snapshot, indent=2, allow_nan=False) + "\n").encode())
            marker = snapshot["rows"][-1]
            summary = {k: marker[k] for k in ("observed_unix", "row_count", "unknown_count", "stale_count")}
            summary.update(snapshot_sha256=bound["sha256"], snapshot_bytes=bound["bytes"],
                           loki_http_status=snapshot["loki"]["http_status"], publish_requested=args.publish,
                           publish_error=snapshot["loki"]["error"], payload_sha256=snapshot["loki"]["payload_sha256"])
            print(json.dumps(summary, separators=(",", ":")))
            return 1 if snapshot["loki"]["error"] else 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "state": "unknown"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
