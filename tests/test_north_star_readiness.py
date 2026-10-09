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
        self.root = Path(temporary.name).resolve() / "repo"
        self.state = Path(temporary.name).resolve() / "state"
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
        self.root = Path(temporary.name).resolve() / "repo"
        self.state = Path(temporary.name).resolve() / "state"
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

    def test_cli_publication_requires_the_expected_page_digest(self):
        page = self.state / "synthetic-readiness.html"
        original = b"<html><body><main>Retained markup</main></body></html>\n"
        page.write_bytes(original)
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                code, _ = self.run_main("--write", "--publish-page", str(page))
            except SystemExit as error:
                code = error.code
        self.assertEqual(2, code)
        self.assertEqual(original, page.read_bytes())
        self.assertEqual([page], list(self.state.iterdir()))

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

    def test_sdk_receipt_through_state_symlink_preserves_its_binding(self):
        alias = self.state.with_name("state-link")
        alias.symlink_to(self.state, target_is_directory=True)
        item = self.sdk_item()
        item["receipt_path"] = str(alias / "sdk/item.json")
        self.write_json("sdk/index.json", {"items": [item]}, state=True)

        bound = self.build()["sdk_frameworks"]["items"][0]

        self.assertEqual("MATCH", bound["receipt_binding"])
        self.assertEqual("sdk/item.json", bound["item_receipt"]["path"])
        self.assertEqual("native_proven", bound["fields"]["evidence_class"]["value"])

    def test_raw_sdk_receipt_through_state_symlink_preserves_its_binding(self):
        alias = self.state.with_name("state-link")
        alias.symlink_to(self.state, target_is_directory=True)
        raw = self.write_json("sdk/raw.json", {"id": "fixture-sdk"}, state=True)
        self.sdk_item(receipt_changes={"raw_receipt": {
            "path": str(alias / "sdk/raw.json"), "sha256": hashlib.sha256(raw).hexdigest(),
        }})

        bound = self.build()["sdk_frameworks"]["items"][0]

        self.assertEqual("MATCH", bound["receipt_binding"])
        self.assertEqual("MATCH", bound["raw_receipt_binding"])
        self.assertEqual("sdk/raw.json", bound["raw_receipt"]["path"])

    def test_sdk_symlinks_cannot_escape_the_state_root(self):
        outside = self.root / "outside.json"
        outside.write_text('{"id": "fixture-sdk"}\n', encoding="utf-8")
        escaped = self.state / "escaped.json"
        escaped.symlink_to(outside)
        for raw_receipt in (False, True):
            with self.subTest(raw_receipt=raw_receipt):
                if raw_receipt:
                    self.sdk_item(receipt_changes={"raw_receipt": {
                        "path": str(escaped), "sha256": hashlib.sha256(outside.read_bytes()).hexdigest(),
                    }})
                else:
                    item = self.sdk_item()
                    item["receipt_path"] = str(escaped)
                    self.write_json("sdk/index.json", {"items": [item]}, state=True)
                with self.assertRaisesRegex(ValueError, "SDK receipt escapes state root"):
                    self.build()

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


