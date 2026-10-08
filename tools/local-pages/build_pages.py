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
MAX_BYTES = 8 * 1024 * 1024
DATE_KEYS = ("as_of_utc", "updated_utc", "generated_utc", "generated_at",
             "checked_at", "recorded_utc", "captured_at", "captured_utc")
ACCOUNT_URL = re.compile(r"https?://(?:claude\.ai/artifact|chatgpt\.com/|chat\.openai\.com/)[^\s<>\"']*", re.I)
TEMPLATE = re.compile(r"\$?\{[A-Za-z_][A-Za-z0-9_]*\}")
PAGES = {"index": "Overview", "readiness": "Readiness", "gaps": "Gap register", "roadmap": "Roadmap"}


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
    text = str(value if value is not None else "Unspecified in source")
    text = ACCOUNT_URL.sub("[account artifact omitted]", text)
    return TEMPLATE.sub("[source template omitted]", text)


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


def source_scope(item: dict[str, Any], document: dict[str, Any]) -> str:
    fields = dates(document)
    if fields:
        return "; ".join(f"{key} = {value}" for key, value in fields.items())
    return "Source-owned snapshot date unspecified. File modified " + item["file_modified_utc"] + " (file metadata, not event or acceptance time)."


def document(page: str, title: str, lede: str, scope: str, body: str,
             refreshed: str, manifest_sha: str, source_notes: list[str]) -> bytes:
    nav = "".join(f'<a href="{name}.html"' + (' aria-current="page"' if name == page else '') + f'>{text}</a>' for name, text in PAGES.items())
    sources = "".join(f"<li>{note}</li>" for note in source_notes)
    return (f'''<!doctype html>
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
  <header class="page-header"><p class="eyebrow">Retained source view</p><h1>{esc(title)}</h1><p class="lede">{esc(lede)}</p></header>
  <div class="snapshot-note"><p><strong>Source as of:</strong> {esc(scope)}</p>
    <p><strong>Page refreshed:</strong> <time datetime="{esc(refreshed)}">{esc(refreshed)}</time></p>
    <p><strong>Native readiness manifest SHA-256:</strong> <code>{manifest_sha}</code></p>
    <p>Recorded source states retain their original scope. Rendering does not establish fresh execution, reader approval or landing.</p>
  </div>
  {body}
</main>
<footer class="site-footer"><h2>Source scope</h2><ul class="source-list">{sources}</ul>
  <p>Input hashes and refresh custody are retained outside this served directory. Source-linked operational records are shown; attributed direction sections and account artifact links are omitted.</p>
</footer>
</div>
</body>
</html>
''').encode("utf-8")


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
</div><p id="gap-result-count" role="status" aria-live="polite">{len(gaps)} of {len(gaps)} gaps shown</p>'''
    cards = []
    seen: set[str] = set()
    for row in gaps:
        identity = display(row["id"])
        if identity in seen:
            raise ValueError(f"duplicate gap identity: {identity}")
        seen.add(identity)
        search = " ".join(display(row.get(key, "")) for key in ("id", "group", "sev", "title", "state", "owner", "next", "due", "evidence")).casefold()
        details = "".join(f'<div><dt>{name}</dt><dd>{esc(row.get(key))}</dd></div>' for key, name in (("owner", "Operational owner"), ("next", "Next action"), ("due", "Source-listed due date"), ("evidence", "Evidence pointer")))
        cards.append(f'<article class="gap-card" data-search="{esc(search)}" data-group="{esc(display(row["group"]).strip().casefold())}" data-severity="{esc(display(row["sev"]).strip().casefold())}"><div class="gap-meta"><span>{esc(identity)}</span><span>{esc(row["group"])}</span><span class="severity">{esc(row["sev"])}</span></div><h2>{esc(row["title"])}</h2><p class="gap-state">{esc(row.get("state"))}</p><dl class="gap-details">{details}</dl></article>')
    return summary + controls + '<div id="gap-register">' + "\n".join(cards) + '</div><p id="gap-empty" hidden>No source rows match these filters. Clear the search or choose All.</p>'


def roadmap_body(status: dict[str, Any]) -> str:
    milestones = rows(status, "milestones", ("what", "state"))
    # Custodian build_roadmap.py:284 uses a truthy at, otherwise its when label.
    for row in milestones:
        if not row.get("at") and "when" not in row:
            raise ValueError("milestone must provide at or when source timing")
    servers = rows(status, "servers", ("key", "label", "job", "paired", "verdict", "next"))
    events = "".join(f'<li class="milestone"><span class="milestone-time">{esc(row["at"] if row.get("at") else row["when"])}</span><div><h3 class="milestone-title">{esc(row["what"])}</h3><p class="milestone-state">{esc(row["state"])}</p></div></li>' for row in milestones)
    server_rows = "".join('<tr>' + "".join(f'<td>{esc(row[key])}</td>' for key in ("label", "job", "paired", "verdict", "next")) + '</tr>' for row in servers)
    ladder = rows(status, "ladder")
    if any(not isinstance(item, str) for item in ladder):
        raise ValueError("ladder entries must be source text")
    sequence = "".join(f'<li>{esc(item.replace("**", ""))}</li>' for item in ladder)
    return f'''<div class="metric-grid" aria-label="Source row counts"><p><strong>{len(milestones)}</strong> milestones</p><p><strong>{len(servers)}</strong> server records</p></div>
