"""Resumable, source-based LongMemEval comparison; imports adapters lazily."""

import argparse
import json
import os
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .data import file_sha256, load_questions, stratified_subset
from .protocol import CompletionFailure, run_question
from .score import recall_at_k, score_record
from .stats import accuracy
from .types import ModelRoute


def _write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def _read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = path.read_bytes()
    records = []
    offset = 0
    lines = raw.splitlines(keepends=True)
    seen = set()
    for index, line in enumerate(lines):
        if not line.strip():
            offset += len(line)
            continue
        try:
            record = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            if index != len(lines) - 1 or line.endswith(b"\n"):
                raise ValueError(f"Corrupt records.jsonl at line {index + 1}") from None
            # A killed append can leave a partial final line. Keep the original
            # fragment for inspection and recover the last complete checkpoint.
            path.with_name("records.partial").write_bytes(line)
            with path.open("r+b") as stream:
                stream.truncate(offset)
            break
        qid = record["question_id"]
        if qid in seen:
            raise ValueError(f"Duplicate completed question id: {qid}")
        if record.get("status") != "complete" or not isinstance(record.get("autoeval_label", {}).get("label"), bool):
            raise ValueError(f"Incomplete record in records.jsonl for {qid}")
        seen.add(qid)
        records.append(record)
        offset += len(line)
    else:
        if raw and not raw.endswith(b"\n"):
            with path.open("ab") as stream:
                stream.write(b"\n")
    return records


