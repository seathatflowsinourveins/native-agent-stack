#!/usr/bin/env python3
"""Stage the packaged GPT-6 Codex lane for an ad-hoc review batch, the way the landscape sweep's build_args.py does it (its own stage_lane_home, not a copy of its logic):
<work>/codex-home (config.toml with the OmniRoute provider block and the rendered token MCP servers, the stack-worker profile, AGENTS.md), <work>/empty/.claude/settings.json and
<work>/staged.json {"codex": {...}} as codex_job.py reads it. The two project-note MCP servers (ai-memory, qmd) are switched off in the lane home so the reviewer reads only what the
prompt names. Prints names and hashes, never a key.
usage: stage_review_lane.py <checkout> <host-json> <work-dir> <model> <slots> <base-url>"""
import json, re, sys
from pathlib import Path

checkout, host, work, model = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3]).expanduser(), sys.argv[4]
slots, base_url = int(sys.argv[5]), sys.argv[6]
sys.path.insert(0, str(checkout / "tools/sota-convergence/landscape-sweep"))
import build_args  # noqa: E402  (the checkout's own module)

work.mkdir(parents=True, exist_ok=True)
work.chmod(0o700)
lane = build_args.stage_lane_home(work, model=model, base_url=base_url, host=host,
                                  profile=checkout / "adoption/templates/codex.stack-worker.config.toml", repo_root=checkout)
(work / "empty").mkdir(exist_ok=True)
config_path = work / "codex-home" / "config.toml"
text = config_path.read_text(encoding="utf-8")
switched = []
for name in ("ai-memory", "qmd"):
    header = re.search(r"^\[mcp_servers\.\"?" + re.escape(name) + r"\"?\]\s*$", text, re.M)
    if not header:
        continue
    text = text[:header.end()] + "\nenabled = false" + text[header.end():]
    switched.append(name)
config_path.write_text(text, encoding="utf-8")
lane["lane_home"]["config_sha256_after_switching_project_notes_off"] = build_args.sha256_bytes(config_path.read_bytes())
lane["lane_home"]["project_note_servers_off"] = switched
staged = {"schema_version": 1, "kind": "ad_hoc_review_lane", "codex": {"model": model, "effort": "max", "slots": slots, "timeout_s": 3600, **lane}}
(work / "staged.json").write_text(json.dumps(staged, indent=2, sort_keys=True) + "\n", encoding="utf-8")
servers = [entry.get("name") if isinstance(entry, dict) else entry for entry in lane["lane_home"]["mcp_servers"]]
print("staged", work.name, "| model", model, "| provider", lane["provider"], "| base", lane["base_url"], "| slots", slots)
print("mcp servers in the lane home:", servers)
print("switched off:", switched)
