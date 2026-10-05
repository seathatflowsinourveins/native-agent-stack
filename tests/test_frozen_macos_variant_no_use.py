"""A tripwire for direct references to the frozen macOS application artifact, behind Dependabot alert 16's dismissal.

ARTIFACT (below) keeps the run summary and, under variant/, the package.json and pnpm-lock.yaml of the application
that ran on the Mac on 2026-09-24. The lock pins next 16.3.5, in the range of GHSA-vcvr-r3jv-pc5j (critical, fixed in
16.3.6). .github/osv-scanner-frozen-macos.toml excepts that advisory for this one lock until 2026-12-24, and Dependabot
alert 16 on the variant's package.json was dismissed as not_used
(docs/decisions/2026-09-22-github-automation-closure.md, evidence/receipts/dependabot-alert-16-dismissal-20261003.json),
because nothing in this repository installs, builds or serves the variant. These tests fail when:

- the artifact directory holds a file besides run-summary.json, variant/package.json and variant/pnpm-lock.yaml
  (ARTIFACT_FILES), on disk or in Git, apart from OS metadata files (OS_METADATA). The whole directory is watched, not
  only variant/, because a script beside variant/ reaches the lock by a relative path (cd variant) that never names the
  directory. Tracked paths are compared in any ASCII letter case, since a case-insensitive file system checks a
  differently cased path out into the same directory. A missing file and an absent directory pass, and the lock tests
  pass once both variant files are gone: removing the variant (the closure record's exit path, "the frozen lock stops
  being kept") or the artifact is not a use;
- a scanned file (Scope, below) names the artifact directory on a line that PINNED_LINES does not pin. The match is the
  directory's name as bytes (TOKEN) in any ASCII letter case, both sides lower-cased, so a path through the parent
  directory, a join of the name and "variant" or a differently cased path counts. A pin is the sha256 of one
  referencing line exactly as written, stripped, so a pinned file may gain no new referencing line either;
- a pinned line is not found where it is pinned, so a scope rule that stops reading a pinned file cannot pass silently;
- the variant's package.json or lock no longer pins next 16.3.5, or the lock's sha256 differs from the one FROZEN_LOCKS
  in tests/test_osv_lockfile_coverage.py binds (read from that module's syntax tree, not imported);
- the frozen OSV config (FROZEN_CONFIG) holds no exception for the advisory (ADVISORY), more than one, or one whose
  ignoreUntil is not 2026-12-24 (REVIEW_DATE) or that has a key besides id, ignoreUntil and reason (EXCEPTION_KEYS):
  the trigger to recheck alert 16 when that exception is renewed, changed or removed. The exception's reason line names
  the artifact and is pinned, so a changed reason fails too;
- git ls-files cannot run: the tripwire fails rather than skips.

Scope. Every file that git ls-files lists is scanned except four excluded classes: Markdown documentation (*.md in any
directory but the client configuration directories below), retained evidence and the hash registry (evidence/** and
manifests/evidence.json) and catalog data (catalogs/**). Inside those classes the scan reads only the files that
is_configuration_or_script recognises: the names in CONFIG_NAMES (package.json, lerna.json, nx.json, turbo.json,
rush.json, deno.json, deno.jsonc, devcontainer.json and .devcontainer.json), tsconfig*.json and jsconfig*.json, every
file under a directory in CONFIG_DIRECTORIES, the suffixes in CONFIG_SUFFIXES (.toml, .yml, .yaml) and SCRIPT_SUFFIXES,
the names in BUILD_NAMES, Dockerfile*, Containerfile* and *.dockerfile, content that starts with #!, Git's executable
mode, and symbolic links. CONFIG_DIRECTORIES holds .devcontainer and the client configuration directories .claude,
.codex and .agents, matched at any depth: an agent, command or skill definition there is Markdown whose YAML
frontmatter can declare hooks or tools that the client runs, so it is configuration, not documentation, and Markdown is
excluded only outside those directories. Names and suffixes are compared as written; the directory names in
CONFIG_DIRECTORIES are compared in any ASCII letter case, since a client on a case-insensitive file system loads
.CLAUDE or .Agents as it loads .claude or .agents. Any other file
in an excluded class is not scanned, whatever it holds: a JSON launch configuration there, such as an mcpServers entry,
is not read. For a symbolic link the scan reads the path that the link holds, not the file it points to, and a file
that cannot be read (a submodule, or a file missing from the work tree) is skipped.

Limits. This is a tripwire for direct references; it does not prove that nothing uses the lock. It misses a route that
reaches the variant without spelling the directory's name in a scanned file: a step that iterates the paths of the OSV
inventory or of FROZEN_LOCKS, a glob such as evidence/artifacts/*/variant, a name assembled from fragments or held
outside the repository, a Markdown recipe whose commands someone runs, a file in an excluded class that the scan does
not read (such as that launch configuration) or that a script reads the path from, and text that does not hold the
name as ASCII-compatible bytes. Its mutation checks (the receipt's guard_mutation_checks) confirmed that the glob,
inventory-loop, fragment, Markdown-recipe and evidence/** launch-configuration cases pass it. The guard is also only as
strong as review of this module: any part of it (PINNED_LINES, REVIEW_DATE, ARTIFACT_FILES, the recognisers, the
excluded classes, or the module itself) can be changed or removed in the same change that adds a use, and the main
ruleset (.github/main-ruleset.json) sets required_approving_review_count 0 and require_code_owner_review false, so no
code owner has to review that edit. That is why the dismissal is also tied to the OSV exception's review: recheck
alert 16 when that exception is renewed, changed or removed (the REVIEW_DATE test or the pinned reason line fails
then), or when this tripwire fails (the overturn in the receipt and in the closure record).

A failure that can mean a new use says to reopen Dependabot alert 16 and remove the frozen OSV exception before
installing, building or serving from the lock. A new line that only describes or checks the artifact may be pinned
instead, after review: the failure lists its file, line number, sha256 and text.
"""

