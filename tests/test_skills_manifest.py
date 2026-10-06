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
import tomllib
import unittest
from pathlib import Path
from scripts import skills_status

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "adoption" / "skills" / "manifest.json"
SETTINGS_TEMPLATE_PATH = ROOT / "adoption" / "templates" / "claude.settings.template.json"
CODEX_TEMPLATE_PATH = ROOT / "adoption" / "templates" / "codex.config.template.toml"
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

    def test_trial_block_has_the_review_window_without_a_manifest_listing_cap(self):
        trial = self.manifest["trial"]
        for key in ("started", "window_days", "review_after"):
            self.assertIn(key, trial, key)
        self.assertNotIn("on_description_char_cap", trial)


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
                form = "blob" if skill.get("source_type") == "native_generated" else "tree"
                expected = f"https://github.com/{skill['source']}/{form}/{skill['ref']}/{skill['path']}"
                self.assertEqual(skill["url"], expected)

    def test_ref_and_tree_sha_are_40_hex(self):
        for skill in self.skills:
            with self.subTest(skill=skill["name"]):
                self.assertRegex(skill["ref"], HEX40, f"ref {skill['ref']!r}")
                if skill.get("source_type") == "native_generated":
                    self.assertIsNone(skill["tree_sha"])
                    self.assertTrue(skills_status.native_generated(skill))
                else:
                    self.assertRegex(skill["tree_sha"], HEX40, f"tree_sha {skill['tree_sha']!r}")

    def test_hf_generated_and_mirror_identities_are_distinct(self):
        skill = next(s for s in self.skills if s["name"] == "hf-cli")
        self.assertEqual(skill["generator"]["version"], "2.1.1")
        self.assertEqual(skill["skill_md_bytes"] + 1, skill["mirror"]["skill_md_bytes"])
        self.assertNotEqual(skill["skill_md_sha256"], skill["mirror"]["skill_md_sha256"])
        for key, value in (("name", "unrelated"), ("source", "other/repo"), ("ref", "HEAD"),
                           ("tree_sha", "a" * 40), ("generator", {}), ("mirror", {})):
            with self.subTest(key=key):
                mutant = dict(skill, **{key: value})
                self.assertFalse(skills_status.native_generated(mutant))

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

    def test_status_is_kept_trial_or_held(self):
        # held (2026-10-03, wave-2 skills ruling, change 6): not installed until the measurement held_for names returns.
        for skill in self.skills:
            with self.subTest(skill=skill["name"]):
                self.assertIn(skill["status"], ("kept", "trial", "held"))
                if skill["status"] == "held":
                    self.assertTrue(skill["held_for"].strip())
        self.assertEqual([s["name"] for s in self.skills if s["status"] == "held"], ["agent-browser"])

    def test_a_global_entry_names_its_agents_and_only_a_claude_code_copy(self):
        # skill-creator is a copy for Claude Code only: Codex keeps the skill-creator it embeds (wave-2 skills ruling,
        # change 6; the layer consensus's skill-authoring row).
        for skill in self.skills:
            with self.subTest(skill=skill["name"]):
                agents = skill.get("agents", ["claude-code", "codex"])
                self.assertTrue(agents and set(agents) <= {"claude-code", "codex"} and len(set(agents)) == len(agents))
                if skill.get("copy"):
                    self.assertEqual(agents, ["claude-code"])
        copies = {s["name"]: s for s in self.skills if s.get("copy")}
        self.assertEqual(sorted(copies), ["skill-creator"])
        self.assertIs(copies["skill-creator"]["codex_enabled"], False)

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

    def test_manifest_sums_are_not_a_live_client_listing_gate(self):
        self.assertNotIn("claude_on_cap", self.budget)

    def test_codex_enabled_description_chars_is_the_sum_over_codex_enabled_skills(self):
        expected = sum(skill["description_chars"] for skill in self.skills if skill["codex_enabled"])
        self.assertEqual(self.budget["codex_enabled_description_chars"], expected)

    def test_codex_catalog_description_chars_counts_only_the_skills_codex_shows_the_model(self):
        # Codex leaves a skill whose agents/openai.yaml sets allow_implicit_invocation: false out of the model's
        # catalog (openai/codex rust-v0.159.2 codex-rs/ext/skills/src/provider/host.rs L147-148; the flag defaults
        # to true, codex-rs/skills/src/model.rs L22-28). At their pins only the two upstream user-only skills set it.
        for skill in self.skills:
            if "upstream_allow_implicit_invocation" in skill:
                with self.subTest(skill=skill["name"]):
                    self.assertIsInstance(skill["upstream_allow_implicit_invocation"], bool)
        explicit_only = {s["name"] for s in self.skills if s.get("upstream_allow_implicit_invocation") is False}
        # The two that set it, grill-me and improve-codebase-architecture, were retired on 2026-10-03.
        self.assertEqual(explicit_only, set())
        shown = [s for s in self.skills if s["codex_enabled"] and s.get("upstream_allow_implicit_invocation", True)]
        self.assertEqual(self.budget["codex_catalog_description_chars"],
                         sum(skill["description_chars"] for skill in shown))

    def test_codex_configured_budget_tokens_is_the_codex_template_budget(self):
        # scripts/skills_status.py compares its catalog estimate with this figure, so it must be what hosts apply.
        template = tomllib.loads(CODEX_TEMPLATE_PATH.read_text(encoding="utf-8")).get("skills", {})
        self.assertEqual(self.budget["codex_configured_budget_tokens"], template.get("max_context_tokens"))

    def test_codex_eight_thousand_characters_is_kept_as_the_fallback_not_a_cap(self):
        # codex-rs/ext/skills/src/render.rs L19 and L138-151 at rust-v0.159.2: 8,000 characters only when the
        # context window is unknown and no max_context_tokens is set.
        self.assertEqual(self.budget["codex_fallback_budget_chars"], 8000)
        self.assertNotIn("codex_default_budget_chars", self.budget)


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

    def test_a_retired_entry_names_one_unselected_skill_and_its_date(self):
        retired = {entry["skills"]: entry for entry in self.excluded if "retired" in entry}
        # mattpocock/skills removed it in daa01d8 (2026-09-24); it is absent at d81f3a18.
        self.assertIn("resolving-merge-conflicts", retired)
        # Retired on 2026-10-03 by the wave-2 skills ruling (changes 1 and 3), each with its historical pin in the reason.
        for name, pin in (("grill-me", "c55ee46073ed923f86ce59a5eb3b6d895095d1b7"),
                          ("improve-codebase-architecture", "d81f3a183412e71a5b1e84ca21bc1a35eea03a60"),
                          ("semgrep", "82fe8226252622fa807643bdca1710901198553a")):
            with self.subTest(retired=name):
                self.assertEqual(retired[name]["retired"], "2026-10-03")
                self.assertIn(pin, retired[name]["reason"])
        selected = {skill["name"] for skill in self.manifest["skills"]}
        for name, entry in retired.items():
            with self.subTest(skill=name):
                # One skillOverrides key per retired entry, never a comma-separated list.
                self.assertRegex(name, r"^[a-z0-9][a-z0-9-]*$")
                self.assertNotIn(name, selected)
                self.assertRegex(entry["retired"], r"^\d{4}-\d{2}-\d{2}$")


