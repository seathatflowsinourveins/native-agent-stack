"""Real verified producer execution through the Fleet adapter and composer."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from tests import test_local_pages as composer_fixtures
from tests.test_local_pages_fleet_data import SEALED_MEMFD_AVAILABLE, SEALED_MEMFD_REASON


@unittest.skipUnless(SEALED_MEMFD_AVAILABLE, SEALED_MEMFD_REASON)
class FleetExecutionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = composer_fixtures.LocalPagesTests("test_full_documents_native_digest_and_local_resources")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.fleet_patch.stop()
        self.producer = self.fixture.state / "coordination/ns2604-coop/tools/fleet_block.py"
        self.producer.parent.mkdir(parents=True, exist_ok=True)
        (self.producer.parent / "fixture_helper.py").write_text("LANE = 'verified-snapshot-lane'\n")
        self.safe = (
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "from fixture_helper import LANE\n"
            "assert sys.argv[0] == __file__\n"
            "assert sys.argv[1:] == ['--json', '--no-gh']\n"
            "assert sys.path[0] == os.path.dirname(__file__)\n"
            "assert Path(__file__).parent == Path(sys.path[0])\n"
            "print(json.dumps({'schema':'coop-fleet/1','at':'2024-07-08T09:00:00Z',"
            "'lanes_live':[{'lane':LANE,'status':'active','tier':'standard'}],"
            "'lanes_parked':[],'claude_sessions':[],'exec_reads_in_flight':[],"
            "'claude_subagents_running':{},'pool_accounts':[]}))\n"
        ).encode()
        self.producer.write_bytes(self.safe)
        self.outside = self.fixture.base / "outside-producer.py"
        self.executed = self.fixture.base / "outside-was-executed"
        self.outside.write_text(
            "from pathlib import Path\n"
            f"Path({str(self.executed)!r}).write_text('outside execution')\n"
            "print('{\"schema\":\"coop-fleet/1\",\"at\":\"2024-07-08T09:00:00Z\","
            "\"lanes_live\":[{\"lane\":\"outside-read-sentinel\"}]}')\n"
        )

    def exercise(self, replacement):
        producer_calls = []
        observed_snapshots = []
        def transport(command, **kwargs):
            if command[0] == "gh":
                return subprocess.CompletedProcess(command, 0, "[]", "")
            producer_calls.append(command)
            replacement()
            for descriptor in kwargs.get("pass_fds", ()):
                observed_snapshots.append(os.pread(descriptor, len(self.safe) + 1, 0))
                with self.assertRaises(OSError):
                    os.pwrite(descriptor, b"changed", 0)
                # Independent Linux UAPI literals verify the actual kernel seal.
                self.assertEqual(fcntl.fcntl(descriptor, 1034) & 0x000F, 0x000F)
            return subprocess.run(command, **kwargs)
        def adapter(state, cache, root):
            return composer_fixtures.BUILDER.load_local("fleet_data").collect(
                state, cache, root, run=transport,
                tracking_run=lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "", ""),
                tracking_fetch=lambda *args, **kwargs: {"status": "success", "data": {"resultType": "vector", "result": []}},
                tracking_probe=lambda *args, **kwargs: None,
            )
        with patch.object(composer_fixtures.BUILDER, "collect_fleet", side_effect=adapter):
            receipt = self.fixture.refresh()
        page = (self.fixture.output / "fleet.html").read_text()
        self.assertIn("verified-snapshot-lane", page)
        self.assertNotIn("outside-read-sentinel", page)
        self.assertFalse(self.executed.exists())
        self.assertEqual(receipt["fleet"]["fleet_source"], "direct native")
        self.assertEqual(len(producer_calls), 1)
        self.assertEqual(observed_snapshots, [self.safe])
        source = next(row for row in receipt["fleet"]["source_inputs"] if row["path"] == str(self.producer))
        self.assertEqual(source["sha256"], hashlib.sha256(self.safe).hexdigest())
        self.assertEqual(source["bytes"], len(self.safe))
        self.assertEqual(source["execution"]["sha256"], hashlib.sha256(self.safe).hexdigest())
        self.assertEqual(source["execution"]["bytes"], len(self.safe))
        self.assertEqual(source["execution"]["status"], "completed")

    def test_pathname_replaced_with_outside_symlink_executes_only_verified_snapshot(self):
        def replace():
            self.producer.unlink()
            self.producer.symlink_to(self.outside)
        self.exercise(replace)

    def test_in_place_change_cannot_alter_sealed_producer_snapshot(self):
        self.exercise(lambda: self.producer.write_bytes(self.outside.read_bytes()))


if __name__ == "__main__":
    unittest.main()
