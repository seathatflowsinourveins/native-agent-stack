#!/usr/bin/env python3
"""Make a Codex home meet tools/adoption/apply_codex_lane.py's configuration preconditions. Stdlib only.

apply_codex_lane.py refuses a Codex home without config.toml and one whose features.daemon_auto_start is not false
(its Plan.preconditions); adoption/bootstrap-linux.sh --configure-full-profile runs this first, in its codex-lane step,
and passes the lane the host value file's HOST_PATH itself. Two cases:

  no config.toml   the user config tools/adoption/render_config.py rendered for this host (adoption/templates/
                   codex.config.template.toml, the user-level ~/.codex/config.toml of adoption/bootstrap.md step 4),
                   without the source host's trust state: every [projects."..."] table (trust_level grants) and the
                   [hooks.state] tables (trusted_hash hook approvals), the two sections step 4's trust-state warning
                   says were never reviewed on this machine, with the comment lines directly above each. Codex asks
                   about both on this host instead. The text is cut, then checked: parsed, it must equal the parsed
                   render minus exactly those tables, keep features.daemon_auto_start = false, and set
                   shell_environment_policy.set.PATH under this run's --eco-root, or nothing is written. Written
                   create-only (a temporary file linked into place, so an existing name is never replaced), mode
                   0600, in a Codex home made 0700 when this run creates it.
  config.toml      never rewritten by this tool. When features.daemon_auto_start is not false, it is backed up beside
                   itself (<name>.bak.<UTC stamp>, never over an earlier backup) and set through Codex's own config
                   writer, `codex features disable daemon_auto_start` (codex-rs/cli/src/main.rs
                   disable_feature_in_config, ConfigEditsBuilder, at rust-v0.157.1; recipes/README.md, codex row),
                   then read back: that key false and every other key as it was. Like apply_codex_lane.py --apply, it
                   refuses while a process named codex runs (--codex-process-name), since a running Codex writes the
                   same file. A symlink or a non-regular file is refused rather than written through. The backup is
                   the only undo: apply_codex_lane.py --rollback does not cover this key.

The Codex home is --codex-home, else $CODEX_HOME, else ~/.codex, as apply_codex_lane.py resolves it. --dry-run
reports what a real run would do and writes nothing.

Exit status: 0 written, set or already in place; 3 refused (nothing written); 2 usage error; 1 unexpected error.
"""

from __future__ import annotations

import argparse
import copy
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parent))
# Reused, not rewritten: the lane's own key helpers and create-only write, and the settings merge's backup.
import apply_claude_settings as file_io  # noqa: E402
import apply_codex_lane as lane  # noqa: E402

DAEMON_KEY = ["features", "daemon_auto_start"]
PATH_KEY = ["shell_environment_policy", "set", "PATH"]
CODEX_TIMEOUT_SECONDS = 60
EXIT_USAGE, EXIT_REFUSED = 2, 3


class Refused(ValueError):
    """Nothing is written (exit 3)."""


def daemon_disabled(config: dict) -> bool:
    """features.daemon_auto_start is the boolean false (a 0 would compare equal to False, and Codex rejects it)."""
    present, value = lane.get_path(config, DAEMON_KEY)
    return present and value is False


def header_key(line: str) -> list[str] | None:
    """The key path of a table header line ([a."b".c] or [[a.b]]), read by tomllib itself; None for any other line."""
    if not line.lstrip().startswith("["):
        return None
    try:
        node = tomllib.loads(line)
    except tomllib.TOMLDecodeError:
        return None  # an array value's line, not a header
    path = []
    while isinstance(node, (dict, list)) and node:
        if isinstance(node, list):
            node = node[-1]
            continue
        if len(node) != 1:
            return None
        key, node = next(iter(node.items()))
        path.append(key)
    return path or None


def trust_table(path: list[str]) -> bool:
    """[projects.*] trust grants and [hooks.state] / [hooks.state.*] hook approvals."""
    return path[:1] == ["projects"] or path[:2] == ["hooks", "state"]


