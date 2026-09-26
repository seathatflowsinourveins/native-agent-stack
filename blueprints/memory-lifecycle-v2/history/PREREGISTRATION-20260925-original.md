# Memory lifecycle v2 -- preregistration (2026-09-25)

Written and frozen before any acceptance run of this blueprint. Its own sha256 is
recorded outside the worktree before `run.py` executes against either binary; this
file is not edited afterward. Where a run's result differs from a bar below, the
result is a documented FAIL for that check, not a reason to loosen the bar.

This is a FOUNDATION blueprint, independent of `blueprints/us-equities/memory-lifecycle/`
(v1, a trading-path blueprint). v2 imports v1's bubblewrap isolation recipe and disposable
harness pattern by attribution (same author lineage, `run.py`/`exercise.py`/`analyze.py`
split, standard-library only) but is a new blueprint at this path, with its own binaries,
fixtures and checks. v1 is not modified.

## 1. What this adds over v1

v1 (`blueprints/us-equities/memory-lifecycle/receipt.json`, `status: passed_scoped_acceptance`,
23/23 checks over 31 MCP calls against ai-memory 2.3.1) explicitly did not exercise: service
restart durability, a TTL crossing in real time, scoped retrieval under more than two
projects, or upgrade behaviour. The open gate this closes is recorded at
`catalogs/us-equities/convergence-review.json` (`id: memory-lifecycle`,
`state: isolated_native_lifecycle_accepted_live_quality_pending`) and at
`catalogs/landscape/foundation.json` (`layer_id: durable-memory`, `open_gaps`), which lists,
among others: "TTL controls default search visibility until sweep..." and "the scheduler
covers all store scopes with a per-project limit, and only one project is adopted. Isolation
with multiple projects in production is unobserved" and "the reviewed ai-memory upstream
revision is not the accepted installed 2.3.2 revision; upgrade behavior remains unqualified."

This run adds four groups of checks, listed in full in section 4:

- **(a) TTL crossing in real time.** A page with a near-future `expires_at` is queried
  before expiry, the run sleeps past expiry on the real wall clock, ordinary search is
  re-checked, then an explicit sweep is run and re-checked. A durable (non-expiring) control
  page is checked to still be present throughout.
- **(b) Scoped retrieval under more than two projects.** Three projects (`alpha`, `beta`,
  `gamma`) in one workspace, plus a fourth project (`delta`) in a second workspace, each
  hold a page with a unique term. Every same-scope query finds its own term; every
  cross-scope query (all 12 ordered pairs) returns zero. The documented `scopes` (explicit
  multi-project list) and `global` (every project in every workspace) query modes are each
  exercised and checked against the behaviour their own tool schema documents (section 3).
- **(c) Restart durability.** The native stdio server process for a binary is stopped (its
  process fully exits; `serve --help`'s own single-instance-lock warning is why this run
  never overlaps two servers on one data directory) and a new server process for the SAME
  binary is started pointed at the same disposable `--data-dir`. Durable pages, a live
  (undeleted) supersession chain, and an already-completed deletion are all re-checked
  read-only against the new process. One additional write+read-back after restart checks the
  new process is not just serving frozen state.
- **(d) v1 regression.** v1's project routing/isolation, TTL/expiry-sweep and
  supersession/delete semantics are reproduced as checks in this run (same shape, new
  fixture terms), so a regression in the newer binary is caught, not just the new behaviour.

**Upgrade behaviour** is qualified by running the SAME check suite, unmodified, against
BOTH 2.3.2 and 2.4.0, each against its OWN fresh disposable store. This is a same-checks,
different-binary comparison, not a store migration: per the task's hard rule and
`docs/decisions/2026-09-25-ai-memory-2-4-0-release-review.md` ("Refinery's
`set_abort_missing(true)` makes an older binary refuse a newer store with `DataSchemaAhead`"
and this repository's own trial found "stock 2.3.2 hook binaries abort on a store migrated to
2.4.0"), 2.4.0 migrates forward any store it opens, and that migration is one-way. Opening one
store with both binaries would therefore not be a clean comparison and is out of scope
(section 5).

## 2. Binaries under test

| | production 2.3.2 | official 2.4.0 |
|---|---|---|
| path | `~/.local/share/codex-ecosystem/tools/ai-memory-2.3.2/ai-memory` | `~/.local/share/codex-ecosystem/tools/ai-memory-2.4.0/ai-memory` |
| file type | ELF 64-bit LSB pie executable, x86-64, stripped | ELF 64-bit LSB pie executable, x86-64, stripped |
| installed binary sha256 (measured directly in this run, before AND after each of the two phases, for both binaries) | `93eeb2994343f8d5427328650d3fc2ec85250332e2308c163d27169d8b5cfed0` | `360b9dff30537cc514876eab0c4df0d57b9c8c8bb1c62d4a9240f0264e246344` |
| `--version` output (confirmed live, inside bwrap) | `ai-memory 2.3.2` | `ai-memory 2.4.0` |
| release tarball sha256 | not supplied for this pin; not asserted | `590f75ddaf0f8f1a07b70ba20900de717b89c3f6c46e6e5e0540ade302795076`, asserted per the task's stated peer rehearsal -- **not independently re-fetched or re-verified in this run** (no network egress; the run's bwrap sandbox unshares networking). Recorded as a distinct, differently-sourced fact from the installed-binary sha256 above, which this run DID measure directly. |
| repository pin (`manifests/stack.json`) | `2.3.2`, matches installed | 2.4.0 is explicitly NOT the adopted pin (`docs/decisions/2026-09-25-ai-memory-2-4-0-release-review.md`: "Stay on 2.3.2 until a planned upgrade window"); this run does not change that pin |

