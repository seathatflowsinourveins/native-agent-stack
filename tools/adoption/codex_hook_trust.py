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
rewritten call (codex-rs/core/src/exec_policy.rs L316-L420). rtk's hook rewrites `git push` to `rtk git push` and has no Codex rule
source (rtk-ai/rtk v0.51.0 hooks/codex/README.md L14-L24, src/hooks/permissions.rs L64-L72), so a `forbidden` or `prompt` rule on
`git push` does not match the rewritten command; a rule on a command that rtk does not rewrite (`hcom kill`) is not affected.
When the user layer holds rule files, the tool reviews them with the upstream tools themselves, before anything else:
  - it lists <codex home>/rules/*.rules as Codex's collect_policy_files does (exec_policy.rs L1121-L1170, rust-v0.160.0): a missing
    directory is no rules, any other error is a failure, and a symlink or another non-file is not loaded;
  - it reads each file with ast (the files are Starlark; the `prefix_rule` calls are Python-compatible literals) for the commands the
    rules name, every spelling of each `pattern` and each `match` example, and adds REWRITE_SAMPLE, commands rtk 0.51.0 rewrites, so a
    rule broader than its own examples (`git`) is seen;
  - for every such command it asks `rtk hook check --agent codex` whether rtk rewrites it, and for each rewritten one `codex execpolicy
    check` (all the files together, as Codex merges them; the strictest decision wins: forbidden > prompt > allow) for the decision on the
    original and on the rewrite.
It reports an exposure only when the original is `forbidden` or `prompt` and the rewrite's decision is weaker (forbidden > prompt > no
match > allow). So hcom's rules (rtk rewrites none of them) and a rule with an `rtk ...` twin pass, and an allow rule whose rewrite
matches nothing is only noted (the rewrite may add a prompt). A step that could not be done is an exposure as well, so the review fails
closed: a directory listing or file read error, rules the tool cannot read as literals, no rtk or codex executable, an evaluator error
(Codex itself drops every file rule when one file does not parse, exec_policy.rs L645-L660). --apply refuses with exit 2 on an exposure
before the app-server starts, so before any write; --check exits 6 for a trusted hook beside one; --allow-exec-rules accepts it
(write the rtk forms of the rules or exclude the commands in rtk's exclude_commands first). The review needs no rtk or codex when
there is no rule file. Not seen: rules in a project's .codex/rules or a managed layer, and a rule on a rewritten command that
neither its heads, its examples nor the sample reach; write the rtk form beside the plain one and check both with `codex execpolicy
check`.

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
import itertools
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply_codex_lane as lane  # noqa: E402

# The commands `rtk hook check --agent codex` rewrote under upstream defaults at rtk v0.51.0 (e001f773f80b): 36 of the 55 measured in
# evidence/artifacts/token-stack-fresh-session-e2e-20261004/rtk-behaviour-probe.json (codex_hook_check, upstream_defaults). A sample of
# rtk's registry (96 patterns, src/discover/rules.rs), not the registry: rtk decides at run time whether each one is still rewritten.
REWRITE_SAMPLE = (
    "git push origin main", "git push --force origin main", "git commit -m x", "git add -A", "git checkout -- .", "git checkout -b topic",
    "git pull", "git stash", "git worktree add ../w", "gh pr merge 1", "gh pr create --fill", "gh api -X DELETE repos/o/r",
    "gh release create v1", "docker run --rm alpine sh", "docker exec c sh", "docker build .", "kubectl apply -f x.yaml",
    "helm install r chart", "pulumi up", "pip install x", "cargo install x", "make install", "curl -X POST http://x", "wget http://x",
    "rsync -a --delete a/ b/", "aws s3 rm s3://b/k", "iptables -F", "git status", "git log --oneline -3", "git diff", "ls -la",
    "cat a/x/util.py", "grep -rn needle .", "find . -name x", "pytest -q", "cargo test",
)
# Strictest first (codex-rs/execpolicy/README.md, "forbidden > prompt > allow"); None is no matching rule, which the approval policy decides.
RANK = {"forbidden": 3, "prompt": 2, None: 1, "allow": 0}
RESTRICTING = ("forbidden", "prompt")
MAX_SPELLINGS = 512
SHELL_OPERATORS = {"&&", "||", ";", "|", "&", ">", ">>", "<", "<<"}
SHOWN = 8


class ReviewError(Exception):
    """A step of the rule review that could not be done; the review fails closed on it."""


class Review:
    """What the review of the user layer's execution rules found."""

    def __init__(self) -> None:
        self.files: list[Path] = []
        self.rules = 0
        self.probed = 0
        self.rewritten = 0
        self.exposed: list[str] = []
        self.notes: list[str] = []
        self.problems: list[str] = []

    @property
    def blocked(self) -> bool:
        return bool(self.exposed or self.problems)

    def lines(self, home: Path) -> list[str]:
        if not self.files:
            return [f"cannot check the execution rules: {problem}" for problem in self.problems]
        out = [f"execution rules in {home / 'rules'}: {', '.join(path.name for path in self.files)}; {self.rules} rule(s); "
               f"{self.probed} commands probed, {self.rewritten} rewritten by `rtk hook check --agent codex`"]
        for label, items in (("exposed", self.exposed), ("cannot check", self.problems), ("note", self.notes)):
            out += [f"  {label}: {item}" for item in items[:SHOWN]]
            if len(items) > SHOWN:
                out.append(f"  {label}: and {len(items) - SHOWN} more")
        if not self.blocked and not self.notes:
            out.append("  every rule keeps its decision under the rewrite")
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
    rust-v0.160.0): a missing directory is no rules, any other error is raised (Codex fails the load on it as well), and an entry counts
    when its extension is `rules` and its own file type, symlinks not followed, is a file, so a symlink is not loaded."""
    directory = home / "rules"
    try:
        with os.scandir(directory) as entries:
            found = [directory / entry.name for entry in entries
                     if Path(entry.name).suffix == ".rules" and entry.is_file(follow_symlinks=False)]
    except FileNotFoundError:
        return []
    return sorted(found)


def concretize(pattern: list) -> list[tuple[str, ...]]:
    """Every command a prefix_rule pattern spells: an ordered list whose elements are a token or a list of alternative tokens."""
    choices = [element if isinstance(element, list) else [element] for element in pattern]
    total = 1
    for choice in choices:
        total *= len(choice)
    if total > MAX_SPELLINGS:
        raise ReviewError(f"a pattern spells {total} commands (more than {MAX_SPELLINGS})")
    return [tuple(spelling) for spelling in itertools.product(*choices)]


def literal(node: ast.expr | None, line: int, name: str):
    if node is None:
        raise ReviewError(f"line {line}: no {name}")
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError) as error:
        raise ReviewError(f"line {line}: {name} is not a literal ({error})") from error


def read_rules(path: Path) -> tuple[int, list[tuple[str, ...]], list[tuple[str, ...]]]:
    """One rules file: how many prefix_rule calls it holds, the commands their patterns spell and their `match` examples. The files are
    Starlark (codex-rs/execpolicy/README.md); the keyword calls of prefix_rule and host_executable read as Python literals, and anything
    else is refused rather than guessed."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    count, heads, examples = 0, [], []
    for node in tree.body:
        call = node.value if isinstance(node, ast.Expr) else None
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and not call.args and all(k.arg for k in call.keywords)):
            raise ReviewError(f"line {node.lineno}: not a keyword call of prefix_rule or host_executable")
        if call.func.id == "host_executable":
            continue
        if call.func.id != "prefix_rule":
            raise ReviewError(f"line {node.lineno}: {call.func.id}() is not read by this tool")
        keywords = {k.arg: k.value for k in call.keywords}
        pattern = literal(keywords.get("pattern"), node.lineno, "pattern")
        match = literal(keywords.get("match", ast.List(elts=[], ctx=ast.Load())), node.lineno, "match")
        if not (isinstance(pattern, list) and pattern and all(
                isinstance(element, str) or (isinstance(element, list) and element and all(isinstance(t, str) for t in element))
                for element in pattern)):
            raise ReviewError(f"line {node.lineno}: pattern is not a list of tokens and lists of alternative tokens")
        if not (isinstance(match, list) and all(isinstance(e, str) or (isinstance(e, list) and all(isinstance(t, str) for t in e))
                                                  for e in match)):
            raise ReviewError(f"line {node.lineno}: match is not a list of strings and token lists")
        count += 1
        heads += concretize(pattern)
        examples += [tuple(shlex.split(e)) if isinstance(e, str) else tuple(e) for e in match]
    return count, heads, examples


def brief(text: str) -> str:
    """The error line of a tool's output and, when it has one, the line that says why (codex prints `Error: ...` then `error: ...`)."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    first = next((line for line in lines if line.startswith("Error")), lines[0] if lines else "")
    cause = next((line for line in lines if line.startswith("error:")), "")
    return (first + (f" ({cause})" if cause else ""))[:300]


def invoke(command: list[str], runner, env: dict | None = None) -> subprocess.CompletedProcess:
    try:
        return runner(command, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, ValueError, subprocess.SubprocessError) as error:  # ValueError: output that is not text
        raise ReviewError(f"cannot run {command[0]}: {error}") from error


def rewrite_of(rtk: str, command: str, runner) -> str | None:
    """What `rtk hook check --agent codex` says the hook rewrites ``command`` to: the rewritten command on stdout with exit 0, or, for a
    command it leaves alone, `No rewrite for: ...` on stderr with exit 1 (rtk 0.51.0); None for the second. Anything else is a failure."""
    done = invoke([rtk, "hook", "check", "--agent", "codex", command], runner, {**os.environ, "RTK_TELEMETRY_DISABLED": "1"})
    out = (done.stdout or "").strip()
    if done.returncode == 0 and out:
        return out
    if done.returncode == 1 and not out and (done.stderr or "").lstrip().startswith("No rewrite for"):
        return None
    raise ReviewError(f"rtk hook check failed for {command!r} (exit {done.returncode}): {brief(done.stderr or out)}")


def decision_of(codex: str, env: dict, files: list[Path], argv: tuple[str, ...], runner) -> tuple[str | None, list[list[str]]]:
    """`codex execpolicy check` over all the files together: the strictest decision (None when no rule matches) and the matched prefixes."""
    command = [codex, "execpolicy", "check"]
    for path in files:
        command += ["--rules", str(path)]
    done = invoke([*command, "--", *argv], runner, env)
    if done.returncode != 0:
        raise ReviewError(f"codex execpolicy check failed for {shlex.join(argv)!r} (exit {done.returncode}): {brief(done.stderr or done.stdout)}")
    try:
        data = json.loads(done.stdout)
    except ValueError as error:
        raise ReviewError(f"codex execpolicy check printed no JSON for {shlex.join(argv)!r}: {error}") from error
    matched = data.get("matchedRules") if isinstance(data, dict) else None
    decision = data.get("decision") if isinstance(data, dict) else None
    if not isinstance(matched, list) or not (decision is None or decision in ("forbidden", "prompt", "allow")) \
            or (decision is None) != (not matched):
        raise ReviewError(f"codex execpolicy check answered unexpectedly for {shlex.join(argv)!r}: {brief(done.stdout)}")
    prefixes = [m.get("prefixRuleMatch", {}).get("matchedPrefix", []) for m in matched if isinstance(m, dict)]
    return decision, prefixes


def review_rules(home: Path, codex: str, rtk: str | None, runner=None) -> Review:
    """Review the user layer's execution rules against rtk's rewrite (see the module docstring); fails closed."""
    runner = runner or subprocess.run
    review = Review()
    try:
        review.files = rule_files(home)
    except OSError as error:
        review.problems.append(f"cannot list {home / 'rules'}: {error}")
        return review
    if not review.files:
        return review
    heads: list[tuple[str, ...]] = []
    examples: list[tuple[str, ...]] = []
    for path in review.files:
        try:
            count, spelled, shown = read_rules(path)
        except (OSError, SyntaxError, ValueError, RecursionError, ReviewError) as error:
            review.problems.append(f"cannot read the rules of {path.name}: {error}")
            continue
        review.rules += count
        heads += spelled
        examples += shown
    if review.problems or not review.rules:
        return review
    rtk = rtk or shutil.which("rtk")
    if not rtk:
        review.problems.append("no rtk executable on PATH (or --rtk): the rules cannot be compared with the rewrite")
        return review
    # `codex execpolicy check` creates <CODEX_HOME>/tmp/arg0 (measured, codex-cli 0.159.3), so it runs with a throwaway home: the
    # review writes nothing into the Codex home it reviews. The rules are given to it by path, so the home does not change the answer.
    try:
        with tempfile.TemporaryDirectory(prefix="codex-hook-trust-") as scratch:
            settings = lane.codex_env(Path(scratch))
            for argv in dict.fromkeys([*(tuple(shlex.split(command)) for command in REWRITE_SAMPLE), *heads, *examples]):
                review.probed += 1
                rewritten = rewrite_of(rtk, shlex.join(argv), runner)
                if rewritten is None:
                    continue
                review.rewritten += 1
                try:
                    after = tuple(shlex.split(rewritten))
                except ValueError as error:
                    raise ReviewError(f"rtk rewrites {shlex.join(argv)!r} to {rewritten!r}, which does not split into words ({error})") from error
                if SHELL_OPERATORS & set(after):
                    raise ReviewError(f"rtk rewrites {shlex.join(argv)!r} to a compound command ({rewritten!r}), which is not compared")
                before_decision, before_prefixes = decision_of(codex, settings, review.files, argv, runner)
                if before_decision is None:
                    continue
                after_decision, _ = decision_of(codex, settings, review.files, after, runner)
                matched = shlex.join(before_prefixes[0]) if before_prefixes and before_prefixes[0] else "?"
                where = f"`{shlex.join(argv)}` is {before_decision} ({matched})"
                if before_decision in RESTRICTING and RANK[after_decision] < RANK[before_decision]:
                    review.exposed.append(f"{where}, its rewrite `{rewritten}` is {after_decision or 'matched by no rule'}")
                elif before_decision == "allow" and after_decision is None:
                    review.notes.append(f"{where}, its rewrite `{rewritten}` is matched by no rule (it may need an approval)")
    except (ReviewError, OSError) as error:
        review.problems.append(str(error))
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
                        help="go on although the rewrite would bypass an execution rule, or the rules could not be checked")
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
    review = review_rules(home, codex, args.rtk)
    for line in review.lines(home):
        print(line)
    blocked = review.blocked and not args.allow_exec_rules
    if args.apply and blocked:
        print("refused: the rewrite would bypass the user layer's execution rules, or they could not be checked (above). Trusting "
              "`rtk hook codex` activates a hook that makes Codex run `rtk <command>` in place of each command rtk rewrites, and Codex "
              "matches execution rules against the command words after the rewrite (codex-rs/core/src/tools/registry.rs L603-L660, "
              "codex-rs/core/src/exec_policy.rs L316-L420). Write the rtk form of each exposed rule beside the plain one and check both "
              "with `codex execpolicy check`, or exclude those commands in rtk's exclude_commands, then run again; "
              "--allow-exec-rules accepts the exposure", file=sys.stderr)
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
