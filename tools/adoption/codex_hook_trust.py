#!/usr/bin/env python3
"""Trust named hooks of one Codex home the way Codex's own /hooks review persists a decision, and read the result back.

Codex runs a non-managed hook only while its current hash equals `[hooks.state."<key>"].trusted_hash`; a hook with no entry is
`untrusted` and one whose definition changed is `modified`, and both are skipped (openai/codex rust-v0.159.3, commit
01fc69f4026735edfdf6789820549727a4867b11: codex-rs/hooks/src/engine/discovery.rs hook_hash L775 and hook_trust_status L794-L815;
codex-rs/hooks/src/config_rules.rs hook_states_from_stack L15-L62 merges the state tables across config layers). `rtk init -g
--codex` registers rtk's PreToolUse hook but cannot trust it. The TUI persists a trust decision with config/batchWrite of the key
`hooks.state`, mergeStrategy upsert, `{"<key>": {"trusted_hash": <currentHash>}}` (codex-rs/tui/src/hooks_rpc.rs write_hook_trusts
L58-L91), where key and currentHash are what hooks/list reports. This tool sends that edit through `codex app-server`, for only the
hooks of the base user layer whose command equals one named with --command, never for any other hook, a managed hook or a project's.

  python3 tools/adoption/codex_hook_trust.py --command "rtk hook codex"            # dry run: each match, its status, its hash
  python3 tools/adoption/codex_hook_trust.py --command "rtk hook codex" --apply    # back up config.toml (0600), trust, read back
  python3 tools/adoption/codex_hook_trust.py --command "rtk hook codex" --check    # verify: exit 0 only while every match is trusted

Execution rules. Trusting the hook is what activates it, and an activated hook changes what Codex's execution rules see. Codex runs a
PreToolUse hook before the tool handler and replaces the call with the hook's `updatedInput` (codex-rs/core/src/tools/registry.rs
L603-L660, rust-v0.159.3 and rust-v0.160.0), and the handler's approval path matches execution rules against the command words of the
rewritten call (codex-rs/core/src/exec_policy.rs L316-L420). rtk's hook rewrites `git push` to `rtk git push` (and `cat f` to `rtk read f`,
`python3 -m pytest` to `rtk pytest`) and has no Codex rule source (rtk-ai/rtk v0.51.0 hooks/codex/README.md L14-L24,
src/hooks/permissions.rs L64-L72), so a `forbidden` or `prompt` rule on a command rtk rewrites no longer matches it. The rewrite space is not
finite (rtk strips env prefixes, global options, absolute paths and wrappers before it matches one anchored regex per tool), so no sample of
commands and no `rtk` twin of a rule can show that a rule is preserved. The tool decides from what rtk can route at all:
  - tools/adoption/rtk_rewrite_heads.json holds the command heads rtk 0.51.0 can rewrite, derived from rtk's source at the pin (the leading
    tokens of the RULES patterns in src/discover/rules.rs and of the builtin TOML filters in src/filters, the process and shell wrappers and the
    env prefix of src/discover/registry.rs), with line provenance (evidence/artifacts/token-stack-fresh-session-e2e-20261004/
    derive_rtk_rewrite_heads.py), and was checked against the real binary (check_rtk_rewrite_heads.py). It is valid for the one rtk version it
    names: `rtk --version` must report it, so a pin move must re-derive it (tests/test_codex_hook_trust.py compares it with the pin);
  - a `forbidden` or `prompt` rule is exposed when its first pattern token (every alternative, a path reduced to its basename) is such a head, or
    the first word of a `[hooks].transparent_prefixes` entry that `rtk config` reports; a twin does not change that. A rule on `hcom ...` or
    `uvx hcom ...` is not exposed (neither is a head), so #713's hcom-deny.rules passes; an `allow` rule on a head is only noted (its
    rewrite may need an approval);
  - the rules are read with Python's ast (Starlark's keyword calls of prefix_rule and host_executable are Python literals): every argument of
    both builtins must be a literal, because Codex evaluates argument expressions and a nested prefix_rule would register a rule this tool
    never sees; anything else is refused, not guessed;
  - the directory is listed as Codex's collect_policy_files does (codex-rs/core/src/exec_policy.rs L1121-L1170, rust-v0.160.0): only opening
    it may report a missing directory (no rules), every other error, also on an entry and for every entry's file type before its extension, is a
    failure; a symlink or another non-file is not loaded;
  - any step that cannot be done (a listing or read error, rules not readable as literals, no rtk, another rtk version, an unreadable `rtk
    config`, user-defined rtk TOML filters, which can add heads) is an exposure too: the review fails closed.
--apply refuses with exit 2 on an exposure before the app-server starts, so before any write, even for an already trusted hook; --check
exits 6 for a trusted hook beside one (the install plan's acceptance runs it, so a rule added after the grant is caught); --allow-exec-rules
accepts it, after the rtk forms of the rules are written and checked with `codex execpolicy check`. The review runs only when rule files exist,
and needs rtk (`rtk --version`, `rtk config`) only for a `forbidden` or `prompt` rule. Not seen: rules in a project's .codex/rules or a managed
layer, rtk TOML filters that a project trusts with `rtk trust`, and Starlark beyond Python's parser (refused).

A dry run makes no trust or config edit and no backup. It is not read-only: starting the app-server creates its own state files in
the Codex home (SQLite databases, an installation id, the bundled skills; measured on a scratch home, 2026-10-04).

The grant is a trust decision about a hook that sees every tool call it matches (rtk's sees each Bash command), so it belongs to
the host's owner: a plan row runs it only under a recorded decision (docs/decisions/2026-10-04-codex-rtk-hook-qualified.md). A
hook whose command changed is a different hook: this tool trusts the command it is told to, at its current definition, and a later
change of the hook (a moved group index changes the key) returns it to `untrusted` until the tool runs again.

--apply refuses while a codex process runs (as apply_codex_lane.py does), writes config.toml.bak.<UTC stamp> beside the config first
(never overwriting one), sends the edit with the user layer's version as expectedVersion (a changed file is refused) and then
asks hooks/list again. expectedVersion guards config.toml, not the file a hook is defined in, so the read-back does not search
for the command again: every hook that was named must still be listed under its key as a user-layer command hook, at the hash
it had, and `trusted`; a hook that vanished, moved or changed during the write, and a discovery error that was not there before
the write, are failures. It is idempotent: with every match already trusted it makes no edit.
--check verifies and nothing else (the install plan's acceptance runs it): it makes no edit and no backup, and takes no part in the
refusal beside a running codex, which only --apply has. Exit status: 0 done, nothing to do, or --check found every match trusted and
no exposure, 2 refused before any write (a running codex, or an execution-rule exposure without --allow-exec-rules), 3 a write or the
read-back failed, 4 no hook of the user layer has a named command (register it first), 5 --check found a named hook that is not
trusted (untrusted or modified), 6 --check found every named hook trusted beside an execution-rule exposure, 1 unexpected.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply_codex_lane as lane  # noqa: E402

HEADS_FILE = Path(__file__).with_name("rtk_rewrite_heads.json")
RESTRICTING = ("forbidden", "prompt")
DECISIONS = ("allow", "prompt", "forbidden")
PREFIX_RULE_KEYS = {"pattern", "decision", "justification", "match", "not_match"}
HOST_EXECUTABLE_KEYS = {"name", "paths"}
SHOWN = 8


class ReviewError(Exception):
    """A step of the rule review that could not be done; the review fails closed on it."""


@dataclass
class Rule:
    path: Path
    line: int
    pattern: list
    decision: str


class Review:
    """What the review of the user layer's execution rules found."""

    def __init__(self) -> None:
        self.files: list[Path] = []
        self.rules = 0
        self.restricting = 0
        self.version = ""
        self.exposed: list[str] = []
        self.notes: list[str] = []
        self.problems: list[str] = []

    @property
    def blocked(self) -> bool:
        return bool(self.exposed or self.problems)

    def lines(self, home: Path) -> list[str]:
        if not self.files:
            return [f"cannot check the execution rules: {problem}" for problem in self.problems]
        out = [f"execution rules in {home / 'rules'}: {', '.join(path.name for path in self.files)}; {self.rules} rule(s), {self.restricting} "
               f"forbidden or prompt" + (f"; checked against the commands {self.version} can rewrite" if self.version else "")]
        for label, items in (("exposed", self.exposed), ("cannot check", self.problems), ("note", self.notes)):
            out += [f"  {label}: {item}" for item in items[:SHOWN]]
            if len(items) > SHOWN:
                out.append(f"  {label}: and {len(items) - SHOWN} more")
        if not self.blocked and self.restricting:
            out.append(f"  no forbidden or prompt rule starts with a command {self.version} can rewrite")
        return out


