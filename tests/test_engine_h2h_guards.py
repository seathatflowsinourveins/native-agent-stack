"""Local unit tests for the head-to-head runners' paper-only refusals (no engine, no network).

Each runner must refuse unless given exactly its own dedicated paper env file, must
refuse the other lanes' paper accounts and the other engines' files, and must refuse a
non-paper host. Every refusal here happens before any engine import or broker request.
Fixture values are the same inert stand-ins the adaptive-paper credential tests use.
"""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from tests.adaptive_paper_hermetic import real_tmp_root

ROOT = Path(__file__).resolve().parents[1]
H2H = ROOT / "blueprints" / "us-equities" / "engine-h2h"
PAPER = "https://paper-api.alpaca.markets"
LIVE = "https://api.alpaca.markets"
ENV_BODY = "APCA_API_KEY_ID=fixture-key-id\nAPCA_API_SECRET_KEY=fixture-secret-key\n"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


common = load("h2h_common_guard_test", H2H / "h2h_common.py")


class EnvFileNames(unittest.TestCase):
    def test_only_the_dedicated_name_passes(self):
        for engine in common.ENGINES:
            common.check_env_file(engine, Path("/store") / f"alpaca-paper-h2h-{engine}.env")
        refused = {
            None: "h2h:env_file_required",
            "alpaca-paper.env": "h2h:forbidden_shared_paper_account",
            "alpaca-paper-1.env": "h2h:forbidden_shared_paper_account",
            "alpaca-paper-2.env": "h2h:forbidden_shared_paper_account",
            "alpaca-paper-3.env": "h2h:forbidden_shared_paper_account",
            "alpaca-paper-4.env": "h2h:forbidden_shared_paper_account",
            "paper-3.env": "h2h:forbidden_shared_paper_account",
            "alpaca-paper-h2h-lean.env": "h2h:another_engines_paper_account",
            "alpaca-paper-h2h-lumibot.env": "h2h:another_engines_paper_account",
            "alpaca-paper-h2h-nautilus.env.bak": "h2h:not_the_dedicated_env_file",
            "live.env": "h2h:not_the_dedicated_env_file",
        }
        for name, reason in refused.items():
            with self.subTest(name=name):
                with self.assertRaises(common.H2HRefusal) as caught:
                    common.check_env_file("nautilus", None if name is None else Path("/store") / name)
                self.assertEqual(str(caught.exception), reason)

    def test_unknown_engine(self):
        with self.assertRaisesRegex(common.H2HRefusal, "h2h:unknown_engine"):
            common.env_file_name("backtrader")


