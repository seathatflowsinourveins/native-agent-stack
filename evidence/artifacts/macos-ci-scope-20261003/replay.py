#!/usr/bin/env python3
"""Re-run the replay of docs/decisions/2026-10-03-macos-ci-scope.md from this receipt's inputs.

Usage, from anywhere in a clone that holds the verification base 6112d14d4:

    python3 evidence/artifacts/macos-ci-scope-20261003/replay.py [--root REPOSITORY]

Standard library only, offline, read-only. It reads MACOS_PATTERNS from the committed
.github/workflows/adoption-bootstrap.yml, so it measures the list that ships, and compares each number it recomputes
with the figure the record states and with the outputs the record's own replay saved (replay_r2.json, d1_rows.json,
runs30.json). It prints one line per comparison and exits 0 only when every comparison matches.

Method (the record's R): take every pull_request `validate-macos` check run in G (runs_graphql.json) that completed
with SUCCESS or FAILURE, and the file list of its head SHA (files_of.json: `git diff` against the merge base with
main); a head SHA without a file list counts as a full run. A pattern matches as a bash case glob does
(fnmatch.fnmatchcase: `*` also matches `/`). The changed-tests rule is the `changes` job's: a top-level
tests/test_*.py whose module name matches ^tests\\.test_[A-Za-z0-9_]+$ is a changed-tests module, and any other
tests/ path selects full mode. The file lists carry no deletion status, so no module is dropped as deleted here
(the job drops it). The changed-tests duration estimate is the record's: 0.5 min of setup plus the selected modules'
test counts (modcount.json, 0 for a module absent at the base) at 1,974 s / 9,849 tests each.

Not re-run here: the 5-slot simulation (sim_r2.json holds its saved outputs; its code was not retained, so the record's
simulated figures are only compared with sim_r2.json), the queue and time-to-result tables, and the classifications
(runs30.json holds both families' labels as recorded).
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import fnmatch
import json
from pathlib import Path
import re
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BASE = "6112d14d40f741855f0b961124d98939daaad00e"
MODULE = re.compile(r"^tests\.test_[A-Za-z0-9_]+$")
SECONDS_PER_TEST = 1974 / 9849


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def workflow_patterns(root):
    text = (root / ".github/workflows/adoption-bootstrap.yml").read_text(encoding="utf-8")
    block = re.search(r"(?ms)^[ \t]*MACOS_PATTERNS=\(\n(.*?)^[ \t]*\)[ \t]*$", text)
    if block is None:
        raise SystemExit("no MACOS_PATTERNS array in .github/workflows/adoption-bootstrap.yml")
    return re.findall(r"(?m)^[ \t]*'([^']*)'[ \t]*$", block.group(1))


def classify(files, patterns, changed_tests):
    """('full' | 'changed' | 'skip', changed-tests modules) for one change's file list."""
    if files is None:
        return "full", []
    mac = other = False
    modules = []
    for path in files:
        if any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns):
            mac = True
        if path.startswith("tests/"):
            rest = path[len("tests/"):]
            if "/" in rest:
                other = True
            elif fnmatch.fnmatchcase(rest, "test_*.py") and MODULE.match("tests." + rest[:-3]):
                modules.append("tests." + rest[:-3])
            else:
                other = True
    if mac:
        return "full", []
    if not changed_tests:
        return "skip", []
    if other:
        return "full", []
    return ("changed", modules) if modules else ("skip", [])


def hours(check):
    started = datetime.strptime(check["startedAt"], "%Y-%m-%dT%H:%M:%SZ")
    completed = datetime.strptime(check["completedAt"], "%Y-%m-%dT%H:%M:%SZ")
    return (completed - started).total_seconds() / 3600


