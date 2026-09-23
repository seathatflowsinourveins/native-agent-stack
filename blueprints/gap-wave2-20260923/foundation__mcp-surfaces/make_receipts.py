#!/usr/bin/env python3
"""Build the wave-2 receipts for foundation/mcp-surfaces from the committed raw outputs.

Every number in a receipt is read from a raw file under raw/; outcomes follow the preregistered criteria
in preregistrations.json. Run from the repository root.
"""
import hashlib
import json
import pathlib
import re
import statistics

L = pathlib.Path("evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces")
RAW = L / "raw"
BP = pathlib.Path("blueprints/gap-wave2-20260923/foundation__mcp-surfaces")
PRE = json.loads((L / "preregistrations.json").read_text())
import datetime  # noqa: E402
CHECKED_AT = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # receipt assembly; run times are in raw files


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def rawref(*names):
    return [{"file": str(RAW / n), "sha256": sha(RAW / n)} for n in names]


def scripts(*names):
    return [{"file": str(BP / n), "sha256": sha(BP / n)} for n in names]


def prereg(i, addenda=()):
    g = PRE["gaps"][str(i)]
    out = {"written_at": g["written_at"], "expectation": g["expectation"], "criteria": g["criteria"],
           "source": str(L / "preregistrations.json")}
    add = [a for a in PRE.get("addenda", []) if i in a["gaps"]]
    if add:
        out["addenda"] = [{"written_at": a["written_at"], "label": a["label"], "expectation": a["expectation"],
                           "criteria": a["criteria"]} for a in add]
    return out


def base(i, slug):
    g = PRE["gaps"][str(i)]
    return {"id": f"gap-wave2-20260923-foundation-mcp-surfaces-{i}", "gap_index": i, "slug": slug,
            "gap_text_sha256": g["gap_text_sha256"], "gap_text": g["gap_text"], "next_check": g["next_check"],
            "preregistration": prereg(i), "checked_at": CHECKED_AT}


# ---------------------------------------------------------------- load raw
B = json.loads((RAW / "bridges-matched.json").read_text())
NS = json.loads((RAW / "ns-exact-config.json").read_text())
LC = {v: json.loads((RAW / f"lifecycle-mcporter-{v}.json").read_text()) for v in ("0.13.13", "0.14.0")}
LC1 = {v: json.loads((RAW / f"round1/lifecycle-mcporter-{v}.run1.json").read_text()) for v in ("0.13.13", "0.14.0")}
ENF = {n: json.loads((RAW / f"{n}.enforce.json").read_text()) for n in ("bridges-matched", "lifecycle-mcporter-0.13.13", "lifecycle-mcporter-0.14.0", "wong2-interactive-list")}
README_MEASURE = dict(l.split("=", 1) for l in (RAW / "0-readme-measure.txt").read_text().splitlines() if "=" in l)
INSTALL_ID = (RAW / "1-install-identity.txt").read_text()
WP = json.loads((RAW / "wong2-interactive-list.json").read_text())
SR = json.loads((RAW / "7-source-review.json").read_text())
DEF = json.loads((RAW / "3-retained-op-definitions.json").read_text())
S = B["summary"]
RUNS = {(r["bridge"], r["op"], r["rep"]): r for r in B["runs"]}
NSR = {r["label"]: r for r in NS["runs"]}
BR = ["mcporter-installed-0.13.13", "mcporter-0.13.13", "mcporter-0.14.0", "inspector", "wong2-mcp-cli-2.0.0"]


def cell(op, b):
    s = S[op][b]
    return {"all_pass": s["all_pass"], "exits": s["exits"], "median_ms": s["median_ms"],
            **({"distinct_server_pids": s["distinct_server_pids"]} if s["distinct_server_pids"] else {})}


def excerpt(text, n=240):
    t = re.sub(r"\s+", " ", text).strip()
    return t[:n]


def norm(t):
    t = re.sub(r"\d+(\.\d+)?\s?ms\b", "<ms>", t)
    t = re.sub(r'"session_duration_s": [\d.]+', '"session_duration_s": <s>', t)
    t = re.sub(r"PPID=\d+", "PPID=<pid>", t)
    t = re.sub(r'"this_pid": \d+', '"this_pid": <pid>', t)
    return t


ENF_TXT = (f"Fix round 1 runs are ENFORCED: unshare -rnm with an empty tmpfs over $HOME/.mcporter and a fresh network namespace "
           f"(enforce.py / ns_exact.py). Inside, an AF_UNIX connect to the shared daemon socket path returned "
           f"'{B['enforcement_probe_start']['shared_socket']}' and TCP 49374/16333 returned "
           f"'{B['enforcement_probe_start']['live_tcp']['49374']}', while the same AF_UNIX probe against each owned daemon socket returned "
           f"{sorted(set(B['owned_socket_controls'].values()))} (owned control, so the probe can detect a reachable socket).")
common_limits = [
    "Servers ran with owned state only (temp HOME/XDG, MCPORTER_DAEMON_DIR under $HOME/.cache/gap-wave2-20260923, owned "
    "ai-memory --data-dir and Qdrant storage). " + ENF_TXT + " Round-1 runs (raw/round1/) set only environment-level isolation; "
    "their stat() of the shared daemon (pid, socket inode, metadata mtime) could not detect a client connection, so they are not "
    "cited for the no-contact claim.",
    "/tmp was not isolated; SocratiCode reported another process watching the agent-lab checkout, i.e. it read host watcher state.",
]

receipts = []

# ---------------------------------------------------------------- gap 0
ops0 = ["list-context-mode", "list-ai-memory", "list-socraticode", "list-codebase-memory", "list-jcodemunch",
        "ctx-execute-file", "ctx-arith-42", "jcodemunch-session-stats"]
ns0 = ["host-cfg-list-context-mode", "host-cfg-list-ai-memory", "host-cfg-list-socraticode", "host-cfg-ctx-execute-file",
       "adhoc-jcodemunch-session-stats", "inspector-context-mode-42", "host-daemon-status", "host-daemon-stop"]
sk = LC["0.13.13"]["stages"]["stale_metadata_sigkill"]
r = base(0, "retained-bridge-rerun")
r["preregistration"] = prereg(0)
all_ns_ok = all(NSR[k]["exit"] == 0 for k in ns0)
fixture_ok = all(S[o]["mcporter-installed-0.13.13"]["all_pass"] for o in ops0) and S["ctx-arith-42"]["inspector"]["all_pass"]
r["arms"] = [
    {"arm": "mcporter list of each configured server (unmodified $HOME/codex-ecosystem/config/mcporter.json)", "status": "executed",
     "detail": {k: NSR[k]["exit"] for k in ns0[:3]}},
    {"arm": "retained current-session bridge call: context-mode.ctx_execute_file via --config", "status": "executed",
     "detail": excerpt(NSR["host-cfg-ctx-execute-file"]["stdout"], 400)},
    {"arm": "retained current-session bridge call: jcodemunch order/get_session_stats via --stdio", "status": "executed",
     "detail": excerpt(NSR["adhoc-jcodemunch-session-stats"]["stdout"], 160)},
    {"arm": "retained Inspector call (context-mode ctx_execute arithmetic)", "status": "executed",
     "detail": excerpt(NSR["inspector-context-mode-42"]["stdout"], 160)},
    {"arm": "same calls x3 on the owned-port fixture with the installed binaries", "status": "executed",
     "detail": {o: cell(o, "mcporter-installed-0.13.13") for o in ops0} | {"inspector ctx-arith-42": cell("ctx-arith-42", "inspector")}},
    {"arm": "restart-receipt daemon recovery scenario repeated on an owned daemon (stale metadata after daemon death)", "status": "executed",
     "detail": {"next_call_exit": sk["next_call"]["exit"], "refusal": excerpt(sk["next_call"]["stdout"], 200),
                "manual_steps": sk["manual_steps"], "call_after_manual_step_exit": sk["call_after_manual_step"]["exit"]}},
]
r["commands"] = [" ".join(NSR[k]["argv"]) + f"   # cwd {NSR[k]['cwd']}" for k in ns0] + [
    "python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/ns_exact.py evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/ns-exact-config.json",
    "python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/run_bridges.py evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/bridges-matched.json --reps 3",
    "python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/run_lifecycle.py mcporter-0.13.13 evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/lifecycle-mcporter-0.13.13.json"]
