"""Render only builder-projected landscape/inventory facts as local HTML.

Source contracts are read by architecture_sources and architecture_inventory.
Design provenance is recorded from the installed skill manifest, not copied.
"""
from __future__ import annotations

from html import escape
import hashlib
import importlib.util
import json
import math
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


_SANITIZER = None


def _sanitizer():
    """Reuse the maintained local-pages projection on values, never markup."""
    global _SANITIZER
    if _SANITIZER is None:
        spec = importlib.util.spec_from_file_location("architecture_text_projection", Path(__file__).with_name("sanitization.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _SANITIZER = module
    return _SANITIZER


def _portable(item: Any) -> Any:
    # JSON object keys can contain source paths too. Project them before JSON
    # string escaping makes encoded source identities part of the payload.
    if isinstance(item, dict):
        return {_sanitizer().text(key): _portable(child) for key, child in item.items()}
    if isinstance(item, (list, tuple)):
        return [_portable(child) for child in item]
    return _sanitizer().sanitize(item)


def esc(value: Any) -> str:
    return escape(_sanitizer().text(value), quote=True)


def value(item: Any) -> str:
    if item is None or item == "" or item == [] or item == {}:
        return "UNREPORTED"
    return json.dumps(_portable(item), ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else _sanitizer().text(item)


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
    """Retain canonical catalog joins and explicit reviewed mappings."""
    layers = model["layers"]
    mapping = {layer["key"]: [] for layer in layers}
    repositories = {layer["key"]: _repositories(layer) for layer in layers}
    unmapped = []
    for original in inventory.get("items", []):
        row = dict(original)
        explicit = row.get("layer_id")
        keys = row.get("layer_keys") or []
        if not isinstance(keys, list):
            keys = []
        matches = [layer["key"] for layer in layers if any(key in (layer["key"], layer["catalog"] + "/" + layer["layer_id"]) for key in keys)]
        if not matches and explicit:
            matches = [layer["key"] for layer in layers if explicit in (layer["key"], layer["layer_id"]) and row.get("catalog", layer["catalog"]) == layer["catalog"]]
        if not matches:
            repository = repo_key(row.get("repository"))
            if repository:
                matches = [key for key, values in repositories.items() if repository in values]
        if matches:
            row["mapping_basis"] = row.get("mapping_reason") or ("explicit layer ID" if explicit or keys else "exact repository identity")
            for key in matches:
                mapping[key].append(row)
        else:
            row["unmapped_reason"] = row.get("unmapped_reason") or "No canonical component/repository join or reviewed mapping matches this item"
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
        reason = observed.get("reason") if isinstance(observed, dict) else None
        return "unmeasured: " + str(reason or "No attached producer observation matches this component identity")
    descriptions = []
    for row in observed.get("roles") or []:
        if not isinstance(row, dict):
            continue
        owner = row.get("role") or "owning role unmeasured (producer attribution absent)"
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
        unit = "sessions" if observed.get("measure") == "sessions" else "calls"
        text = f'{label}: {calls} recorded {unit}' if measured else f'{label}: unmeasured (published count absent)'
        text += f'; {calls / hours:.3f} {unit}/hour' if measured and timed else '; rate unmeasured (window duration absent)'
        for field, population in (("sessions", "session"), ("conversations", "conversation")):
            if field in row:
                count = row[field]
                count_text = str(count) if isinstance(count, int) and not isinstance(count, bool) and count >= 0 else "unmeasured (producer count absent or invalid)"
                text += f'; published {population} count: {count_text}'
        if row.get("aggregation_scope"):
            text += '; ' + str(row["aggregation_scope"])
        descriptions.append(text)
    return "; ".join(descriptions) if descriptions else "unmeasured: " + str(observed.get("reason") or "Producer supplied no owning-role observations")


def _e2e_text(item: dict) -> str:
    evidence = item.get("e2e") or item.get("upstream_e2e")
    if not isinstance(evidence, dict):
        return "no upstream E2E evidence: no registered receipt matches this component identity"
    recorded = evidence.get("path") and evidence.get("sha256") and (evidence.get("verified") or evidence.get("receipt_verified") or evidence.get("kind"))
    if not recorded:
        return "no upstream E2E evidence: " + str(evidence.get("reason") or "No digest-bound E2E receipt is registered for this component")
    scope = evidence.get("evidence_scope") or evidence.get("source_scope")
    label = {"native_host": "native E2E on this host", "vendor_test_suite": "vendor test-suite run", "local": "local host E2E receipt"}.get(scope, str(scope or "recorded E2E receipt"))
    if evidence.get("kind") in ("historical_inventory", "compatibility_attempt"):
        label = "not E2E; " + str(evidence["kind"])
    elif evidence.get("kind") == "artifact_measurement":
        label = "measurement receipt"
    elif evidence.get("kind") == "upstream_provenance":
        label = "source provenance receipt"
    details = [label, f'kind: {value(evidence.get("kind") or evidence.get("evidence_class"))}', f'UTC date: {value(evidence.get("date"))}', f'result: {value(evidence.get("result"))}', f'receipt: {evidence["path"]}#{evidence["sha256"]}', f'command: {value(evidence.get("command"))}']
    if evidence.get("command_count") is not None:
        details.append(f'commands: {evidence["command_count"]}; programs: {value(evidence.get("command_programs"))}')
    if evidence.get("date_original") and not evidence.get("date"):
        details.append(f'recorded date: {value(evidence["date_original"])}; timezone: {value(evidence.get("date_timezone"))}')
    for key in ("evidence_class", "selected_pin", "observed_pin", "reason"):
        if evidence.get(key):
            details.append(f'{key}: {value(evidence[key])}')
    return "; ".join(details)


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
    rows = [[esc(item.get("name", "UNREPORTED")), esc(value(item.get("kind"))), esc(value(item.get("path"))), esc(value(item.get("repository"))), esc(value(item.get("pin"))), esc(value(item.get("sha256"))), esc(value(item.get("status"))), esc(value(item.get("mapping_basis") or item.get("unmapped_reason"))) + ("; source: " + esc(value(item["mapping_source"])) if item.get("mapping_source") else ""), esc(_invoke_text(item, model)), esc(_e2e_text(item))] for item in items]
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


def _closed(label: str, count: int, content: str) -> str:
    return f'<details><summary>{esc(label)} · {count} records</summary>{content}</details>'


def _layer_detail(row: dict, items: list[dict], model: dict) -> str:
    candidates, grand = row.get("candidates") or [], row.get("g5_candidates") or []
    content = '<p class="source-note">Detail for ' + esc(value(row.get("title"))) + ' · ' + esc(row["key"]) + '</p>'
    content += _closed("Recorded winners", len(row.get("winners") or []), _candidate_table(row.get("winners") or [], "Winners and retained pins", model))
    content += _closed("Full landscape candidates and reasons", len(candidates), _candidate_table(candidates, "Landscape candidates", model))
    for field, label in (("alternatives", "Alternatives"), ("rejected", "Rejected records")):
        content += _closed(label, len(row.get(field) or []), _candidate_table(row.get(field) or [], label, model))
    content += _closed("G5 upstream quality candidates", len(grand), '<p class="g5-boundary">' + esc(value((model.get("g5") or {}).get("candidate_label") or "candidate, PENDING G5")) + '</p>' + _candidate_table(grand, "Grand catalog candidate identities", model) + '<pre class="architecture-quality">' + esc(value(row.get("source_quality"))) + '</pre>')
    content += _closed("Inventory mapped by sources", len(items), _inventory_table(items, "Skills, agents, automation, SDKs, actions and pinned repositories", model))
    content += _closed("Adoption stages and use per role", len(grand or candidates), _tool_progress(grand or candidates, model))
    return content


def _deferred(key: str, label: str, content: str, outputs: dict[str, bytes] | None) -> str:
    if outputs is None:
        return content
    raw = content.encode("utf-8")
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", _sanitizer().text(key)).strip("-") or "detail"
    path = f'architecture/layers/{slug}-{hashlib.sha256(raw).hexdigest()[:16]}.html'
    outputs[path] = raw
    return f'<details class="architecture-detail" data-layer-src="{esc(path)}"><summary>{esc(label)}</summary><div class="architecture-detail-content" aria-live="polite"><p>Expand to load these component tables. <a href="{esc(path)}">Open the detail page</a>.</p></div></details>'


def _local_host_receipts(host: dict) -> str:
    items = host.get("items") or []
    rows = [[esc(value(item.get("title"))), "local host receipt (state root)", esc(value(item.get("path"))), esc(value(item.get("sha256"))), esc(value(item.get("bytes"))), esc(value(item.get("mtime_utc")))] for item in items]
    note = '<p>The sanitized index does not supply execution date, command or result. Receipt hashes are index-declared; mtime is file metadata. Referenced receipt bodies are not read, and this metadata does not establish native E2E or selected-pin acceptance.</p>'
    table = _table("State-root host receipt metadata", ["Receipt title", "Scope", "Index-provided path", "SHA-256 (index-declared)", "Bytes (index)", "mtime UTC (index)"], rows) if rows else '<p>' + esc(value((host.get("coverage") or {}).get("status") or "Sanitized local receipt index unavailable")) + '</p>'
    return _closed("Local host receipt metadata", len(items), note + table)


def render(model: dict, inventory: dict, first_layer: str | None = None,
           detail_outputs: dict[str, bytes] | None = None) -> tuple[str, dict]:
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
        counts_text = f'Component tables · {len(row.get("winners") or [])} winners · {len(candidates)} landscape candidates · {len(grand)} G5 candidates · {len(mapped[key])} inventory items'
        body += _deferred(key, counts_text, _layer_detail(row, mapped[key], model), detail_outputs)
        body += '<p class="source-note">Catalog date ' + esc(value(row.get("checked_at"))) + '; source references ' + _source_refs(row) + '</p></section>'
        sections.append(body)
    design = model.get("design") or {}
    design_text = esc(value({key: design.get(key) for key in ("path", "source", "ref", "tree_sha", "skill_md_sha256")}))
    sources = (model.get("sources") or []) + (inventory.get("sources") or [])
    custody = _table("Architecture input custody", ["Source path", "SHA-256", "Source date / state"], [[esc(value(source.get("path"))), esc(value(source.get("sha256"))), esc(value(source.get("checked_at") or source.get("generated_utc") or source.get("status")))] for source in sources if isinstance(source, dict)])
    body = f'<div class="architecture-summary"><p><strong>{len(selected)}</strong> rendered sections / <strong>{len(all_layers)}</strong> canonical landscape layers.</p><p>Invoke counts are observational (organic use, not a controlled trial). Client counts measure sessions; Bash-run CLI invocations are outside the producer’s MCP counters. Native host E2E, local receipts and vendor test-suite runs retain their distinct scopes.</p></div>' + toc + '<div class="architecture-sections">' + "".join(sections) + '</div>'
    coverage = inventory.get("coverage") or {}
    projection = coverage.get("automation_projection") or {}
    limits = projection.get("limits") or coverage.get("automation_limits") or []
    automation = '<p>Hooks: ' + esc(value(coverage.get("client_hook_wiring"))) + '. Cron: ' + esc(value(coverage.get("cron_status"))) + '.</p>'
    automation += '<ul>' + ''.join('<li>' + esc(str(limit)) + '</li>' for limit in limits) + '</ul>' if limits else ''
    body += '<section id="architecture-automation"><h2>Automation observation</h2>' + automation + '</section>'
    host = model.get("host_receipts") or {}
    local_items = host.get("items") or []
    local_source = next(iter(host.get("sources") or []), {})
    local_intro = f'<p>{len(local_items)} local host receipts · index <code>{esc(value(local_source.get("path")))}#{esc(value(local_source.get("sha256")))}</code></p>'
    body += '<section id="architecture-local-host-receipts"><h2>Local host receipts</h2>' + local_intro + _deferred("local-host-receipts", f'Local host receipt metadata · {len(local_items)} records', _local_host_receipts(host), detail_outputs) + '</section>'
    unmapped_detail = _closed("Unmapped observed items", len(unmapped), _inventory_table(unmapped, "Unmapped observed items", model))
    body += '<section id="architecture-unmapped"><h2>Unmapped inventory</h2><p>' + str(len(unmapped)) + ' items remain outside canonical joins and the committed mapping; each carries its specific reason.</p>' + (_deferred("unmapped", f'Unmapped observed items · {len(unmapped)} records', unmapped_detail, detail_outputs) if unmapped else '') + '</section>'
    custody_detail = '<p>Installed frontend-design metadata: <code>' + design_text + '</code></p>' + _closed("Architecture input custody", len(sources), custody)
    body += '<section id="architecture-custody"><h2>Builder sources and design provenance</h2>' + _deferred("custody", f'Source custody · {len(sources)} records', custody_detail, detail_outputs) + '</section>'
    receipt = {"canonical_layer_count": len(all_layers), "rendered_layer_count": len(selected), "layer_keys": [row["key"] for row in selected], "mapped_inventory_occurrences": sum(len(items) for items in mapped.values()), "unmapped_inventory_items": len(unmapped)}
    return body, receipt
