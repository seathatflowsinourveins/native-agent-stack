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
| `core/holdout.py`, `core/holdout_store.py` | the holdout path: authorization, collection batches merged per (symbol, session), counts with the extension decision, the read and the not-read label (review round 9) |
| `core/count_only.py`, `core/coverage_rule.py` | the pre-freeze count-only code and `coverage_rule.decided_by_code` |
| `core/transport_check.py` | the transport-deviation reproduction check (run by `run.py transport-check`, review round 10) |
| `core/transport_proc.py` | the child process that alone imports `fetch/` and returns raw pages (review round 10, H1) |
| `pinned/github-web-flow.gpg` | GitHub's web-flow public key: reach and freeze times come only from commits it signs (review round 10, M3) |
| `pinned/`, `pinned_copies.json` | byte-for-byte copies of the aa6fc79 definitions (`run_discipline.pinned_copies`) |
| `core/params.py` | every parameter; equal to `run_discipline.study_code.parameters` |
| `runtime.lock`, `runtime-requirements.txt` | the pinned runtime |

Data files that are appended after the freeze (`../data/`), the run log, the access log, the deviations file and the
results files (`../results/`) sit outside this tree, so appending to them never changes the tree hash.

## Entry points

`run.py` is the only entry point (`study/runtime.lock` `run_command`, run as `python -I -B`). Before the freeze only
`build-calendar`, `count-only` and `dry-run` run; after it, `fetch` and `evaluate` (development and validation, each
once), `transport-check` (from a tree that changes only `fetch/`) and the holdout commands `authorize`, `amend`,
`collect`, `count` and `read`. `count` and `read` run twice under one authorization: the first run fetches and seals,
the second, after that line is pushed, evaluates over the sealed snapshot. Every command refuses unless its run-log,
access-log and amendment lines are committed and pushed to origin/main (checked against the remote with
`git ls-remote`, and append-only across origin/main's history), and a holdout action runs only under its own committed
authorization record. Freeze and reach times come only from commits signed by the pinned GitHub web-flow key. The
fetch transport runs in a child process; the process that plans, parses and evaluates never imports `fetch/`.
Results files have fixed paths under `../results/`.

Review round 11: `count-only`, `dry-run` and `fetch` also run twice. The first run appends only a start line (protocol
sha256, study tree and, for count-only, the coverage_rule sha256); nothing is fetched until that line is pushed, and
while it has no end line a run with another protocol, tree or rule is refused. Every fetch is paced by the child
process at the protocol's pinned rate limit (`exposure_registry.pre_freeze_access_path.rate_limit`), and every
fetching command refuses while that limit is not pinned. The dry run refuses any planned request that reaches before
2021-01-04 or after 2024-10-31, not only a session outside that window. Development is evaluated only after the
validation fetch line is on origin/main. `transport-check` needs `--holdout-root` once a holdout snapshot is sealed,
and seeds its live sample with the first origin/main commit that holds the new tree. A held-back refused `read`
authorization cannot be spent. A read that sealed its snapshot is always evaluated, and one evaluated after the
deadline carries `late-read`. Holdout due times are judged by the signed time the authorization reached origin/main.

Review round 12: identity dedup runs as of each candidate session over rows of sessions up to it (`core/identity.py`
`dedupe_asof`). A count's or read's `_fetch` line pins its base snapshots and collection batches, and the evaluation
step reads only those; a read whose retry chain sealed a snapshot may be retried after the deadline. `count` and
`read` refuse an authorization whose items differ from the governing validation file's validated items, or whose
record is malformed. Every command refuses a frozen protocol whose count-only output lacks a passing identity probe
and fetch margin at the pinned rate limit. A failed `count-only` or `dry-run` logs every part it sealed.

## Tests

From the repository root:

```
uv run --no-project --managed-python --python 3.13.15 \
  --with-requirements blueprints/us-equities/mover-v3/study/runtime-requirements.txt \
  python -m unittest discover -s blueprints/us-equities/mover-v3/study/tests -t blueprints/us-equities/mover-v3/study
```

The tests need the repository's git objects, because the pinned copies are checked against their blobs and a real
origin/main squash merge is verified against the pinned web-flow key. They also need `git` and GnuPG (`gpg`) on the
path: the command-level tests push to a bare local origin and sign their commits with a throwaway key. They make no
network call: the fake client in `tests/synth.py` stands in for the provider. They are synthetic tests of locally
written code. They are not upstream acceptance and not a native run against the provider.