class Report:
    def __init__(self):
        self.mismatches = 0

    def check(self, label, measured, expected):
        ok = measured == expected
        self.mismatches += not ok
        print(f"{'OK      ' if ok else 'MISMATCH'} {label}: measured {measured!r}, expected {expected!r}")

    def note(self, text):
        print(f"NOTE     {text}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--root", type=Path, default=HERE.parents[2], help="the repository root (default: this clone)")
    root = parser.parse_args().root.resolve()
    report = Report()

    lists = load("lists_r2.json")
    patterns = workflow_patterns(root)
    report.check("MACOS_PATTERNS entries in the workflow", len(patterns), 89)
    report.check("entries in only one of MACOS_PATTERNS and the record's list (lists_r2.json Bp)",
                 sorted(set(patterns) ^ set(lists["Bp"])), [])
    report.check("MACOS_PATTERNS has no duplicate", len(set(patterns)), len(patterns))

    listed = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", "--name-only", BASE],
                            capture_output=True, text=True)
    if listed.returncode != 0:
        raise SystemExit(f"the verification base {BASE} is not in this clone; fetch full history first")
    tracked = listed.stdout.splitlines()
    report.check("tracked files at 6112d14d4 that the list matches",
                 sum(any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns) for path in tracked), 151)
    report.check("patterns that match no tracked file at 6112d14d4",
                 [pattern for pattern in patterns if not any(fnmatch.fnmatchcase(path, pattern) for path in tracked)], [])

    candidates = {
        "B0": (lists["B0"], False),
        "Bp": (patterns, False),
        "Amac": (patterns + load("mac_tests_strict.json"), False),
        "Aall": (patterns + ["tests/*"], False),
        "B2": (patterns, True),
    }
    runs = load("runs_graphql.json")["runs"]
    files_of = load("files_of.json")
    test_counts = load("modcount.json")
    jobs = [(run, check) for run in runs if run["event"] == "pull_request"
            for check in run["checkSuite"]["checkRuns"]["nodes"]
            if check["name"] == "validate-macos" and check["status"] == "COMPLETED"
            and check["conclusion"] in ("SUCCESS", "FAILURE")]
    report.check("completed pull_request validate-macos jobs (SUCCESS or FAILURE)", len(jobs), 1069)
    report.check("their slot-hours", round(sum(hours(check) for _, check in jobs), 1), 348.8)
    report.check("head SHAs without a file list (counted as full runs)",
                 sum(run["checkSuite"]["commit"]["oid"] not in files_of for run, _ in jobs), 40)

    recorded = load("replay_r2.json")
    for name, (candidate, changed_tests) in candidates.items():
        modes = Counter()
        full_hours = 0.0
        durations = []
        for run, check in jobs:
            mode, modules = classify(files_of.get(run["checkSuite"]["commit"]["oid"]), candidate, changed_tests)
            modes[mode] += 1
            if mode == "full":
                full_hours += hours(check)
            elif mode == "changed":
                durations.append(0.5 + sum(test_counts.get(module, 0) for module in modules) * SECONDS_PER_TEST / 60)
        expected = recorded[name]
        report.check(f"{name}: full / skipped / changed-tests PR jobs", (modes["full"], modes["skip"], modes["changed"]),
                     (expected["full"], expected["skip"], expected["tests"]))
        slot_hours = full_hours + sum(durations) / 60
        report.check(f"{name}: PR slot-hours{' (with the changed-tests estimate)' if durations else ''}",
                     round(slot_hours, 1), expected["slot_h"])
        if durations:
            report.check(f"{name}: changed-tests job minutes, median and p90 (estimate)",
                         (round(statistics.median(durations), 2),
                          round(statistics.quantiles(durations, n=10, method="inclusive")[8], 2)),
                         (expected["tests_med"], expected["tests_p90"]))

    commit_of = {run["databaseId"]: run["checkSuite"]["commit"]["oid"] for run in runs}
    escapes, merged, disagreements = Counter(), Counter(), 0
    rows = load("d1_rows.json")
    for run_id, _, _, pulls, failing, _, _, flags in rows:
        for name, (candidate, changed_tests) in candidates.items():
            mode, modules = classify(files_of.get(commit_of.get(run_id)), candidate, changed_tests)
            caught = mode == "full" or (mode == "changed" and set(failing) & set(modules))
            disagreements += ("C" if caught else "-") != flags[name]
            if not caught:
                escapes[name] += 1
                merged[name] += any(state == "MERGED" for _, state in pulls)
    report.check("deterministic macOS-only PR failures (D1 rows)", len(rows), 18)
    report.check("D1 caught/escaped flags that differ from d1_rows.json", disagreements, 0)
    report.check("D1 escapes per candidate", {name: escapes[name] for name in candidates},
                 {"B0": 5, "Bp": 5, "Amac": 1, "Aall": 0, "B2": 0})
    report.check("D1 merged escapes per candidate", {name: merged[name] for name in candidates},
                 {"B0": 2, "Bp": 2, "Amac": 0, "Aall": 0, "B2": 0})

    differing = []
    failures = load("runs30.json")
    for row in failures:
        if row["ev"] != "pull_request":
            continue
        files = files_of.get(commit_of.get(row["run"]))
        bootstrap = row["B0"] == "bootstrap job"  # the failing job's identity, an input fact
        for name in ("B0", "Bp"):
            mode, _ = classify(files, *candidates[name])
            measured = "bootstrap job" if bootstrap else ("runs" if mode == "full" else "skipped")
            if measured != row[name]:
                differing.append((row["run"], name, measured, row[name]))
        mode, modules = classify(files, *candidates["B2"])
        if bootstrap:
            measured = f"bootstrap job (B+: {'runs' if mode == 'full' else 'skipped'})"
        elif mode == "full":
            measured = "runs"
        elif mode == "skip":
            measured = "skipped"
        else:
            selected = set(row["mods"]) & set(modules)
            measured = ("tests-only:caught" if selected == set(row["mods"]) and selected
                        else "tests-only:partial" if selected else "tests-only:missed")
        if measured != row["B2"]:
            differing.append((row["run"], "B2", measured, row["B2"]))
    report.check("macOS-only failures in the 30-run table", len(failures), 30)
    report.check("pull_request rows whose B0/Bp/B2 outcome differs from runs30.json", differing, [])
    report.check("both families' labels over the 25 classified runs",
                 (Counter(row["claude"] for row in failures if row["gpt"] != "-"),
                  Counter(row["gpt"] for row in failures if row["gpt"] != "-")),
                 (Counter({"test-portability-only": 12, "flaky-or-infra": 11, "mac-host-defect": 2}),
                  Counter({"test-portability-only": 10, "unknown": 8, "flaky-or-infra": 6, "mac-host-defect": 1})))

    commits = load("main_6112.json")
    report.check("first-parent main commits since 2026-09-25T00:00Z at 6112d14d4", len(commits), 369)
    expected_exposure = {"B0": (237, 95, 0), "Bp": (232, 90, 0), "Aall": (142, 0, 0), "B2": (142, 0, 90)}
    for name, expected in expected_exposure.items():
        modes = [classify(commit["files"], *candidates[name])[0] for commit in commits]
        skipped = [commit for commit, mode in zip(commits, modes) if mode == "skip"]
        touching = sum(any(fnmatch.fnmatchcase(path, "tests/*.py") for path in commit["files"]) for commit in skipped)
        report.check(f"{name}: main commits skipped / of those touching tests/*.py / run changed-tests",
                     (len(skipped), touching, modes.count("changed")), expected)

    def by_name(run):
        return {check["name"]: check for check in run["checkSuite"]["checkRuns"]["nodes"]}

    with_changes = [run for run in runs if run["event"] == "pull_request"
                    and (by_name(run).get("changes") or {}).get("conclusion") is not None]
    gated = sum((by_name(run).get("bootstrap-macos") or {}).get("conclusion") == "SKIPPED" for run in with_changes)
    report.check("pull_request runs with a changes result", len(with_changes), 1211)
    report.note(f"the bootstrap gate skipped bootstrap-macos on {gated} of them; the record's 52 counts skipped "
                "bootstrap-macos check runs across all events, one of them a workflow_dispatch run")

    # The record's simulated columns (§3.5 and §5) against the saved simulation output. The simulation code was not
    # retained, so this compares figures and re-runs nothing. (a-mac) and (b1) have no saved output.
    simulation = load("sim_r2.json")
    stated = (("D", "D", (579.7, 19.2)), ("B0", "B0", (358.5, 1.8)), ("B0 with B+", "B0+", (308.6, 0.9)),
              ("B′", "Bp", (363.8, 1.8)), ("B′ with B+", "B+", (315.7, 1.1)), ("(a-all)", "Aall", (446.8, 5.4)),
              ("(a-all) with B+", "Aall+", (419.1, 4.1)), ("(b2)", "B2", (367.7, 2.4)),
              ("(b2) with B+", "B2+", (339.9, 1.7)))
    for name, key, figures in stated:
        report.check(f"{name}: simulated total macOS slot-h and PR wait p90 min (sim_r2.json {key}, not re-run)",
                     (simulation[key]["slot_h"], simulation[key]["p90"]), figures)

    print(f"{'PASS' if report.mismatches == 0 else 'FAIL'}: {report.mismatches} mismatch(es)")
    return 0 if report.mismatches == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
