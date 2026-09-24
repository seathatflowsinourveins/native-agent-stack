#!/usr/bin/env bash
# Gaps 0/10: Grype 0.119.0 on the exact 2026-09-19 equity-worker-sdk Syft SBOM,
# with two positive controls on the same isolated database. The database was
# downloaded once into $C/grypedb (network, ~2.1 GB unpacked); this script runs
# offline against it. Nothing outside $C is written.
set -uo pipefail
C=${C:-$HOME/.cache/gap-wave2-20260923/security-supply-chain}
SBOM=${SBOM:-$HOME/codex-ecosystem/state/supply-chain-20260919/inventory/runtime.syft.json}
GRYPE=${GRYPE:-$HOME/.local/share/codex-ecosystem/tools/grype-0.119.0/grype}
OUT=$C/work/grype-sdk; mkdir -p "$OUT"
export GRYPE_DB_CACHE_DIR=$C/grypedb GRYPE_DB_AUTO_UPDATE=false GRYPE_CHECK_FOR_APP_UPDATE=false
LOG=$OUT/exits.log; : > "$LOG"
run() { local label=$1; shift; "$@"; local rc=$?; echo "$label exit=$rc" | tee -a "$LOG"; }

sha256sum "$SBOM" | tee -a "$LOG"
run db-status "$GRYPE" db status -o json > "$OUT/db-status.json"
run sdk-json "$GRYPE" "sbom:$SBOM" -o json --file "$OUT/sdk.grype.json" 2> "$OUT/sdk.stderr"
run sdk-cdx "$GRYPE" "sbom:$SBOM" -o cyclonedx-json --file "$OUT/sdk.grype.cdx.json" 2>> "$OUT/sdk.stderr"
# Positive control 1: the same SBOM with requests' version changed to 2.19.0 (known CVEs).
python3 - "$SBOM" "$OUT/sdk-mutated.syft.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1])); n = 0
for a in d["artifacts"]:
    if a["name"] == "requests":
        old = a["version"]; a["version"] = "2.19.0"
        a["purl"] = a["purl"].replace("@" + old, "@2.19.0"); n += 1
json.dump(d, open(sys.argv[2], "w"))
print("mutated requests artifacts:", n)
EOF
run mutated "$GRYPE" "sbom:$OUT/sdk-mutated.syft.json" -o json --file "$OUT/mutated.grype.json" 2> "$OUT/mutated.stderr"
# Positive control 2: bare PURLs known to be vulnerable.
printf 'pkg:pypi/requests@2.19.0\npkg:pypi/urllib3@1.24.1\n' > "$OUT/positive.purls"
run purls "$GRYPE" "purl:$OUT/positive.purls" -o json --file "$OUT/positive.grype.json" 2> "$OUT/positive.stderr"
python3 - "$OUT" "$SBOM" <<'EOF' | tee -a "$LOG"
import json, sys, collections
o, sbom = sys.argv[1], sys.argv[2]
s = json.load(open(sbom))
print("sbom artifacts:", len(s["artifacts"]), collections.Counter(a["type"] for a in s["artifacts"]))
for k in ("openai", "openai-codex", "exchange-calendars"):
    print("sbom has", k, [a["version"] for a in s["artifacts"] if a["name"] == k])
cdx = json.load(open(f"{o}/sdk.grype.cdx.json"))
print("grype cdx components by type:", collections.Counter(c["type"] for c in cdx.get("components", [])))
for f in ("sdk", "mutated", "positive"):
    d = json.load(open(f"{o}/{f}.grype.json"))
    db = d["descriptor"]["db"]["status"]
    print(f, "matches:", len(d["matches"]), "db built:", db["built"], "schema:", db["schemaVersion"],
          "ids:", sorted({m["vulnerability"]["id"] for m in d["matches"]})[:8])
EOF
