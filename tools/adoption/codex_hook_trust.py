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

The grant is a trust decision about a hook that sees every tool call it matches (rtk's sees each Bash command), so it belongs to
the host's owner: a plan row runs it only under a recorded decision (docs/decisions/2026-10-04-codex-rtk-hook-qualified.md). A
hook whose command changed is a different hook: this tool trusts the command it is told to, at its current definition, and a later
change of the hook (a moved group index changes the key) returns it to `untrusted` until the tool runs again.

--apply refuses while a codex process runs (as apply_codex_lane.py does), writes config.toml.bak.<UTC stamp> beside the config first
(never overwriting one), sends the edit with the user layer's version as expectedVersion (a changed file is refused) and then
asks hooks/list again: every match must be `trusted`. It is idempotent: with every match already trusted it writes nothing.
Exit status: 0 done or nothing to do, 2 refused before any write, 3 a write or the read-back failed, 4 no hook of the user layer
has a named command (register it first), 1 unexpected.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply_codex_lane as lane  # noqa: E402


def listed_hooks(server, cwd: Path) -> list[dict]:
    """The hooks Codex loads for ``cwd`` (hooks/list), every config layer."""
    answer = server.request("hooks/list", {"cwds": [str(cwd)]})
    return [hook for entry in answer.get("data") or [] for hook in entry.get("hooks") or []]


def matches(hooks: list[dict], commands: set[str]) -> list[dict]:
    """The hooks this tool may trust: a command handler of the user layer, not managed, whose command is exactly one named."""
    chosen = [hook for hook in hooks if hook.get("handlerType") == "command" and hook.get("command") in commands
              and hook.get("source") == "user" and not hook.get("isManaged")]
    return sorted(chosen, key=lambda hook: hook.get("key") or "")


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
    parser.add_argument("--apply", action="store_true", help="write the trust (default: dry run)")
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
            found = matches(listed_hooks(server, cwd), commands)
            if not found:
                print(f"no user-layer hook of {home} has a command named ({', '.join(sorted(commands))}): register it first, "
                      f"for rtk `rtk init -g --codex`", file=sys.stderr)
                return 4
            print(f"hooks named in {home}:")
            for hook in found:
                print(describe(hook))
            todo = [hook for hook in found if hook.get("trustStatus") != "trusted"]
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
            left = [hook for hook in matches(listed_hooks(server, cwd), commands) if hook.get("trustStatus") != "trusted"]
    except (lane.Failed, lane.AppServerError) as error:
        print(f"failed: {error}" + (f"; the backup is {backup}" if backup else ""), file=sys.stderr)
        return 3
    if left:
        print("failed: hooks/list still reports not trusted after the write: " + "; ".join(describe(h).strip() for h in left)
              + (f"; the backup is {backup}" if backup else ""), file=sys.stderr)
        return 3
    print(f"trusted {len(todo)} hook(s) in {config}; read back from hooks/list")
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
