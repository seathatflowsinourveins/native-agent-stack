#!/usr/bin/env python3
"""Owned-daemon lifecycle fixture for gaps 2, 9 and 10 (foundation/mcp-surfaces, wave 2).

Usage: run_lifecycle.py BRIDGE OUT_JSON      (BRIDGE = mcporter-0.13.13 | mcporter-0.14.0)

Every daemon here is owned: MCPORTER_DAEMON_DIR points into $HOME/.cache/gap-wave2-20260923, and any
signal is sent only to a pid whose /proc environ carries that directory (iso.Fixture.owned_daemon_pids).
The shared per-user daemon ($HOME/.mcporter/daemon) is only stat()ed before and after.

Detection methods
  server identity   ctx_execute(javascript) prints process.ppid = the context-mode server pid; the pid's
                    /proc cmdline is recorded to prove it is the server.
  persistence       same server pid across consecutive calls for a keep-alive entry; an identical entry with
                    lifecycle "ephemeral" is the negative control (must show distinct pids).
  cleanup           /proc scan for any process whose environ carries this fixture's HOME.
  recovery          exit status and stderr of the first call after the induced fault, with no manual step.
"""
import json
import os
import pathlib
import re
import signal
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import iso  # noqa: E402

BRIDGE = sys.argv[1]
OUT = pathlib.Path(sys.argv[2])
M = iso.BINS[BRIDGE]
f = iso.Fixture("lc" + BRIDGE.split("-")[-1].replace(".", ""))
rec = {"bridge": BRIDGE, "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
       "fixture_root": iso.sanitize(str(f.root)), "daemon_dir": iso.sanitize(f.env["MCPORTER_DAEMON_DIR"]),
       "shared_daemon_before": iso.shared_daemon_snapshot(), "enforcement_probe_start": iso.enforcement_probe(), "stages": {}}


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def pid_info(pid):
    try:
        cmd = pathlib.Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
        cwd = os.readlink(f"/proc/{pid}/cwd")
        return {"pid": pid, "alive": True, "cmd": iso.sanitize(cmd[:160]), "cwd": iso.sanitize(cwd)}
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return {"pid": pid, "alive": False}


def ppid_of(r):
    m = re.search(r"PPID=(\d+)", r["stdout"])
    return int(m.group(1)) if m else None


def slim(r, keep=600):
    return {k: (v[:keep] if isinstance(v, str) else v) for k, v in r.items()}


def ctx(cfg, server="context-mode", cwd=None, timeout=120):
    r = f.run([M, "--config", str(cfg), "call", f"{server}.ctx_execute", "--args",
               json.dumps({"language": "javascript", "code": "console.log('PPID=' + process.ppid)"}),
               "--output", "json", "--no-oauth"], cwd=cwd or proj, timeout=timeout)
    r["server_pid"] = ppid_of(r)
    if r["server_pid"]:
        r["server"] = pid_info(r["server_pid"])
    return slim(r)


def readfile(cfg, server="context-mode", cwd=None):
    r = f.run([M, "--config", str(cfg), "call", f"{server}.ctx_execute_file", "--args",
               json.dumps({"path": "marker.txt", "language": "python", "code": "print('MARK=' + FILE_CONTENT.strip())"}),
               "--output", "json", "--no-oauth"], cwd=cwd or proj, timeout=120)
    m = re.search(r"MARK=(\w+)", r["stdout"])
    r["marker"] = m.group(1) if m else None
    return slim(r)


def daemon(cmd, *extra, timeout=60):
    return slim(f.run([M, "daemon", cmd, *extra], timeout=timeout))


def status():
    r = f.run([M, "daemon", "status", "--json"], timeout=30)
    try:
        j = json.loads(r["stdout"])
        return {"exit": r["exit"], "pid": j.get("pid"), "servers": j.get("servers"), "views": j.get("views"),
                "generation": j.get("generation")}
    except Exception:  # noqa: BLE001
        return slim(r, 400)


