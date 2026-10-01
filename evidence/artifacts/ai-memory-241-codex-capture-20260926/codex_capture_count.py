"""Read-only count of ai-memory observations written by Codex sessions since a start time.

Usage: python3 codex_capture_count.py <start_epoch_seconds>
Prints one line per (agent_kind, observation kind) with its count, plus the codex session count.
"""
import os
import sqlite3
import sys

t0 = int(sys.argv[1]) * 1_000_000
db = os.path.expanduser("~/.local/share/ai-memory/db/memory.sqlite")
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=15)
try:
    rows = con.execute(
        """select s.agent_kind, o.kind, count(*) from observations o
           join sessions s on s.id = o.session_id
           where o.created_at >= ? and s.agent_kind = 'codex'
           group by 1, 2 order by 2""", (t0,)).fetchall()
    sessions = con.execute(
        """select count(distinct o.session_id) from observations o
           join sessions s on s.id = o.session_id
           where o.created_at >= ? and s.agent_kind = 'codex'""", (t0,)).fetchone()[0]
    schema = con.execute("select max(version) from refinery_schema_history").fetchone()[0]
finally:
    con.close()
print(f"store schema V{schema}")
print(f"codex sessions with observations since probe start: {sessions}")
for agent, kind, n in rows:
    print(f"{agent}\t{kind}\t{n}")
