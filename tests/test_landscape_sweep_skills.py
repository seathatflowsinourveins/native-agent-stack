"""Synthetic-fixture tests for the landscape sweep's skills modality (tools/sota-convergence/landscape-sweep; no
network, no codex, no model calls).

Covered: the skills lifecycle catalog, the strict discover-skills return schema, skills layer inputs and their frozen
scope, each modality's own history and baseline, the templates a skills-* layer resolves to, a skills run staged by
build_args.py and run by sweep.js under node (skipped without node), agents/openai.yaml as Codex reads it (the subset
reader always, the PyYAML reader when PyYAML is installed), SKILL.md copies as skill_md.mjs judges them (the pinned
skills CLI's parseSkillMd with the yaml install skills-yaml.pin.json pins), source reviews of skill survivors against a
fake gh whose git trees carry the object ids git itself computes (git is required), make_result.py's pin checks of a
skills RESULT.json, and the decision record it writes. Tests that run skill_md.mjs need node and a verified yaml install
(LANDSCAPE_SWEEP_SKILLS_YAML, else the pin's default directory under HOME; install it with the pin's command) and skip
with that reason without one, as the tree-sitter lane tests do; the fail-closed checks run without it. Schemas are
validated with scripts/host_receipts.py's validator (the repository's JSON Schema subset; CI installs no jsonschema),
and with jsonschema as well when it is installed.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import host_receipts  # noqa: E402  (the repository's JSON Schema subset validator)
import saturation_ledger as sl  # noqa: E402
import tests.test_landscape_sweep_harness as harness_tests  # noqa: E402  (helpers only; its test classes run there)
import tests.test_shell_parser_ci as shell_ci  # noqa: E402  (the tree-sitter pin's CI helpers; its tests run there)

HARNESS = harness_tests.HARNESS
CATALOG = ROOT / "catalogs" / "landscape" / "skills-lifecycle.json"
SKILLS_SCHEMA = HARNESS / "schemas" / "discover-skills.json"
SKILLS_MANIFEST = ROOT / "adoption" / "skills" / "manifest.json"
build_args, build_inputs, convert = harness_tests.build_args, harness_tests.build_inputs, harness_tests.convert
make_prompt, make_result, sweep_common = harness_tests.make_prompt, harness_tests.make_result, harness_tests.sweep_common
usage_record = harness_tests.usage_record
run, write_json, temp_dir = harness_tests.run, harness_tests.write_json, harness_tests.temp_dir
REQ, PLAT, LANE = harness_tests.REQ, harness_tests.PLAT, "landscape-sweep-skills-20260930"
TASKS = ("research", "skill-lifecycle", "design-intake", "architecture", "implement", "test", "debug", "review",
         "security", "ci-pr", "agent-docs", "browser", "mcp-build")
HEX40, HEX64 = re.compile(r"[0-9a-f]{40}"), re.compile(r"[0-9a-f]{64}")


def manifest_repositories(value: str) -> list[str]:
    """owner/repo values of a skills-manifest source field ("a/b, c/d", "o/r (skill-data/)"); "various" names none."""
    out = []
    for part in value.split(","):
        part = re.sub(r"\s*\(.*\)$", "", part.strip())
        if re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+", part):
            out.append(part.lower())
    return out


def skill_proposal(skill_ref="acme/agent-skills@debug-kit", **changes) -> dict:
    """A proposal that discover-skills.json accepts."""
    repository = skill_ref.split("@", 1)[0]
    proposal = {"skill_ref": skill_ref, "source_id": "unlisted", "lifecycle_task": "debug", "pin": "a" * 40,
                "skill_md_sha256": "b" * 64, "license": "MIT", "source": "fixture", "description_chars": 120,
                "model_invocable": True, "codex_implicit": True, "replaces": "diagnosing-bugs",
                "proposed_label": "keep_but_compare", "demonstrated_gap": f"gap of {skill_ref}",
                "evidence": [f"https://github.com/{repository}/blob/{'a' * 40}/SKILL.md shows it"],
                "upstream_now": {"latest_release": None, "released_at": None, "stars": 10,
                                 "pushed_at": "2026-09-29T00:00:00Z", "archived": False, "license": "MIT"},
                "comparison_that_would_overturn": "skill-creator's paired with-skill/without-skill benchmark on ten "
                                                  f"frozen debug prompts decides {skill_ref}"}
    proposal.update(changes)
    return proposal


def skills_discovery(layer_id, proposals, skills=("search-first",)) -> dict:
    return {"layer_id": layer_id, "proposed": list(proposals), "calls": {"web_search": 2, "web_fetch": 1, "gh_api": 9},
            "notes": "", "skills_used": list(skills)}


def schema_errors(instance) -> list[str]:
    errors: list[str] = []
    host_receipts.validate_against_schema(instance, json.loads(SKILLS_SCHEMA.read_text(encoding="utf-8")), "$", errors)
    return errors


# --------------------------------------------------------------------------- the committed catalog


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        self.manifest = json.loads(SKILLS_MANIFEST.read_text(encoding="utf-8"))

    def test_catalog_shape_tasks_and_pins(self):
        catalog = self.catalog
        self.assertEqual((catalog["schema_version"], catalog["kind"], catalog["checked_at"]),
                         (1, "skills-lifecycle", "2026-09-30"))
        self.assertEqual([task["lifecycle_task"] for task in catalog["tasks"]], list(TASKS))
        for task in catalog["tasks"]:
            self.assertEqual(task["layer_id"], f"skills-{task['lifecycle_task']}")
            self.assertEqual(sorted(task), ["installed", "layer_id", "lifecycle_task", "open_gaps", "overturn_when",
                                            "requirement", "source_ids"], task["layer_id"])
            self.assertIn("skill-creator", task["overturn_when"], task["layer_id"])
        for source in catalog["sources"]:
            self.assertEqual(sorted(set(source) - {"maintenance"}), ["kind", "pin", "source_id", "url"])
            self.assertIn(source["kind"], build_inputs.SOURCE_KINDS)
            self.assertRegex(source["pin"], HEX40)
        kinds = {source["source_id"]: source["kind"] for source in catalog["sources"]}
        self.assertEqual(kinds["skills-sh-registry"], "registry")
        self.assertEqual(kinds["composiohq-awesome-claude-skills"], "awesome-list")
        # host_receipts.landscape_winners reads layers[].winners[] of every catalogs/landscape/*.json: tasks, not layers.
        self.assertNotIn("layers", catalog)
        self.assertEqual(build_inputs.check_skills_catalog(catalog, self.manifest), [])

    def test_every_manifest_source_and_the_named_sources_are_listed(self):
        listed = {re.sub(r"^https://github\.com/", "", s["url"]).lower() for s in self.catalog["sources"]}
        wanted = set()
        for entry in [*self.manifest["skills"], *self.manifest["excluded"]]:
            wanted.update(manifest_repositories(entry["source"]))
        wanted.update({"anthropics/skills", "vercel-labs/skills", "openai/skills", "trailofbits/skills",
                       "obra/superpowers", "mattpocock/skills", "affaan-m/ecc", "cloudflare/security-audit-skill",
                       "microsoft/skills", "huggingface/skills", "bgauryy/octocode",
                       "composiohq/awesome-claude-skills", "https://skills.sh"})
        self.assertEqual(sorted(wanted - listed), [])

    def test_every_pinned_skill_serves_exactly_one_task(self):
        served = [name for task in self.catalog["tasks"] for name in task["installed"]]
        self.assertEqual(sorted(served), sorted(skill["name"] for skill in self.manifest["skills"]))
        self.assertEqual(len(served), len(set(served)))

    def test_open_gaps_state_the_pinned_codex_and_claude_flags(self):
        # Each layer input carries the installed skills' codex_enabled and claude_listing from the manifest beside the
        # task's open gaps (build_inputs.py), so a gap that states one of those flags names the skills it is about and
        # agrees with the manifest. Unit F3 (#553) changed both flags for many skills on 2026-09-30 and left gaps here
        # saying "disabled in Codex (codex_enabled false)" of skills it had enabled.
        pinned = {skill["name"]: skill for skill in self.manifest["skills"]}
        claims = {"codex_enabled": (r"codex_enabled false|disabled in Codex",
                                    lambda skill: skill["codex_enabled"] is False),
                  "claude_listing": (r"name-only|user-invocable-only|user-invoked only",
                                     lambda skill: skill["claude_listing"] != "on")}
        stated = {field: 0 for field in claims}
        for task in self.catalog["tasks"]:
            for gap in task["open_gaps"]:
                named = build_args.skill_mentions(gap, pinned)
                for field, (pattern, holds) in claims.items():
                    if not re.search(pattern, gap):
                        continue
                    stated[field] += 1
                    with self.subTest(layer=task["layer_id"], field=field, gap=gap[:80]):
                        self.assertTrue(named, f"names no pinned skill: {gap}")
                        for name in named:
                            self.assertTrue(holds(pinned[name]),
                                            f"{name} {field} is {pinned[name][field]!r} in the manifest: {gap}")
        # The Codex kind is stated today (skill-creator off in Codex), so its pattern still matches the catalog's wording.
        # The listing kind is not: its two user-invocable-only skills, grill-me and improve-codebase-architecture, were
        # retired on 2026-10-03 (wave-2 skills ruling, change 1), and no pinned skill has a listing other than on.
        self.assertEqual({field: count > 0 for field, count in stated.items()},
                         {"codex_enabled": True, "claude_listing": False})
        self.assertEqual([skill["name"] for skill in self.manifest["skills"] if skill["claude_listing"] != "on"], [])

    def test_tasks_that_need_model_invocation_say_so(self):
        tasks = {task["lifecycle_task"]: task for task in self.catalog["tasks"]}
        for name in ("design-intake", "architecture"):
            self.assertIn("must be model-invocable", tasks[name]["requirement"], name)

    def test_catalog_problems_are_reported(self):
        broken = copy.deepcopy(self.catalog)
        broken["tasks"][0]["installed"].append("not-a-pinned-skill")
        broken["tasks"][1]["source_ids"].append("no-such-source")
        broken["tasks"][2]["layer_id"] = "skills-other"
        broken["sources"][0]["pin"] = "main"
        broken["sources"][1]["kind"] = "blog"
        broken["sources"][2]["maintenance"] = {"status": "unmaintained", "checked_at": "2026-09-30", "evidence": "x"}
        broken["sources"][3]["maintenance"] = {"status": "stale", "checked_at": "30 Sep", "evidence": "x"}
        broken["sources"][4]["notes"] = "an unknown field"
        broken["tasks"].append(copy.deepcopy(broken["tasks"][3]))
        problems = "\n".join(build_inputs.check_skills_catalog(broken, self.manifest))
        for fragment in ("not-a-pinned-skill", "no-such-source", "skills-other", "40-hex", "blog",
                         "skills-architecture", f"{broken['sources'][2]['source_id']!r}: maintenance must be",
                         f"{broken['sources'][3]['source_id']!r}: maintenance must be",
                         f"{broken['sources'][4]['source_id']!r}: needs exactly"):
            self.assertIn(fragment, problems)

    def test_a_stale_source_is_marked_and_kept_for_its_installed_skills(self):
        # openai/skills has no main commit since 2026-06-24 (98 days before 2026-09-30): stale under the common
        # block's 90-day maintenance rule. It stays a source and keeps its four installed skills; the tasks they serve
        # say so as an open gap, and the discover template labels a stale source's skills not_adopted.
        sources = {source["source_id"]: source for source in self.catalog["sources"]}
        record = sources["openai-skills"]["maintenance"]
        self.assertEqual((record["status"], record["checked_at"]), ("stale", "2026-09-30"))
        for fact in ("since=2026-07-02T00:00:00Z", "49f948faa9258a0c61caceaf225e179651397431", "2026-06-24T02:36:12Z",
                     "pushed_at"):
            self.assertIn(fact, record["evidence"])
        self.assertEqual([source_id for source_id, source in sources.items() if "maintenance" in source],
                         ["openai-skills"])
        openai = sorted(skill["name"] for skill in self.manifest["skills"] if skill["source"] == "openai/skills")
        self.assertEqual(openai, ["gh-address-comments", "gh-fix-ci", "security-best-practices",
                                  "security-threat-model"])
        tasks = {task["lifecycle_task"]: task for task in self.catalog["tasks"]}
        for name in ("ci-pr", "security"):
            self.assertTrue(any(gap.startswith("Stale source: replacement via this sweep.")
                                for gap in tasks[name]["open_gaps"]), name)
        served = sorted(name for task in self.catalog["tasks"] for name in task["installed"] if name in openai)
        self.assertEqual(served, openai)
        self.assertEqual(sorted(task["lifecycle_task"] for task in self.catalog["tasks"]
                                if "openai-skills" in task["source_ids"]),
                         ["browser", "ci-pr", "design-intake", "security", "skill-lifecycle"])


# --------------------------------------------------------------------------- the strict return schema


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(SKILLS_SCHEMA.read_text(encoding="utf-8"))

    def test_schema_is_strict_requires_every_property_and_uses_supported_keywords(self):
        self.assertIn("skills_used", self.schema["required"])
        for node in host_receipts.schema_nodes(self.schema):
            unknown = set(node) - host_receipts.SCHEMA_SUPPORTED_KEYWORDS - host_receipts.SCHEMA_META_KEYWORDS
            self.assertEqual(unknown, set(), node)
            if "properties" in node:  # Codex strict output schemas: every object closed, every property required
                self.assertIs(node.get("additionalProperties"), False, sorted(node["properties"]))
                self.assertEqual(sorted(node["required"]), sorted(node["properties"]))
        proposal = self.schema["properties"]["proposed"]["items"]["properties"]
        for field in ("skill_ref", "source_id", "lifecycle_task", "pin", "skill_md_sha256", "license", "source",
                      "description_chars", "model_invocable", "codex_implicit", "replaces", "proposed_label",
                      "demonstrated_gap", "evidence", "upstream_now", "comparison_that_would_overturn"):
            self.assertIn(field, proposal)
        discover = json.loads((HARNESS / "schemas" / "discover.json").read_text(encoding="utf-8"))
        repository = discover["properties"]["proposed"]["items"]["properties"]
        self.assertEqual(proposal["proposed_label"], repository["proposed_label"])
        self.assertEqual(proposal["upstream_now"], repository["upstream_now"])
        self.assertEqual(self.schema["properties"]["calls"], discover["properties"]["calls"])

    def test_known_pass(self):
        self.assertEqual(schema_errors(skills_discovery("skills-debug", [skill_proposal()])), [])
        unknown = skill_proposal(skill_md_sha256=None, license=None, replaces=None, model_invocable=False,
                                 codex_implicit=False, comparison_that_would_overturn="a promptfoo config over the "
                                                                                      "frozen prompts decides it")
        self.assertEqual(schema_errors(skills_discovery("skills-debug", [unknown])), [])

    def test_known_fail_missing_model_invocable(self):
        proposal = skill_proposal()
        del proposal["model_invocable"]
        errors = schema_errors(skills_discovery("skills-debug", [proposal]))
        self.assertEqual(errors, ["$.proposed[0]: missing required key 'model_invocable'"])

    def test_malformed_returns_are_refused(self):
        cases = {
            "skill_ref as a URL": skill_proposal(skill_ref="https://github.com/acme/agent-skills@debug-kit"),
            "skill_ref without a skill": skill_proposal(skill_ref="acme/agent-skills"),
            "pin not a commit": skill_proposal(pin="main"),
            "sha256 upper case": skill_proposal(skill_md_sha256="B" * 64),
            "comparison names no benchmark": skill_proposal(comparison_that_would_overturn="compare them later"),
            "negative description_chars": skill_proposal(description_chars=-1),
            "model_invocable as text": skill_proposal(model_invocable="yes"),
            "task outside the catalog": skill_proposal(lifecycle_task="deploy"),
            "label outside the enum": skill_proposal(proposed_label="adopt_now"),
            "extra property": skill_proposal(repository="https://github.com/acme/agent-skills"),
        }
        for name, proposal in cases.items():
            with self.subTest(name):
                self.assertNotEqual(schema_errors(skills_discovery("skills-debug", [proposal])), [])
        self.assertNotEqual(schema_errors(skills_discovery("alpha", [skill_proposal()])), [])  # not a skills-* layer
        self.assertNotEqual(schema_errors({"layer_id": "skills-debug", "proposed": "none"}), [])

    def test_lifecycle_task_enum_is_the_catalog_task_list(self):
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        enum = self.schema["properties"]["proposed"]["items"]["properties"]["lifecycle_task"]["enum"]
        self.assertEqual(enum, [task["lifecycle_task"] for task in catalog["tasks"]])

    def test_jsonschema_agrees_when_available(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed; host_receipts.validate_against_schema is the enforced check")
        jsonschema.Draft202012Validator.check_schema(self.schema)
        validator = jsonschema.Draft202012Validator(self.schema)
        self.assertEqual(list(validator.iter_errors(skills_discovery("skills-debug", [skill_proposal()]))), [])
        broken = skill_proposal()
        del broken["model_invocable"]
        self.assertNotEqual(list(validator.iter_errors(skills_discovery("skills-debug", [broken]))), [])


# --------------------------------------------------------------------------- skills layer inputs and scope


def skills_repo(case) -> Path:
    """A synthetic checkout: a two-task skills catalog, a skills manifest, the adoption profiles and an empty ledger."""
    repo = temp_dir(case)
    write_json(repo / "catalogs/landscape/skills-lifecycle.json", {
        "schema_version": 1, "kind": "skills-lifecycle", "checked_at": "2026-09-30", "sources": [
            {"source_id": "o-skills", "kind": "github-skills-repo", "url": "https://github.com/o/skills", "pin": "c" * 40},
            {"source_id": "skills-sh-registry", "kind": "registry", "url": "https://skills.sh", "pin": "d" * 40}],
        "tasks": [
            {"layer_id": "skills-debug", "lifecycle_task": "debug", "requirement": "debug things", "installed": ["diag"],
             "source_ids": ["o-skills", "skills-sh-registry"], "open_gaps": ["g" * 400], "overturn_when": "never"},
            {"layer_id": "skills-design-intake", "lifecycle_task": "design-intake",
             "requirement": "intake that must be model-invocable", "installed": ["grill"],
             "source_ids": ["skills-sh-registry"], "open_gaps": [], "overturn_when": "later"}]})
    skill = {"source": "o/skills", "ref": "e" * 40, "path": "skills/diag", "skill_md_sha256": "f" * 64,
             "description_chars": 100, "status": "trial", "upstream_disable_model_invocation": False,
             "claude_listing": "on", "codex_enabled": True, "license": "MIT"}
    # excluded[].skills as the committed manifest states it (one comma-separated string), plus one list-shaped entry.
    write_json(repo / "adoption/skills/manifest.json", {"checked_at": "2026-09-28", "skills": [
        {"name": "diag", **skill, "gap": "x" * 400},
        {"name": "grill", **skill, "path": "skills/grill", "upstream_disable_model_invocation": True,
         "claude_listing": "user-invocable-only", "codex_enabled": False, "gap": "user only"}],
        "excluded": [{"source": "o/skills, p/more", "skills": "old-debug, the other skills", "reason": "dup",
                      "overturn": "never"},
                     {"source": "various", "skills": "Lark/Feishu, reddit-automation and vendor-specific packs",
                      "reason": "off-domain", "overturn": "x"},
                     {"source": "o/skills", "skills": ["listed-debug"], "reason": "list-shaped", "overturn": "x"}]})
    write_json(repo / "adoption/manifest.json", {"platform_profiles": [{"id": "linux-x86_64", "os": "linux"}]})
    write_json(repo / "catalogs/saturation/ledger.json", {"sweeps": []})
    return repo


class SkillsInputTests(unittest.TestCase):
    def setUp(self):
        self.repo, self.work = skills_repo(self), temp_dir(self)

    def build(self, *extra):
        return run([sys.executable, HARNESS / "build_inputs.py", "--repo-root", self.repo, *extra])

    def freeze(self):
        done = self.build("--skills-scope")
        self.assertEqual(done.returncode, 0, done.stderr)
        write_json(self.work / "scope.json", json.loads(done.stdout))
        return json.loads(done.stdout)

    def test_skills_scope_is_the_ledger_scope_format_for_the_skills_catalog(self):
        scope = self.freeze()
        self.assertEqual(build_inputs.SKILLS_REQUIREMENT_FIELDS, ("lifecycle_task", "requirement", "overturn_when"))
        catalog = json.loads((self.repo / build_inputs.SKILLS_CATALOG).read_text())
        adoption = json.loads((self.repo / "adoption/manifest.json").read_text())
        self.assertEqual(scope, {
            "platform_profiles_sha256": sl.platform_profiles_sha256(adoption),
            "requirement_sha256": {f"skills/{task['layer_id']}": sl.sha256_bytes(sl.canonical(
                {field: task[field] for field in ("lifecycle_task", "requirement", "overturn_when")}))
                for task in catalog["tasks"]}})

    def test_skills_inputs_carry_installed_pins_sources_known_skills_and_scope(self):
        scope = self.freeze()
        seeds = write_json(self.work / "seeds.json", {"skills-debug": ["acme/agent-skills@debug-kit"]})
        done = self.build("--work-dir", self.work, "--modality", "skills", "--seeds", seeds)
        self.assertEqual(done.returncode, 0, done.stderr)
        layers = json.loads((self.work / "layers.json").read_text())
        self.assertEqual([(x["catalog"], x["layer_id"], x["modality"]) for x in layers],
                         [("skills", "skills-debug", "skills"), ("skills", "skills-design-intake", "skills")])
        debug = json.loads((self.work / "inputs/skills-debug.json").read_text())
        self.assertEqual((debug["catalog"], debug["modality"], debug["lifecycle_task"]), ("skills", "skills", "debug"))
        self.assertEqual((debug["requirement_sha256"], debug["platform_profiles_sha256"]),
                         (scope["requirement_sha256"]["skills/skills-debug"], scope["platform_profiles_sha256"]))
        # The installed skill's gap, the task's open gaps and its overturn condition pass whole (the first round cut
        # the gap at 300 characters without a marker).
        self.assertEqual(debug["installed"], [{
            "name": "diag", "source": "o/skills", "ref": "e" * 40, "path": "skills/diag", "skill_md_sha256": "f" * 64,
            "description_chars": 100, "status": "trial", "upstream_disable_model_invocation": False,
            "claude_listing": "on", "codex_enabled": True, "gap": "x" * 400}])
        self.assertEqual(debug["sources"], [
            {"source_id": "o-skills", "kind": "github-skills-repo", "url": "https://github.com/o/skills", "pin": "c" * 40},
            {"source_id": "skills-sh-registry", "kind": "registry", "url": "https://skills.sh", "pin": "d" * 40}])
        # Installed skills by repository; excluded skills by the manifest's own source text, since an excluded entry can
        # name several repositories and phrases: no owner/repo@name pair is invented from it. Each comma-separated name
        # stays whole, and a list-shaped entry is taken item by item.
        self.assertEqual(debug["known_skills"], {
            "installed": {"o/skills": ["diag", "grill"]},
            "excluded": {"o/skills": ["listed-debug"], "o/skills, p/more": ["old-debug", "the other skills"],
                         "various": ["Lark/Feishu", "reddit-automation and vendor-specific packs"]}})
        self.assertEqual(debug["seeded_candidates"], ["acme/agent-skills@debug-kit"])
        self.assertEqual((debug["previous_sweep"], debug["open_gaps"], debug["overturn_when"]), ({}, ["g" * 400], "never"))
        self.assertEqual((debug["skills_catalog_checked_at"], debug["skills_manifest_checked_at"]),
                         ("2026-09-30", "2026-09-28"))
        intake = json.loads((self.work / "inputs/skills-design-intake.json").read_text())
        self.assertIs(intake["installed"][0]["upstream_disable_model_invocation"], True)

    def test_unfrozen_layers_unknown_seeds_and_a_broken_catalog_are_refused(self):
        write_json(self.work / "scope.json", {"platform_profiles_sha256": PLAT, "requirement_sha256": {}})
        done = self.build("--work-dir", self.work, "--modality", "skills")
        self.assertEqual(done.returncode, 2)
        self.assertIn("skills/skills-debug", done.stderr)
        self.freeze()
        seeds = write_json(self.work / "seeds.json", {"alpha": ["x"]})
        done = self.build("--work-dir", self.work, "--modality", "skills", "--seeds", seeds)
        self.assertEqual(done.returncode, 2)
        self.assertIn("alpha", done.stderr)
        catalog = json.loads((self.repo / build_inputs.SKILLS_CATALOG).read_text())
        catalog["tasks"][0]["installed"] = ["unpinned"]
        write_json(self.repo / build_inputs.SKILLS_CATALOG, catalog)
        done = self.build("--work-dir", self.work, "--modality", "skills")
        self.assertEqual(done.returncode, 2)
        self.assertIn("unpinned", done.stderr)

    def test_repository_layers_still_need_the_freshness_manifest(self):
        done = self.build("--work-dir", self.work)
        self.assertEqual(done.returncode, 2)
        self.assertIn("--freshness-manifest", done.stderr)

    def test_inputs_built_from_the_committed_catalog_and_manifest_name_whole_skills(self):
        # The committed manifest states each excluded entry's skills as one comma-separated string; the first round
        # iterated its characters, so known_skills.excluded held 363 single characters.
        work = temp_dir(self)
        scope = run([sys.executable, HARNESS / "build_inputs.py", "--skills-scope"])
        self.assertEqual(scope.returncode, 0, scope.stderr)
        write_json(work / "scope.json", json.loads(scope.stdout))
        done = run([sys.executable, HARNESS / "build_inputs.py", "--work-dir", work, "--modality", "skills"])
        self.assertEqual(done.returncode, 0, done.stderr)
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        manifest = json.loads(SKILLS_MANIFEST.read_text(encoding="utf-8"))
        for task in catalog["tasks"]:
            known = json.loads((work / "inputs" / f"{task['layer_id']}.json").read_text(encoding="utf-8"))["known_skills"]
            values = [name for group in known.values() for names in group.values() for name in names]
            self.assertTrue(values, task["layer_id"])
            self.assertEqual([value for value in values if len(value) == 1], [], task["layer_id"])
        known = json.loads((work / "inputs/skills-debug.json").read_text(encoding="utf-8"))["known_skills"]
        self.assertIn("systematic-debugging", known["excluded"]["obra/superpowers"])
        self.assertIn("code-review", known["excluded"]["mattpocock/skills"])
        for entry in manifest["excluded"]:
            self.assertIsInstance(entry["skills"], str, entry["source"])
            for name in entry["skills"].split(","):
                self.assertIn(name.strip(), known["excluded"][entry["source"]], entry["source"])
        # Each installed skill's gap passes whole. security-audit's (930 characters in the manifest unit F3 (#553)
        # left on 2026-09-30, over 1,000 before) is longer than the 300 and 600 characters that a repository layer's
        # open gaps and overturn condition keep (build_inputs.py), so the equality shows that nothing was cut.
        security = json.loads((work / "inputs/skills-security.json").read_text(encoding="utf-8"))
        pinned = {skill["name"]: skill["gap"] for skill in manifest["skills"]}
        gaps = {skill["name"]: skill["gap"] for skill in security["installed"]}
        self.assertEqual(gaps, {name: pinned[name] for name in gaps})
        self.assertGreater(len(gaps["security-audit"]), 600)


# --------------------------------------------------------------------------- each modality's own history


REPOSITORY_SWEEP = {"sweep_id": "sweep-r1", "status": "completed", "manifest_ref": "catalogs/m-r1.json", "layers": [
    {"catalog": "foundation", "layer_id": "alpha", "survived": [{"repo": "https://github.com/o/kept"}],
     "refuted": [{"repo": "https://github.com/o/gone"}]}]}
SKILLS_SWEEP = {"sweep_id": "sweep-s1", "status": "completed", "manifest_ref": "catalogs/m-s1.json", "layers": [
    {"catalog": "skills", "layer_id": "skills-debug", "survived": [{"repo": "acme/agent-skills@debug-kit"}],
     "refuted": [{"repo": "acme/agent-skills@old-kit"}]}]}


class ModalityHistoryTests(unittest.TestCase):
    """build_inputs.py takes previous_sweep and the baseline manifest from the last completed sweep of the run's own
    modality (the ledger names it by its layers' catalogs), never from a sweep of the other modality (GPT-6 review of
    #541: a skills sweep after a repository sweep emptied the next repository run's history and became its baseline)."""

    def setUp(self):
        self.repo = skills_repo(self)
        write_json(self.repo / "catalogs/landscape/foundation.json", {"layers": [{
            "layer_id": "alpha", "title": "Alpha", "requirement": "alpha req", "winners": [], "alternatives": [],
            "candidates": []}]})
        write_json(self.repo / "catalogs/landscape/us-equities.json", {"layers": []})
        write_json(self.repo / "catalogs/landscape/research-state.json", {"layers": [
            {"catalog": "foundation", "layer_id": "alpha", "status": "comparison_required", "next_action": "a"}]})
        # The repository sweep's manifest holds a baseline candidate; a skills lane's manifest has no layer section.
        write_json(self.repo / "catalogs/m-r1.json", {"foundation": [{"layer": "alpha", "candidates": [
            {"repository": "https://github.com/r1/baseline"}]}], "trading": []})
        write_json(self.repo / "catalogs/m-r2.json", {"foundation": [], "trading": []})
        write_json(self.repo / "catalogs/m-s1.json", {"foundation": [], "trading": [], "lane_groupings": {}})

    def ledger(self, *sweeps):
        write_json(self.repo / "catalogs/saturation/ledger.json", {"sweeps": list(sweeps)})

    def repository_run(self):
        work = temp_dir(self)
        write_json(work / "scope.json", harness_tests.scope_for((("foundation", "alpha"),)))
        freshness = write_json(work / "freshness.json", {"checked_at": "2026-09-30", "foundation": [], "trading": []})
        done = run([sys.executable, HARNESS / "build_inputs.py", "--work-dir", work, "--repo-root", self.repo,
                    "--freshness-manifest", freshness])
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads((work / "inputs/alpha.json").read_text(encoding="utf-8")), done.stdout

    def skills_run(self):
        work = temp_dir(self)
        scope = run([sys.executable, HARNESS / "build_inputs.py", "--repo-root", self.repo, "--skills-scope"])
        self.assertEqual(scope.returncode, 0, scope.stderr)
        write_json(work / "scope.json", json.loads(scope.stdout))
        done = run([sys.executable, HARNESS / "build_inputs.py", "--repo-root", self.repo, "--work-dir", work,
                    "--modality", "skills"])
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads((work / "inputs/skills-debug.json").read_text(encoding="utf-8")), done.stdout

    def test_a_repository_run_after_a_skills_sweep_keeps_the_repository_history_and_baseline(self):
        # Repositories, then skills, then repositories: the third run's history and baseline are the first run's.
        self.ledger(REPOSITORY_SWEEP, SKILLS_SWEEP)
        alpha, summary = self.repository_run()
        self.assertEqual(alpha["previous_sweep"], {"sweep_id": "sweep-r1", "survived": ["https://github.com/o/kept"],
                                                   "refuted": ["https://github.com/o/gone"]})
        self.assertEqual(alpha["known_repositories"], ["r1/baseline"])
        self.assertIn("baseline m-r1.json", summary)
        self.assertIn("previous repository sweep sweep-r1", summary)

    def test_a_repository_run_after_only_skills_sweeps_has_an_empty_history_and_no_baseline(self):
        self.ledger(SKILLS_SWEEP)
        alpha, summary = self.repository_run()
        self.assertEqual((alpha["previous_sweep"], alpha["known_repositories"]), ({}, []))
        self.assertIn("baseline none", summary)
        self.assertIn("previous repository sweep none", summary)

    def test_a_skills_run_reads_only_the_skills_sweeps(self):
        # The skills run between the two repository runs has no skills history; a later one reads that skills sweep.
        self.ledger(REPOSITORY_SWEEP)
        debug, summary = self.skills_run()
        self.assertEqual(debug["previous_sweep"], {})
        self.assertIn("previous skills sweep none", summary)
        self.ledger(REPOSITORY_SWEEP, SKILLS_SWEEP,
                    dict(REPOSITORY_SWEEP, sweep_id="sweep-r2", manifest_ref="catalogs/m-r2.json"))
        debug, summary = self.skills_run()
        self.assertEqual(debug["previous_sweep"], {"sweep_id": "sweep-s1", "survived": ["acme/agent-skills@debug-kit"],
                                                   "refuted": ["acme/agent-skills@old-kit"]})
        self.assertIn("previous skills sweep sweep-s1", summary)

    def test_a_sweep_takes_its_modality_from_its_layers_catalogs(self):
        self.assertEqual(build_inputs.sweep_modality(REPOSITORY_SWEEP), "repository")
        self.assertEqual(build_inputs.sweep_modality(SKILLS_SWEEP), "skills")
        mixed = dict(REPOSITORY_SWEEP, layers=REPOSITORY_SWEEP["layers"] + SKILLS_SWEEP["layers"])
        self.assertIsNone(build_inputs.sweep_modality(mixed))  # neither history: a run covers one modality
        self.assertIsNone(build_inputs.sweep_modality(dict(REPOSITORY_SWEEP, layers=[])))
        ledger = {"sweeps": [REPOSITORY_SWEEP, SKILLS_SWEEP, dict(REPOSITORY_SWEEP, sweep_id="sweep-r2",
                                                                  status="stopped"), mixed]}
        self.assertEqual(build_inputs.last_completed(ledger, "repository")["sweep_id"], "sweep-r1")
        self.assertEqual(build_inputs.last_completed(ledger, "skills")["sweep_id"], "sweep-s1")


# --------------------------------------------------------------------------- templates a skills-* layer resolves to


SKILLS_INPUT = {"catalog": "skills", "layer_id": "skills-debug", "title": "Skills: debug", "modality": "skills",
                "lifecycle_task": "debug", "requirement": "debug things", "requirement_sha256": REQ,
                "platform_profiles_sha256": PLAT}


def stage_skills_work(case, layer_ids=("skills-debug", "skills-review"), work=None, extra_rows=()):
    work = work or temp_dir(case)
    rows = []
    for layer_id in layer_ids:
        data = dict(SKILLS_INPUT, layer_id=layer_id, title=f"Skills: {layer_id[7:]}", lifecycle_task=layer_id[7:],
                    requirement=f"{layer_id} req")
        path = write_json(work / "inputs" / f"{layer_id}.json", data)
        rows.append({"catalog": "skills", "layer_id": layer_id, "title": data["title"], "input": str(path),
                     "modality": "skills"})
    write_json(work / "layers.json", rows + list(extra_rows))
    return work


class SkillsTemplateTests(unittest.TestCase):
    def test_a_skills_layer_resolves_to_the_skills_templates(self):
        templates = build_args.load_templates()
        skills = harness_tests.filled_templates(modality="skills")
        repository = harness_tests.filled_templates()
        values = {"DATE": "2026-10-26", "LAYER_COUNT": "2", "SKILLS_CHECKED_AT": "2026-09-25"}
        # The role keys of a skills run hold the skills templates; a repository run's are the repository templates.
        self.assertEqual(skills["discover"], make_prompt.fill(templates["discover_skills"], values))
        self.assertEqual(skills["critic"], make_prompt.fill(templates["critic_skills"], values))
        for key in ("facts", "fit"):
            self.assertEqual(skills[key], templates[key].replace("<<MODALITY>>", templates["modality_skills"]), key)
            self.assertEqual(repository[key], templates[key].replace("<<MODALITY>>", ""), key)
        for key in ("common", "followup"):
            self.assertEqual(skills[key], repository[key], key)
        self.assertEqual(repository["discover"], make_prompt.fill(templates["discover"], values))
        # The GPT-6 prompts come from the run's frozen templates, whatever the layer input says.
        text = make_prompt.compose(skills, "discover", SKILLS_INPUT)
        self.assertIn("ROLE: skills discovery researcher for ONE lifecycle task", text)
        self.assertNotIn("ROLE: discovery researcher for ONE layer", text)
        self.assertIn(json.dumps(SKILLS_INPUT, indent=1), text)
        self.assertIn("Set layer_id to skills-debug.", text)
        followup = {"reason": "missed a registry", "search_directions": ["d1"], "already": ["o/r@s"]}
        self.assertIn("FOLLOW-UP ROUND", make_prompt.compose(skills, "discover", SKILLS_INPUT, followup=followup))
        proposals = json.dumps([{"repository": "o/r@s"}])
        fit = make_prompt.compose(skills, "fit", SKILLS_INPUT, proposals)
        self.assertIn(templates["modality_skills"], fit)
        self.assertNotIn("<<", fit)
        repository_fit = make_prompt.compose(repository, "fit", dict(SKILLS_INPUT, layer_id="alpha"), proposals)
        self.assertNotIn("SKILLS MODALITY", repository_fit)
        self.assertTrue(repository_fit.endswith("in total for all proposals." + make_prompt.TAIL))

    def test_the_modality_placeholder_ends_the_refuter_templates(self):
        # An empty fill leaves a repository layer's facts and fit prompts exactly as they were before the modality.
        templates = build_args.load_templates()
        for key in ("facts", "fit"):
            self.assertTrue(templates[key].endswith("in total for all proposals.<<MODALITY>>"), key)
        self.assertTrue(templates["modality_skills"].startswith("\nSKILLS MODALITY: "))
        self.assertIn("MODALITY", make_prompt.BUILD_PLACEHOLDERS)  # a frozen run's templates never keep it open

    def test_skills_templates_carry_the_selection_rules(self):
        templates = build_args.load_templates()
        discover, critic, modality = (templates["discover_skills"], templates["critic_skills"],
                                      templates["modality_skills"])
        for phrase in ("maintenance rule", "never evidence of quality or fit", "Primary sources only",
                       "Read-only: never install a skill", "DISABLE_TELEMETRY=1 npx skills@1.7.0 find",
                       "skill-creator's paired with-skill/without-skill benchmark", "promptfoo", "skill_ref"):
            self.assertIn(phrase, discover, phrase)
        # Invocation flags as the clients read them: Claude Code's boolean set, and a plain false for Codex's serde_yaml.
        for text in (discover, modality):
            self.assertIn("a true-valued disable-model-invocation (true/yes/on/1) in any letter case", text)
            self.assertIn("allow_implicit_invocation to a plain false", text)
            self.assertIn("quoted or another word such as no", text)
            self.assertNotIn("disable-model-invocation: true", text)
            # Unasked writes to the instruction files conflict; skills-agent-docs maintains them on request.
            self.assertIn("writes into CLAUDE.md or AGENTS.md on its own initiative", text)
            self.assertIn("skills-agent-docs task's requirement", text)
        # A source the catalog marks stale (the common block's maintenance rule, recorded with its API fact).
        self.assertIn("carries a maintenance record with status stale failed that rule", discover)
        self.assertIn("label its skills not_adopted and cite the record, unless you find a maintained fork or "
                      "replacement", discover)
        self.assertIn("has maintenance status stale is stale under the selection principles' maintenance rule", modality)
        self.assertIn("no commit on its default branch in the last 90 days", templates["common"])
        self.assertIn("<<LAYER_COUNT>>-layer skills sweep", critic)
        self.assertIn("never evidence", critic)
        for phrase in ("vote with that exact string as repository", "skill-creator", "promptfoo",
                       "model-invocable", "never count as evidence"):
            self.assertIn(phrase, modality, phrase)
        self.assertIn("a 2-layer skills sweep", harness_tests.filled_templates(modality="skills")["critic"])


class SkillsStagingTests(unittest.TestCase):
    def test_a_skills_run_is_staged_with_the_skills_schema_and_templates(self):
        work = stage_skills_work(self)
        done = harness_tests.build(work)
        self.assertEqual(done.returncode, 0, done.stderr)
        args = json.loads((work / "args.json").read_text())
        self.assertEqual(args["layers"], [{"layer_id": "skills-debug", "catalog": "skills", "modality": "skills"},
                                          {"layer_id": "skills-review", "catalog": "skills", "modality": "skills"}])
        self.assertEqual(sorted(args["schemas"]), ["critic", "discover", "discover-skills", "votes"])
        self.assertEqual(args["schemas"]["discover-skills"], json.loads(SKILLS_SCHEMA.read_text()))
        self.assertEqual(json.loads((work / "schemas/discover-skills.json").read_text()), json.loads(SKILLS_SCHEMA.read_text()))
        checked_at = json.loads(SKILLS_MANIFEST.read_text())["checked_at"]
        self.assertEqual(args["T"], harness_tests.filled_templates("2026-10-26", 2, checked_at, "skills"))
        self.assertEqual(json.loads((work / "templates.json").read_text()), args["T"])
        layer_input = json.loads((work / "inputs/skills-debug.json").read_text())
        prompt = (work / "prompts/gpt6-discover-skills-debug.txt").read_text()
        self.assertEqual(prompt, make_prompt.compose(args["T"], "discover", layer_input) + "\n")
        self.assertIn("ROLE: skills discovery researcher", prompt)
        staged = json.loads((work / "staged.json").read_text())
        self.assertEqual(staged["modality"], "skills")
        self.assertEqual(staged["prompts_sha256"], sweep_common.prompts_sha256(args["T"]))
        self.assertIn("schemas/discover-skills.json", staged["harness"]["files"])
        # Templates and schemas only (the skills templates are longer, and discover-skills rides along): the layer
        # inputs stay files.
        self.assertLess(json.loads(done.stdout)["args_bytes"], 24_000)
        self.assertNotIn("skills-debug req", (work / "args.json").read_text())
        smoke = stage_skills_work(self)
        self.assertEqual(harness_tests.build(smoke, "--smoke", "skills-review").returncode, 0)
        smoke_args = json.loads((smoke / "args.json").read_text())
        self.assertEqual((smoke_args["layers"][0]["layer_id"], smoke_args.get("test")), ("skills-review", True))
        self.assertIn("a 1-layer skills sweep", smoke_args["T"]["critic"])

    def test_the_ledgers_due_report_selects_the_due_skills_layers(self):
        # build_args.py --due-report reads saturation_ledger.py --report --json. Before the ledger learned the skills
        # catalog, its report had no skills row and a skills work directory selected nothing ("no layer selected").
        report = sl.build_report(ROOT, json.loads((ROOT / sl.LEDGER).read_text(encoding="utf-8")))
        tasks = json.loads(CATALOG.read_text(encoding="utf-8"))["tasks"]
        rows = [{"catalog": "skills", "layer_id": task["layer_id"], "title": task["layer_id"], "input": "unused",
                 "modality": "skills"} for task in tasks]
        due = [row["layer_id"] for row in report["layers"] if row["catalog"] == "skills" and row["due"]]
        self.assertTrue(due)
        self.assertEqual([row["layer_id"] for row in build_args.select_layers(rows, due_report=report)], due)
        research_only = {"layers": [row for row in report["layers"] if row["catalog"] != "skills"]}
        with self.assertRaisesRegex(ValueError, "no layer selected"):
            build_args.select_layers(rows, due_report=research_only)

    def test_a_repository_run_keeps_its_args_and_a_mixed_run_is_refused(self):
        repository = harness_tests.stage_work(self, ("alpha",))
        self.assertEqual(harness_tests.build(repository).returncode, 0)
        args = json.loads((repository / "args.json").read_text())
        self.assertEqual(args["layers"], [{"layer_id": "alpha", "catalog": "foundation"}])
        self.assertEqual(sorted(args["schemas"]), ["critic", "discover", "votes"])
        self.assertEqual(sorted(args["T"]), ["common", "critic", "discover", "facts", "fit", "followup"])
        self.assertNotIn("SKILLS MODALITY", json.dumps(args["T"]))
        self.assertEqual(json.loads((repository / "staged.json").read_text())["modality"], "repository")
        mixed = temp_dir(self)
        alpha = write_json(mixed / "inputs/alpha.json", json.loads((repository / "inputs/alpha.json").read_text()))
        stage_skills_work(self, ("skills-debug",), work=mixed, extra_rows=[
            {"catalog": "foundation", "layer_id": "alpha", "title": "Alpha", "input": str(alpha)}])
        done = harness_tests.build(mixed)
        self.assertEqual(done.returncode, 2)
        self.assertIn("one modality per run", done.stderr)
        self.assertEqual(harness_tests.build(mixed, "--layers", "alpha").returncode, 0)


# --------------------------------------------------------------------------- a skills run of sweep.js


RECORDING_HARNESS = harness_tests.NODE_HARNESS.replace("schema: !!opts.schema", "schema: opts.schema || null")
A1, A1_GPT6, B1 = "Acme/agent-skills@debug-kit", "acme/agent-skills@debug-kit", "beta/skills@root-cause"


def skills_run_fixture():
    votes, wrapper = harness_tests.votes, harness_tests.wrapper
    return {"responses": {
        "discover:skills-debug": skills_discovery("skills-debug", [skill_proposal(A1), skill_proposal(B1)]),
        "gpt6-discover:skills-debug": wrapper(skills_discovery("skills-debug", [skill_proposal(A1_GPT6)])),
        "refute-facts:skills-debug": votes("skills-debug", "facts", {A1: False, B1: False}),
        "refute-fit:skills-debug": votes("skills-debug", "fit", {A1: False, B1: True}),
        "gpt6-refute-fit:skills-debug": wrapper(votes("skills-debug", "fit", {A1: False, B1: False})),
        "critic": {"followup_layers": [], "general": ["fixture"]}}}


@unittest.skipUnless(harness_tests.NODE, "node is not installed")
class SkillsSweepScriptTests(unittest.TestCase):
    def setUp(self):
        self.assertNotEqual(RECORDING_HARNESS, harness_tests.NODE_HARNESS)
        self.work = stage_skills_work(self, ("skills-debug",))
        self.assertEqual(harness_tests.build(self.work).returncode, 0)
        self.harness = self.work / "harness.cjs"
        self.harness.write_text(RECORDING_HARNESS, encoding="utf-8")

    def execute(self, fixture, args):
        cmd = ["node", self.harness, HARNESS / "sweep.js", write_json(self.work / "fixture.json", fixture),
               write_json(self.work / "run-args.json", args)]
        done = run(cmd)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_a_skills_run_keys_proposals_by_skill_ref_and_uses_the_skills_templates(self):
        args = json.loads((self.work / "args.json").read_text())
        out = self.execute(skills_run_fixture(), args)
        result, calls = out["result"], {call["label"]: call for call in out["calls"]}
        S = str(self.work)
        merged = result["first"][0]["merged"]
        # The two families' spellings of one skill merge; the skill_ref is the identity the refuters vote on.
        self.assertEqual([(p["repository"], p["skill_ref"], p["families"]) for p in merged],
                         [(A1, A1, ["claude", "gpt6"]), (B1, B1, ["claude"])])
        skills_schema = json.loads(SKILLS_SCHEMA.read_text())
        self.assertEqual(calls["discover:skills-debug"]["schema"], skills_schema)
        self.assertIn("ROLE: skills discovery researcher", calls["discover:skills-debug"]["prompt"])
        self.assertIn(f"{S}/schemas/discover-skills.json", calls["gpt6-discover:skills-debug"]["prompt"])
        for label in ("refute-facts:skills-debug", "refute-fit:skills-debug"):
            prompt = calls[label]["prompt"]
            self.assertIn("SKILLS MODALITY", prompt, label)
            self.assertIn(f'"repository": "{A1}"', prompt, label)
            self.assertIn('"model_invocable": true', prompt, label)
            self.assertEqual(calls[label]["schema"], args["schemas"]["votes"], label)
        self.assertIn("1-layer skills sweep", calls["critic"]["prompt"])
        self.assertNotIn("1-layer saturation sweep", calls["critic"]["prompt"])
        scope = {"platform_profiles_sha256": PLAT, "requirement_sha256": {"skills/skills-debug": REQ}}
        converted = convert.convert(result, scope, LANE, convert.resolved_models(None))
        layer = converted["layers"][0]
        self.assertEqual((layer["catalog"], layer["proposed"]), ("skills", [A1, B1]))
        self.assertEqual([entry["repo"] for entry in layer["survived"]], [A1])
        # A skills survivor carries the pin and SKILL.md hash its proposal named, which source_reviews.py reviews at.
        self.assertEqual(converted["survivors"], [{"layer_id": "skills-debug", "repository": A1, "pin": "a" * 40,
                                                   "skill_md_sha256": "b" * 64}])
        limits = " ".join(converted["lanes"]["lanes"][0]["result"]["limits"])
        self.assertIn("at most 6 skills", limits)
        self.assertIn("merged by skill_ref", limits)

    def test_a_run_mixing_modalities_stops_before_any_agent(self):
        args = json.loads((self.work / "args.json").read_text())
        mixed = dict(args, layers=args["layers"] + [{"layer_id": "alpha", "catalog": "foundation"}])
        out = self.execute({"responses": {}}, mixed)
        self.assertEqual((out["result"]["status"], out["calls"]), ("incomplete", []))
        without_schema = dict(args, schemas={k: v for k, v in args["schemas"].items() if k != "discover-skills"})
        out = self.execute({"responses": {}}, without_schema)
        self.assertEqual((out["result"]["status"], out["calls"]), ("incomplete", []))


# --------------------------------------------------------------------------- source reviews of skill survivors


source_reviews = harness_tests.load("source_reviews")
FIND_BUGS = b"---\nname: find-bugs\ndescription: Find bugs.\n---\n\nBody.\n"
PIN, HEAD = "c" * 40, "a" * 40  # the adjudicated pin, and the default branch's commit (the first round's fallback)
GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"}
NODE = harness_tests.NODE
SKILL_MD_MJS, YAML_PIN_PATH = HARNESS / "skill_md.mjs", HARNESS / "skills-yaml.pin.json"
YAML_ENV = "LANDSCAPE_SWEEP_SKILLS_YAML"
NEL, LS, PS = chr(0x85), chr(0x2028), chr(0x2029)


def reader_run(items, install=None, env=None) -> tuple[int, dict]:
    """skill_md.mjs on items [(path, bytes)]: (its exit status, its JSON answer, or {} when it printed none)."""
    request = {"items": [{"id": str(number), "path": path, "base64": base64.b64encode(data).decode()}
                         for number, (path, data) in enumerate(items)]}
    done = subprocess.run([NODE, str(SKILL_MD_MJS), *(["--install", str(install)] if install else [])],
                          input=json.dumps(request), capture_output=True, text=True, timeout=120, check=False,
                          env=env if env is not None else {**os.environ, "TMPDIR": tempfile.gettempdir()})
    try:
        return done.returncode, json.loads(done.stdout)
    except ValueError:
        return done.returncode, {}


def verified_install():
    """The verified yaml install on this host (LANDSCAPE_SWEEP_SKILLS_YAML, else the default directory the pin names
    under HOME), or None."""
    if not (NODE and SKILL_MD_MJS.is_file() and YAML_PIN_PATH.is_file()):
        return None
    pin = json.loads(YAML_PIN_PATH.read_text(encoding="utf-8"))
    candidate = os.environ.get(YAML_ENV) or str(Path.home() / pin["install"]["default_directory"])
    status, answer = reader_run([], candidate)
    return candidate if status == 0 and (answer.get("reader") or {}).get("ok") is True else None


SKILLS_YAML = verified_install()
NO_READER = ("no verified yaml install for skill_md.mjs (LANDSCAPE_SWEEP_SKILLS_YAML, else the default directory that "
             "skills-yaml.pin.json names under HOME; install it with the pin's command)")


def skill_md(name="find-bugs", description="Find bugs.", extra=()) -> bytes:
    """A SKILL.md with that name and description (None leaves the field out) and any extra frontmatter lines."""
    fields = [f"name: {name}"] * (name is not None) + [f"description: {description}"] * (description is not None)
    return ("---\n" + "".join(f"{line}\n" for line in [*fields, *extra]) + "---\n\nBody.\n").encode()


NO_DESCRIPTION, NO_NAME = skill_md(description=None), skill_md(name=None)


def git_out(case, directory, *args) -> str:
    done = run(["git", "-C", directory, *args], env={**os.environ, **GIT_ENV})
    case.assertEqual(done.returncode, 0, done.stderr)
    return done.stdout


def git_listing(case, files: dict, executable=(), symlinks=None) -> dict:
    """The GitHub git-trees answer (?recursive=1) for a commit holding `files` ({path: bytes}) and `symlinks` ({path:
    target}), with the object ids upstream git computes: `git write-tree` gives the root tree's sha and `git ls-tree -r
    -t -l -z` every folder and blob (a symlink is a blob of mode 120000), so the fixture never reimplements git's object
    format."""
    directory = temp_dir(case)
    git_out(case, directory, "init", "-q")
    for path, data in files.items():
        target = directory / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if path in executable:
            target.chmod(0o755)
    for path, link in (symlinks or {}).items():
        (directory / path).parent.mkdir(parents=True, exist_ok=True)
        os.symlink(link, directory / path)
    git_out(case, directory, "add", "-A")
    root = git_out(case, directory, "write-tree").strip()
    tree = []
    for record in git_out(case, directory, "ls-tree", "-r", "-t", "-l", "-z", root).split("\0"):
        if record:
            meta, path = record.split("\t", 1)
            mode, kind, sha, size = meta.split()
            tree.append({"path": path, "mode": mode, "type": kind, "sha": sha,
                         **({"size": int(size)} if kind == "blob" else {})})
    return {"sha": root, "truncated": False, "tree": tree}


class CliDiscoveryOrderTests(unittest.TestCase):
    """source_reviews.cli_skill_dir follows vercel-labs/skills v1.7.0 discoverSkills (src/skills.ts@7407f389)."""

    def resolve(self, folders, name="find-bugs", plugin_dirs=()):
        return source_reviews.cli_skill_dir(set(folders), name, list(plugin_dirs))

    def test_translations_and_agent_copies_resolve_to_the_skills_folder(self):
        # The review's fixture: affaan-m/ECC keeps translations under docs/<lang>/skills and agent copies under
        # .kiro/skills; the first round refused every such name (254 of ECC's 296).
        folder, where = self.resolve(["skills/find-bugs", "docs/fr/skills/find-bugs", "docs/ja-JP/skills/find-bugs",
                                      ".kiro/skills/find-bugs", "skills/other"])
        self.assertEqual(folder, "skills/find-bugs")
        self.assertIn("skills/", where)

    def test_the_first_location_that_holds_the_name_decides(self):
        cases = [
            (["find-bugs", "skills/find-bugs"], "find-bugs"),  # the root's child folders come first
            ([".agents/skills/find-bugs", "skills/find-bugs"], "skills/find-bugs"),
            ([".kiro/skills/find-bugs", ".agents/skills/find-bugs"], ".agents/skills/find-bugs"),
            (["skills/.curated/find-bugs", ".claude/skills/find-bugs"], "skills/.curated/find-bugs"),
            (["skills/engineering/find-bugs", ".github/skills/find-bugs"], "skills/engineering/find-bugs"),
            # A shallower SKILL.md shadows the folders below it.
            (["skills/find-bugs", "skills/find-bugs/examples/find-bugs"], "skills/find-bugs"),
            (["skills/tools", "skills/tools/find-bugs", ".agents/skills/find-bugs"], ".agents/skills/find-bugs"),
            # Containers are walked three levels deep; node_modules and the other SKIP_DIRS are never walked through.
            (["skills/a/b/find-bugs", "skills/other"], "skills/a/b/find-bugs"),
            (["skills/node_modules/find-bugs", ".agents/skills/find-bugs"], ".agents/skills/find-bugs"),
        ]
        for folders, expected in cases:
            with self.subTest(folders=folders):
                self.assertEqual(self.resolve(folders)[0], expected)

    def test_folders_outside_the_locations_and_same_location_duplicates_are_not_taken(self):
        for folders, message in (
                (["docs/en/skills/find-bugs", "skills/other"], "no folder named find-bugs in the locations"),
                (["skills/a/b/c/find-bugs", "skills/other"], "no folder named find-bugs in the locations"),
                (["skills/a/find-bugs", "skills/b/find-bugs"], "2 folders named find-bugs in skills/"),
                (["skills/.curated/find-bugs", "skills/.system/find-bugs"], "2 folders named find-bugs in skills/"),
                (["a/find-bugs", "b/find-bugs"], "2 unnested folders named find-bugs in the CLI's recursive search"),
                (["skills/other"], "no folder named find-bugs")):
            with self.subTest(folders=folders):
                folder, why = self.resolve(folders)
                self.assertIsNone(folder)
                self.assertIn(message, why)

    def test_the_recursive_fallback_runs_only_when_no_location_holds_a_skill(self):
        self.assertEqual(self.resolve(["skills/a/b/c/find-bugs"])[0], "skills/a/b/c/find-bugs")
        self.assertEqual(self.resolve(["x/y/find-bugs", "x/y/find-bugs/z/find-bugs"])[0], "x/y/find-bugs")
        self.assertIsNone(self.resolve(["a/b/c/d/e/find-bugs"])[0])  # six levels: deeper than findSkillDirs goes
        self.assertIsNone(self.resolve(["a/dist/find-bugs"])[0])

    def test_plugin_manifest_folders_are_searched_one_level_deep(self):
        dirs = source_reviews.cli_plugin_dirs(
            {"metadata": {"pluginRoot": "./plugins"}, "plugins": [
                {"name": "p", "source": "./p", "skills": ["./skills/find-bugs", "./extra/"]},
                {"name": "remote", "source": {"source": "github", "repo": "o/r"}},
                {"name": "bad", "source": "q"}]},
            {"skills": ["./root-skills/review", "../outside/x"]})
        self.assertEqual(dirs, ["plugins/p/skills", "plugins/p", "plugins/p/skills", "root-skills", "skills"])
        self.assertEqual(self.resolve(["plugins/p/skills/find-bugs", "skills/other"], plugin_dirs=dirs)[0],
                         "plugins/p/skills/find-bugs")
        # trailofbits/skills' shape: sources without skills lists, so each plugin's skills/ folder.
        dirs = source_reviews.cli_plugin_dirs({"plugins": [{"name": "fp-check", "source": "./plugins/fp-check"}]}, None)
        self.assertEqual(dirs, ["plugins/fp-check/skills"])
        # microsoft/skills' shape: a pluginRoot and sources that repeat it, which the CLI joins into a folder that
        # does not exist, so those skills are not discovered.
        dirs = source_reviews.cli_plugin_dirs({"metadata": {"pluginRoot": "./.github/plugins"}, "plugins": [
            {"name": "deep-wiki", "source": "./.github/plugins/deep-wiki", "skills": ["./skills/"]}]}, None)
        self.assertEqual(dirs, [".github/plugins/.github/plugins/deep-wiki", ".github/plugins/.github/plugins/deep-wiki/skills"])
        self.assertIsNone(self.resolve([".github/plugins/deep-wiki/skills/find-bugs", "skills/other"],
                                       plugin_dirs=dirs)[0])
        self.assertEqual(source_reviews.cli_plugin_dirs({"metadata": {"pluginRoot": None}, "plugins": [
            {"source": "./p"}]}, None), [])

    def test_a_skill_md_the_reader_cannot_type_never_decides_the_order_by_a_guess(self):
        def inspect(folder):
            if folder in ("skills/odd", "find-bugs"):
                raise source_reviews.SkillMdUnverified(f"{folder}/SKILL.md: frontmatter line 2: an anchor")
            return None, folder.rsplit("/", 1)[-1]

        # A copy of the skill that the reader cannot type comes first: it may be the CLI's pick.
        with self.assertRaisesRegex(source_reviews.SkillMdUnverified, "an anchor"):
            source_reviews.cli_skill_dir({"find-bugs", "skills/find-bugs"}, "find-bugs", [], inspect)
        # No location holds a copy: whether the CLI searches further depends on skills/odd, unless another is valid.
        with self.assertRaisesRegex(source_reviews.SkillMdUnverified, "skills/odd"):
            source_reviews.cli_skill_dir({"skills/odd", "x/y/find-bugs"}, "find-bugs", [], inspect)
        folder, why = source_reviews.cli_skill_dir({"skills/odd", "skills/other", "x/y/find-bugs"}, "find-bugs", [],
                                                   inspect)
        self.assertIsNone(folder)
        self.assertIn("no folder named find-bugs in the locations", why)
        # A valid copy decides before the reader's doubt about another skill's SKILL.md matters.
        self.assertEqual(source_reviews.cli_skill_dir({"skills/find-bugs", "skills/odd"}, "find-bugs", [], inspect)[0],
                         "skills/find-bugs")

    # Opus round-4 review of #541, D1: discoverSkills walks each search location with readdir, which follows a symlink at
    # or above the location (dist/cli.mjs lines 1339-1370), and skips a symlinked folder inside it (entry.isDirectory()
    # is false, src/skills.ts lines 284-298); the git tree lists a symlink as one blob and nothing below it.

    def doubt(self, skill_dirs, symlinks=(), linked=()):
        return lambda container, depth: source_reviews.location_doubt(container, depth, set(skill_dirs), set(symlinks),
                                                                      set(linked))

    def test_a_symlink_at_or_above_a_location_or_a_symlinked_skill_md_above_skill_folders_is_a_doubt(self):
        doubt = source_reviews.location_doubt
        self.assertEqual(source_reviews.symlink_at_or_above(".posit/assistant/skills", {".posit"}), ".posit")
        self.assertIsNone(source_reviews.symlink_at_or_above("skills", {"skills-old", "x/skills"}))
        self.assertIn("the search location skills/ is a symlink", doubt("skills", 3, set(), {"skills"}, set()))
        self.assertIn("is below the symlink .posit", doubt(".posit/assistant/skills", 3, set(), {".posit"}, set()))
        self.assertIsNone(doubt("", 1, {"a"}, {"a"}, set()))  # the root is the clone; a symlinked child is skipped
        self.assertIsNone(doubt("skills", 3, {"skills/find-bugs"}, {"skills/alias", "skills/find-bugs/x"}, set()))
        # skills/tools/SKILL.md is a symlink: the CLI descends below skills/tools only when its target is not a file.
        dirs = {"skills/tools", "skills/tools/find-bugs"}
        self.assertIn("skills/tools/SKILL.md is a symlink with the skill folder skills/tools/find-bugs below it",
                      doubt("skills", 3, dirs, set(), {"skills/tools"}))
        self.assertIsNone(doubt("skills", 3, {"skills/tools"}, set(), {"skills/tools"}))  # nothing below it
        self.assertIsNone(doubt("skills", 1, dirs, set(), {"skills/tools"}))  # below the walk's depth
        self.assertIsNone(doubt("skills", 3, {"skills/tools", "skills/tools/node_modules/x"}, set(), {"skills/tools"}))

    def test_a_doubtful_location_before_the_pick_stops_it_and_one_after_does_not(self):
        LocationUnverified = source_reviews.LocationUnverified
        cases = {
            # skills -> elsewhere comes before .agents/skills: the CLI may find find-bugs through it first.
            "symlinked skills before the copy": ({".agents/skills/find-bugs"}, {"skills"}, (), [], None),
            # .claude/skills -> ../skills comes after skills/: the pick is made before the CLI walks it.
            "symlinked agent folder after the copy": ({"skills/find-bugs"}, {".claude/skills"}, (), [], "skills/find-bugs"),
            # No location holds a valid skill, so the recursive search would decide, unless the symlinked location
            # holds one (then the CLI never searches recursively).
            "symlinked location and the recursive search": ({"x/y/find-bugs"}, {".github/skills"}, (), [], None),
            # A plugin folder below a symlink is the last location: it matters only when nothing earlier decides.
            "symlinked plugin folder, no earlier copy": ({"x/y/find-bugs"}, {"plugins"}, (), ["plugins/p/skills"], None),
            "symlinked plugin folder after the copy": ({"skills/find-bugs"}, {"plugins"}, (), ["plugins/p/skills"],
                                                       "skills/find-bugs"),
            # A symlinked SKILL.md above a copy: the CLI may walk below it and find skills/tools/find-bugs first.
            "symlinked SKILL.md above a copy": ({"skills/tools", "skills/tools/find-bugs", ".agents/skills/find-bugs"},
                                                (), {"skills/tools"}, [], None),
        }
        for label, (dirs, symlinks, linked, plugins, expected) in cases.items():
            with self.subTest(label):
                call = lambda: source_reviews.cli_skill_dir(dirs, "find-bugs", plugins, doubt=self.doubt(dirs, symlinks, linked))  # noqa: E731
                if expected is None:
                    with self.assertRaisesRegex(LocationUnverified, "no earlier location the CLI searches holds a valid copy"):
                        call()
                else:
                    self.assertEqual(call()[0], expected)
        # The same trees without the symlinks: the round-4 resolver's answers, which the doubts now stop.
        self.assertEqual(source_reviews.cli_skill_dir({".agents/skills/find-bugs"}, "find-bugs")[0], ".agents/skills/find-bugs")
        self.assertEqual(source_reviews.cli_skill_dir({"x/y/find-bugs"}, "find-bugs")[0], "x/y/find-bugs")

    def test_unknown_plugin_folders_stop_the_pick_only_when_nothing_earlier_decides(self):
        why = "the plugin manifest folder .claude-plugin is a symlink, which the CLI reads through"
        with self.assertRaisesRegex(source_reviews.LocationUnverified, "is a symlink, which the CLI reads through"):
            source_reviews.cli_skill_dir({"x/y/find-bugs"}, "find-bugs", [], plugin_doubt=why)
        with self.assertRaisesRegex(source_reviews.LocationUnverified, "is a symlink, which the CLI reads through"):
            source_reviews.cli_skill_dir({"plugins/p/skills/find-bugs"}, "find-bugs", ["plugins/p/skills"], plugin_doubt=why)
        self.assertEqual(source_reviews.cli_skill_dir({"skills/find-bugs"}, "find-bugs", [], plugin_doubt=why)[0],
                         "skills/find-bugs")


PYYAML = importlib.util.find_spec("yaml") is not None
DOCUMENTED_OPENAI_YAML = (  # the example of https://developers.openai.com/codex/skills, Optional metadata
    'interface:\n  display_name: "Find bugs"\n  brand_color: "#3B82F6"\n\npolicy:\n  allow_implicit_invocation: false\n'
    '\ndependencies:\n  tools:\n    - type: "mcp"\n      value: "openaiDeveloperDocs"\n'
    '      url: "https://developers.openai.com/mcp"\n')
# agents/openai.yaml texts: name -> (text, the subset reader's codex_implicit, the PyYAML reader's codex_implicit, a
# phrase of the subset reader's note). None is unverified. Codex rust-v0.157.1 deserializes the file with serde_yaml
# 0.9.34, which reads a bool only from a plain true/True/TRUE/false/False/FALSE, follows anchors and aliases and
# refuses a second document, and Codex ignores the whole file when that fails (implicit invocation stays allowed).
OPENAI_YAML = {
    "the documented block form": (DOCUMENTED_OPENAI_YAML, False, False, "policy.allow_implicit_invocation: false"),
    "block true": ("policy:\n  allow_implicit_invocation: true\n", True, True, "allow_implicit_invocation: true"),
    "FALSE after a document marker": ("---\npolicy:\n  allow_implicit_invocation: FALSE  # manual only\n", False,
                                      False, "FALSE"),
    "a quoted key": ('policy:\n  "allow_implicit_invocation": false\n', False, False, "false"),
    "a block sequence beside it": ("policy:\n  products:\n    - codex\n  allow_implicit_invocation: false\n", False,
                                   False, "false"),
    "no policy (the Codex default)": ("interface:\n  display_name: Find bugs\n", True, True, "no policy"),
    "comments only": ("# nothing yet\n", True, True, "no policy"),
    "a null policy": ("policy:\ninterface:\n  display_name: X\n", True, True, "policy is null"),
    "a null value": ("policy:\n  allow_implicit_invocation: ~\n", True, True, "is null"),
    "not a direct child": ("policy:\n  products:\n    allow_implicit_invocation: false\n", True, True,
                           "no policy.allow_implicit_invocation"),
    "no, which serde_yaml does not read": ("policy:\n  allow_implicit_invocation: no\n", True, True,
                                           "not a YAML boolean"),
    "a quoted false": ('policy:\n  allow_implicit_invocation: "false"\n', True, True, "not a YAML boolean"),
    "a scalar policy": ("policy: false\n", True, True, "not a mapping"),
    "a list policy": ("policy:\n  - allow_implicit_invocation\n", True, True, "a list"),
    "policy twice": ("policy:\n  allow_implicit_invocation: false\npolicy:\n  products:\n    - codex\n", True, True,
                     "policy appears twice"),
    "a flow mapping": ("policy: {allow_implicit_invocation: false}\n", None, False, "flow mapping"),
    "a flow mapping over lines": ('policy: {\n  "allow_implicit_invocation": false,\n  products: [codex]\n}\n', None,
                                  False, "flow mapping"),
    "an anchored mapping": ("policy: &p\n  allow_implicit_invocation: false\n", None, False, "anchor"),
    "an aliased mapping": ("shared: &p\n  allow_implicit_invocation: false\npolicy: *p\n", None, False, "anchor"),
    "an alias alone": ("policy: *p\n", None, None, "alias"),
    "a tagged value": ("policy:\n  allow_implicit_invocation: !!bool false\n", None, False, "tag"),
    "a value on the next line": ("policy:\n  allow_implicit_invocation:\n    false\n", None, False, "not a key"),
    "a null tag on false": ("policy:\n  allow_implicit_invocation: !!null false\n", None, True, "tag"),
    "a block scalar": ("policy:\n  allow_implicit_invocation: |-\n    false\n", None, True, "block scalar"),
    "two documents": ("policy:\n  allow_implicit_invocation: true\n---\npolicy:\n  allow_implicit_invocation: false\n",
                      None, True, "second document"),
    "tab indentation": ("policy:\n\tallow_implicit_invocation: false\n", None, None, "tab"),
    "a plain scalar holding ': '": ("interface:\n  short_description: Finds bugs: fast\npolicy:\n"
                                    "  allow_implicit_invocation: false\n", None, None, "': '"),
    # GPT-6 round-3 review of #541: without PyYAML an escape YAML does not define, anywhere in the file, still gave a
    # definite false, while serde_yaml's scanner refuses the file (unsafe-libyaml 0.2.11 src/scanner.rs lines
    # 2195-2361: "found unknown escape character", a missing hex digit, a surrogate) and Codex then allows it.
    "an invalid escape in another value": ('note: "C:\\skills"\npolicy:\n  allow_implicit_invocation: false\n', None,
                                           None, "escape \\s"),
    "a hex escape without its digits": ('note: "\\x4"\npolicy:\n  allow_implicit_invocation: false\n', None, None,
                                        "escape \\x4"),
    "a surrogate escape": ('note: "\\uD800"\npolicy:\n  allow_implicit_invocation: false\n', None, None, "a surrogate"),
    "an unbalanced single quote": ("note: 'it's'\npolicy:\n  allow_implicit_invocation: false\n", None, None,
                                   "text after a quoted scalar"),
    "YAML's escapes": ('note: "Tab\\t\\"q\\" \\x41\\u00e9\\U0001F600\\/"\npolicy:\n  allow_implicit_invocation: false\n',
                       False, False, "false"),
    # Opus round-3 review of #541, finding 5: the subset reader took characters libyaml refuses (unsafe-libyaml 0.2.11
    # src/reader.rs lines 381-395, "control characters are not allowed"; serde_yaml then fails and Codex allows
    # implicit invocation) and split lines where Python's str.splitlines does. Characters outside libyaml's set and
    # line breaks other than LF and CRLF are unverified before either reader runs.
    "a form feed after false": ("policy:\n  allow_implicit_invocation: false\x0c\n", None, None, "U+000C"),
    "a vertical tab after false": ("policy:\n  allow_implicit_invocation: false\x0b\n", None, None, "U+000B"),
    "a control character in another value": ("note: a\x01b\npolicy:\n  allow_implicit_invocation: false\n", None, None,
                                             "U+0001"),
    "a file separator between lines": ("policy:\x1c  allow_implicit_invocation: false\n", None, None, "U+001C"),
    "a lone CR between lines": ("policy:\r  allow_implicit_invocation: false\n", None, None, "U+000D"),
    "U+0085 between lines": (f"policy:{NEL}  allow_implicit_invocation: false\n", None, None, "U+0085"),
    "U+2028 between lines": (f"policy:{LS}  allow_implicit_invocation: false\n", None, None, "U+2028"),
    "U+2029 between lines": (f"policy:{PS}  allow_implicit_invocation: false\n", None, None, "U+2029"),
    "CRLF line breaks": ("policy:\r\n  allow_implicit_invocation: false\r\n", False, False, "false"),
}


class OpenAiYamlSubsetReaderTests(unittest.TestCase):
    """agents/openai.yaml without PyYAML: the plain block-mapping subset the handwritten reader parses, and
    codex_implicit null with the reason for anything else (GPT-6 review of #541: the reader said true for a valid
    flow mapping and for an anchored policy, both false for Codex)."""

    def test_the_subset_reader_is_right_or_says_it_cannot_tell(self):
        with mock.patch.object(source_reviews, "yaml", None, create=True):
            for name, (text, expected, _, phrase) in OPENAI_YAML.items():
                with self.subTest(name):
                    implicit, _, note = source_reviews.openai_yaml_policy(text)
                    self.assertIs(implicit, expected, note)
                    self.assertIn(phrase, note)
                    if expected is None:
                        self.assertIn("unverified", note)


@unittest.skipUnless(PYYAML, "PyYAML is not installed; the subset reader's tests run without it")
class OpenAiYamlPyYamlReaderTests(unittest.TestCase):
    """agents/openai.yaml with PyYAML: its composer (libyaml's grammar, as serde_yaml's unsafe-libyaml) builds the node
    tree, and serde_yaml 0.9.34's rules decide the value (a plain true/false spelling, no YAML 1.1 yes/no)."""

    def test_the_pyyaml_reader_reads_what_codex_reads(self):
        for name, (text, _, expected, _) in OPENAI_YAML.items():
            with self.subTest(name):
                implicit, _, note = source_reviews.openai_yaml_policy(text)
                self.assertIs(implicit, expected, note)
                if expected is None:
                    self.assertIn("unverified", note)
        self.assertIsNotNone(getattr(source_reviews, "yaml", None))
        self.assertTrue(source_reviews.openai_yaml_reader().startswith("PyYAML"))

    def test_the_pure_python_loader_reads_what_codex_reads(self):
        # Without the libyaml binding PyYAML's own scanner takes a surrogate escape, which libyaml refuses, and raises
        # ValueError (not a YAMLError) beyond U+10FFFF: both stay unverified.
        with mock.patch.object(source_reviews.yaml, "CSafeLoader", None, create=True):
            self.assertTrue(source_reviews.openai_yaml_reader().endswith("with SafeLoader"))
            for name, (text, _, expected, _) in OPENAI_YAML.items():
                with self.subTest(name):
                    implicit, _, note = source_reviews.openai_yaml_policy(text)
                    self.assertIs(implicit, expected, note)
            implicit, _, note = source_reviews.openai_yaml_policy(
                'note: "\\U00110000"\npolicy:\n  allow_implicit_invocation: false\n')
            self.assertIsNone(implicit, note)
            self.assertIn("unverified", note)


class OpenAiYamlBytesTests(unittest.TestCase):
    """agents/openai.yaml as the review reads it, as bytes: what is not UTF-8 is unverified before any reader runs."""

    def test_bytes_that_are_not_utf8_are_unverified(self):
        implicit, _, note = source_reviews.openai_yaml_policy(b"policy:\n  allow_implicit_invocation: false\n# \xff\n")
        self.assertIsNone(implicit, note)
        self.assertIn("not UTF-8", note)
        implicit, _, note = source_reviews.openai_yaml_policy(b"policy:\n  allow_implicit_invocation: false\n")
        self.assertIs(implicit, False, note)


def skill_frontmatter(lines: str) -> bytes:
    """A SKILL.md whose frontmatter is these lines, after a name line unless they give their own."""
    return (f"---\n{'' if lines.startswith('name:') else 'name: find-bugs' + chr(10)}{lines}\n---\n\nBody.\n").encode()


# SKILL.md copies as skill_md.mjs judges them at skills/find-bugs/SKILL.md: name -> (bytes, verdict, the recorded name
# (take) or a phrase of the warning (skip) or of the reason (error), the display name (take)). Each take and skip, with
# its name and warning, is the pinned CLI's own: on 2026-09-30 it matched parseSkillMd sliced byte for byte from the
# published skills@1.7.0 dist/cli.mjs, run with yaml 2.9.0 and with the 2.9.1 a fresh install resolves
# (evidence/artifacts/skills-md-reader-20260930). "error" is this reader's refusal: a line break other than LF or CRLF
# in the frontmatter. The Opus round-3 review of #541 found both earlier readers taking copies the CLI skips (findings
# 2-4) and splitting lines where the yaml package does not (finding 3); those inputs are rows here.
SKILL_MD = {
    "a plain description": (skill_frontmatter("description: Find bugs."), "take", "find-bugs", "find-bugs"),
    "a list description": (skill_frontmatter("description:\n  - Find bugs."), "skip",
                           'frontmatter "name" and "description" must be strings (got string and object)', None),
    "a mapping description": (skill_frontmatter("description:\n  summary: Find bugs."), "skip",
                              "(got string and object)", None),
    "a flow list description": (skill_frontmatter("description: [Find bugs.]"), "skip", "(got string and object)", None),
    "a number description": (skill_frontmatter("description: 1.5"), "skip", "(got string and number)", None),
    "a null description": (skill_frontmatter("description: ~"), "skip",
                           "missing required frontmatter field(s): description", None),
    "a literal block": (skill_frontmatter("description: |\n  Find bugs."), "take", "find-bugs", "find-bugs"),
    "a folded block over lines": (skill_frontmatter("description: >-\n  Find bugs\n  in a change."), "take",
                                  "find-bugs", "find-bugs"),
    "a block without text": (skill_frontmatter("description: >-"), "skip",
                             "missing required frontmatter field(s): description", None),
    "a plain scalar on the next lines": (skill_frontmatter("description:\n  Find bugs\n  in a change."), "take",
                                         "find-bugs", "find-bugs"),
    "YAML's escapes": (skill_frontmatter('description: "Tab\\there \\"q\\" \\x41\\u00e9"'), "take", "find-bugs",
                       "find-bugs"),
    "an anchored description": (skill_frontmatter("description: &d Find bugs."), "take", "find-bugs", "find-bugs"),
    "a tagged description": (skill_frontmatter("description: !!str Find bugs."), "take", "find-bugs", "find-bugs"),
    "an int-tagged description": (skill_frontmatter("description: !!int 1"), "skip", "(got string and number)", None),
    "an invalid escape in another value": (skill_frontmatter('description: Find bugs.\nnote: "C:\\skills"'), "skip",
                                           "YAML parse error: Invalid escape sequence \\s", None),
    "a plain scalar holding ': '": (skill_frontmatter("description: Use when: asked."), "skip",
                                    "YAML parse error: Nested mappings are not allowed in compact mappings", None),
    "a key given twice": (skill_frontmatter("description: Find bugs.\ndescription: Again."), "skip",
                          "YAML parse error: Map keys must be unique", None),
    "a nested key given twice": (skill_frontmatter("description: Find bugs.\nmetadata:\n  a: 1\n  a: 2"), "skip",
                                 "YAML parse error: Map keys must be unique", None),
    "a block scalar with an indentation indicator": (skill_frontmatter("description: |2\n    Find bugs."), "take",
                                                     "find-bugs", "find-bugs"),
    "an internal skill (add --skill includes it)": (
        skill_frontmatter("description: Find bugs.\nmetadata:\n  internal: true"), "take", "find-bugs", "find-bugs"),
    "no frontmatter": (b"# Find bugs\n", "skip", "missing required frontmatter field(s): name, description", None),
    "a UTF-8 BOM before the frontmatter": (b"\xef\xbb\xbf" + FIND_BUGS, "skip",
                                           "missing required frontmatter field(s): name, description", None),
    "CRLF line breaks": (FIND_BUGS.replace(b"\n", b"\r\n"), "take", "find-bugs", "find-bugs"),
    # finding 2: continuations yaml refuses, which the PyYAML reader took
    "an under-indented double-quoted continuation": (skill_frontmatter('description: "Find bugs\nin a change."'), "skip",
                                                     'YAML parse error: Missing closing "quote', None),
    "a flow sequence continued at column 0": (skill_frontmatter("description: Find bugs.\ntags: [a,\nb]"), "skip",
                                              "YAML parse error: Flow sequence in block collection must be sufficiently "
                                              "indented", None),
    # finding 4: nested structure yaml refuses, which the subset reader took
    "a nested mapping key under-indented": (skill_frontmatter("description: Find bugs.\nmetadata:\n  a: 1\n b: 2"),
                                            "skip", "YAML parse error: All mapping items must start at the same column",
                                            None),
    "a flow sequence with an empty item": (skill_frontmatter("description: Find bugs.\ntags: [,]"), "skip",
                                           "YAML parse error: Unexpected , in flow sequence", None),
    "mismatched flow brackets": (skill_frontmatter("description: Find bugs.\ntags: {a: [b}]"), "skip",
                                 "YAML parse error: Flow sequence in block collection", None),
    # finding 3: line breaks other than LF and CRLF (the CLI's own verdict follows "the CLI alone")
    "a lone CR between keys": (skill_frontmatter("name: find-bugs\rdescription: Find bugs."), "error",
                               "frontmatter line 2: a CR without LF", None),
    "U+0085 between keys": (skill_frontmatter(f"name: find-bugs{NEL}description: Find bugs."), "error",
                            "frontmatter line 2: U+0085", None),
    "U+2028 inside a description": (skill_frontmatter(f"description: Find{LS}bugs."), "error",
                                    "U+2028, a line break to libyaml", None),
    "U+2029 between keys": (skill_frontmatter(f"name: find-bugs{PS}description: Find bugs."), "error", "U+2029", None),
    "a lone CR before the closing marker": (b"---\nname: find-bugs\ndescription: Find bugs.\r---\n\nBody.\n", "error",
                                            "the CLI alone skips it: missing required frontmatter field(s)", None),
    "CR-only line endings": (b"---\rname: find-bugs\rdescription: Find bugs.\r---\r\rBody.\r", "error",
                             "frontmatter line 1: a CR without LF", None),
    "U+2028 in the body only": (FIND_BUGS + f"More{LS}text.\n".encode(), "take", "find-bugs", "find-bugs"),
    "a lone CR in the body only": (FIND_BUGS + b"More\rtext.\n", "take", "find-bugs", "find-bugs"),
    # finding 6: the name as the CLI records it (sanitizeMetadata) and matches --skill against (getSkillDisplayName)
    "a name of one CSI sequence": (skill_frontmatter('name: "\\e[31m"\ndescription: Find bugs.'), "take", "",
                                   "find-bugs"),
    "a name of spaces only": (skill_frontmatter('name: "   "\ndescription: Find bugs.'), "take", "", "find-bugs"),
    "a CSI sequence inside the name": (skill_frontmatter('name: "find-\\e[1mbugs"\ndescription: Find bugs.'), "take",
                                       "find-bugs", "find-bugs"),
    "an OSC title sequence in the name": (skill_frontmatter('name: "\\e]0;title\\afind-bugs"\ndescription: Find bugs.'),
                                          "take", "find-bugs", "find-bugs"),
    "a C1 control in the name": (skill_frontmatter('name: "find-bugs\\x9b"\ndescription: Find bugs.'), "take",
                                 "find-bugs", "find-bugs"),
    "BEL and backspace in the name": (skill_frontmatter('name: "find\\a-bugs\\b"\ndescription: Find bugs.'), "take",
                                      "find-bugs", "find-bugs"),
    "a raw ESC byte in the name": (skill_frontmatter("name: find-\x1b[1mbugs\ndescription: Find bugs."), "take",
                                   "find-bugs", "find-bugs"),
    "a line break inside a quoted name": (skill_frontmatter('name: "find-\\nbugs"\ndescription: Find bugs.'), "take",
                                          "find- bugs", "find- bugs"),
    "a quoted name with spaces": (skill_frontmatter('name: " find-bugs "\ndescription: Find bugs.'), "take",
                                  "find-bugs", "find-bugs"),
}


@unittest.skipUnless(NODE, "node is not installed")
class SkillMdReaderPinTests(unittest.TestCase):
    """skill_md.mjs runs only the bytes skills-yaml.pin.json pins, installs nothing, and parses nothing without them
    (the tree-sitter-bash pattern of examples/claude-native/workflows/shell-parser.pin.json)."""

    def test_the_pin_names_the_clis_lockfile_package_and_every_file_that_runs(self):
        pin = json.loads(YAML_PIN_PATH.read_text(encoding="utf-8"))
        package = pin["package"]
        # vercel-labs/skills v1.7.0 pnpm-lock.yaml (tag commit 7407f389) resolves yaml@2.9.0 with this integrity.
        self.assertEqual((package["name"], package["version"], package["integrity"]),
                         ("yaml", "2.9.0", "sha512-2AvhNX3mb8zd6Zy7INTtSpl1F15HW6Wnqj0srWlkKLcpYl/gMIMJiyuGq2KeI2YFxUPjdl"
                                           "B+3Lc10seMLtL4cA=="))
        self.assertEqual(package["upstream"]["tag_commit"], "ddb21b04cb889722cec8f89dc1b67f19d62d7f7d")
        self.assertIn(pin["entry"], pin["files"])
        self.assertIn("node_modules/yaml/package.json", pin["files"])  # its "type": "commonjs" governs the .js files
        self.assertTrue(all(HEX64.fullmatch(value["sha256"]) for value in pin["files"].values()))
        self.assertEqual(pin["install"]["command"], "npm install --prefix <directory> --ignore-scripts --no-audit "
                                                    "--no-fund --save-exact yaml@2.9.0")
        self.assertEqual(pin["install"]["environment"], YAML_ENV)
        self.assertIn("2.9.1", pin["consumer"]["resolution"])  # what npm resolves ^2.8.3 to is recorded, not implied

    def test_without_a_verified_install_nothing_is_parsed(self):
        empty = temp_dir(self)
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(empty), "TMPDIR": tempfile.gettempdir()}
        for install, extra in ((empty / "absent", {}), (None, {YAML_ENV: str(empty / "absent")}), (None, {})):
            with self.subTest(install=install, env=extra):
                status, answer = reader_run([("skills/find-bugs/SKILL.md", FIND_BUGS)], install, {**env, **extra})
                self.assertEqual(status, 3)
                self.assertEqual(answer, {"reader": {"ok": False, "reason": "not_installed"}, "results": []})

    @unittest.skipUnless(SKILLS_YAML, NO_READER)
    def test_a_changed_byte_a_changed_lockfile_or_a_missing_file_refuses_the_install(self):
        def copy():
            target = temp_dir(self) / "install"
            shutil.copytree(SKILLS_YAML, target, symlinks=True)
            return target

        status, answer = reader_run([("skills/find-bugs/SKILL.md", FIND_BUGS)], copy())
        self.assertEqual((status, answer["reader"]["ok"], answer["results"][0]["verdict"]), (0, True, "take"))
        changed = copy()
        composer = changed / "node_modules/yaml/dist/compose/composer.js"
        composer.write_bytes(composer.read_bytes() + b"\n")
        relock = copy()
        lock = json.loads((relock / "package-lock.json").read_text(encoding="utf-8"))
        lock["packages"]["node_modules/yaml"]["integrity"] = "sha512-" + "A" * 86 + "=="
        (relock / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")
        unlocked = copy()
        (unlocked / "package-lock.json").unlink()
        partial = copy()
        (partial / "node_modules/yaml/dist/parse/lexer.js").unlink()
        for install, reason in ((changed, "hash_mismatch"), (relock, "hash_mismatch"), (unlocked, "not_installed"),
                                (partial, "not_installed")):
            with self.subTest(reason=reason, install=install.parent.name):
                status, answer = reader_run([("skills/find-bugs/SKILL.md", FIND_BUGS)], install)
                self.assertEqual((status, answer), (3, {"reader": {"ok": False, "reason": reason}, "results": []}))

    @unittest.skipUnless(SKILLS_YAML, NO_READER)
    def test_the_directory_order_is_the_flag_then_the_environment_then_home(self):
        empty = temp_dir(self)
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(empty), "TMPDIR": tempfile.gettempdir()}
        order = [reader_run([], None, env)[1]["reader"], reader_run([], None, {**env, YAML_ENV: SKILLS_YAML})[1]["reader"],
                 reader_run([], empty / "absent", {**env, YAML_ENV: SKILLS_YAML})[1]["reader"],
                 reader_run([], SKILLS_YAML, {**env, YAML_ENV: str(empty / "absent")})[1]["reader"]]
        self.assertEqual([item["ok"] for item in order], [False, True, False, True])
        self.assertEqual(order[1]["package"], "yaml@2.9.0")

    @unittest.skipUnless(SKILLS_YAML, NO_READER)
    def test_the_environment_beats_the_default_under_home(self):
        # Test gap (round-4 review): HOME was empty in every case above. Here HOME holds a verified install at the pin's
        # default directory: it is found when nothing else names one, and the environment variable (a tampered copy, or
        # an absent directory) is read instead of it when set.
        home = temp_dir(self)
        pin = json.loads(YAML_PIN_PATH.read_text(encoding="utf-8"))
        shutil.copytree(SKILLS_YAML, home / pin["install"]["default_directory"], symlinks=True)
        tampered = temp_dir(self) / "tampered"
        shutil.copytree(SKILLS_YAML, tampered, symlinks=True)
        composer = tampered / "node_modules/yaml/dist/compose/composer.js"
        composer.write_bytes(composer.read_bytes() + b"\n")
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(home), "TMPDIR": tempfile.gettempdir()}
        found = [reader_run([], None, env)[1]["reader"], reader_run([], None, {**env, YAML_ENV: str(tampered)})[1]["reader"],
                 reader_run([], None, {**env, YAML_ENV: str(home / "absent")})[1]["reader"]]
        self.assertEqual([item.get("reason", "ok") for item in found], ["ok", "hash_mismatch", "not_installed"])

    @unittest.skipUnless(SKILLS_YAML, NO_READER)
    def test_a_file_that_cannot_be_read_or_a_broken_pin_refuses_with_load_error(self):
        # Test gap (round-4 review): the load_error refusal. A pinned file that is a directory (EISDIR, not a missing
        # file), and a pin file that is not the pin's shape, both refuse to parse anything.
        unreadable = temp_dir(self) / "install"
        shutil.copytree(SKILLS_YAML, unreadable, symlinks=True)
        entry = unreadable / "node_modules/yaml/dist/index.js"
        entry.unlink()
        entry.mkdir()
        self.assertEqual(reader_run([("skills/find-bugs/SKILL.md", FIND_BUGS)], unreadable),
                         (3, {"reader": {"ok": False, "reason": "load_error"}, "results": []}))
        reader_dir = temp_dir(self)
        shutil.copyfile(SKILL_MD_MJS, reader_dir / "skill_md.mjs")
        for label, pin_text in (("not JSON", "{"), ("no files", json.dumps({"package": {"name": "yaml"}}))):
            with self.subTest(label):
                (reader_dir / "skills-yaml.pin.json").write_text(pin_text, encoding="utf-8")
                done = subprocess.run([NODE, str(reader_dir / "skill_md.mjs"), "--install", SKILLS_YAML],
                                      input='{"items": []}', capture_output=True, text=True, timeout=120, check=False,
                                      env={**os.environ, "TMPDIR": tempfile.gettempdir()})
                self.assertEqual((done.returncode, json.loads(done.stdout)),
                                 (3, {"reader": {"ok": False, "reason": "load_error"}, "results": []}))


