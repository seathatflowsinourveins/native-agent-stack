"""Read-only snapshot of a promptfoo sqlite store: evals and per-result ids/timestamps."""
import json, sqlite3, sys
con = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
out = {"tables": sorted(tables)}
if "evals" in tables:
    cols = [r[1] for r in con.execute("pragma table_info(evals)")]
    keep = [c for c in ("id", "created_at", "is_redteam") if c in cols]
    out["evals"] = [dict(r) for r in con.execute(f"select {','.join(keep)} from evals")]
if "eval_results" in tables:
    cols = [r[1] for r in con.execute("pragma table_info(eval_results)")]
    keep = [c for c in ("id", "eval_id", "test_idx", "prompt_idx", "success", "created_at", "updated_at", "failure_reason") if c in cols]
    out["eval_results"] = [dict(r) for r in con.execute(f"select {','.join(keep)} from eval_results order by test_idx, created_at")]
print(json.dumps(out, indent=1, default=str))
