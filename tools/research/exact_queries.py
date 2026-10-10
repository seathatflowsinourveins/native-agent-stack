"""Mechanical retention adapter for installed deedy5/ddgs 9.16.0.

Sources: deedy5/ddgs 9.16.0 installed ddgs/ddgs.py:135-272 and
ddgs/engines/duckduckgo.py:15-42, source hashes below. Native text() receives
each exact approved Q string; DDGS owns search, filtering, ranking and extract().
The demonstrated gap is that DeerFlow dispatch plans research with a model and
does not guarantee exact search strings or a zero-model-call capture phase.

This opt-in adapter follows the 2026-10-08 exact-query proposal against landed
618dd6c05ff6750705b52426261748d11e003477. It binds approved scope and retained
inputs/outputs; it implements no search engine, model, scoring or credential
runner. --execute is required at dispatch; validation performs no retrieval.
Search attempts and explicitly bounded top-k extract attempts are counted
separately; vendor HTTP fanout/retries and source publication dates are unknown.
Literal/credentialed nonpublic URL forms are refused for optional extraction;
DNS resolution and redirects remain unverified native vendor behavior.

DDGS 9.16.0 _search_sync raises DDGSException("No results found.") for native
empty results. That condition is recorded separately from transport exceptions,
without copying arbitrary exception text. A finished capture with any errors
retains exit 1 and status captured_with_errors after the parent verifies the
original-byte witness and all approved-query progress; interruption is incomplete.
"""

import argparse
import hashlib
import importlib.metadata
import ipaddress
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

DDGS_VERSION = "9.16.0"
DDGS_SOURCE_HASHES = {
    "ddgs/ddgs.py": "1cd33c4c5dd81ab865d6257327c4f079fae0cbe2e37ec8c7a9c575df771f27b1",
    "ddgs/engines/duckduckgo.py": "91ff4d7443e229cab28c25732df8e046f5730f8d21fe5ee22421d3536bdf71bb",
    "ddgs/http_client.py": "f47f9b973dcfd7ee195f34e95bd78f76b8b7a9bced0f14095c66a906a4f3c5de",
}


def utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def retained(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=".capture-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {"path": str(path), "sha256": sha(data), "bytes": len(data)}


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON keys are not permitted in approved query or scope input")
        value[key] = item
    return value


def validate(query_file, scope_file, scope_sha, query_sha=None):
    if not scope_file or not scope_sha or not re.fullmatch(r"[0-9a-f]{64}", scope_sha):
        raise ValueError("approved scope file and pinned SHA256 are required")
    scope_raw = scope_file.read_bytes()
    if sha(scope_raw) != scope_sha:
        raise ValueError("approved scope SHA256 mismatch")
    scope = json.loads(scope_raw, object_pairs_hook=unique_object)
    active = scope.get("active_fields") if isinstance(scope, dict) else None
    if not isinstance(active, list) or len(active) != 45:
        raise ValueError("approved scope must contain 45 unique layer IDs")
    approved = {}
    for row in active:
        if (not isinstance(row, dict) or not isinstance(row.get("layer_id"), str)
                or not row["layer_id"] or row.get("modality") not in {"repository", "skills"}
                or row["layer_id"] in approved):
            raise ValueError("approved scope must contain 45 unique IDs and explicit modalities")
        approved[row["layer_id"]] = row["modality"]
    raw = query_file.read_bytes()
    if query_sha is not None and (not re.fullmatch(r"[0-9a-f]{64}", query_sha) or sha(raw) != query_sha):
        raise ValueError("frozen query SHA256 mismatch; retrieval was not started")
    data = json.loads(raw, object_pairs_hook=unique_object)
    if (not isinstance(data, dict) or set(data) != {"schema_version", "fields"}
            or type(data["schema_version"]) is not int or data["schema_version"] != 1):
        raise ValueError("exact query envelope must use schema_version 1 and fields")
    rows = data["fields"]
    if not isinstance(rows, list) or len(rows) != 45:
        raise ValueError("require all 45 approved fields")
    ids = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"layer_id", "modality", "queries"}:
            raise ValueError("invalid field shape")
        if not isinstance(row["layer_id"], str) or row["layer_id"] not in approved:
            raise ValueError("unapproved layer ID")
        if row["modality"] != approved[row["layer_id"]]:
            raise ValueError("explicit approved repository/skills modality required")
        queries = row["queries"]
        if not isinstance(queries, list) or not 2 <= len(queries) <= 3:
            raise ValueError("require two or three exact query strings per field")
        if any(not isinstance(q, str) or not q.strip() or len(q.encode("utf-8")) > 4096 for q in queries):
            raise ValueError("query must be nonempty UTF-8 text within 4096 bytes")
        ids.append(row["layer_id"])
    if len(set(ids)) != 45 or set(ids) != set(approved):
        raise ValueError("duplicate or missing approved layer ID")
    return raw, rows, scope_raw


