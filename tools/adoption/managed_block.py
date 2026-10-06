#!/usr/bin/env python3
"""Insert or replace one marker-delimited managed block in a user text file, idempotently. Stdlib only.

Supported blocks (the Linux full-profile flow uses claude-md and profile-path):

  claude-md     ~/.claude/CLAUDE.md, the user memory file Claude Code loads in every project
                (code.claude.com/docs/en/memory, "Choose where to put CLAUDE.md files"): the text of
                examples/claude-native/CLAUDE.md, read at run time, between
                  <!-- native-agent-stack:claude-user-instructions:begin (...) -->
                  <!-- native-agent-stack:claude-user-instructions:end -->
                Claude Code strips block-level HTML comments before the text reaches the context (same page), so the
                markers cost nothing.
  codex-md      $CODEX_HOME/AGENTS.md (else ~/.codex/AGENTS.md), replacing only the canonical Codex
                user-instructions block. Does not run Codex, inspect configuration/authentication, or change
                profiles/roles. A nonblank AGENTS.override.md shadows this file and is refused. `--template PATH`
                reads another file of the same shape (one complete block) instead of the repository's template.
  decision-md   One bounded discovery/maintained-decision paragraph in an existing instruction source.
                --client source --target PATH selects a generator's Markdown source; generated outputs are
                refused. --dry-run previews the fragment and prints the target SHA-256; this mode never writes.
                Apply through the source owner's guarded workflow, preserving existing defaults and RTK.
  profile-path  ~/.profile, which a Bash login shell reads when no ~/.bash_profile or ~/.bash_login exists (GNU bash
                manual, "Bash Startup Files"): a POSIX sh block putting the ecosystem's bin directory first on PATH,
                so `claude` in a login shell is the ecosystem launcher (adoption/bootstrap.md, step 2), between
                  # native-agent-stack:profile-path:begin (...)
                  # native-agent-stack:profile-path:end
                `--extra-dir DIR` (repeatable, none by default) adds each DIR to PATH, behind the ecosystem's bin
                directory, unless it is already on PATH.

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
import hashlib
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply_claude_settings as file_io  # noqa: E402  (reused: refuse_symlink, write_backup, atomic_write)
sys.path.insert(0, str(ROOT / "scripts"))
import adoption_status  # noqa: E402  (native Rust whitespace for the override guard)

CLAUDE_EXAMPLE = ROOT / "examples" / "claude-native" / "CLAUDE.md"
CODEX_TEMPLATE = ROOT / "adoption" / "templates" / "codex.AGENTS.template.md"
RTK_AWARENESS_REL = "adoption/templates/rtk-awareness-full.md"
RTK_INCLUDE = "<!-- native-agent-stack:include-rtk-awareness-full -->\n"
DECISION_TEMPLATE = ROOT / "adoption" / "templates" / "decision-routing.md"
CODEX_BEGIN = "<!-- native-agent-stack:codex-user-instructions:begin"
CODEX_END = "<!-- native-agent-stack:codex-user-instructions:end -->"
CODEX_COPY_MARKERS = ("<!-- native-agent-stack:top-rule", "<!-- native-agent-stack:rtk-upstream",
                      "<!-- native-agent-stack:rtk-exceptions")
CLAUDE_BEGIN = "<!-- native-agent-stack:claude-user-instructions:begin"
CLAUDE_END = "<!-- native-agent-stack:claude-user-instructions:end -->"
CLAUDE_BEGIN_LINE = (f"{CLAUDE_BEGIN} (examples/claude-native/CLAUDE.md of native-agent-stack, written by "
                     "adoption/bootstrap-linux.sh --configure-full-profile; edit outside these markers) -->")
PROFILE_BEGIN = "# native-agent-stack:profile-path:begin"
PROFILE_END = "# native-agent-stack:profile-path:end"
PROFILE_BEGIN_LINE = f"{PROFILE_BEGIN} (adoption/bootstrap-linux.sh --configure-full-profile; edit outside these markers)"
RTK_IMPORT = re.compile(r"@RTK\.md[ \t]*")
GENERATED_DIRECTIVES_HEADER = "<!-- Generated from config/directives; edit sources, then scripts/directives.py. -->"
DECISION_BEGIN = "<!-- native-agent-stack:decision-routing:begin"
DECISION_END = "<!-- native-agent-stack:decision-routing:end -->"
DECISION_BEGIN_LINE = f"{DECISION_BEGIN} (adoption/templates/codex.AGENTS.template.md; edit outside these markers) -->"
DECISION_PREFIX = "Bound discovery to task-filtered names, descriptions and source locators;"
EXIT_USAGE, EXIT_REFUSED = 2, 3


class Refused(ValueError):
    """The file cannot be merged without losing or duplicating text: nothing is written (exit 3)."""


def block_span(text: str, begin: str, end: str) -> tuple[int, int] | None:
    """(start, end) of the block's lines, end after the end marker's newline; None when there is no block."""
    begins = [match.start() for match in re.finditer(r"(?m)^" + re.escape(begin), text)]
    ends = [match.span() for match in re.finditer(r"(?m)^" + re.escape(end) + r"[ \t]*(?:\r?\n|\Z)", text)]
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


def refuse_generated_output(current: str) -> None:
    if GENERATED_DIRECTIVES_HEADER in current:
        raise Refused("this file is generated from config/directives; preview its owned Markdown source with "
                      "decision-md, then use the owner's guarded workflow; do not append a second pack")


def claude_target(home: str, explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.expanduser()
    if "CLAUDE_CONFIG_DIR" in os.environ:
        raise Refused("CLAUDE_CONFIG_DIR is set; select the intended instruction file explicitly with --target")
    return Path(home).expanduser() / ".claude" / "CLAUDE.md"


def refuse_narrow_block_in_full_pack(current: str) -> None:
    if block_span(current, DECISION_BEGIN, DECISION_END) is not None:
        raise Refused("a decision-routing block is already present; preview its owned source with decision-md; "
                      "adding a full instruction pack would duplicate it")


def merged_claude_md(current: str, example: str) -> str:
    refuse_generated_output(current)
    refuse_narrow_block_in_full_pack(current)
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


def codex_block(template: str, *, root: Path = ROOT) -> str:
    """Inline the pinned RTK awareness bytes; Codex does not expand @ imports.

    rtk-ai/rtk v0.51.0 (e001f773), src/hooks/init/codex.rs writes RTK.md
    plus a reference. This existing writer fills only the Codex import gap.
    Already-rendered carriers have no include marker and pass through unchanged.
    """
    if RTK_INCLUDE not in template:
        return template
    if template.count(RTK_INCLUDE) != 1:
        raise Refused("the Codex template must include RTK awareness exactly once")
    awareness = (root / RTK_AWARENESS_REL).read_bytes().decode("utf-8")
    return template.replace(RTK_INCLUDE, awareness)


def merged_codex_md(current: str, template: str) -> str:
    template = codex_block(template)
    refuse_generated_output(current)
    refuse_narrow_block_in_full_pack(current)
    if block_span(template, CODEX_BEGIN, CODEX_END) != (0, len(template)):
        raise Refused("the Codex template must be exactly one complete managed block")
    span = block_span(current, CODEX_BEGIN, CODEX_END)
    outside = current if span is None else current[:span[0]] + current[span[1]:]
    if any(marker in outside for marker in CODEX_COPY_MARKERS):
        raise Refused("an unmanaged Codex template copy exists outside the block; review its migration first")
    if span is None and current.strip():
        # Keep operator bytes, including trailing blank lines, when appending a first block.
        return current + ("\n" if current.endswith("\n") else "\n\n") + template
    return with_block(current, template, CODEX_BEGIN, CODEX_END)


def decision_rule(template: str) -> str:
    if block_span(template, CODEX_BEGIN, CODEX_END) != (0, len(template)):
        raise Refused("the Codex template must be exactly one complete managed block")
    rules = [line for line in template.splitlines() if line.startswith(DECISION_PREFIX)]
    if len(rules) != 1:
        raise Refused("the canonical template must contain exactly one decision-routing paragraph")
    return rules[0]


def decision_block(rule: str) -> str:
    block = DECISION_TEMPLATE.read_bytes().decode("utf-8")
    expected = f"{DECISION_BEGIN_LINE}\n{rule}\n{DECISION_END}\n"
    if block != expected:
        raise Refused("the decision-routing fragment differs from the canonical template paragraph")
    return block


def merged_decision_md(current: str, rule: str) -> str:
    refuse_generated_output(current)
    if not current.strip():
        raise Refused("decision-md refreshes an existing nonblank instruction source, not a new profile")
    span = block_span(current, DECISION_BEGIN, DECISION_END)
    outside = current if span is None else current[:span[0]] + current[span[1]:]
    paragraphs = re.split(r"\r?\n[ \t]*\r?\n", outside)
    copies = [normalized.removeprefix("- ") for paragraph in paragraphs
              if DECISION_PREFIX in (normalized := " ".join(paragraph.split()))]
    if copies:
        if span is None and copies == [rule]:
            return current
        raise Refused("an unmanaged or conflicting decision-routing paragraph exists; reconcile its owned "
                      "source before adding another copy")
    block = decision_block(rule)
    if span:
        return current[:span[0]] + block + current[span[1]:]
    return current + ("\n" if current.endswith("\n") else "\n\n") + block


def sh_double_quoted(text: str) -> str:
    """text for the inside of a POSIX sh double-quoted string."""
    return re.sub(r'([\\"$`])', r"\\\1", text)


def shell_dir(path: str, home: str, what: str) -> str:
    """path as the inside of a POSIX sh double-quoted string: under home it is written as $HOME/<relative>.

    A path of slashes only is the root directory and stays "/", as POSIX basename makes it (for "//" that is
    implementation-defined, and Linux takes "//" as the root), so the result is never empty: an empty PATH component
    names the current directory (XBD 8.3, PATH)."""
    normal = os.path.normpath(path)
    base = os.path.normpath(home)
    if not os.path.isabs(normal):
        raise Refused(f"the {what} must be an absolute path, got {path!r}")
    if any(ord(char) < 32 for char in normal):
        raise Refused(f"the {what} holds a control character")
    relative = os.path.relpath(normal, base) if base != "/" else None
    if relative is not None and relative != "." and not relative.startswith(".."):
        return "$HOME/" + sh_double_quoted(relative)
    return sh_double_quoted(normal.rstrip("/") or "/")


def profile_block(eco_root: str, home: str, extra_dirs: tuple[str, ...] = ()) -> str:
    root = shell_dir(eco_root, home, "ecosystem root")
    directory = ("" if root == "/" else root) + "/bin"  # the root's bin directory is /bin, not //bin
    extras = ""
    if extra_dirs:
        # Each extra directory goes in front of the system path unless it is already on PATH, in reverse order so the
        # first one named ends up next to the ecosystem directory, which is added last and stays first.
        extras = ("# These directories are added when they are not on PATH yet: the native installers' bin directory "
                  "and mise's shims.\n")
        for extra in reversed(extra_dirs):
            wanted = shell_dir(extra, home, "extra directory")
            extras += ('case ":${PATH-}:" in\n'
                       f'  *":{wanted}:"*) ;;\n'
                       f'  *) PATH="{wanted}${{PATH:+:$PATH}}" ;;\n'
                       "esac\n")
    return (f"{PROFILE_BEGIN_LINE}\n"
            "# The ecosystem's bin directory first on PATH, so `claude` in a login shell is its launcher.\n"
            f"{extras}"
            'case ":${PATH-}:" in\n'
            f'  ":{directory}:"*) ;;\n'
            f'  *) PATH="{directory}${{PATH:+:$PATH}}" ;;\n'
            "esac\n"
            "export PATH\n"
            f"{PROFILE_END}\n")


def merged_profile(current: str, eco_root: str, home: str, extra_dirs: tuple[str, ...] = ()) -> str:
    return with_block(current, profile_block(eco_root, home, extra_dirs), PROFILE_BEGIN, PROFILE_END)


PROFILE_ENV_BEGIN = "# native-agent-stack:profile-env:begin"
PROFILE_ENV_END = "# native-agent-stack:profile-env:end"


def profile_env_block(env_file: str, home: str) -> str:
    """Source only the generated pointer file; POSIX set -a exports its assignments.

    systemd/systemd@b3d8fc43:man/environment.d.xml:59-74 and bash@5.3:builtins/set.def (allexport).
    Preserve a caller that already enabled allexport, while restoring the ordinary disabled state.
    """
    target = shell_dir(env_file, home, "pointer environment file")
    return (f"{PROFILE_ENV_BEGIN}\n"
            f'if [ -r "{target}" ]; then\n'
            "  case $- in\n"
            f'    *a*) . "{target}" ;;\n'
            f'    *) set -a; . "{target}"; set +a ;;\n'
            "  esac\n"
            "fi\n"
            f"{PROFILE_ENV_END}\n")


def merged_profile_env(current: str, env_file: str, home: str) -> str:
    return with_block(current, profile_env_block(env_file, home), PROFILE_ENV_BEGIN, PROFILE_ENV_END)


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
        return path.read_bytes().decode("utf-8"), stat.S_IMODE(path.stat().st_mode)
    except UnicodeDecodeError:
        raise Refused(f"{path} is not UTF-8 text") from None


def preview_decision(path: Path, rule: str) -> int:
    current, _ = read_target(path)
    merged = merged_decision_md(current, rule)
    print(f"Reviewed target SHA-256: {hashlib.sha256(current.encode('utf-8')).hexdigest()}")
    if current == merged:
        print(f"{path}: already current, nothing written")
    else:
        sys.stdout.writelines(difflib.unified_diff(current.splitlines(keepends=True), merged.splitlines(keepends=True),
                                                   fromfile=f"{path} (now)", tofile=f"{path} (proposed)"))
        print(f"{path}: PREVIEW ONLY, apply through the source owner's guarded workflow")
    return 0


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
    codex = blocks.add_parser("codex-md", help="only the Codex user instructions block; no config/profile/role changes")
    codex.add_argument("--codex-home", type=Path, help="default: $CODEX_HOME, else <home>/.codex")
    codex.add_argument("--template", type=Path, default=CODEX_TEMPLATE,
                       help="default: adoption/templates/codex.AGENTS.template.md")
    decision = blocks.add_parser("decision-md", help="export or preview the routing paragraph; never write")
    decision.add_argument("--client", choices=("source", "claude", "codex"), default="source",
                          help="source requires --target; native clients use their normal instruction location")
    decision.add_argument("--target", type=Path, help="the owned Markdown source (or a standalone Claude file)")
    decision.add_argument("--codex-home", type=Path, help="Codex only: $CODEX_HOME, else <home>/.codex")
    decision.add_argument("--print", action="store_true", help="print the canonical fragment; no target or client reads")
    profile = blocks.add_parser("profile-path", help="the PATH block in ~/.profile")
    profile.add_argument("--target", type=Path, help="default: <home>/.profile")
    profile.add_argument("--eco-root", required=True, help="the ecosystem root whose bin directory goes first")
    profile.add_argument("--extra-dir", action="append", default=[], metavar="DIR",
                         help="another absolute directory to put on PATH when it is not on it yet, behind the "
                              "ecosystem's bin directory (repeatable; none by default). A host whose tools come from "
                               "native installers and mise names ~/.local/bin and mise's shims directory here")
    env = blocks.add_parser("profile-env", help="source the generated non-secret pointer file from ~/.profile")
    env.add_argument("--target", type=Path, help="default: <home>/.profile")
    env.add_argument("--env-file", required=True, help="generated environment.d pointer file (no credential file)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    home = args.home or os.environ.get("HOME") or str(Path.home())
    try:
        if args.block == "decision-md":
            rule = decision_rule(CODEX_TEMPLATE.read_text(encoding="utf-8"))
            if args.print:
                if args.target or args.codex_home or args.client != "source":
                    raise Refused("--print only exports the fragment; omit target and client options")
                sys.stdout.write(decision_block(rule))
                return 0
            if not args.dry_run:
                raise Refused("decision-md exports or previews only; use --print or --dry-run, then apply "
                              "through the source owner's guarded workflow")
            if args.client == "codex":
                if args.target:
                    raise Refused("use --codex-home for native Codex, or --client source for a generator source")
                codex_home = (args.codex_home or Path(os.environ.get("CODEX_HOME") or Path(home) / ".codex")).expanduser()
                override, _ = read_target(codex_home / "AGENTS.override.md")
                if override.strip(adoption_status.RUST_WHITESPACE):
                    raise Refused("AGENTS.override.md has text and would shadow AGENTS.md; nothing written")
                target = codex_home / "AGENTS.md"
            elif args.client == "claude":
                if args.codex_home:
                    raise Refused("--codex-home is only for --client codex")
                target = claude_target(home, args.target)
            else:
                if not args.target or args.codex_home:
                    raise Refused("--client source requires --target and does not use --codex-home")
                target = args.target.expanduser()
            return preview_decision(target, rule)
        if args.block == "claude-md":
            example = args.example.read_text(encoding="utf-8")
            target = claude_target(home, args.target)
            return apply(target, lambda text: merged_claude_md(text, example), dry_run=args.dry_run)
        if args.block == "codex-md":
            codex_home = (args.codex_home or Path(os.environ.get("CODEX_HOME") or Path(home) / ".codex")).expanduser()
            override, _ = read_target(codex_home / "AGENTS.override.md")
            if override.strip(adoption_status.RUST_WHITESPACE):
                raise Refused("AGENTS.override.md has text and would shadow AGENTS.md; nothing written")
            template = args.template.read_text(encoding="utf-8")
            return apply(codex_home / "AGENTS.md", lambda text: merged_codex_md(text, template), dry_run=args.dry_run)
        target = args.target or Path(home) / ".profile"
        if args.block == "profile-env":
            return apply(target, lambda text: merged_profile_env(text, args.env_file, home), dry_run=args.dry_run)
        extra_dirs = tuple(args.extra_dir)
        return apply(target, lambda text: merged_profile(text, args.eco_root, home, extra_dirs), dry_run=args.dry_run)
    except (Refused, file_io.ApplyError) as error:
        print(f"refused: {error}; nothing written", file=sys.stderr)
        return EXIT_REFUSED
    except OSError as error:
        print(f"failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
