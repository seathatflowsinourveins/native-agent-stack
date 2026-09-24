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
import re
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
        # The candidate's name/repository/evidence fields are kept (the order is neutral; see
        # LedgerCandidateOrderTests).
        by_name = {candidate["name"]: candidate for candidate in row["candidates"]}
        self.assertEqual(by_name["Codex"]["repository"], "https://github.com/openai/codex")


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
        export = self.dest.parent / "hosts" / "blind" / "export"
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
        export = self.dest.parent / "hosts" / "blind" / "export"
        export.mkdir(parents=True)
        with self.assertRaises(SystemExit):
            blind_checkout.main(["--source", str(self.source), "--rev", "HEAD", "--dest", str(self.dest),
                                 "--export", str(export)])
        self.assertFalse(self.dest.exists())

    def test_a_shallow_export_is_refused_before_anything_is_created(self):
        # Independent review of #145, O3: the lanes and the adjudicator refuse such a root, so refuse it here.
        # A fixed two-component path stays shallow whatever TMPDIR is (binding re-review L7).
        shallow = Path("/srv/blind-export-shallow")
        with self.assertRaises(SystemExit) as raised:
            blind_checkout.main(["--source", str(self.source), "--rev", "HEAD", "--dest", str(self.dest),
                                 "--export", str(shallow)])
        self.assertIn("path components", str(raised.exception))
        self.assertFalse(self.dest.exists())

    def test_an_export_inside_a_repository_is_refused(self):
        # Re-review N5: git history would recover every stripped label.
        inside = self.source / "hosts" / "blind" / "export"
        with self.assertRaises(SystemExit) as raised:
            blind_checkout.main(["--source", str(self.source), "--rev", "HEAD", "--dest", str(self.dest),
                                 "--export", str(inside)])
        self.assertIn("inside the git repository", str(raised.exception))

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
        export = self.dest.parent / "hosts" / "blind" / "export"
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
        export = self.dest.parent / "hosts" / "blind" / "export"
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
        export = self.dest.parent / "hosts" / "blind" / "export"
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(blind_checkout.main(["--source", str(self.source), "--rev", "HEAD",
                                                  "--dest", str(self.dest), "--export", str(export)]), 0)
        self.addCleanup(lambda: git(["worktree", "remove", "--force", str(self.dest)], self.source))
        self.assertTrue((export / "docs" / "inner-link.md").is_symlink())
        self.assertFalse(os.path.lexists(export / "docs" / "absolute-link"))
        self.assertFalse(os.path.lexists(export / "docs" / "escaping-link"))
        self.assertIn("docs/absolute-link", out.getvalue())

    def test_instruction_names_that_are_directory_symlinks_become_stubs(self):
        # Codex review of #145: os.walk lists a symlink to a directory in dirs, so a files-only loop missed it
        # and the root stub was not written because the link's target existed.
        (self.source / "docs" / "sub").mkdir(parents=True, exist_ok=True)
        (self.source / "docs" / "sub" / "notes.md").write_text("notes\n", encoding="utf-8")
        for stale in ("AGENTS.md", "CLAUDE.md"):
            if (self.source / stale).exists() or (self.source / stale).is_symlink():
                (self.source / stale).unlink()
        os.symlink("docs/sub", self.source / "AGENTS.md")
        os.symlink("sub", self.source / "docs" / "CLAUDE.md")
        git(["add", "-A"], self.source)
        git(["commit", "-q", "-m", "directory-valued instruction links"], self.source)
        export = self.dest.parent / "hosts" / "blind" / "export"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(blind_checkout.main(["--source", str(self.source), "--rev", "HEAD",
                                                  "--dest", str(self.dest), "--export", str(export)]), 0)
        self.addCleanup(lambda: git(["worktree", "remove", "--force", str(self.dest)], self.source))
        for relative in ("AGENTS.md", "CLAUDE.md", "docs/CLAUDE.md"):
            path = export / relative
            self.assertFalse(path.is_symlink(), relative)
            self.assertEqual(path.read_text(encoding="utf-8"), blind_checkout.EXPORT_INSTRUCTION_STUB, relative)


def ordered_candidates(dispositions):
    """Three candidates in the checked-in order (selected first), with the given dispositions."""
    names = (("Zeta", "https://github.com/zz/zeta"), ("Alpha", "https://github.com/aa/alpha"),
             ("Mid", "https://github.com/mm/mid"))
    return [{"name": name, "repository": repository, "disposition": disposition, "evidence_refs": []}
            for (name, repository), disposition in zip(names, dispositions)]


