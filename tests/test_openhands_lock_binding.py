"""Bindings around the OpenHands recipe lock, retained for the fsspec relock of
2026-10-05 from the litellm relock of 2026-09-30 (review exposed both gaps by mutation).

1. pins.json records the sha256 of requirements.lock and of build-requirements.lock, and the recipe's host.py preflight refuses to run when they differ (host.py:324-327); no test compared
   them, so a relock could leave a stale digest that only a real run would notice.
2. Every grant of tests/test_osv_lockfile_coverage.py (IGNORE_ALLOWED_LOCKS and FROZEN_LOCKS) names an evidence receipt, and the guard only checked that the file exists: a relock that
   moved the granted sha256 and kept an older receipt passed. The receipt of a grant has to record the lock's repository path and the granted sha256, which is what makes it the
   review of those bytes; the carried-forward reasons stay with the receipt's own text.
"""

import hashlib
import json
import unittest

from tests.test_osv_lockfile_coverage import FROZEN_LOCKS, IGNORE_ALLOWED_LOCKS, ROOT

OPENHANDS = ROOT / "blueprints/runtime-workers/openhands"


def receipt_binds(receipt_text, lock_path, sha256):
    """True when a receipt states both the lock's repository path and the sha256 a grant pins for it."""
    return lock_path in receipt_text and sha256 in receipt_text


class PinsDigestTests(unittest.TestCase):
    def test_pins_record_the_digests_of_the_two_lock_files(self):
        pins = json.loads((OPENHANDS / "pins.json").read_text(encoding="utf-8"))
        for key, name in (("requirements_sha256", "requirements.lock"), ("build_requirements_sha256", "build-requirements.lock")):
            actual = hashlib.sha256((OPENHANDS / name).read_bytes()).hexdigest()
            self.assertEqual(pins[key], actual, f"pins.json {key} is not the sha256 of {name}: record the new digest with the relock (the host.py preflight refuses to run otherwise)")


class GrantEvidenceTests(unittest.TestCase):
    def test_each_grant_is_recorded_by_the_receipt_it_names(self):
        for lock_path, grant in {**IGNORE_ALLOWED_LOCKS, **FROZEN_LOCKS}.items():
            receipt_text = (ROOT / grant["evidence"]).read_text(encoding="utf-8")
            self.assertTrue(receipt_binds(receipt_text, lock_path, grant["sha256"]),
                            f"{grant['evidence']} does not record {lock_path} with sha256 {grant['sha256'][:12]}...: write or update the receipt of the review that covers these bytes")

    def test_a_receipt_of_another_digest_or_another_lock_does_not_bind(self):
        lock_path, granted = "blueprints/runtime-workers/openhands/requirements.lock", "e" * 64
        self.assertTrue(receipt_binds(json.dumps({"lock": lock_path, "sha256": granted}), lock_path, granted))
        self.assertFalse(receipt_binds(json.dumps({"lock": lock_path, "sha256": "d" * 64}), lock_path, granted), "a receipt of the previous digest of the same lock")
        self.assertFalse(receipt_binds(json.dumps({"lock": "evidence/other.lock", "sha256": granted}), lock_path, granted), "a receipt of another lock with the same digest")
        self.assertFalse(receipt_binds("", lock_path, granted), "an empty receipt")


if __name__ == "__main__":
    unittest.main()
