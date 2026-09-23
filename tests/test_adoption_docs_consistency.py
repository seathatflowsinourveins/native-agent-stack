"""The new-host documents must agree with adoption/manifest.json and with the tree they ship in.

Found by the 2026-09-23 new-PC documentation inventory: bootstrap.md quoted the previous
release's commit after the pin moved, a documented command combined mutually exclusive flags,
the profile table omitted a profile and said nothing about which profiles the bootstrap pins
cover. Each test below names the drift it stops:

- a 40-hex hash or release tag quoted where a document labels the release pin equals
  ``source.release_commit`` / ``source.release_tag`` (and the checkout pages derive both from
  the manifest instead of quoting them);
- every relative Markdown link (and ``#anchor`` into a Markdown file) in adoption/**/*.md,
  docs/next-host-stages.md and docs/contributing-evidence.md resolves;
- every ``adoption/manifest.json`` profile id is a row of adoption/README.md's profile table,
  and the row's pin columns equal the coverage computed from the pin files;
- no documented command passes two flags from one argparse mutually exclusive group (read from
  each script's own source, so a new group is covered without editing this file);
- every script path those documents mention exists and is tracked at HEAD;
- a new-host page that mentions a path the pinned release lacks (scripts/release_due.py's
  ``due`` list) says so in the same section ("not in the pinned release").

These are local consistency checks over repository text, not a run of any documented step.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import unittest
from pathlib import Path

from scripts import release_due as rd

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "adoption/manifest.json").read_text(encoding="utf-8"))
SOURCE = MANIFEST["source"]

PIN_DOCS = sorted([*ROOT.glob("adoption/*.md"), *ROOT.glob("adoption/platforms/*.md")])
LINK_DOCS = sorted([*ROOT.glob("adoption/**/*.md"), ROOT / "docs/next-host-stages.md",
                    ROOT / "docs/contributing-evidence.md"])
COMMAND_DOCS = LINK_DOCS
CHECKOUT_PAGES = [ROOT / "adoption/bootstrap.md", ROOT / "adoption/platforms/linux-wsl2.md",
                  ROOT / "adoption/platforms/macos-arm64.md"]
PIN_FILES = {"Linux pins": "adoption/pins-linux-x86_64.json", "macOS pins": "adoption/pins-macos-arm64.json"}
DUE_MARKER = "not in the pinned release"

HASH_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])")
TAG_RE = re.compile(r"(?<![\w.])v\d{4}\.\d{2}\.\d{2}(?:\.\d+)?(?![\w.])")
RELEASE_LABEL = re.compile(r"release[_ ](?:commit|tag)|attested release|pinned release", re.I)
FENCE_RE = re.compile(r"^```.*?^```[ \t]*$", re.M | re.S)
LINK_RE = re.compile(r"\[(?:[^\]\\]|\\.)*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
SCRIPT_MENTION_RE = re.compile(r"(?<![\w./-])((?:\.\./)*(?:scripts|tools|adoption)/[\w./-]+\.(?:py|sh|mjs|js))\b")
SCRIPT_IN_COMMAND_RE = re.compile(r"(?<![\w-])((?:[\w.-]+/)*[A-Za-z_][\w-]*\.py)\b")
FLAG_RE = re.compile(r"(?<![\w-])(--[a-z][\w-]*)")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def paragraphs(text: str) -> list[str]:
    return [block for block in re.split(r"\n[ \t]*\n", text) if block.strip()]


def sections(text: str) -> list[str]:
    """Blocks that start at a Markdown heading (the text before the first heading is one too)."""
    return re.split(r"(?m)^(?=#{1,6} )", text)


def github_slug(heading: str) -> str:
    text = re.sub(r"[`*_]", "", heading.strip().lower())
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    text = FENCE_RE.sub("", path.read_text(encoding="utf-8"))
    return {github_slug(match) for match in re.findall(r"(?m)^#{1,6} +(.+?)\s*#*\s*$", text)}


def pin_ids(pin_file: str) -> set[str]:
    pins = json.loads((ROOT / pin_file).read_text(encoding="utf-8"))
    return {tool["id"] for tool in pins["tools"]}


def coverage_text(component_ids: list[str], pinned: set[str]) -> str:
    covered, total = sum(1 for cid in component_ids if cid in pinned), len(component_ids)
    if covered == total:
        return f"all {total}"
    if covered == 0:
        return f"none of {total}"
    return f"{covered} of {total}"


def profile_table(text: str) -> tuple[list[str], dict[str, list[str]]]:
    section = text.split("## Choose a small starting profile", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("|")]
    header = [cell.strip() for cell in rows[0].strip("|").split("|")]
    table = {}
    for line in rows[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        match = re.fullmatch(r"`([a-z0-9-]+)`", cells[0])
        if match:
            table[match.group(1)] = cells
    return header, table


def exclusive_groups(script: Path) -> list[frozenset[str]]:
    """The long flags of every ``X = parser.add_mutually_exclusive_group()`` in ``script``."""
    tree = ast.parse(script.read_text(encoding="utf-8"))
    groups: set[frozenset[str]] = set()
    for scope in [tree, *[node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]]:
        names = {target.id for node in ast.walk(scope) if isinstance(node, ast.Assign)
                 and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
                 and node.value.func.attr == "add_mutually_exclusive_group"
                 for target in node.targets if isinstance(target, ast.Name)}
        members: dict[str, set[str]] = {}
        for node in ast.walk(scope):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "add_argument" and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in names):
                members.setdefault(node.func.value.id, set()).update(
                    arg.value for arg in node.args
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.startswith("--"))
        groups.update(frozenset(flags) for flags in members.values() if len(flags) > 1)
    return sorted(groups, key=sorted)


def resolve_script(token: str) -> Path | None:
    candidate = ROOT / token.lstrip("./")
    if candidate.is_file():
        return candidate
    matches = [path for base in ("scripts", "tools") for path in (ROOT / base).rglob(Path(token).name)
               if "__pycache__" not in path.parts]
    return matches[0] if len(matches) == 1 else None


def command_segments(text: str) -> list[str]:
    """Shell-like commands: fenced code lines (backslash continuations joined) and inline code spans,
    split at &&, ||, ;, | and $(...)."""
    pieces = []
    for block in FENCE_RE.findall(text):
        body = "\n".join(block.splitlines()[1:-1])
        pieces.extend(re.sub(r"\\\n\s*", " ", body).splitlines())
    pieces.extend(INLINE_CODE_RE.findall(FENCE_RE.sub("", text)))
    segments = []
    for piece in pieces:
        segments.extend(part for part in re.split(r"&&|\|\||;|\||\$\(|\)", piece.split(" #", 1)[0]) if part.strip())
    return segments


def mutually_exclusive_violations(text: str, label: str) -> list[str]:
    found = []
    for segment in command_segments(text):
        for match in SCRIPT_IN_COMMAND_RE.finditer(segment):
            script = resolve_script(match.group(1))
            if script is None:
                continue
            flags = set(FLAG_RE.findall(segment[match.end():]))
            for group in exclusive_groups(script):
                clash = sorted(group & flags)
                if len(clash) > 1:
                    found.append(f"{label}: `{segment.strip()}` combines {' and '.join(clash)} "
                                 f"(mutually exclusive in {rel(script)})")
    return found


def git_tracked() -> set[str] | None:
    result = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, check=False)
    return set(result.stdout.splitlines()) if result.returncode == 0 else None


class ReleasePinQuotesTests(unittest.TestCase):
    def pin_quote_errors(self, text: str, label: str) -> list[str]:
        errors = []
        for block in paragraphs(text):
            if not RELEASE_LABEL.search(block):
                continue
            errors += [f"{label}: quotes release commit {value}, manifest pins {SOURCE['release_commit']}"
                       for value in HASH_RE.findall(block) if value != SOURCE["release_commit"]]
            errors += [f"{label}: quotes release tag {value}, manifest pins {SOURCE['release_tag']}"
                       for value in TAG_RE.findall(block) if value != SOURCE["release_tag"]]
        return errors

    def test_quoted_release_commits_and_tags_match_the_manifest(self):
        errors = [error for path in PIN_DOCS
                  for error in self.pin_quote_errors(path.read_text(encoding="utf-8"), rel(path))]
        self.assertEqual(errors, [])

    def test_the_check_rejects_a_stale_quoted_commit_and_tag(self):
        stale = ("This checks out `source.release_tag` (`v2000.01.01`) at `source.release_commit` "
                 f"(`{'b' * 40}`).")
        self.assertEqual(len(self.pin_quote_errors(stale, "mutant")), 2)

    def test_checkout_pages_derive_the_pin_from_the_manifest(self):
        for path in CHECKOUT_PAGES:
            text = path.read_text(encoding="utf-8")
            with self.subTest(page=rel(path)):
                self.assertIn("['source']['release_tag']", text)
                self.assertIn("['source']['release_commit']", text)
                self.assertIn('test "$(git rev-parse HEAD)" = "$commit"', text)
                # The release check runs on the default branch, before the pinned checkout.
                self.assertLess(text.index("python3 scripts/release_due.py"), text.index('git checkout "$tag"'))


class RelativeLinkTests(unittest.TestCase):
    def link_errors(self, path: Path, text: str) -> list[str]:
        errors = []
        for target in LINK_RE.findall(FENCE_RE.sub("", text)):
            if re.match(r"[a-z][a-z0-9+.-]*:", target, re.I):
                continue
            file_part, _, fragment = target.partition("#")
            destination = (path.parent / file_part).resolve() if file_part else path.resolve()
            if ROOT.resolve() not in destination.parents and destination != ROOT.resolve():
                errors.append(f"{rel(path)}: {target} leaves the repository")
            elif not destination.exists():
                errors.append(f"{rel(path)}: {target} does not exist")
            elif fragment and destination.suffix == ".md" and fragment not in anchors(destination):
                errors.append(f"{rel(path)}: {target} has no heading #{fragment}")
        return errors

    def test_every_relative_link_resolves(self):
        errors = [error for path in LINK_DOCS for error in self.link_errors(path, path.read_text(encoding="utf-8"))]
        self.assertEqual(errors, [])

    def test_the_check_rejects_a_missing_path_and_a_missing_anchor(self):
        mutant = "[gone](no-such-file.md) and [anchor](update.md#no-such-heading) and [ok](update.md)"
        self.assertEqual(len(self.link_errors(ROOT / "adoption/README.md", mutant)), 2)

    def test_the_new_release_section_is_linked_from_every_entry_point(self):
        target = "update.md#moving-a-host-to-a-new-release"
        self.assertIn("moving-a-host-to-a-new-release", anchors(ROOT / "adoption/update.md"))
        for path in ("adoption/README.md", "adoption/bootstrap.md", "docs/next-host-stages.md"):
            with self.subTest(page=path):
                self.assertIn(target, (ROOT / path).read_text(encoding="utf-8"))


class ProfileTableTests(unittest.TestCase):
    def setUp(self):
        self.header, self.table = profile_table((ROOT / "adoption/README.md").read_text(encoding="utf-8"))

    def test_every_manifest_profile_is_a_table_row(self):
        self.assertEqual(sorted(self.table), sorted(profile["id"] for profile in MANIFEST["profiles"]))

    def test_pin_columns_match_the_pin_files(self):
        errors = []
        for profile in MANIFEST["profiles"]:
            row = self.table.get(profile["id"])
            if row is None:
                continue
            for column, pin_file in PIN_FILES.items():
                expected = coverage_text(profile["component_ids"], pin_ids(pin_file))
                actual = row[self.header.index(column)]
                if actual != expected:
                    errors.append(f"{profile['id']} {column}: table says {actual!r}, {pin_file} gives {expected!r}")
        self.assertEqual(errors, [])

    def test_coverage_text_forms(self):
        self.assertEqual(coverage_text(["a", "b"], {"a", "b"}), "all 2")
        self.assertEqual(coverage_text(["a", "b"], set()), "none of 2")
        self.assertEqual(coverage_text(["a", "b", "c"], {"b"}), "1 of 3")


class ExclusiveFlagTests(unittest.TestCase):
    def test_no_documented_command_combines_mutually_exclusive_flags(self):
        errors = [error for path in COMMAND_DOCS
                  for error in mutually_exclusive_violations(path.read_text(encoding="utf-8"), rel(path))]
        self.assertEqual(errors, [])

    def test_groups_are_read_from_the_scripts(self):
        self.assertIn(frozenset({"--write", "--check"}), exclusive_groups(ROOT / "scripts/new_host_grand_list.py"))
        self.assertIn(frozenset({"--strict", "--strict-if-repinned"}), exclusive_groups(ROOT / "scripts/release_due.py"))

    def test_the_check_rejects_the_combined_forms(self):
        for mutant in ("re-runs `new_host_grand_list.py --write --check` in that copy",
                       "```sh\npython3 scripts/new_host_grand_list.py \\\n  --check --write\n```",
                       "`python3 scripts/release_due.py --strict --strict-if-repinned origin/main`"):
            with self.subTest(mutant=mutant):
                self.assertEqual(len(mutually_exclusive_violations(mutant, "mutant")), 1)

    def test_separate_invocations_pass(self):
        text = "```sh\npython3 scripts/new_host_grand_list.py --write\npython3 scripts/new_host_grand_list.py --check\n```"
        self.assertEqual(mutually_exclusive_violations(text, "ok"), [])


class ScriptPathTests(unittest.TestCase):
    def missing(self, path: Path, text: str, tracked: set[str] | None) -> list[str]:
        errors = []
        for mention in sorted(set(SCRIPT_MENTION_RE.findall(text))):
            target = (path.parent / mention).resolve() if mention.startswith("../") else (ROOT / mention).resolve()
            relative = target.relative_to(ROOT.resolve()).as_posix() if ROOT.resolve() in target.parents else mention
            if not target.is_file():
                errors.append(f"{rel(path)}: {mention} does not exist")
            elif tracked is not None and relative not in tracked:
                errors.append(f"{rel(path)}: {mention} exists but is not tracked")
        return errors

    def test_every_documented_script_exists_at_head(self):
        tracked = git_tracked()
        errors = [error for path in COMMAND_DOCS for error in self.missing(path, path.read_text(encoding="utf-8"), tracked)]
        self.assertEqual(errors, [])

    def test_the_check_rejects_a_missing_script(self):
        mutant = "Run `python3 scripts/no_such_script.py --check` and `bash adoption/no-such.sh`."
        self.assertEqual(len(self.missing(ROOT / "adoption/bootstrap.md", mutant, None)), 2)


class UnreleasedStepMarkerTests(unittest.TestCase):
    """A page a host follows at the pinned tag marks steps the tag cannot run yet."""

    PAGES = [ROOT / "adoption/bootstrap.md", *sorted(ROOT.glob("adoption/platforms/*.md"))]

    def unmarked(self, text: str, due: set[str], label: str) -> list[str]:
        errors = []
        for section in sections(text):
            mentioned = sorted(due & rd.referenced([section]))
            if mentioned and DUE_MARKER not in section.lower():
                heading = section.splitlines()[0] if section.strip() else "(top)"
                errors.append(f"{label} section {heading!r} uses {', '.join(mentioned)} without "
                              f"saying \"{DUE_MARKER}\"")
        return errors

    def test_sections_using_unreleased_paths_say_so(self):
        if rd.git("cat-file", "-e", f"{SOURCE['release_commit']}^{{commit}}").returncode:
            self.skipTest(f"release commit {SOURCE['release_commit']} is not in this clone")
        due = set(rd.due(SOURCE["release_commit"]))
        errors = [error for path in self.PAGES
                  for error in self.unmarked(path.read_text(encoding="utf-8"), due, rel(path))]
        self.assertEqual(errors, [])

    def test_the_check_rejects_an_unmarked_section(self):
        text = "## Services\n\nRun `tools/adoption/render_launchd.py`.\n\n## Other\n\nNothing due here.\n"
        self.assertEqual(len(self.unmarked(text, {"tools/adoption/render_launchd.py"}, "mutant")), 1)
        marked = text.replace("Run ", "Not in the pinned release: run ")
        self.assertEqual(self.unmarked(marked, {"tools/adoption/render_launchd.py"}, "ok"), [])


if __name__ == "__main__":
    unittest.main()
