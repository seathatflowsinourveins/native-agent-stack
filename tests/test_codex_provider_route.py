"""Offline provider-selection regressions; no client, network or credential store."""
import contextlib
import io
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "sota-convergence"
sys.path.insert(0, str(TOOLS))
import codex_lane as lane


class ProviderRouteTests(unittest.TestCase):
    def command(self, **kwargs):
        return lane.build_command(Path("export"), Path("schema"), Path("output"), "max", "prompt",
                                  "gpt-6-astra", lane.ISOLATION_ARGS, **kwargs)

    def config(self, argv):
        # Codex accepts the existing unquoted effort flag as a string fallback;
        # provider tables and the other isolation overrides use actual TOML.
        return tomllib.loads("\n".join(argv[i + 1] for i, x in enumerate(argv[:-1])
                                     if x == "-c" and not argv[i + 1].startswith("model_reasoning_effort=")))

    def test_missing_provider_refuses_constructor(self):
        with self.assertRaisesRegex(ValueError, "--provider"):
            self.command()

    def test_native_choice_preserves_pins_and_blind_flags(self):
        argv = self.command(provider="native")
        self.assertEqual(argv[argv.index("-m") + 1], "gpt-6-astra")
        self.assertIn("model_reasoning_effort=max", argv)
        self.assertIn("--ignore-user-config", argv)
        config = self.config(argv)
        self.assertEqual(config["model_provider"], "openai")
        self.assertEqual(config["service_tier"], "fast")
        self.assertEqual(config["web_search"], "disabled")
        self.assertFalse(config["features"]["hooks"])

    def test_gateway_block_parses_without_loading_a_profile(self):
        argv = self.command(provider="omniroute", base_url="http://127.0.0.1:21128/v1")
        self.assertNotIn("-p", argv)
        self.assertIn("--ignore-user-config", argv)
        config = self.config(argv)
        self.assertEqual(config["model_provider"], "omniroute")
        self.assertEqual(config["model_providers"]["omniroute"]["base_url"], "http://127.0.0.1:21128/v1")
        self.assertFalse(config["model_providers"]["omniroute"]["requires_openai_auth"])
        self.assertFalse(config["features"]["shell_snapshot"])
        self.assertEqual(config["shell_environment_policy"]["filters"]["OMNIROUTE_API_KEY"], "exclude")
        self.assertEqual(config["service_tier"], "fast")
        self.assertEqual(config["web_search"], "disabled")

    def test_gateway_refuses_missing_or_nonloopback_endpoint(self):
        for url in (None, "https://example.invalid/v1", "http://127.0.0.1/v1",
                    "http://127.0.0.1:0/v1", "http://127.0.0.1:65536/v1",
                    "http://127.0.0.1:21128/v1?x=y"):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "loopback"):
                self.command(provider="omniroute", base_url=url)

    def test_public_placeholder_does_not_read_inherited_key(self):
        class ValueGuard(dict):
            def __getitem__(self, key):
                if key == "OMNIROUTE_API_KEY":
                    raise AssertionError("inherited key must not be read")
                return super().__getitem__(key)
        sentinel = object()
        original = ValueGuard({"OMNIROUTE_API_KEY": sentinel, "HOME": "empty-home", "PATH": "/usr/bin"})
        env = lane.provider_env("omniroute", original)
        self.assertEqual(env["OMNIROUTE_API_KEY"], "local")
        self.assertEqual(env["HOME"], "empty-home")
        self.assertEqual(env["PATH"], "/usr/bin")
        self.assertIs(dict.__getitem__(original, "OMNIROUTE_API_KEY"), sentinel)

    def test_missing_cli_provider_refuses_before_any_state_or_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            with mock.patch.object(lane.subprocess, "Popen") as launch, contextlib.redirect_stderr(io.StringIO()):
                rc = lane.main(["--work-dir", str(work), "--repo", tmp])
            self.assertEqual(rc, 2)
            self.assertFalse(work.exists())
            launch.assert_not_called()

    def test_gateway_run_uses_public_token_and_keeps_empty_home(self):
        argv = self.command(provider="omniroute", base_url="http://127.0.0.1:21128/v1")
        process = mock.Mock(returncode=0)
        process.communicate.return_value = ("", "")
        with mock.patch.object(lane, "CHILD_CODEX_HOME", Path("blind-home")), \
             mock.patch.object(lane, "child_env", return_value={"HOME": "empty-home", "PATH": "/usr/bin"}), \
             mock.patch.object(lane, "blind_child_argv", side_effect=lambda a: a), \
             mock.patch.object(lane.subprocess, "Popen", return_value=process) as launch:
            result = lane.run_attempt(argv, 5)
        self.assertEqual(result["exit_code"], 0)
        env = launch.call_args.kwargs["env"]
        self.assertEqual(env["HOME"], "empty-home")
        self.assertEqual(env["OMNIROUTE_API_KEY"], "local")


    def test_blind_environment_filters_by_name_before_reading_key_values(self):
        class ValueGuard(dict):
            def __getitem__(self, key):
                if key.endswith("API_KEY"):
                    raise AssertionError("inherited key must not be read")
                return super().__getitem__(key)
        with mock.patch.object(lane.os, "environ", ValueGuard({"OMNIROUTE_API_KEY": object(), "OPENAI_API_KEY": object(), "LANG": "C"})):
            env = lane.child_env(Path("blind-home"))
        self.assertEqual(env["LANG"], "C")
        self.assertFalse({"OMNIROUTE_API_KEY", "OPENAI_API_KEY"} & set(env))


if __name__ == "__main__":
    unittest.main()