from __future__ import annotations

import ast
import datetime
import functools
import hashlib
import json
import os
import re
import string
import subprocess
import tomllib
import unittest
from collections import Counter
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
# The one line of this module that names the artifact; PINNED_LINES pins it like the others.
ARTIFACT = "evidence/artifacts/macos-application-20260924"
# Lower-case, and compared with lower-cased text (names_artifact); the pins hash the lines as written.
TOKEN = PurePosixPath(ARTIFACT).name.lower().encode()
VARIANT = f"{ARTIFACT}/variant"
MANIFEST = f"{VARIANT}/package.json"
LOCK = f"{VARIANT}/pnpm-lock.yaml"
FROZEN_FILES = ["package.json", "pnpm-lock.yaml"]
# Every file the artifact directory may hold, relative to it: the run summary and the two frozen files of the variant.
ARTIFACT_FILES = ["run-summary.json", "variant/package.json", "variant/pnpm-lock.yaml"]
OS_METADATA = {".DS_Store", "Thumbs.db"}
ASCII_LOWER = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)
COVERAGE_TESTS = "tests/test_osv_lockfile_coverage.py"
THIS_MODULE = "tests/test_frozen_macos_variant_no_use.py"
NEXT_VERSION = "16.3.5"
# The frozen OSV exception that the recheck of alert 16 is tied to, and the date it ends on.
FROZEN_CONFIG = ".github/osv-scanner-frozen-macos.toml"
ADVISORY = "GHSA-vcvr-r3jv-pc5j"
REVIEW_DATE = datetime.date(2026, 12, 24)
EXCEPTION_KEYS = {"id", "ignoreUntil", "reason"}

REOPEN = (
    "reopen Dependabot alert 16 and remove the frozen OSV exception (its config .github/osv-scanner-frozen-macos.toml, "
    "its inventory key in .github/osv-scanner-lockfiles.json and its FROZEN_LOCKS row in "
    "tests/test_osv_lockfile_coverage.py) before installing, building or serving from the lock "
    "(docs/decisions/2026-09-22-github-automation-closure.md, 'Dependabot alert 16')"
)
NEW_REFERENCE = (
    "A scanned file newly names the frozen macOS artifact (lines above). Treat it as a use: " + REOPEN + ". Only a "
    "line that describes or checks the artifact without using it may be pinned in PINNED_LINES instead, after review."
)
STALE_PIN = (
    "A pinned line was not found where PINNED_LINES expects it (above): the scope rules no longer read that file, or "
    "the line changed or was removed. Restore the scope, or re-pin after review; if the variant and its frozen OSV "
    "exception were removed together (the closure record's exit path), remove this module with them."
)
RECHECK = (
    "recheck Dependabot alert 16 (reopen it unless the renewed exception's reasoning still holds) and update this "
    "pinned date"
)

