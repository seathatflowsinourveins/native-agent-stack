#!/usr/bin/env python3
"""Upstream quality audit of the final catalog's repositories.

For every standing pick, challenger and unjudged incumbent of the final catalog that is a GitHub repository, this
records maintenance, release currency, release provenance (asset digests and GitHub attestations), published security
advisories, the check runs on the default-branch head, the license, and the OpenSSF Scorecard result that deps.dev
publishes where one exists. It is information only: it never selects, ranks or changes a pick or a status; a pick
becomes final only through the rule and the measured comparisons of ``docs/decisions/2026-10-01-final-catalog.md``.

Sources (search-first, 2026-10-02): GitHub REST through ``gh api`` (``github_freshness.fetch_repository`` and
``gh_api``, with the popularity fields dropped; ``releases/latest`` with its assets' ``digest``,
``attestations/{digest}``, ``security-advisories`` and ``commits/{sha}/check-runs``) and the deps.dev v3 project
endpoint (https://docs.deps.dev/api/v3/#getproject) for the license and the Scorecard of the OpenSSF weekly scan. A
repository outside that scan has no published Scorecard and is recorded as not covered.

Flags (thresholds frozen here; a flag is information, never a verdict):
- ``fetch_error``: the repository could not be read.
- ``archived``: the repository is archived.
- ``stale``: no default-branch commit within ``STALE_AFTER_DAYS`` (90, ossf/scorecard's Maintained window).
- ``no_release``: no published release.
- ``old_release``: the latest release is older than 365 days.
- ``no_provenance``: the latest release has digest-carrying assets and none has a GitHub attestation (a project
  that signs another way, such as a Sigstore bundle beside its checksums, still shows this flag).
- ``advisories``: the repository has published security advisories (count and severities). Whether one affects a
  pinned or the latest release is not evaluated; a mature project often publishes and fixes them.
- ``ci_failing``: a check run on the default-branch head concluded failure, timed_out or startup_failure.
- ``low_scorecard``: a published Scorecard overall score below 5.0.
Every age is measured from the observation's own ``observed_at``, so a rebuild is deterministic.

Modes: ``--collect`` (network) writes the sanitized observations; ``--build`` (offline) writes the audit from them;
``--check`` (default, offline) recomputes the audit and fails when it differs, and reports repositories the final
catalog names but the observations lack as drift, not as a failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
for _path in (str(REPO_ROOT), str(HERE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from github_freshness import fetch_repository, gh_api  # noqa: E402
from practice_references import STALE_AFTER_DAYS, gh_http_status  # noqa: E402
from scripts import host_receipts  # noqa: E402
from scripts.final_catalog import github_key  # noqa: E402
from scripts.validate import PRIVATE_CONTENT  # noqa: E402

ROOT = REPO_ROOT
FINAL = "catalogs/foundation/final-catalog-20261001.json"
OBSERVATIONS = "evidence/artifacts/upstream-audit-20261002/observations.json"
OUT = "catalogs/foundation/upstream-audit-20261002.json"
OLD_RELEASE_DAYS = 365
LOW_SCORECARD = 5.0
FAILING = ("failure", "timed_out", "startup_failure")
POPULARITY = ("stargazers_count", "forks_count", "open_issues_count", "description", "language")
FLAGS = ("fetch_error", "archived", "stale", "no_release", "old_release", "no_provenance", "advisories",
         "ci_failing", "low_scorecard")
DEPS_DEV = "https://api.deps.dev/v3/projects/"
MAX_ATTESTED_ASSETS = 5


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def sha256(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def targets(final: dict) -> dict:
    """GitHub repository key -> sorted roles ``{layer_id, role}`` from the final catalog."""
    found: dict[str, set] = {}

    def add(key, layer_id, role):
        if key and "/" in key and " " not in key and not key.startswith("name:"):
            found.setdefault(key.lower(), set()).add((layer_id, role))

    for row in final["rows"]:
        layer_id, result = row["layer_id"], row["final"]
        for label in result.get("standing_picks") or []:
            add(label, layer_id, "standing_pick")
        for label in result.get("challengers") or []:
            add(label, layer_id, "challenger")
        if row.get("blind") is None:
            for winner in row.get("selection_of_record") or []:
                add(github_key(winner.get("repository")), layer_id, "unjudged_incumbent")
    return {key: [{"layer_id": layer, "role": role} for layer, role in sorted(roles)]
            for key, roles in sorted(found.items())}


def deps_dev(slug: str) -> dict:
    url = DEPS_DEV + urllib.parse.quote(f"github.com/{slug}", safe="")
    try:
        with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - fixed https host
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        return {"status": "not_covered" if exc.code == 404 else "error", "http_status": exc.code}
    except Exception as exc:  # noqa: BLE001 - recorded as a bounded error, never raised
        return {"status": "error", "error": str(exc)[:160]}
    card = data.get("scorecard") or {}
    return {"status": "ok", "license": data.get("license"),
            "scorecard": ({"date": card.get("date"), "overall_score": card.get("overallScore")} if card else None)}


def observe(slug: str) -> dict:
    """One repository's sanitized observation (network)."""
    obs = fetch_repository(slug)
    for key in POPULARITY:
        obs.pop(key, None)
    if obs.get("error"):
        return obs
    errors = dict(obs.pop("partial_errors", {}) or {})
    release, err = gh_api(f"repos/{slug}/releases/latest")
    if release:
        assets = [{"name": a.get("name"), "digest": a.get("digest")} for a in release.get("assets") or []]
        attested = []
        for asset in [a for a in assets if (a["digest"] or "").startswith("sha256:")][:MAX_ATTESTED_ASSETS]:
            found, att_err = gh_api(f"repos/{slug}/attestations/{asset['digest']}")
            if found:
                attested.append({"name": asset["name"], "attestations": len(found.get("attestations") or [])})
            elif gh_http_status(att_err) == 404:
                attested.append({"name": asset["name"], "attestations": 0})
            else:
                errors[f"attestations:{asset['name']}"] = att_err
        obs["release"] = {"tag": release.get("tag_name"), "published_at": release.get("published_at"),
                          "assets": len(assets), "assets_with_digest": sum(1 for a in assets if a["digest"]),
                          "attested_assets": attested}
    elif gh_http_status(err) == 404:
        obs["release"] = None
    else:
        errors["release"] = err
    advisories, err = gh_api(f"repos/{slug}/security-advisories?state=published&per_page=100")
    if isinstance(advisories, list):
        obs["advisories"] = sorted((a.get("severity") or "unknown") for a in advisories)
    else:
        errors["advisories"] = err
    head = (obs.get("head") or {}).get("sha")
    if head:
        runs, err = gh_api(f"repos/{slug}/commits/{head}/check-runs?per_page=100")
        if isinstance(runs, dict):
            conclusions: dict[str, int] = {}
            for run in runs.get("check_runs") or []:
                key = run.get("conclusion") or run.get("status") or "unknown"
                conclusions[key] = conclusions.get(key, 0) + 1
            obs["check_runs"] = {"total": runs.get("total_count"), "conclusions": dict(sorted(conclusions.items()))}
        else:
            errors["check_runs"] = err
    obs["deps_dev"] = deps_dev(slug)
    if errors:
        obs["partial_errors"] = {k: (v or "")[:160] for k, v in sorted(errors.items())}
    return obs


