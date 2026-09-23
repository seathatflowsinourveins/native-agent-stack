#!/usr/bin/env python3
"""Build the catalog-freshness drift report, and turn a detected drift into a
reviewable, report-only evidence branch: copy the artifact, write a
``scripts/validate.py``-shaped receipt, register every new file's hash, and
(only when it is still a tracked, non-build-artifact file) rebuild and rehash
the public explorer.

This module never selects, evaluates, or writes to a catalog file:
``catalogs/sota-convergence/*``, ``catalogs/landscape/*.json``,
``manifests/stack.json`` and ``layer-verdicts*`` stay owned by the separate
SOTA-convergence lane review (see ``recipes/sota-convergence-practice.md``).
It only ever adds files under ``evidence/artifacts/`` and
``evidence/receipts/``, and updates ``manifests/evidence.json``'s
registration and receipt list. It is invoked from two places in
``.github/workflows/catalog-freshness.yml``: ``build_drift_report()`` from
the ``freshness`` job's own diff step (so the drift-table header text and
the drift-vs-unfetched rule live in exactly one place, not duplicated
between YAML and Python), and ``main()``/``apply()`` from the ``propose``
job. See ``docs/decisions/2026-09-23-bot-pr-dispatch.md`` for why the
``propose`` job exists and its fix history.

Every read/write here looks up a file by its ``path`` (or a receipt by its
``id``) rather than assuming a fixed position in ``manifests/evidence.json``'s
``files[]``/``receipts[]`` lists, and every hash registration is only ever
for a file this run itself creates or a file ``git ls-files`` currently
tracks -- so this keeps working whether or not ``docs/ecosystem/index.html``
is a tracked file or an untracked build artifact, and regardless of what
order ``files[]``/``receipts[]`` entries are kept in.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

try:
    from .host_receipts import register_file
    from .catalog_decisions import safe_file, unique_json
except ImportError:  # running as a plain script, not a package
    from host_receipts import register_file
    from catalog_decisions import safe_file, unique_json


RECEIPT_KIND = "upstream_provenance"
DRIFT_TABLE_HEADER = (
    "| id | pin (published) | pin (fresh) | upstream latest (published) | "
    "upstream latest (fresh) | behind (published) | behind (fresh) |"
)
DRIFT_TABLE_SEPARATOR = "| --- | --- | --- | --- | --- | --- | --- |"
_DRIFT_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|.*\|$")
_SEPARATOR_ROW = re.compile(r"\A\|[\s:|-]+\|\Z")
EXPLORER_PATH = "docs/ecosystem/index.html"
PUBLISHED_MANIFEST_DIR = "catalogs/sota-convergence"
# Mirrors tools/sota-convergence/build_manifest.py's github_repo_slug() (kept
# independent here, the same way that module's own copy mirrors
# github_freshness.py's, so this module has no import-time dependency on a
# sibling script -- see that function's docstring).
_GITHUB_URL_RE = re.compile(r"^https?://github\.com/([^/\s]+)/([^/\s#?]+)")


class FreshnessProposeError(ValueError):
    """A drift artifact or repository state this module cannot safely act on."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def md_cell(value) -> str:
    """Render one drift-table cell as escaped inline code.

    Cell text (a pin, or an upstream release tag fetched from an external
    API) is untrusted formatting-wise: it could itself contain a backtick or
    a `|`. Backtick-wrapping, with any literal backtick/pipe escaped first,
    keeps it inert as Markdown/table syntax both in ``drift.md`` and in the
    PR body (which embeds ``drift.md`` verbatim).
    """
    text = "(none)" if value is None else str(value)
    text = text.replace("`", "'").replace("|", "\\|")
    return f"`{text}`"


