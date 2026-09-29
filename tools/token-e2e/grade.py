#!/usr/bin/env python3
"""Independent frozen-check grader for the #381 token E2E (unit U9): the command line.

A local integration tool, not upstream acceptance and not a model run of its own: only `judge` calls a model, through the
routes in judge.py, and only after the run windows close. Standard library only, Python 3.11+. Subcommands: `spec`,
`bind`, `keys`, `capture`, `identity`, `grade`, `regrade`, `judge` (packets, codex, claude-args, collect), `controls`,
`differential`, `export` and `check-html`.

Exit status: 0 done (for `grade` and `regrade`: G-Q, M7, every M8 lane and M12 pass), 1 graded and not passing
(judgments pending included; for `controls` and `differential` a control or check that landed elsewhere), 75 a `judge
codex` run paused by a usage limit (resumable), 2 a refusal: `E_CODE field=value ...` on the first line of stderr and
nothing on stdout, with field names and never a private value. An unexpected exception is `E_INTERNAL stage=<command>`,
exit 2.

Private files (the spec, the bindings, keys and captures) are written create-only with mode 0600 and are refused
inside any git work tree, following design R22. Sources: repair-u9.design.md b3, R10, R12, R13, R19, R20, R22.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence as ev  # noqa: E402
import frozen_checks as fc  # noqa: E402
import judge as jd  # noqa: E402

BINDINGS_SCHEMA = "token-e2e-run-bindings/1"
KEYS_SCHEMA = "token-e2e-keys/1"
SPEC_SCHEMA = "token-e2e-grading-spec/1"
CAPTURE_SCHEMA = "token-e2e-capture/1"
CLAUDE_ARMS = ("B", "A", "A0")
LAUNCH_KEYS = {"run", "attempt", "preregistration_commit", "worktree_paths", "worktree_bases", "input_paths", "arm",
               "gates_verified", "frozen_tasks", "input_sha256"}
ROOT_PATHS = ("exec_checkout", "CLAUDE_ROOT", "CODEX_SESSIONS", "E2E_DIR", "judge_export_root", "archive_path")
ROOT_KEYS = set(ROOT_PATHS) | {"exec_rev", "memory_index_roots", "instruction_anchors"}
WINDOW_NAMES = ("W_C", "W_X")


class Parser(argparse.ArgumentParser):
    """Every parser and sub-parser refuses an abbreviated long option (allow_abbrev off): a frozen instrument takes the flags
    as written, so the command it records can be read against the sanitizer's flag table below."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)

    def error(self, message):
        raise fc.Refusal("E_ARGS", field="usage")


def build_parser():
    parser = Parser(prog="grade.py", description="Frozen-check grader for the #381 token E2E (U9).")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
    spec = sub.add_parser("spec", help="build the grading spec from the sealed preregistration and its grading block")
    spec.add_argument("--repo", required=True, help="checkout holding the preregistration commit")
    spec.add_argument("--preregistration-commit", required=True, help="40-hex commit of the Amendment 4 merge")
    spec.add_argument("--out", required=True, help="new private spec file (create-only, mode 0600)")
    bind = sub.add_parser("bind", help="record the private launch inputs")
    bind.add_argument("--launch-args", action="append", required=True, metavar="ARM=FILE",
                      help="a Claude arm's Workflow args as JSON (repeatable: B, A, A0)")
    bind.add_argument("--codex-bindings", help="U10's codex-bindings.json")
    bind.add_argument("--sentinels", required=True)
    bind.add_argument("--windows", required=True)
    bind.add_argument("--roots", required=True)
    bind.add_argument("--out", required=True)
    keys = sub.add_parser("keys", help="compute every freeze key from pinned Git content")
    keys.add_argument("--spec", required=True)
    keys.add_argument("--bindings", required=True)
    keys.add_argument("--repo", required=True)
    keys.add_argument("--memory", action="store_true", help="freeze the historical ai-memory records (R9)")
    keys.add_argument("--qmd", action="store_true", help="record qmd coverage of adoption/update.md")
    keys.add_argument("--out", required=True)
    capture = sub.add_parser("capture", help="observe pages, trees and commands around a window or an arm")
    capture.add_argument("--spec", required=True)
    capture.add_argument("--bindings", required=True)
    capture.add_argument("--phase", required=True, choices=["w-open", "pre-arm", "post-arm", "w-close", "post-w"])
    capture.add_argument("--family", choices=["claude", "codex"])
    capture.add_argument("--arm")
    capture.add_argument("--out-dir", required=True)
    identity = sub.add_parser("identity", help="build the run identity table from the recorded launches")
    identity.add_argument("--spec", required=True)
    identity.add_argument("--bindings", required=True)
    identity.add_argument("--launch-records", required=True, help="launch records of the main, strict, Agent-path and team rows")
    identity.add_argument("--codex-rows", help="U10's identity-rows.codex.json")
    identity.add_argument("--out", required=True, help="new private table (create-only, mode 0600)")
    grade = sub.add_parser("grade", help="grade the retained evidence into a private table and an ID-free aggregate")
    grade.add_argument("--spec", required=True)
    grade.add_argument("--repo", required=True, help="checkout used to regenerate the spec (R20)")
    # The inputs below are checked after the regeneration check, so a hand-edited spec is refused first.
    grade.add_argument("--bindings")
    grade.add_argument("--identity-table")
    grade.add_argument("--keys")
    grade.add_argument("--captures", help="directory of the capture command's files")
    grade.add_argument("--join-ledger", action="append", default=[], metavar="FAMILY=FILE",
                       help="U4's private join ledger of one family window (claude, codex)")
    grade.add_argument("--adoption-report", action="append", default=[], metavar="FAMILY=FILE",
                       help="U4's adoption report of that window (its m12_inputs cross-check U9's sums)")
    grade.add_argument("--run-mode", action="append", default=[], metavar="ARM=FILE",
                       help="U2's run-mode output of a Claude arm's Workflow run")
    grade.add_argument("--call-ledger", action="append", default=[], help="U2's private call ledger (JSONL, repeatable)")
    grade.add_argument("--codex-events-dir", help="directory of <identity>.events.jsonl (default: E2E_DIR)")
    grade.add_argument("--codex-driver", help="U10's codex-driver directory (ledger.jsonl and attempts/)")
    grade.add_argument("--judgments", help="retained judgments: a JSONL file, or a judge directory holding judgments-*.jsonl; "
                                            "none leaves every D clause pending")
    grade.add_argument("--controls", help="the report `controls --out` wrote; its counts are published under `controls`")
    grade.add_argument("--out-private", help="new private directory for the table and the collected records")
    grade.add_argument("--out", help="new aggregate file (create-only, mode 0600)")
    regrade = sub.add_parser("regrade", help="repeat the grading from a private directory alone")
    regrade.add_argument("--from", dest="source", required=True, help="the private directory a grade run wrote")
    regrade.add_argument("--judgments", help="judgments to apply instead of the retained ones (a file or a judge directory)")
    regrade.add_argument("--out-private", required=True)
    regrade.add_argument("--out", required=True)
    judge = sub.add_parser("judge", help="class D judges: packets, the two blind routes and collect")
    judge_sub = judge.add_subparsers(dest="judge_command", required=True, parser_class=Parser)
    packets = judge_sub.add_parser("packets", help="build the scrubbed packets and the calibration controls")
    packets.add_argument("--from", dest="private", required=True, help="the private directory a grade run wrote")
    packets.add_argument("--repo", required=True, help="checkout holding the preregistration commit and the exec revision")
    packets.add_argument("--out-dir", required=True, help="new private judge directory (index, packets, results)")
    codex = judge_sub.add_parser("codex", help="judge the Claude answers with gpt-6-astra at max effort (after both windows)")
    codex.add_argument("--index", required=True, help="the judge directory `judge packets` wrote")
    codex.add_argument("--accept-unavailable", action="store_true",
                       help="after a usage limit, finish with the unrun packets as unknown(judge_unavailable)")
    codex.add_argument("--timeout", type=float, default=jd.CALL_TIMEOUT, help="seconds allowed per codex call")
    claude_args = judge_sub.add_parser("claude-args", help="the Workflow scriptPath and args for the Codex answers")
    claude_args.add_argument("--index", required=True)
    collect = judge_sub.add_parser("collect", help="verify and assemble the Workflow's judgments")
    collect.add_argument("--index", required=True)
    collect.add_argument("--result", required=True, help="the Workflow's returned JSON")
    collect.add_argument("--transcripts", required=True, help="the run's agent transcript directory")
    rehearse = judge_sub.add_parser("rehearse", help="two planted controls through a route, before Amendment 4")
    rehearse.add_argument("--route", required=True, choices=["codex", "claude"])
    rehearse.add_argument("--out-dir", required=True, help="new private directory (the claude collect step reuses it)")
    rehearse.add_argument("--export-dir", help="claude route: new neutral directory for the two packets")
    rehearse.add_argument("--result", help="claude route, second step: the Workflow's returned JSON")
    rehearse.add_argument("--transcripts", help="claude route, second step: the run's agent transcript directory")
    rehearse.add_argument("--timeout", type=float, default=jd.CALL_TIMEOUT, help="seconds allowed per codex call")
    controls = sub.add_parser("controls", help="planted class A, B and C controls, the E1 answers and the calibration files")
    controls.add_argument("--spec", required=True)
    controls.add_argument("--repo", required=True, help="the exec checkout (E1 receipts and their pinned keys)")
    controls.add_argument("--out", help="new file for the counts (create-only, mode 0600); `grade --controls` embeds it")
    differential = sub.add_parser("differential", help="agree with the retained checks of the earlier runs (private inputs)")
    differential.add_argument("--inputs", required=True, help="directory holding rtk-296 and rtk-343")
    export = sub.add_parser("export", help="one returned_results record with the aggregate as an attachment")
    export.add_argument("--from", dest="private", required=True, help="the private directory a grade run wrote")
    export.add_argument("--aggregate", required=True, help="the aggregate file that grade run wrote")
    export.add_argument("--export-dir", required=True, help="new neutral directory for the manifest and its attachment")
    check_html = sub.add_parser("check-html", help="the privacy canary over a generated HTML report")
    check_html.add_argument("html")
    check_html.add_argument("--from", dest="private_dir", help="a grade run's private directory (adds its run values)")
    return parser


