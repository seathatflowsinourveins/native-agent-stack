# Decision: layer-verdict integrity rules before the 2026-09-23 re-record (2026-09-23)

**Decided by:** unit `verdict-integrity`, catalog branch `claude/verdict-integrity-20260923` (base `38847e5`,
merged with catalog `main` at `9432720`, which carries PR #117).

**Scope:** the layer-verdict pipeline under `tools/sota-convergence/` (`build_verdicts.py`,
`lane_packets.py`, `record_verdicts.py`, `codex_lane.py`, `claude_lane.py`) and its CI re-check in
`scripts/landscape.py`. It answers seven defects of the peer update-path audit (workflow
`wf_77c0ea46-091`, catalog main `38847e5`) that had to be fixed before all 32 ledger rows are
re-recorded by both model families under `--run-id 20260923`. Host-receipt review independence,
the macOS receipt rule and the ruleset/CODEOWNERS findings of the same audit were decided in catalog
PR #117 (`scripts/platform_status.py`, merged at `9432720`); this record only makes the recorder use it.

## Decision

1. **Per-wave CI.** Each wave's `catalogs/sota-convergence/layer-verdicts-<run-id>.json` is frozen and
   registered by sha256 in `catalogs/sota-convergence/layer-verdict-waves.json`. `build_verdicts.py
   --check` (CI's unchanged invocation) verifies each wave byte for byte and against the rows whose
   `lanes.sealed_base` names it, and regenerates only the newest wave and the handbook block.
2. **Blind packets.** `--withhold-labels` strips stars, forks, watchers, `pushed_at`, `released_at`
   and any other popularity or timestamp key from every candidate and component copy, keeping
   `archived`/`license` only when the requirement names them, and lists each stripped field in
   `withheld`. The latest upstream release is withheld always (`upstream.latest`, with
   `upstream.prerelease` and the copy's `pin_behind_upstream`, which describe or are derived from it):
   a date-based tag such as inspect_ai's `release/2025-11-28` is a release date. Of the two options
   (strip only a date-shaped `latest`, or withhold it entirely) this is the stricter, and no packet
   requirement names releases, versions or maintenance. Default packets are byte-identical.
3. **No single-family winner.** A `codex_absent` layer stays `pending_lanes` unless
   `--allow-single-lane PATH` names a dated decision record under `docs/decisions/` carrying the
   exact line `single-lane-authorization: <catalog>/<layer_id>` for that layer (review of #122: a
   record that merely named the layer id, such as a wave document naming all 32 layers, authorized
   every one of them). The path and the record's sha256 are stored as `lanes.single_lane_decision`
   and `lanes.single_lane_decision_sha256`, and `landscape.py` rejects a recorded `codex_absent` row
   whose record is missing, elsewhere, lacks the line or changed since.
4. **Lane identity and two-family adjudication.** Lane returns declare `model.family` (claude lane
   `anthropic`, name `claude-*|opus|sonnet|fable|haiku`; codex lane `openai`, name `gpt-*|codex`), and
   the two families differ. `codex_lane.py` writes the Codex `model` itself from its own observation
   (the `--model` it passed to `codex exec -m`, else the event-stream model, else `unknown`), never from
   the model's response text. Each adjudication judgment records `judge {model, family}` and
   `stripped_packet_sha256`, which must equal the layer's sealed lane packet (its `packets/SHA256SUMS`
   entry at record time, its run-manifest `packet_sha256` in CI): the judge is shown the
   `--withhold-labels` packet the lanes judged, not a private reduction. A winner needs unanimous, unrefuted judgments from both lane families,
   each in both presentation orders; otherwise the row is a sealed split (`pending_lanes`).
   `winner_lane` is validated after that rule, so a unanimous single-family adjudication is a split
   whether it writes `null` or the lane its judges chose.
5. **Survivorship.** Every sealed wave writes `evidence/artifacts/layer-verdicts-<run-id>/run-manifest.json`
   listing every packet with its sha256, each lane's outcome (sealed, rejected with reasons, missing)
   and the `packets/SHA256SUMS` text; `landscape.py` requires each new-wave row there with both lanes
   accounted for. A row is new-wave when its `lanes.sealed_base` or any lane run id names a
   non-grandfathered wave, whether or not a lane carries a run id, and every recorded row must seal the
   lanes its agreement implies (both for `same_winner`/`disagree`, claude only for `codex_absent`), so a
   hand-edited row cannot skip identity, provenance or survivorship.
6. **Platform status: one shared rule.** `record_verdicts.py` calls PR #117's
   `scripts/platform_status.py` `platform_status(platform_id, winner, context)` for every platform,
   with `load_context(root)` once per run, so a qualifying macOS receipt records `accepted` on a
   re-record. Linux `accepted` needs a qualifying receipt or a `native_proven`/`measured_comparison`
   winner citing a registered `evidence/` file. The layer-verdict pipeline's own sealed files
   (`evidence/artifacts/layer-verdicts-<run-id>/`: packets, lane returns, adjudications and their
   inputs) never count: they are lane inputs or opinions, not execution receipts. That exclusion is
   made in the shared `registered_evidence_refs`, so the recorder, `landscape.py` and
   `component_matrix.py` agree. `landscape.py` re-checks a new-wave row on every platform with
   `declared_status_error` and a grandfathered row on `ENFORCED_PLATFORMS` (`macos-arm64`, as on main;
   the re-record widens it). The earlier Linux-only adapter in `landscape.py` is deleted.
7. **Reproducible lanes.** The Claude lane workflow is vendored at
   `examples/claude-native/workflows/layer-verdict-lane.js` under its `SHA256SUMS` (pin in
   `vendored-lanes.json`). New-wave Claude returns carry `{workflow_path, workflow_sha256,
   agentlab_commit}` (written by `claude_lane.py`), Codex returns `{codex_lane_py_sha256,
   prompt_sha256}` (written by `codex_lane.py`). Both must name lane code listed in the append-only
   `tools/sota-convergence/lane-provenance.json`: at record time the Claude pair must also equal the
   current `SHA256SUMS` entry of the vendored copy that entry names (the full `workflow_path` is
   matched, not its basename), and the Codex pair this checkout's `codex_lane.py` and
   `lane-prompt.md` hashes; `landscape.py` re-checks every sealed new-wave return against the
   registry in CI, and a unit test keeps the registry covering the current bytes.

## Review of #122 (2026-09-23)

An independent review of the merged #122 (head `2f19193`) found five defects to fix before the
32-row re-record; this branch (base `97a56e2`) fixes them, each with a regression test that fails
on the base (`tests/test_landscape.py`, `tests/test_record_verdicts.py` `ReviewOf122Tests` and
`CodexAbsentTests`, `tests/test_claude_lane.py`, `tests/test_codex_lane.py`,
`tests/test_lane_packets.py`):

8. **The row is what its sealed wave establishes (finding 1).** `landscape.py` recomputes a
   new-wave row's `agreement` from both sealed returns' `winner_keys`, resolved to component ids
   through the retained packet each return names, and requires a recorded row's winners to equal
   the chosen lane's set (`same_winner`/`codex_absent`: claude; `disagree`: the adjudication's
   `winner_lane`); an unrecorded new-wave row has no winners.
9. **Hash-bound, append-only sealed waves (finding 3).** `--write` refuses once a new wave's
   `run-manifest.json` exists unless `--append-rows` names only rows absent from it, and never
   overwrites a sealed file with other bytes. Rows store `lanes.run_manifest_sha256` and, when an
   adjudication was sealed for them, `lanes.adjudication_sha256`; `landscape.py` verifies both and
   rejects any file under a new wave's sealed folder that no row and not the run manifest references.
10. **Claude refutation (finding 5).** The lane (agent-lab `6aab001`, vendored sha256 `2eb9c10d…`,
    registered in `lane-provenance.json`) seals a final only when both lens votes on it returned
    unrefuted and returns a per-layer `refutation` summary; `claude_lane.py` copies it into the
    return, the lane-return schema gains it (`codex_lane.py` drops it from the Codex strict copy), and
    `record_verdicts.py` and `landscape.py` reject a Claude return whose summary shows a refuted or
    unknown final or lacks a lens vote.
11. **Retained packets (finding 6).** A new wave's `--write` copies its packets and `SHA256SUMS` into
    `<sealed_base>/packets/`, listed in the manifest's `retained_packets`, and refuses a packet with a
    withheld key; `landscape.py` re-checks each retained packet's hash and withheld keys (the policy
    `lane_packets.py` now imports from it), requires each row's packet there, and so binds every
    judgment's `stripped_packet_sha256` to a retained packet.
