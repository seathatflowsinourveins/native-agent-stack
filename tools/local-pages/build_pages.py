#!/usr/bin/env python3
"""Compose local pages from the native readiness API and CC snapshot schemas.

Reference: tools/north-star/build_readiness.py (build, render, render_fragment),
and the retained CC gaps/roadmap JSON schemas. This presents source records;
it does not decide gate acceptance or run the CC's source publishers.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ASSETS = Path(__file__).resolve().parent / "assets"
SOURCE_POLICY_PATH = Path(__file__).resolve().parent / "source_policy.json"
MAX_BYTES = 8 * 1024 * 1024
DATE_KEYS = ("as_of_utc", "updated_utc", "generated_utc", "generated_at",
             "checked_at", "recorded_utc", "captured_at", "captured_utc")
TEMPLATE = re.compile(r"\$?\{[A-Za-z_][A-Za-z0-9_]*\}")
PORTABLE_PLACEHOLDERS = {"${USER_HOME}", "${LOCAL_SESSION_ID}", "${LOCAL_TASK_HANDLE}"}
ROAD_REFERENCE_FILES = {
    "board_base": ("coordination/ns2604-coop/readiness-20261005/jobs/BOARD-CLOSE-20261007T190934Z/board-close-20261007T193821Z.json",),
    "board_ruled": (), "handbook": (), "lane_live": (), "triage_owner": (),
    "manifest": (), "token_window": (), "stack_effect": (), "versions": (), "pr_counts": (),
    "css_from": ("coordination/command-center/cc-tools/invoke-evidence/build_page.py",),
}
_SANITIZER = None
PAGES = {"index": "Home", "readiness": "Readiness", "gaps": "Gap board", "roadmap": "Roadmap", "fleet": "Fleet", "sources": "Sources"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def no_symlinks(path: Path) -> Path:
    """Check lexical components before resolve() hides a symlink."""
    absolute = path if path.is_absolute() else Path.cwd() / path
    for candidate in (absolute, *absolute.parents):
        if candidate.is_symlink():
            raise ValueError(f"symlink path is not a page source or destination: {candidate}")
    return Path(os.path.abspath(absolute))


def snapshot(path: Path) -> dict[str, Any]:
    path = no_symlinks(path)
    with path.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
        stat = os.fstat(handle.fileno())
    if len(raw) > MAX_BYTES:
        raise ValueError(f"input exceeds {MAX_BYTES} bytes: {path}")
    return {"path": str(path), "raw": raw, "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw), "file_modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}


def strict_json(raw: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def constant(value: str) -> Any:
        raise ValueError(f"non-JSON constant: {value}")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def dates(document: Any) -> dict[str, str]:
    if not isinstance(document, dict):
        return {}
    return {key: document[key] for key in DATE_KEYS if isinstance(document.get(key), str)}


def display(value: Any) -> str:
    text = sanitizer().text(value)
    return TEMPLATE.sub(lambda match: match.group() if match.group() in PORTABLE_PLACEHOLDERS else "[source template omitted]", text)


def source_templates(value: Any) -> Any:
    """Omit unapproved source placeholders before native HTML rendering."""
    if isinstance(value, str):
        return TEMPLATE.sub(lambda match: match.group() if match.group() in PORTABLE_PLACEHOLDERS else "[source template omitted]", value)
    if isinstance(value, dict):
        return {key: source_templates(child) for key, child in value.items()}
    if isinstance(value, list):
        return [source_templates(child) for child in value]
    return value


def sanitizer() -> Any:
    global _SANITIZER
    if _SANITIZER is None:
        _SANITIZER = load_local("sanitization")
    return _SANITIZER


def event_time(value: Any) -> str:
    text = display(value)
    try:
        return load_local("current_view").time_label(text)
    except (ValueError, TypeError):
        return esc(text)


def esc(value: Any) -> str:
    return html.escape(display(value), quote=True)


def fact(value: Any) -> str:
    if isinstance(value, dict) and "value" in value:
        return display(value["value"]) if value.get("status") == "RECORDED" else "UNVERIFIED"
    return display(value)


def label_path(path: str, root: Path, state_root: Path) -> str:
    for prefix, base in (("repo", root), ("state", state_root)):
        if Path(path).is_relative_to(base):
            return prefix + ":" + Path(path).relative_to(base).as_posix()
    return Path(path).name


def source_scope(item: dict[str, Any], document: dict[str, Any], *, detail: bool = False) -> str:
    fields = dates(document)
    if detail:
        return "; ".join(f"{key} = {value}" for key, value in fields.items()) if fields else "Source-owned snapshot date unspecified. File modified " + item["file_modified_utc"] + " (file metadata, not event or acceptance time)."
    if fields:
        return "Source-owned snapshot as of " + next(iter(fields.values())) + "; per-input date details are listed on Sources."
    return "Source-owned snapshot date unspecified; file metadata is listed on Sources."


def document(page: str, title: str, lede: str, scope: str, body: str,
             refreshed: str, manifest_sha: str, source_notes: list[str], leading: str | None = None) -> bytes:
    nav = "".join(f'<a href="{name}.html"' + (' aria-current="page"' if name == page else '') + f'>{text}</a>' for name, text in PAGES.items())
    heading = leading if leading is not None else f'<header class="page-header"><h1>{esc(title)}</h1><p class="lede">{esc(lede)}</p></header>'
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <meta name="theme-color" content="#f6f8fb">
  <title>{esc(title)} · Native engineering desk</title>
  <link rel="stylesheet" href="assets/site.css">
  <script src="assets/site.js" defer></script>
</head>
<body data-page="{page}">
<a class="skip-link" href="#main-content">Skip to content</a>
<div class="site-shell">
<header class="site-header">
  <a class="brand" href="index.html">Native engineering desk</a>
  <nav class="site-nav" aria-label="Local pages">{nav}</nav>
  <label class="theme-picker" for="theme-toggle"><span>Theme</span>
    <select class="theme-toggle" id="theme-toggle" name="theme" autocomplete="off"><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select>
  </label>
</header>
<main id="main-content">
  {heading}
  {body}
</main>
<footer class="site-footer"><p><a href="sources.html#{page}">Sources and dates for this page</a></p>
  <div class="snapshot-note"><p><strong>Source as of:</strong> {esc(scope)}</p>
    <p><strong>Page refreshed:</strong> <time datetime="{esc(refreshed)}">{esc(refreshed)}</time></p>
    <p><strong>Native readiness manifest SHA-256:</strong> <code>{manifest_sha}</code></p>
  </div>
  <p class="evidence-footnote">Current views and dated receipts retain their source scope; this page does not establish new execution, approval or landing.</p>
</footer>
</div>
</body>
</html>
'''.encode("utf-8")


def rows(document: dict[str, Any], key: str, required: tuple[str, ...] = ()) -> list[Any]:
    result = document.get(key, [])
    if not isinstance(result, list):
        raise ValueError(f"{key} must be an array")
    for row in result:
        if required and (not isinstance(row, dict) or any(field not in row for field in required)):
            raise ValueError(f"{key} row lacks required fields: {', '.join(required)}")
    return result


def gap_body(gaps: list[dict[str, Any]]) -> str:
    counts = Counter(display(row["sev"]).strip().casefold() for row in gaps)
    summary = '<div class="metric-grid" aria-label="Source row counts">' + f'<p><strong>{len(gaps)}</strong> source rows</p>' + "".join(f'<p><strong>{count}</strong> {esc(severity)}</p>' for severity, count in sorted(counts.items())) + '</div>'
    def options(field: str) -> str:
        values = sorted({display(row[field]).strip() for row in gaps}, key=str.casefold)
        return '<option value="all">All</option>' + "".join(f'<option value="{esc(value.casefold())}">{esc(value)}</option>' for value in values)
    controls = f'''<div class="gap-controls" role="search">
<div><label for="gap-search">Search gaps</label><input id="gap-search" name="q" type="search" autocomplete="off" placeholder="Search title, state or evidence, e.g. monitoring…"></div>
<div><label for="gap-group">Group</label><select id="gap-group" name="group" autocomplete="off">{options("group")}</select></div>
<div><label for="gap-severity">Severity</label><select id="gap-severity" name="severity" autocomplete="off">{options("sev")}</select></div>
<div><button id="gap-reset" type="button">Reset filters</button></div>
</div><p id="gap-result-count" role="status" aria-live="polite">{len(gaps)} of {len(gaps)} gaps shown</p>'''
    cards = []
    seen: set[str] = set()
    for row in gaps:
        identity = display(row["id"])
        if identity in seen:
            raise ValueError(f"duplicate gap identity: {identity}")
        seen.add(identity)
        search = " ".join(display(row.get(key, "")) for key in ("id", "group", "sev", "title", "state", "owner", "next", "due", "evidence")).casefold()
        details = "".join(f'<div><dt>{name}</dt><dd>{event_time(row.get(key)) if key == "due" else esc(row.get(key))}</dd></div>' for key, name in (("owner", "Operational owner"), ("next", "Next action"), ("due", "Source-listed due date"), ("evidence", "Evidence pointer")))
        cards.append(f'<article class="gap-card" data-search="{esc(search)}" data-group="{esc(display(row["group"]).strip().casefold())}" data-severity="{esc(display(row["sev"]).strip().casefold())}"><div class="gap-meta"><span>{esc(identity)}</span><span>{esc(row["group"])}</span><span class="severity">{esc(row["sev"])}</span></div><h2>{esc(row["title"])}</h2><p class="gap-state">{esc(row.get("state"))}</p><dl class="gap-details">{details}</dl></article>')
    return summary + controls + '<div id="gap-register">' + "\n".join(cards) + '</div><p id="gap-empty" hidden>No source rows match these filters. Clear the search or choose All.</p>'


def roadmap_body(status: dict[str, Any]) -> str:
    milestones = rows(status, "milestones", ("what", "state"))
    # Custodian build_roadmap.py:284 uses a truthy at, otherwise its when label.
    for row in milestones:
        if not row.get("at") and "when" not in row:
            raise ValueError("milestone must provide at or when source timing")
    servers = rows(status, "servers", ("key", "label", "job", "paired", "verdict", "next"))
    events = "".join(f'<li class="milestone"><span class="milestone-time">{event_time(row["at"]) if row.get("at") else esc(row["when"])}</span><div><h3 class="milestone-title">{esc(row["what"])}</h3><p class="milestone-state">{esc(row["state"])}</p></div></li>' for row in milestones)
    server_rows = "".join('<tr>' + "".join(f'<td>{esc(row[key])}</td>' for key in ("label", "job", "paired", "verdict", "next")) + '</tr>' for row in servers)
    ladder = rows(status, "ladder")
    if any(not isinstance(item, str) for item in ladder):
        raise ValueError("ladder entries must be source text")
    sequence = "".join(f'<li>{esc(item.replace("**", ""))}</li>' for item in ladder)
    return f'''<div class="metric-grid" aria-label="Source row counts"><p><strong>{len(milestones)}</strong> milestones</p><p><strong>{len(servers)}</strong> server records</p></div>
<section class="panel"><div class="section-header"><h2>Milestones</h2></div><ol class="milestone-rail">{events}</ol></section>
<section class="panel"><div class="section-header"><h2>Server records</h2></div><div class="table-wrap"><table><thead><tr><th>Server</th><th>Role</th><th>Paired client evidence</th><th>Source verdict</th><th>Next action</th></tr></thead><tbody>{server_rows}</tbody></table></div></section>
<section class="panel"><div class="section-header"><h2>Recorded finalization sequence</h2></div><ol class="source-sequence">{sequence}</ol></section>'''


def readiness_body(native: Any, manifest: dict[str, Any], current: dict[str, Any], view: Any, *, source_dates: dict | None = None) -> str:
    cards = []
    for row in manifest["gates"]:
        state = fact(row["fields"].get("state"))
        field = row["fields"].get("state") or {}
        receipt = field.get("receipt") or {}
        known_dates = (source_dates or {}).get((receipt.get("root"), receipt.get("path")), {})
        timestamp = next((known_dates[key] for key in DATE_KEYS if key in known_dates), None)
        superseded = '<p class="superseded-note">superseded in the current view</p>' if view.superseded(row["id"], state, current, source_utc=timestamp, source_status=field.get("status", "UNVERIFIED")) else ''
        if not superseded and field.get("status") == "RECORDED" and view.differs(row["id"], state, current):
            superseded = '<p class="superseded-note">differs from the current view</p>'
        cards.append(f'<article class="gate-card" data-manifest-gate="{esc(row["id"])}"><h3>{esc(row["id"])}</h3><p class="gate-state">{esc(state)}</p>{superseded}<p>Operational owner: {esc(fact(row["fields"].get("owner")))}</p></article>')
    gates = "".join(cards)
    fragment = native.render_fragment(source_templates(manifest))
    fragment = fragment.replace('<table>', '<div class="table-wrap"><table>').replace('</table>', '</table></div>')
    summary = manifest["summary"]
    counts = "".join(f'<p><strong>{int(summary[key])}</strong> {title}</p>' for key, title in (("recorded_claims", "recorded claims"), ("unverified_claims", "unverified claims"), ("unverified_sources", "unverified sources")))
    return f'<div class="metric-grid" aria-label="Native manifest counts">{counts}</div><div class="readiness-content"><div class="wrap"><aside class="gates"><div class="section-header"><h2>Gate receipts</h2></div><div class="gate-grid">{gates}</div></aside><div class="panel">{fragment}</div></div></div>'


def load_native(root: Path) -> tuple[Any, dict[str, Any]]:
    path = root / "tools/north-star/build_readiness.py"
    item = snapshot(path)
    spec = importlib.util.spec_from_file_location("local_pages_native_readiness", path)
    if spec is None or spec.loader is None:
        raise ValueError("native readiness module is unavailable")
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    return native, item


def load_local(name: str) -> Any:
    path = Path(__file__).resolve().parent / (name + ".py")
    spec = importlib.util.spec_from_file_location("local_pages_" + name, path)
    if spec is None or spec.loader is None:
        raise ValueError("local presentation module is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def collect_workstation(fallback: dict[str, Any]) -> dict[str, Any]:
    return load_local("workstation").collect(fallback, wsl_job="workstation-node")


def collect_fleet(state_root: Path, cache_dir: Path, root: Path) -> dict[str, Any]:
    return load_local("fleet_data").collect(state_root, cache_dir, root)


def refresh(root: Path, state_root: Path, output_dir: Path, receipt: Path,
            sources: Path = Path("tools/north-star/sources.json"),
            gaps_source: Path | None = None, roadmap_source: Path | None = None,
            roadmap_inputs: Path | None = None, refreshed: str | None = None,
            current_source: Path | None = None) -> dict[str, Any]:
    root, state_root = no_symlinks(root), no_symlinks(state_root)
    output_dir, receipt = no_symlinks(output_dir), no_symlinks(receipt)
    if receipt.is_relative_to(output_dir):
        raise ValueError("refresh receipt must be outside the served root")
    refreshed = refreshed or utc_now()
    cc_tools = state_root / "coordination/command-center/cc-tools"
    sources = sources if sources.is_absolute() else root / sources
    if not no_symlinks(sources).is_relative_to(root):
        raise ValueError("native source index must remain inside the source repository")
    inputs: dict[str, dict[str, Any]] = {}
    def capture(name: str, path: Path) -> dict[str, Any]:
        if no_symlinks(path).is_relative_to(output_dir):
            raise ValueError("input is inside the served root")
        item = snapshot(path)
        inputs[name] = item
        return item
    def override_path(value: Path | None, default: Path, role: str | None = None) -> Path:
        path = no_symlinks(value if value is not None else default)
        if not any(path.is_relative_to(base) for base in (root, state_root)):
            raise ValueError("source override escapes the selected source roots")
        if path.is_relative_to(output_dir):
            raise ValueError("source override is inside the served root")
        if role is not None:
            policy.validate_override(role, path, root, state_root)
        return path
    sources = override_path(sources, root / "tools/north-star/sources.json")
    policy_module = load_local("source_policy")
    policy = policy_module.load_policy(SOURCE_POLICY_PATH)
    policy.validate_index_path(root, state_root, sources)
    override_inputs = {
        "gaps": override_path(gaps_source, cc_tools / "gaps/gaps.json", "gaps_source"),
        "roadmap": override_path(roadmap_source, cc_tools / "roadmap/roadmap-status.json", "roadmap_source"),
        "roadmap_inputs": override_path(roadmap_inputs, cc_tools / "roadmap/roadmap-inputs.json", "roadmap_inputs"),
        "cc_now": override_path(current_source, state_root / "coordination/command-center/pages/cc-now.json", "current_source"),
    }
    inputs["source_policy"] = dict(policy.receipt)
    capture("module:source_policy", Path(__file__).resolve().parent / "source_policy.py")
    index = capture("native_source_index", sources)
    source_spec = strict_json(index["raw"])
    if not isinstance(source_spec, dict) or not isinstance(source_spec.get("sources"), dict):
        raise ValueError("native source index must contain a sources object")
    policy.validate_sources(source_spec)
    for entry in source_spec.get("sources", {}).values():
        base = {"repo": root, "state": state_root}[entry["root"]]
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("native source path is not confined")
        path = no_symlinks(base / relative)
        if path.is_relative_to(output_dir):
            raise ValueError("native input is inside the served root")
    native, native_input = load_native(root)
    if Path(native_input["path"]).is_relative_to(output_dir):
        raise ValueError("native builder is inside the served root")
    inputs["native_builder"] = native_input
    with policy_module.guard_native(native, root, state_root, sources, policy_path=SOURCE_POLICY_PATH):
        raw_manifest = native.build(root, state_root, sources)
    manifest_bytes = native.render(raw_manifest)
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = sanitizer().sanitize(strict_json(manifest_bytes))
    if manifest["source_index"]["sha256"] != index["sha256"]:
        raise ValueError("native source index changed during refresh")
    readiness_notes = []
    for name, record in raw_manifest["receipts"].items():
        path = {"repo": root, "state": state_root}[record["root"]] / record["path"]
        no_symlinks(path)
        fields = {}
        if record["sha256"] is not None:
            item = capture("readiness:" + name, path)
            if item["sha256"] != record["sha256"]:
                raise ValueError(f"native receipt changed during refresh: {name}")
            try:
                fields = dates(strict_json(item["raw"]))
            except (ValueError, UnicodeError):
                pass
            item["source_dates"] = fields
        else:
            inputs["readiness:" + name] = {"path": str(path), "sha256": None, "status": "UNVERIFIED"}
        timestamp = "; ".join(f"{key} = {value}" for key, value in fields.items()) or "Source-owned snapshot date unspecified"
        readiness_notes.append(f'<code>{esc(record["root"] + ":" + record["path"])}</code> — {esc(record["status"])}; {esc(timestamp)}')
    gap_input = capture("gaps", override_inputs["gaps"])
    road_input = capture("roadmap", override_inputs["roadmap"])
    road_index = capture("roadmap_inputs", override_inputs["roadmap_inputs"])
    current_input = capture("cc_now", override_inputs["cc_now"])
    current = strict_json(current_input["raw"])
    view = load_local("current_view")
    view.validate(current)
    for name in ("current_view", "workstation", "sanitization", "fleet_data", "fleet_view", "adoption_view"):
        capture("module:" + name, Path(__file__).resolve().parent / (name + ".py"))
    workstation = collect_workstation(current["workstation"])
    fleet_cache = no_symlinks(receipt.parent / "fleet/cache")
    if fleet_cache.is_relative_to(output_dir):
        raise ValueError("fleet cache must remain outside the served root")
    try:
        fleet = collect_fleet(state_root, fleet_cache, root)
    except (OSError, ValueError, UnicodeError, KeyError, TypeError, AttributeError, OverflowError, RecursionError) as error:
        # An unavailable optional adapter must not prevent the other documents
        # from publishing. Error categories are public; exception text is not.
        fleet = {"fleet_source": "not reported", "at": None,
                 "lanes_live": None, "lanes_parked": None, "claude_sessions": None,
                 "pool_accounts": None, "claude_subagents_running": {},
                 "exec_reads_in_flight": None, "sdk": {}, "actions": {},
                 "availability": {name: {"status": "UNKNOWN", "source": "Fleet adapter",
                                           "reason": "adapter failed (" + type(error).__name__ + ")"}
                                  for name in ("lanes_live", "lanes_parked", "claude_sessions", "pool_accounts")},
                 "source_inputs": [], "errors": [{"type": type(error).__name__}]}
    fleet_view = load_local("fleet_view")
    adoption_view = load_local("adoption_view")
    adoption_path = state_root / "coordination/command-center/pages/adoption-now.json"
    try:
        adoption_input = capture("adoption", adoption_path)
        adoption = strict_json(adoption_input["raw"])
        adoption_view.validate(adoption)
    except (OSError, ValueError, UnicodeError, KeyError, TypeError, AttributeError) as error:
        adoption_input = inputs.get("adoption") or {"path": str(adoption_path), "sha256": None, "status": "UNREPORTED"}
        adoption_input["status"] = "UNREPORTED"
        adoption_input["reason"] = "published Adoption snapshot is unavailable or malformed (" + type(error).__name__ + ")"
        inputs["adoption"] = adoption_input
        adoption = {"schema": "adoption-now/1", "status": "UNREPORTED", "reason": adoption_input["reason"], "generated_utc": None, "window_hours": None, "layers": None, "claude_by_role": None, "codex_by_lane": None, "claude_total_sessions": None, "codex_total_conversations": None}
    gaps, roadmap, road_links = (strict_json(item["raw"]) for item in (gap_input, road_input, road_index))
    if any(not isinstance(item, dict) for item in (gaps, roadmap, road_links)):
        raise ValueError("CC page source must be a JSON object")
    for key, permitted in ROAD_REFERENCE_FILES.items():
        if key not in road_links:
            continue
        if not isinstance(road_links[key], str):
            inputs["roadmap:" + key] = {"path": str(road_index["path"]) + "#/" + key, "sha256": None, "status": "OMITTED", "reason": "reference path is not a supported string"}
            continue
        path = Path(road_links[key])
        path = path if path.is_absolute() else state_root / path
        if path not in {state_root / relative for relative in permitted}:
            inputs["roadmap:" + key] = {"path": str(road_index["path"]) + "#/" + key, "sha256": None, "status": "OMITTED", "reason": "reference path is not allowlisted for this key"}
            continue
        path = no_symlinks(path)
        if not any(path.is_relative_to(base) for base in (root, state_root)):
            raise ValueError(f"roadmap reference escapes the source roots: {key}")
        if path.is_relative_to(output_dir):
            raise ValueError("roadmap reference is inside the served root")
        try:
            item = capture("roadmap:" + key, path)
        except FileNotFoundError:
            inputs["roadmap:" + key] = {"path": str(path), "sha256": None, "status": "UNAVAILABLE"}
            continue
        if path.suffix == ".json":
            try:
                item["source_dates"] = dates(strict_json(item["raw"]))
            except (ValueError, UnicodeError):
                pass
    gap_scope = source_scope(gap_input, gaps)
    road_scope = source_scope(road_input, roadmap)
    gap_notes = [f'<code>{esc(label_path(gap_input["path"], root, state_root))}</code> — {esc(source_scope(gap_input, gaps, detail=True))}', "Counts describe rows and severity labels in this gap snapshot. Due dates are source-listed deadlines."]
    road_notes = [f'<code>{esc(label_path(road_input["path"], root, state_root))}</code> — {esc(source_scope(road_input, roadmap, detail=True))}', f'<code>{esc(label_path(road_index["path"], root, state_root))}</code> — retained input bindings; hashes remain in the nonserved receipt.', "Milestone dates are event dates. No single roadmap snapshot date was inferred from them."]
    for name, item in inputs.items():
        if name.startswith("roadmap:"):
            description = "; ".join(f"{key} = {value}" for key, value in item.get("source_dates", {}).items()) or item.get("status") or "source date unspecified"
            road_notes.append('<code>' + esc(label_path(item["path"], root, state_root)) + '</code> — ' + esc(description))
    overview = '<section class="panel"><h2>Choose a page</h2><ul class="page-index"><li><a href="readiness.html">North-star readiness</a><p>What is done, what is left and what needs a decision.</p></li><li><a href="gaps.html">Grand Gap Board</a><p>Find open gaps and their next actions.</p></li><li><a href="roadmap.html">Roadmap</a><p>Read the dated milestones and server records.</p></li><li><a href="fleet.html">Worker fleet</a><p>See the lanes, sessions, jobs and spend.</p></li><li><a href="sources.html">Sources</a><p>Check input dates, hashes and evidence scope.</p></li></ul></section>'
    current_scope = 'command-center current view snapshot; ' + view.observation_time(current["updated_utc"], plain=True)
    current_notes = [f'<code>{esc(label_path(current_input["path"], root, state_root))}</code> — {esc(current_scope)}; SHA-256 <code>{current_input["sha256"]}</code>', 'Workstation readings use an exact Prometheus metric when present, otherwise the CC-owned value and its recorded read time.']
    fleet_notes = [f'<code>{esc(key)}</code> — {esc(value or "not reported")}' for key, value in fleet.get("source_times", {}).items()]
    fleet_notes += ['Native source: <code>coordination/ns2604-coop/tools/fleet_block.py --json --no-gh</code>; direct fleet values use the snapshot only as fallback. Co-op subagents always retain their separate snapshot time.', 'Read-only inputs: <code>coordination/ns2604-coop/watchers/fleet-now.json</code>, <code>command-center/pages/cc-now.json</code>, <code>command-center/lane-tiers.json</code>, <code>coordination/api-actions-20261008/api-actions-ledger.jsonl</code>.', 'Actions use one bounded native <code>gh run list</code> invocation through a ten-minute nonserved cache; the retained newest-run scope is shown on the Fleet page. Unknown jobs, CLI observations and ceiling are not converted to zero.']
    fleet_policy = fleet.get("tiers", {})
    fast_exceptions = fleet_policy.get("fast")
    fast_policy_text = ', '.join(fast_exceptions) or "0 declared exceptions" if isinstance(fast_exceptions, list) else "UNKNOWN"
    fleet_notes.append('Tier policy: default ' + esc(fleet_policy.get("default") or "UNKNOWN") + '; fast exceptions ' + esc(fast_policy_text) + '. Live lane tiers remain the observed values from the direct fleet source.')
    fleet_notes.append('Parking keep-alive exceptions: ' + esc(', '.join(fleet_policy.get("parking", {}).get("keep_alive") or []) or "not reported") + '. Thresholds and policy time remain source-bound.')
    sdk_policy = fleet.get("sdk", {})
    fleet_notes.append('Spend ceiling source: ' + esc(sdk_policy.get("ceiling_source") or "not reported") + '; read ' + esc(sdk_policy.get("ceiling_read_utc") or "not reported") + '. Planned table amounts: expected USD ' + esc(sdk_policy.get("table_expected_usd") if sdk_policy.get("table_expected_usd") is not None else "not reported") + '; at caps USD ' + esc(sdk_policy.get("table_at_caps_usd") if sdk_policy.get("table_at_caps_usd") is not None else "not reported") + '. These are estimates, separate from the native ledger actual-cost sum.')
    for lane, deadline in fleet_policy.get("versions", {}).get("hold_until", {}).items():
        fleet_notes.append('Version hold for ' + esc(lane) + ': ' + esc(deadline))
    adoption_note = f'<code>{esc(label_path(adoption_input["path"], root, state_root))}</code> — adoption-now/1; generated {esc(adoption["generated_utc"])}; window {esc(adoption["window_hours"])} hours; SHA-256 <code>{esc(adoption_input["sha256"])}</code>. The co-op owns the hourly collector; pages read its published snapshot.'
    if adoption.get("status") == "UNREPORTED":
        adoption_note = '<code>' + esc(label_path(adoption_input["path"], root, state_root)) + '</code> — UNKNOWN: ' + esc(adoption["reason"])
    current_notes.append(adoption_note)
    fleet_notes.append(adoption_note)
    source_groups = {"index": current_notes, "readiness": current_notes + readiness_notes, "gaps": gap_notes, "roadmap": road_notes, "fleet": fleet_notes}
    source_body = "".join(f'<section id="{key}" class="panel"><h2>{esc(PAGES[key])}</h2><ul class="source-list">' + "".join(f'<li>{note}</li>' for note in notes) + '</ul></section>' for key, notes in source_groups.items())
    custody_rows = "".join(f'<tr><td><code>{esc(label_path(item["path"], root, state_root))}</code></td><td><code>{esc(item.get("sha256") or item.get("status", "UNVERIFIED"))}</code></td></tr>' for item in inputs.values())
    source_body += f'<section id="sources" class="panel"><h2>Input identity</h2><div class="table-wrap"><table><thead><tr><th>Source</th><th>SHA-256 or status</th></tr></thead><tbody>{custody_rows}</tbody></table></div></section>'
    index_leading = f'<header class="page-header"><h1>North-star readiness and next steps</h1><p class="current-stamp">Current view snapshot: {view.observation_time(current["updated_utc"])}</p><p>{esc(current["headline"])}</p><p class="now-score"><strong>{current["readiness"]["start_gates_met"]} of {current["readiness"]["start_gates_total"]} START gates met</strong></p></header>' + view.gate_strip(current)
    native_dates = {(sanitizer().sanitize(raw_manifest["receipts"][name.removeprefix("readiness:")]["root"]), sanitizer().sanitize(raw_manifest["receipts"][name.removeprefix("readiness:")]["path"])): item.get("source_dates", {}) for name, item in inputs.items() if name.startswith("readiness:")}
    manifest_body = adoption_view.summary(adoption) + f'<section class="manifest-section" aria-labelledby="manifest-title"><h2 id="manifest-title" class="manifest-title">repository manifest at <code>{manifest_sha}</code>, dated receipts</h2><p><a href="sources.html#readiness">Source dates and retained receipt identities</a></p>' + readiness_body(native, manifest, current, view, source_dates=native_dates) + '</section>'
    common = (refreshed, manifest_sha)
    outputs = {
        "index.html": document("index", "North-star readiness and next steps", "", current_scope, overview, *common, [], leading=index_leading),
        "readiness.html": document("readiness", "North-star readiness: what is done, what is left, what needs a decision", "", current_scope, manifest_body, *common, [], leading=view.render(current, workstation, validated=True, readings_normalized=True)),
        "gaps.html": document("gaps", "Grand Gap Board", "Find the open gaps, who owns them and what happens next.", gap_scope, gap_body(rows(gaps, "gaps", ("id", "group", "sev", "title"))), *common, []),
        "roadmap.html": document("roadmap", "Roadmap", "Read the dated milestones and server records.", road_scope, roadmap_body(roadmap), *common, []),
        "fleet.html": document("fleet", "Worker fleet", "", 'Native fleet as of ' + str(fleet.get("at") or "not reported"), adoption_view.roles(adoption), *common, [], leading=fleet_view.render(fleet)),
        "sources.html": document("sources", "Sources and dates", "Check the dates and identities behind each page.", 'Current view and dated repository receipts remain distinct.', source_body, *common, []),
    }
    for name in ("site.css", "site.js"):
        item = capture("asset:" + name, ASSETS / name)
        outputs["assets/" + name] = item["raw"]
    for name in outputs:
        no_symlinks(output_dir / name)
        if any(Path(item["path"]) == output_dir / name or Path(item["path"]) == receipt for item in inputs.values()):
            raise ValueError("generated destination overlaps an input")
    if any(Path(item["path"]) == receipt for item in inputs.values()):
        raise ValueError("refresh receipt overlaps an input")
    if snapshot(Path(current_input["path"]))["sha256"] != current_input["sha256"]:
        raise ValueError("CC current view changed during refresh")
    receipt_doc = {"schema_version": 1, "kind": "local_page_refresh", "generated_utc": refreshed,
                   "output_dir": str(output_dir), "native_readiness_manifest_sha256": manifest_sha,
                    "native_readiness_summary": manifest["summary"],
                    "command_center_current_view": {"updated_utc": current["updated_utc"], "sha256": current_input["sha256"], "schema": current["schema"]},
                    "workstation": workstation,
                    "fleet": fleet,
                     "adoption": {"schema": adoption["schema"], "generated_utc": adoption["generated_utc"], "window_hours": adoption["window_hours"], "sha256": adoption_input["sha256"], "status": adoption.get("status", "RECORDED"), "reason": adoption.get("reason")},
                   "source_scope": {"readiness": "Per-source retained dates; no combined snapshot timestamp", "gaps": gap_scope, "roadmap": road_scope},
                   "inputs": {key: {field: value for field, value in item.items() if field != "raw"} for key, item in inputs.items()},
                   "outputs": {key: {"sha256": hashlib.sha256(value).hexdigest(), "bytes": len(value)} for key, value in outputs.items()},
                   "content_omissions": [{"source": "roadmap-status.json#/owner", "reason": "attributed_direction"}, {"source": "roadmap-status.json#/rules", "reason": "attributed_direction"}, {"source": "roadmap-status.json narrative/glance fields", "reason": "unexpanded_snapshot_templates"}, {"source": "CC original HTML fragments", "reason": "native_source_view_used_without_external_assets_or_attributed_direction"}],
                   "limitations": ["Per-file atomic replacement after all source reads and rendering succeed.", "Receipt identity and page refresh confer no new acceptance, execution, closure or landing.", "Readiness facts and manifest digest come from the native builder; this composer does not adjudicate gates."]}
    publish(output_dir, receipt, outputs, receipt_doc)
    return receipt_doc


def publish(output_dir: Path, receipt: Path, outputs: dict[str, bytes], receipt_doc: dict[str, Any]) -> None:
    """Prepare every file first; replace only generated files, receipt last."""
    receipt.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="local-pages-refresh-", dir=receipt.parent) as staging:
        stage = Path(staging)
        for name, raw in outputs.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        receipt_raw = (json.dumps(receipt_doc, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        (stage / "refresh-receipt.json").write_bytes(receipt_raw)
        # Tempfiles in each destination directory keep os.replace on its filesystem.
        replacements: list[tuple[Path, Path]] = []
        try:
            for destination, raw in [(output_dir / name, (stage / name).read_bytes()) for name in outputs] + [(receipt, receipt_raw)]:
                no_symlinks(destination)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(prefix=".local-pages-", dir=destination.parent, delete=False) as handle:
                    path = Path(handle.name)
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                replacements.append((path, destination))
            for source, destination in replacements:
                no_symlinks(destination)
                os.replace(source, destination)
        finally:
            for path, _ in replacements:
                path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="native readiness source checkout (assets remain beside this composer)")
    parser.add_argument("--state-root", type=Path, default=Path.home() / ".local/state/native-agent-stack")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--sources", type=Path, default=Path("tools/north-star/sources.json"))
    parser.add_argument("--gaps-source", type=Path)
    parser.add_argument("--roadmap-source", type=Path)
    parser.add_argument("--roadmap-inputs", type=Path)
    parser.add_argument("--current-source", type=Path, help="CC-owned cc-now/1 current view (read only)")
    args = parser.parse_args(argv)
    output = args.output_dir or args.state_root / "coordination/command-center/local-pages"
    receipt = args.receipt or args.state_root / "research/fullspeed-20261008/g5-stars-gap/local-pages/refresh-receipt.json"
    try:
        result = refresh(args.root, args.state_root, output, receipt, args.sources, args.gaps_source, args.roadmap_source, args.roadmap_inputs, current_source=args.current_source)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ImportError) as error:
        parser.exit(1, f"local-pages: refresh failed ({type(error).__name__}): {error}\n")
    print(json.dumps({"output_dir": str(output), "receipt": str(receipt), "generated_utc": result["generated_utc"], "native_readiness_manifest_sha256": result["native_readiness_manifest_sha256"], "pages": 6, "API_errors": result["workstation"].get("API_errors", []) + result["fleet"].get("API_errors", [])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
