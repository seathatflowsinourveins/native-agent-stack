"""Local integration tests for tools/sota-convergence/blind_checkout.py.

These are local integration tests, not upstream E2E: each test builds a
tiny fixture git repository in a temp dir (``git init`` + a real commit) and
runs the real ``git worktree add``/``git worktree remove`` commands against
it, but the fixture content, taxonomy and every catalog/blueprint shape are
synthetic, not a real repository checkout.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = ROOT / "tools" / "sota-convergence"


def load_module(name, filename):
    path = TOOL_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


blind_checkout = load_module("blind_checkout", "blind_checkout.py")


def git(args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def ledger_row(**overrides):
    row = {
        "catalog": "foundation", "layer_id": "native-clients", "title": "Native clients",
        "requirement": "Run coding tasks.", "current_choice": "Codex", "decision": "retain",
        "rationale": "Native evidence supports it.",
        "evidence_refs": ["docs/x.md"], "limitations": [], "overturn_when": "fixtures/x.json changes",
        "candidates": [
            {"name": "Codex", "repository": "https://github.com/openai/codex", "disposition": "selected",
             "rationale": "Chosen for native execution.", "evidence_kind": "native_execution",
             "evidence_refs": [], "review_status": "confirmed_default"},
            {"name": "Other", "repository": "https://github.com/example/other", "disposition": "conditional",
             "rationale": "Not chosen.", "evidence_kind": "source_review", "evidence_refs": []},
        ],
        "verdict_status": "recorded",
        "winners": [{"component_id": "codex", "repository": "https://github.com/openai/codex", "pin": "1.0",
                    "evidence_class": "native_proven", "why_selected": "Native execution evidence.",
                    "evidence_refs": [], "recipe_ref": "catalogs/landscape/foundation.json",
                    "platform_status": {"linux-wsl2-x86_64": "accepted", "macos-arm64": "untested"}}],
        "alternatives": [{"name": "Other", "repository": "https://github.com/example/other",
                          "disposition": "conditional", "why_not_default": "Not the default.",
                          "evidence_class": "source_review", "source": "lane:claude"}],
        "verdict_overturn_when": "fixtures/x.json changes and the new candidate passes.",
        # Non-empty in the fixture, since a lane-written value here is exactly what a
        # blind checkout must not leave a prior selection recoverable from.
        "open_gaps": ["codex lane preferred https://github.com/example/other; claude preferred Codex"],
        "overturn_protocol": {"fixture_paths": ["fixtures/x.json"], "metric": "pass/fail",
                              "arms": ["Codex (selected winner)", "https://github.com/example/other"]},
        "lanes": {"claude": {"run_id": "foundation-native-clients-20260922", "sealed_sha256": "a" * 64},
                  "codex": {"run_id": "foundation-native-clients-20260922", "sealed_sha256": "b" * 64},
                  "agreement": "same_winner"},
        "checked_at": "2026-09-22",
    }
    row.update(overrides)
    return row


class BlindCheckoutFixture(unittest.TestCase):
    def setUp(self):
        source_temp = tempfile.TemporaryDirectory()
        self.addCleanup(source_temp.cleanup)
        self.source = Path(source_temp.name).resolve()

        dest_parent = tempfile.TemporaryDirectory()
        self.addCleanup(dest_parent.cleanup)
        self.dest = Path(dest_parent.name).resolve() / "dest"

        git(["init", "-q"], self.source)
        git(["config", "user.email", "test@example.com"], self.source)
        git(["config", "user.name", "Test"], self.source)

        self.write("catalogs/landscape/foundation.json", {
            "schema_version": 2, "checked_at": "2026-09-22", "scope": "Fixture",
            "layers": [ledger_row()],
        })
        self.write("catalogs/landscape/us-equities.json", {
            "schema_version": 2, "checked_at": "2026-09-22", "scope": "Fixture", "layers": [], "domain_rows": [],
        })
        self.write("catalogs/other/decisions.json", {
            "decisions": [{"id": "d1", "review_status": "accepted_within_scope", "selection": "top_20",
                          "nested": {"decision": "retain"}}],
        })
        self.write("blueprints/example/manifest.json", {
            "disposition": "selected_destination",  # a label -> stripped
            "top": "top_20",  # a data value under an unrelated key -> kept
            "selection": "top_20",  # a data value under a stripped-elsewhere key -> kept (not a label)
            "current_choice": "keep NautilusTrader selected for now",  # states a selection -> stripped
            "mapping_rule": {"decision": {"if": "condition", "then": "branch"}},  # a rule structure -> kept
            "nested": {"disposition": "conditional"},  # a label, nested -> stripped
            # Real repository label strings (the closed enum, and free text stating a
            # retain/adopt/reject/defer decision) -> all stripped, each under an actual
            # stripped key name ("decision"/"disposition"/"selection"), nested so each
            # gets its own object.
            "case_adopt": {"decision": "adopt_within_scope"},
            "case_defer": {"decision": "defer"},
            "case_reject": {"disposition": "reject_evidence"},
            "case_retain_prose_1": {"decision": "Retain current catalog pin. No WSL installation or "
                                    "native qualification in this backup lane; scan publication on "
                                    "the already-qualified Mac tool."},
            "case_retain_prose_2": {"decision": "retain installed offline request baseline; reject "
                                    "advanced fields locally"},
            "case_language_alt": {"decision": "language alternative only"},
            "case_retain_selection": {"selection": "Retain the smallest coherent set that meets "
                                      "requirements. Compare challengers against incumbents and "
                                      "preserve rejected/deferred candidates."},
            # A procedural/data string that happens to contain "retain"/"defer" mid-sentence, not
            # as an opening decision verb -> kept (this is a rule, not a selection).
            "case_rule_kept": {"decision": "Submission is deferred by session, not by bar count, so "
                              "an early close cannot pull the order into the decision session."},
        })
        self.write("evidence/artifacts/layer-verdicts-20260922/claude/foundation-native-clients-20260922.json",
                    {"lane": "claude"})
        self.write("catalogs/sota-convergence/layer-verdicts-20260922.json", {"id": "layer-verdicts-20260922"})
        self.write("docs/grand-catalog-handbook.md", "# Handbook\n")
        self.write("docs/ecosystem/index.html", "<html></html>")
        self.write("docs/ecosystem/manifest.json", {"files": []})
        self.write("docs/keep-me.md", "# Keep this one\n")

        git(["add", "-A"], self.source)
        git(["commit", "-q", "-m", "fixture"], self.source)

    def write(self, relative, value):
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, str):
            path.write_text(value, encoding="utf-8")
        else:
            path.write_text(json.dumps(value), encoding="utf-8")

    def run_checkout(self, dest=None):
        return blind_checkout.run_blind_checkout(self.source, "HEAD", dest or self.dest)

    def remove_worktree(self, dest=None):
        git(["worktree", "remove", "--force", str(dest or self.dest)], self.source)


class RemovedFilesTests(BlindCheckoutFixture):
    def test_dated_evidence_and_generated_indexes_are_removed(self):
        manifest = self.run_checkout()
        self.addCleanup(self.remove_worktree)
        self.assertIn("evidence/artifacts/layer-verdicts-20260922/claude/foundation-native-clients-20260922.json",
                      manifest["removed_files"])
        self.assertIn("catalogs/sota-convergence/layer-verdicts-20260922.json", manifest["removed_files"])
        self.assertIn("docs/grand-catalog-handbook.md", manifest["removed_files"])
        self.assertIn("docs/ecosystem/index.html", manifest["removed_files"])
        self.assertIn("docs/ecosystem/manifest.json", manifest["removed_files"])
        self.assertFalse((self.dest / "evidence/artifacts/layer-verdicts-20260922").exists())
        self.assertFalse((self.dest / "catalogs/sota-convergence/layer-verdicts-20260922.json").exists())
        self.assertFalse((self.dest / "docs/grand-catalog-handbook.md").exists())
        self.assertFalse((self.dest / "docs/ecosystem/index.html").exists())
        self.assertFalse((self.dest / "docs/ecosystem/manifest.json").exists())
        # An unrelated docs file is untouched.
        self.assertTrue((self.dest / "docs/keep-me.md").is_file())


class LedgerV2ResetTests(BlindCheckoutFixture):
    def test_v2_verdict_fields_reset_to_pending_and_requirement_kept(self):
        self.run_checkout()
        self.addCleanup(self.remove_worktree)
        document = json.loads((self.dest / "catalogs/landscape/foundation.json").read_text(encoding="utf-8"))
        row = document["layers"][0]
        self.assertEqual(row["verdict_status"], "pending_lanes")
        self.assertEqual(row["winners"], [])
        self.assertEqual(row["alternatives"], [])
        self.assertEqual(row["verdict_overturn_when"], "")
        self.assertEqual(row["lanes"], {"claude": {"run_id": "", "sealed_sha256": ""},
                                        "codex": {"run_id": "", "sealed_sha256": ""}, "agreement": "pending"})
        # open_gaps and overturn_protocol are also lane-written v2 fields (record_verdicts.process_row);
        # a non-empty open_gaps entry or overturn_protocol.arms names the prior winner/disagreement
        # just as directly as winners/alternatives, so both reset to empty too.
        self.assertEqual(row["open_gaps"], [])
        self.assertEqual(row["overturn_protocol"], {"fixture_paths": [], "metric": "", "arms": []})
        # Requirement and evidence are not v2 fields and stay.
        self.assertEqual(row["requirement"], "Run coding tasks.")
        self.assertEqual(row["evidence_refs"], ["docs/x.md"])
        self.assertEqual(row["overturn_when"], "fixtures/x.json changes")
        # The ledger's own schema (a JSON object with a layers list) still loads.
        self.assertEqual(document["schema_version"], 2)
        self.assertIsInstance(document["layers"], list)


class LedgerV1LabelTests(BlindCheckoutFixture):
    def test_v1_label_fields_removed_from_row_and_candidates(self):
        self.run_checkout()
        self.addCleanup(self.remove_worktree)
        document = json.loads((self.dest / "catalogs/landscape/foundation.json").read_text(encoding="utf-8"))
        row = document["layers"][0]
        for key in ("current_choice", "decision", "rationale"):
            self.assertNotIn(key, row)
        for candidate in row["candidates"]:
            for key in ("disposition", "rationale", "review_status"):
                self.assertNotIn(key, candidate)
        # The candidate's name/repository/evidence fields are kept.
        self.assertEqual(row["candidates"][0]["name"], "Codex")
        self.assertEqual(row["candidates"][0]["repository"], "https://github.com/openai/codex")


class CatalogsUnconditionalTests(BlindCheckoutFixture):
    def test_selection_keys_stripped_anywhere_under_catalogs_regardless_of_value(self):
        self.run_checkout()
        self.addCleanup(self.remove_worktree)
        document = json.loads((self.dest / "catalogs/other/decisions.json").read_text(encoding="utf-8"))
        decision = document["decisions"][0]
        self.assertNotIn("review_status", decision)
        self.assertNotIn("selection", decision)  # even though its value ("top_20") is a data value, not a label
        self.assertNotIn("decision", decision["nested"])
        self.assertEqual(decision["id"], "d1")


class BlueprintLabelExceptionTests(BlindCheckoutFixture):
    def test_label_values_stripped_but_data_values_and_rules_kept(self):
        self.run_checkout()
        self.addCleanup(self.remove_worktree)
        document = json.loads((self.dest / "blueprints/example/manifest.json").read_text(encoding="utf-8"))
        self.assertNotIn("disposition", document)
        self.assertNotIn("current_choice", document)
        self.assertNotIn("disposition", document["nested"])
        # Data values under the same key names are left alone under blueprints/.
        self.assertEqual(document["top"], "top_20")
        self.assertEqual(document["selection"], "top_20")
        # A mapping/rule structure under a stripped-elsewhere key name is left alone.
        self.assertEqual(document["mapping_rule"], {"decision": {"if": "condition", "then": "branch"}})
        # Real repository label strings, enumerated in the extended vocabulary/patterns.
        self.assertNotIn("decision", document["case_adopt"])
        self.assertNotIn("decision", document["case_defer"])
        self.assertNotIn("disposition", document["case_reject"])
        self.assertNotIn("decision", document["case_retain_prose_1"])
        self.assertNotIn("decision", document["case_retain_prose_2"])
        self.assertNotIn("decision", document["case_language_alt"])
        self.assertNotIn("selection", document["case_retain_selection"])
        # A procedural rule string that is not itself a selection is kept even though it
        # contains "deferred" mid-sentence (it does not open with the decision verb).
        self.assertIn("decision", document["case_rule_kept"])
        self.assertEqual(document["case_rule_kept"]["decision"],
                         "Submission is deferred by session, not by bar count, so an early close "
                         "cannot pull the order into the decision session.")


class ManifestTests(BlindCheckoutFixture):
    def test_manifest_lists_every_removal_and_strip_with_old_value_hashes_only(self):
        manifest = self.run_checkout()
        self.addCleanup(self.remove_worktree)
        on_disk = json.loads((self.dest / "BLIND-MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(on_disk["removed_files"], manifest["removed_files"])
        self.assertEqual(on_disk["stripped_fields"], manifest["stripped_fields"])
        # Every stripped entry names a path and an old-value hash, never the value itself.
        serialized = json.dumps(on_disk)
        self.assertNotIn("Codex", serialized)  # a stripped rationale/current_choice value
        self.assertNotIn("selected_destination", serialized)
        self.assertNotIn("example/other", serialized)  # a stripped overturn_protocol arm
        self.assertNotIn("preferred", serialized)  # a stripped open_gaps entry
        for entry in on_disk["stripped_fields"]:
            self.assertIn("path", entry)
            self.assertRegex(entry["old_sha256"], r"^[a-f0-9]{64}$")
        # At least one entry per strip rule is present.
        paths = {entry["path"] for entry in on_disk["stripped_fields"]}
        self.assertTrue(any(path.endswith("/verdict_status") for path in paths))
        self.assertTrue(any(path.endswith("/current_choice") for path in paths))
        self.assertTrue(any("/candidates/0/disposition" in path for path in paths))

    def test_manifest_records_resolved_rev_not_source_host_path(self):
        manifest = self.run_checkout()
        self.addCleanup(self.remove_worktree)
        on_disk = json.loads((self.dest / "BLIND-MANIFEST.json").read_text(encoding="utf-8"))
        self.assertNotIn("source", on_disk)
        self.assertNotIn(str(self.source), json.dumps(on_disk))
        self.assertEqual(on_disk["requested_rev"], "HEAD")
        self.assertRegex(on_disk["rev"], r"^[0-9a-f]{40}$")
        head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(self.source), check=True,
                                  capture_output=True, text=True).stdout.strip()
        self.assertEqual(on_disk["rev"], head_sha)

    def test_hmac_key_is_not_written_under_dest(self):
        manifest = self.run_checkout()
        self.addCleanup(self.remove_worktree)
        self.assertIn("hmac_key_hex", manifest)
        serialized = json.dumps(json.loads((self.dest / "BLIND-MANIFEST.json").read_text(encoding="utf-8")))
        self.assertNotIn(manifest["hmac_key_hex"], serialized)
        for path in self.dest.rglob("*"):
            if path.is_file():
                self.assertNotIn(manifest["hmac_key_hex"], path.read_text(encoding="utf-8", errors="ignore"))


class IdempotenceTests(BlindCheckoutFixture):
    def test_stripping_an_already_blind_worktree_finds_nothing_left_to_strip(self):
        self.run_checkout()
        self.addCleanup(self.remove_worktree)
        second_pass = blind_checkout.strip_worktree(self.dest, hmac_key=b"\x00" * 32)
        self.assertEqual(second_pass["removed_files"], [])
        self.assertEqual(second_pass["stripped_fields"], [])

    def test_running_blind_checkout_twice_from_the_same_source_rev_has_the_same_shape(self):
        # Each call draws its own random HMAC key by default, so old_sha256 values are not
        # expected to match across the two -- only which paths were removed/stripped, and
        # the resolved rev, are stable for the same source/rev.
        first = self.run_checkout()
        self.addCleanup(self.remove_worktree)
        second_dest = self.dest.parent / "dest2"
        second = self.run_checkout(dest=second_dest)
        self.addCleanup(lambda: self.remove_worktree(second_dest))
        self.assertEqual(first["removed_files"], second["removed_files"])
        self.assertEqual([entry["path"] for entry in first["stripped_fields"]],
                         [entry["path"] for entry in second["stripped_fields"]])
        self.assertEqual(first["rev"], second["rev"])
        self.assertNotEqual(first.get("hmac_key_hex"), second.get("hmac_key_hex"))

    def test_explicit_hmac_key_reproduces_the_same_hashes(self):
        key = b"\x01" * 32
        first = self.run_checkout()
        self.addCleanup(self.remove_worktree)
        second_dest = self.dest.parent / "dest2"
        blind_checkout.run_blind_checkout(self.source, "HEAD", second_dest, hmac_key=key)
        self.addCleanup(lambda: self.remove_worktree(second_dest))
        # first used a random key, so re-derive its hashes with the same explicit key by
        # re-running against a third dest with that key and comparing to the second run.
        third_dest = self.dest.parent / "dest3"
        third = blind_checkout.run_blind_checkout(self.source, "HEAD", third_dest, hmac_key=key)
        self.addCleanup(lambda: self.remove_worktree(third_dest))
        second_manifest = json.loads((second_dest / "BLIND-MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(second_manifest["stripped_fields"], third["stripped_fields"])
        self.assertNotEqual(third["stripped_fields"], first["stripped_fields"])


class RepositoryClassificationTests(unittest.TestCase):
    """Runs over this repository's own blueprints/ (local integration)."""

    def test_every_blueprint_value_under_a_label_key_is_classified(self):
        root = Path(__file__).resolve().parents[1]
        keys = {"selection", "decision", "disposition", "current_choice", "review_status"}
        unclassified = set()

        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in keys and isinstance(value, str) and not blind_checkout.is_label_value(value):
                        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
                        if value not in blind_checkout.DATA_VALUES and digest not in blind_checkout.DATA_VALUE_SHA256:
                            unclassified.add(value[:120])
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        for path in sorted((root / "blueprints").rglob("*.json")):
            try:
                walk(json.loads(path.read_text(encoding="utf-8")))
            except (ValueError, UnicodeDecodeError):
                continue
        self.assertEqual(sorted(unclassified), [], "classify these into LABEL_TEXT_SHA256 or DATA_VALUE_SHA256")

    def test_classified_texts_override_the_rules(self):
        methodology = ("Fifteen directly read public documentation files selected before evaluation, "
                       "with source bytes fixed by the base commit. No retrieval or ranking selected these files.")
        if hashlib.sha256(methodology.encode("utf-8")).hexdigest() in blind_checkout.DATA_VALUE_SHA256:
            self.assertFalse(blind_checkout.is_label_value(methodology))
        self.assertTrue(blind_checkout.is_label_value("selected"))
        self.assertFalse(blind_checkout.is_label_value("top_20"))


