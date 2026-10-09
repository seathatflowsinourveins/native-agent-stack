"""Hosted-model freshness: native catalogs, active selectors and dated evidence."""
from __future__ import annotations

import contextlib
import copy
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts import active_model_currency as mc

NOW = "2026-10-09T20:31:55Z"


def catalog():
    latest = {"gpt-sol": "gpt-6.1-sol", "gpt-astra": "gpt-6-astra", "gpt-luna": "gpt-6-luna",
              "claude-opus": "claude-opus-5-5", "claude-sonnet": "claude-sonnet-5-5",
              "claude-haiku": "claude-haiku-5-5", "claude-fable": "claude-fable-5-1"}
    aliases = {value: value for value in latest.values()}
    aliases["gpt-6.1-sol-max"] = "gpt-6.1-sol"
    aliases["claude-opus-5-5[1m]"] = "claude-opus-5-5"
    return {"schema_version": 1, "generated_at": NOW, "latest": latest, "aliases": aliases,
            "sources": [{"name": name, "observed_at": NOW, "sha256": "a" * 64, "rows": 1}
                        for name in ("codex", "omniroute", "claude")]}


class ActiveModelCurrencyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        self.manifest = self.root / mc.MANIFEST
        self.write(mc.MANIFEST, json.dumps(catalog()))

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def check(self):
        return mc.check(catalog(), [self.root])

    def cli(self, *arguments, event=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), \
                mock.patch("sys.stdin", io.StringIO(json.dumps(event) if event is not None else "")):
            rc = mc.main([*arguments, "--root", str(self.root), "--now", NOW, "--json"])
        return rc, stdout.getvalue(), stderr.getvalue()

    def test_current_models_and_observed_effort_alias_pass(self):
        self.write("adoption/templates/client.toml", 'model = "cx/gpt-6.1-sol-max"\nreview_model = "gpt-6-astra"\n')
        self.assertEqual(self.check()["status"], "current")
        self.assertEqual(self.cli("check")[0], 0)

    def test_stale_active_default_fails_and_reports_only_model_values(self):
        sentinel = "private-fixture-value-must-never-be-printed"
        self.write("config.json", json.dumps({"api_key": sentinel, "model": "gpt-6-sol"}))
        rc, stdout, _ = self.cli("check")
        self.assertEqual(rc, 1)
        result = json.loads(stdout)
        self.assertEqual(result["findings"][0]["expected"], "gpt-6.1-sol")
        self.assertNotIn(sentinel, stdout)
        self.assertNotIn("api_key", stdout)

    def test_active_markdown_agent_is_not_exempt(self):
        self.write("adoption/agents/claude/helper.md", '---\nmodel: claude-opus-5\n---\n')
        self.assertEqual(self.check()["stale_count"], 1)

    def test_active_lane_and_date_named_config_are_not_exempt(self):
        self.write("lanes/wsl-lab/config-20261009.yaml", 'model: gpt-6-sol\n')
        self.assertEqual(self.check()["stale_count"], 1)

    def test_active_research_or_notes_defaults_are_not_blanket_exempt(self):
        self.write("research/worker.py", 'DEFAULT_MODEL = "gpt-6-sol"\n')
        self.write("notes/agents/helper.md", 'model: claude-opus-5\n')
        self.assertEqual(self.check()["stale_count"], 2)

    def test_current_install_kit_configuration_remains_active(self):
        self.write("evidence/artifacts/new-wsl-install-plan-20261002/config/client.json", '{"model":"claude-opus-5"}')
        self.assertEqual(self.check()["stale_count"], 1)

    def test_dated_record_and_decision_preserve_old_models(self):
        self.write("evidence/receipts/old.json", '{"model":"gpt-6-sol"}')
        self.write("docs/decisions/2026-09-20-route.md", 'model: claude-opus-5\n')
        receipt = self.write("observability/receipt.json", json.dumps({"recorded_at": "2026-09-20T00:00:00Z", "model": "gpt-6-sol"}))
        before = receipt.read_bytes()
        self.assertEqual(self.check()["stale_count"], 0)
        self.assertEqual(receipt.read_bytes(), before)

    def test_date_in_active_json_does_not_exempt_it(self):
        self.write("client.json", '{"generated_at":"2026-09-20T00:00:00Z","model":"gpt-6-sol"}')
        self.assertEqual(self.check()["stale_count"], 1)

    def test_timestamped_measurements_inside_live_carrier_are_records(self):
        self.write("docs/live.json", json.dumps({"model": "gpt-6.1-sol", "observations": [
            {"started_at_utc": "2026-09-20T00:00:00Z", "exit_code": 0, "requested_model": "gpt-6-sol"}]}))
        self.assertEqual(self.check()["stale_count"], 0)

    def test_supported_catalog_is_not_a_python_default(self):
        self.write("tools/check.py", 'import re\nMODEL = re.compile(r"gpt-reserve|gpt-[0-9]+")\nDEFAULT_MODEL = "gpt-6.1-sol"\n')
        self.assertEqual(self.check()["stale_count"], 0)

    def test_python_cli_environment_and_mapping_defaults_are_checked(self):
        self.write("tools/run.py", 'import os\nMODEL = os.getenv("MODEL", "gpt-6-sol")\nparser.add_argument("--model", default="claude-opus-5")\nconfig = {"model": "gpt-6-sol"}\n')
        self.assertEqual(self.check()["stale_count"], 3)

    def test_shell_environment_default_and_model_flag_are_checked(self):
        self.write("tools/launch.sh", 'MODEL="gpt-6-sol"\ncodex exec --model gpt-6-sol\n')
        self.assertEqual(self.check()["stale_count"], 2)

    def test_claude_context_suffix_and_short_alias_override(self):
        self.write(".claude/settings.json", '{"model":"opus","env":{"ANTHROPIC_DEFAULT_OPUS_MODEL":"claude-opus-5"}}')
        result = self.check()
        self.assertEqual(result["stale_count"], 1)
        self.assertEqual(result["findings"][0]["model"], "claude-opus-5")

    def test_unknown_effort_alias_does_not_pass_by_prefix(self):
        self.write("client.toml", 'model="gpt-6.1-sol-unobserved"\n')
        self.assertEqual(self.check()["stale_count"], 1)

    def test_missing_and_aged_manifest_are_unknown_not_current(self):
        self.manifest.unlink()
        self.assertEqual(self.cli("check")[0], 2)
        old = catalog();old["generated_at"] = "2026-10-07T20:31:55Z"
        self.write(mc.MANIFEST, json.dumps(old))
        self.assertEqual(self.cli("check")[0], 2)

    def test_failed_source_and_unapproved_alias_target_are_rejected(self):
        value = catalog();value["sources"].pop()
        self.write(mc.MANIFEST, json.dumps(value))
        self.assertEqual(self.cli("check")[0], 2)
        value = catalog();value["aliases"]["bad"] = "gpt-6-sol"
        self.write(mc.MANIFEST, json.dumps(value))
        self.assertEqual(self.cli("check")[0], 2)
        value = catalog();value["aliases"]["gpt-6-sol"] = "gpt-6.1-sol"
        self.write(mc.MANIFEST, json.dumps(value))
        self.assertEqual(self.cli("check")[0], 2)

    def test_invalid_manifest_shapes_emit_incomplete_notice_instead_of_traceback(self):
        values = [[], {**catalog(), "latest": []}, {**catalog(), "sources": [None, None, None]},
                  {**catalog(), "generated_at": 123}]
        for value in values:
            with self.subTest(value=value):
                self.write(mc.MANIFEST, json.dumps(value))
                self.assertEqual(self.cli("check")[0], 2)
                rc, stdout, stderr = self.cli("notice", event={"hook_event_name": "SessionStart"})
                self.assertEqual((rc, stderr), (0, ""))
                self.assertIn("check incomplete", json.loads(stdout)["hookSpecificOutput"]["additionalContext"])

    def test_redating_manifest_does_not_refresh_old_source_observations(self):
        value = catalog()
        value["sources"][0]["observed_at"] = "2026-10-07T20:31:55Z"
        self.write(mc.MANIFEST, json.dumps(value))
        self.assertEqual(self.cli("check")[0], 2)

    def test_native_routing_aliases_cannot_exempt_a_stale_model(self):
        for routing in ["gpt-reserve", ["gpt-6-sol"], ["gpt-reserve", "gpt-reserve"], [{}]]:
            with self.subTest(routing=routing):
                value = catalog();value["native_routing_aliases"] = routing
                self.write(mc.MANIFEST, json.dumps(value))
                self.assertEqual(self.cli("check")[0], 2)
        value = catalog();value["native_routing_aliases"] = ["gpt-reserve", "codex-auto-review"]
        self.write(mc.MANIFEST, json.dumps(value))
        self.write("client.toml", 'model = "gpt-reserve"\nreview_model = "codex-auto-review"\n')
        self.assertEqual(self.cli("check")[0], 0)
        value["native_routing_aliases"] = []
        self.write(mc.MANIFEST, json.dumps(value))
        self.assertEqual(self.cli("check")[0], 1)

    def test_session_start_notice_is_informational_and_never_starts_models(self):
        self.write("client.json", '{"model":"gpt-6-sol"}')
        rc, stdout, _ = self.cli("notice", event={"hook_event_name": "SessionStart"})
        self.assertEqual(rc, 0)
        notice = json.loads(stdout)["hookSpecificOutput"]
        self.assertEqual(notice["hookEventName"], "SessionStart")
        self.assertIn("1 stale active selectors", notice["additionalContext"])
        self.assertEqual(self.cli("notice", event={"hook_event_name": "UserPromptSubmit"})[1], "")

    def test_current_session_is_quiet_and_incomplete_session_gets_notice(self):
        self.assertEqual(self.cli("notice", event={"hook_event_name": "SessionStart"})[:2], (0, ""))
        self.manifest.unlink()
        rc, stdout, _ = self.cli("notice", event={"hook_event_name": "SessionStart"})
        self.assertEqual(rc, 0)
        self.assertIn("check incomplete", json.loads(stdout)["hookSpecificOutput"]["additionalContext"])


class GenerateLatestModelsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root = Path(temp.name)
        self.codex = self.root / "codex.json";self.gateway = self.root / "gateway.json";self.claude = self.root / "claude.json"
        values = catalog()["latest"]
        self.codex.write_text(json.dumps({"models": [{"slug": x} for x in values.values() if x.startswith("gpt-")] + [{"slug": "gpt-6-sol"}]}))
        self.gateway.write_text(json.dumps({"data": [{"id": "cx/gpt-6.1-sol-max", "created": 9999999999}, {"id": "cx/gpt-6-sol", "created": 9999999999}]}))
        self.claude.write_text(json.dumps({"data": [{"id": x, "lifecycle": "active"} for x in values.values() if x.startswith("claude-")], "has_more": False}))

    def generate(self):
        return mc.generate(self.codex, self.gateway, self.claude, NOW)

    def test_native_sources_generate_seven_families_and_observed_aliases(self):
        value = self.generate()
        self.assertEqual(value["latest"], catalog()["latest"])
        self.assertEqual(value["aliases"]["cx/gpt-6.1-sol-max"], "gpt-6.1-sol")
        self.assertNotIn("gpt-6-sol", value["aliases"])
        self.assertFalse(value["limits"]["codex_network_refresh_certified"])
        self.assertFalse(value["limits"]["gateway_created_is_release_date"])

    def test_only_observed_native_routing_aliases_enter_manifest(self):
        data = json.loads(self.codex.read_text())
        data["models"].extend([{"slug": "gpt-reserve"}, {"slug": "gpt-reserve"}, {"slug": "codex-auto-review"}, {"slug": "unknown-router"}])
        self.codex.write_text(json.dumps(data))
        self.assertEqual(self.generate()["native_routing_aliases"], ["codex-auto-review", "gpt-reserve"])

    def test_new_stable_generation_updates_latest_without_hardcoded_era(self):
        data = json.loads(self.codex.read_text());data["models"].append({"slug": "gpt-6.2-sol"});self.codex.write_text(json.dumps(data))
        self.assertEqual(self.generate()["latest"]["gpt-sol"], "gpt-6.2-sol")

    def test_gateway_alias_cannot_invent_new_authoritative_generation(self):
        self.gateway.write_text('{"data":[{"id":"cx/gpt-99-sol","created":9999999999}]}')
        self.assertEqual(self.generate()["latest"]["gpt-sol"], "gpt-6.1-sol")

    def test_retired_claude_generation_and_epoch_dates_do_not_override_active_line(self):
        data=json.loads(self.claude.read_text());data["data"].append({"id":"claude-opus-9-9","lifecycle":"retired","created_at":"1970-01-01T00:00:00Z"});self.claude.write_text(json.dumps(data))
        self.assertEqual(self.generate()["latest"]["claude-opus"], "claude-opus-5-5")

    def test_incomplete_pagination_or_missing_family_fails_generation(self):
        data=json.loads(self.claude.read_text());data["has_more"]=True;self.claude.write_text(json.dumps(data))
        with self.assertRaises(mc.CurrencyError):self.generate()
        data["has_more"]=False;data["data"].pop();self.claude.write_text(json.dumps(data))
        with self.assertRaises(mc.CurrencyError):self.generate()


