#!/usr/bin/env python3
r"""Trust named hooks of one Codex home the way Codex's own /hooks review persists a decision, and read the result back.

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
src/hooks/permissions.rs L64-L72), so a `forbidden` or `prompt` rule on a command rtk rewrites no longer matches it. No review of an
arbitrary rule file can be complete: three GPT reads of an analysing version of this tool (heads derived from rtk's source, then probes of
rewritten commands) each found a bypass, among them a raw CR that Codex's Starlark lexer drops inside a string and Python's reader turns
into a newline, rules that Codex evaluates against the whole shell argv when it cannot split an assignment-prefixed script, filter patterns,
PHP tool spellings and Unicode word boundaries. This tool therefore parses nothing. It decides, before anything is written, from the bytes of
each rule file in <codex home>/rules:
  - a file is accepted when its sha256 is on the reviewed list, tools/adoption/exec_rules_reviewed.json: an entry is the review of one exact
    file (today #713's hcom-deny.rules: every rule is a prefix rule on `hcom ...` or `uvx ...`, which rtk 0.51.0 cannot route, from its source
    and against the real binary: evidence/artifacts/token-stack-fresh-session-e2e-20261004/), for one rtk version and its default hook
    configuration, so for such a file `rtk --version` must report the entry's version, `rtk config` must show `transparent_prefixes = []`,
    `rtk trust --list` must say `No trusted filters.` (a trusted project or global TOML filter can make rtk rewrite any command: measured with
    rtk 0.51.0, a trusted project filter makes the hook rewrite `hcom kill luna`), RTK_TRUST_PROJECT_FILTERS must be unset (with a CI variable it
    trusts every project filters file without a store entry) and the user-global TOML filters file beside rtk's config must hold no filter (a pin
    move of rtk re-reviews the list: a test compares the entries with the pin);
  - a file is accepted when it holds nothing but allow rules in Codex's own format, byte for byte: lines `prefix_rule(pattern=["a", "b"],
    decision="allow")` whose tokens are printable ASCII without a quote or a backslash (codex-rs/execpolicy/src/amend.rs, which writes
    default.rules), comment lines of printable ASCII without a backslash and empty lines (hcom's own hcom.rules begins with one comment line,
    src/hooks/codex.rs build_codex_rules); an allow rule that a rewrite stops matching only loses its approval, but one that contains the letters
    `rtk` anywhere is not accepted: the hook's rewrite inserts that word, so such a rule matches the rewritten command and not the original, which
    widens an approval (codex-cli 0.159.3 `execpolicy check`: `["rtk"]` allows `rtk git push origin main` and gives no decision for `git push origin
    main`; and 705g: Codex cannot split an assignment-prefixed script, evaluates it as ONE token of the shell argv, and the hook inserts rtk inside it,
    so `["/bin/bash", "-lc", "FOO=1 rtk git push origin main"]` allows the rewritten script and not the original); a language this small reads the
    same in every parser (705g checked all 93 admitted token characters against Codex's Starlark);
  - any other file (a restriction nobody reviewed against rtk's rewrite, a CR, a non-ASCII byte, a backslash outside a token) is an exposure: --apply
    refuses with exit 2 before the app-server starts, so before any write, even for an already trusted hook; --check exits 6 for a trusted
    hook beside one (the install plan's acceptance runs it, so a rule file added or edited after the grant is caught); --allow-exec-rules
    accepts it, after the rtk form of each rule is written beside the plain one and both are checked with `codex execpolicy check`;
  - the directory is listed as Codex's collect_policy_files does (codex-rs/core/src/exec_policy.rs L1121-L1170, rust-v0.160.0): only opening
    it may report a missing directory (no rules), every other error, also on an entry, is a failure; the type of every entry is asked
    before its extension, from its own lstat, which fails for an entry that vanished (Python's DirEntry.is_file would say False; Codex's
    file_type() propagates the error); a symlink or another non-file is not loaded. Any step that cannot be done is an exposure as well.
With no rule file nothing runs; rtk is run (`rtk --version`, `rtk config`, `rtk trust --list`) only for a file on the reviewed list. Not seen: rules
in a project's .codex/rules or a managed layer, and the environment Codex itself runs the hook in (RTK_TRUST_PROJECT_FILTERS is checked in this tool's own).

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
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply_codex_lane as lane  # noqa: E402

REVIEWED_FILE = Path(__file__).with_name("exec_rules_reviewed.json")
# Codex's own allow rule, as amend.rs writes it: tokens of printable ASCII without `"` (0x22) and `\` (0x5C), so there is nothing to unescape or decode.
TOKEN = r'"[ !#-\[\]-~]+"'
ALLOW_LINE = re.compile(rf'prefix_rule\(pattern=\[{TOKEN}(?:, {TOKEN})*\], decision="allow"\)')
COMMENT_LINE = re.compile(r"#[ -\[\]-~]*")  # printable ASCII except a backslash: a comment that no parser can continue onto the next line
REWRITE_WORD = "rtk"  # the word rtk's hook inserts, as a token or inside a shell-script token (705g); every rewritten command contains it
SCHEMA_LINE = re.compile(r"schema_version\s*=\s*\d+")
NO_TRUSTED_FILTERS = "No trusted filters."  # what `rtk trust --list` prints for an empty trust store (src/hooks/trust.rs run_trust, rtk 0.51.0)
TRUST_ENV = "RTK_TRUST_PROJECT_FILTERS"  # with a CI variable, rtk trusts every project .rtk/filters.toml without a store entry (src/hooks/trust.rs L106-L116)
SHOWN = 8


class ReviewError(Exception):
    """A step of the rule review that could not be done; the review fails closed on it."""


class Review:
    """What the review of the user layer's execution rules found."""

    def __init__(self) -> None:
        self.files: list[Path] = []
        self.reviewed: list[str] = []
        self.allow_only: list[str] = []
        self.exposed: list[str] = []
        self.problems: list[str] = []

    @property
    def blocked(self) -> bool:
        return bool(self.exposed or self.problems)

    def lines(self, home: Path) -> list[str]:
        if not self.files:
            return [f"cannot check the execution rules: {problem}" for problem in self.problems]
        out = [f"execution rules in {home / 'rules'}: {', '.join(path.name for path in self.files)}; {len(self.reviewed)} on the reviewed list, "
               f"{len(self.allow_only)} Codex allow-only, {len(self.exposed)} not accepted"]
        for label, items in (("exposed", self.exposed), ("cannot check", self.problems)):
            out += [f"  {label}: {item}" for item in items[:SHOWN]]
            if len(items) > SHOWN:
                out.append(f"  {label}: and {len(items) - SHOWN} more")
        if not self.blocked:
            out.append("  every rule file is accepted")
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
    rust-v0.160.0). Only opening the directory may report it missing (no rules); an error from the open, the iteration or an entry's file type is
    raised (Codex fails the load on it as well). The type of every entry is asked before its extension, from its own lstat (symlinks not followed),
    which raises for an entry that vanished: DirEntry.is_file() would swallow that and answer False, where Codex's file_type() propagates it. An
    entry counts when its extension is `rules` and it is a regular file, so a symlink is not loaded."""
    directory = home / "rules"
    try:
        entries = os.scandir(directory)
    except FileNotFoundError:
        return []
    found = []
    with entries:
        for entry in entries:
            regular = stat.S_ISREG(entry.stat(follow_symlinks=False).st_mode)
            if regular and Path(entry.name).suffix == ".rules":
                found.append(directory / entry.name)
    return sorted(found)


def is_allow_only(data: bytes) -> bool:
    """Whether the whole file holds nothing but allow rules in Codex's own format (amend.rs): every line is `prefix_rule(pattern=["a", "b"],
    decision="allow")` with tokens of printable ASCII without a quote or a backslash and without the letters `rtk` anywhere (an allow rule that holds the word the
    hook's rewrite inserts, as a token or inside a shell-script token, matches the rewritten command and not the original), a comment of printable ASCII without a
    backslash, or empty; lines are ended by a newline; no CR, no tab, no non-ASCII byte. An empty file holds no rule."""
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        return False
    return all(line == "" or (ALLOW_LINE.fullmatch(line) and REWRITE_WORD not in line) or COMMENT_LINE.fullmatch(line) for line in text.split("\n"))


def load_reviewed() -> dict[str, dict]:
    """The reviewed list by sha256: one entry is the review of one exact rule file for one rtk version."""
    try:
        listed = json.loads(REVIEWED_FILE.read_text(encoding="utf-8"))
        entries = {entry["sha256"]: entry for entry in listed["entries"]}
        for entry in entries.values():
            if not (re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) and entry["reviewed_for"]["rtk_version_output"].startswith("rtk ")):
                raise ValueError("an entry is malformed")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        raise ReviewError(f"cannot read {REVIEWED_FILE.name}: {error}") from error
    return entries


def brief(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " ".join(lines[:2])[:240]


def invoke(command: list[str], runner) -> subprocess.CompletedProcess:
    try:
        return runner(command, env={**os.environ, "RTK_TELEMETRY_DISABLED": "1"}, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                      timeout=30, check=False)
    except (OSError, ValueError, subprocess.SubprocessError) as error:  # ValueError: output that is not text
        raise ReviewError(f"cannot run {command[0]}: {error}") from error


def rtk_conditions(rtk: str | None, entries: list[dict], runner) -> list[str]:
    """Why the reviewed files do not apply on this host, empty when they do. A review covers one rtk version and its default hook configuration:
    `rtk --version` must report that version, `rtk config` must show `transparent_prefixes = []` (a configured prefix makes rtk rewrite the command after
    it), `rtk trust --list` must print exactly `No trusted filters.` (rtk applies a project or global TOML filter only while it is trusted, and the store is
    global, so a filter trusted in any project shows there; a filter's match_command can make rtk rewrite any command), RTK_TRUST_PROJECT_FILTERS must not be
    set in this environment (with a CI variable rtk trusts project filters without a store entry, which the list does not show), and the user-global TOML
    filters file beside rtk's config (src/core/toml_filter.rs) must hold nothing but comments and a schema_version line. Output is compared whole, not parsed."""
    rtk = rtk or shutil.which("rtk")
    if not rtk:
        raise ReviewError("no rtk executable on PATH (or --rtk): a reviewed rule file applies to one rtk version")
    reasons = []
    done = invoke([rtk, "--version"], runner)
    reported = (done.stdout or "").strip()
    reviewed = sorted({entry["reviewed_for"]["rtk_version_output"] for entry in entries})
    if done.returncode != 0 or reported not in reviewed:
        reasons.append(f"rtk reports {reported!r}, but the reviewed rule file was reviewed for {', '.join(reviewed)}: re-review it for this rtk "
                       f"(a pin move re-reviews {REVIEWED_FILE.name}), or accept with --allow-exec-rules")
    done = invoke([rtk, "config"], runner)
    first, _, body = (done.stdout or "").partition("\n")
    if done.returncode != 0 or not first.startswith("Config: "):
        raise ReviewError(f"cannot read the configuration `rtk config` reports: {brief(done.stderr or done.stdout)}")
    if not re.search(r"^transparent_prefixes = \[\]$", body, re.M):
        reasons.append("rtk's [hooks].transparent_prefixes is not empty, or `rtk config` does not say it is: rtk rewrites the command after a configured prefix")
    done = invoke([rtk, "trust", "--list"], runner)
    if done.returncode != 0 or (done.stdout or "").strip() != NO_TRUSTED_FILTERS:
        reasons.append("rtk trusts TOML filter files (`rtk trust --list` does not say `No trusted filters.`, or failed): a trusted project or global filter can make "
                       "rtk rewrite any command, `hcom ...` included")
    if TRUST_ENV in os.environ:
        reasons.append(f"{TRUST_ENV} is set: with a CI variable rtk trusts every project filters file without a store entry")
    filters = Path(first[len("Config: "):].strip()).parent / "filters.toml"
    if filters.exists():
        try:
            text = filters.read_text(encoding="utf-8")
        except (OSError, ValueError) as error:
            raise ReviewError(f"cannot read rtk's {filters.name} ({error})") from error
        extra = [line for line in (re.sub(r"#.*$", "", row).strip() for row in text.splitlines()) if line and not SCHEMA_LINE.fullmatch(line)]
        if extra:
            reasons.append(f"rtk has user TOML filters ({filters.name} holds more than comments and schema_version): a filter's match_command can make rtk "
                           f"rewrite any command")
    return reasons


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
    try:
        reviewed = load_reviewed()
    except ReviewError as error:
        review.problems.append(str(error))
        reviewed = {}
    applied = []
    for path in review.files:
        try:
            data = path.read_bytes()
        except OSError as error:
            review.problems.append(f"cannot read {path.name}: {error}")
            continue
        digest = hashlib.sha256(data).hexdigest()
        if digest in reviewed:
            review.reviewed.append(path.name)
            applied.append(reviewed[digest])
        elif is_allow_only(data):
            review.allow_only.append(path.name)
        else:
            review.exposed.append(f"{path.name} (sha256 {digest[:12]}) is not on the reviewed list ({REVIEWED_FILE.name}) and is not Codex's own allow-only "
                                  f"format (allow rules without an `rtk` token): rtk can rewrite a command out of the reach of a restricting rule, or into the reach of "
                                  f"an allow rule that names rtk, and no review of an arbitrary rule file is complete")
    if applied:
        try:
            review.exposed += [f"{', '.join(review.reviewed)}: {reason}" for reason in rtk_conditions(rtk, applied, runner)]
        except ReviewError as error:
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
                      help="verify only: exit 0 when every named hook is trusted at its current hash and every rule file is accepted, "
                           "5 when a hook is not trusted, 6 when a rule file is not accepted")
    parser.add_argument("--codex-home", help="the Codex home (default: $CODEX_HOME, else ~/.codex)")
    parser.add_argument("--codex", help="the codex executable (default: codex on PATH)")
    parser.add_argument("--rtk", help="the rtk executable the review asks for a reviewed rule file (default: rtk on PATH)")
    parser.add_argument("--cwd", help="the working directory hooks/list is asked for (default: the Codex home)")
    parser.add_argument("--codex-process-name", default="codex", help="the process name --apply refuses to run beside")
    parser.add_argument("--allow-exec-rules", action="store_true",
                        help="go on although a rule file is not on the reviewed list, or the rules could not be checked")
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
        print("refused: a rule file of the user layer is not accepted, or the rules could not be checked (above). Trusting `rtk hook codex` activates a hook "
              "that makes Codex run `rtk <command>` in place of each command rtk rewrites, and Codex matches execution rules against the command words "
              "after the rewrite (codex-rs/core/src/tools/registry.rs L603-L660, codex-rs/core/src/exec_policy.rs L316-L420). Write the rtk form of each "
              "restricting rule beside the plain one and check both with `codex execpolicy check`, then run again; --allow-exec-rules accepts the "
              "exposure (adding a reviewed file to tools/adoption/exec_rules_reviewed.json is a repository change with its evidence)", file=sys.stderr)
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
