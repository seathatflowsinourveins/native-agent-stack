"""Mutation check of the execution-rule review: each mutant of tools/adoption/codex_hook_trust.py must fail at least one test of
tests/test_codex_hook_trust.py. Run from the repository root; it works on a temporary copy, the checkout is not touched.

The tests were written after the code, so this is the check that they are not vacuous: a mutant that survives names an untested decision.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path.cwd()
LISTING = ('    try:\n        entries = os.scandir(directory)\n    except FileNotFoundError:\n        return []\n    found = []\n    with entries:\n'
           '        for entry in entries:\n            is_file = entry.is_file(follow_symlinks=False)\n'
           '            if is_file and Path(entry.name).suffix == ".rules":\n                found.append(directory / entry.name)\n    return sorted(found)')
MUTANTS = {
    "a FileNotFoundError on an entry or the iteration reads as no rules (705e finding 1)": (
        LISTING,
        '    found = []\n    try:\n        with os.scandir(directory) as entries:\n            for entry in entries:\n'
        '                is_file = entry.is_file(follow_symlinks=False)\n                if is_file and Path(entry.name).suffix == ".rules":\n'
        '                    found.append(directory / entry.name)\n    except FileNotFoundError:\n        return []\n    return sorted(found)'),
    "the extension is looked at before the file type (an error on another entry is not seen)": (
        '            is_file = entry.is_file(follow_symlinks=False)\n            if is_file and Path(entry.name).suffix == ".rules":',
        '            if Path(entry.name).suffix == ".rules" and entry.is_file(follow_symlinks=False):'),
    "a symlink is followed": (
        "is_file = entry.is_file(follow_symlinks=False)", "is_file = entry.is_file()"),
    "host_executable arguments are not validated (705e finding 2)": (
        "values[keyword.arg] = literal(keyword.value, node.lineno, builtin, keyword.arg)",
        'values[keyword.arg] = literal(keyword.value, node.lineno, builtin, keyword.arg) if builtin == "prefix_rule" else None'),
    "only pattern, decision, name and paths are validated": (
        "values[keyword.arg] = literal(keyword.value, node.lineno, builtin, keyword.arg)",
        'values[keyword.arg] = literal(keyword.value, node.lineno, builtin, keyword.arg) if keyword.arg in ("pattern", "decision", "name", "paths") else None'),
    "an argument this tool does not know is accepted": (
        "            if keyword.arg not in known:\n                raise ReviewError(", "            if False:\n                raise ReviewError("),
    "an invalid decision is accepted": (
        "        if decision not in DECISIONS:\n            raise ReviewError(", "        if False:\n            raise ReviewError("),
    "only the first alternative of the first token is checked": (
        "        first = rule.pattern[0] if isinstance(rule.pattern[0], list) else [rule.pattern[0]]",
        "        first = [rule.pattern[0] if not isinstance(rule.pattern[0], list) else rule.pattern[0][0]]"),
    "a path is not reduced to its basename": (
        '    name = token.rsplit("/", 1)[-1]\n    for pattern, source in compiled:', '    name = token\n    for pattern, source in compiled:'),
    "regex heads are ignored": (
        'for entry in fixture["heads"]]', 'for entry in fixture["heads"] if not entry["regex"]]'),
    "the version gate is dropped": (
        'if done.returncode != 0 or reported != fixture["rtk_version_output"]:', "if False:"),
    "configured transparent prefixes are ignored": (
        '            extra.append((re.compile(re.escape(words[0].rsplit("/", 1)[-1])), "[hooks].transparent_prefixes of the rtk config"))',
        "            pass"),
    "user-global TOML filters are ignored": (
        'extra = filter_heads(Path(first[len("Config: "):].strip()).parent / "filters.toml")', "extra = []"),
    "an unreadable rtk config is accepted": (
        '            raise ValueError("not the expected output")', "            pass"),
    "no rtk executable is accepted": (
        '        raise ReviewError("no rtk executable on PATH (or --rtk): the rules cannot be checked against what rtk rewrites")',
        "        return []"),
    "allow rules are exposures": (
        "            if rule.decision in RESTRICTING:\n                review.exposed.append(", "            if True:\n                review.exposed.append("),
    "forbidden and prompt rules are only notes": (
        "            if rule.decision in RESTRICTING:\n                review.exposed.append(", "            if False:\n                review.exposed.append("),
    "allow-only rules ask rtk": (
        "        if review.restricting:\n            compiled = compiled + rtk_state(rtk, fixture, runner)", "        if True:\n            compiled = compiled + rtk_state(rtk, fixture, runner)"),
    "--apply does not refuse on an exposure": (
        "    if args.apply and blocked:", "    if False:"),
    "--check ignores an exposure": (
        "                if blocked:\n                    print(\"not accepted:", "                if False:\n                    print(\"not accepted:"),
    "a bad rules file does not fail the review when another file is fine": (
        '            review.problems.append(f"cannot read the rules of {path.name}: {error}")',
        "            pass"),
}

with tempfile.TemporaryDirectory(prefix="mutants-") as scratch:
    base = Path(scratch) / "base"
    (base / "tools").mkdir(parents=True)
    shutil.copytree(root / "tools" / "adoption", base / "tools" / "adoption")
    (base / "tests").mkdir()
    shutil.copy(root / "tests" / "test_codex_hook_trust.py", base / "tests")
    (base / "scripts").symlink_to(root / "scripts")
    e2e = Path("evidence/artifacts/token-stack-fresh-session-e2e-20261004")
    (base / e2e).parent.mkdir(parents=True)
    shutil.copytree(root / e2e, base / e2e)
    (base / "adoption").mkdir()
    shutil.copy(root / "adoption" / "pins-linux-x86_64.json", base / "adoption")
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
        print(f"{'killed' if code else 'SURVIVED'}: {name}: {tail}")
        if not code:
            survivors.append(name)
    tool.write_text(original, encoding="utf-8")
    print(f"{len(MUTANTS)} mutants, survivors: {survivors}")
    sys.exit(1 if survivors else 0)