# Every scanned file that names the artifact when this module was last changed (main at d2777ee7, plus this module),
# with the sha256 of each referencing line after strip() and what the line is. A file may hold each pinned line as many
# times as it is listed, and no other line that names the artifact.
# The workflow's assignment check, the last clause of its jq -e block since the retired WSL group was removed on
# 2026-10-04; SCAN_ASSIGNMENT_THREE_GROUP is the same line with the trailing " and" of the three-group block (#622,
# #673), which the retained copies of that step keep.
SCAN_ASSIGNMENT = "ef6e115280f50c59ce304676bed671f417a6594cd3f461ec82877d07fea44e0f"
SCAN_ASSIGNMENT_THREE_GROUP = "351433a1e19559754ec9f115b4ed30b44af29f8312a2db9015c75d808cfc8eeb"
OSV_SCANNED ="51ca9efbdc11db2f25aecb6526904e1a517f22246cc5820fb245d04a5bedca55"
OSV_FILTERED = "99ed1345f35841de29e655641a9a1446c8d822c5f88da1be4d3b796b197a211e"
OSV_JSON_SOURCE = "6bb997ea6522f0ee3b0465bb074557ef270a657874536028b254da3b8dcfeea1"
# A JSON "path" member naming the variant lock, the variant manifest or the run summary (the same line in each file).
LOCK_PATH = "e18dc9bbb90c041c65d7d610d6c8ba920247f6a774f1e770337cb084ada10cb2"
MANIFEST_PATH = "3a6d91b040d5bb3cce275eeeb08484a60fcffff3f4809f0f945bb58a5afeed07"
RUN_SUMMARY_PATH = "58fcf5ef82c52b23c656d596ef8cb255ae4711320d86c7599b4b80d053b2ca95"
EXPERIMENT = "blueprints/convergence-practice/application-delivery/experiment-macos-20260924.json"
RELOCK = "blueprints/runtime-workers/openhands/evidence/relock-2026-09-30-"
# The 2026-10-03 port of the OSV split-scan hardening (#673, porting #555) retains its own copy of the same control.
SPLIT_PORT = "blueprints/runtime-workers/openhands/evidence/relock-2026-10-03-osv-split-hardening."
RETIREMENT = "evidence/artifacts/wsl-retrieval-retirement-20261003/"
PINNED_LINES: dict[str, list[tuple[str, str]]] = {
    ".github/dependabot.yml": [
        ("0aff72e75928d5620d72d7ca2d8b83710b80b66df2fb13bbcd1efbebc8fd1385", "comment on the frozen npm manifests"),
    ],
    ".github/osv-scanner-frozen-macos.toml": [
        ("b1da0e974ad07fe290e4eb8ab11fed6c9542794f21952c417e4e0cc347a7f510", "header comment naming its one lock"),
        ("28cf96a6b02e884b9ea3fdd019309d8126202a0687cce8f84d871224ecd15206", "the exception's reason"),
    ],
    ".github/osv-scanner-lockfiles.json": [
        (LOCK_PATH, "the frozen lock's inventory key"),
        (MANIFEST_PATH, "the variant manifest's inventory key"),
        ("b8371a517d178a9744e3644d8270dfff5c1efabc0909c35719ac26ebde44fd11", "that manifest's lockfile field"),
    ],
    # The OSV job's check that the frozen config is assigned to this lock alone.
    ".github/workflows/security-scan.yml": [(SCAN_ASSIGNMENT, "the frozen config's assignment check")],
    # The convergence record of the 2026-09-24 run: hashed paths in frozen_inputs and in the observations' artifacts.
    EXPERIMENT: [
        (LOCK_PATH, "frozen_inputs.sources: the variant lock"),
        (MANIFEST_PATH, "frozen_inputs.inputs: the variant manifest"),
        *[(RUN_SUMMARY_PATH, "observations 0-14, artifacts: the run summary")] * 15,
        *[(MANIFEST_PATH, "observations 2, 3 and 14, artifacts: the variant manifest")] * 3,
        *[(LOCK_PATH, "observations 2, 3 and 14, artifacts: the variant lock")] * 3,
    ],
    # Retained OSV outputs and transcripts of the 2026-09-30 relocks.
    RELOCK + "litellm.osv-after.frozen.txt": [
        (OSV_SCANNED, "OSV's 'Scanned' line for the frozen lock"),
        (OSV_FILTERED, "OSV's 'filtered out' line quoting the reason"),
    ],
    RELOCK + "litellm.osv-before.frozen.txt": [
        (OSV_SCANNED, "OSV's 'Scanned' line for the frozen lock"),
        (OSV_FILTERED, "OSV's 'filtered out' line quoting the reason"),
    ],
    RELOCK + "urllib3.cross-family-rubric-1.txt": [
        ("39349ce36dc2c751dbba595989243b623e0c1b4650ab0f19b3dfe0b5507450d2", "the rubric's context paragraph"),
    ],
    RELOCK + "urllib3.osv-after-noconfig.err": [(OSV_SCANNED, "OSV's 'Scanned' line for the frozen lock")],
    RELOCK + "urllib3.osv-after-noconfig.json": [(OSV_JSON_SOURCE, "OSV's JSON source path of the frozen lock")],
    RELOCK + "urllib3.osv-main.err": [(OSV_SCANNED, "OSV's 'Scanned' line for the frozen lock")],
    RELOCK + "urllib3.osv-main.json": [(OSV_JSON_SOURCE, "OSV's JSON source path of the frozen lock")],
    RELOCK + "urllib3.osv-split-controls.py.txt": [
        ("3612aae3ccb881f49e31d0e56d0ef3e8db05e86a25416e0e7bb5057221b30454", "the retained control's FROZEN constant"),
    ],
    # The same constant in the port's retained control: it names the lock that the frozen-config scan control scans.
    SPLIT_PORT + "osv-split-controls.py.txt": [
        ("3612aae3ccb881f49e31d0e56d0ef3e8db05e86a25416e0e7bb5057221b30454", "the retained control's FROZEN constant"),
    ],
    RELOCK + "urllib3.txt": [
        ("6f047ab824483b5f8af7d21d546df60eb0b0dc07c66e82bb510451dd4443cd31", "the ordinary-config scan command"),
        ("686c1f260638adc0461833b0cf31ce2f40bdbd3bcbfc0674a00df09d6981d19c", "the empty-config scan command"),
        ("6b44895e5f9167fd454b3baf487537fce5b6e1844ae76dd60743a517485ed72f", "the git ls-tree command"),
        ("010d61366d7b8e9f0fac0c615c014b7540f8d0429e60e0ee5ca2cacad42d7669", "its package.json output line"),
        ("c0e4280eb6ceb47a4d878d9d791c6bd2d01c7231e04c6e1d5007b4bf8908aeb5", "its pnpm-lock.yaml output line"),
        ("174f14072efef99114e2e30a9e3c0ca2721e91afb93e20f71d50afdfa056befd", "the git log command"),
        ("2f7f54edaa94f0aadec8c6848f94a7107e8d5452ed55a30b63e31a387bb28024", "the git grep -l command"),
        ("679a3eda94b7c4430bb1ec4ce1a0ab1dbff6257fa7bc629b756f163d33513bf9", "the git grep next/og command"),
        ("7b2c2758e86b41f5fc866f571a14ae82362dc1842ba449d14bcbfd1227b89a88", "the git show next@ command"),
        ("bad298b772569a90a4f5c2d689f2d5faa8dd35f3fbbf6221ba420fbc9ccf2ce0", "the sha256sum command"),
        ("4dff833e9e8f16e2cebb1c793412ea3a8c4789d909c795e3cbbaa4fbfbf664b4", "its output line"),
        ("db08ced20b9691d8e4fa52c06d1c74869eaca358a67ea38d03bc89cf7b7a5953", "the frozen entry's --lockfile argument"),
    ],
    # Retained copies of the security-scan.yml scan step (#622's evidence): scripts, so scanned inside evidence/**.
    RETIREMENT + "completion-workflow-scan.sh": [(SCAN_ASSIGNMENT_THREE_GROUP, "the copied assignment check")],
    RETIREMENT + "final-scan-workflow-scan.sh": [(SCAN_ASSIGNMENT_THREE_GROUP, "the copied assignment check")],
    # FROZEN_LOCKS binds the lock to its OSV config, advisory and sha256.
    COVERAGE_TESTS: [
        ("af7168e33bdbbc62c9508daa9d89c98155b510026be7f1e9d0a64e110e9659d9", "the FROZEN_LOCKS key"),
        # #673's split-scan mutants carry a copy of the workflow's assignment check, to prove it keeps this lock alone.
        (SCAN_ASSIGNMENT, "the split-scan test's copy of the assignment check"),
    ],
    THIS_MODULE: [("48df9b77f3b81b77dbab7d9dd55a4397fc1b056bd009e62988bc3475ef2d045e", "this module's ARTIFACT line")],
    # PR #489's gate-reads set diff lists each path of two protected-set derivations; two entries are the frozen
    # lock as a listed path (describes the derivation's output; installs, builds and serves nothing).
    "blueprints/runtime-workers/openhands/evidence/gate-reads-set-diff-20261004.json": [
        ("798ac0438b0cc820dd0f2e5c9ddc05f97f0091c08e2ffdf9f4178edb8cce3d7f", "a protected-set listing entry, base derivation"),
        ("798ac0438b0cc820dd0f2e5c9ddc05f97f0091c08e2ffdf9f4178edb8cce3d7f", "a protected-set listing entry, head derivation"),
    ],
}

