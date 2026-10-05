"""Local lock/census and shared-vector contracts; no installer or network runs.

uv 0.12.17's docs/concepts/projects/dependencies.md defines removal/relocking.
Removing unused DVC also removed the sole no-wheel dependency and its backend.
The virtual project is metadata, not a distribution in the wheel census.
Shell calls below only record synthetic argv bytes.
"""

import copy
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "blueprints/us-equities/runtime-2604"
PROJECT = BUNDLE / "trading-2604-runtime"


def section(case, data, name):
    start = b"# BEGIN " + name + b"\n"
    end = b"# END " + name + b"\n"
    case.assertEqual(data.count(start), 1, "one shared-vector section start")
    case.assertEqual(data.count(end), 1, "one shared-vector section end")
    return data.split(start, 1)[1].split(end, 1)[0]


class Trading2604LockTests(unittest.TestCase):
    def setUp(self):
        self.project = tomllib.loads((PROJECT / "pyproject.toml").read_text())
        self.lock = tomllib.loads((PROJECT / "uv.lock").read_text())

    def assert_contract(self, project, lock):
        constraints = project["tool"]["uv"].get("build-constraint-dependencies", [])
        self.assertEqual(constraints, [], "no unused build constraint")
        self.assertEqual(lock.get("manifest", {}).get("build-constraints", []), [],
                         "no stale lock manifest build constraint")
        source_builds = {
            p["name"] for p in lock["package"]
            if "virtual" not in p["source"] and not p.get("wheels")
        }
        self.assertEqual(source_builds, set(), "wheel census: no package without any wheel")
        names = {p["name"] for p in lock["package"]}
        self.assertFalse(names & {"dvc", "dvc-data", "diskcache"}, "unused DVC chain removed")

    def test_checked_in_lock_contract(self):
        self.assert_contract(self.project, self.lock)

    def test_package_without_any_wheel_fails(self):
        lock = copy.deepcopy(self.lock)
        next(p for p in lock["package"] if p["name"] == "edgartools").pop("wheels")
        with self.assertRaisesRegex(AssertionError, "wheel census"):
            self.assert_contract(self.project, lock)

    def test_unused_build_constraint_fails(self):
        project = copy.deepcopy(self.project)
        project["tool"]["uv"]["build-constraint-dependencies"] = ["setuptools==84.0.0"]
        with self.assertRaisesRegex(AssertionError, "unused build constraint"):
            self.assert_contract(project, self.lock)

    def test_stale_manifest_constraint_fails(self):
        lock = copy.deepcopy(self.lock)
        lock["manifest"] = {"build-constraints": [{"name": "setuptools", "specifier": "==84.0.0"}]}
        with self.assertRaisesRegex(AssertionError, "stale lock manifest"):
            self.assert_contract(self.project, lock)

    def test_reintroduced_diskcache_fails(self):
        lock = copy.deepcopy(self.lock)
        package = copy.deepcopy(next(p for p in lock["package"] if p["name"] == "edgartools"))
        package["name"] = "diskcache"
        lock["package"].append(package)
        with self.assertRaisesRegex(AssertionError, "DVC chain removed"):
            self.assert_contract(self.project, lock)

    def test_project_installer_and_acceptance_pins_agree(self):
        installer = (BUNDLE / "install-trading-2604.sh").read_text()
        acceptance = (BUNDLE / "accept-trading-2604.sh").read_text()
        requirements = re.search(r"^requirements=\(\n(.*?)^\)\n", installer, re.M | re.S)[1]
        requirements = "\n".join(line for line in requirements.splitlines()
                                 if not line.lstrip().startswith("#"))
        self.assertEqual(sorted(re.findall(r"'([^']+)'", requirements)),
                         sorted(self.project["project"]["dependencies"]))
        expected = {name.split("[", 1)[0].replace("_", "-"): version
                    for name, version in (r.split("==") for r in self.project["project"]["dependencies"])}
        specs = re.search(r"^specs=\(\n(.*?)^\)\n", acceptance, re.M | re.S)[1]
        observed = {name: version for name, version, _ in
                    (s.split("|") for s in re.findall(r"'([^']+)'", specs))}
        self.assertEqual(observed, expected, "every installed pin has the same acceptance probe")
        root = next(p for p in self.lock["package"] if p["name"] == "us-equities-runtime")
        self.assertEqual({p["name"] for p in root["dependencies"]}, set(expected))


