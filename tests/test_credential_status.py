"""Credential status checker: lstat-only, names-only, never prints or opens values.

Local integration class: temporary fixture files carry fake sentinel values
generated at test time; no real credential store is read.
"""

import builtins
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts import credential_status as cs

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/credential_status.py"


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
                   cwd=cwd, check=True, capture_output=True)


class CredentialStatusTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name) / "home"
        self.config = self.home / ".config"
        self.store = self.config / "native-agent-stack"
        self.store.mkdir(parents=True)
        self.store.chmod(0o700)
        self.inventory = json.loads((ROOT / cs.INVENTORY).read_text())
        # Fake sentinels generated per test; the checker must never echo them.
        self.fake_a = "SENTINELA" + os.urandom(12).hex()
        self.fake_b = "SENTINELB" + os.urandom(12).hex()
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.config)}
        # The kernel's key list is a fixture file: no test reads this host's /proc/keys.
        self.proc_keys = Path(temporary.name) / "proc-keys"
        self.proc_keys.write_text("")

    def keyring_inventory(self, status="optional"):
        """The inventory with the tavily row back in the kernel keyring, its store until 2026-09-29.

        The real inventory has no memory-only row since then, so the keyring tests plant this one."""
        inventory = copy.deepcopy(self.inventory)
        row = next(e for e in inventory["entries"] if e["id"] == "tavily")
        row["status"] = status
        row["store"] = {"kind": "kernel_keyring", "path_template": "", "key_name": "tavily_api_key"}
        return inventory

    def planted(self, inventory):
        path = self.home.parent / "planted-inventory.json"
        path.write_text(json.dumps(inventory))
        return path

    def write_alpaca(self, mode=0o600):
        path = self.store / "alpaca-paper.env"
        path.unlink(missing_ok=True)
        path.write_text(f"export APCA_API_KEY_ID={self.fake_a}\nexport APCA_API_SECRET_KEY={self.fake_b}\n")
        path.chmod(mode)
        return path

    def report(self, env=None, **kwargs):
        kwargs.setdefault("proc_keys", self.proc_keys)
        return cs.inspect(ROOT, self.inventory, self.env if env is None else env, **kwargs)

    def entry(self, report, identifier="alpaca-paper"):
        return next(e for e in report["entries"] if e["id"] == identifier)

    def assert_no_values(self, *texts):
        for text in texts:
            self.assertNotIn(self.fake_a, text)
            self.assertNotIn(self.fake_b, text)
            self.assertNotIn(str(self.home), text)

    def run_cli(self, *args):
        env = {"PATH": os.environ.get("PATH", ""), **self.env}
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(ROOT), "--proc-keys", str(self.proc_keys),
                                 *args], env=env, capture_output=True, text=True, timeout=60)
        self.assert_no_values(result.stdout, result.stderr)
        return result

    def test_real_inventory_is_valid(self):
        self.assertEqual(cs.inventory_errors(self.inventory, ROOT), [])
        ids = {e["id"] for e in self.inventory["entries"]}
        self.assertTrue({"alpaca-paper", "alpaca-paper-2", "sec-contact", "claude-native", "codex-native", "gh-native",
                         "huggingface-native", "huggingface-native-stored"} <= ids)
        self.assertIn("HUGGING_FACE_HUB_TOKEN", self.inventory["must_not_be_set"])
        self.assertIn("HF_TOKEN", self.inventory["must_not_be_set"])

    def test_second_paper_row_mirrors_the_first(self):
        # alpaca-paper-2 names the second paper account's existing file: same class, lane, store kind and variables as
        # account 1, its own file and its own pointer (2026-09-29), and neither row shares a pointer with the other.
        rows = {e["id"]: e for e in self.inventory["entries"]}
        first, second = rows["alpaca-paper"], rows["alpaca-paper-2"]
        for key in ("class", "lane", "variables", "optional_variables"):
            self.assertEqual(second[key], first[key], key)
        self.assertEqual(second["store"]["kind"], first["store"]["kind"])
        self.assertEqual(second["store"]["path_template"], first["store"]["path_template"].replace("alpaca-paper.env", "alpaca-paper-2.env"))
        self.assertEqual(second["pointer_variables"], ["PAPER_ENV_FILE_2"])
        self.assertFalse(set(second["pointer_variables"]) & set(first["pointer_variables"]))

    def test_public_variables_classify_every_optional_stored_variable(self):
        # 2026-09-29 (tools/credentials/credential_run.py): the key runner masks every variable it injects except the
        # names in the entry's optional public_variables, which may name only optional variables that are not secret,
        # such as a base URL. An env-file entry with optional variables must classify them, even as [] (all masked).
        rows = {e["id"]: e for e in self.inventory["entries"]}
        self.assertEqual(rows["alpaca-paper"]["public_variables"], ["APCA_API_BASE_URL"])
        self.assertEqual(rows["alpaca-paper-2"]["public_variables"], ["APCA_API_BASE_URL"])
        self.assertEqual(rows["sec-contact"]["public_variables"], [])  # EDGAR_IDENTITY is private contact data
        self.assertEqual(rows["grafana-admin"]["public_variables"], [])
        self.assertEqual([i for i, e in rows.items() if "public_variables" in e and not e["optional_variables"]], [])
        cases = [
            (lambda row: row.__setitem__("public_variables", "APCA_API_BASE_URL"), "uppercase variable names"),
            (lambda row: row.__setitem__("public_variables", ["APCA_API_KEY_ID"]), "optional_variables"),
            (lambda row: row.__setitem__("public_variables", ["TAVILY_API_KEY"]), "optional_variables"),
            (lambda row: row.__setitem__("public_variables", ["APCA_API_BASE_URL"] * 2), "optional_variables"),
            (lambda row: row.pop("public_variables"), "must classify"),
        ]
        for mutate, message in cases:
            broken = copy.deepcopy(self.inventory)
            mutate(next(e for e in broken["entries"] if e["id"] == "alpaca-paper"))
            with self.subTest(message=message):
                errors = cs.inventory_errors(broken, ROOT)
                self.assertEqual(len(errors), 1, errors)
                self.assertIn("entries[0]: ", errors[0])
                self.assertIn(message, errors[0])
        # A row without optional variables needs no classification; the field stays optional.
        tavily = copy.deepcopy(self.inventory)
        self.assertNotIn("public_variables", next(e for e in tavily["entries"] if e["id"] == "tavily"))
        self.assertEqual(cs.inventory_errors(tavily, ROOT), [])

    def test_variable_lists_reject_overlap_and_repeats_and_keep_required_masked(self):
        # Review of 2026-09-29: a REQUIRED variable listed again in optional_variables and in public_variables passed
        # the schema and dropped out of masked_names(), so the runner would have injected it unmasked.
        def planted(mutate):
            broken = copy.deepcopy(self.inventory)
            row = next(e for e in broken["entries"] if e["id"] == "alpaca-paper")
            mutate(row)
            return broken, row

        cases = [
            ("variables and optional_variables must not share a name",
             lambda row: row["optional_variables"].append("APCA_API_KEY_ID")),
            ("variables and optional_variables must not share a name",  # the review's case: also public
             lambda row: (row["optional_variables"].append("APCA_API_SECRET_KEY"),
                          row["public_variables"].append("APCA_API_SECRET_KEY"))),
            ("public_variables must name distinct optional_variables",  # a required name that is not optional
             lambda row: row["public_variables"].append("APCA_API_SECRET_KEY")),
            ("variables must not repeat a name",
             lambda row: row["variables"].append("APCA_API_KEY_ID")),
            ("optional_variables must not repeat a name",
             lambda row: row["optional_variables"].append("APCA_API_BASE_URL")),
            ("pointer_variables must not repeat a name",
             lambda row: row["pointer_variables"].append("PAPER_ENV_FILE")),
            ("public_variables must name distinct optional_variables",
             lambda row: row["public_variables"].append("APCA_API_BASE_URL")),
        ]
        for message, mutate in cases:
            broken, _row = planted(mutate)
            with self.subTest(message=message):
                errors = cs.inventory_errors(broken, ROOT)
                self.assertEqual(len(errors), 1, errors)
                self.assertIn("entries[0]: ", errors[0])
                self.assertIn(message, errors[0])
        # Whatever the schema check reports, the masked set is computed from the validated shape: a required variable
        # is masked even when a planted entry lists it as public, and a public name is only ever an optional one.
        _broken, row = planted(lambda row: (row["optional_variables"].append("APCA_API_SECRET_KEY"),
                                            row["public_variables"].append("APCA_API_SECRET_KEY")))
        self.assertIn("APCA_API_SECRET_KEY", cs.masked_names(row))
        self.assertNotIn("APCA_API_SECRET_KEY", cs.public_names(row))
        self.assertEqual(cs.public_names(row), ["APCA_API_BASE_URL"])
        real = next(e for e in self.inventory["entries"] if e["id"] == "alpaca-paper")
        self.assertEqual(cs.masked_names(real), ["APCA_API_KEY_ID", "APCA_API_SECRET_KEY"])
        self.assertEqual(cs.public_names(real), ["APCA_API_BASE_URL"])
        self.assertEqual(cs.inventory_errors(self.inventory, ROOT), [])

    def test_inventory_rejects_non_home_template_and_bad_names(self):
        broken = copy.deepcopy(self.inventory)
        broken["entries"][0]["store"]["path_template"] = "/srv/shared/alpaca.env"
        broken["entries"][1]["variables"] = ["SEC_USER_AGENT=someone"]
        errors = cs.inventory_errors(broken, ROOT)
        self.assertTrue(any("home-anchored" in e for e in errors))
        self.assertTrue(any("uppercase variable names" in e for e in errors))

    def test_kernel_keyring_row_is_validated_and_never_inspected(self):
        # No real row is memory only since 2026-09-29 (test_tavily_row_is_a_stored_file_entry); a planted one is
        # still validated, never inspected as a file, and the keyring is never queried for it.
        inventory = self.keyring_inventory()
        row = next(e for e in inventory["entries"] if e["id"] == "tavily")
        self.assertEqual((row["class"], row["variables"], row["store"]),
                         ("provider_api_key", ["TAVILY_API_KEY"],
                          {"kind": "kernel_keyring", "path_template": "", "key_name": "tavily_api_key"}))
        self.assertEqual(cs.inventory_errors(inventory, ROOT), [])
        report = cs.inspect(ROOT, inventory, self.env, proc_keys=self.proc_keys)
        entry = self.entry(report, "tavily")
        self.assertEqual((entry["state"], entry["key_name"], entry["findings"]), ("unchecked", "tavily_api_key", []))
        self.assertNotIn("mode", entry)
        self.assertEqual(report["result"], "ok")
        self.assertIn("unchecked tavily", cs.render_text(report))
        self.assertIn("(kernel keyring tavily_api_key; check: kernel_keyring.py status)", cs.render_text(report))
        result = self.run_cli("--inventory", str(self.planted(inventory)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("unchecked tavily", result.stdout)
        # Exported in the launcher's environment instead, it is reported by name only.
        exported_report = cs.inspect(ROOT, inventory, {**self.env, "TAVILY_API_KEY": self.fake_a},
                                     proc_keys=self.proc_keys)
        exported = self.entry(exported_report, "tavily")
        self.assertEqual(exported["variables_in_environment"], ["TAVILY_API_KEY"])
        self.assertIn("store_variables_exported_in_environment", exported["warnings"])
        self.assert_no_values(json.dumps(exported_report), cs.render_text(exported_report))

    def test_canary_row_is_test_only_and_informational_when_missing(self):
        # 2026-09-29 (tools/credentials/canary_e2e.py, D1 PR-5): the canary proof's synthetic key, created and removed for
        # each consumer of a run, is class test_canary and status test_only. A missing file is informational: no finding,
        # no warning, result ok and exit 0.
        row = next(e for e in self.inventory["entries"] if e["id"] == "canary-e2e")
        self.assertEqual((row["class"], row["status"], row["variables"], row["optional_variables"],
                          row["pointer_variables"], row["loaders"]),
                         ("test_canary", "test_only", ["CANARY_E2E_KEY"], [], [], []))
        self.assertEqual(row["store"], {"kind": "private_env_file",
                                        "path_template": "${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack/canary-e2e.env"})
        self.assertNotIn("public_variables", row)  # no optional variables, so nothing to classify
        self.assertIn("tools/credentials/canary_e2e.py", row["rotation"])
        report = self.report()
        entry = self.entry(report, "canary-e2e")
        self.assertEqual((entry["state"], entry["findings"], entry["warnings"]), ("missing", [], []))
        self.assertEqual((report["result"], report["warnings"], report["unsafe_stored"]), ("ok", [], []))
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"(?m)^missing +canary-e2e +test_only ")
        # While a run holds it, the file is an ordinary declared row of the store, checked like any other.
        path = self.store / "canary-e2e.env"
        path.write_text(f"export CANARY_E2E_KEY={self.fake_a}\n")
        path.chmod(0o600)
        report = self.report()
        self.assertEqual(self.entry(report, "canary-e2e")["state"], "ok")
        self.assertEqual(report["coverage"]["undeclared_store_files"], [])
        path.chmod(0o644)
        self.assertEqual(self.entry(self.report(), "canary-e2e")["findings"], ["mode_not_0600"])
        self.assert_no_values(json.dumps(self.report()), cs.render_text(self.report()))

    def test_test_only_status_goes_with_the_test_canary_class(self):
        # Neither may label another key: a real key marked test_only would read as a disposable canary.
        for status, klass, valid in (("test_only", "test_canary", True), ("test_only", "provider_api_key", False),
                                     ("optional", "test_canary", False), ("test-only", "test_canary", False)):
            with self.subTest(status=status, klass=klass):
                broken = copy.deepcopy(self.inventory)
                row = next(e for e in broken["entries"] if e["id"] == "tavily")
                row["status"], row["class"] = status, klass
                errors = cs.inventory_errors(broken, ROOT)
                self.assertEqual(errors == [], valid, errors)

    def test_tavily_row_is_a_stored_file_entry(self):
        # 2026-09-29 (docs/decisions/2026-09-29-key-management.md): the key moved from the kernel keyring, which a
        # kernel restart erases, to its own 0600 file in the store. No real row is memory only any more.
        row = next(e for e in self.inventory["entries"] if e["id"] == "tavily")
        self.assertEqual((row["class"], row["status"], row["variables"], row["optional_variables"],
                          row["pointer_variables"]), ("provider_api_key", "optional", ["TAVILY_API_KEY"], [], []))
        self.assertEqual(row["store"], {"kind": "private_env_file",
                                        "path_template": "${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack/tavily.env"})
        self.assertIn("open_credential_terminal.sh tavily", row["rotation"])
        self.assertIn("docs/decisions/2026-09-29-key-management.md", row["notes"])
        self.assertEqual([e["id"] for e in self.inventory["entries"] if e["store"]["kind"] in cs.MEMORY_KINDS], [])
        self.assertEqual(self.entry(self.report(), "tavily")["state"], "missing")
        path = self.store / "tavily.env"
        path.write_text(f"export TAVILY_API_KEY={self.fake_a}\n")
        path.chmod(0o600)
        report = self.report()
        entry = self.entry(report, "tavily")
        self.assertEqual((entry["state"], entry["mode"], entry["findings"]), ("ok", "0600", []))
        self.assertNotIn("persistence", entry)
        self.assertEqual(report["coverage"]["undeclared_store_files"], [])
        self.assert_no_values(json.dumps(report), cs.render_text(report))
        path.chmod(0o644)
        self.assertIn("mode_not_0600", self.entry(self.report(), "tavily")["findings"])

    def test_interim_tavily_rotation_step_is_stated_once_in_each_place(self):
        # Until the id-based runner lands, tvly-keyring and kernel_keyring.py exec read the keyring copy, not the file,
        # so renewing only the file would leave them on the old key. The step is stated once, dated, in the inventory
        # notes and in both pages that tell how to rotate; the runner's change deletes it and this test.
        marker = "Interim step (2026-09-29, until the id-based runner lands)"
        row = next(e for e in self.inventory["entries"] if e["id"] == "tavily")
        places = {"inventory notes": row["notes"],
                  "docs/secret-storage.md": (ROOT / "docs/secret-storage.md").read_text(encoding="utf-8"),
                  "recipes/tavily.md": (ROOT / "recipes/tavily.md").read_text(encoding="utf-8")}
        for place, text in places.items():
            with self.subTest(place=place):
                self.assertEqual(text.count(marker), 1)
                step = text.split(marker, 1)[1].split("\n\n", 1)[0]  # the step's own paragraph
                for words in ("open_credential_terminal.sh tavily", "kernel_keyring.py store --replace tavily_api_key",
                              "next kernel restart"):
                    self.assertIn(words, step)

    def test_keyring_row_reports_memory_only_lost_on_restart(self):
        inventory = self.keyring_inventory()
        report = cs.inspect(ROOT, inventory, self.env, proc_keys=self.proc_keys)
        entry = self.entry(report, "tavily")
        self.assertEqual((entry["state"], entry["persistence"]), ("unchecked", "memory_only"))
        self.assertIn("memory_only_lost_on_restart", entry["warnings"])
        self.assertEqual(report["result"], "ok")  # a warning, not a failure
        self.assertIn("warnings=memory_only_lost_on_restart", cs.render_text(report))
        result = self.run_cli("--inventory", str(self.planted(inventory)), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        listed = self.entry(json.loads(result.stdout), "tavily")
        self.assertEqual((listed["state"], listed["persistence"]), ("unchecked", "memory_only"))
        self.assertIn("memory_only_lost_on_restart", listed["warnings"])

    def test_required_keyring_row_is_an_inventory_error(self):
        # A required key must survive a restart, and nothing in the kernel keyring does.
        errors = cs.inventory_errors(self.keyring_inventory("required"), ROOT)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("required", errors[0])
        self.assertIn("restart", errors[0])
        self.assertEqual(cs.inventory_errors(self.keyring_inventory("optional"), ROOT), [])
        result = self.run_cli("--inventory", str(self.planted(self.keyring_inventory("required"))))
        self.assertEqual(result.returncode, 2)
        self.assertIn("required", result.stderr)

    def test_undeclared_store_file_is_reported_by_name_only(self):
        self.write_alpaca()  # declared by alpaca-paper
        stray = self.store / "stray.env"
        stray.write_text(f"export STRAY_API_KEY={self.fake_b}\n")
        stray.chmod(0o600)
        leftover = self.store / ".tavily.env.0123456789abcdef.tmp"  # what an interrupted write would leave
        leftover.write_text(f"export TAVILY_API_KEY={self.fake_a}\n")
        (self.store / "link.env").symlink_to(stray)  # listed, never followed
        (self.store / "subdirectory").mkdir()  # directories are not listed
        opened = []
        real_open, real_os_open = builtins.open, os.open

        def watch_open(file, *args, **kwargs):
            opened.append(str(file))
            return real_open(file, *args, **kwargs)

        def watch_os_open(file, *args, **kwargs):
            opened.append(str(file))
            return real_os_open(file, *args, **kwargs)

        with patch("builtins.open", watch_open), patch("os.open", watch_os_open), \
                patch.object(Path, "read_text", side_effect=AssertionError("read_text called")), \
                patch.object(Path, "read_bytes", side_effect=AssertionError("read_bytes called")):
            report = self.report()
        self.assertFalse([p for p in opened if str(self.store) in p])
        names = [".tavily.env.0123456789abcdef.tmp", "link.env", "stray.env"]
        self.assertEqual(report["coverage"]["undeclared_store_files"], names)
        self.assertIn("undeclared_store_file", report["warnings"])
        self.assertEqual(report["result"], "ok")  # a warning, not a failure
        text = cs.render_text(report)
        self.assertIn("undeclared store files (names only): " + ",".join(names), text)
        self.assert_no_values(json.dumps(report), text)
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(",".join(names), result.stdout)
        # Nothing undeclared, or no store yet: an empty list and no warning.
        for path in (stray, leftover, self.store / "link.env"):
            path.unlink()
        clean = self.report()
        self.assertEqual((clean["coverage"]["undeclared_store_files"], clean["warnings"]), ([], []))
        self.assertEqual(self.report({**self.env, "XDG_CONFIG_HOME": str(self.home / "none")})[
            "coverage"]["undeclared_store_files"], [])
        # A store root that is a symbolic link is never listed through the link.
        elsewhere = self.home / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "other.env").write_text(f"export OTHER_API_KEY={self.fake_b}\n")
        (self.home / "linked").mkdir()
        (self.home / "linked" / "native-agent-stack").symlink_to(elsewhere)
        linked = self.report({**self.env, "XDG_CONFIG_HOME": str(self.home / "linked")})
        self.assertIsNone(linked["coverage"]["undeclared_store_files"])
        self.assertIn("undeclared store files (names only): unknown", cs.render_text(linked))

    def test_undeclared_keyring_key_is_reported_from_a_proc_keys_fixture(self):
        # Lines in the kernel's format (linux v6.18 security/keys/proc.c, proc_keys_show(): serial, the seven flags
        # I R D Q U N i, usage, expiry, permissions, uid, gid, type; a user key's description then ends with
        # ": <payload length>", user_describe() in security/keys/user_defined.c). Only live keys of this uid named
        # native-agent-stack:<name> count, by name, and a kernel_keyring row claims its key_name.
        uid = os.getuid()

        def line(serial, flags, expiry, owner, kind, description):
            return f"{serial:08x} {flags} {1:5d} {expiry:>4} 3f0b0000 {owner:5d} {owner:5d} {kind:<9.9} {description}\n"

        self.proc_keys.write_text("".join([
            line(0x1a2b3c4d, "I--Q---", "perm", uid, "user", "native-agent-stack:alpaca-paper-1-id: 26"),
            line(0x1a2b3c4e, "I--Q---", "perm", uid, "user", "native-agent-stack:tavily_api_key: 41"),
            line(0x1a2b3c4f, "I--Q---", "59m", uid, "user", "native-agent-stack:alpaca-paper-2-secret: 44"),
            line(0x1a2b3c50, "IR-Q---", "perm", uid, "user", "native-agent-stack:revoked-spare"),
            line(0x1a2b3c51, "I--Q--i", "perm", uid, "user", "native-agent-stack:invalidated-spare: 20"),
            line(0x1a2b3c52, "I--Q---", "expd", uid, "user", "native-agent-stack:expired-spare: 20"),
            line(0x1a2b3c53, "I--Q-N-", "perm", uid, "user", "native-agent-stack:negative-spare"),
            line(0x1a2b3c54, "I--Q---", "perm", uid + 1, "user", "native-agent-stack:another-uid: 20"),
            line(0x1a2b3c55, "I--Q---", "perm", uid, "user", "another-project:key: 20"),
            line(0x1a2b3c56, "I--Q---", "perm", uid, "keyring", f"_uid.{uid}: 2"),
        ]))
        report = self.report()
        # The real inventory has no kernel_keyring row, so tavily_api_key is undeclared until the kernel restarts.
        undeclared = ["alpaca-paper-1-id", "alpaca-paper-2-secret", "tavily_api_key"]
        self.assertEqual(report["coverage"]["undeclared_keyring_keys"], undeclared)
        self.assertIn("undeclared_keyring_key", report["warnings"])
        self.assertEqual(report["result"], "ok")  # a warning, not a failure
        self.assertIn(",".join(undeclared), cs.render_text(report))
        claimed = cs.inspect(ROOT, self.keyring_inventory(), self.env, proc_keys=self.proc_keys)
        self.assertEqual(claimed["coverage"]["undeclared_keyring_keys"], undeclared[:2])
        result = self.run_cli("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["coverage"]["undeclared_keyring_keys"], undeclared)
        # No readable key list (macOS has none): reported as not checked, without a warning.
        absent = self.report(proc_keys=self.home / "no-proc-keys")
        self.assertIsNone(absent["coverage"]["undeclared_keyring_keys"])
        self.assertNotIn("undeclared_keyring_key", absent["warnings"])
        self.assertIn("undeclared kernel keyring keys (names only): not checked", cs.render_text(absent))
        self.assertEqual(cs.PROC_KEYS, Path("/proc/keys"))  # the CLI's default

    def test_proc_keys_descriptions_are_compared_whole_and_reported_in_full(self):
        # user_describe() prints a user key's whole description, which may hold "/", ":" and spaces, then
        # ": <payload length>" for a positive key. Only that last suffix is stripped; a kernel_keyring row's key_name
        # must equal the rest after "native-agent-stack:" exactly, and every other such key is reported by its full
        # name, never cut at a "/" or ":" (2026-09-29 cross-family review: both were dropped or hidden).
        uid = os.getuid()

        def line(serial, description, kind="user"):
            return f"{serial:08x} I--Q--- {1:5d} perm 3f0b0000 {uid:5d} {uid:5d} {kind:<9.9} {description}\n"

        self.proc_keys.write_text("".join([
            line(0x2a000001, "native-agent-stack:paper/backup: 41"),
            line(0x2a000002, "native-agent-stack:tavily_api_key:backup: 41"),
            line(0x2a000003, "native-agent-stack:tavily_api_key2: 41"),
            line(0x2a000004, "native-agent-stack:tavily_api_key: 41"),
            line(0x2a000005, "native-agent-stack:note: 12: 7"),  # a description that itself ends in ": 12"
            line(0x2a000006, "native-agent-stack:with space: 9"),
            line(0x2a000007, "native-agent-stack:logon-key: 9", kind="logon"),  # only user keys are listed
        ]))
        full_names = ["note: 12", "paper/backup", "tavily_api_key2", "tavily_api_key:backup", "with space"]
        declared = cs.inspect(ROOT, self.keyring_inventory(), self.env, proc_keys=self.proc_keys)
        self.assertEqual(declared["coverage"]["undeclared_keyring_keys"], full_names)  # the declared key is not listed
        text = cs.render_text(declared)
        for name in ("paper/backup", "tavily_api_key:backup", "tavily_api_key2"):
            self.assertIn(name, text)
        # With no kernel_keyring row, as in the real inventory, tavily_api_key itself is undeclared as well.
        self.assertEqual(self.report()["coverage"]["undeclared_keyring_keys"],
                         ["note: 12", "paper/backup", "tavily_api_key", "tavily_api_key2", "tavily_api_key:backup",
                          "with space"])

    def test_inventory_rejects_a_keyring_row_with_a_path_or_bad_key_name(self):
        index = next(i for i, e in enumerate(self.inventory["entries"]) if e["id"] == "tavily")
        for store, message in (
                ({"kind": "kernel_keyring", "path_template": "$HOME/.tavily/config.json", "key_name": "tavily_api_key"},
                 "empty path template"),
                ({"kind": "kernel_keyring", "path_template": ""}, "key_name"),
                ({"kind": "kernel_keyring", "path_template": "", "key_name": "Tavily/Key"}, "key_name")):
            broken = copy.deepcopy(self.inventory)
            broken["entries"][index]["store"] = store
            with self.subTest(store=store):
                self.assertTrue(any(message in error for error in cs.inventory_errors(broken, ROOT)))

    def test_missing_required_file_is_informational(self):
        entry = self.entry(self.report())
        self.assertEqual(entry["state"], "missing")
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("missing   alpaca-paper", result.stdout)

    def test_private_file_is_ok_and_output_is_value_free(self):
        self.write_alpaca()
        report = self.report()
        entry = self.entry(report)
        self.assertEqual(entry["state"], "ok")
        self.assertEqual(entry["mode"], "0600")
        self.assertEqual(entry["directory_mode"], "0700")
        self.assertFalse(entry["inside_git_worktree"])
        self.assertFalse(report["values_read"])
        self.assert_no_values(json.dumps(report), cs.render_text(report))
        result = self.run_cli("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["result"], "ok")

    def test_group_readable_required_file_fails_closed(self):
        for mode in (0o644, 0o640, 0o400):
            with self.subTest(mode=oct(mode)):
                self.write_alpaca(mode)
                entry = self.entry(self.report())
                self.assertEqual(entry["state"], "unsafe")
                self.assertIn("mode_not_0600", entry["findings"])
        self.write_alpaca(0o644)
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("mode_not_0600", result.stdout)

    def test_unsafe_optional_file_also_fails_but_missing_optional_does_not(self):
        path = self.store / "typesafe.env"
        path.write_text(f"export TYPESAFE_API_KEY={self.fake_a}\n")
        path.chmod(0o644)
        report = self.report()
        self.assertEqual(self.entry(report, "typesafe")["state"], "unsafe")
        self.assertEqual(report["unsafe_stored"], ["typesafe"])
        self.assertEqual(report["unsafe_required"], [])
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        path.unlink()
        self.assertEqual(self.entry(self.report(), "typesafe")["state"], "missing")
        self.assertEqual(self.run_cli().returncode, 0)

    def test_open_store_directory_is_unsafe(self):
        self.write_alpaca()
        self.store.chmod(0o755)
        self.assertIn("directory_group_or_other_access", self.entry(self.report())["findings"])

    def test_foreign_owner_is_unsafe(self):
        self.write_alpaca()
        entry = self.entry(self.report(uid=os.getuid() + 1))
        self.assertIn("foreign_owner", entry["findings"])

    def test_symlink_is_refused_not_followed(self):
        target = self.home / "elsewhere.env"
        target.write_text(f"export APCA_API_KEY_ID={self.fake_a}\n")
        target.chmod(0o600)
        (self.store / "alpaca-paper.env").symlink_to(target)
        entry = self.entry(self.report())
        self.assertEqual(entry["state"], "unsafe")
        self.assertIn("symlink_refused", entry["findings"])

    def test_store_inside_git_worktree_and_tracked_is_unsafe(self):
        git(self.home, "init", "-q")
        path = self.write_alpaca()
        entry = self.entry(self.report())
        self.assertIn("inside_git_worktree", entry["findings"])
        self.assertNotIn("tracked_by_git", entry["findings"])
        git(self.home, "add", "-f", str(path))
        entry = self.entry(self.report())
        self.assertIn("tracked_by_git", entry["findings"])

    def test_linked_worktree_git_file_counts_as_worktree(self):
        (self.config / ".git").write_text("gitdir: /nonexistent/worktrees/x\n")
        self.write_alpaca()
        self.assertIn("inside_git_worktree", self.entry(self.report())["findings"])

    def test_old_file_is_a_warning_not_a_failure(self):
        path = self.write_alpaca()
        old = time.time() - 120 * 86400
        os.utime(path, (old, old))
        entry = self.entry(self.report())
        self.assertEqual(entry["state"], "ok")
        self.assertIn("older_than_90_days", entry["warnings"])

    def test_exported_names_reported_without_values(self):
        env = {**self.env, "APCA_API_KEY_ID": self.fake_a, "GH_TOKEN": self.fake_b}
        report = self.report(env)
        self.assertEqual(self.entry(report)["variables_in_environment"], ["APCA_API_KEY_ID"])
        self.assertEqual(report["environment"]["must_not_be_set_present"], ["GH_TOKEN"])
        self.assert_no_values(json.dumps(report), cs.render_text(report))
        cli_env = {"APCA_API_KEY_ID": self.fake_a, "GH_TOKEN": self.fake_b}
        with patch.dict(self.env, cli_env):
            result = self.run_cli("--json")
        self.assertIn("GH_TOKEN", result.stdout)

    def test_never_opens_or_reads_credential_files(self):
        self.write_alpaca()
        opened = []
        real_open, real_os_open = builtins.open, os.open

        def watch_open(file, *args, **kwargs):
            opened.append(str(file))
            return real_open(file, *args, **kwargs)

        def watch_os_open(file, *args, **kwargs):
            opened.append(str(file))
            return real_os_open(file, *args, **kwargs)

        with patch("builtins.open", watch_open), patch("os.open", watch_os_open), \
                patch.object(Path, "read_text", side_effect=AssertionError("read_text called")), \
                patch.object(Path, "read_bytes", side_effect=AssertionError("read_bytes called")):
            self.report()
        self.assertFalse([p for p in opened if str(self.store) in p])

    def test_client_guards_reports_booleans_only(self):
        claude = self.home / ".claude"
        (claude / "hooks").mkdir(parents=True)
        (claude / "hooks" / "secret_path_guard.py").write_text("# stand-in\n")
        (claude / "settings.json").write_text(json.dumps({
            "permissions": {"deny": ["Read(~/.config/native-agent-stack/**)"]},
            "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
                {"type": "command", "command": "python3 /h/.claude/hooks/secret_path_guard.py"}]}]},
            "env": {"SOME_PROVIDER_VALUE": self.fake_b, "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
                    "OTEL_LOG_TOOL_CONTENT": "1", "OTEL_LOG_RAW_API_BODIES": f"file:/tmp/{self.fake_b}",
                    "OTEL_LOG_USER_PROMPTS": "false"}}))
        codex = self.home / ".codex"
        codex.mkdir()
        (codex / "config.toml").write_text('[shell_environment_policy]\ninherit = "none"\n')
        report = self.report(with_client_guards=True)
        self.assertEqual(report["client_guards"], {
            "claude_user_deny_rules": True,
            "claude_user_secret_guard_hook": True,
            "claude_sandbox_enabled": False,
            "claude_telemetry_logs_content": True,
            "claude_telemetry_content_flags": {
                "OTEL_LOG_TOOL_CONTENT": True, "OTEL_LOG_TOOL_DETAILS": False,
                "OTEL_LOG_USER_PROMPTS": False, "OTEL_LOG_ASSISTANT_RESPONSES": False,
                "OTEL_LOG_RAW_API_BODIES": True},
            "codex_shell_environment_inherit_none": True,
            "claude_user_guard_matches_pin": False})  # the stand-in's bytes are not the pinned guard's
        self.assert_no_values(json.dumps(report))
        self.assert_no_values(cs.render_text(report))
        self.assertIn("claude telemetry logs content: true", cs.render_text(report))

    def test_guard_pin_check_hashes_only_the_installed_guard(self):
        # claude_user_guard_matches_pin (2026-09-29): the sha256 of the installed user-scope guard against the
        # checkout's pin line in adoption/hooks/claude/SHA256SUMS, whose paths are relative to that file as
        # tools/adoption/install_claude_profile.py reads them. One boolean; the guard is the only file it reads.
        claude = self.home / ".claude"
        installed = claude / "hooks" / "secret_path_guard.py"
        installed.parent.mkdir(parents=True)
        guard_bytes = (ROOT / "scripts/hooks/secret_path_guard.py").read_bytes()

        def matches():
            guards = self.report(with_client_guards=True)["client_guards"]
            self.assertTrue(cs.only_booleans(guards))
            return guards["claude_user_guard_matches_pin"]

        self.assertIs(matches(), False)  # not installed
        installed.write_bytes(guard_bytes)
        self.assertIs(matches(), True)  # what the installer copies from this checkout
        installed.write_bytes(guard_bytes + b"\n")
        self.assertIs(matches(), False)  # one byte more
        installed.unlink()
        installed.symlink_to(ROOT / "scripts/hooks/secret_path_guard.py")
        self.assertIs(matches(), False)  # a link is never followed, even to the pinned bytes
        installed.unlink()
        installed.mkdir()
        self.assertIs(matches(), False)  # nor is a directory hashed
        installed.rmdir()
        # A link planted in the guard's place, pointing at a store file, never makes the check open that file.
        installed.symlink_to(self.write_alpaca())
        opened = []
        real_open, real_io_open, real_os_open = builtins.open, io.open, os.open

        def watch(real):
            def opener(file, *args, **kwargs):
                opened.append(str(file))
                return real(file, *args, **kwargs)
            return opener

        with patch("builtins.open", watch(real_open)), patch("io.open", watch(real_io_open)), \
                patch("os.open", watch(real_os_open)):
            self.assertIs(matches(), False)
        self.assertTrue(opened)  # the watch saw the guard path
        self.assertFalse([p for p in opened if str(self.store) in p])
        installed.unlink()
        # A synthetic checkout: its pin line decides, and a checkout without one never matches.
        checkout = self.home / "checkout"
        pins = checkout / "adoption/hooks/claude/SHA256SUMS"
        pins.parent.mkdir(parents=True)
        body = b"# a synthetic guard\n"
        installed.write_bytes(body)
        digest = hashlib.sha256(body).hexdigest()
        pins.write_text(f"{digest}  ../../../scripts/hooks/secret_path_guard.py\n")
        self.assertIs(cs.guard_matches_pin(claude, checkout), True)
        pins.write_text(f"{digest}  effort-default-guard.py\n")
        self.assertIs(cs.guard_matches_pin(claude, checkout), False)
        pins.unlink()
        self.assertIs(cs.guard_matches_pin(claude, checkout), False)
        # The CLI prints the boolean with the other client guards and never a digest.
        installed.write_bytes(guard_bytes)
        result = self.run_cli("--json", "--client-guards")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIs(json.loads(result.stdout)["client_guards"]["claude_user_guard_matches_pin"], True)
        self.assertNotIn(hashlib.sha256(guard_bytes).hexdigest(), result.stdout)
        text = self.run_cli("--client-guards").stdout
        self.assertIn('"claude_user_guard_matches_pin": true', text)

    def write_client_settings(self):
        claude = self.home / ".claude"
        (claude / "hooks").mkdir(parents=True)
        (claude / "hooks" / "secret_path_guard.py").write_text("# stand-in\n")
        (claude / "settings.json").write_text(json.dumps({
            "permissions": {"deny": ["Read(~/.config/native-agent-stack/**)"]},
            "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
                {"type": "command", "command": "python3 /h/.claude/hooks/secret_path_guard.py"}]}]},
            "env": {"SOME_PROVIDER_VALUE": self.fake_a, "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
                    "OTEL_LOG_TOOL_CONTENT": "1", "OTEL_LOG_RAW_API_BODIES": f"file:/tmp/{self.fake_b}"}}))
        codex = self.home / ".codex"
        codex.mkdir()
        (codex / "config.toml").write_text(f'[shell_environment_policy]\ninherit = "none"\n# {self.fake_b}\n')

    def test_cli_output_never_contains_values_in_any_mode(self):
        self.write_alpaca()
        self.write_client_settings()
        exported = {"APCA_API_KEY_ID": self.fake_a, "GH_TOKEN": self.fake_b}
        for args in ((), ("--json",), ("--client-guards",), ("--json", "--client-guards")):
            with self.subTest(args=args), patch.dict(self.env, exported):
                result = self.run_cli(*args)  # run_cli asserts both fake values are absent
                # The store is safe (0600 in 0700), so the verdict is 0; the exported
                # must-not-be-set name is reported by name, never by value.
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertIn("APCA_API_KEY_ID", result.stdout)
                if "--json" not in args:
                    self.assertIn("result: ", result.stdout)
                    if "--client-guards" in args:
                        self.assertIn("client guards: ", result.stdout)
                if "--json" in args:
                    report = json.loads(result.stdout)
                    if "--client-guards" in args:
                        self.assertTrue(cs.only_booleans(report["client_guards"]))
                        self.assertTrue(report["client_guards"]["claude_telemetry_logs_content"])

    def test_wrong_type_settings_fields_do_not_crash(self):
        claude = self.home / ".claude"
        claude.mkdir(exist_ok=True)
        (claude / "settings.json").write_text(json.dumps({"permissions": {"deny": 3}, "hooks": {"PreToolUse": 7}}))
        self.assertIsNone(cs.claude_guard_booleans(claude))

    def test_settings_env_is_reduced_to_key_names(self):
        present, enabled = cs.enabled_names({"SOME_PROVIDER_VALUE": self.fake_a, "OFF": "0", 3: "x"})
        self.assertEqual(present, {"SOME_PROVIDER_VALUE", "OFF"})
        self.assertEqual(enabled, {"SOME_PROVIDER_VALUE"})
        self.assertEqual(cs.enabled_names("not a dict"), (frozenset(), frozenset()))

    def test_telemetry_flags_need_telemetry_enabled_and_follow_documented_fallback(self):
        off = cs.telemetry_content_logging({"OTEL_LOG_TOOL_CONTENT": "1"})
        self.assertFalse(off["logs_content"])
        self.assertTrue(off["flags"]["OTEL_LOG_TOOL_CONTENT"])
        fallback = cs.telemetry_content_logging({"CLAUDE_CODE_ENABLE_TELEMETRY": "1",
                                                 "OTEL_LOG_USER_PROMPTS": "1"})
        self.assertTrue(fallback["flags"]["OTEL_LOG_ASSISTANT_RESPONSES"])
        self.assertTrue(fallback["logs_content"])
        redacted = cs.telemetry_content_logging({"CLAUDE_CODE_ENABLE_TELEMETRY": "1", "OTEL_LOG_TOOL_CONTENT": "0",
                                                 "OTEL_LOG_RAW_API_BODIES": "false", "OTEL_LOG_TOOL_DETAILS": ""})
        self.assertFalse(redacted["logs_content"])
        self.assertEqual(cs.telemetry_content_logging(None)["flags"]["OTEL_LOG_USER_PROMPTS"], False)

    def test_codex_counts_only_inherit_none_as_guarded(self):
        codex = self.home / ".codex"
        codex.mkdir()
        for body, expected in (('inherit = "none"\n', True), ('inherit = "core"\n', False),
                               ('inherit = "all"\nignore_default_excludes = false\nexclude = ["*KEY*"]\n', False),
                               ('', False)):
            with self.subTest(body=body):
                (codex / "config.toml").write_text("[shell_environment_policy]\n" + body)
                guards = self.report(with_client_guards=True)["client_guards"]
                self.assertIs(guards["codex_shell_environment_inherit_none"], expected)

    def test_guard_hook_needs_registration_and_installed_file(self):
        claude = self.home / ".claude"
        claude.mkdir()
        (claude / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": "python3 /h/.claude/hooks/secret_path_guard.py"}]}]}}))
        guards = self.report(with_client_guards=True)["client_guards"]
        self.assertFalse(guards["claude_user_secret_guard_hook"])
        self.assertIsNone(guards["codex_shell_environment_inherit_none"])

    def test_tracked_sensitive_names_match_basenames_only(self):
        repo = self.home / "repo"
        (repo / "evidence/secrets-credentials").mkdir(parents=True)
        (repo / "docs").mkdir()
        (repo / "cache/huggingface").mkdir(parents=True)
        for name in ("leak.env", "evidence/secrets-credentials/receipt.json",
                     "docs/alpaca-paper.env.example", "service.key",
                     "cache/huggingface/stored_tokens", "cache/huggingface/token"):
            (repo / name).write_text("placeholder\n")
        git(repo, "init", "-q")
        git(repo, "add", "-f", ".")
        # stored_tokens is caught like the other credential-shaped basenames; the bare
        # `token` basename is deliberately not in SENSITIVE_BASENAME (too generic to flag
        # repo-wide, matching .gitignore's own choice), so it is not reported.
        self.assertEqual(cs.tracked_sensitive_names(repo),
                         ["cache/huggingface/stored_tokens", "leak.env", "service.key"])

    def test_repository_has_no_tracked_sensitive_names(self):
        self.assertEqual(cs.tracked_sensitive_names(ROOT), [])


class HuggingFaceNativeStoreTests(unittest.TestCase):
    """The two Hugging Face rows: lstat-only checks of hf's own token files in a fake home."""

    IDS = ("huggingface-native", "huggingface-native-stored")

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name) / "home"
        self.home.mkdir()
        self.hf_home = self.home / ".cache" / "huggingface"
        self.inventory = json.loads((ROOT / cs.INVENTORY).read_text())
        self.fake = "SENTINELHF" + os.urandom(12).hex()  # never shaped like a real token
        self.env = {"HOME": str(self.home)}
        self.proc_keys = Path(temporary.name) / "proc-keys"  # a fixture, never this host's /proc/keys
        self.proc_keys.write_text("")

    def sign_in(self, directory=None, mode=0o600, directory_mode=0o700):
        """What `hf auth login` leaves behind: both files 0600, their directory 0700."""
        directory = directory or self.hf_home
        directory.mkdir(parents=True, exist_ok=True)
        for name, text in (("token", self.fake), ("stored_tokens", f"[host]\nhf_token = {self.fake}\n")):
            (directory / name).write_text(text)
            (directory / name).chmod(mode)
        directory.chmod(directory_mode)
        return directory

    def report(self, env=None):
        return cs.inspect(ROOT, self.inventory, self.env if env is None else env)

    def entry(self, report, identifier="huggingface-native"):
        return next(e for e in report["entries"] if e["id"] == identifier)

    def run_cli(self, env=None, *args):
        cli_env = {"PATH": os.environ.get("PATH", ""), **(self.env if env is None else env)}
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(ROOT), "--proc-keys", str(self.proc_keys),
                                 *args], env=cli_env, capture_output=True, text=True, timeout=60)
        for text in (result.stdout, result.stderr):
            self.assertNotIn(self.fake, text)
            self.assertNotIn(str(self.home), text)
        return result

    def test_rows_are_native_stores_that_render_as_missing_before_sign_in(self):
        rows = {e["id"]: e for e in self.inventory["entries"] if e["id"] in self.IDS}
        self.assertEqual(set(rows), set(self.IDS))
        for row in rows.values():
            self.assertEqual((row["class"], row["status"], row["store"]["kind"]),
                             ("native_signin", "native", "native_store"))
            self.assertEqual(row["pointer_variables"], ["HF_TOKEN_PATH"])
            self.assertEqual(row["variables"], [])
        report = self.report()
        for identifier in self.IDS:
            self.assertEqual(self.entry(report, identifier)["state"], "missing")
        self.assertEqual(report["result"], "ok")
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("missing   huggingface-native          native", result.stdout)
        self.assertIn("missing   huggingface-native-stored   native", result.stdout)
        self.assertIn("${HF_HOME:-${XDG_CACHE_HOME:-$HOME/.cache}/huggingface}/token", result.stdout)

    def test_signed_in_store_is_ok_and_read_by_lstat_only(self):
        self.sign_in()
        opened = []
        real_open, real_os_open = builtins.open, os.open

        def watch_open(file, *args, **kwargs):
            opened.append(str(file))
            return real_open(file, *args, **kwargs)

        def watch_os_open(file, *args, **kwargs):
            opened.append(str(file))
            return real_os_open(file, *args, **kwargs)

        with patch("builtins.open", watch_open), patch("os.open", watch_os_open), \
                patch.object(Path, "read_text", side_effect=AssertionError("read_text called")), \
                patch.object(Path, "read_bytes", side_effect=AssertionError("read_bytes called")):
            report = self.report()
        self.assertFalse([p for p in opened if str(self.hf_home) in p])
        for identifier in self.IDS:
            entry = self.entry(report, identifier)
            self.assertEqual((entry["state"], entry["mode"], entry["directory_mode"]), ("ok", "0600", "0700"))
            self.assertEqual(entry["findings"], [])
        self.assertNotIn(self.fake, json.dumps(report) + cs.render_text(report))
        self.assertEqual(self.run_cli().returncode, 0)

    def test_group_or_world_readable_token_is_a_finding_and_fails(self):
        self.sign_in()
        (self.hf_home / "token").chmod(0o644)
        report = self.report()
        entry = self.entry(report)
        self.assertEqual(entry["state"], "unsafe")
        self.assertIn("group_or_other_access", entry["findings"])
        self.assertEqual(self.entry(report, "huggingface-native-stored")["state"], "ok")
        self.assertEqual(report["unsafe_stored"], ["huggingface-native"])
        self.assertEqual(report["unsafe_required"], [])
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("group_or_other_access", result.stdout)

    def test_template_follows_hf_home_then_xdg_cache_home_like_huggingface_hub(self):
        template = next(e for e in self.inventory["entries"]
                        if e["id"] == "huggingface-native")["store"]["path_template"]
        cache = self.home / "xdg-cache"
        custom = self.home / "hf-home"
        cases = (({}, self.hf_home), ({"XDG_CACHE_HOME": str(cache)}, cache / "huggingface"),
                 ({"XDG_CACHE_HOME": str(cache), "HF_HOME": str(custom)}, custom))
        for extra, directory in cases:
            with self.subTest(extra=extra):
                env = {**self.env, **extra}
                self.assertEqual(cs.expand_template(template, env), directory / "token")
        # Single-level templates expand exactly as before.
        self.assertEqual(cs.expand_template("${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack/x.env", self.env),
                         self.home / ".config" / "native-agent-stack" / "x.env")
        self.sign_in(cache / "huggingface")
        report = self.report({**self.env, "XDG_CACHE_HOME": str(cache)})
        self.assertEqual(self.entry(report)["state"], "ok")
        self.assertEqual(self.entry(self.report())["state"], "missing")

    def test_token_path_override_is_reported_by_name_only(self):
        elsewhere = self.home / "elsewhere"
        self.sign_in(elsewhere)
        env = {**self.env, "HF_TOKEN_PATH": str(elsewhere / "token"),
               # Our own stores are found through pointer variables on purpose; not an override.
               "PAPER_ENV_FILE": str(self.home / "paper.env")}
        report = self.report(env)
        self.assertEqual(report["environment"]["native_store_path_overrides_present"], ["HF_TOKEN_PATH"])
        for identifier in self.IDS:
            entry = self.entry(report, identifier)
            self.assertEqual(entry["state"], "missing")
            self.assertIn("store_path_overridden", entry["warnings"])
        self.assertNotIn("store_path_overridden", self.entry(report, "alpaca-paper")["warnings"])
        text = cs.render_text(report)
        self.assertIn("environment native store path overrides present: HF_TOKEN_PATH", text)
        self.assertNotIn(str(elsewhere), json.dumps(report) + text)
        self.assertEqual(self.report()["environment"]["native_store_path_overrides_present"], [])
        result = self.run_cli(env, "--json")
        self.assertEqual(json.loads(result.stdout)["environment"]["native_store_path_overrides_present"],
                         ["HF_TOKEN_PATH"])

    def test_token_variables_are_flagged_by_name_only(self):
        other = "SENTINELHF" + os.urandom(12).hex()
        env = {**self.env, "HUGGING_FACE_HUB_TOKEN": self.fake, "HF_TOKEN": other}
        report = self.report(env)
        self.assertEqual(report["environment"]["must_not_be_set_present"],
                         ["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"])
        self.assertNotIn(self.fake, json.dumps(report) + cs.render_text(report))
        self.assertNotIn(other, json.dumps(report) + cs.render_text(report))
        result = self.run_cli({**self.env, "HUGGING_FACE_HUB_TOKEN": self.fake})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("environment must_not_be_set present: HUGGING_FACE_HUB_TOKEN", result.stdout)


if __name__ == "__main__":
    unittest.main()
