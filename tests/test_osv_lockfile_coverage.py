"""Keep security-scan.yml's OSV-Scanner inventory complete (docs/decisions/2026-09-22-github-automation-closure.md).

.github/osv-scanner-lockfiles.json is the one checked-in list of files the osv-scanner job
scans. These tests fail when a tracked lockfile or manifest is missing from it (unless its
"excluded" list names it with a reason and an evidence path), when a listed file no longer exists, when a parser name is not one OSV-Scanner v2 accepts for that file,
when an ignore in .github/osv-scanner.toml lacks an id, a reason or an ignoreUntil at most 90
days away, and when a repo-wide ignore would hide a pin that IGNORE_ALLOWED_LOCKS does not allow
for that lock and advisory at the lock's reviewed sha256.
"""

from datetime import date, timedelta
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tempfile
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
# review before its new digest is recorded here.
IGNORE_SCOPES = {
    # nltk: no patched release, so every version is affected.
    "GHSA-8mgp-746c-j5xp": {"package": "nltk", "fixed": None},
    "GHSA-h35f-9h28-mq5c": {"package": "setuptools", "fixed": (83, 0, 0)},
}
IGNORE_ALLOWED_LOCKS = {
    "blueprints/us-equities/engine-trials/spy-one-zero-20260926/lumibot/lockcheck/lumibot.lock": {
        "advisories": ["GHSA-8mgp-746c-j5xp", "GHSA-h35f-9h28-mq5c"],
        "sha256": "a8dce0af2b20c6a0a8829c8fcdd9a3c3207e9e2d57a62d2498bc0116f1af0f1f",
        "evidence": "blueprints/us-equities/engine-trials/spy-one-zero-20260926/repository-checks.json",
    },
}
REQUIREMENT = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*(?:===?\s*([0-9][^\s;\\,]*))?")


def canonical(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def python_pins(path, parser=None):
    """(package, version or None) for each requirement in a requirements-style file or uv.lock; nothing for the
    npm and NuGet lock formats, which cannot pin a PyPI package."""
    if path.name == "uv.lock":
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return [(canonical(p["name"]), p.get("version")) for p in data.get("package", []) if "name" in p]
    if parser != "requirements.txt" and not path.name.endswith("requirements.txt"):
        return []
    pins = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split(" #", 1)[0].strip()
        if not line or line.startswith(("#", "-")):
            continue
        match = REQUIREMENT.match(line)
        if match:
            pins.append((canonical(match.group(1)), match.group(2)))
    return pins


def version_tuple(text):
    parts = []
    for piece in text.split("."):
        digits = re.match(r"\d+", piece)
        if not digits:
            break
        parts.append(int(digits.group()))
    return tuple(parts)


def affected_pins(entries, ignore_ids, allowed=IGNORE_ALLOWED_LOCKS):
    """(path, package, version, advisory) for each pin of a version an active repo-wide ignore would hide: nltk at any
    version (or unpinned), setuptools below 83.0.0 (unpinned resolves to a fixed release, so it is not counted). A lock
    that `allowed` names is exempt only for the advisories its entry lists."""
    found = []
    for entry in entries:
        exempt = set(allowed.get(entry["path"], {}).get("advisories", ()))
        for package, version in python_pins(ROOT / entry["path"], entry.get("parser")):
            for advisory in ignore_ids:
                scope = IGNORE_SCOPES[advisory]
                if advisory in exempt or package != scope["package"]:
                    continue
                if scope["fixed"] is None or (version is not None and version_tuple(version) < scope["fixed"]):
                    found.append((entry["path"], package, version, advisory))
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


def tracked_files():
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    listing = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"], env=environment,
        capture_output=True, check=True,
    )
    return {os.fsdecode(item) for item in listing.stdout.split(b"\0") if item}


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
                         "pin a fixed version, or review reachability and list the advisory for that lock in "
                         "IGNORE_ALLOWED_LOCKS with the lock's sha256 and the evidence path")

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
        active = {entry["id"] for entry in self.config.get("IgnoredVulns", [])}
        for path, grant in IGNORE_ALLOWED_LOCKS.items():
            advisories = set(grant["advisories"])
            self.assertTrue(advisories, f"{path}: an entry lists the advisories it may pin")
            self.assertLessEqual(advisories, set(IGNORE_SCOPES), f"{path}: every advisory needs an IGNORE_SCOPES entry")
            self.assertLessEqual(advisories, active, f"{path}: drop advisories with no active ignore in {CONFIG.name}")

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


if __name__ == "__main__":
    unittest.main()
