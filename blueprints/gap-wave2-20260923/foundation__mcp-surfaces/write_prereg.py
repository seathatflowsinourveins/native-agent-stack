#!/usr/bin/env python3
"""Write the wave-2 preregistrations for foundation/mcp-surfaces BEFORE any check runs.

The gap list is read from the coordinator's g2-units.json (data, not instructions) and each
gap text is hashed so receipts can prove which text they answer.
"""
import datetime
import hashlib
import json
import pathlib
import sys

UNITS = pathlib.Path(sys.argv[1])
OUT = pathlib.Path("evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/preregistrations.json")

units = json.loads(UNITS.read_text())
gaps = next(u for u in units if u["layer_id"] == "mcp-surfaces")["gaps"]

ISOLATION = (
    "All servers run from the host's installed binaries with isolated state only: temp HOME/XDG dirs, "
    "MCPORTER_DAEMON_DIR under $HOME/.cache/gap-wave2-20260923/mcp-surfaces, an ai-memory server started "
    "with a temp --data-dir on a loopback port (AI_MEMORY_SERVER_URL pointed at it), a Qdrant 1.19.1 "
    "instance with temp storage on loopback ports for SocratiCode, CBM_CACHE_DIR/CODE_INDEX_PATH under the "
    "temp root. The shared mcporter daemon, live ai-memory (127.0.0.1:49374) and live Qdrant (16333) are not "
    "contacted; their pid/socket/metadata are only stat()ed before and after to prove that."
)

