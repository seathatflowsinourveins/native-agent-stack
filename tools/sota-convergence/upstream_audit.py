#!/usr/bin/env python3
"""Upstream quality audit of the GitHub repositories that the definitive manifest's foundation rows name.

Targets come from ``evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json``, the install
record; only rows whose ``catalog`` is ``foundation`` count, so the trading rows stay out. A row names a repository
through a GitHub URL in its structured fields: its own ``repository``, its resolution's ``former_default.repository``
and each ``arms[].repository`` (a field can join several URLs with " ; "). A split or measurement row can also name a
finalist as owner/name text in its ``default`` or in its former default's or arms' ``name``. A repository's role in a
row is the row's ``slot_id``, its ``state`` (``pinned`` when the state is empty), whether the row installs it and where
the row names it. A row installs only its own ``repository``, and only when its default is not
``installs_nothing_extra`` (the rule of ``scripts/build_new_wsl_handbook.py``). URLs outside GitHub, and split or
measurement rows that name no finalist repository, are listed as not audited.

For each target this records maintenance, release currency, release provenance (each queried asset's name, digest and
GitHub attestation count), published security advisories, the check runs on the default-branch head, the license and
the OpenSSF Scorecard that deps.dev publishes where one exists, together with every request it made and that
request's outcome. It is information only: it never selects, ranks or changes a default, a state or a slot.

Sources (search-first, 2026-10-02): GitHub REST through the GitHub CLI (``gh api``, following
``tools/sota-convergence/github_freshness.py``; ``gh api --paginate --slurp`` reads every page of a collection), and
the deps.dev v3 GetProject endpoint (https://docs.deps.dev/api/v3/#getproject) for the license and the Scorecard of
the OpenSSF weekly scan. A repository outside that scan has no published Scorecard and is recorded as not covered.

Flags (thresholds frozen here; a flag is an observed fact, never a verdict):
- ``fetch_error``: the repository could not be read.
- ``archived``: the repository is archived.
- ``stale``: no default-branch commit after ``observed_at`` minus ``STALE_AFTER_DAYS`` (90, ossf/scorecard's
  Maintained window, compared as ``tools/sota-convergence/practice_references.py`` compares it).
- ``no_release``: ``releases/latest`` answers 404.
- ``old_release``: the latest release was published no later than ``observed_at`` minus 365 days.
- ``no_provenance``: the latest release has digest-carrying assets, every attestation request answered, and none of
  the queried assets has a GitHub attestation. One erroring request without an attested asset makes provenance
  unknown instead (a project that signs another way, such as a Sigstore bundle beside its checksums, still shows the
  flag).
- ``advisories``: at least one published security advisory was read. Whether one affects a pinned or the latest
  release is not evaluated.
- ``ci_failing``: at least one check run on the default-branch head concluded failure, timed_out or startup_failure.
- ``low_scorecard``: a published Scorecard overall score below 5.0.
A collection that errored or stopped short is listed in the row's ``incomplete`` and never reports a negative fact:
an incomplete check-run collection without a failure reports ``failing: null``, not 0, and an incomplete advisory
collection without an advisory reports ``count: null``. A check-run collection is complete only when every run it
lists was read and the head carries at most ``CHECK_SUITE_LIMIT`` (1000) check suites: above that, GitHub's check-runs
endpoint reads only the 1000 most recent suites and its ``total_count`` describes that truncated set. The suite count
is read after the runs, so a suite added meanwhile is counted. Every age is measured from the observation's own
``observed_at``, so a rebuild is deterministic.

Modes: ``--collect`` (network) writes the sanitized observations with the manifest's sha256 and the role table;
``--build`` (offline) writes the audit from the observations alone; ``--check`` (default, offline) fails when the
audit differs from its rebuild, or when the manifest's sha256 or the role table it yields differs from the one
recorded at collection, and then prints the role drift: repositories added, removed or with changed roles.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
for _path in (str(REPO_ROOT), str(HERE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from github_freshness import github_slug  # noqa: E402
from practice_references import STALE_AFTER_DAYS, gh_http_status  # noqa: E402
from scripts import host_receipts  # noqa: E402
from scripts.validate import PRIVATE_CONTENT  # noqa: E402

ROOT = REPO_ROOT
MANIFEST = "evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json"
OBSERVATIONS = "evidence/artifacts/upstream-audit-20261002/observations.json"
OUT = "catalogs/foundation/upstream-audit-20261002.json"
OLD_RELEASE_DAYS = 365
LOW_SCORECARD = 5.0
FAILING = ("failure", "timed_out", "startup_failure")
FLAGS = ("fetch_error", "archived", "stale", "no_release", "old_release", "no_provenance", "advisories",
         "ci_failing", "low_scorecard")
COLLECTIONS = ("head", "release", "attestations", "advisories", "check_runs", "deps_dev")
STATES = ("definitive", "resolved", "split", "measurement", "pinned")
NAMED_AS = ("repository", "former_default", "arm", "text")
PROVENANCE = ("attested", "none", "unknown", "no_digest", "no_assets")
DEPS_DEV = "https://api.deps.dev/v3/projects/"
GITHUB_REST_DOCS = "https://docs.github.com/en/rest"
CHECK_RUNS_DOCS = "https://docs.github.com/en/rest/checks/runs#list-check-runs-for-a-git-reference"
CHECK_SUITES_DOCS = "https://docs.github.com/en/rest/checks/suites#list-check-suites-for-a-git-reference"
DEPS_DEV_DOCS = "https://docs.deps.dev/api/v3/#getproject"
MAX_ATTESTED_ASSETS = 5
CHECK_SUITE_LIMIT = 1000  # above it, commits/{ref}/check-runs reads only the 1000 most recent check suites
PER_PAGE = 100
RETRIES = 3
BACKOFF_SECONDS = 30
REQUESTS_PER_REPOSITORY = 20  # rate-limit budget per target the collector requires before it starts
SOURCES = {
    "github_rest": {
        "client": "gh api; a collection marked paginate is read with gh api --paginate --slurp",
        "docs": GITHUB_REST_DOCS,
        "request_templates": [
            "repos/{owner}/{repo}",
            "repos/{owner}/{repo}/commits/{default_branch}",
            "repos/{owner}/{repo}/releases/latest",
            f"repos/{{owner}}/{{repo}}/attestations/{{digest}} (the first {MAX_ATTESTED_ASSETS} digest-carrying "
            "assets of the latest release)",
            f"repos/{{owner}}/{{repo}}/security-advisories?state=published&per_page={PER_PAGE} (paginate)",
            f"repos/{{owner}}/{{repo}}/commits/{{head_sha}}/check-runs?per_page={PER_PAGE} (paginate)",
            "repos/{owner}/{repo}/commits/{head_sha}/check-suites?per_page=1 (its total_count, read after the "
            "check runs)",
        ],
        "check_suite_limit": (f"above {CHECK_SUITE_LIMIT} check suites on a ref, the check-runs endpoint reads only "
                              f"the {CHECK_SUITE_LIMIT} most recent ({CHECK_RUNS_DOCS}), so a head above it is "
                              f"recorded incomplete; the suite count comes from {CHECK_SUITES_DOCS}"),
    },
    "deps_dev": {"url_template": DEPS_DEV + "github.com%2F{owner}%2F{repo}", "docs": DEPS_DEV_DOCS},
    "exact_requests": "each repository's observation lists every request it made, in order, with its outcome",
}

URL_RE = re.compile(r"https?://[^\s;,()<>\"']+")
# owner/name as GitHub allows it (an owner of up to 39 letters, digits or inner hyphens), standing alone in text.
OWNER_NAME_RE = re.compile(r"(?<![\w.:/@-])([A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}/[A-Za-z0-9_.-]+)"
                           r"(?![\w/-])")


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def sha256(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# --- targets and roles -------------------------------------------------------------------------------------------


def _urls(value) -> list[str]:
    return [url.rstrip(".") for url in URL_RE.findall(value if isinstance(value, str) else "")]


def owner_names(text) -> list[str]:
    """Lower-cased owner/name keys written as text (URLs removed first), in order of appearance."""
    if not isinstance(text, str):
        return []
    found = []
    for match in OWNER_NAME_RE.finditer(URL_RE.sub(" ", text)):
        owner, name = match.group(1).rstrip(".").split("/", 1)
        if name and re.search(r"[A-Za-z]", owner) and re.search(r"[A-Za-z]", name):
            found.append(f"{owner}/{name.removesuffix('.git')}".lower())
    return found


def targets(manifest: dict) -> tuple[dict, list]:
    """Pure: (GitHub repository key -> roles, not-audited entries) from the manifest's foundation rows."""
    found: dict[str, dict] = {}
    not_audited: list[dict] = []
    for slot in manifest.get("slots") or []:
        if slot.get("catalog") != "foundation":
            continue
        slot_id = slot.get("slot_id")
        state = slot.get("state") or "pinned"
        installs = bool(slot.get("default")) and not slot.get("installs_nothing_extra")
        resolution = slot.get("resolution") if isinstance(slot.get("resolution"), dict) else {}
        former = resolution.get("former_default") if isinstance(resolution.get("former_default"), dict) else {}
        arms = [arm for arm in resolution.get("arms") or [] if isinstance(arm, dict)]
        named: list[tuple[str, str]] = []

        def from_field(value, named_as) -> int:
            urls = _urls(value)
            for url in urls:
                key = github_slug(url)
                if key:
                    named.append((key, named_as))
                else:
                    not_audited.append({"slot_id": slot_id, "state": state, "named_as": named_as,
                                        "reason": "not_github", "url": url})
            return len(urls)

        own = from_field(slot.get("repository"), "repository")
        finalists = from_field(former.get("repository"), "former_default")
        for arm in arms:
            finalists += from_field(arm.get("repository"), "arm")
        if state in ("split", "measurement"):
            for text in [slot.get("default"), former.get("name")] + [arm.get("name") for arm in arms]:
                keys = owner_names(text)
                finalists += len(keys)
                named.extend((key, "text") for key in keys)
            if not own and not finalists:
                not_audited.append({"slot_id": slot_id, "state": state, "named_as": None,
                                    "reason": "finalists_without_repository", "url": None})
        for key, named_as in named:
            role = found.setdefault(key, {}).setdefault(slot_id, {"slot_id": slot_id, "state": state,
                                                                  "installs": False, "named_as": []})
            if named_as not in role["named_as"]:
                role["named_as"].append(named_as)
            if named_as == "repository" and installs:
                role["installs"] = True
    roles = {}
    for key in sorted(found):
        roles[key] = []
        for slot_id in sorted(found[key]):
            role = found[key][slot_id]
            role["named_as"] = [n for n in NAMED_AS if n in role["named_as"]]
            roles[key].append(role)
    not_audited.sort(key=lambda e: (e["slot_id"] or "", e["reason"], e["named_as"] or "", e["url"] or ""))
    return roles, not_audited


