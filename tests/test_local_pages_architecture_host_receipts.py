"""The local host index is the entire authorized read boundary."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("architecture_host_receipts", ROOT / "tools/local-pages/architecture_evidence.py")
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


class HostReceiptsIndexTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name)
        self.index = self.state / "coordination/command-center/pages/host-receipts-index.json"
        policy = json.loads((ROOT / "tools/local-pages/source_policy.json").read_text())
        policy["architecture"] = {"architecture_projection": [{"root": "state", "path": "coordination/command-center/pages/host-receipts-index.json"}]}
        policy["architecture_inventory_aliases"] = []
        policy_path = self.state.parent / (self.state.name + "-independent-policy.json")
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
        self.addCleanup(lambda: policy_path.unlink(missing_ok=True))
        approval = patch.object(evidence, "SOURCE_POLICY_PATH", policy_path)
        approval.start()
        self.addCleanup(approval.stop)
        self.reads = evidence.architecture_reads(ROOT, self.state)

    def row(self, **changes):
        return {"path": "command-center/windows/window-u-20261008/RECEIPT.md", "sha256": "a" * 64, "bytes": 42, "title": "Install receipt: PASS npm test", "mtime_utc": "2026-10-08T16:25:10Z", **changes}

    def write(self, rows=None, **changes):
        self.index.parent.mkdir(parents=True, exist_ok=True)
        document = {"schema": "host-receipts-index/1", "generated_utc": "2026-10-09T03:45:30Z", "scope": "CC-written host receipts only", "receipts": rows if rows is not None else [self.row()], **changes}
        raw = json.dumps(document).encode()
        self.index.write_bytes(raw)
        return raw

    def test_fourteen_records_require_zero_raw_receipt_reads_stats_or_hashes(self):
        rows = [self.row(path=f"command-center/windows/window-{index}-20261008/RECEIPT.md") for index in range(13)]
        rows.append(self.row(path="command-center/host-changes-20261008/changes.md"))
        raw = self.write(rows)
        target = self.state / "coordination" / rows[0]["path"]
        target.parent.mkdir(parents=True)
        target.write_text("RAW RECEIPT MUST NEVER BE OPENED", encoding="utf-8")
        expected_digest = hashlib.sha256(raw).hexdigest()
        original_open, original_hash = os.open, hashlib.sha256
        opened = []

        def index_only_open(path, *args, **kwargs):
            candidate = Path(os.fsdecode(path))
            if not candidate.is_absolute() and kwargs.get("dir_fd") is not None:
                candidate = Path(os.readlink("/proc/self/fd/" + str(kwargs["dir_fd"]))) / candidate
            self.assertIn(candidate, {self.index, *self.index.parents})
            if candidate == self.index:
                opened.append(str(candidate))
            return original_open(path, *args, **kwargs)

        def index_only_hash(value=b",", *args, **kwargs):
            self.assertEqual(value, raw)
            return original_hash(value, *args, **kwargs)

        original_stat = Path.stat
        def index_only_stat(path, *args, **kwargs):
            self.assertIn(path, {self.index, *self.index.parents})
            return original_stat(path, *args, **kwargs)
        with patch.object(os, "open", side_effect=index_only_open), patch.object(hashlib, "sha256", side_effect=index_only_hash), patch.object(Path, "stat", autospec=True, side_effect=index_only_stat), patch.object(Path, "read_text", side_effect=AssertionError("raw reads forbidden")), patch.object(Path, "read_bytes", side_effect=AssertionError("raw reads forbidden")), patch.object(Path, "glob", side_effect=AssertionError("directory scans forbidden")), patch.object(Path, "iterdir", side_effect=AssertionError("directory scans forbidden")):
            result = evidence.host_receipts_index(self.state, reads=self.reads)
        self.assertEqual(opened, [str(self.index)])
        self.assertEqual(len(result["items"]), 14)
        self.assertEqual(result["sources"][0]["sha256"], expected_digest)
        self.assertEqual(result["sources"][0]["bytes"], len(raw))
        self.assertEqual(result["coverage"]["rejected_receipts"], 0)
        for item in result["items"]:
            self.assertEqual(item["label"], "local host receipt (state root)")
            self.assertEqual(item["receipt_hash_status"], "index-declared hash")
            self.assertEqual(item["mtime_status"], "index-provided file metadata")
            self.assertFalse(item["native_acceptance"])
            self.assertFalse(item["vendor_acceptance"])
            self.assertNotIn("result", item)
            self.assertNotIn("command", item)
            self.assertNotIn("e2e", item)

    def test_malformed_index_metadata_is_rejected_without_echoing_values(self):
        invalid = [{"path": "/etc/secrets.md"}, {"path": "command-center/windows/../RECEIPT.md"}, {"path": "command-center/windows/window-u/raw.md"}, {"path": "command-center/windows/window-u/RECEIPT.env.md"}, {"path": "command-center/windows/window-u/RECEIPT.md/extra"}, {"path": "command-center/windows/window-u/RECEIPT\\.md"}, {"sha256": "not-a-digest"}, {"bytes": -1}, {"bytes": True}, {"bytes": 1.5}, {"title": "<script>unsafe</script>"}, {"title": "x" * 300}, {"mtime_utc": "2026-10-08T16:25:10"}, {"mtime_utc": "2026-10-08T16:25:10+01:00"}, {"mtime_utc": {"value": "2026-10-08T16:25:10Z"}}]
        self.write([self.row(), *[self.row(**change) for change in invalid]])
        result = evidence.host_receipts_index(self.state, reads=self.reads)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["coverage"]["rejected_receipts"], len(invalid))
        self.assertEqual(result["coverage"]["status"], "partial")
        self.assertNotIn("/etc/secrets.md", json.dumps(result))
        self.assertNotIn("<script>", json.dumps(result))

    def test_absent_index_has_explicit_coverage_reason(self):
        result = evidence.host_receipts_index(self.state, reads=self.reads)
        self.assertEqual(result["items"], [])
        self.assertEqual(result["sources"], [])
        self.assertIn("absent", result["coverage"]["reason"])

    def test_symlink_index_is_rejected_without_opening_its_target(self):
        self.index.parent.mkdir(parents=True)
        target = self.state / "unapproved.md"
        target.write_text("RAW TARGET MUST NEVER BE READ", encoding="utf-8")
        self.index.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "symlink"):
            evidence.host_receipts_index(self.state, reads=self.reads)

    def test_top_level_schema_and_date_are_required(self):
        for changes in [{"schema": "host-receipts-index/2"}, {"generated_utc": "2026-10-09"}, {"generated_utc": "2026-10-09T03:45:30+01:00"}, {"receipts": {}}, {"scope": "bad\nmetadata"}]:
            with self.subTest(changes=changes):
                self.write(**changes)
                result = evidence.host_receipts_index(self.state, reads=self.reads)
                self.assertEqual(result["items"], [])
                self.assertEqual(result["coverage"]["status"], "unreported")
                self.assertTrue(result["coverage"]["reason"])

    def test_additional_fields_do_not_enter_projection(self):
        self.write([self.row(result="pass", commands=["unauthorized command"], credential="WITHHELD FIXTURE")], label="host E2E pass")
        result = evidence.host_receipts_index(self.state, reads=self.reads)
        self.assertNotIn("unauthorized command", json.dumps(result))
        self.assertNotIn("WITHHELD FIXTURE", json.dumps(result))
        self.assertEqual(result["items"][0]["label"], "local host receipt (state root)")

    def test_index_size_is_bounded(self):
        self.index.parent.mkdir(parents=True)
        self.index.write_bytes(b" " * (256 * 1024 + 1))
        with self.assertRaisesRegex(ValueError, "bound"):
            evidence.host_receipts_index(self.state, reads=self.reads)


if __name__ == "__main__":
    unittest.main()
