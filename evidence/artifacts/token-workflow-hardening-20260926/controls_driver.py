#!/usr/bin/env python3
"""Discriminating controls for the 2026-09-26 checks of scripts/native_token_ci.py.

A local-integration driver written for this run record, not an upstream test: every check is
this repository's own assertion over pinned upstream output. It imports the harness from this
checkout, installs RTK, MarkItDown, ast-grep, Repomix and TOON once with the harness's own
--install methods and pins, then runs the harness's own fixture functions once per arm, each
arm with its own owned work directory, HOME and report:

- "as-harness": the fixture exactly as the harness runs it; every check must pass.
- a control: one argument, setting or input that a check depends on is changed, and exactly
  that check must fail.

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

FIXTURES = {"rtk": ci.rtk_long_log_fixture, "markitdown": ci.markitdown_multi_element_fixture,
            "ast-grep": ci.ast_grep_shell_fixture, "repomix": ci.repomix_fixture, "toon": ci.toon_fixture}


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


def rewrite_argv(label: str, rewrite):
    """Change the argument vector of the one harness command called `label`."""
    def apply(run):
        original = run.command

        def command(name, argv, *args, **kwargs):
            if name == label:
                argv = rewrite(run, list(argv))
                run.report["control"]["rewritten_argv"] = [run.clean(arg) for arg in argv]
            return original(name, argv, *args, **kwargs)
        return patch.object(run, "command", command)
    return apply


def ledger_elsewhere(label: str):
    """Run the command called `label` with RTK_DB_PATH on another run-owned ledger file."""
    def apply(run):
        original = run.command

        def command(name, argv, *args, **kwargs):
            if name != label:
                return original(name, argv, *args, **kwargs)
            saved = run.env["RTK_DB_PATH"]
            run.env["RTK_DB_PATH"] = str(run.work / "other-ledger/history.db")
            (run.work / "other-ledger").mkdir()
            try:
                return original(name, argv, *args, **kwargs)
            finally:
                run.env["RTK_DB_PATH"] = saved
        return patch.object(run, "command", command)
    return apply


def proxy_instead_of_filter(run, argv):
    # [rtk, git, log, -12] -> [rtk, proxy, git, log, -12]: RTK's own passthrough of the same command.
    return [argv[0], "proxy", *argv[1:]]


def html_as_txt(run, argv):
    copy = run.work / "markitdown-multi-element.txt"
    shutil.copyfile(argv[1], copy)
    return [argv[0], str(copy), *argv[2:]]


def script_text_in_paragraph(run, argv):
    copy = run.work / "markitdown-multi-element-script-in-paragraph.html"
    copy.write_text(replace_once(Path(argv[1]).read_text(), "<blockquote>",
                                 '<p>var marker = "NativeCiScriptBody";</p>\n<blockquote>'))
    return [argv[0], str(copy), *argv[2:]]


def pattern_without_keyword(run, argv):
    index = argv.index(ci.AST_GREP_SHELL_PATTERN)
    return [*argv[:index], "subprocess.run($$$ARGS)", *argv[index + 1:]]


def without_compress(run, argv):
    ci.require(argv.count("--compress") == 1, "structure pack must pass --compress once")
    return [arg for arg in argv if arg != "--compress"]


def pipe_delimiter(run, argv):
    return [*argv, "--delimiter", "|"]


def with_count(run, argv):
    return [*argv, f"-{ci.RTK_LOG_COMMITS}"]


# (tool, arm, what the control changes, checks expected to fail, apply)
ARMS = (
    ("rtk", "as-harness", None, [], None),
    ("rtk", "control", "`rtk proxy git log -12`, RTK's own passthrough, in place of the filtered `rtk git log -12`",
     ["rtk-long-log-compacts-every-commit"], rewrite_argv("rtk-long-git-log", proxy_instead_of_filter)),
    ("rtk", "control", "the filtered `rtk git log -12` records into another run-owned ledger (RTK_DB_PATH)",
     ["rtk-long-log-ledger-records-the-filter-saving"], ledger_elsewhere("rtk-long-git-log")),
    ("rtk", "control", "the default-window call `rtk git log` given `-12`",
     ["rtk-long-log-default-window-ten-newest-commits"], rewrite_argv("rtk-long-default-git-log", with_count)),
    ("markitdown", "as-harness", None, [], None),
    ("markitdown", "control", "the same HTML bytes given to MarkItDown as a .txt file",
     ["markitdown-multi-element-structure-converted"], rewrite_argv("markitdown-multi-element-html", html_as_txt)),
    ("markitdown", "control", "the script's text copied into a paragraph in a copy of the input",
     ["markitdown-script-style-and-comment-text-dropped"],
     rewrite_argv("markitdown-multi-element-html", script_text_in_paragraph)),
    ("ast-grep", "as-harness", None, [], None),
    ("ast-grep", "control", "the pattern without its shell=True constraint: `subprocess.run($$$ARGS)`",
     ["ast-grep-shell-true-calls-match-across-lines"], rewrite_argv("ast-grep-shell-true-calls", pattern_without_keyword)),
    ("repomix", "as-harness", None, [], None),
    ("repomix", "control", "the structure pack run without --compress",
     ["repomix-compress-keeps-signatures-drops-bodies"], rewrite_argv("repomix-selected-structure", without_compress)),
    ("toon", "as-harness", None, [], None),
    ("toon", "control", "the records encoded with `--delimiter |`",
     ["toon-tabular-encoding-smaller-than-json"], rewrite_argv("toon-encode-statistics", pipe_delimiter)),
)


def install_tools(setup: ci.Run) -> None:
    for name in FIXTURES:
        binary = setup.install(name)
        setup.tools[name] = binary
        version = setup.command(f"version-{name}", [binary, "--version"])
        ci.require(re.search(rf"(?<![\d.]){re.escape(ci.PINS[name])}(?![\d.])", version) is not None,
                   f"Installed {name} differs from its manifest pin")


def run_arm(run: ci.Run, tool: str, arm: str, change: str | None, expected_checks: list[str], apply) -> None:
    run.report["control"] = {"tool": tool, "arm": arm, "change": change, "expected_failed_checks": expected_checks}
    home = Path(run.env["HOME"])
    ci.require(home.is_relative_to(run.work) and str(home) != os.environ.get("HOME"),
               "every arm must run with a HOME inside its own work directory")
    try:
        with (apply(run) if apply else nullcontext()):
            FIXTURES[tool](run)
    except Exception as error:
        run.report["failures"].append({"component": tool, "error": run.clean(str(error))})
    finally:
        run.observe("driver-owned-home", home)
        if tool == "markitdown" and (run.work / "markitdown-multi-element.md").is_file():
            run.report["control"]["markitdown_output"] = run.clean((run.work / "markitdown-multi-element.md").read_text())
        if tool == "toon" and (run.work / "records.toon").is_file():
            run.report["control"]["toon_output"] = (run.work / "records.toon").read_text()
        failed = [check["label"] for check in run.report["checks"] if not check["passed"]]
        errors = [failure["error"] for failure in run.report["failures"]]
        if change is None:
            as_expected = not failed and not errors
        else:
            as_expected = failed == expected_checks and len(errors) == 1 and errors[0] == failed[0]
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
                "driver": "evidence/artifacts/token-workflow-hardening-20260926/controls_driver.py",
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
            for number, (tool, arm, change, checks, apply) in enumerate(ARMS, 1):
                name = f"{number:02d}-{tool}-{arm}"
                (output / name).mkdir()
                (base / name).mkdir()
                run = owned_run(output / name, base / name)
                run.tools.update(setup.tools)
                run.report["installation"] = "tools installed once by this driver's setup"
                run_arm(run, tool, arm, change, checks, apply)
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
