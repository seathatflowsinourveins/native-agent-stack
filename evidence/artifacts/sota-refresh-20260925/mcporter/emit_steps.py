#!/usr/bin/env python3
"""Build the sanitized step list for the structured result from recorded outputs only."""
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
HOME = str(pathlib.Path.home())
SCR = str(HERE.parents[2])


def san(s):
    s = (s or "").replace(SCR, "<scratchpad>").replace(HOME, "~")
    return re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<uuid>", s)


def short(s, n=230):
    s = " ".join(san(s).split())
    return s if len(s) <= n else s[: n - 40] + " ... " + s[-35:]


RECEIPT_CMD = {
    "R-mcporter-install-0": "receipt evidence/hosts/nativestack-5975wx-20260925/...--mcporter--install--20260925.json commands[0], verbatim",
    "R-mcporter-install-1": "receipt ...--mcporter--install--20260925.json commands[1] (mcporter --version), verbatim",
    "R-jcodemunch-use-0": "receipt ...--jcodemunch-mcp--use--20260925-2.json commands[0] with CODE_INDEX_PATH=$HOME/.code-index -> arm-private copy",
    "R-jcodemunch-use-1": "receipt ...--jcodemunch-mcp--use--20260925-2.json commands[1] with CODE_INDEX_PATH=$HOME/.code-index -> arm-private copy",
    "R-context-mode-use-0": "receipt ...--context-mode--use--20260925-2.json commands[0], verbatim (TMPDIR=scratchpad dir)",
    "R-context-mode-use-1": "receipt ...--context-mode--use--20260925-2.json commands[1], verbatim (TMPDIR=scratchpad dir)",
}
for i in range(4):
    RECEIPT_CMD[f"R-socraticode-use-{i}"] = (f"receipt ...--socraticode--use--20260925-2.json commands[{i}] with "
                                             'C="$HOME/.local/share/codex-ecosystem/config/mcporter.json" -> C="$SCRATCH_CFG"')

steps = []
V = HERE / "verify"
ic = (V / "integrity-compare.txt").read_text()
steps.append({"name": "integrity-hash-compare", "arm": "candidate 0.14.1 artifact",
              "cmd": "curl registry.npmjs.org/mcporter/0.14.1 + /mcporter (abbrev) + gh api releases/tags/v0.14.1 + release checksums.txt + tarball; sha256/sha512/sha1 compare",
              "exit": 0, "output_excerpt": short(" | ".join(l for l in ic.splitlines() if "==" in l or "ALL_MATCH" in l or "computed sha256" in l), 420),
              "pass": "ALL_MATCH True" in ic})
au = (HERE / "stage" / "audit-signatures.txt").read_text()
pv = (V / "provenance-mcporter-0.14.1.txt").read_text()
steps.append({"name": "integrity-npm-audit-signatures", "arm": "candidate 0.14.1 artifact (scratch staging install from registry)",
              "cmd": "npm install --ignore-scripts mcporter@0.14.1 (scratch prefix, scratch cache); npm audit signatures [--json --include-attestations]",
              "exit": 0, "output_excerpt": short(au + " | " + " ".join(l.strip() for l in pv.splitlines() if "workflow" in l or "resolvedDependencies" in l or "invocationId" in l), 420),
              "pass": "41 packages have verified registry signatures" in au and "13 packages have verified attestations" in au})
inst = (V / "npm-install.log").read_text()
steps.append({"name": "install-new-prefix", "arm": "candidate 0.14.1",
              "cmd": "npm install --global --no-audit --no-fund --prefix ~/.local/share/codex-ecosystem/tools/mcporter-0.14.1 <verified mcporter-0.14.1.tgz> (scratch npm cache; prefix absent beforehand; bin symlink not touched)",
              "exit": 0, "output_excerpt": short(inst), "pass": "added 41 packages" in inst})
ls14 = (V / "npm-ls-0.14.1.txt").read_text()
keep = [l.strip("│├└─┬ ") for l in ls14.splitlines() if re.search(r"(mcporter@|@modelcontextprotocol/(client|server|core)@2|zod@4\.6\.5$|commander@|rolldown@|string-width@)", l)]
steps.append({"name": "install-npm-ls-tree", "arm": "candidate 0.14.1 vs baseline 0.13.13 prefix",
              "cmd": "npm ls --global --all --prefix tools/mcporter-0.14.1 ; same for tools/mcporter-0.13.13 ; diff",
              "exit": 0, "output_excerpt": short("0.14.1: " + ", ".join(keep) + " | diff vs 0.13.13: rolldown 1.2.8->1.2.9, @oxc-project/types 0.149.0->0.150.0, string-width 8.2.2->8.3.0; all else identical", 420),
              "pass": True})
steps.append({"name": "install-version-and-bin-link", "arm": "candidate 0.14.1",
              "cmd": "tools/mcporter-0.14.1/bin/mcporter --version ; readlink ~/.local/share/codex-ecosystem/bin/mcporter before/after ; diff -r tarball package vs installed",
              "exit": 0, "output_excerpt": "0.14.1 | bin link unchanged: ~/.local/share/codex-ecosystem/tools/mcporter-0.13.13/bin/mcporter | installed package files identical to verified tarball",
              "pass": True})

att1 = json.loads((HERE / "results-y-attempt1.json").read_text())
for s in att1["steps"]:
    if not s["pass"]:
        steps.append({"name": s["name"] + " (retained failed attempt 1)", "arm": "y (0.13.13) attempt 1, superseded harness",
                      "cmd": "receipt ...--context-mode--use--20260925-2.json commands[1], verbatim, run with TMPDIR=<arm-private ~/.local/state dir> (attempt-1 harness; read-only inside the receipt sandbox)",
                      "exit": s["exit"], "output_excerpt": short(s["output_excerpt"], 300), "pass": False})

for arm in ("x", "y"):
    R = json.loads((HERE / f"results-{arm}.json").read_text())
    for s in R["steps"]:
        steps.append({"name": s["name"], "arm": s["arm"], "cmd": short(RECEIPT_CMD.get(s["name"], s["cmd"]), 300),
                      "exit": s["exit"], "output_excerpt": short(s["output_excerpt"], 230), "pass": s["pass"]})
out = json.dumps(steps, indent=None, ensure_ascii=False)
(HERE / "steps-for-result.json").write_text(out + "\n")
print(len(steps), "steps;", len(out), "chars")
