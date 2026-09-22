"""Selector state-machine, invariants, registry validation and wiring tests.

Evidence class SYN: no broker connection is made anywhere in this file.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(ENGINE))  # runner.py/strategies.py import sibling engine modules


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ENGINE / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SEL = load("adaptive_selector", "selector.py")
STRAT = load("adaptive_strategies_wired", "strategies.py")
RUNNER = load("adaptive_runner_registry", "runner.py")


def inputs(**overrides):
    defaults = dict(timestamp=1000.0, regime="trend", warmed_up=True,
                     operational=SEL.OperationalStatus.clear(), candidate_id="v1",
                     confidence=0.9, advantage_bps=0.0)
    defaults.update(overrides)
    return SEL.DecisionInputs(**defaults)


class V1Spec:
    """Minimal StrategySpec stand-in for the single shipped pool member."""
    id = "adaptive_policy_v1"
    receipt_sha256 = "0" * 64
    sessions = ("regular",)
    regime_affinity = ("trend", "range")

    def propose(self, decision_inputs):
        return {}


class FakeSelector:
    """Always returns a canned SelectionDecision, so strategies.AdaptivePolicy's
    consumption of it (allow_entries gating, liquidate -> force_exit) can be
    tested independently of RegimeSelector's own state-machine gating."""
    def __init__(self, decision):
        self.decision = decision

    def decide(self, decision_inputs):
        return self.decision


