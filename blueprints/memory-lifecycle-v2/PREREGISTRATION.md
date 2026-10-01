# Memory lifecycle v2 -- preregistration for the repaired rerun (2026-09-26)

This file was written before the 2026-09-26 fixture rerun. Its sha256 is recorded outside
the worktree before `run.py` executes against any binary, and the file is not edited after
that. Where a result misses a bar below, that check is a documented FAIL. It is never a
reason to loosen the bar, rerun silently or discard output.

The run of 2026-09-25 was preregistered twice. Both texts are kept byte-identical under
[`history/`](history/): `PREREGISTRATION-20260925-original.md` (sha256 `ca81e9b4...`,
frozen 20:17:18Z) and `PREREGISTRATION-20260925-amended.md` (`fb82e0aa...`, edited at
20:22:50Z after the first failed attempt). Section 6 lists every attempt of that run.

## 1. What this rerun is, and what it is not

It is a **locally authored integration fixture** (`local_integration`). `exercise.py`
drives the official ai-memory binaries over their native stdio MCP protocol, and
`analyze.py` judges the returned responses. It is not an upstream test and it is not
upstream acceptance. The upstream project's own tests for the related properties run
separately, with upstream's own command, under section 7.

The rerun exercises four isolated lifecycle properties on disposable stores: a TTL
crossing in real time, scoped routing across four projects in two workspaces, restart
durability, and v1's supersession, delete and expiry-sweep regressions. It does **not**
close the `memory-lifecycle` gate in `catalogs/us-equities/convergence-review.json`. That
gate's remaining requirements are live-store policy, scoped retrieval *quality* and
evaluated learning, and none of them is exercised here. The 2026-09-25 text said "the
open gate this closes"; that claim is withdrawn.

## 2. Binaries

| | 2.3.2 | 2.4.0 | 2.4.1 |
|---|---|---|---|
| installed binary sha256 | `93eeb299...cfed0` | `360b9dff...246344` | `dec065a8...53aa8dd` |
| release tarball sha256 | `23e8be6c...aef6fc` | `590f75dd...795076` | `15cafdc4...56375e4` |
| why it is here | landscape winner pin | the 2026-09-25 comparison build and the memory-stack control build | current `manifests/stack.json` pin |

On 2026-09-26, before this file was frozen, `upstream-20260926/verify_release.py`
downloaded each official release tarball. For every tag, the download digest equalled
both the `.sha256` sidecar and the GitHub API asset digest. The tarball's `ai-memory`
member was byte-identical to the installed binary. The retained output is
`upstream-20260926/release-verification.json`.

Each binary runs against its own fresh store and no store is opened by two binaries.
Store migration stays out of scope.

## 3. Sources for the pass bars

- **Response shapes** come from the 2026-09-25 retained native responses, now published
  under [`runs-20260925/`](runs-20260925/). `hits` is a list of objects with `id`, `path`,
  `title`, `snippet` and `rank`. A `scopes[]` hit carries an `id` but no scope annotation.
  A `global=true` response puts its results in `global_hits`, whose entries carry
  `workspace_name` and `project_name` but no `id`; its `hits` list is empty.
- **Rejection codes and messages** come from the source at each tag, and all four formats
  are identical in v2.3.2, v2.4.0 and v2.4.1:
  - `"global cannot be combined with workspace/project/scopes"`, an `internal_error`
    (-32603), at `crates/ai-memory-mcp/src/server.rs` 2065, 2321 and 2359 respectively;
  - `"page {path} not found in resolved scope {scope}{hint}"`, -32603, at `server.rs` 3401,
    3819 and 3882. `{hint}` is appended only when the scope was auto-resolved, and every
    call here passes an explicit scope;
  - `"project '{project}' not found in workspace '{workspace}'"` from
    `crates/ai-memory-store/src/scope.rs` 153, 214 and 231. It is mapped to
    `invalid_params` (-32602) by `scope_error` (`server.rs` 1428, 1607 and 1607);
  - `"invalid expires_at in frontmatter for {path} (want RFC3339 or YYYY-MM-DD): {raw}"`,
    -32603, at `crates/ai-memory-wiki/src/wiki.rs` 2454, 2474 and 2498.
