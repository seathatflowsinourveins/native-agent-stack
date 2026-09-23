#!/usr/bin/env python3
"""Build the storage-compute gap-wave-2 receipts from the committed
preregistrations and raw outputs, then derive results.json from the receipts.

Run from the repository root:
  python3 blueprints/gap-wave2-20260923/us-equities__storage-compute/build_receipts.py
"""
import hashlib
import json
import math
from pathlib import Path

E = Path("evidence/artifacts/gap-wave2-20260923/us-equities__storage-compute")
RAW = E / "raw"
H = "blueprints/gap-wave2-20260923/us-equities__storage-compute"
gaps = {g["index"]: g for g in json.loads((E / "inputs" / "gaps-input.json").read_text())["gaps"]}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
load = lambda p: json.loads(Path(p).read_text())


def prereg(i):
    p = E / "prereg" / f"{i}.json"
    d = load(p)
    d["file"] = str(p)
    d["file_sha256"] = sha(p)
    d["committed_in"] = "af80671 (before any check command ran)"
    f = E / "prereg" / f"{i}-fixround.json"
    if f.exists():
        fr = load(f)
        fr["file"] = str(f)
        fr["file_sha256"] = sha(f)
        fr["committed_in"] = "23c9902 (after round 1 and the Codex review, before any round-2 command ran)"
        d["fix_round"] = fr
    f2 = E / "prereg" / f"{i}-fixround2.json"
    if f2.exists():
        fr2 = load(f2)
        fr2["file"] = str(f2)
        fr2["file_sha256"] = sha(f2)
        fr2["committed_in"] = "1f234b9 (after the Codex re-review of 6155b51, before any round-3 command ran)"
        d["fix_round_2"] = fr2
    return d


def raw(*names):
    return [{"path": str(RAW / n), "sha256": sha(RAW / n)} for n in names]


def receipt(i, slug, **kw):
    g = gaps[i]
    r = {"id": f"us-equities__storage-compute-{i}-{slug}", "gap_index": i, "layer_id": "storage-compute",
         "catalog": "us-equities", "gap_text": g["text"],
         "gap_text_sha256": hashlib.sha256(g["text"].encode()).hexdigest(), "next_check": g["next_check"],
         "preregistration": prereg(i)}
    r.update(kw)
    path = E / f"{i}-{slug}.json"
    path.write_text(json.dumps(r, indent=2).replace(str(Path.home()) + "/", "$HOME/") + "\n")
    return path


# ------------------------------------------------------------------ gap 0 / gap 4 shared real-snapshot run
S1 = load(RAW / "real-snapshot-summary.json")          # round 1 (a0f57fa)
S = load(RAW / "real-snapshot-summary-r2.json")        # round 2: full ingest receipts + precision check


def snap_cmd(rnd):
    sfx = "-r2" if rnd == 2 else ""
    return ("$HOME/.cache/gap-wave2-20260923/storage-compute/venv-bench/bin/python "
            f"{H}/real_snapshot_checks.py --run-dir $HOME/.cache/gap-wave2-20260923/storage-compute/runs/real-snapshots{sfx} "
            "--gate-python $HOME/.cache/gap-wave2-20260923/storage-compute/venv-gate/bin/python "
            "--gate blueprints/us-equities/data/promotion_gate.py "
            "--snapshot alpaca-sip-20260922=$HOME/.local/state/native-agent-stack/alpaca-paper/snapshots/20260922/universe-daily.csv:"
            "$HOME/.local/state/native-agent-stack/alpaca-paper/snapshots/20260922/ingest-receipt.json "
            "--snapshot alpaca-sip-dryrun-20260922=$HOME/.local/state/native-agent-stack/alpaca-paper/trials/dryrun-20260922/universe-daily.csv:"
            "$HOME/.local/state/native-agent-stack/alpaca-paper/trials/dryrun-20260922/ingest-receipt.json "
            "--lean-daily $HOME/.local/share/codex-ecosystem/tools/lean-985ef30/Data/equity/usa/daily "
            f"--out {RAW}/real-snapshot-summary{sfx}.json   # round {rnd}; wrapped in $HOME/codex-ecosystem/bin/ecosystem-bounded-run (ECOSYSTEM_JOB_SECONDS=1200, MEMORY_MAX=4G)")


