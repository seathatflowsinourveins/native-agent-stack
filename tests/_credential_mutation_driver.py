"""Real source-mutation driver for credential_guard.py and market_research.py.

Unlike the earlier `MUTATION_KILLS` meta-test (which patched in-process
Python objects and only *claimed* a mapping to test names as hardcoded
strings, without ever running them), this module copies the actual
`blueprints/us-equities/adaptive-paper` source tree to a private temporary
directory, applies one exact-count textual mutation to a real `.py` file in
that copy, and runs the actually-named test(s) against the mutated copy in a
subprocess (`python -m unittest -v <test-id> ...`), the same shape as
`scratchpad/rev-mrcred/claude/driver.py`'s independently-authored driver.

Fix-round-4 correction (both reviewers, MEDIUM): an earlier version of this
driver counted *any* non-zero subprocess exit as a kill. That over-counts:
an ImportError, a SyntaxError, or a mistyped test id all make `unittest`
exit non-zero without ever exercising the named assertion, and
`disable_worktree_check`'s own target test asserts a precondition
(`(repo_root / ".git").exists()`) that a copied-but-unmutated tree fails
too, since the copy previously had no `.git` at all -- a false "kill" on
completely unchanged code. This version:
  1. runs `git init -q` in every copy, so that precondition holds even
     before any mutation is applied;
  2. runs the named test id(s) on the **pristine** (unmutated) copy first
     and requires every one to report "ok" -- anything else means the
     spec itself is broken (wrong test id, a real pre-existing failure,
     an environment problem) and no verdict about the mutation can be
     drawn from what happens next;
  3. only then applies the mutation and re-runs the same test id(s);
  4. counts a kill only when a named test id is present in the mutated
     run's output as a "FAIL" -- never an "ERROR" (an exception raised
     outside an `assert*` call: an import failure, a collection failure,
     or a bug in test setup/teardown) and never merely "the subprocess
     exited non-zero", which conflates the two. Note that a "FAIL" can
     itself come from `setUp()` (unittest reports a `setUp()` failure that
     raises via `self.fail`/`assertX` as "FAIL", the same as one from the
     test method body) -- this driver does not currently distinguish "the
     named test method's own assertion caught the mutation" from "its
     fixture setup did", only "unittest, taken as a whole, marked this
     specific test id FAIL and not ERROR".
  5. a "skipped" result -- the named test declined to run at all (e.g. an
     `@unittest.skipUnless` guard) -- is reported as "inconclusive", not
     folded into "survived": nothing was actually exercised, so nothing
     was actually proven either way, and the overall mutation-kill gate
     must fail on it exactly as it fails on a genuine survival.
"""
from __future__ import annotations

import re
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
# unrelated ImportError before the named test ever executes, which the
# old, cruder kill rule would have miscounted as a kill.
ORDER_CONTRACT = "blueprints/us-equities/order-contract"
# The pinned adaptive-paper runtime, named the same way tests/test_promotion_gate.py
# and tests/test_observability_backends_alerts.py already locate their own pinned
# tool runtimes (relative to Path.home(), never a literal host path).
PY = Path.home() / ".local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python"
_FALLBACK_PY = sys.executable

# A shared test helper several `tests/test_adaptive_paper_*.py` files import
# unconditionally at module scope.
HERMETIC_HELPER = "tests/adaptive_paper_hermetic.py"

# unittest -v prints one line per test: "<method> (<dotted.id>) ... <status>".
# <dotted.id> is exactly the string this driver's callers pass as a test id.
_RESULT_LINE = re.compile(r"^\S+ \((?P<dotted>[\w.]+)\) \.\.\. (?P<status>ok|FAIL|ERROR|skipped.*)\s*$")


def _python():
    return str(PY) if PY.exists() else _FALLBACK_PY


def _prepare_copy(root: Path) -> None:
    """A minimal but self-contained copy: the whole adaptive-paper source
    directory (small, ~3 MB, fast to copy), its one cross-directory import
    dependency, the shared test helper every adaptive-paper test file
    expects as a sibling, plus the specific test files a caller names --
    with a real `.git` (via `git init`) so any test that asserts "this
    checkout is a Git worktree" holds true in the copy too, before any
    mutation is ever applied."""
    (root / "blueprints" / "us-equities").mkdir(parents=True, exist_ok=True)
    shutil.copytree(REPO_ROOT / ADAPTIVE_PAPER, root / ADAPTIVE_PAPER)
    shutil.copytree(REPO_ROOT / ORDER_CONTRACT, root / ORDER_CONTRACT)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    init_file = REPO_ROOT / "tests" / "__init__.py"
    if init_file.is_file():
        shutil.copy2(init_file, root / "tests" / "__init__.py")
    shutil.copy2(REPO_ROOT / HERMETIC_HELPER, root / HERMETIC_HELPER)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True,
                   capture_output=True, text=True)


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
    """Runs `python -m unittest -v <test_ids>` with cwd=root (so each test
    file's own `Path(__file__).resolve().parents[1] / "blueprints/..."`
    lookup resolves inside the copy, not the real checkout). `-v` is what
    makes the per-test "... ok/FAIL/ERROR" lines `_parse_results` depends
    on -- unittest writes them to stderr, not stdout. `-W ignore::
    ResourceWarning` matters here specifically: several mutations make a
    normally-exception-raising `open_verified()` call succeed instead,
    leaking its returned file object (the test only wrapped the call in
    `assertRaisesRegex`, not a `with`, since it never expects a return
    value); the garbage collector's ResourceWarning for that leak prints
    mid-line, between a test's "... " and its status word, which would
    otherwise break `_RESULT_LINE`'s one-line match entirely and turn a
    real "FAIL" into a spurious "not collected"."""
    return subprocess.run([_python(), "-W", "ignore::ResourceWarning", "-m", "unittest", "-v", *test_ids],
                          cwd=root, capture_output=True, text=True, timeout=timeout)


