#!/usr/bin/env python3
"""Select a verified, nonempty Git history window for CI secret scanners.

The PR-range pattern follows us-equities-trading's ci.yml at
1e600094bdd3764a73cc7a1ea4ff85186fc7d6ac. That reference scopes PRs only;
this selector also bounds pushes and manual runs and refuses invalid windows.
Gitleaks v8.30.1 passes --log-opts to git log (sources/git.go at
83d9cd684c87d95d656c1458ef04895a7f1cbd8e). Never fall back to bare HEAD.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


SHA = re.compile(r"[0-9a-fA-F]{40}\Z")
MAIN_REF = "refs/remotes/origin/main"


class RangeError(ValueError):
    """The checkout and event cannot establish a bounded scan window."""


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        # Git diagnostics can contain host paths; report the operation, not its stderr.
        raise RangeError(f"Git {args[0]} failed; the scan range is unavailable")
    return result.stdout.strip()


def event_commit(value: object, field: str) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value) or not value.strip("0"):
        raise RangeError(f"{field} must be a nonzero, full commit SHA")
    value = value.lower()
    resolved = git("rev-parse", "--verify", f"{value}^{{commit}}")
    if resolved != value:
        raise RangeError(f"{field} does not resolve to the specified commit")
    return resolved


def ancestor(start: str, end: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", start, end],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode not in (0, 1):
        raise RangeError("Git could not verify the range's ancestry")
    return result.returncode == 0


def select_range(event_name: str, event: dict) -> tuple[str, str, str]:
    head = git("rev-parse", "--verify", "HEAD^{commit}")
    if not SHA.fullmatch(head):
        raise RangeError("The checkout does not have a full commit SHA")

    if event_name == "pull_request":
        pr = event.get("pull_request")
        if not isinstance(pr, dict):
            raise RangeError("The pull_request payload is missing")
        base = event_commit((pr.get("base") or {}).get("sha"), "pull_request.base.sha")
        pr_head = event_commit((pr.get("head") or {}).get("sha"), "pull_request.head.sha")
        if head == pr_head:
            # A head checkout can itself be a merge commit; classify it before parents.
            start = git("merge-base", base, head)
            reason = "pull-request-head-merge-base"
        else:
            parents = git("show", "--no-patch", "--format=%P", head).split()
            if len(parents) != 2 or parents[1] != pr_head:
                raise RangeError("HEAD is not the merge checkout of the payload's PR head")
            start = parents[0]
            # The payload base can move along the base line before checkout. Use the
            # actual merge's first parent, excluding base-only commits from this run.
            if not (ancestor(base, start) or ancestor(start, base)):
                raise RangeError("The PR payload base and merge base are on unrelated lines")
            reason = "pull-request-merge-first-parent"
    elif event_name == "push":
        after = event_commit(event.get("after"), "push.after")
        if after != head:
            raise RangeError("push.after does not match the checked-out HEAD")
        before = event.get("before")
        if not isinstance(before, str) or not SHA.fullmatch(before):
            raise RangeError("push.before must be a full commit SHA")
        if not before.strip("0"):
            # A new branch has no previous tip. Main is the only known baseline;
            # if it equals HEAD, no safe nonempty introduced range can be inferred.
            start = git("merge-base", MAIN_REF, head)
            reason = "new-branch-main-merge-base"
        else:
            before = event_commit(before, "push.before")
            if ancestor(before, head):
                start = before
                reason = "push-before"
            else:
                # Force pushes can diverge from before. The common ancestor covers
                # every newly reachable commit and may conservatively include more.
                start = git("merge-base", before, head)
                reason = "force-push-merge-base"
    elif event_name == "workflow_dispatch":
        start = git("merge-base", MAIN_REF, head)
        reason = "dispatch-main-merge-base"
        if start == head:
            # A manual run on main has no pushed range. Check its latest commit,
            # alongside the unchanged working-tree scan; a root commit fails closed.
            start = git("rev-parse", "--verify", "HEAD^1^{commit}")
            reason = "dispatch-latest-commit"
    else:
        # merge_group is not a trigger in this workflow. New event types require an
        # explicit range policy and tests instead of silently scanning full history.
        raise RangeError("Unsupported event: no secret-scan range policy")

    if not SHA.fullmatch(start) or not ancestor(start, head):
        raise RangeError("The scan start must be a commit ancestor of HEAD")
    if start == head or not git("rev-list", "--max-count=1", f"{start}..{head}"):
        raise RangeError("The scan range is empty; refusing to report success")
    return start, head, reason


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--event-path", required=True, type=Path)
    args = parser.parse_args()
    try:
        event = json.loads(args.event_path.read_text(encoding="utf-8"))
        if not isinstance(event, dict):
            raise RangeError("The event payload must be an object")
        start, end, reason = select_range(args.event_name, event)
    except (RangeError, OSError, ValueError, TypeError, AttributeError):
        # Do not echo payload contents, host paths, or raw subprocess diagnostics.
        print("::error::Cannot establish a nonempty CI secret-scan range; failing closed", file=sys.stderr)
        return 1
    print(f"start={start}\nend={end}\nrange={start}..{end}\nreason={reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
