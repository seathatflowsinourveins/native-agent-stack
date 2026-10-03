"""Snapshot persistence must not replace the first sealed provider vintage, and a ledger gives each attempt one
completion stamp."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from core import plan
from core.canon import dumps, sha256_file
from core.store import SealError, Store
from tests import synth


class ImmutableSnapshot(unittest.TestCase):
    def test_a_second_write_cannot_replace_a_sealed_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            req = plan.assets_requests()[0]
            first = Store()
            synth.put_json(first, req, [{"symbol": "AAA", "status": "active"}])
            sha = first.write(directory)
            before = {str(p.relative_to(directory)): p.read_bytes()
                      for p in directory.rglob("*") if p.is_file()}
            replacement = Store()
            synth.put_json(replacement, req, [{"symbol": "CHANGED", "status": "active"}])
            with self.assertRaisesRegex(SealError, "already|exists|overwrite"):
                replacement.write(directory)
            self.assertEqual({str(p.relative_to(directory)): p.read_bytes()
                              for p in directory.rglob("*") if p.is_file()}, before)
            self.assertEqual(Store.read(directory, sha).parsed(req["key"])[0]["symbol"], "AAA")

    def test_a_second_completion_stamp_for_one_attempt_is_refused(self):
        """Review round 18, second repair (R2-4, mutant B): Store.read refuses a second completion stamp for one key
        and attempt in every snapshot it reads, whatever the stamp says. At 406ad3c5 no test read such a ledger: the
        cross-family re-check removed that refusal and the 393 tests it ran still passed. The ledger is read under
        its own sha256, so only that refusal can stop it; without it the later stamp would govern the attempt."""
        for second in ("stamp_complete", "stamp_incomplete"):
            with self.subTest(second=second), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                req = plan.assets_requests()[0]
                store = Store()
                synth.put_json(store, req, [{"symbol": "AAA", "status": "active"}])
                self.assertEqual(Store.read(directory, store.write(directory)).status(req["key"]), "complete")
                ledger = directory / "ledger.jsonl"
                lines = ledger.read_bytes().splitlines()
                stamp = json.loads(lines[-1])
                self.assertEqual((stamp["event"], stamp["key"], stamp["attempt"]), ("stamp_complete", req["key"], 0))
                ledger.write_bytes(b"\n".join(lines + [dumps({**stamp, "event": second}).encode("utf-8")]) + b"\n")
                refusal = f"^{re.escape(req['key'])} attempt 0: a second completion stamp$"
                with self.assertRaisesRegex(SealError, refusal):
                    Store.read(directory, sha256_file(ledger))