@unittest.skipUnless(SKILLS_YAML, NO_READER)
class SkillMdReaderTests(unittest.TestCase):
    """skill_md.mjs: each SKILL.md's verdict as the pinned skills CLI decides it, with the name it records and the
    display name --skill is matched against; source_reviews.skill_md_check raises SkillMdUnverified for its "error"."""

    def test_each_copy_gets_the_clis_verdict_name_and_warning(self):
        names = list(SKILL_MD)
        status, answer = reader_run([("skills/find-bugs/SKILL.md", SKILL_MD[name][0]) for name in names], SKILLS_YAML)
        self.assertEqual(status, 0)
        self.assertEqual(answer["reader"]["package"], "yaml@2.9.0")
        for name, result in zip(names, answer["results"]):
            _, verdict, detail, display = SKILL_MD[name]
            with self.subTest(name):
                self.assertEqual(result["verdict"], verdict, result["reason"])
                if verdict == "take":
                    self.assertEqual((result["name"], result["display_name"], result["reason"]), (detail, display, None))
                else:
                    self.assertIn(detail, result["reason"])
                    self.assertIsNone(result["name"])

    def test_a_root_skill_md_without_a_name_has_no_display_name(self):
        # getSkillDisplayName falls back to the folder, which for a root SKILL.md is the CLI's clone directory.
        blank = skill_frontmatter('name: "\\e[31m"\ndescription: Find bugs.')
        _, answer = reader_run([("SKILL.md", blank), ("SKILL.md", FIND_BUGS)], SKILLS_YAML)
        self.assertEqual([(item["name"], item["display_name"]) for item in answer["results"]],
                         [("", None), ("find-bugs", "find-bugs")])

    def test_license_and_disable_model_invocation_are_typed_as_the_yaml_package_types_them(self):
        cases = {"license: MIT\ndisable-model-invocation: yes": ("MIT", "yes"),
                 "license: 'Apache-2.0'\ndisable-model-invocation: true": ("Apache-2.0", True),
                 "license:\n  - MIT\ndisable-model-invocation: 1": (None, 1),
                 "disable-model-invocation: [true]": (None, None)}
        texts = list(cases)
        _, answer = reader_run([("skills/find-bugs/SKILL.md", skill_frontmatter(f"description: Find bugs.\n{text}"))
                                for text in texts], SKILLS_YAML)
        for text, result in zip(texts, answer["results"]):
            with self.subTest(text):
                self.assertEqual((result["license"], result["disable_model_invocation"]), cases[text])
        self.assertEqual([source_reviews.claude_true(value) for value in ("yes", True, 1, None, "off", 0, False)],
                         [True, True, True, False, False, False, False])

    def test_skill_md_check_raises_for_no_verdict_and_returns_the_rest(self):
        with mock.patch.dict(source_reviews.READER, install=SKILLS_YAML, failure=None, record=None):
            self.assertEqual(source_reviews.skill_md_check(FIND_BUGS, "skills/find-bugs/SKILL.md")["verdict"], "take")
            self.assertEqual(source_reviews.READER["record"]["package"], "yaml@2.9.0")
            with self.assertRaisesRegex(source_reviews.SkillMdUnverified, "a CR without LF"):
                source_reviews.skill_md_check(SKILL_MD["a lone CR between keys"][0], "skills/find-bugs/SKILL.md")