def manifest_component_rows(manifest: dict) -> dict[str, dict]:
    """{component_id: row} for every foundation component and trading entry
    in a catalogs/sota-convergence manifest-*.json document."""
    rows: dict[str, dict] = {}
    for group in manifest.get("foundation", []):
        for component in group.get("components", []):
            rows[component["id"]] = component
    for group in manifest.get("trading", []):
        for entry in group.get("entries", []):
            rows[entry["id"]] = entry
    return rows


def _github_repo_slug(url) -> str | None:
    match = _GITHUB_URL_RE.match(url or "")
    if not match:
        return None
    owner, repo = match.group(1), match.group(2)
    if repo.lower().endswith(".git"):
        repo = repo[: -len(".git")]
    return f"{owner}/{repo}".lower()


def _freshness_record_has_error(repository, raw_repositories: dict) -> bool:
    """True if github-freshness.json's raw per-repo record for ``repository``
    (github-freshness.json's "repositories" field, keyed by URL, each record
    optionally carrying its own "slug") shows a fetch problem: either the
    top-level ``repos/{slug}`` call itself failed (``record["error"]``), or a
    releases/tags/commit sub-call failed and was worked around
    (``record["partial_errors"]``) -- for example a 503 on the releases
    endpoint whose fallback to the tags endpoint still populated a value.
    Matches by exact URL first, then by normalized GitHub slug, the same two
    ways ``build_manifest.py``'s own ``compute_upstream()`` resolves a
    repository to its freshness record.
    """
    if not repository or not isinstance(raw_repositories, dict):
        return False
    record = raw_repositories.get(repository)
    if record is None:
        slug = _github_repo_slug(repository)
        if slug:
            for candidate in raw_repositories.values():
                if isinstance(candidate, dict) and (candidate.get("slug") or "").lower() == slug:
                    record = candidate
                    break
    if not isinstance(record, dict):
        return False
    return bool(record.get("error")) or bool(record.get("partial_errors"))


def compute_drift(published_rows: dict, rebuilt_rows: dict, raw_repositories: dict | None = None):
    """Compare two manifest_component_rows() outputs.

    Returns ``(drifted, unfetched, no_release)``.

    - ``drifted``: ``(id, old_pin, new_pin, old_latest, new_latest,
      old_behind, new_behind)`` tuples. ``pin`` is always compared,
      regardless of whether either side's ``upstream.latest`` is known --
      a pin bump is real drift even for a repository with no GitHub
      releases or tags at all.
    - ``unfetched``: ids the fresh manifest has no reliable upstream data for this
      run (a pin change on such a row is still reported in ``drifted``, with its
      fresh upstream fields nulled, because the pin comes from the local catalogs) -- ``upstream.pushed_at`` is ``None`` (``github_freshness.py``
      never fetched that repository this run, e.g. a bounded ``--max-repos``
      run or a full fetch failure) or the raw freshness record shows a
      fetch problem for it (see ``_freshness_record_has_error``, e.g. a
      releases-endpoint error papered over by a tags-endpoint fallback).
      Their upstream comparison is excluded from ``drifted`` and ``no_release``.
    - ``no_release``: ids that *were* reliably fetched this run
      (``pushed_at`` present, no recorded fetch problem) but whose
      ``upstream.latest`` is genuinely ``None`` on both sides -- the
      repository simply has no GitHub release or tag (for example
      ``tavily-cli``, ``skills-ref``, ``poppler`` in the 2026-09-22
      manifest). Not drift, and not "unfetched" either.
    """
    drifted, unfetched, no_release = [], [], []
    for component_id, new in sorted(rebuilt_rows.items()):
        old = published_rows.get(component_id)
        if old is None:
            continue
        new_upstream = new.get("upstream") or {}
        new_latest = new_upstream.get("latest")
        old_latest = (old.get("upstream") or {}).get("latest")
        fetch_unreliable = new_upstream.get("pushed_at") is None or _freshness_record_has_error(
            new.get("repository"), raw_repositories,
        )
        # The pin comes from the local catalogs, not from upstream, so a pin change is
        # real drift whatever the fetch reliability of this run (Codex verification of
        # 7a483f7: the original skills-ref 0.1.0 -> 0.1.1 repro without pushed_at).
        if old.get("pin") != new.get("pin"):
            drifted.append((component_id, old.get("pin"), new.get("pin"),
                             old_latest, None if fetch_unreliable else new_latest,
                             old.get("pin_behind_upstream"),
                             None if fetch_unreliable else new.get("pin_behind_upstream")))
            if fetch_unreliable:
                unfetched.append(component_id)
            continue
        if fetch_unreliable:
            unfetched.append(component_id)
            continue
        if old_latest != new_latest or old.get("pin_behind_upstream") != new.get("pin_behind_upstream"):
            drifted.append((component_id, old.get("pin"), new.get("pin"),
                             old_latest, new_latest,
                             old.get("pin_behind_upstream"), new.get("pin_behind_upstream")))
        elif new_latest is None:
            no_release.append(component_id)
    return drifted, unfetched, no_release


