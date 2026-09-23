#!/usr/bin/env bash
# Gap-wave-2 identity-provenance gaps 0 and 2: dvc repro / restore / reselect / project-local comparison.
# Preregistration: preregistration.json in this directory (committed before this script first ran).
# Usage: run_dvc_arm.sh OUTDIR   (OUTDIR must not exist; everything, including the scratch repos, is created there)
# Repo "git" (git+DVC) runs replay.py and temporal_snapshot.py stages (dvc.yaml). Repo "identity" is a
# `dvc init --no-scm` repo for the security-identity chain (dvc-identity.yaml), because probe.py refuses to
# write a capture inside a git work tree. Attempt 1 (single git repo for all stages) failed on that guard;
# its log is kept as attempt1-run.log. Attempt 2 (two repos, no explicit `dvc add` arm) passed and is kept as
# attempt2-run.log; attempt 3 added the native `dvc add` arm and is the cited run.
set -u
H=$(cd "$(dirname "$0")" && pwd)
WT=$(cd "$H/../../.." && pwd)
C=$HOME/.cache/gap-wave2-20260923/identity-provenance
export PATH="$C/venv-core/bin:$PATH"
O=$1; mkdir "$O" || exit 1
# Isolation: temp HOME/XDG dirs so DVC/git never read or write the user config; DVC analytics and update checks off.
mkdir -p "$O/home"; export HOME="$O/home" XDG_CONFIG_HOME="$O/home"/.config XDG_CACHE_HOME="$O/home"/.cache DVC_NO_ANALYTICS=1 GIT_CONFIG_NOSYSTEM=1
exec > >(tee "$O/run.log") 2>&1
set -x
date -u +%FT%TZ
command -v python dvc; python --version; dvc --version; git --version
python -c 'import duckdb, pandas; print("duckdb", duckdb.__version__, "pandas", pandas.__version__)'

dvc_cycle() {  # $1 = label, cwd = repo root with dvc.yaml
  local L=$1
  : ==== "$L" C0.1/C2.1 dvc repro
  dvc repro; echo "${L}_repro1_exit=$?"
  cat dvc.lock
  [ -d .git ] && { git add -A && git commit -q -m 'dvc.lock after first repro'; git status --short; }
  : ==== "$L" C0.2 cache-aware second repro and status
  dvc repro; echo "${L}_repro2_exit=$?"
  dvc status; echo "${L}_status_exit=$?"
  dvc dag
  : ==== "$L" C0.3 delete every out, dvc checkout, compare sha256 lists
  find data out -type f | sort | xargs sha256sum > "$O/$L-pre-delete.sha256"; wc -l < "$O/$L-pre-delete.sha256"
  cp -a out "$O/$L-repro-out"
  chmod -R u+w data; rm -rf data out
  dvc status; echo "${L}_status_after_delete_exit=$?"
  dvc checkout; echo "${L}_checkout_exit=$?"
  find data out -type f | sort | xargs sha256sum > "$O/$L-post-checkout.sha256"
  diff "$O/$L-pre-delete.sha256" "$O/$L-post-checkout.sha256"; echo "${L}_restore_diff_exit=$?"
  dvc status; echo "${L}_status_after_checkout_exit=$?"
}

# ---------------- repo "git": replay.py and temporal_snapshot.py ----------------
R=$O/repo-git; mkdir -p "$R/code" "$R/stages"
for d in nanosecond-replay point-in-time financial-data; do cp -a "$WT/blueprints/us-equities/$d" "$R/code/$d"; done
cp "$H/stage.py" "$R/stages/stage.py"; cp "$H/dvc.yaml" "$R/dvc.yaml"
cd "$R"
git init -q && git config user.email gap-wave2@local && git config user.name gap-wave2
dvc init -q && dvc config core.analytics false && dvc config core.check_update false && dvc config core.site_cache_dir "$O/dvc-site-cache" && git add -A && git commit -q -m 'code, stage driver and dvc.yaml'
: ==== git native dvc add arm: materialize outside the pipeline, dvc add, delete, checkout, select
mkdir -p tracked && python code/nanosecond-replay/replay.py materialize --source code/nanosecond-replay/fixture.json --output tracked/ns_added > "$O/add-materialize.json"; echo "add_materialize_exit=$?"
dvc add tracked/ns_added; echo "dvc_add_exit=$?"
git add tracked/ns_added.dvc tracked/.gitignore && git commit -q -m 'dvc add tracked/ns_added'
find tracked/ns_added -type f | sort | xargs sha256sum > "$O/add-pre-delete.sha256"
chmod -R u+w tracked/ns_added; rm -rf tracked/ns_added
dvc checkout tracked/ns_added.dvc; echo "add_checkout_exit=$?"
find tracked/ns_added -type f | sort | xargs sha256sum > "$O/add-post-checkout.sha256"
diff "$O/add-pre-delete.sha256" "$O/add-post-checkout.sha256"; echo "add_restore_diff_exit=$?"
python stages/stage.py ns-select --code code --materialized tracked/ns_added --manifest "$O/add-materialize.json" --out "$O/add-restored-ns_select.json"; echo "add_restored_ns_select_exit=$?"
dvc_cycle git
: ==== git C0.4/C0.5/C2.2 rerun select and quarantine directly on the DVC-restored data
mkdir -p "$O/restored-rerun"
python stages/stage.py ns-select --code code --materialized data/ns_materialized --manifest data/ns_materialize.json --out "$O/restored-rerun/ns_select.json"; echo "restored_ns_select_exit=$?"
python stages/stage.py ns-quarantine --code code --materialized data/ns_materialized --manifest data/ns_materialize.json --out "$O/restored-rerun/ns_quarantine.json"; echo "restored_ns_quarantine_exit=$?"
python stages/stage.py pit-select --code code --materialized data/pit_snapshot --manifest data/pit_snapshot.json --out "$O/restored-rerun/pit_select.json"; echo "restored_pit_select_exit=$?"
python stages/stage.py pit-quarantine --code code --materialized data/pit_snapshot --manifest data/pit_snapshot.json --out "$O/restored-rerun/pit_quarantine.json"; echo "restored_pit_quarantine_exit=$?"
# replay.py select CLI exit-code-2 directly on the restored snapshot with the wrong digest (raw stdout kept)
python code/nanosecond-replay/replay.py select --snapshot data/ns_materialized --snapshot-sha256 "$(printf '0%.0s' {1..64})" --cutoff 2025-02-01T21:00:00.000000100Z --universe-id fixture-universe --feed fixture-feed; echo "restored_wrong_digest_cli_exit=$?"
cp -a data/ns_materialize.json data/pit_snapshot.json "$O/restored-rerun/"
cp data/ns_materialized/snapshot.json "$O/first-ns-snapshot.json"; cp data/pit_snapshot/snapshot.json "$O/first-pit-snapshot.json"
: ==== git C0.6 forced regeneration
dvc repro --force; echo "git_repro_force_exit=$?"
find data out -type f | sort | xargs sha256sum > "$O/git-post-force.sha256"
diff "$O/git-pre-delete.sha256" "$O/git-post-force.sha256"; echo "git_force_diff_exit=$?"
cp data/ns_materialized/snapshot.json "$O/forced-ns-snapshot.json"; cp data/pit_snapshot/snapshot.json "$O/forced-pit-snapshot.json"
git diff --stat dvc.lock

