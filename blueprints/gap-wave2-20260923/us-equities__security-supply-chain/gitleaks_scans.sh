#!/usr/bin/env bash
# Gaps 5/12: guarded gitleaks full-history scans plus a synthetic positive control.
# Uses only the guarded wrapper on the ecosystem PATH. Synthetic secrets are generated
# at runtime from random bytes so no secret-shaped literal exists in this script.
set -uo pipefail
C=${C:-$HOME/.cache/gap-wave2-20260923/security-supply-chain}
REPO=${REPO:-$HOME/code/nas-wt-g2-security-supply-chain}
GL=$HOME/codex-ecosystem/bin/gitleaks-guarded
OUT=$C/work/gitleaks; mkdir -p "$OUT"
MODE=${1:-all}

scan() {  # scan LABEL ARGS...
  local label=$1; shift
  local t0=$(date +%s) rc i
  for i in $(seq 1 60); do  # exit 75 = another user's scan holds the per-user lock; wait, never bypass
  "$GL" git --no-banner --no-color --redact=100 --report-format json \
    --report-path "$OUT/$label.json" "$@" > "$OUT/$label.stdout" 2> "$OUT/$label.stderr"
  rc=$?; [[ $rc -eq 75 ]] || break; echo "$label lock busy (75), retry $i" >> "$OUT/exits.log"; sleep 20
  done
  echo "$label exit=$rc seconds=$(( $(date +%s) - t0 ))" | tee -a "$OUT/exits.log"
}

if [[ $MODE == control || $MODE == all ]]; then
  pc=$(mktemp -d "$C/work/gitleaks-control.XXXX")
  git -C "$pc" init -q
  python3 - "$pc" <<'EOF'
import secrets, string, sys, pathlib
root = pathlib.Path(sys.argv[1])
up, al = string.ascii_uppercase + "234567", string.ascii_letters + string.digits
r = lambda chars, n: "".join(secrets.choice(chars) for _ in range(n))
lines = {
    "aws.env": "AWS_ACCESS_KEY_ID=" + "AKIA" + r(up, 16) + "\n",
    "gh.txt": "token = " + "gh" + "p_" + r(al, 36) + "\n",
    "slack.txt": "hook = " + "xox" + "b-" + r(string.digits, 12) + "-" + r(string.digits, 13) + "-" + r(al, 24) + "\n",
    "config.py": "api_key = \"" + r(string.ascii_lowercase + string.digits, 40) + "\"\n",
    "id_rsa": "-----BEGIN " + "RSA PRIVATE KEY-----\n" + "\n".join(r(al + "+/", 64) for _ in range(12)) + "\n-----END " + "RSA PRIVATE KEY-----\n",
    "alpaca.env": "ALPACA_API_SECRET_KEY=" + r(al, 40) + "\n",
}
for name, text in lines.items():
    (root / name).write_text(text)
print("planted", len(lines), "synthetic secret-shaped files:", ",".join(sorted(lines)))
EOF
  git -C "$pc" add -A && git -C "$pc" -c user.name=control -c user.email=control@invalid commit -qm control
  scan control-default-rules "$pc"
  [[ $MODE == all ]] || scan control-repo-config --config "$REPO/.gitleaks.toml" "$pc"
  rm -rf "$pc"
fi
if [[ $MODE == head || $MODE == all ]]; then
  echo "head commits: $(git -C "$REPO" rev-list --count HEAD) head=$(git -C "$REPO" rev-parse HEAD)" | tee -a "$OUT/exits.log"
  scan head-repo-config --config "$REPO/.gitleaks.toml" --log-opts=HEAD "$REPO"
fi
if [[ $MODE == head2mb ]]; then
  # The first uncapped HEAD scan was stopped by the guard's 600 s limit (exit 143).
  # This run skips files larger than 2 MB; the skipped blobs are listed separately.
  echo "head commits: $(git -C "$REPO" rev-list --count HEAD) head=$(git -C "$REPO" rev-parse HEAD)" | tee -a "$OUT/exits.log"
  git -C "$REPO" rev-list --objects HEAD | git -C "$REPO" cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' \
    | awk '$1=="blob" && $3>2*1024*1024 {print $3, $2, $4}' | sort -rn > "$OUT/head-blobs-over-2mb.txt"
  echo "blobs over 2 MB reachable from HEAD: $(wc -l < "$OUT/head-blobs-over-2mb.txt")" | tee -a "$OUT/exits.log"
  scan head-repo-config-2mb --config "$REPO/.gitleaks.toml" --max-target-megabytes 2 --log-opts=HEAD "$REPO"
fi
if [[ $MODE == oversized ]]; then
  # The only path skipped by the 2 MB cap: scan its current HEAD version directly.
  t0=$(date +%s)
  for i in $(seq 1 60); do
    "$GL" dir --no-banner --no-color --redact=100 --report-format json --config "$REPO/.gitleaks.toml" \
      --report-path "$OUT/oversized-head-index.json" "$REPO/docs/ecosystem/index.html" \
      > "$OUT/oversized-head-index.stdout" 2> "$OUT/oversized-head-index.stderr"
    rc=$?; [[ $rc -eq 75 ]] || break; sleep 20
  done
  echo "oversized-head-index exit=$rc seconds=$(( $(date +%s) - t0 ))" | tee -a "$OUT/exits.log"
fi
if [[ $MODE == allrefs ]]; then
  echo "all-ref commits: $(git -C "$REPO" rev-list --all --count)" | tee -a "$OUT/exits.log"
  scan allrefs-repo-config-2mb --config "$REPO/.gitleaks.toml" --max-target-megabytes 2 --log-opts=--all "$REPO"
fi