12. **Failed lanes (finding 7).** `claude_lane.py` and `codex_lane.py` list each layer they ran but
    could not return, with its reason, in `<work-dir>/<lane>/failures.json`; the run manifest records
    that lane as `failed` with the reason instead of a bare `missing`.

**Packet labels kept and withheld (finding 9).** `--withhold-labels` packets keep each candidate's
`adopted` marker. It correlates with the withheld incumbent disposition (every current default is
adopted), but the lane contract needs it: a winner set is 1-3 adopted candidates and every adopted
non-winner must appear in `alternatives` (`lane-prompt.md` rules 2-3, `record_verdicts.py`
`validate_lane_return`), so removing it would remove the rule that keeps an unqualified candidate
out of the winner set. The trade-off is kept deliberately; a lane still sees the evidence of every
candidate. The candidate-only `note` (a newcomer's `demonstrated_gap` or a keep-but-compare entry's
overturn comparison) exists only on non-adopted candidates and only hints at their status, so it is
now withheld with `newcomer` and listed as `candidates[].note`; no packet requirement or prompt rule
reads it.

**Review of the fix round (2026-09-23, head `fcee72b`).** An independent review found one medium
and two low defects; each is fixed with a regression test that fails on `fcee72b`
(`tests/test_lane_packets.py` `RecursiveWithheldKeyTests`, `tests/test_landscape.py`
`test_retained_packets_are_checked_at_every_depth`, `test_a_sealed_adjudication_is_bound_by_the_run_manifest`
and `test_a_layer_verdicts_folder_no_row_can_name_is_rejected`, `tests/test_record_verdicts.py`
`ReviewOf122Tests` `test_a_packet_carrying_a_disposition_label_or_a_nested_withheld_key_is_refused` and
`test_the_run_manifest_lists_each_sealed_adjudication`):

