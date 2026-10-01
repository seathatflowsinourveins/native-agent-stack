#!/usr/bin/env python3
"""Insert or replace one marker-delimited managed block in a user text file, idempotently. Stdlib only.

adoption/bootstrap-linux.sh --configure-full-profile writes two such blocks:

  claude-md     ~/.claude/CLAUDE.md, the user memory file Claude Code loads in every project
                (code.claude.com/docs/en/memory, "Choose where to put CLAUDE.md files"): the text of
                examples/claude-native/CLAUDE.md, read at run time, between
                  <!-- native-agent-stack:claude-user-instructions:begin (...) -->
                  <!-- native-agent-stack:claude-user-instructions:end -->
                Claude Code strips block-level HTML comments before the text reaches the context (same page), so the
                markers cost nothing.
  profile-path  ~/.profile, which a Bash login shell reads when no ~/.bash_profile or ~/.bash_login exists (GNU bash
                manual, "Bash Startup Files"): a POSIX sh block putting the ecosystem's bin directory first on PATH,
                so `claude` in a login shell is the ecosystem launcher (adoption/bootstrap.md, step 2), between
                  # native-agent-stack:profile-path:begin (...)
                  # native-agent-stack:profile-path:end

The merge is the one tools/adoption/apply_codex_lane.py applies to the Codex AGENTS.md block (block_span and
with_block), with the markers as parameters: exactly one begin line and one end line, in that order, or neither; any
other count or order is refused. With no block the block is appended after the existing text, so its PATH line runs
after the others in ~/.profile and stays first. Every line outside the markers is kept.

claude-md also keeps rtk's import: an `@RTK.md` line found only inside an earlier block moves above the begin marker.
A file with no markers that already holds a copy of the example (its heading line) would state every rule twice after
an append, so a copy equal to the current example is replaced by the block (recipes/claude-native-profile.md: replace
an earlier merged copy as a whole, keeping managed imports) and any other copy is refused with nothing written.

Writing refuses a symlink or a non-regular file, backs an existing file up beside it first with
tools/adoption/apply_claude_settings.py's write_backup (<name>.bak.<UTC stamp>, never overwriting an earlier backup),
and replaces it atomically with that tool's atomic_write, keeping its mode (a new file gets 0644). A file already up
to date is left alone: no write, no backup. --dry-run prints the unified diff and writes nothing.

Exit status: 0 written or already current, 3 refused (nothing written), 2 usage error, 1 unexpected error.
"""

from __future__ import annotations

import argparse
import difflib
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply_claude_settings as file_io  # noqa: E402  (reused: refuse_symlink, write_backup, atomic_write)

CLAUDE_EXAMPLE = ROOT / "examples" / "claude-native" / "CLAUDE.md"
CLAUDE_BEGIN = "<!-- native-agent-stack:claude-user-instructions:begin"
CLAUDE_END = "<!-- native-agent-stack:claude-user-instructions:end -->"
CLAUDE_BEGIN_LINE = (f"{CLAUDE_BEGIN} (examples/claude-native/CLAUDE.md of native-agent-stack, written by "
                     "adoption/bootstrap-linux.sh --configure-full-profile; edit outside these markers) -->")
PROFILE_BEGIN = "# native-agent-stack:profile-path:begin"
PROFILE_END = "# native-agent-stack:profile-path:end"
PROFILE_BEGIN_LINE = f"{PROFILE_BEGIN} (adoption/bootstrap-linux.sh --configure-full-profile; edit outside these markers)"
RTK_IMPORT = re.compile(r"@RTK\.md[ \t]*")
EXIT_USAGE, EXIT_REFUSED = 2, 3


class Refused(ValueError):
    """The file cannot be merged without losing or duplicating text: nothing is written (exit 3)."""


def block_span(text: str, begin: str, end: str) -> tuple[int, int] | None:
    """(start, end) of the block's lines, end after the end marker's newline; None when there is no block."""
    begins = [match.start() for match in re.finditer(r"(?m)^" + re.escape(begin), text)]
    ends = [match.span() for match in re.finditer(r"(?m)^" + re.escape(end) + r"[ \t]*(?:\n|\Z)", text)]
    if not begins and not ends:
        return None
    # The end marker must start after the begin marker starts: comparing its end instead would take an end line
    # directly above the begin line for an empty block.
    if len(begins) != 1 or len(ends) != 1 or ends[0][0] <= begins[0]:
        raise Refused(f"the managed block is damaged (its markers are missing, repeated or out of order: {begin})")
    return begins[0], ends[0][1]


def with_block(text: str, block: str, begin: str, end: str) -> str:
    """text with the block replaced, or appended after the existing text when it has none."""
    span = block_span(text, begin, end)
    if span:
        return text[:span[0]] + block + text[span[1]:]
    if not text.strip():
        return block
    return text.rstrip("\n") + "\n\n" + block


def claude_block(example: str) -> str:
    return f"{CLAUDE_BEGIN_LINE}\n{example.strip()}\n{CLAUDE_END}\n"


