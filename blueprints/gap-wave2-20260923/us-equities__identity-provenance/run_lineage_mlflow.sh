#!/usr/bin/env bash
# Gap-wave-2 identity-provenance gap 5: OpenLineage file transport + MLflow log_input, emit then fresh-process readback.
# The core spec was fetched once, before this run, with: curl -sS -o $C/spec/OpenLineage-2-0-2.json https://openlineage.io/spec/2-0-2/OpenLineage.json
# Usage: run_lineage_mlflow.sh OUTDIR (must not exist). Both phases run in a user+network namespace (unshare -rn).
set -u
H=$(cd "$(dirname "$0")" && pwd)
C=$HOME/.cache/gap-wave2-20260923/identity-provenance
PY=$C/venv-mlflow/bin/python
O=$1; mkdir "$O" || exit 1
mkdir -p "$O/home"; export HOME="$O/home" XDG_CONFIG_HOME="$O/home"/.config XDG_CACHE_HOME="$O/home"/.cache MLFLOW_DISABLE_TELEMETRY=true DO_NOT_TRACK=1
export MLFLOW_DISABLE_AGENT_HINT=1
unset OPENLINEAGE_URL OPENLINEAGE_CONFIG OPENLINEAGE_API_KEY MLFLOW_TRACKING_URI
exec > >(tee "$O/run.log") 2>&1
set -x
date -u +%FT%TZ
# network-namespace probe: must fail inside, so a network call by either library would fail too
unshare -rn "$PY" -c 'import socket
try:
    socket.create_connection(("1.1.1.1", 53), timeout=2); print("network_reachable")
except OSError as e:
    print("network_blocked", type(e).__name__)'
unshare -rn "$PY" "$H/lineage_mlflow.py" emit --work "$O/work"; echo "emit_exit=$?"
unshare -rn "$PY" "$H/lineage_mlflow.py" readback --work "$O/work" --spec "$C/spec/OpenLineage-2-0-2.json"; echo "readback_exit=$?"
cat "$O/work/openlineage-events.ndjson" | head -c 20000
date -u +%FT%TZ