Both binaries are run read-only (bind-mounted `--ro-bind`) inside their own disposable
bubblewrap sandbox invocation, each against its own freshly created, empty `--data-dir`
that this run creates under scratch, never a real or shared store.

## 3. Schema-discovery research this preregistration relies on

Before writing the checks below, this run did three non-mutating, discarded reconnaissance
passes (analogous to v1's own retained "schema discovery" attempt in
`blueprints/us-equities/memory-lifecycle/receipt.json`'s `attempts` list) to avoid
preregistering a bar this run could not have known was right or wrong:

1. `initialize` + `tools/list` only, against each binary, fresh empty throwaway store,
   zero tool calls. This is the primary source for the `memory_query` scoping contract cited
   below, and confirms both binaries advertise 23 tools (matching v1's 2.3.1 count and the
   2.4.0 release-review doc's "The MCP surface stays at 23 tools").
2. The SAME recon also recorded the negotiated `initialize` response, which is not something
   v1's own README/receipt actually checked (v1's receipt names the client-requested protocol
   version, not the negotiated response): **2.3.2 negotiates `protocolVersion: 2024-11-05`**
   despite this client requesting `2025-03-26`; **2.4.0 negotiates `2025-03-26`**, matching
   the request. This is recorded as an observation in results, not gated pass/fail (out of
   scope, section 5), because neither the task nor any read source here specifies a required
   negotiated value.
3. One `memory_read_page` and one `memory_delete_page` against a path that was never
   written, fresh throwaway store, each binary. Both binaries: `memory_read_page` on a
   missing page returns a JSON-RPC `error` (code `-32603`, message
   `"page <path> not found in resolved scope <workspace>/<project>"`); `memory_delete_page`
   on a missing page returns a SUCCESS result with `deleted: true` (idempotent-style, not an
   error). This fixes the exact pass bar for check `revision_deleted_direct_read` in section
   4(c) to "the response is a JSON-RPC `error` object with an integer `code`", instead of a
   guess.

The cited `memory_query` input schema (both binaries; the field descriptions below are
byte-identical between 2.3.2 and 2.4.0's `tools/list`, except that 2.4.0 additionally
advertises the opt-in `include_superseded`, `pin_first`, `answer` and `reasoning` fields,
which this run does not exercise -- out of scope, section 5):

> `project`: "Project to search. Session-aware clients may omit it for the current project.
> Static MCP clients must pass it together with `workspace` for every project-scoped call.
> Omit it for `global=true`."
>
> `workspace`: "Workspace to search together with `project`. ... Omit both for `global=true`."
>
> `scopes`: "Explicit multi-project scopes to search. Use this when a task needs context
> from a client project plus shared practice/project knowledge. Cannot be combined with
> `workspace`/`project`."
>
> `global`: "Search EVERY project in every workspace in one call (cross-project global
> search). Use when you don't know which project holds the knowledge... When true, omit
> `project`/`workspace`/`scopes`; each hit is annotated with its workspace + project so you
> can tell where it came from."

This is the documented source the task asks this run to cite for check group (b)'s
global/workspace-wide behaviour. The full captured schema JSON for both binaries is saved
under the private run directories (not copied into the worktree; raw run dirs stay private
per the hard rules) and its sha256 is recorded in `results-20260925.json`.

## 4. Preregistered checks and pass bars

