#!/usr/bin/env python3
"""Gap-wave-2 identity-provenance gap 4: four-arm store comparison on the materialized replay fixture.

Arms: baseline (replay.py hash-manifest snapshot directories), dvc (DVC 3.67.1 + git), iceberg (PyIceberg 0.12.0,
SQLite catalog, local file warehouse), arctic (ArcticDB 6.26.0, LMDB). Each arm runs in its own venv:
    <venv python> store_arms.py ARM --fixture MATERIALIZED_DIR --work WORKDIR --out RESULT.json
Metrics (preregistered C4.1-C4.6): restore fidelity, correction retention, lineage fields, recovery after SIGKILL,
two concurrent writers, storage bytes and latency. Synthetic 5+2-row fixture only; absolute numbers are not
representative of real data sizes.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import re
import shutil
import signal
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
REPLAY = WT / "blueprints/us-equities/nanosecond-replay/replay.py"
FIXTURE_JSON = WT / "blueprints/us-equities/nanosecond-replay/fixture.json"
V1_CUTOFF_NS = None  # set from data: rows available at or before ...150Z form v1 (original, future-member)
TABLES = ("observations", "universe")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def rows_from_duckdb(rel):
    cols = rel.columns
    return [dict(zip(cols, r)) for r in rel.fetchall()]


def canonical(rows):
    def norm(v):
        if hasattr(v, "item"):
            v = v.item()
        return v
    rows = [{k: norm(v) for k, v in r.items()} for r in rows]
    rows.sort(key=lambda r: (str(r.get("row_id")),))
    return sha(json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str).encode()), len(rows)


def read_parquet_rows(path):
    import duckdb
    with duckdb.connect() as con:
        return rows_from_duckdb(con.read_parquet(str(path)))


def rows_from_arrow(table):
    import duckdb
    with duckdb.connect() as con:
        return rows_from_duckdb(con.from_arrow(table))


def rows_from_df(df):
    import duckdb
    with duckdb.connect() as con:
        return rows_from_duckdb(con.from_df(df.reset_index(drop=True)))


def du(path):
    total = 0
    for p in Path(path).rglob("*"):
        if p.is_file() and not p.is_symlink():
            total += p.stat().st_size
    return total


def fixture_rows(fixture):
    return {t: read_parquet_rows(Path(fixture) / f"{t}.parquet") for t in TABLES}


def split_versions(rows):
    """v1 = rows available at or before 21:00:00.000000150Z; v2 adds the later corrections."""
    cutoff = 1738443600000000150  # 2025-02-01T21:00:00.000000150Z in UTC ns
    obs = rows["observations"]
    v1 = [r for r in obs if r["available_ns"] <= cutoff]
    later = [r for r in obs if r["available_ns"] > cutoff]
    return v1, later


def row_key(r):
    def norm(v):
        return v.item() if hasattr(v, "item") else v
    return json.dumps({k: norm(v) for k, v in r.items()}, sort_keys=True, default=str)


def content_check(rows, fixture_obs):
    """Fix round F4.1: decoded rows must be whole copies of the fixture batch (same count per row_id, identical content)."""
    want = {r["row_id"]: row_key(r) for r in fixture_obs}
    counts, problems = {}, []
    for r in rows:
        rid = r.get("row_id")
        if rid not in want:
            problems.append(f"foreign row_id {rid}")
        elif row_key(r) != want[rid]:
            problems.append(f"content differs for {rid}")
        counts[rid] = counts.get(rid, 0) + 1
    if rows and (set(counts) != set(want) or len(set(counts.values())) != 1):
        problems.append(f"unequal copies per row_id {counts}")
    batches = next(iter(counts.values())) if rows and not problems else None
    return {"decoded_rows": len(rows), "batches": batches if rows else 0, "content_ok": not problems, "problems": problems[:5]}


def detector_controls(rows, fixture_obs):
    """Fix round F4.2: the content check must fail on an injected foreign row, a corrupted row and a dropped row."""
    base = [dict(r) for r in rows] or [dict(r) for r in fixture_obs]
    corrupted = [dict(r) for r in base]; corrupted[0]["value_text"] = "999999"
    foreign = [dict(r) for r in base] + [dict(base[0], row_id="foreign-row")]
    dropped = [dict(r) for r in base][1:]
    return {name: not content_check(v, fixture_obs)["content_ok"] for name, v in
            (("corrupted_row_flagged", corrupted), ("foreign_row_flagged", foreign), ("dropped_row_flagged", dropped))}


def du_sb(path, *exclude):
    args = ["du", "-sb", *[f"--exclude={e}" for e in exclude], str(path)]
    return int(subprocess.run(args, capture_output=True, text=True, check=True).stdout.split()[0])


def median_ms(samples):
    return round(statistics.median(samples) * 1000, 3)


# ------------------------------------------------------------------ arms

class Baseline:
    """replay.py materialize directories; each version is a new immutable directory (exist_ok=False)."""
    name = "baseline"

    def __init__(self, work, fixture):
        self.work, self.fixture = Path(work), Path(fixture)
        spec = importlib.util.spec_from_file_location("g2_replay", REPLAY)
        self.ns = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.ns)

    def source_for(self, obs_rows):
        data = json.loads(FIXTURE_JSON.read_text())
        keep = {r["row_id"] for r in obs_rows}
        data["observations"] = [o for o in data["observations"] if o["row_id"] in keep]
        return data

    def write_version(self, label, obs_rows):
        src = self.work / f"{label}-source.json"
        src.write_text(json.dumps(self.source_for(obs_rows)))
        return self.ns.materialize(src, self.work / f"store/{label}")

    def read_version(self, label, manifest):
        _, frozen = self.ns.verified(self.work / f"store/{label}", manifest["snapshot_sha256"])
        tmp = self.work / f"read-{label}-{time.time_ns()}"
        tmp.mkdir()
        out = {}
        for t in TABLES:
            (tmp / f"{t}.parquet").write_bytes(frozen[f"{t}.parquet"])
            out[t] = read_parquet_rows(tmp / f"{t}.parquet")
        shutil.rmtree(tmp)
        return out

    def run(self, rows):
        (self.work / "store").mkdir(parents=True)
        v1, later = split_versions(rows)
        res = {}
        m1 = self.write_version("v1", v1)
        m2 = self.write_version("v2", v1 + later)
        full = self.read_version("v2", m2)
        res["restore"] = {t: canonical(full[t])[0] == canonical(rows[t])[0] for t in TABLES}
        # restore after delete: the baseline has no restore mechanism; it re-materializes from the fixture.
        before = {n: sha((self.work / "store/v2" / n).read_bytes()) for n in ("source.json", "observations.parquet", "universe.parquet", "snapshot.json")}
        shutil.rmtree(self.work / "store/v2")
        m2b = self.write_version("v2", v1 + later)
        after = {n: sha((self.work / "store/v2" / n).read_bytes()) for n in before}
        res["restore_after_delete"] = {"mechanism": "re-materialize from git-tracked fixture",
                                       "per_file_equal": {n: before[n] == after[n] for n in before},
                                       "old_snapshot_sha256_still_verifies": self._verifies("v2", m2["snapshot_sha256"])}
        v1rows = self.read_version("v1", m1)["observations"]
        res["correction_retention"] = {"v1_rows_equal": canonical(v1rows)[0] == canonical(v1)[0], "v1_row_ids": sorted(r["row_id"] for r in v1rows),
                                       "mechanism": "separate immutable snapshot directory per version"}
        manifest = json.loads((self.work / "store/v2/snapshot.json").read_text())
        res["lineage"] = {"version_id": "snapshot_sha256 (content digest, caller-held)", "parent_version": None,
                          "commit_timestamp": manifest.get("ingested_at"), "operation": None,
                          "per_file_content_hash": sorted(manifest["files"]), "input_dataset_name": manifest.get("provenance")[:60],
                          "field_classification": {'version_id': 'native', 'parent_version': 'absent', 'commit_timestamp': 'native', 'operation': 'absent', 'per_file_content_hash': 'native', 'input_dataset_name': 'caller_annotation'}, "native_count": 3, "classification_note": "version_id is the content digest materialize returns; the caller must hold it because the store does not persist it. input_dataset_name is the provenance prose from the source file. The source.json content hash is recorded natively in the manifest."}
        res["storage_bytes"] = {"file_sum": du(self.work / "store"), "du_sb": du_sb(self.work / "store")}
        w, r = [], []
        for i in range(5):
            t0 = time.perf_counter(); m = self.write_version(f"lat{i}", v1 + later); w.append(time.perf_counter() - t0)
            t0 = time.perf_counter(); self.read_version(f"lat{i}", m); r.append(time.perf_counter() - t0)
        res["latency_ms"] = {"write_median": median_ms(w), "read_median": median_ms(r), "write_samples": len(w), "unit_of_work": "materialize two tables + manifest / verify + read two tables"}
        return res

    def _verifies(self, label, digest):
        try:
            self.ns.verified(self.work / f"store/{label}", digest)
            return True
        except Exception as error:  # noqa: BLE001 - recorded
            return f"refused: {error}"

    # writer loop for recovery/concurrency: one new snapshot directory per commit
    def writer(self, store, tag, n, progress):
        data = self.source_for(fixture_rows(self.fixture)["observations"])
        src = Path(store) / f"src-{tag}.json"
        src.write_text(json.dumps(data))
        done = 0
        for i in range(n):
            try:
                self.ns.materialize(src, Path(store) / f"{tag}-{i:05d}")
                done += 1
            except Exception as error:  # noqa: BLE001
                progress.write(json.dumps({"i": i, "error": f"{type(error).__name__}: {error}"}) + "\n"); progress.flush()
                continue
            progress.write(json.dumps({"i": i, "done": done}) + "\n"); progress.flush()

    def inspect(self, store):
        dirs = sorted(p for p in Path(store).iterdir() if p.is_dir())
        complete, incomplete, bad, rows = 0, 0, [], []
        for d in dirs:
            if not (d / "snapshot.json").exists():
                incomplete += 1
                continue
            digest = sha((d / "snapshot.json").read_bytes())
            try:
                _, frozen = self.ns.verified(d, digest)
                complete += 1
                tmp = Path(store).parent / f"decode-{d.name}.parquet"
                tmp.write_bytes(frozen["observations.parquet"])
                rows += read_parquet_rows(tmp)  # decode the verified bytes (fix round F4.1)
                tmp.unlink()
            except Exception as error:  # noqa: BLE001
                bad.append(f"{d.name}: {error}")
        cc = content_check(rows, fixture_rows(self.fixture)["observations"])
        return {"committed_versions": complete, "incomplete_dirs_without_manifest": incomplete, "manifest_present_but_invalid": bad,
                "rows": cc["decoded_rows"], "content": cc, "detector_controls": detector_controls(rows, fixture_rows(self.fixture)["observations"]),
                "readable": not bad}


class Dvc:
    name = "dvc"

    def __init__(self, work, fixture):
        self.work, self.fixture = Path(work), Path(fixture)
        self.env = dict(os.environ, HOME=str(self.work / "home"), XDG_CONFIG_HOME=str(self.work / "home/.config"),
                        XDG_CACHE_HOME=str(self.work / "home/.cache"), DVC_NO_ANALYTICS="1", GIT_CONFIG_NOSYSTEM="1")
        (self.work / "home").mkdir(parents=True, exist_ok=True)
        self.dvc = str(Path(sys.executable).parent / "dvc")

    def sh(self, cwd, *cmd, check=True):
        p = subprocess.run(list(cmd), cwd=cwd, env=self.env, capture_output=True, text=True)
        if check and p.returncode:
            raise RuntimeError(f"{cmd} exit {p.returncode}: {p.stderr[-400:]}")
        return p

    def init_repo(self, repo):
        repo = Path(repo)
        repo.mkdir(parents=True)
        self.sh(repo, "git", "init", "-q"); self.sh(repo, "git", "config", "user.email", "g2@local"); self.sh(repo, "git", "config", "user.name", "g2")
        self.sh(repo, self.dvc, "init", "-q")
        for k, v in (("core.analytics", "false"), ("core.check_update", "false"), ("core.site_cache_dir", str(self.work / "site-cache"))):
            self.sh(repo, self.dvc, "config", k, v)
        self.sh(repo, "git", "add", "-A"); self.sh(repo, "git", "commit", "-q", "-m", "init")
        return repo

    def put(self, repo, rows_by_table, label):
        import duckdb
        d = Path(repo) / "snap"
        if d.exists():
            shutil.rmtree(d)
        d.mkdir()
        with duckdb.connect() as con:
            for t, rows in rows_by_table.items():
                src = self.fixture / f"{t}.parquet"
                ids = [r["row_id"] for r in rows]
                con.read_parquet(str(src)).filter(f"row_id IN ({','.join(repr(i) for i in ids)})").order("row_id").write_parquet(str(d / f"{t}.parquet"), compression="zstd")
        self.sh(repo, self.dvc, "add", "snap")
        self.sh(repo, "git", "add", "snap.dvc", ".gitignore"); self.sh(repo, "git", "commit", "-q", "--allow-empty", "-m", label)
        return self.sh(repo, "git", "rev-parse", "HEAD").stdout.strip()

    def read(self, repo, rev=None):
        repo = Path(repo)
        if rev:
            self.sh(repo, "git", "checkout", "-q", rev, "--", "snap.dvc")
        shutil.rmtree(repo / "snap", ignore_errors=True)
        self.sh(repo, self.dvc, "checkout", "-q", "snap.dvc")
        out = {t: read_parquet_rows(repo / "snap" / f"{t}.parquet") for t in TABLES}
        if rev:
            self.sh(repo, "git", "checkout", "-q", "HEAD", "--", "snap.dvc"); self.sh(repo, self.dvc, "checkout", "-q", "-f", "snap.dvc")
        return out

    def run(self, rows):
        repo = self.init_repo(self.work / "repo")
        v1, later = split_versions(rows)
        r1 = self.put(repo, {"observations": v1, "universe": rows["universe"]}, "v1")
        r2 = self.put(repo, {"observations": v1 + later, "universe": rows["universe"]}, "v2")
        res = {}
        before = {p.name: sha(p.read_bytes()) for p in (repo / "snap").iterdir()}
        full = self.read(repo)
        after = {p.name: sha(p.read_bytes()) for p in (repo / "snap").iterdir()}
        res["restore"] = {t: canonical(full[t])[0] == canonical(rows[t])[0] for t in TABLES}
        res["restore_after_delete"] = {"mechanism": "dvc checkout from local cache", "per_file_equal": {n: before[n] == after.get(n) for n in before}}
        v1read = self.read(repo, r1)["observations"]
        res["correction_retention"] = {"v1_rows_equal": canonical(v1read)[0] == canonical(v1)[0], "v1_row_ids": sorted(r["row_id"] for r in v1read),
                                       "mechanism": "git checkout <v1 commit> -- snap.dvc && dvc checkout"}
        log = self.sh(repo, "git", "log", "-1", "--format=%H %P %cI %s").stdout.split()
        dvcfile = (repo / "snap.dvc").read_text()
        res["lineage"] = {"version_id": log[0], "parent_version": log[1], "commit_timestamp": log[2], "operation": " ".join(log[3:]),
                          "per_file_content_hash": "md5 of the directory manifest in snap.dvc: " + dvcfile.split("md5:")[1].split()[0],
                          "input_dataset_name": None,
                          "field_classification": {'version_id': 'native', 'parent_version': 'native', 'commit_timestamp': 'native', 'operation': 'caller_annotation', 'per_file_content_hash': 'native', 'input_dataset_name': 'absent'}, "native_count": 4, "classification_note": "dvc add mode: operation is the caller commit subject. In pipeline mode dvc.lock natively records the stage cmd and dep paths (see gap-0 run).",
                          "note": "input dataset names appear only for pipeline stages (dvc.lock deps), not for dvc add; see gap 0/2 run dvc.lock"}
        res["storage_bytes"] = {"file_sum_workspace_plus_cache": du(repo) - du(repo / ".git"), "file_sum_dvc_cache": du(repo / ".dvc/cache"),
                                "file_sum_git_dir": du(repo / ".git"), "du_sb_excluding_git": du_sb(repo, ".git"),
                                "du_sb_dvc_cache": du_sb(repo / ".dvc/cache"), "du_sb_git_dir": du_sb(repo / ".git")}
        w, r = [], []
        for i in range(5):
            t0 = time.perf_counter(); self.put(repo, {"observations": v1 + later if i % 2 == 0 else v1, "universe": rows["universe"]}, f"lat{i}"); w.append(time.perf_counter() - t0)
            t0 = time.perf_counter(); self.read(repo); r.append(time.perf_counter() - t0)
        res["latency_ms"] = {"write_median": median_ms(w), "read_median": median_ms(r), "write_samples": len(w),
                             "unit_of_work": "write parquet + dvc add + git commit (CLI subprocesses) / delete + dvc checkout + read"}
        return res

    def writer(self, store, tag, n, progress):
        repo = Path(store) / "repo"
        rows = fixture_rows(self.fixture)
        for i in range(n):
            try:
                d = repo / f"w{tag}"
                d.mkdir(exist_ok=True)
                shutil.copy(self.fixture / "observations.parquet", d / f"batch-{i:05d}.parquet")
                self.sh(repo, self.dvc, "add", f"w{tag}")
                self.sh(repo, "git", "add", f"w{tag}.dvc", ".gitignore"); self.sh(repo, "git", "commit", "-q", "-m", f"{tag}-{i}")
                progress.write(json.dumps({"i": i, "done": i + 1}) + "\n"); progress.flush()
            except Exception as error:  # noqa: BLE001
                progress.write(json.dumps({"i": i, "error": str(error)[:300]}) + "\n"); progress.flush()
        del rows

    def prepare_store(self, store):
        self.init_repo(Path(store) / "repo")

    def inspect(self, store, tags):
        repo = Path(store) / "repo"
        out = {"status_exit": self.sh(repo, self.dvc, "status", check=False).returncode}
        rows, readable, detail, decoded = 0, True, {}, []
        for tag in tags:
            dvcfile = repo / f"w{tag}.dvc"
            if not dvcfile.exists():
                detail[tag] = "no committed version"
                continue
            self.sh(repo, "git", "checkout", "-q", "HEAD", "--", f"w{tag}.dvc")
            shutil.rmtree(repo / f"w{tag}", ignore_errors=True)
            p = self.sh(repo, self.dvc, "checkout", "-q", "-f", f"w{tag}.dvc", check=False)
            files = sorted((repo / f"w{tag}").glob("*.parquet")) if (repo / f"w{tag}").exists() else []
            try:
                got = [r for f in files for r in read_parquet_rows(f)]
                decoded += got
                n = len(got)
            except Exception as error:  # noqa: BLE001
                readable, n = False, 0
                detail[tag] = str(error)
            rows += n
            detail[tag] = {"checkout_exit": p.returncode, "batches": len(files), "stderr": p.stderr[-200:]}
        fx = fixture_rows(self.fixture)["observations"]
        out.update({"rows": rows, "content": content_check(decoded, fx), "detector_controls": detector_controls(decoded, fx),
                    "readable": readable, "detail": detail,
                    "git_commits": int(self.sh(repo, "git", "rev-list", "--count", "HEAD").stdout.strip()) - 1,
                    "status_after_exit": self.sh(repo, self.dvc, "status", check=False).returncode})
        return out


class Iceberg:
    name = "iceberg"

    def __init__(self, work, fixture):
        self.work, self.fixture = Path(work), Path(fixture)

    def catalog(self, store):
        from pyiceberg.catalog.sql import SqlCatalog
        Path(store).mkdir(parents=True, exist_ok=True)
        return SqlCatalog("g2", uri=f"sqlite:///{store}/catalog.db", warehouse=f"file://{store}/warehouse")

    def arrow(self, rows_or_table):
        import pyarrow.parquet as pq
        return pq.read_table(self.fixture / f"{rows_or_table}.parquet")

    def subset(self, table, ids):
        import pyarrow.compute as pc
        return table.filter(pc.is_in(table["row_id"], value_set=__import__("pyarrow").array(sorted(ids))))

    def run(self, rows):
        store = self.work / "store"
        cat = self.catalog(store)
        cat.create_namespace("g2")
        obs_all, uni = self.arrow("observations"), self.arrow("universe")
        v1, later = split_versions(rows)
        t_obs = cat.create_table("g2.observations", schema=obs_all.schema)
        t_uni = cat.create_table("g2.universe", schema=uni.schema)
        t_uni.append(uni)
        t_obs.append(self.subset(obs_all, {r["row_id"] for r in v1}))
        s1 = t_obs.current_snapshot().snapshot_id
        t_obs.append(self.subset(obs_all, {r["row_id"] for r in later}))
        res = {}
        cat2 = self.catalog(store)  # fresh catalog handle = restore from persisted metadata
        full = {t: rows_from_arrow(cat2.load_table(f"g2.{t}").scan().to_arrow()) for t in TABLES}
        res["restore"] = {t: canonical(full[t])[0] == canonical(rows[t])[0] for t in TABLES}
        res["restore_after_delete"] = {"mechanism": "row store; the fixture parquet files are rewritten into Iceberg data files, so source per-file sha256 is not preserved",
                                       "per_file_equal": "not_supported"}
        v1read = rows_from_arrow(cat2.load_table("g2.observations").scan(snapshot_id=s1).to_arrow())
        res["correction_retention"] = {"v1_rows_equal": canonical(v1read)[0] == canonical(v1)[0], "v1_row_ids": sorted(r["row_id"] for r in v1read),
                                       "mechanism": "scan(snapshot_id=<v1 snapshot>) time travel"}
        tbl = cat2.load_table("g2.observations")
        snap = tbl.current_snapshot()
        files = tbl.inspect.files().to_pylist()
        res["lineage"] = {"version_id": snap.snapshot_id, "parent_version": snap.parent_snapshot_id, "commit_timestamp": snap.timestamp_ms,
                          "operation": str(snap.summary.operation) if snap.summary else None,
                          "per_file_content_hash": None, "data_files_recorded": len(files),
                          "data_file_fields": sorted(k for k in files[0] if k in ("file_path", "file_size_in_bytes", "record_count")),
                          "input_dataset_name": None, "history_entries": len(tbl.history()),
                          "field_classification": {'version_id': 'native', 'parent_version': 'native', 'commit_timestamp': 'native', 'operation': 'native', 'per_file_content_hash': 'absent', 'input_dataset_name': 'absent'}, "native_count": 4,
                          "note": "manifests record data file path, size, record count and column stats; no content hash"}
        res["storage_bytes"] = {"file_sum": du(store), "du_sb": du_sb(store)}
        w, r = [], []
        for i in range(5):
            s = self.work / f"lat{i}"
            t0 = time.perf_counter()
            c = self.catalog(s); c.create_namespace("g2")
            for t, a in (("observations", obs_all), ("universe", uni)):
                c.create_table(f"g2.{t}", schema=a.schema).append(a)
            w.append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            c = self.catalog(s)
            for t in TABLES:
                c.load_table(f"g2.{t}").scan().to_arrow()
            r.append(time.perf_counter() - t0)
        res["latency_ms"] = {"write_median": median_ms(w), "read_median": median_ms(r), "write_samples": len(w),
                             "unit_of_work": "new SQLite catalog + create/append two tables / fresh catalog + scan two tables"}
        return res

    def prepare_store(self, store):
        c = self.catalog(store); c.create_namespace("g2")
        c.create_table("g2.observations", schema=self.arrow("observations").schema)

    def writer(self, store, tag, n, progress):
        batch = self.arrow("observations")
        c = self.catalog(store)
        for i in range(n):
            try:
                c.load_table("g2.observations").append(batch)
                progress.write(json.dumps({"i": i, "done": i + 1}) + "\n"); progress.flush()
            except Exception as error:  # noqa: BLE001
                progress.write(json.dumps({"i": i, "error": f"{type(error).__name__}: {str(error)[:200]}"}) + "\n"); progress.flush()

    def inspect(self, store, tags=None):
        try:
            t = self.catalog(store).load_table("g2.observations")
            got = rows_from_arrow(t.scan().to_arrow())
            fx = fixture_rows(self.fixture)["observations"]
            return {"rows": len(got), "content": content_check(got, fx), "detector_controls": detector_controls(got, fx),
                    "readable": True, "snapshots": len(t.snapshots())}
        except Exception as error:  # noqa: BLE001
            return {"rows": None, "readable": False, "error": f"{type(error).__name__}: {error}"}


class Arctic:
    name = "arctic"

    def __init__(self, work, fixture):
        self.work, self.fixture = Path(work), Path(fixture)

    def lib(self, store):
        import arcticdb as adb
        Path(store).mkdir(parents=True, exist_ok=True)
        ac = adb.Arctic(f"lmdb://{store}")
        if "g2" not in ac.list_libraries():
            ac.create_library("g2")
        return ac["g2"]

    def df(self, table, ids=None):
        import pandas as pd
        d = pd.read_parquet(self.fixture / f"{table}.parquet")
        if ids is not None:
            d = d[d["row_id"].isin(ids)]
        return d.sort_values("row_id").reset_index(drop=True)

    def run(self, rows):
        store = self.work / "store"
        lib = self.lib(store)
        v1, later = split_versions(rows)
        lib.write("universe", self.df("universe"))
        w1 = lib.write("observations", self.df("observations", {r["row_id"] for r in v1}), metadata={"input_dataset": "nanosecond-replay/fixture.json", "part": "v1"})
        lib.append("observations", self.df("observations", {r["row_id"] for r in later}))
        res = {}
        lib2 = self.lib(store)
        full = {t: rows_from_df(lib2.read(t).data) for t in TABLES}
        res["restore"] = {t: canonical(full[t])[0] == canonical(rows[t])[0] for t in TABLES}
        res["restore_after_delete"] = {"mechanism": "row store; parquet files are converted to ArcticDB segments, so source per-file sha256 is not preserved",
                                       "per_file_equal": "not_supported"}
        v1read = rows_from_df(lib2.read("observations", as_of=w1.version).data)
        res["correction_retention"] = {"v1_rows_equal": canonical(v1read)[0] == canonical(v1)[0], "v1_row_ids": sorted(r["row_id"] for r in v1read),
                                       "mechanism": "read(as_of=<v1 version>)"}
        versions = lib2.list_versions("observations")
        latest = max(versions, key=lambda k: k.version)
        info = versions[latest]
        meta = lib2.read_metadata("observations", as_of=w1.version).metadata
        res["lineage"] = {"version_id": latest.version, "parent_version": None, "commit_timestamp": str(info.date),
                          "operation": None, "per_file_content_hash": None,
                          "input_dataset_name": f"user metadata only: {meta}",
                          "versions_listed": len(versions),
                          "field_classification": {'version_id': 'native', 'parent_version': 'absent', 'commit_timestamp': 'native', 'operation': 'absent', 'per_file_content_hash': 'absent', 'input_dataset_name': 'caller_annotation'}, "native_count": 2,
                          "note": "version numbers are monotonic per symbol; no parent pointer, operation type or content hash is recorded; metadata is caller-supplied"}
        res["storage_bytes"] = {"file_sum": du(store), "du_sb": du_sb(store)}
        w, r = [], []
        for i in range(5):
            s = self.work / f"lat{i}"
            t0 = time.perf_counter()
            l = self.lib(s)
            for t in TABLES:
                l.write(t, self.df(t))
            w.append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            l = self.lib(s)
            for t in TABLES:
                l.read(t).data
            r.append(time.perf_counter() - t0)
        res["latency_ms"] = {"write_median": median_ms(w), "read_median": median_ms(r), "write_samples": len(w),
                             "unit_of_work": "new LMDB library + write two symbols / fresh handle + read two symbols"}
        return res

    initial_rows = 5  # an empty frame cannot seed the symbol (E_INCOMPATIBLE_INDEX on append), so one batch seeds it

    def prepare_store(self, store):
        l = self.lib(store)
        l.write("observations", self.df("observations"))

    def writer(self, store, tag, n, progress):
        l = self.lib(store)
        batch = self.df("observations")
        for i in range(n):
            try:
                l.append("observations", batch)
                progress.write(json.dumps({"i": i, "done": i + 1}) + "\n"); progress.flush()
            except Exception as error:  # noqa: BLE001
                progress.write(json.dumps({"i": i, "error": f"{type(error).__name__}: {str(error)[:200]}"}) + "\n"); progress.flush()

    def inspect(self, store, tags=None):
        try:
            l = self.lib(store)
            got = rows_from_df(l.read("observations").data)
            fx = fixture_rows(self.fixture)["observations"]
            cc = content_check(got, fx)  # includes the seed batch, so batches = appended + 1
            return {"rows": len(got) - self.initial_rows, "rows_including_seed": len(got), "content": cc,
                    "detector_controls": detector_controls(got, fx), "readable": True,
                    "versions": len(l.list_versions("observations"))}
        except Exception as error:  # noqa: BLE001
            return {"rows": None, "readable": False, "error": f"{type(error).__name__}: {error}"}


ARMS = {"baseline": Baseline, "dvc": Dvc, "iceberg": Iceberg, "arctic": Arctic}


# ------------------------------------------------------------------ recovery and concurrency drivers

def spawn_writer(arm, fixture, store, tag, n, progress_path, work):
    return subprocess.Popen([sys.executable, __file__, arm, "--fixture", str(fixture), "--work", str(work),
                             "--writer", str(store), "--tag", tag, "--n", str(n), "--progress", str(progress_path)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)


def progress_of(path):
    done, errors = 0, []
    if Path(path).exists():
        for line in Path(path).read_text().splitlines():
            rec = json.loads(line)
            if "done" in rec:
                done = max(done, rec["done"] if isinstance(rec["done"], int) else 0)
            else:
                errors.append(rec["error"])
    return done, errors


def recovery(arm_cls, name, fixture, work, trials=5):
    out = []
    rng = random.Random(20260923)
    for trial in range(trials):
        store = Path(work) / f"recovery-{trial}"
        store.mkdir(parents=True)
        a = arm_cls(Path(work) / f"rec-arm-{trial}", fixture)
        (Path(work) / f"rec-arm-{trial}").mkdir(parents=True, exist_ok=True)
        if name != "baseline":
            a.prepare_store(store)
        prog = store.parent / f"recovery-{trial}.progress"
        p = spawn_writer(name, fixture, store, "a", 100000, prog, Path(work) / f"rec-arm-{trial}")
        t0 = time.time()
        while progress_of(prog)[0] < 3 and not progress_of(prog)[1] and time.time() - t0 < 120 and p.poll() is None:
            time.sleep(0.02)
        time.sleep(rng.uniform(0.01, 0.3))
        p.send_signal(signal.SIGKILL); p.wait()
        done, errors = progress_of(prog)
        state = a.inspect(store) if name == "baseline" else a.inspect(store, ["a"]) if name == "dvc" else a.inspect(store)
        rows = state.get("rows")
        seed = 1 if name == "arctic" else 0
        content = state.get("content", {})
        decoded_batches = (content.get("batches") or 0) - seed if content.get("content_ok") else None
        # store-reported committed units, independent of decoding (fix round 2, R4.1)
        store_units = {"baseline": lambda: state.get("committed_versions"),
                       "dvc": lambda: (state.get("detail", {}).get("a") or {}).get("batches") if isinstance(state.get("detail", {}).get("a"), dict) else 0,
                       "iceberg": lambda: state.get("snapshots"),
                       "arctic": lambda: (state.get("versions") or 0) - 1}[name]()

        def predicate(batches, nrows, content_ok):
            return bool(state.get("readable") and content_ok and all(state.get("detector_controls", {}).values())
                        and (nrows > 0 if done > 0 else True) and batches is not None and batches == store_units
                        and store_units in (done, done + 1))

        ok = predicate(decoded_batches, (rows or 0) + seed * 5, content.get("content_ok"))
        recovery_controls = {"whole_batch_loss_flagged": not predicate(None if decoded_batches is None else decoded_batches - 1, max(0, (rows or 0) - 5) + seed * 5, True),
                             "empty_result_flagged": not predicate(0 - seed, 0, content_check([], fixture_rows(fixture)["observations"])["content_ok"])}
        ok = ok and all(recovery_controls.values())
        out.append({"trial": trial, "progress_recorded_commits": done, "writer_errors": errors[:3], "state": state,
                    "decoded_batches": decoded_batches, "store_reported_units": store_units, "recovery_controls": recovery_controls,
                    "whole_units_and_consistent_with_progress": bool(ok)})
    return {"trials": out, "all_recovered": all(t["whole_units_and_consistent_with_progress"] for t in out),
            "detection_method": "after SIGKILL, reopen the store in a fresh process handle and decode every stored row; pass only if it reads, the decoded rows are whole identical copies of the 5-row fixture batch (content_check), the corrupted/foreign/dropped-row controls are flagged, decoded whole batches equal the store-reported committed units (baseline verified manifests, DVC committed batch files, Iceberg snapshots, ArcticDB versions minus the seed), that count is the writer's last recorded count or one more, and the whole-batch-loss and empty-result controls fail the same predicate (fix round 2)"}


def concurrency(arm_cls, name, fixture, work, n=10):
    store = Path(work) / "concurrency"
    store.mkdir(parents=True)
    a = arm_cls(Path(work) / "conc-arm", fixture)
    (Path(work) / "conc-arm").mkdir(parents=True, exist_ok=True)
    if name != "baseline":
        a.prepare_store(store)
    procs = []
    for tag in ("a", "b"):
        procs.append((tag, spawn_writer(name, fixture, store, tag, n, store.parent / f"conc-{tag}.progress", Path(work) / "conc-arm")))
    stderr = {}
    for tag, p in procs:
        try:
            _, err = p.communicate(timeout=600)
        except subprocess.TimeoutExpired:
            p.kill(); _, err = p.communicate()
        stderr[tag] = (err or "")[-300:]
        # fix round 3 (H4.2): keep each writer's complete stderr in its own file; added after the cited stores-fix2 run
        (store.parent / f"conc-{tag}.stderr").write_text(err or "")
    per = {tag: dict(zip(("done", "errors"), progress_of(store.parent / f"conc-{tag}.progress"))) for tag in ("a", "b")}
    state = a.inspect(store) if name == "baseline" else a.inspect(store, ["a", "b"]) if name == "dvc" else a.inspect(store)
    reported = sum(v["done"] for v in per.values())
    rows = state.get("rows")
    lost = None if rows is None else reported * 5 - rows
    return {"writers": 2, "appends_each": n, "reported_successful_appends": reported,
            "writer_error_counts": {t: len(v["errors"]) for t, v in per.items()},
            "writer_error_examples": {t: v["errors"][:2] for t, v in per.items()}, "stderr_tail": stderr,
            "state": state, "rows_expected_from_reported_successes": reported * 5, "rows_found": rows,
            "rows_lost_after_reported_success": lost,
            "content": state.get("content"), "detector_controls": state.get("detector_controls"),
            "no_silent_loss": lost == 0 and bool(state.get("content", {}).get("content_ok")),
            "stderr_full_files": {t: str(store.parent / f"conc-{t}.stderr") for t in ("a", "b")},
            "retry_summary_full_stderr": retry_summary({t: (store.parent / f"conc-{t}.stderr").read_text() for t in ("a", "b")})}


RETRY_RE = re.compile(r"retrying \((\d+)/(\d+)\)")


def retry_summary(texts):
    """Fix round 3 (H4.2): parse every 'retrying (k/N)' line and any CommitFailedException from complete stderr."""
    attempts = [int(m.group(1)) for t in texts.values() for m in RETRY_RE.finditer(t)]
    control = [int(m.group(1)) for m in RETRY_RE.finditer("Commit failed due to a concurrent update, retrying (4/4) in 800 ms")]
    return {"retry_lines": len(attempts), "max_attempt": max(attempts) if attempts else 0,
            "attempt_histogram": {str(k): attempts.count(k) for k in sorted(set(attempts))},
            "commit_failed_exception_lines": sum(t.count("CommitFailedException") for t in texts.values()),
            "stderr_bytes": {k: len(v.encode()) for k, v in texts.items()},
            "detector_control_parses_4_of_4": control == [4]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arm", choices=ARMS)
    ap.add_argument("--fixture", required=True, type=Path)
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--writer"); ap.add_argument("--tag"); ap.add_argument("--n", type=int); ap.add_argument("--progress")
    ap.add_argument("--only-concurrency", type=int, help="repeatability check: run only the two-writer test with N appends each")
    a = ap.parse_args()
    cls = ARMS[a.arm]
    if a.only_concurrency:
        a.work.mkdir(parents=True, exist_ok=False)
        result = {"arm": a.arm, "concurrent_writers": concurrency(cls, a.arm, a.fixture, a.work, n=a.only_concurrency)}
        a.out.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
        c = result["concurrent_writers"]
        print(json.dumps({k: c[k] for k in ("reported_successful_appends", "rows_found", "rows_lost_after_reported_success", "writer_error_counts")}))
        return 0
    if a.writer:
        arm = cls(a.work, a.fixture)
        with open(a.progress, "a") as progress:
            arm.writer(Path(a.writer), a.tag, a.n, progress)
        return 0
    a.work.mkdir(parents=True, exist_ok=False)
    rows = fixture_rows(a.fixture)
    t0 = time.time()
    result = {"arm": a.arm, "python": sys.version.split()[0], "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    for mod in ("duckdb", "pandas", "pyarrow", "pyiceberg", "arcticdb", "dvc"):
        try:
            result.setdefault("versions", {})[mod] = __import__("importlib.metadata").metadata.version(mod)
        except Exception:  # noqa: BLE001
            pass
    arm = cls(a.work / "main", a.fixture)
    (a.work / "main").mkdir(parents=True, exist_ok=True)
    result["fixture_rows"] = {t: canonical(rows[t]) for t in TABLES}
    result.update(arm.run(rows))
    result["recovery_after_sigkill"] = recovery(cls, a.arm, a.fixture, a.work / "rec")
    result["concurrent_writers"] = concurrency(cls, a.arm, a.fixture, a.work / "conc")
    result["elapsed_s"] = round(time.time() - t0, 2)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: result[k] for k in ("arm", "restore", "elapsed_s")}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
