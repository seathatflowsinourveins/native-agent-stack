#!/usr/bin/env python3
"""Compare every pinned `uses:` SHA in .github/ with its comment tag and the latest release.

Read-only: `gh api` GET calls only, through gh's own native sign-in (no token is read here).
Output: one JSON document on stdout (rows + gh api call count)."""
import json, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(sys.argv[1])
calls = 0

def gh(path):
    global calls
    calls += 1
    r = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github+json", path],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return None
    return json.loads(r.stdout)

def tag_commit(repo, tag):
    ref = gh(f"repos/{repo}/git/ref/tags/{tag}")
    if not ref or "object" not in ref:
        return None
    obj = ref["object"]
    # Annotated tags point to a tag object; dereference to the commit.
    while obj["type"] == "tag":
        obj = gh(f"repos/{repo}/git/tags/{obj['sha']}")["object"]
    return obj["sha"]

pins = {}
for path in sorted((ROOT / ".github").rglob("*.yml")):
    for number, line in enumerate(path.read_text().splitlines(), 1):
        m = re.search(r"uses:\s*([\w.-]+/[\w.-]+)(/[\w./-]+)?@([0-9a-f]{40})\s*(?:#\s*(\S+))?", line)
        if m:
            owner_repo, sub, sha, comment = m.group(1), m.group(2) or "", m.group(3), m.group(4)
            key = (owner_repo + sub, sha, comment)
            pins.setdefault(key, []).append(f"{path.relative_to(ROOT)}:{number}")

rows = []
for (action, sha, comment), sites in sorted(pins.items()):
    repo = "/".join(action.split("/")[:2])
    latest = gh(f"repos/{repo}/releases/latest") or {}
    latest_tag = latest.get("tag_name")
    latest_sha = tag_commit(repo, latest_tag) if latest_tag else None
    comment_sha = tag_commit(repo, comment) if comment else None
    rows.append({
        "action": action, "pinned_sha": sha, "comment": comment,
        "comment_tag_commit": comment_sha,
        "comment_matches_pin": comment_sha == sha,
        "latest_release": latest_tag, "latest_published_at": latest.get("published_at"),
        "latest_commit": latest_sha, "pin_is_latest": latest_sha == sha,
        "uses_count": len(sites), "sites": sites,
    })

print(json.dumps({"checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "gh_api_calls": calls, "rows": rows}, indent=1))
