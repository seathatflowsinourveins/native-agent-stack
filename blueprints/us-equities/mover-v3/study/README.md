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
| `core/calendar.py`, `core/amendments.py` | the session calendar and fee files read in their committed schemas, and the versioned amendment line schema (`populations.session_calendar`, `cost_model.fees`, `run_discipline.amendment_format`; review round 15, N01) |
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
`collect`, `count`, `read` and `complete` (review round 15). `count` and `read` run twice under one authorization: the first run fetches and seals,
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

Review round 13: a void deviation applies only if it reached origin/main before the outcome it would void could be
computed: a `tests` or `validation` void before the validation evaluation's first start line, a `holdout` void (which
cites its `read_utc`) before the first granted count or read authorization. A later void is reported
(`void_deviations_late`, `voids_late`, `holdout_label`), never applied (`core/runner.py` `void_effect`). `evaluate` runs
in two committed steps: its first run appends an `evaluate_start` line and computes nothing. Identity dedup and the
same-session guard use only rename records effective by t and no active status. A count after a failed count must
be its retry; retried counts read their first attempt's snapshot directory; identical quote updates inside a page are
kept in provider order; and read lines record `fee_span` for fee first use.

Review round 14: `count` and `read` refuse unless the working validation file's sha256 equals the one the
authorization recorded and the governing run-log line's, and the read takes the H3-c sign from those bytes. A
per-event or quote response that an earlier count fetched before its data end is fetched again for the read
(`core/holdout_store.py`). Fee amendment lines supersede earlier rows by precedence, overlapping base rows are
refused at load, and a count or read refuses a fee gap before it fetches. The dividend cash is taken per ex-date at
the close of the session immediately before it; when that session's split or all bar is missing the cash is undefined
and the trade is excluded like an undefined share factor, never priced at an older close. A results file left without
its line by a hard kill is recomputed and replaced on the retry, and a fetch step refuses a sealed ledger that no
committed line names. `authorize --purpose count` refuses while the protocol's `open_before_first_holdout_count` list
has an entry.

Review round 15 (the 2026-09-24 cross-family review of #190): the calendar and fee files are read in their committed
schemas and the calendar must reach the t-60 lookback of 2016-01-04; amendment lines follow the versioned
`run_discipline.amendment_format` (`core/amendments.py`). A sale's SEC fee row is chosen by its settlement date (T+3,
T+2, T+1 by trade date) and its TAF row by its trade date. Each coverage rate keeps its cohort and counts unknowns
against coverage; rename probes need the same sessions across the rename and identical quotes, and an observed
ticker-reuse failure fails the gate. The count-only output records its dependency manifest and is bound at the freeze
to its complete line, the frozen tree, data files, parameters and budgets; count-only, dry-run and transport-check
adopt an output a hard kill left without its line only if it reproduces from its seals (the transport check seals its
live samples). A count and a read fetch their own terminal records (`terminal_actions`), so
`open_before_first_holdout_count` is empty. Cost tiers use minute bars complete at the fill; the count and the read
share record (split, spin-off) and accounting exclusions, and a delayed exit is checked through its exit session.
Undefined or degenerate bootstrap draws gate both a pass and an MDE exclusion; item results report occupied sessions
and units. Review round 16 adds a fixed floor of 20 occupied entry sessions, identical for every item and every
H1-D group, alongside that bootstrap-implied rule; below it an item is `underpowered` with
`insufficient_occupied_sessions` reported, and the holdout extension decision (`count_unit`) sees the floor too. Verdicts come from H1-D and H3-c alone, with the tradable cells under `profitability`. H3-a is embargoed with
a 10-session block. Validation timeliness is dated by the governing bytes and line. `run.py complete --authorization
ID` rebuilds a completion lost between an action's two log writes. Results carry `claims_scope` (retrospective
reconstruction) and `input_vintage_range`. The fetch-time margin is priced in pages at the measured throughput with
separate market-data and trading limits and pinned retry and evaluation-and-merge allowances, bound to the native dry
run's measurement.

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
