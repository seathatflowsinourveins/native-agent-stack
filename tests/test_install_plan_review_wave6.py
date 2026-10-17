"""Final install-path fold: extracted copies/migration and disposable files only."""
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import tomllib
import unittest

from tests.test_install_plan_no_start_ports import ROOT, PLAN, host_allocation, module


def produced_config_files(name, functions, helpers, visited=None):
    """Read actual copy operations independently of the plan's config_paths list."""
    visited = set() if visited is None else visited
    if name in visited:
        return {}
    visited.add(name)
    files = {}
    for line in functions.get(name, "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("copy_config "):
            target = shlex.split(line)[1]
            files[target] = "$plan_dir/config/" + target
            continue
        if line.startswith("run_command "):
            command = shlex.split(line)[1]
            if 'observability_config.py" research --config-root "$config_root"' in command:
                files["gpt-researcher.config.json"] = "$repo_root/tools/research/gpt-researcher.config.json"
            for source, target in re.findall(
                r'install -m [0-7]+ -- "(\$(?:plan_dir|repo_root)/[^"\n]+)" "\$config_root/([A-Za-z0-9_.@/-]+)"',
                command,
            ):
                files[target] = source
            continue
        for helper in helpers:
            if re.search(r"(?<![\w-])" + re.escape(helper) + r"(?![\w-])", line):
                files.update(produced_config_files(helper, functions, helpers, visited))
    return files


class PortlessOutputTests(unittest.TestCase):
    def test_source_declarations_and_commands_resolve_installed_portless_assets(self):
        renderer = module(PLAN / "config/observability_config.py", "wave6_source_declarations")
        plan = json.loads((PLAN / "install-plan.json").read_text())
        cases = {
            "playwright-cli": ("chrome-devtools-accept.html", "config/chrome-devtools-accept.html"),
            "research-harnesses": ("gateway-effort-accept.py", None),
            "trajectory-analysis": ("scout-round2-delegation.py", "config/scout-round2-delegation.py"),
            "mcp-protocol-conformance": ("mcp-conformance-accept.sh", "$plan_dir/config/mcp-conformance-accept.sh"),
        }
        for slot, (asset, declaration) in cases.items():
            with self.subTest(slot=slot), tempfile.TemporaryDirectory() as tmp:
                # Reproduce the published declaration shapes while retaining the
                # actual commands/copy_config calls as the independent source.
                row = next(row for row in plan["owners"] if row["slot"] == slot)
                row["config_paths"] = [path for path in row["config_paths"] if not path.endswith("/" + asset)]
                if declaration:
                    row["config_paths"].append(declaration)
                root = Path(tmp)
                ports = renderer.service_ports()
                (root / asset).write_text(renderer.render_asset(asset, (PLAN / "config" / asset).read_text(), ports))
                self.assertEqual(renderer.installation_ports(ports, root, plan, slot), ports)
                self.assertFalse((root / ".service-ports.json").exists())

    def test_every_portless_rows_actual_files_allow_an_unchanged_rerun(self):
        plan = json.loads((PLAN / "install-plan.json").read_text())
        checker = module(PLAN / "check_plan.py", "wave6_copy_inventory")
        renderer = module(PLAN / "config/observability_config.py", "wave6_render_inventory")
        functions = checker.functions((PLAN / "install.sh").read_text())
        helpers = set(functions) - {row["slot"] for row in plan["owners"]}
        port_owners = {owner for owner, _ in renderer.SERVICE_PORTS.values()}
        checked_rows = checked_files = 0
        for row in plan["owners"]:
            slot = row["slot"]
            if slot in port_owners:
                continue
            files = produced_config_files(slot, functions, helpers)
            if not files:
                continue
            checked_rows += 1
            checked_files += len(files)
            with self.subTest(slot=slot), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                host, config = root / "host.json", root / "config"
                host.write_text(json.dumps(host_allocation()))
                command = [sys.executable, str(PLAN / "config/observability_config.py")]
                common = ["--config-root", str(config), "--source-root", str(PLAN / "config"),
                          "--plan-file", str(PLAN / "install-plan.json"), "--slot", slot]
                env = {"PATH": "/usr/bin:/bin", "HOME": tmp}
                staged = root / "staged"
                first = subprocess.run(command + ["stage", *common, "--host-file", str(host),
                                                  "--output-root", str(staged)],
                                       env=env, text=True, capture_output=True)
                self.assertEqual(first.returncode, 0, first.stderr)
                # Copy only the files the row/helper actually writes. No installer,
                # service command or complete install/accept script can execute.
                for target, source in files.items():
                    src = (staged / source.removeprefix("$plan_dir/config/")
                           if source.startswith("$plan_dir/config/")
                           else ROOT / source.removeprefix("$repo_root/"))
                    dest = config / target
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(src.read_bytes())
                commit = subprocess.run(command + ["commit-ports", *common,
                    "--host-file", str(staged / ".service-ports.json")],
                    env=env, text=True, capture_output=True)
                self.assertEqual(commit.returncode, 0, commit.stderr)
                self.assertFalse((config / ".service-ports.json").exists())
                retry = subprocess.run(command + ["stage", *common, "--host-file", str(host),
                                                  "--output-root", str(root / "retry")],
                                       env=env, text=True, capture_output=True)
                self.assertEqual(retry.returncode, 0, retry.stderr)
                # Retain the existing custody boundary for every recognized row.
                changed = config / sorted(files)[0]
                changed.write_bytes(changed.read_bytes() + b"\n# operator modification\n")
                rejected = subprocess.run(command + ["stage", *common, "--host-file", str(host),
                                                     "--output-root", str(root / "changed")],
                                          env=env, text=True, capture_output=True)
                self.assertNotEqual(rejected.returncode, 0)
                self.assertIn("needs_owner", rejected.stderr)
        self.assertEqual((checked_rows, checked_files), (13, 31), "Re-audit actual portless writes if the recipe changes")


class MemoryMigrationTests(unittest.TestCase):
    def migration(self, port):
        checker = module(PLAN / "check_plan.py", "wave6_memory_commands")
        renderer = module(PLAN / "config/observability_config.py", "wave6_memory_ports")
        functions = checker.functions((PLAN / "install.sh").read_text())
        migration = next(command for command in checker.run_commands("memory-owner", functions, set())
                         if "embedding_provider" in command)
        return renderer.render_command(migration, renderer.service_ports({"AI_MEMORY_URL": f"127.0.0.1:{port}"}))

    def test_memory_migration_is_idempotent_at_the_upstream_default_port(self):
        command = self.migration(49374)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / ".local/share/ai-memory/config.toml"
            config.parent.mkdir(parents=True)
            config.write_text('bind = "127.0.0.1:49374"\nlog_level = "info"\n')
            env = {"PATH": "/usr/bin:/bin", "HOME": tmp}
            for _ in range(2):
                result = subprocess.run(["bash", "-euo", "pipefail", "-c", command],
                                        env=env, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            # Success must mean valid native TOML, not just grep finding a value.
            settings = tomllib.loads(config.read_text())
            self.assertEqual(settings["bind"], "127.0.0.1:49374")
            self.assertEqual(settings["embedding_provider"], "local")
            self.assertEqual(settings["log_level"], "info")

    def test_existing_provider_and_default_or_moved_allocations_stay_valid_on_rerun(self):
        for port in (29374, 39374, 49374):
            for provider in (None, "local", "openai"):
                with self.subTest(port=port, provider=provider), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    config = root / ".local/share/ai-memory/config.toml"
                    config.parent.mkdir(parents=True)
                    original = 'bind = "127.0.0.1:49374"\nlog_level = "info"\n'
                    if provider:
                        original += f'embedding_provider = "{provider}"\n'
                    config.write_text(original)
                    env = {"PATH": "/usr/bin:/bin", "HOME": tmp}
                    for _ in range(2):
                        result = subprocess.run(["bash", "-euo", "pipefail", "-c", self.migration(port)],
                                                env=env, text=True, capture_output=True)
                        self.assertEqual(result.returncode, 1 if provider == "openai" else 0, result.stderr)
                    settings = tomllib.loads(config.read_text())
                    self.assertEqual(settings["bind"], f"127.0.0.1:{port}")
                    self.assertEqual(settings["embedding_provider"], provider or "local")
                    self.assertEqual(settings["log_level"], "info")


class MineruTelemetryOrderTests(unittest.TestCase):
    def test_normal_setup_disables_telemetry_before_model_download(self):
        checker = module(PLAN / "check_plan.py", "wave6_mineru_order")
        functions = checker.functions((PLAN / "install.sh").read_text())
        command = next(command for command in checker.run_commands("mineru", functions, set())
                       if "models download" in command)
        script = ('mineru() { printf "MINERU %s\\n" "$*"; }; '
                  'mineru-kit() { printf "KIT %s\\n" "$*"; }; jq() { return 1; };\n' + command)
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", script],
                env={"PATH": "/usr/bin:/bin", "HOME": tmp, "NS2604_NO_START": "0"},
                text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertLess(result.stdout.index("MINERU telemetry disable"),
                            result.stdout.index("KIT models download --tier standard"))
            self.assertLess(result.stdout.index("KIT models verify --tier standard"),
                            result.stdout.index("MINERU config set parse_server.local.managed_tier"))
            self.assertIn("MINERU server stop", result.stdout)

    def test_download_failure_cleans_up_only_the_daemon_started_for_telemetry(self):
        checker = module(PLAN / "check_plan.py", "wave6_mineru_failure")
        functions = checker.functions((PLAN / "install.sh").read_text())
        command = next(command for command in checker.run_commands("mineru", functions, set())
                       if "models download" in command)
        for running in (False, True):
            with self.subTest(already_running=running), tempfile.TemporaryDirectory() as tmp:
                script = ('mineru() { printf "MINERU %s\\n" "$*"; }; '
                          'mineru-kit() { printf "KIT %s\\n" "$*"; return 37; }; '
                          f'jq() {{ return {0 if running else 1}; }};\n' + command)
                result = subprocess.run(["bash", "-euo", "pipefail", "-c", script],
                    env={"PATH": "/usr/bin:/bin", "HOME": tmp, "NS2604_NO_START": "0"},
                    text=True, capture_output=True)
                self.assertEqual(result.returncode, 37, result.stderr)
                self.assertLess(result.stdout.index("MINERU telemetry disable"),
                                result.stdout.index("KIT models download"))
                self.assertEqual("MINERU server stop" in result.stdout, not running)
                self.assertNotIn("KIT models verify", result.stdout)
                self.assertNotIn("MINERU config set", result.stdout)


if __name__ == "__main__":
    unittest.main()