venv_cmds = [
    "uv venv --python $HOME/.local/share/codex-ecosystem/python/cpython-3.13-linux-x86_64-gnu/bin/python3.13 venv-gate && uv pip sync --python venv-gate/bin/python --require-hashes blueprints/us-equities/data/requirements.lock   # cwd $HOME/.cache/gap-wave2-20260923/storage-compute, UV_CACHE_DIR there",
    "uv venv --python ...python3.13 venv-bench && uv pip install --python venv-bench/bin/python duckdb==1.5.5 'pyiceberg[sql-sqlite,pyarrow]==0.12.0' pyarrow numpy pandas clickhouse-connect questdb 'psycopg[binary]' psutil",
]


def snap_line(name, e):
    g, pdq = e["gate"], e["parquet_duckdb"]
    q = pdq["queries"]
    rc = e["receipt"]
    return (f"{name}: copy sha256 {e['copy_sha256']} == ingest receipt snapshot_sha256 -> {e['copy_matches_receipt']}; "
            f"ingest receipt kind={rc.get('kind')} evidence_class={rc.get('evidence_class')} feed={rc.get('feed')} adjustment={rc.get('adjustment')} "
            f"fetched_at={rc.get('fetched_at_utc')} symbols={rc.get('symbols')} row_count={rc.get('row_count')} "
            f"symbols_missing={rc.get('symbols_missing', 'field absent')} coverage_problems={rc.get('coverage_problems', 'field absent')}; "
            f"gate status={g['status']} row_count={g['row_count']} failed_checks={g['failed_checks']} of {g['checks_total']}; "
            f"Parquet sha256 {pdq['parquet_sha256']} mode {pdq['parquet_mode']} writable={pdq['parquet_writable_after_chmod']}; "
            f"precision_loss_rows={pdq['precision_loss_rows']} (max price decimals in text {pdq['max_price_decimal_places_in_text']}; probe '1.23456' detected={pdq['precision_probe_1_23456_detected']}); "
            f"CSV-vs-Parquet EXCEPT ALL diffs {pdq['csv_minus_parquet_rows']}/{pdq['parquet_minus_csv_rows']}; "
            f"DuckDB {pdq['duckdb']}: rows={q['rows']} symbols={q['symbols']} sessions {q['first_session']}..{q['last_session']} "
            f"per-symbol {q['sessions_per_symbol_min']}-{q['sessions_per_symbol_max']} null_cells={q['null_cells']} "
            f"ohlc_inconsistent_rows={q['ohlc_inconsistent_rows']}; control gate status={e['detection_control']['gate']['status']} "
            f"failed={e['detection_control']['gate']['failed_checks']}")


alp = S["alpaca_snapshots"]
lean = S["lean"]
snap_results = ["Round 2 (primary):"] + [snap_line(k, v) for k, v in alp.items()]
snap_results.append("Round 1 (a0f57fa) gave the same gate status, row counts, snapshot hashes and control failures: "
                    + json.dumps({k: [v["gate"]["status"], v["copy_matches_receipt"], v["detection_control"]["gate"]["failed_checks"]] for k, v in S1["alpaca_snapshots"].items()}))
lean_results = [f"{k}: {len(v['tickers'])} tickers, gate status={v['gate']['status']} row_count={v['gate']['row_count']} "
                f"failed={v['gate']['failed_checks']}; precision_loss_rows={v['parquet_duckdb']['precision_loss_rows']}; DuckDB sessions {v['parquet_duckdb']['queries']['first_session']}.."
                f"{v['parquet_duckdb']['queries']['last_session']} ohlc_inconsistent_rows={v['parquet_duckdb']['queries']['ohlc_inconsistent_rows']}"
                for k, v in lean.items()]
gate_files = ["alpaca-sip-20260922-gate-result", "alpaca-sip-dryrun-20260922-gate-result", "alpaca-sip-20260922-control-gate-result",
              "alpaca-sip-dryrun-20260922-control-gate-result", "lean-five-252-gate-result", "lean-all-full-gate-result"]
snap_raw = raw("real-snapshot-summary-r2.json", "real-snapshot-stdout-r2.txt", *[f"{g}-r2.json" for g in gate_files],
               "real-snapshot-summary.json", "real-snapshot-stdout.txt", *[f"{g}.json" for g in gate_files])

