#!/usr/bin/env python3
"""Gap 7 / gap 12 source review: pinned punkpeye/awesome-mcp-servers entries against one concrete MCP
surface gap (mcporter does not recover automatically from stale daemon state), plus the CLI-bridge
alternative used in the executed comparison (wong2/mcp-cli), and chrishayuk/mcp-cli (fix round 3).

Reads shallow clones under $HOME/.cache/gap-wave2-20260923/mcp-surfaces/{awesome-mcp-servers,review/*}
and writes the cited line ranges verbatim so the dispositions can be checked without the clones.

Usage: source_review.py OUT_JSON
"""
import json
import pathlib
import subprocess
import sys

CACHE = pathlib.Path.home() / ".cache/gap-wave2-20260923/mcp-surfaces"


def head(repo):
    return subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%H %cI"], capture_output=True, text=True).stdout.split()


def lines(repo, path, a, b):
    text = (repo / path).read_text(errors="replace").splitlines()
    return {"file": path, "lines": f"{a}-{b}", "text": "\n".join(text[a - 1:b])}


awesome = CACHE / "awesome-mcp-servers"
entries = {name: n for n, line in enumerate((awesome / "README.md").read_text().splitlines(), 1)
           for name in ("1mcp-app/agent", "ni-c/mcp-hub", "smart-mcp-proxy/mcpproxy-go", "wong2/mcp-cli", "chrishayuk/mcp-cli")
           if f"github.com/{name})" in line}
aw_sha, aw_date = head(awesome)
R = CACHE / "review"
out = {
    "concrete_gap": "mcporter 0.13.13/0.14.0 refuses to launch a replacement daemon after its daemon dies "
                    "('Previous daemon exited unexpectedly ... No replacement was launched', dist/daemon/client.js ensureDaemon); "
                    "recovery needs a manual metadata archive (observed in raw/lifecycle-mcporter-*.json stale_metadata_sigkill).",
    "list": {"repo": "https://github.com/punkpeye/awesome-mcp-servers", "commit": aw_sha, "committed_at": aw_date,
             "section_rule": "Aggregators section (README lines 138-279) entries that host local stdio servers persistently, "
                             "i.e. could own the daemon/recovery role; plus the CLI testers listed under Other Tools and Integrations.",
             "entry_lines": entries},
    "candidates": {},
}
c = {}
r = R / "1mcp-app_agent"
c["1mcp-app/agent"] = {"commit": head(r), "version": "0.39.0-beta.0 (package.json)", "citations": [
    lines(r, "src/core/server/runtimeLifecycle.ts", 147, 197),
    lines(r, "src/core/server/backendStdioSupervisor.ts", 93, 108),
    lines(r, "src/commands/run/index.ts", 6, 16)],
    "finding": "Tier-1 stale PID handling: a PID file whose process is dead (identity-checked) is removed automatically and the "
               "runtime reported not-running; a live-but-unreachable owner keeps its PID file (tier 2). Backend stdio servers "
               "restart on unexpected exit with backoff when restartOnExit is set. `1mcp run <server>/<tool>` calls tools "
               "against a RUNNING serve instance; it does not launch one.",
    "disposition": "keep-but-compare: closest match to the gap (automatic stale-PID cleanup without the manual archive step, "
                   "at the cost of mcporter's transport-retirement proof). Not adopted: no executed comparison yet.",
    "overturn": "An owned 1mcp serve + kill -9 + `1mcp run` fixture that recovers without a manual step while leaving no orphaned "
                "backend would make it a measured alternative for the recovery role."}
r = R / "ni-c_mcp-hub"
c["ni-c/mcp-hub"] = {"commit": head(r), "version": "0.11.3 (package.json)", "citations": [
    lines(r, "src/supervisor.ts", 119, 130),
    lines(r, "src/sandbox/container-spec.ts", 14, 19)],
    "finding": "Supervises child stdio servers (sleep when idle, backoff restart, give up after unused restarts) and publishes "
               "them over HTTPS/Streamable HTTP from one container. The cited container spec deliberately gives sandboxed children no "
               "Docker restart policy because the hub itself supervises them; recovery of the hub process's own state was not "
               "found in the reviewed files (not searched exhaustively).",
    "disposition": "rejected for this gap: a container HTTP hub, not a per-user CLI bridge; it does not address recovery of a "
                   "local bridge daemon's own stale state.",
    "overturn": "A deployment that must expose these servers to remote HTTP clients would make it relevant for a different role."}