class SelectorStateMachineTests(unittest.TestCase):
    def config(self, **changes):
        defaults = dict(confidence_threshold=0.6, minimum_advantage_bps=5,
                         entry_hysteresis=2, exit_hysteresis=0.1,
                         persistence_bars=2, minimum_residence_s=10, cooldown_s=5)
        defaults.update(changes)
        return SEL.SelectorConfig(**defaults)

    def activate(self, selector, candidate="v1", start=1000.0, step=1.0, confidence=0.9):
        """Drive a fresh selector to ACTIVE on `candidate`; returns last timestamp used."""
        t = start
        for _ in range(selector.config.persistence_bars):
            d = selector.decide(inputs(timestamp=t, candidate_id=candidate, confidence=confidence))
            t += step
        self.assertEqual(d.new_state, SEL.ACTIVE)
        return t - step

    def test_warming_when_not_warmed_up(self):
        selector = SEL.RegimeSelector(self.config())
        d = selector.decide(inputs(warmed_up=False, regime="unavailable"))
        self.assertEqual(d.new_state, SEL.WARMING)
        self.assertEqual(d.prior_state, SEL.WARMING)

    def test_operational_block_forces_no_new_risk_regardless_of_regime(self):
        selector = SEL.RegimeSelector(self.config())
        self.activate(selector)
        for block in (
            SEL.OperationalStatus(kill_switch=True),
            SEL.OperationalStatus(risk_halted=True),
            SEL.OperationalStatus(transport_frozen=True),
            SEL.OperationalStatus(reconciled=False),
            SEL.OperationalStatus(state_fresh=False),
        ):
            with self.subTest(block=block):
                d = selector.decide(inputs(timestamp=2000.0, regime="trend", confidence=1.0,
                                            advantage_bps=1000, operational=block))
                self.assertEqual(d.new_state, SEL.NO_NEW_RISK)
                self.assertTrue(d.blocked_by)

    def test_first_activation_requires_persistence(self):
        selector = SEL.RegimeSelector(self.config(persistence_bars=3))
        d1 = selector.decide(inputs(timestamp=1000.0, candidate_id="v1", confidence=0.9))
        d2 = selector.decide(inputs(timestamp=1001.0, candidate_id="v1", confidence=0.9))
        self.assertEqual(d1.new_state, SEL.HOLD)
        self.assertEqual(d2.new_state, SEL.HOLD)
        d3 = selector.decide(inputs(timestamp=1002.0, candidate_id="v1", confidence=0.9))
        self.assertEqual(d3.new_state, SEL.ACTIVE)
        self.assertEqual(d3.incumbent_id, "v1")

    def test_below_confidence_threshold_never_activates(self):
        selector = SEL.RegimeSelector(self.config())
        d = selector.decide(inputs(candidate_id="v1", confidence=0.1))
        self.assertEqual(d.new_state, SEL.NO_NEW_RISK)
        self.assertIsNone(selector.incumbent_id)

    def test_no_candidate_never_activates(self):
        selector = SEL.RegimeSelector(self.config())
        d = selector.decide(inputs(candidate_id=None, confidence=0.9))
        self.assertEqual(d.new_state, SEL.NO_NEW_RISK)

    def test_active_requires_confidence_and_advantage_and_persistence_and_residence_and_cooldown(self):
        # persistence_bars=1 isolates the confidence/advantage/residence/cooldown
        # gates one at a time; switch persistence itself is covered by
        # test_switch_requires_persistence_bars below.
        selector = SEL.RegimeSelector(self.config(persistence_bars=1, minimum_residence_s=20))
        self.activate(selector, candidate="v1", start=1000.0)  # incumbent_since == 1001
        # Enough confidence but not enough advantage: HOLD.
        d = selector.decide(inputs(timestamp=1005.0, candidate_id="v2", confidence=0.9, advantage_bps=1))
        self.assertEqual(d.new_state, SEL.HOLD)
        self.assertIn("advantage_below_hysteresis", d.reason_codes)
        # Enough advantage but not enough confidence: HOLD.
        d = selector.decide(inputs(timestamp=1006.0, candidate_id="v2", confidence=0.2, advantage_bps=50))
        self.assertEqual(d.new_state, SEL.HOLD)
        self.assertIn("confidence_below_threshold", d.reason_codes)
        # Enough confidence/advantage (persistence_bars=1 so persistence is
        # satisfied on the first qualifying bar) but residence not yet
        # satisfied: 1010 - 1001 == 9 < 20.
        d = selector.decide(inputs(timestamp=1010.0, candidate_id="v2", confidence=0.9, advantage_bps=50))
        self.assertEqual(d.new_state, SEL.HOLD)
        self.assertIn("incumbent_residence_not_satisfied", d.reason_codes)
        self.assertNotIn("persistence_pending", d.reason_codes)
        # Residence now satisfied (1021 - 1001 == 20 >= 20): switch.
        d = selector.decide(inputs(timestamp=1021.0, candidate_id="v2", confidence=0.9, advantage_bps=50))
        self.assertEqual(d.new_state, SEL.ACTIVE)
        self.assertEqual(d.incumbent_id, "v2")
        self.assertEqual(selector.incumbent_id, "v2")

    def test_switch_requires_persistence_bars(self):
        selector = SEL.RegimeSelector(self.config(persistence_bars=2, minimum_residence_s=0, cooldown_s=0))
        self.activate(selector, candidate="v1", start=1000.0)
        d = selector.decide(inputs(timestamp=1005.0, candidate_id="v2", confidence=0.9, advantage_bps=50))
        self.assertEqual(d.new_state, SEL.HOLD)
        self.assertIn("persistence_pending", d.reason_codes)
        d = selector.decide(inputs(timestamp=1006.0, candidate_id="v2", confidence=0.9, advantage_bps=50))
        self.assertEqual(d.new_state, SEL.ACTIVE)
        self.assertEqual(d.incumbent_id, "v2")

    def test_non_consecutive_qualifying_bars_do_not_accumulate_persistence(self):
        selector = SEL.RegimeSelector(self.config(persistence_bars=2, minimum_residence_s=0, cooldown_s=0))
        self.activate(selector, candidate="v1", start=1000.0)
        d = selector.decide(inputs(timestamp=1005.0, candidate_id="v2", confidence=0.9, advantage_bps=50))
        self.assertEqual(d.new_state, SEL.HOLD)
        # A non-qualifying bar in between resets the persistence streak.
        d = selector.decide(inputs(timestamp=1006.0, candidate_id="v2", confidence=0.9, advantage_bps=1))
        self.assertEqual(d.new_state, SEL.HOLD)
        d = selector.decide(inputs(timestamp=1007.0, candidate_id="v2", confidence=0.9, advantage_bps=50))
        self.assertEqual(d.new_state, SEL.HOLD)
        self.assertIn("persistence_pending", d.reason_codes)
        d = selector.decide(inputs(timestamp=1008.0, candidate_id="v2", confidence=0.9, advantage_bps=50))
        self.assertEqual(d.new_state, SEL.ACTIVE)

    def test_cooldown_blocks_immediate_re_switch(self):
        selector = SEL.RegimeSelector(self.config(persistence_bars=1, minimum_residence_s=0, cooldown_s=1))
        self.activate(selector, candidate="v1", start=1000.0)  # incumbent_since == last_switch_at == 1001
        # Enough time since v1's activation for the cooldown gate: switch to v2.
        d = selector.decide(inputs(timestamp=1002.0, candidate_id="v2", confidence=0.9, advantage_bps=50))
        self.assertEqual(d.new_state, SEL.ACTIVE)
        self.assertEqual(d.incumbent_id, "v2")
        # Immediately try to switch back to v1: cooldown since the v2 switch blocks it.
        d = selector.decide(inputs(timestamp=1002.5, candidate_id="v1", confidence=0.9, advantage_bps=50))
        self.assertEqual(d.new_state, SEL.HOLD)
        self.assertIn("cooldown_not_elapsed", d.reason_codes)
        self.assertEqual(selector.incumbent_id, "v2")

    def test_never_liquidates_on_switch_by_default(self):
        selector = SEL.RegimeSelector(self.config(minimum_residence_s=0, cooldown_s=0))
        self.activate(selector, candidate="v1", start=1000.0)
        d1 = selector.decide(inputs(timestamp=1001.0, candidate_id="v2", confidence=0.9, advantage_bps=50))
        d2 = selector.decide(inputs(timestamp=1002.0, candidate_id="v2", confidence=0.9, advantage_bps=50))
        self.assertEqual(d2.new_state, SEL.ACTIVE)
        self.assertFalse(d1.liquidate)
        self.assertFalse(d2.liquidate)

    def test_flatten_before_switch_policy_sets_liquidate_only_on_switch(self):
        selector = SEL.RegimeSelector(self.config(minimum_residence_s=0, cooldown_s=0,
                                                    portfolio_transition_policy=SEL.FLATTEN_BEFORE_SWITCH))
        self.activate(selector, candidate="v1", start=1000.0)
        d1 = selector.decide(inputs(timestamp=1001.0, candidate_id="v2", confidence=0.9, advantage_bps=50))
        self.assertFalse(d1.liquidate)
        d2 = selector.decide(inputs(timestamp=1002.0, candidate_id="v2", confidence=0.9, advantage_bps=50))
        self.assertEqual(d2.new_state, SEL.ACTIVE)
        self.assertTrue(d2.liquidate)

    def test_deterministic_given_identical_inputs_no_wall_clock(self):
        cfg = self.config()
        a, b = SEL.RegimeSelector(cfg), SEL.RegimeSelector(cfg)
        sequence = [inputs(timestamp=1000.0 + i, candidate_id="v1", confidence=0.9) for i in range(5)]
        results_a = [a.decide(i) for i in sequence]
        results_b = [b.decide(i) for i in sequence]
        self.assertEqual(results_a, results_b)

    def test_exit_hysteresis_holds_rather_than_flips_on_minor_confidence_dip(self):
        selector = SEL.RegimeSelector(self.config(exit_hysteresis=0.2))
        self.activate(selector, candidate="v1", start=1000.0)
        d = selector.decide(inputs(timestamp=1010.0, candidate_id="v1", confidence=0.45))
        self.assertEqual(d.new_state, SEL.ACTIVE)
        d = selector.decide(inputs(timestamp=1011.0, candidate_id="v1", confidence=0.3))
        self.assertEqual(d.new_state, SEL.HOLD)
        self.assertEqual(selector.incumbent_id, "v1")

    def test_invalid_config_rejected(self):
        with self.assertRaises(ValueError):
            SEL.SelectorConfig(confidence_threshold=1.5)
        with self.assertRaises(ValueError):
            SEL.SelectorConfig(persistence_bars=0)
        with self.assertRaises(ValueError):
            SEL.SelectorConfig(portfolio_transition_policy="delete_everything")