def inventory(server, cwd: Path) -> tuple[list[dict], list[tuple[str, str]]]:
    """The hooks Codex loads for ``cwd`` (hooks/list), every config layer, and the discovery errors it reports for them as
    (path, message) pairs."""
    entries = server.request("hooks/list", {"cwds": [str(cwd)]}).get("data") or []
    hooks = [hook for entry in entries for hook in entry.get("hooks") or []]
    errors = [(error.get("path") or "", error.get("message") or "") for entry in entries for error in entry.get("errors") or []]
    return hooks, errors


def matches(hooks: list[dict], commands: set[str]) -> list[dict]:
    """The hooks this tool may trust: a command handler of the user layer, not managed, whose command is exactly one named."""
    chosen = [hook for hook in hooks if hook.get("handlerType") == "command" and hook.get("command") in commands
              and hook.get("source") == "user" and not hook.get("isManaged")]
    return sorted(chosen, key=lambda hook: hook.get("key") or "")


def read_back_problems(named: list[dict], listed: list[dict]) -> list[str]:
    """What the read-back finds wrong with the hooks that were named, each looked up by its key: it must still be listed, still a
    user-layer command hook, at the hash it had (a changed definition has another hash and a trust written for the old one no
    longer applies) and trusted."""
    by_key = {hook.get("key"): hook for hook in listed}
    problems = []
    for before in named:
        now = by_key.get(before.get("key"))
        if now is None:
            problems.append(f"{before.get('key')}: no longer listed")
        elif now.get("handlerType") != "command" or now.get("source") != "user" or now.get("isManaged"):
            problems.append(f"{before.get('key')}: no longer a user-layer command hook")
        elif now.get("currentHash") != before.get("currentHash"):
            problems.append(f"{before.get('key')}: changed during the write ({now.get('command')!r} is {now.get('trustStatus')})")
        elif now.get("trustStatus") != "trusted":
            problems.append(f"{before.get('key')}: still reports not trusted ({now.get('trustStatus')})")
    return problems