def _write_hypotheses(path: Path, records: list[dict[str, Any]], question_order: list[str]) -> None:
    by_id = {record["question_id"]: record for record in records}
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        for qid in question_order:
            if qid in by_id:
                record = by_id[qid]
                stream.write(json.dumps(
                    {"question_id": qid, "hypothesis": record["hypothesis"]},
                    ensure_ascii=False, allow_nan=False,
                ) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def _usage_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    stages: dict[str, list[dict[str, Any] | None]] = defaultdict(list)
    for record in records:
        for call in record["model_calls"]:
            stages[call["stage"]].append(call["usage"])
    summary = {}
    for stage, usages in sorted(stages.items()):
        counters = {}
        for counter in ("prompt_tokens", "completion_tokens", "total_tokens"):
            reported = [
                usage[counter] for usage in usages
                if usage is not None and isinstance(usage.get(counter), int)
                and not isinstance(usage[counter], bool)
            ]
            counters[counter] = {
                "reported_sum": sum(reported) if reported else None,
                "reporting_calls": len(reported),
            }
        summary[stage] = {
            "calls": len(usages),
            "unreported_calls": sum(usage is None for usage in usages),
            "counters": counters,
        }
    return summary


def _merge_attempts(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    if previous is None:
        return current
    result = dict(current)
    result["model_calls"] = [*previous["model_calls"], *current["model_calls"]]
    result["seconds"] = previous["seconds"] + current["seconds"]
    result["ingest_attempts"] = [
        *previous.get("ingest_attempts", [previous["ingest"]]),
        *current.get("ingest_attempts", [current["ingest"]]),
    ]
    return result


def summarize(
    records: list[dict[str, Any]], config: dict[str, Any],
    pending: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    completed_ids = {record["question_id"] for record in records}
    unfinished = [record for record in (pending or []) if record["question_id"] not in completed_ids]
    observed = records + unfinished
    groups: dict[str, list[bool]] = defaultdict(list)
    for record in records:
        groups[record["question_type"]].append(record["autoeval_label"]["label"])
    # Never infer the provenance of one question from another question's hits.
    reports_ids = any(record.get("session_ids_reported") is True for record in records)
    recalls = [
        recall_at_k(record, config["k"])
        for record in records
    ]
    eligible = [value for value in recalls if value is not None]
    ingestions = [ingest for record in observed for ingest in record.get("ingest_attempts", [record["ingest"]])]
    unknown_ingest_calls = sum(ingest["llm_calls"] is None for ingest in ingestions)
    known_ingest_calls = [ingest["llm_calls"] for ingest in ingestions if ingest["llm_calls"] is not None]
    return {
        "config": config,
        "status": "complete" if len(records) == len(config["question_ids"]) else "partial",
        "completed": len(records),
        "pending_questions": len(unfinished),
        "expected": len(config["question_ids"]),
        "accuracy": accuracy([record["autoeval_label"]["label"] for record in records]),
        "accuracy_by_type": {qtype: accuracy(labels) for qtype, labels in sorted(groups.items())},
        "recall_at_k": {
            "k": config["k"], "eligible_questions": len(eligible),
            "mean": sum(eligible) / len(eligible) if eligible else None,
            "reports_session_ids": reports_ids,
            "measure": "coverage_of_reported_session_ids",
            "partial_provenance_questions": sum(
                value is not None and record.get("provenance") == "partial"
                for record, value in zip(records, recalls, strict=True)
            ),
            "unscored_questions": len(records) - len(eligible),
        },
        "seconds": sum(record["seconds"] for record in observed),
        "ingest_seconds": sum(ingest["seconds"] for ingest in ingestions),
        "ingest_llm_calls": {
            "reported_sum": sum(known_ingest_calls) if known_ingest_calls else None,
            "unreported_attempts": unknown_ingest_calls,
        },
        "model_usage": _usage_summary(observed),
        "adapter_model_usage": None,
        "notes": ["Adapter model-token usage is not exposed by the fixed MemoryAdapter protocol."],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-arms", action="store_true")
    parser.add_argument("--arm")
    parser.add_argument("--data", type=Path)
    parser.add_argument("--n", type=int, default=60)
    parser.add_argument("--seed", type=int, default=20261002)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--answer-model")
    parser.add_argument("--judge-model")
    parser.add_argument("--base-url")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--limit", type=int, help="Maximum newly completed questions this invocation")
    parser.add_argument("--token-cap", type=int, default=32_768, help="Conservative prompt-token budget; see README")
    parser.add_argument("--api-key-env", default="H2H_API_KEY")
    parser.add_argument("--judge-base-url", help="Defaults to --base-url")
    parser.add_argument("--judge-api-key-env", help="Defaults to --api-key-env")
    parser.add_argument("--memory-model", help="Memory-system LLM; defaults to --answer-model")
    parser.add_argument("--memory-base-url", help="Defaults to --base-url")
    parser.add_argument("--memory-api-key-env", help="Defaults to --api-key-env")
    parser.add_argument("--embed-model", help="Embedding model id; omitted means no embedding route")
    parser.add_argument("--embed-base-url", help="Defaults to --base-url")
    parser.add_argument("--embed-api-key-env", help="Defaults to --api-key-env")
    parser.add_argument("--allow-custom-data", action="store_true", help="Allow a file whose hash differs from pinned cleaned S")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    # Even discovering adapters occurs only after argument parsing.
    from . import adapters

    if args.list_arms:
        print("\n".join(adapters.list_arms()))
        return 0
    required = ("arm", "data", "answer_model", "judge_model", "base_url", "out")
    missing = ["--" + name.replace("_", "-") for name in required if getattr(args, name) is None]
    if missing:
        parser.error("required arguments: " + ", ".join(missing))
    if args.n <= 0 or args.k < 0 or args.token_cap <= 0 or (args.limit is not None and args.limit < 0):
        parser.error("n and token-cap must be positive; k and limit must be nonnegative")
    with (Path(__file__).resolve().parents[1] / "pins.json").open(encoding="utf-8") as stream:
        pins = json.load(stream)
    expected = pins["longmemeval"]["dataset"]["expected_sha256"]
    data_hash = file_sha256(args.data)
    if data_hash != expected and not args.allow_custom_data:
        raise ValueError("Dataset is not the pinned cleaned S release; use --allow-custom-data only for a custom fixture")
    questions = stratified_subset(load_questions(args.data), args.n, args.seed)
    answer = ModelRoute(args.base_url, args.answer_model, args.api_key_env)
    judge = ModelRoute(args.judge_base_url or args.base_url, args.judge_model, args.judge_api_key_env or args.api_key_env)
    memory = ModelRoute(args.memory_base_url or args.base_url, args.memory_model or args.answer_model, args.memory_api_key_env or args.api_key_env)
    embed = ModelRoute(args.embed_base_url or args.base_url, args.embed_model, args.embed_api_key_env or args.api_key_env) if args.embed_model else None
    adapter = adapters.build(args.arm)
    if adapter.name != args.arm:
        raise ValueError("Adapter name does not match the requested arm")
    config = {
        "schema_version": 1,
        "arm": adapter.name, "version": adapter.version,
        "longmemeval_commit": pins["longmemeval"]["commit"],
        "dataset_sha256": data_hash, "pinned_cleaned_s": data_hash == expected,
        "n": args.n, "seed": args.seed, "k": args.k, "token_cap": args.token_cap,
        "prompt_budget_method": "utf8_bytes_plus_32_chat_framing",
        "answer_route": asdict(answer), "judge_route": asdict(judge),
        "memory_route": asdict(memory), "embed_route": asdict(embed) if embed else None,
        "question_ids": [question.question_id for question in questions],
        "question_types": dict(sorted(Counter(question.question_type for question in questions).items())),
    }
    # ModelRoute includes only environment variable names, never their values.
    for route in (answer, judge, memory, embed):
        if route is not None:
            from urllib.parse import urlsplit
            base = urlsplit(route.base_url)
            if base.scheme not in ("http", "https") or not base.hostname or base.username is not None or base.password is not None or base.query or base.fragment:
                raise ValueError("Model route URLs cannot contain credentials, queries or fragments")
            if not route.model or not route.api_key_env.isidentifier():
                raise ValueError("Invalid model route or API key environment variable name")
    out = args.out / args.arm
    out.mkdir(mode=0o700, parents=True, exist_ok=True)
    manifest = out / "run.json"
    if manifest.exists():
        if json.loads(manifest.read_text(encoding="utf-8")) != config:
            raise ValueError("Resume configuration differs from the existing run; choose a new output directory")
    else:
        _write_json(manifest, config)
    records_path = out / "records.jsonl"
    records = _read_records(records_path)
    finished = {record["question_id"] for record in records}
    if not finished.issubset(config["question_ids"]):
        raise ValueError("Completed records contain questions outside the selected subset")
    pending_path = out / "pending.json"
    pending = json.loads(pending_path.read_text(encoding="utf-8")) if pending_path.exists() else {}
    if not set(pending).issubset(config["question_ids"]):
        raise ValueError("Pending records contain questions outside the selected subset")
    for qid in finished:
        pending.pop(qid, None)
    todo = [question for question in questions if question.question_id not in finished]
    if args.limit is not None:
        todo = todo[:args.limit]
    started_adapter = False
    try:
        for question in todo:
            record = pending.get(question.question_id)
            if record is None or record.get("status") == "answer_failed":
                if not started_adapter:
                    started_adapter = True
                    workdir = out / "system"
                    workdir.mkdir(mode=0o700, parents=True, exist_ok=True)
                    adapter.start(workdir, memory, embed)
                previous = record
                try:
                    record = run_question(adapter, question, args.k, answer, args.token_cap)
                except CompletionFailure as exc:
                    if exc.record is not None:
                        exc.record = _merge_attempts(previous, exc.record)
                    raise
                record = _merge_attempts(previous, record)
                pending[question.question_id] = record
                _write_json(pending_path, pending)
            if record.get("status") != "complete":
                record = score_record(record, question, judge)
                # Preserve a successful judge result before the records append;
                # replaying a torn append then needs no second model call.
                pending[question.question_id] = record
                _write_json(pending_path, pending)
            with records_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            records.append(record)
            pending.pop(question.question_id, None)
            _write_json(pending_path, pending)
            print(f"{adapter.name}: {len(records)}/{len(questions)} completed", flush=True)
    except CompletionFailure as exc:
        if exc.record is not None:
            pending[exc.record["question_id"]] = exc.record
            _write_json(pending_path, pending)
        raise
    finally:
        try:
            if started_adapter:
                adapter.stop()
        finally:
            _write_hypotheses(out / "hypotheses.jsonl", records, config["question_ids"])
            _write_json(out / "summary.json", summarize(records, config, list(pending.values())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
