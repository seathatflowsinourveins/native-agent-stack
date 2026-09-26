"""Report-only source bindings in scripts/trading_gates.py.

Synthetic fixtures (local integration, no receipt is replayed and no broker is
contacted) show that a receipt whose bound source files differ from the tree
or from the release manifest is listed under ``warnings`` while the gate's
status, rung readiness, ``errors`` and the exit code stay as they were. The
repository tests only read this tree: they check that the binding table still
matches the receipt the native-faults harness writes, and they print any stale
binding to stderr instead of failing, so an unrelated pull request never fails
because an engine file changed.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import trading_gates  # noqa: E402

GATE_ID = "native-fault-behaviour"
ENGINE = "blueprints/us-equities/adaptive-paper"
RECEIPT = f"{ENGINE}/native-faults/receipt.json"
MANIFEST = f"{ENGINE}/source-hashes.json"
# The keys native-faults/harness.py records in engine_sources_sha256, relative to ENGINE.
ENGINE_KEYS = ("transport.py", "safety.py", "runner.py", "../order-contract/order_contract.py")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SyntheticBindingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.files = {
            f"{ENGINE}/transport.py": b"transport v1\n",
            f"{ENGINE}/safety.py": b"safety v1\n",
            f"{ENGINE}/runner.py": b"runner v1\n",
            "blueprints/us-equities/order-contract/order_contract.py": b"contract v1\n",
            f"{ENGINE}/native-faults/harness.py": b"harness v1\n",
            f"{ENGINE}/native-faults/plan.json": b"{\"plan\": 1}\n",
        }
        for path, data in self.files.items():
            self.put(path, data)
        # The release manifest lists the three engine modules, as source-hashes.json does.
        self.write_manifest({path: sha(self.files[path]) for path in
                             (f"{ENGINE}/transport.py", f"{ENGINE}/safety.py", f"{ENGINE}/runner.py")})
        self.receipt = {
            "schema_version": 1, "kind": "native_fault_behaviour_receipt", "status": "native_faults_passed",
            "engine_sources_sha256": {key: sha(self.files[trading_gates.bound_path(ENGINE, key)])
                                      for key in ENGINE_KEYS},
            "harness_sha256": sha(self.files[f"{ENGINE}/native-faults/harness.py"]),
            "plan_sha256": sha(self.files[f"{ENGINE}/native-faults/plan.json"]),
        }
        self.write_receipt()
        self.gates = self.root / "gates.json"
        self.gates.write_text(json.dumps({"schema_version": 1, "rungs": ["sim", "paper", "live"], "gates": [
            {"id": GATE_ID, "rung": "live", "layer": "execution-broker", "title": "t", "status": "established",
             "owner": "peer:sota-workflow-resolution", "evidence_class": "native_proven", "required": True,
             "receipt_path": RECEIPT, "flip_condition": {"type": "equals", "pointer": "/status",
                                                         "equals": "native_faults_passed"}, "note": ""},
            {"id": "other", "rung": "sim", "layer": "backtesting-engine", "title": "t", "status": "established",
             "owner": "this-effort", "evidence_class": "synthetic", "required": True,
             "receipt_path": RECEIPT, "flip_condition": {"type": "equals", "pointer": "/status",
                                                         "equals": "native_faults_passed"}, "note": ""},
        ]}), encoding="utf-8")

    def tearDown(self):
        self.directory.cleanup()

    def put(self, path: str, data: bytes) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def write_manifest(self, entries: dict) -> None:
        self.put(MANIFEST, json.dumps(entries).encode())

    def write_receipt(self) -> None:
        self.put(RECEIPT, json.dumps(self.receipt).encode())

    def check(self) -> dict:
        return trading_gates.check(self.root, self.gates)

    def assert_report_only(self, result: dict) -> None:
        self.assertEqual((result["status"], result["errors"], result["flip_candidates"]), ("passed", [], []))
        self.assertEqual(result["rung_ready"], {"sim": True, "paper": True, "live": True})
        self.assertEqual({row["id"]: row["condition_holds"] for row in result["rows"]}, {GATE_ID: True, "other": True})

    def stale_paths(self, result: dict) -> list[str]:
        return sorted(warning["path"] for warning in result["warnings"])

    def test_current_binding_reports_nothing(self):
        result = self.check()
        self.assert_report_only(result)
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["source_bindings"], {GATE_ID: {"bound": 6, "stale": 0, "checked": True}})

    def test_only_gates_in_the_table_are_bound(self):
        self.assertNotIn("other", self.check()["source_bindings"])

    def test_released_engine_change_is_a_warning_not_a_failure(self):
        # A later engine release: runner.py changes and source-hashes.json is regenerated to match it.
        new = b"runner v2\n"
        self.put(f"{ENGINE}/runner.py", new)
        self.write_manifest({f"{ENGINE}/transport.py": sha(b"transport v1\n"), f"{ENGINE}/safety.py": sha(b"safety v1\n"),
                             f"{ENGINE}/runner.py": sha(new)})
        result = self.check()
        self.assert_report_only(result)
        self.assertEqual(result["source_bindings"][GATE_ID], {"bound": 6, "stale": 1, "checked": True})
        (warning,) = result["warnings"]
        self.assertEqual(warning["id"], GATE_ID)
        self.assertEqual(warning["path"], f"{ENGINE}/runner.py")
        self.assertEqual(warning["receipt_sha256"], sha(b"runner v1\n"))
        self.assertEqual((warning["tree_sha256"], warning["manifest_sha256"]), (sha(new), sha(new)))
        self.assertIn("until a re-run rebinds it", warning["detail"])
        # The command line keeps exit status 0 and prints the warning by default.
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = trading_gates.main(["--root", str(self.root), "--path", "gates.json"])
        printed = json.loads(stdout.getvalue())
        self.assertEqual((code, printed["status"]), (0, "passed"))
        self.assertEqual([item["path"] for item in printed["warnings"]], [f"{ENGINE}/runner.py"])
        self.assertEqual(printed["source_bindings"][GATE_ID]["stale"], 1)

    def test_manifest_drift_alone_is_reported(self):
        self.write_manifest({f"{ENGINE}/transport.py": sha(b"transport v1\n"), f"{ENGINE}/safety.py": "0" * 64,
                             f"{ENGINE}/runner.py": sha(b"runner v1\n")})
        result = self.check()
        self.assert_report_only(result)
        (warning,) = result["warnings"]
        self.assertEqual((warning["path"], warning["tree_sha256"], warning["manifest_sha256"]),
                         (f"{ENGINE}/safety.py", sha(b"safety v1\n"), "0" * 64))

    def test_harness_plan_and_order_contract_are_bound_outside_the_manifest(self):
        self.put(f"{ENGINE}/native-faults/harness.py", b"harness v2\n")
        self.put(f"{ENGINE}/native-faults/plan.json", b"{\"plan\": 2}\n")
        self.put("blueprints/us-equities/order-contract/order_contract.py", b"contract v2\n")
        result = self.check()
        self.assert_report_only(result)
        self.assertEqual(self.stale_paths(result), sorted([
            f"{ENGINE}/native-faults/harness.py", f"{ENGINE}/native-faults/plan.json",
            "blueprints/us-equities/order-contract/order_contract.py"]))
        self.assertTrue(all(warning["manifest_sha256"] is None for warning in result["warnings"]))

    def test_missing_file_and_absent_binding_are_reported(self):
        (self.root / f"{ENGINE}/transport.py").unlink()
        del self.receipt["plan_sha256"]
        self.write_receipt()
        result = self.check()
        self.assert_report_only(result)
        self.assertEqual(self.stale_paths(result), sorted([f"{ENGINE}/native-faults/plan.json", f"{ENGINE}/transport.py"]))
        missing = next(w for w in result["warnings"] if w["path"] == f"{ENGINE}/transport.py")
        self.assertIsNone(missing["tree_sha256"])
        self.assertIn("the file is missing", missing["detail"])

    def test_keys_that_leave_the_tree_are_refused_without_reading(self):
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        outside = Path(elsewhere.name) / "outside.txt"
        outside.write_text("outside\n", encoding="utf-8")
        self.receipt["engine_sources_sha256"] = {"../../../../outside.txt": "0" * 64, "/etc/hostname": "0" * 64,
                                                 "..\\safety.py": "0" * 64}
        # A symlink inside the tree that points outside it is not followed either.
        try:
            (self.root / ENGINE / "linked.py").symlink_to(outside)
        except OSError:
            self.skipTest("symlinks unavailable")
        self.receipt["engine_sources_sha256"]["linked.py"] = sha(b"outside\n")
        self.write_receipt()
        result = self.check()
        self.assert_report_only(result)
        details = {warning["path"]: warning["detail"] for warning in result["warnings"]}
        self.assertEqual(result["source_bindings"][GATE_ID]["stale"], 4)
        self.assertIn("resolves outside the tree", details[f"{ENGINE}/linked.py"])
        self.assertEqual(sum("not a relative in-tree path" in detail for detail in details.values()), 3)

    def test_symlink_loop_is_one_warning_not_an_exception(self):
        # Python 3.12 raises RuntimeError from Path.resolve() on a symlink loop; 3.13 does not.
        # Either way the loop is one warning, the check passes and the exit code stays 0.
        target = self.root / ENGINE / "runner.py"
        target.unlink()
        try:
            target.symlink_to("runner.py")
        except OSError:
            self.skipTest("symlinks unavailable")
        result = self.check()
        self.assert_report_only(result)
        self.assertEqual(result["source_bindings"][GATE_ID], {"bound": 6, "stale": 1, "checked": True})
        (warning,) = result["warnings"]
        self.assertEqual((warning["path"], warning["tree_sha256"]), (f"{ENGINE}/runner.py", None))
        self.assertTrue("symlink loop" in warning["detail"] or "the file is missing" in warning["detail"],
                        warning["detail"])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = trading_gates.main(["--root", str(self.root), "--path", "gates.json"])
        printed = json.loads(stdout.getvalue())
        self.assertEqual((code, printed["status"], printed["errors"]), (0, "passed", []))
        self.assertEqual([item["path"] for item in printed["warnings"]], [f"{ENGINE}/runner.py"])

    def test_deeply_nested_manifest_is_one_warning_not_an_exception(self):
        # json raises RecursionError (a RuntimeError) on nesting deeper than the interpreter's limit.
        self.put(MANIFEST, b"[" * 200000 + b"]" * 200000)
        result = self.check()
        self.assert_report_only(result)
        (warning,) = result["warnings"]
        self.assertEqual(warning["path"], MANIFEST)
        self.assertIn("release manifest unreadable (RecursionError)", warning["detail"])
        self.assertEqual(result["source_bindings"][GATE_ID], {"bound": 6, "stale": 0, "checked": True})

    def test_unreadable_receipt_or_manifest_never_raises(self):
        self.put(MANIFEST, b"not json")
        result = self.check()
        self.assert_report_only(result)
        self.assertEqual([w["path"] for w in result["warnings"]], [MANIFEST])
        self.assertEqual(result["source_bindings"][GATE_ID]["stale"], 0)
        self.put(RECEIPT, b"not json")
        result = self.check()
        # The flip condition already fails the established gate; the binding only adds one warning
        # (it stops before the manifest, and the other gate is not in the table).
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["source_bindings"][GATE_ID], {"bound": 0, "stale": 0, "checked": False})
        self.assertEqual([w["path"] for w in result["warnings"]], [RECEIPT])
        self.assertIn("receipt unreadable", result["warnings"][0]["detail"])


class RepositoryBindingTests(unittest.TestCase):
    """Read-only checks against this tree. They never assert that the binding is
    current: a stale binding is printed to stderr and the test still passes."""

    @classmethod
    def setUpClass(cls):
        cls.receipt_path = ROOT / RECEIPT
        if not cls.receipt_path.is_file():
            raise unittest.SkipTest("native-faults receipt not present in this tree")
        cls.receipt = json.loads(cls.receipt_path.read_text(encoding="utf-8"))

    def test_table_matches_the_receipt_the_harness_writes(self):
        # The harness records engine_sources_sha256 keys relative to ENGINE = HERE.parent,
        # the directory above native-faults/, which is the table's base directory.
        spec = trading_gates.SOURCE_BINDINGS[GATE_ID]
        self.assertEqual(spec["maps"], {"/engine_sources_sha256": ENGINE})
        harness = (ROOT / ENGINE / "native-faults/harness.py").read_text(encoding="utf-8")
        self.assertIn("ENGINE = HERE.parent", harness)
        self.assertTrue(self.receipt["engine_sources_sha256"])
        for key in self.receipt["engine_sources_sha256"]:
            path = trading_gates.bound_path(ENGINE, key)
            self.assertIsNotNone(path, key)
            self.assertTrue((ROOT / path).is_file(), path)
        for pointer, path in spec["files"].items():
            self.assertIn(pointer.lstrip("/"), self.receipt)
            self.assertTrue((ROOT / path).is_file(), path)

    def test_stale_binding_is_reported_not_failed(self):
        result = trading_gates.check(ROOT, ROOT / trading_gates.GATES)
        binding = result["source_bindings"].get(GATE_ID)
        self.assertIsNotNone(binding)
        self.assertTrue(binding["checked"])
        self.assertEqual(binding["bound"], 6)
        self.assertEqual(result["status"], "passed" if not result["errors"] else "failed")
        for warning in result["warnings"]:
            print(f"trading_gates source-binding warning (report-only): {warning['id']}: {warning['path']}: "
                  f"{warning['detail']}", file=sys.stderr)


if __name__ == "__main__":
    unittest.main()
