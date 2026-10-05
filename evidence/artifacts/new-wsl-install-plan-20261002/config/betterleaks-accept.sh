#!/usr/bin/env bash
# betterleaks/betterleaks@v1.9.0:Makefile:15-16 (unchanged make test),
# go.mod:3-5 (toolchain), README.md:57-70 (native directory scan).
# This qualifies the installation only. The required CI/hook gate stays gitleaks
# 8.30.1 until P1, docs/decisions/2026-10-02-github-automation-practice.md:40-57.
set -euo pipefail
: "${plan_dir:?Run through accept.sh}"
betterleaks_probe="$(mktemp -d)"
trap 'rm -rf -- "$betterleaks_probe"' EXIT
git clone --quiet --depth 1 --branch v1.9.0 \
  https://github.com/betterleaks/betterleaks.git "$betterleaks_probe/source"
test "$(git -C "$betterleaks_probe/source" rev-parse HEAD)" = 81aff7a638638aae3a659845d089043e1d8fe9ac
# mise supplies the upstream-requested Go toolchain; no global Go pin moves.
# The race-enabled upstream test also requires a C compiler on PATH.
MISE_YES=1 mise exec go@1.25.12 -- make -C "$betterleaks_probe/source" test
printf 'betterleaks | upstream-make-test-exit=0\n' >&2
betterleaks dir "$plan_dir" --redact --no-banner
printf 'betterleaks | native-directory-smoke-exit=0 | P1=open | required-gate=gitleaks-8.30.1\n' >&2
