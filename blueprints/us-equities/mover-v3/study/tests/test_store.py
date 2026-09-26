"""Snapshot persistence must not replace the first sealed provider vintage."""
import tempfile
import unittest
from pathlib import Path

from core import plan
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