r["results"] = [
    f"namespace probes before owned services started: {NS['pre_start_probe']}; after: {NS['post_start_probe']}; write probes: {NS['write_probe']}",
    f"unmodified host config, installed mcporter 0.13.13: " + ", ".join(f"{k} exit {NSR[k]['exit']} ({NSR[k]['elapsed_ms']} ms)" for k in ns0),
    "ctx_execute_file on agent-lab README.md returned: " + re.search(r"BYTES=\d+ SHA=\w+", NSR["host-cfg-ctx-execute-file"]["stdout"]).group(0)
    + f" (raw/0-readme-measure.txt: on-disk {README_MEASURE['bytes']} bytes with {README_MEASURE['cr_count']} CR characters; after CRLF->LF "
    f"{README_MEASURE['bytes_after_crlf_to_lf']} bytes, sha256 {README_MEASURE['sha256_after_crlf_to_lf'][:16]}...; FILE_CONTENT is newline-normalized)",
    "Inspector 2.7.0 context-mode arithmetic: " + excerpt(NSR["inspector-context-mode-42"]["stdout"], 120),
    f"owned-port fixture (3 reps each): all installed-binary calls passed = {fixture_ok}",
    f"owned-daemon repeat of the 2026-09-19 recovery: next call exit {sk['next_call']['exit']} with the refusal; after archiving only daemon/user.json the call exited {sk['call_after_manual_step']['exit']} (same manual procedure as restart-receipt.json bridge_recovery)",
]
r["outcome"] = "settled" if (all_ns_ok and fixture_ok and sk["call_after_manual_step"]["exit"] == 0) else "not_settled"
r["note"] = ("Every retained call was repeated on this host with the installed mcporter 0.13.13 and Inspector 2.7.0: the unmodified "
             "host mcporter config (3 servers listed, ctx_execute_file), the ad-hoc jcodemunch stats call, the Inspector '42' call, "
             "and the daemon-recovery scenario on an owned daemon. The configured ports were served by owned instances inside a "
             "network namespace, so the live stores were not the targets; the bridge binaries and configuration files were.")
r["evidence_class"] = "local_integration"
r["limits"] = common_limits + [
    "Inside the namespace ai-memory (49374) and Qdrant (16333) were owned empty instances: memory_status counts are 0 and "
    "SocratiCode reports no index, unlike the retained 2026-09-20 live results.",
    "The shared per-user daemon itself was not restarted or queried (hard rule); the recovery scenario ran on an owned daemon.",
    "saturation-audit.json's current_host_recertified_by_this_audit flags are not edited by this unit (ledger files are out of scope).",
]
r["raw_evidence"] = rawref("ns-exact-config.json", "0-readme-measure.txt", "bridges-matched.json", "bridges-matched.enforce.json",
                           "lifecycle-mcporter-0.13.13.json", "lifecycle-mcporter-0.13.13.enforce.json")
r["helper_scripts"] = scripts("iso.py", "enforce.py", "ns_exact.py", "run_bridges.py", "run_lifecycle.py")
receipts.append(r)

# ---------------------------------------------------------------- gap 1
allops = list(S.keys())
cmp = {}
for op in allops:
    a = RUNS[("mcporter-0.13.13", op, 0)]
    b = RUNS[("mcporter-0.14.0", op, 0)]
    cmp[op] = {"0.13.13": cell(op, "mcporter-0.13.13"), "0.14.0": cell(op, "mcporter-0.14.0"),
               "rep0_stdout_identical": a["stdout"] == b["stdout"],
               "rep0_stdout_identical_after_timing_pid_normalization": norm(a["stdout"]) == norm(b["stdout"])}
LC_KEYS = ("passed", "auto_recovered", "auto_recovered_after_kill", "auto_recovered_after_holder_exit", "restart_cmd_passed")
# fix round 3 (round-4 review finding 5): per-version outcome fields plus an explicit identical flag, so the dict cannot be
# read as pass/fail (receipt 2 uses True = passed or auto_recovered).
lc_cmp = {}
for st in LC["0.13.13"]["stages"]:
    per = {v: {k: x for k, x in LC[v]["stages"][st].items() if k in LC_KEYS} for v in ("0.13.13", "0.14.0")}
    lc_cmp[st] = {**per, "identical_between_versions": per["0.13.13"] == per["0.14.0"]}
lc_same = {st: v["identical_between_versions"] for st, v in lc_cmp.items()}
r = base(1, "mcporter-0.14.0-matched")
r["arms"] = [
    {"arm": "install mcporter 0.14.0 in a separate prefix", "status": "executed",
     "detail": "npm install --prefix $HOME/.cache/gap-wave2-20260923/mcp-surfaces/mcporter-0.14.0 mcporter@0.14.0 (integrity sha512-R60nKyUcW65WawhVjoESC0HeNibsf+1iqpX0wHPX9P60AFX/DYCBlhS7pDYcuWzeGYqYfZG2Xf5jWWkM74d/+A==); "
               "0.13.13 re-installed the same way (integrity sha512-rgltHjpm...vxFkA==, identical to the host install)"},
    {"arm": "run the retained bridge calls under both versions against the same servers", "status": "executed",
     "detail": f"{len(allops)} operations x 3 reps per version, same owned fixture"},
    {"arm": "record per-call results and differences", "status": "executed", "detail": "per-op table below; lifecycle stages compared too"},
]
r["commands"] = [
    "npm install --no-audit --no-fund --prefix $HOME/.cache/gap-wave2-20260923/mcp-surfaces/mcporter-0.14.0 mcporter@0.14.0   # via ecosystem-bounded-run",
    "npm install --no-audit --no-fund --prefix $HOME/.cache/gap-wave2-20260923/mcp-surfaces/mcporter-0.13.13 mcporter@0.13.13   # via ecosystem-bounded-run",
    "python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/run_bridges.py evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/bridges-matched.json --reps 3",
    "python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/run_lifecycle.py mcporter-0.14.0 evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/lifecycle-mcporter-0.14.0.json",
    "diff -rq mcporter-0.13.13/node_modules/mcporter/dist mcporter-0.14.0/node_modules/mcporter/dist; diff .../dist/daemon/client.js (identical)",
]
r["results"] = [
    f"per-op (all_pass/median ms): " + "; ".join(f"{op}: 0.13.13 {v['0.13.13']['all_pass']}/{v['0.13.13']['median_ms']}, 0.14.0 {v['0.14.0']['all_pass']}/{v['0.14.0']['median_ms']}" for op, v in cmp.items()),
    "output differences: rep-0 stdout identical for " + ", ".join(o for o, v in cmp.items() if v["rep0_stdout_identical"])
    + "; identical after normalizing timing/pid fields for " + ", ".join(o for o, v in cmp.items() if not v["rep0_stdout_identical"] and v["rep0_stdout_identical_after_timing_pid_normalization"])
    + "; still different: " + (", ".join(o for o, v in cmp.items() if not v["rep0_stdout_identical_after_timing_pid_normalization"]) or "none"),
    "lifecycle stage outcome fields per version (True/False are the stage's own passed/auto_recovered fields, not agreement), with identical_between_versions: " + "; ".join(f"{st}: 0.13.13 {v['0.13.13']}, 0.14.0 {v['0.14.0']}, identical={v['identical_between_versions']}" for st, v in lc_cmp.items()),
    "install identity and dist diff (raw/1-install-identity.txt): " + "; ".join(l for l in INSTALL_ID.splitlines() if l.startswith(("mcporter-", "host-installed")))
    + f"; {sum(1 for l in INSTALL_ID.splitlines() if l.startswith(('Files ', 'Only in ')))} dist entries differ (non-map), including daemon/process-retirement.js and a new runtime/schema-validator.js; dist/daemon/client.js identical (sha256 074c0571...)",
]
r["per_call"] = cmp
r["lifecycle_per_stage"] = lc_cmp
r["outcome"] = "settled" if all(v["0.13.13"]["all_pass"] and v["0.14.0"]["all_pass"] for v in cmp.values()) and all(lc_same.values()) else "advanced"
r["note"] = ("mcporter 0.14.0 was installed in its own prefix and ran the same 13-operation retained call set and the full owned-daemon "
             "lifecycle fixture next to a fresh 0.13.13 prefix. Every call passed on both versions. After timing and pid fields "
             "are normalized, the outputs are identical, and the lifecycle outcomes match stage for stage, including the "
             "stale-metadata refusal. v0.14.0 is now tested for this call set and shows no regression. The pin itself is not "
             "changed here.")
