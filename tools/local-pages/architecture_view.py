"""Render only builder-projected landscape/inventory facts as local HTML.

Source contracts are read by architecture_sources and architecture_inventory.
Design provenance is recorded from the installed skill manifest, not copied.
"""
from __future__ import annotations

from html import escape
import json
import math
import re
from typing import Any
from urllib.parse import urlsplit


def esc(value: Any) -> str:
    return escape(str(value), quote=True)


def value(item: Any) -> str:
    if item is None or item == "" or item == [] or item == {}:
        return "UNREPORTED"
    return json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else str(item)


def repo_key(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    if raw.startswith("https://github.com/"):
        parts = urlsplit(raw).path.strip("/").split("/")
    elif re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", raw):
        parts = raw.split("/")
    else:
        return None
    if len(parts) < 2:
        return None
    return "/".join(parts[:2]).removesuffix(".git").casefold()


def _repositories(layer: dict) -> set[str]:
    found = set()
    for key in ("candidates", "winners", "alternatives", "rejected", "g5_candidates"):
        for item in layer.get(key, []) or []:
            if isinstance(item, dict):
                normalized = repo_key(item.get("repository") or item.get("repo"))
                if normalized:
                    found.add(normalized)
    return found


def join_inventory(model: dict, inventory: dict) -> tuple[dict[str, list[dict]], list[dict]]:
    """Map only explicit layer IDs or exact source repository identity."""
    layers = model["layers"]
    mapping = {layer["key"]: [] for layer in layers}
    repositories = {layer["key"]: _repositories(layer) for layer in layers}
    unmapped = []
    for original in inventory.get("items", []):
        row = dict(original)
        explicit = row.get("layer_id")
        matches = [layer["key"] for layer in layers if explicit in (layer["key"], layer["layer_id"])] if explicit else []
        if not matches:
            repository = repo_key(row.get("repository"))
            if repository:
                matches = [key for key, values in repositories.items() if repository in values]
        if matches:
            row["mapping_basis"] = "explicit layer ID" if explicit else "exact repository identity"
            for key in matches:
                mapping[key].append(row)
        else:
            unmapped.append(row)
    return mapping, unmapped


def _table(caption: str, headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f'<th scope="col">{esc(header)}</th>' for header in headers)
    body = "".join('<tr><th scope="row">' + row[0] + '</th>' + "".join(f'<td>{cell}</td>' for cell in row[1:]) + '</tr>' for row in rows)
    return f'<div class="table-wrap architecture-table" tabindex="0" role="region" aria-label="{esc(caption)}"><table><caption>{esc(caption)}</caption><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _source_refs(item: dict) -> str:
    return esc(value(item.get("source_refs") or item.get("evidence_refs") or item.get("primary_sources") or item.get("source_pointer")))


def _invoke_text(item: dict, model: dict | None) -> str:
    observed = item.get("invoke")
    if not isinstance(observed, dict) or observed.get("status") == "unmeasured":
        return "unmeasured"
    descriptions = []
    for row in observed.get("roles") or []:
        if not isinstance(row, dict):
            continue
        owner = row.get("role") or "owning role unmeasured"
        if owner == "native-agent-stack-1a":
            owner = "owner session (reports to CC)"
        client = row.get("client")
        label = f'{client} {owner}' if client else str(owner)
        if row.get("server"):
            label += f' ({row["server"]})'
        calls = row.get("calls")
        measured = isinstance(calls, int) and not isinstance(calls, bool) and calls >= 0
        hours = row.get("window_hours", observed.get("window_hours"))
        timed = isinstance(hours, (int, float)) and not isinstance(hours, bool) and math.isfinite(hours) and hours > 0
        text = f'{label}: {calls} recorded calls' if measured else f'{label}: unmeasured'
        text += f'; {calls / hours:.3f} calls/hour' if measured and timed else '; rate unmeasured'
        for field, population in (("sessions", "session"), ("conversations", "conversation")):
            if field in row:
                count = row[field]
                count_text = str(count) if isinstance(count, int) and not isinstance(count, bool) and count >= 0 else "unmeasured"
                text += f'; published {population} count: {count_text}'
        if row.get("aggregation_scope"):
            text += '; ' + str(row["aggregation_scope"])
        descriptions.append(text)
    return "; ".join(descriptions) if descriptions else "unmeasured"


def _e2e_text(item: dict) -> str:
    evidence = item.get("e2e") or item.get("upstream_e2e")
    if not isinstance(evidence, dict) or not evidence.get("verified") or not evidence.get("path") or not evidence.get("sha256"):
        return "no upstream E2E evidence"
    return "; ".join(f'{key}: {value(evidence.get(key))}' for key in ("date", "path", "sha256", "command", "result", "evidence_class"))


def _candidate_table(items: list[Any], caption: str, model: dict | None = None) -> str:
    rows = []
    for item in items:
        if isinstance(item, str):
            rows.append([esc(item), "UNREPORTED", "UNREPORTED", "UNREPORTED", "UNREPORTED", "UNREPORTED", "unmeasured", "no upstream E2E evidence"])
            continue
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("id") or item.get("repository") or "UNREPORTED"
        repository = item.get("repository") or item.get("repo")
        pin = item.get("revision") or item.get("pin") or item.get("source_pin") or item.get("commit")
        reason = item.get("rationale") or item.get("reason") or item.get("disposition") or item.get("requirement_fit") or item.get("recorded_disposition") or item.get("decision_scope")
        quality = item.get("quality_evidence") or item.get("criteria") or item.get("source_findings")
        rows.append([esc(name), esc(value(repository)), esc(value(pin)), esc(value(reason)), _source_refs(item), esc(value(quality)), esc(_invoke_text(item, model)), esc(_e2e_text(item))])
    return _table(caption, ["Tool / repository", "Upstream", "Pin", "Recorded reason", "Evidence sources", "Upstream quality evidence", "Invoke rate per owning role", "Latest upstream E2E evidence"], rows) if rows else '<p>UNREPORTED in this source.</p>'


def _inventory_table(items: list[dict], caption: str, model: dict | None = None) -> str:
    rows = [[esc(item.get("name", "UNREPORTED")), esc(value(item.get("kind"))), esc(value(item.get("path"))), esc(value(item.get("repository"))), esc(value(item.get("pin"))), esc(value(item.get("sha256"))), esc(value(item.get("status"))), esc(value(item.get("mapping_basis"))), esc(_invoke_text(item, model)), esc(_e2e_text(item))] for item in items]
    return _table(caption, ["Name", "Inventory", "Path", "Upstream", "Pin", "SHA-256", "Metadata state", "Layer binding", "Invoke rate per owning role", "Latest upstream E2E evidence"], rows) if rows else '<p>No source-bound inventory item is reported for this layer.</p>'


def _rates(candidate: dict, adoption: dict) -> list[dict]:
    # Exact native server names only; plugin aliases mirror adoption_view's producer.
    names = {value.casefold() for value in (candidate.get("name"), candidate.get("id"), candidate.get("component_id")) if isinstance(value, str)}
    repository = repo_key(candidate.get("repository") or candidate.get("repo"))
    if repository:
        names.add(repository.split("/")[1])
    canonical = {"plugin_context-mode_context-mode": "context-mode", "plugin_socraticode_socraticode": "socraticode"}
    rows = []
    hours = adoption.get("window_hours")
    for client, field, population in (("Claude", "claude_by_role", "sessions"), ("Codex", "codex_by_lane", "conversations")):
        for role, record in (adoption.get(field) or {}).items():
            if not isinstance(record, dict):
                continue
            matches = [entry.get("calls") for server, entry in (record.get("servers") or {}).items() if (server.casefold() in names or canonical.get(server) in names) and isinstance(entry, dict)]
            if matches:
                count = None if any(number is None for number in matches) else sum(matches)
                rate = count / hours if count is not None and isinstance(hours, (int, float)) and hours > 0 else None
                rows.append({"client": client, "role": "owner session (reports to CC)" if role == "native-agent-stack-1a" else role, "calls": count, "calls_per_hour": rate, "population": record.get(population)})
    return rows


def _tool_progress(items: list[Any], model: dict) -> str:
    program = model.get("adoption_program") or {}
    stages = program.get("global_stages") or []
    adoption = model.get("adoption_observation") or {}
    tool_rows = []
    seen = set()
    for candidate in items:
        if not isinstance(candidate, dict):
            continue
        identifier = (candidate.get("name") or candidate.get("id"), candidate.get("repository"))
        if identifier in seen:
            continue
        seen.add(identifier)
        stage_state = candidate.get("stages") or candidate.get("adoption_stage") or "UNREPORTED per tool; no completed stage inferred"
        tool_rows.append([esc(value(identifier[0])), esc(value(stage_state)), esc(_invoke_text(candidate, model)), esc(_e2e_text(candidate))])
    labels = '<ol class="architecture-stages">' + "".join(f'<li>{esc(stage)}</li>' for stage in stages) + '</ol>' if stages else '<p>Stage labels are UNREPORTED in the CC source.</p>'
    return labels + _table("Per-candidate stage and recorded role use", ["Candidate", "Recorded stage", "Invoke rate per owning role", "Latest upstream E2E evidence"], tool_rows) + f'<p class="source-note">Invoke snapshot {esc(value(adoption.get("generated_utc")))}; {esc(value(adoption.get("window_hours")))} hours. Observed calls are not evidence of completed clean install, fresh-session acceptance or a final selection.</p>'


def render(model: dict, inventory: dict, first_layer: str | None = None) -> tuple[str, dict]:
    mapped, unmapped = join_inventory(model, inventory)
    all_layers = model["layers"]
    selected = [row for row in all_layers if first_layer in (None, row["key"], row["layer_id"], row["catalog"] + "/" + row["layer_id"])]
    toc = '<nav class="architecture-index" aria-label="Architecture layers"><ul>' + "".join(f'<li><a href="#layer-{esc(row["key"])}">{esc(row["title"])}</a></li>' for row in selected) + '</ul></nav>'
    sections = []
    for row in selected:
        key = row["key"]
        candidates = row.get("candidates") or []
        grand = row.get("g5_candidates") or []
        observation = model.get("adoption_observation") or {}
        observation_source = observation if observation.get("sha256") else model.get("adoption_source") or next((source for source in model.get("sources", []) if "adoption-now" in str(source.get("path"))), {})
        both = sum(1 for item in candidates if isinstance(item, dict) and (item.get("invoke") or {}).get("calls", 0) is not None and (item.get("invoke") or {}).get("calls", 0) > 0 and (item.get("e2e") or {}).get("verified", False))
        body = f'<section class="architecture-layer" id="layer-{esc(key)}" data-layer="{esc(key)}"><header><h2>{esc(row["title"])}</h2><p class="architecture-layer-id">{esc(row["catalog"])} / {esc(row["layer_id"])}</p><p class="architecture-observation">Invoke snapshot {esc(value(observation.get("generated_utc")))} · SHA-256 <code>{esc(value(observation_source.get("sha256")))}</code></p><p><strong>{both} of {len(candidates)}</strong> source components with both recorded organic use and upstream E2E evidence.</p></header><dl class="architecture-choice"><div><dt>Current choice</dt><dd>{esc(value(row.get("current_choice")))}</dd></div><div><dt>Recorded verdict</dt><dd>{esc(value(row.get("verdict_status") or row.get("decision")))}</dd></div><div><dt>Requirement</dt><dd>{esc(value(row.get("requirement")))}</dd></div><div><dt>Reason</dt><dd>{esc(value(row.get("rationale")))}</dd></div></dl>'
        body += '<h3>Recorded winners</h3>' + _candidate_table(row.get("winners") or [], "Winners and retained pins", model)
        body += '<details open><summary>Full landscape candidates and reasons</summary>' + _candidate_table(candidates, "Landscape candidates", model) + '</details>'
        body += '<details><summary>Alternatives and rejected records</summary>' + _candidate_table(row.get("alternatives") or [], "Alternatives", model) + _candidate_table(row.get("rejected") or [], "Rejected", model) + '</details>'
        body += '<details><summary>G5 upstream quality candidates</summary><p class="g5-boundary">' + esc(value((model.get("g5") or {}).get("candidate_label") or "candidate, PENDING G5")) + '</p>' + _candidate_table(grand, "Grand catalog candidate identities", model) + '<pre class="architecture-quality">' + esc(value(row.get("source_quality"))) + '</pre></details>'
        body += '<details><summary>Inventory mapped by sources</summary>' + _inventory_table(mapped[key], "Skills, agents, automation, SDKs, actions and pinned repositories", model) + '</details>'
        body += '<details><summary>Adoption stages and use per role</summary>' + _tool_progress(grand or candidates, model) + '</details>'
        body += '<p class="source-note">Catalog date ' + esc(value(row.get("checked_at"))) + '; source references ' + _source_refs(row) + '</p></section>'
        sections.append(body)
    design = model.get("design") or {}
    design_text = esc(value({key: design.get(key) for key in ("path", "source", "ref", "tree_sha", "skill_md_sha256")}))
    sources = (model.get("sources") or []) + (inventory.get("sources") or [])
    custody = _table("Architecture input custody", ["Source path", "SHA-256", "Source date / state"], [[esc(value(source.get("path"))), esc(value(source.get("sha256"))), esc(value(source.get("checked_at") or source.get("generated_utc") or source.get("status")))] for source in sources if isinstance(source, dict)])
    body = f'<div class="architecture-summary"><p><strong>{len(selected)}</strong> rendered sections / <strong>{len(all_layers)}</strong> canonical landscape layers.</p><p>Selection, inventory observations, source quality and invoke measurement remain separate records.</p></div>' + toc + '<div class="architecture-sections">' + "".join(sections) + '</div>'
    body += '<section id="architecture-unmapped"><h2>Unmapped inventory</h2><p>Items without an explicit layer or exact source repository association remain here; no layer is guessed.</p>' + _inventory_table(unmapped, "Unmapped observed items", model) + '</section>'
    body += '<details id="architecture-custody"><summary>Builder sources and design provenance</summary><p>Installed frontend-design metadata: <code>' + design_text + '</code></p>' + custody + '</details>'
    receipt = {"canonical_layer_count": len(all_layers), "rendered_layer_count": len(selected), "layer_keys": [row["key"] for row in selected], "mapped_inventory_occurrences": sum(len(items) for items in mapped.values()), "unmapped_inventory_items": len(unmapped)}
    return body, receipt