def owned():
    return {"daemon_pids": f.owned_daemon_pids(), "fixture_processes": f.owned_procs_under_root(),
            "daemon_dir": f.daemon_metadata() and sorted(f.daemon_metadata().keys())}


try:
    proj = f.project_fixture()
    (proj / "marker.txt").write_text("ROOT1\n")
    defs = f.server_defs(proj)
    cm = defs["context-mode"]
    eph = json.loads(json.dumps(cm))
    eph["lifecycle"] = "ephemeral"
    cfg = f.root / "state/mcporter.json"
    cfg.write_text(json.dumps({"imports": [], "mcpServers": {"context-mode": cm, "context-mode-eph": eph}}, indent=1))

    # ---- stage: persistence (gap 2, gap 10) -------------------------------
    t_start = now()
    st = {"started": t_start, "keepalive_calls": [ctx(cfg) for _ in range(3)],
          "ephemeral_calls": [ctx(cfg, "context-mode-eph") for _ in range(3)], "daemon_status": status()}
    ka = {c["server_pid"] for c in st["keepalive_calls"]}
    ep = [c["server_pid"] for c in st["ephemeral_calls"]]
    st["keepalive_distinct_pids"] = len(ka)
    st["ephemeral_distinct_pids"] = len(set(ep))
    st["passed"] = len(ka) == 1 and None not in ka and len(set(ep)) == 3 and None not in ep
    # owned control for the contact probe: the same AF_UNIX probe connects to the owned daemon socket
    st["owned_socket_control"] = iso.socket_probe(pathlib.Path(f.env["MCPORTER_DAEMON_DIR"]) / "daemon/user.sock")
    st["shared_socket_probe"] = iso.socket_probe(iso.SHARED_DAEMON_DIR / "user.sock")
    rec["stages"]["persistence"] = st

    # ---- stage: restart via daemon stop / next call (gap 2) ---------------
    t_start = now()
    before = status()
    server_before = st["keepalive_calls"][-1]["server_pid"]
    stop = daemon("stop")
    time.sleep(1)
    after_stop = {"owned": owned(), "old_daemon": pid_info(before.get("pid")) if before.get("pid") else None,
                  "old_server": pid_info(server_before)}
    call = ctx(cfg)
    rs = {"started": t_start, "status_before": before, "stop": stop, "after_stop": after_stop,
          "next_call": call, "status_after": status()}
    rs["passed"] = (call["exit"] == 0 and rs["status_after"].get("pid") not in (None, before.get("pid"))
                    and call["server_pid"] not in (None, server_before) and not after_stop["old_server"]["alive"])
    # explicit restart subcommand
    pre = status()
    rs["restart_cmd"] = daemon("restart")
    rs["after_restart_call"] = ctx(cfg)
    rs["status_after_restart"] = status()
    rs["restart_cmd_passed"] = (rs["restart_cmd"]["exit"] == 0 and rs["after_restart_call"]["exit"] == 0
                                and rs["status_after_restart"].get("pid") not in (None, pre.get("pid")))
    rec["stages"]["restart"] = rs

    # ---- stage: cleanup after stop (gap 2) ---------------------------------
    t_start = now()
    s_pre = status()
    srv = rs["after_restart_call"]["server_pid"]
    stop = daemon("stop")
    time.sleep(1)
    cl = {"started": t_start, "stop": stop, "server_pid_before": srv, "daemon_pid_before": s_pre.get("pid"),
          "after": owned(), "server_after": pid_info(srv) if srv else None,
          "daemon_after": pid_info(s_pre["pid"]) if s_pre.get("pid") else None}
    cl["passed"] = (not cl["after"]["fixture_processes"] and not cl["after"]["daemon_pids"]
                    and not (cl["server_after"] or {}).get("alive") and "user.sock" not in (cl["after"]["daemon_dir"] or []))
    rec["stages"]["cleanup"] = cl

    # ---- stage: scoped registration cleanup (gap 10) -----------------------
    # Daemon model (dist/daemon/broker.js): each CLI call registers a config *view* and releases it;
    # server connections are keyed by definition identity and retire only on idle timeout (if the
    # definition sets lifecycle.idleTimeoutMs) or on daemon stop/drain. Definitions differ by an env
    # marker so the three entries cannot share one connection.
    def variant(marker, lifecycle):
        d = json.loads(json.dumps(cm))
        d["env"]["FIXTURE_VIEW"] = marker
        d["lifecycle"] = lifecycle
        return d
    cfg_a = f.root / "state/mcporter-a.json"
    cfg_b = f.root / "state/mcporter-b.json"
    cfg_a.write_text(json.dumps({"imports": [], "mcpServers": {
        "cm-a-idle": variant("a-idle", {"mode": "keep-alive", "idleTimeoutMs": 4000}),
        "cm-a-plain": variant("a-plain", "keep-alive")}}, indent=1))
    cfg_b.write_text(json.dumps({"imports": [], "mcpServers": {"cm-b": variant("b", "keep-alive")}}, indent=1))
    t_start = now()
    a_idle, a_plain, b1 = ctx(cfg_a, "cm-a-idle"), ctx(cfg_a, "cm-a-plain"), ctx(cfg_b, "cm-b")
    sc = {"started": t_start, "a_idle_call": a_idle, "a_plain_call": a_plain, "b_call": b1, "status_three_servers": status()}
    # remove both A entries from view A's config (keep one ephemeral entry so the file stays valid)
    cfg_a.write_text(json.dumps({"imports": [], "mcpServers": {"context-mode-eph": eph}}, indent=1))
    sc["view_a_list_after_removal"] = slim(f.run([M, "--config", str(cfg_a), "list", "--no-oauth"], cwd=proj, timeout=120), 400)
    time.sleep(9)  # > idleTimeoutMs 4000 plus timer slack
    sc["a_idle_server_after"] = pid_info(a_idle["server_pid"]) if a_idle["server_pid"] else None
    sc["a_plain_server_after"] = pid_info(a_plain["server_pid"]) if a_plain["server_pid"] else None
    sc["b_call_after"] = ctx(cfg_b, "cm-b")
    sc["status_after_removal"] = status()
    sc["views_released_after_calls"] = sc["status_three_servers"].get("views") == 0 and sc["status_after_removal"].get("views") == 0
    sc["b_unaffected"] = b1["server_pid"] is not None and sc["b_call_after"]["server_pid"] == b1["server_pid"]
    sc["idle_configured_server_retired"] = not (sc["a_idle_server_after"] or {}).get("alive", True)
    sc["plain_server_retired_by_config_removal"] = not (sc["a_plain_server_after"] or {}).get("alive", True)
    sc["passed"] = sc["views_released_after_calls"] and sc["b_unaffected"] and sc["idle_configured_server_retired"]
    stop = daemon("stop")
    time.sleep(1)
    sc["after_stop"] = {"stop": stop, "a_plain_server": pid_info(a_plain["server_pid"]) if a_plain["server_pid"] else None,
                        "b_server": pid_info(b1["server_pid"]) if b1["server_pid"] else None, "owned": owned()}
    rec["stages"]["scoped_registration_cleanup"] = sc

    # ---- stage: changed process root (gap 10) ------------------------------
    t_start = now()
    launch_dir = f.root / "launch-dir"
    launch_dir.mkdir()
    root2 = f.root / "project-root2"
    root2.mkdir()
    (root2 / "marker.txt").write_text("ROOT2\n")
    first = readfile(cfg, cwd=launch_dir)  # daemon is auto-launched from launch_dir
    dstat = status()
    dcwd = pid_info(dstat.get("pid")) if dstat.get("pid") else None
    import shutil
    shutil.rmtree(launch_dir)  # the daemon's launch directory disappears
    moved = f.root / "project-moved"
    os.rename(proj, moved)  # the keep-alive server's process root is moved away
    cm2 = json.loads(json.dumps(cm))
    cm2["cwd"] = str(root2)
    cm2["env"]["CONTEXT_MODE_PROJECT_DIR"] = str(root2)
    cfg.write_text(json.dumps({"imports": [], "mcpServers": {"context-mode": cm2, "context-mode-eph": eph}}, indent=1))
    second = readfile(cfg, cwd=root2)
    third = ctx(cfg, cwd=root2)
    cr = {"started": t_start, "first_read_root1": first, "daemon_after_launch": dcwd, "second_read_after_root_change": second,
          "server_after_root_change": third, "status": status()}
    cr["passed"] = first.get("marker") == "ROOT1" and second.get("marker") == "ROOT2" and second["exit"] == 0
    os.rename(moved, proj)
    cfg.write_text(json.dumps({"imports": [], "mcpServers": {"context-mode": cm, "context-mode-eph": eph}}, indent=1))
    rec["stages"]["changed_process_root"] = cr
    daemon("stop")
    time.sleep(1)

    # ---- stage: stale metadata after SIGKILL (gaps 2, 9) -------------------
    t_start = now()
    warm = ctx(cfg)
    s = status()
    dpid = s.get("pid")
    assert dpid in f.owned_daemon_pids() and dpid != rec["shared_daemon_before"].get("metadata_pid"), "not an owned daemon"
    os.kill(dpid, signal.SIGKILL)
    time.sleep(1)
    orphan = pid_info(warm["server_pid"]) if warm["server_pid"] else None
    first = ctx(cfg, timeout=120)
    second = ctx(cfg, timeout=120)
    sk = {"started": t_start, "warm_call": warm, "killed_daemon_pid": dpid, "metadata_after_kill": f.daemon_metadata(),
          "server_after_daemon_kill": orphan, "next_call": first, "second_call": second}
    sk["auto_recovered"] = first["exit"] == 0
    # minimal manual step: archive only the stale metadata file (as the retained 2026-09-19 recovery did)
    meta = pathlib.Path(f.env["MCPORTER_DAEMON_DIR"]) / "daemon/user.json"
    manual = []
    if meta.exists() and first["exit"] != 0:
        meta.rename(meta.with_suffix(".json.stale-archived"))
        manual.append("archived daemon/user.json only (key and config kept)")
    sk["manual_steps"] = manual
    sk["call_after_manual_step"] = ctx(cfg, timeout=120) if manual else None
    sk["orphan_server_after_recovery"] = pid_info(warm["server_pid"]) if warm["server_pid"] else None
    rec["stages"]["stale_metadata_sigkill"] = sk
    daemon("stop")
    time.sleep(1)
    for o in f.owned_procs_under_root():  # reap an orphaned server from the killed daemon, if any
        if "cli.bundle.mjs" in o["cmd"]:
            os.kill(o["pid"], signal.SIGKILL)

    # ---- stage: unresponsive daemon / status-probe timeout (gap 9) ---------
    t_start = now()
    warm = ctx(cfg)
    s = status()
    dpid = s.get("pid")
    assert dpid in f.owned_daemon_pids() and dpid != rec["shared_daemon_before"].get("metadata_pid"), "not an owned daemon"
    os.kill(dpid, signal.SIGSTOP)
    t0 = time.time()
    hung = ctx(cfg, timeout=150)
    hung_s = round(time.time() - t0, 1)
    hung2 = ctx(cfg, timeout=150)
    un = {"started": t_start, "stopped_daemon_pid": dpid, "next_call": hung, "next_call_wall_s": hung_s, "second_call": hung2}
    un["auto_recovered"] = hung["exit"] == 0
    # obstruction removed the way a crash would remove it: the stopped daemon is killed -> stale metadata case
    os.kill(dpid, signal.SIGKILL)
    time.sleep(1)
    un["call_after_daemon_killed"] = ctx(cfg, timeout=150)
    un["auto_recovered_after_kill"] = un["call_after_daemon_killed"]["exit"] == 0
    meta = pathlib.Path(f.env["MCPORTER_DAEMON_DIR"]) / "daemon/user.json"
    un["manual_steps"] = []
    if meta.exists() and not un["auto_recovered_after_kill"]:
        meta.rename(meta.with_suffix(".json.stale-archived-2"))
        un["manual_steps"].append("archived daemon/user.json only")
        un["call_after_manual_step"] = ctx(cfg, timeout=150)
    rec["stages"]["unresponsive_daemon_sigstop"] = un
    daemon("stop")
    time.sleep(1)

    # ---- stage: daemon STARTUP timeout via a held metadata lock (gap 9, addendum 04:14:45Z) ----
    import subprocess
    ddir = pathlib.Path(f.env["MCPORTER_DAEMON_DIR"]) / "daemon"
    for stale in ddir.glob("user.json*"):
        stale.rename(ddir / f"archived-before-lock-stage.{stale.name}")
    # fix round 1: the holder EXITS ON ITS OWN (fixed lifetime); the harness never kills it
    HOLD_S = 95
    t_start = now()
    holder = subprocess.Popen(["sleep", str(HOLD_S)], env=f.env, start_new_session=True)
    holder_t0 = time.time()
    lock = ddir / "user.json.lock"
    lock.write_text(f"{holder.pid}\n{now()}\n")
    t0 = time.time()
    first = ctx(cfg, timeout=150)
    lt = {"started": t_start, "lock_holder_pid": holder.pid, "holder_lifetime_s": HOLD_S, "first_call": first,
          "first_call_wall_s": round(time.time() - t0, 1),
          "daemon_dir_after_first": sorted(f.daemon_metadata().keys()) + sorted(p.name for p in ddir.glob("*.lock")),
          "owned_daemon_pids_after_first": f.owned_daemon_pids()}
    lt["holder_alive_at_second_call"] = holder.poll() is None
    t1 = time.time()
    lt["second_call_while_held"] = ctx(cfg, timeout=150)
    lt["second_call_wall_s"] = round(time.time() - t1, 1)
    holder.wait(timeout=HOLD_S + 30)  # natural exit, no signal from the harness
    lt["holder_exit_after_s"] = round(time.time() - holder_t0, 1)
    lt["holder_returncode"] = holder.returncode
    time.sleep(1)
    lt["next_call_after_holder_exit"] = ctx(cfg, timeout=150)
    lt["auto_recovered_after_holder_exit"] = lt["next_call_after_holder_exit"]["exit"] == 0
    lt["harness_interventions"] = []
    lt["manual_steps"] = []
    if not lt["auto_recovered_after_holder_exit"]:
        lt["daemon_dir_before_manual"] = sorted(f.daemon_metadata().keys())
        meta = ddir / "user.json"
        if meta.exists():
            meta.rename(ddir / "user.json.stale-archived-3")
            lt["manual_steps"].append("archived daemon/user.json only")
            lt["call_after_manual_step"] = ctx(cfg, timeout=150)
    rec["stages"]["startup_timeout_held_lock"] = lt
    daemon("stop")