class LedgerCandidateOrderTests(BlindCheckoutFixture):
    """2026-09-24 blindness review (F2): candidates[0] was the selected incumbent on every ledger row."""

    def test_candidates_are_exported_in_a_neutral_order_independent_of_dispositions(self):
        first = ledger_row(layer_id="a", candidates=ordered_candidates(("selected", "conditional", "rejected")))
        first["candidates"][0]["review_status"] = "confirmed_default"
        permuted = ledger_row(layer_id="b", candidates=list(reversed(
            ordered_candidates(("rejected", "selected", "conditional")))))
        self.write("catalogs/landscape/foundation.json", {"schema_version": 2, "layers": [first, permuted]})
        git(["add", "-A"], self.source)
        git(["commit", "-q", "-m", "ordered ledger"], self.source)
        manifest = self.run_checkout()
        self.addCleanup(self.remove_worktree)
        rows = json.loads((self.dest / "catalogs/landscape/foundation.json").read_text(encoding="utf-8"))["layers"]
        # The selected candidate (Zeta, whose repository sorts last) is exported last, not first.
        self.assertEqual([c["name"] for c in rows[0]["candidates"]], ["Alpha", "Mid", "Zeta"])
        self.assertEqual([c["name"] for c in rows[1]["candidates"]], ["Alpha", "Mid", "Zeta"])
        # Every stripped pointer names the exported index.
        paths = {entry["path"] for entry in manifest["stripped_fields"]}
        self.assertIn("catalogs/landscape/foundation.json#/layers/0/candidates/2/review_status", paths)
        self.assertNotIn("catalogs/landscape/foundation.json#/layers/0/candidates/0/review_status", paths)


class CatalogWinnerKeyTests(BlindCheckoutFixture):
    """2026-09-24 blindness review (F1): catalogs/ files that name the current winners."""

    def test_no_catalog_json_in_the_export_carries_a_winner_or_incumbent_value(self):
        self.write("catalogs/landscape/component-evidence-matrix.json",
                   {"rows": [{"layer": "x", "winners": ["codex"]}]})
        self.write("catalogs/landscape/new-host-grand-list.json", {"layers": [{"winners": ["codex"]}]})
        self.write("catalogs/landscape/blind-convergence.json", {"rows": [{"coordinator_disposition": "codex"}]})
        self.write("catalogs/sota-convergence/manifest-20260923.json",
                   {"components": [{"id": "codex", "why_selected": "incumbent"}]})
        self.write("catalogs/sota-convergence/sdk-runtime-coverage-20260923.json", {"incumbents": ["codex"]})
        self.write("catalogs/foundation/community-practice-20260920.json",
                   {"incumbent_decision_ids": ["d1"], "incumbent_decisions_path": "catalogs/x.json",
                    "items": [{"winners": [{"id": "codex"}], "why_selected": "chosen",
                               "claude_final_disposition": "codex", "current_selection_record": "r",
                               "dual_lane_same_winner": True, "empty_winners": [], "winners_note": ""}]})
        git(["add", "-A"], self.source)
        git(["commit", "-q", "-m", "winner catalogs"], self.source)
        export = self.dest.parent / "hosts" / "blind" / "export"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(blind_checkout.main(["--source", str(self.source), "--rev", "HEAD",
                                                  "--dest", str(self.dest), "--export", str(export)]), 0)
        self.addCleanup(lambda: git(["worktree", "remove", "--force", str(self.dest)], self.source))
        for removed in ("catalogs/landscape/component-evidence-matrix.json",
                        "catalogs/landscape/new-host-grand-list.json", "catalogs/landscape/blind-convergence.json",
                        "catalogs/sota-convergence/manifest-20260923.json",
                        "catalogs/sota-convergence/sdk-runtime-coverage-20260923.json"):
            self.assertFalse((export / removed).exists(), removed)
        pattern = re.compile(r"winners|incumbent|disposition|why_selected|current_selection_record", re.IGNORECASE)
        offending = []

        def walk(node, pointer):
            if isinstance(node, dict):
                for key, value in node.items():
                    if pattern.search(key) and value not in (None, "", [], {}):
                        offending.append(f"{pointer}/{key}")
                    walk(value, f"{pointer}/{key}")
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    walk(value, f"{pointer}/{index}")

        scanned = 0
        for path in sorted((export / "catalogs").rglob("*.json")):
            walk(json.loads(path.read_text(encoding="utf-8")), path.relative_to(export).as_posix())
            scanned += 1
        self.assertGreater(scanned, 0)
        self.assertEqual(offending, [])
        community = json.loads((export / "catalogs/foundation/community-practice-20260920.json").read_text("utf-8"))
        # Empty values state nothing and are kept, so a pending ledger row keeps winners: [].
        self.assertEqual(community["items"][0]["empty_winners"], [])
        on_disk = json.loads((self.dest / "BLIND-MANIFEST.json").read_text(encoding="utf-8"))
        paths = {entry["path"] for entry in on_disk["stripped_fields"]}
        self.assertIn("catalogs/foundation/community-practice-20260920.json/items/0/why_selected", paths)
        self.assertIn("catalogs/foundation/community-practice-20260920.json/incumbent_decision_ids", paths)