receipt(0, "alpaca-snapshot-parquet-duckdb-gate",
        commands=venv_cmds + [snap_cmd(1), snap_cmd(2),
                              "curl -sL https://docs.alpaca.markets/docs/about-market-data-api   # public docs page, excerpt retained"],
        results=snap_results + [
            "Alpaca plan scope (docs excerpt, raw/alpaca-market-data-plans-excerpt.txt): 'The Basic plan serves as the default option for both Paper and Live trading accounts ... for equities only the IEX exchange ... Historical data timeframe Since 2016 ... Historical data limitation* latest 15 minutes' and 'all the standard plans are real time IEX or 15 mins delayed SIP'.",
            "Both snapshots were fetched after the 2026-09-22 session closed (21:55:59Z and 00:33:24Z), so every daily bar is older than the Basic plan's 15-minute historical SIP limitation."],
        outcome="advanced",
        remaining=["Fetch about 5 symbols x 1 year of Alpaca feed=iex daily bars (next_check's exact request) and record its licence scope: needs the paper credential file and a broker market-data call; owner sota-workflow-resolution.",
                   "Run the DuckDB catalyst query (catalyst-dataset join) against a bars snapshot; only the bars queries ran here."],
        evidence_class="local_integration",
        limits=["The Alpaca fetch was not run by this unit. The two real snapshots were written by the merged #84 ingest (blueprints/us-equities/data/ingest_snapshot.py, alpaca-py 0.44.0) on 2026-09-22/23 and read here read-only from the paper-trial state directory; the file hashes match their ingest receipts, which are retained whole in raw/real-snapshot-summary-r2.json.",
                    "Feed is sip, adjustment raw, 24 symbols x 20 sessions (480 rows), not feed=iex over one year.",
                    "The account's actual Alpaca data plan was not checked (no account call). The licence scope above is the public plan description, not an entitlement record.",
                    "No price row or price-derived value is committed; Parquet files stay in the private run directory. The per-symbol return aggregate is kept only as a hash.",
                    "Evidence class local_integration: licensed native market data from a retained ingest, processed locally."],
        raw_artifacts=snap_raw + raw("alpaca-market-data-plans-excerpt.txt"),
        checked_at=S["finished_at"])

receipt(4, "real-snapshot-promotion-gate",
        commands=venv_cmds[:1] + [snap_cmd(1), snap_cmd(2)],
        results=snap_results + lean_results + [
            "Detection method: the mutated control of each real snapshot (row 1 high set to close - 0.01; row 2 duplicated) fails exactly high_ge_max_open_close and unique_symbol_session, so the gate run here can detect the failures it reports absent on the unmodified snapshots. The precision check detects the probe value '1.23456'.",
            "The production ingest exists at base 41d39b3: blueprints/us-equities/data/ingest_snapshot.py (merged #84) wrote both snapshots; the retained ingest receipts (raw/real-snapshot-summary-r2.json, alpaca_snapshots.*.receipt) carry the fields quoted above."],
        outcome="settled",
        evidence_class="local_integration",
        limits=["Gate outputs are retained for real Alpaca SIP daily snapshots (feed sip, not the next_check's iex). SIP is the consolidated feed; the gate's checks do not depend on the feed.",
                "The Alpaca fetch arm was executed by the #84 ingest (2026-09-22/23), not by this unit; this unit reran the pinned gate in a freshly built hash-locked venv (twice) and retained its outputs and the snapshot hashes.",
                "blueprints/us-equities/data/README.md lines 119-124 still say no production ingest exists; that text is stale relative to #84 and was not edited here (outside this unit's paths).",
                "The LEAN arms use real AlgoSeek daily bars bundled with LEAN 985ef30 ('DATA PROVIDED BY ALGOSEEK / ALL RIGHTS RESERVED'); their observed_at is the LEAN commit time, not original availability. They are supplementary real-data runs, not a licensed production ingest.",
                "No snapshot rows are committed; only gate results (no prices), counts and hashes."],
        raw_artifacts=snap_raw,
        checked_at=S["finished_at"])

