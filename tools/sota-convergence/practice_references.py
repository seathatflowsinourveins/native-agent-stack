#!/usr/bin/env python3
"""Report-only freshness check for catalogs/foundation/practice-references.json.

For every pinned Claude Code practice reference it reports, per repository through the
signed-in ``gh`` CLI:

* whether GitHub marks the repository archived;
* the default-branch head SHA and how many default-branch commits landed after the pin
  (pin drift), or that the pin no longer resolves;
* whether the repository is stale in the sense of the OpenSSF Scorecard Maintained
  check: archived, or no default-branch commit in the last 90 days;
* whether the repository was renamed or transferred, or is missing.

It writes a deterministic JSON report (``--out``) and a Markdown table for a job summary
(``--markdown``). Drift, staleness, renames, missing repositories and fetch errors are
report-only: the exit status is 0 for every well-formed catalog, and 2 only when the
catalog is malformed (unreadable, invalid JSON, a duplicate key, or a validate_catalog()
error) or an argument is invalid. Nothing here edits a pin, a disposition or a practice.
validate_catalog(), classify(), build_report() and render_markdown() are pure, so
tests/test_practice_references.py runs offline; ``--observations`` replays recorded
observations instead of calling gh.

Sources:

* In-repo reference implementation: tools/sota-convergence/github_freshness.py.
  fetch_repository() (archived, full_name, default_branch, the head commit and its
  committer date), gh_api() (never raises) and is_expected_missing() (a 404 is an answer;
  a timeout, 429 or 5xx is not) are imported from it, not re-written.
  scripts/catalog_decisions.py's unique_json() rejects duplicate JSON keys.
* Stale: the Maintained check, https://github.com/ossf/scorecard/blob/main/docs/checks.md#maintained,
  read at ossf/scorecard@8788fc28f563f5a68b4ba67a7a65eb7de6a0a5dd: docs/checks.md:400-408
  (an archived project receives the lowest score; activity is judged over the previous
  90 days), checks/evaluation/maintained.go:31 (lookBackDays = 90) and :88-89 (archived:
  minimum score), probes/hasRecentCommits/impl.go:41 and :52-57 (a default-branch commit
  counts when its CommittedDate is after now minus 90 days). This checker reads only the
  default-branch head commit's committer date and does not credit maintainers' issue
  activity, which Scorecard also scores, so "stale" here is the no-commit condition of the
  Maintained check, not a Scorecard score.
* Pin drift: GitHub REST "Compare two commits", GET /repos/{owner}/{repo}/compare/{basehead}
  (https://docs.github.com/en/rest/commits/commits#compare-two-commits: "equivalent to
  running the git log BASE..HEAD command"; per_page paginates the commit list), and the
  commit-comparison schema (base_commit, status enum diverged/ahead/behind/identical,
  ahead_by, behind_by) in github/rest-api-description@c6721f32a17a71397ae46be21be90d7f1a173b6e
  descriptions/api.github.com/api.github.com.json:55402 (the path) and :148219-148273 (the
  schema). The pin is BASE and the observed head SHA is HEAD, so commits_since_pin is
  ahead_by; a 404 or 422 answer (the operation's documented error responses) means the
  pin does not resolve.
* Renamed: repos/get answers 301 moved_permanently for a moved repository (same
  description, :39424), and the REST best practices say to follow it
  (https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api#follow-redirects);
  gh follows it, so the returned full_name differs from the catalog's owner/name.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
for _path in (str(REPO_ROOT), str(HERE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# Reused, not re-written (see the module docstring).
from github_freshness import fetch_repository, gh_api, is_expected_missing  # noqa: E402
from scripts.catalog_decisions import unique_json  # noqa: E402

SCHEMA = "practice-references-freshness/1"
CATALOG_KIND = "practice_references"
DEFAULT_CATALOG = REPO_ROOT / "catalogs" / "foundation" / "practice-references.json"
# ossf/scorecard@8788fc28 probes/hasRecentCommits/impl.go:41 and checks/evaluation/maintained.go:31.
STALE_AFTER_DAYS = 90
ROLES = ("community", "primary")
# Flag order in a row; the first flag present is the row's headline status ("fresh" when none).
FLAGS = ("missing", "fetch_error", "archived", "stale", "renamed", "pin_unresolved", "drifted",
         "pin_date_mismatch")
DRIFT_STATUSES = ("ahead", "behind", "diverged")

TOP_LEVEL_REQUIRED = ("schema_version", "kind", "checked_at", "dimensions", "references")
TOP_LEVEL_TEXT = ("scope", "pin_rule", "stars_at_check_rule")
TOP_LEVEL_KEYS = frozenset(TOP_LEVEL_REQUIRED + TOP_LEVEL_TEXT + ("freshness_check",))
DIMENSION_KEYS = frozenset({"id", "description", "topics"})
ENTRY_REQUIRED = ("repository", "role", "pin", "pin_date", "stars_at_check", "used_for", "record")
ENTRY_OPTIONAL = ("paths_read", "release", "prior_pin")

REPOSITORY_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9._-]{1,100}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RECORD_RE = re.compile(r"^docs/decisions/\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")


def _is_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_date(value) -> bool:
    if not isinstance(value, str) or not DATE_RE.match(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_repository(value) -> bool:
    return (isinstance(value, str) and bool(REPOSITORY_RE.match(value))
            and value.split("/", 1)[1] not in {".", ".."})


def _is_sha(value) -> bool:
    return isinstance(value, str) and bool(SHA_RE.match(value))


def _validate_used_for(used_for, label, dimension_ids) -> list:
    if not isinstance(used_for, list) or not used_for:
        return [f"{label}: expected a non-empty list"]
    errors, seen = [], set()
    for position, use in enumerate(used_for):
        use_label = f"{label}[{position}]"
        if not isinstance(use, dict) or set(use) != {"dimension", "use"}:
            errors.append(f"{use_label}: expected an object with exactly dimension and use")
            continue
        dimension = use["dimension"]
        if not isinstance(dimension, str) or dimension not in dimension_ids:
            errors.append(f"{use_label}.dimension: not declared in catalog.dimensions")
        elif dimension in seen:
            errors.append(f"{use_label}.dimension: duplicate {dimension}")
        else:
            seen.add(dimension)
        if not _is_text(use["use"]):
            errors.append(f"{use_label}.use: expected non-empty text")
    return errors


def _validate_entry(entry, label, dimension_ids, checked_at) -> list:
    if not isinstance(entry, dict):
        return [f"{label}: expected an object"]
    errors = [f"{label}: missing {key}" for key in ENTRY_REQUIRED if key not in entry]
    errors += [f"{label}: unknown key {key}"
               for key in sorted(set(entry) - set(ENTRY_REQUIRED) - set(ENTRY_OPTIONAL))]
    if "repository" in entry and not _is_repository(entry["repository"]):
        errors.append(f"{label}.repository: expected a GitHub owner/name")
    if "role" in entry and entry["role"] not in ROLES:
        errors.append(f"{label}.role: expected one of {', '.join(ROLES)}")
    if "pin" in entry and not _is_sha(entry["pin"]):
        errors.append(f"{label}.pin: expected a full 40-character lower-case commit SHA")
    if "pin_date" in entry:
        if not _is_date(entry["pin_date"]):
            errors.append(f"{label}.pin_date: expected a YYYY-MM-DD date")
        elif checked_at and entry["pin_date"] > checked_at:
            errors.append(f"{label}.pin_date: later than the catalog's checked_at {checked_at}")
    stars = entry.get("stars_at_check")
    if "stars_at_check" in entry and (type(stars) is not int or stars < 0):
        errors.append(f"{label}.stars_at_check: expected a non-negative integer")
    if "used_for" in entry:
        errors += _validate_used_for(entry["used_for"], f"{label}.used_for", dimension_ids)
    if "record" in entry and not (isinstance(entry["record"], str) and RECORD_RE.match(entry["record"])):
        errors.append(f"{label}.record: expected a docs/decisions/YYYY-MM-DD-<name>.md path")
    if "paths_read" in entry:
        paths = entry["paths_read"]
        if not isinstance(paths, list) or not paths or not all(_is_text(path) for path in paths):
            errors.append(f"{label}.paths_read: expected a non-empty list of non-empty text")
    if "release" in entry and not _is_text(entry["release"]):
        errors.append(f"{label}.release: expected non-empty text")
    if "prior_pin" in entry:
        prior = entry["prior_pin"]
        if (not isinstance(prior, dict) or set(prior) != {"pin", "release"} or not _is_sha(prior["pin"])
                or not _is_text(prior["release"])):
            errors.append(f"{label}.prior_pin: expected an object with a full-SHA pin and a release")
    return errors


def validate_catalog(catalog) -> list:
    """Every structural problem in a parsed catalog, in document order; [] when well-formed.

    The record path's format is checked, not its existence: a wave's decision record can
    land in a separate pull request from its catalog entries."""
    if not isinstance(catalog, dict):
        return ["catalog: expected a JSON object"]
    errors = [f"catalog: missing {key}" for key in TOP_LEVEL_REQUIRED if key not in catalog]
    errors += [f"catalog: unknown key {key}" for key in sorted(set(catalog) - TOP_LEVEL_KEYS)]
    if "schema_version" in catalog and (type(catalog["schema_version"]) is not int
                                        or catalog["schema_version"] != 1):
        errors.append("catalog.schema_version: expected the integer 1")
    if "kind" in catalog and catalog["kind"] != CATALOG_KIND:
        errors.append(f"catalog.kind: expected {CATALOG_KIND!r}")
    checked_at = catalog.get("checked_at")
    if "checked_at" in catalog and not _is_date(checked_at):
        errors.append("catalog.checked_at: expected a YYYY-MM-DD date")
        checked_at = None
    for key in TOP_LEVEL_TEXT:
        if key in catalog and not _is_text(catalog[key]):
            errors.append(f"catalog.{key}: expected non-empty text")
    if "freshness_check" in catalog:
        check = catalog["freshness_check"]
        if not isinstance(check, dict) or not check or not all(_is_text(value) for value in check.values()):
            errors.append("catalog.freshness_check: expected an object of non-empty text")

    dimension_ids = set()
    dimensions = catalog.get("dimensions")
    if "dimensions" in catalog and (not isinstance(dimensions, list) or not dimensions):
        errors.append("catalog.dimensions: expected a non-empty list")
    elif isinstance(dimensions, list):
        for index, dimension in enumerate(dimensions):
            label = f"dimensions[{index}]"
            if not isinstance(dimension, dict):
                errors.append(f"{label}: expected an object")
                continue
            errors += [f"{label}: unknown key {key}" for key in sorted(set(dimension) - DIMENSION_KEYS)]
            ident = dimension.get("id")
            if not isinstance(ident, str) or not KEBAB_RE.match(ident):
                errors.append(f"{label}.id: expected a lower-case kebab-case id")
            elif ident in dimension_ids:
                errors.append(f"{label}.id: duplicate {ident}")
            else:
                dimension_ids.add(ident)
            if not _is_text(dimension.get("description")):
                errors.append(f"{label}.description: expected non-empty text")
            topics = dimension.get("topics", [])
            if not isinstance(topics, list) or not all(_is_text(topic) for topic in topics):
                errors.append(f"{label}.topics: expected a list of non-empty text")

    references = catalog.get("references")
    if "references" in catalog and (not isinstance(references, list) or not references):
        errors.append("catalog.references: expected a non-empty list")
    elif isinstance(references, list):
        first_index = {}
        for index, entry in enumerate(references):
            label = f"references[{index}]"
            errors += _validate_entry(entry, label, dimension_ids, checked_at)
            if isinstance(entry, dict) and isinstance(entry.get("repository"), str):
                key = entry["repository"].lower()
                if key in first_index:
                    errors.append(f"{label}.repository: duplicate of references[{first_index[key]}]")
                else:
                    first_index[key] = index
    return errors


def load_catalog(path: Path):
    """(catalog, errors) for a catalog file; errors is non-empty when it is malformed."""
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
    except (OSError, UnicodeError, ValueError) as exc:
        return None, [f"{path.name}: not a readable JSON document without duplicate keys ({type(exc).__name__})"]
    errors = validate_catalog(catalog)
    return (None if errors else catalog), errors


def observe(entry: dict) -> dict:
    """One repository's upstream observation through gh (network). Never raises: failures
    are carried as "error" (the repository fetch) or "compare_error" (the pin comparison)."""
    repository, pin = entry["repository"], entry["pin"]
    try:
        record = fetch_repository(repository)
        observation = {key: record.get(key) for key in (
            "error", "full_name", "archived", "default_branch", "head", "latest_release", "partial_errors")}
        head_sha = (record.get("head") or {}).get("sha")
        if record.get("error") or not head_sha:
            return observation
        comparison, error = gh_api(f"repos/{repository}/compare/{pin}...{head_sha}?per_page=1")
        if isinstance(comparison, dict) and comparison.get("status"):
            base = comparison.get("base_commit") or {}
            observation["compare"] = {
                "status": comparison.get("status"),
                "ahead_by": comparison.get("ahead_by"),
                "behind_by": comparison.get("behind_by"),
                "base_sha": base.get("sha"),
                "base_date": ((base.get("commit") or {}).get("committer") or {}).get("date"),
            }
        else:
            observation["compare_error"] = error or "the comparison returned no status"
        return observation
    except Exception as exc:  # noqa: BLE001 - one bad repository must not abort the report
        return {"error": f"observation failed ({type(exc).__name__})"}


def _timestamp(value):
    """A GitHub ISO-8601 timestamp as an aware UTC datetime, or None."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _one_line(text, limit=160) -> str:
    return " ".join(str(text).split())[:limit]


