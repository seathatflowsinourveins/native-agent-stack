"""Install-plan regressions: extracted shell commands and disposable config fixtures only.

Never execute install.sh, accept.sh, installers, or the host's systemctl.
The baseline is native-agent-stack@8053f14e7; upstream mechanisms are cited in
the plan's NO_START_PORTS.md record.
"""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "evidence/artifacts/new-wsl-install-plan-20261002"


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def host_allocation(overrides=None):
    """Complete, explicit fixture allocation; expected moved endpoints stay literal in tests."""
    renderer = module(PLAN / "config/observability_config.py", "fixture_allocations")
    values = {"NS_PORT_" + key: str(value) for key, value in renderer.service_ports().items()}
    if overrides and "AI_MEMORY_URL" in overrides:
        values.pop("NS_PORT_MEMORY", None)
    values.update(overrides or {})
    return values


class NoStartTests(unittest.TestCase):
    def test_mineru_transient_start_is_deferred_in_no_start_mode(self):
        checker = module(PLAN / "check_plan.py", "mineru_start_check")
        funcs = checker.functions((PLAN / "install.sh").read_text())
        command = next(c for c in checker.run_commands("mineru", funcs, set()) if "mineru server start" in c)
        script = ('mineru() { printf "CALL %s\\n" "$*"; }; '
                  'mineru-kit() { printf "KIT %s\\n" "$*"; }; jq() { return 1; };\n' + command)
        for mode in ("0", "1"):
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", script], text=True, capture_output=True,
                                    env={"PATH": "/usr/bin:/bin", "NS2604_NO_START": mode})
            self.assertEqual(result.returncode, 0, result.stderr)
            if mode == "0":
                self.assertIn("CALL server start", result.stdout)
                self.assertIn("CALL server stop", result.stdout)
            else:
                self.assertNotIn("CALL", result.stdout)
                self.assertIn("KIT models download --tier standard", result.stdout)
                self.assertIn("KIT models verify --tier standard", result.stdout)

    def test_docker_no_start_masks_package_activation_and_skips_setup(self):
        checker = module(PLAN / "check_plan.py", "docker_check")
        funcs = checker.functions((PLAN / "install.sh").read_text())
        setup = next(c for c in checker.run_commands("container-engine", funcs, set())
                     if "dockerd-rootless-setuptool.sh install" in c)
        script = ('sudo() { printf "CALL %s\\n" "$*"; }; apt_release_version() { printf "fixture"; };\n'
                  'dockerd-rootless-setuptool.sh() { printf "UNSAFE_SETUP\\n"; };\n'
                  'docker_engine_packages() {\n' + funcs["docker_engine_packages"] + '\n}\n'
                  'docker_engine_packages\n' + setup)
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", script], text=True, capture_output=True,
                                    env={"PATH": "/usr/bin:/bin", "HOME": tmp, "NS2604_NO_START": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("UNSAFE_SETUP", result.stdout)
        self.assertLess(result.stdout.index("systemctl mask docker.service docker.socket containerd.service"),
                        result.stdout.index("apt-get install"))

    def test_activation_helper_only_enables_in_normal_mode(self):
        checker = module(PLAN / "check_plan.py", "activation_check")
        body = checker.functions((PLAN / "install.sh").read_text())["activate_user_unit"]
        for mode in ("0", "1"):
            script = 'systemctl() { printf "%s\\n" "$*"; }\nactivate_user_unit() {\n' + body + '\n}\nactivate_user_unit fixture.service'
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", script],
                                    env={"PATH": "/usr/bin:/bin", "NS2604_NO_START": mode}, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "" if mode == "1" else "--user enable --now fixture.service\n")

    def test_dagu_installer_receives_no_service_mode(self):
        checker = module(PLAN / "check_plan.py", "dagu_check")
        funcs = checker.functions((PLAN / "install.sh").read_text())
        command = next(c for c in checker.run_commands("dagu", funcs, set()) if "installer.sh" in c)
        script = 'curl() { :; }; bash() { printf "%s\\n" "$*"; };\n' + command
        result = subprocess.run(["bash", "-euo", "pipefail", "-c", script],
                                env={"PATH": "/usr/bin:/bin", "dagu_service_mode": "no"}, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--service no --service-scope user", result.stdout)

    def test_foreground_units_are_registered_without_activation(self):
        checker = module(PLAN / "check_plan.py", "unit_check")
        body = checker.functions((PLAN / "install.sh").read_text())["register_service_row"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config"
            config.mkdir()
            (config / ".service-ports.json").write_text(json.dumps(host_allocation()))
            (config / "ns2604-prometheus.service").write_text("[Service]\nExecStart=/bin/true\n")
            grafana = root / ".local/bin/grafana"
            grafana.parent.mkdir(parents=True)
            grafana.write_text("fixture binary path only")
            script = 'systemctl() { printf "CALL %s\\n" "$*"; }\nregister_service_row() {\n' + body + '\n}\n'
            script += '\n'.join('register_service_row ' + slot for slot in (
                "otel-collector-contrib", "prometheus", "loki", "grafana", "alerting"))
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", script], text=True, capture_output=True,
                                    env={"PATH": "/usr/bin:/bin", "HOME": tmp, "config_root": str(config),
                                         "plan_dir": str(PLAN), "config_source_root": str(PLAN / "config"),
                                         "tool_root": str(root / "tools"), "NS2604_NO_START": "1"})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(list((root / ".config/systemd/user").glob("*.service"))), 5)
            self.assertEqual(result.stdout.count("--user daemon-reload"), 5)
            self.assertNotRegex(result.stdout, r"\b(enable|start|restart|preset)\b")
            self.assertFalse(list((root / ".config/systemd/user").glob("*.wants")))

    def test_checker_rejects_start_bypass_in_every_service_row(self):
        checker = module(PLAN / "check_plan.py", "every_row_check")
        text = (PLAN / "install.sh").read_text()
        funcs = checker.functions(text)
        rows = json.loads((PLAN / "install-plan.json").read_text())["owners"]
        for row in rows:
            if row.get("service"):
                with self.subTest(slot=row["slot"]):
                    changed = dict(funcs)
                    changed[row["slot"]] += '\nrun_command "systemctl --user start unsafe.service"'
                    errors = []
                    checker.no_start_contract(rows, changed, text, lambda tag, msg: errors.append(msg))
                    self.assertTrue(any(row["slot"] + ": direct service activation" in e for e in errors), errors)

    def test_memory_drop_in_is_installed_and_reloaded_without_enable_or_start(self):
        # ai-memory 3.1.0's setup writes, enables and starts the unit and is deferred with --no-start; the row's own
        # service step installs the plan's drop-in and only reloads (akitaonrails/ai-memory@11ca7c5b
        # crates/ai-memory-cli/src/commands/user_service.rs:855-864).
        checker = module(PLAN / "check_plan.py", "plan_check")
        funcs = checker.functions((PLAN / "install.sh").read_text())
        commands = checker.run_commands("memory-owner", funcs, set())
        command = next(c for c in commands if "systemd/user" in c)
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            helper = ("activate_user_unit() {\n" + funcs["activate_user_unit"] + "\n}\n"
                      if "activate_user_unit" in funcs else "")
            script = "set -euo pipefail\n" + helper + "\n" + (
                'systemctl() { printf "CALL %s\\n" "$*"; }\n'
                'export -f systemctl\n'
            ) + command
            result = subprocess.run(["bash", "-c", script], text=True, capture_output=True,
                                    env={"PATH": "/usr/bin:/bin", "HOME": tmp, "NS2604_NO_START": "1",
                                         "config_root": str(PLAN / "config"), "plan_dir": str(PLAN)})
            self.assertEqual(result.returncode, 0, result.stderr)
            drop = home / ".config/systemd/user/ai-memory.service.d/override.conf"
            self.assertEqual(drop.read_bytes(), (PLAN / "config/ai-memory-override.conf").read_bytes())
            self.assertFalse((home / ".config/systemd/user/ai-memory.service").exists())
            self.assertIn("--user daemon-reload", result.stdout)
            self.assertNotRegex(result.stdout, r"\b(enable|start|restart|preset)\b")
            # A drop-in the plan did not write is the operator's: refused, kept, and nothing reloads.
            drop.write_text("[Service]\nMemoryMax=1G\n")
            result = subprocess.run(["bash", "-c", script], text=True, capture_output=True,
                                    env={"PATH": "/usr/bin:/bin", "HOME": tmp, "NS2604_NO_START": "1",
                                         "config_root": str(PLAN / "config"), "plan_dir": str(PLAN)})
            self.assertEqual(result.returncode, 1)
            self.assertIn("needs_owner: existing ai-memory drop-in", result.stderr)
            self.assertIn("is not the plan copy; retained.", result.stderr)
            self.assertEqual(drop.read_text(), "[Service]\nMemoryMax=1G\n")
            self.assertNotIn("daemon-reload", result.stdout)

    def test_no_start_is_an_install_option(self):
        self.assertTrue(re.search(r"--no-start\)", (PLAN / "install.sh").read_text()), "missing --no-start option")