class CurrencyCollectorIntegrationTests(unittest.TestCase):
    def test_every_currency_check_runs_active_selector_check_and_fails_stale(self):
        from tests.test_currency_due import Checkout
        from scripts import currency_due as cd
        fixture=Checkout(self)
        fixture.set(cd.ACTIVE_MODELS[0], {"schema_version":1,"status":"stale","stale_count":1,
                    "findings":[{"path":"fixture/client.toml","line":1,"model":"gpt-6-sol","expected":"gpt-6.1-sol"}],"errors":[]}, code=1)
        code, stdout, stderr=fixture.run()
        self.assertEqual((code,stderr),(1,""))
        self.assertIn("1 stale model selector",stdout)
        args=fixture.recorded(cd.ACTIVE_MODELS[0]);self.assertEqual(args[0],"check");self.assertIn("--json",args)
        self.assertEqual(json.loads(fixture.due_file.read_text())["due"][cd.MODEL_KEY],1)

    def test_incomplete_selector_check_does_not_remove_existing_due_notice(self):
        from tests.test_currency_due import Checkout
        from scripts import currency_due as cd
        fixture=Checkout(self);fixture.state.mkdir();fixture.due_file.write_text("retained-notice")
        fixture.set(cd.ACTIVE_MODELS[0], {"schema_version":1,"status":"unknown","stale_count":0,"findings":[],"errors":["catalog unavailable"]},code=2)
        code,_,_=fixture.run();self.assertEqual(code,2);self.assertEqual(fixture.due_file.read_text(),"retained-notice")