# ---- Files ------------------------------------------------------------------------------------------------------

def read_file(path, field, code="E_BIND"):
    try:
        with open(path, "rb") as stream:
            return stream.read()
    except OSError:
        raise fc.Refusal(code, field=field) from None


def load_json(path, field, code="E_BIND"):
    data = read_file(path, field, code)
    try:
        document = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise fc.Refusal(code, field=field) from None
    if not isinstance(document, dict):
        raise fc.Refusal(code, field=field)
    return document


def refuse_output(path):
    issue = fc.private_path_issue(path)
    if issue:
        raise fc.Refusal("E_PATH", reason=issue)


# ---- spec (R20) -------------------------------------------------------------------------------------------------

def newest_seal(text):
    """(amendment number, {file name: sha256}) of the newest `**Amendment N seal` table of a README, else (None, {})."""
    best, start = None, 0
    while True:
        index = text.find("**Amendment ", start)
        if index < 0:
            break
        digits_at = index + len("**Amendment ")
        end = digits_at
        while end < len(text) and text[end].isdigit():
            end += 1
        if end > digits_at and text[end:end + 5] == " seal":
            number = int(text[digits_at:end])
            if best is None or number >= best[0]:
                best = (number, index)
        start = index + 1
    if best is None:
        return None, {}
    rows, in_table = {}, False
    for line in text[best[1]:].split("\n")[1:]:
        stripped = line.strip()
        if stripped.startswith("|"):
            in_table = True
            cells = [cell.strip().strip("`") for cell in stripped.strip("|").split("|")]
            if len(cells) >= 2 and fc.is_hex(cells[1], 64):
                rows[cells[0]] = cells[1]
        elif in_table:
            break
    return best[0], rows


def spec_bytes(repo, commit):
    """The canonical spec for a preregistration commit; every refusal names a code and a field."""
    if not fc.is_hex(commit, 40):
        raise fc.Refusal("E_ARGS", field="preregistration_commit")
    source = fc.GitSources(repo, commit)
    prereg = source.read(fc.PREREG_PATH)
    readme = source.read(fc.README_PATH)
    if prereg is None or readme is None:
        raise fc.Refusal("E_PREREG", reason="missing")
    readme_text = readme.decode("utf-8", errors="replace")
    number, rows = newest_seal(readme_text)
    if number is None:
        raise fc.Refusal("E_PREREG", reason="no_seal")
    if rows.get("preregistration.json") != fc.sha256_hex(prereg):
        raise fc.Refusal("E_PREREG", reason="seal_mismatch")
    document = fc.load_preregistration(prereg)
    block = document.get("grading")
    if block is None:
        raise fc.Refusal("E_GRADING_BLOCK", field="missing")
    if not any(line.startswith("## Amendment 4") for line in readme_text.split("\n")):
        raise fc.Refusal("E_GRADING_BLOCK", field="amendment")
    fc.validate_grading_block(block)
    if block["registry_sha256"] != fc.registry_sha256():
        raise fc.Refusal("E_GRADING_BLOCK", field="registry_sha256")
    dropped = block["dropped_tasks"]
    frozen = document.get("thresholds") or {}
    thresholds = {"minimum_arm_b_opportunities": document.get("minimum_arm_b_opportunities")}
    for name in ("M7", "M8", "M12", "G-Q"):
        thresholds[name] = (frozen.get(name) or {}).get("criteria")
    spec = {
        "schema": SPEC_SCHEMA,
        "thresholds": thresholds,
        "preregistration": {"sha256": fc.sha256_hex(prereg), "commit": commit, "bytes": len(prereg)},
        "seal": {"amendment": number, "sha256": rows["preregistration.json"]},
        "grading_block": {"sha256": fc.sha256_hex(fc.canonical(block)), "grammar": block["grammar"],
                          "d_extract": block["d_extract"], "dropped_tasks": dropped},
        "block": block,
        "readings": block["readings"],
        "alternatives": fc.alternatives(block["readings"]),
        "registry_sha256": fc.registry_sha256(),
        "inventory": fc.build_inventory(prereg, dropped),
        "tasks": fc.build_tasks(prereg, dropped),
    }
    return fc.canonical(spec)


def spec_matches(spec_path, repo):
    """R20: the spec file must equal the spec regenerated from its own preregistration commit, byte for byte."""
    data = read_file(spec_path, "spec", "E_SPEC_MISMATCH")
    try:
        commit = json.loads(data.decode("utf-8"))["preregistration"]["commit"]
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        return False
    return spec_bytes(repo, commit) == data


def cmd_spec(args):
    refuse_output(args.out)
    fc.private_create(args.out, spec_bytes(args.repo, args.preregistration_commit))
    return 0


def load_spec(path):
    data = read_file(path, "spec", "E_SPEC_MISMATCH")
    try:
        return json.loads(data.decode("utf-8")), data
    except (ValueError, UnicodeDecodeError):
        raise fc.Refusal("E_SPEC_MISMATCH") from None


# ---- bind (R19) -------------------------------------------------------------------------------------------------

def _bind_strings(mapping, field):
    if not isinstance(mapping, dict) or not all(isinstance(key, str) and isinstance(value, str)
                                                for key, value in mapping.items()):
        raise fc.Refusal("E_BIND", field=field)
    return mapping


