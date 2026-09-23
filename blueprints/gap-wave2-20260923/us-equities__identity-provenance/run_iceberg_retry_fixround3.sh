#!/usr/bin/env bash
# Gap-wave-2 identity-provenance gap 4, fix round 3 (H4.2): supplementary Iceberg two-writer run, n=30 x2, complete stderr retained.
# Usage: run_iceberg_retry_fixround3.sh OUTDIR (must not exist). Preregistration: preregistration-fixround3.json gap "4".
set -u
H=$(cd "$(dirname "$0")" && pwd)
WT=$(cd "$H/../../.." && pwd)
C=$HOME/.cache/gap-wave2-20260923/identity-provenance
O=$1; mkdir "$O" || exit 1
mkdir -p "$O/home"; export HOME="$O/home" XDG_CONFIG_HOME="$O/home"/.config XDG_CACHE_HOME="$O/home"/.cache
exec > >(tee "$O/run.log") 2>&1
set -x
date -u +%FT%TZ
"$C/venv-core/bin/python" "$WT/blueprints/us-equities/nanosecond-replay/replay.py" materialize --source "$WT/blueprints/us-equities/nanosecond-replay/fixture.json" --output "$O/fixture"; echo "fixture_exit=$?"
for rep in 1 2; do
  PATH="$C/venv-iceberg/bin:$PATH" timeout 900 "$C/venv-iceberg/bin/python" "$H/store_arms.py" iceberg --fixture "$O/fixture" --work "$O/conc30-iceberg-$rep" --out "$O/conc30-iceberg-$rep.json" --only-concurrency 30; echo "conc30_iceberg_${rep}_exit=$?"
  "$C/venv-core/bin/python" -c 'import json,sys; c=json.load(open(sys.argv[1]))["concurrent_writers"]; print(json.dumps(c["retry_summary_full_stderr"]), c["rows_lost_after_reported_success"], c["writer_error_counts"])' "$O/conc30-iceberg-$rep.json"
done
date -u +%FT%TZ
