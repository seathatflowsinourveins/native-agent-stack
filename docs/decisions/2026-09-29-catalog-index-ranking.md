# Decision: one ranked catalog index, ordered by recorded role, then evidence (2026-09-29)

**Decided by:** a coordinator's design review of two candidate designs (a reuse-first design and a model-first design,
judged 25 to 19 of 30 on correctness, reuse, rule clarity, honesty, validation and change size), built by a Claude Code
worker on branch `claude/catalog-index-ranking-20260929`, based on `origin/main@df412368`. The review cited its evidence at
`5cfa2400`; between the two revisions no input the index reads changed (only `files[]` of `manifests/evidence.json`, which
the index never reads). After an independent review and verification of that build, one repair round rebased the branch
onto `origin/main@ed293987` and made the changes this record now states (the stack-pin rule for alternatives, duplicate
role records, the bot's index regeneration and the procedures that refresh the matrix).

**The request.** One validated index over the scattered catalog files, with every one of the 32 layers' winners,
alternatives and candidate cards ranked by evidence, and the order readable in the offline explorer.

## Decision

`scripts/catalog_index.py --write` generates `catalogs/landscape/catalog-index.json`, a read-only join of the committed
component evidence matrix, both layer ledgers, the repository decision index (with its coverage aliases),
`manifests/stack.json`, `receipts[]` and `convergence_records[]` of `manifests/evidence.json`, the landscape manifest, and
the host receipts under `evidence/hosts/` (through `host_receipts.build_summary`, with the receipt schema and the platform
profiles it reads). It never selects a winner, changes a verdict, records a receipt or infers a benchmark win. `--check` (a
new CI step after the grand-list check) rebuilds it in memory, runs the fatal checks F2-F16 and byte-compares it (F1).
`scripts/build_ecosystem.py` embeds it as the explorer's hidden-unless-present **Ranked by evidence** tab and re-derives every
position with the index module's own functions. `tools/sota-convergence/blind_checkout.py` removes it from blind exports,
because it names every layer's winner by value. No catalog is merged or retired.

**The rule** (frozen 2026-09-29, `RULE` in the script; order within a layer only, no order across layers). Placements are
one per (layer, entity), keeping every source record; when an entity has more than one record of its governing role in
a layer (two winner component ids of one repository, or two alternatives of one repository, which the validators allow),
the first record by path and pointer governs the placement and a `role/duplicate-role-record` status item lists every
such record, so none is merged silently. `out_of_scope` goes to `outside_ranking`, `observed_failure` to `caution`, and
everything else is ranked, in the two `pending_lanes` layers too. Keys compare lexicographically, smaller first, with no
arithmetic across keys:

1. **recorded_role**: verdict winner 0, verdict alternative 1, card-only candidate 2. A card never raises a role.
2. **evidence_tier**: A for `native_proven`/`measured_comparison` (and card kinds `native_execution`/`measured_comparison`,
   or `mixed` with a retained local result, the `scripts/landscape.py` observed-failure predicate); B for
   `local_integration`/`synthetic` (tied); C for `source_review` or `mixed` without a retained result; U for
   `requirement_fit` (no policy row), flagged.
3. **host_verification_at_pin**, on linux-wsl2-x86_64 only, from the matrix's derived status and the host receipts, never
   the declared status. Level 0 needs an independently reviewed `native_proven` use-stage host receipt on that platform
   that records the pinned version, is current (not superseded at its version, not on a forked chain) and is in the
   layer's scope.
   - Winners: 0 `host_verified` (derived `accepted` on such a receipt, which `scripts/platform_status.py` binds to the
     winner's verdict pin), 1 derived `accepted` by another route (this includes the registered-evidence route, which is
     bound to no pin), 2 `conditional`, 3 `not_established`/`untested`.
   - Alternatives: 0 `host_verified_at_stack_pin`: a receipt of the `manifests/stack.json` component that shares the
     alternative's repository, which `component_matrix.build_alternative` alone accepts, on linux-wsl2-x86_64, whose
     `tool_versions` entry equals that component's stack version (`host_receipts.pin_matches`). 1 otherwise. That
     includes the matrix's `host_verified`, a join by repository on any platform and at any version, when no such
     receipt exists; the placement is then flagged `verification/alternative-receipt-version-mismatch` (a receipt at
     another version), `verification/alternative-receipt-version-unknown` (no comparable version recorded, or no stack
     version) or `verification/alternative-receipt-off-platform` (only another platform's receipt verifies it).
     `receipts_recorded` is an annotation.
   - Card-only candidates: a constant.

   The index reruns `component_matrix.build_alternative` on the host receipts and fails (F2) when that does not
   reproduce the matrix's alternative `e2e_state`. It repeats no version or pin: `receipt_versions` counts an
   alternative's qualifying linux-wsl2-x86_64 receipts as `at_stack_pin`, `other_version` or `unknown_version`, and
   `stack_component_id` names the component.
4. **measured_rank**: 0 unless every member of a K1-K3 tie class has a verified result in one comparability group (layer,
   the layer's overturn metric, benchmark id and major version, fixture sha256 set, host profile, pins, direction); then the
   approximate rank from non-overlapping intervals, or an exact pass before an exact fail on the same frozen fixture. Empty in
   this version: no layer records structured measurements.

Positions are competition ranks (1, 1, 3) and tied entries share a position (`shared`, shown as "=n"). Upstream pin
currency (`pin_current`), stars, releases, sweep review status, votes, confidence, receipt recency, the declared
`catalog_status`, dispositions within a role and priorities are never sort keys. Conflicts become status items
(`status_items`, Backstage style); none is resolved.

## Counts recomputed by the generator on `origin/main@ed293987` plus this branch

- 32 layers (30 recorded, 2 `pending_lanes`), 614 source records, 0 unresolved; 440 placements: 414 ranked (66 winners, 164
  alternatives, 184 card-only candidates), 26 outside the ranking, 0 under caution. 36 of the ranked placements are in the
  two pending layers.
- 368 of 414 ranked placements share a position; 120 distinct positions; the largest tie holds 16.
- Winners by K3: 44 `host_verified`, 5 `accepted`, 13 `conditional`, 4 `not_established`. Alternatives: 6
  `host_verified_at_stack_pin` (level 0) and 158 at level 1: 1 `host_verified` off the stack pin, 21
  `receipts_recorded`, 136 `not_run`. The one off the pin is ggml-org/llama.cpp in `foundation/observation-inference`:
  its reviewed use receipt records `b11146 (0.5.0-dev)` against the stack pin `b11057 (0.4.1-dev)`, so it moves from =4
  (level 0, beside agentsview) to =5 (level 1, beside ntfy, grafana, claude-hud and alertmanager). Winner `pin_current`:
  33 true, 14 false, 19 unknown.
- Entities: 875 (the decision-index records); receipts: 172 listed, 172 attached; experiments: 25 convergence records, none
  joined (a record path carries no layer or component key).
- Coverage of 94 listed catalog and manifest files: 8 index inputs, 4 matrix inputs, 30 decision-index sources, 52 not
  reached; 5 unmodeled collections (three `non_repository_decisions` arrays, `manifests/stack.json#/models` and
  `catalogs/us-equities/models.json#/entries`).
- Status items (22 types):
  - role: 72 `role/selected-card-not-winner` (30 verdict alternatives, 42 card-only), 11 `role/selected-card-no-verdict`,
    4 `role/winner-card-not-selected`, 0 `role/duplicate-role-record`;
  - status and evidence: 4 `status/declared-above-derived`, 6 `evidence/winner-tier-below-alternative` (layers), 5
    `evidence/class-verification-inversion` (pairs), 25 `evidence/mixed-kind`, 4 `evidence/unmapped-kind`;
  - verification: 28 `verification/joined-by-repository`, 1 `verification/alternative-receipt-version-mismatch`, 0
    `verification/alternative-receipt-version-unknown`, 0 `verification/alternative-receipt-off-platform`, 2
    `verification/host-fail-recorded`;
  - freshness: 33 `freshness/pin-behind-upstream` (14 false, 19 unknown), 30 `freshness/layer-reopened`;
  - identity: 8 `identity/multiple-component-ids`, 0 `identity/component-id-conflict`, 0 `identity/unresolved`;
  - other: 8 `domain-card/default-never-winner`, 1 `source/sweep-manifest-divergence` (manifests 0922, 0923 and 0929 in
    use), 52 `coverage/not-reached`.
- Overturn metrics: 5 pairs flip between class-first and verification-first order, 0 of them winner pairs (all five in
  `foundation/observation-inference`: otel-tui against grafana, alertmanager, ntfy, claude-hud and, since the stack-pin
  rule, llama.cpp); a `pin_current` tiebreak would unshare 23 placements (368 to 345 shared).
- The file is 1,256,834 bytes, under the 1,500,000-byte warning and the 2,000,000-byte cap (gitleaks skips files over
  2 MB).
- At `df412368`, before the rebase and the repair round, every count the design review simulated at `5cfa2400` equalled
  its simulation (it did not simulate the 614 source records, the file size or `domain-card/default-never-winner`), and
  every ranked placement's role, tier, verification level and pin currency equalled that simulation's placement list.
  Since then `origin/main` changed the matrix (the 2026-09-29 landscape sweep: `pin_current`, the 0929 manifest), added
  one receipt and one catalog file, and the repair round moved llama.cpp and added four status types.

## Deviations from the reviewed schema

The repository's secret scan (gitleaks 8.30.1 with `.gitleaks.toml`, run by the pre-commit hook and in CI) refused the
first generated file with 48 findings, all false positives, so two fields of the reviewed schema changed shape:

- `entities[].decision_index.key` is `entities[].decision_index.repository`. The canonical owner/name under a key named
  `key` matched the `generic-api-key` rule 34 times.
- Placements do not repeat a winner's `pin`; `matrix_record` points to the matrix entry that keeps it verbatim. The file
  names Sourcegraph repositories, which arms the `sourcegraph-access-token` rule, and that rule then matched 14 pin lines
  holding 12 bare 40-hex commit ids, all of them ids that `.gitleaks.toml` already allowlists by value for the SOTA
  manifests. Restoring the field takes a separate, reviewed allowlist change first (the index path joins that
  value-pinned allowlist, with its test), then a one-line generator change; the ranking reads no pin, so the order does
  not change.

**Sign-off.** The coordinator approved both deviations in the repair round (2026-09-29), for the reason above: each
avoids a gitleaks false positive without a rule change.
- The winner `pin` is dropped from placements. Every winner still reaches its pin through `matrix_record`, a pointer into
  `catalogs/landscape/component-evidence-matrix.json`, and 66 of 66 resolve to the matrix entry with that component id
  and its pin.
- `decision_index.key` is renamed `decision_index.repository` (875 of 875 entities).

For the same reason the repair round's `receipt_versions` counts versions and never repeats one, and the file holds no
bare 40-hex id (test 30).

## Alternatives rejected

- **A blended score** (for example the best-of-generator project score): it hides which behaviour a result rests on; the
  OpenSSF Scorecard README says aggregate scores tell "nothing about what individual behaviors a repository is or is not
  doing", and `scripts/component_matrix.py` already refuses a blended convergence score.
- **Evidence before role**: a recorded winner would sort below a stronger-evidence alternative in 6 layers, so the index
  would select winners.
- **Verification before class**: it departs from the user's listed order and moves the 5 pairs above.
- **An alternative's repository-joined `host_verified` at level 0, disclosed as bound to no pin or platform** (the
  review's first option): the order would still put a receipt at another version, or on another platform only, ahead of
  unverified alternatives. The repair round took the review's second option, binding level 0 to a linux-wsl2-x86_64
  receipt at the stack pin, as the coordinator directed.
- **The `pin_current` tiebreak**: it is upstream currency, and "a current release or repository activity check does not
  supersede an accepted pin" (`catalogs/landscape/manifest.json` rules); the newest sweep rows are not individually reviewed.
- **Unranked pending layers**: the request covers each of the 32 layers; they rank on evidence only, under a banner.
- **A Thoughtworks-radar crosswalk**: a second ordinal that disagrees with the position order in 4 pairs, and "Adopt" claims
  more than an unreviewed `accepted` supports.
- **A committed Markdown twin**: the decided form is the JSON plus the explorer page, and a new `docs/**/*.md` page would move
  the frozen QMD counts of the Gate A window.
- **Physical merges or retirements** (the wave-2 gap ledger, layer-verdicts, the sweep manifests, the decision index and
  others): each is a CI-checked input, a pinned fixture or a cited dated record.
- **A multi-namespace entity model** (seven entity kinds, a router change and four PRs): the repository identity of
  `scripts/catalog_decisions.py` already covers every placed record.

## Overturn conditions

1. A layer records a structured, verified, comparable measurement: `measured_rank` activates with no rule change.
2. `class_vs_verification_flipped_pairs` includes a winner pair or exceeds 4: reconsider verification-first order.
   **Met since the repair round: 5 pairs**, none of them a winner pair. The stack-pin rule moved llama.cpp to level 1,
   behind otel-tui's level 0, while llama.cpp keeps tier A over otel-tui's tier C. The rule stays class-first until the
   coordinator decides; this record does not move the threshold.
3. The user chooses the `pin_current` tiebreak (winners only; true, then unknown, then false, as a fifth key): shared
   placements fall from 368 to 345 of 414 at this revision.
4. A recorded ordering of `local_integration` against `synthetic` appears: split tier B.
5. macOS gets accepted receipts for most winners: add a second, per-platform ordering.

A layer added to or removed from a ledger updates `EXPECTED_LAYER_COUNT` (F2) and this record together.

## Sources

Read 2026-09-29 during the design review; the quotations are the review's.

- OpenSSF Scorecard README at `ac4b5844` (no aggregate score); GRADE Handbook, updated October 2013, section 5.1.1 (study
  design sets the starting quality; expert opinion is not a quality category); MLPerf results messaging guidelines at
  `45b8b625` (compare only compatible results; label unverified ones); SPEC Fair Use rules, updated 21 September 2026 (state
  the basis; a new major version is generally not comparable); Chatbot Arena, arXiv 2403.04132v1 (rank = 1 + the number of
  entries whose interval lies entirely above; approximate ranking); Backstage descriptor format and "life of an entity"
  (read-only status items; no two providers emit the same entity); cncf/landscape2 README and `docs/config/data.yml` at
  `2ee800df` (generated from data files; `second_path` lists one item in several places).
- Repository patterns reused: `scripts/component_matrix.py` (read-only join, `--check`/`--write`, `serialize`, private-content
  scan, attribute-call registration), `scripts/new_host_grand_list.py` (reads the committed matrix; names the regeneration
  sequence), `scripts/catalog_decisions.py` (identity, aliases, pointers), `scripts/platform_status.py` (one rule for every
  caller) and `build_convergence` in `scripts/build_ecosystem.py`.

## Residuals

- The PR edits `docs/lanes.md`, so it is `lane:shared` and needs the trading lane's acknowledgement. The cost to state in
  that request, in the review's words: "any change that rewrites the component evidence matrix, plus receipts[],
  convergence_records[], decision index, stack, aliases, landscape manifest and catalog JSON additions or removals" now
  also runs `python3 scripts/catalog_index.py --write`, and CI enforces it. Since the repair round the index also reads
  the host receipts under `evidence/hosts/` (a new receipt already rewrites the matrix, and a receipt of an alternative's
  stack component can move that alternative's K3 even when the matrix does not change), `adoption/host-receipt.schema.json`
  and the platform profiles in `adoption/manifest.json`, so a change to those runs it too.
- The procedures that refresh the matrix name the index write after the grand list's: `docs/lanes.md`,
  `docs/contributing-evidence.md` (steps 4 and 5, and the review step), `docs/next-host-stages.md`, `adoption/update.md`,
  `recipes/sota-convergence-practice.md`, `recipes/saturation-sweep.md` (after its matrix write) and
  `adoption/platforms/macos-arm64.md` (whose CI recording smoke commits nothing and so skips it), and
  `scripts/new_host_grand_list.py`'s stale message. `.github/workflows/adoption-bootstrap.yml`'s macOS recording smoke is
  unchanged. The catalog-freshness propose path regenerates the index itself (2026-09-29 addendum of
  `docs/decisions/2026-09-23-bot-pr-dispatch.md`).
- This record is a new `docs/**/*.md` file, which the QMD `foundation-docs` collection indexes; merge it outside the Gate A
  window W or hold it until the window closes.
- **Secret scan on a clean tree.** Run `gitleaks dir . --config .gitleaks.toml --max-target-megabytes 2 --redact
  --no-banner` on a tree without `__pycache__` directories: remove them first, or run the tests with
  `PYTHONDONTWRITEBYTECODE=1`. After the test suite has written bytecode, the ignored, untracked
  `tests/__pycache__/test_omniroute_gateway_unit.cpython-313.pyc` holds a pre-existing `generic-api-key` false positive
  whose source test this branch does not touch. The committed tree and the branch's history scan clean.
- **Five-symbol rule and `scripts/freshness_propose.py`.** The repair round edits that module for the bot's index
  regeneration. It already held two bare `register_file(...)` calls, which are Name-call sites of the Gate A oracle
  (`main` lines 598 and 649). They are left as they were (now lines 608 and 680), so the oracle's set of sites does not
  change, and no definition or bare call of the five symbols is added anywhere. The literal AST scan over the branch's
  changed files therefore lists those two pre-existing sites. Converting them to attribute calls would remove two oracle
  sites; that choice is left to the coordinator.
- **No GPT-6 cross-family review ran** on this build or its repair round: Codex capacity is reserved for the Gate A
  (#381) reviews until 2026-10-04. The independent review and verification were Claude sessions.
- `domain-card/default-never-winner` counts 8, a figure the review had not verified: the reuse-first design reported 5
  (ntfy, grafana, context-mode, alertmanager, quantstats); the generator also flags
  open-telemetry/opentelemetry-collector, quantconnect/lean.brokerages.alpaca and the repository itself, each a
  decision-index `catalog_card` with decision `default` and no winner placement under its canonical identity.
