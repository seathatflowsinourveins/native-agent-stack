#!/usr/bin/env bash
# X9 round 3's pre-dispatch isolation, round 2's attempt-2 procedure (x9-round2/isolation-receipt.json) with round 3's
# literal targets: check the arms, remove every worktree of this session after checking its state, move every other
# scratchpad entry into a held directory, then scan the judges' root and files. Refuses on any unexpected state.
# usage: isolate_r3.sh SCRATCHPAD
set -euo pipefail
S=$1
REPO=~/code/native-agent-stack
X3=$S/convergence-r3/x9-round3
A2=$S/convergence-prompt-audit/x9-round2/arms
cmp "$S/wt-x9r3-g/CLAUDE.md" "$A2/CLAUDE.g.md"
cmp "$S/wt-x9r3-c/CLAUDE.md" "$A2/CLAUDE.c.md"
cmp "$S/wt-x9r3-0/CLAUDE.md" "$A2/CLAUDE.0.md"
echo "arms match the worktrees"
test "$(git -C "$S/wt-pa-r3" rev-parse HEAD)" = "$(git -C "$REPO" rev-parse claude/prompt-audit-instructions-20260927)"
test -z "$(git -C "$S/wt-pa-r3" status --porcelain)"
test -z "$(git -C "$S/wt-x5" status --porcelain)"
test -z "$(git -C "$S/wt-r3-base" status --porcelain)"
test -z "$(git -C "$S/wt-x9r3-0" status --porcelain)"
test "$(git -C "$S/wt-x9r3-g" status --porcelain)" = " M CLAUDE.md"
test "$(git -C "$S/wt-x9r3-c" status --porcelain)" = " M CLAUDE.md"
echo "worktree states as expected"
git -C "$REPO" worktree remove --force "$S/wt-x9r3-g"
git -C "$REPO" worktree remove --force "$S/wt-x9r3-c"
git -C "$REPO" worktree remove "$S/wt-x9r3-0"
git -C "$REPO" worktree remove "$S/wt-r3-base"
git -C "$REPO" worktree remove "$S/wt-x5"
git -C "$REPO" worktree remove "$S/wt-pa-r3"
git -C "$REPO" worktree prune
echo "worktrees of this session left: $(git -C "$REPO" worktree list | grep -c 789daede || true)"
EXPECT="addendum.txt base-f508-two-tests.log body.txt c.go checks.txt convergence-prompt-audit convergence-r3 cookbook_sha.txt decision-main.md err.txt handoff-draft.md j2 j3 m.go make_proposed.py neg-controls-46184751 pages pr444-body-a28f6a91.md pr444-body-current.md pr444-body-live.md pr444-body-new.md prompt-audit-adjudication prompt-audit-adjudication-runs prompt-audit-x9-round2-judgment prompt-audit-x9-round2-runs proposed readme.txt reg-commit-msg.txt reg-commit.err template-main.md template_hashes.py templates.f2_f3.json templates.f2_only.json templates.f3_only.json unittest-pr2-1db9cec4.log unittest-pr2-46184751.log unittest-pr2-a28f6a91.log verify web-supp"
test "$(ls -A1 "$S" | sort | tr '\n' ' ' | sed 's/ $//')" = "$EXPECT"
mkdir "$S/.hold3"
chmod 700 "$S/.hold3"
for n in addendum.txt base-f508-two-tests.log body.txt c.go checks.txt convergence-prompt-audit convergence-r3 \
  cookbook_sha.txt decision-main.md err.txt handoff-draft.md j2 m.go make_proposed.py neg-controls-46184751 pages \
  pr444-body-a28f6a91.md pr444-body-current.md pr444-body-live.md pr444-body-new.md prompt-audit-adjudication \
  prompt-audit-adjudication-runs prompt-audit-x9-round2-judgment prompt-audit-x9-round2-runs proposed readme.txt \
  reg-commit-msg.txt reg-commit.err template-main.md template_hashes.py templates.f2_f3.json templates.f2_only.json \
  templates.f3_only.json unittest-pr2-1db9cec4.log unittest-pr2-46184751.log unittest-pr2-a28f6a91.log verify web-supp; do
  mv "$S/$n" "$S/.hold3/$n"
done
echo "scratchpad now: $(ls -A1 "$S" | tr '\n' ' ')"
echo "held: $(ls -A1 "$S/.hold3" | wc -l)"
ls -A "$S/j3" "$S/j3/x9"
H3=$S/.hold3/convergence-r3/x9-round3
python3 - "$S" "$H3" <<'EOF'
import os, re, sys
from pathlib import Path
S, H3 = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(H3))
import void_patterns_r3 as v
root = S / "j3/x9/root"
hits, n = {"MAPPING": [], "PHRASES": []}, 0
for d, _, fs in os.walk(root):
    for f in fs:
        p = Path(d) / f
        try:
            t = p.read_text(errors="ignore")
        except OSError:
            continue
        n += 1
        for k in hits:
            if getattr(v, k).search(t):
                hits[k].append(str(p.relative_to(root)))
print(n, "root files;", {k: len(x) for k, x in hits.items()}, {k: x[:5] for k, x in hits.items()})
CONFIG = re.compile(r"enabledPlugins|statusLine|status-?line (?:command|is wired|wiring)|installed_plugins"
                    r"|known_marketplaces|plugins/cache|[a-z0-9-]+@[a-z0-9-]+\"?\s*:\s*true")
for d in ("adjudication-inputs", "packets", "prompts", "schemas"):
    for f in sorted((S / "j3/x9" / d).iterdir()):
        t = f.read_text()
        print(f"{d}/{f.name}: config-text matches {len(CONFIG.findall(t))}; mapping {bool(v.MAPPING.search(t))}")
EOF
python3 "$H3/check_orders_r3.py" "$S/j3/x9/packets" "$H3/round3-mapping.json"
