#!/usr/bin/env bash
# v3.1 = v3 (sha256 df7a7fb3...) with ONE change: chk_fail2 matches error phrases case-insensitively.
# Discriminating acceptance for an rtk candidate prefix on the Claude Code PreToolUse Bash
# hook path (`rtk hook claude`). v3 = the refuter's v2 (sha256 186dd891...) unchanged in
# every v2 assertion, plus additions marked "v3:":
#  - hook robustness: empty / malformed / command-less payloads must exit 0 and stay silent;
#  - failure signals for more frequent commands (ls, cat, find, grep -r, rg, ruff, git status,
#    git diff): the rewritten command's exit code must equal the NATIVE command's exit code and
#    the error text must survive (on stderr; stdout-only is a NOTE, absent is a FAIL);
#  - success-path content for git log (-3, --oneline -5), git show, git diff --cached, rg,
#    find and wc (v2 already covers git status, git diff, grep -rn and ls);
#  - a second synthetic permission config: legacy `:*` allow rule and a leading-wildcard
#    deny rule shaped like the live `* --flag*` deny rule;
#  - non-gating NOTEs: plain `git log` default cap, allow-prefix semantics, hook stderr;
#  - a distinctive session_id so leakage into a production tracking DB can be queried;
#  - a COUNTS summary line.
# Usage: rtk-hook-acceptance-v3.sh <prefix-dir-containing-rtk> <expected-version>
# Run from a plain shell (bash <file>), never as individual commands through the live hook.
set -u
P=${1:?prefix dir}; WANT=${2:?expected version, e.g. 0.50.0}
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export XDG_DATA_HOME="$T/data" RTK_DB_PATH="$T/data/history.db" RTK_TELEMETRY_DISABLED=1
export PATH="$P:$PATH"
cd "$T" || exit 2
fail=0; npass=0; nfail=0; nnote=0; ncalls=0; nherr=0; herr1=""
ok()   { printf 'PASS %s\n' "$1"; npass=$((npass+1)); }
bad()  { printf 'FAIL %s\n' "$1"; fail=1; nfail=$((nfail+1)); }
note() { printf 'NOTE %s\n' "$1"; nnote=$((nnote+1)); }
SID=sota-refresh-rtk-acc   # v3: distinctive marker for production-DB leakage queries

hook_raw() { # one Claude PreToolUse payload -> $T/h.out (stdout), $T/h.err; returns hook exit code
  python3 -c 'import json,os,sys;print(json.dumps({"session_id":sys.argv[2],"tool_use_id":sys.argv[2]+"-1","cwd":os.getcwd(),"permission_mode":"bypassPermissions","hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":sys.argv[1],"description":"acc","timeout":30000}}))' "$1" "$SID" \
    | "$P/rtk" hook claude > "$T/h.out" 2> "$T/h.err"
  local rc=$?
  ncalls=$((ncalls+1))
  if [ -s "$T/h.err" ]; then nherr=$((nherr+1)); [ -z "$herr1" ] && herr1="$1 :: $(head -c 160 "$T/h.err" | tr '\n' ' ')"; fi
  return $rc
}
hook() { # sets R to the rewritten command ("" when silent); FAILs on any protocol violation
  local cmd=$1 want=${2:-none} rc
  R=""
  hook_raw "$cmd"; rc=$?
  if [ "$rc" != 0 ]; then bad "hook exit $rc for: $cmd"; return; fi
  if ! python3 - "$want" "$T/h.out" > "$T/h.cmd" 2> "$T/h.perr" <<'PY'
import json,sys
want=sys.argv[1]; s=open(sys.argv[2]).read().strip()
if not s: sys.exit(0)
o=json.loads(s)["hookSpecificOutput"]
assert o["hookEventName"]=="PreToolUse", o
assert o["permissionDecisionReason"]=="RTK auto-rewrite", o
assert o["updatedInput"]["description"]=="acc" and o["updatedInput"]["timeout"]==30000, o
pd=o.get("permissionDecision")
assert (pd is None) if want=="none" else (pd==want), ("permissionDecision", pd, "want", want)
print(o["updatedInput"]["command"])
PY
  then bad "hook protocol for: $cmd :: $(tail -n 1 "$T/h.perr")"; return; fi
  R=$(cat "$T/h.cmd")
}
defer() { # the hook must exit 0 and write nothing at all to stdout
  local rc; hook_raw "$1"; rc=$?
  if [ "$rc" = 0 ] && [ ! -s "$T/h.out" ]; then ok "silent: $2"; else bad "not silent: $2 (rc=$rc stdout=$(head -c 160 "$T/h.out"))"; fi
}
has() { case "$2" in *"$3"*) ok "$1";; *) bad "$1 (missing [$3])";; esac; }

