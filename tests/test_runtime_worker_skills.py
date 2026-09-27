"""Structural/source-contract checks, not native worker or upstream acceptance."""
import ast
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "blueprints/runtime-workers/skills"
SCENARIOS = {
    "planning-and-specs", "tdd", "e2e-testing", "ab-testing-and-evaluation", "debugging",
    "code-review", "security", "github-issue-to-pr", "github-pr-review", "github-ci-fix",
    "github-actions", "release-notes", "docs-and-citations", "research", "deployment-uv-docker", "memory",
}
ROLES = {"coding", "orchestration", "research", "extraction-caller"}


class RuntimeWorkerManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((DIRECTORY / "manifest.json").read_text())
        cls.skills = cls.manifest["skills"]

    def test_schema_and_pins_are_well_formed(self):
        self.assertEqual(self.manifest["schema_version"], 1)
        self.assertEqual(self.manifest["kind"], "skills_trial_manifest")
        self.assertEqual(self.manifest["cli"]["version"], "1.7.0")
        self.assertEqual(self.manifest["cli"]["ref"], "7407f3893ad4dceab546ac002c3ef806e4000c73")
        for skill in self.skills:
            with self.subTest(skill=skill["name"]):
                self.assertRegex(skill["name"], r"^[a-z0-9][a-z0-9._-]*$")
                self.assertRegex(skill["source"], r"^[\w.-]+/[\w.-]+$")
                for key in ("ref", "tree_sha"):
                    self.assertRegex(skill[key], r"^[0-9a-f]{40}$")
                self.assertRegex(skill["skill_md_sha256"], r"^[0-9a-f]{64}$")
                self.assertTrue(all(p not in ("", ".", "..") for p in skill["path"].split("/")))
                self.assertEqual(skill["url"], f"https://github.com/{skill['source']}/tree/{skill['ref']}/{skill['path']}")
                self.assertGreater(skill["skill_md_bytes"], 0)
                self.assertGreater(skill["description_chars"], 0)
                self.assertIsInstance(skill["upstream_disable_model_invocation"], bool)
                self.assertIn(skill["status"], {"trial", "pruned"})
                if skill["status"] == "pruned":
                    self.assertTrue(skill["prune_evidence"])
                self.assertTrue(skill["scenarios"])
                self.assertTrue(set(skill["scenarios"]) <= SCENARIOS)
                self.assertTrue(skill["roles"])
                self.assertTrue(set(skill["roles"]) <= ROLES)
                self.assertIn(skill["source"] + "@" + skill["ref"], skill["merit_note"])
                self.assertIn(skill["path"] + "/SKILL.md:", skill["merit_note"])

    def test_no_duplicate_names_and_each_role_has_skills(self):
        names = [s["name"] for s in self.skills]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(self.manifest["roles"]), ROLES)
        for role in ROLES:
            self.assertTrue(any(role in s["roles"] for s in self.skills))

    def test_every_scenario_role_cell_has_real_skills_or_explicit_gap(self):
        self.assertEqual(set(self.manifest["scenarios"]), SCENARIOS)
        self.assertEqual(set(self.manifest["coverage"]), SCENARIOS)
        gap_keys = [(g["scenario"], g["role"]) for g in self.manifest["gaps"]]
        self.assertEqual(len(gap_keys), len(set(gap_keys)))
        for scenario in SCENARIOS:
            self.assertEqual(set(self.manifest["coverage"][scenario]), ROLES)
            self.assertTrue(any(scenario in s["scenarios"] for s in self.skills)
                            or any(g["scenario"] == scenario for g in self.manifest["gaps"]))
            for role in ROLES:
                expected = sorted(s["name"] for s in self.skills if s["status"] == "trial"
                                  and scenario in s["scenarios"] and role in s["roles"])
                self.assertEqual(self.manifest["coverage"][scenario][role], expected)
                self.assertEqual((scenario, role) in gap_keys, not bool(expected))
        self.assertTrue(all(g["reason"] for g in self.manifest["gaps"]))

    def test_all_existing_skills_are_reused_by_reference_without_pin_drift(self):
        base = json.loads((ROOT / "adoption/skills/manifest.json").read_text())
        reused = [s for s in self.skills if "reuse_ref" in s]
        self.assertEqual(len(reused), len(base["skills"]))
        for skill in reused:
            prefix, index = skill["reuse_ref"].rsplit("/", 1)
            self.assertEqual(prefix, "adoption/skills/manifest.json#/skills")
            old = base["skills"][int(index)]
            for key in ("name", "source", "url", "ref", "path", "tree_sha", "skill_md_sha256",
                        "skill_md_bytes", "description_chars", "upstream_disable_model_invocation"):
                self.assertEqual(skill[key], old[key], (skill["name"], key))

    def test_openhands_inventory_has_a_decision_for_every_skill(self):
        inventory = self.manifest["openhands_inventory"]
        # Pinned v0.25.0 API tree: 66 skills/ files + 18 plugin skill entrypoints.
        self.assertEqual(len(inventory), 84)
        selected = {s["path"] for s in self.skills if s["source"] == "OpenHands/extensions"}
        excluded = {s["path"] for s in self.manifest["excluded"] if s["source"] == "OpenHands/extensions"}
        self.assertEqual(selected | excluded, {row["path"] for row in inventory})
        self.assertFalse(selected & excluded)
        for row in inventory:
            self.assertEqual(row["selected"], row["path"] in selected)
        self.assertTrue(all(s["reason"] for s in self.manifest["excluded"]))

    def test_superpowers_lifecycle_and_collisions_are_explicit(self):
        lifecycle = {"brainstorming", "writing-plans", "executing-plans", "test-driven-development",
                     "systematic-debugging", "using-git-worktrees", "dispatching-parallel-agents",
                     "subagent-driven-development", "requesting-code-review", "receiving-code-review",
                     "finishing-a-development-branch", "verification-before-completion",
                     "using-superpowers", "writing-skills", "diagnosing-superpowers"}
        self.assertEqual({s["name"] for s in self.skills if s["source"] == "obra/superpowers"}, lifecycle)
        by_name = {s["name"]: s for s in self.skills}
        for collision in self.manifest["collisions"]:
            winner = by_name[collision["name"]]
            self.assertTrue(collision["reason"])
            self.assertTrue(collision["alternatives"])
            self.assertEqual(collision["selected"], {key: winner[key] for key in ("source", "ref", "path")})

    def test_budget_is_catalog_metadata_and_native_tokens_remain_unknown(self):
        budget = self.manifest["budget"]
        self.assertEqual(budget["selected_count"], len(self.skills))
        self.assertEqual(budget["skill_md_bytes"], sum(s["skill_md_bytes"] for s in self.skills))
        self.assertEqual(budget["description_chars"], sum(s["description_chars"] for s in self.skills))
        self.assertIsNone(budget["provider_input_tokens_before"])
        self.assertIsNone(budget["provider_input_tokens_after"])

    def test_worker_installation_uses_extended_installer_without_hand_copy(self):
        readme = (DIRECTORY / "README.md").read_text()
        for target in ("OpenHands", "DeerFlow", "GPT Researcher", "crawl4ai"):
            self.assertIn(target, readme)
        self.assertIn("tools/adoption/install_skills.py", readme)
        for flag in ("--manifest", "--project-dir", "--agent", "--check-only"):
            self.assertIn(flag, readme)
        code_blocks = re.findall(r"```(?:bash|sh)\n(.*?)```", readme, re.S)
        self.assertFalse(any(re.search(r"(?m)^\s*(?:cp|rsync)\s", block) for block in code_blocks))
        source = (ROOT / "tools/adoption/install_skills.py").read_text()
        calls = [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Call)]
        self.assertFalse(any(isinstance(c.func, ast.Attribute) and c.func.attr in
                             {"write_text", "write_bytes", "copytree", "copyfile"} for c in calls))

    def test_readme_matrix_matches_manifest_including_empty_cells(self):
        table = (DIRECTORY / "README.md").read_text().split("<!-- coverage-table -->", 1)[1]
        rows = [line for line in table.splitlines() if line.startswith("| ")][2:]
        self.assertEqual(len(rows), len(SCENARIOS))
        for row in rows:
            scenario, *cells = [cell.strip() for cell in row.strip("|").split("|")]
            self.assertEqual(len(cells), len(ROLES))
            for role, cell in zip(self.manifest["roles"], cells):
                names = self.manifest["coverage"][scenario][role]
                self.assertEqual(re.findall(r"`([^`]+)`", cell), names)
                self.assertEqual("**GAP**" in cell, not bool(names))

    def test_freshness_workflow_is_report_only_and_actions_are_sha_pinned(self):
        workflow = (ROOT / ".github/workflows/runtime-worker-skills-freshness.yml").read_text()
        self.assertIn("schedule:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn(": write", workflow)
        self.assertNotRegex(workflow, r"(?m)^\s*(?:git push|gh pr|skills check|skills update)\b")
        for action in re.findall(r"uses:\s*(\S+)", workflow):
            self.assertRegex(action, r"^[\w./-]+@[0-9a-f]{40}$")
        self.assertIn("tools/adoption/runtime_skill_freshness.py", workflow)


_SPEC = importlib.util.spec_from_file_location("runtime_skill_freshness", ROOT / "tools/adoption/runtime_skill_freshness.py")
freshness = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(freshness)


class FreshnessComparisonTests(unittest.TestCase):
    def test_head_movement_is_distinct_from_skill_change_and_native_check(self):
        skill = {"name": "sample", "source": "example/skills", "path": "skills/sample",
                 "status": "trial", "ref": "a" * 40, "tree_sha": "1" * 40}
        upstream = {"head": "b" * 40, "trees": {
            "a" * 40: {"skills/sample": "1" * 40}, "b" * 40: {"skills/sample": "1" * 40}}}
        result = freshness.compare_skill(skill, upstream)
        self.assertEqual(result["state"], "repository-drift")
        self.assertFalse(result["native_check_advances_commit_pin"])
        self.assertEqual(result["native_check_ref"], "a" * 40)
        upstream["trees"]["b" * 40]["skills/sample"] = "2" * 40
        self.assertEqual(freshness.compare_skill(skill, upstream)["state"], "skill-drift")
        upstream["trees"]["b" * 40] = {}
        self.assertEqual(freshness.compare_skill(skill, upstream)["state"], "removed-at-head")
        upstream["trees"]["a" * 40] = {}
        self.assertEqual(freshness.compare_skill(skill, upstream)["state"], "invalid-pin")

    def test_fetch_failure_stays_unknown_not_current(self):
        def unavailable(endpoint):
            raise ValueError("unavailable")
        manifest = {"cli": {"version": "1.7.0"}, "skills": [{
            "name": "sample", "source": "example/skills", "path": "skills/sample",
            "status": "trial", "ref": "a" * 40, "tree_sha": "1" * 40}]}
        report = freshness.build_report(manifest, api=unavailable)
        self.assertFalse(report["ok"])
        self.assertEqual(report["skills"][0]["state"], "unfetched")
        self.assertIsNone(report["skills"][0]["manifest_tree_matches_pin"])
        self.assertFalse(report["native_check"]["executed"])

    def test_truncated_tree_is_rejected(self):
        def truncated(endpoint):
            return {"sha": "a" * 40} if endpoint.endswith("HEAD") else {"tree": [], "truncated": True}
        result = freshness.fetch_source("example/skills", ["a" * 40], api=truncated)
        self.assertEqual(result["trees"], {})
        self.assertIn("incomplete", result["errors"][0])


if __name__ == "__main__":
    unittest.main()