class Trading2604SyncVectorTests(unittest.TestCase):
    def setUp(self):
        self.installer = (BUNDLE / "install-trading-2604.sh").read_bytes()
        self.vector = (BUNDLE / "sync-trading-2604.sh").read_bytes()

    def assert_shared_source(self, installer, vector):
        self.assertEqual(section(self, installer, b"shared-sync-source"),
                         b'source "$script_directory/sync-trading-2604.sh"\n')
        self.assertEqual(section(self, installer, b"shared-sync-call"), b"sync_trading_2604\n")
        self.assertNotRegex(installer, rb"uv\s+--no-config\s+(?:lock|sync|pip\s+check)",
                            "installer must not retype the shared vector")
        digest = re.search(rb"^readonly sync_vector_hash=([0-9a-f]{64})$", installer, re.M)
        self.assertIsNotNone(digest, "installer must verify shared-vector bytes before sourcing")
        self.assertEqual(digest[1].decode(), hashlib.sha256(vector).hexdigest())

    def record_vector(self, installer=None, fail_stage=""):
        # This records argv only. No uv command, host installer or host guard is run.
        body = '''capture() {
    printf '%s\\0' "$step" "$@"
    printf '\\n'
    [[ $step != "$fail_stage" ]] || return 23
}
safe=(capture)
project='/tmp/contract project'
runtime_python='/tmp/managed python/bin/python3.12'
script_directory=$1
fail_stage=$2
'''
        if installer is None:
            body += 'source "$script_directory/sync-trading-2604.sh"\nsync_trading_2604\n'
        else:
            body += section(self, installer, b"shared-sync-source").decode()
            body += section(self, installer, b"shared-sync-call").decode()
        return subprocess.run(
            ["bash", "--noprofile", "--norc", "-c", body, "record-vector", str(BUNDLE), fail_stage],
            capture_output=True, env={"PATH": os.defpath, "LC_ALL": "C"}, check=False,
        )

    def test_installer_and_ci_source_have_byte_identical_argv(self):
        self.assert_shared_source(self.installer, self.vector)
        host = self.record_vector(self.installer)
        ci = self.record_vector()
        self.assertEqual((host.returncode, ci.returncode), (0, 0))
        self.assertEqual(host.stdout, ci.stdout, "every argv byte and step must agree")
        self.assertEqual([line.split(b"\0", 1)[0] for line in host.stdout.splitlines()],
                         [b"lock-check", b"package-sync", b"dependency-check"])
        lock = tomllib.loads((PROJECT / "uv.lock").read_text())
        cutoff = re.search(rb"^readonly exclude_newer=(.+)$", self.vector, re.M)[1].decode()
        python = re.search(rb"^readonly python_pin=(.+)$", self.vector, re.M)[1].decode()
        self.assertEqual(cutoff, lock["options"]["exclude-newer"])
        self.assertEqual("==" + python, lock["requires-python"])

    def test_installer_one_byte_change_fails(self):
        changed = self.installer.replace(b"\nsync_trading_2604\n", b"\nsync_trading_2604 \n")
        self.assertNotEqual(changed, self.installer)
        with self.assertRaises(AssertionError):
            self.assert_shared_source(changed, self.vector)

    def test_retyped_installer_step_fails(self):
        changed = self.installer + b'uv --no-config sync --locked --no-dev\n'
        with self.assertRaisesRegex(AssertionError, "must not retype"):
            self.assert_shared_source(changed, self.vector)

    def test_changed_shared_file_without_hash_refresh_fails(self):
        with self.assertRaises(AssertionError):
            self.assert_shared_source(self.installer, self.vector + b"\n")

    def test_each_failure_stops_before_next_step(self):
        for index, step in enumerate(("lock-check", "package-sync", "dependency-check"), 1):
            with self.subTest(step=step):
                result = self.record_vector(self.installer, fail_stage=step)
                self.assertEqual(result.returncode, 23)
                self.assertEqual(len(result.stdout.splitlines()), index)

    def test_bundle_hashes_and_final_completion_marker_agree(self):
        for field, name in (("project_hash", "pyproject.toml"), ("lock_hash", "uv.lock")):
            digest = re.search(rb"^readonly " + field.encode() + rb"=([0-9a-f]{64})$",
                               self.installer, re.M)
            self.assertEqual(digest[1].decode(), hashlib.sha256((PROJECT / name).read_bytes()).hexdigest())
        marker = re.search(rb"^readonly completion='([^']+)'$", self.installer, re.M)[1]
        acceptance = (BUNDLE / "accept-trading-2604.sh").read_bytes()
        self.assertIn(b"$recorded_completion == " + marker + b" ]]", acceptance)


if __name__ == "__main__":
    unittest.main()