<section class="panel"><div class="section-header"><h2>Source-listed milestones</h2><p>These are retained event dates and source states. Passing a date does not record completion.</p></div><ol class="milestone-rail">{events}</ol></section>
<section class="panel"><div class="section-header"><h2>Server records</h2><p>Verdicts are copied from this roadmap snapshot; they are not a new host check.</p></div><div class="table-wrap"><table><thead><tr><th>Server</th><th>Role</th><th>Paired client evidence</th><th>Source verdict</th><th>Next action</th></tr></thead><tbody>{server_rows}</tbody></table></div></section>
<section class="panel"><div class="section-header"><h2>Recorded finalization sequence</h2></div><ol class="source-sequence">{sequence}</ol></section>'''


def readiness_body(native: Any, manifest: dict[str, Any]) -> str:
    gates = "".join(f'<article class="gate-card"><h3>{esc(row["id"])}</h3><p class="gate-state">{esc(fact(row["fields"].get("state")))}</p><p>Operational owner: {esc(fact(row["fields"].get("owner")))}</p></article>' for row in manifest["gates"])
    fragment = display(native.render_fragment(manifest))
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


def refresh(root: Path, state_root: Path, output_dir: Path, receipt: Path,
            sources: Path = Path("tools/north-star/sources.json"),
            gaps_source: Path | None = None, roadmap_source: Path | None = None,
            roadmap_inputs: Path | None = None, refreshed: str | None = None) -> dict[str, Any]:
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
    index = capture("native_source_index", sources)
    source_spec = strict_json(index["raw"])
    if not isinstance(source_spec, dict) or not isinstance(source_spec.get("sources"), dict):
        raise ValueError("native source index must contain a sources object")
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
    manifest = native.build(root, state_root, sources)
    manifest_bytes = native.render(manifest)
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest["source_index"]["sha256"] != index["sha256"]:
        raise ValueError("native source index changed during refresh")
    readiness_notes = []
    for name, record in manifest["receipts"].items():
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
    gap_input = capture("gaps", gaps_source or cc_tools / "gaps/gaps.json")
    road_input = capture("roadmap", roadmap_source or cc_tools / "roadmap/roadmap-status.json")
    road_index = capture("roadmap_inputs", roadmap_inputs or cc_tools / "roadmap/roadmap-inputs.json")
    gaps, roadmap, road_links = (strict_json(item["raw"]) for item in (gap_input, road_input, road_index))
    if any(not isinstance(item, dict) for item in (gaps, roadmap, road_links)):
        raise ValueError("CC page source must be a JSON object")
    for key in ("board_base", "board_ruled", "handbook", "lane_live", "triage_owner", "manifest", "token_window", "stack_effect", "versions", "pr_counts", "css_from"):
        if key not in road_links:
            continue
        path = Path(road_links[key])
        path = path if path.is_absolute() else state_root / path
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
    gap_notes = [f'<code>{esc(label_path(gap_input["path"], root, state_root))}</code> — {esc(gap_scope)}', "Counts describe rows and severity labels in this gap snapshot. Due dates are source-listed deadlines."]
    road_notes = [f'<code>{esc(label_path(road_input["path"], root, state_root))}</code> — {esc(road_scope)}', f'<code>{esc(label_path(road_index["path"], root, state_root))}</code> — retained input bindings; hashes remain in the nonserved receipt.', "Milestone dates are event dates. No single roadmap snapshot date was inferred from them."]
    overview = '<section class="panel"><div class="section-header"><h2>Choose a source view</h2></div><ul class="page-index"><li><a href="readiness.html">Readiness receipts</a><p>Native gate, layer and SDK records, with retained source boundaries.</p></li><li><a href="gaps.html">Gap register</a><p>Search and filter the CC snapshot by group and severity.</p></li><li><a href="roadmap.html">Roadmap</a><p>Source-listed milestones, server records and finalization sequence.</p></li></ul></section>'
    common = (refreshed, manifest_sha)
    outputs = {
        "index.html": document("index", "Engineering source views", "Read the records and their dates before following the next action.", "Mixed snapshots. Each page names its own source date scope.", overview, *common, ["Gap snapshot: " + esc(gap_scope), "Roadmap snapshot: " + esc(road_scope), "Readiness: per-source retained dates; no combined snapshot timestamp."]),
        "readiness.html": document("readiness", "Readiness receipts", "The native manifest joins retained receipt facts. Each claim keeps its source status.", "Per-source dates below; no combined source-owned snapshot timestamp.", readiness_body(native, manifest), *common, readiness_notes),
        "gaps.html": document("gaps", "Gap register", "Source-listed open measurements and next actions, in one searchable register.", gap_scope, gap_body(rows(gaps, "gaps", ("id", "group", "sev", "title"))), *common, gap_notes),
        "roadmap.html": document("roadmap", "Roadmap", "Retained milestone events and server records from the command-center roadmap snapshot.", road_scope, roadmap_body(roadmap), *common, road_notes),
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
    receipt_doc = {"schema_version": 1, "kind": "local_page_refresh", "generated_utc": refreshed,
                   "output_dir": str(output_dir), "native_readiness_manifest_sha256": manifest_sha,
                   "native_readiness_summary": manifest["summary"],
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
    args = parser.parse_args(argv)
    output = args.output_dir or args.state_root / "coordination/command-center/local-pages"
    receipt = args.receipt or args.state_root / "research/fullspeed-20261008/g5-stars-gap/local-pages/refresh-receipt.json"
    try:
        result = refresh(args.root, args.state_root, output, receipt, args.sources, args.gaps_source, args.roadmap_source, args.roadmap_inputs)
    except (OSError, ValueError, KeyError, TypeError, ImportError) as error:
        parser.exit(1, f"local-pages: refresh failed ({type(error).__name__}): {error}\n")
    print(json.dumps({"output_dir": str(output), "receipt": str(receipt), "generated_utc": result["generated_utc"], "native_readiness_manifest_sha256": result["native_readiness_manifest_sha256"], "pages": 4}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
