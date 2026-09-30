"""Synthetic-fixture tests for the landscape sweep's skills modality (tools/sota-convergence/landscape-sweep; no
network, no codex, no model calls).

Covered: the skills lifecycle catalog, the strict discover-skills return schema, skills layer inputs and their frozen
scope, each modality's own history and baseline, the templates a skills-* layer resolves to, a skills run staged by
build_args.py and run by sweep.js under node (skipped without node), agents/openai.yaml as Codex reads it and SKILL.md
frontmatter as the skills CLI's yaml package types it (each with the subset reader always, the PyYAML reader when
PyYAML is installed), source reviews of skill survivors against a fake gh whose
git trees carry the object ids git itself computes (git is required), make_result.py's pin checks of a skills
RESULT.json, and the decision record it writes. Schemas are validated with scripts/host_receipts.py's validator (the
repository's JSON Schema subset; CI installs no jsonschema), and with jsonschema as well when it is installed.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import host_receipts  # noqa: E402  (the repository's JSON Schema subset validator)
import saturation_ledger as sl  # noqa: E402
import tests.test_landscape_sweep_harness as harness_tests  # noqa: E402  (helpers only; its test classes run there)

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
        # Each installed skill's gap passes whole: security-audit's is over 1,000 characters.
        security = json.loads((work / "inputs/skills-security.json").read_text(encoding="utf-8"))
        pinned = {skill["name"]: skill["gap"] for skill in manifest["skills"]}
        gaps = {skill["name"]: skill["gap"] for skill in security["installed"]}
        self.assertEqual(gaps, {name: pinned[name] for name in gaps})
        self.assertGreater(len(gaps["security-audit"]), 1000)


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


def skill_md(name="find-bugs", description="Find bugs.", extra=()) -> bytes:
    """A SKILL.md with that name and description (None leaves the field out) and any extra frontmatter lines."""
    fields = [f"name: {name}"] * (name is not None) + [f"description: {description}"] * (description is not None)
    return ("---\n" + "".join(f"{line}\n" for line in [*fields, *extra]) + "---\n\nBody.\n").encode()


NO_DESCRIPTION, NO_NAME = skill_md(description=None), skill_md(name=None)


def git_out(case, directory, *args) -> str:
    done = run(["git", "-C", directory, *args], env={**os.environ, **GIT_ENV})
    case.assertEqual(done.returncode, 0, done.stderr)
    return done.stdout


def git_listing(case, files: dict, executable=()) -> dict:
    """The GitHub git-trees answer (?recursive=1) for a commit holding `files` ({path: bytes}), with the object ids
    upstream git computes: `git write-tree` gives the root tree's sha and `git ls-tree -r -t -l -z` every folder and
    blob, so the fixture never reimplements git's object format."""
    directory = temp_dir(case)
    git_out(case, directory, "init", "-q")
    for path, data in files.items():
        target = directory / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if path in executable:
            target.chmod(0o755)
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


def skill_frontmatter(lines: str) -> bytes:
    """A SKILL.md whose frontmatter is these lines, after a name line unless they give their own."""
    return (f"---\n{'' if lines.startswith('name:') else 'name: find-bugs' + chr(10)}{lines}\n---\n\nBody.\n").encode()