# 0. identity and live-settings precondition (rewrites below must carry no permissionDecision)
[ "$("$P/rtk" --version)" = "rtk $WANT" ] && ok version || bad "version: $("$P/rtk" --version)"
nallow=$(python3 - <<'PY'
import json,os
d=os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
n=0
for f in ("settings.json","settings.local.json"):
    try: p=json.load(open(os.path.join(d,f))).get("permissions",{})
    except Exception: continue
    n+=sum(1 for r in p.get("allow",[]) if str(r).startswith("Bash("))
print(n)
PY
)
[ "$nallow" = 0 ] && ok "precondition: live settings have 0 Bash allow rules" || bad "precondition: $nallow live Bash allow rules"

# v3: 0b. hook robustness -- a broken payload must never block or rewrite (exit 0, empty stdout)
hook_stdin() { printf '%s' "$1" | "$P/rtk" hook claude > "$T/h.out" 2> "$T/h.err"; }
for label in empty malformed no-command; do
  case $label in
    empty) inp='';;
    malformed) inp='{"tool_input": {"command": "git status"';;
    no-command) inp='{"session_id":"'$SID'","tool_use_id":"'$SID'-0","hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"description":"acc"}}';;
  esac
  hook_stdin "$inp"; rc=$?
  if [ "$rc" = 0 ] && [ ! -s "$T/h.out" ]; then ok "robust: $label payload -> exit 0, silent"; else bad "robust: $label payload (rc=$rc stdout=$(head -c 160 "$T/h.out"))"; fi
done

# 1. read fidelity through the hook
seq 1 40 | sed 's/^/line /' > "$T/f.txt"
for n in 1 5; do
  hook "head -$n $T/f.txt"
  [ "$R" = "rtk read $T/f.txt --head-lines $n" ] && ok "head-$n rewrite" || bad "head-$n rewrite: [$R]"
  [ -n "$R" ] && [ "$(bash -c "$R" | sha256sum)" = "$(head -"$n" "$T/f.txt" | sha256sum)" ] && ok "head-$n bytes==native" || bad "head-$n bytes differ from native head"
done
hook "cat $T/f.txt"
[ -n "$R" ] && [ "$(bash -c "$R" | sha256sum)" = "$(cat "$T/f.txt" | sha256sum)" ] && ok "cat bytes==native [$R]" || bad "cat bytes differ [$R]"
hook "tail -3 $T/f.txt"
[ -n "$R" ] && [ "$(bash -c "$R" | sha256sum)" = "$(tail -3 "$T/f.txt" | sha256sum)" ] && ok "tail-3 bytes==native [$R]" || bad "tail-3 bytes differ [$R]"