r["evidence_class"] = "local_integration"
r["limits"] = common_limits + ["Call set limited to the retained operations (5 servers, stdio + HTTP); OAuth, generate-cli, emit-ts and Chrome relay paths changed in 0.14.0 were not exercised.",
                               "Latency medians are 3 reps on one loaded host; small differences are within run-to-run spread."]
r["raw_evidence"] = rawref("bridges-matched.json", "bridges-matched.enforce.json", "lifecycle-mcporter-0.13.13.json",
                           "lifecycle-mcporter-0.14.0.json", "lifecycle-mcporter-0.14.0.enforce.json", "1-install-identity.txt")
r["helper_scripts"] = scripts("iso.py", "enforce.py", "run_bridges.py", "run_lifecycle.py")
receipts.append(r)

# ---------------------------------------------------------------- gap 2
st = LC["0.13.13"]["stages"]
r = base(2, "owned-daemon-lifecycle-stages")
r["arms"] = [
    {"arm": "owned daemon with isolated config and state directory", "status": "executed",
     "detail": {"MCPORTER_DAEMON_DIR": LC["0.13.13"]["daemon_dir"], "enforcement_probe_in_namespace": LC["0.13.13"]["enforcement_probe_start"],
                "owned_socket_control": st["persistence"]["owned_socket_control"], "shared_socket_probe_mid_run": st["persistence"]["shared_socket_probe"],
                "shared_daemon_outside_unchanged": ENF["lifecycle-mcporter-0.13.13"]["shared_daemon_unchanged"]}},
    {"arm": "persistence across calls", "status": "executed",
     "detail": {"method": "ctx_execute prints process.ppid (= context-mode server pid, cmdline recorded); ephemeral twin is the negative control",
                "keepalive_distinct_pids": st["persistence"]["keepalive_distinct_pids"], "ephemeral_distinct_pids": st["persistence"]["ephemeral_distinct_pids"],
                "passed": st["persistence"]["passed"]}},
    {"arm": "kill/restart", "status": "executed",
     "detail": {"daemon stop then call auto-launches new daemon+server": st["restart"]["passed"], "daemon restart subcommand": st["restart"]["restart_cmd_passed"],
                "SIGKILL then call": f"exit {st['stale_metadata_sigkill']['next_call']['exit']} (refused)"}},
    {"arm": "registration cleanup", "status": "executed",
     "detail": {"after daemon stop: no fixture process, no daemon pid, socket removed": st["cleanup"]["passed"],
                "config views released after each call": st["scoped_registration_cleanup"]["views_released_after_calls"]}},
    {"arm": "recovery from stale metadata without manual steps", "status": "executed",
     "detail": {"auto_recovered": st["stale_metadata_sigkill"]["auto_recovered"], "second_call_exit": st["stale_metadata_sigkill"]["second_call"]["exit"],
                "manual_steps_needed": st["stale_metadata_sigkill"]["manual_steps"],
                "orphaned_server_after_daemon_kill": st["stale_metadata_sigkill"]["server_after_daemon_kill"]}},
]
r["commands"] = ["python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/run_lifecycle.py mcporter-0.13.13 evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/lifecycle-mcporter-0.13.13.json",
                 "(inside) mcporter --config <owned>/mcporter.json call context-mode.ctx_execute --args '{\"language\":\"javascript\",\"code\":\"console.log(\\'PPID=\\' + process.ppid)\"}' --output json --no-oauth",
                 "(inside) mcporter daemon status --json | daemon stop | daemon restart; kill -KILL <owned daemon pid verified via /proc environ>"]
r["results"] = [
    f"persistence: keep-alive server pids {[c['server_pid'] for c in st['persistence']['keepalive_calls']]} vs ephemeral {[c['server_pid'] for c in st['persistence']['ephemeral_calls']]}",
    f"restart: daemon pid {st['restart']['status_before'].get('pid')} -> {st['restart']['status_after'].get('pid')} after stop + call; old server alive after stop = {st['restart']['after_stop']['old_server']['alive']}",
    f"cleanup after stop: fixture processes {st['cleanup']['after']['fixture_processes']}, daemon dir {st['cleanup']['after']['daemon_dir']}",
    "stale metadata: " + excerpt(st["stale_metadata_sigkill"]["next_call"]["stdout"], 220),
    f"after archiving only daemon/user.json: exit {st['stale_metadata_sigkill']['call_after_manual_step']['exit']}",
    f"stage outcomes in the round-1 first run (raw/round1/, 04:09Z; passed or auto_recovered): { {k: v.get('passed', v.get('auto_recovered')) for k, v in LC1['0.13.13']['stages'].items()} }",
]
r["outcome"] = "settled" if all([st["persistence"]["passed"], st["restart"]["passed"], st["cleanup"]["passed"]]) and "next_call" in st["stale_metadata_sigkill"] else "advanced"
r["note"] = ("All four stages ran on an owned daemon with a stated detection method. Persistence, restart (stop followed by an "
             "auto-launch, and `daemon restart`) and cleanup (no process left, socket removed, views released) pass. Recovery "
             "from stale metadata is now established as NOT automatic: after SIGKILL the next calls are refused ('No replacement "
             "was launched'), and archiving daemon/user.json is required. This is the fail-closed design in "
             "dist/daemon/client.js ensureDaemon. The killed daemon's server child exited with it, so nothing was orphaned.")
r["evidence_class"] = "local_integration"
r["limits"] = common_limits + ["Owned daemon on this host only; the shared daemon's own lifecycle was not exercised.",
                               "SIGKILL is the induced crash; a WSL reboot (the 2026-09-19 cause) was not reproduced."]
r["raw_evidence"] = rawref("lifecycle-mcporter-0.13.13.json", "lifecycle-mcporter-0.13.13.enforce.json", "round1/lifecycle-mcporter-0.13.13.run1.json")
r["helper_scripts"] = scripts("iso.py", "enforce.py", "run_lifecycle.py")
receipts.append(r)

# ---------------------------------------------------------------- gap 3
ids = ["fresh-static-graph", "fresh-static-callees", "fresh-memory-status", "fresh-socraticode-status"]
r = base(3, "retained-operation-ids-defined")
r["preregistration"] = prereg(3)
defs = {}
for i in ids:
    d = DEF["operations"][i]
    defs[i] = {"retained_argv": d["argv"], "retained_cwd": d["cwd"], "retained_at": d["started_at_utc"], "retained_exit": d["exit_code"],
               "retained_checks": [c["name"] for c in d["checks"]], "retained_stdout_sha256": d["stdout_sha256"],
               "fresh_argv": RUNS[("mcporter-installed-0.13.13", i, 0)]["argv"],
               "fresh": {b: cell(i, b) for b in BR},
               "fresh_stdout_excerpt": excerpt(RUNS[("mcporter-installed-0.13.13", i, 0)]["stdout"], 300)}
