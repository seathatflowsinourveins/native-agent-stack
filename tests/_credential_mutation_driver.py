"""Real source-mutation driver for credential_guard.py and market_research.py.

Unlike the earlier `MUTATION_KILLS` meta-test (which patched in-process
Python objects and only *claimed* a mapping to test names as hardcoded
strings, without ever running them), this module copies the actual
`blueprints/us-equities/adaptive-paper` source tree to a private temporary
directory, applies one exact-count textual mutation to a real `.py` file in
that copy, and runs the actually-named test(s) against the mutated copy in a
subprocess (`python -m unittest <test-id> ...`), the same shape as
`scratchpad/rev-mrcred/claude/driver.py`'s independently-authored driver.
"killed" means that subprocess exits non-zero -- the named test(s) really
did fail against the mutated source, not an assumption about what "should"
happen.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTIVE_PAPER = "blueprints/us-equities/adaptive-paper"
# transport.py loads this sibling directory's order_contract.py by an
# absolute, import-time path (`Path(__file__).resolve().parent.parent /
# "order-contract" / "order_contract.py"`) -- any test id that imports
# runner.py (which imports transport.py unconditionally) needs it present
# at the same relative location in the copy, or every such run fails on an
# unrelated ImportError before the named test ever executes, which would
# silently masquerade as a "kill".
ORDER_CONTRACT = "blueprints/us-equities/order-contract"
# The pinned adaptive-paper runtime, named the same way tests/test_promotion_gate.py
# and tests/test_observability_backends_alerts.py already locate their own pinned
# tool runtimes (relative to Path.home(), never a literal host path).
PY = Path.home() / ".local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python"
_FALLBACK_PY = sys.executable


def _python():
    return str(PY) if PY.exists() else _FALLBACK_PY


# A shared test helper several `tests/test_adaptive_paper_*.py` files import
# unconditionally at module scope.
HERMETIC_HELPER = "tests/adaptive_paper_hermetic.py"


def _prepare_copy(root: Path) -> None:
    """A minimal but self-contained copy: the whole adaptive-paper source
    directory (small, ~3 MB, fast to copy), its one cross-directory import
    dependency, the shared test helper every adaptive-paper test file
    expects as a sibling, plus the specific test files a caller names."""
    (root / "blueprints" / "us-equities").mkdir(parents=True, exist_ok=True)
    shutil.copytree(REPO_ROOT / ADAPTIVE_PAPER, root / ADAPTIVE_PAPER)
    shutil.copytree(REPO_ROOT / ORDER_CONTRACT, root / ORDER_CONTRACT)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    init_file = REPO_ROOT / "tests" / "__init__.py"
    if init_file.is_file():
        shutil.copy2(init_file, root / "tests" / "__init__.py")
    shutil.copy2(REPO_ROOT / HERMETIC_HELPER, root / HERMETIC_HELPER)


def apply_mutation(root: Path, mutation: list[tuple[str, str, str, int]]) -> str:
    """`mutation` is a list of (relative_path, old, new, expected_count).
    Raises if `old` does not occur exactly `expected_count` times -- a
    mutation that silently no-ops (because the source moved on) must fail
    loudly, not report a false kill. Returns a unified-diff string."""
    import difflib
    diff_parts = []
    for rel, old, new, expected_count in mutation:
        path = root / rel
        text = path.read_text()
        found = text.count(old)
        if found != expected_count:
            raise AssertionError(
                f"mutation target text occurs {found} time(s) in {rel}, expected {expected_count} "
                f"(the mutation driver's assumption about this source no longer holds)")
        mutated = text.replace(old, new)
        path.write_text(mutated)
        diff_parts.extend(difflib.unified_diff(text.splitlines(True), mutated.splitlines(True),
                                                f"a/{rel}", f"b/{rel}"))
    return "".join(diff_parts)


def run_test_ids(root: Path, test_ids: list[str], *, timeout: int = 90) -> subprocess.CompletedProcess:
    """Runs `python -m unittest <test_ids>` with cwd=root (so each test
    file's own `Path(__file__).resolve().parents[1] / "blueprints/..."`
    lookup resolves inside the mutated copy, not the real checkout)."""
    return subprocess.run([_python(), "-m", "unittest", *test_ids],
                          cwd=root, capture_output=True, text=True, timeout=timeout)


def run_mutation(name: str, mutation: list[tuple[str, str, str, int]], test_ids: list[str],
                 extra_test_files: list[str], *, timeout: int = 90) -> dict:
    """End to end: fresh temp copy, apply the mutation, copy in the needed
    test files, run the named test ids, report whether they failed (i.e.
    this mutation was "killed"). Returns a JSON-serializable result dict."""
    with tempfile.TemporaryDirectory(prefix=f"cg-mutation-{name}-") as tmp:
        root = Path(tmp)
        _prepare_copy(root)
        for rel in extra_test_files:
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO_ROOT / rel, dest)
        diff = apply_mutation(root, mutation) if mutation else ""
        try:
            proc = run_test_ids(root, test_ids, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            return {"mutation": name, "test_ids": test_ids, "killed": False, "timed_out": True,
                    "returncode": None, "diff_lines": diff.count("\n"),
                    "stdout_tail": "", "stderr_tail": str(error)[-2000:]}
        killed = proc.returncode != 0
        return {"mutation": name, "test_ids": test_ids, "killed": killed, "timed_out": False,
                "returncode": proc.returncode, "diff_lines": diff.count("\n"),
                "stdout_tail": proc.stdout[-2000:], "stderr_tail": proc.stderr[-2000:]}