# 2. failure signals: exit code AND error text must survive
chk_fail() { # label, command, expected rc, expected stderr substring
  local e rc
  hook "$2"; [ -n "$R" ] || { bad "$1: hook did not rewrite"; return; }
  e=$(bash -c "$R" 2>&1 >/dev/null); rc=$?
  [ "$rc" = "$3" ] && ok "$1 rc=$rc" || bad "$1 rc=$rc want $3"
  case "$e" in *"$4"*) ok "$1 stderr kept";; *) bad "$1 stderr lost: [$e]";; esac
}
chk_fail wc   "wc -l $T/missing"          1 "No such file or directory"
chk_fail grep "grep -n needle $T/missing" 2 "No such file or directory"
mkdir -p "$T/bin"; printf '#!/bin/sh\necho "ERROR: file or directory not found: nosuch_test.py" >&2\nexit 4\n' > "$T/bin/pytest"; chmod +x "$T/bin/pytest"
PATH="$P:$T/bin:$PATH" chk_fail pytest "pytest -q nosuch_test.py" 4 "file or directory not found: nosuch_test.py"
printf 'a\n' > "$T/a.txt"
hook "diff $T/a.txt $T/missing.txt"
if [ -n "$R" ]; then e=$(bash -c "$R" 2>&1 >/dev/null); rc=$?; note "diff unreadable-file rc=$rc (native diff: 2; upstream fix bdee7f2 is develop-only) stderr=[$e]"; fi

# v3: 2b. failure signals compared with the NATIVE command (rc equality + error text)
chk_fail2() { # label, dir, command, key
  local label=$1 dir=$2 cmd=$3 key=$4 nrc rc
  pushd "$dir" >/dev/null || { bad "$label: cd $dir"; return; }
  bash -c "$cmd" >/dev/null 2>&1; nrc=$?
  hook "$cmd"
  if [ -z "$R" ]; then note "$label: not rewritten (native path, rc=$nrc)"; popd >/dev/null; return; fi
  bash -c "$R" > "$T/c.out" 2> "$T/c.err"; rc=$?
  [ "$rc" = "$nrc" ] && ok "$label rc=$rc (native $nrc)" || bad "$label rc=$rc want native $nrc [$R]"
  # v3.1: phrase match is case-insensitive, like upstream's own contract for this class
  # (git_cmd.rs test: stderr.to_lowercase().contains("not a git repository")).
  if grep -qiF -- "$key" "$T/c.err"; then ok "$label error text on stderr"
  elif grep -qiF -- "$key" "$T/c.out"; then note "$label error text only on stdout [$key]"
  else bad "$label error text lost [$key] :: stderr=[$(head -c 200 "$T/c.err" | tr '\n' ' ')] stdout=[$(head -c 120 "$T/c.out" | tr '\n' ' ')]"; fi
  popd >/dev/null
}
mkdir -p "$T/nonrepo"
chk_fail2 "ls missing"          "$T" "ls $T/missing"               "No such file or directory"
chk_fail2 "cat missing"         "$T" "cat $T/missing"              "No such file or directory"
chk_fail2 "find missing"        "$T" "find $T/missing -name x"     "No such file or directory"
chk_fail2 "grep -rn missing-dir" "$T" "grep -rn needle $T/missing-dir" "No such file or directory"
if command -v rg >/dev/null 2>&1; then chk_fail2 "rg missing" "$T" "rg -n needle $T/missing" "No such file or directory"; else note "rg not installed"; fi
printf '#!/bin/sh\necho "ruff failed" >&2\necho "  Cause: Failed to parse /nonexistent/pyproject.toml" >&2\nexit 2\n' > "$T/bin/ruff"; chmod +x "$T/bin/ruff"
PATH="$P:$T/bin:$PATH" chk_fail2 "ruff check (stderr-only)" "$T" "ruff check nosuch.py" "Failed to parse"
GIT_CEILING_DIRECTORIES="$T" chk_fail2 "git status outside repo" "$T/nonrepo" "git status" "not a git repository"

git init -q "$T/repo" && cd "$T/repo" && git config user.email a@b.invalid && git config user.name acc
for i in $(seq 1 12); do echo "$i" > n.txt; git add n.txt; git commit -qm "c$i"; done
seq 1 4000 | sed 's/^/row /' > big.txt; git add big.txt; git commit -qm big
chk_fail gitlog "git log -1 nsr-no-such-ref" 128 "fatal: ambiguous argument 'nsr-no-such-ref'"
chk_fail2 "git diff bad ref" "$T/repo" "git diff nsr-no-such-ref" "ambiguous argument 'nsr-no-such-ref'"   # v3