- **Direct reads after a sweep need their own check.** `memory_read_page` falls back to
  the database (`served_from: "db-fallback"`) when a page file is missing. Search
  visibility therefore does not imply that a direct read fails.

## 4. Analysis rules repaired after the 2026-09-25 review

An independent cross-family review (Codex `gpt-6-astra`, 2026-09-26) showed the following
with the retained 2026-09-25 responses. Each mutated input still passed all 72 phase-pre
and 17 phase-post checks: four restart queries replaced by `{}`; the scope-conflict
rejection replaced by `-32603 "storage unavailable"`; the deleted-page read replaced by
`-32601`; and the `scopes[]` result replaced by three copies of alpha's hit. The repaired
`analyze.py` applies these rules:

1. **Malformed is not empty.** `hits` must be present and list-valued. For a global query
   `global_hits` must be too. Every hit must be an object with a string `path`. Otherwise
   the analysis raises and `run.py` records an `analysis_error` with `passed: false`.
   An unexpected protocol error or `isError` on a success call also raises, as before.
2. **Rejections match their semantics.** Each expected rejection must be a JSON-RPC error
   with the exact code and a message that fully matches its pattern (table below). An
   unexpected success, another code (for example -32601) or another message is a failed
   check, and the observed code and message are retained.
3. **Distinct identity, not identical paths.** All four projects use the same path, so a
   path alone proves nothing. The four routing writes must return four distinct page ids.
   Each `{n}_search_self` must return exactly the id written to project `n`. The
   `scopes[]` query must return exactly one hit for each of alpha, beta and gamma,
   identified by those ids, each with its own project's term in the snippet. A global
   query must return exactly one `global_hits` entry, with `hits == []`, the expected
   `workspace_name`/`project_name`, and its project's own term in the snippet.
4. **Swept pages leave the direct-read surface.** Direct reads of `notes/ttl-short.md` and
   `notes/expired.md` must be rejected as missing pages right after the sweep (phase pre)
   and again after the restart (phase post).
5. **Real-time TTL ordering is checked against the server's own clock claim.** Every call's
   wall-clock send and receive instants are retained in `timeline.json`. The server's own
   `expired_at` for `notes/ttl-short.md` comes from the sweep preview.
   `ttl_before_expiry` must be answered before that instant. The three post-expiry calls
   must be sent after it.

| label (phase) | expected code | message must fully match |
|---|---|---|
| `missing_scope` (pre) | -32602 | `project 'absent' not found in workspace 'lifecycle-v2'` |
| `invalid_combined_scope` (pre) | -32603 | `global cannot be combined with workspace/project/scopes` |
| `invalid_expiry` (pre) | -32603 | `invalid expires_at in frontmatter for notes/invalid-expiry.md (want RFC3339 or YYYY-MM-DD): not-a-date` |
| `ttl_after_sweep_direct_read` (pre), `ttl_short_direct_read_gone` (post) | -32603 | `page notes/ttl-short.md not found in resolved scope lifecycle-v2/alpha` |
| `expired_past_after_sweep_direct_read` (pre), `expired_past_direct_read_gone` (post) | -32603 | `page notes/expired.md not found in resolved scope lifecycle-v2/alpha` |
| `revision_deleted_direct_read` (post) | -32603 | `page notes/revision.md not found in resolved scope lifecycle-v2/alpha` |

The discriminating controls for these rules are the unit tests in
`tests/test_memory_lifecycle_v2.py`. They apply the review's four mutations, and others
for rules 4 and 5, to this rerun's retained responses and require every mutated input to
fail or to raise.

## 5. Calls and checks

