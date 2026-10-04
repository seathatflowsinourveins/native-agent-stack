#!/usr/bin/env python3
"""Discriminating controls for state and output checks of scripts/native_token_ci.py.

A local-integration driver written for this run record, not an upstream test: every check is
this repository's own assertion over pinned upstream output. It imports the harness from this
checkout, installs MCPorter, RTK, headroom-ai[mcp], jcodemunch-mcp, ccusage and MarkItDown once
with the harness's own --install methods and pins, then runs the harness's own fixture functions
once per arm, each arm with its own owned work directory and report:

- "as-harness": the fixture exactly as the harness runs it; every check must pass.
- a control: one setting or input that a check depends on is changed, and exactly that check
  must fail (for the empty usage directory and the failing RTK inline test, the tool's own
  command fails first).

Every run, the installation included, gets a HOME inside its own work directory, never the
caller's: a control that removes a tool's state setting (HEADROOM_WORKSPACE_DIR, for example)
makes that tool fall back to its default under HOME, and the driver observes and removes that
owned directory with the rest of its temporary directory.

codebase-memory-mcp has no arm: its fixture needs a short TMPDIR for its rendezvous socket.

Usage: controls_driver.py --output NEW_DIRECTORY
Writes NEW_DIRECTORY/controls.json; exits 1 unless every arm ends as expected.
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location("native_token_ci", ROOT / "scripts/native_token_ci.py")
ci = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ci)

USAGE_LOG = "fixtures/ccusage-synthetic-claude/projects/native-ci-synthetic-project/synthetic-session.jsonl"
FIXTURES = {"rtk": ci.rtk_fixture, "headroom": ci.headroom_fixture, "jcodemunch-mcp": ci.jcodemunch_mcp_fixture,
            "ccusage": ci.ccusage_fixture, "markitdown": ci.markitdown_fixture}


def owned_run(output: Path, work: Path) -> ci.Run:
    """A harness Run whose HOME is a new directory inside its own work directory."""
    run = ci.Run(output, work)
    home = work / "home"
    home.mkdir(mode=0o700)
    run.env["HOME"] = str(home)
    run.report["native_home_preserved"] = False
    run.report["driver_home"] = run.clean(str(home))
    run.flush()
    return run


def replace_once(text: str, old: str, new: str) -> str:
    ci.require(text.count(old) == 1, f"control input must contain {old!r} exactly once")
    return text.replace(old, new)


def without_server_setting(key: str):
    """mcporter_stdio_call with `key` neither passed by --env nor present in MCPorter's own
    environment, so the MCP server falls back to its default location."""
    original = ci.mcporter_stdio_call

    def call(run, label, server, name, tool, args, env_keys, timeout_ms, timeout=90, extra_env=None):
        saved = run.env.pop(key)
        try:
            return original(run, label, server, name, tool, args,
                            tuple(item for item in env_keys if item != key), timeout_ms,
                            timeout=timeout, extra_env=extra_env)
        finally:
            run.env[key] = saved
    return lambda _run: patch.object(ci, "mcporter_stdio_call", call)


# A project filter whose one inline test expects the wrong output: the filter strips the "noise"
# line that the test expects to survive. RTK's own built-in filters and tests are unchanged.
RTK_FAILING_FILTER = r"""schema_version = 1

[filters.native-ci-control]
description = "Controls driver only: a project filter whose one inline test expects the wrong output"
match_command = "^native-ci-control\\b"
strip_lines_matching = ["^noise"]

[[tests.native-ci-control]]
name = "expects the stripped noise line to survive"
input = "noise line\nkept line\n"
expected = "noise line\nkept line"
"""


def rtk_failing_inline_test(run):
    """Just before `rtk verify`, the fixture repository gets .rtk/filters.toml with RTK_FAILING_FILTER,
    trusted through RTK's CI override (RTK_TRUST_PROJECT_FILTERS=1 while CI is set; src/hooks/trust.rs)."""
    original = run.command

    def command(name, argv, *args, **kwargs):
        if name == "rtk-verify-inline-filter-tests":
            cwd = Path(args[0] if args else kwargs["cwd"])
            (cwd / ".rtk").mkdir()
            (cwd / ".rtk/filters.toml").write_text(RTK_FAILING_FILTER)
            run.env["RTK_TRUST_PROJECT_FILTERS"] = "1"
            run.report["environment"]["RTK_TRUST_PROJECT_FILTERS"] = "1"
        return original(name, argv, *args, **kwargs)
    return patch.object(run, "command", command)