# SKILL.md frontmatters: name -> (lines, the subset reader's verdict, the PyYAML reader's verdict, a phrase of the
# subset reader's reason). "take" and "skip" are what vercel-labs/skills v1.7.0 parseSkillMd (src/skills.ts lines
# 80-133) decides with the yaml package 2.9.0 it parses the frontmatter with, checked by running both under node (the
# package whose sha512 integrity the CLI's pnpm-lock.yaml pins); None is unverified: syntax the reader does not parse,
# never a guess (GPT-6 round-3 review of #541: a list description read as a string let an invalid copy win).
SKILL_MD = {
    "a plain description": ("description: Find bugs.", "take", "take", None),
    "a list description": ("description:\n  - Find bugs.", "skip", "skip", "must be strings (got string and object)"),
    "a mapping description": ("description:\n  summary: Find bugs.", "skip", "skip", "(got string and object)"),
    "a mapping with a quoted key": ('description:\n  "summary": Find bugs.', "skip", "skip", "(got string and object)"),
    "a flow list description": ("description: [Find bugs.]", "skip", "skip", "(got string and object)"),
    "a number description": ("description: 1.5", "skip", "skip", "(got string and number)"),
    "a null description": ("description: ~", "skip", "skip", "missing required frontmatter field(s): description"),
    "a literal block": ("description: |\n  Find bugs.", "take", "take", None),
    "a folded block over lines": ("description: >-\n  Find bugs\n  in a change.", "take", "take", None),
    "a block without text": ("description: >-", "skip", "skip", "missing required frontmatter field(s): description"),
    "a plain scalar on the next lines": ("description:\n  Find bugs\n  in a change.", "take", "take", None),
    "a continuation starting with a quote": ('description: Use when asked to "scan",\n  "audit a skill", or more.',
                                             "take", "take", None),
    "YAML's escapes": ('description: "Tab\\there \\"q\\" \\x41\\u00e9"', "take", "take", None),
    "a quoted name with spaces": ('name: " find-bugs "\ndescription: Find bugs.', "take", "take", None),
    "nested metadata, a nested block scalar and a flow list": (
        "description: Find bugs.\nmetadata:\n  tags:\n    - a\n  notes: |\n    a: b: c\ntags: [a, b]", "take", "take",
        None),
    "an anchored description": ("description: &d Find bugs.", None, "take", "an anchor"),
    "a tagged description": ("description: !!str Find bugs.", None, None, "a tag"),
    "an invalid escape in another value": ('description: Find bugs.\nnote: "C:\\skills"', None, None, "escape \\s"),
    "a plain scalar holding ': '": ("description: Use when: asked.", None, None, "holding ': '"),
    "a key given twice": ("description: Find bugs.\ndescription: Again.", None, None, "appears twice"),
    "a nested key given twice": ("description: Find bugs.\nmetadata:\n  a: 1\n  a: 2", None, None, "appears twice"),
    "a block scalar with an indentation indicator": ("description: |2\n    Find bugs.", None, "take",
                                                     "block scalar header"),
    "a comment inside a plain scalar": ("description: Find bugs # c\n  in a change.", None, None, "a comment inside"),
}


class SkillMdReaderTests(unittest.TestCase):
    """source_reviews.skill_md_check: a SKILL.md's verdict and recorded name as the pinned skills CLI decides them, or
    SkillMdUnverified. The subset reader runs without PyYAML; the PyYAML reader with each of its two loaders."""

    def check(self, lines, expected, phrase, subset):
        try:
            problem, declared = source_reviews.skill_md_check(skill_frontmatter(lines))
        except source_reviews.SkillMdUnverified as why:
            self.assertIsNone(expected, str(why))
            self.assertIn(phrase if subset and phrase else "", str(why))
            return
        self.assertEqual("take" if problem is None else "skip", expected, problem)
        if problem is None:
            self.assertEqual(declared, "find-bugs")  # sanitizeMetadata: the quoted name's spaces are trimmed
        else:
            self.assertIsNone(declared)
            self.assertIn(phrase, problem)  # the CLI's own warning text, whichever reader typed the field

    def test_the_subset_reader_types_the_frontmatter_as_the_cli_does_or_says_it_cannot(self):
        with mock.patch.object(source_reviews, "yaml", None, create=True):
            for name, (lines, expected, _, phrase) in SKILL_MD.items():
                with self.subTest(name):
                    self.check(lines, expected, phrase, True)
            self.assertEqual(source_reviews.skill_md_check(b"# Find bugs\n"),
                             ("missing required frontmatter field(s): name, description", None))

    @unittest.skipUnless(PYYAML, "PyYAML is not installed; the subset reader's tests run without it")
    def test_the_pyyaml_reader_types_the_frontmatter_as_the_cli_does_or_says_it_cannot(self):
        for loader in ("default", "SafeLoader"):
            with mock.patch.object(source_reviews.yaml, "CSafeLoader", None, create=True) if loader == "SafeLoader" \
                    else mock.patch.object(source_reviews, "yaml", source_reviews.yaml):
                for name, (lines, _, expected, phrase) in SKILL_MD.items():
                    with self.subTest(name, loader=loader):
                        self.check(lines, expected, phrase, False)


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


