#!/usr/bin/env bash
# Live-captured re-run of dvc-arm-restore-compare (the first run's log was reconstructed afterwards).
# Preregistered (written before this script ran): the DVC arm passes if `dvc checkout` after deleting the
# tracked directory restores files whose sha256 equal the pre-delete sha256. The baseline arm passes if a
# second `replay.py materialize` from the git-tracked fixture.json produces the same per-file sha256. Both
# arms are compared on the same four files; any difference in either arm is a failure of that arm.
# Amended before the second attempt: the first attempt used a python3.13 without duckdb (ModuleNotFoundError), so it
# materialized nothing; this attempt uses the SDK venv built from adoption/sdk/requirements-linux-x86_64-py313.lock.
set -u
O=$(cd "$(dirname "$0")" && pwd)
CAT=~/code/nas-wt-gapint
SDK_PYTHON=~/.local/share/codex-ecosystem/tools/sdk-env-baseline-20260922/bin/python3.13
DVC=~/.local/share/codex-ecosystem/tools/dvc-3.67.1-20260922/bin/dvc
W=$O/work; rm -rf "$W"; mkdir -p "$W"
exec > >(tee "$O/run.log") 2>&1
set -x
date -u +%FT%TZ
"$DVC" --version; git --version; "$SDK_PYTHON" --version
cd "$CAT/blueprints/us-equities/nanosecond-replay"
"$SDK_PYTHON" replay.py materialize --source fixture.json --output "$W/materialized"
cd "$W" && mkdir repo && cp -a materialized repo/materialized && chmod -R u+w repo/materialized && cd repo
git init -q && git config user.email gap-resolution@local && git config user.name gap-resolution
"$DVC" init -q && "$DVC" add materialized && git add materialized.dvc .gitignore .dvc && git commit -q -m 'track materialized fixture'
find materialized -type f | sort | xargs sha256sum | tee "$O/pre-delete.sha256"
rm -rf materialized
"$DVC" status
"$DVC" checkout
find materialized -type f | sort | xargs sha256sum | tee "$O/post-checkout.sha256"
diff "$O/pre-delete.sha256" "$O/post-checkout.sha256"; echo "dvc_arm_diff_exit=$?"
cd "$CAT/blueprints/us-equities/nanosecond-replay"
"$SDK_PYTHON" replay.py materialize --source fixture.json --output "$W/rematerialized"
(cd "$W/rematerialized" && find . -type f | sort | xargs sha256sum | sed 's#  \./#  materialized/#') | tee "$O/baseline-rematerialize.sha256"
diff "$O/pre-delete.sha256" "$O/baseline-rematerialize.sha256"; echo "baseline_arm_diff_exit=$?"
date -u +%FT%TZ
