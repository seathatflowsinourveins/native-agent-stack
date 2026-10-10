#!/usr/bin/env python3
"""Parse reviewed drafts and their inverses; never apply a host setting."""
import configparser
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / "change-plan.json").read_text())


def active_lines(path):
    return [line.strip() for line in path.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith(("#", ";"))]


def ini(path):
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(path)
    return parser


class DraftTests(unittest.TestCase):
    def test_slice_and_sysctl_values(self):
        dropin = ini(ROOT / "systemd/user-1000.slice.d/60-native-stack-memory.conf")
        self.assertEqual(dict(dropin["Slice"]), {"MemoryMax": "64G", "MemoryHigh": "infinity"})
        lines = active_lines(ROOT / "sysctl.d/90-native-stack-swappiness.conf")
        self.assertEqual(len(lines), 1)
        key, value = (part.strip() for part in lines[0].split("=", 1))
        self.assertEqual((key, int(value)), ("vm.swappiness", 10))

    def test_every_effective_configuration_line_has_a_citation(self):
        paths = [ROOT / c["draft"] for c in PLAN["changes"]]
        paths.append(ROOT / "windows/wslconfig-104GB.inverse.fragment.ini")
        for path in paths:
            previous = ""
            for line in path.read_text().splitlines():
                if line.strip() and not line.lstrip().startswith(("#", ";")):
                    with self.subTest(file=path.name, line=line):
                        self.assertTrue(previous.startswith("# Source: "))
                        self.assertRegex(previous, r"/blob/[0-9a-f]{40}/.+#L[0-9]+|systemd\.[a-z-]+\([57]\).+v259\.5")
                        self.assertNotIn("#", line, "inline comments change INI values")
                previous = line.strip()

    def test_oneshot_is_boot_enabled_and_fail_closed(self):
        service = ini(ROOT / "systemd/native-stack-non-systemd-memory.service")
        self.assertEqual(service["Service"]["Type"], "oneshot")
        self.assertEqual(service["Service"]["MemoryAccounting"], "yes")
        self.assertEqual(service["Service"]["RemainAfterExit"], "yes")
        self.assertEqual(service["Install"]["WantedBy"], "multi-user.target")
        argv = shlex.split(service["Service"]["ExecStart"])
        self.assertEqual(argv[:2], ["/bin/sh", "-ec"])
        self.assertIn('test "$$cap" = 42949672960', argv[2])
        self.assertNotIn("sleep", argv[2])
        # A regular temporary file substitutes for cgroupfs. systemd's documented
        # $$ escape becomes $ before sh receives this argument. No host path runs.
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "memory.max"
            fake.write_text("max\n")
            command = argv[2].replace("/sys/fs/cgroup/non-systemd/memory.max",
                                     shlex.quote(str(fake))).replace("$$", "$")
            success = subprocess.run(["/bin/sh", "-ec", command], capture_output=True)
            self.assertEqual(success.returncode, 0, success.stderr)
            self.assertEqual(fake.read_text(), "42949672960\n")
            fake.unlink()
            refused = subprocess.run(["/bin/sh", "-ec", command], capture_output=True)
            self.assertNotEqual(refused.returncode, 0)
            self.assertFalse(fake.exists(), "missing cgroup must fail before creating a file")

    def test_timer_resets_preserve_all_original_expressions(self):
        original = json.loads((ROOT / "measurements/time.json").read_text())["timer_files"]
        timers = [c for c in PLAN["changes"] if c["id"].startswith("zone-")]
        self.assertEqual(len(timers), 7)
        for change in timers:
            before = next(t for t in original if t["draft_target"] == change["target"])
            native = [
                line.strip() for line in before["text"].splitlines()
                if line.strip() and not line.startswith("#")]
            # Empty OnCalendar resets monotonic settings too. Refuse losing any.
            self.assertFalse(any(line.startswith(("OnBootSec=", "OnStartupSec=",
                              "OnUnitActiveSec=", "OnUnitInactiveSec=",
                              "OnActiveSec=")) for line in native))
            self.assertEqual(active_lines(ROOT / change["draft"]),
                             ["[Timer]", "OnCalendar=", "OnCalendar=" + change["new_calendar"]])
            self.assertEqual(change["new_calendar"],
                             change["original_calendar"] + " " + change["calendar_zone"])
            expected = "UTC" if any(name in change["id"] for name in
                       ("native-agent-pages-refresh", "wu-watch")) else "America/New_York"
            self.assertEqual(change["calendar_zone"], expected)

    def test_exact_inverse_and_absent_target_preconditions(self):
        memory = json.loads((ROOT / "measurements/memory.json").read_text())
        self.assertTrue(all(v == "absent" for v in memory["new_targets"].values()))
        for change in PLAN["changes"]:
            inverse = change["inverse"]
            if change["id"] == "wsl-vm-96GiB-option":
                self.assertEqual(inverse["operation"], "restore-original-bytes-from-CC-backup")
                self.assertEqual(inverse["sha256"], memory["windows"]["data"]["file_sha256"])
                self.assertEqual(inverse["sha256"], change["before"]["sha256"])
                self.assertEqual(ini(ROOT / change["draft"])["wsl2"]["memory"], "96GB")
                self.assertEqual(ini(ROOT / inverse["fragment"])["wsl2"]["memory"], "104GB")
            else:
                self.assertEqual(change["before"], "absent")
                self.assertEqual(inverse["target"], change["target"])
                self.assertTrue(inverse["operation"].startswith("remove-only-new-file"))
                if "enable_link" in change:
                    self.assertEqual(change["enable_link_before"], "absent")
                    self.assertEqual(inverse["enable_link"], change["enable_link"])
        self.assertIn("no guest zone, chrony, shell TZ or clock-hook edit",
                      PLAN["time_zone_decision"]["inverse"])

    @unittest.skipUnless(shutil.which("systemd-analyze"), "systemd parser unavailable")
    def test_native_systemd_parser_without_activation(self):
        # Assemble only temporary fixtures: real drafts + the recorded timer bases.
        # The parser loads these files; it does not start any service or timer.
        originals = json.loads((ROOT / "measurements/time.json").read_text())["timer_files"]
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            slice_file = temporary / "user-1000.slice"
            slice_file.write_text((ROOT / "systemd/user-1000.slice.d/60-native-stack-memory.conf").read_text())
            service_file = temporary / "native-stack-non-systemd-memory.service"
            shutil.copyfile(ROOT / "systemd/native-stack-non-systemd-memory.service", service_file)
            units = [slice_file, service_file]
            for change in [c for c in PLAN["changes"] if c["id"].startswith("zone-")]:
                name = change["id"].removeprefix("zone-")
                before = next(t for t in originals if t["draft_target"] == change["target"])
                timer = temporary / name
                timer.write_text(before["text"])
                dropin = temporary / (name + ".d")
                dropin.mkdir()
                shutil.copyfile(ROOT / change["draft"], dropin / "90-native-stack-explicit-zone.conf")
                paired = temporary / (name.removesuffix(".timer") + ".service")
                paired.write_text("[Service]\nType=oneshot\nExecStart=/usr/bin/true\n")
                units.append(timer)
            env = os.environ.copy()
            env["SYSTEMD_UNIT_PATH"] = str(temporary) + ":"
            result = subprocess.run(["systemd-analyze", "--man=no", "verify",
                                     *map(str, units)], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
