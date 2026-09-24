#!/usr/bin/env python3
"""Report new-machine files that main documents but the pinned release lacks or ships differently.

A new machine checks out adoption/manifest.json source.release_tag (step 0), then follows the
documents in that checkout. Main may already describe steps that are not released. This report
lists, against source.release_commit:
  due      new-machine files on main that are absent at the release: the new-host documents, the
           platform pages, and every repository path they (or README.md's Start here section)
           reference, by extension-matched path, relative Markdown link or bare path;
  changed  those files present in main's HEAD tree and at the release whose mode, object kind or
           content differs, adoption/manifest.json compared without source.release_tag,
           source.release_commit and updated_at (a re-pin rewrites them), and README.md's Start
           here section (reported as README.md#start-here). A pinned host runs the release's copy of
           each, so a changed script, pin file, profile or step is not on a new machine until a
           release carries it.
manifests/evidence.json (the hash index) always differs after a re-pin and is not compared.
Either list non-empty means a release (and a re-pin) is due.

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
import posixpath
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
# The hash index changes with every registered file (a re-pin PR re-registers the manifest), so it
# never matches the release; adoption/manifest.json is compared without PIN_FIELDS and updated_at.
DRIFT_EXEMPT = frozenset({"manifests/evidence.json"})
PIN_FIELDS = ("release_tag", "release_commit")
START_HERE = "README.md#start-here"
LINK_RE = re.compile(r"\[(?:[^\]\\]|\\.)*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
BARE_PATH_RE = re.compile(r"(?<![A-Za-z0-9_./-])((?:\.github|scripts|tools|tests|adoption|docs|recipes|catalogs)/[A-Za-z0-9_./-]+)")
# Referenced install guides (Markdown under these prefixes) are followed through nested guides.
GUIDE_PREFIXES = ("adoption/", "recipes/")


def git(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    # UTF-8 whatever the locale: README's Start here section is compared with its release copy.
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8",
                          check=check)


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


def new_host_docs() -> list[str]:
    """The new-host documents and platform pages as they exist on main."""
    pages = platform_docs(lambda d: [f"{d}/{x.name}" for x in (ROOT / d).glob("*")] if (ROOT / d).is_dir() else [])
    return [rel for rel in (*NEW_HOST_DOCS, *pages) if (ROOT / rel).is_file()]


def repo_file(rel: str) -> str | None:
    """rel normalized, if it names a regular file (or a symlink) inside the repository."""
    rel = posixpath.normpath(rel)
    if rel.startswith(("../", "/")) or rel in (".", ".."):
        return None
    path = ROOT / rel
    return rel if (path.is_file() or path.is_symlink()) and not path.is_dir() else None


def linked_or_bare(doc: str, text: str) -> set[str]:
    """Files a document names without a matching PATH_RE extension: relative Markdown link
    targets (resolved against the document's directory) and bare repository paths such as
    adoption/tools/ecosystem-bounded-run or adoption/hooks/claude/SHA256SUMS."""
    base = posixpath.dirname(doc)
    found = set()
    for target in LINK_RE.findall(text):
        target = target.split("#", 1)[0].split("?", 1)[0]
        if target and not re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
            rel = repo_file(posixpath.join(base, target) if not target.startswith("/") else target.lstrip("/"))
            if rel:
                found.add(rel)
    for token in BARE_PATH_RE.findall(text):
        rel = repo_file(token.rstrip("./,"))
        if rel:
            found.add(rel)
    return found


def mentioned(doc: str, text: str) -> set[str]:
    return {rel for rel in referenced([text]) if repo_file(rel)} | linked_or_bare(doc, text)


def new_machine_files() -> set[str]:
    """Every file a new machine follows or runs: the new-host documents and platform pages, every
    file they (or README's Start here section) reference, and every file referenced by a referenced
    install guide (a Markdown file under adoption/ or recipes/, e.g. adoption/tools/README.md, which
    installs the guarded runners), followed through nested guides, on main, not git-ignored."""
    texts = {doc: (ROOT / doc).read_text(encoding="utf-8") for doc in new_host_docs()}
    readme = ROOT / "README.md"
    if readme.is_file():
        texts["README.md"] = start_here_section(readme.read_text(encoding="utf-8"))
    files = set(texts) - {"README.md"}
    for doc, text in texts.items():
        files |= mentioned(doc, text)
    visited = set(texts)
    while True:  # follow install guides to closure; the visited set bounds a cycle of links
        guides = sorted(rel for rel in files - visited
                        if rel.endswith(".md") and rel.startswith(GUIDE_PREFIXES) and (ROOT / rel).is_file())
        if not guides:
            break
        for guide in guides:
            visited.add(guide)
            files |= mentioned(guide, (ROOT / guide).read_text(encoding="utf-8"))
    return {rel for rel in files if not ignored(rel)}


def due(commit: str) -> list[str]:
    """Paths main's new-machine documents reference, and the documents themselves, that exist on
    main but not at the release."""
    paths = {rel for rel in worktree_paths() if (ROOT / rel).exists()} | new_machine_files()
    return sorted(rel for rel in paths if not ignored(rel) and not at_commit(commit, rel))


def tree_entries(ref: str, rels: list[str]) -> dict[str, tuple[str, str, str]]:
    """(mode, object kind, object id) per path at ref: an executable bit, a symlink or a
    submodule differs even when the bytes do not."""
    if not rels:
        return {}
    out = git("ls-tree", "-r", "-z", "--full-tree", ref, "--", *rels, check=True).stdout
    entries = {}
    for entry in filter(None, out.split("\0")):
        meta, _, rel = entry.partition("\t")
        mode, kind, oid = meta.split()
        entries[rel] = (mode, kind, oid)
    return entries


def comparable_manifest(text: str) -> str:
    """adoption/manifest.json without the fields a re-pin rewrites."""
    data = json.loads(text)
    data.pop("updated_at", None)
    for field in PIN_FIELDS:
        data.get("source", {}).pop(field, None)
    return json.dumps(data, sort_keys=True)


def changed(commit: str) -> list[str]:
    """New-machine files present in main's HEAD tree and at the release whose mode, kind or content
    differs, adoption/manifest.json apart from its pin fields, and README's Start here section."""
    candidates = sorted(new_machine_files() - DRIFT_EXEMPT - {"adoption/manifest.json"})
    head, released = tree_entries("HEAD", candidates), tree_entries(commit, candidates)
    drift = [rel for rel in candidates if rel in head and rel in released and head[rel] != released[rel]]
    manifest_now, manifest_then = git("show", "HEAD:adoption/manifest.json"), git("show", f"{commit}:adoption/manifest.json")
    if manifest_now.returncode == 0 and manifest_then.returncode == 0 and (
            comparable_manifest(manifest_now.stdout) != comparable_manifest(manifest_then.stdout)):
        drift.append("adoption/manifest.json")
    readme_now, readme_then = git("show", "HEAD:README.md"), git("show", f"{commit}:README.md")
    if readme_now.returncode == 0 and readme_then.returncode == 0 and (
            start_here_section(readme_now.stdout) != start_here_section(readme_then.stdout)):
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
