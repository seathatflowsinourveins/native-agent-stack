"""R3-F2 mutation checks of the real verifier; synthetic, not scientific acceptance.

Harness: CPython unittest/tempfile/importlib; seed: published metadata packet at
36e36ea498e23ffd5bfc103035a2da883a6a08e4. No study outcomes or external evidence read.
"""
import hashlib
from contextlib import redirect_stderr, redirect_stdout
import errno
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PACKET = Path(__file__).resolve().parents[1] / "blueprints/us-equities/event-anchored-ranking"
SCRIPT = PACKET / "R3-VERIFY.py"
SPEC = importlib.util.spec_from_file_location("r3_verify", SCRIPT)
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class R3VerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="r3-verify-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "packet"
        self.root.mkdir()
        self.members = [line[66:] for line in (PACKET / "SHA256SUMS").read_text().splitlines()]
        for name in self.members:
            shutil.copyfile(PACKET / name, self.root / name)
        self.seal()

    def read(self, name):
        return json.loads((self.root / name).read_text())

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value, indent=2) + "\n")

    def seal(self, update_row=True):
        # Keep the unrelated carrier/ROW bindings valid when mutating a protocol leaf.
        if update_row:
            row = self.read("ROW14-SUBMISSION-R3.json")
            row["protocol"]["sha256"] = sha(self.root / "protocol.draft.json")
            row["R3B_corrections"]["verifier"]["sha256"] = sha(self.root / "R3-VERIFY.py")
            self.write("ROW14-SUBMISSION-R3.json", row)
        carrier = "".join(f"{sha(self.root / name)}  {name}\n" for name in self.members)
        for name in ("SHA256SUMS", "SHA256SUMS.R3", "SHA256SUMS.R3B"):
            (self.root / name).write_text(carrier)

    def failed(self, text):
        result = VERIFIER.verify(self.root)
        self.assertEqual(result["status"], "FAIL", result["errors"])
        self.assertTrue(any(text in error for error in result["errors"]), result["errors"])
        return result

    def test_valid_bundle_and_unique_binding_occurrences(self):
        result = VERIFIER.verify(self.root)
        self.assertEqual(result["status"], "PASS", result["errors"])
        locations = [(item["file"], item["pointer"]) for item in result["internal_bindings"]]
        self.assertEqual(len(locations), len(set(locations)))
        # 17 distinct digest locations, independently enumerated in the seed packet.
        self.assertEqual(len(locations), 17)

    def test_exact_committed_bundle_passes_without_resealing(self):
        result = VERIFIER.verify(PACKET)
        self.assertEqual(result["status"], "PASS", result["errors"])
        self.assertEqual(result["internal_binding_count"], 17)
        self.assertEqual(result["internal_binding_count"], len(result["internal_bindings"]))
        self.assertIn("digest JSON-pointer", result["binding_count_scope"])
        cli = subprocess.run([sys.executable, str(SCRIPT), "--root", str(PACKET)],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertEqual(json.loads(cli.stdout)["status"], "PASS")

    def test_changed_member_bytes_without_resealing_are_detected(self):
        path = self.root / "R2-CONSTRUCTION.json"
        path.write_bytes(path.read_bytes() + b"\n")
        self.failed("carrier mismatch: R2-CONSTRUCTION.json")

    def test_wrong_row_digest_without_resealing_is_detected(self):
        row = self.read("ROW14-SUBMISSION-R3.json")
        row["contracts"]["R2-CONSTRUCTION.json"] = "0" * 64
        self.write("ROW14-SUBMISSION-R3.json", row)
        self.failed("internal binding mismatch")

    def test_retarget_to_another_valid_member_is_rejected(self):
        protocol = self.read("protocol.draft.json")
        target = "R2-COMPARISON.json"
        protocol["R2_bound_contracts"]["construction"] = {"path": target, "sha256": sha(self.root / target)}
        self.write("protocol.draft.json", protocol)
        self.seal()
        result = self.failed("mandatory target")
        self.assertFalse(any("carrier mismatch" in item or "internal binding mismatch" in item for item in result["errors"]))

    def test_deep_json_decoder_failure_returns_json(self):
        depth = sys.getrecursionlimit() + 100
        (self.root / "protocol.draft.json").write_bytes(b'{"nested":' + b'[' * depth + b'0' + b']' * depth + b'}')
        self.seal()
        self.failed("RecursionError")
        self.assert_cli_failure()

    def test_huge_integer_decoder_failure_returns_json(self):
        original = sys.get_int_max_str_digits()
        self.addCleanup(sys.set_int_max_str_digits, original)
        sys.set_int_max_str_digits(4300)
        (self.root / "protocol.draft.json").write_text('{"number":' + "1" * 4400 + '}')
        self.seal()
        self.failed("ValueError")
        self.assert_cli_failure(interpreter_args=("-X", "int_max_str_digits=4300"))

    def test_decoder_limit_error_classes_are_named(self):
        for error in (RecursionError("synthetic nesting limit"), ValueError("synthetic number limit")):
            with self.subTest(error=type(error).__name__):
                with patch.object(VERIFIER.json, "loads", side_effect=error):
                    self.failed("protocol.draft.json: " + type(error).__name__)

    def test_walker_recursion_failure_is_reported_separately(self):
        name = "synthetic-deep.json"
        marker = '{"synthetic_deep_fixture": true}'
        (self.root / name).write_text(marker)
        self.members.append(name)
        self.seal()
        nested = {}
        for _ in range(sys.getrecursionlimit() + 100):
            nested = {"nested": nested}
        native_loads = json.loads
        def loaded(value, *args, **kwargs):
            return nested if value == marker else native_loads(value, *args, **kwargs)
        with patch.object(VERIFIER.json, "loads", loaded):
            result = self.failed("JSON traversal limit: " + name)
        self.assertTrue(all(result["semantic_checks"].values()))
        self.assertFalse(any("carrier mismatch" in item for item in result["errors"]))

    def probe_failures(self, operation, target):
        original = getattr(Path, operation)
        for failure in (PermissionError(errno.EACCES, "Permission denied"),
                        OSError(errno.ENAMETOOLONG, "File name too long")):
            with self.subTest(operation=operation, errno=failure.errno):
                def failing_probe(path, *args, **kwargs):
                    if path == target:
                        raise failure
                    return original(path, *args, **kwargs)
                stdout, stderr = io.StringIO(), io.StringIO()
                with patch.object(Path, operation, failing_probe), \
                     patch.object(sys, "argv", [str(SCRIPT), "--root", str(self.root)]), \
                     redirect_stdout(stdout), redirect_stderr(stderr):
                    with self.assertRaises(SystemExit) as exit_status:
                        runpy.run_path(str(SCRIPT), run_name="__main__")
                self.assertEqual(exit_status.exception.code, 1)
                self.assertNotIn("Traceback", stderr.getvalue())
                data = json.loads(stdout.getvalue())
                self.assertEqual(data["status"], "FAIL")
                self.assertTrue(any(target.name in error for error in data["errors"]), data["errors"])
                self.assertTrue(any(failure.strerror in error for error in data["errors"]), data["errors"])

    def test_symlink_probe_oserrors_return_json_failure(self):
        self.probe_failures("is_symlink", self.root / "SHA256SUMS")

    def test_regular_file_probe_oserrors_return_json_failure(self):
        self.probe_failures("is_file", self.root / "R2-CONSTRUCTION.json")

    def test_byte_read_oserrors_return_json_failure(self):
        self.probe_failures("read_bytes", self.root / "SHA256SUMS")

    def test_optional_reference_probe_oserrors_return_json_failure(self):
        target = self.root / "optional-target.json"
        protocol = self.read("protocol.draft.json")
        protocol["synthetic_optional"] = {"path": target.name, "sha256": "f" * 64}
        self.write("protocol.draft.json", protocol)
        self.seal()
        self.probe_failures("is_file", target)

    def test_cli_root_resolution_oserrors_return_json_failure(self):
        self.probe_failures("resolve", self.root)

    def test_cli_long_carrier_filename_returns_json_failure(self):
        self.set_carrier((self.root / "SHA256SUMS").read_bytes() + ("f" * 64 + "  " + "x" * 256 + "\n").encode())
        self.assert_cli_failure()

    def test_cli_long_optional_reference_returns_json_failure(self):
        protocol = self.read("protocol.draft.json")
        protocol["synthetic_optional"] = {"path": "x" * 256, "sha256": "f" * 64}
        self.write("protocol.draft.json", protocol)
        self.seal()
        self.assert_cli_failure()

    def set_carrier(self, value):
        for name in ("SHA256SUMS", "SHA256SUMS.R3", "SHA256SUMS.R3B"):
            (self.root / name).write_bytes(value)

    def test_symlinked_carriers_and_member_fail(self):
        for name in ("SHA256SUMS", "SHA256SUMS.R3", "SHA256SUMS.R3B", "R2-CONSTRUCTION.json"):
            with self.subTest(name=name):
                path = self.root / name
                raw = path.read_bytes()
                target = Path(self.temp.name) / "link-target"
                target.write_bytes(raw)
                path.unlink()
                path.symlink_to(target)
                try:
                    self.failed("file is a symlink: " + name)
                finally:
                    path.unlink()
                    path.write_bytes(raw)

    def test_non_utf8_canonical_carrier_returns_early_failure(self):
        self.set_carrier(b"\xff")
        result = self.failed("invalid UTF-8: SHA256SUMS")
        self.assertIsNotNone(result["manifest_sha256"])
        self.assertEqual(result["semantic_checks"], {})

    def test_malformed_manifest_lines_fail(self):
        original = (self.root / "SHA256SUMS").read_bytes()
        lines = ["", "short", "f" * 64 + " one-space.json", "F" * 64 + "  uppercase.json",
                 original.decode().splitlines()[0], "f" * 64 + "  /synthetic/absolute.json",
                 "f" * 64 + "  ../parent.json", "f" * 64 + "  .", "f" * 64 + "  "]
        for line in lines:
            with self.subTest(line=line):
                self.set_carrier(original + (line + "\n").encode())
                self.failed("manifest line")

    def test_standalone_sha256_is_validated_without_becoming_a_join(self):
        for value in ("f" * 64, "F" * 64, "f" * 63, None, {}, []):
            with self.subTest(value=value):
                protocol = self.read("protocol.draft.json")
                protocol["synthetic_standalone"] = {"sha256": value}
                self.write("protocol.draft.json", protocol)
                self.seal()
                if value == "f" * 64:
                    result = VERIFIER.verify(self.root)
                    self.assertEqual(result["status"], "PASS", result["errors"])
                    self.assertEqual(result["internal_binding_count"], 17)
                else:
                    self.failed("invalid digest")

    def test_manifest_named_dict_or_list_is_an_invalid_digest(self):
        for value in ({"path": "optional.json", "sha256": "f" * 64}, [{"sha256": "f" * 64}]):
            with self.subTest(value=value):
                protocol = self.read("protocol.draft.json")
                protocol["synthetic_named"] = {"R2-CONSTRUCTION.json": value}
                self.write("protocol.draft.json", protocol)
                self.seal()
                self.failed("invalid digest")

    def test_optional_json_carrier_member_requires_object_root(self):
        name = "synthetic-list.json"
        self.write(name, [])
        self.members.append(name)
        self.seal()
        self.failed("expected JSON object: " + name)

    def test_invalid_embedded_digest_is_an_error(self):
        for value in ("F" * 64, "f" * 63, "f" * 65, "g" * 64, "f" * 64 + "\n", "", None, 123):
            with self.subTest(value=value):
                protocol = self.read("protocol.draft.json")
                protocol["R2_bound_contracts"]["construction"]["sha256"] = value
                self.write("protocol.draft.json", protocol)
                self.seal()
                self.failed("invalid digest")

    def test_invalid_hash_in_filename_map_is_an_error(self):
        row = self.read("ROW14-SUBMISSION-R3.json")
        row["contracts"]["R2-CONSTRUCTION.json"] = "F" * 64
        self.write("ROW14-SUBMISSION-R3.json", row)
        self.seal()
        self.failed("invalid digest")

    def test_missing_mandatory_target_cannot_be_an_external_boundary(self):
        for target in ("missing-contract.json", "retained-evidence:research/missing-contract.json"):
            with self.subTest(target=target):
                protocol = self.read("protocol.draft.json")
                protocol["R2_bound_contracts"]["construction"]["path"] = target
                self.write("protocol.draft.json", protocol)
                self.seal()
                self.failed("mandatory target")

    def test_missing_mandatory_join_is_an_error(self):
        protocol = self.read("protocol.draft.json")
        del protocol["R2_bound_contracts"]["construction"]
        self.write("protocol.draft.json", protocol)
        self.seal()
        self.failed("construction")

    def test_each_current_packet_object_join_is_required(self):
        # Independently list the published normative locations, including the
        # registry's exclusion contract and ROW's separate logit reference.
        joins = {
            "protocol.draft.json": [
                ("R2_bound_contracts", role) for role in
                ("construction", "comparison", "logit_operators", "inspection", "survivorship")
            ] + [("freeze_prerequisites", "inspection_registry")],
            "inspection-registry.draft.json": [("exclusion_contract",)],
            "ROW14-SUBMISSION-R3.json": [
                ("protocol",), ("registry",), ("unchanged_logit_operators",),
                ("runtime_acceptance",), ("runtime_lock_verification",), ("R3B_corrections", "verifier")
            ],
        }
        for name, pointers in joins.items():
            for keys in pointers:
                with self.subTest(file=name, pointer=keys):
                    shutil.copyfile(PACKET / name, self.root / name)
                    document = self.read(name)
                    parent = document
                    for key in keys[:-1]:
                        parent = parent[key]
                    del parent[keys[-1]]
                    self.write(name, document)
                    # seal() would repair ROW.protocol, obscuring that mutation.
                    self.seal(update_row=name != "ROW14-SUBMISSION-R3.json")
                    self.failed("/" + "/".join(keys))
            shutil.copyfile(PACKET / name, self.root / name)
            self.seal()

    def test_each_filename_keyed_contract_join_is_required(self):
        original = self.read("ROW14-SUBMISSION-R3.json")
        for name in tuple(original["contracts"]):
            with self.subTest(name=name):
                row = json.loads(json.dumps(original))
                del row["contracts"][name]
                self.write("ROW14-SUBMISSION-R3.json", row)
                self.seal()
                self.failed("/contracts/" + name)

    def test_target_removed_from_both_disk_and_carrier_is_an_error(self):
        name = "R2-INSPECTION.json"
        (self.root / name).unlink()
        self.members.remove(name)
        self.seal()
        self.failed("mandatory target")

    def test_missing_digest_and_null_join_fail(self):
        for value in ({"path": "R2-CONSTRUCTION.json"}, None):
            with self.subTest(value=value):
                protocol = self.read("protocol.draft.json")
                protocol["R2_bound_contracts"]["construction"] = value
                self.write("protocol.draft.json", protocol)
                self.seal()
                self.failed("construction")

    def test_inspection_registry_target_is_mandatory(self):
        protocol = self.read("protocol.draft.json")
        protocol["freeze_prerequisites"]["inspection_registry"]["path"] = "missing-registry.json"
        self.write("protocol.draft.json", protocol)
        self.seal()
        self.failed("mandatory target")

    def test_each_alternate_carrier_is_required(self):
        for name in ("SHA256SUMS.R3", "SHA256SUMS.R3B"):
            with self.subTest(name=name):
                self.seal()
                (self.root / name).unlink()
                self.failed(name)

    def test_carrier_difference_is_an_error(self):
        (self.root / "SHA256SUMS.R3").write_text("changed\n")
        self.failed("carrier differs")

    def test_missing_canonical_carrier_is_an_error(self):
        (self.root / "SHA256SUMS").unlink()
        result = self.failed("SHA256SUMS")
        self.assertIsNone(result["manifest_sha256"])
        self.assertEqual(result["internal_binding_count"], 0)
        self.assertEqual(result["semantic_checks"], {})

    def test_missing_member_is_an_error_without_traceback(self):
        (self.root / "R2-COMPARISON.json").unlink()
        self.failed("R2-COMPARISON.json")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO required")
    def test_nonregular_carriers_and_members_are_rejected_before_open(self):
        original_read = Path.read_bytes
        for name in ("SHA256SUMS", "SHA256SUMS.R3", "R2-CONSTRUCTION.json"):
            with self.subTest(name=name):
                target = self.root / name
                original = target.read_bytes()
                target.unlink()
                os.mkfifo(target)
                def guarded_read(path):
                    self.assertNotEqual(path, target, "nonregular file was opened; a FIFO would block")
                    return original_read(path)
                try:
                    with patch.object(Path, "read_bytes", guarded_read):
                        self.failed("not a regular file")
                finally:
                    target.unlink()
                    target.write_bytes(original)

    def test_extra_mandatory_contract_does_not_become_optional_external(self):
        protocol = self.read("protocol.draft.json")
        protocol["R2_bound_contracts"]["extra"] = {"path": "retained-evidence:research/synthetic/missing.json", "sha256": "f" * 64}
        self.write("protocol.draft.json", protocol)
        self.seal()
        self.failed("unexpected mandatory contract")

    def test_extra_filename_contract_does_not_disappear_from_walk(self):
        row = self.read("ROW14-SUBMISSION-R3.json")
        row["contracts"]["missing-contract.json"] = "f" * 64
        self.write("ROW14-SUBMISSION-R3.json", row)
        self.seal()
        self.failed("unexpected mandatory contract")

    def test_invalid_json_is_an_error_without_traceback(self):
        for name in ("protocol.draft.json", "ROW14-SUBMISSION-R3.json"):
            with self.subTest(name=name):
                # Restore the previous mutation before corrupting the other JSON member.
                shutil.copyfile(PACKET / "protocol.draft.json", self.root / "protocol.draft.json")
                shutil.copyfile(PACKET / "ROW14-SUBMISSION-R3.json", self.root / "ROW14-SUBMISSION-R3.json")
                (self.root / name).write_text("{broken\n")
                self.seal(update_row=name != "ROW14-SUBMISSION-R3.json")
                self.failed("invalid JSON")

    def test_wrong_json_root_is_an_error(self):
        self.write("protocol.draft.json", [])
        self.seal()
        self.failed("JSON object")

    def test_invalid_utf8_is_an_error(self):
        (self.root / "protocol.draft.json").write_bytes(b"\xff")
        self.seal()
        self.failed("UTF-8")

    def test_unaccepted_pit04_placeholders_cannot_hide_a_partial_binding(self):
        document = self.read("R2-SURVIVORSHIP.json")
        placeholder = document["native_PIT04_exclusions"]["accepted_layer15_receipt"]
        self.assertEqual((placeholder["path"], placeholder["sha256"]), (None, None))
        placeholder["path"] = "retained-evidence:research/synthetic/receipt.json"
        self.write("R2-SURVIVORSHIP.json", document)
        row = self.read("ROW14-SUBMISSION-R3.json")
        row["contracts"]["R2-SURVIVORSHIP.json"] = sha(self.root / "R2-SURVIVORSHIP.json")
        self.write("ROW14-SUBMISSION-R3.json", row)
        protocol = self.read("protocol.draft.json")
        protocol["R2_bound_contracts"]["survivorship"]["sha256"] = row["contracts"]["R2-SURVIVORSHIP.json"]
        self.write("protocol.draft.json", protocol)
        self.seal()
        self.failed("invalid digest")

    def test_semantic_missing_nested_field_is_an_error(self):
        protocol = self.read("protocol.draft.json")
        del protocol["models"]["main"]["runtime_state"]
        self.write("protocol.draft.json", protocol)
        self.seal()
        self.failed("semantic input")

    def test_earlier_checkpoint_digest_is_checked(self):
        protocol = self.read("protocol.draft.json")
        protocol["prior_R2_checkpoint"]["earlier_sha256"] = "F" * 64
        self.write("protocol.draft.json", protocol)
        self.seal()
        self.failed("invalid digest")

    def test_optional_external_reference_is_reported_without_being_accepted(self):
        protocol = self.read("protocol.draft.json")
        reference = "retained-evidence:research/synthetic/external.json"
        protocol["synthetic_external"] = {"path": reference, "sha256": "f" * 64}
        self.write("protocol.draft.json", protocol)
        self.seal()
        result = VERIFIER.verify(self.root)
        self.assertEqual(result["status"], "PASS", result["errors"])
        self.assertTrue(any(item["reference"] == reference for item in result["external_or_historical_boundaries"]))

    def test_cli_missing_file_returns_json_failure(self):
        (self.root / "R2-CONSTRUCTION.json").unlink()
        self.assert_cli_failure()

    def test_cli_invalid_json_returns_json_failure(self):
        (self.root / "protocol.draft.json").write_text("{broken\n")
        self.seal()
        self.assert_cli_failure()

    def assert_cli_failure(self, interpreter_args=()):
        result = subprocess.run([sys.executable, *interpreter_args, str(SCRIPT), "--root", str(self.root)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "FAIL")
        self.assertTrue(data["errors"])


if __name__ == "__main__":
    unittest.main()
