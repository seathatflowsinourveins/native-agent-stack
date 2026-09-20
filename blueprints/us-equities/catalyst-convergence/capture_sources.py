#!/usr/bin/env python3
"""Capture six frozen public documents with native Requests and bounded provenance.

Project adapter, not an upstream downloader command. No broker client or API key.
"""
import argparse
import importlib.metadata
import importlib.util
import inspect
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "alpaca-historical" / "collect.py"
SPEC = importlib.util.spec_from_file_location("capture_base", BASE)
B = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(B)
PLAN_SHA256 = "1324845825796e32b46d502884bf036e6b9211ca9976b7e9684dfda5b9b7f72b"
PUBLIC_IDENTITY = "native-agent-stack research (+https://github.com/seathatflowsinourveins/native-agent-stack)"


def native_session():
    if importlib.metadata.version("requests") != "2.34.2":
        raise ValueError("requests_version_mismatch")
    import requests
    session = requests.Session()
    session.trust_env = False
    session.mount("https://", requests.adapters.HTTPAdapter(max_retries=0))
    return session


def transport_identity():
    import requests.adapters
    import requests.models
    import requests.sessions
    sources = []
    for module in [requests.adapters, requests.models, requests.sessions]:
        raw = B.read(Path(inspect.getfile(module)))
        sources.append({"module": module.__name__, "bytes": len(raw), "sha256": B.sha(raw)})
    return {"library": "requests", "version": importlib.metadata.version("requests"),
            "sources": sources, "capture_code": B.digest("capture_sources.py", B.read(Path(__file__))),
            "shared_helper": B.digest("alpaca-historical/collect.py", B.read(BASE)),
            "environment_proxy_and_netrc": False, "automatic_retries": 0,
            "timeout_scope": "connect/read inactivity; not a whole-request wall deadline"}


def fetch(session, source, sec_identity):
    import requests
    url = source["url"]
    headers = {"User-Agent": sec_identity if urlsplit(url).hostname == "www.sec.gov" else PUBLIC_IDENTITY}
    started = B.now()
    body = bytearray()
    response = None
    status = None
    actual = None
    error = None
    complete = False
    try:
        response = session.get(url, headers=headers, stream=True, allow_redirects=False, timeout=(10, 30))
        status = response.status_code
        actual = {"method": response.request.method, "url": response.request.url}
        if actual != {"method": "GET", "url": url}:
            error = "prepared_request_scope_mismatch"
        else:
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                remaining = B.MAX_BODY - len(body)
                body.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    error = "body_limit_exceeded"
                    break
            else:
                complete = True
    except requests.RequestException as exc:
        error = type(exc).__name__
        request = getattr(exc, "request", None)
        if request is not None:
            actual = {"method": request.method, "url": request.url}
    finally:
        if response is not None:
            response.close()
    return {"source_id": source["source_id"], "url": url, "started_at": started,
            "observed_at": B.now(), "status": status, "body_complete": complete,
            "transport_error": error, "actual_request": actual}, bytes(body)


def capture(plan_path, out):
    raw_plan = B.read(plan_path)
    if B.sha(raw_plan) != PLAN_SHA256:
        raise ValueError("frozen_plan_hash_mismatch")
    plan = B.strict_json(raw_plan)
    sec_identity = os.environ.get("SEC_USER_AGENT", "").strip()
    if not sec_identity or "@" not in sec_identity or any(c in sec_identity for c in "\r\n"):
        raise ValueError("configured_sec_contact_required")
    out = B.safe_path(out)
    if any((parent / ".git").exists() for parent in [out, *out.parents]):
        raise ValueError("private_capture_inside_git_refused")
    out.mkdir(mode=0o700, parents=False, exist_ok=False)
    B.write_new(out / "plan.json", raw_plan)
    identity = transport_identity()
    frozen_at = B.now()
    B.write_new(out / "freeze.json", B.encode({"frozen_at": frozen_at, "plan_sha256": PLAN_SHA256,
                                               "transport": identity}))
    denied_origins = set()
    sources = []
    attempts = 0
    with native_session() as session:
        for source in plan["sources"]:
            origin = urlsplit(source["url"]).netloc
            if origin in denied_origins:
                stamp = B.now()
                entry = {"source_id": source["source_id"], "url": source["url"],
                         "started_at": stamp, "observed_at": stamp, "status": None,
                         "body_complete": False, "transport_error": "skipped_origin_access_refusal",
                         "actual_request": None}
                raw = b""
            else:
                attempts += 1
                entry, raw = fetch(session, source, sec_identity)
                if entry["status"] in {401, 403, 429}:
                    denied_origins.add(origin)
            name = source["source_id"] + ".body"
            B.write_new(out / name, raw)
            entry = entry | {"body": B.digest(name, raw)}
            meta_name = source["source_id"] + ".meta.json"
            meta_raw = B.encode(entry)
            B.write_new(out / meta_name, meta_raw)
            sources.append(entry | {"meta": B.digest(meta_name, meta_raw)})
    manifest = {"schema_version": 1, "kind": "lifecycle-source-capture-v1", "synthetic": False,
                "plan": B.digest("plan.json", raw_plan), "sources": sources,
                "freeze": B.digest("freeze.json", B.read(out / "freeze.json")),
                "transport": identity, "http_attempts": attempts}
    B.write_new(out / "manifest.json", B.encode(manifest))
    return {"manifest_sha256": B.sha(B.read(out / "manifest.json")), "http_attempts": attempts,
            "sources": [{k: row[k] for k in ["source_id", "status", "body_complete", "transport_error", "body"]}
                        for row in sources]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = capture(args.plan, args.out)
    print(json.dumps(result, sort_keys=True))
    return 0 if all(row["status"] == 200 and row["body_complete"] and row["transport_error"] is None
                    for row in result["sources"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
