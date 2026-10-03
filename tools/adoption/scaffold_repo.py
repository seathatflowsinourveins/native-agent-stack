#!/usr/bin/env python3
"""Write this catalog's new-repository scaffold into a target directory, idempotently. Stdlib only.

The scaffold is every file under adoption/scaffold/ plus one file rendered for this host:

  AGENTS.md                            the top rule (the block after the native-agent-stack:top-rule marker of
                                       adoption/templates/codex.AGENTS.template.md, byte for byte) and a repository
                                       expectations section to fill in
  CLAUDE.md                            `@AGENTS.md` and a one-line comment: Claude Code reads AGENTS.md through the
                                       import (code.claude.com/docs/en/memory, "Share one file with other coding tools")
  .agents/skills/README.md             where repository-only skills go; skills every repository uses are global
  .github/pull_request_template.md     scope, lane, "## SOTA sources" and the evidence classes
  .github/workflows/sota-sources.yml   from sota-sources.yml.template: calls this repository's reusable
                                       .github/workflows/sota-sources-gate.yml at a pinned main commit
  .codex/config.toml                   adoption/templates/project.codex.config.template.toml rendered with
                                       tools/adoption/render_config.py's renderer for this host's ECO_ROOT, HOST_PATH
                                       and CODE_INDEX_PATH: it carries host paths, so each host renders its own

A scaffold file whose name ends in `.template` holds a placeholder: the tool fills it and drops the suffix, the rule
copier applies to its template suffix (copier v9.18.2 docs/configuring.md, `templates_suffix`, default `.jinja`);
every other file is copied byte for byte. The workflow is kept under that name because zizmor 1.30.1 collects nested
.github/workflows directories, and validate.yml's repository-wide zizmor gate would report the unfilled `<sha>` as an
unpinned `uses:`. --dry-run is copier's `pretend` (same page). Copier's `overwrite` replaces every existing file and
its `skip_if_exists` (`--skip`) names the files to keep; the scaffold's AGENTS.md is meant to be filled in, so this
tool runs the other way round: every file whose content differs is kept unless --force names it.

`<sha>` is --main-sha, else what `git ls-remote origin refs/heads/main` reports for this checkout. When that commit is
in this checkout it must carry .github/workflows/sota-sources-gate.yml, since the written workflow would otherwise
call a missing file: refused before any write. A commit this checkout lacks is used as given and reported unchecked.
Either way GitHub resolves the reusable workflow at run time, so the new repository's check runs only once that
commit, pushed to this repository on GitHub, carries the gate file.

Template values for .codex/config.toml: ECO_ROOT is $ECO_INSTALL_ROOT, else ~/.local/share/codex-ecosystem (the
bootstrap default); HOST_PATH is the system directories of adoption/hosts/example.json, never this process's PATH
(on WSL it can carry Windows directories that name the user); CODE_INDEX_PATH is $CODE_INDEX_PATH, else ~/.code-index.
--host <name> reads adoption/hosts/<name>.json instead, and --set KEY=VALUE overrides one value.

For each file: created when absent and unchanged when identical. A file whose content differs is skipped, never
overwritten, unless --force names it: `--force <path>`, the path as the table prints it (for example
`--force .github/workflows/sota-sources.yml`), repeatable. A named file is overwritten, keeping its mode bits, with no
backup (commit first); every other file that differs is still skipped. A bare --force is a usage error, and a path that
is not a scaffold file is refused before any write. A symlink or a non-regular file on the way to a target is skipped
even when named, so nothing is written through it. --dry-run writes nothing and reports what a real run would do, with
the same exit status; it also plans a --target that does not exist yet (every file would be created), which a real
run refuses. The table goes to stdout.

Exit status: 0 done (nothing skipped), 3 a file was skipped (refusal), 2 a usage error or an input the scaffold
cannot be written from (nothing written), 1 an unexpected error.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_config  # noqa: E402  (reused, not rewritten: the host value files and the ${NAME} renderer)

SCAFFOLD = ROOT / "adoption" / "scaffold"
PROJECT_CODEX_TEMPLATE = ROOT / "adoption" / "templates" / "project.codex.config.template.toml"
CODEX_CONFIG = ".codex/config.toml"
TEMPLATE_SUFFIX = ".template"
SHA_PLACEHOLDER = "<sha>"
GATE_FILE = ".github/workflows/sota-sources-gate.yml"
GATE_REFERENCE = f"seathatflowsinourveins/native-agent-stack/{GATE_FILE}"
SHA = re.compile(r"[0-9a-f]{40}")
DEFAULT_HOST_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"  # adoption/hosts/example.json
CODEX_KEYS = ("ECO_ROOT", "HOST_PATH", "CODE_INDEX_PATH")
EXIT_USAGE, EXIT_REFUSED = 2, 3


class Unusable(ValueError):
    """An input the scaffold cannot be written from: exit 2, nothing written."""


def render_caller(text: str, sha: str) -> str:
    """The caller workflow with the gate pinned to ``sha``: a full, lowercase 40-hex commit id."""
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise ValueError(f"the gate's commit must be a full 40-hex lowercase commit id, got {sha!r}")
    if text.count(SHA_PLACEHOLDER) != 1 or f"{GATE_REFERENCE}@{SHA_PLACEHOLDER}" not in text:
        raise ValueError(f"a scaffold template must name {GATE_REFERENCE}@{SHA_PLACEHOLDER} exactly once")
    return text.replace(SHA_PLACEHOLDER, sha)


def codex_values(host: str | None, pairs: list[str], env) -> dict[str, str]:
    """The three template values of .codex/config.toml: the defaults, then --host's file, then --set."""
    home = env.get("HOME") or str(Path.home())
    values = {"ECO_ROOT": env.get("ECO_INSTALL_ROOT") or f"{home}/.local/share/codex-ecosystem",
              "HOST_PATH": DEFAULT_HOST_PATH,
              "CODE_INDEX_PATH": env.get("CODE_INDEX_PATH") or f"{home}/.code-index"}
    try:
        if host:
            values.update(render_config.load_host_values(host))
        values.update(render_config.parse_set_values(pairs))
    except (render_config.RenderError, OSError, ValueError) as error:
        raise Unusable(str(error)) from None
    for key in CODEX_KEYS:
        value = values.get(key, "")
        # Each value lands inside a TOML basic string, so a quote, a backslash or a control character would end or
        # change it.
        if not value or any(char in value for char in '"\\') or any(ord(char) < 32 for char in value):
            raise Unusable(f"{key} must be nonempty text without quotes, backslashes or control characters")
        if key != "HOST_PATH" and not value.startswith("/"):
            raise Unusable(f"{key} must be an absolute path")
    return values


