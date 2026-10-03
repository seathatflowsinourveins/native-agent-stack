#!/usr/bin/env python3
"""Regenerate fixtures/ from real runs of the controls (stdlib only; local, never in CI).

  python3 make_fixtures.py --parallel-python VENV/bin/python --work SCRATCH_DIR

VENV holds unittest-parallel 1.8.6 and coverage 7.16.2, installed with
--only-binary=:all: --require-hashes (README.md, "Fixtures"); its interpreter runs
every configuration, so S and the parallel arms share one Python. Each control file
is copied alone into a fresh directory under SCRATCH_DIR and the arm's exact command
runs there with stdout and stderr in one file, as the trial workflow runs it. Logs
are sanitized (run directory, virtualenv, interpreter and home prefixes become
placeholders) and written to fixtures/real/, the mutated copies to fixtures/mutated/,
and their provenance to fixtures/index.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
CONTROL = HERE / "controls" / "test_zz_trial_controls.py"
CRASH = HERE / "controls" / "crash_control" / "test_crash.py"
CONFIGS = {
    "S": ["-m", "unittest", "-v"],
    "P3": ["-m", "unittest_parallel", "-j", "3", "--level", "module", "-v"],
    "P3F": ["-m", "unittest_parallel", "-j", "3", "--level", "module", "--disable-process-pooling", "-v"],
    "P3C": ["-m", "unittest_parallel", "-j", "3", "--level", "class", "-v"],
    "P4": ["-m", "unittest_parallel", "-j", "4", "--level", "module", "-v"],
    "L4F": ["-m", "unittest_parallel", "-j", "4", "--level", "module", "--disable-process-pooling", "-v"],
    "L4C": ["-m", "unittest_parallel", "-j", "4", "--level", "class", "-v"],
}
REPEATS = {"S": 3, "P3": 3, "P3C": 3}
PRIVATE = (re.compile(r"/(?:home|Users)/[A-Za-z0-9_.-]+"),
           re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I))
PASS_LINE = "test_pass (test_zz_trial_controls.TrialControlsA.test_pass) ... ok"
# Each mutated copy is its source with these operations applied (apply_mutation); test_compare.py
# re-applies them and requires the stored copy to equal the result.
MUTATIONS = [
    {"file": "mutated/dropped-line-parallel.log", "source": "real/controls-P3C-r1.log",
     "ops": [{"op": "drop_line", "line": PASS_LINE}],
     "why": "a dropped result line: the started test has no result"},
    {"file": "mutated/dropped-line-serial.log", "source": "real/controls-S-r1.log",
     "ops": [{"op": "drop_line", "line": PASS_LINE}],
     "why": "a dropped serial line: one started test fewer than Ran N"},
    {"file": "mutated/changed-outcome.log", "source": "real/controls-P3-r1.log",
     "ops": [{"op": "replace_line", "old": PASS_LINE,
              "new": "test_pass (test_zz_trial_controls.TrialControlsA.test_pass) ... skipped 'mutated'"},
             {"op": "replace_suffix", "old": "skipped=1, expected failures=1, unexpected successes=1)",
              "new": "skipped=2, expected failures=1, unexpected successes=1)"}],
     "why": "a self-consistent changed outcome: the log parses, but test_pass differs from S"},
    {"file": "mutated/changed-outcome-unbalanced.log", "source": "real/controls-P3-r1.log",
     "ops": [{"op": "replace_line", "old": PASS_LINE,
              "new": "test_pass (test_zz_trial_controls.TrialControlsA.test_pass) ... skipped 'mutated'"}],
     "why": "a changed outcome the status line does not count"},
    {"file": "mutated/truncated.log", "source": "real/controls-S-r1.log",
     "ops": [{"op": "keep_first_lines", "count": 6}],
     "why": "a truncated log: no summary"},
    {"file": "mutated/missing-ran-line.log", "source": "real/controls-P3-r1.log",
     "ops": [{"op": "drop_matching", "pattern": r"^Ran \d+ tests? in \d+\.\d{3}s$"}],
     "why": "the Ran line alone removed"},
    {"file": "mutated/extra-id.log", "source": "real/controls-P3-r1.log",
     "ops": [{"op": "insert_after", "line": PASS_LINE,
              "lines": ["test_extra (test_zz_trial_controls.TrialControlsA.test_extra) ...",
                        "test_extra (test_zz_trial_controls.TrialControlsA.test_extra) ... ok"]},
             {"op": "replace_matching", "pattern": r"^Ran 8 tests in ", "new": "Ran 9 tests in "},
             {"op": "replace_matching", "pattern": r"\(9 total tests\)", "new": "(10 total tests)"}],
     "why": "a self-consistent extra id outside the inventory"},
]


def apply_mutation(text: str, ops: list) -> str:
    """Apply the declared operations; each must change the text, else it raises ValueError."""
    lines = text.split("\n")
    for op in ops:
        before = list(lines)
        kind = op["op"]
        if kind == "drop_line":
            index = lines.index(op["line"])
            del lines[index]
        elif kind == "replace_line":
            lines[lines.index(op["old"])] = op["new"]
        elif kind == "replace_suffix":
            hits = [i for i, line in enumerate(lines) if line.endswith(op["old"])]
            if len(hits) != 1:
                raise ValueError(f"{op}: {len(hits)} lines end with the text")
            lines[hits[0]] = lines[hits[0]][: -len(op["old"])] + op["new"]
        elif kind == "keep_first_lines":
            lines = lines[: op["count"]]
        elif kind == "drop_matching":
            lines = [line for line in lines if not re.search(op["pattern"], line)]
        elif kind == "replace_matching":
            lines = [re.sub(op["pattern"], op["new"], line) for line in lines]
        elif kind == "insert_after":
            index = lines.index(op["line"])
            lines[index + 1:index + 1] = op["lines"]
        else:
            raise ValueError(f"unknown mutation {kind}")
        if lines == before:
            raise ValueError(f"{op} changed nothing")
    return "\n".join(lines)


def sanitize(text: str, replacements: list) -> str:
    for old, new in sorted(replacements, key=lambda pair: -len(pair[0])):
        if old:
            text = text.replace(old, new)
    for pattern in PRIVATE:
        if pattern.search(text):
            raise SystemExit(f"make_fixtures.py: a private path or identifier survived sanitization ({pattern.pattern})")
    return text


def probe(python: str) -> dict:
    code = ("import sys, platform, importlib.metadata as m, hashlib, unittest_parallel.main as u;"
            "print(sys.prefix); print(sys.base_prefix); print(platform.python_version());"
            "print(platform.platform()); print(m.version('unittest-parallel')); print(m.version('coverage'));"
            "print(hashlib.sha256(open(u.__file__, 'rb').read()).hexdigest())")
    out = subprocess.run([python, "-c", code], capture_output=True, text=True, check=True).stdout.split("\n")
    keys = ("prefix", "base_prefix", "python_version", "platform", "unittest_parallel", "coverage", "main_py_sha256")
    return dict(zip(keys, out))


def run_one(python: str, args: list, source: Path, run_dir: Path, bound: int) -> tuple:
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    shutil.copy2(source, run_dir / source.name)
    log = run_dir / "log.txt"
    with log.open("wb") as handle:
        completed = subprocess.run(["timeout", str(bound), python, *args], cwd=run_dir,
                                   stdout=handle, stderr=subprocess.STDOUT, check=False)
    return completed.returncode, log.read_text(encoding="utf-8", errors="replace")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--parallel-python", required=True, help="interpreter of the hash-locked virtualenv")
    parser.add_argument("--work", required=True, type=Path, help="scratch directory outside the checkout")
    parser.add_argument("--crash-timeout", type=int, default=20,
                        help="local bound for the crash control (the workflow uses 300 s)")
    args = parser.parse_args(argv)
    work = args.work.resolve()
    if HERE in work.parents or work == HERE:
        raise SystemExit("make_fixtures.py: --work must be outside the checkout")
    facts = probe(args.parallel_python)
    replacements = [(str(work), "<scratch>"), (facts["prefix"], "<venv>"), (facts["base_prefix"], "<python>"),
                    (str(Path.home()), "<home>")]
    (FIXTURES / "real").mkdir(parents=True, exist_ok=True)
    (FIXTURES / "mutated").mkdir(parents=True, exist_ok=True)
    entries = []
    for kind, source, bound in (("controls", CONTROL, 120), ("crash", CRASH, args.crash_timeout)):
        for config, config_args in CONFIGS.items():
            for repeat in range(1, (REPEATS.get(config, 1) if kind == "controls" else 1) + 1):
                name = f"{kind}-{config}-r{repeat}"
                code, text = run_one(args.parallel_python, config_args, source, work / name, bound)
                relative = f"real/{name}.log"
                clean = sanitize(text, replacements)
                (FIXTURES / relative).write_text(clean, encoding="utf-8")
                entries.append({"file": relative, "kind": kind, "config": config, "repeat": repeat,
                                "command": "python3 " + " ".join(config_args), "exit_code": code,
                                "bound_seconds": bound, "sha256": hashlib.sha256(clean.encode()).hexdigest()})
                print(f"{relative}: exit {code}")
    mutated = []
    for spec in MUTATIONS:
        source_text = (FIXTURES / spec["source"]).read_text(encoding="utf-8")
        text = apply_mutation(source_text, spec["ops"])
        (FIXTURES / spec["file"]).write_text(text, encoding="utf-8")
        mutated.append(dict(spec, sha256=hashlib.sha256(text.encode()).hexdigest()))
    inventory = subprocess.run([sys.executable, str(HERE / "ids.py"), "--root", str(work / "controls-S-r1"),
                                "--start-directory", "."], capture_output=True, text=True, check=True).stdout
    (FIXTURES / "inventory-controls.txt").write_text(inventory, encoding="utf-8")
    index = {
        "schema": "suite-parallelism-fixtures/1",
        "evidence_class": "synthetic fixture: real local runs of the controls, not a GitHub-hosted runner",
        "generator": "make_fixtures.py --parallel-python <venv>/bin/python --work <scratch> "
                     f"--crash-timeout {args.crash_timeout}",
        "host": {"platform": facts["platform"], "python_version": facts["python_version"],
                 "machine": platform.machine()},
        "packages": {"unittest-parallel": facts["unittest_parallel"], "coverage": facts["coverage"],
                     "unittest_parallel_main_py_sha256": facts["main_py_sha256"]},
        "sanitized_prefixes": {"<scratch>": "the scratch root that holds one directory per run",
                               "<venv>": "the virtualenv prefix", "<python>": "the interpreter's base prefix",
                               "<home>": "the home directory"},
        "runs": entries,
        "mutations": mutated,
    }
    (FIXTURES / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