finally:
    rec["leftover_after_stop"] = f.stop()
    rec["owned_after_stop"] = owned()
    rec["shared_daemon_after"] = iso.shared_daemon_snapshot()
    rec["enforcement_probe_end"] = iso.enforcement_probe()
    rec["shared_daemon_unchanged"] = rec["shared_daemon_before"] == rec["shared_daemon_after"]
    rec["ended_at"] = now()
    OUT.write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n")

for k, v in rec["stages"].items():
    print(k.ljust(30), {kk: vv for kk, vv in v.items() if kk in ("passed", "auto_recovered", "auto_recovered_after_kill", "restart_cmd_passed",
                                                               "keepalive_distinct_pids", "ephemeral_distinct_pids", "manual_steps",
                                                               "b_unaffected", "idle_configured_server_retired", "plain_server_retired_by_config_removal",
                                                               "views_released_after_calls", "next_call_wall_s",
                                                               "first_call_wall_s", "second_call_wall_s", "holder_alive_at_second_call",
                                                               "holder_exit_after_s", "auto_recovered_after_holder_exit")})
print("enforcement:", rec["enforcement_probe_start"], "owned control:", rec["stages"].get("persistence", {}).get("owned_socket_control"))
print("shared daemon unchanged:", rec["shared_daemon_unchanged"], "leftover:", rec["leftover_after_stop"])
