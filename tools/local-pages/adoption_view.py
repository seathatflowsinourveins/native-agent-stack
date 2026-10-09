"""Read-only HTML views of the published adoption-now/1 invocation snapshot."""

from __future__ import annotations

from datetime import datetime, timedelta
from html import escape as _escape
import importlib.util
from pathlib import Path
import re
from typing import Any


SCHEMA = "adoption-now/1"
METHOD = "docs/decisions/2026-09-26-tool-invoke-rates.md"
_OWNER = "native-agent-stack-1a"
_OWNER_DISPLAY = "owner session (reports to CC)"
_LABEL = re.compile(r"[A-Za-z0-9 ._:/()+&-]{1,120}\Z")
_OPAQUE = re.compile(r"[A-Za-z0-9]{24,}|(?:sk-|gh[pousr]_|github_pat_|Bearer\s)", re.I)
# Exact memberships published by adoption_invoke.py LAYERS, not substrings.
_CANONICAL = {
    "plugin_context-mode_context-mode": "context-mode",
    "plugin_socraticode_socraticode": "socraticode",
}
_PRODUCER_LAYERS = {
    "memory and retrieval": ("ai-memory", "hindsight", "qmd", "qmdshared"),
    "session context and token efficiency": ("context-mode", "headroom"),
    "code intelligence": ("serena", "codebase-memory-mcp", "jcodemunch", "semble", "socraticode"),
    "evaluation": ("promptfoo",), "observability": ("grafana", "agentsview"),
    "browser": ("chrome-devtools",), "client-native": ("codex_apps", "codex_worktrees"),
}
_SANITIZER_SPEC = importlib.util.spec_from_file_location("local_adoption_view_sanitization", Path(__file__).with_name("sanitization.py"))
_sanitization = importlib.util.module_from_spec(_SANITIZER_SPEC)
_SANITIZER_SPEC.loader.exec_module(_sanitization)


def escape(value: Any, quote: bool = True) -> str:
    return _escape(_sanitization.text(value), quote=quote)


def _count(value: Any) -> bool:
    return value is None or isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _map(value: Any, field: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, dict) or len(value) > 2000:
        raise ValueError(f"{field} must be a bounded object")
    if any(not isinstance(key, str) or not key or len(key) > 200 for key in value):
        raise ValueError(f"{field} has an invalid label")


def _server_map(row: Any, fields: tuple[str, ...], category: str) -> None:
    if not isinstance(row, dict) or "servers" not in row:
        raise ValueError(f"{category} requires a servers map")
    servers = row["servers"]
    _map(servers, "servers", nullable=True)
    if servers is None:
        return
    for entry in servers.values():
        if not isinstance(entry, dict):
            raise ValueError("server observations must be objects")
        if any(not _count(entry.get(field)) for field in fields):
            raise ValueError("server observations require nonnegative integer or null counts")


