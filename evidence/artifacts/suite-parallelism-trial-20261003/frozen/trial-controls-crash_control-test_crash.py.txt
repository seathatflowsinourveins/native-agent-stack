"""Crash control: the only test ends its own process with os._exit(3).

Run alone, in an empty directory, under a 300-second bound (README.md,
"Controls"). The serial runner exits 3 with no summary; a parallel runner may
hang on the lost task until the bound fires. Either way the run must not report
success: a zero exit or an OK summary fails the control.
"""

import os
import unittest


class CrashControl(unittest.TestCase):
    def test_crash(self):
        os._exit(3)