def rule_files(home: Path) -> list[Path]:
    """The user layer's execution-rule files, listed as Codex's collect_policy_files does (codex-rs/core/src/exec_policy.rs L1121-L1170,
    rust-v0.160.0). Only opening the directory may report it missing (no rules); an error from the open, the iteration or an entry's file type
    is raised (Codex fails the load on it as well), and the file type of every entry is asked before its extension is looked at. An entry
    counts when its extension is `rules` and its own file type, symlinks not followed, is a file, so a symlink is not loaded."""
    directory = home / "rules"
    try:
        entries = os.scandir(directory)
    except FileNotFoundError:
        return []
    found = []
    with entries:
        for entry in entries:
            is_file = entry.is_file(follow_symlinks=False)
            if is_file and Path(entry.name).suffix == ".rules":
                found.append(directory / entry.name)
    return sorted(found)


def literal(node: ast.expr, line: int, call: str, name: str):
    """One argument of a builtin as a Python literal. Codex evaluates argument expressions, so a nested call (`name = prefix_rule(...) or "git"`) can
    register a rule that nothing here would count: an argument that is not a literal is refused."""
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError) as error:
        raise ReviewError(f"line {line}: the {name} argument of {call}() is not a literal ({type(node).__name__} expression)") from error


def read_rules(path: Path) -> list[Rule]:
    """The prefix rules of one file. The files are Starlark (codex-rs/execpolicy/README.md); the keyword calls of prefix_rule and host_executable
    read as Python literals, and anything else (a statement that is not such a call, a positional or ** argument, an argument this tool does not
    know, a value that is not a literal) is refused rather than guessed."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    rules = []
    for node in tree.body:
        call = node.value if isinstance(node, ast.Expr) else None
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and not call.args and all(k.arg for k in call.keywords)):
            raise ReviewError(f"line {node.lineno}: not a keyword call of prefix_rule or host_executable")
        builtin = call.func.id
        known = {"prefix_rule": PREFIX_RULE_KEYS, "host_executable": HOST_EXECUTABLE_KEYS}.get(builtin)
        if known is None:
            raise ReviewError(f"line {node.lineno}: {builtin}() is not read by this tool")
        values = {}
        for keyword in call.keywords:
            if keyword.arg not in known:
                raise ReviewError(f"line {node.lineno}: {builtin}() has an argument this tool does not read ({keyword.arg})")
            values[keyword.arg] = literal(keyword.value, node.lineno, builtin, keyword.arg)
        if builtin == "host_executable":
            continue
        pattern = values.get("pattern")
        decision = values.get("decision", "allow")
        if not (isinstance(pattern, list) and pattern and all(
                isinstance(element, str) or (isinstance(element, list) and element and all(isinstance(t, str) for t in element))
                for element in pattern)):
            raise ReviewError(f"line {node.lineno}: pattern is not a list of tokens and lists of alternative tokens")
        if decision not in DECISIONS:
            raise ReviewError(f"line {node.lineno}: decision is not one of {', '.join(DECISIONS)}")
        rules.append(Rule(path, node.lineno, pattern, decision))
    return rules


def brief(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " ".join(lines[:2])[:240]


def invoke(command: list[str], runner) -> subprocess.CompletedProcess:
    try:
        return runner(command, env={**os.environ, "RTK_TELEMETRY_DISABLED": "1"}, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                      timeout=30, check=False)
    except (OSError, ValueError, subprocess.SubprocessError) as error:  # ValueError: output that is not text
        raise ReviewError(f"cannot run {command[0]}: {error}") from error


def load_heads() -> tuple[dict, list[tuple[re.Pattern, str]]]:
    """The fixture of the commands rtk can rewrite and its heads compiled (a literal head is matched as written)."""
    try:
        fixture = json.loads(HEADS_FILE.read_text(encoding="utf-8"))
        compiled = [(re.compile(entry["head"] if entry["regex"] else re.escape(entry["head"])), entry["from"][0]) for entry in fixture["heads"]]
    except (OSError, ValueError, KeyError, IndexError, TypeError, re.error) as error:
        raise ReviewError(f"cannot read {HEADS_FILE.name}: {error}") from error
    return fixture, compiled


def filter_heads(path: Path) -> list[tuple[re.Pattern, str]]:
    """The heads of the user-global TOML filters beside rtk's config (src/core/toml_filter.rs: `~/.config/rtk/filters.toml`; rtk applies one once it is
    trusted, which is assumed here): the word that each `match_command` starts with. A pattern that is not a plain anchored word (`^name\\b`) is a
    failure: its head cannot be read without a regex parser."""
    try:
        parsed = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError) as error:
        raise ReviewError(f"cannot read rtk's {path.name} ({error})") from error
    heads = []
    for name, definition in sorted((parsed.get("filters") or {}).items()):
        pattern = definition.get("match_command") if isinstance(definition, dict) else None
        if pattern is None:
            continue
        word = re.match(r"\^([A-Za-z0-9_.+-]+)(?:\\b|\\s|\$|\(|$)", pattern) if isinstance(pattern, str) else None
        if not word:
            raise ReviewError(f"rtk's {path.name} filter {name} has a match_command ({pattern!r}) that is not a plain anchored word, so its head is not read")
        heads.append((re.compile(re.escape(word.group(1)) + r"(?:\W\S*)?"), f"filter {name} in {path.name}"))
    return heads


def rtk_state(rtk: str | None, fixture: dict, runner) -> list[tuple[re.Pattern, str]]:
    """The version gate and rtk's own configuration: `rtk --version` must report the version the heads were derived for, the first word of each
    `[hooks].transparent_prefixes` entry of `rtk config` is a head, and so is the word each user-global TOML filter starts with."""
    rtk = rtk or shutil.which("rtk")
    if not rtk:
        raise ReviewError("no rtk executable on PATH (or --rtk): the rules cannot be checked against what rtk rewrites")
    done = invoke([rtk, "--version"], runner)
    reported = (done.stdout or "").strip()
    if done.returncode != 0 or reported != fixture["rtk_version_output"]:
        raise ReviewError(f"rtk reports {reported!r}, but the head set was derived for {fixture['rtk_version_output']!r}: re-derive "
                          f"{HEADS_FILE.name} (derive_rtk_rewrite_heads.py) for the pinned rtk, or accept with --allow-exec-rules")
    done = invoke([rtk, "config"], runner)
    first, _, body = (done.stdout or "").partition("\n")
    # `rtk config` prints `Config: <path>`, then the configuration as TOML, after `(default config, file not created)` when there is no file
    # (src/core/config.rs show_config, rtk v0.51.0).
    body = "\n".join(line for line in body.splitlines() if line.strip() != "(default config, file not created)")
    try:
        config = tomllib.loads(body)
        prefixes = config.get("hooks", {}).get("transparent_prefixes", [])
        if done.returncode != 0 or not first.startswith("Config: ") or not isinstance(prefixes, list) or not all(isinstance(p, str) for p in prefixes):
            raise ValueError("not the expected output")
    except (ValueError, AttributeError) as error:
        raise ReviewError(f"cannot read the configuration `rtk config` reports ({error}): {brief(done.stderr or done.stdout)}") from error
    extra = filter_heads(Path(first[len("Config: "):].strip()).parent / "filters.toml")
    for prefix in prefixes:
        words = shlex.split(prefix)
        if words:
            extra.append((re.compile(re.escape(words[0].rsplit("/", 1)[-1])), "[hooks].transparent_prefixes of the rtk config"))
    return extra


def head_of(token: str, compiled: list[tuple[re.Pattern, str]]) -> str | None:
    """The source of the head that ``token`` (a path reduced to its basename) matches, else None."""
    name = token.rsplit("/", 1)[-1]
    for pattern, source in compiled:
        if pattern.fullmatch(name):
            return source
    return None


def review_rules(home: Path, rtk: str | None, runner=None) -> Review:
    """Review the user layer's execution rules (see the module docstring); fails closed."""
    runner = runner or subprocess.run
    review = Review()
    try:
        review.files = rule_files(home)
    except OSError as error:
        review.problems.append(f"cannot list {home / 'rules'}: {error}")
        return review
    if not review.files:
        return review
    rules: list[Rule] = []
    for path in review.files:
        try:
            rules += read_rules(path)
        except (OSError, SyntaxError, ValueError, RecursionError, ReviewError) as error:
            review.problems.append(f"cannot read the rules of {path.name}: {error}")
    review.rules = len(rules)
    review.restricting = sum(rule.decision in RESTRICTING for rule in rules)
    if review.problems or not rules:
        return review
    try:
        fixture, compiled = load_heads()
        if review.restricting:
            compiled = compiled + rtk_state(rtk, fixture, runner)
            review.version = fixture["rtk_version_output"]
    except ReviewError as error:
        review.problems.append(str(error))
        return review
    for rule in rules:
        first = rule.pattern[0] if isinstance(rule.pattern[0], list) else [rule.pattern[0]]
        for token in first:
            source = head_of(token, compiled)
            if source is None:
                continue
            where = f"{rule.path.name}:{rule.line}: {rule.decision} rule {json.dumps(rule.pattern)} starts with `{token}`"
            if rule.decision in RESTRICTING:
                review.exposed.append(f"{where}, a command rtk can rewrite ({source}): a command the rule matches can be rewritten out of its "
                                      f"reach, and an `rtk` twin cannot be shown to cover every rewrite")
            else:
                review.notes.append(f"{where}, a command rtk can rewrite ({source}): its rewrite may need an approval")
            break
    return review


