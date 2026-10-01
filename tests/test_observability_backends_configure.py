"""observability/backends/configure.py --port-overrides: host loopback ports survive a re-render.

All WSL 2 distributions share one network namespace, so a host can have to move a scraped service off its
template port. These tests run the real renderer into temporary roots; they start no service.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIGURE = ROOT / "observability/backends/configure.py"


class PortOverrideTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def render(self, overrides=None, *, raw=None, data="data"):
        args = [sys.executable, str(CONFIGURE),
                "--tools-root", str(self.root / "tools"), "--config-root", str(self.root / "config"),
                "--data-root", str(self.root / data), "--unit-root", str(self.root / "unit")]
        if overrides is not None or raw is not None:
            path = self.root / "overrides.json"
            path.write_text(raw if raw is not None else json.dumps(overrides))
            args += ["--port-overrides", str(path)]
        return subprocess.run(args, capture_output=True, text=True)

    def read(self, relative):
        return (self.root / relative).read_text()

    def test_without_overrides_the_template_ports_render_and_nothing_is_saved(self):
        self.assertEqual(self.render().returncode, 0)
        self.assertIn("127.0.0.1:8231", self.read("config/ecosystem-prometheus.yml"))
        self.assertFalse((self.root / "config/port-overrides.json").exists())
        tokens = {f"@{name.upper()}_ROOT@": str((self.root / name).resolve())
                  for name in ("tools", "config", "data", "unit")}
        for template in sorted((CONFIGURE.parent / "templates").glob("*.example")):
            name = template.name.removesuffix(".example")
            name = "alertmanager.yml" if name == "ecosystem-ntfy-alertmanager.yml" else name
            [rendered] = [path for path in (self.root / "config").rglob(name)]
            expected = template.read_text()
            for token, value in tokens.items():
                expected = expected.replace(token, value)
            with self.subTest(template.name):
                self.assertEqual(rendered.read_text(), expected)

    def test_overrides_rewrite_configs_and_units_and_are_kept_for_the_next_render(self):
        result = self.render({"8231": 18231, "16333": 26333, "19090": 29090})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Applied 3 loopback port overrides", result.stdout)
        prometheus = self.read("config/ecosystem-prometheus.yml")
        self.assertIn("127.0.0.1:18231", prometheus)
        self.assertIn("127.0.0.1:26333", prometheus)
        self.assertIsNone(re.search(r"127\.0\.0\.1:(8231|16333)(?!\d)", prometheus))
        self.assertIn("--web.listen-address=127.0.0.1:29090", self.read("unit/ecosystem-prometheus.service"))
        self.assertIn("127.0.0.1:29090", self.read("config/ecosystem-grafana-provisioning/datasources/"
                                                   "ecosystem-grafana-datasources.yml"))
        self.assertEqual(json.loads(self.read("config/port-overrides.json")),
                         {"8231": 18231, "16333": 26333, "19090": 29090})

        # A later render without the flag reuses the kept map, so the host ports are not reset.
        first = {path: path.read_text() for path in sorted(self.root.rglob("*")) if path.is_file()}
        again = self.render()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("port-overrides.json", again.stdout)
        second = {path: path.read_text() for path in sorted(self.root.rglob("*")) if path.is_file()}
        self.assertEqual(first, second)

    def test_a_swap_is_applied_in_one_pass(self):
        result = self.render({"19090": 19093, "19093": 19090})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--web.listen-address=127.0.0.1:19093", self.read("unit/ecosystem-prometheus.service"))
        self.assertIn("--web.listen-address=127.0.0.1:19090", self.read("unit/ecosystem-alertmanager.service"))

    def test_a_root_path_that_contains_the_port_digits_is_not_a_collision(self):
        # Review finding: the bare-port check used to scan the substituted root paths too.
        result = self.render({"18888": 28888}, data="18888-data")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("18888-data", self.read("unit/ecosystem-prometheus.service"))
        self.assertNotIn("127.0.0.1:18888", self.read("config/ecosystem-prometheus.yml"))

    def test_refusals_exit_2_and_write_nothing(self):
        cases = {
            "stale port": {"1234": 11234},
            "bare listen port (Loki http_listen_port)": {"13100": 23100},
            "collides with a rendered address": {"8231": 19090},
            "same port": {"8231": 8231},
            "out of range": {"8231": 70000},
            "boolean value": {"8231": True},
            "two ports to one": {"8231": 28231, "16333": 28231},
            "one valid and one stale entry": {"8231": 18231, "1234": 11234},
        }
        for label, overrides in cases.items():
            with self.subTest(label):
                result = self.render(overrides)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertFalse((self.root / "config").exists(), "a refused render must write nothing")
        for label, raw in {"not JSON": "{", "not an object": "[8231]",
                           "non-ASCII digit key": '{"\\u00b2": 28888}'}.items():
            with self.subTest(label):
                result = self.render(raw=raw)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse((self.root / "config").exists())


if __name__ == "__main__":
    unittest.main()