@unittest.skipUnless(NODE, "node is not installed")
class SkillMdReaderUnavailableTests(unittest.TestCase):
    """Without a verified install every copy is unverified, and the failure is kept rather than retried."""

    def test_every_copy_is_unverified_and_the_reason_is_kept(self):
        empty = temp_dir(self)
        with mock.patch.dict(source_reviews.READER, install=str(empty / "absent"), failure=None, record=None):
            for _ in range(2):
                with self.assertRaisesRegex(source_reviews.SkillMdUnverified, "is not_installed"):
                    source_reviews.skill_md_check(FIND_BUGS)
            self.assertIn("skills-yaml.pin.json", source_reviews.READER["failure"])
        with mock.patch.dict(source_reviews.READER, install=None, failure=None, record=None), \
                mock.patch.object(source_reviews.shutil, "which", return_value=None):
            with self.assertRaisesRegex(source_reviews.SkillMdUnverified, "node is not installed"):
                source_reviews.skill_md_check(FIND_BUGS)


class GitObjectIdTests(unittest.TestCase):
    """source_reviews.py's folder hash is git's own tree id (the id the skills CLI's lock records as
    skillFolderHash), recomputed from a tree listing and checked here against git itself."""

    def test_blob_and_tree_ids_are_the_ids_git_computes(self):
        # a-b, a.txt and the folder a sort as git sorts them (a folder compares as its name plus "/").
        files = {"README.md": b"top\n", "skills/x/SKILL.md": skill_md("x"), "skills/x/agents/openai.yaml": b"a: 1\n",
                 "skills/x/scripts/run.sh": b"#!/bin/sh\necho hi\n", "skills/x/a.txt": b"a\n",
                 "skills/x/a/b.txt": b"b\n", "skills/x/a-b": b"dash\n"}
        listing = git_listing(self, files, executable={"skills/x/scripts/run.sh"})
        self.assertIn("100755", {entry["mode"] for entry in listing["tree"]})
        ids = {entry["path"]: entry["sha"] for entry in listing["tree"]}
        for folder in ("skills/x", "skills/x/agents", "skills/x/a", "skills", ""):
            with self.subTest(folder or "the root"):
                self.assertEqual(source_reviews.git_tree_id(listing["tree"], folder),
                                 ids[folder] if folder else listing["sha"])
        for path, data in files.items():
            self.assertEqual(source_reviews.git_blob_id(data), ids[path], path)