The fixture, terms, scopes and sandbox are those of the 2026-09-25 preregistration
(`history/PREREGISTRATION-20260925-amended.md`, sections 4 and 5). The only additions are
four direct reads. Phase "pre" gains `ttl_after_sweep_direct_read` and
`expired_past_after_sweep_direct_read`, straight after `ttl_after_sweep`, for **71 calls**.
Phase "post" gains `ttl_short_direct_read_gone` and `expired_past_direct_read_gone`, after
`expired_past_gone`, for **18 calls**. Each script asserts its exact count.

A binary passes only if all **82 phase-pre** and all **19 phase-post** checks are true:

- **Phase pre (82).**
  - *Rejections (5):* `missing_scope`, `invalid_combined_scope`, `invalid_expiry`,
    `ttl_after_sweep_direct_read` and `expired_past_after_sweep_direct_read`, each as
    `<label>_rejected_as_expected`.
  - *Identity and routing (25):* `routing_page_ids_distinct`; for each of alpha, beta, gamma
    and delta, `write_{n}_ok`, `{n}_read_matches` and `{n}_search_self_own_page`; and the 12
    `{me}_search_{other}_zero`.
  - *Scopes and global (16):* `scopes_ws1_three_one_page_per_project`,
    `scopes_ws1_three_all_routing`, `scopes_ws1_three_hits_carry_own_terms` and
    `scopes_excludes_delta_zero`; for each project, `global_finds_{n}_one_hit`,
    `global_finds_{n}_origin_annotated` and `global_finds_{n}_own_term`.
  - *TTL (7):* `ttl_before_expiry_one_hit`, `ttl_after_expiry_default_zero`,
    `ttl_after_expiry_explicit_one_hit`, `ttl_after_expiry_direct_read_ok`,
    `durable_after_expiry_wait_one_hit`, `ttl_before_expiry_answered_before_native_expiry`
    and `ttl_after_expiry_calls_sent_after_native_expiry`.
  - *Sweep (10):* `sweep_preview_dry_run_true`, `sweep_preview_expired_set_correct`,
    `expired_past_after_preview_one_hit`, `ttl_after_preview_one_hit`,
    `sweep_apply_dry_run_false`, `sweep_apply_expired_set_correct`,
    `expired_past_after_sweep_zero`, `ttl_after_sweep_zero`, `future_after_sweep_one_hit`
    and `durable_after_sweep_one_hit`.
  - *v1 regressions, supersession and status (19):* `write_expired_past_ok`,
    `expired_past_default_zero`, `expired_past_explicit_one_hit`,
    `expired_past_direct_read_body_and_pinned`, `write_future_ok`, `future_default_one_hit`,
    `write_old_new_distinct_ids`, `old_now_zero`, `new_now_one_hit`,
    `old_as_of_matches_old_id_and_fts_active`, `new_as_of_zero`, `delete_revision_true`,
    `deleted_now_zero`, `deleted_as_of_zero`, `beta_unaffected_by_alpha`,
    `write_old2_new2_distinct_ids`, `old2_as_of_one_hit_matches_id`,
    `new2_now_one_hit_matches_id` and `status_pre_no_imported_history`.
- **Phase post (19).** `revision_deleted_direct_read`, `ttl_short_direct_read_gone` and
  `expired_past_direct_read_gone` as `<label>_rejected_as_expected`;
  `{alpha,beta,gamma,delta}_read_persisted`; `durable_persisted`;
  `old2_as_of_persisted_same_id`; `new2_now_persisted_same_id`;
  `revision_deletion_persisted_current`; `revision_deletion_persisted_as_of`;
  `ttl_sweep_persisted`; `expired_past_sweep_persisted`; `future_persisted`;
  `status_post_no_imported_history`; `status_stable_across_restart`;
  `post_restart_write_ok`; and `post_restart_readback_one_hit`.

The check names above are the complete list that `analyze.py` produces. The unit test
`tests/test_memory_lifecycle_v2.py` asserts this list against the analyzer.

## 6. Retention and attempts

