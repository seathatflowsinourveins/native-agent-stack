#!/usr/bin/env bash
# Gap-wave-2 identity-provenance gap 0, fix round 3: corrected C0.3 full-tree restore (preregistration-fixround3.json, G0.3a-e).
# Usage: run_c03_fixround3.sh OUTDIR   (OUTDIR must not exist; the scratch git+DVC repo is created there)
set -u
H=$(cd "$(dirname "$0")" && pwd)
WT=$(cd "$H/../../.." && pwd)
C=$HOME/.cache/gap-wave2-20260923/identity-provenance
export PATH="$C/venv-core/bin:$PATH"
O=$1; mkdir "$O" || exit 1
mkdir -p "$O/home"; export HOME="$O/home" XDG_CONFIG_HOME="$O/home"/.config XDG_CACHE_HOME="$O/home"/.cache DVC_NO_ANALYTICS=1 GIT_CONFIG_NOSYSTEM=1
exec > >(tee "$O/run.log") 2>&1
set -x
date -u +%FT%TZ
dvc --version; git --version
tree_list() { find data out -type f | sort | xargs sha256sum > "$O/$1.sha256"; wc -l < "$O/$1.sha256"; }
R=$O/repo-git; mkdir -p "$R/code" "$R/stages"
for d in nanosecond-replay point-in-time financial-data; do cp -a "$WT/blueprints/us-equities/$d" "$R/code/$d"; done
cp "$H/stage.py" "$R/stages/stage.py"; cp "$H/dvc.yaml" "$R/dvc.yaml"
cd "$R"
git init -q && git config user.email gap-wave2@local && git config user.name gap-wave2
dvc init -q && dvc config core.analytics false && dvc config core.check_update false && dvc config core.site_cache_dir "$O/dvc-site-cache" && git add -A && git commit -q -m 'code, stage driver and dvc.yaml'
: ==== G0.3a dvc repro, commit lock and gitignores, second repro
dvc repro; echo "repro1_exit=$?"
git add -A && git commit -q -m 'dvc.lock and .gitignore after first repro'; git ls-files data out; git status --short
dvc repro; echo "repro2_exit=$?"
dvc status; echo "status_exit=$?"
tree_list pre-delete
: ==== G0.3b as written: rm -rf data out, dvc checkout only
chmod -R u+w data; rm -rf data out
dvc checkout; echo "b_checkout_exit=$?"
tree_list b-post-checkout
diff "$O/pre-delete.sha256" "$O/b-post-checkout.sha256"; echo "b_diff_exit=$?"
: ==== G0.3c rm -rf data out, git checkout of the gitignores, dvc checkout
chmod -R u+w data; rm -rf data out
git checkout -- data/.gitignore out/.gitignore; echo "c_git_checkout_exit=$?"
dvc checkout; echo "c_checkout_exit=$?"
tree_list c-post-checkout
diff "$O/pre-delete.sha256" "$O/c-post-checkout.sha256"; echo "c_diff_exit=$?"
dvc status; echo "c_status_exit=$?"
: ==== G0.3d delete only the eight DVC outs declared in dvc.yaml
chmod -R u+w data
rm -rf data/ns_materialized data/ns_materialize.json data/pit_snapshot data/pit_snapshot.json out/ns_select.json out/ns_quarantine.json out/pit_select.json out/pit_quarantine.json
find data out -type f | sort
dvc checkout; echo "d_checkout_exit=$?"
tree_list d-post-checkout
diff "$O/pre-delete.sha256" "$O/d-post-checkout.sha256"; echo "d_diff_exit=$?"
dvc status; echo "d_status_exit=$?"
: ==== G0.3e detector control: one-byte overwrite, then dvc checkout --force
F=data/ns_materialized/observations.parquet
ls -l "$F"; chmod u+w "$F"; rm -f "$F.tmp"; cp "$F" "$F.tmp"; rm -f "$F"; mv "$F.tmp" "$F"
printf 'X' | dd of="$F" bs=1 seek=100 conv=notrunc status=none; echo "e_tamper_exit=$?"
tree_list e-tampered
diff "$O/pre-delete.sha256" "$O/e-tampered.sha256"; echo "e_tamper_diff_exit=$?"
dvc status; echo "e_status_exit=$?"
dvc checkout --force; echo "e_force_checkout_exit=$?"
tree_list e-post-force-checkout
diff "$O/pre-delete.sha256" "$O/e-post-force-checkout.sha256"; echo "e_restore_diff_exit=$?"
dvc status; echo "e_status_after_restore_exit=$?"
date -u +%FT%TZ