class SkillReviewFixture:
    """source_reviews.py on skill survivors against a fake gh whose git trees carry git's own object ids. review() hands
    source_reviews.py the verified yaml install (LANDSCAPE_SWEEP_SKILLS_YAML), or `install` when given."""

    META = {"full_name": "O/Skills-Repo", "default_branch": "main", "license": {"spdx_id": "MIT"},
            "description": "skills", "stargazers_count": 7, "pushed_at": "2026-09-29T00:00:00Z", "archived": False}

    def review(self, answers, survivors, install=None, flag=None):
        """Runs source_reviews.py; with `flag`, --skills-yaml names that install, and the environment variable an
        absent directory, so only the flag can find it."""
        work, bin_dir = temp_dir(self), temp_dir(self)
        gh = bin_dir / "gh"
        gh.write_text(harness_tests.FAKE_GH.format(python=sys.executable, answers=repr(answers)), encoding="utf-8")
        gh.chmod(0o755)
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
               YAML_ENV: str(work / "no-yaml-install" if flag else install or SKILLS_YAML or work / "no-yaml-install")}
        done = run([sys.executable, HARNESS / "source_reviews.py", "--survivors", write_json(work / "s.json", survivors),
                    "--out", work / "reviews", "--lane", LANE, *(["--skills-yaml", flag] if flag else [])], env=env)
        return done, work / "reviews"

    @staticmethod
    def contents(files) -> dict:
        """{path: bytes}; None stands for a valid SKILL.md named after its folder, or placeholder bytes elsewhere."""
        out = {}
        for path, data in files.items():
            if data is None:
                folder = path.rsplit("/", 2)[-2] if path.endswith("/SKILL.md") else None
                data = skill_md(folder, f"The {folder} skill.") if folder else f"placeholder {path}\n".encode()
            out[path] = data
        return out

    def add_commit(self, answers, commit, files, truncated=False, symlinks=None):
        contents = self.contents(files)
        answers[f"repos/O/Skills-Repo/git/trees/{commit}?recursive=1"] = dict(
            git_listing(self, contents, symlinks=symlinks), truncated=truncated)
        for path, raw in contents.items():
            answers[f"repos/O/Skills-Repo/contents/{path}?ref={commit}"] = {
                "path": path, "type": "file", "encoding": "base64", "content": base64.b64encode(raw).decode()}

    def answers(self, files, pin=PIN, truncated=False, head=None, symlinks=None):
        """Fake gh answers for O/Skills-Repo: `files` and `symlinks` ({path: target}, listed with mode 120000 as git
        lists them) at the adjudicated pin, whose commit lookup answers that pin (pin None: not answered, so gh exits
        1); with `head`, the default branch at HEAD holding `head`."""
        answers = {"repos/o/skills-repo": dict(self.META)}
        if pin:
            answers[f"repos/O/Skills-Repo/commits/{pin}"] = {"sha": pin}
            self.add_commit(answers, pin, files, truncated, symlinks)
        if head is not None:
            answers["repos/O/Skills-Repo/commits/main"] = {"sha": HEAD}
            self.add_commit(answers, HEAD, head, truncated)
        return answers

    @staticmethod
    def survivor(judged=FIND_BUGS, layer_id="skills-debug", repository="o/skills-repo@find-bugs", pin=PIN) -> dict:
        """A survivors.json row: the pin and the sha256 of the SKILL.md bytes the refuters judged."""
        return {"layer_id": layer_id, "repository": repository, "pin": pin,
                "skill_md_sha256": hashlib.sha256(judged).hexdigest()}

    @staticmethod
    def reviewed(out, name="o-skills-repo-find-bugs.json") -> dict:
        return json.loads((out / name).read_text(encoding="utf-8"))

    def stopped(self, done, out) -> dict:
        """The one stopped entry of a run that wrote no review."""
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertEqual(list(out.glob("*.json")), [])
        [entry] = json.loads(done.stdout)
        self.assertEqual(entry["status"], "stopped")
        return entry


