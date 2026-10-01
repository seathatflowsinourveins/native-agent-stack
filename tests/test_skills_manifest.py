"""Schema/shape and cross-file consistency checks for the pinned skills trial
manifest, adoption/skills/manifest.json. These are structural checks against
the committed manifest itself (not a fixture): every number, hash and cross
reference here is expected to hold for the real file, and a genuine drift
(a renamed skill, a moved pin, a recomputed budget that no one updated) should
fail exactly one of these tests rather than surface later as a broken install
or a silently stale settings template.
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "adoption" / "skills" / "manifest.json"
SETTINGS_TEMPLATE_PATH = ROOT / "adoption" / "templates" / "claude.settings.template.json"
NATIVE_PRACTICE_PATH = ROOT / "catalogs" / "landscape" / "native-practice.json"

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_CLAUDE_LISTINGS = {"on", "name-only", "user-invocable-only", "off"}
AUDIT_FIELDS = ("gen_agent_trust_hub", "socket", "snyk")
# The three skills this manifest's "kept" winners share with the pre-existing
# catalogs/landscape/native-practice.json record (docs/decisions/2026-09-25-skills-trial-and-usage.md
# folds that record's three skills into this manifest as its first kept winners).
SHARED_KEPT_NAMES = ("typesafe-ai", "gh-fix-ci", "security-best-practices")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ManifestShapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_json(MANIFEST_PATH)

    def test_top_level_shape(self):
        for key in ("schema_version", "kind", "checked_at", "decision_record", "cli", "trial",
                    "settings_propagation", "skills", "budget", "excluded"):
            self.assertIn(key, self.manifest, key)
        self.assertEqual(self.manifest["kind"], "skills_trial_manifest")
        self.assertIsInstance(self.manifest["skills"], list)
        self.assertTrue(self.manifest["skills"])
        self.assertIsInstance(self.manifest["excluded"], list)
        self.assertTrue(self.manifest["excluded"])

    def test_cli_block_carries_the_pinned_upstream_version_and_install_hint(self):
        cli = self.manifest["cli"]
        for key in ("package", "version", "source", "install", "env", "lock_path"):
            self.assertIn(key, cli, key)
        self.assertEqual(cli["package"], "skills")
        self.assertTrue(cli["version"])
        self.assertEqual(cli["env"].get("DISABLE_TELEMETRY"), "1")

    def test_trial_block_has_the_review_window_and_char_cap(self):
        trial = self.manifest["trial"]
        for key in ("started", "window_days", "review_after", "on_description_char_cap"):
            self.assertIn(key, trial, key)
        self.assertIsInstance(trial["on_description_char_cap"], int)
        self.assertGreater(trial["on_description_char_cap"], 0)


class SkillEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_json(MANIFEST_PATH)
        cls.skills = cls.manifest["skills"]

    def test_every_skill_has_the_required_keys(self):
        required = {"name", "source", "url", "ref", "path", "tree_sha", "skill_md_sha256",
                    "skill_md_bytes", "description_chars", "upstream_disable_model_invocation",
                    "license", "official", "audits", "status", "gap", "claude_listing", "codex_enabled"}
        for skill in self.skills:
            with self.subTest(skill=skill.get("name")):
                missing = required - set(skill)
                self.assertEqual(missing, set(), f"{skill.get('name')} missing {missing}")

    def test_names_are_unique(self):
        names = [skill["name"] for skill in self.skills]
        duplicates = {name for name in names if names.count(name) > 1}
        self.assertEqual(duplicates, set())

    def test_url_is_built_from_source_ref_and_path(self):
        for skill in self.skills:
            with self.subTest(skill=skill["name"]):
                expected = f"https://github.com/{skill['source']}/tree/{skill['ref']}/{skill['path']}"
                self.assertEqual(skill["url"], expected)

    def test_ref_and_tree_sha_are_40_hex(self):
        for skill in self.skills:
            with self.subTest(skill=skill["name"]):
                self.assertRegex(skill["ref"], HEX40, f"ref {skill['ref']!r}")
                self.assertRegex(skill["tree_sha"], HEX40, f"tree_sha {skill['tree_sha']!r}")

    def test_skill_md_sha256_is_64_hex(self):
        for skill in self.skills:
            with self.subTest(skill=skill["name"]):
                self.assertRegex(skill["skill_md_sha256"], HEX64)

    def test_no_audit_field_is_a_bare_fail(self):
        # An exact-value check: "Fail" as a whole gen_agent_trust_hub/socket/snyk verdict is a
        # reason to exclude or drop a skill (see excluded[] reasons), never a value a kept or
        # trial entry carries. Prose that merely mentions "Fail" elsewhere is not this check.
        for skill in self.skills:
            with self.subTest(skill=skill["name"]):
                for field in AUDIT_FIELDS:
                    self.assertNotEqual(skill["audits"].get(field), "Fail",
                                       f"{skill['name']}.audits.{field}")

    def test_audit_url_is_on_skills_sh(self):
        for skill in self.skills:
            with self.subTest(skill=skill["name"]):
                self.assertTrue(skill["audits"]["url"].startswith("https://skills.sh/"),
                               skill["audits"]["url"])

    def test_every_trial_skill_has_a_nonempty_gap(self):
        for skill in self.skills:
            if skill["status"] != "trial":
                continue
            with self.subTest(skill=skill["name"]):
                self.assertIsInstance(skill["gap"], str)
                self.assertTrue(skill["gap"].strip(), f"{skill['name']} gap must not be empty")

    def test_status_is_kept_or_trial(self):
        for skill in self.skills:
            with self.subTest(skill=skill["name"]):
                self.assertIn(skill["status"], ("kept", "trial"))

    def test_claude_listing_is_one_of_the_four_allowed_values(self):
        for skill in self.skills:
            with self.subTest(skill=skill["name"]):
                self.assertIn(skill["claude_listing"], ALLOWED_CLAUDE_LISTINGS)

    def test_codex_enabled_is_a_bool(self):
        for skill in self.skills:
            with self.subTest(skill=skill["name"]):
                self.assertIsInstance(skill["codex_enabled"], bool)


class BudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_json(MANIFEST_PATH)
        cls.skills = cls.manifest["skills"]
        cls.budget = cls.manifest["budget"]

    def test_claude_on_description_chars_is_the_sum_over_on_listed_skills(self):
        expected = sum(skill["description_chars"] for skill in self.skills if skill["claude_listing"] == "on")
        self.assertEqual(self.budget["claude_on_description_chars"], expected)

    def test_claude_on_description_chars_stays_within_the_trial_cap(self):
        cap = self.manifest["trial"]["on_description_char_cap"]
        self.assertEqual(self.budget["claude_on_cap"], cap)
        self.assertLessEqual(self.budget["claude_on_description_chars"], cap)

    def test_codex_enabled_description_chars_is_the_sum_over_codex_enabled_skills(self):
        expected = sum(skill["description_chars"] for skill in self.skills if skill["codex_enabled"])
        self.assertEqual(self.budget["codex_enabled_description_chars"], expected)


class ExcludedEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_json(MANIFEST_PATH)
        cls.excluded = cls.manifest["excluded"]

    def test_every_excluded_entry_has_a_nonempty_reason_and_overturn(self):
        for entry in self.excluded:
            with self.subTest(skills=entry.get("skills")):
                for key in ("skills", "source", "reason", "overturn"):
                    self.assertIn(key, entry, key)
                    self.assertIsInstance(entry[key], str)
                    self.assertTrue(entry[key].strip(), f"{key} must not be empty")


class TemplateSkillOverridesConsistencyTests(unittest.TestCase):
    """adoption/templates/claude.settings.template.json's skillOverrides must name every
    manifest skill exactly once, at its manifest claude_listing (settings_propagation)."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = load_json(MANIFEST_PATH)
        cls.template = load_json(SETTINGS_TEMPLATE_PATH)

    def test_skill_overrides_equals_name_to_claude_listing(self):
        expected = {skill["name"]: skill["claude_listing"] for skill in self.manifest["skills"]}
        self.assertEqual(self.template.get("skillOverrides"), expected)


