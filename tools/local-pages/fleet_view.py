"""Present whitelist-only native fleet data as a compact operator view.

Source contracts: coop-fleet/1, cc-now/1 and lane-tiers/1. Design references:
Anthropic frontend-design683bc88e; Vercel web-design-guidelines063bee94.
"""
from __future__ import annotations

from html import escape
from typing import Any


def esc(value: Any) -> str:
    return escape(str(value), quote=True)


def text(value: Any) -> str:
    return "not reported" if value is None or value == "" else esc(value)


def number(value: Any, suffix: str = "") -> str:
    return "not reported" if value is None else f"{value:g}{suffix}"


def tier(value: Any) -> str:
    return "standard" if value == "default" else text(value)


def render(data: dict[str, Any]) -> str:
    lanes = data.get("lanes_live", [])
    parked = data.get("lanes_parked", [])
    reported = data.get("fleet_source") not in (None, "", "not reported")
    stamp = f'<time datetime="{esc(data["at"])}">{esc(data["at"])}</time>' if data.get("at") else 'not reported'
    versions = data.get("tiers", {}).get("versions", {})
    holds = versions.get("hold", {})
    lane_rows = []
    for row in lanes:
        held = f' <span class="version-hold" title="{esc(versions.get("hold_until", {}).get(row["lane"], "Version held by source policy"))}">hold</span>' if row["lane"] in holds else ''
        lane_rows.append(f'<tr data-lane="{esc(row["lane"])}"><th scope="row">{esc(row["lane"])}</th><td>{text(row.get("status"))}</td><td>{tier(row.get("tier"))}</td><td>{text(row.get("cli_version"))}{held}</td><td>{number(row.get("subagents_running"))}</td><td>{number(row.get("subagent_uncached_share_pct"), "%")}</td></tr>')
    parked_items = "".join(f'<li data-parked-lane="{esc(row["lane"])}"><strong>{esc(row["lane"])}</strong><small>{tier(row.get("tier"))} · CLI {text(row.get("cli_version"))}</small></li>' for row in parked)
    subgroups = data.get("claude_subagents_running", {})
    # CC source role: this named session belongs to the owner, not our workers.
    session_rows = data.get("claude_sessions", [])
    owner_count = sum(row.get("name") == "native-agent-stack-1a" for row in session_rows)
    worker_count = len(session_rows) - owner_count
    sessions = "".join(f'<li data-session-role="{"owner" if row.get("name") == "native-agent-stack-1a" else "worker"}"><strong>{"owner session (reports to CC)" if row.get("name") == "native-agent-stack-1a" else text(row.get("name"))}</strong> <span>{text(row.get("status"))}</span></li>' for row in session_rows) or '<li>not reported</li>'
    named_groups = []
    for key, label in (("coop", "Co-op"), ("cc", "Command center"), ("api_actions", "API actions")):
        group = subgroups.get(key, {})
        names = group.get("names")
        displayed = ', '.join(esc(name) for name in names) if names else 'none' if names == [] else 'not reported'
        named_groups.append(f'<li><strong>{label}:</strong> {displayed}<small>{text(group.get("source"))} · read {text(group.get("read_utc"))}</small></li>')
    reads = data.get("exec_reads_in_flight")
    read_items = ''.join(f'<li>{esc(item)}</li>' for item in reads) if reads else '<li>none reported</li>' if reads == [] else '<li>not reported</li>'
    sdk = data.get("sdk", {})
    spent = 'no spend yet' if sdk.get("status") == "no spend yet" else '$' + number(sdk.get("spend_usd")) if sdk.get("spend_usd") is not None else 'not reported'
    ceiling = '$' + number(sdk.get("ceiling_usd")) if sdk.get("ceiling_usd") is not None else 'not reported'
    actions = data.get("actions", {})
    runs = actions.get("runs", [])
    active = [row for row in runs if row.get("status") != "completed"]
    recent = active + [row for row in runs if row.get("status") == "completed"]
    visible_runs = recent[:6]
    action_rows = ''.join(f'<li><span>{text(row.get("workflowName"))}</span><strong>{text(row.get("conclusion") or row.get("status"))}</strong></li>' for row in visible_runs) or '<li>No matching runs in the retained result</li>' if actions.get("read_utc") else '<li>Actions observation not reported</li>'
    action_counts = f'{len(active)} active / {len(runs)} matching. Showing {len(visible_runs)}; ' if actions.get("read_utc") else ''
    pool = ''.join(f'<div class="pool-account"><strong>{text(row.get("account"))}</strong><span>{number(row.get("used_pct"), "% used")}</span></div>' for row in data.get("pool_accounts", []))
    policy = data.get("tiers", {}).get("parking", {})
    held_names = ', '.join(f'{esc(name)} {esc(version)}' for name, version in holds.items()) or 'none listed'
    return f'''<section id="fleet-view" class="fleet-view" aria-labelledby="fleet-title">
<header class="page-header"><h1 id="fleet-title">Worker fleet</h1><p class="fleet-stamp">{text(data.get("fleet_source"))} · {stamp}</p></header>
<div class="fleet-counts"><p><strong>{len(lanes) if reported else "not reported"}</strong> live Codex lanes</p><p><strong>{len(parked) if reported else "not reported"}</strong> parked</p><p><strong>{worker_count if reported else "not reported"}</strong> Claude worker sessions{f' + {owner_count} owner session' if owner_count else ''}</p><p><strong>{number(data.get("fresh_total_pct"), "%")}</strong> fresh pool used</p></div>
<div class="fleet-grid"><div class="fleet-left">
<section class="fleet-codex"><h2>Codex lanes</h2><div class="table-wrap fleet-table-wrap" tabindex="0" role="region" aria-label="Codex lanes; scroll horizontally on narrow screens"><table class="fleet-table"><thead><tr><th>Lane</th><th>State</th><th>Tier</th><th>CLI</th><th>Subagents running</th><th>Subagents' uncached share</th></tr></thead><tbody>{''.join(lane_rows)}</tbody></table></div></section>
<section class="fleet-parked"><h2>Parked lanes</h2><ul>{parked_items}</ul></section>
</div><div class="fleet-right">
<section class="fleet-claude"><h2>Claude sessions and subagents</h2><ul class="claude-sessions">{sessions}</ul><ul class="claude-subagents">{''.join(named_groups)}</ul></section>
<section class="fleet-reads"><h2>Reads in flight</h2><ul>{read_items}</ul></section>
<section class="fleet-sdk"><h2>SDK jobs and spend</h2><dl><div><dt>Jobs running</dt><dd>{number(sdk.get("jobs_running"))}</dd></div><div><dt>Spend</dt><dd>{spent}</dd></div><div><dt>Ceiling</dt><dd>{ceiling}</dd></div></dl><p class="fleet-source-note">Ledger read {text(sdk.get("read_utc"))}</p></section>
<section class="fleet-actions"><h2>Model Actions runs</h2><ul>{action_rows}</ul><p class="fleet-source-note">{action_counts}{text(actions.get("scope"))}. Read {text(actions.get("read_utc"))}{' · cached result is stale' if actions.get("stale") else ''}.</p></section>
</div></div>
<section class="fleet-pool"><h2>Pool accounts</h2>{pool}</section>
<p class="fleet-policy">Parking: {number(policy.get("idle_minutes_default"))} min idle; {number(policy.get("idle_minutes_when_memory_tight"))} min when Windows available &lt; {number(policy.get("windows_available_gib_below"))} GiB or WSL available &lt; {number(policy.get("wsl_available_gib_below"))} GiB. Default CLI {text(versions.get("default"))}; version holds: {held_names}. Parked CLI values are last reported observations, never inferred from policy.</p>
</section>'''
