#!/usr/bin/env python3
"""Select the verified event scope for CI secret scanners.

The PR-range pattern follows us-equities-trading's ci.yml at
1e600094bdd3764a73cc7a1ea4ff85186fc7d6ac. That reference scopes PRs only;
pushes and CI backstops follow the CC's 2026-10-10 vendor baseline ruling
(gitleaks/gitleaks-action src/gitleaks.js at bcfb9cce635345aac9996cedc19b2de8e01b894f).
Gitleaks v8.30.1 passes --log-opts to git log (sources/git.go at
83d9cd684c87d95d656c1458ef04895a7f1cbd8e). Full backstops require both
--ci-backstop and GITHUB_ACTIONS=true; local scans remain PR-range only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


SHA = re.compile(r"[0-9a-fA-F]{40}\Z")


class RangeError(ValueError):
    """The checkout and event cannot establish an allowed scan scope."""


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


def select_range(event_name: str, event: dict, *, ci_backstop: bool = False) -> dict[str, str]:
    head = git("rev-parse", "--verify", "HEAD^{commit}")
    if not SHA.fullmatch(head):
        raise RangeError("The checkout does not have a full commit SHA")
    start = ""
    mode = "range"

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
            # The vendor baseline checks only the tip when there is no prior tip.
            mode = "tip"
            reason = "new-branch-head-only"
        else:
            before = before.lower()
            before_object = subprocess.run(
                ["git", "cat-file", "-t", before], text=True,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
            )
            if before_object.returncode:
                # A force push can orphan the old tip, so a fresh checkout may not
                # contain it. Only GitHub's explicit boolean forced flag permits
                # this unavailable-commit fallback; malformed/ordinary pushes fail.
                if event.get("forced") is not True:
                    raise RangeError("push.before is unavailable without a forced push")
                mode = "tip"
                reason = "force-push-unavailable-before-head-only"
            else:
                if before_object.stdout.strip() != "commit":
                    raise RangeError("push.before must identify a commit object")
                before = event_commit(before, "push.before")
                if ancestor(before, head):
                    start = before
                    reason = "push-before"
                else:
                    # Rewritten history has no ordinary pushed range. Match the
                    # CC's vendor baseline with a head-only scan, not a merge-base.
                    mode = "tip"
                    reason = "force-push-head-only"
    elif event_name in ("workflow_dispatch", "schedule"):
        if not ci_backstop or os.environ.get("GITHUB_ACTIONS") != "true":
            raise RangeError("Full-history backstops require explicit CI authorization")
        mode = "full"
        reason = "dispatch-ci-full-history" if event_name == "workflow_dispatch" else "schedule-ci-full-history"
    else:
        # merge_group is not a trigger in this workflow. New event types require an
        # explicit scope policy and tests instead of silently scanning full history.
        raise RangeError("Unsupported event: no secret-scan range policy")

    if mode == "range":
        if not SHA.fullmatch(start) or not ancestor(start, head):
            raise RangeError("The scan start must be a commit ancestor of HEAD")
        if start == head or not git("rev-list", "--max-count=1", f"{start}..{head}"):
            raise RangeError("The scan range is empty; refusing to report success")
        scan_range = f"{start}..{head}"
        log_opts = f"--no-merges --first-parent {scan_range}" if event_name == "push" else scan_range
    else:
        scan_range = ""
        # CC 2026-10-10 amendment: the CI backstop scans only the checkout's ancestry.
        # Unrelated lane refs must not turn a scheduled/dispatch run red.
        log_opts = "-1" if mode == "tip" else "HEAD"
    return {"mode": mode, "log_opts": log_opts, "start": start, "end": head,
            "range": scan_range, "reason": reason}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--event-path", required=True, type=Path)
    parser.add_argument("--ci-backstop", action="store_true",
                        help="Allow a full-history backstop only when GITHUB_ACTIONS=true")
    args = parser.parse_args()
    try:
        event = json.loads(args.event_path.read_text(encoding="utf-8"))
        if not isinstance(event, dict):
            raise RangeError("The event payload must be an object")
        outputs = select_range(args.event_name, event, ci_backstop=args.ci_backstop)
    except (RangeError, OSError, ValueError, TypeError, AttributeError):
        # Do not echo payload contents, host paths, or raw subprocess diagnostics.
        print("::error::Cannot establish the authorized CI secret-scan scope; failing closed", file=sys.stderr)
        return 1
    for key, value in outputs.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