# ------------------------------------------------------------------ gap 6
V1 = load(RAW / "paired-receipt-verification.json")
V = load(RAW / "paired-receipt-verification-r2.json")
ctl2 = load(RAW / "paired-receipt-negative-controls-r2.json")
receipt(6, "paired-astra-claude-covered",
        commands=[f"python3 {H}/verify_paired_receipt.py .   # round 1 and round 2 (round 2 adds prompt reconstruction via run_worker.native_prompt)",
                  f"copy adoption/paired and blueprints/us-equities/research-runtime/run_worker.py to $T; printf ' ' >> $T/adoption/paired/astra.report.json; python3 {H}/verify_paired_receipt.py $T   # control 'bytes', exit 1 expected",
                  f"copy as above; append ' (edited)' to astra.report.json findings[0].claim and set the copied receipt's astra report_sha256 to the new file hash; python3 {H}/verify_paired_receipt.py $T   # control 'handoff', exit 1 expected"],
        results=[f"Round 2 verify_paired_receipt.py exit 0; all_pass={V['all_pass']}; checks={json.dumps(V['checks'])}",
                 f"research-pair window {V['research_pair_window_utc']}; models {V['models']}; usage astra_total_tokens={V['usage']['astra_total_tokens']} claude_total_tokens={V['usage']['claude_total_tokens']}",
                 f"file sha256: {json.dumps(V['file_sha256'])}; receipt sha256 {V['receipt_sha256']}",
                 "Round 2 controls: " + json.dumps(ctl2) + " (the handoff control shows the Claude prompt hash binds the accepted Astra report content, independent of the report-hash field).",
                 f"Round 1 (a0f57fa): all_pass={V1['all_pass']}; one-byte control failed " + (RAW / "paired-receipt-negative-control.txt").read_text().strip(),
                 "blueprints/us-equities/research-runtime/README.md opens with 'Later paired acceptance: native sign-in restored Codex readiness and the existing workflow completed fresh LEAN -> Dagu -> DuckDB -> Astra -> Claude ... See the paired receipt and native results (../../../adoption/paired/README.md).'"],
        outcome="covered_elsewhere",
        covered_by={"receipt": "adoption/paired/receipt.json", "id": "native-paired-adoption-20260919",
                    "kind": "native_model_e2e", "observed_at_utc": "2026-09-19T19:41:50Z"},
        evidence_class="source_review",
        limits=["No model was called in this wave. The covering run is the 2026-09-19 native pair (evidence class native_model_e2e in that receipt); this unit verified the committed receipt, its file hashes, status fields and reconstructed prompt hashes.",
                "blueprints/us-equities/research-runtime/receipt.json still carries paired_model_workflow_executed false for its own earlier run; that field is historical and was not edited.",
                "The gap-6 preregistration notes that an exploratory hash of the four files was taken before it was written; the scripted verification and controls ran after it."],
        raw_artifacts=raw("paired-receipt-verification-r2.json", "paired-receipt-negative-controls-r2.json",
                          "paired-receipt-verification.json", "paired-receipt-negative-control.txt"),
        checked_at="2026-09-23T05:59:00Z")

# ------------------------------------------------------------------ gaps 3 and 10 benchmark
STORES = ("duckdb", "clickhouse", "questdb", "iceberg")
B1 = {s: load(RAW / f"bench-{s}.json") for s in STORES}        # round 1 (a0f57fa)
B2 = {s: load(RAW / f"bench-r2-{s}.json") for s in STORES}     # round 2 (6155b51)
B = {s: load(RAW / f"bench-r3-{s}.json") for s in STORES}      # round 3 (primary; engine-level kill proof)
man = load(RAW / "bench-dataset-manifest.json")


def bench_cmd(s, rnd):
    tasks = "" if (s == "duckdb" and rnd == 1) else "ECOSYSTEM_JOB_TASKS_MAX=4096 "
    work = "bench/w-" if rnd == 1 else f"bench/r{rnd}/w-"
    out = f"bench/{s}.json" if rnd == 1 else f"bench/r{rnd}/{s}.json"
    return (f"ECOSYSTEM_JOB_SECONDS=1200 {tasks}ECOSYSTEM_JOB_MEMORY_HIGH=12G ECOSYSTEM_JOB_MEMORY_MAX=14G "
            f"$HOME/codex-ecosystem/bin/ecosystem-bounded-run $HOME/.cache/gap-wave2-20260923/storage-compute/venv-bench/bin/python {H}/bench.py run --store {s} "
            f"--data $HOME/.cache/gap-wave2-20260923/storage-compute/bench/data --work $HOME/.cache/gap-wave2-20260923/storage-compute/{work}{s} "
            f"--out $HOME/.cache/gap-wave2-20260923/storage-compute/{out}"
            + (" --ch-bin $HOME/.cache/gap-wave2-20260923/storage-compute/clickhouse-26.8.11.7/clickhouse-common-static-26.8.11.7/usr/bin/clickhouse" if s == "clickhouse" or rnd == 2 else "")
            + (" --qdb-home $HOME/.cache/gap-wave2-20260923/storage-compute/questdb-10.0.1/questdb-10.0.1-rt-linux-x86-64" if s == "questdb" or rnd == 2 else "")
            + f"   # round {rnd}" + ("; default 256-task cgroup limit" if tasks == "" else ""))


