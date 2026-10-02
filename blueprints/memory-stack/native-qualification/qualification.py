"""Inspect offline scoring of independently collected native-memory evidence.

This module executes no clients, bridges or model calls. ``synthetic_pipeline`` is
an explicitly synthetic plumbing check. Promotion consumes Inspect logs and
independently observed, hashed operational evidence; absent observations fail.
Upstream interface: inspect-ai 0.3.275, official solver/scorer/dataset/log APIs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.log import read_eval_log
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import Score, Target, mean, scorer, stderr
from inspect_ai.solver import Generate, TaskState, solver
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr

Scalar = StrictStr | StrictInt | StrictFloat | StrictBool | None
Arm = Literal["native_files", "ai_memory", "hindsight"]
Mode = Literal["common_retrieval", "tuned_pipeline"]
Split = Literal["dev", "holdout"]
ARMS = ("native_files", "ai_memory", "hindsight")
MODES = ("common_retrieval", "tuned_pipeline")
OPERATIONAL_GATES = (
    "scope_isolation", "effective_hook_isolation", "fresh_session_recall",
    "compact_resume", "cross_client_handoff", "duplicate_effect_prevention",
    "crash_after_claim_recovery", "backend_unavailable_recovery",
    "interrupted_tool_recovery", "backup_restore", "latency_budget",
    "blind_cross_family", "canary_20_sessions_2_restarts",
)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Fact(Contract):
    fact_id: str
    value: Scalar
    source_ids: list[str]


class Expected(Contract):
    answer_type: Literal["answer", "abstain"]
    required_facts: list[Fact]
    forbidden_facts: list[Fact]
    citation_source_ids: list[str]
    abstention_reason: str | None


class Provenance(Contract):
    synthetic: Literal[True]
    authored_by: str
    exposure: Literal["development", "sealed-authored-holdout"]


class Case(Contract):
    case_id: str
    scenario_id: str
    split: Split
    category: str
    input: str
    query_time: str
    source_ids: list[str]
    expected: Expected
    provenance: Provenance


class Source(Contract):
    source_id: str
    path: str
    sha256: str
    scenario_id: str
    split: Split
    recorded_at: str
    available_from: str
    effective_at: str
    effective_until: str | None
    authority: str
    supersedes: list[str]
    supported_facts: dict[str, Scalar]
    supports_abstention: list[str]


class Answer(Contract):
    answer_type: Literal["answer", "abstain"]
    facts: dict[str, Scalar]
    as_of: str
    abstention_reason: str | None


class Citation(Contract):
    fact_id: str
    source_id: str
    source_sha256: str


class Evidence(Contract):
    path: str
    sha256: str
    kind: Literal["native_transcript", "synthetic_fixture"]


class Accounting(Contract):
    input_tokens: StrictInt | None = Field(default=None, ge=0)
    output_tokens: StrictInt | None = Field(default=None, ge=0)
    cost_usd: StrictFloat | StrictInt | None = Field(default=None, ge=0)


class Runtime(Contract):
    actual: bool
    client: Literal["codex", "claude", "synthetic"]
    model: str | None = None
    model_family: str | None = None
    version: str | None = None
    run_id: str
    started_at: str
    completed_at: str
    corpus_freeze_id: str
    pipeline_config_sha256: str
    holdout_exposed: bool
    accounting: Accounting = Field(default_factory=Accounting)
    latency_ms: StrictFloat | StrictInt | None = Field(default=None, ge=0)


class Result(Contract):
    case_id: str
    arm: Arm
    mode: Mode
    split: Split
    answer: Answer
    citations: list[Citation]
    evidence: Evidence
    runtime: Runtime


# Inspect loads task files in a transient module; resolve Pydantic aliases using
# this module's namespace before its task loader discards that namespace.
for _contract in (Fact, Expected, Provenance, Case, Source, Answer, Citation, Evidence, Accounting, Runtime, Result):
    _contract.model_rebuild(_types_namespace=globals())


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: str) -> bool:
    return len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _time(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return result


def _same(left: Any, right: Any) -> bool:
    # JSON booleans must not silently equal integer 1/0.
    return type(left) is type(right) and left == right


def _verified_path(base: Path, path: str, digest: str) -> Path:
    candidate = (base / path).resolve()
    if Path(path).is_absolute() or not candidate.is_relative_to(base.resolve()):
        raise ValueError(f"evidence path escapes its declared root: {path}")
    if not _digest(digest) or not candidate.is_file() or sha256_file(candidate) != digest:
        raise ValueError(f"missing file or sha256 mismatch: {path}")
    return candidate


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _unique(rows: list[Any], key: str) -> dict[str, Any]:
    result = {}
    for row in rows:
        identity = getattr(row, key)
        if not identity or identity in result:
            raise ValueError(f"empty or duplicate {key}: {identity}")
        result[identity] = row
    return result


def _source_current(source: Source, query_time: datetime) -> bool:
    return (_time(source.available_from) <= query_time
            and _time(source.effective_at) <= query_time
            and (source.effective_until is None or query_time < _time(source.effective_until)))


def load_inputs(cases: Path | str, sources: Path | str, results: Path | str, *,
                arm: str, mode: str, split: str, freeze_id: str,
                corpus_manifest: Path | str, manifest_sha256: str,
                allow_synthetic: bool = False) -> list[dict[str, Any]]:
    """Validate full coverage, provenance, split identity and actual runtime labels."""
    cases, sources, results = Path(cases), Path(sources), Path(results)
    corpus_manifest = Path(corpus_manifest)
    if not _digest(manifest_sha256) or sha256_file(corpus_manifest) != manifest_sha256:
        raise ValueError("frozen corpus manifest sha256 mismatch")
    manifest = json.loads(corpus_manifest.read_text())
    frozen_split = manifest.get("splits", {}).get(split, {})
    case_digest, registry_digest = sha256_file(cases), sha256_file(sources)
    if (manifest.get("corpus_freeze_id") != freeze_id
            or frozen_split.get("cases_sha256") != case_digest
            or frozen_split.get("sources_registry_sha256") != registry_digest):
        raise ValueError("case/source bytes differ from independently frozen corpus manifest")
    case_map = _unique([Case.model_validate(row) for row in _jsonl(cases)], "case_id")
    source_map = _unique([Source.model_validate(row) for row in json.loads(sources.read_text())], "source_id")
    result_map = _unique([Result.model_validate(row) for row in _jsonl(results)], "case_id")
    if not case_map or set(result_map) != set(case_map):
        raise ValueError("result case ids must exactly cover the nonempty case set")
    if frozen_split.get("case_count") != len(case_map) or frozen_split.get("source_count") != len(source_map):
        raise ValueError("frozen corpus case/source totals mismatch")
    if arm not in ARMS or mode not in MODES or split not in ("dev", "holdout") or not freeze_id:
        raise ValueError("explicit valid arm, mode, split and freeze id are required")
    for source in source_map.values():
        _verified_path(sources.parent, source.path, source.sha256)
        for value in (source.recorded_at, source.available_from, source.effective_at):
            _time(value)
        if source.effective_until is not None and _time(source.effective_until) <= _time(source.effective_at):
            raise ValueError("source effective interval is empty")
        if not source.authority or not set(source.supersedes) <= source_map.keys():
            raise ValueError("source authority or supersedes provenance missing")
    output = []
    for identity, case in case_map.items():
        record = result_map[identity]
        runtime = record.runtime
        query_time = _time(case.query_time)
        if (case.split != split or record.split != split or record.arm != arm or record.mode != mode):
            raise ValueError(f"case/result arm, mode or split mismatch: {identity}")
        exposure = "development" if split == "dev" else "sealed-authored-holdout"
        if case.provenance.exposure != exposure or not case.provenance.authored_by:
            raise ValueError("case exposure/provenance is inconsistent with its split")
        if not case.category or not case.input or not case.source_ids or len(set(case.source_ids)) != len(case.source_ids):
            raise ValueError("case category/input/source identity missing or duplicated")
        relevant = {}
        for source_id in case.source_ids:
            source = source_map.get(source_id)
            if source is None or source.split != split or source.scenario_id != case.scenario_id:
                raise ValueError(f"case source scope/split mismatch: {identity}/{source_id}")
            relevant[source_id] = source
        expected = case.expected
        if not expected.citation_source_ids or not set(expected.citation_source_ids) <= relevant.keys():
            raise ValueError("expected citation source provenance missing")
        facts = expected.required_facts
        if len({fact.fact_id for fact in facts}) != len(facts):
            raise ValueError("duplicate required fact id")
        if expected.answer_type == "answer" and (not facts or expected.abstention_reason is not None):
            raise ValueError("answer target requires facts and no abstention reason")
        if expected.answer_type == "abstain" and (facts or not expected.abstention_reason):
            raise ValueError("abstention target requires reason and no asserted facts")
        for fact in facts:
            if (not fact.fact_id or not fact.source_ids or not set(fact.source_ids) <= set(expected.citation_source_ids)
                    or not all(_same(relevant[s].supported_facts.get(fact.fact_id), fact.value)
                               and fact.fact_id in relevant[s].supported_facts
                               and _source_current(relevant[s], query_time) for s in fact.source_ids)):
                raise ValueError(f"target fact lacks current source support: {fact.fact_id}")
        if expected.answer_type == "abstain" and not any(
            expected.abstention_reason in relevant[s].supports_abstention
            and _source_current(relevant[s], query_time) for s in expected.citation_source_ids
        ):
            raise ValueError("abstention target lacks source support")
        if runtime.corpus_freeze_id != freeze_id or not _digest(runtime.pipeline_config_sha256):
            raise ValueError("corpus freeze or pipeline configuration provenance mismatch")
        if not runtime.run_id or _time(runtime.completed_at) < _time(runtime.started_at):
            raise ValueError("runtime identity or timestamps invalid")
        if runtime.actual:
            if (runtime.client == "synthetic" or not all((runtime.model, runtime.model_family, runtime.version))
                    or record.evidence.kind != "native_transcript"):
                raise ValueError("actual runtime metadata/provenance incomplete")
        elif not allow_synthetic or runtime.client != "synthetic" or record.evidence.kind != "synthetic_fixture":
            raise ValueError("synthetic results cannot be ingested as native runtime evidence")
        _verified_path(results.parent, record.evidence.path, record.evidence.sha256)
        output.append({"case": case.model_dump(), "sources": {k: v.model_dump() for k, v in relevant.items()},
                       "freeze": {"manifest_sha256": manifest_sha256, "cases_sha256": case_digest,
                                  "sources_registry_sha256": registry_digest,
                                  "parent_manifest_sha256": manifest.get("parent_manifest_sha256")},
                       "record": record.model_dump()})
    return output


def score_record(case: dict[str, Any], sources: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """All required facts, citation attribution and temporal checks must pass."""
    case_obj, result = Case.model_validate(case), Result.model_validate(record)
    source_map = {k: Source.model_validate(v) for k, v in sources.items()}
    answer, expected = result.answer, case_obj.expected
    required = {f.fact_id: f for f in expected.required_facts}
    expected_values = {k: f.value for k, f in required.items()}
    checks = {
        "case_identity": result.case_id == case_obj.case_id and result.split == case_obj.split,
        "answer_type": answer.answer_type == expected.answer_type,
        "facts": set(answer.facts) == set(expected_values)
            and all(_same(answer.facts[k], value) for k, value in expected_values.items()),
        "no_forbidden_claim": not any(f.fact_id in answer.facts and _same(answer.facts[f.fact_id], f.value)
                                       for f in expected.forbidden_facts),
        "abstention": answer.abstention_reason == expected.abstention_reason,
        "answer_time": _time(answer.as_of) == _time(case_obj.query_time),
        "citations": bool(result.citations),
    }
    covered = set()
    covered_pairs = set()
    seen = set()
    for citation in result.citations:
        source = source_map.get(citation.source_id)
        key = (citation.fact_id, citation.source_id)
        valid = (key not in seen and source is not None
                 and citation.source_id in expected.citation_source_ids
                 and citation.source_id in case_obj.source_ids)
        seen.add(key)
        if valid:
            valid = (citation.source_sha256 == source.sha256
                     and source.split == case_obj.split and source.scenario_id == case_obj.scenario_id
                     and _source_current(source, _time(case_obj.query_time)))
        if valid and expected.answer_type == "abstain":
            valid = citation.fact_id == "$abstention" and expected.abstention_reason in source.supports_abstention
        elif valid:
            fact = required.get(citation.fact_id)
            valid = (fact is not None and citation.source_id in fact.source_ids
                     and citation.fact_id in source.supported_facts
                     and _same(source.supported_facts[citation.fact_id], fact.value))
        checks["citations"] = checks["citations"] and valid
        if valid:
            covered.add(citation.fact_id)
            covered_pairs.add(key)
    checks["citation_coverage"] = covered == (set(required) if expected.answer_type == "answer" else {"$abstention"})
    checks["required_source_coverage"] = all((fact.fact_id, sid) in covered_pairs
                                             for fact in required.values() for sid in fact.source_ids)
    return {"score": int(all(checks.values())), "checks": checks}


@solver
def recorded_response():
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        record = state.metadata["record"]
        state.output = ModelOutput.from_content(record["runtime"]["model"] or "synthetic-offline",
                                               json.dumps(record["answer"], sort_keys=True))
        state.messages.append(state.output.message)
        return state
    return solve


@scorer(metrics=[mean(), stderr()])
def native_contract_score():
    async def score(state: TaskState, target: Target) -> Score:
        result = score_record(state.metadata["case"], state.metadata["sources"], state.metadata["record"])
        return Score(value=result["score"], answer=state.output.completion,
                     explanation=json.dumps(result["checks"], sort_keys=True), metadata=result["checks"])
    return score


def _inspect_task(inputs: list[dict[str, Any]], synthetic: bool) -> Task:
    return Task(dataset=MemoryDataset([Sample(id=row["case"]["case_id"], input=row["case"]["input"],
                                             target=json.dumps(row["case"]["expected"]), metadata=row)
                                      for row in inputs]),
                solver=recorded_response(), scorer=native_contract_score(),
                metadata={"evidence_class": "synthetic_pipeline" if synthetic else "native_offline_scoring",
                          "runtime_quality_claim": False if synthetic else "limited_to_collected_native_records"})


@task
def native_qualification(cases: str, sources: str, results: str, arm: str, mode: str,
                         split: str, corpus_freeze_id: str, corpus_manifest: str,
                         corpus_manifest_sha256: str) -> Task:
    return _inspect_task(load_inputs(cases, sources, results, arm=arm, mode=mode, split=split,
                                    freeze_id=corpus_freeze_id, corpus_manifest=corpus_manifest,
                                    manifest_sha256=corpus_manifest_sha256), False)


@task
def synthetic_pipeline(cases: str, sources: str) -> Task:
    """Inspect plumbing only; cannot consume holdout or produce promotable evidence."""
    case_rows = [Case.model_validate(row) for row in _jsonl(Path(cases))]
    source_map = _unique([Source.model_validate(row) for row in json.loads(Path(sources).read_text())], "source_id")
    inputs = []
    for case in case_rows:
        if case.split != "dev":
            raise ValueError("synthetic_pipeline is restricted to development cases")
        relevant = {sid: source_map[sid].model_dump() for sid in case.source_ids}
        citations = [dict(fact_id=f.fact_id, source_id=sid, source_sha256=source_map[sid].sha256)
                     for f in case.expected.required_facts for sid in f.source_ids]
        if case.expected.answer_type == "abstain":
            sid = next(s for s in case.expected.citation_source_ids
                       if case.expected.abstention_reason in source_map[s].supports_abstention)
            citations = [dict(fact_id="$abstention", source_id=sid, source_sha256=source_map[sid].sha256)]
        source = source_map[case.source_ids[0]]
        record = Result.model_validate(dict(case_id=case.case_id, arm="native_files", mode="common_retrieval", split="dev",
            answer=dict(answer_type=case.expected.answer_type, facts={f.fact_id: f.value for f in case.expected.required_facts},
                        as_of=case.query_time, abstention_reason=case.expected.abstention_reason), citations=citations,
            evidence=dict(path=source.path, sha256=source.sha256, kind="synthetic_fixture"),
            runtime=dict(actual=False, client="synthetic", run_id="synthetic-plumbing-only",
                         started_at=case.query_time, completed_at=case.query_time, corpus_freeze_id="synthetic-only",
                         pipeline_config_sha256="0" * 64, holdout_exposed=False)))
        for source in relevant.values():
            _verified_path(Path(sources).parent, source["path"], source["sha256"])
        inputs.append({"case": case.model_dump(), "sources": relevant, "record": record.model_dump()})
    if not inputs:
        raise ValueError("synthetic pipeline requires nonempty development cases")
    return _inspect_task(inputs, True)


def _quantile(values: list[float], probability: float) -> float:
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def paired_comparison(rows: list[dict[str, Any]], *, baseline: str, candidate: str,
                      mode: str, iterations: int = 10000, seed: int = 384) -> dict[str, Any]:
    """Category-macro paired bootstrap, stratified by frozen case category."""
    if iterations < 100:
        raise ValueError("at least 100 bootstrap iterations required")
    arms = {baseline: {}, candidate: {}}
    for row in rows:
        if row["split"] == "holdout" and row["mode"] == mode and row["arm"] in arms:
            if row["case_id"] in arms[row["arm"]] or type(row["score"]) not in (int, float) or row["score"] not in (0, 1):
                raise ValueError("duplicate case or invalid score in paired input")
            arms[row["arm"]][row["case_id"]] = row
    if not arms[baseline] or set(arms[baseline]) != set(arms[candidate]):
        raise ValueError("paired comparison requires identical nonempty sample ids")
    groups = defaultdict(list)
    for case_id, control in arms[baseline].items():
        treatment = arms[candidate][case_id]
        if control["category"] != treatment["category"]:
            raise ValueError("paired case category mismatch")
        groups[control["category"]].append(treatment["score"] - control["score"])
    categories = {category: sum(values) / len(values) for category, values in sorted(groups.items())}
    gain = sum(categories.values()) / len(categories)
    rng = random.Random(seed)
    samples = sorted(sum(sum(rng.choices(values, k=len(values))) / len(values) for values in groups.values())
                     / len(groups) for _ in range(iterations))
    ci95 = [_quantile(samples, .025), _quantile(samples, .975)]
    # Three predeclared contrasts x two preplanned looks: familywise error <= .05.
    tail = .05 / (3 * 2 * 2)
    simultaneous = [_quantile(samples, tail), _quantile(samples, 1 - tail)]
    return {"baseline": baseline, "candidate": candidate, "mode": mode, "n_pairs": len(arms[baseline]),
            "category_gains": categories, "gain": gain, "ci95": ci95, "decision_ci": simultaneous,
            "decision_confidence": 1 - .05 / 6,
            "decision_pass": gain >= .05 and simultaneous[0] > 0,
            "tie": gain == 0, "iterations": iterations, "seed": seed}


def _configuration(rows: list[dict[str, Any]]) -> dict[str, str]:
    groups = defaultdict(set)
    for row in rows:
        digest = row["runtime"]["pipeline_config_sha256"]
        if not _digest(digest):
            raise ValueError("pipeline configuration sha256 invalid")
        groups[f'{row["arm"]}/{row["mode"]}'].add(digest)
    if any(len(values) != 1 for values in groups.values()):
        raise ValueError("pipeline retuning/configuration changes within frozen evaluation")
    return {key: next(iter(values)) for key, values in sorted(groups.items())}


def _gate_evidence(name: str, gate: dict[str, Any], freeze_id: str, root: Path | None) -> bool:
    """Receipt consistency, including a separate independent-observer attestation.

    This validator cannot authenticate model-family labels or native execution.
    It checks retained observations and requires independent verification rather
    than treating a hash or a self-reported passed field as runtime acceptance.
    """
    identities = gate.get("observed_ids", [])
    valid = (gate.get("passed") is True and gate.get("actual_native") is True
             and gate.get("arm") == "hindsight" and isinstance(identities, list)
             and bool(identities) and all(isinstance(i, str) and i for i in identities)
             and len(set(identities)) == len(identities)
             and gate.get("corpus_freeze_id") == freeze_id and root is not None)
    if not valid:
        return False
    try:
        path = _verified_path(root, gate["evidence"]["path"], gate["evidence"]["sha256"])
        receipt = json.loads(path.read_text())
        for key in ("passed", "actual_native", "arm", "observed_ids", "corpus_freeze_id"):
            if receipt.get(key) != gate[key]:
                return False
        if receipt.get("gate") != name or receipt.get("evidence_class") != "native_operation":
            return False
        checks = receipt.get("checks", [])
        if not checks or not all(c.get("name") and "expected" in c and "observed" in c and c.get("passed") is True
                                 and _same(c.get("observed"), c.get("expected")) for c in checks):
            return False
        control = receipt.get("discriminating_control", {})
        if not (control.get("observed_failure") is True and control.get("expected_failure") is True
                and control.get("observed_id")):
            return False
        verification = gate["independent_verification"]
        observer_path = _verified_path(root, verification["evidence"]["path"], verification["evidence"]["sha256"])
        observer = json.loads(observer_path.read_text())
        if not (verification.get("verified") is True and observer.get("verified") is True
                and observer.get("observer_id") and observer.get("gate") == name
                and observer.get("receipt_sha256") == gate["evidence"]["sha256"]):
            return False
        if name == "blind_cross_family":
            if not (receipt.get("blinded") is True and len(set(receipt.get("model_families", []))) >= 2
                    and observer.get("native_family_provenance_verified") is True):
                return False
        if name == "backup_restore":
            if not {"database", "external_configuration", "wiki"} <= set(receipt.get("restored_components", [])):
                return False
        if name == "canary_20_sessions_2_restarts":
            if not (len(identities) >= 20 and receipt.get("completed_sessions", 0) >= 20
                    and receipt.get("restarts", 0) >= 2 and {"codex", "claude"} <= set(receipt.get("clients", []))):
                return False
        if name == "latency_budget":
            if not (isinstance(receipt.get("p95_ms"), (int, float))
                    and isinstance(receipt.get("budget_ms"), (int, float))
                    and 0 <= receipt["p95_ms"] <= receipt["budget_ms"] and receipt.get("sample_count", 0) > 0):
                return False
    except (KeyError, ValueError, TypeError, OSError):
        return False
    return True


def promotion_decision(rows: list[dict[str, Any]], gates: dict[str, Any], *, freeze_id: str,
                       manifest_sha256: str,
                       look: str = "initial", previous: dict[str, Any] | None = None,
                       evidence_root: Path | None = None, iterations: int = 10000) -> dict[str, Any]:
    """Fail closed; a quality recommendation and production promotion are distinct."""
    if look not in ("initial", "extension"):
        raise ValueError("look must be initial or the single extension")
    configs = _configuration(rows)
    primary = [r for r in rows if r["mode"] == "tuned_pipeline" and r["split"] == "holdout"]
    identities = {r["case_id"] for r in primary}
    n_expected = 60 if look == "initial" else 120
    if len(identities) != n_expected:
        raise ValueError(f"{look} requires exactly {n_expected} distinct paired holdout cases")
    if look == "extension":
        if (previous is None or previous.get("look") != "initial" or previous.get("extension_used") is not False
                or previous.get("corpus_freeze_id") != freeze_id or previous.get("pipeline_configs") != configs
                or not set(previous.get("case_ids", [])) < identities or len(previous.get("case_ids", [])) != 60
                or previous.get("extension_eligible") is not True):
            raise ValueError("extension requires unchanged frozen configs and the initial 60-case decision")
    comparisons = [paired_comparison(primary, baseline=b, candidate="hindsight", mode="tuned_pipeline",
                                     iterations=iterations) for b in ("native_files", "ai_memory")]
    comparisons.append(paired_comparison(primary, baseline="ai_memory", candidate="native_files",
                                         mode="tuned_pipeline", iterations=iterations))
    reasons = []
    category_counts = Counter(r["category"] for r in primary if r["arm"] == "hindsight")
    if len(category_counts) != 6 or set(category_counts.values()) != {n_expected // 6}:
        reasons.append("holdout must contain six equally represented frozen categories")
    if any(not comparison["decision_pass"] for comparison in comparisons[:2]):
        reasons.append("quality gain/positive simultaneous interval not established against both baselines")
    for row in rows:
        runtime = row["runtime"]
        if not runtime["actual"] or runtime["client"] == "synthetic":
            reasons.append("synthetic runtime cannot establish promotion")
            break
    if any(r["runtime"]["corpus_freeze_id"] != freeze_id for r in rows):
        reasons.append("corpus freeze identifiers mismatch")
    if not _digest(manifest_sha256):
        raise ValueError("independently frozen manifest sha256 required")
    original_ids = set(previous["case_ids"]) if look == "extension" else set()
    for row in rows:
        freeze = row.get("freeze", {})
        if look == "extension" and row["case_id"] in original_ids:
            expected_manifest = previous.get("corpus_manifest_sha256")
        else:
            expected_manifest = manifest_sha256
        if freeze.get("manifest_sha256") != expected_manifest:
            reasons.append("corpus manifest provenance mismatch")
        if look == "extension" and row["case_id"] not in original_ids:
            if freeze.get("parent_manifest_sha256") != previous.get("corpus_manifest_sha256"):
                reasons.append("extension corpus does not reference independently frozen initial manifest")
    if any(r["runtime"]["holdout_exposed"] for r in rows):
        reasons.append("holdout exposed before pipeline freeze")
    gate_results = {}
    for name in OPERATIONAL_GATES:
        gate = gates.get(name, {})
        gate_results[name] = _gate_evidence(name, gate, freeze_id, evidence_root)
    missing = [name for name, passed in gate_results.items() if not passed]
    if missing:
        reasons.append("operational gates unqualified: " + ", ".join(missing))
    pre_canary = all(value for name, value in gate_results.items() if name != "canary_20_sessions_2_restarts")
    inputs_valid = not any("holdout" in r or "synthetic" in r or "corpus" in r for r in reasons)
    quality_ok = inputs_valid and all(c["decision_pass"] for c in comparisons[:2])
    confirmed_operational_failure = any(gates.get(name, {}).get("passed") is False for name in OPERATIONAL_GATES)
    extension_eligible = (look == "initial" and not all(c["decision_pass"] for c in comparisons[:2])
                          and all(c["decision_ci"][1] >= .05 for c in comparisons[:2])
                          and not confirmed_operational_failure
                          and not any("synthetic" in r or "exposed" in r or "freeze" in r for r in reasons))
    return {"promote": not reasons, "candidate_recommendation": quality_ok and pre_canary,
            "native_file_answer_recommendation": inputs_valid and comparisons[2]["decision_pass"]
                and -comparisons[0]["gain"] >= .05 and -comparisons[0]["decision_ci"][1] > 0,
            "production_promotion": not reasons, "reasons": list(dict.fromkeys(reasons)), "gates": gate_results,
            "comparisons": comparisons, "look": look, "extension_used": look == "extension",
            "extension_eligible": extension_eligible,
            "decision_scope": "eligibility only; receipt consistency requires independent native verification",
            "corpus_freeze_id": freeze_id, "pipeline_configs": configs, "case_ids": sorted(identities),
            "corpus_manifest_sha256": manifest_sha256,
            "accounting": {"whole_task_usage": None, "net_savings": None}}


def rows_from_inspect_logs(paths: list[Path]) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for path in paths:
        log = read_eval_log(str(path))
        if log.status != "success" or not log.samples or log.stats.model_usage:
            raise ValueError(f"Inspect log unsuccessful, empty or unexpectedly generated model calls: {path}")
        for sample in log.samples:
            metadata = sample.metadata or {}
            record = Result.model_validate(metadata.get("record"))
            case = Case.model_validate(metadata.get("case"))
            if sample.id != case.case_id or record.case_id != case.case_id or sample.error or sample.model_usage:
                raise ValueError("Inspect sample identity/error mismatch")
            if any(getattr(event, "event", None) == "model" for event in sample.events):
                raise ValueError("offline scoring log unexpectedly contains a ModelEvent")
            scores = sample.scores or {}
            if set(scores) != {"native_contract_score"}:
                raise ValueError("expected exact qualification scorer in Inspect log")
            value = scores["native_contract_score"].value
            independent = score_record(case.model_dump(), metadata["sources"], record.model_dump())["score"]
            if value != independent:
                raise ValueError("Inspect stored score differs from deterministic contract")
            identity = (record.arm, record.mode, record.case_id)
            if identity in seen:
                raise ValueError("duplicate arm/mode/case across Inspect logs")
            seen.add(identity)
            rows.append(dict(case_id=case.case_id, category=case.category, split=case.split,
                             arm=record.arm, mode=record.mode, score=value, runtime=record.runtime.model_dump(),
                             freeze=metadata.get("freeze", {})))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare upstream Inspect logs; runs no clients/models")
    parser.add_argument("logs", type=Path, nargs="+")
    parser.add_argument("--gates", type=Path, required=True)
    parser.add_argument("--corpus-freeze-id", required=True)
    parser.add_argument("--corpus-manifest-sha256", required=True)
    parser.add_argument("--look", choices=("initial", "extension"), default="initial")
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    previous = json.loads(args.previous.read_text()) if args.previous else None
    rows = rows_from_inspect_logs(args.logs)
    decision = promotion_decision(rows, json.loads(args.gates.read_text()),
                                  freeze_id=args.corpus_freeze_id, manifest_sha256=args.corpus_manifest_sha256,
                                  look=args.look, previous=previous,
                                  evidence_root=args.gates.parent)
    diagnostics = []
    if any(row["mode"] == "common_retrieval" for row in rows):
        diagnostics = [paired_comparison(rows, baseline=b, candidate="hindsight", mode="common_retrieval")
                       for b in ("native_files", "ai_memory")]
    decision["common_retrieval_diagnostic"] = diagnostics
    args.output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"promote": decision["promote"], "reasons": decision["reasons"]}))


if __name__ == "__main__":
    main()
