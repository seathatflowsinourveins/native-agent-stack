#!/usr/bin/env python3
"""Run the install plan's `command-output` Codex hook steps in a scratch HOME and print what each returned (one JSON object).

    python3 plan_row_scratch_run.py [OUTFILE]    # default: ~/.local/state/native-agent-stack/e2e/plan-row-scratch-run.json

The program text of every step is read from evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json (the exact strings the plan runs),
not retyped here: the config install, `rtk init -g --codex`, the trust command, and the post_install acceptance program (run with bash -euo
pipefail, as accept.sh does); the `--check` line is the last line of that program. Around them: a `--check` before the hook exists (exit 4), one after `rtk init` and before the trust (exit 5), the jq filter and test of the
after_sign_in program against synthetic streams of `codex exec --json` in the shape recorded from a real session (one that passes and five negative
fixtures: a failed rewritten command, a non-zero exit, a declined command, no rtk prefix, no command item; the model call itself needs the sign-in and is
not run), and the execution-rule review of the trust tool in more scratch homes, each with the real rtk and codex. The review parses nothing: a rule file is
accepted by its sha256 on tools/adoption/exec_rules_reviewed.json (and the conditions of its rtk) or when it is Codex's own allow-only format byte for byte.
Scenarios: #713's hcom-deny.rules by its exact bytes (the trust proceeds; a `git push` rule added after the grant makes `--check` exit 6 and the trust
refuse) and the same bytes plus one comment line (refused); the allow-only files Codex and hcom write (the trust proceeds); a configured rtk
transparent prefix, a trusted project filter and the CI override variable (each of which makes the real rtk rewrite `hcom kill luna`), an allow rule that names rtk (the evaluator allows `rtk git push origin main` under it and gives no decision for `git push origin main`) and a user TOML filter (705f's `^reviewalpha\\b|^hcom\\b`), each of which ends the review of the reviewed file (refused); a `git push` forbid rule (refused before anything is
written; --allow-exec-rules accepts it, after which `--check` exits 6) and the same rule with its `rtk git push` twin (still refused); the counterexamples of the
three GPT reads (705e: `git -C .` is not rewritten by rtk but `git -C . push origin main` is, and the native evaluator forbids the original and not the
rewrite, broad `uv` and `npx` rules, a `host_executable(name = prefix_rule(...) or "git", ...)` file that the real codex evaluator accepts and that registers a
hidden rule; 705f: a raw CR inside a triple-quoted string, a `bash -lc` script rule, a `phpunit.exe` rule, `g++` plus a combining mark); and an unreadable rules directory. Codex's own `codex execpolicy
check` is run on the rule for `git push` and `git commit` and on the nested file, and each answer must be an exit 0 with a valid response before its decision
counts. Nothing leaves the scratch HOME: rtk and Codex write their files there, and the live ~/.codex and rtk configuration are not read or written. The scratch
ECO_ROOT links the installed rtk instead of running the plan's download and extract steps. The trust command refuses while a codex process runs (the tool's own
rule); when other codex processes run on the host, the scratch run appends `--codex-process-name no-such-process-name` to it and says so, as
codex_hook_qual.py does. One run, one host: local_integration evidence.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN_DIR = ROOT / "evidence" / "artifacts" / "new-wsl-install-plan-20261002"
HCOM_RULES = (HERE / "fixtures" / "hcom-deny.rules").read_bytes()
GIT_PUSH = b'prefix_rule(pattern = ["git", "push"], decision = "forbidden", justification = "pushes need the owner")\n'
NESTED_HOST_EXECUTABLE = (b'host_executable(name = prefix_rule(pattern = ["git", "push"], decision = "forbidden") or "git", '
                          b'paths = ["/usr/bin/git"])\n')
GIT_PUSH_TWIN = b'prefix_rule(pattern = ["rtk", "git", "push"], decision = "forbidden", justification = "pushes need the owner")\n'
RAW_CR = b'prefix_rule(pattern = ["""gi\rt""", "push"], decision = "forbidden")\n'
BASH_LC = b'prefix_rule(pattern = ["/bin/bash", "-lc", "FOO=1 git push origin main"], decision = "forbidden")\n'
PHPUNIT_EXE = b'prefix_rule(pattern = ["phpunit.exe", "tests/"], decision = "forbidden")\n'
# Codex's own default.rules format (codex-rs/execpolicy/src/amend.rs) and hcom's own hcom.rules format (aannoo/hcom 7151660a3 src/hooks/codex.rs build_codex_rules)
CODEX_ALLOW = b'prefix_rule(pattern=["ls"], decision="allow")\nprefix_rule(pattern=["echo", "Hello, world!"], decision="allow")\n'
# (the lists are SAFE_HCOM_COMMANDS, src/hooks/common.rs L52-L72, and HCOM_TOOL_NAMES, src/hooks/codex.rs L578-L585; the installer itself is not run here)
SAFE_HCOM_COMMANDS = ("send", "start", "help", "--help", "-h", "list", "events", "listen", "relay", "config", "transcript", "archive", "bundle", "status",
                      "term", "hooks", "--version", "-v", "--new-terminal")
HCOM_TOOL_NAMES = ("claude", "gemini", "codex", "opencode", "antigravity", "agy")


def hcom_own_rules(prefix: tuple[str, ...]) -> bytes:
    parts = ", ".join(f'"{word}"' for word in prefix)
    rules = ["# hcom integration - auto-approve safe commands"]
    rules += [f'prefix_rule(pattern=[{parts}, "{command}"], decision="allow")' for command in SAFE_HCOM_COMMANDS]
    for tool in HCOM_TOOL_NAMES:
        rules += [f'prefix_rule(pattern=[{parts}, "{tool}", "--help"], decision="allow")', f'prefix_rule(pattern=[{parts}, "{tool}", "-h"], decision="allow")']
    return ("\n".join(rules) + "\n").encode("ascii")


HCOM_OWN = hcom_own_rules(("hcom",))
# An allow rule that names rtk: with the hook active it matches the rewritten command and not the original (the evaluator's own answer is recorded below)
ALLOW_RTK = b'prefix_rule(pattern=["rtk"], decision="allow")\n'
# 705f: a filter that rtk (after `rtk trust`) lets rewrite `hcom ...` although the first word of its pattern is `reviewalpha`
USER_FILTER = 'schema_version = 1\n\n[filters.reviewalpha]\nmatch_command = "^reviewalpha\\\\b|^hcom\\\\b"\nstrip_lines_matching = ["^#"]\n'
# 705f: rtk's Rust regex word boundary rewrites `g++` followed by a combining mark; Python's `\\w` does not include it
UNICODE_GXX = 'prefix_rule(pattern = ["g++\u0301"], decision = "forbidden")\n'.encode("utf-8")


def stream(command: str | None, exit_code: int | None, status: str) -> str:
    """A `codex exec --json` stream in the shape recorded from a real session (JSONL command item: command, aggregated_output, exit_code, status;
    codex-rs/exec/src/exec_events.rs L161-L166 at rust-v0.159.3 and rust-v0.160.0)."""
    lines = [{"type": "thread.started", "thread_id": "fixture"}]
    if command is not None:
        lines.append({"type": "item.completed", "item": {"id": "item_0", "type": "command_execution", "command": command,
                                                          "aggregated_output": "", "exit_code": exit_code, "status": status}})
    lines.append({"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}})
    return "\n".join(json.dumps(line) for line in lines) + "\n"


RTK = "/bin/bash -lc 'rtk git status --short'"
# (label, stream, the exit status the plan's after_sign_in check must end with: 0 passes, 1 fails)
AFTER_SIGN_IN_FIXTURES = (
    ("the rewritten command ran and exited 0", stream(RTK, 0, "completed"), 0),
    ("the rewritten command failed (rtk not on the launcher's PATH: exit 127)", stream(RTK, 127, "failed"), 1),
    ("the rewritten command completed with a non-zero exit status", stream(RTK, 1, "completed"), 1),
    ("the rewritten command was declined", stream(RTK, None, "declined"), 1),
    ("the command ran without the rtk prefix (no hook)", stream("/bin/bash -lc 'git status --short'", 0, "completed"), 1),
    ("no command item at all", stream(None, None, "completed"), 1),
)


def evaluator_answer(done: subprocess.CompletedProcess) -> tuple[bool, dict]:
    """A `codex execpolicy check` answer counts only with exit 0 and a JSON object whose matchedRules is a list (and a decision exactly when a rule
    matched); anything else is invalid, not an unmatched command."""
    try:
        verdict = json.loads(done.stdout)
    except ValueError:
        return False, {}
    valid = (done.returncode == 0 and isinstance(verdict, dict) and isinstance(verdict.get("matchedRules"), list)
             and (verdict.get("decision") is None) == (not verdict["matchedRules"]))
    return valid, verdict if valid else {}


def main() -> int:
    for tool in ("rtk", "codex", "jq"):
        if not shutil.which(tool):
            print(f"needs {tool} on PATH", file=sys.stderr)
            return 2
    target = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else \
        Path.home() / ".local/state/native-agent-stack/e2e/plan-row-scratch-run.json"
    plan = json.loads((PLAN_DIR / "install-plan.json").read_text(encoding="utf-8"))
    row = next(r for r in plan["owners"] if r["slot"] == "command-output")
    config_cmd, init_cmd, trust_cmd = row["commands"][2], row["commands"][4], row["commands"][5]
    assert "rtk-config.toml" in config_cmd and "init -g --codex" in init_cmd and "codex_hook_trust.py" in trust_cmd and "--apply" in trust_cmd
    post_program = row["acceptance"]["post_install"]["command"]
    after_program = row["acceptance"]["after_sign_in"]["command"]
    check_line = post_program.splitlines()[-1]
    assert "codex_hook_trust.py" in check_line and check_line.endswith("--check"), check_line
    check_cmd = 'e="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}"; ' + check_line
    busy = subprocess.run(["pgrep", "-x", "codex"], capture_output=True, text=True, check=False).stdout.split()
    steps = []
    with tempfile.TemporaryDirectory(prefix="plan-row-") as scratch:
        eco = Path(scratch) / "eco"
        (eco / "bin").mkdir(parents=True)
        os.symlink(shutil.which("rtk"), eco / "bin" / "rtk")
        hooks = json.dumps({"hooks": {"PreToolUse": [{"matcher": "", "hooks": [
            {"type": "command", "command": "python3 /fixture/memory_hook.py"}]}]}}, indent=2) + "\n"

        def make_home(name: str, rules: dict[str, bytes] | None = None) -> dict:
            """A scratch HOME with a user-layer hooks.json (a memory hook), an empty config.toml and, when given, rules files; the environment for it."""
            home = Path(scratch) / name
            (home / ".codex").mkdir(parents=True)
            (home / ".codex" / "hooks.json").write_text(hooks, encoding="utf-8")
            (home / ".codex" / "config.toml").write_text("# scratch user layer\n", encoding="utf-8")
            if rules is not None:
                (home / ".codex" / "rules").mkdir()
                for fname, body in rules.items():
                    (home / ".codex" / "rules" / fname).write_bytes(body)
            settings = {**os.environ, "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"), "XDG_DATA_HOME": str(home / ".local/share"),
                        "XDG_CACHE_HOME": str(home / ".cache"), "XDG_STATE_HOME": str(home / ".local/state"), "RTK_TELEMETRY_DISABLED": "1",
                        "ECO_ROOT": str(eco), "plan_dir": str(PLAN_DIR), "repo_root": str(ROOT)}
            settings.pop("CODEX_HOME", None)
            return settings

        env = make_home("fake-home")
        deviation = None
        execpolicy: list[dict] = []
        rtk_hook_check: list[dict] = []
        nested_check: list[dict] = []
        allow_rtk_check: list[dict] = []
        project_filter_check: list[dict] = []
        if busy:
            trust_cmd = trust_cmd + " --codex-process-name no-such-process-name"
            deviation = (f"{len(busy)} codex process(es) were running on the host, so the trust command carries "
                         f"--codex-process-name no-such-process-name (the tool would otherwise refuse, exit 2)")

        def run(label: str, program: str, expect: int | None = None, environment: dict | None = None) -> None:
            done = subprocess.run(["bash", "-euo", "pipefail", "-c", program], cwd=ROOT, env=environment or env, capture_output=True, text=True,
                                  timeout=300, check=False, stdin=subprocess.DEVNULL)
            clean = lambda text: [line.replace(scratch, "<scratch>")[:260] for line in text.splitlines() if line.strip()]  # noqa: E731
            steps.append({"step": label, "exit": done.returncode, "expected_exit": expect, "stdout_tail": clean(done.stdout)[-12:],
                          "stderr_tail": clean(done.stderr)[-3:]})

        run("--check before any rtk hook exists", check_cmd, 4)
        run("plan command 3: the exact five-entry exclusions config", config_cmd, 0)
        run("plan command 5: rtk init -g --codex", init_cmd, 0)
        run("--check after init, before the trust", check_cmd, 5)
        run("plan command 6: the trust", trust_cmd, 0)
        run("the plan's post_install acceptance program", post_program, 0)
        jq_line = next(line for line in after_program.splitlines() if line.startswith("ran=$(jq -rs "))
        jq_program = re.search(r"jq -rs ('.*?')", jq_line).group(1)
        assert after_program.splitlines()[-1] == '[[ "$ran" == "true" ]]', after_program.splitlines()[-1]
        for number, (label, fixture, expected) in enumerate(AFTER_SIGN_IN_FIXTURES):
            fixture_file = Path(scratch) / f"out-{number}.jsonl"
            fixture_file.write_text(fixture, encoding="utf-8")
            run(f"the after_sign_in filter and test on a synthetic stream: {label} (the model call is not run)",
                f'ran=$(jq -rs {jq_program} "{fixture_file}"); printf "%s\\n" "$ran"; [[ "$ran" == "true" ]]', expected)

        # Execution rules and the rewritten command. Codex matches rules against the command words after the hook's rewrite, so a rule on `git push`
        # does not match `rtk git push`: Codex's own evaluator first, then the trust tool's review in scratch homes with the real rtk and codex.
        gate = Path(scratch) / "gate.rules"
        gate.write_bytes(GIT_PUSH + b'prefix_rule(pattern = ["git", "commit"], decision = "prompt", justification = "commits are reviewed")\n')
        for command in ("git push origin main", "rtk git push origin main", "git commit -m x", "rtk git commit -m x", "git status", "rtk git status"):
            done = subprocess.run(["codex", "execpolicy", "check", "--rules", str(gate), "--", *command.split()], env=env, capture_output=True,
                                  text=True, timeout=120, check=False, stdin=subprocess.DEVNULL)
            valid, verdict = evaluator_answer(done)
            execpolicy.append({"command": command, "exit": done.returncode, "valid": valid, "decision": verdict.get("decision"),
                               "matched_prefixes": [m.get("prefixRuleMatch", {}).get("matchedPrefix") for m in verdict.get("matchedRules", [])]})

        for command in ("git -C .", "git -C . push origin main", "uv", "uv run harmless.py", "npx", "npx prisma migrate deploy", "uvx hcom kill luna",
                        "phpunit.exe tests/", "g++\u0301 --version", "hcom kill luna"):
            done = subprocess.run(["rtk", "hook", "check", "--agent", "codex", command], env=env, capture_output=True, text=True, timeout=60, check=False,
                                  stdin=subprocess.DEVNULL)
            rtk_hook_check.append({"command": command, "exit": done.returncode, "rewritten_to": done.stdout.strip() or None})
        nested_file = Path(scratch) / "nested.rules"
        nested_file.write_bytes(NESTED_HOST_EXECUTABLE)
        for command in ("git push origin main", "rtk git push origin main"):
            done = subprocess.run(["codex", "execpolicy", "check", "--rules", str(nested_file), "--", *command.split()], env=env, capture_output=True,
                                  text=True, timeout=120, check=False, stdin=subprocess.DEVNULL)
            valid, verdict = evaluator_answer(done)
            nested_check.append({"command": command, "exit": done.returncode, "valid": valid, "decision": verdict.get("decision")})

        allow_rtk_file = Path(scratch) / "allow-rtk.rules"
        allow_rtk_file.write_bytes(ALLOW_RTK)
        for command in ("rtk git push origin main", "git push origin main"):
            done = subprocess.run(["codex", "execpolicy", "check", "--rules", str(allow_rtk_file), "--", *command.split()], env=env, capture_output=True,
                                  text=True, timeout=120, check=False, stdin=subprocess.DEVNULL)
            valid, verdict = evaluator_answer(done)
            allow_rtk_check.append({"command": command, "exit": done.returncode, "valid": valid, "decision": verdict.get("decision")})

        def home_with_hook(name: str, rules: dict[str, bytes]) -> dict:
            settings = make_home(name, rules)
            run(f"{name}: plan command 3 (the exclusions config)", config_cmd, 0, settings)
            run(f"{name}: plan command 5 (rtk init -g --codex)", init_cmd, 0, settings)
            return settings

        def rtk_config_dir(settings: dict) -> Path:
            return Path(settings["HOME"]) / ".config" / "rtk"

        hcom = home_with_hook("rules-hcom", {"hcom-deny.rules": HCOM_RULES})
        run("rules-hcom (#713's hcom-deny.rules, on the reviewed list by its sha256): --check before the trust", check_cmd, 5, hcom)
        run("rules-hcom: the plan's trust command proceeds", trust_cmd, 0, hcom)
        run("rules-hcom: --check", check_cmd, 0, hcom)
        (Path(hcom["HOME"]) / ".codex" / "rules" / "default.rules").write_bytes(GIT_PUSH)
        run("rules-hcom: a git push forbid rule is added after the grant: --check exits 6", check_cmd, 6, hcom)
        run("rules-hcom: the trust command now refuses although the hook is already trusted", trust_cmd, 2, hcom)

        modified = home_with_hook("rules-hcom-modified", {"hcom-deny.rules": HCOM_RULES + b"# note\n"})
        run("rules-hcom-modified (the reviewed bytes plus one comment line): refused, one added byte ends the review", trust_cmd, 2, modified)

        allow = home_with_hook("rules-allow-only", {"default.rules": CODEX_ALLOW, "hcom.rules": HCOM_OWN})
        run("rules-allow-only (Codex's default.rules format and hcom's hcom.rules format): the trust proceeds", trust_cmd, 0, allow)
        run("rules-allow-only: --check", check_cmd, 0, allow)

        prefixed = home_with_hook("rules-hcom-prefix", {"hcom-deny.rules": HCOM_RULES})
        config_file = rtk_config_dir(prefixed) / "config.toml"
        config_file.write_text(config_file.read_text(encoding="utf-8") + 'transparent_prefixes = ["sudo"]\n', encoding="utf-8")
        run("rules-hcom-prefix (the reviewed file, a configured rtk transparent prefix): refused", trust_cmd, 2, prefixed)

        filtered = home_with_hook("rules-hcom-filter", {"hcom-deny.rules": HCOM_RULES})
        (rtk_config_dir(filtered) / "filters.toml").write_text(USER_FILTER, encoding="utf-8")
        run("rules-hcom-filter (the reviewed file, a user TOML filter beside rtk's config): refused", trust_cmd, 2, filtered)

        # A trusted project filter (`rtk trust`) or the CI override variable makes the hook rewrite `hcom ...` although the first word of the filter's pattern
        # is something else: measured with the real rtk, from the project's own directory. The trust store is global, so `rtk trust --list` shows a trusted
        # filter from anywhere; the override variable is not in the store, so the tool also looks at its own environment.
        def project_step(settings: dict, project: Path, step: str, command: list[str], extra: dict | None = None) -> subprocess.CompletedProcess:
            done = subprocess.run(command, cwd=project, env={**settings, **(extra or {})}, capture_output=True, text=True, timeout=60, check=False,
                                  stdin=subprocess.DEVNULL)
            shown = [line.replace(scratch, "<scratch>")[:200] for line in done.stdout.splitlines() if line.strip()][:3]
            project_filter_check.append({"step": step, "exit": done.returncode, "stdout": shown, "stderr_first": (done.stderr.strip().splitlines() or [""])[0][:100]})
            return done

        hook_check = ["rtk", "hook", "check", "--agent", "codex", "hcom kill luna"]
        trusted_filter = home_with_hook("rules-hcom-trusted-filter", {"hcom-deny.rules": HCOM_RULES})
        project = Path(trusted_filter["HOME"]) / "project"
        (project / ".rtk").mkdir(parents=True)
        (project / ".rtk" / "filters.toml").write_text(USER_FILTER, encoding="utf-8")
        project_step(trusted_filter, project, "project filter present, untrusted: hook check hcom kill luna", hook_check)
        project_step(trusted_filter, project, "rtk trust --yes in the project", ["rtk", "trust", "--yes"])
        project_step(trusted_filter, project, "project filter trusted: hook check hcom kill luna", hook_check)
        project_step(trusted_filter, Path(trusted_filter["HOME"]), "rtk trust --list from another directory", ["rtk", "trust", "--list"])
        run("rules-hcom-trusted-filter (the reviewed file, a trusted project filter that makes rtk rewrite hcom): refused", trust_cmd, 2, trusted_filter)

        override = home_with_hook("rules-hcom-trust-override", {"hcom-deny.rules": HCOM_RULES})
        project_env = Path(override["HOME"]) / "project"
        (project_env / ".rtk").mkdir(parents=True)
        (project_env / ".rtk" / "filters.toml").write_text(USER_FILTER, encoding="utf-8")
        trust_override = {"RTK_TRUST_PROJECT_FILTERS": "1", "CI": "1"}
        project_step(override, project_env, "no store entry, no override: hook check hcom kill luna", hook_check)
        project_step(override, project_env, "RTK_TRUST_PROJECT_FILTERS=1 and CI=1, no store entry: hook check hcom kill luna", hook_check, trust_override)
        project_step(override, project_env, "RTK_TRUST_PROJECT_FILTERS=1 and CI=1: rtk trust --list", ["rtk", "trust", "--list"], trust_override)
        run("rules-hcom-trust-override (the reviewed file, RTK_TRUST_PROJECT_FILTERS in the tool's environment): refused", trust_cmd, 2, {**override, **trust_override})

        exposed = home_with_hook("rules-exposed", {"default.rules": GIT_PUSH})
        run("rules-exposed (a git push forbid rule, no rtk twin): the trust command is refused before anything is written", trust_cmd, 2, exposed)
        run("rules-exposed: --check says the hook is not trusted (nothing was written)", check_cmd, 5, exposed)
        run("rules-exposed: --allow-exec-rules accepts the exposure", trust_cmd + " --allow-exec-rules", 0, exposed)
        run("rules-exposed: --check after the accepted trust exits 6", check_cmd, 6, exposed)
        run("rules-exposed: --check --allow-exec-rules", check_cmd + " --allow-exec-rules", 0, exposed)

        twin = home_with_hook("rules-twin", {"default.rules": GIT_PUSH + GIT_PUSH_TWIN})
        run("rules-twin (the git push rule and its rtk git push twin): still refused, a twin cannot be shown to cover every rewrite", trust_cmd, 2, twin)
        run("rules-twin: --allow-exec-rules accepts it", trust_cmd + " --allow-exec-rules", 0, twin)

        counter = home_with_hook("rules-705e-extension", {"default.rules": b'prefix_rule(pattern = ["git", "-C", "."], decision = "forbidden")\n'})
        run("rules-705e-extension (`git -C .` forbidden; rtk leaves `git -C .` alone but rewrites `git -C . push origin main`): refused", trust_cmd, 2, counter)
        broad = home_with_hook("rules-705e-broad", {"default.rules": b'prefix_rule(pattern = ["uv"], decision = "prompt")\n'
                                                                  b'prefix_rule(pattern = [["npx", "bunx"]], decision = "forbidden")\n'})
        run("rules-705e-broad (broad `uv` and `npx` rules): refused", trust_cmd, 2, broad)
        nested = home_with_hook("rules-705e-nested", {"nested.rules": NESTED_HOST_EXECUTABLE})
        run("rules-705e-nested (a prefix_rule nested in host_executable, which the real evaluator registers): refused", trust_cmd, 2, nested)
        raw_cr = home_with_hook("rules-705f-raw-cr", {"default.rules": RAW_CR})
        run("rules-705f-raw-cr (a raw CR inside a triple-quoted token: Codex's lexer reads `git push`): refused", trust_cmd, 2, raw_cr)
        bash_lc = home_with_hook("rules-705f-bash-lc", {"default.rules": BASH_LC})
        run("rules-705f-bash-lc (an assignment-prefixed script matched against the whole shell argv): refused", trust_cmd, 2, bash_lc)
        phpunit = home_with_hook("rules-705f-phpunit", {"default.rules": PHPUNIT_EXE})
        run("rules-705f-phpunit (`phpunit.exe`, which rtk normalizes to its PHP tool word): refused", trust_cmd, 2, phpunit)

        allow_rtk = home_with_hook("rules-allow-rtk", {"default.rules": ALLOW_RTK})
        run("rules-allow-rtk (an allow rule that names rtk: it matches the rewritten command and not the original, a widened approval): refused", trust_cmd, 2, allow_rtk)

        unicode_gxx = home_with_hook("rules-705f-unicode", {"default.rules": UNICODE_GXX})
        run("rules-705f-unicode (`g++` plus a combining mark, which rtk's Rust regex rewrites): refused", trust_cmd, 2, unicode_gxx)

        unreadable = home_with_hook("rules-unreadable", {"default.rules": GIT_PUSH})
        rules_dir = Path(unreadable["HOME"]) / ".codex" / "rules"
        if os.geteuid() == 0:
            steps.append({"step": "rules-unreadable: skipped (running as root, so a mode 000 directory is still listable)", "exit": 2,
                          "expected_exit": 2, "stdout_tail": [], "stderr_tail": []})
        else:
            rules_dir.chmod(0)
            try:
                run("rules-unreadable (the rules directory cannot be listed): the trust command fails closed", trust_cmd, 2, unreadable)
            finally:
                rules_dir.chmod(0o755)
    record = {"schema": "plan-row-scratch-run/3", "evidence_class": "local_integration: one run, one host, scratch HOMEs, the real rtk and codex (the stream is synthetic)",
              "rtk": subprocess.run(["rtk", "--version"], capture_output=True, text=True, check=False).stdout.strip(),
              "codex": subprocess.run(["codex", "--version"], capture_output=True, text=True, check=False).stdout.strip(),
              "deviation": deviation, "steps": steps, "execpolicy_check": execpolicy,
              "rtk_hook_check": rtk_hook_check, "nested_host_executable_check": nested_check, "allow_rtk_check": allow_rtk_check, "project_filter_check": project_filter_check,
              "all_as_expected": all(step["exit"] == step["expected_exit"] for step in steps) and all(e["valid"] for e in execpolicy) and
              [e["decision"] for e in execpolicy] == ["forbidden", None, "prompt", None, None, None] and
              all(e["valid"] for e in nested_check) and [e["decision"] for e in nested_check] == ["forbidden", None] and
              all(e["valid"] for e in allow_rtk_check) and [e["decision"] for e in allow_rtk_check] == ["allow", None] and
              [(e["exit"], e["stdout"][:1]) for e in project_filter_check] ==
              [(1, []), (0, ["Risk summary:"]), (0, ["rtk hcom kill luna"]), (0, ["Trusted filters:"]), (1, []), (0, ["rtk hcom kill luna"]),
               (0, ["No trusted filters."])] and
              [(e["command"], e["exit"], bool(e["rewritten_to"])) for e in rtk_hook_check] ==
              [("git -C .", 1, False), ("git -C . push origin main", 0, True), ("uv", 1, False), ("uv run harmless.py", 0, True), ("npx", 1, False),
               ("npx prisma migrate deploy", 0, True), ("uvx hcom kill luna", 1, False), ("phpunit.exe tests/", 0, True), ("g++\u0301 --version", 0, True),
               ("hcom kill luna", 1, False)]}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {target}: {len(steps)} steps, all as expected: {record['all_as_expected']}")
    return 0 if record["all_as_expected"] else 1


if __name__ == "__main__":
    sys.exit(main())