@unittest.skipUnless(SKILLS_YAML, NO_READER)
class SkillSourceReviewTests(SkillReviewFixture, unittest.TestCase):
    """Reviews whose SKILL.md copies skill_md.mjs judges: they need node and the verified yaml install."""

    def test_a_skill_survivor_is_reviewed_at_its_adjudicated_pin(self):
        skill = ("---\nname: find-bugs\ndescription: Find bugs in a change.\ndisable-model-invocation: true\n---\n\n"
                 "# Find bugs\n\n" + "A long enough paragraph about how the skill hunts bugs in a change. " * 3).encode()
        files = {"skills/find-bugs/SKILL.md": skill, "skills/other/SKILL.md": None,
                 "skills/find-bugs/agents/openai.yaml":
                     b"interface:\n  display_name: Find bugs\npolicy:\n  allow_implicit_invocation: false\n"}
        done, out = self.review(self.answers(files), [self.survivor(skill, "skills-review"),
                                                      self.survivor(skill, repository="O/Skills-Repo@find-bugs")])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), [{"repository": "O/Skills-Repo@find-bugs",
                                                    "path": "o-skills-repo-find-bugs.json",
                                                    "layers": ["skills-debug", "skills-review"]}])
        review = self.reviewed(out)
        observed = review["observed"]
        self.assertEqual((review["id"], review["reviewed_commit"], review["readme_path"], review["license"]),
                         ("source-review-o-skills-repo-find-bugs", PIN, "skills/find-bugs/SKILL.md", "MIT"))
        self.assertEqual((observed["adjudicated_pin"], observed["pin_lookup"]), (PIN, "ok"))
        self.assertEqual((observed["skill_md_sha256"], observed["survivor_skill_md_sha256"], observed["skill_md_bytes"]),
                         (hashlib.sha256(skill).hexdigest(), hashlib.sha256(skill).hexdigest(), len(skill)))
        # The skill folder's git tree id at the pin: the id the skills CLI's lock records as skillFolderHash.
        listing = git_listing(self, self.contents(files))
        self.assertEqual(observed["skill_folder_tree_sha"],
                         next(entry["sha"] for entry in listing["tree"] if entry["path"] == "skills/find-bugs"))
        self.assertIs(observed["disable_model_invocation"], True)
        self.assertEqual((observed["codex_implicit"], observed["unverified_reason"], observed["openai_yaml_policy_value"]),
                         (False, None, "false"))
        self.assertEqual(observed["skipped_skill_md"], [])
        # The reader behind the verdicts: the pinned yaml package, its npm integrity and the pin file's own sha256.
        pin = json.loads(YAML_PIN_PATH.read_text(encoding="utf-8"))
        self.assertEqual(observed["skill_md_reader"], {
            "package": "yaml@2.9.0", "integrity": pin["package"]["integrity"], "script": "skill_md.mjs",
            "pin_sha256": hashlib.sha256(YAML_PIN_PATH.read_bytes()).hexdigest()})
        self.assertEqual(review["documentation_excerpts"][0]["source"], f"skills/find-bugs/SKILL.md@{PIN}")
        self.assertNotIn("disable-model-invocation", json.dumps(review["documentation_excerpts"]))
        for phrase in ("skill find-bugs", "(the adjudicated pin; license MIT)",
                       "its sha256 matches the survivor's skill_md_sha256", observed["skill_folder_tree_sha"]):
            self.assertIn(phrase, review["claim"])
        self.assertNotIn("default branch", review["claim"])
        # make_result.py matches the review to the survivor as the ledger compares repositories.
        self.assertEqual(make_result.review_key(review["repository"]), make_result.review_key("o/skills-repo@find-bugs"))

    def test_a_skill_without_openai_yaml_keeps_implicit_invocation(self):
        # A trailofbits/skills-shaped plugin: marketplace.json names the plugin, and its skills/ folder holds the skill.
        marketplace = json.dumps({"plugins": [{"name": "p", "source": "./plugins/p"}]}).encode()
        files = {"plugins/p/skills/find-bugs/SKILL.md": FIND_BUGS, ".claude-plugin/marketplace.json": marketplace,
                 "skills/other/SKILL.md": None}
        done, out = self.review(self.answers(files), [self.survivor()])
        self.assertEqual(done.returncode, 0, done.stderr)
        review = self.reviewed(out)
        observed = review["observed"]
        self.assertEqual(review["readme_path"], "plugins/p/skills/find-bugs/SKILL.md")
        self.assertEqual((observed["disable_model_invocation"], observed["codex_implicit"], observed["unverified_reason"]),
                         (False, True, None))
        self.assertIn("no agents/openai.yaml", observed["openai_yaml_policy_note"])

    def test_an_openai_yaml_outside_the_subset_is_unverified_without_pyyaml(self):
        files = {"skills/find-bugs/SKILL.md": FIND_BUGS,
                 "skills/find-bugs/agents/openai.yaml": b"policy: {allow_implicit_invocation: false}\n"}
        done, out = self.review(self.answers(files), [self.survivor()])
        self.assertEqual(done.returncode, 0, done.stderr)
        observed = self.reviewed(out)["observed"]
        if PYYAML:  # source_reviews.py runs under this interpreter
            self.assertEqual((observed["codex_implicit"], observed["unverified_reason"]), (False, None))
            self.assertTrue(observed["openai_yaml_reader"].startswith("PyYAML"), observed["openai_yaml_reader"])
        else:
            self.assertIsNone(observed["codex_implicit"])
            self.assertIn("flow mapping", observed["unverified_reason"])
            self.assertTrue(observed["openai_yaml_reader"].startswith("subset"), observed["openai_yaml_reader"])

    def test_the_cli_discovery_order_picks_skills_over_translations_and_agent_copies(self):
        files = {"skills/find-bugs/SKILL.md": FIND_BUGS, "docs/fr/skills/find-bugs/SKILL.md": None,
                 ".kiro/skills/find-bugs/SKILL.md": None, ".agents/skills/find-bugs/SKILL.md": None,
                 "docs/fr/skills/find-bugs/agents/openai.yaml": None}
        done, out = self.review(self.answers(files), [self.survivor()])
        self.assertEqual(done.returncode, 0, done.stderr)
        review = self.reviewed(out)
        self.assertEqual(review["readme_path"], "skills/find-bugs/SKILL.md")
        self.assertIn("skills/, the first location", review["observed"]["skill_md_found_by"])
        self.assertIsNone(review["observed"]["openai_yaml_path"])  # the translation's openai.yaml is not the skill's

    def test_claude_code_boolean_values_set_disable_model_invocation(self):
        for value, expected in (("true", True), ("yes", True), ("Yes", True), ("ON", True), ("1", True),
                                ("'yes'  # quoted", True), ("false", False), ("no", False), ("off", False),
                                ("0", False), (None, False)):
            with self.subTest(value=value):
                flag = "" if value is None else f"disable-model-invocation: {value}\n"
                skill = f"---\nname: find-bugs  # the folder's name\ndescription: Find bugs.\n{flag}---\n\nBody.\n".encode()
                done, out = self.review(self.answers({"skills/find-bugs/SKILL.md": skill}), [self.survivor(skill)])
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertIs(self.reviewed(out)["observed"]["disable_model_invocation"], expected)

    def test_bytes_other_than_the_judged_skill_md_are_refused(self):
        judged = skill_md(description="Find bugs, as judged.")
        done, out = self.review(self.answers({"skills/find-bugs/SKILL.md": FIND_BUGS}), [self.survivor(judged)])
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("not the survivor's skill_md_sha256", done.stderr)
        [entry] = json.loads(done.stdout)
        self.assertEqual((entry["status"], entry["pin"], entry["pin_lookup"]), ("stopped", PIN, "ok"))
        self.assertEqual(list(out.glob("*.json")), [])

    def test_one_skill_judged_at_two_pins_gets_one_review_per_pin(self):
        older = skill_md(description="Find bugs, older.")
        answers = self.answers({"skills/find-bugs/SKILL.md": older})
        answers[f"repos/O/Skills-Repo/commits/{HEAD}"] = {"sha": HEAD}
        self.add_commit(answers, HEAD, {"skills/find-bugs/SKILL.md": FIND_BUGS})
        done, out = self.review(answers, [self.survivor(older), self.survivor(FIND_BUGS, "skills-review", pin=HEAD)])
        self.assertEqual(done.returncode, 0, done.stderr)
        written = json.loads(done.stdout)
        self.assertEqual(sorted(item["layers"] for item in written), [["skills-debug"], ["skills-review"]])
        self.assertEqual(len({item["path"] for item in written}), 2)
        self.assertTrue(all(re.fullmatch(r"o-skills-repo-find-bugs-[0-9a-f]{10}\.json", item["path"]) for item in written))
        commits = {self.reviewed(out, item["path"])["reviewed_commit"]: item["layers"] for item in written}
        self.assertEqual(commits, {PIN: ["skills-debug"], HEAD: ["skills-review"]})
        # make_result.py takes, for each layer's survivor, the review of that repository that names the layer.
        for layer_id in ("skills-debug", "skills-review"):
            matches = [item for item in written if make_result.review_key(item["repository"])
                       == make_result.review_key("o/skills-repo@find-bugs") and layer_id in item["layers"]]
            self.assertEqual(len(matches), 1, layer_id)

    def test_an_unresolvable_skill_is_reported_and_not_reviewed(self):
        other_root = skill_md("other-skill", "Another skill.")
        cases = (
            ({"skills/other/SKILL.md": None}, False, "no folder named find-bugs in the locations the CLI searches"),
            ({"docs/en/skills/find-bugs/SKILL.md": None, "skills/other/SKILL.md": None}, False,
             "no folder named find-bugs in the locations the CLI searches"),
            ({"skills/a/find-bugs/SKILL.md": None, "skills/b/find-bugs/SKILL.md": None}, False,
             "2 folders named find-bugs in skills/"),
            ({"a/find-bugs/SKILL.md": None, "b/find-bugs/SKILL.md": None}, False, "2 unnested folders named find-bugs"),
            ({"SKILL.md": other_root, "skills/find-bugs/SKILL.md": FIND_BUGS}, False,
             f"the root SKILL.md at {PIN} is the skill 'other-skill'"),
            ({"skills/find-bugs/SKILL.md": FIND_BUGS}, True, "is truncated"))
        for files, truncated, message in cases:
            with self.subTest(message):
                done, out = self.review(self.answers(files, truncated=truncated), [self.survivor()])
                self.assertEqual(done.returncode, 1, done.stdout)
                self.assertIn(message, done.stderr)
                self.assertEqual([entry["status"] for entry in json.loads(done.stdout)], ["stopped"])

    def test_a_root_skill_md_without_a_description_is_skipped_like_the_cli_skips_it(self):
        done, out = self.review(self.answers({"SKILL.md": NO_DESCRIPTION, "skills/find-bugs/SKILL.md": FIND_BUGS}),
                                [self.survivor()])
        self.assertEqual(done.returncode, 0, done.stderr)
        review = self.reviewed(out)
        self.assertEqual(review["readme_path"], "skills/find-bugs/SKILL.md")
        self.assertEqual(review["observed"]["skipped_skill_md"],
                         [{"path": "SKILL.md", "reason": "missing required frontmatter field(s): description"}])

    # vercel-labs/skills v1.7.0 (src/skills.ts): parseSkillMd skips a SKILL.md without a name or description before
    # discoverSkills applies its location order, so an invalid copy never claims the name (GPT-6 review of #541).

    def test_an_invalid_earlier_copy_is_skipped_and_a_valid_later_copy_wins(self):
        # The root's child folders come first, and find-bugs/ has no description.
        done, out = self.review(self.answers({"find-bugs/SKILL.md": NO_DESCRIPTION,
                                              "skills/find-bugs/SKILL.md": FIND_BUGS}), [self.survivor()])
        self.assertEqual(done.returncode, 0, done.stderr)
        review = self.reviewed(out)
        self.assertEqual(review["readme_path"], "skills/find-bugs/SKILL.md")
        self.assertEqual(review["observed"].get("skipped_skill_md"), [
            {"path": "find-bugs/SKILL.md", "reason": "missing required frontmatter field(s): description"}])

    def test_a_skill_whose_every_copy_is_invalid_is_reported_invalid_not_reviewed(self):
        done, out = self.review(self.answers({"find-bugs/SKILL.md": NO_DESCRIPTION,
                                              "skills/find-bugs/SKILL.md": NO_NAME}), [self.survivor(NO_DESCRIPTION)])
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertEqual(list(out.glob("*.json")), [])
        self.assertIn("find-bugs/SKILL.md: missing required frontmatter field(s): description", done.stderr)
        self.assertIn("skills/find-bugs/SKILL.md: missing required frontmatter field(s): name", done.stderr)
        [entry] = json.loads(done.stdout)
        self.assertEqual((entry["status"], entry["pin_lookup"]), ("stopped", "ok"))
        self.assertIn("every copy of find-bugs", entry["reason"])

    def test_a_valid_earlier_copy_wins_over_an_invalid_later_one(self):
        done, out = self.review(self.answers({"find-bugs/SKILL.md": FIND_BUGS,
                                              "skills/find-bugs/SKILL.md": NO_DESCRIPTION}), [self.survivor()])
        self.assertEqual(done.returncode, 0, done.stderr)
        review = self.reviewed(out)
        self.assertEqual(review["readme_path"], "find-bugs/SKILL.md")
        self.assertEqual(review["observed"].get("skipped_skill_md"), [])  # the later copy is never read

    def test_one_valid_copy_among_same_location_duplicates_is_taken(self):
        done, out = self.review(self.answers({"skills/a/find-bugs/SKILL.md": NO_NAME,
                                              "skills/b/find-bugs/SKILL.md": FIND_BUGS}), [self.survivor()])
        self.assertEqual(done.returncode, 0, done.stderr)
        review = self.reviewed(out)
        self.assertEqual(review["readme_path"], "skills/b/find-bugs/SKILL.md")
        self.assertEqual(review["observed"].get("skipped_skill_md"), [
            {"path": "skills/a/find-bugs/SKILL.md", "reason": "missing required frontmatter field(s): name"}])

    def test_the_recursive_search_runs_when_no_location_holds_a_valid_skill(self):
        # discoverSkills searches every folder only when its locations added no skill; skills/other adds none.
        done, out = self.review(self.answers({"skills/other/SKILL.md": skill_md("other", None),
                                              "x/y/find-bugs/SKILL.md": FIND_BUGS}), [self.survivor()])
        self.assertEqual(done.returncode, 0, done.stderr)
        review = self.reviewed(out)
        self.assertEqual(review["readme_path"], "x/y/find-bugs/SKILL.md")
        self.assertIn("recursive search", review["observed"]["skill_md_found_by"])

    # GPT-6 round-3 review of #541: a list description was read as a string, so an invalid earlier copy still won.
    # parseSkillMd skips a name or description that is not a string (src/skills.ts lines 108-115), and the yaml package
    # reads a list or a mapping as an object (checked with yaml 2.9.0 and `npx skills@1.7.0 add <fixture> --list`).

    def test_an_earlier_copy_with_a_list_or_mapping_description_is_skipped_and_a_valid_later_copy_wins(self):
        for shape in ("- Find bugs.", "summary: Find bugs."):
            with self.subTest(shape):
                invalid = skill_md(description=None, extra=("description:", f"  {shape}"))
                done, out = self.review(self.answers({"find-bugs/SKILL.md": invalid,
                                                      "skills/find-bugs/SKILL.md": FIND_BUGS}), [self.survivor()])
                self.assertEqual(done.returncode, 0, done.stderr)
                review = self.reviewed(out)
                self.assertEqual(review["readme_path"], "skills/find-bugs/SKILL.md")
                self.assertEqual(review["observed"]["skipped_skill_md"], [{
                    "path": "find-bugs/SKILL.md",
                    "reason": 'frontmatter "name" and "description" must be strings (got string and object)'}])

    def test_a_block_scalar_description_is_a_string_and_one_without_text_is_missing(self):
        literal = skill_md(description="|", extra=("  Find bugs in a change.",))
        done, out = self.review(self.answers({"skills/find-bugs/SKILL.md": literal}), [self.survivor(literal)])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.reviewed(out)["readme_path"], "skills/find-bugs/SKILL.md")
        done, out = self.review(self.answers({"find-bugs/SKILL.md": skill_md(description=">-"),
                                              "skills/find-bugs/SKILL.md": FIND_BUGS}), [self.survivor()])
        self.assertEqual(done.returncode, 0, done.stderr)
        review = self.reviewed(out)
        self.assertEqual(review["readme_path"], "skills/find-bugs/SKILL.md")
        self.assertEqual(review["observed"]["skipped_skill_md"], [
            {"path": "find-bugs/SKILL.md", "reason": "missing required frontmatter field(s): description"}])

    # The Opus round-3 review of #541: both frontmatter readers of round 3 still gave a verdict on copies the pinned
    # CLI's yaml package reads otherwise (findings 2-4); the CLI's own parseSkillMd now decides (skill_md.mjs).

    def test_an_earlier_copy_the_yaml_package_refuses_loses_to_a_valid_later_copy(self):
        # Finding 2 (the PyYAML reader took under-indented quoted and flow continuations) and finding 4 (the subset
        # reader took bad nested indentation, an empty flow item and mismatched brackets): each earlier copy is a YAML
        # parse error to the CLI, so the valid later copy wins.
        for extra, warning in (
                (('description: "Find bugs', 'in a change."'), 'Missing closing "quote'),
                (("description: Find bugs.", "tags: [a,", "b]"), "Flow sequence in block collection"),
                (("description: Find bugs.", "metadata:", "  a: 1", " b: 2"),
                 "All mapping items must start at the same column"),
                (("description: Find bugs.", "tags: [,]"), "Unexpected , in flow sequence"),
                (("description: Find bugs.", "tags: {a: [b}]"), "Flow sequence in block collection")):
            with self.subTest(warning):
                earlier = skill_md(description=None, extra=extra)
                done, out = self.review(self.answers({"find-bugs/SKILL.md": earlier,
                                                      "skills/find-bugs/SKILL.md": FIND_BUGS}), [self.survivor()])
                self.assertEqual(done.returncode, 0, done.stderr)
                review = self.reviewed(out)
                self.assertEqual(review["readme_path"], "skills/find-bugs/SKILL.md")
                [skipped] = review["observed"]["skipped_skill_md"]
                self.assertEqual(skipped["path"], "find-bugs/SKILL.md")
                self.assertTrue(skipped["reason"].startswith(f"YAML parse error: {warning}"), skipped["reason"])

    def test_a_line_break_other_than_lf_or_crlf_leaves_the_copy_without_a_verdict(self):
        # Finding 3: the yaml package reads "name: find-bugs<CR>description: ..." as one plain scalar, so the CLI skips
        # the copy, while libyaml (Codex's serde_yaml) breaks the line there. No verdict: when that copy decides the
        # pick, the survivor stops.
        for text in ("find-bugs\rdescription: Find bugs.", f"find-bugs{LS}description: Find bugs."):
            with self.subTest(repr(text[9])):
                odd = f"---\nname: {text}\n---\n\nBody.\n".encode()
                done, out = self.review(self.answers({"find-bugs/SKILL.md": odd,
                                                      "skills/find-bugs/SKILL.md": FIND_BUGS}), [self.survivor()])
                entry = self.stopped(done, out)
                self.assertEqual(entry["pin_lookup"], "ok")
                for phrase in ("find-bugs/SKILL.md", "a line break to libyaml", "which copy it installs, is unverified"):
                    self.assertIn(phrase, entry["reason"])
        # The same break in the copy the survivor judged: no review rests on it either.
        odd = b"---\nname: find-bugs\ndescription: Find\rbugs.\n---\n\nBody.\n"
        done, out = self.review(self.answers({"skills/find-bugs/SKILL.md": odd}), [self.survivor(odd)])
        self.assertIn("a CR without LF", self.stopped(done, out)["reason"])
        # In the body it changes no frontmatter, and the copy is reviewed.
        body = FIND_BUGS + b"More\rtext" + LS.encode() + b".\n"
        done, out = self.review(self.answers({"skills/find-bugs/SKILL.md": body}), [self.survivor(body)])
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_anchors_and_tags_are_read_as_the_cli_reads_them(self):
        # The yaml package follows an anchor and resolves !!str, so the earlier copy is the CLI's pick (round 3 left
        # a tag unverified in both readers and an anchor in the subset reader).
        for description in ("&d Find bugs.", "!!str Find bugs."):
            with self.subTest(description):
                earlier = skill_md(description=description)
                done, out = self.review(self.answers({"find-bugs/SKILL.md": earlier,
                                                      "skills/find-bugs/SKILL.md": FIND_BUGS}), [self.survivor(earlier)])
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(self.reviewed(out)["readme_path"], "find-bugs/SKILL.md")

    def test_the_name_is_matched_as_the_cli_records_it(self):
        spaced = skill_md(name='" find-bugs "')  # sanitizeMetadata trims it (src/sanitize.ts lines 61-65)
        done, out = self.review(self.answers({"skills/find-bugs/SKILL.md": spaced}), [self.survivor(spaced)])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.reviewed(out)["readme_path"], "skills/find-bugs/SKILL.md")

    def test_a_name_that_sanitizes_to_nothing_is_matched_by_its_folder(self):
        # Finding 6: getSkillDisplayName (src/skills.ts lines 331-333) matches a name that sanitizeMetadata empties by
        # its folder's name, and terminal escapes are stripped before any name is compared (src/sanitize.ts 19-65).
        for name in ('"\\e[31m"', '"   "', '"\\e]0;title\\a"', '"find-\\e[1mbugs"', '"\\e[1mFind-Bugs\\e[0m"'):
            with self.subTest(name):
                copy = skill_md(name=name)
                done, out = self.review(self.answers({"skills/find-bugs/SKILL.md": copy}), [self.survivor(copy)])
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(self.reviewed(out)["readme_path"], "skills/find-bugs/SKILL.md")
        # A name that sanitizes to another skill's name is not a copy of find-bugs.
        other = skill_md(name='"other-\\e[1mskill"')
        done, out = self.review(self.answers({"skills/find-bugs/SKILL.md": other}), [self.survivor(other)])
        self.assertIn("its name field names the skill 'other-skill', not find-bugs", self.stopped(done, out)["reason"])
        # A valid root SKILL.md is the only skill, and one whose name sanitizes to nothing is named after the CLI's
        # clone directory: no review.
        blank = skill_md(name='"\\e[31m"')
        done, out = self.review(self.answers({"SKILL.md": blank, "skills/find-bugs/SKILL.md": FIND_BUGS}),
                                [self.survivor(blank)])
        self.assertIn("a name that sanitizes to nothing", self.stopped(done, out)["reason"])

    def test_an_openai_yaml_with_an_escape_yaml_does_not_define_is_unverified(self):
        # GPT-6 round-3 review of #541: without PyYAML this was a definite codex_implicit false.
        files = {"skills/find-bugs/SKILL.md": FIND_BUGS,
                 "skills/find-bugs/agents/openai.yaml": b'note: "C:\\skills"\npolicy:\n  allow_implicit_invocation: false\n'}
        done, out = self.review(self.answers(files), [self.survivor()])
        self.assertEqual(done.returncode, 0, done.stderr)
        observed = self.reviewed(out)["observed"]
        self.assertIsNone(observed["codex_implicit"])
        self.assertIn("PyYAML cannot parse" if PYYAML else "the escape \\s", observed["unverified_reason"])

    # Opus round-4 review of #541, D1: the CLI walks a search location through a symlink at or above it (readdir
    # follows it: dist/cli.mjs lines 1339-1370) and keeps the first skill of a name (seenNames, line 1352), while the git
    # tree lists the symlink as one blob and nothing below it. Round 4 reviewed a later copy the CLI throws away.

    def test_a_symlinked_search_location_before_the_pick_stops_the_review(self):
        marketplace = json.dumps({"plugins": [{"name": "p", "source": "./plugins/p"}]}).encode()
        cases = {
            # skills -> packages/core/skills: the CLI takes packages/core/skills/find-bugs through skills/ and drops
            # the .agents/skills copy, which the review named.
            "a symlinked skills folder": (
                {"packages/core/skills/find-bugs/SKILL.md": FIND_BUGS, ".agents/skills/find-bugs/SKILL.md": FIND_BUGS},
                {"skills": "packages/core/skills"}, "the search location skills/ is a symlink"),
            # .claude -> config/claude: .claude/skills lies below the symlink and comes before .github/skills.
            "a symlink above an agent folder": (
                {"config/claude/skills/find-bugs/SKILL.md": FIND_BUGS, ".github/skills/find-bugs/SKILL.md": FIND_BUGS},
                {".claude": "config/claude"}, "the search location .claude/skills/ is below the symlink .claude"),
            # plugins -> vendor/plugins: the plugin's skills/ folder holds a valid skill, so the CLI never runs the
            # recursive search that found x/y/find-bugs for the review.
            "a plugin folder below a symlink": (
                {".claude-plugin/marketplace.json": marketplace, "vendor/plugins/p/skills/other/SKILL.md": None,
                 "x/y/find-bugs/SKILL.md": FIND_BUGS},
                {"plugins": "vendor/plugins"}, "the search location plugins/p/skills/ is below the symlink plugins"),
            # .claude-plugin -> meta: the CLI reads the manifest through the symlink; the review cannot, and the plugin
            # folders it declares come before the recursive search.
            "manifests behind a symlink": (
                {"meta/marketplace.json": marketplace, "plugins/p/skills/other/SKILL.md": None,
                 "x/y/find-bugs/SKILL.md": FIND_BUGS},
                {".claude-plugin": "meta"}, "the plugin manifest folder .claude-plugin is a symlink"),
            # .claude-plugin/marketplace.json -> ../meta/marketplace.json: readFile follows the link; the review reads
            # no verified bytes for it.
            "a symlinked manifest file": (
                {"meta/marketplace.json": marketplace, "plugins/p/skills/other/SKILL.md": None,
                 "x/y/find-bugs/SKILL.md": FIND_BUGS},
                {".claude-plugin/marketplace.json": "../meta/marketplace.json"},
                "the plugin manifest .claude-plugin/marketplace.json has no verified bytes"),
            # skills/tools/SKILL.md -> a missing file: hasSkillMd is false for it, so the CLI walks below skills/tools and
            # takes skills/tools/find-bugs first; the review treated skills/tools as a skill and named the later copy.
            "a symlinked SKILL.md above a copy": (
                {"skills/tools/find-bugs/SKILL.md": FIND_BUGS, ".agents/skills/find-bugs/SKILL.md": FIND_BUGS},
                {"skills/tools/SKILL.md": "../../missing.md"},
                "skills/tools/SKILL.md is a symlink with the skill folder skills/tools/find-bugs below it"),
        }
        for label, (files, symlinks, phrase) in cases.items():
            with self.subTest(label):
                entry = self.stopped(*self.review(self.answers(files, symlinks=symlinks), [self.survivor()]))
                self.assertEqual(entry["pin_lookup"], "ok")
                for expected in (phrase, "no earlier location the CLI searches holds a valid copy of find-bugs",
                                 "which copy the skills CLI installs is unverified"):
                    self.assertIn(expected, entry["reason"])

    def test_a_symlink_that_cannot_change_the_pick_leaves_the_review(self):
        # The common layout: .claude/skills -> ../skills, searched after skills/, so the copy the CLI meets there again
        # has a name it has seen. A symlinked folder inside a location is skipped by the CLI (its entry is not a
        # directory) as the tree shows it, a symlinked SKILL.md with nothing below it shadows nothing, and a symlinked
        # plugin manifest only adds locations after skills/ (round 4 stopped every review with one).
        files = {"skills/find-bugs/SKILL.md": FIND_BUGS}
        symlinks = {".claude/skills": "../skills", "skills/alias": "find-bugs", "skills/tools/SKILL.md": "../../x.md",
                    ".claude-plugin/marketplace.json": "../x.json"}
        done, out = self.review(self.answers(files, symlinks=symlinks), [self.survivor()])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.reviewed(out)["readme_path"], "skills/find-bugs/SKILL.md")

    def test_the_skills_yaml_flag_names_the_install(self):
        # Test gap (round-4 review): --skills-yaml was never passed; here the environment variable names an absent
        # directory and HOME holds none, so only the flag finds the install.
        done, out = self.review(self.answers({"skills/find-bugs/SKILL.md": FIND_BUGS}), [self.survivor()],
                                flag=SKILLS_YAML)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.reviewed(out)["observed"]["skill_md_reader"]["package"], "yaml@2.9.0")

    # The folder hash (GPT-6 review of #541: a SKILL.md hash did not freeze agents/openai.yaml).

    def test_the_folder_hash_covers_agents_openai_yaml(self):
        files = {"skills/find-bugs/SKILL.md": FIND_BUGS,
                 "skills/find-bugs/agents/openai.yaml": b"policy:\n  allow_implicit_invocation: true\n"}
        changed = dict(files, **{"skills/find-bugs/agents/openai.yaml": b"policy:\n  allow_implicit_invocation: false\n"})
        observed = []
        for version in (files, changed):
            done, out = self.review(self.answers(version), [self.survivor()])
            self.assertEqual(done.returncode, 0, done.stderr)
            observed.append(self.reviewed(out)["observed"])
        folder = [item.get("skill_folder_tree_sha") for item in observed]
        self.assertEqual([item["skill_md_sha256"] for item in observed], [hashlib.sha256(FIND_BUGS).hexdigest()] * 2)
        self.assertTrue(all(isinstance(value, str) and HEX40.fullmatch(value) for value in folder), folder)
        self.assertNotEqual(folder[0], folder[1])
        self.assertEqual([item["codex_implicit"] for item in observed], [True, False])

    def test_a_tree_listing_that_does_not_cover_the_bytes_read_is_refused(self):
        files = {"skills/find-bugs/SKILL.md": FIND_BUGS,
                 "skills/find-bugs/agents/openai.yaml": b"policy:\n  allow_implicit_invocation: false\n"}
        other = git_listing(self, dict(files, **{"skills/find-bugs/agents/openai.yaml": b"policy:\n  products:\n"}))
        for path, message in (("skills/find-bugs/agents/openai.yaml", "not the git blob"),
                              ("skills/find-bugs", "does not hash to")):
            with self.subTest(path):
                answers = self.answers(files)
                listed = answers[f"repos/O/Skills-Repo/git/trees/{PIN}?recursive=1"]["tree"]
                entry = next(item for item in listed if item["path"] == path)
                entry["sha"] = next(item["sha"] for item in other["tree"] if item["path"] == path)
                done, out = self.review(answers, [self.survivor()])
                self.assertEqual(done.returncode, 1, done.stdout)
                self.assertIn(message, done.stderr)
                self.assertEqual(list(out.glob("*.json")), [])