def describe(hook: dict) -> str:
    where = hook.get("matcher") or "(any)"
    return f"  {hook.get('key')}: {hook.get('eventName')} {where} {hook.get('command')!r} is {hook.get('trustStatus')}"


def backup_path(config: Path) -> Path:
    stamp = lane.utc_stamp()
    candidate = config.with_name(f"{config.name}.bak.{stamp}")
    suffix = 0
    while candidate.exists():
        suffix += 1
        candidate = config.with_name(f"{config.name}.bak.{stamp}.{suffix}")
    return candidate


def write_backup(config: Path) -> Path:
    target = backup_path(config)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(config.read_bytes())
    return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--command", action="append", required=True, metavar="COMMAND",
                        help="trust the user-layer hook whose command is exactly this (repeatable)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="write the trust (default: dry run)")
    mode.add_argument("--check", action="store_true",
                      help="verify only: exit 0 when every named hook is trusted at its current hash and no rule is exposed, "
                           "5 when a hook is not trusted, 6 when a rule is exposed")
    parser.add_argument("--codex-home", help="the Codex home (default: $CODEX_HOME, else ~/.codex)")
    parser.add_argument("--codex", help="the codex executable (default: codex on PATH)")
    parser.add_argument("--rtk", help="the rtk executable the rule review asks (default: rtk on PATH)")
    parser.add_argument("--cwd", help="the working directory hooks/list is asked for (default: the Codex home)")
    parser.add_argument("--codex-process-name", default="codex", help="the process name --apply refuses to run beside")
    parser.add_argument("--allow-exec-rules", action="store_true",
                        help="go on although the rewrite could bypass an execution rule, or the rules could not be checked")
    return parser


