#!/usr/bin/env python3
"""P1 freeze manifest: the sha256 of every frozen input (Jev and TypeSafe design report r1, 5.0).

Section 5.0: freeze before any model call the case pack, the labelling rule, the labels and their
15% re-labels, the exact bytes each arm receives (after A2), the question text, the option orders,
the seeds, the scoring code and config, and each native arm's launch context; publish their sha256
in a pushed commit reachable from main before the first call. File mtimes do not count.

draft (default) records what exists and lists every missing role. --final refuses a missing role,
a pending adversarial insertion, a pack whose current bytes are not the output of its last A2 pass,
A2 custody files that are not the original results of the recorded passes (item i is pass i, matched
by the canonical result_sha256 the pass recorded; a missing, extra, duplicate or mismatched original
is refused, and so are a custody file that is not a JSON A2 result object and a pass whose input or
result sha256 is missing, null or malformed, each under its own reason), a label packet that is not
label_packet(pack) in full (cases, rules, criteria, claim
types and instructions), a label or re-label record outside the packet's label_record contract, an
unlabelled case, a re-label list that differs from the drawn one, a re-label written less than 24
hours after its first label, promptfoo test rows that differ from the rows the pack, the labels'
native repeats and three local repeats generate, rendered inputs that differ from the case pack, and
a render check that does not reproduce them. External (private) files are recorded by a caller-chosen
name, sha256 and size only, never by host path.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import re
from datetime import timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
P1 = "blueprints/native-skill-practice/p1"
BASE = "blueprints/native-skill-practice"

REQUIRED_ROLES = {
    "case_pack": "drawn cases, strata, provenance, seed, frame commit and frame sha256",
    "label_packet": "the blind packet the user labelled, with the frozen labelling rules",
    "labels": "the user's blind labels (label and claim type per case), each in the packet's label_record contract",
    "relabels": "the seeded 15% re-labels, written at least 24 hours later and before any model call, in the "
                "same record contract",
    "promptfoo_tests": "the generated test rows (case_id, repeat_index, source, claim, arm_group): the bytes "
                       "p1_casepack.py tests writes from the pack, the labels' native repeats and three local repeats",
    "rendered_inputs": "sha256 of the exact bytes per case and arm input, after the A2 pass: the native "
                       "prompt (O, S, G), the jev-state prompt (L) and each J provider's HTTP request body",
    "render_check": "promptfoo output reproducing every rendered input with no model call: the echo provider "
                    "for the prompts, loopback copies of the J providers for the request bodies",
    "harness": "promptfoo config, prompts (question text and option orders), provider adapters",
    "draw_and_scoring_code": "frame extractor, case pack, scoring code and its hash-locked requirements",
    "native_launch_contexts": "hash of each native arm's init event (O, S, G) from the smoke checks",
    "arm_l_checkpoint": "arm L checkpoint name, full revision and file hashes",
    "a2_custody": "each A2 result the case pack records, in pass order: item i is the original result of "
                  "a2_passes[i], whose canonical sha256 is that pass's result_sha256 (gitleaks 8.30.1, the "
                  "host-path and identity rule and the home-directory and user-name canary over the exact bytes)",
    "canary": "the A1 canary: 10 frozen cases and their stored answers",
}
REPOSITORY_DEFAULTS = {
    "harness": [f"{P1}/promptfooconfig.yaml", f"{P1}/render-check.yaml", f"{P1}/prompts/jev-state.txt",
                f"{P1}/prompts/native-question.txt", f"{P1}/l_nli_provider.py", f"{P1}/response-model.cjs",
                f"{P1}/render_echo_server.py", f"{BASE}/response.cjs", f"{BASE}/gate.cjs"],
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


J_BODY_PROVIDERS = ("J-o0", "J-o1", "J-o2")


def compare_render(rendered: dict, echo_output: dict) -> dict:
    """Match render-check results to the rendered-input hashes, by (case_id, input).

    The echo provider's output is the prompt a provider receives, keyed by the prompt label. That is
    what O, S and G receive, not what arm J receives: promptfoo 0.123.1's HTTP provider parses the
    JSON-valued state back into an object and sends JSON.stringify of the whole body (providers-*.js
    processJsonBody and the fetch body). render-check.yaml therefore also sends every case through
    loopback copies of the three J providers, whose echo server returns the request body unchanged;
    those rows are keyed by the provider label (J-o0, J-o1, J-o2). promptfoo records prompt.raw in a
    re-serialized form, so prompt.raw is never the comparison. A file prompt's recorded label is
    "<label>: <path>: <template>"; the configured label is its first field."""
    expected = {(record["case_id"], record["input"]): record["sha256"] for record in rendered["inputs"]}
    results = echo_output.get("results", {})
    rows = results.get("results", []) if isinstance(results, dict) else results
    seen, mismatched = set(), []
    for row in rows:
        case = (row.get("vars") or (row.get("testCase") or {}).get("vars") or {}).get("case_id")
        provider = (row.get("provider") or {}).get("label")
        prompt = str((row.get("prompt") or {}).get("label") or "").split(": ", 1)[0]
        name = provider if provider in J_BODY_PROVIDERS else prompt
        output = (row.get("response") or {}).get("output")
        if (case, name) not in expected or not isinstance(output, str):
            continue
        seen.add((case, name))
        if hashlib.sha256(output.encode("utf-8")).hexdigest() != expected[(case, name)]:
            mismatched.append(f"{case}/{name}")
    missing = sorted(f"{case}/{name}" for case, name in set(expected) - seen)
    return {"expected": len(expected), "matched": len(seen) - len(mismatched), "mismatched": sorted(mismatched),
            "missing": missing, "passed": not mismatched and not missing}


@functools.cache
def _casepack_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("p1_casepack_for_freeze", HERE / "p1_casepack.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SHA256_HEX = re.compile(r"[0-9a-f]{64}")
# A custody file whose bytes are not JSON. The loader keeps it apart from a file that holds JSON null,
# so each is refused under its own reason.
NOT_JSON = object()
JSON_KINDS = {type(None): "JSON null", list: "a JSON array", str: "a JSON string", bool: "a JSON boolean",
              int: "a JSON number", float: "a JSON number"}


def sha256_field_problem(record: dict, field: str) -> str | None:
    """Why record[field] is not a sha256 as hexdigest writes it (64 lowercase hex characters), or None.
    A missing or null hash is refused here and never compared: None would equal None."""
    if field not in record:
        return f"has no {field}"
    if record[field] is None:
        return f"has a null {field}"
    if not isinstance(record[field], str) or SHA256_HEX.fullmatch(record[field]) is None:
        return f"has a {field} that is not 64 lowercase hex characters"
    return None


def a2_custody_problems(passes: list, originals: list) -> list[str]:
    """Bind the a2_custody files to the recorded A2 passes. Item i is the original result of pass i: its
    canonical sha256 (p1_casepack.canonical_sha256, the domain apply_a2 records as result_sha256) equals
    that pass's result_sha256, and it names that pass's input bytes and shows every check passed. A
    missing, extra, duplicate or mismatched original is refused.

    Before any pair is compared, every recorded pass must be an object whose input_sha256 and
    result_sha256 are sha256 strings, and every item an A2 result object: the schema apply_a2 requires,
    an input_sha256 sha256 string and a passed flag for every A2 check. NOT_JSON stands for a file that
    is not JSON and None for one that holds JSON null. Each malformation is refused under its own reason
    and never defaulted. Every pair is then compared on each field both sides hold well formed; a pair
    with a malformed side is already refused by that malformation, so no pair passes unchecked."""
    casepack = _casepack_module()
    problems, failed = [], set()

    def refuse(position: int, reason: str) -> None:
        problems.append(f"A2 custody: {reason}")
        failed.add(position)

    if len(originals) < len(passes):
        problems.append(f"A2 custody: {len(passes) - len(originals)} recorded pass(es) have no original result")
    if len(originals) > len(passes):
        problems.append(f"A2 custody: {len(originals) - len(passes)} original(s) beyond the {len(passes)} recorded pass(es)")
    for position, record in enumerate(passes, 1):
        if not isinstance(record, dict):
            refuse(position, f"recorded pass {position} is not an object")
            continue
        for field in ("input_sha256", "result_sha256"):
            reason = sha256_field_problem(record, field)
            if reason:
                refuse(position, f"recorded pass {position} {reason}")
    for position, item in enumerate(originals, 1):
        if item is NOT_JSON:
            refuse(position, f"item {position} is not JSON")
            continue
        if not isinstance(item, dict):
            kind = JSON_KINDS.get(type(item), f"a {type(item).__name__}")
            refuse(position, f"item {position} is {kind}, not an A2 result object")
            continue
        if item.get("schema") != casepack.A2_RESULT_SCHEMA:
            refuse(position, f"item {position} does not have schema {casepack.A2_RESULT_SCHEMA}")
        reason = sha256_field_problem(item, "input_sha256")
        if reason:
            refuse(position, f"item {position} {reason}")
        checks = item.get("checks")
        unpassed = [name for name in casepack.A2_CHECKS if not isinstance(checks, dict)
                    or not isinstance(checks.get(name), dict) or checks[name].get("passed") is not True]
        if unpassed:
            refuse(position, f"item {position} does not show these A2 checks passed: {unpassed}")
    given = [casepack.canonical_sha256(item) if isinstance(item, dict) else None for item in originals]
    repeated = [index + 1 for index, value in enumerate(given) if value is not None and given.count(value) > 1]
    if repeated:
        problems.append(f"A2 custody: items {repeated} are the same result")
    for position, (item, record) in enumerate(zip(originals, passes), 1):
        if not isinstance(item, dict) or not isinstance(record, dict):
            continue        # refused above: an item or pass record that is not an object has nothing to compare
        if sha256_field_problem(record, "result_sha256") is None and given[position - 1] != record["result_sha256"]:
            refuse(position, f"item {position}'s canonical sha256 is not the result_sha256 of recorded pass {position}")
        if (sha256_field_problem(record, "input_sha256") is None and sha256_field_problem(item, "input_sha256") is None
                and item["input_sha256"] != record["input_sha256"]):
            refuse(position, f"item {position} names other input bytes than the input_sha256 of recorded pass {position}")
    paired = sorted(position for position in failed if position <= min(len(originals), len(passes)))
    if paired:
        problems.append(f"A2 custody: items {paired} are not the original result of the recorded pass at that position")
    return problems


def final_checks(pack: dict, labels, relabels, rendered: dict | None, render: dict | None,
                 packet: dict | None, a2_originals: list, test_rows: str | None) -> list[str]:
    """The --final consistency checks. Every expected value comes from p1_casepack and the pack itself."""
    casepack = _casepack_module()
    problems = []
    if any(case["pending_insertion"] for case in pack["cases"]):
        problems.append("the case pack still has a pending adversarial insertion")
    passes = pack.get("a2_passes") or []
    if (pack.get("status") != "ready_for_labels" or not passes
            or passes[-1].get("output_sha256") != casepack.case_bytes_sha256(pack)):
        problems.append("the case pack's bytes are not the output of a recorded A2 pass")
    problems += a2_custody_problems(passes, a2_originals)
    # The whole packet, not only its cases: the labelling rules, criteria, claim types and instructions
    # the user labelled under are frozen inputs too (section 5.0).
    expected_packet = casepack.label_packet(pack)
    if (expected_packet["status"] != "ready" or not isinstance(packet, dict)
            or casepack.canonical_sha256(packet) != casepack.canonical_sha256(expected_packet)):
        problems.append("the label packet is not label_packet(pack) for the ready post-A2 pack: cases, rules, "
                        "criteria, claim types and instructions")
    record_problems = casepack.label_record_problems(labels, "label") + casepack.label_record_problems(relabels, "re-label")
    problems += record_problems
    labels = labels if isinstance(labels, dict) else {}
    relabels = relabels if isinstance(relabels, dict) else {}
    case_ids = {case["case_id"] for case in pack["cases"]}
    if set(labels) != case_ids:
        problems.append("labels do not cover exactly the drawn cases")
    if set(relabels) != set(pack["relabel"]["case_ids"]):
        problems.append("re-labels do not cover exactly the drawn re-label list")
    for case, record in sorted(relabels.items()):
        earlier = labels.get(case)
        first = casepack.utc_timestamp(earlier.get("labelled_at")) if isinstance(earlier, dict) else None
        second = casepack.utc_timestamp(record.get("labelled_at")) if isinstance(record, dict) else None
        if first is None or second is None:
            continue        # label_record_problems or the coverage check has named the record
        if second - first < timedelta(hours=24):
            problems.append(f"{case}: re-label written {second - first} after the first label")
    if record_problems or set(labels) != case_ids:
        problems.append("the promptfoo test rows were not checked: they depend on valid labels for every case")
    else:
        native = casepack.native_repeat_ids(labels)["case_ids"]
        expected_rows = casepack.promptfoo_rows_text(casepack.promptfoo_rows(pack, native, casepack.FROZEN_LOCAL_REPEATS))
        if test_rows != expected_rows:
            problems.append("the promptfoo test rows are not the rows the pack, the labels' native repeats and "
                            f"{casepack.FROZEN_LOCAL_REPEATS} local repeats generate")
    if rendered is None or rendered.get("inputs") != casepack.rendered_inputs(pack):
        problems.append("rendered inputs differ from the case pack and prompt templates")
    if render is None or not render.get("passed"):
        problems.append("the render check did not reproduce every rendered input")
    return problems


def _role_paths(spec: dict, role: str, root: Path) -> list[Path]:
    return [root / item if isinstance(item, str) else Path(item["file"]) if "file" in item else root / item["path"]
            for item in spec[role]]


def _load_role(spec: dict, role: str, root: Path):
    data = json.loads(_role_paths(spec, role, root)[0].read_text(encoding="utf-8"))
    return data.get("labels", data) if role in ("labels", "relabels") and isinstance(data, dict) else data


def _custody_original(path: Path):
    """A custody file's JSON value, or NOT_JSON when its bytes are not UTF-8 JSON (never None, which is
    what a file holding JSON null loads as)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return NOT_JSON


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
        originals = [_custody_original(path) for path in _role_paths(spec, "a2_custody", root)]
        test_rows = _role_paths(spec, "promptfoo_tests", root)[0].read_bytes().decode("utf-8", "replace")
        problems = final_checks(pack, _load_role(spec, "labels", root), _load_role(spec, "relabels", root),
                                rendered, render, _load_role(spec, "label_packet", root), originals, test_rows)
        manifest["checks"] = {"render": render, "a2_custody": {"recorded_passes": len(pack.get("a2_passes") or []),
                                                               "originals": len(originals)},
                              "problems": problems}
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
                                    "render_check_method": "render-check.yaml: the echo provider for the prompts and "
                                                           "loopback copies of the J providers for the request "
                                                           "bodies, in a network namespace with only loopback; "
                                                           "no model call"}
    args.out.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "missing_roles": manifest["missing_roles"],
                      **({"draft_checks": manifest["draft_checks"]} if "draft_checks" in manifest else {})}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