def without_trust_state(text: str) -> str:
    """text without the trust tables and the comment lines directly above each. A table runs from its header to the
    comment block directly above the next header, so a kept table's own comments stay with it."""
    lines = text.splitlines(keepends=True)
    headers = [(index, key) for index, key in ((i, header_key(line)) for i, line in enumerate(lines)) if key]
    starts = []
    for index, _ in headers:
        start = index
        while start > 0 and lines[start - 1].lstrip().startswith("#"):
            start -= 1
        starts.append(start)
    dropped = set()
    for number, (_, key) in enumerate(headers):
        if trust_table(key):
            end = starts[number + 1] if number + 1 < len(headers) else len(lines)
            dropped.update(range(starts[number], end))
    kept = "".join(line for index, line in enumerate(lines) if index not in dropped)
    return kept.rstrip("\n") + "\n"


def expected_without_trust(config: dict) -> dict:
    expected = copy.deepcopy(config)
    expected.pop("projects", None)
    hooks = expected.get("hooks")
    if isinstance(hooks, dict):
        hooks.pop("state", None)
        if not hooks:
            expected.pop("hooks")
    return expected


def fresh_config(rendered: str, eco_root: str) -> tuple[str, int, int]:
    """(text to write, trust grants left out, hook approvals left out) for a Codex home without config.toml."""
    try:
        source = tomllib.loads(rendered)
    except tomllib.TOMLDecodeError as error:
        raise Refused(f"the rendered codex.config.toml does not parse: {error}") from None
    grants = len(source.get("projects") or {})
    approvals = len((source.get("hooks") or {}).get("state") or {})
    body = without_trust_state(rendered)
    try:
        result = tomllib.loads(body)
    except tomllib.TOMLDecodeError as error:
        raise Refused(f"the render without its trust state does not parse ({error}); nothing written") from None
    if result != expected_without_trust(source):
        raise Refused("leaving out the trust state would change more than the [projects] and [hooks.state] tables; "
                      "nothing written")
    if not daemon_disabled(result):
        raise Refused("the rendered codex.config.toml does not set features.daemon_auto_start = false")
    present, path = lane.get_path(result, PATH_KEY)
    first = path.split(":", 1)[0] if present and isinstance(path, str) else ""
    if not first or os.path.realpath(first) != os.path.realpath(os.path.join(eco_root, "bin")):
        raise Refused(f"the rendered shell_environment_policy.set.PATH does not start with {eco_root}/bin: the host "
                      "value file's ECO_ROOT is not this run's ecosystem root (ECO_INSTALL_ROOT); make them agree")
    note = ("# Written by adoption/bootstrap-linux.sh --configure-full-profile (tools/adoption/codex_home.py) from\n"
            "# adoption/templates/codex.config.template.toml as tools/adoption/render_config.py rendered it for this\n"
            f"# host, without the source host's trust state: {grants} [projects] trust grant(s) and {approvals} "
            "[hooks.state] hook\n# approval(s) were left out, so Codex asks about them here (adoption/bootstrap.md, "
            "step 4).\n")
    return note + body, grants, approvals


def install_fresh(codex_home: Path, config: Path, rendered: str, eco_root: str, dry_run: bool) -> int:
    text, grants, approvals = fresh_config(rendered, eco_root)
    if os.path.lexists(codex_home) and not codex_home.is_dir():
        raise Refused(f"{codex_home} exists and is not a directory")
    left_out = f"{grants} [projects] trust grant(s) and {approvals} [hooks.state] approval(s) left out"
    if dry_run:
        print(f"{config}: absent; DRY RUN, would write the rendered user config ({left_out}, "
              f"sha256 {lane.sha256_bytes(text.encode('utf-8'))[:12]}), mode 0600; nothing written")
        return 0
    if not codex_home.is_dir():
        codex_home.mkdir(mode=0o700, parents=True)
        os.chmod(codex_home, 0o700)
    try:
        lane.atomic_write(config, text.encode("utf-8"), 0o600, None, create_only=True)
    except FileExistsError:
        raise Refused(f"{config} appeared since it was checked; left as it is") from None
    print(f"{config}: written from the rendered user config ({left_out}), mode 0600")
    return 0