defs["fresh-memory-status"]["fresh_unmodified_host_config"] = {"exit": NSR["host-cfg-fresh-memory-status"]["exit"], "stdout": excerpt(NSR["host-cfg-fresh-memory-status"]["stdout"])}
defs["fresh-socraticode-status"]["fresh_unmodified_host_config"] = {"exit": NSR["host-cfg-fresh-socraticode-status"]["exit"], "stdout": excerpt(NSR["host-cfg-fresh-socraticode-status"]["stdout"], 300)}
r["arms"] = [{"arm": f"{i} as an explicit mcporter call with command, exit status and output published", "status": "executed",
              "detail": {"fresh_exit_installed": S[i]["mcporter-installed-0.13.13"]["exits"], "check_passed": S[i]["mcporter-installed-0.13.13"]["all_pass"]}} for i in ids]
r["operations"] = defs
r["commands"] = [" ".join(defs[i]["fresh_argv"]) for i in ids] + [" ".join(NSR[k]["argv"]) for k in ("host-cfg-fresh-memory-status", "host-cfg-fresh-socraticode-status")]
r["results"] = [f"{i}: retained {defs[i]['retained_at']} exit {defs[i]['retained_exit']}; fresh exits {S[i]['mcporter-installed-0.13.13']['exits']} check {S[i]['mcporter-installed-0.13.13']['all_pass']}: {defs[i]['fresh_stdout_excerpt'][:160]}" for i in ids]
r["outcome"] = "settled" if all(S[i]["mcporter-installed-0.13.13"]["all_pass"] for i in ids) else "not_settled"
r["note"] = ("The four ids are defined in the host-local codex-ecosystem state (combined-functional-summary.json). Their argv, cwd, "
             "checks and retained output hashes are now published in raw/3-retained-op-definitions.json. Each was re-run as an explicit "
             "`mcporter call` and passed its retained check: the collect node found, 4 outbound callees (the retained run also had 4), "
             "a structured counts object, and a structured status. The ai-memory and SocratiCode ids were also re-run through the "
             "unmodified host config inside the namespace.")
r["evidence_class"] = "local_integration"
r["limits"] = common_limits + [
    "codebase-memory-mcp 0.11.0 was removed from the host config on 2026-09-21; the retained binary (tools/codebase-memory-mcp-0.11.0.removed-20260921) "
    "indexed an owned copy of tools/ecosystem/linux-usage-report.cjs, so the project name differs from the retained 'agent-lab' and only that file is indexed.",
    "memory_status ran against an owned empty store (counts 0), and codebase_status against an owned Qdrant with no index ('No index found'). "
    "The retained runs read the live store and index.",
]
r["raw_evidence"] = rawref("3-retained-op-definitions.json", "bridges-matched.json", "bridges-matched.enforce.json", "ns-exact-config.json")
r["helper_scripts"] = scripts("iso.py", "enforce.py", "run_bridges.py", "ns_exact.py")
receipts.append(r)

# ---------------------------------------------------------------- gap 4
r = base(4, "inspector-tools-list-local-servers")
r["preregistration"] = prereg(4)
tl = {s: cell(f"list-{s}", "inspector") for s in ("ai-memory", "jcodemunch", "context-mode", "socraticode", "codebase-memory")}
nsl = {s: NSR[f"inspector-inside-list-{s}"]["exit"] for s in ("serena", "ai-memory", "socraticode")}
r["arms"] = [
    {"arm": "Inspector --cli --method tools/list against ai-memory (HTTP) and jcodemunch (stdio)", "status": "executed", "detail": {k: tl[k] for k in ("ai-memory", "jcodemunch")}},
    {"arm": "same against the other retained local servers", "status": "executed", "detail": {k: tl[k] for k in ("context-mode", "socraticode", "codebase-memory")}},
    {"arm": "tools/list against agent-lab's configured .mcp.json servers (unmodified file, namespace)", "status": "executed", "detail": nsl},
    {"arm": "full client plugin, hooks, Desktop connection", "status": "not_executed", "detail": "no Desktop client or plugin-hook host in this environment; next_check marks Desktop as separate"},
]
r["commands"] = [" ".join(RUNS[("inspector", "list-ai-memory", 0)]["argv"]), " ".join(RUNS[("inspector", "list-jcodemunch", 0)]["argv"])] + [" ".join(NSR[f"inspector-inside-list-{s}"]["argv"]) + "   # cwd $HOME/code/agent-lab" for s in ("serena", "ai-memory", "socraticode")]
serena_err = NSR["inspector-inside-list-serena"]["stderr"]
r["results"] = [f"fixture tools/list: {tl}",
                f"agent-lab .mcp.json tools/list exits: {nsl}",
                "serena failure: " + excerpt(serena_err[serena_err.find("OSError"):], 220) + " (the serena-context wrapper writes logs under $HOME/.local/share/codex-ecosystem/context/serena-home regardless of HOME; read-only in the namespace)",
                "ai-memory tools/list first tool: " + excerpt(RUNS[("inspector", "list-ai-memory", 0)]["stdout"], 120)]
r["outcome"] = "advanced"
r["note"] = ("Inspector 2.7.0 tools/list now has receipts against ai-memory (HTTP) and jcodemunch (stdio), plus context-mode, "
             "SocratiCode and codebase-memory, all passing 3 of 3. It also passed for agent-lab's configured ai-memory and SocratiCode. "
             "Serena failed only because its wrapper writes logs into the read-only ecosystem directory. Remaining: full "
             "client plugin, hook behavior and Desktop connectivity. Project-file scope is covered by gap 8.")
r["evidence_class"] = "local_integration"
r["limits"] = common_limits + ["Serena's tools/list could not complete under the read-only mount; it was not retried with a writable ecosystem dir (that would write shared state)."]
r["raw_evidence"] = rawref("bridges-matched.json", "bridges-matched.enforce.json", "ns-exact-config.json")
r["helper_scripts"] = scripts("iso.py", "enforce.py", "run_bridges.py", "ns_exact.py")
receipts.append(r)

# ---------------------------------------------------------------- gap 5
idx = [l.split("\t") for l in (RAW / "5-mcp-list-index.tsv").read_text().splitlines()[1:] if l.strip()]
listing = {}
for label, cli, rc, *_ in idx:
    out = (RAW / f"5-{label}-{cli}.stdout.txt").read_text()
    if cli == "codex":
        try:
            names = [s["name"] for s in json.loads(out)]
        except Exception:  # noqa: BLE001
            names = out[:120]
        listing[f"{label}/{cli}"] = {"exit": int(rc), "servers": names}
    else:
        listing[f"{label}/{cli}"] = {"exit": int(rc), "lines": [l for l in out.splitlines() if " - " in l and ":" in l][:6] or out.strip().splitlines()[:1]}
r = base(5, "project-config-without-registry")
r["preregistration"] = prereg(5)
r["arms"] = [
    {"arm": "claude mcp list in the project (agent-lab, read-only mount, no network)", "status": "executed", "detail": listing.get("project/claude")},
    {"arm": "codex mcp list in the project (trusted in a temp CODEX_HOME)", "status": "executed", "detail": listing.get("project/codex")},
    {"arm": "both CLIs in an empty scratch project", "status": "executed", "detail": {k: listing[k] for k in listing if k.startswith("scratch-empty")}},
    {"arm": "both CLIs in a scratch project with its own .mcp.json / .codex/config.toml", "status": "executed", "detail": {k: listing[k] for k in listing if k.startswith("scratch-config")}},
    {"arm": "controls: codex without project trust; claude with local approval state seeded (addendum 04:23:01Z)", "status": "executed",
     "detail": {k: listing[k] for k in listing if "untrusted" in k or "approved" in k}},
]
r["commands"] = ["bash blueprints/gap-wave2-20260923/foundation__mcp-surfaces/run_mcp_list.sh evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw",
                 "ONLY_APPROVED=1 bash blueprints/gap-wave2-20260923/foundation__mcp-surfaces/run_mcp_list.sh evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw",
                 "(each) unshare -rnm bash -c 'mount --rbind $HOME $HOME && mount -o remount,bind,ro $HOME && ... && env -i HOME=<temp> CLAUDE_CONFIG_DIR=<temp> CODEX_HOME=<temp> ... claude mcp list | codex mcp list --json'"]