class RegistryValidationTests(unittest.TestCase):
    """All scratch registries/modules live under a fresh tempfile.TemporaryDirectory
    per test (never under the tracked tests/fixtures tree)."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def write(self, name, content):
        path = self.tmp / name
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content)
        return path

    def pin_module(self, name, content: bytes):
        """Write `name`.py plus a source-hashes.json that pins it, matching
        load_registry's "already reviewed and hash-pinned" requirement. Uses
        the bare "name.py" key form (prefix ""), which load_registry falls
        back to when no "*/runner.py" key is present."""
        self.write(f"{name}.py", content)
        digest = hashlib.sha256(content).hexdigest()
        self.write("source-hashes.json", json.dumps({f"{name}.py": digest}))
        return digest

    def write_registry(self, entries, **top):
        payload = {"schema_version": 1, "strategies": entries, **top}
        return self.write("registry.json", json.dumps(payload))

    def valid_entry(self, *, id="a", module="mod", receipt=b"{}", **overrides):
        self.pin_module(module, b"x = 1\n")
        receipt_path = self.write("receipt.json", receipt)
        entry = {"id": id, "module": module, "receipt_path": "receipt.json",
                  "receipt_sha256": hashlib.sha256(receipt).hexdigest(),
                  "evidence_class": "SYN", "sessions": ["regular"], "enabled": True}
        entry.update(overrides)
        return entry

    def test_shipped_registry_is_valid(self):
        entries = RUNNER.load_registry(ENGINE / "registry.json")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["id"], "adaptive_policy_v1")

    def test_never_executes_module_code(self):
        """A registry module that would raise/have side effects if imported
        must still validate cleanly: load_registry only ast.parse()s it and
        checks its sha256 pin, it never execs the file (D1)."""
        marker = self.tmp / "executed.marker"
        content = f"import pathlib; pathlib.Path({str(marker)!r}).write_text('x')\n".encode()
        self.pin_module("sideeffect", content)
        receipt_path = self.write("receipt.json", b"{}")
        entry = {"id": "a", "module": "sideeffect", "receipt_path": "receipt.json",
                  "receipt_sha256": hashlib.sha256(b"{}").hexdigest(),
                  "evidence_class": "SYN", "sessions": ["regular"], "enabled": True}
        path = self.write_registry([entry])
        RUNNER.load_registry(path)  # must not raise
        self.assertFalse(marker.exists(), "load_registry executed the registry module")

    def test_bad_schema_version_rejected(self):
        path = self.write_registry([], schema_version=2)
        with self.assertRaises(ValueError):
            RUNNER.load_registry(path)

    def test_empty_strategies_rejected(self):
        path = self.write_registry([])
        with self.assertRaises(ValueError):
            RUNNER.load_registry(path)

    def test_duplicate_ids_rejected(self):
        entry = self.valid_entry(id="dup")
        path = self.write_registry([entry, entry])
        with self.assertRaises(ValueError):
            RUNNER.load_registry(path)

    def test_invalid_identifier_characters_rejected(self):
        entry = self.valid_entry(id="not a valid id!")
        path = self.write_registry([entry])
        with self.assertRaises(ValueError):
            RUNNER.load_registry(path)

    def test_invalid_module_name_characters_rejected(self):
        self.pin_module("mod", b"x = 1\n")
        receipt = self.write("receipt.json", b"{}")
        entry = {"id": "a", "module": "not a module!", "receipt_path": "receipt.json",
                  "receipt_sha256": hashlib.sha256(b"{}").hexdigest(),
                  "evidence_class": "SYN", "sessions": ["regular"], "enabled": True}
        path = self.write_registry([entry])
        with self.assertRaises(ValueError):
            RUNNER.load_registry(path)

    def test_missing_receipt_file_rejected(self):
        self.pin_module("mod", b"x = 1\n")
        entry = {"id": "a", "module": "mod", "receipt_path": "missing.json",
                  "receipt_sha256": "0" * 64, "evidence_class": "SYN", "sessions": ["regular"], "enabled": True}
        path = self.write_registry([entry])
        with self.assertRaises(ValueError):
            RUNNER.load_registry(path)

    def test_receipt_hash_mismatch_rejected(self):
        self.pin_module("mod", b"x = 1\n")
        self.write("receipt.json", b'{"a": 1}')
        entry = {"id": "a", "module": "mod", "receipt_path": "receipt.json",
                  "receipt_sha256": "0" * 64, "evidence_class": "SYN", "sessions": ["regular"], "enabled": True}
        path = self.write_registry([entry])
        with self.assertRaises(ValueError):
            RUNNER.load_registry(path)

    def test_missing_module_file_rejected(self):
        receipt = self.write("receipt.json", b"{}")
        entry = {"id": "a", "module": "no_such_module", "receipt_path": "receipt.json",
                  "receipt_sha256": hashlib.sha256(b"{}").hexdigest(),
                  "evidence_class": "SYN", "sessions": ["regular"], "enabled": True}
        path = self.write_registry([entry])
        with self.assertRaises(ValueError):
            RUNNER.load_registry(path)

    def test_module_with_invalid_syntax_rejected(self):
        # ast.parse must reject this; load_registry never execs it (D1), so a
        # module that would only fail at import time is not what this tests --
        # see test_module_not_pinned_rejected/test_module_hash_mismatch_rejected
        # for the exec-free pin checks that replace the old import-based check.
        self.write("broken.py", "def f(:\n")
        self.write("source-hashes.json", json.dumps({"broken.py": "0" * 64}))
        receipt = self.write("receipt.json", b"{}")
        entry = {"id": "a", "module": "broken", "receipt_path": "receipt.json",
                  "receipt_sha256": hashlib.sha256(b"{}").hexdigest(),
                  "evidence_class": "SYN", "sessions": ["regular"], "enabled": True}
        path = self.write_registry([entry])
        with self.assertRaises(ValueError):
            RUNNER.load_registry(path)

    def test_module_not_pinned_rejected(self):
        self.write("mod.py", "x = 1\n")  # no source-hashes.json at all
        receipt = self.write("receipt.json", b"{}")
        entry = {"id": "a", "module": "mod", "receipt_path": "receipt.json",
                  "receipt_sha256": hashlib.sha256(b"{}").hexdigest(),
                  "evidence_class": "SYN", "sessions": ["regular"], "enabled": True}
        path = self.write_registry([entry])
        with self.assertRaises(ValueError):
            RUNNER.load_registry(path)

    def test_module_hash_mismatch_rejected(self):
        self.write("mod.py", "x = 1\n")
        # Pin a hash that does not match the actual file content.
        self.write("source-hashes.json", json.dumps({"mod.py": "0" * 64}))
        receipt = self.write("receipt.json", b"{}")
        entry = {"id": "a", "module": "mod", "receipt_path": "receipt.json",
                  "receipt_sha256": hashlib.sha256(b"{}").hexdigest(),
                  "evidence_class": "SYN", "sessions": ["regular"], "enabled": True}
        path = self.write_registry([entry])
        with self.assertRaises(ValueError):
            RUNNER.load_registry(path)

    def test_receipt_path_escaping_registry_directory_rejected(self):
        self.pin_module("mod", b"x = 1\n")
        entry = {"id": "a", "module": "mod", "receipt_path": "../../etc/passwd",
                  "receipt_sha256": "0" * 64, "evidence_class": "SYN", "sessions": ["regular"], "enabled": True}
        path = self.write_registry([entry])
        with self.assertRaises(ValueError):
            RUNNER.load_registry(path)

    def test_invalid_evidence_class_rejected(self):
        entry = self.valid_entry(evidence_class="LIVE")
        path = self.write_registry([entry])
        with self.assertRaises(ValueError):
            RUNNER.load_registry(path)

    def _write_golden_repo_shape(self, *, fixture_sha_correct, case_count):
        """Build a minimal repo-shaped tempdir (engine dir 2 levels under a
        root, tests/fixtures/ sibling of blueprints/) so load_registry's
        repo-root-relative golden_fixture resolution (source_dir.parents[2])
        works exactly as it does for the real repository."""
        root = self.tmp
        engine_dir = root / "blueprints" / "us-equities" / "adaptive-paper"
        engine_dir.mkdir(parents=True)
        fixtures_dir = root / "tests" / "fixtures"
        fixtures_dir.mkdir(parents=True)
        module_bytes = b"x = 1\n"
        (engine_dir / "mod.py").write_bytes(module_bytes)
        module_digest = hashlib.sha256(module_bytes).hexdigest()
        (engine_dir / "source-hashes.json").write_text(json.dumps({
            "blueprints/us-equities/adaptive-paper/runner.py": "0" * 64,
            "blueprints/us-equities/adaptive-paper/mod.py": module_digest,
        }))
        fixture_bytes = json.dumps({f"case{i}": i for i in range(2)}).encode()
        (fixtures_dir / "golden.json").write_bytes(fixture_bytes)
        actual_fixture_sha = hashlib.sha256(fixture_bytes).hexdigest()
        receipt = {
            "kind": "golden_decision_fixture",
            "golden_fixture": "tests/fixtures/golden.json",
            "golden_fixture_sha256": actual_fixture_sha if fixture_sha_correct else "0" * 64,
            "case_count": case_count,
        }
        receipt_bytes = json.dumps(receipt).encode()
        (engine_dir / "receipt.json").write_bytes(receipt_bytes)
        entry = {"id": "a", "module": "mod", "receipt_path": "receipt.json",
                  "receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
                  "evidence_class": "SYN", "sessions": ["regular"], "enabled": True}
        registry_path = engine_dir / "registry.json"
        registry_path.write_text(json.dumps({"schema_version": 1, "strategies": [entry]}))
        return registry_path

    def test_golden_fixture_receipt_hash_mismatch_rejected(self):
        path = self._write_golden_repo_shape(fixture_sha_correct=False, case_count=2)
        with self.assertRaises(ValueError):
            RUNNER.load_registry(path)

    def test_golden_fixture_receipt_case_count_mismatch_rejected(self):
        path = self._write_golden_repo_shape(fixture_sha_correct=True, case_count=99)
        with self.assertRaises(ValueError):
            RUNNER.load_registry(path)

    def test_golden_fixture_receipt_matching_sha_and_case_count_accepted(self):
        path = self._write_golden_repo_shape(fixture_sha_correct=True, case_count=2)
        entries = RUNNER.load_registry(path)
        self.assertEqual(len(entries), 1)

    def test_load_config_refuses_when_pointed_at_a_malformed_registry(self):
        path = self.write_registry("not-a-list")
        with self.assertRaises(ValueError):
            RUNNER.load_config(ENGINE / "config.json", registry_path=path)

    def test_load_config_accepts_the_shipped_registry_via_explicit_path(self):
        config, risk, policy = RUNNER.load_config(ENGINE / "config.json", registry_path=ENGINE / "registry.json")
        self.assertEqual(policy.max_leverage, 1)


class AdaptivePolicyWiringTests(unittest.TestCase):
    def policy_config(self, **changes):
        return STRAT.PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"),
                                   max_positions=6, **changes)

    def feed(self, policy, prices, *, benchmark_slope=0, start=1000):
        for i, price in enumerate(prices):
            for s in policy.config.symbols:
                p = 100 + benchmark_slope * i if s in policy.config.benchmarks else price
                policy.observe(s, p - .005, p + .005, start + i)
        return start + len(prices) - 1

    def test_default_empty_pool_matches_golden_fixture(self):
        golden = json.loads((ENGINE / "receipts" / "adaptive_policy_v1.golden.json").read_text())
        policy = STRAT.AdaptivePolicy(self.policy_config())
        now = self.feed(policy, [100 + i * .04 for i in range(40)], benchmark_slope=.015)
        d = policy.decide(now)
        self.assertEqual(d.regime, golden["trend"]["regime"])
        self.assertEqual({k: str(v) for k, v in d.targets.items()}, golden["trend"]["targets"])

    def test_selector_active_state_allows_entries_hold_state_blocks_new_entries(self):
        config = SEL.SelectorConfig(confidence_threshold=0.9, minimum_advantage_bps=5,
                                     entry_hysteresis=2, exit_hysteresis=0.1, persistence_bars=5,
                                     minimum_residence_s=0, cooldown_s=0)
        selector = SEL.RegimeSelector(config)
        policy = STRAT.AdaptivePolicy(self.policy_config(), strategy_pool=(V1Spec(),), selector=selector)
        now = self.feed(policy, [100 + i * .04 for i in range(40)], benchmark_slope=.015)
        d = policy.decide(now)
        # Persistence not yet satisfied (1 bar so far, need 5): selector HOLDs,
        # so no new entries are proposed despite a qualifying trend regime.
        self.assertEqual(policy.last_selector_decision.new_state, SEL.HOLD)
        self.assertEqual(d.targets, {})

    def test_selector_with_empty_pool_is_refused_at_construction(self):
        # D9: a selector with nothing to select from would block entries
        # forever (no candidate_id is ever proposed); refuse eagerly instead.
        with self.assertRaises(ValueError):
            STRAT.AdaptivePolicy(self.policy_config(), strategy_pool=(),
                                  selector=SEL.RegimeSelector(SEL.SelectorConfig()))

    def _seeded_policy(self, selector):
        """A policy with an AAPL holding and a fresh, benign quote for it (no
        stop/take-profit/trailing/time-exit condition is close to firing), so
        any exit that does appear in the next decide() must come from the
        selector's liquidate flag, not the ordinary exit chain."""
        policy = STRAT.AdaptivePolicy(self.policy_config(), strategy_pool=(V1Spec(),), selector=selector)
        now = self.feed(policy, [100 + i * .04 for i in range(40)], benchmark_slope=.015)
        policy.sync_positions({"AAPL": {"qty": 1, "avg_entry_price": "101"}}, now)
        quote_time = now + 2
        policy.observe("AAPL", 100.995, 101.005, quote_time)
        return policy, quote_time

    def test_operational_block_state_change_emits_no_exit_and_leaves_holdings_and_targets_untouched(self):
        selector = SEL.RegimeSelector(SEL.SelectorConfig(confidence_threshold=0.6, minimum_advantage_bps=5,
                                                          entry_hysteresis=2, exit_hysteresis=0.1,
                                                          persistence_bars=1, minimum_residence_s=0, cooldown_s=0))
        policy, quote_time = self._seeded_policy(selector)
        holding = policy.holdings["AAPL"]
        snapshot = (holding.quantity, holding.average_price, holding.entered_at)
        d = policy.decide(quote_time, operational=SEL.OperationalStatus(kill_switch=True))
        self.assertEqual(policy.last_selector_decision.new_state, SEL.NO_NEW_RISK)
        self.assertFalse(policy.last_selector_decision.liquidate)
        # The actual observable invariant: no exit order for AAPL, its target
        # quantity is unchanged, and the Holding record itself is untouched --
        # not merely "the key is still present" (decide() never deletes from
        # self.holdings regardless; only sync_positions does).
        self.assertNotIn("AAPL", d.exits)
        self.assertEqual(d.targets.get("AAPL"), holding.quantity)
        self.assertEqual((holding.quantity, holding.average_price, holding.entered_at), snapshot)

    def test_liquidate_false_never_forces_an_exit_on_a_state_change(self):
        decision = SEL.SelectionDecision(timestamp=0, prior_state=SEL.HOLD, new_state=SEL.ACTIVE,
                                          regime="trend", confidence=1.0, advantage_bps=0.0,
                                          incumbent_id="adaptive_policy_v1", candidate_id="adaptive_policy_v1",
                                          reason_codes=("switched",), blocked_by=(), liquidate=False)
        policy, quote_time = self._seeded_policy(FakeSelector(decision))
        d = policy.decide(quote_time)
        self.assertNotIn("AAPL", d.exits)
        self.assertEqual(d.targets.get("AAPL"), policy.holdings["AAPL"].quantity)

    def test_liquidate_true_is_the_only_path_that_forces_an_exit_via_the_existing_exit_chain(self):
        # D4/D6: FLATTEN_BEFORE_SWITCH's effect (liquidate=True) must be
        # consumed by routing through _decide_core's existing force_exit path
        # -- no new order type -- but with a distinct reason, "rotation_flatten",
        # so this decision event (and any order tag built from it) is
        # distinguishable from an actual end-of-trial "trial_end" exit.
        decision = SEL.SelectionDecision(timestamp=0, prior_state=SEL.HOLD, new_state=SEL.ACTIVE,
                                          regime="trend", confidence=1.0, advantage_bps=50.0,
                                          incumbent_id="adaptive_policy_v1", candidate_id="adaptive_policy_v1",
                                          reason_codes=("switched",), blocked_by=(), liquidate=True)
        policy, quote_time = self._seeded_policy(FakeSelector(decision))
        d = policy.decide(quote_time)
        self.assertEqual(d.exits.get("AAPL"), "rotation_flatten")
        self.assertNotIn("AAPL", d.targets)


