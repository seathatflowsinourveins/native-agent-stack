#!/usr/bin/env python3
"""Codex review gate for the CC landing scripts (corrections #122 and #123, 2026-10-09).

Prints one status line. Exit codes:
  0  the connector finished a review at or after the PR's latest review trigger, and no review is running;
  3  a review is running, or none has finished since the latest trigger (poll again);
  4  the latest review ended in a state other than Completed (a person decides);
  5  Codex is unavailable: since the latest trigger it posted a usage-limit or account notice, or showed no
     activity at all for NOSTART_MINUTES (the landing proceeds on its other reviews and logs this line).
     Measured 2026-10-09: the connector answered "You have reached your Codex usage limits" at 22:42:34Z (uet#51)
     and started nothing on nas#885 after its 22:44:17Z ready mark, while it starts within seconds when available
     (uet#47: 11 s; nas#939). A Running review is always waited for.

Sources (the connector's own summary comment, read on uet#47 and nas#939 on 2026-10-09):
  - the comment marked <!-- codex-pull-request-review-summary --> holds one table row per review,
    with status "Running since <time>" or "Completed <time>";
  - reviews start when a PR is opened for review, when a draft is marked ready, and on an
    "@codex review" or "@codex security review" comment;
  - the connector reacts +1 once all reviews finish with no findings, and comments when it has suggestions.
Why: uet#40 (correction #122) and uet#47 (correction #123) merged while a Codex review was running.

usage: codex_gate.py <owner/repo> <pr>
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timezone

BOT = "chatgpt-codex-connector[bot]"
NOSTART_MINUTES = 10
UNAVAILABLE = re.compile(r"reached your Codex usage limits|create a Codex account", re.I)
ROW = re.compile(r"\*\*(?P<status>[A-Za-z][A-Za-z ]*)\*\*[^|]*?datetime=\"(?P<time>[^\"]+)\"")
TRIGGER = re.compile(r"^\s*@codex (security )?review\b")


def gh(path):
    out = subprocess.run(["gh", "api", "--paginate", "--slurp", path],
                         capture_output=True, text=True, check=True).stdout
    pages = json.loads(out)
    return [item for page in pages for item in page]


def when(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def main(repo, pr):
    head = json.loads(subprocess.run(["gh", "api", f"repos/{repo}/pulls/{pr}"],
                                     capture_output=True, text=True, check=True).stdout)
    comments = gh(f"repos/{repo}/issues/{pr}/comments?per_page=100")
    timeline = gh(f"repos/{repo}/issues/{pr}/timeline?per_page=100")

    triggers = [when(head["created_at"])]
    triggers += [when(e["created_at"]) for e in timeline if e.get("event") == "ready_for_review"]
    triggers += [when(c["created_at"]) for c in comments
                 if c["user"]["login"] != BOT and TRIGGER.match(c.get("body") or "")]
    trigger = max(triggers)

    rows = []
    for c in comments:
        if c["user"]["login"] == BOT and "codex-pull-request-review-summary" in (c.get("body") or ""):
            rows += [(m["status"].strip(), when(m["time"])) for m in ROW.finditer(c["body"])]
    running = [t for s, t in rows if s.lower().startswith("running")]
    if running:
        print(f"Codex review running since {max(running):%Y-%m-%dT%H:%M:%SZ}")
        return 3
    done = [t for s, t in rows if s.lower().startswith("completed") and t >= trigger]
    # Without a summary row: a connector review, a +1 reaction or its no-findings comment after the trigger.
    done += [when(r["submitted_at"]) for r in gh(f"repos/{repo}/pulls/{pr}/reviews?per_page=100")
             if r["user"]["login"] == BOT and r.get("submitted_at") and when(r["submitted_at"]) >= trigger]
    done += [when(r["created_at"]) for r in gh(f"repos/{repo}/issues/{pr}/reactions?per_page=100")
             if r["user"]["login"] == BOT and r["content"] == "+1" and when(r["created_at"]) >= trigger]
    done += [when(c["created_at"]) for c in comments
             if c["user"]["login"] == BOT and "find any major issues" in (c.get("body") or "")
             and when(c["created_at"]) >= trigger]
    if done:
        print(f"Codex review finished at {max(done):%Y-%m-%dT%H:%M:%SZ} after the latest trigger "
              f"{trigger:%Y-%m-%dT%H:%M:%SZ}")
        return 0
    other = [(s, t) for s, t in rows if t >= trigger]
    if other:
        s, t = max(other, key=lambda x: x[1])
        print(f"Codex review ended '{s}' at {t:%Y-%m-%dT%H:%M:%SZ}; not Completed")
        return 4
    notices = [when(c["created_at"]) for c in comments
               if c["user"]["login"] == BOT and UNAVAILABLE.search(c.get("body") or "")
               and when(c["created_at"]) >= trigger]
    if notices:
        print(f"Codex unavailable: usage-limit or account notice at {max(notices):%Y-%m-%dT%H:%M:%SZ} "
              f"after the trigger {trigger:%Y-%m-%dT%H:%M:%SZ}; proceeding on the other reviews")
        return 5
    activity = [when(c["created_at"]) for c in comments if c["user"]["login"] == BOT and when(c["created_at"]) >= trigger]
    activity += [when(r["created_at"]) for r in gh(f"repos/{repo}/issues/{pr}/reactions?per_page=100")
                 if r["user"]["login"] == BOT and when(r["created_at"]) >= trigger]
    idle = (datetime.now(timezone.utc) - trigger).total_seconds() / 60
    if not activity and idle >= NOSTART_MINUTES:
        print(f"Codex unavailable: no connector activity in {idle:.0f} min since the trigger "
              f"{trigger:%Y-%m-%dT%H:%M:%SZ}; proceeding on the other reviews")
        return 5
    print(f"no Codex review finished since the latest trigger {trigger:%Y-%m-%dT%H:%M:%SZ}")
    return 3


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