install_cmds = [
    "curl -fsSL -o questdb-10.0.1-rt-linux-x86-64.tar.gz https://github.com/questdb/questdb/releases/download/10.0.1/questdb-10.0.1-rt-linux-x86-64.tar.gz   # 98,016,278 bytes; sha256 38a736c253c3ac4c795aca1db35d6bf6f479e2788fcd88b9001693844682db86 equals the GitHub asset digest",
    "curl -fsSL -o clickhouse-common-static-26.8.11.7-amd64.tgz https://github.com/ClickHouse/ClickHouse/releases/download/v26.8.11.7-lts/clickhouse-common-static-26.8.11.7-amd64.tgz && sha512sum -c clickhouse-common-static-26.8.11.7-amd64.tgz.sha512   # 235,732,763 bytes, 'OK'; both downloads inside ecosystem-bounded-run",
] + venv_cmds[1:] + [f"$HOME/codex-ecosystem/bin/ecosystem-bounded-run $HOME/.cache/gap-wave2-20260923/storage-compute/venv-bench/bin/python {H}/bench.py gen --out $HOME/.cache/gap-wave2-20260923/storage-compute/bench/data"]
bench_cmds = install_cmds + [bench_cmd(s, 1) for s in STORES] + [bench_cmd(s, 2) for s in STORES] + [bench_cmd(s, 3) for s in STORES] + [
    f"$HOME/.cache/gap-wave2-20260923/storage-compute/venv-bench/bin/python {H}/kill_verifier_control.py $HOME/.cache/gap-wave2-20260923/storage-compute/ctl/bench.duckdb 30   # on a copy of the round-2 DuckDB smoke database"]


def r(x, n=3):
    return None if x is None else round(x, n)


def same_rows(a, b):
    if len(a) != len(b):
        return False
    for ra, rb in zip(a, b):
        if len(ra) != len(rb):
            return False
        for x, y in zip(ra, rb):
            if isinstance(x, float) or isinstance(y, float):
                if not math.isclose(float(x), float(y), rel_tol=1e-9, abs_tol=1e-9):
                    return False
            elif x != y:
                return False
    return True


def store_summary(s, d):
    L = d["steps"]["load"]
    out = {"versions": d["versions"], "loadavg_start_end": [d["host"]["loadavg_start"], d["host"]["loadavg_end"]],
           "bulk_load_s": r(L["seconds"]), "bulk_load_rows_per_s": round(L["rows_per_s"]), "row_count_ok": L["row_count_ok"],
           "query_median_s": {q: r(v["median_s"], 4) for q, v in d["queries"].items()}}
    if s == "questdb":
        out["bulk_load_until_visible_rows_per_s"] = round(L["rows_per_s_until_visible"])
    phases = {}
    for c in d["concurrency"]:
        k = f"{c['phase']}{c['clients']}"
        phases[k] = {"write_p50_p95_p99_s": [r((c["write_latency_s"] or {}).get(p), 4) for p in ("p50", "p95", "p99")] if c["write_latency_s"] else None,
                     "read_p50_p95_p99_s": [r((c["read_latency_s"] or {}).get(p), 4) for p in ("p50", "p95", "p99")] if c["read_latency_s"] else None,
                     "write_batches_ok": c["write_batches_ok"], "write_errors": c["write_errors"], "read_errors": c["read_errors"],
                     "workers_lost": c.get("workers_lost"),
                     "rows_visible_ok": (c.get("rows_visible_after_phase") == c.get("rows_expected")) if c["writers"] else None,
                     "wall_rows_per_s": round(c["write_rows_per_s"]) if c["writers"] else None}
        if s == "iceberg":
            phases[k]["pyiceberg_internal_commit_retries"] = c["pyiceberg_internal_commit_retries"]
            phases[k]["commit_failed_after_internal_retries_then_harness_retry"] = c["commit_conflicts_retried"]
    out["phases"] = phases
    out["kill_recover"] = d["kill_recover"]
    out["footprint_bytes"] = {"after_load": d["footprint_after_load_bytes"], "after_recovery": d["footprint_after_recovery_bytes"]}
    out["memory"] = {"server_after_load": d.get("mem_after_load"), "server_after_concurrency": d.get("mem_after_concurrency"),
                     "server_idle_before_load": d.get("mem_idle"), "harness_maxrss_kB": d["harness_maxrss_kB"]}
    if s == "duckdb":
        out["second_process"] = d["duckdb_second_process"]
    return out


