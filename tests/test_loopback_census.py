"""The loopback-only listener census flags every listener that does not bind loopback, and only those.

docs/decisions/2026-10-17-loopback-listener-census.md: loopback binds only, alert on any other listener. WSL's DNS tunnel
at 10.255.255.254:53 is the one exception. The script reads `ss -H -ltunp`, prints one JSON line and exits 1 on a
breach, so the unit's OnFailure= handler fires.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/loopback_census.py"
SERVICE = ROOT / "adoption/templates/systemd/loopback-census.service"
TIMER = ROOT / "adoption/templates/systemd/loopback-census.timer"

LOOPBACK_ONLY = """\
udp UNCONN 0 0 10.255.255.254:53 0.0.0.0:*
udp UNCONN 0 0 127.0.0.1:323 0.0.0.0:*
udp UNCONN 0 0 [::1]:323 [::]:*
tcp LISTEN 0 4096 127.0.0.53%lo:53 0.0.0.0:*
tcp LISTEN 0 4096 127.0.0.1:23777 0.0.0.0:* users:(("hindsight-api",pid=2708854,fd=11))
tcp LISTEN 0 511 [::ffff:127.0.0.1]:23090 *:*
tcp LISTEN 0 128 [::1]:631 [::]:*
"""
BREACHES = """\
tcp LISTEN 0 4096 0.0.0.0:8080 0.0.0.0:* users:(("python3",pid=4242,fd=3))
tcp LISTEN 0 4096 [::]:9090 [::]:*
udp UNCONN 0 0 *:5353 *:*
tcp LISTEN 0 128 192.168.1.20:8000 0.0.0.0:* users:(("node",pid=77,fd=19))
udp UNCONN 0 0 10.255.255.254:5353 0.0.0.0:*
"""


def run(text):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as stream:
        stream.write(text)
    result = subprocess.run([sys.executable, str(SCRIPT), "--ss-output", stream.name], capture_output=True, text=True)
    Path(stream.name).unlink()
    return result.returncode, json.loads(result.stdout)


class CensusTests(unittest.TestCase):
    def test_loopback_listeners_and_the_wsl_dns_tunnel_pass(self):
        code, report = run(LOOPBACK_ONLY)
        self.assertEqual(code, 0)
        self.assertEqual(report["check"], "loopback-census")
        self.assertEqual(report["listeners"], 7)
        self.assertEqual(report["violations"], [])

    def test_every_non_loopback_listener_is_reported_and_fails_the_run(self):
        code, report = run(LOOPBACK_ONLY + BREACHES)
        self.assertEqual(code, 1)
        found = {(v["proto"], v["address"]) for v in report["violations"]}
        self.assertEqual(found, {("tcp", "0.0.0.0:8080"), ("tcp", "[::]:9090"), ("udp", "*:5353"),
                                 ("tcp", "192.168.1.20:8000"), ("udp", "10.255.255.254:5353")})

    def test_the_owning_process_is_named_by_name_and_pid_only(self):
        _code, report = run(BREACHES)
        processes = {v["address"]: v["process"] for v in report["violations"]}
        self.assertEqual(processes["0.0.0.0:8080"], "python3 pid=4242")
        self.assertEqual(processes["[::]:9090"], "unknown")

    def test_the_dns_tunnel_exception_is_exact(self):
        # Only 10.255.255.254:53 is allowed; the same address on another port is a breach.
        code, report = run("udp UNCONN 0 0 10.255.255.254:5353 0.0.0.0:*\n")
        self.assertEqual((code, len(report["violations"])), (1, 1))


class UnitTemplateTests(unittest.TestCase):
    def test_the_service_runs_the_script_from_the_live_clone_and_alerts_on_failure(self):
        text = SERVICE.read_text(encoding="utf-8")
        self.assertIn("ExecStart=/usr/bin/python3 @REPOSITORY@/scripts/loopback_census.py", text)
        self.assertIn("OnFailure=stack-alert@%n.service", text)
        self.assertIn("Type=oneshot", text)
        # Timer-triggered oneshots in this directory carry no [Install] section (the header may name it in prose).
        self.assertNotIn("[Install]", [line.strip() for line in text.splitlines()])

    def test_the_timer_starts_the_census_every_five_minutes(self):
        text = TIMER.read_text(encoding="utf-8")
        self.assertIn("OnUnitActiveSec=5min", text)
        self.assertIn("Unit=loopback-census.service", text)


if __name__ == "__main__":
    unittest.main()
