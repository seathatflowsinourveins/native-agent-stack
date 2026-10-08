"""Present the CC-owned cc-now/1 schema without modifying its source claims.

References: CC cc-now/1 schema; Python3.13 datetime/zoneinfo/html/urllib.parse;
Anthropic frontend-design683bc88e and Vercel web-design-guidelines063bee94.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import importlib.util
import math
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo


_SANITIZER_SPEC = importlib.util.spec_from_file_location("local_current_view_sanitization", Path(__file__).with_name("sanitization.py"))
_sanitization = importlib.util.module_from_spec(_SANITIZER_SPEC)
_SANITIZER_SPEC.loader.exec_module(_sanitization)


def esc(value: object) -> str:
    return escape(_sanitization.text(value), quote=True)


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("current-view dates require a timezone")
    return parsed.astimezone(timezone.utc)


def validate(view: dict) -> None:
    if not isinstance(view, dict) or view.get("schema") != "cc-now/1":
        raise ValueError("expected CC current-view schema cc-now/1")
    parse_time(view["updated_utc"])
    if view.get("timezone_for_display") != "America/New_York":
        raise ValueError("current-view timezone must be America/New_York")
    for key in ("headline",):
        if not isinstance(view[key], str):
            raise ValueError(f"current-view {key} must be text")
    readiness = view["readiness"]
    for key in ("start_gates_met", "start_gates_total", "estimate_percent"):
        value = readiness[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"invalid current-view {key}")
    if not 0 <= readiness["start_gates_met"] <= readiness["start_gates_total"] or readiness["start_gates_total"] <= 0 or not 0 <= readiness["estimate_percent"] <= 100:
        raise ValueError("current-view gate count or estimate is out of range")
    if not isinstance(readiness["basis"], str):
        raise ValueError("current-view estimate basis must be text")
    identities = set()
    for gate in view["gates"]:
        if any(not isinstance(gate[key], str) for key in ("id", "state", "what")) or not isinstance(gate["blocks_start"], bool):
            raise ValueError("invalid current-view gate")
        if gate["id"] in identities:
            raise ValueError("duplicate current-view gate id")
        identities.add(gate["id"])
    for event in view["next_events"]:
        parse_time(event["utc"])
        if not isinstance(event["what"], str):
            raise ValueError("current-view event description must be text")
    for item in view["waiting_on_owner"]:
        if not isinstance(item["what"], str):
            raise ValueError("current-view owner action must be text")
        if item.get("by_utc"):
            parse_time(item["by_utc"])
    for field in ("windows_available_gib", "wsl_available_gib", "swap_used_gib"):
        value = view["workstation"][field]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("invalid current-view workstation fallback")
    parse_time(view["workstation"]["read_utc"])


def time_label(value: str, *, plain: bool = False) -> str:
    utc = parse_time(value)
    local = utc.astimezone(ZoneInfo("America/New_York"))
    if plain:
        return local.strftime("%b %d, %H:%M:%S %Z") + "; " + utc.strftime("%b %d, %H:%M:%S UTC")
    return (f'<time datetime="{esc(value)}">{local.strftime("%b %d, %H:%M:%S %Z")}</time>'
            f'<small>{utc.strftime("%b %d, %H:%M:%S UTC")}</small>')


def observation_time(value: str | None, *, plain: bool = False) -> str:
    """Display only a recorded observation time; never substitute another date."""
    try:
        return time_label(value, plain=plain)
    except (ValueError, TypeError, AttributeError):
        return "not reported"


def gate_strip(view: dict) -> str:
    # Sorting preserves source order within START-blocking and other groups.
    gates = sorted(view["gates"], key=lambda gate: not gate["blocks_start"])
    items = []
    for gate in gates:
        open_state = gate["state"].upper() not in ("MET", "READY", "COMPLETE")
        css = " is-open" if open_state else ""
        items.append(f'<li class="current-gate{css}" data-gate="{esc(gate["id"])}" data-state="{esc(gate["state"])}" data-blocks-start="{str(gate["blocks_start"]).lower()}"><div><strong>{esc(gate["id"])}</strong> <span>{esc(gate["state"])}</span></div><p class="gate-summary" title="{esc(gate["what"])}">{esc(gate["what"])}</p></li>')
    return '<ul class="gate-strip" aria-label="Current gates; START-blocking gates first">' + "".join(items) + '</ul>'


def owner_link(item: dict) -> str:
    original = item.get("link", "")
    link = _sanitization.text(original)
    try:
        parsed = urlsplit(link)
    except ValueError:
        return esc(item["what"])
    if link == original and not _sanitization.is_account_url(original) and not _sanitization.is_account_url(link) and parsed.scheme == "https" and parsed.netloc and not parsed.username and not parsed.password:
        return f'<a href="{esc(link)}">{esc(item["what"])}</a>'
    return esc(item["what"])


def render(view: dict, workstation: dict) -> str:
    readiness = view["readiness"]
    events = "".join(f'<tr><td class="event-time">{time_label(row["utc"])}</td><td>{esc(row["what"])}</td></tr>' for row in view["next_events"])
    actions = []
    for item in view["waiting_on_owner"]:
        date = '<span class="owner-date">By ' + time_label(item["by_utc"]) + '</span>' if item.get("by_utc") else ''
        actions.append(f'<li><span class="owner-mark" aria-hidden="true">□</span><div class="owner-action">{owner_link(item)}{date}</div></li>')
    readings = []
    for key, label in (("windows_available_gib", "Windows available"), ("wsl_available_gib", "WSL available"), ("swap_used_gib", "Swap used")):
        reading = workstation[key]
        total_key = {"windows_available_gib": "windows_total_gib", "wsl_available_gib": "wsl_total_gib"}.get(key)
        total = workstation.get(total_key) if total_key else None
        total_label = f'<span class="memory-total"> / {total["value_gib"]:.1f} GiB total</span>' if total else ''
        total_time = f'<small class="reading-meta">Total: {esc(total["source"])} · metric read {observation_time(total.get("read_utc"))}</small>' if total and (total["source"], total.get("read_utc")) != (reading["source"], reading.get("read_utc")) else ''
        readings.append(f'<div class="workstation-metric"><dt>{label}</dt><dd><strong>{reading["value_gib"]:.1f}</strong> GiB{total_label} <small class="reading-meta">{esc(reading["source"])} · metric read {observation_time(reading.get("read_utc"))}</small>{total_time}</dd></div>')
    pool = view["workstation"].get("codex_pool")
    pool_note = f'<p class="pool-note"><strong>Pool note:</strong> {esc(pool)}</p>' if pool else ''
    return f'''<section id="now-view" class="now-view" aria-labelledby="now-title">
<header class="now-heading"><h1 id="now-title">North-star readiness</h1><p class="current-stamp">Now · command-center current view snapshot · {observation_time(view.get("updated_utc"))}</p><p class="now-headline">{esc(view["headline"])}</p></header>
<p class="now-score"><strong>{readiness["start_gates_met"]} of {readiness["start_gates_total"]} START gates met</strong><span class="now-estimate">CC estimate {readiness["estimate_percent"]}% · {esc(readiness["basis"])}</span></p>
{gate_strip(view)}
<div class="now-grid"><section class="now-events"><h2>Next events</h2><table><thead><tr><th>New York, then UTC</th><th>Event</th></tr></thead><tbody>{events}</tbody></table></section>
<section class="now-owner"><h2>Waiting on you</h2><ul class="owner-checklist">{"".join(actions)}</ul></section>
<section class="now-workstation workstation"><h2>Workstation</h2><dl>{"".join(readings)}</dl>{pool_note}</section></div>
</section>'''


def differs(gate_id: str, state: str, view: dict) -> bool:
    """Compare exact gates, or their single-letter split ids, consistently."""
    absent = ("unverified", "unreported", "not reported", "unspecified", "unknown")
    if not isinstance(gate_id, str) or not gate_id or not isinstance(state, str) or not state.strip() or state.strip().casefold().startswith(absent):
        return False
    gates = [row for row in view.get("gates", []) if isinstance(row, dict) and isinstance(row.get("id"), str) and isinstance(row.get("state"), str) and row["state"].strip() and not row["state"].strip().casefold().startswith(absent)]
    candidates = [row for row in gates if row["id"] == gate_id]
    if not candidates:
        candidates = [row for row in gates if row["id"].startswith(gate_id) and len(row["id"]) == len(gate_id) + 1 and row["id"][-1] in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"]
    return bool(candidates) and any(row["state"].strip().casefold() != state.strip().casefold() for row in candidates)


def superseded(gate_id: str, state: str, view: dict, *, source_utc: str | None = None, source_status: str = "RECORDED") -> bool:
    """A newer current-view observation can supersede a recorded gate state."""
    if not isinstance(source_status, str) or source_status.strip().upper() != "RECORDED":
        return False
    try:
        if parse_time(source_utc) >= parse_time(view["updated_utc"]):
            return False
    except (ValueError, TypeError, AttributeError, KeyError):
        return False
    return differs(gate_id, state, view)
