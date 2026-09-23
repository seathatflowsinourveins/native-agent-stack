# Decision: layer-verdict integrity rules before the 2026-09-23 re-record (2026-09-23)

**Decided by:** unit `verdict-integrity`, catalog branch `claude/verdict-integrity-20260923` (base `38847e5`).

**Scope:** the layer-verdict pipeline under `tools/sota-convergence/` (`build_verdicts.py`,
`lane_packets.py`, `record_verdicts.py`, `codex_lane.py`, `claude_lane.py`) and its CI re-check in
`scripts/landscape.py`. It answers seven defects of the peer update-path audit (workflow
`wf_77c0ea46-091`, catalog main `38847e5`) that had to be fixed before all 32 ledger rows are
re-recorded by both model families under `--run-id 20260923`. Host-receipt review independence,
macOS platform status and the ruleset/CODEOWNERS findings of the same audit belong to catalog PR #117
and are not decided here.

## Decision

1. **Per-wave CI.** Each wave's `catalogs/sota-convergence/layer-verdicts-<run-id>.json` is frozen and
   registered by sha256 in `catalogs/sota-convergence/layer-verdict-waves.json`. `build_verdicts.py
   --check` (CI's unchanged invocation) verifies each wave byte for byte and against the rows whose
   `lanes.sealed_base` names it, and regenerates only the newest wave and the handbook block.
2. **Blind packets.** `--withhold-labels` strips stars, forks, watchers, `pushed_at`, `released_at`
   and any other popularity or timestamp key from every candidate and component copy, keeping
   `archived`/`license` only when the requirement names them, and lists each stripped field in
   `withheld`. Default packets are byte-identical.
3. **No single-family winner.** A `codex_absent` layer stays `pending_lanes` unless
   `--allow-single-lane PATH` names a dated decision record that names the layer; the path is stored
   as `lanes.single_lane_decision` and `landscape.py` rejects a recorded `codex_absent` row without it.
   The record must name the layer id as a whole token (`workers` is not named by
   `agents-models-workers`).
4. **Lane identity and two-family adjudication.** Lane returns declare `model.family` (claude lane
   `anthropic`, name `claude-*|opus|sonnet|fable|haiku`; codex lane `openai`, name `gpt-*|codex`), and
   the two families differ. Each adjudication judgment records `judge {model, family}` and
   `stripped_packet_sha256`, which must equal the layer's sealed lane packet (its `packets/SHA256SUMS`
   entry at record time, its run-manifest `packet_sha256` in CI): the judge is shown the
   `--withhold-labels` packet the lanes judged, not a private reduction. A winner needs unanimous, unrefuted judgments from both lane families,
   each in both presentation orders; otherwise the row is a sealed split (`pending_lanes`).
5. **Survivorship.** Every sealed wave writes `evidence/artifacts/layer-verdicts-<run-id>/run-manifest.json`
   listing every packet with its sha256, each lane's outcome (sealed, rejected with reasons, missing)
   and the `packets/SHA256SUMS` text; `landscape.py` requires each new-wave row there with both lanes
   accounted for.
6. **Linux platform status.** `accepted` needs a `native_proven`/`measured_comparison` winner citing a
   receipt or `evidence/` artifact registered in `manifests/evidence.json`; otherwise `conditional`.
   The layer-verdict pipeline's own sealed files (`evidence/artifacts/layer-verdicts-<run-id>/`:
   packets, lane returns, adjudications and their inputs) never count: they are lane inputs or
   opinions, not execution receipts.
   `record_verdicts.py` reaches the rule through a one-line adapter import with the call shape of
   PR #117's shared `scripts/platform_status.py`, which was not on `origin/main` at `05e134f` when this
   was built.
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

## Grandfathered wave

`GRANDFATHERED_RUN_IDS = {"20260922"}` in `scripts/landscape.py`. The 32 rows sealed on 2026-09-22
keep the rules they were recorded under: no `model.family` or provenance on their lane returns,
Opus-only adjudications covering both presentation orders (12 disagree rows, 10 recorded), no run
manifest (their `packets/` and `SHA256SUMS` are retained under
`evidence/artifacts/layer-verdicts-20260922/`; a manifest generated now could not list that run's
rejected returns, so none is fabricated), and Linux `accepted` from the lane's own evidence class.
Under the new Linux rule two recorded rows would change (`foundation/ci-supply-chain` and
`foundation/hosting-services`, six winners, `accepted` to `conditional`); they stay unchanged because the
wave is frozen by hash and any row still naming it must equal its frozen entry. No 2026-09-22 row is
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
