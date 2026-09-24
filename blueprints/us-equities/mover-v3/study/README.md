# Mover v3 core: study code tree (draft)

This is the code that `../protocol-core-draft.json` preregisters. The protocol is still a draft
(`frozen_before_outcomes: false`), so every command that fetches or evaluates stage data refuses to run
(`core/guards.py`, `core/runner.py`). No market data has been read and no outcome has been computed. Every test
input is synthetic.

## Layout

| Path | Protocol section |
|---|---|
| `core/plan.py`, `core/stage.py`, `core/driver.py` | the request plan and the fetch loop: symbols, asof, stamps, entry, exit, search and backward windows, the collection batch (`run_discipline.fetch`, review round 8 R8-1) |
| `fetch/transport.py` | the transport only: HTTP client, authentication, pagination and retry (`run_discipline.transport_deviations`) |
| `core/records.py`, `core/store.py` | response parsing, the sealed snapshot, the ledger records and the corporate-action date fields |
| `core/identity.py`, `core/screen.py`, `core/events.py` | `universe_and_identity`, the screen, dedup (pinned `dedupe_identity` through DuckDB, E1) and D membership |
| `core/formulas.py`, `core/fills.py`, `core/costs.py`, `core/trades.py` | `populations`, `arms`, `cost_model` and the net return |
| `core/terciles.py`, `core/chronology.py`, `core/stats.py`, `core/evaluate.py` | `tercile_rule`, `chronology`, `statistics`, `multiple_testing` and `outcome_reporting` |
| `core/count_unit.py`, `core/gate.py`, `core/logs.py`, `core/guards.py`, `core/runner.py` | the holdout count, the gate, the access log, the evaluator refusals, the append-only files and the runtime lock |
| `core/count_only.py`, `core/coverage_rule.py` | the pre-freeze count-only code and `coverage_rule.decided_by_code` |
| `core/transport_check.py` | the transport-deviation reproduction check |
| `pinned/`, `pinned_copies.json` | byte-for-byte copies of the aa6fc79 definitions (`run_discipline.pinned_copies`) |
| `core/params.py` | every parameter; equal to `run_discipline.study_code.parameters` |
| `runtime.lock`, `runtime-requirements.txt` | the pinned runtime |

Data files that are appended after the freeze (`../data/`), the run log, the access log and the deviations file sit
outside this tree, so appending to them never changes the tree hash.

## Tests

From the repository root:

```
uv run --no-project --managed-python --python 3.13.15 \
  --with-requirements blueprints/us-equities/mover-v3/study/runtime-requirements.txt \
  python -m unittest discover -s blueprints/us-equities/mover-v3/study/tests -t blueprints/us-equities/mover-v3/study
```

The tests need the repository's git objects, because the pinned copies are checked against their blobs. They make
no network call: the fake client in `tests/synth.py` stands in for the provider. They are synthetic tests of locally
written code. They are not upstream acceptance and not a native run against the provider.
