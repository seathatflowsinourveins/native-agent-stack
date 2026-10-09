"""Synthetic runtime-name and native Betterleaks privacy regressions."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import host_name_scan


class HostNameSourceTests(unittest.TestCase):
    def setUp(self):
        environment = {key: value for key, value in os.environ.items()
                       if key not in (host_name_scan.OVERRIDE, "WSL_DISTRO_NAME")}
        patch = mock.patch.dict(os.environ, environment, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(host_name_scan.shutil, "which", return_value=None)
        patch.start()
        self.addCleanup(patch.stop)

    def test_override_replaces_all_runtime_sources(self):
        with mock.patch.dict(os.environ, {host_name_scan.OVERRIDE: '["fixtureagent"]'}), \
                mock.patch.object(host_name_scan, "_command", side_effect=AssertionError("source used")), \
                mock.patch.object(host_name_scan, "PROFILE_ROOT") as profiles:
            self.assertEqual(host_name_scan.host_names(Path.cwd()), ("fixtureagent",))
            profiles.exists.assert_not_called()

    def test_runtime_identity_hostname_profiles_and_private_email_are_combined(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profiles = root / "profiles"
            profiles.mkdir()
            (profiles / "fixtureprofile").mkdir()
            (profiles / "not-a-profile").write_text("fixture")
            results = [subprocess.CompletedProcess([], 0, "fixtureagent\n", ""),
                       subprocess.CompletedProcess([], 0, "fixturehostname\n", ""),
                       subprocess.CompletedProcess([], 0, "fixturemail@example.invalid\n", "")]
            environment = {key: value for key, value in os.environ.items() if key != host_name_scan.OVERRIDE}
            with mock.patch.dict(os.environ, environment, clear=True), \
                    mock.patch.object(host_name_scan, "PROFILE_ROOT", profiles), \
                    mock.patch.object(host_name_scan, "_command", side_effect=results) as command:
                self.assertEqual(host_name_scan.host_names(root),
                                 ("fixtureagent", "fixturehostname", "fixtureprofile", "fixturemail"))
                self.assertEqual([call.args[0] for call in command.call_args_list],
                                 [["id", "-un"], ["uname", "-n"],
                                  ["git", "config", "--get", "user.email"]])

    def test_invalid_overrides_fail_without_echoing_values(self):
        for value in ('not-json-fixtureagent', '["fixtureagent\\n"]', '[]', '"fixtureagent"', '[1]'):
            with self.subTest(value=value), mock.patch.dict(os.environ, {host_name_scan.OVERRIDE: value}):
                with self.assertRaises(host_name_scan.HostNameScanError) as caught:
                    host_name_scan.host_names(Path.cwd())
                self.assertNotIn("fixtureagent", str(caught.exception))

    def test_source_failures_are_closed_and_value_free(self):
        environment = {key: value for key, value in os.environ.items()
                       if key != host_name_scan.OVERRIDE}
        cases = ([subprocess.CompletedProcess([], 1, "fixtureagent", "fixtureagent")],
                 [subprocess.CompletedProcess([], 0, "fixtureagent\n", ""),
                  subprocess.CompletedProcess([], 2, "fixtureagent", "fixtureagent")])
        for results in cases:
            with self.subTest(count=len(results)), \
                    mock.patch.dict(os.environ, environment, clear=True), \
                    mock.patch.object(host_name_scan, "PROFILE_ROOT") as profiles, \
                    mock.patch.object(host_name_scan, "_command", side_effect=results):
                profiles.iterdir.return_value = []
                with self.assertRaises(host_name_scan.HostNameScanError) as caught:
                    host_name_scan.host_names(Path.cwd())
                self.assertNotIn("fixtureagent", str(caught.exception))

    def test_inaccessible_profile_source_fails_closed(self):
        environment = {key: value for key, value in os.environ.items()
                       if key != host_name_scan.OVERRIDE}
        with mock.patch.dict(os.environ, environment, clear=True), \
                mock.patch.object(host_name_scan, "PROFILE_ROOT") as profiles, \
                mock.patch.object(host_name_scan, "_command", return_value=
                                  subprocess.CompletedProcess([], 0, "fixtureagent\n", "")):
            profiles.iterdir.side_effect = PermissionError("fixtureagent")
            with self.assertRaises(host_name_scan.HostNameScanError) as caught:
                host_name_scan.host_names(Path.cwd())
            self.assertNotIn("fixtureagent", str(caught.exception))

    def test_a_profile_entry_stat_failure_is_not_treated_as_an_absent_source(self):
        environment = {key: value for key, value in os.environ.items()
                       if key != host_name_scan.OVERRIDE}
        with mock.patch.dict(os.environ, environment, clear=True), \
                mock.patch.object(host_name_scan, "PROFILE_ROOT") as profiles, \
                mock.patch.object(host_name_scan, "_command", return_value=
                                  subprocess.CompletedProcess([], 0, "fixtureagent\n", "")):
            entry = mock.Mock()
            entry.stat.side_effect = FileNotFoundError("fixtureagent")
            profiles.iterdir.return_value = [entry]
            with self.assertRaises(host_name_scan.HostNameScanError):
                host_name_scan.host_names(Path.cwd())

    def test_windows_shared_template_and_junction_folders_are_not_personal_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            profiles = Path(temporary)
            for name in ("All Users", "Default", "Default User", "Public", "fixtureprofile"):
                (profiles / name).mkdir()
            results = [subprocess.CompletedProcess([], 0, "Public\n", ""),
                       subprocess.CompletedProcess([], 0, "fixturehostname\n", ""),
                       subprocess.CompletedProcess([], 0, "Default@example.invalid\n", "")]
            with mock.patch.dict(os.environ, {}, clear=True), \
                    mock.patch.object(host_name_scan, "PROFILE_ROOT", profiles), \
                    mock.patch.object(host_name_scan, "_command", side_effect=results):
                # Id and email remain designated sources even if their actual
                # values happen to coincide with a Windows system-folder name.
                self.assertEqual(host_name_scan.host_names(profiles),
                                 ("Public", "fixturehostname", "fixtureprofile", "Default"))

    def test_github_noreply_local_part_is_public_but_coincident_id_stays(self):
        for email in ("123+fixturepublic@users.noreply.github.com",
                      "fixturepublic@USERS.NOREPLY.GITHUB.COM"):
            results = [subprocess.CompletedProcess([], 0, "fixturepublic\n", ""),
                       subprocess.CompletedProcess([], 0, "fixturehostname\n", ""),
                       subprocess.CompletedProcess([], 0, email + "\n", "")]
            with self.subTest(email=email), \
                    mock.patch.object(host_name_scan, "PROFILE_ROOT") as profiles, \
                    mock.patch.object(host_name_scan, "_command", side_effect=results):
                profiles.iterdir.return_value = []
                self.assertEqual(host_name_scan.host_names(Path.cwd()),
                                 ("fixturepublic", "fixturehostname"))

    def test_windows_native_sources_work_without_mnt_c_profile_mount(self):
        results = [subprocess.CompletedProcess([], 0, "fixtureagent\n", ""),
                   subprocess.CompletedProcess([], 0, "fixturehostname\n", ""),
                   subprocess.CompletedProcess([], 0, json.dumps({
                       "computer": "fixturecomputer", "profiles": ["fixtureprofile", "Public"]}), ""),
                   subprocess.CompletedProcess([], 0, "fixturemail@example.invalid\n", "")]
        with mock.patch.object(host_name_scan, "PROFILE_ROOT") as profiles, \
                mock.patch.object(host_name_scan.shutil, "which", return_value="powershell.exe"), \
                mock.patch.object(host_name_scan, "_command", side_effect=results):
            profiles.iterdir.side_effect = FileNotFoundError()
            self.assertEqual(host_name_scan.host_names(Path.cwd()),
                             ("fixtureagent", "fixturehostname", "fixturecomputer", "fixtureprofile", "fixturemail"))

    def test_wsl_without_windows_source_refuses_without_values(self):
        with mock.patch.dict(os.environ, {"WSL_DISTRO_NAME": "fixture"}), \
                mock.patch.object(host_name_scan, "_command", return_value=
                                  subprocess.CompletedProcess([], 0, "fixtureagent\n", "")):
            with self.assertRaises(host_name_scan.HostNameScanError) as caught:
                host_name_scan.host_names(Path.cwd())
            self.assertNotIn("fixtureagent", str(caught.exception))


@unittest.skipUnless(shutil.which("betterleaks"), "native Betterleaks unavailable")
class NativeHostNameScanTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.target = self.root / "synthetic.txt"
        self.names = ("fixtureagent", "fixture--agent", "fixtureagent-", "fixtureéagent")
        self.environment = mock.patch.dict(os.environ, {host_name_scan.OVERRIDE: json.dumps(self.names)})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def scan(self, content):
        self.target.write_text(content, encoding="utf-8")
        return host_name_scan.scan_paths([self.target], root=self.root)

    def test_every_ascii_punctuation_boundary_and_hyphen_shape(self):
        from string import punctuation
        lines = [left + name + right for name in self.names for left in punctuation for right in punctuation]
        findings = self.scan("\n".join(lines))
        self.assertEqual(findings, [(self.target, line) for line in range(1, len(lines) + 1)])

    def test_unicode_alphanumeric_neighbors_are_not_bare_names(self):
        # A shorter deny-name can legitimately match before a longer name's
        # punctuation suffix; isolate rules when testing the neighbor invariant.
        for name in self.names:
            with self.subTest(name=name), mock.patch.dict(
                    os.environ, {host_name_scan.OVERRIDE: json.dumps([name])}):
                lines = [left + name + right for left, right in
                         (("A", ""), ("", "7"), ("é", ""), ("", "中"), ("Ⅸ", ""))]
                self.assertEqual(self.scan("\n".join(lines)), [])

    def test_case_insensitive_literal_and_escaped_delimiter_boundaries(self):
        lines = [prefix + "FIXTUREAGENT" for prefix in
                 ("", "/", "%2F", "%5C", "%20", r"\n", r"\t", r"\r", r"\u000a", "%0A")]
        self.assertEqual(self.scan("\n".join(lines)),
                         [(self.target, line) for line in range(1, len(lines) + 1)])

    def test_native_decoders_and_original_line_mapping(self):
        import base64
        name = "fixtureagentextendedmarker"
        encoded = [base64.b64encode(name.encode()).decode(), name.encode().hex(),
                   "".join("%" + format(byte, "02X") for byte in name.encode()),
                   "".join(r"\u" + format(ord(char), "04x") for char in name)]
        with mock.patch.dict(os.environ, {host_name_scan.OVERRIDE: json.dumps([name])}):
            self.assertEqual(self.scan("\n".join("clean\n" + value for value in encoded)),
                             [(self.target, line) for line in (2, 4, 6, 8)])
            neighbors = [value.encode().hex() for value in ("A" + name, name + "A")]
            self.assertEqual(self.scan("\n".join(neighbors)), [])

    def test_decoded_names_at_artificial_cuts_retain_neighbor_guards(self):
        name = "fixtureagentextendedmarker"
        encoded = "".join("%" + format(byte, "02X") for byte in name.encode())
        with mock.patch.dict(os.environ, {host_name_scan.OVERRIDE: json.dumps([name])}):
            lines = ["_" * offset + encoded + "_" * 8000 for offset in (3980, 3990, 4050, 4060, 4090, 4110)]
            self.assertEqual(self.scan("\n".join(lines)),
                             [(self.target, line) for line in range(1, len(lines) + 1)])

    def test_adjacent_names_multifile_lines_and_binary_magic_are_retained(self):
        self.target.write_bytes(b"%PDF-1.4\nfixtureagent_fixtureagent\n")
        other = self.root / "other.txt"
        other.write_text("clean\nfixture--agent\n", encoding="utf-8")
        self.assertEqual(host_name_scan.scan_paths([self.target, other], root=self.root),
                         [(other, 2), (self.target, 2)])

    def test_larger_multiline_input_retains_end_findings(self):
        lines = ["safe text"] * 18000 + ["fixtureagent"]
        self.assertEqual(self.scan("\n".join(lines)), [(self.target, 18001)])

    def test_long_records_retain_findings_and_unicode_neighbor_context(self):
        lines = ["safe " * 4000 + "fixtureagent",
                 "safe " * 20000 + "|fixtureéagent|" + "safe " * 20000,
                 "中" * 100000 + "fixtureagent" + "中" * 100000,
                 "safe " * 40000 + "fixtureagent"]
        self.assertEqual(self.scan("\n".join(lines)),
                         [(self.target, 1), (self.target, 2), (self.target, 4)])

    def test_long_record_framing_never_introduces_a_candidate(self):
        with mock.patch.dict(os.environ, {host_name_scan.OVERRIDE:
                                          '["x", "xfixture", "fixturex"]'}):
            lines = ["~" * offset + "fixture!" + "~" * 8000
                     for offset in range(3990, 4120)]
            self.assertEqual(self.scan("\n".join(lines)), [])

    def test_mixed_binary_bytes_retain_utf8_names(self):
        self.target.write_bytes(b"\xff%PDF-1.4\x00\n" + "fixtureéagent".encode("utf-8"))
        self.assertEqual(host_name_scan.scan_paths([self.target], root=self.root),
                         [(self.target, 2)])

    def test_each_malformed_utf8_byte_has_the_native_replacement_rune(self):
        with mock.patch.dict(os.environ, {host_name_scan.OVERRIDE: json.dumps(["��"])}):
            self.target.write_bytes(b"\xe2\x82")
            self.assertEqual(host_name_scan.scan_paths([self.target], root=self.root),
                             [(self.target, 1)])

    def test_long_records_keep_names_spanning_artificial_edges(self):
        lines = ["_" * offset + name + "_" * 8000
                 for name in self.names for offset in range(3990, 4120)]
        self.assertEqual(self.scan("\n".join(lines)),
                         [(self.target, line) for line in range(1, len(lines) + 1)])

    def test_invalid_native_metadata_is_refused_without_native_text(self):
        self.target.write_text("fixtureagent", encoding="utf-8")
        invalid = ([{"RuleID": "host-name-0", "StartLine": True}],
                   [{"RuleID": "fixtureagent", "StartLine": 3}],
                   [{"RuleID": "host-name-0", "StartLine": 1}], {"fixtureagent": 1})
        for report in invalid:
            with self.subTest(report=report), mock.patch.object(
                    host_name_scan.subprocess, "run", side_effect=[
                        subprocess.CompletedProcess([], 0, "1.9.0\n", ""),
                        subprocess.CompletedProcess([], 1, json.dumps(report), "fixtureagent")]):
                with self.assertRaises(host_name_scan.HostNameScanError) as caught:
                    host_name_scan.scan_paths([self.target], root=self.root)
                self.assertNotIn("fixtureagent", str(caught.exception))

    def test_literal_config_escaping_and_framing_markers_are_not_matches(self):
        names = ('#', 'fixture"agent', r'fixture\agent', 'fixture[agent]', 'fixture💠agent')
        with mock.patch.dict(os.environ, {host_name_scan.OVERRIDE: json.dumps(names)}):
            self.assertEqual(self.scan("\n".join(names)),
                             [(self.target, line) for line in range(1, len(names) + 1)])
            self.assertEqual(self.scan("safe"), [])

    def test_private_authentication_file_is_refused_before_reading(self):
        for name in (".env", ".credentials.json", "auth.json", "AUTH.JSON"):
            with self.subTest(name=name), mock.patch.object(
                    Path, "read_bytes", side_effect=AssertionError("private file read")):
                with self.assertRaises(host_name_scan.HostNameScanError):
                    host_name_scan.scan_paths([self.root / name], root=self.root)

    def test_symbolic_link_is_refused_without_reading_its_target(self):
        link = self.root / "linked.txt"
        link.symlink_to(self.root / "auth.json")
        with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("target read")):
            with self.assertRaises(host_name_scan.HostNameScanError):
                host_name_scan.scan_paths([link], root=self.root)

    def test_native_errors_do_not_echo_config_or_diagnostics(self):
        self.target.write_text("fixtureagent", encoding="utf-8")
        version = subprocess.CompletedProcess([], 0, "1.9.0\n", "")
        error = subprocess.CompletedProcess([], 2, "fixtureagent config", "fixtureagent failure")
        with mock.patch.object(host_name_scan.subprocess, "run", side_effect=[version, error]):
            with self.assertRaises(host_name_scan.HostNameScanError) as caught:
                host_name_scan.scan_paths([self.target], root=self.root)
        self.assertNotIn("fixtureagent", str(caught.exception))

    def test_locator_sanitizes_parent_and_candidate_filename(self):
        with mock.patch.dict(os.environ, {host_name_scan.OVERRIDE: '["fixtureagent"]'}):
            label = host_name_scan.safe_locator(self.root / "fixtureagent.txt", 4, root=self.root)
        self.assertEqual(label, "<host-name>.txt:4")


if __name__ == "__main__":
    unittest.main()
