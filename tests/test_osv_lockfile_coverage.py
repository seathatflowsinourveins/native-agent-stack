"""Keep security-scan.yml's OSV-Scanner inventory complete (docs/decisions/2026-09-22-github-automation-closure.md).

.github/osv-scanner-lockfiles.json is the one checked-in list of files the osv-scanner job
scans. These tests fail when a tracked lockfile or manifest is missing from it (unless its
"excluded" list names it with a reason and an evidence path), when a listed file no longer exists, when a parser name is not one OSV-Scanner v2 accepts for that file,
when an ignore in .github/osv-scanner.toml lacks an id, a reason or an ignoreUntil at most 90
days away, and when a repo-wide ignore would hide a pin that IGNORE_ALLOWED_LOCKS does not allow
for that lock and advisory at the lock's reviewed sha256. That guard follows includes and fails
closed on a version or line it cannot parse strictly; an allowed lock must be self-contained, and
an ignore counts as active only before its ignoreUntil date. A dated exception for one frozen artifact lives in a config of its own
that only that lock's scan uses (FROZEN_LOCKS). The workflow and these policy checks enforce the split and scope;
OSV applies an explicit config to every invocation input and does not enforce that path boundary itself.
"""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tempfile
import textwrap
import tomllib
import unittest
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / ".github/osv-scanner-lockfiles.json"
CONFIG = ROOT / ".github/osv-scanner.toml"
FROZEN_CONFIG = ".github/osv-scanner-frozen-macos.toml"
WORKFLOW = ROOT / ".github/workflows/security-scan.yml"
# Dependency lockfile and manifest names in this repository or supported by OSV-Scanner v2's
# source extractors (docs/supported_languages_and_lockfiles.md at v2.6.0).
TRACKED = re.compile(
    r"(?:^|/)(?:"
    r"requirements[^/]*\.(?:txt|in)|[^/]*constraints[^/]*\.txt|[^/]*\.lock|[^/]*\.lock\.txt"
    r"|[^/]*packages\.lock\.json|packages\.config|[^/]*\.deps\.json|uv\.lock|pylock(?:\.[^/]+)?\.toml"
    r"|poetry\.lock|pdm\.lock|Pipfile(?:\.lock)?|pnpm-lock\.yaml|package-lock\.json|yarn\.lock"
    r"|bun\.lock|package\.json|pyproject\.toml|go\.mod|Cargo\.lock|Gemfile\.lock|gems\.locked"
    r"|composer\.lock|pom\.xml|[^/]*gradle\.lockfile|mix\.lock|pubspec\.lock|renv\.lock|conan\.lock"
    r")$"
)
# File names OSV-Scanner infers without a parser prefix, and the parsers this inventory uses.
# package-lock.json is listed in the pinned v2.6.0 supported-lockfiles documentation.
INFERRED = {"requirements.txt", "uv.lock", "package-lock.json", "pnpm-lock.yaml", "packages.lock.json"}
# OSV-Scanner v2.6.0 lockfile.go maps "uv.lock" to the native UV extractor;
# an explicit parser also supports the native uv PEP 723 script-lock basename.
PARSERS = {"requirements.txt", "packages.lock.json", "uv.lock"}
# A dependency_free entry is a package.json with nothing to scan: no key naming dependencies (dependencies,
# devDependencies, peerDependenciesMeta and the rest) or the fields below, in any letter case, and none of these
# lockfile names beside it. They are the JavaScript lockfiles that GitHub's dependency graph (npm, Yarn, pnpm and
# Deno rows) or OSV-Scanner v2.6.0 (docs/supported_languages_and_lockfiles.md) reads by name, and npm's shrinkwrap.
DEPENDENCY_STEERING_FIELDS = {"workspaces", "overrides", "resolutions"}
JS_LOCK_NAMES = {"package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lock", "deno.lock"}


# osv-scanner 2.6.0 matches [[IgnoredVulns]] by id in every input of that invocation (ShouldIgnore checks the id and
# ignoreUntil). An ignore in CONFIG therefore reaches the whole ordinary group; dedicated archive groups have separate
# configs. IGNORE_SCOPES names the package versions each ordinary ignore affects. IGNORE_ALLOWED_LOCKS names the
# only locks allowed to pin them: per inventory lockfile, the advisories whose non-reachability was reviewed for it, the
# sha256 of the lock content that review covered and the repository path of its evidence. A changed lock needs a new
# review before its new digest is recorded here, and an allowed lock must be self-contained: its digest covers only its
# own bytes, not a file it includes.
IGNORE_SCOPES = {
    # nltk: no patched release, so every version is affected.
    "GHSA-8mgp-746c-j5xp": {"package": "nltk", "fixed": None},
    "GHSA-h35f-9h28-mq5c": {"package": "setuptools", "fixed": (83, 0, 0)},
    # oauthlib 4.0.0 fixes both oauthlib advisories (GitHub and OSV records, 2026-09-29).
    "GHSA-hj66-6f7g-4r5v": {"package": "oauthlib", "fixed": (4, 0, 0)},
    "GHSA-xpv3-w29h-x7cv": {"package": "oauthlib", "fixed": (4, 0, 0)},
}
IGNORE_ALLOWED_LOCKS = {
    # Live recipe lock; the 2026-10-05 relock changes only fsspec and multidict
    # and carries the existing oauthlib review forward at the new exact digest.
    # No fsspec ignore is granted; moving oauthlib to 4.0.0 removes this entry.
    "blueprints/runtime-workers/openhands/requirements.lock": {
        "advisories": ["GHSA-hj66-6f7g-4r5v", "GHSA-xpv3-w29h-x7cv"],
        "sha256": "2837036a2bb832958e2daad6094811610d1fd605a315dacd9a0616841e9e2401",
        "evidence": "evidence/receipts/osv-openhands-fsspec-relock-20261005.json",
    },
}
# A dated exception for one frozen artifact is not a repo-wide ignore: OSV-Scanner 2.6.0 applies an explicit --config to every input of its
# invocation (docs/configuration.md, internal/config/manager.go Manager.Get), so the exception lives in a config of its own and security-scan.yml
# scans the inventory entries that name it in an invocation of their own, and every other entry under CONFIG, which holds no exception for the
# advisory. FROZEN_LOCKS binds each such config to the one lock it is for: its advisories, the lock's sha256 (a changed lock needs a new review)
# and the repository path of the evidence.
FROZEN_LOCKS = {
    # Frozen macOS application variant (2026-09-24): package.json and this lock only, no source, installed by nothing here.
    "evidence/artifacts/macos-application-20260924/variant/pnpm-lock.yaml": {
        "config": FROZEN_CONFIG,
        "advisories": ["GHSA-vcvr-r3jv-pc5j", "GHSA-68fv-2mgg-jv7q", "GHSA-wq5f-xc86-pv6w",
                       # next 16.3.5; first patched in 16.3.8 (advisories published 2026-10-07)
                       "GHSA-39w2-rjm5-chcv", "GHSA-3w37-wq28-93x7", "GHSA-4jqv-mc3x-m676",
                       "GHSA-cjq9-62q9-8jv4", "GHSA-f87g-xv8r-7p7x", "GHSA-mcj8-r9mp-w47p"],
        "sha256": "f1c707b8295e85bd396e49b990de92dc82bc0d58eca1e4e4bef31262d9898cd2",
        "evidence": "evidence/receipts/osv-frozen-macos-next-1638-20261007.json",
    },
}

# Requirements files follow pip's format (https://pip.pypa.io/en/stable/reference/requirements-file-format/): a line
# ending in `\` continues on the next line, comments (a `#` that starts a line or follows whitespace) are stripped
# after continuations are joined, `-r`/`--requirement` and `-c`/`--constraint` include another requirements or
# constraints file, and the other global options it lists name no package (NON_INSTALLING; `-e`/`--editable` does).
# osv-scanner 2.6.0 (osv-scalibr 0.5.2) follows only `-r` includes: recursively, relative to the including file and
# reading each file once (extractFromExtraPaths, the same code as
# https://github.com/google/osv-scalibr/blob/3090dbb7aaa2/extractor/filesystem/language/python/requirements/requirements.go#L223).
# The guard follows all four include forms that way, which errs closed: a constraints file pins only packages that
# something else requires.
COMMENT = re.compile(r"(^|\s+)#.*$")
OPTION = re.compile(r"(--[^=\s]+|-[^-\s])(?:=|\s+)?(.*)")
INCLUDES = {"-r", "--requirement", "-c", "--constraint"}
NON_INSTALLING = {
    "-i", "--index-url", "--extra-index-url", "--no-index", "-f", "--find-links", "--no-binary", "--only-binary",
    "--prefer-binary", "--require-hashes", "--no-require-hashes", "--pre", "--all-releases", "--only-final",
    "--trusted-host", "--use-feature",
}
# A requirement is osv-scalibr's package name (reValidPkg) and extras (reExtras), then nothing, a marker (;), a URL (@)
# or a version specifier, once per-requirement options are cut (reTextAfterFirstOptionInclusive).
REQUIREMENT = re.compile(r"([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)\s*(?:\[[^\[\]]*\])?\s*([;@(=<>!~].*)?")
PER_REQUIREMENT_OPTIONS = re.compile(r"(?:\s+|^)(?:--hash|--global-option|--config-settings|-C).*")
PIN = re.compile(r"===?\s*(\S+)")
PLAIN_RELEASE = re.compile(r"\d+(?:\.\d+)*")


