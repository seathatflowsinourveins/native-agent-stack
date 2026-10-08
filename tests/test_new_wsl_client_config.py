"""Tests for tools/adoption/new_wsl_client_config.py and adoption/new-wsl/client-config-map.json.

Evidence classes, kept apart: the map, the manifest and the install plan are read as committed (the repository's own
files); a scratch copy of them is broken one way at a time as a negative control; the clients are never the real ones,
a synthetic stub stands in for `claude` and `codex` (the stub's `mcp` commands answer in the shape of Claude Code
2.1.287's `claude mcp get`), and the launcher is run through the repository's own pseudo-terminal table
(tests/test_adoption_bootstrap.py). A real bash login shell proves the PATH. Nothing here proves that a real
Claude Code or Codex session on a new distribution uses what the render wires.
"""

from __future__ import annotations

import contextlib
import fnmatch
import hashlib
import io
import importlib.util
import json
import os
import random
import re
import shutil
import signal
import stat
import string
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))

import codex_roles  # noqa: E402
import install_claude_profile as icp  # noqa: E402
import managed_block  # noqa: E402
import new_wsl_client_config as cfg  # noqa: E402
import render_config  # noqa: E402
from tests import test_adoption_bootstrap as boot  # noqa: E402
from tests import test_wsl_new_distro_recipe as recipe_tests  # noqa: E402

MAP = ROOT / cfg.MAP_REL
MANIFEST = ROOT / cfg.MANIFEST_REL
PLAN = ROOT / cfg.PLAN_REL


