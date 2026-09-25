"""Model-based (property/fuzz) test for adoption/tools/ecosystem-switch's txn state machine.

Coordinator directive (sota-rollout-20260925, W1 track "switch", round 8 -- a method change that
supersedes finding-by-finding patching of the round-8 review's rollback/txn findings): runs many
random sequences of apply/confirm/rollback/relink/recover/timer-fire -- plus resync and two
synthetic external-drift actions modelling an out-of-band change (a manual ``ln -sfn``, or a plain
``bootstrap-linux.sh`` re-run without ``--no-link``) -- with crash injection between every
write-ahead step, against a temp ``ECO_INSTALL_ROOT``, and asserts six invariants:

  (a) no txn is ever permanently wedged (a documented operator sequence always reaches a clean
      state);
  (b) rollback of a txn is refused while any later txn for the component is
      applied/unconfirmed/in_progress, for every txn kind including relink;
  (c) the rollback:intent marker is written only after all refusal pre-checks pass;
  (d) live links/files always equal the ledger's derived state after recover;
  (e) a timer only acts on its own txn;
  (f) (round 9) an action scoped to one component never changes another component's own
      open-transaction state -- two independently managed components, "foo" and "bar", now share
      one sequence and interleave.

Coordinator directive (round 9 -- a correctness gap in how this file itself exercises the tool,
found by review rather than in ecosystem-switch): the round-8 version above called
``reconcile_to_clean_state`` after EVERY step, which closes any open/pending/interrupted-rollback
txn before the NEXT step ever runs. That made every one of those states -- and everything that
should have been exercised while a txn sat in one of them -- structurally unreachable from a LATER
step: ``timer_fire`` never once met a real ``pending_confirmation`` txn (it fires on some ALREADY
known txn, but the SAME step's own apply had not yet run when the timer step is chosen, and any
PRIOR step's own pending txn was already confirmed/rolled back by ITS OWN post-step reconciliation
before this step began), a crash could never land mid-rollback of a txn another step had left
open, and no drift/resync ever ran while a txn was genuinely open. The 48,000-step, 0-violation
round-8 result was real for what it covered -- clean, single-action-from-a-clean-state
sequences -- but never actually reached the states invariants (b)/(e) are about, contradicting
this file's own README/lifecycle.md-cited claim that it proves the timer's revert path and the
open-txn wedge protection. Fixed here by moving reconciliation to the END of each sequence only
(never after an individual step -- see the main loop below), asserting it actually reaches a clean
state for every component, and adding two new, self-selecting action kinds --
``timer_fire_pending`` (explicitly targets a txn that IS pending_confirmation right now, so the
timer's real revert-or-noop path runs) and ``crash_mid_rollback`` (explicitly targets a standing
txn and forces an early crash inside its own rollback, via either the timer or a direct ``--txn``
call) -- plus a second, interleaved component ("bar") so an open txn on one component can coexist
with unrelated activity on the other across several steps, the way two real adopted components
would in production. Coverage counters (visited-state-class and scenario counts; see
``AdoptionSwitchModelTests`` below) are asserted greater than zero so a future regression that
silently makes one of these scenarios unreachable again fails loudly instead of just running out
the clock on 48,000 steps that never touch it.

stdlib only (unittest, random, tempfile, contextlib, io, json, os, types, importlib). Deterministic:
MODEL_TEST_SEED (default 20260925) is combined with the sequence index to seed a fresh
``random.Random`` per sequence, so any failure names an exact, independently reproducible seed and
step index. MODEL_TEST_SEQUENCES/MODEL_TEST_STEPS (defaults below) size the run; both are
overridable for a longer exploratory run without editing this file (a MUCH smaller override is not
a supported/claimed mode: the coverage-counter assertions at the end assume the defaults' scale).

Every action below calls ecosystem-switch's own cmd_* handler directly, in-process (imported the
same way tests/test_adoption_switch.py does, via importlib against the real script -- see
_load_switch_module), never through main() and never via subprocess: this is what makes many
thousands of steps finish in a bounded time, and it is also what makes the crash-injection
technique below possible at all (it patches the module's own Ledger.append and op_* functions,
which only affects calls made through this same in-process module object -- see `instrumented`).
Note this in-process style means every mutating cmd_* call still goes through ecosystem-switch's
own switch_locks() the same as a real invocation would -- harmlessly: every call in a given
sequence runs on the same thread, one at a time, so the lock is always free when acquired here (no
contention, and thus no exercise of the round-9 bounded-wait lock behaviour -- that is
tests/test_adoption_switch.py's IfUnconfirmedLockWaitTests' job, which uses a real, separately-held
OS lock across two processes).

Scope note (recorded rather than hidden): crash injection here is a Python exception raised
between two of the tool's own write-ahead checkpoints (a real mutation returning, or a ledger
append completing) -- it faithfully exercises the ledger/rollback resumability logic those
checkpoints exist to protect, but it cannot reproduce a literal `kill -9` leaving switch.lock's
flock held by a dead process (Python's `with` block still runs its own `finally` on any raised
exception, including the synthetic ModelCrash below, and releases the flock cleanly). That
OS-level scenario needs a real subprocess kill, which conflicts with running thousands of sequences
quickly in-process; it is not one of the six invariants this file is asked to enforce.

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
(open_txn_for_component correctly reports the component clean) and not one of the six invariants
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

# Round 9: two independently managed components sharing one sequence (invariant (f) below), the
# same way a real ECO_INSTALL_ROOT adopts several components at once. Every component-scoped
# action (apply/relink/resync/rollback_bare/external_drift/external_bypass) picks one of these at
# random each time it is dispatched, so the two interleave organically across a sequence's steps
# rather than needing a dedicated "act on the other component" action of its own.
COMPONENT_IDS = ("foo", "bar")

ACTION_NAMES = ("apply", "confirm", "rollback_bare", "rollback_txn", "relink", "resync",
                "recover", "timer_fire", "timer_fire_pending", "crash_mid_rollback",
                "external_drift", "external_bypass")
ACTION_WEIGHTS = (6, 3, 3, 3, 2, 2, 3, 3, 3, 3, 1, 1)

DEFAULT_SEED = 20260925
DEFAULT_SEQUENCES = 2000
DEFAULT_STEPS = 24

# Coordinator directive (round 9): coverage counters this run must actually exercise -- named
# directly from the round-9 review's own "Requested: those counters on this model" (timer fire on
# a pending txn, a Busy refusal, drift while a txn is open) plus the two new explicit scenarios the
# round-9 coordinator directive itself asks to add (crash mid-rollback, a second interleaved
# component) -- asserted greater than zero at the end of AdoptionSwitchModelTests below, so a
# future change that silently makes one of these unreachable again fails loudly.
HARD_GATED_COUNTERS = ("timer_fire_on_pending", "busy_refusal", "open_txn_plus_drift",
                       "crash_mid_rollback", "second_component_interleaved",
                       "state_class_open", "state_class_pending", "state_class_in_progress")


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
# Fixture setup (two components "foo"/"bar", four pre-built version roots each, all synthetic)
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
    (root / "switch").mkdir()
    components = {}
    for component_id in COMPONENT_IDS:
        for version in VERSIONS:
            bin_dir = root / "tools" / f"{component_id}-{version}" / "bin"
            bin_dir.mkdir(parents=True)
            (bin_dir / component_id).write_text(version)
        (root / "bin" / component_id).symlink_to(root / "tools" / f"{component_id}-1.0.0" / "bin" / component_id)
        components[component_id] = {
            "version": "1.0.0", "kind": "tarball", "root_name": f"{component_id}-1.0.0",
            "current_link": f"current/{component_id}",
            "entrypoints": [{"bin": f"bin/{component_id}", "in_root": f"bin/{component_id}"}],
            "surfaces": [], "state_dirs": [], "window": "default", "rollback_class": "safe",
        }
        for index, version in enumerate(VERSIONS, start=1):
            _write_receipt(root, f"{component_id}-R{index}", component_id, version)
    (root / "switch" / "components.json").write_text(json.dumps({"schema_version": 1, "components": components}))
    (root / "switch" / "windows").mkdir(parents=True)
    window = {"name": "default", "start_utc": _iso(-3600), "end_utc": _iso(3600 * 24),
              "allowed_components": list(COMPONENT_IDS)}
    (root / "switch" / "windows" / "default.json").write_text(json.dumps(window))
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

    def _plan_sha(self, component_id: str, version: str) -> str:
        to_root = self.root / "tools" / f"{component_id}-{version}"
        try:
            spec = self.switch_mod.load_spec(self.root, None)
            steps = self.switch_mod.build_apply_plan(spec, component_id, str(to_root.resolve()), root=self.root)
            return self.switch_mod.plan_sha256(steps)
        except self.switch_mod.SwitchError:
            # current_link does not exist yet (no relink ever ran): apply refuses on the same
            # ground again, from inside the lock, whatever digest is passed here.
            return "0" * 64

    def apply(self, component_id, version, *, crash_after=None, confirm_within=None) -> ActionResult:
        to_root = self.root / "tools" / f"{component_id}-{version}"
        rid = f"{component_id}-R{VERSIONS.index(version) + 1}"
        return self._call(crash_after, self.switch_mod.cmd_apply, component=component_id,
                           to_root=str(to_root.resolve()), receipt=rid, window="default",
                           plan_sha256=self._plan_sha(component_id, version), confirm_within=confirm_within, spec=None)

    def confirm(self, txn, *, crash_after=None) -> ActionResult:
        return self._call(crash_after, self.switch_mod.cmd_confirm, txn=txn)

    def rollback_bare(self, component_id, *, crash_after=None) -> ActionResult:
        return self._call(crash_after, self.switch_mod.cmd_rollback, component=component_id, txn=None,
                           if_unconfirmed=False)

    def rollback_txn(self, txn, *, crash_after=None) -> ActionResult:
        return self._call(crash_after, self.switch_mod.cmd_rollback, component=None, txn=txn,
                           if_unconfirmed=False)

    def timer_fire(self, txn, *, crash_after=None) -> ActionResult:
        return self._call(crash_after, self.switch_mod.cmd_rollback, component=None, txn=txn,
                           if_unconfirmed=True)

    def relink(self, component_id, *, crash_after=None) -> ActionResult:
        return self._call(crash_after, self.switch_mod.cmd_adopt, baseline=False, relink=True,
                           resync=None, reason=None, component=[component_id], spec=None)

    def resync(self, component_id, reason, *, crash_after=None) -> ActionResult:
        return self._call(crash_after, self.switch_mod.cmd_adopt, baseline=False, relink=False,
                           resync=component_id, reason=reason, component=None, spec=None)

    def recover(self, *, crash_after=None) -> ActionResult:
        return self._call(crash_after, self.switch_mod.cmd_recover)

    def external_drift_current_link(self, component_id: str, rng: random.Random):
        link_path = self.root / "current" / component_id
        if not link_path.is_symlink():
            return None
        before = os.readlink(link_path)
        version = rng.choice(VERSIONS)
        target = str((self.root / "tools" / f"{component_id}-{version}").resolve())
        link_path.unlink()
        link_path.symlink_to(target)
        return (f"current/{component_id}", before)

    def external_bypass_entrypoint(self, component_id: str, rng: random.Random):
        link_path = self.root / "bin" / component_id
        if not link_path.is_symlink():
            return None
        before = os.readlink(link_path)
        version = rng.choice(VERSIONS)
        target = str((self.root / "tools" / f"{component_id}-{version}" / "bin" / component_id).resolve())
        link_path.unlink()
        link_path.symlink_to(target)
        return (f"bin/{component_id}", before)


def _status_snapshot(switch_mod, root: Path, exclude: str) -> dict:
    state = switch_mod.load_state(root)
    return {txn: record.get("status") for txn, record in state["txns"].items() if txn != exclude}


def _dispatch(actions: Actions, rng: random.Random, name: str, known_txns: list[str],
              counters: dict) -> tuple:
    """Runs one named action with its own randomly-chosen parameters (and a randomly-chosen crash
    countdown roughly a third of the time, except ``crash_mid_rollback`` which forces its own).
    Returns ``(ActionResult-or-None, extra, acted_components)``: ``extra`` is
    ``(target_txn, before_snapshot)`` for a timer_fire/timer_fire_pending step (invariant (e)) or
    None; ``acted_components`` is the set of component ids this dispatch could plausibly have
    mutated (used by invariant (f) below) -- a single id for every component-scoped action, both
    ids for ``recover`` (which reconciles every component's txns in one call), and the specific
    txn's own component (if resolvable) for a txn-scoped action, or an empty set for a no-op."""
    switch_mod = actions.switch_mod
    root = actions.root
    crash_after = rng.randint(0, 7) if rng.random() < 0.35 else None

    def _status_of(txn):
        return switch_mod.load_state(root)["txns"].get(txn, {}).get("status")

    def _component_of(txn):
        component_id = switch_mod.load_state(root)["txns"].get(txn, {}).get("component")
        return {component_id} if component_id else frozenset()

    def _bucket(status):
        # Coordinator directive (round 9): "report ... invariant checks per state class (open,
        # pending, in_progress, rolled back)". Counts how many times a rollback-shaped or confirm
        # dispatch targeted a txn actually in each named class right before acting on it.
        if status is None:
            return
        if status in switch_mod.OPEN_TXN_STATUSES:
            counters["state_class_open"] += 1
        if status == "pending_confirmation":
            counters["state_class_pending"] += 1
        elif status == "in_progress":
            counters["state_class_in_progress"] += 1
        elif status == "rolled_back":
            counters["state_class_rolled_back"] += 1

    if name == "apply":
        component_id = rng.choice(COMPONENT_IDS)
        version = rng.choice(VERSIONS)
        confirm_within = rng.choice((None, None, 30, 300))
        result = actions.apply(component_id, version, crash_after=crash_after, confirm_within=confirm_within)
        if result.code == switch_mod.EXIT_BUSY:
            counters["busy_refusal"] += 1
        return result, None, {component_id}
    if name == "confirm":
        if not known_txns:
            return None, None, frozenset()
        txn = rng.choice(known_txns)
        _bucket(_status_of(txn))
        return actions.confirm(txn, crash_after=crash_after), None, _component_of(txn)
    if name == "rollback_bare":
        component_id = rng.choice(COMPONENT_IDS)
        return actions.rollback_bare(component_id, crash_after=crash_after), None, {component_id}
    if name == "rollback_txn":
        if not known_txns:
            return None, None, frozenset()
        txn = rng.choice(known_txns)
        _bucket(_status_of(txn))
        return actions.rollback_txn(txn, crash_after=crash_after), None, _component_of(txn)
    if name == "relink":
        component_id = rng.choice(COMPONENT_IDS)
        result = actions.relink(component_id, crash_after=crash_after)
        if result.code == switch_mod.EXIT_BUSY:
            counters["busy_refusal"] += 1
        return result, None, {component_id}
    if name == "resync":
        component_id = rng.choice(COMPONENT_IDS)
        return actions.resync(component_id, "model fuzz resync", crash_after=crash_after), None, {component_id}
    if name == "recover":
        return actions.recover(crash_after=crash_after), None, set(COMPONENT_IDS)
    if name == "timer_fire":
        if not known_txns:
            return None, None, frozenset()
        txn = rng.choice(known_txns)
        _bucket(_status_of(txn))
        before = _status_snapshot(switch_mod, root, exclude=txn)
        return actions.timer_fire(txn, crash_after=crash_after), (txn, before), _component_of(txn)
    if name == "timer_fire_pending":
        # Round 9: explicitly targets a txn that IS pending_confirmation right now (rather than
        # any known txn regardless of status), so the timer's real revert-or-no-op path actually
        # runs instead of only ever meeting an already-closed txn -- see this file's own module
        # docstring for why the round-8 per-step reconciliation made this otherwise unreachable.
        pending = [t for t, r in switch_mod.load_state(root)["txns"].items()
                   if r.get("status") == "pending_confirmation"]
        if not pending:
            return None, None, frozenset()
        txn = rng.choice(pending)
        counters["timer_fire_on_pending"] += 1
        _bucket("pending_confirmation")
        before = _status_snapshot(switch_mod, root, exclude=txn)
        return actions.timer_fire(txn, crash_after=crash_after), (txn, before), _component_of(txn)
    if name == "crash_mid_rollback":
        # Round 9: explicitly targets a currently-STANDING txn (applied/pending_confirmation/
        # in_progress -- i.e. one with real forward operations to reverse) and forces a small
        # crash countdown (0 or 1) guaranteed to land inside rollback_txn's own body -- right
        # after the load-bearing rollback:intent marker is durably written (0), or right after
        # the first reversed entry's own mutation+ledger-append lands (1) -- rather than leaving a
        # genuine mid-rollback crash to the same ~35% chance every other action gets, which could
        # otherwise go a whole run without ever crashing a txn that had anything to reverse yet.
        # Randomly via the timer (--if-unconfirmed) or a direct --txn call: both are real
        # production call paths into the same rollback_txn, and both deserve this coverage.
        standing = [t for t, r in switch_mod.load_state(root)["txns"].items()
                    if r.get("status") in switch_mod.STANDING_TXN_STATUSES]
        if not standing:
            return None, None, frozenset()
        txn = rng.choice(standing)
        _bucket(_status_of(txn))
        component = _component_of(txn)
        forced_crash = rng.choice((0, 1))
        caller = actions.timer_fire if rng.random() < 0.5 else actions.rollback_txn
        result = caller(txn, crash_after=forced_crash)
        if result.crashed:
            counters["crash_mid_rollback"] += 1
        return result, None, component
    if name == "external_drift":
        component_id = rng.choice(COMPONENT_IDS)
        if switch_mod.open_txn_for_component(root, component_id) is not None:
            counters["open_txn_plus_drift"] += 1
        actions.external_drift_current_link(component_id, rng)
        return None, None, {component_id}
    if name == "external_bypass":
        component_id = rng.choice(COMPONENT_IDS)
        if switch_mod.open_txn_for_component(root, component_id) is not None:
            counters["open_txn_plus_drift"] += 1
        actions.external_bypass_entrypoint(component_id, rng)
        return None, None, {component_id}
    raise AssertionError(f"unknown model action {name!r}")


# --------------------------------------------------------------------------------------
# Independent invariant checks (re-derived from raw ledger facts, not by calling the same
# helper functions rollback_txn/_superseding_txn use, so a bug in that shared logic cannot
# simply be reproduced -- and pass -- here too)
# --------------------------------------------------------------------------------------

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
    """True when ``txn`` has its own forward "link" entry on THIS SPECIFIC component's own
    current_link surface (``current/<component_id>``, exact match -- round 9 fix, found by this
    very redesign: with a single component, ``component_id`` was accepted but never actually
    checked against, since ``reconciled`` could never contain any OTHER component's txn either --
    dead code, harmlessly. With two components now sharing one ``recover()`` call, ``reconciled``
    can legitimately contain BOTH components' own txns in the same call, and the old, unscoped
    "any current/* link" check let a "bar" txn's own perfectly normal current/bar link entry
    incorrectly satisfy this guard for a "foo" invariant-(d) check, firing it even when nothing
    recover just did to "foo" specifically ever touched current/foo's ledger record at all --
    false-positive invariant (d) failures traced to this exact function, not to ecosystem-switch)."""
    surface = f"current/{component_id}"
    return any(entry.get("op") == "link" and entry.get("surface") == surface
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
    for every forward op kind, not one of the invariants this file enforces) has, correctly,
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


def assert_invariant_f(acted_components: frozenset, other_component: str, pre_open, post_open, name: str,
                        note: str) -> None:
    """Round 9: an action scoped to ``acted_components`` (never including ``other_component``)
    must never change ``other_component``'s own open-transaction state -- component isolation,
    the one property at-most-one-open-txn-per-component and the superseded-txn checks do not by
    themselves prove once two independent state machines start sharing a single ledger/root.
    ``recover`` is exempt at the call site below (it legitimately reconciles every component in
    one call, so it is never passed here with a narrower ``acted_components``)."""
    if pre_open != post_open:
        raise AssertionError(
            f"invariant (f) violated ({note}): action {name!r} scoped to {sorted(acted_components)!r} "
            f"changed component {other_component!r}'s own open-transaction state from {pre_open!r} "
            f"to {post_open!r}")


def _is_component_clean(switch_mod, root: Path, component_id: str) -> bool:
    return switch_mod.open_txn_for_component(root, component_id) is None


def reconcile_to_clean_state(switch_mod, actions: Actions, root: Path, component_id: str,
                              note: str, max_iterations: int = 8) -> None:
    """Invariant (a): from whatever state a sequence's random walk (crash injection, external
    drift) left `component_id` in, a bounded, documented operator sequence must always reach a
    clean one (``open_txn_for_component`` returns None -- no open or interrupted-rollback txn
    left). Tries, each pass: `recover`; then `confirm` (pending_confirmation) or `rollback --txn`
    (every other status) on whichever single txn `open_txn_for_component` still names (there is
    at most one, by construction: apply/relink refuse a second one while any is open -- see that
    function's own round-8 docstring). A refusal naming drift on a "link" surface is repaired by
    restoring that surface to what the STUCK txn's own ledger entry last set it to (the
    "investigate and fix it by hand" this tool's own drift refusals advise -- this model is the
    only source of drift in a closed test environment) and retried. Raises AssertionError -- a
    genuine invariant (a) failure -- on non-convergence, or on any refusal this function does not
    recognize as a repairable drift.

    Coordinator directive (round 9): called only once per component at the END of a sequence now
    (see AdoptionSwitchModelTests below), never after every individual step -- see this file's own
    module docstring for why the per-step version made several states this file is asked to
    exercise structurally unreachable. This function's own body needed one further round-9 fix
    beyond that (found BY this redesign, not merely a mechanical follow-on of it): the round-8
    repair strategy restored a drifted surface to the single most recent value recorded in a
    running ``drift_log`` of every external_drift/external_bypass call -- correct only when at
    most one out-of-band change ever lands on a given surface before a stuck txn's own rollback is
    attempted. Reconciling only at the end of a sequence (rather than after every step) lets many
    more such actions land on the SAME surface across many steps before reconciliation ever runs
    at all, so "the most recent drift_log entry" can itself be an INTERMEDIATE drifted value that
    still matches neither the stuck txn's own ``to`` nor ``from`` -- the repair then finds nothing
    left to restore on the very next pass (nothing in ``drift_log`` still differs from what is
    live) and raises invariant (a) instead of unwinding further back through the chain. Repairing
    directly from the stuck txn's OWN forward ledger entries below -- no drift history needed at
    all -- always targets exactly what THAT txn's own compare-and-swap check wants, regardless of
    how many out-of-band changes happened on top of it since: ``to`` (what the forward operation
    itself set) when this entry has not yet been reversed by an earlier, interrupted attempt at
    rolling back this SAME txn, or ``from`` (what that earlier, real reversal already set, before
    further drift knocked it away again) when it has -- a second round-9 fix, also found by this
    redesign: restoring to ``to`` unconditionally let a resumed rollback_txn call, which skips a
    (op, surface) key it already sees reversed in the ledger, close the txn "rolled_back" without
    ever re-touching the surface, leaving it at this repair's own value rather than the ledger's
    recorded post-reversal one -- the live/ledger mismatch invariant (d) exists to catch."""
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
        # Round 9 fix (found by this redesign, not a pre-existing gap this file exercised
        # before): a txn can be "pending_confirmation" (passes every earlier cmd_confirm status
        # check) while ALSO carrying an incomplete rollback marker -- a rollback:intent with no
        # matching rollback:done, from a timer_fire_pending/crash_mid_rollback call that started
        # reversing it and then crashed before finishing (exactly the new scenario round 9 asks
        # this file to reach). cmd_confirm's own OWN later check refuses that case explicitly
        # ("run 'rollback --txn' again to resume and finish reversing it before confirming"), so
        # branching on the raw status alone (as round 8's single-component version did, when this
        # combination was never actually reachable) tries `confirm` here, gets refused, and the
        # refusal message never matches this function's drift-repair branch below -- a spurious
        # invariant (a) failure, not a real one. Mirrors open_txn_for_component's own
        # has_incomplete_rollback derivation (not imported: a private local, so a bug in the
        # tool's own copy cannot also hide the bug here) to choose `rollback_txn` (resume/finish
        # it) instead, exactly as cmd_confirm's own error message advises.
        has_incomplete_rollback = record.get("status") != "rolled_back" and any(
            entry.get("op") == "rollback:intent" for entry in record.get("ops") or [])
        if not has_incomplete_rollback and record.get("status") == "pending_confirmation":
            result = actions.confirm(txn)
        else:
            result = actions.rollback_txn(txn)
        if result.ok:
            continue
        message = str(result.error) if result.error else ""
        if "no longer matches" in message or "drift" in message.lower():
            # This model's own external_drift/external_bypass actions are the only source of
            # drift in this closed test environment, and both only ever touch a "link" surface
            # (current/<id> or bin/<id>) -- never a text-replace/file-write one (no shipped
            # surfaces[] entry drives those through this model at all) -- so repairing every
            # "link" entry of the STUCK txn itself, whose live target currently matches neither
            # what this operation last set it to (``to``) nor what rolling it back would restore
            # (``from``), by putting it back to ``to`` (undoing only the extraneous out-of-band
            # change, never guessing at an unrelated drift history) is complete for what this
            # model can actually do to a surface.
            # An entry may already have been reversed for real by an EARLIER, interrupted attempt
            # at rolling back this same txn (rollback_txn's own resumability: a matching
            # "rollback:<op>" ledger entry already exists for this (op, surface) pair) before
            # further external_drift/external_bypass calls knocked the surface away from THAT
            # value too -- restoring such an entry to its forward ``to`` (as if nothing had been
            # reversed yet) would silently UNDO a real, already-ledgered reversal instead of
            # repairing drift, which a resumed rollback_txn call then trusts blindly (it skips a
            # (op, surface) key already in this set, per its own resumability contract) and closes
            # as "rolled_back" without ever re-touching the surface -- leaving it at whatever this
            # repair put there, not at the ledger's own recorded post-reversal value: exactly the
            # live/ledger mismatch invariant (d) exists to catch. The expected value is therefore
            # ``from`` (what reversing it already set, or should have) once already-reversed, and
            # ``to`` (what the forward operation itself set, undisturbed) otherwise -- the same
            # bare-(op, surface) key ecosystem-switch's own rollback_txn derives from
            # "rollback:"-prefixed entries (mirrored here, not imported, so a bug in the tool's own
            # derivation cannot also hide the bug here).
            already_reversed_keys = set()
            for candidate in switch_mod.Ledger(root).for_txn(txn):
                candidate_op = candidate.get("op")
                if not (isinstance(candidate_op, str) and candidate_op.startswith("rollback:")
                        and candidate_op not in ("rollback:done", "rollback:intent")):
                    continue
                bare_op = candidate_op[len("rollback:"):]
                if bare_op.endswith("-failed"):
                    bare_op = bare_op[: -len("-failed")]
                already_reversed_keys.add((bare_op, candidate.get("surface")))

            restored_any = False
            for entry in switch_mod.Ledger(root).for_txn(txn):
                if entry.get("op") != "link":
                    continue
                surface = entry.get("surface")
                if not surface:
                    continue
                link_path = root / surface
                live = os.readlink(link_path) if link_path.is_symlink() else None
                if live in (entry.get("to"), entry.get("from")):
                    continue  # not drifted (or already at the value this entry's own turn wants)
                expected = entry.get("from") if (entry.get("op"), surface) in already_reversed_keys \
                    else entry.get("to")
                if link_path.is_symlink():
                    link_path.unlink()
                if expected is not None:
                    link_path.symlink_to(expected)
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
        counters = {
            "timer_fire_on_pending": 0,
            "busy_refusal": 0,
            "open_txn_plus_drift": 0,
            "crash_mid_rollback": 0,
            "second_component_interleaved": 0,
            "state_class_open": 0,
            "state_class_pending": 0,
            "state_class_in_progress": 0,
            "state_class_rolled_back": 0,
        }

        for sequence_index in range(sequences):
            rng = random.Random(base_seed + sequence_index)
            sequence_dir = tmp_root / f"seq-{sequence_index}"
            sequence_dir.mkdir()
            root = _setup_root(sequence_dir)
            os.environ["ECO_INSTALL_ROOT"] = str(root)
            known_txns: list[str] = []

            with instrumented(switch_mod) as (injector, intent_violations):
                actions = Actions(switch_mod, root, injector)
                for step_index in range(steps_per_sequence):
                    total_steps += 1
                    name = rng.choices(ACTION_NAMES, weights=ACTION_WEIGHTS, k=1)[0]
                    note = f"seed {base_seed + sequence_index} step {step_index} action {name}"

                    pre_open = {cid: switch_mod.open_txn_for_component(root, cid) for cid in COMPONENT_IDS}
                    result, extra, acted = _dispatch(actions, rng, name, known_txns, counters)

                    if result is not None:
                        with contextlib.suppress(Exception):
                            state = switch_mod.load_state(root)
                            for txn in state["txns"]:
                                if txn not in known_txns:
                                    known_txns.append(txn)

                    if result is not None and not result.crashed and result.ok:
                        if name in ("rollback_bare", "rollback_txn", "timer_fire", "timer_fire_pending",
                                    "crash_mid_rollback"):
                            payload = result.payload or {}
                            if payload.get("status") == "rolled_back" and payload.get("txn"):
                                state = switch_mod.load_state(root)
                                txn_component = state["txns"].get(payload["txn"], {}).get("component") or "foo"
                                assert_invariant_b(switch_mod, root, txn_component, payload["txn"], note)
                        if name == "recover":
                            for component_id in COMPONENT_IDS:
                                _assert_invariant_d_if_recover_reconciled(switch_mod, root, component_id, result, note)
                        if name in ("timer_fire", "timer_fire_pending") and extra is not None:
                            target_txn, before_snapshot = extra
                            assert_invariant_e(switch_mod, root, target_txn, before_snapshot, note)

                    # Invariant (f) (round 9): whatever this step acted on, every OTHER component's
                    # own open-transaction state must be exactly what it was before this step --
                    # skipped for `recover`, which legitimately spans every component in one call.
                    post_open = {cid: switch_mod.open_txn_for_component(root, cid) for cid in COMPONENT_IDS}
                    if all(post_open[cid] is not None for cid in COMPONENT_IDS):
                        counters["second_component_interleaved"] += 1
                    if acted and acted != set(COMPONENT_IDS):
                        for other in COMPONENT_IDS:
                            if other in acted:
                                continue
                            assert_invariant_f(acted, other, pre_open[other], post_open[other], name, note)

                    # Invariant (a) is checked from *inside* reconcile_to_clean_state, called only
                    # at the end of the sequence below -- never after an individual step; see this
                    # file's own module docstring for why.

                # Coordinator directive (round 9): reconcile to a clean state only at the END of
                # each sequence, for every component, and assert it actually reaches one -- never
                # after every step, which would make several of the states/scenarios above
                # structurally unreachable from a LATER step (see module docstring).
                for component_id in COMPONENT_IDS:
                    reconcile_to_clean_state(switch_mod, actions, root, component_id,
                                              note=f"seed {base_seed + sequence_index} end-of-sequence {component_id}")
                    self.assertTrue(
                        _is_component_clean(switch_mod, root, component_id),
                        f"seed {base_seed + sequence_index}: component {component_id!r} was not clean "
                        "after end-of-sequence reconciliation")

                total_crashes += injector.injected
                all_intent_violations.extend(intent_violations)

        self.assertEqual(
            all_intent_violations, [],
            "invariant (c) violated: rollback:intent was written for a txn whose rollback call "
            "ultimately raised SwitchError (a clean refusal) -- see rollback_txn's round-8 reordering")

        # Coordinator directive (round 9): "assert visit counters ... are above 0" (the round-9
        # review's own wording) for every scenario this round's redesign was specifically asked to
        # make reachable again -- a future change that silently makes one of these unreachable
        # (the exact regression the round-8 per-step reconciliation caused, undetected for a whole
        # round) now fails this test directly instead of hiding behind an unrelated 0-violation
        # count over steps that never touched the scenario at all.
        for key in HARD_GATED_COUNTERS:
            self.assertGreater(
                counters[key], 0,
                f"model coverage gap: {key!r} was never exercised across {sequences} sequences x "
                f"{steps_per_sequence} steps -- the model must actually reach this state class/"
                "scenario, not merely avoid crashing while never reaching it")

        summary = (f"model test: {sequences} sequences x {steps_per_sequence} steps = {total_steps} "
                   f"total steps, {total_crashes} simulated crashes injected (seed {base_seed}); "
                   f"coverage counters: {json.dumps(counters, sort_keys=True)}")
        print(summary, file=sys.stderr)
        self.summary = summary  # exposed for a caller that wants it without parsing stderr


if __name__ == "__main__":
    unittest.main()