def public_url(url):
    if not isinstance(url, str):
        return False
    try:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or parts.username or parts.password or not parts.hostname:
            return False
        # Native transports can canonicalize encoded/non-ASCII host spellings
        # into nonpublic addresses. Refuse them rather than rewriting vendor URLs.
        if "%" in parts.hostname or "\\" in parts.hostname or not parts.hostname.isascii():
            return False
        hostname = parts.hostname.lower().rstrip(".")
        if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
            return False
        try:
            return ipaddress.ip_address(hostname).is_global
        except ValueError:
            try:
                # Native numeric parsing only, with no DNS lookup: URL clients
                # also recognize short/octal/hex IPv4 literals such as 127.1.
                return ipaddress.ip_address(socket.inet_aton(hostname)).is_global
            except OSError:
                return "." in hostname
    except ValueError:
        return False


def native_error_kind(error):
    error_type = type(error)
    if (error_type.__module__ == "ddgs.exceptions" and error_type.__name__ == "DDGSException"
            and error.args == ("No results found.",)):
        return "native_no_results"
    if ((error_type.__module__ == "ddgs.exceptions" and error_type.__name__ == "TimeoutException")
            or isinstance(error, TimeoutError)):
        return "native_timeout"
    return "retrieval_failure"


def capture(rows, directory, fetch_top_k, client_factory, manifest=None):
    # The worker owns this same mutable receipt throughout capture; interruption
    # cannot replace observed progress with a newly initialized zero-count receipt.
    if manifest is None:
        manifest = {}
    manifest.update(schema_version=1, status="capturing", started_at_utc=utc(), search_calls=0,
                    fetch_calls=0, error_count=0, empty_query_count=0, completed_query_count=0,
                    queries=[], provider_model_calls=0, network_request_count=None,
                    inflight_operation=None, published_month_validation="pending_primary_review",
                    counter_boundary="Logical attempts started; vendor HTTP request counts are unknown.")
    for field_order, row in enumerate(rows):
        for query_order, query in enumerate(row["queries"]):
            slug = f"{field_order:02d}-{query_order:02d}"
            record = {"layer_id": row["layer_id"], "modality": row["modality"], "query": query,
                      "query_sha256": sha(query.encode("utf-8")), "field_order": field_order,
                      "query_order": query_order, "started_at_utc": utc(), "sources": [], "status": "in_flight"}

            def checkpoint():
                artifact = retained(directory / f"{slug}-search.json", record)
                if len(manifest["queries"]) == query_index:
                    manifest["queries"].append(artifact)
                else:
                    manifest["queries"][query_index] = artifact
                retained(directory / "progress.json", manifest)

            query_index = len(manifest["queries"])
            manifest["search_calls"] += 1
            manifest["inflight_operation"] = {"kind": "search", "field_order": field_order,
                                               "query_order": query_order, "query_sha256": record["query_sha256"],
                                               "outcome": "pending"}
            checkpoint()
            try:
                client = client_factory(timeout=15)
                results = client.text(query, region="wt-wt", safesearch="moderate",
                                      max_results=5, page=1, backend="duckduckgo")
                record["raw_vendor_results"] = results
                if not isinstance(results, list) or any(not isinstance(hit, dict) for hit in results):
                    raise ValueError("native DDGS returned an unsupported result shape")
                record["status"] = "returned" if results else "empty"
                manifest["inflight_operation"] = None
                if not results:
                    manifest["empty_query_count"] += 1
                # Preserve every returned hit and its native rank, even if a
                # vendor response exceeds max_results. Only fetching uses top-k.
                record["sources"] = [
                    {"vendor_result_rank": rank, "url": hit.get("href") or hit.get("url") or hit.get("link"),
                     "status": "retained_not_fetched"}
                    for rank, hit in enumerate(results, 1)
                ]
                checkpoint()  # Retain all returned hits before optional fetching.
                for source in record["sources"]:
                    rank, url = source["vendor_result_rank"], source["url"]
                    if rank <= fetch_top_k and public_url(url):
                        manifest["fetch_calls"] += 1
                        source["started_at_utc"] = utc()
                        source["status"] = "in_flight"
                        manifest["inflight_operation"] = {"kind": "fetch", "field_order": field_order,
                                                           "query_order": query_order, "vendor_result_rank": rank,
                                                           "url": url, "outcome": "pending"}
                        checkpoint()
                        try:
                            value = client.extract(url, fmt="text")
                            source.update(status="captured", raw=retained(directory / f"{slug}-source-{rank:02d}.json", value))
                        except Exception as error:
                            source.update(status="failed", error_type=type(error).__name__, error_kind=native_error_kind(error))
                            manifest["error_count"] += 1
                        source["ended_at_utc"] = utc()
                        manifest["inflight_operation"] = None
                        checkpoint()
                    elif rank <= fetch_top_k:
                        source["status"] = "refused_nonpublic_url_form"
            except Exception as error:
                kind = native_error_kind(error)
                record.update(status="empty_native_exception" if kind == "native_no_results" else "failed",
                              error_type=type(error).__name__, error_kind=kind)
                if kind == "native_no_results":
                    manifest["empty_query_count"] += 1
                manifest["error_count"] += 1
            manifest["inflight_operation"] = None
            record["ended_at_utc"] = utc()
            manifest["completed_query_count"] += 1
            checkpoint()
    manifest["ended_at_utc"] = utc()
    retained(directory / "manifest.json", manifest)
    return manifest