def validate(document: Any) -> None:
    """Reject malformed source shapes without replacing them with zero counts."""
    if not isinstance(document, dict) or document.get("schema") != SCHEMA:
        raise ValueError("expected adoption-now/1")
    if document.get("status") == "UNREPORTED":
        if not isinstance(document.get("reason"), str) or not document["reason"] or len(document["reason"]) > 240 or any(document.get(field) is not None for field in ("generated_utc", "window_hours", "layers", "claude_by_role", "codex_by_lane", "codex_by_role", "claude_total_sessions", "codex_total_conversations")):
            raise ValueError("unreported adoption requires an explicit reason and unknown observation fields")
        return
    hours = document.get("window_hours")
    if isinstance(hours, bool) or not isinstance(hours, int) or hours <= 0:
        raise ValueError("window_hours must be a positive integer")
    timestamp = document.get("generated_utc")
    if not isinstance(timestamp, str) or len(timestamp) > 40:
        raise ValueError("generated_utc must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("generated_utc must be a UTC timestamp") from None
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("generated_utc must be a UTC timestamp")
    for category in ("layers", "claude_by_role"):
        _map(document.get(category), category)
    if "codex_by_role" in document:
        _map(document["codex_by_role"], "codex_by_role", nullable=True)
    if "codex_by_lane" in document or "codex_by_role" not in document:
        _map(document.get("codex_by_lane"), "codex_by_lane")
    for field in ("claude_total_sessions", "codex_total_conversations"):
        if not _count(document.get(field)):
            raise ValueError("population counts require nonnegative integer or null counts")
    for row in document["layers"].values():
        _server_map(row, ("claude_calls", "claude_sessions", "codex_calls", "codex_conversations"), "layer")
    for row in document["claude_by_role"].values():
        _server_map(row, ("calls", "sessions"), "Claude role")
        if any(not _count(row.get(field)) for field in ("sessions", "tool_calls")):
            raise ValueError("Claude role counts require nonnegative integer or null counts")
    for category in ("codex_by_role", "codex_by_lane"):
        for row in (document.get(category) or {}).values():
            _server_map(row, ("calls", "conversations"), "Codex role / label")
            if not _count(row.get("conversations")):
                raise ValueError("Codex conversation counts require nonnegative integer or null counts")
    # A canonical server cannot belong to two published layers.
    assignments = {}
    for layer, row in document["layers"].items():
        for server in row["servers"] or {}:
            canonical = _CANONICAL.get(server, server)
            if canonical in assignments and assignments[canonical] != layer:
                raise ValueError("server assigned to multiple layers")
            assignments[canonical] = layer


def _label(value: str) -> str:
    if value == _OWNER:
        return _OWNER_DISPLAY
    if not _LABEL.fullmatch(value) or "@" in value or _OPAQUE.search(value):
        return "withheld label"
    return _sanitization.text(value)


def _show(value: int | None) -> str:
    return "not reported" if value is None else f"{value:,}"


def _sum(values: list[int | None]) -> int | None:
    return None if any(value is None for value in values) else sum(values)


def _layer_members(document: dict[str, Any]) -> dict[str, str]:
    membership = {}
    for layer in document["layers"]:
        for server in _PRODUCER_LAYERS.get(layer, ()):
            membership[server] = layer
    for layer, row in document["layers"].items():
        for server in row["servers"] or {}:
            membership[_CANONICAL.get(server, server)] = layer
    return membership


def _layer_counts(row: dict[str, Any], layers: list[str], membership: dict[str, str]) -> list[int | None]:
    if row["servers"] is None:
        return [None] * len(layers)
    values: dict[str, list[int | None]] = {layer: [] for layer in layers}
    for server, record in row["servers"].items():
        layer = membership.get(_CANONICAL.get(server, server))
        if layer in values:
            values[layer].append(record.get("calls"))
    return [_sum(values[layer]) for layer in layers]


def _table(caption: str, columns: list[str], rows: list[list[str]]) -> str:
    header = "".join(f'<th scope="col">{escape(column)}</th>' for column in columns)
    body = "".join("<tr>" + f'<th scope="row">{row[0]}</th>' + "".join(f"<td>{cell}</td>" for cell in row[1:]) + "</tr>" for row in rows)
    return f'<div class="table-wrap adoption-table" tabindex="0" role="region" aria-label="{escape(caption, quote=True)}"><table><caption>{escape(caption)}</caption><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>'


def _meta(document: dict[str, Any]) -> str:
    return f'<p class="muted">Last {document["window_hours"]} hours · snapshot <time datetime="{escape(document["generated_utc"], quote=True)}">{escape(document["generated_utc"])}</time> · co-op hourly view</p>'


def summary(document: dict[str, Any]) -> str:
    """Readiness section: recorded layer totals and optional server detail."""
    validate(document)
    if document.get("status") == "UNREPORTED":
        return '<section id="adoption"><h2>Adoption</h2><p>UNKNOWN · ' + escape(document["reason"]) + '</p><p>Session populations, observation window and invocation counts are unavailable.</p></section>'
    layer_rows, server_rows = [], []
    for layer, row in document["layers"].items():
        servers = row["servers"]
        claude = _sum([record.get("claude_calls") for record in servers.values()]) if servers is not None else None
        codex = _sum([record.get("codex_calls") for record in servers.values()]) if servers is not None else None
        layer_rows.append([escape(_label(layer)), _show(claude), _show(codex)])
        for server, record in (servers or {}).items():
            server_rows.append([escape(_label(server)), escape(_label(layer)), *[_show(record.get(field)) for field in ("claude_calls", "claude_sessions", "codex_calls", "codex_conversations")]])
    population = f'<p>Window population: {_show(document.get("claude_total_sessions"))} Claude sessions; {_show(document.get("codex_total_conversations"))} Codex conversations.</p>'
    totals = _table("Recorded MCP calls by layer", ["Layer", "Claude calls", "Codex calls"], layer_rows)
    detail = _table("Recorded observations by server", ["Server", "Layer", "Claude calls", "Claude sessions", "Codex calls", "Codex conversations"], server_rows)
    return '<section id="adoption"><h2>Adoption</h2>' + _meta(document) + population + totals + '<details><summary>Per-server counts</summary>' + detail + '<p class="muted">Session and conversation counts belong to each server; adding them does not yield a unique layer population.</p></details><p class="muted">Recorded invocations describe this window; they do not establish adoption acceptance, session freshness or a readiness gate. Zero means no recorded calls in this window.</p></section>'


def roles(document: dict[str, Any]) -> str:
    """Fleet section: every published role, grouped by client, after the roster."""
    validate(document)
    if document.get("status") == "UNREPORTED":
        return '<section id="adoption-by-role"><h2>Adoption by role</h2><p>UNKNOWN · ' + escape(document["reason"]) + '</p><p>Role counts and observation dates are unavailable.</p></section>'
    layers = list(document["layers"])
    membership = _layer_members(document)
    groups = []
    server_rows = []
    codex_key = "codex_by_role" if "codex_by_role" in document else "codex_by_lane"
    fallback = codex_key == "codex_by_lane"
    for key, client, population in (("claude_by_role", "Claude", "sessions"), (codex_key, "Codex", "conversations")):
        rows = []
        for name, row in (document.get(key) or {}).items():
            label = escape(_label(name))
            counts = _layer_counts(row, layers, membership)
            rows.append([label, _show(row.get(population)), *[_show(count) for count in counts]])
            for server, record in (row["servers"] or {}).items():
                layer = membership.get(_CANONICAL.get(server, server))
                server_rows.append([label, client, escape(_label(server)), escape(_label(layer)) if layer else "other published server", _show(record.get("calls")), _show(record.get(population))])
        label_kind = "labels" if client == "Codex" and fallback else "roles"
        table = _table(f"{client}: recorded MCP calls per layer by published {label_kind}", ["Published role / label", population.capitalize(), *[_label(layer) for layer in layers]], rows)
        groups.append(f'<details><summary>{client}: {len(rows) if document.get(key) is not None else "UNKNOWN"} published {label_kind}</summary>{table}</details>')
    detail = _table("Per-role observations by server", ["Published role / label", "Client", "Server", "Layer", "Calls", "Server sessions / conversations"], server_rows)
    note = '<p>Codex role projection is absent; fallback uses recorded instance labels from snapshot ' + escape(document["generated_utc"]) + '.</p>' if fallback else '<p>Codex rows use the producer-published role projection for this observation window.</p>'
    return '<section id="adoption-by-role"><h2>Adoption by role</h2>' + _meta(document) + note + '<p>Historical labels in this window are independent of the current worker roster. Counts are recorded MCP calls per layer.</p>' + "".join(groups) + '<details><summary>Per-role server counts</summary>' + detail + '</details><p class="muted">Missing entries in a valid server map mean zero recorded calls; unknown source counts are labelled not reported. Counts do not establish adoption acceptance or session freshness.</p></section>'