def read_config(config: Path) -> dict:
    try:
        return tomllib.loads(config.read_bytes().decode("utf-8"))
    except OSError as error:  # a dangling symlink, a directory, an unreadable file
        raise Refused(f"{config} cannot be read ({error.strerror or error}); fix it first") from None
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise Refused(f"{config} is not valid UTF-8 TOML ({error}); fix it first") from None


def disable_daemon(codex_home: Path, config: Path, codex: str | None, dry_run: bool, process_name: str) -> int:
    before = read_config(config)
    if daemon_disabled(before):
        print(f"{config}: kept; features.daemon_auto_start is already false")
        return 0
    if config.is_symlink() or not config.is_file():
        raise Refused(f"{config} is a symlink or not a regular file, so it is not written through; set "
                      "features.daemon_auto_start = false there yourself (codex features disable daemon_auto_start)")
    running = lane.codex_processes(process_name)
    if dry_run:
        print(f"{config}: kept; DRY RUN, would back it up and run `codex features disable daemon_auto_start`"
              + (f" once no {process_name} process runs ({len(running)} now)" if running else ""))
        return 0
    if running:
        raise Refused(f"{len(running)} {process_name} process(es) running (pids {', '.join(running)}); a running "
                      "Codex writes the same config.toml, so stop them, then run again")
    if not codex:
        raise Refused("no codex executable to set features.daemon_auto_start with (pass --codex)")
    backup = file_io.write_backup(config)
    result = subprocess.run([codex, "features", "disable", "daemon_auto_start"], env=lane.codex_env(codex_home),
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=CODEX_TIMEOUT_SECONDS,
                            check=False)
    if result.returncode != 0:
        raise Refused(f"`codex features disable daemon_auto_start` exited {result.returncode}: "
                      f"{lane.last_line(result.stderr) or lane.last_line(result.stdout)} (backup {backup})")
    after = read_config(config)
    if not daemon_disabled(after):
        raise Refused(f"read-back: features.daemon_auto_start is still not false in {config} (backup {backup})")
    if lane.without_owned(before, [DAEMON_KEY]) != lane.without_owned(after, [DAEMON_KEY]):
        raise Refused(f"read-back: keys besides features.daemon_auto_start changed in {config}; restore {backup}")
    print(f"{config}: features.daemon_auto_start set to false by `codex features disable daemon_auto_start` "
          f"(backup {backup})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rendered", required=True, type=Path,
                        help="codex.config.toml as render_config.py --host <name> --out wrote it for this host")
    parser.add_argument("--eco-root", required=True, help="this run's ecosystem root (ECO_INSTALL_ROOT)")
    parser.add_argument("--codex", default=None, help="the codex executable (default: codex on PATH)")
    parser.add_argument("--codex-home", type=Path, help="default: $CODEX_HOME, else ~/.codex")
    parser.add_argument("--dry-run", action="store_true", help="report what a real run would do; write nothing")
    parser.add_argument("--codex-process-name", default="codex",
                        help="the executable name whose running processes stop a config.toml write (default: codex, "
                             "as apply_codex_lane.py)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    codex_home = Path(args.codex_home or os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    config = codex_home / "config.toml"
    try:
        if not os.path.lexists(config):
            return install_fresh(codex_home, config, args.rendered.read_text(encoding="utf-8"), args.eco_root,
                                 args.dry_run)
        return disable_daemon(codex_home, config, args.codex or shutil.which("codex"), args.dry_run,
                              args.codex_process_name)
    except (Refused, file_io.ApplyError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return EXIT_REFUSED
    except (OSError, subprocess.SubprocessError) as error:
        print(f"failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