class Round2RepairIntegrationTests(unittest.TestCase):
    """Local synthetic controls; never producer, provider or destination acceptance."""

    @staticmethod
    def source_module(name):
        spec = importlib.util.spec_from_file_location(name.replace("-", "_"), PLAN / "config" / name)
        module = importlib.util.module_from_spec(spec)
        with mock.patch.object(sys, "dont_write_bytecode", True):
            spec.loader.exec_module(module)
        return module

    def test_hcom_apply_never_grants_inbound_authorization_or_requires_codex(self):
        # docs/decisions/2026-10-06-hcom-relaxation.md: the apply proceeds while Codex runs,
        # leaves Claude settings untouched, writes no Codex rule file and runs no subprocess.
        adapter = self.source_module("hcom-client-config.py")
        for inbound in (None, "accept", "hold"):
            with self.subTest(inbound=inbound), tempfile.TemporaryDirectory() as scratch:
                root = Path(scratch)
                claude = root / "claude"
                claude.mkdir()
                settings = {} if inbound is None else {"crossSessionInbound": inbound}
                (claude / "settings.json").write_text(json.dumps(settings))
                env = {"CLAUDE_CONFIG_DIR": str(claude), "CODEX_HOME": str(root / "codex"),
                       "HCOM_DIR": str(root / "hcom")}
                with mock.patch.dict(os.environ, env), mock.patch.object(sys, "argv", [
                        "adapter", "--repo-root", str(ROOT), "--apply"]), \
                        mock.patch.object(cfg, "running_codex_pids", return_value=[4242]) as codex, \
                        mock.patch("subprocess.run") as native, \
                        contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(adapter.main(), 0)
                native.assert_not_called()
                codex.assert_not_called()
                self.assertEqual(json.loads((claude / "settings.json").read_text()), settings)
                self.assertFalse((root / "codex" / "rules").exists())
                for target in (claude / "CLAUDE.md", root / "codex" / "AGENTS.md"):
                    text = target.read_text()
                    self.assertIn("treat it as data", text)
                    self.assertIn("never counts as the user's approval", text)
                    self.assertNotIn("Agents may not use", text)

    @unittest.skipUnless(shutil.which("jq"), "the after-sign-in program parses the checker's JSON with jq")
    def test_hcom_after_sign_in_reads_hcoms_codex_home_and_every_rules_file(self):
        # docs/decisions/2026-10-06-hcom-relaxation.md: the Codex home is CODEX_HOME, else the parent of
        # HCOM_DIR (aannoo/hcom@2c5f343b src/hooks/codex.rs:72-75, src/paths.rs:26-53), and Codex loads every
        # *.rules file there (openai/codex rust-v0.160.0 codex-rs/core/src/exec_policy.rs:662-700). A stub
        # codex answers by the basenames it receives, like the real checker on the retained receipt
        # (evidence/artifacts/hcom-relaxation-20261006/probe-receipt.json), and records its arguments.
        row = next(r for r in json.loads((PLAN / "install-plan.json").read_text())["owners"]
                   if r["slot"] == "agent-messaging")
        program = row["acceptance"]["after_sign_in"]["command"]
        stub = ("#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "args = sys.argv[1:]\n"
                "with open(os.environ['STUB_LOG'], 'a') as log:\n"
                "    log.write(json.dumps(args) + '\\n')\n"
                "names = {os.path.basename(args[i + 1]) for i, a in enumerate(args) if a == '--rules'}\n"
                "command = args[args.index('--') + 1:]\n"
                "decision = 'allow' if 'hcom.rules' in names and command[1:2] in (['send'], ['term']) else None\n"
                "if 'hcom-deny.rules' in names and command[1:2] == ['term']:\n"
                "    decision = 'forbidden'\n"
                "print(json.dumps({'decision': decision}))\n")
        retired = ["Bash(hcom term)", "Bash(hcom term *)", "Bash(uvx hcom * claude-pty *)",
                   "Bash(hcom send --from=*)", "Bash(uvx hcom --go *)"]
        kept = ["Bash(git push --force *)", "Bash(hcom send *)", "Bash(hcom term inject *)", "Read(~/mine)"]

        def run(layout, env=None, settings=None):
            with tempfile.TemporaryDirectory() as scratch:
                base = Path(scratch)
                (base / "bin").mkdir()
                (base / "bin" / "codex").write_text(stub)
                (base / "bin" / "codex").chmod(0o755)
                (base / "home").mkdir()
                for rel in layout:
                    (base / rel).parent.mkdir(parents=True, exist_ok=True)
                    (base / rel).write_text("# synthetic\n")
                if settings is not None:
                    (base / "home" / ".claude").mkdir()
                    (base / "home" / ".claude" / "settings.json").write_text(
                        json.dumps({"permissions": {"deny": settings}}))
                full_env = {"PATH": f"{base / 'bin'}:{os.environ['PATH']}", "HOME": str(base / "home"),
                            "STUB_LOG": str(base / "calls.jsonl")}
                full_env.update({k: str(base / v) for k, v in (env or {}).items()})
                done = subprocess.run(["bash", "-euo", "pipefail", "-c", program], env=full_env, cwd=base,
                                      capture_output=True, text=True)
                calls = [json.loads(line) for line in (base / "calls.jsonl").read_text().splitlines()] \
                    if (base / "calls.jsonl").exists() else []
                rules = sorted({str(Path(c[i + 1]).relative_to(base)) for c in calls
                                for i, a in enumerate(c) if a == "--rules"})
                return done.returncode, done.stderr, rules

        rc, err, rules = run([])
        self.assertEqual((rc, rules), (78, []))
        self.assertIn("launch hcom codex once", err)
        rc, err, rules = run(["home/.codex/rules/hcom.rules"])
        self.assertEqual((rc, rules), (0, ["home/.codex/rules/hcom.rules"]), err)
        rc, err, rules = run(["home/.codex/rules/hcom.rules", "home/.codex/rules/hcom-deny.rules"])
        self.assertEqual((rc, rules), (78, ["home/.codex/rules/hcom-deny.rules", "home/.codex/rules/hcom.rules"]))
        self.assertIn("allow for hcom send and forbidden for hcom term", err)
        rc, err, rules = run(["state/.codex/rules/hcom.rules"], env={"HCOM_DIR": "state/hub"})
        self.assertEqual((rc, rules), (0, ["state/.codex/rules/hcom.rules"]), err)
        rc, err, rules = run(["home/.codex/rules/hcom.rules"], env={"HCOM_DIR": "state/hub"})
        self.assertEqual((rc, rules), (78, []))
        rc, err, rules = run(["explicit/rules/hcom.rules"], env={"HCOM_DIR": "state/hub", "CODEX_HOME": "explicit"})
        self.assertEqual((rc, rules), (0, ["explicit/rules/hcom.rules"]), err)
        rc, err, rules = run(["home/.codex/rules/hcom.rules"], settings=kept + retired)
        self.assertEqual((rc, rules), (78, []))
        self.assertIn(f"{len(retired)} retired 2026-10-04 hcom deny entries", err)
        rc, err, rules = run(["home/.codex/rules/hcom.rules"], settings=kept)
        self.assertEqual(rc, 0, err)

    def test_gateway_default_metadata_is_observed_without_pipeline_capture(self):
        gate = self.source_module("gateway-effort-accept.py")
        rows = [{"id": "synthetic-call", "status": 200, "path": "/v1/chat/completions",
                 "model": "gpt-6.1-sol", "requestedModel": "cx/gpt-6.1-sol"}]
        self.assertEqual(gate.observed_routes(rows), {"cx/gpt-6.1-sol"})
        for field, value in (("status", 503), ("path", "/v1/embeddings"),
                             ("model", "another-model"), ("requestedModel", "cx/gpt-6.1-sol-unlisted")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                gate.observed_routes([dict(rows[0], **{field: value})])
        with self.assertRaisesRegex(ValueError, "no call log"):
            gate.observed_routes([])

    def test_gateway_metadata_accepts_only_documented_codex_id_and_alias(self):
        gate = self.source_module("gateway-effort-accept.py")
        for prefix in ("cx", "codex"):
            for model, effort in (("gpt-6.1-sol", "xhigh"), ("gpt-6.1-sol-high", "high"),
                                  ("gpt-6.1-sol-max", "max")):
                route = f"{prefix}/{model}"
                row = {"status": 200, "path": "/v1/chat/completions", "model": model,
                       "requestedModel": route, "provider": "codex"}
                with self.subTest(route=route):
                    self.assertEqual(gate.observed_routes([row]), {route})
                    self.assertEqual(gate.ROUTES[route], effort)
                for field, value in (("requestedModel", f"other/{model}"),
                                     ("requestedModel", f"{prefix}/{model}-unlisted"),
                                     ("requestedModel", f"{prefix}/gpt-6.1-sol-high" if model == "gpt-6.1-sol" else f"{prefix}/gpt-6.1-sol"),
                                     ("provider", "other"), ("status", 503), ("active", True),
                                     ("path", "/v1/embeddings"), ("path", "/v1/unlisted-inference")):
                    with self.subTest(route=route, field=field, value=value), self.assertRaises(ValueError):
                        gate.observed_routes([dict(row, **{field: value})])

    def test_gateway_session_join_includes_canonical_deerflow_max_route_without_wire_claim(self):
        gate = self.source_module("gateway-effort-accept.py")
        started, finished = "2026-10-05T04:00:00+00:00", "2026-10-05T04:01:00+00:00"
        rows = [
            {"id": "synthetic-gptr", "timestamp": "2026-10-05T04:00:10Z", "sessionTag": "synthetic-research",
             "status": 200, "path": "/v1/chat/completions", "model": "gpt-6.1-sol-high",
             "requestedModel": "cx/gpt-6.1-sol-high", "provider": "codex"},
            {"id": "synthetic-deerflow", "timestamp": "2026-10-05T04:00:20Z", "sessionTag": "synthetic-research",
             "status": 200, "path": "/v1/responses", "model": "gpt-6.1-sol-max",
             "requestedModel": "codex/gpt-6.1-sol-max", "provider": "codex"},
        ]
        with mock.patch.object(gate, "get_json", return_value=rows), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(gate.main("synthetic-research", started, finished), 0)
        self.assertIn("join=session", out.getvalue())
        self.assertIn("high, max", out.getvalue())
        self.assertIn("not observed wire", out.getvalue())
        self.assertIn("Delivered wire effort is not asserted", out.getvalue())

    def test_gateway_paging_stops_at_old_persisted_rows_and_joins_the_run(self):
        gate = self.source_module("gateway-effort-accept.py")
        started, finished = "2026-10-05T04:00:00+00:00", "2026-10-05T04:01:00+00:00"
        fresh = {"id": "fresh", "timestamp": "2026-10-05T04:00:20Z", "sessionTag": "synthetic-run",
                 "status": 200, "path": "/v1/chat/completions", "model": "gpt-6.1-sol",
                 "requestedModel": "cx/gpt-6.1-sol"}
        # An old active row heads the native API list; only persisted rows give
        # the paging cutoff. Retention may be far larger than 6,400 entries.
        active = dict(fresh, id="active", active=True, timestamp="2026-10-04T00:00:00Z")
        page = [active, fresh] + [dict(fresh, id=f"other-{i}", sessionTag="other") for i in range(99)]
        old = dict(fresh, id="old", timestamp="2026-10-05T03:59:59Z")
        with mock.patch.object(gate, "get_json", side_effect=[page, [old]]) as native:
            rows, join = gate.run_rows("synthetic-run", started, finished)
        self.assertEqual((rows, join), ([fresh], "session"))
        self.assertEqual(native.call_count, 2)
        with mock.patch.object(gate, "get_json", return_value=[dict(fresh, sessionTag=None)]):
            rows, join = gate.run_rows("synthetic-run", started, finished)
        self.assertEqual(join, "time-window-plus-model")
        with mock.patch.object(gate, "get_json", return_value=[old]):
            with self.assertRaisesRegex(ValueError, "no call log"):
                gate.observed_routes(gate.run_rows("synthetic-run", started, finished)[0])

    def test_plan_owned_helpers_refresh_without_overwriting_operator_configuration(self):
        # The plan ships no rule file since the 2026-10-06 relaxation; a .py helper takes the same plan-owned branch.
        spec = importlib.util.spec_from_file_location("plan_checker", PLAN / "check_plan.py")
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        body = checker.functions((PLAN / "install.sh").read_text())["copy_config"]
        with tempfile.TemporaryDirectory() as scratch:
            config = Path(scratch)
            helper = config / "hcom-client-config.py"
            helper.write_text("# stale copied helper\n")
            operator = config / "deer-flow-config.yaml"
            operator.write_text("# operator choice\n")
            done = subprocess.run(["bash", "-euo", "pipefail", "-c",
                                   "copy_config() {\n" + body + "\n}\n"
                                   "copy_config hcom-client-config.py\ncopy_config deer-flow-config.yaml"],
                                  env={"PATH": os.environ["PATH"], "config_root": str(config),
                                       "plan_dir": str(PLAN)}, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(helper.read_bytes(), (PLAN / "config/hcom-client-config.py").read_bytes())
            self.assertEqual(operator.read_text(), "# operator choice\n")

    def test_alerting_without_destination_reports_needs_user(self):
        spec = importlib.util.spec_from_file_location("plan_checker", PLAN / "check_plan.py")
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        body = checker.functions((PLAN / "accept.sh").read_text())["alerting"]
        script = ("stage=after_sign_in; failed=0; config_root=unused; plan_dir=unused\n"
                  "python3() { return 78; }\n"
                  "check() { echo 'unexpected delivery check'; return 1; }\n"
                  "skipped() { echo skipped; }\nalerting() {\n" + body + "\n}\n"
                  "alerting\nprintf 'failed=%s\\n' \"$failed\"\n")
        done = subprocess.run(["bash", "-euo", "pipefail", "-c", script], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("alerting | after_sign_in | needs_user (78)", done.stdout)
        self.assertIn("failed=0", done.stdout)

    def test_claude_registration_accepts_the_native_indented_fields(self):
        spec = importlib.util.spec_from_file_location("plan_checker", PLAN / "check_plan.py")
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        body = checker.functions((PLAN / "accept.sh").read_text())["playwright-cli"]
        program, = [command for stage, _, _, command in checker.checks_of(body) if stage == "after_sign_in"]
        checks = "\n".join(line for line in program.splitlines() if "grep -Eq" in line and "claude-registration.txt" in line)
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "claude-registration.txt"
            for package, expected in (("1.10.1", 0), ("1.10.0", 1)):
                path.write_text("  Command: npx\n  Args: -y chrome-devtools-mcp@" + package +
                                " --headless --isolated --no-usage-statistics --no-performance-crux\n")
                done = subprocess.run(["bash", "-euo", "pipefail", "-c", checks],
                                      env={"PATH": os.environ["PATH"], "native_probe": scratch}, capture_output=True)
                self.assertEqual(done.returncode, expected)

    def test_cross_family_review_receives_the_bounded_diff_on_stdin(self):
        plan = json.loads((PLAN / "install-plan.json").read_text())
        row = next(r for r in plan["owners"] if r["slot"] == "cross-family-review")
        lines = row["acceptance"]["after_sign_in"]["command"].splitlines()
        assignment, = [line for line in lines if line.startswith("claude_review_argv=(")]
        invocation, = [line for line in lines if 'flock -w 3600' in line and
                       '"${claude_review_argv[@]}"' in line]
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch)
            binary = path / "bin" / "claude"
            binary.parent.mkdir()
            binary.write_text("#!/bin/sh\ncat > \"$run_dir/seen.diff\"\n")
            binary.chmod(0o755)
            diff = "diff --git a/example b/example\n-old\n+new\n"
            (path / "gpt-authored.diff").write_text(diff)
            done = subprocess.run(["bash", "-euo", "pipefail", "-c", assignment + "\n" + invocation],
                                  env={"PATH": str(binary.parent) + os.pathsep + os.environ["PATH"],
                                       "run_dir": scratch, "plan_dir": str(PLAN),
                                       "gpt_base": "synthetic-base", "gpt_head": "synthetic-head",
                                       "NATIVE_STACK_CLAUDE_SESSION_LOCK": str(path / "private-fixture.lock")},
                                  capture_output=True, timeout=20)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual((path / "seen.diff").read_text(), diff)

    def test_chrome_acceptance_allows_updates_and_requires_the_google_origin(self):
        spec = importlib.util.spec_from_file_location("plan_checker", PLAN / "check_plan.py")
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        body = checker.functions((PLAN / "accept.sh").read_text())["playwright-cli"]
        program, = [command for stage, _, _, command in checker.checks_of(body) if stage == "post_install"]
        prefix = program.split('cd "$tool_root/chrome-devtools-mcp-source"', 1)[0]
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch)
            sources = path / "sources"
            sources.mkdir()
            (sources / "native-stack-google-chrome.sources").write_text(
                "Signed-By: /etc/apt/keyrings/google-chrome.asc EB4C1BFD4F042F6DDDCCEC917721F63BD38B4796\n")
            prefix = prefix.replace("/etc/apt/sources.list.d/", str(sources) + "/")
            # CI 37320629278, full-suite-macos.log:12587-12617: macOS has no dpkg.
            # Stub the WSL-only comparator and require its exact production arguments (accept.sh:541 at main 2d849ba1f).
            stubs = ('google-chrome-stable() { printf "Chrome %s\\n" "$build"; }\n'
                     'dpkg-query() { printf "%s" "$build"; }\n'
                     'dpkg() { [[ "$1" == --compare-versions && "$2" == "$build" && "$3" == ge && '
                     '"$4" == 154.0.8037.97-1 ]] && return "$version_status"; }\n'
                     'apt-cache() { printf "google-chrome-stable | %s | %s stable/main amd64 Packages\\n" "$build" "$origin"; }\n')
            for build, origin, expected in (("154.0.8037.97-1", "https://dl.google.com/linux/chrome/deb/", 0),
                                            ("155.0.9000.1-1", "https://dl.google.com/linux/chrome/deb/", 0),
                                            ("153.0.1.1-1", "https://dl.google.com/linux/chrome/deb/", 1),
                                            ("155.0.9000.1-1", "https://other.invalid/chrome/deb/", 1)):
                with self.subTest(build=build, origin=origin):
                    done = subprocess.run(["bash", "-euo", "pipefail", "-c", stubs + prefix],
                                          env={"PATH": os.environ["PATH"], "XDG_STATE_HOME": scratch,
                                                "build": build, "origin": origin,
                                                "version_status": "1" if build.startswith("153.") else "0"},
                                          capture_output=True, text=True)
                    self.assertEqual(done.returncode, expected, done.stderr)

    def test_harbor_openhands_adapter_must_match_the_installed_producer(self):
        text = (PLAN / "config/harbor-worker-telemetry-accept.sh").read_text()
        start = text.index("<<'PY'", text.index('python3 - "$HARBOR_TELEMETRY_JOB_CONFIG"')) + len("<<'PY'\n")
        script = text[start:text.index("\nPY", start)]
        job = {"agents": [
            {"name": "codex", "model_name": "gpt-6.1-sol", "kwargs": {"version": "0.160.0",
             "config": {"model_provider": "openai", "model_reasoning_effort": "max"}}},
            {"name": "openhands-sdk", "model_name": "synthetic-model", "kwargs": {"version": "1.50.1"}},
            {"name": "deerflow", "model_name": "synthetic-model", "kwargs": {"repo_ref": "v2.1.0"}},
        ]}
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "public-job.json"
            for adapter, wanted in (("1.50.1", 0), ("1.51.0", 78)):
                job["agents"][1]["kwargs"]["version"] = adapter
                path.write_text(json.dumps(job))
                done = subprocess.run([sys.executable, "-c", script, str(path)],
                                      env={"producer_version": "1.50.1"}, capture_output=True, text=True)
                self.assertEqual(done.returncode, wanted, done.stderr)
                if wanted:
                    self.assertIn("needs_user", done.stderr)

    def test_harbor_refuses_auth_store_upload_before_launch(self):
        for name in ("CODEX_AUTH_JSON_PATH", "CODEX_FORCE_AUTH_JSON"):
            with self.subTest(name=name):
                done = subprocess.run(["bash", str(PLAN / "config/harbor-worker-telemetry-accept.sh")],
                                      env={"PATH": os.environ["PATH"], name: ""}, capture_output=True, text=True)
                self.assertEqual(done.returncode, 78, done.stderr)
                self.assertIn("auth-store upload is forbidden", done.stderr)


class Round3AlertReceiverRepairTests(unittest.TestCase):
    """Local receiver controls; no credential values or live delivery are used."""

    def test_selected_receivers_use_native_templates_without_reading_private_files(self):
        adapter = Round2RepairIntegrationTests.source_module("observability_config.py")
        for mode in ("webhook", "telegram", "on-host"):
            with self.subTest(receiver=mode), tempfile.TemporaryDirectory() as scratch:
                root = Path(scratch)
                store = root / "private/native-agent-stack"
                store.mkdir(parents=True, mode=0o700)
                names = ({"@BOT_TOKEN_FILE@": "alertmanager-telegram-token",
                          "@CHAT_ID_FILE@": "alertmanager-telegram-chat-id"}
                         if mode == "telegram" else {"@URL_FILE@": "alertmanager-webhook-url"})
                pointers = {marker: store / name for marker, name in names.items()}
                for pointer in pointers.values():
                    pointer.touch(mode=0o600)  # Empty synthetic metadata fixtures.
                config = root / "config"
                config.mkdir()
                template_name = "alertmanager-telegram.yaml" if mode == "telegram" else "alertmanager-webhook.yaml"
                rendered = (PLAN / "config" / template_name).read_text()
                for marker, pointer in pointers.items():
                    rendered = rendered.replace(marker, json.dumps(str(pointer)))
                (config / "alertmanager.yaml").write_text(rendered)
                read_text, read_bytes = Path.read_text, Path.read_bytes

                def guarded_text(path, *args, **kwargs):
                    self.assertNotIn(path, pointers.values(), "private destination contents must remain unread")
                    return read_text(path, *args, **kwargs)

                def guarded_bytes(path, *args, **kwargs):
                    self.assertNotIn(path, pointers.values(), "private destination contents must remain unread")
                    return read_bytes(path, *args, **kwargs)

                environment = {"PATH": os.environ["PATH"], "HOME": str(root),
                               "XDG_CONFIG_HOME": str(root / "private"),
                               "NATIVE_STACK_ALERT_RECEIVER": mode, "GIT_OPTIONAL_LOCKS": "0"}
                argv = ["observability_config.py", "alerting-ready", "--config-root", str(config),
                        "--source-root", str(PLAN / "config")]
                with mock.patch.dict(os.environ, environment, clear=True), mock.patch.object(sys, "argv", argv), \
                        mock.patch.object(Path, "read_text", guarded_text), mock.patch.object(Path, "read_bytes", guarded_bytes):
                    self.assertEqual(adapter.destination(), (mode, pointers, True))
                    self.assertEqual(adapter.main(), 0)

    def test_missing_receiver_pointers_remain_needs_user_for_every_mode(self):
        adapter = Round2RepairIntegrationTests.source_module("observability_config.py")
        for mode in ("webhook", "telegram", "on-host"):
            with self.subTest(receiver=mode), tempfile.TemporaryDirectory() as scratch:
                root = Path(scratch)
                environment = {"HOME": str(root), "XDG_CONFIG_HOME": str(root / "private"),
                               "NATIVE_STACK_ALERT_RECEIVER": mode}
                argv = ["observability_config.py", "alerting-ready", "--config-root", str(root / "config")]
                with mock.patch.dict(os.environ, environment, clear=True), mock.patch.object(sys, "argv", argv), \
                        contextlib.redirect_stderr(io.StringIO()) as returned:
                    self.assertEqual(adapter.main(), 78)
                self.assertIn("needs_user", returned.getvalue())


class ObservabilityMigrationRepairTests(unittest.TestCase):
    """Synthetic integration control; does not claim native collector acceptance."""

    def test_prometheus_unit_render_consumes_plan_and_preserves_custody(self):
        import copy
        original_plan = json.loads((PLAN / "install-plan.json").read_text())
        cases = ("valid", "changed_owned", "edited", "symlink", "operator_custody",
                 "empty_features", "string_features", "duplicate_features", "unsafe_feature",
                 "string_port", "invalid_release", "unsafe_path")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                config = root / ("config space" if case == "unsafe_path" else "config")
                config.mkdir()
                source_plan = root / "plan.json"
                plan = copy.deepcopy(original_plan)
                row = next(r for r in plan["owners"] if r["slot"] == "prometheus")
                source_plan.write_text(json.dumps(plan))
                data = root / "data"
                tools = root / "tools"
                tools.mkdir()
                systemctl = tools / "systemctl"
                systemctl.write_text("#!/bin/sh\nprintf activated > " + str(root / "activation") + "\nexit 99\n")
                systemctl.chmod(0o700)
                active = root / "active-user-units" / "ns2604-prometheus.service"
                active.parent.mkdir()
                active.write_text("Existing operator-owned active unit\n")
                env = {**{key: os.environ[key] for key in ("PATH", "TMPDIR") if key in os.environ},
                       "PATH": str(tools) + os.pathsep + os.environ["PATH"],
                       "NS2604_OBSERVABILITY_DATA": str(data)}
                command = [sys.executable, str(PLAN / "config/observability_config.py"), "prometheus",
                           "--config-root", str(config), "--source-root", str(PLAN / "config"),
                           "--tools-root", str(tools), "--plan-file", str(source_plan)]
                target = config / "ns2604-prometheus.service"
                ledger = config / ".g4-source-digests.json"
                if case in ("valid", "changed_owned", "edited", "symlink", "operator_custody"):
                    first = subprocess.run(command, env=env, capture_output=True, text=True)
                    self.assertEqual(first.returncode, 0, first.stderr)
                    unit = target.read_text()
                    required = ",".join(row["service"]["enable_features"])
                    self.assertIn("--enable-feature=" + required, unit)
                    self.assertIn("--web.listen-address=127.0.0.1:" + str(row["service"]["port"]), unit)
                    self.assertIn(str(tools / "prometheus/prometheus-3.15.0.linux-amd64/prometheus"), unit)
                    self.assertIn("WorkingDirectory=" + str(data / "prometheus"), unit)
                    self.assertNotIn("@PROMETHEUS_", unit)
                    self.assertEqual(json.loads(ledger.read_text())["ns2604-prometheus.service"],
                                     hashlib.sha256(unit.encode()).hexdigest())
                    if case == "changed_owned":
                        row["service"]["enable_features"].reverse()
                    elif case == "edited":
                        target.write_text("Operator-edited candidate unit\n")
                    elif case == "symlink":
                        target.unlink()
                        target.symlink_to(active)
                    elif case == "operator_custody":
                        ledger.write_text(json.dumps({"operator_migrations": {"ns2604-prometheus.service": "operator"}}))
                else:
                    target.write_text("Retained unit fixture\n")
                    ledger.write_text(json.dumps({"fixture": "retain"}))
                    if case == "empty_features":
                        row["service"]["enable_features"] = []
                    elif case == "string_features":
                        row["service"]["enable_features"] = "created-timestamp-zero-ingestion"
                    elif case == "duplicate_features":
                        row["service"]["enable_features"] *= 2
                    elif case == "unsafe_feature":
                        row["service"]["enable_features"] = ["bad feature\nExecStart=injected"]
                    elif case == "string_port":
                        row["service"]["port"] = str(row["service"]["port"])
                    elif case == "invalid_release":
                        row["release"] = "v3.15.0\nExecStart=injected"
                source_plan.write_text(json.dumps(plan))
                before_target, before_ledger = target.read_bytes(), ledger.read_bytes()
                checked = subprocess.run(command, env=env, capture_output=True, text=True)
                passed = case in ("valid", "changed_owned")
                self.assertEqual(checked.returncode == 0, passed, checked.stderr)
                if passed:
                    self.assertIn("--enable-feature=" + ",".join(row["service"]["enable_features"]), target.read_text())
                else:
                    self.assertEqual(target.read_bytes(), before_target)
                    self.assertEqual(ledger.read_bytes(), before_ledger)
                    if case in ("edited", "symlink", "operator_custody"):
                        self.assertIn("needs_owner:", checked.stderr)
                self.assertEqual(active.read_text(), "Existing operator-owned active unit\n")
                self.assertFalse((root / "activation").exists())
                self.assertFalse(data.exists(), "render-only publisher must not prepare service runtime state")

    def test_migrated_operator_pipelines_survive_reruns_and_are_never_owned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config"
            config.mkdir()
            binary = root / "otelcol-contrib"
            binary.write_text("#!/bin/sh\nexit 0\n")
            binary.chmod(0o700)
            original = "extensions:\n  file_storage:\n    directory: /otelcol/queue\nservice:\n  pipelines:\n    operator-custom: {}\n"
            target = config / "otel.yaml"
            target.write_text(original)
            env = {**{key: os.environ[key] for key in ("PATH", "TMPDIR") if key in os.environ},
                   "PATH": str(root) + os.pathsep + os.environ["PATH"],
                   "NS2604_OBSERVABILITY_DATA": str(root / "data")}
            command = [sys.executable, str(PLAN / "config/observability_config.py"), "otel",
                       "--config-root", str(config), "--source-root", str(PLAN / "config")]
            first = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(first.returncode, 3, first.stderr)
            self.assertIn("needs_owner:", first.stderr)
            migrated = target.read_text()
            self.assertIn("operator-custom", migrated)
            self.assertNotIn("/otelcol/queue\n", migrated)
            ledger_path = config / ".g4-source-digests.json"
            ledger = json.loads(ledger_path.read_text())
            self.assertNotIn("otel.yaml", ledger)
            second = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(second.returncode, 3, second.stderr)
            self.assertIn("needs_owner:", second.stderr)
            self.assertEqual(target.read_text(), migrated)
            # Recover the old erroneous ownership ledger using the retained migration backup.
            ledger["otel.yaml"] = hashlib.sha256(migrated.encode()).hexdigest()
            ledger_path.write_text(json.dumps(ledger))
            third = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(third.returncode, 3, third.stderr)
            self.assertIn("needs_owner:", third.stderr)
            self.assertEqual(target.read_text(), migrated)
            self.assertNotIn("otel.yaml", json.loads(ledger_path.read_text()))

    def test_operator_custody_survives_template_pristine_and_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config"
            config.mkdir()
            target = config / "otel.yaml"
            ledger_path = config / ".g4-source-digests.json"
            # A synthetic pristine value exercises the same digest branch as an
            # operator restoring the earlier template; no collector is executed.
            pristine = "service:\n  pipelines:\n    operator-restored: {}\n"
            script = root / "observability_config.py"
            script.write_text((PLAN / "config/observability_config.py").read_text().replace(
                '"otel.yaml": "1bcdf496537bab925fd39b42fd5b2b8226e2d4fb4f95b3aaba1d52e23c3d731f"',
                '"otel.yaml": "' + hashlib.sha256(pristine.encode()).hexdigest() + '"'))
            command = [sys.executable, str(script), "otel", "--config-root", str(config),
                       "--source-root", str(PLAN / "config")]
            for text in (pristine, (PLAN / "config/otel.yaml").read_text(), None):
                with self.subTest(restored=text is not None):
                    ledger_path.write_text(json.dumps({"otel.yaml": "old-owned-digest",
                                                       "operator_migrations": {"otel.yaml": "migrated"}}))
                    if text is None:
                        target.unlink()
                    else:
                        target.write_text(text)
                    result = subprocess.run(command, capture_output=True, text=True,
                                            env={**{key: os.environ[key] for key in ("PATH", "TMPDIR") if key in os.environ},
                                                 "NS2604_OBSERVABILITY_DATA": str(root / "data")})
                    self.assertEqual(result.returncode, 3, result.stderr)
                    self.assertIn("needs_owner:", result.stderr)
                    self.assertNotIn("otel.yaml", json.loads(ledger_path.read_text()))
                    self.assertEqual(target.read_text() if target.exists() else None, text)

    def test_historical_plan_render_digest_is_exact_and_operator_custody_wins(self):
        historical = {
            "otel.yaml": "d928bbb9dbd61a5245933e94c4e371289e8b7bf0013488116c6d76de5c346a1e",
            "prometheus.yaml": "1568a5025ee2e6cab6e0a853031e438d7f04ae03a0d700aa5eb6a406b3e89e65",
        }
        source = (PLAN / "config/observability_config.py").read_text()
        for name, known in historical.items():
            earlier = "service:\n  pipelines: {}\n# synthetic earlier render\n" if name == "otel.yaml" else (
                "global:\n  scrape_interval: 15s\nscrape_configs: []\n# synthetic earlier render\n")
            self.assertEqual(source.count(known), 1)
            for case in ("known", "one_byte_edit", "unknown", "empty_unknown", "operator_custody", "dangling_backup"):
                if case == "dangling_backup" and name != "otel.yaml":
                    continue
                with self.subTest(name=name, case=case), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    config = root / "config"
                    config.mkdir()
                    script = root / "observability_config.py"
                    # Locally designated stand-in for a historical render; this is
                    # synthetic ownership-transition evidence, never native acceptance.
                    script.write_text(source.replace(known, hashlib.sha256(earlier.encode()).hexdigest()))
                    target = config / name
                    original = earlier + " " if case == "one_byte_edit" else (
                        "" if case == "empty_unknown" else
                        "# unknown valid configuration\nservice: {}\n" if case == "unknown" else earlier)
                    target.write_text(original)
                    ledger_path = config / ".g4-source-digests.json"
                    if case == "dangling_backup":
                        target.with_name("otel.yaml.pre-g4-observability").symlink_to(config / "absent-backup")
                    if case == "operator_custody":
                        ledger_path.write_text(json.dumps({"operator_migrations": {name: "fixture-owner"}}))
                    env = {key: os.environ[key] for key in ("PATH", "TMPDIR") if key in os.environ}
                    env.update({"NS2604_OBSERVABILITY_DATA": str(root / "data"),
                                "XDG_CONFIG_HOME": str(root / "isolated-config"),
                                "NATIVE_STACK_ALERT_RECEIVER": "on-host"})
                    result = subprocess.run(
                        [sys.executable, str(script), "otel" if name == "otel.yaml" else "alerting",
                         "--config-root", str(config), "--source-root", str(PLAN / "config")],
                        env=env, capture_output=True, text=True, timeout=10)
                    if case == "known":
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(target.read_text(), (PLAN / "config" / name).read_text())
                        self.assertEqual(json.loads(ledger_path.read_text())[name],
                                         hashlib.sha256(target.read_bytes()).hexdigest())
                    else:
                        self.assertNotEqual(result.returncode, 0, result.stderr)
                        self.assertIn("needs_owner:", result.stderr)
                        self.assertEqual(target.read_text(), original)
                        if ledger_path.exists():
                            self.assertNotIn(name, json.loads(ledger_path.read_text()))
                        else:
                            self.assertNotEqual(case, "operator_custody")

    def test_grafana_absent_legacy_paths_allow_publish_and_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config"
            unrelated = config / "owner-backup/ns2604.yaml"
            unrelated.parent.mkdir(parents=True)
            unrelated.write_bytes(b"unrelated owner bytes\n")
            env = {key: os.environ[key] for key in ("PATH", "TMPDIR") if key in os.environ}
            env["NS2604_OBSERVABILITY_DATA"] = str(root / "data")
            for action in ("grafana", "grafana-check"):
                result = subprocess.run(
                    [sys.executable, str(PLAN / "config/observability_config.py"), action,
                     "--config-root", str(config), "--source-root", str(PLAN / "config")],
                    env=env, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(unrelated.read_bytes(), b"unrelated owner bytes\n")
            self.assertTrue((config / "grafana-provisioning/datasources/native-stack.yaml").is_file())
            self.assertTrue((config / "grafana-provisioning/dashboards/native-stack.yaml").is_file())
            self.assertTrue((config / "grafana-dashboards/token-layer.json").is_file())

    def test_grafana_legacy_preflight_preserves_every_path_before_publish_or_check(self):
        legacy_paths = (
            "grafana-provisioning/datasources/ns2604.yaml",
            "grafana-provisioning/dashboards/token-layer.yaml",
            "grafana-dashboards/token-layer/token-layer.json",
        )

        def snapshot(root):
            result = {}
            for path in root.rglob("*"):
                info = path.lstat()
                payload = (os.readlink(path) if path.is_symlink() else
                           path.read_bytes() if path.is_file() else None)
                result[path.relative_to(root).as_posix()] = (
                    info.st_mode, info.st_ino, info.st_mtime_ns, payload)
            return result

        for name in legacy_paths:
            for case in ("file", "empty", "ledger_owned", "directory", "live_symlink", "dangling_symlink", "loop_symlink"):
                for action in ("grafana", "grafana-check"):
                    with self.subTest(name=name, case=case, action=action), tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        config = root / "config"
                        env = {key: os.environ[key] for key in ("PATH", "TMPDIR") if key in os.environ}
                        env["NS2604_OBSERVABILITY_DATA"] = str(root / "data")
                        command = [sys.executable, str(PLAN / "config/observability_config.py"),
                                   "--config-root", str(config), "--source-root", str(PLAN / "config")]
                        initial = subprocess.run(command + ["grafana"], env=env, capture_output=True, text=True, timeout=10)
                        self.assertEqual(initial.returncode, 0, initial.stderr)
                        target = config / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if case == "directory":
                            target.mkdir()
                            (target / "preserved").write_bytes(b"directory-owned bytes\n")
                        elif case.endswith("symlink"):
                            linked = root / "linked-owner-file"
                            if case == "live_symlink":
                                linked.write_bytes(b"symlink target bytes\n")
                            target.symlink_to(target.name if case == "loop_symlink" else linked)
                        else:
                            target.write_bytes(b"" if case == "empty" else b"legacy owner bytes\n")
                            if case == "ledger_owned":
                                ledger = config / ".g4-source-digests.json"
                                values = json.loads(ledger.read_text())
                                values[name] = hashlib.sha256(target.read_bytes()).hexdigest()
                                ledger.write_text(json.dumps(values))
                        before = snapshot(root)
                        env["NS2604_OBSERVABILITY_DATA"] = str(root / "never-created-data")
                        result = subprocess.run(command + [action], env=env, capture_output=True, text=True, timeout=10)
                        self.assertNotEqual(result.returncode, 0, result.stderr)
                        self.assertIn("needs_owner:", result.stderr)
                        self.assertIn(name, result.stderr)
                        self.assertEqual(snapshot(root), before)
                        self.assertFalse((root / "never-created-data").exists())

    def test_all_grafana_acceptance_stages_preflight_current_source_before_native_work(self):
        row = next(row for row in json.loads((PLAN / "install-plan.json").read_text())["owners"]
                   if row["slot"] == "grafana")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config"
            legacy = config / "grafana-provisioning/datasources/ns2604.yaml"
            legacy.parent.mkdir(parents=True)
            legacy.write_bytes(b"synthetic legacy configuration\n")
            marker = root / "unexpected-native-work"
            installed = config / "observability_config.py"
            installed.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n")
            bin_dir = root / "bin"
            bin_dir.mkdir()
            for name in ("grafana", "curl", "flock", "uv", "claude"):
                stub = bin_dir / name
                stub.write_text("#!/bin/sh\ntouch \"$NATIVE_FIXTURE_MARKER\"\nexit 93\n")
                stub.chmod(0o700)
            env = {key: os.environ[key] for key in ("PATH", "TMPDIR") if key in os.environ}
            env.update({"PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
                        "plan_dir": str(PLAN), "config_root": str(config),
                        "NATIVE_FIXTURE_MARKER": str(marker),
                        "NS2604_OBSERVABILITY_DATA": str(root / "data")})
            for stage, entry in row["acceptance"].items():
                with self.subTest(stage=stage):
                    result = subprocess.run(["bash", "-euo", "pipefail", "-c", entry["command"]],
                                            env=env, capture_output=True, text=True, timeout=10)
                    self.assertNotEqual(result.returncode, 0, result.stderr)
                    self.assertIn("needs_owner:", result.stderr)
                    self.assertFalse(marker.exists(), "preflight must precede installed helpers and native work")
                    self.assertFalse((root / "data").exists())
                    self.assertEqual(legacy.read_bytes(), b"synthetic legacy configuration\n")

    def test_grafana_uninspectable_legacy_path_needs_owner_before_any_output(self):
        adapter = Round2RepairIntegrationTests.source_module("observability_config.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original_lstat = Path.lstat

            def unreadable(path, *args, **kwargs):
                if path == root / "grafana-provisioning/datasources/ns2604.yaml":
                    raise PermissionError("synthetic metadata denial")
                return original_lstat(path, *args, **kwargs)

            for action in ("grafana", "grafana-check"):
                with self.subTest(action=action), mock.patch.object(Path, "lstat", unreadable), \
                        mock.patch.object(sys, "argv", ["observability_config.py", action, "--config-root", str(root)]), \
                        mock.patch.object(adapter, "atomic") as writer:
                    with self.assertRaisesRegex(ValueError, "needs_owner: cannot verify legacy Grafana path"):
                        adapter.main()
                    writer.assert_not_called()

    def test_validator_refusal_preserves_operator_config_and_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config"
            config.mkdir()
            binary = root / "otelcol-contrib"
            binary.write_text("#!/bin/sh\nexit 29\n")
            binary.chmod(0o700)
            original = "extensions:\n  file_storage:\n    directory: /otelcol/queue\nservice:\n  pipelines:\n    operator-custom: {}\n"
            target = config / "otel.yaml"
            target.write_text(original)
            ledger_path = config / ".g4-source-digests.json"
            ledger = {"prometheus.yaml": "unrelated-fixture-digest"}
            ledger_path.write_text(json.dumps(ledger))
            env = {key: os.environ[key] for key in ("PATH", "TMPDIR") if key in os.environ}
            env.update({"PATH": str(root) + os.pathsep + os.environ["PATH"],
                        "NS2604_OBSERVABILITY_DATA": str(root / "data")})
            result = subprocess.run(
                [sys.executable, str(PLAN / "config/observability_config.py"), "otel",
                 "--config-root", str(config), "--source-root", str(PLAN / "config")],
                env=env, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0, result.stderr)
            self.assertIn("upstream validator refused", result.stderr)
            self.assertEqual(target.read_text(), original)
            self.assertEqual(json.loads(ledger_path.read_text()), ledger)




class GatewayCanaryBindingRepairTests(unittest.TestCase):
    """Synthetic package controls; no gateway binary or provider is executed."""

    def test_canary_binding_rejects_rollback_foreign_and_mismatched_builds(self):
        with tempfile.TemporaryDirectory() as tmp:
            tool_root = Path(tmp) / "tools"
            build = tool_root / "omniroute-canary-fixture"
            (build / "source").mkdir(parents=True)
            package = build / "prefix/lib/node_modules/omniroute"
            (package / "bin").mkdir(parents=True)
            (package / "dist").mkdir()
            binary = package / "bin/omniroute"
            binary.write_text("#!/bin/sh\nprintf '3.8.52\\n'\n")
            binary.chmod(0o700)
            marker = package / "dist/BUILD_SHA"
            metadata = package / "package.json"
            receipt = json.loads((PLAN / "config/omniroute-canary-evidence.json").read_text())
            expected = receipt["composition"]
            # Synthetic git output keeps this a local binding test, rather than
            # claiming an upstream source checkout or gateway build was accepted.
            shim = Path(tmp) / "git"
            shim.write_text("#!/bin/sh\nprintf '" + receipt["reproduction"]["source_tree"] + "\\n'\n")
            shim.chmod(0o700)
            env = {**os.environ, "PATH": tmp + os.pathsep + os.environ["PATH"]}
            command = [sys.executable, str(PLAN / "config/omniroute-canary-check.py"), str(binary),
                       str(PLAN / "config/omniroute-canary-evidence.json"), str(tool_root)]
            for name, version, sha, code in (("omniroute", "3.8.52", expected["recorded_build_sha"], 0),
                                             ("omniroute", "3.8.51", expected["recorded_build_sha"], 1),
                                             ("foreign", "3.8.52", expected["recorded_build_sha"], 1),
                                             ("omniroute", "3.8.52", "foreign-build", 1)):
                with self.subTest(name=name, version=version, sha=sha):
                    metadata.write_text(json.dumps({"name": name, "version": version}))
                    marker.write_text(sha)
                    result = subprocess.run(command, capture_output=True, text=True, env=env)
                    self.assertEqual(result.returncode, code, result.stderr)
            metadata.write_text(json.dumps({"name": "omniroute", "version": "3.8.52"}))
            marker.write_text(expected["recorded_build_sha"])
            shim.write_text("#!/bin/sh\nprintf 'foreign-tree\\n'\n")
            self.assertEqual(subprocess.run(command, capture_output=True, env=env).returncode, 1)
            shim.write_text("#!/bin/sh\nprintf '" + receipt["reproduction"]["source_tree"] + "\\n'\n")
            outside = Path(tmp) / "foreign"
            shutil.copytree(package, outside)
            command[2] = str(outside / "bin/omniroute")
            self.assertEqual(subprocess.run(command, capture_output=True, env=env).returncode, 1)


class AlertingAttestationRepairTests(unittest.TestCase):
    """Cached receipt controls, without delivery, secrets or service operations."""

    def test_invalid_attestation_is_retained_and_does_not_block_a_fresh_test(self):
        rows = json.loads((PLAN / "install-plan.json").read_text())["owners"]
        row = next(r for r in rows if r["slot"] == "alerting")
        command = row["acceptance"]["after_sign_in"]["command"]
        cache = "receipt=" + command.split("\nreceipt=", 1)[1].split("\nfixture=", 1)[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("alertmanager.yaml", "prometheus.yaml", "prometheus-alerts.yaml"):
                (root / name).write_text("synthetic nonsecret config\n")
            config_digest = hashlib.sha256(b"".join((root / name).read_bytes() for name in (
                "alertmanager.yaml", "prometheus.yaml", "prometheus-alerts.yaml"))).hexdigest()
            for stale, mismatched in ((True, False), (False, True), (False, False)):
                with self.subTest(stale=stale, mismatched=mismatched):
                    receipt = {"observed_unix": time.time() - (3600 if stale else 0),
                               "acceptance_id": "synthetic-id", "config_sha256": config_digest,
                               "rule_fired": True, "rule_resolved": True, "notification_delta": 1}
                    confirmation = {"acceptance_id": "different" if mismatched else "synthetic-id",
                                    "firing_received": True, "resolved_received": True, "confirmed_by": "user"}
                    (root / "alerting-delivery-receipt.json").write_text(json.dumps(receipt))
                    (root / "alerting-receiver-confirmation.json").write_text(json.dumps(confirmation))
                    result = subprocess.run(["bash", "-euo", "pipefail", "-c", cache +
                                             '\nprintf "FRESH_DELIVERY_TEST\\n"'], capture_output=True, text=True,
                                            env={**os.environ, "config_root": str(root)})
                    self.assertEqual(result.returncode, 0, result.stderr)
                    if stale or mismatched:
                        self.assertIn("FRESH_DELIVERY_TEST", result.stdout)
                        self.assertFalse((root / "alerting-delivery-receipt.json").exists())
                        self.assertTrue(list(root.glob("alerting-stale.*/alerting-delivery-receipt.json")))
                    else:
                        self.assertNotIn("FRESH_DELIVERY_TEST", result.stdout)
                        self.assertIn("user_attestation; provenance_not_verified", result.stdout)


class SrtWriteRepairNegativeControlTests(unittest.TestCase):
    def test_a_bypassed_write_policy_cannot_pass_the_native_recipe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            allowed = root / "allowed"
            allowed.mkdir()
            protected, unreadable, policy = (root / name for name in ("protected", "unreadable", "policy.json"))
            for fixture in (protected, unreadable, policy):
                fixture.write_text("synthetic fixture\n")
            # A synthetic srt enforces the read control but bypasses write protection.
            shim = root / "srt"
            shim.write_text('#!/bin/bash\nif [[ "$1" == --settings ]]; then shift 2; fi\n'
                            'if [[ "$1" == -- ]]; then shift; fi\n'
                            'if [[ "$1" == cat ]]; then exit 1; fi\nexec "$@"\n')
            shim.chmod(0o700)
            curl = root / "curl"
            curl.write_text("#!/bin/sh\nexit 0\n")
            curl.chmod(0o700)
            source = (PLAN / "config/srt-client-accept.sh").read_text()
            recipe = source.split("<<'SRT'\n", 1)[1].split("\nSRT\n", 1)[0]
            env = {**os.environ, "PATH": str(root) + os.pathsep + os.environ["PATH"],
                   "SRT_ACCEPT_POLICY": str(policy), "SRT_ACCEPT_DENY_READ": str(unreadable),
                   "SRT_ACCEPT_DENY_WRITE": str(protected), "SRT_ACCEPT_ALLOWED_DIR": str(allowed),
                   "SRT_ACCEPT_DENIED_URL": "https://example.com"}
            result = subprocess.run(["bash", "-c", recipe], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("SRT_ALLOW_WRITE_CONTROL=passed", result.stdout)
            self.assertIn("SRT_DENY_READ_EXIT=1", result.stdout)
            self.assertIn("sandboxed write", protected.read_text())
            self.assertNotIn("SRT_NATIVE_USE_OK", result.stdout)
EXAMPLE_HOST = "example"

# A synthetic stand-in for the claude client: --version and `mcp get|add|remove` against a JSON file under $HOME, in the
# output shape of Claude Code 2.1.287 (tests/test_install_claude_profile.py's recorded `claude mcp get` text). When
# STUB_MARKER names a file, every call is appended to it, so a test can show that a client was or was not run.
STUB_CLAUDE = """#!/usr/bin/env python3
import json, os, sys
marker = os.environ.get("STUB_MARKER")
if marker:
    open(marker, "a").write(" ".join(sys.argv[1:]) + "\\n")
state = os.path.join(os.environ["HOME"], ".stub-claude-mcp.json")
data = json.load(open(state)) if os.path.exists(state) else {}
a = sys.argv[1:]
if a[:1] == ["--version"]:
    print("2.1.287 (Claude Code)")
elif a[:2] == ["mcp", "get"]:
    spec = data.get(a[2])
    if spec is None:
        print("No MCP server found with name: " + a[2], file=sys.stderr)
        sys.exit(1)
    print(a[2] + ":\\n  Scope: User config (available in all your projects)\\n  Status: Connected\\n  Type: " + spec["type"])
    if spec["type"] == "stdio":
        print("  Command: " + spec["command"] + "\\n  Args: " + " ".join(spec["args"]) + "\\n  Environment:")
        for key in spec["env"]:
            print("    " + key + "=" + spec["env"][key])
    else:
        print("  URL: " + spec["url"])
    print("\\nTo remove this server, run: claude mcp remove " + a[2] + " -s user")
elif a[:2] == ["mcp", "add"]:
    rest = a[2:]
    assert rest[:2] == ["--scope", "user"], rest
    rest, env = rest[2:], {}
    if rest[:1] == ["--transport"]:
        data[rest[2]] = {"type": rest[1], "url": rest[3]}
        assert len(rest) == 4, rest
        json.dump(data, open(state, "w"))
        print("Added " + rest[1] + " MCP server " + rest[2])
        sys.exit(0)
    name, rest = rest[0], rest[1:]
    while rest and rest[0] != "--":
        assert rest[0] == "-e", rest
        key, _, value = rest[1].partition("=")
        env[key] = value
        rest = rest[2:]
    command = rest[1:]
    data[name] = {"type": "stdio", "command": command[0], "args": command[1:], "env": env}
    json.dump(data, open(state, "w"))
    print("Added stdio MCP server " + name)
elif a[:2] == ["mcp", "remove"]:
    data.pop(a[2], None)
    json.dump(data, open(state, "w"))
else:
    sys.exit(2)
"""
# A synthetic stand-in for codex: --version, and `features disable daemon_auto_start` writing that key into
# $CODEX_HOME/config.toml the way Codex's own writer does. STUB_CODEX_MODE=fail exits 3; =extra also writes a table that
# the merge does not expect. Every call is appended to STUB_MARKER as `codex <arguments>`.
STUB_CODEX = """#!/usr/bin/env python3
import os, sys
a = sys.argv[1:]
marker = os.environ.get("STUB_MARKER")
if marker:
    open(marker, "a").write("codex " + " ".join(a) + "\\n")
mode = os.environ.get("STUB_CODEX_MODE", "")
if a[:1] == ["--version"]:
    print("codex-cli 0.160.0")
elif a[:3] == ["features", "disable", "daemon_auto_start"]:
    if mode == "fail":
        print("error: the stub refuses", file=sys.stderr)
        sys.exit(3)
    path = os.path.join(os.environ["CODEX_HOME"], "config.toml")
    lines = open(path).read().split("\\n") if os.path.exists(path) else []
    if "[features]" in lines:
        lines.insert(lines.index("[features]") + 1, "daemon_auto_start = false")
        text = "\\n".join(lines)
    else:
        text = "\\n".join(lines).rstrip("\\n") + "\\n\\n[features]\\ndaemon_auto_start = false\\n"
    if mode == "extra":
        text += "\\n[stub_extra]\\nsurprise = 1\\n"
    open(path, "w").write(text)
else:
    sys.exit(2)
"""
NO_PROCESS = "no-such-process-name-here"   # the Codex process guard looks for no running process of this name
# The width of the display of a conflicting value, as the tool's docstring and Decision 11 of the decision record state it: a
# longer value is cut to this many characters less three and `...`, in the display only. It is a number here, not the tool's
# constant, so that a change of the constant has to change the documentation and this test with it.
DOCUMENTED_WIDTH = 300


def plan_marketplace() -> tuple:
    """(commit, url) from the two `plugin marketplace add` lines of the install plan's Trail of Bits row."""
    rows = {row["slot"]: row for row in json.loads((PLAN / "install-plan.json").read_text())["owners"]}
    commands = rows["trail-of-bits-security-skills-trailofbits-skills"]["commands"]
    codex = next(c for c in commands if c.startswith("codex plugin marketplace add"))
    claude = next(c for c in commands if c.startswith("claude plugin marketplace add"))
    return re.search(r"--ref ([0-9a-f]{40})\b", codex).group(1), claude.split()[-1]


PLAN_COMMIT, PLAN_MARKETPLACE_URL = plan_marketplace()
# What the destination holds after the plan and the sign-ins (observed 2026-10-02: 192 and 194 bytes), rebuilt from the
# plan's own commands. `codex plugin marketplace add trailofbits/skills --ref <commit>` writes the Codex table, and
# Codex's first start adds `[tui]`; `claude plugin marketplace add <url>` writes the Claude marketplace, and its first
# start the theme (here "auto", a four-character value like the observed file's, and not the template's "dark").
DESTINATION_CODEX = ('[marketplaces.trailofbits]\nsource_type = "git"\nsource = "https://github.com/trailofbits/skills.git"\n'
                     f'ref = "{PLAN_COMMIT}"\n\n[tui]\nscreen_reader_detection_done = true\n')
DESTINATION_CLAUDE = {"extraKnownMarketplaces": {"trailofbits": {"source": {
    "source": "git", "url": PLAN_MARKETPLACE_URL}}}, "theme": "auto"}
FAILING_CLAUDE = "#!/bin/sh\nexit 3\n"
# The wave-2 batch owes both acknowledgements until its pull request has them, and --apply refuses to wire an interim
# install meanwhile (AcknowledgementGateTests, with the real function). Every other test applies as if both were recorded.
REAL_OWED_ACKNOWLEDGEMENTS = cfg.owed_acknowledgements
ACKNOWLEDGED = mock.patch.object(cfg, "owed_acknowledgements", return_value=[])


def setUpModule():
    ACKNOWLEDGED.start()


def tearDownModule():
    ACKNOWLEDGED.stop()


def write_exe(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def run_main(*argv: str):
    """(exit code, stdout, stderr) of cfg.main(argv) in this process."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cfg.main(list(argv))
    return code, out.getvalue(), err.getvalue()


def make_catalog(tmp: Path) -> Path:
    """A scratch copy of everything the tool reads from a catalog checkout, to break one input at a time. The committed
    filtered blocks are copied too, so the copy starts clean."""
    root = tmp / "catalog"
    files = [cfg.MAP_REL, cfg.MANIFEST_REL, cfg.BOOTSTRAP_REL, cfg.HOST_TEMPLATE_REL, *cfg.TEMPLATES.values(),
             *cfg.TEMPLATE_ADDITIONS.values(), *cfg.BLOCK_TEXT_REL.values(), *cfg.GENERATED_BLOCKS.values(), f"{cfg.PLAN_REL}/install-plan.json",
             f"{cfg.PLAN_REL}/config/otel.yaml", f"{cfg.PLAN_REL}/config/omniroute.env.example",
             cfg.SKILLS_MANIFEST_REL, cfg.managed_block.RTK_AWARENESS_REL]
    # The dated records that the map's `directive` fields name: --check requires each to be a file of the checkout.
    files += sorted({entry["directive"] for entry in json.loads((ROOT / cfg.MAP_REL).read_text(encoding="utf-8"))["entries"]
                     if "directive" in entry})
    for rel in files:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, root / rel)
    for rel in (cfg.CLAUDE_AGENTS_REL, cfg.CODEX_ROLES_REL):
        shutil.copytree(ROOT / rel, root / rel)
    return root


def write_blocks(root: Path) -> None:
    """Make the two filtered blocks of a scratch catalog fresh again after its map, manifest or a source changed."""
    code, out, err = run_main("--write-blocks", "--root", str(root))
    assert code == 0, err or out


def edit_json(path: Path, change) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def without_interim(slot: str):
    """A change for edit_json on the manifest: the foundation row `slot` without its interim install (amendment 3 of the
    decision rule), so the row is what it was before the wave-2 records."""
    def change(data):
        row = next(r for r in data["slots"] if r["slot_id"] == slot and r["catalog"] == "foundation")
        assert row.pop("interim", None), f"{slot} carries no interim"
    return change


# The ai-memory routing line both block sources carried until the philosophy-only blocks of 2026-10-08, and the map
# declaration of its dependent sentence that went with it. The committed blocks now name no tool, so the tests that follow
# a tool's sentence through the filter add this line and declaration to a scratch catalog.
AI_MEMORY_LINE = ("Bound discovery to task-filtered names, descriptions and source locators; load only selected tool "
                  "schemas. For maintained decisions, and before describing deployed architecture after compaction/resume, "
                  "query scoped ai-memory with `pin_first=true, limit=2` when supported by the installed schema. Check "
                  "relevance; retry without pin priority or widen if needed, then read the relevant exact path and verify "
                  "current canonical sources.")
AI_MEMORY_DEPENDENT = {"starts": "Check relevance; retry without pin priority", "on": "previous",
                       "why": "It refines the ai-memory query the sentence before it describes ('pin priority' is that "
                              "query's `pin_first`), so without that sentence it points at nothing to check or retry."}


def with_ai_memory_line(root: Path) -> None:
    """Add AI_MEMORY_LINE to both block sources of a scratch catalog (inside the Codex block, before its RTK section),
    declare its dependent sentence in the map and write the blocks again, so the catalog starts clean."""
    for piece, relative in cfg.BLOCK_TEXT_REL.items():
        path = root / relative
        text = path.read_text(encoding="utf-8")
        if piece == cfg.CODEX_MD_PIECE:
            marker = "<!-- native-agent-stack:rtk-upstream"
            text = text.replace(marker, AI_MEMORY_LINE + "\n\n" + marker, 1)
        else:
            text += "\n" + AI_MEMORY_LINE + "\n"
        path.write_text(text, encoding="utf-8")
    edit_json(root / cfg.MAP_REL, lambda data: data["dependent_sentences"].append(dict(AI_MEMORY_DEPENDENT)))
    write_blocks(root)


def tree(home: Path) -> dict:
    """{relative path: sha256 of its bytes, or the link target} of every file and link under home."""
    found = {}
    for path in sorted(home.rglob("*")):
        if path.is_symlink():
            found[str(path.relative_to(home))] = "->" + os.readlink(path)
        elif path.is_file():
            found[str(path.relative_to(home))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def foundation_rows() -> dict:
    return {row["slot_id"]: row for row in json.loads(MANIFEST.read_text())["slots"] if row["catalog"] == "foundation"}


def plan_ports() -> dict:
    """The plan's ports as the plan's own files state them, read without the tool."""
    otel = (PLAN / "config" / "otel.yaml").read_text()
    http = re.search(r"http:\s*\n\s*endpoint: 127\.0\.0\.1:(\d+)", otel).group(1)
    grpc = re.search(r"grpc:\s*\n\s*endpoint: 127\.0\.0\.1:(\d+)", otel).group(1)
    rows = {row["slot"]: row for row in json.loads((PLAN / "install-plan.json").read_text())["owners"]}
    return {"http": int(http), "grpc": int(grpc), "gateway": rows["gpt-gateway"]["service"]["port"]}


class MapTests(unittest.TestCase):
    """The map is a closed world over the templates and says why each piece is or is not wired."""

    def test_the_repository_passes_its_own_check(self):
        code, out, err = run_main("--check")
        self.assertEqual((code, err), (0, ""), out[-400:])
        self.assertIn("check passed", out)
        self.assertRegex(out, rf"pieces: [34]\d\d; wired: \d+; not wired: \d+; authorization: {len(AuthorizationTests.ALL)}\n")

    def test_every_piece_has_one_line_and_every_unwired_one_says_why(self):
        results, *_ = cfg.analyse(ROOT)
        code, out, _ = run_main("--check")
        lines = [line for line in out.splitlines() if line.startswith(("wired ", "not wired ", "authorization  "))]
        self.assertEqual(len(lines), len(results))
        self.assertEqual(sum(1 for line in lines if line.startswith("not wired")),
                         sum(1 for v in results if not v.wired and not v.authorization))
        self.assertEqual(sum(1 for line in lines if line.startswith("authorization  ")), len(AuthorizationTests.ALL))
        for verdict in results:
            self.assertTrue(verdict.reason.strip(), verdict.piece.key)

    def test_the_json_table_lists_every_piece(self):
        code, out, _ = run_main("--check", "--json")
        rows = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual([row["piece"] for row in rows], [p.key for p in cfg.collect_pieces(ROOT)])
        self.assertTrue(all(sorted(row) == ["piece", "reason", "wired", "wiring"] for row in rows))
        kinds = {row["wiring"].split(":")[0] for row in rows}
        self.assertEqual(kinds, {"practice", "not_wired", "slot", "authorization"})

    def test_a_piece_that_the_map_does_not_name_fails_the_check(self):
        cases = {
            "an added hook": ("claude/settings", lambda d: d["hooks"]["PreToolUse"][0]["hooks"].append(
                {"type": "command", "command": "echo an unmapped hook"}),
             "unmapped piece: claude/settings/hook/PreToolUse/matcher=Bash/echo an unmapped hook"),
            "an added variable": ("claude/settings", lambda d: d["env"].update(AN_UNMAPPED_VARIABLE="1"),
                                  "unmapped piece: claude/settings/env/AN_UNMAPPED_VARIABLE"),
            "an added setting": ("claude/settings", lambda d: d.update(anUnmappedSetting=True),
                                 "unmapped piece: claude/settings/setting/anUnmappedSetting"),
            "an added permission rule": ("claude/settings", lambda d: d["permissions"]["deny"].append("WebFetch(x)"),
                                         "unmapped piece: claude/settings/permission/deny/WebFetch(x)"),
            "an added plugin": ("claude/settings", lambda d: d["enabledPlugins"].update({"new@market": True}),
                                "unmapped piece: claude/settings/plugin/new@market"),
            "an added server": ("claude/mcp", lambda d: d["mcpServers"].update(new={"type": "stdio", "command": "x"}),
                                "unmapped piece: claude/mcp/server/new"),
            "an added overlay hook": ("claude/overlay", lambda d: d["hooks"].update(Stop=[{"hooks": [{
                "type": "command", "command": "echo stop"}]}]),
                                      "unmapped piece: claude/overlay/hook/Stop/matcher=-/echo stop"),
        }
        for name, (group, change, expected) in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                root = make_catalog(Path(tmp))
                self.assertEqual(cfg.analyse(root)[3], [], "the scratch copy must start clean")
                edit_json(root / cfg.TEMPLATES[group], change)
                errors = cfg.analyse(root)[3]
                self.assertIn(expected, errors)
                code, _, err = run_main("--check", "--root", str(root))
                self.assertEqual(code, 1)
                self.assertIn(expected, err)

    def test_keep_existing_is_a_flag_of_top_level_claude_settings_only(self):
        entry = next(e for e in json.loads(MAP.read_text())["entries"] if e["match"] == ["claude/settings/setting/theme"])
        self.assertEqual((entry["wiring"], entry["keep_existing"]), ("practice", True))
        results, *_ = cfg.analyse(ROOT)
        # The theme, and the status line that claude-hud's setup.mjs writes with the runtime that ran it.
        self.assertEqual(sorted(v.piece.key for v in results if v.entry.keep_existing),
                         ["claude/settings/setting/statusLine", "claude/settings/setting/theme"])
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            edit_json(root / cfg.MAP_REL, lambda d: d["entries"].append(
                {"match": ["codex/config/model"], "wiring": "practice", "keep_existing": True}))
            errors = cfg.analyse(root)[3]
        self.assertTrue(any("keep_existing applies to top-level Claude settings only" in e for e in errors), errors)
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            edit_json(root / cfg.MAP_REL, lambda d: next(
                e for e in d["entries"] if e["match"] == ["claude/settings/setting/theme"]).update(keep_existing="yes"))
            with self.assertRaises(cfg.ConfigError):
                cfg.load_map(root)

    def test_an_added_codex_key_agent_or_role_fails_the_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            toml = root / cfg.TEMPLATES["codex/config"]
            toml.write_text(toml.read_text() + "\n[an_unmapped_table]\nkey = 1\n", encoding="utf-8")
            (root / cfg.CLAUDE_AGENTS_REL / "unmapped-agent.md").write_text("---\nname: x\n---\n", encoding="utf-8")
            (root / cfg.CODEX_ROLES_REL / "unmapped-role.toml").write_text("name = 'x'\n", encoding="utf-8")
            errors = cfg.analyse(root)[3]
        for expected in ("unmapped piece: codex/config/an_unmapped_table.key", "unmapped piece: claude/profile/agent/"
                         "unmapped-agent.md", "unmapped piece: codex/role/unmapped-role.toml"):
            self.assertIn(expected, errors)

    def test_an_entry_that_names_no_piece_fails_the_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            edit_json(root / cfg.MAP_REL, lambda d: d["entries"].append(
                {"match": ["claude/settings/env/NOT_A_VARIABLE"], "wiring": "practice"}))
            errors = cfg.analyse(root)[3]
        self.assertEqual([e for e in errors if "matches no piece" in e],
                         ["map entry %d matches no piece that an earlier entry left: "
                          "'claude/settings/env/NOT_A_VARIABLE'" % (len(json.loads(MAP.read_text())["entries"]))])

    def test_a_slot_that_the_manifest_does_not_have_fails_the_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))

            def change(data):
                entry = next(e for e in data["entries"] if e["match"] == ["claude/mcp/server/serena"])
                entry["wiring"] = "slot:no-such-slot"
            edit_json(root / cfg.MAP_REL, change)
            errors = cfg.analyse(root)[3]
        self.assertIn("claude/mcp/server/serena: slot 'no-such-slot' is not a foundation slot of the manifest", errors)

    def test_a_malformed_wiring_is_refused(self):
        for wiring in ("wired", "slot:", "not_wired:", "practice:x"):
            with self.subTest(wiring=wiring), tempfile.TemporaryDirectory() as tmp:
                root = make_catalog(Path(tmp))
                edit_json(root / cfg.MAP_REL, lambda d: d["entries"][0].update(wiring=wiring))
                with self.assertRaises(cfg.ConfigError):
                    cfg.load_map(root)

    def test_a_practice_piece_that_runs_a_tool_outside_the_repository_fails_the_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))

            def change(data):
                entry = next(e for e in data["entries"] if e["match"] ==
                             ["claude/settings/hook/PreToolUse/matcher=Bash/rtk hook claude"])
                entry["wiring"] = "practice"
                entry.pop("directive", None)    # a directive belongs to a slot entry only
            edit_json(root / cfg.MAP_REL, change)
            errors = cfg.analyse(root)[3]
        self.assertIn("claude/settings/hook/PreToolUse/matcher=Bash/rtk hook claude: a practice piece runs `rtk`, which "
                      "is not in the repository", errors)

    def test_a_directive_adds_its_owner_while_the_slot_installs_and_needs_its_record(self):
        hook = "claude/settings/hook/PreToolUse/matcher=Bash/rtk hook claude"
        verdicts = {v.piece.key: v for v in cfg.analyse(ROOT)[0]}
        self.assertTrue(verdicts[hook].wired)
        self.assertIn("slot command-output installs RTK 0.51.0", verdicts[hook].reason)
        with tempfile.TemporaryDirectory() as tmp:     # a directive adds an owner beside a different installed default
            root = make_catalog(Path(tmp))

            def other_owner(data):
                row = next(row for row in data["slots"]
                           if row.get("catalog") == "foundation" and row["slot_id"] == "command-output")
                row.pop("interim", None)
                row.update(default="Other command-output tool", installs_nothing_extra=False)

            edit_json(root / cfg.MANIFEST_REL, other_owner)
            record = next(e["directive"] for e in json.loads((root / cfg.MAP_REL).read_text())["entries"]
                          if e["match"] == [hook])
            verdicts = {v.piece.key: v for v in cfg.analyse(root)[0]}
            self.assertTrue(verdicts[hook].wired)
            self.assertIn("the owner's directive (", verdicts[hook].reason)
            self.assertIn(record, verdicts[hook].reason)
            # With the very same installed default, removing the directive removes the hook.
            edit_json(root / cfg.MAP_REL, lambda d: next(e for e in d["entries"] if e["match"] == [hook]).pop(
                "directive"))
            verdicts = {v.piece.key: v for v in cfg.analyse(root)[0]}
            self.assertFalse(verdicts[hook].wired)
            self.assertIn("not 'rtk'", verdicts[hook].reason)
        with tempfile.TemporaryDirectory() as tmp:     # the record the directive names is gone
            root = make_catalog(Path(tmp))
            record = next(e["directive"] for e in json.loads((root / cfg.MAP_REL).read_text())["entries"] if "directive" in e)
            (root / record).unlink()
            errors = cfg.analyse(root)[3]
        self.assertTrue([e for e in errors if "its directive record" in e and record in e], errors)
        with tempfile.TemporaryDirectory() as tmp:     # the slot comes to install nothing: the owner unwires with it
            root = make_catalog(Path(tmp))

            def no_layer(data):
                for row in data["slots"]:
                    if row.get("catalog") == "foundation" and row["slot_id"] == "command-output":
                        row.pop("interim", None)
                        row["installs_nothing_extra"] = True
            edit_json(root / cfg.MANIFEST_REL, no_layer)
            verdicts = {v.piece.key: v for v in cfg.analyse(root)[0]}
        self.assertFalse(verdicts[hook].wired)
        with tempfile.TemporaryDirectory() as tmp:     # a directive on an entry that is not a slot entry is refused
            root = make_catalog(Path(tmp))
            edit_json(root / cfg.MAP_REL, lambda d: next(e for e in d["entries"] if e["match"] == [hook]).update(
                wiring="practice"))
            with self.assertRaises(cfg.ConfigError):
                cfg.load_map(root)

    def test_a_practice_hook_may_run_only_files_that_the_repository_copies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            edit_json(root / cfg.TEMPLATES["claude/settings"], lambda d: d["hooks"]["SessionStart"][0]["hooks"].append(
                {"type": "command", "command": 'python3 "${HOME}/.claude/hooks/not-copied.py"'}))
            edit_json(root / cfg.MAP_REL, lambda d: d["entries"].insert(0, {
                "match": ["claude/settings/hook/SessionStart/*not-copied.py*"], "wiring": "practice"}))
            errors = cfg.analyse(root)[3]
        self.assertTrue(any("runs not-copied.py, which the repository does not copy" in e for e in errors), errors)

    def test_a_wired_hook_whose_file_is_not_a_wired_file_fails_the_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))

            def change(data):
                entry = next(e for e in data["entries"] if e["match"] == ["claude/profile/hook-file/effort-default-guard.py",
                                                                          "claude/profile/hook-file/secret_path_guard.py"])
                entry["match"] = ["claude/profile/hook-file/secret_path_guard.py"]
                data["entries"].append({"match": ["claude/profile/hook-file/effort-default-guard.py"],
                                        "wiring": "not_wired:a control"})
            edit_json(root / cfg.MAP_REL, change)
            errors = cfg.analyse(root)[3]
        self.assertTrue(any("runs effort-default-guard.py, which is not a wired hook file" in e for e in errors), errors)

    def test_a_listed_name_that_no_text_holds_fails_the_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            edit_json(root / cfg.MAP_REL, lambda d: d["entries"][0].update(names=["no-such-tool-anywhere"]))
            errors = cfg.analyse(root)[3]
        self.assertIn("the map lists the name 'no-such-tool-anywhere', and no template, instruction or agent text "
                      "holds it", errors)

    def test_a_rewrite_whose_source_text_is_gone_fails_the_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            path = root / cfg.TEMPLATES["codex/omniroute"]
            path.write_text(path.read_text().replace("127.0.0.1:20128", "127.0.0.1:20999"), encoding="utf-8")
            errors = cfg.analyse(root)[3]
        self.assertTrue(any("the rewrite source '127.0.0.1:20128' is not in the template value" in e for e in errors),
                        errors)


class AgentGapTests(unittest.TestCase):
    """What each project agent names that this distribution will not have, derived from the frontmatter."""

    def test_the_gaps_are_the_servers_and_skills_the_agents_name_beyond_the_wired_ones_and_the_plans_skills(self):
        results, _, plan, errors, warnings = cfg.analyse(ROOT)
        self.assertEqual(errors, [])
        gaps = cfg.agent_gaps(ROOT, results, plan)
        # Wave 3 wires the token servers; context-mode's plugin tools and skill retain their native names.
        wired_servers = {"serena", "qmd", "ai-memory", "semble", "socraticode", "headroom", "codebase-memory",
                         "jcodemunch", "plugin_context-mode_context-mode"}
        for path in sorted((ROOT / cfg.CLAUDE_AGENTS_REL).glob("*.md")):
            text = path.read_text()
            head = re.match(r"---\n(.*?)\n---\n", text, re.S).group(1)
            named = set(re.findall(r"mcp__([A-Za-z0-9_-]+?)__[A-Za-z0-9_]+", head))
            skills = re.findall(r"^  - (\S+)$", head, re.M)
            expected_servers = named - wired_servers
            expected_skills = [skill for skill in skills if skill not in plan["skills"]
                               and not skill.startswith("context-mode:")]
            gap = gaps.get(path.name, {"mcp_tools": [], "skills": []})
            self.assertEqual({tool.split("__")[1] for tool in gap["mcp_tools"]}, expected_servers, path.name)
            self.assertEqual(gap["skills"], expected_skills, path.name)
        # The owner-selected token stack supplies every server and skill the project agents name; jCodeMunch is registered
        # at user scope (the user's directive of 2026-10-04, docs/decisions/2026-10-04-new-wsl-jcodemunch-user-scope.md).
        self.assertEqual(gaps, {})
        # The skills rows run install_skills.py over adoption/skills/manifest.json (wave-2 skills ruling, change 7): the
        # selected rows, without the retired, pruned and held ones.
        selected = {skill["name"] for skill in json.loads((ROOT / cfg.SKILLS_MANIFEST_REL).read_text())["skills"]
                    if skill.get("status") not in ("pruned", "held")}
        self.assertEqual(plan["skills"], frozenset(selected))
        self.assertEqual(len(plan["skills"]), 27)
        self.assertTrue({"tdd", "diagnosing-bugs", "codebase-design", "writing-for-agents", "skill-creator"} <= plan["skills"])
        self.assertEqual({"grill-me", "improve-codebase-architecture", "semgrep", "agent-browser", "domain-modeling",
                          "setup-matt-pocock-skills"} & plan["skills"], set())
        self.assertTrue(any("MCP_AUTO_OPEN_ENABLED" in w and "mcp-inspector" in w for w in warnings), warnings)

    def test_a_server_that_becomes_wired_leaves_the_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))

            def install(data):
                row = next(r for r in data["slots"] if r["slot_id"] == "code-search" and r["catalog"] == "foundation")
                row.update(installs_nothing_extra=False, state="definitive", default="SocratiCode")
                row["resolution"] = {"outcome": "final"}
                row.pop("interim", None)       # a decided default replaces the interim install
            # Keep the absent-server control now that the committed interim installs SocratiCode too.
            edit_json(root / cfg.MANIFEST_REL, lambda data: next(
                r for r in data["slots"] if r["slot_id"] == "code-search" and r["catalog"] == "foundation")[
                    "interim"].update(default="semble 0.6.1"))
            before = cfg.agent_gaps(root, *[cfg.analyse(root)[i] for i in (0, 2)])
            edit_json(root / cfg.MANIFEST_REL, install)
            after = cfg.agent_gaps(root, *[cfg.analyse(root)[i] for i in (0, 2)])
        self.assertIn("socraticode", json.dumps(before["evidence-reviewer.md"]))
        self.assertNotIn("evidence-reviewer.md", after)    # jCodeMunch is wired too, so no gap remains


class ManifestRuleTests(unittest.TestCase):
    """A slot installs by the install plan's own rule, and a piece follows its slot when the manifest changes."""

    def test_the_rule_selects_the_rows_the_plan_installs_and_the_two_on_demand_rows(self):
        plan = {row["slot"]: row for row in json.loads((PLAN / "install-plan.json").read_text())["owners"]}
        installing = {slot for slot, row in foundation_rows().items() if cfg.installs(row)}
        planned = {slot for slot, row in plan.items() if row["installed"]}
        self.assertEqual(installing - planned, {"mcp-inspector", "base-distribution"})
        self.assertEqual(planned - installing, set())
        # 57 after wave 4; round 2 adds four rows and installs both former split owners.
        self.assertEqual(len(planned), 63)

    def test_a_split_slot_that_is_changed_to_installing_wires_its_piece_and_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            keys = ("claude/mcp/server/socraticode", "codex/config/mcp_servers.socraticode.command")

            def wired():
                write_blocks(root)  # the names a block is filtered by follow the manifest
                results, _, _, errors, _ = cfg.analyse(root)
                self.assertEqual(errors, [])
                return {v.piece.key: v.wired for v in results}

            def servers():
                plan = cfg.analyse(root)
                files = cfg.render(root, plan[0], plan[2], cfg.host_values(EXAMPLE_HOST, plan[2], None, []))
                return json.loads(files["mcp-servers.json"])["mcpServers"], files["codex.config.toml"]

            # Wave 3's split-slot interim installs both semble and SocratiCode.
            before = wired()
            self.assertEqual([before[k] for k in keys], [True, True])
            self.assertIn("socraticode", servers()[0])
            self.assertIn("socraticode", servers()[1])
            manifest = root / cfg.MANIFEST_REL
            original = manifest.read_text()

            def install(data, default="SocratiCode"):
                row = next(r for r in data["slots"] if r["slot_id"] == "code-search" and r["catalog"] == "foundation")
                row.update(installs_nothing_extra=False, state="definitive", default=default)
                row["resolution"] = {"outcome": "final"}
                row.pop("interim", None)       # a decided default replaces the interim install
            edit_json(manifest, install)
            after = wired()
            self.assertEqual([after[k] for k in keys], [True, True])
            self.assertIn("socraticode", servers()[0])
            self.assertIn("[mcp_servers.socraticode]", servers()[1])
            manifest.write_text(original, encoding="utf-8")
            restored = wired()
            self.assertEqual([restored[k] for k in keys], [True, True])
            self.assertIn("socraticode", servers()[0])
            # The slot installs a different owner: the piece for SocratiCode stays out, and the check says so.
            edit_json(manifest, lambda data: install(data, default="semble"))
            other = wired()
            self.assertEqual([other[k] for k in keys], [False, False])
            self.assertTrue(any("installs 'semble'" in w for w in cfg.analyse(root)[4]))

    def test_a_slot_that_stops_installing_unwires_its_pieces(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            edit_json(root / cfg.MANIFEST_REL, lambda data: next(
                r for r in data["slots"] if r["slot_id"] == "serena" and r["catalog"] == "foundation").update(
                installs_nothing_extra=True))
            results = {v.piece.key: v for v in cfg.analyse(root)[0]}
        self.assertFalse(results["claude/mcp/server/serena"].wired)
        self.assertFalse(results["codex/config/mcp_servers.serena.command"].wired)
        self.assertIn("installs nothing extra", results["claude/mcp/server/serena"].reason)

    def test_the_slots_the_map_names_are_foundation_slots_and_the_unwired_ones_do_not_install(self):
        rows = foundation_rows()
        entries = json.loads(MAP.read_text())["entries"]
        slots = {e["wiring"][5:] for e in entries if e["wiring"].startswith("slot:")}
        self.assertTrue(slots <= set(rows), slots - set(rows))
        not_installing = {s for s in slots if not cfg.installs(rows[s])}
        self.assertEqual(not_installing, set())
        # Wave 3 gives context-supply its owner default and adds five slots with client configuration pieces.
        self.assertEqual({s for s in slots if cfg.installs(rows[s])},
                         {"serena", "tobi-qmd", "otel-collector-contrib", "gpt-gateway", "claude-code", "mise",
                          "mcp-inspector", "context-supply", "memory-owner", "code-search", "statusline",
                          "container-engine", "command-output", "output-compression", "code-index", "code-graph",
                          "api-docs", "playwright-cli"})
        self.assertEqual({s for s in slots if rows[s].get("interim")}, {"memory-owner", "code-search"})


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "render"
        code, out, err = run_main("--render", "--host", EXAMPLE_HOST, "--out", str(cls.out))
        assert code == 0, err
        cls.files = {path.name: path.read_text(encoding="utf-8") for path in cls.out.iterdir()}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_render_writes_each_file_and_is_deterministic(self):
        self.assertEqual(set(self.files), {"settings.json", "settings.linux-wsl2.overlay.json", "mcp-servers.json",
                                           "codex.config.toml", "codex.hooks.json", "codex.stack-worker.config.toml",
                                           "codex.omniroute.config.toml", "wiring.json", "claude-user-instructions.md",
                                           "codex-user-instructions.md"})
        for piece, name in cfg.RENDERED_BLOCKS.items():
            self.assertEqual(self.files[name], (ROOT / cfg.GENERATED_BLOCKS[piece]).read_text(encoding="utf-8"), name)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run_main("--render", "--host", EXAMPLE_HOST, "--out", tmp)[0], 0)
            again = {path.name: path.read_text(encoding="utf-8") for path in Path(tmp).iterdir()}
        self.assertEqual(again, self.files)

    def test_every_file_parses_and_holds_no_placeholder(self):
        for name, text in self.files.items():
            with self.subTest(file=name):
                if name.endswith(".json"):
                    json.loads(text)
                elif name.endswith(".toml"):
                    tomllib.loads(text)
                else:
                    self.assertNotIn("${", text)
        for name in ("settings.json", "codex.config.toml"):
            self.assertNotIn("${", self.files[name])
            self.assertNotIn("$$", self.files[name])

    def test_settings_keep_the_practice_pieces_and_drop_the_old_profile_pieces(self):
        settings = json.loads(self.files["settings.json"])
        # The user's choice of 2026-10-04, Opus 5.5, pinned by its full model name (the map's model entry overrides the
        # shared template's opus[1m], which other hosts keep); the advisor is Opus 5.5 too, by the map's override, the user's
        # decision of 2026-10-04 and the value NativeStack carries.
        self.assertEqual(settings["model"], "claude-opus-5-5")
        self.assertEqual(settings["advisorModel"], "opus")
        self.assertEqual(json.loads((ROOT / "adoption/templates/claude.settings.template.json").read_text())["model"],
                         "opus[1m]")
        self.assertEqual(settings["effortLevel"], "xhigh")
        self.assertNotIn("defaultMode", settings["permissions"])        # an authorization setting: not by default
        self.assertNotIn("allow", settings["permissions"])              # an allow rule is one too
        self.assertNotIn("skipDangerousModePermissionPrompt", settings)
        # The wave-2 rows: context-mode's plugin (an interim install) and claude-hud 0.10.0 (the statusline row), whose
        # status line is the command its setup.mjs writes; the codex plugin for Claude Code stays out.
        self.assertEqual(settings["enabledPlugins"], {"context-mode@context-mode": True, "claude-hud@claude-hud": True,
                                                      "cc-plugin-you-should-know@builtin": True})
        self.assertEqual(sorted(settings["extraKnownMarketplaces"]), ["claude-hud", "context-mode"])
        self.assertEqual(settings["extraKnownMarketplaces"]["claude-hud"]["source"]["ref"], "v0.10.0")
        self.assertEqual(settings["statusLine"], {
            "type": "command", "refreshInterval": 5,
            "command": "'/home/example/.local/share/mise/installs/node/24.21.0/bin/node' "
                       "'/home/example/.claude/plugins/claude-hud/statusline.mjs'"})
        events = {event: [h["command"] for g in groups for h in g["hooks"]] for event, groups in settings["hooks"].items()}
        commands = [command for v in events.values() for command in v]
        # Each hook runs a file the repository copies, ai-memory (an interim install) at the link the plan's
        # memory-owner row makes, rtk (the owner's directive of 2026-10-04), or the logging-only ConfigChange audit command
        # that NativeStack runs; context-mode writes its own cache-heal hook.
        ai_memory = "/home/example/.local/bin/ai-memory "
        audit = "jq -c '{timestamp: now | todate, source: .source, file: .file_path}' >> ~/claude-config-audit.log || true"
        self.assertEqual(events["ConfigChange"], [audit])
        self.assertEqual(sum(".claude/hooks/" in command for command in commands), 4)
        self.assertTrue(all(".claude/hooks/" in command or command.startswith(ai_memory) or command in ("rtk hook claude", audit)
                            for command in commands), commands)
        self.assertTrue(any(command.startswith(ai_memory) for command in events["SessionStart"]), events)
        self.assertEqual([command for command in commands if "cache-heal" in command], [])
        self.assertFalse([e for e in settings["permissions"]["deny"] if e.startswith("Agent(codex")])
        self.assertEqual(len([e for e in settings["permissions"]["deny"] if e.startswith("Bash(rtk git push")]), 6)
        self.assertIn("Bash(git push --force *)", settings["permissions"]["deny"])
        self.assertEqual(settings["env"]["MCP_AUTO_OPEN_ENABLED"], "false")
        # rtk and agent teams: the owner's directive of 2026-10-04 (docs/decisions/2026-10-04-new-wsl-token-layer-default.md).
        self.assertEqual(settings["env"]["RTK_TELEMETRY_DISABLED"], "1")
        self.assertEqual(settings["env"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"], "1")
        self.assertEqual(events["PreToolUse"][0], "rtk hook claude")
        # The token-lane carriers are this repository's own adaptation, so the clean default holds them out (the owner's
        # directive of 2026-10-04): neither the SubagentStart nor the SessionStart hook runs a carrier file.
        self.assertEqual([c for c in commands if "token-lanes" in c], [])
        self.assertTrue([c for c in events["SessionStart"] if "currency-due-notice.py" in c], events)

    def test_the_overlay_keeps_its_bell_and_the_notification_channel(self):
        overlay = json.loads(self.files["settings.linux-wsl2.overlay.json"])
        self.assertEqual(overlay, json.loads((ROOT / cfg.TEMPLATES["claude/overlay"]).read_text()))

    def test_the_wired_servers_are_registered_and_serena_and_qmd_by_the_command_their_readmes_give(self):
        servers = json.loads(self.files["mcp-servers.json"])["mcpServers"]
        # The owner-selected token stack joins Serena, QMD and the interim memory/search installs.
        self.assertEqual(list(servers), ["ai-memory", "serena", "socraticode", "headroom", "codebase-memory", "qmd",
                                         "jcodemunch", "semble", "chrome-devtools"])
        self.assertEqual(servers["serena"]["command"], "serena")
        self.assertEqual(servers["serena"]["args"][:1] + servers["serena"]["args"][3:6],
                         ["start-mcp-server", "--project-from-cwd", "--context", "claude-code"])
        self.assertEqual((servers["qmd"]["command"], servers["qmd"]["args"][-1]), ("qmd", "mcp"))
        host = json.loads((ROOT / "adoption/hosts/example.json").read_text())
        self.assertEqual(servers["ai-memory"], {"type": "http", "url": f"http://{host['AI_MEMORY_URL']}/mcp"})
        # semble: the pinned model's local snapshot and Claude Code's own cache (wave-2 code-search ruling, changes 4, 5);
        # ${HOME} is filled when install_claude_profile.py registers the file.
        self.assertEqual((servers["semble"]["command"], servers["semble"]["args"]), ("semble", []))
        self.assertEqual(servers["semble"]["env"], {
            "SEMBLE_MODEL_NAME": "${HOME}/.local/share/semble/potion-code-16M-v2-e9d2a44c",
            "SEMBLE_CACHE_LOCATION": "${HOME}/.cache/semble-claude"})
        config = tomllib.loads(self.files["codex.config.toml"])
        # semble comes from the new distribution's additions, merged after the shared template's servers.
        self.assertEqual(list(config["mcp_servers"]), ["serena", "ai-memory", "socraticode", "headroom", "codebase-memory",
                                                      "qmd", "context-mode", "jcodemunch", "semble", "chrome-devtools"])
        # Round-2 browser verdict: one stdio server serves automation and diagnostics.
        chrome_args = ["-y", "chrome-devtools-mcp@1.10.1", "--headless", "--isolated", "--no-usage-statistics", "--no-performance-crux"]
        self.assertEqual(servers["chrome-devtools"], {"type": "stdio", "command": "npx", "args": chrome_args})
        self.assertEqual(config["mcp_servers"]["chrome-devtools"], {"command": "npx", "args": chrome_args})
        pinned_search = host["ECO_ROOT"] + "/tools/socraticode-1.15.0/lib/node_modules/socraticode/dist/index.js"
        self.assertEqual(servers["socraticode"]["args"], [pinned_search.replace(host["ECO_ROOT"], "${ECO_ROOT}")])
        self.assertEqual(config["mcp_servers"]["socraticode"]["args"], [pinned_search])
        # jCodeMunch at user scope, with the documented opt-out of its anonymous savings counter in the server's env block
        # (the user's directive of 2026-10-04; JCODEMUNCH_SHARE_SAVINGS=0, CONFIGURATION.md at the pinned revision).
        self.assertEqual(servers["jcodemunch"], {"type": "stdio", "command": "${ECO_ROOT}/bin/jcodemunch-mcp", "args": [],
                                                 "env": {"JCODEMUNCH_SHARE_SAVINGS": "0"}})
        # The Codex entry is the one the project template registers per project (startup allowance, the three verbs of the
        # front door, the savings opt-out); its approval mode is an authorization piece, written only with the option.
        self.assertEqual(config["mcp_servers"]["jcodemunch"], {
            "command": host["ECO_ROOT"] + "/bin/jcodemunch-mcp", "startup_timeout_sec": 60,
            "enabled_tools": ["route", "menu", "order"],
            "env": {"RTK_TELEMETRY_DISABLED": "1", "PATH": config["mcp_servers"]["context-mode"]["env"]["PATH"],
                    "JCODEMUNCH_SHARE_SAVINGS": "0"}})
        self.assertTrue(config["mcp_servers"]["jcodemunch"]["env"]["PATH"].startswith(host["ECO_ROOT"] + "/bin:"))
        self.assertEqual(config["mcp_servers"]["ai-memory"], {"url": f"http://{host['AI_MEMORY_URL']}/mcp"})
        semble = config["mcp_servers"]["semble"]
        self.assertEqual((semble["command"], semble["enabled_tools"]), ("semble", ["search", "find_related"]))
        self.assertEqual(semble["env"]["SEMBLE_CACHE_LOCATION"], "/home/example/.cache/semble-codex")
        self.assertEqual(semble["env"]["SEMBLE_MODEL_NAME"], servers["semble"]["env"]["SEMBLE_MODEL_NAME"].replace(
            "${HOME}", "/home/example"))
        for server in config["mcp_servers"].values():      # an approval mode is an authorization setting
            self.assertNotIn("default_tools_approval_mode", server)
        self.assertEqual(config["mcp_servers"]["serena"]["command"], "serena")
        self.assertIn("--context", config["mcp_servers"]["serena"]["args"])
        self.assertEqual(config["mcp_servers"]["serena"]["args"][config["mcp_servers"]["serena"]["args"].index(
            "--context") + 1], "codex")

    def test_the_codex_config_meets_what_the_codex_home_tool_requires(self):
        config = tomllib.loads(self.files["codex.config.toml"])
        self.assertIs(config["features"]["daemon_auto_start"], False)
        # The changelog parity of 2026-10-04: the experimental allowance-history feature (the shared template's, on both hosts)
        # and the standard tier chosen in its 2026-10-05 amendment (this distribution's additions).
        self.assertIs(config["features"]["analytics_plan_history"], True)
        self.assertEqual(config["service_tier"], "default")
        eco = json.loads((ROOT / "adoption/hosts/example.json").read_text())["ECO_ROOT"]
        self.assertEqual(config["shell_environment_policy"]["set"]["PATH"].split(":")[0], eco + "/bin")
        self.assertNotIn("projects", config)
        # context-mode (an interim install): its marketplace, its plugin with the plugin's own server off (the user-scope
        # entry serves it), and the trust of its six hooks, the only [hooks.state] entries rendered (wave-2 context ruling,
        # change 9; codex_home.py leaves them out of a file it creates, and the merge adds them).
        self.assertEqual(list(config["marketplaces"]), ["context-mode"])
        self.assertEqual(config["plugins"], {"context-mode@context-mode": {
            "enabled": True, "mcp_servers": {"context-mode": {"enabled": False}}}})
        self.assertEqual(list(config["hooks"]), ["state"])
        self.assertEqual(sorted(key.rsplit(":", 3)[1] for key in config["hooks"]["state"]),
                         ["post_tool_use", "pre_compact", "pre_tool_use", "session_start", "stop", "user_prompt_submit"])
        self.assertTrue(all(key.startswith("context-mode@context-mode:") for key in config["hooks"]["state"]))
        # The footer (the statusline row) and the shell environment policy (wave-2 custody ruling, change 7).
        self.assertEqual(config["tui"]["status_line"], ["model-with-reasoning", "project-name", "git-branch",
                                                        "context-used", "five-hour-limit", "weekly-limit"])
        policy = config["shell_environment_policy"]
        self.assertEqual(policy["inherit"], "none")
        self.assertEqual(sorted(policy["set"]), ["DOCKER_HOST", "HOME", "LANG", "MCP_AUTO_OPEN_ENABLED", "PATH",
                                                 "RTK_TELEMETRY_DISABLED", "TERM", "TMPDIR", "WSL_DISTRO_NAME", "XDG_RUNTIME_DIR"])
        self.assertEqual(policy["set"]["HOME"], "/home/example")
        self.assertEqual(policy["set"]["WSL_DISTRO_NAME"], "NativeStack2604")
        # The user's systemd runtime directory, for systemctl --user and the messaging courier, and the rootless Docker
        # socket in it (wave-2 custody ruling, change 7; synthesis X12): the id of the user the tool runs as.
        self.assertEqual(policy["set"]["XDG_RUNTIME_DIR"], f"/run/user/{os.getuid()}")
        self.assertRegex(policy["set"]["XDG_RUNTIME_DIR"], r"\A/run/user/[0-9]+\Z")
        self.assertEqual(policy["set"]["DOCKER_HOST"], f"unix://{policy['set']['XDG_RUNTIME_DIR']}/docker.sock")
        self.assertEqual(config["model"], "gpt-6.1-sol")
        self.assertNotIn("check_for_update_on_startup", config)
        self.assertEqual(self.files["codex.hooks.json"].strip().replace(" ", "").replace("\n", ""), '{"hooks":{}}')

    def test_the_toml_writer_reads_back_to_the_data_it_was_given(self):
        data = {"a": "x\"y\\zé", "b": [1, 2], "c": True, "t": {"k": "v", "dotted.key": 1, "sub": {"n": 2}},
                "empty": {}, "list": ["a", "b"], "n": 3.5}
        self.assertEqual(tomllib.loads(cfg.emit_toml(data, "# h")), data)
        with self.assertRaises(cfg.ConfigError):
            cfg.emit_toml({"bad": object()}, "")

    def test_the_stack_worker_profile_keeps_the_wired_servers_and_the_settings_that_need_no_tool(self):
        profile = tomllib.loads(self.files["codex.stack-worker.config.toml"])
        self.assertEqual(set(profile), {"model", "model_reasoning_effort", "web_search", "mcp_servers",
                                        "shell_environment_policy"})
        self.assertEqual(profile["shell_environment_policy"], {"set": {"CHUB_TELEMETRY": "0", "CHUB_FEEDBACK": "0"}})
        # All installed servers' worker policies remain; without the option no approval mode.
        self.assertEqual(profile["mcp_servers"], {
            "serena": {"startup_timeout_sec": 60, "required": True},
            "codebase-memory": {"startup_timeout_sec": 60},
            "ai-memory": {"enabled_tools": ["memory_query", "memory_read_page", "memory_recent", "memory_status",
                                            "memory_briefing"]},
            "socraticode": {"enabled_tools": ["codebase_search", "codebase_status", "codebase_list_projects", "codebase_health"],
                             "env": {"SOCRATICODE_WATCHER": "manual"}},
            "headroom": {"enabled_tools": ["headroom_compress", "headroom_retrieve", "headroom_stats"]},
            "context-mode": {"disabled_tools": ["ctx_upgrade", "ctx_purge"]}})

    def test_no_service_reference_names_a_tool_that_the_manifest_does_not_install(self):
        names = unwired_names_independently()
        # Reproduced failure: hcom was still asserted unwired after wave 5 made
        # it an installed owner. Keep the original name set and verify both
        # partitions against that decision, rather than dropping its name.
        referenced = {"codex-plugin-cc", "codex-rescue", "context-mode-cache-heal", "hcom", "openai-codex"}
        consensus = json.loads((ROOT / "evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json").read_text())
        adopted = next(e["owner_default"] for e in consensus["wave5"]["amend_rows"]
                       if e["slot_id"] == "agent-messaging")
        messaging = foundation_rows()["agent-messaging"]
        self.assertEqual(messaging["default"], adopted["default"])
        self.assertFalse(messaging["installs_nothing_extra"])
        self.assertTrue(cfg.installs(messaging))
        installed_names = {adopted["default"].split()[0].lower()}
        self.assertEqual(installed_names, {"hcom"})
        self.assertEqual(referenced & {n.lower() for n in names}, referenced - installed_names)
        self.assertEqual(installed_names & {n.lower() for n in names}, set())
        # The owner defaults and interim installs are wired, so their names are no longer scanned for.
        self.assertEqual({"ai-memory", "context-mode", "claude-hud", "semble", "rtk", "socraticode", "headroom",
                          "codebase-memory", "jcodemunch", "chub"} & {n.lower() for n in names}, set())
        with tempfile.TemporaryDirectory() as tmp:    # the render with the authorization settings is scanned too
            self.assertEqual(run_main("--render", "--host", EXAMPLE_HOST, "--out", tmp, "--with-authorization-settings")[0], 0)
            with_option = {path.name: path.read_text(encoding="utf-8") for path in Path(tmp).iterdir()}
        self.assertIn("danger-full-access", with_option["codex.config.toml"])
        for label, files in (("without", self.files), ("with", with_option)):
            for name, text in files.items():
                if name == "wiring.json":
                    continue
                # The scan is the tool's: --check runs the same function on the same renders, with the tool's names.
                self.assertEqual(cfg.rendered_name_hits(name, text, names), [], f"{label} the option: {name}")

    def test_the_same_scan_finds_those_names_in_the_old_full_profile_render(self):
        # Negative control: the render of the old workstation profile (every template piece) is full of them.
        values = render_config.load_host_values(EXAMPLE_HOST)
        old = render_config.render_all(values)
        names = unwired_names_independently()
        found = {n for text in old.values() for n in names if name_hits(text, [n])}
        self.assertTrue({"codex-plugin-cc", "codex-rescue", "context-mode-cache-heal", "openai-codex"} <= {
            n.lower() for n in found}, found)

    def test_the_ports_are_the_install_plans(self):
        ports = plan_ports()
        self.assertEqual(ports, {"http": 21318, "grpc": 21317, "gateway": 21128})
        settings = json.loads(self.files["settings.json"])
        self.assertEqual(settings["env"]["OTEL_EXPORTER_OTLP_ENDPOINT"], f"http://127.0.0.1:{ports['http']}")
        config = tomllib.loads(self.files["codex.config.toml"])
        self.assertEqual(config["otel"]["exporter"]["otlp-http"]["endpoint"], f"http://127.0.0.1:{ports['http']}/v1/logs")
        self.assertEqual(config["otel"]["metrics_exporter"]["otlp-http"]["endpoint"],
                         f"http://127.0.0.1:{ports['http']}/v1/metrics")
        omniroute = tomllib.loads(self.files["codex.omniroute.config.toml"])
        self.assertEqual(omniroute["model_providers"]["omniroute"]["base_url"], f"http://127.0.0.1:{ports['gateway']}/v1")
        for workstation in ("14318", "24318", "20128", "20129"):
            for name, text in self.files.items():
                if name != "wiring.json":
                    self.assertNotIn(workstation, text, name)
        # One port truth: the host file that F8 renders from the template names the port the settings carry.
        host = json.loads(string.Template((ROOT / cfg.HOST_TEMPLATE_REL).read_text()).substitute(WSL_USER="example"))
        self.assertEqual(f"http://{host['OTEL_ENDPOINT']}", settings["env"]["OTEL_EXPORTER_OTLP_ENDPOINT"])
        self.assertEqual(host["OTEL_ENDPOINT"], f"127.0.0.1:{ports['http']}")
        # ai-memory's port is the host file's AI_MEMORY_URL in both clients (the example host names the repository
        # default); the new distribution's host template names 29374, the bind of the plan's memory-owner row (X5).
        example = json.loads((ROOT / "adoption/hosts/example.json").read_text())["AI_MEMORY_URL"]
        self.assertEqual(json.loads(self.files["mcp-servers.json"])["mcpServers"]["ai-memory"]["url"],
                         f"http://{example}/mcp")
        self.assertEqual(config["mcp_servers"]["ai-memory"]["url"], f"http://{example}/mcp")
        self.assertEqual(host["AI_MEMORY_URL"], "127.0.0.1:29374")
        memory = next(row for row in json.loads((ROOT / cfg.PLAN_REL / "install-plan.json").read_text())["owners"]
                      if row["slot"] == "memory-owner")
        self.assertTrue(any(f'bind = "{host["AI_MEMORY_URL"]}"' in command for command in memory["commands"]),
                        memory["commands"])

    def test_the_render_follows_the_plan_and_refuses_a_plan_that_states_a_port_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            base = root / cfg.PLAN_REL
            otel = base / "config" / "otel.yaml"
            otel.write_text(otel.read_text().replace("21318", "21999"), encoding="utf-8")
            edit_json(base / "install-plan.json", lambda d: next(r for r in d["owners"] if r["slot"] ==
                      "otel-collector-contrib")["service"].update(port_setting=next(
                          r for r in d["owners"] if r["slot"] == "otel-collector-contrib")["service"][
                              "port_setting"].replace("21318", "21999")))
            results, _, plan, errors, _ = cfg.analyse(root)
            self.assertEqual(errors, [])
            files = cfg.render(root, results, plan, cfg.host_values(EXAMPLE_HOST, plan, None, []))
            self.assertEqual(json.loads(files["settings.json"])["env"]["OTEL_EXPORTER_OTLP_ENDPOINT"],
                             "http://127.0.0.1:21999")
            # The plan's two statements of a port then differ: the tool refuses to choose.
            (base / "config" / "omniroute.env.example").write_text("export PORT=21129\n", encoding="utf-8")
            with self.assertRaises(cfg.ConfigError):
                cfg.load_plan(root)

    def test_the_host_template_carries_the_plans_port_and_a_note_names_a_difference(self):
        self.assertIsNone(cfg.host_template_note(ROOT, cfg.load_plan(ROOT)))
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            template = root / cfg.HOST_TEMPLATE_REL
            template.write_text(template.read_text().replace("127.0.0.1:21318", "127.0.0.1:24318"), encoding="utf-8")
            note = cfg.host_template_note(root, cfg.load_plan(root))
        self.assertIn("24318", note)
        self.assertIn("21318", note)

    def test_a_host_name_with_a_path_in_it_is_refused(self):
        for mode in (["--render", "--out", "x"], ["--apply", "--dry-run"]):
            with self.subTest(mode=mode):
                self.assertEqual(run_main(*mode, "--host", "../example")[0], 2)

    def test_every_wired_hook_runs_a_file_the_repository_copies_with_its_checksum(self):
        settings = json.loads(self.files["settings.json"])
        overlay = json.loads(self.files["settings.linux-wsl2.overlay.json"])
        referenced = set()
        for data in (settings, overlay):
            for groups in data["hooks"].values():
                for group in groups:
                    for hook in group["hooks"]:
                        referenced.update(re.findall(r"\.claude/hooks/([A-Za-z0-9_.-]+)", hook["command"]))
        self.assertEqual(referenced, {"secret_path_guard.py", "effort-default-guard.py", "currency-due-notice.py"})
        for name in referenced:
            source = icp.HOOKS[name]
            self.assertTrue(source.is_file(), name)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), icp.expected_sha256(source), name)

    def test_the_token_lane_carriers_are_held_out_of_the_shared_template_and_the_default_install(self):
        # The carriers are this repository's own adaptation, not a feature of an upstream tool, so the owner's directive of
        # 2026-10-04 (a clean install: upstream installers with upstream defaults) holds them out of every host's default
        # (docs/decisions/2026-10-04-claude-template-holds-out-token-lane-carriers.md): the shared Claude settings template
        # registers neither hook and install_claude_profile.py copies none of the nine files unless a caller names it, so
        # the builder has no carrier piece to wire or to leave unwired, and no rendered file, the wiring record included,
        # runs or names one.
        self.assertEqual([v.piece.key for v in cfg.analyse(ROOT)[0] if "token-lanes" in v.piece.key], [])
        for name, text in self.files.items():
            self.assertNotIn("token-lanes", text, name)

    def test_a_checksum_that_does_not_match_fails_the_check_and_the_install(self):
        def wrong_for_the_guard(source):
            return "0" * 64 if source.name == "secret_path_guard.py" else hashlib.sha256(source.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(icp, "expected_sha256", wrong_for_the_guard):
            errors = cfg.analyse(ROOT)[3]
            with self.assertRaises(icp.InstallError) as caught:
                icp.install_guards(Path(tmp), False, ["secret_path_guard.py"])
            self.assertFalse((Path(tmp) / ".claude").exists())
        self.assertTrue(any("does not match its row" in e for e in errors), errors)
        self.assertIn("refusing to install", str(caught.exception))

# A coarser sentence splitter than the tool's (it splits after any .!? and whitespace), so that no piece of a kept line
# spans the junction where a sentence was left out.
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
SENTENCE_STOP = r"[.!?][\"')\]`*_]*"


def source_lines(piece: str) -> list:
    return cfg.block_text(ROOT, piece).split("\n")


def generated_text(piece: str) -> str:
    return (ROOT / cfg.GENERATED_BLOCKS[piece]).read_text(encoding="utf-8")


def find_whole(source: str, piece: str, position: int) -> int:
    """The end of the first occurrence of piece at or after position that is whole sentences of source (it starts the line
    or follows a sentence end, and it ends the line or a sentence); -1 when there is none."""
    start = source.find(piece, position)
    while start >= 0:
        end = start + len(piece)
        begins = start == 0 or re.search(SENTENCE_STOP + r"\s+$", source[:start]) is not None
        ends = end == len(source) or (re.search(SENTENCE_STOP + "$", source[:end]) is not None
                                      and source[end:end + 1].isspace())
        if begins and ends:
            return end
        start = source.find(piece, start + 1)
    return -1


def line_is_verbatim(line: str, sources: list) -> bool:
    """A kept line is a whole source line, or what is left of one after whole sentences went: its sentences are found
    unchanged and in order in one source line."""
    if line in sources:
        return True
    pieces = SENTENCE_SPLIT.split(line)
    for source in sources:
        position = 0
        for piece in pieces:
            position = find_whole(source, piece, position)
            if position < 0:
                break
        else:
            return True
    return False


class TemplateAdditionsTests(unittest.TestCase):
    """The new distribution's additions (adoption/new-wsl/templates/): keys only this tool renders, so the shared templates
    stay what render_config.py, install_claude_profile.py and the bootstrap render on every other host."""

    def test_the_shared_templates_carry_none_of_the_additions(self):
        codex = tomllib.loads((ROOT / cfg.TEMPLATES["codex/config"]).read_text(encoding="utf-8"))
        self.assertNotIn("inherit", codex["shell_environment_policy"])
        self.assertEqual(sorted(codex["shell_environment_policy"]["set"]),
                         ["MCP_AUTO_OPEN_ENABLED", "PATH", "RTK_TELEMETRY_DISABLED"])
        self.assertNotIn("semble", codex["mcp_servers"])
        self.assertEqual(codex["mcp_servers"]["ai-memory"], {"url": "http://${AI_MEMORY_URL}/mcp"})
        self.assertNotIn("semble", json.loads((ROOT / cfg.TEMPLATES["claude/mcp"]).read_text())["mcpServers"])
        self.assertNotIn("allow", json.loads((ROOT / cfg.TEMPLATES["claude/settings"]).read_text())["permissions"])
        for group, rel in cfg.TEMPLATE_ADDITIONS.items():     # each addition adds a key its template lacks
            base = leaves(cfg.read_template(ROOT / cfg.TEMPLATES[group]))
            extra = leaves({k: v for k, v in cfg.read_template(ROOT / rel).items() if k != "_comment"})
            self.assertTrue(extra, rel)
            self.assertEqual(set(base) & set(extra), set(), rel)
        # The render of the shared Codex template that every other host takes has no policy of the new distribution.
        shared = tomllib.loads(render_config.render_one(ROOT / cfg.TEMPLATES["codex/config"],
                                                        render_config.load_host_values(EXAMPLE_HOST)))
        self.assertNotIn("inherit", shared["shell_environment_policy"])
        self.assertNotIn("semble", shared["mcp_servers"])

    def test_the_render_merges_the_additions_into_their_templates(self):
        results, *_ = cfg.analyse(ROOT)
        keys = {v.piece.key for v in results}
        for key in ("codex/config/shell_environment_policy.inherit", "codex/config/shell_environment_policy.set.XDG_RUNTIME_DIR",
                    "codex/config/shell_environment_policy.set.DOCKER_HOST", "codex/config/mcp_servers.semble.command",
                    "codex/config/mcp_servers.ai-memory.default_tools_approval_mode", "claude/mcp/server/semble",
                    "claude/settings/permission/allow/mcp__semble__search"):
            self.assertIn(key, keys)
        self.assertFalse([key for key in keys if "_comment" in key])    # a file's note is not a piece

    def test_an_addition_that_names_a_key_of_its_template_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            path = root / cfg.TEMPLATE_ADDITIONS["codex/config"]
            path.write_text(path.read_text(encoding="utf-8") + '\n[mcp_servers.serena]\ncommand = "other"\n',
                            encoding="utf-8")
            with self.assertRaises(cfg.ConfigError) as caught:
                cfg.analyse(root)
            self.assertIn("mcp_servers.serena.command", str(caught.exception))
            code, _, err = run_main("--check", "--root", str(root))
        self.assertEqual(code, 1)
        self.assertIn("which its shared template defines too", err)


class InstructionBlockTests(unittest.TestCase):
    """The two instruction blocks as this distribution installs them: each source with every unit that names a tool that
    is not wired left out, and nothing written in its place."""

    PIECES = (cfg.CLAUDE_MD_PIECE, cfg.CODEX_MD_PIECE)
    SYNTHETIC = ("# Title\n\nKeep this sentence. Drop alpha-tool here. Keep the last one.\n\n## Mixed\n\n"
                 "- A bullet that names beta.\n"
                 "- A bullet that stays. Its second sentence names alpha-tool. A third stays.\n"
                 "- Its first sentence names beta. A later sentence stays.\n\n"
                 "## Wrapped\n\nA wrapped paragraph that runs on\nand names alpha-tool in\nits second line.\n")

    def test_the_committed_blocks_are_what_the_filter_makes_of_their_sources(self):
        results, manifest, *_ = cfg.analyse(ROOT)
        names = cfg.unwired_names(results, manifest)
        self.assertEqual(cfg.block_errors(ROOT, names), [])
        verdicts = {v.piece.key: v for v in results}
        for piece, (relative, text, dropped) in cfg.generate_blocks(ROOT, names).items():
            self.assertEqual((ROOT / relative).read_text(encoding="utf-8"), text, relative)
            self.assertEqual(dropped, [], relative)  # every named harness is now selected
            self.assertTrue(verdicts[piece].wired, piece)
            self.assertIn("filtered", verdicts[piece].reason)

    def test_a_stale_or_missing_committed_block_fails_the_check_and_the_apply_until_it_is_written_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            self.assertEqual(cfg.analyse(root)[3], [])
            source = root / cfg.BLOCK_TEXT_REL[cfg.CLAUDE_MD_PIECE]
            source.write_text(source.read_text() + "\nAn added line.\n", encoding="utf-8")
            stale = [e for e in cfg.analyse(root)[3] if "is stale" in e]
            self.assertEqual(len(stale), 1, stale)
            self.assertIn("claude-user-instructions.md", stale[0])
            code, _, err = run_main("--check", "--root", str(root))
            self.assertEqual(code, 1)
            self.assertIn("is stale", err)
            code, _, err = run_main("--apply", "--dry-run", "--host", EXAMPLE_HOST, "--home", str(Path(tmp) / "home"),
                                    "--root", str(root))
            self.assertEqual(code, 1)
            self.assertIn("apply refused", err)
            write_blocks(root)
            self.assertEqual(cfg.analyse(root)[3], [])
            self.assertIn("An added line.", (root / cfg.GENERATED_BLOCKS[cfg.CLAUDE_MD_PIECE]).read_text())
            (root / cfg.GENERATED_BLOCKS[cfg.CODEX_MD_PIECE]).unlink()
            self.assertTrue(any("is missing" in e for e in cfg.analyse(root)[3]))
            code, out, _ = run_main("--write-blocks", "--root", str(root))
            self.assertEqual(code, 0)
            self.assertIn("wrote", out)
            self.assertEqual(cfg.analyse(root)[3], [])

    def test_every_kept_line_is_in_the_source_verbatim(self):
        for piece in self.PIECES:
            sources = source_lines(piece)
            kept = [line for line in generated_text(piece).split("\n") if line.strip()]
            # At least the philosophy core's six lines (heading, bold rule, four bullets) since 2026-10-08.
            self.assertGreaterEqual(len(kept), 6, piece)
            self.assertEqual([line for line in kept if not line_is_verbatim(line, sources)], [], piece)
        # Controls: the same check rejects a reworded line, a line with an added sentence, a sentence cut off inside a
        # word or after a word, and a line the source never had.
        sources = source_lines(cfg.CODEX_MD_PIECE)
        line = next(source for source in sources if source.startswith("- Research before acting:"))
        self.assertTrue(line_is_verbatim(line, sources))
        for changed in (line.replace("upstream", "Upstream"), line + " An added sentence.", line[:-12], line[:-15],
                        "A line the source never had.", line.replace(". Never rebuild", ". Always rebuild")):
            self.assertNotEqual(changed, line)
            self.assertFalse(line_is_verbatim(changed, sources), changed)
        # A line with a sentence taken out of its middle is what a filter may produce, and passes.
        first, second, third = SENTENCE_SPLIT.split(line)[:3]
        self.assertTrue(line_is_verbatim(f"{first} {third}", sources))
        self.assertFalse(line_is_verbatim(f"{third} {first}", sources))

    def test_no_tool_that_is_not_wired_is_named_in_either_block(self):
        names = unwired_names_independently()
        self.assertTrue({"codex-plugin-cc", "codex-rescue", "context-mode-cache-heal", "openai-codex", "phoenix"} <= {
            n.lower() for n in names}, names)
        for piece in self.PIECES:
            self.assertEqual(name_hits("\n".join(source_lines(piece)), names), [], piece)
            self.assertEqual(name_hits(generated_text(piece), names), [], piece)
        # Control: the same scan finds a name that is added back, whole or in a different case.
        self.assertIn("Phoenix", name_hits(generated_text(cfg.CODEX_MD_PIECE) + "Use phoenix.\n", names))
        self.assertIn("Phoenix", name_hits(generated_text(cfg.CLAUDE_MD_PIECE) + "Ask PHOENIX.\n", names))

    def test_the_kept_and_the_dropped_text_together_are_the_whole_source(self):
        results, manifest, *_ = cfg.analyse(ROOT)
        for piece, (relative, _, dropped) in cfg.generate_blocks(ROOT, cfg.unwired_names(results, manifest)).items():
            source = "\n".join(source_lines(piece))
            left_out = " ".join(unit.text for unit in dropped)
            self.assertEqual(Counter(source.split()), Counter(generated_text(piece).split()) + Counter(left_out.split()),
                             piece)

    def test_every_dropped_unit_names_a_tool_that_is_not_wired_or_is_a_heading_left_with_nothing(self):
        names = unwired_names_independently()
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            for source in cfg.BLOCK_TEXT_REL.values():
                path = root / source
                path.write_text(path.read_text() + "\nUse Phoenix.\n")
            results, manifest, *_ = cfg.analyse(root, check_blocks=False)
            total = 0
            for piece, (_, _, dropped) in cfg.generate_blocks(root, cfg.unwired_names(results, manifest)).items():
                self.assertGreater(len(dropped), 0, piece)
                for unit in dropped:
                    total += 1
                    self.assertTrue(name_hits(unit.text, names), (piece, unit.line, unit.text))
            self.assertEqual(total, len(self.PIECES))

    def test_the_dropped_list_is_printed_in_full_by_the_check_and_by_write_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            for source in cfg.BLOCK_TEXT_REL.values():
                path = root / source
                path.write_text(path.read_text() + "\nUse Phoenix.\n")
            write_blocks(root)
            results, manifest, *_ = cfg.analyse(root)
            units = [(unit, piece) for piece, (_, _, dropped) in
                     cfg.generate_blocks(root, cfg.unwired_names(results, manifest)).items() for unit in dropped]
            self.assertEqual(len(units), len(self.PIECES))
            code, out, _ = run_main("--check", "--dropped", "--root", str(root))
            self.assertEqual(code, 0)
            for unit, _piece in units:
                for line in unit.text.split("\n"):
                    self.assertIn("    " + line, out)
            code, written, _ = run_main("--write-blocks", "--dropped", "--root", str(root))
            self.assertEqual(code, 0)
            self.assertIn("kept", written)
            self.assertEqual(written.count("\n    "), out.count("\n    "))

    def test_the_filter_drops_sentences_bullets_paragraphs_and_headings_and_writes_nothing_new(self):
        names = ["alpha-tool", "beta"]
        text, dropped = cfg.filter_block(self.SYNTHETIC, names)
        self.assertEqual(text, "# Title\n\nKeep this sentence. Keep the last one.\n\n## Mixed\n\n"
                               "- A bullet that stays. A third stays.\n")
        self.assertEqual([(unit.line, unit.kind) for unit in dropped],
                         [(3, "sentence"), (7, "bullet"), (8, "sentence"), (9, "bullet"), (11, "heading"),
                          (13, "paragraph")])
        self.assertEqual([unit.text for unit in dropped],
                         ["Drop alpha-tool here.", "- A bullet that names beta.", "Its second sentence names alpha-tool.",
                          "- Its first sentence names beta. A later sentence stays.", "## Wrapped",
                          "A wrapped paragraph that runs on\nand names alpha-tool in\nits second line."])
        self.assertIn("nothing is kept under it", dropped[4].note)
        self.assertIn("wrapped over several lines", dropped[5].note)
        sources = self.SYNTHETIC.split("\n")
        self.assertTrue(all(line_is_verbatim(line, sources) for line in text.split("\n") if line.strip()))
        self.assertEqual(name_hits(text, names), [])
        # Nothing is left to drop the second time.
        self.assertEqual(cfg.filter_block(text, names), (text, []))
        # A text that names none comes back byte for byte.
        self.assertEqual(cfg.filter_block(self.SYNTHETIC, ["nothing-named-here"]), (self.SYNTHETIC, []))

    def test_a_numbered_item_that_goes_leaves_the_other_numbers_as_written_and_a_named_heading_goes_alone(self):
        names = ["beta"]
        text, dropped = cfg.filter_block("1. First stays.\n2. Second names beta.\n3. Third stays.\n", names)
        self.assertEqual(text, "1. First stays.\n3. Third stays.\n")
        self.assertEqual([(unit.line, unit.kind) for unit in dropped], [(2, "bullet")])
        text, dropped = cfg.filter_block("## About beta\n\nKeep this.\n", names)
        self.assertEqual(text, "Keep this.\n")
        self.assertEqual([(unit.kind, unit.text) for unit in dropped], [("heading", "## About beta")])
        text, dropped = cfg.filter_block("<!-- a marker for beta -->\nKeep this.\n", names)
        self.assertEqual((text, [unit.kind for unit in dropped]), ("Keep this.\n", ["marker"]))

    def test_the_filter_refuses_text_it_cannot_cut_without_rewriting(self):
        for text in ("```sh\nrtk git status\n```\n", "a line\r\nanother\r\n"):
            with self.subTest(text=text[:12]), self.assertRaises(cfg.ConfigError):
                cfg.filter_block(text, ["rtk"])

    def test_a_block_whose_filtered_text_still_names_an_unwired_tool_is_left_out_of_the_apply(self):
        # Control: were the filter to let a name through, the scan that follows it would still keep the block out.
        results, manifest, *_ = cfg.analyse(ROOT)
        names = cfg.unwired_names(results, manifest)
        with mock.patch.object(cfg, "filter_block",
                               lambda text, names, dependents=(): (text + "\nUse Phoenix.\n", [])):
            by_key = {v.piece.key: v for v in cfg.resolve_blocks(ROOT, results, names)}
        for key in self.PIECES:
            self.assertFalse(by_key[key].wired, key)
            self.assertIn("still names", by_key[key].reason)

    def test_a_dependent_sentence_goes_with_the_sentence_before_it_only_when_the_map_declares_it(self):
        names, dependents = ["alpha-tool"], ("Follows it",)
        text, dropped = cfg.filter_block("Keep. Drop alpha-tool here. Follows it. Next one.\n", names, dependents)
        self.assertEqual(text, "Keep. Next one.\n")
        self.assertEqual([(unit.text, unit.names, bool(unit.note)) for unit in dropped],
                         [("Drop alpha-tool here.", ("alpha-tool",), False), ("Follows it.", (), True)])
        self.assertIn("depends on the sentence before it", dropped[1].note)
        # A chain: a declared sentence after a dependent one goes too.
        self.assertEqual(cfg.filter_block("Drop alpha-tool. Follows it. Follows it again. Stay.\n", names, dependents)[0],
                         "Stay.\n")
        # Where the sentence before it stays, it stays; a declaration is not a rule about the sentence's own words.
        self.assertEqual(cfg.filter_block("Keep. Follows it. Drop alpha-tool.\n", names, dependents)[0],
                         "Keep. Follows it.\n")
        # Nothing is inferred: the same text with no declaration leaves the sentence where it is.
        self.assertEqual(cfg.filter_block("Drop alpha-tool. Follows it.\n", names, ())[0], "Follows it.\n")
        # In a bullet, the sentence after a dropped one goes, and a bullet left with one sentence keeps its marker.
        self.assertEqual(cfg.filter_block("- Keep. Drop alpha-tool. Follows it.\n", names, dependents)[0], "- Keep.\n")

    def test_the_two_blocks_lose_the_sentence_that_only_made_sense_with_the_ai_memory_one_and_list_it(self):
        # ai-memory is wired while the memory-owner row carries its interim install; without it, as before wave 2, the
        # sentence that names ai-memory goes and takes the declared dependent with it. The committed blocks name no tool
        # since 2026-10-08, so a scratch catalog carries the ai-memory line and its declaration (with_ai_memory_line).
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            with_ai_memory_line(root)
            edit_json(root / cfg.MANIFEST_REL, without_interim("memory-owner"))
            results, manifest, *_ = cfg.analyse(root, check_blocks=False)
            generated = cfg.generate_blocks(root, cfg.unwired_names(results, manifest))
            scratch_sources = {piece: cfg.block_text(root, piece).split("\n") for piece in self.PIECES}
        for piece, (_, text, dropped) in generated.items():
            self.assertNotIn("Check relevance; retry without pin priority", text, piece)
            sources = scratch_sources[piece]
            unit = next(u for u in dropped if cfg.DEPENDS_NOTE in u.note)
            self.assertTrue(unit.text.startswith("Check relevance; retry without pin priority or widen if needed, then "
                                                 "read the relevant exact path and verify current canonical sources."))
            before = dropped[dropped.index(unit) - 1]
            self.assertIn("query scoped ai-memory", before.text)
            line = sources[unit.line - 1]
            self.assertLess(line.index(before.text), line.index(unit.text))
            self.assertEqual(line[line.index(before.text) + len(before.text)], " ")   # it follows that sentence directly

    def test_a_dependent_sentence_the_map_declares_must_exist_and_have_a_sentence_before_it(self):
        cases = {
            "no block holds it": ({"starts": "A sentence that no block holds", "on": "previous", "why": "a control"},
                                  "no instruction block holds it"),
            "it starts its line": ({"starts": "**Research convergence first;", "on": "previous", "why": "a control"},
                                   "starts its line"),
        }
        for name, (declaration, expected) in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                root = make_catalog(Path(tmp))
                edit_json(root / cfg.MAP_REL, lambda d: d["dependent_sentences"].append(declaration))
                errors = cfg.analyse(root)[3]
                self.assertTrue(any(expected in error for error in errors), errors)
        for declaration in ({"starts": "x", "on": "previous"}, {"starts": "x", "why": "y", "on": "next"},
                            {"starts": " ", "why": "y", "on": "previous"}, "a string"):
            with self.subTest(malformed=str(declaration)), tempfile.TemporaryDirectory() as tmp:
                root = make_catalog(Path(tmp))
                edit_json(root / cfg.MAP_REL, lambda d: d["dependent_sentences"].append(declaration))
                with self.assertRaises(cfg.ConfigError):
                    cfg.load_dependents(root)

    def test_a_slot_that_starts_installing_brings_back_the_sentence_that_names_its_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            with_ai_memory_line(root)            # the committed blocks name no tool since 2026-10-08
            blocks = {piece: root / cfg.GENERATED_BLOCKS[piece] for piece in self.PIECES}
            for path in blocks.values():         # the scratch blocks: ai-memory is an interim install
                self.assertEqual(path.read_text().count("query scoped ai-memory"), 1)
            # Without the interim, as before wave 2, the memory-owner row installs nothing and the sentence goes.
            edit_json(root / cfg.MANIFEST_REL, without_interim("memory-owner"))
            write_blocks(root)
            for path in blocks.values():
                self.assertNotIn("query scoped ai-memory", path.read_text())
                self.assertNotIn("Check relevance; retry without pin priority", path.read_text())

            def install(data):
                row = next(r for r in data["slots"] if r["slot_id"] == "memory-owner" and r["catalog"] == "foundation")
                row.update(installs_nothing_extra=False, state="definitive", default="ai-memory")
                row["resolution"] = {"outcome": "final"}
            edit_json(root / cfg.MANIFEST_REL, install)
            self.assertTrue(any("is stale" in e for e in cfg.analyse(root)[3]), "the blocks follow the manifest")
            write_blocks(root)
            self.assertEqual(cfg.analyse(root)[3], [])
            for path in blocks.values():
                self.assertEqual(path.read_text().count("query scoped ai-memory"), 1)
                self.assertEqual(path.read_text().count("Check relevance; retry without pin priority or widen if needed"), 1)
            # What came back is the source sentence, word for word.
            self.assertIn("query scoped ai-memory with `pin_first=true, limit=2` when supported by the installed schema.",
                          blocks[cfg.CLAUDE_MD_PIECE].read_text())


class BlocksSentenceTests(unittest.TestCase):
    """F9's sentence about the instruction blocks, held against what the filter actually left out and kept."""

    SKILLS_AND_TIMERS = ("search-first", "find-skills", "skill-creator", "daily currency timer")

    def test_a_unit_is_left_out_when_it_names_a_tool_that_is_not_wired_by_the_map_or_as_a_former_default(self):
        results, manifest, *_ = cfg.analyse(ROOT)
        names = cfg.unwired_names(results, manifest)
        by_map, by_manifest = map_unwired_names_independently(), former_default_names_independently()
        # The names that decide are those two sources and nothing else, and the second is not empty of its own: Phoenix is
        # in no map entry, and comes from the manifest row `phoenix`, whose former default it is.
        self.assertEqual(set(names), by_map | by_manifest)
        self.assertIn("Phoenix", by_manifest - by_map)
        self.assertEqual([e for e in json.loads(MAP.read_text())["entries"] if "Phoenix" in json.dumps(e)], [])
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            # The committed blocks name no skill or timer since 2026-10-08, so a line that names all four, and no tool,
            # stands in for them below.
            for source in cfg.BLOCK_TEXT_REL.values():
                path = root / source
                path.write_text(path.read_text() + "\nUse Phoenix and skill-creator.\n"
                                "Keep search-first, find-skills, skill-creator and the daily currency timer.\n")
            generated = cfg.generate_blocks(root, names)
        for piece, (_, kept, dropped) in generated.items():
            with self.subTest(block=piece):
                for unit in dropped:
                    if unit.names:       # a unit that names a tool names one of the two sources, in its own words
                        self.assertTrue(set(unit.names) <= set(names) and independent_name_hits(unit.text, unit.names), unit)
                    else:                # none does but a heading left empty or a declared dependent sentence, which say why
                        self.assertTrue(unit.note, unit)
                # The Phoenix unit: left out although no map entry lists the name, and although it names a skill too.
                phoenix = [unit for unit in dropped if "Phoenix" in unit.names]
                self.assertEqual(len(phoenix), 1)
                self.assertTrue(set(phoenix[0].names) <= by_manifest - by_map, phoenix[0].names)
                self.assertIn("skill-creator", phoenix[0].text)
                self.assertEqual(independent_name_hits(kept, ["Phoenix"]), [])
        # And not left out merely for naming a skill or a timer: every kept line that names one names no tool that is not
        # wired, and each of the four stays in at least one block.
        kept_lines = [line for _, kept, _ in generated.values() for line in kept.splitlines()]
        for word in self.SKILLS_AND_TIMERS:
            holders = [line for line in kept_lines if word in line]
            self.assertTrue(holders, f"no kept line names {word}")
            for line in holders:
                self.assertEqual(independent_name_hits(line, names), [], line)


class CarrierTests(unittest.TestCase):
    """The two Codex role carriers name context-mode, ai-memory and qmd tools, and rtk (stack-researcher jcodemunch too).
    A filtered copy would break the repository's own rules for them, so the map leaves them out: they require the RTK
    block (wave-2 context ruling, change 14)."""

    def test_the_carriers_are_not_wired_and_only_the_researcher_names_a_tool_that_is_not_wired(self):
        results, manifest, *_ = cfg.analyse(ROOT)
        verdicts = {v.piece.key: v for v in results}
        names = cfg.unwired_names(results, manifest)
        sums = codex_roles.sha256sums(codex_roles.ROLES_SOURCE / "SHA256SUMS")
        self.assertEqual(sorted(codex_roles.ROLE_FILES), ["stack-researcher.toml", "stack-verifier.toml"])
        for role_file in codex_roles.ROLE_FILES:
            role = role_file[: -len(".toml")]
            path = codex_roles.ROLES_SOURCE / role_file
            self.assertFalse(verdicts[f"codex/role/{role_file}"].wired, role_file)
            self.assertIn("byte-pinned", verdicts[f"codex/role/{role_file}"].reason)
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            # The carrier meets its own rules and its pinned hash as it is.
            self.assertEqual(codex_roles.structural_problems(role, role, data), [])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), sums[role_file])
            hits = {n.lower() for n in name_hits(data["developer_instructions"], names)}
            # The owner defaults now include jCodeMunch; both carriers name only wired tools.
            self.assertEqual(hits, set(), role_file)
            # Filtered the way the two blocks are, a carrier keeps the three rules; a dropped sentence changes the bytes
            # its pinned hash covers.
            text, dropped = cfg.filter_block(data["developer_instructions"], names)
            self.assertEqual(bool(dropped), bool(hits), role_file)
            self.assertEqual(name_hits(text, names), [], role_file)
            self.assertEqual(text != data["developer_instructions"], bool(dropped), role_file)
            problems = codex_roles.structural_problems(role, role, dict(data, developer_instructions=text))
            self.assertEqual(problems, [], role_file)


def installing_independently(row: dict) -> bool:
    """The install plan's rule, written out again here instead of called: a row that carries an interim install
    (amendment 3 of the manifest's decision rule) installs it; any other row installs its default when it names one,
    installs something extra, is not resolved as not installed and is not split."""
    if row.get("interim"):
        return True
    return (bool(row["default"]) and not row["installs_nothing_extra"]
            and (row.get("resolution") or {}).get("outcome") != "not_installed" and (row.get("state") or "") != "split")


def slot_wires_independently(entry: dict, row: dict) -> bool:
    """Whether a slot entry is wired, written out again: its slot installs, and what it installs (the interim's default
    while the row carries one, otherwise the decided default) names the entry's owner."""
    installed = str((row.get("interim") or {}).get("default") or row["default"])
    return installing_independently(row) and entry["owner"].casefold() in installed.casefold()


def map_unwired_names_independently() -> set:
    """The names the map lists for its unwired entries (not_wired, or a slot that does not install the owner the entry
    names), read from the map file. An authorization entry carries none: its tool's other pieces do."""
    rows = foundation_rows()
    names = set()
    for entry in json.loads(MAP.read_text())["entries"]:
        wiring = entry["wiring"]
        if wiring.startswith("not_wired") or (wiring.startswith("slot:")
                                              and not slot_wires_independently(entry, rows[wiring[5:]])
                                              and not (entry.get("directive")
                                                       and installing_independently(rows[wiring[5:]]))):
            names.update(entry.get("names", []))
    return names


def former_default_names_independently() -> set:
    """The former defaults of the manifest rows that install nothing."""
    names = set()
    for row in foundation_rows().values():
        former = (row.get("resolution") or {}).get("former_default") or {}
        if not installing_independently(row) and former.get("repository") and former.get("name"):
            names.add(former["name"])
    return names


def unwired_names_independently() -> list:
    """The names of tools that are not wired: the map's unwired entries and the manifest's non-installing rows."""
    return sorted(map_unwired_names_independently() | former_default_names_independently())


def independent_name_hits(text: str, names) -> list:
    """The rule of the scan written out a second time: a name as a whole word, in any case."""
    return [n for n in names if re.search(r"(?<![A-Za-z0-9])" + re.escape(n) + r"(?![A-Za-z0-9])", text, re.I)]


def name_hits(text: str, names) -> list:
    """The tool's own scan (--check uses it on the rendered files); the names the tests give it come from
    unwired_names_independently, not from the tool."""
    return cfg.name_hits(text, names)


class ApplyCase(unittest.TestCase):
    """A temporary home, stub clients and an `--apply` that names them: the base of the apply tests."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.bins = self.base / "bin"
        self.claude = write_exe(self.bins / "claude", STUB_CLAUDE)
        self.codex = write_exe(self.bins / "codex", STUB_CODEX)
        self.marker = self.base / "client-calls.txt"
        patcher = mock.patch.dict(os.environ, {"STUB_MARKER": str(self.marker)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.eco = self.home / ".local/share/codex-ecosystem"
        native_run = subprocess.run

        def synthetic_rtk(command, **kwargs):
            home = Path(kwargs.get("env", {}).get("HOME", str(self.home)))
            if command == [str(home / ".local/share/codex-ecosystem/bin/rtk"), "init", "-g", "--no-patch"]:
                self.assertTrue(home.is_relative_to(self.base), "synthetic native init escaped the temporary home")
                target = home / ".claude"
                target.mkdir(exist_ok=True)
                (target / "RTK.md").write_text("Synthetic native RTK awareness.\n")
                path = target / "CLAUDE.md"
                current = path.read_text() if path.exists() else ""
                if "@RTK.md" not in current.splitlines():
                    path.write_text(current + ("\n" if current and not current.endswith("\n") else "") + "@RTK.md\n")
                return subprocess.CompletedProcess(command, 0, "Synthetic RTK init.\n", "")
            return native_run(command, **kwargs)

        # Cover direct run_main calls and alternate temporary homes as well as
        # this helper, without executing a real RTK installation in integration tests.
        patcher = mock.patch.object(subprocess, "run", side_effect=synthetic_rtk)
        patcher.start()
        self.addCleanup(patcher.stop)

    def apply(self, *extra: str, dry: bool = False, claude: Path | None = None):
        argv = ["--apply", "--host", EXAMPLE_HOST, "--home", str(self.home), "--claude-bin", str(claude or self.claude),
                "--codex-bin", str(self.codex), "--codex-process-name", NO_PROCESS, *extra]
        return run_main(*argv, *(["--dry-run"] if dry else []))

    def installed_state(self) -> None:
        """What the install plan leaves in the home: the native clients and the tools that sit in its two bin directories."""
        write_exe(self.home / ".local/bin/claude", boot.InteractiveEffortLauncherTests.STUB_CLIENT)
        write_exe(self.home / ".local/bin/codex", STUB_CODEX)
        write_exe(self.home / ".local/bin/serena", "#!/bin/sh\necho serena\n")
        write_exe(self.home / ".local/bin/mise", "#!/bin/sh\necho mise\n")
        write_exe(self.home / ".local/share/mise/shims/qmd", "#!/bin/sh\necho qmd\n")


class CodexOwnedMigrationTests(ApplyCase):
    """Scratch profiles and a synthetic native config writer; no native account or provider is used."""

    def setUp(self):
        super().setUp()
        self.installed_state()
        self.config = self.home / ".codex/config.toml"
        self.config.parent.mkdir()
        self.migration_marker = self.config.parent / ".native-agent-stack-migrations/service-tier-fast-to-default-20261005.json"
        self.edits = []
        case = self

        class SyntheticAppServer:
            def __init__(self, codex, env, cwd):
                case.assertEqual(Path(env["CODEX_HOME"]), case.config.parent)

            def __enter__(self):
                return self

            def __exit__(self, *error):
                return False

            def user_layer(self):
                return hashlib.sha256(case.config.read_bytes()).hexdigest(), tomllib.loads(case.config.read_text())

            def batch_write(self, edits, expected_version):
                version, data = self.user_layer()
                case.assertEqual(version, expected_version)
                case.edits.extend(edits)
                for edit in edits:
                    case.assertEqual(edit["key"], ["service_tier"])
                    data["service_tier"] = edit["value"]
                case.config.write_text(cfg.emit_toml(data, "# synthetic native writer\n"))
                return {"status": "ok", "version": self.user_layer()[0]}

        self.synthetic_server = SyntheticAppServer
        patcher = mock.patch.object(cfg.lane, "AppServer", SyntheticAppServer)
        patcher.start()
        self.addCleanup(patcher.stop)

    def fast_config(self):
        original = b"service_tier = 'fast'\nmodel = 'operator-model'\n[features]\ndaemon_auto_start = false\n"
        self.config.write_bytes(original)
        return original

    def test_fresh_host_gets_default_and_a_marker_that_preserves_later_fast(self):
        code, out, err = self.apply()
        self.assertEqual(code, 0, out[-800:] + err)
        data = tomllib.loads(self.config.read_text())
        self.assertEqual(data["service_tier"], "default")
        self.assertTrue(self.migration_marker.is_file())
        data["service_tier"] = "fast"  # A later native /fast choice.
        self.config.write_text(cfg.emit_toml(data, ""))
        code, out, err = self.apply()
        self.assertEqual(code, 0, out[-800:] + err)
        self.assertEqual(tomllib.loads(self.config.read_text())["service_tier"], "fast")
        self.assertEqual(self.edits, [])

    def test_upgraded_fast_migrates_once_with_backup_and_native_version_guard(self):
        before = self.fast_config()
        code, out, err = self.apply()
        self.assertEqual(code, 0, out[-800:] + err)
        self.assertEqual(tomllib.loads(self.config.read_text())["service_tier"], "default")
        self.assertTrue(self.migration_marker.is_file())
        self.assertEqual(self.edits, [{"key": ["service_tier"], "value": "default"}])
        self.assertIn("service_tier", out)
        self.assertIn("migration", out)
        self.assertEqual([p.read_bytes() for p in self.config.parent.glob("config.toml.bak.*")], [before])
        once = tree(self.home)
        code, out, err = self.apply()
        self.assertEqual(code, 0, out[-800:] + err)
        self.assertEqual(tree(self.home), once)
        self.assertEqual(len(self.edits), 1)

    def test_fast_with_marker_stays_as_a_conflict(self):
        self.fast_config()
        self.migration_marker.parent.mkdir()
        self.migration_marker.write_text("completed\n")  # Presence alone; never parse marker values.
        code, out, err = self.apply()
        self.assertEqual(code, 0, out[-800:] + err)
        self.assertEqual(tomllib.loads(self.config.read_text())["service_tier"], "fast")
        self.assertIn("service_tier", out)
        self.assertIn("conflicts kept", out)
        self.assertEqual(self.edits, [])

    def test_dry_run_reports_migration_without_writes_or_native_calls(self):
        self.fast_config()
        before = tree(self.home)
        code, out, err = self.apply(dry=True)
        self.assertEqual(code, 0, out[-800:] + err)
        self.assertIn("would migrate service_tier", out)
        self.assertEqual(tree(self.home), before)
        self.assertFalse(self.migration_marker.exists())
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.edits, [])

    def test_other_scalars_still_conflict_while_owned_fast_is_migrated(self):
        self.fast_config()
        code, out, err = self.apply()
        self.assertEqual(code, 0, out[-800:] + err)
        data = tomllib.loads(self.config.read_text())
        self.assertEqual(data["model"], "operator-model")
        self.assertEqual(data["service_tier"], "default")
        self.assertIn("conflicts kept", out)

    def test_already_default_adoption_stamps_completion_without_native_edit(self):
        self.config.write_text("service_tier = 'default'\n[features]\ndaemon_auto_start = false\n")
        code, out, err = self.apply()
        self.assertEqual(code, 0, out[-800:] + err)
        self.assertTrue(self.migration_marker.is_file())
        self.assertEqual(self.edits, [])

    def test_marker_failure_restores_config_and_does_not_mark_migration_done(self):
        before = self.fast_config()
        native_write = cfg.lane.atomic_write

        def fail_marker(path, *args, **kwargs):
            if path == self.migration_marker:
                raise OSError("synthetic marker write failure")
            return native_write(path, *args, **kwargs)

        with mock.patch.object(cfg.lane, "atomic_write", side_effect=fail_marker):
            code, out, err = self.apply()
        self.assertEqual(code, 1, out[-800:] + err)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertFalse(self.migration_marker.exists())
        self.assertIn("the file is back as it was", out)

    def test_native_precheck_rejection_keeps_the_concurrent_choice(self):
        self.fast_config()
        native_read = self.synthetic_server.user_layer

        def changed_before_read(server):
            data = tomllib.loads(self.config.read_text())
            data["service_tier"] = "flex"
            self.config.write_text(cfg.emit_toml(data, ""))
            return native_read(server)

        with mock.patch.object(self.synthetic_server, "user_layer", changed_before_read):
            code, out, err = self.apply()
        self.assertEqual(code, 1, out[-800:] + err)
        self.assertEqual(tomllib.loads(self.config.read_text())["service_tier"], "flex")
        self.assertFalse(self.migration_marker.exists())
        self.assertEqual(self.edits, [])

    def test_native_version_rejection_keeps_concurrent_unowned_edits(self):
        self.fast_config()

        def reject_write(*args):
            data = tomllib.loads(self.config.read_text())
            data["operator_after_read"] = "keep"
            self.config.write_text(cfg.emit_toml(data, ""))
            raise cfg.lane.AppServerError("config/batchWrite", {"message": "synthetic version rejection", "code": 1})

        with mock.patch.object(self.synthetic_server, "batch_write", side_effect=reject_write):
            code, out, err = self.apply()
        self.assertEqual(code, 1, out[-800:] + err)
        self.assertEqual(tomllib.loads(self.config.read_text())["operator_after_read"], "keep")
        self.assertFalse(self.migration_marker.exists())

    def test_fresh_marker_failure_is_failed_adoption_and_can_retry_at_default(self):
        native_write = cfg.lane.atomic_write

        def fail_marker(path, *args, **kwargs):
            if path == self.migration_marker:
                raise OSError("synthetic marker write failure")
            return native_write(path, *args, **kwargs)

        with mock.patch.object(cfg.lane, "atomic_write", side_effect=fail_marker):
            code, out, err = self.apply()
        self.assertEqual(code, 1, out[-800:] + err)
        self.assertEqual(tomllib.loads(self.config.read_text())["service_tier"], "default")
        self.assertFalse(self.migration_marker.exists())
        code, out, err = self.apply()
        self.assertEqual(code, 0, out[-800:] + err)
        self.assertTrue(self.migration_marker.is_file())

    def test_native_written_version_must_match_readback_before_completion(self):
        self.fast_config()
        native_write = self.synthetic_server.batch_write

        def wrong_version(server, edits, expected_version):
            result = native_write(server, edits, expected_version)
            result["version"] = "synthetic-intervening-version"
            return result

        with mock.patch.object(self.synthetic_server, "batch_write", wrong_version):
            code, out, err = self.apply()
        self.assertEqual(code, 1, out[-800:] + err)
        self.assertFalse(self.migration_marker.exists())
        self.assertIn("native migration version changed", out)

    def test_preserved_flex_is_marked_and_a_later_fast_choice_is_kept(self):
        self.config.write_text("service_tier = 'flex'\n[features]\ndaemon_auto_start = false\n")
        code, out, err = self.apply()
        self.assertEqual(code, 0, out[-600:] + err)
        self.assertEqual(tomllib.loads(self.config.read_text())["service_tier"], "flex")
        self.assertTrue(self.migration_marker.is_file())
        data = tomllib.loads(self.config.read_text())
        data["service_tier"] = "fast"  # Native /fast persists this spelling from another tier.
        self.config.write_text(cfg.emit_toml(data, ""))
        before = self.config.read_bytes()
        code, out, err = self.apply()
        self.assertEqual(code, 0, out[-600:] + err)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(self.edits, [])

    def test_native_requirement_rejection_reports_the_local_error_text(self):
        self.fast_config()
        rejection = cfg.lane.AppServerError("config/batchWrite", {
            "message": "synthetic service tier requirement is readonly",
            "data": {"config_write_error_code": "ConfigRequirementReadonly"},
        })
        with mock.patch.object(self.synthetic_server, "batch_write", side_effect=rejection):
            code, out, err = self.apply()
        self.assertEqual(code, 1, out[-600:] + err)
        self.assertTrue("synthetic service tier requirement is readonly" in out)
        self.assertTrue("ConfigRequirementReadonly" in out)
        self.assertFalse(self.migration_marker.exists())

    def test_a_dry_run_without_a_native_migration_writer_refuses_without_writes(self):
        self.fast_config()
        before = tree(self.home)
        native_binary = cfg.Apply.binary

        def no_codex(apply, name, explicit):
            return None if name == "codex" else native_binary(apply, name, explicit)

        with mock.patch.object(cfg.Apply, "binary", no_codex):
            code, out, err = self.apply(dry=True)
        self.assertEqual(code, 1, out[-600:] + err)
        self.assertTrue("needs the native Codex app-server writer" in out)
        self.assertEqual(tree(self.home), before)
        self.assertEqual(self.edits, [])


class ApplyTests(ApplyCase):
    def test_apply_keeps_the_owned_skill_listing_fraction_and_host_only_settings(self):
        self.installed_state()
        target = self.home / ".claude/settings.json"
        target.parent.mkdir()
        original = {"skillListingBudgetFraction": 0.05, "hostOnly": {"keep": 1}}
        target.write_text(json.dumps(original) + "\n", encoding="utf-8")
        before = target.read_bytes()
        code, out, _ = self.apply(dry=True)
        self.assertEqual(code, 0, out[-800:])
        self.assertEqual(target.read_bytes(), before)
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-800:])
        settings = json.loads(target.read_text())
        self.assertEqual(settings["skillListingBudgetFraction"], 0.05)
        self.assertEqual(settings["hostOnly"], {"keep": 1})
        backups = list(target.parent.glob("settings.json.bak.*"))
        self.assertEqual([p.read_bytes() for p in backups], [before])
        once = tree(self.home)
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-800:])
        self.assertEqual(tree(self.home), once)

    def test_a_dry_run_writes_nothing_and_runs_no_client(self):
        self.installed_state()
        before = tree(self.home)
        code, out, err = self.apply(dry=True)
        self.assertEqual((code, err), (0, ""), out[-600:])
        self.assertEqual(tree(self.home), before)
        self.assertFalse(self.marker.exists(), "a dry run started a client")
        self.assertIn("DRY RUN", out)
        self.assertIn("claude mcp add --scope user serena -- serena start-mcp-server", out)
        self.assertIn("summary: ", out)
        self.assertNotIn("failed", out.split("summary: ")[1])

    def test_a_dry_run_into_an_empty_home_creates_nothing_at_all(self):
        code, out, _ = self.apply(dry=True)
        self.assertEqual(code, 0, out[-600:])
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertFalse(self.marker.exists())

    def test_apply_twice_gives_the_same_files_and_the_second_run_changes_nothing(self):
        self.installed_state()
        first = self.apply()
        self.assertEqual(first[0], 0, first[1][-800:])
        once = tree(self.home)
        second = self.apply()
        self.assertEqual(second[0], 0, second[1][-800:])
        self.assertEqual(tree(self.home), once)
        summary = second[1].split("summary: ")[1]
        for step in ("claude-hooks", "claude-agents", "claude-mcp", "claude-settings", "claude-launcher", "claude-md",
                     "codex-config", "codex-files", "codex-md", "login-path"):
            self.assertIn(f"{step} current", summary)
        # Native RTK first creates the import; adopting our managed block backs
        # that original file up once. The complete tree comparison above proves
        # the second adoption neither changes files nor adds another backup.
        backups = [p for p in self.home.rglob("*") if ".bak." in p.name]
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].parent, self.home / ".claude")
        self.assertTrue(backups[0].name.startswith("CLAUDE.md.bak."))
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "@RTK.md\n")

    def test_the_first_run_writes_what_the_wired_pieces_name_and_nothing_else(self):
        self.installed_state()
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-800:])
        hooks = sorted(p.name for p in (self.home / ".claude/hooks").iterdir())
        self.assertEqual(hooks, ["currency-due-notice.py", "effort-default-guard.py", "secret_path_guard.py"])
        for name in hooks:
            self.assertEqual(hashlib.sha256((self.home / ".claude/hooks" / name).read_bytes()).hexdigest(),
                             icp.expected_sha256(icp.HOOKS[name]))
        self.assertEqual(len(list((self.home / ".claude/agents").iterdir())), 11)
        self.assertEqual(sorted(json.loads((self.home / ".stub-claude-mcp.json").read_text())),
                         ["ai-memory", "chrome-devtools", "codebase-memory", "headroom", "jcodemunch", "qmd", "semble", "serena", "socraticode"])
        settings = json.loads((self.home / ".claude/settings.json").read_text())
        # The repository's hooks and the overlay's Notification, and the events ai-memory's hooks take (an interim install).
        self.assertEqual(sorted(settings["hooks"]), ["ConfigChange", "Notification", "PostToolUse", "PreCompact", "PreToolUse",
                                                     "SessionEnd", "SessionStart", "Stop", "SubagentStart",
                                                     "SubagentStop"])
        self.assertEqual(settings["env"]["PATH"].split(":")[:3],
                         [f"{self.eco}/bin", f"{self.home}/.local/bin", f"{self.home}/.local/share/mise/shims"])
        codex = self.home / ".codex"
        self.assertEqual(stat.S_IMODE(codex.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((codex / "config.toml").stat().st_mode), 0o600)
        # No role carrier (the map leaves them out), so no agents directory; the Codex block is the whole AGENTS.md.
        self.assertEqual(sorted(p.name for p in codex.iterdir()), [".native-agent-stack-migrations", "AGENTS.md", "config.toml", "omniroute.config.toml",
                                                                    "stack-worker.config.toml"])
        self.assertIn(f"{self.home}/.local/share/mise/shims", (codex / "config.toml").read_text())
        launcher = self.eco / "bin" / "claude"
        self.assertEqual(stat.S_IMODE(launcher.stat().st_mode), 0o755)
        self.assertEqual((codex / "AGENTS.md").read_text(), generated_text(cfg.CODEX_MD_PIECE))
        self.assertNotIn("never rewritten", out)
        claude_md = (self.home / ".claude" / "CLAUDE.md").read_text()
        self.assertTrue(claude_md.startswith("@RTK.md\n\n" + managed_block.CLAUDE_BEGIN_LINE + "\n"))
        self.assertEqual(claude_md.splitlines().count("@RTK.md"), 1)
        self.assertTrue(claude_md.endswith(generated_text(cfg.CLAUDE_MD_PIECE).rstrip("\n") + "\n" + managed_block.CLAUDE_END + "\n"))
        self.assertEqual(name_hits(claude_md + (codex / "AGENTS.md").read_text(), unwired_names_independently()), [])

    def test_the_filtered_blocks_are_installed_between_markers_and_the_text_around_them_stays(self):
        self.installed_state()
        (self.home / ".claude").mkdir()
        (self.home / ".codex").mkdir(mode=0o700)
        (self.home / ".claude/CLAUDE.md").write_text("# mine\nkeep me\n", encoding="utf-8")
        (self.home / ".codex/AGENTS.md").write_text("my rules\n", encoding="utf-8")
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-800:])
        claude_md = (self.home / ".claude/CLAUDE.md").read_text()
        agents_md = (self.home / ".codex/AGENTS.md").read_text()
        self.assertTrue(claude_md.startswith("# mine\nkeep me\n"))
        self.assertTrue(agents_md.startswith("my rules\n"))
        self.assertIn(generated_text(cfg.CLAUDE_MD_PIECE).rstrip("\n"), claude_md)
        self.assertEqual(agents_md, "my rules\n\n" + generated_text(cfg.CODEX_MD_PIECE))
        for name in ("CLAUDE.md", "AGENTS.md"):
            backups = [p for p in self.home.rglob(name + ".bak.*")]
            self.assertEqual(len(backups), 1, name)
        # The second run changes nothing and makes no second backup.
        once = tree(self.home)
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-800:])
        self.assertEqual(tree(self.home), once)
        self.assertIn("claude-md current", out)
        self.assertIn("codex-md current", out)
        # A block that a person edited between the markers is replaced by the filtered one, text outside kept.
        edited = claude_md.replace("Decide by evidence", "An edited rule")
        self.assertNotEqual(edited, claude_md)  # the edit lands between the markers
        (self.home / ".claude/CLAUDE.md").write_text(edited, encoding="utf-8")
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual((self.home / ".claude/CLAUDE.md").read_text(), claude_md)

    def test_a_dry_run_shows_the_blocks_it_would_install_and_writes_none(self):
        code, out, _ = self.apply(dry=True)
        self.assertEqual(code, 0, out[-600:])
        self.assertIn("claude-md planned", out)
        self.assertIn("codex-md planned", out)
        self.assertIn("+# Native engineering defaults", out)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_apply_runs_no_client_subcommand_that_needs_a_signed_in_client(self):
        # The sign-ins come after --apply in F9, so no step may run a client command that needs one. With stubs that
        # record every call, a first run starts Claude Code only for `mcp get` and `mcp add` (they read and write its
        # configuration file) and starts Codex not at all: its one call, `codex features disable daemon_auto_start`, is
        # for an existing config.toml that lacks the key, and the render carries the key.
        self.installed_state()
        self.assertEqual(self.apply()[0], 0)
        calls = self.marker.read_text().splitlines()
        self.assertTrue(calls)
        self.assertEqual([call for call in calls if call.startswith("codex")], [])
        self.assertEqual({" ".join(call.split()[:2]) for call in calls}, {"mcp get", "mcp add"})
        words = {word for call in calls for word in call.split()}
        self.assertEqual(words & {"login", "logout", "auth", "setup-token", "doctor", "update", "exec", "chat", "review"},
                         set())
        # Control: the stub does record a Codex call when one is made.
        self.marker.unlink()
        subprocess.run([str(self.codex), "--version"], check=True, capture_output=True)
        self.assertEqual(self.marker.read_text().splitlines(), ["codex --version"])

    def test_a_login_shell_finds_the_launcher_the_native_codex_and_the_mise_tools_only_after_the_apply(self):
        self.installed_state()
        names = ["claude", "codex", "serena", "qmd", "mise"]
        self.assertEqual(cfg.login_shell_resolution(self.home, names), {n: None for n in names})
        self.assertEqual(self.apply()[0], 0)
        found = cfg.login_shell_resolution(self.home, names)
        self.assertEqual(found, {"claude": f"{self.eco}/bin/claude", "codex": f"{self.home}/.local/bin/codex",
                                 "serena": f"{self.home}/.local/bin/serena",
                                 "qmd": f"{self.home}/.local/share/mise/shims/qmd",
                                 "mise": f"{self.home}/.local/bin/mise"})

    def test_the_launcher_adds_max_effort_to_an_interactive_launch_only_and_runs_the_native_client(self):
        self.installed_state()
        self.assertEqual(self.apply()[0], 0)
        launcher = self.eco / "bin" / "claude"
        runner = boot.InteractiveEffortLauncherTests("test_another_command_gets_the_plain_launcher")
        outcomes = {name: runner.run_launcher(launcher, self.home, argv, tty_in, tty_out, env)
                    for name, (argv, tty_in, tty_out, env, _) in boot.InteractiveEffortLauncherTests.CASES.items()}
        self.assertEqual(outcomes, runner.expected())

    def test_the_launcher_is_the_text_of_the_bootstraps_install_native_and_is_never_a_fork(self):
        text = (ROOT / cfg.BOOTSTRAP_REL).read_text()
        heredoc = re.search(r"<<'LAUNCHER_EFFORT'\n(.*?)^LAUNCHER_EFFORT$", text, re.S | re.M).group(1)
        data = cfg.launcher_bytes(ROOT / cfg.BOOTSTRAP_REL).decode()
        self.assertIn(heredoc, data)
        self.assertTrue(data.startswith("#!/usr/bin/env bash\n"))
        self.assertTrue(data.rstrip().endswith('exec "$HOME/.local/bin/claude" "$@"'))
        # The same bytes the bootstrap's own function writes when the repository's test harness runs it.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            bin_dir = home / "eco" / "bin"
            bin_dir.mkdir(parents=True)
            case = boot.InstallNativeLauncherTests("test_launcher_goes_to_bin_dir_and_leaves_the_native_binary_intact")
            result = boot.InstallNativeLauncherTests.run_install_native(case, ROOT / cfg.BOOTSTRAP_REL, home, bin_dir)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((bin_dir / "claude").read_text(), data)

    def test_the_launcher_generation_never_downloads_a_client(self):
        # Control: were the client not kept (keep=0 in the cut-out function), the function would fetch one, and the
        # stub fetch of the generator refuses.
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "bootstrap.sh"
            text = (ROOT / cfg.BOOTSTRAP_REL).read_text()
            self.assertEqual(text.count("    keep=1\n"), 1)
            script.write_text(text.replace("    keep=1\n", "    keep=0\n"), encoding="utf-8")
            with self.assertRaises(cfg.ConfigError) as caught:
                cfg.launcher_bytes(script)
        self.assertIn("install_native failed", str(caught.exception))
        self.assertIn("without downloading a client", str(caught.exception))

    def test_the_launcher_is_not_written_into_the_native_installers_directory(self):
        args = cfg.build_parser().parse_args(["--apply", "--host", EXAMPLE_HOST, "--home", str(self.home)])
        run = cfg.Apply(args)
        run.results, run.manifest, run.plan = cfg.analyse(ROOT)[:3]
        run.values = cfg.host_values(EXAMPLE_HOST, run.plan, self.home, [])
        run.eco = self.home / ".local"
        run.wired = {v.piece.key: v for v in run.results if v.wired}
        with contextlib.redirect_stdout(io.StringIO()):
            run.step_claude_launcher()
        self.assertEqual(run.outcomes[0][1], "failed")
        self.assertFalse((self.home / ".local" / "bin" / "claude").exists())

    def test_the_client_binary_is_the_native_installers_and_never_the_launcher(self):
        self.installed_state()
        write_exe(self.eco / "bin" / "claude", "#!/bin/sh\necho launcher\n")
        args = cfg.build_parser().parse_args(["--apply", "--host", EXAMPLE_HOST, "--home", str(self.home)])
        run = cfg.Apply(args)
        run.values = {"ECO_ROOT": str(self.eco)}
        path = f"{self.eco}/bin:/usr/bin:/bin"
        with mock.patch.dict(os.environ, {"PATH": path}):
            self.assertEqual(run.binary("claude", None), str(self.home / ".local/bin/claude"))
            self.assertEqual(run.binary("claude", str(self.claude)), str(self.claude))
            self.assertIsNone(run.binary("claude", str(self.base / "missing")))

    def test_what_exists_is_backed_up_and_host_only_settings_survive(self):
        self.installed_state()
        claude = self.home / ".claude"
        (claude / "hooks").mkdir(parents=True)
        (claude / "agents").mkdir()
        (claude / "hooks/secret_path_guard.py").write_text("# an older guard\n", encoding="utf-8")
        (claude / "agents/stack-verifier.md").write_text("an edited agent\n", encoding="utf-8")
        (claude / "settings.json").write_text(json.dumps(
            {"theme": "light", "hostOnly": {"keep": 1}, "permissions": {"deny": ["Read(~/host-only)"]}}), encoding="utf-8")
        (self.home / ".profile").write_text("# my profile\nalias ll='ls -l'\n", encoding="utf-8")
        original = {p: p.read_bytes() for p in (claude / "hooks/secret_path_guard.py", claude / "agents/stack-verifier.md",
                                                 claude / "settings.json", self.home / ".profile")}
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-800:])
        for path, content in original.items():
            backups = [p for p in path.parent.iterdir() if p.name.startswith(path.name + ".bak.")]
            self.assertEqual(len(backups), 1, path.name)
            self.assertEqual(backups[0].read_bytes(), content)
        settings = json.loads((claude / "settings.json").read_text())
        self.assertEqual(settings["hostOnly"], {"keep": 1})
        self.assertEqual(settings["theme"], "light")   # a person's choice: the template's "dark" is not written over it
        self.assertIn('kept your theme: "light" (the render has "dark")', out)
        self.assertIn("Read(~/host-only)", settings["permissions"]["deny"])
        self.assertIn("Bash(git push --force *)", settings["permissions"]["deny"])
        profile = (self.home / ".profile").read_text()
        self.assertTrue(profile.startswith("# my profile\nalias ll='ls -l'\n"))
        self.assertIn("native-agent-stack:profile-path:begin", profile)
        self.assertEqual(hashlib.sha256((claude / "hooks/secret_path_guard.py").read_bytes()).hexdigest(),
                         icp.expected_sha256(icp.HOOKS["secret_path_guard.py"]))

    def test_a_differing_profile_file_is_never_overwritten_while_an_existing_config_is_merged(self):
        self.installed_state()
        codex = self.home / ".codex"
        codex.mkdir(mode=0o700)
        (codex / "config.toml").write_text("model = 'mine'\n[features]\ndaemon_auto_start = false\n", encoding="utf-8")
        (codex / "stack-worker.config.toml").write_text("model = 'mine'\n", encoding="utf-8")
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-800:])
        config = tomllib.loads((codex / "config.toml").read_text())
        self.assertEqual(config["model"], "mine")                       # the file's own value stays
        self.assertIs(config["features"]["daemon_auto_start"], False)
        self.assertIn("mcp_servers", config)                            # what it lacked came in
        self.assertIn("conflict kept: model: the file has \"mine\"; the render has \"gpt-6.1-sol\"", out)
        self.assertIn("codex-config merged with conflicts kept", out.split("summary: ")[1])
        self.assertEqual((codex / "stack-worker.config.toml").read_text(), "model = 'mine'\n")
        self.assertIn("stack-worker.config.toml: differs from the render and is never overwritten", out)
        self.assertTrue((codex / "omniroute.config.toml").exists())
        self.assertIn("codex-files applied; differs, not written", out.split("summary: ")[1])
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-800:])
        self.assertEqual((codex / "stack-worker.config.toml").read_text(), "model = 'mine'\n")
        self.assertIn("codex-files differs, not written", out.split("summary: ")[1])
        self.assertNotIn("codex-files current", out.split("summary: ")[1])

    def test_a_settings_file_of_the_destinations_shape_keeps_its_marketplace_and_theme_and_gains_the_wired_settings(self):
        self.installed_state()
        claude = self.home / ".claude"
        claude.mkdir()
        original = json.dumps(DESTINATION_CLAUDE, indent=2) + "\n"
        (claude / "settings.json").write_text(original, encoding="utf-8")
        self.assertEqual(len(original.encode()), 194)
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-800:])
        settings = json.loads((claude / "settings.json").read_text())
        # The destination's own marketplace stays, beside the two the wave-2 rows wire (context-mode and claude-hud).
        self.assertEqual(settings["extraKnownMarketplaces"]["trailofbits"],
                         DESTINATION_CLAUDE["extraKnownMarketplaces"]["trailofbits"])
        self.assertEqual(sorted(settings["extraKnownMarketplaces"]), ["claude-hud", "context-mode", "trailofbits"])
        self.assertEqual(settings["theme"], "auto")
        self.assertIn('kept your theme: "auto" (the render has "dark")', out)
        for key in ("model", "effortLevel", "hooks", "permissions", "env"):
            self.assertIn(key, settings)
        self.assertNotIn("defaultMode", settings["permissions"])
        self.assertIn("PreToolUse", settings["hooks"])
        self.assertEqual(settings["env"]["PATH"].split(":")[0], f"{self.eco}/bin")
        backups = [p for p in claude.iterdir() if p.name.startswith("settings.json.bak.")]
        self.assertEqual([p.read_text() for p in backups], [original])
        once = tree(self.home)
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-800:])
        self.assertEqual(tree(self.home), once)
        self.assertIn("claude-settings current", out.split("summary: ")[1])
        # A theme equal to the template's has nothing to report, and a file without one gets the template's.
        (claude / "settings.json").write_text(json.dumps({**DESTINATION_CLAUDE, "theme": "dark"}, indent=2) + "\n")
        self.assertNotIn("kept your theme", self.apply()[1])
        fresh = self.base / "fresh"
        fresh.mkdir()
        argv = ["--apply", "--host", EXAMPLE_HOST, "--home", str(fresh), "--claude-bin", str(self.claude), "--codex-bin",
                str(self.codex), "--codex-process-name", NO_PROCESS, "--skip", "claude-mcp", "--skip", "verify"]
        self.assertEqual(run_main(*argv)[0], 0)
        self.assertEqual(json.loads((fresh / ".claude/settings.json").read_text())["theme"], "dark")

    def test_a_step_that_fails_is_reported_and_the_others_still_run(self):
        self.installed_state()
        failing = write_exe(self.bins / "failing-claude", FAILING_CLAUDE)
        code, out, _ = self.apply(claude=failing)
        self.assertEqual(code, 1)
        summary = out.split("summary: ")[1]
        self.assertIn("claude-mcp failed", summary)
        for step in ("claude-hooks applied", "claude-settings applied", "codex-config applied", "login-path applied"):
            self.assertIn(step, summary)

    def test_a_skipped_step_changes_nothing(self):
        self.installed_state()
        code, out, _ = self.apply("--skip", "claude-agents", "--skip", "codex-files", "--skip", "login-path")
        self.assertEqual(code, 0, out[-400:])
        self.assertFalse((self.home / ".claude/agents").exists())
        self.assertFalse((self.home / ".codex/agents").exists())
        self.assertFalse((self.home / ".profile").exists())
        self.assertIn("claude-agents skipped", out)

    def test_a_missing_client_is_a_clear_failure_of_the_registration_step_only(self):
        empty = self.base / "empty-path"
        empty.mkdir()
        with mock.patch.dict(os.environ, {"PATH": str(empty)}):
            code, out, err = run_main("--apply", "--host", EXAMPLE_HOST, "--home", str(self.home), "--codex-bin",
                                      str(self.codex), "--skip", "verify")
        self.assertEqual(code, 1)
        self.assertIn("no claude binary", out)
        self.assertTrue((self.home / ".claude/settings.json").exists())
        self.assertFalse(self.marker.exists())

    def test_an_environment_that_names_another_config_directory_is_refused_for_the_real_home(self):
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.base / "elsewhere")}):
            with mock.patch.object(cfg.Path, "home", return_value=self.home):
                code, _, err = run_main("--apply", "--host", EXAMPLE_HOST, "--home", str(self.home), "--claude-bin",
                                        str(self.claude))
        self.assertEqual(code, 2)
        self.assertIn("CLAUDE_CONFIG_DIR or CODEX_HOME is set", err)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_a_host_value_file_whose_home_is_the_root_is_refused_and_nothing_is_moved_or_written(self):
        # The example host's values with its home at the root: HOME "/" (or "//"), its home paths written from the root
        # and HOST_PATH as it is. Without its trailing slashes such a HOME is empty, a prefix of every absolute path:
        # the code before the fix moved /usr/local/sbin, HOST_PATH's first entry, under the new home and applied that.
        example = json.loads((render_config.HOSTS / f"{EXAMPLE_HOST}.json").read_text(encoding="utf-8"))
        hosts = self.base / "hosts"
        hosts.mkdir()
        plan = cfg.analyse(ROOT)[2]
        for declared in ("/", "//"):
            root_home = {k: (declared if k == "HOME" else v.replace(example["HOME"], "")) for k, v in example.items()}
            (hosts / "root-home.json").write_text(json.dumps(root_home, indent=2) + "\n", encoding="utf-8")
            with self.subTest(declared=declared), mock.patch.object(render_config, "HOSTS", hosts):
                code, out, err = run_main("--apply", "--host", "root-home", "--home", str(self.home), "--claude-bin",
                                          str(self.claude), "--codex-bin", str(self.codex), "--codex-process-name",
                                          NO_PROCESS)
                self.assertEqual(code, 1, out[-600:])
                self.assertTrue(err.startswith(f"apply failed: the host value file declares HOME as {declared!r}"), err)
                self.assertEqual(list(self.home.iterdir()), [])
                self.assertFalse(self.marker.exists(), "a client ran")
                with self.assertRaises(cfg.ConfigError):
                    cfg.host_values("root-home", plan, self.home, [])
                # With the new home at the root as well nothing moves: the values are those of a render without --home.
                self.assertEqual(cfg.host_values("root-home", plan, Path("/"), []),
                                 cfg.host_values("root-home", plan, None, []))
        # A home below the root moves the paths under it and leaves the system's directories where they are.
        values = cfg.host_values(EXAMPLE_HOST, plan, self.home, [])
        self.assertEqual((values["HOME"], values["ECO_ROOT"], values["HOST_PATH"]),
                         (str(self.home), str(self.eco), example["HOST_PATH"]))


def leaves(node, prefix=()):
    """{key path: JSON text of the value} of every leaf of a parsed settings or config tree."""
    if isinstance(node, dict) and node:
        found = {}
        for key, value in node.items():
            found.update(leaves(value, prefix + (key,)))
        return found
    return {prefix: json.dumps(node, sort_keys=True)}


class AuthorizationTests(ApplyCase):
    """The settings that grant a permission or suppress a confirmation are written only on request: the five that stand
    alone, the main checkout's Codex trust grant, and the tool approval modes and allow rules tied to the slot that wires
    their server."""

    STANDALONE = ("claude/settings/setting/permissions.defaultMode", "claude/settings/setting/skipDangerousModePermissionPrompt",
                  "codex/config/approval_policy", "codex/config/sandbox_mode",
                  # the user's directive of 2026-10-04 (the wave-2 messaging ruling left it unset)
                  "claude/settings/setting/crossSessionInbound")
    # The coordinator's decision of 2026-10-04: the main checkout is trusted, and Codex looks a linked worktree's trust
    # up under it (codex-rs/git-utils/src/trust.rs at rust-v0.160.0); every other project still asks.
    TRUST = ('codex/config/projects."${PROJECT_ROOT}".trust_level',)
    # Wave 5 adds Chrome's scoped approval piece to the existing owner approvals.
    APPROVAL = ("codex/config/mcp_servers.ai-memory.default_tools_approval_mode",
                "codex/config/mcp_servers.semble.default_tools_approval_mode",
                "codex/config/mcp_servers.context-mode.default_tools_approval_mode",
                "codex/config/mcp_servers.jcodemunch.default_tools_approval_mode",
                "codex/config/mcp_servers.chrome-devtools.default_tools_approval_mode",
                "codex/stack-worker/mcp_servers.ai-memory.default_tools_approval_mode",
                "codex/stack-worker/mcp_servers.socraticode.default_tools_approval_mode",
                "codex/stack-worker/mcp_servers.headroom.default_tools_approval_mode")
    # semble's exact-name allow rules for Claude Code (wave-2 code-search ruling, change 3).
    ALLOW = ("claude/settings/permission/allow/mcp__semble__search",
             "claude/settings/permission/allow/mcp__semble__find_related")
    ALL = STANDALONE + TRUST + APPROVAL + ALLOW
    SLOT_OF = dict(zip(APPROVAL + ALLOW, (("memory-owner", "ai-memory"), ("code-search", "semble"),
                                          ("context-supply", "context-mode"), ("code-index", "jcodemunch"),
                                          ("playwright-cli", "Chrome DevTools MCP 1.10.1 (one stdio MCP server, chrome-devtools, "
                                           "in both clients; it also serves browser diagnostics)"),
                                          ("memory-owner", "ai-memory"),
                                          ("code-search", "SocratiCode"), ("output-compression", "headroom"),
                                          ("code-search", "semble"), ("code-search", "semble"))))
    WAITING = APPROVAL[6:]                        # the same two negative-control owners, after Chrome's insertion
    WRITTEN = STANDALONE + TRUST + APPROVAL + ALLOW     # what the option writes today
    OPTION = "--with-authorization-settings"
    DEFAULT_LINE = ("authorization settings: left to the clients' own defaults (Claude Code permissions.defaultMode, "
                    "skipDangerousModePermissionPrompt and crossSessionInbound, Codex approval_policy and sandbox_mode, the trust_level of the wired "
                    "Codex projects, and the tool approval modes and allow rules of the wired MCP servers are not written, "
                    "and a value of theirs that a file has is not touched; --with-authorization-settings adds the ones a "
                    "file lacks, except existing create-only profile files)")

    def render(self, *extra: str):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_main("--render", "--host", EXAMPLE_HOST, "--out", tmp, *extra)
            self.assertEqual(code, 0, err)
            return (json.loads((Path(tmp) / "settings.json").read_text()),
                    tomllib.loads((Path(tmp) / "codex.config.toml").read_text()))

    def seed(self, settings=None, codex_text=None) -> None:
        self.installed_state()
        if settings is not None:
            (self.home / ".claude").mkdir(exist_ok=True)
            (self.home / ".claude" / "settings.json").write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
        if codex_text is not None:
            (self.home / ".codex").mkdir(mode=0o700, exist_ok=True)
            (self.home / ".codex" / "config.toml").write_text(codex_text, encoding="utf-8")
            (self.home / ".codex" / "config.toml").chmod(0o600)

    def authorization_line(self, out: str) -> str:
        lines = [line for line in out.splitlines() if line.startswith("authorization settings:")]
        self.assertEqual(len(lines), 1, lines)       # one line, once
        return lines[0]

    def test_the_map_classes_the_authorization_settings_and_the_deny_list_stays_practice(self):
        results, *_ = cfg.analyse(ROOT)
        by_key = {v.piece.key: v for v in results}
        self.assertEqual({v.piece.key for v in results if v.authorization}, set(self.ALL))
        for key in self.ALL:
            self.assertFalse(by_key[key].wired, key)
            self.assertIn("not written unless --with-authorization-settings is given", by_key[key].reason)
            self.assertEqual(by_key[key].entry.wiring.partition(":")[0], "authorization")
            self.assertTrue(by_key[key].entry.wiring.partition(":")[2].strip(), "a reason")
            # The four settings and the trust grant stand alone; a tool approval mode or an allow rule is tied to the slot
            # that wires its server as well.
            self.assertEqual((by_key[key].entry.slot, by_key[key].entry.owner), self.SLOT_OF.get(key, ("", "")), key)
        deny = [v for v in results if "/permission/deny/" in v.piece.key and v.entry.wiring == "practice"]
        self.assertGreater(len(deny), 100)
        self.assertTrue(all(v.wired for v in deny))
        with_option, *_ = cfg.analyse(ROOT, authorization=True)
        self.assertEqual({v.piece.key for v in with_option if v.authorization and v.wired}, set(self.WRITTEN))
        with tempfile.TemporaryDirectory() as tmp:   # preserve the absent-owner control after wave 3 installs both
            root = make_catalog(Path(tmp))
            def without_owners(data):
                for row in data["slots"]:
                    if row.get("catalog") == "foundation" and row["slot_id"] in ("code-search", "output-compression"):
                        row.pop("interim", None)
                        row.update(default="semble", installs_nothing_extra=False, state="definitive")
                        row["resolution"] = {"outcome": "final"}
            edit_json(root / cfg.MANIFEST_REL, without_owners)
            absent_owners, *_ = cfg.analyse(root, authorization=True)
        for verdict in absent_owners:       # a tool approval mode waits while its slot installs another owner
            if verdict.piece.key in self.WAITING:
                self.assertFalse(verdict.wired, verdict.piece.key)
                self.assertIn(f"not written although {self.OPTION} was given: slot {self.SLOT_OF[verdict.piece.key][0]} "
                              "installs", verdict.reason)
        self.assertEqual({v.piece.key for v in with_option if v.wired} - {v.piece.key for v in results if v.wired},
                         set(self.WRITTEN))

    def test_the_default_render_has_none_of_the_authorization_keys_and_the_option_adds_those_and_nothing_else(self):
        settings, codex = self.render()
        self.assertNotIn("defaultMode", settings["permissions"])
        self.assertNotIn("allow", settings["permissions"])
        self.assertNotIn("skipDangerousModePermissionPrompt", settings)
        self.assertNotIn("crossSessionInbound", settings)
        self.assertNotIn("approval_policy", codex)
        self.assertNotIn("sandbox_mode", codex)
        self.assertNotIn("projects", codex)
        self.assertEqual([name for name, server in codex["mcp_servers"].items() if "default_tools_approval_mode" in server],
                         [])
        settings_on, codex_on = self.render(self.OPTION)
        self.assertEqual(settings_on["permissions"]["defaultMode"], "bypassPermissions")
        self.assertIs(settings_on["skipDangerousModePermissionPrompt"], True)
        self.assertEqual(settings_on["crossSessionInbound"], "accept")
        self.assertEqual(settings_on["permissions"]["allow"], ["mcp__semble__search", "mcp__semble__find_related"])
        self.assertEqual((codex_on["approval_policy"], codex_on["sandbox_mode"]), ("never", "danger-full-access"))
        self.assertEqual({name: server["default_tools_approval_mode"] for name, server in codex_on["mcp_servers"].items()
                          if "default_tools_approval_mode" in server},
                         {"ai-memory": "approve", "semble": "approve", "context-mode": "approve", "jcodemunch": "approve",
                          "chrome-devtools": "approve"})
        # One trust grant, for the host's main checkout (PROJECT_ROOT) and nothing else: no parent directory, and not
        # the publication checkout the shared template also names.
        project_root = json.loads((ROOT / "adoption/hosts/example.json").read_text())["PROJECT_ROOT"]
        self.assertEqual(codex_on["projects"], {project_root: {"trust_level": "trusted"}})
        # The two renders differ in those keys and in nothing else; the deny list is in both.
        for off, on in ((settings, settings_on), (codex, codex_on)):
            self.assertEqual(sorted(set(leaves(on)) - set(leaves(off))), sorted(
                [("permissions", "defaultMode"), ("skipDangerousModePermissionPrompt",), ("crossSessionInbound",),
                 ("permissions", "allow")]
                if on is settings_on else
                [("approval_policy",), ("sandbox_mode",), ("mcp_servers", "ai-memory", "default_tools_approval_mode"),
                 ("mcp_servers", "semble", "default_tools_approval_mode"),
                 ("mcp_servers", "context-mode", "default_tools_approval_mode"),
                 ("mcp_servers", "jcodemunch", "default_tools_approval_mode"),
                 ("mcp_servers", "chrome-devtools", "default_tools_approval_mode"),
                 ("projects", project_root, "trust_level")]))
            self.assertEqual(set(leaves(off)) - set(leaves(on)), set())
            self.assertEqual({k: v for k, v in leaves(on).items() if k in leaves(off)}, leaves(off))
        self.assertEqual(settings["permissions"]["deny"], settings_on["permissions"]["deny"])
        self.assertGreater(len(settings["permissions"]["deny"]), 100)

    # In the order of the pieces: the additions (semble's allow rules and server) merge after the shared template's keys.
    ALLOW_LABELS = "Claude Code allow rule mcp__semble__search, Claude Code allow rule mcp__semble__find_related"
    ADDED_CLAUDE = (f"added: Claude Code permissions.defaultMode, {ALLOW_LABELS}, Claude Code skipDangerousModePermissionPrompt, "
                    "Claude Code crossSessionInbound")
    CODEX_CONFIG = ("Codex approval_policy, Codex sandbox_mode, Codex mcp_servers.ai-memory.default_tools_approval_mode, "
                    "Codex mcp_servers.context-mode.default_tools_approval_mode, "
                    "Codex mcp_servers.jcodemunch.default_tools_approval_mode, "
                    "Codex mcp_servers.semble.default_tools_approval_mode, "
                    "Codex mcp_servers.chrome-devtools.default_tools_approval_mode, "
                    'Codex projects."${PROJECT_ROOT}".trust_level')
    STACK_WORKER = ("Codex stack-worker profile mcp_servers.ai-memory.default_tools_approval_mode, "
                    "Codex stack-worker profile mcp_servers.socraticode.default_tools_approval_mode, "
                    "Codex stack-worker profile mcp_servers.headroom.default_tools_approval_mode")
    TRUST_LABEL = 'Codex projects."${PROJECT_ROOT}".trust_level'

    def test_a_fresh_apply_writes_none_by_default_and_all_of_them_with_the_option(self):
        self.seed()
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-800:])
        settings = json.loads((self.home / ".claude/settings.json").read_text())
        config = tomllib.loads((self.home / ".codex/config.toml").read_text())
        self.assertNotIn("defaultMode", settings["permissions"])
        self.assertNotIn("allow", settings["permissions"])
        self.assertNotIn("skipDangerousModePermissionPrompt", settings)
        self.assertEqual({"approval_policy", "sandbox_mode"} & set(config), set())
        self.assertEqual([name for name, server in config["mcp_servers"].items() if "default_tools_approval_mode" in server],
                         [])
        self.assertEqual(self.authorization_line(out), self.DEFAULT_LINE)
        # Negative control: the same home with the option gets every one, in both clients and the stack-worker profile.
        code, out, _ = self.apply(self.OPTION)
        self.assertEqual(code, 0, out[-800:])
        settings = json.loads((self.home / ".claude/settings.json").read_text())
        config = tomllib.loads((self.home / ".codex/config.toml").read_text())
        self.assertEqual(settings["permissions"]["defaultMode"], "bypassPermissions")
        self.assertEqual(settings["permissions"]["allow"], ["mcp__semble__search", "mcp__semble__find_related"])
        self.assertIs(settings["skipDangerousModePermissionPrompt"], True)
        self.assertEqual((config["approval_policy"], config["sandbox_mode"]), ("never", "danger-full-access"))
        for server in ("ai-memory", "semble", "context-mode"):
            self.assertEqual(config["mcp_servers"][server]["default_tools_approval_mode"], "approve", server)
        # The stack-worker profile is created only when absent, so the profile the plain run created stays as it was.
        line = self.authorization_line(out)
        self.assertEqual(line, f"authorization settings: partly applied (--with-authorization-settings; {self.ADDED_CLAUDE}, "
                               f"{self.CODEX_CONFIG}; not reached, its step codex-files ended differs, not written: "
                               f"{self.STACK_WORKER})")
        # Main configuration settings are now present; missing keys in create-only profiles remain not reached.
        code, out, _ = self.apply(self.OPTION)
        self.assertEqual(code, 0, out[-800:])
        line = self.authorization_line(out)
        self.assertEqual(line, f"authorization settings: not applied (--with-authorization-settings; already the same: "
                               f"{self.ADDED_CLAUDE[len('added: '):]}, {self.CODEX_CONFIG}; "
                               f"not reached, its step codex-files ended differs, not written: {self.STACK_WORKER})")

    def test_profile_formatting_and_model_drift_do_not_change_equal_authorization_values(self):
        self.seed()
        code, out, _ = self.apply(self.OPTION)
        self.assertEqual(code, 0, out[-800:])
        profile = self.home / ".codex/stack-worker.config.toml"
        original = profile.read_text()
        for text in ("# different formatting\n" + original,
                     original.replace('default_tools_approval_mode = "approve"',
                                      "default_tools_approval_mode = 'approve'"),
                     original.replace('model = "gpt-6.1-sol"', 'model = "local-choice"', 1)):
            with self.subTest(format_only=text.startswith("# different formatting")):
                self.assertNotEqual(text, original)
                parsed, baseline = tomllib.loads(text), tomllib.loads(original)
                for server in ("ai-memory", "socraticode", "headroom"):
                    self.assertEqual(parsed["mcp_servers"][server]["default_tools_approval_mode"],
                                     baseline["mcp_servers"][server]["default_tools_approval_mode"])
                profile.write_text(text, encoding="utf-8")
                code, out, _ = self.apply(self.OPTION)
                self.assertEqual(code, 0, out[-800:])
                self.assertEqual(profile.read_text(), text)
                line = self.authorization_line(out)
                self.assertIn("already the same: ", line)
                self.assertIn(self.STACK_WORKER, line.split("already the same: ", 1)[1])
                self.assertNotIn("kept your value:", line)
                self.assertNotIn("not reached", line)
                self.assertIn("codex-files differs, not written", out.split("summary: ")[1])

    def test_only_the_changed_profile_authorization_key_is_kept(self):
        self.seed()
        code, out, _ = self.apply(self.OPTION)
        self.assertEqual(code, 0, out[-800:])
        profile = self.home / ".codex/stack-worker.config.toml"
        original = profile.read_text()
        text = original.replace('[mcp_servers.ai-memory]\ndefault_tools_approval_mode = "approve"',
                                '[mcp_servers.ai-memory]\ndefault_tools_approval_mode = false', 1)
        self.assertNotEqual(text, original)
        self.assertIs(tomllib.loads(text)["mcp_servers"]["ai-memory"]["default_tools_approval_mode"], False)
        profile.write_text(text, encoding="utf-8")
        code, out, _ = self.apply(self.OPTION)
        self.assertEqual(code, 0, out[-800:])
        self.assertEqual(profile.read_text(), text)
        line = self.authorization_line(out)
        kept = line.split("kept your value: ", 1)[1].split(";", 1)[0]
        self.assertEqual(kept, "Codex stack-worker profile mcp_servers.ai-memory.default_tools_approval_mode")
        self.assertIn("Codex stack-worker profile mcp_servers.socraticode.default_tools_approval_mode",
                      line.split("already the same: ", 1)[1])
        self.assertIn("Codex stack-worker profile mcp_servers.headroom.default_tools_approval_mode",
                      line.split("already the same: ", 1)[1])
        self.assertNotIn("not reached", line)

    def test_an_absent_key_in_an_existing_profile_is_not_reported_as_kept(self):
        self.seed()
        code, out, _ = self.apply(self.OPTION)
        self.assertEqual(code, 0, out[-800:])
        profile = self.home / ".codex/stack-worker.config.toml"
        original = profile.read_text()
        text = original.replace('[mcp_servers.ai-memory]\ndefault_tools_approval_mode = "approve"',
                                '[mcp_servers.ai-memory]', 1)
        self.assertNotEqual(text, original)
        self.assertNotIn("default_tools_approval_mode", tomllib.loads(text)["mcp_servers"]["ai-memory"])
        profile.write_text(text, encoding="utf-8")
        code, out, _ = self.apply(self.OPTION)
        self.assertEqual(code, 0, out[-800:])
        self.assertEqual(profile.read_text(), text)
        line = self.authorization_line(out)
        self.assertTrue(line.startswith("authorization settings: not applied "), line)
        self.assertNotIn("kept your value:", line)
        self.assertIn("not reached, its step codex-files ended differs, not written: "
                      "Codex stack-worker profile mcp_servers.ai-memory.default_tools_approval_mode", line)
        self.assertIn("Codex stack-worker profile mcp_servers.socraticode.default_tools_approval_mode",
                      line.split("already the same: ", 1)[1])

    def test_malformed_profile_authorization_is_failed_and_preserved(self):
        self.seed()
        code, out, _ = self.apply(self.OPTION)
        self.assertEqual(code, 0, out[-800:])
        profile = self.home / ".codex/stack-worker.config.toml"
        for data in (b"[invalid\n", b"\xff"):
            with self.subTest(data=data):
                profile.write_bytes(data)
                code, out, _ = self.apply(self.OPTION)
                self.assertEqual(code, 1, out[-800:])
                self.assertEqual(profile.read_bytes(), data)
                self.assertIn("codex-files failed", out.split("summary: ")[1])
                line = self.authorization_line(out)
                self.assertIn("not reached, its step codex-files failed: " + self.STACK_WORKER, line)
                self.assertNotIn("kept your value:", line)

    def test_dry_run_with_a_stale_profile_reports_both_creation_and_preservation(self):
        self.seed()
        profile = self.home / ".codex/stack-worker.config.toml"
        profile.parent.mkdir(mode=0o700)
        profile.write_text("model = 'local-choice'\n", encoding="utf-8")
        before = tree(self.home)
        code, out, _ = self.apply(self.OPTION, dry=True)
        self.assertEqual(code, 0, out[-800:])
        self.assertEqual(tree(self.home), before)
        self.assertFalse(self.marker.exists())
        self.assertIn("codex-files planned; differs, not written", out.split("summary: ")[1])
        self.assertTrue(self.authorization_line(out).startswith("authorization settings: would be partly applied "), out)
        self.assertIn("not reached, its step codex-files ended planned; differs, not written: " + self.STACK_WORKER, out)

    def test_a_new_codex_home_with_the_option_keeps_the_trust_grant_and_a_second_run_finds_it_the_same(self):
        # codex_home.py --keep-project-trust: the grant the render holds survives the creation of config.toml, so the
        # line's "added" is true; the merge of the second run looks the grant up under the path the render filled in
        # for ${PROJECT_ROOT}, finds it and adds nothing.
        self.seed()
        self.assertFalse((self.home / ".codex/config.toml").exists())
        code, out, _ = self.apply(self.OPTION)
        self.assertEqual(code, 0, out[-800:])
        text = (self.home / ".codex/config.toml").read_text()
        self.assertTrue(text.startswith("# Written by tools/adoption/codex_home.py --keep-hook-trust "
                                        "--keep-project-trust from the user config"), text[:200])
        main_checkout = str(self.home / "code/agent-lab")   # the example host's PROJECT_ROOT, moved under --home
        self.assertEqual(tomllib.loads(text)["projects"], {main_checkout: {"trust_level": "trusted"}})
        trust = self.TRUST_LABEL
        self.assertIn(trust, self.authorization_line(out).split("added: ", 1)[1].split("; ", 1)[0].split(", "))
        code, out, _ = self.apply(self.OPTION)
        self.assertEqual(code, 0, out[-800:])
        line = self.authorization_line(out)
        self.assertNotIn("added: ", line)
        self.assertIn(trust, line.split("already the same: ", 1)[1].split("; ", 1)[0].split(", "))
        self.assertEqual(tomllib.loads((self.home / ".codex/config.toml").read_text())["projects"],
                         {main_checkout: {"trust_level": "trusted"}})

    def test_a_trust_answer_the_file_already_has_is_kept_and_named(self):
        # The person said no to the folder once: the merge keeps the file's answer, and the line says so.
        main_checkout = str(self.home / "code/agent-lab")
        self.seed(codex_text=f'[projects."{main_checkout}"]\ntrust_level = "untrusted"\n')
        code, out, _ = self.apply(self.OPTION)
        self.assertEqual(code, 0, out[-800:])
        config = tomllib.loads((self.home / ".codex/config.toml").read_text())
        self.assertEqual(config["projects"], {main_checkout: {"trust_level": "untrusted"}})
        self.assertIn(self.TRUST_LABEL, self.authorization_line(out).split("kept your value: ", 1)[1])

    def test_the_destinations_files_gain_them_only_with_the_option(self):
        self.seed(DESTINATION_CLAUDE, DESTINATION_CODEX)
        for extra, present in (((), False), ((self.OPTION,), True)):
            with self.subTest(option=bool(extra)):
                code, out, _ = self.apply(*extra)
                self.assertEqual(code, 0, out[-800:])
                settings = json.loads((self.home / ".claude/settings.json").read_text())
                config = tomllib.loads((self.home / ".codex/config.toml").read_text())
                self.assertEqual("defaultMode" in settings["permissions"], present)
                self.assertEqual("allow" in settings["permissions"], present)
                self.assertEqual("skipDangerousModePermissionPrompt" in settings, present)
                self.assertEqual("approval_policy" in config, present)
                self.assertEqual("sandbox_mode" in config, present)
                self.assertEqual("projects" in config, present)
                for server in ("ai-memory", "semble", "context-mode"):
                    self.assertEqual("default_tools_approval_mode" in config["mcp_servers"][server], present, server)
                self.assertEqual(settings["theme"], "auto")                       # the destination's own keys stay
                self.assertEqual(config["marketplaces"]["trailofbits"]["ref"], PLAN_COMMIT)

    def test_an_existing_value_survives_a_default_apply_and_one_with_the_option_and_both_values_are_printed(self):
        mine = {"permissions": {"defaultMode": "default", "deny": ["Read(~/mine)"]}, "skipDangerousModePermissionPrompt": False}
        codex_text = 'approval_policy = "on-request"\nsandbox_mode = "workspace-write"\n'
        self.seed(mine, codex_text)
        for extra in ((), (self.OPTION,), ()):
            with self.subTest(option=bool(extra)):
                code, out, _ = self.apply(*extra)
                self.assertEqual(code, 0, out[-800:])
                settings = json.loads((self.home / ".claude/settings.json").read_text())
                config = tomllib.loads((self.home / ".codex/config.toml").read_text())
                self.assertEqual(settings["permissions"]["defaultMode"], "default")
                self.assertIs(settings["skipDangerousModePermissionPrompt"], False)
                self.assertEqual((config["approval_policy"], config["sandbox_mode"]), ("on-request", "workspace-write"))
                self.assertIn("Read(~/mine)", settings["permissions"]["deny"])   # the person's own rule stays beside ours
                if extra:
                    for expected in ('kept your permissions.defaultMode: "default" (the render has "bypassPermissions")',
                                     "kept your skipDangerousModePermissionPrompt: false (the render has true)",
                                     'conflict kept: approval_policy: the file has "on-request"; the render has "never"',
                                     'conflict kept: sandbox_mode: the file has "workspace-write"; the render has '
                                     '"danger-full-access"'):
                        self.assertIn(expected, out)
                    self.assertIn("codex-config merged with conflicts kept", out.split("summary: ")[1])
                    # The person's four values stay; what the files lack (the allow rules and approval modes) is added.
                    line = self.authorization_line(out)
                    self.assertTrue(line.startswith("authorization settings: partly applied (--with-authorization-settings; "
                                                    f"added: {self.ALLOW_LABELS}, "), line)
                    # The stack-worker profile the plain run created is kept too (profiles are created only when absent).
                    self.assertIn("kept your value: Claude Code permissions.defaultMode, Claude Code "
                                  "skipDangerousModePermissionPrompt, Codex approval_policy, Codex sandbox_mode", line)
                    self.assertIn("not reached, its step codex-files ended differs, not written: "
                                  f"{self.STACK_WORKER})", line)
                else:
                    self.assertNotIn("kept your permissions.defaultMode", out)
                    self.assertNotIn("conflict kept: approval_policy", out)
                    self.assertTrue(self.authorization_line(out).startswith("authorization settings: left to the clients' "
                                                                            "own defaults"))

    def test_with_the_option_a_setting_one_file_has_and_another_lacks_is_added_only_where_it_is_missing(self):
        self.seed({"permissions": {"defaultMode": "plan"}}, 'sandbox_mode = "read-only"\n')
        code, out, _ = self.apply(self.OPTION)
        self.assertEqual(code, 0, out[-800:])
        settings = json.loads((self.home / ".claude/settings.json").read_text())
        config = tomllib.loads((self.home / ".codex/config.toml").read_text())
        self.assertEqual(settings["permissions"]["defaultMode"], "plan")                # kept
        self.assertIs(settings["skipDangerousModePermissionPrompt"], True)              # added
        self.assertEqual(config["sandbox_mode"], "read-only")                           # kept
        self.assertEqual(config["approval_policy"], "never")                            # added
        line = self.authorization_line(out)
        added = line.split("added: ", 1)[1].split("; ", 1)[0].split(", ")
        self.assertTrue({"Claude Code skipDangerousModePermissionPrompt", "Codex approval_policy"} <= set(added), added)
        self.assertNotIn("Claude Code permissions.defaultMode", added)
        self.assertNotIn("Codex sandbox_mode", added)
        self.assertIn("kept your value: Claude Code permissions.defaultMode, Codex sandbox_mode", line)

    def test_a_dry_run_with_the_option_writes_nothing_and_says_what_would_be_applied(self):
        self.seed()
        before = tree(self.home)
        code, out, _ = self.apply(self.OPTION, dry=True)
        self.assertEqual(code, 0, out[-600:])
        self.assertEqual(tree(self.home), before)
        self.assertTrue(self.authorization_line(out).startswith("authorization settings: would be applied ("), out[-600:])

    def test_the_apply_line_says_not_applied_when_every_step_that_would_write_the_settings_is_skipped(self):
        self.seed()
        code, out, _ = self.apply(self.OPTION, "--skip", "claude-settings", "--skip", "codex-config",
                                  "--skip", "codex-files")
        self.assertEqual(code, 0, out[-600:])
        self.assertEqual(self.authorization_line(out), (
            "authorization settings: not applied (--with-authorization-settings; not reached, its step claude-settings was "
            f"skipped: {self.ADDED_CLAUDE[len('added: '):]}; not reached, its step codex-config was skipped: "
            f"{self.CODEX_CONFIG}; not reached, its step codex-files was skipped: {self.STACK_WORKER})"))

    def test_a_skipped_step_leaves_the_line_partly_applied_and_says_it_was_skipped(self):
        self.seed()
        code, out, _ = self.apply(self.OPTION, "--skip", "codex-config")
        self.assertEqual(code, 0, out[-600:])
        self.assertEqual(self.authorization_line(out), (
            f"authorization settings: partly applied (--with-authorization-settings; {self.ADDED_CLAUDE}, "
            f"{self.STACK_WORKER}; not reached, its step codex-config was skipped: {self.CODEX_CONFIG})"))
        settings = json.loads((self.home / ".claude/settings.json").read_text())
        self.assertEqual(settings["permissions"]["defaultMode"], "bypassPermissions")    # what was reached is written
        self.assertFalse((self.home / ".codex/config.toml").exists())                      # what was not, is not

    def test_a_failed_step_leaves_the_line_partly_applied_and_says_it_failed(self):
        self.seed(codex_text="[tui\nbroken = \n")                                         # not TOML: the Codex step fails
        code, out, _ = self.apply(self.OPTION)
        self.assertEqual(code, 1)
        self.assertEqual(self.authorization_line(out), (
            f"authorization settings: partly applied (--with-authorization-settings; {self.ADDED_CLAUDE}, "
            f"{self.STACK_WORKER}; not reached, its step codex-config failed: {self.CODEX_CONFIG})"))
        self.assertEqual((self.home / ".codex/config.toml").read_text(), "[tui\nbroken = \n")

    def test_a_dry_run_with_a_skipped_step_says_it_would_be_partly_applied(self):
        self.seed()
        before = tree(self.home)
        code, out, _ = self.apply(self.OPTION, "--skip", "codex-config", dry=True)
        self.assertEqual(code, 0, out[-600:])
        self.assertEqual(self.authorization_line(out), (
            f"authorization settings: would be partly applied (--with-authorization-settings; {self.ADDED_CLAUDE}, "
            f"{self.STACK_WORKER}; not reached, its step codex-config was skipped: {self.CODEX_CONFIG})"))
        self.assertEqual(tree(self.home), before)

    def test_settings_that_are_kept_beside_a_step_that_is_not_reached_say_not_applied(self):
        # The file already has every Claude Code one (three of its own values, and semble's two allow rules), and the steps
        # that write the Codex ones are skipped: nothing is added.
        self.seed({"permissions": {"defaultMode": "default", "allow": ["mcp__semble__search", "mcp__semble__find_related"]},
                   "skipDangerousModePermissionPrompt": False, "crossSessionInbound": "hold"})
        code, out, _ = self.apply(self.OPTION, "--skip", "codex-config", "--skip", "codex-files")
        self.assertEqual(code, 0, out[-600:])
        self.assertEqual(self.authorization_line(out), (
            "authorization settings: not applied (--with-authorization-settings; kept your value: Claude Code "
            f"permissions.defaultMode, Claude Code skipDangerousModePermissionPrompt, Claude Code crossSessionInbound; "
            f"already the same: {self.ALLOW_LABELS}; "
            f"not reached, its step codex-config was skipped: {self.CODEX_CONFIG}; not reached, its step codex-files was "
            f"skipped: {self.STACK_WORKER})"))

    def test_the_line_says_so_when_the_map_wires_no_authorization_setting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))

            def drop(data):
                for entry in data["entries"]:
                    if entry["wiring"].startswith("authorization:"):
                        entry["wiring"] = "not_wired:a decision to drop them"
                        entry.pop("slot", None)
                        entry.pop("owner", None)
            edit_json(root / cfg.MAP_REL, drop)
            self.seed()
            code, out, _ = self.apply(self.OPTION, "--root", str(root))
        self.assertEqual(code, 0, out[-600:])
        self.assertEqual(self.authorization_line(out), (
            "authorization settings: not applied (--with-authorization-settings; no authorization setting is wired: the map "
            "leaves each out, or its slot does not install)"))

    def scenario(self, name: str, *extra: str, dry: bool = False, twice: bool = False, **seed) -> str:
        """The authorization line of one --apply in a home of its own (of the second, with twice=True)."""
        self.home = self.base / f"home-{name}"
        self.home.mkdir()
        self.eco = self.home / ".local/share/codex-ecosystem"
        self.seed(**seed)
        for _ in range(2 if twice else 1):
            code, out, _ = self.apply(*extra, dry=dry)
            self.assertEqual(code, 0, (name, out[-500:]))
        return self.authorization_line(out)

    def test_the_line_has_seven_outcomes_and_the_four_documents_name_every_one(self):
        lines = {
            "left to the clients' own defaults": self.scenario("plain"),
            "applied": self.scenario("applied", self.OPTION),
            "would be applied": self.scenario("would", self.OPTION, dry=True),
            "partly applied": self.scenario("partly", self.OPTION, "--skip", "codex-config"),
            "would be partly applied": self.scenario("would-partly", self.OPTION, "--skip", "codex-config", dry=True),
            "kept": self.scenario("kept", self.OPTION, twice=True),    # the second run finds every one already there
            "not applied": self.scenario("not", self.OPTION, "--skip", "claude-settings", "--skip", "codex-config",
                                         "--skip", "codex-files"),
        }
        for expected, line in lines.items():
            self.assertTrue(line.startswith(f"authorization settings: {expected} ("), (expected, line))
        # Those are all the outcomes there are, and the tool names the same seven.
        self.assertEqual(set(lines), set(cfg.AUTHORIZATION_OUTCOMES))
        # The recipe, the decision record, the receipt example and the tool's own text name every one, in the words printed.
        places = {"the recipe": (ROOT / "adoption/platforms/linux-wsl2-new-distro.md").read_text(encoding="utf-8"),
                  "the decision record": RecordTests.RECORD.read_text(encoding="utf-8"),
                  "the receipt example": (ROOT / "adoption/templates/wsl/stage1-receipt.example.json").read_text(encoding="utf-8"),
                  "the tool's docstring": cfg.__doc__}
        for place, text in places.items():
            normalized = " ".join(text.split())
            for outcome in cfg.AUTHORIZATION_OUTCOMES:
                self.assertIn(f"`{outcome}`", normalized, f"{place} does not name `{outcome}`")
        for place in ("the recipe", "the decision record", "the tool's docstring"):   # the prose says it the same way
            self.assertIn(recipe_tests.AUTHORIZATION_LINE_SENTENCE, " ".join(places[place].split()), place)

    def test_the_map_refuses_an_authorization_setting_classed_practice_or_slot(self):
        for key in self.STANDALONE:
            for wiring, owner in (("practice", None), ("slot:serena", "serena")):
                with self.subTest(piece=key, wiring=wiring), tempfile.TemporaryDirectory() as tmp:
                    root = make_catalog(Path(tmp))

                    def reclass(data):
                        entry = next(e for e in data["entries"] if key in e["match"])
                        entry["match"].remove(key)
                        if not entry["match"]:
                            data["entries"].remove(entry)
                        data["entries"].insert(0, {"match": [key], "wiring": wiring, **({"owner": owner} if owner else {})})
                    edit_json(root / cfg.MAP_REL, reclass)
                    errors = cfg.analyse(root)[3]
                    self.assertTrue(any(error.startswith(f"{key}: a setting that grants a permission or suppresses a "
                                                         "confirmation is classed authorization:<reason>") for error in errors),
                                    errors)
                    self.assertEqual(run_main("--check", "--root", str(root))[0], 1)
                    # --render and --apply refuse the map too, with and without the option.
                    for extra in ((), (self.OPTION,)):
                        out_dir = Path(tmp) / "out"
                        code, _, err = run_main("--render", "--host", EXAMPLE_HOST, "--out", str(out_dir), "--root", str(root),
                                                *extra)
                        self.assertEqual(code, 1)
                        self.assertIn("render refused", err)
                        self.assertFalse(out_dir.exists())

    def test_a_tool_approval_mode_that_the_map_classes_practice_or_slot_is_refused(self):
        for key in self.APPROVAL:
            slot, owner = self.SLOT_OF[key]
            for wiring in ("practice", f"slot:{slot}"):
                with self.subTest(piece=key, wiring=wiring), tempfile.TemporaryDirectory() as tmp:
                    root = make_catalog(Path(tmp))

                    def reclass(data, key=key, wiring=wiring):
                        entry = next(e for e in data["entries"] if e["wiring"].startswith("authorization")
                                     and any(fnmatch.fnmatchcase(key, pattern) for pattern in e["match"]))
                        entry["wiring"] = wiring
                        entry.pop("slot")
                    edit_json(root / cfg.MAP_REL, reclass)
                    errors = cfg.analyse(root)[3]
                    kind = wiring.partition(":")[0]
                    self.assertTrue(any(error.startswith(
                        f"{key}: a setting that grants a permission or suppresses a confirmation is classed "
                        f"authorization:<reason>, not {kind}") for error in errors), errors)
                    self.assertEqual(run_main("--check", "--root", str(root))[0], 1)
                    out_dir = Path(tmp) / "out"
                    code, _, err = run_main("--render", "--host", EXAMPLE_HOST, "--out", str(out_dir), "--root", str(root))
                    self.assertEqual(code, 1)
                    self.assertIn("render refused", err)

    def test_the_predicate_takes_every_default_tools_approval_mode_and_an_approving_approval_mode_and_nothing_else(self):
        for key, value, expected in (
                ("codex/config/mcp_servers.x.default_tools_approval_mode", "approve", True),
                ("codex/config/mcp_servers.x.default_tools_approval_mode", "prompt", True),     # the key, whatever its value
                ("codex/config/mcp_servers.x.tools.y.approval_mode", "approve", True),
                ("codex/config/mcp_servers.x.tools.y.approval_mode", "prompt", False),         # a mode that asks restricts
                ("codex/config/mcp_servers.x.tools.y.approval_mode", "writes", False),
                ("codex/config/mcp_servers.x.tools.y.approval_mode", "auto", False),
                ("codex/config/mcp_servers.x.tools.y.approval_mode", ["approve"], False),
                ("codex/config/mcp_servers.x.enabled_tools", ["approve"], False),
                ("claude/settings/env/default_tools_approval_mode", "approve", False),          # an environment variable
                ("claude/settings/permission/allow/Bash(ls)", None, True),
                ("claude/settings/permission/deny/Bash(rm *)", None, False),
                ("codex/config/approval_policy", "never", True),
                ('codex/config/projects."/srv/repo".trust_level', "trusted", True),
                ('codex/config/projects."/srv/repo".trust_level', "untrusted", True),     # a saved answer, either way
                ('codex/stack-worker/projects."/srv/repo".trust_level', "trusted", True),
                ('codex/config/projects."/srv/repo".other', "x", False),
                ("codex/config/model", "gpt-6.1-sol", False)):
            self.assertEqual(cfg.is_authorization_piece(key, value), expected, (key, value))
        # Without the value only the key decides.
        self.assertTrue(cfg.is_authorization_piece("codex/config/mcp_servers.x.default_tools_approval_mode"))
        self.assertFalse(cfg.is_authorization_piece("codex/config/mcp_servers.x.tools.y.approval_mode"))

    SERENA_TABLE = "[mcp_servers.serena.env]"

    def serena_catalog(self, tmp: str, extra_lines: str) -> Path:
        """A scratch catalog whose Codex template gives the serena server, which the manifest installs, extra lines."""
        root = make_catalog(Path(tmp))
        template = root / cfg.TEMPLATES["codex/config"]
        text = template.read_text(encoding="utf-8")
        self.assertEqual(text.count(self.SERENA_TABLE), 1)
        template.write_text(text.replace(self.SERENA_TABLE, extra_lines + "\n" + self.SERENA_TABLE), encoding="utf-8")
        return root

    def test_a_wired_server_that_gains_an_approving_mode_is_caught_and_its_key_is_written_only_with_the_option(self):
        key = "codex/config/mcp_servers.serena.default_tools_approval_mode"
        with tempfile.TemporaryDirectory() as tmp:
            root = self.serena_catalog(tmp, 'default_tools_approval_mode = "approve"\n')
            # The serena slot installs, so the map's slot entry would wire the key, and a plain --apply would write it.
            verdict = next(v for v in cfg.analyse(root)[0] if v.piece.key == key)
            self.assertEqual((verdict.entry.wiring.partition(":")[0], verdict.wired), ("slot", True))
            errors = cfg.analyse(root)[3]
            self.assertTrue(any(e.startswith(f"{key}: a setting that grants a permission or suppresses a confirmation is "
                                             "classed authorization:<reason>, not slot") for e in errors), errors)
            self.assertEqual(run_main("--check", "--root", str(root))[0], 1)
            code, _, err = run_main("--render", "--host", EXAMPLE_HOST, "--out", str(Path(tmp) / "refused"), "--root",
                                    str(root))
            self.assertEqual((code, "render refused" in err), (1, True))
            # Classed authorization and tied to its slot, the key is the option's to write, and the server is wired either way.
            edit_json(root / cfg.MAP_REL, lambda d: d["entries"].insert(0, {
                "match": [key], "wiring": "authorization:an auto-approval", "slot": "serena", "owner": "Serena"}))
            self.assertEqual(cfg.analyse(root)[3], [])
            for option, present in ((False, False), (True, True)):
                out_dir = Path(tmp) / f"render-{option}"
                code, _, err = run_main("--render", "--host", EXAMPLE_HOST, "--out", str(out_dir), "--root", str(root),
                                        *([self.OPTION] if option else []))
                self.assertEqual(code, 0, err)
                serena = tomllib.loads((out_dir / "codex.config.toml").read_text())["mcp_servers"]["serena"]
                self.assertEqual("default_tools_approval_mode" in serena, present)
                self.assertEqual(serena.get("default_tools_approval_mode"), "approve" if present else None)
                self.assertIn("command", serena)                                           # the server is wired both ways
            # A plain --apply leaves the key out of the file and the line says so; with the option it is added.
            for option in (False, True):
                self.home = self.base / f"home-serena-{option}"
                self.home.mkdir()
                self.seed()
                code, out, _ = self.apply("--root", str(root), *([self.OPTION] if option else []))
                self.assertEqual(code, 0, out[-500:])
                config = tomllib.loads((self.home / ".codex/config.toml").read_text())
                self.assertEqual("default_tools_approval_mode" in config["mcp_servers"]["serena"], option)
                line = self.authorization_line(out)
                self.assertEqual("Codex mcp_servers.serena.default_tools_approval_mode" in line, option, line)

    def test_a_tool_approval_mode_of_one_tool_is_caught_when_it_approves_and_left_alone_when_it_asks(self):
        key = "codex/config/mcp_servers.serena.tools.search.approval_mode"
        for value, caught in (("approve", True), ("prompt", False)):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                root = self.serena_catalog(tmp, f'[mcp_servers.serena.tools.search]\napproval_mode = "{value}"\n')
                errors = cfg.analyse(root)[3]
                self.assertEqual(any(e.startswith(f"{key}: a setting that grants a permission") for e in errors), caught,
                                 errors)
                self.assertEqual(run_main("--check", "--root", str(root))[0], 1 if caught else 0)

    def test_when_the_slot_of_a_server_installs_its_approval_mode_is_still_written_only_with_the_option(self):
        key = "codex/stack-worker/mcp_servers.ai-memory.default_tools_approval_mode"
        self.assertIn(key, self.APPROVAL)
        with tempfile.TemporaryDirectory() as tmp:
            # The memory-owner slot installs ai-memory (its interim install, amendment 3).
            root = make_catalog(Path(tmp))
            self.assertEqual(cfg.analyse(root)[3], [])
            for option, present in ((False, False), (True, True)):
                results, manifest, plan, errors, _ = cfg.analyse(root, authorization=option)
                self.assertEqual(errors, [])
                verdict = next(v for v in results if v.piece.key == key)
                self.assertEqual(verdict.wired, option, verdict.reason)
                self.assertIn("slot memory-owner installs ai-memory", verdict.reason)         # the slot is not what holds it back
                files = cfg.render(root, results, plan, cfg.host_values(EXAMPLE_HOST, plan, None, cfg.wired_path_dirs(results)),
                                   manifest)
                table = tomllib.loads(files["codex.stack-worker.config.toml"])["mcp_servers"]["ai-memory"]
                self.assertIn("enabled_tools", table)                                         # the server's own keys are in
                self.assertEqual("default_tools_approval_mode" in table, present)
            # A plain --apply creates the profile without the key; with the option, it has it and the line says it was added.
            for option in (False, True):
                self.home = self.base / f"home-ai-memory-{option}"
                self.home.mkdir()
                self.seed()
                # The Claude registration of the newly wired server and the login-shell probe are not what this is about.
                code, out, _ = self.apply("--root", str(root), "--skip", "claude-mcp", "--skip", "verify",
                                          *([self.OPTION] if option else []))
                self.assertEqual(code, 0, out[-500:])
                profile = tomllib.loads((self.home / ".codex/stack-worker.config.toml").read_text())
                self.assertEqual("default_tools_approval_mode" in profile["mcp_servers"]["ai-memory"], option)
                line = self.authorization_line(out)
                if option:
                    self.assertTrue(line.startswith("authorization settings: applied ("), line)
                    self.assertIn("Codex stack-worker profile mcp_servers.ai-memory.default_tools_approval_mode",
                                  line.split("added: ")[1])
                else:
                    self.assertTrue(line.startswith("authorization settings: left to the clients' own defaults"))

    def test_a_setting_that_is_not_an_authorization_one_is_refused_in_that_class_and_not_wired_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            edit_json(root / cfg.MAP_REL, lambda d: d["entries"].insert(0, {
                "match": ["claude/settings/setting/model"], "wiring": "authorization:a control"}))
            errors = cfg.analyse(root)[3]
        self.assertIn("claude/settings/setting/model: classed authorization, which this tool does not know as a setting "
                      "that grants a permission or suppresses a confirmation (is_authorization_piece)", errors)
        # Dropping one of the four altogether is allowed (it is then never written, with or without the option).
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))

            def drop(data):
                entry = next(e for e in data["entries"] if self.STANDALONE[2] in e["match"])
                entry["match"].remove(self.STANDALONE[2])
                data["entries"].insert(0, {"match": [self.STANDALONE[2]], "wiring": "not_wired:a decision to drop it"})
            edit_json(root / cfg.MAP_REL, drop)
            self.assertEqual(cfg.analyse(root)[3], [])
            results, *_ = cfg.analyse(root, authorization=True)
        self.assertFalse(next(v for v in results if v.piece.key == self.STANDALONE[2]).wired)
        # An allow rule would grant too: the tool classes it as authorization whatever the map says.
        self.assertTrue(cfg.is_authorization_piece("claude/settings/permission/allow/Bash(git status)"))
        self.assertFalse(cfg.is_authorization_piece("claude/settings/permission/deny/Bash(git push -f *)"))
        self.assertFalse(cfg.is_authorization_piece("claude/settings/setting/model"))

    def test_check_lists_the_authorization_pieces_apart_in_its_text_json_and_markdown(self):
        code, out, _ = run_main("--check")
        self.assertEqual(code, 0)
        self.assertIn(f"authorization: {len(self.ALL)}\n", out)
        block = out.split("authorization settings (", 1)[1].split("\nwarning", 1)[0]
        self.assertIn('claude/settings/setting/permissions.defaultMode = "bypassPermissions"', block)
        self.assertIn('codex/config/sandbox_mode = "danger-full-access"', block)
        listed = [line for line in block.splitlines() if line.startswith("  claude/") or line.startswith("  codex/")]
        self.assertEqual(len(listed), len(self.ALL))
        # A tool approval mode or an allow rule says which slot it also waits for; the four settings and the trust grant
        # say nothing of the kind.
        for key in self.APPROVAL:
            slot, owner = self.SLOT_OF[key]
            self.assertIn(f'  {key} = "approve"  (and only while slot {slot} installs {owner})', block)
        for key in self.ALLOW:
            slot, owner = self.SLOT_OF[key]
            self.assertIn(f'  {key} = "{key.rsplit("/", 1)[1]}"  (and only while slot {slot} installs {owner})', block)
        self.assertEqual([line for line in listed if "only while slot" in line
                          and not any(k in line for k in self.APPROVAL + self.ALLOW)], [])
        not_wired = [line for line in out.splitlines() if line.startswith("not wired")]
        self.assertFalse([line for line in not_wired if any(key in line for key in self.ALL)])
        rows = {row["piece"]: row for row in json.loads(run_main("--check", "--json")[1])}
        for key in self.ALL:
            self.assertEqual((rows[key]["wiring"], rows[key]["wired"]), ("authorization", False))
        results, _, plan, _, _ = cfg.analyse(ROOT)
        tables = cfg.markdown_tables(ROOT, results, plan).split("\n\n")
        head = tables[1].splitlines()[0]
        for column in ("Authorization setting", "Written by default", "Also needs"):
            self.assertIn(column, head)
        self.assertTrue(all(row.count("| no |") == 1 for row in tables[1].splitlines()[2:]))
        for key in self.ALL:
            rows_of_key = [row for row in tables[1].splitlines() if key in row]
            self.assertEqual(len(rows_of_key), 1, key)
            slot_cell = rows_of_key[0].rstrip("|").rsplit("|", 1)[1].strip()
            self.assertEqual(slot_cell, "-" if key in self.STANDALONE + self.TRUST else
                             "slot `%s` installing `%s`" % self.SLOT_OF[key], key)

    def test_the_help_text_names_the_option_what_it_writes_and_who_it_is_for(self):
        helped = " ".join(cfg.build_parser().format_help().split())
        self.assertIn("--with-authorization-settings", helped)
        for phrase in ("grant a permission or suppress a confirmation", "permissions.defaultMode",
                       "skipDangerousModePermissionPrompt", "approval_policy", "sandbox_mode",
                       "the trust_level of the host's main checkout in Codex",
                       "neither rendered nor written and a value a file already has is never touched",
                       "a differing one is kept and printed beside the render's",
                       "only on a host whose owner asked for the repository's permission practice"):
            self.assertIn(phrase, helped)


class AcknowledgementGateTests(ApplyCase):
    """--apply wires no interim install (amendment 3 of the manifest's decision rule) while the layer consensus's wave-2
    batch owes an acknowledgement: a real run refuses and writes nothing, and a dry run says that a real run would refuse
    (wave-2 code-search ruling, change 1; install.sh's interim_acknowledged is the plan's side of the same gate)."""

    def test_the_list_is_read_from_the_committed_batch(self):
        owed = json.loads((ROOT / cfg.CONSENSUS_REL).read_text(encoding="utf-8"))["wave2"]["acknowledgements_owed"]
        self.assertEqual(REAL_OWED_ACKNOWLEDGEMENTS(ROOT), owed)

    def test_a_list_that_cannot_be_read_is_an_error_and_an_empty_one_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / cfg.CONSENSUS_REL
            path.parent.mkdir(parents=True)
            for broken in ({}, {"wave2": {}}, {"wave2": {"acknowledgements_owed": "gpt"}},
                           {"wave2": {"acknowledgements_owed": [""]}}):
                with self.subTest(consensus=broken):
                    path.write_text(json.dumps(broken), encoding="utf-8")
                    with self.assertRaises(cfg.ConfigError):
                        REAL_OWED_ACKNOWLEDGEMENTS(Path(tmp))
            path.write_text(json.dumps({"wave2": {"acknowledgements_owed": []}}), encoding="utf-8")
            self.assertEqual(REAL_OWED_ACKNOWLEDGEMENTS(Path(tmp)), [])

    def test_a_real_apply_refuses_while_one_is_owed_and_a_dry_run_says_so(self):
        self.installed_state()
        before = tree(self.home)
        with mock.patch.object(cfg, "owed_acknowledgements", return_value=["claude", "gpt"]):
            code, out, err = self.apply()
            self.assertEqual(code, 1, out + err)
            self.assertIn("apply refused: the render wires the interim installs of code-search, "
                          "memory-owner (amendment 3 of the manifest's decision rule), and the acknowledgement of the "
                          "wave-2 batch is still owed by claude, gpt", err)
            self.assertNotIn("summary:", out)                  # no step ran
            self.assertEqual(tree(self.home), before)
            self.assertFalse(self.marker.exists())             # and no client was called
            code, out, err = self.apply(dry=True)
            self.assertEqual(code, 0, out + err)
            self.assertIn("note: a real run refuses now: the render wires the interim installs of code-search, "
                          "memory-owner", out)
        self.assertEqual(tree(self.home), before)


class RenderedScanTests(unittest.TestCase):
    """--check renders the example host, without and with the authorization settings, and scans every file."""

    def test_a_skill_override_identifier_does_not_require_its_namesake_service(self):
        rendered = {"settings.json": json.dumps({"skillOverrides": {"loki": "on"}})}
        with mock.patch.object(cfg, "render", return_value=rendered):
            self.assertEqual(cfg.rendered_name_errors(ROOT), [])

    def test_an_unwired_service_reference_is_found_outside_skill_identifiers(self):
        for settings in (
            {"skillOverrides": {"loki": "on"}, "env": {"LOG_ENDPOINT": "http://loki:3100"}},
            {"skillOverrides": {"loki": "on"}, "mcpServers": {"loki": {"command": "loki"}}},
            {"skillOverrides": {"loki": "use loki"}},
        ):
            with self.subTest(settings=settings):
                with mock.patch.object(cfg, "render", return_value={"settings.json": json.dumps(settings)}):
                    errors = cfg.rendered_name_errors(ROOT)
                self.assertEqual(len(errors), 2)
                self.assertTrue(all("settings.json names Loki, which is not wired" in error for error in errors), errors)

    def test_the_repository_render_names_no_tool_that_is_not_wired_either_way(self):
        self.assertEqual(cfg.rendered_name_errors(ROOT), [])
        code, out, err = run_main("--check")
        self.assertEqual((code, err), (0, ""), out[-300:])

    def test_a_name_in_a_rendered_file_fails_the_check_and_the_message_says_which_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            edit_json(root / cfg.TEMPLATES["claude/settings"], lambda d: d["env"].update(SCAN_PROBE="use phoenix here"))
            edit_json(root / cfg.MAP_REL, lambda d: d["entries"].insert(0, {
                "match": ["claude/settings/env/SCAN_PROBE"], "wiring": "practice"}))
            code, _, err = run_main("--check", "--root", str(root))
        self.assertEqual(code, 1)
        self.assertIn("the render for the example host without --with-authorization-settings: settings.json names Phoenix, "
                      "which is not wired", err)
        self.assertIn("the render for the example host with --with-authorization-settings: settings.json names Phoenix", err)

    def test_a_name_that_only_an_authorization_setting_carries_is_found_in_the_render_with_the_option_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            edit_json(root / cfg.TEMPLATES["claude/settings"], lambda d: d["permissions"].update(defaultMode="phoenix-default"))
            errors = cfg.rendered_name_errors(root)
            code, _, err = run_main("--check", "--root", str(root))
        self.assertEqual(code, 1)
        self.assertEqual(errors, ["the render for the example host with --with-authorization-settings: settings.json "
                                  "names Phoenix, which is not wired"])
        self.assertIn("with --with-authorization-settings: settings.json names Phoenix", err)

    def test_a_name_in_an_instruction_block_or_the_codex_config_is_found_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            path = root / cfg.TEMPLATES["codex/config"]
            path.write_text(path.read_text().replace('web_search = "live"', 'web_search = "live"\nprobe_note = "phoenix"'),
                            encoding="utf-8")
            edit_json(root / cfg.MAP_REL, lambda d: d["entries"].insert(0, {
                "match": ["codex/config/probe_note"], "wiring": "practice"}))
            errors = cfg.rendered_name_errors(root)
        self.assertTrue(any("codex.config.toml names Phoenix" in error for error in errors), errors)

    def test_a_render_that_fails_is_reported_and_not_taken_for_a_clean_scan(self):
        with mock.patch.object(cfg, "render", side_effect=cfg.ConfigError("boom")):
            errors = cfg.rendered_name_errors(ROOT)
        self.assertEqual(len(errors), 2)
        self.assertTrue(all("failed, so it was not scanned: boom" in error for error in errors), errors)

    def test_the_scan_takes_whole_words_in_any_case(self):
        self.assertEqual(cfg.name_hits("Use RTK here", ["rtk", "headroom"]), ["rtk"])
        self.assertEqual(cfg.name_hits("artkb and rtks", ["rtk"]), [])
        self.assertEqual(cfg.name_hits("rtk-default", ["rtk"]), ["rtk"])
        # Against the rule written out a second time in this file, on texts that put a name beside letters, digits, marks and
        # other names: the two can differ, so this can fail.
        names = ["rtk", "headroom", "ai-memory", "SocratiCode", "context-mode", "Promptfoo"]
        for text in ("Use RTK here", "artkb and rtks", "rtk-default", "(ai-memory), socraticode.", "xheadroom headroom_x",
                     "CONTEXT-MODE:context-mode", "rtk2 2rtk rtk", "promptfoo/Promptfoo", "ai-memoryx", "no name here"):
            self.assertEqual(cfg.name_hits(text, names), independent_name_hits(text, names), text)


class McpEndpointRepairTests(unittest.TestCase):
    """Local integration regressions for co-op D02, not upstream acceptance.

    Native formats: https://code.claude.com/docs/en/mcp and
    https://developers.openai.com/codex/mcp. SocratiCode's endpoint variables:
    giancarloerra/SocratiCode@f6191f076a42405f0d5508139f3a8b505cfef93a:README.md,
    Configuration (QDRANT_URL and LMSTUDIO_URL, including the /v1 suffix).
    """

    def test_alternate_host_render_uses_the_same_endpoints_and_keeps_other_env(self):
        host = render_config.load_host_values(EXAMPLE_HOST)
        host.update(QDRANT_URL="127.0.0.1:21633", EMBED_URL="127.0.0.1:28231")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
                render_config, "load_host_values", return_value=host):
            code, _, err = run_main("--render", "--host", EXAMPLE_HOST, "--out", tmp)
            self.assertEqual((code, err), (0, ""))
            claude = json.loads((Path(tmp) / "mcp-servers.json").read_text())["mcpServers"]["socraticode"]
            codex = tomllib.loads((Path(tmp) / "codex.config.toml").read_text())["mcp_servers"]["socraticode"]
        self.assertEqual(claude["env"]["QDRANT_URL"], "http://127.0.0.1:21633")
        self.assertEqual(claude["env"]["LMSTUDIO_URL"], "http://127.0.0.1:28231/v1")
        for key in ("QDRANT_URL", "LMSTUDIO_URL"):
            self.assertEqual(claude["env"][key], codex["env"][key], key)
        # A partial host override must retain the native provider/model/dimension settings.
        template = json.loads((ROOT / cfg.TEMPLATES["claude/mcp"]).read_text())["mcpServers"]["socraticode"]
        self.assertEqual({k: v for k, v in claude["env"].items() if k not in ("QDRANT_URL", "LMSTUDIO_URL")},
                         {k: v for k, v in template["env"].items() if k not in ("QDRANT_URL", "LMSTUDIO_URL")})

    def test_check_accepts_matching_host_endpoints_with_client_specific_cache_paths(self):
        code, out, err = run_main("--check")
        self.assertEqual((code, err), (0, ""), out[-300:])
        self.assertIn("check passed", out)

    def test_check_rejects_the_missing_env_override_even_when_the_example_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))

            def remove_host_env(data):
                entry = next(e for e in data["entries"] if e["match"] == ["claude/mcp/server/socraticode"])
                entry["override"].pop("env", None)

            edit_json(root / cfg.MAP_REL, remove_host_env)
            code, _, err = run_main("--check", "--root", str(root))
        self.assertEqual(code, 1)
        for field in ("env.QDRANT_URL", "env.LMSTUDIO_URL"):
            self.assertIn(f"MCP server socraticode {field} differs between Claude and Codex renders", err)

    def test_check_rejects_a_hardcoded_http_url_for_another_shared_server(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))

            def freeze_host_url(data):
                entry = next(e for e in data["entries"] if e["match"] == ["claude/mcp/server/ai-memory"])
                host = render_config.load_host_values(EXAMPLE_HOST)
                entry["override"]["url"] = f"http://{host['AI_MEMORY_URL']}/mcp"

            edit_json(root / cfg.MAP_REL, freeze_host_url)
            code, _, err = run_main("--check", "--root", str(root))
        self.assertEqual(code, 1)
        self.assertIn("MCP server ai-memory url differs between Claude and Codex renders", err)

    def test_check_rejects_a_host_endpoint_missing_from_one_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_catalog(Path(tmp))
            path = root / cfg.TEMPLATES["codex/config"]
            path.write_text(path.read_text().replace('QDRANT_URL = "http://${QDRANT_URL}"\n', ""))
            code, _, err = run_main("--check", "--root", str(root))
        self.assertEqual(code, 1)
        self.assertIn("MCP server socraticode env.QDRANT_URL differs between Claude and Codex renders", err)


ONLY_CODEX_CONFIG = tuple(arg for step in cfg.STEPS if step != "codex-config" for arg in ("--skip", step))


def expected_merge(existing: dict, rendered: dict) -> dict:
    """What merging should give, written again here: the file's data, plus every key and table the render has that it lacks,
    a table both have merged key by key, and no existing value changed."""
    merged = {key: (expected_merge(value, {}) if isinstance(value, dict) else value) for key, value in existing.items()}
    for key, value in rendered.items():
        if key not in merged:
            merged[key] = value
        elif isinstance(value, dict) and isinstance(merged[key], dict):
            merged[key] = expected_merge(merged[key], value)
    return merged


def keeps_lines(original: str, merged: str) -> bool:
    """Every line of the original is still in the merged text, in the same order (the merge only adds)."""
    position = 0
    lines = merged.split("\n")
    for line in original.split("\n"):
        if not line:
            continue
        try:
            position = lines.index(line, position) + 1
        except ValueError:
            return False
    return True


class CodexMergeTests(unittest.TestCase):
    """`--apply` merges the render into a Codex config.toml that exists, as the install plan leaves one."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.codex_home = self.home / ".codex"
        self.config = self.codex_home / "config.toml"
        self.claude = write_exe(self.base / "bin" / "claude", STUB_CLAUDE)
        self.codex = write_exe(self.base / "bin" / "codex", STUB_CODEX)
        self.marker = self.base / "client-calls.txt"
        patcher = mock.patch.dict(os.environ, {"STUB_MARKER": str(self.marker)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def put(self, text: str, mode: int = 0o600) -> None:
        self.codex_home.mkdir(mode=0o700, exist_ok=True)
        self.config.write_text(text, encoding="utf-8")
        self.config.chmod(mode)

    def apply(self, *extra: str, dry: bool = False, name: str = NO_PROCESS, codex=None):
        argv = ["--apply", "--host", EXAMPLE_HOST, "--home", str(self.home), "--claude-bin", str(self.claude),
                "--codex-bin", str(codex or self.codex), "--codex-process-name", name, *ONLY_CODEX_CONFIG, *extra]
        return run_main(*argv, *(["--dry-run"] if dry else []))

    def rendered(self) -> dict:
        results, manifest, plan, _, _ = cfg.analyse(ROOT)
        values = cfg.host_values(EXAMPLE_HOST, plan, self.home, cfg.wired_path_dirs(results))
        return tomllib.loads(cfg.render(ROOT, results, plan, values, manifest)["codex.config.toml"])

    def backups(self) -> list:
        return sorted(p for p in self.codex_home.iterdir() if ".bak." in p.name)

    def calls(self) -> list:
        return self.marker.read_text().splitlines() if self.marker.exists() else []

    def summary(self, out: str) -> str:
        return out.split("summary: ")[1]

    def assert_conflict_display(self, out: str, key: str, have_text: str, render_value: str) -> str:
        """The one conflict line of `key` names the key, shows the file's value (`have_text`) and shows the render's value
        as the documented display makes it: the whole TOML text when that fits in DOCUMENTED_WIDTH characters, else its first
        DOCUMENTED_WIDTH - 3 characters and `...`. The expectation is worked out here from the render's value, so it holds
        whichever side of the width a host's temporary directory puts a path-valued key on. Returns what was shown."""
        prefix = f"conflict kept: {key}: the file has {have_text}; the render has "
        found = [line[line.index(prefix) + len(prefix):] for line in out.splitlines() if prefix in line]
        self.assertEqual(len(found), 1, (prefix, found))
        shown = found[0]
        full = json.dumps(render_value, ensure_ascii=False)     # a TOML basic string: a path has nothing to escape
        self.assertEqual(shown, full if len(full) <= DOCUMENTED_WIDTH else full[:DOCUMENTED_WIDTH - 3] + "...")
        self.assertLessEqual(len(shown), DOCUMENTED_WIDTH)
        return shown

    def test_the_destinations_two_files_are_rebuilt_from_the_plans_own_commands_at_the_observed_sizes(self):
        self.assertIn(f"--ref {PLAN_COMMIT}", (PLAN / "install.sh").read_text())
        self.assertIn(f"claude plugin marketplace add {PLAN_MARKETPLACE_URL}", (PLAN / "install.sh").read_text())
        self.assertEqual(len(DESTINATION_CODEX.encode()), 192)
        self.assertEqual(len((json.dumps(DESTINATION_CLAUDE, indent=2) + "\n").encode()), 194)
        self.assertEqual(tomllib.loads(DESTINATION_CODEX)["marketplaces"]["trailofbits"],
                         {"source_type": "git", "source": "https://github.com/trailofbits/skills.git", "ref": PLAN_COMMIT})

    def test_the_destinations_config_gets_what_it_lacks_and_keeps_what_it_has(self):
        self.assertEqual(len(DESTINATION_CODEX.encode()), 192)
        self.put(DESTINATION_CODEX)
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-900:])
        merged_text = self.config.read_text()
        merged, rendered = tomllib.loads(merged_text), self.rendered()
        self.assertEqual(merged, expected_merge(tomllib.loads(DESTINATION_CODEX), rendered))
        self.assertIs(merged["features"]["daemon_auto_start"], False)
        # What the file had is as it was: every old line in order, the marketplace table equal, [tui] only extended.
        self.assertTrue(keeps_lines(DESTINATION_CODEX, merged_text))
        # The trailofbits table as it was, and context-mode's beside it (the context-supply slot's interim install).
        self.assertEqual(merged["marketplaces"], {**tomllib.loads(DESTINATION_CODEX)["marketplaces"],
                                                  "context-mode": rendered["marketplaces"]["context-mode"]})
        self.assertTrue(merged["tui"]["screen_reader_detection_done"])
        self.assertEqual(sorted(merged["tui"]), sorted({"screen_reader_detection_done", *rendered["tui"]}))
        self.assertIn("[tui]\nscreen_reader_detection_done = true\n", merged_text)
        # A backup of the original, the file's mode kept, Codex's own writer used for the one key it has one for.
        self.assertEqual([p.read_bytes() for p in self.backups()], [DESTINATION_CODEX.encode()])
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o600)
        self.assertEqual(self.calls(), ["codex features disable daemon_auto_start"])
        self.assertIn("codex-config applied", self.summary(out))
        self.assertIn("keys added to tables the file has: tui.notifications", out)
        # The second run changes nothing and makes no second backup.
        once = tree(self.home)
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-600:])
        self.assertEqual(tree(self.home), once)
        self.assertEqual(len(self.backups()), 1)
        self.assertIn("codex-config current", self.summary(out))
        self.assertEqual(self.calls(), ["codex features disable daemon_auto_start"])

    def test_a_conflict_keeps_the_files_value_shows_both_and_the_step_says_so(self):
        text = 'model = "mine"\n\n[tui]\nnotifications = ["x"]\n\n[shell_environment_policy.set]\nPATH = "/my/path"\n'
        self.put(text)
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-900:])
        merged, rendered = tomllib.loads(self.config.read_text()), self.rendered()
        self.assertEqual((merged["model"], merged["tui"]["notifications"], merged["shell_environment_policy"]["set"]["PATH"]),
                         ("mine", ["x"], "/my/path"))
        self.assertEqual(merged["shell_environment_policy"]["set"]["MCP_AUTO_OPEN_ENABLED"], "false")   # a missing key came in
        self.assertIn("mcp_servers", merged)
        lines = [line for line in out.splitlines() if "conflict kept:" in line]
        self.assertEqual(len(lines), 3, lines)
        self.assertIn('conflict kept: model: the file has "mine"; the render has "gpt-6.1-sol"', out)
        self.assertIn('conflict kept: tui.notifications: the file has ["x"]; the render has '
                      '["approval-requested", "plan-mode-prompt", "async-question"]', out)
        # PATH holds the home three times, so the length of its render follows the host's temporary directory (a macOS
        # runner's is the longer): what is asserted is the key, the file's value on the screen and in the file (above), and
        # the render's value as the documented display makes it, whichever side of the width the host puts it on.
        self.assert_conflict_display(out, "shell_environment_policy.set.PATH", '"/my/path"',
                                     rendered["shell_environment_policy"]["set"]["PATH"])
        self.assertEqual(out.count("codex-config merged with conflicts kept"), 1)
        self.assertEqual(len(self.backups()), 1)
        # The second run writes nothing and makes no backup; the conflicts stay in view.
        once = tree(self.home)
        code, again, _ = self.apply()
        self.assertEqual(code, 0, again[-600:])
        self.assertEqual(tree(self.home), once)
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(len([line for line in again.splitlines() if "conflict kept:" in line]), 3)
        self.assertIn("codex-config merged with conflicts kept", self.summary(again))

    def test_the_display_of_a_value_is_cut_at_the_documented_width_and_no_sooner(self):
        self.assertEqual(cfg.SHOWN_WIDTH, DOCUMENTED_WIDTH)
        for length, cut in ((DOCUMENTED_WIDTH - 2, False), (DOCUMENTED_WIDTH - 1, True), (DOCUMENTED_WIDTH * 2, True)):
            value = "x" * length
            full = json.dumps(value)                               # two quotes more than the characters
            with self.subTest(text_length=len(full)):
                self.assertEqual(cfg.shown(("a", "b"), value),
                                 full[:DOCUMENTED_WIDTH - 3] + "..." if cut else full)
                self.assertLessEqual(len(cfg.shown(("a", "b"), value)), DOCUMENTED_WIDTH)
        self.assertEqual(cfg.shown(("a", "b"), ["x", "y"]), '["x", "y"]')          # a short value is shown whole

    def test_a_value_longer_than_the_documented_width_is_cut_in_the_display_and_never_in_the_file(self):
        # A home with a long name makes the render's PATH longer than the width on any host, so the cut is exercised here
        # whatever the temporary directory is; the conflict test above meets whichever side of the width the host's puts it.
        home = self.base / ("long-home-" + "x" * 90) / "home"
        codex_home = home / ".codex"
        codex_home.mkdir(parents=True, mode=0o700)
        config = codex_home / "config.toml"
        results, manifest, plan, _, _ = cfg.analyse(ROOT)
        values = cfg.host_values(EXAMPLE_HOST, plan, home, cfg.wired_path_dirs(results))
        render_path = tomllib.loads(cfg.render(ROOT, results, plan, values, manifest)["codex.config.toml"])[
            "shell_environment_policy"]["set"]["PATH"]
        self.assertGreater(len(json.dumps(render_path)), DOCUMENTED_WIDTH)
        for case, text in (("the file has its own PATH", '[shell_environment_policy.set]\nPATH = "/my/path"\n'),
                           ("the file lacks PATH", "# nothing of ours\n")):
            with self.subTest(case=case):
                config.write_text(text, encoding="utf-8")
                config.chmod(0o600)
                code, out, _ = run_main("--apply", "--host", EXAMPLE_HOST, "--home", str(home), "--claude-bin",
                                        str(self.claude), "--codex-bin", str(self.codex), "--codex-process-name", NO_PROCESS,
                                        *ONLY_CODEX_CONFIG)
                self.assertEqual(code, 0, out[-900:])
                in_file = tomllib.loads(config.read_text())["shell_environment_policy"]["set"]["PATH"]
                if "its own" in case:
                    self.assertEqual(in_file, "/my/path")                     # the file's value stays, whole
                    shown = self.assert_conflict_display(out, "shell_environment_policy.set.PATH", '"/my/path"', render_path)
                    self.assertEqual((len(shown), shown[-3:]), (DOCUMENTED_WIDTH, "..."))   # cut, on every host
                else:
                    self.assertEqual(in_file, render_path)                    # a value that is added is written whole
                    self.assertGreater(len(in_file), DOCUMENTED_WIDTH)
                    self.assertNotIn("conflict kept: shell_environment_policy.set.PATH", out)

    def test_a_value_whose_key_looks_like_a_secret_is_never_printed(self):
        plan = cfg.plan_merge({"mcp_servers": {"x": {"env": {"API_TOKEN": "abc123-secret"}}}},
                              {"mcp_servers": {"x": {"env": {"API_TOKEN": "zzz-other"}}}})
        report = "\n".join(cfg.merge_report(plan))
        self.assertIn("conflict kept: mcp_servers.x.env.API_TOKEN", report)
        self.assertIn("hidden", report)
        self.assertNotIn("abc123", report)
        self.assertNotIn("zzz-other", report)
        shown = cfg.shown(("a", "b"), "x" * 500)
        self.assertEqual(len(shown), cfg.SHOWN_WIDTH)
        self.assertTrue(shown.endswith("..."))
        # A table or array that holds such a key is hidden whole, wherever the conflict sits.
        for value in ({"API_TOKEN": "abc123"}, [{"a": {"client_secret": "abc123"}}], {"ok": 1, "Bearer": "abc123"}):
            self.assertIn("hidden", cfg.shown(("env",), value))
        self.assertEqual(cfg.shown(("env",), {"PATH": "/bin"}), '{ PATH = "/bin" }')
        plan = cfg.plan_merge({"env": {"API_TOKEN": "abc123"}}, {"env": "plain"})   # a table where the render has a string
        self.assertNotIn("abc123", "\n".join(cfg.merge_report(plan)))

    def test_a_trailing_comment_without_a_final_newline_and_a_comment_only_file_are_kept(self):
        self.put(DESTINATION_CODEX + "# end of file")
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-600:])
        text = self.config.read_text()
        self.assertTrue(text.endswith("\n"))
        self.assertIn("# end of file", text.splitlines())
        self.assertTrue(keeps_lines(DESTINATION_CODEX + "# end of file", text))
        self.assertEqual(tomllib.loads(text), expected_merge(tomllib.loads(DESTINATION_CODEX), self.rendered()))
        self.config.unlink()
        for backup in self.backups():
            backup.unlink()
        self.put("# only a comment")
        self.assertEqual(self.apply()[0], 0)
        text = self.config.read_text()
        self.assertTrue(text.startswith("# only a comment\n"))
        self.assertEqual(tomllib.loads(text), self.rendered())

    def test_lines_that_look_like_tables_inside_arrays_and_strings_are_not_tables(self):
        text = ('matrix = [\n  [1, 2],\n  [3, 4],\n]\nnote = """\n[features]\nhooks = false\n"""\nliteral = \'\'\'\n[tui]\n\'\'\'\n\n'
                '[tui]\nscreen_reader_detection_done = true\n')
        self.put(text)
        # No codex binary here: the stub's own edit is line-based, and the file holds a string with a `[features]` line.
        code, out, _ = self.apply(codex=self.base / "no-such-codex")
        self.assertEqual(code, 0, out[-600:])
        merged = tomllib.loads(self.config.read_text())
        self.assertEqual(merged["matrix"], [[1, 2], [3, 4]])
        self.assertEqual(merged["note"], "[features]\nhooks = false\n")   # the string is as it was
        self.assertIs(merged["features"]["hooks"], True)                   # the real table came in
        self.assertEqual(merged, expected_merge(tomllib.loads(text), self.rendered()))
        self.assertTrue(keeps_lines(text, self.config.read_text()))

    def test_every_partial_render_in_the_file_is_completed_to_the_whole_and_a_second_pass_adds_nothing(self):
        rendered = self.rendered()
        leaves = list(cfg.toml_leaves(rendered))
        rng = random.Random(20261002)
        for trial in range(80):
            part: dict = {}
            for path, value in (leaf for leaf in leaves if rng.random() < 0.5):
                node = part
                for key in path[:-1]:
                    node = node.setdefault(key, {})
                node[path[-1]] = value
            text = cfg.emit_toml(part, "# a partial config") if part and trial % 4 else ""
            if trial % 3 == 0 and text:
                text = text.rstrip("\n")   # and without the final newline
            with self.subTest(trial=trial):
                plan = cfg.plan_merge(tomllib.loads(text), rendered)
                merged = cfg.merge_toml_text(text, plan)
                self.assertEqual(tomllib.loads(merged), rendered)
                self.assertTrue(cfg.strict_equal(tomllib.loads(merged), plan.expected))
                self.assertTrue(keeps_lines(text, merged))
                again = cfg.plan_merge(tomllib.loads(merged), rendered)
                self.assertEqual((again.keys, again.tables, again.conflicts), ([], [], []))
                self.assertEqual(cfg.merge_toml_text(merged, again), merged)

    def test_the_empty_home_still_gets_the_rendered_file_created(self):
        self.assertFalse(self.codex_home.exists())
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-600:])
        self.assertEqual(stat.S_IMODE(self.codex_home.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o600)
        # codex_home.py --keep-hook-trust: the whole render, the wired [hooks.state] approvals included, so a second run
        # (a merge) finds nothing to add.
        self.assertEqual(tomllib.loads(self.config.read_text()), self.rendered())
        self.assertTrue(self.config.read_text().startswith("# Written by tools/adoption/codex_home.py --keep-hook-trust"))
        self.assertIn("hooks", tomllib.loads(self.config.read_text()))
        self.assertEqual(self.backups(), [])
        self.assertIn("written from the rendered user config", out)
        self.assertEqual(self.calls(), [])
        self.assertIn("codex-config applied", self.summary(out))

    def test_a_running_codex_stops_the_write_and_the_message_says_how_to_go_on(self):
        self.put(DESTINATION_CODEX)
        sleeper = subprocess.Popen(["sleep", "120"])
        self.addCleanup(lambda: (sleeper.kill(), sleeper.wait()))
        for _ in range(100):   # pgrep sees the name once the new program is set up
            if str(sleeper.pid) in cfg.lane.codex_processes("sleep"):
                break
            time.sleep(0.05)
        code, out, _ = self.apply(name="sleep")
        self.assertEqual(code, 1)
        self.assertIn("codex-config failed", self.summary(out))
        self.assertIn("a running Codex writes the same config.toml: close the Codex sessions, then run `--apply` again", out)
        self.assertEqual(self.config.read_text(), DESTINATION_CODEX)
        self.assertEqual(self.backups(), [])
        code, out, _ = self.apply(name="sleep", dry=True)
        self.assertEqual(code, 0, out[-600:])
        self.assertIn("close the Codex sessions before the real run", out)
        self.assertEqual(self.config.read_text(), DESTINATION_CODEX)
        # Control: with no such process the same file is merged.
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-600:])
        self.assertIn("codex-config applied", self.summary(out))
        # A file that needs nothing is not held up by a running Codex.
        code, out, _ = self.apply(name="sleep")
        self.assertEqual(code, 0, out[-600:])
        self.assertIn("codex-config current", self.summary(out))

    def stand_in_pgrep(self, body: str):
        """A `pgrep` that comes first on PATH: the shell lines `body` is all it does. Returns the patch of PATH to enter."""
        directory = self.base / "stand-in-pgrep"
        write_exe(directory / "pgrep", "#!/bin/sh\n" + body)
        return mock.patch.dict(os.environ, {"PATH": f"{directory}{os.pathsep}{os.environ['PATH']}"})

    def prepare_marker_only_default(self):
        self.put(DESTINATION_CODEX)
        self.assertEqual(self.apply()[0], 0)
        migration = self.codex_home / ".native-agent-stack-migrations/service-tier-fast-to-default-20261005.json"
        migration.unlink()
        self.assertEqual(tomllib.loads(self.config.read_text())["service_tier"], "default")
        return migration, self.config.read_bytes(), self.backups(), self.calls()

    def test_marker_only_default_completes_while_a_process_runs_without_guard_or_backup(self):
        migration, before, backups, calls = self.prepare_marker_only_default()
        sleeper = subprocess.Popen(["sleep", "120"])
        self.addCleanup(lambda: (sleeper.kill(), sleeper.wait()))
        for _ in range(100):
            if str(sleeper.pid) in cfg.lane.codex_processes("sleep"):
                break
            time.sleep(0.05)
        self.assertIsNone(sleeper.poll())
        with mock.patch.object(cfg, "running_codex_pids", wraps=cfg.running_codex_pids) as probe:
            code, out, err = self.apply(name="sleep")
        self.assertEqual(code, 0, out[-600:] + err)
        probe.assert_not_called()
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(self.backups(), backups)
        self.assertEqual(self.calls(), calls)
        self.assertTrue(migration.is_file())
        self.assertIn("codex-config current", self.summary(out))
        self.assertIn("one-time migration recorded", out)

    def test_marker_only_default_completes_without_invoking_a_failing_pgrep(self):
        migration, before, backups, calls = self.prepare_marker_only_default()
        with self.stand_in_pgrep("exit 2\n"), mock.patch.object(cfg, "running_codex_pids", wraps=cfg.running_codex_pids) as probe:
            code, out, err = self.apply()
        self.assertEqual(code, 0, out[-600:] + err)
        probe.assert_not_called()
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(self.backups(), backups)
        self.assertEqual(self.calls(), calls)
        self.assertTrue(migration.is_file())
        self.assertIn("codex-config current", self.summary(out))
        self.assertIn("one-time migration recorded", out)

    def test_marker_only_dry_run_needs_no_process_check_and_writes_nothing(self):
        migration, before, backups, calls = self.prepare_marker_only_default()
        with self.stand_in_pgrep("exit 2\n"), mock.patch.object(cfg, "running_codex_pids", wraps=cfg.running_codex_pids) as probe:
            code, out, err = self.apply(dry=True)
        self.assertEqual(code, 0, out[-600:] + err)
        probe.assert_not_called()
        self.assertFalse(migration.exists())
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(self.backups(), backups)
        self.assertEqual(self.calls(), calls)
        self.assertIn("would record one-time migration completion", out)

    def test_marker_only_completion_verifies_actual_readback_and_keeps_a_concurrent_tier(self):
        migration, _, backups, calls = self.prepare_marker_only_default()
        native_pending = cfg.Apply.pending_codex_migrations

        def concurrent_choice(apply, rendered):
            pending = native_pending(apply, rendered)
            data = tomllib.loads(self.config.read_text())
            data["service_tier"] = "flex"
            self.config.write_text(cfg.emit_toml(data, ""))
            return pending

        with mock.patch.object(cfg.Apply, "pending_codex_migrations", concurrent_choice), mock.patch.object(cfg, "running_codex_pids", wraps=cfg.running_codex_pids) as probe:
            code, out, err = self.apply()
        self.assertEqual(code, 1, out[-600:] + err)
        probe.assert_not_called()
        self.assertFalse(migration.exists())
        self.assertEqual(tomllib.loads(self.config.read_text())["service_tier"], "flex")
        self.assertEqual(self.backups(), backups)
        self.assertEqual(self.calls(), calls)

    def test_a_pgrep_that_fails_stops_the_merge_and_the_creation_and_the_message_names_the_status(self):
        calls = []
        real_tool = cfg.Apply.tool

        def recording(apply, step, argv):
            calls.append(argv[0])
            return real_tool(apply, step, argv)
        for body, said in (('echo "pgrep: stand-in failure 2" >&2\nexit 2\n', "exited with status 2: pgrep: stand-in failure 2"),
                           ('echo "pgrep: stand-in failure 3" >&2\nexit 3\n', "exited with status 3: pgrep: stand-in failure 3"),
                           ("kill -9 $$\n", "was ended by signal 9")):
            for state in ("a config.toml that needs a write", "no config.toml"):
                with self.subTest(pgrep=said, state=state):
                    self.codex_home.mkdir(mode=0o700, exist_ok=True)
                    for leftover in list(self.codex_home.iterdir()):
                        leftover.unlink()
                    if state.startswith("a config"):
                        self.put(DESTINATION_CODEX)
                    with self.stand_in_pgrep(body), mock.patch.object(cfg.Apply, "tool", recording):
                        code, out, _ = self.apply()
                    self.assertEqual(code, 1, out[-500:])
                    self.assertIn("codex-config failed", self.summary(out))
                    self.assertIn(f"`pgrep -x {NO_PROCESS}` {said}", out)
                    self.assertIn("so whether one runs is not known; nothing is written", out)
                    self.assertEqual(self.config.read_text() if self.config.exists() else None,
                                     DESTINATION_CODEX if state.startswith("a config") else None)
                    self.assertEqual(self.backups(), [])
                    self.assertFalse([c for c in calls if c.endswith("codex_home.py")], "codex_home.py ran after a failed check")

    def test_a_pgrep_that_finds_nothing_or_finds_one_is_not_a_failed_check(self):
        self.put(DESTINATION_CODEX)
        with self.stand_in_pgrep("exit 1\n"):                       # no process: the merge goes ahead
            code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-500:])
        self.assertIn("codex-config applied", self.summary(out))
        self.config.write_text(DESTINATION_CODEX, encoding="utf-8")
        with self.stand_in_pgrep("echo 4242\nexit 0\n"):           # one process: the refusal that was always there
            code, out, _ = self.apply()
        self.assertEqual(code, 1)
        self.assertIn(f"1 {NO_PROCESS} process(es) running (pids 4242)", out)
        self.assertEqual(self.config.read_text(), DESTINATION_CODEX)

    def test_a_pgrep_that_cannot_run_fails_the_step_and_says_so(self):
        self.put(DESTINATION_CODEX)
        empty = self.base / "empty-path"
        empty.mkdir()
        with mock.patch.dict(os.environ, {"PATH": str(empty)}):
            code, out, _ = self.apply()
        self.assertEqual(code, 1, out[-500:])
        self.assertIn(f"the check for a running Codex could not run `pgrep -x {NO_PROCESS}`", out)
        self.assertIn("install pgrep (procps) and run `--apply` again", out)
        self.assertEqual(self.config.read_text(), DESTINATION_CODEX)

    def test_a_file_that_needs_nothing_is_not_held_up_by_a_failed_check_and_a_dry_run_fails_with_it(self):
        self.put(DESTINATION_CODEX)
        self.assertEqual(self.apply()[0], 0)                           # merged: the file now holds the render
        with self.stand_in_pgrep("exit 2\n"):
            code, out, _ = self.apply()
            self.assertEqual(code, 0, out[-500:])
            self.assertIn("codex-config current", self.summary(out))   # nothing to write, so no check was needed
            self.config.write_text(DESTINATION_CODEX, encoding="utf-8")
            code, out, _ = self.apply(dry=True)                        # a dry run that passed would promise a run that cannot
        self.assertEqual(code, 1, out[-500:])
        self.assertIn("codex-config failed", self.summary(out))
        self.assertIn("exited with status 2", out)
        self.assertEqual(self.config.read_text(), DESTINATION_CODEX)

    def test_a_file_that_changes_under_the_run_is_left_as_the_other_writer_made_it(self):
        self.put(DESTINATION_CODEX)
        other = DESTINATION_CODEX + "# someone else was here\n"

        def changed(path, data, mode, expect, create_only=False):
            path.write_text(other, encoding="utf-8")
            raise cfg.lane.Failed(f"{path} changed since it was read; nothing written")
        with mock.patch.object(cfg.lane, "atomic_write", side_effect=changed), \
                mock.patch.object(cfg.Apply, "restore_config") as restore:
            code, out, _ = self.apply()
        self.assertEqual(code, 1)
        restore.assert_not_called()    # nothing of this run was written, so there is nothing to put back
        self.assertEqual(self.config.read_text(), other)
        self.assertIn("changed since it was read; nothing written", out)
        self.assertIn("codex-config failed", self.summary(out))

    def start_app_server(self) -> subprocess.Popen:
        """A process that looks like Codex's background app-server to a command-line reader: `app-server` is one of its
        arguments (`codex app-server --listen unix://` is the real shape). It is a Python process that sleeps, with no
        shell and no script in between, so that its command line is the same on every platform, and it is waited for until
        that command line reads right: it reads empty for a moment while a new program is being set up."""
        daemon = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)", "app-server", "--listen",
                                   "unix://"])
        self.addCleanup(lambda: (daemon.kill(), daemon.wait()))
        for _ in range(100):
            if cfg.app_server_pids([str(daemon.pid)]):
                break
            time.sleep(0.05)
        return daemon

    def test_the_message_names_the_app_server_daemon_and_how_to_stop_it(self):
        # Runs where /proc exists and where it does not (the command line is read through /proc or through `ps`). The
        # guard's list of running processes is stood in for, so that no platform's naming of a process decides this test;
        # a real `pgrep -x` is covered by the `sleep` tests above and, on Linux, by the script test below.
        self.put(DESTINATION_CODEX)
        daemon = self.start_app_server()
        self.assertEqual(cfg.app_server_pids([str(daemon.pid), "1"]), [str(daemon.pid)])
        with mock.patch.object(cfg, "running_codex_pids", return_value=[str(daemon.pid)]):
            code, out, _ = self.apply(name="fakecodex")
            self.assertEqual(code, 1)
            self.assertIn(f"close the Codex sessions, stop the app-server daemon (pid {daemon.pid}) with `codex app-server "
                          "daemon stop`, then run `--apply` again", out)
            self.assertEqual(self.config.read_text(), DESTINATION_CODEX)
            self.assertEqual(self.backups(), [])
            code, out, _ = self.apply(name="fakecodex", dry=True)
            self.assertEqual(code, 0, out[-600:])
            self.assertIn("stop the app-server daemon", out)
        self.assertEqual(cfg.app_server_pids(["not-a-pid", "999999999"]), [])

    @unittest.skipUnless(sys.platform.startswith("linux"),
                         "the guard finds a #! script by its file name through `pgrep -x`, which is how Linux names the "
                         "process of a script; what macOS makes of a script's name is not verified")
    def test_the_guard_finds_a_script_named_like_codex_through_pgrep_and_names_its_app_server_daemon(self):
        # A script named like the process the guard looks for, started with `app-server` as an argument: the shape of
        # Codex's background app-server (a `codex app-server --listen unix://` of the codex binary), found by the real
        # `pgrep -x` and read through the real /proc.
        self.put(DESTINATION_CODEX)
        fake = write_exe(self.base / "bin" / "fakecodex", "#!/bin/sh\nsleep 120\n")
        daemon = subprocess.Popen([str(fake), "app-server", "--listen", "unix://"], start_new_session=True)
        self.addCleanup(lambda: (os.killpg(daemon.pid, signal.SIGKILL), daemon.wait()))
        for _ in range(100):   # the command line reads empty for a moment while the new program is being set up
            if cfg.app_server_pids([str(daemon.pid), "1"]):
                break
            time.sleep(0.05)
        self.assertEqual(cfg.app_server_pids([str(daemon.pid), "1"]), [str(daemon.pid)])
        code, out, _ = self.apply(name="fakecodex")
        self.assertEqual(code, 1)
        self.assertIn(f"close the Codex sessions, stop the app-server daemon (pid {daemon.pid}) with `codex app-server "
                      "daemon stop`, then run `--apply` again", out)
        self.assertEqual(self.config.read_text(), DESTINATION_CODEX)
        self.assertEqual(self.backups(), [])

    def test_a_running_codex_refuses_the_creation_of_an_absent_file_and_nothing_is_written(self):
        # No config.toml yet: the creation is a write too, and codex_home.py's own fresh-file path has no process check.
        sleeper = subprocess.Popen(["sleep", "120"])
        self.addCleanup(lambda: (sleeper.kill(), sleeper.wait()))
        for _ in range(100):
            if str(sleeper.pid) in cfg.lane.codex_processes("sleep"):
                break
            time.sleep(0.05)
        calls = []
        real_tool = cfg.Apply.tool

        def recording(apply, step, argv):
            calls.append(argv[0])
            return real_tool(apply, step, argv)
        for home_state in ("no Codex home", "a Codex home without config.toml"):
            with self.subTest(state=home_state):
                if home_state != "no Codex home":
                    self.codex_home.mkdir(mode=0o700)
                with mock.patch.object(cfg.Apply, "tool", recording):
                    code, out, _ = self.apply(name="sleep")
                self.assertEqual(code, 1)
                self.assertIn("codex-config failed", self.summary(out))
                self.assertIn("a running Codex writes the same config.toml: close the Codex sessions, then run `--apply` "
                              "again", out)
                self.assertFalse(self.config.exists())                 # nothing was created
                self.assertEqual(list(self.codex_home.iterdir()) if self.codex_home.exists() else [], [])
                self.assertEqual(self.backups() if self.codex_home.exists() else [], [])
                self.assertFalse([c for c in calls if c.endswith("codex_home.py")], "codex_home.py ran before the check")
        # A dry run writes nothing either, says why the real run would stop, and still shows what it would write.
        code, out, _ = self.apply(name="sleep", dry=True)
        self.assertEqual(code, 0, out[-600:])
        self.assertIn("close the Codex sessions before the real run", out)
        self.assertIn("would write the rendered user config", out)
        self.assertFalse(self.config.exists())
        # Control: with no such process the same state gets its file, so the refusal is the guard and nothing else.
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-600:])
        self.assertTrue(self.config.is_file())
        self.assertIn("codex-config applied", self.summary(out))

    def test_the_refusal_for_an_absent_file_names_the_app_server_daemon_too(self):
        daemon = self.start_app_server()
        with mock.patch.object(cfg, "running_codex_pids", return_value=[str(daemon.pid)]):   # as in the test above
            code, out, _ = self.apply(name="fakecodex")
        self.assertEqual(code, 1)
        self.assertIn(f"stop the app-server daemon (pid {daemon.pid}) with `codex app-server daemon stop`, then run "
                      "`--apply` again", out)
        self.assertFalse(self.codex_home.exists())

    def test_a_dry_run_merges_nothing_and_runs_no_codex(self):
        self.put(DESTINATION_CODEX)
        code, out, _ = self.apply(dry=True)
        self.assertEqual(code, 0, out[-600:])
        self.assertEqual(self.config.read_text(), DESTINATION_CODEX)
        self.assertEqual(self.backups(), [])
        self.assertEqual(self.calls(), [])
        self.assertIn("DRY RUN: would back up", out)
        self.assertIn("codex-config planned", self.summary(out))

    def test_a_read_back_that_is_not_the_merge_puts_the_file_back_and_fails_the_step(self):
        self.put(DESTINATION_CODEX)
        with mock.patch.dict(os.environ, {"STUB_CODEX_MODE": "extra"}):
            code, out, _ = self.apply()
        self.assertEqual(code, 1)
        self.assertIn("codex-config failed", self.summary(out))
        self.assertIn("read-back: the file does not equal the merge (it differs at stub_extra)", out)
        self.assertIn("the file is back as it was", out)
        self.assertEqual(self.config.read_text(), DESTINATION_CODEX)
        self.assertEqual([p.read_bytes() for p in self.backups()], [DESTINATION_CODEX.encode()])

    def test_a_writer_that_fails_puts_the_file_back_and_fails_the_step(self):
        self.put(DESTINATION_CODEX)
        with mock.patch.dict(os.environ, {"STUB_CODEX_MODE": "fail"}):
            code, out, _ = self.apply()
        self.assertEqual(code, 1)
        self.assertIn("`codex features disable daemon_auto_start` exited 3: error: the stub refuses", out)
        self.assertEqual(self.config.read_text(), DESTINATION_CODEX)
        self.assertEqual(len(self.backups()), 1)

    def test_without_a_codex_binary_the_text_edit_adds_the_daemon_key_too(self):
        self.put(DESTINATION_CODEX)
        code, out, _ = self.apply(codex=self.base / "no-such-codex")
        self.assertEqual(code, 0, out[-600:])
        merged = tomllib.loads(self.config.read_text())
        self.assertIs(merged["features"]["daemon_auto_start"], False)
        self.assertEqual(merged, expected_merge(tomllib.loads(DESTINATION_CODEX), self.rendered()))
        self.assertEqual(self.calls(), [])
        # With the key already in the file, Codex's writer is not asked either.
        self.config.unlink()
        self.put('[features]\ndaemon_auto_start = false\n')
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual(self.calls(), [])

    def test_a_table_that_an_inline_table_or_dotted_keys_define_is_refused_not_corrupted(self):
        for name, text in {"an inline table": 'tui = { screen_reader_detection_done = true }\n',
                           "dotted keys": 'tui.screen_reader_detection_done = true\n'}.items():
            with self.subTest(case=name):
                self.put(text)
                code, out, _ = self.apply()
                self.assertEqual(code, 1)
                self.assertIn("inside [tui]: it is defined as an inline table or with dotted keys", out)
                self.assertEqual(self.config.read_text(), text)
                self.assertEqual(self.backups(), [])

    def test_a_config_that_is_not_toml_or_is_a_link_is_refused(self):
        self.put("[tui\nbroken = \n")
        code, out, _ = self.apply()
        self.assertEqual(code, 1)
        self.assertIn("is not valid UTF-8 TOML", out)
        self.assertEqual(self.config.read_text(), "[tui\nbroken = \n")
        self.config.unlink()
        target = self.base / "elsewhere.toml"
        target.write_text(DESTINATION_CODEX, encoding="utf-8")
        self.config.symlink_to(target)
        code, out, _ = self.apply()
        self.assertEqual(code, 1)
        self.assertIn("is a symlink or not a regular file", out)
        self.assertEqual(target.read_text(), DESTINATION_CODEX)
        self.assertEqual(self.backups(), [])

    def test_the_merge_takes_neither_one_for_true_nor_a_changed_type_for_a_match(self):
        self.assertFalse(cfg.strict_equal(1, True))
        self.assertFalse(cfg.strict_equal(1.0, 1))
        self.assertTrue(cfg.strict_equal({"a": [1, {"b": "c"}]}, {"a": [1, {"b": "c"}]}))
        plan = cfg.plan_merge({"features": {"daemon_auto_start": 0}}, {"features": {"daemon_auto_start": False}})
        self.assertEqual([(path, have, want) for path, have, want in plan.conflicts],
                         [(("features", "daemon_auto_start"), 0, False)])
        self.assertEqual(plan.expected, {"features": {"daemon_auto_start": 0}})
        # An existing value that is a table where the render has a plain value is a conflict, not an edit.
        plan = cfg.plan_merge({"model": {"a": 1}}, {"model": "x"})
        self.assertEqual(len(plan.conflicts), 1)
        self.assertEqual(cfg.first_difference({"a": {"b": 1}}, {"a": {"b": True}}), ("a", "b"))
        self.assertIsNone(cfg.first_difference({"a": {"b": 1}}, {"a": {"b": 1}}))


