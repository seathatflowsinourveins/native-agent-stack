#!/usr/bin/env python3
"""Storage-compute comparison harness (gap-wave-2, gaps 3 and 10).

One fixed-seed OHLCV dataset, four stores: DuckDB (embedded file), ClickHouse
(single loopback server), QuestDB (single loopback server, bundled JRE) and
pyiceberg (SQLite SQL catalog, local warehouse). Per store:

  load     bulk load of the whole dataset, then row-count check
  queries  Q1..Q4, one warm-up and REPS timed runs each
  conc     writers-only (W), readers-only (R) and mixed (M) phases at 1/4/8
           clients; per-batch writer latency and per-query reader latency
  kill     SIGKILL during acknowledged batch inserts (server for ClickHouse and
           QuestDB, writer process for DuckDB and pyiceberg), then restart or
           reopen; every acknowledged batch must be present and no partial
           batch may be visible
  footprint on-disk bytes and RSS (server VmRSS/VmHWM, harness ru_maxrss)

Usage:
  bench.py gen --out DIR
  bench.py run --store {duckdb,clickhouse,questdb,iceberg} --data DIR --work DIR
               --out RESULT.json [--ch-bin PATH] [--qdb-home PATH]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import platform
import random
import resource
import shutil
import signal
import statistics
import subprocess
import sys
import threading
import time
import traceback
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

SEED = 20260923
SYMBOLS = 500
MINUTES = int(os.environ.get("BENCH_MINUTES", 100_000))  # per symbol -> 50,000,000 rows
FILES = int(os.environ.get("BENCH_FILES", 50))                # 2,000 minutes x 500 symbols = 1,000,000 rows per file
START = datetime(2025, 1, 2, 14, 30, tzinfo=timezone.utc)
BATCH = 10_000
BATCHES_PER_WRITER = 20
QUERIES_PER_READER = 20
REPS = 5
LEVELS = (1, 4, 8)
SCHEMA = pa.schema([("symbol", pa.string()), ("ts", pa.timestamp("us", tz="UTC")),
                    ("open", pa.float64()), ("high", pa.float64()), ("low", pa.float64()),
                    ("close", pa.float64()), ("volume", pa.int64())])
CH_HTTP, CH_TCP = 18123, 19101
QDB_HTTP, QDB_PG, QDB_ILP, QDB_MIN = 19120, 18812, 19109, 19103


def now():
    return datetime.now(timezone.utc).isoformat()


def ts_of(idx):
    return START + timedelta(days=idx // 390, minutes=idx % 390)


# ----------------------------------------------------------------------------- dataset

def gen(out: Path):
    out.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(SEED)
    price = rng.uniform(10, 500, SYMBOLS)
    syms = np.array([f"S{i:04d}" for i in range(SYMBOLS)])
    per = MINUTES // FILES
    manifest = []
    base_us = int(START.timestamp() * 1_000_000)
    for f in range(FILES):
        idx = np.arange(f * per, (f + 1) * per)
        tsu = base_us + (idx // 390) * 86_400_000_000 + (idx % 390) * 60_000_000
        r = rng.normal(0, 0.001, (per, SYMBOLS))
        closes = price * np.exp(np.cumsum(r, axis=0))
        opens = np.vstack([price, closes[:-1]])
        price = closes[-1]
        hi = np.maximum(opens, closes) * (1 + np.abs(rng.normal(0, 0.0005, (per, SYMBOLS))))
        lo = np.minimum(opens, closes) * (1 - np.abs(rng.normal(0, 0.0005, (per, SYMBOLS))))
        vol = rng.integers(100, 100_000, (per, SYMBOLS))
        # time-major order: each minute, all symbols
        tbl = pa.table({"symbol": np.tile(syms, per), "ts": pa.array(np.repeat(tsu, SYMBOLS), pa.timestamp("us", tz="UTC")),
                        "open": opens.ravel(), "high": hi.ravel(), "low": lo.ravel(), "close": closes.ravel(),
                        "volume": vol.ravel().astype(np.int64)}, schema=SCHEMA)
        p = out / f"part-{f:03d}.parquet"
        pq.write_table(tbl, p, compression="zstd", row_group_size=250_000)
        manifest.append({"file": p.name, "rows": tbl.num_rows, "bytes": p.stat().st_size,
                         "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    combined = hashlib.sha256("".join(m["sha256"] for m in manifest).encode()).hexdigest()
    info = {"seed": SEED, "symbols": SYMBOLS, "minutes_per_symbol": MINUTES, "rows": SYMBOLS * MINUTES,
            "files": manifest, "combined_sha256": combined, "pyarrow": pa.__version__, "numpy": np.__version__,
            "first_ts": ts_of(0).isoformat(), "last_ts": ts_of(MINUTES - 1).isoformat()}
    (out / "manifest.json").write_text(json.dumps(info, indent=1))
    print(json.dumps({k: v for k, v in info.items() if k != "files"}))


# ----------------------------------------------------------------------------- queries

def q_params():
    rng = random.Random(SEED)
    sym = f"S{rng.randrange(SYMBOLS):04d}"
    day = rng.randrange(MINUTES // 390)
    t1 = START + timedelta(days=day)
    return {"sym": sym, "t1": t1, "t2": t1 + timedelta(days=1)}


def reader_params(k):
    rng = random.Random(SEED + k)
    day = rng.randrange(MINUTES // 390)
    t1 = START + timedelta(days=day)
    return f"S{rng.randrange(SYMBOLS):04d}", t1, t1 + timedelta(days=1)


def pct(xs):
    if not xs:
        return None
    s = sorted(xs)
    g = lambda p: s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))]
    return {"n": len(s), "p50": g(50), "p95": g(95), "p99": g(99), "max": s[-1], "mean": statistics.fmean(s)}


def writer_batch(tag: str, b: int) -> pa.Table:
    rng = np.random.default_rng(zlib.crc32(f"{tag}/{b}".encode()))
    base = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() * 1_000_000) + b * BATCH * 1_000_000
    ts = base + np.arange(BATCH, dtype=np.int64) * 1_000_000
    c = 100 + rng.normal(0, 1, BATCH)
    return pa.table({"symbol": [tag] * BATCH, "ts": pa.array(ts, pa.timestamp("us", tz="UTC")),
                     "open": c, "high": c + 1, "low": c - 1, "close": c,
                     "volume": rng.integers(1, 1000, BATCH).astype(np.int64)}, schema=SCHEMA)


# ----------------------------------------------------------------------------- store adapters

def _in_list(tags):
    return ", ".join("'" + t + "'" for t in tags)


class DuckStore:
    name = "duckdb"

    def __init__(self, work: Path, **_):
        import duckdb
        self.duckdb = duckdb
        self.path = work / "bench.duckdb"
        self.work = work
        self.con = None

    def version(self):
        return {"duckdb": self.duckdb.__version__}

    def start(self):
        self.con = self.duckdb.connect(str(self.path), config={"memory_limit": "8GB"})
        return None

    def stop(self):
        if self.con:
            self.con.close()
            self.con = None

    def data_paths(self):
        return [self.path, Path(str(self.path) + ".wal")]

    def load(self, data: Path):
        self.con.execute(f"CREATE TABLE bars AS SELECT * FROM read_parquet('{data}/part-*.parquet')")
        self.con.execute("CHECKPOINT")

    def count(self, sym=None):
        if sym:
            return self.con.execute("SELECT count(*) FROM bars WHERE symbol = ?", [sym]).fetchone()[0]
        return self.con.execute("SELECT count(*) FROM bars").fetchone()[0]

    def count_in(self, tags):
        return self.con.execute(f"SELECT count(*) FROM bars WHERE symbol IN ({_in_list(tags)})").fetchone()[0]

    def query(self, q, p, con=None):
        con = con or self.con
        if q == "Q1":
            return con.execute("SELECT count(*) FROM bars").fetchall()
        if q == "Q2":
            return con.execute("SELECT min(low), max(high), sum(volume) FROM bars WHERE symbol = ? AND ts >= ? AND ts < ?",
                               [p["sym"], p["t1"], p["t2"]]).fetchall()
        if q == "Q3":
            return con.execute("SELECT symbol, avg(close), sum(volume) FROM bars GROUP BY symbol ORDER BY symbol").fetchall()
        if q == "Q4":
            return con.execute("SELECT symbol, count(*), avg(close) FROM bars WHERE ts >= ? AND ts < ? GROUP BY symbol ORDER BY symbol",
                               [p["t1"], p["t2"]]).fetchall()


class ClickHouseStore:
    name = "clickhouse"

    def __init__(self, work: Path, ch_bin=None, **_):
        self.bin = ch_bin
        self.work = work
        self.proc = None
        self.client = None

    def version(self):
        out = subprocess.run([self.bin, "--version"], capture_output=True, text=True).stdout.strip()
        import clickhouse_connect
        return {"clickhouse": out, "clickhouse_connect": clickhouse_connect.__version__}

    def config(self):
        d = self.work / "ch"
        (d / "data").mkdir(parents=True, exist_ok=True)
        (d / "log").mkdir(parents=True, exist_ok=True)
        cfg = d / "config.xml"
        cfg.write_text(f"""<clickhouse>
  <logger><level>warning</level><log>{d}/log/server.log</log><errorlog>{d}/log/error.log</errorlog><console>0</console></logger>
  <listen_host>127.0.0.1</listen_host>
  <http_port>{CH_HTTP}</http_port><tcp_port>{CH_TCP}</tcp_port>
  <path>{d}/data/</path><tmp_path>{d}/data/tmp/</tmp_path><user_files_path>{d}/data/user_files/</user_files_path>
  <max_server_memory_usage>8589934592</max_server_memory_usage>
  <memory_worker_use_cgroup>false</memory_worker_use_cgroup>
  <mark_cache_size>268435456</mark_cache_size>
  <users><default><password></password><networks><ip>127.0.0.1</ip></networks><profile>default</profile><quota>default</quota><access_management>0</access_management></default></users>
  <profiles><default><max_memory_usage>6000000000</max_memory_usage></default></profiles>
  <quotas><default></default></quotas>
  <send_crash_reports><enabled>false</enabled></send_crash_reports>
