#!/usr/bin/env bash
# Fix round 4 (preregistration-fixround4.json L5.3): rerun the hardened lineage verifier on the fix-round-3 inputs.
set -uo pipefail
C="$HOME/.cache/gap-wave2-20260923/identity-provenance"
O="$C/runs/lineage-verify-fix4"; mkdir -p "$O"
{
  date -u +%FT%TZ
  set -x
  unshare -rn "$C/venv-mlflow/bin/python" blueprints/gap-wave2-20260923/us-equities__identity-provenance/verify_lineage_fixround3.py \
    --original "$C/runs/lineage-fix-20260923T053153Z/work/openlineage-events.ndjson" \
    --expected-source-sha256 6356b077266baba83804538bfadab91a5a467e31e170c292b4c6d5c9aca07d9f \
    --published evidence/artifacts/gap-wave2-20260923/us-equities__identity-provenance/raw/lineage/work__openlineage-events.ndjson \
    --spec "$C/spec/OpenLineage-2-0-2.json" > "$O/verify.json"
  echo "verify_exit=$?"
  set +x
  date -u +%FT%TZ
} > "$O/run.log" 2>&1
