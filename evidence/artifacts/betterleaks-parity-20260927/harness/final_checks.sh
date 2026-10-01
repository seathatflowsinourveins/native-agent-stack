#!/usr/bin/env bash
# The named checks on the final worktree (local integration wrapper around unchanged tools), run from the
# scratch directory that holds the verified binaries. Arguments: the worktree and the directory holding
# this run's lint tools (zizmor 1.30.1 in venv-zizmor/, actionlint 1.7.12, shellcheck 0.11.0 in sc-bin/).
# The test modules use the `gitleaks` on PATH, the host's guarded gitleaks 8.30.1 launcher. Prints one
# line per check; full outputs stay under repair/final/ in this directory.
set -u
D="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
W="$1"; LINT="$2"
L="$D/repair/final"; mkdir -p "$L" "$D/iso-cache"
export XDG_CACHE_HOME="$D/iso-cache"
cd "$W" || exit 2
echo "start=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "gitleaks on PATH reports $(gitleaks version 2>&1)"
for m in tests.test_gitleaks_config tests.test_workflow_hardening tests.test_catalog_freshness_pins \
         tests.test_workflow_security tests.test_workflow_security_coverage; do
  s=$(date +%s)
  python3 -m unittest "$m" > "$L/$m.txt" 2>&1
  rc=$?
  echo "$m rc=$rc $(grep -E '^Ran ' "$L/$m.txt") $(tail -n 1 "$L/$m.txt") ($(( $(date +%s) - s ))s)"
done
python3 "$D/mutation_controls.py" "$W" > "$L/mutation-controls.jsonl" 2>&1
rc=$?; echo "mutation controls rc=$rc $(tail -n 1 "$L/mutation-controls.jsonl")"
"$LINT/venv-zizmor/bin/zizmor" --no-config --no-ignores --persona regular --strict-collection . > "$L/zizmor.out" 2>&1
rc=$?; echo "zizmor $("$LINT/venv-zizmor/bin/zizmor" --version) rc=$rc $(tail -n 1 "$L/zizmor.out")"
PATH="$LINT/sc-bin:$PATH" "$LINT/actionlint" > "$L/actionlint-all.out" 2>&1
rc=$?; echo "actionlint $("$LINT/actionlint" -version | head -n 1) all workflows rc=$rc output_lines=$(wc -l < "$L/actionlint-all.out")"
PATH="$LINT/sc-bin:$PATH" "$LINT/actionlint" .github/workflows/validate.yml > "$L/actionlint-validate.out" 2>&1
rc=$?; echo "actionlint validate.yml rc=$rc output_lines=$(wc -l < "$L/actionlint-validate.out")"
PATH="$LINT/sc-bin:$PATH" shellcheck evidence/artifacts/betterleaks-parity-20260927/harness/*.sh > "$L/shellcheck.out" 2>&1
rc=$?; echo "shellcheck $("$LINT/sc-bin/shellcheck" --version | sed -n 's/^version: //p') on the harness scripts rc=$rc output_lines=$(wc -l < "$L/shellcheck.out")"
python3 scripts/validate.py > "$L/validate.out" 2>&1
rc=$?; echo "scripts/validate.py rc=$rc $(tail -n 1 "$L/validate.out")"
echo "end=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