def parse_time(value):
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def days_between(earlier, later):
    if earlier is None or later is None:
        return None
    return (later - earlier).days


def audit_row(slug: str, roles: list, obs: dict) -> dict:
    """Pure: one repository's audit row from its observation."""
    row = {"repository": slug, "roles": roles, "flags": [], "observed_at": obs.get("observed_at")}
    flags = set()
    if obs.get("error"):
        flags.add("fetch_error")
        row["error"] = obs["error"][:160]
        row["flags"] = [f for f in FLAGS if f in flags]
        return row
    now = parse_time(obs.get("observed_at"))
    row["archived"] = obs.get("archived") is True
    if row["archived"]:
        flags.add("archived")
    head_date = parse_time((obs.get("head") or {}).get("date"))
    row["last_commit"] = (obs.get("head") or {}).get("date")
    row["days_since_last_commit"] = days_between(head_date, now)
    if row["days_since_last_commit"] is not None and row["days_since_last_commit"] > STALE_AFTER_DAYS:
        flags.add("stale")
    release = obs.get("release")
    if release is None and "release" in obs:
        flags.add("no_release")
        row["release"] = None
    elif isinstance(release, dict):
        age = days_between(parse_time(release.get("published_at")), now)
        attested = [a for a in release.get("attested_assets") or [] if a.get("attestations")]
        row["release"] = {"tag": release.get("tag"), "published_at": release.get("published_at"), "days_old": age,
                          "assets": release.get("assets"), "assets_with_digest": release.get("assets_with_digest"),
                          "attested_assets": len(attested)}
        if age is not None and age > OLD_RELEASE_DAYS:
            flags.add("old_release")
        if release.get("assets") and release.get("assets_with_digest") and not attested:
            flags.add("no_provenance")
    advisories = obs.get("advisories")
    if isinstance(advisories, list):
        row["advisories"] = {"count": len(advisories), "severities": advisories}
        if advisories:
            flags.add("advisories")
    runs = obs.get("check_runs")
    if isinstance(runs, dict):
        failing = sum(n for k, n in (runs.get("conclusions") or {}).items() if k in FAILING)
        row["check_runs"] = {"total": runs.get("total"), "failing": failing}
        if failing:
            flags.add("ci_failing")
    row["license"] = obs.get("license")
    deps = obs.get("deps_dev") or {}
    card = deps.get("scorecard")
    row["scorecard"] = card if card else ("not_covered" if deps.get("status") in ("ok", "not_covered") else None)
    if isinstance(card, dict) and isinstance(card.get("overall_score"), (int, float)) and card["overall_score"] < LOW_SCORECARD:
        flags.add("low_scorecard")
    if obs.get("partial_errors"):
        row["partial_errors"] = sorted(obs["partial_errors"])
    row["flags"] = [f for f in FLAGS if f in flags]
    return row


