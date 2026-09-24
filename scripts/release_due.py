#!/usr/bin/env python3
"""Report new-machine files that main documents but the pinned release lacks or ships differently.

A new machine checks out adoption/manifest.json source.release_tag (step 0), then follows the
documents in that checkout. Main may already describe steps that are not released. This report
lists, against source.release_commit:
  due      repository paths referenced by main's new-machine documents that are absent at the release;
  changed  new-machine files present at both whose content differs: the new-host documents, the
           platform pages, README.md's Start here section (reported as README.md#start-here) and every
           path those documents reference. A pinned host runs the release's copy of each, so a
           changed script, pin file or step is not on a new machine until a release carries it.
adoption/manifest.json (the pin itself) and manifests/evidence.json (the hash index) always differ
after a re-pin and are not compared. Either list non-empty means a release (and a re-pin) is due.

Modes:
  (default)                       report only, exit 0
  --strict                        exit 1 if anything is due or changed (use before cutting/re-pinning
                                  a release)
  --strict-if-repinned BASE_REF   exit 1 if anything is due or changed AND this tree's
                                  source.release_commit differs from BASE_REF's (a re-pin PR must pin
                                  a release that has what main documents); report only otherwise

tests/test_release_pin_contents.py separately requires the pinned release to be self-consistent
(its own documents only reference paths it contains).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])((?:\.github|scripts|tools|tests|adoption|docs|recipes|catalogs)/[A-Za-z0-9_./-]+"
    r"\.(?:py|sh|md|json|toml|ya?ml|plist|template|txt))\b")
# Documents a new machine follows after step 0.
NEW_HOST_DOCS = ("adoption/bootstrap.md", "adoption/README.md", "docs/next-host-stages.md",
                 "docs/contributing-evidence.md", "docs/new-host-grand-list.md")
# The pin record and the hash index: a re-pin PR changes both, so they never match the release.
DRIFT_EXEMPT = frozenset({"adoption/manifest.json", "manifests/evidence.json"})
START_HERE = "README.md#start-here"


def git(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=check)


def start_here_section(text: str) -> str:
    match = re.search(r"^## Start here\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return match.group(1) if match else ""


def doc_texts(read) -> list[str]:
    """read(rel) -> text or None. Returns README's Start here section plus every new-host doc."""
    texts = []
    readme = read("README.md")
    if readme:
        texts.append(start_here_section(readme))
    for rel in NEW_HOST_DOCS:
        text = read(rel)
        if text:
            texts.append(text)
    return texts


def platform_docs(list_dir) -> list[str]:
    return sorted(p for p in list_dir("adoption/platforms") if p.endswith(".md"))


def referenced(texts: list[str]) -> set[str]:
    return {m for text in texts for m in PATH_RE.findall(text)}


def ignored(rel: str) -> bool:
    return git("check-ignore", "-q", rel).returncode == 0  # host-local files (adoption/hosts/*.json)


def at_commit(commit: str, rel: str) -> bool:
    return git("cat-file", "-e", f"{commit}:{rel}").returncode == 0


def worktree_paths() -> set[str]:
    def read(rel):
        p = ROOT / rel
        return p.read_text(encoding="utf-8") if p.exists() else None
    texts = doc_texts(read) + [read(p) for p in platform_docs(
        lambda d: [f"{d}/{x.name}" for x in (ROOT / d).glob("*")] if (ROOT / d).is_dir() else [])]
    return referenced([t for t in texts if t])


def commit_paths(commit: str) -> set[str]:
    def read(rel):
        r = git("show", f"{commit}:{rel}")
        return r.stdout if r.returncode == 0 else None
    def list_dir(d):
        r = git("ls-tree", "--name-only", f"{commit}:{d}")
        return [f"{d}/{x}" for x in r.stdout.split()] if r.returncode == 0 else []
    texts = doc_texts(read) + [read(p) for p in platform_docs(list_dir)]
    return referenced([t for t in texts if t])


def pin(manifest_text: str) -> tuple[str, str]:
    source = json.loads(manifest_text)["source"]
    return source["release_tag"], source["release_commit"]


