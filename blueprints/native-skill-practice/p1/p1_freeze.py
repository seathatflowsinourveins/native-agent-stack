#!/usr/bin/env python3
"""P1 freeze manifest: the sha256 of every frozen input (Jev and TypeSafe design report r1, 5.0).

Section 5.0: freeze before any model call the case pack, the labelling rule, the labels and their
15% re-labels, the exact bytes each arm receives (after A2), the question text, the option orders,
the seeds, the scoring code and config, and each native arm's launch context; publish their sha256
in a pushed commit reachable from main before the first call. File mtimes do not count.

draft (default) records what exists and lists every missing role. --final refuses a missing role,
a pending adversarial insertion, an unlabelled case, a re-label list that differs from the drawn
one, a re-label written less than 24 hours after its first label, rendered inputs that differ from
the case pack, and a render check that does not reproduce them. External (private) files are
recorded by a caller-chosen name, sha256 and size only, never by host path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
P1 = "blueprints/native-skill-practice/p1"
BASE = "blueprints/native-skill-practice"

REQUIRED_ROLES = {
    "case_pack": "drawn cases, strata, provenance, seed, frame commit and frame sha256",
    "label_packet": "the blind packet the user labelled, with the frozen labelling rules",
    "labels": "the user's blind labels (label and claim type per case)",
    "relabels": "the seeded 15% re-labels, written at least 24 hours later and before any model call",
    "promptfoo_tests": "the generated test rows (case_id, repeat_index, source, claim, arm_group)",
    "rendered_inputs": "sha256 of the exact prompt bytes per case and prompt, after the A2 rule",
    "render_check": "promptfoo echo output reproducing every rendered input (no model call)",
    "harness": "promptfoo config, prompts (question text and option orders), provider adapters",
    "draw_and_scoring_code": "frame extractor, case pack, scoring code and its hash-locked requirements",
    "native_launch_contexts": "hash of each native arm's init event (O, S, G) from the smoke checks",
    "arm_l_checkpoint": "arm L checkpoint name, full revision and file hashes",
    "a2_custody": "gitleaks 8.30.1 and host-path/identity rule output over the exact bytes; home-directory canary",
    "canary": "the A1 canary: 10 frozen cases and their stored answers",
}
REPOSITORY_DEFAULTS = {
    "harness": [f"{P1}/promptfooconfig.yaml", f"{P1}/render-check.yaml", f"{P1}/prompts/jev-state.txt",
                f"{P1}/prompts/native-question.txt", f"{P1}/l_nli_provider.py", f"{BASE}/response.cjs",
                f"{BASE}/gate.cjs"],
    "draw_and_scoring_code": [f"{P1}/p1_frame.py", f"{P1}/p1_casepack.py", f"{P1}/p1_scoring.py",
                              f"{P1}/p1_freeze.py", f"{P1}/requirements-scoring.in",
                              f"{P1}/requirements-scoring.lock"],
}


def digest(path: Path) -> dict:
    raw = path.read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def entry(item, root: Path) -> dict:
    """{"path": repo-relative} or {"external": name, "file": private path}; the private path is dropped."""
    if isinstance(item, str):
        item = {"path": item}
    if "path" in item:
        target = (root / item["path"]).resolve()
        if root not in target.parents:
            raise ValueError(f"{item['path']} is outside the repository; record it as external")
        return {"path": item["path"], **digest(target)}
    return {"external": item["external"], **digest(Path(item["file"]))}


def compare_render(rendered: dict, echo_output: dict) -> dict:
    """Match promptfoo echo results (prompt label, case_id) to the rendered-input hashes.

    The echo provider's output is the prompt a provider receives. promptfoo 0.123.1 records
    prompt.raw in a re-serialized form (the 2026-10-03 draft check saw '{"source":"' where the
    provider received '{"source": "'), so prompt.raw is never the comparison. A file prompt's
    recorded label is "<label>: <path>: <template>"; the configured label is its first field."""
    expected = {(record["case_id"], record["prompt"]): record["sha256"] for record in rendered["inputs"]}
    results = echo_output.get("results", {})
    rows = results.get("results", []) if isinstance(results, dict) else results
    seen, mismatched = set(), []
    for row in rows:
        case = (row.get("vars") or (row.get("testCase") or {}).get("vars") or {}).get("case_id")
        prompt = str((row.get("prompt") or {}).get("label") or "").split(": ", 1)[0]
        output = (row.get("response") or {}).get("output")
        if (case, prompt) not in expected or not isinstance(output, str):
            continue
        seen.add((case, prompt))
        if hashlib.sha256(output.encode("utf-8")).hexdigest() != expected[(case, prompt)]:
            mismatched.append(f"{case}/{prompt}")
    missing = sorted(f"{case}/{prompt}" for case, prompt in set(expected) - seen)
    return {"expected": len(expected), "matched": len(seen) - len(mismatched), "mismatched": sorted(mismatched),
            "missing": missing, "passed": not mismatched and not missing}


def final_checks(pack: dict, labels: dict, relabels: dict, rendered: dict | None, render: dict | None,
                 rendered_now: list[dict]) -> list[str]:
    problems = []
    if pack.get("status") != "ready_for_labels" or any(case["pending_insertion"] for case in pack["cases"]):
        problems.append("the case pack still has a pending adversarial insertion")
    case_ids = {case["case_id"] for case in pack["cases"]}
    if set(labels) != case_ids:
        problems.append("labels do not cover exactly the drawn cases")
    if set(relabels) != set(pack["relabel"]["case_ids"]):
        problems.append("re-labels do not cover exactly the drawn re-label list")
    for case, record in relabels.items():
        first, second = labels.get(case, {}).get("labelled_at"), record.get("labelled_at")
        if not first or not second:
            problems.append(f"{case}: a label without labelled_at")
            continue
        gap = datetime.fromisoformat(second.replace("Z", "+00:00")) - datetime.fromisoformat(first.replace("Z", "+00:00"))
        if gap < timedelta(hours=24):
            problems.append(f"{case}: re-label written {gap} after the first label")
    if rendered is None or rendered.get("inputs") != rendered_now:
        problems.append("rendered inputs differ from the case pack and prompt templates")
    if render is None or not render.get("passed"):
        problems.append("the render check did not reproduce every rendered input")
    return problems


def _load_role(spec: dict, role: str, root: Path):
    item = spec[role][0]
    path = root / item if isinstance(item, str) else Path(item["file"] if "file" in item else root / item["path"])
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("labels", data) if role in ("labels", "relabels") and isinstance(data, dict) else data


def _casepack_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("p1_casepack_for_freeze", HERE / "p1_casepack.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_manifest(spec: dict, root: Path, final: bool) -> dict:
    roles = {}
    for role in REQUIRED_ROLES:
        items = list(spec.get(role) or REPOSITORY_DEFAULTS.get(role, []))
        roles[role] = [entry(item, root) for item in items]
    missing = [role for role, items in roles.items() if not items]
    manifest = {"schema": "jev-p1-freeze-manifest/1", "status": "frozen" if final else "draft",
                "required_roles": REQUIRED_ROLES, "roles": roles, "missing_roles": missing}
    if final:
        if missing:
            raise SystemExit("cannot freeze; missing roles: " + ", ".join(missing))
        pack = _load_role(spec, "case_pack", root)
        rendered = _load_role(spec, "rendered_inputs", root)
        render = compare_render(rendered, _load_role(spec, "render_check", root))
        problems = final_checks(pack, _load_role(spec, "labels", root), _load_role(spec, "relabels", root),
                                rendered, render, _casepack_module().rendered_inputs(pack))
        manifest["checks"] = {"render": render, "problems": problems}
        if problems:
            raise SystemExit("cannot freeze: " + "; ".join(problems))
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", type=Path, help='JSON {"<role>": ["repo/path" or {"external": name, "file": path}]}')
    parser.add_argument("--final", action="store_true", help="refuse anything missing or inconsistent")
    parser.add_argument("--render-echo", type=Path,
                        help="draft only: summarize a render check against the spec's rendered_inputs "
                             "(counts only; the echo file is neither hashed nor named)")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    spec = json.loads(args.spec.read_text(encoding="utf-8")) if args.spec else {}
    manifest = build_manifest(spec, REPO_ROOT, args.final)
    if args.render_echo and not args.final:
        summary = compare_render(_load_role(spec, "rendered_inputs", REPO_ROOT),
                                 json.loads(args.render_echo.read_text(encoding="utf-8")))
        manifest["draft_checks"] = {"render_check": {key: summary[key] for key in ("expected", "matched", "passed")},
                                    "render_check_method": "render-check.yaml (echo provider, no model call)"}
    args.out.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "missing_roles": manifest["missing_roles"],
                      **({"draft_checks": manifest["draft_checks"]} if "draft_checks" in manifest else {})}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
