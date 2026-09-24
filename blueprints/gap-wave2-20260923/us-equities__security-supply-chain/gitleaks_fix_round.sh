#!/usr/bin/env bash
# Gaps 5/12 fix round: close the two scan exclusions left by the capped history scan.
#   oversized  every blob > 2 MB reachable from HEAD, written with git cat-file into a private
#              temp dir and scanned with the guarded `gitleaks dir` in batches (guard: 600 s each)
#   merges     each merge commit's diff against its first parent (covers merge-resolution content)
#   controls   detection controls for both methods, with runtime-generated synthetic tokens
# Only the guarded wrapper is used. Unredacted reports stay in a 0700 temp dir and are
# reduced by classify_findings.py to redacted summaries, then deleted.
set -uo pipefail
C=${C:-$HOME/.cache/gap-wave2-20260923/security-supply-chain}
REPO=${REPO:-$HOME/code/nas-wt-g2-security-supply-chain}
GL=$HOME/codex-ecosystem/bin/gitleaks-guarded
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$C/work/gitleaks-fix; mkdir -p "$OUT"; LOG=$OUT/exits.log
MODE=${1:-all}; BATCH=${BATCH:-40}
umask 077

guarded() {  # guarded LABEL ARGS... ; retries only on the per-user lock (75), never raises limits
  local label=$1; shift; local t0=$(date +%s) rc i
  for i in $(seq 1 60); do
    "$GL" "$@" > "$OUT/$label.stdout" 2> "$OUT/$label.stderr"; rc=$?
    [[ $rc -eq 75 ]] || break; echo "$label lock busy (75), retry $i" >> "$LOG"; sleep 20
  done
  echo "$label exit=$rc seconds=$(( $(date +%s) - t0 ))" | tee -a "$LOG"
}
token() { python3 -c 'import secrets,string;a=string.ascii_letters+string.digits;print("gh"+"p_"+"".join(secrets.choice(a) for _ in range(36)))'; }

PRIV=$(mktemp -d "$C/work/gitleaks-fix-private.XXXX"); trap 'rm -rf "$PRIV"' EXIT

if [[ $MODE == controls || $MODE == all ]]; then
  # Oversized control: one listed blob, unmodified and with an appended synthetic token.
  ctl=$PRIV/oversized-control; mkdir -p "$ctl"
  b=$(git -C "$REPO" rev-parse HEAD:docs/ecosystem/index.html)
  git -C "$REPO" cat-file blob "$b" > "$ctl/unmodified.html"
  { git -C "$REPO" cat-file blob "$b"; printf '\ntoken = "%s"\n' "$(token)"; } > "$ctl/planted.html"
  guarded oversized-control dir --no-banner --no-color --redact=0 --report-format json \
    --config "$REPO/.gitleaks.toml" --report-path "$PRIV/oversized-control.json" "$ctl"
  # Merge-resolution control: the synthetic token exists only in the merge commit's resolution.
  m=$PRIV/merge-control; git init -q -b main "$m"; g() { git -C "$m" -c user.name=c -c user.email=c@invalid "$@"; }
  echo base > "$m/a.txt"; g add -A; g commit -qm base
  g checkout -qb side; echo side > "$m/b.txt"; g add -A; g commit -qm side
  g checkout -q main; echo main > "$m/c.txt"; g add -A; g commit -qm main
  g merge -q --no-ff --no-commit side; printf 'token = "%s"\n' "$(token)" > "$m/resolution.txt"; g add -A; g commit -qm merge
  echo "merge-control commits: $(git -C "$m" rev-list --count HEAD) merges: $(git -C "$m" rev-list --merges --count HEAD)" | tee -a "$LOG"
  guarded merge-control-default git --no-banner --no-color --redact=0 --report-format json \
    --report-path "$PRIV/merge-control-default.json" --log-opts=HEAD "$m"
  guarded merge-control-first-parent git --no-banner --no-color --redact=0 --report-format json \
    --report-path "$PRIV/merge-control-first-parent.json" "--log-opts=--merges --diff-merges=first-parent HEAD" "$m"
fi

if [[ $MODE == oversized || $MODE == all ]]; then
  echo "oversized head=$(git -C "$REPO" rev-parse HEAD)" | tee -a "$LOG"
  git -C "$REPO" rev-list --objects HEAD | git -C "$REPO" cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' \
    | awk '$1=="blob" && $3>2*1024*1024 {print $3, $2, $4}' | sort -rn > "$OUT/oversized-blobs-now.txt"
  echo "blobs over 2 MB reachable from HEAD: $(wc -l < "$OUT/oversized-blobs-now.txt")" | tee -a "$LOG"
  n=0; batch=0
  while read -r size oid path; do
    d=$PRIV/blobs/b$(printf %02d $batch); mkdir -p "$d"
    git -C "$REPO" cat-file blob "$oid" > "$d/$oid.html"
    n=$((n+1)); (( n % BATCH == 0 )) && batch=$((batch+1))
  done < "$OUT/oversized-blobs-now.txt"
  echo "blobs written: $(find "$PRIV/blobs" -type f | wc -l) in $(ls "$PRIV/blobs" | wc -l) batches" | tee -a "$LOG"
  for d in "$PRIV"/blobs/b*; do
    k=$(basename "$d")
    guarded "oversized-$k" dir --no-banner --no-color --redact=0 --report-format json \
      --config "$REPO/.gitleaks.toml" --report-path "$PRIV/oversized-$k.json" "$d"
    echo "oversized-$k files=$(ls "$d" | wc -l)" >> "$LOG"
  done
fi

if [[ $MODE == merges || $MODE == all ]]; then
  echo "merges head=$(git -C "$REPO" rev-parse HEAD) merge commits: $(git -C "$REPO" rev-list --merges --count HEAD)" | tee -a "$LOG"
  guarded merges-first-parent-2mb git --no-banner --no-color --redact=0 --report-format json \
    --config "$REPO/.gitleaks.toml" --max-target-megabytes 2 --report-path "$PRIV/merges-first-parent-2mb.json" \
    "--log-opts=--merges --diff-merges=first-parent HEAD" "$REPO"
fi

# Reduce every unredacted report to a redacted summary before the trap deletes it.
python3 "$HERE/classify_findings.py" "$PRIV" "$OUT" "$REPO"