def render_codex_config(values: dict[str, str]) -> str:
    try:
        text = render_config.render_one(PROJECT_CODEX_TEMPLATE, values)
        tomllib.loads(text)
    except (render_config.RenderError, tomllib.TOMLDecodeError) as error:
        raise Unusable(f"{PROJECT_CODEX_TEMPLATE.name}: {error}") from None
    return text


def git(*args: str) -> subprocess.CompletedProcess:
    # Inherited GIT_* routing variables must not point this at another repository (scripts/validate.py does the same).
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return subprocess.run(["git", "--no-optional-locks", "-C", str(ROOT), *args], env=environment,
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60, check=False)


def main_sha(explicit: str | None) -> str:
    if explicit is not None:
        if not SHA.fullmatch(explicit):
            raise Unusable("--main-sha must be a full 40-hex lowercase commit id")
        return explicit
    try:
        result = git("ls-remote", "origin", "refs/heads/main")
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Unusable(f"git ls-remote origin refs/heads/main failed ({type(error).__name__}); pass --main-sha") from None
    fields = result.stdout.split()
    if result.returncode != 0 or len(fields) != 2 or fields[1] != "refs/heads/main" or not SHA.fullmatch(fields[0]):
        raise Unusable("git ls-remote origin refs/heads/main named no single commit; pass --main-sha")
    return fields[0]


def gate_state(sha: str) -> str:
    """present or absent at that commit, or unknown when this checkout does not have the commit."""
    if git("cat-file", "-e", f"{sha}^{{commit}}").returncode != 0:
        return "unknown"
    return "present" if git("cat-file", "-e", f"{sha}:{GATE_FILE}").returncode == 0 else "absent"


def scaffold_files(sha: str, codex_text: str) -> list[tuple[str, bytes]]:
    """[(path in the target, content)], in a fixed order."""
    files = []
    for source in sorted(SCAFFOLD.rglob("*")):
        if source.is_dir() and not source.is_symlink():
            continue
        relative = source.relative_to(SCAFFOLD).as_posix()
        if source.is_symlink() or not source.is_file():
            raise Unusable(f"adoption/scaffold/{relative} is not a regular file")
        data = source.read_bytes()
        if relative.endswith(TEMPLATE_SUFFIX):
            relative = relative[:-len(TEMPLATE_SUFFIX)]
            data = render_caller(data.decode("utf-8"), sha).encode("utf-8")
        files.append((relative, data))
    files.append((CODEX_CONFIG, codex_text.encode("utf-8")))
    return files


def blocked(target: Path, relative: str) -> str | None:
    """Why nothing may be written at target/relative: a symlink on the way, a non-directory where a directory must
    be, or a non-regular file at the path. None when the path is safe to create or replace."""
    current = target
    parts = PurePosixPath(relative).parts
    for index, part in enumerate(parts):
        current = current / part
        shown = "/".join(parts[:index + 1])
        if current.is_symlink():
            return f"{shown} is a symlink; nothing is written through it"
        if index < len(parts) - 1 and current.exists() and not current.is_dir():
            return f"{shown} is not a directory"
    if current.exists() and not current.is_file():
        return "not a regular file"
    return None


def forced_files(named: list[str], files: list[tuple[str, bytes]]) -> set[str]:
    """The scaffold paths --force names, each as the table prints it; any other path is unusable."""
    known = [relative for relative, _ in files]
    forced = set()
    for name in named:
        relative = PurePosixPath(name).as_posix()
        if relative not in known:
            raise Unusable(f"--force {name!r} is not a scaffold file; name one of: {', '.join(known)}")
        forced.add(relative)
    return forced


