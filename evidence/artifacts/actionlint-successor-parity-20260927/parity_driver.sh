#!/usr/bin/env bash
# Local integration check (thin parity driver), not an upstream test.
#
# Runs two already-verified upstream actionlint binaries over one checkout the way
# .github/workflows/validate.yml's "Check workflow syntax and expressions with pinned upstream
# actionlint" step does ("$BIN" -version, then "$BIN" -color, from the repository root with no
# file arguments, so actionlint discovers .github/workflows itself: `actionlint --help`, both
# releases). Each binary is then run with actionlint's documented JSON template,
# -format '{{json .}}' (docs/usage.md in rhysd/actionlint v1.7.12 and kjanat/actionlint v1.17.0),
# and once with -verbose, whose "Collected N YAML files" and 'Rule "shellcheck" was disabled'
# lines show what was linted and which external tools ran. compare.py pairs the two JSON reports.
# Each binary sees the same minimal environment (env -i) and the same PATH in each tool
# configuration, so shellcheck and pyflakes availability is identical for both.
#
# Usage: parity_driver.sh REPO OUT OLD_BIN NEW_BIN SHELLCHECK_DIR
set -u
REPO=$1 OUT=$2 OLD=$3 NEW=$4 SC_DIR=$5
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT/home"
declare -A PATHS=([no-tools]="/usr/bin:/bin" [shellcheck-0.9.0]="$SC_DIR:/usr/bin:/bin")
for config in no-tools shellcheck-0.9.0; do
  path=${PATHS[$config]}
  dir="$OUT/$config"
  mkdir -p "$dir"
  # Tool availability under this PATH (present/absent, never the scratch path itself).
  env -i PATH="$path" HOME="$OUT/home" LANG=C.UTF-8 bash -c \
    'for t in shellcheck pyflakes; do if command -v "$t" >/dev/null; then echo "$t=present"; else echo "$t=absent"; fi; done;
     command -v shellcheck >/dev/null && shellcheck --version | sed -n "s/^version: /shellcheck_version=/p"' \
    > "$dir/tools.txt"
  for pair in "1.7.12:$OLD" "1.17.0:$NEW"; do
    tag=${pair%%:*} bin=${pair#*:}
    run() {  # run LABEL ARGS... : exit code, stdout, stderr and wall time of one invocation
      local label=$1; shift
      local start end
      start=$(date +%s%N)
      (cd "$REPO" && env -i PATH="$path" HOME="$OUT/home" LANG=C.UTF-8 "$bin" "$@") \
        > "$dir/$tag.$label.stdout" 2> "$dir/$tag.$label.stderr"
      echo $? > "$dir/$tag.$label.exit"
      end=$(date +%s%N)
      echo $(( (end - start) / 1000000 )) > "$dir/$tag.$label.ms"
    }
    run version -version
    run color -color
    run json -format '{{json .}}'
    run verbose -verbose -color
    plain=$(sed -E 's/\x1b\[[0-9;]*m//g' "$dir/$tag.verbose.stderr")
    {
      echo "collected=$(grep -oE 'Collected [0-9]+ YAML files' <<<"$plain" | head -n 1)"
      echo "shellcheck_rule_disabled_lines=$(grep -c 'Rule "shellcheck" was disabled' <<<"$plain")"
      echo "pyflakes_rule_disabled_lines=$(grep -c 'Rule "pyflakes" was disabled' <<<"$plain")"
    } > "$dir/$tag.verbose.summary"
  done
  python3 "$HERE/compare.py" "$dir/1.7.12.json.stdout" "$dir/1.17.0.json.stdout" > "$dir/compare.json"
  printf '%s: 1.7.12 exit=%s | 1.17.0 exit=%s | %s\n' "$config" \
    "$(cat "$dir/1.7.12.color.exit")" "$(cat "$dir/1.17.0.color.exit")" \
    "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["counts"])' "$dir/compare.json")"
done
