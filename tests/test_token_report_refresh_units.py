"""Structural tests for the drafted token-report-refresh systemd --user templates.

Offline text/logic checks only, in the style of test_host_requests.py's
UnitTemplateTests: nothing here loads, starts, enables or verifies the unit
with a live systemd manager. `systemd-analyze --user verify` and
`systemd-analyze calendar` are run by hand as separate acceptance checks (see
adoption/templates/systemd/token-report-refresh.timer's own comment for the
exact calendar command), not from this suite, so the suite stays runnable
without a systemd --user session.
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSTEMD_DIR = ROOT / "adoption/templates/systemd"


class TokenReportRefreshUnitTests(unittest.TestCase):
    def setUp(self):
        self.service = (SYSTEMD_DIR / "token-report-refresh.service").read_text(encoding="utf-8")
        self.timer = (SYSTEMD_DIR / "token-report-refresh.timer").read_text(encoding="utf-8")
        self.service_lines = self.service.splitlines()
        self.timer_lines = self.timer.splitlines()

    def test_service_is_a_guarded_oneshot_with_no_install_section(self):
        for setting in ("Type=oneshot", "UMask=0077", "NoNewPrivileges=true", "TimeoutStartSec=900"):
            self.assertIn(setting, self.service_lines)
        self.assertNotIn("[Install]", self.service_lines)

    def test_service_environment_no_longer_redirects_the_headroom_workspace(self):
        # Regression guard: HEADROOM_WORKSPACE_DIR used to redirect `headroom savings --json`'s
        # read target away from the shared ~/.headroom ledger it is meant to report on, because
        # `savings` (no --reset) never writes anywhere -- see the service file's own comment for
        # the source lines this rests on (savings_ledger.py, settings_store.py).
        expected_environment = {
            "Environment=HEADROOM_UPDATE_CHECK=off",
            "Environment=HEADROOM_OFFLINE=1",
            "Environment=DO_NOT_TRACK=1",
        }
        for setting in expected_environment:
            self.assertIn(setting, self.service_lines)
        # Assert the exact set of live Environment= directives, not just that these three are
        # present. A later edit could add an unrelated override -- for example
        # HEADROOM_SAVINGS_EVENTS_PATH, HEADROOM_SETTINGS_PATH or HEADROOM_WORKSPACE_DIR itself,
        # each of which takes precedence over the workspace root in headroom/paths.py's
        # per-resource `_resolve()` (explicit > env var > derived default) -- without this test
        # noticing, as long as the three settings above stayed untouched. The explanatory comment
        # above legitimately names HEADROOM_WORKSPACE_DIR in prose to say why it is absent; only
        # the actual [Service] directives are checked here.
        directives = [line for line in self.service_lines if not line.startswith("#")]
        environment_directives = {line for line in directives if line.startswith("Environment=")}
        self.assertEqual(environment_directives, expected_environment,
                         "unexpected or missing Environment= directive in [Service]")

    def test_service_execstart_uses_the_repository_placeholder_convention(self):
        exec_start = next(line for line in self.service_lines if line.startswith("ExecStart="))
        self.assertEqual(
            exec_start,
            "ExecStart=/usr/bin/python3 @REPOSITORY@/tools/token-report/token_manifest.py "
            "refresh --config @REPORT_CONFIG@")

    def test_exec_condition_skips_exactly_the_sat_sun_0500_0900_window(self):
        match = re.search(r"^ExecCondition=/bin/sh -c '(.+)'$", self.service, re.MULTILINE)
        self.assertIsNotNone(match, "ExecCondition line missing or not shaped as /bin/sh -c '...'")
        # Undo the unit file's own systemd escaping ($$ -> $, %% -> %) to recover the literal
        # shell script systemd would actually execute.
        script = match.group(1).replace("$$", "$").replace("%%", "%")
        self.assertIn("$(/bin/date +%u%H)", script,
                      "guard must key off ISO weekday + 24h hour, called by absolute path so "
                      "the guard does not depend on this unit's own PATH (see the standalone "
                      "PATH-independence regression test below)")
        # Swap the live `/bin/date` call for a supplied positional argument so every
        # (weekday, hour) combination can be exercised without waiting on the real clock, while
        # still executing the exact case pattern shipped in the unit file.
        parameterized = script.replace("$(/bin/date +%u%H)", "$1")
        for weekday in range(1, 8):
            for hour in range(24):
                code = f"{weekday}{hour:02d}"
                result = subprocess.run(["/bin/sh", "-c", parameterized, "sh", code],
                                        capture_output=True, timeout=5)
                expect_skip = weekday in (6, 7) and 5 <= hour <= 8
                self.assertEqual(result.returncode, 1 if expect_skip else 0,
                                 f"weekday={weekday} hour={hour:02d} code={code} stderr={result.stderr!r}")

    def test_exec_condition_guard_is_independent_of_this_units_own_path(self):
        # Regression guard for the /bin/date fix above (round-3 review, low finding on
        # README.md:123-124 / service:36-38): a bare `date` call resolves through this unit's
        # own PATH (which Environment=PATH=... installer advice, or a restrictive --user
        # manager, can leave without a `date`); if not found there, `$(date ...)` silently
        # expands to an empty string, no `case` pattern matches, and an unmatched case exits 0 --
        # failing the quiet window open instead of closed. Calling `/bin/date` by absolute path,
        # like /bin/sh itself, must make the guard's result identical no matter what PATH the
        # unit runs with. This operationalizes the review's manual confirmation probe
        # (`env PATH=/nonexistent /bin/sh -c 'case $(date +%u%H) in ?*) exit 1;; esac'; echo $?`)
        # as an unconditional, always-run check instead of a probe someone has to remember to run.
        match = re.search(r"^ExecCondition=/bin/sh -c '(.+)'$", self.service, re.MULTILINE)
        self.assertIsNotNone(match, "ExecCondition line missing or not shaped as /bin/sh -c '...'")
        script = match.group(1).replace("$$", "$").replace("%%", "%")
        with_normal_path = subprocess.run(["/bin/sh", "-c", script], capture_output=True, timeout=5)
        with_broken_path = subprocess.run(["/bin/sh", "-c", script], capture_output=True, timeout=5,
                                          env={"PATH": "/nonexistent-for-this-regression-test"})
        self.assertNotIn(b"not found", with_broken_path.stderr.lower(),
                         f"guard could not resolve a command under a broken PATH: "
                         f"{with_broken_path.stderr!r}")
        self.assertEqual(with_broken_path.returncode, with_normal_path.returncode,
                         "guard result changed when this unit's own PATH could not resolve a "
                         "bare command name; ExecCondition= must call /bin/date by absolute path")

    def test_timer_schedule_never_lands_in_the_quiet_window_and_keeps_persistent_false(self):
        # Check every OnCalendar= directive, not just the first: systemd accepts more than one
        # (each fires independently), so a second line added later -- widening the schedule --
        # must not escape this guard just because the first line still passes.
        oncalendar_lines = [line for line in self.timer_lines if line.startswith("OnCalendar=")]
        self.assertTrue(oncalendar_lines, "at least one OnCalendar= directive is required")
        for oncalendar in oncalendar_lines:
            match = re.match(r"OnCalendar=\*-\*-\* (\S+):15:00$", oncalendar)
            self.assertIsNotNone(match, oncalendar)
            hours = [int(part) for part in match.group(1).split(",")]
            self.assertTrue(hours, "OnCalendar must list at least one hour")
            for hour in hours:
                self.assertFalse(5 <= hour <= 8,
                                 f"scheduled hour {hour:02d} falls inside the 05:00-09:00 quiet window")
        # Only non-comment lines count: a stale reference to Persistent= inside a comment must
        # not satisfy this check.
        settings = [line for line in self.timer_lines if line and not line.startswith("#")]
        self.assertIn("Persistent=false", settings)
        self.assertIn("AccuracySec=1min", settings)
        self.assertIn("Unit=token-report-refresh.service", settings)
        self.assertIn("WantedBy=timers.target", settings)

    def test_timer_no_longer_claims_persistent_false_alone_prevents_a_quiet_window_run(self):
        # Regression guard: the old comment said a missed tick was "simply skipped", which
        # `man systemd.timer`'s sleep/resume catch-up text (quoted in both templates' comments)
        # contradicts. The corrected comment must name the actual enforcement mechanism instead.
        self.assertNotIn("is simply skipped until the next scheduled time", self.timer)
        self.assertIn("ExecCondition", self.timer)

    def test_service_has_no_runtime_directory_directive(self):
        # No workspace-dir redirect means no runtime directory needs to be created/removed for
        # this unit; a RuntimeDirectory= line would be dead configuration. (The comment
        # explaining that absence legitimately names the directive; only a live directive
        # line must not.)
        directives = [line for line in self.service_lines if not line.startswith("#")]
        self.assertFalse(any("RuntimeDirectory" in line for line in directives))


if __name__ == "__main__":
    unittest.main()
