"""Synthetic fixtures for scripts/trading_gates.py (local integration; no receipts are replayed).

The live-go signature tests run the host's real ssh-keygen -Y sign/verify with
throwaway keys made in temporary directories; they skip on a host without
ssh-keygen, and no key or signature is committed."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import trading_gates  # noqa: E402

SSH_KEYGEN = shutil.which("ssh-keygen")
SIGNER = "live-go-signer"
NAMESPACE = "live-go@native-agent-stack"
LIVE_GO_MD = "docs/decisions/live-go.md"
LIVE_GO_SIG = "docs/decisions/live-go.md.sig"
LIVE_GO_SIGNERS = "docs/decisions/live-go.allowed_signers"


def gate(**overrides):
    base = {
        "id": "g", "rung": "sim", "layer": "backtesting-engine", "title": "t", "status": "established",
        "owner": "this-effort", "evidence_class": "synthetic", "required": True,
        "receipt_path": "r.json", "flip_condition": {"type": "equals", "pointer": "/ok", "equals": True}, "note": "",
    }
    base.update(overrides)
    return base


# Repository-relative path -> bytes of every synthetic paper-output.json a
# ladder_receipt fixture names; write_ladder_sources puts them under a test root.
LADDER_SOURCES: dict[str, bytes] = {}


def ladder_receipt(rung, config_max_leverage, threshold, *, peak, seconds, needs_attention=0,
                   run_status="passed", drop=()):
    """A leverage-ladder rung receipt in the schema preregistered in the gate
    notes, bound to a synthetic paper-output.json (registered in
    LADDER_SOURCES) whose "leverage" block it copies verbatim. Decimal fields
    are strings, as runner.run_native writes them; the duration is a float.
    `drop` removes leverage keys from both the source and the receipt, so the
    source binding still holds and only the rung's own conditions are judged."""
    leverage = {
        "policy_version": "leverage-schedule-v1-20260922",
        "config_max_leverage": config_max_leverage,
        "next_lower_rung_ceiling": threshold,
        "peak_achieved_leverage": peak,
        "ceiling_at_peak_achieved_leverage": config_max_leverage,
        "seconds_above_next_lower_rung_ceiling": seconds,
    }
    for key in drop:
        leverage.pop(key)
    data = (json.dumps({"status": run_status, "mode": "native", "leverage": leverage}, indent=2, sort_keys=True)
            + "\n").encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    path = f"blueprints/us-equities/adaptive-paper/trials/ladder-fixture-{digest[:16]}/paper-output.json"
    LADDER_SOURCES[path] = data
    return {
        "schema_version": 1, "kind": "leverage_ladder_rung_receipt", "rung": rung,
        "needs_attention": needs_attention,
        "source": {"paper_output_path": path, "paper_output_sha256": digest, "certified_run_status": run_status},
        "leverage": copy.deepcopy(leverage),
    }


def write_ladder_sources(root: Path) -> None:
    for relative, data in LADDER_SOURCES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def document(*gates, authorship=None):
    doc = {"schema_version": 1, "rungs": ["sim", "paper", "live"], "gates": list(gates)}
    if authorship is not None:
        doc["authorship"] = authorship
    return doc


def live_go(**overrides):
    """A live-go row in the repository's shape: owned by user-decision, null flip condition."""
    return gate(**{"id": "live-go", "rung": "live", "layer": "cross-layer", "status": "user_decision",
                   "owner": "user-decision", "evidence_class": "none", "receipt_path": LIVE_GO_MD,
                   "flip_condition": None, **overrides})


def live_go_control(**overrides):
    control = {"method": "ssh-keygen -Y verify", "signature_path": LIVE_GO_SIG,
               "allowed_signers_path": LIVE_GO_SIGNERS, "principal": SIGNER, "namespace": NAMESPACE, "note": ""}
    control.update(overrides)
    return control


def run_ssh_keygen(*args):
    """The host's ssh-keygen without an agent socket; stdin is closed so a prompt fails instead of waiting."""
    env = {key: value for key, value in os.environ.items() if key != "SSH_AUTH_SOCK"}
    return subprocess.run([SSH_KEYGEN, *args], stdin=subprocess.DEVNULL, capture_output=True, env=env,
                          timeout=60, check=True)


class ThrowawaySigner:
    """An ed25519 key generated for one test in its own temporary directory,
    outside the synthetic tree under test. Nothing here is committed: the
    directory is removed when the test ends."""

    def __init__(self, directory: Path, name: str):
        self.key = directory / f"{name}_ed25519"
        run_ssh_keygen("-q", "-t", "ed25519", "-N", "", "-C", name, "-f", str(self.key))

    def allowed_signers_line(self, principal=SIGNER, options=f'namespaces="{NAMESPACE}"'):
        kind, blob = Path(f"{self.key}.pub").read_text(encoding="utf-8").split()[:2]
        return f"{principal} {options} {kind} {blob}\n"

    def sign(self, data: bytes, namespace=NAMESPACE) -> bytes:
        """Sign a fresh copy (ssh-keygen -Y sign prompts before overwriting a .sig) and return the signature."""
        with tempfile.TemporaryDirectory() as scratch:
            copy_path = Path(scratch) / "document"
            copy_path.write_bytes(data)
            run_ssh_keygen("-Y", "sign", "-f", str(self.key), "-n", namespace, str(copy_path))
            return Path(f"{copy_path}.sig").read_bytes()


