"""Hermetic DEFAULT_STOP isolation for adaptive-paper engine tests.

blueprints/us-equities/adaptive-paper/safety.py binds one canonical
live-host kill switch, DEFAULT_STOP =
~/.local/state/native-agent-stack/alpaca-paper/STOP, and derives its default
lock root from it (DEFAULT_STOP.parent / "locks"). runner.py and
native_strategy.py each bind their own DEFAULT_STOP name via
`from safety import ... DEFAULT_STOP`, so any test that omits
stop_file/lock_root to safety.Ledger.reserve_intent/validate_pending,
runner.run_native, or native_strategy.AdaptiveStrategy reads the live file
and its sibling lock directory instead of a fixture -- and fails or errors
whenever that live kill switch happens to exist.

Call patch_default_stop() from a test module's setUpModule and
restore_default_stop() from its tearDownModule to repoint every
already-imported engine module's DEFAULT_STOP at a private path for the
duration of that module's tests. The path sits under a fresh
tempfile.TemporaryDirectory() that is never written to, so `.exists()` is
always False there -- equivalent to "no live STOP" -- and the directory is
removed again in restore_default_stop().

Tests that deliberately exercise a STOP file keep working: they either
create their own file/pass their own stop_file or lock_root explicitly to
the call under test, or patch DEFAULT_STOP themselves for the duration of a
single test (e.g. test_native_faults_min.py's per-test
unittest.mock.patch.object calls), which simply shadows this module-level
value and restores over top of it.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Names under which the engine modules this suite cares about are commonly
# already present in sys.modules by the time setUpModule runs: safety.py
# proper, its importlib-loaded copy in test_adaptive_paper_safety.py (loaded
# there as "adaptive_paper_safety"), runner.py, and native_strategy.py (only
# importable, and hence only present, when nautilus_trader is installed).
# recovery.py currently only imports SafetyError from safety and has no
# DEFAULT_STOP attribute of its own; it is listed anyway (and skipped via
# hasattr below) so it is covered automatically if that ever changes.
_DEFAULT_MODULE_NAMES = ("safety", "adaptive_paper_safety", "runner", "native_strategy", "recovery")


def _candidate_modules(extra):
    seen_ids, modules = set(), []
    for name in _DEFAULT_MODULE_NAMES:
        module = sys.modules.get(name)
        if module is not None and id(module) not in seen_ids:
            seen_ids.add(id(module))
            modules.append(module)
    for module in extra:
        if module is not None and id(module) not in seen_ids:
            seen_ids.add(id(module))
            modules.append(module)
    return modules


def patch_default_stop(*extra_modules):
    """Repoint DEFAULT_STOP on every already-imported engine module that has
    one (see _DEFAULT_MODULE_NAMES, plus any module object passed in
    ``extra_modules``) at a private, never-created tmp path, so no test in
    this process reads the live host kill switch or its default lock root
    unless it opts in explicitly. Call once from setUpModule.

    Returns an opaque token; pass it to restore_default_stop() to undo the
    patch and clean up the backing tmp directory.
    """
    tmpdir = tempfile.TemporaryDirectory(prefix="adaptive-paper-hermetic-stop-")
    stop_path = Path(tmpdir.name) / "STOP"
    originals = []
    for module in _candidate_modules(extra_modules):
        if hasattr(module, "DEFAULT_STOP"):
            originals.append((module, module.DEFAULT_STOP))
            module.DEFAULT_STOP = stop_path
    return tmpdir, originals


def restore_default_stop(token):
    """Undo patch_default_stop(), restoring each module's original
    DEFAULT_STOP and cleaning up the tmp directory. Call once from
    tearDownModule with the token patch_default_stop() returned."""
    tmpdir, originals = token
    for module, original in originals:
        module.DEFAULT_STOP = original
    tmpdir.cleanup()
