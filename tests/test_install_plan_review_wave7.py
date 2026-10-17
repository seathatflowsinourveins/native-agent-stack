"""Selective installation and later consumers; fixtures and extracted commands only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest import mock

from tests.test_install_plan_no_start_ports import ROOT, PLAN, host_allocation, module


class SelectiveAllocationTests(unittest.TestCase):
    def fixture(self, root):
        config = root / ".config/new-wsl-native-stack"
        config.mkdir(parents=True)
        saved = host_allocation({"NS_PORT_GATEWAY": "41128"})
        (config / ".service-ports.json").write_text(json.dumps(saved))
        values = json.loads((ROOT / "adoption/hosts/example.json").read_text())
        values.update(saved)
        values.update(HOME=str(root), XDG_CONFIG_HOME=str(root / ".config"),
                      AI_MEMORY_URL="127.0.0.1:29374", NS_PORT_GATEWAY="51128", WSL_DISTRO_NAME="FixtureDistro")
        host = root / "host.json"
        host.write_text(json.dumps(values))
        return config, host, values

    def test_selective_install_refuses_an_unselected_owner_port_change_before_writes(self):
        checker = module(PLAN / "check_plan.py", "wave7_staging")
        body = checker.functions((PLAN / "install.sh").read_text())["stage_plan_sources"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, host, _ = self.fixture(root)
            before = (config / ".service-ports.json").read_bytes()
            result = subprocess.run(["bash", "-euo", "pipefail", "-c",
                'stage_plan_sources() {\n' + body + '\n}\nstage_plan_sources\nprintf "ROWS_WOULD_RUN\\n"'],
                env={"PATH": "/usr/bin:/bin", "HOME": tmp, "plan_dir": str(PLAN), "only": "memory-owner",
                     "config_root": str(config), "host_file": str(host), "NS2604_NO_START": "1"},
                text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("needs_owner", result.stderr)
            self.assertNotIn("ROWS_WOULD_RUN", result.stdout)
            self.assertEqual((config / ".service-ports.json").read_bytes(), before)

    def test_acceptance_staging_refuses_the_conflicting_explicit_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, host, _ = self.fixture(root)
            # The actual renderer invocation made before accept.sh dispatches any check.
            result = subprocess.run([sys.executable, str(PLAN / "config/observability_config.py"), "stage",
                "--config-root", str(config), "--source-root", str(PLAN / "config"),
                "--output-root", str(root / "accepted"), "--host-file", str(host)],
                env={"PATH": "/usr/bin:/bin", "HOME": tmp}, text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("needs_owner", result.stderr)
            self.assertFalse((root / "accepted/.service-ports.json").exists())

    def test_direct_client_render_and_host_loader_refuse_snapshot_conflicts(self):
        from tests import test_new_wsl_client_config as fixtures
        cfg = fixtures.cfg
        plan = cfg.load_plan(ROOT)
        results, manifest, _, errors, _ = cfg.analyse(ROOT)
        self.assertEqual(errors, [])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, _, values = self.fixture(root)
            with self.subTest(api="host_values"), mock.patch.object(fixtures.render_config, "load_host_values", return_value=values):
                with self.assertRaisesRegex(cfg.ConfigError, "needs_owner"):
                    cfg.host_values("fixture", plan, root, [])
            with mock.patch.object(fixtures.render_config, "load_host_values", return_value={**values, "NS_PORT_GATEWAY": "41128"}):
                prepared = cfg.host_values("fixture", plan, root, [])
            prepared["NS_PORT_GATEWAY"] = "51128"
            with self.subTest(api="render"), self.assertRaisesRegex(cfg.ConfigError, "needs_owner"):
                cfg.render(ROOT, results, plan, prepared, manifest)

    def test_current_home_client_render_uses_the_installers_xdg_config_root(self):
        from tests import test_new_wsl_client_config as fixtures
        cfg = fixtures.cfg
        plan = cfg.load_plan(ROOT)
        results, manifest, _, errors, _ = cfg.analyse(ROOT)
        self.assertEqual(errors, [])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, _, values = self.fixture(root)
            custom = root / "custom-config"
            custom.mkdir()
            config.rename(custom / "new-wsl-native-stack")
            values.pop("XDG_CONFIG_HOME")
            with mock.patch.dict(os.environ, {"HOME": tmp, "XDG_CONFIG_HOME": str(custom)}), \
                    mock.patch.object(fixtures.render_config, "load_host_values", return_value=values):
                with self.assertRaisesRegex(cfg.ConfigError, "needs_owner"):
                    cfg.host_values("fixture", plan, root, [])

    def test_runtime_and_drift_consumers_refuse_the_same_conflict(self):
        from tests import test_runtime_profiles as fixture
        from tools.adoption import mcp_template_drift as drift
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, host, values = self.fixture(root)
            env = {"HOME": tmp, "XDG_CONFIG_HOME": str(root / ".config"), "NS2604_HOST_FILE": str(host)}
            with mock.patch.dict(os.environ, env):
                readers = {
                    "wsl-mcp": lambda: fixture.profiles.render_wsl_mcp(root, root / "eco"),
                    "opencode": lambda: fixture.profiles.opencode_provider("gpt"),
                    "pi": lambda: fixture.profiles.pi_models("gpt"),
                    "runtime-telemetry": lambda: fixture.profiles.profile_environment("pi-gpt", root),
                    "drift-files": lambda: drift.render_files(root, host_file=host),
                    "drift-templates": lambda: drift.render_templates(root, root / "eco", host_file=host),
                }
                for name, reader in readers.items():
                    with self.subTest(consumer=name), self.assertRaisesRegex(ValueError, "needs_owner"):
                        reader()
                values["NS_PORT_GATEWAY"] = "41128"
                host.write_text(json.dumps(values))
                for name, reader in readers.items():
                    with self.subTest(consumer=name, allocation="committed"):
                        rendered = json.dumps(reader())
                        self.assertNotIn("51128", rendered)
                        if name in {"opencode", "pi"}:
                            self.assertIn("127.0.0.1:41128/v1", rendered)

    def test_selected_change_then_committed_host_reaches_every_client(self):
        from tests import test_new_wsl_client_config as fixtures
        cfg = fixtures.cfg
        checker = module(PLAN / "check_plan.py", "wave7_selected_commit")
        functions = checker.functions((PLAN / "install.sh").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, host, values = self.fixture(root)
            values.update(NS_PORT_GATEWAY="41128", NS_PORT_MEMORY="39374", AI_MEMORY_URL="127.0.0.1:39374")
            host.write_text(json.dumps(values))
            body = '\n'.join(name + '() {\n' + functions[name] + '\n}'
                             for name in ("stage_plan_sources", "run_command", "commit_allocation"))
            body += '\nstage_plan_sources\nrun_command \'printf "%s\\n" http://127.0.0.1:29374\'\nfailed=0; needs_execution=true; commit_allocation'
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", body],
                env={"PATH": "/usr/bin:/bin", "HOME": tmp, "plan_dir": str(PLAN), "only": "memory-owner",
                     "config_root": str(config), "host_file": str(host), "NS2604_NO_START": "1"},
                text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("http://127.0.0.1:39374", result.stdout)
            accepted = subprocess.run([sys.executable, str(PLAN / "config/observability_config.py"), "stage",
                "--config-root", str(config), "--source-root", str(PLAN / "config"),
                "--output-root", str(root / "accepted"), "--host-file", str(host)],
                env={"PATH": "/usr/bin:/bin", "HOME": tmp}, text=True, capture_output=True)
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            plan = cfg.load_plan(ROOT)
            results, manifest, _, errors, _ = cfg.analyse(ROOT)
            self.assertEqual(errors, [])
            with mock.patch.object(fixtures.render_config, "load_host_values", return_value=values):
                resolved = cfg.host_values("fixture", plan, root, [])
            files = cfg.render(ROOT, results, plan, resolved, manifest)
            self.assertIn("127.0.0.1:39374", files["mcp-servers.json"])
            self.assertIn("127.0.0.1:39374", files["codex.config.toml"])
            self.assertIn("127.0.0.1:41128/v1", files["codex.omniroute.config.toml"])


class ActivationInstructionsTests(unittest.TestCase):
    def test_recipe_and_checklist_require_normal_mineru_configuration_before_activation(self):
        for path in ("adoption/platforms/linux-wsl2-new-distro.md", "adoption/templates/wsl/first-boot-checklist.md"):
            with self.subTest(path=path):
                text = (ROOT / path).read_text()
                self.assertIn("install.sh --only mineru --host-file 'adoption/hosts/<host>.json'", text)
                self.assertIn("before activation", text.lower())
                self.assertIn("telemetry", text.lower())


class CurrentMemoryInitTests(unittest.TestCase):
    def test_v310_fresh_init_settings_accept_the_local_provider_migration(self):
        # v3.1.0 /11ca7c5b init.rs:207-212 copies the default template and appends
        # render_default_auth_block (token_pepper) and, on a fresh data dir, bearer_token_file.
        # The file is <data_dir>/config.toml, setup's config (setup.rs:318-320).
        template = (ROOT / "tests/fixtures/ai-memory-3.1.0-init-active.toml").read_text()
        initial = template + '\ntoken_pepper = "' + "ab" * 32 + '"\n'
        before = tomllib.loads(initial)
        self.assertEqual(before["bind"], "127.0.0.1:49374")
        self.assertNotIn("embedding_provider", before)
        checker = module(PLAN / "check_plan.py", "wave7_v310_commands")
        renderer = module(PLAN / "config/observability_config.py", "wave7_v310_ports")
        functions = checker.functions((PLAN / "install.sh").read_text())
        command = next(command for command in checker.run_commands("memory-owner", functions, set())
                       if "embedding_provider" in command)
        for port in (29374, 49374):
            with self.subTest(port=port), tempfile.TemporaryDirectory() as tmp:
                config = Path(tmp) / ".local/share/ai-memory/config.toml"
                config.parent.mkdir(parents=True)
                config.write_text(initial)
                selected = renderer.render_command(command, renderer.service_ports({"NS_PORT_MEMORY": str(port)}))
                for _ in range(2):
                    result = subprocess.run(["bash", "-euo", "pipefail", "-c", selected],
                        env={"PATH": "/usr/bin:/bin", "HOME": tmp}, text=True, capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                after = tomllib.loads(config.read_text())
                self.assertEqual(after["bind"], f"127.0.0.1:{port}")
                self.assertEqual(after["embedding_provider"], "local")
                self.assertEqual(after["auth"], before["auth"])


class ResearchAllocationTests(unittest.TestCase):
    def test_research_only_install_retains_gateway_after_staging_selector_disappears(self):
        from tests import test_research_entry
        fixture = test_research_entry.ResearchEntry()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        root = fixture.temp
        config = root / "config"
        host = root / "host.json"
        host.write_text(json.dumps(host_allocation({"NS_PORT_GATEWAY": "41128"})))
        renderer = [sys.executable, str(PLAN / "config/observability_config.py")]
        common = ["--config-root", str(config), "--plan-file", str(PLAN / "install-plan.json"),
                  "--slot", "research-harnesses"]
        staged = root / "staged"
        result = subprocess.run(renderer + ["stage", *common, "--source-root", str(PLAN / "config"),
                                "--output-root", str(staged), "--host-file", str(host)],
                                env=fixture.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        checker = module(PLAN / "check_plan.py", "wave7_research_copy")
        functions = checker.functions((PLAN / "install.sh").read_text())
        # Execute only the row's config/wrapper publication command; no checkout,
        # package operation, installer or research request can run.
        publish = next(command for command in checker.run_commands("research-gpt-researcher", functions, set())
                       if 'install -m 0700 -- "$repo_root/tools/research/gpt_researcher.sh"' in command)
        env = {**fixture.env, "repo_root": str(ROOT), "plan_dir": str(PLAN), "config_root": str(config),
               "NS2604_HOST_FILE": str(staged / ".service-ports.json")}
        result = subprocess.run(["bash", "-euo", "pipefail", "-c", publish], env=env,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        (config / "observability_config.py").write_bytes((PLAN / "config/observability_config.py").read_bytes())
        (config / "deer-flow-config.yaml").write_bytes((staged / "deer-flow-config.yaml").read_bytes())
        result = subprocess.run(renderer + ["commit-ports", *common,
            "--host-file", str(staged / ".service-ports.json")], env=fixture.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((config / ".service-ports.json").exists())
        result = subprocess.run(["bash", str(config / "gpt-researcher.sh"), "--preflight-only"],
                                env=fixture.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        selected = json.loads((fixture.run_dir(result) / "config.json").read_text())["LLM_KWARGS"]["base_url"]
        self.assertEqual(selected, "http://127.0.0.1:41128/v1")
        self.assertIn(selected, (config / "deer-flow-config.yaml").read_text())
        self.assertFalse((config / ".service-ports.json").exists())
        later = subprocess.run(renderer + ["stage", "--config-root", str(config),
            "--plan-file", str(PLAN / "install-plan.json"), "--slot", "memory-owner",
            "--source-root", str(PLAN / "config"), "--output-root", str(root / "memory-stage"),
            "--host-file", str(host)], env=fixture.env, text=True, capture_output=True)
        self.assertEqual(later.returncode, 0, later.stderr)
        host.write_text(json.dumps(host_allocation({"NS_PORT_GATEWAY": "51128"})))
        refused = subprocess.run(["bash", str(config / "gpt-researcher.sh"), "--preflight-only"],
            env={**fixture.env, "NS2604_HOST_FILE": str(host)}, text=True, capture_output=True)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("needs_owner", refused.stderr)
        self.assertEqual(json.loads((config / "gpt-researcher.config.json").read_text())["LLM_KWARGS"]["base_url"], selected)


if __name__ == "__main__":
    unittest.main()