# Loaded by the Headroom MCP server's Python from PYTHONPATH in one control only. headroom/compress.py
# documents compress()'s `optimize` flag as "Whether to actually compress (False = passthrough for
# A/B testing)"; the server imports compress from headroom.compress for every call.
PASSTHROUGH_SITECUSTOMIZE = """\
import functools
import importlib
import os
import pathlib

_module = importlib.import_module("headroom.compress")
_module.compress = functools.partial(_module.compress, optimize=False)
pathlib.Path(os.environ["NATIVE_CI_PASSTHROUGH_MARKER"]).write_text("compress(optimize=False) installed\\n")
"""


def headroom_compression_disabled():
    """Every Headroom MCP server of the arm starts with Headroom's own compress() passthrough; the
    input, server command and call are unchanged."""
    original = ci.mcporter_stdio_call

    def apply(run):
        site = run.work / "headroom-passthrough-site"
        site.mkdir()
        (site / "sitecustomize.py").write_text(PASSTHROUGH_SITECUSTOMIZE)
        run.report["control"]["passthrough_marker"] = run.clean(str(run.work / "passthrough-loaded"))

        def call(run_, label, server, name, tool, args, env_keys, timeout_ms, timeout=90, extra_env=None):
            injected = {"PYTHONPATH": str(site), "NATIVE_CI_PASSTHROUGH_MARKER": str(run.work / "passthrough-loaded")}
            return original(run_, label, server, name, tool, args, env_keys, timeout_ms, timeout=timeout,
                            extra_env={**(extra_env or {}), **injected})
        return patch.object(ci, "mcporter_stdio_call", call)
    return apply


def usage_log(edit: tuple[str, str] | None):
    """Point ccusage at a copy of the committed synthetic log with one value edited, or, with
    no edit, at an empty directory."""
    def apply(run):
        config = run.work / ("claude-config-control" if edit else "empty-claude-config")
        config.mkdir()
        if edit:
            target = config / USAGE_LOG.split("ccusage-synthetic-claude/", 1)[1]
            target.parent.mkdir(parents=True)
            target.write_text(replace_once((ROOT / USAGE_LOG).read_text(), *edit))
        run.env["CLAUDE_CONFIG_DIR"] = str(config)
        run.report["environment"]["CLAUDE_CONFIG_DIR"] = run.clean(str(config))
        return nullcontext()
    return apply


def markitdown_input(label: str, make_copy):
    """Give one MarkItDown command a changed copy of its input file instead of the original."""
    def apply(run):
        original = run.command

        def command(name, argv, *args, **kwargs):
            if name == label:
                argv = [argv[0], str(make_copy(run, Path(argv[1]))), *argv[2:]]
            return original(name, argv, *args, **kwargs)
        return patch.object(run, "command", command)
    return apply


def heading_as_paragraph(run, source: Path) -> Path:
    copy = run.work / "greeting-heading-as-paragraph.html"
    copy.write_text(replace_once(source.read_text(), "<h1>Local browser command check</h1>",
                                 "<p>Local browser command check</p>"))
    return copy


def plain_text_as_csv(run, source: Path) -> Path:
    # MarkItDown 0.1.8's CsvConverter renders these same bytes as a Markdown table. (An .html
    # copy was tried first and did not discriminate: its HTML conversion kept this text.)
    copy = run.work / "markitdown-plain.csv"
    shutil.copyfile(source, copy)
    return copy