def _abs_path(value, field):
    if not isinstance(value, str) or not os.path.isabs(value):
        raise fc.Refusal("E_BIND", field=field)
    return value


def _launch_arm(arm, args_document):
    if set(args_document) - LAUNCH_KEYS:
        raise fc.Refusal("E_BIND", field="schema")
    if "arm" in args_document and args_document["arm"] != arm:
        raise fc.Refusal("E_BIND", field="arm")
    if not isinstance(args_document.get("run"), str) or not args_document["run"]:
        raise fc.Refusal("E_BIND", field="run")
    attempt = args_document.get("attempt")
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        raise fc.Refusal("E_BIND", field="attempt")
    commit = args_document.get("preregistration_commit")
    if commit is not None and not fc.is_hex(commit, 40):
        raise fc.Refusal("E_BIND", field="preregistration_commit")
    paths = _bind_strings(args_document.get("worktree_paths", {}), "worktree_paths")
    bases = _bind_strings(args_document.get("worktree_bases", {}), "worktree_bases")
    if set(paths) != set(bases) or not all(fc.is_hex(base, 40) for base in bases.values()):
        raise fc.Refusal("E_BIND", field="worktree_bases")
    for value in paths.values():
        _abs_path(value, "worktree_paths")
    inputs = _bind_strings(args_document.get("input_paths", {}), "input_paths")
    expected = args_document.get("input_sha256", {})
    bound = {}
    for task in sorted(inputs):
        path = _abs_path(inputs[task], "input_paths")
        try:
            with open(path, "rb") as stream:
                data = stream.read()
        except OSError:
            raise fc.Refusal("E_BIND", field="input_paths") from None
        if task in expected and expected[task] != fc.sha256_hex(data):
            raise fc.Refusal("E_BIND", field="input_paths")
        bound[task] = {"path": path, "sha256": fc.sha256_hex(data), "bytes": len(data)}
    return {"attempt": attempt, "preregistration_commit": commit, "worktree_paths": dict(paths),
            "worktree_bases": dict(bases), "input_paths": bound}


def _sentinels(document):
    if set(document) - {"sentinels"} or not isinstance(document.get("sentinels"), dict):
        raise fc.Refusal("E_BIND", field="schema")
    result = {}
    for task, entry in document["sentinels"].items():
        if not isinstance(entry, dict) or set(entry) - {"value", "sha256", "sibling_value"}:
            raise fc.Refusal("E_BIND", field="schema")
        if not isinstance(entry.get("value"), str) or fc.sha256_hex(entry["value"]) != entry.get("sha256"):
            raise fc.Refusal("E_BIND", field="sentinel")
        result[task] = {"value": entry["value"], "sha256": entry["sha256"], "sibling_value": entry.get("sibling_value")}
    return result


def _windows(document):
    if set(document) - set(WINDOW_NAMES):
        raise fc.Refusal("E_BIND", field="schema")
    result = {}
    for name in WINDOW_NAMES:
        entry = document.get(name)
        if not isinstance(entry, dict) or set(entry) - {"since", "until"}:
            raise fc.Refusal("E_BIND", field="schema" if isinstance(entry, dict) else "windows")
        since, until = fc.parse_utc(entry.get("since")), fc.parse_utc(entry.get("until"))
        if since is None or until is None or since >= until:
            raise fc.Refusal("E_BIND", field="windows")
        result[name] = {"since": entry["since"], "until": entry["until"]}
    return result


def _roots(document):
    if set(document) - ROOT_KEYS:
        raise fc.Refusal("E_BIND", field="schema")
    for name in sorted(ROOT_KEYS):
        if name not in document:
            raise fc.Refusal("E_BIND", field=name)
    if not fc.is_hex(document["exec_rev"], 40):
        raise fc.Refusal("E_BIND", field="exec_rev")
    result = {"exec_rev": document["exec_rev"]}
    for name in ROOT_PATHS:
        result[name] = _abs_path(document[name], name)
    for name in ("memory_index_roots", "instruction_anchors"):
        value = document[name]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise fc.Refusal("E_BIND", field=name)
        result[name] = list(value)
    return result


def _codex_bindings(document, exec_rev):
    """U10's codex-bindings.json (the stated interface, consumed loosely): its exec_rev must equal ours; each tree keeps
    its path, base and slot, and a sentinel joins the record by task."""
    if document.get("exec_rev") != exec_rev:
        raise fc.Refusal("E_BIND", field="exec_rev")
    trees, sentinels = [], {}
    for tree in document.get("trees", []):
        if not isinstance(tree, dict) or not fc.is_hex(tree.get("base"), 40):
            raise fc.Refusal("E_BIND", field="codex_bindings")
        entry = {"task": tree.get("task"), "slot": tree.get("slot"), "arm": tree.get("arm"), "kind": tree.get("kind"),
                 "path": _abs_path(tree.get("path"), "codex_bindings"), "base": tree["base"]}
        sentinel = tree.get("sentinel")
        if sentinel:
            if fc.sha256_hex(sentinel.get("value", "")) != sentinel.get("sha256"):
                raise fc.Refusal("E_BIND", field="sentinel")
            entry["sentinel_sha256"] = sentinel["sha256"]
            if tree.get("task"):
                sentinels[tree["task"]] = {"value": sentinel["value"], "sha256": sentinel["sha256"],
                                           "sibling_value": sentinel.get("sibling_value")}
        trees.append(entry)
    record = {"trees": trees}
    if isinstance(document.get("conditions"), dict):
        record["conditions"] = document["conditions"]
    if "parent_servers" in document:  # the parent's `codex mcp list` names at the freeze (M11 for role children)
        servers = document["parent_servers"]
        if not isinstance(servers, list) or not all(isinstance(item, str) and item for item in servers):
            raise fc.Refusal("E_BIND", field="codex_bindings")
        record["parent_servers"] = list(servers)
    return record, sentinels


def cmd_bind(args):
    refuse_output(args.out)
    arms, tokens = {}, set()
    for item in args.launch_args:
        arm, sep, path = item.partition("=")
        if not sep or arm not in CLAUDE_ARMS or arm in arms:
            raise fc.Refusal("E_ARGS", field="launch_args")
        document = load_json(path, "launch_args")
        arms[arm] = _launch_arm(arm, document)
        tokens.add(document["run"])
    if len(tokens) != 1:
        raise fc.Refusal("E_BIND", field="run")
    sentinels = _sentinels(load_json(args.sentinels, "sentinels"))
    windows = _windows(load_json(args.windows, "windows"))
    roots = _roots(load_json(args.roots, "roots"))
    record = {"schema": BINDINGS_SCHEMA, "exec_rev": roots["exec_rev"], "exec_checkout": roots["exec_checkout"],
              "run_token_sha256": fc.sha256_hex(next(iter(tokens))), "arms": arms, "sentinels": sentinels,
              "windows": windows, "roots": {name: roots[name] for name in sorted(roots)
                                            if name not in ("exec_rev",)},
              "instruction_anchors": roots["instruction_anchors"]}
    if args.codex_bindings:
        codex, codex_sentinels = _codex_bindings(load_json(args.codex_bindings, "codex_bindings"), roots["exec_rev"])
        record["codex"] = codex
        record["sentinels"].update(codex_sentinels)
    fc.private_create(args.out, fc.canonical(record))
    return 0


def load_bindings(path):
    document = load_json(path, "schema", "E_BIND")
    if document.get("schema") != BINDINGS_SCHEMA:
        raise fc.Refusal("E_BIND", field="schema")
    return document


# ---- keys -------------------------------------------------------------------------------------------------------