class SkillReviewBeforeTheReaderTests(SkillReviewFixture, unittest.TestCase):
    """Refusals that come before skill_md.mjs judges any copy, so they hold without node or the yaml install: every
    review here runs with no yaml install at all."""

    def review(self, answers, survivors, install=None, path=None):
        if path is None:
            return super().review(answers, survivors, install or temp_dir(self) / "no-yaml-install")
        work, bin_dir = temp_dir(self), temp_dir(self)
        (bin_dir / "gh").write_text(harness_tests.FAKE_GH.format(python=sys.executable, answers=repr(answers)),
                                    encoding="utf-8")
        (bin_dir / "gh").chmod(0o755)
        done = run([sys.executable, HARNESS / "source_reviews.py", "--survivors", write_json(work / "s.json", survivors),
                    "--out", work / "reviews", "--lane", LANE], env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{path}"})
        return done, work / "reviews"

    def test_without_the_reader_a_survivor_stops_and_no_copy_is_guessed(self):
        answers = self.answers({"skills/find-bugs/SKILL.md": FIND_BUGS})
        entry = self.stopped(*self.review(answers, [self.survivor()]))
        self.assertEqual(entry["pin_lookup"], "ok")
        for phrase in ("skills/find-bugs/SKILL.md", "the yaml install skill_md.mjs verifies is not_installed",
                       "skills-yaml.pin.json", "which copy it installs, is unverified"):
            self.assertIn(phrase, entry["reason"])
        # Without node on PATH (the fake gh runs by its own interpreter), nothing is parsed either.
        entry = self.stopped(*self.review(answers, [self.survivor()], path=temp_dir(self)))
        self.assertIn("node is not installed", entry["reason"])

    def test_an_earlier_copy_gh_cannot_read_stops_the_review(self):
        # The CLI reads the blob from its clone; a failed API read says nothing about whether the CLI takes it.
        answers = self.answers({"find-bugs/SKILL.md": FIND_BUGS, "skills/find-bugs/SKILL.md": FIND_BUGS})
        del answers[f"repos/O/Skills-Repo/contents/find-bugs/SKILL.md?ref={PIN}"]
        entry = self.stopped(*self.review(answers, [self.survivor()]))
        self.assertEqual(entry["pin_lookup"], "ok")
        self.assertIn("find-bugs/SKILL.md could not be read here", entry["reason"])

    def test_every_copy_read_is_the_blob_the_tree_lists(self):
        # Opus round-3 review of #541, finding 7: only the chosen copy's bytes were checked against the tree, so a
        # skipped copy was judged on whatever the contents API returned, and a symlink ended in KeyError('content').
        def answers_with(contents, symlink=None, listed=NO_DESCRIPTION):
            answers = self.answers({"find-bugs/SKILL.md": listed, "skills/find-bugs/SKILL.md": FIND_BUGS})
            if symlink:
                listing = git_listing(self, {"skills/find-bugs/SKILL.md": FIND_BUGS},
                                      symlinks={"find-bugs/SKILL.md": symlink})
                answers[f"repos/O/Skills-Repo/git/trees/{PIN}?recursive=1"] = listing
            answers[f"repos/O/Skills-Repo/contents/find-bugs/SKILL.md?ref={PIN}"] = contents
            return answers

        valid = {"path": "find-bugs/SKILL.md", "type": "file", "encoding": "base64",
                 "content": base64.b64encode(FIND_BUGS).decode()}
        invalid = dict(valid, content=base64.b64encode(NO_DESCRIPTION).decode())
        cases = {
            # the contents API returns other bytes than the blob the tree lists: invalid bytes for a valid copy (round 3
            # skipped the copy and reviewed the later one) and valid bytes for an invalid one
            "other bytes skip a valid copy": (answers_with(invalid, listed=FIND_BUGS), "are not the git blob"),
            "other bytes": (answers_with(valid), "are not the git blob"),
            # a file the contents API returns without content (over 1 MB it answers with the encoding "none")
            "no content": (answers_with(dict(valid, encoding="none", content="")),
                           "returned no base64 content (type file, encoding none)"),
            # a symlink to a file in the repository: GitHub answers with that file's bytes
            "a symlink to a file": (answers_with(valid, symlink="../skills/find-bugs/SKILL.md"), "a symlink"),
            # a symlink to nothing: GitHub answers with a symlink entry and no content
            "a dangling symlink": (answers_with({"path": "find-bugs/SKILL.md", "type": "symlink", "target": "../x.md"},
                                                symlink="../x.md"), "a symlink"),
        }
        for name, (answers, phrase) in cases.items():
            with self.subTest(name):
                entry = self.stopped(*self.review(answers, [self.survivor()]))
                self.assertEqual(entry["pin_lookup"], "ok")
                for expected in ("find-bugs/SKILL.md", phrase, "which copy it installs, is unverified"):
                    self.assertIn(expected, entry["reason"])

    # The adjudicated pin (GPT-6 review of #541: an unreadable pin fell back to the default branch, and a null hash
    # let other bytes pass).

    def test_an_unreadable_pin_gives_no_review_and_a_stopped_layer(self):
        # The pin's commit lookup is not answered (gh exits 1); the first round reviewed the default branch instead.
        answers = self.answers({}, pin=None, head={"skills/find-bugs/SKILL.md": FIND_BUGS})
        done, out = self.review(answers, [self.survivor()])
        entry = self.stopped(done, out)
        self.assertEqual({key: entry[key] for key in ("repository", "layers", "pin", "pin_lookup", "status")},
                         {"repository": "o/skills-repo@find-bugs", "layers": ["skills-debug"], "pin": PIN,
                          "pin_lookup": "failed", "status": "stopped"})
        self.assertIn(f"the adjudicated pin {PIN} is unreadable", entry["reason"])
        self.assertIn(f"gh api repos/O/Skills-Repo/commits/{PIN}", entry["reason"])
        self.assertIn(entry["reason"], done.stderr)

    def test_a_pin_that_resolves_to_another_commit_is_refused(self):
        answers = self.answers({"skills/find-bugs/SKILL.md": FIND_BUGS}, head={"skills/find-bugs/SKILL.md": FIND_BUGS})
        answers[f"repos/O/Skills-Repo/commits/{PIN}"] = {"sha": HEAD}
        entry = self.stopped(*self.review(answers, [self.survivor()]))
        self.assertEqual(entry["pin_lookup"], "failed")
        self.assertIn(f"not the adjudicated pin {PIN}", entry["reason"])

    def test_a_survivor_without_a_pin_or_with_a_null_hash_is_not_reviewed(self):
        files = {"skills/find-bugs/SKILL.md": FIND_BUGS}
        for survivor, lookup, message in ((dict(self.survivor(), pin=None), "failed", "names no adjudicated pin"),
                                          (dict(self.survivor(), pin="c0ffee"), "failed", "not a 40-hex commit"),
                                          (dict(self.survivor(), skill_md_sha256=None), None,
                                           "skill_md_sha256 is null")):
            with self.subTest(message):
                entry = self.stopped(*self.review(self.answers(files, head=files), [survivor]))
                self.assertEqual(entry["pin_lookup"], lookup)
                self.assertIn(message, entry["reason"])


# --------------------------------------------------------------------------- the decision record


C1 = "gamma/skills@review-kit"


def skills_sweep_result() -> dict:
    votes, gpt6_entry = harness_tests.votes, harness_tests.gpt6_entry
    debug = {"layer_id": "skills-debug", "catalog": "skills", "round": "first", "followup_reason": None,
             "claude_discover": skills_discovery("skills-debug", [skill_proposal(A1, proposed_label="targeted_candidate"),
                                                                  skill_proposal(B1)]),
             "gpt6_discover": gpt6_entry(skills_discovery("skills-debug", [skill_proposal(A1_GPT6)])),
             "merged": [dict(skill_proposal(A1, proposed_label="targeted_candidate"), repository=A1,
                             families=["claude", "gpt6"]),
                        dict(skill_proposal(B1), repository=B1, families=["claude"])],
             "dropped": [],
             "facts": votes("skills-debug", "facts", {A1: False, B1: False}),
             "fit_claude": votes("skills-debug", "fit", {A1: False, B1: True}),
             "fit_gpt6": gpt6_entry(votes("skills-debug", "fit", {A1: False, B1: False}))}
    review = {"layer_id": "skills-review", "catalog": "skills", "round": "first", "followup_reason": None,
              "claude_discover": skills_discovery("skills-review", [skill_proposal(C1, lifecycle_task="review")]),
              "gpt6_discover": gpt6_entry(skills_discovery("skills-review", [])),
              "merged": [dict(skill_proposal(C1, lifecycle_task="review"), repository=C1, families=["claude"])],
              "dropped": [],
              "facts": votes("skills-review", "facts", {C1: True}),
              "fit_claude": votes("skills-review", "fit", {C1: False}),
              "fit_gpt6": gpt6_entry(votes("skills-review", "fit", {C1: False}))}
    return {"sweep": LANE, "first": [debug, review],
            "critic": {"followup_layers": [], "general": ["Discovery leaned on one registry."]},
            "followups": [], "lost_first": []}


class DecisionRecordTests(unittest.TestCase):
    def setUp(self):
        self.root = temp_dir(self)
        (self.root / "catalogs/landscape").mkdir(parents=True)
        shutil.copy(CATALOG, self.root / "catalogs/landscape/skills-lifecycle.json")
        res = skills_sweep_result()
        scope = {"platform_profiles_sha256": PLAT,
                 "requirement_sha256": {"skills/skills-debug": REQ, "skills/skills-review": REQ}}
        out = convert.convert(res, scope, LANE, convert.resolved_models(None))
        base = f"evidence/artifacts/{LANE}"
        write_json(self.root / base / "returns.json", out["returns"])
        labels = [f"{role}:{layer}" for layer in ("skills-debug", "skills-review") for role in
                  ("discover", "gpt6-discover", "refute-facts", "refute-fit", "gpt6-refute-fit")] + ["critic"]
        usage = usage_record.record(harness_tests.child_usage_raw("wf_fixture-1", labels), 0, "cmd", ROOT)
        write_json(self.root / f"{base}-attempts/child-usage-wf_fixture-1.json", usage)
        manifest = {"checked_at": "2026-09-30", "critic": res["critic"]}
        write_json(self.root / "catalogs/sota-convergence/manifest-20260930.json", manifest)
        write_json(self.root / base / "acme-agent-skills-debug-kit.json", A1_REVIEW)  # at the adjudicated pin
        result = make_result.build_result(
            layers=out["layers"], reviews=A1_WRITTEN, usage=usage, manifest=manifest, sweep_id=LANE, lane=LANE,
            returns_ref=f"{base}/returns.json", usage_ref=f"{base}-attempts/child-usage-wf_fixture-1.json",
            manifest_ref="catalogs/sota-convergence/manifest-20260930.json", prompts_sha256="c" * 64,
            returns=out["returns"], load_review=lambda path: json.loads((self.root / path).read_text(encoding="utf-8")))
        self.result = write_json(self.root / "RESULT.json", result)
        self.record = self.root / "docs/decisions/2026-09-30-skills-landscape-sweep.md"

    def write(self, *extra):
        return run([sys.executable, HARNESS / "make_result.py", "--decision-record", self.result,
                    "--repo-root", self.root, *extra])

    def test_the_record_carries_survivors_refutations_critic_and_overturn_conditions(self):
        done = self.write()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("docs/decisions/2026-09-30-skills-landscape-sweep.md", done.stdout)
        text = self.record.read_text(encoding="utf-8")
        headings = [line for line in text.splitlines() if line.startswith("## ")]
        self.assertEqual(headings, ["## Context", "## Alternatives", "## Decision", "## Overturn condition", "## Sources"])
        self.assertTrue(text.startswith(f"# Decision: skills landscape sweep {LANE} (2026-09-30)"))
        context, alternatives, decision, overturn, sources = re.split(r"^## .*$", text, flags=re.M)[1:]
        self.assertIn(A1, decision)
        self.assertIn("targeted_candidate", decision)
        self.assertIn("replaces diagnosing-bugs", decision)
        self.assertIn(f"{LANE}/acme-agent-skills-debug-kit.json", decision)
        self.assertIn("No proposal survived", decision)  # skills-review
        self.assertIn(B1, alternatives)
        self.assertIn(f"fit on {B1}", alternatives)  # the Claude fit refuter's reasoning
        self.assertIn(C1, alternatives)
        self.assertIn(f"facts on {C1}", alternatives)
        self.assertIn("Discovery leaned on one registry.", context)
        self.assertIn(f"skill-creator's paired with-skill/without-skill benchmark on ten frozen debug prompts decides {A1}",
                      overturn)
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        debug_task = next(task for task in catalog["tasks"] if task["layer_id"] == "skills-debug")
        self.assertIn(debug_task["overturn_when"], overturn)
        for ref in (f"evidence/artifacts/{LANE}/returns.json", "catalogs/sota-convergence/manifest-20260930.json",
                    f"evidence/artifacts/{LANE}-attempts/child-usage-wf_fixture-1.json",
                    "catalogs/landscape/skills-lifecycle.json"):
            self.assertIn(ref, sources)
        self.assertIn("edits no manifest", context)
        patterns = sweep_common.private_content(ROOT)
        self.assertEqual(sweep_common.private_findings(text, patterns), [])

    def test_lost_workers_are_reported_as_incomplete_layers_not_refutations(self):
        result = json.loads(self.result.read_text())
        self.assertNotIn("lost_workers", result)
        result["layers"][1]["refuted"], result["layers"][1]["proposed"] = [], []
        result["lost_workers"] = ["discover:skills-review", "refute-fit:skills-debug:followup", "stray-label"]
        write_json(self.result, result)
        self.assertEqual(self.write("--force").returncode, 0)
        text = self.record.read_text(encoding="utf-8")
        context, _, decision, _, _ = re.split(r"^## .*$", text, flags=re.M)[1:]
        self.assertIn("- `discover:skills-review`", context)
        self.assertIn("Of these, `stray-label` name no layer of this record.", context)
        review = decision.split("### `skills-review`")[1]
        self.assertIn("No proposal survived, and the layer lost workers (`discover:skills-review`): its result is "
                      "incomplete, not a refutation", review)
        self.assertNotIn("refuted all", review)
        debug = decision.split("### `skills-debug`")[1].split("###")[0]
        self.assertIn(A1, debug)
        self.assertIn("The layer also lost workers (`refute-fit:skills-debug:followup`)", debug)
        # A layer with no proposal and no lost worker says so, rather than "No proposal survived".
        del result["lost_workers"]
        write_json(self.result, result)
        self.assertEqual(self.write("--force").returncode, 0)
        context, _, decision, _, _ = re.split(r"^## .*$", self.record.read_text(encoding="utf-8"), flags=re.M)[1:]
        self.assertIn("- No proposal was made.", decision.split("### `skills-review`")[1])
        self.assertIn("Lost workers (they never returned, so their layers' results are incomplete, not refutations):"
                      "\n\n- None.", context)

    def test_refusals(self):
        self.assertEqual(self.write().returncode, 0)
        done = self.write()
        self.assertEqual(done.returncode, 2)
        self.assertIn("exists", done.stderr)
        self.assertEqual(self.write("--force").returncode, 0)
        result = json.loads(self.result.read_text())
        result["layers"][0]["catalog"] = "foundation"
        write_json(self.result, result)
        done = self.write("--force")
        self.assertEqual(done.returncode, 2)
        self.assertIn("skills", done.stderr)


# --------------------------------------------------------------------------- a skills RESULT.json and its reviews


# A source review of A1 at its adjudicated pin (skill_proposal: pin a*40, skill_md_sha256 b*64).
A1_REVIEW = {"schema_version": 1, "repository": A1, "layers": ["skills-debug"], "reviewed_commit": "a" * 40,
             "observed": {"adjudicated_pin": "a" * 40, "pin_lookup": "ok", "skill_md_sha256": "b" * 64,
                          "skill_folder_tree_sha": "d" * 40}}
A1_WRITTEN = [{"repository": A1, "path": "acme-agent-skills-debug-kit.json", "layers": ["skills-debug"]}]


def skills_result_checkout(case, res=None):
    """A checkout holding a skills sweep's retained returns, usage record and manifest (skills_sweep_result), and
    convert.py's output: what make_result.py reads."""
    root = temp_dir(case)
    (root / "catalogs/landscape").mkdir(parents=True)
    shutil.copy(CATALOG, root / "catalogs/landscape/skills-lifecycle.json")
    res = res or skills_sweep_result()
    scope = {"platform_profiles_sha256": PLAT,
             "requirement_sha256": {"skills/skills-debug": REQ, "skills/skills-review": REQ}}
    out = convert.convert(res, scope, LANE, convert.resolved_models(None))
    base = f"evidence/artifacts/{LANE}"
    write_json(root / base / "returns.json", out["returns"])
    labels = [f"{role}:{layer}" for layer in ("skills-debug", "skills-review") for role in
              ("discover", "gpt6-discover", "refute-facts", "refute-fit", "gpt6-refute-fit")] + ["critic"]
    usage = usage_record.record(harness_tests.child_usage_raw("wf_fixture-1", labels), 0, "cmd", ROOT)
    write_json(root / f"{base}-attempts/child-usage-wf_fixture-1.json", usage)
    manifest = {"checked_at": "2026-09-30", "critic": res["critic"]}
    write_json(root / "catalogs/sota-convergence/manifest-20260930.json", manifest)
    return root, base, out, usage, manifest


class SkillResultPinTests(unittest.TestCase):
    """make_result.py completes a skills RESULT.json only when each survivor's source review was written at the
    survivor's adjudicated pin, over the SKILL.md bytes the refuters judged, with the skill folder's tree hash; a
    stopped review stops its layer (GPT-6 review of #541)."""

    def make(self, reviews, review=A1_REVIEW, res=None):
        root, base, out, _, _ = skills_result_checkout(self, res)
        if review is not None:
            write_json(root / base / "acme-agent-skills-debug-kit.json", review)
        layers = write_json(root / "out/layers.json", out["layers"])
        listing = write_json(root / "out/reviews.json", reviews)
        done = run([sys.executable, HARNESS / "make_result.py", "--layers", layers, "--reviews", listing,
                    "--sweep-id", LANE, "--returns-ref", f"{base}/returns.json",
                    "--usage-ref", f"{base}-attempts/child-usage-wf_fixture-1.json",
                    "--manifest-ref", "catalogs/sota-convergence/manifest-20260930.json", "--prompts-sha256", "c" * 64,
                    "--repo-root", root])
        return done, base

    def test_a_review_at_the_adjudicated_pin_completes_the_record(self):
        done, base = self.make(A1_WRITTEN)
        self.assertEqual(done.returncode, 0, done.stderr)
        layer = json.loads(done.stdout)["layers"][0]
        self.assertEqual((layer["layer_id"], layer["survived"][0]["source_review"]),
                         ("skills-debug", f"{base}/acme-agent-skills-debug-kit.json"))

    def test_a_review_at_another_commit_or_of_other_bytes_is_refused(self):
        observed = A1_REVIEW["observed"]
        for change, message in (({"reviewed_commit": "e" * 40}, f"not the adjudicated pin {'a' * 40}"),
                                ({"observed": dict(observed, skill_md_sha256="f" * 64)}, "skill_md_sha256"),
                                ({"observed": dict(observed, skill_folder_tree_sha=None)}, "skill_folder_tree_sha"),
                                ({"observed": dict(observed, pin_lookup="failed")}, "pin_lookup")):
            with self.subTest(message):
                done, _ = self.make(A1_WRITTEN, dict(A1_REVIEW, **change))
                self.assertEqual(done.returncode, 2, done.stdout)
                self.assertIn(message, done.stderr)

    def test_a_stopped_review_stops_its_layer(self):
        stopped = [{"repository": A1, "layers": ["skills-debug"], "status": "stopped", "pin": "a" * 40,
                    "pin_lookup": "failed", "reason": "the adjudicated pin is unreadable (gh: Not Found)"}]
        done, _ = self.make(stopped, review=None)
        self.assertEqual(done.returncode, 2, done.stdout)
        for phrase in ("stopped", "skills-debug", "the adjudicated pin is unreadable (gh: Not Found)", "status stopped"):
            self.assertIn(phrase, done.stderr)

    def test_the_pin_check_cannot_be_skipped(self):
        # build_result without the review loader refuses a skills survivor rather than leaving its pin unchecked.
        _, base, out, usage, manifest = skills_result_checkout(self)
        with self.assertRaisesRegex(ValueError, "the review file are needed"):
            make_result.build_result(
                layers=out["layers"], reviews=A1_WRITTEN, usage=usage, manifest=manifest, sweep_id=LANE, lane=LANE,
                returns_ref=f"{base}/returns.json", usage_ref=f"{base}-attempts/child-usage-wf_fixture-1.json",
                manifest_ref="catalogs/sota-convergence/manifest-20260930.json", prompts_sha256="c" * 64,
                returns=out["returns"])

    def test_a_survivor_with_a_null_hash_is_refused(self):
        res = skills_sweep_result()
        debug = res["first"][0]
        for proposal in [*debug["claude_discover"]["proposed"], *debug["gpt6_discover"]["output"]["proposed"],
                         *debug["merged"]]:
            proposal["skill_md_sha256"] = None
        done, _ = self.make(A1_WRITTEN, res=res)
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("skill_md_sha256 is null", done.stderr)


# --------------------------------------------------------------------------- the documents describe what is delivered


class SkillsDocsTests(unittest.TestCase):
    DOCS = (HARNESS / "README.md", ROOT / "docs" / "decisions" / "2026-09-30-skills-sweep-modality.md")

    def test_the_docs_describe_the_delivered_ledger_schema_and_the_pinned_reviews(self):
        schema = json.loads((ROOT / "catalogs/saturation/ledger.schema.json").read_text(encoding="utf-8"))
        self.assertIn("skills", schema["$defs"]["layer"]["properties"]["catalog"]["enum"])
        for path in self.DOCS:
            with self.subTest(path.name):
                text = re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
                # GPT-6 review of #541: both said the schema still lacked skills and needed a future edit.
                self.assertNotIn("still lists only the foundation and us-equities catalogs", text)
                self.assertNotIn("lists only `foundation` and `us-equities`", text)
                self.assertIn("`catalogs/saturation/ledger.schema.json` lists `skills`", text)
                # No default-branch fallback remains to describe.
                self.assertNotIn("falls back to the default branch", text)
                self.assertNotIn("pin_fallback", text)

    def test_the_docs_describe_the_reader_and_what_it_leaves_unverified(self):
        # Opus round-3 review of #541, finding 1: both documents said the readers never guess while both still did.
        for path in self.DOCS:
            with self.subTest(path.name):
                text = re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
                for claim in ("Neither reader guesses", "subset reader covers", "none was found"):
                    self.assertNotIn(claim, text)
                for phrase in ("skill_md.mjs", "skills-yaml.pin.json", "2.9.1", "a line break other than LF",
                               "U+2028", "symlink", "evidence/artifacts/skills-md-reader-20260930/README.md"):
                    self.assertIn(phrase, text)

    def test_the_docs_say_the_cli_walks_a_symlinked_location(self):
        # Opus round-4 review of #541, D1: both documents said a symlinked folder is not followed while the clone would
        # walk it; the CLI walks a symlinked search location (readdir follows it) and skips a symlinked skill folder.
        for path in self.DOCS:
            with self.subTest(path.name):
                text = re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
                self.assertNotIn("A symlinked folder is not followed", text)
                for phrase in ("walks a search location through a symlink", "skips a symlinked skill folder",
                               ".gitattributes"):
                    self.assertIn(phrase, text)


# --------------------------------------------------------------------------- CI provisioning of the yaml pin
#
# The tests that run skill_md.mjs skip without a verified yaml install, so a CI job that never installed the pin would
# pass while exercising only the fail-closed gate. validate.yml installs the pin before the suite, as it does the
# tree-sitter-bash pin, and these tests hold it there with the pattern of tests/test_shell_parser_ci.py: a runtime
# tripwire that fails an Actions job without the verified install (outside the recorded gaps), structure checks on the
# provisioning step, a ratchet over the jobs that run the whole suite, and mutation controls for each.

YAML_PIN_REL = "tools/sota-convergence/landscape-sweep/skills-yaml.pin.json"
YAML_WORKFLOW, YAML_JOB = "validate.yml", "validate"
YAML_KEY = f"{YAML_WORKFLOW}:{YAML_JOB}"
# The remaining serial suite without the YAML pin is catalog-freshness.yml:freshness.
# Its reader tests and tripwire report this recorded gap; add provisioning and
# delete the entry together. The ratchet rejects stale exemptions.
YAML_KNOWN_UNPROVISIONED = {"catalog-freshness.yml:freshness"}
YAML_TRIPWIRE = "tests.test_landscape_sweep_skills.SkillsYamlInstalledInCI"


def yaml_stand_down(env):
    """None when skill_md.mjs must report the pinned install in a process with `env`; otherwise why the tripwire does
    not apply: outside GitHub Actions, or in a job recorded in YAML_KNOWN_UNPROVISIONED. Anything else fails closed."""
    if env.get("GITHUB_ACTIONS") != "true":
        return "not in GitHub Actions (GITHUB_ACTIONS is not 'true')"
    if shell_ci.job_key(env) in YAML_KNOWN_UNPROVISIONED:
        return "a recorded gap: this job runs the whole suite without installing the yaml pin (YAML_KNOWN_UNPROVISIONED)"
    return None


def reader_status(env):
    """What skill_md.mjs reports about its yaml install in a node process with `env` (no --install: the environment
    variable, then the default under HOME): its reader record, which carries no path, or node_missing / probe_failed."""
    node = shutil.which("node", path=env.get("PATH"))
    if node is None:
        return {"ok": False, "reason": "node_missing"}
    try:
        done = subprocess.run([node, str(SKILL_MD_MJS)], input='{"items": []}', env=env, capture_output=True,
                              text=True, timeout=120, check=False)
        record = json.loads(done.stdout)["reader"]
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError):
        return {"ok": False, "reason": "probe_failed"}
    return record if isinstance(record, dict) else {"ok": False, "reason": "probe_failed"}


