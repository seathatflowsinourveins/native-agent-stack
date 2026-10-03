#!/usr/bin/env python3
"""Build one pipeline script per missing slot: a discovery unit, then two blind judge units in different seeded orders.

The judge prompt, criteria and output schema are the GPT lane's own first-round contract (copied from a finished unit of
blind-sol-ultra-recommendations), so the missing slots are judged exactly as the other layers were. The only differences
are the route (the gateway pool instead of the native login, to spread load) and effort max instead of ultra.
Usage: make_gap_units.py <gap-slots.json> <output folder> <blind-run folder>
"""
import hashlib
import json
import pathlib
import random
import sys

spec = json.loads(pathlib.Path(sys.argv[1]).read_text())
out = pathlib.Path(sys.argv[2])
blind = pathlib.Path(sys.argv[3])
home = str(pathlib.Path.home())
judge_schema = blind / "judge-strict.schema.json"
ref_prompt = (blind / "order-1" / "hosting-services" / "prompt.txt").read_text()
judge_head = ref_prompt.split("Packets:\n")[0]
assert "blind merit judge" in judge_head and judge_schema.exists()

discover_schema = {
    "type": "object", "additionalProperties": False, "required": ["candidates", "search_notes"],
    "properties": {
        "candidates": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["name", "repository", "why_candidate"],
            "properties": {"name": {"type": "string"}, "repository": {"type": "string"}, "why_candidate": {"type": "string"}}}},
        "search_notes": {"type": "string"}}}
(out / "schemas").mkdir(parents=True, exist_ok=True)
(out / "schemas" / "discover.schema.json").write_text(json.dumps(discover_schema, indent=1))

CODEX = ("rtk proxy codex exec --ignore-user-config --strict-config --sandbox workspace-write --skip-git-repo-check -C '{d}' "
         "-m cx/gpt-6.1-sol -c 'model_provider=\"omniroute\"' -c 'model_providers.omniroute.name=\"OmniRoute\"' "
         "-c 'model_providers.omniroute.base_url=\"http://127.0.0.1:20128/v1\"' -c 'model_providers.omniroute.requires_openai_auth=false' "
         "-c 'model_providers.omniroute.wire_api=\"responses\"' -c 'model_providers.omniroute.supports_standalone_web_search=true' "
         "-c 'model_reasoning_effort=\"max\"' -c sandbox_workspace_write.network_access=true -c project_doc_max_bytes=0 "
         "-c features.hooks=false -c features.plugin_hooks=false -c features.standalone_web_search=true -c 'web_search=\"live\"' "
         "-c 'mcp_servers.context-mode.command=\"node\"' "
         "-c 'mcp_servers.context-mode.args=[\"" + home + "/.codex/plugins/cache/context-mode/context-mode/1.0.169/start.mjs\"]' "
         "-c 'mcp_servers.context-mode.env.CONTEXT_MODE_PROJECT_DIR=\"{d}\"' "
         "--output-schema '{schema}' --output-last-message '{d}/last.json' --json - < '{d}/prompt.txt' > '{d}/events.jsonl' 2> '{d}/stderr'")

(out / "pipelines").mkdir(exist_ok=True)
for s in spec["slots"]:
    lid = s["layer_id"]
    dd = out / "discover" / lid
    dd.mkdir(parents=True, exist_ok=True)
    seeds = "\n".join(f"- {n}: {u}" for n, u in sorted(s["seeds"]))
    (dd / "prompt.txt").write_text(
        "You are building the candidate list for a blind merit judgment of open-source repositories. You do not rank and you do not recommend.\n\n"
        f"Slot: {s['title']}\nRequirement: {s['requirement']}\nTarget hosts: {spec['target_hosts']}\n\n"
        "Task: list every maintained open-source candidate that could meet the requirement on the target host. A candidate is a public "
        "repository, or an open-weight model with a public repository or model card. Verify each one from primary sources (the GitHub API "
        "through `gh api repos/OWNER/REPO` and `repos/OWNER/REPO/releases/latest`, the project's README or the model card): it must exist, "
        "must not be archived, and must have a release or default-branch commit in the last 90 days. Include a seed below only if it "
        "passes those checks, and add the candidates the seeds miss, especially ones released in the last six months. Use the canonical "
        "repository URL. Give at least 3 and at most 12 candidates. When the requirement says 'or establish that ... is not needed', also "
        "include the candidate named 'No additional component' with an empty repository.\n\n"
        "Rules: do not open files of the local working directory or anything under it; your evidence is upstream public sources only. "
        "Budget: at most 6 web searches, 8 page fetches and 30 GitHub API calls. In why_candidate give one factual line (what it is, latest "
        "release and date), with no comparison and no praise.\n\n"
        f"Seeds (unordered starting points, not preferences):\n{seeds}\n")
    cmds = ["#!/usr/bin/env bash", "set -u", f"cd '{out}' || exit 1",
            f"if [ ! -s '{dd}/last.json' ]; then " + CODEX.format(d=dd, schema=out / "schemas" / "discover.schema.json") + "; fi",
            f"python3 -B '{out}/make_packets.py' '{sys.argv[1]}' '{out}' '{lid}' || {{ echo '{{\"unit_id\":\"{lid}\",\"stage\":\"packets\",\"exit\":1}}'; exit 1; }}"]
    for order in ("order-1", "order-2"):
        jd = out / order / lid
        jd.mkdir(parents=True, exist_ok=True)
        (jd / "prompt.txt").write_text(judge_head + f"Packets:\n- {lid}: {jd}/packet.json\n")
        cmds.append(f"( if [ ! -s '{jd}/last.json' ]; then " + CODEX.format(d=jd, schema=judge_schema) +
                    f"; fi; echo '{{\"unit_id\":\"{order}:{lid}\",\"native_exit_code\":'$?'}}' ) &")
    cmds += ["wait"]
    (out / "pipelines" / f"{lid}.sh").write_text("\n".join(cmds) + "\n")
print("pipelines:", len(spec["slots"]))