- *Withheld keys at any depth (medium).* `withheld_packet_keys` checked only the positions
  `withhold_popularity` strips, so a nested release date, `evidence.stars`, a top-level `newcomers`
  list, a non-null `review_status` or a `decisions[].selection` passed CI and `--write`. The check now
  walks the whole packet. At any depth it rejects a popularity/recency key, `pin_behind_upstream`,
  `newcomer`, `note`, and any key naming the latest version, a release or a newcomer. On a
  candidate or component copy it also rejects `selection`, `disposition`, `rationale`,
  `current_choice` and a non-null `review_status`. At the top level it rejects `current_choice`,
  `decision` and `rationale`. It also requires every always-listed policy label in `withheld[]`,
  which confirms the packet was built with `--withhold-labels`. The only exemptions are
  `archived`/`license` when the requirement names them and the packet's own `checked_at`.
  `lane_packets.withhold_popularity` strips with the same predicate at any depth.
  The review also exposed one leak in real packets: `upstream.latest_flag`, whose tag-listing
  fallback can be date-shaped (`release/2025-11-28` in the 2026-09-23 manifest's packets). It is now
  withheld and listed. The default (2026-09-22) build is byte-identical.
- *Adjudication bound by the manifest (low).* The run manifest entry of a row with a sealed
  adjudication (recorded or split) carries `adjudication: {outcome: sealed, sha256}`. `landscape.py`
  requires it to equal the row's `lanes.adjudication_sha256` and re-hashes the file against it. A
  rewrite therefore has to change the manifest and every row's `run_manifest_sha256`, the same as a
  sealed return.
- *Stray wave folders (low).* A `layer-verdicts-<id>` folder whose id is not alphanumeric is now
  rejected instead of skipped.
- *Kept deliberately: a proposal after a failed revision.* The lane (agent-lab `6aab001`) still seals
  a never-refuted proposal when the revision ran only for a major finding and that revision is then
  refuted or comes back unknown. The lens prompts define such a major finding as not refuting the
  winner (for example a stronger non-adopted candidate missing from `challenger_preferred`). Both
  lenses returned unrefuted on the proposal, and the sealed Claude return records `revision_status`, so the
  unresolved major finding is visible. Discarding the proposal would turn a failed attempt to add
  detail into no verdict. Overturn: a re-record in which a sealed proposal with a refuted revision
  is shown wrong by its retained evidence.

**Left for a later PR:** finding 4 (a CI step comparing `layer-verdict-waves.json` with the base
branch so a single PR cannot rewrite an older wave's document, registry hash and rows together) and
finding 8 (the Claude lane's model name taken from the workflow's `result["model"]` and bound to a
child-usage receipt hash instead of `--resolved-model` free text).

## Grandfathered wave

`GRANDFATHERED_RUN_IDS = {"20260922"}` in `scripts/landscape.py`. The 32 rows sealed on 2026-09-22
keep the rules they were recorded under: no `model.family` or provenance on their lane returns,
Opus-only adjudications covering both presentation orders (12 disagree rows, 10 recorded), no run
manifest (their `packets/` and `SHA256SUMS` are retained under
`evidence/artifacts/layer-verdicts-20260922/`; a manifest generated now could not list that run's
rejected returns, so none is fabricated), and Linux `accepted` from the lane's own evidence class.
Under the shared rule 13 of the 33 Linux `accepted` winners would derive `conditional` (six rows:
`foundation/ci-supply-chain`, `foundation/hosting-services`, `us-equities/market-data-reference`,
`storage-compute`, `research-factors-ml` and `portfolio-risk`, measured with
`declared_status_error` on the merged tree); they stay unchanged because the wave is frozen by hash and
any row still naming it must equal its frozen entry, and the re-record moves them. No 2026-09-22 row is
`codex_absent`, so item 3 needs no grandfathering.

The exemption is narrow because the committed wave is frozen by the tools and by CI, whether or not a
later wave exists yet (an earlier revision froze it only once a newer wave was registered, and
`record_verdicts.py` defaulted to this run id):

- `record_verdicts.py` has no default `--run-id`; its `--write` refuses a grandfathered id once
  `--root` holds that wave (its sealed directory or a registered wave document), so nothing is
  re-recorded there and no run manifest is ever added to it.
- `build_verdicts.py --write` refuses to regenerate or re-register a registered grandfathered wave,
  even as the newest; `--check` compares every row still naming it with the hash-registered document.
- `tests/test_layer_verdicts.py` `GrandfatheredWavePinTests` (CI runs `python3 -m unittest`) pins
  the document's sha256 and registry entry and the sha256 listing of all 122 files under the sealed
  2026-09-22 directory, and asserts no `run-manifest.json` is there.

Rows move out of the exemption by being re-recorded under a new run id (all 32 are planned for
`20260923`); they cannot move into it.

## Keep-but-compare: two-family adjudication

Settling a lane disagreement by both lane families is the current default, not a demonstrated best
judge: every judge shares a family with one lane it rules on. Alternatives considered: a single-family
two-order panel (the 2026-09-22 rule; rejected because one family can then decide alone), and a third
family judge (preferred in principle; no judge of a third family has been qualified on this task).

**Overturn condition.** A qualified third-family judge (for example the key-free local Qwen3-8B-AWQ
worker) clears a preregistered judge-agreement bar on the sealed 2026-09-22 and 2026-09-23 adjudication
packets. The rule then moves to, or adds, that judge.

## Evidence and limits

Regression tests reproduce each audit claim on the base code (they fail at `38847e5`) and pass after the
change; see the branch's commit message for the names. These are local synthetic-fixture checks: no
lane, judge or re-record was run for this decision, and every family and provenance field remains a
declaration by the runner that writes it, checked for shape and consistency, not authenticated.
Lane-code hashes are now bound to registered bytes, and judgment packet hashes to the sealed packet,
but the registry only proves which code a runner claims to have run, and a judge that saw a different
packet while writing the sealed packet's hash is not detected. An independent Opus review of the first
revision found the grandfather rule too broad and four minor gaps (shared-reference stripping in
`lane_packets.py`, pipeline artifacts counting as receipts, substring layer matching, format-only
provenance and packet hashes); all five are fixed with regression tests that fail on the first
revision.

A re-review of the second revision found the recorder still on the Linux-only adapter although
PR #117 was already on `main`, plus five minor gaps (a hand-edited new-wave row skipping the checks,
`winner_lane` validated before the two-family rule, `--checked-at` defaulting to 2026-09-22, the
Codex `model.name` taken from response text, and `upstream.latest` surviving `--withhold-labels`);
each is fixed with a regression test.