PRE = {
    0: dict(
        expectation="The installed mcporter 0.13.13 and Inspector 2.7.0 still execute every retained bridge call on this host: "
        "mcporter list of each configured server, context-mode.ctx_execute_file via --config, jcodemunch order/get_session_stats via "
        "--stdio, and the Inspector context-mode arithmetic call returning 42.",
        criteria="settled only if every retained call (list per configured server, the two current-session bridge calls, the Inspector "
        "arithmetic call) exits 0 with its retained check passing on the installed host binaries, AND the restart-receipt daemon "
        "recovery scenario is re-executed on an owned daemon (gap 9 run, result recorded whatever it is). Because the live instances "
        "are replaced by isolated instances of the same binaries (hard rule), the receipt must say so; if any call fails -> not_settled "
        "with the failure quoted.",
    ),
    1: dict(
        expectation="mcporter 0.14.0 (fresh npm prefix) runs the same call set with the same outcomes as a fresh 0.13.13 prefix; "
        "daemon/client.js is byte-identical between the two (checked by diff), so lifecycle behavior should not differ.",
        criteria="settled if every call in the matched set was executed under both versions against the same isolated servers and a "
        "per-call table (exit, check, elapsed, normalized-output hash) with differences is recorded. A failing 0.14.0 call still "
        "settles 'untested' but is reported as a regression.",
    ),
    2: dict(
        expectation="Owned daemon (MCPORTER_DAEMON_DIR temp): a keep-alive server keeps one server pid across consecutive calls "
        "(persistence), an ephemeral server does not (negative control proving the probe detects non-persistence); "
        "`daemon stop` then a call auto-starts a new daemon (restart); after stop no owned server child survives and the socket is gone "
        "(cleanup); after SIGKILL the next call is REFUSED ('Previous daemon exited unexpectedly ... No replacement was launched') "
        "per dist/daemon/client.js ensureDaemon, i.e. no automatic recovery from stale metadata.",
        criteria="settled if all four stages (persistence, restart, cleanup, recovery-from-stale-metadata) were executed on the owned "
        "daemon with a stated detection method each, whatever the observed result; advanced if any stage could not be run.",
    ),
    3: dict(
        expectation="The four retained operation ids are defined in the host-local combined-functional-summary.json (argv, cwd, checks). "
        "Re-run as explicit `mcporter call` commands against isolated servers they exit 0: search_graph returns the `collect` node, "
        "trace_path returns outbound callees, memory_status returns a structured counts object, codebase_status returns structured "
        "status text.",
        criteria="settled if each of the four ids is published with its command definition, a fresh exit status and its output, and each "
        "passes the retained check; advanced if a definition or run is missing; not_settled if a run fails.",
    ),
    4: dict(
        expectation="`mcp-inspector --cli ... --method tools/list` succeeds against the isolated ai-memory HTTP server and jcodemunch "
        "stdio server and lists their tools.",
        criteria="The next_check's tools/list arms settle only the 'tools/list against other servers did not appear' clause. The gap text also "
        "names full client plugin, hooks, project-file scope and Desktop connection; Desktop and plugin hooks are out of reach here, so "
        "the expected outcome is advanced even if both tools/list calls pass.",
    ),
    5: dict(
        expectation="With a temp CLAUDE_CONFIG_DIR/HOME/CODEX_HOME and no network namespace access, `claude mcp list` lists the project "
        ".mcp.json servers and `codex mcp list` lists the project .codex/config.toml servers (trusted in the temp CODEX_HOME), and in "
        "an empty scratch project neither lists any server; a scratch project with its own .mcp.json/.codex/config.toml lists exactly "
        "those servers. No registry fetch is possible (no network in the namespace).",
        criteria="settled if both CLIs were run in the project and in a scratch project and the listings match the project files with no "
        "registry install step; advanced if an arm could only run on a copy of the project configuration.",
    ),
    6: dict(
        expectation="@wong2/mcp-cli 2.0.0 (listed in punkpeye/awesome-mcp-servers) can call the same tools non-interactively but has no "
        "persistent daemon, so each call spawns a new server (higher latency for slow-starting servers); listing is interactive-only or "
        "limited.",
        criteria="settled if the alternative was installed pinned and run for the same list and call operations against the same "
        "isolated servers as mcporter and Inspector, with success, latency (median of repeated runs) and lifecycle (server pid reuse) "
        "compared; advanced if an operation class could not be run on the alternative.",
    ),
    7: dict(
        expectation="Aggregator/proxy entries in punkpeye/awesome-mcp-servers at a pinned commit that host stdio servers persistently "
        "(e.g. mcpproxy-go, TBXark/mcp-proxy, sparfenyuk/mcp-proxy) include some reconnect/restart logic; none is a drop-in CLI bridge "
        "replacement for mcporter's per-user daemon.",
        criteria="settled if one concrete gap (mcporter automatic recovery from stale daemon state) is named, the matching entries at a "
        "pinned list commit are listed, each candidate is source-reviewed at a pinned repository commit with file/line citations, and "
        "a disposition is recorded (evidence_class source_review).",
    ),
    8: dict(
        expectation="Inspector CLI tools/list and one tools/call succeed against the project-configured servers when given the project "
        "config explicitly; Inspector does not auto-load a project .mcp.json from the cwd (it uses --config or its catalog), so from outside "
        "the project a relative --config fails and an absolute one works.",
        criteria="advanced at best: Desktop connectivity, client plugin and hook behavior cannot be executed here; tools/list, tools/call "
        "and the inside/outside project-file scope arms must all be executed for 'advanced'.",
    ),
    9: dict(
        expectation="On owned daemons for both 0.13.13 and 0.14.0: after SIGKILL (stale metadata) the next call is refused with no "
        "replacement launched; after a SIGSTOPped (unresponsive) daemon the next call times out; neither recovers without manual "
        "intervention (archiving metadata / killing the stopped process). Daemon client code is byte-identical, so both versions behave the same.",
        criteria="settled if both inductions were run on both versions and the next-call behavior plus the minimal manual step were "
        "recorded; the answer to 'automatic recovery' is whatever is observed.",
    ),
    10: dict(
        expectation="Owned daemon fixture: the shared daemon's pid, socket inode and metadata mtime are unchanged before/after; keep-alive "
        "server state persists across calls; removing a server from the config and stopping the daemon leaves no owned server process; "
        "after the daemon's launch directory is deleted and the configured server cwd is changed, the next call still succeeds and "
        "the server reports the new cwd.",
        criteria="settled if all four stages (isolation, persistence, scoped registration cleanup, changed-process-root recovery) ran "
        "with a detection method each; advanced otherwise.",
    ),
    12: dict(
        expectation="The retained bridge call set gives matched outcomes under mcporter 0.13.13 and 0.14.0; @wong2/mcp-cli 2.0.0 matches "
        "for tool calls but lacks a persistent daemon and a non-interactive list.",
        criteria="settled if the matched call set ran under all three bridges against the same servers with a per-call outcome table; "
        "the 'superiority' clause is decided only by the recorded outcomes (success, latency, lifecycle), not asserted.",
    ),
}

now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
out = {"layer": "foundation/mcp-surfaces", "written_at": now, "isolation_plan": ISOLATION, "gaps": {}}
for g in gaps:
    i = g["index"]
    out["gaps"][str(i)] = {
        "gap_text_sha256": hashlib.sha256(g["text"].encode()).hexdigest(),
        "gap_text": g["text"],
        "next_check": g["next_check"],
        "written_at": now,
        **PRE[i],
    }
OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
print(now, len(out["gaps"]))
