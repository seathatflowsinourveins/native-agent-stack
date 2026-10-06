"""Local fixture controls; no Terminal process, deployment or client state read."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from scripts.terminal_profile_ids import derived_guid
from scripts.validate import scan_file_for_private_content

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "checks/check-terminal-profiles.py"


def profile(name="NativeStack2604 - Claude", client="claude"):
    row = {
        "name": name, "guid": derived_guid("NativeStack", name),
        "commandline": f'wsl.exe -d NativeStack2604 --cd "~/code/native-agent-stack" --exec /bin/bash -lc "exec {client}"',
        "bellStyle": ["audible", "taskbar"],
        "bellSound": "C:\\Windows\\Media\\Windows Ding.wav",
    }
    if client == "claude":
        row["environment"] = {"COLORTERM": "truecolor"}
    return row


class TerminalFragmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "nativestack2604.json"
        self.media = self.root / "Media"
        self.media.mkdir()
        (self.media / "Windows Ding.wav").touch()
        self.home = self.root / "home"
        (self.home / ".codex").mkdir(parents=True)
        # Malformed synthetic client state must never be inspected by this checker.
        (self.home / ".codex/config.toml").write_text("not valid TOML [", encoding="utf-8")

    def write(self, rows):
        self.path.write_text(json.dumps({"profiles": rows}), encoding="utf-8")

    def run_check(self, rows):
        self.write(rows)
        env = dict(os.environ, HOME=str(self.home), NATIVESTACK_MEDIA_DIR=str(self.media))
        return subprocess.run([sys.executable, "-B", str(CHECKER), str(self.path)],
                              env=env, capture_output=True, text=True)

    def test_microsoft_documented_guid_example_and_identity(self):
        expected = "{" + "-".join(("2ece5bfe", "50ed", "5f3a", "ab87", "5cd4baafed2b")) + "}"
        self.assertEqual(derived_guid("Git", "Git Bash"), expected)
        self.assertEqual(profile()["guid"], derived_guid("NativeStack", profile()["name"]))
        self.assertNotEqual(profile()["guid"], derived_guid("Changed", profile()["name"]))

    def test_valid_ai_and_static_profiles_skip_native_client_configuration(self):
        static = profile("NativeStack2604 - Shell", "/bin/bash -l")
        static.update(bellStyle=["taskbar"], suppressApplicationTitle=True)
        static.pop("bellSound")
        result = self.run_check([profile(), profile("NativeStack2604 - Codex", "codex"), static])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_wrong_and_duplicate_identifiers_fail(self):
        for change in ("missing", "wrong", "duplicate"):
            with self.subTest(change=change):
                rows = [profile()]
                if change == "missing":
                    rows[0].pop("guid")
                elif change == "wrong":
                    rows[0]["guid"] = derived_guid("Different", rows[0]["name"])
                else:
                    rows.append(copy.deepcopy(rows[0]))
                self.assertNotEqual(self.run_check(rows).returncode, 0)

    def test_bell_colour_title_and_client_override_controls(self):
        defects = (
            ("bellStyle", "all"), ("bellStyle", ["audible"]),
            ("bellSound", "C:\\Windows\\Media\\..\\Windows Ding.wav"),
            ("bellSound", "C:\\Windows\\Media\\missing.wav"),
            ("environment", {}), ("suppressApplicationTitle", True),
            ("commandline", profile()["commandline"].replace("exec claude", "exec claude --effort max")),
        )
        for key, value in defects:
            with self.subTest(key=key, value=value):
                row = profile()
                row[key] = value
                self.assertNotEqual(self.run_check([row]).returncode, 0)

    def test_static_profile_cannot_ring_audibly(self):
        row = profile("NativeStack2604 - Shell", "/bin/bash -l")
        self.assertNotEqual(self.run_check([row]).returncode, 0)
        row['bellStyle'] = ['window', 'taskbar']
        self.assertNotEqual(self.run_check([row]).returncode, 0)

    def test_empty_and_non_ascii_profiles_are_rejected_explicitly(self):
        self.assertNotEqual(self.run_check([]).returncode, 0)
        self.assertNotEqual(self.run_check([None]).returncode, 0)
        row = profile()
        row['name'] = 'Terminal café'
        result = self.run_check([row])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ASCII profile names only', result.stdout)
        self.assertNotIn('Traceback', result.stderr)

    def test_repository_default_never_discovers_host_media_or_client_state(self):
        fixture_root = self.root / 'repo'
        for directory in ('checks', 'scripts', 'windows'):
            (fixture_root / directory).mkdir(parents=True)
        shutil.copyfile(CHECKER, fixture_root / 'checks/check-terminal-profiles.py')
        shutil.copyfile(ROOT / 'scripts/terminal_profile_ids.py', fixture_root / 'scripts/terminal_profile_ids.py')
        (fixture_root / 'windows/nativestack2604.json').write_text(json.dumps({'profiles': [profile()]}))
        code = 'import runpy; from unittest.mock import patch; ' + \
               'p=patch("pathlib.Path.is_file", side_effect=AssertionError("unexpected media read")); p.start(); ' + \
               'runpy.run_path("checks/check-terminal-profiles.py", run_name="__main__")'
        env = dict(os.environ, HOME=str(self.home))
        env.pop('NATIVESTACK_MEDIA_DIR', None)
        result = subprocess.run([sys.executable, '-B', '-c', code], cwd=fixture_root,
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_host_launcher_contracts_keep_client_bell_and_colour_controls(self):
        for launcher, client in [('command-center-resume.sh', 'claude'),
                                 ('co-op-resume.sh', 'claude'),
                                 ('codex-account-pool.sh', 'codex'), ('codex-lane.sh', 'codex')]:
            with self.subTest(launcher=launcher):
                row = profile(client=client)
                row['commandline'] = profile()['commandline'].replace('exec claude',
                    'exec bash ~/.local/state/native-agent-stack/lanes/' + launcher)
                self.assertEqual(self.run_check([row]).returncode, 0)
                row['bellStyle'] = ['taskbar']
                self.assertNotEqual(self.run_check([row]).returncode, 0)

    def test_cold_file_spec_validator_import_and_fragment_scan(self):
        self.write([profile()])
        code = ('import importlib.util; from pathlib import Path; '
                's=importlib.util.spec_from_file_location("cold_validate", ' + repr(str(ROOT / 'scripts/validate.py')) + '); '
                'v=importlib.util.module_from_spec(s); s.loader.exec_module(v); '
                'assert not v.scan_file_for_private_content(Path(' + repr(str(self.path)) + '))')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code], cwd=self.root,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_guid_privacy_exception_is_only_for_validated_field_and_filename(self):
        self.write([profile()])
        self.assertEqual(scan_file_for_private_content(self.path), [])
        other = self.root / "other.json"
        other.write_bytes(self.path.read_bytes())
        self.assertTrue(any("session identifier" in x for x in scan_file_for_private_content(other)))
        row = profile()
        row["commandline"] += " " + row["guid"]
        self.write([row])
        self.assertTrue(any("session identifier" in x for x in scan_file_for_private_content(self.path)))

    def test_duplicate_json_keys_and_escaped_identifiers_cannot_hide_private_data(self):
        private = "-".join(("01234567", "89ab", "cdef", "0123", "456789abcdef"))
        good = profile()
        text = json.dumps({"profiles": [good]})
        text = text.replace('"guid": ', '"guid": "' + private + '", "guid": ', 1)
        self.path.write_text(text, encoding="utf-8")
        self.assertTrue(scan_file_for_private_content(self.path))
        good["extra"] = private
        text = json.dumps({"profiles": [good]}).replace(private, "".join("\\u" + format(ord(x), "04x") for x in private))
        self.path.write_text(text, encoding="utf-8")
        self.assertTrue(scan_file_for_private_content(self.path))

    def test_private_paths_and_generated_token_controls_still_fail_without_echo(self):
        for value in ("/home/" + "private-person/project", "ghp" + "_" + "x" * 36):
            with self.subTest(kind=value[:4]):
                row = profile()
                row["extra"] = value
                self.write([row])
                findings = scan_file_for_private_content(self.path)
                self.assertTrue(findings)
                self.assertTrue(all(value not in finding for finding in findings))


if __name__ == "__main__":
    unittest.main()
