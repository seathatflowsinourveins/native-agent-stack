"""Small native make/socket regressions; no application or PostgreSQL build."""
import errno
import hashlib
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ledger_serve", HERE / "serve.py")
serve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve)


class MakeBoundaryTests(unittest.TestCase):
    def exercise(self, source):
        make = shutil.which("make")
        self.assertIsNotNone(make, "native make is required for this regression")
        commands = [line for line in source.read_text().splitlines()
                    if "$(MAKE)" in line and "-C .runtime/postgresql-build" in line]
        self.assertEqual(len(commands), 2, "exercise both actual build/install boundaries")
        with tempfile.TemporaryDirectory(prefix="ledger-make-boundary-") as folder:
            root = Path(folder)
            external = root / ".runtime/postgresql-build"
            external.mkdir(parents=True)
            (root / "Makefile").write_text(".PHONY: all\nall:\n" + "\n".join(commands) + "\n")
            (external / "Makefile").write_text(
                ".PHONY: all install internal\n"
                "all install:\n"
                "\t@printf '%s:%s\\n' '$@' '$(MAKELEVEL)' >> levels.txt\n"
                "\t@test '$(MAKELEVEL)' = '0'\n"
                "\t@$(MAKE) --no-print-directory internal\n"
                "internal:\n"
                "\t@printf 'internal:%s\\n' '$(MAKELEVEL)' >> levels.txt\n"
                "\t@test '$(MAKELEVEL)' = '1'\n"
            )
            result = subprocess.run([make, "--no-print-directory"], cwd=root,
                env={"PATH": os.defpath, "LC_ALL": "C"}, capture_output=True, text=True,
                timeout=10, check=False)
            levels = (external / "levels.txt").read_text().splitlines()
            return result, levels

    def test_original_recipe_reproduces_external_recursion_bug(self):
        result, levels = self.exercise(HERE / "history/Makefile.cabbe2c")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(levels, ["all:1"])

    def test_build_and_install_reset_only_external_boundary(self):
        result, levels = self.exercise(HERE / "Makefile")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(levels, ["all:0", "internal:1", "install:0", "internal:1"])


class RestartPortTests(unittest.TestCase):
    def test_time_wait_restart_is_allowed(self):
        # The accepted server socket actively closes, leaving its local port in
        # TIME_WAIT. Both listener and accepted socket inherit SO_REUSEADDR,
        # matching ordinary native application server behavior.
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            address = listener.getsockname()
            with socket.create_connection(address, timeout=2) as client:
                accepted, _ = listener.accept()
                with accepted:
                    accepted.settimeout(2)
                    accepted.shutdown(socket.SHUT_WR)
                    self.assertEqual(client.recv(1), b"")
                    client.shutdown(socket.SHUT_WR)
                    self.assertEqual(accepted.recv(1), b"")
        with socket.socket() as old_probe:
            with self.assertRaises(OSError) as raised:
                old_probe.bind(address)
            self.assertEqual(raised.exception.errno, errno.EADDRINUSE)
        serve.probe_ports([address[1]])

    def test_live_listener_is_refused_and_remains_usable(self):
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(2)
            address = listener.getsockname()
            with self.assertRaises(OSError) as raised:
                serve.probe_ports([address[1]])
            self.assertEqual(raised.exception.errno, errno.EADDRINUSE)
            with socket.create_connection(address, timeout=2) as client:
                accepted, _ = listener.accept()
                with accepted:
                    accepted.sendall(b"owned listener remains alive")
                    self.assertEqual(client.recv(128), b"owned listener remains alive")


class RecipeHistoryTests(unittest.TestCase):
    def test_retained_originals_and_current_mapping(self):
        history = json.loads((HERE / "history/recipe-revisions.json").read_text())
        original_receipt = json.loads((HERE / "receipt.json").read_text())
        accepted_hashes = {row["artifact"]: row["sha256"]
                           for row in original_receipt["artifact_sha256"]}
        for row in history["recipes"]:
            with self.subTest(recipe=row["current_path"]):
                old = HERE / row["original"]["retained_path"]
                current = HERE / row["current_path"]
                self.assertEqual(hashlib.sha256(old.read_bytes()).hexdigest(), row["original"]["sha256"])
                self.assertEqual(accepted_hashes[row["current_path"]], row["original"]["sha256"])
                self.assertEqual(hashlib.sha256(current.read_bytes()).hexdigest(), row["current_sha256"])
                self.assertNotEqual(old.read_bytes(), current.read_bytes())
        for name, expected in history["unchanged_historical_evidence"].items():
            self.assertEqual(hashlib.sha256((HERE / name).read_bytes()).hexdigest(), expected)

    def test_relocated_frozen_inputs_keep_their_original_bytes(self):
        history = json.loads((HERE / "history/recipe-revisions.json").read_text())
        repo = HERE.parents[2]
        for row in history.get("relocated_frozen_inputs", []):
            with self.subTest(record=row["record"]):
                old = (HERE / row["original"]["retained_path"]).read_bytes()
                current = (HERE / row["record"]).read_bytes()
                self.assertEqual(hashlib.sha256(old).hexdigest(), row["original"]["sha256"])
                self.assertEqual(hashlib.sha256(current).hexdigest(), row["current_sha256"])
                moved = row["relocated"]
                # Only the path changes; the frozen hash names the same retained bytes.
                self.assertEqual(
                    old.replace(moved["from_path"].encode(), moved["to_path"].encode()), current)
                self.assertEqual(
                    hashlib.sha256((repo / moved["to_path"]).read_bytes()).hexdigest(), moved["sha256"])


if __name__ == "__main__":
    unittest.main()
