"""Keep security-scan.yml's OSV-Scanner inventory complete (docs/decisions/2026-09-22-github-automation-closure.md).

.github/osv-scanner-lockfiles.json is the one checked-in list of files the osv-scanner job
scans. These tests fail when a tracked lockfile or manifest is missing from it (unless its
"excluded" list names it with a reason and an evidence path), when a listed file no longer exists, when a parser name is not one OSV-Scanner v2 accepts for that file,
when an ignore in .github/osv-scanner.toml lacks an id, a reason or an ignoreUntil at most 90
days away, and when a repo-wide ignore would hide a pin that IGNORE_ALLOWED_LOCKS does not allow
for that lock and advisory at the lock's reviewed sha256. That guard follows includes and fails
closed on a version or line it cannot parse strictly; an allowed lock must be self-contained, and
an ignore counts as active only before its ignoreUntil date. The npm advisory (next) is guarded by
readers for pnpm, package-lock and yarn locks (npm_next_pins) that fail closed on any other npm lock.
"""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / ".github/osv-scanner-lockfiles.json"
CONFIG = ROOT / ".github/osv-scanner.toml"
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
PARSERS = {"requirements.txt", "packages.lock.json"}


# osv-scanner 2.6.0 matches [[IgnoredVulns]] by id in every lockfile it scans (ShouldIgnore checks only the id and
# ignoreUntil, and security-scan.yml passes one --config for the whole inventory). An ignore added for one lock is
# therefore repo-wide. IGNORE_SCOPES names the package versions each such ignore affects. IGNORE_ALLOWED_LOCKS names the
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
    # next (npm), affected from 16.2.0 and fixed in 16.3.6 (OSV and GitHub records, 2026-09-30). python_pins reads no npm
    # format, so this entry drives the npm readers (npm_next_pins) and their test, not affected_pins; only they use "introduced".
    "GHSA-vcvr-r3jv-pc5j": {"package": "next", "introduced": (16, 2, 0), "fixed": (16, 3, 6)},
}
NEXT_ADVISORY = "GHSA-vcvr-r3jv-pc5j"
IGNORE_ALLOWED_LOCKS = {
    # Live recipe lock, relocked onto PyJWT 2.14.0 and then, on 2026-09-30, onto urllib3 2.8.0 and PyJWT 2.15.0. Its receipt carries
    # the 2026-09-29 oauthlib review forward at this sha256 (those relocks change only the urllib3 and PyJWT entries); the relock onto
    # oauthlib 4.0.0 deletes this entry in the same change.
    "blueprints/runtime-workers/openhands/requirements.lock": {
        "advisories": ["GHSA-hj66-6f7g-4r5v", "GHSA-xpv3-w29h-x7cv"],
        "sha256": "1d11bae34f09707d1ad353e24c33d25c7b004f25de9821d434e065b10969559c",
        "evidence": "evidence/receipts/osv-urllib3-next-20260930.json",
    },
    # Frozen macOS application variant (2026-09-24): package.json and this lock only, no source, installed by nothing here.
    "evidence/artifacts/macos-application-20260924/variant/pnpm-lock.yaml": {
        "advisories": ["GHSA-vcvr-r3jv-pc5j"],
        "sha256": "f1c707b8295e85bd396e49b990de92dc82bc0d58eca1e4e4bef31262d9898cd2",
        "evidence": "evidence/receipts/osv-urllib3-next-20260930.json",
    },
    # Frozen evaluation-only lock. The receipt reviews the oauthlib advisories and carries forward the 2026-09-26
    # nltk and setuptools review (repository-checks.json in the trial directory) at the same sha256.
    "blueprints/us-equities/engine-trials/spy-one-zero-20260926/lumibot/lockcheck/lumibot.lock": {
        "advisories": ["GHSA-8mgp-746c-j5xp", "GHSA-h35f-9h28-mq5c", "GHSA-hj66-6f7g-4r5v", "GHSA-xpv3-w29h-x7cv"],
        "sha256": "a8dce0af2b20c6a0a8829c8fcdd9a3c3207e9e2d57a62d2498bc0116f1af0f1f",
        "evidence": "evidence/receipts/osv-oauthlib-pyjwt-reachability-20260929.json",
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
    if path.name == "uv.lock":
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


# npm-ecosystem lock formats, by file name or by the parser name the inventory gives. python_pins reads none of them, so the next
# advisory is guarded by npm_next_pins, which follows what OSV-Scanner 2.6.0 extracts (google/osv-scalibr at the commit its go.mod
# pins, 3090dbb7aaa24ce7a807899e7f16baa8b802a828, extractor/filesystem/language/javascript/{pnpmlock,packagelockjson,yarnlock}) for the
# CANONICAL output of each tool, and fails closed (None) on anything else: another npm format, a file it cannot read strictly, or
# valid syntax outside the canonical subset (a YAML or JSON construct the port does not model would otherwise be read as "no next").
# A lock in a new format or style therefore fails the test until a reader is extended.
NPM_LOCKS = ("package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb", "deno.lock")
PNPM_LOCKFILE_VERSION = re.compile(r"^lockfileVersion:[ \t]*['\"]?([0-9.]+)['\"]?[ \t\r]*$", re.MULTILINE)
PNPM_ENTRY_KEY = re.compile(r"""  ('(?:[^']|'')+'|[A-Za-z0-9_.][^\s#]*):""")
PNPM_FIELD = re.compile(r"""    ([A-Za-z_][A-Za-z0-9_]*):(?: (\S.*))?""")
PNPM_PLAIN_SCALAR = re.compile(r"""[A-Za-z0-9_.][^#]*""")
NPM_SEMVER = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?")
YARN_VERSION = re.compile(r"""^ {2}"?version"?:? "?([\w.+-]+)"?$""")
GO_JSON_FIELDS = ("lockfileVersion", "packages", "dependencies", "name", "version", "resolved")


def pnpm_scalar(value):
    """A plain or single-quoted YAML scalar, unquoted; None for anything else (a comment, a flow collection, a double-quoted string)."""
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if PNPM_PLAIN_SCALAR.fullmatch(value) and " #" not in value and not value.endswith(":"):
        return value
    return None


def pnpm_packages(text):
    """(key, fields) for each entry of the top-level `packages:` map of one YAML document of a pnpm-lock.yaml written the way pnpm writes it: entry keys at two
    spaces, plain or single-quoted, alone on their line; their `name:` and `version:` fields at four, plain or single-quoted scalars;
    anything deeper is content of a field (flow mappings, block mappings) and is skipped. OSV reads only this map. None when a line
    of the section is outside that subset: an inline record, a double-quoted key, a quoted field key, a trailing comment, a tab or an
    odd indentation, a repeated or quoted `packages` key at the top level."""
    entries, in_packages, seen, current = [], False, False, None
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "\t" in line[: len(line) - len(line.lstrip())]:
            return None
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            if line == "packages:" or line.startswith("packages: "):
                if seen or line != "packages:" and line != "packages: {}":
                    return None
                in_packages, seen, current = line == "packages:", True, None
            elif re.match(r"""['"]?packages['"]?\s*:""", line) or line.startswith("? "):
                return None
            else:
                in_packages, current = False, None
            continue
        if not in_packages:
            continue
        if indent == 2:
            match = PNPM_ENTRY_KEY.fullmatch(line)
            if not match:
                return None
            key = match.group(1)
            current = {}
            entries.append((key[1:-1].replace("''", "'") if key.startswith("'") else key, current))
        elif indent == 4:
            match = PNPM_FIELD.fullmatch(line)
            if not match or current is None:
                return None
            if match.group(1) in ("name", "version"):
                value = pnpm_scalar(match.group(2) or "")
                if value is None:
                    return None
                current[match.group(1)] = value
        elif indent % 2 or current is None:
            return None
    return entries


def pnpm_package_pin(key, fields):
    """The (name, version) OSV derives for one `packages` entry at lockfileVersion 9: the `<name>@<version>` key (a scope's leading @
    kept, `file:` keys carry neither), with the entry's own `name:` and `version:` fields taking precedence."""
    if key.startswith("file:"):
        name = version = ""
    else:
        scoped = key.startswith("@")
        name, _, version = (key[1:] if scoped else key).partition("@")
        name = "@" + name if scoped else name
    return fields.get("name") or name, fields.get("version") or version


def pnpm_documents(text):
    """The non-empty YAML documents of a pnpm-lock.yaml, each as text: pnpm 12 writes the environment lockfile and the project lock as two
    documents separated by `---`, and OSV extracts the packages of every document. None for a document end marker or a marker that
    carries content."""
    documents, current = [], []
    for raw in text.splitlines():
        line = raw.rstrip()
        if line == "---":
            documents.append(current)
            current = []
        elif line.startswith(("---", "...")):
            return None
        else:
            current.append(raw)
    documents.append(current)
    return ["\n".join(lines) for lines in documents if any(line.strip() and not line.strip().startswith("#") for line in lines)]


def pnpm_next_pins(text):
    """The versions of `next` in a pnpm-lock.yaml (any document at lockfileVersion 9; another version, or none: None), from the `packages`
    entries only, as OSV reads them (name and version from the key or the entry's own fields, so tarball, aliased and renamed entries
    count; importers, snapshots and peer declarations are not packages). None for a file outside the canonical subset (pnpm_packages)."""
    documents = pnpm_documents(text)
    if not documents:
        return None
    found = set()
    for document in documents:
        match = PNPM_LOCKFILE_VERSION.search(document)
        if not match:
            return None
        try:
            lock_version = float(match.group(1))
        except ValueError:
            return None
        if not 9.0 <= lock_version < 10.0:
            return None
        entries = pnpm_packages(document)
        if entries is None:
            return None
        for key, fields in entries:
            name, version = pnpm_package_pin(key, fields)
            if name == "next" and version:
                found.add(version)
    return sorted(found)


def npm_path_name(path):
    """OSV's extractNpmPackageName: the last path segment, with the scope when the segment before it is `@scope`."""
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 2 and parts[-2].startswith("@"):
        return parts[-2] + "/" + parts[-1]
    return parts[-1] if parts else ""


def strict_json_object(pairs):
    """An object hook for the package-lock reader. Go decodes a lock into structs whose fields match case-insensitively and merges
    repeated maps, which this port does not model, so a repeated key or a key that differs from a field the reader uses only in its
    case (Packages, Version) is rejected (ValueError), not read as the last or the canonical one."""
    found = {}
    for key, value in pairs:
        if key in found or any(key.lower() == field.lower() and key != field for field in GO_JSON_FIELDS):
            raise ValueError(key)
        found[key] = value
    return found


def package_lock_next_pins(text):
    """The versions of `next` in a package-lock.json or npm-shrinkwrap.json (lockfileVersion 1 to 3), as OSV reads it: the `packages`
    map when the file has one (the root entry "" skipped; the entry's "name", else the last path segment, so aliases and paths such as
    vendor/next count), otherwise the nested `dependencies`, where an `npm:<name>@<version>` version is an alias. Any other
    lockfileVersion, malformed or deeply nested JSON, a repeated or differently cased field, or a next entry without a string version
    gives None."""
    try:
        data = json.loads(text, object_pairs_hook=strict_json_object)
    except (ValueError, RecursionError):
        return None
    if not isinstance(data, dict) or data.get("lockfileVersion") not in (1, 2, 3):
        return None
    found = []
    packages = data.get("packages")
    if "packages" in data and not isinstance(packages, dict):
        return None
    if isinstance(packages, dict):
        for key, meta in packages.items():
            if key == "":
                continue
            if not isinstance(meta, dict):
                return None
            if (meta.get("name") or npm_path_name(key)) == "next":
                if not isinstance(meta.get("version"), str) or not meta["version"] or meta["version"].startswith("file:"):
                    return None  # a local path gives OSV no version to match (Go blanks it); the guard cannot judge it
                found.append(meta["version"])
        return sorted(set(found))
    dependencies = data.get("dependencies", {})
    if not isinstance(dependencies, dict):
        return None
    stack = [dependencies]
    while stack:
        for name, meta in stack.pop().items():
            if not isinstance(meta, dict):
                return None
            version = meta.get("version")
            if isinstance(version, str) and version.startswith("npm:") and "@" in version[4:]:
                name, _, version = version[4:].rpartition("@")
            if name == "next":
                if not isinstance(version, str) or not version or version.startswith("file:"):
                    return None  # a local path gives OSV no version to match (Go blanks it); the guard cannot judge it
                found.append(version)
            nested = meta.get("dependencies")
            if nested is not None:
                if not isinstance(nested, dict):
                    return None
                stack.append(nested)
    return sorted(set(found))


def yarn_package_name(header):
    """OSV's extractYarnPackageName: the package a group header names, taken from its first spec and following `npm:` aliases."""
    text = header
    while True:
        text = text[1:] if text.startswith('"') else text
        text = text[:-1] if text.endswith(":") else text
        text = text.split(",", 1)[0]
        scoped = text.startswith("@")
        name, _, right = (text[1:] if scoped else text).partition("@")
        if right.startswith("npm:") and "@" in right:
            text = right[4:]
            continue
        return "@" + name if scoped else name


def yarn_lock_next_pins(text):
    """The versions of `next` in a yarn.lock (classic or berry) as OSV groups it: a header line, then its indented lines, the first of
    which of the form `version "x"` or `version: x` gives the version; a header naming next through an `npm:` alias counts, and the
    `__metadata:` group and the root workspace (`@workspace:.":`) are skipped. A file with neither the classic header nor
    `__metadata:`, an indented line before any header, or a next group without a version gives None."""
    lines = text.splitlines()
    if not any(line.startswith(("# yarn lockfile v1", "__metadata:")) for line in lines):
        return None
    groups = []
    for line in lines:
        if not line.strip() or line.strip().startswith("#"):
            continue
        if not line.startswith(" "):
            groups.append((line, []))
        elif not groups:
            return None
        else:
            groups[-1][1].append(line)
    found = []
    for header, props in groups:
        if header == "__metadata:" or header.endswith('@workspace:.":') or yarn_package_name(header) != "next":
            continue
        versions = [m.group(1) for m in (YARN_VERSION.match(prop) for prop in props) if m]
        if not versions:
            return None
        found.append(versions[0])
    return sorted(set(found))


NPM_NEXT_READERS = {"pnpm-lock.yaml": pnpm_next_pins, "package-lock.json": package_lock_next_pins, "npm-shrinkwrap.json": package_lock_next_pins,
                    "yarn.lock": yarn_lock_next_pins}


def npm_next_pins(path, name=None):
    """The versions of `next` a lockfile in an npm format pins, or None when the guard cannot read it strictly: no reader for that
    format (bun.lock, bun.lockb, deno.lock, an unknown name), an unreadable file, a format version or a style the reader does not know."""
    reader = NPM_NEXT_READERS.get(name or Path(path).name)
    if reader is None:
        return None
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        return reader(text)
    except RecursionError:
        return None


def npm_affected(version, fixed, introduced):
    """Whether an npm version may be one an advisory affects: introduced <= version < fixed by semver, where a prerelease sorts below
    its release (so 16.2.0-canary.1 is not affected and 16.3.6-canary.1 is) and build metadata is ignored. Text that is not a plain
    semver (a range, a URL, a tag) counts as affected: the guard errs closed."""
    match = NPM_SEMVER.fullmatch(version or "")
    if not match:
        return True
    core = tuple(int(part) for part in match.group(1, 2, 3))
    prerelease = match.group(4) is not None
    if core < introduced or (core == introduced and prerelease):
        return False
    return core < fixed or (core == fixed and prerelease)


def npm_next_findings(entries, root=ROOT, allowed=IGNORE_ALLOWED_LOCKS):
    """(path, problem) for each inventory entry in an npm lock format that the next ignore could hide something in: it pins a next the
    advisory affects (unless `allowed` lists the advisory for that lock, which must then still pin next), or the guard cannot read it
    strictly (fail closed)."""
    scope = IGNORE_SCOPES[NEXT_ADVISORY]
    found = []
    for entry in entries:
        name = entry.get("parser") or Path(entry["path"]).name
        if name not in NPM_LOCKS:
            continue
        versions = npm_next_pins(root / entry["path"], name)
        if versions is None:
            found.append((entry["path"], "cannot be read strictly: extend npm_next_pins for this npm format or style"))
        elif NEXT_ADVISORY in allowed.get(entry["path"], {}).get("advisories", ()):
            if not versions:
                found.append((entry["path"], "the allowed lock no longer pins next; drop its entry"))
        else:
            found += [(entry["path"], f"pins next {version}, which the {NEXT_ADVISORY} ignore hides")
                      for version in versions if npm_affected(version, scope["fixed"], scope["introduced"])]
    return found


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

    def test_every_tracked_lockfile_and_manifest_is_listed(self):
        try:
            files = tracked_files()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a Git checkout; the listed paths are still checked below")
        expected = sorted(path for path in files if TRACKED.search(path))
        self.assertGreater(len(expected), 0)
        missing = sorted(set(expected) - set(self.listed()) - set(self.covered()) - set(self.excluded()))
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
        paths = self.listed() + self.covered() + self.excluded()
        self.assertEqual(len(paths), len(set(paths)), "duplicate inventory entry")
        for path in paths:
            self.assertTrue((ROOT / path).is_file(), f"{path} is listed but missing")

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
        config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
        latest = date.today() + timedelta(days=90)
        for entry in config.get("IgnoredVulns", []):
            self.assertTrue(entry.get("id"), entry)
            self.assertTrue(str(entry.get("reason", "")).strip(), entry)
            until = entry.get("ignoreUntil")
            self.assertIsInstance(until, date, f"{entry.get('id')}: ignoreUntil must be a TOML date")
            if hasattr(until, "date"):
                until = until.date()
            self.assertLessEqual(until, latest, f"{entry.get('id')}: ignoreUntil more than 90 days away")

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

    def test_no_other_suppression_mechanism_bypasses_the_policy(self):
        config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertLessEqual(set(config), {"IgnoredVulns", "PackageOverrides"})
        latest = date.today() + timedelta(days=90)
        for entry in config.get("PackageOverrides", []):
            # An override can silently ignore a whole package; it needs the same reason and expiry.
            self.assertTrue(str(entry.get("reason", "")).strip(), entry)
            until = entry.get("effectiveUntil")
            self.assertIsInstance(until, date, f"{entry}: effectiveUntil must be a TOML date")
            if hasattr(until, "date"):
                until = until.date()
            self.assertLessEqual(until, latest, f"{entry}: effectiveUntil more than 90 days away")


class AllowedLockTests(unittest.TestCase):
    """Each IGNORE_ALLOWED_LOCKS entry is a scanned lock, bound to the advisories reviewed for it, the sha256 of the
    content that review covered and an existing evidence file."""

    config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))

    def test_only_the_allowed_lock_pins_an_affected_next(self):
        # The next ignore is repo-wide by id and python_pins reads no npm format, so every inventory lock in an npm format is read here:
        # the frozen macOS variant may pin next below the fix, no other lock may, and a lock in a format or style no reader knows fails.
        entries = self.inventory["lockfiles"]
        self.assertEqual(npm_next_findings(entries), [])
        read = [entry for entry in entries if (entry.get("parser") or Path(entry["path"]).name) in NPM_LOCKS]
        self.assertGreaterEqual(len(read), 3)  # the two pnpm locks and the retrieval recipe's package-lock.json today
        self.assertEqual({entry["path"]: npm_next_pins(ROOT / entry["path"]) for entry in read if entry["path"].endswith("pnpm-lock.yaml")},
                         {"blueprints/convergence-practice/application-delivery/pnpm-lock.yaml": ["16.3.6"],
                          "evidence/artifacts/macos-application-20260924/variant/pnpm-lock.yaml": ["16.3.5"]})

    def test_the_npm_next_readers_see_every_shape_or_fail_closed(self):
        pnpm = "lockfileVersion: '9.0'\n\n"
        yarn1 = '# yarn lockfile v1\n\n\n'
        resolution = "    resolution: {integrity: sha512-x}\n"
        cases = [
            # pnpm at lockfileVersion 9, canonical style: the `packages` entries only (snapshots, importers and peer declarations are not
            # packages to OSV); plain or single-quoted keys; a scoped or longer name is not next
            ("pnpm-lock.yaml", pnpm + "packages:\n\n  next@16.3.5:\n" + resolution + "    engines: {node: '>=20.9.0'}\n\n  next@16.3.6:\n" + resolution
                               + "\nsnapshots:\n\n  next@16.3.5(react@19.3.0):\n    dependencies:\n      react: 19.3.0\n", ["16.3.5", "16.3.6"]),
            ("pnpm-lock.yaml", pnpm + "packages:\n\n  'next@16.3.5':\n" + resolution, ["16.3.5"]),
            ("pnpm-lock.yaml", pnpm + "packages:\n\n  '@next/env@16.3.5':\n" + resolution + "\n  eslint-config-next@16.3.5:\n" + resolution
                               + "\n  next-themes@0.4.6:\n" + resolution + "    peerDependencies:\n      next: 16.3.5\n      react: ^19\n"
                               "    peerDependenciesMeta:\n      next:\n        optional: true\n", []),
            ("pnpm-lock.yaml", pnpm + "importers:\n  .:\n    dependencies:\n      next:\n        specifier: ^16.3.0\n        version: 16.3.5(react@19.3.0)\n"
                               "\npackages:\n\n  react@19.3.0:\n" + resolution, []),
            ("pnpm-lock.yaml", "lockfileVersion: '9.0'\r\n\r\npackages:\r\n\r\n  next@16.3.5:\r\n    resolution: {integrity: sha512-x}\r\n", ["16.3.5"]),
            ("pnpm-lock.yaml", "lockfileVersion: 9\n\npackages:\n\n  next@16.3.6:\n" + resolution, ["16.3.6"]),
            ("pnpm-lock.yaml", "lockfileVersion: 9.0\n\npackages:\n\n  next@16.3.6:\n" + resolution, ["16.3.6"]),
            ("pnpm-lock.yaml", pnpm + "packages: {}\n", []),
            # pnpm 12 writes two documents (the environment lockfile, then the project lock); OSV extracts the packages of every one
            ("pnpm-lock.yaml", "---\n" + pnpm + "packages:\n\n  react@19.3.0:\n" + resolution + "\n---\n" + pnpm + "packages:\n\n  next@16.3.5:\n" + resolution, ["16.3.5"]),
            ("pnpm-lock.yaml", "---\n" + pnpm + "packages:\n\n  next@16.3.6:\n" + resolution + "\n---\n" + pnpm + "packages:\n\n  next@16.3.5:\n" + resolution,
             ["16.3.5", "16.3.6"]),
            ("pnpm-lock.yaml", "---\n" + pnpm + "packages:\n\n  react@19.3.0:\n" + resolution + "\n---\nlockfileVersion: '10.0'\npackages:\n\n  next@16.3.5:\n" + resolution, None),
            ("pnpm-lock.yaml", "--- # env\n" + pnpm + "packages:\n\n  next@16.3.5:\n" + resolution, None),
            ("pnpm-lock.yaml", pnpm + "packages:\n\n  next@16.3.5:\n" + resolution + "...\n", None),
            ("pnpm-lock.yaml", pnpm + "importers:\n  .: {}\n", []),
            # entries that carry their own name or version, which OSV prefers over the key: tarball, renamed, disagreeing and file: entries
            ("pnpm-lock.yaml", pnpm + "packages:\n\n  next@https://registry.npmjs.org/next/-/next-16.3.5.tgz:\n"
                               "    resolution: {tarball: https://registry.npmjs.org/next/-/next-16.3.5.tgz}\n    version: 16.3.5\n", ["16.3.5"]),
            ("pnpm-lock.yaml", pnpm + "packages:\n\n  foo@1.0.0:\n" + resolution + "    name: next\n    version: 16.3.5\n", ["16.3.5"]),
            ("pnpm-lock.yaml", pnpm + "packages:\n\n  next@16.3.6:\n" + resolution + "    version: 16.3.5\n", ["16.3.5"]),
            ("pnpm-lock.yaml", pnpm + "packages:\n\n  file:vendor/next:\n" + resolution + "    name: next\n    version: '16.3.5'\n", ["16.3.5"]),
            ("pnpm-lock.yaml", pnpm + "packages:\n\n  next@https://registry.npmjs.org/next/-/next-16.3.5.tgz:\n" + resolution,
             ["https://registry.npmjs.org/next/-/next-16.3.5.tgz"]),
            # valid YAML outside the canonical subset fails closed instead of reading as "no next": an inline record, a double-quoted or
            # quoted field key, a trailing comment on a name or version, odd indentation, tabs, a quoted or repeated `packages` key
            ("pnpm-lock.yaml", pnpm + "packages:\n\n  file:vendor/next: {name: next, version: 16.3.5}\n", None),
            ("pnpm-lock.yaml", pnpm + 'packages:\n\n  "next@16.3.5":\n' + resolution, None),
            ("pnpm-lock.yaml", pnpm + "packages:\n\n  foo@1.0.0:\n" + resolution + "    'name': next\n    version: 16.3.5\n", None),
            ("pnpm-lock.yaml", pnpm + "packages:\n\n  foo@1.0.0:\n" + resolution + "    name: next # renamed\n    version: 16.3.5\n", None),
            ("pnpm-lock.yaml", pnpm + "packages:\n\n   next@16.3.5:\n" + resolution, None),
            ("pnpm-lock.yaml", pnpm + "packages:\n\n\tnext@16.3.5:\n" + resolution, None),
            ("pnpm-lock.yaml", pnpm + "'packages':\n\n  next@16.3.5:\n" + resolution, None),
            ("pnpm-lock.yaml", pnpm + "packages: # the packages\n\n  next@16.3.5:\n" + resolution, None),
            ("pnpm-lock.yaml", pnpm + "packages:\n\n  next@16.3.5:\n" + resolution + "\npackages:\n\n  react@19.3.0:\n" + resolution, None),
            ("pnpm-lock.yaml", pnpm + "packages:\n" + resolution, None),
            ("pnpm-lock.yaml", "lockfileVersion: '10.0'\npackages:\n\n  next@16.3.5:\n" + resolution, None),
            ("pnpm-lock.yaml", "lockfileVersion: '6.0'\npackages:\n\n  /next/16.3.5:\n" + resolution, None),
            ("pnpm-lock.yaml", "packages:\n\n  next@16.3.5:\n" + resolution, None),
            # package-lock.json and npm-shrinkwrap.json: nested, aliased and path-named entries, the root project named next is not a
            # dependency, the old nested form with npm: aliases, a lock with only legacy dependencies, unknown versions and malformed files,
            # and Go-decoder differences this port does not model (repeated keys, differently cased fields) failing closed
            ("package-lock.json", json.dumps({"lockfileVersion": 3, "packages": {
                "": {"name": "app"}, "node_modules/next": {"version": "16.3.5"}, "node_modules/x/node_modules/next": {"version": "16.3.6"},
                "node_modules/next-themes": {"version": "0.4.6"}}}), ["16.3.5", "16.3.6"]),
            ("package-lock.json", json.dumps({"lockfileVersion": 3, "packages": {"node_modules/foo": {"name": "next", "version": "16.3.5"}}}), ["16.3.5"]),
            ("package-lock.json", json.dumps({"lockfileVersion": 3, "packages": {"node_modules/next": {"name": "", "version": "16.3.5"}}}), ["16.3.5"]),
            ("package-lock.json", json.dumps({"lockfileVersion": 3, "packages": {"vendor/next": {"version": "16.3.5"}}}), ["16.3.5"]),
            ("package-lock.json", json.dumps({"lockfileVersion": 3, "packages": {"node_modules/@scope/next": {"version": "16.3.5"}}}), []),
            ("package-lock.json", json.dumps({"lockfileVersion": 3, "packages": {"": {"name": "next", "version": "16.3.5"}}}), []),
            ("npm-shrinkwrap.json", json.dumps({"lockfileVersion": 1, "dependencies": {"a": {"version": "1.0.0", "dependencies": {
                "next": {"version": "16.3.5"}}}}}), ["16.3.5"]),
            ("package-lock.json", json.dumps({"lockfileVersion": 1, "dependencies": {"foo": {"version": "npm:next@16.3.5"}}}), ["16.3.5"]),
            ("package-lock.json", json.dumps({"lockfileVersion": 2, "dependencies": {"next": {"version": "16.3.5"}}}), ["16.3.5"]),
            ("package-lock.json", json.dumps({"lockfileVersion": 3, "packages": {}, "dependencies": {"next": {"version": "16.3.5"}}}), []),
            ("package-lock.json", '{"lockfileVersion":3,"packages":{"node_modules/next":{"version":"16.3.5"}},"packages":{}}', None),
            ("package-lock.json", '{"lockfileVersion":3,"Packages":{"node_modules/next":{"version":"16.3.5"}}}', None),
            ("package-lock.json", '{"lockfileVersion":1,"dependencies":{"next":{"version":"16.3.5"}},"dependencies":{}}', None),
            ("package-lock.json", '{"lockfileVersion":3,"packages":{"node_modules/next":{"Version":"16.3.5"}}}', None),
            ("package-lock.json", json.dumps({"lockfileVersion": 1, "dependencies": {"next": {"version": "file:vendor/next"}}}), None),
            ("package-lock.json", json.dumps({"lockfileVersion": 3, "packages": {"node_modules/next": {"version": "file:vendor/next"}}}), None),
            ("package-lock.json", json.dumps({"lockfileVersion": 4, "packages": {}}), None),
            ("package-lock.json", json.dumps({"lockfileVersion": 3, "packages": {"node_modules/next": {"link": True}}}), None),
            ("package-lock.json", json.dumps({"lockfileVersion": 3, "packages": ["node_modules/next"]}), None),
            ("package-lock.json", "{not json", None),
            # yarn.lock, classic and berry, with npm: aliases (also long chains) and scopes; the root workspace and __metadata are skipped
            ("yarn.lock", yarn1 + 'next@^16.3.0, next@^16.3.5:\n  version "16.3.5"\n  resolved "https://x"\n\nnext-themes@^0.4.0:\n  version "0.4.6"\n',
             ["16.3.5"]),
            ("yarn.lock", '__metadata:\n  version: 8\n\n"next@npm:^16.3.0, next@npm:16.3.6":\n  version: 16.3.6\n  resolution: "next@npm:16.3.6"\n',
             ["16.3.6"]),
            ("yarn.lock", '__metadata:\n  version: 8\n\n"foo@npm:next@^16.3.0":\n  version: 16.3.5\n  resolution: "next@npm:16.3.5"\n', ["16.3.5"]),
            ("yarn.lock", yarn1 + 'foo@npm:next@^16.3.0:\n  version "16.3.5"\n', ["16.3.5"]),
            ("yarn.lock", '__metadata:\n  version: 8\n\n"@x/foo@npm:next@^16.3.0":\n  version: 16.3.5\n', ["16.3.5"]),
            ("yarn.lock", yarn1 + '"@vercel/next@^1.0.0":\n  version "1.0.0"\n', []),
            ("yarn.lock", '__metadata:\n  version: 8\n"next@workspace:.":\n  version: 16.3.5\n', []),
            ("yarn.lock", yarn1 + "alias@npm:" * 1200 + 'next@^16.3.0:\n  version "16.3.5"\n', ["16.3.5"]),
            ("yarn.lock", yarn1 + "next@^16.3.0:\n  resolved \"https://x\"\n", None),
            ("yarn.lock", "next@^16.3.0:\n  version \"16.3.5\"\n", None),
            ("yarn.lock", '# yarn lockfile v1\n  version "1.0.0"\n', None),
            # formats no reader knows
            ("bun.lock", '{"lockfileVersion": 1, "packages": {"next": ["next@16.3.5"]}}', None),
            ("deno.lock", "{}", None),
        ]
        with tempfile.TemporaryDirectory() as scratch:
            for name, text, expected in cases:
                path = Path(scratch) / name
                path.write_bytes(text.encode("utf-8"))
                self.assertEqual(npm_next_pins(path), expected, f"{name}: {text[:140]!r}")
            self.assertIsNone(npm_next_pins(Path(scratch) / "missing" / "pnpm-lock.yaml"))
            binary = Path(scratch) / "bun.lockb"
            binary.write_bytes(b"\xff\x00bun")
            self.assertIsNone(npm_next_pins(binary))

    def test_deep_nesting_is_read_or_fails_closed_never_an_error_or_an_empty_read(self):
        deep = '{"lockfileVersion":1,"dependencies":' + '{"p":{"dependencies":' * 1200 + '{"next":{"version":"16.3.5"}}' + '}}' * 1200 + '}'
        self.assertIn(package_lock_next_pins(deep), (None, ["16.3.5"]))  # Python's JSON parser may refuse this depth; a walk must not raise
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "package-lock.json"
            path.write_text(deep, encoding="utf-8")
            self.assertIn(npm_next_pins(path), (None, ["16.3.5"]))

    def test_the_readers_run_in_linear_time_on_large_input(self):
        # A regex that backtracks over the indentation of a `next:` block took seconds on 604 bytes (review of the first repair).
        heavy = ("  foo@1.0.0:\n    resolution: {integrity: x}\n    peerDependenciesMeta:\n      next:\n" + " " * 160
                 + "optional: true\n" + " " * 160 + "injected: true\n" + " " * 160 + "other: true\n")
        big = "".join(f"  pkg{index}@1.0.{index}:\n    resolution: {{integrity: x}}\n" for index in range(20000))
        for text in ("lockfileVersion: 9.0\npackages:\n" + heavy, "lockfileVersion: 9.0\npackages:\n" + heavy * 500, "lockfileVersion: '9.0'\npackages:\n" + big):
            started = time.perf_counter()
            self.assertEqual(pnpm_next_pins(text), [])
            self.assertLess(time.perf_counter() - started, 2.0)

    def test_the_next_guard_catches_a_mutant_lock(self):
        # An extra lock in any npm format that pins an affected next fails; a fixed or older one and a non-npm file do not; the
        # allowed exemption covers only the lock and advisory it names and requires the lock to keep pinning next.
        resolution = "    resolution: {integrity: sha512-x}\n"
        header = "lockfileVersion: '9.0'\n\npackages:\n\n"
        files = {
            "a/pnpm-lock.yaml": header + "  next@16.3.5:\n" + resolution,
            "b/package-lock.json": json.dumps({"lockfileVersion": 3, "packages": {"node_modules/next": {"version": "16.3.5"}}}),
            "c/yarn.lock": '# yarn lockfile v1\n\nnext@^16.3.0:\n  version "16.3.5"\n',
            "d/bun.lockb": "binary",
            "e/pnpm-lock.yaml": header + "  next@16.3.6:\n" + resolution + "\n  'next@16.3.5':\n" + resolution,
            "f/pnpm-lock.yaml": header + "  next@16.3.6:\n" + resolution,
            "g/pnpm-lock.yaml": header + "  next@16.1.9:\n" + resolution + "  next@16.4.0-canary.1:\n" + resolution + "  next@16.3.6+build.1:\n" + resolution
                                + "  next@16.2.0-canary.1:\n" + resolution,
            "h/requirements.txt": "next==16.3.5\n",
            "j/pnpm-lock.yaml": header + "  next@https://registry.npmjs.org/next/-/next-16.3.5.tgz:\n" + resolution + "    name: next\n    version: 16.3.5\n",
            "k/yarn.lock": '__metadata:\n  version: 8\n\n"foo@npm:next@^16.3.0":\n  version: 16.3.5\n',
            "l/package-lock.json": json.dumps({"lockfileVersion": 1, "dependencies": {"foo": {"version": "npm:next@16.3.5"}}}),
            "m/pnpm-lock.yaml": header + "  file:vendor/next: {name: next, version: 16.3.5}\n",
        }
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            for rel, text in files.items():
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text(text, encoding="utf-8")
            entries = [{"path": rel} for rel in files]
            flagged = lambda allowed: sorted({path for path, _ in npm_next_findings(entries, root, allowed)})
            every = ["a/pnpm-lock.yaml", "b/package-lock.json", "c/yarn.lock", "d/bun.lockb", "e/pnpm-lock.yaml", "j/pnpm-lock.yaml", "k/yarn.lock",
                     "l/package-lock.json", "m/pnpm-lock.yaml"]
            self.assertEqual(flagged({}), every)
            allowed = {"a/pnpm-lock.yaml": {"advisories": [NEXT_ADVISORY]}}
            self.assertEqual(flagged(allowed), every[1:])
            self.assertEqual(flagged({"a/pnpm-lock.yaml": {"advisories": ["GHSA-8mgp-746c-j5xp"]}}), flagged({}))
            (root / "a/pnpm-lock.yaml").write_text("lockfileVersion: '10.0'\n", encoding="utf-8")
            self.assertIn(("a/pnpm-lock.yaml", "cannot be read strictly: extend npm_next_pins for this npm format or style"), npm_next_findings(entries, root, allowed))
            (root / "a/pnpm-lock.yaml").write_text(header + "  react@19.3.0:\n" + resolution, encoding="utf-8")
            self.assertIn(("a/pnpm-lock.yaml", "the allowed lock no longer pins next; drop its entry"), npm_next_findings(entries, root, allowed))
            # the inventory's parser name selects the reader when the file name does not
            (root / "i.lock").write_text('# yarn lockfile v1\n\nnext@^16.3.0:\n  version "16.3.5"\n', encoding="utf-8")
            self.assertEqual(npm_next_findings([{"path": "i.lock", "parser": "yarn.lock"}], root, {}),
                             [("i.lock", f"pins next 16.3.5, which the {NEXT_ADVISORY} ignore hides")])

    def test_the_next_range_has_both_bounds(self):
        scope = IGNORE_SCOPES[NEXT_ADVISORY]
        for version, expected in (("16.1.9", False), ("16.2.0-canary.1", False), ("16.2.0", True), ("16.2.1-canary.1", True), ("16.3.5", True),
                                  ("16.3.6", False), ("16.3.6+build.1", False), ("16.4.0", False), ("16.4.0-canary.1", False),
                                  ("16.3.6-canary.1", True), ("16.3.5-canary.1", True), ("16.3.x", True), ("16", True),
                                  ("https://registry.npmjs.org/next/-/next-16.3.5.tgz", True), ("", True), (None, True)):
            self.assertIs(npm_affected(version, scope["fixed"], scope["introduced"]), expected, version)

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