class RtkFreshHostTests(unittest.TestCase):
    def test_hook_checks_ignore_the_upstream_missing_hook_warning(self):
        checker = module(PLAN / "check_plan.py", "rtk_plan_check")
        install = checker.functions((PLAN / "install.sh").read_text())
        acceptance = checker.functions((PLAN / "accept.sh").read_text())
        programs = [command for command in checker.run_commands("command-output", install, set())
                    if 'hook check "$command"' in command]
        programs += [command for _, _, _, command in checker.checks_of(acceptance["command-output"])
                     if 'hook check "$command"' in command]
        self.assertEqual(len(programs), 2)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = root / "bin/rtk"
            fake.parent.mkdir()
            fake.write_text('#!/bin/bash\n'
                            'if [[ "${RTK_SUPPRESS_HOOK_WARNING:-0}" != 1 ]]; then '
                            'printf "No hook installed\\n" >&2; fi\n'
                            'if [[ "$3" == "git status" ]]; then printf "rtk git status\\n"; '
                            'else printf "No rewrite for: %s\\n" "$3"; exit 1; fi\n')
            fake.chmod(0o755)
            for index, program in enumerate(programs):
                with self.subTest(carrier=("install", "accept")[index]):
                    # Only the hook-check fragment: never initialize/trust hooks or run a client.
                    end = program.index('[[ "$decision" == "rtk git status" ]]') + len('[[ "$decision" == "rtk git status" ]]')
                    start = program.index('for command in ')
                    fragment = 'e="$ECO_ROOT"; ' + program[start:end]
                    result = subprocess.run(["bash", "-euo", "pipefail", "-c", fragment],
                                            env={"PATH": "/usr/bin:/bin", "ECO_ROOT": tmp},
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, "missing-hook stderr contaminated the decision")