def _parse_results(proc: subprocess.CompletedProcess) -> dict[str, str]:
    """{test_id: "ok" | "FAIL" | "ERROR" | "skipped...\"} for every test id
    unittest actually reported a per-test result line for. A test id absent
    from this dict was never collected/run at all (e.g. a module-level
    ImportError aborted collection before any test line could be printed)."""
    results: dict[str, str] = {}
    for line in (proc.stdout + "\n" + proc.stderr).splitlines():
        match = _RESULT_LINE.match(line)
        if match:
            results[match.group("dotted")] = match.group("status")
    return results


def _run_once(root: Path, test_ids: list[str], timeout: int):
    try:
        proc = run_test_ids(root, test_ids, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        return None, {"timed_out": True, "returncode": None, "stdout_tail": "",
                      "stderr_tail": str(error)[-2000:], "results": {}}
    results = _parse_results(proc)
    return proc, {"timed_out": False, "returncode": proc.returncode,
                  "stdout_tail": proc.stdout[-2000:], "stderr_tail": proc.stderr[-2000:], "results": results}


def run_mutation(name: str, mutation: list[tuple[str, str, str, int]], test_ids: list[str],
                 extra_test_files: list[str], *, timeout: int = 90) -> dict:
    """End to end: fresh temp copy; run the named test id(s) on the
    *pristine*, unmutated copy first (every one must report "ok", or the
    spec itself -- not the mutation -- is what failed, and no kill/survive
    verdict is drawn); apply the mutation; run the same test id(s) again;
    report a kill only for a test id whose status changed from "ok" to a
    real "FAIL" (never "ERROR", never merely "the process exited
    non-zero"). Returns a JSON-serializable result dict."""
    with tempfile.TemporaryDirectory(prefix=f"cg-mutation-{name}-") as tmp:
        root = Path(tmp)
        _prepare_copy(root)
        for rel in extra_test_files:
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO_ROOT / rel, dest)

        _, pristine = _run_once(root, test_ids, timeout)
        pristine_ok = (not pristine["timed_out"] and pristine["returncode"] == 0
                       and all(pristine["results"].get(t) == "ok" for t in test_ids))
        if not pristine_ok:
            return {"mutation": name, "test_ids": test_ids, "killed": False, "timed_out": pristine["timed_out"],
                    "returncode": pristine["returncode"], "diff_lines": 0, "verdict": "pristine_baseline_failed",
                    "pristine_results": pristine["results"],
                    "stdout_tail": pristine["stdout_tail"], "stderr_tail": pristine["stderr_tail"]}

        diff = apply_mutation(root, mutation) if mutation else ""
        _, mutated = _run_once(root, test_ids, timeout)
        if mutated["timed_out"]:
            return {"mutation": name, "test_ids": test_ids, "killed": False, "timed_out": True,
                    "returncode": None, "diff_lines": diff.count("\n"), "verdict": "timed_out",
                    "stdout_tail": mutated["stdout_tail"], "stderr_tail": mutated["stderr_tail"]}

        collected = {t: mutated["results"].get(t) for t in test_ids}
        killed_by = [t for t, status in collected.items() if status == "FAIL"]
        uncollected = [t for t, status in collected.items() if status is None]
        skipped = [t for t, status in collected.items() if status is not None and status.startswith("skipped")]
        # Order matters: a "FAIL" always wins (genuinely killed); otherwise
        # any uncollected or skipped test id makes the result inconclusive
        # -- nothing was actually exercised for that id, so nothing was
        # actually proven, and that must not be conflated with "survived"
        # (which specifically means the mutated code really did run and
        # really did pass). Round 6 (Codex, low): every named test id can
        # report "ok" while the *process* still exits non-zero -- a
        # tearDownClass() (or other class-scoped fixture) failure is
        # reported by unittest as a separate pseudo-test-id (e.g.
        # "tearDownClass (module.Class)"), which never matches anything in
        # `test_ids` and so never shows up in `collected` at all; ignoring
        # `mutated["returncode"]` here let that silently report "survived"
        # even though the run, taken as a whole, did not cleanly succeed.
        # A non-zero exit that none of the named ids explain is therefore
        # also "inconclusive", not "survived".
        verdict = ("killed" if killed_by else
                   "not_collected" if uncollected else
                   "inconclusive" if skipped else
                   "error_not_fail" if any(status == "ERROR" for status in collected.values()) else
                   "inconclusive" if mutated["returncode"] != 0 else
                   "survived")
        killed = bool(killed_by) and verdict == "killed"
        return {"mutation": name, "test_ids": test_ids, "killed": killed, "timed_out": False,
                "returncode": mutated["returncode"], "diff_lines": diff.count("\n"), "verdict": verdict,
                "killed_by": killed_by, "mutated_results": collected,
                "stdout_tail": mutated["stdout_tail"], "stderr_tail": mutated["stderr_tail"]}