def render_drift_markdown(published_path, rebuilt_name: str, published: dict, rebuilt: dict,
                           drifted: list, unfetched: list, no_release: list) -> str:
    lines = [
        "# Catalog freshness drift", "",
        f"Published manifest: `{published_path}` (counts: {published.get('counts')})",
        f"Rebuilt manifest: `{rebuilt_name}` (counts: {rebuilt.get('counts')})", "",
        "This diff is report-only; it changes no catalog selection.", "",
    ]
    if drifted:
        lines += [DRIFT_TABLE_HEADER, DRIFT_TABLE_SEPARATOR]
        for row in drifted:
            lines.append("| " + " | ".join(md_cell(value) for value in row) + " |")
    else:
        lines.append("No pin/upstream drift detected for components present in both manifests.")
    if unfetched:
        lines += [
            "",
            f"{len(unfetched)} component(s) have no reliable upstream data this run (an "
            "unfinished/bounded fetch, or a releases/tags/commit fetch problem for that repository) "
            "and are excluded from the drift count above:",
            "",
            ", ".join(md_cell(component_id) for component_id in sorted(unfetched)),
        ]
    if no_release:
        lines += [
            "",
            f"{len(no_release)} component(s) were fetched successfully this run but have no GitHub "
            "release or tag at all; this is not drift:",
            "",
            ", ".join(md_cell(component_id) for component_id in sorted(no_release)),
        ]
    return "\n".join(lines) + "\n"