def reader_verified(status):
    """True when the reader reports the pinned package, its integrity and this pin file's sha256."""
    pin = json.loads(YAML_PIN_PATH.read_text(encoding="utf-8"))
    expected = {"package": f"{pin['package']['name']}@{pin['package']['version']}",
                "integrity": pin["package"]["integrity"], "pin_sha256": hashlib.sha256(YAML_PIN_PATH.read_bytes()).hexdigest()}
    return status.get("ok") is True and all(status.get(key) == value for key, value in expected.items())


def reader_describe(status):
    """A path-free reason for a status that is not the verified record."""
    if status.get("ok") is True:
        return "the reader's record differs from the pin"
    reason = status.get("reason")
    return f"reason={reason}" if isinstance(reason, str) and reason.isidentifier() else "reason=unrecognized"


def yaml_ci_env(home, drop=(), **extra):
    """The validate job's environment as far as the tripwire reads it, over a clean host: no inherited GITHUB_ or
    LANDSCAPE_SWEEP_SKILLS_YAML variable, and HOME an empty directory, so that no host install is found by default."""
    env = {key: value for key, value in os.environ.items() if not key.startswith(("GITHUB_", YAML_ENV))}
    env.update({"GITHUB_ACTIONS": "true", "GITHUB_JOB": YAML_JOB, "HOME": str(home),
                "GITHUB_WORKFLOW_REF": f"owner/repo/.github/workflows/{YAML_WORKFLOW}@refs/pull/1/merge"})
    env.update(extra)
    for key in drop:
        env.pop(key, None)
    return env


