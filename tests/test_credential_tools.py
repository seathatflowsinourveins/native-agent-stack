"""Tests for tools/credentials: hidden-prompt storage, the read-only rate-limit probe and
the terminal launcher. Every value is a random fake generated per test."""
from __future__ import annotations

import email.message
import http.client
import http.server
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "credentials"
sys.path.insert(0, str(TOOLS))
import alpaca_rate_limit_probe as probe_mod  # noqa: E402
import set_credential as store_mod  # noqa: E402


def fake_token(prefix: str = "") -> str:
    return prefix + os.urandom(12).hex()


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.env = {"HOME": str(base / "home"), "XDG_CONFIG_HOME": str(base / "cfg")}
        self.store = base / "cfg" / "native-agent-stack"

    def tearDown(self):
        self.tmp.cleanup()

    def run_store(self, entry, answers):
        answers = iter(answers)
        out = io.StringIO()
        code = store_mod.run(entry, env=self.env, prompt=lambda _p: next(answers), out=out)
        return code, out.getvalue()

    def test_stores_values_atomically_with_private_modes(self):
        key_value, other_value = fake_token("PK"), fake_token()
        code, output = self.run_store("alpaca-paper", [key_value, other_value, ""])
        self.assertEqual(code, 0)
        path = self.store / "alpaca-paper.env"
        self.assertEqual(stat.S_IMODE(os.lstat(path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.lstat(self.store).st_mode), 0o700)
        self.assertEqual(path.read_text(),
                         f"export APCA_API_KEY_ID={key_value}\nexport APCA_API_SECRET_KEY={other_value}\n")
        self.assertEqual(probe_mod.read_env_file(path), (key_value, other_value))  # round-trips
        self.assertIn("APCA_API_KEY_ID", output)
        for value in (key_value, other_value):
            self.assertNotIn(value, output)
        self.assertNotIn("warning", output)
        self.assertEqual([p.name for p in self.store.iterdir()], ["alpaca-paper.env"])  # no temp left

    def test_prefix_mismatch_warns_without_echoing(self):
        key_value = fake_token("AK")
        code, output = self.run_store("alpaca-paper", [key_value, fake_token(), ""])
        self.assertEqual(code, 0)
        self.assertIn("does not start with PK", output)
        self.assertNotIn(key_value, output)

    def test_second_paper_account_gets_the_same_prefix_hint(self):
        # alpaca-paper-2 is a paper account too, so a live-shaped key id (AK) is flagged the same way.
        key_value = fake_token("AK")
        code, output = self.run_store("alpaca-paper-2", [key_value, fake_token(), ""])
        self.assertEqual(code, 0)
        self.assertIn("does not start with PK", output)
        self.assertNotIn(key_value, output)
        self.assertTrue((self.store / "alpaca-paper-2.env").is_file())
        code, output = self.run_store("alpaca-paper-2", ["replace", fake_token("PK"), fake_token(), ""])
        self.assertEqual(code, 0)
        self.assertNotIn("warning", output)

    def test_replacing_needs_the_hidden_word_replace(self):
        self.run_store("alpaca-paper", [fake_token("PK"), fake_token(), ""])
        path = self.store / "alpaca-paper.env"
        before = path.read_text()
        code, _ = self.run_store("alpaca-paper", ["y"])
        self.assertEqual(code, 1)
        self.assertEqual(path.read_text(), before)
        code, _ = self.run_store("alpaca-paper", ["replace", fake_token("PK"), fake_token(), ""])
        self.assertEqual(code, 0)
        self.assertNotEqual(path.read_text(), before)

    def test_refuses_store_inside_git_worktree(self):
        repo = Path(self.tmp.name) / "repo"
        (repo / ".git").mkdir(parents=True)
        self.env["XDG_CONFIG_HOME"] = str(repo / "cfg")
        with self.assertRaises(store_mod.Refused):
            self.run_store("alpaca-paper", [fake_token("PK"), fake_token(), ""])

    def test_refuses_symlinked_store(self):
        target = Path(self.tmp.name) / "elsewhere"
        target.mkdir()
        self.store.parent.mkdir(parents=True)
        self.store.symlink_to(target)
        with self.assertRaises(store_mod.Refused):
            self.run_store("alpaca-paper", [fake_token("PK"), fake_token(), ""])
        self.assertEqual(list(target.iterdir()), [])

    def test_only_operator_supplied_stored_entries(self):
        # The IBKR paper gateway's three files (2026-10-06) are private_file stores in docker's formats; the writer's
        # `export NAME=value` lines would break them, so it refuses all three.
        for entry in ("alpaca-live", "grafana-admin", "claude-native", "no-such-entry",
                      "ibkr-gateway", "ibkr-gateway-tws-password", "ibkr-gateway-vnc-password"):
            with self.subTest(entry=entry), self.assertRaises(store_mod.Refused):
                store_mod.load_entry(entry, env=self.env)
        self.assertEqual(store_mod.load_entry("typesafe", env=self.env)["id"], "typesafe")
        # tavily lived in the kernel keyring only from 2026-09-26 and moved to its own file on 2026-09-29
        # (docs/decisions/2026-09-29-key-management.md). A kernel keyring row is still never written to a file.
        self.assertEqual(store_mod.load_entry("tavily", env=self.env)["store"]["kind"], "private_env_file")
        inventory = json.loads((ROOT / "adoption/credential-inventory.json").read_text(encoding="utf-8"))
        row = next(e for e in inventory["entries"] if e["id"] == "tavily")
        row["store"] = {"kind": "kernel_keyring", "path_template": "", "key_name": "tavily_api_key"}
        planted = Path(self.tmp.name) / "planted-inventory.json"
        planted.write_text(json.dumps(inventory), encoding="utf-8")
        with mock.patch.object(store_mod.cs, "INVENTORY", str(planted)), \
                self.assertRaisesRegex(store_mod.Refused, "not an operator-supplied stored entry"):
            store_mod.load_entry("tavily", env=self.env)

    def test_value_encoding(self):
        self.assertEqual(store_mod.encode("A", "abc-123"), "export A=abc-123\n")
        self.assertEqual(store_mod.encode("A", "project name a@b.example"),
                         'export A="project name a@b.example"\n')
        # `~` never goes out bare (a sourcing shell would expand it); quoted, bash leaves it alone.
        self.assertEqual(store_mod.encode("A", "tilde~home"), 'export A="tilde~home"\n')
        for bad in ("", " padded", "has\nnewline", "has\ttab", 'has"quote', "has$dollar", "has`tick",
                    "back\\slash", "café bar", "nul\x00"):
            with self.subTest(bad=bad), self.assertRaises(store_mod.Refused):
                store_mod.encode("A", bad)

    def test_cli_refuses_without_a_terminal(self):
        result = subprocess.run([sys.executable, str(TOOLS / "set_credential.py"), "alpaca-paper"],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30,
                                env={"PATH": os.environ.get("PATH", ""), **self.env})
        self.assertEqual(result.returncode, 2)
        self.assertIn("interactive terminal", result.stderr)
        self.assertFalse(self.store.exists())


class StoreFromEnvTests(unittest.TestCase):
    """--from-env: an entry's one variable, from this process's environment, into a new 0600 file. It exists for a
    key that already lives only in memory, which `kernel_keyring.py exec` hands over (docs/secret-storage.md).
    Every value is a synthetic fake and the store is a temporary XDG_CONFIG_HOME."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.store = self.base / "cfg" / "native-agent-stack"
        self.value = fake_token("tvly-") + fake_token()
        self.env = {"HOME": str(self.base / "home"), "XDG_CONFIG_HOME": str(self.base / "cfg"),
                    "TAVILY_API_KEY": self.value}

    def store_from_env(self, entry="tavily", env=None):
        out = io.StringIO()
        code = store_mod.run_from_env(entry, env=self.env if env is None else env, out=out, isolated_start=True)
        return code, out.getvalue()

    def cli(self, *args, flags=("-I", "-S"), python=sys.executable, **extra_env):
        env = {"PATH": os.environ.get("PATH", ""), **self.env, **extra_env}
        command = [str(python), *flags, str(TOOLS / "set_credential.py"), *args]
        return subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60, env=env)

    def assert_never_echoed(self, *texts, value=None):
        # Neither the value nor any six-character piece of it (`tvly auth`, for one, prints a key's first eight
        # and last four characters).
        value = self.value if value is None else value
        pieces = {value[i:i + 6] for i in range(len(value) - 5)}
        for text in texts:
            self.assertNotIn(value, text)
            self.assertEqual(sorted(piece for piece in pieces if piece in text), [])

    def test_stores_the_one_variable_in_a_new_private_file(self):
        with mock.patch.object(store_mod.os, "replace", side_effect=AssertionError("os.replace overwrites")):
            code, output = self.store_from_env()
        self.assertEqual((code, output), (0, "tavily: stored\n"))
        path = self.store / "tavily.env"
        self.assertEqual(path.read_text(encoding="ascii"), f"export TAVILY_API_KEY={self.value}\n")
        info = os.lstat(path)
        self.assertEqual((stat.S_IMODE(info.st_mode), info.st_nlink), (0o600, 1))  # the temporary name is gone
        self.assertEqual(stat.S_IMODE(os.lstat(self.store).st_mode), 0o700)
        self.assertEqual([p.name for p in self.store.iterdir()], ["tavily.env"])
        self.assertNotIn("TAVILY_API_KEY", self.env)  # popped, so no child of the writer inherits it
        self.assert_never_echoed(output)

    def test_refuses_unless_the_interpreter_started_with_minus_I_and_minus_S(self):
        with self.assertRaisesRegex(store_mod.Refused, r"python3 -I -S") as caught:
            store_mod.run_from_env("tavily", env=self.env, out=io.StringIO(), isolated_start=False)
        self.assert_never_echoed(str(caught.exception))
        if not (sys.flags.isolated and sys.flags.no_site):  # the default reads both flags; this process has neither
            with self.assertRaisesRegex(store_mod.Refused, r"python3 -I -S"):
                store_mod.run_from_env("tavily", env=self.env, out=io.StringIO())
        self.assertFalse(self.store.exists())
        self.assertEqual(self.env["TAVILY_API_KEY"], self.value)  # refused before the value was taken

    def test_refuses_an_entry_without_exactly_one_variable(self):
        # A pair's provenance cannot be proven from an inherited environment, so pairs never take this path; an
        # optional variable counts too (sec-contact declares SEC_USER_AGENT and EDGAR_IDENTITY).
        self.env.update({"APCA_API_KEY_ID": fake_token("PK"), "APCA_API_SECRET_KEY": fake_token(),
                         "SEC_USER_AGENT": "name a@b.example"})
        for entry in ("alpaca-paper", "alpaca-paper-2", "sec-contact"):
            with self.subTest(entry=entry), self.assertRaisesRegex(store_mod.Refused, "exactly one variable"):
                self.store_from_env(entry)
        self.assertFalse(self.store.exists())
        # Entries that are not operator-supplied files keep the interactive path's refusal.
        for entry in ("grafana-admin", "claude-native", "no-such-entry"):
            with self.subTest(entry=entry), self.assertRaises(store_mod.Refused):
                self.store_from_env(entry)
        self.assertFalse(self.store.exists())

    def test_refuses_an_absent_empty_or_out_of_grammar_value(self):
        cases = {"absent": None, "empty": "", "padded": f" {self.value}", "newline": f"{self.value}\nx",
                 "quote": f'{self.value}"', "dollar": f"{self.value}$HOME", "backtick": f"{self.value}`id`",
                 "backslash": f"{self.value}\\", "non-ASCII": f"{self.value}\u00e9"}
        for label, value in cases.items():
            env = {name: text for name, text in self.env.items() if name != "TAVILY_API_KEY"}
            if value is not None:
                env["TAVILY_API_KEY"] = value
            with self.subTest(label), self.assertRaises(store_mod.Refused) as caught:
                self.store_from_env(env=env)
            self.assert_never_echoed(str(caught.exception))
            self.assertIn("TAVILY_API_KEY", str(caught.exception))  # the refusal names the variable only
        self.assertFalse(self.store.exists())  # refused before the store was even created

    def test_never_replaces_an_existing_file_and_writes_nothing_first(self):
        # A loose store directory would be tightened to 0700 on the way to a write; a refusal comes before any write,
        # so it stays as it was.
        self.store.mkdir(parents=True)
        self.store.chmod(0o750)
        path = self.store / "tavily.env"
        path.write_text("export TAVILY_API_KEY=kept\n")
        path.chmod(0o600)
        with self.assertRaisesRegex(store_mod.Refused, "exists") as caught:
            self.store_from_env()
        self.assert_never_echoed(str(caught.exception))
        self.assertEqual(path.read_text(), "export TAVILY_API_KEY=kept\n")
        self.assertEqual([p.name for p in self.store.iterdir()], ["tavily.env"])
        self.assertEqual(stat.S_IMODE(os.lstat(self.store).st_mode), 0o750)
        # A symbolic link at the name is refused the same way, and neither it nor its target changes.
        path.unlink()
        target = self.base / "elsewhere.env"
        target.write_text("untouched\n")
        path.symlink_to(target)
        self.env["TAVILY_API_KEY"] = self.value
        with self.assertRaisesRegex(store_mod.Refused, "exists"):
            self.store_from_env()
        self.assertTrue(path.is_symlink())
        self.assertEqual(target.read_text(), "untouched\n")
        self.assertEqual([p.name for p in self.store.iterdir()], ["tavily.env"])
        self.assertEqual(stat.S_IMODE(os.lstat(self.store).st_mode), 0o750)

    def test_a_leftover_temporary_file_is_a_listed_dot_file_and_never_the_stored_file(self):
        # A kill between writing the temporary file and linking it leaves that file behind. It is a dot-file named
        # after the final file: the checker lists it as undeclared and never counts it as the stored key, and the
        # writer never takes it for the final file.
        linked, real_link = [], os.link

        def watching_link(src, dst, **kwargs):
            linked.append((src, dst))
            return real_link(src, dst, **kwargs)

        with mock.patch.object(store_mod.os, "link", watching_link):
            self.assertEqual(self.store_from_env(), (0, "tavily: stored\n"))
        [(temporary, final)] = linked
        self.assertEqual(final, "tavily.env")
        self.assertRegex(temporary, r"^\.tavily\.env\.[0-9a-f]{16}\.tmp$")
        # The state that a kill before the link leaves: the value under the temporary name, no final name.
        (self.store / "tavily.env").rename(self.store / temporary)
        cs = store_mod.cs
        inventory = json.loads((ROOT / cs.INVENTORY).read_text(encoding="utf-8"))

        def tavily_state_and_undeclared():
            report = cs.inspect(ROOT, inventory, self.env)
            row = next(e for e in report["entries"] if e["id"] == "tavily")
            return row["state"], report["coverage"]["undeclared_store_files"], report["warnings"]

        self.assertEqual(tavily_state_and_undeclared(), ("missing", [temporary], ["undeclared_store_file"]))
        self.env["TAVILY_API_KEY"] = self.value
        self.assertEqual(self.store_from_env(), (0, "tavily: stored\n"))
        self.assertEqual(sorted(p.name for p in self.store.iterdir()), sorted([temporary, "tavily.env"]))
        self.assertEqual(tavily_state_and_undeclared(), ("ok", [temporary], ["undeclared_store_file"]))

    def test_the_final_link_is_create_only(self):
        # The existence check before writing can race with another writer; os.link cannot: it fails with EEXIST
        # rather than replace, so a file that appears after the check is kept and the temporary name is removed.
        dfd = store_mod.open_store(self.store, os.getuid())
        self.addCleanup(os.close, dfd)
        path = self.store / "tavily.env"
        path.write_text("appeared after the check\n")
        with self.assertRaisesRegex(store_mod.Refused, "exists") as caught:
            store_mod.create_exclusively(dfd, "tavily.env", f"export TAVILY_API_KEY={self.value}\n")
        self.assert_never_echoed(str(caught.exception))
        self.assertEqual(path.read_text(), "appeared after the check\n")
        self.assertEqual([p.name for p in self.store.iterdir()], ["tavily.env"])

    def test_cli_stores_once_without_a_terminal_and_prints_only_the_id(self):
        first = self.cli("tavily", "--from-env")
        self.assertEqual((first.returncode, first.stdout, first.stderr), (0, "tavily: stored\n", ""))
        path = self.store / "tavily.env"
        self.assertEqual(path.read_text(), f"export TAVILY_API_KEY={self.value}\n")
        self.assertEqual(stat.S_IMODE(os.lstat(path).st_mode), 0o600)
        other = fake_token("tvly-") + fake_token()
        second = self.cli("tavily", "--from-env", TAVILY_API_KEY=other)
        self.assertEqual(second.returncode, 2)
        self.assertIn("exists", second.stderr)
        self.assertEqual(path.read_text(), f"export TAVILY_API_KEY={self.value}\n")
        for result in (first, second):
            self.assert_never_echoed(result.stdout + result.stderr)
            self.assert_never_echoed(result.stdout + result.stderr, value=other)
            self.assertNotIn("Traceback", result.stderr)

    def test_cli_refuses_a_non_isolated_start(self):
        # Without -I, site-time code has already run beside the value: a sitecustomize module on PYTHONPATH records
        # that it saw TAVILY_API_KEY (the control). Re-running isolated could not undo that, so the tool refuses and
        # writes nothing; with -I -S the module never runs. The next test but one shows that it never re-executes.
        poison, marker = self.base / "poison", self.base / "site-ran"
        poison.mkdir()
        (poison / "sitecustomize.py").write_text(
            f"import os\nwith open({str(marker)!r}, 'a') as h:\n    h.write(str('TAVILY_API_KEY' in os.environ))\n")
        plain = self.cli("tavily", "--from-env", flags=(), PYTHONPATH=str(poison))
        self.assertEqual(plain.returncode, 2, plain.stderr)
        self.assertIn("python3 -I -S", plain.stderr)
        self.assertEqual(marker.read_text(), "True")
        self.assertFalse(self.store.exists())
        isolated = self.cli("tavily", "--from-env", PYTHONPATH=str(poison))
        self.assertEqual((isolated.returncode, isolated.stdout), (0, "tavily: stored\n"), isolated.stderr)
        self.assertEqual(marker.read_text(), "True")  # unchanged: -I ignored PYTHONPATH and -S skipped site
        for result in (plain, isolated):
            self.assert_never_echoed(result.stdout + result.stderr)

    def test_cli_refuses_minus_I_without_minus_S(self):
        # -I ignores PYTHONPATH and the user site directory but still imports site, which runs the .pth lines of the
        # interpreter's own site-packages (the control is the next test), so only -I -S is accepted.
        result = self.cli("tavily", "--from-env", flags=("-I",))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("python3 -I -S", result.stderr)
        self.assertFalse(self.store.exists())
        self.assert_never_echoed(result.stdout + result.stderr)

    def test_site_code_runs_under_minus_I_alone_and_a_refused_start_never_reexecutes(self):
        # The control for the rule above, in a throwaway venv whose site-packages this test may write: a .pth line
        # there records every interpreter start as "<isolated><saw TAVILY_API_KEY>". It runs beside the value in a
        # plain start and under -I, so both are refused; the plain start leaves no isolated record, so nothing was
        # re-executed; under -I -S the line never runs and the file is stored.
        venv = self.base / "venv"
        made = subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)],
                              capture_output=True, text=True, timeout=120)
        if made.returncode != 0:
            self.skipTest("python3 -m venv is not available")
        python = venv / "bin" / "python"
        purelib = subprocess.run([str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
                                 capture_output=True, text=True, timeout=60, check=True).stdout.strip()
        record = self.base / "starts"
        Path(purelib, "zz_control.pth").write_text(
            f"import os, sys; open({str(record)!r}, 'a').write('%d%d;' % "
            "(sys.flags.isolated, 'TAVILY_API_KEY' in os.environ))\n")

        def starts():
            text = record.read_text() if record.exists() else ""
            record.unlink(missing_ok=True)
            return {start for start in text.split(";") if start}

        plain = self.cli("tavily", "--from-env", flags=(), python=python)
        self.assertEqual(plain.returncode, 2, plain.stderr)
        self.assertEqual(starts(), {"01"})  # one kind of start: not isolated, value present; no isolated re-run
        minus_i = self.cli("tavily", "--from-env", flags=("-I",), python=python)
        self.assertEqual(minus_i.returncode, 2, minus_i.stderr)
        self.assertEqual(starts(), {"11"})  # the control: site code ran beside the value under -I too
        self.assertFalse(self.store.exists())
        stored = self.cli("tavily", "--from-env", python=python)
        self.assertEqual((stored.returncode, stored.stdout), (0, "tavily: stored\n"), stored.stderr)
        self.assertEqual(starts(), set())  # under -I -S the .pth line never ran
        for result in (plain, minus_i, stored):
            self.assert_never_echoed(result.stdout + result.stderr)

    def test_cli_takes_no_abbreviation_of_from_env(self):
        # argparse would read --from as --from-env, which the start-up check does not look for.
        for flags in (("-I", "-S"), ()):
            with self.subTest(flags=flags):
                result = self.cli("tavily", "--from", flags=flags)
                self.assertEqual(result.returncode, 2)
                self.assertFalse(self.store.exists())
                self.assert_never_echoed(result.stdout + result.stderr)


class _Response:
    def __init__(self, status, headers):
        self.status, self.headers = status, headers

    def close(self):
        pass

    def read(self):  # pragma: no cover - the probe must never read the body
        raise AssertionError("body read")


def headers(**values):
    message = email.message.Message()
    for name, value in values.items():
        message[name.replace("_", "-")] = value
    return message


class ProbeFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "store"
        self.dir.mkdir(mode=0o700)
        os.chmod(self.dir, 0o700)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text, mode=0o600, name="paper.env", directory=None):
        path = (directory or self.dir) / name
        path.write_text(text)
        os.chmod(path, mode)
        return path

    def pair(self):
        return fake_token("PK"), fake_token()

    def test_reads_the_two_values(self):
        val_a, val_b = self.pair()
        path = self.write(f'# comment\nexport APCA_API_KEY_ID={val_a}\nAPCA_API_SECRET_KEY="{val_b}"\n')
        self.assertEqual(probe_mod.read_env_file(path), (val_a, val_b))

    def test_refuses_unsafe_files(self):
        val_a, val_b = self.pair()
        body = f"APCA_API_KEY_ID={val_a}\nAPCA_API_SECRET_KEY={val_b}\n"
        cases = {"0644": self.write(body, mode=0o644, name="a.env"),
                 "0400": self.write(body, mode=0o400, name="b.env"),
                 "half": self.write(f"APCA_API_KEY_ID={val_a}\n", name="c.env"),
                 "not a token": self.write(f"APCA_API_KEY_ID=has space\nAPCA_API_SECRET_KEY={val_b}\n",
                                           name="d.env"),
                 "absent": self.dir / "absent.env"}
        link = self.dir / "link.env"
        link.symlink_to(self.write(body, name="real.env"))
        cases["symlink"] = link
        hard = self.write(body, name="hard.env")
        os.link(hard, self.dir / "hard-2.env")
        cases["two links"] = hard
        for label, path in cases.items():
            with self.subTest(label), self.assertRaises(probe_mod.Refused):
                probe_mod.read_env_file(path)

    def test_refuses_loose_or_repository_directories(self):
        val_a, val_b = self.pair()
        loose = Path(self.tmp.name) / "loose"
        loose.mkdir()
        os.chmod(loose, 0o755)
        with self.assertRaises(probe_mod.Refused):
            probe_mod.read_env_file(self.write(f"APCA_API_KEY_ID={val_a}\nAPCA_API_SECRET_KEY={val_b}\n",
                                               directory=loose))
        repo = Path(self.tmp.name) / "repo"
        (repo / ".git").mkdir(parents=True)
        inside = repo / "cfg"
        inside.mkdir(mode=0o700)
        os.chmod(inside, 0o700)
        with self.assertRaises(probe_mod.Refused):
            probe_mod.read_env_file(self.write(f"APCA_API_KEY_ID={val_a}\nAPCA_API_SECRET_KEY={val_b}\n",
                                               directory=inside))


class ProbeRequestTests(unittest.TestCase):
    def test_sends_one_get_and_keeps_only_rate_limit_headers(self):
        seen = []

        class Opener:
            def open(self, request, timeout):
                seen.append(request)
                return _Response(200, headers(x_ratelimit_limit="1000", x_ratelimit_remaining="999",
                                              x_ratelimit_reset="1790260000", x_request_id="rid"))

        val_a, val_b = fake_token("PK"), fake_token()
        result = probe_mod.probe(val_a, val_b, opener=Opener())
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].get_method(), "GET")
        self.assertEqual(seen[0].full_url, "https://paper-api.alpaca.markets/v2/account")
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(sorted(result["rate_limit_headers"]),
                         ["x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset"])
        self.assertEqual(result["interpretation"], "1000 calls/min")
        rendered = json.dumps(result)
        for value in (val_a, val_b):
            self.assertNotIn(value, rendered)

    def test_http_error_still_reports_headers(self):
        class Opener:
            def open(self, request, timeout):
                raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized",
                                             headers(x_ratelimit_limit="200"), None)

        result = probe_mod.probe("a", "b", opener=Opener())
        self.assertEqual(result["http_status"], 401)
        self.assertEqual(result["rate_limit_headers"], {"x-ratelimit-limit": "200"})
        self.assertIn("HTTP 401", result["interpretation"])

    def test_failures_report_only_the_error_type(self):
        for error in (urllib.error.URLError("down"), http.client.BadStatusLine("junk"), ValueError("x")):
            class Opener:
                def open(self, request, timeout, _error=error):
                    raise _error

            with self.subTest(error=type(error).__name__):
                result = probe_mod.probe("a", "b", opener=Opener())
                self.assertIsNone(result["http_status"])
                self.assertEqual(result["error"], type(error).__name__)

    def test_redirects_are_never_followed_end_to_end(self):
        hits = {"origin": 0, "target": 0}

        def handler(name, redirect_to=None):
            class Handler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    hits[name] += 1
                    if redirect_to:
                        self.send_response(302)
                        self.send_header("Location", redirect_to())
                    else:
                        self.send_response(200)
                    self.end_headers()

                def log_message(self, *args):
                    pass
            return Handler

        target = http.server.HTTPServer(("127.0.0.1", 0), handler("target"))
        origin = http.server.HTTPServer(("127.0.0.1", 0), handler(
            "origin", lambda: f"http://127.0.0.1:{target.server_address[1]}/stolen"))
        servers = [target, origin]
        for server in servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            opener = urllib.request.build_opener(probe_mod._NoRedirect())
            request = urllib.request.Request(f"http://127.0.0.1:{origin.server_address[1]}/v2/account",
                                             headers={"APCA-API-KEY-ID": "k", "APCA-API-SECRET-KEY": "s"})
            with self.assertRaises(urllib.error.HTTPError) as caught:
                opener.open(request, timeout=5)
            self.assertEqual(caught.exception.code, 302)
            caught.exception.close()
            self.assertEqual(hits, {"origin": 1, "target": 0})
        finally:
            for server in servers:
                server.shutdown()
                server.server_close()

    def test_only_the_fixed_paper_host(self):
        self.assertEqual(probe_mod.HOST, "https://paper-api.alpaca.markets")


class ProbeCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "store"
        self.dir.mkdir(mode=0o700)
        os.chmod(self.dir, 0o700)

    def tearDown(self):
        self.tmp.cleanup()

    def test_there_is_no_live_option(self):
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr), self.assertRaises(SystemExit) as caught:
            probe_mod.main(["--account", "live"])
        self.assertEqual(caught.exception.code, 2)

    def test_paper_file_writes_private_result_without_following_symlinks(self):
        val_a, val_b = fake_token("PK"), fake_token()
        path = self.dir / "paper.env"
        path.write_text(f"export APCA_API_KEY_ID={val_a}\nexport APCA_API_SECRET_KEY={val_b}\n")
        os.chmod(path, 0o600)
        results = Path(self.tmp.name) / "results"
        results.mkdir()
        victim = Path(self.tmp.name) / "victim.txt"
        victim.write_text("untouched")
        out = results / "paper.json"
        out.symlink_to(victim)

        class Opener:
            def open(self, request, timeout):
                return _Response(200, headers(x_ratelimit_limit="200"))

        stdout = io.StringIO()
        with mock.patch.object(probe_mod.urllib.request, "build_opener", return_value=Opener()), \
                mock.patch("sys.stdout", stdout):
            code = probe_mod.main(["--env-file", str(path), "--out", str(out)])
        self.assertEqual(code, 0)
        self.assertEqual(victim.read_text(), "untouched")
        self.assertFalse(out.is_symlink())
        self.assertEqual(stat.S_IMODE(os.lstat(out).st_mode), 0o600)
        for text in (stdout.getvalue(), out.read_text()):
            self.assertNotIn(val_a, text)
            self.assertNotIn(val_b, text)
        self.assertEqual(json.loads(out.read_text())["interpretation"], "200 calls/min: standard tier")


class IsolationTests(unittest.TestCase):
    def test_direct_runs_ignore_a_poisoned_pythonpath(self):
        with tempfile.TemporaryDirectory() as tmp:
            poison, marker = Path(tmp) / "poison", Path(tmp) / "imported"
            poison.mkdir()
            for module in ("getpass", "argparse"):
                (poison / f"{module}.py").write_text(f"open({str(marker)!r}, 'a').write({module!r})\n")
            env = {"PATH": os.environ.get("PATH", ""), "HOME": tmp, "XDG_CONFIG_HOME": str(Path(tmp) / "cfg"),
                   "PYTHONPATH": str(poison)}
            for args in ([str(TOOLS / "set_credential.py"), "alpaca-paper"],
                         [str(TOOLS / "alpaca_rate_limit_probe.py"), "--env-file", str(Path(tmp) / "none.env")]):
                with self.subTest(tool=Path(args[0]).name):
                    result = subprocess.run([sys.executable, *args], stdin=subprocess.DEVNULL, env=env,
                                            capture_output=True, text=True, timeout=60)
                    self.assertEqual(result.returncode, 2, result.stderr)
            self.assertFalse(marker.exists(), "a PYTHONPATH module was imported")


class LauncherTests(unittest.TestCase):
    def run_launcher(self, *args, state):
        env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "/tmp"),
               "XDG_STATE_HOME": str(state)}
        if os.environ.get("WSL_DISTRO_NAME"):  # exercise the WSL launcher branch on WSL hosts
            env["WSL_DISTRO_NAME"] = os.environ["WSL_DISTRO_NAME"]
        return subprocess.run(["bash", str(TOOLS / "open_credential_terminal.sh"), *args],
                              capture_output=True, text=True, timeout=60, env=env)

    def test_store_mode_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_launcher("alpaca-paper", "--probe", "--dry-run", state=Path(tmp))
            self.assertEqual(result.returncode, 0, result.stderr)
            out = result.stdout
            self.assertIn("python3 -I tools/credentials/set_credential.py alpaca-paper", out)
            self.assertIn("alpaca_rate_limit_probe.py --out", out)
            self.assertIn("git status --porcelain -- tools/credentials", out)
            self.assertIn("unset PYTHONPATH", out)
            sessions = Path(tmp) / "native-agent-stack" / "credential-sessions"
            self.assertEqual(stat.S_IMODE(os.lstat(sessions).st_mode), 0o700)
            self.assertEqual(list(sessions.iterdir()), [])

    def test_rejects_bad_arguments_and_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            for args in (("../etc",), ("typesafe", "--probe"), ("--live-rate-limit",),
                         ("alpaca-paper", "--bogus"), ("alpaca-paper", "typesafe"), ()):
                with self.subTest(args=args):
                    self.assertEqual(self.run_launcher(*args, state=Path(tmp)).returncode, 2)
            unsafe = Path(tmp) / "has space"
            unsafe.mkdir()
            result = self.run_launcher("typesafe", "--dry-run", state=unsafe)
            self.assertEqual(result.returncode, 2)
            self.assertIn("cannot pass safely", result.stderr)


if __name__ == "__main__":
    unittest.main()