class EnvFileLoading(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = real_tmp_root(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, engine, *lines, mode=0o600, name=None):
        path = self.root / (name or common.env_file_name(engine))
        path.write_text(ENV_BODY + "".join(line + "\n" for line in lines))
        os.chmod(path, mode)
        return path

    def test_valid_file_is_pinned_to_paper(self):
        for lines in ((), (f"APCA_API_BASE_URL={PAPER}",), (f"export APCA_API_BASE_URL='{PAPER}/'",)):
            with self.subTest(lines=lines):
                values = common.load_paper_env("lean", self.write("lean", *lines), environ={})
                self.assertEqual(values, {"key_id": "fixture-key-id", "secret": "fixture-secret-key",
                                          "base_url": PAPER})

    def test_non_paper_hosts_are_refused(self):
        for line in (f"APCA_API_BASE_URL={LIVE}", "APCA_API_BASE_URL=https://example.invalid"):
            with self.subTest(line=line):
                with self.assertRaisesRegex(common.H2HRefusal, "^h2h:not_paper_host$"):
                    common.load_paper_env("lumibot", self.write("lumibot", line), environ={})
        with self.assertRaisesRegex(common.H2HRefusal, "^h2h:not_paper_host$"):
            common.load_paper_env("lumibot", self.write("lumibot"), environ={"APCA_API_BASE_URL": LIVE})

    def test_file_guard_refusals(self):
        with self.assertRaisesRegex(common.H2HRefusal, "credential_file_permissions:mode"):
            common.load_paper_env("nautilus", self.write("nautilus", mode=0o644), environ={})
        target = self.write("nautilus", name="elsewhere.env")
        link = self.root / common.env_file_name("nautilus")
        link.unlink()
        link.symlink_to(target)
        with self.assertRaisesRegex(common.H2HRefusal, "credential_file_permissions:symlink"):
            common.load_paper_env("nautilus", link, environ={})

    def test_missing_secret_is_refused(self):
        path = self.root / common.env_file_name("lean")
        path.write_text("APCA_API_KEY_ID=fixture-key-id\n")
        os.chmod(path, 0o600)
        with self.assertRaisesRegex(common.H2HRefusal, "^h2h:missing_paper_credentials$"):
            common.load_paper_env("lean", path, environ={})

    def test_refusals_never_carry_values(self):
        with self.assertRaises(common.H2HRefusal) as caught:
            common.load_paper_env("lumibot", self.write("lumibot", f"APCA_API_BASE_URL={LIVE}"), environ={})
        self.assertNotIn("fixture", str(caught.exception))
        self.assertNotIn(str(self.root), str(caught.exception))


class Accounts(unittest.TestCase):
    def test_distinct_accounts(self):
        fp = {e: common.account_fingerprint(i) for i, e in enumerate(common.ENGINES)}
        common.assert_distinct_accounts(fp)
        with self.assertRaisesRegex(common.H2HRefusal, "paper_account_shared_between_engines"):
            common.assert_distinct_accounts({"nautilus": "x", "lean": "x"})
        with self.assertRaisesRegex(common.H2HRefusal, "forbidden_shared_paper_account"):
            common.assert_distinct_accounts(fp, forbidden={fp["lean"]})

    def test_scrubbed_environment(self):
        scrubbed = common.scrubbed_environment({"APCA_API_KEY_ID": "x", "ALPACA_SECRET_KEY": "y",
                                                "LUMIWEALTH_API_KEY": "z", "PATH": "/usr/bin"})
        self.assertEqual(scrubbed, {"PATH": "/usr/bin"})


class RunnerRefusals(unittest.TestCase):
    """Each runner's paper command refuses before importing its engine or opening a socket."""

    @classmethod
    def setUpClass(cls):
        cls.runners = {"nautilus": load("h2h_run_nautilus_test", H2H / "run_nautilus.py"),
                       "lumibot": load("h2h_run_lumibot_test", H2H / "run_lumibot.py"),
                       "lean": load("h2h_run_lean_test", H2H / "run_lean" / "run.py")}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = real_tmp_root(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def argv(self, engine, env_file):
        out = str(self.root / f"out-{engine}")
        base = {"nautilus": ["paper", "--out", out, "--state-root", str(self.root), "--trial", "t1"],
                "lumibot": ["paper", "--out", out],
                "lean": ["paper", "--lean-source", str(self.root), "--dotnet", str(self.root / "dotnet"),
                         "--plugin", str(self.root), "--out", out]}[engine]
        return base + ([] if env_file is None else ["--env-file", str(env_file)])

    def refusal(self, engine, env_file):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), mock.patch("socket.socket", side_effect=AssertionError("network")):
            code = self.runners[engine].main(self.argv(engine, env_file))
        self.assertEqual(code, 2)
        return json.loads(stdout.getvalue())["refused"]

    def write(self, name, *lines):
        path = self.root / name
        path.write_text(ENV_BODY + "".join(line + "\n" for line in lines))
        os.chmod(path, 0o600)
        return path

    def test_no_env_file(self):
        for engine in common.ENGINES:
            with self.subTest(engine=engine):
                self.assertEqual(self.refusal(engine, None), "h2h:env_file_required")

    def test_shared_and_foreign_accounts(self):
        for engine in common.ENGINES:
            other = next(e for e in common.ENGINES if e != engine)
            with self.subTest(engine=engine):
                self.assertEqual(self.refusal(engine, self.write("alpaca-paper-2.env")),
                                 "h2h:forbidden_shared_paper_account")
                self.assertEqual(self.refusal(engine, self.write(common.env_file_name(other))),
                                 "h2h:another_engines_paper_account")

    def test_live_host(self):
        for engine in common.ENGINES:
            with self.subTest(engine=engine):
                path = self.write(common.env_file_name(engine), f"APCA_API_BASE_URL={LIVE}")
                self.assertEqual(self.refusal(engine, path), "h2h:not_paper_host")

    def test_lean_needs_the_quantconnect_license_decision(self):
        path = self.write(common.env_file_name("lean"))
        self.assertEqual(self.refusal("lean", path), "h2h:lean_requires_quantconnect_license_credentials")

    def test_offline_modes_refuse_credentials_in_the_environment(self):
        with mock.patch.dict(os.environ, {"APCA_API_KEY_ID": "fixture-key-id"}):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = self.runners["nautilus"].main(["synthetic", "--out", str(self.root / "syn")])
            self.assertEqual((code, json.loads(stdout.getvalue())["refused"]),
                             (2, "h2h:credentials_present_in_offline_run"))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = self.runners["lumibot"].main(["backtest", "--lean-data", str(self.root),
                                                     "--out", str(self.root / "bt")])
            self.assertEqual((code, json.loads(stdout.getvalue())["refused"]),
                             (2, "h2h:credentials_present_in_offline_run"))


if __name__ == "__main__":
    unittest.main()
