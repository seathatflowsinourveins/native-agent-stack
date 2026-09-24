#!/usr/bin/env bash
# Gap-wave-2 identity-provenance gap 4: run the four store arms on one materialized replay fixture.
# Usage: run_store_arms.sh OUTDIR   (OUTDIR must not exist). Preregistration: preregistration.json gap "4".
set -u
H=$(cd "$(dirname "$0")" && pwd)
WT=$(cd "$H/../../.." && pwd)
C=$HOME/.cache/gap-wave2-20260923/identity-provenance
O=$1; mkdir "$O" || exit 1
mkdir -p "$O/home"; export HOME="$O/home" XDG_CONFIG_HOME="$O/home"/.config XDG_CACHE_HOME="$O/home"/.cache DVC_NO_ANALYTICS=1 GIT_CONFIG_NOSYSTEM=1
exec > >(tee "$O/run.log") 2>&1
set -x
date -u +%FT%TZ
"$C/venv-core/bin/python" "$WT/blueprints/us-equities/nanosecond-replay/replay.py" materialize --source "$WT/blueprints/us-equities/nanosecond-replay/fixture.json" --output "$O/fixture"; echo "fixture_exit=$?"
(cd "$O/fixture" && sha256sum source.json observations.parquet universe.parquet snapshot.json)
for arm in baseline:core dvc:core iceberg:iceberg arctic:arctic; do
  name=${arm%%:*}; venv=${arm##*:}
  PATH="$C/venv-$venv/bin:$PATH" timeout 900 "$C/venv-$venv/bin/python" "$H/store_arms.py" "$name" --fixture "$O/fixture" --work "$O/work-$name" --out "$O/$name.json"; echo "${name}_exit=$?"
done
date -u +%FT%TZ
: ==== repeatability of the two-writer result with 30 appends per writer, two repetitions per arm
for rep in 1 2; do
  for arm in baseline:core dvc:core iceberg:iceberg arctic:arctic; do
    name=${arm%%:*}; venv=${arm##*:}
    PATH="$C/venv-$venv/bin:$PATH" timeout 900 "$C/venv-$venv/bin/python" "$H/store_arms.py" "$name" --fixture "$O/fixture" --work "$O/conc30-$name-$rep" --out "$O/conc30-$name-$rep.json" --only-concurrency 30; echo "conc30_${name}_${rep}_exit=$?"
  done
done
date -u +%FT%TZ
