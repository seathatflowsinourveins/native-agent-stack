"""Known-outcome controls for the suite-parallelism trial oracle.

Never copy this file into tests/. The trial workflow copies it alone into an
empty directory and runs each arm's exact command there (README.md, "Controls"),
so the module is ``test_zz_trial_controls`` and every count is exact.
Every outcome below is deliberate; control_expectations.json lists them, and
compare.py checks each control run against that file.
"""

import unittest


class TrialControlsA(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(2 + 2, 4)

    @unittest.skip("control: skipped on purpose")
    def test_skip(self):
        self.fail("a skipped control must never run")

    def test_fail(self):
        self.assertEqual(1, 2, "control: fails on purpose")

    def test_error(self):
        raise RuntimeError("control: errors on purpose")


class TrialControlsB(unittest.TestCase):
    def test_subtest_fails(self):
        """Control: subtest i=1 fails; i=0 and i=2 pass."""
        for i in range(3):
            with self.subTest(i=i):
                self.assertNotEqual(i, 1, "control: subtest i=1 fails on purpose")

    @unittest.expectedFailure
    def test_expected_failure(self):
        self.assertEqual(1, 2, "control: an expected failure")

    @unittest.expectedFailure
    def test_unexpected_success(self):
        self.assertEqual(1, 1)

    def test_multiline_docstring(self):
        """Control: this first docstring line becomes a second description line.

        unittest prints only the first line, so in -v output the result of this
        test spans two lines in both runners.
        """
        self.assertTrue(True)


class TrialControlsFixture(unittest.TestCase):
    """A fixture error: setUpClass fails, so test_not_run never starts."""

    @classmethod
    def setUpClass(cls):
        raise RuntimeError("control: setUpClass errors on purpose")

    def test_not_run(self):
        self.fail("must never run: setUpClass failed")
