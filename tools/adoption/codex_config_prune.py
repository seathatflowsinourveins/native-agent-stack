#!/usr/bin/env python3
"""Drop the feature flags that Codex reports as removed from one Codex home's config.toml, through Codex's own config writer.

`codex features list` is the source of truth: a feature whose stage is `removed` is a key that does nothing (`plugin_hooks`,
`Stage::Removed` at openai/codex rust-v0.160.0, codex-rs/features/src/lib.rs L1474-L1479). A `[features]` entry for one is
deleted with `config/batchWrite` (value null, mergeStrategy replace, expectedVersion from config/read): the writer Codex's own
clients use and the one tools/adoption/apply_codex_lane.py uses, so nothing else in the file moves and a changed file is refused.
Only the base user layer's `[features]` table is read; a profile's table and every other key are left alone.

  python3 tools/adoption/codex_config_prune.py             # dry run: what would go, and why
  python3 tools/adoption/codex_config_prune.py --apply     # back up config.toml (mode 0600), delete, read back

--apply refuses while a codex process runs (as apply_codex_lane.py does), writes config.toml.bak.<UTC stamp> beside it first
(never overwriting one), and reads the result back from the writer. It is idempotent: with nothing stale it exits 0 and starts
no app-server. Exit status: 0 done or nothing to do, 2 refused before any write, 3 a write or read-back failed, 1 unexpected.
The decision and why a re-apply of a template never removes a key: docs/decisions/2026-10-04-claude-template-holds-out-token-lane-carriers.md.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply_codex_lane as lane  # noqa: E402

REMOVED_STAGE = "removed"


def parse_removed(listing: str) -> list[str]:
    """The names `codex features list` prints with the stage `removed`. A line is `<name> <stage words> <default>`: the stage is
    every word between the name and the trailing true or false ("under development" has two)."""
    names = []
    for line in listing.splitlines():
        words = line.split()
        if len(words) >= 3 and words[-1] in ("true", "false") and " ".join(words[1:-1]) == REMOVED_STAGE:
            names.append(words[0])
    return names


def removed_features(codex: str) -> list[str]:
    """The removed features of this Codex, asked in an empty temporary HOME and CODEX_HOME so that no host file is read."""
    with tempfile.TemporaryDirectory(prefix="codex-prune-") as scratch:
        env = {"PATH": os.environ.get("PATH", ""), "HOME": scratch, "CODEX_HOME": scratch}
        result = subprocess.run([codex, "features", "list"], env=env, cwd=scratch, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=60, check=False)
    if result.returncode != 0:
        raise lane.Failed(f"codex features list exited {result.returncode}: {lane.last_line(result.stderr)}")
    return parse_removed(result.stdout)


def stale_keys(config: dict, removed: list[str]) -> list[str]:
    """The names in the config's own [features] table that Codex reports as removed."""
    features = config.get("features")
    return sorted(name for name in features if name in removed) if isinstance(features, dict) else []


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
    parser.add_argument("--apply", action="store_true", help="delete the keys (default: dry run)")
    parser.add_argument("--codex-home", help="the Codex home (default: $CODEX_HOME, else ~/.codex)")
    parser.add_argument("--codex", help="the codex executable (default: codex on PATH)")
    parser.add_argument("--codex-process-name", default="codex", help="the process name --apply refuses to run beside")
    return parser


def run(args: argparse.Namespace) -> int:
    codex = args.codex or shutil.which("codex")
    if not codex:
        print("refused: no codex executable on PATH (or --codex)", file=sys.stderr)
        return 2
    home = Path(args.codex_home or os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    config = home / "config.toml"
    removed = removed_features(codex)
    if not config.is_file():
        print(f"nothing to do: {config} does not exist")
        return 0
    try:
        live = tomllib.loads(config.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        print(f"refused: {config} does not parse ({type(error).__name__})", file=sys.stderr)
        return 2
    stale = stale_keys(live, removed)
    if not stale:
        print(f"nothing to prune: no [features] key of {config} names a feature this Codex removed "
              f"(removed: {', '.join(removed) or 'none'})")
        return 0
    for name in stale:
        print(f"  [features] {name} = {live['features'][name]!r}: {name} is stage `{REMOVED_STAGE}` in `codex features list`")
    if not args.apply:
        print(f"dry run: {len(stale)} key(s) would be deleted from {config} through config/batchWrite; "
              "run with --apply (no codex process running) to do it")
        return 0
    running = lane.codex_processes(args.codex_process_name)
    if running:
        print(f"refused: {len(running)} codex processes running (pids {', '.join(running)})", file=sys.stderr)
        return 2
    backup = write_backup(config)
    print(f"backup: {backup}")
    try:
        with lane.AppServer(codex, lane.codex_env(home), home) as server:
            version, current = server.user_layer()
            todo = stale_keys(current, removed)
            if todo:
                server.batch_write([{"key": ["features", name], "value": None} for name in todo], version)
            _, after = server.user_layer()
    except (lane.Failed, lane.AppServerError) as error:
        print(f"failed: {error}; config.toml is as the writer left it, the backup is {backup}", file=sys.stderr)
        return 3
    left = stale_keys(after, removed)
    if left:
        print(f"failed: the writer still reports {', '.join(left)} after the delete; the backup is {backup}", file=sys.stderr)
        return 3
    print(f"pruned {', '.join(todo) if todo else 'nothing (another writer got there first)'} from {config}; read back from config/read")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except lane.Failed as error:
        print(f"failed: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
