#!/usr/bin/env python3
"""Observe fresh research calls using default OmniRoute metadata, without bodies.

Integration predicate, not an upstream test or model runner. Sources:
OmniRoute@c1e30b7676975feb298b49eff6ff58923c04b89e:
open-sse/handlers/chatCore.ts:1087-1090,1133;
open-sse/services/conversationTracker.ts:462-468;
src/app/api/usage/call-logs/route.ts:218-225,233-277;
src/lib/usage/callLogs.ts:472-520,650-668,1036;
src/lib/db/migrations/014_unified_log_artifacts.sql:7-10.

The default list exposes session, timestamp, status and model, but no delivered
reasoning effort. Conditional encrypted-reasoning effort columns in the DB are
not exposed by this API either. We assert logged model routes and success,
report source-based expected effort, and never claim delivered wire effort.
Pipeline capture remains an operator decision because it retains prompts and
completions. No detail/body endpoint or credential store is accessed. Only the
listed metadata fields are inspected; native summary responses stay transient
and are never written or printed.
"""
import datetime
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


BASE = "http://127.0.0.1:21128/api/usage/call-logs"
# OmniRoute@c1e30b76: registry/codex/index.ts:9-13; services/model.ts:484-490.
# Composed upstream@0585aba5589d5a1f49243a13a8db249558e7c9e3:
# open-sse/config/providers/registry/codex/index.ts:73;
# open-sse/executors/codex/reasoningSuffix.ts:11-18,35-50.
# Canonical plan topology: pool_fallback.model=cx/gpt-6.1-sol-max.
# Accept only the documented provider ID/alias and these exact model suffixes.
ROUTES = {"cx/gpt-6.1-sol": "xhigh", "cx/gpt-6.1-sol-high": "high",
          "cx/gpt-6.1-sol-max": "max",
          "codex/gpt-6.1-sol": "xhigh", "codex/gpt-6.1-sol-high": "high",
          "codex/gpt-6.1-sol-max": "max"}
MODELS = {route.split("/", 1)[1] for route in ROUTES}


def observed_routes(rows):
    """Validate only fields present in default native call-list summaries."""
    if not rows:
        raise ValueError("no call log matched the fresh research run")
    observed = set()
    for row in rows:
        if row.get("path", "").endswith("/embeddings"):
            raise ValueError("selected research calls reached the embeddings route")
        if row.get("path") not in {"/v1/chat/completions", "/v1/responses"}:
            raise ValueError("research call used an unexpected inference endpoint")
        if row.get("status") != 200 or row.get("active"):
            raise ValueError("research run contains an unsuccessful or unfinished gateway call")
        alias = row.get("requestedModel")
        if (row.get("model") not in MODELS
                or (alias and (alias not in ROUTES or alias.split("/", 1)[1] != row["model"]))
                or (row.get("provider") and row["provider"] != "codex")):
            raise ValueError("research run used an unexpected model route")
        if alias:
            observed.add(alias)
    return observed


def get_json(url):
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.load(response)


def instant(value):
    parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("run timestamps must include a timezone")
    return parsed


def run_rows(session, started_at, finished_at):
    start, end = instant(started_at), instant(finished_at)
    if not session or start > end:
        raise ValueError("a session and an ordered run window are required")
    fresh, offset = {}, 0
    while True:
        page = get_json(BASE + "?" + urllib.parse.urlencode({"limit": 100, "offset": offset}))
        if not isinstance(page, list):
            raise ValueError("native call-log list did not return an array")
        old_persisted, persisted_count = False, 0
        for row in page:
            # The API prepends active/recent in-memory rows on every page.
            # Only persisted rows are ordered by descending DB timestamp.
            persisted = not row.get("active") and not row.get("completed")
            timestamp = instant(row["timestamp"])
            if persisted:
                persisted_count += 1
                old_persisted |= timestamp < start
            if start <= timestamp <= end and not row.get("active"):
                fresh[row["id"]] = row
        if old_persisted or persisted_count < 100:
            break
        offset += 100
    joined = [row for row in fresh.values() if row.get("sessionTag") == session]
    if joined:
        return joined, "session"
    # In-memory summaries omit sessionTag and requestedModel. This fallback
    # observes model calls within the run window; concurrent traffic can match,
    # so it cannot prove attribution or whole-run zero embeddings.
    return [row for row in fresh.values()
            if (row.get("requestedModel") or row.get("model")) in ROUTES
            or (not row.get("requestedModel") and row.get("model") in MODELS)], "time-window-plus-model"


def main(session, started_at, finished_at):
    rows, join = run_rows(session, started_at, finished_at)
    routes = observed_routes(rows)
    print("Gateway metadata: successful Sol-route calls; join=" + join)
    if routes:
        print("Source-based expected effort (not observed wire): " + ", ".join(sorted({ROUTES[route] for route in routes})))
    print("Delivered wire effort is not asserted; pipeline capture was not requested.")
    if join != "session":
        print("Window/model join cannot exclude concurrent traffic or certify whole-run zero embeddings.")
    return 0


if __name__ == "__main__":
    try:
        if len(sys.argv) != 4:
            raise ValueError("fresh session, run start and run end are required")
        sys.exit(main(*sys.argv[1:]))
    except urllib.error.HTTPError as error:
        if error.code in {401, 403}:
            print("needs_user: native OmniRoute management observation needs its own sign-in; no credential is read here", file=sys.stderr)
            sys.exit(78)
        print("Gateway metadata check: native log endpoint failed", file=sys.stderr)
        sys.exit(1)
    except (ValueError, KeyError, TypeError, AttributeError, OSError):
        print("Gateway metadata check: fresh successful model calls are missing or mismatched", file=sys.stderr)
        sys.exit(1)
