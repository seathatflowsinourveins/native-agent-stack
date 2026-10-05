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
refusal beside a running codex, which only --apply has. Exit status: 0 done, nothing to do, or --check found every match trusted,
2 refused before any write, 3 a write or the read-back failed, 4 no hook of the user layer has a named command (register it first),
5 --check found a named hook that is not trusted (untrusted or modified), 1 unexpected.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply_codex_lane as lane  # noqa: E402


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
                      help="verify only: exit 0 when every named hook is trusted at its current hash, 5 when one is not")
    parser.add_argument("--codex-home", help="the Codex home (default: $CODEX_HOME, else ~/.codex)")
    parser.add_argument("--codex", help="the codex executable (default: codex on PATH)")
    parser.add_argument("--cwd", help="the working directory hooks/list is asked for (default: the Codex home)")
    parser.add_argument("--codex-process-name", default="codex", help="the process name --apply refuses to run beside")
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
                print("every named hook is trusted at its current hash")
                return 0
            if not todo:
                print("nothing to do: every named hook is trusted")
                return 0
            if not args.apply:
                print(f"dry run: {len(todo)} hook(s) would be trusted at their current hash through config/batchWrite "
                      f"(hooks.state, upsert); run with --apply (no codex process running) to do it")
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
