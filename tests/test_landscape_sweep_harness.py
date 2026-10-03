"""Synthetic-fixture tests for tools/sota-convergence/landscape-sweep (no network, no codex, no model calls).

A fake `codex` (and a fake `gh`) early on PATH stands in for the real CLI, and a stubbed Hugging Face Hub fetch
for source_reviews.py; sweep.js runs under node with stubbed agent(), parallel() and pipeline() (skipped without
node); convert.py's evidence is appended to a synthetic saturation ledger checkout with scripts/saturation_ledger.py
itself. Optional: BASH32_BINARY (a real bash 3.2, as on macOS) and shellcheck.
"""

from __future__ import annotations

import base64
import contextlib
import copy
import errno
import hashlib
import importlib.util
import io
import json
import os
import re
import shlex
import shutil
import stat
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "sota-convergence" / "landscape-sweep"
sys.path.insert(0, str(ROOT / "scripts"))
import saturation_ledger as sl  # noqa: E402

NODE = shutil.which("node")
SHELLCHECK = shutil.which("shellcheck")
BASH32 = os.environ.get("BASH32_BINARY") if os.environ.get("BASH32_BINARY") and os.access(
    os.environ["BASH32_BINARY"], os.X_OK) else None
# A change detector: templates.json filled with the 2026-09-26 run's values (date, layer count, skills date) must give
# PROMPTS_SHA256_CURRENT, the sha256 of json.dumps(T, sort_keys=True, ensure_ascii=False). An intended template edit
# changes every later run's prompts_sha256; update PROMPTS_SHA256_CURRENT with it.
# 2026-09-27: the maintenance rule is derived from the OpenSSF Scorecard Maintained check, and licenses are information only
# (never a refutation reason), per the operator's 2026-09-26/27 decisions. Later on 2026-09-27 the facts refuter
# gained the unknown-field, maintenance and license exceptions (docs/decisions/2026-09-27-prompt-audit-resolution.md).
# 2026-09-28: the common Skills paragraph drops verification-before-completion, which the skills trial removed under
# its conflict rule (docs/decisions/2026-09-25-skills-trial-and-usage.md, 2026-09-28 removal addendum); the refutation
# rule "evidence before any verdict" stays as plain text. Previous value: 11fcd52312b9…0107.
# 2026-09-30: the skills modality (docs/decisions/2026-09-30-skills-sweep-modality.md) adds discover_skills,
# critic_skills and modality_skills to templates.json and ends facts and fit in <<MODALITY>>. build_args.fill_build
# resolves the modality at build time, so a repository run's frozen templates, and this value, are unchanged.
# Later on 2026-09-30, after unit F3 (#553) pinned skill-creator, which the skills templates name for its paired
# with-skill/without-skill benchmark, the common Skills paragraph names it too (build_args.TEMPLATE_SKILLS), as a
# Claude-Code-only skill to read and never run. Previous value: 9c34fa7211bc…f14b.
PROMPTS_SHA256_CURRENT = "b61956f351f5b71b6478f713a5f5f10a0c13e09198e528e6b10c9e1daa3c726d"
# Future U11 A/B source contract, filled with the same fixture values. This is not an activated runner's receipt.
PROMPTS_SHA256_V2_CURRENT = "67e3adfa24fd4110f9784283ad3884fd18ae67cabad53977f6cb98839b94e525"
# The same change detector for a skills run (filled with the same 2026-09-26 values and modality "skills"): discover
# and critic are discover_skills and critic_skills, and facts and fit end in modality_skills. The skills templates name
# the layer input's known_skills (installed and excluded skills as the manifest states them); the first value,
# 7798ad98a5d3…ec25, named a flattened owner/repo@name list. 2026-09-30 review repair: a true-valued
# disable-model-invocation is true/yes/on/1 in any letter case (Claude Code), Codex's allow_implicit_invocation counts
# only as a plain false, a source the catalog marks maintenance stale labels its skills not_adopted, and writing
# CLAUDE.md or AGENTS.md conflicts only when unasked (skills-agent-docs maintains them). Previous value: 5d9ae85a17be…48db.
# Later on 2026-09-30: common's Skills paragraph names skill-creator (see PROMPTS_SHA256_CURRENT). Previous value:
# 2c2efbaed4d9…63d3.
PROMPTS_SHA256_SKILLS_CURRENT = "a76ee858fe65b998dc974f8fe9cdac9562bdf14abe6f73dcd7d1778c9f95b460"
# The 2026-09-26 run's own value, kept in that run's record (evidence/artifacts/landscape-sweep-20260926/README.md);
# fixtures below use it as a historical run's recorded prompts_sha256.
PROMPTS_SHA256_20260926 = "3adfbed7a83e85da3fd7951032e1fa3a579101772a47b211580065c6b42618d4"
REQ, PLAT = "a" * 64, "b" * 64
LIMIT_TEXT = ("You’ve hit your usage limit. Visit https://chatgpt.com/codex/settings/usage to purchase more "
              "credits or try again at Sep 30th, 2026 11:50 PM.")
# Codex's report of an HTTP 429 without a usage-limit body (RetryLimitReachedError's Display,
# codex-rs/protocol/src/error.rs at rust-v0.157.1): the text of the ten jobs that ended so on 2026-09-29
# (gpt6-job-outcomes.json), with a fixture id.
RETRY_429_TEXT = "exceeded retry limit, last status: 429 Too Many Requests, request id: req_fixture0001"


def load(name):
    spec = importlib.util.spec_from_file_location(f"landscape_sweep_{name}", HARNESS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_args = load("build_args")
build_inputs = load("build_inputs")
codex_job = load("codex_job")
convert = load("convert")
make_prompt = load("make_prompt")
make_result = load("make_result")
sweep_common = load("sweep_common")
usage_record = load("usage_record")


def run(cmd, env=None, cwd=None, timeout=60):
    return subprocess.run([str(part) for part in cmd], capture_output=True, text=True, env=env, cwd=cwd,
                          timeout=timeout, check=False)


def write_json(path: Path, value) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1) + "\n", encoding="utf-8")
    return path


def temp_dir(case: unittest.TestCase) -> Path:
    path = Path(tempfile.mkdtemp(prefix="landscape-sweep-test-")).resolve()
    case.addCleanup(shutil.rmtree, path, ignore_errors=True)
    return path


def filled_templates(run_date="2026-10-26", count=2, skills_date="2026-09-25", modality="repository"):
    return build_args.fill_build(build_args.load_templates(), run_date, count, skills_date, modality)


# --------------------------------------------------------------------------- synthetic sweep data


def proposal(repository, label="keep_but_compare"):
    return {"repository": repository, "proposed_label": label, "demonstrated_gap": f"gap of {repository}",
            "comparison_that_would_overturn": "a frozen comparison", "evidence": [f"{repository} shows it"],
            "upstream_now": {"latest_release": "v1", "released_at": "2026-10-01", "stars": 10,
                             "pushed_at": "2026-10-20", "archived": False, "license": "MIT"},
            "source": "fixture"}


def discovery(layer_id, repositories, skills=(), calls=(3, 2, 20)):
    return {"layer_id": layer_id, "proposed": [proposal(r) for r in repositories],
            "calls": {"web_search": calls[0], "web_fetch": calls[1], "gh_api": calls[2]}, "notes": "",
            "skills_used": list(skills)}


def votes(layer_id, role, verdicts, skills=()):
    return {"layer_id": layer_id, "role": role, "skills_used": list(skills),
            "votes": [{"repository": repo, "refuted": refuted, "confidence": 0.8, "reasoning": f"{role} on {repo}",
                       "refs": [f"{repo}/releases"]} for repo, refuted in verdicts.items()]}


def gpt6_entry(output, status="ok"):
    """What sweep.js's parseWrapped returns for one GPT-6 job."""
    return {"status": status, "output": output, "usage": {"input_tokens": 1000, "cached_input_tokens": 900,
                                                         "output_tokens": 40} if output else {},
            "started": "2026-10-26T00:00:00Z", "finished": "2026-10-26T00:05:00Z",
            "stderr_tail": None if output else "boom", "model": "gpt-6-astra", "effort": "max"}


def merged_row(repository, families, label="keep_but_compare"):
    return {**proposal(repository, label), "families": list(families)}


A1, A2_CLAUDE, A2_GPT6 = "https://github.com/Owner/Alpha-One.git", "https://github.com/O/alpha-two", \
    "https://github.com/o/alpha-two/tree/main"
A3, A4, A5 = "https://github.com/o/alpha-three", "https://github.com/o/alpha-four", "https://github.com/o/alpha-five"
B1, B2 = "https://github.com/o/beta-one", "https://github.com/o/beta-two"


def synthetic_result():
    """Two layers as sweep.js returns them, plus a layer whose only round was lost.

    alpha: A2 proposed by both families (two spellings), A1/A3 by Claude, A4 by GPT-6, A5 dropped at the cap.
      facts refutes A3; the GPT-6 fit refuter refutes A2 and has no vote on A3. Survivors: A1, A4.
    beta: first round without a GPT-6 discovery return (degraded) and without a facts vote on B1 (refuted);
      a follow-up round proposes B2, which survives.
    gamma: lost.
    """
    alpha_gpt6_fit = votes("alpha", "fit", {A1: False, A2_GPT6: True, A4: False}, ["verification-before-completion"])
    alpha = {"layer_id": "alpha", "catalog": "foundation", "round": "first", "followup_reason": None,
             "claude_discover": discovery("alpha", [A1, A2_CLAUDE, A3], ["search-first", "iterative-retrieval"]),
             "gpt6_discover": gpt6_entry(discovery("alpha", [A2_GPT6, A4], ["search-first"], (4, 5, 6))),
             "merged": [merged_row(A2_CLAUDE, ["claude", "gpt6"]), merged_row(A1, ["claude"]),
                        merged_row(A3, ["claude"]), merged_row(A4, ["gpt6"])],
             "dropped": [{"repository": A5, "families": ["gpt6"], "proposed_label": "not_adopted"}],
             "facts": votes("alpha", "facts", {A1: False, A2_CLAUDE: False, A3: True, A4: False},
                            ["verification-before-completion"]),
             "fit_claude": votes("alpha", "fit", {A1: False, A2_CLAUDE: False, A3: False, A4: False}, ["fp-check"]),
             "fit_gpt6": gpt6_entry(alpha_gpt6_fit)}
    beta = {"layer_id": "beta", "catalog": "us-equities", "round": "first", "followup_reason": None,
            "claude_discover": discovery("beta", [B1]), "gpt6_discover": gpt6_entry(None, "failed_exit_1"),
            "merged": [merged_row(B1, ["claude"])], "dropped": [],
            "facts": votes("beta", "facts", {}), "fit_claude": votes("beta", "fit", {B1: False}),
            "fit_gpt6": gpt6_entry(votes("beta", "fit", {B1: False}))}
    followup = {"reason": "missed a class", "search_directions": ["x"], "already": [B1]}
    beta_followup = {"layer_id": "beta", "catalog": "us-equities", "round": "followup", "followup_reason": followup,
                     "claude_discover": discovery("beta", [B2]),
                     "gpt6_discover": gpt6_entry(discovery("beta", [B2])),
                     "merged": [merged_row(B2, ["claude", "gpt6"])], "dropped": [],
                     "facts": votes("beta", "facts", {B2: False}, ["supply-chain-risk-auditor"]),
                     "fit_claude": votes("beta", "fit", {B2: False}),
                     "fit_gpt6": gpt6_entry(votes("beta", "fit", {B2: False}))}
    gamma = {"layer_id": "gamma", "catalog": "foundation", "round": "first", "lost": True}
    critic = {"followup_layers": [{"layer_id": "beta", "reason": "missed a class", "search_directions": ["x"]}],
              "general": []}
    return {"sweep": "landscape-sweep-20261026", "first": [alpha, beta, gamma], "critic": critic,
            "followups": [beta_followup], "lost_first": ["gamma"]}


def healthy_result():
    """One layer whose every worker returned: both discovery families, and all three votes on each proposal. A1 is
    refuted by facts and A4 by the Claude fit refuter, so nothing survives: a clean layer."""
    alpha = {"layer_id": "alpha", "catalog": "foundation", "round": "first", "followup_reason": None,
             "claude_discover": discovery("alpha", [A1]), "gpt6_discover": gpt6_entry(discovery("alpha", [A4])),
             "merged": [merged_row(A1, ["claude"]), merged_row(A4, ["gpt6"])], "dropped": [],
             "facts": votes("alpha", "facts", {A1: True, A4: False}),
             "fit_claude": votes("alpha", "fit", {A1: False, A4: True}),
             "fit_gpt6": gpt6_entry(votes("alpha", "fit", {A1: False, A4: False}))}
    return {"sweep": "landscape-sweep-20261026", "first": [alpha], "critic": {"followup_layers": [], "general": []},
            "followups": [], "lost_first": []}


def healthy_two_layers():
    """healthy_result() plus an equally healthy us-equities layer beta: without a retained failure both are clean."""
    res = healthy_result()
    res["first"].append({"layer_id": "beta", "catalog": "us-equities", "round": "first", "followup_reason": None,
                         "claude_discover": discovery("beta", [B1]), "gpt6_discover": gpt6_entry(discovery("beta", [B2])),
                         "merged": [merged_row(B1, ["claude"]), merged_row(B2, ["gpt6"])], "dropped": [],
                         "facts": votes("beta", "facts", {B1: True, B2: False}),
                         "fit_claude": votes("beta", "fit", {B1: False, B2: True}),
                         "fit_gpt6": gpt6_entry(votes("beta", "fit", {B1: False, B2: False}))})
    return res


def fail_gpt6_fit(res):
    """Every GPT-6 fit job failed (any non-limit failure: auth, a missing model, a timeout, a lossy wrapper)."""
    for entry in res["first"] + [e for e in res.get("followups") or [] if e]:
        if not entry.get("lost"):
            entry["fit_gpt6"] = gpt6_entry(None, "failed_exit_1")
    return res


def write_codex_files(work: Path, res: dict) -> None:
    """The gpt6/<job>/last.json and exit files a faithful run leaves for each GPT-6 output the workflow received."""
    for entry in res["first"] + [e for e in res.get("followups") or [] if e]:
        if entry.get("lost"):
            continue
        suffix = "-followup" if entry.get("round") == "followup" else ""
        for name, key in (("discover", "gpt6_discover"), ("fit", "fit_gpt6")):
            job = entry.get(key)
            if job and job.get("status") == "ok":
                directory = work / "gpt6" / f"gpt6-{name}-{entry['layer_id']}{suffix}"
                write_json(directory / "last.json", job["output"])
                (directory / "exit").write_text("0\n", encoding="utf-8")


def scope_for(layers=(("foundation", "alpha"), ("us-equities", "beta"), ("foundation", "gamma"))):
    return {"platform_profiles_sha256": PLAT,
            "requirement_sha256": {f"{catalog}/{layer_id}": REQ for catalog, layer_id in layers}}


def child_usage_raw(run_id, labels, status="complete", transcript_root="/home/example/.claude/projects/p/s"):
    children = [{"label": label, "requested_model": "sonnet" if label.startswith("gpt6-") else "opus",
                 "resolved_models": ["claude-sonnet-5" if label.startswith("gpt6-") else "claude-opus-5-5"],
                 "efforts": ["max"], "web_search": {"calls": 0, "capped": 0, "first_capped_at": None},
                 "complete": True} for label in labels]
    return json.dumps({"transcript_dir": f"{transcript_root}/subagents/workflows/{run_id}", "status": status,
                       "reason": "fixture", "web_search": {"calls": 0, "capped": 0, "capped_children": []},
                       "children": children}).encode("utf-8")


SYNTHETIC_LABELS = [f"{role}:{layer}" for layer in ("alpha", "beta") for role in
                    ("discover", "gpt6-discover", "refute-facts", "refute-fit", "gpt6-refute-fit")] + [
    f"{role}:beta:followup" for role in ("discover", "gpt6-discover", "refute-facts", "refute-fit", "gpt6-refute-fit")
] + ["critic"]


# --------------------------------------------------------------------------- templates and skills