# The excluded classes besides *.md: retained evidence, the hash registry and catalog data. A file in an excluded class
# is outside the scan unless is_configuration_or_script recognises it; nothing else there is read, whatever it holds.
RECORD_TOP_DIRECTORIES = {"evidence", "catalogs"}
RECORD_FILES = {"manifests/evidence.json"}
# Workspace and tool configuration that the scan recognises by name, beside the YAML and TOML suffixes.
CONFIG_NAMES = {
    "package.json", "lerna.json", "nx.json", "turbo.json", "rush.json", "deno.json", "deno.jsonc",
    "devcontainer.json", ".devcontainer.json",
}
# Directories, at any depth, whose every file is configuration: development-container definitions, and the client
# configuration of Claude Code (.claude), the Codex CLI (.codex) and agent skills (.agents, which Codex loads), where an
# agent, command or skill definition is Markdown whose YAML frontmatter can declare hooks or tools that the client runs.
CONFIG_DIRECTORIES = {".devcontainer", ".claude", ".codex", ".agents"}
CONFIG_SUFFIXES = {".toml", ".yml", ".yaml"}
SCRIPT_SUFFIXES = {
    ".sh", ".bash", ".zsh", ".ksh", ".fish", ".ps1", ".psm1", ".bat", ".cmd", ".py", ".pyw", ".js", ".mjs", ".cjs",
    ".jsx", ".ts", ".mts", ".cts", ".tsx", ".rb", ".pl", ".lua", ".go", ".rs", ".mk",
}
BUILD_NAMES = {"Makefile", "makefile", "GNUmakefile", "Justfile", "justfile", "Procfile", "Rakefile", "Taskfile"}
EXECUTABLE_MODE = "100755"
SYMLINK_MODE = "120000"