class SkillsYamlInstalledInCI(unittest.TestCase):
    """The runtime tripwire. It skips outside GitHub Actions and in the recorded gaps, and fails everywhere else."""

    def test_a_github_actions_job_has_the_verified_yaml_install(self):
        reason = yaml_stand_down(os.environ)
        if reason is not None:
            self.skipTest(reason)
        status = reader_status(dict(os.environ))
        if not reader_verified(status):
            self.fail(f"this GitHub Actions job has no verified yaml install for skill_md.mjs ({reader_describe(status)}): "
                      "the reader tests would skip; a step that installs skills-yaml.pin.json must run before the suite, "
                      "as validate.yml's does, or the job must be a recorded gap")


class SkillsYamlTripwireControls(unittest.TestCase):
    """The tripwire run in each environment a job can present, over a clean host: it must fail on each way the install
    can be missing or wrong, skip only outside Actions and in the recorded gaps, and pass on the verified install."""

    BARE = ("GITHUB_JOB", "GITHUB_WORKFLOW_REF")  # GITHUB_ACTIONS=true and nothing else that names a job

    def run_tripwire(self, home, drop=(), **extra):
        return subprocess.run([sys.executable, "-m", "unittest", "-v", YAML_TRIPWIRE], cwd=ROOT, capture_output=True,
                              text=True, timeout=300, check=False, env=yaml_ci_env(home, drop, **extra))

    def assert_failed(self, done, reason):
        self.assertEqual(done.returncode, 1, f"the tripwire did not fail (exit {done.returncode})")
        self.assertIn("FAILED (failures=1)", done.stderr)
        self.assertIn(f"reason={reason}", done.stderr)
        self.assertNotIn("skipped", done.stderr)

    def assert_skipped(self, done, why):
        self.assertEqual(done.returncode, 0, f"the tripwire run exited {done.returncode}, not 0")
        self.assertIn("skipped", done.stderr)
        self.assertIn(why, done.stderr)

    @unittest.skipUnless(NODE, "node is not installed")
    def test_no_install_or_a_nonexistent_directory_fails_the_tripwire(self):
        for label, drop, extra in (("no install anywhere", (), {}), ("a nonexistent directory", (), {"absent": True}),
                                   ("Actions alone, no install", self.BARE, {})):
            with self.subTest(label), tempfile.TemporaryDirectory() as home:
                named = {YAML_ENV: str(Path(home) / "absent")} if extra else {}
                self.assert_failed(self.run_tripwire(home, drop, **named), "not_installed")

    @unittest.skipUnless(SKILLS_YAML, NO_READER)
    def test_a_one_byte_change_fails_the_tripwire_and_the_verified_install_passes(self):
        with tempfile.TemporaryDirectory() as home:
            copy = Path(home) / "copy"
            shutil.copytree(SKILLS_YAML, copy, symlinks=True)
            passed = self.run_tripwire(home, **{YAML_ENV: str(copy)})
            self.assertEqual(passed.returncode, 0, "the unchanged copy must pass, or the change proves nothing")
            self.assertIn("OK", passed.stderr)
            self.assertNotIn("skipped", passed.stderr)
            composer = copy / "node_modules/yaml/dist/compose/composer.js"
            data = bytearray(composer.read_bytes())
            data[len(data) >> 1] ^= 1  # one bit of the middle byte: the same length, so only the hash can tell
            composer.write_bytes(bytes(data))
            self.assert_failed(self.run_tripwire(home, **{YAML_ENV: str(copy)}), "hash_mismatch")

    @unittest.skipUnless(NODE, "node is not installed")
    def test_an_unlisted_job_fails_and_a_recorded_gap_skips(self):
        unlisted = {"another job of the validate workflow": {"GITHUB_JOB": "another-job"},
                    "the validate job's name in another workflow": {
                        "GITHUB_WORKFLOW_REF": "owner/repo/.github/workflows/other.yml@refs/heads/main"},
                    "a gap's job name in the validate workflow": {"GITHUB_JOB": "freshness"}}
        for label, extra in unlisted.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as home:
                self.assert_failed(self.run_tripwire(home, **extra), "not_installed")
        for key in sorted(YAML_KNOWN_UNPROVISIONED):
            workflow, _, job = key.partition(":")
            extra = {"GITHUB_JOB": job, "GITHUB_WORKFLOW_REF": f"owner/repo/.github/workflows/{workflow}@refs/heads/main"}
            with self.subTest(key), tempfile.TemporaryDirectory() as home:
                self.assert_skipped(self.run_tripwire(home, **extra), "a recorded gap")

    def test_runs_outside_actions_skip_with_a_message(self):
        with tempfile.TemporaryDirectory() as home:
            self.assert_skipped(self.run_tripwire(home, ("GITHUB_ACTIONS",)), "not in GitHub Actions")


def yaml_provisioning_indexes(steps):
    return [index for index, step in enumerate(steps) if YAML_PIN_REL in shell_ci.uncommented(step)]


def yaml_provisioning_problems(text, job_id=YAML_JOB):
    """(category, message) for each way the yaml provisioning of job `job_id` in the workflow `text` departs from what
    these tests require (the categories of tests/test_shell_parser_ci.py). With no single provisioning step to inspect,
    every category is reported."""
    job = shell_ci.jobs(text).get(job_id)
    steps = shell_ci.step_blocks(job) if job is not None else []
    found = yaml_provisioning_indexes(steps)
    if len(found) != 1:
        reason = "no such job" if job is None else f"expected one step that reads the pin file, found {len(found)}"
        return [(category, reason) for category in shell_ci.CATEGORIES]
    step = shell_ci.uncommented(steps[found[0]])
    problems = []
    suite = [index for index, other in enumerate(steps) if shell_ci.runs_suite(other)]
    if not suite:
        problems.append(("order", "no step runs the whole suite or a module shard"))
    elif found[0] >= suite[0]:
        problems.append(("order", "the provisioning step does not precede the suite/shard step"))
    for key in ("install", "command", "default_directory"):
        if not shell_ci.mentions(step, key):
            problems.append(("derived", f"the step does not read {key} from the pin"))
    package = json.loads(YAML_PIN_PATH.read_text(encoding="utf-8"))["package"]
    retyped = [f"{package['name']}@{package['version']}", package["version"], "--ignore-scripts", "--save-exact"]
    problems += [("derived", "the step retypes part of the pinned command") for token in retyped if token in step][:1]
    if YAML_ENV not in step or "GITHUB_ENV" not in step:
        problems.append(("export", f"the step does not write {YAML_ENV} to the GITHUB_ENV file"))
    if "continue-on-error" in step:
        problems.append(("enforced", "the step continues on error"))
    if any(line.startswith(("        if:", "      - if:")) for line in step.splitlines()):
        problems.append(("enforced", "the step has a condition, so some events would skip the install"))
    if "${{" in step:
        problems.append(("enforced", "the step expands an expression inside its script"))
    return problems


def yaml_ratchet_problems(texts, gaps=YAML_KNOWN_UNPROVISIONED):
    """'unlisted': a suite/shard job lacks the yaml provisioning step and is not a recorded gap; 'stale': a recorded gap
    provisions, no longer runs the suite or is gone; 'required': validate.yml's job does not provision, or is a gap."""
    found = shell_ci.suite_jobs(texts)
    installing = {key for key, job_text in found.items() if yaml_provisioning_indexes(shell_ci.step_blocks(job_text))}
    without = set(found) - installing
    problems = [("unlisted", f"{key} runs project tests without installing the yaml pin and is not a recorded gap")
                for key in sorted(without - gaps)]
    problems += [("stale", f"{key} is a recorded gap but does not run project tests without the yaml pin")
                 for key in sorted(gaps - without)]
    if YAML_KEY not in installing or YAML_KEY in gaps:
        problems.append(("required", f"{YAML_KEY} must run project tests with the provisioning step and cannot be a gap"))
    return problems


def yaml_provisioning_span(lines):
    index = next((i for i, line in enumerate(lines) if YAML_PIN_REL in line and not line.lstrip().startswith("#")), None)
    if index is None:
        raise AssertionError("no step of the workflow reads the yaml pin file: there is no provisioning step to inspect")
    return shell_ci.step_span(lines, index)


class SkillsYamlProvisioningTests(unittest.TestCase):
    """validate.yml installs the yaml pin before the suite, derived from the pin, exported, and not skippable; every
    other whole-suite job does so too or is a recorded gap."""

    texts = shell_ci.workflow_texts()

    def test_the_validate_job_provisions_the_yaml_pin_before_the_suite(self):
        self.assertEqual(yaml_provisioning_problems(self.texts[YAML_WORKFLOW]), [])

    def test_every_whole_suite_job_provisions_the_yaml_pin_or_is_a_recorded_gap(self):
        self.assertEqual(yaml_ratchet_problems(self.texts), [])

    def test_a_native_module_shard_requires_the_yaml_pin_too(self):
        # Kind-3 suite/shard binding: docs/decisions/2026-10-07-validate-module-shards.md.
        bare = {**self.texts, "new.yml": shell_ci.synthetic_workflow(build=shell_ci.SHARD_STEP)}
        self.assertEqual([category for category, _ in yaml_ratchet_problems(bare)], ["unlisted"])
        pin_step = f"      - name: Install the yaml pin\n        run: cat {YAML_PIN_REL}\n"
        bare["new.yml"] = shell_ci.synthetic_workflow(build=pin_step + shell_ci.SHARD_STEP)
        self.assertEqual(yaml_ratchet_problems(bare), [])


class SkillsYamlProvisioningControls(unittest.TestCase):
    """Each mutant is the real workflow with one defect and must be reported in its category; the ratchet reports a new
    whole-suite job and a recorded gap that now provisions."""

    texts = shell_ci.workflow_texts()
    text = texts[YAML_WORKFLOW]

    def mutants(self):
        lines = self.text.split("\n")
        start, end = yaml_provisioning_span(lines)
        step = lines[start:end]
        run_index = next(i for i, line in enumerate(step) if line.startswith("        run: |"))
        suite_end = shell_ci.suite_step_span(lines)[1]
        return {
            "removed step": ("missing", "\n".join(lines[:start] + lines[end:])),
            "step after the suite": ("order", "\n".join(lines[:start] + lines[end:suite_end] + step + lines[suite_end:])),
            "command retyped": ("derived", "\n".join(lines[:start + run_index + 1] + ['          echo "yaml@2.9.0"']
                                                    + lines[start + run_index + 1:])),
            "export dropped": ("export", "\n".join(lines[:start] + [line.replace(YAML_ENV, "SKILLS_YAML_DIR") for line in step]
                                                  + lines[end:])),
            "continues on error": ("enforced", "\n".join(lines[:start + 1] + ["        continue-on-error: true"] + lines[start + 1:])),
            "conditional": ("enforced", "\n".join(lines[:start + 1] + ["        if: github.event_name == 'push'"] + lines[start + 1:])),
            "expression in the script": ("enforced", "\n".join(lines[:start + run_index + 1] + ["          echo ${{ github.sha }}"]
                                                              + lines[start + run_index + 1:])),
        }

    def test_each_mutant_is_reported_in_its_category(self):
        self.assertEqual(yaml_provisioning_problems(self.text), [])
        for label, (category, mutant) in self.mutants().items():
            with self.subTest(label):
                self.assertNotEqual(mutant, self.text, "the mutation must apply")
                self.assertIn(category, {found for found, _ in yaml_provisioning_problems(mutant)})

    def test_the_ratchet_reports_a_new_whole_suite_job_and_a_gap_that_now_provisions(self):
        gap_files = {key.partition(":")[0] for key in YAML_KNOWN_UNPROVISIONED}
        name = next(file for file in sorted(self.texts) if file != YAML_WORKFLOW and file not in gap_files)
        added = self.texts[name].rstrip("\n") + "\n\n  extra-suite:\n    runs-on: ubuntu-24.04\n    steps:\n" + shell_ci.SUITE_STEP
        self.assertEqual([category for category, _ in yaml_ratchet_problems({**self.texts, name: added})], ["unlisted"])
        lines = self.text.split("\n")
        start, end = yaml_provisioning_span(lines)
        for key in sorted(YAML_KNOWN_UNPROVISIONED):
            workflow, _, job = key.partition(":")
            with self.subTest(key):
                mutant = {**self.texts, workflow: shell_ci.with_step(self.texts[workflow], job, lines[start:end])}
                self.assertEqual([category for category, _ in yaml_ratchet_problems(mutant)], ["stale"])
                self.assertEqual(yaml_ratchet_problems(mutant, YAML_KNOWN_UNPROVISIONED - {key}), [])
                self.assertEqual(yaml_provisioning_problems(mutant[workflow], job), [])
        bare = {**self.texts, YAML_WORKFLOW: "\n".join(lines[:start] + lines[end:])}
        self.assertIn("required", [category for category, _ in yaml_ratchet_problems(bare)])


@unittest.skipUnless(shutil.which("bash"), "the step runs under bash, as on the runner")
class SkillsYamlProvisioningStepRuns(unittest.TestCase):
    """Runs the step's script as the runner does (bash -e over the script file) in a scratch workspace, with a stand-in
    npm that records its arguments, so nothing is installed and nothing leaves the machine."""

    PRIOR = "CHILD_USAGE_SHELL_PARSER=stub\n"  # the steps before this one append to the same file

    def run_step(self, pin=None, npm_exit=0):
        lines = (ROOT / ".github/workflows" / YAML_WORKFLOW).read_text(encoding="utf-8").split("\n")
        start, end = yaml_provisioning_span(lines)
        script = shell_ci.run_script("\n".join(lines[start:end]))
        pin = pin if pin is not None else json.loads(YAML_PIN_PATH.read_text(encoding="utf-8"))
        scratch = temp_dir(self)
        workspace, runner_temp, stub = scratch / "workspace", scratch / "runner-temp", scratch / "bin"
        (workspace / YAML_PIN_REL).parent.mkdir(parents=True)
        (workspace / YAML_PIN_REL).write_text(json.dumps(pin), encoding="utf-8")
        runner_temp.mkdir()
        stub.mkdir()
        (stub / "npm").write_text('#!/bin/sh\nprintf \'%s\\n\' "$@" > "$NPM_ARGV_FILE"\nexit "$NPM_EXIT"\n', encoding="utf-8")
        (stub / "npm").chmod(0o755)
        (scratch / "github-env").write_text(self.PRIOR, encoding="utf-8")
        (scratch / "step.sh").write_text(script, encoding="utf-8")
        env = {"PATH": f"{stub}{os.pathsep}{os.environ['PATH']}", "HOME": str(scratch), "RUNNER_TEMP": str(runner_temp),
               "GITHUB_ENV": str(scratch / "github-env"), "NPM_ARGV_FILE": str(scratch / "argv"), "NPM_EXIT": str(npm_exit)}
        done = subprocess.run(["bash", "--noprofile", "--norc", "-e", str(scratch / "step.sh")], cwd=workspace, env=env,
                              capture_output=True, text=True, timeout=60, check=False)
        argv = (scratch / "argv").read_text(encoding="utf-8").splitlines() if (scratch / "argv").exists() else None
        directory = os.path.join(str(runner_temp), os.path.basename(pin["install"]["default_directory"]))
        return done.returncode, argv, (scratch / "github-env").read_text(encoding="utf-8"), directory

    def test_it_runs_the_pin_command_into_runner_temp_and_exports_the_directory(self):
        words = shlex.split(json.loads(YAML_PIN_PATH.read_text(encoding="utf-8"))["install"]["command"])
        code, argv, exported, directory = self.run_step()
        self.assertEqual(code, 0)
        self.assertEqual(argv, [directory if word == "<directory>" else word for word in words[1:]])
        self.assertTrue(os.path.isdir(directory), "the step creates the directory under RUNNER_TEMP before npm runs")
        self.assertEqual(exported, self.PRIOR + f"{YAML_ENV}={directory}\n")

    def test_it_refuses_a_bad_command_or_directory_and_a_failing_npm_exports_nothing(self):
        base = json.loads(YAML_PIN_PATH.read_text(encoding="utf-8"))
        bad = {"no placeholder": ("command", "npm install --ignore-scripts yaml@2.9.0"),
               "not an npm install": ("command", "true --prefix <directory>"),
               "a newline in the directory": ("default_directory", "tools/x\nNODE_OPTIONS=--require=evil"),
               "a leading dot": ("default_directory", "tools/.hidden")}
        for label, (key, value) in bad.items():
            with self.subTest(label):
                pin = copy.deepcopy(base)
                pin["install"][key] = value
                code, argv, exported, _ = self.run_step(pin)
                self.assertNotEqual(code, 0)
                self.assertIsNone(argv, "npm must not run")
                self.assertEqual(exported, self.PRIOR)
        code, _, exported, _ = self.run_step(npm_exit=1)
        self.assertNotEqual(code, 0)
        self.assertEqual(exported, self.PRIOR)


if __name__ == "__main__":
    unittest.main()