- Every attempt gets a new `--out` directory, and no attempt directory is deleted.
  `run.py` writes `run.json` (stage reached, failure reason) and `acceptance.json`,
  including an analysis error. `publish.py` retains each attempt, passing or failing,
  under `runs-20260926/`. It keeps the full request/response exchange with per-call
  instants, the outcomes, the handoff, and the execution receipts (argv, bubblewrap
  version, start/finish, exit codes, driver stdout/stderr, server log records, namespace
  and mount records). Id aliases are consistent, and every retained file is bound to the
  sha256 of its private source.
- The 2026-09-25 run had five attempts for 2.3.2 and two for 2.4.0. Their output
  directories were deleted, except for the final pair at 20:32Z. These are recorded in
  `results-20260925.json` from the worker's retained command output: the 20:21:37Z
  count-guard failure; the 20:23:08Z attempt that sent `(project, workspace)` swapped;
  the 20:27:16Z attempt that failed eight global checks until the analyzer was changed to
  read `global_hits`; and the passing 20:28Z runs, since superseded. The final pair's
  private files survive and are published under `runs-20260925/`.

## 7. Upstream verification (separate evidence class: upstream test)

For each tag, the tag's own CI test step runs unchanged. v2.3.2 and v2.4.0 run
`cargo test --workspace --all-targets`. v2.4.1 runs that command and then
`cargo test --workspace --doc`, which its `ci.yml` added. The toolchain is 1.95.0 from
the tag's `rust-toolchain.toml`, installed with official rustup whose `rustup-init` was
checked against its published sha256. The checkouts are pinned-tag shallow clones: v2.3.2
`353841d9`, v2.4.0 `b1b25219` and v2.4.1 `433a19f3`, each with its commit verified. The
command runs inside bubblewrap with no network, a throwaway HOME and `/tmp`, and no real
home, store or service visible. Dependencies come from `cargo fetch --locked` beforehand.

The environment deviates from CI in these ways only: `CARGO_TERM_COLOR=never` (CI uses
`always`), `CARGO_INCREMENTAL=0`, `CARGO_NET_OFFLINE=true`, and `TAILWIND_BUILD` unset (on
Linux, CI sets it only to regenerate the web stylesheet). `RUSTFLAGS="-D warnings"` is kept.

- **Pass bar:** exit 0 and zero failed tests. A failure is recorded as a failure. When the
  fail-fast run stops early, a `--no-fail-fast` run enumerates all failures, and both runs
  are retained.
- **Property map:** name-based relevance, not a claim that an upstream test equals a
  fixture check. The map lists every test whose full name contains, case-insensitively:
  - TTL/expiry/sweep: `expir`, `ttl` or `sweep`;
  - scope isolation: `scope`, `isolat`, `cross_project`, `workspace`, `global` or `boundar`;
  - persistence/restart: `restart`, `reopen`, `persist`, `durab`, `surviv` or `shutdown`;
  - supersession/as-of: `as_of`, `supersed` or `temporal`;
  - delete: `delete`, `purge` or `tombstone`.
- **Discriminating control** (v2.4.1): run `ttl_expiry_lifecycle_end_to_end` in
  `ai-memory-consolidate` unmodified, then with `not_expired()` in
  `crates/ai-memory-store/src/reader.rs` returning an empty fragment, which disarms the
  default expiry filter. Then restore the file and run it again. The expected results are
  pass, fail and pass, and the mutation diff is retained.
- The upstream runs started at 02:07:03Z on 2026-09-26, before this file was frozen. The
  pass bar, property patterns and control above were fixed before any upstream test
  result was read.
- **Upstream benchmark not run.** `docs/benchmarks` publishes the LongMemEval retrieval
  harness (`ai-memory-eval retrieval --fetch`). It downloads its dataset from Hugging Face,
  so it cannot run offline, and it measures retrieval quality, which is out of scope here.
  The other harness, `ab`, needs LLM provider keys. By its own README, CI never runs
  either.

## 8. Out of scope

This list is unchanged from 2026-09-25, section 5: tenant authorization; secure erasure;
valid-time semantics; retrieval quality, embeddings and LLM synthesis; store migration
between binaries; concurrent clients; macOS and Windows; and any change to an adopted pin.
Live-store policy and evaluated learning are added to it, as named in section 1.
