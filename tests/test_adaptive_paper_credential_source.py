"""`--credentials keychain-env` and the paper-only guard for the adaptive-paper
loaders (blueprints/us-equities/adaptive-paper/credential_source.py, plus
runner.py's and market_research.py's `paper_credentials()` and CLI wiring).

Local integration class, stdlib only: no broker call, no network, no real
key. Every credential value below is a stand-in, and the Keychain is never
touched -- `secret run` is represented by the process environment it would
hand down. See docs/decisions/2026-09-22-broker-credential-handling.md
(2026-09-25 addendum).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))

import credential_source as cs  # noqa: E402
import market_research as mr  # noqa: E402
import runner as runner_module  # noqa: E402

try:  # package mode (python -m unittest tests.x) or discover -s tests (top-level modules)
    from .adaptive_paper_hermetic import real_tmp_root
except ImportError:
    from adaptive_paper_hermetic import real_tmp_root  # noqa: E402

KEY = "fixture-key-id"
SECRET = "fixture-secret-key"
PAPER = "https://paper-api.alpaca.markets"
LIVE = "https://api.alpaca.markets"
OTHER = "https://example.invalid"

# Every environment name the code under test reads; each test starts from an
# environment with none of them set.
_NAMES = (cs.KEY_ID_VARIABLE, cs.SECRET_KEY_VARIABLE, cs.BASE_URL_VARIABLE, *cs.ENV_FILE_LOADER_MARKERS)


@contextlib.contextmanager
def clean_environ(**values):
    """os.environ with none of `_NAMES` set, then `values` added; restored
    afterwards (patch.dict)."""
    with patch.dict(os.environ):
        for name in _NAMES:
            os.environ.pop(name, None)
        os.environ.update(values)
        yield os.environ


def pair(**extra):
    return {cs.KEY_ID_VARIABLE: KEY, cs.SECRET_KEY_VARIABLE: SECRET, **extra}


class _NoLeakMixin:
    def assertRefusedWithoutLeak(self, error, reason, *secrets):
        self.assertEqual(str(error), reason)
        self.assertEqual(error.args, (reason,))
        self.assertIsNone(error.__context__)
        self.assertIsNone(error.__cause__)
        for value in (KEY, SECRET, *secrets):
            self.assertNotIn(value, str(error))
            self.assertNotIn(value, repr(error))


class PaperBaseUrl(_NoLeakMixin, unittest.TestCase):
    def test_absent_and_exact_paper_url_are_accepted(self):
        for value in (None, PAPER, PAPER + "/"):
            with self.subTest(value=value):
                self.assertIsNone(cs.paper_base_url_reason(value))
                cs.require_paper_base_url(value)

    def test_live_trading_host_has_its_own_reason(self):
        for value in (LIVE, LIVE + "/", LIVE + "/v2", "http://api.alpaca.markets", "https://API.ALPACA.MARKETS",
                      " https://api.alpaca.markets"):
            with self.subTest(value=value):
                with self.assertRaises(cs.CredentialSourceError) as caught:
                    cs.require_paper_base_url(value)
                self.assertRefusedWithoutLeak(caught.exception, cs.REASON_LIVE_HOST, value.strip())

    def test_every_other_value_is_refused_as_not_paper(self):
        for value in ("", OTHER, "https://data.alpaca.markets", "https://broker-api.alpaca.markets",
                      "https://paper-api.alpaca.markets.example.invalid", "http://paper-api.alpaca.markets",
                      "https://paper-api.alpaca.markets:8443", "https://user@paper-api.alpaca.markets",
                      "https://paper-api.alpaca.markets/v2", "https://paper-api.alpaca.markets?x=1",
                      "paper-api.alpaca.markets", "HTTPS://PAPER-API.ALPACA.MARKETS", "https://[::1",
                      b"https://paper-api.alpaca.markets", 7):
            with self.subTest(value=value):
                with self.assertRaises(cs.CredentialSourceError) as caught:
                    cs.require_paper_base_url(value)
                leaked = (value,) if isinstance(value, str) and value else ()
                self.assertRefusedWithoutLeak(caught.exception, cs.REASON_NOT_PAPER, *leaked)


class SelectionError(unittest.TestCase):
    def test_consistent_pairs_pass(self):
        self.assertIsNone(cs.selection_error(cs.SOURCE_ENV_FILE, Path("paper.env")))
        self.assertIsNone(cs.selection_error(cs.SOURCE_KEYCHAIN_ENV, None))

    def test_env_file_source_needs_a_file(self):
        self.assertIn("requires --env-file", cs.selection_error(cs.SOURCE_ENV_FILE, None))

    def test_keychain_source_refuses_a_file(self):
        message = cs.selection_error(cs.SOURCE_KEYCHAIN_ENV, Path("/private/paper.env"))
        self.assertIn("cannot be combined", message)
        self.assertNotIn("/private/paper.env", message)


class KeychainEnvCredentials(_NoLeakMixin, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = real_tmp_root(self.tmp.name)
        # Precondition for every "outside a worktree" case below.
        self.assertFalse(cs._has_git_ancestor(str(self.root)), "temporary root is inside a Git worktree")
        self.repo = self.root / "repo"
        (self.repo / ".git").mkdir(parents=True)
        (self.repo / ".envrc").write_text("# stand-in\n")
        self.linked = self.root / "linked"
        self.linked.mkdir()
        (self.linked / ".git").write_text("gitdir: /nonexistent/stand-in\n")
        self.plain = self.root / "plain"
        self.plain.mkdir()
        (self.plain / ".envrc").write_text("# stand-in\n")

    def tearDown(self):
        self.tmp.cleanup()

    def refused(self, environ, reason, cwd=None):
        with self.assertRaises(cs.CredentialSourceError) as caught:
            cs.keychain_env_credentials(environ, cwd=cwd)
        self.assertRefusedWithoutLeak(caught.exception, reason, *(v for v in environ.values() if v))
        self.assertNotIn(cs.KEY_ID_VARIABLE, environ)
        self.assertNotIn(cs.SECRET_KEY_VARIABLE, environ)
        return caught.exception

    def test_both_set_returns_the_pair_and_removes_it_from_the_environment(self):
        environ = pair(OTHER_NAME="kept")
        self.assertEqual(cs.keychain_env_credentials(environ), (KEY, SECRET))
        self.assertEqual(environ, {"OTHER_NAME": "kept"})

    def test_default_environment_is_the_process_environment(self):
        with clean_environ(**pair()):
            self.assertEqual(cs.keychain_env_credentials(), (KEY, SECRET))
            self.assertNotIn(cs.KEY_ID_VARIABLE, os.environ)
            self.assertNotIn(cs.SECRET_KEY_VARIABLE, os.environ)

    def test_paper_base_url_is_accepted(self):
        self.assertEqual(cs.keychain_env_credentials(pair(APCA_API_BASE_URL=PAPER)), (KEY, SECRET))

    def test_neither_set_is_missing(self):
        self.refused({}, cs.REASON_ENV_MISSING)

    def test_only_one_set_is_partial(self):
        self.refused({cs.KEY_ID_VARIABLE: KEY}, cs.REASON_ENV_PARTIAL)
        self.refused({cs.SECRET_KEY_VARIABLE: SECRET}, cs.REASON_ENV_PARTIAL)
        self.refused({cs.KEY_ID_VARIABLE: ""}, cs.REASON_ENV_PARTIAL)

    def test_empty_value_is_refused(self):
        self.refused({cs.KEY_ID_VARIABLE: "", cs.SECRET_KEY_VARIABLE: SECRET}, cs.REASON_ENV_EMPTY)
        self.refused({cs.KEY_ID_VARIABLE: KEY, cs.SECRET_KEY_VARIABLE: ""}, cs.REASON_ENV_EMPTY)
        self.refused({cs.KEY_ID_VARIABLE: "", cs.SECRET_KEY_VARIABLE: ""}, cs.REASON_ENV_EMPTY)

    def test_value_that_is_not_one_printable_ascii_token_is_refused(self):
        for bad in (" " + SECRET, SECRET + "\n", "fixture\tsecret", "fixture-secrét", "fixture\x07secret",
                    "x" * (cs.MAX_VALUE_CHARS + 1)):
            with self.subTest(bad=repr(bad)):
                self.refused({cs.KEY_ID_VARIABLE: KEY, cs.SECRET_KEY_VARIABLE: bad}, cs.REASON_ENV_INVALID)
                self.refused({cs.KEY_ID_VARIABLE: bad, cs.SECRET_KEY_VARIABLE: SECRET}, cs.REASON_ENV_INVALID)
        self.assertEqual(cs.keychain_env_credentials(pair(**{cs.SECRET_KEY_VARIABLE: "x" * cs.MAX_VALUE_CHARS})),
                         (KEY, "x" * cs.MAX_VALUE_CHARS))

    def test_live_or_other_base_url_is_refused_first(self):
        self.refused(pair(APCA_API_BASE_URL=LIVE), cs.REASON_LIVE_HOST)
        self.refused(pair(APCA_API_BASE_URL=OTHER), cs.REASON_NOT_PAPER)
        self.refused(pair(APCA_API_BASE_URL=""), cs.REASON_NOT_PAPER)
        # Paper-only is checked before presence, so it is never masked.
        self.refused({cs.BASE_URL_VARIABLE: LIVE}, cs.REASON_LIVE_HOST)

    def test_each_loader_marker_inside_a_worktree_is_refused(self):
        for name in cs.ENV_FILE_LOADER_MARKERS:
            with self.subTest(marker=name):
                self.refused(pair(**{name: str(self.repo / ".envrc")}), cs.REASON_ENV_WORKTREE)

    def test_direnv_dir_prefix_and_linked_worktree_file(self):
        self.refused(pair(DIRENV_DIR="-" + str(self.repo)), cs.REASON_ENV_WORKTREE)
        self.refused(pair(DIRENV_FILE=str(self.linked / ".envrc")), cs.REASON_ENV_WORKTREE)
        self.refused(pair(DIRENV_FILE=str(self.repo / "sub" / "missing" / ".env")), cs.REASON_ENV_WORKTREE)

    def test_any_of_several_uv_env_files_inside_a_worktree_is_refused(self):
        value = f"{self.plain / '.envrc'} {self.repo / '.envrc'}"
        self.refused(pair(UV_ENV_FILE=value), cs.REASON_ENV_WORKTREE)

    def test_relative_marker_resolves_against_cwd(self):
        self.refused(pair(MISE_ENV_FILE=".env"), cs.REASON_ENV_WORKTREE, cwd=str(self.repo))
        self.assertEqual(cs.keychain_env_credentials(pair(MISE_ENV_FILE=".env"), cwd=str(self.plain)), (KEY, SECRET))

    def test_symlink_outside_a_worktree_to_a_file_inside_one_is_refused(self):
        link = self.plain / "link.env"
        link.symlink_to(self.repo / ".envrc")
        self.refused(pair(DIRENV_FILE=str(link)), cs.REASON_ENV_WORKTREE)

    def test_markers_outside_every_worktree_or_empty_are_accepted(self):
        environ = pair(DIRENV_FILE=str(self.plain / ".envrc"), DIRENV_DIR="-" + str(self.plain), UV_ENV_FILE="",
                       PIPENV_DOTENV_LOCATION=str(self.plain / "absent.env"))
        self.assertEqual(cs.keychain_env_credentials(environ), (KEY, SECRET))

    def test_an_uninspectable_marker_location_fails_closed(self):
        with patch.object(cs.os, "lstat", side_effect=PermissionError(13, "stand-in", str(self.plain))):
            self.refused(pair(DIRENV_FILE=str(self.plain / ".envrc")), cs.REASON_ENV_WORKTREE)

    def test_relative_marker_without_a_current_directory_fails_closed(self):
        with patch.object(cs.os, "getcwd", side_effect=FileNotFoundError(2, "stand-in")):
            self.refused(pair(MISE_ENV_FILE=".env"), cs.REASON_ENV_WORKTREE)


class SelectCredentials(_NoLeakMixin, unittest.TestCase):
    def test_keychain_source_never_calls_the_file_loader(self):
        loader = Mock(side_effect=AssertionError("env file read"))
        self.assertEqual(cs.select_credentials(cs.SOURCE_KEYCHAIN_ENV, None, env_file_loader=loader,
                                               environ=pair()), (KEY, SECRET))
        loader.assert_not_called()

    def test_env_file_source_calls_the_file_loader(self):
        loader = Mock(return_value=(KEY, SECRET))
        environ = pair(APCA_API_BASE_URL=PAPER)
        self.assertEqual(cs.select_credentials(cs.SOURCE_ENV_FILE, Path("paper.env"), env_file_loader=loader,
                                               environ=environ), (KEY, SECRET))
        loader.assert_called_once_with(Path("paper.env"))
        # The env-file source leaves the process environment alone.
        self.assertIn(cs.KEY_ID_VARIABLE, environ)

    def test_env_file_source_refuses_a_non_paper_process_base_url_before_reading(self):
        for value, reason in ((LIVE, cs.REASON_LIVE_HOST), (OTHER, cs.REASON_NOT_PAPER)):
            with self.subTest(value=value):
                loader = Mock(side_effect=AssertionError("env file read"))
                with self.assertRaises(cs.CredentialSourceError) as caught:
                    cs.select_credentials(cs.SOURCE_ENV_FILE, Path("paper.env"), env_file_loader=loader,
                                          environ={cs.BASE_URL_VARIABLE: value})
                self.assertRefusedWithoutLeak(caught.exception, reason, value)
                loader.assert_not_called()

    def test_unknown_source_is_refused(self):
        with self.assertRaises(cs.CredentialSourceError) as caught:
            cs.select_credentials("plaintext", None, env_file_loader=Mock(), environ=pair())
        self.assertRefusedWithoutLeak(caught.exception, cs.REASON_UNKNOWN_SOURCE)


# Env-file fixture text, written as a literal (the same stand-ins as KEY and
# SECRET above) the way the other adaptive-paper credential tests write theirs.
ENV_BODY = "APCA_API_KEY_ID=fixture-key-id\nAPCA_API_SECRET_KEY=fixture-secret-key\n"


def write_env(directory, *extra_lines):
    path = directory / "paper.env"
    path.write_text(ENV_BODY + "".join(line + "\n" for line in extra_lines))
    os.chmod(path, 0o600)
    return path


class EnvFilePaperOnly(_NoLeakMixin, unittest.TestCase):
    """Both loaders' `credentials(path, paper_only=True)` refuse a non-paper
    APCA_API_BASE_URL line; the default keeps the earlier behavior."""

    def test_fixture_text_carries_the_stand_ins(self):
        self.assertEqual(ENV_BODY.splitlines(), [f"APCA_API_KEY_ID={KEY}", f"APCA_API_SECRET_KEY={SECRET}"])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = real_tmp_root(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_runner_file_base_url(self):
        accepted = ((), (f"APCA_API_BASE_URL={PAPER}",), (f"export APCA_API_BASE_URL='{PAPER}/'",))
        for lines in accepted:
            with self.subTest(lines=lines):
                self.assertEqual(runner_module.credentials(write_env(self.root, *lines), paper_only=True),
                                 (KEY, SECRET))
        refused = ((f"APCA_API_BASE_URL={LIVE}", cs.REASON_LIVE_HOST),
                   (f"export APCA_API_BASE_URL=\"{LIVE}/v2\"", cs.REASON_LIVE_HOST),
                   (f"APCA_API_BASE_URL={OTHER}", cs.REASON_NOT_PAPER),
                   ("APCA_API_BASE_URL=", cs.REASON_NOT_PAPER))
        for line, reason in refused:
            with self.subTest(line=line):
                with self.assertRaises(runner_module.SafetyError) as caught:
                    runner_module.credentials(write_env(self.root, line), paper_only=True)
                self.assertRefusedWithoutLeak(caught.exception, reason, LIVE, OTHER)

    def test_runner_default_is_unchanged(self):
        # order-throughput's capacity.py relies on this: it refuses the live
        # base URL itself, into its own receipt.
        path = write_env(self.root, f"APCA_API_BASE_URL={LIVE}")
        self.assertEqual(runner_module.credentials(path), (KEY, SECRET))
        # The default never parses the line at all, so a malformed one is ignored as before.
        path = write_env(self.root, "APCA_API_BASE_URL='unclosed")
        self.assertEqual(runner_module.credentials(path), (KEY, SECRET))
        with self.assertRaises(ValueError):
            runner_module.credentials(path, paper_only=True)

    def test_market_research_file_base_url(self):
        for lines in ((), (f"APCA_API_BASE_URL={PAPER}",), (f"export APCA_API_BASE_URL='{PAPER}'",)):
            with self.subTest(lines=lines):
                self.assertEqual(mr.credentials(write_env(self.root, *lines), paper_only=True), (KEY, SECRET))
        refused = (((f"APCA_API_BASE_URL={LIVE}",), cs.REASON_LIVE_HOST),
                   ((f"APCA_API_BASE_URL={OTHER}",), cs.REASON_NOT_PAPER),
                   (("APCA_API_BASE_URL=",), cs.REASON_NOT_PAPER),
                   ((f"APCA_API_BASE_URL={PAPER}", f"APCA_API_BASE_URL={LIVE}"), "duplicate_credential_variable"))
        for lines, reason in refused:
            with self.subTest(lines=lines):
                with self.assertRaises(mr.ResearchError) as caught:
                    mr.credentials(write_env(self.root, *lines), paper_only=True)
                self.assertEqual(str(caught.exception), reason)
                for value in (KEY, SECRET, LIVE, OTHER):
                    self.assertNotIn(value, str(caught.exception))

    def test_market_research_default_is_unchanged(self):
        self.assertEqual(mr.credentials(write_env(self.root, f"APCA_API_BASE_URL={LIVE}")), (KEY, SECRET))
        self.assertEqual(mr.credentials(write_env(self.root, f"APCA_API_BASE_URL={PAPER}",
                                                  f"APCA_API_BASE_URL={LIVE}")), (KEY, SECRET))


class RunnerCli(_NoLeakMixin, unittest.TestCase):
    """runner.main(): `--credentials` selection up to the first broker call,
    which is replaced by a stand-in that stops the run."""

    CONFIG = {"symbols": ["SPY"], "feed": "iex"}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = real_tmp_root(self.tmp.name)
        self.output = self.root / "out" / "preflight.json"

    def tearDown(self):
        self.tmp.cleanup()

    def main(self, *extra):
        argv = ["runner.py", "preflight", "--output", str(self.output), "--state-root", str(self.root / "state"),
                "--config", str(self.root / "unused-config.json"), *extra]
        network = Mock(side_effect=runner_module.TransportError("fixture preflight stop"))
        loader = Mock(return_value=(dict(self.CONFIG), None, None))
        with patch.object(sys, "argv", argv), \
             patch.object(runner_module, "load_config", loader), \
             patch.object(runner_module, "validate_session_policy", return_value={"overnight_holds": False}), \
             patch.object(runner_module, "check_order_contract_boundary", return_value={"active": True}), \
             patch.object(runner_module, "preflight", network), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                return runner_module.main(), network, None
            except (Exception, SystemExit) as error:  # noqa: BLE001 -- the refusal under test
                return None, network, error

    def test_keychain_env_reaches_the_first_request_and_leaves_the_environment(self):
        with clean_environ(**pair(APCA_API_BASE_URL=PAPER)):
            code, network, error = self.main("--credentials", "keychain-env")
            self.assertIsNone(error)
            self.assertNotIn(cs.KEY_ID_VARIABLE, os.environ)
            self.assertNotIn(cs.SECRET_KEY_VARIABLE, os.environ)
        self.assertEqual(code, 2)
        self.assertEqual(network.call_args.args[:2], (KEY, SECRET))
        text = self.output.read_text()
        self.assertEqual(json.loads(text)["stage"], "preflight")
        self.assertNotIn(KEY, text)
        self.assertNotIn(SECRET, text)

    def test_keychain_env_refusals_happen_before_any_request(self):
        cases = ((pair(APCA_API_BASE_URL=LIVE), cs.REASON_LIVE_HOST),
                 (pair(APCA_API_BASE_URL=OTHER), cs.REASON_NOT_PAPER),
                 ({}, cs.REASON_ENV_MISSING),
                 ({cs.SECRET_KEY_VARIABLE: SECRET}, cs.REASON_ENV_PARTIAL),
                 ({cs.KEY_ID_VARIABLE: KEY, cs.SECRET_KEY_VARIABLE: ""}, cs.REASON_ENV_EMPTY))
        for environ, reason in cases:
            with self.subTest(reason=reason), clean_environ(**environ):
                code, network, error = self.main("--credentials", "keychain-env")
                self.assertIsInstance(error, runner_module.SafetyError)
                self.assertRefusedWithoutLeak(error, reason, LIVE, OTHER)
                network.assert_not_called()
                self.assertFalse(self.output.exists())

    def test_env_file_is_a_usage_error_with_keychain_env(self):
        with clean_environ(**pair()):
            code, network, error = self.main("--credentials", "keychain-env", "--env-file", str(self.root / "x.env"))
        self.assertIsInstance(error, SystemExit)
        self.assertEqual(error.code, 2)
        network.assert_not_called()

    def test_default_source_still_requires_env_file(self):
        with clean_environ():
            code, network, error = self.main()
        self.assertIsInstance(error, SystemExit)
        self.assertEqual(error.code, 2)
        network.assert_not_called()

    def test_default_env_file_source_reaches_the_first_request(self):
        path = write_env(self.root, f"APCA_API_BASE_URL={PAPER}")
        with clean_environ():
            code, network, error = self.main("--env-file", str(path))
        self.assertIsNone(error)
        self.assertEqual(network.call_args.args[:2], (KEY, SECRET))

    def test_env_file_source_refuses_a_non_paper_file_base_url_before_any_request(self):
        path = write_env(self.root, f"APCA_API_BASE_URL={LIVE}")
        with clean_environ():
            code, network, error = self.main("--credentials", "env-file", "--env-file", str(path))
        self.assertIsInstance(error, runner_module.SafetyError)
        self.assertRefusedWithoutLeak(error, cs.REASON_LIVE_HOST, LIVE)
        network.assert_not_called()

    def test_env_file_source_refuses_a_non_paper_process_base_url_before_reading_the_file(self):
        file_loader = Mock(side_effect=AssertionError("env file read"))
        with clean_environ(APCA_API_BASE_URL=OTHER), patch.object(runner_module, "credentials", file_loader):
            code, network, error = self.main("--env-file", str(self.root / "x.env"))
        self.assertIsInstance(error, runner_module.SafetyError)
        self.assertRefusedWithoutLeak(error, cs.REASON_NOT_PAPER, OTHER)
        file_loader.assert_not_called()
        network.assert_not_called()


class MarketResearchCli(unittest.TestCase):
    """market_research.main(): the same selection, with `collect` (the only
    network path) replaced by a stand-in."""

    ARTIFACT = {"status": "complete_bounded_shadow", "items": [], "quarantined": [], "http_observations": [],
                "artifact_sha256": "0" * 64, "errors": []}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = real_tmp_root(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def main(self, *extra):
        out = self.root / "research.json"
        collect = Mock(return_value=dict(self.ARTIFACT))
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(mr, "collect", collect), contextlib.redirect_stdout(stdout), \
             contextlib.redirect_stderr(stderr):
            try:
                code = mr.main(["--symbols", "SPY", "--out", str(out), *extra])
            except SystemExit as error:
                code = ("exit", error.code)
        for text in (stdout.getvalue(), stderr.getvalue(), out.read_text() if out.exists() else ""):
            self.assertNotIn(KEY, text)
            self.assertNotIn(SECRET, text)
        return code, collect, stdout.getvalue()

    def test_keychain_env_reaches_collect_and_leaves_the_environment(self):
        with clean_environ(**pair()):
            code, collect, _ = self.main("--credentials", "keychain-env")
            self.assertNotIn(cs.KEY_ID_VARIABLE, os.environ)
            self.assertNotIn(cs.SECRET_KEY_VARIABLE, os.environ)
        self.assertEqual(code, 0)
        self.assertEqual(collect.call_args.args[:2], (KEY, SECRET))

    def test_keychain_env_refusals_report_only_the_reason_code(self):
        cases = ((pair(APCA_API_BASE_URL=LIVE), cs.REASON_LIVE_HOST),
                 ({cs.KEY_ID_VARIABLE: KEY}, cs.REASON_ENV_PARTIAL),
                 ({}, cs.REASON_ENV_MISSING))
        for environ, reason in cases:
            with self.subTest(reason=reason), clean_environ(**environ):
                code, collect, stdout = self.main("--credentials", "keychain-env")
                self.assertEqual(code, 1)
                self.assertEqual(json.loads(stdout)["error"], reason)
                collect.assert_not_called()

    def test_selection_errors_are_usage_errors(self):
        with clean_environ(**pair()):
            for extra in (("--credentials", "keychain-env", "--env-file", str(self.root / "x.env")), ()):
                with self.subTest(extra=extra):
                    code, collect, _ = self.main(*extra)
                    self.assertEqual(code, ("exit", 2))
                    collect.assert_not_called()

    def test_env_file_source_is_paper_only(self):
        path = write_env(self.root, f"APCA_API_BASE_URL={OTHER}")
        with clean_environ():
            code, collect, stdout = self.main("--env-file", str(path))
        self.assertEqual((code, json.loads(stdout)["error"]), (1, cs.REASON_NOT_PAPER))
        collect.assert_not_called()
        path = write_env(self.root)
        with clean_environ(APCA_API_BASE_URL=LIVE):
            code, collect, stdout = self.main("--env-file", str(path))
        self.assertEqual((code, json.loads(stdout)["error"]), (1, cs.REASON_LIVE_HOST))
        collect.assert_not_called()
        with clean_environ(APCA_API_BASE_URL=PAPER):
            code, collect, _ = self.main("--env-file", str(path))
        self.assertEqual(code, 0)
        self.assertEqual(collect.call_args.args[:2], (KEY, SECRET))


if __name__ == "__main__":
    unittest.main()