def merged_claude_md(current: str, example: str) -> str:
    block = claude_block(example)
    span = block_span(current, CLAUDE_BEGIN, CLAUDE_END)
    heading = next((line for line in example.splitlines() if line.strip()), "")
    heading_line = re.compile(r"(?m)^" + re.escape(heading) + r"[ \t]*$") if heading else None
    if span:
        head, old = current[:span[0]], current[span[0]:span[1]]
        outside = head + current[span[1]:]
        if heading_line and heading_line.search(outside):
            raise Refused(f"besides the managed block it holds another copy of examples/claude-native/CLAUDE.md (its "
                          f"{heading!r} line), which would state its rules twice; remove that copy, then run again")
        if (any(RTK_IMPORT.fullmatch(line) for line in old.splitlines())
                and not any(RTK_IMPORT.fullmatch(line) for line in outside.splitlines())
                and not any(RTK_IMPORT.fullmatch(line) for line in block.splitlines())):
            current = head + "@RTK.md\n" + current[span[0]:]
        return with_block(current, block, CLAUDE_BEGIN, CLAUDE_END)
    if heading_line and heading_line.search(current):
        imports = [line.strip() for line in current.splitlines() if RTK_IMPORT.fullmatch(line)]
        rest = "\n".join(line for line in current.splitlines() if not RTK_IMPORT.fullmatch(line))
        if rest.strip() != example.strip():
            raise Refused(f"it holds an unmanaged copy of examples/claude-native/CLAUDE.md (its {heading!r} line) that "
                          "differs from the current example; appending the block would state its rules twice. Remove "
                          "that copy, or wrap the part to replace in the begin and end markers, then run again")
        return "\n".join(dict.fromkeys(imports)) + ("\n\n" if imports else "") + block
    return with_block(current, block, CLAUDE_BEGIN, CLAUDE_END)


def sh_double_quoted(text: str) -> str:
    """text for the inside of a POSIX sh double-quoted string."""
    return re.sub(r'([\\"$`])', r"\\\1", text)


def profile_block(eco_root: str, home: str) -> str:
    root = os.path.normpath(eco_root)
    base = os.path.normpath(home)
    if not os.path.isabs(root):
        raise Refused(f"the ecosystem root must be an absolute path, got {eco_root!r}")
    if any(ord(char) < 32 for char in root):
        raise Refused("the ecosystem root holds a control character")
    relative = os.path.relpath(root, base) if base != "/" else None
    if relative is not None and relative != "." and not relative.startswith(".."):
        directory = "$HOME/" + sh_double_quoted(relative) + "/bin"
    else:
        directory = sh_double_quoted(root.rstrip("/") + "/bin")
    return (f"{PROFILE_BEGIN_LINE}\n"
            "# The ecosystem's bin directory first on PATH, so `claude` in a login shell is its launcher.\n"
            'case ":${PATH-}:" in\n'
            f'  ":{directory}:"*) ;;\n'
            f'  *) PATH="{directory}${{PATH:+:$PATH}}" ;;\n'
            "esac\n"
            "export PATH\n"
            f"{PROFILE_END}\n")


def merged_profile(current: str, eco_root: str, home: str) -> str:
    return with_block(current, profile_block(eco_root, home), PROFILE_BEGIN, PROFILE_END)


def read_target(path: Path) -> tuple[str, int | None]:
    """(text, mode) of the target; ("", None) when it does not exist."""
    try:
        file_io.refuse_symlink(path)
    except file_io.ApplyError as error:
        raise Refused(str(error)) from None
    if not path.exists():
        return "", None
    if not path.is_file():
        raise Refused(f"{path} is not a regular file")
    try:
        return path.read_text(encoding="utf-8"), stat.S_IMODE(path.stat().st_mode)
    except UnicodeDecodeError:
        raise Refused(f"{path} is not UTF-8 text") from None


def apply(path: Path, merge, *, dry_run: bool) -> int:
    current, mode = read_target(path)
    merged = merge(current)
    if merged == current:
        print(f"{path}: already current, nothing written")
        return 0
    if dry_run:
        sys.stdout.writelines(difflib.unified_diff(current.splitlines(keepends=True), merged.splitlines(keepends=True),
                                                   fromfile=f"{path} (now)", tofile=f"{path} (merged)"))
        print(f"{path}: DRY RUN, nothing written")
        return 0
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup = None
    if mode is not None:
        file_io.refuse_symlink(path)  # checked again right before the write
        backup = file_io.write_backup(path)
    file_io.atomic_write(path, merged, mode if mode is not None else 0o644)
    print(f"{path}: written" + (f" (backup {backup})" if backup else " (new file)"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--home", default=None, help="the home directory (default: $HOME)")
    parser.add_argument("--dry-run", action="store_true", help="print the diff and write nothing")
    blocks = parser.add_subparsers(dest="block", required=True)
    claude = blocks.add_parser("claude-md", help="the Claude Code user instructions block in ~/.claude/CLAUDE.md")
    claude.add_argument("--target", type=Path, help="default: <home>/.claude/CLAUDE.md")
    claude.add_argument("--example", type=Path, default=CLAUDE_EXAMPLE, help="default: examples/claude-native/CLAUDE.md")
    profile = blocks.add_parser("profile-path", help="the PATH block in ~/.profile")
    profile.add_argument("--target", type=Path, help="default: <home>/.profile")
    profile.add_argument("--eco-root", required=True, help="the ecosystem root whose bin directory goes first")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    home = args.home or os.environ.get("HOME") or str(Path.home())
    try:
        if args.block == "claude-md":
            example = args.example.read_text(encoding="utf-8")
            target = args.target or Path(home) / ".claude" / "CLAUDE.md"
            return apply(target, lambda text: merged_claude_md(text, example), dry_run=args.dry_run)
        target = args.target or Path(home) / ".profile"
        return apply(target, lambda text: merged_profile(text, args.eco_root, home), dry_run=args.dry_run)
    except (Refused, file_io.ApplyError) as error:
        print(f"refused: {error}; nothing written", file=sys.stderr)
        return EXIT_REFUSED
    except OSError as error:
        print(f"failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
