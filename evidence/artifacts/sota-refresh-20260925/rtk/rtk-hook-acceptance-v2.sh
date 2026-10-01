#!/usr/bin/env bash
# Corrected discriminating acceptance for an rtk candidate prefix on the Claude Code
# PreToolUse Bash hook path (`rtk hook claude`). Derived from the reviewed
# rtk-hook-acceptance.sh (sha256 c14e75e7...) with these changes:
#  - the hook's exit status is asserted (exit 2 blocks the Bash call in Claude Code);
#  - deferral means raw stdout is EMPTY (a deny/ask/garbage reply no longer counts as a defer);
#  - with the live settings (no Bash allow rules) a rewrite must carry NO permissionDecision;
#  - a synthetic CLAUDE_CONFIG_DIR checks the allow/ask/deny/compound permission matrix;
#  - success-path content checks for the most frequent rewritten commands;
#  - the known pre-existing `rtk diff` exit-code defect is reported as NOTE (non-gating).
# Usage: rtk-hook-acceptance-v2.sh <prefix-dir-containing-rtk> <expected-version>
set -u
P=${1:?prefix dir}; WANT=${2:?expected version, e.g. 0.50.0}
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export XDG_DATA_HOME="$T/data" RTK_DB_PATH="$T/data/history.db" RTK_TELEMETRY_DISABLED=1
export PATH="$P:$PATH"
cd "$T" || exit 2
fail=0
ok()   { printf 'PASS %s\n' "$1"; }
bad()  { printf 'FAIL %s\n' "$1"; fail=1; }
note() { printf 'NOTE %s\n' "$1"; }

hook_raw() { # one Claude PreToolUse payload -> $T/h.out (stdout), $T/h.err; returns hook exit code
  python3 -c 'import json,os,sys;print(json.dumps({"session_id":"acc","tool_use_id":"acc-1","cwd":os.getcwd(),"permission_mode":"bypassPermissions","hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":sys.argv[1],"description":"acc","timeout":30000}}))' "$1" \
    | "$P/rtk" hook claude > "$T/h.out" 2> "$T/h.err"
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

git init -q "$T/repo" && cd "$T/repo" && git config user.email a@b.invalid && git config user.name acc
for i in $(seq 1 12); do echo "$i" > n.txt; git add n.txt; git commit -qm "c$i"; done
seq 1 4000 | sed 's/^/row /' > big.txt; git add big.txt; git commit -qm big
chk_fail gitlog "git log -1 nsr-no-such-ref" 128 "fatal: ambiguous argument 'nsr-no-such-ref'"

# 3. deferral invariants: exit 0 and empty stdout
defer 'echo $(whoami)' 'command substitution'
defer "git status > $T/out" 'file redirect'
defer "$(printf "cat <<'EOF'\nx\nEOF")" 'heredoc'
defer 'htop' 'no rtk equivalent'
defer "git show HEAD:big.txt | sha256sum" 'non-display pipe consumer'

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

# 8. permission matrix against a synthetic Claude config (never the live one)
mkdir -p "$T/cc"
printf '%s\n' '{"permissions":{"allow":["Bash(git status)"],"deny":["Bash(git log --oneline*)"],"ask":["Bash(git diff*)"]}}' > "$T/cc/settings.json"
export CLAUDE_CONFIG_DIR="$T/cc"
hook "git status" allow;               [ "$R" = "rtk git status" ] && ok "explicit allow rule -> allow" || bad "explicit allow: [$R]"
hook "git status && git log -1" none;  [ -n "$R" ] && ok "partly allowed compound -> no decision" || bad "compound: [$R]"
hook "git diff" none;                  [ "$R" = "rtk git diff" ] && ok "ask rule -> no decision" || bad "ask rule: [$R]"
defer "git log --oneline -3" 'deny rule'
unset CLAUDE_CONFIG_DIR

echo "RESULT $([ $fail = 0 ] && echo pass || echo fail)"; exit $fail
