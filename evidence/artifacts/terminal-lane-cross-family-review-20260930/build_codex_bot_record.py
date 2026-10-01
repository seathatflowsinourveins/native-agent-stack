#!/usr/bin/env python3
"""Build the sanitized record of the Codex review bot's read of the first push of pull request 572 (2026-10-01): the three threads as GitHub returned them (a private raw file saved with the GraphQL API: author, time, commit, path, line, body), how each was reproduced (the output of
`verify_codex_bot_findings.py` before the repairs, recorded/codex_bot_verification.txt, and after them, recorded/codex_bot_verification_after.txt) and what repaired it. Writes codex-bot-read.json next to this script. The sanitizer rules come from record_sanitizer.py, shared with the
other record builders. usage: build_codex_bot_record.py <raw threads json> [--out <directory>]"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import record_sanitizer  # noqa: E402  (the shared sanitizer rules; the private labels come from a private file)

raw = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["data"]["repository"]["pullRequest"]
out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else HERE
RULES = record_sanitizer.rules()
before = (HERE / "recorded/codex_bot_verification.txt").read_text(encoding="utf-8").splitlines()
after = (HERE / "recorded/codex_bot_verification_after.txt").read_text(encoding="utf-8").splitlines()

DISPOSITIONS = {
    "Close the final signal handoff window": {
        "id": "B1", "check": "R1", "lines": ("R1 alert", "R1 push"), "severity_of_the_coordinator": "medium",
        "repair": "`end_by_latched_signal` is the last safe point and the end of the latch's life: with the handled signals blocked it reads the latch; a latched signal ends the process BY it; with none latched every handler that is still the latch goes back to the default action "
                  "and the old mask returns, so a signal that is pending or lands later ends the process by its default action (a signal the parent ignored stays ignored). The handoff is run once, in `main`'s `finally` (the probe's `__main__` and the test drivers no longer repeat it), and the sweep covers the handoff and the output after it and requires death BY SIGTERM (it accepted exit status 143 too).",
        "checks": ["the sweep case (a SIGTERM at each line, now including `end_by_latched_signal` and `emit_report`)", "mutant: the snapshot of the latch is read without a block", "mutant: the latch is not handed back to the default action when nothing was latched",
                   "mutant: an ignored signal is handed to the default action too", "the nohup case at the end of the process"],
    },
    "Avoid flushing before honoring the latched signal": {
        "id": "B2", "check": "R2", "lines": ("R2 alert", "R2 push"), "severity_of_the_coordinator": "medium",
        "repair": "Nothing is written while the latch is installed: `measure` collects its result lines with `say`, `end_by_latched_signal` runs first in the `finally` of `main`, and `emit_report` prints after it, so a stuck stdout cannot hold a probe that has a signal to honor and a signal during the output takes its default action.",
        "checks": ["the flush case: the real `main`, in children without PYTHONUNBUFFERED, with a closed stdout and a latched signal, with a closed stdout and none (the exit status must stay 0), with a full pipe and a latched signal, with a full pipe and a signal sent once the child is seen blocked in its write, and with a blocked signal (each must die by SIGTERM, or exit 0, and leave no payload directory)",
                   "the static case: `measure` and `type_prompt` write nothing to stdout or stderr themselves", "mutant: the diagnostic is printed before the handoff", "mutant: a failed report leaves its bytes for the final flush", "mutant: the measurement writes a result line itself", "mutant: a flush comes back before the final kill"],
    },
    "Remove socket directories recorded during failed controls": {
        "id": "B3", "check": "R3", "lines": ("R3 bell", "R3 sync"), "severity_of_the_coordinator": "low",
        "repair": "The controls remove the directory of every recorded socket once its server is stopped (`remove_work_directory`: a direct child of /tmp that looks like the probe's own `mkdtemp` result, never the parent of an arbitrary path), compare the directories before and after, "
                  "and a scope control checks that an unrelated directory and one with the right prefix and another shape stay; a directory is removed only when its server is gone; `tmux_servers()` counts only the processes started with a socket in the probes' own directories.",
        "checks": ["the cleanup control and the shutdown-failure control (socket directories left behind 0)", "the scope control", "mutant: the socket directories of a failing control are not removed", "mutant: the removal is not scoped to this probe's own directories"],
    },
}


def clean(value):
    if isinstance(value, str):
        for pattern, replacement in RULES:
            value = pattern.sub(replacement, value)
        return value
    if isinstance(value, list):
        return [clean(item) for item in value]
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    return value


def pick(lines, prefixes):
    found = [line for line in lines if any(line.startswith(prefix) for prefix in prefixes)]
    assert len(found) == len(prefixes), (prefixes, found)
    return found


threads = raw["reviewThreads"]["nodes"]
assert len(threads) == 3, len(threads)
rows = []
for thread in threads:
    comment = thread["comments"]["nodes"][0]
    title = re.search(r"</sub></sub>\s+(.+?)\*\*", comment["body"]).group(1).strip()
    disposition = DISPOSITIONS[title]
    badge = re.search(r"badge/(P\d)-", comment["body"]).group(1)
    body = re.sub(r"\n\nAGENTS\.md reference:.*$", "", comment["body"], flags=re.S)
    body = body.split("</sub></sub>", 1)[1].strip()
    rows.append({
        "id": disposition["id"], "reviewer": comment["author"]["login"], "severity": badge, "title": title, "commit": comment["originalCommit"]["abbreviatedOid"], "path": thread["path"], "line": thread["line"] or thread["originalLine"], "posted": comment["createdAt"],
        "body": body[:3000], "resolved_when_read": thread["isResolved"], "reproduced_by": disposition["check"],
        "before_the_repairs": pick(before, disposition["lines"]), "after_the_repairs": pick(after, disposition["lines"]), "coordinator_severity": disposition["severity_of_the_coordinator"],
        "repair": disposition["repair"], "checks_that_fail_without_it": disposition["checks"],
    })
rows.sort(key=lambda row: row["id"])
record = clean({"read": {"reviewer": "chatgpt-codex-connector (GitHub's Codex review bot)", "pull_request": 572, "commit_read": rows[0]["commit"], "head_when_fetched": raw["headRefOid"][:8],
                         "threads": len(rows), "severities": {"P2": len(rows)}, "all_reproduced_by_execution": True, "verification_script": "verify_codex_bot_findings.py"}, "findings": rows})
target = out / "codex-bot-read.json"
target.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
record_sanitizer.assert_clean(target.read_text(encoding="utf-8"), target.name)
print(f"wrote {target.name}: {target.stat().st_size} bytes, {len(rows)} findings, severities {[row['severity'] for row in rows]}")