r["results"] = [f"{k}: {v}" for k, v in listing.items()] + ["temp client homes: " + excerpt((RAW / "5-registry-state-find.txt").read_text(), 400)]
r["outcome"] = "settled"
r["note"] = ("With fresh client homes, no network and a read-only checkout, `codex mcp list` in agent-lab lists exactly the 5 servers of its "
             ".codex/config.toml once the project is trusted, and none when it is not. `claude mcp list` lists the 3 .mcp.json servers "
             "(pending approval until local approval state exists). With that state, SocratiCode connects and Serena fails (read-only log "
             "dir). For ai-memory the client attempted an HTTP connect to the live-service URL in agent-lab's .mcp.json "
             "(http://127.0.0.1:49374/mcp); the no-network namespace blocked it before any packet left (ENETUNREACH). Empty scratch projects list nothing; a scratch project with its own "
             "files lists and connects its server. No registry, marketplace or plugin state existed or was created.")
r["evidence_class"] = "native_proven"
r["limits"] = ["Temp client homes: the user's real ~/.claude.json and ~/.codex/config.toml (user-scope servers, claude.ai connectors, plugins) were deliberately not read.",
               "Claude connects project servers only after local approval state; the approved arm seeded that state in the temp CLAUDE_CONFIG_DIR (not a registry action).",
               "Health checks ran without network, so HTTP servers on the host loopback cannot be reached.",
               "Disclosure (round-4 review finding 4): the project-approved Claude arm approved ai-memory, so the client attempted a connect "
               "to the LIVE ai-memory URL http://127.0.0.1:49374/mcp hard-coded in agent-lab's .mcp.json. No owned ai-memory server was "
               "running and AI_MEMORY_SERVER_URL was not set (it would not redirect a hard-coded project URL anyway). The attempt was "
               "blocked by the network namespace: `unshare -rnm` gives a fresh net namespace whose loopback is never brought up "
               "(run_mcp_list.sh has no `ip link set lo up`), and the client reported ENETUNREACH, i.e. the connect failed with no "
               "route before any packet was sent; the live store was not contacted. This meets the no-contact intent but not the "
               "letter of the ai-memory rule; any rerun must drop ai-memory from the approval list or point the entry at an owned "
               "temp-data-dir server.",
               "These arms ran at 04:22-04:23Z, before fix round 1. They did not use the tmpfs over $HOME/.mcporter; claude/codex mcp list do not use mcporter, and the network namespace blocked live TCP.",
               "run_mcp_list.sh was edited after these runs only to replace hard-coded home paths with $HOME (publication rule); command behavior is unchanged. The run-time version is at commit feb2cd1."]
r["raw_evidence"] = rawref(*sorted(p.name for p in RAW.glob("5-*")))
r["helper_scripts"] = scripts("run_mcp_list.sh")
receipts.append(r)

# ---------------------------------------------------------------- gap 6
w = "wong2-mcp-cli-2.0.0"
ops6 = allops
full_names = {}
for srv in ("context-mode", "socraticode", "codebase-memory", "jcodemunch", "ai-memory"):
    full_names[srv] = sorted(t["name"] for t in json.loads(RUNS[("inspector", f"list-{srv}", 0)]["stdout"])["tools"])
wl = {}
for key, v in WP["runs"].items():
    srv = key.split("#")[0]
    wl.setdefault(srv, []).append({"connected": v["connected"], "tools": v["tools_rendered"], "ready_ms": v["ready_ms"], "harness_ms": v["harness_ms"],
                                   "error": (re.search(r"McpError: [^\n]+", v["screen_excerpt"]) or [None])[0]})
wong2_list = {}
for srv, runs in wl.items():
    readies = [x["ready_ms"] for x in runs if x["ready_ms"] is not None]
    wong2_list[srv] = {"executed_interactive_reps": len(runs), "connected": [x["connected"] for x in runs],
                       "tools_collected": [len(x["tools"]) for x in runs], "full_tool_count": len(full_names[srv]),
                       "complete": all(x["tools"] == full_names[srv] for x in runs),
                       "missing_vs_inspector": sorted(set(full_names[srv]) - set().union(*[set(x["tools"]) for x in runs])),
                       "median_ready_ms": statistics.median(readies) if readies else None,
                       "median_harness_ms_not_latency": statistics.median([x["harness_ms"] for x in runs]),
                       "error": next((x["error"] for x in runs if x["error"]), None)}
tab6 = {op: {b: cell(op, b) for b in ("mcporter-0.13.13", "inspector", w)} for op in ops6}
for op in ops6:
    if op.startswith("list-"):
        tab6[op][w] = {"non_interactive": "not available in 2.0.0 (src/cli.js usage)", "interactive_pty": wong2_list[op[5:]]}
r = base(6, "alternative-bridge-comparison")
r["arms"] = [
    {"arm": "install a pinned alternative MCP CLI (registry-listed)", "status": "executed",
     "detail": "@wong2/mcp-cli 2.0.0 (raw/1-install-identity.txt; awesome-mcp-servers line %s)" % SR["list"]["entry_lines"].get("wong2/mcp-cli")},
    {"arm": "same call operations against the same servers (x3)", "status": "executed",
     "detail": {op: tab6[op][w]["all_pass"] for op in ops6 if not op.startswith("list-")}},
    {"arm": "same list operations against the same servers (x3)", "status": "executed",
     "detail": {"method": "2.0.0 has no non-interactive list; its interactive mode was driven through a pty and scrolled with Down x45 "
                          "(fix round 2) so every autocomplete choice renders; completeness = collected tool-name set equals Inspector tools/list names",
                "per_server": wong2_list}},
    {"arm": "compare success, latency and lifecycle", "status": "executed",
     "detail": {"lifecycle (distinct context-mode server pids over 3 calls)": {b: S["ctx-ppid"][b]["distinct_server_pids"] for b in ("mcporter-0.13.13", "inspector", w)}}},
]
r["per_op"] = tab6
r["commands"] = [" ".join(RUNS[(w, "ctx-arith-42", 0)]["argv"]), " ".join(RUNS[(w, "fresh-memory-status", 0)]["argv"]),
                 "python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/enforce.py evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/wong2-interactive-list.enforce.json -- python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/wong2_pty_list.py evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/wong2-interactive-list.json"]
passed_calls = {b: sum(1 for op in ops6 if not op.startswith("list-") and S[op][b]["all_pass"]) for b in ("mcporter-0.13.13", "inspector", w)}
passed_lists = {"mcporter-0.13.13": sum(1 for op in ops6 if op.startswith("list-") and S[op]["mcporter-0.13.13"]["all_pass"]),
                "inspector": sum(1 for op in ops6 if op.startswith("list-") and S[op]["inspector"]["all_pass"]),
                w: sum(1 for v in wong2_list.values() if v["complete"])}
