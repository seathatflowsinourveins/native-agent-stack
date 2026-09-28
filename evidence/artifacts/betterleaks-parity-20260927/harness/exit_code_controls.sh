#!/usr/bin/env bash
# Local control (not an upstream test) of the trial job's report-only mechanism on the verified betterleaks
# 1.8.1 binary (coordinator repair, 2026-09-28), run from the scratch directory that holds it. A scratch
# directory gets one synthetic line holding a randomly generated GitHub-token-shaped value; the value is
# generated here, never printed, and removed with the directory. Every run passes the job's flags and
# --redact, with HOME and XDG_CACHE_HOME in scratch; only exit statuses and finding counts are printed.
#   A  dir mode, default --exit-code              B  dir mode, --exit-code 0
#   C  B plus one unreadable file (chmod 000)     D  B plus one unreadable directory (chmod 000)
#   E  B with a --config that does not exist      F  B with a --report-path in a missing directory
#   G  git mode over a one-commit scratch repository, --exit-code 0
#   H  G with an unknown revision in --log-opts
# Argument: the worktree, whose .gitleaks.toml every run uses.
set -uo pipefail
D="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
W="$1"
C="$D/repair/exit-code-control"
R="$D/repair/exit-code-reports"
rm -rf "$C" "$R"; mkdir -p "$C/planted" "$C/locked" "$R" "$D/iso-home" "$D/iso-cache"
python3 - "$C" <<'EOF'
import secrets
import string
import sys
from pathlib import Path

value = "ghp_" + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(36))
(Path(sys.argv[1]) / "planted/planted.txt").write_text(f'github_token = "{value}"\n')
EOF
cd "$C" || exit 1
bl() { env HOME="$D/iso-home" XDG_CACHE_HOME="$D/iso-cache" "$D/betterleaks/betterleaks" "$@" > /dev/null 2>&1; }
count() { jq '(. // []) | length' "$1" 2>/dev/null || echo no-report; }
FLAGS=(--max-target-megabytes 2 --max-archive-depth 0 --gitleaks-ignore-path .gitleaksignore --redact --no-banner
       --report-format json)
bl dir . --config "$W/.gitleaks.toml" "${FLAGS[@]}" --report-path "$R/a.json"
echo "A dir, default --exit-code: rc=$? findings=$(count "$R/a.json")"
bl dir . --config "$W/.gitleaks.toml" "${FLAGS[@]}" --report-path "$R/b.json" --exit-code 0
echo "B dir, --exit-code 0: rc=$? findings=$(count "$R/b.json")"
printf 'plain text\n' > unreadable.txt; chmod 000 unreadable.txt
bl dir . --config "$W/.gitleaks.toml" "${FLAGS[@]}" --report-path "$R/c.json" --exit-code 0
echo "C dir, --exit-code 0, an unreadable file: rc=$? findings=$(count "$R/c.json")"
chmod 600 unreadable.txt; chmod 000 locked
bl dir . --config "$W/.gitleaks.toml" "${FLAGS[@]}" --report-path "$R/d.json" --exit-code 0
echo "D dir, --exit-code 0, an unreadable directory: rc=$? findings=$(count "$R/d.json")"
chmod 700 locked
bl dir . --config "$C/missing.toml" "${FLAGS[@]}" --report-path "$R/e.json" --exit-code 0
echo "E dir, --exit-code 0, a missing --config: rc=$? findings=$(count "$R/e.json")"
bl dir . --config "$W/.gitleaks.toml" "${FLAGS[@]}" --report-path "$C/missing-dir/f.json" --exit-code 0
echo "F dir, --exit-code 0, a report path in a missing directory: rc=$?"
g() { env GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 git -c core.hooksPath=/dev/null -c user.name=fixture \
        -c user.email=fixture@example.invalid -c commit.gpgsign=false "$@"; }
g init -q && g add planted/planted.txt && g commit -q -m planted || echo "scratch commit failed"
bl git . --config "$W/.gitleaks.toml" "${FLAGS[@]}" --log-opts=HEAD --report-path "$R/g.json" --exit-code 0
echo "G git, --exit-code 0: rc=$? findings=$(count "$R/g.json")"
bl git . --config "$W/.gitleaks.toml" "${FLAGS[@]}" --log-opts=no-such-revision --report-path "$R/h.json" --exit-code 0
echo "H git, --exit-code 0, an unknown revision: rc=$? findings=$(count "$R/h.json")"
cd "$D" && rm -rf "$C"
echo "control directory removed: $([ -e "$C" ] && echo no || echo yes)"