def drift(recorded: dict, current: dict) -> dict:
    """Pure: repositories added to or removed from the role table, and those whose roles changed."""
    added = sorted(k for k in current if k not in recorded)
    removed = sorted(k for k in recorded if k not in current)
    changed = [{"repository": k, "recorded": recorded[k], "current": current[k]}
               for k in sorted(current) if k in recorded and recorded[k] != current[k]]
    return {"added": added, "removed": removed, "changed": changed}


# --- network collection ------------------------------------------------------------------------------------------


def outcome(error) -> str:
    """A bounded, value-free outcome for a failed request: its HTTP status, a timeout or a generic error."""
    code = gh_http_status(error)
    if code:
        return f"HTTP {code}"
    text = str(error or "").lower()
    match = re.search(r"\(http (\d{3})\)", text)
    if match:
        return f"HTTP {match.group(1)}"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    return "error"


def _retryable(error) -> bool:
    text = str(error or "").lower()
    status = outcome(error)
    return "rate limit" in text or status == "HTTP 429" or status.startswith("HTTP 5") or status == "timeout"


def gh_call(args: list, timeout: int = 180):
    """One ``gh api`` call with bounded retries on rate limits, 5xx and timeouts. Never raises (the contract of
    ``github_freshness.gh_api``): returns ``(data, None, attempts)`` or ``(None, error, attempts)``."""
    error = None
    for attempt in range(1, RETRIES + 2):
        try:
            proc = subprocess.run(["gh", "api", *args], capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            error = "timeout"
        except Exception as exc:  # noqa: BLE001 - recorded as a bounded error, never raised
            return None, f"error: {type(exc).__name__}", attempt
        else:
            if proc.returncode == 0:
                try:
                    return json.loads(proc.stdout), None, attempt
                except ValueError:
                    return None, "error: invalid JSON", attempt
            error = proc.stderr.strip()
        if attempt <= RETRIES and _retryable(error):
            time.sleep(BACKOFF_SECONDS * attempt)
            continue
        return None, error, attempt
    return None, error, RETRIES + 1


def http_json(url: str, timeout: int = 30):
    """One GET of a JSON document with bounded retries on 429 and 5xx: ``(data, http_status, attempts)``; a
    non-HTTP failure returns status ``None`` and data ``{"error": ...}``."""
    for attempt in range(1, RETRIES + 2):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - fixed https host
                return json.load(response), response.status, attempt
        except urllib.error.HTTPError as exc:
            if attempt <= RETRIES and (exc.code == 429 or exc.code >= 500):
                time.sleep(BACKOFF_SECONDS * attempt)
                continue
            return None, exc.code, attempt
        except Exception as exc:  # noqa: BLE001 - recorded as a bounded error, never raised
            if attempt <= RETRIES:
                time.sleep(BACKOFF_SECONDS * attempt)
                continue
            return {"error": type(exc).__name__}, None, attempt
    return None, None, RETRIES + 1


class Requests:
    """Every request one observation makes, in order, with its outcome (never a response body)."""

    def __init__(self):
        self.log: list[dict] = []

    def gh(self, path: str, paginate: bool = False):
        data, error, attempts = gh_call(["--paginate", "--slurp", path] if paginate else [path])
        entry = {"api": "github", "path": path, "status": "ok" if error is None else outcome(error)}
        if paginate:
            entry["paginate"] = True
            if error is None:
                entry["pages"] = len(data) if isinstance(data, list) else None
        if attempts > 1:
            entry["attempts"] = attempts
        self.log.append(entry)
        return data, error

    def deps_dev(self, slug: str) -> dict:
        url = DEPS_DEV + urllib.parse.quote(f"github.com/{slug}", safe="")
        data, status, attempts = http_json(url)
        entry = {"api": "deps.dev", "url": url,
                 "status": "ok" if status == 200 else (f"HTTP {status}" if status else "error")}
        if attempts > 1:
            entry["attempts"] = attempts
        self.log.append(entry)
        if status == 200 and isinstance(data, dict):
            card = data.get("scorecard") or {}
            return {"status": "ok", "license": data.get("license"),
                    "scorecard": ({"date": card.get("date"), "overall_score": card.get("overallScore")}
                                  if card else None)}
        if status == 404:
            return {"status": "not_covered", "http_status": 404}
        return {"status": "error", "http_status": status}


def observe(slug: str) -> dict:
    """One repository's sanitized observation (network). Popularity fields are never copied."""
    requests = Requests()
    obs: dict = {"slug": slug, "observed_at": now_iso()}
    repo, error = requests.gh(f"repos/{slug}")
    if not isinstance(repo, dict):
        obs["error"] = outcome(error)
        obs["requests"] = requests.log
        return obs
    errors: dict[str, str] = {}
    obs.update({"full_name": repo.get("full_name"), "archived": repo.get("archived"),
                "disabled": repo.get("disabled"), "fork": repo.get("fork"),
                "default_branch": repo.get("default_branch"), "pushed_at": repo.get("pushed_at"),
                "license": (repo.get("license") or {}).get("spdx_id"),
                "renamed_to": (repo.get("full_name") if str(repo.get("full_name", "")).lower() != slug.lower()
                               else None)})
    commit, error = requests.gh(f"repos/{slug}/commits/{repo.get('default_branch')}")
    if isinstance(commit, dict) and commit.get("sha"):
        obs["head"] = {"sha": commit.get("sha"),
                       "date": ((commit.get("commit") or {}).get("committer") or {}).get("date")}
    else:
        errors["head"] = outcome(error)

    release, error = requests.gh(f"repos/{slug}/releases/latest")
    if isinstance(release, dict):
        assets = [{"name": a.get("name"), "digest": a.get("digest")} for a in release.get("assets") or []]
        with_digest = [a for a in assets if a["digest"]]
        queried = []
        for asset in [a for a in with_digest if str(a["digest"]).startswith("sha256:")][:MAX_ATTESTED_ASSETS]:
            found, att_error = requests.gh(f"repos/{slug}/attestations/{asset['digest']}")
            entry = {"name": asset["name"], "digest": asset["digest"]}
            if isinstance(found, dict) and att_error is None:
                entry["attestations"] = len(found.get("attestations") or [])
            elif gh_http_status(att_error) == 404:
                entry["attestations"] = 0
            else:
                entry["attestations"] = None
                entry["error"] = outcome(att_error)
                errors[f"attestations:{asset['name']}"] = entry["error"]
            queried.append(entry)
        obs["release"] = {"tag": release.get("tag_name"), "published_at": release.get("published_at"),
                          "assets": len(assets), "assets_with_digest": len(with_digest), "queried_assets": queried}
    elif gh_http_status(error) == 404:
        obs["release"] = None
    else:
        errors["release"] = outcome(error)

    pages, error = requests.gh(f"repos/{slug}/security-advisories?state=published&per_page={PER_PAGE}",
                               paginate=True)
    if error is None and isinstance(pages, list) and all(isinstance(page, list) for page in pages):
        items = [a for page in pages for a in page if isinstance(a, dict)]
        unique = {a.get("ghsa_id") or json.dumps(a, sort_keys=True): a for a in items}
        # The advisories endpoint reports no total, so the collection records only what it read.
        obs["advisories"] = {"observed": len(unique), "complete": True, "pages": len(pages),
                             "severities": sorted((a.get("severity") or "unknown") for a in unique.values())}
    else:
        obs["advisories"] = {"observed": None, "complete": False}
        errors["advisories"] = outcome(error)

    head = (obs.get("head") or {}).get("sha")
    if head:
        pages, error = requests.gh(f"repos/{slug}/commits/{head}/check-runs?per_page={PER_PAGE}", paginate=True)
        if error is None and isinstance(pages, list) and pages and all(isinstance(page, dict) for page in pages):
            runs = {}
            for page in pages:
                for run in page.get("check_runs") or []:
                    runs[run.get("id")] = run
            totals = [page.get("total_count") for page in pages]
            total = totals[0] if isinstance(totals[0], int) else None
            # Every distinct total_count the pages reported: more than one means runs moved while they were listed.
            total_counts = sorted({t for t in totals if isinstance(t, int)})
            conclusions: dict[str, int] = {}
            for run in runs.values():
                key = run.get("conclusion") or run.get("status") or "unknown"
                conclusions[key] = conclusions.get(key, 0) + 1
            # Above CHECK_SUITE_LIMIT suites the runs' total_count covers only the most recent suites, so the head's
            # suite count decides completeness. It is read after the runs, so a suite added meanwhile is counted.
            found, suites_error = requests.gh(f"repos/{slug}/commits/{head}/check-suites?per_page=1")
            suites = found.get("total_count") if isinstance(found, dict) and suites_error is None else None
            if not isinstance(suites, int) or isinstance(suites, bool):
                suites = None
                errors["check_suites"] = outcome(suites_error)
            listed_all = (total is not None and len(runs) == total and len(set(totals)) == 1
                          and total_counts == [total])
            obs["check_runs"] = {"observed": len(runs), "total": total, "total_counts": total_counts,
                                 "check_suites": suites,
                                 "complete": listed_all and suites is not None and suites <= CHECK_SUITE_LIMIT,
                                 "pages": len(pages), "conclusions": dict(sorted(conclusions.items()))}
        else:
            obs["check_runs"] = {"observed": None, "total": None, "complete": False}
            errors["check_runs"] = outcome(error)

    obs["deps_dev"] = requests.deps_dev(slug)
    if obs["deps_dev"]["status"] == "error":
        errors["deps_dev"] = (f"HTTP {obs['deps_dev']['http_status']}" if obs["deps_dev"].get("http_status")
                              else "error")
    if errors:
        obs["partial_errors"] = dict(sorted(errors.items()))
    obs["requests"] = requests.log
    return obs


# --- the audit (pure) --------------------------------------------------------------------------------------------


def parse_time(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def whole_days(earlier, later):
    if earlier is None or later is None:
        return None
    return max((later - earlier).days, 0)


def provenance(release: dict, partial_errors: dict) -> str:
    """attested, none, unknown, no_digest or no_assets. ``none`` needs an answer from every queried asset."""
    if not release.get("assets"):
        return "no_assets"
    if not release.get("assets_with_digest"):
        return "no_digest"
    queried = release.get("queried_assets")
    if queried is None:
        queried = release.get("attested_assets") or []
    queried = [a for a in queried if isinstance(a, dict)]
    if any(isinstance(a.get("attestations"), int) and a["attestations"] > 0 for a in queried):
        return "attested"
    errored = any(a.get("error") or not isinstance(a.get("attestations"), int) for a in queried) or any(
        str(key).startswith("attestations") for key in partial_errors)
    if errored or not queried:
        return "unknown"
    return "none"


def audit_row(slug: str, roles: list, obs: dict) -> dict:
    """Pure: one repository's audit row from its observation."""
    row = {"repository": slug, "roles": roles, "flags": [], "observed_at": obs.get("observed_at")}
    flags: set = set()
    if obs.get("error"):
        flags.add("fetch_error")
        row["error"] = str(obs["error"])[:160]
        row["flags"] = [f for f in FLAGS if f in flags]
        return row
    incomplete: set = set()
    partial = obs.get("partial_errors") if isinstance(obs.get("partial_errors"), dict) else {}
    now = parse_time(obs.get("observed_at"))
    row["archived"] = obs.get("archived") is True
    if row["archived"]:
        flags.add("archived")

    head = obs.get("head") if isinstance(obs.get("head"), dict) else {}
    head_time = parse_time(head.get("date"))
    row["last_commit"] = head.get("date")
    row["days_since_last_commit"] = whole_days(head_time, now)
    if head_time is not None and now is not None:
        # A commit counts only when it is after the cutoff (practice_references.py's hasRecentCommits rule).
        if not head_time > now - timedelta(days=STALE_AFTER_DAYS):
            flags.add("stale")
    else:
        incomplete.add("head")

    release = obs.get("release")
    if release is None and "release" in obs:
        flags.add("no_release")
        row["release"] = None
    elif isinstance(release, dict):
        published = parse_time(release.get("published_at"))
        state = provenance(release, partial)
        queried = release.get("queried_assets")
        if queried is None:
            queried = release.get("attested_assets") or []
        queried = [dict(a) for a in queried if isinstance(a, dict)]
        row["release"] = {"tag": release.get("tag"), "published_at": release.get("published_at"),
                          "days_old": whole_days(published, now), "assets": release.get("assets"),
                          "assets_with_digest": release.get("assets_with_digest"),
                          "queried_assets": queried,
                          "attested_assets": sum(1 for a in queried
                                                 if isinstance(a.get("attestations"), int) and a["attestations"] > 0),
                          "provenance": state}
        if published is not None and now is not None and not published > now - timedelta(days=OLD_RELEASE_DAYS):
            flags.add("old_release")
        if state == "none":
            flags.add("no_provenance")
        elif state == "unknown":
            incomplete.add("attestations")
    else:
        incomplete.add("release")

    advisories = obs.get("advisories")
    if isinstance(advisories, dict) and advisories.get("complete") is True:
        severities = list(advisories.get("severities") or [])
        row["advisories"] = {"count": len(severities), "complete": True, "severities": severities}
        if severities:
            flags.add("advisories")
    else:
        severities = list((advisories or {}).get("severities") or []) if isinstance(advisories, dict) else []
        row["advisories"] = {"count": None, "complete": False, "observed": len(severities) if severities else None,
                             "severities": severities}
        if severities:
            flags.add("advisories")
        incomplete.add("advisories")

    runs = obs.get("check_runs")
    if isinstance(runs, dict):
        conclusions = runs.get("conclusions") if isinstance(runs.get("conclusions"), dict) else {}
        failing = sum(n for k, n in conclusions.items() if k in FAILING)
        suites = runs.get("check_suites")
        suites = suites if isinstance(suites, int) and not isinstance(suites, bool) else None
        counts = runs.get("total_counts") if isinstance(runs.get("total_counts"), list) else None
        # Rechecked from the recorded counts: every listed run read under one unchanged total, and the head within
        # the check-suite limit. An observation without these counts (the shape before they were read) is incomplete.
        complete = (runs.get("complete") is True and isinstance(runs.get("total"), int)
                    and runs.get("observed") == runs.get("total") and counts == [runs.get("total")]
                    and suites is not None and suites <= CHECK_SUITE_LIMIT)
        row["check_runs"] = {"observed": runs.get("observed"), "total": runs.get("total"), "total_counts": counts,
                             "check_suites": suites, "complete": complete,
                             "failing": failing if (complete or failing) else None}
        if failing:
            flags.add("ci_failing")
        if not complete:
            incomplete.add("check_runs")
    else:
        row["check_runs"] = None
        incomplete.add("check_runs")

    row["license"] = obs.get("license")
    deps = obs.get("deps_dev") if isinstance(obs.get("deps_dev"), dict) else {}
    card = deps.get("scorecard")
    row["scorecard"] = card if card else ("not_covered" if deps.get("status") in ("ok", "not_covered") else None)
    if deps.get("status") not in ("ok", "not_covered"):
        incomplete.add("deps_dev")
    if isinstance(card, dict) and isinstance(card.get("overall_score"), (int, float)) \
            and card["overall_score"] < LOW_SCORECARD:
        flags.add("low_scorecard")
    if partial:
        row["partial_errors"] = sorted(partial)
    row["incomplete"] = [c for c in COLLECTIONS if c in incomplete]
    row["flags"] = [f for f in FLAGS if f in flags]
    return row


def _tally(rows: list) -> dict:
    return {"repositories": len(rows),
            "flag_counts": {flag: sum(1 for r in rows if flag in r["flags"]) for flag in FLAGS},
            "archived_or_stale": sum(1 for r in rows if "archived" in r["flags"] or "stale" in r["flags"]),
            "incomplete_counts": {c: sum(1 for r in rows if c in (r.get("incomplete") or [])) for c in COLLECTIONS},
            "provenance": {p: sum(1 for r in rows if isinstance(r.get("release"), dict)
                                  and r["release"].get("provenance") == p) for p in PROVENANCE},
            "scorecard_published": sum(1 for r in rows if isinstance(r.get("scorecard"), dict))}


def build(observations: dict) -> dict:
    """Pure: the audit from the observations alone (their role table was taken from the manifest at collection)."""
    wanted = observations.get("targets", {})
    observed = observations.get("repositories", {})
    rows = [audit_row(slug, wanted.get(slug, []), observed[slug]) for slug in sorted(observed)]
    by_state = {state: _tally([r for r in rows if any(role["state"] == state for role in r["roles"])])
                for state in STATES}
    installed = _tally([r for r in rows if any(role["installs"] for role in r["roles"])])
    by_slot: dict[str, list] = {}
    for r in rows:
        for role in r["roles"]:
            by_slot.setdefault(role["slot_id"], []).append(
                {"repository": r["repository"], "state": role["state"], "installs": role["installs"],
                 "named_as": role["named_as"], "flags": r["flags"]})
    manifest = observations.get("manifest") or {}
    return {
        "schema_version": 2,
        "kind": "upstream_quality_audit",
        "meaning": ("Upstream maintenance, release currency, provenance, advisories, default-branch checks, license "
                    "and published Scorecard for the GitHub repositories that the definitive manifest's foundation "
                    "rows name. Information only: no default, state or slot changes through it."),
        "observed_at": observations.get("collected_at"),
        "thresholds": {"stale_after_days": STALE_AFTER_DAYS, "old_release_days": OLD_RELEASE_DAYS,
                       "low_scorecard": LOW_SCORECARD, "failing_conclusions": list(FAILING),
                       "max_attested_assets": MAX_ATTESTED_ASSETS},
        "inputs": {manifest.get("path") or MANIFEST: manifest.get("sha256"), OBSERVATIONS: None},
        "summary": dict(_tally(rows), by_state=by_state, installed=installed,
                        not_audited=len(observations.get("not_audited") or [])),
        "not_audited": observations.get("not_audited") or [],
        "rows": rows,
        "by_slot": dict(sorted(by_slot.items())),
    }


# --- decision-record figures (pure) -----------------------------------------------------------------------------

TABLE_COLUMNS = (
    ("Repositories", lambda t: t["repositories"]),
    ("Scorecard published", lambda t: t["scorecard_published"]),
    ("No release", lambda t: t["flag_counts"]["no_release"]),
    ("Release > 365 days", lambda t: t["flag_counts"]["old_release"]),
    ("No GitHub attestation", lambda t: t["flag_counts"]["no_provenance"]),
    ("Provenance unknown", lambda t: t["provenance"]["unknown"]),
    ("Published advisories", lambda t: t["flag_counts"]["advisories"]),
    ("Failing head check", lambda t: t["flag_counts"]["ci_failing"]),
    ("Check runs incomplete", lambda t: t["incomplete_counts"]["check_runs"]),
    ("Scorecard < 5", lambda t: t["flag_counts"]["low_scorecard"]),
    ("Archived or stale", lambda t: t["archived_or_stale"]),
    ("Fetch errors", lambda t: t["flag_counts"]["fetch_error"]),
)


def results_table(audit: dict) -> str:
    """The decision record's results table, generated from the audit so its numbers cannot drift from it."""
    summary = audit["summary"]
    groups = [("all", summary)] + [(state, summary["by_state"][state]) for state in STATES]
    groups.append(("installed by a row", summary["installed"]))
    lines = ["| Role | " + " | ".join(name for name, _ in TABLE_COLUMNS) + " |",
             "| " + " | ".join(["---"] * (len(TABLE_COLUMNS) + 1)) + " |"]
    for label, tally in groups:
        lines.append(f"| {label} | " + " | ".join(str(fn(tally)) for _, fn in TABLE_COLUMNS) + " |")
    return "\n".join(lines)


def _roles_text(row: dict) -> str:
    return ", ".join(f"`{role['slot_id']}` ({role['state']}{', installed' if role['installs'] else ''})"
                     for role in row["roles"])


def _listing(rows: list, detail=lambda row: "") -> str:
    if not rows:
        return "none"
    return "; ".join(f"`{row['repository']}`{detail(row)} in {_roles_text(row)}" for row in rows)


def _check_runs_gap(row: dict) -> str:
    """Why a row's check-run collection is incomplete, from the row's own counts."""
    runs = row.get("check_runs")
    if not isinstance(runs, dict) or runs.get("observed") is None:
        return " (not read)"
    suites = runs.get("check_suites")
    if suites is None:
        return f" ({runs['observed']} runs read; check-suite count unknown)"
    if suites > CHECK_SUITE_LIMIT:
        return f" ({runs['observed']} runs read from the {CHECK_SUITE_LIMIT} most recent of {suites} check suites)"
    counts = runs.get("total_counts") or []
    if len(counts) > 1:
        return (f" ({runs['observed']} runs read while the reported total moved between pages: "
                + ", ".join(str(count) for count in counts) + ")")
    return f" ({runs['observed']} of {runs['total']} runs read)"


def _failing_detail(row: dict) -> str:
    runs = row["check_runs"]
    return f" ({runs['failing']} of {runs['observed']}{'' if runs['complete'] else ' read, collection incomplete'})"


def results_markdown(audit: dict) -> str:
    """The decision record's results, generated from the audit so that none of its numbers can drift from it."""
    summary, rows = audit["summary"], audit["rows"]

    def flagged(flag):
        return [row for row in rows if flag in row["flags"]]

    incomplete = summary["incomplete_counts"]
    provenance_counts = summary["provenance"]
    not_audited = "; ".join(
        f"`{entry['slot_id']}` ({entry['state']}): "
        + (entry["url"] if entry["reason"] == "not_github" else "finalists named without a repository")
        for entry in audit["not_audited"]) or "none"
    lines = [
        f"The audit covers {summary['repositories']} GitHub repositories that the manifest's foundation rows name, "
        f"observed until {audit['observed_at']}; a row installs {summary['installed']['repositories']} of them. A "
        "repository can hold roles in several slots, so the state rows overlap. \"Provenance unknown\" and \"Check "
        "runs incomplete\" count collections that could not establish a negative fact.",
        "",
        results_table(audit),
        "",
        f"- **Collections:** {sum(incomplete.values())} incomplete (head {incomplete['head']}, release "
        f"{incomplete['release']}, attestations {incomplete['attestations']}, advisories {incomplete['advisories']}, "
        f"check runs {incomplete['check_runs']}, deps.dev {incomplete['deps_dev']}); "
        f"{summary['flag_counts']['fetch_error']} repositories could not be read.",
        "- **Stale** (no default-branch commit after the 90-day cutoff): " + _listing(
            flagged("stale"), lambda r: f" (last commit {r['last_commit']}, {r['days_since_last_commit']} days)") + ".",
        "- **No GitHub release** (`releases/latest` answers 404): " + _listing(flagged("no_release")) + ".",
        "- **Latest release older than 365 days:** " + _listing(
            flagged("old_release"), lambda r: f" (`{r['release']['tag']}`, {r['release']['days_old']} days)") + ".",
        "- **No GitHub attestation on any queried asset:** " + _listing(
            flagged("no_provenance"),
            lambda r: f" ({len(r['release']['queried_assets'])} of {r['release']['assets_with_digest']} "
                      "digest-carrying assets queried)") + ".",
        f"- **Provenance of the latest release:** attested {provenance_counts['attested']}, no attestation "
        f"{provenance_counts['none']}, unknown {provenance_counts['unknown']}, no digest-carrying asset "
        f"{provenance_counts['no_digest']}, no asset {provenance_counts['no_assets']}, no release "
        f"{summary['flag_counts']['no_release']}.",
        f"- **Scorecard:** published for {summary['scorecard_published']} of {summary['repositories']}; below "
        f"{LOW_SCORECARD}: " + _listing(
            flagged("low_scorecard"),
            lambda r: f" ({r['scorecard']['overall_score']}, scan of {str(r['scorecard']['date'])[:10]})") + ".",
        "- **Failing check runs on the default-branch head:** " + _listing(flagged("ci_failing"), _failing_detail)
        + ".",
        f"- **Check runs incomplete** (a head above {CHECK_SUITE_LIMIT} check suites, or a short or failed read): "
        + _listing([row for row in rows if "check_runs" in (row.get("incomplete") or [])], _check_runs_gap) + ".",
        "- **Published advisories:** " + _listing(
            flagged("advisories"), lambda r: f" ({r['advisories']['count']})") + ".",
        f"- **Not audited** ({summary['not_audited']}): {not_audited}.",
    ]
    return "\n".join(lines)


# --- modes -------------------------------------------------------------------------------------------------------


def guard(text: str, rel: str) -> bool:
    for label, pattern in PRIVATE_CONTENT:
        if pattern.search(text):
            print(f"{rel}: {label} in generated output", file=sys.stderr)
            return False
    return True


def rate_remaining():
    data, _error, _attempts = gh_call(["rate_limit"], timeout=60)
    core = ((data or {}).get("resources") or {}).get("core") or {}
    return core.get("remaining"), core.get("reset")


def collect(workers: int) -> int:
    wanted, not_audited = targets(load(MANIFEST))
    remaining, reset = rate_remaining()
    needed = REQUESTS_PER_REPOSITORY * len(wanted)
    print(json.dumps({"status": "collecting", "targets": len(wanted), "rate_remaining": remaining,
                      "rate_needed": needed}), file=sys.stderr)
    if not isinstance(remaining, int) or remaining < needed:
        print(f"refused: GitHub REST budget {remaining} is below {needed} (resets at {reset})", file=sys.stderr)
        return 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = dict(zip(wanted, pool.map(observe, wanted)))
    data = {"schema_version": 2, "kind": "upstream_audit_observations", "collected_at": now_iso(),
            "manifest": {"path": MANIFEST, "sha256": sha256(MANIFEST)}, "sources": SOURCES,
            "targets": wanted, "not_audited": not_audited, "repositories": results}
    text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if not guard(text, OBSERVATIONS):
        return 1
    (ROOT / OBSERVATIONS).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / OBSERVATIONS).write_text(text, encoding="utf-8")
    host_receipts.register_file(ROOT, OBSERVATIONS)
    after, _ = rate_remaining()
    print(json.dumps({"status": "collected", "repositories": len(results),
                      "fetch_errors": sum(1 for o in results.values() if o.get("error")),
                      "with_partial_errors": sum(1 for o in results.values() if o.get("partial_errors")),
                      "requests": sum(len(o.get("requests") or []) for o in results.values()),
                      "rate_remaining_after": after}))
    return 0


def consistency(observations: dict, manifest_sha: str, manifest: dict) -> tuple[list, dict]:
    """Why the observations no longer describe the manifest: a changed sha256, role table or not-audited list."""
    problems = []
    recorded = observations.get("manifest") or {}
    if recorded.get("sha256") != manifest_sha:
        problems.append(f"{MANIFEST} changed since collection (recorded {recorded.get('sha256')}, now {manifest_sha})")
    current, not_audited = targets(manifest)
    moved = drift(observations.get("targets") or {}, current)
    if any(moved.values()):
        problems.append("the role table differs from the one recorded at collection")
    if (observations.get("not_audited") or []) != not_audited:
        problems.append("the not-audited list differs from the one recorded at collection")
    return problems, moved


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--collect", action="store_true", help="observe every target (network)")
    mode.add_argument("--build", action="store_true", help="write the audit from the observations")
    mode.add_argument("--check", action="store_true",
                      help="exit 1 if the audit differs from its observations or they from the manifest (default)")
    mode.add_argument("--results", action="store_true",
                      help="print the decision record's results section from the committed audit")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    if args.collect:
        return collect(args.workers)
    if args.results:
        print(results_markdown(load(OUT)))
        return 0
    observations = load(OBSERVATIONS)
    data = build(observations)
    data["inputs"][OBSERVATIONS] = sha256(OBSERVATIONS)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if not guard(text, OUT):
        return 1
    if args.build:
        (ROOT / OUT).write_text(text, encoding="utf-8")
        host_receipts.register_file(ROOT, OUT)
        print(json.dumps({"status": "written", "repositories": data["summary"]["repositories"],
                          "flag_counts": data["summary"]["flag_counts"]}))
        return 0
    failed = False
    if not (ROOT / OUT).is_file():
        print("missing: run tools/sota-convergence/upstream_audit.py --build", file=sys.stderr)
        failed = True
    elif (ROOT / OUT).read_text(encoding="utf-8") != text:
        print(f"stale: {OUT} no longer matches its observations; run --build", file=sys.stderr)
        failed = True
    problems, moved = consistency(observations, sha256(MANIFEST), load(MANIFEST))
    for problem in problems:
        print(f"drift: {problem}; re-collect with --collect, then --build", file=sys.stderr)
    if problems:
        print(json.dumps({"status": "failed", "drift": moved}, indent=2))
        return 1
    if failed:
        return 1
    print(json.dumps({"status": "passed", "repositories": data["summary"]["repositories"], "drift": moved}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