# 3. deferral invariants: exit 0 and empty stdout
defer 'echo $(whoami)' 'command substitution'
defer "git status > $T/out" 'file redirect'
defer "$(printf "cat <<'EOF'\nx\nEOF")" 'heredoc'
defer 'htop' 'no rtk equivalent'
defer "git show HEAD:big.txt | sha256sum" 'non-display pipe consumer'
defer 'uname -s' 'no rtk equivalent (uname)'   # v3

# 4. raw recovery path is byte-identical
[ "$(rtk proxy git status | sha256sum)" = "$(git status | sha256sum)" ] && ok "proxy==raw" || bad "proxy differs"

# 5. git show blob window is announced and recovers byte-exactly
hook "git show HEAD:big.txt"; out=$(bash -c "$R"; echo x); out=${out%x}
last=$(printf '%s' "$out" | tail -n 1)
if [[ "$last" =~ ^\.\.\.\ \(\+[0-9]+\ lines\)\ \[see\ remaining:\ (rtk\ proxy\ git\ show\ \'HEAD:big.txt\'\ \|\ tail\ -n\ \+[0-9]+)\]$ ]]; then
  rec=$( { printf '%s' "$out" | sed '$d'; bash -c "${BASH_REMATCH[1]}"; } | sha256sum)
  [ "$rec" = "$(git show HEAD:big.txt | sha256sum)" ] && ok "blob window recovers exactly" || bad "blob recovery mismatch"
else bad "blob not windowed/announced: [$last]"; fi

# 6. git log default cap is announced on stderr
hook "git log -p"; e=$(bash -c "$R" 2>&1 >/dev/null)
case "$e" in *"[rtk] capped at 10 commits; pass -n <count> for more"*) ok "log cap announced";; *) bad "log cap silent: [$e]";; esac

# v3: 6b. git log success-path content (explicit limits must keep every requested commit)
subjects() { python3 -c 'import re,sys; s=sys.stdin.read(); f=set(re.findall(r"(?<![\w-])(c\d+|big)(?![\w-])", s)); print(len(f))'; }
hook "git log -3"; out=$(bash -c "$R" 2>&1)
for s in big c12 c11; do has "git log -3 keeps subject $s" "$out" "$s"; done
hook "git log --oneline -5"; out=$(bash -c "$R" 2>&1)
for s in big c12 c11 c10 c9; do has "git log --oneline -5 keeps subject $s" "$out" "$s"; done
hook "git log"; out=$(bash -c "$R" 2>&1); nshown=$(printf '%s' "$out" | subjects)
case "$out" in *"capped at"*|*"more commits"*|*"pass -n"*) capmsg=announced;; *) capmsg=none;; esac
note "plain git log (13 commits, no -n): $nshown distinct subjects shown, cap notice=$capmsg [$R]"
hook "git show HEAD~1"; out=$(bash -c "$R" 2>&1)
has "git show HEAD~1 keeps subject c12" "$out" "c12"; has "git show HEAD~1 names n.txt" "$out" "n.txt"; has "git show HEAD~1 keeps +12" "$out" "+12"