def native_ddgs():
    """Check the installed version/source before using the supported vendor API."""
    distribution = importlib.metadata.distribution("ddgs")
    if distribution.version != DDGS_VERSION:
        raise ValueError("DDGS version changed; reverify native source before retrieval")
    sources = {}
    for relative, expected in DDGS_SOURCE_HASHES.items():
        path = Path(distribution.locate_file(relative))
        raw = path.read_bytes()
        sources[relative] = {"path": str(path), "bytes": len(raw), "sha256": sha(raw)}
        if sha(raw) != expected:
            raise ValueError("DDGS native source changed; reverify before retrieval")
    from ddgs import DDGS
    from ddgs.engines import ENGINES
    if "duckduckgo" not in ENGINES.get("text", {}):
        raise ValueError("Fixed DDGS duckduckgo backend unavailable; no fallback is allowed")
    return DDGS, {"distribution": "ddgs", "version": distribution.version,
                  "repository": "https://github.com/deedy5/ddgs", "sources": sources}


def dispatch_exact(args, file_record, utc_now, native_session_tools, run_producer):
    os.umask(0o077)
    root = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "native-agent-stack/research/dispatch"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory = Path(tempfile.mkdtemp(prefix="run.", dir=root)).resolve()
    receipt = {"schema_version": 1, "status": "failed", "started_at_utc": utc_now(),
               "mode": "exact_queries_ddgs", "provider_model_calls": 0,
               "evidence_boundary": "Mechanical DDGS capture only; no cited-answer, landscape workflow, usage or adoption verdict."}
    code = 1
    try:
        raw, rows, scope_raw = validate(args.exact_queries_file, args.approved_scope_file, args.approved_scope_sha256)
        expected_query_sha, expected_query_bytes = sha(raw), len(raw)
        receipt["queries"] = {"path": str(args.exact_queries_file), "sha256": expected_query_sha, "bytes": expected_query_bytes}
        receipt["approved_scope"] = {"path": str(args.approved_scope_file), "sha256": sha(scope_raw), "bytes": len(scope_raw)}
        frozen = directory / "frozen-queries.json"
        frozen.write_bytes(raw)
        frozen_scope = directory / "frozen-scope.json"
        frozen_scope.write_bytes(scope_raw)
        receipt["frozen_queries"] = file_record(frozen)
        if (receipt["frozen_queries"].get("sha256") != expected_query_sha
                or receipt["frozen_queries"].get("bytes") != expected_query_bytes):
            raise ValueError("Frozen query bytes changed after validation; retrieval was not started")
        receipt["frozen_scope"] = file_record(frozen_scope)
        receipt["logical_search_bound"] = sum(len(row["queries"]) for row in rows)
        receipt["source_fetch_bound"] = receipt["logical_search_bound"] * args.fetch_top_k
        command = ["hcom", "list", "self", "--json"]
        if args.name:
            command.extend(["--name", args.name])
        receipt["hcom_command"] = command
        with (directory / "hcom.stdout").open("wb") as out, (directory / "hcom.stderr").open("wb") as err:
            identity_result = subprocess.run(command, stdout=out, stderr=err, timeout=30)
        receipt["hcom_exit_code"] = identity_result.returncode
        if identity_result.returncode:
            raise ValueError("native caller resolution failed; retrieval was not started")
        identity = json.loads((directory / "hcom.stdout").read_text(encoding="utf-8"))
        if not isinstance(identity, dict) or not identity.get("name") or not identity.get("session_id"):
            raise ValueError("native caller resolution failed; retrieval was not started")
        receipt["hcom_identity"] = {key: identity.get(key) for key in ("name", "session_id", "tool")}
        if args.execute:
            if not args.mechanical_python or not args.mechanical_python.is_absolute():
                raise ValueError("explicit absolute installed DDGS Python is required")
            tools, tool_records = native_session_tools()
            receipt["cancellation_prerequisites"] = tool_records
            helper = Path(__file__).resolve()
            receipt["adapter"] = file_record(helper)
            receipt["runtime"] = file_record(args.mechanical_python)
            command = [str(args.mechanical_python), str(helper), "--worker-file", str(frozen),
                       "--query-sha256", expected_query_sha,
                       "--scope-file", str(frozen_scope), "--scope-sha256", args.approved_scope_sha256,
                       "--out", str(directory), "--fetch-top-k", str(args.fetch_top_k)]
            # This mechanical worker inherits no native accounts, provider keys,
            # proxy variables or client config. The ordinary producer's env is unchanged.
            worker_env = {"PATH": os.defpath, "PYTHONNOUSERSITE": "1", "PYTHONUNBUFFERED": "1"}
            exit_code, interrupted, cancellation = run_producer(None, None, directory, tools, command=command, env=worker_env)
            receipt.update(native_exit_code=exit_code, interrupted_by_signal=interrupted, cancellation=cancellation)
            manifest = None
            if (directory / "manifest.json").is_file():
                receipt["manifest"] = file_record(directory / "manifest.json")
                manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
                if not isinstance(manifest, dict):
                    raise ValueError("Mechanical worker manifest is not an object")
            if (directory / "progress.json").is_file():
                receipt["progress"] = file_record(directory / "progress.json")
            if (interrupted or (isinstance(exit_code, int) and exit_code < 0)
                    or manifest is not None and manifest.get("status") == "interrupted"):
                receipt["failure_kind"] = "cancelled_or_terminated"
                receipt["interruption_boundary"] = (
                    "Worker did not complete; retained progress counts started attempts. "
                    "In-flight result and uncheckpointed completion are unknown."
                )
                if interrupted:
                    code = 128 + interrupted
                elif isinstance(exit_code, int) and exit_code < 0:
                    code = 128 - exit_code
                else:
                    code = exit_code if isinstance(exit_code, int) and exit_code > 0 else 1
                raise ValueError("Mechanical capture cancelled or terminated; owned evidence retained")
            if manifest is None or manifest.get("status") not in {"captured", "captured_with_errors"}:
                receipt["failure_kind"] = "incomplete_capture"
                code = exit_code if isinstance(exit_code, int) and exit_code > 0 else 1
                raise ValueError("Mechanical worker did not finish capture; incomplete evidence retained")
            parsed_queries = manifest.get("parsed_queries")
            if (not isinstance(parsed_queries, dict)
                    or parsed_queries.get("sha256") != expected_query_sha
                    or parsed_queries.get("bytes") != expected_query_bytes):
                raise ValueError("Worker parsed-query witness does not match the frozen query bytes")
            receipt["worker_parsed_queries"] = parsed_queries
            bound = receipt["logical_search_bound"]
            if (type(manifest.get("search_calls")) is not int or manifest["search_calls"] != bound
                    or type(manifest.get("completed_query_count")) is not int or manifest["completed_query_count"] != bound
                    or not isinstance(manifest.get("queries"), list) or len(manifest["queries"]) != bound
                    or type(manifest.get("error_count")) is not int or manifest["error_count"] < 0):
                raise ValueError("Worker completed-capture counts do not match all approved logical queries")
            expected_code = 1 if manifest["error_count"] else 0
            expected_status = "captured_with_errors" if manifest["error_count"] else "captured"
            if exit_code != expected_code or manifest["status"] != expected_status:
                raise ValueError("Worker exit code disagrees with completed-capture error verdict")
            receipt["capture_counts"] = {key: manifest.get(key) for key in (
                "search_calls", "fetch_calls", "completed_query_count", "error_count", "empty_query_count",
            )}
            receipt["capture_outcome"] = "all_logical_queries_finished"
            receipt["status"] = expected_status
            code = expected_code
        else:
            receipt["status"] = "validated_no_network"
            code = 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        receipt.update(error_type=type(error).__name__, error=str(error))
    finally:
        for filename in ("producer.stdout", "producer.stderr", "hcom.stdout", "hcom.stderr"):
            if (directory / filename).exists():
                receipt[filename] = file_record(directory / filename)
        receipt["finished_at_utc"] = utc_now()
        retained(directory / "dispatch.json", receipt)
    print(directory / "dispatch.json")
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-file", required=True, type=Path)
    parser.add_argument("--query-sha256", required=True)
    parser.add_argument("--scope-file", required=True, type=Path)
    parser.add_argument("--scope-sha256", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--fetch-top-k", type=int, choices=range(6), default=0)
    args = parser.parse_args(argv)
    os.umask(0o077)
    receipt = {"schema_version": 1, "status": "failed", "provider_model_calls": 0,
               "started_at_utc": utc(), "search_calls": 0, "fetch_calls": 0}
    previous = {}

    def interrupted(signum, _frame):
        raise KeyboardInterrupt(signum)

    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, interrupted)
        raw, rows, _ = validate(args.worker_file, args.scope_file, args.scope_sha256, args.query_sha256)
        receipt["parsed_queries"] = {"path": str(args.worker_file), "sha256": sha(raw), "bytes": len(raw)}
        client, source_record = native_ddgs()
        retained(args.out / "native-ddgs.json", source_record)
        receipt["native_ddgs"] = source_record
        capture(rows, args.out, args.fetch_top_k, client, receipt)
        receipt["status"] = "captured_with_errors" if receipt["error_count"] else "captured"
    except KeyboardInterrupt as error:
        for signum in previous:
            signal.signal(signum, signal.SIG_IGN)
        receipt.update(status="interrupted", error_type="KeyboardInterrupt",
                       interruption_boundary="Started-attempt counters are retained; in-flight outcome and uncheckpointed completion are unknown.")
        if receipt.get("inflight_operation"):
            receipt["inflight_operation"]["outcome"] = "unknown"
        if error.args and error.args[0] in (signal.SIGINT, signal.SIGTERM):
            receipt["interrupted_by_signal"] = error.args[0]
    except (OSError, ValueError, TypeError, KeyError, importlib.metadata.PackageNotFoundError) as error:
        receipt.update(status="failed", error_type=type(error).__name__)
        if receipt.get("inflight_operation"):
            receipt["inflight_operation"]["outcome"] = "unknown"
    finally:
        receipt["ended_at_utc"] = utc()
        try:
            retained(args.out / "manifest.json", receipt)
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)
    if receipt["status"] == "interrupted":
        return 128 + receipt.get("interrupted_by_signal", signal.SIGINT)
    return 0 if receipt["status"] == "captured" else 1


if __name__ == "__main__":
    raise SystemExit(main())