class SessionStartHookTemplateTests(unittest.TestCase):
    def template(self):
        root = Path(mc.__file__).resolve().parents[1]
        return json.loads((root / "adoption/templates/model-currency.hooks.template.json").read_text())

    def test_cc_patch_appends_template_and_preserves_existing_client_settings(self):
        root = Path(mc.__file__).resolve().parents[1]
        patch = json.loads((root / "adoption/templates/model-currency.user-hooks.patch.json").read_text())
        self.assertEqual({target["path"] for target in patch["targets"]}, {"~/.codex/hooks.json", "~/.claude/settings.json"})
        group = self.template()["hooks"]["SessionStart"][0]
        for target in patch["targets"]:
            with self.subTest(target=target["path"]):
                before = {"model": "gpt-6.1-sol", "other_setting": [1, 2], "hooks": {
                    "SessionStart": [{"hooks": [{"type": "command", "command": "existing-start"}]}],
                    "PreToolUse": [{"hooks": [{"type": "command", "command": "existing-tool"}]}]}}
                after = copy.deepcopy(before)
                self.assertEqual(target["format"], "RFC6902")
                self.assertEqual(target["patch"], [{"op": "add", "path": "/hooks/SessionStart/-", "value": group}])
                after["hooks"]["SessionStart"].append(copy.deepcopy(group))
                after["hooks"]["SessionStart"].pop()
                self.assertEqual(after, before)

    def test_shipped_hook_command_runs_offline_with_native_event_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            checkout = home / "code/native-agent-stack"
            checkout.mkdir(parents=True)
            subprocess.run(["git", "init", "-q", str(checkout)], check=True, capture_output=True)
            script = checkout / "scripts/active_model_currency.py"
            script.parent.mkdir()
            shutil.copyfile(mc.__file__, script)
            manifest = checkout / mc.MANIFEST
            manifest.parent.mkdir(parents=True)
            value = catalog()
            value["generated_at"] = datetime.now(timezone.utc).isoformat()
            for source in value["sources"]:
                source["observed_at"] = value["generated_at"]
            manifest.write_text(json.dumps(value))
            (checkout / "client.toml").write_text('model = "gpt-6-sol"\n')
            group = self.template()["hooks"]["SessionStart"][0]
            self.assertEqual(group["matcher"], "startup|resume")
            handler = group["hooks"][0]
            self.assertEqual(handler["type"], "command")
            result = subprocess.run(["bash", "-c", handler["command"]], env={**os.environ, "HOME": str(home)},
                                    input=json.dumps({"hook_event_name": "SessionStart", "source": "startup"}),
                                    capture_output=True, text=True, timeout=handler["timeout"])
            self.assertEqual((result.returncode, result.stderr), (0, ""))
            notice = json.loads(result.stdout)["hookSpecificOutput"]
            self.assertEqual(notice["hookEventName"], "SessionStart")
            self.assertIn("1 stale active selectors", notice["additionalContext"])


if __name__ == "__main__":
    unittest.main()