class RemotePluginRuleTests(unittest.TestCase):
    """The local fallback for the account's remote Codex plugins (wave-2 skills ruling, change 5): --apply reads the plugin
    cache and adds a name rule per plugin skill and an off switch per plugin MCP server, as Codex names them. The cache here
    is a fixture of this project's own, in the shapes of the cached bundles (manifest, skills/, .mcp.json)."""

    SKILL = "---\nname: {name}\ndescription: A fixture skill.\n---\nBody.\n"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.codex_home = self.home / ".codex"
        self.config = self.codex_home / "config.toml"
        self.claude = write_exe(self.base / "bin" / "claude", STUB_CLAUDE)
        self.codex = write_exe(self.base / "bin" / "codex", STUB_CODEX)
        patcher = mock.patch.dict(os.environ, {"STUB_MARKER": str(self.base / "client-calls.txt")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def plugin(self, plugin: str, version: str, manifest=None, skills=None, servers=()) -> Path:
        """A cached remote plugin: `manifest` is its plugin.json (None: none), `skills` maps a directory under skills/ to its
        SKILL.md text, `servers` names the MCP servers of its .mcp.json."""
        root = self.codex_home / "plugins/cache" / cfg.REMOTE_MARKETPLACE / plugin / version
        root.mkdir(parents=True)
        if manifest is not None:
            (root / ".codex-plugin").mkdir()
            (root / ".codex-plugin/plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
        for directory, text in (skills or {}).items():
            (root / "skills" / directory).mkdir(parents=True)
            (root / "skills" / directory / "SKILL.md").write_text(text, encoding="utf-8")
        if servers:
            (root / ".mcp.json").write_text(json.dumps({"mcpServers": {name: {"command": "node"} for name in servers}}),
                                            encoding="utf-8")
        return root

    def apply(self):
        return run_main("--apply", "--host", EXAMPLE_HOST, "--home", str(self.home), "--claude-bin", str(self.claude),
                        "--codex-bin", str(self.codex), "--codex-process-name", NO_PROCESS, *ONLY_CODEX_CONFIG)

    def test_the_names_are_the_ones_codex_gives_and_the_servers_are_each_plugins(self):
        self.plugin("superpowers", "6.4.2", {"name": "superpowers", "skills": "./skills/"}, {
            "brainstorming": self.SKILL.format(name="brainstorming"),
            "cli": self.SKILL.format(name="hf-cli"),                           # the frontmatter's name, not the folder's
            "quoted": self.SKILL.format(name="'quoted-skill'"),
            "spaced": self.SKILL.format(name="two   words  # a comment"),
            "unnamed": "---\ndescription: No name, so the folder's.\n---\n",
            "no-frontmatter": "Just text, which Codex does not load as a skill.\n"})
        self.plugin("superpowers", "6.3.0", {"name": "superpowers"}, {"old": self.SKILL.format(name="old-skill")})
        self.plugin("openai-developers", "1.3.6", {"name": "openai-developers", "mcpServers": "./.mcp.json"},
                    {"agents": self.SKILL.format(name="agents")}, servers=("local-confirmation",))
        self.plugin("blank-name", "0.1.0", {"name": " "}, {"x": self.SKILL.format(name="x")})   # the root's own name
        self.plugin("no-manifest", "1.0.0", None, {"y": self.SKILL.format(name="y")})        # Codex loads no plugin
        names, servers = cfg.remote_plugin_rules(self.codex_home)
        self.assertEqual(names, ["0.1.0:x", "openai-developers:agents", "superpowers:brainstorming", "superpowers:hf-cli",
                                 "superpowers:old-skill", "superpowers:quoted-skill", "superpowers:two words",
                                 "superpowers:unnamed"])
        self.assertEqual(servers, {"openai-developers@openai-curated-remote": ["local-confirmation"]})
        self.assertEqual(cfg.remote_plugin_rules(self.base / "no-codex-home"), ([], {}))

    def test_a_name_this_tool_cannot_read_is_refused_rather_than_guessed(self):
        self.plugin("p", "1.0.0", {"name": "p"}, {"folded": "---\nname: >-\n  folded\ndescription: d\n---\n"})
        with self.assertRaises(cfg.ConfigError) as caught:
            cfg.remote_plugin_rules(self.codex_home)
        self.assertIn("is not a one-line value this tool reads", str(caught.exception))
        code, _, err = self.apply()
        self.assertEqual(code, 1)
        self.assertIn("apply failed: the account's remote plugins in", err)
        self.assertFalse(self.config.exists())

    def test_an_apply_adds_the_rules_and_a_later_one_adds_only_the_new_rules_after_the_files_own(self):
        self.plugin("superpowers", "6.4.2", {"name": "superpowers"}, {"brainstorming": self.SKILL.format(name="brainstorming")})
        self.plugin("openai-developers", "1.3.6", {"name": "openai-developers"}, servers=("local-confirmation",))
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-800:])
        # Planned when read, in place only after the codex-config step's write and read-back (finding 2 of the Codex root
        # lane's read of b6828c7d): the line never says the rules are on before the file holds them.
        self.assertIn("remote plugins: 1 skill name rule(s) and 1 plugin MCP server off switch(es) planned", out)
        self.assertNotIn("turned off", out)
        text = self.config.read_text()
        config = tomllib.loads(text)
        # Relative, so Codex resolves it against the Codex home that holds this config.toml (the template's comment).
        installer = {"path": "skills/.system/skill-installer/SKILL.md", "enabled": False}
        self.assertEqual(config["skills"]["config"], [installer, {"name": "superpowers:brainstorming", "enabled": False}])
        self.assertEqual(text.count("[[skills.config]]"), 2)                # an array of tables, so it can grow as text
        self.assertEqual(config["plugins"]["openai-developers@openai-curated-remote"],
                         {"enabled": False, "mcp_servers": {"local-confirmation": {"enabled": False}}})
        # The account gains a plugin skill: the next run adds its rule after the file's own and changes nothing else.
        (self.codex_home / "plugins/cache" / cfg.REMOTE_MARKETPLACE / "superpowers/6.4.2/skills/debugging").mkdir()
        (self.codex_home / "plugins/cache" / cfg.REMOTE_MARKETPLACE / "superpowers/6.4.2/skills/debugging/SKILL.md"
         ).write_text(self.SKILL.format(name="systematic-debugging"), encoding="utf-8")
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-800:])
        self.assertIn("rules added to skills.config: 1, after the file's own", out)
        merged = tomllib.loads(self.config.read_text())
        self.assertEqual(merged["skills"]["config"], config["skills"]["config"] + [
            {"name": "superpowers:systematic-debugging", "enabled": False}])
        self.assertTrue(keeps_lines(text, self.config.read_text()))
        # The check that X11 asks for after an apply still passes (it reads the repository, never the host's files).
        code, out, err = run_main("--check")
        self.assertEqual(code, 0, err[-400:])
        self.assertIn("check passed", out)

    def test_a_file_with_rules_of_its_own_keeps_them_first(self):
        self.plugin("superpowers", "6.4.2", {"name": "superpowers"}, {"brainstorming": self.SKILL.format(name="brainstorming")})
        own = '[[skills.config]]\nname = "my-skill"\nenabled = false\n\n[tui]\nscreen_reader_detection_done = true\n'
        self.codex_home.mkdir(mode=0o700, exist_ok=True)
        self.config.write_text(own, encoding="utf-8")
        self.config.chmod(0o600)
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-800:])
        rules = tomllib.loads(self.config.read_text())["skills"]["config"]
        self.assertEqual(rules[0], {"name": "my-skill", "enabled": False})
        self.assertIn({"name": "superpowers:brainstorming", "enabled": False}, rules[1:])
        self.assertNotIn("conflict kept: skills.config", out)
        self.assertTrue(keeps_lines(own, self.config.read_text()))

    def test_a_rule_list_written_inline_is_refused_and_the_file_stays_as_it_was(self):
        self.plugin("superpowers", "6.4.2", {"name": "superpowers"}, {"brainstorming": self.SKILL.format(name="brainstorming")})
        inline = '[skills]\nconfig = [{ name = "my-skill", enabled = false }]\n'
        self.codex_home.mkdir(mode=0o700, exist_ok=True)
        self.config.write_text(inline, encoding="utf-8")
        self.config.chmod(0o600)
        code, out, _ = self.apply()
        self.assertEqual(code, 1)
        self.assertIn("the file defines it as an inline array, which text cannot extend", out)
        self.assertEqual(self.config.read_text(), inline)

    def test_an_existing_rule_list_gains_the_rules_or_is_refused_and_an_empty_one_is_never_kept_as_a_conflict(self):
        """Finding 2 of the Codex root lane's read of b6828c7d: an existing, valid `[skills] config = []` was not taken for a
        rule list, so the render's disable rules became a kept conflict and were lost while the step ended `merged with
        conflicts kept`. The empty list is a rule list now: the plan appends the render's rules to it, and since TOML writes
        an empty array only inline (and TOML 1.0 forbids adding [[skills.config]] items to a statically defined array, even
        an empty one), the text edit refuses it and writes nothing. A non-empty array of tables is extended after its own
        rules. The plan-level assertions on the empty list are the negative control: the earlier plan_merge kept it as a
        conflict with no appends."""
        installer = {"path": "/h/.codex/skills/.system/skill-installer/SKILL.md", "enabled": False}
        remote = {"name": "superpowers:brainstorming", "enabled": False}
        own = {"name": "my-skill", "enabled": False}
        rendered = {"skills": {"config": [installer, remote]}}
        for name, existing, appended, merged in (
                ("empty", [], [installer, remote], [installer, remote]),
                ("non-empty", [own, remote], [installer], [own, remote, installer])):
            with self.subTest(existing=name):
                plan = cfg.plan_merge({"skills": {"config": existing}}, rendered)
                self.assertEqual(plan.conflicts, [])
                self.assertEqual(plan.appends, [(("skills", "config"), appended)])
                self.assertEqual(plan.expected, {"skills": {"config": merged}})
                self.assertEqual(cfg.merge_report(plan), [f"rules added to skills.config: {len(appended)}, after the file's own"])
        # The writer still writes an empty list as a plain `key = []`, never as nothing.
        self.assertEqual(tomllib.loads(cfg.emit_toml({"skills": {"config": []}}, "# h")), {"skills": {"config": []}})
        self.plugin("superpowers", "6.4.2", {"name": "superpowers"}, {"brainstorming": self.SKILL.format(name="brainstorming")})
        self.codex_home.mkdir(mode=0o700, exist_ok=True)
        # The empty list, as a file: refused, nothing written, and no conflict reported in place of the rules.
        empty = '[skills]\nconfig = []\n\n[tui]\nscreen_reader_detection_done = true\n'
        self.config.write_text(empty, encoding="utf-8")
        self.config.chmod(0o600)
        code, out, _ = self.apply()
        self.assertEqual(code, 1, out[-800:])
        self.assertIn("cannot add 2 item(s) to skills.config: the file defines it as an inline array, which text cannot "
                      "extend; write it as [[skills.config]] items; it is empty, so removing the key is enough", out)
        self.assertNotIn("conflict kept: skills.config", out)
        self.assertNotIn("merged with conflicts kept", out)
        self.assertEqual(self.config.read_text(), empty)
        # The way out the message names: without the key, the next run adds both rules as [[skills.config]] items.
        self.config.write_text(empty.replace("[skills]\nconfig = []\n\n", ""), encoding="utf-8")
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-800:])
        self.assertEqual(tomllib.loads(self.config.read_text())["skills"]["config"],
                         [{"path": "skills/.system/skill-installer/SKILL.md", "enabled": False}, remote])
        # A non-empty array of tables, as a file: extended after its own rule, every line it had kept.
        tables = '[[skills.config]]\nname = "my-skill"\nenabled = false\n\n[tui]\nscreen_reader_detection_done = true\n'
        self.config.write_text(tables, encoding="utf-8")
        code, out, _ = self.apply()
        self.assertEqual(code, 0, out[-800:])
        self.assertIn("rules added to skills.config: 2, after the file's own", out)
        self.assertEqual(tomllib.loads(self.config.read_text())["skills"]["config"],
                         [own, {"path": "skills/.system/skill-installer/SKILL.md", "enabled": False}, remote])
        self.assertTrue(keeps_lines(tables, self.config.read_text()))

    def test_the_toml_writer_writes_a_list_of_tables_as_an_array_of_tables(self):
        data = {"skills": {"max_context_tokens": 6000, "config": [{"path": "/a", "enabled": False},
                                                                 {"name": "p:s", "enabled": False}]},
                "plugins": {"x@m": {"enabled": False, "mcp_servers": {"s": {"enabled": False}}}}}
        text = cfg.emit_toml(data, "# h")
        self.assertEqual(text.count("[[skills.config]]"), 2)
        self.assertEqual(tomllib.loads(text), data)


