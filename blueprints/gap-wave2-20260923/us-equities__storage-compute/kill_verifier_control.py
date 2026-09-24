#!/usr/bin/env python3
"""Detection control for bench.py's per-batch kill-recovery verification.

On a copy of a DuckDB smoke database that already passed recovery, delete the
rows of acknowledged batch 5 and insert a second copy of batch 6. Total KILL
rows are unchanged and still a multiple of 10,000, so the round-1 aggregate
check (count >= acked, count % 10,000 == 0) passes; the round-2 per-batch check
must flag batches 5 (missing) and 6 (duplicated).

Usage: kill_verifier_control.py SMOKE_DB_COPY ACKED_BATCHES
"""
import json
import sys
from pathlib import Path

import pyarrow.compute as pc

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench  # noqa: E402

db, acked_n = Path(sys.argv[1]), int(sys.argv[2])
st = bench.DuckStore(db.parent)
st.path = db
st.start()
s = bench.KILL_BASE_US
step = bench.KILL_STEP_US
before = st.count("KILL")
st.con.execute(f"DELETE FROM bars WHERE symbol = 'KILL' AND epoch_us(ts) >= {s + 5 * step} AND epoch_us(ts) < {s + 6 * step}")
st.con.execute(f"INSERT INTO bars SELECT * FROM bars WHERE symbol = 'KILL' AND epoch_us(ts) >= {s + 6 * step} AND epoch_us(ts) < {s + 7 * step}")
after = st.count("KILL")
per = bench.kill_batches(st)
acked = list(range(acked_n))
expected = {b: int(pc.sum(bench.writer_batch("KILL", b)["volume"]).as_py()) for b in acked}
ok = lambda b: b in per and per[b]["rows"] == bench.BATCH and per[b]["distinct_ts"] == bench.BATCH and per[b]["sum_volume"] == expected[b]
out = {"kill_rows_before": before, "kill_rows_after_mutation": after,
       "round1_aggregate_check_passes": after >= acked_n * bench.BATCH and after % bench.BATCH == 0,
       "round2_failing_batches": [b for b in acked if not ok(b)],
       "batch_5": per.get(5), "batch_6": per.get(6)}
st.stop()
print(json.dumps(out))
sys.exit(0 if out["round2_failing_batches"] == [5, 6] and out["round1_aggregate_check_passes"] else 1)
