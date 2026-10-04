# Memory lifecycle v2 -- restart, real-time TTL and multi-project checks

This blueprint holds a **locally authored integration fixture** (`local_integration`).
`exercise.py` drives the official ai-memory binaries over their native stdio MCP protocol
inside bubblewrap, with networking unshared, and `analyze.py` judges the responses. It is
not an upstream test. ai-memory's own test suites for the related properties ran
separately, with upstream's command at the release tags, and are recorded under
[`upstream-20260926/`](upstream-20260926/).

On 2026-09-26 the repaired rerun passed **all 82 phase-pre and all 19 phase-post checks**
on each of ai-memory **2.3.2**, **2.4.0** and **2.4.1** (71 + 18 MCP calls per binary). Each
binary used its own fresh, disposable store, and each passed on its first attempt.
[`PREREGISTRATION.md`](PREREGISTRATION.md) was frozen at 02:18:28Z, before the first fixture
run at 02:18:43Z. [`results-20260926.json`](results-20260926.json) is generated from the
retained evidence by [`assemble_results.py`](assemble_results.py).

This is a foundation blueprint, separate from the trading-lane v1 at
[`blueprints/us-equities/memory-lifecycle/`](../us-equities/memory-lifecycle/). It reuses
v1's bubblewrap recipe and `run.py`/`exercise.py`/`analyze.py` split.

## What it checks, and what it does not establish

- **TTL crossing in real time.** A page expires 4 s after its write. The before-expiry query
  is answered before the server's own reported `expired_at`, and the post-expiry calls are
  sent after it; both orderings are checked from retained per-call instants. Ordinary
  search then hides the page, while `include_expired` and a direct read still return it. A
  `memory_forget_sweep` removes it and a v1-style already-expired pinned page. After the
  sweep, **direct reads of both pages are rejected as missing**, immediately and again
  after a restart.
- **Scoped routing across 4 projects in 2 workspaces.** All four projects use the same page
  path, so every check compares page ids. Each self-search returns exactly its own
  project's page id, and all 12 cross-project searches return zero hits. `scopes[]` returns
  exactly one page each from alpha, beta and gamma, identified by id. `global=true` returns
  each project's page once, annotated with its own workspace and project.
- **Restart durability.** A second native server process opens the same store after the
  first has fully exited. It returns persisted bodies, `as_of` history and page ids,
  persisted deletions and sweeps, and unchanged status counts, and it takes a new write.
- **v1 regressions:** supersession and `as_of`, an explicit delete, invalid expiry, and a
  far-future expiry.

This does **not** close the `memory-lifecycle` gate in
[`catalogs/us-equities/convergence-review.json`](../../catalogs/us-equities/convergence-review.json).
Live-store policy, scoped retrieval *quality* and evaluated learning remain untested. The
2026-09-25 preregistration said the run closed that gate, and PR #292 said it covered the
gate's "live quality" half. Both claims are withdrawn.

## Repairs after the 2026-09-26 cross-family review

