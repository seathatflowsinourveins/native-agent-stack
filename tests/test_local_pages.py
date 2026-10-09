"""Finite, network-independent invariants for the native local page composer."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import base64
import builtins
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("local_pages_builder", ROOT / "tools/local-pages/build_pages.py")
assert SPEC is not None and SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class DocumentAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.doctype = False
        self.tags: list[str] = []
        self.attributes: list[dict[str, str | None]] = []

    def handle_decl(self, declaration: str) -> None:
        self.doctype = declaration.lower() == "doctype html"

    def handle_starttag(self, tag: str, attributes: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        self.attributes.append(dict(attributes))


class LocalPagesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="local-pages-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "source-checkout"
        self.state = self.base / "state"
        self.output = self.base / "served"
        self.receipt = self.base / "custody/refresh.json"
        self.assets = self.base / "composer-assets"
        self.assets.mkdir()
        (self.assets / "site.css").write_text("body { color: #183047; }\n")
        (self.assets / "site.js").write_text("'use strict';\n")
        self.asset_patch = patch.object(BUILDER, "ASSETS", self.assets)
        self.asset_patch.start()
        self.addCleanup(self.asset_patch.stop)
        native = self.root / "tools/north-star/build_readiness.py"
        native.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "tools/north-star/build_readiness.py", native)
        sources = {}
        for name in ("foundation", "stack", "evidence", "profile", "sdk_contract", "sdk_rows"):
            path = self.root / "fixtures" / (name + ".json")
            self.write_json(path, {"checked_at": "2024-03-04T05:06:07Z"} if name == "foundation" else {})
            sources[name] = {"root": "repo", "path": path.relative_to(self.root).as_posix()}
        self.gate = self.state / "gate.json"
        self.write_json(self.gate, {"updated_utc": "2024-04-05T06:07:08Z", "state": "retained pending measurement", "owner": "test lane"})
        sources["gate"] = {"root": "state", "path": "gate.json"}
        self.source_spec = {"schema_version": 1, "sources": sources, "gates": [{"id": "G-test", "title": "Test gate", "fields": {"state": {"source": "gate", "pointer": "/state"}, "owner": {"source": "gate", "pointer": "/owner"}}}]}
        self.source_index = self.root / "tools/north-star/sources.json"
        self.write_json(self.source_index, self.source_spec)
        self.cc = self.state / "coordination/command-center/cc-tools"
        self.gaps_path = self.cc / "gaps/gaps.json"
        self.gaps = {"updated_utc": "2024-05-06T07:08Z", "gaps": [{"id": "gap-1", "group": "Measurement", "sev": "critical", "title": "Pending measurement", "state": "Source says pending", "owner": "test lane", "next": "Capture the native receipt", "due": "2024-05-07T08:00Z", "evidence": "receipts/probe.json"}]}
        self.write_json(self.gaps_path, self.gaps)
        self.road_path = self.cc / "roadmap/roadmap-status.json"
        self.roadmap = {"milestones": [{"at": "2024-06-07T08:09:00Z", "what": "Retained milestone event", "state": "pending", "kind": "warn"}], "servers": [{"key": "test", "label": "Test server", "job": "Test role", "paired": "No new invocation", "verdict": "pending", "next": "Read the receipt"}], "ladder": ["**Selected:** recorded upstream source"], "owner": ["OWNER-DIRECTION-SENTINEL"], "rules": ["RULES-DIRECTION-SENTINEL"], "lead": "Unsupported {g_total} narrative", "glance": [{"value": "{g_closed}"}]}
        self.write_json(self.road_path, self.roadmap)
        self.road_inputs = self.cc / "roadmap/roadmap-inputs.json"
        self.write_json(self.road_inputs, {"board_base": str(self.state / "coordination/ns2604-coop/readiness-20261005/jobs/BOARD-CLOSE-20261007T190934Z/board-close-20261007T193821Z.json"), "handbook_commit": "fixture-only"})
        self.current_path = self.state / "coordination/command-center/pages/cc-now.json"
        self.current = {"schema": "cc-now/1", "updated_utc": "2024-07-08T09:10:00Z", "timezone_for_display": "America/New_York", "headline": "Fixture current headline", "readiness": {"start_gates_met": 4, "start_gates_total": 5, "estimate_percent": 75, "basis": "Authored fixture estimate"}, "gates": [{"id": "G-test", "state": "MET", "what": "Current test receipt", "blocks_start": True}, {"id": "G-other", "state": "OPEN", "what": "Optional fixture task", "blocks_start": False}], "next_events": [{"utc": "2024-07-09T13:15:00Z", "what": "Summer fixture event"}, {"utc": "2024-12-09T13:15:00Z", "what": "Winter fixture event"}], "waiting_on_owner": [{"what": "Review a source", "by_utc": "2024-07-09T18:00:00Z"}], "workstation": {"windows_available_gib": 17.4, "wsl_available_gib": 70.7, "swap_used_gib": 0, "read_utc": "2024-07-08T08:00:00Z"}}
        self.write_json(self.current_path, self.current)
        self.workstation_result = {key: {"value_gib": self.current["workstation"][key], "source": "cc-now fallback", "read_utc": self.current["workstation"]["read_utc"]} for key in ("windows_available_gib", "wsl_available_gib", "swap_used_gib")}
        self.workstation_result["API_errors"] = []
        self.workstation_patch = patch.object(BUILDER, "collect_workstation", return_value=self.workstation_result)
        self.workstation_patch.start()
        self.addCleanup(self.workstation_patch.stop)
        policy = json.loads((ROOT / "tools/local-pages/source_policy.json").read_text())
        policy["sources"] = {name: [dict(record)] for name, record in sources.items()}
        policy["source_index"] = [{"root": "repo", "path": "tools/north-star/sources.json"}, {"root": "repo", "path": "tools/north-star/source-override.json"}]
        self.policy_path = self.base / "approved-source-policy.json"
        self.write_json(self.policy_path, policy)
        self.policy_patch = patch.object(BUILDER, "SOURCE_POLICY_PATH", self.policy_path)
        self.policy_patch.start()
        self.addCleanup(self.policy_patch.stop)
        self.fleet_result = {"schema": "local-fleet/1", "at": "2024-07-08T09:00:00Z", "fleet_source": "fixture native", "lanes_live": [{"lane": "fixture-lane", "status": "active", "tier": "standard", "cli_version": "0.161.0", "subagents_running": 0, "subagent_uncached_share_pct": None}], "lanes_parked": [{"lane": "fixture-parked", "tier": "standard", "cli_version": None}], "claude_sessions": [], "claude_subagents_running": {}, "exec_reads_in_flight": None, "sdk": {"status": "no spend yet", "jobs_running": None, "spend_usd": 0, "ceiling_usd": None, "read_utc": "2024-07-08T09:00:00Z"}, "actions": {"runs": [], "scope": "fixture only", "read_utc": "2024-07-08T09:00:00Z"}, "pool_accounts": [{"account": "reset 01:00Z", "used_pct": 0}], "fresh_total_pct": 0, "tiers": {}, "source_times": {"fleet_direct": "2024-07-08T09:00:00Z"}, "API_errors": []}
        self.fleet_patch = patch.object(BUILDER, "collect_fleet", return_value=self.fleet_result)
        self.fleet_patch.start()
        self.addCleanup(self.fleet_patch.stop)
        self.adoption_path = self.state / "coordination/command-center/pages/adoption-now.json"
        self.adoption = {"schema": "adoption-now/1", "generated_utc": "2024-07-08T09:00:00Z", "window_hours": 24, "method": "fixture count of record", "claude_total_sessions": 0, "codex_total_conversations": 0, "layers": {}, "claude_by_role": {}, "codex_by_lane": {}}
        self.write_json(self.adoption_path, self.adoption)

    @staticmethod
    def write_json(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False) + "\n")

    def refresh(self, **kwargs: object) -> dict:
        return BUILDER.refresh(self.root, self.state, self.output, self.receipt, refreshed="2030-01-02T03:04:05Z", **kwargs)

    def generated_bytes(self) -> dict[str, bytes]:
        return {path.relative_to(self.output).as_posix(): path.read_bytes() for path in self.output.rglob("*") if path.is_file()}

    def test_reference_keys_cannot_select_unapproved_files(self) -> None:
        for relative in ("credentials.json", "client-secret.json", ".env.json", "coordination/e2e-truth-20261006/capture.json", "unrelated/public.json"):
            with self.subTest(relative=relative):
                forbidden = self.state / relative
                self.write_json(forbidden, {"updated_utc": "2024-08-01T00:00:00Z", "value": "SYNTHETIC-NOT-FOR-PUBLICATION"})
                self.write_json(self.road_inputs, {"board_base": str(forbidden)})
                original = BUILDER.snapshot
                attempts = []
                def guarded(path):
                    if Path(path) == forbidden:
                        attempts.append(path)
                        raise AssertionError("unapproved roadmap source opened")
                    return original(path)
                with patch.object(BUILDER, "snapshot", side_effect=guarded):
                    receipt = self.refresh()
                self.assertEqual(attempts, [])
                self.assertEqual(receipt["inputs"]["roadmap:board_base"]["status"], "OMITTED")

    def test_native_html_and_every_page_string_are_portable(self) -> None:
        private = "/".join(("", "home", "synthetic-private-user", "private-data"))
        account = "https://chatgpt.com/c/synthetic-account"
        gate = json.loads(self.gate.read_text())
        gate["owner"] = private
        gate["state"] = "source with " + account
        self.write_json(self.gate, gate)
        self.current["headline"] = private
        self.gaps["gaps"][0]["title"] = private
        self.roadmap["servers"][0]["job"] = private
        self.write_json(self.current_path, self.current)
        self.write_json(self.gaps_path, self.gaps)
        self.write_json(self.road_path, self.roadmap)
        self.refresh()
        for name in ("index", "readiness", "gaps", "roadmap", "sources"):
            html = (self.output / (name + ".html")).read_text()
            self.assertNotIn(private, html)
            self.assertNotIn(account, html)
        self.assertIn("${USER_HOME}", (self.output / "readiness.html").read_text())

    def test_milestone_times_and_reset_match_documented_controls(self) -> None:
        self.refresh()
        road = (self.output / "roadmap.html").read_text()
        self.assertIn("04:09:00 EDT", road)
        self.assertLess(road.index("04:09:00 EDT"), road.index("08:09:00 UTC"))
        gaps = (self.output / "gaps.html").read_text()
        self.assertIn('id="gap-reset"', gaps)
        self.assertIn("Reset filters", gaps)

    def test_cli_attribute_error_is_finite(self) -> None:
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(BUILDER, "refresh", side_effect=AttributeError("synthetic malformed field")), redirect_stdout(stdout), redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as caught:
                BUILDER.main([])
        self.assertEqual(caught.exception.code, 1)
        self.assertIn("AttributeError", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_source_date_lists_are_kept_on_sources_page(self) -> None:
        self.refresh()
        sources = (self.output / "sources.html").read_text()
        self.assertIn("checked_at = 2024-03-04T05:06:07Z", sources)
        for name in ("index", "readiness", "gaps", "roadmap"):
            self.assertNotIn("checked_at = 2024-03-04T05:06:07Z", (self.output / (name + ".html")).read_text())

    def test_approved_roadmap_reference_dates_render_on_sources(self) -> None:
        target = self.state / "coordination/ns2604-coop/readiness-20261005/jobs/BOARD-CLOSE-20261007T190934Z/board-close-20261007T193821Z.json"
        self.write_json(target, {"updated_utc": "2024-08-09T10:11:12Z"})
        self.refresh()
        html = (self.output / "sources.html").read_text()
        self.assertIn("updated_utc = 2024-08-09T10:11:12Z", html)

    def test_raw_receipt_paths_are_not_replaced_by_portable_placeholders(self) -> None:
        segment = "-".join(("11111111", "2222", "3333", "4444", "555555555555"))
        path = self.state / segment / "gate.json"
        self.write_json(path, json.loads(self.gate.read_text()))
        self.source_spec["sources"]["gate"]["path"] = path.relative_to(self.state).as_posix()
        self.write_json(self.source_index, self.source_spec)
        policy = json.loads(self.policy_path.read_text())
        policy["sources"]["gate"] = [dict(self.source_spec["sources"]["gate"])]
        self.write_json(self.policy_path, policy)
        result = self.refresh()
        self.assertEqual(result["inputs"]["readiness:gate"]["path"], str(path))
        self.assertIn("${LOCAL_SESSION_ID}", (self.output / "sources.html").read_text())
        self.assertNotIn(segment, (self.output / "sources.html").read_text())

    def test_override_flags_refuse_files_outside_source_roots_before_read(self) -> None:
        outside = self.base / "outside/unrelated.json"
        self.write_json(outside, {"value": "synthetic outside source"})
        for keyword in ("gaps_source", "roadmap_source", "roadmap_inputs", "current_source"):
            with self.subTest(keyword=keyword):
                original = BUILDER.snapshot
                attempts = []
                def guarded(path):
                    if Path(path) == outside:
                        attempts.append(path)
                        raise AssertionError("outside override opened")
                    return original(path)
                with patch.object(BUILDER, "snapshot", side_effect=guarded), self.assertRaises(ValueError):
                    self.refresh(**{keyword: outside})
                self.assertEqual(attempts, [])

    def test_all_override_roles_refuse_protected_and_unapproved_files_on_actual_opens(self) -> None:
        relative_paths = ("coordination/e2e-truth-20261006/synthetic-capture.json", "credentials/client-secret.env", ".env", "environment.json", "client-secret.json", "unrelated/public.json")
        for keyword in ("gaps_source", "roadmap_source", "roadmap_inputs", "current_source"):
            for source_root in (self.root, self.state):
                for relative in relative_paths:
                    with self.subTest(keyword=keyword, root=source_root.name, relative=relative):
                        target = source_root / relative
                        self.write_json(target, {"value": "synthetic unapproved projection"})
                        attempts = []
                        original_builtin, original_io, original_os = builtins.open, io.open, os.open
                        def guard(original):
                            def checked(path, *args, **kwargs):
                                if not isinstance(path, int) and Path(path) == target:
                                    attempts.append(path)
                                    raise AssertionError("protected override reached a real file-open boundary")
                                return original(path, *args, **kwargs)
                            return checked
                        with patch.object(builtins, "open", side_effect=guard(original_builtin)), patch.object(io, "open", side_effect=guard(original_io)), patch.object(os, "open", side_effect=guard(original_os)), self.assertRaises(ValueError):
                            self.refresh(**{keyword: target})
                        self.assertEqual(attempts, [])
                        self.assertFalse(self.receipt.exists())

    def test_newer_native_observation_only_differs_from_current_view(self) -> None:
        gate = json.loads(self.gate.read_text())
        gate["updated_utc"] = "2024-12-01T00:00:00Z"
        self.write_json(self.gate, gate)
        self.refresh()
        html = (self.output / "readiness.html").read_text()
        self.assertNotIn("superseded in the current view", html)
        self.assertIn("differs from the current view", html)

    def test_missing_or_partial_adoption_degrades_without_aborting_pages(self) -> None:
        self.refresh()
        adoption_path = self.state / "coordination/command-center/pages/adoption-now.json"
        for content in (None, '{"schema":'):
            with self.subTest(content=content):
                if content is None:
                    adoption_path.unlink(missing_ok=True)
                else:
                    adoption_path.write_text(content)
                result = self.refresh()
                self.assertEqual(result["adoption"]["status"], "UNREPORTED")
                html = (self.output / "readiness.html").read_text()
                self.assertIn("Adoption", html)
                self.assertIn("UNKNOWN", html)
                self.assertNotIn("0 Claude sessions", html)
                self.assertTrue((self.output / "fleet.html").is_file())

    def test_failed_fleet_adapter_preserves_all_pages_with_unknown_observations(self) -> None:
        for failure in (OverflowError("fixture timestamp"), AttributeError("fixture memfd"), RecursionError("fixture structure")):
            with self.subTest(failure=type(failure).__name__), patch.object(BUILDER, "collect_fleet", side_effect=failure):
                result = self.refresh()
                self.assertEqual(result["fleet"]["fleet_source"], "not reported")
                for name in ("index", "readiness", "gaps", "roadmap", "fleet", "sources"):
                    self.assertTrue((self.output / (name + ".html")).is_file())
                html = (self.output / "fleet.html").read_text()
                self.assertIn("UNKNOWN</strong> live Codex lanes", html)
                self.assertIn(type(failure).__name__, html)

    def test_fleet_source_notes_render_reported_actions_cache_ttl(self) -> None:
        for seconds in (540, 731):
            with self.subTest(seconds=seconds):
                self.fleet_result["actions"]["cache_ttl_seconds"] = seconds
                self.refresh()
                text = (self.output / "sources.html").read_text()
                self.assertIn(f"reported TTL of {seconds} seconds", text)
                self.assertNotIn("ten-minute nonserved cache", text)
        self.fleet_result["actions"].pop("cache_ttl_seconds")
        self.refresh()
        self.assertIn("reported TTL of UNKNOWN seconds", (self.output / "sources.html").read_text())

    def test_short_home_names_preserve_native_readiness_fragment_html(self) -> None:
        for name in ("li", "link", "section"):
            with self.subTest(name=name), patch.object(Path, "home", return_value=self.base / name):
                self.refresh()
                text = (self.output / "readiness.html").read_text()
                self.assertIn('<section class="manifest-section"', text)
                self.assertIn("</section>", text)
                self.assertNotIn("<[personal identifier omitted]", text)

    def test_architecture_failure_refreshes_other_pages_and_preserves_previous_page(self) -> None:
        self.refresh()
        architecture = self.output / "architecture.html"
        architecture.write_bytes(b"previous Architecture publication")
        (self.state / "coordination/ns2604-coop/notes/adoption-evidence-20261008").mkdir(parents=True)
        original = BUILDER.load_local
        for failure in (ValueError("synthetic protected input"), OSError("synthetic source unavailable")):
            with self.subTest(failure=type(failure).__name__):
                adapter = mock.Mock()
                adapter.refresh_if_changed.side_effect = failure
                with patch.object(BUILDER, "load_local", side_effect=lambda name: adapter if name == "architecture_builder" else original(name)):
                    result = self.refresh()
                self.assertEqual(result["architecture"]["status"], "UNREPORTED")
                self.assertEqual(architecture.read_bytes(), b"previous Architecture publication")
                for name in ("index", "readiness", "gaps", "roadmap", "fleet", "sources"):
                    self.assertTrue((self.output / (name + ".html")).is_file())
                self.assertIn(type(failure).__name__, result["architecture"]["reason"])
                self.assertNotIn("synthetic protected input", json.dumps(result["architecture"]))

    def test_first_architecture_failure_publishes_explicit_unreported_page(self) -> None:
        (self.state / "coordination/ns2604-coop/notes/adoption-evidence-20261008").mkdir(parents=True)
        original = BUILDER.load_local
        adapter = mock.Mock()
        adapter.refresh_if_changed.side_effect = ValueError("controlled input refusal")
        with patch.object(BUILDER, "load_local", side_effect=lambda name: adapter if name == "architecture_builder" else original(name)):
            result = self.refresh()
        page = (self.output / "architecture.html").read_text()
        self.assertIn("UNREPORTED", page)
        self.assertNotIn("controlled input refusal", page)
        self.assertEqual(result["architecture"]["status"], "UNREPORTED")
        self.assertIn("architecture.html", result["outputs"])

    def real_fleet_adapter(self, state, cache, root):
        def native_transport(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, stdout="[]" if command[0] == "gh" else "", stderr="")
        return BUILDER.load_local("fleet_data").collect(state, cache, root, run=native_transport)

    def test_real_fleet_adapter_rejects_snapshot_symlink_before_publication(self) -> None:
        producer = self.state / "coordination/ns2604-coop/tools/fleet_block.py"
        producer.parent.mkdir(parents=True, exist_ok=True)
        producer.write_text("# synthetic producer transport fixture\n")
        outside = self.base / "outside/credentials.json"
        self.write_json(outside, {"schema": "coop-fleet/1", "at": "2024-07-08T00:00:00Z", "lanes_live": [{"lane": "outside-read-sentinel", "tier": "standard"}], "lanes_parked": [], "claude_sessions": []})
        source = self.state / "coordination/ns2604-coop/watchers/fleet-now.json"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.symlink_to(outside)
        with patch.object(BUILDER, "collect_fleet", side_effect=self.real_fleet_adapter):
            result = self.refresh()
        html = (self.output / "fleet.html").read_text()
        self.assertNotIn("outside-read-sentinel", html)
        self.assertIn("UNKNOWN", html)
        observed = next(row for row in result["fleet"]["source_inputs"] if row["path"] == str(source))
        self.assertEqual(observed["status"], "unavailable")
        self.assertIsNone(observed.get("sha256"))

    def test_real_fleet_adapter_does_not_overwrite_cache_temp_symlink(self) -> None:
        producer = self.state / "coordination/ns2604-coop/tools/fleet_block.py"
        producer.parent.mkdir(parents=True, exist_ok=True)
        producer.write_text("# synthetic producer transport fixture\n")
        cache = self.receipt.parent / "fleet/cache"
        cache.mkdir(parents=True, exist_ok=True)
        outside = self.base / "outside/private-cache-target.json"
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_text("synthetic cache target must remain unchanged")
        (cache / "fleet-actions.json.tmp").symlink_to(outside)
        with patch.object(BUILDER, "collect_fleet", side_effect=self.real_fleet_adapter):
            self.refresh()
        self.assertEqual(outside.read_text(), "synthetic cache target must remain unchanged")
        self.assertTrue((self.output / "fleet.html").is_file())

    def test_full_generated_fleet_masks_private_labels_after_counting(self) -> None:
        home = self.base / "synthetic-host-user"
        labels = ["file:" + "/".join(("", "home", home.name, "private")), "worker-" + home.name]
        for label in labels:
            with self.subTest(label=label):
                self.fleet_result.update(fleet_source="direct native", lanes_live=[{"lane": label, "tier": "standard", "status": "active", "subagents_spawned": 0, "subagents_running": 0}], lanes_parked=[], claude_sessions=[])
                with patch.object(Path, "home", return_value=home):
                    result = self.refresh()
                html = (self.output / "fleet.html").read_text()
                self.assertNotIn(label, html)
                self.assertNotIn(home.name, html)
                self.assertIn('<strong>1</strong> live Codex lanes', html)
                self.assertEqual(result["fleet"]["lanes_live"][0]["lane"], label)

    def test_real_composer_masks_underscore_identity_in_fleet_and_adoption_after_grouping(self) -> None:
        home = self.base / "synthetic-host-user"
        label = "worker_" + home.name + "_read"
        self.write_json(self.state / "coordination/ns2604-coop/watchers/fleet-now.json", {"schema": "coop-fleet/1", "at": "2024-07-08T09:00:00Z", "lanes_live": [{"lane": label, "tier": "standard", "status": "active", "subagents_running": 0}], "lanes_parked": [], "claude_sessions": []})
        self.adoption["layers"] = {label: {"servers": {"context-mode": {"claude_calls": 3, "claude_sessions": 1, "codex_calls": 17, "codex_conversations": 3}}}}
        self.adoption["codex_by_role"] = {label: {"conversations": 3, "servers": {"context-mode": {"calls": 17, "conversations": 3}}}}
        self.write_json(self.adoption_path, self.adoption)
        with patch.object(Path, "home", return_value=home), patch.object(BUILDER, "collect_fleet", side_effect=self.real_fleet_adapter):
            result = self.refresh()
        for name in ("index", "readiness", "gaps", "roadmap", "fleet", "sources"):
            html = (self.output / (name + ".html")).read_text()
            self.assertNotIn(home.name.casefold(), html.casefold())
        fleet_html = (self.output / "fleet.html").read_text()
        self.assertIn('<strong>1</strong> live Codex lanes', fleet_html)
        self.assertIn("<td>17</td>", fleet_html)
        self.assertEqual(result["fleet"]["lanes_live"][0]["lane"], label)
        self.assertEqual(json.loads(self.adoption_path.read_text())["codex_by_role"][label]["servers"]["context-mode"]["calls"], 17)

    def test_real_composer_applies_identity_policy_to_classified_decoded_tokens(self) -> None:
        home = self.base / "synthetic-host-user"
        raw = "worker_" + home.name + "_read"
        encoded = ["".join("%" + format(ord(char), "02x") for char in raw), "".join("&#" + str(ord(char)) + ";" for char in raw), "".join("\\u" + format(ord(char), "04x") for char in raw), raw.encode().hex(), base64.b64encode(raw.encode()).decode()]
        for label in encoded:
            with self.subTest(label=label):
                self.current["headline"] = label
                self.write_json(self.current_path, self.current)
                with patch.object(Path, "home", return_value=home):
                    self.refresh()
                for name in ("index", "readiness", "gaps", "roadmap", "fleet", "sources"):
                    html = (self.output / (name + ".html")).read_text()
                    self.assertNotIn(label, html)
                    self.assertNotIn(home.name.casefold(), html.casefold())
                self.assertIn("[personal identifier omitted]", (self.output / "index.html").read_text())

    def test_full_documents_native_digest_and_local_resources(self) -> None:
        source_bytes = {path: path.read_bytes() for path in (self.source_index, self.gate, self.gaps_path, self.road_path, self.current_path)}
        receipt = self.refresh()
        native, _ = BUILDER.load_native(self.root)
        expected = hashlib.sha256(native.render(native.build(self.root, self.state, self.source_index))).hexdigest()
        self.assertEqual(receipt["native_readiness_manifest_sha256"], expected)
        self.assertEqual(json.loads(self.receipt.read_text()), receipt)
        self.assertEqual(len(receipt["outputs"]), 8)
        for name in ("index", "readiness", "gaps", "roadmap", "fleet", "sources"):
            text = (self.output / (name + ".html")).read_text()
            audit = DocumentAudit()
            audit.feed(text)
            self.assertTrue(audit.doctype)
            self.assertIn("head", audit.tags)
            self.assertIn("body", audit.tags)
            self.assertTrue(any(attributes.get("lang") == "en" for attributes in audit.attributes))
            self.assertTrue(any(attributes.get("id") == "main-content" for attributes in audit.attributes))
            self.assertTrue(any(attributes.get("aria-label") == "Local pages" for attributes in audit.attributes))
            self.assertIn(expected, text)
            self.assertIn("2030-01-02T03:04:05Z", text)
            for attributes in audit.attributes:
                self.assertFalse(any(key.startswith("on") for key in attributes))
                for key in ("src", "href"):
                    if key in attributes:
                        self.assertNotRegex(attributes[key], r"^(https?:|//|javascript:|data:|file:)")
        self.assertEqual(source_bytes, {path: path.read_bytes() for path in source_bytes})
        self.assertFalse(any("receipt" in name for name in self.generated_bytes()))
        self.assertEqual(receipt["inputs"]["gaps"]["sha256"], hashlib.sha256(self.gaps_path.read_bytes()).hexdigest())
        self.assertEqual(receipt["inputs"]["roadmap:board_base"]["status"], "UNAVAILABLE")

    def test_source_dates_and_event_dates_keep_distinct_scope(self) -> None:
        self.refresh()
        gap = (self.output / "gaps.html").read_text()
        readiness = (self.output / "readiness.html").read_text()
        sources = (self.output / "sources.html").read_text()
        roadmap = (self.output / "roadmap.html").read_text()
        self.assertIn("snapshot as of 2024-05-06T07:08Z", gap)
        self.assertIn("updated_utc = 2024-05-06T07:08Z", sources)
        self.assertIn("updated_utc = 2024-04-05T06:07:08Z", sources)
        self.assertIn("checked_at = 2024-03-04T05:06:07Z", sources)
        self.assertNotIn('<ul class="source-list">', readiness)
        self.assertIn("Source-owned snapshot date unspecified", roadmap)
        self.assertIn("file metadata, not event or acceptance time", sources)
        self.assertIn("2024-06-07T08:09:00Z", roadmap)
        self.assertEqual(roadmap.count('class="evidence-footnote"'), 1)
        self.assertNotIn("Passing a date does not record completion", roadmap)

    def test_current_view_precedes_dated_manifest_without_mutating_sources(self) -> None:
        original = self.current_path.read_bytes()
        receipt = self.refresh()
        text = (self.output / "readiness.html").read_text()
        self.assertLess(text.index('id="now-view"'), text.index('id="manifest-title"'))
        self.assertIn("4 of 5 START gates met", text)
        self.assertIn("CC estimate 75%", text)
        self.assertIn("Authored fixture estimate", text)
        self.assertIn("command-center current view", text)
        self.assertIn("retained pending measurement", text)
        self.assertIn("superseded in the current view", text)
        self.assertEqual(self.current_path.read_bytes(), original)
        self.assertEqual(receipt["command_center_current_view"]["sha256"], hashlib.sha256(original).hexdigest())
        for name in ("index", "readiness"):
            html = (self.output / (name + ".html")).read_text()
            self.assertLess(html.index('data-gate="G-test"'), html.index('data-gate="G-other"'))
            self.assertEqual(html.count('class="evidence-footnote"'), 1)

    def test_current_view_times_keep_new_york_first_and_exact_utc(self) -> None:
        self.refresh()
        text = (self.output / "readiness.html").read_text()
        self.assertLess(text.index("Jul 09, 09:15:00 EDT"), text.index("Jul 09, 13:15:00 UTC"))
        self.assertLess(text.index("Dec 09, 08:15:00 EST"), text.index("Dec 09, 13:15:00 UTC"))
        self.assertIn("2024-07-08T08:00:00Z", text)
        self.assertIn("cc-now fallback", text)

    def test_small_live_swap_is_visible_instead_of_rounded_to_zero(self) -> None:
        self.workstation_result["swap_used_gib"].update(value_gib=.003265380859, source="prometheus", read_utc="2024-07-08T09:00:00Z")
        self.refresh()
        text = (self.output / "readiness.html").read_text()
        self.assertIn("<strong>3.3</strong> MiB", text)
        self.assertIn("prometheus · metric read", text)
        self.assertIn('datetime="2024-07-08T09:00:00Z"', text)

    def test_full_refresh_invalid_optional_total_is_unknown_and_still_publishes(self) -> None:
        collector = BUILDER.load_local("workstation")
        for field in ("windows_total_gib", "wsl_total_gib"):
            for value in [None, -1, 0, "32", False,
                          {"value_gib": 128, "read_utc": "2024-07-08T08:00:00"}]:
                with self.subTest(field=field, value=value):
                    self.current["workstation"][field] = value
                    self.write_json(self.current_path, self.current)
                    def observed(fallback):
                        return collector.collect(fallback, lambda *args, **kwargs: {"status": "success", "data": {"resultType": "matrix", "result": []}})
                    with patch.object(BUILDER, "collect_workstation", side_effect=observed):
                        result = self.refresh()
                    self.assertEqual(len(result["outputs"]), 8)
                    self.assertNotIn(field, result["workstation"])
                    self.assertEqual(result["workstation"]["optional_total_status"][field]["status"], "UNKNOWN")
                    text = (self.output / "readiness.html").read_text()
                    self.assertIn("total unknown", text)
                    self.assertIn("<strong>17.4</strong> GiB", text)
                    self.assertNotIn('class="memory-total"', text)
            self.current["workstation"].pop(field)

    def test_full_refresh_optional_total_dictionary_preserves_its_own_date(self) -> None:
        collector = BUILDER.load_local("workstation")
        recorded = "2024-07-08T07:30:00Z"
        self.current["workstation"]["windows_total_gib"] = {"value_gib": 32, "read_utc": recorded}
        self.write_json(self.current_path, self.current)
        with patch.object(BUILDER, "collect_workstation", side_effect=lambda fallback: collector.collect(fallback, lambda *args, **kwargs: {"status": "success", "data": {"resultType": "matrix", "result": []}})):
            result = self.refresh()
        reading = result["workstation"]["windows_total_gib"]
        self.assertEqual(reading["value_gib"], 32)
        self.assertEqual(reading["read_utc"], recorded)
        text = (self.output / "readiness.html").read_text()
        self.assertIn("32.0 GiB total", text)
        self.assertIn('datetime="' + recorded + '"', text)
        self.assertNotIn("total unknown", text)

    def test_adoption_snapshot_is_read_only_and_follows_operator_summary(self) -> None:
        source_bytes = self.adoption_path.read_bytes()
        receipt = self.refresh()
        ready = (self.output / "readiness.html").read_text()
        fleet = (self.output / "fleet.html").read_text()
        self.assertLess(ready.index('id="now-view"'), ready.index('id="adoption"'))
        self.assertLess(fleet.index('id="fleet-view"'), fleet.index('id="adoption-by-role"'))
        self.assertEqual(self.adoption_path.read_bytes(), source_bytes)
        self.assertEqual(receipt["adoption"]["sha256"], hashlib.sha256(source_bytes).hexdigest())

    def test_native_orchestration_keeps_owner_role_and_unattributed_counts(self) -> None:
        projection = {"document": self.adoption, "window": {}, "sources": [], "source_errors": [], "instances": {"role_map": {"fixture-instance": None}}, "orchestration": {"claude_by_role": {"native-agent-stack-1a": {"Agent": 1}}, "codex_by_role": {}, "codex_unattributed": {"spawn_agent": 2}}, "sdk": {"status": "UNREPORTED"}}
        role_module = type("RoleProjection", (), {"project": staticmethod(lambda *unused: projection)})
        original = BUILDER.load_local
        def local(name):
            return role_module if name == "adoption_roles" else original(name)
        registry = self.state / "coordination/ns2604-coop/lanes/hcom-lanes.json"
        self.write_json(registry, {})
        with patch.object(BUILDER, "load_local", side_effect=local):
            self.refresh()
        text = (self.output / "fleet.html").read_text()
        self.assertIn("owner session (reports to CC)", text)
        self.assertNotIn("native-agent-stack-1a", text)
        self.assertIn("unattributed instances", text)
        self.assertIn("spawn_agent", text)
        self.assertIn("SDK client observations", text)

    def test_cc_current_schema_failure_preserves_last_successful_render(self) -> None:
        self.refresh()
        old = self.generated_bytes()
        old_receipt = self.receipt.read_bytes()
        self.current["schema"] = "cc-now/unsupported"
        self.write_json(self.current_path, self.current)
        with self.assertRaises(ValueError):
            self.refresh()
        self.assertEqual(self.generated_bytes(), old)
        self.assertEqual(self.receipt.read_bytes(), old_receipt)

    def test_current_links_allow_https_and_reject_executable_urls(self) -> None:
        self.current["waiting_on_owner"] = [{"what": "Allowed external source", "link": "https://example.org/document", "by_utc": "2024-07-09T18:00:00Z"}, {"what": "Unsafe URL remains text", "link": "javascript:alert(1)"}]
        self.write_json(self.current_path, self.current)
        self.refresh()
        text = (self.output / "readiness.html").read_text()
        self.assertIn('href="https://example.org/document"', text)
        self.assertNotIn("javascript:", text)
        self.assertIn("Unsafe URL remains text", text)

    def test_fleet_links_every_worker_and_distinguishes_unknown_from_zero(self) -> None:
        receipt = self.refresh()
        fleet = (self.output / "fleet.html").read_text()
        for name in ("fixture-lane", "fixture-parked"):
            self.assertIn(name, fleet)
        self.assertIn("no spend yet", fleet)
        self.assertIn("not reported", fleet)
        self.assertIn("0% used", fleet)
        self.assertEqual(fleet.count('class="evidence-footnote"'), 1)
        self.assertIn('href="fleet.html"', (self.output / "index.html").read_text())
        self.assertIn('id="fleet"', (self.output / "sources.html").read_text())
        self.assertEqual(receipt["fleet"]["lanes_live"], self.fleet_result["lanes_live"])

    def test_partial_fleet_observation_does_not_claim_zero_workers(self) -> None:
        for source in (None, "", "not reported"):
            with self.subTest(source=source):
                self.fleet_result.update(fleet_source=source, at=None, lanes_live=[], lanes_parked=[], claude_sessions=[])
                self.refresh()
                text = (self.output / "fleet.html").read_text()
                self.assertNotIn('<strong>0</strong> live Codex lanes', text)
                self.assertNotIn('<strong>0</strong> Claude worker sessions', text)
                self.assertIn('<strong>UNKNOWN</strong> live Codex lanes', text)
                self.assertNotIn('datetime=""', text)

    def test_owner_claude_session_is_named_by_role_and_excluded_from_workers(self) -> None:
        self.fleet_result["claude_sessions"] = [{"name": "native-agent-stack-1a", "status": "idle"}, {"name": "fixture-worker", "status": "busy"}]
        self.refresh()
        text = (self.output / "fleet.html").read_text()
        self.assertIn("owner session (reports to CC)", text)
        self.assertIn('<strong>1</strong> Claude worker sessions + 1 owner session', text)
        self.assertNotIn("native-agent-stack-1a", text)
        self.assertIn('data-session-role="owner"', text)

    def test_fleet_shows_mapped_values_beside_running_tier_and_version_gaps(self) -> None:
        self.fleet_result["tiers"] = {"default": "default", "fast": ["fixture-lane"], "versions": {"default": "0.162.0", "hold": {}, "hold_until": {}}}
        self.refresh()
        text = (self.output / "fleet.html").read_text()
        self.assertIn("standard / fast", text)
        self.assertIn("0.161.0 / 0.162.0", text)
        self.assertIn("Tier: running / map", text)

    def test_untrusted_text_does_not_create_markup_or_account_links(self) -> None:
        attack = '<img src="https://attacker.invalid/x" onerror="alert(1)">'
        row = self.gaps["gaps"][0]
        row.update(title=attack, group='Measurement" autofocus="true', evidence="https://claude.ai/artifact/private javascript:alert(1)")
        self.write_json(self.gaps_path, self.gaps)
        self.roadmap["milestones"][0]["what"] = attack
        self.write_json(self.road_path, self.roadmap)
        self.refresh()
        for name in ("gaps", "roadmap"):
            text = (self.output / (name + ".html")).read_text()
            audit = DocumentAudit()
            audit.feed(text)
            self.assertNotIn("img", audit.tags)
            self.assertFalse(any("autofocus" in attributes or "onerror" in attributes for attributes in audit.attributes))
            self.assertIn("&lt;img", text)
            self.assertNotIn("https://claude.ai/artifact", text)
        road = (self.output / "roadmap.html").read_text()
        self.assertNotIn("OWNER-DIRECTION-SENTINEL", road)
        self.assertNotIn("RULES-DIRECTION-SENTINEL", road)
        self.assertNotIn("{g_total}", road)
        self.assertNotIn("{g_closed}", road)

    def test_filter_and_theme_contract_is_named_and_source_bound(self) -> None:
        self.refresh()
        text = (self.output / "gaps.html").read_text()
        for identity in ("gap-search", "gap-group", "gap-severity"):
            self.assertIn(f'for="{identity}"', text)
            self.assertIn(f'id="{identity}"', text)
        self.assertIn('data-group="measurement"', text)
        self.assertIn('data-severity="critical"', text)
        self.assertIn('data-search="', text)
        self.assertIn('id="gap-result-count" role="status" aria-live="polite"', text)
        self.assertIn('id="gap-empty" hidden', text)
        self.assertIn('for="theme-toggle"', text)
        for value in ("system", "light", "dark"):
            self.assertIn(f'value="{value}"', text)

    def test_when_only_milestones_preserve_relative_source_labels(self) -> None:
        self.roadmap["milestones"].extend([
            {"when": "After the qualified receipt; time not set", "what": "Relative checkpoint", "state": "pending", "kind": "quiet"},
            {"at": None, "when": "Next custodian review", "what": "Fallback checkpoint", "state": "pending", "kind": "quiet"},
        ])
        self.write_json(self.road_path, self.roadmap)
        self.refresh()
        text = (self.output / "roadmap.html").read_text()
        self.assertIn("After the qualified receipt; time not set", text)
        self.assertIn("Next custodian review", text)
        self.assertIn("2024-06-07T08:09:00Z", text)
        self.assertIn("Relative checkpoint", text)
        self.assertIn("Fallback checkpoint", text)
        self.assertIn("Source-owned snapshot date unspecified", text)

    def test_milestone_without_at_or_when_does_not_publish(self) -> None:
        self.refresh()
        before, receipt = self.generated_bytes(), self.receipt.read_bytes()
        del self.roadmap["milestones"][0]["at"]
        self.write_json(self.road_path, self.roadmap)
        with self.assertRaisesRegex(ValueError, "at or when"):
            self.refresh()
        self.assertEqual(self.generated_bytes(), before)
        self.assertEqual(self.receipt.read_bytes(), receipt)

    def test_successful_refresh_replaces_sources_and_preserves_unrelated_files(self) -> None:
        first = self.refresh()
        (self.output / "custodian-note.txt").write_text("preserve this")
        self.gaps["updated_utc"] = "2025-07-08T09:10Z"
        self.gaps["gaps"][0]["title"] = "Changed retained source"
        self.write_json(self.gaps_path, self.gaps)
        second = self.refresh()
        self.assertNotEqual(first["inputs"]["gaps"]["sha256"], second["inputs"]["gaps"]["sha256"])
        self.assertIn("Changed retained source", (self.output / "gaps.html").read_text())
        self.assertIn("snapshot as of 2025-07-08T09:10Z", (self.output / "gaps.html").read_text())
        self.assertIn("updated_utc = 2025-07-08T09:10Z", (self.output / "sources.html").read_text())
        self.assertEqual((self.output / "custodian-note.txt").read_text(), "preserve this")
        self.assertFalse(list(self.output.rglob(".local-pages-*")))

    def test_source_or_asset_failure_keeps_last_successful_bytes(self) -> None:
        self.refresh()
        before, receipt = self.generated_bytes(), self.receipt.read_bytes()
        self.gaps_path.write_text('{"gaps": NaN}')
        with self.assertRaisesRegex(ValueError, "non-JSON constant"):
            self.refresh()
        self.assertEqual(self.generated_bytes(), before)
        self.assertEqual(self.receipt.read_bytes(), receipt)
        self.write_json(self.gaps_path, self.gaps)
        (self.assets / "site.js").unlink()
        with self.assertRaises(FileNotFoundError):
            self.refresh()
        self.assertEqual(self.generated_bytes(), before)
        self.assertEqual(self.receipt.read_bytes(), receipt)

    def test_receipt_inside_served_root_and_symlink_paths_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside the served root"):
            BUILDER.refresh(self.root, self.state, self.output, self.output / "refresh.json")
        self.assertFalse(self.output.exists())
        target = self.state / "other-gate.json"
        target.write_bytes(self.gate.read_bytes())
        self.gate.unlink()
        self.gate.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.refresh()
        self.assertFalse(self.output.exists())
        alias = self.base / "output-alias"
        self.output.mkdir()
        alias.symlink_to(self.output, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            BUILDER.refresh(self.root, self.state, alias, self.receipt)

    def test_receipt_cannot_overwrite_source_and_output_symlink_is_rejected(self) -> None:
        self.refresh()
        before = self.generated_bytes()
        with self.assertRaisesRegex(ValueError, "overlaps an input"):
            BUILDER.refresh(self.root, self.state, self.output, self.gaps_path)
        self.assertEqual(self.generated_bytes(), before)
        (self.output / "gaps.html").unlink()
        (self.output / "gaps.html").symlink_to(self.gaps_path)
        source = self.gaps_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.refresh()
        self.assertEqual(self.gaps_path.read_bytes(), source)

    def test_native_hash_mismatch_remains_unverified(self) -> None:
        self.source_spec["sources"]["gate"]["expected_sha256"] = "0" * 64
        self.write_json(self.source_index, self.source_spec)
        result = self.refresh()
        page = (self.output / "readiness.html").read_text()
        self.assertIn("UNVERIFIED", page)
        self.assertNotIn("retained pending measurement", page)
        self.assertEqual(result["native_readiness_summary"]["unverified_sources"], 1)

    def test_explicit_source_override_is_native_and_assets_are_composer_relative(self) -> None:
        self.source_spec["gates"][0]["id"] = "G-explicit-override"
        override = self.root / "tools/north-star/source-override.json"
        self.write_json(override, self.source_spec)
        result = self.refresh(sources=override)
        self.assertIn("G-explicit-override", (self.output / "readiness.html").read_text())
        self.assertEqual(result["inputs"]["native_source_index"]["sha256"], hashlib.sha256(override.read_bytes()).hexdigest())
        self.assertEqual((self.output / "assets/site.css").read_bytes(), (self.assets / "site.css").read_bytes())
        self.assertFalse((self.root / "tools/local-pages/assets").exists())

    def test_cli_failure_is_finite_and_does_not_publish(self) -> None:
        self.gaps_path.write_text('{"gaps": [], "gaps": []}')
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr), self.assertRaises(SystemExit) as failure:
            BUILDER.main(["--root", str(self.root), "--state-root", str(self.state), "--output-dir", str(self.output), "--receipt", str(self.receipt)])
        self.assertEqual(failure.exception.code, 1)
        self.assertIn("refresh failed", stderr.getvalue())
        self.assertIn("duplicate JSON key", stderr.getvalue())
        self.assertEqual(stdout.getvalue(), "")
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