class ExportTimestampTests(BlindCheckoutFixture):
    def test_every_exported_path_has_the_same_fixed_timestamp(self):
        export = self.dest.parent / "hosts" / "blind" / "export"
        self.run_checkout()
        self.addCleanup(self.remove_worktree)
        blind_checkout.export_tree(self.dest, export)
        paths = [export, *export.rglob("*")]
        self.assertTrue(any(path.is_file() for path in paths))
        for path in paths:
            stat = os.lstat(path)
            self.assertEqual(stat.st_mtime, 0, path)
            if path.is_file():
                # Listing a directory (this test's rglob) refreshes its atime, so atime is asserted only for
                # files, which this test never reads.
                self.assertEqual(stat.st_atime, 0, path)


class AllowlistExportTests(BlindCheckoutFixture):
    """2026-09-24 blindness review (F1): with --allow-from-packets the export holds only what the packets name."""

    def setUp(self):
        super().setUp()
        self.write("README.md", "# Catalog\n\nThe selected stack is Codex.\n")
        self.write("evidence/receipts/a.json", {"see": "evidence/receipts/b.md#L3",
                                                "catalog": "catalogs/other/decisions.json",
                                                "doc": "docs/keep-me.md", "readme": "README.md"})
        self.write("evidence/receipts/b.md", "transitive\n")
        self.write("evidence/receipts/c.json", {"next": "evidence/receipts/d.json"})
        self.write("evidence/receipts/d.json", {"next": "evidence/receipts/e.md"})
        self.write("evidence/receipts/e.md", "two levels away\n")
        self.write("evidence/receipts/unreferenced.md", "not named\n")
        self.write("evidence/dir/x.txt", "x\n")
        self.write("evidence/dir/sub/y.txt", "y\n")
        self.write("blueprints/bp/recipe.md", "recipe\n")
        self.write("tests/test_example.py", "# test\n")
        self.write("tools/example/tool.py", "# tool\n")
        self.write("scripts/example.sh", "#!/bin/sh\n")
        git(["add", "-A"], self.source)
        git(["commit", "-q", "-m", "allowlist fixture"], self.source)
        packets_parent = tempfile.TemporaryDirectory()
        self.addCleanup(packets_parent.cleanup)
        self.packets = Path(packets_parent.name).resolve() / "packets"
        self.packets.mkdir()
        packet = {
            "catalog": "foundation", "layer_id": "native-clients",
            "candidates": [
                {"name": "Codex", "evidence_refs": ["evidence/receipts/a.json", "evidence/dir/",
                                                    "catalogs/landscape/foundation.json:12",
                                                    "evidence/missing.md, see notes",
                                                    "https://github.com/openai/codex", "/etc/hostname",
                                                    "../outside/file.md"],
                 "registered_receipts": [{"id": "withheld", "path": "evidence/receipts/c.json"}],
                 "recipe_ref": "blueprints/bp/recipe.md:L12"},
                {"name": "Other", "evidence_refs": [], "recipe_ref": None},
            ],
            "sota_components_not_in_candidates": [
                {"registered_receipts": [{"path": "evidence/dir/sub/y.txt;"}]}],
        }
        (self.packets / "foundation__native-clients.json").write_text(json.dumps(packet), encoding="utf-8")
        (self.packets / "SHA256SUMS").write_text("ignored\n", encoding="utf-8")
        self.export = self.dest.parent / "hosts" / "blind" / "export"
        self.out = io.StringIO()
        with contextlib.redirect_stdout(self.out):
            # The fixture references a missing file on purpose, to test its reporting (refused by default).
            self.assertEqual(blind_checkout.main(["--source", str(self.source), "--rev", "HEAD",
                                                  "--dest", str(self.dest), "--export", str(self.export),
                                                  "--allow-from-packets", str(self.packets),
                                                  "--allow-missing-refs"]), 0)
        self.addCleanup(lambda: git(["worktree", "remove", "--force", str(self.dest)], self.source))

    def test_missing_references_are_refused_by_default(self):
        # Independent review of #145, round 4, F4/OPS-1: a lane must not be pointed at a file the export lacks.
        dest = self.dest.parent / "second-checkout"
        export = self.dest.parent / "hosts" / "blind" / "export-2"
        with self.assertRaisesRegex(SystemExit, "reference 1 path\\(s\\) the export lacks \\(evidence/missing.md\\)"):
            blind_checkout.main(["--source", str(self.source), "--rev", "HEAD", "--dest", str(dest),
                                 "--export", str(export), "--allow-from-packets", str(self.packets)])
        self.assertFalse(export.exists())
        self.assertFalse(dest.exists())  # the worktree goes too, so a rerun can reuse --dest (review of 52344da8)

    def test_an_export_inside_the_worktree_is_refused(self):
        # Round 4, R4-REG-8.
        dest = self.dest.parent / "third-checkout"
        with self.assertRaisesRegex(SystemExit, "overlaps --dest"):
            blind_checkout.main(["--source", str(self.source), "--rev", "HEAD", "--dest", str(dest),
                                 "--export", str(dest / "hosts" / "blind" / "export")])
        self.assertFalse(dest.exists())

    def test_export_holds_only_referenced_and_transitive_paths(self):
        exported = sorted(p.relative_to(self.export).as_posix() for p in self.export.rglob("*") if p.is_file())
        self.assertEqual(exported, sorted([
            "AGENTS.md", "CLAUDE.md",
            "blueprints/bp/recipe.md",
            "catalogs/landscape/foundation.json",
            "evidence/dir/sub/y.txt", "evidence/dir/x.txt",
            "evidence/receipts/a.json", "evidence/receipts/b.md", "evidence/receipts/c.json",
            "evidence/receipts/d.json",
        ]))
        # tests/, tools/ and scripts/ are not exported whole: they carry selection-bearing data and assertions
        # (Codex review of #145); a file there is exported only when a packet references it.
        for excluded in ("scripts/example.sh", "tests/test_example.py", "tools/example/tool.py",
                         "README.md", "docs/keep-me.md", "catalogs/other/decisions.json",
                         "evidence/receipts/e.md", "evidence/receipts/unreferenced.md"):
            self.assertFalse((self.export / excluded).exists(), excluded)
        # Included files still get the export's stripping and stubs.
        self.assertEqual((self.export / "AGENTS.md").read_text(encoding="utf-8"),
                         blind_checkout.EXPORT_INSTRUCTION_STUB)
        row = json.loads((self.export / "catalogs/landscape/foundation.json").read_text(encoding="utf-8"))["layers"][0]
        self.assertEqual(row["winners"], [])
        self.assertNotIn("current_choice", row)

    def test_a_reference_to_a_symlink_whose_target_is_not_exported_is_missing(self):
        # Codex review of #145 at a4dfd99e: the link alone was exported, dangling or removed as escaping, while
        # missing_refs stayed empty.
        scratch = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, scratch)
        dest, export, packets = scratch / "dest", scratch / "hosts" / "blind" / "export", scratch / "packets"
        (dest / "evidence").mkdir(parents=True)
        packets.mkdir()
        (dest / "evidence" / "target.md").write_text("target\n", encoding="utf-8")
        (dest / "evidence" / "link.md").symlink_to("target.md")
        (dest / "evidence" / "escape.md").symlink_to(scratch / "outside.md")
        (scratch / "outside.md").write_text("outside\n", encoding="utf-8")
        (dest / "evidence" / "plain.md").write_text("plain\n", encoding="utf-8")
        (packets / "foundation__layer.json").write_text(json.dumps({"candidates": [{"key": "c1", "evidence_refs": [
            "evidence/link.md", "evidence/escape.md", "evidence/plain.md"]}]}), encoding="utf-8")
        result = blind_checkout.export_tree(dest, export, allow_from_packets=packets)
        self.assertEqual(result["missing_refs"], ["evidence/escape.md", "evidence/link.md"])

    def test_counts_and_missing_references_are_reported(self):
        printed = json.loads(self.out.getvalue())
        self.assertEqual(printed["export_missing_refs"], ["evidence/missing.md"])
        self.assertEqual(printed["export_transitive_refs"], 2)  # b.md (from a.json) and d.json (from c.json)
        self.assertEqual(printed["export_allowlisted_files"], 8)

    def test_bare_reference_reduction(self):
        reduce = blind_checkout.bare_reference
        self.assertEqual(reduce("docs/x.md#section"), "docs/x.md")
        self.assertEqual(reduce("tools/a.py:12"), "tools/a.py")
        self.assertEqual(reduce("tools/a.py:L12-L40,"), "tools/a.py")
        self.assertEqual(reduce("(evidence/a.json)"), "evidence/a.json")
        self.assertEqual(reduce("./evidence/dir/ plus prose"), "evidence/dir")
        for rejected in ("https://example.com/a", "/etc/hostname", "../x", "a/../../b", "", None, 3):
            self.assertIsNone(reduce(rejected), rejected)


