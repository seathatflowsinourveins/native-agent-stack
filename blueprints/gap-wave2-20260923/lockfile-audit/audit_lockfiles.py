#!/usr/bin/env python3
"""Enumerate every language-runtime dependency manifest in this repository,
check each for a hash-pinned lockfile and a Dependabot updater entry for its
package ecosystem, and print a machine-readable summary.

Closes gap ci-supply-chain[12]'s next_check: "Enumerate every runtime in the
stack manifest, check each for a hash-pinned lockfile (uv.lock/package-lock/
requirements with hashes) and an assigned updater, and record the unlocked
runtimes." manifests/stack.json's components[] are installed CLI tools, not
in-repository language runtimes with their own dependency manifests, so this
script instead walks the repository for the concrete manifest files
(requirements.txt, pyproject.toml/uv.lock, package.json/pnpm-lock.yaml,
Cargo.toml/Cargo.lock) that determine actual lock coverage, and cross-checks
.github/dependabot.yml's package-ecosystem entries.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

MANIFEST_GLOBS = {
    "pip/requirements.txt": "requirements*.txt",
    "uv (pyproject.toml)": "pyproject.toml",
    "npm/pnpm (package.json)": "package.json",
    "cargo (Cargo.toml)": "Cargo.toml",
}

LOCKFILE_NAMES = {
    "pip/requirements.txt": None,  # locking checked in-file via --hash
    "uv (pyproject.toml)": "uv.lock",
    "npm/pnpm (package.json)": ["pnpm-lock.yaml", "package-lock.json", "yarn.lock"],
    "cargo (Cargo.toml)": "Cargo.lock",
}

SKIP_DIR_PARTS = {".git", "node_modules", ".venv", "venv", "__pycache__"}

# Wave-2 gap-check synthetic fixtures (e.g. the grype known-CVE fixture's
# unhashed, unowned-by-design requirements.txt) live under this prefix. They
# are check tooling, not in-repository application/service runtime manifests,
# so they are excluded from the runtime-lockfile enumeration below. This
# script itself (audit_lockfiles.py) also lives under this prefix.
SKIP_PATH_PREFIX = ROOT / "blueprints" / "gap-wave2-20260923"


def _iter_files(glob_pattern: str):
    for path in ROOT.rglob(glob_pattern):
        if any(part in SKIP_DIR_PARTS for part in path.parts):
            continue
        try:
            path.relative_to(SKIP_PATH_PREFIX)
        except ValueError:
            pass
        else:
            continue
        yield path


def _requirements_has_hashes(path: Path) -> bool:
    return "--hash" in path.read_text(encoding="utf-8", errors="replace")


def _lockfile_present(kind: str, manifest: Path) -> tuple[bool, str | None]:
    names = LOCKFILE_NAMES[kind]
    if names is None:
        return _requirements_has_hashes(manifest), None
    if isinstance(names, str):
        names = [names]
    for name in names:
        candidate = manifest.parent / name
        if candidate.exists():
            return True, str(candidate.relative_to(ROOT))
    return False, None


def load_dependabot_ecosystems() -> list[str]:
    dependabot = ROOT / ".github/dependabot.yml"
    if not dependabot.exists():
        return []
    text = dependabot.read_text(encoding="utf-8")
    return sorted(set(re.findall(r"package-ecosystem:\s*[\"']?([a-zA-Z0-9_-]+)[\"']?", text)))


ECOSYSTEM_FOR_KIND = {
    "pip/requirements.txt": "pip",
    "uv (pyproject.toml)": "pip",  # Dependabot's ecosystem id for uv/pyproject is "pip"
    "npm/pnpm (package.json)": "npm",
    "cargo (Cargo.toml)": "cargo",
}


def main() -> int:
    dependabot_ecosystems = load_dependabot_ecosystems()
    rows = []
    seen_manifests: set[Path] = set()
    for kind, pattern in MANIFEST_GLOBS.items():
        for manifest in _iter_files(pattern):
            if manifest in seen_manifests:
                continue
            seen_manifests.add(manifest)
            locked, lockfile = _lockfile_present(kind, manifest)
            ecosystem = ECOSYSTEM_FOR_KIND[kind]
            has_updater = ecosystem in dependabot_ecosystems
            rows.append(
                {
                    "runtime_kind": kind,
                    "manifest": str(manifest.relative_to(ROOT)),
                    "hash_pinned_lockfile": locked,
                    "lockfile_path": lockfile,
                    "dependabot_ecosystem_expected": ecosystem,
                    "dependabot_ecosystem_configured": has_updater,
                    "fully_covered": locked and has_updater,
                }
            )

    summary = {
        "dependabot_configured_ecosystems": dependabot_ecosystems,
        "manifests": sorted(rows, key=lambda r: r["manifest"]),
        "unlocked_or_unowned": sorted(
            (r["manifest"] for r in rows if not r["fully_covered"]),
        ),
        "fully_covered_count": sum(1 for r in rows if r["fully_covered"]),
        "total_count": len(rows),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