class LlmNativeListingTests(unittest.TestCase):
    """The user's 2026-09-30 directive, docs/decisions/2026-09-30-skills-llm-native-listing.md: every skill
    the model may invoke is listed to Claude with its description and enabled for Codex. Only an upstream
    disable-model-invocation skill stays user-invocable-only, and only the copy of a skill Codex ships
    natively stays off for Codex."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = load_json(MANIFEST_PATH)
        cls.skills = cls.manifest["skills"]

    def test_every_model_invocable_skill_stays_listed_with_its_description(self):
        for skill in self.skills:
            with self.subTest(skill=skill["name"]):
                expected = "user-invocable-only" if skill["upstream_disable_model_invocation"] else "on"
                self.assertEqual(skill["claude_listing"], expected)

    def test_codex_disables_only_the_skill_codex_ships_natively(self):
        # Codex installs its own skill-creator into CODEX_HOME/skills/.system from
        # codex-rs/skills/src/assets/samples (codex-rs/skills/src/lib.rs L55-69 at rust-v0.157.1).
        self.assertEqual({s["name"] for s in self.skills if not s["codex_enabled"]}, {"skill-creator"})

    def test_skill_creator_is_pinned_from_anthropics_and_the_openai_copy_stays_excluded(self):
        by_name = {skill["name"]: skill for skill in self.skills}
        self.assertIn("skill-creator", sorted(by_name))
        self.assertEqual(by_name["skill-creator"]["source"], "anthropics/skills")
        naming = [entry for entry in self.manifest["excluded"]
                  if "skill-creator" in [name.strip() for name in entry["skills"].split(",")]]
        self.assertEqual([entry["source"] for entry in naming], ["openai/skills"])

    def test_zero_use_no_longer_demotes_a_listing(self):
        prune_rule = self.manifest["trial"]["prune_rule"]
        self.assertNotIn("on -> name-only", prune_rule)
        self.assertIn("dated decision record", prune_rule)


class ListingBudgetTemplateTests(unittest.TestCase):
    """The listing budgets the two client templates set (2026-09-30 record)."""

    def test_claude_template_keeps_the_directive_backed_listing_fraction(self):
        # 2026-09-30-skills-llm-native-listing.md: descriptions must remain visible.
        template = load_json(SETTINGS_TEMPLATE_PATH)
        self.assertEqual(template["skillListingBudgetFraction"], 0.05)
        self.assertNotIn("SLASH_COMMAND_TOOL_CHAR_BUDGET", template.get("env", {}))

    def test_codex_template_sets_the_catalog_token_budget_and_no_per_skill_tables(self):
        skills = tomllib.loads(CODEX_TEMPLATE_PATH.read_text(encoding="utf-8")).get("skills", {})
        budget = skills.get("max_context_tokens")
        self.assertIsInstance(budget, int)
        # codex-rs/ext/skills/src/render.rs L18 and L127-133 at rust-v0.157.1: a set value is capped at 10,000.
        self.assertTrue(1 <= budget <= 10_000, budget)
        self.assertEqual(budget, 6000)
        # Per-skill disables of manifest skills come from tools/adoption/install_skills.py --print-codex-config, never
        # the template. Its one rule turns off Codex's bundled skill-installer by path (wave-2 skills ruling), a path
        # relative to the Codex home that holds config.toml (tests/test_render_config.py,
        # test_the_bundled_skill_installer_rule_follows_the_codex_home).
        self.assertEqual(skills.get("config"), [{"path": "skills/.system/skill-installer/SKILL.md", "enabled": False}])

    def test_codex_template_comment_counts_the_skills_the_catalog_shows(self):
        text = CODEX_TEMPLATE_PATH.read_text(encoding="utf-8")
        match = re.search(r"manifest's (\d+) catalog-visible skills", text)
        self.assertIsNotNone(match, "the [skills] comment names the manifest's catalog-visible count")
        skills = load_json(MANIFEST_PATH)["skills"]
        shown = [s for s in skills if s["codex_enabled"] and s.get("upstream_allow_implicit_invocation", True)]
        self.assertEqual(int(match.group(1)), len(shown))


class TemplateSkillOverridesConsistencyTests(unittest.TestCase):
    """adoption/templates/claude.settings.template.json's skillOverrides must name every
    manifest skill exactly once, at its manifest claude_listing (settings_propagation), plus an
    explicit off for every retired excluded entry: the settings writer deep-merges, so dropping a
    key would leave a host's earlier on value in place (adoption/skills/lifecycle.md, Retire)."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = load_json(MANIFEST_PATH)
        cls.template = load_json(SETTINGS_TEMPLATE_PATH)

    def test_skill_overrides_equals_name_to_claude_listing(self):
        expected = {skill["name"]: skill["claude_listing"] for skill in self.manifest["skills"]}
        expected.update({entry["skills"]: "off" for entry in self.manifest["excluded"] if "retired" in entry})
        overrides = self.template.get("skillOverrides", {})
        # Native Claude's missing override is on; full host status still checks any host's retained off value.
        self.assertEqual({name: overrides.get(name, "on") for name in expected}, expected)
        self.assertFalse(set(overrides) - set(expected))


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