def cmd_keys(args):
    refuse_output(args.out)
    if not spec_matches(args.spec, args.repo):
        raise fc.Refusal("E_SPEC_MISMATCH")
    spec, spec_data = load_spec(args.spec)
    bindings = load_bindings(args.bindings)
    bindings_data = read_file(args.bindings, "schema")
    block = spec["block"]
    memory = qmd = None
    if args.memory:
        # The earliest SINCE of either window: a page written after the first window opens must not count as history
        # for any arm, because arms share one store (U9-D13).
        since = min((window["since"] for window in bindings["windows"].values()), key=fc.parse_utc)
        memory = fc.memory_keys(block["memory"], block["memory_scope"], since)
    if args.qmd:
        qmd = fc.qmd_coverage(block["qmd"], ["adoption/update.md"])
    inputs = {}
    for arm in sorted(bindings["arms"]):
        inputs.update(bindings["arms"][arm]["input_paths"])
    keys = fc.compute_keys(spec["tasks"], fc.GitSources(args.repo, bindings["exec_rev"]),
                           fc.GitSources(args.repo, spec["preregistration"]["commit"]), inputs, memory, qmd, bindings)
    document = {"schema": KEYS_SCHEMA, "exec_rev": bindings["exec_rev"], "spec_sha256": fc.sha256_hex(spec_data),
                "bindings_sha256": fc.sha256_hex(bindings_data), "keys": keys}
    # Not the canonical (key-sorted) form: a key's records keep the field order of their source, which R2-02 compares.
    fc.private_create(args.out, json.dumps(document, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    return 0


# ---- capture (R10, R12, R13) ------------------------------------------------------------------------------------

def _write_capture(out_dir, name, record):
    record = dict({"schema": CAPTURE_SCHEMA}, **record)
    fc.private_create(os.path.join(out_dir, name), (json.dumps(record, indent=1, sort_keys=True) + "\n").encode("utf-8"))


def _run_token(bindings):
    token = os.environ.get("RUN_TOKEN", "")
    if not token or fc.sha256_hex(token) != bindings.get("run_token_sha256"):
        raise fc.Refusal("E_CAPTURE", field="run_token")
    return token


def _tree_for(bindings, family, arm, task_id):
    if family == "claude":
        return bindings["arms"].get(arm, {}).get("worktree_paths", {}).get(task_id)
    trees = [tree for tree in (bindings.get("codex") or {}).get("trees", []) if tree.get("task") == task_id]
    if not trees:
        return None
    named = [tree for tree in trees if tree.get("arm") == arm]
    if named:
        return named[0]["path"]
    if len(trees) == 1 and trees[0].get("arm") is None:
        return trees[0]["path"]
    raise fc.Refusal("E_CAPTURE", field="codex_tree")  # several trees and none names this arm


def _conditions(bindings, family, arm, token, home):
    """(environment, plain environment, sandbox prefix, conditions record) of the arm (R10). Every environment is an
    allowlist (PATH, LANG, TMPDIR, a HOME that is not the operator's) plus the frozen names, never the operator's own."""
    plain = fc.minimal_env(home)
    if family == "claude":
        arm_env = dict(plain, RTK_DB_PATH=os.path.join(bindings["roots"]["E2E_DIR"], "rtk.db"),
                       OTEL_RESOURCE_ATTRIBUTES=f"ecosystem.task.id={token}")
        return arm_env, plain, (), {"kind": "claude_env", "verified": True}
    conditions = (bindings.get("codex") or {}).get("conditions")
    if not conditions:
        return plain, plain, (), {"kind": "codex_sandbox", "verified": False, "reason": "conditions_unfrozen"}
    plain_home = plain
    plain = dict(plain_home, **{str(name): str(value) for name, value in (conditions.get("env") or {}).items()})

    def prefix(cwd):
        argv = [conditions.get("launcher") or "codex", "sandbox", "-C", str(cwd)]
        if conditions.get("profile"):
            argv += ["-p", conditions["profile"]]
        for item in conditions.get("config", []):
            argv += ["-c", item]
        return argv + ["--"]
    return plain, plain_home, prefix, {"kind": "codex_sandbox", "verified": None}


def _verify_sandbox(prefix, tree, conditions):
    try:
        done = subprocess.run(prefix(tree) + ["true"], cwd=tree, capture_output=True, stdin=subprocess.DEVNULL, timeout=120)
        ok = done.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        ok = False
    conditions["verified"] = ok
    if not ok:
        conditions["reason"] = "sandbox_probe_failed"


def _arm_tasks(spec, template, family, arm):
    return [task for task in spec["tasks"] if task["template"] == template and task["family"] == family
            and arm in task["arms"]]


def capture_arm(args, spec, bindings):
    if args.family == "claude" and args.arm not in bindings["arms"]:
        raise fc.Refusal("E_ARGS", field="arm")
    token = _run_token(bindings)
    home = tempfile.mkdtemp(prefix="u9-home-")
    try:
        return _capture_arm(args, spec, bindings, token, home)
    finally:
        shutil.rmtree(home, ignore_errors=True)


def _capture_arm(args, spec, bindings, token, home):
    arm_env, plain_env, prefix, conditions = _conditions(bindings, args.family, args.arm, token, home)
    name = f"arm-{args.family}-{args.arm}-{args.phase}.json"
    pre_name = f"arm-{args.family}-{args.arm}-pre-arm.json"
    pre = None
    if args.phase == "post-arm":
        pre_path = os.path.join(args.out_dir, pre_name)
        if not os.path.exists(pre_path):
            raise fc.Refusal("E_CAPTURE", field="pre_arm")
        pre = load_json(pre_path, "pre_arm", "E_CAPTURE")
    started = fc.utc_now()
    record = {"phase": args.phase, "family": args.family, "arm": args.arm, "started_at": started, "t0": {},
              "trees": {}}
    # One file per family, arm and phase: Claude and Codex both have an arm B and `grade` reads one directory.
    for task in _arm_tasks(spec, "T0", args.family, args.arm):
        tree = _tree_for(bindings, args.family, args.arm, task["id"])
        if tree is None or not os.path.isdir(tree):
            record["t0"][task["id"]] = {"error": "tree_missing"}
            continue
        cond = dict(conditions)
        if callable(prefix) and cond.get("verified") is None:
            _verify_sandbox(prefix, tree, cond)
        if args.phase == "pre-arm":
            arm_capture = fc.capture_t0(tree, arm_env, prefix)
            plain_capture = fc.capture_t0(tree, plain_env, ())
            arm_capture["conditions"] = cond
            plain_capture["conditions"] = {"kind": "plain", "verified": True}
            record["t0"][task["id"]] = {"arm": arm_capture, "plain": plain_capture}
            record["trees"][task["id"]] = arm_capture["tree"]
        else:
            before = (pre["trees"] or {}).get(task["id"])
            if before is None:
                record["t0"][task["id"]] = {"error": "pre_arm_missing"}
                continue
            arm_capture = fc.post_capture_t0(tree, before, arm_env, prefix)
            if "discarded" in arm_capture:
                record["t0"][task["id"]] = arm_capture
            else:
                arm_capture["conditions"] = cond
                plain_capture = fc.post_capture_t0(tree, before, plain_env, ())
                plain_capture["conditions"] = {"kind": "plain", "verified": True}
                record["t0"][task["id"]] = {"arm": arm_capture, "plain": plain_capture}
            record["trees"][task["id"]] = fc.tree_state(tree)
    exec_checkout = bindings["exec_checkout"]
    if os.path.isdir(exec_checkout):
        record["exec_checkout"] = {"tree": fc.tree_state(exec_checkout), "entries": fc.porcelain_entries(exec_checkout)}
    else:
        record["exec_checkout"] = {"error": "missing"}
    if args.phase == "post-arm":
        record["builders"] = {}
        for task in _arm_tasks(spec, "T31", args.family, args.arm):
            tree = _tree_for(bindings, args.family, args.arm, task["id"])
            if tree and os.path.isdir(tree):
                target = os.path.join(tree, "fixtures", "before.py")
                data = fc.DirSources(tree).read("fixtures/before.py") if os.path.exists(target) else None
                record["builders"][task["id"]] = {
                    "head": fc.tree_state(tree)["head"], "entries": fc.porcelain_entries(tree),
                    "before_sha256": fc.sha256_hex(data) if data is not None else None,
                    "before_py": data.decode("utf-8", errors="replace")[:65536] if data is not None else None}
        since = fc.parse_utc(pre.get("completed_at")) or 0
        record["processes"] = fc.list_processes(since - 1)
        record["clones"] = {}
        for task in _arm_tasks(spec, "T11", args.family, args.arm):
            clone = _tree_for(bindings, args.family, args.arm, task["id"])
            if clone and os.path.isdir(clone):
                head = fc.tree_state(clone)["head"]
                base = bindings["arms"].get(args.arm, {}).get("worktree_bases", {}).get(task["id"])
                clean = fc.porcelain_entries(clone) == []
                key = fc.key_T11(fc.DirSources(clone), task["params"]) if clean and head == base else None
                record["clones"][task["id"]] = {"head": head, "base_ok": head == base, "clean": clean, "key": key}
    record["completed_at"] = fc.utc_now()
    _write_capture(args.out_dir, name, record)


def capture_pages(args, spec):
    pages = [fc.capture_page(kind, spec["block"]["pages"][kind]) for kind in fc.PAGE_KINDS]
    _write_capture(args.out_dir, f"pages-{args.phase}-{args.family}.json",
                   {"phase": args.phase, "family": args.family, "captured_at": fc.utc_now(), "pages": pages})


def capture_after_window(args, spec, bindings):
    acceptance = {task["id"]: task["params"]["acceptance_argv"] for task in spec["tasks"] if task["template"] == "T27"}
    result = fc.capture_post_w(bindings["exec_checkout"], bindings["exec_rev"], acceptance)
    _write_capture(args.out_dir, "post-w.json", dict(result, phase="post-w", captured_at=fc.utc_now()))


def cmd_capture(args):
    if args.phase != "post-w" and not args.family:
        raise fc.Refusal("E_ARGS", field="family")
    if args.phase in ("pre-arm", "post-arm") and not args.arm:
        raise fc.Refusal("E_ARGS", field="arm")
    if fc.inside_git_work_tree(args.out_dir):
        raise fc.Refusal("E_PATH", reason="work_tree")
    spec, _ = load_spec(args.spec)
    bindings = load_bindings(args.bindings)
    if args.phase in ("w-open", "w-close"):
        capture_pages(args, spec)
    elif args.phase in ("pre-arm", "post-arm"):
        capture_arm(args, spec, bindings)
    else:
        capture_after_window(args, spec, bindings)
    return 0


# ---- identity (R19) ---------------------------------------------------------------------------------------------

def cmd_identity(args):
    refuse_output(args.out)
    spec, _ = load_spec(args.spec)
    bindings = load_bindings(args.bindings)
    launches = load_json(args.launch_records, "launch_records", "E_IDENTITY_SOURCE")
    codex = load_json(args.codex_rows, "codex_rows", "E_IDENTITY_SOURCE") if args.codex_rows else None
    table, counts = ev.build_identity_table(spec, bindings, os.environ.get("RUN_TOKEN", ""), launches, codex)
    try:
        validator = ev.validator_state(ev.bridge({"op": "validate_identity", "table": table, "options": {}}))
    except fc.Refusal as stop:
        if stop.code == "E_IDENTITY_INVALID":
            raise
        validator = "unchecked"
    fc.private_create(args.out, fc.canonical(table))
    by_actor = {}
    for row in table["rows"]:
        by_actor[row["actor"]] = by_actor.get(row["actor"], 0) + 1
    print(json.dumps(dict(counts, rows=len(table["rows"]), by_actor=dict(sorted(by_actor.items())), u4_validator=validator),
                     sort_keys=True))
    return 0


# ---- grade and regrade (R3-R6, R14-R18, R22) --------------------------------------------------------------------

PRIVATE_FILES = ("spec.json", "keys.json", "bindings.json", "identity-table.json", "captures.json", "judgments.jsonl")
CONTEXT_SCHEMA = "token-e2e-grade-context/1"


def make_private_dir(path):
    issue = fc.private_path_issue(path)
    if issue:
        raise fc.Refusal("E_PATH", reason=issue)
    try:
        os.mkdir(path, 0o700)
    except OSError:
        raise fc.Refusal("E_PATH", reason="unwritable") from None


def _pairs(items, allowed, flag):
    found = {}
    for item in items:
        name, sep, path = item.partition("=")
        if not sep or name not in allowed or name in found:
            raise fc.Refusal("E_ARGS", field=flag)
        found[name] = path
    return found


def _read_lines(path, field):
    rows, errors = ev.read_jsonl(path)
    if rows is None or errors:
        raise fc.Refusal("E_ARGS", field=field)
    return rows


def _load_captures(directory):
    captures = {}
    if directory:
        for name in sorted(os.listdir(directory)):
            if name.endswith(".json"):
                document = ev.read_json(os.path.join(directory, name))
                if isinstance(document, dict):
                    captures[name] = document
    return captures


def _load_judgments(rows):
    """{(identity, actor, run_index): judgment}, and the route summaries under the reserved key ("route", name, 0)."""
    loaded = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        if item.get("kind") == "route" and isinstance(item.get("route"), str):
            loaded[("route", item["route"], 0)] = item
        elif "identity" in item and "actor" in item:
            loaded[(item["identity"], item["actor"], item.get("run_index", 0))] = item
    return loaded


def _read_judgment_rows(path, field):
    """A judgments file (JSONL), or a judge directory: every judgments-*.jsonl in it, in name order."""
    if os.path.isdir(path):
        rows = []
        for name in sorted(os.listdir(path)):
            if name.startswith("judgments-") and name.endswith(".jsonl"):
                rows.extend(_read_lines(os.path.join(path, name), field))
        return rows
    return _read_lines(path, field)


def _jsonl(rows):
    return "".join(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for row in rows).encode("utf-8")


# Flags whose value is a private path: the recorded command keeps the flag and a placeholder (R22, U9-D17).
PATH_FLAGS = {"--spec": "spec", "--repo": "exec-checkout", "--bindings": "run-bindings", "--identity-table": "identity-table",
              "--keys": "keys", "--captures": "captures-dir", "--join-ledger": "join-ledger",
              "--adoption-report": "adoption-report", "--run-mode": "run-mode", "--call-ledger": "call-ledger",
              "--codex-events-dir": "codex-events-dir", "--codex-driver": "codex-driver", "--judgments": "judgments",
              "--out-private": "private-dir", "--out": "aggregate", "--from": "private-dir", "--controls": "controls-report"}


def _placeholder(value, name):
    head, sep, _ = value.partition("=")
    return f"{head}=<{name}>" if sep and "/" not in head else f"<{name}>"


def sanitize_argv(argv):
    """The command as a manifest may record it: `python3 tools/token-e2e/grade.py`, the subcommand, every flag, and a
    placeholder for each private path (`FAMILY=FILE` values keep their family), never a path or a name of this host. A flag
    is read in both spellings argparse accepts, `--flag value` and `--flag=value` (abbreviations are refused by the parser)."""
    tokens, clean, index = [str(item) for item in argv], ["python3", "tools/token-e2e/grade.py"], 0
    while index < len(tokens):
        token = tokens[index]
        flag, equals, inline = token.partition("=") if token.startswith("--") else (token, "", "")
        name = PATH_FLAGS.get(flag)
        if name and equals:
            clean.append(f"{flag}={_placeholder(inline, name)}")
            index += 1
            continue
        clean.append(token)
        if name and index + 1 < len(tokens):
            clean.append(_placeholder(tokens[index + 1], name))
            index += 2
            continue
        index += 1
    return clean


def argv_issue(argv):
    """Why a recorded command may not enter a manifest, else None: it is not a list of strings, or an element after the script
    path has a path shape ('/', '\\', a home shorthand or a drive prefix). A recorded command holds flags and placeholders
    only, so this is the fail-closed backstop behind `sanitize_argv` for a context.json written by any other means."""
    if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
        return "argv"
    for item in argv[2:]:
        if "/" in item or "\\" in item or item.startswith("~") or ev.has_drive_prefix(item):
            return "argv"
    return None


def _finish(spec, keys, bindings, table, records, captures, judgments, meta, out_private, out, copies, join=None,
            controls=None, command=None):
    """Evaluate, run the canary, then write; nothing is written when a check refuses (R22)."""
    rows, aggregate = ev.evaluate(spec, keys, bindings, records, captures, judgments, meta=meta, join=join, controls=controls)
    aggregate["privacy"]["canary_values_checked"] = ev.assert_no_private(aggregate, ev.canary_values(bindings, table, records))
    make_private_dir(out_private)
    files = dict(copies)
    files["grades.jsonl"] = _jsonl(rows)
    files["evidence.jsonl"] = _jsonl(records)
    files["context.json"] = fc.canonical({"schema": CONTEXT_SCHEMA, "meta": meta, "command": command or sanitize_argv(["grade"]),
                                          "files": {name: fc.sha256_hex(data) for name, data in sorted(copies.items())}})
    for name in sorted(files):
        fc.private_create(os.path.join(out_private, name), files[name])
    fc.private_create(out, fc.canonical(aggregate))
    summary = ev.exit_status(aggregate)
    print(json.dumps({"g_q": aggregate["g_q"]["status"], "m7": aggregate["m7"]["status"],
                      "m8": {lane: item["status"] for lane, item in sorted(aggregate["m8"].items())},
                      "m12": aggregate["m12"]["status"], "exit": summary}, sort_keys=True))
    return summary


def cmd_grade(args):
    if not spec_matches(args.spec, args.repo):
        raise fc.Refusal("E_SPEC_MISMATCH")
    for flag in ("bindings", "identity_table", "keys", "out_private", "out"):
        if getattr(args, flag) is None:
            raise fc.Refusal("E_ARGS", field=flag)
    refuse_output(args.out)
    refuse_output(args.out_private)
    spec, spec_data = load_spec(args.spec)
    bindings = load_bindings(args.bindings)
    bindings_data = read_file(args.bindings, "schema")
    keys = load_json(args.keys, "keys", "E_KEYS_MISMATCH")
    keys_data = read_file(args.keys, "keys", "E_KEYS_MISMATCH")
    if keys.get("spec_sha256") != fc.sha256_hex(spec_data) or keys.get("bindings_sha256") != fc.sha256_hex(bindings_data):
        raise fc.Refusal("E_KEYS_MISMATCH")
    table_data = read_file(args.identity_table, "identity_table", "E_ARGS")
    table = load_json(args.identity_table, "identity_table", "E_ARGS")
    joins, join_rows = {}, {}
    for family, path in _pairs(args.join_ledger, ("claude", "codex"), "join_ledger").items():
        join_rows[family] = [row for row in _read_lines(path, "join_ledger") if isinstance(row, dict)]
        joins[family] = {(row["identity"], row["actor"]): row for row in join_rows[family]
                         if row.get("identity") and "actor" in row}
    run_mode = {}
    for arm, path in _pairs(args.run_mode, CLAUDE_ARMS, "run_mode").items():
        document = load_json(path, "run_mode", "E_ARGS")
        run_mode[arm] = document.get("children") if isinstance(document.get("children"), list) else []
    ledger = []
    for path in args.call_ledger:
        ledger.extend(_read_lines(path, "call_ledger"))
    captures = _load_captures(args.captures)
    sources = {"join": joins, "run_mode": run_mode, "call_ledger": ledger, "events_dir": args.codex_events_dir,
               "driver_dir": args.codex_driver}
    judgment_rows = _read_judgment_rows(args.judgments, "judgments") if args.judgments else []
    controls, controls_copy = None, None
    if args.controls:
        report = load_json(args.controls, "controls", "E_ARGS")
        controls, controls_copy = {"run": True, "classes": report}, fc.canonical(report)
    records = ev.collect(spec, bindings, keys, table, sources, captures)
    reports = {}
    for family, path in _pairs(args.adoption_report, ("claude", "codex"), "adoption_report").items():
        reports[family] = load_json(path, "adoption_report", "E_ARGS")
    if "claude" in reports and isinstance(reports["claude"].get("m12_inputs"), dict):
        ev.m12_cross_check(ev.m12_sums(records), reports["claude"]["m12_inputs"])
    meta = {"spec_sha256": fc.sha256_hex(spec_data), "bindings_sha256": fc.sha256_hex(bindings_data),
            "keys_sha256": fc.sha256_hex(keys_data)}
    copies = {"spec.json": spec_data, "keys.json": keys_data, "bindings.json": bindings_data,
              "identity-table.json": table_data, "captures.json": fc.canonical(captures),
              "judgments.jsonl": _jsonl(judgment_rows)}
    for family, rows in sorted(join_rows.items()):  # M8's opportunities follow these rows, so regrade needs them
        copies[f"join-{family}.jsonl"] = _jsonl(rows)
    if controls_copy is not None:
        copies["controls.json"] = controls_copy
    return _finish(spec, keys, bindings, table, records, captures, _load_judgments(judgment_rows), meta, args.out_private,
                   args.out, copies, join_rows or None, controls, sanitize_argv(args.raw_argv))


def cmd_regrade(args):
    refuse_output(args.out)
    refuse_output(args.out_private)
    source = args.source
    context = load_json(os.path.join(source, "context.json"), "context", "E_REGRADE")
    if context.get("schema") != CONTEXT_SCHEMA:
        raise fc.Refusal("E_REGRADE", field="schema")
    copies = {}
    for name in PRIVATE_FILES:
        copies[name] = read_file(os.path.join(source, name), name, "E_REGRADE")
        if fc.sha256_hex(copies[name]) != (context.get("files") or {}).get(name):
            raise fc.Refusal("E_REGRADE", field="digest")
    join = {}
    for family in ("claude", "codex"):
        name = f"join-{family}.jsonl"
        if name in (context.get("files") or {}):
            copies[name] = read_file(os.path.join(source, name), name, "E_REGRADE")
            if fc.sha256_hex(copies[name]) != context["files"][name]:
                raise fc.Refusal("E_REGRADE", field="digest")
            join[family] = [json.loads(line) for line in copies[name].decode("utf-8").split("\n") if line.strip()]
    controls = None
    if "controls.json" in (context.get("files") or {}):
        copies["controls.json"] = read_file(os.path.join(source, "controls.json"), "controls.json", "E_REGRADE")
        if fc.sha256_hex(copies["controls.json"]) != context["files"]["controls.json"]:
            raise fc.Refusal("E_REGRADE", field="digest")
        controls = {"run": True, "classes": json.loads(copies["controls.json"].decode("utf-8"))}
    spec, keys, bindings = (json.loads(copies[name].decode("utf-8")) for name in ("spec.json", "keys.json", "bindings.json"))
    table = json.loads(copies["identity-table.json"].decode("utf-8"))
    captures = json.loads(copies["captures.json"].decode("utf-8"))
    records, errors = ev.read_jsonl(os.path.join(source, "evidence.jsonl"))
    if records is None or errors:
        raise fc.Refusal("E_REGRADE", field="evidence")
    if args.judgments:
        judgment_rows = _read_judgment_rows(args.judgments, "judgments")
        copies["judgments.jsonl"] = _jsonl(judgment_rows)
    else:
        judgment_rows, _ = ev.read_jsonl(os.path.join(source, "judgments.jsonl"))
    return _finish(spec, keys, bindings, table, records, captures, _load_judgments(judgment_rows or []), context["meta"],
                   args.out_private, args.out, copies, join or None, controls, sanitize_argv(args.raw_argv))


# ---- judge (R21) -------------------------------------------------------------------------------------------------------

def cmd_judge(args):
    services = argparse.Namespace(context_schema=CONTEXT_SCHEMA, refuse_output=refuse_output, spec_matches=spec_matches)
    return jd.run_command(args, services)


# ---- controls (e5) -----------------------------------------------------------------------------------------------------

E1_REV = "f5812d3f"  # the E1 receipt's catalog revision: the pinned keys its historical answers are graded at
E1_RECEIPT = "evidence/artifacts/token-e2e-ultracode-20260925/receipt.json"


def e1_controls(repo, readings):
    """The two committed E1 answers that must fail at their pinned keys: the repomix 47-name list (T8: names missing) and
    the qmd wrong-document answer (T4: the required document is not cited)."""
    met = 0
    try:
        tools = {item.get("tool"): item for item in json.loads(fc.GitSources(repo, "HEAD").read(E1_RECEIPT).decode("utf-8"))["tools"]}
        key = fc.key_T8(fc.GitSources(repo, E1_REV), {})
        result = fc.ORACLES["T8"]({}, key, fc.Answer(tools["repomix"]["answer_excerpt"], ()), readings, {})["A"]
        met += 1 if result.status == "fail" and "names_missing" in result.reasons else 0
        result = fc.ORACLES["T4"]({}, {}, fc.Answer(tools["qmd"]["answer_excerpt"], ()), readings, {})["A"]
        met += 1 if result.status == "fail" and result.reasons == ("citation_missing",) else 0
    except (AttributeError, KeyError, TypeError, ValueError, fc.KeyUnavailable, fc.Refusal):
        pass
    return {"expected": 2, "observed": met}


def calibration_controls(block):
    """Class D, structurally: every calibration file loads against the registry and meets the grading block's minimums (no
    model is called here; the routes run these controls blind at grading time)."""
    minimum = block["judges"]["calibration"]
    templates = jd.calibrated_templates()
    good = 0
    for template in templates:
        try:
            calibration = jd.load_calibration(template)
        except fc.Refusal:
            continue
        kinds = {kind: sum(1 for item in calibration["controls"] if item["kind"] == kind)
                 for kind in ("reference", "paraphrased", "wrong")}
        if calibration["clauses"]:
            wrong_fail = all(False in item["expected"].values() for item in calibration["controls"] if item["kind"] == "wrong")
            good += 1 if (kinds["reference"] >= minimum["correct"] and kinds["paraphrased"] >= minimum["paraphrased"]
                          and kinds["wrong"] >= minimum["wrong"] and wrong_fail) else 0
        else:
            good += 1 if len(calibration.get("extraction_controls") or []) >= 2 else 0
    return {"expected": len(templates), "observed": good}


def cmd_controls(args):
    """Planted class A, B and C controls, the E1 historical answers and the calibration files, as counts only: exit 0 when every
    class landed where it was planted, 1 otherwise, and no answer, key or path is ever printed."""
    if args.out:
        refuse_output(args.out)
    spec, _ = load_spec(args.spec)
    catalog = load_json(str(jd.CALIBRATION_DIR / "oracle-controls.json"), "catalog", "E_CONTROLS")
    if catalog.get("schema") != "token-e2e-oracle-controls/1" or not isinstance(catalog.get("controls"), list):
        raise fc.Refusal("E_CONTROLS", field="catalog")
    readings = spec["readings"]
    counts, _ = ev.run_controls(catalog, readings)
    for name in ("A", "B", "C"):
        counts.setdefault(name, {"expected": 0, "observed": 0})
    counts["D"] = calibration_controls(spec["block"])
    counts["E1"] = e1_controls(args.repo, readings)
    if args.out:
        fc.private_create(args.out, fc.canonical(counts))
    print(json.dumps(counts, sort_keys=True))
    return 0 if all(item["expected"] == item["observed"] for item in counts.values()) else 1


# ---- differential (e6): agreement with the retained checks of the earlier runs ---------------------------------------------

DIFFERENTIAL_RUNS = ("rtk-296", "rtk-343")


def _base_sections(text):
    """(git log text, unittest text) of a retained baseline: the six marked sections of rtk-296, or the raw concatenation of
    rtk-343 (its git log leads and its unittest summary closes the file)."""
    marked = {}
    for part in ("\n" + text).split("\n=== [")[1:]:
        number, _, rest = part.partition("] ")
        marked[number] = rest.partition(" ===\n")[2]
    if "1" in marked and "6" in marked:
        return marked["1"], marked["6"]
    return text, text


def _t0_from_base(text):
    log, unit = _base_sections(text)
    facts = fc.parse_unittest_facts(unit)
    return {"subjects": fc.parse_git_log_subjects(log) or ["<none>"], "ran": facts["ran"], "status": facts["status"],
            "skipped": facts["skipped"]}


def _base_answer(text):
    """The answer a correct child gives for the baseline `text`: the newest subject and the unittest result."""
    spec = _t0_from_base(text)
    result = spec["status"] + (f" (skipped={spec['skipped']})" if spec["skipped"] else "")
    return f"Newest commit: {spec['subjects'][0]}\nUnittest: {result}; {spec['ran']} tests ran."


def _mutations(text):
    """The baseline unchanged, then three mutations the retained checks must reject: the newest subject, the test count and
    the result line."""
    spec = _t0_from_base(text)
    yield "original", text
    yield "subject", text.replace(spec["subjects"][0], "Unrelated subject text", 1)
    yield "count", text.replace(f"Ran {spec['ran']} test", f"Ran {spec['ran'] + 1} test", 1)
    lines = text.split("\n")
    for number in range(len(lines) - 1, -1, -1):
        stripped = lines[number].strip()
        if stripped == "OK" or stripped.startswith(("OK (", "FAILED")):
            lines[number] = "FAILED (failures=1)"
            break
    yield "result", "\n".join(lines)


def _retained_verdict(run_dir, base_text):
    """PASS or FAIL as the retained check.py says for `base_text`, run from a temporary copy (the inputs are never touched;
    rtk-296's check reads a hard-coded BASE path, which the copy points at its own base.txt)."""
    with tempfile.TemporaryDirectory(prefix="u9-diff-") as scratch:
        for name in os.listdir(run_dir):
            source = os.path.join(run_dir, name)
            if os.path.isfile(source) and name not in ("base.txt", "check.py"):
                shutil.copy(source, os.path.join(scratch, name))
        with open(os.path.join(scratch, "base.txt"), "w", encoding="utf-8") as stream:
            stream.write(base_text)
        code = read_file(os.path.join(run_dir, "check.py"), "inputs", "E_DIFFERENTIAL").decode("utf-8", errors="replace")
        lines = [f'BASE = "{os.path.join(scratch, "base.txt")}"' if line.startswith("BASE = ") else line for line in code.split("\n")]
        with open(os.path.join(scratch, "check.py"), "w", encoding="utf-8") as stream:
            stream.write("\n".join(lines))
        try:
            done = subprocess.run([sys.executable, "-B", "check.py"], cwd=scratch, env=fc.minimal_env(scratch),
                                  capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
        except (OSError, subprocess.TimeoutExpired):
            return "FAIL"
        return "PASS" if done.stdout.strip().startswith("PASS") else "FAIL"


def _grader_verdict(text, answer):
    spec = _t0_from_base(text)
    capture = ev._t0_capture(spec)
    ctx = {"captures": {"pre": {"arm": capture, "plain": capture}, "post": {"arm": capture, "plain": capture}}}
    parts = fc.ORACLES["T0"]({}, {}, fc.Answer(answer, ()), {}, ctx)
    return "PASS" if all(part.status == "pass" for part in parts.values()) else "FAIL"


def cmd_differential(args):
    """Agreement of this grader's T0 oracle with the retained check.py of each earlier run on the original baseline and on
    three mutations of it: counts only, so nothing of the private inputs is printed."""
    reports, agree_all = [], True
    for name in DIFFERENTIAL_RUNS:
        run_dir = os.path.join(args.inputs, name)
        if not os.path.isfile(os.path.join(run_dir, "base.txt")) or not os.path.isfile(os.path.join(run_dir, "check.py")):
            raise fc.Refusal("E_DIFFERENTIAL", field="inputs")
        base = read_file(os.path.join(run_dir, "base.txt"), "inputs", "E_DIFFERENTIAL").decode("utf-8", errors="replace")
        answer_path = os.path.join(run_dir, "answer.json")
        answer = None
        if os.path.isfile(answer_path):
            document = ev.read_json(answer_path)
            answer = document.get("answer") if isinstance(document, dict) else None
        answer = answer if isinstance(answer, str) else _base_answer(base)
        agree = total = 0
        for _, text in _mutations(base):
            total += 1
            agree += 1 if _retained_verdict(run_dir, text) == _grader_verdict(text, answer) else 0
        agree_all = agree_all and agree == total
        reports.append(f"{name} agree {agree}/{total}")
    print("; ".join(reports))
    return 0 if agree_all else 1


# ---- export and check-html (R22, U9-D17) ----------------------------------------------------------------------------------

MANIFEST_BOUNDARY = ("local integration grading of retained run evidence; not upstream acceptance; judge calls are separate "
                     "model runs counted in judges")
MANIFEST_SCOPE = "frozen-check grading of one run of the #381 token E2E"


def _private_inputs(private, code):
    bindings = ev.read_json(os.path.join(private, "bindings.json"))
    table = ev.read_json(os.path.join(private, "identity-table.json"))
    records, errors = ev.read_jsonl(os.path.join(private, "evidence.jsonl"))
    if not isinstance(bindings, dict) or not isinstance(table, dict) or records is None or errors:
        raise fc.Refusal(code, reason="private")
    return bindings, table, records


def export_dir_issue(path, values):
    """Why an export directory cannot be used: it lies inside a work tree, exists already, or its own path names a run value,
    the home directory or the user name (the token-report importer would carry that path into the manifest)."""
    if fc.inside_git_work_tree(path):
        return "work_tree"
    if fc.path_exists(path):
        return "exists"
    spelled = "\0".join({os.path.abspath(path), os.path.realpath(path)})
    if any(value in spelled for value in values if isinstance(value, str) and len(value) >= 8):
        return "canary"
    return None


def cmd_export(args):
    """One returned_results record whose attachment is the ID-free aggregate, in a fresh neutral directory. The canary runs
    over the aggregate and over the whole manifest before anything is written; the recorded command holds placeholders."""
    context = ev.read_json(os.path.join(args.private, "context.json"))
    if not isinstance(context, dict) or context.get("schema") != CONTEXT_SCHEMA:
        raise fc.Refusal("E_EXPORT_INPUT", reason="private")
    command = context.get("command") or sanitize_argv(["grade"])
    if argv_issue(command):
        raise fc.Refusal("E_EXPORT_INPUT", reason="argv")
    bindings, table, records = _private_inputs(args.private, "E_EXPORT_INPUT")
    data = read_file(args.aggregate, "aggregate", "E_EXPORT_INPUT")
    try:
        aggregate = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise fc.Refusal("E_EXPORT_INPUT", reason="aggregate") from None
    if not isinstance(aggregate, dict) or aggregate.get("schema") != ev.GRADES_SCHEMA:
        raise fc.Refusal("E_EXPORT_INPUT", reason="aggregate")
    values = ev.canary_values(bindings, table, records)
    issue = export_dir_issue(args.export_dir, values)
    if issue:
        raise fc.Refusal("E_EXPORT_DIR", reason=issue)
    ev.assert_no_private(aggregate, values)
    judges = aggregate.get("judges") or {}
    status = "pending" if judges.get("pending") else ("pass" if ev.exit_status(aggregate) == 0 else "fail")
    stamp = fc.utc_now()
    record = {"id": "token-e2e-frozen-check-grades", "runtime": "python3", "kind": "frozen_check_grading", "status": status,
              "boundary": MANIFEST_BOUNDARY, "component_ids": [],
              "command": {"argv": list(command)},
              "started_at": None, "completed_at": stamp,
              "observation": {"g_q": aggregate["g_q"]["status"], "m7": aggregate["m7"]["status"],
                              "m8": {lane: item["status"] for lane, item in sorted(aggregate["m8"].items())},
                              "m12": aggregate["m12"]["status"]},
              "attachments": [{"label": "grades-aggregate", "path": "grades-aggregate.json", "bytes": len(data),
                               "sha256": fc.sha256_hex(data), "mime_type": "application/json"}]}
    manifest = {"schema_version": 1, "captured_at": stamp, "scope": MANIFEST_SCOPE, "records": [record]}
    ev.assert_no_private(manifest, values)
    try:
        os.makedirs(args.export_dir, mode=0o700)
    except OSError:
        raise fc.Refusal("E_EXPORT_DIR", reason="exists") from None
    fc.private_create(os.path.join(args.export_dir, "grades-aggregate.json"), data)
    fc.private_create(os.path.join(args.export_dir, "returned-results.json"),
                      (json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"attachments": 1, "records": 1}, sort_keys=True))
    return 0


def html_values(private_dir):
    """The run-specific canary values a grade run's private directory names; none without one."""
    if not private_dir:
        return []
    bindings, table, records = _private_inputs(private_dir, "E_CHECK_HTML")
    return ev.canary_values(bindings, table, records)


def cmd_check_html(args):
    """The privacy canary over a generated HTML report: gathered run values (with --from), the home directory and user name,
    UUIDs, tool_use and call ids and the project-slug shape of a home path. A leading '/' is not one: URLs and tags carry it."""
    text = read_file(args.html, "html", "E_ARGS").decode("utf-8", errors="replace")
    home = os.path.expanduser("~")
    values = sorted({value for value in list(html_values(args.private_dir)) + [home, os.path.basename(home.rstrip("/")),
                                                                                os.environ.get("USER", "")]
                     if isinstance(value, str) and len(value) >= 8})
    if any(value in text for value in values) or ev.id_shape(text):
        raise fc.Refusal("E_PRIVACY")
    print(json.dumps({"canary_values_checked": len(values)}, sort_keys=True))
    return 0


HANDLERS = {"spec": cmd_spec, "bind": cmd_bind, "keys": cmd_keys, "capture": cmd_capture, "grade": cmd_grade,
            "identity": cmd_identity, "regrade": cmd_regrade, "judge": cmd_judge, "controls": cmd_controls,
            "differential": cmd_differential, "export": cmd_export, "check-html": cmd_check_html}


def main(argv=None):
    command = "usage"
    try:
        raw = [str(item) for item in (sys.argv[1:] if argv is None else argv)]
        args = build_parser().parse_args(raw)
        args.raw_argv = raw
        command = args.command
        return HANDLERS[command](args) or 0
    except fc.Refusal as stop:
        sys.stderr.write(str(stop) + "\n")
        return 2
    except Exception:  # noqa: BLE001 - a crash is a refusal (exit 2), never "graded and not passing" (exit 1)
        sys.stderr.write(f"E_INTERNAL stage={command}\n")
        if os.environ.get("GRADE_DEBUG") == "1":
            traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
