#!/usr/bin/env python3
"""A2 differential: the same corpus through both binaries' `rtk hook claude`, then each
rewritten form executed in ONE shared deterministic fixture with that binary first on PATH.
Compares rewrite strings, exit codes, stdout and stderr between 0.49.0 and 0.50.0, and each
version's exit code against the native command. All rtk state goes to scratch data dirs.
Credentials: gh runs with an EMPTY scratch GH_CONFIG_DIR and token variables removed from the
child environment (values are never read), so gh fails locally before any authenticated call.
"""
import hashlib, json, os, re, shutil, subprocess, sys, tempfile, time

IMPL = os.path.dirname(os.path.abspath(__file__))
S = os.path.expanduser("~/.local/share/codex-ecosystem")
PFX = {"049": f"{S}/tools/rtk-0.49.0", "050": f"{S}/tools/rtk-0.50.0"}
OUT = f"{IMPL}/out/a2"; os.makedirs(f"{OUT}/raw", exist_ok=True)
FX = tempfile.mkdtemp(prefix="a2fx.", dir=f"{IMPL}/tmp")
DATA = {v: tempfile.mkdtemp(prefix=f"a2data-{v}.", dir=f"{IMPL}/tmp") for v in PFX}
SID = "sota-refresh-rtk-a2"

BASE = {k: v for k, v in os.environ.items()
        if k not in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN",
                     "CLAUDE_CONFIG_DIR", "XDG_DATA_HOME", "RTK_DB_PATH")}
BASE.update(RTK_TELEMETRY_DISABLED="1", GH_CONFIG_DIR=f"{FX}/ghcfg", GH_PROMPT_DISABLED="1",
            GH_NO_UPDATE_NOTIFIER="1", TMPDIR=f"{IMPL}/tmp")
ORIG_PATH = os.environ["PATH"]