# (tool, arm, what the control changes, checks expected to fail, failure text expected, apply)
ARMS = (
    ("rtk", "as-harness", None, [], None, None),
    ("rtk", "control", "a project filter whose one inline test expects the wrong output, trusted with "
     "RTK_TRUST_PROJECT_FILTERS=1 under CI, added to the fixture repository just before rtk verify",
     [], "rtk-verify-inline-filter-tests: unexpected exit 1", rtk_failing_inline_test),
    ("headroom", "as-harness", None, [], None, None),
    ("headroom", "control", "HEADROOM_WORKSPACE_DIR removed from the MCP server's environment",
     ["headroom-compression-store-inside-run"], None, without_server_setting("HEADROOM_WORKSPACE_DIR")),
    ("headroom", "control", "compression disabled: Headroom's compress() made its documented optimize=False "
     "passthrough in the MCP server process", ["headroom-compress-json-records-saves-tokens"], None,
     headroom_compression_disabled()),
    ("jcodemunch-mcp", "as-harness", None, [], None, None),
    ("jcodemunch-mcp", "control", "CODE_INDEX_PATH removed from the MCP server's environment",
     ["jcodemunch-index-inside-run"], None, without_server_setting("CODE_INDEX_PATH")),
    ("ccusage", "as-harness", None, [], None, None),
    ("ccusage", "control", "CLAUDE_CONFIG_DIR is an empty directory",
     [], "ccusage-claude-daily-synthetic-fixture: unexpected exit", usage_log(None)),
    ("ccusage", "control", "first assistant record's output_tokens 300 -> 301 in a copy of the log",
     ["ccusage-synthetic-fixture-token-totals"], None, usage_log(('"output_tokens":300', '"output_tokens":301'))),
    ("ccusage", "control", "first assistant record's costUSD 0.0271 -> 0.0371 in a copy of the log",
     ["ccusage-synthetic-fixture-cost-total"], None, usage_log(('"costUSD":0.0271', '"costUSD":0.0371'))),
    ("markitdown", "as-harness", None, [], None, None),
    ("markitdown", "control", "the fixture's <h1> heading turned into a <p> paragraph in a copy",
     ["markitdown-html-heading-present"], None, markitdown_input("markitdown-html-fixture", heading_as_paragraph)),
    ("markitdown", "control", "the plain-text input given to MarkItDown as a .csv file",
     ["markitdown-txt-passthrough-unchanged"], None, markitdown_input("markitdown-txt-passthrough", plain_text_as_csv)),
)


def install_tools(setup: ci.Run) -> None:
    ci.ensure_mcporter(setup)
    for name in ("rtk", "headroom", "jcodemunch-mcp", "ccusage", "markitdown"):
        binary = setup.install(name)
        setup.tools[name] = binary
        version = setup.command(f"version-{name}", [binary, "--version"])
        ci.require(re.search(rf"(?<![\d.]){re.escape(ci.PINS[name])}(?![\d.])", version) is not None,
                   f"Installed {name} differs from its manifest pin")


