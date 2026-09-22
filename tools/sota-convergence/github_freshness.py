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
  {schema, generated_at, count, errors, partial_errors, fetched_this_run,
   retained_from_prior_runs, observation_window: {min, max},
   repositories: {repo_url: {..., observed_at, slug, aliases, partial_errors?}}}

Resumability: a repository already present in an existing --out file is
skipped unless --refresh is given, *unless* its record carries a
"partial_errors" entry (a sub-request -- releases/tags/commit -- that failed
with something other than an ordinary "not found"); such a record is left
pending so the next run retries exactly the missing metadata. --max-repos
bounds a trial run to the first N (sorted) slugs that still need fetching.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import defaultdict
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
    """Return normalized, lower-cased 'owner/repo' for a github.com URL
    (release/tag/tree suffixes and a trailing slash are already excluded by
    the capturing pattern, which stops at the next '/', '#' or '?'), or
    None. Lower-casing means a canonical URL and a differently-cased alias
    resolve to the same slug."""
    match = GITHUB_URL_RE.match(url or "")
    if not match:
        return None
    owner, repo = match.group(1), match.group(2).removesuffix(".git")
    return f"{owner}/{repo}".lower()


def build_targets(urls) -> dict:
    """slug -> one representative original URL (first seen, sorted for determinism)."""
    targets = {}
    for url in sorted(urls):
        slug = github_slug(url)
        if slug and slug not in targets:
            targets[slug] = url
    return targets


def build_slug_aliases(urls) -> dict:
    """slug -> sorted list of every distinct URL alias seen for that slug
    (e.g. a canonical https://github.com/owner/repo URL and a
    .../releases/tag/v1 or .../tree/main alias for the same repository).
    Every alias this run saw is recorded on the freshness record so a
    catalog card referencing any alias form still resolves
    (build_manifest.py looks records up by normalized slug -- see its
    ``github_repo_slug`` / ``compute_upstream``)."""
    aliases = defaultdict(set)
    for url in urls:
        slug = github_slug(url)
        if slug:
            aliases[slug].add(url)
    return {slug: sorted(urlset) for slug, urlset in aliases.items()}


def gh_api(path: str, timeout: int = 60):
    """Run one ``gh api <path>`` call. Never raises: a timeout, a missing
    ``gh`` binary or any other subprocess failure is caught here and returned
    as ``(None, str(exc))``, the same shape as a non-zero exit or unparsable
    stdout, so one bad repository never aborts the whole fetch."""
    try:
        proc = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - surfaced as a bounded error string, never re-raised
        return None, str(exc)
    if proc.returncode != 0:
        return None, proc.stderr.strip()[:160]
    try:
        return json.loads(proc.stdout), None
    except Exception as exc:  # noqa: BLE001 - surfaced as a bounded error string
        return None, str(exc)


def is_expected_missing(err) -> bool:
    """True when a gh api sub-request failure (releases/tags/commit -- never
    the primary ``repos/{slug}`` call, which is always a real fetch
    failure) looks like an ordinary "not found" -- e.g. GitHub's REST API
    returns 404 for ``releases/latest`` on a repository with no releases at
    all, which is an expected outcome, not a fetch failure. A timeout, a 429
    rate limit, or a 5xx server error is a real, transient, retryable
    failure and must not be swallowed here."""
    if not err:
        return False
    lowered = str(err).lower()
    if "429" in lowered or "rate limit" in lowered:
        return False
    if re.search(r"\b5\d\d\b", lowered):
        return False
    return "404" in lowered or "not found" in lowered


def fetch_repository(slug: str) -> dict:
    out = {"slug": slug, "observed_at": datetime.now(timezone.utc).isoformat()}
    partial_errors = {}
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

    release, release_err = gh_api(f"repos/{slug}/releases/latest")
    if release:
        out["latest_release"] = {
            "tag": release.get("tag_name"),
            "published_at": release.get("published_at"),
            "prerelease": release.get("prerelease"),
        }
    else:
        if release_err and not is_expected_missing(release_err):
            partial_errors["releases"] = release_err
        tags, tags_err = gh_api(f"repos/{slug}/tags?per_page=1")
        if tags_err is None:
            out["latest_tag"] = tags[0]["name"] if tags else None
        elif not is_expected_missing(tags_err):
            partial_errors["tags"] = tags_err

    commit, commit_err = gh_api(f"repos/{slug}/commits/{repo.get('default_branch')}")
    if commit:
        out["head"] = {
            "sha": commit.get("sha"),
            "date": ((commit.get("commit") or {}).get("committer") or {}).get("date"),
        }
    elif commit_err and not is_expected_missing(commit_err):
        partial_errors["commit"] = commit_err

    if partial_errors:
        # Kept on the record (not discarded) and counted at the top level,
        # and treated as retryable on resume (see main()'s
        # already_covered_slugs) -- a record with fewer than all three
        # sub-fields populated is not silently treated as "done".
        out["partial_errors"] = partial_errors
    return out