All checks run inside the SAME bubblewrap recipe v1 uses: `--unshare-all --clearenv
--die-with-parent --new-session --cap-drop ALL`, only the selected binary/driver/system
runtime read-only and a fresh output directory read-write, network limited to loopback (in
practice unused -- `--unshare-all` unshares the network namespace entirely), no LLM,
`embedding_provider = "none"`, watcher/backfill/autowire/maintenance/auto-improve all off.
Fixture terms are invented whimsical compound words with no real-world referent (matching
v1's `Cobaltquartz`/`Ambermeadow` style), never real project or account data.

Fixture identifiers used below: workspace `WS1` = `lifecycle-v2`, workspace `WS2` =
`lifecycle-v2-secondary`; projects `alpha`/`beta`/`gamma` in `WS1`, project `delta` in `WS2`
(server started with `--workspace lifecycle-v2 --project alpha`, matching v1's pattern of a
server default plus explicit per-call `workspace`/`project` arguments). Unique terms:
`alpha`=`Marigoldpixel`, `beta`=`Driftwoodlantern`, `gamma`=`Cinderfoxglove`,
`delta`=`Thistlebronze`, already-past-expiry+pinned=`Palewinterlynx`,
far-future=`Sablefernbrook`, revision-old=`Hollowcopperfield`, revision-new (deleted at the
end)=`Brightendersteel`, near-future TTL=`Emberquokka`, durable control=`Granitewillow`,
kept-undeleted revision-old=`Ironpetalwren`, kept-undeleted revision-new=`Copperlatticefawn`,
post-restart write=`Quillmarrowdrift`.

A run PASSES only if every check below is `true` for BOTH binaries independently. A binary
can fail while the other passes; both are reported.

### Phase "pre" (single server process, one binary, fresh store)

**Group R -- routing/isolation across 4 projects / 2 workspaces (item b, positive+negative):**

| label | call | pass bar |
|---|---|---|
| write_alpha / write_beta / write_gamma / write_delta | `memory_write_page` to each project's `notes/routing.md` with its unique term | all 4 calls succeed (no `error`) |
| alpha_read / beta_read / gamma_read / delta_read | `memory_read_page` same path, matching scope | body equals exactly what was written |
| alpha_search_self / beta_search_self / gamma_search_self / delta_search_self | `memory_query` own term, own scope | exactly 1 hit, path `notes/routing.md` |
| 12 ordered cross checks (`{alpha,beta,gamma,delta}_search_{the other 3}`) | `memory_query` another project's term, this project's scope | 0 hits, for all 12 ordered pairs |
| missing_scope | `memory_read_page` project=`absent`, workspace `WS1` | JSON-RPC `error` (integer `code`) |
| invalid_combined_scope | `memory_query` with `global=true` AND `workspace`/`project` also set | JSON-RPC `error`; message mentions the conflict (regression of v1's identical check) |

**Group G -- documented global/scopes behaviour (item b):**

| label | call | pass bar |
|---|---|---|
| scopes_ws1_three | `memory_query` query = OR of alpha+beta+gamma terms, `scopes=[{WS1,alpha},{WS1,beta},{WS1,gamma}]`, no `workspace`/`project` | exactly 3 hits, all path `notes/routing.md` |
| scopes_excludes_delta | `memory_query` delta's term, same `scopes` list (delta not named) | 0 hits |
| global_finds_alpha / _beta / _gamma / _delta | `memory_query` each project's term, `global=true`, no `workspace`/`project`/`scopes` | exactly 1 hit, path `notes/routing.md`, AND the hit (or its immediate containing structure) names the correct origin workspace and project somewhere in the response -- the exact field is recorded in results either way, since section 3 only fixes the documented CLAIM, not an unverified exact JSON path |

**Group T -- TTL crossing in real time (item a):**

| label | call | pass bar |
|---|---|---|
| write_ttl_short | write `notes/ttl-short.md`, `expires_at` = wall-clock now + 4s | succeeds |
| write_durable | write `notes/durable.md`, no `expires_at` | succeeds |
| ttl_before_expiry | query the TTL term, immediately after the write above | exactly 1 hit -- confirms "before expiry" |
| *(real `time.sleep` until wall-clock now > expiry + 2.5s safety margin -- not simulated, not mocked)* | | |
| ttl_after_expiry_default | query the TTL term, ordinary (no `include_expired`) | 0 hits -- ordinary search hides it once really expired |
| ttl_after_expiry_explicit | query the TTL term, `include_expired=true` | exactly 1 hit -- not yet swept |
| ttl_after_expiry_direct_read | `memory_read_page` the same path | succeeds, body still contains the term |
| durable_after_expiry_wait | query the durable term | exactly 1 hit -- elapsed time alone does not affect a page with no TTL |

**Group S -- sweep, extended to both the v1-style already-past-expiry page and the new
real-time-expired page (items a + d):**

| label | call | pass bar |
|---|---|---|
| sweep_preview | `memory_forget_sweep(dry_run=true)` | `dry_run==true`; `expired` list has exactly 2 entries, paths `{notes/expired.md, notes/ttl-short.md}`, each `deleted==false` |
| expired_past_after_preview / ttl_after_preview | query each term, `include_expired=true` | still 1 hit each -- preview does not delete |
| sweep_apply | `memory_forget_sweep(dry_run=false)` | `dry_run==false`; `expired` list exactly the same 2 paths, each `deleted==true` |
| expired_past_after_sweep / ttl_after_sweep | query each term, `include_expired=true` | 0 hits each -- gone even with `include_expired` |
| future_after_sweep | query the far-future term | exactly 1 hit -- untouched (v1 regression) |
| durable_after_sweep | query the durable term | exactly 1 hit -- untouched (new control) |

**Group V -- v1-shape regressions kept (item d): already-past-expiry+pinned, far-future,
invalid expiry, supersession/as_of, explicit delete:**

| label | call | pass bar |
|---|---|---|
| write_expired_past | write `notes/expired.md`, `expires_at=2000-01-01T00:00:00Z`, `pinned=true` | succeeds |
| expired_past_default | query its term, ordinary | 0 hits |
| expired_past_explicit | query its term, `include_expired=true` | exactly 1 hit |
| expired_past_direct_read | direct read | body has the term; `frontmatter.pinned == true` |
| write_future | write `notes/future.md`, `expires_at=2999-01-01T00:00:00Z` | succeeds |
| future_default | query its term | exactly 1 hit |
| invalid_expiry | write with `expires_at="not-a-date"` | JSON-RPC `error` |
| write_old / write_new | write, then overwrite, `notes/revision.md` (an `as_of` instant is captured strictly between the two writes) | both succeed; different `page_id` |
| old_now | query old term, ordinary | 0 hits |
| new_now | query new term, ordinary | exactly 1 hit |
| old_as_of | query old term, `as_of=<the captured instant>`, `explain=true` | exactly 1 hit, its `id` equals `write_old`'s `page_id`; `'fts'` is in the returned `streams_active` |
| new_as_of | query new term, same `as_of` | 0 hits |
| delete_revision | `memory_delete_page(notes/revision.md)` | `deleted == true` |
| deleted_now | query new term, ordinary | 0 hits |
| deleted_as_of | query old term, same `as_of` | 0 hits |
| beta_after_alpha_mutations | re-read beta's `notes/routing.md` | body unchanged from `beta_read`, unaffected by every alpha-scoped mutation above |

**Group P -- a SECOND, undeleted supersession pair, held live specifically so phase "post"
(restart) has real supersession history to re-check (feeds item c):**

| label | call | pass bar |
|---|---|---|
| write_old2 / write_new2 | write, then overwrite, `notes/revision2.md` (a second `as_of` instant captured between) | both succeed; different `page_id`; NOT deleted in this phase |
| old2_as_of | query old2 term, `as_of=<second instant>` | exactly 1 hit, `id` equals `write_old2`'s `page_id` |
| new2_now | query new2 term, ordinary | exactly 1 hit, `id` equals `write_new2`'s `page_id` |

**Status (narrow regression of v1's isolation-freshness check):**

| label | call | pass bar |
|---|---|---|
| status_pre | `memory_status` (server-default scope) | `counts.sessions == 0` and `counts.observations == 0` (isolated fixture, nothing imported) -- `pages_latest`/`pages_all` are RECORDED for the restart comparison below but not asserted to an exact predicted integer here, since their exact accounting (e.g. how a sweep-purge vs an explicit delete affects a historical-version count) is not independently confirmed by this preregistration's research and is not one of the task's four required items |

That is 69 phase-"pre" calls. The exercise script asserts this exact count before summarizing,
mirroring v1's own `if len(outcomes) != 31: raise ValueError(...)` guard, so a silently
dropped or duplicated call is a hard failure, not a smaller passing total.

### Restart (phase "pre" server process fully exited, a NEW process started against the
SAME `--data-dir`; item c)

The two bwrap invocations run strictly sequentially from `run.py` (the second is not
launched until `subprocess.run` for the first has returned), and neither passes `--force`
to `serve`; `ai-memory serve --help` documents a single-instance lock ("two live servers on
one data directory corrupt wiki and index state"), so overlap is a bug this design avoids by
construction, not a race this run tolerates.

| label | call | pass bar |
|---|---|---|
| alpha_read / beta_read / gamma_read / delta_read | re-read all 4 | each body byte-equal to its phase-"pre" counterpart |
| durable_search | query the durable term | exactly 1 hit, `notes/durable.md` |
| old2_as_of | query old2 term, the SAME captured `as_of` instant from phase "pre" | exactly 1 hit, SAME `page_id` as phase "pre"'s `write_old2` |
| new2_now | query new2 term | exactly 1 hit, SAME `page_id` as phase "pre"'s `write_new2` |
| revision_deleted_current | query the (phase-"pre"-deleted) new-revision term | 0 hits -- the deletion persisted |
| revision_deleted_as_of | query the (phase-"pre"-deleted) old-revision term, phase-"pre"'s `as_of` instant | 0 hits -- the deletion also removed `as_of` visibility, and that persisted |
| revision_deleted_direct_read | direct read of the deleted page's path | JSON-RPC `error` with an integer `code` (section 3, finding 3) |
| ttl_short_gone / expired_past_gone | query each swept term, `include_expired=true` | 0 hits each -- the sweep's deletions persisted |
| future_present | query the far-future term | exactly 1 hit -- untouched page persisted |
| status_post | `memory_status` (server-default scope) | `counts.sessions == 0`, `counts.observations == 0`, AND `counts.pages_latest` / `counts.pages_all` EXACTLY equal their phase-"pre" `status_pre` values (nothing was written between the two status calls, so this relative invariant is the actual restart-durability claim, independent of whichever absolute accounting v1's precedent suggested) |
| post_restart_write_readback (functional-continuity bonus, not a persistence claim) | write a new page with a new term, then immediately query it | 1 hit -- the restarted process is not just serving frozen state, it is a fully live server |

That is 15 phase-"post" calls (14 read-only persistence checks + 1 write-capability bonus).

## 5. Out of scope (unchanged from v1 unless noted)

- Tenant authorization, secure multi-tenant access; this fixture deliberately creates its own
  projects and workspaces.
- Secure erasure from Git checkpoints, backups, or disk-level forensics; "deleted"/"swept"
  means absent from the MCP surface (query + direct read), not that no byte trace exists
  anywhere.
- Market/valid-time semantics; `as_of` is ingestion-time only (`docs/temporal.md`, cited by
  v1; not refetched over the network by this run).
- Retrieval QUALITY (ranking, ANN/BM25 comparison, embeddings, LLM answer synthesis); this
  run keeps `embedding_provider = "none"` and no LLM, exactly like v1. That gap is tracked
  separately by `catalogs/landscape/foundation.json`'s `overturn_protocol`.
- **Store migration / opening one store with both binaries.** Each binary gets its own fresh
  store (section 1); 2.3.2 opening a 2.4.0-migrated store, or vice versa, is a real and
  interesting question (the release-review doc already predicts 2.3.2 aborts with
  `DataSchemaAhead`) but is a DIFFERENT experiment from a same-checks binary comparison and
  is not run here.
- Re-verifying the 2.4.0 release tarball's sha256 against a network fetch of the GitHub
  release (section 2); this run has no network egress by design and takes that hash as
  supplied, asserted evidence, distinct from the binary sha256 this run does measure.
- The negotiated `initialize` protocolVersion difference found in section 3, finding 2, and
  the 2.4.0-only opt-in `memory_query`/`memory_read_page` fields listed in section 3, are
  recorded as observations, not gated pass/fail checks -- the task's four lettered items do
  not ask for either.
- Concurrent multi-client access to one server process; every check here is one client, one
  request in flight at a time (matching v1).
- Any change to the repository's adopted ai-memory pin (stays 2.3.2 per
  `manifests/stack.json` and the 2026-09-25 release-review decision); this run only produces
  comparison evidence.
- macOS/Windows native execution (Linux/WSL2 bubblewrap only, matching v1).

## 6. What counts as failure

A check fails when its response does not meet its pass bar above, including: a protocol
`error` where a success was expected (or vice versa); a wrong hit count, path, or body; a
changed `page_id` across restart; the binary's own sha256 changing between the start and end
of either phase; either bwrap invocation's process exiting non-zero or timing out; the phase
"pre" tool-call count not being exactly 69, or phase "post" not exactly 15. A failing check
is recorded as failing in `results-20260925.json` with its actual observed value; it is never
silently retried, hidden, or used to loosen the bar above after the fact.