def due(commit: str) -> list[str]:
    """Paths main's new-machine documents reference that exist on main but not at the release."""
    return sorted(rel for rel in worktree_paths()
                  if (ROOT / rel).exists() and not ignored(rel) and not at_commit(commit, rel))


def worktree_blobs(rels: list[str]) -> dict[str, str]:
    """Blob ids git would store for these working-tree files (same filters as git add)."""
    if not rels:
        return {}
    out = subprocess.run(["git", "-C", str(ROOT), "hash-object", "--stdin-paths"], input="\n".join(rels) + "\n",
                         capture_output=True, text=True, check=True).stdout.split()
    return dict(zip(rels, out))


def commit_blobs(commit: str, rels: list[str]) -> dict[str, str]:
    if not rels:
        return {}
    out = git("ls-tree", "-r", "-z", "--full-tree", commit, "--", *rels, check=True).stdout
    blobs = {}
    for entry in filter(None, out.split("\0")):
        meta, _, rel = entry.partition("\t")
        mode, kind, blob = meta.split()
        if kind == "blob":
            blobs[rel] = blob
    return blobs


def changed(commit: str) -> list[str]:
    """New-machine files present on main and at the release whose content differs."""
    worktree_docs = [*NEW_HOST_DOCS, *platform_docs(
        lambda d: [f"{d}/{x.name}" for x in (ROOT / d).glob("*")] if (ROOT / d).is_dir() else [])]
    candidates = sorted(rel for rel in (worktree_paths() | set(worktree_docs)) - DRIFT_EXEMPT
                        if (ROOT / rel).is_file() and not ignored(rel))
    released = commit_blobs(commit, candidates)
    current = worktree_blobs([rel for rel in candidates if rel in released])
    drift = [rel for rel, blob in current.items() if blob != released[rel]]
    readme = ROOT / "README.md"
    old_readme = git("show", f"{commit}:README.md")
    if readme.is_file() and old_readme.returncode == 0 and (
            start_here_section(readme.read_text(encoding="utf-8")) != start_here_section(old_readme.stdout)):
        drift.append(START_HERE)
    return sorted(drift)


def repinned(base_ref: str) -> bool:
    base = git("show", f"{base_ref}:adoption/manifest.json")
    if base.returncode != 0:
        return True  # no comparable base: treat as a re-pin and be strict
    return pin(base.stdout)[1] != pin((ROOT / "adoption/manifest.json").read_text(encoding="utf-8"))[1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--strict", action="store_true")
    mode.add_argument("--strict-if-repinned", metavar="BASE_REF")
    args = ap.parse_args(argv)
    if shutil.which("git") is None:
        print(json.dumps({"status": "error", "error": "git is not on PATH; install git and rerun"}))
        return 2
    tag, commit = pin((ROOT / "adoption/manifest.json").read_text(encoding="utf-8"))
    if git("cat-file", "-e", f"{commit}^{{commit}}").returncode:
        print(json.dumps({"status": "error", "error": f"release commit {commit} ({tag}) not in this clone"}))
        return 2
    missing = due(commit)
    drift = changed(commit)
    strict = args.strict or (args.strict_if_repinned is not None and repinned(args.strict_if_repinned))
    report = {"release_tag": tag, "release_commit": commit, "due": missing, "changed": drift, "strict": strict,
              "status": "release_due" if missing else "content_changed" if drift else "current"}
    print(json.dumps(report, indent=1))
    if missing:
        print(f"\n{len(missing)} path(s) documented on main are not in {tag}.", file=sys.stderr)
    if drift:
        print(f"\n{len(drift)} new-machine file(s) differ between main and {tag}; a pinned host runs the "
              f"{tag} copies.", file=sys.stderr)
    if missing or drift:
        print("Cut a new release and re-pin adoption/manifest.json source.release_tag/release_commit.",
              file=sys.stderr)
    return 1 if (strict and (missing or drift)) else 0


if __name__ == "__main__":
    sys.exit(main())
