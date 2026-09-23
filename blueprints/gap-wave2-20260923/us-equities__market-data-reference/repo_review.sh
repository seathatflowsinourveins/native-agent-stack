#!/usr/bin/env bash
# Gaps 17/18: retained GitHub metadata for one repository (gh api, read-only GETs).
# Usage: repo_review.sh OWNER/REPO OUT_PREFIX
set -uo pipefail
R=$1; O=$2
run() { local name=$1; shift; "$@" > "$O-$name.json" 2> "$O-$name.err"; echo "$name exit=$?"; [ -s "$O-$name.err" ] || rm -f "$O-$name.err"; }
run repo gh api "repos/$R"
run release-latest gh api "repos/$R/releases/latest"
run releases gh api "repos/$R/releases?per_page=5"
run tags gh api "repos/$R/tags?per_page=10"
run license gh api "repos/$R/license"
run commits gh api "repos/$R/commits?per_page=15"
run readme gh api "repos/$R/readme"
run tree gh api "repos/$R/git/trees/HEAD?recursive=1"
run contributors gh api "repos/$R/contributors?per_page=10"