class SkillSourceReviewTests(unittest.TestCase):
    """source_reviews.py on skill survivors against a fake gh whose git trees carry git's own object ids."""

    META = {"full_name": "O/Skills-Repo", "default_branch": "main", "license": {"spdx_id": "MIT"},
            "description": "skills", "stargazers_count": 7, "pushed_at": "2026-09-29T00:00:00Z", "archived": False}

    def review(self, answers, survivors):
        work, bin_dir = temp_dir(self), temp_dir(self)
        gh = bin_dir / "gh"
        gh.write_text(harness_tests.FAKE_GH.format(python=sys.executable, answers=repr(answers)), encoding="utf-8")
        gh.chmod(0o755)
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
        done = run([sys.executable, HARNESS / "source_reviews.py", "--survivors", write_json(work / "s.json", survivors),
                    "--out", work / "reviews", "--lane", LANE], env=env)
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

    def add_commit(self, answers, commit, files, truncated=False):
        contents = self.contents(files)
        answers[f"repos/O/Skills-Repo/git/trees/{commit}?recursive=1"] = dict(git_listing(self, contents),
                                                                              truncated=truncated)
        for path, raw in contents.items():
            answers[f"repos/O/Skills-Repo/contents/{path}?ref={commit}"] = {
                "path": path, "type": "file", "encoding": "base64", "content": base64.b64encode(raw).decode()}

    def answers(self, files, pin=PIN, truncated=False, head=None):
        """Fake gh answers for O/Skills-Repo: `files` at the adjudicated pin, whose commit lookup answers that pin (pin
        None: not answered, so gh exits 1); with `head`, the default branch at HEAD holding `head`."""
        answers = {"repos/o/skills-repo": dict(self.META)}
        if pin:
            answers[f"repos/O/Skills-Repo/commits/{pin}"] = {"sha": pin}
            self.add_commit(answers, pin, files, truncated)
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

    def test_a_copy_the_reader_cannot_type_stops_the_review_instead_of_deciding_the_order(self):
        tagged = skill_md(description="!!str Find bugs.")  # both readers leave tags unverified
        done, out = self.review(self.answers({"find-bugs/SKILL.md": tagged, "skills/find-bugs/SKILL.md": FIND_BUGS}),
                                [self.survivor()])
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertEqual(list(out.glob("*.json")), [])
        [entry] = json.loads(done.stdout)
        self.assertEqual((entry["status"], entry["pin_lookup"]), ("stopped", "ok"))
        for phrase in ("find-bugs/SKILL.md", "tag", "which copy it installs, is unverified"):
            self.assertIn(phrase, entry["reason"])
        # An anchored description is a string to the yaml package: PyYAML's composer follows the anchor and that copy
        # is the CLI's pick; the subset reader does not parse anchors, so it stops rather than pass the copy over.
        anchored = skill_md(description="&d Find bugs.")
        done, out = self.review(self.answers({"find-bugs/SKILL.md": anchored, "skills/find-bugs/SKILL.md": FIND_BUGS}),
                                [self.survivor(anchored)])
        if PYYAML:  # source_reviews.py runs under this interpreter
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(self.reviewed(out)["readme_path"], "find-bugs/SKILL.md")
        else:
            self.assertEqual(done.returncode, 1, done.stdout)
            [entry] = json.loads(done.stdout)
            self.assertEqual((entry["status"], entry["pin_lookup"]), ("stopped", "ok"))
            self.assertIn("an anchor", entry["reason"])

    def test_an_earlier_copy_gh_cannot_read_stops_the_review(self):
        # The CLI reads the blob from its clone; a failed API read says nothing about whether the CLI takes it.
        answers = self.answers({"find-bugs/SKILL.md": FIND_BUGS, "skills/find-bugs/SKILL.md": FIND_BUGS})
        del answers[f"repos/O/Skills-Repo/contents/find-bugs/SKILL.md?ref={PIN}"]
        done, out = self.review(answers, [self.survivor()])
        self.assertEqual(done.returncode, 1, done.stdout)
        [entry] = json.loads(done.stdout)
        self.assertEqual((entry["status"], entry["pin_lookup"]), ("stopped", "ok"))
        self.assertIn("find-bugs/SKILL.md could not be read here", entry["reason"])

    def test_the_name_is_matched_as_the_cli_records_it(self):
        spaced = skill_md(name='" find-bugs "')  # sanitizeMetadata trims it (src/sanitize.ts lines 61-65)
        done, out = self.review(self.answers({"skills/find-bugs/SKILL.md": spaced}), [self.survivor(spaced)])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.reviewed(out)["readme_path"], "skills/find-bugs/SKILL.md")

    def test_an_openai_yaml_with_an_escape_yaml_does_not_define_is_unverified(self):
        # GPT-6 round-3 review of #541: without PyYAML this was a definite codex_implicit false.
        files = {"skills/find-bugs/SKILL.md": FIND_BUGS,
                 "skills/find-bugs/agents/openai.yaml": b'note: "C:\\skills"\npolicy:\n  allow_implicit_invocation: false\n'}
        done, out = self.review(self.answers(files), [self.survivor()])
        self.assertEqual(done.returncode, 0, done.stderr)
        observed = self.reviewed(out)["observed"]
        self.assertIsNone(observed["codex_implicit"])
        self.assertIn("PyYAML cannot parse" if PYYAML else "the escape \\s", observed["unverified_reason"])

    # The adjudicated pin and the folder hash (GPT-6 review of #541: an unreadable pin fell back to the default
    # branch, a null hash let other bytes pass, and a SKILL.md hash did not freeze agents/openai.yaml).

    def test_an_unreadable_pin_gives_no_review_and_a_stopped_layer(self):
        # The pin's commit lookup is not answered (gh exits 1); the first round reviewed the default branch instead.
        answers = self.answers({}, pin=None, head={"skills/find-bugs/SKILL.md": FIND_BUGS})
        done, out = self.review(answers, [self.survivor()])
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertEqual(list(out.glob("*.json")), [])
        [entry] = json.loads(done.stdout)
        self.assertEqual({key: entry[key] for key in ("repository", "layers", "pin", "pin_lookup", "status")},
                         {"repository": "o/skills-repo@find-bugs", "layers": ["skills-debug"], "pin": PIN,
                          "pin_lookup": "failed", "status": "stopped"})
        self.assertIn(f"the adjudicated pin {PIN} is unreadable", entry["reason"])
        self.assertIn(f"gh api repos/O/Skills-Repo/commits/{PIN}", entry["reason"])
        self.assertIn(entry["reason"], done.stderr)

    def test_a_pin_that_resolves_to_another_commit_is_refused(self):
        answers = self.answers({"skills/find-bugs/SKILL.md": FIND_BUGS}, head={"skills/find-bugs/SKILL.md": FIND_BUGS})
        answers[f"repos/O/Skills-Repo/commits/{PIN}"] = {"sha": HEAD}
        done, out = self.review(answers, [self.survivor()])
        self.assertEqual(done.returncode, 1, done.stdout)
        [entry] = json.loads(done.stdout)
        self.assertEqual((entry["pin_lookup"], entry["status"]), ("failed", "stopped"))
        self.assertIn(f"not the adjudicated pin {PIN}", entry["reason"])

    def test_a_survivor_without_a_pin_or_with_a_null_hash_is_not_reviewed(self):
        files = {"skills/find-bugs/SKILL.md": FIND_BUGS}
        for survivor, lookup, message in ((dict(self.survivor(), pin=None), "failed", "names no adjudicated pin"),
                                          (dict(self.survivor(), pin="c0ffee"), "failed", "not a 40-hex commit"),
                                          (dict(self.survivor(), skill_md_sha256=None), None,
                                           "skill_md_sha256 is null")):
            with self.subTest(message):
                done, out = self.review(self.answers(files, head=files), [survivor])
                self.assertEqual(done.returncode, 1, done.stdout)
                self.assertEqual(list(out.glob("*.json")), [])
                [entry] = json.loads(done.stdout)
                self.assertEqual((entry["status"], entry["pin_lookup"]), ("stopped", lookup))
                self.assertIn(message, entry["reason"])

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


if __name__ == "__main__":
    unittest.main()