A Codex (`gpt-6-astra`) review of PR #292 found that the 2026-09-25 analyzer still passed
72/72 and 17/17 checks after each of four mutations: restart queries replaced by `{}`, a
`"storage unavailable"` error in place of the scope-conflict rejection, `-32601` in place of
the deleted-page error, and three copies of alpha's hit as the `scopes[]` result. The
repaired rules, in [PREREGISTRATION.md section 4](PREREGISTRATION.md#4-analysis-rules-repaired-after-the-2026-09-25-review),
are these:

- A missing or non-list `hits` or `global_hits` is an analysis error, never an empty result.
- Every expected rejection must carry the exact code and full message of the tested source.
- Identity is checked by page id, not by path.
- Swept pages must fail direct reads after the sweep and after the restart.
- TTL ordering is checked against the server's own `expired_at`.

[`tests/test_memory_lifecycle_v2.py`](../../tests/test_memory_lifecycle_v2.py) applies those
mutations, and more, to the retained native responses as discriminating controls. It also
holds one control for each of the 82 + 19 checks on each retained run: a single change to a
response, a per-call instant or a handoff value that must turn that check false, so no
check can pass vacuously.

## Changes after the independent review of this repair

An independent review of the repair found five low-severity defects. One is outside the
repository: PR #292's description still claims the gate's "live quality" half, which this
README withdraws above, and it needs a correcting comment on that pull request. The other
four are fixed here, each with a regression test:

- `results-20260926.json` listed the four discriminating-control runs among the upstream
  test runs. They ran a filtered command, twice on a mutated checkout, so they now appear
  only under `discriminating_control`, labelled local integration.
- The grand-dashboard checkpoint was dated before the evidence it cited. The shared
  dashboard file changes in a separate `lane:shared` PR, which moves the row to the
  2026-09-26 results with a timestamp after them. `DashboardCheckpointTests` checks that
  ordering once the row cites them, and skips until then.
- `assemble_results.py` stopped on a failed attempt (an unexpected success, an analysis
  error, a phase that never ran, a missing native expiry) and kept one attempt per binary.
  It now reports every attempt. `status` is `passed` only when every retained attempt
  passed, so a later pass cannot hide an earlier failure.
- `upstream-20260926/setup.log` had its scratch path replaced without a declaration.
  `upstream-20260926/publication.json` now binds every retained upstream file to the sha256
  of its private source and declares each substitution.

[`history/review_repair_controls_20260926.py`](history/review_repair_controls_20260926.py)
re-introduces each defect in a temporary copy of the files and shows that its test fails
with the defect and passes without it (`history/review-repair-controls-20260926.txt`).
Of the verification gaps the review named, these are closed in the repository: the
re-check output is retained, the unit tests rebuild `results-20260926.json` and require it
to match, the rustup-init checksum comparison is recorded, the first release-verification
run is listed by its sha256, and every fixture check has its own discriminating control.

## Changes after the verification review

A verification review of that repair found two medium defects and one low defect in the
repository. Its other low finding is outside the repository: PR #292's description is
still uncorrected, and that correction is a comment on the pull request. A further check
found a fourth repository defect, the `setup.sh` header below. Each repository defect is
fixed here with a regression test:

- **The upstream runner could overwrite an earlier attempt.** Rerunning
  `run_upstream_tests.py` with the same `--out` and label truncated the earlier log and
  replaced its receipt, so the section 7 `--no-fail-fast` follow-up to a failed run could
  erase that failure. The runner now refuses to start when either file exists and creates
  both exclusively. `--reparse` prints the recomputed receipt instead of rewriting it.
- **The control exited 0 whatever happened.** `control.py` returned success even when all
  four runs failed or both mutations survived. It now exits 1 unless the runs gave pass,
  fail, fail, pass (a build error or an empty selection is neither) and the file was
  restored byte-for-byte. It writes its summary either way and refuses existing output.
  The retained control run meets that bar.
- **The historical hash log had an undeclared substitution.**
  `history/preregistration-sha256-20260925.txt` has the private scratch root replaced by
  `<scratch>` on lines 1 and 6. `history/publication.json` now binds it to its private
  source (1,191 bytes; 1,009 bytes published, both sha256 values recorded) and declares
  that substitution. It also accounts for every other file under `history/`.
- **`setup.sh` claimed an unrecorded check.** Its header said the rustup-init checksum was
  verified before the script ran. It now agrees with the rustup-init erratum in
  `results-20260926.json`. Only the comment changed.

The upstream runs, the control and the setup used the earlier `run_upstream_tests.py`,
`control.py` and `setup.sh`. They are kept byte-for-byte under
`history/upstream-scripts-as-run-20260926/`, and every upstream and control receipt records
the as-run runner's sha256. The script that ran the final upstream round and the control is
kept with its output as `history/upstream-final-round-driver-20260926.sh` and `.log`. That
log recorded the sha256 of `run_upstream_tests.py` and `control.py` when the round started,
and both equal the kept copies. Its `exit=` fields are always 0 and are not exit statuses;
the receipts hold those. No hash of `setup.sh` was recorded when it ran, so
`history/publication.json` states the basis for that copy: its private source was last
modified before `setup.log`'s first line.

`history/verification_repair_controls_20260926.py` puts each defect, and an as-run copy that
is not what ran, back in a temporary copy and shows the matching tests failing with it and
passing without it (output in `history/verification-repair-controls-20260926.txt`).

## Evidence layout

| Path | What it holds |
|---|---|
| `runs-20260926/ai-memory-<version>/attempt-1/` | Each rerun: the full request/response exchange with per-call instants (`records.json`, `timeline.json`), `outcomes.json`, the restart handoff, and the execution receipts (argv, bubblewrap version, start/finish, exit codes, driver output, server log records, namespace and mounts). `publication.json` binds every file to the sha256 of its private source and declares the substitutions. |
| `runs-20260925/` | The two surviving 2026-09-25 runs (2.3.2 attempt 5, 2.4.0 attempt 2), published the same way. |
| `history/` | The original and amended 2026-09-25 preregistrations, byte-identical and recovered by hash. Also both freeze records, the ledger of all seven 2026-09-25 attempts (`attempts-20260925.json`), and a re-check of those responses with the repaired rules (`recheck_20260925.py`, output retained in `recheck-20260925.json`: 95 of 95 comparable checks pass on both binaries). Also the review reproduction (`reproduce_review_20260926.py`) and the controls for the post-review regression tests (`review_repair_controls_20260926.py` and `verification_repair_controls_20260926.py`, outputs in the matching `.txt` files). `upstream-scripts-as-run-20260926/` keeps `run_upstream_tests.py`, `control.py` and `setup.sh` as they ran, and `upstream-final-round-driver-20260926.sh`/`.log` are the script that ran the final upstream round and the control, with its output. `publication.json` binds each file copied from a private file (the 2026-09-25 hash log and the driver files, whose scratch paths are replaced, the 2026-09-26 freeze record and the as-run scripts) to the sha256 of its source, and says what binds every other file here. |
| `results-20260925.json` | The 2026-09-25 results, now `superseded`, with a `corrections` list. |
| `upstream-20260926/` | The toolchain and checkout setup (`setup.sh`, `setup.log`), the rustup-init checksum check (`verify_rustup_init.py`) and release-asset verification (`verify_release.py`). For each tag, ai-memory's own CI test command with logs and receipts (`run_upstream_tests.py`), including the superseded first round. Also a property map and a discriminating control (`control.py`). `publication.json`, written by `publish_upstream.py`, binds every retained file there to the sha256 of its private source and declares each substitution. The committed `run_upstream_tests.py`, `control.py` and `setup.sh` were changed after the runs; the versions that ran are under `history/upstream-scripts-as-run-20260926/`. |

Page ids and Git checkpoint ids in the retained files are consistent aliases
(`fixture-id-N`, `fixture-checkpoint-N`). Equal ids stay equal and distinct ids stay
distinct, so `analyze.py` reaches the same verdicts on the published files as it reached
at run time. `results-20260926.json` records that comparison per binary.

## Commands

```sh
python3 blueprints/memory-lifecycle-v2/run.py --binary PATH/TO/ai-memory --out NEW_PRIVATE_DIR
python3 blueprints/memory-lifecycle-v2/publish.py --run NEW_PRIVATE_DIR \
  --dest blueprints/memory-lifecycle-v2/runs-YYYYMMDD/ai-memory-VERSION/attempt-N --scratch SCRATCH_ROOT
python3 blueprints/memory-lifecycle-v2/analyze.py blueprints/memory-lifecycle-v2/runs-20260926/ai-memory-2.4.1/attempt-1
python3 blueprints/memory-lifecycle-v2/assemble_results.py --check
python3 blueprints/memory-lifecycle-v2/history/review_repair_controls_20260926.py
python3 blueprints/memory-lifecycle-v2/history/verification_repair_controls_20260926.py
```

`run.py` rejects a non-fresh output directory. It runs phase "pre" and then, only after
that process has exited, phase "post" against the same store. A failed attempt keeps its
directory, with `run.json` (the stage reached and the reason it stopped) and
`acceptance.json` (including an analysis error). Never delete an attempt; run the next one
with a new `--out`. In the same way, `upstream-20260926/run_upstream_tests.py` refuses a
`--out` and `--label` whose log or receipt exists, and `control.py` refuses an `--out`
that holds control output.

## Results

| | 2.3.2 | 2.4.0 | 2.4.1 |
|---|---|---|---|
| binary equals the official release asset (download, sidecar and API digests agree) | yes | yes | yes |
| phase pre: calls, checks passed | 71, 82 of 82 | 71, 82 of 82 | 71, 82 of 82 |
| phase post (restart): calls, checks passed | 18, 19 of 19 | 18, 19 of 19 | 18, 19 of 19 |
| negotiated `protocolVersion` (the client requests `2025-03-26`) | `2024-11-05` | `2025-03-26` | `2025-03-26` |
| direct reads of swept pages, after the sweep and after restart | -32603, page not found | same | same |
| `memory_status` for `alpha`, pre and post restart | `pages_latest=4`, `pages_all=5` | same, plus `evidence_rows=0` | same as 2.4.0 |
| upstream `cargo test --workspace --all-targets` at the tag | 3,357 passed, 0 failed, 11 ignored | 3,515 passed, 0 failed, 14 ignored | 3,615 passed, 0 failed, 14 ignored |

**Upstream verification.** Each tag's own CI test command ran unchanged, at a
commit-verified shallow checkout, with toolchain 1.95.0 from the tag's
`rust-toolchain.toml` through official rustup, inside a network-less sandbox. The
rustup-init that installed it (rustup 1.29.1) equals its downloaded `.sha256` sidecar and
the official archive checksum. No record of a check before installation was kept, so the
comparison was made on the same binary at 04:16Z, after the runs
(`upstream-20260926/rustup-init-verification.json`). v2.4.1's CI also runs
`cargo test --workspace --doc`. That step ran 11 doc-test harnesses holding no doc tests,
so it is recorded as **untested**, not passed.

Every tag command ran twice. The first round's sandbox HOME sat under `/home`, which the
repository's private-content scanner flags, so the final round reran those commands with
the runner kept as `history/upstream-scripts-as-run-20260926/run_upstream_tests.py`, whose
sha256 each receipt records. Both rounds gave identical totals. The first round's logs contain the source build
from each tag checkout and are kept under `upstream-20260926/superseded-round-1/`.

**Discriminating control** (v2.4.1, `ttl_expiry_lifecycle_end_to_end`):

- Unmodified, the test passes.
- With `not_expired()` disarmed so that expired pages match (`... OR 1 = 1`), it fails at
  its own assertion: `expired hidden: ["notes/expired.md", ...]`.
- With the preregistered empty fragment it also fails, but on
  `Sqlite(InvalidParameterCount(5, 4))`, which is a binding error, not the expiry
  semantics.
- Restored byte-for-byte, it passes again.

The mutation diffs are in `upstream-20260926/control/`. These four runs use a filtered command
on a mutated and then restored checkout, so `results-20260926.json` reports them only under
`discriminating_control`, as a local integration control, and never among the upstream test runs.

`upstream-20260926/property-map.json` lists the upstream tests selected by name for each
property. At v2.4.1 it selects 72 TTL/expiry/sweep tests, 300 scope-isolation tests, 59
persistence/restart tests, 20 supersession/as-of tests and 114 delete tests. All pass
except `removal::purge_data_refuses_when_sibling_alive`, which upstream marks ignored.
Examples:

- `integration::lifecycle::ttl_expiry_lifecycle_end_to_end`
- `server::tests::memory_forget_sweep_targets_the_explicit_project`
- `integration::retrieval_via_tools::memory_query_as_of_returns_the_superseded_version_through_the_tool`
- `commands::serve::tests::a_restart_seeds_the_active_project_fallback_from_the_last_activity`

`verify_release.py` confirmed each fixture binary against its official release asset.

## Limitations

- Store migration between binaries is not exercised. Each binary had its own store, so
  "same checks pass" is the whole upgrade claim. 2.4.x migrates a store forward and 2.4.0
  refuses a V67 store (`evidence/receipts/ai-memory-241-qualification-20260925.json`).
- The upstream tests are the tags' own suites under their CI command. They were run with
  colour off, `CARGO_INCREMENTAL=0`, offline after `cargo fetch --locked`, without
  `TAILWIND_BUILD`, and in a network-less sandbox. The tests upstream marks `#[ignore]`
  (model files, datasets, Node, throughput) did not run. The property map is name-based.
- The upstream LongMemEval harness was not run. It needs a network dataset fetch and
  measures retrieval quality, which is outside this blueprint.
- Concurrent clients, tenant authorization, secure erasure, retrieval ranking, embeddings,
  LLM features, macOS and Windows are out of scope.
- The repository's pins are unchanged. `manifests/stack.json` pins 2.4.1; the durable-memory
  landscape winner pin stays 2.3.2 until a verdict wave.
