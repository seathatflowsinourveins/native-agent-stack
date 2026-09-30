#!/usr/bin/env bash
# Self-scan (local integration): every file this branch adds or changes relative to the base commit,
# copied at its repository path into a scratch tree and scanned in dir mode, then the branch's commits in
# git mode (--log-opts=<base>..HEAD); both with the verified gitleaks 8.30.1 and betterleaks 1.8.1 (the
# flags of their jobs), this repository's .gitleaks.toml and --redact. Prints counts and rule, file and
# line only. Arguments: the worktree and the base commit.
set -u
D="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
W="$1"; BASE="$2"
L="$D/repair/final"; T="$D/repair/changed-tree"
rm -rf "$T"; mkdir -p "$L" "$T" "$D/iso-home" "$D/iso-cache"
cd "$W" || exit 2
mapfile -t files < <({ git diff --name-only --diff-filter=AM "$BASE"; git ls-files --others --exclude-standard; } | sort -u)
for f in "${files[@]}"; do cp --parents -- "$f" "$T/"; done
echo "start=$(date -u +%Y-%m-%dT%H:%M:%SZ) changed_or_new_files=${#files[@]} branch_commits=$(git rev-list --count "$BASE..HEAD")"
show() { jq -r '(. // [])[] | "   " + ([.RuleID, .File, (.StartLine | tostring)] | join("\t"))' "$1"; }
count() { jq '(. // []) | length' "$1" 2>/dev/null || echo no-report; }
BL=(env HOME="$D/iso-home" XDG_CACHE_HOME="$D/iso-cache" "$D/betterleaks/betterleaks")
BLFLAGS=(--max-archive-depth 0 --gitleaks-ignore-path "$W/.gitleaksignore")
for tool in gitleaks betterleaks; do
  if [ "$tool" = gitleaks ]; then cmd=("$D/gitleaks/gitleaks"); extra=(); else cmd=("${BL[@]}"); extra=("${BLFLAGS[@]}"); fi
  (cd "$T" && "${cmd[@]}" dir . --config "$W/.gitleaks.toml" --max-target-megabytes 2 "${extra[@]}" --redact \
     --no-banner --report-format json --report-path "$L/changed-$tool.json" > /dev/null 2>&1)
  rc=$?; echo "$tool dir, changed files: rc=$rc findings=$(count "$L/changed-$tool.json")"; show "$L/changed-$tool.json"
  "${cmd[@]}" git . --config .gitleaks.toml --max-target-megabytes 2 "${extra[@]}" --log-opts="$BASE..HEAD" --redact \
    --no-banner --report-format json --report-path "$L/range-$tool.json" > /dev/null 2>&1
  rc=$?; echo "$tool git, $BASE..HEAD: rc=$rc findings=$(count "$L/range-$tool.json")"; show "$L/range-$tool.json"
done
rm -rf "$T"