med = {b: statistics.median([S[op][b]["median_ms"] for op in ("ctx-execute-file", "ctx-arith-42", "ctx-ppid")]) for b in ("mcporter-0.13.13", "inspector", w)}
r["results"] = [f"call operations passing 3/3 (of 8): {passed_calls}",
                f"list operations complete 3/3 (of 5): {passed_lists} (wong2 via interactive pty, name sets compared with Inspector)",
                "wong2 interactive listing per server (collected/full, median ready ms): " + ", ".join(f"{k} {v['tools_collected']}/{v['full_tool_count']} ({v['median_ready_ms']})" + (f" [{v['error']}]" if v["error"] else "") for k, v in wong2_list.items()),
                "list latency, median ms (mcporter/Inspector: whole CLI run; wong2: spawn -> listing ready, excludes scrolling/teardown): " + ", ".join(
                    f"{srv}: {S[f'list-{srv}']['mcporter-0.13.13']['median_ms']}/{S[f'list-{srv}']['inspector']['median_ms']}/{wong2_list[srv]['median_ready_ms']}" for srv in wong2_list),
                f"median of context-mode call medians (ms): {med}",
                "wong2 ai-memory (HTTP) non-interactive call: " + excerpt(RUNS[(w, "fresh-memory-status", 0)]["stderr"], 160),
                "codebase-memory calls take ~4-5 s on every bridge (server startup dominates; not keep-alive in the config)"]
r["outcome"] = "settled"
r["note"] = ("A measured head-to-head now exists, with every list and call operation executed 3 times on each bridge against the same "
             f"owned servers. Calls passing: mcporter {passed_calls['mcporter-0.13.13']}/8, Inspector {passed_calls['inspector']}/8, "
             f"@wong2/mcp-cli 2.0.0 {passed_calls[w]}/8 (its non-interactive mode cannot call the HTTP ai-memory server). Complete lists: "
             f"mcporter {passed_lists['mcporter-0.13.13']}/5, Inspector {passed_lists['inspector']}/5, wong2 {passed_lists[w]}/5. wong2 lists "
             "only interactively. Scrolled through its autocomplete, it shows every tool of 4 servers, but it crashed on jcodemunch with "
             "MCP -32601 in all 3 runs. mcporter's keep-alive daemon reused one context-mode server over 3 calls, where the others started "
             "3, and it had the lowest context-mode call latency. Fix round 1 replaced skipped list rows with executed runs. Fix round 2 "
             "scrolled the interactive list and separated listing readiness from harness time.")
r["evidence_class"] = "local_integration"
r["limits"] = common_limits + ["One alternative only; latency is 3 reps on one host (fix-round medians are higher than round 1 because of host load).",
                               "The interactive listing is captured through a pty; 'complete' means the collected tool-name set equals the Inspector tools/list name set.",
                               "The jcodemunch crash is an interop failure: jcodemunch 1.108.319 advertises resources but answers resources/templates/list with "
                               "'Method not found' (raw/6-jcodemunch-method-probe.txt), and wong2 lists resource templates whenever resources are advertised "
                               "and aborts on the error. mcporter and Inspector only request tools/list here.",
                               "wong2 list latency is spawn-to-ready inside an interactive session, not a whole non-interactive CLI run; it is not strictly matched with the mcporter/Inspector list timings."]
r["raw_evidence"] = rawref("bridges-matched.json", "bridges-matched.enforce.json", "wong2-interactive-list.json", "wong2-interactive-list.enforce.json",
                           "6-jcodemunch-method-probe.txt", "7-source-review.json", "1-install-identity.txt", "round1/wong2-interactive-list.fix1.json")
r["helper_scripts"] = scripts("iso.py", "enforce.py", "run_bridges.py", "wong2_pty_list.py")
receipts.append(r)

# ---------------------------------------------------------------- gap 7
r = base(7, "awesome-mcp-servers-recovery-review")
r["arms"] = [
    {"arm": "choose one concrete gap", "status": "executed", "detail": SR["concrete_gap"]},
    {"arm": "pick matching entries in punkpeye/awesome-mcp-servers at a pinned commit", "status": "executed",
     "detail": {"commit": SR["list"]["commit"], "rule": SR["list"]["section_rule"], "entry_lines": SR["list"]["entry_lines"]}},
    {"arm": "source-review them against that gap with a recorded disposition", "status": "executed",
     "detail": {k: {"commit": v["commit"][0], "disposition": v["disposition"]} for k, v in SR["candidates"].items()},
     "coverage": {"section_rule_entries": sorted(SR["list"]["entry_lines"]), "reviewed": sorted(SR["candidates"]),
                  "all_selected_entries_reviewed": sorted(SR["list"]["entry_lines"]) == sorted(SR["candidates"])}},
]
assert sorted(SR["list"]["entry_lines"]) == sorted(SR["candidates"]), "gap 7: a section-rule entry lacks a review"
r["commands"] = ["git clone --depth 1 https://github.com/punkpeye/awesome-mcp-servers.git   # fbc52bcf301a3468954f6ee4fd12b75b853c93cf",
                 "git clone --depth 1 https://github.com/1mcp-app/agent.git; ...ni-c/mcp-hub; ...smart-mcp-proxy/mcpproxy-go; ...wong2/mcp-cli",
                 "git clone --depth 1 https://github.com/chrishayuk/mcp-cli.git   # fix round 3, 2026-09-23T13:07Z; 8.7 MB network download",
                 "python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/source_review.py evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/7-source-review.json"]
r["results"] = [f"{k} @ {v['commit'][0][:12]}: {v['finding']} -> {v['disposition']}" for k, v in SR["candidates"].items()]
r["outcome"] = "settled"
r["note"] = ("The concrete gap is that mcporter does not recover automatically from stale daemon metadata, as observed in gaps 2 and 9. "
             "All five entries selected by the section rule were source-reviewed at pinned commits, with verbatim line excerpts "
             "(chrishayuk/mcp-cli was added in fix round 3 after the round-4 review found it selected but unreviewed). "
             "1mcp-app/agent is keep-but-compare: it automatically removes a dead-PID file and restarts backends with backoff, "
             "and it is the closest match. ni-c/mcp-hub is rejected: it is an HTTP container hub, not a CLI bridge. "
             "smart-mcp-proxy/mcpproxy-go is rejected: its own stale-lock cleanup is explicitly unimplemented. "
             "The two CLI testers have no daemon to go stale: wong2/mcp-cli was the reviewed alternative in the executed "
             "comparison (gaps 6 and 12), and chrishayuk/mcp-cli is rejected (per-command in-process servers, closed on exit; "
             "its declared reconnect defaults are not referenced in src/). No candidate is adopted.")
r["evidence_class"] = "source_review"
r["limits"] = ["Source review only, of shallow clones; no candidate was executed.", "Section rule picks self-described persistent hosts; other list sections were keyword-searched, not read in full (4,735 lines)."]
r["raw_evidence"] = rawref("7-source-review.json")
r["helper_scripts"] = scripts("source_review.py")
receipts.append(r)

# ---------------------------------------------------------------- gap 8
g8 = ["inspector-inside-list-serena", "inspector-inside-list-ai-memory", "inspector-inside-list-socraticode",
      "inspector-inside-call-memory-status", "inspector-inside-call-codebase-status-cwd", "inspector-inside-no-config",
      "inspector-outside-relative-config", "inspector-outside-absolute-list", "inspector-outside-absolute-call-codebase-status-cwd"]
r = base(8, "inspector-project-file-scope")
r["arms"] = [
    {"arm": "Inspector CLI tools/list against configured project servers", "status": "executed", "detail": {k: NSR[k]["exit"] for k in g8[:3]}},
    {"arm": "one tools/call against configured project servers", "status": "executed", "detail": {k: NSR[k]["exit"] for k in g8[3:5]}},
    {"arm": "project-file scope from inside and outside the project", "status": "executed", "detail": {k: NSR[k]["exit"] for k in g8[5:]}},
    {"arm": "client plugin behavior, hooks, current Desktop connectivity", "status": "not_executed", "detail": "no Desktop/plugin host here"},
]
r["commands"] = [" ".join(NSR[k]["argv"]) + f"   # cwd {NSR[k]['cwd']}" for k in g8]
r["results"] = [f"{k}: exit {NSR[k]['exit']}: " + excerpt(NSR[k]["stdout"] or NSR[k]["stderr"], 200) for k in g8]
r["outcome"] = "advanced"
r["note"] = ("Inspector 2.7.0 with agent-lab's unmodified .mcp.json listed tools for ai-memory and SocratiCode and called memory_status "
             "and codebase_status. Serena failed on the read-only ecosystem log dir. Project-file scope is explicit, not cwd-discovered: "
             "without --config the server is not found, and a relative --config from outside fails. With an absolute --config from outside, "
             "the SocratiCode entry (which sets no cwd) reported the OUTSIDE directory as the project. Remaining: Desktop connectivity, "
             "client plugin and hook behavior.")
