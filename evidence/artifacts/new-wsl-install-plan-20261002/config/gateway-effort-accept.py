#!/usr/bin/env python3
"""Check one research session's delivered effort in native OmniRoute call logs.

Integration predicate, not an upstream test or model runner. Sources:
OmniRoute@c1e30b7676975feb298b49eff6ff58923c04b89e:
src/app/api/usage/call-logs/route.ts:233-277;
src/app/api/usage/call-logs/[id]/route.ts:5-17;
src/lib/usage/callLogs.ts:472-520,1067-1074;
open-sse/utils/providerRequestLogging.ts:269-284.
No credential store, request header or model content is printed or retained.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


BASE = "http://127.0.0.1:21128/api/usage/call-logs"


def delivered_efforts(rows, detail):
    """Require real successful calls and inspect the serialized provider body."""
    if not rows:
        raise ValueError("no call log matched the fresh research session")
    observed = set()
    for row in rows:
        if row.get("path", "").endswith("/embeddings"):
            raise ValueError("research session reached the embeddings route")
        if row.get("status") != 200:
            raise ValueError("research session contains an unsuccessful gateway call")
        alias = row.get("requestedModel") or row.get("model", "")
        if alias not in {"cx/gpt-6.1-sol", "cx/gpt-6.1-sol-high"}:
            raise ValueError("research session requested an unexpected model route")
        payloads = detail(row["id"]).get("pipelinePayloads") or {}
        wire = payloads.get("providerRequest") or {}
        if isinstance(wire, str):
            wire = json.loads(wire)
        wanted = "high" if alias.endswith("-high") else "xhigh"
        if wire.get("model") != "gpt-6.1-sol" or (wire.get("reasoning") or {}).get("effort") != wanted:
            raise ValueError("missing or mismatched delivered provider reasoning.effort")
        observed.add(wanted)
    return observed


def get_json(url):
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.load(response)


def main(session):
    rows = []
    # Page the native list without hydrating unrelated request bodies.
    for offset in range(0, 6400, 100):
        page = get_json(BASE + "?" + urllib.parse.urlencode({"limit": 100, "offset": offset}))
        if not isinstance(page, list):
            raise ValueError("native call-log list did not return an array")
        rows.extend(row for row in page if row.get("sessionTag") == session)
        if len(page) < 100:
            break
    else:
        raise ValueError("native call-log pagination limit reached")
    efforts = delivered_efforts(rows, lambda ident: get_json(BASE + "/" + urllib.parse.quote(ident, safe="")))
    print("Gateway delivered effort: " + ", ".join(sorted(efforts)))
    return 0


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or not sys.argv[1]:
            raise ValueError("one fresh research session tag is required")
        sys.exit(main(sys.argv[1]))
    except urllib.error.HTTPError as error:
        if error.code in {401, 403}:
            print("needs_user: native OmniRoute management observation needs its own sign-in; no credential is read here", file=sys.stderr)
            sys.exit(78)
        print("Gateway effort check: native log endpoint failed", file=sys.stderr)
        sys.exit(1)
    except (ValueError, KeyError, TypeError, OSError):
        print("Gateway effort check: fresh call log or delivered reasoning.effort is missing or mismatched", file=sys.stderr)
        sys.exit(1)