class GitUnavailable(Exception):
    """git ls-files could not run, so the tracked files are unknown."""


def is_record(name: str) -> bool:
    """Whether a tracked path is in an excluded class: *.md, evidence/**, manifests/evidence.json or catalogs/**."""
    pure = PurePosixPath(name)
    return pure.name.endswith(".md") or pure.parts[0] in RECORD_TOP_DIRECTORIES or name in RECORD_FILES


def is_configuration_or_script(name: str, mode: str, content: bytes) -> bool:
    """Whether the scan recognises a tracked file as configuration, a script or a symbolic link, by its name or suffix
    (compared as written), a client configuration directory (compared in any ASCII letter case), its first bytes or its
    Git mode; such a file is read inside the excluded classes too, Markdown under a client configuration directory
    included."""
    pure = PurePosixPath(name)
    return (pure.name in CONFIG_NAMES or pure.suffix in CONFIG_SUFFIXES
            or not CONFIG_DIRECTORIES.isdisjoint(fold_ascii(part) for part in pure.parts[:-1])
            or (pure.name.startswith(("tsconfig", "jsconfig")) and pure.suffix == ".json")
            or pure.suffix in SCRIPT_SUFFIXES or pure.name in BUILD_NAMES
            or pure.name.startswith(("Dockerfile", "Containerfile")) or pure.name.endswith(".dockerfile")
            or mode in {EXECUTABLE_MODE, SYMLINK_MODE} or content.startswith(b"#!"))


def in_scope(name: str, mode: str, content: bytes) -> bool:
    """Whether the tripwire scans a tracked file: every file outside the excluded classes, and inside them only what
    is_configuration_or_script recognises."""
    return not is_record(name) or is_configuration_or_script(name, mode, content)


def names_artifact(text: bytes) -> bool:
    """Whether text names the artifact directory, in any ASCII letter case (TOKEN is lower-case)."""
    return TOKEN in text.lower()


