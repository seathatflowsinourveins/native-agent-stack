#!/usr/bin/env bash
# Local control (not an upstream test): does dir mode read a real .git directory? A hosted checkout has
# one; the recording worktree's .git is a file. A scratch directory gets `git init` and the same synthetic
# line, holding a randomly generated GitHub-token-shaped value, in .git/planted.txt and in
# planted/planted.txt. Both verified scanners scan it with this repository's .gitleaks.toml and the dir-mode
# flags of their jobs, --redact; only rule, file and line are printed. The value is generated here, never
# printed, and removed with the directory.
set -uo pipefail
D="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
W="$1"
C="$D/repair/gitdir-control"
rm -rf "$C"; mkdir -p "$C/planted" "$D/iso-home" "$D/iso-cache"
git -C "$C" init -q
python3 - "$C" <<'EOF'
import secrets
import string
import sys
from pathlib import Path

value = "ghp_" + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(36))
for rel in ("planted/planted.txt", ".git/planted.txt"):
    (Path(sys.argv[1]) / rel).write_text(f'github_token = "{value}"\n')
EOF
cd "$C" || exit 1
show() { jq -r '(. // [])[] | "   " + ([.RuleID, .File, (.StartLine | tostring)] | join("\t"))' "$1"; }
"$D/gitleaks/gitleaks" dir . --config "$W/.gitleaks.toml" --max-target-megabytes 2 --redact --no-banner \
  --report-format json --report-path "$D/repair/gitdir-gitleaks.json" > /dev/null 2>&1
echo "gitleaks 8.30.1 rc=$?"; show "$D/repair/gitdir-gitleaks.json"
env HOME="$D/iso-home" XDG_CACHE_HOME="$D/iso-cache" "$D/betterleaks/betterleaks" dir . --config "$W/.gitleaks.toml" \
  --max-target-megabytes 2 --max-archive-depth 0 --gitleaks-ignore-path .gitleaksignore --redact --no-banner \
  --report-format json --report-path "$D/repair/gitdir-betterleaks.json" > /dev/null 2>&1
echo "betterleaks 1.8.1 rc=$?"; show "$D/repair/gitdir-betterleaks.json"
cd "$D" && rm -rf "$C"
echo "control directory removed: $([ -e "$C" ] && echo no || echo yes)"
