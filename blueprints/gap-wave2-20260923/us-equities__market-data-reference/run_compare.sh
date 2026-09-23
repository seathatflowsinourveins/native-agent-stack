#!/usr/bin/env bash
# Gap 5 acceptance: reproduce the AAPL 25-session result, score second symbols, controls.
set -uo pipefail
WT=${WT:-$(cd "$(dirname "$0")/../../.." && pwd)}; cd "$WT"
B=blueprints/gap-wave2-20260923/us-equities__market-data-reference
RUN=$HOME/codex-ecosystem/state/authenticated-data-20260920/alpaca-run-1
RS=a59c6ed74e839ca43ee704033e207865ed938a22e4738afce22ec197e91b6bcd
LEAN=$HOME/codex-ecosystem/state/catalyst-dataset-readiness-20260920/corporate-actions/run-5/native-results.json
LS=b31c282c90367c3baf87232772fc78a7bc36a8c64229faa2ef86a9068e88b25b
PQ=$HOME/codex-ecosystem/state/broad-market-20260921/dataset/daily.parquet
LD=$HOME/.local/share/codex-ecosystem/tools/lean-985ef30-remediation/Data/equity/usa
DPY=$HOME/.local/share/codex-ecosystem/tools/sdk-env-baseline-20260922/bin/python3   # has duckdb 1.5.5
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
step() { echo "## $1"; shift; "$@" > "$T/out.json" 2> "$T/err.txt"; local rc=$?; echo "exit=$rc"; cat "$T/out.json"; [ -s "$T/err.txt" ] && tail -n 5 "$T/err.txt"; cp "$T/out.json" "$T/$STEP.json"; return 0; }
STEP=original step "original compare.py (AAPL, hard-coded)" python3 blueprints/us-equities/authenticated-data/compare.py --run "$RUN" --receipt-sha256 $RS --lean "$LEAN" --lean-sha256 $LS
STEP=multi_aapl step "compare_multi AAPL lean-probe vs alpaca-run" python3 $B/compare_multi.py --reference lean-probe:$LEAN,$LS --provider alpaca-run:$RUN,$RS --symbols AAPL --start 2020-08-03 --end 2020-09-04 --expect-sessions 25
echo "## equality of per-symbol result vs original (input_hashes excluded)"
python3 - "$T" <<'PY'
import json,sys
t=sys.argv[1]; a=json.load(open(t+"/original.json")); b=json.load(open(t+"/multi_aapl.json"))
a.pop("input_hashes"); r=b["results"]["AAPL"]
print(json.dumps({"identical": a == r, "keys_only_original": sorted(set(a)-set(r)), "keys_only_multi": sorted(set(r)-set(a))}))
PY
STEP=parquet_aapl step "AAPL lean-probe vs alpaca-parquet (broad-market store)" "$DPY" $B/compare_multi.py --reference lean-probe:$LEAN,$LS --provider alpaca-parquet:$PQ --symbols AAPL --start 2020-08-03 --end 2020-09-04 --expect-sessions 25
STEP=second_window step "second symbols IBM,SPY lean-daily vs alpaca-parquet, same 25-session window" "$DPY" $B/compare_multi.py --reference lean-daily:$LD --provider alpaca-parquet:$PQ --symbols IBM,SPY --start 2020-08-03 --end 2020-09-04 --expect-sessions 25
STEP=second_long step "IBM,SPY,AAPL lean-daily vs alpaca-parquet 2016-01-04..2021-03-31" "$DPY" $B/compare_multi.py --reference lean-daily:$LD --provider alpaca-parquet:$PQ --symbols IBM,SPY,AAPL --start 2016-01-04 --end 2021-03-31
# normalized-csv arm (provider-neutral export): built from public LEAN IBM data in a temp dir.
python3 - "$LD" "$T" <<'PY'
import sys, zipfile, io
from decimal import Decimal
ld, t = sys.argv[1], sys.argv[2]
rows = []
with zipfile.ZipFile(ld + "/daily/ibm.zip") as z:
    for line in io.TextIOWrapper(z.open(z.namelist()[0]), encoding="ascii"):
        s, *_rest = line.strip().split(","); c = _rest[3]
        d = f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
        if "2020-08-03" <= d <= "2020-09-04": rows.append((d, str(Decimal(c).scaleb(-4))))
for name, bump in [("clean", False), ("perturbed", True)]:
    with open(f"{t}/{name}.csv", "w") as f:
        f.write("symbol,session_date,close\n")
        for i, (d, c) in enumerate(rows):
            f.write(f"IBM,{d},{Decimal(c) + Decimal('0.01') if bump and i == 7 else c}\n")
PY
STEP=csv_clean step "normalized-csv positive control (IBM, unchanged)" python3 $B/compare_multi.py --reference lean-daily:$LD --provider normalized-csv:$T/clean.csv --symbols IBM --start 2020-08-03 --end 2020-09-04
STEP=csv_perturbed step "normalized-csv negative control (IBM, one close +0.01)" python3 $B/compare_multi.py --reference lean-daily:$LD --provider normalized-csv:$T/perturbed.csv --symbols IBM --start 2020-08-03 --end 2020-09-04
STEP=bad_count step "expect-sessions guard (IBM 24 expected, 25 present)" python3 $B/compare_multi.py --reference lean-daily:$LD --provider normalized-csv:$T/clean.csv --symbols IBM --start 2020-08-03 --end 2020-09-04 --expect-sessions 24
# Fix round 1 controls (Codex review): unavailable/empty reference and per-symbol action filtering.
echo "## fix-round controls"
python3 - "$B" <<'PY'
import json, sys, types
sys.path.insert(0, sys.argv[1]); import compare_multi as m
ref = m.Source("alpaca-run", "ref", bars_status="unavailable", reason="request_failed")
empty_provider = m.Source("normalized-csv", "provider")
print("unavailable_reference:", json.dumps(m.compare(ref, empty_provider, ["AAPL"])["AAPL"]["bars"]))
ok_ref = m.Source("lean-daily", "ref"); ok_ref.bars = {"IBM": {"2020-08-03": "1"}}
print("symbol_absent_from_reference:", json.dumps(m.compare(ok_ref, empty_provider, ["ZZZ"])["ZZZ"]["bars"]))
stages = {"bars": {"status": "complete", "rows": []}, "actions": {"status": "complete", "rows": [
    {"symbol": "IBM", "ex_date": "2020-08-07"}, {"symbol": "AAPL", "ex_date": "2019-01-01"}, {"symbol": "AAPL", "ex_date": "2020-08-07"}]}}
m.original.load_collector = lambda: types.SimpleNamespace(verify=lambda *_: stages)
s = m.alpaca_run(["unused", "unused"], {"AAPL"}, "2020-08-03", "2020-09-04")
print("filtered_action_rows:", json.dumps(s.actions["rows"]))
PY