def is_unresolvable_pin(error) -> bool:
    """True when a failed comparison means the pin does not resolve in the repository (404 or
    422), not a transient failure (timeout, 429, 5xx), which is_expected_missing() excludes."""
    if is_expected_missing(error):
        return True
    lowered = str(error or "").lower()
    return "429" not in lowered and bool(re.search(r"\b422\b", lowered))


def _finish(row: dict, flags: set, errors: list) -> dict:
    row["flags"] = [flag for flag in FLAGS if flag in flags]
    row["status"] = row["flags"][0] if row["flags"] else "fresh"
    row["error"] = "; ".join(_one_line(error) for error in errors) if errors else None
    return row


def classify(entry: dict, observation, now: datetime) -> dict:
    """Pure: the report row for one catalog entry and its observation, evaluated at ``now``."""
    row = {
        "repository": entry["repository"], "role": entry["role"], "pin": entry["pin"],
        "pin_date": entry["pin_date"], "status": "fresh", "flags": [], "archived": None, "stale": None,
        "stale_reason": None, "renamed_to": None, "default_branch": None, "head_sha": None,
        "head_date": None, "days_since_head_commit": None, "compare_status": None,
        "commits_since_pin": None, "pin_commits_not_on_head": None, "pin_date_observed": None,
        "latest_release": None, "error": None,
    }
    flags, errors = set(), []
    if not isinstance(observation, dict):
        observation = {"error": "not observed"}
    if observation.get("error"):
        flags.add("missing" if is_expected_missing(observation["error"]) else "fetch_error")
        errors.append(observation["error"])
        return _finish(row, flags, errors)

    archived = observation.get("archived") is True
    row["archived"] = archived
    full_name = observation.get("full_name")
    if isinstance(full_name, str) and full_name and full_name.lower() != entry["repository"].lower():
        row["renamed_to"] = full_name
        flags.add("renamed")
    row["default_branch"] = observation.get("default_branch")
    release = observation.get("latest_release")
    if isinstance(release, dict):
        row["latest_release"] = release.get("tag")

    head = observation.get("head") if isinstance(observation.get("head"), dict) else {}
    row["head_sha"], row["head_date"] = head.get("sha"), head.get("date")
    head_time = _timestamp(head.get("date"))
    if head_time is not None:
        row["days_since_head_commit"] = max((now - head_time).days, 0)
    if archived:
        row["stale"], row["stale_reason"] = True, "archived"
        flags.update(("archived", "stale"))
    elif head_time is not None:
        # hasRecentCommits: a commit counts only when its CommittedDate is after now - 90 days.
        row["stale"] = not head_time > now - timedelta(days=STALE_AFTER_DAYS)
        if row["stale"]:
            row["stale_reason"] = f"no default-branch commit in the last {STALE_AFTER_DAYS} days"
            flags.add("stale")
    if head_time is None:
        flags.add("fetch_error")
        partial = observation.get("partial_errors") or {}
        errors.append("default-branch head commit not observed"
                      + (f" ({partial['commit']})" if isinstance(partial, dict) and partial.get("commit") else ""))

    compare = observation.get("compare")
    if isinstance(compare, dict):
        status, ahead, behind = compare.get("status"), compare.get("ahead_by"), compare.get("behind_by")
        row["compare_status"] = status
        if status == "identical":
            row["commits_since_pin"] = 0
        elif status in DRIFT_STATUSES and type(ahead) is int:
            row["commits_since_pin"] = ahead
            flags.add("drifted")
        else:
            flags.add("fetch_error")
            errors.append(f"unexpected comparison (status {status!r})")
        if type(behind) is int and behind > 0:
            row["pin_commits_not_on_head"] = behind
        base_time = _timestamp(compare.get("base_date"))
        if base_time is not None:
            row["pin_date_observed"] = base_time.date().isoformat()
            if row["pin_date_observed"] != entry["pin_date"]:
                flags.add("pin_date_mismatch")
    elif observation.get("compare_error"):
        flags.add("pin_unresolved" if is_unresolvable_pin(observation["compare_error"]) else "fetch_error")
        errors.append(observation["compare_error"])
    elif head_time is not None:
        flags.add("fetch_error")
        errors.append("pin comparison not observed")
    return _finish(row, flags, errors)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_report(catalog: dict, observations: dict, now: datetime, catalog_label: str) -> dict:
    """Pure: the whole report, rows sorted by repository so the output is deterministic."""
    rows = [classify(entry, observations.get(entry["repository"]), now) for entry in catalog["references"]]
    rows.sort(key=lambda row: (row["repository"].lower(), row["repository"]))
    summary = {"references": len(rows), "fresh": sum(1 for row in rows if not row["flags"])}
    for flag in FLAGS:
        summary[flag] = sum(1 for row in rows if flag in row["flags"])
    return {
        "schema": SCHEMA,
        "catalog": catalog_label,
        "catalog_checked_at": catalog["checked_at"],
        "observed_at": _iso(now),
        "stale_after_days": STALE_AFTER_DAYS,
        "report_only": True,
        "summary": summary,
        "references": rows,
    }


