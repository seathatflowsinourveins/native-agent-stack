"""Exercise retained-receipt provenance without accessing the host's receipts."""

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "north_star_readiness", ROOT / "tools/north-star/build_readiness.py"
)
READINESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(READINESS)


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="north-star-receipts-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repo"
        self.state = Path(temporary.name) / "state"
        self.root.mkdir()
        self.state.mkdir()

    def receipts(self, raw, **source_fields):
        path = self.root / "receipt.json"
        path.write_bytes(raw)
        return READINESS.Receipts(self.root, self.state, {
            "receipt": {"root": "repo", "path": path.name, **source_fields},
        })

    def test_json_rejects_duplicate_keys_and_non_json_constants(self):
        for raw in (
            b'{"state":"open","state":"accepted"}',
            b'{"outer":{"state":"open","state":"accepted"}}',
            b'{"state":NaN}', b'{"state":Infinity}', b'{"state":-Infinity}',
        ):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                READINESS.unique_json(raw)

    def test_json_preserves_valid_false_null_and_unicode(self):
        self.assertEqual(
            {"accepted": False, "invoke": None, "title": "α"},
            READINESS.unique_json('{"accepted":false,"invoke":null,"title":"α"}'.encode()),
        )

    def test_identity_and_claim_use_the_same_original_bytes(self):
        raw = '{ "accepted" : false, "title" : "α" }\r\n'.encode()
        receipts = self.receipts(raw)
        identity = dict(receipts.get("receipt"))
        (self.root / "receipt.json").write_bytes(b'{"accepted":true,"title":"changed"}')
        claim = receipts.claim({"source": "receipt", "pointer": "/accepted"})
        self.assertIs(claim["value"], False)
        self.assertEqual("RECORDED", claim["status"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), identity["sha256"])
        self.assertEqual(identity["sha256"], claim["receipt"]["sha256"])
        self.assertEqual("/accepted", claim["receipt"]["locator"])
        self.assertEqual("α", receipts.document("receipt")["title"])
        reencoded = json.dumps(receipts.document("receipt"), sort_keys=True).encode()
        self.assertNotEqual(hashlib.sha256(reencoded).hexdigest(), identity["sha256"])

    def test_declared_digest_mismatch_blocks_a_well_formed_claim(self):
        raw = b'{"state":"accepted"}\n'
        receipts = self.receipts(raw, expected_sha256="0" * 64)
        claim = receipts.claim({"source": "receipt", "pointer": "/state"})
        self.assertEqual("UNVERIFIED", claim["status"])
        self.assertIsNone(claim["value"])
        self.assertIsNone(receipts.document("receipt"))
        self.assertEqual("0" * 64, receipts.get("receipt")["expected_sha256"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), claim["receipt"]["sha256"])

    def test_invalid_json_retains_raw_identity_without_a_claim(self):
        raw = b'{"state":"open","state":"accepted"}'
        receipts = self.receipts(raw)
        self.assertIsNone(receipts.document("receipt"))
        claim = receipts.claim({"source": "receipt", "pointer": "/state"})
        self.assertEqual("UNVERIFIED", claim["status"])
        self.assertIsNone(claim["value"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), claim["receipt"]["sha256"])
        self.assertIn("duplicate", receipts.get("receipt")["reason"])

    def test_missing_and_ambiguous_text_selectors_are_unknown(self):
        regex = r"^gate=(?P<value>[^\n]+)$"
        for raw in (b"no gate here\n", b"gate=open\ngate=accepted\n"):
            with self.subTest(raw=raw):
                receipts = self.receipts(raw)
                claim = receipts.claim({"source": "receipt", "regex": regex})
                self.assertEqual("UNVERIFIED", claim["status"])
                self.assertIsNone(claim["value"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), claim["receipt"]["sha256"])
        receipts = self.receipts(b"heading\ngate=open\n")
        claim = receipts.claim({"source": "receipt", "regex": regex})
        self.assertEqual("open", claim["value"])
        self.assertEqual("RECORDED", claim["status"])
        self.assertTrue(claim["receipt"]["locator"].startswith("line:2;"))

    def test_missing_file_absent_field_and_null_do_not_fabricate_values(self):
        receipts = self.receipts(b'{"invoke":null}')
        for pointer in ("/absent", "/invoke"):
            with self.subTest(pointer=pointer):
                claim = receipts.claim({"source": "receipt", "pointer": pointer})
                self.assertIsNone(claim["value"])
                self.assertEqual("UNVERIFIED", claim["status"])
        (self.root / "receipt.json").unlink()
        missing = READINESS.Receipts(self.root, self.state, receipts.sources)
        claim = missing.claim({"source": "receipt", "pointer": "/state"})
        self.assertIsNone(claim["value"])
        self.assertIsNone(claim["receipt"]["sha256"])
        self.assertEqual("UNVERIFIED", claim["status"])

    def test_invalid_array_indices_do_not_select_another_gate(self):
        receipts = self.receipts(b'{"gates":["open","accepted"]}')
        for pointer in ("/gates/-1", "/gates/01", "/gates/+1", "/gates/1.0"):
            with self.subTest(pointer=pointer):
                claim = receipts.claim({"source": "receipt", "pointer": pointer})
                self.assertEqual("UNVERIFIED", claim["status"])
                self.assertIsNone(claim["value"])
        self.assertEqual("accepted", receipts.claim({"source": "receipt", "pointer": "/gates/1"})["value"])

    def test_sources_cannot_escape_their_declared_roots(self):
        for path in ("../state/outside.json", str(self.state / "outside.json")):
            with self.subTest(path=path):
                receipts = READINESS.Receipts(self.root, self.state, {
                    "receipt": {"root": "repo", "path": path},
                })
                with self.assertRaises(ValueError):
                    receipts.get("receipt")
        outside = self.state / "outside.json"
        outside.write_bytes(b'{"state":"accepted"}')
        (self.root / "link.json").symlink_to(outside)
        receipts = READINESS.Receipts(self.root, self.state, {
            "receipt": {"root": "repo", "path": "link.json"},
        })
        with self.assertRaises(ValueError):
            receipts.get("receipt")

    def test_missing_source_reason_does_not_export_an_absolute_root(self):
        receipts = READINESS.Receipts(self.root, self.state, {
            "missing": {"root": "repo", "path": "missing.json"},
        })
        record = receipts.get("missing")
        self.assertEqual("UNVERIFIED", record["status"])
        self.assertIsNone(record["sha256"])
        self.assertNotIn(str(self.root), json.dumps(record))
        self.assertNotIn(str(self.state), json.dumps(record))


class ReadinessBuilderTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="north-star-builder-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repo"
        self.state = Path(temporary.name) / "state"
        self.root.mkdir()
        self.state.mkdir()
        self.spec_path = self.root / "tools/north-star/sources.json"
        winner = {
            "component_id": "shared-tool", "repository": "https://example.test/tool",
            "pin": "v1", "evidence_class": "selected", "recipe_ref": "recipes/tool.md",
        }
        self.write_json("foundation.json", {"checked_at": "2026-10-08", "layers": [
            {"layer_id": "layer-b", "title": "Layer B", "winners": [dict(winner)]},
            {"layer_id": "layer-a", "title": "Layer A", "winners": [dict(winner)]},
        ]})
        self.write_json("stack.json", {"components": [{
            "id": "shared-tool", "version": "v1", "evidence_ids": ["install-fixture"],
            "commands": {"install": "tool install", "invoke": "tool --version"},
        }]})
        support = self.write_json("receipts/install.json", {"kind": "install-fixture", "pin": "v1"})
        self.write_json("evidence.json", {
            "receipts": [{"id": "install-fixture", "path": "receipts/install.json"}],
            "files": [{"path": "receipts/install.json", "sha256": hashlib.sha256(support).hexdigest()}],
        })
        self.write_json("profile.json", {"entries": [{
            "component_id": "shared-tool", "pin": "v1", "install": "tool install",
            "acceptance": "documented fixture", "provisioning_status": "documented",
        }]})
        self.write_json("gate.json", {"state": "open", "owner": "fixture-lane"})
        self.write_json("sdk-contract.json", {"schema_version": 1})
        self.spec = {
            "schema_version": 1,
            "sources": {name: {"root": "repo", "path": path} for name, path in (
                ("foundation", "foundation.json"), ("stack", "stack.json"),
                ("evidence", "evidence.json"), ("profile", "profile.json"),
                ("gate", "gate.json"), ("sdk_contract", "sdk-contract.json"),
            )},
            "gates": [{"id": "G1", "title": "Fixture gate", "fields": {
                "state": {"source": "gate", "pointer": "/state"},
                "owner": {"source": "gate", "pointer": "/owner"},
            }}],
            "data": [], "paper": [], "rnd_inputs": [], "open_items": [], "observations": [],
        }
        self.spec["sources"]["sdk_rows"] = {"root": "state", "path": "sdk/index.json"}
        self.save_spec()

    def write_json(self, path, value, *, state=False):
        destination = (self.state if state else self.root) / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
        destination.write_bytes(raw)
        return raw

    def save_spec(self):
        self.write_json("tools/north-star/sources.json", self.spec)

    def build(self):
        return READINESS.build(self.root, self.state, self.spec_path)

    def run_main(self, *arguments):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = READINESS.main([
                "--root", str(self.root), "--state-root", str(self.state),
                "--sources", str(self.spec_path), *arguments,
            ])
        return code, output.getvalue()

    def sdk_item(self, *, declared_hash=None, receipt_changes=None, raw_receipt=None):
        fields = {
            "id": "fixture-sdk", "title": "Fixture SDK", "repository": "https://example.test/sdk",
            "pin": "v1", "install": {"command": "sdk --version", "exit_code": 0},
            "native": {"command": "sdk fixture", "exit_code": 0},
            "fresh_session": {"command": "sdk fresh-fixture", "exit_code": 0},
            "evidence_class": "native_proven", "designated_reader": {"state": "pending"},
            "limitations": ["synthetic fixture"], "primary_sources": ["https://example.test/sdk/docs"],
        }
        receipt = dict(fields)
        receipt.update(receipt_changes or {})
        path = self.state / "sdk/item.json"
        raw = self.write_json("sdk/item.json", receipt, state=True)
        if raw_receipt is not None:
            raw = raw_receipt
            path.write_bytes(raw)
        item = dict(fields, receipt_path=str(path),
                    receipt_sha256=declared_hash or hashlib.sha256(raw).hexdigest())
        self.write_json("sdk/index.json", {"items": [item]}, state=True)
        return item

    def test_shared_component_remains_selected_in_each_layer(self):
        manifest = self.build()
        self.assertEqual(["layer-a", "layer-b"], [row["id"] for row in manifest["layers"]])
        tools = [row["selected_tools"][0] for row in manifest["layers"]]
        self.assertEqual(["shared-tool", "shared-tool"], [row["id"] for row in tools])
        for tool in tools:
            self.assertEqual("v1", tool["fields"]["pin"]["value"])
            self.assertIs(tool["fields"]["pin_agreement"]["value"], True)
            self.assertEqual("install-fixture", tool["supporting_receipts"][0]["id"])
            for field in ("install_receipt", "fresh_session_invoke"):
                self.assertIsNone(tool["fields"][field]["value"])
                self.assertEqual("UNVERIFIED", tool["fields"][field]["status"])
        self.assertNotEqual(tools[0]["fields"]["pin"]["receipt"]["locator"],
                            tools[1]["fields"]["pin"]["receipt"]["locator"])

    def test_changed_gate_anchor_cannot_confer_closure(self):
        raw = (self.root / "gate.json").read_bytes()
        self.spec["sources"]["gate"]["expected_sha256"] = hashlib.sha256(raw).hexdigest()
        self.save_spec()
        self.assertEqual("open", self.build()["gates"][0]["fields"]["state"]["value"])
        self.write_json("gate.json", {"state": "accepted", "owner": "fixture-lane"})
        claim = self.build()["gates"][0]["fields"]["state"]
        self.assertEqual("UNVERIFIED", claim["status"])
        self.assertIsNone(claim["value"])

    def test_source_index_digest_binds_the_snapshot_that_was_parsed(self):
        original = self.spec_path.read_bytes()
        read_bytes = Path.read_bytes

        def replace_after_read(path):
            raw = read_bytes(path)
            if path == self.spec_path:
                path.write_bytes(b'{"schema_version":2,"sources":{}}\n')
            return raw

        with mock.patch.object(Path, "read_bytes", autospec=True, side_effect=replace_after_read):
            manifest = self.build()
        self.assertEqual("open", manifest["gates"][0]["fields"]["state"]["value"])
        self.assertEqual(hashlib.sha256(original).hexdigest(), manifest["source_index"]["sha256"])
        self.assertNotEqual(hashlib.sha256(self.spec_path.read_bytes()).hexdigest(),
                            manifest["source_index"]["sha256"])

    def test_outside_source_index_is_rejected_before_reading_bytes(self):
        outside = self.state / "outside-sources.json"
        outside.write_bytes(self.spec_path.read_bytes())
        link = self.root / "external-sources.json"
        link.symlink_to(outside)
        for path in (outside, link):
            with self.subTest(path=path):
                with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("outside source read")):
                    with self.assertRaises(ValueError):
                        READINESS.build(self.root, self.state, path)

    def test_portable_export_keeps_source_identity_and_locators(self):
        raw = self.write_json("gate.json", {
            "state": "open", "owner": "/home/example/work/gate.json",
            "mac_path": "/Users/example/work/gate.json",
        })
        self.spec["gates"][0]["fields"]["mac_path"] = {"source": "gate", "pointer": "/mac_path"}
        self.save_spec()
        manifest = self.build()
        exported = READINESS.render(manifest)
        self.assertNotIn(b"/home/example", exported)
        self.assertNotIn(b"/Users/example", exported)
        self.assertIn(b"${USER_HOME}", exported)
        document = json.loads(exported)
        digest = hashlib.sha256(raw).hexdigest()
        self.assertEqual(digest, document["receipts"]["gate"]["sha256"])
        for field, original in (("owner", "/home/example/work/gate.json"),
                                ("mac_path", "/Users/example/work/gate.json")):
            claim = document["gates"][0]["fields"][field]
            self.assertEqual("${USER_HOME}/work/gate.json", claim["value"])
            self.assertEqual(digest, claim["receipt"]["sha256"])
            self.assertEqual("/" + field, claim["receipt"]["locator"])
            self.assertEqual(original, manifest["gates"][0]["fields"][field]["value"])
        self.assertEqual(raw, (self.root / "gate.json").read_bytes())

    def test_write_check_is_deterministic_and_detects_source_drift(self):
        output = self.root / READINESS.OUTPUT
        self.assertEqual(1, self.run_main("--check")[0])
        self.assertFalse(output.exists())
        self.assertEqual(0, self.run_main("--write")[0])
        original = output.read_bytes()
        self.assertEqual(0, self.run_main("--check")[0])
        self.assertEqual(0, self.run_main("--write")[0])
        self.assertEqual(original, output.read_bytes())
        self.assertEqual(original, READINESS.render(self.build()))
        changed = self.write_json("gate.json", {"state": "open", "owner": "next-fixture-lane"})
        self.assertEqual(1, self.run_main("--check")[0])
        self.assertEqual(original, output.read_bytes())
        self.assertEqual(0, self.run_main("--write")[0])
        refreshed = output.read_bytes()
        self.assertNotEqual(original, refreshed)
        document = json.loads(refreshed)
        self.assertEqual("next-fixture-lane", document["gates"][0]["fields"]["owner"]["value"])
        self.assertEqual(hashlib.sha256(changed).hexdigest(), document["receipts"]["gate"]["sha256"])
        self.assertEqual(0, self.run_main("--check")[0])

    def test_missing_expected_sdk_has_no_invented_execution(self):
        self.spec["sdk"] = {"expected_ids": ["fixture-sdk"], "owner": {"source": "gate", "pointer": "/owner"}}
        self.save_spec()
        item = self.build()["sdk_frameworks"]["items"][0]
        self.assertEqual("fixture-sdk", item["id"])
        self.assertEqual("UNVERIFIED", item["receipt_binding"])
        self.assertIsNone(item["fields"]["evidence_class"]["value"])
        self.assertEqual("fixture-lane", item["fields"]["owner"]["value"])

    def test_sdk_digest_mismatch_cannot_carry_native_proven(self):
        self.sdk_item(declared_hash="0" * 64)
        item = self.build()["sdk_frameworks"]["items"][0]
        self.assertEqual("UNVERIFIED", item["receipt_binding"])
        self.assertIsNone(item["fields"]["evidence_class"]["value"])
        self.assertEqual("UNVERIFIED", item["fields"]["evidence_class"]["status"])

    def test_sdk_index_cannot_promote_a_different_receipt_claim(self):
        self.sdk_item(receipt_changes={"evidence_class": "metadata_only"})
        item = self.build()["sdk_frameworks"]["items"][0]
        self.assertEqual("UNVERIFIED", item["fields"]["evidence_class"]["status"])
        self.assertIsNone(item["fields"]["evidence_class"]["value"])

    def test_sdk_hash_of_non_json_bytes_cannot_carry_native_proven(self):
        self.sdk_item(raw_receipt=b"this is a retained file, not an SDK receipt\n")
        item = self.build()["sdk_frameworks"]["items"][0]
        self.assertEqual("UNVERIFIED", item["fields"]["evidence_class"]["status"])
        self.assertIsNone(item["fields"]["evidence_class"]["value"])

    def test_valid_sdk_claim_does_not_turn_pending_reader_into_approval(self):
        self.sdk_item()
        item = self.build()["sdk_frameworks"]["items"][0]
        self.assertEqual("MATCH", item["receipt_binding"])
        self.assertEqual("native_proven", item["fields"]["evidence_class"]["value"])
        self.assertEqual({"state": "pending"}, item["fields"]["designated_reader"]["value"])

    def test_sdk_without_contract_does_not_carry_execution_claims(self):
        self.sdk_item()
        (self.root / "sdk-contract.json").unlink()
        item = self.build()["sdk_frameworks"]["items"][0]
        self.assertEqual("UNVERIFIED", item["fields"]["evidence_class"]["status"])
        self.assertIsNone(item["fields"]["evidence_class"]["value"])

    def test_fragment_escapes_untrusted_values_in_every_table(self):
        manifest = self.build()
        manifest["gates"][0]["id"] = "<img src=x onerror=alert(1)>"
        manifest["gates"][0]["fields"]["state"]["value"] = "<script>gate()</script>"
        manifest["gates"][0]["fields"]["owner"]["value"] = 'owner & "quoted"'
        manifest["layers"][0]["id"] = "<Layer&>"
        tool = manifest["layers"][0]["selected_tools"][0]
        tool["id"] = "<tool>"
        tool["fields"]["pin"]["value"] = "<v&>"
        manifest["sdk_frameworks"]["items"] = [{"id": "<SDK>", "receipt_binding": "<MATCH>"}]
        fragment = READINESS.render_fragment(manifest)
        self.assertNotIn("<script>", fragment)
        self.assertNotIn("<img ", fragment)
        for escaped in ("&lt;img", "&lt;script&gt;", "owner &amp; &quot;quoted&quot;",
                        "&lt;Layer&amp;&gt;", "&lt;tool&gt;", "&lt;v&amp;&gt;", "&lt;SDK&gt;", "&lt;MATCH&gt;"):
            self.assertIn(escaped, fragment)


if __name__ == "__main__":
    unittest.main()