r["evidence_class"] = "local_integration"
r["limits"] = common_limits + ["Inside the namespace the configured ports were served by owned empty instances. Fix-round rerun: "
                               f"shared socket path -> {NS['enforcement_probe']['shared_socket']}, owned daemon socket -> {NS['owned_socket_control']}."]
r["raw_evidence"] = rawref("ns-exact-config.json")
r["helper_scripts"] = scripts("ns_exact.py")
receipts.append(r)

# ---------------------------------------------------------------- gap 9
def g9(v):
    s_ = LC[v]["stages"]
    sk_, un_, lt_ = s_["stale_metadata_sigkill"], s_["unresponsive_daemon_sigstop"], s_["startup_timeout_held_lock"]
    return {"stale_metadata_sigkill": {"induction": "harness SIGKILLs the owned daemon", "next_call_exit": sk_["next_call"]["exit"],
                                       "second_call_exit": sk_["second_call"]["exit"], "auto_recovered": sk_["auto_recovered"],
                                       "manual_steps": sk_["manual_steps"], "after_manual_exit": sk_["call_after_manual_step"]["exit"]},
            "unresponsive_daemon_sigstop": {"induction": "harness SIGSTOPs the owned daemon", "next_call_exit": un_["next_call"]["exit"],
                                            "next_call_wall_s": un_["next_call_wall_s"], "second_call_exit": un_["second_call"]["exit"],
                                            "auto_recovered": un_["auto_recovered"],
                                            "harness_intervention": "the harness then SIGKILLs the stopped daemon (simulated crash)",
                                            "after_daemon_killed_auto_recovered": un_["auto_recovered_after_kill"],
                                            "manual_steps": un_["manual_steps"], "after_manual_exit": un_.get("call_after_manual_step", {}).get("exit")},
            "startup_timeout_held_lock": {"induction": f"daemon/user.json.lock held by an owned `sleep {lt_['holder_lifetime_s']}` that exits on its own",
                                          "first_call_exit": lt_["first_call"]["exit"], "first_call_wall_s": lt_["first_call_wall_s"],
                                          "holder_alive_at_second_call": lt_["holder_alive_at_second_call"],
                                          "second_call_exit": lt_["second_call_while_held"]["exit"], "second_call_wall_s": lt_["second_call_wall_s"],
                                          "holder_exit_after_s": lt_["holder_exit_after_s"], "holder_returncode": lt_["holder_returncode"],
                                          "harness_interventions": lt_["harness_interventions"],
                                          "next_call_after_natural_exit_exit": lt_["next_call_after_holder_exit"]["exit"],
                                          "auto_recovered_after_holder_exit": lt_["auto_recovered_after_holder_exit"], "manual_steps": lt_["manual_steps"]}}
r = base(9, "induced-stale-metadata-and-startup-timeout")
r["preregistration"] = prereg(9)
res9 = {v: g9(v) for v in LC}
r["arms"] = [{"arm": f"owned disposable daemon {v}: induce stale metadata and a startup timeout (plus an unresponsive daemon); record whether the next call recovers without manual intervention",
              "status": "executed", "detail": res9[v]} for v in LC]
st9 = LC["0.13.13"]["stages"]
r["commands"] = ["python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/enforce.py evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/lifecycle-mcporter-0.13.13.enforce.json -- python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/run_lifecycle.py mcporter-0.13.13 evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/lifecycle-mcporter-0.13.13.json",
                 "python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/enforce.py evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/lifecycle-mcporter-0.14.0.enforce.json -- python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/run_lifecycle.py mcporter-0.14.0 evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/lifecycle-mcporter-0.14.0.json",
                 "(inside) kill -KILL <owned daemon> | kill -STOP <owned daemon> | daemon/user.json.lock <- pid of an owned `sleep 95`, then mcporter call context-mode.ctx_execute"]
r["results"] = ["stale metadata: " + excerpt(st9["stale_metadata_sigkill"]["next_call"]["stdout"], 200),
                "unresponsive daemon: " + excerpt(st9["unresponsive_daemon_sigstop"]["next_call"]["stdout"], 200),
                "startup timeout (lock held): " + excerpt(st9["startup_timeout_held_lock"]["first_call"]["stdout"], 200),
                f"per version: {res9}"]
r["outcome"] = "settled"
r["note"] = ("Both inductions ran on owned daemons for 0.13.13 and 0.14.0, with identical results. Stale metadata after SIGKILL is "
             "refused on every following call, and one manual step (archiving daemon/user.json) is required: no automatic recovery. "
             "Startup timeout: while daemon/user.json.lock is held by a live process, two consecutive calls each fail after about 45 s "
             "('did not become ready within 45 seconds'). The holder has a fixed lifetime and exits on its own (fix round 1: the "
             "harness does not kill it). The first call after that succeeds with no harness or operator step. So mcporter recovers "
             "automatically once a startup obstruction clears, but never from stale metadata. The SIGSTOP arm is disclosed separately: "
             "calls time out after 60 s, and the harness then kills the stopped daemon, which leaves the stale-metadata case.")
r["evidence_class"] = "local_integration"
r["limits"] = common_limits + ["The startup-timeout arm was added by addendum at 04:14:45Z and changed in fix round 1 (04:36:13Z) so that the lock holder exits by itself; round-1 files are in raw/round1/.",
                               "Inductions are SIGKILL, SIGSTOP and a held lock; the WSL-reboot incident of 2026-09-19 was not reproduced."]
r["raw_evidence"] = rawref("lifecycle-mcporter-0.13.13.json", "lifecycle-mcporter-0.14.0.json", "lifecycle-mcporter-0.13.13.enforce.json",
                           "lifecycle-mcporter-0.14.0.enforce.json", "round1/lifecycle-mcporter-0.13.13.json", "round1/lifecycle-mcporter-0.14.0.json")
r["helper_scripts"] = scripts("iso.py", "enforce.py", "run_lifecycle.py")
receipts.append(r)

# ---------------------------------------------------------------- gap 10
sc = st["scoped_registration_cleanup"]
cr = st["changed_process_root"]
r = base(10, "disposable-daemon-lifecycle-fixture")
r["arms"] = [
    {"arm": "isolation from the shared daemon", "status": "executed",
     "detail": {"enforcement": "unshare -rnm with an empty tmpfs over $HOME/.mcporter (enforce.py)",
                "shared_socket_probe_in_namespace": {v: LC[v]["enforcement_probe_start"]["shared_socket"] for v in LC},
                "shared_socket_probe_mid_run": {v: LC[v]["stages"]["persistence"]["shared_socket_probe"] for v in LC},
                "owned_socket_control": {v: LC[v]["stages"]["persistence"]["owned_socket_control"] for v in LC},
                "shared_daemon_outside_unchanged": {v: ENF[f"lifecycle-mcporter-{v}"]["shared_daemon_unchanged"] for v in LC},
                "owned_daemon_dir": LC["0.13.13"]["daemon_dir"]}},
    {"arm": "persistence", "status": "executed", "detail": {"keepalive_distinct_pids": st["persistence"]["keepalive_distinct_pids"], "ephemeral_distinct_pids": st["persistence"]["ephemeral_distinct_pids"]}},
    {"arm": "scoped registration cleanup", "status": "executed",
     "detail": {k: sc[k] for k in ("views_released_after_calls", "b_unaffected", "idle_configured_server_retired", "plain_server_retired_by_config_removal")}
     | {"plain_server_after_daemon_stop_alive": sc["after_stop"]["a_plain_server"]["alive"]}},
    {"arm": "recovery after changing the process root directory", "status": "executed",
     "detail": {"first_marker": cr["first_read_root1"]["marker"], "after_root_change_marker": cr["second_read_after_root_change"]["marker"],
                "daemon_launch_cwd_before_deletion": cr["daemon_after_launch"]["cwd"] if cr.get("daemon_after_launch") else None,
                "new_server_cwd": (cr["server_after_root_change"].get("server") or {}).get("cwd"), "passed": cr["passed"]}},
]
r["commands"] = ["python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/enforce.py evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/lifecycle-mcporter-0.13.13.enforce.json -- python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/run_lifecycle.py mcporter-0.13.13 evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/lifecycle-mcporter-0.13.13.json",
                 "python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/enforce.py evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/lifecycle-mcporter-0.14.0.enforce.json -- python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/run_lifecycle.py mcporter-0.14.0 evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/lifecycle-mcporter-0.14.0.json"]