def _load_freshness_document(work_dir: Path) -> dict:
    """Load github-freshness.json, failing closed (N2b): raises rather than
    returning an empty/zero-like default when the file is missing,
    unreadable, or not a JSON object, so a broken or absent freshness
    document can never be silently treated as "zero errors" downstream."""
    freshness_path = work_dir / "github-freshness.json"
    try:
        document = json.loads(freshness_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise FreshnessProposeError(f"could not read {freshness_path}: {error}") from error
    if not isinstance(document, dict):
        raise FreshnessProposeError(f"{freshness_path}: expected a JSON object")
    return document


def _int_field(document: dict, field: str, source_hint: str) -> int:
    value = document.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise FreshnessProposeError(f"{source_hint}: missing or invalid integer {field!r} field")
    return value


def upstream_error_count(document: dict) -> int:
    """The ``errors`` count from an already-loaded github-freshness.json
    document (see ``_load_freshness_document``). Fails closed (N2b): raises
    rather than defaulting to 0 when the field is missing or not an int."""
    return _int_field(document, "errors", "github-freshness.json")


def upstream_partial_error_count(document: dict) -> int:
    """The ``partial_errors`` count from an already-loaded
    github-freshness.json document. A nonzero count means at least one
    repository's releases/tags/commit sub-fetch failed and was worked
    around with a fallback (N2) -- ``propose``'s job condition treats this
    the same as a full fetch error: it must be 0 before a PR is opened."""
    return _int_field(document, "partial_errors", "github-freshness.json")


def build_drift_report(work_dir: Path) -> dict:
    """Rebuild ``drift.md``, ``drift-status.txt``, ``upstream-errors.txt``
    and ``upstream-partial-errors.txt`` from the newest rebuilt manifest in
    ``work_dir``, the newest published manifest in the checkout (current
    working directory), and ``work_dir``'s ``github-freshness.json``.

    Called both by ``catalog-freshness.yml``'s "Diff the rebuilt manifest"
    step (imported directly from a small inline script, not reimplemented
    there) and by this module's own tests, so the drift-table header text
    and the drift-vs-unfetched rule can never drift apart between the
    workflow and this module.
    """
    manifests = sorted(work_dir.glob("manifest-*.json"))
    if not manifests:
        raise FreshnessProposeError(f"no manifest-*.json found in {work_dir}")
    rebuilt_path = manifests[-1]
    rebuilt = json.loads(rebuilt_path.read_text(encoding="utf-8"))

    published_candidates = sorted(Path(PUBLISHED_MANIFEST_DIR).glob("manifest-*.json"))
    if not published_candidates:
        raise FreshnessProposeError(f"no manifest-*.json found in {PUBLISHED_MANIFEST_DIR}")
    published_path = published_candidates[-1]
    published = json.loads(published_path.read_text(encoding="utf-8"))

    freshness_document = _load_freshness_document(work_dir)
    raw_repositories = freshness_document.get("repositories")
    if not isinstance(raw_repositories, dict):
        raw_repositories = {}

    drifted, unfetched, no_release = compute_drift(
        manifest_component_rows(published), manifest_component_rows(rebuilt), raw_repositories,
    )
    # rebuilt_path.name only (N4): rebuilt_path lives under $RUNNER_TEMP, an
    # absolute, host-specific path that must never be written into committed
    # evidence; published_path is already a safe, relative repository path.
    markdown = render_drift_markdown(published_path, rebuilt_path.name, published, rebuilt,
                                      drifted, unfetched, no_release)
    (work_dir / "drift.md").write_text(markdown, encoding="utf-8")
    (work_dir / "drift-status.txt").write_text("true\n" if drifted else "false\n", encoding="utf-8")
    (work_dir / "upstream-errors.txt").write_text(f"{upstream_error_count(freshness_document)}\n", encoding="utf-8")
    (work_dir / "upstream-partial-errors.txt").write_text(
        f"{upstream_partial_error_count(freshness_document)}\n", encoding="utf-8",
    )
    return {
        "drifted": [row[0] for row in drifted],
        "unfetched": unfetched,
        "no_release": no_release,
        "published_path": published_path.as_posix(),
        "rebuilt_path": rebuilt_path.as_posix(),
    }


def select_receipt_component_ids(drifted_ids, known_stack_ids) -> list[str]:
    """Component ids the receipt claims coverage over: this run's actual
    drifted ids, narrowed to ones ``manifests/stack.json`` still recognizes
    (a sota-convergence catalog id is not always a stack component id).

    Raises rather than falling back to an unrelated fixed component set when
    none of the drifted ids match a known stack component: a receipt whose
    ``component_ids`` do not actually describe what drifted would be
    misleading. This is meant to be a rare condition, surfaced as a failed
    job (no branch is pushed and no PR is opened), not silently papered over
    with a fallback that names tools unrelated to the actual drift.
    """
    matched = sorted(set(drifted_ids) & set(known_stack_ids))
    if matched:
        return matched
    raise FreshnessProposeError(
        "no drifted component id matches a known manifests/stack.json component; refusing to open "
        f"a PR with component_ids unrelated to what actually drifted (drifted ids: {sorted(set(drifted_ids))!r})"
    )


def build_receipt(receipt_id: str, component_ids: list[str], drifted_component_count: int,
                   run_url: str, checked_at_utc: str) -> dict:
    """The evidence/receipts/*.json payload, shaped for scripts/validate.py's generic
    receipt rules (kind, claim, limitations, component_ids -- see scripts/validate.py's
    Validator.validate())."""
    return {
        "schema_version": 1,
        "id": receipt_id,
        "kind": RECEIPT_KIND,
        "component_ids": component_ids,
        "claim": (
            f"Scheduled catalog-freshness run ({run_url}) rebuilt the SOTA-convergence manifest and "
            f"found {drifted_component_count} component(s) with pin/upstream drift against the "
            "currently published manifest. This receipt, and the branch/PR it is registered from, are "
            "report-only: no catalogs/sota-convergence/*, catalogs/landscape/*.json, "
            "manifests/stack.json, or layer-verdicts* file was selected, evaluated, or changed by this "
            "run. A pin bump requires its own separately qualified receipt under evidence/artifacts/*/, "
            "produced by the existing SOTA-convergence lane review, not by this automation."
        ),
        "limitations": [
            "This is drift detection only: it reports that a pin or upstream 'latest' value differs "
            "from the published manifest; it does not evaluate, select, or adopt any candidate, and it "
            "changes no catalog selection file.",
            "component_ids lists only this run's drifted rows whose id is also a manifests/stack.json "
            "component; it is not a claim that every drifted id in the full drift report was reviewed.",
            "Components with no reliable upstream data this run (an unfinished/bounded fetch, or a "
            "releases/tags/commit fetch problem for that repository) are excluded from the drift count "
            "and from component_ids; they are not claimed to have been checked. A component fetched "
            "successfully but with no GitHub release or tag at all is also not counted as drift.",
            "The rebuilt manifest and drift table are read from this run's own catalog-freshness "
            "workflow artifact; this receipt does not independently re-fetch upstream sources.",
        ],
        "recorded_at_utc": checked_at_utc,
        "run_url": run_url,
        "drifted_component_count": drifted_component_count,
    }


def register_receipt(root: Path, receipt: dict, relative_path: str) -> None:
    """Upsert receipt's manifest-facing fields into manifests/evidence.json's
    receipts[], matched by id -- never by list position, since neither
    files[] nor receipts[] order is assumed stable across writers."""
    evidence_path = safe_file(root, "manifests/evidence.json")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
    entry = {
        "id": receipt["id"], "kind": receipt["kind"], "component_ids": receipt["component_ids"],
        "claim": receipt["claim"], "limitations": receipt["limitations"], "path": relative_path,
    }
    receipts = evidence.setdefault("receipts", [])
    for index, existing in enumerate(receipts):
        if isinstance(existing, dict) and existing.get("id") == entry["id"]:
            receipts[index] = entry
            break
    else:
        receipts.append(entry)
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


def is_git_tracked(root: Path, relative_path: str) -> bool:
    """True only if ``git ls-files`` currently tracks ``relative_path``.

    Used to gate the explorer rehash so this stays correct both before and
    after ``docs/ecosystem/index.html`` becomes an untracked build artifact;
    never assumes either state.
    """
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), "ls-files", "--error-unmatch", "--", relative_path],
        capture_output=True, text=True, timeout=10, check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == relative_path