def run(args: argparse.Namespace) -> int:
    codex = args.codex or shutil.which("codex")
    if not codex:
        print("refused: no codex executable on PATH (or --codex)", file=sys.stderr)
        return 2
    home = Path(args.codex_home or os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    config = home / "config.toml"
    cwd = Path(args.cwd).expanduser() if args.cwd else home
    commands = set(args.command)
    # The rule review needs neither the app-server nor a write, so it comes first: a refusal leaves the Codex home as it was.
    review = review_rules(home, args.rtk)
    for line in review.lines(home):
        print(line)
    blocked = review.blocked and not args.allow_exec_rules
    if args.apply and blocked:
        print("refused: the rewrite could bypass the user layer's execution rules, or they could not be checked (above). Trusting "
              "`rtk hook codex` activates a hook that makes Codex run `rtk <command>` in place of each command rtk rewrites, and Codex "
              "matches execution rules against the command words after the rewrite (codex-rs/core/src/tools/registry.rs L603-L660, "
              "codex-rs/core/src/exec_policy.rs L316-L420). Write the rtk form of each exposed rule beside the plain one and check both "
              "with `codex execpolicy check`, then run again; --allow-exec-rules accepts the exposure", file=sys.stderr)
        return 2
    # Before the app-server starts: that child is itself a codex process.
    running = lane.codex_processes(args.codex_process_name) if args.apply else []
    backup = None
    try:
        with lane.AppServer(codex, lane.codex_env(home), cwd) as server:
            listed, errors_before = inventory(server, cwd)
            found = matches(listed, commands)
            if not found:
                print(f"no user-layer hook of {home} has a command named ({', '.join(sorted(commands))}): register it first, "
                      f"for rtk `rtk init -g --codex`", file=sys.stderr)
                return 4
            print(f"hooks named in {home}:")
            for hook in found:
                print(describe(hook))
            for path, message in errors_before:
                print(f"  note: hooks/list reports a discovery error before any write: {path}: {message}")
            todo = [hook for hook in found if hook.get("trustStatus") != "trusted"]
            if args.check:
                if todo:
                    print("not trusted: " + "; ".join(describe(hook).strip() for hook in todo), file=sys.stderr)
                    return 5
                if blocked:
                    print("not accepted: the hook is trusted beside an execution-rule exposure (above); fix the rules, or "
                          "--allow-exec-rules accepts it", file=sys.stderr)
                    return 6
                print("every named hook is trusted at its current hash")
                return 0
            if not todo:
                print("nothing to do: every named hook is trusted")
                return 0
            if not args.apply:
                print(f"dry run: {len(todo)} hook(s) would be trusted at their current hash through config/batchWrite "
                      f"(hooks.state, upsert); run with --apply (no codex process running) to do it")
                if blocked:
                    print("note: --apply would refuse until the exposure above is fixed or accepted with --allow-exec-rules")
                return 0
            if running:
                print(f"refused: {len(running)} codex processes running (pids {', '.join(running)})", file=sys.stderr)
                return 2
            if config.is_file():
                backup = write_backup(config)
                print(f"backup: {backup}")
            version, _ = server.user_layer()
            server.request("config/batchWrite", {
                "edits": [{"keyPath": "hooks.state", "mergeStrategy": "upsert",
                           "value": {hook["key"]: {"trusted_hash": hook["currentHash"]} for hook in todo}}],
                "expectedVersion": version})
            listed_after, errors_after = inventory(server, cwd)
    except (lane.Failed, lane.AppServerError) as error:
        print(f"failed: {error}" + (f"; the backup is {backup}" if backup else ""), file=sys.stderr)
        return 3
    problems = read_back_problems(found, listed_after)
    problems += [f"discovery error after the write: {path}: {message}" for path, message in errors_after
                 if (path, message) not in errors_before]
    if problems:
        print("failed: hooks/list after the write: " + "; ".join(problems) + (f"; the backup is {backup}" if backup else ""),
              file=sys.stderr)
        return 3
    print(f"trusted {len(todo)} hook(s) in {config}; read back from hooks/list by key and hash")
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