class CommandLineTests(unittest.TestCase):
    """How the guard reads the command line of a process to find Codex's app-server: through /proc where Linux has one, and
    through `ps` where there is none (macOS). Only the hint of the refusal depends on it; the refusal is `pgrep -x`'s."""

    PROGRAM = [sys.executable, "-c", "import time; time.sleep(120)"]
    ARGUMENTS = ("app-server", "--listen", "unix://", "two words")

    def spawn(self, *words: str) -> subprocess.Popen:
        process = subprocess.Popen([*self.PROGRAM, *words])
        self.addCleanup(lambda: (process.kill(), process.wait()))
        return process

    def words_of(self, pid: int, word: str) -> list:
        """The words of the command line once they hold `word`: they read empty for a moment while a new program is being
        set up."""
        words = []
        for _ in range(100):
            words = cfg.process_command_line(str(pid))
            if word in words:
                break
            time.sleep(0.05)
        return words

    @contextlib.contextmanager
    def no_proc(self):
        """The tool's /proc pointed at a directory that does not exist, so that it reads command lines as it does on macOS."""
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(cfg, "PROC", Path(tmp) / "no-proc"):
            yield

    def test_a_process_with_app_server_among_its_arguments_is_found_and_one_without_is_not(self):
        daemon, quiet = self.spawn(*self.ARGUMENTS), self.spawn("--listen", "unix://")
        self.words_of(daemon.pid, "app-server")
        self.words_of(quiet.pid, "--listen")
        pids = [str(daemon.pid), str(quiet.pid), "1", str(os.getpid()), "999999999", "not-a-pid", ""]
        self.assertEqual(cfg.app_server_pids(pids), [str(daemon.pid)])

    def test_the_program_itself_is_not_taken_for_an_argument(self):
        words = {"10": ["app-server"], "11": ["/x/codex", "app-server", "--listen", "unix://"], "12": ["/x/codex", "exec"],
                 "13": [], "14": [""]}
        with mock.patch.object(cfg, "process_command_line", side_effect=lambda pid: words[pid]):
            self.assertEqual(cfg.app_server_pids(list(words)), ["11"])

    def test_where_there_is_no_proc_the_command_line_comes_from_ps(self):
        if shutil.which("ps") is None:
            self.skipTest("no ps command on this host")
        daemon = self.spawn(*self.ARGUMENTS)
        with self.no_proc():
            words = self.words_of(daemon.pid, "app-server")
            self.assertTrue(words and words[0], words)
            # ps joins the arguments with spaces, so the argument that holds a space comes back as two words.
            self.assertEqual(words[-5:], ["app-server", "--listen", "unix://", "two", "words"])
            self.assertEqual(cfg.app_server_pids([str(daemon.pid), "1", "999999999", "not-a-pid"]), [str(daemon.pid)])

    def test_ps_is_asked_for_the_command_column_only_and_every_failure_leaves_the_hint_out(self):
        listing = subprocess.CompletedProcess([], 0, "/x/codex app-server --listen unix://\n", "")
        with self.no_proc():
            with mock.patch.object(subprocess, "run", return_value=listing) as run:
                self.assertEqual(cfg.process_command_line("123"), ["/x/codex", "app-server", "--listen", "unix://"])
                self.assertEqual(cfg.app_server_pids(["123"]), ["123"])
            # The environment of a process is never asked for: the one column is the command, and no option shows more.
            self.assertEqual(run.call_args.args[0], ["ps", "-ww", "-o", "command=", "-p", "123"])
            for failure in (FileNotFoundError("ps"), subprocess.TimeoutExpired("ps", 10), PermissionError("ps")):
                with mock.patch.object(subprocess, "run", side_effect=failure):
                    self.assertEqual(cfg.process_command_line("123"), [], failure)
            with mock.patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "")):
                self.assertEqual(cfg.process_command_line("123"), [])          # ps exits 1 for a process that is gone
            with mock.patch.object(subprocess, "run", side_effect=AssertionError("ps run for a pid that is no number")):
                self.assertEqual(cfg.process_command_line("not-a-pid"), [])
                self.assertEqual(cfg.process_command_line("1; echo"), [])

    @unittest.skipUnless(Path("/proc/self/cmdline").exists(), "no /proc on this platform: the ps reading above covers it")
    def test_where_there_is_a_proc_the_words_are_the_arguments_as_passed_and_the_reading_is_the_one_before(self):
        daemon, quiet = self.spawn(*self.ARGUMENTS), self.spawn("--listen", "unix://")
        words = self.words_of(daemon.pid, "app-server")
        self.assertEqual(words, [*self.PROGRAM, *self.ARGUMENTS])         # "two words" is one word here

        def reading_before_ps_was_added(pids):
            """What this tool did before the ps reading existed: the arguments of /proc/<pid>/cmdline, program left out."""
            found = []
            for pid in pids:
                try:
                    parts = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
                except OSError:
                    continue
                if b"app-server" in parts[1:]:
                    found.append(pid)
            return found
        self.words_of(quiet.pid, "--listen")
        pids = [str(daemon.pid), str(quiet.pid), "1", str(os.getpid()), "999999999", "not-a-pid", ""]
        self.assertEqual(reading_before_ps_was_added(pids), [str(daemon.pid)])      # control: the reference finds it
        self.assertEqual(cfg.app_server_pids(pids), reading_before_ps_was_added(pids))
        if shutil.which("ps"):                                                       # and ps gives the same words, joined
            with self.no_proc():
                self.assertEqual(cfg.process_command_line(str(daemon.pid)), " ".join(words).split())