class RealExportIsolationTests(unittest.TestCase):
    """Independent re-review of #145, blindness N1: on this repository's real 2026-09-23 packets, no list in the
    allowlisted blind export isolates a layer's winner among its adopted candidates under a non-evidence key
    (a membership or role label). Evidence-reference lists that cite what was exercised stay (disclosed)."""

    def test_the_real_export_carries_no_role_label_that_isolates_a_winner(self):
        tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=False)
        if tracked.returncode != 0 or not tracked.stdout:
            self.skipTest("not a git checkout")
        lane_packets = load_module("lane_packets_for_isolation", "lane_packets.py")
        isolation = load_module("export_isolation_check", "export_isolation_check.py")
        scratch = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, scratch)
        packets_dir = scratch / "work" / "packets"
        packets_dir.mkdir(parents=True)
        sealed = {}
        packets = lane_packets.build_all_packets(
            ROOT, catalogs=["foundation", "us-equities"], seed="20260923", checked_at="2026-09-23",
            trading_candidates="manifest", withhold=True,
            manifest="catalogs/sota-convergence/manifest-20260923.json", registered_receipts=True, sealed_keys=sealed)
        for name, text in packets.items():
            (packets_dir / name).write_text(text, encoding="utf-8")
        dest = scratch / "hosts" / "blind" / "checkout"
        for relative in tracked.stdout.decode("utf-8").split("\0"):
            source = ROOT / relative
            if relative and source.is_file() and not source.is_symlink():
                target = dest / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        blind_checkout.strip_worktree(dest, b"k" * 32)
        export = scratch / "hosts" / "blind" / "export"
        result = blind_checkout.export_tree(dest, export, allow_from_packets=packets_dir)
        # Every packet reference resolves in the export (independent review of #145, round 4, F4/OPS-1).
        self.assertEqual(result["missing_refs"], [])
        # Id-aware (round 4, F1): component ids come from the sealed keys, as a lane never sees them.
        report = isolation.isolation_hits(export, packets_dir, isolation.ledger_winners(ROOT),
                                          {"schema_version": 1, "packets": sealed})
        self.assertGreaterEqual(len(report), 25)
        self.assertEqual(isolation.role_label_hits(report), [])
        # Record-field hits are reported, never failed (round 7, OPR7-2): a winner change made intrinsic attributes
        # (license, a version) isolate the new winner. The cards' own label fields are stripped (round 6, B6-3), so
        # none sits outside an evidence record today.
        records = isolation.record_field_hits(export, packets_dir, isolation.ledger_winners(ROOT),
                                              {"schema_version": 1, "packets": sealed})
        self.assertEqual([hit for hit in isolation.record_label_hits(records) if not hit["evidence_record"]], [])
        # The exposure a wave discloses (round 7, BL7-1): web-research's cited table row states its selection.
        exposure = isolation.prose_exposure(export, packets_dir, isolation.ledger_winners(ROOT),
                                            {"schema_version": 1, "packets": sealed})
        self.assertIn("docs/full-stack-convergence.md", exposure["foundation::web-research"]["cited_files"])
        self.assertFalse(exposure["foundation::git-github-automation"]["cited_files"])
        # Exported files are verbatim beyond label stripping (round 6, B6-4): a hash-bound listing keeps its bytes.
        for relative in ("evidence/artifacts/usage-report.source.txt",):
            if (export / relative).is_file():
                self.assertEqual((export / relative).read_bytes(), (ROOT / relative).read_bytes(), relative)
        # Exercised checks survive role-key stripping (round 4, R4-REG-1).
        practice = json.loads((export / "catalogs/landscape/native-practice.json").read_text(encoding="utf-8"))
        self.assertIn("coordinator_owned_qualification", practice)
        self.assertTrue(any("retained_helper_check" in skill for skill in practice.get("skills") or []))
        for removed in ("adoption/manifest.json", "catalogs/foundation/decisions.json",
                        "catalogs/us-equities/runtime-target.json", "blueprints/us-equities/north-star.md"):
            self.assertFalse((export / removed).exists(), removed)
        # Review of #145 (F5): no packet field but evidence is present on exactly a layer's winners.
        fields = isolation.packet_field_hits(packets_dir, isolation.ledger_winners(ROOT))
        self.assertGreaterEqual(len(fields), 25)
        self.assertEqual(isolation.packet_role_label_hits(fields), [])

    def test_a_packet_field_on_exactly_the_winners_is_a_role_label_unless_it_is_evidence(self):
        isolation = load_module("export_isolation_check", "export_isolation_check.py")
        scratch = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, scratch)
        candidates = [{"key": "c1", "repository": "https://github.com/acme/win", "adopted": True, "pin": "1.0",
                       "registered_receipts": [{"kind": "host_e2e", "path": "a.json"}]},
                      {"key": "c2", "repository": "https://github.com/acme/other", "adopted": True, "pin": None,
                       "registered_receipts": []},
                      {"key": "c3", "repository": "https://github.com/acme/new", "adopted": False, "pin": "2.0"}]
        (scratch / "foundation__layer.json").write_text(json.dumps({"candidates": candidates}), encoding="utf-8")
        fields = isolation.packet_field_hits(scratch, {"foundation::layer": [("github.com/acme/win", "")]})
        self.assertEqual(fields, {"foundation::layer": ["pin", "registered_receipts"]})
        self.assertEqual(isolation.packet_role_label_hits(fields), [{"layer": "foundation::layer", "field": "pin"}])

    def test_round6_checker_gaps_are_closed(self):
        # Round 6, B6-6: camelCase and role words inside evidence records, and a field absent on exactly the winners.
        isolation = load_module("export_isolation_check", "export_isolation_check.py")
        self.assertEqual(isolation._key_tokens("$.records[].selectedTools"), {"selected", "tools"})
        self.assertEqual(isolation._key_tokens("$.x.selected-repos{keys}"), {"selected", "repos"})
        # Round 7, OPR7-2: in an evidence record the strong role words fail, the others are reported.
        for key in ("winnerTools", "chosen_repos", "incumbents"):
            hit = {"file": "evidence/run/receipt.json", "path": f"$.{key}", "mode": "names_alone"}
            self.assertFalse(isolation.evidence_hit(hit), key)
        for key in ("selectedTools", "selected_repos", "selection", "picked", "recommended", "default", "primary"):
            hit = {"file": "evidence/run/receipt.json", "path": f"$.{key}", "mode": "names_alone"}
            self.assertTrue(isolation.evidence_hit(hit), key)
            self.assertEqual(len(isolation.evidence_role_word_hits({"foundation::layer": [hit]})), 1, key)
        self.assertTrue(isolation.evidence_hit({"file": "evidence/run/receipt.json", "path": "$.sources",
                                                "mode": "names_alone"}))
        scratch = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, scratch)
        candidates = [{"key": "c1", "repository": "https://github.com/acme/win", "adopted": True},
                      {"key": "c2", "repository": "https://github.com/acme/other", "adopted": True, "role": "optional"},
                      {"key": "c3", "repository": "https://github.com/acme/third", "adopted": True, "role": "optional"}]
        (scratch / "foundation__layer.json").write_text(json.dumps({"candidates": candidates}), encoding="utf-8")
        fields = isolation.packet_field_hits(scratch, {"foundation::layer": [("github.com/acme/win", "")]})
        self.assertEqual(fields, {"foundation::layer": ["role"]})

    def test_a_card_role_is_stripped_only_when_it_states_status(self):
        # Round 7, BL7-4: the export's role strip shares the packet rule, so behaviour roles stay.
        for role in ("Selected-file handoff bundles", "Retained local sanitized operational logs and LogQL queries"):
            self.assertFalse(blind_checkout._role_key("role", role), role)
        for role in ("Selected north-star engine for backtests.", "The selected GitHub CLI."):
            self.assertTrue(blind_checkout._role_key("role", role), role)

    def test_prose_exposure_scores_tables_and_discriminating_statements(self):
        # Round 7, BL7-1: a selection-headed table row, a statement naming only winners, never one naming a non-winner.
        isolation = load_module("export_isolation_check", "export_isolation_check.py")
        scratch = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, scratch)
        packets, export = scratch / "packets", scratch / "export"
        (export / "docs").mkdir(parents=True)
        packets.mkdir()
        (packets / "foundation__layer.json").write_text(json.dumps({"candidates": [
            {"key": "c1", "name": "Tavily", "repository": "https://github.com/acme/tavily", "adopted": True,
             "evidence_refs": ["docs/a.md", "docs/b.md"]},
            {"key": "c2", "name": "Crawler", "repository": "https://github.com/acme/crawler", "adopted": True}]}),
            encoding="utf-8")
        winners = {"foundation::layer": [("github.com/acme/tavily", "")]}
        (export / "docs" / "a.md").write_text("| Layer | Selected practice |\n| --- | --- |\n| Web | Tavily |\n",
                                              encoding="utf-8")
        (export / "docs" / "b.md").write_text("Tavily and Crawler both keep defaults. `Tavily` defaults `--depth`.\n",
                                              encoding="utf-8")
        (export / "docs" / "c.md").write_text("Retain Tavily for search.\n", encoding="utf-8")
        report = isolation.prose_exposure(export, packets, winners)
        self.assertEqual(report["foundation::layer"], {"scored": True, "cited_files": ["docs/a.md"],
                                                       "export_files": ["docs/a.md", "docs/c.md"]})
        self.assertFalse(isolation.prose_exposure(export, packets, {})["foundation::layer"]["scored"])

    def test_an_exact_component_id_picks_one_of_two_candidates_of_one_repository(self):
        # Codex review of #145 at 68e74f2c: alpaca-py and data-alpaca-py share alpacahq/alpaca-py, and normalizing
        # both to alpaca-py made a verdict for one match both.
        isolation = load_module("export_isolation_check", "export_isolation_check.py")
        adopted = [{"key": "c1", "repository": "https://github.com/alpacahq/alpaca-py", "component_id": "alpaca-py"},
                   {"key": "c2", "repository": "https://github.com/alpacahq/alpaca-py", "component_id": "data-alpaca-py"}]
        for exact, expected in (("alpaca-py", {"c1"}), ("data-alpaca-py", {"c2"})):
            winner = [("github.com/alpacahq/alpaca-py", isolation.norm(exact), exact)]
            self.assertEqual(isolation.winner_keys(adopted, winner), expected, exact)
        # A two-element winner (no exact id) keeps the earlier behaviour.
        self.assertEqual(isolation.winner_keys(adopted, [("github.com/alpacahq/alpaca-py", "alpaca-py")]), {"c1", "c2"})

    def test_the_checker_refuses_bad_input_with_exit_2(self):
        # Round 6, OPR6-5: a missing or malformed --packet-keys, or none for sealed packets, is a usage error (2),
        # never the role-label exit (1).
        isolation = load_module("export_isolation_check", "export_isolation_check.py")
        scratch = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, scratch)
        packets, export = scratch / "packets", scratch / "export"
        packets.mkdir()
        export.mkdir()
        packet = {"candidates": [{"key": "c1", "repository": "https://github.com/acme/win", "adopted": True}],
                  "sealed_candidates_sha256": "0" * 64}
        (packets / "foundation__layer.json").write_text(json.dumps(packet), encoding="utf-8")
        bad = {"missing": None, "text": "not json", "list": "[]", "string-entry": json.dumps(
            {"schema_version": 1, "packets": {"foundation__layer.json": "x"}})}
        for label, content in [("none", None)] + list(bad.items()):
            argv = [str(export), str(packets), str(ROOT)]
            if label != "none":
                keys = scratch / f"{label}.json"
                if content is not None:
                    keys.write_text(content, encoding="utf-8")
                argv += ["--packet-keys", str(keys)]
            with contextlib.redirect_stderr(io.StringIO()) as err, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(isolation.main(argv), 2, label)
            self.assertIn("export_isolation_check:", err.getvalue(), label)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(isolation.main([str(scratch / "absent"), str(packets)]), 2)

    def test_a_categorical_card_field_on_exactly_the_winners_is_a_label(self):
        # Round 6, B6-3: evidence_level native_proven only on the winners, installed_version only on them.
        isolation = load_module("export_isolation_check", "export_isolation_check.py")
        scratch = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, scratch)
        packets, export = scratch / "packets", scratch / "export"
        packets.mkdir()
        (packets / "us-equities__layer.json").write_text(json.dumps({"candidates": [
            {"key": f"c{i}", "repository": f"https://github.com/acme/tool{i}", "adopted": True} for i in (1, 2, 3)]}),
            encoding="utf-8")
        cards = {"entries": [
            {"id": "tool1", "repository": "https://github.com/acme/tool1", "evidence_level": "native_proven",
             "installed_version": "1.0", "limitations": ["a"]},
            {"id": "tool2", "repository": "https://github.com/acme/tool2", "evidence_level": "source_review",
             "limitations": ["b"]},
            {"id": "tool3", "repository": "https://github.com/acme/tool3", "evidence_level": "source_review",
             "limitations": ["c"]}]}
        (export / "catalogs").mkdir(parents=True)
        (export / "catalogs" / "cards.json").write_text(json.dumps(cards), encoding="utf-8")
        report = isolation.record_field_hits(export, packets, {"us-equities::layer": [("github.com/acme/tool1", "")]})
        self.assertEqual({hit["field"] for hit in isolation.record_label_hits(report)},
                         {"evidence_level", "installed_version"})

    def test_id_keyed_containers_are_matched_and_classified(self):
        # Round 4, F1 and F6: an id-keyed list or key set naming the winner alone outside an evidence record is a
        # role label; the same under evidence/ or in a receipt is evidence; a complement list fails under any key.
        isolation = load_module("export_isolation_check", "export_isolation_check.py")
        scratch = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, scratch)
        packets, export = scratch / "packets", scratch / "export"
        packets.mkdir()
        (packets / "foundation__layer.json").write_text(json.dumps({"candidates": [
            {"key": "c1", "repository": "https://github.com/acme/win", "adopted": True},
            {"key": "c2", "repository": "https://github.com/acme/other", "adopted": True},
            {"key": "c3", "repository": "https://github.com/acme/third", "adopted": True}]}), encoding="utf-8")
        keys = {"packets": {"foundation__layer.json": {"candidates": {
            "c1": {"component_id": "data-win-tool"}, "c2": {"component_id": "other"}, "c3": {"component_id": "third"}}}}}
        documents = {"adoption/profiles.json": {"recipe_map": {"win_tool": "recipes/x.md"}},
                     "evidence/run/receipt.json": {"component_ids": ["win-tool"]},
                     "catalogs/cards.json": {"entries": [{"sources": ["https://github.com/acme/other",
                                                                      "https://github.com/acme/third"]}]}}
        for relative, document in documents.items():
            (export / relative).parent.mkdir(parents=True, exist_ok=True)
            (export / relative).write_text(json.dumps(document), encoding="utf-8")
        winners = {"foundation::layer": [("github.com/acme/win", "win-tool")]}
        report = isolation.isolation_hits(export, packets, winners, keys)
        self.assertEqual({(hit["file"], hit["mode"]) for hit in report["foundation::layer"]},
                         {("adoption/profiles.json", "names_alone"), ("evidence/run/receipt.json", "names_alone"),
                          ("catalogs/cards.json", "complement")})
        self.assertEqual({hit["file"] for hit in isolation.role_label_hits(report)},
                         {"adoption/profiles.json", "catalogs/cards.json"})
        # Without the sealed ids, the id-keyed map is invisible: why the checker takes the packet keys.
        self.assertNotIn("adoption/profiles.json",
                         {hit["file"] for hit in isolation.isolation_hits(export, packets, winners)["foundation::layer"]})


if __name__ == "__main__":
    unittest.main()
