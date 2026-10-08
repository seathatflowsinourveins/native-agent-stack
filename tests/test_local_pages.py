"""Finite, network-independent invariants for the native local page composer."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
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
        self.write_json(self.road_inputs, {"board_base": str(self.state / "unavailable-board.json"), "handbook_commit": "fixture-only"})
        self.current_path = self.state / "coordination/command-center/pages/cc-now.json"
        self.current = {"schema": "cc-now/1", "updated_utc": "2024-07-08T09:10:00Z", "timezone_for_display": "America/New_York", "headline": "Fixture current headline", "readiness": {"start_gates_met": 4, "start_gates_total": 5, "estimate_percent": 75, "basis": "Authored fixture estimate"}, "gates": [{"id": "G-test", "state": "MET", "what": "Current test receipt", "blocks_start": True}, {"id": "G-other", "state": "OPEN", "what": "Optional fixture task", "blocks_start": False}], "next_events": [{"utc": "2024-07-09T13:15:00Z", "what": "Summer fixture event"}, {"utc": "2024-12-09T13:15:00Z", "what": "Winter fixture event"}], "waiting_on_owner": [{"what": "Review a source", "by_utc": "2024-07-09T18:00:00Z"}], "workstation": {"windows_available_gib": 17.4, "wsl_available_gib": 70.7, "swap_used_gib": 0, "read_utc": "2024-07-08T08:00:00Z"}}
        self.write_json(self.current_path, self.current)
        self.workstation_result = {key: {"value_gib": self.current["workstation"][key], "source": "cc-now fallback", "read_utc": self.current["workstation"]["read_utc"]} for key in ("windows_available_gib", "wsl_available_gib", "swap_used_gib")}
        self.workstation_result["API_errors"] = []
        self.workstation_patch = patch.object(BUILDER, "collect_workstation", return_value=self.workstation_result)
        self.workstation_patch.start()
        self.addCleanup(self.workstation_patch.stop)

    @staticmethod
    def write_json(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False) + "\n")

    def refresh(self, **kwargs: object) -> dict:
        return BUILDER.refresh(self.root, self.state, self.output, self.receipt, refreshed="2030-01-02T03:04:05Z", **kwargs)

    def generated_bytes(self) -> dict[str, bytes]:
        return {path.relative_to(self.output).as_posix(): path.read_bytes() for path in self.output.rglob("*") if path.is_file()}

    def test_full_documents_native_digest_and_local_resources(self) -> None:
        source_bytes = {path: path.read_bytes() for path in (self.source_index, self.gate, self.gaps_path, self.road_path, self.current_path)}
        receipt = self.refresh()
        native, _ = BUILDER.load_native(self.root)
        expected = hashlib.sha256(native.render(native.build(self.root, self.state, self.source_index))).hexdigest()
        self.assertEqual(receipt["native_readiness_manifest_sha256"], expected)
        self.assertEqual(json.loads(self.receipt.read_text()), receipt)
        self.assertEqual(len(receipt["outputs"]), 7)
        for name in ("index", "readiness", "gaps", "roadmap", "sources"):
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
        self.assertIn("updated_utc = 2024-05-06T07:08Z", gap)
        self.assertIn("updated_utc = 2024-04-05T06:07:08Z", sources)
        self.assertIn("checked_at = 2024-03-04T05:06:07Z", sources)
        self.assertNotIn('<ul class="source-list">', readiness)
        self.assertIn("Source-owned snapshot date unspecified", roadmap)
        self.assertIn("file metadata, not event or acceptance time", roadmap)
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
        self.assertIn("updated_utc = 2025-07-08T09:10Z", (self.output / "gaps.html").read_text())
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