def _entry(id="adaptive_policy_v1", *, enabled=True, sessions=("regular",), evidence_class="SYN"):
    return {"id": id, "module": "strategies_v1", "receipt_path": "adaptive_policy_v1.receipt.json",
            "receipt_sha256": "0" * 64, "evidence_class": evidence_class,
            "sessions": list(sessions), "enabled": enabled}


class RotationConfigTests(unittest.TestCase):
    """Gap-closing: config["rotation"] is opt-in and off by default; the on
    path builds a real strategy_pool/RegimeSelector from validated registry
    entries. These use fake/synthetic registry entry dicts (not load_registry
    itself, which RegistryValidationTests already covers) to isolate
    strategy_pool_and_selector's own logic."""

    def test_off_by_default_returns_empty_pool_and_no_selector(self):
        pool, selector = RUNNER.strategy_pool_and_selector({}, [_entry()])
        self.assertEqual(pool, ())
        self.assertIsNone(selector)
        pool, selector = RUNNER.strategy_pool_and_selector({"rotation": {"enabled": False}}, [_entry()])
        self.assertEqual(pool, ())
        self.assertIsNone(selector)

    def test_shipped_config_json_is_off_and_golden_unchanged(self):
        # The real shipped config.json (rotation.enabled: false) must resolve
        # to the exact same off-path inputs used everywhere else in this file.
        raw = json.loads((ENGINE / "config.json").read_text())
        self.assertEqual(raw["rotation"], {"enabled": False})
        entries = RUNNER.load_registry(ENGINE / "registry.json")
        pool, selector = RUNNER.strategy_pool_and_selector(raw, entries)
        self.assertEqual(pool, ())
        self.assertIsNone(selector)
        # AdaptivePolicy built from that (pool, selector) takes the exact
        # byte-identical v1 path (see test_default_empty_pool_matches_golden_fixture).
        policy = STRAT.AdaptivePolicy(STRAT.PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"),
                                                          max_positions=6),
                                       strategy_pool=pool, selector=selector)
        self.assertEqual(policy.strategy_pool, ())
        self.assertIsNone(policy.selector)

    def test_enabled_builds_pool_honouring_enabled_and_sessions(self):
        entries = [_entry("a", enabled=True, sessions=("regular",), evidence_class="HIST"),
                   _entry("b", enabled=False, sessions=("regular",), evidence_class="HIST"),
                   _entry("c", enabled=True, sessions=("extended",), evidence_class="HIST")]
        pool, selector = RUNNER.strategy_pool_and_selector(
            {"rotation": {"enabled": True, "selector": {"persistence_bars": 2}}}, entries, session="regular")
        self.assertEqual([spec.id for spec in pool], ["a"])
        self.assertIsInstance(selector, STRAT.RegimeSelector)
        self.assertEqual(selector.config.persistence_bars, 2)

    def test_synthetic_only_pool_is_refused_without_allow_synthetic(self):
        # D2: rotation.enabled true with a pool whose members are all SYN
        # must refuse unless config rotation.allow_synthetic is explicitly true.
        entries = [_entry("a", evidence_class="SYN")]
        with self.assertRaises(ValueError):
            RUNNER.strategy_pool_and_selector({"rotation": {"enabled": True}}, entries)
        with self.assertRaises(ValueError):
            RUNNER.strategy_pool_and_selector({"rotation": {"enabled": True, "allow_synthetic": False}}, entries)

    def test_synthetic_only_pool_accepted_with_explicit_allow_synthetic(self):
        entries = [_entry("a", evidence_class="SYN")]
        pool, selector = RUNNER.strategy_pool_and_selector(
            {"rotation": {"enabled": True, "allow_synthetic": True}}, entries)
        self.assertEqual([spec.id for spec in pool], ["a"])
        self.assertIsInstance(selector, STRAT.RegimeSelector)

    def test_hist_and_paper_entries_are_always_eligible_regardless_of_allow_synthetic(self):
        for evidence_class in ("HIST", "PAPER"):
            with self.subTest(evidence_class=evidence_class):
                entries = [_entry("a", evidence_class=evidence_class)]
                pool, selector = RUNNER.strategy_pool_and_selector({"rotation": {"enabled": True}}, entries)
                self.assertEqual([spec.id for spec in pool], ["a"])

    def test_mixed_pool_with_at_least_one_non_synthetic_entry_does_not_need_allow_synthetic(self):
        entries = [_entry("a", evidence_class="SYN"), _entry("b", evidence_class="HIST")]
        pool, selector = RUNNER.strategy_pool_and_selector({"rotation": {"enabled": True}}, entries)
        self.assertEqual({spec.id for spec in pool}, {"a", "b"})

    def test_invalid_allow_synthetic_type_refused(self):
        with self.assertRaises(ValueError):
            RUNNER.strategy_pool_and_selector(
                {"rotation": {"enabled": True, "allow_synthetic": "yes"}}, [_entry(evidence_class="HIST")])

    def test_enabled_with_no_eligible_strategy_is_refused(self):
        entries = [_entry("a", enabled=False)]
        with self.assertRaises(ValueError):
            RUNNER.strategy_pool_and_selector({"rotation": {"enabled": True}}, entries)

    def test_invalid_rotation_shape_refused(self):
        with self.assertRaises(ValueError):
            RUNNER.strategy_pool_and_selector({"rotation": {"enabled": "not-a-bool"}}, [_entry()])
        with self.assertRaises(ValueError):
            RUNNER.strategy_pool_and_selector({"rotation": "not-a-dict"}, [_entry()])

    def test_invalid_selector_sub_config_refused(self):
        # R3: _entry() defaults to evidence_class="SYN"; without an explicit
        # allow_synthetic opt-in, strategy_pool_and_selector's all-SYN gate
        # ("rotation_enabled_with_only_synthetic_strategies") fires before
        # the selector sub-config is even parsed, so this used to pass for
        # the wrong reason. Set allow_synthetic True so the selector-shape
        # validation itself is what raises, and assert on its message.
        # A field with a valid name but out-of-range value fails SelectorConfig's
        # own __post_init__ with a ValueError, which strategy_pool_and_selector
        # does not wrap (only TypeError is caught) -- the specific message
        # propagates as-is.
        with self.assertRaises(ValueError) as caught:
            RUNNER.strategy_pool_and_selector(
                {"rotation": {"enabled": True, "allow_synthetic": True,
                              "selector": {"confidence_threshold": 5}}}, [_entry()])
        self.assertEqual(str(caught.exception), "invalid_confidence_threshold")
        # An unknown field name fails at the constructor call itself
        # (TypeError), which strategy_pool_and_selector wraps into the
        # generic invalid_rotation_selector_config.
        with self.assertRaises(ValueError) as caught:
            RUNNER.strategy_pool_and_selector(
                {"rotation": {"enabled": True, "allow_synthetic": True,
                              "selector": {"not_a_real_field": 1}}}, [_entry()])
        self.assertEqual(str(caught.exception), "invalid_rotation_selector_config")

    def test_load_config_validates_rotation_shape_eagerly(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            raw = json.loads((ENGINE / "config.json").read_text())
            raw["rotation"] = {"enabled": "not-a-bool"}
            config_path = root / "config.json"
            config_path.write_text(json.dumps(raw))
            with self.assertRaises(ValueError):
                RUNNER.load_config(config_path, registry_path=ENGINE / "registry.json")


if __name__ == "__main__":
    unittest.main()
