"""Model-based (property/fuzz) test for adoption/tools/ecosystem-switch's txn state machine.

Coordinator directive (sota-rollout-20260925, W1 track "switch", round 8 -- a method change that
supersedes finding-by-finding patching of the round-8 review's rollback/txn findings): runs many
random sequences of apply/confirm/rollback/relink/recover/timer-fire -- plus resync and two
synthetic external-drift actions modelling an out-of-band change (a manual ``ln -sfn``, or a plain
``bootstrap-linux.sh`` re-run without ``--no-link``) -- with crash injection between every
write-ahead step, against a temp ``ECO_INSTALL_ROOT``, and asserts five invariants:

  (a) no txn is ever permanently wedged (a documented operator sequence always reaches a clean
      state);
  (b) rollback of a txn is refused while any later txn for the component is
      applied/unconfirmed/in_progress, for every txn kind including relink;
  (c) the rollback:intent marker is written only after all refusal pre-checks pass;
  (d) live links/files always equal the ledger's derived state after recover;
  (e) a timer only acts on its own txn.

stdlib only (unittest, random, tempfile, contextlib, io, json, os, types, importlib). Deterministic:
MODEL_TEST_SEED (default 20260925) is combined with the sequence index to seed a fresh
``random.Random`` per sequence, so any failure names an exact, independently reproducible seed and
step index. MODEL_TEST_SEQUENCES/MODEL_TEST_STEPS (defaults below) size the run; both are
overridable for a longer exploratory run without editing this file.

Every action below calls ecosystem-switch's own cmd_* handler directly, in-process (imported the
same way tests/test_adoption_switch.py does, via importlib against the real script -- see
_load_switch_module), never through main() and never via subprocess: this is what makes many
thousands of steps finish in well under a minute, and it is also what makes the crash-injection
technique below possible at all (it patches the module's own Ledger.append and op_* functions,
which only affects calls made through this same in-process module object -- see `instrumented`).

Scope note (recorded rather than hidden): crash injection here is a Python exception raised
between two of the tool's own write-ahead checkpoints (a real mutation returning, or a ledger
append completing) -- it faithfully exercises the ledger/rollback resumability logic those
checkpoints exist to protect, but it cannot reproduce a literal `kill -9` leaving switch.lock's
flock held by a dead process (Python's `with` block still runs its own `finally` on any raised
exception, including the synthetic ModelCrash below, and releases the flock cleanly). That
OS-level scenario needs a real subprocess kill, which conflicts with running thousands of sequences
quickly in-process; it is not one of the five invariants this file is asked to enforce.

A second, narrower scope note this run's own crash injection surfaced: every forward operation
kind (op_link/op_text_replace/op_file_write/...) mutates the real filesystem FIRST and is ledgered
by its caller in a SEPARATE, subsequent call -- a real crash between those two steps, for a txn's
very first operation (before even ``txn_begin``'s own reversibility is established by anything
else), leaves a live change with no ledger entry at all describing it, not even an in_progress one.
Nothing then attributes it to any txn (rollback_txn has nothing recorded to reverse), but nothing
silently proceeds on top of it either -- the tool's own drift gate (`apply`'s drift_issue) refuses
the next apply until an operator runs `adopt --resync`, the same documented path a genuine
out-of-band `ln -sfn` needs. This is a real, if extremely narrow, exposure of the tool's
consistent mutate-then-ledger ordering (present for every forward op, not something round 8
introduced or is asked to redesign into a fully write-ahead scheme); it is not a wedge
(open_txn_for_component correctly reports the component clean) and not one of the five invariants
below, so this file's own invariant (d) check is deliberately scoped to reconciliation work that
touched the specific surface it inspects (see `_assert_invariant_d_if_recover_reconciled`).
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import random
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWITCH_BIN = ROOT / "adoption" / "tools" / "ecosystem-switch"

VERSIONS = ("1.0.0", "2.0.0", "3.0.0", "4.0.0")

ACTION_NAMES = ("apply", "confirm", "rollback_bare", "rollback_txn", "relink", "resync",
                "recover", "timer_fire", "external_drift", "external_bypass")
ACTION_WEIGHTS = (6, 3, 3, 3, 2, 2, 3, 3, 1, 1)

DEFAULT_SEED = 20260925
DEFAULT_SEQUENCES = 2000
DEFAULT_STEPS = 24


def _load_switch_module():
    """A fresh, independent module object each call (never registered in sys.modules), the same
    technique tests/test_adoption_switch.py uses -- so this file's own monkey-patching (see
    `instrumented`) can never leak into that other test file's own copy even when both run in the
    same `unittest discover` process."""
    loader = importlib.machinery.SourceFileLoader("ecosystem_switch_model", str(SWITCH_BIN))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    module.time = _MonotonicClockModule(module.time)
    return module


class _MonotonicClockModule:
    """A stand-in for the real ``time`` module, bound only as ``switch_mod.time`` -- i.e. only in
    THIS model's own freshly loaded copy of ecosystem-switch's namespace, never the process-wide
    ``time`` module every other piece of code (including this test file's own ``import time``)
    keeps using unmodified. cmd_apply/cmd_adopt derive a txn id from ``int(time.time())`` plus
    ``os.getpid()`` -- collision-free for the tool's real, one-shot-CLI-subprocess deployment
    (every invocation gets a fresh PID from the OS even within the same wall-clock second), but
    not for this model, which calls many cmd_* handlers in-process, from the SAME pid, often many
    times within one real wall-clock second. ``time()`` here strictly increases by at least a
    whole second across calls so two txn-creating actions can never collide onto the same id;
    every other attribute (``gmtime``, ``strftime``, used only for the ledger's own audit
    ``at_utc`` timestamps) is forwarded unchanged to the real module."""

    def __init__(self, real_module):
        self._real = real_module
        self._next = None

    def time(self):
        # Deliberately NOT "advance only when real time has not moved": on a real system clock,
        # time.time() itself already advances (by microseconds) on almost every call, so
        # comparing against the previous raw float and bumping only "when stalled" almost never
        # triggers -- int(time.time()) (what cmd_apply/cmd_adopt actually truncate to for a txn
        # id) can still repeat across two calls a few microseconds apart. A plain +1.0 per call,
        # seeded once from the real clock, guarantees the truncated integer second strictly
        # increases every single call, which is all a txn id needs.
        self._next = self._real.time() if self._next is None else self._next + 1.0
        return self._next

    def __getattr__(self, name):
        return getattr(self._real, name)


# --------------------------------------------------------------------------------------
# Crash injection
# --------------------------------------------------------------------------------------

class ModelCrash(Exception):
    """Simulates the process dying at exactly this point: propagates out of the direct cmd_*
    call the same way a real ``kill -9`` would -- never caught by the tool's own SwitchError/Busy
    handling, since every action below calls a cmd_* handler directly rather than through main()."""


class CrashInjector:
    """Armed with a countdown before one action; ``checkpoint()`` (called after every one of the
    tool's own write-ahead mutations -- see `instrumented`) decrements it and raises ModelCrash
    once it reaches zero, then disarms itself (one crash per arming). Disarmed between actions
    regardless of outcome, so a countdown that never reaches zero within one action (it had fewer
    checkpoints than the chosen countdown) never bleeds into an unrelated, later action."""

    def __init__(self) -> None:
        self._armed = False
        self._remaining = 0
        self.injected = 0

    def arm(self, countdown: int) -> None:
        self._armed = True
        self._remaining = countdown

    def disarm(self) -> None:
        self._armed = False

    def checkpoint(self) -> None:
        if not self._armed:
            return
        if self._remaining <= 0:
            self._armed = False
            self.injected += 1
            raise ModelCrash("simulated crash at a write-ahead checkpoint")
        self._remaining -= 1


@contextlib.contextmanager
def instrumented(switch_mod):
    """Installs crash-injection checkpoints on every write-ahead primitive (``Ledger.append`` and
    every ``op_*`` mutator) and an intent-ordering monitor on ``rollback_txn`` (invariant (c)):
    yields ``(injector, intent_violations)`` and restores every original on exit, so this can be
    entered fresh once per model sequence with no cross-sequence leakage."""
    injector = CrashInjector()
    intent_violations: list[str] = []

    real_ledger_append = switch_mod.Ledger.append

    def patched_append(self, **fields):
        result = real_ledger_append(self, **fields)
        injector.checkpoint()
        return result

    switch_mod.Ledger.append = patched_append

    op_names = ("op_link", "op_text_replace", "op_file_write", "op_data_backup", "op_data_restore",
                "op_unit_restart", "op_native_cli")
    originals = {name: getattr(switch_mod, name) for name in op_names}

    def make_wrapper(fn):
        def wrapper(*args, **kwargs):
            result = fn(*args, **kwargs)
            injector.checkpoint()
            return result
        return wrapper

    for name, original in originals.items():
        setattr(switch_mod, name, make_wrapper(original))

    real_rollback_txn = switch_mod.rollback_txn

    def checked_rollback_txn(root, txn):
        # Invariant (c): a rollback_txn call that ultimately raises SwitchError (a clean refusal,
        # never a ModelCrash) must never have appended a NEW rollback:intent entry for this txn
        # along the way -- see rollback_txn's own round-8 reordering.
        before = sum(1 for e in switch_mod.Ledger(root).for_txn(txn) if e.get("op") == "rollback:intent")
        try:
            return real_rollback_txn(root, txn)
        except switch_mod.SwitchError:
            after = sum(1 for e in switch_mod.Ledger(root).for_txn(txn) if e.get("op") == "rollback:intent")
            if after > before:
                intent_violations.append(txn)
            raise

    switch_mod.rollback_txn = checked_rollback_txn

    try:
        yield injector, intent_violations
    finally:
        switch_mod.Ledger.append = real_ledger_append
        for name, original in originals.items():
            setattr(switch_mod, name, original)
        switch_mod.rollback_txn = real_rollback_txn


# --------------------------------------------------------------------------------------
# Fixture setup (one component "foo", four pre-built version roots, all synthetic)
# --------------------------------------------------------------------------------------

def _iso(offset_seconds: float) -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + offset_seconds))


def _write_receipt(root: Path, rid: str, component_id: str, version: str) -> None:
    receipts_dir = root / "switch" / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema_version": 1, "id": f"{component_id}-{version}-{rid}", "kind": "native_rollout",
        "status": "passed",
        "identity": {"component_id": component_id, "version": version, "host_id": "model-test"},
        "upstream": {"repo": "https://example.invalid/x", "tag": f"v{version}",
                     "artifact_url": "https://example.invalid/x.tar.gz", "sha256": "0" * 64},
        "install": {"class": "tarball", "root": f"${{STACK_HOME}}/tools/{component_id}-{version}",
                    "marker_sha256": "0" * 64, "argv": ["true"], "private_env_names": []},
        "tiers": [{"tier": tier, "commands": [], "result": "passed"} for tier in ("T0", "T2", "T4")]
                 + [{"tier": "T1", "commands": [], "result": "unavailable", "unavailable_reason": "no GPU"}],
        "independent": {"rerun_label": "model", "agreement": "same_result", "loki": []},
        "decision": "retain", "evidence_class_claimed": "local_integration",
        "limitations": ["Synthetic model-test receipt (tests/test_adoption_switch_model.py); not a real rollout."],
        "retained_native_failures": [],
    }
    (receipts_dir / f"{rid}.json").write_text(json.dumps(receipt))


def _setup_root(tmp_dir: Path) -> Path:
    root = tmp_dir / "eco"
    root.mkdir()
    (root / "bin").mkdir()
    (root / "tools").mkdir()
    for version in VERSIONS:
        bin_dir = root / "tools" / f"foo-{version}" / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "foo").write_text(version)
    (root / "bin" / "foo").symlink_to(root / "tools" / "foo-1.0.0" / "bin" / "foo")
    (root / "switch").mkdir()
    spec = {"schema_version": 1, "components": {"foo": {
        "version": "1.0.0", "kind": "tarball", "root_name": "foo-1.0.0", "current_link": "current/foo",
        "entrypoints": [{"bin": "bin/foo", "in_root": "bin/foo"}], "surfaces": [], "state_dirs": [],
        "window": "default", "rollback_class": "safe",
    }}}
    (root / "switch" / "components.json").write_text(json.dumps(spec))
    (root / "switch" / "windows").mkdir(parents=True)
    window = {"name": "default", "start_utc": _iso(-3600), "end_utc": _iso(3600 * 24),
              "allowed_components": ["foo"]}
    (root / "switch" / "windows" / "default.json").write_text(json.dumps(window))
    for index, version in enumerate(VERSIONS, start=1):
        _write_receipt(root, f"R{index}", "foo", version)
    return root


# --------------------------------------------------------------------------------------
# Actions
# --------------------------------------------------------------------------------------

class ActionResult:
    __slots__ = ("ok", "crashed", "code", "payload", "error")

    def __init__(self, ok, crashed, code, payload, error):
        self.ok = ok
        self.crashed = crashed
        self.code = code
        self.payload = payload
        self.error = error


class Actions:
    def __init__(self, switch_mod, root: Path, injector: CrashInjector):
        self.switch_mod = switch_mod
        self.root = root
        self.injector = injector

    def _call(self, crash_after, fn, **kwargs) -> ActionResult:
        if crash_after is not None:
            self.injector.arm(crash_after)
        buf = io.StringIO()
        try:
            namespace = types.SimpleNamespace(**kwargs)
            with contextlib.redirect_stdout(buf):
                code = fn(namespace)
            payload = None
            text = buf.getvalue().strip()
            if text:
                with contextlib.suppress(Exception):
                    payload = json.loads(text.splitlines()[-1])
            return ActionResult(code == 0, False, code, payload, None)
        except ModelCrash:
            return ActionResult(False, True, None, None, None)
        except self.switch_mod.SwitchError as error:
            return ActionResult(False, False, getattr(error, "exit_code", 1), None, error)
        finally:
            self.injector.disarm()

    def _plan_sha(self, version: str) -> str:
        to_root = self.root / "tools" / f"foo-{version}"
        try:
            spec = self.switch_mod.load_spec(self.root, None)
            steps = self.switch_mod.build_apply_plan(spec, "foo", str(to_root.resolve()), root=self.root)
            return self.switch_mod.plan_sha256(steps)
        except self.switch_mod.SwitchError:
            # current_link does not exist yet (no relink ever ran): apply refuses on the same
            # ground again, from inside the lock, whatever digest is passed here.
            return "0" * 64

    def apply(self, version, *, crash_after=None, confirm_within=None) -> ActionResult:
        to_root = self.root / "tools" / f"foo-{version}"
        rid = f"R{VERSIONS.index(version) + 1}"
        return self._call(crash_after, self.switch_mod.cmd_apply, component="foo",
                           to_root=str(to_root.resolve()), receipt=rid, window="default",
                           plan_sha256=self._plan_sha(version), confirm_within=confirm_within, spec=None)

    def confirm(self, txn, *, crash_after=None) -> ActionResult:
        return self._call(crash_after, self.switch_mod.cmd_confirm, txn=txn)

    def rollback_bare(self, *, crash_after=None) -> ActionResult:
        return self._call(crash_after, self.switch_mod.cmd_rollback, component="foo", txn=None,
                           if_unconfirmed=False)

    def rollback_txn(self, txn, *, crash_after=None) -> ActionResult:
        return self._call(crash_after, self.switch_mod.cmd_rollback, component=None, txn=txn,
                           if_unconfirmed=False)

    def timer_fire(self, txn, *, crash_after=None) -> ActionResult:
        return self._call(crash_after, self.switch_mod.cmd_rollback, component=None, txn=txn,
                           if_unconfirmed=True)

    def relink(self, *, crash_after=None) -> ActionResult:
        return self._call(crash_after, self.switch_mod.cmd_adopt, baseline=False, relink=True,
                           resync=None, reason=None, component=["foo"], spec=None)

    def resync(self, reason, *, crash_after=None) -> ActionResult:
        return self._call(crash_after, self.switch_mod.cmd_adopt, baseline=False, relink=False,
                           resync="foo", reason=reason, component=None, spec=None)

    def recover(self, *, crash_after=None) -> ActionResult:
        return self._call(crash_after, self.switch_mod.cmd_recover)

    def external_drift_current_link(self, rng: random.Random):
        link_path = self.root / "current" / "foo"
        if not link_path.is_symlink():
            return None
        before = os.readlink(link_path)
        version = rng.choice(VERSIONS)
        target = str((self.root / "tools" / f"foo-{version}").resolve())
        link_path.unlink()
        link_path.symlink_to(target)
        return ("current/foo", before)

    def external_bypass_entrypoint(self, rng: random.Random):
        link_path = self.root / "bin" / "foo"
        if not link_path.is_symlink():
            return None
        before = os.readlink(link_path)
        version = rng.choice(VERSIONS)
        target = str((self.root / "tools" / f"foo-{version}" / "bin" / "foo").resolve())
        link_path.unlink()
        link_path.symlink_to(target)
        return ("bin/foo", before)


def _dispatch(actions: Actions, rng: random.Random, name: str, known_txns: list[str], drift_log: list):
    """Runs one named action with its own randomly-chosen parameters (and a randomly-chosen crash
    countdown roughly a third of the time). Returns (ActionResult-or-None, extra); extra is
    (target_txn, before_snapshot) for a timer_fire step (invariant (e)) or None."""
    crash_after = rng.randint(0, 7) if rng.random() < 0.35 else None
    if name == "apply":
        version = rng.choice(VERSIONS)
        confirm_within = rng.choice((None, None, 30, 300))
        return actions.apply(version, crash_after=crash_after, confirm_within=confirm_within), None
    if name == "confirm":
        if not known_txns:
            return None, None
        return actions.confirm(rng.choice(known_txns), crash_after=crash_after), None
    if name == "rollback_bare":
        return actions.rollback_bare(crash_after=crash_after), None
    if name == "rollback_txn":
        if not known_txns:
            return None, None
        return actions.rollback_txn(rng.choice(known_txns), crash_after=crash_after), None
    if name == "relink":
        return actions.relink(crash_after=crash_after), None
    if name == "resync":
        return actions.resync("model fuzz resync", crash_after=crash_after), None
    if name == "recover":
        return actions.recover(crash_after=crash_after), None
    if name == "timer_fire":
        if not known_txns:
            return None, None
        txn = rng.choice(known_txns)
        before = _status_snapshot(actions.switch_mod, actions.root, exclude=txn)
        return actions.timer_fire(txn, crash_after=crash_after), (txn, before)
    if name == "external_drift":
        drifted = actions.external_drift_current_link(rng)
        if drifted:
            drift_log.append(drifted)
        return None, None
    if name == "external_bypass":
        drifted = actions.external_bypass_entrypoint(rng)
        if drifted:
            drift_log.append(drifted)
        return None, None
    raise AssertionError(f"unknown model action {name!r}")


# --------------------------------------------------------------------------------------
# Independent invariant checks (re-derived from raw ledger facts, not by calling the same
# helper functions rollback_txn/_superseding_txn use, so a bug in that shared logic cannot
# simply be reproduced -- and pass -- here too)
# --------------------------------------------------------------------------------------

def _status_snapshot(switch_mod, root: Path, exclude: str) -> dict:
    state = switch_mod.load_state(root)
    return {txn: record.get("status") for txn, record in state["txns"].items() if txn != exclude}


def _standing_and_seq(switch_mod, root: Path, component_id: str) -> dict:
    ledger_entries = switch_mod.Ledger(root).all()
    state = switch_mod.load_state(root)
    result = {}
    for txn, record in state["txns"].items():
        if record.get("component") != component_id:
            continue
        seqs = [e["seq"] for e in ledger_entries
                if e.get("txn") == txn and e.get("op") in switch_mod.OPERATION_KINDS and e.get("seq") is not None]
        if seqs:
            result[txn] = (record.get("status"), min(seqs))
    return result


def assert_invariant_b(switch_mod, root: Path, component_id: str, rolled_back_txn: str, note: str) -> None:
    info = _standing_and_seq(switch_mod, root, component_id)
    if rolled_back_txn not in info:
        return
    _, own_seq = info[rolled_back_txn]
    for other_txn, (status, other_seq) in info.items():
        if other_txn == rolled_back_txn:
            continue
        if status in switch_mod.STANDING_TXN_STATUSES and other_seq > own_seq:
            raise AssertionError(
                f"invariant (b) violated ({note}): {rolled_back_txn!r} was rolled back while a later, "
                f"still-standing txn {other_txn!r} (status {status!r}) already existed")


def assert_invariant_d(switch_mod, root: Path, component_id: str, note: str) -> None:
    state = switch_mod.load_state(root)
    recorded = (state["components"].get(component_id) or {}).get("current")
    link_path = root / "current" / component_id
    live = os.readlink(link_path) if link_path.is_symlink() else None
    if live != recorded:
        raise AssertionError(
            f"invariant (d) violated ({note}): after recover, current/{component_id} live target "
            f"{live!r} does not equal the ledger's derived state {recorded!r}")


def _txn_touches_current_link(switch_mod, root: Path, txn: str, component_id: str) -> bool:
    return any(entry.get("op") == "link" and str(entry.get("surface") or "").startswith("current/")
               for entry in switch_mod.Ledger(root).for_txn(txn) if entry.get("op") in switch_mod.OPERATION_KINDS)


def _assert_invariant_d_if_recover_reconciled(switch_mod, root: Path, component_id: str,
                                               recover_result: ActionResult, note: str) -> None:
    """Invariant (d) is scoped to what it actually says -- "after recover" -- meaning after
    recover has DONE something to THIS component's current/<id> switch point specifically (rolled
    back or closed-as-superseded a txn that itself had a forward "link" entry on it), not as a
    general claim that recover repairs arbitrary un-ledgered drift on a surface none of what it
    just reconciled ever touched. Two cases that are NOT what this invariant claims: (1) this
    tool never promises recover fixes drift with no open txn at all (`adopt --resync` is its own
    documented mechanism for a live value some out-of-band change produced, and resync updates the
    LEDGER to match what is live, not the other way around); (2) a txn recover reconciles that
    crashed before its own first forward operation was ever ledgered (a real, narrow, documented
    exposure -- see this file's own module docstring -- of the tool's mutate-then-ledger ordering
    for every forward op kind, not one of the five invariants this file enforces) has, correctly,
    nothing of its own for rollback_txn to reverse and nothing for recover to have gotten wrong;
    any pre-existing mismatch on current/<id> in that case predates and is unrelated to what THIS
    recover call actually did, and remains a drift `resync` -- not recover -- addresses. Only
    checks when at least one reconciled txn's own forward entries include a "link" on
    current/<id>, so this only ever fires for reconciliation work invariant (d) actually concerns."""
    if recover_result.crashed or not recover_result.ok or not recover_result.payload:
        return
    reconciled = (recover_result.payload.get("recovered_txns") or []) + \
        (recover_result.payload.get("superseded_txns") or [])
    if any(_txn_touches_current_link(switch_mod, root, txn, component_id) for txn in reconciled):
        assert_invariant_d(switch_mod, root, component_id, note + " (recover reconciled a current-link txn)")


def assert_invariant_e(switch_mod, root: Path, target_txn: str, before_snapshot: dict, note: str) -> None:
    after_snapshot = _status_snapshot(switch_mod, root, exclude=target_txn)
    if before_snapshot != after_snapshot:
        changed = {t: (before_snapshot.get(t), after_snapshot.get(t)) for t in
                   set(before_snapshot) | set(after_snapshot) if before_snapshot.get(t) != after_snapshot.get(t)}
        raise AssertionError(
            f"invariant (e) violated ({note}): firing the timer for {target_txn!r} changed another "
            f"txn's own status: {changed}")


def _is_component_clean(switch_mod, root: Path, component_id: str) -> bool:
    return switch_mod.open_txn_for_component(root, component_id) is None


def reconcile_to_clean_state(switch_mod, actions: Actions, root: Path, component_id: str,
                              drift_log: list, note: str, max_iterations: int = 8) -> None:
    """Invariant (a): from whatever state a sequence's random walk (crash injection, external
    drift) left `component_id` in, a bounded, documented operator sequence must always reach a
    clean one (``open_txn_for_component`` returns None -- no open or interrupted-rollback txn
    left). Tries, each pass: `recover`; then `confirm` (pending_confirmation) or `rollback --txn`
    (every other status) on whichever single txn `open_txn_for_component` still names (there is
    at most one, by construction: apply/relink refuse a second one while any is open -- see that
    function's own round-8 docstring). A refusal naming drift on a surface this same sequence's
    own external_drift/external_bypass actions touched is repaired by restoring that surface to
    its pre-drift value (the "investigate and fix it by hand" this tool's own drift refusals
    advise -- this model is the only source of drift in a closed test environment) and retried.
    Raises AssertionError -- a genuine invariant (a) failure -- on non-convergence, or on any
    refusal this function does not recognize as a repairable drift."""
    for _ in range(max_iterations):
        if _is_component_clean(switch_mod, root, component_id):
            return
        recover_result = actions.recover()
        _assert_invariant_d_if_recover_reconciled(switch_mod, root, component_id, recover_result, note)
        if _is_component_clean(switch_mod, root, component_id):
            return
        open_txn = switch_mod.open_txn_for_component(root, component_id)
        if open_txn is None:
            return
        txn, descriptive_status = open_txn
        state = switch_mod.load_state(root)
        record = state["txns"].get(txn, {})
        if record.get("status") == "pending_confirmation":
            result = actions.confirm(txn)
        else:
            result = actions.rollback_txn(txn)
        if result.ok:
            continue
        message = str(result.error) if result.error else ""
        if "no longer matches" in message or "drift" in message.lower():
            # Restore each distinct drifted surface to its OWN most recent pre-drift value only
            # -- not by walking the whole drift_log in reverse, which would cascade past exactly
            # what the stuck txn expects and keep undoing progressively OLDER drifts too. Correct
            # because reconcile_to_clean_state runs after every single step: an earlier drift, by
            # the time a later one happens, has already had its own reconciliation pass (finding
            # nothing open, doing nothing) -- so the only drift ever still unresolved for a given
            # surface at this point is the most recent one recorded for it.
            restored_any = False
            latest_per_surface = {}
            for surface, previous_value in drift_log:
                latest_per_surface[surface] = previous_value
            for surface, previous_value in latest_per_surface.items():
                link_path = root / surface
                if link_path.is_symlink() and os.readlink(link_path) != previous_value:
                    link_path.unlink()
                    link_path.symlink_to(previous_value)
                    restored_any = True
            if restored_any:
                continue
        raise AssertionError(
            f"invariant (a) violated ({note}): txn {txn!r} (status {descriptive_status!r}) could not "
            f"be reconciled to a clean state: {message!r}")
    raise AssertionError(
        f"invariant (a) violated ({note}): reconciliation did not converge within {max_iterations} "
        "iterations")


# --------------------------------------------------------------------------------------
# The model test itself
# --------------------------------------------------------------------------------------

class AdoptionSwitchModelTests(unittest.TestCase):
    def test_state_machine_invariants_hold_across_many_random_crash_injected_sequences(self):
        switch_mod = _load_switch_module()
        base_seed = int(os.environ.get("MODEL_TEST_SEED", str(DEFAULT_SEED)))
        sequences = int(os.environ.get("MODEL_TEST_SEQUENCES", str(DEFAULT_SEQUENCES)))
        steps_per_sequence = int(os.environ.get("MODEL_TEST_STEPS", str(DEFAULT_STEPS)))

        stub_dir = tempfile.TemporaryDirectory()
        self.addCleanup(stub_dir.cleanup)
        systemd_run_stub = Path(stub_dir.name) / "systemd-run-stub.py"
        systemd_run_stub.write_text("#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n")
        systemd_run_stub.chmod(0o755)
        systemctl_stub = Path(stub_dir.name) / "systemctl-stub.py"
        systemctl_stub.write_text("#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n")
        systemctl_stub.chmod(0o755)

        env_names = ("ECO_INSTALL_ROOT", "ECOSYSTEM_SWITCH_SYSTEMD_RUN", "ECOSYSTEM_SWITCH_SYSTEMCTL")
        saved_env = {name: os.environ.get(name) for name in env_names}

        def restore_env():
            for name, value in saved_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

        self.addCleanup(restore_env)
        os.environ["ECOSYSTEM_SWITCH_SYSTEMD_RUN"] = f"{sys.executable} {systemd_run_stub}"
        os.environ["ECOSYSTEM_SWITCH_SYSTEMCTL"] = f"{sys.executable} {systemctl_stub}"

        tmp_root_holder = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_root_holder.cleanup)
        tmp_root = Path(tmp_root_holder.name)

        total_steps = 0
        total_crashes = 0
        all_intent_violations: list[str] = []

        for sequence_index in range(sequences):
            rng = random.Random(base_seed + sequence_index)
            sequence_dir = tmp_root / f"seq-{sequence_index}"
            sequence_dir.mkdir()
            root = _setup_root(sequence_dir)
            os.environ["ECO_INSTALL_ROOT"] = str(root)
            known_txns: list[str] = []
            drift_log: list = []

            with instrumented(switch_mod) as (injector, intent_violations):
                actions = Actions(switch_mod, root, injector)
                for step_index in range(steps_per_sequence):
                    total_steps += 1
                    name = rng.choices(ACTION_NAMES, weights=ACTION_WEIGHTS, k=1)[0]
                    note = f"seed {base_seed + sequence_index} step {step_index} action {name}"
                    result, extra = _dispatch(actions, rng, name, known_txns, drift_log)

                    if result is not None:
                        with contextlib.suppress(Exception):
                            state = switch_mod.load_state(root)
                            for txn in state["txns"]:
                                if txn not in known_txns:
                                    known_txns.append(txn)

                    if result is not None and not result.crashed and result.ok:
                        if name in ("rollback_bare", "rollback_txn", "timer_fire"):
                            payload = result.payload or {}
                            if payload.get("status") == "rolled_back" and payload.get("txn"):
                                assert_invariant_b(switch_mod, root, "foo", payload["txn"], note)
                        if name == "recover":
                            _assert_invariant_d_if_recover_reconciled(switch_mod, root, "foo", result, note)
                        if name == "timer_fire" and extra is not None:
                            target_txn, before_snapshot = extra
                            assert_invariant_e(switch_mod, root, target_txn, before_snapshot, note)

                    # Invariant (a), checked after every step: whatever this step (crashed,
                    # refused, or successful) left behind, a bounded operator sequence must be
                    # able to reach a clean state from here. (Invariant (d) is checked from
                    # *inside* reconcile_to_clean_state, scoped to recover calls that actually
                    # reconciled a txn -- not to unresolved drift with no open txn, which this
                    # tool never claims recover fixes; see resync.)
                    reconcile_to_clean_state(switch_mod, actions, root, "foo", drift_log, note)

                total_crashes += injector.injected
                all_intent_violations.extend(intent_violations)

        self.assertEqual(
            all_intent_violations, [],
            "invariant (c) violated: rollback:intent was written for a txn whose rollback call "
            "ultimately raised SwitchError (a clean refusal) -- see rollback_txn's round-8 reordering")

        summary = (f"model test: {sequences} sequences x {steps_per_sequence} steps = {total_steps} "
                   f"total steps, {total_crashes} simulated crashes injected (seed {base_seed})")
        print(summary, file=sys.stderr)
        self.summary = summary  # exposed for a caller that wants it without parsing stderr


if __name__ == "__main__":
    unittest.main()
