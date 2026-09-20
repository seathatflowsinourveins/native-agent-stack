# Executable convergence records

Design v1: one record describes a planned or observed experiment in one lane of
[protocol.json](protocol.json). The existing fifteen evidence fields remain
required. [contract.schema.json](contract.schema.json) defines their shape;
`scripts/validate_convergence.py` additionally checks local artifact hashes and
cross-field consistency. It uses only Python's standard library, reads files,
and never executes a recorded command, installs a tool or calls a model.

```sh
python3 scripts/validate_convergence.py path/to/experiment.json --root . --json
```

Record and artifact paths are canonical repository-relative paths. Absolute
paths, traversal, symlink files and symlink parents are refused. Source and input
files, evaluation rules and observed outputs must have actual SHA-256 matches.
The base revision and primary source revisions are immutable 40- or 64-character
hex identities; the validator does not fetch them or establish that a declared
revision supplied those bytes. Likewise, hashes prove retained byte identity,
not source authenticity, observation truth or that a freeze preceded execution.

## Minimal planned example

This example is valid after creating `fixture.txt` containing exactly `abc`
(without a newline) and saving this JSON as an experiment under the same root.
Its synthetic source/revision and one reused artifact illustrate structure;
they do not qualify a real implementation. Actual experiments retain distinct
source, input and evaluation artifacts where their contents differ.

```json
{
  "schema_version": 1,
  "kind": "convergence_experiment",
  "status": "planned",
  "lane": "native-agent-engineering",
  "task_and_failure": "Synthetic patch fixture; correctness is not observed yet.",
  "primary_sources_and_pins": [{"url": "https://example.org/fixture", "revision": "0000000000000000000000000000000000000000"}],
  "discovery_provenance": ["A measured local workflow gap."],
  "license_and_compatibility": "Synthetic public fixture; no dependencies.",
  "baseline_and_candidate": {"baseline": "full context", "candidate": "scoped context"},
  "frozen_inputs": {
    "base_revision": "0000000000000000000000000000000000000000",
    "tasks": ["patch-a"], "roles": ["worker"],
    "sources": [{"path": "fixture.txt", "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"}],
    "inputs": [{"path": "fixture.txt", "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"}],
    "evaluation": [{"path": "fixture.txt", "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"}]
  },
  "predeclared_metrics": {"quality_rule": "Patch passes held-out tests and review.", "usage_rule": "Keep unknown usage null; no savings claim."},
  "runtime_and_platform": {"platform": "disposable fixture", "tools": [{"name": "python", "version": "3.13.15"}], "isolation": "Separate project workspace."},
  "commands": ["python3 -m unittest"],
  "observations": [],
  "failures_and_skips": [],
  "limitations": ["Synthetic plan; no execution or model outcome."],
  "decision_and_scope": {"decision": "trial", "scope": "fixture only", "qualification_run_ids": []},
  "rollback": "Retain the accepted workflow; discard the disposable candidate.",
  "next_decision_changing_test": "Execute the frozen patch fixture.",
  "usage_assessment": {"claim": "none", "coverage": "partial", "expected_run_ids": [], "coverage_artifact": null}
}
```

## Observations and decisions

An observed record contains at least one run. Each run names a unique `id`, a
declared `task` and `role`, `condition` (`baseline` or `candidate`), positive
`attempt`, `command_index` into `commands`, `evidence_class`, exact `scope`,
`status` (`passed`, `failed` or `skipped`), nullable `exit_code`, `quality`
(`semantic` and `contract`, each boolean or null), nonempty hashed `artifacts`,
and `usage`. Every non-passed run also appears once in `failures_and_skips` as
`{"run_id": "…", "reason": "…"}`. Pre-execution or unparsed failures may have
unknown exit status. A process exit of zero does not imply semantic acceptance.

Planned records have no runs, failures, qualifications or usage claim.
`adopt_within_scope` requires observed, passed candidate runs with exit zero,
both quality checks true, matching decision scope, and an execution evidence
class (`offline_artifact_check`, `native_cli_execution`, `model_task_execution`
or `recovery_execution`). Discovery and source review cannot qualify adoption.
Each qualification must be the latest numbered candidate attempt for its
task/role/scope. A later failed or skipped attempt prevents reuse of an earlier
success; an earlier failure followed by a qualifying success remains recorded.
This is a necessary evidence check, not authority to install or promote globally.

## Usage and matched comparisons

Every run has the same nullable, nonnegative integer fields in `usage`:
`uncached_input`, `cache_creation`, `cache_read`, `output`,
`reasoning_in_output`, `total`, and `native_retries`. The three input categories
are **disjoint**; output already includes reasoning. When all four disjoint
categories are known, their sum must equal `total`. Reasoning cannot exceed
output. Unknown provider fields remain null; deterministic no-model work may
record observed zeros, but missing telemetry must not be converted to zero.
Usage is the aggregate for one invocation, including any known native retries;
an outer resubmission is a separate numbered attempt, never counted twice.

`usage_assessment.coverage = complete` requires an exact list of observed run IDs
and a hashed JSON `coverage_artifact` containing exactly
`{"run_ids": ["…"], "complete": true}`. This is an explicit audit assertion;
software cannot discover omitted external calls. `whole_task_token_savings`
additionally requires every declared task/role in both conditions, consecutive
attempt numbers from one, equal passing attempt counts for each task/role pair,
execution evidence in the declared scope, complete known usage/retry categories,
passed quality for every attempt, and strictly lower summed candidate tokens.
Unequal outer resubmission counts remain reportable observations, but this v1
contract conservatively refuses their savings claim. Extra baseline attempts
must not manufacture a saving. Failed attempts remain retained and also prevent
accepted efficiency. All coordinator,
preparation, review and other roles in the actual task boundary must be declared;
excluded roles or attempts make coverage partial; any unknown usage prevents
this claim even when the attempt inventory is complete.

Matching uses the record's frozen tasks, source/input/evaluation references and
quality rule. The validator cannot establish independent grading, comparable
native account/hook/cache conditions, a truly exhaustive task boundary, causal
savings, billing savings or general superiority. Retain those limitations and
inspect the underlying evidence. Report per-task observations before drawing
broader conclusions; a cheaper failed answer is not accepted efficiency.