class PagePublicationTests(unittest.TestCase):
    START = b"<!-- north-star-readiness:start -->"
    END = b"<!-- north-star-readiness:end -->"

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="north-star-page-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.page = self.directory / "synthetic-readiness.html"
        self.original = (
            b'<!doctype html>\r\n<html><body class="command-center">\r\n'
            b'<main id="retained-status">\r\n<h1>Retained readiness</h1>\r\n'
            b'<p data-keep="true">Retained markup: \xce\xb1.</p>\r\n'
            b'</main>\r\n<footer>Retained footer</footer>\r\n</body></html>\r\n'
        )
        self.page.write_bytes(self.original)
        self.manifest = {
            "gates": [{"id": "G1", "fields": {
                "state": {"value": "open", "status": "RECORDED"},
                "owner": {"value": "fixture-lane", "status": "RECORDED"},
            }}],
            "layers": [], "sdk_frameworks": {"items": []},
        }

    def files(self):
        return {path.name: path.read_bytes() for path in self.directory.iterdir()}

    def publish(self, *, expected=None, dry_run=False):
        digest = expected if expected is not None else hashlib.sha256(self.page.read_bytes()).hexdigest()
        return READINESS.publish_page(self.manifest, self.page, digest, dry_run=dry_run)

    def test_wrong_page_digest_never_mutates_or_creates_files(self):
        before = self.files()
        with self.assertRaises(ValueError):
            self.publish(expected="0" * 64)
        self.assertEqual(before, self.files())

    def test_dry_run_creates_no_files_and_predicts_publication(self):
        before = self.files()
        preview = self.publish(dry_run=True)
        self.assertEqual(before, self.files())
        self.assertIs(preview["dry_run"], True)
        self.assertEqual(hashlib.sha256(self.original).hexdigest(), preview["original_sha256"])
        self.assertNotEqual(preview["original_sha256"], preview["output_sha256"])
        self.assertGreater(preview["output_bytes"], len(self.original))
        published = self.publish()
        self.assertIs(published["dry_run"], False)
        self.assertEqual(preview["output_sha256"], hashlib.sha256(self.page.read_bytes()).hexdigest())
        self.assertEqual(preview["output_bytes"], len(self.page.read_bytes()))

    def test_publication_keeps_surrounding_bytes_and_exact_backup(self):
        old_digest = hashlib.sha256(self.original).hexdigest()
        result = self.publish()
        output = self.page.read_bytes()
        anchor = self.original.index(b"</main>")
        self.assertTrue(output.startswith(self.original[:anchor]))
        self.assertTrue(output.endswith(self.original[anchor:]))
        self.assertEqual(1, output.count(self.START))
        self.assertEqual(1, output.count(self.END))
        self.assertEqual(old_digest, result["original_sha256"])
        self.assertEqual(hashlib.sha256(output).hexdigest(), result["output_sha256"])
        backup = self.page.with_name(self.page.name + ".receipt-backup-" + old_digest[:16])
        self.assertEqual(self.original, backup.read_bytes())

    def test_repeated_publication_replaces_one_block_idempotently(self):
        self.publish()
        first = self.page.read_bytes()
        self.publish()
        self.assertEqual(first, self.page.read_bytes())
        self.manifest["gates"][0]["fields"]["owner"]["value"] = "next-fixture-lane"
        self.publish()
        refreshed = self.page.read_bytes()
        self.assertEqual(1, refreshed.count(self.START))
        self.assertEqual(1, refreshed.count(self.END))
        self.assertIn(b"next-fixture-lane", refreshed)
        self.assertNotEqual(first, refreshed)
        anchor = self.original.index(b"</main>")
        self.assertTrue(refreshed.startswith(self.original[:anchor]))
        self.assertTrue(refreshed.endswith(self.original[anchor:]))

    def test_body_is_fallback_when_main_is_not_unique(self):
        for raw in (
            b"<html><body><p>No main here</p></body></html>\n",
            b"<html><body><main>One</main><main>Two</main></body></html>\n",
        ):
            with self.subTest(raw=raw):
                self.page.write_bytes(raw)
                self.publish()
                output = self.page.read_bytes()
                anchor = raw.index(b"</body>")
                self.assertTrue(output.startswith(raw[:anchor]))
                self.assertTrue(output.endswith(raw[anchor:]))
                self.assertEqual(1, output.count(self.START))

    def test_fragment_footer_fallback_preserves_the_wrapper(self):
        footer = b'<section aria-labelledby="l" class="foot">'
        raw = (
            b'<div id="retained-wrapper">\r\n'
            b'<section aria-labelledby="r"><h1>Retained readiness</h1></section>\r\n'
            + footer + b'<p>Retained footer</p></section>\r\n</div>\r\n'
        )
        self.page.write_bytes(raw)
        self.publish()
        output = self.page.read_bytes()
        anchor = raw.index(footer)
        self.assertTrue(output.startswith(raw[:anchor]))
        self.assertTrue(output.endswith(raw[anchor:]))
        self.assertLess(output.index(self.START), output.index(footer))
        self.assertEqual(1, output.count(self.START))
        self.assertEqual(1, output.count(self.END))
        self.publish()
        self.assertEqual(output, self.page.read_bytes())

    def test_broken_marker_blocks_fail_before_backup_or_mutation(self):
        blocks = (
            self.START + b" orphan",
            b"orphan " + self.END,
            self.END + b" reversed " + self.START,
            self.START + self.START + b" nested " + self.END + self.END,
            self.START + b"one" + self.END + self.START + b"two" + self.END,
            self.START + b"one" + self.END + self.END,
        )
        for block in blocks:
            with self.subTest(block=block):
                self.page.write_bytes(b"<html><body><main>" + block + b"</main></body></html>\n")
                before = self.files()
                with self.assertRaises(ValueError):
                    self.publish()
                self.assertEqual(before, self.files())

    def test_missing_or_ambiguous_anchors_fail_before_backup_or_mutation(self):
        for raw in (
            b"<html><p>No insertion anchor</p></html>\n",
            b"<main>One</main><main>Two</main>\n",
            b"<body>One</body><body>Two</body>\n",
            b"<body><main>One</main><main>Two</main></body></body>\n",
        ):
            with self.subTest(raw=raw):
                self.page.write_bytes(raw)
                before = self.files()
                with self.assertRaises(ValueError):
                    self.publish()
                self.assertEqual(before, self.files())


if __name__ == "__main__":
    unittest.main()