def run_arm(run: ci.Run, tool: str, arm: str, change: str | None, expected_checks: list[str],
            expected_failure: str | None, apply) -> None:
    run.report["control"] = {"tool": tool, "arm": arm, "change": change,
                             "expected_failed_checks": expected_checks,
                             "expected_failure_text": expected_failure}
    home = Path(run.env["HOME"])
    ci.require(home.is_relative_to(run.work) and str(home) != os.environ.get("HOME"),
               "every arm must run with a HOME inside its own work directory")
    try:
        with (apply(run) if apply else nullcontext()):
            FIXTURES[tool](run)
    except Exception as error:
        run.report["failures"].append({"component": tool, "error": run.clean(str(error))})
    finally:
        # Whatever any tool of this arm wrote under its owned HOME.
        run.observe("driver-owned-home", home)
        if tool == "headroom":
            # Where Headroom's default workspace (~/.headroom) stands after this arm, in the owned HOME.
            run.observe("headroom-default-workspace-under-home", home / ".headroom")
            marker = run.work / "passthrough-loaded"
            run.report["control"]["passthrough_loaded"] = marker.is_file()
        if tool == "markitdown":
            # What MarkItDown wrote, before the owned work directory is removed.
            run.report["control"]["markitdown_outputs"] = {
                name: run.clean((run.work / name).read_text()) for name in
                ("greeting.md", "markitdown-plain-converted.txt") if (run.work / name).is_file()}
        if tool == "jcodemunch-mcp":
            run.observe("jcodemunch-mcp-server-home", run.work / "jcodemunch-mcp-home")
            # The pre-polish check passed whenever CODE_INDEX_PATH was not empty.
            run.report["control"]["pre_polish_index_check_would_pass"] = bool(
                run.report["state_observations"].get("jcodemunch-mcp-index"))
        failed = [check["label"] for check in run.report["checks"] if not check["passed"]]
        errors = [failure["error"] for failure in run.report["failures"]]
        if change is None:
            as_expected = not failed and not errors
        else:
            as_expected = (failed == expected_checks and len(errors) == 1
                           and (expected_failure in errors[0] if expected_failure else errors[0] == failed[0]))
        if tool == "headroom":
            # The passthrough must be in force exactly in the arm that asks for it.
            as_expected = as_expected and (run.report["control"]["passthrough_loaded"]
                                           == ("passthrough_marker" in run.report["control"]))
        run.report["control"]["as_expected"] = as_expected
        run.report["status"] = "passed" if not errors else "failed"
        run.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New result directory")
    output = parser.parse_args().output.expanduser().absolute()
    output.mkdir(parents=True, exist_ok=False)
    combined = {"schema_version": 1, "kind": "native_cli_e2e_controls", "evidence_class": "local_integration",
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "driver": "evidence/artifacts/native-token-ci-extension-20260926/controls_driver.py",
                "harness_sha256": ci.digest((ROOT / "scripts/native_token_ci.py").read_bytes()),
                "driver_sha256": ci.digest(Path(__file__).read_bytes()), "arms": []}
    with tempfile.TemporaryDirectory(prefix="native-token-ci-controls-") as directory:
        base = Path(directory)
        (base / "setup").mkdir()
        (output / "setup").mkdir()
        setup = owned_run(output / "setup", base / "setup")
        setup.fresh_install = True
        setup.report["installation"] = "fresh-upstream-prefix"
        try:
            install_tools(setup)
            setup.report["status"] = "passed"
        except Exception as error:
            setup.report["failures"].append({"component": "setup", "error": setup.clean(str(error))})
            setup.report["status"] = "failed"
        setup.flush()
        combined["setup"] = setup.report
        if setup.report["status"] == "passed":
            for number, (tool, arm, change, checks, failure, apply) in enumerate(ARMS, 1):
                name = f"{number:02d}-{tool}-{arm}"
                (output / name).mkdir()
                (base / name).mkdir()
                run = owned_run(output / name, base / name)
                run.tools.update(setup.tools)
                run.report["installation"] = "tools installed once by this driver's setup"
                run_arm(run, tool, arm, change, checks, failure, apply)
                combined["arms"].append(run.report)
        work = base
    combined["cleanup"] = {"owned_temporary_directory_absent": not work.exists()}
    combined["summary"] = [{"tool": report["control"]["tool"], "arm": report["control"]["arm"],
                            "change": report["control"]["change"], "status": report["status"],
                            "failed_checks": [check["label"] for check in report["checks"] if not check["passed"]],
                            "failures": report["failures"], "as_expected": report["control"]["as_expected"]}
                           for report in combined["arms"]]
    passed = (setup.report["status"] == "passed" and len(combined["arms"]) == len(ARMS)
              and all(row["as_expected"] for row in combined["summary"]))
    combined["status"] = "as_expected" if passed else "not_as_expected"
    text = json.dumps(combined, indent=2) + "\n"
    replacements = [(str(work), "<CONTROLS_WORK>"), (str(output), "<RESULTS>"), (str(ROOT), "<CHECKOUT>")]
    if os.environ.get("HOME"):
        replacements.append((os.environ["HOME"], "<NATIVE_HOME>"))
    for source, target in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        text = text.replace(source, target)
    (output / "controls.json").write_text(text)
    print(json.dumps({"status": combined["status"], "summary": combined["summary"]}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