def plan(target: Path, files: list[tuple[str, bytes]], force: set[str]) -> list[dict]:
    rows = []
    for relative, data in files:
        destination = target / relative
        row = {"file": relative, "data": data, "reason": blocked(target, relative)}
        if row["reason"]:
            row["status"] = "skipped"
        elif not destination.exists():
            row["status"] = "create"
        elif destination.read_bytes() == data:
            row["status"] = "unchanged"
        elif relative in force:
            row["status"] = "overwrite"
        else:
            row["status"], row["reason"] = "skipped", f"differs from the scaffold; --force {relative} overwrites it"
        rows.append(row)
    return rows


def write(destination: Path, data: bytes) -> None:
    """Replace atomically through a temporary file in the same directory, keeping an existing file's mode bits."""
    mode = stat.S_IMODE(destination.stat().st_mode) if destination.exists() else 0o644
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=destination.parent, prefix=f".{destination.name}.")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            os.unlink(temporary)


LABELS = {False: {"create": "created", "overwrite": "overwritten"},
          True: {"create": "would create", "overwrite": "would overwrite"}}
GATE_NOTES = {"present": "present at that commit", "absent": "MISSING at that commit",
              "unknown": "commit not in this checkout, unchecked"}


def report(rows: list[dict], dry_run: bool) -> None:
    labels = LABELS[dry_run]
    width = max(len(label) for label in (*labels.values(), "unchanged", "skipped"))
    print(f"{'status':<{width}}  file")
    for row in rows:
        label = labels.get(row["status"], row["status"])
        print(f"{label:<{width}}  {row['file']}" + (f"  ({row['reason']})" if row["reason"] else ""))
    counts = {}
    for row in rows:
        label = labels.get(row["status"], row["status"])
        counts[label] = counts.get(label, 0) + 1
    print("summary: " + ", ".join(f"{count} {label}" for label, count in counts.items()))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", required=True, type=Path,
                        help="the new repository's directory (a real run needs it to exist; --dry-run does not)")
    parser.add_argument("--dry-run", action="store_true", help="write nothing; report what a real run would do")
    parser.add_argument("--main-sha", help="the main commit the workflow pins the gate to (default: git ls-remote "
                                           "origin refs/heads/main)")
    parser.add_argument("--force", action="append", default=[], metavar="PATH",
                        help="overwrite this scaffold file although its content differs, PATH as the table prints it "
                             "(e.g. .github/workflows/sota-sources.yml); repeatable. Other differing files are kept")
    parser.add_argument("--host", help="read .codex/config.toml's values from adoption/hosts/<host>.json")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="override one of ECO_ROOT, HOST_PATH, CODE_INDEX_PATH; repeatable")
    return parser


def main(argv: list[str] | None = None, env=None) -> int:
    args = build_parser().parse_args(argv)
    env = os.environ if env is None else env
    target = args.target
    # Only a dry run may name a directory that does not exist yet: it writes nothing, so its plan can come before
    # `git init`. A dangling symlink or a file in its place is refused either way.
    missing = not target.exists() and not target.is_symlink()
    try:
        if not target.is_dir() and not (missing and args.dry_run):
            raise Unusable(f"--target {target} is not an existing directory (create it, for example with git init; "
                           "--dry-run plans one that does not exist yet)")
        if target.resolve() == ROOT:
            raise Unusable("--target is this catalog checkout; name the new repository's directory")
        codex_text = render_codex_config(codex_values(args.host, args.set, env))
        sha = main_sha(args.main_sha)
        files = scaffold_files(sha, codex_text)
        force = forced_files(args.force, files)
    except (Unusable, ValueError) as error:
        print(f"refused: {error}; nothing written", file=sys.stderr)
        return EXIT_USAGE
    gate = gate_state(sha)
    rows = plan(target, files, force)
    # A refused run writes nothing either, so its plan is shown the way a dry run shows it.
    hypothetical = args.dry_run or gate == "absent"
    print(("DRY RUN: nothing is written. " if args.dry_run else "") + f"Scaffold for {target}"
          + (" (does not exist yet: create it, for example with git init, before a real run)" if missing else ""))
    print(f"gate: {GATE_FILE} at {sha} ({GATE_NOTES[gate]})")
    report(rows, hypothetical)
    if gate == "absent":
        print(f"refused: {sha} has no {GATE_FILE}, so the workflow would call a missing file; pass --main-sha "
              "with a main commit that carries it. Nothing written.", file=sys.stderr)
        return EXIT_USAGE
    if not args.dry_run:
        for row in rows:
            if row["status"] in ("create", "overwrite"):
                write(target / row["file"], row["data"])
    if any(row["file"] == CODEX_CONFIG and row["status"] in ("create", "overwrite") for row in rows):
        print(f"note: {CODEX_CONFIG} carries this host's {', '.join(CODEX_KEYS)}; each host renders its own.")
    return EXIT_REFUSED if any(row["status"] == "skipped" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