class TemplateTests(unittest.TestCase):
    def test_filled_templates_match_the_current_prompts_sha256(self):
        frozen = filled_templates("2026-09-26", 32, "2026-09-25")
        self.assertEqual(sweep_common.prompts_sha256(frozen), PROMPTS_SHA256_CURRENT)

    def test_filled_skills_templates_match_the_current_skills_prompts_sha256(self):
        frozen = filled_templates("2026-09-26", 32, "2026-09-25", "skills")
        self.assertEqual(sorted(frozen), sorted(make_prompt.RUNTIME_PLACEHOLDERS))
        self.assertEqual(sweep_common.prompts_sha256(frozen), PROMPTS_SHA256_SKILLS_CURRENT)
        with self.assertRaisesRegex(ValueError, "modality"):
            filled_templates(modality="papers")

    def test_templates_never_refute_on_license_and_name_the_maintenance_rule(self):
        templates = json.loads((HARNESS / "templates.json").read_text())
        common, fit = templates["common"], templates["fit"]
        # Licenses: information only, in the selection principles and in the merit criteria every role receives.
        self.assertIn("never a reason to exclude, refute or rank down", common)
        self.assertIn("and platform fit (license is information only)", common)
        self.assertNotIn("license and platform fit", common)
        self.assertNotIn("OSI or clearly usable license", common)
        self.assertNotIn("license is non-commercial", fit)
        # No role treats a license as a criterion: the facts refuter records a wrong or unverifiable license in its
        # reasoning and never refutes on it.
        for key, text in templates.items():
            for phrase in ("license is non-commercial", "restrictive license", "unclear license", "usable license"):
                self.assertNotIn(phrase, text, f"{key} still uses a license as a criterion: {phrase!r}")
        # Maintenance: derived from the Scorecard check, with its evidence command and a flag destination.
        self.assertIn("derived from the OpenSSF Scorecard Maintained check", common)
        self.assertIn("commits?since=", common)
        self.assertIn("not from pushed_at", common)
        self.assertIn("TOO NEW TO ASSESS (<90 days)", common)
        self.assertIn("it is stale under the selection principles' maintenance rule", fit)
        # A lane that cannot reach the commit evidence (the web-only GPT-6 lane) never refutes on it.
        self.assertIn("never excludes or refutes a repository on unknown maintenance", common)
        self.assertIn("unknown maintenance is never a reason to refute", fit)

    def test_the_facts_refuter_states_the_unknown_field_maintenance_and_license_exceptions(self):
        # The facts refuter gets common and each proposal's upstream_now in one prompt (sweep.js), so its
        # refute-when-uncertain default must name common's exceptions; #385 changed common and fit only
        # (docs/decisions/2026-09-27-prompt-audit-resolution.md).
        facts = json.loads((HARNESS / "templates.json").read_text())["facts"]
        for phrase in ("a null upstream_now field means unknown",
                       "record an unverifiable commit or activity fact as unknown",
                       "none of these is a reason to refute",
                       "a wrong or unverifiable license as a correction or as unknown"):
            self.assertIn(phrase, facts)

    def test_only_per_call_placeholders_remain_after_filling(self):
        frozen = filled_templates()
        for key, text in frozen.items():
            self.assertEqual(set(make_prompt.PLACEHOLDER.findall(text)), make_prompt.RUNTIME_PLACEHOLDERS[key], key)
        self.assertIn("Date: 2026-10-26.", frozen["common"])
        self.assertIn("a 2-layer saturation sweep", frozen["critic"])
        skills = filled_templates(modality="skills")
        for key, text in skills.items():
            self.assertEqual(set(make_prompt.PLACEHOLDER.findall(text)), make_prompt.RUNTIME_PLACEHOLDERS[key], key)
        self.assertIn("a 2-layer skills sweep", skills["critic"])

    def test_skills_named_by_the_templates_are_pinned_kept_or_trial_skills(self):
        manifest = json.loads((ROOT / build_args.SKILLS_MANIFEST).read_text(encoding="utf-8"))
        templates = build_args.load_templates()
        self.assertEqual(build_args.skills_problems(templates, manifest), [])
        self.assertEqual(build_args.skill_mentions(templates["common"], build_args.TEMPLATE_SKILLS),
                         list(build_args.TEMPLATE_SKILLS))
        self.assertIn("skills_used", templates["common"])

    def test_skill_drift_is_reported(self):
        manifest = json.loads((ROOT / build_args.SKILLS_MANIFEST).read_text(encoding="utf-8"))
        templates = build_args.load_templates()
        unpinned = copy.deepcopy(manifest)
        unpinned["skills"] = [s for s in unpinned["skills"] if s["name"] != "fp-check"]
        self.assertTrue(any("fp-check is not pinned" in p for p in build_args.skills_problems(templates, unpinned)))
        extra = dict(templates, common=templates["common"] + " Also use tdd.")
        self.assertTrue(any("missing from TEMPLATE_SKILLS" in p for p in build_args.skills_problems(extra, manifest)))
        # Every template is scanned, not only common: the skills modality's templates reach workers too.
        for key in ("discover_skills", "critic_skills", "modality_skills", "facts"):
            extra = dict(templates, **{key: templates[key] + " Also use tdd."})
            self.assertTrue(any("missing from TEMPLATE_SKILLS" in p and key in p
                                for p in build_args.skills_problems(extra, manifest)), key)

    def test_worker_schemas_are_strict_and_require_skills_used(self):
        for name in ("discover", "discover-skills", "votes"):
            schema = json.loads((HARNESS / "schemas" / f"{name}.json").read_text(encoding="utf-8"))
            self.assertFalse(schema["additionalProperties"])
            self.assertIn("skills_used", schema["required"])
        critic = json.loads((HARNESS / "schemas" / "critic.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(critic["required"]), ["followup_layers", "general"])


# --------------------------------------------------------------------------- make_prompt


class MakePromptTests(unittest.TestCase):
    LAYER = {"catalog": "foundation", "layer_id": "alpha", "title": "Alpha", "requirement": "do alpha",
             "requirement_sha256": REQ, "platform_profiles_sha256": PLAT}

    def test_discover_prompt_embeds_the_input_and_ends_with_the_lane_note(self):
        frozen = filled_templates()
        text = make_prompt.compose(frozen, "discover", self.LAYER)
        self.assertTrue(text.startswith(frozen["common"] + "\n\n"))
        self.assertIn(json.dumps(self.LAYER, indent=1), text)
        self.assertIn("Set layer_id to alpha.", text)
        self.assertNotIn("<<", text)
        self.assertTrue(text.endswith(make_prompt.TAIL))

    def test_followup_and_fit_prompts(self):
        frozen = filled_templates()
        followup = {"reason": "missed class", "search_directions": ["d1", "d2"], "already": ["r1", "r2"]}
        text = make_prompt.compose(frozen, "discover", self.LAYER, followup=followup)
        self.assertIn("FOLLOW-UP ROUND. The completeness critic flagged this layer: missed class", text)
        self.assertIn("Search directions: d1; d2", text)
        self.assertIn("(do not re-propose): r1, r2", text)
        proposals = json.dumps([{"repository": "https://github.com/o/a"}])
        fit = make_prompt.compose(frozen, "fit", self.LAYER, proposals)
        self.assertIn("Proposals (JSON):\n" + proposals, fit)
        self.assertIn("Set role to fit and layer_id to alpha.", fit)

    def test_values_are_filled_in_one_pass(self):
        frozen = filled_templates()
        tricky = '[{"repository": "$& $\' $1 <<LAYER_ID>> <<PROPOSALS>>"}]'
        fit = make_prompt.compose(frozen, "fit", self.LAYER, tricky)
        self.assertIn(tricky, fit)

    def test_unfilled_repository_templates_are_refused(self):
        with self.assertRaisesRegex(ValueError, "DATE"):
            make_prompt.compose(build_args.load_templates(), "discover", self.LAYER)


# --------------------------------------------------------------------------- repository canonicalization

CANONICAL = {
    "https://github.com/httpie/cli/tree/main": "https://github.com/httpie/cli",
    "https://github.com/HTTPie/CLI.git": "https://github.com/httpie/cli",
    "http://www.github.com/http-party/http-server/": "https://github.com/http-party/http-server",
    "github.com/o/r#readme": "https://github.com/o/r",
    " https://github.com/o/r ": "https://github.com/o/r",
    "https://github.com/o/pages.github.io": "https://github.com/o/pages.github.io",
    "httpie/cli": "https://github.com/httpie/cli",
    "HTTPie/cli.git": "https://github.com/httpie/cli",
    "http-party/http-server/": "https://github.com/http-party/http-server",
}
NOT_GITHUB = ["https://gitlab.com/o/r", "https://example.com", "gitlab.com/o", "https://github.com/o", "not a repo", ""]


class CanonTests(unittest.TestCase):
    def test_github_urls_and_bare_slugs_are_canonical_whatever_the_owner_is_called(self):
        for value, expected in CANONICAL.items():
            self.assertEqual(sweep_common.canon(value), expected, value)
            self.assertEqual(sweep_common.slug(value), expected[len("https://github.com/"):], value)
        for value in NOT_GITHUB:
            self.assertEqual(sweep_common.canon(value), value, value)
        self.assertIsNone(sweep_common.canon(None))


# --------------------------------------------------------------------------- build_inputs


class BuildInputsTests(unittest.TestCase):
    def setUp(self):
        self.repo = temp_dir(self)
        self.work = temp_dir(self)
        write_json(self.repo / "catalogs/landscape/foundation.json", {"layers": [{
            "layer_id": "alpha", "title": "Alpha", "requirement": "alpha req", "open_gaps": ["g" * 400],
            "overturn_when": "never",
            "winners": [{"component_id": "w", "repository": "https://github.com/sharkdp/bat", "pin": "1",
                         "evidence_class": "native", "platform_status": {"linux": "ok"}, "why_selected": "x"}],
            "alternatives": [{"name": "alt", "repository": "https://github.com/cli/cli.git", "disposition": "keep",
                              "why_not_default": "y"}],
            "candidates": [{"name": "c", "repository": "https://github.com/tauri-apps/tauri/tree/dev"}]}]})
        write_json(self.repo / "catalogs/landscape/us-equities.json", {"layers": [{
            "layer_id": "beta", "title": "Beta", "requirement": "beta req", "winners": [], "alternatives": [],
            "candidates": []}]})
        write_json(self.repo / "catalogs/landscape/research-state.json", {"layers": [
            {"catalog": "foundation", "layer_id": "alpha", "status": "comparison_required", "next_action": "a"},
            {"catalog": "us-equities", "layer_id": "beta", "status": "on_requirement_change", "next_action": "b"}]})
        completed = {"sweep_id": "sw-1", "status": "completed", "manifest_ref": "catalogs/m1.json", "layers": [
            {"catalog": "foundation", "layer_id": "alpha", "survived": [{"repo": "https://github.com/o/s"}],
             "refuted": [{"repo": "https://github.com/o/r"}]}]}
        stopped = {"sweep_id": "sw-2-attempt", "status": "stopped", "manifest_ref": "catalogs/m1.json",
                   "layers": [{"catalog": "foundation", "layer_id": "alpha", "survived": [], "refuted": []}]}
        write_json(self.repo / "catalogs/saturation/ledger.json", {"sweeps": [completed, stopped]})
        write_json(self.repo / "catalogs/m1.json", {"foundation": [{"layer": "alpha", "candidates": [
            {"repository": "https://github.com/facebook/react"}]}], "trading": []})
        self.freshness = write_json(self.work / "freshness.json", {"checked_at": "2026-10-26", "foundation": [
            {"layer": "alpha", "components": [{"id": "w", "repository": "https://github.com/sharkdp/bat", "pin": "1",
                                               "upstream": {"latest": "2"}, "pin_behind_upstream": True,
                                               "pin_comparison": "compared", "review_status": "x"}]}],
            "trading": [{"layer": "beta", "entries": [{"id": "e", "repository": "https://github.com/o/e", "pin": "3",
                                                       "upstream": {"latest": "4"}, "pin_behind_upstream": True,
                                                       "pin_comparison": "compared", "decision": "default"}]}]})
        write_json(self.work / "scope.json", scope_for((("foundation", "alpha"), ("us-equities", "beta"))))

    def build(self, *extra):
        return run([sys.executable, HARNESS / "build_inputs.py", "--work-dir", self.work, "--repo-root", self.repo,
                    "--freshness-manifest", self.freshness, *extra])

    def test_inputs_carry_scope_winners_pins_previous_sweep_and_seeds(self):
        seeds = write_json(self.work / "seeds.json", {"beta": ["seeded thing"]})
        done = self.build("--seeds", seeds)
        self.assertEqual(done.returncode, 0, done.stderr)
        alpha = json.loads((self.work / "inputs/alpha.json").read_text())
        beta = json.loads((self.work / "inputs/beta.json").read_text())
        # Slugs keep repositories that end in t, i, g or a dot (the prototype's rstrip(".git") cut them).
        self.assertEqual(alpha["known_repositories"], ["cli/cli", "facebook/react", "sharkdp/bat", "tauri-apps/tauri"])
        self.assertEqual(alpha["previous_sweep"], {"sweep_id": "sw-1", "survived": ["https://github.com/o/s"],
                                                   "refuted": ["https://github.com/o/r"]})
        self.assertEqual((alpha["requirement_sha256"], alpha["platform_profiles_sha256"]), (REQ, PLAT))
        self.assertEqual(alpha["components_vs_upstream"][0]["pin_behind_upstream"], True)
        self.assertNotIn("review_status", alpha["components_vs_upstream"][0])
        self.assertEqual(beta["components_vs_upstream"][0]["id"], "e")  # trading entries count too
        self.assertEqual((alpha["seeded_candidates"], beta["seeded_candidates"]), ([], ["seeded thing"]))
        self.assertEqual(alpha["upstream_checked_at"], "2026-10-26")
        self.assertEqual(len(alpha["open_gaps"][0]), 300)
        layers = json.loads((self.work / "layers.json").read_text())
        self.assertEqual([(x["catalog"], x["layer_id"]) for x in layers], [("foundation", "alpha"), ("us-equities", "beta")])

    def test_inputs_date_the_sealed_verdict_fields_and_join_the_gap_ledgers(self):
        # winners, alternatives and open_gaps are a row's sealed verdict (tools/sota-convergence/README.md, the
        # grandfathered wave): a sweep reads them weeks later. The gap-wave ledgers record, by open_gaps index and
        # text, what later receipts did to each gap (lane_packets.gap_receipts_index reads the same ledgers).
        catalog = json.loads((self.repo / "catalogs/landscape/foundation.json").read_text())
        catalog["layers"][0].update({"checked_at": "2026-09-22", "open_gaps": ["g" * 400, "second gap", "third gap"]})
        write_json(self.repo / "catalogs/landscape/foundation.json", catalog)
        receipt = "evidence/artifacts/gap-wave2-20260923/alpha/0-run.json"
        write_json(self.repo / receipt, {"id": "0-run"})
        first, both = "gap-wave2-20260923--owner-a", "gap-wave2-20260923+gap-wave3-20260923--owner-b"
        write_json(self.repo / f"catalogs/landscape/{first}.json", {
            "id": first, "wave": "gap-wave2-20260923", "layers": [
                {"catalog": "foundation", "layer_id": "alpha", "gaps": [
                    {"index": 0, "text": "g" * 400, "status": "advanced",
                     "receipts": [{"path": receipt, "credit": "advanced"}]},
                    {"index": 1, "text": "a text the sealed row does not carry", "status": "settled", "receipts": []},
                    {"index": 2, "text": "third gap", "status": "not_run"}]},
                {"catalog": "foundation", "layer_id": "no-such-layer", "gaps": [
                    {"index": 0, "text": "x", "status": "settled"}]}]})
        write_json(self.repo / f"catalogs/landscape/{both}.json", {
            "id": both, "wave": ["gap-wave2-20260923", "gap-wave3-20260923"], "layers": [
                {"catalog": "foundation", "layer_id": "alpha", "gaps": [
                    {"index": 0, "text": "g" * 400, "status": "settled",
                     "receipts": [{"path": receipt, "credit": "settled"},
                                  {"path": "evidence/artifacts/not-in-this-checkout.json", "credit": "settled"}]}]}]})
        done = self.build()
        self.assertEqual(done.returncode, 0, done.stderr)
        alpha = json.loads((self.work / "inputs/alpha.json").read_text())
        beta = json.loads((self.work / "inputs/beta.json").read_text())
        self.assertEqual(alpha["verdict_checked_at"], "2026-09-22")
        self.assertEqual(alpha["open_gaps_followup"], [
            {"index": 0, "status": "settled", "receipts": [receipt],
             "waves": ["gap-wave2-20260923", "gap-wave3-20260923"], "ledgers": [both]},
            {"index": 0, "status": "advanced", "receipts": [receipt], "waves": ["gap-wave2-20260923"],
             "ledgers": [first]},
            {"index": 2, "status": "not_run", "receipts": [], "waves": ["gap-wave2-20260923"], "ledgers": [first]}])
        # open_gaps itself stays the list of clipped strings the templates read.
        self.assertEqual([len(gap) for gap in alpha["open_gaps"]], [300, 10, 9])
        for field in ("verdict_checked_at", "components_vs_upstream", "open_gaps_followup"):
            self.assertIn(field, alpha["verdict_note"])
        self.assertEqual(alpha["verdict_note"], beta["verdict_note"])
        self.assertEqual((beta["verdict_checked_at"], beta["open_gaps_followup"]), (None, []))
        # No silent caps: the entry whose text the sealed row does not carry and the unknown layer's entry are counted.
        self.assertIn("gap follow-ups: 3 joined from 2 ledger(s), 2 dropped", done.stdout)

    def test_two_ledgers_that_record_the_same_followup_share_one_entry(self):
        catalog = json.loads((self.repo / "catalogs/landscape/foundation.json").read_text())
        catalog["layers"][0]["open_gaps"] = ["only gap"]
        write_json(self.repo / "catalogs/landscape/foundation.json", catalog)
        first, both = "gap-wave2-20260923--owner-a", "gap-wave2-20260923+gap-wave3-20260923--owner-a"
        for name, wave in ((first, "gap-wave2-20260923"), (both, ["gap-wave2-20260923", "gap-wave3-20260923"])):
            write_json(self.repo / f"catalogs/landscape/{name}.json", {"id": name, "wave": wave, "layers": [
                {"catalog": "foundation", "layer_id": "alpha", "gaps": [
                    {"index": 0, "text": "only gap", "status": "advanced", "receipts": []}]}]})
        done = self.build()
        self.assertEqual(done.returncode, 0, done.stderr)
        alpha = json.loads((self.work / "inputs/alpha.json").read_text())
        self.assertEqual(alpha["open_gaps_followup"], [
            {"index": 0, "status": "advanced", "receipts": [],
             "waves": ["gap-wave2-20260923", "gap-wave3-20260923"], "ledgers": [both, first]}])
        self.assertIn("gap follow-ups: 2 joined from 2 ledger(s), 0 dropped", done.stdout)

    def test_a_gap_beyond_the_five_shown_gets_no_followup(self):
        catalog = json.loads((self.repo / "catalogs/landscape/foundation.json").read_text())
        catalog["layers"][0]["open_gaps"] = [f"gap {number}" for number in range(7)]
        write_json(self.repo / "catalogs/landscape/foundation.json", catalog)
        write_json(self.repo / "catalogs/landscape/gap-wave2-20260923--owner-a.json", {
            "id": "gap-wave2-20260923--owner-a", "wave": "gap-wave2-20260923", "layers": [
                {"catalog": "foundation", "layer_id": "alpha", "gaps": [
                    {"index": 4, "text": "gap 4", "status": "advanced"},
                    {"index": 6, "text": "gap 6", "status": "settled"}]}]})
        done = self.build()
        self.assertEqual(done.returncode, 0, done.stderr)
        alpha = json.loads((self.work / "inputs/alpha.json").read_text())
        self.assertEqual(len(alpha["open_gaps"]), 5)
        self.assertEqual([entry["index"] for entry in alpha["open_gaps_followup"]], [4])
        self.assertIn("gap follow-ups: 1 joined from 1 ledger(s), 0 dropped", done.stdout)

    def test_a_proposal_refuted_by_absence_is_shown_as_not_adjudicated(self):
        # o/r: facts and the Claude fit refuter returned not refuted, the GPT-6 fit vote never returned. o/m: facts
        # refuted it on merit.
        returns = "evidence/sw-1/returns.json"
        write_json(self.repo / returns, {"votes": {"alpha": [
            {"facts": {"role": "facts", "repository": "https://github.com/o/r", "refuted": False},
             "fit": {"role": "fit", "repository": "https://github.com/o/r", "refuted": True,
                     "claude": {"refuted": False}, "gpt6": {"missing": True}}},
            {"facts": {"role": "facts", "repository": "https://github.com/o/m", "refuted": True},
             "fit": {"role": "fit", "repository": "https://github.com/o/m", "refuted": True,
                     "claude": {"refuted": False}, "gpt6": {"missing": True}}}]}})
        ledger = json.loads((self.repo / "catalogs/saturation/ledger.json").read_text())

        def entry(repo, index, facts):
            return {"repo": repo, "facts": {"vote": facts, "ref": f"{returns}#/votes/alpha/{index}/facts"},
                    "fit": {"vote": "refuted", "ref": f"{returns}#/votes/alpha/{index}/fit"}}
        ledger["sweeps"][0]["layers"][0]["refuted"] = [entry("https://github.com/o/r", 0, "not_refuted"),
                                                        entry("https://github.com/o/m", 1, "refuted")]
        write_json(self.repo / "catalogs/saturation/ledger.json", ledger)
        done = self.build()
        self.assertEqual(done.returncode, 0, done.stderr)
        previous = json.loads((self.work / "inputs/alpha.json").read_text())["previous_sweep"]
        self.assertEqual((previous["refuted"], previous["not_adjudicated"]),
                         (["https://github.com/o/m"], ["https://github.com/o/r"]))
        self.assertIn("not refuted on merit", previous["not_adjudicated_note"])

    def test_unknown_seed_layers_and_unfrozen_layers_are_refused(self):
        seeds = write_json(self.work / "seeds.json", {"zeta": ["x"]})
        done = self.build("--seeds", seeds)
        self.assertEqual(done.returncode, 2)
        self.assertIn("zeta", done.stderr)
        write_json(self.work / "scope.json", scope_for((("foundation", "alpha"),)))
        done = self.build()
        self.assertEqual(done.returncode, 2)
        self.assertIn("us-equities/beta", done.stderr)

    def test_the_20260926_seeds_record_has_the_seeds_format(self):
        # A record of that run's inputs: its format is checked, not today's layer list.
        seeds = json.loads((HARNESS / "seeds-20260926.json").read_text(encoding="utf-8"))
        self.assertEqual(build_inputs.check_seeds(seeds, list(seeds)), seeds)
        self.assertEqual(len(seeds), 14)


class NeutralSchemaTests(unittest.TestCase):
    @staticmethod
    def judgment():
        return {"judgment_id": "screen-alpha-claude-1", "order_seed": 17, "family": "claude",
                "model_route_requested": "opus", "model_route_actual": None, "source_field_sha256": "c" * 64,
                "provider_sampling_seed_requested": None, "provider_sampling_seed_actual": None,
                "provider_sampling_seed_status": "not_exposed"}

    def test_v2_vote_schema_requires_screen_provenance_without_inventing_provider_seeds(self):
        import host_receipts
        schema = json.loads((HARNESS / "schemas/votes-v2.json").read_text())
        returned = {"contract_version": 2, "layer_id": "alpha", "role": "facts", "votes": [{
            "candidate_key": "foundation/alpha/o/r", "repository": "https://github.com/o/r",
            "evidence_key": "foundation/alpha/o/r", "status": "pending", "criterion": None,
            "fact": None, "confidence": 0, "reasoning": "identity source unavailable", "refs": [],
            "requirement_fit": None}], "skills_used": [], "judgment": self.judgment()}
        errors = []
        host_receipts.validate_against_schema(returned, schema, "$", errors)
        self.assertEqual(errors, [])
        for field in ("judgment_id", "order_seed", "family", "model_route_requested", "source_field_sha256",
                      "provider_sampling_seed_requested", "provider_sampling_seed_actual", "provider_sampling_seed_status"):
            invalid = copy.deepcopy(returned)
            invalid["judgment"].pop(field)
            errors = []
            host_receipts.validate_against_schema(invalid, schema, "$", errors)
            self.assertTrue(errors, field)
        invalid = copy.deepcopy(returned)
        invalid.pop("judgment")
        errors = []
        host_receipts.validate_against_schema(invalid, schema, "$", errors)
        self.assertTrue(errors)

    def test_v2_templates_admit_against_the_requirement_and_keep_unknown_votes_pending(self):
        templates = build_args.load_templates()
        v2 = build_args.fill_build(templates, "2026-09-26", 32, "2026-09-25", contract_version=2)
        self.assertEqual(sweep_common.prompts_sha256(v2), PROMPTS_SHA256_V2_CURRENT)
        self.assertIn("requirement_fit", v2["discover"])
        self.assertIn("frozen_tasks", v2["discover"])
        self.assertIn("novelty only", v2["discover"])
        self.assertIn("not an eligibility limit", v2["discover"])
        self.assertIn("https://huggingface.co/<lowercase namespace/model>", v2["discover"])
        self.assertIn("only when the frozen requirement explicitly requires maintenance", v2["common"])
        for role in ("facts", "fit"):
            self.assertIn("status=pending", v2[role])
            self.assertIn("candidate_key", v2[role])
            self.assertNotIn("refuted=true", v2[role])
            self.assertNotIn("gap versus the current winners", v2[role])
        for candidate_name in ("NautilusTrader", "ai-memory", "LEAN"):
            self.assertNotIn(candidate_name, v2["common"])
        self.assertIn("mandatory paid service", v2["fit"])
        self.assertIn("missing credentials", v2["fit"])
        # Existing source strings and frozen V1 hashes remain the explicit historical lane contract.
        self.assertEqual(sweep_common.prompts_sha256(filled_templates("2026-09-26", 32, "2026-09-25")),
                         PROMPTS_SHA256_CURRENT)
        self.assertEqual(sweep_common.prompts_sha256(filled_templates("2026-09-26", 32, "2026-09-25", "skills")),
                         PROMPTS_SHA256_SKILLS_CURRENT)
        with self.assertRaisesRegex(ValueError, "skills"):
            build_args.fill_build(templates, "2026-09-26", 32, "2026-09-25", "skills", contract_version=2)

    def test_v2_discovery_admits_requirement_fit_without_a_winner_relative_gap(self):
        import host_receipts
        schema = json.loads((HARNESS / "schemas/discover-v2.json").read_text())
        candidate = {"candidate_key": "foundation/alpha/o/r", "repository": "https://github.com/o/r",
                     "evidence_key": "foundation/alpha/o/r", "proposed_label": "admit",
                     "requirement_fit": "The documented interface renders exact output on both target hosts.",
                     "frozen_tasks": ["frozen-render-task"], "admission_reason": None, "pending_reason": None,
                     "evidence": ["https://github.com/o/r/blob/main/README.md"], "source": "primary-source search",
                     "upstream_now": {"latest_release": None, "released_at": None, "stars": None,
                                      "pushed_at": None, "archived": None, "license": None}}
        returned = {"contract_version": 2, "layer_id": "alpha", "proposed": [candidate],
                    "calls": {"web_search": 1, "web_fetch": 1, "gh_api": 0}, "notes": "", "skills_used": []}
        errors = []
        host_receipts.validate_against_schema(returned, schema, "$", errors)
        self.assertEqual(errors, [])
        for change in ({"proposed_label": "keep_but_compare"}, {"admission_reason": "no_gap_vs_winner"},
                       {"demonstrated_gap": "must beat the installed winner"}):
            errors = []
            invalid = copy.deepcopy(returned)
            invalid["proposed"][0].update(change)
            host_receipts.validate_against_schema(invalid, schema, "$", errors)
            self.assertTrue(errors, change)

    def test_v2_votes_preserve_pending_identity_and_reject_incumbent_relative_refutations(self):
        import host_receipts
        schema = json.loads((HARNESS / "schemas/votes-v2.json").read_text())
        vote = {"candidate_key": "foundation/alpha/o/r", "repository": "https://github.com/o/r",
                "evidence_key": "foundation/alpha/o/r", "status": "pending", "criterion": None,
                "fact": None, "confidence": 0.0, "reasoning": "the primary source did not return",
                "refs": [], "requirement_fit": None}
        returned = {"contract_version": 2, "layer_id": "alpha", "role": "fit", "votes": [vote], "skills_used": [],
                    "judgment": self.judgment()}
        errors = []
        host_receipts.validate_against_schema(returned, schema, "$", errors)
        self.assertEqual(errors, [])
        for change in ({"criterion": "no_gap_vs_winner", "status": "not_credible"}, {"refuted": True},
                       {"status": "not_refuted"}):
            errors = []
            invalid = copy.deepcopy(returned)
            invalid["votes"][0].update(change)
            host_receipts.validate_against_schema(invalid, schema, "$", errors)
            self.assertTrue(errors, change)
        for required in ("candidate_key", "evidence_key", "reasoning"):
            errors = []
            invalid = copy.deepcopy(returned)
            invalid["votes"][0].pop(required)
            host_receipts.validate_against_schema(invalid, schema, "$", errors)
            self.assertTrue(errors, required)


class NeutralFieldTests(unittest.TestCase):
    """U11 A/B fixtures at the input-builder CLI, independent of the live V1 workflow."""

    def setUp(self):
        BuildInputsTests.setUp(self)
        profiles = [{"id": "linux-wsl2-x86_64", "os": "linux", "architecture": "x86_64"},
                    {"id": "macos-arm64", "os": "macos", "architecture": "arm64"}]
        write_json(self.repo / "adoption/manifest.json", {"platform_profiles": profiles})
        scope = json.loads((self.work / "scope.json").read_text())
        scope["platform_profiles_sha256"] = hashlib.sha256(
            json.dumps(profiles, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        write_json(self.work / "scope.json", scope)

    build = BuildInputsTests.build

    def test_v2_field_keeps_actual_hugging_face_history_and_fit_refutations_pending(self):
        path = self.repo / "catalogs/saturation/ledger.json"
        ledger = json.loads(path.read_text())
        repository = "https://huggingface.co/XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B"
        ledger["sweeps"][0]["layers"][0]["proposed"] = [repository, "https://github.com/o/also-returned"]
        ledger["sweeps"][0]["layers"][0]["refuted"].append({"repo": repository,
            "facts": {"vote": "not_refuted"}, "fit": {"vote": "refuted"}})
        write_json(path, ledger)
        done = self.build("--contract-version", "2")
        self.assertEqual(done.returncode, 0, done.stderr)
        row = json.loads((self.work / "inputs/alpha.json").read_text())
        field = {member["repository"]: member for member in row["eligible_field"]}
        self.assertIn(repository, field)
        self.assertIn("https://github.com/o/also-returned", field)
        self.assertEqual(field[repository]["candidate_key"],
                         "foundation/alpha/https://huggingface.co/xiaomimimo/mimo-v2.6-distill-qwen-9b")
        self.assertEqual(field[repository]["pending_reason"], "legacy_v1_refutation")
        self.assertTrue(field[repository]["material"])
        screen = json.loads((self.work / "inputs/alpha.fit-v2.json").read_text())
        model = next(candidate for candidate in screen["candidates"] if candidate["repository"] == repository)
        self.assertEqual(model["primary_sources"], [repository, repository + "/tree/main",
                         "https://huggingface.co/api/models/XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B"])

    def test_v2_requirement_keeps_capability_words_that_are_only_repository_owner_fragments(self):
        path = self.repo / "catalogs/landscape/foundation.json"
        catalog = json.loads(path.read_text())
        requirement = "Keep exact project knowledge retrievable across clients, with explicit project scope."
        catalog["layers"][0]["requirement"] = requirement
        catalog["layers"][0]["alternatives"].append({"name": "loopx-project/loopx",
            "repository": "https://github.com/loopx-project/loopx", "disposition": "not_adopted"})
        write_json(path, catalog)
        done = self.build("--contract-version", "2")
        self.assertEqual(done.returncode, 0, done.stderr)
        screen = json.loads((self.work / "inputs/alpha.fit-v2.json").read_text())
        self.assertEqual(screen["requirement"], requirement)

    def test_v2_field_catalog_provenance_resolves_to_the_recorded_member(self):
        done = self.build("--contract-version", "2")
        self.assertEqual(done.returncode, 0, done.stderr)
        layer = json.loads((self.work / "inputs/alpha.json").read_text())
        member = next(row for row in layer["eligible_field"] if row["repository"] == "https://github.com/sharkdp/bat")
        self.assertIn("catalogs/landscape/foundation.json#/layers/0/winners/0", member["evidence_refs"])

    def test_v2_field_includes_known_review_seed_and_all_historical_proposals(self):
        ledger_path = self.repo / "catalogs/saturation/ledger.json"
        ledger = json.loads(ledger_path.read_text())
        ledger["sweeps"].insert(0, {"sweep_id": "older", "status": "completed", "layers": [{
            "catalog": "foundation", "layer_id": "alpha", "proposed": ["o/fit-only", "o/over-cap"],
            "survived": [], "refuted": [{"repo": "o/fit-only", "facts": {"vote": "not_refuted"},
                                          "fit": {"vote": "refuted"}}]}]})
        ledger["sweeps"][-1]["layers"][0]["proposed"] = ["o/stopped"]
        write_json(ledger_path, ledger)
        write_json(self.repo / "catalogs/landscape/candidate-quality-review.json", {
            "candidates": [{"repository": "o/review", "disposition": "not_adopted"}],
            "layer_coverage": [{"catalog": "foundation", "layer_id": "alpha",
                                "challenger_repositories": ["o/review"]}]})
        write_json(self.repo / "evidence/artifacts/blind-catalog-convergence-20260921/claude-final-layers.json", [{
            "catalog": "foundation", "layer_id": "alpha", "selected": [{"repo": "o/second-family"}],
            "challengers": ["o/another (reviewed)"]}])
        seeds = write_json(self.work / "seeds.json", {"alpha": [f"o/seed-{n}" for n in range(9)] + ["note only"]})
        done = self.build("--contract-version", "2", "--seeds", seeds)
        self.assertEqual(done.returncode, 0, done.stderr)
        row = json.loads((self.work / "inputs/alpha.json").read_text())
        field = {member["repository"]: member for member in row["eligible_field"]}
        expected = {"sharkdp/bat", "cli/cli", "tauri-apps/tauri", "facebook/react", "o/s", "o/r",
                    "o/fit-only", "o/over-cap", "o/stopped", "o/review", "o/second-family", "o/another"}
        expected |= {f"o/seed-{n}" for n in range(9)}
        self.assertEqual(set(field), {f"https://github.com/{repo}" for repo in expected})
        self.assertEqual(row["contract_version"], 2)
        self.assertEqual(field["https://github.com/o/fit-only"]["pending_reason"], "legacy_v1_refutation")
        self.assertEqual(field["https://github.com/sharkdp/bat"]["disposition"], "admit_pending")
        self.assertTrue(all(member["material"] for member in field.values()))
        self.assertTrue(all(member["evidence_refs"] for member in field.values()))
        self.assertEqual(field["https://github.com/o/fit-only"]["candidate_key"], "foundation/alpha/o/fit-only")
        self.assertEqual(field["https://github.com/o/fit-only"]["evidence_key"], "foundation/alpha/o/fit-only")
        self.assertIn("o/fit-only", row["known_repositories"])
        layers = json.loads((self.work / "layers.json").read_text())
        self.assertEqual(layers[0]["contract_version"], 2)
        self.assertEqual(layers[0]["field_sha256"], row["field_sha256"])

    def test_v2_blind_input_carries_only_readable_target_requirements_and_separate_hash(self):
        profiles = [
            {"id": "macos-arm64", "os": "macos", "architecture": "arm64", "status": "ADOPTION_STATUS_MARKER",
             "pins": {"tool": "PIN_MARKER"}, "doc": "DOC_MARKER", "evidence_ref": "RECEIPT_MARKER"},
            {"id": "linux-wsl2-x86_64", "os": "linux", "architecture": "x86_64",
             "bootstrap_script": "BOOTSTRAP_MARKER", "hosted_smoke": {"result": "HISTORY_MARKER"}},
        ]
        write_json(self.repo / "adoption/manifest.json", {"platform_profiles": profiles})
        scope = json.loads((self.work / "scope.json").read_text())
        scope["platform_profiles_sha256"] = hashlib.sha256(
            json.dumps(profiles, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        write_json(self.work / "scope.json", scope)
        self.assertEqual(self.build().returncode, 0)
        legacy = (self.work / "inputs/alpha.json").read_bytes()
        done = self.build("--contract-version", "2")
        self.assertEqual(done.returncode, 0, done.stderr)
        expected = [{"id": "linux-wsl2-x86_64", "os": "linux", "architecture": "x86_64"},
                    {"id": "macos-arm64", "os": "macos", "architecture": "arm64"}]
        digest = hashlib.sha256(json.dumps(expected, sort_keys=True, separators=(",", ":"),
                                          ensure_ascii=False).encode()).hexdigest()
        for name in ("alpha.json", "alpha.fit-v2.json", "beta.json", "beta.fit-v2.json"):
            value = json.loads((self.work / "inputs" / name).read_text())
            self.assertEqual(value.get("platform_requirements"), expected)
            self.assertEqual(value.get("platform_requirements_sha256"), digest)
            self.assertEqual(value["platform_profiles_sha256"], scope["platform_profiles_sha256"])
            text = json.dumps(value)
            for marker in ("ADOPTION_STATUS_MARKER", "PIN_MARKER", "DOC_MARKER", "RECEIPT_MARKER",
                           "BOOTSTRAP_MARKER", "HISTORY_MARKER"):
                self.assertNotIn(marker, text)
        self.assertEqual(self.build().returncode, 0)
        self.assertEqual((self.work / "inputs/alpha.json").read_bytes(), legacy)
        self.assertEqual(json.loads((self.repo / "adoption/manifest.json").read_text())["platform_profiles"], profiles)

    def test_v2_rejects_changed_or_unreadable_platform_scope_before_writing_inputs(self):
        for problem in ("changed_scope", "missing_architecture", "duplicate_profile_id"):
            with self.subTest(problem=problem):
                profiles = [{"id": "linux", "os": "linux", "architecture": "x86_64"}]
                if problem == "missing_architecture":
                    profiles[0].pop("architecture")
                elif problem == "duplicate_profile_id":
                    profiles.append({"id": "linux", "os": "linux", "architecture": "arm64"})
                write_json(self.repo / "adoption/manifest.json", {"platform_profiles": profiles})
                if problem != "changed_scope":
                    scope = json.loads((self.work / "scope.json").read_text())
                    scope["platform_profiles_sha256"] = hashlib.sha256(json.dumps(
                        profiles, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
                    write_json(self.work / "scope.json", scope)
                done = self.build("--contract-version", "2")
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertIn("platform", done.stderr)
                self.assertFalse((self.work / "inputs").exists())
                self.assertFalse((self.work / "layers.json").exists())

    def test_v2_offline_fit_input_withholds_origin_facts_and_keeps_equal_primary_sources(self):
        path = self.repo / "catalogs/landscape/foundation.json"
        catalog = json.loads(path.read_text())
        catalog["layers"][0]["requirement"] = "bat must render exact output. The current winner bat stays selected."
        catalog["layers"][0]["winners"][0]["why_selected"] = "ADOPTION_ONLY_MARKER"
        catalog["layers"][0]["alternatives"][0]["why_not_default"] = "INCUMBENT_ONLY_MARKER"
        write_json(path, catalog)
        freshness = json.loads(self.freshness.read_text())
        freshness["foundation"][0]["components"][0]["upstream"]["archived"] = True
        write_json(self.freshness, freshness)
        env = self.upstream_fixture()
        with mock.patch.dict(os.environ, env):
            done = self.build("--contract-version", "2")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse(Path(env["FACTS_CALLS"]).exists(), "offline V2 must not query either upstream transport")
        self.assertEqual(json.loads((self.work / "upstream-facts-v2.json").read_text())["mode"], "not_requested")
        screen_path = self.work / "inputs/alpha.fit-v2.json"
        self.assertTrue(screen_path.is_file(), "V2 fit must have its own blind input")
        text = screen_path.read_text()
        screen = json.loads(text)
        self.assertEqual(screen["requirement"], "<candidate> must render exact output.")
        for signal in ("winners", "alternatives", "why_selected", "why_not_default", "ADOPTION_ONLY_MARKER",
                       "INCUMBENT_ONLY_MARKER", "legacy_v1_refutation", "admit_pending", "pin_behind_upstream"):
            self.assertNotIn(signal, text)
        source = json.loads((self.work / "inputs/alpha.json").read_text())
        self.assertEqual(screen["field_sha256"], source["field_sha256"])
        self.assertEqual({row["candidate_key"] for row in screen["candidates"]},
                         {row["candidate_key"] for row in source["eligible_field"]})
        for candidate in screen["candidates"]:
            self.assertEqual(candidate["primary_sources"], [candidate["repository"],
                             candidate["repository"] + "/releases", candidate["repository"] + "/commits"])
            self.assertTrue(all(value is None for value in candidate["upstream_now"].values()))
            self.assertNotIn("stars", candidate["upstream_now"])
            self.assertNotIn("license", candidate["upstream_now"])
            self.assertEqual(candidate["upstream_observation"]["status"], "pending")
            self.assertEqual(candidate["upstream_observation"]["pending_reason"], "not_requested")
        bat = next(row for row in screen["candidates"] if row["repository"] == "https://github.com/sharkdp/bat")
        self.assertIsNone(bat["upstream_now"]["latest_release"])
        self.assertIsNone(bat["upstream_now"]["archived"])
        health_member = next(row for row in source["eligible_field"] if row["candidate_key"] == bat["candidate_key"])
        self.assertEqual(health_member["disposition"], "admit_pending")
        self.assertTrue(health_member["material"])
        self.assertIsNone(health_member["exclusion_reason"])
        self.assertNotIn("pin", bat)
        self.assertTrue(all(row["requirement_fit"] is None for row in screen["candidates"]))
        layers = json.loads((self.work / "layers.json").read_text())
        self.assertEqual(layers[0]["fit_input"], str(screen_path))

    def upstream_fixture(self, failure="", malformed=""):
        """Synthetic API returns through the public CLI's existing native gh/urllib transports."""
        fixtures = temp_dir(self)
        gh = fixtures / "gh"
        gh.write_text(f"#!{sys.executable}\n" + '''import json, os, sys
from pathlib import Path
path = sys.argv[2]
with Path(os.environ["FACTS_CALLS"]).open("a") as log:
    log.write(path + "\\n")
if path == os.environ.get("FACTS_FAILURE"):
    print("synthetic API unavailable; PRIVATE_ERROR_MARKER", file=sys.stderr)
    sys.exit(1)
if path == os.environ.get("FACTS_MALFORMED"):
    print('["wrong response shape"]')
    sys.exit(0)
if path.endswith("/releases/latest"):
    value = {"tag_name": "v-live", "published_at": "2026-09-30T10:00:00Z"}
elif path.endswith("/commits?per_page=1"):
    value = [{"sha": "c" * 40, "commit": {"committer": {"date": "2026-09-29T10:00:00Z"}}}]
else:
    value = {"default_branch": "main", "archived": False, "disabled": False,
             "pushed_at": "2026-09-30T11:00:00Z", "stargazers_count": 999,
             "license": {"spdx_id": "LICENSE_ONLY_MARKER"}}
print(json.dumps(value))
''', encoding="utf-8")
        gh.chmod(0o755)
        # No network is used: urllib sees fixed public model-info responses, and any unexpected path fails closed.
        (fixtures / "sitecustomize.py").write_text('''import io, json, os, urllib.error, urllib.request
from pathlib import Path
def urlopen(request, timeout=None):
    url = request.full_url
    with Path(os.environ["FACTS_CALLS"]).open("a") as log:
        log.write(url + "\\n")
    if url != "https://huggingface.co/api/models/Org/Model":
        raise urllib.error.URLError("synthetic model info unavailable")
    return io.BytesIO(json.dumps({"id": "Org/Model", "sha": "d" * 40,
        "lastModified": "2026-09-28T10:00:00Z", "disabled": False, "gated": "auto",
        "likes": 999, "cardData": {"license": "LICENSE_ONLY_MARKER"}}).encode())
urllib.request.urlopen = urlopen
''', encoding="utf-8")
        return {"PATH": str(fixtures) + os.pathsep + os.environ.get("PATH", ""),
                "PYTHONPATH": str(fixtures), "FACTS_CALLS": str(fixtures / "calls.txt"),
                "FACTS_FAILURE": failure, "FACTS_MALFORMED": malformed}

    def test_v2_pull_reuses_one_origin_neutral_snapshot_for_every_membership(self):
        beta_path = self.repo / "catalogs/landscape/us-equities.json"
        beta = json.loads(beta_path.read_text())
        beta["layers"][0]["candidates"] = [{"repository": "https://github.com/sharkdp/bat",
            "upstream_now": {"latest_release": "ORIGIN_ONLY_MARKER", "archived": True}}]
        write_json(beta_path, beta)
        env = self.upstream_fixture()
        with mock.patch.dict(os.environ, env):
            done = self.build("--contract-version", "2", "--pull-upstream-facts")
        self.assertEqual(done.returncode, 0, done.stderr)
        snapshot_path = self.work / "upstream-facts-v2.json"
        snapshot = json.loads(snapshot_path.read_text())
        self.assertEqual(snapshot["mode"], "api_pull")
        observations = snapshot["repositories"]
        calls = Path(env["FACTS_CALLS"]).read_text().splitlines()
        expected = [f"repos/{url.removeprefix('https://github.com/')}" + suffix
                    for url in sorted(observations)
                    for suffix in ("", "/commits?per_page=1", "/releases/latest")]
        self.assertEqual(calls, expected)  # exactly once, same path/order for adopted, catalog and sweep-only
        shared = []
        for layer in ("alpha", "beta"):
            screen = json.loads((self.work / f"inputs/{layer}.fit-v2.json").read_text())
            digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False,
                                               separators=(",", ":")).encode()).hexdigest()
            self.assertEqual(screen["upstream_facts_sha256"], digest)
            for candidate in screen["candidates"]:
                frozen = observations[candidate["repository"]]
                self.assertEqual(candidate["upstream_now"], frozen["upstream_now"])
                self.assertEqual(candidate["upstream_observation"], frozen["upstream_observation"])
                self.assertEqual(candidate["upstream_now"]["latest_release"], "v-live")
                self.assertIs(candidate["upstream_now"]["archived"], False)
                self.assertEqual(candidate["upstream_now"]["head_commit"], "c" * 40)
                self.assertEqual(candidate["upstream_now"]["head_committed_at"], "2026-09-29T10:00:00Z")
                self.assertEqual(candidate["upstream_observation"]["status"], "observed")
                self.assertIsNone(candidate["requirement_fit"])
                if candidate["repository"] == "https://github.com/sharkdp/bat":
                    shared.append(frozen)
            for signal in ("stars", "license", "LICENSE_ONLY_MARKER", "ORIGIN_ONLY_MARKER"):
                self.assertNotIn(signal, json.dumps(screen))
        self.assertEqual(len(shared), 2)
        self.assertEqual(shared[0], shared[1])
        release = {"tag_name": "v-live", "published_at": "2026-09-30T10:00:00Z"}
        release_source = observations["https://github.com/sharkdp/bat"]["upstream_observation"]["sources"][-1]
        self.assertEqual(release_source["url"], "https://api.github.com/repos/sharkdp/bat/releases/latest")
        self.assertEqual(release_source["response_json_sha256"], hashlib.sha256(
            json.dumps(release, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest())

    def test_v2_failed_api_facts_stay_unknown_pending_and_later_members_and_layers_continue(self):
        env = self.upstream_fixture(failure="repos/cli/cli")  # first repository in the sorted pull
        with mock.patch.dict(os.environ, env):
            done = self.build("--contract-version", "2", "--pull-upstream-facts")
        self.assertEqual(done.returncode, 0, done.stderr)
        alpha = json.loads((self.work / "inputs/alpha.fit-v2.json").read_text())
        failed = next(row for row in alpha["candidates"] if row["repository"] == "https://github.com/cli/cli")
        self.assertIsNone(failed["upstream_now"]["archived"])
        self.assertIsNone(failed["upstream_now"]["pushed_at"])
        self.assertEqual(failed["upstream_observation"]["status"], "pending")
        source = failed["upstream_observation"]["sources"][0]
        self.assertEqual(source["url"], "https://api.github.com/repos/cli/cli")
        self.assertEqual(source["status"], "pending")
        self.assertIsNone(source["response_json_sha256"])
        beta = json.loads((self.work / "inputs/beta.fit-v2.json").read_text())
        self.assertEqual(beta["candidates"][0]["upstream_observation"]["status"], "observed")
        self.assertEqual(beta["candidates"][0]["upstream_now"]["latest_release"], "v-live")
        owner = json.loads((self.work / "inputs/alpha.json").read_text())
        self.assertTrue(all(row["disposition"] == "admit_pending" for row in owner["eligible_field"]))
        self.assertNotIn("PRIVATE_ERROR_MARKER", (self.work / "upstream-facts-v2.json").read_text())

    def test_v2_malformed_api_payload_retains_its_hash_and_leaves_facts_pending(self):
        env = self.upstream_fixture(malformed="repos/cli/cli")
        with mock.patch.dict(os.environ, env):
            done = self.build("--contract-version", "2", "--pull-upstream-facts")
        self.assertEqual(done.returncode, 0, done.stderr)
        snapshot = json.loads((self.work / "upstream-facts-v2.json").read_text())
        failed = snapshot["repositories"]["https://github.com/cli/cli"]
        self.assertIsNone(failed["upstream_now"]["archived"])
        self.assertEqual(failed["upstream_observation"]["status"], "pending")
        source = failed["upstream_observation"]["sources"][0]
        self.assertEqual(source["status"], "pending")
        self.assertEqual(source["response_json_sha256"], hashlib.sha256(b'["wrong response shape"]').hexdigest())
        self.assertEqual(snapshot["repositories"]["https://github.com/sharkdp/bat"]["upstream_observation"]["status"],
                         "observed")

    def test_v2_hub_pull_keeps_host_unknowns_null_and_failure_does_not_abort(self):
        seeds = write_json(self.work / "seeds.json", {"alpha": ["https://huggingface.co/Org/Missing",
                                                               "https://huggingface.co/Org/Model"],
                                                   "beta": ["https://huggingface.co/org/model"]})
        env = self.upstream_fixture()
        with mock.patch.dict(os.environ, env):
            done = self.build("--contract-version", "2", "--pull-upstream-facts", "--seeds", seeds)
        self.assertEqual(done.returncode, 0, done.stderr)
        snapshot = json.loads((self.work / "upstream-facts-v2.json").read_text())
        model = snapshot["repositories"]["https://huggingface.co/Org/Model"]
        self.assertEqual(model["upstream_now"]["head_commit"], "d" * 40)
        self.assertEqual(model["upstream_now"]["last_modified"], "2026-09-28T10:00:00Z")
        self.assertEqual(model["upstream_now"]["gated"], "auto")
        self.assertEqual(snapshot["repositories"]["https://huggingface.co/org/model"], model)
        for key in ("archived", "latest_release", "released_at", "head_committed_at"):
            self.assertIsNone(model["upstream_now"][key])
        missing = snapshot["repositories"]["https://huggingface.co/Org/Missing"]
        self.assertTrue(all(value is None for value in missing["upstream_now"].values()))
        self.assertEqual(missing["upstream_observation"]["status"], "pending")
        calls = Path(env["FACTS_CALLS"]).read_text().splitlines()
        self.assertEqual(calls.count("https://huggingface.co/api/models/Org/Model"), 1)

    def test_upstream_pull_requires_explicit_v2_repository_mode(self):
        done = self.build("--pull-upstream-facts")
        self.assertEqual(done.returncode, 2)
        self.assertIn("--contract-version 2", done.stderr)
        self.assertFalse((self.work / "inputs").exists())

    def test_acceptance_summaries_pin_the_exact_reviewed_plan_sections(self):
        # Full source revision 798ac445307e2cd8eba6e74d7722ac0e16da02c7; bytes from each heading through
        # the byte before the next section heading (the last range runs to EOF). These are summaries, not extracts.
        plan = (ROOT / "blueprints/us-equities/engine-nautilus/acceptance-plan.md").read_bytes()
        hashes = {
            "retained-equity-replay": (1, 3, "a79c33c07f9de52bb7270fb9e6e0e85a19c1064da9ad47f9d7cc92ff362f0a0f"),
            "broker-state-failures": (4, 4, "1f557403dc4169db578cd2a327f025ac3acee25c78b333dfc91906d83ff421c3"),
            "separate-paper-adapters": (5, 6, "e5921c5afa6d5db25408549873127b5a07cd8690e2ca674b6ed508f22bb32ec9"),
        }
        self.assertEqual(set(hashes), set(build_inputs.ACCEPTANCE_REQUIREMENTS))
        for gate, (first, last, expected) in hashes.items():
            with self.subTest(gate=gate):
                start = re.search(rb"^## " + str(first).encode() + rb"\. ", plan, re.M)
                self.assertIsNotNone(start)
                following = re.search(rb"^## " + str(last + 1).encode() + rb"\. ", plan, re.M)
                section = plan[start.start():following.start() if following else len(plan)]
                self.assertEqual(hashlib.sha256(section).hexdigest(), expected,
                                 "Review the requirement summary against the changed acceptance-plan sections")

    def test_v2_pinned_requirements_and_declarative_gates_survive_without_executed_status(self):
        path = self.repo / "catalogs/landscape/us-equities.json"
        catalog = json.loads(path.read_text())
        catalog["layers"][0]["requirement"] = (
            "Use the selected NautilusTrader destination with IBKR and a separate Alpaca adapter; "
            "preserve the prior LEAN oracle and reconcile numeric accounting.")
        catalog["layers"][0]["candidates"] = [
            {"name": "NautilusTrader", "repository": "https://github.com/nautechsystems/nautilus_trader",
             "disposition": "selected"},
            {"name": "LEAN", "repository": "https://github.com/QuantConnect/Lean", "disposition": "not_adopted"}]
        write_json(path, catalog)
        write_json(self.repo / "catalogs/us-equities/runtime-target.json", {
            "engine": {"repository": "https://github.com/nautechsystems/nautilus_trader",
                       "decision": "selected_destination", "requested_version": "2.0.0rc5"},
            "acceptance_plan": "blueprints/us-equities/engine-nautilus/acceptance-plan.md",
            "next_acceptance": [{"id": "broker-state-failures", "status": "EXECUTED_ONLY_MARKER",
                                 "scope": "Installed incumbent already passed 27 checks.",
                                 "executed_evidence_ref": "incumbent-receipt.json"}]})
        done = self.build("--contract-version", "2")
        self.assertEqual(done.returncode, 0, done.stderr)
        text = (self.work / "inputs/beta.fit-v2.json").read_text()
        screen = json.loads(text)
        self.assertEqual(screen["requirement"], (
            "Use the user-pinned NautilusTrader destination with IBKR and a separate Alpaca adapter; "
            "preserve the fixed LEAN oracle and reconcile numeric accounting."))
        self.assertEqual({pin["name"] for pin in screen["pinned_requirements"]},
                         {"NautilusTrader", "IBKR", "Alpaca", "LEAN"})
        self.assertEqual(screen["acceptance_gates"][0]["id"], "broker-state-failures")
        self.assertIn("durable", screen["acceptance_gates"][0]["requirement"])
        for signal in ("EXECUTED_ONLY_MARKER", "executed_evidence_ref", "incumbent-receipt.json",
                       "already passed", "requested_version", "2.0.0rc5"):
            self.assertNotIn(signal, text)


class NeutralStagingTests(unittest.TestCase):
    def test_legacy_staging_refuses_v2_inputs_before_writing_a_launchable_runner(self):
        work = stage_work(self, layers=("alpha",))
        path = work / "inputs/alpha.json"
        layer = json.loads(path.read_text())
        write_json(path, dict(layer, contract_version=2, field_sha256="c" * 64))
        done = build(work)
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("V2", done.stderr)
        self.assertFalse((work / "args.json").exists())
        self.assertFalse((work / "sweep.embedded.js").exists())
        explicit = build(work, "--contract-version", "2")
        self.assertEqual(explicit.returncode, 2, explicit.stdout + explicit.stderr)
        self.assertIn("future V2 runner", explicit.stderr)
        self.assertFalse((work / "templates.json").exists())


# --------------------------------------------------------------------------- build_args


def stage_work(case, layers=("alpha", "beta", "gamma"), work=None):
    work = work or temp_dir(case)
    catalogs = {"alpha": "foundation", "beta": "us-equities", "gamma": "foundation"}
    rows = []
    for layer_id in layers:
        data = {"catalog": catalogs[layer_id], "layer_id": layer_id, "title": layer_id.title(),
                "requirement": f"{layer_id} req", "requirement_sha256": REQ, "platform_profiles_sha256": PLAT}
        path = write_json(work / "inputs" / f"{layer_id}.json", data)
        rows.append({"catalog": catalogs[layer_id], "layer_id": layer_id, "title": data["title"], "input": str(path)})
    write_json(work / "layers.json", rows)
    return work


def build(work, *extra):
    return run([sys.executable, HARNESS / "build_args.py", "--work-dir", work, "--sweep-id", "landscape-sweep-20261026",
                "--date", "2026-10-26", *extra])


class BuildArgsTests(unittest.TestCase):
    def test_args_are_compact_and_the_run_is_staged(self):
        work = stage_work(self)
        done = build(work)
        self.assertEqual(done.returncode, 0, done.stderr)
        summary = json.loads(done.stdout)
        args = json.loads((work / "args.json").read_text())
        self.assertEqual(sorted(args), ["S", "T", "layers", "schemas", "stars", "sweep_id"])
        self.assertEqual(args["S"], str(work))
        self.assertIsNone(args["stars"])
        self.assertEqual(args["layers"], [{"layer_id": "alpha", "catalog": "foundation"},
                                          {"layer_id": "beta", "catalog": "us-equities"},
                                          {"layer_id": "gamma", "catalog": "foundation"}])
        self.assertEqual(sorted(args["schemas"]), ["critic", "discover", "votes"])
        self.assertEqual(args["T"], filled_templates("2026-10-26", 3, json.loads(
            (ROOT / build_args.SKILLS_MANIFEST).read_text())["checked_at"]))
        self.assertLess(summary["args_bytes"], 16_000)  # templates and schemas only; layer inputs stay files
        self.assertEqual(summary["prompts_sha256"], sweep_common.prompts_sha256(args["T"]))
        self.assertEqual((work / "prompts_sha256.txt").read_text().strip(), summary["prompts_sha256"])
        self.assertEqual(json.loads((work / "templates.json").read_text()), args["T"])
        for layer_id in ("alpha", "beta", "gamma"):
            layer_input = json.loads((work / "inputs" / f"{layer_id}.json").read_text())
            self.assertEqual((work / "prompts" / f"gpt6-discover-{layer_id}.txt").read_text(),
                             make_prompt.compose(args["T"], "discover", layer_input) + "\n")
        self.assertEqual((work / "prompts/gpt6-probe.txt").read_text(), build_args.PROBE_PROMPT + "\n")
        for name in build_args.RUNTIME:
            self.assertEqual((work / name).read_bytes(), (HARNESS / name).read_bytes())
        self.assertTrue(os.stat(work / "codex_call.sh").st_mode & stat.S_IXUSR)
        probe = (ROOT / "scripts" / "codex_quota.py").read_bytes()
        self.assertEqual((work / "codex_quota.py").read_bytes(), probe)
        staged = json.loads((work / "staged.json").read_text())
        self.assertEqual(staged["codex"], {"model": "gpt-6-astra", "effort": "max", "slots": 3})  # no quota gate
        self.assertEqual(staged["harness"]["quota_probe"], {"path": "scripts/codex_quota.py",
                                                            "sha256": hashlib.sha256(probe).hexdigest()})
        self.assertEqual(staged["prompts_sha256"], summary["prompts_sha256"])
        self.assertEqual(staged["harness"]["files"]["sweep.js"],
                         hashlib.sha256((HARNESS / "sweep.js").read_bytes()).hexdigest())

    def test_embedded_copy_replaces_the_single_args_line(self):
        work = stage_work(self)
        self.assertEqual(build(work).returncode, 0)
        source = (HARNESS / "sweep.js").read_text()
        self.assertEqual(source.count("\nconst A = args\n"), 1)
        embedded = (work / "sweep.embedded.js").read_text()
        self.assertNotIn("const A = args\n", embedded)
        old_lines, new_lines = source.split("\n"), embedded.split("\n")
        self.assertEqual(len(old_lines), len(new_lines))
        changed = [i for i, (a, b) in enumerate(zip(old_lines, new_lines)) if a != b]
        self.assertEqual(len(changed), 1)
        line = new_lines[changed[0]]
        self.assertTrue(line.startswith("const A = {"))
        self.assertTrue(line.isascii())
        self.assertEqual(json.loads(line[len("const A = "):]), json.loads((work / "args.json").read_text()))
        with self.assertRaisesRegex(ValueError, "exactly one"):
            build_args.embed(source + "\nconst A = args\n", {})

    def test_smoke_due_report_and_explicit_layer_selection(self):
        work = stage_work(self)
        self.assertEqual(build(work, "--smoke", "beta").returncode, 0)
        args = json.loads((work / "args.json").read_text())
        self.assertEqual((args["layers"], args.get("test")), ([{"layer_id": "beta", "catalog": "us-equities"}], True))
        self.assertIn("a 1-layer saturation sweep", args["T"]["critic"])
        work = stage_work(self)
        report = write_json(work / "report.json", {"layers": [
            {"catalog": "foundation", "layer_id": "alpha", "due": False},
            {"catalog": "us-equities", "layer_id": "beta", "due": True},
            {"catalog": "foundation", "layer_id": "gamma", "due": True}]})
        self.assertEqual(build(work, "--due-report", report).returncode, 0)
        self.assertEqual([x["layer_id"] for x in json.loads((work / "args.json").read_text())["layers"]], ["beta", "gamma"])
        work = stage_work(self)
        self.assertEqual(build(work, "--layers", "gamma,alpha").returncode, 0)
        self.assertEqual([x["layer_id"] for x in json.loads((work / "args.json").read_text())["layers"]], ["gamma", "alpha"])
        done = build(stage_work(self), "--layers", "alpha,zeta")
        self.assertEqual(done.returncode, 2)
        self.assertIn("zeta", done.stderr)

    def test_refusals(self):
        work = stage_work(self)
        (work / "gpt6" / "gpt6-discover-alpha").mkdir(parents=True)
        done = build(work)
        self.assertEqual(done.returncode, 2)
        self.assertIn("already holds 1 job", done.stderr)
        self.assertEqual(build(work, "--force").returncode, 0)
        repo = temp_dir(self)
        (repo / ".git").mkdir()
        (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        inside = repo / "sweep"
        inside.mkdir()
        done = run([sys.executable, HARNESS / "build_args.py", "--work-dir", inside, "--sweep-id", "s", "--date",
                    "2026-10-26"])
        self.assertEqual(done.returncode, 2)
        self.assertIn("inside the git repository", done.stderr)
        newline = temp_dir(self) / "line\nbreak"
        newline.mkdir()
        done = build(stage_work(self, ("alpha",), work=newline))
        self.assertEqual(done.returncode, 2)
        self.assertIn("control character", done.stderr)


# --------------------------------------------------------------------------- the GPT-6 runner

FAKE_CODEX = """#!{python}
import json, os, sys, time
if sys.argv[1:] == ["--version"]:
    print("codex-cli 0.0.0-fixture")
    sys.exit(0)
if sys.argv[1:] == ["-c", 'sandbox_mode="read-only"', "app-server"]:  # the quota probe: initialize, initialized, account/rateLimits/read
    quota = json.load(open(os.environ["FAKE_CODEX_CONFIG"])).get("quota") or {{}}
    if quota.get("log"):
        with open(quota["log"], "a") as log:
            log.write("probe\\n")
    for line in sys.stdin:
        msg = json.loads(line)
        if msg.get("method") == "initialize":
            print(json.dumps({{"id": msg["id"], "result": {{"userAgent": "fixture"}}}}), flush=True)
        elif msg.get("method") == "account/rateLimits/read":
            key = "error" if "error" in quota else "result"
            print(json.dumps({{"id": msg["id"], key: quota.get(key)}}), flush=True)
    sys.exit(0)
config = json.load(open(os.environ["FAKE_CODEX_CONFIG"]))
if config.get("attempts"):
    counter = config["attempt_counter"]
    attempt = int(open(counter).read()) if os.path.exists(counter) else 0
    with open(counter, "w") as out:
        out.write(str(attempt + 1))
    config.update(config["attempts"][min(attempt, len(config["attempts"]) - 1)])
stdin, null = os.fstat(0), os.stat(os.devnull)
record = {{"argv": sys.argv[1:], "cwd": os.getcwd(), "stdin_devnull": (stdin.st_ino, stdin.st_dev) == (null.st_ino, null.st_dev),
          "stdin_read": sys.stdin.read(), "rust_log": os.environ.get("RUST_LOG"),
          "codex_home": os.environ.get("CODEX_HOME"), "api_key_present": bool(os.environ.get("OMNIROUTE_API_KEY"))}}
if config.get("stubborn"):
    import subprocess
    subprocess.Popen([sys.executable, "-c", "import os, signal, sys, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                      "open(sys.argv[1] + '.tmp', 'w').write(str(os.getpid())); os.replace(sys.argv[1] + '.tmp', sys.argv[1]); "
                      "time.sleep(120)", config["stubborn"]])
    while not os.path.exists(config["stubborn"]):
        time.sleep(0.02)
if config.get("log"):
    with open(config["log"], "a") as log:
        log.write("start %.6f\\n" % time.time())
for tick in config.get("ticks", []):
    time.sleep(tick.get("delay_s", 0))
    if "event" in tick:
        print(json.dumps(tick["event"]), flush=True)
    if "raw" in tick:
        sys.stdout.write(tick["raw"])
        sys.stdout.flush()
    if "stderr" in tick:
        sys.stderr.write(tick["stderr"])
        sys.stderr.flush()
time.sleep(config.get("sleep", 0))
for event in config.get("events", []):
    print(json.dumps(event))
sys.stdout.flush()
# Upstream exec emits completion, shuts down, then writes -o (rust-v0.159.2,
# codex-rs/exec/src/lib.rs:1318-1321; event_processor_with_jsonl_output.rs:631-636).
time.sleep(config.get("output_delay_s", 0))
if config.get("last") is not None:
    with open(sys.argv[sys.argv.index("-o") + 1], "w") as out:
        json.dump(config["last"], out, indent=2)
if "last_text" in config:
    with open(sys.argv[sys.argv.index("-o") + 1], "w") as out:
        out.write(config["last_text"])
sys.stderr.write(config.get("stderr", ""))
if config.get("record"):
    with open(config["record"], "w") as out:
        json.dump(record, out)
if config.get("log"):
    with open(config["log"], "a") as log:
        log.write("end %.6f\\n" % time.time())
sys.exit(config.get("exit", 0))
"""


def process_alive(pid: int) -> bool:
    """True while pid runs; a zombie (exited, not yet reaped by its new parent) counts as gone."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(state) and not state.startswith("Z")


STACK_WORKER_FIXTURE = """model = "gpt-6-astra"
model_reasoning_effort = "max"
web_search = "live"

[mcp_servers.context-mode]
disabled_tools = ["ctx_upgrade", "ctx_purge"]
"""
TOKEN_MCP_SERVERS = ("serena", "ai-memory", "socraticode", "headroom", "codebase-memory", "qmd", "context-mode")


class OmniRouteFallbackBuildTests(unittest.TestCase):
    def test_fallback_is_opt_in_and_restaging_keeps_frozen_prompts(self):
        work = stage_work(self)
        first = build(work)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertNotIn("fallback", json.loads((work / "staged.json").read_text())["codex"])
        frozen = {name: (work / name).read_bytes() for name in
                  ("prompts_sha256.txt", "templates.json", "args.json", "sweep.embedded.js")}
        (work / "gpt6" / "earlier-job").mkdir()
        fallback = build(work, "--force", "--gpt6-fallback", "omniroute", "--fallback-codex-host", "127.0.0.1:20128")
        self.assertEqual(fallback.returncode, 0, fallback.stderr)
        settings = codex_job.settings(work)
        self.assertEqual(settings["fallback"], {"provider": "omniroute", "base_url": "http://127.0.0.1:20128/v1"})
        self.assertEqual((settings["provider"], settings["model"], settings["effort"]), ("native", "gpt-6-astra", "max"))
        self.assertFalse((work / "codex-home").exists())
        for name, original in frozen.items():
            self.assertEqual((work / name).read_bytes(), original, name)
        profile = temp_dir(self) / "stack-worker.config.toml"
        profile.write_text(STACK_WORKER_FIXTURE, encoding="utf-8")
        gateway = build(work, "--force", "--gpt6-provider", "omniroute", "--codex-host", "example",
                        "--stack-worker-profile", profile)
        self.assertEqual(gateway.returncode, 0, gateway.stderr)
        self.assertNotIn("fallback", json.loads((work / "staged.json").read_text())["codex"])
        for name, original in frozen.items():
            self.assertEqual((work / name).read_bytes(), original, name)

    def test_invalid_fallback_stages_nothing(self):
        for extra in (("--fallback-codex-host", "127.0.0.1:20128"),
                      ("--gpt6-fallback", "omniroute", "--fallback-codex-host", "example.org:20128"),
                      ("--gpt6-fallback", "omniroute", "--fallback-codex-host", "127.0.0.1:0"),
                      ("--gpt6-fallback", "omniroute", "--fallback-codex-host", "127.0.0.1:65536"),
                      ("--gpt6-fallback", "omniroute", "--gpt6-provider", "omniroute"),
                      ("--gpt6-fallback", "omniroute", "--gpt6-model", "cx/gpt-6-astra")):
            with self.subTest(extra=extra):
                work = stage_work(self)
                done = build(work, *extra)
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertFalse((work / "staged.json").exists())
                self.assertFalse((work / "codex-home").exists())


class OmniRouteLaneBuildTests(unittest.TestCase):
    """--gpt6-provider omniroute stages a lane-local CODEX_HOME: the provider block, the rendered token MCP servers
    and the stack-worker profile, and nothing of the host's interactive trust state."""

    def stage_lane(self, *extra):
        work = stage_work(self)
        profile = temp_dir(self) / "stack-worker.config.toml"
        profile.write_text(STACK_WORKER_FIXTURE, encoding="utf-8")
        return work, profile, build(work, "--gpt6-provider", "omniroute", "--codex-host", "example",
                                    "--stack-worker-profile", profile, *extra)

    def test_lane_home_carries_provider_mcp_servers_and_profile(self):
        work, profile, done = self.stage_lane()
        self.assertEqual(done.returncode, 0, done.stderr)
        config = (work / "codex-home" / "config.toml").read_text(encoding="utf-8")
        for line in ('model = "cx/gpt-6-astra"', 'model_provider = "omniroute"', 'model_reasoning_effort = "max"',
                     "[model_providers.omniroute]", 'base_url = "http://127.0.0.1:20128/v1"',
                     'env_key = "OMNIROUTE_API_KEY"', "requires_openai_auth = false", 'wire_api = "responses"'):
            self.assertIn(line, config)
        for server in TOKEN_MCP_SERVERS:
            self.assertIn(f"[mcp_servers.{server}]", config)
        self.assertNotIn("supports_websockets = true", config)
        self.assertNotIn("http_headers", config)  # the 20128 default sends no provider headers
        # The key never reaches a shell snapshot file, and GPT-6 Astra's search is Codex's standalone web.run.
        for line in ("[features]", "shell_snapshot = false", "standalone_web_search = true",
                     "supports_standalone_web_search = true"):
            self.assertIn(line, config)
        self.assertNotIn("[projects.", config)
        self.assertNotIn("[hooks.state", config)
        self.assertNotIn("${", config)  # every template placeholder rendered
        self.assertEqual((work / "codex-home" / "stack-worker.config.toml").read_bytes(), profile.read_bytes())
        try:
            import tomllib
        except ImportError:
            tomllib = None
        if tomllib is not None:
            parsed = tomllib.loads(config)
            self.assertEqual(parsed["model_providers"]["omniroute"]["env_key"], "OMNIROUTE_API_KEY")
            self.assertIs(parsed["model_providers"]["omniroute"]["supports_standalone_web_search"], True)
            self.assertEqual(parsed["features"], {"shell_snapshot": False, "standalone_web_search": True})
            # Codex 0.157.1 leaves its default *KEY* excludes off, so the key variable is excluded by name.
            self.assertEqual(parsed["shell_environment_policy"], {"filters": {"OMNIROUTE_API_KEY": "exclude"}})
            self.assertEqual(sorted(parsed["mcp_servers"]), sorted(TOKEN_MCP_SERVERS))
        codex = json.loads((work / "staged.json").read_text())["codex"]
        self.assertEqual((codex["provider"], codex["codex_home"], codex["profile"], codex["api_key_env"],
                          codex["model"], codex["effort"]),
                         ("omniroute", "codex-home", "stack-worker", "OMNIROUTE_API_KEY", "cx/gpt-6-astra", "max"))
        self.assertEqual(sorted(codex["lane_home"]["mcp_servers"]), sorted(TOKEN_MCP_SERVERS))
        self.assertNotIn("quota_stop_percent", codex)
        self.assertEqual(codex["api_key_placeholder"], "local-loopback")  # keyless loopback gateway by default
        self.assertNotIn("local-loopback", config)  # the placeholder is runtime-only, never in the lane config
        self.assertEqual(codex["http_headers"], {})
        # The staged runner reads the same settings back.
        lane = codex_job.settings(work)
        self.assertEqual((lane["provider"], lane["codex_home"], lane["profile"], lane["http_headers"]),
                         ("omniroute", work / "codex-home", "stack-worker", {}))

    def test_builder_and_runner_keep_the_name_patterns_equal(self):
        # build_args.py checks what it stages and codex_job.py what it runs; the two copies must never drift.
        for name in ("MODEL_NAME", "HEADER_VALUE"):
            self.assertEqual(getattr(build_args, name).pattern, getattr(codex_job, name).pattern, name)
        self.assertEqual(build_args.OMNIROUTE_REQUEST_HEADERS, codex_job.OMNIROUTE_REQUEST_HEADERS)
        # Codex strips one namespace for metadata lookup, and only one of [A-Za-z0-9_-]+ (openai/codex rust-v0.157.1,
        # codex-rs/models-manager/src/manager.rs L763-780); 20129 therefore needs a one-slash route.
        for module in (build_args, codex_job):
            for model in ("gpt-6-astra", "cx/gpt-6-astra", "sharedgw/gpt-6-astra-max", "gpt-6-astra-max",
                          "my_gw/gpt-6.1", "my-gw/gpt-6-astra"):
                self.assertTrue(module.MODEL_NAME.fullmatch(model), (module.__name__, model))
            for model in ("sharedgw/cx/gpt-6-astra", "a/sharedgw/cx/gpt-6-astra", "/gpt-6-astra",
                          "cx//gpt-6-astra", "cx/", "cx/gpt 6", "", "my.gw/gpt-6-astra-max"):
                self.assertIsNone(module.MODEL_NAME.fullmatch(model), (module.__name__, model))

    def test_two_slash_model_is_refused_by_builder_and_runner(self):
        # Supplied 2026-09-27 gateway finding, pinned to openai/codex rust-v0.157.1 manager.rs L763-780: Codex strips
        # one namespace, and only one of letters, digits, '_' and '-', so a second slash or any other namespace gets
        # fallback metadata even if the gateway can route the request. Both entry points refuse before writing.
        prompt = temp_dir(self) / "prompt.txt"
        prompt.write_text("Reply in JSON.\n", encoding="utf-8")
        for model in ("sharedgw/cx/gpt-6-astra", "my.gw/gpt-6-astra-max"):
            with self.subTest(entrypoint="build_args.py", model=model):
                work, _, done = self.stage_lane("--omniroute-base-url", "http://127.0.0.1:20129/v1",
                                                "--gpt6-model", model)
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertIn("fallback metadata", done.stderr)
                self.assertIn("manager.rs L763-780", done.stderr)
                self.assertFalse((work / "codex-home").exists())
                self.assertFalse((work / "staged.json").exists())
            with self.subTest(entrypoint="codex_call.sh start", model=model):
                work, _, done = self.stage_lane("--omniroute-base-url", "http://127.0.0.1:20129/v1",
                                                "--gpt6-model", "sharedgw/gpt-6-astra-max")
                self.assertEqual(done.returncode, 0, done.stderr)
                staged = json.loads((work / "staged.json").read_text())
                staged["codex"]["model"] = model
                write_json(work / "staged.json", staged)
                jobs_before = sorted((work / "gpt6").iterdir())  # stage() creates this directory before any job
                started = run(["bash", HARNESS / "codex_call.sh", "--work-dir", work, "start", "gpt6-probe", prompt,
                               HARNESS / "schemas" / "probe.json"])
                self.assertEqual(started.returncode, 2, started.stdout + started.stderr)
                self.assertIn("fallback metadata", started.stderr)
                self.assertIn("manager.rs L763-780", started.stderr)
                self.assertEqual(sorted((work / "gpt6").iterdir()), jobs_before)

    def test_framework_instance_lane_stages_static_provider_headers(self):
        # Codex 0.157.1 adds model_providers.<id>.http_headers to every request to that provider
        # (codex-rs/model-provider-info/src/lib.rs:166-168 and 385-412 at rust-v0.157.1).
        work, _, done = self.stage_lane("--omniroute-base-url", "http://127.0.0.1:20129/v1",
                                        "--gpt6-model", "sharedgw/gpt-6-astra-max",
                                        "--omniroute-header", "x-omniroute-compression=allow-lossy",
                                        "--omniroute-header", "X-OmniRoute-No-Memory=1")
        self.assertEqual(done.returncode, 0, done.stderr)
        headers = {"x-omniroute-compression": "allow-lossy", "x-omniroute-no-memory": "1"}
        config = (work / "codex-home" / "config.toml").read_text(encoding="utf-8")
        for line in ('model = "sharedgw/gpt-6-astra-max"', 'base_url = "http://127.0.0.1:20129/v1"',
                     'http_headers = { "x-omniroute-compression" = "allow-lossy", "x-omniroute-no-memory" = "1" }'):
            self.assertIn(line, config)
        if sys.version_info >= (3, 11):
            import tomllib
            provider = tomllib.loads(config)["model_providers"]["omniroute"]
            self.assertEqual(provider["http_headers"], headers)
            self.assertNotIn("env_http_headers", provider)
        codex = json.loads((work / "staged.json").read_text())["codex"]
        self.assertEqual((codex["model"], codex["base_url"], codex["http_headers"]),
                         ("sharedgw/gpt-6-astra-max", "http://127.0.0.1:20129/v1", headers))
        lane = codex_job.settings(work)
        self.assertEqual((lane["model"], lane["http_headers"]), ("sharedgw/gpt-6-astra-max", headers))

    def test_omniroute_headers_take_only_listed_request_switches_and_plain_values(self):
        # Only OmniRoute 3.8.51's per-request switches can be staged. Other x-omniroute-* headers carry secrets under
        # names without a credential word, such as x-omniroute-self-hop (open-sse/utils/selfHop.ts:1-12) and
        # x-omniroute-video-bridge-broker (src/lib/guardrails/videoBridgeBrokerAuth.ts:7-33).
        self.assertEqual(build_args.omniroute_headers([]), {})
        self.assertEqual(build_args.omniroute_headers(["X-OmniRoute-Compression=engine:caveman",
                                                       "x-omniroute-no-memory=1", "x-omniroute-no-cache=true",
                                                       "x-omniroute-strip-reasoning=yes"]),
                         {"x-omniroute-compression": "engine:caveman", "x-omniroute-no-cache": "true",
                          "x-omniroute-no-memory": "1", "x-omniroute-strip-reasoning": "yes"})
        refused = [(["x-omniroute-compression"], "NAME=VALUE"),
                   (["x-omniroute-compression=off", "X-OmniRoute-Compression=default"], "more than once")]
        refused += [([f"x-omniroute-compression={value}"], "printable ASCII")
                    for value in ("", 'a"b', "a\\b", "é", " off", "off ", "a\tb", "a" * 129)]
        refused += [([f"{name}=1"], "per-request switches") for name in (
            "x-omniroute-self-hop", "x-omniroute-video-bridge-broker", "x-omniroute-lease-owner",
            "x-omniroute-session-id", "x-omniroute-cli-token", "x-omniroute-ws-bridge-secret",
            "x-omniroute-feed-signature", "authorization", "x-other", "x-omniroute-", "x-omniroute-a b")]
        for specs, needle in refused:
            with self.assertRaisesRegex(ValueError, re.escape(needle), msg=specs):
                build_args.omniroute_headers(specs)
        self.assertEqual(build_args.omniroute_headers(["x-omniroute-compression=" + "a" * 128]),
                         {"x-omniroute-compression": "a" * 128})

    def test_omniroute_header_refusals_stage_nothing(self):
        work, _, done = self.stage_lane("--omniroute-header", "x-omniroute-self-hop=abc")
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("per-request switches", done.stderr)
        self.assertNotIn("abc", done.stderr)  # a refused value is never echoed
        self.assertNotIn("self-hop", done.stderr)  # nor a refused name
        self.assertFalse((work / "codex-home").exists())
        self.assertFalse((work / "staged.json").exists())
        work = stage_work(self)
        done = build(work, "--omniroute-header", "x-omniroute-compression=allow-lossy")
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("--gpt6-provider omniroute", done.stderr)
        self.assertFalse((work / "staged.json").exists())

    def stage_lane_with_skills(self):
        """Stage the lane with HOME at a fake home: a skill with a reference file and a symlink cycle, a symlinked skill
        directory, a file outside the skills root, and a file whose name holds a glob character."""
        home = temp_dir(self)
        root = home / ".agents" / "skills"
        (root / "demo" / "references").mkdir(parents=True)
        (root / "demo" / "SKILL.md").write_text("# demo\n", encoding="utf-8")
        (root / "demo" / "references" / "notes.md").write_text("notes\n", encoding="utf-8")
        (root / "demo" / "odd*name.md").write_text("glob character\n", encoding="utf-8")
        (root / "demo" / "loop").symlink_to(root / "demo", target_is_directory=True)
        linked = temp_dir(self) / "linked-skill"
        linked.mkdir()
        (linked / "SKILL.md").write_text("# linked\n", encoding="utf-8")
        (root / "linked").symlink_to(linked, target_is_directory=True)
        (home / "outside.md").write_text("outside\n", encoding="utf-8")
        work = stage_work(self)
        profile = temp_dir(self) / "stack-worker.config.toml"
        profile.write_text(STACK_WORKER_FIXTURE, encoding="utf-8")
        env = {**os.environ, "HOME": str(home)}
        common = [sys.executable, HARNESS / "build_args.py", "--work-dir", work, "--sweep-id", "landscape-sweep-20261026",
                  "--date", "2026-10-26"]
        done = run([*common, "--gpt6-provider", "omniroute", "--codex-host", "example", "--stack-worker-profile", profile],
                   env=env)
        return home, work, done, lambda: run(common, env=env)

    def test_lane_allows_context_mode_exactly_the_skill_files(self):
        # context-mode 1.0.169 refuses ctx_execute_file paths outside the runner's cwd unless a Read(...) allow rule in
        # <cwd>/.claude/settings.json names them (#852); the lane's GPT-6 loads its pinned skills with that tool.
        home, work, done, restage_native = self.stage_lane_with_skills()
        self.assertEqual(done.returncode, 0, done.stderr)
        root = home / ".agents" / "skills"
        settings = json.loads((work / "empty" / ".claude" / "settings.json").read_text(encoding="utf-8"))
        # One exact rule per file, by the path Codex lists; the cycle is listed once and the glob-character file never.
        self.assertEqual(settings, {"permissions": {"allow": [
            f"Read({root / 'demo' / 'SKILL.md'})", f"Read({root / 'demo' / 'references' / 'notes.md'})",
            f"Read({root / 'linked' / 'SKILL.md'})"]}})
        staged = (work / "staged.json").read_text(encoding="utf-8")
        self.assertEqual(json.loads(staged)["codex"]["lane_home"]["context_mode_skill_reads"],
                         {"settings": "empty/.claude/settings.json", "root": "$HOME/.agents/skills", "exact_files": 3})
        self.assertNotIn(str(home), staged)  # the lane record keeps the host's paths out
        # Restaging the same work dir for the native lane, which has no context-mode, removes the rules.
        native = restage_native()
        self.assertEqual(native.returncode, 0, native.stderr)
        self.assertFalse((work / "empty" / ".claude").exists())
        self.assertTrue((work / "empty").is_dir())

    @unittest.skipUnless(NODE and os.environ.get("CONTEXT_MODE_SECURITY_JS")
                         and Path(os.environ.get("CONTEXT_MODE_SECURITY_JS", "")).is_file(),
                         "set CONTEXT_MODE_SECURITY_JS to an installed context-mode build/security.js")
    def test_context_mode_reads_only_the_listed_skill_files(self):
        """context-mode's own matcher on the staged file: listed files pass; a sibling, the outside file and ..
        traversals under the root do not. The control shows why the rules are exact: with a <root>/** rule, the
        traversal passes too, because context-mode also matches the raw path."""
        home, work, done, _ = self.stage_lane_with_skills()
        self.assertEqual(done.returncode, 0, done.stderr)
        root = home / ".agents" / "skills"
        script = (
            "const [url, project, root, home] = process.argv.slice(1);\n"
            "const m = await import(url);\n"
            "const allow = m.readToolPermissionPatterns('Read', 'allow', project, project + '/no-global-settings.json');\n"
            "const check = (rules, p) => m.evaluateProjectContainment(p, project, rules).allowed;\n"
            "const paths = {skill: root + '/demo/SKILL.md', reference: root + '/demo/references/notes.md',\n"
            "  linked: root + '/linked/SKILL.md', sibling: root + '/demo/other.md', outside: home + '/outside.md',\n"
            "  traversal: root + '/demo/../../../outside.md', shallow_traversal: root + '/../../outside.md'};\n"
            "const out = {};\n"
            "for (const [name, p] of Object.entries(paths)) out[name] = check(allow, p);\n"
            "out.control_wildcard_traversal = check([[root + '/**']], paths.traversal);\n"
            "console.log(JSON.stringify(out));\n")
        url = Path(os.environ["CONTEXT_MODE_SECURITY_JS"]).resolve().as_uri()
        done = run([NODE, "--input-type=module", "-e", script, url, work / "empty", root, home])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), {
            "skill": True, "reference": True, "linked": True, "sibling": False, "outside": False,
            "traversal": False, "shallow_traversal": False, "control_wildcard_traversal": True})

    def test_lane_refuses_quota_gate_missing_host_and_remote_gateways(self):
        for extra, needle in ((("--quota-stop-percent", "90"), "--quota-stop-percent"),
                              (("--omniroute-base-url", "http://10.0.0.5:20128/v1"), "loopback")):
            _, _, done = self.stage_lane(*extra)
            self.assertEqual(done.returncode, 2, done.stdout)
            self.assertIn(needle, done.stderr)
        work = stage_work(self)
        done = build(work, "--gpt6-provider", "omniroute")
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("--codex-host", done.stderr)

    def test_codex_host_accepts_a_private_host_value_file_by_path(self):
        private = temp_dir(self) / "privatehost.json"
        private.write_text((ROOT / "adoption" / "hosts" / "example.json").read_text(encoding="utf-8"), encoding="utf-8")
        work = stage_work(self)
        profile = temp_dir(self) / "stack-worker.config.toml"
        profile.write_text(STACK_WORKER_FIXTURE, encoding="utf-8")
        done = build(work, "--gpt6-provider", "omniroute", "--codex-host", private, "--stack-worker-profile", profile)
        self.assertEqual(done.returncode, 0, done.stderr)
        config = (work / "codex-home" / "config.toml").read_text(encoding="utf-8")
        self.assertIn("[mcp_servers.context-mode]", config)
        self.assertNotIn(str(private.parent), config)  # the private file's location stays out of the lane record
        codex = json.loads((work / "staged.json").read_text())["codex"]
        self.assertEqual(codex["lane_home"]["host"], "privatehost")
        missing = build(stage_work(self), "--gpt6-provider", "omniroute", "--codex-host", str(private) + ".gone.json",
                        "--stack-worker-profile", profile)
        self.assertEqual(missing.returncode, 2)
        self.assertIn("does not exist", missing.stderr)

    @unittest.skipIf(sys.version_info < (3, 11), "tomllib is Python 3.11+")
    def test_mcp_extraction_accepts_quoted_and_spaced_headers_and_fails_closed(self):
        import tomllib
        text = ('model = "x"\n[mcp_servers."demo"]\ncommand = "a"\n[ mcp_servers.plain ]\ncommand = "b"\n'
                '[mcp_servers.plain.env]\nK = "v"\n[projects."/p"]\ntrust_level = "trusted"\n')
        sections, names = build_args.mcp_sections(text)
        self.assertEqual(names, ["demo", "plain"])
        self.assertNotIn("[projects.", sections)
        self.assertEqual(tomllib.loads(sections)["mcp_servers"], tomllib.loads(text)["mcp_servers"])
        # A server the line extraction cannot see (declared with inline-table syntax under [mcp_servers]) fails closed.
        with self.assertRaises(ValueError):
            build_args.mcp_sections('[mcp_servers]\nhidden = { command = "c" }\n[mcp_servers.plain]\ncommand = "b"\n')

    @unittest.skipIf(sys.version_info < (3, 11), "tomllib is Python 3.11+")
    def test_mcp_extraction_keeps_nested_tables_in_every_header_spelling(self):
        import tomllib
        # TOML allows a literal-quoted name and spaces around the dots; a server's env table in either spelling is kept.
        for env_header in ("[mcp_servers.'demo'.env]", "[ mcp_servers . demo . env ]", "[mcp_servers . 'demo' . env]"):
            text = f'[mcp_servers.demo]\ncommand = "a"\n{env_header}\nK = "v"\n[projects."/p"]\ntrust_level = "t"\n'
            sections, names = build_args.mcp_sections(text)
            self.assertEqual(names, ["demo"], env_header)
            self.assertEqual(tomllib.loads(sections)["mcp_servers"], {"demo": {"command": "a", "env": {"K": "v"}}},
                             env_header)
        # A nested table the line extraction cannot see (a quoted top-level key) would lose the env: fail closed.
        with self.assertRaisesRegex(ValueError, r"differ from the rendered config for \['demo'\]"):
            build_args.mcp_sections('[mcp_servers.demo]\ncommand = "a"\n["mcp_servers".demo.env]\nK = "v"\n')

    def test_mcp_extraction_refuses_without_tomllib(self):
        with mock.patch.dict(sys.modules, {"tomllib": None}):  # a None entry makes the import raise ImportError
            with self.assertRaisesRegex(ValueError, "Python 3.11"):
                build_args.mcp_sections('[mcp_servers.demo]\ncommand = "a"\n')

    def stage_with_profile_tail(self, tail):
        work = stage_work(self)
        profile = temp_dir(self) / "stack-worker.config.toml"
        profile.write_text(STACK_WORKER_FIXTURE + tail, encoding="utf-8")
        return work, build(work, "--gpt6-provider", "omniroute", "--codex-host", "example",
                           "--stack-worker-profile", profile)

    def test_profile_overlay_for_a_rendered_server_stages(self):
        # Codex merges the profile over config.toml, so a partial table may tune a server the lane config defines.
        _, done = self.stage_with_profile_tail("\n[mcp_servers.serena]\nstartup_timeout_sec = 60\n")
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_profile_overlay_for_an_undefined_server_fails_closed(self):
        # A merged server table with neither command nor url is "invalid transport" in Codex 0.157.1
        # (codex-rs/config/src/mcp_types.rs:454-510), so -p stack-worker would not load at all.
        work, done = self.stage_with_profile_tail("\n[mcp_servers.absent-server]\nstartup_timeout_sec = 60\n")
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("absent-server", done.stderr)
        self.assertIn("invalid transport", done.stderr)
        self.assertFalse((work / "codex-home" / "config.toml").exists())

    def test_profile_may_define_a_whole_server(self):
        _, done = self.stage_with_profile_tail('\n[mcp_servers.extra]\ncommand = "extra-mcp"\n')
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_shipped_profile_overlays_only_rendered_servers(self):
        # The repository's own stack-worker profile, staged for the example host, must load under Codex.
        work = stage_work(self)
        done = build(work, "--gpt6-provider", "omniroute", "--codex-host", "example")
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_missing_profile_names_the_flag(self):
        work = stage_work(self)
        done = build(work, "--gpt6-provider", "omniroute", "--codex-host", "example",
                     "--stack-worker-profile", temp_dir(self) / "absent.config.toml")
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("pass --stack-worker-profile", done.stderr)

    def test_lane_home_carries_the_hosts_codex_user_instructions(self):
        # Codex reads $CODEX_HOME/AGENTS.md as global instructions; the native lane's workers get the top rule and
        # RTK's instructions from ~/.codex/AGENTS.md, so the gateway lane's home must carry the same managed block.
        work, _, done = self.stage_lane()
        self.assertEqual(done.returncode, 0, done.stderr)
        template = (ROOT / "adoption" / "templates" / "codex.AGENTS.template.md").read_bytes()
        staged = (work / "codex-home" / "AGENTS.md").read_bytes()
        self.assertEqual(staged, template)
        self.assertIn(b"rtk-ai/rtk v0.50.0 hooks/rtk-awareness-full.md, verbatim", staged)
        lane = json.loads((work / "staged.json").read_text())["codex"]["lane_home"]
        self.assertEqual(lane["agents_sha256"], hashlib.sha256(template).hexdigest())

    def test_reading_the_instructions_leaves_the_import_path_unchanged(self):
        # apply_codex_lane.py prepends the repository root on import (its line 69); the whole path must come back,
        # measured with the installer not yet loaded, so its module-level insert actually runs.
        sys.modules.pop("apply_codex_lane", None)
        before = list(sys.path)
        text = build_args.codex_user_instructions(ROOT)
        self.assertEqual(sys.path, before)
        self.assertTrue(text.startswith("<!-- native-agent-stack:codex-user-instructions:begin"))

    def test_require_key_stages_no_placeholder(self):
        work, _, done = self.stage_lane("--omniroute-require-key")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("api_key_placeholder", json.loads((work / "staged.json").read_text())["codex"])

    def test_native_default_is_unchanged(self):
        work = stage_work(self)
        done = build(work)
        self.assertEqual(done.returncode, 0, done.stderr)
        codex = json.loads((work / "staged.json").read_text())["codex"]
        self.assertNotIn("provider", codex)
        self.assertEqual(codex["model"], "gpt-6-astra")
        self.assertFalse((work / "codex-home").exists())
        self.assertEqual(codex_job.settings(work)["codex_home"], None)


class RunnerCase(unittest.TestCase):
    def setUp(self):
        self.work = temp_dir(self)
        self.bin = temp_dir(self)
        codex = self.bin / "codex"
        codex.write_text(FAKE_CODEX.format(python=sys.executable), encoding="utf-8")
        codex.chmod(0o755)
        self.config_path = self.bin / "config.json"
        self.settings({})
        self.prompt = self.bin / "prompt.txt"
        self.prompt.write_text("Reply in JSON.\n", encoding="utf-8")
        self.schema = HARNESS / "schemas" / "probe.json"
        self.env = {**os.environ, "PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}",
                    "FAKE_CODEX_CONFIG": str(self.config_path)}
        self.env.pop("SWEEP_WORK_DIR", None)

    def settings(self, codex_settings):
        write_json(self.work / "staged.json", {"codex": {"wait_poll_s": 0.05, "slot_poll_s": 0.05, "timeout_s": 30,
                                                         **codex_settings}})

    def fake(self, **config):
        config.setdefault("record", str(self.bin / "record.json"))
        if config.get("attempts"):
            counter = self.bin / "attempt-counter"
            counter.unlink(missing_ok=True)
            config["attempt_counter"] = str(counter)
        write_json(self.config_path, config)

    def call(self, *args, shell="bash"):
        return run([shell, HARNESS / "codex_call.sh", "--work-dir", self.work, *args], env=self.env)

    def job(self, name, shell="bash", **config):
        self.fake(**config)
        started = self.call("start", name, self.prompt, self.schema, shell=shell)
        self.assertEqual(started.returncode, 0, started.stderr + started.stdout)
        self.assertEqual(started.stdout.strip(), f"started {name}")
        waited = self.call("wait", name, "20", shell=shell)
        self.assertTrue(waited.stdout.startswith("done exit="), waited.stdout + waited.stderr)
        result = json.loads(self.call("result", name, shell=shell).stdout)
        if result.get("exit") == codex_job.EXIT_REFUSED:  # a started job is never refused: retain the runner's reason
            directory = self.work / "gpt6" / name
            self.fail(f"the runner refused {name}: {codex_job.read(directory / 'stderr.txt')!r} "
                      f"{codex_job.read(directory / 'failure.json')!r}")
        return result

    def record(self):
        return json.loads((self.bin / "record.json").read_text())

    def diagnose(self, name, completed):
        """What a failed start, wait or result left behind: the command's own output and the runner's files."""
        directory = self.work / "gpt6" / name
        parts = [f"stdout={completed.stdout!r}", f"stderr={completed.stderr!r}"]
        for file_name in ("exit", "failure.json", "stderr.txt", "runner.log"):
            parts.append(f"{file_name}={codex_job.read(directory / file_name)!r}")
        parts.append(f"done={(directory / 'done').exists()} running={codex_job.running(directory)}")
        return "\n".join(parts)


LAST = {"repository": "https://github.com/ggml-org/llama.cpp", "latest_release": "b1", "stars_known": 1}
COMPLETED = {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 80, "output_tokens": 7,
                                                 "reasoning_output_tokens": 3}}


class WaitFinishRaceTests(unittest.TestCase):
    """wait() checked done and then the job lock. A job that finished between the two checks was reported as
    "done exit=none (the job is not running)": one hosted CI run of 2026-10-01 failed
    test_web_search_modes_are_staged_bound_and_recorded that way. The runner writes done before it releases the lock,
    so wait reads done again once it sees the lock free. Synthetic fixture: the lock check itself completes the job."""

    def wait_output(self, finishes_during_the_lock_check):
        base = temp_dir(self)
        write_json(base / "staged.json", {"codex": {"wait_poll_s": 0.05}})
        directory = codex_job.job_dir(base, "race")
        directory.mkdir(parents=True)
        (directory / "job.lock").touch()

        def lock_check(_directory):
            if finishes_during_the_lock_check:  # the runner's last writes; its lock is free when this returns
                (directory / "events.jsonl").write_text(json.dumps(COMPLETED) + "\n", encoding="utf-8")
                write_json(directory / "last.json", LAST)
                codex_job.finish(directory, 0)
            return False
        output = io.StringIO()
        with mock.patch.object(codex_job, "running", side_effect=lock_check), contextlib.redirect_stdout(output):
            self.assertEqual(codex_job.wait(base, "race", 5), 0)
        return output.getvalue().strip()

    def test_a_job_that_finishes_during_the_lock_check_is_reported_done(self):
        self.assertEqual(self.wait_output(True), "done exit=0")

    def test_a_job_that_never_ran_is_still_reported_as_not_running(self):
        self.assertEqual(self.wait_output(False), "done exit=none (the job is not running)")


class ProcessGroupStopTests(unittest.TestCase):
    """Darwin's killpg skips zombies and reports EPERM when a still-existing group has nothing else to signal
    (apple-oss-distributions/xnu xnu-12377.121.6, bsd/kern/kern_sig.c, killpg1); Linux signals a zombie silently. The
    2026-09-30 macOS full-suite job on this branch failed every watchdog test whose group died at TERM with exit 2
    "refused" (the uncaught PermissionError from the SIGKILL after the grace period). Synthetic fixture: os.killpg is
    patched to answer EPERM once the group holds only exited members; the macOS job on the fixed head is the real
    observation."""

    def child(self) -> subprocess.Popen:
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True,
                                   stdin=subprocess.DEVNULL)
        self.addCleanup(lambda: (process.kill(), process.wait()) if process.poll() is None else None)
        return process

    @staticmethod
    def darwin_killpg(real):
        def killpg(pgid, signum):
            if signum == signal.SIGTERM:
                return real(pgid, signum)
            raise PermissionError(errno.EPERM, "Operation not permitted")  # signal 0 or SIGKILL: only zombies left
        return killpg

    def test_stop_group_completes_when_darwin_reports_eperm_for_the_dead_group(self):
        process = self.child()
        with mock.patch.object(codex_job.os, "killpg", side_effect=self.darwin_killpg(os.killpg)):
            codex_job.stop_group(process, 0.1)
        self.assertEqual(process.returncode, -signal.SIGTERM)

    def test_stop_group_still_kills_a_group_that_survives_term(self):
        process = self.child()
        real = os.killpg
        calls = []

        def killpg(pgid, signum):
            calls.append(signum)
            if signum == signal.SIGTERM:
                return None  # a member ignores TERM: the group stays alive until KILL
            return real(pgid, signum)
        with mock.patch.object(codex_job.os, "killpg", side_effect=killpg):
            codex_job.stop_group(process, 0.2)
        self.assertEqual((process.returncode, calls[0], calls[-1]), (-signal.SIGKILL, signal.SIGTERM, signal.SIGKILL))

    def test_group_alive_treats_esrch_and_darwin_eperm_as_stopped(self):
        for error in (ProcessLookupError(errno.ESRCH, "No such process"),
                      PermissionError(errno.EPERM, "Operation not permitted")):
            with self.subTest(error=type(error).__name__), \
                    mock.patch.object(codex_job.os, "killpg", side_effect=error):
                self.assertFalse(codex_job.group_alive(2 ** 22 + 1))
        with mock.patch.object(codex_job.os, "killpg", return_value=None):
            self.assertTrue(codex_job.group_alive(2 ** 22 + 1))


class OmniRouteLaneRunnerTests(RunnerCase):
    def test_primary_gateway_429_stops_with_the_pool_reason(self):
        self.lane()
        staged = json.loads((self.work / "staged.json").read_text())
        self.settings({**staged["codex"], "api_key_placeholder": "local-loopback"})
        self.env.pop("OMNIROUTE_API_KEY", None)
        result = self.job("gpt6-primary-429", exit=1, events=[{"type": "error", "message": RETRY_429_TEXT}])
        self.assertEqual((result["exit"], result["limit"], result["limit_marker"]), (3, True, True))
        self.assertTrue((self.work / "LIMIT").read_text().startswith("gateway pool 429;"))
        self.assertFalse((self.work / "LIMIT-native").exists())

    def test_primary_gateway_stderr_429_is_a_fault_without_an_error_event(self):
        self.lane()
        staged = json.loads((self.work / "staged.json").read_text())
        self.settings({**staged["codex"], "api_key_placeholder": "local-loopback"})
        self.env.pop("OMNIROUTE_API_KEY", None)
        result = self.job("gpt6-primary-stderr", exit=1, stderr="ERROR: " + RETRY_429_TEXT + "\n")
        self.assertEqual((result["exit"], result["limit"], result["limit_marker"]), (1, False, False))

    """A gateway lane runs Codex with CODEX_HOME set to the staged lane-local home, -p stack-worker and no
    --ignore-user-config, and never starts without its key variable."""

    def lane(self):
        home = self.work / "codex-home"
        home.mkdir(exist_ok=True)
        (home / "config.toml").write_text('model = "cx/gpt-6-astra"\nmodel_provider = "omniroute"\n', encoding="utf-8")
        (home / "stack-worker.config.toml").write_text(STACK_WORKER_FIXTURE, encoding="utf-8")
        self.settings({"provider": "omniroute", "codex_home": "codex-home", "profile": "stack-worker",
                       "api_key_env": "OMNIROUTE_API_KEY", "model": "cx/gpt-6-astra"})

    def test_lane_uses_its_codex_home_and_profile(self):
        self.lane()
        self.env["OMNIROUTE_API_KEY"] = "fixture-not-a-key"
        result = self.job("gpt6-probe", last=LAST, events=[COMPLETED])
        directory = self.work / "gpt6" / "gpt6-probe"
        self.assertEqual(self.record()["argv"], [
            "exec", "-p", "stack-worker",
            "--skip-git-repo-check", "-s", "read-only",
            "-m", "cx/gpt-6-astra", "-c", 'model_reasoning_effort="max"', "-c", 'web_search="live"',
            "--output-schema", str(directory / "schema.json"), "-o", str(directory / "last.json"), "--json",
            "Reply in JSON."])
        self.assertEqual(self.record()["codex_home"], str(self.work / "codex-home"))
        self.assertTrue(self.record()["api_key_present"])
        self.assertEqual((result["status"], result["exit"], result["model"]), ("done", 0, "cx/gpt-6-astra"))
        self.assertEqual(json.loads((directory / "inputs.json").read_text())["provider"], "omniroute")

    def test_lane_overrides_profile_effort_and_web_search_from_staged_settings(self):
        self.lane()
        staged = json.loads((self.work / "staged.json").read_text())
        staged["codex"].update(model="cx/gpt-6.1-sol", effort="ultra", web_search="disabled")
        write_json(self.work / "staged.json", staged)
        self.env["OMNIROUTE_API_KEY"] = "fixture-not-a-key"
        result = self.job("worker", last=LAST, events=[COMPLETED])
        self.assertEqual((result["exit"], result["effort"], result["web_search"]), (0, "ultra", "disabled"))
        for override in ('model_reasoning_effort="ultra"', 'web_search="disabled"'):
            self.assertIn(override, self.record()["argv"])
        self.assertNotIn("features.unbounded_connection_retries=false", self.record()["argv"])
        self.assertEqual(result["inputs"]["effort"], "ultra")

    def test_lane_without_its_key_never_starts_codex(self):
        self.lane()
        self.env.pop("OMNIROUTE_API_KEY", None)
        result = self.job("gpt6-probe", last=LAST, events=[COMPLETED])
        self.assertEqual(result["exit"], codex_job.EXIT_NO_KEY)
        self.assertEqual(result["failure"]["kind"], "no_key")
        self.assertIn("OMNIROUTE_API_KEY is not set", result["stderr_tail"])
        self.assertFalse((self.bin / "record.json").exists())  # the fake codex never ran

    def test_keyless_lane_uses_the_placeholder_only_when_the_variable_is_unset(self):
        self.lane()
        self.settings({"provider": "omniroute", "codex_home": "codex-home", "profile": "stack-worker",
                       "api_key_env": "OMNIROUTE_API_KEY", "api_key_placeholder": "local-loopback",
                       "model": "cx/gpt-6-astra"})
        self.env.pop("OMNIROUTE_API_KEY", None)
        result = self.job("gpt6-probe", last=LAST, events=[COMPLETED])
        self.assertEqual(result["exit"], 0)
        self.assertTrue(self.record()["api_key_present"])
        lane = codex_job.settings(self.work)
        saved = os.environ.pop("OMNIROUTE_API_KEY", None)
        try:
            self.assertEqual(codex_job.codex_env(lane)["OMNIROUTE_API_KEY"], "local-loopback")
            os.environ["OMNIROUTE_API_KEY"] = "   "  # blank counts as unset: Codex rejects a blank env_key value
            self.assertEqual(codex_job.codex_env(lane)["OMNIROUTE_API_KEY"], "local-loopback")
            os.environ["OMNIROUTE_API_KEY"] = "operator-value"
            self.assertEqual(codex_job.codex_env(lane)["OMNIROUTE_API_KEY"], "operator-value")  # a real key wins
        finally:
            os.environ.pop("OMNIROUTE_API_KEY", None)
            if saved is not None:
                os.environ["OMNIROUTE_API_KEY"] = saved

    def test_lane_settings_refuse_a_quota_gate_and_a_missing_home(self):
        self.lane()
        self.settings({"provider": "omniroute", "codex_home": "codex-home", "profile": "stack-worker",
                       "api_key_env": "OMNIROUTE_API_KEY", "quota_stop_percent": 90})
        with self.assertRaises(codex_job.UsageError):
            codex_job.settings(self.work)
        self.settings({"provider": "omniroute", "codex_home": "missing-home", "api_key_env": "OMNIROUTE_API_KEY"})
        with self.assertRaises(codex_job.UsageError):
            codex_job.settings(self.work)
        self.settings({"provider": "omniroute", "codex_home": "../outside", "api_key_env": "OMNIROUTE_API_KEY"})
        with self.assertRaises(codex_job.UsageError):
            codex_job.settings(self.work)

    def test_lane_headers_must_match_the_lane_home_and_are_recorded_per_job(self):
        self.lane()
        headers = {"x-omniroute-compression": "allow-lossy"}
        (self.work / "codex-home" / "config.toml").write_text(
            'model = "sharedgw/gpt-6-astra-max"\nmodel_provider = "omniroute"\n\n[model_providers.omniroute]\n'
            'name = "OmniRoute"\nhttp_headers = { "x-omniroute-compression" = "allow-lossy" }\n', encoding="utf-8")
        base = {"provider": "omniroute", "codex_home": "codex-home", "profile": "stack-worker",
                "api_key_env": "OMNIROUTE_API_KEY", "api_key_placeholder": "local-loopback",
                "model": "sharedgw/gpt-6-astra-max"}
        self.settings({**base, "http_headers": headers})
        self.env.pop("OMNIROUTE_API_KEY", None)
        result = self.job("gpt6-probe", last=LAST, events=[COMPLETED])
        self.assertEqual((result["exit"], result["model"]), (0, "sharedgw/gpt-6-astra-max"))
        argv = self.record()["argv"]
        self.assertEqual(argv[argv.index("-m") + 1], "sharedgw/gpt-6-astra-max")
        # The job's inputs carry the headers, so a job finished under other headers is rerun, never reused.
        self.assertEqual(result["inputs"]["http_headers"], headers)
        self.assertEqual(codex_job.job_inputs(b"p", b"s", "m", "omniroute", {}),
                         codex_job.job_inputs(b"p", b"s", "m", "omniroute"))
        # The lane home must carry exactly the staged headers: other values, or headers the record lacks.
        if sys.version_info >= (3, 11):
            for staged in ({**base, "http_headers": {"x-omniroute-compression": "off"}}, base):
                self.settings(staged)
                with self.assertRaisesRegex(codex_job.UsageError, "does not carry the staged provider headers"):
                    codex_job.settings(self.work)
        # Headers other than OmniRoute's per-request switches (secret-carrying ones first), malformed values, and any
        # header on the native lane are refused.
        refused = [({name: "x"}, "per-request switches") for name in (
            "x-omniroute-self-hop", "x-omniroute-video-bridge-broker", "x-omniroute-lease-owner",
            "x-omniroute-session-id", "authorization", "x-omniroute-cli-token")]
        refused += [({"x-omniroute-compression": 'a"b'}, "printable ASCII"),
                    ({"x-omniroute-compression": 1}, "printable ASCII"),
                    (["x-omniroute-compression"], "must be a table")]
        for http_headers, needle in refused:
            self.settings({**base, "http_headers": http_headers})
            with self.assertRaisesRegex(codex_job.UsageError, re.escape(needle), msg=http_headers):
                codex_job.settings(self.work)
        self.settings({"model": "gpt-6-astra", "http_headers": headers})
        with self.assertRaisesRegex(codex_job.UsageError, "needs a gateway provider"):
            codex_job.settings(self.work)
        # Through the real entry point, a refused header starts nothing and is not echoed.
        self.settings({**base, "http_headers": {"x-omniroute-self-hop": "x"}})
        started = self.call("start", "gpt6-refused", self.prompt, self.schema)
        self.assertEqual(started.returncode, 2, started.stdout + started.stderr)
        self.assertIn("per-request switches", started.stderr)
        self.assertNotIn("self-hop", started.stderr)
        self.assertFalse((self.work / "gpt6" / "gpt6-refused").exists())

    def test_staged_headers_need_tomllib_and_header_less_lanes_do_not(self):
        # Without tomllib (Python 3.9 and 3.10, as macOS's /usr/bin/python3 3.9) the lane home's header table cannot
        # be read back, so a lane with staged headers is refused; a header-less lane still runs there.
        self.lane()
        base = {"provider": "omniroute", "codex_home": "codex-home", "profile": "stack-worker",
                "api_key_env": "OMNIROUTE_API_KEY", "model": "cx/gpt-6-astra"}
        with mock.patch.dict(sys.modules, {"tomllib": None}):  # a None entry makes the import raise ImportError
            self.settings({**base, "http_headers": {"x-omniroute-compression": "allow-lossy"}})
            with self.assertRaisesRegex(codex_job.UsageError, r"Python 3\.11"):
                codex_job.settings(self.work)
            self.settings(base)
            self.assertEqual(codex_job.settings(self.work)["http_headers"], {})


class OmniRouteFallbackRunnerTests(RunnerCase):
    """Synthetic native errors and no-model app-server probes through fake codex on PATH."""

    def setUp(self):
        super().setUp()
        self.settings({"model": "gpt-6.1-sol", "fallback": {
            "provider": "omniroute", "base_url": "http://127.0.0.1:20128/v1"}})
        self.env.pop("OMNIROUTE_API_KEY", None)
        self.native_home = self.bin / "native-home"
        self.native_home.mkdir()
        self.env["CODEX_HOME"] = str(self.native_home)

    def native_marker(self):
        codex_job.mark_limit(self.work, json.dumps({"reason": LIMIT_TEXT, "reset_time": "reported reset"}),
                             marker="LIMIT-native")

    def test_native_limit_falls_back_in_the_held_slot_and_keeps_native_inputs(self):
        native_record, gateway_record = self.bin / "native.json", self.bin / "gateway.json"
        native_events = [{"type": "error", "message": LIMIT_TEXT},
                         {"type": "turn.failed", "error": {"message": LIMIT_TEXT}}]
        result = self.job("gpt6-fallback", attempts=[
            {"exit": 1, "events": native_events, "record": str(native_record), "stderr": "ERROR: " + LIMIT_TEXT + "\n"},
            {"exit": 0, "events": [COMPLETED], "last": LAST, "record": str(gateway_record), "stderr": ""}])
        directory = self.work / "gpt6" / "gpt6-fallback"
        kept = directory / "attempts" / "1"
        self.assertEqual((result["exit"], result["limit"], result["limit_marker"]), (0, False, False))
        self.assertEqual(result["inputs"]["model"], "gpt-6.1-sol")
        self.assertEqual(result["model"], "cx/gpt-6.1-sol-max")
        self.assertEqual(result["route"], {"provider": "omniroute", "fallback_from": "native", "reason": LIMIT_TEXT,
                         "native_model": "gpt-6.1-sol", "gateway_model": "cx/gpt-6.1-sol-max", "native_attempt": 1,
                         "search_backend": "omniroute:/alpha/search"})
        self.assertEqual(result["attempts"][0]["exit"], 3)
        self.assertIsNone(result["attempts"][0]["route"])
        self.assertEqual((kept / "events.jsonl").read_text(), "".join(json.dumps(e) + "\n" for e in native_events))
        self.assertEqual((kept / "stderr.txt").read_text(), "ERROR: " + LIMIT_TEXT + "\n")
        self.assertEqual((kept / "model").read_text(), "gpt-6.1-sol\n")
        self.assertFalse((kept / "done").exists(), "the held job must not advertise completion between routes")
        for name in ("prompt.txt", "schema.json", "inputs.json", "slot"):
            self.assertEqual((kept / name).read_bytes(), (directory / name).read_bytes(), name)
        marker = json.loads((self.work / "LIMIT-native").read_text())
        self.assertEqual(marker["reason"], LIMIT_TEXT)
        self.assertIn("Sep 30th, 2026 11:50 PM", marker["reset_time"])
        native = json.loads(native_record.read_text())
        gateway = json.loads(gateway_record.read_text())
        for record in (native, gateway):
            self.assertEqual(record["cwd"], str(self.work / "empty"))
            self.assertEqual(record["codex_home"], str(self.native_home))
            self.assertTrue(record["stdin_devnull"])
            self.assertEqual(record["argv"][-1], self.prompt.read_text().rstrip("\n"))
            self.assertIn("--ignore-user-config", record["argv"])
            self.assertNotIn("-p", record["argv"])
            self.assertIn('model_reasoning_effort="max"', record["argv"])
        self.assertFalse(native["api_key_present"])
        self.assertTrue(gateway["api_key_present"])
        configs = [gateway["argv"][i + 1] for i, arg in enumerate(gateway["argv"]) if arg == "-c"]
        for config in ('model_provider="omniroute"', "features.standalone_web_search=true",
                       "features.shell_snapshot=false", 'shell_environment_policy.filters.OMNIROUTE_API_KEY="exclude"'):
            self.assertIn(config, configs)
        block = next(c for c in configs if c.startswith("model_providers.omniroute="))
        for value in ('base_url = "http://127.0.0.1:20128/v1"', 'env_key = "OMNIROUTE_API_KEY"',
                      'wire_api = "responses"', "requires_openai_auth = false", "supports_standalone_web_search = true"):
            self.assertIn(value, block)
        again = self.call("start", "gpt6-fallback", self.prompt, self.schema)
        self.assertEqual((again.returncode, again.stdout.strip()), (0, "already done: gpt6-fallback"))

    def test_native_limit_then_gateway_429_stops_the_lane(self):
        result = self.job("gpt6-exhausted", attempts=[
            {"exit": 1, "events": [{"type": "error", "message": LIMIT_TEXT}]},
            {"exit": 1, "events": [{"type": "turn.failed", "error": {"message": RETRY_429_TEXT}}]}])
        self.assertEqual((result["exit"], result["limit"], result["limit_marker"]), (3, True, True))
        self.assertEqual(result["failure"]["kind"], "http_429")
        self.assertTrue((self.work / "LIMIT-native").exists())
        self.assertTrue((self.work / "LIMIT").read_text().startswith("gateway pool 429;"))
        self.assertEqual(len(result["attempts"]), 1)
        self.assertEqual((self.bin / "attempt-counter").read_text(), "2")
        stopped = self.call("start", "gpt6-next", self.prompt, self.schema)
        self.assertEqual(stopped.returncode, 3)
        self.assertIn("gateway pool 429", stopped.stdout)

    def test_gateway_retry_preserves_route_and_both_failed_attempts(self):
        staged = json.loads((self.work / "staged.json").read_text())
        self.settings({**staged["codex"], "timeout_s": 400, "capacity_backoff_s": 0.01,
                       "capacity_backoff_max_s": 0.01})
        result = self.job("gpt6-gateway-retry", attempts=[
            {"exit": 1, "events": [{"type": "error", "message": LIMIT_TEXT}]},
            {"exit": 1, "events": [{"type": "error", "message": "Selected model is at capacity."}]},
            {"exit": 0, "events": [COMPLETED], "last": LAST}])
        self.assertEqual(result["exit"], 0)
        self.assertEqual([a["failure"]["kind"] for a in result["attempts"]], ["usage", "capacity"])
        self.assertEqual(result["attempts"][1]["route"], result["route"])
        self.assertEqual(result["route"]["native_attempt"], 1)
        self.assertEqual((self.bin / "attempt-counter").read_text(), "3")
        directory = self.work / "gpt6" / "gpt6-gateway-retry"
        for number in (1, 2):
            self.assertEqual((directory / "attempts" / str(number) / "inputs.json").read_bytes(),
                             (directory / "inputs.json").read_bytes())

    def test_native_attempt_consumes_the_shared_deadline_before_gateway_launch(self):
        staged = json.loads((self.work / "staged.json").read_text())
        self.settings({**staged["codex"], "timeout_s": 10})
        self.fake(attempts=[{"exit": 1, "events": [{"type": "error", "message": LIMIT_TEXT}]}])
        directory = self.work / "gpt6" / "gpt6-budget"
        directory.mkdir(parents=True)
        prompt, schema = self.prompt.read_bytes(), self.schema.read_bytes()
        (directory / "prompt.txt").write_bytes(prompt)
        (directory / "schema.json").write_bytes(schema)
        write_json(directory / "inputs.json", codex_job.job_inputs(prompt, schema, "gpt-6.1-sol"))
        clock = [0.0]

        def wait_native(process, directory, config, deadline):
            code = process.wait(timeout=5)  # the real subprocess is fake codex on PATH
            self.assertEqual(deadline, 10)
            clock[0] = 11.0
            return code, None

        with mock.patch.dict(os.environ, self.env), \
                mock.patch.object(codex_job.time, "monotonic", side_effect=lambda: clock[0]), \
                mock.patch.object(codex_job, "wait_process", side_effect=wait_native):
            code = codex_job.run(self.work, "gpt6-budget")
        result = codex_job.result(self.work, "gpt6-budget")
        self.assertEqual((code, result["exit"], result["failure"]["kind"]), (124, 124, "timeout"))
        self.assertEqual(result["attempts"][0]["exit"], 3)
        self.assertEqual((self.bin / "attempt-counter").read_text(), "1")
        self.assertIsNone(result["started"], "no second process may start on a fresh fallback budget")

    def test_gateway_idle_retry_preserves_the_route(self):
        staged = json.loads((self.work / "staged.json").read_text())
        self.settings({**staged["codex"], "timeout_s": 400, "idle_timeout_s": 0.2, "kill_grace_s": 0.1})
        result = self.job("gpt6-gateway-idle", attempts=[
            {"exit": 1, "events": [{"type": "error", "message": LIMIT_TEXT}]},
            {"exit": 0, "events": [], "sleep": 2},
            {"exit": 0, "events": [COMPLETED], "last": LAST, "sleep": 0}])
        self.assertEqual(result["exit"], 0)
        self.assertEqual([a["failure"]["kind"] for a in result["attempts"]], ["usage", "idle"])
        self.assertEqual(result["attempts"][1]["route"], result["route"])
        self.assertEqual(result["route"]["native_attempt"], 1)

    def test_limit_native_sends_new_jobs_directly_to_gateway_when_probe_is_not_allowed(self):
        self.native_marker()
        answer = quota_answer(99)
        answer["ordinaryUsageAllowed"] = False
        probes = self.bin / "probes.log"
        result = self.job("gpt6-direct", last=LAST, events=[COMPLETED], quota={"log": str(probes), "result": answer})
        self.assertEqual((result["exit"], result["model"], result["attempts"]), (0, "cx/gpt-6.1-sol-max", []))
        self.assertIsNone(result["route"]["native_attempt"])
        self.assertEqual(probes.read_text(), "probe\n")
        self.assertTrue((self.work / "LIMIT-native").exists())
        self.assertFalse((self.work / "LIMIT").exists())
        self.assertIn('model_provider="omniroute"', self.record()["argv"])

    def test_native_recovery_probe_clears_limit_native_and_returns_to_native(self):
        self.native_marker()
        probes = self.bin / "probes.log"
        result = self.job("gpt6-recovered", last=LAST, events=[COMPLETED],
                          quota={"log": str(probes), "result": quota_answer(4)})
        self.assertEqual((result["exit"], result["model"], result["route"]), (0, "gpt-6.1-sol", None))
        self.assertEqual(probes.read_text(), "probe\n")
        self.assertFalse((self.work / "LIMIT-native").exists())
        self.assertNotIn('model_provider="omniroute"', self.record()["argv"])
        self.assertFalse(self.record()["api_key_present"])

    def test_unknown_or_failed_recovery_probe_keeps_the_gateway_route(self):
        for name, quota in (("unknown", {"result": {**quota_answer(0), "ordinaryUsageAllowed": None}}),
                            ("failed", {"error": {"code": -32600, "message": "fixture error"}})):
            with self.subTest(name=name):
                self.native_marker()
                result = self.job(f"gpt6-{name}", last=LAST, events=[COMPLETED], quota=quota)
                self.assertEqual((result["exit"], result["model"]), (0, "cx/gpt-6.1-sol-max"))
                self.assertTrue((self.work / "LIMIT-native").exists())
                self.assertEqual(result["route"]["fallback_from"], "native")

    def test_native_quota_gate_can_fail_over_without_a_native_model_call(self):
        staged = json.loads((self.work / "staged.json").read_text())
        self.settings({**staged["codex"], "quota_stop_percent": 95})
        result = self.job("gpt6-gated", last=LAST, events=[COMPLETED], quota={"result": quota_answer(96)})
        self.assertEqual((result["exit"], result["model"], result["limit_marker"]), (0, "cx/gpt-6.1-sol-max", False))
        self.assertEqual(result["attempts"][0]["failure"]["kind"], "quota")
        self.assertEqual(result["attempts"][0]["quota"]["status"], "gate")
        self.assertEqual(json.loads((self.work / "LIMIT-native").read_text())["reset_time"], "2026-10-03T01:28Z")

    def test_gateway_429_content_and_stderr_quotes_are_not_limits(self):
        self.native_marker()
        cited = {"type": "item.completed", "item": {"type": "agent_message", "text": RETRY_429_TEXT}}
        answer = {**quota_answer(99), "ordinaryUsageAllowed": False}
        result = self.job("gpt6-cited", last=LAST, events=[cited, COMPLETED],
                          stderr="ERROR: " + RETRY_429_TEXT + "\n", quota={"result": answer})
        self.assertEqual((result["exit"], result["limit"], result["limit_marker"]), (0, False, False))
        result = self.job("gpt6-stderr-429", exit=1, events=[], stderr="ERROR: " + RETRY_429_TEXT + "\n",
                          quota={"result": answer})
        self.assertEqual((result["exit"], result["limit"], result["limit_marker"]), (1, False, False))


class RunnerTests(RunnerCase):
    def bound_job(self, name="snapshot"):
        directory = self.work / "gpt6" / name
        directory.mkdir(parents=True, exist_ok=True)
        prompt, schema = self.prompt.read_bytes(), self.schema.read_bytes()
        (directory / "prompt.txt").write_bytes(prompt)
        (directory / "schema.json").write_bytes(schema)
        write_json(directory / "inputs.json", codex_job.job_inputs(prompt, schema, "gpt-6-astra"))
        return directory

    def test_invalid_restage_through_start_and_run_records_inputs_changed(self):
        for command in ("start", "run"):
            with self.subTest(command=command):
                directory = self.bound_job(command)
                bound = (directory / "inputs.json").read_bytes()
                self.settings({"effort": "invalid"})
                self.fake(last=LAST, events=[COMPLETED])
                args = (command, command, self.prompt, self.schema) if command == "start" else (command, command)
                refused = self.call(*args)
                self.assertEqual(refused.returncode, 2, refused.stdout + refused.stderr)
                self.assertFalse((self.bin / "record.json").exists())
                self.assertEqual((directory / "inputs.json").read_bytes(), bound)
                self.assertEqual((directory / "exit").read_text().strip(), "2")
                self.assertTrue((directory / "done").exists())
                result = json.loads(self.call("result", command).stdout)
                self.assertEqual((result["status"], result["failure"]["kind"]), ("failed", "inputs_changed"))
                self.assertEqual(self.call("wait", command, "0").stdout.strip(), "done exit=2")

    def test_start_records_invalid_restage_in_its_detached_runner(self):
        self.fake(last=LAST, events=[COMPLETED])

        def launch(argv, **kwargs):
            # Restaging between start's binding and the child reading settings is deterministic here.
            self.settings({"effort": "invalid"})
            inherited = os.dup(kwargs["pass_fds"][0])
            with mock.patch.dict(os.environ, {**kwargs["env"], "SWEEP_JOB_LOCK_FD": str(inherited)}):
                self.assertEqual(codex_job.run(self.work, "start-race"), 2)
            return mock.Mock()

        with mock.patch.dict(os.environ, self.env), mock.patch.object(codex_job.subprocess, "Popen", side_effect=launch):
            self.assertEqual(codex_job.start(self.work, "start-race", str(self.prompt), str(self.schema)), 0)
        self.assertFalse((self.bin / "record.json").exists())
        directory = self.work / "gpt6" / "start-race"
        self.assertTrue((directory / "done").exists())
        self.assertEqual((directory / "exit").read_text().strip(), "2")
        self.assertEqual(json.loads((directory / "failure.json").read_text())["kind"], "inputs_changed")

    def test_ultra_defaults_and_idle_refusal_precede_state_changes(self):
        write_json(self.work / "staged.json", {"codex": {"model": "gpt-6.1-sol", "effort": "ultra"}})
        config = codex_job.settings(self.work)
        self.assertEqual((config["idle_timeout_s"], config["timeout_s"], config["request_effort"]),
                         (4200, 14400, "xhigh"))
        self.settings({"effort": "ultra", "idle_timeout_s": 4800, "timeout_s": 18000})
        config = codex_job.settings(self.work)
        self.assertEqual((config["idle_timeout_s"], config["timeout_s"]), (4800, 18000))
        for idle in (1, 1800, 3599, 3600):
            with self.subTest(idle=idle):
                self.settings({"effort": "ultra", "idle_timeout_s": idle})
                refused = self.call("start", "ultra-refused", self.prompt, self.schema)
                self.assertEqual(refused.returncode, 2)
                self.assertIn("above 3600 s", refused.stderr)
                self.assertFalse((self.work / "gpt6").exists())

    def test_catalog_request_effort_mapping_and_primary_thread_usage(self):
        self.assertEqual(set(codex_job.MODEL_MULTI_AGENT_EFFORTS), set(codex_job.MODEL_EFFORTS))
        for model, expected in (("gpt-6-astra", "xhigh"), ("cx/gpt-6.1-sol-extra", "xhigh"),
                                ("gpt-6-sol", "max"), ("gpt-daybreak-blue-latest", "max")):
            with self.subTest(model=model):
                self.assertEqual(codex_job.job_inputs(b"p", b"s", model, effort="ultra")["request_effort"], expected)
        collab = {"type": "item.completed", "item": {"type": "collab_tool_call", "tool": "spawn_agent"}}
        result = self.job("delegated-max", last=LAST, events=[collab, COMPLETED])
        self.assertEqual((result["usage"], result["usage_status"]), (COMPLETED["usage"], "primary_thread_only"))
        self.prompt.write_text("Another claim.")
        self.fake(last=LAST, events=[COMPLETED])
        self.assertEqual(self.call("start", "delegated-max", self.prompt, self.schema).returncode, 0)
        self.assertEqual(self.call("wait", "delegated-max", "20").stdout.strip(), "done exit=0")
        result = json.loads(self.call("result", "delegated-max").stdout)
        self.assertEqual(result["usage_status"], "reported")
        self.assertEqual(result["attempts"][0]["usage_status"], "primary_thread_only")

    def test_completion_grace_allows_final_output_after_the_deadline(self):
        self.settings({"timeout_s": 0.3, "idle_timeout_s": 10, "kill_grace_s": 0.8})
        result = self.job("completed-grace", events=[COMPLETED], output_delay_s=0.5, last=LAST)
        self.assertEqual((result["status"], result["exit"]), ("done", 0))
        self.assertEqual(json.loads(result["output_text"]), LAST)
        self.assertIsNone(result["failure"])

    def test_completion_grace_is_bounded(self):
        self.settings({"timeout_s": 0.3, "idle_timeout_s": 10, "kill_grace_s": 0.1})
        result = self.job("completed-stuck", events=[COMPLETED], output_delay_s=60, last=LAST)
        self.assertEqual((result["exit"], result["failure"]["kind"]), (124, "timeout"))

    def test_refusal_paths_write_terminal_failure_receipts(self):
        bad_schema = self.bin / "bad-schema.json"
        bad_schema.write_text("not JSON")
        large_prompt = self.bin / "large.txt"
        large_prompt.write_text("x" * (codex_job.MAX_PROMPT_BYTES + 1))
        for name, prompt, schema in (("bad-schema", self.prompt, bad_schema),
                                     ("large-prompt", large_prompt, self.schema)):
            with self.subTest(name=name):
                self.assertEqual(self.call("start", name, prompt, schema).returncode, 2)
                directory = self.work / "gpt6" / name
                self.assertTrue((directory / "done").exists())
                failure = json.loads((directory / "failure.json").read_text())
                self.assertEqual((failure["kind"], failure["exit"]), ("refused", 2))
        directory = self.bound_job("slot-limit")
        (self.work / "LIMIT").write_text("quota reached\n")
        with mock.patch.dict(os.environ, self.env), mock.patch.object(codex_job, "acquire_slot", return_value=(None, None)):
            self.assertEqual(codex_job.run(self.work, "slot-limit"), 3)
        self.assertEqual(json.loads((directory / "failure.json").read_text())["kind"], "limit")
        self.assertTrue((directory / "done").exists())

    def test_supervisor_launch_refusal_writes_terminal_failure_receipt(self):
        with mock.patch.dict(os.environ, self.env), \
                mock.patch.object(codex_job.subprocess, "Popen", side_effect=OSError("launch refused")):
            self.assertEqual(codex_job.start(self.work, "launch-refused", str(self.prompt), str(self.schema)), 2)
        directory = self.work / "gpt6" / "launch-refused"
        self.assertTrue((directory / "done").exists())
        self.assertEqual((directory / "exit").read_text().strip(), "2")
        self.assertEqual(json.loads((directory / "failure.json").read_text())["kind"], "refused")

    def test_zero_exit_requires_a_completed_turn_and_nonempty_output(self):
        cases = [("no-evidence", {}), ("no-turn", {"last": LAST}), ("no-output", {"events": [COMPLETED]}),
                 ("empty-output", {"events": [COMPLETED], "last_text": ""}),
                 ("blank-output", {"events": [COMPLETED], "last_text": " \n"})]
        for name, config in cases:
            with self.subTest(name=name):
                result = self.job(name, **config)
                self.assertEqual((result["status"], result["exit"]), ("failed", 126))
                self.assertEqual(result["failure"]["kind"], "incomplete")
                self.assertFalse(result["failure"]["retryable"])
                self.assertFalse(result["limit_marker"])
                recovered = self.job(name, last=LAST, events=[COMPLETED])
                self.assertEqual((recovered["status"], recovered["exit"]), ("done", 0))
                self.assertEqual(recovered["attempts"][0]["exit"], 126)
                self.assertEqual(recovered["attempts"][0]["failure"]["kind"], "incomplete")

    def test_legacy_false_success_is_reported_and_reruns_with_the_same_inputs(self):
        for name, config in (("no-turn", {"last": LAST}), ("no-output", {"events": [COMPLETED]}),
                             ("empty-output", {"events": [COMPLETED], "last_text": ""})):
            with self.subTest(name=name):
                self.job(name, **config)
                directory = self.work / "gpt6" / name
                (directory / "exit").write_text("0\n", encoding="utf-8")
                (directory / "failure.json").unlink(missing_ok=True)
                before = json.loads(self.call("result", name).stdout)
                self.assertEqual((before["status"], before["exit"], before["failure"]["kind"]),
                                 ("failed", 126, "incomplete"))
                self.assertEqual(self.call("wait", name, "0").stdout.strip(), "done exit=126")
                recovered = self.job(name, last=LAST, events=[COMPLETED])
                self.assertEqual(recovered["exit"], 0)
                self.assertEqual(recovered["attempts"][0]["failure"]["kind"], "incomplete")
                # Historical files stay unchanged even when their summary rejects the old success claim.
                self.assertEqual((directory / "attempts" / "1" / "exit").read_text(), "0\n")

    def test_nonzero_exit_is_a_failure_even_with_completed_turn_and_output(self):
        result = self.job("failed-turn", exit=1, last=LAST, events=[COMPLETED])
        self.assertEqual((result["status"], result["exit"], result["failure"]["kind"]), ("failed", 1, "exit"))

    def test_effort_is_staged_bound_to_inputs_and_recorded_for_the_attempt(self):
        self.settings({"model": "gpt-6.1-sol"})
        first = self.job("worker", last=LAST, events=[COMPLETED])
        self.assertEqual(first["effort"], "max")
        self.assertEqual((first["request_effort"], first["inputs"]["request_effort"]), ("max", "max"))
        self.settings({"model": "gpt-6.1-sol", "effort": "ultra"})
        self.fake(last=LAST, events=[COMPLETED])
        started = self.call("start", "worker", self.prompt, self.schema)
        self.assertIn("inputs changed", started.stdout)
        self.assertIn("started worker", started.stdout)
        self.assertTrue(self.call("wait", "worker", "20").stdout.startswith("done exit=0"))
        result = json.loads(self.call("result", "worker").stdout)
        self.assertIn('model_reasoning_effort="ultra"', self.record()["argv"])
        self.assertEqual((result["effort"], result["inputs"]["effort"]), ("ultra", "ultra"))
        self.assertEqual((result["request_effort"], result["inputs"]["request_effort"]), ("xhigh", "xhigh"))
        self.assertEqual((result["usage"], result["usage_status"]), (COMPLETED["usage"], "primary_thread_only"))
        self.assertEqual(result["attempts"][0]["inputs"]["effort"], "max")
        self.assertEqual(self.call("start", "worker", self.prompt, self.schema).stdout.strip(), "already done: worker")
        self.settings({"model": "gpt-6.1-sol", "effort": "max"})
        self.assertEqual(json.loads(self.call("result", "worker").stdout)["effort"], "ultra")

    def test_a_model_outside_the_catalog_takes_every_effort_but_ultra(self):
        # Codex sends a non-ultra effort unchanged for fallback metadata; ultra alone would resolve to medium.
        self.settings({"model": "unknown-model", "effort": "max"})
        result = self.job("outside", last=LAST, events=[COMPLETED])
        self.assertEqual((result["exit"], result["effort"]), (0, "max"))
        self.assertIn('model_reasoning_effort="max"', self.record()["argv"])

    def test_settings_changed_between_binding_and_launch_are_refused(self):
        directory = self.work / "gpt6" / "snapshot"
        directory.mkdir(parents=True)
        prompt, schema = self.prompt.read_bytes(), self.schema.read_bytes()
        (directory / "prompt.txt").write_bytes(prompt)
        (directory / "schema.json").write_bytes(schema)
        write_json(directory / "inputs.json", codex_job.job_inputs(prompt, schema, "gpt-6.1-sol"))
        self.settings({"model": "gpt-6.1-sol", "effort": "ultra", "web_search": "disabled"})
        self.fake(last=LAST, events=[COMPLETED])
        launched = self.call("run", "snapshot")
        self.assertEqual(launched.returncode, 2)
        self.assertFalse((self.bin / "record.json").exists())  # no Codex invocation under a different identity
        result = json.loads(self.call("result", "snapshot").stdout)
        self.assertEqual((result["status"], result["failure"]["kind"]), ("failed", "inputs_changed"))
        self.assertEqual((result["effort"], result["web_search"]), ("max", "live"))

    def test_unsupported_effort_and_web_search_are_refused_before_state_changes(self):
        cases = [("gpt-6.1-sol", "unknown"), ("gpt-6.1-sol", "none"), ("gpt-6.1-sol", "minimal"),
                 ("gpt-6.1-sol", "persistent"), ("gpt-6.1-sol", None), ("gpt-6.1-sol", True),
                 ("gpt-6-luna", "ultra"), ("cx/gpt-6-luna", "ultra"), ("gpt-5.5", "max"),
                 ("codex-auto-review", "ultra"), ("unknown-model", "ultra"), ("cx/unknown-model", "ultra")]
        for model, effort in cases:
            with self.subTest(model=model, effort=effort):
                self.settings({"model": model, "effort": effort})
                refused = self.call("start", "refused", self.prompt, self.schema)
                self.assertEqual(refused.returncode, 2)
                self.assertIn("codex.effort", refused.stderr)
                self.assertFalse((self.work / "gpt6" / "refused").exists())
        for mode in ("unknown", None, True):
            with self.subTest(web_search=mode):
                self.settings({"web_search": mode})
                refused = self.call("start", "refused", self.prompt, self.schema)
                self.assertEqual(refused.returncode, 2)
                self.assertIn("codex.web_search", refused.stderr)
                self.assertFalse((self.work / "gpt6" / "refused").exists())

    def test_web_search_modes_are_staged_bound_and_recorded(self):
        first = self.job("search", last=LAST, events=[COMPLETED])
        self.assertEqual(first["web_search"], "live")
        for mode in ("disabled", "cached", "indexed", "live"):
            with self.subTest(mode=mode):
                self.settings({"web_search": mode})
                self.fake(last=LAST, events=[COMPLETED])
                started = self.call("start", "search", self.prompt, self.schema)
                self.assertIn("started search", started.stdout, self.diagnose("search", started))
                waited = self.call("wait", "search", "20")
                self.assertTrue(waited.stdout.startswith("done exit=0"), self.diagnose("search", waited))
                result = json.loads(self.call("result", "search").stdout)
                self.assertEqual(result["web_search"], mode)
                self.assertIn(f'web_search="{mode}"', self.record()["argv"])
        self.settings({"web_search": "disabled"})
        self.assertEqual(json.loads(self.call("result", "search").stdout)["web_search"], "live")

    def test_codex_command_line_stdin_and_directory(self):
        result = self.job("gpt6-probe", last=LAST, events=[{"type": "thread.started", "thread_id": "fixture"}, COMPLETED])
        directory = self.work / "gpt6" / "gpt6-probe"
        self.assertEqual(self.record()["argv"], [
            "exec", "--ignore-user-config", "--skip-git-repo-check", "-s", "read-only",
            "-m", "gpt-6-astra", "-c", 'model_reasoning_effort="max"', "-c", 'web_search="live"',
            "--output-schema", str(directory / "schema.json"), "-o", str(directory / "last.json"), "--json",
            "Reply in JSON."])  # the prompt without its trailing newline, as "$(cat prompt.txt)" gave it
        self.assertEqual(self.record()["cwd"], str(self.work / "empty"))
        self.assertTrue(self.record()["stdin_devnull"])
        self.assertEqual(self.record()["stdin_read"], "")
        self.assertEqual((result["status"], result["exit"], result["limit"]), ("done", 0, False))
        self.assertEqual(json.loads(result["output_text"]), LAST)
        self.assertNotIn("\n", result["output_text"])  # compact: fewer tokens for the wrapper agent to copy
        self.assertEqual(result["usage"], COMPLETED["usage"])
        self.assertEqual((result["model"], result["effort"], result["codex_version"]),
                         ("gpt-6-astra", "max", "codex-cli 0.0.0-fixture"))
        self.assertFalse((self.work / "LIMIT").exists())

    def test_model_and_usage_across_turns(self):
        self.settings({"model": "gpt-6-sol"})
        result = self.job("gpt6-probe", last=LAST, events=[COMPLETED, COMPLETED])
        argv = self.record()["argv"]
        self.assertEqual(argv[argv.index("-m") + 1], "gpt-6-sol")
        self.assertEqual(result["usage"]["input_tokens"], 200)
        self.assertEqual(result["model"], "gpt-6-sol")

    def test_cited_usage_limitation_text_never_sets_the_marker(self):
        cited = {"type": "item.completed", "item": {"id": "1", "type": "agent_message", "text":
                 "The README's 'Usage limitation' section; a quoted log says: You've hit your usage limit."}}
        search = {"type": "item.completed", "item": {"id": "2", "type": "web_search", "query": "Usage limitation"}}
        result = self.job("gpt6-discover-workers", last=LAST, events=[cited, search, COMPLETED],
                          stderr="Reading additional input from stdin...\n")
        self.assertEqual((result["exit"], result["limit"]), (0, False))
        self.assertFalse((self.work / "LIMIT").exists())

    def test_usage_limit_in_stderr_sets_the_marker_and_blocks_later_starts(self):
        result = self.job("gpt6-fit-alpha", exit=1, stderr="Reading additional input from stdin...\nERROR: " + LIMIT_TEXT + "\n")
        self.assertEqual((result["exit"], result["limit"], result["limit_marker"]), (3, True, True))
        self.assertTrue((self.work / "LIMIT").exists())
        refused = self.call("start", "gpt6-fit-beta", self.prompt, self.schema)
        self.assertEqual(refused.returncode, 3)
        self.assertIn("LIMIT marker present; refusing to start gpt6-fit-beta", refused.stdout)
        self.assertEqual(self.call("wait", "gpt6-fit-beta", "5").stdout.strip(), "done exit=3")
        refused_result = json.loads(self.call("result", "gpt6-fit-beta").stdout)
        self.assertEqual((refused_result["status"], refused_result["failure"]["kind"]), ("failed", "limit"))

    def test_usage_limit_in_json_error_events_sets_the_marker(self):
        # codex exec --json prints fatal errors on stdout as `error` and `turn.failed` events (rust-v0.155.1).
        for name, events in (("both", [{"type": "error", "message": LIMIT_TEXT},
                                       {"type": "turn.failed", "error": {"message": LIMIT_TEXT}}]),
                             ("failed-only", [{"type": "turn.failed", "error": {"message":
                                                                             "You've hit your usage limit."}}])):
            (self.work / "LIMIT").unlink(missing_ok=True)
            result = self.job(f"gpt6-{name}", exit=1, events=events, stderr="Reading additional input from stdin...\n")
            self.assertEqual((result["exit"], result["limit"]), (3, True), name)
            self.assertTrue((self.work / "LIMIT").exists(), name)

    def test_gateway_429_sets_the_marker_with_a_reason_and_blocks_later_starts(self):
        # A pooled route answers 429 without the usage-limit body, and Codex retries no 429, so it ends at once with
        # its retry-limit report (an `error` then a `turn.failed` event); on 2026-09-29 nine follow-up jobs ended so
        # within two seconds each while the workflow kept spending.
        result = self.job("gpt6-gateway-429", exit=1, stderr="Reading additional input from stdin...\n",
                          events=[{"type": "error", "message": RETRY_429_TEXT},
                                  {"type": "turn.failed", "error": {"message": RETRY_429_TEXT}}])
        self.assertEqual((result["exit"], result["limit"], result["limit_marker"]), (3, True, True))
        reason = (self.work / "LIMIT").read_text()
        self.assertIn("HTTP 429 from the route", reason)
        self.assertIn("gpt6-gateway-429", reason)
        self.assertIn("no reset time", reason)
        refused = self.call("start", "gpt6-fit-beta", self.prompt, self.schema)
        self.assertEqual(refused.returncode, 3)
        self.assertIn("LIMIT marker present; refusing to start gpt6-fit-beta", refused.stdout)

    def test_a_usage_limit_report_keeps_its_empty_marker_when_a_retry_report_follows(self):
        result = self.job("gpt6-both", exit=1, stderr="Reading additional input from stdin...\n",
                          events=[{"type": "error", "message": LIMIT_TEXT},
                                  {"type": "error", "message": RETRY_429_TEXT}])
        self.assertEqual((result["exit"], result["limit"]), (3, True))
        self.assertEqual((self.work / "LIMIT").read_text(), "")

    def test_a_retry_limit_report_for_another_status_is_a_fault_not_a_limit(self):
        # Synthetic: Codex builds this report for a 429 only, so these pin the pattern's status boundary.
        for status in ("500 Internal Server Error", "502 Bad Gateway", "4290 Unknown", "404 Not Found"):
            with self.subTest(status=status):
                (self.work / "LIMIT").unlink(missing_ok=True)
                result = self.job(f"gpt6-status-{status.split()[0]}", exit=1, stderr="Reading additional input from stdin...\n",
                                  events=[{"type": "error", "message":
                                           f"exceeded retry limit, last status: {status}, request id: r"}])
                self.assertEqual((result["exit"], result["limit"]), (1, False))
                self.assertFalse((self.work / "LIMIT").exists())

    def test_other_failures_do_not_set_the_marker_and_rerun_on_the_next_start(self):
        log = self.bin / "runs.log"
        result = self.job("gpt6-flaky", exit=1, log=str(log), events=[{"type": "error", "message": "stream error"}])
        self.assertEqual((result["exit"], result["limit"]), (1, False))
        self.assertFalse((self.work / "LIMIT").exists())
        result = self.job("gpt6-flaky", last=LAST, log=str(log), events=[COMPLETED])
        self.assertEqual(result["exit"], 0)
        again = self.call("start", "gpt6-flaky", self.prompt, self.schema)
        self.assertEqual(again.stdout.strip(), "already done: gpt6-flaky")
        self.assertEqual(log.read_text().count("start"), 2)
        # The failed attempt is kept unchanged and still accounted: exit 1, no usage reported.
        kept = self.work / "gpt6" / "gpt6-flaky" / "attempts" / "1"
        self.assertIn("stream error", (kept / "events.jsonl").read_text())
        self.assertEqual((kept / "exit").read_text().strip(), "1")
        self.assertEqual([(a["attempt"], a["exit"], a["usage"], a["usage_status"]) for a in result["attempts"]],
                         [(1, 1, None, "unavailable")])
        self.assertEqual((result["usage"], result["usage_status"]), (COMPLETED["usage"], "reported"))

    def test_a_done_job_is_reused_only_for_the_same_inputs(self):
        # The resume case: a regenerated prompt (new proposals) must get a new GPT-6 vote, not the cached one.
        log = self.bin / "runs.log"
        first = self.job("gpt6-fit-alpha", last=LAST, log=str(log), events=[COMPLETED])
        self.assertEqual(first["inputs"]["model"], "gpt-6-astra")
        self.prompt.write_text("Reply in JSON about other proposals.\n", encoding="utf-8")
        self.fake(last={**LAST, "latest_release": "b2"}, log=str(log), events=[COMPLETED])
        rerun = self.call("start", "gpt6-fit-alpha", self.prompt, self.schema)
        self.assertEqual(rerun.stdout.strip().splitlines(), [
            "inputs changed since gpt6-fit-alpha finished; its attempt is kept under attempts/", "started gpt6-fit-alpha"])
        self.assertTrue(self.call("wait", "gpt6-fit-alpha", "20").stdout.startswith("done exit=0"))
        second = json.loads(self.call("result", "gpt6-fit-alpha").stdout)
        self.assertEqual(json.loads(second["output_text"])["latest_release"], "b2")
        self.assertNotEqual(second["inputs"]["prompt_sha256"], first["inputs"]["prompt_sha256"])
        self.assertEqual([(a["exit"], a["usage"], a["inputs"]) for a in second["attempts"]],
                         [(0, COMPLETED["usage"], first["inputs"])])
        self.assertEqual(self.call("start", "gpt6-fit-alpha", self.prompt, self.schema).stdout.strip(),
                         "already done: gpt6-fit-alpha")
        # Changed inputs while the usage limit is set: refused, and the old claim's output is no longer served.
        (self.work / "LIMIT").touch()
        self.prompt.write_text("Reply in JSON about a third set of proposals.\n", encoding="utf-8")
        refused = self.call("start", "gpt6-fit-alpha", self.prompt, self.schema)
        self.assertEqual(refused.returncode, 3)
        stale = json.loads(self.call("result", "gpt6-fit-alpha").stdout)
        self.assertEqual((stale["status"], stale["exit"], stale["output_text"]), ("failed", 3, None))
        self.assertEqual([a["exit"] for a in stale["attempts"]], [0, 0])
        (self.work / "LIMIT").unlink()
        self.settings({"model": "gpt-6-sol"})  # a different model is a different claim too
        self.assertIn("started gpt6-fit-alpha", self.call("start", "gpt6-fit-alpha", self.prompt, self.schema).stdout)
        self.assertTrue(self.call("wait", "gpt6-fit-alpha", "20").stdout.startswith("done exit=0"))
        self.assertEqual(log.read_text().count("start"), 3)

    def test_a_running_job_is_not_started_twice(self):
        self.fake(last=LAST, sleep=2, events=[COMPLETED])
        self.assertEqual(self.call("start", "gpt6-slow", self.prompt, self.schema).returncode, 0)
        again = self.call("start", "gpt6-slow", self.prompt, self.schema)
        self.assertEqual(again.stdout.strip(), "already running: gpt6-slow")
        other = self.bin / "other-prompt.txt"
        other.write_text("A different claim.\n", encoding="utf-8")
        refused = self.call("start", "gpt6-slow", other, self.schema)
        self.assertEqual(refused.returncode, 2)
        self.assertEqual(refused.stdout.strip(), "already running with different inputs: gpt6-slow; not started")
        self.assertEqual(self.call("wait", "gpt6-slow", "0.1").stdout.strip(), "running")
        self.assertTrue(self.call("wait", "gpt6-slow", "20").stdout.startswith("done exit=0"))

    def test_slots_bound_concurrent_codex_processes(self):
        self.settings({"slots": 1})
        log = self.bin / "slots.log"
        self.fake(last=LAST, sleep=0.6, log=str(log), events=[COMPLETED])
        for name in ("gpt6-a", "gpt6-b"):
            self.assertEqual(self.call("start", name, self.prompt, self.schema).returncode, 0)
        for name in ("gpt6-a", "gpt6-b"):
            self.assertTrue(self.call("wait", name, "20").stdout.startswith("done exit=0"))
        events = [(float(t), kind) for kind, t in (line.split() for line in log.read_text().splitlines())]
        self.assertEqual([kind for _, kind in sorted(events)], ["start", "end", "start", "end"])
        slots = {(self.work / "gpt6" / name / "slot").read_text().strip() for name in ("gpt6-a", "gpt6-b")}
        self.assertEqual(slots, {"1"})

    def test_rust_log_is_not_passed_to_codex_and_trace_text_never_sets_the_marker(self):
        # GPT-6 review of #324: with RUST_LOG=trace Codex 0.155.1 logs model response data on stderr, and a quoted
        # limit message there set the marker falsely.
        self.env["RUST_LOG"] = "trace"
        trace = ('2026-09-26T03:47:00.000000Z TRACE codex_api::sse::responses: SSE event: '
                 '{"type":"response.output_text.delta","delta":"a cited log: ' + LIMIT_TEXT + '"}\n')
        result = self.job("gpt6-traced", last=LAST, events=[COMPLETED], stderr=trace)
        self.assertIsNone(self.record()["rust_log"])
        self.assertEqual((result["exit"], result["limit"]), (0, False))
        self.assertFalse((self.work / "LIMIT").exists())

    def test_timeout_kills_children_that_ignore_term(self):
        self.settings({"timeout_s": 1, "kill_grace_s": 0.5})
        pid_file = self.bin / "stubborn.pid"
        result = self.job("gpt6-stubborn", sleep=60, stubborn=str(pid_file))
        self.assertEqual(result["exit"], 124)
        pid = int(pid_file.read_text())
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and process_alive(pid):
            time.sleep(0.1)
        self.assertFalse(process_alive(pid), "a child that ignored SIGTERM survived the timeout cleanup")

    def test_timeout_stops_codex_with_exit_124(self):
        self.settings({"timeout_s": 1})
        began = time.monotonic()
        result = self.job("gpt6-hang", sleep=60)
        self.assertEqual(result["exit"], 124)
        self.assertLess(time.monotonic() - began, 20)

    def test_missing_codex_and_bad_inputs_fail_fast(self):
        env = dict(self.env, PATH=os.pathsep.join(p for p in os.environ.get("PATH", "").split(os.pathsep)
                                                  if not (Path(p) / "codex").exists()))
        done = run(["bash", HARNESS / "codex_call.sh", "--work-dir", self.work, "start", "gpt6-x", self.prompt,
                    self.schema], env=env)
        self.assertEqual(done.returncode, 127)
        self.assertEqual(json.loads(self.call("result", "gpt6-x").stdout)["failure"]["kind"], "no_codex")
        self.assertIn("codex is not on PATH", done.stdout)
        self.assertEqual(self.call("wait", "gpt6-x", "5").stdout.strip(), "done exit=127")
        self.assertEqual(self.call("start", "../escape", self.prompt, self.schema).returncode, 2)
        self.assertEqual(self.call("bogus").returncode, 2)

    def test_work_dir_inside_a_repository_is_refused(self):
        repo = temp_dir(self)
        (repo / ".git").mkdir()
        (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (repo / "w").mkdir()
        done = run(["bash", HARNESS / "codex_call.sh", "--work-dir", repo / "w", "start", "gpt6-x", self.prompt,
                    self.schema], env=self.env)
        self.assertEqual(done.returncode, 2)
        self.assertIn("inside the git repository", done.stderr)

    def test_codex_sandbox_mount_targets_are_not_repositories(self):
        # Codex's Linux sandbox leaves an empty .git (directory or file) under its writable roots while a command runs
        # (codex-rs/linux-sandbox/src/bwrap.rs, SyntheticMountTarget); only a real marker makes a repository.
        for kind in ("empty-dir", "empty-file", "gitdir-file", "unborn-head-symlink"):
            with self.subTest(kind=kind):
                root = temp_dir(self)
                if kind == "empty-dir":
                    (root / ".git").mkdir()
                elif kind == "unborn-head-symlink":
                    # git allows HEAD to be a symlink to a branch that has no commit yet (a dangling link): a repository.
                    (root / ".git").mkdir()
                    (root / ".git" / "HEAD").symlink_to("refs/heads/main")
                else:
                    (root / ".git").write_text("gitdir: /elsewhere/.git\n" if kind == "gitdir-file" else "",
                                               encoding="utf-8")
                (root / "w").mkdir()
                expected = root if kind in ("gitdir-file", "unborn-head-symlink") else None
                self.assertEqual(codex_job.inside_repository(root / "w"), expected)
                self.assertEqual(sweep_common.inside_repository(root / "w"), expected)

    def test_limit_detection_reads_only_codex_error_reports(self):
        directory = self.work / "gpt6" / "unit"
        directory.mkdir(parents=True)
        cases = [
            ("", [{"type": "item.completed", "item": {"type": "agent_message", "text": "hit your usage limit"}}], False),
            ("ERROR: " + LIMIT_TEXT, [], True),
            ("", [{"type": "error", "message": LIMIT_TEXT}], True),
            ("", [{"type": "turn.failed", "error": {"message": LIMIT_TEXT}}], True),
            ("", [{"type": "turn.failed", "error": "not an object: hit your usage limit"}], False),
            ("Usage limitation", [], False),
            # stderr counts only for Codex's own error lines, and only when no turn completed
            ("2026-09-26T03:47:00.000000Z ERROR codex_core::codex: " + LIMIT_TEXT, [], True),
            ("2026-09-26T03:47:00.000000Z TRACE codex_api::sse::responses: " + LIMIT_TEXT, [], False),
            ("a quoted page: " + LIMIT_TEXT, [], False),
            ("ERROR: " + LIMIT_TEXT, [{"type": "turn.completed", "usage": {"output_tokens": 1}}], False),
            # Codex's 429 report counts like the usage-limit report, and only that status (the 500 and 4290 cases are synthetic)
            ("", [{"type": "error", "message": RETRY_429_TEXT}], True),
            ("", [{"type": "turn.failed", "error": {"message": RETRY_429_TEXT}}], True),
            ("", [{"type": "error", "message": "exceeded retry limit, last status: 500 Internal Server Error"}], False),
            ("", [{"type": "error", "message": "exceeded retry limit, last status: 4290 Unknown"}], False),
            ("", [{"type": "item.completed", "item": {"type": "agent_message", "text": RETRY_429_TEXT}}], False),
            ("2026-09-29T13:47:00.000000Z ERROR codex_core::codex: " + RETRY_429_TEXT, [], True),
            ("2026-09-29T13:47:00.000000Z TRACE codex_api::sse::responses: " + RETRY_429_TEXT, [], False),
            ("a quoted page: " + RETRY_429_TEXT, [], False),
            ("ERROR: " + RETRY_429_TEXT, [{"type": "turn.completed", "usage": {"output_tokens": 1}}], False),
        ]
        for stderr, events, expected in cases:
            (directory / "stderr.txt").write_text(stderr)
            (directory / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\nnot json\n")
            self.assertEqual(codex_job.limit_error(directory), expected, (stderr, events))
        for events, kind in (([{"type": "error", "message": LIMIT_TEXT}], "usage"),
                             ([{"type": "error", "message": RETRY_429_TEXT}], "http_429"),
                             ([{"type": "error", "message": RETRY_429_TEXT}, {"type": "error", "message": LIMIT_TEXT}], "usage")):
            (directory / "stderr.txt").write_text("")
            (directory / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
            self.assertEqual(codex_job.limit_kind(directory), kind, events)


def quota_answer(used, reached=None):
    """An account/rateLimits/read result (openai/codex app-server-protocol v2 GetAccountRateLimitsResponse)."""
    snapshot = {"limitId": "codex", "limitName": None, "normalModelSlug": None,
                "primary": {"usedPercent": used, "windowDurationMins": 10080, "resetsAt": 1790990880},
                "secondary": None, "credits": None, "individualLimit": None, "spendControlReached": None,
                "planType": "prolite", "rateLimitReachedType": reached}
    return {"ordinaryUsageAllowed": True, "rateLimits": snapshot, "rateLimitsByLimitId": {"codex": snapshot},
            "rateLimitResetCredits": {"availableCount": 1, "credits": None}, "accountId": "acct-fixture"}



class RecoveryRunnerTests(RunnerCase):
    CAPACITY = "Selected model is at capacity. Please try a different model."

    def setUp(self):
        super().setUp()
        self.settings({"idle_timeout_s": 0.6, "timeout_s": 400, "kill_grace_s": 0.1,
                       "capacity_backoff_s": 0.02, "capacity_backoff_max_s": 0.03})

    def capacity_events(self):
        return [{"type": "error", "message": self.CAPACITY},
                {"type": "turn.failed", "error": {"message": self.CAPACITY}}]

    def simulated_run(self, name, *, limit_during_backoff=False, quota_probe=None, version_delay_s=0,
                      retry_probe_delay_s=0, backoff_overrun_s=0):
        """Exercise real supervisor/watchdog deadlines with a virtual clock and no model process."""
        directory = self.work / "gpt6" / name
        directory.mkdir(parents=True)
        prompt, schema = self.prompt.read_bytes(), self.schema.read_bytes()
        (directory / "prompt.txt").write_bytes(prompt)
        (directory / "schema.json").write_bytes(schema)
        write_json(directory / "inputs.json", codex_job.job_inputs(prompt, schema, "gpt-6-astra"))
        clock, starts = [0.0], []

        class Process:
            pid = 987654

            def __init__(proc, argv, **kwargs):
                starts.append(argv)
                proc.returncode = 1 if len(starts) == 1 else None
                if len(starts) == 1:
                    kwargs["stdout"].write(("\n".join(json.dumps(e) for e in self.capacity_events()) + "\n").encode())
                    kwargs["stdout"].flush()

            def poll(proc):
                return proc.returncode

            def wait(proc, timeout=None):
                if proc.returncode is not None:
                    return proc.returncode
                clock[0] += timeout
                raise subprocess.TimeoutExpired("fixture", timeout)

        def sleep(seconds):
            clock[0] += seconds + backoff_overrun_s
            if limit_during_backoff:
                (self.work / "LIMIT").write_text("another job reached quota\n")

        def version(codex):
            clock[0] += version_delay_s
            return "codex-cli fixture"

        def probe(base, directory, config):
            if len(starts) == 1:
                clock[0] += retry_probe_delay_s
            return quota_probe(base, directory, config) if quota_probe else None

        with mock.patch.dict(os.environ, self.env), \
                mock.patch.object(codex_job.subprocess, "Popen", Process), \
                mock.patch.object(codex_job, "codex_version", side_effect=version), \
                mock.patch.object(codex_job, "quota_gate", side_effect=probe), \
                mock.patch.object(codex_job.time, "monotonic", side_effect=lambda: clock[0]), \
                mock.patch.object(codex_job.time, "sleep", side_effect=sleep), \
                mock.patch.object(codex_job, "stop_group"):
            code = codex_job.run(self.work, name)
        return code, codex_job.result(self.work, name), starts, clock[0]

    def test_second_attempt_hits_the_shared_deadline(self):
        self.settings({"timeout_s": 301, "idle_timeout_s": 1000, "kill_grace_s": 0.1,
                       "capacity_backoff_s": 0.02, "capacity_backoff_max_s": 0.02})
        code, result, starts, elapsed = self.simulated_run("shared-deadline")
        self.assertEqual((code, len(starts), elapsed), (124, 2, 301))
        self.assertEqual([a["failure"]["kind"] for a in result["attempts"]], ["capacity"])
        self.assertEqual(result["failure"]["kind"], "timeout")
        self.assertFalse(result["failure"]["retrying"])

    def test_version_check_spends_the_shared_budget(self):
        self.settings({"timeout_s": 400, "idle_timeout_s": 1000, "capacity_backoff_s": 0.02,
                       "capacity_backoff_max_s": 0.02})
        code, result, starts, elapsed = self.simulated_run("version-budget", version_delay_s=101)
        self.assertEqual((code, len(starts), elapsed), (1, 1, 101))
        self.assertFalse(result["failure"]["retrying"])

    def test_retry_probe_spending_the_reserve_keeps_original_failure(self):
        self.settings({"timeout_s": 400, "quota_stop_percent": 95,
                       "capacity_backoff_s": 0.02, "capacity_backoff_max_s": 0.02})
        for delay in (101, 401):
            with self.subTest(probe_delay=delay):
                code, result, starts, _ = self.simulated_run(f"probe-reserve-{delay}", retry_probe_delay_s=delay)
                self.assertEqual((code, len(starts), result["failure"]["kind"]), (1, 1, "capacity"))
                self.assertTrue(result["failure"]["retryable"])
                self.assertFalse(result["failure"]["retrying"])

    def test_backoff_oversleep_spending_the_reserve_keeps_original_failure(self):
        self.settings({"timeout_s": 301, "capacity_backoff_s": 0.02, "capacity_backoff_max_s": 0.02})
        code, result, starts, _ = self.simulated_run("oversleep", backoff_overrun_s=2)
        self.assertEqual((code, len(starts), result["attempts"]), (1, 1, []))
        self.assertEqual(result["failure"]["kind"], "capacity")
        self.assertFalse(result["failure"]["retrying"])

    def test_limit_during_backoff_records_a_refused_retry(self):
        code, result, starts, _ = self.simulated_run("backoff-limit", limit_during_backoff=True)
        self.assertEqual((code, len(starts), result["exit"]), (3, 1, 3))
        self.assertEqual(result["failure"]["kind"], "limit")
        self.assertEqual(result["attempts"][0]["failure"]["kind"], "capacity")
        directory = self.work / "gpt6" / "backoff-limit"
        self.assertEqual((directory / "exit").read_text().strip(), "3")
        self.assertTrue((directory / "done").exists())

    def test_every_attempt_gets_its_own_quota_probe_and_a_retry_can_be_gated(self):
        self.settings({"timeout_s": 400, "quota_stop_percent": 95,
                       "capacity_backoff_s": 0.02, "capacity_backoff_max_s": 0.02})
        probes = []

        def probe(base, directory, config):
            probes.append(len(probes) + 1)
            gated = len(probes) == 2
            write_json(directory / "quota.json", {"status": "gate" if gated else "ok", "probe": len(probes)})
            return "retry quota reached" if gated else None

        code, result, starts, _ = self.simulated_run("retry-quota", quota_probe=probe)
        self.assertEqual((code, len(starts), probes), (3, 1, [1, 2]))
        self.assertEqual(result["failure"]["kind"], "quota")
        directory = self.work / "gpt6" / "retry-quota"
        self.assertEqual(json.loads((directory / "attempts" / "1" / "quota.json").read_text()),
                         {"status": "ok", "probe": 1})
        self.assertEqual(json.loads((directory / "quota.json").read_text()), {"status": "gate", "probe": 2})

    def test_real_quota_probe_runs_before_both_attempts(self):
        self.settings({"timeout_s": 400, "quota_stop_percent": 95,
                       "capacity_backoff_s": 0.02, "capacity_backoff_max_s": 0.02})
        probes = self.bin / "probes.log"
        result = self.job("probe-twice", quota={"log": str(probes), "result": quota_answer(10)},
                          attempts=[{"exit": 1, "events": self.capacity_events()},
                                    {"last": LAST, "events": [COMPLETED]}])
        self.assertEqual((result["exit"], probes.read_text().count("probe")), (0, 2))
        self.assertEqual(result["quota"]["status"], "ok")
        kept = self.work / "gpt6" / "probe-twice" / "attempts" / "1" / "quota.json"
        self.assertEqual(json.loads(kept.read_text())["status"], "ok")

    def test_limit_created_during_retry_probe_prevents_another_attempt(self):
        self.settings({"timeout_s": 400, "quota_stop_percent": 95,
                       "capacity_backoff_s": 0.02, "capacity_backoff_max_s": 0.02})
        probes = []

        def probe(base, directory, config):
            probes.append(1)
            if len(probes) == 2:
                (base / "LIMIT").write_text("another job reached quota\n")

        code, result, starts, _ = self.simulated_run("limit-probe", quota_probe=probe)
        self.assertEqual((code, len(starts), result["failure"]["kind"]), (3, 1, "limit"))

    def test_backoff_longer_than_remaining_budget_preserves_original_failure(self):
        self.settings({"timeout_s": 30, "capacity_backoff_s": 60, "capacity_backoff_max_s": 60})
        result = self.job("too-long", attempts=[{"exit": 1, "events": self.capacity_events()}])
        self.assertEqual((result["exit"], result["attempts"]), (1, []))
        self.assertEqual((self.bin / "attempt-counter").read_text(), "1")
        self.assertEqual(result["failure"]["kind"], "capacity")
        self.assertFalse(result["failure"]["retrying"])
        self.assertIsNone(result["failure"]["delay_s"])

    def test_retry_floor_prevents_backoff_with_less_than_300_seconds_after_delay(self):
        self.settings({"timeout_s": 300.1, "capacity_backoff_s": 1, "capacity_backoff_max_s": 1})
        result = self.job("retry-floor", attempts=[{"exit": 1, "events": self.capacity_events()}])
        self.assertEqual((result["exit"], result["attempts"]), (1, []))
        self.assertFalse(result["failure"]["retrying"])
        self.assertEqual((self.bin / "attempt-counter").read_text(), "1")

    def test_terminal_stderr_capacity_error_is_retryable(self):
        result = self.job("stderr-capacity", attempts=[{"exit": 1, "stderr": "ERROR: " + self.CAPACITY + "\n"},
                                                      {"last": LAST, "events": [COMPLETED]}])
        self.assertEqual(result["exit"], 0)
        self.assertEqual((self.bin / "attempt-counter").read_text(), "2")
        self.assertEqual(result["attempts"][0]["failure"]["kind"], "capacity")

    def test_capacity_retries_once_for_duplicate_error_reports_and_retains_the_failure(self):
        result = self.job("recover", attempts=[{"exit": 1, "events": self.capacity_events()},
                                              {"last": LAST, "events": [COMPLETED]}])
        self.assertEqual((result["exit"], result["limit_marker"]), (0, False))
        self.assertEqual((self.bin / "attempt-counter").read_text(), "2")
        kept = self.work / "gpt6" / "recover" / "attempts" / "1"
        self.assertEqual(json.loads((kept / "failure.json").read_text())["kind"], "capacity")
        self.assertIn(self.CAPACITY, (kept / "events.jsonl").read_text())
        self.assertEqual((kept / "inputs.json").read_bytes(), (kept.parent.parent / "inputs.json").read_bytes())
        self.assertEqual((result["attempts"][0]["exit"], result["attempts"][0]["usage"]), (1, None))
        self.assertEqual(json.loads(result["output_text"]), LAST)

    def test_capacity_retry_budget_and_backoff_cap(self):
        result = self.job("capacity", attempts=[{"exit": 1, "events": self.capacity_events()}])
        self.assertEqual((result["exit"], result["limit_marker"]), (1, False))
        self.assertEqual((self.bin / "attempt-counter").read_text(), "3")
        self.assertEqual([a["exit"] for a in result["attempts"]], [1, 1])
        delays = [a["failure"]["delay_s"] for a in result["attempts"]]
        self.assertTrue(0.02 * 0.9 <= delays[0] <= 0.02 * 1.1)
        self.assertEqual(delays[1], 0.03)
        self.assertFalse(result["failure"]["retrying"])
        self.assertTrue(all(a["usage_status"] == "unavailable" for a in result["attempts"]))

    def test_limits_take_precedence_over_capacity(self):
        for message in (LIMIT_TEXT, "exceeded retry limit, last status: 429 Too Many Requests"):
            with self.subTest(message=message):
                (self.work / "LIMIT").unlink(missing_ok=True)
                result = self.job("limited", attempts=[{"exit": 1, "events":
                    self.capacity_events() + [{"type": "error", "message": message}]}])
                self.assertEqual((result["exit"], result["limit_marker"]), (3, True))
                self.assertEqual((self.bin / "attempt-counter").read_text(), "1")

    def test_quoted_capacity_and_stderr_trace_are_not_retryable(self):
        result = self.job("quoted", exit=1,
                          events=[{"type": "item.completed", "item": {"type": "web_search", "text": self.CAPACITY}}],
                          stderr="2026-09-30 TRACE tool: " + self.CAPACITY + "\n")
        self.assertEqual((result["exit"], result["attempts"]), (1, []))
        self.assertFalse(result["failure"]["retryable"])

    def test_idle_stops_the_group_retries_once_and_retains_both_failures(self):
        pid_files = [self.bin / f"stubborn-{i}.pid" for i in (1, 2)]
        result = self.job("silent", attempts=[{"sleep": 60, "stubborn": str(p)} for p in pid_files])
        self.assertEqual(result["exit"], 125)
        self.assertEqual((self.bin / "attempt-counter").read_text(), "2")
        self.assertEqual([a["failure"]["kind"] for a in result["attempts"]], ["idle"])
        self.assertEqual(result["failure"]["kind"], "idle")
        self.assertFalse(result["failure"]["retrying"])
        self.assertFalse(result["limit_marker"])
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and any(process_alive(int(p.read_text())) for p in pid_files):
            time.sleep(0.1)
        self.assertTrue(all(not process_alive(int(p.read_text())) for p in pid_files))

    def test_stderr_and_incomplete_json_are_not_progress(self):
        ticks = [{"delay_s": 0.05, "raw": '{"type":"item.started"}', "stderr": "diagnostic\n"}] * 40
        result = self.job("partial", attempts=[{"sleep": 60, "ticks": ticks}])
        self.assertEqual(result["exit"], 125)
        self.assertEqual([a["exit"] for a in result["attempts"]], [125])

    def test_reconnect_error_events_are_not_progress(self):
        ticks = [{"delay_s": 0.05, "event": {"type": "error", "message": "Reconnecting... 1/5"}}] * 40
        result = self.job("reconnect", attempts=[{"sleep": 60, "ticks": ticks}])
        self.assertEqual((result["exit"], result["failure"]["kind"]), (125, "idle"))
        self.assertEqual([a["exit"] for a in result["attempts"]], [125])
        directory = self.work / "gpt6" / "reconnect"
        for path in (directory, directory / "attempts" / "1"):
            self.assertLess(len(codex_job.events(path)), len(ticks))  # stopped while reconnects were still arriving
        self.assertFalse(result["limit_marker"])

    def test_default_budgets_clear_observed_healthy_silence_and_research_duration(self):
        write_json(self.work / "staged.json", {"codex": {}})
        config = codex_job.settings(self.work)
        self.assertEqual((config["idle_timeout_s"], config["timeout_s"]), (1800, 4000))
        self.assertLess(config["timeout_s"] + config["quota_timeout_s"] + codex_job.QUOTA_BACKSTOP_S
                        + 60 + 2 * config["kill_grace_s"], 8 * 540)
        self.settings({"idle_timeout_s": 600, "timeout_s": 4000})
        config = codex_job.settings(self.work)
        self.assertEqual((config["idle_timeout_s"], config["timeout_s"]), (600, 4000))

    def test_new_complete_events_keep_the_job_alive(self):
        ticks = [{"delay_s": 0.1, "event": {"type": "item.updated", "item": {"id": "1", "type": "web_search"}}}] * 12
        result = self.job("progress", ticks=ticks, last=LAST, events=[COMPLETED])
        self.assertEqual((result["exit"], result["attempts"]), (0, []))

    def test_idle_failure_can_recover(self):
        result = self.job("idle-recover", attempts=[{"sleep": 60}, {"last": LAST, "events": [COMPLETED]}])
        self.assertEqual(result["exit"], 0)
        self.assertEqual([a["exit"] for a in result["attempts"]], [125])
        self.assertEqual(result["attempts"][0]["failure"]["kind"], "idle")

    def test_total_timeout_remains_terminal(self):
        self.settings({"timeout_s": 0.7, "idle_timeout_s": 5, "kill_grace_s": 0.1})
        result = self.job("total-timeout", attempts=[{"sleep": 60}])
        self.assertEqual((result["exit"], result["attempts"]), (124, []))
        self.assertEqual(result["failure"]["kind"], "timeout")
        self.assertEqual((self.bin / "attempt-counter").read_text(), "1")

    def test_watchdog_policy_requires_finite_positive_durations_and_bounded_retries(self):
        for key, value in (("idle_timeout_s", 0), ("idle_timeout_s", float("nan")),
                           ("capacity_backoff_s", float("inf")), ("capacity_max_retries", -1),
                           ("capacity_max_retries", 11)):
            self.settings({key: value})
            with self.subTest(key=key, value=value), self.assertRaises(codex_job.UsageError):
                codex_job.settings(self.work)


class QuotaGateTests(RunnerCase):
    def test_the_gate_is_off_by_default(self):
        probes = self.bin / "probes.log"
        result = self.job("gpt6-probe", last=LAST, events=[COMPLETED],
                          quota={"log": str(probes), "result": quota_answer(99)})
        self.assertEqual((result["exit"], result["limit_marker"], result["quota"]), (0, False, None))
        self.assertFalse(probes.exists())

    def test_below_the_stop_percent_the_job_runs_and_the_probe_is_recorded(self):
        self.settings({"quota_stop_percent": 95})
        probes = self.bin / "probes.log"
        result = self.job("gpt6-probe", last=LAST, events=[COMPLETED],
                          quota={"log": str(probes), "result": quota_answer(63)})
        self.assertEqual((result["exit"], result["limit_marker"]), (0, False))
        self.assertEqual(probes.read_text().count("probe"), 1)
        self.assertEqual({k: result["quota"][k] for k in ("status", "stop_percent", "used_percent", "resets_at_utc")},
                         {"status": "ok", "stop_percent": 95.0, "used_percent": 63,
                          "resets_at_utc": "2026-10-03T01:28Z"})
        self.assertTrue((self.bin / "record.json").exists())  # codex exec ran
        self.assertNotIn("acct-fixture", (self.work / "gpt6" / "gpt6-probe" / "quota.json").read_text())

    def test_the_stop_percent_keeps_its_precision(self):
        # GPT-6 review of #348: '{:g}' turned 95.00001 into 95 and refused a snapshot at exactly 95.
        self.settings({"quota_stop_percent": 95.00001})
        result = self.job("gpt6-precise", last=LAST, events=[COMPLETED], quota={"result": quota_answer(95)})
        self.assertEqual((result["exit"], result["limit_marker"]), (0, False))
        self.assertEqual(result["quota"]["status"], "ok")

    def test_reaching_the_stop_percent_refuses_like_a_usage_limit(self):
        self.settings({"quota_stop_percent": 95})
        result = self.job("gpt6-fit-alpha", last=LAST, events=[COMPLETED], quota={"result": quota_answer(96)})
        self.assertEqual((result["exit"], result["limit"], result["limit_marker"], result["started"]),
                         (3, False, True, None))
        self.assertFalse((self.bin / "record.json").exists())  # codex exec never started
        self.assertEqual(result["failure"]["kind"], "quota")
        limit = (self.work / "LIMIT").read_text()
        self.assertTrue(limit.startswith("quota gate: primary window 96% used >= 95% (window 10080 min, resets "
                                         "2026-10-03T01:28Z); codex.quota_stop_percent 95; checked "), limit)
        self.assertIn("before gpt6-fit-alpha started", limit)
        self.assertIn("quota gate: primary window 96%", result["stderr_tail"])
        self.assertEqual((result["quota"]["status"], result["quota"]["reasons"][0][:30]),
                         ("gate", "primary window 96% used >= 95%"))
        refused = self.call("start", "gpt6-fit-beta", self.prompt, self.schema)
        self.assertEqual(refused.returncode, 3)
        self.assertEqual(refused.stdout.splitlines()[0], "LIMIT marker present; refusing to start gpt6-fit-beta")
        self.assertTrue(refused.stdout.splitlines()[1].startswith("LIMIT: quota gate: primary window 96%"))
        # After the user's reset the coordinator removes LIMIT; the job runs and the refused attempt stays counted.
        (self.work / "LIMIT").unlink()
        rerun = self.job("gpt6-fit-alpha", last=LAST, events=[COMPLETED], quota={"result": quota_answer(4)})
        self.assertEqual((rerun["exit"], rerun["quota"]["used_percent"]), (0, 4))
        self.assertEqual([(a["attempt"], a["exit"], a["usage_status"]) for a in rerun["attempts"]],
                         [(1, 3, "unavailable")])
        kept = json.loads((self.work / "gpt6" / "gpt6-fit-alpha" / "attempts" / "1" / "quota.json").read_text())
        self.assertEqual(kept["status"], "gate")

    def test_a_limit_flag_reaches_the_gate_below_the_percent(self):
        self.settings({"quota_stop_percent": 95})
        result = self.job("gpt6-flagged", quota={"result": quota_answer(10, reached="rate_limit_reached")})
        self.assertEqual(result["exit"], 3)
        self.assertIn("rateLimitReachedType rate_limit_reached", (self.work / "LIMIT").read_text())

    def test_an_existing_marker_keeps_its_reason(self):
        self.settings({"quota_stop_percent": 95})
        codex_job.mark_limit(self.work, "first reason")
        codex_job.mark_limit(self.work, "second reason")
        self.assertEqual((self.work / "LIMIT").read_text(), "first reason\n")

    def test_a_failed_probe_is_recorded_and_never_blocks_the_job(self):
        self.settings({"quota_stop_percent": 95, "quota_timeout_s": 5})
        error = {"code": -32600, "message": "codex account authentication required to read rate limits"}
        result = self.job("gpt6-probe", last=LAST, events=[COMPLETED], quota={"error": error})
        self.assertEqual((result["exit"], result["limit_marker"]), (0, False))
        self.assertEqual(result["quota"]["status"], "probe_failed")
        # The server's text is never recorded (backend errors can carry account ids).
        self.assertEqual(result["quota"]["error"], "account/rateLimits/read: the server answered with an error")
        self.assertNotIn(error["message"], (self.work / "gpt6" / "gpt6-probe" / "quota.json").read_text())
        self.assertTrue((self.bin / "record.json").exists())

    def test_a_missing_probe_is_recorded_and_never_blocks_the_job(self):
        staged = temp_dir(self)
        write_json(staged / "staged.json", {"codex": {}})
        self.assertIsNone(codex_job.quota_script(staged))  # a staged runner never reaches into another checkout
        (staged / "codex_quota.py").write_text("", encoding="utf-8")
        self.assertEqual(codex_job.quota_script(staged), staged / "codex_quota.py")
        self.assertEqual(codex_job.quota_script(HARNESS), ROOT / "scripts" / "codex_quota.py")
        directory = self.work / "gpt6" / "unit"
        directory.mkdir(parents=True)
        (self.work / "empty").mkdir(exist_ok=True)
        config = {"quota_stop_percent": 95.0, "quota_timeout_s": 5.0}
        original = codex_job.quota_script
        codex_job.quota_script = lambda: None
        self.addCleanup(setattr, codex_job, "quota_script", original)
        self.assertIsNone(codex_job.quota_gate(self.work, directory, config))
        record = json.loads((directory / "quota.json").read_text())
        self.assertEqual(record["status"], "probe_failed")
        self.assertIn("codex_quota.py", record["error"])

    def test_bad_stop_percents_are_refused_before_anything_changes(self):
        for bad in (0, 101, "95", True):
            with self.subTest(bad):
                self.settings({"quota_stop_percent": bad})
                done = self.call("start", "gpt6-x", self.prompt, self.schema)
                self.assertEqual(done.returncode, 2)
                self.assertIn("quota_stop_percent", done.stderr)
                self.assertFalse((self.work / "gpt6" / "gpt6-x").exists())


class ShellTests(RunnerCase):
    def test_bash_syntax(self):
        done = run(["bash", "-n", HARNESS / "codex_call.sh"])
        self.assertEqual(done.returncode, 0, done.stderr)

    @unittest.skipUnless(SHELLCHECK, "shellcheck is not installed")
    def test_shellcheck(self):
        done = run([SHELLCHECK, HARNESS / "codex_call.sh"])
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    @unittest.skipUnless(BASH32, "no real bash 3.2 binary (set BASH32_BINARY, or run on a Mac)")
    def test_runs_under_bash_3_2(self):
        result = self.job("gpt6-probe", shell=BASH32, last=LAST, events=[COMPLETED])
        self.assertEqual(result["exit"], 0)

    def test_staged_copy_needs_no_work_dir_argument(self):
        work = stage_work(self, ("alpha",))
        self.assertEqual(build(work).returncode, 0)
        self.fake(last=LAST, events=[COMPLETED])
        write_json(work / "staged.json", {**json.loads((work / "staged.json").read_text()),
                                          "codex": {"wait_poll_s": 0.05, "slot_poll_s": 0.05}})
        env = dict(self.env, SWEEP_WORK_DIR=str(self.work))  # ignored: the staged copy uses its own directory
        started = run(["bash", work / "codex_call.sh", "start", "gpt6-probe", work / "prompts/gpt6-probe.txt",
                       work / "schemas/probe.json"], env=env)
        self.assertEqual(started.returncode, 0, started.stderr)
        run(["bash", work / "codex_call.sh", "wait", "gpt6-probe", "20"], env=env)
        self.assertTrue((work / "gpt6/gpt6-probe/done").exists())
        self.assertFalse((self.work / "gpt6").exists())
        prompt = run([sys.executable, work / "make_prompt.py", "discover", work / "inputs/alpha.json"], env=env)
        self.assertEqual(prompt.stdout, (work / "prompts/gpt6-discover-alpha.txt").read_text())

    def test_staged_quota_gate_uses_the_staged_probe(self):
        work = stage_work(self, ("alpha",))
        self.assertEqual(build(work, "--quota-stop-percent", "90").returncode, 0)
        staged = json.loads((work / "staged.json").read_text())
        self.assertEqual(staged["codex"]["quota_stop_percent"], 90.0)
        write_json(work / "staged.json", {**staged, "codex": {**staged["codex"], "wait_poll_s": 0.05,
                                                             "slot_poll_s": 0.05}})
        self.fake(last=LAST, quota={"result": quota_answer(91)})
        started = run(["bash", work / "codex_call.sh", "start", "gpt6-probe", work / "prompts/gpt6-probe.txt",
                       work / "schemas/probe.json"], env=self.env)
        self.assertEqual(started.returncode, 0, started.stderr)
        run(["bash", work / "codex_call.sh", "wait", "gpt6-probe", "20"], env=self.env)
        self.assertEqual((work / "gpt6/gpt6-probe/exit").read_text().strip(), "3")
        self.assertIn("primary window 91% used >= 90%", (work / "LIMIT").read_text())
        for bad in ("0", "100.5", "nan"):
            done = build(stage_work(self, ("alpha",)), "--quota-stop-percent", bad)
            self.assertEqual(done.returncode, 2, bad)
            self.assertIn("--quota-stop-percent", done.stderr)


# --------------------------------------------------------------------------- convert


class ConvertTests(unittest.TestCase):
    def test_route_provenance_survives_the_wrappers_fixed_field_copy(self):
        work = temp_dir(self)
        res = healthy_result()
        route = {"provider": "omniroute", "fallback_from": "native", "reason": "native usage limit",
                 "native_model": "gpt-6-astra", "gateway_model": "cx/gpt-6-astra-max", "native_attempt": 1,
                 "search_backend": "omniroute:/alpha/search"}
        # The workflow does not copy result.route; conversion must read the runner's original sibling receipt.
        res["first"][0]["fit_gpt6"]["model"] = "cx/gpt-6-astra-max"
        self.assertNotIn("route", res["first"][0]["fit_gpt6"])
        write_codex_files(work, res)
        write_json(work / "gpt6/gpt6-fit-alpha/route.json", route)
        out = self.convert(res, work=work)
        self.assertEqual(out["returns"]["raw"]["alpha"]["first"]["gpt6_routes"], {"fit": route})
        self.assertEqual(out["returns"]["votes"]["alpha"][0]["fit"]["gpt6"]["route"], route)
        self.assertIn("cx/gpt-6-astra-max", out["lanes"]["lanes"][0]["result"]["limits"][0])
        self.assertTrue(any("/alpha/search" in text for text in out["lanes"]["lanes"][0]["result"]["limits"]))

    def convert(self, res=None, models=None, work=None):
        return convert.convert(res or synthetic_result(), scope_for(), "landscape-sweep-20261026",
                               models or convert.resolved_models(None), work)

    def test_two_family_survival_and_missing_votes(self):
        out = self.convert()
        layers = {layer["layer_id"]: layer for layer in out["layers"]}
        canon = sweep_common.canon
        self.assertEqual([e["repo"] for e in layers["alpha"]["survived"]], [canon(A1), canon(A4)])
        self.assertEqual([e["repo"] for e in layers["alpha"]["refuted"]], [canon(A2_CLAUDE), canon(A3)])
        votes_alpha = {v["fit"]["repository"]: v for v in out["returns"]["votes"]["alpha"]}
        a2 = votes_alpha["https://github.com/o/alpha-two"]
        self.assertEqual((a2["facts"]["refuted"], a2["fit"]["claude"]["refuted"], a2["fit"]["gpt6"]["refuted"],
                          a2["fit"]["refuted"]), (False, False, True, True))
        a3 = votes_alpha["https://github.com/o/alpha-three"]
        self.assertIn("GPT-6 fit vote missing (counted as refuted)", a3["fit"]["notes"])
        self.assertTrue(a3["fit"]["gpt6"]["missing"])
        self.assertEqual([e["repo"] for e in layers["beta"]["survived"]], [B2])
        b1 = out["returns"]["votes"]["beta"][0]
        self.assertEqual((b1["facts"]["repository"], b1["facts"]["refuted"]), (B1, True))
        self.assertIn("facts vote missing (counted as refuted)", b1["facts"]["notes"])
        # Refuted by absence: B1 has only a missing facts vote against it; A3's facts vote refutes it on merit.
        self.assertTrue(b1["facts"]["missing"])
        self.assertNotIn("missing", a3["facts"])
        self.assertEqual(out["summary"]["refuted_by_absence"], {"beta": ["o/beta-one"]})
        self.assertNotIn("votes_note", layers["alpha"])
        self.assertIn("1 of 2 proposals are refuted only because a vote did not return (facts;", layers["beta"]["votes_note"])
        self.assertTrue(layers["beta"]["votes_note"].endswith("not adjudicated: o/beta-one."))
        # Every GPT-6 fit vote missing: A1, A2 and A4 pass facts and the Claude fit refuter, so they are refuted by
        # absence; A3 stays refuted on merit by facts.
        failed = self.convert(fail_gpt6_fit(synthetic_result()))
        self.assertEqual(failed["summary"]["refuted_by_absence"]["alpha"], ["o/alpha-two", "owner/alpha-one", "o/alpha-four"])
        self.assertIn("(GPT-6 fit;", {x["layer_id"]: x for x in failed["layers"]}["alpha"]["votes_note"])
        self.assertEqual(out["survivors"], [{"layer_id": "alpha", "repository": canon(A1)},
                                            {"layer_id": "alpha", "repository": canon(A4)},
                                            {"layer_id": "beta", "repository": B2}])

    def test_canonical_urls_and_discovery_equals_the_voted_set(self):
        out = self.convert()
        self.assertEqual(out["returns"]["discovery"]["alpha"]["proposed"], [
            "https://github.com/o/alpha-two", "https://github.com/owner/alpha-one",
            "https://github.com/o/alpha-three", "https://github.com/o/alpha-four"])
        for layer in out["layers"]:
            voted = [v["facts"]["repository"] for v in out["returns"]["votes"][layer["layer_id"]]]
            self.assertEqual(out["returns"]["discovery"][layer["layer_id"]]["proposed"], voted)
            self.assertEqual(layer["proposed"], voted)
            self.assertEqual(sorted(e["repo"] for e in layer["survived"] + layer["refuted"]), sorted(voted))
        self.assertEqual(out["returns"]["discovery"]["alpha"]["families"]["https://github.com/o/alpha-two"],
                         ["claude", "gpt6"])

    def test_refs_point_into_returns_as_the_ledger_resolves_them(self):
        out = self.convert()
        returns = out["returns"]
        for layer in out["layers"]:
            path, _, pointer = layer["discovery_ref"].partition("#")
            self.assertEqual(path, "@RETURNS@")
            target = sl.resolve_pointer(returns, pointer)
            self.assertEqual((target["catalog"], target["layer_id"]), (layer["catalog"], layer["layer_id"]))
            self.assertEqual((target["requirement_sha256"], target["platform_profiles_sha256"]), (REQ, PLAT))
            for field in ("survived", "refuted"):
                for entry in layer[field]:
                    self.assertEqual(sl.entry_survives(entry), field == "survived")
                    for role in ("facts", "fit"):
                        path, _, pointer = entry[role]["ref"].partition("#")
                        self.assertEqual(path, "@RETURNS@")
                        vote = sl.resolve_pointer(returns, pointer)
                        self.assertEqual(vote["role"], role)
                        self.assertEqual(sl.norm_repo(vote["repository"]), sl.norm_repo(entry["repo"]))
                        self.assertEqual(vote["refuted"], entry[role]["vote"] == "refuted")

    def test_raw_rounds_dropped_proposals_lost_layers_and_degraded_discovery(self):
        out = self.convert()
        raw = out["returns"]["raw"]
        self.assertEqual(raw["alpha"]["first"]["dropped"], synthetic_result()["first"][0]["dropped"])
        self.assertEqual(sorted(raw["beta"]), ["first", "followup"])
        self.assertEqual(raw["beta"]["followup"]["followup_reason"]["reason"], "missed a class")
        self.assertNotIn("gamma", out["returns"]["discovery"])  # never a clean layer with no proposals
        self.assertEqual([layer["layer_id"] for layer in out["layers"]], ["alpha", "beta"])
        summary = out["summary"]
        self.assertEqual((summary["lost"], summary["excluded_layers"], summary["degraded_discovery"]),
                         (["gamma:first"], ["gamma"], ["beta:first"]))
        self.assertEqual(out["returns"]["discovery"]["beta"]["families_returned"],
                         {"first": ["claude"], "followup": ["claude", "gpt6"]})
        self.assertEqual(out["lanes"]["lost"], ["gamma:first"])

    def test_skills_usage_calls_models_and_lanes(self):
        out = self.convert()
        self.assertEqual(out["returns"]["skills_usage"], {
            "discover_claude": {"search-first": 1, "iterative-retrieval": 1},
            "discover_gpt6": {"search-first": 1},
            "facts": {"verification-before-completion": 1, "supply-chain-risk-auditor": 1},
            "fit_claude": {"fp-check": 1}, "fit_gpt6": {"verification-before-completion": 1}})
        facts_b2 = out["returns"]["votes"]["beta"][1]["facts"]
        self.assertEqual(facts_b2["skills_used"], ["supply-chain-risk-auditor"])  # its own round's skills
        alpha_calls = out["layers"][0]["calls"]
        self.assertEqual(alpha_calls, {"web_search": 3, "web_fetch": 2, "gh_api": 20,
                                       "gpt6_web_search": 4, "gpt6_web_fetch": 5, "gpt6_gh_api": 6})
        self.assertEqual((out["returns"]["gpt6_usage"]["jobs"], out["returns"]["gpt6_usage"]["by_status"]),
                         (6, {"ok": 5, "failed_exit_1": 1}))
        lane = out["lanes"]["lanes"][0]
        self.assertEqual(lane["lane"], "landscape-sweep-20261026")
        self.assertEqual(len(lane["proposals"]), 6)
        self.assertTrue(all(len(p["votes"]) == 3 for p in lane["proposals"]))
        self.assertEqual(sum(p["survives"] for p in lane["proposals"]), 3)
        self.assertTrue(any("capped at 8 per layer" in limit for limit in lane["result"]["limits"]))
        # Without a usage record the vote objects name the requested aliases, never a guessed model.
        self.assertEqual(out["returns"]["votes"]["alpha"][0]["facts"]["model"], "opus")

    def test_resolved_models_come_from_the_usage_record(self):
        document = usage_record.record(child_usage_raw("wf_fixture-1", SYNTHETIC_LABELS), 0, "cmd", ROOT)
        models = convert.resolved_models(document)
        self.assertEqual(models, {"discover": "claude-opus-5-5", "refute-facts": "claude-opus-5-5",
                                  "refute-fit": "claude-opus-5-5", "critic": "claude-opus-5-5"})
        out = self.convert(models=models)
        vote = out["returns"]["votes"]["alpha"][0]
        self.assertEqual((vote["facts"]["model"], vote["fit"]["claude"]["model"], vote["fit"]["gpt6"]["model"]),
                         ("claude-opus-5-5", "claude-opus-5-5", "gpt-6-astra"))

    def test_failed_gpt6_fit_lanes_reopen_every_affected_layer(self):
        out = self.convert(fail_gpt6_fit(synthetic_result()))
        self.assertEqual(out["survivors"], [])  # every proposal lacks its GPT-6 fit vote, so each counts as refuted
        for layer in out["layers"]:
            layer_id = layer["layer_id"]
            self.assertEqual(layer["reopen"], [{"trigger": "retained_failure", "ref": f"@RETURNS@#/failures/{layer_id}"}])
            failures = sl.resolve_pointer(out["returns"], f"/failures/{layer_id}")
            gpt6 = [f for f in failures if f["cause"] == "vote_missing" and f["role"] == "fit_gpt6"]
            self.assertTrue(gpt6, layer_id)
            self.assertTrue(all(f["status"] == "failed_exit_1" for f in gpt6))
            voted = {r for f in gpt6 for r in f["repositories"]}
            self.assertEqual(voted, set(layer["proposed"]))
        self.assertEqual(out["summary"]["reopened_layers"], ["alpha", "beta"])

    def test_only_a_layer_with_retained_failures_is_reopened(self):
        out = self.convert(healthy_result())
        self.assertEqual((out["layers"][0]["reopen"], out["returns"]["failures"]), ([], {}))
        out = self.convert()
        # alpha: A3 has no GPT-6 fit vote; beta: the first round lacks the GPT-6 discovery and B1's facts vote.
        self.assertEqual(out["summary"]["retained_failures"], {
            "alpha": ["first:vote_missing"],
            "beta": ["first:discovery_missing", "first:vote_missing"]})
        beta = out["returns"]["failures"]["beta"]
        self.assertEqual((beta[0]["family"], beta[0]["status"]), ("gpt6", "failed_exit_1"))
        self.assertEqual((beta[1]["role"], beta[1]["repositories"]), ("facts", [B1]))

    def test_a_reproposal_takes_the_later_rounds_proposal_and_all_three_votes(self):
        x = "https://github.com/o/x"

        def layer_round(rnd, label, facts, fit_claude, fit_gpt6):
            return {"layer_id": "alpha", "catalog": "foundation", "round": rnd,
                    "followup_reason": {"reason": "r"} if rnd == "followup" else None,
                    "claude_discover": discovery("alpha", [x]), "gpt6_discover": gpt6_entry(discovery("alpha", [x])),
                    "merged": [merged_row(x, ["claude", "gpt6"], label)], "dropped": [],
                    "facts": facts, "fit_claude": fit_claude, "fit_gpt6": fit_gpt6}

        critic = {"followup_layers": [{"layer_id": "alpha", "reason": "r", "search_directions": []}], "general": []}
        # (a) refuted as a targeted_candidate, proposed again as keep_but_compare and passed by all three refuters
        first = layer_round("first", "targeted_candidate", votes("alpha", "facts", {x: False}),
                            votes("alpha", "fit", {x: True}), gpt6_entry(votes("alpha", "fit", {x: True})))
        follow = layer_round("followup", "keep_but_compare", votes("alpha", "facts", {x: False}),
                             votes("alpha", "fit", {x: False}), gpt6_entry(votes("alpha", "fit", {x: False})))
        follow["fit_claude"]["votes"][0]["reasoning"] = "follow-up fit"
        out = self.convert({"sweep": LANE, "first": [first], "critic": critic, "followups": [follow]})
        self.assertEqual(out["returns"]["discovery"]["alpha"]["proposed"], [x])
        self.assertEqual([e["repo"] for e in out["layers"][0]["survived"]], [x])
        candidate = out["lanes"]["lanes"][0]["result"]["layers"][0]["new_candidates"][0]
        self.assertEqual((candidate["proposed_label"], candidate["demonstrated_gap"]), ("keep_but_compare", f"gap of {x}"))
        vote = out["returns"]["votes"]["alpha"][0]
        self.assertEqual((vote["facts"]["round"], vote["fit"]["round"], vote["fit"]["claude"]["reasoning"]),
                         ("followup", "followup", "follow-up fit"))
        self.assertEqual(out["returns"]["failures"], {})
        # (b) the follow-up's Claude fit refuter returned nothing: the round-1 Claude vote is never reused
        first = layer_round("first", "keep_but_compare", votes("alpha", "facts", {x: False}),
                            votes("alpha", "fit", {x: False}), gpt6_entry(votes("alpha", "fit", {x: True})))
        follow = layer_round("followup", "keep_but_compare", votes("alpha", "facts", {x: False}), None,
                             gpt6_entry(votes("alpha", "fit", {x: False})))
        out = self.convert({"sweep": LANE, "first": [first], "critic": critic, "followups": [follow]})
        self.assertEqual([e["repo"] for e in out["layers"][0]["refuted"]], [x])
        vote = out["returns"]["votes"]["alpha"][0]
        self.assertTrue(vote["fit"]["claude"]["missing"])
        self.assertEqual((vote["fit"]["gpt6"]["refuted"], vote["fit"]["refuted"]), (False, True))
        self.assertIn("Claude fit vote missing (counted as refuted)", vote["fit"]["notes"])
        self.assertEqual([(f["round"], f["cause"], f["role"]) for f in out["returns"]["failures"]["alpha"]],
                         [("followup", "vote_missing", "fit_claude")])
        self.assertEqual(out["layers"][0]["reopen"][0]["trigger"], "retained_failure")
        # (c) GPT-6 review of #324: the first round's GPT-6 fit job failed, and the follow-up re-proposed x with all
        # three votes. The later votes decide x, but the first round's missing vote stays a retained failure.
        first = layer_round("first", "keep_but_compare", votes("alpha", "facts", {x: False}),
                            votes("alpha", "fit", {x: False}), gpt6_entry(None, "failed_exit_1"))
        follow = layer_round("followup", "keep_but_compare", votes("alpha", "facts", {x: False}),
                             votes("alpha", "fit", {x: False}), gpt6_entry(votes("alpha", "fit", {x: False})))
        out = self.convert({"sweep": LANE, "first": [first], "critic": critic, "followups": [follow]})
        self.assertEqual([e["repo"] for e in out["layers"][0]["survived"]], [x])
        failures = out["returns"]["failures"]["alpha"]
        self.assertEqual([(f["round"], f["cause"], f.get("role"), f.get("status")) for f in failures],
                         [("first", "vote_missing", "fit_gpt6", "failed_exit_1")])
        self.assertEqual(failures[0]["repositories"], [x])
        self.assertEqual(out["layers"][0]["reopen"][0]["trigger"], "retained_failure")

    def test_gpt6_usage_counts_every_attempt(self):
        res = healthy_result()
        fit = res["first"][0]["fit_gpt6"]
        fit["usage_status"] = "reported"
        fit["attempts"] = [{"attempt": 1, "exit": 1, "usage": None, "usage_status": "unavailable"},
                           {"attempt": 2, "exit": 0, "usage": {"input_tokens": 5, "output_tokens": 2},
                            "usage_status": "reported"}]
        usage = self.convert(res)["returns"]["gpt6_usage"]
        self.assertEqual(usage["earlier_attempts"], {"attempts": 2, "usage": {"input_tokens": 5, "output_tokens": 2},
                                                     "usage_unavailable": 1})
        self.assertEqual(usage["usage"]["input_tokens"], 2000)  # the final attempts of the two jobs
        self.assertEqual(usage["usage_unavailable"], 0)

    def test_a_vote_refutes_unless_it_says_false(self):
        res = healthy_result()
        alpha = res["first"][0]
        alpha["facts"] = votes("alpha", "facts", {A1: False, A4: False})
        alpha["facts"]["votes"][1]["refuted"] = None  # A4: no boolean (a falsy value never passes a proposal)
        alpha["fit_claude"] = votes("alpha", "fit", {A1: True, A4: False})
        alpha["fit_claude"]["votes"].append(dict(alpha["fit_claude"]["votes"][0], refuted=False))  # A1 voted twice
        out = self.convert(res)
        votes_alpha = {v["facts"]["repository"]: v for v in out["returns"]["votes"]["alpha"]}
        self.assertTrue(votes_alpha[sweep_common.canon(A4)]["facts"]["refuted"])
        self.assertTrue(votes_alpha[sweep_common.canon(A1)]["fit"]["claude"]["refuted"])  # the refuting vote wins
        self.assertEqual(out["survivors"], [])

    def test_lost_and_unrun_followups_and_a_lost_critic_are_retained_failures(self):
        res = synthetic_result()
        res["followups"] = [None]  # a lost follow-up round, as the prototype returned it
        out = self.convert(res)
        self.assertIn("beta:followup", out["summary"]["lost"])
        self.assertEqual(out["returns"]["raw"]["beta"]["followup"]["lost"], True)
        self.assertIn("followup:round_lost", out["summary"]["retained_failures"]["beta"])
        self.assertEqual(out["returns"]["discovery"]["beta"]["proposed"], [B1])  # the first round only
        unattributed = dict(synthetic_result(), followups=[None])
        del unattributed["critic"]
        with self.assertRaisesRegex(ValueError, "no critic"):
            self.convert(unattributed)
        with self.assertRaisesRegex(ValueError, "do not match the critic"):
            self.convert(dict(synthetic_result(), followups=[]))
        out = self.convert(dict(synthetic_result(), critic=None, followups=[]))
        self.assertTrue(out["summary"]["critic_lost"])
        for layer in out["layers"]:
            self.assertIn("critic:critic_lost", out["summary"]["retained_failures"][layer["layer_id"]])
        # A critic-flagged layer beyond the follow-up cap got no round: it cannot count as clean either.
        ids = [f"layer-{i}" for i in range(convert.FOLLOWUP_CAP + 1)]

        def empty_round(layer_id, rnd):
            return {"layer_id": layer_id, "catalog": "foundation", "round": rnd, "followup_reason": None,
                    "claude_discover": discovery(layer_id, []), "gpt6_discover": gpt6_entry(discovery(layer_id, [])),
                    "merged": [], "dropped": [], "facts": None, "fit_claude": None, "fit_gpt6": None}

        critic = {"followup_layers": [{"layer_id": i, "reason": "r", "search_directions": []} for i in ids], "general": []}
        res = {"sweep": LANE, "first": [empty_round(i, "first") for i in ids], "critic": critic,
               "followups": [empty_round(i, "followup") for i in ids[:convert.FOLLOWUP_CAP]]}
        out = convert.convert(res, scope_for([("foundation", i) for i in ids]), LANE, convert.resolved_models(None))
        self.assertEqual(out["summary"]["retained_failures"], {ids[-1]: ["critic:followup_not_run"]})

    def test_vote_models_and_efforts_come_from_each_workers_usage(self):
        document = usage_record.record(child_usage_raw("wf_fixture-1", SYNTHETIC_LABELS), 0, "cmd", ROOT)
        for child in document["child_usage"]["children"]:
            if child["label"] == "refute-fit:alpha":
                child["efforts"] = ["xhigh"]
        out = convert.convert(synthetic_result(), scope_for(), LANE, convert.resolved_models(document), usage=document)
        vote = out["returns"]["votes"]["alpha"][0]
        self.assertEqual((vote["facts"]["effort"], vote["fit"]["claude"]["effort"], vote["fit"]["gpt6"]["effort"]),
                         ("max", "xhigh", "max"))
        followup_vote = out["returns"]["votes"]["beta"][1]
        self.assertEqual((followup_vote["facts"]["round"], followup_vote["facts"]["effort"],
                          followup_vote["facts"]["model"]), ("followup", "max", "claude-opus-5-5"))
        # Without a usage record nothing was measured: the requested alias, and effort null rather than a claimed max.
        vote = self.convert()["returns"]["votes"]["alpha"][0]
        self.assertEqual((vote["facts"]["model"], vote["facts"]["effort"], vote["fit"]["claude"]["effort"]),
                         ("opus", None, None))

    def test_a_rerun_workers_vote_is_measured_by_the_attempt_that_returned(self):
        # A record listing a re-run call's earlier attempt among its children (child-usage.mjs before
        # superseded_attempts): the vote names the attempt that returned, and <synthetic> is never a model.
        failed = {"label": "refute-fit:alpha", "agent_id": "x1", "requested_model": "opus",
                  "resolved_models": ["claude-opus-5-5", "<synthetic>"], "efforts": ["max"], "complete": False}
        raw = json.loads(child_usage_raw("wf_fixture-1", SYNTHETIC_LABELS))
        raw["children"].insert(0, failed)
        document = usage_record.record(json.dumps(raw).encode("utf-8"), 1, "cmd", ROOT)
        models = convert.resolved_models(document)
        self.assertEqual(models["refute-fit"], "claude-opus-5-5")
        out = convert.convert(synthetic_result(), scope_for(), LANE, models, usage=document)
        self.assertEqual(out["returns"]["votes"]["alpha"][0]["fit"]["claude"]["model"], "claude-opus-5-5")
        # The current tool lists that attempt under superseded_attempts: never a vote's worker, still effort-checked.
        raw = json.loads(child_usage_raw("wf_fixture-1", SYNTHETIC_LABELS))
        raw["superseded_attempts"] = [dict(failed, superseded_by="x2")]
        document = usage_record.record(json.dumps(raw).encode("utf-8"), 0, "cmd", ROOT)
        out = convert.convert(synthetic_result(), scope_for(), LANE, convert.resolved_models(document), usage=document)
        self.assertEqual(out["returns"]["votes"]["alpha"][0]["fit"]["claude"]["model"], "claude-opus-5-5")
        self.assertEqual(out["summary"]["effort_deviations"], [])

    def test_a_worker_at_another_effort_is_a_retained_failure_of_its_layer(self):
        # A skill whose frontmatter sets `effort: low` lowers the turns after it loads; child-usage.mjs measures it.
        raw = json.loads(child_usage_raw("wf_fixture-1", SYNTHETIC_LABELS))
        for child in raw["children"]:
            if child["label"] in ("discover:alpha", "refute-fit:beta:followup"):
                child["efforts"] = ["max", "low"]
        raw["superseded_attempts"] = [{"label": "refute-facts:alpha", "agent_id": "x1", "superseded_by": "x2",
                                       "efforts": ["xhigh"], "complete": False}]
        document = usage_record.record(json.dumps(raw).encode("utf-8"), 1, "cmd", ROOT)
        out = convert.convert(synthetic_result(), scope_for(), LANE, convert.resolved_models(document), usage=document)
        self.assertEqual(out["summary"]["effort_deviations"],
                         ["discover:alpha", "refute-fit:beta:followup", "refute-facts:alpha"])
        found = {layer_id: [(f["round"], f["child"], f["efforts"]) for f in failures if f["cause"] == "effort_deviation"]
                 for layer_id, failures in out["returns"]["failures"].items()}
        self.assertEqual(found["alpha"], [("first", "discover:alpha", ["max", "low"]),
                                          ("first", "refute-facts:alpha", ["xhigh"])])
        self.assertEqual(found["beta"], [("followup", "refute-fit:beta:followup", ["max", "low"])])
        self.assertEqual(out["returns"]["votes"]["beta"][1]["fit"]["claude"]["effort"], "low+max")
        # A deviation alone reopens a healthy layer; the critic's belongs to every layer; an unknown layer's is listed.
        raw = json.loads(child_usage_raw("wf_fixture-1", SYNTHETIC_LABELS + ["refute-fit:zeta"]))
        for child in raw["children"]:
            if child["label"] in ("critic", "refute-fit:zeta"):
                child["efforts"] = ["xhigh"]
        document = usage_record.record(json.dumps(raw).encode("utf-8"), 1, "cmd", ROOT)
        out = convert.convert(healthy_result(), scope_for(), LANE, convert.resolved_models(document), usage=document)
        self.assertEqual(out["summary"]["retained_failures"], {"alpha": ["critic:effort_deviation"]})
        self.assertEqual(out["summary"]["effort_deviations_unmapped"], ["refute-fit:zeta"])
        self.assertEqual(out["layers"][0]["reopen"], [{"trigger": "retained_failure",
                                                       "ref": "@RETURNS@#/failures/alpha"}])

    def test_a_worker_with_a_capped_web_search_is_a_retained_failure_of_its_layer(self):
        # The session's WebSearch cap (CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION): child-usage.mjs counts capped calls.
        raw = json.loads(child_usage_raw("wf_fixture-1", SYNTHETIC_LABELS + ["refute-fit:zeta"]))
        capped = {"refute-fit:beta:followup": 2, "refute-facts:alpha": 1, "refute-fit:zeta": 1}
        for child in raw["children"]:
            if child["label"] in capped:
                child["web_search"] = {"calls": 3, "capped": capped[child["label"]],
                                       "first_capped_at": "2026-10-26T04:10:13Z"}
        document = usage_record.record(json.dumps(raw).encode("utf-8"), 0, "cmd", ROOT)
        out = convert.convert(synthetic_result(), scope_for(), LANE, convert.resolved_models(document), usage=document)
        self.assertEqual(out["summary"]["web_search_capped"],
                         ["refute-facts:alpha", "refute-fit:beta:followup", "refute-fit:zeta"])
        self.assertEqual(out["summary"]["web_search_capped_unmapped"], ["refute-fit:zeta"])
        found = {layer_id: [(f["round"], f["child"], f["capped"]) for f in failures if f["cause"] == "web_search_capped"]
                 for layer_id, failures in out["returns"]["failures"].items()}
        self.assertEqual(found, {"alpha": [("first", "refute-facts:alpha", 1)],
                                 "beta": [("followup", "refute-fit:beta:followup", 2)]})
        # A capped worker alone reopens a healthy layer, and the critic's cap counts for every layer.
        raw = json.loads(child_usage_raw("wf_fixture-1", SYNTHETIC_LABELS))
        next(c for c in raw["children"] if c["label"] == "critic")["web_search"] = {
            "calls": 2, "capped": 2, "first_capped_at": "2026-10-26T11:06:45Z"}
        document = usage_record.record(json.dumps(raw).encode("utf-8"), 0, "cmd", ROOT)
        out = convert.convert(healthy_result(), scope_for(), LANE, convert.resolved_models(document), usage=document)
        self.assertEqual(out["summary"]["retained_failures"], {"alpha": ["critic:web_search_capped"]})
        self.assertEqual(out["layers"][0]["reopen"], [{"trigger": "retained_failure",
                                                       "ref": "@RETURNS@#/failures/alpha"}])

    def cli(self, work, res, *extra, codex_files=True):
        run_file = write_json(work / "run.json", {"runId": "wf_fixture-1", "status": "completed", "result": res})
        write_json(work / "scope.json", scope_for())
        if codex_files:
            write_codex_files(work, res)
        return run([sys.executable, HARNESS / "convert.py", "--workflow-output", run_file, "--work-dir", work,
                    "--out", work / "out", *extra])

    def test_cli_sanitizes_host_paths_and_flags_private_content(self):
        work = temp_dir(self)
        res = synthetic_result()
        res["first"][0]["claude_discover"]["notes"] = f"read {work}/inputs/alpha.json"
        done = self.cli(work, res, "--limit", "run note")
        self.assertEqual(done.returncode, 0, done.stderr)
        returns = json.loads((work / "out/returns.json").read_text())
        self.assertEqual(returns["raw"]["alpha"]["first"]["claude_discover"]["notes"], "read <work-dir>/inputs/alpha.json")
        self.assertEqual(returns["workflow_run"], "wf_fixture-1")
        lanes = json.loads((work / "out/lanes.json").read_text())
        self.assertEqual(lanes["lanes"][0]["result"]["limits"][-1], "run note")
        identifier = "-".join(["0123abcd", "4567", "89ab", "cdef", "0123456789ab"])
        res["first"][0]["claude_discover"]["notes"] = f"session {identifier}"
        done = self.cli(work, res)
        self.assertEqual(done.returncode, 3)
        self.assertIn("returns.json#/raw/alpha/first/claude_discover/notes: local session identifier", done.stderr)
        self.assertNotIn(identifier, done.stderr + done.stdout)

    def test_cli_compares_each_gpt6_output_with_the_file_codex_wrote(self):
        work = temp_dir(self)
        res = synthetic_result()
        done = self.cli(work, res)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["gpt6_copy_check"], {"match": 5})
        altered = copy.deepcopy(res["first"][0]["gpt6_discover"]["output"])
        altered["proposed"][0]["demonstrated_gap"] = "changed by the wrapper"
        beta_discover = work / "gpt6/gpt6-discover-beta"  # that job failed: the workflow received no output
        cases = [  # (change to a faithful run's files, the job, its expected check)
            (lambda: write_json(work / "gpt6/gpt6-discover-alpha/last.json", altered), "gpt6-discover-alpha", "mismatch"),
            (lambda: (work / "gpt6/gpt6-fit-alpha/last.json").unlink(), "gpt6-fit-alpha", "no_file"),
            (lambda: (work / "gpt6/gpt6-fit-alpha/last.json").write_text("{not json"), "gpt6-fit-alpha", "file_unparseable"),
            (lambda: (write_json(beta_discover / "last.json", discovery("beta", [B2])),
                      (beta_discover / "exit").write_text("0\n")), "gpt6-discover-beta", "file_only"),
        ]
        for change, job, expected in cases:
            shutil.rmtree(work / "gpt6", ignore_errors=True)
            write_codex_files(work, res)
            change()
            done = self.cli(work, res, codex_files=False)
            self.assertEqual(done.returncode, 4, (expected, done.stderr))
            self.assertIn(expected, done.stderr)
            summary = json.loads(done.stdout)
            self.assertEqual(summary["gpt6_copy_check"].get(expected), 1, expected)
            layer = job.split("-")[-1]
            returns = json.loads((work / "out/returns.json").read_text())
            self.assertIn({"round": "first", "cause": "gpt6_copy", "job": job, "check": expected},
                          returns["failures"][layer])
            layers = {x["layer_id"]: x for x in json.loads((work / "out/layers.json").read_text())}
            self.assertEqual(layers[layer]["reopen"][0]["trigger"], "retained_failure")
        # A failed job that wrote a file anyway is not a copy problem: the workflow rightly did not use it.
        shutil.rmtree(work / "gpt6")
        write_codex_files(work, res)
        write_json(beta_discover / "last.json", discovery("beta", [B2]))
        (beta_discover / "exit").write_text("1\n")
        done = self.cli(work, res, codex_files=False)
        self.assertEqual(done.returncode, 0, done.stderr)


# --------------------------------------------------------------------------- usage record, result and ledger


class UsageRecordTests(unittest.TestCase):
    def test_record_sanitizes_the_transcript_dir_and_hashes_the_raw_output(self):
        work = temp_dir(self)
        raw = child_usage_raw("wf_fixture-1", ["discover:alpha"])
        (work / "raw.json").write_bytes(raw)
        done = run([sys.executable, HARNESS / "usage_record.py", "--raw-output", work / "raw.json", "--exit-code", "0",
                    "--out", work / "usage.json"])
        self.assertEqual(done.returncode, 0, done.stderr)
        document = json.loads((work / "usage.json").read_text())
        self.assertEqual(document["child_usage"]["transcript_dir"], "<session-transcripts>/subagents/workflows/wf_fixture-1")
        self.assertEqual(document["measurement"]["raw_output_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(document["measurement"]["tool_sha256"], hashlib.sha256(
            (ROOT / usage_record.TOOL).read_bytes()).hexdigest())
        self.assertEqual(document["measurement"]["command"], "node examples/claude-native/workflows/child-usage.mjs "
                         "<session-transcripts>/subagents/workflows/wf_fixture-1 --require-effort max")
        self.assertEqual(json.loads(done.stdout)["workflow_run"], "wf_fixture-1")

    def test_incomplete_usage_is_written_with_exit_1_and_private_content_is_refused(self):
        work = temp_dir(self)
        (work / "raw.json").write_bytes(child_usage_raw("wf_fixture-2", ["discover:alpha"], status="incomplete"))
        done = run([sys.executable, HARNESS / "usage_record.py", "--raw-output", work / "raw.json", "--exit-code", "1",
                    "--out", work / "usage.json"])
        self.assertEqual(done.returncode, 1)
        self.assertTrue((work / "usage.json").exists())
        private = json.loads(child_usage_raw("wf_fixture-3", ["discover:alpha"]))
        private["children"][0]["label"] = "discover:" + "/home/" + "alice" + "/x"
        (work / "raw2.json").write_text(json.dumps(private))
        done = run([sys.executable, HARNESS / "usage_record.py", "--raw-output", work / "raw2.json", "--exit-code", "0",
                    "--out", work / "usage2.json"])
        self.assertEqual(done.returncode, 3)
        self.assertFalse((work / "usage2.json").exists())

    def test_effort_drift_fails_even_when_the_usage_is_complete(self):
        # child-usage.mjs --require-effort max exits 1 and lists the child when one ran at another effort.
        work = temp_dir(self)
        drifted = json.loads(child_usage_raw("wf_fixture-4", ["discover:alpha"]))
        drifted["children"][0]["efforts"] = ["xhigh"]
        drifted["effort_mismatches"] = [{"child": "discover:alpha", "efforts": ["xhigh"]}]
        (work / "raw.json").write_text(json.dumps(drifted))
        for code in ("1", "0"):  # the tool's exit code, and the mismatch list on its own
            done = run([sys.executable, HARNESS / "usage_record.py", "--raw-output", work / "raw.json", "--exit-code",
                        code, "--out", work / "usage.json"])
            self.assertEqual(done.returncode, 1, code)
            self.assertEqual(json.loads(done.stdout)["effort_mismatches"], drifted["effort_mismatches"])
            self.assertEqual(json.loads((work / "usage.json").read_text())["child_usage"]["status"], "complete")

    @unittest.skipUnless(NODE, "node not installed")
    def test_transcripts_arrive_whole_through_node_and_a_rerun_call_is_superseded(self):
        # 300 children give child-usage.mjs more output than a pipe buffer (64 KiB), which process.exit() used to
        # truncate; one call the runtime re-ran after a usage-limit pause keeps its earlier attempt as superseded.
        transcripts = temp_dir(self) / "session" / "subagents" / "workflows" / "wf_fixture-5"
        transcripts.mkdir(parents=True)
        journal = [{"type": "started", "agentId": "r0", "label": "discover:layer-0", "phase": "Discover", "key": "v2:0"}]
        for i in range(300):
            journal += [{"type": "started", "agentId": f"b{i}", "label": f"discover:layer-{i}", "phase": "Discover",
                         "key": f"v2:{i}"}, {"type": "result", "agentId": f"b{i}", "result": {"ok": True}}]
        (transcripts / "journal.jsonl").write_text("".join(json.dumps(e) + "\n" for e in journal), encoding="utf-8")
        zero = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
        for agent in ["r0"] + [f"b{i}" for i in range(300)]:
            rows = [{"type": "assistant", "effort": "max", "message": {"id": f"m-{agent}", "model": "claude-opus-5-5",
                                                                       "usage": dict(zero, output_tokens=5)}}]
            if agent == "r0":
                rows.append({"type": "assistant", "isApiErrorMessage": True, "effort": "max",
                             "message": {"id": "limit", "model": "<synthetic>", "usage": zero}})
            (transcripts / f"agent-{agent}.meta.json").write_text(json.dumps({"model": "opus"}), encoding="utf-8")
            (transcripts / f"agent-{agent}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        out = temp_dir(self) / "usage.json"
        done = run([sys.executable, HARNESS / "usage_record.py", "--transcript-dir", transcripts, "--out", out])
        self.assertEqual(done.returncode, 0, done.stderr)
        usage = json.loads(out.read_text())["child_usage"]
        self.assertGreater(len(json.dumps(usage, indent=2)), 65536)
        self.assertEqual((usage["status"], len(usage["children"]), usage["transcript_dir"]),
                         ("complete", 300, "<session-transcripts>/subagents/workflows/wf_fixture-5"))
        self.assertEqual([(a["agent_id"], a["superseded_by"]) for a in usage["superseded_attempts"]], [("r0", "b0")])
        self.assertEqual(usage["by_resolved_model"]["claude-opus-5-5"]["output_tokens"], 5 * 301)
        self.assertEqual(json.loads(done.stdout)["superseded_attempts"], ["discover:layer-0"])


LANE = "landscape-sweep-20261026"


class LedgerIntegrationTests(unittest.TestCase):
    """convert.py -> make_result.py -> saturation_ledger.append in a synthetic checkout."""

    def setUp(self):
        self.root = temp_dir(self)
        write_json(self.root / sl.RESEARCH_STATE, {"schema_version": 1, "layers": [
            {"catalog": c, "layer_id": l, "status": "comparison_required", "next_action": f"compare {l}",
             "decision_ref": "catalogs/landscape/foundation.json"}
            for c, l in (("foundation", "alpha"), ("us-equities", "beta"), ("foundation", "gamma"))]})
        write_json(self.root / sl.ADOPTION, {"platform_profiles": [{"id": "linux-x86_64", "os": "linux"}]})
        self.scope = sl.scope_hashes(self.root)
        self.base = f"evidence/artifacts/{LANE}"

    def evidence(self, res, usage=None):
        """Converted evidence; with `usage`, converted against that record (votes measured, efforts checked)."""
        out = convert.convert(res, self.scope, LANE, convert.resolved_models(usage), usage=usage)
        write_json(self.root / self.base / "returns.json", out["returns"])
        usage = usage or usage_record.record(child_usage_raw("wf_fixture-1", SYNTHETIC_LABELS), 0, "cmd", ROOT)
        write_json(self.root / f"{self.base}-attempts/child-usage-wf_fixture-1.json", usage)
        sections = {"foundation": [], "trading": []}
        for layer in out["lanes"]["lanes"][0]["result"]["layers"]:
            catalog = next(x["catalog"] for x in out["layers"] if x["layer_id"] == layer["layer_id"])
            rows = [{"repository": p["repository"], "lane": LANE,
                     "adversarial_verification": {"survives": p["survives"], "votes": p["votes"]}}
                    for p in out["lanes"]["lanes"][0]["proposals"] if p["layer"] == layer["layer_id"]]
            section = sweep_common.MANIFEST_SECTION[catalog]
            sections[section].append({"layer": layer["layer_id"], "candidates": rows,
                                      ("components" if section == "foundation" else "entries"): []})
        write_json(self.root / "catalogs/sota-convergence/manifest-20261026.json", {"checked_at": "2026-10-26", **sections})
        reviews = []
        for survivor in out["survivors"]:
            name = survivor["repository"].rsplit("/", 2)[-2] + "-" + survivor["repository"].rsplit("/", 1)[-1]
            write_json(self.root / self.base / f"{name}.json", {"repository": survivor["repository"],
                                                               "layers": [survivor["layer_id"]]})
            reviews.append({"repository": survivor["repository"], "path": f"{name}.json",
                            "layers": [survivor["layer_id"]]})
        files = []
        for path in sorted(self.root.rglob("*.json")):
            relative = path.relative_to(self.root).as_posix()
            if relative.startswith(("evidence/", "catalogs/sota-convergence/")):
                raw = path.read_bytes()
                files.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        write_json(self.root / sl.EVIDENCE, {"schema_version": 1, "receipts": [], "files": files})
        (self.root / sl.LEDGER).parent.mkdir(parents=True, exist_ok=True)
        (self.root / sl.LEDGER).write_text(sl.dump(sl.empty_ledger()), encoding="utf-8")
        return out, reviews

    def result(self, out, reviews, **overrides):
        values = dict(layers=out["layers"], reviews=reviews,
                      usage=json.loads((self.root / f"{self.base}-attempts/child-usage-wf_fixture-1.json").read_text()),
                      manifest={"checked_at": "2026-10-26"}, sweep_id=LANE, lane=LANE,
                      returns_ref=f"{self.base}/returns.json",
                      usage_ref=f"{self.base}-attempts/child-usage-wf_fixture-1.json",
                      manifest_ref="catalogs/sota-convergence/manifest-20261026.json", prompts_sha256="c" * 64,
                      returns=json.loads((self.root / self.base / "returns.json").read_text()))
        values.update(overrides)
        return make_result.build_result(**values)

    def clean_counts(self, res):
        out, reviews = self.evidence(res)
        ledger = sl.append(self.root, json.loads((self.root / sl.LEDGER).read_text()), self.result(out, reviews))
        self.assertEqual(sl.check_ledger(self.root, ledger), [])
        return {key[1]: value for key, value in sl.derive(ledger).items()}

    def test_a_layer_whose_workers_all_returned_counts_as_clean(self):
        state = self.clean_counts(healthy_result())
        self.assertEqual((state["alpha"]["count"], state["alpha"]["reset"]), (1, []))

    def test_a_sweep_whose_gpt6_fit_lane_failed_never_counts_as_clean(self):
        # The reviewers' reproduction: every GPT-6 fit job failed, so every proposal is refuted and nothing
        # survives. Before the repair both layers derived as clean (count 1); the retained failures now reset them.
        state = self.clean_counts(fail_gpt6_fit(synthetic_result()))
        for layer_id in ("alpha", "beta"):
            self.assertEqual(state[layer_id]["count"], 0, layer_id)
            self.assertIn({"trigger": "retained_failure", "ref": f"{self.base}/returns.json#/failures/{layer_id}"},
                          state[layer_id]["reset"])
        state = self.clean_counts(fail_gpt6_fit(healthy_result()))  # the same failure in an otherwise clean layer
        self.assertEqual(state["alpha"]["count"], 0)

    def test_a_failed_first_round_never_counts_as_clean_after_a_reproposal(self):
        # GPT-6 review of #324: round 1's GPT-6 fit failed, the follow-up re-proposed every repository with all
        # votes, and the layer derived as clean (count 1) because the re-proposal replaced the failed round's votes.
        res = fail_gpt6_fit(healthy_result())
        first = res["first"][0]
        follow = json.loads(json.dumps(healthy_result()["first"][0]))
        follow.update(round="followup", followup_reason={"reason": "r", "search_directions": []})
        res.update(critic={"followup_layers": [{"layer_id": first["layer_id"], "reason": "r",
                                                "search_directions": []}], "general": []},
                   followups=[follow])
        state = self.clean_counts(res)
        self.assertEqual(state[first["layer_id"]]["count"], 0)
        self.assertIn({"trigger": "retained_failure",
                       "ref": f"{self.base}/returns.json#/failures/{first['layer_id']}"}, state[first["layer_id"]]["reset"])

    def test_converted_evidence_appends_and_checks(self):
        out, reviews = self.evidence(synthetic_result())
        result = self.result(out, reviews)
        self.assertEqual(result["workflow_run"], "wf_fixture-1")
        self.assertNotIn("@RETURNS@", json.dumps(result))
        self.assertEqual(result["layers"][0]["survived"][0]["source_review"], f"{self.base}/owner-alpha-one.json")
        ledger = sl.append(self.root, json.loads((self.root / sl.LEDGER).read_text()), result)
        self.assertEqual(sl.check_ledger(self.root, ledger), [])
        record = ledger["sweeps"][0]
        self.assertEqual([layer["layer_id"] for layer in record["layers"]], ["alpha", "beta"])
        self.assertEqual(record["layers"][0]["requirement_sha256"], self.scope["requirement_sha256"]["foundation/alpha"])

    def test_the_ledger_rejects_a_vote_changed_after_conversion(self):
        out, reviews = self.evidence(synthetic_result())
        result = self.result(out, reviews)
        returns = json.loads((self.root / self.base / "returns.json").read_text())
        returns["votes"]["alpha"][1]["fit"]["refuted"] = True  # A1's fit vote no longer matches its survival
        write_json(self.root / self.base / "returns.json", returns)
        with self.assertRaises(sl.LedgerError):
            sl.append(self.root, json.loads((self.root / sl.LEDGER).read_text()), result)

    def test_make_result_refusals(self):
        out, reviews = self.evidence(synthetic_result())
        with self.assertRaisesRegex(ValueError, "without a source review"):
            self.result(out, reviews[:1])
        usage = json.loads((self.root / f"{self.base}-attempts/child-usage-wf_fixture-1.json").read_text())
        usage["child_usage"]["status"] = "incomplete"
        with self.assertRaisesRegex(ValueError, "complete usage"):
            self.result(out, reviews, usage=usage)
        with self.assertRaisesRegex(ValueError, "did not cover"):
            self.result(out, reviews, reopen={"zeta": [{"trigger": "retained_failure", "ref": "x"}]})
        # Effort drift: a failed measurement, a listed mismatch, or a child not measured at max alone.
        for change, message in (
                (lambda u: u["measurement"].update(exit_code=1), "measurement.exit_code"),
                (lambda u: u["child_usage"].update(effort_mismatches=[{"child": "critic", "efforts": ["xhigh"]}]),
                 "effort_mismatches"),
                (lambda u: u["child_usage"]["children"][0].update(efforts=["max", "xhigh"]), "effort max only")):
            drifted = copy.deepcopy(usage)
            drifted["child_usage"]["status"] = "complete"
            change(drifted)
            with self.assertRaisesRegex(ValueError, message):
                self.result(out, reviews, usage=drifted)
        # The WebSearch cap: every child needs a measured web_search, and a capped worker needs its retained failure.
        unmeasured = copy.deepcopy(usage)
        unmeasured["child_usage"]["status"] = "complete"
        del unmeasured["child_usage"]["children"][0]["web_search"]
        with self.assertRaisesRegex(ValueError, "without a measured web_search"):
            self.result(out, reviews, usage=unmeasured)
        capped = copy.deepcopy(usage)
        capped["child_usage"]["status"] = "complete"
        capped["child_usage"]["children"][0]["web_search"] = {"calls": 2, "capped": 1, "first_capped_at": None}
        with self.assertRaisesRegex(ValueError, "no web_search_capped retained failure"):
            self.result(out, reviews, usage=capped)
        # A layer with retained failures must keep its retained_failure reopen entry.
        stripped = copy.deepcopy(out["layers"])
        stripped[0]["reopen"] = []
        with self.assertRaisesRegex(ValueError, r"no retained_failure reopen entry.*alpha"):
            self.result(dict(out, layers=stripped), reviews)

    def test_a_worker_at_another_effort_reopens_its_layer_and_the_record_appends(self):
        raw = json.loads(child_usage_raw("wf_fixture-1", SYNTHETIC_LABELS))
        next(c for c in raw["children"] if c["label"] == "discover:alpha")["efforts"] = ["max", "low"]
        raw["effort_mismatches"] = [{"child": "discover:alpha", "efforts": ["max", "low"]}]
        out, reviews = self.evidence(healthy_result(),
                                     usage=usage_record.record(json.dumps(raw).encode("utf-8"), 1, "cmd", ROOT))
        result = self.result(out, reviews)
        self.assertEqual(result["layers"][0]["reopen"], [
            {"trigger": "retained_failure", "ref": f"{self.base}/returns.json#/failures/alpha"}])
        ledger = sl.append(self.root, json.loads((self.root / sl.LEDGER).read_text()), result)
        self.assertEqual(sl.check_ledger(self.root, ledger), [])
        self.assertEqual({key[1]: value for key, value in sl.derive(ledger).items()}["alpha"]["count"], 0)
        # Without its effort_deviation retained failure, the same usage record is refused.
        returns = json.loads((self.root / self.base / "returns.json").read_text())
        returns["failures"] = {}
        with self.assertRaisesRegex(ValueError, "no effort_deviation retained failure"):
            self.result(out, reviews, returns=returns)

    def test_a_capped_web_search_reopens_every_layer_through_the_critic(self):
        raw = json.loads(child_usage_raw("wf_fixture-1", SYNTHETIC_LABELS))
        next(c for c in raw["children"] if c["label"] == "critic")["web_search"] = {
            "calls": 2, "capped": 2, "first_capped_at": "2026-10-26T11:06:45Z"}
        out, reviews = self.evidence(healthy_result(),
                                     usage=usage_record.record(json.dumps(raw).encode("utf-8"), 0, "cmd", ROOT))
        result = self.result(out, reviews)
        ledger = sl.append(self.root, json.loads((self.root / sl.LEDGER).read_text()), result)
        self.assertEqual(sl.check_ledger(self.root, ledger), [])
        # healthy_result's layer would be clean (count 1) without the capped critic.
        self.assertEqual({key[1]: value for key, value in sl.derive(ledger).items()}["alpha"]["count"], 0)

    def omission(self, raw, exit_code, drop):
        """Converted evidence of healthy_two_layers() measured by `raw`, then `drop(returns, layers)` applied in memory
        before make_result: the result, or the ValueError make_result raised."""
        out, reviews = self.evidence(healthy_two_layers(),
                                     usage=usage_record.record(json.dumps(raw).encode("utf-8"), exit_code, "cmd", ROOT))
        returns = json.loads((self.root / self.base / "returns.json").read_text())
        layers = copy.deepcopy(out["layers"])
        drop(returns["failures"], {layer["layer_id"]: layer for layer in layers})
        try:
            return self.result(dict(out, layers=layers), reviews, returns=returns)
        except ValueError as error:
            return error

    def test_failure_coverage_is_checked_per_worker_and_per_layer(self):
        # GPT-6 review of the 2026-09-26 record: with token-efficiency's critic-cap failure and its reopen entry removed,
        # make_result passed, because another layer's "critic" failure satisfied a check over all layers, and the
        # layer derived a clean count of 1. Each worker's failure must be in each of its layers: the critic's in every
        # layer of the record, a <role>:<layer> worker's in its own.
        self.assertEqual({k: v["count"] for k, v in self.clean_counts(healthy_two_layers()).items()},
                         {"alpha": 1, "beta": 1})
        baseline = json.loads(child_usage_raw("wf_fixture-1", SYNTHETIC_LABELS))

        def drop_only_failure(layer_id, cause):
            def drop(failures, layers):
                failures[layer_id] = [f for f in failures[layer_id] if f["cause"] != cause]
                self.assertEqual(failures[layer_id], [])  # it was the layer's only retained failure
                del failures[layer_id]
                layers[layer_id]["reopen"] = []
            return drop

        capped = copy.deepcopy(baseline)
        next(c for c in capped["children"] if c["label"] == "critic")["web_search"] = {
            "calls": 2, "capped": 2, "first_capped_at": "2026-10-26T11:06:45Z"}
        low = copy.deepcopy(baseline)
        next(c for c in low["children"] if c["label"] == "critic")["efforts"] = ["max", "low"]
        low["effort_mismatches"] = [{"child": "critic", "efforts": ["max", "low"]}]
        worker = copy.deepcopy(baseline)
        next(c for c in worker["children"] if c["label"] == "refute-fit:alpha")["web_search"] = {
            "calls": 1, "capped": 1, "first_capped_at": "2026-10-26T11:06:45Z"}

        def move_to_beta(failures, layers):  # alpha's worker failure recorded under beta instead
            failures["beta"] = failures.pop("alpha")
            layers["beta"]["reopen"], layers["alpha"]["reopen"] = [
                {"trigger": "retained_failure", "ref": f"{self.base}/returns.json#/failures/beta"}], []

        for name, raw, exit_code, drop, message in (
                ("critic cap", capped, 0, drop_only_failure("beta", "web_search_capped"),
                 r"no web_search_capped retained failure.*critic in beta"),
                ("critic effort", low, 1, drop_only_failure("beta", "effort_deviation"),
                 r"no effort_deviation retained failure.*critic in beta"),
                ("worker in another layer", worker, 0, move_to_beta,
                 r"no web_search_capped retained failure.*refute-fit:alpha in alpha")):
            with self.subTest(name):
                self.assertIsInstance(self.omission(raw, exit_code, lambda failures, layers: None), dict)
                refused = self.omission(raw, exit_code, drop)
                self.assertIsInstance(refused, ValueError, "make_result accepted a record whose layer lost its failure")
                self.assertRegex(str(refused), message)

    def test_refuted_by_absence_is_not_an_earlier_adjudication(self):
        # beta's B1 is refuted only by its missing facts vote; alpha's A3 by its returned facts vote.
        out, reviews = self.evidence(synthetic_result())
        ledger = sl.append(self.root, json.loads((self.root / sl.LEDGER).read_text()), self.result(out, reviews))
        self.assertEqual(sl.check_ledger(self.root, ledger), [])
        layers = {layer["layer_id"]: layer for layer in ledger["sweeps"][-1]["layers"]}
        self.assertIn("o/beta-one", layers["beta"]["votes_note"])
        target_of = sl.ref_resolver(lambda path: sl.load_json(self.root, path))
        self.assertEqual(sl.adjudicated_repos(layers["beta"], target_of), {sl.norm_repo(B2)})
        self.assertEqual(sl.adjudicated_repos(layers["beta"]), {sl.norm_repo(B1), sl.norm_repo(B2)})
        self.assertIn(sl.norm_repo(A3), sl.adjudicated_repos(layers["alpha"], target_of))

    def test_hand_written_reopen_entries_are_added_to_the_retained_failures(self):
        out, reviews = self.evidence(synthetic_result())
        extra = {"trigger": "pin_moved", "ref": "evidence/receipts/x.json"}
        result = self.result(out, reviews, reopen={"alpha": [extra], "beta": [extra]})
        for layer in result["layers"]:
            self.assertEqual(layer["reopen"], [
                {"trigger": "retained_failure", "ref": f"{self.base}/returns.json#/failures/{layer['layer_id']}"}, extra])
        ledger = sl.append(self.root, json.loads((self.root / sl.LEDGER).read_text()), result)
        self.assertEqual(sl.check_ledger(self.root, ledger), [])


# --------------------------------------------------------------------------- source reviews

FAKE_GH = """#!{python}
import json, sys
path = sys.argv[2]
answers = {answers}
if path not in answers:
    sys.stderr.write("gh: Not Found (HTTP 404)\\n")
    sys.exit(1)
print(json.dumps(answers[path]))
"""


class SourceReviewTests(unittest.TestCase):
    def test_one_review_per_repository_with_every_layer_and_failures_reported(self):
        work, bin_dir = temp_dir(self), temp_dir(self)
        readme = base64.b64encode(("# Alpha\n\n" + "A long enough paragraph about what alpha one does. " * 3).encode()).decode()
        answers = {"repos/o/alpha-one": {"full_name": "O/Alpha-One", "default_branch": "main", "license": {"spdx_id": "MIT"},
                                         "description": "alpha", "stargazers_count": 5, "pushed_at": "2026-10-20",
                                         "archived": False},
                   "repos/O/Alpha-One/commits/main": {"sha": "f" * 40},
                   f"repos/O/Alpha-One/readme?ref={'f' * 40}": {"path": "README.md", "content": readme}}
        gh = bin_dir / "gh"
        gh.write_text(FAKE_GH.format(python=sys.executable, answers=repr(answers)), encoding="utf-8")
        gh.chmod(0o755)
        survivors = write_json(work / "survivors.json", [
            {"layer_id": "beta", "repository": "https://github.com/o/alpha-one"},
            {"layer_id": "alpha", "repository": "https://github.com/o/alpha-one"},
            {"layer_id": "alpha", "repository": "https://github.com/o/missing"}])
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
        done = run([sys.executable, HARNESS / "source_reviews.py", "--survivors", survivors, "--out", work / "reviews",
                    "--lane", LANE], env=env)
        self.assertEqual(done.returncode, 1)
        self.assertIn("https://github.com/o/missing", done.stderr)
        written = json.loads(done.stdout)
        self.assertEqual(written, [{"repository": "https://github.com/O/Alpha-One", "path": "o-alpha-one.json",
                                    "layers": ["alpha", "beta"]}])
        review = json.loads((work / "reviews/o-alpha-one.json").read_text())
        self.assertEqual((review["id"], review["reviewed_commit"], review["license"]),
                         ("source-review-o-alpha-one", "f" * 40, "MIT"))
        self.assertIn(f"Survived the {LANE} facts refuter and both fit refuters", review["claim"])
        self.assertEqual(review["documentation_excerpts"][0]["source"], f"README.md@{'f' * 40}")

    def test_repositories_sharing_a_readable_name_get_distinct_files_and_none_is_overwritten(self):
        work, bin_dir = temp_dir(self), temp_dir(self)
        answers = {}
        for full in ("acme/a-b", "acme-a/b", "o/alpha-one"):
            answers[f"repos/{full}"] = {"full_name": full, "default_branch": "main", "license": None,
                                        "description": "", "stargazers_count": 1, "pushed_at": "2026-10-20",
                                        "archived": False}
            answers[f"repos/{full}/commits/main"] = {"sha": "e" * 40}
        gh = bin_dir / "gh"
        gh.write_text(FAKE_GH.format(python=sys.executable, answers=repr(answers)), encoding="utf-8")
        gh.chmod(0o755)
        survivors = write_json(work / "survivors.json", [
            {"layer_id": "alpha", "repository": "https://github.com/acme/a-b"},
            {"layer_id": "beta", "repository": "https://github.com/acme-a/b"},
            {"layer_id": "alpha", "repository": "https://github.com/o/alpha-one"}])
        other = write_json(work / "reviews/o-alpha-one.json", {"repository": "https://github.com/someone/else"})
        before = other.read_bytes()
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
        done = run([sys.executable, HARNESS / "source_reviews.py", "--survivors", survivors, "--out", work / "reviews",
                    "--lane", LANE], env=env)
        self.assertEqual(done.returncode, 1)
        self.assertIn("already holds a review of another repository", done.stderr)
        self.assertEqual(other.read_bytes(), before)
        written = {item["repository"]: item["path"] for item in json.loads(done.stdout)}
        digest = {full: hashlib.sha256(full.encode()).hexdigest()[:10] for full in ("acme/a-b", "acme-a/b")}
        self.assertEqual(written, {"https://github.com/acme/a-b": f"acme-a-b-{digest['acme/a-b']}.json",
                                   "https://github.com/acme-a/b": f"acme-a-b-{digest['acme-a/b']}.json"})
        for repository, path in written.items():
            review = json.loads((work / "reviews" / path).read_text())
            self.assertEqual((review["repository"], review["id"]), (repository, f"source-review-{path[:-5]}"))

    def test_a_hugging_face_model_survivor_is_reviewed_at_its_hub_commit(self):
        # The 2026-09-26 sweep kept a Hugging Face model repository in agents-models-workers, which gh cannot read.
        # Its review reads the Hub's model-info endpoint for the default revision's commit and the model card at that
        # commit; the card's YAML metadata block is not an excerpt. A dataset URL is no model repository.
        source_reviews = load("source_reviews")
        sha = "a" * 40
        card = ("---\nlicense: apache-2.0\nlibrary_name: transformers\n---\n\n# Model 1.5\n\n"
                + "A long enough paragraph about what the model does and how it was trained. " * 2)
        answers = {"api/models/Org/Model-1.5": {"id": "Org/Model-1.5", "sha": sha, "cardData": {"license": "apache-2.0"},
                                                "tags": ["license:apache-2.0"], "likes": 7, "gated": False,
                                                "disabled": False, "lastModified": "2026-10-20T00:00:00.000Z"},
                   f"Org/Model-1.5/resolve/{sha}/README.md": card}
        requested = []

        def hub_get(path, text=False):
            requested.append(path)
            if path not in answers:
                raise source_reviews.HubError(f"GET {path}: HTTP Error 404: Not Found")
            return answers[path]

        work = temp_dir(self)
        survivors = write_json(work / "survivors.json", [
            {"layer_id": "agents-models-workers", "repository": "https://huggingface.co/Org/Model-1.5"},
            {"layer_id": "agents-models-workers", "repository": "https://huggingface.co/datasets/org/data"}])
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(source_reviews, "hub_get", hub_get), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            code = source_reviews.main(["--survivors", str(survivors), "--out", str(work / "reviews"), "--lane", LANE])
        self.assertEqual(code, 1)
        self.assertIn("https://huggingface.co/datasets/org/data", err.getvalue())
        self.assertEqual(json.loads(out.getvalue()), [{"repository": "https://huggingface.co/Org/Model-1.5",
                                                       "path": "hf-org-model-1-5.json",
                                                       "layers": ["agents-models-workers"]}])
        review = json.loads((work / "reviews/hf-org-model-1-5.json").read_text())
        self.assertEqual((review["id"], review["reviewed_commit"], review["license"], review["readme_path"]),
                         ("source-review-hf-org-model-1-5", sha, "apache-2.0", "README.md"))
        self.assertEqual(review["documentation_excerpts"][0]["source"], f"README.md@{sha}")
        self.assertNotIn("library_name", json.dumps(review["documentation_excerpts"]))
        self.assertIn(f"Survived the {LANE} facts refuter and both fit refuters", review["claim"])
        self.assertEqual(requested, ["api/models/Org/Model-1.5", f"Org/Model-1.5/resolve/{sha}/README.md"])

    def test_hub_reviews_survive_truncated_responses_trailing_slashes_and_indented_card_metadata(self):
        # Review repairs (2026-09-26): http.client.HTTPException is not an OSError, so a truncated Hub response
        # escaped as a traceback; the same model with and without a trailing slash got two reviews; a card whose
        # metadata block follows a blank line (huggingface_hub repocard.REGEX_YAML_BLOCK allows it) was excerpted.
        source_reviews = load("source_reviews")
        with mock.patch.object(source_reviews.urllib.request, "urlopen",
                               side_effect=source_reviews.http.client.IncompleteRead(b"")):
            with self.assertRaises(source_reviews.HubError):
                source_reviews.hub_get("api/models/Org/M")
        sha = "b" * 40
        card = "\n---\nlicense: mit\nbase_model: some/model\n---\n\n" + "A long enough paragraph about the model itself. " * 3
        answers = {"api/models/Org/M": {"id": "Org/M", "sha": sha, "cardData": {"license": "mit"}},
                   f"Org/M/resolve/{sha}/README.md": card}
        work = temp_dir(self)
        survivors = write_json(work / "survivors.json", [
            {"layer_id": "alpha", "repository": "https://huggingface.co/Org/M"},
            {"layer_id": "beta", "repository": "https://huggingface.co/Org/M/"}])
        out = io.StringIO()
        with mock.patch.object(source_reviews, "hub_get", lambda path, text=False: answers[path]), \
                contextlib.redirect_stdout(out):
            code = source_reviews.main(["--survivors", str(survivors), "--out", str(work / "reviews"), "--lane", LANE])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue()), [{"repository": "https://huggingface.co/Org/M",
                                                       "path": "hf-org-m.json", "layers": ["alpha", "beta"]}])
        excerpts = json.loads((work / "reviews/hf-org-m.json").read_text())["documentation_excerpts"]
        self.assertTrue(excerpts and not any("base_model" in item["text"] for item in excerpts))
        # make_result.py finds that review for a survivor recorded with the trailing slash, as the ledger compares.
        usage = usage_record.record(child_usage_raw("wf_fixture-1", SYNTHETIC_LABELS), 0, "cmd", ROOT)
        layer = {"catalog": "us-equities", "layer_id": "beta", "reopen": [],
                 "survived": [{"repo": "https://huggingface.co/Org/M/"}]}
        result = make_result.build_result(
            layers=[layer], reviews=json.loads(out.getvalue()), usage=usage, manifest={"checked_at": "2026-10-26"},
            sweep_id=LANE, lane=LANE, returns_ref=f"evidence/artifacts/{LANE}/returns.json", usage_ref="u.json",
            manifest_ref="m.json", prompts_sha256=PROMPTS_SHA256_20260926, returns={"failures": {}})
        self.assertEqual(result["layers"][0]["survived"][0]["source_review"], f"evidence/artifacts/{LANE}/hf-org-m.json")


# --------------------------------------------------------------------------- sweep.js under node

NODE_HARNESS = r"""
const fs = require('fs')
const [scriptPath, fixturePath, argsPath] = process.argv.slice(2)
const src = fs.readFileSync(scriptPath, 'utf8').replace(/^export const meta/m, 'const meta')
const fixture = JSON.parse(fs.readFileSync(fixturePath, 'utf8'))
const args = argsPath ? JSON.parse(fs.readFileSync(argsPath, 'utf8')) : undefined
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const calls = [], logs = [], phases = []
const agent = async (prompt, opts = {}) => {
  calls.push({ label: opts.label, model: opts.model, effort: opts.effort, phase: opts.phase, schema: !!opts.schema, agentType: opts.agentType || null, prompt })
  const r = fixture.responses[opts.label]
  return r === undefined ? null : r
}
const parallel = async (thunks) => Promise.all(thunks.map(async (t) => { try { return await t() } catch (e) { return null } }))
// fixture.lose_pipeline {"<n>": [item index, ...]}: the n-th pipeline() call returns null for those items, as the
// runtime does for an item whose stage failed.
let pipelineCall = 0
const pipeline = async (items, ...stages) => {
  const lose = (fixture.lose_pipeline || {})[String(pipelineCall++)] || []
  return Promise.all(items.map(async (item, i) => {
    if (lose.includes(i)) return null
    let v = item
    try { for (const s of stages) v = await s(v, item, i); return v } catch (e) { return null }
  }))
}
const fn = new AsyncFunction('args', 'agent', 'parallel', 'pipeline', 'phase', 'log', 'budget', 'workflow', src)
fn(args, agent, parallel, pipeline, (t) => phases.push(t), (m) => logs.push(m), { total: null }, null)
  .then((result) => process.stdout.write(JSON.stringify({ result, calls, logs, phases })))
  .catch((e) => { console.error(e && e.stack || e); process.exit(1) })
"""


def wrapper(output, exit_code=0):
    meta = {"status": "done", "exit": exit_code, "started": "2026-10-26T00:00:00Z", "finished": "2026-10-26T00:05:00Z",
            "usage": {"input_tokens": 1000, "cached_input_tokens": 900, "output_tokens": 50},
            "output_text": json.dumps(output) if output is not None else None,
            "stderr_tail": None if output is not None else "boom", "limit": False, "limit_marker": False,
            "model": "gpt-6-astra", "effort": "max", "codex_version": "codex-cli 0.0.0-fixture"}
    return {"result_json": json.dumps(meta)}


def node_fixture():
    alpha_claude = [f"https://github.com/o/a{i}" for i in range(1, 6)]
    alpha_gpt6 = ["https://github.com/O/a1.git"] + [f"https://github.com/o/g{i}" for i in range(1, 5)]
    merged_alpha = ["https://github.com/o/a1", *alpha_claude[1:], *alpha_gpt6[1:]]
    kept = merged_alpha[:8]
    reason = "missed $& the $' class"
    responses = {
        "discover:alpha": discovery("alpha", alpha_claude, ["search-first"]),
        "gpt6-discover:alpha": wrapper(discovery("alpha", alpha_gpt6)),
        "refute-facts:alpha": votes("alpha", "facts", {r: False for r in kept}),
        "refute-fit:alpha": votes("alpha", "fit", {r: r.endswith("a2") for r in kept}),
        "gpt6-refute-fit:alpha": wrapper(votes("alpha", "fit", {r: r.endswith("g1") for r in kept})),
        "discover:beta": discovery("beta", ["https://github.com/o/b1"]),
        "gpt6-discover:beta": wrapper(None, 1),
        "refute-facts:beta": votes("beta", "facts", {"https://github.com/o/b1": False}),
        "refute-fit:beta": votes("beta", "fit", {"https://github.com/o/b1": False}),
        "gpt6-refute-fit:beta": wrapper(votes("beta", "fit", {"https://github.com/o/b1": False})),
        "critic": {"followup_layers": [{"layer_id": "beta", "reason": reason, "search_directions": ["d1", "d2"]},
                                       {"layer_id": "zeta", "reason": "outside", "search_directions": []}],
                   "general": ["fixture"]},
        "discover:beta:followup": discovery("beta", ["https://github.com/o/b2"]),
        "gpt6-discover:beta:followup": wrapper(discovery("beta", ["https://github.com/o/b2"])),
        "refute-facts:beta:followup": votes("beta", "facts", {"https://github.com/o/b2": False}),
        "refute-fit:beta:followup": votes("beta", "fit", {"https://github.com/o/b2": False}),
        "gpt6-refute-fit:beta:followup": wrapper(votes("beta", "fit", {"https://github.com/o/b2": False})),
    }
    return {"responses": responses}, kept, reason


EXPECTED_MODELS = {"discover": "opus", "gpt6-discover": "sonnet", "refute-facts": "opus", "refute-fit": "opus",
                   "gpt6-refute-fit": "sonnet", "critic": "opus"}
# The Claude judgment stages run as the sweep's own agent type (WebFetch disallowed); the GPT-6 wrappers keep the default.
EXPECTED_AGENT_TYPES = {"discover": "landscape-sweep-worker", "gpt6-discover": None,
                        "refute-facts": "landscape-sweep-worker", "refute-fit": "landscape-sweep-worker",
                        "gpt6-refute-fit": None, "critic": "landscape-sweep-worker"}


@unittest.skipUnless(NODE, "node is not installed")
class SweepScriptTests(unittest.TestCase):
    def setUp(self):
        self.work = stage_work(self, ("alpha", "beta"))
        self.assertEqual(build(self.work).returncode, 0)
        self.harness = self.work / "harness.cjs"
        self.harness.write_text(NODE_HARNESS, encoding="utf-8")

    def execute(self, script, fixture, args=None):
        fixture_path = write_json(self.work / "fixture.json", fixture)
        cmd = ["node", self.harness, script, fixture_path]
        if args is not None:
            cmd.append(write_json(self.work / "run-args.json", args))
        done = run(cmd)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_syntax_of_the_script_and_its_embedded_copy(self):
        for script in (HARNESS / "sweep.js", self.work / "sweep.embedded.js"):
            body = script.read_text().replace("export const meta", "const meta", 1)
            wrapped = self.work / f"check-{script.stem}.js"
            wrapped.write_text("async function workflow(args, agent, parallel, pipeline, phase, log, budget) {\n"
                               + body + "\n}\n", encoding="utf-8")
            done = run(["node", "--check", wrapped])
            self.assertEqual(done.returncode, 0, done.stderr)
        done = run(["node", ROOT / "examples/claude-native/workflows/check-syntax.mjs", HARNESS / "sweep.js",
                    self.work / "sweep.embedded.js"])
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_roles_labels_models_cap_and_followup(self):
        fixture, kept, reason = node_fixture()
        out = self.execute(HARNESS / "sweep.js", fixture, json.loads((self.work / "args.json").read_text()))
        result, calls, logs = out["result"], out["calls"], out["logs"]
        S = str(self.work)
        for call in calls:
            role = call["label"].split(":")[0]
            self.assertEqual((call["model"], call["effort"], call["schema"], call["agentType"]),
                             (EXPECTED_MODELS[role], "max", True, EXPECTED_AGENT_TYPES[role]), call["label"])
            # No prompt tells a worker to use WebFetch: the worker type disallows it, and pages go through ctx_*.
            self.assertNotIn("WebFetch", call["prompt"], call["label"])
        self.assertEqual(sorted(c["label"] for c in calls), sorted(fixture["responses"]))
        self.assertEqual(out["phases"], ["Discover", "Critic", "Follow-up"])
        self.assertEqual({c["label"]: c["phase"] for c in calls}["refute-fit:alpha"], "Refute")
        alpha = result["first"][0]
        self.assertEqual([p["repository"] for p in alpha["merged"]][0], "https://github.com/o/a1")  # both families first
        self.assertEqual(alpha["merged"][0]["families"], ["claude", "gpt6"])
        self.assertEqual(len(alpha["merged"]), 8)
        self.assertNotIn("by_family", alpha["merged"][0])
        self.assertEqual(alpha["dropped"], [{"repository": "https://github.com/o/g4", "families": ["gpt6"],
                                             "proposed_label": "keep_but_compare"}])
        self.assertIn("alpha: 1 proposal(s) beyond the cap of 8 dropped: https://github.com/o/g4", logs)
        self.assertIn("critic named layers outside this sweep, ignored: zeta", logs)
        self.assertIn("follow-up layers: beta", logs)
        self.assertEqual(result["first"][1]["gpt6_discover"]["status"], "failed_exit_1")
        self.assertEqual(result["first"][0]["fit_gpt6"]["codex_version"], "codex-cli 0.0.0-fixture")
        prompts = {c["label"]: c["prompt"] for c in calls}
        self.assertIn(f"bash {S}/codex_call.sh start gpt6-discover-alpha {S}/prompts/gpt6-discover-alpha.txt "
                      f"{S}/schemas/discover.json", prompts["gpt6-discover:alpha"])
        self.assertIn(f"bash {S}/codex_call.sh wait gpt6-discover-alpha 540", prompts["gpt6-discover:alpha"])
        self.assertIn(f"python3 {S}/make_prompt.py fit {S}/inputs/alpha.json {S}/gpt6/props-alpha.json > "
                      f"{S}/prompts/gpt6-fit-alpha.txt", prompts["gpt6-refute-fit:alpha"])
        self.assertIn(f"{S}/schemas/votes.json", prompts["gpt6-refute-fit:alpha"])
        self.assertIn(f"python3 {S}/make_prompt.py discover {S}/inputs/beta.json - {S}/gpt6/fu-beta.json > "
                      f"{S}/prompts/gpt6-discover-beta-followup.txt", prompts["gpt6-discover:beta:followup"])
        self.assertIn(reason, prompts["discover:beta:followup"])  # '$&' and "$'" stay literal
        self.assertIn(json.dumps(reason)[1:-1], prompts["gpt6-discover:beta:followup"])
        self.assertIn(f"Read the layer input JSON file with the Read tool: {S}/inputs/alpha.json", prompts["discover:alpha"])
        self.assertTrue(prompts["refute-facts:alpha"].startswith(json.loads((self.work / "args.json").read_text())["T"]["common"]))
        self.assertEqual(result["sweep"], "landscape-sweep-20261026")
        # The Claude labels are the ones saturation_ledger.py --check requires of a completed sweep.
        converted = convert.convert(result, scope_for(), LANE, convert.resolved_models(None))
        labels = {c["label"] for c in calls}
        for layer in converted["layers"]:
            roles = ["discover"] + (["refute-facts", "refute-fit"] if layer["proposed"] else [])
            for role in roles:
                self.assertIn(f"{role}:{layer['layer_id']}", labels)
        self.assertEqual([e["repo"] for e in converted["layers"][0]["survived"]],
                         [r for r in kept if not r.endswith(("a2", "g1"))])

    def test_embedded_copy_runs_without_args_and_smoke_stops_after_the_first_round(self):
        fixture, _, _ = node_fixture()
        from_args = self.execute(HARNESS / "sweep.js", fixture, json.loads((self.work / "args.json").read_text()))
        embedded = self.execute(self.work / "sweep.embedded.js", fixture)
        self.assertEqual(embedded["result"], from_args["result"])
        smoke_args = dict(json.loads((self.work / "args.json").read_text()), test=True)
        smoke = self.execute(HARNESS / "sweep.js", fixture, smoke_args)
        self.assertEqual(smoke["result"]["sweep"], "landscape-sweep-20261026-smoke")
        self.assertNotIn("critic", {c["label"] for c in smoke["calls"]})

    def test_bad_args_stop_before_any_agent(self):
        out = self.execute(HARNESS / "sweep.js", {"responses": {}}, {"S": "relative", "layers": []})
        self.assertEqual(out["result"]["status"], "incomplete")
        self.assertEqual(out["calls"], [])
        self.assertTrue(any("S must be the absolute work directory" in i for i in out["result"]["argument_issues"]))
        args = json.loads((self.work / "args.json").read_text())
        for bad in (dict(args, S=args["S"] + "\nx"), dict(args, layers=[{"layer_id": "a;b", "catalog": "foundation"}])):
            out = self.execute(HARNESS / "sweep.js", {"responses": {}}, bad)
            self.assertEqual((out["result"]["status"], out["calls"]), ("incomplete", []))

    def test_a_lost_followup_round_is_kept_as_a_lost_round_of_its_layer(self):
        fixture, _, reason = node_fixture()
        fixture["responses"]["gpt6-discover:beta"] = wrapper(discovery("beta", ["https://github.com/o/b1"]))
        fixture["lose_pipeline"] = {"1": [0]}  # the second pipeline() call runs the follow-up rounds
        out = self.execute(HARNESS / "sweep.js", fixture, json.loads((self.work / "args.json").read_text()))
        result = out["result"]
        self.assertEqual(result["followups"], [{
            "layer_id": "beta", "catalog": "us-equities", "round": "followup", "lost": True,
            "followup_reason": {"reason": reason, "search_directions": ["d1", "d2"],
                                "already": ["https://github.com/o/b1"]}}])
        self.assertEqual(result["lost_followups"], ["beta"])
        self.assertIn("follow-up round lost layers: beta", out["logs"])
        converted = convert.convert(result, scope_for(), LANE, convert.resolved_models(None))
        self.assertEqual(converted["summary"]["lost"], ["beta:followup"])
        self.assertEqual(converted["summary"]["retained_failures"], {"beta": ["followup:round_lost"]})
        beta = next(layer for layer in converted["layers"] if layer["layer_id"] == "beta")
        self.assertEqual(beta["reopen"], [{"trigger": "retained_failure", "ref": "@RETURNS@#/failures/beta"}])

    def test_a_layer_the_critic_names_twice_gets_one_followup_round(self):
        fixture, _, _ = node_fixture()
        fixture["responses"]["critic"]["followup_layers"].append(
            {"layer_id": "beta", "reason": "again", "search_directions": []})
        out = self.execute(HARNESS / "sweep.js", fixture, json.loads((self.work / "args.json").read_text()))
        self.assertIn("critic named layers more than once, repeats ignored: beta", out["logs"])
        self.assertEqual([c["label"] for c in out["calls"]].count("discover:beta:followup"), 1)
        self.assertEqual(len(out["result"]["followups"]), 1)
        convert.convert(out["result"], scope_for(), LANE, convert.resolved_models(None))  # the plan matches

    def test_commands_quote_a_work_directory_with_spaces_and_shell_metacharacters(self):
        odd = temp_dir(self) / "sweep run $HOME;touch pwned&(x) 'q' \"d\""
        odd.mkdir()
        work = stage_work(self, ("alpha",), work=odd)
        self.assertEqual(build(work).returncode, 0)
        staged = json.loads((work / "staged.json").read_text())
        staged["codex"].update(wait_poll_s=0.05, slot_poll_s=0.05)
        write_json(work / "staged.json", staged)
        fixture, _, _ = node_fixture()
        prompts = {c["label"]: c["prompt"] for c in
                   self.execute(HARNESS / "sweep.js", fixture, json.loads((work / "args.json").read_text()))["calls"]}
        S = str(work)
        discover, fit = prompts["gpt6-discover:alpha"], prompts["gpt6-refute-fit:alpha"]
        start = re.search(r"^Then run: (bash .*)$", discover, re.M).group(1)
        wait = re.search(r"^Then run `(bash [^`]*)` with the Bash tool", discover, re.M).group(1)
        result = re.search(r"^Then run `(bash [^`]*)` and return", discover, re.M).group(1)
        make = re.search(r"^2\. Run: (python3 .*)$", fit, re.M).group(1)
        self.assertEqual(shlex.split(start), ["bash", f"{S}/codex_call.sh", "start", "gpt6-discover-alpha",
                                              f"{S}/prompts/gpt6-discover-alpha.txt", f"{S}/schemas/discover.json"])
        self.assertEqual(shlex.split(make), ["python3", f"{S}/make_prompt.py", "fit", f"{S}/inputs/alpha.json",
                                             f"{S}/gpt6/props-alpha.json", ">", f"{S}/prompts/gpt6-fit-alpha.txt"])
        self.assertIn(f"Use the Write tool to create {S}/gpt6/props-alpha.json", fit)  # a tool path, not shell
        # The commands run as the wrapper agent would run them, against a fake codex.
        bin_dir, cwd = temp_dir(self), temp_dir(self)
        (bin_dir / "codex").write_text(FAKE_CODEX.format(python=sys.executable), encoding="utf-8")
        (bin_dir / "codex").chmod(0o755)
        config = write_json(bin_dir / "config.json", {"last": LAST, "events": [COMPLETED]})
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
               "FAKE_CODEX_CONFIG": str(config)}
        env.pop("SWEEP_WORK_DIR", None)
        done = run(["bash", "-c", start], env=env, cwd=cwd)
        self.assertEqual((done.returncode, done.stdout.strip()), (0, "started gpt6-discover-alpha"), done.stderr)
        self.assertTrue(run(["bash", "-c", wait], env=env, cwd=cwd).stdout.startswith("done exit=0"))
        self.assertEqual(json.loads(run(["bash", "-c", result], env=env, cwd=cwd).stdout)["exit"], 0)
        write_json(work / "gpt6/props-alpha.json", [{"repository": "https://github.com/o/a1"}])
        done = run(["bash", "-c", make], env=env, cwd=cwd)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('"repository": "https://github.com/o/a1"', (work / "prompts/gpt6-fit-alpha.txt").read_text())
        self.assertEqual(list(cwd.iterdir()), [])  # no word of the path ran as a command

    def test_slug_is_the_same_function_as_sweep_common_slug(self):
        source = (HARNESS / "sweep.js").read_text(encoding="utf-8")
        function = re.search(r"^function slug\(u\) \{$.*?^\}$", source, re.M | re.S).group(0)
        cases = [*CANONICAL, *NOT_GITHUB, "Owner/Repo.GIT/", "https://github.com/O/a1.git", None]
        script = self.work / "slug.cjs"
        script.write_text(function + f"\nprocess.stdout.write(JSON.stringify({json.dumps(cases)}.map(slug)))\n",
                          encoding="utf-8")
        done = run(["node", script])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), [sweep_common.slug(case) for case in cases])


if __name__ == "__main__":
    unittest.main()