</clickhouse>
""")
        return cfg

    def start(self):
        cfg = self.config()
        t0 = time.monotonic()
        # No watchdog fork, so the Popen pid is the server whose memory is sampled.
        self.proc = subprocess.Popen([self.bin, "server", f"--config-file={cfg}"], cwd=self.work / "ch",
                                     env={**os.environ, "CLICKHOUSE_WATCHDOG_ENABLE": "0"},
                                     stdout=open(self.work / "ch/stdout.log", "ab"), stderr=subprocess.STDOUT,
                                     start_new_session=True)
        import urllib.request
        while time.monotonic() - t0 < 120:
            try:
                if urllib.request.urlopen(f"http://127.0.0.1:{CH_HTTP}/ping", timeout=1).read().strip() == b"Ok.":
                    break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError("clickhouse not ready")
        ready = time.monotonic() - t0
        self.client = self.new_client()
        return ready

    def new_client(self):
        import clickhouse_connect
        return clickhouse_connect.get_client(host="127.0.0.1", port=CH_HTTP, username="default", password="",
                                             send_receive_timeout=600)

    def stop(self, kill=False):
        if self.proc:
            os.killpg(self.proc.pid, signal.SIGKILL if kill else signal.SIGTERM)
            try:
                self.proc.wait(60)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait(30)
            self.proc = None

    def pid(self):
        return self.proc.pid

    def data_paths(self):
        return [self.work / "ch/data"]

    def load(self, data: Path):
        self.client.command("CREATE TABLE bars (symbol LowCardinality(String), ts DateTime64(6, 'UTC'), open Float64, "
                            "high Float64, low Float64, close Float64, volume Int64) ENGINE = MergeTree ORDER BY (symbol, ts)")
        for f in sorted(data.glob("part-*.parquet")):
            self.client.raw_insert("bars", insert_block=f.read_bytes(), fmt="Parquet")

    def count(self, sym=None, client=None):
        c = client or self.client
        if sym:
            return c.query("SELECT count() FROM bars WHERE symbol = {s:String}", parameters={"s": sym}).result_rows[0][0]
        return c.query("SELECT count() FROM bars").result_rows[0][0]

    def count_in(self, tags):
        return self.client.query(f"SELECT count() FROM bars WHERE symbol IN ({_in_list(tags)})").result_rows[0][0]

    def query(self, q, p, client=None):
        c = client or self.client
        fmt = lambda t: t.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        prm = {"s": p["sym"], "t1": fmt(p["t1"]), "t2": fmt(p["t2"])}
        if q == "Q1":
            return c.query("SELECT count() FROM bars").result_rows
        if q == "Q2":
            return c.query("SELECT min(low), max(high), sum(volume) FROM bars WHERE symbol = {s:String} AND ts >= {t1:DateTime64(6, 'UTC')} AND ts < {t2:DateTime64(6, 'UTC')}", parameters=prm).result_rows
        if q == "Q3":
            return c.query("SELECT symbol, avg(close), sum(volume) FROM bars GROUP BY symbol ORDER BY symbol").result_rows
        if q == "Q4":
            return c.query("SELECT symbol, count(), avg(close) FROM bars WHERE ts >= {t1:DateTime64(6, 'UTC')} AND ts < {t2:DateTime64(6, 'UTC')} GROUP BY symbol ORDER BY symbol", parameters=prm).result_rows


def qdb_exec(sql, timeout=600):
    import requests
    r = requests.get(f"http://127.0.0.1:{QDB_HTTP}/exec", params={"query": sql}, timeout=timeout)
    j = r.json()
    if "error" in j:
        raise RuntimeError(j["error"])
    return j


def qdb_lit(t: datetime):
    return "'" + t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000Z") + "'"


class QuestDBStore:
    name = "questdb"

    def __init__(self, work: Path, qdb_home=None, **_):
        self.home = Path(qdb_home)
        self.work = work
        self.root = work / "qdb"
        self.proc = None

    def version(self):
        out = subprocess.run([str(self.home / "bin/java"), "-version"], capture_output=True, text=True).stderr.strip().splitlines()[0]
        import questdb
        return {"questdb": "10.0.1 (questdb-10.0.1-rt-linux-x86-64)", "bundled_java": out, "questdb_python_client": questdb.__version__}

    def start(self):
        (self.root / "conf").mkdir(parents=True, exist_ok=True)
        (self.root / "log").mkdir(parents=True, exist_ok=True)
        (self.root / "conf/server.conf").write_text(
            f"http.bind.to=127.0.0.1:{QDB_HTTP}\nhttp.min.net.bind.to=127.0.0.1:{QDB_MIN}\n"
            f"pg.net.bind.to=127.0.0.1:{QDB_PG}\nline.tcp.net.bind.to=127.0.0.1:{QDB_ILP}\n"
            "line.udp.enabled=false\ntelemetry.enabled=false\nhttp.security.readonly=false\n")
        java = self.home / "bin/java"
        cmd = ["env", f"LD_PRELOAD={self.home}/bin/libjemalloc.so", str(java), "-DQuestDB-Runtime-gapwave2",
               f"-Dquestdb.libs.dir={self.home}/lib", "-ea", "-Dnoebug", "-Xmx4g",
               f"-XX:ErrorFile={self.root}/hs_err_pid%p.log", "-XX:+UnlockExperimentalVMOptions", "-XX:+UseParallelGC",
               "--sun-misc-unsafe-memory-access=allow", "--enable-native-access=io.questdb",
               "--add-opens=java.base/java.lang=io.questdb", "--add-opens=java.base/java.lang.reflect=io.questdb",
               "--add-opens=java.base/java.nio=io.questdb", "--add-opens=java.base/java.time.zone=io.questdb",
               "--add-exports=java.base/jdk.internal.vm=io.questdb",
               "-m", "io.questdb/io.questdb.ServerMain", "-d", str(self.root)]
        t0 = time.monotonic()
        self.proc = subprocess.Popen(cmd, stdout=open(self.root / "log/stdout.log", "ab"), stderr=subprocess.STDOUT,
                                     start_new_session=True)
        while time.monotonic() - t0 < 180:
            if self.proc.poll() is not None:
                raise RuntimeError("questdb exited %s" % self.proc.returncode)
            try:
                qdb_exec("SELECT 1", timeout=2)
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("questdb not ready")
        return time.monotonic() - t0

    def stop(self, kill=False):
        if self.proc:
            os.killpg(self.proc.pid, signal.SIGKILL if kill else signal.SIGTERM)
            try:
                self.proc.wait(60)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait(30)
            self.proc = None

    def pid(self):
        # env execs java, so the Popen pid is the JVM
        return self.proc.pid

    def data_paths(self):
        return [self.root / "db"]

    def sender(self):
        from questdb.ingress import Sender
        return Sender.from_conf(f"http::addr=127.0.0.1:{QDB_HTTP};auto_flush=off;request_timeout=600000;")

    def load(self, data: Path):
        qdb_exec("CREATE TABLE bars (symbol SYMBOL CAPACITY 2048, ts TIMESTAMP, open DOUBLE, high DOUBLE, low DOUBLE, "
                 "close DOUBLE, volume LONG) TIMESTAMP(ts) PARTITION BY DAY WAL")
        with self.sender() as s:
            for f in sorted(data.glob("part-*.parquet")):
                df = pq.read_table(f).to_pandas()
                for i in range(0, len(df), 100_000):
                    s.dataframe(df.iloc[i:i + 100_000], table_name="bars", symbols=["symbol"], at="ts")
                    s.flush()

    def wait_visible(self, expected, sym=None, timeout=900):
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            try:
                n = self.count(sym)
                if n >= expected:
                    return time.monotonic() - t0, n
            except Exception:
                pass
            time.sleep(0.25)
        return None, self.count(sym)

    def count(self, sym=None):
        if sym:
            return qdb_exec(f"SELECT count() FROM bars WHERE symbol = '{sym}'")["dataset"][0][0]
        return qdb_exec("SELECT count() FROM bars")["dataset"][0][0]

    def count_in(self, tags):
        return qdb_exec(f"SELECT count() FROM bars WHERE symbol IN ({_in_list(tags)})")["dataset"][0][0]

    def query(self, q, p, client=None):
        if q == "Q1":
            return qdb_exec("SELECT count() FROM bars")["dataset"]
        if q == "Q2":
            return qdb_exec(f"SELECT min(low), max(high), sum(volume) FROM bars WHERE symbol = '{p['sym']}' AND ts >= {qdb_lit(p['t1'])} AND ts < {qdb_lit(p['t2'])}")["dataset"]
        if q == "Q3":
            return qdb_exec("SELECT symbol, avg(close), sum(volume) FROM bars GROUP BY symbol ORDER BY symbol")["dataset"]
        if q == "Q4":
            return qdb_exec(f"SELECT symbol, count(), avg(close) FROM bars WHERE ts >= {qdb_lit(p['t1'])} AND ts < {qdb_lit(p['t2'])} GROUP BY symbol ORDER BY symbol")["dataset"]


class IcebergStore:
    name = "iceberg"

    def __init__(self, work: Path, **_):
        self.work = work
        self.wh = work / "warehouse"
        self.table = None

    def version(self):
        import pyiceberg
        import sqlalchemy
        return {"pyiceberg": pyiceberg.__version__, "catalog": "SqlCatalog (sqlite)", "sqlalchemy": sqlalchemy.__version__,
                "pyarrow": pa.__version__}

    def catalog(self):
        from pyiceberg.catalog.sql import SqlCatalog
        return SqlCatalog("bench", uri=f"sqlite:///{self.wh}/catalog.db", warehouse=f"file://{self.wh}")

    def start(self):
        self.wh.mkdir(parents=True, exist_ok=True)
        return None

    def stop(self):
        self.table = None

    def data_paths(self):
        return [self.wh]

    def load(self, data: Path):
        cat = self.catalog()
        cat.create_namespace_if_not_exists("bench")
        self.table = cat.create_table("bench.bars", schema=SCHEMA)
        for f in sorted(data.glob("part-*.parquet")):
            self.table.append(pq.read_table(f))

    def tbl(self):
        return self.catalog().load_table("bench.bars")

    def count(self, sym=None):
        from pyiceberg.expressions import EqualTo
        t = self.tbl()
        if sym:
            return t.scan(row_filter=EqualTo("symbol", sym), selected_fields=("symbol",)).to_arrow().num_rows
        return t.scan().count()

    def count_in(self, tags):
        from pyiceberg.expressions import In
        return self.tbl().scan(row_filter=In("symbol", set(tags)), selected_fields=("symbol",)).to_arrow().num_rows

    def query(self, q, p, client=None):
        from pyiceberg.expressions import And, EqualTo, GreaterThanOrEqual, LessThan
        t = self.tbl()
        t1, t2 = p["t1"].isoformat(), p["t2"].isoformat()
        if q == "Q1":
            return t.scan().count()
        if q == "Q2":
            a = t.scan(row_filter=And(EqualTo("symbol", p["sym"]), GreaterThanOrEqual("ts", t1), LessThan("ts", t2)),
                       selected_fields=("low", "high", "volume")).to_arrow()
            return [(pc.min(a["low"]).as_py(), pc.max(a["high"]).as_py(), pc.sum(a["volume"]).as_py())]
        if q == "Q3":
            a = t.scan(selected_fields=("symbol", "close", "volume")).to_arrow()
            g = a.group_by("symbol").aggregate([("close", "mean"), ("volume", "sum")]).sort_by("symbol")
            return g.to_pylist()
        if q == "Q4":
            a = t.scan(row_filter=And(GreaterThanOrEqual("ts", t1), LessThan("ts", t2)),
                       selected_fields=("symbol", "close")).to_arrow()
            return a.group_by("symbol").aggregate([("close", "count"), ("close", "mean")]).sort_by("symbol").to_pylist()


STORES = {"duckdb": DuckStore, "clickhouse": ClickHouseStore, "questdb": QuestDBStore, "iceberg": IcebergStore}


# ----------------------------------------------------------------------------- concurrency workers

def _write_one(store_name, cfg, tag, conn_state):
    """Insert one batch through a per-worker connection; returns seconds or raises."""
    tbl = conn_state["next"]
    t0 = time.perf_counter()
    if store_name == "clickhouse":
        conn_state["client"].insert_arrow("bars", tbl)
    elif store_name == "questdb":
        s = conn_state["sender"]
        s.dataframe(tbl.to_pandas(), table_name="bars", symbols=["symbol"], at="ts")
        s.flush()
    elif store_name == "iceberg":
        from pyiceberg.exceptions import CommitFailedException
        tries = 0
        while True:
            tries += 1
            try:
                conn_state["cat"].load_table("bench.bars").append(tbl)
                break
            except CommitFailedException:
                conn_state["conflicts"] += 1
                if tries >= 100:
                    raise
    return time.perf_counter() - t0


def proc_worker(store_name, cfg, role, wid, tag, barrier, q):
    """Separate-process client for ClickHouse, QuestDB and pyiceberg."""
    res = {"role": role, "wid": wid, "lat": [], "errors": [], "conflicts": 0}
    try:
        st = STORES[store_name](Path(cfg["work"]), ch_bin=cfg.get("ch_bin"), qdb_home=cfg.get("qdb_home"))
        conn = {"conflicts": 0}
        if store_name == "clickhouse":
            conn["client"] = st.new_client()
        elif store_name == "questdb" and role == "w":
            conn["sender"] = st.sender().__enter__()
        elif store_name == "iceberg":
            conn["cat"] = st.catalog()
            import logging

            class _RetryCounter(logging.Handler):
                def emit(self, record):
                    if "Commit failed due to a concurrent update" in record.getMessage():
                        res["pyiceberg_internal_retries"] = res.get("pyiceberg_internal_retries", 0) + 1
            logging.getLogger().addHandler(_RetryCounter())
        barrier.wait(120)
        if role == "w":
            for b in range(BATCHES_PER_WRITER):
                conn["next"] = writer_batch(tag, b)
                try:
                    res["lat"].append(_write_one(store_name, cfg, tag, conn))
                except Exception as e:
                    res["errors"].append(f"{type(e).__name__}: {str(e)[:200]}")
        else:
            for k in range(QUERIES_PER_READER):
                sym, t1, t2 = reader_params(wid * 1000 + k)
                t0 = time.perf_counter()
                try:
                    st.query("Q2", {"sym": sym, "t1": t1, "t2": t2}, client=conn.get("client"))
                    res["lat"].append(time.perf_counter() - t0)
                except Exception as e:
                    res["errors"].append(f"{type(e).__name__}: {str(e)[:200]}")
        res["conflicts"] = conn["conflicts"]
        if "sender" in conn:
            conn["sender"].__exit__(None, None, None)
    except Exception as e:
        res["errors"].append("worker_setup: " + f"{type(e).__name__}: {str(e)[:300]}")
    q.put(res)


def duck_thread_worker(st, role, wid, tag, barrier, out):
    res = {"role": role, "wid": wid, "lat": [], "errors": [], "conflicts": 0}
    cur = st.con.cursor()
    barrier.wait(120)
    if role == "w":
        for b in range(BATCHES_PER_WRITER):
            tbl = writer_batch(tag, b)
            t0 = time.perf_counter()
            try:
                cur.register("batch_tbl", tbl)
                cur.execute("INSERT INTO bars SELECT * FROM batch_tbl")
                cur.unregister("batch_tbl")
                res["lat"].append(time.perf_counter() - t0)
            except Exception as e:
                res["errors"].append(f"{type(e).__name__}: {str(e)[:200]}")
                res["conflicts"] += 1
    else:
        for k in range(QUERIES_PER_READER):
            sym, t1, t2 = reader_params(wid * 1000 + k)
            t0 = time.perf_counter()
            try:
                st.query("Q2", {"sym": sym, "t1": t1, "t2": t2}, con=cur)
                res["lat"].append(time.perf_counter() - t0)
            except Exception as e:
                res["errors"].append(f"{type(e).__name__}: {str(e)[:200]}")
    cur.close()
    out.append(res)


def run_phase(st, cfg, phase, n):
    roles = (["w"] * n if phase in ("W", "M") else []) + (["r"] * n if phase in ("R", "M") else [])
    tags = [f"{phase}{n}_{i}" for i in range(len(roles))]
    t0 = time.perf_counter()
    results = []
    if st.name == "duckdb":
        barrier = threading.Barrier(len(roles))
        ths = [threading.Thread(target=duck_thread_worker, args=(st, r, i, tags[i], barrier, results)) for i, r in enumerate(roles)]
        [t.start() for t in ths]
        [t.join() for t in ths]
    else:
        ctx = mp.get_context("spawn")
        barrier = ctx.Barrier(len(roles))
        q = ctx.Queue()
        ps = [ctx.Process(target=proc_worker, args=(st.name, cfg, r, i, tags[i], barrier, q)) for i, r in enumerate(roles)]
        [p.start() for p in ps]
        import queue as _queue
        deadline = time.monotonic() + 900
        while len(results) < len(ps) and time.monotonic() < deadline:
            try:
                results.append(q.get(timeout=5))
            except _queue.Empty:
                if not any(p.is_alive() for p in ps) and q.empty():
                    break
        [p.join(60) for p in ps]
        lost = len(ps) - len(results)
        for i in range(lost):
            results.append({"role": "lost", "wid": -1, "lat": [], "errors": ["worker_exited_without_result"], "conflicts": 0})
        if lost:
            results_exitcodes = [p.exitcode for p in ps]
    wall = time.perf_counter() - t0
    w = [r for r in results if r["role"] == "w"]
    rd = [r for r in results if r["role"] == "r"]
    wl = [x for r in w for x in r["lat"]]
    rl = [x for r in rd for x in r["lat"]]
    out = {"phase": phase, "clients": n, "wall_s": wall,
           "writers": len(w), "readers": len(rd),
           "write_batches_ok": len(wl), "write_errors": sum(len(r["errors"]) for r in w),
           "commit_conflicts_retried": sum(r["conflicts"] for r in w) if st.name == "iceberg" else None,
           "pyiceberg_internal_commit_retries": sum(r.get("pyiceberg_internal_retries", 0) for r in w) if st.name == "iceberg" else None,
           "rows_written": len(wl) * BATCH,
           "write_rows_per_s": (len(wl) * BATCH / wall) if wl else 0,
           "write_latency_s": pct(wl), "read_queries_ok": len(rl),
           "read_errors": sum(len(r["errors"]) for r in rd), "read_latency_s": pct(rl),
           "error_samples": sorted({e for r in results for e in r["errors"]})[:5],
           "workers_lost": sum(1 for r in results if r["role"] == "lost"),
           "raw_write_latency_s": [round(x, 6) for x in wl], "raw_read_latency_s": [round(x, 6) for x in rl]}
    # visibility check of written rows
    if w:
        exp = len(wl) * BATCH
        got = 0
        if st.name == "questdb":
            vis_s = None
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                got = st.count_in(tags[:len(w)])
                if got >= exp:
                    break
                time.sleep(0.25)
        else:
            got = st.count_in(tags[:len(w)])
        out["rows_visible_after_phase"] = got
        out["rows_expected"] = exp
    return out


# ----------------------------------------------------------------------------- kill and recover

def kill_writer(store_name, cfg, ackfile):
    st = STORES[store_name](Path(cfg["work"]), ch_bin=cfg.get("ch_bin"), qdb_home=cfg.get("qdb_home"))
    conn = {"conflicts": 0}
    if store_name == "duckdb":
        import duckdb
        con = duckdb.connect(str(st.path))
    elif store_name == "clickhouse":
        conn["client"] = st.new_client()
    elif store_name == "questdb":
        conn["sender"] = st.sender().__enter__()
    elif store_name == "iceberg":
        conn["cat"] = st.catalog()
    fd = os.open(ackfile, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    b = 0
    while True:
        tbl = writer_batch("KILL", b)
        os.write(fd, f"S {b} {time.time():.6f}\n".encode())
        os.fsync(fd)
        # 'I' is written immediately before the engine call (after all client-side preparation).
        mark = lambda: os.write(fd, f"I {b} {time.time():.6f}\n".encode())
        if store_name == "duckdb":
            con.register("batch_tbl", tbl)
            mark()
            con.execute("INSERT INTO bars SELECT * FROM batch_tbl")
            con.unregister("batch_tbl")
        elif store_name == "clickhouse":
            mark()
            conn["client"].insert_arrow("bars", tbl)
        elif store_name == "questdb":
            conn["sender"].dataframe(tbl.to_pandas(), table_name="bars", symbols=["symbol"], at="ts")
            mark()
            conn["sender"].flush()
        else:
            t = conn["cat"].load_table("bench.bars")
            mark()
            t.append(tbl)
        os.write(fd, f"A {b} {time.time():.6f}\n".encode())
        os.fsync(fd)
        b += 1


def iceberg_files(st):
    t = st.tbl()
    referenced = {f.split("://", 1)[-1] for f in t.inspect.files().column("file_path").to_pylist()}
    on_disk = {str(pth) for pth in st.wh.rglob("*.parquet") if "/data/" in str(pth)}
    return {"data_files_on_disk": len(on_disk), "data_files_referenced_by_current_snapshot": len(referenced),
            "orphan_data_files": len(on_disk - referenced), "snapshots": len(t.snapshots())}


def read_markers(ack):
    m = {"S": {}, "I": {}, "A": {}}
    for line in ack.read_text().splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] in m:
            m[parts[0]][int(parts[1])] = float(parts[2])
    return m


KILL_BASE_US = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() * 1_000_000)
KILL_STEP_US = BATCH * 1_000_000


def kill_batches(st):
    """Per writer-batch index: rows, distinct timestamps, sum(volume) for symbol KILL."""
    if st.name == "duckdb":
        rows = st.con.execute(f"SELECT (epoch_us(ts) - {KILL_BASE_US}) // {KILL_STEP_US}, count(*), count(DISTINCT ts), sum(volume) "
                              "FROM bars WHERE symbol = 'KILL' GROUP BY 1 ORDER BY 1").fetchall()
    elif st.name == "clickhouse":
        rows = st.client.query(f"SELECT intDiv(toUnixTimestamp64Micro(ts) - {KILL_BASE_US}, {KILL_STEP_US}) b, count(), uniqExact(ts), sum(volume) "
                               "FROM bars WHERE symbol = 'KILL' GROUP BY b ORDER BY b").result_rows
    elif st.name == "questdb":
        rows = qdb_exec(f"SELECT (cast(ts AS long) - {KILL_BASE_US}) / {KILL_STEP_US} b, count(), count_distinct(cast(ts AS long)), sum(volume) "
                        "FROM bars WHERE symbol = 'KILL' GROUP BY b ORDER BY b")["dataset"]
    else:
        from pyiceberg.expressions import EqualTo
        a = st.tbl().scan(row_filter=EqualTo("symbol", "KILL"), selected_fields=("ts", "volume")).to_arrow()
        us = pc.cast(a["ts"], pa.int64()).to_numpy()
        vol = a["volume"].to_numpy()
        b = (us - KILL_BASE_US) // KILL_STEP_US
        rows = []
        for k in np.unique(b):
            m = b == k
            rows.append((int(k), int(m.sum()), int(len(np.unique(us[m]))), int(vol[m].sum())))
    return {int(r[0]): {"rows": int(r[1]), "distinct_ts": int(r[2]), "sum_volume": int(r[3])} for r in rows}


def kill_and_recover(st, cfg, work: Path):
    ack = work / "kill-acks.txt"
    before = iceberg_files(st) if st.name == "iceberg" else None
    ctx = mp.get_context("spawn")
    p = ctx.Process(target=kill_writer, args=(st.name, cfg, str(ack)))
    if st.name == "duckdb":
        st.stop()  # the writer process must own the file; DuckDB allows one writer process
    p.start()
    t0 = time.monotonic()
    median_engine_s = None
    while time.monotonic() - t0 < 180:
        lines = ack.read_text().splitlines() if ack.exists() else []
        if median_engine_s is None and sum(1 for l in lines if l.startswith("A ")) >= 30:
            mk = read_markers(ack)
            median_engine_s = statistics.median(mk["A"][b] - mk["I"][b] for b in mk["A"] if b in mk["I"])
        if median_engine_s is not None and lines and lines[-1].startswith("I "):
            ti = float(lines[-1].split()[2])
            if time.time() - ti >= 0.25 * median_engine_s:
                break
        time.sleep(0.0005)
    killed = "writer_process"
    if st.name in ("clickhouse", "questdb"):
        kill_t = time.time()
        os.killpg(st.proc.pid, signal.SIGKILL)
        st.proc.wait(30)
        st.proc = None
        killed = "server_process_group"
        time.sleep(0.5)
        os.kill(p.pid, signal.SIGKILL)
    else:
        kill_t = time.time()
        os.kill(p.pid, signal.SIGKILL)
    p.join(30)
    mk = read_markers(ack)
    acks = {b: t for b, t in mk["A"].items() if t < kill_t}
    acked = sorted(acks)
    inflight = [b for b, t in mk["S"].items() if b not in mk["A"] and t < kill_t]
    in_engine = {b: kill_t - mk["I"][b] for b in inflight if b in mk["I"] and mk["I"][b] < kill_t}
    late_acks = sorted(b for b, t in mk["A"].items() if t >= kill_t)
    t1 = time.monotonic()
    ready = st.start()
    vis = None
    if st.name == "questdb":
        vis, _ = st.wait_visible(len(acked) * BATCH, sym="KILL", timeout=300)
        time.sleep(3)
    got = st.count("KILL")
    reopen_s = time.monotonic() - t1  # restart/reopen through the first successful recovery query
    per = kill_batches(st)
    expected = {b: int(pc.sum(writer_batch("KILL", b)["volume"]).as_py()) for b in set(acked) | set(inflight)}
    ok = lambda b: b in per and per[b]["rows"] == BATCH and per[b]["distinct_ts"] == BATCH and per[b]["sum_volume"] == expected[b]
    acked_bad = [b for b in acked if not ok(b)]
    inflight_state = {b: ("absent" if b not in per else ("complete" if ok(b) else "torn_or_wrong")) for b in inflight}
    unexpected = sorted(set(per) - set(acked) - set(inflight))
    total = st.count()
    out = {"killed": killed, "signal": "SIGKILL", "kill_time_unix": kill_t,
           "acked_batches": len(acked), "acked_rows": len(acked) * BATCH,
           "inflight_batches_at_kill": inflight, "inflight_proven": bool(inflight),
           "median_engine_call_s_acked": median_engine_s,
           "engine_call_elapsed_at_kill_s": in_engine,
           "engine_interrupted_proven": bool(in_engine) and all(v >= 0.25 * median_engine_s for v in in_engine.values()) and not late_acks,
           "acks_after_kill_time": late_acks,
           "inflight_state_after_recovery": inflight_state,
           "rows_after_recovery": got, "acked_batches_failing_verification": acked_bad,
           "all_acked_batches_exact": not acked_bad, "unexpected_batch_indices": unexpected,
           "per_batch_checks": "rows == 10000, distinct ts == 10000, sum(volume) == deterministic expected",
           "restart_or_reopen_through_first_query_s": reopen_s, "server_ready_s": ready,
           "questdb_wal_visible_after_s": vis, "total_rows_after_recovery": total}
    if st.name == "iceberg":
        out["iceberg_files_before_kill"] = before
        out["iceberg_files_after_recovery"] = iceberg_files(st)
        out["orphan_data_files_added_by_kill"] = out["iceberg_files_after_recovery"]["orphan_data_files"] - before["orphan_data_files"]
    return out


# ----------------------------------------------------------------------------- footprint

def du(paths):
    tot = 0
    for p in paths:
        p = Path(p)
        if p.is_file():
            tot += p.stat().st_size
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file() and not f.is_symlink():
                    tot += f.stat().st_size
    return tot


def proc_mem(pid):
    if not pid:
        return None
    try:
        kv = dict(l.split(":", 1) for l in Path(f"/proc/{pid}/status").read_text().splitlines() if ":" in l)
        return {"VmRSS_kB": int(kv["VmRSS"].split()[0]), "VmHWM_kB": int(kv["VmHWM"].split()[0])}
    except Exception as e:
        return {"error": str(e)}


def maxrss_kb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


# ----------------------------------------------------------------------------- driver

def run(store: str, data: Path, work: Path, out: Path, ch_bin=None, qdb_home=None):
    work.mkdir(parents=True, exist_ok=False)
    cfg = {"work": str(work), "ch_bin": ch_bin, "qdb_home": qdb_home}
    st = STORES[store](work, ch_bin=ch_bin, qdb_home=qdb_home)
    manifest = json.loads((data / "manifest.json").read_text())
    R = {"store": store, "started_at": now(), "host": {"cpus": os.cpu_count(), "platform": platform.platform(),
         "loadavg_start": os.getloadavg()}, "versions": st.version(),
         "dataset": {"rows": manifest["rows"], "combined_sha256": manifest["combined_sha256"], "seed": manifest["seed"],
                     "parquet_bytes": sum(f["bytes"] for f in manifest["files"])},
         "params": {"batch_rows": BATCH, "batches_per_writer": BATCHES_PER_WRITER,
                    "queries_per_reader": QUERIES_PER_READER, "reps": REPS, "levels": LEVELS,
                    "minutes_per_symbol": MINUTES, "files": FILES},
         "steps": {}}
    try:
        R["steps"]["start_s"] = st.start()
        spid = getattr(st, "pid", lambda: None)()
        R["mem_idle"] = proc_mem(spid)
        t0 = time.perf_counter()
        st.load(data)
        load_s = time.perf_counter() - t0
        R["steps"]["load"] = {"seconds": load_s, "rows_per_s": manifest["rows"] / load_s}
        if store == "questdb":
            vis, n = st.wait_visible(manifest["rows"])
            R["steps"]["load"]["wal_visible_after_s"] = vis
            R["steps"]["load"]["seconds_until_visible"] = load_s + (vis or 0)
            R["steps"]["load"]["rows_per_s_until_visible"] = manifest["rows"] / (load_s + (vis or 0))
        R["steps"]["load"]["row_count"] = st.count()
        R["steps"]["load"]["row_count_ok"] = R["steps"]["load"]["row_count"] == manifest["rows"]
        R["footprint_after_load_bytes"] = du(st.data_paths())
        R["mem_after_load"] = proc_mem(spid)
        # queries
        p = q_params()
        R["query_params"] = {"sym": p["sym"], "t1": p["t1"].isoformat(), "t2": p["t2"].isoformat()}
        R["queries"] = {}
        for q in ("Q1", "Q2", "Q3", "Q4"):
            first = st.query(q, p)
            times = []
            for _ in range(REPS):
                t0 = time.perf_counter()
                st.query(q, p)
                times.append(time.perf_counter() - t0)
            R["queries"][q] = {"raw_s": times, "median_s": statistics.median(times), "result_digest": digest(q, first),
                               "canonical_rows": canonical(q, first)}
        # concurrency
        R["concurrency"] = []
        if store == "duckdb":
            R["duckdb_second_process"] = duck_second_process(st)
        for phase in ("W", "R", "M"):
            for n in LEVELS:
                R["concurrency"].append(run_phase(st, cfg, phase, n))
        R["mem_after_concurrency"] = proc_mem(getattr(st, "pid", lambda: None)())
        R["footprint_after_concurrency_bytes"] = du(st.data_paths())
        R["kill_recover"] = kill_and_recover(st, cfg, work)
        R["mem_after_recovery"] = proc_mem(getattr(st, "pid", lambda: None)())
        R["footprint_after_recovery_bytes"] = du(st.data_paths())
    except Exception:
        R["error"] = traceback.format_exc()[-3000:]
    finally:
        try:
            st.stop()
        except Exception as e:
            R["stop_error"] = str(e)
    R["harness_maxrss_kB"] = maxrss_kb()
    R["children_maxrss_kB"] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    R["host"]["loadavg_end"] = os.getloadavg()
    R["finished_at"] = now()
    out.write_text(json.dumps(R, indent=1, default=str) + "\n")
    print(json.dumps({"store": store, "error": R.get("error", "")[-400:], "load": R["steps"].get("load"),
                      "queries": {k: v["median_s"] for k, v in R.get("queries", {}).items()},
                      "kill": R.get("kill_recover")}, default=str))


def digest(q, res):
    """Store-independent result digest for cross-store agreement checks."""
    def norm(x):
        if isinstance(x, dict):
            x = list(x.values())
        if isinstance(x, (list, tuple)):
            return [norm(y) for y in x]
        if isinstance(x, float):
            return round(x, 4)
        if isinstance(x, (np.integer,)):
            return int(x)
        if isinstance(x, (np.floating,)):
            return round(float(x), 4)
        if x is not None and hasattr(x, "__int__") and not isinstance(x, (str, bool)):
            try:
                return round(float(x), 4) if float(x) != int(x) else int(x)
            except Exception:
                return str(x)
        return x
    if q == "Q1":
        v = res if isinstance(res, int) else norm(res)[0][0]
        return {"count": int(v)}
    rows = norm(res)
    if q == "Q2":
        r = rows[0]
        return {"min_low": r[0], "max_high": r[1], "sum_volume": int(r[2])}
    return {"groups": len(rows), "sum_col2": round(sum(float(r[1]) for r in rows), 3),
            "sum_col3": round(sum(float(r[2]) for r in rows), 3)}


def canonical(q, res):
    """Full result rows as JSON-safe lists (strings, ints, floats) for cross-store comparison."""
    def val(x):
        if isinstance(x, (np.integer,)):
            return int(x)
        if isinstance(x, (np.floating,)):
            return float(x)
        if isinstance(x, (str, int, float)) or x is None:
            return x
        try:
            f = float(x)
            return int(f) if f == int(f) and "." not in str(x) else f
        except Exception:
            return str(x)
    if q == "Q1":
        return [[int(res if isinstance(res, int) else res[0][0])]]
    rows = [list(r.values()) if isinstance(r, dict) else list(r) for r in res]
    return [[val(v) for v in r] for r in rows]


def duck_second_process(st):
    code = ("import duckdb,sys\n"
            "try:\n duckdb.connect(sys.argv[1]).execute('INSERT INTO bars SELECT * FROM bars LIMIT 1'); print('opened')\n"
            "except Exception as e: print(type(e).__name__+': '+str(e)[:300])\n")
    r = subprocess.run([sys.executable, "-c", code, str(st.path)], capture_output=True, text=True, timeout=60)
    r2 = subprocess.run([sys.executable, "-c", code.replace("duckdb.connect(sys.argv[1])", "duckdb.connect(sys.argv[1], read_only=True)"), str(st.path)],
                        capture_output=True, text=True, timeout=60)
    return {"second_writer_process": r.stdout.strip()[:300], "second_read_only_process": r2.stdout.strip()[:300]}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen")
    g.add_argument("--out", required=True)
    r = sub.add_parser("run")
    r.add_argument("--store", required=True, choices=sorted(STORES))
    r.add_argument("--data", required=True)
    r.add_argument("--work", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--ch-bin")
    r.add_argument("--qdb-home")
    a = ap.parse_args()
    if a.cmd == "gen":
        gen(Path(a.out))
    else:
        run(a.store, Path(a.data), Path(a.work), Path(a.out), a.ch_bin, a.qdb_home)


if __name__ == "__main__":
    main()
