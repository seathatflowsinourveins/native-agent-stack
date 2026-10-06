"""Source and native-parser checks; these do not activate host services."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
UNITS = ROOT / "adoption/templates/systemd"
DATA_SERVICE = "ecosystem-native-data.service"
DATA_TIMER = "ecosystem-native-data.timer"
GUARD_SERVICE = "disk-headroom-guard.service"
GUARD_TIMER = "disk-headroom-guard.timer"


class NativeUpkeepTimerTests(unittest.TestCase):
    def test_native_data_keeps_the_recorded_observer_and_timer_contract(self):
        service = (UNITS / DATA_SERVICE).read_text()
        timer = (UNITS / DATA_TIMER).read_text()
        for directive in ("Type=oneshot", "UMask=0077", "NoNewPrivileges=true",
                          "TimeoutStartSec=90", "Nice=19", "After=ns2604-loki.service",
                          "Environment=RTK_TELEMETRY_DISABLED=1"):
            self.assertIn(directive, service.splitlines())
        self.assertIn('ExecStart=/usr/bin/python3 -B "@REPOSITORY@/observability/native-data/snapshot.py" '
                      '--config "@PRIVATE_CONFIG@" --publish', service.splitlines())
        self.assertIn('Environment="PATH=@NODE_DIRECTORY@:/usr/local/bin:/usr/bin:/bin"', service.splitlines())
        self.assertNotIn("RemainAfterExit=yes", service)
        self.assertNotIn("[Install]", service)
        for directive in ("OnBootSec=45s", "OnUnitActiveSec=2min", "AccuracySec=10s",
                          "Unit=ecosystem-native-data.service", "WantedBy=timers.target"):
            self.assertIn(directive, timer.splitlines())
        self.assertNotIn("Persistent=true", timer)  # Only calendar timers persist.

    def test_guard_keeps_the_observed_scope_and_cadence(self):
        service = (UNITS / GUARD_SERVICE).read_text()
        timer = (UNITS / GUARD_TIMER).read_text()
        for directive in ("Type=oneshot", "Nice=19", "UMask=0077", "NoNewPrivileges=true",
                          "ExecStart=%h/.local/state/native-agent-stack/ops/disk-headroom-guard.sh"):
            self.assertIn(directive, service.splitlines())
        for directive in ("OnBootSec=2min", "OnUnitActiveSec=2min", "AccuracySec=15s",
                          "Unit=disk-headroom-guard.service", "WantedBy=timers.target"):
            self.assertIn(directive, timer.splitlines())
        self.assertNotIn("RemainAfterExit=yes", service)
        self.assertNotIn("[Install]", service)
        self.assertNotIn("Persistent=true", timer)

    def verify(self, directory, timer_text, strict=True):
        executable = shutil.which("systemd-analyze")
        if not executable:
            self.skipTest("systemd-analyze unavailable; host validation remains required")
        help_result = subprocess.run([executable, "--help"], capture_output=True, text=True)
        if not all(flag in help_result.stdout for flag in ("--recursive-errors", "--generators")):
            self.skipTest("Native verifier options unavailable; installed259.5 host validation required")
        service = (UNITS / DATA_SERVICE).read_text()
        # A whitespace-bearing path checks the reviewed unit quoting with the native parser.
        service = service.replace("@REPOSITORY@", str(ROOT))
        service = service.replace("@PRIVATE_CONFIG@", str(directory / "private configuration.json"))
        service = service.replace("@NODE_DIRECTORY@", str(directory / "node directory"))
        self.assertNotIn("@REPOSITORY@", service)
        self.assertNotIn("@PRIVATE_CONFIG@", service)
        self.assertNotIn("@NODE_DIRECTORY@", service)
        service_path, timer_path = directory / DATA_SERVICE, directory / DATA_TIMER
        service_path.write_text(service)
        timer_path.write_text(timer_text)
        guard = (UNITS / GUARD_SERVICE).read_text().replace(
            "%h/.local/state/native-agent-stack/ops/disk-headroom-guard.sh",
            str(ROOT / "tools/maintenance/disk-headroom-guard.sh"))
        guard_service, guard_timer = directory / GUARD_SERVICE, directory / GUARD_TIMER
        guard_service.write_text(guard)
        guard_timer.write_text((UNITS / GUARD_TIMER).read_text())
        runtime = directory / "runtime"
        runtime.mkdir(mode=0o700, exist_ok=True)
        env = {"PATH": os.environ["PATH"], "HOME": os.environ["HOME"], "LANG": "C",
               "XDG_RUNTIME_DIR": str(runtime),
               "SYSTEMD_UNIT_PATH": str(directory) + ":/usr/lib/systemd/user"}
        argv = [executable, "--user", "--man=no", "--generators=no"]
        if strict:
            argv.append("--recursive-errors=no")
        return subprocess.run(argv + ["verify", str(service_path), str(timer_path),
                                      str(guard_service), str(guard_timer)],
                              env=env, capture_output=True, text=True, timeout=20)

    def test_native_parser_accepts_all_four_rendered_transfer_units(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.verify(Path(directory), (UNITS / DATA_TIMER).read_text())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_verification_fails_an_unknown_directive_instead_of_accepting_warning_only(self):
        timer = (UNITS / DATA_TIMER).read_text().replace("OnBootSec=", "OnBootSecc=")
        self.assertIn("OnBootSecc=", timer)
        with tempfile.TemporaryDirectory() as directory:
            # systemd259.5's default verify exits0 despite this warning.
            ordinary = self.verify(Path(directory), timer, strict=False)
            strict = self.verify(Path(directory), timer)
        self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
        self.assertIn("OnBootSecc", ordinary.stderr)
        self.assertNotEqual(strict.returncode, 0, strict.stdout)
        self.assertIn("OnBootSecc", strict.stderr)


if __name__ == "__main__":
    unittest.main()