def canonical(name):
    """PEP 503 name normalization (https://peps.python.org/pep-0503/#normalized-names)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def logical_lines(text):
    """A requirements file's non-empty logical lines. A line ending in `\\` joins the next, a comment line is never
    continued and still reads as a comment once joined (join_lines in pip 26.2.1,
    https://github.com/pypa/pip/blob/26.2.1/src/pip/_internal/req/req_file.py#L496-L522), and comments are then
    stripped. A continued line that holds a comment is kept whole: pip strips that comment after joining, osv-scalibr
    before (its readLine), so the two read different requirements, and requirement_line fails the line closed."""
    lines, joined, commented = [], "", False
    for line in [*text.splitlines(), ""]:  # the final "" ends a continuation on the last line
        if line.endswith("\\") and not COMMENT.match(line):
            joined, commented = joined + line[:-1], commented or bool(COMMENT.search(line[:-1]))
            continue
        whole = joined + (" " + line if COMMENT.match(line) else line)
        lines.append(whole.strip() if commented else COMMENT.sub("", whole).strip())
        joined, commented = "", False
    return [line for line in lines if line]


def requirement_line(line):
    """("include", path), ("option", None), ("requirement", (package, version)) or ("unparseable", None) for a logical
    line. version is None for an unpinned requirement, the text after == or === for a single pin and the whole
    specifier otherwise (>=70, @ url)."""
    if COMMENT.search(line):
        return "unparseable", None  # a continued line that holds a comment (logical_lines)
    if line.startswith("-"):
        option = OPTION.fullmatch(line)
        if option and option.group(1) in INCLUDES:
            return "include", option.group(2)
        return ("option" if option and option.group(1) in NON_INSTALLING else "unparseable"), None
    requirement = REQUIREMENT.fullmatch(PER_REQUIREMENT_OPTIONS.sub("", line))
    if not requirement:
        return "unparseable", None  # a URL, a path or an environment variable
    specifier = (requirement.group(2) or "").split(";", 1)[0].strip()
    pin = PIN.fullmatch(specifier)
    return "requirement", (canonical(requirement.group(1)), pin.group(1) if pin else specifier or None)


def python_pins(path, parser=None):
    """(file, package, version) for each requirement in a uv.lock, or in a requirements-style file and each file it
    includes, each read once (a shared or cyclic include is not read again). package is None for a line the guard
    cannot parse strictly, an include that names no file among them; version then holds the line. Nothing for the npm
    and NuGet lock formats, which cannot pin a PyPI package."""
    if parser == "uv.lock" or path.name == "uv.lock":
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return [(path, canonical(p["name"]), p.get("version")) if "name" in p else (path, None, str(p))
                for p in data.get("package", [])]
    if parser != "requirements.txt" and not path.name.endswith("requirements.txt"):
        return []
    pins, queue, read = [], [path], set()
    while queue:
        current = queue.pop(0)
        if current.resolve() in read:
            continue
        read.add(current.resolve())
        for line in logical_lines(current.read_text(encoding="utf-8")):
            kind, value = requirement_line(line)
            if kind == "include" and (current.parent / value).is_file():
                queue.append(current.parent / value)
            elif kind == "requirement":
                pins.append((current, *value))
            elif kind != "option":
                pins.append((current, None, line))
    return pins


def affected(version, fixed):
    """Whether a tracked package at this version or specifier (python_pins) may be one its advisory affects: every
    version when no release is fixed. Otherwise a plain release (digits and dots) is compared with the fix as an integer
    tuple, so 83 counts as below 83.0.0 and errs closed; any other text, a `v` prefix, a pre-, post-, dev- or local
    release, a range such as >=70 (OSV scans its lower bound) or a URL, counts as affected, because the guard does not
    implement PEP 440. An unpinned requirement (None) gives OSV no version to match."""
    if fixed is None:
        return True
    if version is None:
        return False
    return not PLAIN_RELEASE.fullmatch(version) or tuple(int(part) for part in version.split(".")) < fixed


def affected_pins(entries, ignore_ids, allowed=IGNORE_ALLOWED_LOCKS):
    """(path, package, version, advisory) for each pin, in an inventory lockfile or a file it includes, of a version an
    active repo-wide ignore could hide (affected), and (path, None, line, "unparseable") for each line the guard cannot
    parse strictly, which fails closed. A lock that `allowed` names is exempt only for the advisories its entry lists,
    and only for its own lines: its digest does not cover a file it includes."""
    if not ignore_ids:
        return []  # no ignore, nothing hidden
    found = []
    for entry in entries:
        lock = ROOT / entry["path"]
        exempt = set(allowed.get(entry["path"], {}).get("advisories", ()))
        for file, package, version in python_pins(lock, entry.get("parser")):
            path = entry["path"] if file == lock else str(file)
            if package is None:
                found.append((path, None, version, "unparseable"))
                continue
            for advisory in ignore_ids:
                scope = IGNORE_SCOPES[advisory]
                if package != canonical(scope["package"]) or (file == lock and advisory in exempt):
                    continue
                if affected(version, scope["fixed"]):
                    found.append((path, package, version, advisory))
    return found


def digest_drift(allowed=IGNORE_ALLOWED_LOCKS):
    """(path, reviewed sha256, current sha256, or None for a missing file) for each allowed lock whose bytes differ from
    the content its review covered. `* text=auto eol=lf` in .gitattributes checks locks out with LF on every host, so
    the digest does not depend on the checkout."""
    drift = []
    for path, grant in sorted(allowed.items()):
        lock = ROOT / path
        current = hashlib.sha256(lock.read_bytes()).hexdigest() if lock.is_file() else None
        if current != grant["sha256"]:
            drift.append((path, grant["sha256"], current))
    return drift


def allowed_lock_includes(allowed=IGNORE_ALLOWED_LOCKS):
    """(path, line) for each include line in an allowed lock: its sha256 covers only its own bytes, so an allowed lock
    must be self-contained."""
    return [(path, line) for path in sorted(allowed) if (ROOT / path).is_file()
            for line in logical_lines((ROOT / path).read_text(encoding="utf-8"))
            if requirement_line(line)[0] == "include"]


def active_ignores(config, today=None):
    """The ids of the [[IgnoredVulns]] entries OSV-Scanner still applies. 2.6.0 ignores an id while its ignoreUntil is
    after the current time (https://github.com/google/osv-scanner/blob/v2.6.0/internal/config/config.go#L149-L157), and
    its TOML decoder reads a bare date as midnight in the host's zone
    (https://github.com/BurntSushi/toml/blob/v1.6.0/internal/tz.go#L32-L35), so on a UTC runner an ignore no longer
    applies on its ignoreUntil date. An entry without ignoreUntil never expires."""
    today = today or datetime.now(timezone.utc).date()
    active = set()
    for entry in config.get("IgnoredVulns", []):
        until = entry.get("ignoreUntil")
        if isinstance(until, datetime):
            until = until.date()
        if until is None or until > today:
            active.add(entry["id"])
    return active


def scan_partition(entries, configs=None):
    """The split security-scan.yml's jq makes of the inventory: (the entries scanned together under CONFIG, {config path: the entries scanned
    under that config alone}, the entries that name any other config). The last are in neither scan, which the workflow's count check
    turns into a failure; `configs` defaults to the configs FROZEN_LOCKS binds."""
    configs = {lock["config"] for lock in FROZEN_LOCKS.values()} if configs is None else set(configs)
    ordinary, frozen, stray = [], {config: [] for config in configs}, []
    for entry in entries:
        if "config" not in entry:
            ordinary.append(entry)
        elif entry["config"] in configs:
            frozen[entry["config"]].append(entry)
        else:
            stray.append(entry)
    return ordinary, frozen, stray


IGNORE_ENTRY_KEYS = {"id", "ignoreUntil", "reason"}


def ignore_entry_problems(config):
    """Reject invalid grants and keys not spelled exactly as policy reads them.

    OSV-Scanner v2.6.0's BurntSushi/toml v1.6.0 decoder matches struct fields
    case-insensitively, so distinct id/ID keys can target the same native field.
    """
    problems, latest = [], date.today() + timedelta(days=90)
    for key in sorted(set(config) - {"IgnoredVulns", "PackageOverrides"}):
        problems.append(f"{key}: not a table this policy knows")
    for entry in config.get("IgnoredVulns", []):
        for key in sorted(set(entry) - IGNORE_ENTRY_KEYS):
            problems.append(f"{entry.get('id')}: unknown key {key!r}")
        if not entry.get("id"):
            problems.append(f"{entry}: no id")
        if not str(entry.get("reason", "")).strip():
            problems.append(f"{entry.get('id')}: no reason")
        until = entry.get("ignoreUntil")
        if not isinstance(until, date):
            problems.append(f"{entry.get('id')}: ignoreUntil must be a TOML date")
            continue
        if hasattr(until, "date"):
            until = until.date()
        if until > latest:
            problems.append(f"{entry.get('id')}: ignoreUntil more than 90 days away")
        if until <= date.today():
            problems.append(f"{entry.get('id')}: ignoreUntil has expired")
    return problems


# The toml tags of PackageOverrideEntry and its nested tables at OSV-Scanner v2.6.0
# (internal/config/config.go:38-49 and :83-89).
PACKAGE_OVERRIDE_KEYS = {"name", "version", "ecosystem", "group", "nameIsRegex", "ignore",
                         "vulnerability", "license", "effectiveUntil", "reason"}
PACKAGE_OVERRIDE_TABLE_KEYS = {"vulnerability": {"ignore"}, "license": {"override", "ignore"}}


def override_problems(config):
    """Reject ordinary overrides that can suppress an npm package by name or regex.

    OSV applies an override without an ecosystem to every ecosystem. Reject npm
    in any case as project policy; native ecosystem matching is case-sensitive.
    The decoder matches keys case-blind, so a key not spelled exactly as a toml
    tag (Ecosystem beside ecosystem) can set the field this policy reads.
    """
    problems = []
    for entry in config.get("PackageOverrides", []):
        for key in sorted(set(entry) - PACKAGE_OVERRIDE_KEYS):
            problems.append(f"{entry.get('name')!r}: unknown key {key!r}")
        for table, keys in PACKAGE_OVERRIDE_TABLE_KEYS.items():
            nested = entry.get(table)
            if isinstance(nested, dict):
                for key in sorted(set(nested) - keys):
                    problems.append(f"{entry.get('name')!r}: unknown key {table}.{key}")
        ecosystem = str(entry.get("ecosystem", "")).strip().lower()
        if not ecosystem or ecosystem == "npm":
            problems.append(f"{entry.get('name')!r}: a package override needs an ecosystem other than npm")
    return problems


def tracked_files():
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    listing = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"], env=environment,
        capture_output=True, check=True,
    )
    return {os.fsdecode(item) for item in listing.stdout.split(b"\0") if item}


def scratch_findings(files, allowed_advisories=(), scanned="requirements.lock", parser="requirements.txt"):
    """affected_pins for every IGNORE_SCOPES advisory over scratch files (name: text or bytes), scanning `scanned` by
    its absolute path (ROOT / path keeps it as is) and allowing it `allowed_advisories`; paths are shown relative to
    the scratch directory."""
    with tempfile.TemporaryDirectory() as scratch:
        for name, content in files.items():
            path = Path(scratch) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
        lock = str(Path(scratch) / scanned)
        allowed = {lock: {"advisories": list(allowed_advisories)}} if allowed_advisories else {}
        found = affected_pins([{"path": lock, "parser": parser}], list(IGNORE_SCOPES), allowed)
    return [(os.path.relpath(path, scratch), package, version, advisory) for path, package, version, advisory in found]


class LockfileInventoryTests(unittest.TestCase):
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))

    def listed(self):
        return [entry["path"] for entry in self.inventory["lockfiles"]]

    def covered(self):
        return [entry["path"] for entry in self.inventory["covered_by_lockfile"]]

    def excluded(self):
        return [entry["path"] for entry in self.inventory.get("excluded", [])]

    def dependency_free(self):
        return [entry["path"] for entry in self.inventory.get("dependency_free", [])]

    def test_every_tracked_lockfile_and_manifest_is_listed(self):
        try:
            files = tracked_files()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a Git checkout; the listed paths are still checked below")
        expected = sorted(path for path in files if TRACKED.search(path))
        self.assertGreater(len(expected), 0)
        missing = sorted(set(expected) - set(self.listed()) - set(self.covered()) - set(self.excluded())
                         - set(self.dependency_free()))
        self.assertEqual(missing, [], "add these to .github/osv-scanner-lockfiles.json")
        # An exclusion only covers a tracked file this inventory would otherwise require.
        for path in self.excluded():
            self.assertIn(path, expected, f"{path} is excluded but is not a tracked lockfile")

    def test_exclusions_are_reasoned_fixtures_not_scanned_anywhere(self):
        scanned = set(self.listed()) | set(self.covered())
        for entry in self.inventory.get("excluded", []):
            path = entry.get("path", "")
            self.assertNotIn(path, scanned, f"{path} is both scanned and excluded")
            self.assertTrue(str(entry.get("reason", "")).strip(), f"{path}: exclusion needs a reason")
            self.assertIn("fixture", entry["reason"].lower(), f"{path}: only a test fixture may be excluded")
            evidence = entry.get("evidence", "")
            self.assertTrue(evidence and (ROOT / evidence).is_file(), f"{path}: exclusion needs an existing evidence path")

    def test_entries_are_unique_existing_files(self):
        paths = self.listed() + self.covered() + self.excluded() + self.dependency_free()
        self.assertEqual(len(paths), len(set(paths)), "duplicate inventory entry")
        for path in paths:
            self.assertTrue((ROOT / path).is_file(), f"{path} is listed but missing")

    def test_dependency_free_manifests_have_nothing_to_scan(self):
        for entry in self.inventory.get("dependency_free", []):
            path = entry.get("path", "")
            with self.subTest(path=path):
                self.assertEqual(path.rsplit("/", 1)[-1], "package.json", f"{path}: only a package.json can be dependency-free")
                self.assertTrue(str(entry.get("reason", "")).strip(), f"{path}: a dependency-free entry needs a reason")
                evidence = entry.get("evidence", "")
                self.assertTrue(evidence and (ROOT / evidence).is_file(), f"{path}: needs an existing evidence path")
                manifest = json.loads((ROOT / path).read_text(encoding="utf-8"))
                self.assertIsInstance(manifest, dict, path)
                declared = sorted(key for key in manifest
                                  if "dependencies" in key.lower() or key.lower() in DEPENDENCY_STEERING_FIELDS)
                self.assertEqual(declared, [], f"{path} declares dependencies: list it as covered_by_lockfile with its scanned lock")
                beside = sorted(child.name for child in (ROOT / path).parent.iterdir() if child.name.lower() in JS_LOCK_NAMES)
                self.assertEqual(beside, [], f"{path} has a lockfile beside it: scan that lock and cover the manifest with it")

    def test_parsers_are_explicit_where_osv_cannot_infer_them(self):
        for entry in self.inventory["lockfiles"]:
            name = entry["path"].rsplit("/", 1)[-1]
            parser = entry.get("parser")
            if parser is None:
                self.assertIn(name, INFERRED, f"{entry['path']} needs an explicit parser")
            else:
                self.assertIn(parser, PARSERS, entry["path"])
                if parser == "packages.lock.json":
                    self.assertTrue(name.endswith("packages.lock.json"), entry["path"])

    def test_manifests_without_an_extractor_point_at_a_scanned_lockfile(self):
        listed = set(self.listed())
        for entry in self.inventory["covered_by_lockfile"]:
            self.assertIn(entry["lockfile"], listed, entry["path"])
            self.assertEqual(entry["path"].rsplit("/", 1)[0], entry["lockfile"].rsplit("/", 1)[0])

    def test_workflow_scans_the_inventory_with_the_config(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(".github/osv-scanner-lockfiles.json", text)
        self.assertIn("--config .github/osv-scanner.toml", text)
        self.assertIn("--no-resolve", text)


class IgnorePolicyTests(unittest.TestCase):
    def test_every_ignore_has_id_reason_and_a_near_expiry(self):
        for path in (CONFIG, ROOT / FROZEN_CONFIG):
            config = tomllib.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(ignore_entry_problems(config), [], str(path))

    def test_the_ignore_field_check_catches_a_mutant(self):
        far = date.today() + timedelta(days=91)
        self.assertEqual(ignore_entry_problems({"IgnoredVulns": [{"id": "GHSA-x", "reason": "r", "ignoreUntil": date.today() + timedelta(days=90)}]}), [])
        for entry in ({"reason": "r", "ignoreUntil": far}, {"id": "GHSA-x", "ignoreUntil": far}, {"id": "GHSA-x", "reason": "r"},
                      {"id": "GHSA-x", "reason": "r", "ignoreUntil": far}, {"id": "GHSA-x", "reason": " ", "ignoreUntil": far}):
            self.assertNotEqual(ignore_entry_problems({"IgnoredVulns": [entry]}), [], entry)

    def test_repo_wide_ignores_hide_nothing_outside_their_allowed_lock(self):
        # Every ignore matches repo-wide, so while one is active no inventory lockfile may pin a version it would hide
        # (IGNORE_SCOPES) unless IGNORE_ALLOWED_LOCKS lists that advisory for that lock; AllowedLockTests bind each
        # entry to the reviewed lock's sha256 and its evidence. The rule began as 9a's condition on #336 for the
        # Lumibot ignores.
        config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
        active = [entry["id"] for entry in config.get("IgnoredVulns", [])]
        unscoped = [advisory for advisory in active if advisory not in IGNORE_SCOPES]
        self.assertEqual(unscoped, [], "every ignore needs an IGNORE_SCOPES entry naming the versions it affects")
        entries = json.loads(INVENTORY.read_text(encoding="utf-8"))["lockfiles"]
        self.assertEqual(affected_pins(entries, active), [],
                         "pin a fixed plain release (digits and dots after == or ===), or review reachability and list "
                         "the advisory for that lock in IGNORE_ALLOWED_LOCKS with the lock's sha256 and the evidence "
                         "path; an unparseable line, an include that names no file among them, fails closed")

    def test_the_scope_guard_catches_a_mutant(self):
        # A lock outside the allowed set that pins nltk, or setuptools below the fix, must be reported; a fixed
        # setuptools and an unpinned setuptools must not.
        with tempfile.TemporaryDirectory() as scratch:
            lock = Path(scratch) / "requirements.lock"  # an absolute path: ROOT / path keeps it as is
            lock.write_text("nltk==3.9.1 \\\n    --hash=sha256:00\nsetuptools==80.9.0\nSetuptools==84.0.0\n"
                            "setuptools\n# nltk==1.0 in a comment\n", encoding="utf-8")
            found = affected_pins([{"path": str(lock), "parser": "requirements.txt"}], list(IGNORE_SCOPES))
        self.assertEqual(sorted((package, version) for _, package, version, _ in found),
                         [("nltk", "3.9.1"), ("setuptools", "80.9.0")])

    def test_a_continuation_is_joined_before_a_requirement_is_read(self):
        # A backslash may split the name itself (the review's nlt\ then k==3.10.3), with LF or CRLF line ends.
        for text in ("nlt\\\nk==3.10.3\n", "nlt\\\r\nk==3.10.3\r\n", "nltk=\\\n=3.10.3 \\\n    --hash=sha256:00\n"):
            with self.subTest(text=text):
                self.assertEqual(scratch_findings({"requirements.lock": text}),
                                 [("requirements.lock", "nltk", "3.10.3", "GHSA-8mgp-746c-j5xp")])

    def test_a_tracked_version_that_is_not_a_plain_release_fails_closed(self):
        # The guard does not implement PEP 440: setuptools counts unless pinned with == or === to a plain release at or
        # above the fix. osv-scanner 2.6.0 reports v80.10.2, 83.0.0rc1 and >=70 (as 70) under this advisory.
        for specifier in ("==v80.10.2", "==83.0.0rc1", "==83.0.0.post1", "==84.0.0.dev1", "==84.0.0+local",
                          "==1!84.0.0", ">=70", "~=84.0", "==84.*", "==84.0.0,<85", " (==84.0.0)",
                          " @ https://example.invalid/setuptools-84.0.0.tar.gz"):
            with self.subTest(specifier=specifier):
                self.assertEqual(scratch_findings({"requirements.lock": f"setuptools{specifier}\n"}),
                                 [("requirements.lock", "setuptools", specifier.strip().removeprefix("=="),
                                   "GHSA-h35f-9h28-mq5c")])
        for text in ("setuptools==83.0.0\n", "setuptools===84.0.0\n",
                     "setuptools == 84.0.0 ; python_version >= '3.9'\n", "setuptools\n",
                     "setuptools ; python_version < '3.12'\n"):
            with self.subTest(text=text):
                self.assertEqual(scratch_findings({"requirements.lock": text}), [])

    def test_equality_extras_markers_spacing_and_case_are_read(self):
        # Forms the review found detected already, kept as regressions: ===, extras, markers, spaces and name case.
        text = ("NLTK [all] == 3.10.3 ; python_version >= '3.9'\nsetuptools===80.10.2\n"
                "Setuptools[core]==80.10.2;python_version>='3'\nnltk==3.10.3 --hash=sha256:00\n")
        found = scratch_findings({"requirements.lock": text})
        self.assertEqual([(package, version) for _, package, version, _ in found],
                         [("nltk", "3.10.3"), ("setuptools", "80.10.2"), ("setuptools", "80.10.2"), ("nltk", "3.10.3")])

    def test_includes_are_followed_relative_to_the_including_file(self):
        # osv-scanner 2.6.0 reports a pin that a -r include brings in (the review's -r pins.txt). The guard follows
        # every include form pip documents, recursively and relative to the including file, reading a cycle once.
        self.assertEqual(scratch_findings({"requirements.lock": "-r pins.txt\n", "pins.txt": "nltk==3.10.3\n"}),
                         [("pins.txt", "nltk", "3.10.3", "GHSA-8mgp-746c-j5xp")])
        files = {
            "requirements.lock": "-r sub/pins.txt\n--requirement=more.txt\n",
            "sub/pins.txt": "-r ../requirements.lock\n-c deeper.txt\nnltk==3.9.1\n",
            "sub/deeper.txt": "--constraint ../sub/pins.txt\nsetuptools==80.10.2\n",
            "more.txt": "-rsub/deeper.txt\nsetuptools==84.0.0\n",
        }
        self.assertEqual(scratch_findings(files),  # breadth-first: each include is read after the file that names it
                         [("sub/pins.txt", "nltk", "3.9.1", "GHSA-8mgp-746c-j5xp"),
                          ("sub/deeper.txt", "setuptools", "80.10.2", "GHSA-h35f-9h28-mq5c")])

    def test_an_include_that_names_no_file_fails_closed(self):
        for line in ("-r missing.txt", "--requirement", "-c https://example.invalid/constraints.txt"):
            with self.subTest(line=line):
                self.assertEqual(scratch_findings({"requirements.lock": line + "\n"}),
                                 [("requirements.lock", None, line, "unparseable")])

    def test_lines_the_guard_cannot_parse_fail_closed(self):
        # Each could install a tracked package at any version: an editable or per-requirement option on its own line,
        # a path, a URL, an environment variable or a malformed requirement.
        for line in ("-e .", "--hash=sha256:00", "./wheels/nltk-3.10.3-py3-none-any.whl",
                     "https://example.invalid/nltk-3.10.3-py3-none-any.whl", "${NLTK}==3.10.3", "nltk 3.10.3"):
            with self.subTest(line=line):
                self.assertEqual(scratch_findings({"requirements.lock": line + "\n"}),
                                 [("requirements.lock", None, line, "unparseable")])
        # pip strips a comment after joining continuations, so it installs numpy alone; osv-scanner 2.6.0 strips it
        # first and reports the next line's nltk==3.10.3. The guard fails that continued line closed.
        self.assertEqual(scratch_findings({"requirements.lock": "numpy==2.0.0 # pinned \\\nnltk==3.10.3\n"}),
                         [("requirements.lock", None, "numpy==2.0.0 # pinned nltk==3.10.3", "unparseable")])

    def test_documented_options_that_name_no_package_pass(self):
        text = ("--index-url https://pypi.org/simple\n-i https://pypi.org/simple\n"
                "--extra-index-url=https://example.invalid/simple\n--no-index\n-f ./wheels\n--find-links ./wheels\n"
                "--no-binary :none:\n--only-binary :all:\n--prefer-binary\n--require-hashes\n--no-require-hashes\n"
                "--pre\n--all-releases :all:\n--only-final :all:\n--trusted-host example.invalid\n"
                "--use-feature fast-deps\nsetuptools==84.0.0\n")
        self.assertEqual(scratch_findings({"requirements.lock": text}), [])

    def test_a_uv_lock_pin_is_read(self):
        lock = ('version = 1\n\n[[package]]\nname = "nltk"\nversion = "3.10.3"\n\n'
                '[[package]]\nname = "setuptools"\nversion = "80.10.2"\n\n'
                '[[package]]\nname = "setuptools-scm"\nversion = "8.0.0"\n')
        self.assertEqual(scratch_findings({"uv.lock": lock}, scanned="uv.lock", parser=None),
                         [("uv.lock", "nltk", "3.10.3", "GHSA-8mgp-746c-j5xp"),
                          ("uv.lock", "setuptools", "80.10.2", "GHSA-h35f-9h28-mq5c")])
        self.assertEqual(scratch_findings({"worker.py.lock": lock}, scanned="worker.py.lock", parser="uv.lock"),
                         [("worker.py.lock", "nltk", "3.10.3", "GHSA-8mgp-746c-j5xp"),
                          ("worker.py.lock", "setuptools", "80.10.2", "GHSA-h35f-9h28-mq5c")])

    def test_no_other_suppression_mechanism_bypasses_the_policy(self):
        config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertLessEqual(set(config), {"IgnoredVulns", "PackageOverrides"})
        self.assertEqual(override_problems(config), [])
        latest = date.today() + timedelta(days=90)
        for entry in config.get("PackageOverrides", []):
            # An override can silently ignore a whole package; it needs the same reason and expiry.
            self.assertTrue(str(entry.get("reason", "")).strip(), entry)
            until = entry.get("effectiveUntil")
            self.assertIsInstance(until, date, f"{entry}: effectiveUntil must be a TOML date")
            if hasattr(until, "date"):
                until = until.date()
            self.assertLessEqual(until, latest, f"{entry}: effectiveUntil more than 90 days away")


class FrozenScanTests(unittest.TestCase):
    """The workflow and policy preflight bind each explicit OSV config to its reviewed artifact; OSV itself applies it to all inputs."""

    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    ordinary_config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_the_split_is_exhaustive_and_disjoint(self):
        entries = self.inventory["lockfiles"]
        ordinary, frozen, stray = scan_partition(entries)
        self.assertEqual(stray, [], "an entry that names a config nothing scans")
        scanned = ordinary + [entry for group in frozen.values() for entry in group]
        self.assertEqual(len(scanned), len(entries), "an entry in two scans, or in none")
        self.assertEqual(sorted(entry["path"] for entry in scanned), sorted(entry["path"] for entry in entries))
        self.assertGreater(len(ordinary), 0)
        for config, group in frozen.items():
            self.assertTrue(group, f"{config} is named by no inventory entry")

    def test_only_the_frozen_locks_name_a_config(self):
        named = {entry["path"]: entry["config"] for entry in self.inventory["lockfiles"] if "config" in entry}
        self.assertEqual(named, {path: lock["config"] for path, lock in FROZEN_LOCKS.items()})
        for path, lock in FROZEN_LOCKS.items():
            self.assertIn(path, [entry["path"] for entry in self.inventory["lockfiles"]], "a frozen lock is a lockfile entry, not a manifest")

    def test_the_ordinary_config_has_no_exception_for_a_frozen_advisory(self):
        self.assertEqual(ignore_entry_problems(self.ordinary_config), [])
        ids = {entry["id"] for entry in self.ordinary_config.get("IgnoredVulns", [])}
        frozen_ids = {advisory for lock in FROZEN_LOCKS.values() for advisory in lock["advisories"]}
        self.assertEqual(ids & frozen_ids, set(), "the exception belongs in the frozen config, which only the frozen scan uses")
        self.assertEqual({override.get("name") for override in self.ordinary_config.get("PackageOverrides", [])} & {"next", "braces"}, set())
        self.assertEqual(override_problems(self.ordinary_config), [])

    def test_a_config_with_a_key_the_scanner_reads_case_blind_is_a_problem(self):
        good = {"IgnoredVulns": [{"id": "GHSA-x", "reason": "r", "ignoreUntil": date.today() + timedelta(days=30)}]}
        self.assertEqual(ignore_entry_problems(good), [])
        for label, config in (("an upper-case ID beside id", {"IgnoredVulns": [{**good["IgnoredVulns"][0], "ID": "GHSA-y"}]}),
                              ("a case-varied reason key", {"IgnoredVulns": [{**good["IgnoredVulns"][0], "Reason": "r"}]}),
                              ("a case-varied top-level table", {**good, "ignoredvulns": good["IgnoredVulns"]})):
            with self.subTest(label=label):
                self.assertNotEqual(ignore_entry_problems(config), [], label)

    def test_a_package_override_that_could_match_next_or_braces_is_a_problem(self):
        self.assertEqual(override_problems({"PackageOverrides": [{"name": "lib", "ecosystem": "PyPI", "ignore": True}]}), [])
        for override in ({"name": "next", "ecosystem": "npm", "ignore": True},
                         {"name": "nex[t]", "nameIsRegex": True, "ecosystem": "npm", "ignore": True},
                         {"name": "brac[e]s", "nameIsRegex": True, "ecosystem": "npm", "ignore": True},
                         {"name": "nex[t]", "nameIsRegex": True, "ignore": True},
                         {"name": ".*", "nameIsRegex": True, "ecosystem": "NPM"},
                         {"name": "nex[t]", "nameIsRegex": True, "ecosystem": "PyPI", "Ecosystem": "npm", "ignore": True},
                         {"name": "lib", "Name": "next", "ecosystem": "PyPI", "Ecosystem": "npm", "ignore": True},
                         {"name": "lib", "ecosystem": "PyPI", "vulnerability": {"Ignore": True}}):
            with self.subTest(override=override):
                self.assertNotEqual(override_problems({"PackageOverrides": [override]}), [], override)

    def test_each_frozen_config_holds_exactly_the_advisories_of_its_locks(self):
        for config_path in sorted({lock["config"] for lock in FROZEN_LOCKS.values()}):
            config = tomllib.loads((ROOT / config_path).read_text(encoding="utf-8"))
            self.assertEqual(set(config), {"IgnoredVulns"}, "a frozen config holds ignores only, no package override")
            expected = sorted(advisory for lock in FROZEN_LOCKS.values() if lock["config"] == config_path for advisory in lock["advisories"])
            self.assertEqual(sorted(entry["id"] for entry in config["IgnoredVulns"]), expected)
            self.assertEqual(ignore_entry_problems(config), [])
            self.assertEqual(active_ignores(config), set(expected), 'an archive exception must still be active (UTC)')

    def test_each_frozen_lock_matches_its_reviewed_digest_and_names_evidence(self):
        for path, lock in FROZEN_LOCKS.items():
            self.assertTrue((ROOT / path).is_file(), path)
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), lock["sha256"],
                             f"{path} changed after its review: re-review whether it reaches the advisories of its config, then record the new sha256")
            self.assertTrue((ROOT / lock["evidence"]).is_file(), lock["evidence"])

    def test_the_workflow_scans_each_config_in_its_own_invocation(self):
        text = self.workflow
        configs = {lock["config"] for lock in FROZEN_LOCKS.values()}
        self.assertEqual(re.findall(r"(?m)^\s+frozen_config=(\S+)$", text), sorted(configs))
        for needle in ('select(has("config") | not)', 'select(.config == $config)', "--config .github/osv-scanner.toml", '--config "$frozen_config"',
                       '$(( ${#lockfiles[@]} + ${#frozen[@]} ))',
                       'jq \'.lockfiles | length\' "$inventory"', "osv-scanner-frozen-macos.sarif"):
            self.assertIn(needle, text, needle)
        # the frozen scan never gets the ordinary lock list, and the ordinary scan never gets the frozen one
        self.assertEqual(text.count('"${frozen[@]}")'), 1)
        self.assertEqual(text.count('"${lockfiles[@]}")'), 1)
        # The retired WSL group went on 2026-10-04, when its lock was renamed out of discovery; only the
        # preflight's retirement tests still name that partition.
        rest = [line for line in text.splitlines() if "tests.test_wsl_retrieval.RetiredRunnerTests" not in line]
        self.assertEqual([line for line in rest if "wsl" in line.lower()], [])

    def test_the_partition_check_catches_a_mutant_inventory(self):
        entries = [{"path": "a"}, {"path": "b", "config": FROZEN_CONFIG}, {"path": "c", "config": ".github/other.toml"}, {"path": "d", "parser": "requirements.txt"}]
        ordinary, frozen, stray = scan_partition(entries, {FROZEN_CONFIG})
        self.assertEqual([entry["path"] for entry in ordinary], ["a", "d"])
        self.assertEqual({config: [entry["path"] for entry in group] for config, group in frozen.items()}, {FROZEN_CONFIG: ["b"]})
        self.assertEqual([entry["path"] for entry in stray], ["c"])
        self.assertEqual(len(ordinary) + sum(len(group) for group in frozen.values()) + len(stray), len(entries))

    def test_expired_ignore_fails_the_policy_before_a_scan(self):
        for until in [date(2000, 1, 1), date.today()]:
            with self.subTest(until=until):
                config = {'IgnoredVulns': [{'id': 'GHSA-vfj7-8cjw-p6xm', 'reason': 'dated retirement evidence',
                                           'ignoreUntil': until}]}
                self.assertTrue(any('expired' in message for message in ignore_entry_problems(config)))


class SyntheticWorkflowInvocationTests(unittest.TestCase):
    """Execute the workflow shell with recording doubles; check routing/status behavior, never native scanner acceptance."""

    configs = ['.github/osv-scanner.toml', FROZEN_CONFIG]

    def run_step(self, inventory=None, primary=(0, 0), sarif=(0, 0), write_sarif=True, preflight=0, script=None):
        if script is None:
            workflow = WORKFLOW.read_text(encoding='utf-8')
            step = workflow.split('      - name: Scan every listed lockfile and manifest', 1)[1]
            script = textwrap.dedent(step.split('        run: |\n', 1)[1].split('      - name:', 1)[0])
        inventory = inventory or json.loads(INVENTORY.read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            (scratch / '.github').mkdir()
            (scratch / '.github/osv-scanner-lockfiles.json').write_text(json.dumps(inventory), encoding='utf-8')
            binaries = scratch / 'bin'
            binaries.mkdir()
            tool_directory = scratch / 'runner/osv-scanner'
            tool_directory.mkdir(parents=True)
            double = '#!' + sys.executable + '\n' + textwrap.dedent('''\
                import json, os, sys
                from pathlib import Path
                argv = sys.argv[1:]
                preflight = Path(sys.argv[0]).name == 'python3'
                fact = {'kind': 'preflight' if preflight else 'scanner', 'argv': argv}
                with open(os.environ['OSV_WORKFLOW_LOG'], 'a', encoding='utf-8') as output:
                    output.write(json.dumps(fact) + '\\n')
                if preflight:
                    raise SystemExit(int(os.environ['OSV_WORKFLOW_PREFLIGHT']))
                configs = [argv[index + 1] if arg == '--config' else arg.split('=', 1)[1]
                           for index, arg in enumerate(argv) if arg == '--config' or arg.startswith('--config=')]
                if len(configs) != 1:
                    raise SystemExit(2)
                config = configs[0]
                format_run = '--format' in argv
                if format_run:
                    Path(argv[argv.index('--output-file') + 1]).write_text('synthetic workflow fixture; not native SARIF\\n')
                status = json.loads(os.environ['OSV_WORKFLOW_STATUSES'])[config]['sarif' if format_run else 'primary']
                raise SystemExit(status)
                ''')
            for path in [binaries / 'python3', tool_directory / 'osv-scanner']:
                path.write_text(double, encoding='utf-8')
                path.chmod(0o700)
            environment = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ['PATH'],
                               RUNNER_TEMP=str(scratch / 'runner'), WRITE_SARIF=str(write_sarif).lower(),
                               OSV_WORKFLOW_LOG=str(scratch / 'calls.jsonl'), OSV_WORKFLOW_PREFLIGHT=str(preflight),
                               OSV_WORKFLOW_STATUSES=json.dumps({config: {'primary': p, 'sarif': s}
                                   for config, p, s in zip(self.configs, primary, sarif)}))
            result = subprocess.run(['bash', '-c', script], cwd=scratch, env=environment,
                                    text=True, capture_output=True, check=False)
            log = scratch / 'calls.jsonl'
            calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            artifacts = sorted(path.name for path in tool_directory.glob('*.sarif'))
        return result, calls, artifacts

    def test_two_invocations_keep_every_input_and_parser_separate(self):
        result, calls, artifacts = self.run_step()
        self.assertEqual(result.returncode, 0, result.stderr)
        preflight = [call for call in calls if call['kind'] == 'preflight']
        self.assertEqual(len(preflight), 1)
        self.assertIn('tests.test_osv_lockfile_coverage.LockfileInventoryTests', preflight[0]['argv'])
        self.assertIn('tests.test_osv_lockfile_coverage.FrozenScanTests', preflight[0]['argv'])
        self.assertIn('tests.test_wsl_retrieval.RetiredRunnerTests', preflight[0]['argv'])
        scanners = [call['argv'] for call in calls if call['kind'] == 'scanner']
        self.assertEqual(len(scanners), 4)
        for argv in scanners:
            self.assertEqual(sum(arg == '--config' or arg.startswith('--config=') for arg in argv), 1, argv)
        inventory = json.loads(INVENTORY.read_text(encoding='utf-8'))
        for config in self.configs:
            group = [argv for argv in scanners
                     if [argv[index + 1] if arg == '--config' else arg.split('=', 1)[1]
                         for index, arg in enumerate(argv) if arg == '--config' or arg.startswith('--config=')] == [config]]
            self.assertEqual(len(group), 2, config)
            expected = ['--lockfile=' + entry.get('parser', '') + ':' + entry['path']
                        for entry in inventory['lockfiles']
                        if entry.get('config', '.github/osv-scanner.toml') == config]
            self.assertGreater(len(expected), 0)
            for argv in group:
                self.assertEqual(argv[:2], ['scan', 'source'])
                self.assertIn('--no-resolve', argv)
                self.assertEqual([arg for arg in argv if arg.startswith('--lockfile=')], expected)
        self.assertEqual(artifacts, ['osv-scanner-frozen-macos.sarif', 'osv-scanner.sarif'])

    def test_each_primary_and_sarif_status_is_retained(self):
        cases = [((1, 0), (0, 0), 1), ((0, 1), (0, 0), 1),
                 ((2, 0), (0, 0), 2), ((0, 0), (1, 0), 1),
                 ((0, 0), (0, 1), 1), ((0, 0), (0, 7), 7),
                 ((0, 7), (2, 0), 7), ((0, 127), (0, 0), 127)]
        for primary, sarif, expected in cases:
            with self.subTest(primary=primary, sarif=sarif):
                result, calls, artifacts = self.run_step(primary=primary, sarif=sarif)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual(len([call for call in calls if call['kind'] == 'scanner']), 4)
                self.assertEqual(len(artifacts), 2)

    def test_pr_collects_both_primary_statuses_without_sarif(self):
        result, calls, artifacts = self.run_step(primary=(0, 1), write_sarif=False)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(len([call for call in calls if call['kind'] == 'scanner']), 2)
        self.assertEqual(artifacts, [])

    def test_unknown_duplicate_missing_and_wrong_archive_assignments_fail_before_scan(self):
        for mutation in ['unknown-config', 'duplicate', 'missing-archive', 'wrong-archive-lock']:
            with self.subTest(mutation=mutation):
                inventory = json.loads(INVENTORY.read_text(encoding='utf-8'))
                entries = inventory['lockfiles']
                if mutation == 'unknown-config':
                    entries[0]['config'] = '.github/unknown.toml'
                elif mutation == 'duplicate':
                    entries.append(dict(entries[0]))
                elif mutation == 'missing-archive':
                    inventory['lockfiles'] = [entry for entry in entries if entry.get('config') != FROZEN_CONFIG]
                else:
                    archive = next(entry for entry in entries if entry.get('config') == FROZEN_CONFIG)
                    archive['path'] = 'other-active-project/pnpm-lock.yaml'
                result, calls, artifacts = self.run_step(inventory=inventory)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual([call for call in calls if call['kind'] == 'scanner'], [])
                self.assertEqual(artifacts, [])

    def test_preflight_failure_is_returned_before_scan(self):
        for status in [1, 7, 127]:
            with self.subTest(status=status):
                result, calls, artifacts = self.run_step(preflight=status)
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0]['kind'], 'preflight')
                self.assertEqual(artifacts, [])

    def test_the_step_catches_a_mutant_of_itself(self):
        # Extend main's recording doubles; this method is outside the real preflight.
        workflow = WORKFLOW.read_text(encoding='utf-8')
        step = workflow.split('      - name: Scan every listed lockfile and manifest', 1)[1]
        script = textwrap.dedent(step.split('        run: |\n', 1)[1].split('      - name:', 1)[0])
        routing = 'test_two_invocations_keep_every_input_and_parser_separate'
        statuses = 'test_each_primary_and_sarif_status_is_retained'
        assignment = textwrap.dedent('''\
            jq -e --arg mac_config "$frozen_config" '
              .lockfiles as $entries | ($entries | map(.path)) as $paths |
              (($paths | length) == ($paths | unique | length)) and
              ([$entries[] | select(.config == $mac_config) | .path] ==
                ["evidence/artifacts/macos-application-20260924/variant/pnpm-lock.yaml"])
            ' "$inventory" > /dev/null || exit 1
            ''')
        count_guard = '-eq "$(jq \'.lockfiles | length\' "$inventory")"'
        mutants = [
            ('R1 duplicated config', routing, [
                ('"${scan[@]}"\nstatus=$?\n', 'scan+=(--config "$frozen_config")\n"${scan[@]}"\nstatus=$?\n')]),
            ('R1 duplicated inline config', routing, [
                ('"${scan[@]}"\nstatus=$?\n', 'scan+=(--config="$frozen_config")\n"${scan[@]}"\nstatus=$?\n')]),
            ('R2 omitted ordinary input and weakened count', routing, [
                ('| select(has("config") | not) |', '| select(has("config") | not) | select(.path != ".github/requirements-ci.txt") |'),
                (count_guard, count_guard.replace('-eq', '-le'))]),
            ('macOS scan uses ordinary config', routing, [
                ('scan_frozen=("$RUNNER_TEMP/osv-scanner/osv-scanner" scan source --config "$frozen_config"',
                 'scan_frozen=("$RUNNER_TEMP/osv-scanner/osv-scanner" scan source --config .github/osv-scanner.toml')]),
            ('primary status dropped', statuses, [
                ('statuses=("$status" "$frozen_status")', 'statuses=("$status")')]),
            ('R3 SARIF statuses dropped', statuses, [
                ('statuses+=("$sarif_status" "$frozen_sarif_status")\n', '')]),
            ('scanner error no longer wins', statuses, [
                ('if [ "$code" -gt "$status" ]; then', 'if [ "$code" -eq 1 ]; then')]),
            ('preflight failure ignored', 'test_preflight_failure_is_returned_before_scan', [
                ('tests.test_wsl_retrieval.RetiredRunnerTests || exit "$?"', 'tests.test_wsl_retrieval.RetiredRunnerTests')]),
            ('SARIF written on pull_request', 'test_pr_collects_both_primary_statuses_without_sarif', [
                ('if [ "$WRITE_SARIF" = true ]; then', 'if true; then')]),
            ('jq assignment and uniqueness guard removed', 'test_unknown_duplicate_missing_and_wrong_archive_assignments_fail_before_scan', [
                (assignment, '')]),
            ('ordinary scan resolves unpinned inputs', routing, [
                ('--no-resolve "${lockfiles[@]}")', '"${lockfiles[@]}")')]),
        ]
        for name, check, replacements in mutants:
            with self.subTest(mutation=name, check=check):
                mutated = script
                for old, new in replacements:
                    self.assertIn(old, script, name)
                    self.assertEqual(mutated.count(old), 1, name)
                    mutated = mutated.replace(old, new, 1)
                case = type(self)(check)
                result = unittest.TestResult()
                with patch.object(case, 'run_step', side_effect=lambda *args, **kwargs: self.run_step(*args, script=mutated, **kwargs)):
                    case.run(result)
                self.assertEqual(result.errors, [], result.errors)
                self.assertTrue(result.failures, f'{name} survived {check}')


class FrozenPolicyMutationTests(unittest.TestCase):
    """Mutate candidate policy inputs and exercise the actual guards the workflow invokes.

    Scratch evidence is explicitly synthetic; these controls prove policy rejection,
    never archive eligibility or native scanner acceptance.
    """

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.scratch = Path(temporary.name)
        for path, grant in FROZEN_LOCKS.items():
            for name in (path, grant['config']):
                target = self.scratch / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / name).read_bytes())
            evidence = self.scratch / grant['evidence']
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text('{"synthetic_policy_fixture": true}\n', encoding='utf-8')
        # The frozen macOS archive is the one config-bound lock since the WSL group's removal (2026-10-04).
        self.lock, grant = next(iter(FROZEN_LOCKS.items()))
        self.config = self.scratch / grant['config']
        self.receipt = self.scratch / grant['evidence']

    def check(self, method, **attributes):
        case = FrozenScanTests(method)
        for key, value in attributes.items():
            setattr(case, key, value)
        result = unittest.TestResult()
        with patch(__name__ + '.ROOT', self.scratch):
            case.run(result)
        return result

    def assert_rejected(self, method, **attributes):
        result = self.check(method, **attributes)
        self.assertTrue(result.failures, 'the actual preflight guard accepted the changed input')
        self.assertEqual(result.errors, [], result.errors)

    def test_changed_lock_bytes_and_missing_evidence_are_rejected(self):
        method = 'test_each_frozen_lock_matches_its_reviewed_digest_and_names_evidence'
        self.assertTrue(self.check(method).wasSuccessful())
        lock = self.scratch / self.lock
        original = lock.read_bytes()
        lock.write_bytes(original + b'\n')
        self.assert_rejected(method)
        lock.write_bytes(original)
        self.receipt.unlink()
        self.assert_rejected(method)

    def test_frozen_advisory_or_package_override_cannot_leak_to_ordinary_inputs(self):
        original = FrozenScanTests.ordinary_config
        overrides = {
            'package-override': {'name': 'braces', 'ignore': True},
            'next-regex': {'name': 'nex[t]', 'nameIsRegex': True, 'ecosystem': 'npm', 'ignore': True},
            'npm-case-regex': {'name': '.*', 'nameIsRegex': True, 'ecosystem': 'NPM', 'ignore': True},
            'ecosystem-less-regex': {'name': 'brac[e]s', 'nameIsRegex': True, 'ignore': True},
            'case-aliased-ecosystem': {'name': 'nex[t]', 'nameIsRegex': True, 'ecosystem': 'PyPI', 'Ecosystem': 'npm', 'ignore': True},
            'case-aliased-name-and-ecosystem': {'name': 'lib', 'Name': 'next', 'ecosystem': 'PyPI', 'Ecosystem': 'npm', 'ignore': True},
        }
        for mutation in ('advisory', *overrides):
            with self.subTest(mutation=mutation):
                config = {key: list(value) for key, value in original.items()}
                if mutation == 'advisory':
                    # Well formed, so the frozen-id check is the only one that can reject it.
                    config.setdefault('IgnoredVulns', []).append({
                        'id': FROZEN_LOCKS[self.lock]['advisories'][0], 'reason': 'synthetic leaked exception',
                        'ignoreUntil': date.today() + timedelta(days=30)})
                    self.assertEqual(ignore_entry_problems(config), [])
                else:
                    config.setdefault('PackageOverrides', []).append(overrides[mutation])
                self.assert_rejected('test_the_ordinary_config_has_no_exception_for_a_frozen_advisory',
                                     ordinary_config=config)

    def test_an_unbound_advisory_cannot_leak_into_the_macos_config(self):
        # GHSA-vfj7-8cjw-p6xm belonged to the retired WSL group (removed 2026-10-04); no frozen lock carries it now.
        until = date.today() + timedelta(days=30)
        with self.config.open('a', encoding='utf-8') as output:
            output.write(f'\n[[IgnoredVulns]]\nid = "GHSA-vfj7-8cjw-p6xm"\n'
                         f'ignoreUntil = {until.isoformat()}\nreason = "synthetic leaked exception"\n')
        self.assert_rejected('test_each_frozen_config_holds_exactly_the_advisories_of_its_locks')

    def test_expired_config_is_rejected_by_the_actual_preflight_guard(self):
        text = self.config.read_text(encoding='utf-8')
        expired = re.sub(r'(?m)^ignoreUntil = \S+$', 'ignoreUntil = 2000-01-01', text)
        self.assertNotEqual(expired, text, 'the frozen config has no ignoreUntil line to expire')
        self.config.write_text(expired, encoding='utf-8')
        self.assert_rejected('test_each_frozen_config_holds_exactly_the_advisories_of_its_locks')

    def test_ordinary_inventory_omission_is_rejected_by_the_actual_preflight_guard(self):
        inventory = json.loads(INVENTORY.read_text(encoding='utf-8'))
        inventory['lockfiles'].remove(next(entry for entry in inventory['lockfiles'] if 'config' not in entry))
        case = LockfileInventoryTests('test_every_tracked_lockfile_and_manifest_is_listed')
        case.inventory = inventory
        result = unittest.TestResult()
        case.run(result)
        self.assertTrue(result.failures, 'preflight accepted an omitted tracked active input')
        self.assertEqual(result.errors, [], result.errors)


class DependencyFreeMutationTests(unittest.TestCase):
    """Mutate a scratch copy of each dependency_free manifest and its entry, and run the actual inventory test on it.

    Synthetic policy controls: they prove the check rejects a manifest with something to scan, not that GitHub's
    dependency graph or OSV-Scanner reports nothing for the real one (the rename's receipt holds those controls).
    """

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.scratch = Path(temporary.name)
        self.inventory = json.loads(INVENTORY.read_text(encoding='utf-8'))
        self.assertTrue(self.inventory['dependency_free'], 'no dependency_free entry to mutate')
        self.entry = self.inventory['dependency_free'][0]
        for name in (self.entry['path'], self.entry['evidence']):
            target = self.scratch / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())
        self.manifest = self.scratch / self.entry['path']

    def check(self, inventory=None):
        case = LockfileInventoryTests('test_dependency_free_manifests_have_nothing_to_scan')
        case.inventory = inventory or self.inventory
        result = unittest.TestResult()
        with patch(__name__ + '.ROOT', self.scratch):
            case.run(result)
        return result

    def assert_rejected(self, label, inventory=None):
        result = self.check(inventory)
        self.assertTrue(result.failures, f'{label} was accepted')
        self.assertEqual(result.errors, [], result.errors)

    def test_unchanged_copy_passes(self):
        result = self.check()
        self.assertTrue(result.wasSuccessful(), result.failures + result.errors)

    def test_a_manifest_with_something_to_scan_is_rejected(self):
        original = self.manifest.read_text(encoding='utf-8')
        mutations = {
            'restored dependency': {'dependencies': {'@tobilu/qmd': '2.8.3'}},
            'case-varied devDependencies': {'DevDependencies': {'braces': '3.0.3'}},
            'peer dependency metadata': {'peerDependenciesMeta': {'braces': {'optional': True}}},
            'workspaces': {'workspaces': ['packages/*']},
            'overrides': {'overrides': {'braces': '3.0.3'}},
            'resolutions': {'resolutions': {'braces': '3.0.3'}},
        }
        for label, fields in mutations.items():
            with self.subTest(mutation=label):
                self.manifest.write_text(json.dumps({**json.loads(original), **fields}), encoding='utf-8')
                self.assert_rejected(label)
        self.manifest.write_text(original, encoding='utf-8')

    def test_a_lockfile_beside_the_manifest_is_rejected(self):
        for name in sorted(JS_LOCK_NAMES) + ['Package-Lock.json']:
            with self.subTest(beside=name):
                lock = self.manifest.parent / name
                lock.write_text('{}\n', encoding='utf-8')
                try:
                    self.assert_rejected(name)
                finally:
                    lock.unlink()

    def test_an_unreasoned_unevidenced_or_non_package_json_entry_is_rejected(self):
        for label in ('empty reason', 'missing evidence', 'not a package.json'):
            with self.subTest(mutation=label):
                inventory = json.loads(json.dumps(self.inventory))
                entry = inventory['dependency_free'][0]
                if label == 'empty reason':
                    entry['reason'] = ' '
                elif label == 'missing evidence':
                    entry['evidence'] = 'evidence/receipts/no-such-receipt.json'
                else:
                    entry['path'] = entry['path'].rsplit('/', 1)[0] + '/requirements.txt'
                self.assert_rejected(label, inventory)


class AllowedLockTests(unittest.TestCase):
    """Each IGNORE_ALLOWED_LOCKS entry is a scanned lock, bound to the advisories reviewed for it, the sha256 of the
    content that review covered and an existing evidence file."""

    config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))

    def test_every_allowed_lock_is_an_inventory_lockfile(self):
        listed = {entry["path"] for entry in self.inventory["lockfiles"]}
        self.assertEqual(sorted(set(IGNORE_ALLOWED_LOCKS) - listed), [],
                         f"an allowed lock must be scanned: list it under lockfiles in {INVENTORY.relative_to(ROOT)}")

    def test_every_allowed_lock_matches_its_reviewed_digest(self):
        self.assertEqual(
            digest_drift(), [],
            "these allowed locks changed after their reachability review (path, reviewed sha256, current sha256). "
            "Re-review whether each changed lock reaches the advisories listed for it, then record its new sha256 and "
            "the evidence path of that review in IGNORE_ALLOWED_LOCKS, or remove the entry and the affected pins.")

    def test_every_allowed_lock_names_existing_evidence(self):
        for path, grant in IGNORE_ALLOWED_LOCKS.items():
            evidence = grant.get("evidence", "")
            self.assertTrue(evidence and (ROOT / evidence).is_file(),
                            f"{path}: evidence must be the repository path of its non-reachability receipt")

    def test_allowed_advisories_are_scoped_active_ignores(self):
        active = active_ignores(self.config)
        for path, grant in IGNORE_ALLOWED_LOCKS.items():
            advisories = set(grant["advisories"])
            self.assertTrue(advisories, f"{path}: an entry lists the advisories it may pin")
            self.assertLessEqual(advisories, set(IGNORE_SCOPES), f"{path}: every advisory needs an IGNORE_SCOPES entry")
            self.assertLessEqual(advisories, active,
                                 f"{path}: each advisory needs an ignore in {CONFIG.name} that OSV-Scanner still "
                                 "applies (ignoreUntil after today, UTC). Re-review reachability and extend it with a "
                                 "new dated reason, or drop the advisory from this entry")

    def test_an_ignore_is_active_only_before_its_ignore_until_date(self):
        # The review's probe: both ignores dated 2000-01-01 still counted as active, though OSV-Scanner had stopped
        # applying them. One dated today is inactive too (active_ignores).
        today = date(2026, 9, 27)
        config = {"IgnoredVulns": [{"id": "GHSA-a", "ignoreUntil": date(2000, 1, 1)},
                                   {"id": "GHSA-b", "ignoreUntil": today - timedelta(days=1)},
                                   {"id": "GHSA-c", "ignoreUntil": today},
                                   {"id": "GHSA-d", "ignoreUntil": today + timedelta(days=1)},
                                   {"id": "GHSA-e", "ignoreUntil": datetime(2000, 1, 1, tzinfo=timezone.utc)}]}
        self.assertEqual(active_ignores(config, today), {"GHSA-d"})
        expired = {"IgnoredVulns": [dict(entry, ignoreUntil=date(2000, 1, 1)) for entry in self.config["IgnoredVulns"]]}
        for path, grant in IGNORE_ALLOWED_LOCKS.items():
            self.assertFalse(set(grant["advisories"]) <= active_ignores(expired), path)

    def test_an_allowed_lock_is_exempt_only_for_the_advisories_it_lists(self):
        # A lock allowed for the nltk advisory alone that also pins setuptools below the fix (a relock, or a new pin)
        # must still report the setuptools pin, and only that pin.
        with tempfile.TemporaryDirectory() as scratch:
            lock = Path(scratch) / "requirements.lock"  # an absolute path: ROOT / path keeps it as is
            lock.write_text("nltk==3.10.3 \\\n    --hash=sha256:00\nsetuptools==80.10.2\n", encoding="utf-8")
            evidence = Path(scratch) / "reachability.json"
            evidence.write_text("{}\n", encoding="utf-8")
            allowed = {str(lock): {"advisories": ["GHSA-8mgp-746c-j5xp"],
                                   "sha256": hashlib.sha256(lock.read_bytes()).hexdigest(), "evidence": str(evidence)}}
            found = affected_pins([{"path": str(lock), "parser": "requirements.txt"}], list(IGNORE_SCOPES), allowed)
        self.assertEqual([(package, version, advisory) for _, package, version, advisory in found],
                         [("setuptools", "80.10.2", "GHSA-h35f-9h28-mq5c")])

    def test_the_digest_check_catches_a_changed_byte(self):
        with tempfile.TemporaryDirectory() as scratch:
            lock = Path(scratch) / "requirements.lock"
            lock.write_bytes(b"nltk==3.10.3 \\\n    --hash=sha256:00\n")
            evidence = Path(scratch) / "reachability.json"
            evidence.write_text("{}\n", encoding="utf-8")
            reviewed = hashlib.sha256(lock.read_bytes()).hexdigest()
            allowed = {str(lock): {"advisories": ["GHSA-8mgp-746c-j5xp"], "sha256": reviewed,
                                   "evidence": str(evidence)}}
            self.assertEqual(digest_drift(allowed), [])
            content = bytearray(lock.read_bytes())
            content[content.index(b"3.10.3") + 5] ^= 1  # one byte: nltk==3.10.3 becomes nltk==3.10.2
            lock.write_bytes(bytes(content))
            drift = digest_drift(allowed)
        self.assertEqual(drift, [(str(lock), reviewed, hashlib.sha256(bytes(content)).hexdigest())])

    def test_the_digest_is_taken_over_bytes_not_text(self):
        # CRLF and LF read back as the same text, so only a digest over the bytes sees a CRLF relock.
        lf, crlf = b"nltk==3.10.3 \\\n    --hash=sha256:00\n", b"nltk==3.10.3 \\\r\n    --hash=sha256:00\r\n"
        with tempfile.TemporaryDirectory() as scratch:
            lock = Path(scratch) / "requirements.lock"
            lock.write_bytes(crlf)
            self.assertEqual(lock.read_text(encoding="utf-8"), lf.decode("utf-8"))
            allowed = {str(lock): {"advisories": ["GHSA-8mgp-746c-j5xp"], "sha256": hashlib.sha256(lf).hexdigest()}}
            drift = digest_drift(allowed)
        self.assertNotEqual(hashlib.sha256(crlf).hexdigest(), hashlib.sha256(lf).hexdigest())
        self.assertEqual(drift, [(str(lock), hashlib.sha256(lf).hexdigest(), hashlib.sha256(crlf).hexdigest())])

    def test_the_digest_check_reads_every_allowed_lock(self):
        # Two allowed locks, of which only the second (in sorted order) changed after its review.
        reviewed = hashlib.sha256(b"nltk==3.10.3\n").hexdigest()
        with tempfile.TemporaryDirectory() as scratch:
            first, second = Path(scratch) / "a.lock", Path(scratch) / "b.lock"
            first.write_bytes(b"nltk==3.10.3\n")
            second.write_bytes(b"nltk==3.10.2\n")
            allowed = {str(path): {"advisories": ["GHSA-8mgp-746c-j5xp"], "sha256": reviewed}
                       for path in (first, second)}
            drift = digest_drift(allowed)
        self.assertEqual(drift, [(str(second), reviewed, hashlib.sha256(b"nltk==3.10.2\n").hexdigest())])

    def test_a_missing_allowed_lock_is_reported(self):
        with tempfile.TemporaryDirectory() as scratch:
            missing = str(Path(scratch) / "removed.lock")
            drift = digest_drift({missing: {"advisories": ["GHSA-8mgp-746c-j5xp"], "sha256": "0" * 64}})
        self.assertEqual(drift, [(missing, "0" * 64, None)])

    def test_every_allowed_lock_is_self_contained(self):
        self.assertEqual(allowed_lock_includes(), [],
                         "an allowed lock's sha256 covers only its own bytes: inline the included pins, then review "
                         "the lock and record its new sha256")

    def test_an_include_in_an_allowed_lock_is_flagged_and_not_exempt(self):
        # An allowed lock is exempt only for its own reviewed lines: a pin an include brings in is reported, and the
        # include line itself breaks the self-contained rule.
        files = {"requirements.lock": "nltk==3.10.3\n-r pins.txt\n", "pins.txt": "nltk==3.10.3\n"}
        self.assertEqual(scratch_findings(files, allowed_advisories=["GHSA-8mgp-746c-j5xp"]),
                         [("pins.txt", "nltk", "3.10.3", "GHSA-8mgp-746c-j5xp")])
        with tempfile.TemporaryDirectory() as scratch:
            lock = Path(scratch) / "requirements.lock"
            lock.write_text("nltk==3.10.3 \\\n    --hash=sha256:00\n-r pins.txt\n", encoding="utf-8")
            allowed = {str(lock): {"advisories": ["GHSA-8mgp-746c-j5xp"],
                                   "sha256": hashlib.sha256(lock.read_bytes()).hexdigest()}}
            self.assertEqual(allowed_lock_includes(allowed), [(str(lock), "-r pins.txt")])


if __name__ == "__main__":
    unittest.main()