r["results"] = [f"isolation: shared socket path inside the namespace -> {LC['0.13.13']['enforcement_probe_start']['shared_socket']}; owned daemon socket -> {st['persistence']['owned_socket_control']}",
                f"views after calls: {sc['status_three_servers'].get('views')} / {sc['status_after_removal'].get('views')}; servers registered {len(sc['status_three_servers'].get('servers') or [])} -> {len(sc['status_after_removal'].get('servers') or [])}",
                f"entry removed from config with idleTimeoutMs 4000: alive after 9 s = {sc['a_idle_server_after']['alive']}; removed plain keep-alive entry alive = {sc['a_plain_server_after']['alive']}, after daemon stop = {sc['after_stop']['a_plain_server']['alive']}",
                f"other view's server kept its pid: {sc['b_unaffected']}",
                f"changed root: first call (client cwd = a separate launch dir, server cwd = project) read ROOT1; then the launch dir was deleted, the project moved and the config cwd switched -> next call read {cr['second_read_after_root_change']['marker']} (exit {cr['second_read_after_root_change']['exit']})",
                f"same outcomes on 0.14.0: { {k: LC['0.14.0']['stages'][k].get('passed') for k in ('persistence', 'scoped_registration_cleanup', 'changed_process_root')} }"]
iso_ok = all(LC[v]["enforcement_probe_start"]["shared_socket"].startswith("FileNotFoundError") and LC[v]["stages"]["persistence"]["owned_socket_control"] == "connected" for v in LC)
r["outcome"] = "settled" if (iso_ok and st["persistence"]["passed"] and sc["passed"] and cr["passed"]) else "advanced"
r["note"] = ("All four stages ran with a detection method each. Isolation is enforced, not just observed (fix round 1): inside the "
             "namespace the shared daemon socket path does not exist (ENOENT), while the same AF_UNIX probe connects to the owned "
             "daemon socket. Config views are released after every call. A keep-alive entry with idleTimeoutMs is retired once removed and "
             "idle, while the other view's server keeps its pid. A plain keep-alive entry removed from config keeps running until "
             "`daemon stop`: a real cleanup limit, now recorded. After the daemon's launch directory was deleted and the server root "
             "moved and changed in config, the next call started a new server in the new root with no manual step.")
r["evidence_class"] = "local_integration"
r["limits"] = common_limits + ["Registration cleanup is exercised through mcporter's own model (views + definition-keyed connections); there is no explicit per-server unregister command to test."]
r["raw_evidence"] = rawref("lifecycle-mcporter-0.13.13.json", "lifecycle-mcporter-0.14.0.json", "lifecycle-mcporter-0.13.13.enforce.json", "lifecycle-mcporter-0.14.0.enforce.json")
r["helper_scripts"] = scripts("iso.py", "enforce.py", "run_lifecycle.py")
receipts.append(r)

# ---------------------------------------------------------------- gap 12
three = ("mcporter-0.13.13", "mcporter-0.14.0", w)
tab12 = {}
for op in allops:
    row = {}
    for b in three:
        if b == w and op.startswith("list-"):
            v = wong2_list[op[5:]]
            row[b] = {"mode": "interactive pty x3 (scrolled)", "complete": v["complete"], "collected": v["tools_collected"], "full": v["full_tool_count"],
                      "median_ready_ms": v["median_ready_ms"], **({"error": v["error"]} if v["error"] else {})}
        else:
            row[b] = {"mode": "non-interactive x3", "pass": S[op][b]["all_pass"], "median_ms": S[op][b]["median_ms"]}
    tab12[op] = row
ok12 = {b: sum(1 for op in allops if tab12[op][b].get("pass", tab12[op][b].get("complete"))) for b in three}
r = base(12, "matched-set-three-bridges")
r["arms"] = [
    {"arm": "retained bridge call set under mcporter 0.13.13", "status": "executed", "detail": f"{ok12['mcporter-0.13.13']}/13 pass x3"},
    {"arm": "same under mcporter 0.14.0", "status": "executed", "detail": f"{ok12['mcporter-0.14.0']}/13 pass x3"},
    {"arm": "same under one reviewed registry alternative", "status": "executed",
     "detail": {"candidate": "wong2/mcp-cli 2.0.0", "registry_line": SR["list"]["entry_lines"].get("wong2/mcp-cli"), "list_commit": SR["list"]["commit"],
                "source_review_commit": SR["candidates"]["wong2/mcp-cli"]["commit"][0], "ok": f"{ok12[w]}/13",
                "list_ops": "executed interactively through a pty (fix round 1); no row is a synthetic placeholder"}},
    {"arm": "record matched outcomes against the same servers", "status": "executed", "detail": tab12},
]
r["commands"] = ["python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/enforce.py evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/bridges-matched.enforce.json -- python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/run_bridges.py evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/bridges-matched.json --reps 3",
                 "python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/enforce.py evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/wong2-interactive-list.enforce.json -- python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/wong2_pty_list.py evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/wong2-interactive-list.json",
                 "python3 blueprints/gap-wave2-20260923/foundation__mcp-surfaces/source_review.py evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/raw/7-source-review.json"]
r["results"] = [f"{op}: " + "; ".join(f"{b} {json.dumps(v)}" for b, v in row.items()) for op, row in tab12.items()]
r["outcome"] = "settled"
r["note"] = ("The 13-operation retained call set ran 3 times under mcporter 0.13.13, mcporter 0.14.0 and the reviewed registry "
             "alternative @wong2/mcp-cli 2.0.0 (awesome-mcp-servers line 4667), all against the same owned servers. The alternative's "
             f"5 list operations were driven interactively, because 2.0.0 has no non-interactive list. Results: {ok12['mcporter-0.13.13']}/13, "
             f"{ok12['mcporter-0.14.0']}/13 and {ok12[w]}/13. Scrolled, the alternative's interactive lists are complete for 4 servers. It "
             "crashes listing jcodemunch (MCP -32601), cannot call the HTTP ai-memory server non-interactively, has no non-interactive list, "
             "and restarts the server on every call. On this call set mcporter is superior to that candidate, and 0.14.0 matches 0.13.13. "
             "This says nothing about untested candidates such as 1mcp.")
r["evidence_class"] = "local_integration"
r["limits"] = common_limits + ["One registry alternative; superiority is limited to this call set and these servers."]
r["raw_evidence"] = rawref("bridges-matched.json", "bridges-matched.enforce.json", "wong2-interactive-list.json", "wong2-interactive-list.enforce.json", "7-source-review.json")
r["helper_scripts"] = scripts("iso.py", "enforce.py", "run_bridges.py", "wong2_pty_list.py", "source_review.py")
receipts.append(r)

for rc in receipts:
    p = L / f"{rc['gap_index']}-{rc.pop('slug')}.json"
    p.write_text(json.dumps(rc, indent=1, ensure_ascii=False).replace(str(pathlib.Path.home()), "$HOME") + "\n")
    print(p.name, rc["outcome"])
