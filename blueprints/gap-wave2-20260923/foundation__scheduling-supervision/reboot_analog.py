#!/usr/bin/env python3
"""Gap 11: ONE run that records both oracles together.

(a) Unchanged upstream Dagu retry tests at v2.16.6 (same archive, command and Go version
    as blueprints/convergence-practice/service-reboot/upstream-tests.sh; run locally from
    the prepared cache instead of the hosted runner).
(b) A real project workflow (validate.py + build_ecosystem.py --check on a HEAD snapshot,
    no model) carried through an orderly-restart ANALOG: boot1 and boot2 are separate
    unprivileged user+pid+mount namespaces (ns_init.py). This is not a kernel reboot.

Usage: reboot_analog.py --work /new/absolute/dir [--base-commit SHA]
Run under $HOME/codex-ecosystem/bin/ecosystem-bounded-run (Go compilation).
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import time

import dagu_common as dc
import real_steps as rs
from real_scheduled_recovery import reference, snapshot

GO_CACHE = Path.home() / ".cache/gap-wave2-20260923/scheduling-supervision/go-setup"
SRC_REV = "58fed633d58c1dd1319091fdb2c2f6158ecfa053"
SRC_SHA = "8f4b1095a88bb037b582f8b5e337360b1702879f1abb9cfc319643ef1a775746"
UPSTREAM_CMD = ["go", "test", "-count=1", "-run", "^TestRetryCommand($|_)", "-timeout", "12m", "-v", "./internal/cmd"]


def upstream(work):
    root = work / "upstream"
    (root / "reports").mkdir(parents=True)
    (root / "home").mkdir()
    archive = GO_CACHE / "dagu-source.tar.gz"
    archive_sha = rs.digest(archive)
    if archive_sha != SRC_SHA:
        raise ValueError("Upstream source archive hash mismatch")
    with tarfile.open(archive) as source:
        source.extractall(root / "source", filter="data")
    tree = root / "source" / f"dagu-{SRC_REV}"
    before = {str(p.relative_to(tree)): rs.digest(p) for p in tree.rglob("*") if p.is_file() and not p.is_symlink()}
    env = {"PATH": f"{GO_CACHE}/go/bin:/usr/bin:/bin", "HOME": str(root / "home"), "GOPATH": str(GO_CACHE / "gopath"),
           "GOCACHE": str(root / "go-cache"), "GOTOOLCHAIN": "local", "GOSUMDB": "sum.golang.org"}
    go_version = subprocess.run(["go", "version"], cwd=tree, env=env, capture_output=True, text=True).stdout.strip()
    started = time.time()
    proc = subprocess.run(["timeout", "--signal=TERM", "--kill-after=15s", "20m", *UPSTREAM_CMD], cwd=tree, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (root / "reports" / "upstream-tests.txt").write_text(proc.stdout)
    after = {name: rs.digest(tree / name) for name in before}
    text = proc.stdout
    return {"archive_sha256": archive_sha, "source_revision": SRC_REV, "go_version": go_version,
            "command": shlex.join(UPSTREAM_CMD), "exit_code": proc.returncode, "seconds": round(time.time() - started, 1),
            "top_level_pass": len(re.findall(r"^--- PASS", text, re.M)), "subtest_pass": len(re.findall(r"^\s+--- PASS", text, re.M)),
            "fail_records": len(re.findall(r"--- FAIL", text)), "skip_records": len(re.findall(r"--- SKIP", text)),
            "final_line": text.strip().splitlines()[-1] if text.strip() else "",
            "source_unchanged": before == after, "source_files": len(before),
            "report_sha256": rs.digest(root / "reports" / "upstream-tests.txt")}


def unshare(work, phase, run_id):
    argv = ["unshare", "--user", "--map-current-user", "--pid", "--fork", "--mount-proc",
            sys.executable, "-B", str(dc.HERE / "ns_init.py"), phase, str(work), run_id]
    out = (work / "native" / f"{phase}-ns.stdout").open("x")
    err = (work / "native" / f"{phase}-ns.stderr").open("x")
    return subprocess.Popen(argv, cwd=work, stdout=out, stderr=err, start_new_session=True)


def real_restart(work, commit):
    home = work / "dagu-home"
    home.mkdir()
    snap = snapshot(work, commit)
    ref = reference(work)
    config = work / "config.yaml"
    config.write_text("check_updates: false\n", encoding="utf-8")
    steps = {a: shlex.join([sys.executable, "-B", str(dc.HERE / "real_steps.py"), a, str(work)]) for a in ("checkpoint", "finalize")}
    workflow = work / "realboot.yaml"
    workflow.write_text("\n".join([
        "type: graph", "timeout_sec: 600", "max_active_runs: 1", "working_dir: " + json.dumps(str(work)), "steps:",
        "  - id: checkpoint", "    run: " + json.dumps(steps["checkpoint"]),
        "  - id: finalize", "    depends: [checkpoint]", "    run: " + json.dumps(steps["finalize"]), ""]), encoding="utf-8")
    env = {"HOME": str(work), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "DAGU_HOME": str(home), "TMPDIR": str(work),
           "XDG_CONFIG_HOME": str(work / "xdg-config"), "XDG_CACHE_HOME": str(work / "xdg-cache"), "DO_NOT_TRACK": "1"}
    base = [str(dc.DAGU), "--context", "local", "--dagu-home", str(home), "--config", str(config)]
    (work / "dagu-base.json").write_text(json.dumps(base))
    (work / "dagu-env.json").write_text(json.dumps(env))
    rec = dc.Recorder(work, env)
    rec.call("version", [str(dc.DAGU), "version"])
    rec.call("validate", base + ["validate", str(workflow)])
    run_id = "realboot-" + os.urandom(8).hex()
    timeline = {}
    boot1 = unshare(work, "boot1", run_id)
    try:
        if not dc.wait_for(lambda: (work / "finalize-ready.json").exists() or boot1.poll() is not None, 120):
            raise ValueError("Finalizer not reached in boot1")
        timeline["finalize_ready"] = datetime.now(timezone.utc).isoformat()
        owned = dc.descendants(boot1.pid)
        running = [r for r in dc.history_rows(rec.call("history-before-shutdown", base + ["history", "--run-id", run_id, "--format", "json"])) if r.get("dagRunId") == run_id]
        before = rs.verify_checkpoint(work)
        init_host_pid = [p for p, (parent, _) in dc.process_table().items() if parent == boot1.pid]
        os.kill(init_host_pid[0], signal.SIGTERM)
        timeline["shutdown_requested"] = datetime.now(timezone.utc).isoformat()
        boot1.wait(timeout=60)
        timeline["boot1_exited"] = datetime.now(timezone.utc).isoformat()
    finally:
        dc.stop_group(boot1)
    owned_remaining = len(dc.live(owned))
    after_shutdown = [r for r in dc.history_rows(rec.call("history-after-shutdown", base + ["history", "--run-id", run_id, "--format", "json"])) if r.get("dagRunId") == run_id]
    completed_before_boot2 = (work / "completed.json").exists()
    boot1_init_alive_at_boot2 = bool(dc.live({p: s for p, s in owned.items() if p in init_host_pid}))
    boot2 = unshare(work, "boot2", run_id)
    try:
        boot2.wait(timeout=300)
    finally:
        dc.stop_group(boot2)
    timeline["boot2_exited"] = datetime.now(timezone.utc).isoformat()
    succeeded = [r for r in dc.history_rows(rec.call("history-after-boot2", base + ["history", "--run-id", run_id, "--format", "json"])) if r.get("dagRunId") == run_id]
    attempts = []
    for status_file in sorted(home.glob("data/dag-runs/realboot/dag-runs/*/*/*/*/*/status.jsonl")):
        last = json.loads(status_file.read_text().splitlines()[-1])
        attempts.append({"attempt_dir": status_file.parent.name, "status": last.get("status"), "triggerType": last.get("triggerType")})
    completed = json.loads((work / "completed.json").read_text()) if (work / "completed.json").exists() else None
    checkpoint = json.loads((work / "checkpoint.json").read_text())
    ids = [json.loads((work / f"boot{i}-identity.json").read_text()) for i in (1, 2)]
    checks = {
        "running_before_shutdown": len(running) == 1 and running[0]["status"] == "running",
        "no_completed_effect_before_boot2": not completed_before_boot2,
        "boot_identity_changed": ids[0]["boot_token"] != ids[1]["boot_token"] and not boot1_init_alive_at_boot2,
        "boot1_processes_retired": owned_remaining == 0,
        "status_after_shutdown": after_shutdown[0]["status"] if after_shutdown else None,
        "boot2_retry_exit_zero": boot2.returncode == 0,
        "after_retry_succeeded_same_run_id": len(succeeded) == 1 and succeeded[0]["status"] == "succeeded",
        "checkpoint_unchanged_count_one": completed is not None and rs.verify_checkpoint(work) == before == completed["checkpoint_sha256"] and checkpoint["execution_count"] == 1,
        "validate_equals_reference": completed is not None and checkpoint["validate"]["stdout_first_line"] == ref["validate"] == completed["validate"]["stdout_first_line"],
        "ecosystem_equals_reference": completed is not None and completed["ecosystem"]["stdout_first_line"] == ref["ecosystem"],
    }
    passed = all(v for k, v in checks.items() if k != "status_after_shutdown") and checks["status_after_shutdown"] in ("aborted", "failed")
    return {"status": "passed" if passed else "failed", "checks": checks, "run_id": run_id, "snapshot": snap,
            "reference": ref, "boot_identities": ids, "boot1_init_alive_at_boot2": boot1_init_alive_at_boot2, "timeline_utc": timeline, "native_attempts": attempts,
            "boot1_shutdown": json.loads((work / "boot1-shutdown.json").read_text()) if (work / "boot1-shutdown.json").exists() else None,
            "boot2_service": json.loads((work / "boot2-service.json").read_text()) if (work / "boot2-service.json").exists() else None,
            "command_exit_codes": rec.codes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--base-commit", default="41d39b3")
    args = parser.parse_args()
    work = args.work
    if not work.is_absolute() or work.exists():
        raise SystemExit("--work must name a new absolute directory")
    work.mkdir(mode=0o700, parents=True)
    os.umask(0o077)
    if rs.digest(dc.DAGU) != dc.DAGU_2166_SHA256:
        raise SystemExit("Dagu binary is not the pinned 2.16.6 executable")
    started = datetime.now(timezone.utc).isoformat()
    frozen = {"inputs": {p.name: rs.digest(p) for p in sorted(dc.HERE.glob("*.py"))}, "dagu_binary_sha256": rs.digest(dc.DAGU)}
    rs.exclusive(work / "freeze.json", frozen)
    oracle_a = upstream(work)
    oracle_b = real_restart(work, args.base_commit)
    result = {"started_at_utc": started, "completed_at_utc": datetime.now(timezone.utc).isoformat(),
              "platform": platform.system() + " " + platform.release(), "python_version": platform.python_version(),
              "frozen": frozen, "upstream_retry_tests": oracle_a, "real_workflow_restart_analog": oracle_b,
              "both_oracles_passed": oracle_a["exit_code"] == 0 and oracle_a["fail_records"] == 0 and oracle_a["source_unchanged"] and oracle_b["status"] == "passed"}
    rs.exclusive(work / "result.json", result)
    print(json.dumps({"both_oracles_passed": result["both_oracles_passed"],
                      "upstream": {k: oracle_a[k] for k in ("exit_code", "top_level_pass", "subtest_pass", "fail_records", "final_line", "source_unchanged", "seconds")},
                      "real": {"status": oracle_b["status"], "checks": oracle_b["checks"]}}, indent=2))


if __name__ == "__main__":
    main()