def build(observations: dict) -> dict:
    """Pure: the audit from the observations alone (their roles were taken from the final catalog at collection)."""
    wanted = observations.get("targets", {})
    observed = observations.get("repositories", {})
    rows = [audit_row(slug, wanted.get(slug, []), observed[slug]) for slug in sorted(observed)]
    counts = {flag: sum(1 for r in rows if flag in r["flags"]) for flag in FLAGS}
    by_layer: dict[str, dict] = {}
    for r in rows:
        for role in r["roles"]:
            entry = by_layer.setdefault(role["layer_id"], {})
            entry.setdefault(role["role"], []).append({"repository": r["repository"], "flags": r["flags"]})
    return {
        "schema_version": 1,
        "kind": "upstream_quality_audit",
        "meaning": ("Upstream maintenance, release currency, provenance, advisories, default-branch checks, license and "
                    "published Scorecard for the final catalog's GitHub repositories. Information only: no pick, status "
                    "or selection changes through it."),
        "observed_at": observations.get("collected_at"),
        "thresholds": {"stale_after_days": STALE_AFTER_DAYS, "old_release_days": OLD_RELEASE_DAYS,
                       "low_scorecard": LOW_SCORECARD, "failing_conclusions": list(FAILING)},
        "inputs": {FINAL: observations.get("final_catalog_sha256"), OBSERVATIONS: None},
        "summary": {"repositories": len(rows), "flag_counts": counts,
                    "scorecard_published": sum(1 for r in rows if isinstance(r.get("scorecard"), dict))},
        "rows": rows,
        "by_layer": dict(sorted(by_layer.items())),
    }


def guard(text: str, rel: str) -> bool:
    for label, pattern in PRIVATE_CONTENT:
        if pattern.search(text):
            print(f"{rel}: {label} in generated output", file=sys.stderr)
            return False
    return True


def collect(workers: int) -> int:
    final = load(FINAL)
    wanted = targets(final)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = dict(zip(wanted, pool.map(observe, wanted)))
    data = {"schema_version": 1, "kind": "upstream_audit_observations",
            "collected_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "final_catalog": FINAL, "final_catalog_sha256": sha256(FINAL),
            "sources": ["gh api (GitHub REST)", DEPS_DEV], "targets": wanted, "repositories": results}
    text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if not guard(text, OBSERVATIONS):
        return 1
    (ROOT / OBSERVATIONS).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / OBSERVATIONS).write_text(text, encoding="utf-8")
    host_receipts.register_file(ROOT, OBSERVATIONS)
    print(json.dumps({"status": "collected", "repositories": len(results),
                      "errors": sum(1 for o in results.values() if o.get("error"))}))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--collect", action="store_true", help="observe every target (network)")
    mode.add_argument("--build", action="store_true", help="write the audit from the observations")
    mode.add_argument("--check", action="store_true", help="exit 1 if the audit differs from its observations (default)")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args(argv)
    if args.collect:
        return collect(args.workers)
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
    if not (ROOT / OUT).is_file():
        print("missing: run tools/sota-convergence/upstream_audit.py --build", file=sys.stderr)
        return 1
    if (ROOT / OUT).read_text(encoding="utf-8") != text:
        print(f"stale: {OUT} no longer matches its observations; run --build", file=sys.stderr)
        return 1
    drift = sorted(set(targets(load(FINAL))) - set(observations.get("repositories", {})))
    print(json.dumps({"status": "passed", "repositories": data["summary"]["repositories"], "drift": drift}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
