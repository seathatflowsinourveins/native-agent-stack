"""Gap 8: Feast point-in-time join fixture (local provider, file offline store, temp repo).

Synthetic fundamentals-availability rows (not market data). Checks:
  1. as-of join returns the latest value whose event_timestamp <= entity timestamp;
  2. leakage control: a row published after the entity timestamp is never joined;
  3. TTL control: a row older than the view TTL is never returned (attempt 1 showed Feast
     drops such entity rows instead of returning null; the drop is now reported explicitly);
  4. created_timestamp tie-break: a restatement with the same event time but later
     created time wins (Feast's documented dedup order).
Every returned row is compared against an independent filter-and-sort pandas oracle, so a
wrong join (including a future-leaking one) is detected, not assumed absent.
No server, network listener or telemetry: FEAST_USAGE=False, local provider only.
"""
import json
import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

os.environ["FEAST_USAGE"] = "False"
import pandas as pd
from feast import Entity, FeatureStore, FeatureView, Field, FileSource
from feast.types import Float64
from feast import __version__ as feast_version

UTC = "UTC"
T = lambda s: pd.Timestamp(s, tz=UTC)

rows = pd.DataFrame([
    # symbol, event_timestamp (value becomes knowable), created (ingested), eps
    ("AAA", T("2020-01-10"), T("2020-01-10"), 1.00),
    ("AAA", T("2020-04-10"), T("2020-04-10"), 1.10),
    ("AAA", T("2020-04-10"), T("2020-04-12"), 1.15),   # restatement: same event time, later created -> wins
    ("AAA", T("2020-07-10"), T("2020-07-10"), 1.20),   # published AFTER the 2020-06-30 entity row -> must not leak
    ("BBB", T("2019-01-05"), T("2019-01-05"), 2.00),   # older than TTL for the 2020-06-30 entity row -> no value
], columns=["symbol", "event_timestamp", "created", "eps"])

# CCC has no feature rows at all (added after attempt 1 dropped the stale-only BBB row).
entities = pd.DataFrame({"symbol": ["AAA", "AAA", "AAA", "BBB", "CCC"],
                         "event_timestamp": [T("2020-02-01"), T("2020-05-01"), T("2020-06-30"), T("2020-06-30"), T("2020-06-30")]})
TTL = timedelta(days=365)

with tempfile.TemporaryDirectory(prefix="feast-pit-") as tmp:
    repo = Path(tmp)
    data = repo / "fundamentals.parquet"
    rows.to_parquet(data)
    (repo / "feature_store.yaml").write_text(
        "project: pit_fixture\nprovider: local\nregistry: registry.db\n"
        f"online_store:\n  type: sqlite\n  path: {repo / 'online.db'}\n"
        "offline_store:\n  type: file\nentity_key_serialization_version: 3\n")
    symbol = Entity(name="symbol", join_keys=["symbol"])
    source = FileSource(path=str(data), timestamp_field="event_timestamp", created_timestamp_column="created")
    view = FeatureView(name="fundamentals", entities=[symbol], ttl=TTL,
                       schema=[Field(name="eps", dtype=Float64)], source=source)
    store = FeatureStore(repo_path=str(repo))
    store.apply([symbol, view])
    got = store.get_historical_features(entity_df=entities, features=["fundamentals:eps"]).to_df()

# Independent oracle: latest (event_timestamp, created) row with event_timestamp <= entity ts within TTL.
def oracle(sym, ts):
    cand = rows[(rows.symbol == sym) & (rows.event_timestamp <= ts) & (rows.event_timestamp >= ts - TTL)]
    if cand.empty:
        return None
    return float(cand.sort_values(["event_timestamp", "created"]).iloc[-1].eps)

got = got.sort_values(["symbol", "event_timestamp"]).reset_index(drop=True)
checks = []
for _, r in got.iterrows():
    exp = oracle(r.symbol, r.event_timestamp)
    val = None if pd.isna(r.eps) else float(r.eps)
    checks.append({"symbol": r.symbol, "entity_ts": r.event_timestamp.isoformat(), "feast": val, "oracle": exp, "match": val == exp})
leak = any(c["feast"] == 1.20 for c in checks)
from collections import Counter

def cardinality_ok(returned_keys, requested_keys):
    """Fix round 1 (Codex review): no duplicate and no unrequested (symbol, ts) rows."""
    return not (Counter(returned_keys) - Counter(requested_keys))

requested_keys = [(e.symbol, e.event_timestamp.isoformat()) for e in entities.itertuples()]
returned_keys = [(c["symbol"], c["entity_ts"]) for c in checks]
returned = set(returned_keys)
dropped = [{"symbol": e.symbol, "entity_ts": e.event_timestamp.isoformat(), "oracle": oracle(e.symbol, e.event_timestamp)}
           for e in entities.itertuples() if (e.symbol, e.event_timestamp.isoformat()) not in returned]
out = {"feast": feast_version, "pandas": pd.__version__, "rows_returned": len(got), "checks": checks,
       "future_value_leaked": leak,
       "restatement_wins": any(c["entity_ts"].startswith("2020-05-01") and c["feast"] == 1.15 for c in checks),
       "stale_value_never_returned": not any(c["symbol"] == "BBB" and c["feast"] == 2.00 for c in checks),
       "entity_rows_in": len(entities), "entity_rows_dropped": dropped,
       "dropped_rows_all_have_null_oracle": all(d["oracle"] is None for d in dropped),
       "returned_rows_match_oracle": all(c["match"] for c in checks),
       "join_cardinality_ok": cardinality_ok(returned_keys, requested_keys),
       "self_test_duplicate_row_rejected": not cardinality_ok(returned_keys + returned_keys[:1], requested_keys),
       "self_test_unrequested_row_rejected": not cardinality_ok(returned_keys + [("ZZZ", "2020-06-30T00:00:00+00:00")], requested_keys)}
print(json.dumps(out, indent=1))
# Pass = no leak, every returned row equals the oracle, and any dropped entity row had no
# eligible value (a dropped row with an eligible value would be silent data loss -> fail).
sys.exit(0 if out["returned_rows_match_oracle"] and out["dropped_rows_all_have_null_oracle"] and out["join_cardinality_ok"]
         and out["self_test_duplicate_row_rejected"] and out["self_test_unrequested_row_rejected"] and not leak else 1)
