"""Present whitelist-only native fleet data as a compact operator view.

Source contracts: coop-fleet/1, cc-now/1 and lane-tiers/1. Design references:
Anthropic frontend-design683bc88e; Vercel web-design-guidelines063bee94.
"""
from __future__ import annotations

from html import escape
import importlib.util
import ipaddress
import math
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit


_SANITIZER_SPEC = importlib.util.spec_from_file_location("local_fleet_view_sanitization", Path(__file__).with_name("sanitization.py"))
_sanitization = importlib.util.module_from_spec(_SANITIZER_SPEC)
_SANITIZER_SPEC.loader.exec_module(_sanitization)

# Native enum vocabulary reproduced with systemctl --state=help. Service
# substates retain their own type instead of borrowing timer/socket states.
_STATE_VALUES = {
    'LoadState': {'stub', 'loaded', 'not-found', 'bad-setting', 'error', 'merged', 'masked'},
    'ActiveState': {'active', 'reloading', 'inactive', 'failed', 'activating', 'deactivating', 'maintenance', 'refreshing'},
    'SubState': {'dead', 'condition', 'start-pre', 'start', 'start-post', 'running', 'exited', 'refresh-extensions', 'reload', 'reload-signal', 'reload-notify', 'reload-post', 'mounting', 'stop', 'stop-watchdog', 'stop-sigterm', 'stop-sigkill', 'stop-post', 'final-watchdog', 'final-sigterm', 'final-sigkill', 'failed', 'dead-before-auto-restart', 'failed-before-auto-restart', 'dead-resources-pinned', 'auto-restart', 'auto-restart-queued', 'cleaning'},
    'UnitFileState': {'enabled', 'enabled-runtime', 'linked', 'linked-runtime', 'alias', 'masked', 'masked-runtime', 'static', 'disabled', 'indirect', 'generated', 'transient', 'bad'},
}


def esc(value: Any) -> str:
    return escape(_sanitization.text(value), quote=True)


def text(value: Any) -> str:
    return "not reported" if value is None or value == "" else esc(value)


def number(value: Any, suffix: str = "") -> str:
    return "UNKNOWN" if value is None else f"{value:g}{suffix}"


def tier(value: Any) -> str:
    return "standard" if value == "default" else text(value)


