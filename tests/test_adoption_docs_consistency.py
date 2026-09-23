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
  and the row's pin columns equal the coverage computed from the pin files; where the pinned
  release's own pin files give a different coverage, the cell says so ("all 8 (7 of 8 at
  `vT`)"), and any such note naming a tag this clone has is checked against that tag;
- no documented command passes two flags from one argparse mutually exclusive group (read from
  each script's own source, so a new group is covered without editing this file) or a pair
  listed in ``EXCLUSIVE_IN_EFFECT`` (independent flags where one silently wins);
- every script path those documents mention exists and is tracked at HEAD;
- a new-host page unit (a heading section or a top-level numbered step) that mentions a path the
  pinned release lacks (scripts/release_due.py's ``due`` list) says "added after `<release_tag>`";
- a new-host page that mentions an install input (bootstrap script or pin file) whose content
  differs between the pinned release and HEAD says "changed after `<release_tag>`" in a unit
  that mentions it. release_due.py only reports missing paths, so this is the check that sees
  a changed script.

The markers name the release they were written against, so they stay true in every later
checkout: at a newer release they are history, and a re-pin needs no documentation edit for
them (they may be dropped in any later PR).

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
TAG = r"v\d{4}\.\d{2}\.\d{2}(?:\.\d+)?"
MARKER_RE = re.compile(rf"\b(added|changed) after `?({TAG})`?", re.I)
COVERAGE_RE = re.compile(rf"^(all \d+|none of \d+|\d+ of \d+)(?: \((all \d+|none of \d+|\d+ of \d+) at `?({TAG})`?\))?$")
HISTORICAL_TAG_RE = re.compile(rf"(?:\b(?:added|changed) after|\d+\)? at) `?{TAG}`?", re.I)
INSTALL_INPUTS = ("adoption/bootstrap-linux.sh", "adoption/bootstrap-macos.sh",
                  "adoption/pins-linux-x86_64.json", "adoption/pins-macos-arm64.json")
# Independent store_true flags where one silently wins, so argparse cannot reject the pair.
EXCLUSIVE_IN_EFFECT = {"component_matrix.py": [frozenset({"--write", "--check"})]}  # write_mode = write and not check

HASH_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])")
TAG_RE = re.compile(rf"(?<![\w.]){TAG}(?![\w.])")
RELEASE_LABEL = re.compile(r"release[_ ](?:commit|tag)|attested release|pinned release", re.I)
FENCE_RE = re.compile(r"^[ \t]*```.*?^[ \t]*```[ \t]*$", re.M | re.S)  # list items indent their fences
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


def units(text: str) -> list[str]:
    """Heading sections, each split again at top-level numbered steps (``1. ...`` at column 0), so
    a marker in one step never covers another step of the same page."""
    return [unit for section in sections(text) for unit in re.split(r"(?m)^(?=\d+\. )", section)]


def show(commit: str, path: str) -> str | None:
    result = rd.git("show", f"{commit}:{path}")
    return result.stdout if result.returncode == 0 else None


def resolve_commit(ref: str) -> str | None:
    result = rd.git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return result.stdout.strip() if result.returncode == 0 else None


def release_present() -> bool:
    return rd.git("cat-file", "-e", f"{SOURCE['release_commit']}^{{commit}}").returncode == 0


def github_slug(heading: str) -> str:
    text = re.sub(r"[`*]", "", heading.strip().lower())
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    text = FENCE_RE.sub("", path.read_text(encoding="utf-8"))
    return {github_slug(match) for match in re.findall(r"(?m)^#{1,6} +(.+?)\s*#*\s*$", text)}


def pin_ids(pin_file: str, commit: str | None = None) -> set[str]:
    text = (ROOT / pin_file).read_text(encoding="utf-8") if commit is None else show(commit, pin_file)
    return {tool["id"] for tool in json.loads(text)["tools"]}


