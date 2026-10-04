"""Discriminating controls for the 2026-09-26 receipt repairs, run from the recorded receipt commands.

Each control takes a command verbatim from a receipt in the worktree, applies exact, counted text substitutions
(the fault), runs it the way scripts/host_receipts.py record does (/bin/sh -c, cwd = worktree root) and records the
exit code and the sanitized output. Output: controls.txt (sanitized) next to this script.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "wt-g3b"
sys.path.insert(0, str(ROOT / "scripts"))
import host_receipts  # noqa: E402

HOSTDIR = ROOT / "evidence/hosts/nativestack-5975wx-20260925"
ART = ROOT / "evidence/artifacts/eval-native-reports-20260926"


def cmd(receipt_id, index):
    return json.loads((HOSTDIR / f"{receipt_id}.json").read_text())["commands"][index]["cmd"]


def fault(text, subs):
    for old, new in subs:
        if text.count(old) != 1:
            raise SystemExit(f"substitution anchor found {text.count(old)} times: {old[:80]!r}")
        text = text.replace(old, new)
    return text


def clean(output):
    text = host_receipts.sanitize(output)
    text = text.replace(str(ROOT), "<worktree>").replace(str(HERE.parent), "<scratch>")
    text = re.sub(r"/tmp/tmp\.[A-Za-z0-9]+", "<tmp>", text)
    return text


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


H = "nativestack-5975wx-20260925--"
RESTRICTED_PATH = "PATH=/usr/bin:/bin; export PATH\n"
CONTROLS = []

# 1-2: socraticode resolution with socraticode absent from PATH (the #277 '|| echo' fail-open and its fix).
CONTROLS.append(("socraticode install 2026-09-25, command 1, PATH=/usr/bin:/bin (socraticode absent)",
                 "exit 0: the '|| echo' fail-open the #277 review reported",
                 RESTRICTED_PATH + cmd(H + "socraticode--install--20260925", 0), lambda rc, out: rc == 0))
CONTROLS.append(("socraticode install 2026-09-26-2, command 1, same PATH",
                 "exit 1 with SOCRATICODE_RESOLVE_FAIL",
                 RESTRICTED_PATH + cmd(H + "socraticode--install--20260926-2", 0),
                 lambda rc, out: rc == 1 and out.startswith("SOCRATICODE_RESOLVE_FAIL")))
# 3-4: LEAN primary run pointed at a missing data folder (the #281 fail-open and its fix).
LEAN_PRIMARY = ('--data-folder "$L/Lean/Data/"', '--data-folder "$W/nsr-missing-data/"')
CONTROLS.append(("lean use 2026-09-25, command 2, primary run --data-folder pointed at a missing directory",
                 "exit 0: the fail-open the #281 review reported",
                 fault(cmd(H + "lean--use--20260925", 1), [LEAN_PRIMARY]), lambda rc, out: rc == 0))
CONTROLS.append(("lean use 2026-09-26, command 2, same fault",
                 "exit 1 with LEAN_BACKTEST_FAIL",
                 fault(cmd(H + "lean--use--20260926", 1), [LEAN_PRIMARY]),
                 lambda rc, out: rc == 1 and out.startswith("LEAN_BACKTEST_FAIL")))
# 5: MCPorter bridge with env -i and --config removed from the config listing (the #277 isolation defect).
CONTROLS.append(("mcporter use 2026-09-26-2, command 3, without env -i and without --config on config list",
                 "exit 1 with MCPORTER_BRIDGE_FAIL: the inherited canary MCPORTER_CONFIG is selected",
                 fault(cmd(H + "mcporter--use--20260926-2", 2), [
                     ('run() { env -i PATH="$PATH" HOME="$d/fakehome" LANG=C.UTF-8 "$@"; }',
                      'run() { env HOME="$d/fakehome" "$@"; }'),
                     ('run timeout 20 "$M" --config "$d/mcporter.json" config list',
                      'run timeout 20 "$M" config list')]),
                 lambda rc, out: rc == 1 and out.startswith("MCPORTER_BRIDGE_FAIL") and "canary.json" in out))
# 6: FastAPI EXIT-trap path: exit early while the server runs; the trap must stop only its process group.
PGID_LINE = ('[ "$PGID" = "$SPID" ] || { echo "FASTAPI_SERVE_FAIL: server pid $SPID is not its own process group '
             'leader (pgid $PGID)"; exit 1; }')
CONTROLS.append(("fastapi use 2026-09-26, command 2, early exit 3 injected right after the server starts",
                 "exit 3, and afterwards no process is left in the server's process group",
                 fault(cmd(H + "fastapi--use--20260926", 1),
                       [(PGID_LINE, PGID_LINE + '\nsleep 2; echo "simulated early exit with server group $SPID '
                                                'running"; exit 3')]),
                 None))
# 7: the cause of the failed first fastapi dry run: dash's builtin kill rejects '--'.
CONTROLS.append(("/bin/sh builtin kill versus /bin/kill on a throwaway process group (setsid sleep)",
                 "the builtin 'kill -TERM -- -PGID' fails and leaves the group running; /bin/kill stops it",
                 'setsid sleep 60 < /dev/null > /dev/null 2>&1 &\nP=$!\nsleep 0.3\n'
                 'G=$(ps -o pgid= -p "$P" | tr -d " ")\n[ "$G" = "$P" ] || { echo "not a group leader"; exit 9; }\n'
                 'E=$(mktemp) || exit 9\nkill -TERM -- "-$G" 2> "$E"; b=$?; sleep 0.3\n'
                 'if pgrep -g "$G" > /dev/null; then after_b=running; else after_b=gone; fi\n'
                 '/bin/kill -TERM -- "-$G"; k=$?; sleep 0.3\n'
                 'if pgrep -g "$G" > /dev/null; then after_k=running; else after_k=gone; fi\n'
                 'echo "builtin kill exit $b ($(cat "$E")) -> group $after_b | /bin/kill exit $k -> group $after_k"\n'
                 'rm -f "$E"\n[ "$b" -ne 0 ] && [ "$after_b" = running ] && [ "$k" -eq 0 ] && [ "$after_k" = gone ]',
                 lambda rc, out: rc == 0))
# 8-9: re-running the eval commands never overwrites the tracked reports.
CONTROLS.append(("promptfoo use 2026-09-26-2, command 2, re-run unchanged with results-2.json present",
                 "exit 0, results-2.json left unchanged (sha256 before == after), a fresh report with its own sha256",
                 cmd(H + "promptfoo--use--20260926-2", 1), None))
CONTROLS.append(("inspect-ai use 2026-09-26-2, command 2, re-run unchanged with eval-log-2.json present",
                 "exit 0, eval-log-2.json left unchanged (sha256 before == after), a fresh log with its own sha256",
                 cmd(H + "inspect-ai--use--20260926-2", 1), None))


def main():
    backups = {}
    for rel in ("promptfoo/results-2.json", "inspect-ai/eval-log-2.json"):
        backup = HERE / "artifact-backup" / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ART / rel, backup)
        backups[rel] = sha(ART / rel)
    lines, problems = [], 0
    for number, (label, expected, text, judge) in enumerate(CONTROLS, 1):
        if number in (8, 9):
            gen = subprocess.run(["systemctl", "--user", "is-active", "nativestack-generation"],
                                 capture_output=True, text=True).stdout.strip()
            if gen != "active":
                lines.append(f"{number:02d} {label}: not run (nativestack-generation is {gen})")
                problems += 1
                continue
        started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        rc, output, duration = host_receipts.run_command(text, cwd=ROOT, timeout=900)
        out = clean(output).strip()
        if number == 6:
            match = re.search(r"simulated early exit with server group (\d+) running", output)
            left = (subprocess.run(["pgrep", "-g", match.group(1)], capture_output=True).returncode == 0) if match else None
            out = f"[harness, after exit] processes left in group {match.group(1) if match else '?'}: {'yes' if left else 'none'}\n" + out
            ok = rc == 3 and match is not None and left is False
        elif number in (8, 9):
            rel = "promptfoo/results-2.json" if number == 8 else "inspect-ai/eval-log-2.json"
            after = sha(ART / rel)
            out = f"[harness] tracked {rel} sha256 before {backups[rel]} after {after}: {'unchanged' if after == backups[rel] else 'CHANGED'}\n" + out
            ok = rc == 0 and after == backups[rel] and "exists, left unchanged" in output
        else:
            ok = judge(rc, out)
        problems += 0 if ok else 1
        lines.append(f"{number:02d} {label}\n   expected: {expected}\n   observed: exit {rc} in {duration:.1f}s at {started}"
                     f" -> {'as expected' if ok else 'NOT AS EXPECTED'}\n   output: " + out[:1200].replace("\n", "\n           "))
    lines.append(f"{len(CONTROLS)} controls, {problems} not as expected")
    (HERE / "controls.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
