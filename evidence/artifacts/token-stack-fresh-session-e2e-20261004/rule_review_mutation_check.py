"""Mutation check of the execution-rule review: each mutant of codex_hook_trust.py must fail at least one test. Run from the repository root.
Works on a temporary copy; the checkout is not touched."""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path.cwd()
MUTANTS = {
    "a failed listing reads as no rules (P1 as reviewed)": (
        "    except FileNotFoundError:\n        return []\n    return sorted(found)",
        "    except OSError:\n        return []\n    return sorted(found)"),
    "the review comes after the app-server starts": (
        "    review = review_rules(home, codex, args.rtk)\n    for line in review.lines(home):\n        print(line)\n    blocked = review.blocked and not args.allow_exec_rules\n    if args.apply and blocked:",
        "    review = review_rules(home, codex, args.rtk)\n    for line in review.lines(home):\n        print(line)\n    blocked = review.blocked and not args.allow_exec_rules\n    if False:"),
    "the sample is dropped": (
        "for argv in dict.fromkeys([*(tuple(shlex.split(command)) for command in REWRITE_SAMPLE), *heads, *examples]):",
        "for argv in dict.fromkeys([*heads, *examples]):"),
    "heads are not probed": (
        "for argv in dict.fromkeys([*(tuple(shlex.split(command)) for command in REWRITE_SAMPLE), *heads, *examples]):",
        "for argv in dict.fromkeys([*(tuple(shlex.split(command)) for command in REWRITE_SAMPLE), *examples]):"),
    "examples are not probed": (
        "for argv in dict.fromkeys([*(tuple(shlex.split(command)) for command in REWRITE_SAMPLE), *heads, *examples]):",
        "for argv in dict.fromkeys([*(tuple(shlex.split(command)) for command in REWRITE_SAMPLE), *heads]):"),
    "any difference is an exposure": (
        "if before_decision in RESTRICTING and RANK[after_decision] < RANK[before_decision]:",
        "if after_decision != before_decision:"),
    "a weaker twin passes (only no-match counts)": (
        "if before_decision in RESTRICTING and RANK[after_decision] < RANK[before_decision]:",
        "if before_decision in RESTRICTING and after_decision is None:"),
    "the files are evaluated one at a time": (
        "    for path in files:\n        command += [\"--rules\", str(path)]\n    done = invoke([*command, \"--\", *argv], runner, env)",
        "    command += [\"--rules\", str(files[0])]\n    done = invoke([*command, \"--\", *argv], runner, env)"),
    "the real home is the evaluator's home": (
        "            settings = lane.codex_env(Path(scratch))",
        "            settings = lane.codex_env(home)"),
    "--check ignores an exposure": (
        "                if blocked:\n                    print(\"not accepted:",
        "                if False:\n                    print(\"not accepted:"),
    "a symlink is followed": (
        "entry.is_file(follow_symlinks=False)", "entry.is_file()"),
    "an unsupported statement is skipped": (
        "            raise ReviewError(f\"line {node.lineno}: {call.func.id}() is not read by this tool\")",
        "            continue"),
    "no rtk executable is fine": (
        "        review.problems.append(\"no rtk executable on PATH (or --rtk): the rules cannot be compared with the rewrite\")\n        return review",
        "        return review"),
    "a failing evaluator is no decision": (
        "    if done.returncode != 0:\n        raise ReviewError(f\"codex execpolicy check failed",
        "    if done.returncode != 0 and False:\n        raise ReviewError(f\"codex execpolicy check failed"),
}

with tempfile.TemporaryDirectory(prefix="mutants-") as scratch:
    base = Path(scratch) / "base"
    (base / "tools").mkdir(parents=True)
    shutil.copytree(root / "tools" / "adoption", base / "tools" / "adoption")
    (base / "tests").mkdir()
    (base / "scripts").symlink_to(root / "scripts")
    shutil.copy(root / "tests" / "test_codex_hook_trust.py", base / "tests")
    record = Path("evidence/artifacts/token-stack-fresh-session-e2e-20261004/rtk-behaviour-probe.json")
    (base / record.parent).mkdir(parents=True)
    shutil.copy(root / record, base / record)
    (base / record.parent / "fixtures").mkdir()
    shutil.copy(root / record.parent / "fixtures" / "hcom-deny.rules", base / record.parent / "fixtures")
    tool = base / "tools" / "adoption" / "codex_hook_trust.py"
    original = tool.read_text(encoding="utf-8")

    def run_tests():
        done = subprocess.run([sys.executable, "-B", "-m", "unittest", "tests.test_codex_hook_trust"], cwd=base, capture_output=True, text=True)
        tail = done.stderr.strip().splitlines()[-1] if done.stderr.strip() else done.stdout[-80:]
        return done.returncode, tail

    base_code, base_tail = run_tests()
    print("baseline:", base_code, base_tail)
    if base_code:
        sys.exit("the baseline must pass")
    survivors = []
    for name, (old, new) in MUTANTS.items():
        if original.count(old) != 1:
            print(f"!! cannot apply: {name} ({original.count(old)} matches)")
            survivors.append(name)
            continue
        tool.write_text(original.replace(old, new), encoding="utf-8")
        code, tail = run_tests()
        failed = re.search(r"FAILED \((.*)\)", tail)
        print(f"{'killed' if code else 'SURVIVED'}: {name}: {tail}")
        if not code:
            survivors.append(name)
    tool.write_text(original, encoding="utf-8")
    print("survivors:", survivors)