def coverage_at(commit: str, profile_id: str, pin_file: str) -> str | None:
    """Coverage of ``profile_id`` by ``pin_file`` as that commit's own manifest and pins give it."""
    manifest, pins = show(commit, "adoption/manifest.json"), show(commit, pin_file)
    if manifest is None or pins is None:
        return None
    profiles = {profile["id"]: profile["component_ids"] for profile in json.loads(manifest)["profiles"]}
    if profile_id not in profiles:
        return None
    return coverage_text(profiles[profile_id], {tool["id"] for tool in json.loads(pins)["tools"]})


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
            for group in [*exclusive_groups(script), *EXCLUSIVE_IN_EFFECT.get(script.name, [])]:
                clash = sorted(group & flags)
                if len(clash) > 1:
                    found.append(f"{label}: `{segment.strip()}` combines {' and '.join(clash)} "
                                 f"(mutually exclusive in effect in {rel(script)})")
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
            block = HISTORICAL_TAG_RE.sub("", block)  # "added after `vT`" names the tag it was written against
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

    def test_historical_markers_are_not_pin_quotes(self):
        text = ("The pinned release is `source.release_tag`; this step was added after `v2000.01.01` "
                "and the script changed after v2000.01.01.")
        self.assertEqual(self.pin_quote_errors(text, "ok"), [])

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

    def cell_errors(self, profile_id: str, component_ids: list[str], column: str, cell: str,
                    release_commit: str | None) -> list[str]:
        """``cell`` is HEAD's coverage, plus "(X at `vT`)" when the pinned release (or another tag
        this clone has) differs. ``release_commit`` None means the pinned release is not in this
        clone, so only HEAD's part and the note's form are checked."""
        pin_file = PIN_FILES[column]
        label = f"{profile_id} {column}"
        match = COVERAGE_RE.match(cell)
        if match is None:
            return [f"{label}: {cell!r} is not 'all N', 'none of N' or 'X of N', optionally '(X of N at `vT`)'"]
        head, noted, noted_tag = match.groups()
        errors = []
        expected_head = coverage_text(component_ids, pin_ids(pin_file))
        if head != expected_head:
            errors.append(f"{label}: table says {head!r}, {pin_file} gives {expected_head!r}")
        if release_commit is not None:
            at_release = coverage_at(release_commit, profile_id, pin_file)
            if at_release is not None and at_release != expected_head and (noted, noted_tag) != (at_release, SOURCE["release_tag"]):
                errors.append(f"{label}: the pinned release {SOURCE['release_tag']} gives {at_release!r}; "
                              f"the cell must end '({at_release} at `{SOURCE['release_tag']}`)'")
        if noted_tag is not None:
            commit = release_commit if noted_tag == SOURCE["release_tag"] else resolve_commit(noted_tag)
            actual = coverage_at(commit, profile_id, pin_file) if commit else None
            if actual is not None and actual != noted:
                errors.append(f"{label}: note says {noted!r} at {noted_tag}, that tag gives {actual!r}")
        return errors

    def test_pin_columns_match_the_pin_files(self):
        release_commit = SOURCE["release_commit"] if release_present() else None
        errors = []
        for profile in MANIFEST["profiles"]:
            row = self.table.get(profile["id"])
            if row is None:
                continue
            for column in PIN_FILES:
                errors += self.cell_errors(profile["id"], profile["component_ids"], column,
                                           row[self.header.index(column)], release_commit)
        self.assertEqual(errors, [])

    def test_the_cell_check_rejects_wrong_and_missing_release_notes(self):
        if not release_present():
            self.skipTest(f"release commit {SOURCE['release_commit']} is not in this clone")
        commit, tag = SOURCE["release_commit"], SOURCE["release_tag"]
        for profile in MANIFEST["profiles"]:
            for column, pin_file in PIN_FILES.items():
                head = coverage_text(profile["component_ids"], pin_ids(pin_file))
                at_release = coverage_at(commit, profile["id"], pin_file)
                if at_release is None or at_release == head:
                    continue
                with self.subTest(profile=profile["id"], column=column):
                    args = (profile["id"], profile["component_ids"], column)
                    self.assertEqual(self.cell_errors(*args, f"{head} ({at_release} at `{tag}`)", commit), [])
                    self.assertEqual(len(self.cell_errors(*args, head, commit)), 1)          # note missing
                    self.assertEqual(len(self.cell_errors(*args, f"{head} ({head} at `{tag}`)", commit)), 2)
                    self.assertEqual(len(self.cell_errors(*args, "junk", commit)), 1)
                return
        self.skipTest("no profile's coverage differs between the pinned release and HEAD")

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
                       "`python3 scripts/component_matrix.py --check --write`",
                       "```sh\npython3 scripts/new_host_grand_list.py \\\n  --check --write\n```",
                       "`python3 scripts/release_due.py --strict --strict-if-repinned origin/main`"):
            with self.subTest(mutant=mutant):
                self.assertEqual(len(mutually_exclusive_violations(mutant, "mutant")), 1)

    def test_indented_fences_inside_list_items_are_read(self):
        mutant = "5. **Refresh.**\n\n   ```sh\n   python3 scripts/new_host_grand_list.py \\\n     --write --check\n   ```\n"
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
    """A page a host follows at the pinned tag marks steps the tag cannot run as documented."""

    PAGES = [ROOT / "adoption/bootstrap.md", *sorted(ROOT.glob("adoption/platforms/*.md"))]

    @staticmethod
    def marked(unit: str, kind: str, tag: str) -> bool:
        return any(found_kind.lower() == kind and found_tag == tag for found_kind, found_tag in MARKER_RE.findall(unit))

    def unmarked(self, text: str, due: set[str], label: str, tag: str) -> list[str]:
        errors = []
        for unit in units(text):
            mentioned = sorted(due & rd.referenced([unit]))
            if mentioned and not self.marked(unit, "added", tag):
                heading = unit.strip().splitlines()[0] if unit.strip() else "(top)"
                errors.append(f"{label} unit {heading[:70]!r} uses {', '.join(mentioned)} without "
                              f"saying \"added after `{tag}`\"")
        return errors

    def unmarked_changes(self, text: str, changed: list[str], label: str, tag: str) -> list[str]:
        errors = []
        for path in changed:
            names = (path, Path(path).name)
            mentioning = [unit for unit in units(text) if any(name in unit for name in names)]
            if mentioning and not any(self.marked(unit, "changed", tag) for unit in mentioning):
                errors.append(f"{label} mentions {path}, which changed after {tag}, but no unit that "
                              f"mentions it says \"changed after `{tag}`\"")
        return errors

    def require_release(self):
        if not release_present():
            self.skipTest(f"release commit {SOURCE['release_commit']} is not in this clone")

    def test_units_using_unreleased_paths_say_so(self):
        self.require_release()
        due = set(rd.due(SOURCE["release_commit"]))
        errors = [error for path in self.PAGES
                  for error in self.unmarked(path.read_text(encoding="utf-8"), due, rel(path), SOURCE["release_tag"])]
        self.assertEqual(errors, [])

    def test_pages_mentioning_a_changed_install_input_say_so(self):
        self.require_release()
        changed = [path for path in INSTALL_INPUTS
                   if show(SOURCE["release_commit"], path) != (ROOT / path).read_text(encoding="utf-8")]
        errors = [error for path in self.PAGES
                  for error in self.unmarked_changes(path.read_text(encoding="utf-8"), changed, rel(path),
                                                     SOURCE["release_tag"])]
        self.assertEqual(errors, [])

    def test_the_check_rejects_an_unmarked_unit(self):
        due = {"tools/adoption/render_launchd.py"}
        text = "## Services\n\nRun `tools/adoption/render_launchd.py`.\n\n## Other\n\nNothing due here.\n"
        self.assertEqual(len(self.unmarked(text, due, "mutant", "v2000.01.01")), 1)
        marked = text.replace("Run ", "Added after `v2000.01.01`: run ")
        self.assertEqual(self.unmarked(marked, due, "ok", "v2000.01.01"), [])
        # A marker naming an older release does not cover a path still missing from the current one.
        self.assertEqual(len(self.unmarked(marked, due, "mutant", "v2000.02.01")), 1)

    def test_a_marker_in_one_numbered_step_does_not_cover_another(self):
        due = {"tools/adoption/render_launchd.py"}
        text = ("# Bootstrap\n\n**Step 0.** Steps marked added after `v2000.01.01` wait for a release.\n\n"
                "1. Install.\n\n5. **Services.** Run `tools/adoption/render_launchd.py`.\n")
        self.assertEqual(len(self.unmarked(text, due, "mutant", "v2000.01.01")), 1)

    def test_the_check_rejects_an_undisclosed_install_change(self):
        text = ("## Install\n\nRun `adoption/bootstrap-macos.sh`.\n\n## Usage\n\n"
                "`bootstrap-macos.sh --plan` prints the pins.\n")
        changed = ["adoption/bootstrap-macos.sh"]
        self.assertEqual(len(self.unmarked_changes(text, changed, "mutant", "v2000.01.01")), 1)
        disclosed = text.replace("prints the pins.", "prints the pins (changed after `v2000.01.01`).")
        self.assertEqual(self.unmarked_changes(disclosed, changed, "ok", "v2000.01.01"), [])
        self.assertEqual(self.unmarked_changes("## Other\n\nNo mention.\n", changed, "ok", "v2000.01.01"), [])


if __name__ == "__main__":
    unittest.main()