# ---------------- repo "identity": security-identity chain, dvc --no-scm ----------------
RI=$O/repo-identity; mkdir -p "$RI/code" "$RI/stages"
for d in security-identity alpaca-historical financial-data; do cp -a "$WT/blueprints/us-equities/$d" "$RI/code/$d"; done
cp "$H/stage.py" "$RI/stages/stage.py"; cp "$H/dvc-identity.yaml" "$RI/dvc.yaml"
cd "$RI"
dvc init -q --no-scm && dvc config core.analytics false && dvc config core.check_update false && dvc config core.site_cache_dir "$O/dvc-site-cache"
dvc_cycle identity
python stages/stage.py id-select --code code --ledger data/id_ledger --ledger-json data/id_ledger.json --out "$O/restored-rerun/id_select.json"; echo "restored_id_select_exit=$?"
cp -a data/id_ledger.json "$O/restored-rerun/"
dvc repro --force; echo "identity_repro_force_exit=$?"
find data out -type f | sort | xargs sha256sum > "$O/identity-post-force.sha256"
diff "$O/identity-pre-delete.sha256" "$O/identity-post-force.sha256"; echo "identity_force_diff_exit=$?"

# ---------------- project-local adapter arm: original worktree code, plain processes, no DVC ----------------
: ==== project-local arm
L=$O/local; mkdir -p "$L"; CODE=$WT/blueprints/us-equities; S=$H/stage.py
python "$CODE/nanosecond-replay/replay.py" materialize --source "$CODE/nanosecond-replay/fixture.json" --output "$L/ns_materialized" > "$L/ns_materialize.json"; echo "local_ns_materialize_exit=$?"
python "$S" ns-select --code "$CODE" --materialized "$L/ns_materialized" --manifest "$L/ns_materialize.json" --out "$L/ns_select.json"; echo "local_ns_select_exit=$?"
python "$S" ns-quarantine --code "$CODE" --materialized "$L/ns_materialized" --manifest "$L/ns_materialize.json" --out "$L/ns_quarantine.json"; echo "local_ns_quarantine_exit=$?"
python "$CODE/point-in-time/temporal_snapshot.py" snapshot --source "$CODE/point-in-time/fixture.json" --output "$L/pit_snapshot" > "$L/pit_snapshot.json"; echo "local_pit_snapshot_exit=$?"
python "$S" pit-select --code "$CODE" --materialized "$L/pit_snapshot" --manifest "$L/pit_snapshot.json" --out "$L/pit_select.json"; echo "local_pit_select_exit=$?"
python "$S" pit-quarantine --code "$CODE" --materialized "$L/pit_snapshot" --manifest "$L/pit_snapshot.json" --out "$L/pit_quarantine.json"; echo "local_pit_quarantine_exit=$?"
python "$S" id-capture --code "$CODE" --out-dir "$L/id_capture" --out "$L/id_capture.json"; echo "local_id_capture_exit=$?"
python "$S" id-quality --code "$CODE" --capture "$L/id_capture" --capture-json "$L/id_capture.json" --out-dir "$L/id_quality" --out "$L/id_quality.json"; echo "local_id_quality_exit=$?"
python "$S" id-ledger --code "$CODE" --quality "$L/id_quality" --quality-json "$L/id_quality.json" --out-dir "$L/id_ledger" --out "$L/id_ledger.json"; echo "local_id_ledger_exit=$?"
python "$S" id-select --code "$CODE" --ledger "$L/id_ledger" --ledger-json "$L/id_ledger.json" --out "$L/id_select.json"; echo "local_id_select_exit=$?"
(cd "$L" && find ns_materialized pit_snapshot id_capture id_quality id_ledger -type f | sort | xargs sha256sum) > "$O/local.sha256"
date -u +%FT%TZ
