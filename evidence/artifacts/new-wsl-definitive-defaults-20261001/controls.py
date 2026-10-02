#!/usr/bin/env python3
"""Mutate one input at a time, regenerate, and require the named unittest assertion to fail.

Usage: controls.py <worktree root>
Uses Python's unittest CLI (python/cpython v3.13.15, Lib/unittest/__main__.py), as the test module does.
Each case restores the inputs, manifest and record byte for byte, including when a command fails.
"""
import json
import subprocess
import sys
from pathlib import Path

ART = Path("evidence/artifacts/new-wsl-definitive-defaults-20261001")
RECORD = Path("docs/decisions/2026-10-01-new-wsl-definitive-defaults.md")
MODULE = "tests.test_new_wsl_definitive_defaults"
CASES = [
    ("a settled row marked definitive", "test_settled_rows_are_measurements_with_verified_receipts", None),
    ("a settlement with a wrong receipt sha256", "test_manifest_is_current", "receipt sha256 mismatch"),
    ("a settlement for a slot that is not split", "test_manifest_is_current", "not a split or measurement row"),
    ("a converged slot not marked definitive", "test_converged_slots_are_definitive_except_the_known_trading_slot", None),
    ("a row without state", "test_every_row_has_state_and_measurement", None),
    ("the memory row marked as returned", "test_memory_and_code_search_measurements_have_not_returned", None),
    ("an empty settlements file", "test_settled_rows_are_measurements_with_verified_receipts", None),
    ("a final outcome for a Claude-only repository", "test_manifest_is_current", "final repository not in combined.json"),
    ("two installed rows with one job", "test_manifest_is_current", "installed job also owned by"),
    ("a slot without a decision", "test_manifest_is_current", "codex: missing decision"),
    ("a critic install with a wrong evidence sha256", "test_manifest_is_current", "prometheus: evidence sha256 mismatch"),
    ("a covering slot that installs nothing", "test_manifest_is_current", "covered_by memory-owner installs nothing"),
    ("a split row that keeps a repository", "test_pending_measurements_install_nothing", None),
]


def run(root, *args):
    return subprocess.run([sys.executable, "-B", *map(str, args)], cwd=root, capture_output=True, text=True)


def mutate(root, case):
    if case in {entry[0] for entry in CASES[7:12]}:
        path = root / ART / "convergence.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        decisions = {d["slot_id"]: d for d in doc["decisions"]}
        if case == CASES[7][0]:
            decisions["claude-plugins-official-code-intelligence-lsp-pl"]["outcome"] = "final"
        elif case == CASES[8][0]:
            doc["jobs"]["codex"] = doc["jobs"]["claude-code"]
        elif case == CASES[9][0]:
            doc["decisions"] = [d for d in doc["decisions"] if d["slot_id"] != "codex"]
        elif case == CASES[10][0]:
            decisions["prometheus"]["critic"]["sha256"] = "0" * 64
        else:
            decisions["claude-plugins-official-code-intelligence-lsp-pl"]["covered_by"] = ["memory-owner"]
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    elif case in (CASES[1][0], CASES[2][0], CASES[6][0]):
        path = root / ART / "settlements.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        if case == CASES[1][0]:
            doc[0]["receipts"][0]["sha256"] = "0" * 64
        elif case == CASES[2][0]:
            doc[0]["slot_id"] = "container-engine"
        else:
            doc = []
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    else:
        path = root / ART / "assemble_manifest.py"
        text = path.read_text(encoding="utf-8")
        anchor = "    convergence = apply_convergence(rows, layers)\n"
        if text.count(anchor) != 1:
            raise ValueError("the assembler's mutation anchor is missing or ambiguous")
        defect = {
            CASES[0][0]: '    next(row for row in rows if row["slot_id"] == "local-model-server")["definitive"] = True\n',
            CASES[3][0]: '    next(row for row in rows if row["slot_id"] == "container-engine")["definitive"] = False\n',
            CASES[4][0]: '    del rows[0]["state"]\n',
            CASES[5][0]: '    next(row for row in rows if row["slot_id"] == "memory-owner")["measurement"]["returned"] = True\n',
            CASES[12][0]: '    next(row for row in rows if row["slot_id"] == "playwright-cli")["repository"] = "https://github.com/microsoft/playwright-cli"\n',
        }[case]
        path.write_text(text.replace(anchor, anchor + defect), encoding="utf-8")


def main():
    if len(sys.argv) != 2:
        print("usage: controls.py <worktree root>")
        return 2
    root = Path(sys.argv[1]).resolve()
    paths = [root / ART / name for name in ("assemble_manifest.py", "settlements.json", "convergence.json", "definitive-manifest.json")]
    paths.append(root / RECORD)
    originals = {path: path.read_bytes() for path in paths}

    def restore():
        for path, data in originals.items():
            if path.read_bytes() != data:
                path.write_bytes(data)

    baseline = run(root, "-m", "unittest", MODULE)
    if baseline.returncode:
        print("baseline tests failed")
        print(baseline.stdout + baseline.stderr)
        return 1
    failed = False
    for case, test, refusal in CASES:
        try:
            mutate(root, case)
            assembled = run(root, ART / "assemble_manifest.py")
            rendered = run(root, ART / "render_tables.py", "--write", RECORD)
            result = run(root, "-m", "unittest", "-v", MODULE)
            output = result.stdout + result.stderr
            generation_ok = rendered.returncode == 0 and (
                assembled.returncode == 0 if refusal is None else
                assembled.returncode != 0 and refusal in assembled.stdout + assembled.stderr)
            named_failure = f"FAIL: {test} ({MODULE}.Manifest.{test})"
            killed = generation_ok and result.returncode != 0 and named_failure in output
            print(f"{case}: {'killed' if killed else 'survived'} ({test})")
            if not killed:
                print(assembled.stdout + assembled.stderr + rendered.stdout + rendered.stderr + output)
            failed |= not killed
        except (OSError, ValueError) as error:
            print(f"{case}: survived ({error})")
            failed = True
        finally:
            restore()
        if any(path.read_bytes() != data for path, data in originals.items()):
            print("restoration failed")
            return 1
    final = run(root, "-m", "unittest", MODULE)
    print(final.stdout + final.stderr, end="")
    restored = all(path.read_bytes() == data for path, data in originals.items())
    print("all files restored" if restored else "restoration failed")
    return int(failed or final.returncode != 0 or not restored)


if __name__ == "__main__":
    sys.exit(main())
