#!/usr/bin/env python3
"""Gap-wave-2 identity-provenance gap 5: OpenLineage file-transport persistence with version/cutoff facets and
MLflow run-to-dataset bindings (mlflow.log_input) for one replay.py materialize + select run.

    emit     --work DIR : materialize the replay fixture, run one select at an explicit cutoff, emit OpenLineage
                          START/COMPLETE events for both runs through FileTransport, log one MLflow run (SQLite store)
                          with log_input bindings for the materialized files; writes DIR/emit.json
    readback --work DIR : fresh process; reads the event file and the SQLite store back, checks consistency, runs the
                          detector control on a tampered copy of the event file; writes DIR/readback.json
Synthetic fixture only; intended to run under `unshare -rn` (no network namespace).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import uuid

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
REPLAY = WT / "blueprints/us-equities/nanosecond-replay/replay.py"
FIXTURE = WT / "blueprints/us-equities/nanosecond-replay/fixture.json"
CUTOFF = "2025-02-01T21:00:00.000000200Z"
PRODUCER = "https://github.com/seathatflowsinourveins/native-agent-stack/blueprints/gap-wave2-20260923"
NS = "file"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def replay():
    spec = importlib.util.spec_from_file_location("g2_replay", REPLAY)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def facets():
    import attr
    from openlineage.client.generated.base import DatasetFacet, RunFacet

    @attr.define
    class FileHashesDatasetFacet(DatasetFacet):
        files: dict
        snapshot_sha256: str

        @staticmethod
        def _get_schema() -> str:
            return PRODUCER + "/FileHashesDatasetFacet.json"

    @attr.define
    class KnowledgeCutoffRunFacet(RunFacet):
        cutoff: str
        cutoff_ns: str

        @staticmethod
        def _get_schema() -> str:
            return PRODUCER + "/KnowledgeCutoffRunFacet.json"

    return FileHashesDatasetFacet, KnowledgeCutoffRunFacet


def emit(work: Path):
    from openlineage.client import OpenLineageClient
    from openlineage.client.event_v2 import InputDataset, Job, OutputDataset, Run, RunEvent, RunState
    from openlineage.client.generated.dataset_version_dataset import DatasetVersionDatasetFacet
    from openlineage.client.transport.file import FileConfig, FileTransport
    from openlineage.client.uuid import generate_new_uuid
    import openlineage.client
    import mlflow
    import pandas as pd
    from datetime import datetime, timezone

    ns = replay()
    FileHashes, Cutoff = facets()
    events_path = work / "openlineage-events.ndjson"  # .jsonl is gitignored in this repository
    client = OpenLineageClient(transport=FileTransport(FileConfig(log_file_path=str(events_path), append=True)))
    snap = work / "materialized"
    now = lambda: datetime.now(timezone.utc).isoformat()  # noqa: E731

    # ---- materialize run
    mat_run = str(generate_new_uuid())
    mat_job = Job(namespace="gap-wave2", name="nanosecond-replay.materialize")
    fixture = json.loads(FIXTURE.read_text())
    horizon_ns = max(ns.utc_ns(r["available_at"]) for c in ("observations", "universe") for r in fixture[c])
    horizon = next(r["available_at"] for c in ("observations", "universe") for r in fixture[c] if ns.utc_ns(r["available_at"]) == horizon_ns)
    mat_facets = {"g2_knowledgeCutoff": Cutoff(cutoff=horizon, cutoff_ns=str(horizon_ns))}  # snapshot knowledge horizon
    src_ds = InputDataset(namespace=NS, name=str(FIXTURE.relative_to(WT)), facets={
        "version": DatasetVersionDatasetFacet(datasetVersion=sha(FIXTURE.read_bytes()))})
    client.emit(RunEvent(eventType=RunState.START, eventTime=now(), run=Run(runId=mat_run, facets=mat_facets), job=mat_job,
                         producer=PRODUCER, inputs=[src_ds], outputs=[OutputDataset(namespace=NS, name="materialized")]))
    manifest = ns.materialize(FIXTURE, snap)
    files = json.loads((snap / "snapshot.json").read_text())["files"]
    out_ds = OutputDataset(namespace=NS, name="materialized", facets={
        "version": DatasetVersionDatasetFacet(datasetVersion=manifest["snapshot_sha256"]),
        "g2_fileHashes": FileHashes(files={k: v["sha256"] for k, v in files.items()}, snapshot_sha256=manifest["snapshot_sha256"])})
    client.emit(RunEvent(eventType=RunState.COMPLETE, eventTime=now(), run=Run(runId=mat_run, facets=mat_facets), job=mat_job,
                         producer=PRODUCER, inputs=[src_ds], outputs=[out_ds]))

    # ---- select run with an explicit knowledge cutoff; its input is the versioned materialized dataset
    sel_run = str(generate_new_uuid())
    sel_job = Job(namespace="gap-wave2", name="nanosecond-replay.select")
    cutoff_ns = str(ns.utc_ns(CUTOFF))
    in_ds = InputDataset(namespace=NS, name="materialized", facets={
        "version": DatasetVersionDatasetFacet(datasetVersion=manifest["snapshot_sha256"]),
        "g2_fileHashes": FileHashes(files={k: v["sha256"] for k, v in files.items()}, snapshot_sha256=manifest["snapshot_sha256"])})
    run_facets = {"g2_knowledgeCutoff": Cutoff(cutoff=CUTOFF, cutoff_ns=cutoff_ns)}
    client.emit(RunEvent(eventType=RunState.START, eventTime=now(), run=Run(runId=sel_run, facets=run_facets), job=sel_job,
                         producer=PRODUCER, inputs=[in_ds], outputs=[]))
    result = ns.select(snap, manifest["snapshot_sha256"], CUTOFF, "fixture-universe", "fixture-feed")
    client.emit(RunEvent(eventType=RunState.COMPLETE, eventTime=now(), run=Run(runId=sel_run, facets=run_facets), job=sel_job,
                         producer=PRODUCER, inputs=[in_ds], outputs=[]))

    # ---- MLflow: one run for the select, dataset inputs bound with log_input
    os.environ.setdefault("MLFLOW_DISABLE_TELEMETRY", "true")
    uri = f"sqlite:///{work / 'mlflow.db'}"
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment("gap-wave2-identity-provenance")
    bindings = {}
    digest_attempts = {}
    with mlflow.start_run(run_name="nanosecond-replay.materialize") as mrun:
        mlflow.set_tags({"openlineage.run_id": mat_run, "snapshot_sha256": manifest["snapshot_sha256"],
                         "knowledge_horizon": horizon, "knowledge_horizon_ns": str(horizon_ns)})
        fx_sha = sha(FIXTURE.read_bytes())
        for table in ("observations", "universe"):
            ds = mlflow.data.from_pandas(pd.DataFrame(fixture[table]), source=str(FIXTURE), name=f"fixture.{table}")
            mlflow.log_input(ds, context="materialize_source", tags={"file_sha256": fx_sha})
            bindings[f"materialize:fixture.{table}"] = {"name": ds.name, "digest": ds.digest, "file_sha256": fx_sha}
        materialize_mlflow_run = mrun.info.run_id
    with mlflow.start_run(run_name="nanosecond-replay.select") as run:
        mlflow.set_tags({"openlineage.select_run_id": sel_run, "openlineage.materialize_run_id": mat_run,
                         "snapshot_sha256": manifest["snapshot_sha256"], "knowledge_cutoff": CUTOFF, "knowledge_cutoff_ns": cutoff_ns})
        mlflow.log_params({"cutoff": CUTOFF, "universe_id": "fixture-universe", "feed": "fixture-feed",
                           "selection_sql_sha256": result["selection_sql_sha256"]})
        mlflow.log_metric("selected_records", len(result["records"]))
        for table in ("observations", "universe"):
            df = pd.read_parquet(snap / f"{table}.parquet")
            file_sha = files[f"{table}.parquet"]["sha256"]
            try:  # try binding the project's sha256 as the MLflow dataset digest
                ds = mlflow.data.from_pandas(df, source=str(snap / f"{table}.parquet"), name=table, digest=file_sha)
                mlflow.log_input(ds, context="replay_select_input", tags={"file_sha256": file_sha, "snapshot_sha256": manifest["snapshot_sha256"]})
                digest_attempts[table] = "project sha256 accepted as digest"
            except Exception as error:  # noqa: BLE001 - fall back to MLflow's own digest, keep the hash in tags
                digest_attempts[table] = f"project sha256 refused as digest: {type(error).__name__}: {str(error)[:200]}"
                ds = mlflow.data.from_pandas(df, source=str(snap / f"{table}.parquet"), name=table)
                mlflow.log_input(ds, context="replay_select_input", tags={"file_sha256": file_sha, "snapshot_sha256": manifest["snapshot_sha256"]})
            bindings[f"select:{table}"] = {"name": ds.name, "digest": ds.digest, "file_sha256": file_sha}
        run_id = run.info.run_id
    out = {"events_path": events_path.name, "materialize_run_id": mat_run, "select_run_id": sel_run,
           "snapshot_sha256": manifest["snapshot_sha256"], "files": {k: v["sha256"] for k, v in files.items()},
           "cutoff": CUTOFF, "cutoff_ns": cutoff_ns, "horizon": horizon, "horizon_ns": str(horizon_ns), "fixture_sha256": sha(FIXTURE.read_bytes()), "selected_row_ids": [r["row_id"] for r in result["records"]],
           "mlflow": {"tracking_uri": "sqlite:///<work>/mlflow.db", "run_id": run_id, "materialize_run_id": materialize_mlflow_run, "bindings": bindings, "digest_attempts": digest_attempts},
           "versions": {"openlineage-python": __import__("importlib.metadata").metadata.version("openlineage-python"),
                        "mlflow": mlflow.__version__, "pandas": pd.__version__,
                        "duckdb": __import__("importlib.metadata").metadata.version("duckdb")}}
    (work / "emit.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"emitted": True, "run_id": run_id}))


def check_events(events, expect):
    """Fix-round F5.1/F5.2: lifecycle-aware facet rule with required (event, role, dataset) presence."""
    problems = []
    fixture_name = str(FIXTURE.relative_to(WT))
    runs = {expect["materialize_run_id"]: "materialize", expect["select_run_id"]: "select"}
    by = {}
    for e in events:
        by.setdefault((runs.get(e["run"]["runId"], "unknown"), e["eventType"]), []).append(e)
    for label in ("materialize", "select"):
        for et in ("START", "COMPLETE"):
            if len(by.get((label, et), [])) != 1:
                problems.append(f"{label} {et}: {len(by.get((label, et), []))} events")
    if any(k[0] == "unknown" for k in by):
        problems.append("event with unknown runId")

    def one(e, role, name):
        found = [d for d in e.get(role, []) if d.get("name") == name and d.get("namespace") == NS]
        return found[0] if len(found) == 1 else None

    def versioned(d, where, want_version, hashes):
        if d is None:
            problems.append(f"{where}: dataset missing")
            return
        f = d.get("facets", {})
        if f.get("version", {}).get("datasetVersion") != want_version:
            problems.append(f"{where}: version {f.get('version', {}).get('datasetVersion')} != expected")
        if hashes:
            h = f.get("g2_fileHashes", {})
            if h.get("files") != expect["files"] or h.get("snapshot_sha256") != expect["snapshot_sha256"]:
                problems.append(f"{where}: file hashes differ from manifest")

    rules = [("materialize", "START", "inputs", fixture_name, expect["fixture_sha256"], False),
             ("materialize", "COMPLETE", "inputs", fixture_name, expect["fixture_sha256"], False),
             ("materialize", "COMPLETE", "outputs", "materialized", expect["snapshot_sha256"], True),
             ("select", "START", "inputs", "materialized", expect["snapshot_sha256"], True),
             ("select", "COMPLETE", "inputs", "materialized", expect["snapshot_sha256"], True)]
    for label, et, role, name, version, hashes in rules:
        for e in by.get((label, et), [])[:1]:
            versioned(one(e, role, name), f"{label} {et} {role} {name}", version, hashes)
    for e in by.get(("materialize", "START"), [])[:1]:
        if one(e, "outputs", "materialized") is None:  # declared output by name; its version is unknown before the run
            problems.append("materialize START outputs materialized: dataset missing")
    want_cut = {"materialize": (expect["horizon"], expect["horizon_ns"]), "select": (expect["cutoff"], expect["cutoff_ns"])}
    for (label, et), es in by.items():
        if label in want_cut:
            for e in es:
                c = e["run"].get("facets", {}).get("g2_knowledgeCutoff", {})
                if (c.get("cutoff"), c.get("cutoff_ns")) != want_cut[label]:
                    problems.append(f"{label} {et}: cutoff facet {c.get('cutoff')}/{c.get('cutoff_ns')} differs")
    return problems


def controls(events, expect):
    """Fix-round F5.3 (a)-(d): each tampered copy must produce at least one problem."""
    def mutate(fn):
        t = copy.deepcopy(events)
        fn(t)
        return check_events(t, expect)

    def ev(t, run_key, et):
        return next(e for e in t if e["run"]["runId"] == expect[run_key] and e["eventType"] == et)

    def tamper(t):
        e = ev(t, "select_run_id", "COMPLETE")
        e["inputs"][0]["facets"]["version"]["datasetVersion"] = "0" * 64
        e["run"]["facets"]["g2_knowledgeCutoff"]["cutoff_ns"] = "1"

    def drop_output(t):
        ev(t, "materialize_run_id", "COMPLETE")["outputs"] = []

    def drop_select_input(t):
        ev(t, "select_run_id", "START")["inputs"] = []

    def rename_output(t):
        ev(t, "materialize_run_id", "COMPLETE")["outputs"][0]["name"] = "materialized-renamed"

    return {name: mutate(fn) for name, fn in (("a_tampered_version_and_cutoff", tamper), ("b_removed_materialize_complete_output", drop_output),
                                              ("c_removed_select_start_input", drop_select_input), ("d_renamed_materialize_complete_output", rename_output))}


def readback(work: Path, spec=None):
    os.environ.setdefault("MLFLOW_DISABLE_TELEMETRY", "true")
    from mlflow.tracking import MlflowClient
    expect = json.loads((work / "emit.json").read_text())
    raw = (work / expect["events_path"]).read_text().splitlines()
    events = [json.loads(line) for line in raw if line.strip()]
    problems = check_events(events, expect)
    # detector control: alter one copy of the select COMPLETE event's input version and cutoff; the checker must flag it
    control_results = controls(events, expect)
    control = [f"{k}: {v[0] if v else 'NOT FLAGGED'}" for k, v in control_results.items()]
    control_all_flagged = all(control_results.values())
    schema = {"checked": False}
    if spec:
        import jsonschema
        doc = json.loads(Path(spec).read_text())
        validator = jsonschema.Draft202012Validator({**doc, "$ref": "#/$defs/RunEvent"}, format_checker=jsonschema.FormatChecker())
        errs = {i: [e.message[:160] for e in validator.iter_errors(ev)] for i, ev in enumerate(events)}
        bad = copy.deepcopy(events[0]); bad.pop("eventTime"); bad["run"]["runId"] = "not-a-uuid"
        control_errs = [e.message[:160] for e in validator.iter_errors(bad)]
        schema = {"checked": True, "spec_id": doc.get("$id"), "spec_sha256": sha(Path(spec).read_bytes()),
                  "errors_by_event": errs, "all_valid": not any(errs.values()),
                  "detector_control_errors": control_errs, "detector_control_flagged": bool(control_errs)}
    client = MlflowClient(tracking_uri=f"sqlite:///{work / 'mlflow.db'}")

    def inputs_of(run):
        return [{"name": di.dataset.name, "digest": di.dataset.digest,
                 "source": json.loads(di.dataset.source).get("uri") if di.dataset.source.startswith("{") else di.dataset.source,
                 "source_type": di.dataset.source_type, "tags": {t.key: t.value for t in di.tags}} for di in run.inputs.dataset_inputs]

    runs = {"select": client.get_run(expect["mlflow"]["run_id"]), "materialize": client.get_run(expect["mlflow"]["materialize_run_id"])}
    inputs = {k: inputs_of(r) for k, r in runs.items()}
    ml_problems = []
    for key, b in expect["mlflow"]["bindings"].items():
        kind, name = key.split(":", 1)
        match = [i for i in inputs[kind] if i["name"] == name]
        if len(match) != 1:
            ml_problems.append(f"{key}: {len(match)} bindings")
            continue
        i = match[0]
        if i["digest"] != b["digest"]:
            ml_problems.append(f"{key}: digest {i['digest']} != {b['digest']}")
        want_sha = expect["files"][f"{name}.parquet"] if kind == "select" else expect["fixture_sha256"]
        if i["tags"].get("file_sha256") != want_sha:
            ml_problems.append(f"{key}: file_sha256 tag differs")
        if kind == "select" and i["tags"].get("snapshot_sha256") != expect["snapshot_sha256"]:
            ml_problems.append(f"{key}: snapshot tag differs")
        want_src = f"materialized/{name}.parquet" if kind == "select" else "nanosecond-replay/fixture.json"
        if not str(i["source"]).endswith(want_src):
            ml_problems.append(f"{key}: source {i['source']}")
    stags, mtags = runs["select"].data.tags, runs["materialize"].data.tags
    if stags.get("openlineage.select_run_id") != expect["select_run_id"] or stags.get("openlineage.materialize_run_id") != expect["materialize_run_id"]:
        ml_problems.append("select run openlineage run id tags differ")
    if mtags.get("openlineage.run_id") != expect["materialize_run_id"]:
        ml_problems.append("materialize run openlineage run id tag differs")
    if stags.get("knowledge_cutoff_ns") != expect["cutoff_ns"] or mtags.get("knowledge_horizon_ns") != expect["horizon_ns"]:
        ml_problems.append("cutoff/horizon tag differs")
    if stags.get("snapshot_sha256") != expect["snapshot_sha256"] or mtags.get("snapshot_sha256") != expect["snapshot_sha256"]:
        ml_problems.append("snapshot tag differs")
    tags = {k: {t: v for t, v in r.data.tags.items() if not t.startswith("mlflow.")} for k, r in runs.items()}
    out = {"event_count": len(events), "event_types": [(e["run"]["runId"][:8], e["job"]["name"], e["eventType"]) for e in events],
           "event_file_sha256": sha((work / expect["events_path"]).read_bytes()),
           "openlineage_consistency_problems": problems, "detector_control_problems": control,
           "detector_control_flagged": control_all_flagged,
           "detector_controls": {k: {"flagged": bool(v), "problems": v[:3]} for k, v in control_results.items()},
           "mlflow_inputs": inputs, "mlflow_tags": tags,
           "mlflow_params": {k: r.data.params for k, r in runs.items()}, "mlflow_problems": ml_problems,
           "openlineage_schema_validation": schema,
           "all_ok": not problems and control_all_flagged and not ml_problems and schema.get("all_valid", False) and schema.get("detector_control_flagged", False)}
    (work / "readback.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"all_ok": out["all_ok"], "ol_problems": problems, "controls_flagged": {k: bool(v) for k, v in control_results.items()}, "ml_problems": ml_problems}))
    return 0 if out["all_ok"] else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=("emit", "readback"))
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--spec", help="OpenLineage core JSON schema (spec 2-0-2) for event validation")
    a = ap.parse_args()
    if a.phase == "emit":
        a.work.mkdir(parents=True, exist_ok=False)
        emit(a.work)
        return 0
    return readback(a.work, a.spec)


if __name__ == "__main__":
    raise SystemExit(main())