class ExportTests(BlindCheckoutFixture):
    """2026-09-23 re-record: lanes get a copy without .git, whose history recovers every stripped value."""

    def test_export_has_the_stripped_tree_without_git_or_the_manifest(self):
        export = self.dest.parent / "export"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(blind_checkout.main(["--source", str(self.source), "--rev", "HEAD",
                                                  "--dest", str(self.dest), "--export", str(export)]), 0)
        self.addCleanup(lambda: git(["worktree", "remove", "--force", str(self.dest)], self.source))
        self.assertTrue((self.dest / ".git").exists())
        self.assertFalse((export / ".git").exists())
        self.assertFalse((export / "BLIND-MANIFEST.json").exists())
        exported = json.loads((export / "catalogs/other/decisions.json").read_text(encoding="utf-8"))
        self.assertNotIn("selection", json.dumps(exported))
        self.assertEqual((export / "catalogs/other/decisions.json").read_bytes(),
                         (self.dest / "catalogs/other/decisions.json").read_bytes())

    def test_an_existing_export_is_refused_before_anything_is_created(self):
        export = self.dest.parent / "export"
        export.mkdir()
        with self.assertRaises(SystemExit):
            blind_checkout.main(["--source", str(self.source), "--rev", "HEAD", "--dest", str(self.dest),
                                 "--export", str(export)])
        self.assertFalse(self.dest.exists())

    def test_the_export_replaces_every_project_instruction_file_and_leaves_the_worktree_alone(self):
        """PR #141 review (P1): AGENTS.md and CLAUDE.md were copied unchanged, so a Codex child started with
        -C <export> read the incumbent choices (AGENTS.md names the selected destination engine)."""
        label = "NautilusTrader is the selected destination."
        instruction_files = ("AGENTS.md", "CLAUDE.md", "docs/sub/AGENTS.md", "examples/native/CLAUDE.md",
                             "docs/sub/AGENTS.override.md", "CLAUDE.local.md")
        for relative in instruction_files:
            self.write(relative, f"# Instructions\n\n{label}\n")
        self.write(".claude/settings.json", {"note": label})
        self.write(".codex/config.toml", f"# {label}\n")
        self.write(".agents/skills/pick/SKILL.md", f"# {label}\n")
        self.write("docs/sub/.claude/agents/judge.md", f"# {label}\n")
        git(["add", "-A"], self.source)
        git(["commit", "-q", "-m", "instructions"], self.source)
        export = self.dest.parent / "export"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(blind_checkout.main(["--source", str(self.source), "--rev", "HEAD",
                                                  "--dest", str(self.dest), "--export", str(export)]), 0)
        self.addCleanup(lambda: git(["worktree", "remove", "--force", str(self.dest)], self.source))
        for relative in instruction_files:
            self.assertEqual((export / relative).read_text(encoding="utf-8"), blind_checkout.EXPORT_INSTRUCTION_STUB,
                             relative)
            self.assertIn(label, (self.dest / relative).read_text(encoding="utf-8"), "the worktree is unchanged")
        for relative in (".claude", ".codex", ".agents", "docs/sub/.claude"):
            self.assertFalse((export / relative).exists(), relative)
            self.assertTrue((self.dest / relative).exists(), relative)
        exported_text = "".join(path.read_text(encoding="utf-8") for path in export.rglob("*") if path.is_file())
        self.assertNotIn("selected destination", exported_text)
        self.assertEqual((export / "docs/keep-me.md").read_text(encoding="utf-8"), "# Keep this one\n")
        printed = json.loads(out.getvalue())
        self.assertEqual(printed["export_instruction_files_replaced"], sorted(instruction_files))
        self.assertEqual(printed["export_instruction_dirs_removed"],
                         [".agents", ".claude", ".codex", "docs/sub/.claude"])

    def test_an_export_without_instruction_files_still_gets_the_root_stubs(self):
        export = self.dest.parent / "export"
        self.run_checkout()
        self.addCleanup(self.remove_worktree)
        result = blind_checkout.export_tree(self.dest, export)
        self.assertEqual(result, {"replaced_instruction_files": ["AGENTS.md", "CLAUDE.md"],
                                  "removed_instruction_dirs": [], "removed_escaping_symlinks": []})
        self.assertEqual((export / "AGENTS.md").read_text(encoding="utf-8"), blind_checkout.EXPORT_INSTRUCTION_STUB)
        self.assertFalse((self.dest / "AGENTS.md").exists())