def refuse_if_symlink(path: Path) -> None:
    """Raise rather than let shutil.copyfile/write_text follow an existing
    symlink at a destination this module is about to (over)write. Without
    this, a pre-existing symlink planted at, e.g.,
    evidence/artifacts/catalog-freshness-<date>/drift.md would cause the
    copy to silently write through it to wherever it points."""
    if path.is_symlink():
        raise FreshnessProposeError(f"refusing to write through an existing symlink: {path}")


def safe_file_placeholder(root: Path, relative: str) -> Path:
    """Like catalog_decisions.safe_file, but for a path that may not exist yet
    (safe_file requires the final component to already be a file); used for a
    destination this module is about to create."""
    parts = PurePosixPath(relative)
    if parts.is_absolute() or str(parts) != relative or any(part in {".", "..", ".git"} for part in parts.parts):
        raise FreshnessProposeError(f"unsafe destination directory: {relative!r}")
    path = root
    for part in parts.parts:
        path = path / part
        if path.is_symlink():
            raise FreshnessProposeError(f"destination path traverses a symlink: {relative!r}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise FreshnessProposeError(f"destination path escapes the repository: {relative!r}")
    return path


def copy_artifact(root: Path, artifact_dir: Path, date_stamp: str) -> tuple[str, str]:
    """Copy the freshness job's drift.md and its newest manifest-*.json into
    evidence/artifacts/catalog-freshness-<date_stamp>/, returning their two
    repository-relative paths (drift, manifest)."""
    manifests = sorted(artifact_dir.glob("manifest-*.json"))
    if not manifests:
        raise FreshnessProposeError(f"no manifest-*.json found in {artifact_dir}")
    drift_source = artifact_dir / "drift.md"
    if not drift_source.is_file():
        raise FreshnessProposeError(f"drift.md not found in {artifact_dir}")
    destination_dir = safe_file_placeholder(root, f"evidence/artifacts/catalog-freshness-{date_stamp}")
    destination_dir.mkdir(parents=True, exist_ok=True)
    drift_dest = destination_dir / "drift.md"
    manifest_dest = destination_dir / manifests[-1].name
    refuse_if_symlink(drift_dest)
    refuse_if_symlink(manifest_dest)
    shutil.copyfile(drift_source, drift_dest)
    shutil.copyfile(manifests[-1], manifest_dest)
    return (
        drift_dest.resolve().relative_to(root.resolve()).as_posix(),
        manifest_dest.resolve().relative_to(root.resolve()).as_posix(),
    )


def rebuild_explorer(root: Path, attempts: int = 3) -> None:
    """Rebuild docs/ecosystem/index.html and converge its registered hash.

    Both the ``--write`` and ``--check`` subprocess calls run with
    ``capture_output=True``: scripts/build_ecosystem.py prints a one-line
    JSON summary to stdout, and letting that inherit this process's stdout
    would land inside the same stream a caller (main(), and the ``propose``
    job's `tee`) treats as this module's own single-JSON-document output --
    a second JSON document on the same stream makes `json.load` fail with
    "Extra data". Diagnostic output is not discarded: it is folded into the
    raised error's message if ``--check`` never converges.

    Registering the explorer's own hash only touches manifests/evidence.json's
    files[] entry, which scripts/build_ecosystem.py's EVIDENCE input-tracking
    explicitly excludes from the explorer's rendered content (only
    evidence.json's receipts[] feeds its output -- see build_data()'s
    "avoids generated-file self-reference" comment), so a single --write +
    register + --check pass should already converge; the retry bound is a
    safety margin, not evidence that more than one pass is ever needed.
    """
    last_output = ""
    for _ in range(attempts):
        subprocess.run(
            ["python3", "scripts/build_ecosystem.py", "--write"],
            cwd=root, check=True, capture_output=True, text=True,
        )
        register_file(root, EXPLORER_PATH)
        check = subprocess.run(
            ["python3", "scripts/build_ecosystem.py", "--check"],
            cwd=root, check=False, capture_output=True, text=True,
        )
        if check.returncode == 0:
            return
        last_output = (check.stdout or "") + (check.stderr or "")
    raise FreshnessProposeError(
        f"scripts/build_ecosystem.py --check did not converge after {attempts} attempt(s): "
        f"{last_output[-2000:]}"
    )


def apply(root: Path, artifact_dir: Path, run_url: str, checked_at_utc: str | None = None) -> dict:
    """Build the artifact copy, receipt and registration for one catalog-freshness run.

    Returns a small JSON-serializable summary the calling workflow step reads
    (receipt path, artifact paths, resolved component_ids, and whether the
    explorer was rehashed).
    """
    checked_at_utc = checked_at_utc or utc_now()
    date_stamp = checked_at_utc[:10].replace("-", "")
    if not re.fullmatch(r"[0-9]{8}", date_stamp):
        raise FreshnessProposeError(f"checked_at_utc must start with an ISO date: {checked_at_utc!r}")

    drift_text = (artifact_dir / "drift.md").read_text(encoding="utf-8")
    drifted_ids = drifted_component_ids(drift_text)

    stack = json.loads(
        safe_file(root, "manifests/stack.json").read_text(encoding="utf-8"), object_pairs_hook=unique_json,
    )
    known_stack_ids = {
        component["id"] for component in stack.get("components", [])
        if isinstance(component, dict) and isinstance(component.get("id"), str)
    }
    component_ids = select_receipt_component_ids(drifted_ids, known_stack_ids)

    drift_relative, manifest_relative = copy_artifact(root, artifact_dir, date_stamp)

    receipt_id = f"catalog-freshness-{date_stamp}"
    receipt_relative = f"evidence/receipts/{receipt_id}.json"
    receipt = build_receipt(receipt_id, component_ids, len(drifted_ids), run_url, checked_at_utc)
    receipt_path = safe_file_placeholder(root, receipt_relative)
    refuse_if_symlink(receipt_path)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    # Register only files this job itself just created, or a file `git ls-files`
    # already tracks (the explorer rehash below) -- never a path assumed present.
    for relative in (drift_relative, manifest_relative, receipt_relative):
        register_file(root, relative)
    register_receipt(root, receipt, receipt_relative)

    rehashed_explorer = False
    if is_git_tracked(root, EXPLORER_PATH):
        rebuild_explorer(root)
        rehashed_explorer = True

    return {
        "receipt_id": receipt_id,
        "receipt_path": receipt_relative,
        "artifact_paths": [drift_relative, manifest_relative],
        "component_ids": component_ids,
        "drifted_component_count": len(drifted_ids),
        "rehashed_explorer": rehashed_explorer,
    }


def drifted_component_ids(drift_md_text: str) -> list[str]:
    """Parse the DRIFT_TABLE_HEADER-led drift-table body rows written by
    build_drift_report()/render_drift_markdown().

    Returns a sorted, de-duplicated list of ids, or ``[]`` when the report
    found no drift (its "No pin/upstream drift detected ..." sentence has no
    table at all). Detects the header via DRIFT_TABLE_HEADER -- the exact
    same constant render_drift_markdown() writes -- so this can never drift
    out of sync with the text the workflow's own diff step produces.
    """
    ids: set[str] = set()
    in_table = False
    for line in drift_md_text.splitlines():
        stripped = line.strip()
        if not in_table:
            if stripped == DRIFT_TABLE_HEADER:
                in_table = True
            continue
        if not stripped.startswith("|"):
            break
        if _SEPARATOR_ROW.match(stripped):
            continue
        match = _DRIFT_ROW.match(stripped)
        if match:
            ids.add(match.group(1).strip().strip("`"))
    return sorted(ids)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--artifact-dir", type=Path, required=True,
                         help="Directory holding the downloaded catalog-freshness artifact "
                              "(drift.md and manifest-*.json).")
    parser.add_argument("--run-url", required=True,
                         help="The catalog-freshness run's own URL, recorded in the receipt's claim.")
    parser.add_argument("--checked-at-utc", default=None,
                         help="ISO-8601 UTC timestamp; defaults to now. Also fixes the date stamp used "
                              "in the receipt id and evidence directory name.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Prints exactly one JSON document to stdout (the apply() result) and
    nothing else -- callers (the `propose` job's `tee`, and this module's own
    subprocess tests) rely on that single-document contract. Any diagnostic
    output from a called subprocess (see rebuild_explorer()) is captured, not
    inherited, so it can never land on this process's stdout."""
    args = build_parser().parse_args(argv)
    result = apply(args.root.resolve(), args.artifact_dir.resolve(), args.run_url, args.checked_at_utc)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
