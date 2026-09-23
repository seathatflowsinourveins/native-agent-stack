#!/usr/bin/env python3
import subprocess, time, os, signal, json, hashlib, sys

REPO = "$HOME/.cache/gap-wave2-20260923/workers/fix5/wt-repo"
SIB = REPO + ".sibling-dirty"
DELAYS_MS = [1, 2, 3, 5, 8, 12, 20, 33, 55, 90]

def recreate_target():
    subprocess.run(["wt", "-C", REPO, "switch", "--create", "crash-target", "--no-cd", "--format=json", "-y"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def target_exists():
    return os.path.isdir(REPO + ".crash-target")

def worktrees_listed():
    out = subprocess.run(["git", "-C", REPO, "worktree", "list", "--porcelain"], capture_output=True, text=True).stdout
    return [l.split()[1] for l in out.splitlines() if l.startswith("worktree ")]

def sibling_status():
    return subprocess.run(["git", "-C", SIB, "status", "--porcelain"], capture_output=True, text=True).stdout

results = []
for ms in DELAYS_MS:
    if not target_exists():
        recreate_target()
    t0 = time.time()
    p = subprocess.Popen(["wt", "-C", REPO, "remove", "crash-target", "-y", "--force", "--foreground"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    time.sleep(ms / 1000.0)
    try:
        os.killpg(p.pid, signal.SIGKILL)
        killed = True
    except ProcessLookupError:
        killed = False
    p.wait(timeout=5)
    elapsed = time.time() - t0
    state = "target_present" if target_exists() else "target_removed"
    wtl = worktrees_listed()
    sib_after = sibling_status()
    results.append({
        "delay_ms_requested": ms,
        "elapsed_s": round(elapsed, 4),
        "killed_process_group": killed,
        "target_state": state,
        "worktree_list_count": len(wtl),
        "worktree_list": wtl,
        "sibling_status_porcelain": sib_after,
        "sibling_intact": sib_after.strip() == "?? README.md",
    })

sib_final = sibling_status()
out = {
    "trial_count": len(results),
    "delays_ms": DELAYS_MS,
    "trials": results,
    "sibling_final_status": sib_final,
    "sibling_survived_all_trials": all(r["sibling_intact"] for r in results),
}
print(json.dumps(out, indent=2))
