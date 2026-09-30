"""Synthetic-fixture tests for the landscape sweep's skills modality (tools/sota-convergence/landscape-sweep; no
network, no codex, no model calls).

Covered: the skills lifecycle catalog, the strict discover-skills return schema, skills layer inputs and their frozen
scope, the templates a skills-* layer resolves to, a skills run staged by build_args.py and run by sweep.js under node
(skipped without node), source reviews of skill survivors against a fake gh, and the decision record make_result.py
writes from a skills sweep's RESULT.json. Schemas are validated with scripts/host_receipts.py's validator (the
repository's JSON Schema subset; CI installs no jsonschema), and with jsonschema as well when it is installed.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import re
import shutil
import sys
import unittest
from pathlib import Path

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
                       "disable-model-invocation: true", "allow_implicit_invocation: false",
                       "skill-creator's paired with-skill/without-skill benchmark", "promptfoo", "skill_ref"):
            self.assertIn(phrase, discover, phrase)
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
        self.assertEqual(converted["survivors"], [{"layer_id": "skills-debug", "repository": A1}])
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


class SkillSourceReviewTests(unittest.TestCase):
    COMMIT = "a" * 40

    def review(self, answers, survivors):
        work, bin_dir = temp_dir(self), temp_dir(self)
        gh = bin_dir / "gh"
        gh.write_text(harness_tests.FAKE_GH.format(python=sys.executable, answers=repr(answers)), encoding="utf-8")
        gh.chmod(0o755)
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
        done = run([sys.executable, HARNESS / "source_reviews.py", "--survivors", write_json(work / "s.json", survivors),
                    "--out", work / "reviews", "--lane", LANE], env=env)
        return done, work / "reviews"

    def answers(self, tree, files):
        commit = self.COMMIT
        answers = {"repos/o/skills-repo": {"full_name": "O/Skills-Repo", "default_branch": "main",
                                           "license": {"spdx_id": "MIT"}, "description": "skills",
                                           "stargazers_count": 7, "pushed_at": "2026-09-29T00:00:00Z",
                                           "archived": False},
                   "repos/O/Skills-Repo/commits/main": {"sha": commit},
                   f"repos/O/Skills-Repo/git/trees/{commit}?recursive=1": {
                       "truncated": False, "tree": [{"path": path, "type": "blob"} for path in tree]}}
        for path, raw in files.items():
            answers[f"repos/O/Skills-Repo/contents/{path}?ref={commit}"] = {
                "path": path, "type": "file", "encoding": "base64", "content": base64.b64encode(raw).decode()}
        return answers

    def test_a_skill_survivor_is_reviewed_at_its_skill_md(self):
        skill_md = ("---\nname: find-bugs\ndescription: Find bugs in a change.\ndisable-model-invocation: true\n---\n\n"
                    "# Find bugs\n\n" + "A long enough paragraph about how the skill hunts bugs in a change. " * 3
                    ).encode()
        openai_yaml = b"interface:\n  display_name: Find bugs\npolicy:\n  allow_implicit_invocation: false\n"
        answers = self.answers(["skills/find-bugs/SKILL.md", "skills/find-bugs/agents/openai.yaml",
                                "skills/other/SKILL.md"],
                               {"skills/find-bugs/SKILL.md": skill_md,
                                "skills/find-bugs/agents/openai.yaml": openai_yaml})
        done, out = self.review(answers, [{"layer_id": "skills-review", "repository": "o/skills-repo@find-bugs"},
                                          {"layer_id": "skills-debug", "repository": "O/Skills-Repo@find-bugs"}])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), [{"repository": "O/Skills-Repo@find-bugs",
                                                    "path": "o-skills-repo-find-bugs.json",
                                                    "layers": ["skills-debug", "skills-review"]}])
        review = json.loads((out / "o-skills-repo-find-bugs.json").read_text())
        self.assertEqual((review["id"], review["reviewed_commit"], review["readme_path"], review["license"]),
                         ("source-review-o-skills-repo-find-bugs", self.COMMIT, "skills/find-bugs/SKILL.md", "MIT"))
        self.assertEqual(review["observed"]["skill_md_sha256"], hashlib.sha256(skill_md).hexdigest())
        self.assertEqual(review["observed"]["skill_md_bytes"], len(skill_md))
        self.assertIs(review["observed"]["disable_model_invocation"], True)
        self.assertIs(review["observed"]["allow_implicit_invocation"], False)
        self.assertEqual(review["documentation_excerpts"][0]["source"], f"skills/find-bugs/SKILL.md@{self.COMMIT}")
        self.assertNotIn("disable-model-invocation", json.dumps(review["documentation_excerpts"]))
        self.assertIn("skill find-bugs", review["claim"])
        # make_result.py matches the review to the survivor as the ledger compares repositories.
        self.assertEqual(make_result.review_key(review["repository"]), make_result.review_key("o/skills-repo@find-bugs"))

    def test_a_skill_without_openai_yaml_keeps_implicit_invocation(self):
        skill_md = b"---\nname: find-bugs\ndescription: Find bugs.\n---\n\nBody.\n"
        done, out = self.review(self.answers(["plugins/p/skills/find-bugs/SKILL.md"],
                                             {"plugins/p/skills/find-bugs/SKILL.md": skill_md}),
                                [{"layer_id": "skills-review", "repository": "o/skills-repo@find-bugs"}])
        self.assertEqual(done.returncode, 0, done.stderr)
        observed = json.loads((out / "o-skills-repo-find-bugs.json").read_text())["observed"]
        self.assertEqual((observed["disable_model_invocation"], observed["allow_implicit_invocation"]), (False, True))

    def test_a_missing_or_ambiguous_skill_md_is_reported_and_skipped(self):
        for tree, message in ((["skills/other/SKILL.md"], "no SKILL.md"),
                              (["a/find-bugs/SKILL.md", "b/find-bugs/SKILL.md"], "2 SKILL.md folders")):
            with self.subTest(message):
                done, out = self.review(self.answers(tree, {}),
                                        [{"layer_id": "skills-review", "repository": "o/skills-repo@find-bugs"}])
                self.assertEqual(done.returncode, 1)
                self.assertIn(message, done.stderr)
                self.assertEqual(json.loads(done.stdout), [])


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
        write_json(self.root / base / "acme-agent-skills-debug-kit.json", {"repository": A1, "layers": ["skills-debug"]})
        reviews = [{"repository": A1, "path": "acme-agent-skills-debug-kit.json", "layers": ["skills-debug"]}]
        result = make_result.build_result(
            layers=out["layers"], reviews=reviews, usage=usage, manifest=manifest, sweep_id=LANE, lane=LANE,
            returns_ref=f"{base}/returns.json", usage_ref=f"{base}-attempts/child-usage-wf_fixture-1.json",
            manifest_ref="catalogs/sota-convergence/manifest-20260930.json", prompts_sha256="c" * 64,
            returns=out["returns"])
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


if __name__ == "__main__":
    unittest.main()