summ = {s: store_summary(s, d) for s, d in B.items()}
full_agree = {s: {q: same_rows(B[s]["queries"][q]["canonical_rows"], B["duckdb"]["queries"][q]["canonical_rows"]) for q in ("Q1", "Q2", "Q3", "Q4")} for s in STORES}
agree = all(all(v.values()) for v in full_agree.values())
rounds = {s: {f"round{i}": {"bulk_load_rows_per_s": round(X[s]["steps"]["load"]["rows_per_s"]),
                            "query_median_s": {q: r(v["median_s"], 4) for q, v in X[s]["queries"].items()},
                            "loadavg_start": X[s]["host"]["loadavg_start"][0]} for i, X in ((1, B1), (2, B2))} for s in STORES}
full_agree_r2 = all(same_rows(B2[s]["queries"][q]["canonical_rows"], B2["duckdb"]["queries"][q]["canonical_rows"]) for s in STORES for q in ("Q1", "Q2", "Q3", "Q4"))
round1 = {s: rounds[s]["round1"] for s in STORES}
ctl = load(RAW / "kill-verifier-control.json")
bench_raw = raw("bench-dataset-manifest.json", *[f"bench-r3-{s}.json" for s in STORES], *[f"bench-r3-{s}.stdout.txt" for s in STORES],
                *[f"bench-r2-{s}.json" for s in STORES], *[f"bench-r2-{s}.stdout.txt" for s in STORES],
                *[f"bench-{s}.json" for s in STORES], *[f"bench-{s}.stdout.txt" for s in STORES],
                "bench-clickhouse.attempt1-tasksmax256.stdout.txt")
la3 = [B[s]["host"]["loadavg_start"][0] for s in STORES]
la2 = [B2[s]["host"]["loadavg_start"][0] for s in STORES]
la1 = [B1[s]["host"]["loadavg_start"][0] for s in STORES]
common_limits = [
    f"Three runs per store (round 1 at a0f57fa, round 2 after the first review, round 3 after the second review) on a shared WSL2 host (24 CPUs) while other sessions ran heavy jobs; 1-minute load average at store start {min(la1):.0f}-{max(la1):.0f} / {min(la2):.0f}-{max(la2):.0f} / {min(la3):.0f}-{max(la3):.0f} in rounds 1/2/3. Absolute numbers are noisy (DuckDB bulk load {rounds['duckdb']['round1']['bulk_load_rows_per_s']} / {rounds['duckdb']['round2']['bulk_load_rows_per_s']} / {summ['duckdb']['bulk_load_rows_per_s']} rows/s across rounds); no confidence intervals.",
    "Python harness: ClickHouse via clickhouse-connect HTTP, QuestDB via ILP/HTTP (questdb 5.0.0 client) and /exec, pyiceberg scans materialised to Arrow with pyarrow compute. Client serialisation is inside every latency. Phase wall_rows_per_s includes spawn start-up for process-based clients (not for DuckDB threads); per-batch percentiles do not.",
    "Load paths differ by store's native client: DuckDB read_parquet CTAS, ClickHouse one sequential Parquet HTTP insert per file, QuestDB ILP dataframe flushes of 100k rows, pyiceberg one append per 1M-row file. ClickHouse loaded far below the preregistered 'tens of millions rows/s' expectation with this single sequential client.",
    "DuckDB concurrency is in-process threads (one cursor each) because a second process cannot open the file while a writer holds it (retained IOException, including for a read_only second process).",
    "Retained failed attempt: the first round-1 ClickHouse run under the default 256-task cgroup limit lost its writer process ('std::system_error: Resource temporarily unavailable') and hung; it was stopped, its data deleted, and the store rerun with ECOSYSTEM_JOB_TASKS_MAX=4096 (raw/bench-clickhouse.attempt1-tasksmax256.stdout.txt). A dead-worker guard was added to the harness before the rerun.",
    "Data are synthetic fixed-seed minute bars (seed 20260923, 500 symbols x 100,000 minutes = 50,000,000 rows, combined sha256 " + man["combined_sha256"] + "); the dataset itself stays in the private cache, only its manifest is committed.",
    f"Round 1 compared only aggregate query digests (Codex review finding); rounds 2 and 3 compare full canonical Q1-Q4 result rows (round 2 agreement: {full_agree_r2}). Round-1 kill checks were aggregate only; round 2 added per-batch verification; round 3 added the engine-call marker that proves an engine-level write was interrupted (second Codex review finding). Round 3 is primary.",
]