r = R / "smart-mcp-proxy_mcpproxy-go"
c["smart-mcp-proxy/mcpproxy-go"] = {"commit": head(r), "citations": [
    lines(r, "cmd/mcpproxy-tray/main.go", 1694, 1698),
    lines(r, "internal/upstream/managed/client.go", 1826, 1840)],
    "finding": "Reconnects upstream servers (managed client tryReconnect with in-progress guard); its own core database-lock "
               "failure has no automatic stale-lock cleanup ('Could implement automatic stale lock cleanup here'). Ships a tray, "
               "web UI and self-update path (AUTOUPDATE.md).",
    "disposition": "rejected for this gap: upstream reconnect is not the missing piece, and its own stale-lock recovery is "
                   "explicitly unimplemented.",
    "overturn": "A release that implements and tests automatic stale core-lock recovery."}
r = R / "wong2_mcp-cli"
c["wong2/mcp-cli"] = {"commit": head(r), "version": "2.0.0 (package.json; src/cli.js and src/mcp.js byte-identical to the npm 2.0.0 tarball used in the run)",
    "citations": [lines(r, "src/cli.js", 9, 20), lines(r, "src/mcp.js", 189, 207)],
    "finding": "CLI tester. Non-interactive mode supports call-tool/read-resource/get-prompt only, always through a "
               "StdioClientTransport built from the config entry (an HTTP entry cannot be called non-interactively); listing "
               "exists only inside the interactive autocomplete prompt. No daemon: every call spawns the server.",
    "disposition": "used as the reviewed registry alternative in the executed comparison (gaps 6 and 12); not a replacement.",
    "overturn": "A release with non-interactive list and HTTP call support, re-run on the same call set."}
r = R / "chrishayuk_mcp-cli"  # fix round 3 (round-4 review finding 1): selected by the section rule, previously unreviewed
reconnect_refs = sorted(f"{q.relative_to(r)}:{n}" for q in (r / "src").rglob("*.py")
                        for n, line in enumerate(q.read_text(errors="replace").splitlines(), 1)
                        if "reconnect_on_failure" in line.lower() or "max_reconnect_attempts" in line.lower())
c["chrishayuk/mcp-cli"] = {"commit": head(r), "version": "0.20.1 (pyproject.toml)", "citations": [
    lines(r, "src/mcp_cli/run_command.py", 151, 173),
    lines(r, "src/mcp_cli/run_command.py", 205, 224),
    lines(r, "src/mcp_cli/tools/manager.py", 218, 223),
    lines(r, "src/mcp_cli/tools/manager.py", 786, 800),
    lines(r, "src/mcp_cli/config/defaults.py", 133, 137)],
    "reconnect_constant_references_in_src": reconnect_refs,
    "reconnect_search_method": "every *.py under src/ scanned case-insensitively for reconnect_on_failure / max_reconnect_attempts; the scan finds the "
                               "definitions themselves, so it can detect a use site if one exists",
    "finding": "Python CLI tester/chat client. Each command builds an in-process ToolManager/StreamManager that starts the "
               "configured servers and is always closed in `finally` when the command ends; there is no persistent bridge "
               "daemon, pid file or socket to go stale. A tool call that fails with a connection error is diagnosed with a "
               "health check and the status appended to the error; it is not reconnected. DEFAULT_RECONNECT_ON_FAILURE / "
               "DEFAULT_MAX_RECONNECT_ATTEMPTS are defined in config/defaults.py but have no other reference in src/ "
               "(outside src/ only examples/safety/tier2_efficiency_demo.py prints them).",
    "disposition": "rejected for this gap: no persistent daemon, so no stale daemon state to recover; like wong2/mcp-cli it "
                   "trades recovery for a fresh spawn per invocation. Not used in the executed comparison (wong2 was the "
                   "reviewed CLI alternative there).",
    "overturn": "A release that keeps servers alive across invocations (daemon or session reuse) with automatic recovery of that "
                "state, or that wires the declared reconnect defaults into the tool-call path."}
out["candidates"] = c
pathlib.Path(sys.argv[1]).write_text(json.dumps(out, indent=1, ensure_ascii=False).replace(str(pathlib.Path.home()), "$HOME") + "\n")
print(json.dumps({k: v["commit"] for k, v in c.items()}), entries)