class ExportSymlinkTests(BlindCheckoutFixture):
    """Codex review of #145: a symlink escaping the export is removed; one inside it is kept."""

    def test_escaping_symlinks_are_removed_and_inner_ones_kept(self):
        (self.source / "docs").mkdir(exist_ok=True)
        (self.source / "docs" / "inner.md").write_text("inner\n", encoding="utf-8")
        os.symlink("inner.md", self.source / "docs" / "inner-link.md")
        os.symlink("/etc/hostname", self.source / "docs" / "absolute-link")
        os.symlink("../../../outside", self.source / "docs" / "escaping-link")
        git(["add", "-A"], self.source)
        git(["commit", "-q", "-m", "links"], self.source)
        export = self.dest.parent / "export"
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(blind_checkout.main(["--source", str(self.source), "--rev", "HEAD",
                                                  "--dest", str(self.dest), "--export", str(export)]), 0)
        self.addCleanup(lambda: git(["worktree", "remove", "--force", str(self.dest)], self.source))
        self.assertTrue((export / "docs" / "inner-link.md").is_symlink())
        self.assertFalse(os.path.lexists(export / "docs" / "absolute-link"))
        self.assertFalse(os.path.lexists(export / "docs" / "escaping-link"))
        self.assertIn("docs/absolute-link", out.getvalue())


if __name__ == "__main__":
    unittest.main()