class AdditiveOptionTests(unittest.TestCase):
    """The options added to the existing tools leave their defaults as they were."""

    def test_the_guard_step_installs_every_hook_by_default_and_only_the_named_ones_when_asked(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with contextlib.redirect_stdout(io.StringIO()):
                everything = icp.install_guards(home, True)
                only = icp.install_guards(home, True, ["secret_path_guard.py", "secret_path_guard.py"])
            self.assertEqual(list(everything), list(icp.HOOKS))
            self.assertEqual(list(only), ["secret_path_guard.py"])
            with self.assertRaises(icp.InstallError):
                icp.install_guards(home, True, ["nope.py"])
            self.assertEqual(list(home.iterdir()), [])

    def test_the_agents_step_installs_every_agent_by_default_and_only_the_named_ones_when_asked(self):
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(len(icp.install_agents(Path(tmp), True)), 11)
                self.assertEqual(icp.install_agents(Path(tmp), True, ["stack-verifier.md"]), ["planned"])
            with self.assertRaises(icp.InstallError):
                icp.install_agents(Path(tmp), True, ["nope.md"])

    def test_the_mcp_step_registers_the_servers_of_the_template_it_is_given(self):
        with tempfile.TemporaryDirectory() as tmp:
            template = Path(tmp) / "servers.json"
            template.write_text(json.dumps({"mcpServers": {"only": {"type": "stdio", "command": "only", "args": []}}}))
            asked = []
            with mock.patch.object(icp, "claude_mcp_get", side_effect=lambda binary, name: asked.append(name)):
                with contextlib.redirect_stdout(io.StringIO()):
                    icp.install_mcp_servers("claude", True, Path(tmp), Path(tmp), template=template)
                    icp.install_mcp_servers("claude", True, Path(tmp), Path(tmp))
        self.assertEqual(asked[0], "only")
        self.assertEqual(asked[1:], [n for n in json.loads(icp.MCP_TEMPLATE.read_text())["mcpServers"]])

    OLD_BLOCK = (managed_block.PROFILE_BEGIN_LINE + "\n"
                 "# The ecosystem's bin directory first on PATH, so `claude` in a login shell is its launcher.\n"
                 'case ":${PATH-}:" in\n'
                 '  ":$HOME/.local/share/codex-ecosystem/bin:"*) ;;\n'
                 '  *) PATH="$HOME/.local/share/codex-ecosystem/bin${PATH:+:$PATH}" ;;\n'
                 "esac\n"
                 "export PATH\n" + managed_block.PROFILE_END + "\n")

    def test_the_path_block_is_byte_identical_without_extra_directories(self):
        text = managed_block.profile_block("/home/example/.local/share/codex-ecosystem", "/home/example")
        self.assertEqual(text, self.OLD_BLOCK)
        self.assertEqual(managed_block.profile_block("/home/example/.local/share/codex-ecosystem", "/home/example", ()), text)

    def path_after(self, block: str, path: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            profile.write_text(block, encoding="utf-8")
            result = subprocess.run(["bash", "-c", f'. "{profile}"; printf %s "$PATH"'], capture_output=True, text=True,
                                    env={"HOME": "/home/example", "PATH": path})
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_extra_directories_are_added_behind_the_ecosystem_directory_and_never_twice(self):
        eco, home = "/home/example/.local/share/codex-ecosystem", "/home/example"
        extras = ("/home/example/.local/bin", "/home/example/.local/share/mise/shims", "/opt/other")
        block = managed_block.profile_block(eco, home, extras)
        self.assertIn('$HOME/.local/bin', block)
        self.assertIn('"/opt/other', block)
        self.assertEqual(self.path_after(block, "/usr/bin:/bin"),
                         ":".join([eco + "/bin", *extras, "/usr/bin", "/bin"]))
        # A directory that is already on PATH stays where it is, and the block run twice adds nothing.
        once = self.path_after(block, "/usr/bin:/home/example/.local/bin:/bin")
        self.assertEqual(once.count("/home/example/.local/bin"), 1)
        self.assertEqual(self.path_after(block + block, "/usr/bin:/bin"), self.path_after(block, "/usr/bin:/bin"))
        with self.assertRaises(managed_block.Refused):
            managed_block.profile_block(eco, home, ("relative/dir",))

    def test_the_cli_takes_the_option_and_writes_one_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            argv = [sys.executable, "-B", str(ROOT / "tools/adoption/managed_block.py"), "--home", str(home),
                    "profile-path", "--eco-root", str(home / ".local/share/codex-ecosystem"), "--extra-dir",
                    str(home / ".local/bin")]
            for _ in range(2):
                self.assertEqual(subprocess.run(argv, capture_output=True, text=True).returncode, 0)
            text = (home / ".profile").read_text()
        self.assertEqual(text.count("profile-path:begin"), 1)
        self.assertIn('PATH="$HOME/.local/bin${PATH:+:$PATH}"', text)


class PlanConfigurationTests(unittest.TestCase):
    """Run only the plan's configuration writes in scratch homes, without installing tools or contacting providers."""

    def config_command(self, slot, filename):
        plan = json.loads((ROOT / cfg.PLAN_REL / "install-plan.json").read_text())
        row = next(row for row in plan["owners"] if row["slot"] == slot)
        commands = [command for command in row["commands"] if f"config/{filename}" in command]
        self.assertEqual(len(commands), 1, f"{slot} must persist {filename} before client hooks are wired")
        return commands[0]

    def test_rtk_install_persists_the_recipe_exclusions_and_preserves_existing_configuration(self):
        command = self.config_command("command-output", "rtk-config.toml")
        source = ROOT / cfg.PLAN_REL / "config/rtk-config.toml"
        recipe = (ROOT / "recipes/README.md").read_text()
        expected = re.search(r"```toml\n(\[hooks\]\nexclude_commands = \[.*?\n\])\n```", recipe, re.S).group(1) + "\n"
        self.assertEqual(source.read_text(), expected)
        for xdg in (None, "absolute", "relative"):
            with self.subTest(xdg=xdg), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp) / "home"
                config_root = Path(tmp) / "xdg" if xdg == "absolute" else home / ".config"
                target = config_root / "rtk/config.toml"
                env = dict(os.environ, HOME=str(home), plan_dir=str(ROOT / cfg.PLAN_REL),
                           ECO_ROOT=str(Path(tmp) / "ecosystem"))
                env.pop("XDG_CONFIG_HOME", None)
                if xdg:
                    env["XDG_CONFIG_HOME"] = str(config_root) if xdg == "absolute" else "relative-config"

                def write_config():
                    result = subprocess.run(["bash", "-euo", "pipefail", "-c", command],
                                            cwd=tmp, env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    return result

                self.assertFalse(target.exists())
                write_config()
                self.assertEqual(target.read_text(), expected)
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
                self.assertEqual(write_config().stderr, "")   # an identical rerun has no warning
                target.write_text("# operator configuration\n[hooks]\nexclude_commands = [\"curl\"]\n")
                original = target.read_bytes()
                result = write_config()
                self.assertEqual(target.read_bytes(), original)
                self.assertIn("differs; retained", result.stderr)
                self.assertFalse((Path(tmp) / "relative-config/rtk/config.toml").exists())

    def test_chub_install_persists_both_opt_outs_and_preserves_existing_configuration(self):
        command = self.config_command("api-docs", "chub-config.yaml")
        source = ROOT / cfg.PLAN_REL / "config/chub-config.yaml"
        self.assertEqual([line for line in source.read_text().splitlines() if not line.startswith("#")],
                         ["telemetry: false", "feedback: false"])
        for override in (False, True):
            with self.subTest(chub_dir=override), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp) / "home"
                target = (Path(tmp) / "custom-chub" if override else home / ".chub") / "config.yaml"
                env = dict(os.environ, HOME=str(home), plan_dir=str(ROOT / cfg.PLAN_REL),
                           XDG_CONFIG_HOME=str(Path(tmp) / "xdg"), ECO_ROOT=str(Path(tmp) / "ecosystem"))
                env.pop("CHUB_DIR", None)
                if override:
                    env["CHUB_DIR"] = str(target.parent)

                def write_config():
                    result = subprocess.run(["bash", "-euo", "pipefail", "-c", command],
                                            cwd=tmp, env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    return result

                self.assertFalse(target.exists())
                write_config()
                self.assertEqual(target.read_bytes(), source.read_bytes())
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
                self.assertEqual(write_config().stderr, "")
                target.write_text("# operator configuration\ntelemetry: true\nfeedback: true\n")
                original = target.read_bytes()
                result = write_config()
                self.assertEqual(target.read_bytes(), original)
                self.assertIn("differs; retained", result.stderr)
                if override:
                    self.assertFalse((home / ".chub/config.yaml").exists())

    def test_plan_checker_counts_direct_config_installs_and_refuses_an_uncopied_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_dir = Path(tmp) / "plan"
            shutil.copytree(ROOT / cfg.PLAN_REL, plan_dir)
            args = [sys.executable, "-B", str(ROOT / cfg.PLAN_REL / "check_plan.py"), "--plan-dir", str(plan_dir),
                    "--manifest", str(ROOT / cfg.MANIFEST_REL)]
            result = subprocess.run(args, cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("acceptance entries agree with the scripts", result.stdout)
            (plan_dir / "config/uncopied-config.yaml").write_text("telemetry: false\n")
            # A filename mentioned in an installation comment cannot turn an uncopied file into an installed one.
            with (plan_dir / "install.sh").open("a") as stream:
                stream.write('\n# install -m 0600 -- "$plan_dir/config/uncopied-config.yaml" "$HOME/config.yaml"\n')
            result = subprocess.run(args, cwd=tmp, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("config/uncopied-config.yaml is copied by no install function", result.stdout)


class RecordTests(unittest.TestCase):
    RECORD = ROOT / "docs/decisions/2026-10-02-new-wsl-client-configuration.md"
    FILES = (RECORD, ROOT / "tools/adoption/new_wsl_client_config.py", MAP, Path(__file__),
             *(ROOT / relative for relative in cfg.GENERATED_BLOCKS.values()))

    def test_the_record_holds_the_tables_the_tool_prints(self):
        results, _, plan, errors, _ = cfg.analyse(ROOT)
        self.assertEqual(errors, [])
        tables = cfg.markdown_tables(ROOT, results, plan).rstrip("\n")
        text = self.RECORD.read_text(encoding="utf-8")
        self.assertIn(tables, text, "regenerate the record's tables with `new_wsl_client_config.py --check --markdown`")
        # The user reads the list of dropped sentences in the record: it is the one the tool prints, every unit in full.
        manifest = cfg.load_manifest(ROOT)
        listed = cfg.dropped_markdown(ROOT, cfg.generate_blocks(ROOT, cfg.unwired_names(results, manifest))).rstrip("\n")
        self.assertIn(listed, text, "regenerate the record's dropped list with `--check --markdown`")
        self.assertEqual(listed.count("\nline "), 0)          # all harnesses in the sources are now selected
        # Control: a table whose row differs from the tool's is not in the record.
        self.assertNotIn(tables.replace("| `not_wired` |", "| `slot:other` |", 1), text)
        piece_rows = tables.split("\n\n")[0].splitlines()[2:]
        self.assertEqual(len(piece_rows), sum(1 for v in results if not v.wired and not v.authorization))
        # The authorization settings are a table of their own, and none of them is among the pieces that are not wired.
        self.assertEqual(len(tables.split("\n\n")), 3)
        authorization_rows = tables.split("\n\n")[1].splitlines()[2:]
        self.assertEqual(len(authorization_rows), len(AuthorizationTests.ALL))
        self.assertFalse([row for row in piece_rows if any(key in row for key in AuthorizationTests.ALL)])

    def test_the_counts_that_the_record_states_are_the_ones_check_prints(self):
        text = " ".join(self.RECORD.read_text(encoding="utf-8").split())
        matches = list(re.finditer(r"Today: (\d+) pieces, (\d+) wired \((\d+) practice, (\d+) through a slot\), (\d+) not wired "
                                  r"\((\d+) through a slot that does not install, (\d+) by their own entry\) and (\d+) authorization "
                                  r"pieces", text))
        match = matches[-1] if matches else None  # Latest dated projection; historical counts remain intact.
        self.assertIsNotNone(match, "Decision 2 no longer states the counts in that shape")
        rows = json.loads(run_main("--check", "--json")[1])

        def kind(row):
            return row["wiring"].split(":")[0]
        counted = (len(rows), sum(1 for r in rows if r["wired"]),
                   sum(1 for r in rows if kind(r) == "practice" and r["wired"]),
                   sum(1 for r in rows if kind(r) == "slot" and r["wired"]),
                   sum(1 for r in rows if not r["wired"] and kind(r) != "authorization"),
                   sum(1 for r in rows if kind(r) == "slot" and not r["wired"]),
                   sum(1 for r in rows if kind(r) == "not_wired"),
                   sum(1 for r in rows if kind(r) == "authorization"))
        self.assertEqual(tuple(int(group) for group in match.groups()), counted)
        # The counts line of --check says the same, and so does Decision 14.
        self.assertIn(f"pieces: {counted[0]}; wired: {counted[1]}; not wired: {counted[4]}; authorization: {counted[7]}\n",
                      run_main("--check")[1])
        self.assertIn(f"`authorization: {counted[7]}`, and {counted[4]} pieces are not wired", text)

    def test_the_sentence_about_the_blocks_reads_the_same_in_the_recipe_and_both_records(self):
        places = {"the recipe": ROOT / "adoption/platforms/linux-wsl2-new-distro.md",
                  "the decision record": self.RECORD,
                  "the recipe's decision record": ROOT / "docs/decisions/2026-10-01-new-wsl-distro-recipe.md"}
        for place, path in places.items():
            text = " ".join(path.read_text(encoding="utf-8").split())
            self.assertIn(recipe_tests.F9_BLOCKS_SENTENCE, text, place)
            for stale in (recipe_tests.F9_OLD_BLOCKS_CLAIM, recipe_tests.F9_PREVIOUS_BLOCKS_CLAIM,
                          "the filter works by the names the map declares as not wired"):
                self.assertNotIn(stale, text, f"{place} still says: {stale}")

    def test_no_file_of_this_change_names_a_personal_path_or_an_address(self):
        for path in self.FILES:
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertIsNone(re.search(r"/(?:home|Users)/(?!example(?:/|\b))[A-Za-z0-9_.-]+", text))
                self.assertIsNone(re.search(r"[\w.+-]+@[\w-]+\.(?:com|org|net)\b", text.replace("@openai-codex", "")), path.name)


class RecipeCommandTests(unittest.TestCase):
    """F9 of the recipe runs this tool with flags that it has."""

    def f9_commands(self) -> list:
        return [command for step, _, command in recipe_tests.recipe_rows(recipe_tests.read(recipe_tests.RECIPE))
                if step == "F9"]

    def test_every_tool_flag_in_f9_is_a_flag_of_the_tool_and_every_file_it_runs_exists(self):
        commands = self.f9_commands()
        tool_lines = [c for c in commands if "new_wsl_client_config.py" in c]
        self.assertTrue(tool_lines, commands)
        for line in tool_lines:
            words = line.split()
            args = [w.strip("'") for w in words[words.index("tools/adoption/new_wsl_client_config.py") + 1:]]
            with self.subTest(command=line):
                cfg.build_parser().parse_args([a.replace("<host>", "example") for a in args])
        for command in commands:
            for word in command.split():
                if word.endswith((".sh", ".py")) and "/" in word:
                    self.assertTrue((ROOT / word.strip("'")).is_file(), word)



class RtkNativeLayoutTests(unittest.TestCase):
    def apply(self, temporary, dry=False, wired=True):
        args = cfg.build_parser().parse_args(["--apply", "--home", str(temporary)] + (["--dry-run"] if dry else []))
        runner = cfg.Apply(args)
        runner.eco = Path(temporary) / "eco"
        runner.wired = {"step/rtk-claude-init": True} if wired else {}
        return runner

    def test_dry_run_and_unwired_slot_do_not_execute_the_native_installer(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(subprocess, "run") as run:
            for dry, wired, expected in ((True, True, "planned"), (False, False, "left out")):
                runner = self.apply(tmp, dry, wired)
                with contextlib.redirect_stdout(io.StringIO()):
                    runner.step_rtk_claude_init()
                self.assertEqual(runner.outcomes, [("rtk-claude-init", expected)])
            run.assert_not_called()

    def test_native_global_default_is_used_and_its_files_are_read_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = self.apply(tmp)
            def native(argv, **kwargs):
                self.assertEqual(argv, [str(runner.eco / "bin/rtk"), "init", "-g", "--no-patch"])
                self.assertEqual(kwargs["env"]["HOME"], tmp)
                target = Path(tmp) / ".claude"
                target.mkdir()
                (target / "RTK.md").write_text("Native synthetic RTK instructions.\n")
                (target / "CLAUDE.md").write_text("@RTK.md\n")
                return subprocess.CompletedProcess(argv, 0, "Native init succeeded.\n", "")
            with mock.patch.object(subprocess, "run", side_effect=native), contextlib.redirect_stdout(io.StringIO()):
                runner.step_rtk_claude_init()
            self.assertEqual(runner.outcomes, [("rtk-claude-init", "applied")])

    def test_exit_zero_without_the_native_import_fails_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = self.apply(tmp)
            target = Path(tmp) / ".claude"
            target.mkdir()
            (target / "RTK.md").write_text("Synthetic file without import.\n")
            with mock.patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")), \
                    contextlib.redirect_stdout(io.StringIO()):
                runner.step_rtk_claude_init()
            self.assertEqual(runner.outcomes, [("rtk-claude-init", "failed")])


if __name__ == "__main__":
    unittest.main()
