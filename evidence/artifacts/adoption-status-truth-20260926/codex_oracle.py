#!/usr/bin/env python3
"""local_integration oracle: ask Codex's own `codex app-server` `hooks/list` (stdio JSON-RPC: `initialize`, the
`initialized` notification, `hooks/list`; no thread, no model call, no write request) how it loads a hooks.json,
in a throwaway CODEX_HOME and HOME under --base. Nothing touches the real ~/.codex.

Two modes:
  parse    one hooks.json text per case (duplicate keys, NaN, lone surrogates, out-of-range numbers, nesting depth,
           array forms, ...). Codex is asked twice: first with an empty config.toml, then with a config.toml that
           trusts every user hook with the currentHash Codex itself reported. So a case's "trusted" count is
           Codex's own, independent of any checker. With --repo, the same config is then read by that checkout's
           scripts/adoption_status.py codex_wiring, whose counts are printed beside Codex's.
  matchers one PreToolUse group per matcher string; a group Codex loads appears in hooks/list, a group whose
           matcher Codex cannot compile does not. With --repo, codex_matcher_loads's verdict is printed beside it.
  trust    twelve hook shapes (matchers, timeouts, async, status messages, context limits, Windows commands,
           Unicode). Codex first reports each hook's key and currentHash; the config.toml then gives each hook one
           [hooks.state] variant: trusted with Codex's own hash, a stale hash, no state, trusted but disabled,
           trusted under its key padded with spaces, or trusted under its key prefixed with U+001C. Codex's
           second answer (trustStatus, enabled) is compared per hook with --repo's codex_hook_hashes and
           codex_hook_states on the same files, and so is each hash (compared here, never printed).

Output is JSON lines with the throwaway base path replaced by $BASE; no hash value is printed (a hash is only
compared inside this process).
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import shlex
import signal
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path, PurePosixPath

AI = "/opt/example/ai-memory --data-dir /opt/example hook --event {} --agent codex --server-url http://127.0.0.1:1"
STOP = AI.format("stop")


def group(handler: str, extra: str = "") -> str:
    return '{"hooks": [' + handler + ']' + extra + '}'


def command(cmd: str = STOP, extra: str = "") -> str:
    return '{"type": "command", "command": ' + json.dumps(cmd) + extra + '}'


def nested(depth: int) -> str:
    return "[" * depth + "]" * depth


def stop_file(groups: str, extra: str = "") -> str:
    return '{"hooks": {"Stop": [' + groups + ']' + extra + '}}'


# One Stop hook running ai-memory unless stated. The label says what differs from the control.
PARSE_CASES = [
    ("control", stop_file(group(command()))),
    ("dup top-level hooks", '{"hooks": {}, "hooks": {"Stop": [' + group(command()) + ']}}'),
    ("dup top-level description", '{"description": "a", "description": "b", "hooks": {"Stop": ['
     + group(command()) + ']}}'),
    ("unknown top-level key", '{"x": 1, "hooks": {"Stop": [' + group(command()) + ']}}'),
    ("dup event Stop", '{"hooks": {"Stop": [], "Stop": [' + group(command()) + ']}}'),
    ("dup unknown event", stop_file(group(command()), ', "Future": 1, "Future": 2')),
    ("dup group matcher (PreToolUse)", '{"hooks": {"PreToolUse": [{"matcher": "", "matcher": "", "hooks": ['
     + command(AI.format("pre-tool-use")) + ']}]}}'),
    ("dup group unknown field", stop_file(group(command(), ', "note": 1, "note": 2'))),
    ("dup handler command", stop_file(group('{"type": "command", "command": "echo", "command": '
                                            + json.dumps(STOP) + '}'))),
    ("dup handler type", stop_file(group('{"type": "command", "type": "command", "command": '
                                         + json.dumps(STOP) + '}'))),
    ("dup handler unknown field", stop_file(group(command(extra=', "note": 1, "note": 2')))),
    ("commandWindows and command_windows", stop_file(group(command(extra=', "commandWindows": "a", '
                                                                         '"command_windows": "b"')))),
    ("NaN in handler unknown field", stop_file(group(command(extra=', "note": NaN')))),
    ("NaN in unknown event", stop_file(group(command()), ', "Future": NaN')),
    ("Infinity in group unknown field", stop_file(group(command(), ', "note": Infinity'))),
    ("lone surrogate in command", stop_file(group('{"type": "command", "command": "' + STOP + ' \\ud800"}'))),
    ("lone surrogate in handler unknown field", stop_file(group(command(extra=', "note": "\\ud800"')))),
    ("lone surrogate in handler unknown key", stop_file(group(command(extra=', "\\ud800": 1')))),
    ("lone surrogate in group unknown field", stop_file(group(command(), ', "note": "\\ud800"'))),
    ("lone surrogate in group unknown key", stop_file(group(command(), ', "\\ud800": 1'))),
    ("lone surrogate nested in group unknown field", stop_file(group(command(), ', "note": {"\\ud800": "\\udc00x"}'))),
    ("lone surrogate in unknown event", stop_file(group(command()), ', "Future": "\\ud800"')),
    ("lone surrogate in description", '{"description": "\\ud800", "hooks": {"Stop": [' + group(command()) + ']}}'),
    ("surrogate pair in command", stop_file(group('{"type": "command", "command": "' + STOP + ' \\ud83d\\ude00"}'))),
    ("1e400 in handler unknown field", stop_file(group(command(extra=', "note": 1e400')))),
    ("1e400 in group unknown field", stop_file(group(command(), ', "note": 1e400'))),
    ("400-digit integer in handler unknown field", stop_file(group(command(extra=', "note": 1' + "0" * 400)))),
    ("timeout -0", stop_file(group(command(extra=', "timeout": -0')))),
    ("timeout 2^64", stop_file(group(command(extra=', "timeout": 18446744073709551616')))),
    ("timeout 5.0", stop_file(group(command(extra=', "timeout": 5.0')))),
    ("timeout 2^63 (Stop)", stop_file(group(command(extra=', "timeout": 9223372036854775808')))),
    ("timeout 2^63-1 (Stop)", stop_file(group(command(extra=', "timeout": 9223372036854775807')))),
    ("timeout 2^64-1 (SessionEnd clamps)", '{"hooks": {"SessionEnd": [' + group(command(
        AI.format("session-end"), ', "timeout": 18446744073709551615')) + ']}}'),
    ("async null", stop_file(group(command(extra=', "async": null')))),
    ("type as variant index 0", stop_file(group('{"type": 0, "command": ' + json.dumps(STOP) + '}'))),
    ("mcp_tool input dup, last not null", stop_file(group(command()) + ", " + group(
        '{"type": "mcp_tool", "server": "s", "tool": "t", "input": {"k": null, "k": 1}}'))),
    ("mcp_tool input dup, last null", stop_file(group(command()) + ", " + group(
        '{"type": "mcp_tool", "server": "s", "tool": "t", "input": {"k": 1, "k": null}}'))),
    ("mcp_tool input 2^63", stop_file(group(command()) + ", " + group(
        '{"type": "mcp_tool", "server": "s", "tool": "t", "input": {"k": 9223372036854775808}}'))),
    ("mcp_tool input 2^64", stop_file(group(command()) + ", " + group(
        '{"type": "mcp_tool", "server": "s", "tool": "t", "input": {"k": 18446744073709551616}}'))),
    ("mcp_tool input -2^63-1", stop_file(group(command()) + ", " + group(
        '{"type": "mcp_tool", "server": "s", "tool": "t", "input": {"k": -9223372036854775809}}'))),
    ("depth 127 inside handler", stop_file(group(command(extra=', "note": ' + nested(121))))),
    ("depth 128 inside handler", stop_file(group(command(extra=', "note": ' + nested(122))))),
    ("depth 300 in group unknown field", stop_file(group(command(), ', "note": ' + nested(296)))),
    ("group as array", '{"hooks": {"Stop": [[null, [' + command() + ']]]}}'),
    ("group array too long", '{"hooks": {"Stop": [[null, [' + command() + '], 1]]}}'),
    ("handler as array", stop_file(group('["command", ' + json.dumps(STOP) + ']'))),
    ("prompt handler as array with a field", stop_file(group(command()) + ", " + group('["prompt", 1]'))),
    ("events as array", '{"hooks": [' + "[], " * 10 + '[' + group(command()) + ']]}'),
    ("file as array", '[null, {"Stop": [' + group(command()) + ']}]'),
    ("hooks null", '{"hooks": null}'),
    ("event null", '{"hooks": {"Stop": null}}'),
    ("blank command", stop_file(group(command("   ")) + ", " + group(command()))),
    ("unit separator command", stop_file(group(command("\u001f")) + ", " + group(command()))),
    ("empty file", ""),
    ("BOM", "\ufeff" + stop_file(group(command()))),
    # appended after the first run, so earlier indices stay stable
    ("mcp_tool timeout 2^63 (Stop)", stop_file(group(command()) + ", " + group(
        '{"type": "mcp_tool", "server": "s", "tool": "t", "timeout": 9223372036854775808}'))),
    ("mcp_tool timeout 2^63 (SessionEnd skips MCP)", '{"hooks": {"SessionEnd": [' + group(command(
        AI.format("session-end"))) + ", " + group('{"type": "mcp_tool", "server": "s", "tool": "t", '
                                                   '"timeout": 9223372036854775808}') + ']}}'),
    ("mcp_tool blank server, timeout 2^63", stop_file(group(command()) + ", " + group(
        '{"type": "mcp_tool", "server": " ", "tool": "t", "timeout": 9223372036854775808}'))),
    ("additionalContextLimit 2^63 (SessionStart)", '{"hooks": {"SessionStart": [' + group(command(
        AI.format("session-start"), ', "additionalContextLimit": 9223372036854775808')) + ']}}'),
    ("additionalContextLimit 2^63 (Stop drops it)", stop_file(group(command(
        extra=', "additionalContextLimit": 9223372036854775808')))),
    ("invalid matcher group, timeout 2^63", '{"hooks": {"PreToolUse": [{"matcher": "(", "hooks": ['
     + command(AI.format("pre-tool-use"), ', "timeout": 9223372036854775808') + ']}, ' + group(command(
         AI.format("pre-tool-use"))) + ']}}'),
    ("lone surrogate in matcher", '{"hooks": {"PreToolUse": [{"matcher": "\\ud800", "hooks": ['
     + command(AI.format("pre-tool-use")) + ']}]}}'),
    ("lone surrogate in unknown event key", stop_file(group(command()), ', "\\ud800": 1')),
    ("matcher on Stop ignored", '{"hooks": {"Stop": [{"matcher": "(", "hooks": [' + command() + ']}]}}'),
]

MATCHERS = [
    "", "*", "Bash", "Bash|Edit", "mcp__.*", "Ba.*", "^Bash$", "(Bash|Edit)", "(?:Bash)", "[A-Z]\\w+", "\\d+",
    "\\bBash\\b", "Bash.*?", "B.+", "Bas?h", "a|", "()", "\\.", "\\-", "\\#", "\\&", "\\~", "\\n", "\\t", "\\a",
    "\\v", "\\f", "\\r", "[a-]", "[-a]", "[^a-z]", "[\\d_]", "[\\]]", "[\\-a]", "[é]", "é+", "a b", "#x",
    "\\AB", "Bash$", "(^)*", "(a|)*", "(?:)*", "()+", "(\\b)?", "[.]", "[*+?]", "[(){}|$]", "[a^]", "[\\\\]",
    "[\\n]", "[-]", "[^-]", "[a-z0-9_]", "\\\\", "a$b", "(?:)", "(|)", "a||b", "\\B", "[^\\W]",
    "[a-z-]", "[Z-a]", "[9-0]", "x|", "(?:a|b)+?", "[^\\s]+", "\\W*", "[--]", "[a\\-]", "[.-]",
    # invalid in both engines, inside the shared subset
    "(", ")", "*a", "a|*", "(*)", "[a", "[z-a]", "a\\", "a**", "a+*",
    # outside the shared subset (the check answers null); Codex's verdict is recorded for reference
    "(?#note)Bash", "(?a)Bash", "\\0Bash", "(B)?(?(1)ash|x)", "\\N{LATIN SMALL LETTER A}", "(?i)bash",
    "(?P<n>a)", "(?<n>a)", "(?=a)", "(a)\\1", "(?>a)", "a\\Z", "a\\z", "\\p{L}", "\\pL", "a{2}", "a{2,}",
    "a{,2}", "a{", "a{}", "}", "]", "[[:alpha:]]", "[a&&b]", "[a--b]", "[a~~b]", "\\x41", "\\x{41}", "\\u0041",
    "\\U00000041", "\\<a", "\\/", "\\:", "\\ ", "a*+", "a++", "a?+", "^*", "$+", "\\b*", "[]a]", "[^]a]", "\\e",
    "[\\b]", "\\_",
]


def hooks_list(codex_home: Path, home: Path, timeout: float = 45.0) -> list[dict]:
    """hooks/list from a throwaway app-server; RuntimeError when it answers with an error, closes its output or
    gives no answer in ``timeout`` seconds (Codex 0.157.1 hangs, for example, on a hook it cannot hash)."""
    env = {key: value for key, value in os.environ.items()
           if key not in ("OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_HOME")}
    env.update(CODEX_HOME=str(codex_home), HOME=str(home), RUST_LOG="error")
    process = subprocess.Popen(["codex", "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, cwd=home, env=env, text=True, start_new_session=True)
    lines: queue.Queue = queue.Queue()

    def read():
        for line in process.stdout:
            lines.put(line)
        lines.put("")  # end of output

    threading.Thread(target=read, daemon=True).start()

    def send(message):
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

    def response(request_id, deadline):
        while True:
            try:
                line = lines.get(timeout=max(0.0, deadline - time.monotonic()))
            except queue.Empty:
                raise RuntimeError(f"no answer within {timeout:.0f} s") from None
            if not line:
                raise RuntimeError("app-server closed its output")
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if message.get("id") == request_id and ("result" in message or "error" in message):
                if "error" in message:
                    raise RuntimeError(f"app-server error: {message['error'].get('message')}")
                return message["result"]

    deadline = time.monotonic() + timeout
    try:
        send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "u5-oracle", "version": "0"}}})
        response(1, deadline)
        send({"method": "initialized"})
        send({"id": 2, "method": "hooks/list", "params": {"cwds": [str(home)]}})
        return response(2, deadline)["data"]
    finally:
        for sig, wait in ((signal.SIGTERM, 3), (signal.SIGKILL, 10)):
            try:
                os.killpg(process.pid, sig)
                process.wait(timeout=wait)
                break
            except ProcessLookupError:
                break
            except subprocess.TimeoutExpired:
                continue


def runs_ai_memory(command_text) -> bool:
    try:
        argv = shlex.split(command_text or "")
    except ValueError:
        return False
    return bool(argv) and PurePosixPath(argv[0]).name == "ai-memory" and "hook" in argv[1:]


def fresh(root: Path) -> tuple[Path, Path]:
    shutil.rmtree(root, ignore_errors=True)
    codex_home, home = root / "codex", root / "home"
    codex_home.mkdir(parents=True)
    home.mkdir()
    return codex_home.resolve(), home.resolve()


def parse_mode(base: Path, adoption_status, only: set[int] | None = None) -> int:
    disagreements = 0
    for index, (label, text) in enumerate(PARSE_CASES):
        if only is not None and index not in only:
            continue
        codex_home, home = fresh(base / f"parse-{index:02d}")
        (codex_home / "hooks.json").write_text(text, encoding="utf-8")
        (codex_home / "config.toml").write_text("", encoding="utf-8")
        try:
            data = hooks_list(codex_home, home)
        except RuntimeError as error:  # no hooks/list answer: Codex loads nothing it could report
            row = {"case": label, "codex_answer": str(error)}
            if adoption_status is not None:
                wiring = adoption_status.codex_wiring(codex_home, str(codex_home))
                row["checker_configured_trusted"] = [wiring["ai_memory_hook_events"],
                                                     wiring["ai_memory_hook_events_trusted"]]
                row["agrees"] = row["checker_configured_trusted"] == [None, None]
                disagreements += not row["agrees"]
            print(json.dumps(row), flush=True)
            continue
        user = [hook for entry in data for hook in entry["hooks"] if hook["source"] == "user"]
        warnings = [w.replace(str(base), "$BASE")[:160] for entry in data for w in entry["warnings"]]
        state = "".join(f'[hooks.state.{json.dumps(hook["key"])}]\ntrusted_hash = {json.dumps(hook["currentHash"])}\n'
                        for hook in user)
        (codex_home / "config.toml").write_text(state, encoding="utf-8")
        trusted = [hook for entry in hooks_list(codex_home, home) for hook in entry["hooks"]
                   if hook["source"] == "user" and hook["enabled"] and hook["trustStatus"] == "trusted"]
        events = {hook["eventName"] for hook in user if runs_ai_memory(hook.get("command"))}
        running = {hook["eventName"] for hook in trusted if runs_ai_memory(hook.get("command"))}
        row = {"case": label, "codex_parse_failed": any("failed to parse hooks config" in w for w in warnings),
               "codex_user_hooks": len(user), "codex_ai_memory_events": len(events),
               "codex_ai_memory_events_trusted": len(running), "codex_warnings": warnings}
        if adoption_status is not None:
            try:
                wiring = adoption_status.codex_wiring(codex_home, str(codex_home))
                checker = [wiring["ai_memory_hook_events"], wiring["ai_memory_hook_events_trusted"]]
            except Exception as error:  # noqa: BLE001 - a crash is a finding, reported as such
                checker = f"raised {type(error).__name__}"
            expected = None if row["codex_parse_failed"] else [len(events), len(running)]
            row["checker_configured_trusted"] = checker
            row["agrees"] = checker == ([None, None] if expected is None else expected)
            disagreements += not row["agrees"]
        print(json.dumps(row), flush=True)
    return disagreements


def matcher_mode(base: Path, adoption_status) -> int:
    codex_home, home = fresh(base / "matchers")
    groups = [{"matcher": matcher, "hooks": [{"type": "command", "command": AI.format("pre-tool-use")}]}
              for matcher in MATCHERS]
    (codex_home / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": groups}}), encoding="utf-8")
    (codex_home / "config.toml").write_text("", encoding="utf-8")
    data = hooks_list(codex_home, home)
    loaded = {int(hook["key"].rsplit(":", 2)[1]) for entry in data for hook in entry["hooks"]
              if hook["source"] == "user"}
    disagreements = 0
    for index, matcher in enumerate(MATCHERS):
        row = {"matcher": matcher, "codex_loads": index in loaded}
        if adoption_status is not None:
            verdict = adoption_status.codex_matcher_loads(matcher)
            row["checker"] = verdict
            row["agrees"] = verdict is None or verdict == row["codex_loads"]
            disagreements += not row["agrees"]
        print(json.dumps(row, ensure_ascii=False), flush=True)
    return disagreements


TRUST_SHAPES = [
    ("SessionStart", "", {"type": "command", "command": AI.format("session-start")}),
    ("UserPromptSubmit", "", {"type": "command", "command": AI.format("user-prompt-submit")}),
    ("PreToolUse", "Bash", {"type": "command", "command": AI.format("pre-tool-use"), "timeout": 30}),
    ("PreToolUse", None, {"type": "command", "command": "rtk hook codex", "statusMessage": "rewriting"}),
    ("PostToolUse", "mcp__.*", {"type": "command", "command": AI.format("post-tool-use"), "async": True}),
    ("PreCompact", "*", {"type": "command", "command": AI.format("pre-compact"), "additionalContextLimit": 3000}),
    ("SessionStart", "startup", {"type": "command", "command": AI.format("session-start"),
                                 "additionalContextLimit": 2500}),
    ("SessionStart", "resume", {"type": "command", "command": AI.format("session-start"),
                                "additionalContextLimit": 4000}),
    ("SessionEnd", "", {"type": "command", "command": AI.format("session-end")}),
    ("SessionEnd", "", {"type": "command", "command": AI.format("session-end"), "timeout": 10}),
    ("Stop", "", {"type": "command", "command": AI.format("stop"), "timeout": 0}),
    ("Stop", "", {"type": "command", "command": "echo 'quoted \"text\" \u00e9'", "commandWindows": "echo win"}),
]
TRUST_VARIANTS = ("trusted", "stale hash", "no state", "trusted, disabled", "trusted, key padded with spaces",
                  "trusted, key prefixed with U+001C")


def trust_state(variant: str, key: str, current: str) -> str:
    if variant == "no state":
        return ""
    name = {"trusted, key padded with spaces": f"  {key} ",
            "trusted, key prefixed with U+001C": "\u001c" + key}.get(variant, key)
    digest = "sha256:" + "0" * 64 if variant == "stale hash" else current
    table_key = json.dumps(name)  # a JSON string is a TOML basic string here: ASCII, U+001C as \u001c
    return (f"[hooks.state.{table_key}]\ntrusted_hash = {json.dumps(digest)}\n"
            + ("enabled = false\n" if variant == "trusted, disabled" else ""))


def trust_mode(base: Path, adoption_status) -> int:
    codex_home, home = fresh(base / "trust")
    events: dict = {}
    for event, matcher, handler in TRUST_SHAPES:
        events.setdefault(event, []).append({"hooks": [handler]} if matcher is None else
                                            {"matcher": matcher, "hooks": [handler]})
    text = json.dumps({"hooks": events})
    (codex_home / "hooks.json").write_text(text, encoding="utf-8")
    (codex_home / "config.toml").write_text("", encoding="utf-8")
    first = [hook for entry in hooks_list(codex_home, home) for hook in entry["hooks"] if hook["source"] == "user"]
    variants = {hook["key"]: TRUST_VARIANTS[index % len(TRUST_VARIANTS)]
                for index, hook in enumerate(sorted(first, key=lambda hook: hook["key"]))}
    (codex_home / "config.toml").write_text("".join(trust_state(variants[hook["key"]], hook["key"],
                                                                hook["currentHash"]) for hook in first),
                                            encoding="utf-8")
    second = [hook for entry in hooks_list(codex_home, home) for hook in entry["hooks"] if hook["source"] == "user"]
    current = {hook["key"]: hook["currentHash"] for hook in first}
    mine = states = None
    if adoption_status is not None:
        mine = adoption_status.codex_hook_hashes(f"{codex_home}/hooks.json", adoption_status.codex_hooks_json(text))
        states = adoption_status.codex_hook_states(
            adoption_status.read_client_file(codex_home / "config.toml", "toml"))
    disagreements = 0
    for hook in sorted(second, key=lambda hook: hook["key"]):
        codex_runs = hook["enabled"] and hook["trustStatus"] == "trusted"
        row = {"event": hook["eventName"], "key": hook["key"].replace(str(base), "$BASE"),
               "variant": variants[hook["key"]], "codex_trust": hook["trustStatus"], "codex_enabled": hook["enabled"],
               "codex_runs": codex_runs}
        if mine is not None:
            _, loads, digest, _ = mine.get(hook["key"], (None, None, None, None))
            state = states.get(hook["key"], {})
            checker_runs = bool(loads) and state.get("enabled") is not False and state.get("trusted_hash") == digest
            row.update(checker_hash_equals_codex=digest == current[hook["key"]], checker_runs=checker_runs)
            row["agrees"] = row["checker_hash_equals_codex"] and checker_runs == codex_runs
            disagreements += not row["agrees"]
        print(json.dumps(row, ensure_ascii=False), flush=True)
    if mine is not None:
        extra = set(mine) - {hook["key"] for hook in second}
        print(json.dumps({"codex_user_hooks": len(second), "checker_hooks": len(mine),
                          "checker_hooks_codex_lacks": len(extra)}))
        disagreements += len(extra) + (len(mine) != len(second))
    return disagreements


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("parse", "matchers", "trust"))
    parser.add_argument("--base", required=True, help="throwaway directory for the CODEX_HOME and HOME pairs")
    parser.add_argument("--repo", help="checkout whose scripts/adoption_status.py is compared with Codex")
    parser.add_argument("--cases", help="parse mode: comma-separated case indices to run (default: all)")
    args = parser.parse_args()
    adoption_status = None
    if args.repo:
        sys.path.insert(0, str(Path(args.repo).resolve() / "scripts"))
        import adoption_status  # noqa: E402
    base = Path(args.base).resolve()
    if base.exists() and (not base.is_dir() or any(base.iterdir())):  # fresh() deletes its case directories
        parser.error("--base must be a new or empty directory: the oracle deletes and recreates the case "
                     "directories it makes there, and nothing else")
    base.mkdir(parents=True, exist_ok=True)
    print(json.dumps({"codex_version": subprocess.run(["codex", "--version"], capture_output=True, text=True,
                                                      stdin=subprocess.DEVNULL, timeout=60).stdout.strip(),
                      "checker": None if adoption_status is None else "scripts/adoption_status.py of --repo"}))
    if args.mode == "parse":
        only = None if not args.cases else {int(item) for item in args.cases.split(",")}
        disagreements = parse_mode(base, adoption_status, only)
    elif args.mode == "matchers":
        disagreements = matcher_mode(base, adoption_status)
    else:
        disagreements = trust_mode(base, adoption_status)
    if adoption_status is not None:
        print(json.dumps({"disagreements": disagreements}))
    return 1 if disagreements else 0


if __name__ == "__main__":
    raise SystemExit(main())
