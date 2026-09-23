# Gap wave 2: us-equities / identity-provenance

These checks ran on 2026-09-23 in worktree branch `claude/g2-identity-provenance-20260923` (base 41d39b3). The gap
indexes follow the crosswalk at main 92bb279 (PR #85). The preregistration
(`blueprints/gap-wave2-20260923/us-equities__identity-provenance/preregistration.json`) was committed in 7078d05
before any check ran. Changes made after it are listed in each receipt under
`preregistration.amendments_after_preregistration` and marked `late`.

| Gap | Outcome | Evidence class | Receipt |
|---:|---|---|---|
| 0 | settled | native_proven | [0-dvc-repro-restore-contract.json](0-dvc-repro-restore-contract.json) |
| 2 | advanced | local_integration | [2-dvc-executes-selection-quarantine.json](2-dvc-executes-selection-quarantine.json) |
| 4 | settled | local_integration | [4-four-store-comparison.json](4-four-store-comparison.json) |
| 5 | settled | local_integration | [5-openlineage-mlflow-bindings.json](5-openlineage-mlflow-bindings.json) |

`results.json` is generated from the receipts by `build_receipts.py`.

**Fix round.** A Codex read-only review (2026-09-23T05:23-05:29Z) found three P1 and four P2 issues:

- baseline row counts were derived, not decoded;
- the lineage checker accepted missing datasets;
- the original C5.2 was unmet for the materialize START event;
- lineage counts included caller annotations;
- storage was measured by a different method;
- the gap 0 wording was too strong;
- a `.jsonl` file was ignored by git.

`preregistration-fixround.json` (commit 3ce38e9) was written before the reruns. A second Codex review
(05:37-05:44Z) agreed with all four outcomes. It found one P2 issue: the recovery predicate accepted whole-batch loss
or an empty decode. It also found one P3 issue: a wrong log path. `preregistration-fixround2.json` (commit 260398f)
preceded the gap 4 rerun.

**Fix round 3.** An independent Opus review found one major and three minor issues. Gap 0 had been marked settled
although C0.3 as written failed (`git_restore_diff_exit=1`) and the original refutation rule makes that run
not_settled. The other three were minor: an unrecorded change to fix-round-2 R4.1's store-reported units, a retry
maximum read from truncated stderr, and a C5.1 runId listing that could not tell the two runs apart (plus redacted
runIds that no longer met `format: uuid`). `preregistration-fixround3.json` was written at 13:20:19Z, after the
original C0.3 result had been seen, and committed in 9f84cc9 before any fix-round-3 check ran. Fix round 3 then:

- reran C0.3 on a fresh git+DVC repo (`run_c03_fixround3.sh`, published as `raw/dvc-fixround3/`):
  - the as-written arm again showed only the two git-tracked `.gitignore` files missing;
  - `git checkout -- data/.gitignore out/.gitignore && dvc checkout` and an outs-only delete plus `dvc checkout`
    each restored all 16 files, and the full-tree diff exited 0;
  - a one-byte tamper was caught by the diff and by `dvc status`, and `dvc checkout --force` repaired it;
- recorded the R4.1 measure that actually ran (Iceberg snapshots; ArcticDB versions minus the seed) as a late amendment;
- ran a supplementary Iceberg n=30 x2 two-writer run that kept each writer's complete stderr (`raw/stores-fixround3/`):
  the maximum retry was 3/4, with no CommitFailedException and no rows lost;
- derived the runId structure from the original event file (`verify_lineage_fixround3.py`, `raw/lineage-fixround3/`).
  The published ndjson was validated with FormatChecker after only its `uuid-redacted-NN` runIds were mapped to
  valid-format UUIDs; the unmapped file fails on format. Publishing valid-format placeholder UUIDs was tried first and
  rejected, because `scripts/validate.py` refuses every UUID-shaped string in published files.

**Fix round 4.** A Codex read-only review of fix round 3 (15:05-15:15Z) agreed with all four outcomes. It found one
P2 and one P3 issue in the probes, not in the retained results:

- P2: the lineage verifier paired original and published events with `zip`, so dropping the published select
  COMPLETE event or collapsing every runId to one placeholder would still have passed;
- P3: the Iceberg retry summary counts `CommitFailedException` in stderr only, but writers catch exceptions into their
  progress files.

`preregistration-fixround4.json` was written at 15:16:17Z and committed in aa85595 before the rerun. The verifier now
checks equal event counts, per-position job name and eventType, placeholder format and a one-to-one runId mapping.
Its three new detector controls (dropped event, collapsed runIds, job names swapped across jobs) were each flagged.
On the real published file it passed together with L5.1 and L5.2 (`run_verify_fixround4.sh`, published as
`raw/lineage-fixround4/`). The first two events share one job, so the swap control pairs the first event with the
first event of the other job. This deviation from preregistered L5.3b(iii) was written at 15:16:43.905Z, after the
preregistration, in the same command that ran the verifier (see fix round 5). For gap 4, the receipt now reports the
supplement's progress-file `writer_error_counts` (0 and 0 in both runs) beside the stderr count. This was read from
retained output; nothing was rerun. The review prompt, answer and stderr are in `raw/review-fixround3-codex/`.

**Fix round 5.** An independent Opus review of fix round 4 found four minor documentation issues. Nothing was
rerun, and no outcome changed.

- Gap 5: the L5.3b(iii) deviation now has its own amendment, timed at 15:16:43.905Z. The time was reconstructed by
  `extract_fixround4_timeline.py` from the fix-round-4 worker's session transcript, the verifier's mtime and the
  aa85595 tree, and is published as `raw/fixround5-timeline/timeline.json`. At 15:16:28.900Z a draft implemented (iii)
  as preregistered, with a rename fallback; it was never run. The across-job swap replaced it at 15:16:43.905Z, and
  the same command made the only verifier run. The verifier committed with the preregistration has no swap control.
  The earlier claim "amended before the run was read" had no time of its own and is withdrawn.
  `preregistration-fixround4.json` is unchanged.
- Gap 4: the H4.5 reading is labelled `source_review`. A new limit says this is not the `verdict_overturn_when`
  comparison: it used the nanosecond-replay fixture, not `blueprints/us-equities/point-in-time/fixture.json`, and ran
  no `validate_source` rejection in any store arm. The receipt and the handoff now name the same unmeasured candidates:
  lakeFS, QuestDB and ClickHouse. delta-rs is not a candidate of this layer.
- Gap 2: the handoff now gives the receipt's blocker, which is the private identity-readiness capture directory for an
  offline replay. Provider transport is not the blocker.

The cited runs are:

- gap 4: `stores-fix2`, published as `raw/stores/`;
- gap 5: `lineage-fix`, published as `raw/lineage/`.

Superseded rounds are kept in `raw/stores-fixround1/`, `raw/stores-round1/` and `raw/lineage-round1/`.

## What ran

- **Gap 0 (DVC add, restore and reproduction).** A fresh git repo with DVC 3.67.1 ran:
  - `dvc add`, a delete and a `dvc checkout` of a replay.py snapshot;
  - a `dvc.yaml` pipeline that wraps replay.py materialize/select and temporal_snapshot.py snapshot/select, run twice
    with `dvc repro` (the second run skipped all six stages);
  - deletion of every out, then `dvc checkout`. The 14 DVC-tracked files came back byte-identical, but the two
    git-tracked `.gitignore` files did not, so C0.3 as written failed. In fix round 3, git checkout of those two
    files plus `dvc checkout` restored the full 16-file tree;
  - per-cutoff selection on the restored data (records and `selection_sql_sha256` equal the project-local path and the
    unit-test assertions);
  - unknown-availability mutations of the restored `source.json` (exit 2; the unmutated control exits 0);
  - `dvc repro --force` (the data files are identical and only `ingested_at` changes).
- **Gap 2 (DVC as the executing implementation).** The same selection and quarantine stages ran under `dvc repro`. The
  security-identity capture → quality → ledger → select chain also ran under DVC, with the unit tests' synthetic
  transport. The zero-activity quarantine (2 rows, 1 qualified, 1 quarantined) and the digest and tamper refusals are
  preserved. The results equal the project-local adapter path.
  - Finding: the identity adapters refuse to write inside any git work tree (`private_output_must_be_outside_git`), so
    that chain needs `dvc init --no-scm`.
  - Remaining: replay the retained private identity-readiness captures offline through the DVC pipeline, and decide
    whether the no-scm mode is acceptable. The blocker is access to that private capture directory, which is outside the
    repository and was not accessed. The receipt plans this as an offline replay, without provider contact.
- **Gap 4 (four-store comparison).** The baseline hash manifest, DVC, PyIceberg 0.12.0 (SQLite catalog) and ArcticDB
  6.26.0 (LMDB) were compared on one materialized replay fixture. The metrics were restore fidelity, correction
  retention by time travel or version, native lineage fields, recovery after SIGKILL (5 trials), two concurrent
  writers (n=10, then 30 twice), storage bytes and median latency.
  - In the cited run, every recovery and concurrency count comes from decoding the stored rows. Recovery also requires
    decoded whole batches to equal the store-reported committed units. The detector controls cover corrupted,
    foreign, dropped-row, whole-batch-loss and empty results.
  - Main finding: ArcticDB lost appends that its writers reported as successful when two processes appended to one
    symbol. In the cited run it lost 50/100, 130/300 and 150/300 rows. Earlier rounds lost 50/100, 140/300 and 145/300,
    then 45/100, 145/300 and 150/300. Its
    installed docstrings say single-symbol concurrent writers are not supported.
  - Iceberg retried commit conflicts and lost nothing. The cited runs kept only 300-character stderr tails. In the
    fix-round-3 supplement, which kept complete stderr, the maximum retry was 3/4.
  - Numbers are for a 7-row fixture only.
  - This is not the `verdict_overturn_when` comparison. That comparison uses the point-in-time fixture and the
    `validate_source` rejection invariants, and neither was run here.
- **Gap 5 (OpenLineage and MLflow).** openlineage-python 1.53.0 FileTransport persisted START and COMPLETE events for a
  materialize run and a select run, with version, file-hash and cutoff/horizon facets. A fresh process read them back
  consistently under the fix-round rule, which is lifecycle-aware and requires every expected dataset. They validate
  against the OpenLineage 2-0-2 core schema. All five detector controls were flagged: tamper, removed output,
  removed input, rename, and a schema control.
  - The original C5.2 as written was unmet for the materialize START event: its output cannot carry a version before
    the snapshot exists. The receipt records this.
  - MLflow 3.16.1 (SQLite) logged both runs with `mlflow.log_input` bindings, which were read back and verified.
  - Finding: MLflow caps dataset digests at 36 characters, so the project sha256 is carried in dataset-input tags.

## Isolation and downloads

- **Installs.** Everything is under `$HOME/.cache/gap-wave2-20260923/identity-provenance/`:
  - venv-core: dvc, duckdb, pandas, openlineage-python;
  - venv-iceberg;
  - venv-arctic;
  - venv-mlflow, plus jsonschema.

  The installs used `uv` from PyPI through `ecosystem-bounded-run`. Freezes are in `raw/install/`. The OpenLineage
  2-0-2 core schema was fetched once with curl; its sha256 is in `inputs/raw-index.json`.
- **Isolated homes.** Every run used a temporary `HOME`/`XDG_*`, with DVC analytics and update checks turned off.
  `~/.config/iterative/telemetry` kept its pre-existing mtime of 2026-09-22 20:06 throughout.
- **Network.** The OpenLineage/MLflow phases ran under `unshare -rn`. A probe showed the network blocked inside the
  namespace and reachable outside it.
- **Out of scope.** No broker, paper account, credential, ai-memory, Qdrant, service or gate file was touched.

## Raw outputs

The cited raw outputs are under `raw/`. The published copies make these replacements:

- the home directory becomes `$HOME` and the host name `<host>`;
- `/mnt/c/Users/<name>` (from PATH echoes) becomes `/mnt/c/Users/example`;
- each UUID, mostly OpenLineage runIds, becomes a stable `uuid-redacted-NN` placeholder. The mapping is the same across
  all published files, so equality relations still hold. The original checks ran on the unredacted files. Fix round 3
  validated the published ndjson against the schema after mapping those runIds back to valid-format UUIDs in memory.

`inputs/raw-index.json` records the source and published sha256 of each file.

After the runs, the three `run_*.sh` scripts were changed to quote `"$O/home"/.config` so the repository privacy scan
does not flag the unquoted home-then-.config path form. The expanded paths are unchanged. Parquet data files, SQLite
databases and DVC caches were not copied; their hashes appear in the sha256 lists and JSON outputs.

## Helper scripts

The helpers are in `blueprints/gap-wave2-20260923/us-equities__identity-provenance/`:

- `run_dvc_arm.sh`, `dvc.yaml`, `dvc-identity.yaml`, `stage.py` and `compare_dvc_arm.py` (gaps 0 and 2);
- `run_store_arms.sh` and `store_arms.py` (gap 4);
- `run_lineage_mlflow.sh` and `lineage_mlflow.py` (gap 5);
- `publish_raw.py` and `build_receipts.py`;
- fix round 3: `preregistration-fixround3.json`, `run_c03_fixround3.sh` (gap 0), `run_iceberg_retry_fixround3.sh`
  (gap 4) and `verify_lineage_fixround3.py` (gap 5);
- fix round 4: `preregistration-fixround4.json` and `run_verify_fixround4.sh` (gap 5; the verifier was hardened in
  place);
- fix round 5: `extract_fixround4_timeline.py` (gap 5 timeline; source review, no rerun).

## Coordinator note (2026-09-23): privacy sweep

The catalog rule is: "Evidence belongs in compact sanitized receipts; no raw conversations, tokens, personal paths or machine-specific active client configuration." The PR #132 review found the host username, Claude transcript and plugin-data locations, worktree names and the active session environment in conversation-derived raw files, and the username in several command outputs.

Host username replaced by `<user>` (`-home-<name>-` project slugs become `-home-<user>-`). Raw command outputs are otherwise unchanged; metadata files also had the text changes listed under "Pins updated":

- `raw/dvc-fixround3/run.log`: 2 replacement(s), sha256 `5739d72205f8...` -> `2bc3b35419d0...`

Pins updated: `inputs/raw-index.json` (`sha256`, `bytes` and a `user_name` replacement entry; `source_sha256` is unchanged) and `0-dvc-repro-restore-contract.json` (`raw_artifacts` sha256). `publish_raw.py` now applies the same username replacement.