class NativePracticePinConsistencyTests(unittest.TestCase):
    """The three skills this manifest keeps that catalogs/landscape/native-practice.json already
    pinned (typesafe-ai, gh-fix-ci, security-best-practices) must stay pinned at the same source
    identity in both places: this manifest's ref/skill_md_sha256 are that record's
    source_pin/skill_sha256, never a silent second, drifted pin."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = load_json(MANIFEST_PATH)
        cls.native_practice = load_json(NATIVE_PRACTICE_PATH)
        cls.by_name = {skill["name"]: skill for skill in cls.manifest["skills"]}
        cls.practice_by_name = {skill["name"]: skill for skill in cls.native_practice["skills"]}

    def test_shared_kept_skills_are_present_in_both_records(self):
        for name in SHARED_KEPT_NAMES:
            with self.subTest(skill=name):
                self.assertIn(name, self.by_name)
                self.assertIn(name, self.practice_by_name)
                self.assertEqual(self.by_name[name]["status"], "kept")

    def test_shared_kept_skills_keep_the_same_source_pin_and_sha256(self):
        for name in SHARED_KEPT_NAMES:
            with self.subTest(skill=name):
                manifest_skill = self.by_name[name]
                practice_skill = self.practice_by_name[name]
                self.assertEqual(manifest_skill["ref"], practice_skill["source_pin"])
                self.assertEqual(manifest_skill["skill_md_sha256"], practice_skill["skill_sha256"])


if __name__ == "__main__":
    unittest.main()