class GateTreeCase(unittest.TestCase):
    """A synthetic repository tree in a temporary directory."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relative, payload):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def put(self, relative, data: bytes):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def run_check(self, doc):
        path = self.write("gates.json", doc)
        return trading_gates.check(self.root, path)

    def ladder(self, live_go_row, control=None):
        """Every other required gate established with a holding receipt, so live-go alone decides the live rung."""
        self.write("r.json", {"ok": True})
        return document(gate(id="sim-gate", rung="sim"), gate(id="paper-gate", rung="paper"),
                        gate(id="live-gate", rung="live"), live_go_row,
                        authorship={"live-go": control or live_go_control()})


class TradingGatesTests(GateTreeCase):
    def test_established_gate_with_matching_receipt_passes(self):
        self.write("r.json", {"ok": True})
        result = self.run_check(document(gate()))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["rung_ready"]["sim"])

    def test_established_gate_with_missing_receipt_fails(self):
        result = self.run_check(document(gate()))
        self.assertEqual(result["status"], "failed")
        self.assertIn("receipt missing", result["errors"][0])

    def test_established_gate_with_false_condition_fails(self):
        self.write("r.json", {"ok": False})
        result = self.run_check(document(gate()))
        self.assertEqual(result["status"], "failed")
        self.assertIn("/ok", result["errors"][0])

    def test_equals_condition_is_type_strict(self):
        # Codex fix-round finding: Python's == treats False == 0 and 0.0 == 0,
        # so an untyped comparison would let a boolean or float receipt value
        # satisfy an integer flip condition (e.g. /unresolved_collisions == 0).
        self.write("r.json", {"ok": False})
        result = self.run_check(document(gate(flip_condition={"type": "equals", "pointer": "/ok", "equals": 0})))
        self.assertEqual(result["status"], "failed")
        holds, _ = trading_gates.condition_holds(self.root, gate(flip_condition={"type": "equals", "pointer": "/ok", "equals": 0}))
        self.assertFalse(holds)

        self.write("r.json", {"ok": 0})
        result = self.run_check(document(gate(status="not_established", flip_condition={"type": "equals", "pointer": "/ok", "equals": 0})))
        self.assertEqual([c["id"] for c in result["flip_candidates"]], ["g"])

    def test_absent_pointer_is_reported_not_crashed(self):
        self.write("r.json", {"other": 1})
        result = self.run_check(document(gate(flip_condition={"type": "equals", "pointer": "/a/b/0", "equals": 1})))
        self.assertEqual(result["status"], "failed")
        self.assertIn("pointer absent", result["errors"][0])

    def test_not_established_gate_whose_receipt_holds_is_a_flip_candidate_not_an_error(self):
        self.write("r.json", {"ok": True})
        result = self.run_check(document(gate(status="not_established")))
        self.assertEqual(result["status"], "passed")
        self.assertEqual([c["id"] for c in result["flip_candidates"]], ["g"])
        self.assertFalse(result["rung_ready"]["sim"])
        self.assertEqual(result["blocking"]["sim"], ["g"])

    def test_array_contains_id_condition(self):
        self.write("stack.json", {"components": [{"id": "exchange-calendars"}, {"id": "duckdb"}]})
        good = gate(receipt_path="stack.json", flip_condition={"type": "array_contains_id", "pointer": "/components", "id": "exchange-calendars"})
        self.assertEqual(self.run_check(document(good))["status"], "passed")
        bad = gate(receipt_path="stack.json", flip_condition={"type": "array_contains_id", "pointer": "/components", "id": "absent"})
        self.assertEqual(self.run_check(document(bad))["status"], "failed")

    def test_exists_condition_accepts_non_json_receipts(self):
        (self.root / "decision.md").write_text("# decision\n", encoding="utf-8")
        result = self.run_check(document(gate(receipt_path="decision.md", flip_condition={"type": "exists"})))
        self.assertEqual(result["status"], "passed")

    def test_exists_condition_rejects_an_empty_file(self):
        # Codex cross-family review of PR-4: presence-only conditions must not be
        # satisfiable by an empty file.
        (self.root / "empty.json").write_text("", encoding="utf-8")
        result = self.run_check(document(gate(receipt_path="empty.json", flip_condition={"type": "exists"})))
        self.assertEqual(result["status"], "failed")
        self.assertIn("empty", result["errors"][0])

    def test_rung_readiness_requires_every_earlier_rung(self):
        self.write("r.json", {"ok": True})
        sim = gate(id="sim-gate", rung="sim")
        paper = gate(id="paper-gate", rung="paper", status="not_established")
        # live-go now needs its authorship control named (and is owned by user-decision, as in the repository).
        result = self.run_check(document(sim, paper, live_go(), authorship={"live-go": live_go_control()}))
        self.assertTrue(result["rung_ready"]["sim"])
        self.assertFalse(result["rung_ready"]["paper"])
        self.assertFalse(result["rung_ready"]["live"])
        self.assertEqual(result["blocking"]["live"], ["paper-gate", "live-go"])

    def test_optional_gates_do_not_block_readiness(self):
        self.write("r.json", {"ok": True})
        result = self.run_check(document(gate(), gate(id="opt", status="paid_entitlement", required=False, evidence_class="none", flip_condition=None)))
        self.assertTrue(result["rung_ready"]["sim"])

    def test_vocabulary_and_shape_errors_are_rejected(self):
        for bad in (
            gate(status="passed"),
            gate(owner="someone"),
            gate(layer="unknown-layer"),
            gate(rung="prod"),
            gate(receipt_path="/abs/path.json"),
            gate(receipt_path="../escape.json"),
            gate(flip_condition={"type": "equals", "pointer": "/ok"}),
            gate(evidence_class="none"),
            {**gate(), "extra": 1},
        ):
            with self.assertRaises(trading_gates.GateError):
                trading_gates.validate_document(document(bad))
        with self.assertRaises(trading_gates.GateError):
            trading_gates.validate_document(document(gate(id="dup"), gate(id="dup")))
        with self.assertRaises(trading_gates.GateError):
            trading_gates.validate_document({"schema_version": 1, "rungs": ["sim"], "gates": [gate()]})

    def test_greater_than_compares_numbers_and_decimal_strings_exactly(self):
        condition = {"type": "greater_than", "pointer": "/v", "than": "1"}
        cases = (
            ("1.01", True), (1.5, True), (2, True),
            ("1", False), ("1.00", False), (1, False), (0.99, False), ("0.5", False),
            # Not numbers: a boolean, a non-numeric or non-finite string, null, a list.
            (True, False), ("high", False), ("NaN", False), ("Infinity", False), (None, False), ([2], False),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                self.write("r.json", {"v": value})
                holds, detail = trading_gates.condition_holds(self.root, gate(flip_condition=condition))
                self.assertEqual(holds, expected, detail)
        self.write("r.json", {"other": 5})
        holds, detail = trading_gates.condition_holds(self.root, gate(flip_condition=condition))
        self.assertFalse(holds)
        self.assertIn("pointer absent", detail)

    def test_all_of_requires_every_member(self):
        condition = {"type": "all_of", "conditions": [
            {"type": "equals", "pointer": "/needs_attention", "equals": 0},
            {"type": "greater_than", "pointer": "/peak", "than": "2"},
            {"type": "array_contains_id", "pointer": "/items", "id": "a"},
        ]}
        good = {"needs_attention": 0, "peak": "2.4", "items": [{"id": "a"}]}
        self.write("r.json", good)
        holds, detail = trading_gates.condition_holds(self.root, gate(flip_condition=condition))
        self.assertTrue(holds, detail)
        self.assertIn("3 of 3 hold", detail)
        result = self.run_check(document(gate(status="not_established", evidence_class="none", flip_condition=condition)))
        self.assertEqual([c["id"] for c in result["flip_candidates"]], ["g"])
        for broken in ({"needs_attention": 1}, {"peak": "2"}, {"items": []}, {"needs_attention": False}):
            with self.subTest(broken=broken):
                self.write("r.json", {**good, **broken})
                holds, detail = trading_gates.condition_holds(self.root, gate(flip_condition=condition))
                self.assertFalse(holds)
                self.assertIn("1 of 3 failed", detail)
                result = self.run_check(document(gate(status="not_established", evidence_class="none", flip_condition=condition)))
                self.assertEqual(result["flip_candidates"], [])
                self.assertEqual(self.run_check(document(gate(flip_condition=condition)))["status"], "failed")

    def test_greater_than_and_all_of_shape_errors_are_rejected(self):
        member = {"type": "equals", "pointer": "/ok", "equals": True}
        for bad in (
            {"type": "greater_than", "pointer": "/v"},
            {"type": "greater_than", "pointer": "/v", "than": True},
            {"type": "greater_than", "pointer": "/v", "than": "many"},
            {"type": "greater_than", "pointer": "/v", "than": "Infinity"},
            {"type": "greater_than", "pointer": "v", "than": 1},
            {"type": "greater_than", "pointer": "/v", "than": 1, "or_equal": True},
            {"type": "all_of"},
            {"type": "all_of", "conditions": []},
            {"type": "all_of", "conditions": member},
            {"type": "all_of", "conditions": [member], "extra": 1},
            {"type": "all_of", "conditions": [{"type": "exists"}]},
            {"type": "all_of", "conditions": [{"type": "all_of", "conditions": [member]}]},
            {"type": "all_of", "conditions": [member, {"type": "equals", "pointer": "/x"}]},
            {"type": "source_matches", "path_pointer": "/p", "sha256_pointer": "/h"},
            {"type": "source_matches", "path_pointer": "/p", "sha256_pointer": "/h", "pairs": []},
            {"type": "source_matches", "path_pointer": "/p", "sha256_pointer": "/h", "pairs": [["/a"]]},
            {"type": "source_matches", "path_pointer": "/p", "sha256_pointer": "/h", "pairs": [["/a", "b"]]},
            {"type": "source_matches", "path_pointer": "/p", "sha256_pointer": "/h", "pairs": [("/a", "/b")]},
            {"type": "source_matches", "path_pointer": "p", "sha256_pointer": "/h", "pairs": [["/a", "/b"]]},
            {"type": "source_matches", "path_pointer": "/p", "sha256_pointer": "/h", "pairs": [["/a", "/b"]], "pointer": "/x"},
        ):
            with self.subTest(condition=bad), self.assertRaises(trading_gates.GateError):
                trading_gates.validate_document(document(gate(flip_condition=bad)))
        binding = {"type": "source_matches", "path_pointer": "/p", "sha256_pointer": "/h", "pairs": [["/a", "/b"]]}
        trading_gates.validate_document(document(gate(flip_condition={"type": "all_of", "conditions": [
            member, {"type": "greater_than", "pointer": "/v", "than": 0}, binding]})))
        trading_gates.validate_document(document(gate(flip_condition=binding)))

    def test_source_matches_binds_the_receipt_to_hashed_source_bytes(self):
        source = {"status": "passed", "leverage": {"peak": "1.5", "seconds": 3.0}}
        data = json.dumps(source).encode("utf-8")
        (self.root / "src").mkdir()
        (self.root / "src" / "out.json").write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        condition = {"type": "source_matches", "path_pointer": "/source/path", "sha256_pointer": "/source/sha256",
                     "pairs": [["/leverage", "/leverage"], ["/source/status", "/status"]]}
        good = {"source": {"path": "src/out.json", "sha256": digest, "status": "passed"}, "leverage": source["leverage"]}
        self.write("r.json", good)
        holds, detail = trading_gates.condition_holds(self.root, gate(flip_condition=condition))
        self.assertTrue(holds, detail)
        for case, receipt in {
            "value_differs": {**good, "leverage": {"peak": "1.6", "seconds": 3.0}},
            # Type-strict: the float 3.0 in the source is not the integer 3.
            "type_differs": {**good, "leverage": {"peak": "1.5", "seconds": 3}},
            "status_differs": {**good, "source": {**good["source"], "status": "needs_attention"}},
            "digest_differs": {**good, "source": {**good["source"], "sha256": hashlib.sha256(b"x").hexdigest()}},
            "digest_not_hex": {**good, "source": {**good["source"], "sha256": "z" * 64}},
            "path_escapes": {**good, "source": {**good["source"], "path": "src/../../out.json"}},
            "path_backslash": {**good, "source": {**good["source"], "path": "src\\out.json"}},
            "path_not_string": {**good, "source": {**good["source"], "path": 7}},
            "path_missing": {**good, "source": {**good["source"], "path": "src/none.json"}},
            "path_is_directory": {**good, "source": {**good["source"], "path": "src"}},
            "pointer_absent": {"leverage": source["leverage"]},
        }.items():
            with self.subTest(case=case):
                self.write("r.json", receipt)
                holds, detail = trading_gates.condition_holds(self.root, gate(flip_condition=condition))
                self.assertFalse(holds, detail)
                self.assertIn("source_matches", detail)
        # A source that hashes correctly but is not JSON is refused, not crashed on.
        (self.root / "src" / "out.json").write_bytes(b"not json")
        self.write("r.json", {**good, "source": {**good["source"], "sha256": hashlib.sha256(b"not json").hexdigest()}})
        holds, detail = trading_gates.condition_holds(self.root, gate(flip_condition=condition))
        self.assertFalse(holds, detail)
        self.assertIn("source unreadable", detail)

    def test_main_exit_codes(self):
        self.write("r.json", {"ok": True})
        self.write("gates.json", document(gate()))
        self.assertEqual(trading_gates.main(["--root", str(self.root), "--path", "gates.json"]), 0)
        self.write("gates.json", document(gate(status="established", receipt_path="missing.json")))
        self.assertEqual(trading_gates.main(["--root", str(self.root), "--path", "gates.json"]), 1)


class RepositoryGatesTests(unittest.TestCase):
    def test_repository_gate_document_checks_clean(self):
        path = ROOT / trading_gates.GATES
        if not path.exists():
            self.skipTest("gate ladder not yet recorded in this tree")
        result = trading_gates.check(ROOT, path)
        self.assertEqual(result["errors"], [], result["errors"])


class GatePointerContentTests(unittest.TestCase):
    """A presence-only ('exists') flip condition is satisfiable by an empty
    placeholder file. Every not-yet-established gate in the repository ladder
    that used to use 'exists' now uses a content condition instead. For each
    of those gates this proves an empty JSON placeholder at the receipt path
    does not make the checker list the gate as a flip candidate, while a
    well-formed passing receipt (matching the schema recorded in the gate's
    own note) does.
    """

    # Gate id -> a well-formed receipt payload that satisfies the gate's
    # current flip_condition, per the schema documented in its note.
    GOOD_RECEIPTS = {
        "dividend-sim-module": {
            "schema_version": 1,
            "status": "closed",
            "mappings_closed": ["market_on_open_proxy", "distributions_and_cash"],
        },
        "pre-2020-delisting": {
            "schema_version": 1,
            "coverage_status": "confirmed",
            "years_covered": [2016, 2017, 2018, 2019],
            "source": {"name": "example-entitled-source", "kind": "entitled"},
        },
        "dated-security-identity": {
            "schema_version": 1,
            "collisions_total": 235,
            "unresolved_collisions": 0,
            "source": "example-entitled-source",
        },
        "pit-news-filings": {
            "schema_version": 1,
            "pit_status": "confirmed",
            "vintage_source": "example-vintage-source",
            "survivorship_free": True,
        },
        "databento-arm-b": {
            "schema_version": 1,
            "arm": "B",
            "provider": "databento",
            "status": "executed",
            "window": {"start": "2016-01-01", "end": "2026-01-01"},
        },
        "native-fault-behaviour": {
            "schema_version": 1,
            "kind": "native_fault_behaviour_receipt",
            "status": "native_faults_passed",
            "broker": "alpaca",
        },
        "ibkr-local-acceptance": {
            "schema_version": 1,
            "kind": "native_ibkr_local_acceptance",
            "status": "passed",
            "broker": "ibkr",
        },
        "leverage-ladder-1x": ladder_receipt("1x", "1", "0.5", peak="0.87", seconds=412.3),
        "leverage-ladder-2x": ladder_receipt("2x", "2", "1", peak="1.62", seconds=95.0),
        "leverage-ladder-4x": ladder_receipt("4x", "4", "2", peak="3.1", seconds=38.4),
    }

    # Gate id -> a well-formed receipt payload (same shape as GOOD_RECEIPTS)
    # whose terminal value fails the gate's flip condition. Regression for the
    # ibkr-local-acceptance finding: a receipt with the right kind/shape but a
    # failing result must not be a flip candidate.
    BAD_RECEIPTS = {
        "dividend-sim-module": {**GOOD_RECEIPTS["dividend-sim-module"], "status": "open"},
        "pre-2020-delisting": {**GOOD_RECEIPTS["pre-2020-delisting"], "coverage_status": "unconfirmed"},
        "dated-security-identity": {**GOOD_RECEIPTS["dated-security-identity"], "unresolved_collisions": 3},
        "pit-news-filings": {**GOOD_RECEIPTS["pit-news-filings"], "pit_status": "unconfirmed"},
        "databento-arm-b": {**GOOD_RECEIPTS["databento-arm-b"], "status": "not_executed"},
        "native-fault-behaviour": {**GOOD_RECEIPTS["native-fault-behaviour"], "status": "bounded_alpaca_synthetic_cases_passed_native_faults_pending"},
        "ibkr-local-acceptance": {**GOOD_RECEIPTS["ibkr-local-acceptance"], "status": "failed"},
        # Audit gap #5: zero needs_attention alone no longer flips a rung; a
        # trial that never exceeded the next-lower cap is well formed but fails.
        "leverage-ladder-1x": ladder_receipt("1x", "1", "0.5", peak="0.5", seconds=0.0),
        "leverage-ladder-2x": ladder_receipt("2x", "2", "1", peak="1", seconds=0.0),
        "leverage-ladder-4x": ladder_receipt("4x", "4", "2", peak="2", seconds=0.0),
    }

    @classmethod
    def setUpClass(cls):
        path = ROOT / trading_gates.GATES
        if not path.exists():
            raise unittest.SkipTest("gate ladder not yet recorded in this tree")
        cls.gates_by_id = {gate["id"]: gate for gate in trading_gates.load_json(path)["gates"]}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write_ladder_sources(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_every_designated_gate_dropped_the_exists_condition(self):
        for gate_id in self.GOOD_RECEIPTS:
            with self.subTest(gate=gate_id):
                condition = self.gates_by_id[gate_id]["flip_condition"]
                self.assertIsNotNone(condition, f"{gate_id}: flip_condition must not be null")
                self.assertNotEqual(condition["type"], "exists",
                                     f"{gate_id}: still uses a presence-only 'exists' condition")

    def test_empty_placeholder_is_not_a_flip_candidate_but_a_passing_receipt_is(self):
        for gate_id, good_content in self.GOOD_RECEIPTS.items():
            with self.subTest(gate=gate_id):
                # The content condition is what is under test, not the gate's live status
                # (a gate may already be established): evaluate a not-established copy.
                gate = {**self.gates_by_id[gate_id], "status": "not_established", "evidence_class": "none"}

                # An empty JSON placeholder (what a presence-only 'exists' flip
                # would have accepted) must not satisfy the content condition.
                self.write(gate["receipt_path"], "{}")
                empty_result = trading_gates.check(self.root, self.write("gates.json", json.dumps(document(gate))))
                self.assertEqual(
                    [c["id"] for c in empty_result["flip_candidates"]], [],
                    f"{gate_id}: empty placeholder was listed as a flip candidate",
                )
                holds, detail = trading_gates.condition_holds(self.root, gate)
                self.assertFalse(holds, f"{gate_id}: empty placeholder unexpectedly holds ({detail})")

                # A well-formed, passing receipt must satisfy the condition
                # and be reported as a flip candidate.
                self.write(gate["receipt_path"], json.dumps(good_content))
                passing_result = trading_gates.check(self.root, self.write("gates.json", json.dumps(document(gate))))
                self.assertEqual(
                    [c["id"] for c in passing_result["flip_candidates"]], [gate_id],
                    f"{gate_id}: well-formed passing receipt was not listed as a flip candidate",
                )
                holds, detail = trading_gates.condition_holds(self.root, gate)
                self.assertTrue(holds, f"{gate_id}: well-formed passing receipt does not hold ({detail})")

    def test_well_formed_failing_receipt_is_not_a_flip_candidate(self):
        for gate_id, bad_content in self.BAD_RECEIPTS.items():
            with self.subTest(gate=gate_id):
                # The content condition is what is under test, not the gate's live status
                # (a gate may already be established): evaluate a not-established copy.
                gate = {**self.gates_by_id[gate_id], "status": "not_established", "evidence_class": "none"}

                self.write(gate["receipt_path"], json.dumps(bad_content))
                result = trading_gates.check(self.root, self.write("gates.json", json.dumps(document(gate))))
                self.assertEqual(
                    [c["id"] for c in result["flip_candidates"]], [],
                    f"{gate_id}: well-formed but failing receipt was listed as a flip candidate",
                )
                holds, detail = trading_gates.condition_holds(self.root, gate)
                self.assertFalse(holds, f"{gate_id}: well-formed failing receipt unexpectedly holds ({detail})")

    def test_no_non_established_gate_in_the_repository_ladder_uses_presence_only_exists(self):
        # Generic guard (not limited to GOOD_RECEIPTS' seven ids): any gate
        # that is not yet established must not rely on a presence-only
        # 'exists' flip condition, which an empty placeholder file satisfies.
        for gate_id, gate in self.gates_by_id.items():
            if gate["status"] == "established":
                continue
            condition = gate["flip_condition"]
            if condition is None:
                continue
            with self.subTest(gate=gate_id):
                self.assertNotEqual(condition["type"], "exists",
                                     f"{gate_id}: non-established gate uses a presence-only 'exists' condition")


class LeverageLadderFlipConditionTests(unittest.TestCase):
    """Audit gap #5 (2026-09-24): the leverage-ladder-1x/2x/4x rows used to flip
    on needs_attention == 0 alone, so a rung could be established by a trial
    whose achieved exposure never exceeded the next-lower rung's cap. Each row
    now also requires the rung receipt's peak_achieved_leverage and
    seconds_above_next_lower_rung_ceiling to exceed that threshold (0.5x for
    the 1x rung, the documented minimum exposure)."""

    RUNGS = {"leverage-ladder-1x": ("1x", "1", "0.5"),
             "leverage-ladder-2x": ("2x", "2", "1"),
             "leverage-ladder-4x": ("4x", "4", "2")}

    @classmethod
    def setUpClass(cls):
        path = ROOT / trading_gates.GATES
        if not path.exists():
            raise unittest.SkipTest("gate ladder not yet recorded in this tree")
        cls.gates_by_id = {gate["id"]: gate for gate in trading_gates.load_json(path)["gates"]}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def holds(self, gate_id, receipt):
        write_ladder_sources(self.root)
        gate = {**self.gates_by_id[gate_id], "status": "not_established", "evidence_class": "none"}
        path = self.root / gate["receipt_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt), encoding="utf-8")
        return trading_gates.condition_holds(self.root, gate)

    def test_each_rung_requires_needs_attention_and_both_achievement_fields(self):
        for gate_id, (rung, config_max, threshold) in self.RUNGS.items():
            with self.subTest(gate=gate_id):
                condition = self.gates_by_id[gate_id]["flip_condition"]
                self.assertEqual(condition["type"], "all_of")
                members = {(c["type"], c.get("pointer")): c for c in condition["conditions"]}
                self.assertEqual(members[("equals", "/schema_version")]["equals"], 1)
                self.assertEqual(members[("equals", "/kind")]["equals"], "leverage_ladder_rung_receipt")
                self.assertEqual(members[("equals", "/rung")]["equals"], rung)
                self.assertEqual(members[("equals", "/source/certified_run_status")]["equals"], "passed")
                binding = members[("source_matches", None)]
                self.assertEqual(binding["path_pointer"], "/source/paper_output_path")
                self.assertEqual(binding["sha256_pointer"], "/source/paper_output_sha256")
                self.assertEqual(binding["pairs"], [["/leverage", "/leverage"], ["/source/certified_run_status", "/status"]])
                self.assertEqual(members[("equals", "/needs_attention")]["equals"], 0)
                self.assertEqual(members[("equals", "/leverage/config_max_leverage")]["equals"], config_max)
                self.assertEqual(members[("equals", "/leverage/next_lower_rung_ceiling")]["equals"], threshold)
                self.assertEqual(members[("greater_than", "/leverage/peak_achieved_leverage")]["than"], threshold)
                self.assertEqual(members[("greater_than", "/leverage/seconds_above_next_lower_rung_ceiling")]["than"], 0)

    def test_trial_that_never_exceeds_the_lower_cap_does_not_satisfy_the_rung(self):
        for gate_id, (rung, config_max, threshold) in self.RUNGS.items():
            below = str(Decimal(threshold) * Decimal("0.8"))
            for peak in (below, threshold):
                with self.subTest(gate=gate_id, peak=peak):
                    # Zero needs_attention, a clean receipt, but exposure stayed at
                    # or under the next-lower cap for the whole trial.
                    holds, detail = self.holds(gate_id, ladder_receipt(rung, config_max, threshold, peak=peak, seconds=0.0))
                    self.assertFalse(holds, detail)
                    # The source binding holds; only the achievement members fail.
                    self.assertIn("2 of 10 failed", detail)
                    self.assertNotIn("source_matches", detail)

    def test_each_achievement_field_is_required_on_its_own(self):
        for gate_id, (rung, config_max, threshold) in self.RUNGS.items():
            good = ladder_receipt(rung, config_max, threshold, peak=str(Decimal(threshold) + 1), seconds=12.5)
            with self.subTest(gate=gate_id, case="good"):
                holds, detail = self.holds(gate_id, good)
                self.assertTrue(holds, detail)
            above = str(Decimal(threshold) + 1)
            # Each case is internally consistent (its own hashed source), so
            # the named member is what fails, not the source binding.
            consistent = {
                "needs_attention": ladder_receipt(rung, config_max, threshold, peak=above, seconds=12.5, needs_attention=1),
                "peak_not_above": ladder_receipt(rung, config_max, threshold, peak=threshold, seconds=12.5),
                "no_time_above": ladder_receipt(rung, config_max, threshold, peak=above, seconds=0.0),
                "peak_missing": ladder_receipt(rung, config_max, threshold, peak=above, seconds=12.5,
                                               drop=("peak_achieved_leverage",)),
                "seconds_missing": ladder_receipt(rung, config_max, threshold, peak=above, seconds=12.5,
                                                  drop=("seconds_above_next_lower_rung_ceiling",)),
                "pre_gap5_1x_threshold": ladder_receipt(rung, config_max, None, peak=above, seconds=12.5),
                "other_rung_config": ladder_receipt(rung, "3", threshold, peak=above, seconds=12.5),
                "boolean_seconds": ladder_receipt(rung, config_max, threshold, peak=above, seconds=True),
                "run_not_passed": ladder_receipt(rung, config_max, threshold, peak=above, seconds=12.5,
                                                 run_status="needs_attention"),
                "wrong_rung_label": {**good, "rung": "8x"},
                "wrong_kind": {**good, "kind": "native_fault_behaviour_receipt"},
                "wrong_schema_version": {**good, "schema_version": 2},
            }
            for case, receipt in consistent.items():
                with self.subTest(gate=gate_id, case=case):
                    holds, detail = self.holds(gate_id, receipt)
                    self.assertFalse(holds, detail)
                    self.assertNotIn("source_matches", detail)
            # The receipt no longer matches the hashed paper-output.json it names.
            unbound = {
                "leverage_edited": {**good, "leverage": {**good["leverage"], "peak_achieved_leverage": "9"}},
                "status_edited": {**good, "source": {**good["source"], "certified_run_status": "needs_attention"}},
                "sha256_wrong": {**good, "source": {**good["source"], "paper_output_sha256": "0" * 64}},
                "sha256_uppercase": {**good, "source": {**good["source"],
                                                        "paper_output_sha256": good["source"]["paper_output_sha256"].upper()}},
                "source_missing": {**good, "source": {**good["source"], "paper_output_path": "trials/absent/paper-output.json"}},
                "source_outside_tree": {**good, "source": {**good["source"], "paper_output_path": "../paper-output.json"}},
                "source_absolute": {**good, "source": {**good["source"], "paper_output_path": "/etc/hostname"}},
                "no_source_block": {k: v for k, v in good.items() if k != "source"},
                "no_leverage_block": {k: v for k, v in good.items() if k != "leverage"},
            }
            for case, receipt in unbound.items():
                with self.subTest(gate=gate_id, case=case):
                    holds, detail = self.holds(gate_id, receipt)
                    self.assertFalse(holds, detail)
                    self.assertIn("source_matches", detail)

    def test_leverage_block_and_status_must_come_from_the_same_hashed_run(self):
        # A clean certified run that stayed under the cap, stitched to the
        # leverage block of another run: the binding refuses the mix.
        for gate_id, (rung, config_max, threshold) in self.RUNGS.items():
            with self.subTest(gate=gate_id):
                used = ladder_receipt(rung, config_max, threshold, peak=str(Decimal(threshold) + 1), seconds=30.0,
                                      run_status="needs_attention")
                clean = ladder_receipt(rung, config_max, threshold, peak=threshold, seconds=0.0)
                stitched = {**clean, "leverage": used["leverage"]}
                holds, detail = self.holds(gate_id, stitched)
                self.assertFalse(holds, detail)
                self.assertIn("/leverage != source /leverage", detail)


class UserDecisionEvidenceTests(GateTreeCase):
    """Checker hardening (2026-09-25), item 1: an evidence class for user
    decisions, valid only for a gate owned by user-decision whose flip_condition
    is null."""

    def test_user_decision_is_an_evidence_class(self):
        self.assertIn("user_decision", trading_gates.EVIDENCE)

    def test_valid_only_for_user_owned_gates_without_a_flip_condition(self):
        for status in ("established", "user_decision", "not_established"):
            with self.subTest(status=status):
                trading_gates.validate_document(document(gate(
                    id="choice", owner="user-decision", flip_condition=None, evidence_class="user_decision",
                    status=status)))
        for case, bad in {
            "owned by this-effort": gate(owner="this-effort", flip_condition=None, evidence_class="user_decision"),
            "owned by the peer": gate(owner="peer:sota-workflow-resolution", flip_condition=None,
                                      evidence_class="user_decision"),
            "equals flip condition": gate(owner="user-decision", evidence_class="user_decision"),
            "exists flip condition": gate(owner="user-decision", flip_condition={"type": "exists"},
                                          evidence_class="user_decision"),
            "not established either": gate(owner="user-decision", status="not_established",
                                           evidence_class="user_decision"),
        }.items():
            with self.subTest(case=case):
                with self.assertRaises(trading_gates.GateError) as caught:
                    trading_gates.validate_document(document(bad))
                self.assertIn("evidence_class user_decision is valid only for a gate owned by user-decision",
                              str(caught.exception))

    def test_other_gates_keep_their_evidence_rules(self):
        # A user-decision gate with a flip condition still records any other class,
        # and a null-condition gate that is not live-go keeps the presence rule.
        trading_gates.validate_document(document(gate(owner="user-decision", evidence_class="native_proven")))
        self.put("decision.md", b"# decision\n")
        result = self.run_check(document(gate(receipt_path="decision.md", flip_condition=None)))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["authorship"], {})


class ReadinessRequiresHoldingEvidenceTests(GateTreeCase):
    """Checker hardening (2026-09-25), item 2. Simulation V1 of the readiness
    plan showed status failed alongside rung_ready.live true, because rung_ready
    and blocking read only the recorded status. A required gate now counts only
    while it is recorded established and its condition holds."""

    def test_established_gate_whose_condition_fails_blocks_its_rung_and_every_later_rung(self):
        self.write("sim.json", {"ok": True})
        self.write("paper.json", {"ok": False})
        self.write("live.json", {"ok": True})
        gates = (gate(id="sim-gate", rung="sim", receipt_path="sim.json"),
                 gate(id="paper-gate", rung="paper", receipt_path="paper.json"),
                 gate(id="live-gate", rung="live", receipt_path="live.json"))
        result = self.run_check(document(*gates))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("paper-gate: recorded established but", result["errors"][0])
        self.assertEqual(result["rung_ready"], {"sim": True, "paper": False, "live": False})
        self.assertEqual(result["blocking"], {"sim": [], "paper": ["paper-gate"], "live": ["paper-gate"]})
        self.write("paper.json", {"ok": True})
        result = self.run_check(document(*gates))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["rung_ready"], {"sim": True, "paper": True, "live": True})
        self.assertEqual(result["blocking"], {"sim": [], "paper": [], "live": []})

    def test_established_gate_with_a_missing_or_empty_receipt_blocks(self):
        (self.root / "empty.md").write_text("", encoding="utf-8")
        for case, row in {
            "missing receipt": gate(id="g", receipt_path="absent.json"),
            "empty presence-only receipt": gate(id="g", receipt_path="empty.md", flip_condition={"type": "exists"}),
        }.items():
            with self.subTest(case=case):
                result = self.run_check(document(row))
                self.assertEqual(result["status"], "failed")
                self.assertFalse(result["rung_ready"]["sim"])
                self.assertEqual(result["blocking"]["sim"], ["g"])

    def test_optional_established_gate_that_fails_is_an_error_but_does_not_block(self):
        self.write("r.json", {"ok": True})
        self.write("opt.json", {"ok": False})
        result = self.run_check(document(gate(), gate(id="opt", required=False, receipt_path="opt.json")))
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["rung_ready"]["sim"])
        self.assertEqual(result["blocking"]["sim"], [])

    def test_repository_ladder_recorded_established_without_receipts_is_not_ready(self):
        # Simulation V1 on the repository's own rows: every required gate is
        # recorded established (live-go with user_decision evidence) in a tree
        # that holds none of their receipts.
        path = ROOT / trading_gates.GATES
        if not path.exists():
            self.skipTest("gate ladder not yet recorded in this tree")
        doc = copy.deepcopy(trading_gates.load_json(path))
        required = []
        for row in doc["gates"]:
            if row["required"]:
                row["status"] = "established"
                row["evidence_class"] = "user_decision" if row["id"] == "live-go" else "synthetic"
                required.append(row)
        result = self.run_check(doc)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["rung_ready"], {"sim": False, "paper": False, "live": False})
        self.assertEqual(result["blocking"]["live"], [row["id"] for row in required])
        self.assertEqual(result["blocking"]["sim"], [row["id"] for row in required if row["rung"] == "sim"])
        self.assertIn("live-go", result["blocking"]["live"])


class LiveGoAuthorshipTests(GateTreeCase):
    """Checker hardening (2026-09-25), item 3: live-go counts only when a
    detached SSH signature over its receipt verifies with ssh-keygen -Y verify
    against the allowed_signers file the catalog names. Every case here fails
    before ssh-keygen would run, or replaces it with a stub."""

    def established(self):
        return live_go(status="established", evidence_class="user_decision")

    def assert_fails_closed(self, result, reason):
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["errors"]), 1, result["errors"])
        self.assertTrue(result["errors"][0].startswith("live-go: recorded established but "), result["errors"])
        self.assertIn(reason, result["errors"][0])
        self.assertFalse(result["rung_ready"]["live"])
        self.assertEqual(result["blocking"]["live"], ["live-go"])
        self.assertFalse(result["authorship"]["live-go"]["verified"])
        self.assertIn(reason, result["authorship"]["live-go"]["detail"])

    def test_live_go_must_name_its_control(self):
        with self.assertRaises(trading_gates.GateError) as caught:
            trading_gates.validate_document(document(live_go()))
        self.assertIn("live-go: the catalog must name its authorship control", str(caught.exception))
        trading_gates.validate_document(document(live_go(), authorship={"live-go": live_go_control()}))

    def test_control_shape_errors_are_rejected(self):
        row = live_go()
        control = live_go_control()
        cases = {
            "authorship is a list": document(row, authorship=[control]),
            "authorship is null": {**document(row), "authorship": None},
            "unknown gate": document(row, authorship={"live-go": control, "ghost": control}),
            "gate with a flip condition": document(row, gate(id="cond", owner="user-decision"),
                                                   authorship={"live-go": control, "cond": control}),
            "gate not owned by user-decision": document(live_go(owner="this-effort"), authorship={"live-go": control}),
            "control is not an object": document(row, authorship={"live-go": "ssh-keygen -Y verify"}),
            "missing field": document(row, authorship={"live-go": {k: v for k, v in control.items() if k != "namespace"}}),
            "extra field": document(row, authorship={"live-go": {**control, "public_key": "ssh-ed25519 AAAA"}}),
            "other method": document(row, authorship={"live-go": live_go_control(method="gpg --verify")}),
            "absolute signature path": document(row, authorship={"live-go": live_go_control(signature_path="/etc/x.sig")}),
            "escaping signers path": document(row, authorship={"live-go": live_go_control(allowed_signers_path="../signers")}),
            "backslash path": document(row, authorship={"live-go": live_go_control(signature_path="docs\\live-go.md.sig")}),
            "empty path": document(row, authorship={"live-go": live_go_control(allowed_signers_path="")}),
            "non-string path": document(row, authorship={"live-go": live_go_control(signature_path=7)}),
            "signature is the receipt": document(row, authorship={"live-go": live_go_control(signature_path=LIVE_GO_MD)}),
            "signers file is the receipt": document(row, authorship={"live-go": live_go_control(
                allowed_signers_path="docs/decisions/./live-go.md")}),
            "signers file is the signature": document(row, authorship={"live-go": live_go_control(
                allowed_signers_path=LIVE_GO_SIG)}),
            "empty principal": document(row, authorship={"live-go": live_go_control(principal="")}),
            "option-like principal": document(row, authorship={"live-go": live_go_control(principal="-Overify-time=1")}),
            "principal with a space": document(row, authorship={"live-go": live_go_control(principal="live go")}),
            "principal with a newline": document(row, authorship={"live-go": live_go_control(principal="live\ngo")}),
            "non-string namespace": document(row, authorship={"live-go": live_go_control(namespace=None)}),
            "option-like namespace": document(row, authorship={"live-go": live_go_control(namespace="-n")}),
            "non-string note": document(row, authorship={"live-go": live_go_control(note=None)}),
            "established with another evidence class": document(
                live_go(status="established", evidence_class="native_proven"), authorship={"live-go": control}),
        }
        for case, doc in cases.items():
            with self.subTest(case=case), self.assertRaises(trading_gates.GateError):
                trading_gates.validate_document(doc)

    def test_live_go_fails_closed_without_its_signature_or_allowed_signers_file(self):
        document_bytes = b"# live go\n"
        cases = {
            "nothing written": ({}, "receipt missing"),
            "document only": ({LIVE_GO_MD: document_bytes}, "allowed_signers file missing"),
            "document and signature": ({LIVE_GO_MD: document_bytes, LIVE_GO_SIG: b"signature"},
                                       "allowed_signers file missing"),
            "document and allowed_signers": ({LIVE_GO_MD: document_bytes, LIVE_GO_SIGNERS: b"signer line\n"},
                                             "signature missing"),
            "empty document": ({LIVE_GO_MD: b"", LIVE_GO_SIG: b"signature", LIVE_GO_SIGNERS: b"signer line\n"},
                               "receipt present but empty"),
            "empty allowed_signers file": ({LIVE_GO_MD: document_bytes, LIVE_GO_SIG: b"signature",
                                            LIVE_GO_SIGNERS: b""}, "allowed_signers file empty"),
            "empty signature": ({LIVE_GO_MD: document_bytes, LIVE_GO_SIG: b"", LIVE_GO_SIGNERS: b"signer line\n"},
                                "signature empty"),
        }
        for case, (files, reason) in cases.items():
            with self.subTest(case=case):
                for relative in (LIVE_GO_MD, LIVE_GO_SIG, LIVE_GO_SIGNERS):
                    (self.root / relative).unlink(missing_ok=True)
                for relative, data in files.items():
                    self.put(relative, data)
                # Nothing is verified when a file is absent or empty: ssh-keygen never runs.
                with mock.patch.object(trading_gates.subprocess, "run",
                                       side_effect=AssertionError("ssh-keygen must not run")):
                    self.assert_fails_closed(self.run_check(self.ladder(self.established())), reason)
                    # Not recorded established, the same tree is simply not ready: no error.
                    result = self.run_check(self.ladder(live_go()))
                self.assertEqual(result["status"], "passed")
                self.assertEqual(result["blocking"]["live"], ["live-go"])
                self.assertEqual(result["flip_candidates"], [])

    def test_live_go_fails_closed_when_ssh_keygen_is_missing_or_does_not_verify(self):
        self.put(LIVE_GO_MD, b"# live go\n")
        self.put(LIVE_GO_SIG, b"signature")
        self.put(LIVE_GO_SIGNERS, b"signer line\n")
        with mock.patch.object(trading_gates.shutil, "which", return_value=None):
            self.assert_fails_closed(self.run_check(self.ladder(self.established())), "ssh-keygen not found")
        for error in (subprocess.TimeoutExpired(cmd="ssh-keygen", timeout=30), OSError("exec format error")):
            with self.subTest(error=type(error).__name__), \
                    mock.patch.object(trading_gates.shutil, "which", return_value="ssh-keygen"), \
                    mock.patch.object(trading_gates.subprocess, "run", side_effect=error):
                self.assert_fails_closed(self.run_check(self.ladder(self.established())), "did not complete")
        # The exit status decides: a non-zero exit is a refusal whatever the tool printed.
        refused = subprocess.CompletedProcess(args=[], returncode=255, stdout=b'Good "x" signature for y\n', stderr=b"")
        with mock.patch.object(trading_gates.shutil, "which", return_value="ssh-keygen"), \
                mock.patch.object(trading_gates.subprocess, "run", return_value=refused) as run:
            self.assert_fails_closed(self.run_check(self.ladder(self.established())), "does not verify")
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["ssh-keygen", "-Y", "verify"])
        self.assertEqual(command[3:], ["-f", f"./{LIVE_GO_SIGNERS}", "-I", SIGNER, "-n", NAMESPACE,
                                       "-s", f"./{LIVE_GO_SIG}"])
        self.assertEqual(run.call_args.kwargs["input"], b"# live go\n")
        self.assertEqual(Path(run.call_args.kwargs["cwd"]), self.root.resolve())

    def test_paths_that_resolve_outside_the_tree_fail_closed(self):
        self.put(LIVE_GO_MD, b"# live go\n")
        self.put(LIVE_GO_SIG, b"signature")
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "allowed_signers"
            target.write_text("signer line\n", encoding="utf-8")
            try:
                (self.root / LIVE_GO_SIGNERS).symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links are unavailable here")
            with mock.patch.object(trading_gates.subprocess, "run",
                                   side_effect=AssertionError("ssh-keygen must not run")):
                self.assert_fails_closed(self.run_check(self.ladder(self.established())),
                                         f"allowed_signers file {LIVE_GO_SIGNERS} resolves outside the tree")

    def test_live_go_never_holds_on_presence_alone(self):
        self.put(LIVE_GO_MD, b"# live go\n")
        holds, detail = trading_gates.condition_holds(self.root, self.established())
        self.assertFalse(holds)
        self.assertIn("never counts on presence alone", detail)
        # Any other null-condition gate keeps the earlier presence rule.
        holds, _ = trading_gates.condition_holds(self.root, gate(id="choice", receipt_path=LIVE_GO_MD,
                                                                 flip_condition=None))
        self.assertTrue(holds)

    def test_the_checker_writes_nothing(self):
        self.put(LIVE_GO_MD, b"# live go\n")
        gates_path = self.write("gates.json", self.ladder(self.established()))

        def snapshot():
            return {path.relative_to(self.root).as_posix(): path.read_bytes()
                    for path in sorted(self.root.rglob("*")) if path.is_file()}

        before = snapshot()
        result = trading_gates.check(self.root, gates_path)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(snapshot(), before)


@unittest.skipUnless(SSH_KEYGEN, "ssh-keygen is not installed on this host")
class LiveGoSignatureTests(GateTreeCase):
    """Real ssh-keygen -Y sign and -Y verify with throwaway ed25519 keys made in
    a separate temporary directory per test (removed afterwards; no key,
    signature or allowed_signers entry is committed)."""

    def setUp(self):
        super().setUp()
        self.keys = tempfile.TemporaryDirectory()
        self.signer = ThrowawaySigner(Path(self.keys.name), "throwaway-signer")

    def tearDown(self):
        self.keys.cleanup()
        super().tearDown()

    def established(self):
        return live_go(status="established", evidence_class="user_decision")

    def sign_tree(self, text=b"# live go\n", *, signer=None, namespace=NAMESPACE, allowed=None):
        self.put(LIVE_GO_MD, text)
        self.put(LIVE_GO_SIG, (signer or self.signer).sign(text, namespace))
        self.put(LIVE_GO_SIGNERS, (allowed or self.signer.allowed_signers_line()).encode("utf-8"))

    def test_a_valid_signature_lets_live_go_count_as_established(self):
        self.sign_tree()
        gates_path = self.write("gates.json", self.ladder(self.established()))
        before = {path: path.read_bytes() for path in sorted(self.root.rglob("*")) if path.is_file()}
        result = trading_gates.check(self.root, gates_path)
        # Verification writes nothing into the tree.
        self.assertEqual({path: path.read_bytes() for path in sorted(self.root.rglob("*")) if path.is_file()}, before)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["rung_ready"], {"sim": True, "paper": True, "live": True})
        self.assertEqual(result["blocking"]["live"], [])
        self.assertTrue(result["authorship"]["live-go"]["verified"])
        self.assertIn(f'Good "{NAMESPACE}" signature for {SIGNER}', result["authorship"]["live-go"]["detail"])
        # Verified but not yet recorded established: still blocking, never a flip candidate.
        result = self.run_check(self.ladder(live_go()))
        self.assertTrue(result["authorship"]["live-go"]["verified"])
        self.assertEqual(result["blocking"]["live"], ["live-go"])
        self.assertEqual(result["flip_candidates"], [])

    def test_every_mismatch_fails_closed(self):
        other = ThrowawaySigner(Path(self.keys.name), "other-signer")
        another_namespace = "other@native-agent-stack"
        cases = {
            "document edited after signing": dict(edit=b"# live go, edited\n"),
            "signed by a key the file does not list": dict(signer=other),
            "signed in the generic file namespace": dict(namespace="file"),
            "signed in another namespace": dict(namespace=another_namespace),
            "file lists the key for another principal": dict(
                allowed=self.signer.allowed_signers_line(principal="someone-else")),
            "file restricts the key to another namespace": dict(
                allowed=self.signer.allowed_signers_line(options=f'namespaces="{another_namespace}"')),
            "file lists an expired key": dict(
                allowed=self.signer.allowed_signers_line(options=f'namespaces="{NAMESPACE}",valid-before="20200101"')),
            "file holds no key": dict(allowed="not a key line\n"),
            "catalog names another principal": dict(control=live_go_control(principal="someone-else")),
            "catalog names another namespace": dict(control=live_go_control(namespace=another_namespace)),
            "signature of another document": dict(signature=self.signer.sign(b"# another document\n")),
            "signature is not a signature": dict(
                signature=b"-----BEGIN SSH SIGNATURE-----\nAAAA\n-----END SSH SIGNATURE-----\n"),
        }
        for case, spec in cases.items():
            with self.subTest(case=case):
                self.sign_tree(signer=spec.get("signer"), namespace=spec.get("namespace", NAMESPACE),
                               allowed=spec.get("allowed"))
                if "edit" in spec:
                    self.put(LIVE_GO_MD, spec["edit"])
                if "signature" in spec:
                    self.put(LIVE_GO_SIG, spec["signature"])
                result = self.run_check(self.ladder(self.established(), spec.get("control")))
                self.assertEqual(result["status"], "failed")
                self.assertIn("does not verify", result["errors"][0])
                self.assertFalse(result["rung_ready"]["live"])
                self.assertEqual(result["blocking"]["live"], ["live-go"])
                self.assertFalse(result["authorship"]["live-go"]["verified"])


class RepositoryLiveGoControlTests(unittest.TestCase):
    def test_repository_live_go_names_an_ssh_signature_control_and_the_checker_writes_none_of_its_files(self):
        path = ROOT / trading_gates.GATES
        if not path.exists():
            self.skipTest("gate ladder not yet recorded in this tree")
        document_ = trading_gates.load_json(path)
        row = {gate_["id"]: gate_ for gate_ in document_["gates"]}["live-go"]
        self.assertEqual((row["rung"], row["owner"], row["required"], row["flip_condition"]),
                         ("live", "user-decision", True, None))
        control = document_["authorship"]["live-go"]
        self.assertEqual(control["method"], "ssh-keygen -Y verify")
        self.assertEqual((control["signature_path"], control["allowed_signers_path"]),
                         (f"{row['receipt_path']}.sig", "docs/decisions/live-go.allowed_signers"))
        files = [ROOT / row["receipt_path"], ROOT / control["signature_path"], ROOT / control["allowed_signers_path"]]
        before = [(file.exists(), file.read_bytes() if file.is_file() else None) for file in files]
        trading_gates.check(ROOT, path)
        self.assertEqual([(file.exists(), file.read_bytes() if file.is_file() else None) for file in files], before)


if __name__ == "__main__":
    unittest.main()