@functools.lru_cache(maxsize=None)
def tracked_entries() -> tuple[tuple[str, str], ...]:
    """(path, mode) of every file in Git's index, read without the GIT_* variables a Git hook sets, so that the listing
    is this checkout's (as tracked_files in tests/test_osv_lockfile_coverage.py does)."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    try:
        listing = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "--stage", "-z"], env=environment, capture_output=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", None) or b""
        detail = detail.decode("utf-8", "replace").strip() if isinstance(detail, bytes) else str(detail)
        raise GitUnavailable(
            f"git ls-files could not run in {ROOT} ({error}{': ' + detail if detail else ''}). This tripwire reads the "
            "tracked files and fails instead of skipping without them (a skipped guard is no guard in the required "
            "job): run it in a Git checkout with git on PATH."
        ) from error
    entries = {}
    for record in listing.stdout.split(b"\0"):
        if record:
            meta, _, path = record.partition(b"\t")
            entries[os.fsdecode(path)] = meta.split(b" ", 1)[0].decode("ascii")
    return tuple(sorted(entries.items()))


def tracked_or_fail(test: unittest.TestCase) -> tuple[tuple[str, str], ...]:
    try:
        return tracked_entries()
    except GitUnavailable as error:
        test.fail(str(error))


@functools.lru_cache(maxsize=None)
def scan() -> dict[str, tuple[tuple[int, bytes], ...]]:
    """Every scanned tracked file that names the artifact, with its referencing lines (line number, stripped bytes as
    written)."""
    found = {}
    for name, mode in tracked_entries():
        path = ROOT / name
        try:
            content = os.fsencode(os.readlink(path)) if path.is_symlink() else path.read_bytes()
        except OSError:  # a submodule's directory, or a file deleted from the work tree
            continue
        if names_artifact(content) and in_scope(name, mode, content):
            found[name] = tuple(
                (number, line.strip()) for number, line in enumerate(content.splitlines(), 1) if names_artifact(line)
            )
    return found


def scan_or_fail(test: unittest.TestCase) -> dict[str, tuple[tuple[int, bytes], ...]]:
    try:
        return scan()
    except GitUnavailable as error:
        test.fail(str(error))


def line_digest(line: bytes) -> str:
    return hashlib.sha256(line).hexdigest()


def variant_removed() -> bool:
    """Neither frozen file is on disk: the variant was removed, which is not a use."""
    return not any((ROOT / VARIANT / name).exists() for name in FROZEN_FILES)


def fold_ascii(text: str) -> str:
    """text with its ASCII letters lower-cased, as names_artifact compares the name."""
    return text.translate(ASCII_LOWER)


def artifact_relative_paths(names: Iterable[str]) -> list[str]:
    """The tracked paths inside the artifact directory, relative to it, compared and returned in any ASCII letter case
    (a case-insensitive file system checks a differently cased path out into the same directory); OS metadata files
    aside."""
    prefix = fold_ascii(f"{ARTIFACT}/")
    metadata = {fold_ascii(name) for name in OS_METADATA}
    relative = []
    for name in names:
        folded = fold_ascii(name)
        if folded.startswith(prefix) and PurePosixPath(folded).name not in metadata:
            relative.append(folded[len(prefix):])
    return sorted(relative)


def beyond_artifact_files(relative: Iterable[str]) -> list[str]:
    """The paths that are not one of ARTIFACT_FILES, a second copy of one included; a missing file is not reported,
    since removing the variant or the artifact is not a use."""
    return sorted((Counter(relative) - Counter(ARTIFACT_FILES)).elements())


def frozen_locks_sha256() -> str | None:
    """The sha256 that FROZEN_LOCKS in the coverage tests binds for the variant lock, read from their syntax tree."""
    tree = ast.parse((ROOT / COVERAGE_TESTS).read_text(encoding="utf-8"), filename=COVERAGE_TESTS)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            continue
        if not any(isinstance(target, ast.Name) and target.id == "FROZEN_LOCKS" for target in targets):
            continue
        if not isinstance(value, ast.Dict):
            return None
        for key, row in zip(value.keys, value.values):
            if isinstance(key, ast.Constant) and key.value == LOCK and isinstance(row, ast.Dict):
                for field, setting in zip(row.keys, row.values):
                    if (isinstance(field, ast.Constant) and field.value == "sha256"
                            and isinstance(setting, ast.Constant) and isinstance(setting.value, str)):
                        return setting.value
    return None


class ArtifactDirectoryTests(unittest.TestCase):
    """The whole artifact directory, not only variant/: a file beside variant/ reaches the lock by a relative path."""

    def test_the_artifact_directory_holds_nothing_beyond_its_three_files_on_disk(self):
        """OS metadata files aside; a directory is not a file, a symbolic link is. A missing file or an absent directory
        passes: removing the variant or the artifact is not a use."""
        directory = ROOT / ARTIFACT
        present = [
            path.relative_to(directory).as_posix() for path in directory.rglob("*")
            if (path.is_symlink() or not path.is_dir()) and path.name not in OS_METADATA
        ] if directory.is_dir() else []
        extra = beyond_artifact_files(present)
        self.assertEqual(extra, [], f"{ARTIFACT} holds {extra} besides {ARTIFACT_FILES}: {REOPEN}.")

    def test_git_tracks_nothing_beyond_the_three_files_there(self):
        """Paths compared in any ASCII letter case; OS metadata files aside. Fewer files pass: removing the variant or
        the artifact is not a use."""
        extra = beyond_artifact_files(artifact_relative_paths(name for name, _ in tracked_or_fail(self)))
        self.assertEqual(
            extra, [],
            f"Git tracks {extra} in {ARTIFACT} (paths compared in any ASCII letter case) besides {ARTIFACT_FILES}: "
            f"{REOPEN}.",
        )

    def test_tracked_paths_are_compared_in_any_ascii_letter_case(self):
        """A differently cased path is inside the directory and a second copy of a file counts; a sibling is outside."""
        parent, name = PurePosixPath(ARTIFACT).parent, PurePosixPath(ARTIFACT).name
        names = [
            f"{ARTIFACT.upper()}/rebuild.sh", f"{parent}/{name.title()}/Variant/package.json", f"{ARTIFACT}/.DS_Store",
            f"{ARTIFACT}/variant/THUMBS.DB", f"{ARTIFACT}-copy/rebuild.sh", f"{ARTIFACT}/run-summary.json",
        ]
        self.assertEqual(artifact_relative_paths(names), ["rebuild.sh", "run-summary.json", "variant/package.json"])
        self.assertEqual(beyond_artifact_files(artifact_relative_paths(names)), ["rebuild.sh"])
        self.assertEqual(beyond_artifact_files([*ARTIFACT_FILES, "variant/package.json"]), ["variant/package.json"])
        self.assertEqual(beyond_artifact_files(ARTIFACT_FILES[:1]), [])


class ArtifactReferenceTripwireTests(unittest.TestCase):
    def test_the_listed_configuration_kinds_are_scanned_inside_the_record_classes(self):
        """Outside the excluded classes every file is scanned, blueprints/**/*.json included; inside them only the
        recognised configuration and scripts are, client definitions under .claude, .codex and .agents included, so
        other files there, a JSON launch configuration included, are not (the stated limit)."""
        configuration = [
            "pnpm-workspace.yaml", ".yarnrc.yml", "lerna.json", "docker-compose.yml", "docker-compose.override.yaml",
            "compose.yaml", ".devcontainer/devcontainer.json", ".devcontainer/Dockerfile", "package.json",
            "tsconfig.json", "bunfig.toml", "action.yml", "build.sh", "build.py", "index.ts", "Makefile",
            "Dockerfile", "tests/test_build.py", ".claude/agents/x.md", ".claude/commands/x.md",
            ".claude/skills/x/SKILL.md", ".claude/settings.json", ".codex/config.toml", ".codex/prompts/x.md",
            ".agents/skills/x/SKILL.md", ".CLAUDE/skills/x/SKILL.md", ".Codex/prompts/x.md", ".AGENTS/skills/x/SKILL.md",
        ]
        for directory in ("", "evidence/artifacts/x/", "catalogs/x/", "blueprints/x/", "docs/x/", "manifests/"):
            for name in configuration:
                with self.subTest(path=directory + name):
                    self.assertTrue(in_scope(directory + name, "100644", b""))
        for path in ("evidence/artifacts/x/run", "catalogs/x/run"):
            with self.subTest(path=path):
                self.assertTrue(in_scope(path, EXECUTABLE_MODE, b""))
                self.assertTrue(in_scope(path, "100644", b"#!/bin/sh\n"))
                self.assertTrue(in_scope(path, SYMLINK_MODE, b"../y"))
        for path in ("README.md", "docs/x.md", "blueprints/x/README.md", "evidence/receipts/x.json",
                     "evidence/artifacts/x/out.txt", "evidence/artifacts/x/launch.json", "manifests/evidence.json",
                     "catalogs/x/y.json", "docs/claude/agents/x.md", "docs/.claude.md"):
            with self.subTest(path=path):
                self.assertFalse(in_scope(path, "100644", b"{}"))
        for path in ("blueprints/x/experiment.json", "blueprints/x/launch.json", "blueprints/x/socraticode-mcp.json",
                     "blueprints/x/scan.txt", "manifests/stack.json", ".github/osv-scanner-lockfiles.json", "x.cfg"):
            with self.subTest(path=path):
                self.assertTrue(in_scope(path, "100644", b"{}"))

    def test_the_name_is_matched_in_any_letter_case(self):
        """A differently cased path names the same directory on a case-insensitive file system; pins stay exact."""
        name = PurePosixPath(ARTIFACT).name
        for text in (name, name.upper(), name.title(), f"{ARTIFACT.upper()}/variant", f"Path({name.upper()!r})"):
            with self.subTest(text=text):
                self.assertTrue(names_artifact(text.encode()))
        self.assertFalse(names_artifact(b"evidence/artifacts/*/variant"))
        self.assertNotEqual(line_digest(name.encode()), line_digest(name.upper().encode()))

    def test_no_scanned_file_names_the_artifact_beyond_its_pinned_lines(self):
        unpinned = []
        for name, lines in sorted(scan_or_fail(self).items()):
            allowed = Counter(pin for pin, _ in PINNED_LINES.get(name, ()))
            for number, line in lines:
                digest = line_digest(line)
                if allowed[digest]:
                    allowed[digest] -= 1
                else:
                    unpinned.append(f"{name}:{number}: sha256 {digest}: {line.decode('utf-8', 'replace')[:240]}")
        if unpinned:
            self.fail("\n".join(unpinned) + "\n" + NEW_REFERENCE)

    def test_every_pinned_file_is_scanned_with_its_pinned_lines(self):
        """Not vacuous: each pinned file, this module included, is read by the scan and holds each pinned line."""
        found = scan_or_fail(self)
        missing = []
        for name, pins in sorted(PINNED_LINES.items()):
            present = Counter(line_digest(line) for _, line in found.get(name, ()))
            for digest, what in pins:
                if present[digest]:
                    present[digest] -= 1
                else:
                    missing.append(f"{name}: {what} (sha256 {digest})")
        self.assertIn(THIS_MODULE, PINNED_LINES, "this module pins its own ARTIFACT line")
        if missing:
            self.fail("\n".join(missing) + "\n" + STALE_PIN)


class FrozenVariantLockTests(unittest.TestCase):
    def test_package_json_and_the_lock_still_pin_next_16_3_5_or_are_absent(self):
        """Absent frozen files pass: removing the variant is not a use."""
        if variant_removed():
            return
        manifest = json.loads((ROOT / MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual(manifest.get("dependencies", {}).get("next"), NEXT_VERSION, f"{MANIFEST}: {REOPEN}.")
        lock = (ROOT / LOCK).read_text(encoding="utf-8")
        importer = re.search(r"(?m)^      next:\n        specifier: (\S+)\n        version: ([^(\s]+)", lock)
        self.assertIsNotNone(importer, f"{LOCK} has no importer entry for next: {REOPEN}.")
        self.assertEqual(importer.groups(), (NEXT_VERSION, NEXT_VERSION), f"{LOCK}: {REOPEN}.")
        self.assertEqual(sorted(set(re.findall(r"(?m)^  next@([^(:\s]+)", lock))), [NEXT_VERSION], f"{LOCK}: {REOPEN}.")

    def test_the_lock_has_the_sha256_that_frozen_locks_binds_or_is_absent(self):
        """An absent lock passes: removing the variant is not a use."""
        if variant_removed():
            return
        expected = frozen_locks_sha256()
        self.assertIsNotNone(
            expected,
            f"{COVERAGE_TESTS} binds no literal sha256 for {LOCK} in FROZEN_LOCKS while the variant is kept: keep that "
            "row with the frozen OSV exception, or remove the variant with them (the closure record's exit path).",
        )
        self.assertEqual(hashlib.sha256((ROOT / LOCK).read_bytes()).hexdigest(), expected, f"{LOCK}: {REOPEN}.")


class FrozenOsvExceptionReviewTests(unittest.TestCase):
    def test_the_frozen_osv_exception_still_ends_on_the_pinned_review_date(self):
        """The recheck of alert 16 is tied to this exception: removing it, renewing or otherwise changing its
        ignoreUntil, or giving it a key besides id, ignoreUntil and reason fails here (a TOML date-time on the same day
        counts as that date, as in the coverage tests)."""
        try:
            config = tomllib.loads((ROOT / FROZEN_CONFIG).read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as error:
            self.fail(f"{FROZEN_CONFIG} could not be read ({error}), so no exception for {ADVISORY} holds: {RECHECK}.")
        ignores = config.get("IgnoredVulns", [])
        entries = [entry for entry in (ignores if isinstance(ignores, list) else [])
                   if isinstance(entry, dict) and entry.get("id") == ADVISORY]
        self.assertEqual(
            len(entries), 1, f"{FROZEN_CONFIG} holds {len(entries)} exceptions for {ADVISORY}, not one: {RECHECK}.",
        )
        unexpected = sorted(set(entries[0]) - EXCEPTION_KEYS)
        self.assertEqual(
            unexpected, [],
            f"{FROZEN_CONFIG}: the exception for {ADVISORY} has keys {unexpected} besides {sorted(EXCEPTION_KEYS)}: "
            f"{RECHECK}.",
        )
        written = entries[0].get("ignoreUntil")
        until = written.date() if isinstance(written, datetime.datetime) else written
        self.assertEqual(
            until, REVIEW_DATE,
            f"{FROZEN_CONFIG}: the exception for {ADVISORY} has ignoreUntil {written!r}, not {REVIEW_DATE}: {RECHECK}.",
        )


if __name__ == "__main__":
    unittest.main()