class HostPortTests(unittest.TestCase):
    def test_shell_dispatchers_use_host_ports_and_staged_config_sources(self):
        checker = module(PLAN / "check_plan.py", "dispatch_ports")
        install = checker.functions((PLAN / "install.sh").read_text())
        acceptance = checker.functions((PLAN / "accept.sh").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "source").mkdir()
            (root / "source/probe.txt").write_text("http://127.0.0.1:31128")
            (root / "config/.service-ports.json").write_text(json.dumps(host_allocation({"NS_PORT_GATEWAY": "31128"})))
            env = {"PATH": "/usr/bin:/bin", "plan_dir": str(PLAN), "config_root": str(root / "config"),
                   "config_source_root": str(root / "source")}
            program = 'test "$(cat "$plan_dir/config/probe.txt")" = "http://127.0.0.1:21128"'
            script = 'run_command() {\n' + install["run_command"] + '\n}\nrun_command ' + shlex.quote(program)
            installed = subprocess.run(["bash", "-euo", "pipefail", "-c", script], env=env, text=True, capture_output=True)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            script = ('stage=post_install; failed=0; port_args=(); prepare_path() { :; };\ncheck() {\n'
                      + acceptance["check"] + '\n}\ncheck fixture smoke ' + shlex.quote(program) + '\nexit "$failed"')
            accepted = subprocess.run(["bash", "-euo", "pipefail", "-c", script], env=env, text=True, capture_output=True)
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertEqual(accepted.stdout, "fixture | post_install | 0\n")

    def test_staging_and_later_commands_share_the_persisted_allocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host = root / "host.json"
            host.write_text(json.dumps(host_allocation({"NS_PORT_GATEWAY": "31128", "AI_MEMORY_URL": "127.0.0.1:39374"})))
            script = str(PLAN / "config/observability_config.py")
            common = [sys.executable, script]
            result = subprocess.run(common + ["stage", "--config-root", str(root / "config"),
                "--source-root", str(PLAN / "config"), "--output-root", str(root / "staged"),
                "--host-file", str(host)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("serve --port 31128", (root / "staged/omniroute-serve.sh").read_text())
            self.assertIn("Environment=PORT=31128", (root / "staged/omniroute.service").read_text())
            self.assertFalse((root / "config/.service-ports.json").exists())
            committed = subprocess.run(common + ["commit-ports", "--config-root", str(root / "config"),
                "--host-file", str(root / "staged/.service-ports.json")], text=True, capture_output=True)
            self.assertEqual(committed.returncode, 0, committed.stderr)
            saved = (root / "config/.service-ports.json").read_bytes()
            command = subprocess.run(common + ["command", "--config-root", str(root / "config")],
                                     input="http://127.0.0.1:21128 http://127.0.0.1:29374", text=True, capture_output=True)
            self.assertEqual(command.returncode, 0, command.stderr)
            self.assertEqual(command.stdout, "http://127.0.0.1:31128 http://127.0.0.1:39374")
            acceptance = subprocess.run(common + ["stage", "--config-root", str(root / "config"),
                "--source-root", str(PLAN / "config"), "--output-root", str(root / "accept-source")],
                text=True, capture_output=True)
            self.assertEqual(acceptance.returncode, 0, acceptance.stderr)
            self.assertEqual((root / "config/.service-ports.json").read_bytes(), saved)
            self.assertEqual((root / "staged/gpt-gateway-topology.json").read_bytes(),
                             (root / "accept-source/gpt-gateway-topology.json").read_bytes())

    def test_dashboard_generator_emits_plan_port_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            result = subprocess.run([sys.executable, str(ROOT / "observability/ns2604_dashboards.py"),
                                     "--plan-dir", str(root)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue("@PORT_AGENTSVIEW@" in (root / "config/grafana-command-center.json").read_text(),
                            "dashboard output lacks the host port marker")

    def test_custom_gateway_preserves_composition_wrapper_and_moves_its_unit(self):
        renderer = module(PLAN / "config/observability_config.py", "gateway_ports")
        ports = renderer.service_ports({"NS_PORT_GATEWAY": "31128"})
        wrapper = renderer.render_asset("omniroute-serve.sh", (PLAN / "config/omniroute-serve.sh").read_text(), ports)
        self.assertIn("serve --port 31128", wrapper)
        expected = hashlib.sha256(wrapper.encode()).hexdigest()
        command = renderer.render_command(
            "672063a12174d46f7065ae7bb9adf1ed268c958cd264f64a25d0af3f74ae45bc wrapper", ports)
        self.assertEqual(command, expected + " wrapper")
        unit = renderer.render_asset("omniroute.service", (PLAN / "config/omniroute.service").read_text(), ports)
        self.assertIn("Environment=PORT=31128\n", unit)
        self.assertNotIn("Environment=PORT=21128\n", unit)

    def test_checker_rejects_literal_service_ports(self):
        checker = module(PLAN / "check_plan.py", "literal_check")
        rows = json.loads((PLAN / "install-plan.json").read_text())["owners"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config/observability_config.py").write_text((PLAN / "config/observability_config.py").read_text())
            for literal in ("21318", "32123"):
                (root / "config/rogue.yaml").write_text("endpoint: 127.0.0.1:" + literal + "\n")
                errors = []
                checker.host_port_contract(root, rows, None, lambda tag, msg: errors.append(msg))
                self.assertTrue(any("literal service port" in e for e in errors), errors)

    def test_command_render_swaps_ports_without_cascading(self):
        renderer = module(PLAN / "config/observability_config.py", "command_ports")
        ports = renderer.service_ports({"NS_PORT_GATEWAY": "21080", "NS_PORT_DAGU": "21128"})
        self.assertEqual(renderer.render_command("http://127.0.0.1:21128 http://127.0.0.1:21080 @PORT_DAGU@", ports),
                         "http://127.0.0.1:21080 http://127.0.0.1:21128 21128")

    def test_default_host_renders_the_baseline_config_bytes(self):
        renderer = module(PLAN / "config/observability_config.py", "plan_ports")
        host = json.loads((ROOT / "adoption/templates/wsl/host.new-distro.json.template").read_text())
        ports = renderer.service_ports(host)
        fixture = json.loads((ROOT / "tests/fixtures/install_plan_default_ports.json").read_text())
        for entry in fixture["files"]:
            name, expected = entry["path"], entry["sha256"]
            if entry.get("comparison") == "native_export":
                self.assertEqual(name, "promptfoo-gateway.cjs")
                continue  # Its recorded source correction has a native export-equivalence regression.
            with self.subTest(config=name):
                rendered = renderer.render_ports((PLAN / "config" / name).read_text(), ports)
                self.assertEqual(hashlib.sha256(rendered.encode()).hexdigest(), expected)

    def test_host_ports_reach_collector_bindings_and_cross_service_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host = root / "host.json"
            host.write_text(json.dumps(host_allocation({"NS_PORT_OTEL_HTTP": "31318", "NS_PORT_OTEL_GRPC": "31317",
                                        "NS_PORT_GATEWAY": "31128", "NS_PORT_LOKI_HTTP": "31300"})))
            out = root / "render"
            out.mkdir()
            result = subprocess.run([sys.executable, str(PLAN / "config/observability_config.py"), "otel",
                                     "--config-root", str(out), "--source-root", str(PLAN / "config"),
                                     "--host-file", str(host)], text=True, capture_output=True,
                                    env={"PATH": "/usr/bin:/bin", "HOME": tmp})
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (out / "otel.yaml").read_text()
            for endpoint in ("127.0.0.1:31318", "127.0.0.1:31317", "127.0.0.1:31128/api/health",
                             "127.0.0.1:31300/otlp"):
                self.assertIn(endpoint, text)
            self.assertNotRegex(text, r"127\.0\.0\.1:(21318|21317|21128|21300)\b")

    def test_two_rows_cannot_claim_the_same_port(self):
        renderer = module(PLAN / "config/observability_config.py", "plan_ports")
        self.assertTrue(hasattr(renderer, "service_ports"), "plan has no host-port validation")
        with self.assertRaisesRegex(ValueError, "claimed"):
            renderer.service_ports({"NS_PORT_GATEWAY": "31080", "NS_PORT_DAGU": "31080"})


class CitationAuditTests(unittest.TestCase):
    def test_live_locators_and_dated_history_remain_distinct(self):
        audit = json.loads((PLAN / "no-start-citation-audit.json").read_text())
        for row in audit["locators"]:
            line = (PLAN / row["script"]).read_text().splitlines()[row["current_line"] - 1]
            self.assertEqual(hashlib.sha256(line.encode()).hexdigest(), row["anchor_sha256"])
        history = audit["dated_history"]
        self.assertEqual(hashlib.sha256((ROOT / history["path"]).read_bytes()).hexdigest(), history["sha256"])


class ReviewWave1Tests(unittest.TestCase):
    def test_dagu_preserves_native_bootstrap_unless_no_start_is_selected(self):
        source = (PLAN / "install.sh").read_text()
        parser = "only=''" + source.split("only=''", 1)[1].split("\ndone\n", 1)[0] + "\ndone\n"
        for args, expected in (([], "yes"), (["--no-start"], "no")):
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", parser + 'printf "%s" "$dagu_service_mode"',
                                     "fixture", *args], env={"PATH": "/usr/bin:/bin"}, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, expected)
        checker = module(PLAN / "check_plan.py", "wave_dagu_bootstrap")
        commands = checker.run_commands("dagu", checker.functions(source), set())
        self.assertLess(next(i for i, command in enumerate(commands) if "20-ns2604-coordinator.conf" in command),
                        next(i for i, command in enumerate(commands) if "scripts/installer.sh" in command))

    def test_checker_lists_the_transitive_docker_lifecycle(self):
        checker = module(PLAN / "check_plan.py", "wave_inventory")
        source = (PLAN / "install.sh").read_text()
        inventory = checker.transitive_service_inventory(checker.functions(source), source)
        self.assertEqual({entry["selected_row"] for entry in inventory},
                         {"docker-compose", "harbor-containerized-agent-e2e-runner"})
        for entry in inventory:
            self.assertEqual(entry["dependency"], "container-engine")
            self.assertEqual({step["kind"] for step in entry["steps"]},
                             {"package_install", "rootless_setup", "unit_registration", "activation"})

    def test_no_start_covers_both_docker_dependency_selections(self):
        checker = module(PLAN / "check_plan.py", "wave_dependency_check")
        reference = os.environ.get("NS_TEST_INSTALL_REF")
        source = (subprocess.check_output(["git", "show", reference + ":" + str((PLAN / "install.sh").relative_to(ROOT))],
                                         cwd=ROOT, text=True) if reference else (PLAN / "install.sh").read_text())
        functions = checker.functions(source)
        dependency_selection = next(line for line in source.splitlines()
                                    if line.startswith("for slot in ") and "needs_docker=true" in line)
        dependency_dispatch = re.search(
            r"^if \$needs_docker \|\| selected container-engine; then\n  run_slot container-engine\n.*?(?=^if \$needs_docker \|\| selected docker-compose;)",
            source, re.M | re.S)[0]
        cases = ((row, present) for row in ("docker-compose", "harbor-containerized-agent-e2e-runner")
                 for present in (False, True))
        for selected_row, existing in cases:
            with self.subTest(row=selected_row, existing=existing), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "config").mkdir()
                (root / "config/.service-ports.json").write_text(json.dumps(host_allocation()))
                unit = root / ".config/systemd/user/docker.service"
                if existing:
                    unit.parent.mkdir(parents=True)
                    unit.write_text("fixture pre-existing unit\n")
                names = ("selected", "copy_config", "run_command", "activate_user_unit", "register_service_row",
                         "container-engine", "docker_engine_packages", "run_slot")
                definitions = "\n".join(name + "() {\n" + functions[name] + "\n}" for name in names if name in functions)
                script = definitions + '\n' + (
                    'systemctl() { printf "CALL %s\\n" "$*"; };\n'
                    'sudo() { printf "ROOT %s\\n" "$*"; '
                    'if [[ "$*" == "systemctl mask docker.service docker.socket containerd.service" ]]; then '
                    ': > "$HOME/.package-units-masked"; '
                    'elif [[ "$1" == apt-get && ! -f "$HOME/.package-units-masked" ]]; then printf "PACKAGE_START\\n"; fi; };\n'
                    'docker_repository() { :; }; apt_release_version() { printf fixture; };\n'
                    'dockerd-rootless-setuptool.sh() { printf "SETUP\\n"; mkdir -p "$HOME/.config/systemd/user"; '
                    'printf "fixture setup unit\\n" > "$HOME/.config/systemd/user/docker.service"; };\n'
                    'export -f systemctl sudo docker_repository docker_engine_packages apt_release_version dockerd-rootless-setuptool.sh\n'
                    'if declare -F activate_user_unit >/dev/null; then export -f activate_user_unit; fi\n'
                    'needs_docker=false; failed=0; last_rc=0\n'
                ) + 'only=' + shlex.quote(selected_row) + '\n' + dependency_selection + '\n' + dependency_dispatch
                result = subprocess.run(["bash", "-euo", "pipefail", "-c", script], text=True, capture_output=True,
                    env={"PATH": "/usr/bin:/bin", "HOME": tmp, "XDG_RUNTIME_DIR": str(root / "run"),
                         "NS2604_NO_START": "1", "plan_dir": str(PLAN), "config_root": str(root / "config"),
                         "config_source_root": str(PLAN / "config"), "tool_root": str(root / "tools")})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("container-engine | install | 0", result.stdout)
                self.assertIn("ROOT apt-get install", result.stdout)
                self.assertNotRegex(result.stdout, r"\b(enable|start|restart|SETUP|PACKAGE_START)\b")
                self.assertIn("CALL --user daemon-reload", result.stdout)
                self.assertTrue(unit.is_file())

    def test_native_research_command_carries_the_host_file_explicitly(self):
        checker = module(PLAN / "check_plan.py", "wave_native_research")
        body = checker.functions((PLAN / "accept.sh").read_text())["research-harnesses"]
        program = next(p for stage, _, _, p in checker.checks_of(body) if stage == "after_sign_in")
        assignment = next(line for line in program.splitlines() if "printf -v gpt_command " in line)
        with tempfile.TemporaryDirectory() as tmp:
            host = str(Path(tmp) / "host values.json")
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", assignment + '\nprintf "%s" "$gpt_command"'],
                text=True, capture_output=True, env={"PATH": "/usr/bin:/bin", "client_state": tmp,
                    "repo_root": str(ROOT), "NS2604_HOST_FILE": host, "gpt_marker": "fixture-complete"})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("NS2604_HOST_FILE=" + host, shlex.split(result.stdout))

    def test_plan_rejects_a_foreign_listener_in_a_supplied_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host, snapshot = root / "host.json", root / "ss.txt"
            snapshot.write_text("LISTEN 0 128 127.0.0.1:21128 0.0.0.0:*\n")
            for moved in (False, True):
                host.write_text(json.dumps(host_allocation({"NS_PORT_GATEWAY": "31128"} if moved else {})))
                result = subprocess.run([sys.executable, str(PLAN / "check_plan.py"), "--host-file", str(host),
                                         "--ss-output", str(snapshot)], text=True, capture_output=True)
                self.assertEqual(result.returncode, 0 if moved else 1, result.stderr)
                if not moved:
                    self.assertIn("21128 foreign", result.stdout)

    def test_cited_acceptance_programs_use_host_ports(self):
        renderer = module(PLAN / "config/observability_config.py", "wave_accept_ports")
        checker = module(PLAN / "check_plan.py", "wave_accept_check")
        functions = checker.functions((PLAN / "accept.sh").read_text())
        ports = renderer.service_ports({"NS_PORT_MEMORY": "39374", "NS_PORT_ALERTMANAGER": "31093",
                                        "NS_PORT_PROMETHEUS": "31090", "NS_PORT_GATEWAY": "31128"})
        for slot, stage, expected in (("memory-owner", "service_health", "39374"),
                                      ("alerting", "service_health", "31093"),
                                      ("alerting", "after_sign_in", "31090"),
                                      ("gpt-gateway", "service_health", "31128"),
                                      ("research-harnesses", "post_install", "31128")):
            with self.subTest(slot=slot, stage=stage):
                program = next(p for s, _, _, p in checker.checks_of(functions[slot]) if s == stage)
                rendered = renderer.render_command(program, ports)
                self.assertIn("127.0.0.1:" + expected, rendered)
                self.assertNotRegex(rendered, r"127\.0\.0\.1:(29374|21093|21090|21128)\b")

    def test_all_gateway_listeners_move_and_require_visible_owners(self):
        renderer = module(PLAN / "config/observability_config.py", "wave_ws_ports")
        ports = renderer.service_ports({"NS_PORT_GATEWAY": "41128", "NS_PORT_GATEWAY_WS": "41129",
                                        "NS_PORT_GATEWAY_EMBED_WS": "41131"})
        unit = renderer.render_ports((PLAN / "config/omniroute.service").read_text(), ports)
        self.assertIn("Environment=PORT=41128\n", unit)
        self.assertIn("Environment=LIVE_WS_PORT=41129\n", unit)
        self.assertIn("Environment=EMBED_WS_PROXY_PORT=41131\n", unit)
        plan = json.loads((PLAN / "install-plan.json").read_text())
        expected = renderer.planned_listeners(plan, ports, "gpt-gateway")
        self.assertEqual(set(expected), {41128, 41129, 41131})
        owned = lambda port: f'LISTEN 0 128 127.0.0.1:{port} 0.0.0.0:* users:(("fixture",pid=42,fd=3))\n'
        self.assertEqual(renderer.listener_ownership(plan, ports, "".join(owned(p) for p in expected), "gpt-gateway"), [])
        errors = renderer.listener_ownership(plan, ports, owned(41128) + "LISTEN 0 128 127.0.0.1:41129 0.0.0.0:*\n", "gpt-gateway")
        self.assertTrue(any("41129 foreign" in error for error in errors))
        self.assertTrue(any("41131 absent" in error for error in errors))
        with self.assertRaisesRegex(ValueError, "claimed"):
            renderer.service_ports({"NS_PORT_GATEWAY_WS": "41129", "NS_PORT_DAGU": "41129"})

    def test_default_stage_s_enumerates_fifteen_planned_listeners(self):
        renderer = module(PLAN / "config/observability_config.py", "wave_all_ports")
        plan = json.loads((PLAN / "install-plan.json").read_text())
        self.assertEqual(len(renderer.planned_listeners(plan, renderer.service_ports())), 15)

    def test_foreign_listener_stops_the_acceptance_program(self):
        checker = module(PLAN / "check_plan.py", "wave_gate_check")
        body = checker.functions((PLAN / "accept.sh").read_text())["check"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bin").mkdir()
            (root / "config").mkdir()
            sudo = root / "bin/sudo"
            sudo.write_text('#!/bin/sh\n[ "$*" = "ss -ltnpH" ] || exit 99\nprintf "%s\\n" "LISTEN 0 128 127.0.0.1:29374 0.0.0.0:*"\n')
            sudo.chmod(0o755)
            script = ('stage=service_health; failed=0; port_args=(); prepare_path() { :; };\ncheck() {\n'
                      + body + '\n}\ncheck memory-owner health ' + shlex.quote('touch "$config_root/probe-ran"')
                      + '\nexit "$failed"')
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", script], text=True, capture_output=True,
                env={"PATH": str(root / "bin") + ":/usr/bin:/bin", "plan_dir": str(PLAN),
                     "config_root": str(root / "config"), "config_source_root": str(root / "config")})
            self.assertEqual(result.returncode, 1)
            self.assertIn("foreign", result.stderr)
            self.assertFalse((root / "config/probe-ran").exists())

    def test_runtime_profiles_reads_the_host_gateway(self):
        with tempfile.TemporaryDirectory() as tmp:
            host = Path(tmp) / "host.json"
            host.write_text(json.dumps(host_allocation({"NS_PORT_GATEWAY": "41128"})))
            with mock.patch.dict(os.environ, {"NS2604_HOST_FILE": str(host)}):
                profiles = module(ROOT / "tools/adoption/runtime_profiles.py", "wave_runtime_profiles")
            self.assertEqual(profiles.GATEWAY, "http://127.0.0.1:41128/v1")

    def test_research_helper_uses_the_host_gateway_before_scrubbing(self):
        from tests import test_research_entry
        fixture = test_research_entry.ResearchEntry()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.provide_timer()
        host = fixture.temp / "host.json"
        host.write_text(json.dumps(host_allocation({"NS_PORT_GATEWAY": "41128"})))
        fixture.env["NS2604_HOST_FILE"] = str(host)
        result = fixture.run_script("fixture research query")
        self.assertEqual(result.returncode, 0, result.stderr)
        run = fixture.run_dir(result)
        self.assertEqual(json.loads((run / "config.json").read_text())["LLM_KWARGS"]["base_url"],
                         "http://127.0.0.1:41128/v1")
        self.assertEqual(json.loads((run / "cli-call.json").read_text())["env"]["OPENAI_BASE_URL"],
                         "http://127.0.0.1:41128/v1")

    def ownership(self, text):
        renderer = module(PLAN / "config/observability_config.py", "listener_ports")
        self.assertTrue(hasattr(renderer, "listener_ownership"), "stage-S ownership gate is absent")
        plan = json.loads((PLAN / "install-plan.json").read_text())
        ports = renderer.service_ports({"NS_PORT_MEMORY": "39374"})
        return renderer.listener_ownership(plan, ports, text, slot="memory-owner")

    def test_owned_listener_has_visible_process(self):
        self.assertEqual(self.ownership('LISTEN 0 128 127.0.0.1:39374 0.0.0.0:* users:(("ai-memory",pid=42,fd=3))\n'), [])

    def test_foreign_listener_is_rejected(self):
        self.assertTrue(any("foreign" in error for error in self.ownership('LISTEN 0 128 127.0.0.1:39374 0.0.0.0:*\n')))

    def test_absent_listener_is_rejected(self):
        self.assertTrue(any("absent" in error for error in self.ownership('LISTEN 0 128 127.0.0.1:49374 0.0.0.0:* users:(("other",pid=42,fd=3))\n')))


class ReviewWave2Tests(unittest.TestCase):
    def test_reserved_and_metrics_ports_remain_in_the_collision_set(self):
        renderer = module(PLAN / "config/observability_config.py", "wave2_reserved_collisions")
        for key in ("CODE_GRAPH_UI", "GRAFANA_GRPC", "OTEL_METRICS", "OTEL_EXPORTER"):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "claimed"):
                renderer.service_ports({"NS_PORT_GATEWAY": str(renderer.SERVICE_PORTS[key][1])})

    def test_clients_accept_the_plans_memory_gateway_allocation(self):
        from tests import test_new_wsl_client_config as fixtures
        cfg = fixtures.cfg
        values = json.loads((ROOT / "adoption/hosts/example.json").read_text())
        values.update(AI_MEMORY_URL="127.0.0.1:39374", NS_PORT_GATEWAY="29374")
        plan = cfg.load_plan(ROOT)
        with mock.patch.object(fixtures.render_config, "load_host_values", return_value=values):
            resolved = cfg.host_values("fixture", plan, None, [])
        results, manifest, _, errors, _ = cfg.analyse(ROOT)
        self.assertEqual(errors, [])
        files = cfg.render(ROOT, results, plan, resolved, manifest)
        self.assertIn("127.0.0.1:39374", files["mcp-servers.json"])
        self.assertIn("127.0.0.1:39374", files["codex.config.toml"])
        self.assertIn("127.0.0.1:29374/v1", files["codex.omniroute.config.toml"])

    def test_isolated_host_modes_refuse_missing_port_keys(self):
        renderer = module(PLAN / "config/observability_config.py", "wave2_required_ports")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host = root / "partial.json"
            host.write_text(json.dumps({"NS_PORT_GATEWAY": "41128"}))
            with self.assertRaisesRegex(ValueError, "missing"):
                renderer.load_service_ports(host, root)
            with mock.patch.dict(os.environ, {"NS2604_NO_START": "1"}):
                with self.assertRaisesRegex(ValueError, "missing"):
                    renderer.load_service_ports(None, root)

    def allocation_setup(self, root, extra=""):
        checker = module(PLAN / "check_plan.py", "wave2_transaction_check")
        source = (PLAN / "install.sh").read_text()
        funcs = checker.functions(source)
        names = ("stage_plan_sources", "commit_allocation", "run_command")
        definitions = "\n".join(name + "() {\n" + funcs[name] + "\n}" for name in names if name in funcs)
        if "stage_plan_sources" in funcs:
            staging = "stage_plan_sources"
        else:
            staging = source[source.index('config_source_root="$(mktemp -d)"'):source.index("# Planned. Package prerequisites")]
        script = definitions + "\n" + staging + "\n" + extra
        return subprocess.run(["bash", "-euo", "pipefail", "-c", script], text=True, capture_output=True,
            env={"PATH": "/usr/bin:/bin", "HOME": str(root), "plan_dir": str(PLAN),
                 "config_root": str(root / "config"), "config_source_root": str(PLAN / "config"),
                 "host_file": str(root / "B.json"), "NS2604_HOST_FILE": str(root / "A.json")})

    def allocation_fixture(self, root):
        (root / "config").mkdir()
        original = json.dumps(host_allocation({"NS_PORT_GATEWAY": "31128"}))
        (root / "A.json").write_text(original)
        (root / "B.json").write_text(json.dumps(host_allocation({"NS_PORT_GATEWAY": "41128"})))
        (root / "config/.service-ports.json").write_text(original)
        return original

    def test_failed_install_keeps_the_published_allocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = self.allocation_fixture(root)
            result = self.allocation_setup(root, 'failed=1; needs_execution=true; if declare -F commit_allocation >/dev/null; then commit_allocation; fi; exit "$failed"')
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(json.loads((root / "config/.service-ports.json").read_text())["NS_PORT_GATEWAY"], "31128")
            self.assertEqual((root / "config/.service-ports.json").read_text(), original)

    def test_explicit_host_file_wins_inherited_selection_for_all_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.allocation_fixture(root)
            result = self.allocation_setup(root,
                'run_command \'printf "%s\\n" http://127.0.0.1:21128/v1\'\n'
                'failed=0; needs_execution=true; commit_allocation\n'
                'run_command \'python3 "$plan_dir/config/observability_config.py" gateway --config-root "$config_root"\'')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), ["http://127.0.0.1:41128/v1"] * 2)

    def test_ollama_readiness_uses_the_allocated_endpoint(self):
        checker = module(PLAN / "check_plan.py", "wave2_ollama")
        body = checker.functions((PLAN / "install.sh").read_text())["model_server_answers"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config/.service-ports.json").write_text(json.dumps(host_allocation({"NS_PORT_OLLAMA": "31434"})))
            script = ('ollama() { [[ "$OLLAMA_HOST" == 127.0.0.1:31434 ]]; }; '
                      'curl() { [[ "$*" == *"http://127.0.0.1:31434/api/version"* ]] || return 99; printf "{}"; }; '
                      'jq() { printf 0.35.0; };\nmodel_server_answers() {\n' + body + '\n}\nmodel_server_answers')
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", script], text=True, capture_output=True,
                env={"PATH": "/usr/bin:/bin", "plan_dir": str(PLAN), "config_root": str(root / "config")})
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_disabled_grafana_grpc_is_not_a_required_listener(self):
        renderer = module(PLAN / "config/observability_config.py", "wave2_optional")
        plan = json.loads((PLAN / "install-plan.json").read_text())
        text = 'LISTEN 0 128 127.0.0.1:21301 0.0.0.0:* users:(("grafana",pid=42,fd=3))\n'
        self.assertEqual(renderer.listener_ownership(plan, renderer.service_ports(), text, "grafana"), [])
        enabled = renderer.listener_ownership(plan, renderer.service_ports(), text, "grafana",
                                             enabled_optional={"GRAFANA_GRPC"})
        self.assertTrue(any("21302 absent" in error for error in enabled))
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)
            (config / "grafana.ini").write_text("[grpc_server]\nenabled = true\naddress = 127.0.0.1:21302\n")
            self.assertIn("GRAFANA_GRPC", renderer.configured_optional_listeners(config))

    def test_enabled_grafana_grpc_requires_its_moved_owned_listener(self):
        renderer = module(PLAN / "config/observability_config.py", "wave2_enabled_grpc")
        plan = json.loads((PLAN / "install-plan.json").read_text())
        ports = renderer.service_ports({"NS_PORT_GRAFANA_HTTP": "31301", "NS_PORT_GRAFANA_GRPC": "31302"})
        http = 'LISTEN 0 128 127.0.0.1:31301 0.0.0.0:* users:(("grafana",pid=42,fd=3))\n'
        grpc = 'LISTEN 0 128 127.0.0.1:31302 0.0.0.0:* users:(("grafana",pid=42,fd=4))\n'
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)
            (config / "grafana.ini").write_text("[grpc_server]\nenabled = true\naddress = 127.0.0.1:31302\n")
            enabled = renderer.configured_optional_listeners(config)
            self.assertEqual(renderer.listener_ownership(plan, ports, http, "grafana", enabled_optional=enabled),
                             ["grafana/GRAFANA_GRPC: port 31302 absent"])
            self.assertEqual(renderer.listener_ownership(plan, ports, http + grpc, "grafana", enabled_optional=enabled), [])
            errors = renderer.listener_ownership(plan, ports, http + grpc.split(" users:", 1)[0] + "\n",
                                                "grafana", enabled_optional=enabled)
            self.assertTrue(any("31302" in error and "foreign" in error for error in errors), errors)

    def test_codex_host_identity_is_explicit_and_required_for_direct_render(self):
        from tests import test_new_wsl_client_config as fixtures
        cfg = fixtures.cfg
        values = json.loads((ROOT / "adoption/hosts/example.json").read_text())
        values["WSL_DISTRO_NAME"] = "NativeHorizonNY"
        plan = cfg.load_plan(ROOT)
        results, manifest, _, errors, _ = cfg.analyse(ROOT)
        self.assertEqual(errors, [])
        with mock.patch.object(fixtures.render_config, "load_host_values", return_value=values):
            resolved = cfg.host_values("fixture", plan, None, [])
        import tomllib
        config = tomllib.loads(cfg.render(ROOT, results, plan, resolved, manifest)["codex.config.toml"])
        self.assertEqual(config["shell_environment_policy"]["set"]["WSL_DISTRO_NAME"], "NativeHorizonNY")
        for missing in (None, "", "  "):
            with self.subTest(missing=missing):
                resolved["WSL_DISTRO_NAME"] = missing
                with self.assertRaisesRegex(cfg.ConfigError, "WSL_DISTRO_NAME"):
                    cfg.render(ROOT, results, plan, resolved, manifest)

    def test_code_graph_has_an_explicit_disabled_ui_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config"
            config.mkdir()
            host = root / "host.json"
            host.write_text(json.dumps(host_allocation({"NS_PORT_CODE_GRAPH_UI": "19749"})))
            result = subprocess.run([sys.executable, str(PLAN / "config/observability_config.py"), "code-graph",
                "--config-root", str(config), "--source-root", str(PLAN / "config"), "--host-file", str(host)],
                env={"PATH": "/usr/bin:/bin", "HOME": tmp}, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads((root / ".cache/codebase-memory-mcp/config.json").read_text()),
                             {"ui_enabled": False, "ui_port": 19749})

    def test_code_graph_port_owner_and_legacy_allocation_are_consistent(self):
        renderer = module(PLAN / "config/observability_config.py", "wave2_graph_owner")
        self.assertEqual(renderer.SERVICE_PORTS["CODE_GRAPH_UI"], ("code-graph", 9749))
        self.assertEqual(renderer.service_ports({"NS_PORT_TRACE_VIEWER": "19749"})["CODE_GRAPH_UI"], 19749)
        with self.assertRaisesRegex(ValueError, "disagree"):
            renderer.service_ports({"NS_PORT_TRACE_VIEWER": "9749", "NS_PORT_CODE_GRAPH_UI": "19749"})

    def test_code_graph_preserves_conflicting_operator_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config"
            config.mkdir()
            target = root / ".cache/codebase-memory-mcp/config.json"
            target.parent.mkdir(parents=True)
            for value in ({"ui_enabled": True, "ui_port": 9749}, {"ui_enabled": False, "ui_port": 9749.0}):
                original = json.dumps(value)
                target.write_text(original)
                result = subprocess.run([sys.executable, str(PLAN / "config/observability_config.py"), "code-graph",
                    "--config-root", str(config), "--source-root", str(PLAN / "config")],
                    env={"PATH": "/usr/bin:/bin", "HOME": tmp}, text=True, capture_output=True)
                self.assertEqual(result.returncode, 1)
                self.assertIn("needs_owner", result.stderr)
                self.assertEqual(target.read_text(), original)

    def test_dagu_coordinator_and_agentsview_ports_are_host_selected(self):
        renderer = module(PLAN / "config/observability_config.py", "wave2_auxiliary_ports")
        ports = renderer.service_ports({"NS_PORT_DAGU_COORDINATOR": "25055", "NS_PORT_AGENTSVIEW": "31808"})
        coordinator = renderer.render_ports((PLAN / "config/dagu-coordinator.conf").read_text(), ports)
        self.assertIn("DAGU_COORDINATOR_PORT=25055", coordinator)
        archive = renderer.render_ports(self.source("config/agentsview.toml"), ports)
        self.assertIn("port = 31808", archive)
        plan = json.loads((PLAN / "install-plan.json").read_text())
        self.assertIn(25055, renderer.planned_listeners(plan, ports, "dagu"))
        self.assertIn(31808, renderer.planned_listeners(plan, ports, "session-analytics"))

    def test_existing_ui_configuration_is_not_an_installation_target(self):
        renderer = module(PLAN / "config/observability_config.py", "wave2_optional_ui")
        plan = json.loads((PLAN / "install-plan.json").read_text())
        ports = renderer.service_ports({"NS_PORT_CODE_GRAPH_UI": "19749"})
        self.assertNotIn(19749, renderer.planned_listeners(plan, ports))
        enabled = renderer.planned_listeners(plan, ports, "code-graph", enabled_optional={"CODE_GRAPH_UI"})
        self.assertEqual(enabled, {19749: "code-graph/CODE_GRAPH_UI"})

    def test_agentsview_conflicting_archive_port_blocks_publication(self):
        checker = module(PLAN / "check_plan.py", "wave2_agentsview_custody")
        funcs = checker.functions((PLAN / "install.sh").read_text())
        command = next(c for c in checker.run_commands("session-analytics", funcs, set())
                       if 'd="${XDG_DATA_HOME' in c)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config/agentsview.toml").write_text("port = 31808\n")
            target = root / "data/new-wsl-native-stack/agentsview/config.toml"
            target.parent.mkdir(parents=True)
            target.write_text("port = 21808\n")
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", command],
                env={"PATH": "/usr/bin:/bin", "HOME": tmp, "plan_dir": tmp, "XDG_DATA_HOME": str(root / "data")},
                text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0, result.stderr)
            self.assertIn("needs_owner", result.stderr)
            self.assertEqual(target.read_text(), "port = 21808\n")

    def test_successful_install_publishes_candidate_only_at_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = self.allocation_fixture(root)
            result = self.allocation_setup(root,
                'cmp -s "$config_root/.service-ports.json" "$HOME/A.json"\n'
                'failed=0; needs_execution=true; commit_allocation')
            self.assertEqual(result.returncode, 0, result.stderr)
            current = json.loads((root / "config/.service-ports.json").read_text())
            self.assertEqual(current["NS_PORT_GATEWAY"], "41128")
            self.assertNotEqual((root / "config/.service-ports.json").read_text(), original)

    def test_inspector_is_rendered_before_the_frozen_recipe_hash(self):
        checker = module(PLAN / "check_plan.py", "wave2_freeze")
        body = checker.functions((PLAN / "accept.sh").read_text())["mcp-inspector"]
        program = next(p for stage, _, _, p in checker.checks_of(body) if stage == "after_sign_in")
        freeze = program[program.index('python3 "$plan_dir/config/observability_config.py" command'):program.index("for client in claude codex;")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "session").mkdir()
            host = root / "host.json"
            host.write_text(json.dumps(host_allocation({"NS_PORT_INSPECTOR_PROBE": "26399"})))
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", freeze + '\nprintf "%s" "$probe_sha"'],
                env={"PATH": "/usr/bin:/bin", "plan_dir": str(PLAN), "config_root": str(root / "config"),
                     "session": str(root / "session"), "NS2604_HOST_FILE": str(host)}, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            rendered = (root / "session/probe.sh").read_bytes()
            self.assertEqual(result.stdout, hashlib.sha256(rendered).hexdigest())
            self.assertIn(b"CLIENT_PORT=26399", rendered)

    def test_checker_rejects_literal_probe_and_closed_fixture_ports(self):
        checker = module(PLAN / "check_plan.py", "wave2_literal")
        rows = json.loads((PLAN / "install-plan.json").read_text())["owners"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config/observability_config.py").write_text((PLAN / "config/observability_config.py").read_text())
            (root / "inspector-client-probe.sh").write_text("curl http://127.0.0.1:16399/\n")
            (root / "config/prometheus-alerts.test.yaml").write_text('targets: ["127.0.0.1:21997"]\n')
            errors = []
            checker.host_port_contract(root, rows, None, lambda tag, msg: errors.append(msg))
            self.assertTrue(any("inspector-client-probe.sh: literal" in error for error in errors), errors)
            self.assertTrue(any("prometheus-alerts.test.yaml: literal" in error for error in errors), errors)

    def source(self, relative):
        reference = os.environ.get("NS_TEST_CONFIG_REF")
        path = PLAN / relative
        if reference:
            return subprocess.check_output(["git", "show", reference + ":" + str(path.relative_to(ROOT))], cwd=ROOT, text=True)
        return path.read_text()

    def test_grafana_grpc_and_gateway_consumers_follow_host_values(self):
        renderer = module(PLAN / "config/observability_config.py", "wave2_config_ports")
        ports = renderer.service_ports({"NS_PORT_GRAFANA_GRPC": "31302", "NS_PORT_GATEWAY": "31128"})
        for name, expected in (("grafana.ini", "127.0.0.1:31302"),
                               ("deer-flow-config.yaml", "127.0.0.1:31128/v1"),
                               ("openhands-job.json", "127.0.0.1:31128/v1")):
            with self.subTest(asset=name):
                rendered = renderer.render_ports(self.source("config/" + name), ports)
                self.assertIn(expected, rendered)

    def test_inspector_probe_port_is_host_selected(self):
        renderer = module(PLAN / "config/observability_config.py", "wave2_inspector_ports")
        ports = renderer.service_ports({"NS_PORT_INSPECTOR_PROBE": "26399"})
        rendered = renderer.render_ports(self.source("inspector-client-probe.sh"), ports)
        self.assertIn("CLIENT_PORT=26399", rendered)
        self.assertIn("http://127.0.0.1:26399/", rendered)
        self.assertIn("sport = :26399", rendered)
        self.assertNotIn("16399", rendered)

    def test_closed_alert_port_has_its_own_predicate(self):
        renderer = module(PLAN / "config/observability_config.py", "wave2_closed_ports")
        checker = module(PLAN / "check_plan.py", "wave2_closed_check")
        ports = renderer.service_ports({"NS_PORT_ALERT_CLOSED": "26397"})
        body = checker.functions((PLAN / "accept.sh").read_text())["alerting"]
        program = renderer.render_command(next(p for stage, _, _, p in checker.checks_of(body) if stage == "after_sign_in"), ports)
        start = program.index("import socket\nimport subprocess\n")
        predicate = program[start:program.index("\nPY", start)]
        for errno, listeners in ((111, ""), (0, ""), (111, "LISTEN foreign\n"), (111, 'LISTEN owned users:(("fixture",pid=42))\n')):
            with self.subTest(errno=errno, listeners=bool(listeners)), mock.patch("socket.socket") as sock, mock.patch("subprocess.run") as ss:
                sock.return_value.__enter__.return_value.connect_ex.return_value = errno
                ss.return_value.stdout = listeners
                if errno != 0 and not listeners:
                    exec(compile(predicate, "<closed-port-fixture>", "exec"), {})
                    sock.return_value.__enter__.return_value.connect_ex.assert_called_once_with(("127.0.0.1", 26397))
                    ss.assert_called_once_with(["ss", "-ltnH", "sport = :26397"], check=True, capture_output=True, text=True)
                else:
                    with self.assertRaises(AssertionError):
                        exec(compile(predicate, "<closed-port-fixture>", "exec"), {})
        plan = json.loads((PLAN / "install-plan.json").read_text())
        self.assertNotIn(26397, renderer.planned_listeners(plan, ports, "alerting", program))

    def test_probe_and_closed_ports_participate_in_collision_checks(self):
        renderer = module(PLAN / "config/observability_config.py", "wave2_collision")
        for key in ("NS_PORT_INSPECTOR_PROBE", "NS_PORT_ALERT_CLOSED"):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "claimed"):
                renderer.service_ports({key: "26399", "NS_PORT_GATEWAY": "26399"})


if __name__ == "__main__":
    unittest.main()
