"""Structural/source-contract checks, not native worker or upstream acceptance."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "blueprints/runtime-workers/skills"
ADOPTION_MANIFEST = ROOT / "adoption/skills/manifest.json"
# A reuse_ref or adoption_ref names main's adoption manifest; the entry is matched there by skill name,
# so main can reorder or insert skills without moving a reference.
ADOPTION_REF = "adoption/skills/manifest.json"
SCENARIOS = {
    "planning-and-specs", "tdd", "e2e-testing", "ab-testing-and-evaluation", "debugging",
    "code-review", "security", "github-issue-to-pr", "github-pr-review", "github-ci-fix",
    "github-actions", "release-notes", "docs-and-citations", "research", "deployment-uv-docker", "memory",
}
ROLES = {"coding", "orchestration", "research", "extraction-caller"}
PIN_KEYS = ("name", "source", "url", "ref", "path", "tree_sha", "skill_md_sha256",
            "skill_md_bytes", "description_chars", "upstream_disable_model_invocation")
# Main's per-skill gates. A reused entry never restates them; the installer reads them from main.
GATE_KEYS = ("codex_enabled", "claude_listing")


def adoption_contract_problems(runtime: dict, base: dict) -> list[str]:
    """Each skill in main's adoption manifest is claimed exactly once, by name: reused by `reuse_ref`
    (pins equal to main's, gates not restated) or excluded by `adoption_ref` (with a reason
    and an overturn condition). Returns one line per violation; empty means the contract holds."""
    problems = []
    main_names = [old["name"] for old in base["skills"]]
    claims: dict[str, list[tuple[str, dict]]] = {}
    for kind, entries, key in (("reused", runtime["skills"], "reuse_ref"),
                               ("excluded", runtime["excluded"], "adoption_ref")):
        for entry in entries:
            if key not in entry:
                continue
            if entry[key] != ADOPTION_REF or main_names.count(entry.get("name")) != 1:
                problems.append(f"{entry.get('name')}: {key} {entry[key]!r} names no single main adoption skill")
                continue
            claims.setdefault(entry["name"], []).append((kind, entry))
    for old in base["skills"]:
        entries = claims.get(old["name"], [])
        if len(entries) != 1:
            kinds = ", ".join(kind for kind, _ in entries) or "neither reused nor excluded"
            problems.append(f"{old['name']}: {kinds}")
            continue
        kind, entry = entries[0]
        if kind == "reused":
            problems += [f"{old['name']}: reused {key} differs from main" for key in PIN_KEYS
                         if entry.get(key) != old.get(key)]
            problems += [f"{old['name']}: reused entry restates main's {key}" for key in GATE_KEYS
                         if key in entry]
        else:
            if (entry.get("name"), entry.get("source")) != (old["name"], old["source"]):
                problems.append(f"{old['name']}: exclusion names {entry.get('name')!r} from {entry.get('source')!r}")
            problems += [f"{old['name']}: exclusion lacks {key}" for key in ("reason", "overturn")
                         if not entry.get(key)]
    return problems


class RuntimeWorkerManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((DIRECTORY / "manifest.json").read_text())
        cls.skills = cls.manifest["skills"]

    def test_schema_and_pins_are_well_formed(self):
        self.assertEqual(self.manifest["schema_version"], 1)
        self.assertEqual(self.manifest["kind"], "skills_trial_manifest")
        self.assertEqual(self.manifest["scope"], "project")  # the installer refuses it without --project-dir
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

    def test_source_counts_match_the_selected_skills_and_the_research_table(self):
        counted = {}
        for skill in self.skills:
            counted[skill["source"]] = counted.get(skill["source"], 0) + 1
        self.assertEqual({s["source"]: s["selected_skills"] for s in self.manifest["sources"]}, counted)
        table = (DIRECTORY / "research.md").read_text().split("<!-- source-pins -->", 1)[1]
        rows = [line for line in table.splitlines() if line.startswith("| ")][2:]
        parsed = {}
        for row in rows:
            repository, ref, count = [cell.strip() for cell in row.strip("|").split("|")]
            parsed[repository] = (ref.strip("`"), int(count))
        self.assertEqual(parsed, {s["source"]: (s["ref"], s["selected_skills"]) for s in self.manifest["sources"]})

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

    def test_every_adoption_skill_is_reused_or_explicitly_excluded(self):
        base = json.loads(ADOPTION_MANIFEST.read_text())
        self.assertEqual(adoption_contract_problems(self.manifest, base), [])

    def test_contract_rejects_a_future_main_skill_in_neither_set(self):
        # Negative control: a skill main adds later that is neither reused nor excluded must fail.
        base = json.loads(ADOPTION_MANIFEST.read_text())
        base["skills"].append(dict(base["skills"][0], name="future-main-skill"))
        self.assertEqual(adoption_contract_problems(self.manifest, base),
                         ["future-main-skill: neither reused nor excluded"])

    def test_contract_survives_main_reordering_its_skills(self):
        # References are matched by name, so a reorder on main moves no claim.
        base = json.loads(ADOPTION_MANIFEST.read_text())
        base["skills"].reverse()
        self.assertEqual(adoption_contract_problems(self.manifest, base), [])

    def test_contract_rejects_double_claims_restated_gates_and_bare_exclusions(self):
        base = json.loads(ADOPTION_MANIFEST.read_text())
        runtime = copy.deepcopy(self.manifest)
        reused = [s for s in runtime["skills"] if "reuse_ref" in s]
        double, restating, bare_skill = reused[0], reused[1], reused[2]
        runtime["excluded"].append({"name": double["name"], "source": double["source"],
                                    "adoption_ref": double["reuse_ref"], "reason": "r", "overturn": "o"})
        restating["codex_enabled"] = True
        # Build a bare exclusion independently of the host-research exclusion: one reused skill claimed
        # only by an exclusion without an overturn condition must still fail.
        runtime["skills"].remove(bare_skill)
        bare = {"name": bare_skill["name"], "source": bare_skill["source"], "adoption_ref": ADOPTION_REF,
                "reason": "r"}
        runtime["excluded"].append(bare)
        problems = adoption_contract_problems(runtime, base)
        self.assertIn(f"{double['name']}: reused, excluded", problems)
        self.assertIn(f"{restating['name']}: reused entry restates main's codex_enabled", problems)
        self.assertIn(f"{bare['name']}: exclusion lacks overturn", problems)

    def test_security_audit_is_reused_since_main_promoted_it(self):
        # Main promoted security-audit on 2026-09-30 (listing on, Codex enabled;
        # docs/decisions/2026-09-30-skills-llm-native-listing.md), which met the #448 exclusion's overturn:
        # the exclusion became a reuse_ref entry with its own scenarios and roles.
        self.assertFalse([e for e in self.manifest["excluded"] if e.get("name") == "security-audit"])
        entry = next((s for s in self.skills if s["name"] == "security-audit"), None)
        self.assertIsNotNone(entry, "main promoted security-audit: the runtime must reuse it")
        self.assertEqual(entry.get("reuse_ref"), ADOPTION_REF)
        self.assertEqual((entry["scenarios"], entry["roles"]), (["security"], ["coding", "orchestration"]))
        gate = {s["name"]: s for s in json.loads(ADOPTION_MANIFEST.read_text())["skills"]}["security-audit"]
        # Review trigger: a later change to main's gate fails here; a demotion needs a new review of the reuse.
        self.assertEqual((gate["codex_enabled"], gate["claude_listing"]), (True, "on"),
                         "main changed security-audit's gate again: review the reuse")

    def test_verification_before_completion_stays_excluded_until_main_readmits_it(self):
        name = "verification-before-completion"
        base = json.loads(ADOPTION_MANIFEST.read_text())

        def listed(entry):
            names = entry.get("skills")
            return [names] if isinstance(names, str) else list(names or [])

        # Overturn trigger: main re-admitting the skill fails here, and the coverage contract then finds
        # it neither reused nor excluded. Replace this exclusion with a reuse_ref entry at main's new pin.
        self.assertNotIn(name, [s["name"] for s in base["skills"]],
                         "main re-admitted verification-before-completion: overturn the runtime exclusion")
        self.assertTrue(any(name in listed(e) and e.get("source") == "obra/superpowers"
                            for e in base["excluded"]))
        exclusion = next((e for e in self.manifest["excluded"] if e.get("name") == name), None)
        self.assertIsNotNone(exclusion, "main excludes verification-before-completion; the runtime must too")
        self.assertEqual(exclusion["source"], "obra/superpowers")
        self.assertNotIn("adoption_ref", exclusion)  # main lists it under excluded, not under skills
        self.assertNotIn(name, [s["name"] for s in self.skills])
        for cited in ("#464", "M4", "AGENTS.md:16", "Reuse passing evidence when its inputs still match"):
            self.assertIn(cited, exclusion["reason"], cited)
        self.assertIn("re-admits", exclusion["overturn"])

    def test_print_codex_config_disables_every_reused_skill_main_disables(self):
        base = {s["name"]: s for s in json.loads(ADOPTION_MANIFEST.read_text())["skills"]}
        expected = sorted(
            [s["name"] for s in self.skills
             if "reuse_ref" in s and base[s["name"]].get("codex_enabled") is False]
            + [s["name"] for s in self.skills if "reuse_ref" not in s and s.get("codex_enabled") is False])
        self.assertTrue(expected)  # non-vacuous: main keeps some reused skills off for Codex
        command = [sys.executable, str(ROOT / "tools/adoption/install_skills.py"),
                   "--manifest", str(DIRECTORY / "manifest.json"), "--print-codex-config"]
        # Each table names the project's installed SKILL.md (a name rule would also hide Codex's bundled
        # skill-creator), so this project-scoped manifest prints only with --project-dir.
        refused = subprocess.run(command, capture_output=True, text=True, check=False, timeout=60)
        self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
        self.assertIn("--project-dir", refused.stderr)
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            result = subprocess.run([*command, "--project-dir", str(project)],
                                    capture_output=True, text=True, check=False, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        tables = tomllib.loads(result.stdout).get("skills", {}).get("config", [])
        names = [Path(table.get("path", "")).parent.name for table in tables]
        self.assertEqual(sorted(names), expected)
        self.assertEqual(tables, [{"path": str(project / ".agents" / "skills" / name / "SKILL.md"), "enabled": False}
                                  for name in names])
        self.assertNotRegex(result.stdout, r"(?m)^name = ")

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
        # The 15 skills of the pinned superpowers tree: each is selected or excluded, never both.
        lifecycle = {"brainstorming", "writing-plans", "executing-plans", "test-driven-development",
                     "systematic-debugging", "using-git-worktrees", "dispatching-parallel-agents",
                     "subagent-driven-development", "requesting-code-review", "receiving-code-review",
                     "finishing-a-development-branch", "verification-before-completion",
                     "using-superpowers", "writing-skills", "diagnosing-superpowers"}
        selected = {s["name"] for s in self.skills if s["source"] == "obra/superpowers"}
        excluded = {e["name"] for e in self.manifest["excluded"] if e["source"] == "obra/superpowers"}
        self.assertEqual(excluded, {"verification-before-completion"})  # main's M4 removal, #464
        self.assertEqual(selected | excluded, lifecycle)
        self.assertFalse(selected & excluded)
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

    def test_prune_contract_records_claude_listing_budget_and_unknown_visibility(self):
        readme = (DIRECTORY / "README.md").read_text()
        for required in ("skillListingBudgetFraction", "SLASH_COMMAND_TOOL_CHAR_BUDGET",
                         "/context", "excluded-skill warnings", "uninstrumented (unknown)"):
            self.assertIn(required, readme, required)
        self.assertIn("description visibility", readme)

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
        manifest = {"cli": {"version": "1.7.0", "ref": "7407f3893ad4dceab546ac002c3ef806e4000c73"}, "skills": [{
            "name": "sample", "source": "example/skills", "path": "skills/sample",
            "status": "trial", "ref": "a" * 40, "tree_sha": "1" * 40}]}
        report = freshness.build_report(manifest, api=unavailable)
        self.assertFalse(report["ok"])
        self.assertEqual(report["skills"][0]["state"], "unfetched")
        self.assertIsNone(report["skills"][0]["manifest_tree_matches_pin"])
        self.assertFalse(report["native_check"]["executed"])

    def test_cli_version_and_ref_come_from_the_manifest_pin(self):
        # A pin bump in the manifest must not need a code edit here, and must not fail as a version mismatch.
        ref, head = "c" * 40, "d" * 40
        skill = {"name": "sample", "source": "example/skills", "path": "skills/sample",
                 "status": "trial", "ref": "a" * 40, "tree_sha": "1" * 40}

        def api(endpoint):
            if endpoint == "repos/vercel-labs/skills/releases/latest":
                return {"tag_name": "v9.9.9"}
            if endpoint.endswith("/commits/HEAD"):
                return {"sha": head}
            return {"tree": [{"path": "skills/sample", "type": "tree", "sha": "1" * 40}], "truncated": False}

        report = freshness.build_report({"cli": {"version": "9.9.9", "ref": ref}, "skills": [skill]}, api=api)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["cli"], {"pinned": "9.9.9", "latest": "v9.9.9", "drift": False})
        self.assertEqual((report["native_check"]["pinned_version"], report["native_check"]["pinned_ref"]),
                         ("9.9.9", ref))
        self.assertIn(f"/blob/{ref}/", report["native_check"]["source"])
        markdown = freshness.render_markdown(report)
        self.assertIn("9.9.9", markdown)
        self.assertNotIn("1.7.0", json.dumps(report) + markdown)
        for broken in ({"version": "9.9.9"}, {"version": "", "ref": ref}, {"version": "9.9.9", "ref": "main"}):
            with self.subTest(cli=broken):
                report = freshness.build_report({"cli": broken, "skills": [skill]}, api=api)
                self.assertFalse(report["ok"])
                self.assertTrue(any("cli pin" in error for error in report["errors"]), report["errors"])

    def test_truncated_tree_is_rejected(self):
        def truncated(endpoint):
            return {"sha": "a" * 40} if endpoint.endswith("HEAD") else {"tree": [], "truncated": True}
        result = freshness.fetch_source("example/skills", ["a" * 40], api=truncated)
        self.assertEqual(result["trees"], {})
        self.assertIn("incomplete", result["errors"][0])


if __name__ == "__main__":
    unittest.main()
