#!/usr/bin/env python3
"""Authenticated GitHub REST metadata for every repository the working files
reference, made resumable and CLI-driven.

This is a network step: it shells out to the ``gh`` CLI (which must already be
signed in) once per unique ``owner/repo`` slug. It never prints or writes a
token; ``gh`` handles its own stored auth. Nothing here is a claim about
license fitness, correctness, or adoption -- it is metadata only (stars,
pushed_at, latest release/tag, head commit, license, archived, rename).

Reads (repository-relative to --work-dir):
  foundation-layers.json  (#/layers[]/components[]/repository)
  trading-catalog.json    (#/entries[]/repository)
  star-candidates.json    (#/star_candidates[]/repository, #/beyond_stars[]/repository)

Writes --out (default <work-dir>/github-freshness.json):
  {schema, generated_at, count, errors, repositories: {repo_url: {...}}}

Resumability: a repository already present in an existing --out file is
skipped unless --refresh is given. --max-repos bounds a trial run to the
first N (sorted) slugs that still need fetching.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

GITHUB_URL_RE = re.compile(r"^https?://github\.com/([^/\s]+)/([^/\s#?]+)")

WORKING_FILE_REPO_PATHS = (
    ("foundation-layers.json", lambda doc: (
        component.get("repository")
        for layer in doc.get("layers", [])
        for component in layer.get("components", [])
    )),
    ("trading-catalog.json", lambda doc: (
        entry.get("repository") for entry in doc.get("entries", [])
    )),
    ("star-candidates.json", lambda doc: (
        entry.get("repository")
        for entry in list(doc.get("star_candidates", [])) + list(doc.get("beyond_stars", []))
    )),
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def collect_repository_urls(work_dir: Path) -> set:
    urls = set()
    for filename, extractor in WORKING_FILE_REPO_PATHS:
        path = work_dir / filename
        if not path.exists():
            continue
        doc = load_json(path)
        for url in extractor(doc):
            if url:
                urls.add(url)
    return urls


def github_slug(url: str):
    """Return 'owner/repo' for a github.com URL (release/tag/tree suffixes stripped), or None."""
    match = GITHUB_URL_RE.match(url or "")
    if not match:
        return None
    owner, repo = match.group(1), match.group(2).removesuffix(".git")
    return f"{owner}/{repo}"


def build_targets(urls) -> dict:
    """slug -> one representative original URL (first seen, sorted for determinism)."""
    targets = {}
    for url in sorted(urls):
        slug = github_slug(url)
        if slug and slug not in targets:
            targets[slug] = url
    return targets


def gh_api(path: str, timeout: int = 60):
    proc = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        return None, proc.stderr.strip()[:160]
    try:
        return json.loads(proc.stdout), None
    except Exception as exc:  # noqa: BLE001 - surfaced as a bounded error string
        return None, str(exc)


def fetch_repository(slug: str) -> dict:
    out = {"slug": slug, "observed_at": datetime.now(timezone.utc).isoformat()}
    repo, err = gh_api(f"repos/{slug}")
    if not repo:
        out["error"] = err
        return out
    for key in ("full_name", "description", "stargazers_count", "forks_count", "open_issues_count",
                "archived", "disabled", "fork", "pushed_at", "updated_at", "created_at",
                "default_branch", "language", "html_url"):
        out[key] = repo.get(key)
    out["license"] = (repo.get("license") or {}).get("spdx_id")
    out["renamed_to"] = repo["full_name"] if repo.get("full_name", "").lower() != slug.lower() else None
    release, _ = gh_api(f"repos/{slug}/releases/latest")
    if release:
        out["latest_release"] = {
            "tag": release.get("tag_name"),
            "published_at": release.get("published_at"),
            "prerelease": release.get("prerelease"),
        }
    else:
        tags, _ = gh_api(f"repos/{slug}/tags?per_page=1")
        out["latest_tag"] = tags[0]["name"] if tags else None
    commit, _ = gh_api(f"repos/{slug}/commits/{repo.get('default_branch')}")
    if commit:
        out["head"] = {
            "sha": commit.get("sha"),
            "date": ((commit.get("commit") or {}).get("committer") or {}).get("date"),
        }
    return out


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work-dir", type=Path, required=True,
                         help="Directory holding the extract_layers.py working files.")
    parser.add_argument("--out", type=Path, default=None,
                         help="Output path (default: <work-dir>/github-freshness.json).")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--max-repos", type=int, default=None,
                         help="Bound a trial run to the first N repositories still needing a fetch.")
    parser.add_argument("--refresh", action="store_true",
                         help="Re-fetch repositories already present in --out instead of skipping them.")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    out_path = args.out or (args.work_dir / "github-freshness.json")

    urls = collect_repository_urls(args.work_dir)
    targets = build_targets(urls)
    non_github = sorted(u for u in urls if u and not github_slug(u))

    existing = {"repositories": {}}
    if out_path.exists() and not args.refresh:
        existing = load_json(out_path)

    results = dict(existing.get("repositories", {}))
    already_covered_slugs = {rec.get("slug") for rec in results.values() if isinstance(rec, dict)}
    pending = {slug: url for slug, url in sorted(targets.items())
               if args.refresh or slug not in already_covered_slugs}
    if args.max_repos is not None:
        pending = dict(list(pending.items())[: args.max_repos])

    print(f"github repositories {len(targets)} non-github {len(non_github)} "
          f"already-covered {len(targets) - len(pending)} to-fetch {len(pending)}", flush=True)

    if pending:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            for i, record in enumerate(pool.map(fetch_repository, sorted(pending)), 1):
                results[pending[record["slug"]]] = record
                if i % 50 == 0:
                    print(f"fetched {i}", flush=True)

    document = {
        "schema": "github-freshness/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(results),
        "errors": sum(1 for rec in results.values() if isinstance(rec, dict) and rec.get("error")),
        "repositories": results,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    print(f"done {len(results)} errors {document['errors']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