def sh(cmd, cwd, env, timeout=60):
    t = time.perf_counter()
    try:
        p = subprocess.run(["bash", "-c", cmd], cwd=cwd, env=env, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr, time.perf_counter() - t
    except subprocess.TimeoutExpired as e:
        return "timeout", e.stdout or b"", e.stderr or b"", time.perf_counter() - t

def build_fixture():
    g = dict(BASE, GIT_AUTHOR_NAME="acc", GIT_AUTHOR_EMAIL="a@b.invalid", GIT_COMMITTER_NAME="acc",
             GIT_COMMITTER_EMAIL="a@b.invalid", PATH=ORIG_PATH)
    def git(args, cwd, day):
        d = f"2026-01-{day:02d}T12:00:00+0000"
        subprocess.run(["git"] + args, cwd=cwd, env=dict(g, GIT_AUTHOR_DATE=d, GIT_COMMITTER_DATE=d),
                       check=True, capture_output=True)
    r = f"{FX}/repo"; os.makedirs(r)
    git(["init", "-q", "-b", "main"], r, 1)
    for i in range(1, 13):
        if i == 7:
            git(["checkout", "-q", "-b", "side"], r, 1)
            open(f"{r}/s.txt", "w").write("side\n"); git(["add", "s.txt"], r, 1); git(["commit", "-qm", "s1"], r, 7)
            git(["checkout", "-q", "main"], r, 1)
        open(f"{r}/n.txt", "w").write(f"{i}\n"); git(["add", "n.txt"], r, i); git(["commit", "-qm", f"c{i}"], r, i)
    git(["merge", "-q", "--no-ff", "-m", "Merge branch 'side'", "side"], r, 13)
    open(f"{r}/big.txt", "w").write("".join(f"row {k}\n" for k in range(1, 4001)))
    git(["add", "big.txt"], r, 14); git(["commit", "-qm", "big"], r, 14)
    open(f"{r}/n.txt", "a").write("changed-line\n")
    open(f"{r}/untracked-file.txt", "w").write("new\n")
    open(f"{r}/staged-file.txt", "w").write("staged\n"); git(["add", "staged-file.txt"], r, 15)
    os.makedirs(f"{FX}/g/sub"); os.makedirs(f"{FX}/l/three"); os.makedirs(f"{FX}/nonrepo"); os.makedirs(f"{FX}/ghcfg"); os.makedirs(f"{FX}/bin")
    open(f"{FX}/g/a.txt", "w").write("alpha\nneedle one\n"); open(f"{FX}/g/sub/b.txt", "w").write("needle two\n")
    open(f"{FX}/g/c.md", "w").write("x\ny needle three\n")
    open(f"{FX}/g/m.txt", "w").write("".join(f"needle {k}\n" for k in range(1, 121)))
    open(f"{FX}/l/one.txt", "w").close(); open(f"{FX}/l/two.log", "w").close()
    open(f"{FX}/f.txt", "w").write("".join(f"line {k}\n" for k in range(1, 41)))
    open(f"{FX}/big2.txt", "w").write("".join(f"text line {k} lorem ipsum dolor sit amet\n" for k in range(1, 3001)))
    open(f"{FX}/a.txt", "w").write("".join(f"{k}\n" for k in range(1, 11)))
    open(f"{FX}/b.txt", "w").write("".join(("five-changed\n" if k == 5 else f"{k}\n") for k in range(1, 12)))
    json.dump({"a": 1, "b": [1, 2, 3], "c": {"d": "e"}}, open(f"{FX}/x.json", "w"))
    subprocess.run(["tar", "-cf", "x.tar", "l"], cwd=FX, check=True)
    for d in (f"{FX}/l", f"{FX}/l/three"): os.utime(d, (1767268800, 1767268800))
    for f in ("one.txt", "two.log"): os.utime(f"{FX}/l/{f}", (1767268800, 1767268800))
    open(f"{FX}/Makefile", "w").write("hello:\n\t@echo hello-from-make\nfail:\n\t@echo make-fail-marker >&2; exit 2\n")
    open(f"{FX}/bin/pytest", "w").write('#!/bin/sh\necho "ERROR: file or directory not found: nosuch_test.py" >&2\nexit 4\n')
    open(f"{FX}/bin/ruff", "w").write('#!/bin/sh\necho "ruff failed" >&2\necho "  Cause: Failed to parse /nonexistent/pyproject.toml" >&2\nexit 2\n')
    os.chmod(f"{FX}/bin/pytest", 0o755); os.chmod(f"{FX}/bin/ruff", 0o755)

CORPUS = [  # (id, cwd, command, execute)
 ("git-status","repo","git status",1), ("git-status-short","repo","git status --short",1),
 ("git-log-3","repo","git log -3",1), ("git-log-oneline-5","repo","git log --oneline -5",1),
 ("git-log-plain","repo","git log",1), ("git-log-oneline","repo","git log --oneline",1),
 ("git-log-p-2","repo","git log -p -2",1), ("git-log-p","repo","git log -p",1),
 ("git-log-stat-3","repo","git log --stat -3",1), ("git-diff","repo","git diff",1),
 ("git-diff-stat","repo","git diff --stat",1), ("git-diff-cached","repo","git diff --cached",1),
 ("git-show-c12","repo","git show HEAD~2",1), ("git-show-stat","repo","git show --stat HEAD",1),
 ("git-show-blob","repo","git show HEAD:big.txt",1), ("git-show-blob-tail","repo","git show HEAD:big.txt | tail -n 5",1),
 ("git-show-blob-head","repo","git show HEAD:big.txt | head -n 5",1), ("git-branch","repo","git branch",1),
 ("git-stash-list","repo","git stash list",1), ("git-compound","repo","git status && git log -1",1),
 ("git-C","fx","git -C repo status",1),
 ("git-log-badref","repo","git log -1 nsr-no-such-ref",1), ("git-diff-badref","repo","git diff nsr-no-such-ref",1),
 ("git-status-nonrepo","nonrepo","git status",1),
 ("grep-rn","fx","grep -rn needle g",1), ("grep-n-file","fx","grep -n needle g/a.txt",1),
 ("grep-many","fx","grep -n needle g/m.txt",1), ("grep-c","fx","grep -c needle g/m.txt",1),
 ("grep-rl","fx","grep -rl needle g",1), ("grep-missing","fx","grep -n needle missing.txt",1),
 ("grep-nomatch","fx","grep -rn zzznomatch g",1),
 ("rg-n","fx","rg -n needle g",1), ("rg-many","fx","rg -n needle g/m.txt",1),
 ("rg-missing","fx","rg -n needle missing.txt",1), ("rg-nomatch","fx","rg -n zzznomatch g",1),
 ("find-name","fx","find g -name '*.txt'",1), ("find-type-d","fx","find g -type d",1),
 ("find-missing","fx","find missing -name x",1),
 ("ls","fx","ls g",1), ("ls-la","fx","ls -la l",1), ("ls-missing","fx","ls missing",1),
 ("cat","fx","cat f.txt",1), ("cat-big","fx","cat big2.txt",1), ("cat-missing","fx","cat missing.txt",1),
 ("cat-pipe-head","fx","cat f.txt | head -3",1), ("head-3","fx","head -3 f.txt",1), ("head-bare","fx","head f.txt",1),
 ("head-n-3","fx","head -n 3 f.txt",1), ("tail-5","fx","tail -5 f.txt",1), ("tail-n-3","fx","tail -n 3 f.txt",1),
 ("wc-l","fx","wc -l f.txt",1), ("wc-multi","fx","wc -l f.txt g/a.txt",1), ("wc","fx","wc f.txt",1),
 ("wc-missing","fx","wc -l missing.txt",1),
 ("diff-files","fx","diff a.txt b.txt",1), ("diff-u","fx","diff -u a.txt b.txt",1), ("diff-missing","fx","diff a.txt missing.txt",1),
 ("du","fx","du -s l",1), ("make-ok","fx","make -s hello",1), ("make-fail","fx","make -s fail",1),
 ("pytest-fake","fx","pytest -q nosuch_test.py",1), ("python-m-pytest","fx","python3 -m pytest -q nosuch_test.py",1),
 ("ruff-fake","fx","ruff check nosuch.py",1), ("uv-run-pytest","fx","uv run pytest -q",0),
 ("curl-file","fx","curl -s file://{FX}/x.json",1), ("curl-missing","fx","curl -sS file://{FX}/missing.json",1),
 ("jq","fx","jq .b x.json",1), ("tar-tf","fx","tar -tf x.tar",1),
 ("gh-pr-view","repo","gh pr view 1",1), ("gh-run-view","repo","gh run view 1",1), ("gh-api","repo","gh api repos/rtk-ai/rtk",1),
 ("systemctl-status","fx","systemctl status nonexistent-unit-sota-probe.service",1),
 ("echo-subst","fx","echo $(date +%Y)",1), ("uname","fx","uname -s",1), ("htop","fx","htop",0),
 ("redirect","repo","git status > {FX}/redir.out",0),
]

def norm(b, v):
    s = b.decode("utf-8", "replace").replace(DATA[v], "<DATA>").replace(FX, "<FX>")
    return re.sub(r"\d{9,}", "<N>", s)

def main():
    build_fixture()
    cwdmap = {"repo": f"{FX}/repo", "fx": FX, "nonrepo": f"{FX}/nonrepo"}
    envs = {}
    for v in PFX:
        envs[v] = dict(BASE, PATH=f"{PFX[v]}:{FX}/bin:{ORIG_PATH}", XDG_DATA_HOME=DATA[v], RTK_DB_PATH=f"{DATA[v]}/history.db")
    native_env = dict(BASE, PATH=f"{FX}/bin:{ORIG_PATH}", XDG_DATA_HOME=f"{FX}/nativedata")
    rows = []
    for n, (cid, cwdk, cmd, execute) in enumerate(CORPUS):
        cmd = cmd.replace("{FX}", FX); cwd = cwdmap[cwdk]
        row = {"id": cid, "cwd": cwdk, "cmd": cmd.replace(FX, "<FX>"), "executed": bool(execute)}
        if execute:
            rc, o, e, dt = sh(cmd, cwd, native_env)
            row["native"] = {"rc": rc, "out_len": len(o), "err_len": len(e)}
            open(f"{OUT}/raw/{cid}.native.out", "wb").write(o); open(f"{OUT}/raw/{cid}.native.err", "wb").write(e)
        for v in PFX:
            payload = json.dumps({"session_id": SID, "tool_use_id": f"{SID}-{n}-{v}", "cwd": cwd,
                                  "permission_mode": "bypassPermissions", "hook_event_name": "PreToolUse",
                                  "tool_name": "Bash", "tool_input": {"command": cmd, "description": "a2", "timeout": 30000}})
            hp = subprocess.run([f"{PFX[v]}/rtk", "hook", "claude"], input=payload.encode(), cwd=cwd, env=envs[v], capture_output=True)
            rew, pd = None, None
            if hp.stdout.strip():
                try:
                    ho = json.loads(hp.stdout)["hookSpecificOutput"]
                    rew = ho["updatedInput"]["command"]; pd = ho.get("permissionDecision")
                except Exception as ex:
                    pd = f"UNPARSABLE:{type(ex).__name__}"
            r = {"hook_rc": hp.returncode, "hook_err": hp.stderr.decode()[:200], "rewrite": rew.replace(FX, "<FX>") if rew else None, "pd": pd}
            if execute:
                rc, o, e, dt = sh(rew or cmd, cwd, envs[v])
                open(f"{OUT}/raw/{cid}.{v}.out", "wb").write(o); open(f"{OUT}/raw/{cid}.{v}.err", "wb").write(e)
                r.update(rc=rc, out_len=len(o), err_len=len(e), out_n=norm(o, v), err_n=norm(e, v), secs=round(dt, 3))
            row[v] = r
        a, b = row["049"], row["050"]
        row["same_rewrite"] = a["rewrite"] == b["rewrite"]
        if execute:
            row["same_rc"] = a["rc"] == b["rc"]; row["same_out"] = a["out_n"] == b["out_n"]; row["same_err"] = a["err_n"] == b["err_n"]
            row["rc_vs_native"] = {v: row[v]["rc"] == row["native"]["rc"] for v in PFX}
        rows.append(row)
    # compact report (no raw output bodies)
    rep = []
    for r in rows:
        a, b = r["049"], r["050"]
        line = {"id": r["id"], "cmd": r["cmd"], "rw049": a["rewrite"], "rw050": b["rewrite"], "pd": [a["pd"], b["pd"]],
                "hook_rc": [a["hook_rc"], b["hook_rc"]], "same_rewrite": r["same_rewrite"]}
        if r["executed"]:
            line.update(rc=[r["native"]["rc"], a["rc"], b["rc"]], out_len=[r["native"]["out_len"], a["out_len"], b["out_len"]],
                        err_len=[r["native"]["err_len"], a["err_len"], b["err_len"]], same_rc=r["same_rc"],
                        same_out=r["same_out"], same_err=r["same_err"])
        rep.append(line)
    json.dump(rep, open(f"{OUT}/a2-report.json", "w"), indent=1)
    with open(f"{OUT}/a2-table.txt", "w") as f:
        f.write("id | same_rewrite | rc native/049/050 | same_out | same_err | out_len n/049/050 | err_len n/049/050 | hook_rc | pd\n")
        for l in rep:
            f.write(f"{l['id']} | {l['same_rewrite']} | {l.get('rc')} | {l.get('same_out')} | {l.get('same_err')} | {l.get('out_len')} | {l.get('err_len')} | {l['hook_rc']} | {l['pd']}\n")
            if not l["same_rewrite"]:
                f.write(f"    rewrite 049: {l['rw049']}\n    rewrite 050: {l['rw050']}\n")
    # the scratch tracking DBs are kept for the rollback-hazard check; the fixture is kept for review
    json.dump({"FX": FX, "DATA": DATA}, open(f"{OUT}/a2-paths.json", "w"))
    nd = [l["id"] for l in rep if not l["same_rewrite"] or (l.get("same_rc") is False) or (l.get("same_out") is False) or (l.get("same_err") is False)]
    print(f"corpus={len(rep)} executed={sum(1 for l in rep if 'rc' in l)} differing={len(nd)}: {', '.join(nd)}")
    print("hook rc nonzero:", [l["id"] for l in rep if l["hook_rc"] != [0, 0]])
    print("rc != native (049):", [l["id"] for l in rep if "rc" in l and l["rc"][1] != l["rc"][0]])
    print("rc != native (050):", [l["id"] for l in rep if "rc" in l and l["rc"][2] != l["rc"][0]])
    print("permissionDecision set:", [l["id"] for l in rep if any(l["pd"])])

if __name__ == "__main__":
    main()
