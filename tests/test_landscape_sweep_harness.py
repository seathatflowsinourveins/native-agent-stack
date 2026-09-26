"""Synthetic-fixture tests for tools/sota-convergence/landscape-sweep (no network, no codex, no model calls).

A fake `codex` (and a fake `gh`) early on PATH stands in for the real CLI; sweep.js runs under node with stubbed
agent(), parallel() and pipeline() (skipped without node); convert.py's evidence is appended to a synthetic
saturation ledger checkout with scripts/saturation_ledger.py itself. Optional: BASH32_BINARY (a real bash 3.2, as
on macOS) and shellcheck.
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
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "sota-convergence" / "landscape-sweep"
sys.path.insert(0, str(ROOT / "scripts"))
import saturation_ledger as sl  # noqa: E402

NODE = shutil.which("node")
SHELLCHECK = shutil.which("shellcheck")
BASH32 = os.environ.get("BASH32_BINARY") if os.environ.get("BASH32_BINARY") and os.access(
    os.environ["BASH32_BINARY"], os.X_OK) else None
# prompts_sha256 of the 2026-09-26 run (its templates, sha256 of json.dumps(T, sort_keys=True, ensure_ascii=False)).
# A change detector: templates.json filled with that run's values must give it. An intended template edit changes
# every later run's prompts_sha256; update this test with it (the 2026-09-26 value stays in that run's record).
PROMPTS_SHA256_20260926 = "3adfbed7a83e85da3fd7951032e1fa3a579101772a47b211580065c6b42618d4"
REQ, PLAT = "a" * 64, "b" * 64
LIMIT_TEXT = ("You’ve hit your usage limit. Visit https://chatgpt.com/codex/settings/usage to purchase more "
              "credits or try again at Sep 30th, 2026 11:50 PM.")


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


def filled_templates(run_date="2026-10-26", count=2, skills_date="2026-09-25"):
    return build_args.fill_build(build_args.load_templates(), run_date, count, skills_date)


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
    children = [{"label": label, "requested_model": "sonnet" if label.startswith(("refute-facts", "gpt6-")) else "opus",
                 "resolved_models": ["claude-sonnet-5" if label.startswith(("refute-facts", "gpt6-")) else "claude-opus-5-5"],
                 "efforts": ["max"], "complete": True} for label in labels]
    return json.dumps({"transcript_dir": f"{transcript_root}/subagents/workflows/{run_id}", "status": status,
                       "reason": "fixture", "children": children}).encode("utf-8")


SYNTHETIC_LABELS = [f"{role}:{layer}" for layer in ("alpha", "beta") for role in
                    ("discover", "gpt6-discover", "refute-facts", "refute-fit", "gpt6-refute-fit")] + [
    f"{role}:beta:followup" for role in ("discover", "gpt6-discover", "refute-facts", "refute-fit", "gpt6-refute-fit")
] + ["critic"]


# --------------------------------------------------------------------------- templates and skills


class TemplateTests(unittest.TestCase):
    def test_filled_templates_reproduce_the_20260926_prompts_sha256(self):
        frozen = filled_templates("2026-09-26", 32, "2026-09-25")
        self.assertEqual(sweep_common.prompts_sha256(frozen), PROMPTS_SHA256_20260926)

    def test_only_per_call_placeholders_remain_after_filling(self):
        frozen = filled_templates()
        for key, text in frozen.items():
            self.assertEqual(set(make_prompt.PLACEHOLDER.findall(text)), make_prompt.RUNTIME_PLACEHOLDERS[key], key)
        self.assertIn("Date: 2026-10-26.", frozen["common"])
        self.assertIn("a 2-layer saturation sweep", frozen["critic"])

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

    def test_worker_schemas_are_strict_and_require_skills_used(self):
        for name in ("discover", "votes"):
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
        staged = json.loads((work / "staged.json").read_text())
        self.assertEqual(staged["codex"], {"model": "gpt-6-astra", "effort": "max", "slots": 3})
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
config = json.load(open(os.environ["FAKE_CODEX_CONFIG"]))
stdin, null = os.fstat(0), os.stat(os.devnull)
record = {{"argv": sys.argv[1:], "cwd": os.getcwd(), "stdin_devnull": (stdin.st_ino, stdin.st_dev) == (null.st_ino, null.st_dev),
          "stdin_read": sys.stdin.read()}}
if config.get("log"):
    with open(config["log"], "a") as log:
        log.write("start %.6f\\n" % time.time())
time.sleep(config.get("sleep", 0))
if config.get("last") is not None:
    with open(sys.argv[sys.argv.index("-o") + 1], "w") as out:
        json.dump(config["last"], out, indent=2)
for event in config.get("events", []):
    print(json.dumps(event))
sys.stdout.flush()
sys.stderr.write(config.get("stderr", ""))
if config.get("record"):
    with open(config["record"], "w") as out:
        json.dump(record, out)
if config.get("log"):
    with open(config["log"], "a") as log:
        log.write("end %.6f\\n" % time.time())
sys.exit(config.get("exit", 0))
"""


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
        return json.loads(self.call("result", name, shell=shell).stdout)

    def record(self):
        return json.loads((self.bin / "record.json").read_text())