def _cell(value) -> str:
    return "n/a" if value is None or value == "" else _one_line(value, 200).replace("|", "\\|")


def _notes(row: dict) -> str:
    notes = []
    if row["renamed_to"]:
        notes.append(f"now {row['renamed_to']}")
    if row["stale_reason"]:
        notes.append(row["stale_reason"])
    if row["compare_status"] in ("behind", "diverged"):
        notes.append(f"pin is not on the default branch ({row['compare_status']}, "
                     f"{row['pin_commits_not_on_head']} pin-side commits)")
    if "pin_date_mismatch" in row["flags"]:
        notes.append(f"pin committed {row['pin_date_observed']}, catalog says {row['pin_date']}")
    if row["latest_release"]:
        notes.append(f"latest release {row['latest_release']}")
    if row["error"]:
        notes.append(row["error"])
    return "; ".join(notes)


def render_markdown(report: dict) -> str:
    """Pure: the job-summary Markdown for a report."""
    summary = report["summary"]
    lines = [
        "## Practice references freshness (report-only)",
        "",
        f"`{report['catalog']}` (checked {report['catalog_checked_at']}), observed {report['observed_at']}. "
        f"Stale means archived, or no default-branch commit in the last {report['stale_after_days']} days "
        "(the OpenSSF Scorecard Maintained check's window). Drift counts default-branch commits after the pin. "
        "The report never changes a pin, and no result here fails the job.",
        "",
        ("**{references} references:** {fresh} fresh, {drifted} drifted, {stale} stale, {archived} archived, "
         "{renamed} renamed, {missing} missing, {pin_unresolved} pin unresolved, "
         "{pin_date_mismatch} pin date mismatch, {fetch_error} fetch error(s).").format(**summary),
        "",
        "| Repository | Role | Pin | Flags | Commits since pin | Default-branch head | Last commit | Notes |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in report["references"]:
        repository, pin, head = row["repository"], row["pin"], row["head_sha"]
        commits = row["commits_since_pin"]
        if commits and head:
            commits_cell = f"[{commits}](https://github.com/{repository}/compare/{pin[:12]}...{head[:12]})"
        else:
            commits_cell = _cell(commits)
        head_cell = f"`{head[:12]}` ({_cell(row['default_branch'])})" if head else "n/a"
        if row["head_date"] and row["days_since_head_commit"] is not None:
            last_cell = f"{row['head_date'][:10]} ({row['days_since_head_commit']} d ago)"
        else:
            last_cell = "n/a"
        lines.append("| " + " | ".join((
            f"[{repository}](https://github.com/{repository})", row["role"], f"`{pin[:12]}`",
            ", ".join(row["flags"]) or "fresh", commits_cell, head_cell, last_cell, _cell(_notes(row)),
        )) + " |")
    return "\n".join(lines) + "\n"


def _parse_now(value: str) -> datetime:
    moment = _timestamp(value)
    if moment is None:
        raise argparse.ArgumentTypeError(f"not an ISO-8601 time: {value!r}")
    return moment


def _catalog_label(path: Path) -> str:
    """The catalog's repository-relative path, or only its file name outside the repository,
    so the report never records a host path."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG,
                        help="Catalog to check (default: catalogs/foundation/practice-references.json).")
    parser.add_argument("--out", type=Path, help="Write the JSON report here (default: standard output).")
    parser.add_argument("--markdown", type=Path, help="Write the Markdown summary table here.")
    parser.add_argument("--observations", type=Path,
                        help="Replay recorded observations (a JSON object keyed by repository) instead of calling gh.")
    parser.add_argument("--now", type=_parse_now, default=None,
                        help="Evaluate staleness at this ISO-8601 time instead of the current UTC time.")
    parser.add_argument("--workers", type=int, default=6)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    catalog, errors = load_catalog(args.catalog)
    if errors:
        for error in errors:
            print(f"malformed catalog: {error}", file=sys.stderr)
        return 2
    now = args.now or datetime.now(timezone.utc)
    if args.observations:
        try:
            observations = json.loads(args.observations.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            print(f"--observations: not a readable JSON document ({type(exc).__name__})", file=sys.stderr)
            return 2
        if not isinstance(observations, dict):
            print("--observations: expected a JSON object keyed by repository", file=sys.stderr)
            return 2
    else:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            observed = list(pool.map(observe, catalog["references"]))
        observations = {entry["repository"]: item for entry, item in zip(catalog["references"], observed)}

    report = build_report(catalog, observations, now, _catalog_label(args.catalog))
    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_markdown(report), encoding="utf-8")
    counts = " ".join(f"{key}={value}" for key, value in report["summary"].items())
    print(f"practice references (report-only): {counts}", file=sys.stdout if args.out else sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