res3 = [f"Dataset: {man['rows']} rows, {len(man['files'])} Zstandard Parquet files, combined sha256 {man['combined_sha256']}.",
        f"Round 3 full-row cross-store agreement on Q1-Q4 (keys and integer counts exact, floats rel_tol 1e-9) against DuckDB: {json.dumps(full_agree)} -> {agree}."]
for s, v in summ.items():
    res3.append(f"{s} {json.dumps(v['versions'])} (round 3): bulk load {v['bulk_load_s']} s = {v['bulk_load_rows_per_s']} rows/s (row_count_ok {v['row_count_ok']}); "
                f"query medians {json.dumps(v['query_median_s'])}; writers-only W1/W4/W8 batch p50/p95/p99 s "
                f"{[v['phases'][k]['write_p50_p95_p99_s'] for k in ('W1', 'W4', 'W8')]}, errors {[v['phases'][k]['write_errors'] for k in ('W1', 'W4', 'W8')]}; "
                f"readers-only R1/R4/R8 Q2 p50/p95/p99 s {[v['phases'][k]['read_p50_p95_p99_s'] for k in ('R1', 'R4', 'R8')]}; "
                f"earlier rounds: {json.dumps(rounds[s])}")
res3.append("DuckDB second process while the harness holds the file: " + summ["duckdb"]["second_process"]["second_writer_process"][:160])
ic = summ["iceberg"]["phases"]
res3.append("pyiceberg SqlCatalog concurrent appends (round 3): internal commit retries W1/W4/W8 = "
            + str([ic[k]["pyiceberg_internal_commit_retries"] for k in ("W1", "W4", "W8")])
            + ", CommitFailedException after pyiceberg's retries then retried by the harness = "
            + str([ic[k]["commit_failed_after_internal_retries_then_harness_retry"] for k in ("W1", "W4", "W8")])
            + f"; W8 batches ok {ic['W8']['write_batches_ok']}, rows visible ok {ic['W8']['rows_visible_ok']}.")

receipt(3, "four-store-throughput-concurrency",
        commands=bench_cmds[:-1],
        results=res3, outcome="settled", evidence_class="local_integration",
        store_summaries={s: {k: v[k] for k in ("versions", "bulk_load_s", "bulk_load_rows_per_s", "query_median_s", "phases")} | {"earlier_rounds": rounds[s]} for s, v in summ.items()},
        limits=common_limits,
        raw_artifacts=bench_raw, checked_at=max(d["finished_at"] for d in B.values()))

res10 = [f"Representative volume: {man['rows']} fixed-seed OHLCV rows (about 40M rows is 8,000 US symbols x 20 years of daily bars; this is the same order).",
         f"Round 3 full-row cross-store agreement on Q1-Q4: {agree}; round 2: {full_agree_r2}."]
for s, v in summ.items():
    k = v["kill_recover"]
    res10.append(f"{s} (round 3): mixed M1/M4/M8 writer batch p50/p95/p99 s {[v['phases'][x]['write_p50_p95_p99_s'] for x in ('M1', 'M4', 'M8')]}, "
                 f"reader Q2 p50/p95/p99 s {[v['phases'][x]['read_p50_p95_p99_s'] for x in ('M1', 'M4', 'M8')]}, errors w/r "
                 f"{[(v['phases'][x]['write_errors'], v['phases'][x]['read_errors']) for x in ('M1', 'M4', 'M8')]}; "
                 f"kill: SIGKILL {k['killed']} while batch(es) {k['inflight_batches_at_kill']} were inside the engine call for {json.dumps({b: r(t, 4) for b, t in k['engine_call_elapsed_at_kill_s'].items()})} s "
                 f"(median acknowledged engine call {r(k['median_engine_call_s_acked'], 4)} s; engine_interrupted_proven {k['engine_interrupted_proven']}; acks after kill time {k['acks_after_kill_time']}), "
                 f"{k['acked_batches']} acknowledged batches -> acked batches failing per-batch verification {k['acked_batches_failing_verification']}, "
                 f"in-flight state {json.dumps(k['inflight_state_after_recovery'])}, unexpected batch indices {k['unexpected_batch_indices']}, "
                 f"restart/reopen through first recovery query {r(k['restart_or_reopen_through_first_query_s'], 4)} s (server ready {r(k['server_ready_s'], 4)} s); "
                 f"disk after load {v['footprint_bytes']['after_load']} B, after recovery {v['footprint_bytes']['after_recovery']} B; memory {json.dumps(v['memory'])}")
