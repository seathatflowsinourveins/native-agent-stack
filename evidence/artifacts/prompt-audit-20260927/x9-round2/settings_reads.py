"""List, per comparison run, which client configuration files its Bash commands named (names only, no contents).

usage: settings_reads.py RESULTS_JSON [RESULTS_JSON...] OUT_JSON
The compact results drop Bash command text, because K2 and K4 commands printed client settings. This keeps only
the configuration file names each run's commands mention, so the claim that K2 and K4 runs read them can be
checked from retained data.
"""
import json
import re
import sys
from pathlib import Path

NAMES = re.compile(r"(?:~|\$HOME|\$\{CLAUDE_CONFIG_DIR[^}]*\})?/?\.claude\.json|\.mcp\.json|settings(?:\.local)?\.json"
                   r"|installed_plugins\.json|known_marketplaces\.json|plugins/cache")
out = {"note": __doc__.split("\n\n", 1)[1].strip(), "pattern": NAMES.pattern, "runs": []}
for path in sys.argv[1:-1]:
    for r in json.loads(Path(path).read_text())["results"]["results"]:
        s = json.loads(r["response"]["output"])
        named = sorted({re.sub(r"^(?:\$HOME|\$\{CLAUDE_CONFIG_DIR[^}]*\})", "~", m.group(0))
                        for c in s.get("calls") or [] if c.get("name") == "Bash"
                        for m in NAMES.finditer(c.get("command") or "")})
        out["runs"].append({"arm": r["provider"]["label"].removeprefix("arm-"), "case": r["vars"].get("case"),
                            "transcript": s.get("transcript"), "bash_calls": sum(c.get("name") == "Bash"
                                                                                for c in s.get("calls") or []),
                            "config_files_named": named})
summary = {}
for x in out["runs"]:
    k = f"{x['case']} {x['arm']}"
    summary.setdefault(k, [0, 0])
    summary[k][0] += bool(x["config_files_named"])
    summary[k][1] += 1
out["runs_naming_a_config_file"] = {k: f"{a} of {n}" for k, (a, n) in sorted(summary.items())}
Path(sys.argv[-1]).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
print(json.dumps(out["runs_naming_a_config_file"]))
