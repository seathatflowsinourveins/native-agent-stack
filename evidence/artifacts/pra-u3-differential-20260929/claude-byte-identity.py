#!/usr/bin/env python3
"""Claude byte-identity check for PR-A U3 commit 9 (the kernel's rtkAgent option; design section 10 step 3, with the U3 review's
finding that the check must run with --rtk-check over named roots, or it never reaches the replay).

For each revision it extracts examples/claude-native/workflows with `git archive` into a scratch directory and runs
`node child-usage.mjs --lanes-sweep --root <root> --rtk-check` over a synthetic Claude root that this script writes: Bash calls
from the kernel's rtk control commands (tests/test_token_measurement.py), in an Agent-tool child, a workflow child and a main
transcript, with one PreToolUse:Bash rtk rewrite. It runs twice per revision: with a temporary HOME and the root as the
working directory (no Claude settings apply), and with the caller's HOME and the checkout as the working directory (its
.claude/settings.json and the home's apply). Only the exit codes, byte counts and sha256 digests are printed; the reports stay
under --work. Identical digests across revisions are the check.

Usage: python3 -B claude-byte-identity.py --repo <checkout> --work <scratch dir> BEFORE_REV AFTER_REV
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

COMMANDS = [  # tests/test_token_measurement.py rtk controls, exclusions, log/find, proxy, quoting and redirects
    "git status && gh pr view 1 | head -n 5", "gh pr view 1 | head -n 5", "git status && gh pr view 1",
    "git status && ls -la | wc -l", 'git status && printf "%s" "$(date)"', "rtk jq . a.json", "rtk git -C . show HEAD:a",
    "rtk git branch -a", "rtk diff a b", "rtk git log", "rtk find missing", "rtk cd .", "rtk proxy git show HEAD:a",
    "git status > output.txt", "gh pr view 1 --json title", "git status && rtk git status", "git status && printf 'a|b; c'",
    "git status | tail -f", "rtk head -c 5 file", 'rtk tail -n 5 "$FILE"', "rtk gh pr view 1 --json title",
    "rtk /usr/bin/git status", 'rtk grep -n "=>" f', 'rtk rg "Vec<String>" src', "rtk git status > out.txt",
    "git status 2>/dev/null", "rtk git log -3 && rtk find . -name x", "rtk proxy git diff --stat && rtk git status",
    "git log --oneline -5", "ls", "cat README.md | head -n 3", "cd repo && rtk proxy pytest -q"]


def transcript(prefix: str, commands: list, hour: int) -> list:
    rows = []
    for index, command in enumerate(commands):
        key = f"toolu_{prefix}_{index:02d}"
        at = f"2026-09-26T{hour:02d}:{index:02d}:00Z"
        rows.append({"type": "assistant", "timestamp": at, "message": {"id": f"msg_{prefix}_{index:02d}",
                     "model": "claude-opus-5-5", "content": [{"type": "tool_use", "id": key, "name": "Bash",
                     "input": {"command": command}}], "usage": {"input_tokens": 1, "output_tokens": 1}}})
        rows.append({"type": "user", "timestamp": at, "message": {"content": [
            {"type": "tool_result", "tool_use_id": key, "content": "ok", "is_error": False}]}})
    return rows


def write_root(root: Path) -> None:
    half = len(COMMANDS) // 2
    child = root / "proj" / "session-a" / "subagents"
    workflow = child / "workflows" / "wf_1"
    workflow.mkdir(parents=True)
    rows = transcript("a", COMMANDS[:half], 1)
    # One observed rewrite: a PreToolUse:Bash hook row from `rtk hook` whose stdout carries updatedInput (child-usage.mjs).
    rows.append({"type": "attachment", "timestamp": "2026-09-26T01:59:00Z", "attachment": {
        "type": "hook_success", "hookName": "PreToolUse:Bash", "command": "rtk hook claude", "toolUseID": "toolu_a_00",
        "stdout": json.dumps({"hookSpecificOutput": {"updatedInput": {"command": "rtk git status && gh pr view 1 | head -n 5"}}})}})
    (child / "agent-a1.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    (child / "agent-a1.meta.json").write_text(json.dumps({"agentType": "stack-researcher"}))
    (workflow / "agent-w1.jsonl").write_text("".join(json.dumps(row) + "\n" for row in transcript("w", COMMANDS[half:], 2)))
    (workflow / "agent-w1.meta.json").write_text(json.dumps({"agentType": "general-purpose"}))
    (root / "proj" / "session-b.jsonl").write_text("".join(json.dumps(row) + "\n" for row in transcript("m", COMMANDS[:4], 3)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("revs", nargs=2)
    args = parser.parse_args()
    work = args.work.resolve()
    root = work / "claude-root"
    if not root.exists():
        write_root(root)
    digests = {}
    for rev in args.revs:
        src = work / "src" / rev
        if not src.exists():
            src.mkdir(parents=True)
            archive = subprocess.run(["git", "-C", str(args.repo), "archive", rev, "examples/claude-native/workflows"],
                                     capture_output=True, check=True).stdout
            subprocess.run(["tar", "-x", "-C", str(src)], input=archive, check=True)
        module = src / "examples/claude-native/workflows/child-usage.mjs"
        with tempfile.TemporaryDirectory(dir=work) as home:
            for label, env, cwd in (("hermetic", {**os.environ, "HOME": home}, root),
                                    ("host", dict(os.environ), args.repo.resolve())):
                result = subprocess.run(["node", str(module), "--lanes-sweep", "--root", str(root), "--rtk-check"],
                                        capture_output=True, env=env, cwd=cwd, check=False)
                out = work / "out" / f"{rev}-{label}.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(result.stdout)
                digest = hashlib.sha256(result.stdout).hexdigest()
                replay = json.loads(result.stdout)["groups"]["all"]["measurement"]["rtk_parts"] if result.returncode == 0 else {}
                digests.setdefault(label, []).append(digest)
                print(f"{rev[:12]} {label} exit={result.returncode} bytes={len(result.stdout)} sha256={digest} "
                      f"rtk_parts.status={replay.get('status')} calls={replay.get('calls')} eligible_parts="
                      f"{replay.get('eligible_parts')} d7={'d7' in replay}")
    same = all(len(set(values)) == 1 for values in digests.values())
    print("IDENTICAL" if same else "DIFFERENT")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