LAST = {"repository": "https://github.com/ggml-org/llama.cpp", "latest_release": "b1", "stars_known": 1}
COMPLETED = {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 80, "output_tokens": 7,
                                                 "reasoning_output_tokens": 3}}


class RunnerTests(RunnerCase):
    def test_codex_command_line_stdin_and_directory(self):
        result = self.job("gpt6-probe", last=LAST, events=[{"type": "thread.started", "thread_id": "fixture"}, COMPLETED])
        directory = self.work / "gpt6" / "gpt6-probe"
        self.assertEqual(self.record()["argv"], [
            "--search", "exec", "--ignore-user-config", "--skip-git-repo-check", "-s", "read-only",
            "-m", "gpt-6-astra", "-c", 'model_reasoning_effort="max"',
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
        self.assertEqual(self.call("wait", "gpt6-fit-beta", "5").stdout.strip(), "done exit=none (the job is not running)")
        self.assertEqual(json.loads(self.call("result", "gpt6-fit-beta").stdout)["status"], "not_running")

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

    def test_other_failures_do_not_set_the_marker_and_rerun_on_the_next_start(self):
        log = self.bin / "runs.log"
        result = self.job("gpt6-flaky", exit=1, log=str(log), events=[{"type": "error", "message": "stream error"}])
        self.assertEqual((result["exit"], result["limit"]), (1, False))
        self.assertFalse((self.work / "LIMIT").exists())
        result = self.job("gpt6-flaky", last=LAST, log=str(log))
        self.assertEqual(result["exit"], 0)
        again = self.call("start", "gpt6-flaky", self.prompt, self.schema)
        self.assertEqual(again.stdout.strip(), "already done: gpt6-flaky")
        self.assertEqual(log.read_text().count("start"), 2)

    def test_a_running_job_is_not_started_twice(self):
        self.fake(last=LAST, sleep=2)
        self.assertEqual(self.call("start", "gpt6-slow", self.prompt, self.schema).returncode, 0)
        again = self.call("start", "gpt6-slow", self.prompt, self.schema)
        self.assertEqual(again.stdout.strip(), "already running: gpt6-slow")
        self.assertEqual(self.call("wait", "gpt6-slow", "0.1").stdout.strip(), "running")
        self.assertTrue(self.call("wait", "gpt6-slow", "20").stdout.startswith("done exit=0"))

    def test_slots_bound_concurrent_codex_processes(self):
        self.settings({"slots": 1})
        log = self.bin / "slots.log"
        self.fake(last=LAST, sleep=0.6, log=str(log))
        for name in ("gpt6-a", "gpt6-b"):
            self.assertEqual(self.call("start", name, self.prompt, self.schema).returncode, 0)
        for name in ("gpt6-a", "gpt6-b"):
            self.assertTrue(self.call("wait", name, "20").stdout.startswith("done exit=0"))
        events = [(float(t), kind) for kind, t in (line.split() for line in log.read_text().splitlines())]
        self.assertEqual([kind for _, kind in sorted(events)], ["start", "end", "start", "end"])
        slots = {(self.work / "gpt6" / name / "slot").read_text().strip() for name in ("gpt6-a", "gpt6-b")}
        self.assertEqual(slots, {"1"})

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
        self.assertIn("codex is not on PATH", done.stdout)
        self.assertEqual(self.call("wait", "gpt6-x", "5").stdout.strip(), "done exit=127")
        self.assertEqual(self.call("start", "../escape", self.prompt, self.schema).returncode, 2)
        self.assertEqual(self.call("bogus").returncode, 2)

    def test_work_dir_inside_a_repository_is_refused(self):
        repo = temp_dir(self)
        (repo / ".git").mkdir()
        (repo / "w").mkdir()
        done = run(["bash", HARNESS / "codex_call.sh", "--work-dir", repo / "w", "start", "gpt6-x", self.prompt,
                    self.schema], env=self.env)
        self.assertEqual(done.returncode, 2)
        self.assertIn("inside the git repository", done.stderr)

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
        ]
        for stderr, events, expected in cases:
            (directory / "stderr.txt").write_text(stderr)
            (directory / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\nnot json\n")
            self.assertEqual(codex_job.limit_error(directory), expected, (stderr, events))


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
        self.fake(last=LAST)
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


# --------------------------------------------------------------------------- convert


class ConvertTests(unittest.TestCase):
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
        self.assertEqual(out["returns"]["votes"]["alpha"][0]["facts"]["model"], "sonnet")

    def test_resolved_models_come_from_the_usage_record(self):
        document = usage_record.record(child_usage_raw("wf_fixture-1", SYNTHETIC_LABELS), 0, "cmd", ROOT)
        models = convert.resolved_models(document)
        self.assertEqual(models, {"discover": "claude-opus-5-5", "refute-facts": "claude-sonnet-5",
                                  "refute-fit": "claude-opus-5-5", "critic": "claude-opus-5-5"})
        out = self.convert(models=models)
        vote = out["returns"]["votes"]["alpha"][0]
        self.assertEqual((vote["facts"]["model"], vote["fit"]["claude"]["model"], vote["fit"]["gpt6"]["model"]),
                         ("claude-sonnet-5", "claude-opus-5-5", "gpt-6-astra"))

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
                          followup_vote["facts"]["model"]), ("followup", "max", "claude-sonnet-5"))
        # Without a usage record nothing was measured: the requested alias, and effort null rather than a claimed max.
        vote = self.convert()["returns"]["votes"]["alpha"][0]
        self.assertEqual((vote["facts"]["model"], vote["facts"]["effort"], vote["fit"]["claude"]["effort"]),
                         ("sonnet", None, None))

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

    def evidence(self, res):
        out = convert.convert(res, self.scope, LANE, convert.resolved_models(None))
        write_json(self.root / self.base / "returns.json", out["returns"])
        usage = usage_record.record(child_usage_raw("wf_fixture-1", SYNTHETIC_LABELS), 0, "cmd", ROOT)
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
        # A layer with retained failures must keep its retained_failure reopen entry.
        stripped = copy.deepcopy(out["layers"])
        stripped[0]["reopen"] = []
        with self.assertRaisesRegex(ValueError, r"no retained_failure reopen entry.*alpha"):
            self.result(dict(out, layers=stripped), reviews)

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
  calls.push({ label: opts.label, model: opts.model, effort: opts.effort, phase: opts.phase, schema: !!opts.schema, prompt })
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


EXPECTED_MODELS = {"discover": "opus", "gpt6-discover": "sonnet", "refute-facts": "sonnet", "refute-fit": "opus",
                   "gpt6-refute-fit": "sonnet", "critic": "opus"}


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
            self.assertEqual((call["model"], call["effort"], call["schema"]), (EXPECTED_MODELS[role], "max", True),
                             call["label"])
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