ik = summ["iceberg"]["kill_recover"]
res10.append("pyiceberg orphan data files (round 3): " + json.dumps(ik["iceberg_files_before_kill"])
             + " before the kill, equal to the " + str(sum(ic[x]["commit_failed_after_internal_retries_then_harness_retry"] for x in ic))
             + " appends that raised CommitFailedException and were rewritten by the harness retry; " + str(ik["orphan_data_files_added_by_kill"]) + " added by the kill.")
res10.append("Detection method: the writer fsyncs 'S b t' before client-side preparation, writes 'I b t' immediately before the engine call (DuckDB INSERT, clickhouse-connect insert_arrow, QuestDB Sender.flush, pyiceberg Table.append) and fsyncs 'A b t' after it returns; the kill fires only when the last marker is 'I' and at least 25% of the median acknowledged engine-call duration has elapsed, so the process was inside the engine call at the kill. After recovery every batch index of symbol KILL is checked for 10,000 rows, 10,000 distinct timestamps and the deterministic expected sum(volume). Control (raw/kill-verifier-control.json): deleting acknowledged batch 5 and duplicating batch 6 on a copy leaves the total at "
             + str(ctl["kill_rows_after_mutation"]) + " rows, so the round-1 aggregate check still passes (" + str(ctl["round1_aggregate_check_passes"]) + "), while the round-2 check flags batches " + str(ctl["round2_failing_batches"]) + ".")
res10.append("QuestDB's restart_or_reopen_through_first_query_s includes a fixed 3.0 s settle sleep after WAL visibility; server_ready_s + questdb_wal_visible_after_s = "
             + str(r(summ["questdb"]["kill_recover"]["server_ready_s"] + summ["questdb"]["kill_recover"]["questdb_wal_visible_after_s"], 3)) + " s.")
receipt(10, "four-store-latency-recovery-footprint",
        commands=bench_cmds,
        results=res10, outcome="settled", evidence_class="local_integration",
        store_summaries={s: {k: v[k] for k in ("kill_recover", "footprint_bytes", "memory")} | {"mixed_phases": {x: v["phases"][x] for x in ("M1", "M4", "M8")}} for s, v in summ.items()},
        limits=common_limits + [
            "Recovery is process kill (SIGKILL) only: unsynced data in the OS page cache survives it, so power loss, disk failure and fsync policy are not tested.",
            "One kill per store per round; the in-flight batch was absent after recovery in every store, so the 'in-flight batch committed but unacknowledged' path was not observed.",
            "Memory for embedded stores (DuckDB, pyiceberg) is the harness process ru_maxrss, which includes Python, pyarrow and the dataset reads; server stores report the server process VmRSS/VmHWM from /proc (ClickHouse run with CLICKHOUSE_WATCHDOG_ENABLE=0 so the sampled pid is the server). The preregistered expectation that server RSS 'far exceeds' embedded RSS did not hold.",
            "Operational cost is proxied by disk bytes and RSS only; no CPU-hours, licence or hosting cost was measured."],
        raw_artifacts=bench_raw + raw("kill-verifier-control.json"), checked_at=max(d["finished_at"] for d in B.values()))

# ------------------------------------------------------------------ results.json derived from receipts
results = {}
for p in sorted(E.glob("[0-9]*-*.json")):
    d = load(p)
    results[str(d["gap_index"])] = {"outcome": d["outcome"], "receipt": p.name}
(E / "results.json").write_text(json.dumps(dict(sorted(results.items(), key=lambda x: int(x[0]))), indent=2) + "\n")
print(json.dumps(results))