def _metric_number(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return "UNKNOWN"
    if isinstance(value, float) and not math.isfinite(value):
        return "UNKNOWN"
    return esc(str(value) if isinstance(value, int) else format(value, '.6g'))


def _reading(item: Any) -> str:
    metric = item if isinstance(item, dict) else {}
    measured = metric.get('status') == 'reported' and metric.get('stale') is not True
    unit = metric.get('unit')
    raw = metric.get('value')
    if unit == 'state':
        accepted = isinstance(raw, str) and raw in _STATE_VALUES.get(metric.get('metric'), set())
        value = esc(raw) if measured and accepted else 'UNKNOWN'
    else:
        value = _metric_number(raw) if measured else 'UNKNOWN'
    reading = value + (' ' + esc(unit) if unit else '')
    reason = metric.get('reason')
    if reason:
        reading += '<small>' + esc(reason) + '</small>'
    return reading


def _measurement_time(item: dict) -> str:
    fields = [('Source sample', item.get('source_sample_utc')), ('Evaluated', item.get('evaluated_utc'))]
    lines = []
    for label, value in fields:
        time = f'<time datetime="{esc(value)}">{esc(value)}</time>' if value else 'UNKNOWN'
        lines.append(label + ': ' + time)
    window = item.get('window_seconds')
    if window is not None:
        lines.append('Window: ' + _metric_number(window) + ' seconds')
    return '<small>' + '<br>'.join(lines) + '</small>'


def _tracking_table(caption: str, headers: list[str], rows: list[str]) -> str:
    head = ''.join('<th scope="col">' + esc(header) + '</th>' for header in headers)
    return f'<div class="table-wrap fleet-table-wrap" tabindex="0" role="region" aria-label="{esc(caption)}"><table class="fleet-table"><caption>{esc(caption)}</caption><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def _grafana_origin(raw: Any):
    if not isinstance(raw, str) or not raw or _sanitization.text(raw) != raw:
        return None
    if any(char.isspace() or ord(char) < 32 for char in raw) or any(char in raw for char in '<>"\\'):
        return None
    try:
        parsed = urlsplit(raw)
        host = (parsed.hostname or '').lower()
        if parsed.username is not None or parsed.password is not None or not host or _sanitization.is_account_url(raw):
            return None
        if host in {'127.0.0.1', 'localhost', '::1'}:
            if parsed.scheme not in {'http', 'https'} or parsed.port != 21301:
                return None
        else:
            if parsed.scheme != 'https' or '.' not in host or host.endswith(('.local', '.internal', '.lan', '.test', '.invalid')):
                return None
            try:
                if not ipaddress.ip_address(host).is_global:
                    return None
            except ValueError:
                pass
        return parsed.scheme, host, parsed.port
    except ValueError:
        return None


def _grafana_links(grafana: Any) -> str:
    source = grafana if isinstance(grafana, dict) else {}
    origin = _grafana_origin(source.get('base_url'))
    links = []
    for row in source.get('links') or []:
        if not isinstance(row, dict):
            continue
        raw = row.get('url')
        valid = origin is not None and _grafana_origin(raw) == origin
        if valid:
            parsed = urlsplit(raw)
            valid = parsed.path.startswith(('/d/', '/d-solo/')) or parsed.path == '/explore'
            parameters = parse_qsl(parsed.query)
            valid &= not any(any(word in key.lower() for word in ('token', 'secret', 'password', 'credential', 'api_key', 'auth')) for key, _ in parameters)
            valid &= all(_sanitization.text(key) == key and _sanitization.text(value) == value for key, value in parameters)
        label = esc(row.get('title') or row.get('uid') or 'Grafana')
        links.append(f'<a href="{esc(raw)}" rel="noreferrer">{label}</a>' if valid else label + ' · link UNKNOWN')
    body = ' · '.join(links) if links else 'UNKNOWN'
    return '<p class="fleet-source-note">Grafana: ' + body + '. Read ' + text(source.get('read_utc')) + ('. ' + esc(source['reason']) if source.get('reason') else '') + '</p>'


def _tracking(data: dict) -> str:
    tracking = data.get('tracking')
    if not isinstance(tracking, dict):
        return ''
    if tracking.get('schema') != 'fleet-tracking/1':
        return '<section id="fleet-tracking"><h2>Fleet tracking</h2><p>UNKNOWN: tracking source is unavailable.</p></section>'
    hcom = tracking.get('hcom') if isinstance(tracking.get('hcom'), dict) else {}
    agents = hcom.get('agents')
    agent_rows = []
    for item in agents if isinstance(agents, list) else []:
        if not isinstance(item, dict):
            continue
        agent_rows.append(f'<tr data-hcom-name="{esc(item.get("name"))}"><th scope="row">{text(item.get("name"))}<small>{text(item.get("base_name"))}</small></th><td>{text(item.get("tool"))}</td><td>{text(item.get("tag"))}</td><td>{text(item.get("status"))}</td><td>{_metric_number(item.get("status_age_seconds"))}</td><td>{text(item.get("created_at"))}</td></tr>')
    hcom_known = hcom.get('status') == 'reported' and isinstance(agents, list)
    roster_count = _metric_number(hcom.get('count')) if hcom_known else 'UNKNOWN'
    roster = '<section class="fleet-codex" id="fleet-hcom"><h2>Live hcom roster</h2><p class="fleet-source-note">Published count: ' + roster_count + '. Read ' + text(hcom.get('read_utc')) + ('. ' + esc(hcom['reason']) if hcom.get('reason') else '') + '</p>'
    roster += _tracking_table('Every published hcom agent', ['Agent / base name', 'Client', 'Lane tag', 'Published state', 'State age (seconds)', 'Created at'], agent_rows) if agent_rows else '<p>' + ('0 published agents' if hcom_known else 'UNKNOWN') + '</p>'
    roster += '</section>'
    telemetry_rows = []
    for lane in tracking.get('lanes') or []:
        if not isinstance(lane, dict):
            continue
        clients = lane.get('clients')
        for client in clients if isinstance(clients, list) and clients else [{}]:
            if not isinstance(client, dict):
                continue
            tokens = client.get('tokens')
            token_readings = []
            for item in tokens if isinstance(tokens, list) else []:
                if not isinstance(item, dict):
                    continue
                token_readings.append('<li data-tracking-metric="token" data-token-type="' + esc(item.get('token_type')) + '"><strong>' + text(item.get('token_type')) + ':</strong> ' + _reading(item) + _measurement_time(item) + '</li>')
            token_cell = '<ul>' + ''.join(token_readings) + '</ul>' if token_readings else 'UNKNOWN'
            invocation = client.get('invocations') if isinstance(client.get('invocations'), dict) else {}
            calls = _reading(invocation) + _measurement_time(invocation)
            if invocation.get('scope'):
                calls += '<small>' + esc(invocation['scope']) + '</small>'
            telemetry_rows.append('<tr data-tracking-lane="' + esc(lane.get('lane')) + '" data-tracking-client="' + esc(client.get('client')) + '"><th scope="row">' + text(lane.get('lane')) + '</th><td>' + text(client.get('client')) + '</td><td>' + token_cell + '</td><td data-tracking-metric="invocations">' + calls + '</td></tr>')
    telemetry = '<section class="fleet-codex" id="fleet-lane-metrics"><h2>Lane token and MCP rates</h2><p class="fleet-source-note">Telemetry retains its published lane labels and measurement windows. Token types remain separate; source sample time describes the metric observation.</p>'
    telemetry += _tracking_table('All published lane and client measurements', ['Published lane', 'Client', 'Token types and rates', 'Native MCP calls'], telemetry_rows) if telemetry_rows else '<p>UNKNOWN: lane measurements are not reported.</p>'
    query_rows = []
    for item in tracking.get('query_observations') or []:
        if not isinstance(item, dict):
            continue
        query_rows.append('<tr data-tracking-query="' + esc(item.get('measurement')) + '"><th scope="row">' + text(item.get('client')) + '</th><td>' + text(item.get('measurement')) + '</td><td>' + text(item.get('status')) + '</td><td>' + _metric_number(item.get('series_count')) + '</td><td>' + text(item.get('reason')) + '<small>Read ' + text(item.get('read_utc')) + '</small></td></tr>')
    if query_rows:
        telemetry += '<details><summary>Metric source availability</summary>' + _tracking_table('Published metric query availability', ['Client', 'Measurement', 'Source status', 'Returned series', 'Reason and source time'], query_rows) + '</details>'
    telemetry += '</section>'
    service_rows = []
    for service in tracking.get('services') or []:
        if not isinstance(service, dict):
            continue
        observations = service.get('observations')
        for item in observations if isinstance(observations, list) and observations else [{}]:
            if not isinstance(item, dict):
                continue
            service_rows.append('<tr data-tracking-service="' + esc(service.get('id')) + '"><th scope="row">' + text(service.get('title') or service.get('id')) + '</th><td>' + text(item.get('metric')) + '</td><td>' + _reading(item) + '</td><td>' + text(item.get('scope')) + '</td><td>' + _measurement_time(item) + '</td></tr>')
    services = '<section class="fleet-sdk" id="fleet-model-services"><h2>Model and memory services</h2><p class="fleet-source-note">Each observation retains the measurement scope supplied by its source.</p>'
    services += _tracking_table('Published model-service observations', ['Service', 'Observed metric', 'Reading', 'Measurement scope', 'Source and evaluation time'], service_rows) if service_rows else '<p>UNKNOWN: service observations are not reported.</p>'
    services += '</section>'
    limits = tracking.get('limitations')
    notes = '<ul class="fleet-source-note">' + ''.join('<li>' + esc(item) + '</li>' for item in limits) + '</ul>' if isinstance(limits, list) and limits else ''
    return '<div id="fleet-tracking"><p class="fleet-stamp">Tracking evaluated ' + text(tracking.get('observed_utc')) + '</p>' + roster + telemetry + services + _grafana_links(tracking.get('grafana')) + notes + '</div>'


def render(data: dict[str, Any]) -> str:
    lane_source, parked_source, session_source = (data.get(key) for key in ("lanes_live", "lanes_parked", "claude_sessions"))
    lanes = lane_source if isinstance(lane_source, list) else []
    parked = parked_source if isinstance(parked_source, list) else []
    availability = data.get("availability") if isinstance(data.get("availability"), dict) else {}
    reported = data.get("fleet_source") not in (None, "", "not reported")
    def known(name, rows):
        section = availability.get(name)
        status = section.get("status") if isinstance(section, dict) else None
        return isinstance(rows, list) and (status in ("reported", "snapshot fallback") if status is not None else reported)
    stamp = f'<time datetime="{esc(data["at"])}">{esc(data["at"])}</time>' if data.get("at") else 'not reported'
    tiers = data.get("tiers") if isinstance(data.get("tiers"), dict) else {}
    versions = tiers.get("versions") if isinstance(tiers.get("versions"), dict) else {}
    holds = versions.get("hold", {})
    lane_rows = []
    for row in lanes:
        fast = tiers.get("fast")
        mapped_tier = "fast" if isinstance(fast, list) and row["lane"] in fast else tier(tiers.get("default")) if isinstance(fast, list) else "UNKNOWN"
        running_tier = tier(row.get("tier"))
        tier_cell = running_tier if mapped_tier == running_tier or mapped_tier == "not reported" else f'{running_tier} / {mapped_tier}'
        mapped_cli = holds.get(row["lane"], versions.get("default"))
        running_cli = row.get("cli_version")
        cli_cell = text(running_cli) if not mapped_cli or mapped_cli == running_cli else f'{text(running_cli)} / {text(mapped_cli)}'
        held = f' <span class="version-hold" title="{esc(versions.get("hold_until", {}).get(row["lane"], "Version held by source policy"))}">hold</span>' if row["lane"] in holds else ''
        lane_rows.append(f'<tr data-lane="{esc(row["lane"])}"><th scope="row">{esc(row["lane"])}</th><td>{text(row.get("status"))}</td><td>{tier_cell}</td><td>{cli_cell}{held}</td><td>{number(row.get("subagents_running"))}</td><td>{number(row.get("subagent_uncached_share_pct"), "%")}</td></tr>')
    parked_items = "".join(f'<li data-parked-lane="{esc(row["lane"])}"><strong>{esc(row["lane"])}</strong><small>{tier(row.get("tier"))} · CLI {text(row.get("cli_version"))}</small></li>' for row in parked)
    subgroups = data.get("claude_subagents_running") if isinstance(data.get("claude_subagents_running"), dict) else {}
    # CC source role: this named session belongs to the owner, not our workers.
    session_rows = session_source if isinstance(session_source, list) else []
    owner_count = sum(row.get("name") == "native-agent-stack-1a" for row in session_rows) if known("claude_sessions", session_source) else 0
    worker_count = len(session_rows) - owner_count
    sessions = "".join(f'<li data-session-role="{"owner" if row.get("name") == "native-agent-stack-1a" else "worker"}"><strong>{"owner session (reports to CC)" if row.get("name") == "native-agent-stack-1a" else text(row.get("name"))}</strong> <span>{text(row.get("status"))}</span></li>' for row in session_rows) or '<li>none reported</li>' if known("claude_sessions", session_source) else '<li>UNKNOWN</li>'
    named_groups = []
    for key, label in (("coop", "Co-op"), ("cc", "Command center"), ("api_actions", "API actions")):
        group = subgroups.get(key) if isinstance(subgroups.get(key), dict) else {}
        names = group.get("names")
        displayed = ', '.join(esc(name) for name in names) if names else 'none' if names == [] else 'not reported'
        named_groups.append(f'<li><strong>{label}:</strong> {displayed}<small>{text(group.get("source"))} · read {text(group.get("read_utc"))}</small></li>')
    reads = data.get("exec_reads_in_flight")
    read_items = ''.join(f'<li>{text(item.get("name"))} · {tier(item.get("tier"))}</li>' if isinstance(item, dict) else f'<li>{esc(item)}</li>' for item in reads) if reads else '<li>none reported</li>' if reads == [] else '<li>UNKNOWN</li>'
    sdk = data.get("sdk") if isinstance(data.get("sdk"), dict) else {}
    spent = 'no spend yet' if sdk.get("status") == "no spend yet" else '$' + number(sdk.get("spend_usd")) if sdk.get("spend_usd") is not None else 'not reported'
    ceiling = '$' + number(sdk.get("ceiling_usd")) if sdk.get("ceiling_usd") is not None else 'not reported'
    stop = '<div><dt>Stop and report</dt><dd>$' + number(sdk["stop_and_report_at_usd"]) + '</dd></div>' if sdk.get("stop_and_report_at_usd") is not None else ''
    actions = data.get("actions") if isinstance(data.get("actions"), dict) else {}
    runs = actions.get("runs") if isinstance(actions.get("runs"), list) else []
    active = [row for row in runs if row.get("status") != "completed"]
    recent = active + [row for row in runs if row.get("status") == "completed"]
    visible_runs = recent[:6]
    action_rows = ''.join(f'<li><span>{text(row.get("workflowName"))}</span><strong>{text(row.get("conclusion") or row.get("status"))}</strong></li>' for row in visible_runs) or '<li>No matching runs in the retained result</li>' if actions.get("read_utc") else '<li>Actions observation not reported</li>'
    action_counts = f'{len(active)} active / {len(runs)} matching. Showing {len(visible_runs)}; ' if actions.get("read_utc") else ''
    pool_source = data.get("pool_accounts")
    pool = (''.join(f'<div class="pool-account"><strong>{text(row.get("account"))}</strong><span>{number(row.get("used_pct"), "% used")}</span></div>' for row in pool_source) or '<p>No recorded pool accounts</p>') if known("pool_accounts", pool_source) else '<p>UNKNOWN</p>'
    policy = tiers.get("parking") if isinstance(tiers.get("parking"), dict) else {}
    held_names = ', '.join(f'{esc(name)} {esc(version)}' for name, version in holds.items()) or 'none listed'
    section_notes = ''.join('<li>' + esc(name) + ': ' + text(row.get("status")) + ' · ' + text(row.get("source")) + ' · read ' + text(row.get("read_utc")) + (' · ' + text(row.get("reason")) if row.get("reason") else '') + '</li>' for name, row in availability.items() if isinstance(row, dict))
    return f'''<section id="fleet-view" class="fleet-view" aria-labelledby="fleet-title">
<header class="page-header"><h1 id="fleet-title">Worker fleet</h1><p class="fleet-stamp">{text(data.get("fleet_source"))} · {stamp}</p></header>
<div class="fleet-counts"><p><strong>{len(lanes) if known("lanes_live", lane_source) else "UNKNOWN"}</strong> live Codex lanes</p><p><strong>{len(parked) if known("lanes_parked", parked_source) else "UNKNOWN"}</strong> parked</p><p><strong>{worker_count if known("claude_sessions", session_source) else "UNKNOWN"}</strong> Claude worker sessions{f' + {owner_count} owner session' if owner_count else ''}</p><p><strong>{number(data.get("fresh_total_pct"), "%")}</strong> sum of per-account fresh-pool percentages (reference 200)</p></div>
<ul class="fleet-source-note">{section_notes}</ul>
{_tracking(data)}
<div class="fleet-grid"><div class="fleet-left">
<section class="fleet-codex"><h2>Codex lanes</h2><div class="table-wrap fleet-table-wrap" tabindex="0" role="region" aria-label="Codex lanes; scroll horizontally on narrow screens"><table class="fleet-table"><thead><tr><th>Lane</th><th>State</th><th>Tier: running / map</th><th>CLI: running / map</th><th>Subagents running</th><th>Subagents' uncached share</th></tr></thead><tbody>{''.join(lane_rows)}</tbody></table></div></section>
<section class="fleet-parked"><h2>Parked lanes</h2><ul>{parked_items}</ul></section>
</div><div class="fleet-right">
<section class="fleet-claude"><h2>Claude sessions and subagents</h2><ul class="claude-sessions">{sessions}</ul><ul class="claude-subagents">{''.join(named_groups)}</ul></section>
<section class="fleet-reads"><h2>Reads in flight</h2><ul>{read_items}</ul></section>
<section class="fleet-sdk"><h2>SDK jobs and spend</h2><dl><div><dt>Jobs running</dt><dd>{number(sdk.get("jobs_running"))}</dd></div><div><dt>Spend</dt><dd>{spent}</dd></div><div><dt>Ceiling</dt><dd>{ceiling}</dd></div>{stop}</dl><p class="fleet-source-note">Ledger read {text(sdk.get("read_utc"))}</p></section>
<section class="fleet-actions"><h2>Model Actions runs</h2><ul>{action_rows}</ul><p class="fleet-source-note">{action_counts}{text(actions.get("scope"))}. Read {text(actions.get("read_utc"))}{' · cached result is stale' if actions.get("stale") else ''}.</p></section>
</div></div>
<section class="fleet-pool"><h2>Pool accounts</h2>{pool}</section>
<p class="fleet-policy">Parking: {number(policy.get("idle_minutes_default"))} min idle; {number(policy.get("idle_minutes_when_memory_tight"))} min when Windows available &lt; {number(policy.get("windows_available_gib_below"))} GiB or WSL available &lt; {number(policy.get("wsl_available_gib_below"))} GiB. Default CLI {text(versions.get("default"))}; version holds: {held_names}. Parked CLI values are last reported observations, never inferred from policy.</p>
</section>'''