def build_document(results: dict, slug_aliases: dict | None = None, fetched_this_run: int = 0) -> dict:
    if slug_aliases:
        for record in results.values():
            if not isinstance(record, dict):
                continue
            aliases = slug_aliases.get(record.get("slug"))
            if aliases:
                record["aliases"] = sorted(aliases)
    observed_dates = sorted(
        rec.get("observed_at") for rec in results.values()
        if isinstance(rec, dict) and rec.get("observed_at")
    )
    retained = max(len(results) - fetched_this_run, 0)
    return {
        "schema": "github-freshness/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(results),
        "errors": sum(1 for rec in results.values() if isinstance(rec, dict) and rec.get("error")),
        "partial_errors": sum(1 for rec in results.values() if isinstance(rec, dict) and rec.get("partial_errors")),
        "fetched_this_run": fetched_this_run,
        "retained_from_prior_runs": retained,
        # Actual observation dates, not this write's checkpoint/generation
        # time (see build_manifest.py's format_observation_window, which
        # cites this window rather than generated_at in the published
        # manifest's method.freshness text).
        "observation_window": ({"min": observed_dates[0], "max": observed_dates[-1]}
                                if observed_dates else None),
        "repositories": results,
    }


def write_document(out_path: Path, results: dict, slug_aliases: dict | None = None,
                    fetched_this_run: int = 0) -> dict:
    document = build_document(results, slug_aliases=slug_aliases, fetched_this_run=fetched_this_run)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    return document


# Write a checkpoint to --out after this many freshly-fetched repositories,
# so a long run that is interrupted (killed, out of budget, or an
# unanticipated exception past gh_api's own try/except) still leaves the
# repositories fetched so far on disk for the next resumed run to pick up.
CHECKPOINT_INTERVAL = 25


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
    slug_aliases = build_slug_aliases(urls)
    non_github = sorted(u for u in urls if u and not github_slug(u))

    existing = {"repositories": {}}
    if out_path.exists() and not args.refresh:
        existing = load_json(out_path)

    results = dict(existing.get("repositories", {}))
    # A record carrying "error" (a prior gh timeout/failure on the primary
    # repos/{slug} call) or "partial_errors" (a releases/tags/commit
    # sub-request that failed with something other than an ordinary "not
    # found") is not covered: it stays pending so a resumed run retries
    # exactly the repositories that previously failed or are incomplete,
    # instead of only genuinely-fetched ones.
    already_covered_slugs = {rec.get("slug") for rec in results.values()
                              if isinstance(rec, dict) and not rec.get("error")
                              and not rec.get("partial_errors")}
    pending = {slug: url for slug, url in sorted(targets.items())
               if args.refresh or slug not in already_covered_slugs}
    if args.max_repos is not None:
        pending = dict(list(pending.items())[: args.max_repos])

    print(f"github repositories {len(targets)} non-github {len(non_github)} "
          f"already-covered {len(targets) - len(pending)} to-fetch {len(pending)}", flush=True)

    fetched_count = 0
    if pending:
        try:
            with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
                for i, record in enumerate(pool.map(fetch_repository, sorted(pending)), 1):
                    results[pending[record["slug"]]] = record
                    fetched_count = i
                    if i % 50 == 0:
                        print(f"fetched {i}", flush=True)
                    if i % CHECKPOINT_INTERVAL == 0:
                        write_document(out_path, results, slug_aliases=slug_aliases, fetched_this_run=fetched_count)
                        print(f"checkpoint {i} written to {out_path}", flush=True)
        finally:
            # Always leave whatever was fetched so far on disk, even on an
            # unanticipated exception (gh_api itself never raises, but this
            # is the resumability backstop the checkpoint above is not
            # guaranteed to have reached).
            document = write_document(out_path, results, slug_aliases=slug_aliases, fetched_this_run=fetched_count)
    else:
        document = write_document(out_path, results, slug_aliases=slug_aliases, fetched_this_run=0)

    print(f"done {len(results)} errors {document['errors']} partial_errors {document['partial_errors']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