# 7. success-path content for frequent rewritten commands
echo changed-line >> n.txt; echo new > untracked-file.txt; echo staged > staged-file.txt; git add staged-file.txt
hook "git status"; out=$(bash -c "$R" 2>&1)
for p in n.txt untracked-file.txt staged-file.txt; do has "git status shows $p" "$out" "$p"; done
hook "git diff"; out=$(bash -c "$R" 2>&1)
has "git diff names n.txt" "$out" "n.txt"; has "git diff keeps added line" "$out" "changed-line"
mkdir -p "$T/g/sub"; printf 'alpha\nneedle one\n' > "$T/g/a.txt"; printf 'needle two\n' > "$T/g/sub/b.txt"; printf 'x\ny needle three\n' > "$T/g/c.md"
hook "grep -rn needle $T/g"; out=$(bash -c "$R" 2>&1)
for m in "needle one" "needle two" "y needle three" a.txt b.txt c.md; do has "grep -rn keeps $m" "$out" "$m"; done
mkdir -p "$T/l/three"; : > "$T/l/one.txt"; : > "$T/l/two.log"
hook "ls $T/l"; out=$(bash -c "$R" 2>&1)
for m in one.txt two.log three; do has "ls keeps $m" "$out" "$m"; done
# v3: 7b. more success-path content (added after v2's inputs so v2's checks see identical fixtures)
echo cached-marker-line > cached-file.txt; git add cached-file.txt
hook "git diff --cached"; out=$(bash -c "$R" 2>&1)
has "git diff --cached names cached-file.txt" "$out" "cached-file.txt"; has "git diff --cached keeps added line" "$out" "cached-marker-line"
if command -v rg >/dev/null 2>&1; then
  hook "rg -n needle $T/g"; out=$(bash -c "$R" 2>&1)
  for m in "needle one" "needle two" "y needle three" a.txt b.txt c.md; do has "rg -n keeps $m" "$out" "$m"; done
fi
hook "find $T/g -name '*.txt'"; out=$(bash -c "$R" 2>&1)
has "find keeps a.txt" "$out" "a.txt"; has "find keeps sub/b.txt" "$out" "b.txt"
case "$out" in *c.md*) bad "find -name '*.txt' lists c.md";; *) ok "find excludes c.md";; esac
hook "wc -l $T/f.txt"; out=$(bash -c "$R" 2>&1)
has "wc -l keeps count 40" "$out" "40"

# 8. permission matrix against a synthetic Claude config (never the live one)
mkdir -p "$T/cc"
printf '%s\n' '{"permissions":{"allow":["Bash(git status)"],"deny":["Bash(git log --oneline*)"],"ask":["Bash(git diff*)"]}}' > "$T/cc/settings.json"
export CLAUDE_CONFIG_DIR="$T/cc"
hook "git status" allow;               [ "$R" = "rtk git status" ] && ok "explicit allow rule -> allow" || bad "explicit allow: [$R]"
hook "git status && git log -1" none;  [ -n "$R" ] && ok "partly allowed compound -> no decision" || bad "compound: [$R]"
hook "git diff" none;                  [ "$R" = "rtk git diff" ] && ok "ask rule -> no decision" || bad "ask rule: [$R]"
defer "git log --oneline -3" 'deny rule'
# v3: record (non-gating) how a wildcard-free allow rule treats a longer command
hook_raw "git status --short"; rc=$?
pd=$(python3 -c 'import json,sys; s=open(sys.argv[1]).read().strip(); print((json.loads(s)["hookSpecificOutput"].get("permissionDecision") or "none") if s else "silent")' "$T/h.out" 2>/dev/null)
note "allow rule Bash(git status) applied to 'git status --short': rc=$rc permissionDecision=$pd"
# v3: 8b. second synthetic config: legacy colon allow + leading-wildcard deny (live rule shape)
mkdir -p "$T/cc2"
printf '%s\n' '{"permissions":{"allow":["Bash(git log:*)"],"deny":["Bash(* --porcelain*)"]}}' > "$T/cc2/settings.json"
export CLAUDE_CONFIG_DIR="$T/cc2"
hook "git log -2" allow;               [ "$R" = "rtk git log -2" ] && ok "legacy colon allow rule -> allow" || bad "colon allow: [$R]"
defer "git status --porcelain" 'leading-wildcard deny rule'
hook "git log -2 && git status" none;  [ -n "$R" ] && ok "compound with unallowed segment -> no decision" || bad "compound2: [$R]"
unset CLAUDE_CONFIG_DIR

note "hook stderr non-empty in $nherr of $ncalls payload calls${herr1:+; first: $herr1}"
echo "COUNTS pass=$npass fail=$nfail note=$nnote"
echo "RESULT $([ $fail = 0 ] && echo pass || echo fail)"; exit $fail
