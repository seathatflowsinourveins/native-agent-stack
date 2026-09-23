# Current landscape: choices and alternatives

Open the offline comparison view (`docs/ecosystem/index.html#landscape`; it is
generated, not committed -- build it with `python3 scripts/build_ecosystem.py
--write`, or download it from a `publish-catalog.yml` release artifact) for
the requirement, current choice, named competitors, evidence and reopening
condition in **all 20 foundation layers and the 12-layer US-equities trading
taxonomy** (`catalogs/sota-convergence/manifest-20260922.json#/taxonomy`).
Download its combined JSON from the page, or start with [manifest.json](manifest.json).

As of 2026-09-22 `us-equities.json` carries schema v2 and is restructured onto
that 12-layer taxonomy (`market-data-reference`, `identity-provenance`,
`storage-compute`, `data-quality-orchestration`, `research-factors-ml`,
`backtesting-engine`, `execution-broker`, `portfolio-risk`,
`evaluation-experiments`, `agents-models-workers`, `observability-hosting`,
`security-supply-chain`) instead of the four prior domain rows
(`foundation-memory`, `agents-operations`, `data-research`,
`engines-strategies`). Each row now names the `group` (the domain document its
content is primarily derived from) and carries a "Derived from domain row
&lt;group&gt; (2026-09-22): " prefix in `rationale`. The four original domain
rows are preserved verbatim, unrestructured, in the top-level `domain_rows`
array of `us-equities.json` so nothing from the prior review is lost.

For the complete installation and decision sequence, use the
[grand catalog handbook](../../docs/grand-catalog-handbook.md). It connects
[repository quality review](../../docs/candidate-quality-review-20260921.md),
[actual native-runtime review](../../blueprints/catalog-runtime-review/README.md)
and [clean-install evidence](../../blueprints/catalog-clean-install/README.md).
The HTML embeds these guides and the source-backed quality criteria for the
focused challenger set. Unknown quality/cost remains explicit.

Each selected component has an explicit current role explanation. Every layer
also has a [research continuation record](research-state.json): its next useful
comparison, evidence and requirement trigger. Use the
[new-PC/session guide](../../docs/landscape-continuation.md) and
[hosting/container comparison](../../docs/hosting-container-practice.md) when
those boundaries apply. A complete index is distinct from comparative saturation.

The current comparison joins [foundation.json](foundation.json) and
[us-equities.json](us-equities.json). The existing 152 domain candidate cards
remain available, binding to every trading-taxonomy row that shares its
originating domain document's `group` (several taxonomy layers can share one
`group`, e.g. `data-research` feeds `market-data-reference`,
`identity-provenance` and `storage-compute`), with their original dates, pins,
rationales and limits. The canonical repository explorer retains the wider
research inventory. Neither record counts nor discovery breadth rank the tools.

## Read a decision

| Outcome | What it means |
| --- | --- |
| Selected for this scope | The retained approach meets the stated requirement at the linked evidence depth. Several complementary tools can be selected in one layer. |
| Observed test failure | The named version/host/operation has an actual retained failure. This does not condemn all versions or uses. |
| Measured tradeoff | Recorded results expose a cost, compatibility or quality tradeoff; read the denominator and limits. |
| Conditional alternative | Credible for a different requirement or a future matched comparison. |
| Not qualified | Required task or deployment evidence is missing. No failed test is implied. |
| Overlapping capability | The current stack already supplies the needed role; replacement value has not been established. |
| Outside this requirement | A different use case, constraint or deployment boundary applies. |

Every layer records what would overturn its decision. Evidence labels distinguish
source review, requirement fit, native execution and measured comparison. The
[acceptance policy](../../docs/acceptance-evidence-policy.md) governs the strength
of the claim. There is no universal best-in-field claim.

## Layer-verdict schema v2

Every row in both `foundation.json` and `us-equities.json` also carries a
second, independent verdict record layered on top of the v1
requirement/current_choice/candidates fields above (all v1 fields are kept
unchanged):

- `group` -- trading rows only: the domain document id (`foundation-memory`,
  `agents-operations`, `data-research` or `engines-strategies`) the row's
  content derives from. `null` on foundation rows.
- `verdict_status` -- one of `pending_lanes` (no lane has run; `winners` and
  `alternatives` may be empty), `recorded` (a lane selected a winner: needs
  at least one winner and one alternative, a `why_selected` distinct from
  every alternative's `why_not_default`, and a `verdict_overturn_when` naming
  a fixture/blueprint/test path or a runnable command) or `no_selection` (no
  qualified candidate yet: needs a nonempty `open_gaps`).
- `verdict_overturn_when` -- the recorded verdict's own overturn condition
  (text; empty or absent unless recorded). The v1 `overturn_when` stays the
  dated review's condition, which the quality comparison mirrors, and is never
  rewritten by a lane.
- `winners[]` -- `{component_id, repository (https URL or null), pin,
  evidence_class, why_selected, evidence_refs[], recipe_ref, platform_status}`.
  `pin` must equal the [sota manifest](../sota-convergence/manifest-20260922.json)
  pin for that `component_id` when the component is listed there; `recipe_ref`
  must resolve to an [`adoption/manifest.json`](../../adoption/manifest.json)
  `recipe_map` key or an existing repository path; `platform_status` covers
  exactly `linux-wsl2-x86_64` (`accepted`/`conditional`/`not_established`) and
  `macos-arm64` (currently always `untested` on this profile).
- `alternatives[]` -- `{name, repository, disposition, why_not_default,
  evidence_class, evidence_refs[], source}`, `source` one of `star`, `awesome`,
  `discovery_index`, `lane:claude`, `lane:codex`.
- `overturn_protocol` -- `{fixture_paths[], metric, arms[]}`; may be empty
  while `pending_lanes`.
- `lanes` -- `{claude: {run_id, sealed_sha256}, codex: {run_id,
  sealed_sha256}, agreement}`; `agreement` is one of `same_winner`,
  `disagree`, `codex_absent`, `pending`. A nonempty `sealed_sha256` must have
  a corresponding retained file under
  `evidence/artifacts/layer-verdicts-20260922/<lane>/<run_id>.json`.
- `open_gaps[]`, `checked_at` (per-row date).

The v2 migration from the September 2026 v1 review set every row to
`verdict_status: "pending_lanes"` with empty `winners`/`alternatives`/`open_gaps`;
it selected no winner and ran no lane. On 2026-09-22 the Claude lane recorded all
32 rows (PR-5). Every row carries `lanes.agreement: "codex_absent"` because the
Codex lane could not run (account usage limit until 2026-09-28); four trading rows
record in `open_gaps` that their packet carried the group's candidates instead of
the layer's own tools (see the handbook's "Limits of the September 22 verdicts").
[`tools/sota-convergence/build_verdicts.py`](../../tools/sota-convergence/README.md)
joins these rows with the sota manifest and `adoption/manifest.json` into
[`catalogs/sota-convergence/layer-verdicts-20260922.json`](../sota-convergence/layer-verdicts-20260922.json)
and the generated section of the
[grand catalog handbook](../../docs/grand-catalog-handbook.md#per-layer-verdicts-generated).

## Current metadata and historical evidence

[upstream-snapshot.json](upstream-snapshot.json) records fresh primary-source
metadata for every selected component, request failures, selected pins and the
public-star identity change. Newer releases are a review queue, not accepted
upgrades. The dated star/source audits keep their original scope; newly discovered
repositories receive explicit source-only dispositions without implied installation.

The comparison is a current interpretation over retained research. In particular,
the current Nautilus destination takes precedence over historical LEAN-default
cards; LEAN's actual comparison results remain useful. Source-only DVC/Pandera
cards do not become installed data-pipeline acceptance. Earlier failed HUD
attempts remain recorded alongside later actual rendering observations.

See [foundation notes](../../docs/landscape-foundation-notes.md),
[domain notes](../../docs/landscape-domain-notes.md) and
[freshness notes](../../docs/landscape-freshness-notes.md), and
[selected native skill practice](../../docs/native-skill-practice-20260921.md) for the reasoning and
limits behind the reconciliation.

## Another PC

Use the [adoption guide](../../adoption/README.md), starting with the selected
profile. The documented baseline targets Linux/WSL2 x86_64. Clean userspace and
hosted Linux receipts cover named subsets; native sign-in, tool discovery,
scoped integrations, representative work and selected service/recovery behavior
must be verified on the destination host. This static page certifies no machine.

## Maintain the records

Update the affected layer and its sources when a requirement or measured result
changes. Keep failures and historical pins. Register new candidate arrays through
the existing `scripts/catalog_decisions.py --write --supplement` interface;
inclusion adds a source reference, not an adoption decision. Then run:

```sh
python3 scripts/landscape.py
python3 scripts/catalog_decisions.py --check
python3 tools/sota-convergence/build_verdicts.py --write
python3 tools/sota-convergence/build_verdicts.py --check
python3 scripts/build_ecosystem.py --write
python3 scripts/build_ecosystem.py --check
```

The landscape checker verifies complete layer coverage, required comparisons,
safe existing source references and canonical repository identities. It rejects
source screening mislabeled as an observed execution failure. It does not prove
the truth of narrative claims; independent source review remains necessary.
The HTML embeds all comparison data without background network calls, hashes its
inputs and derives displayed counts from the current records.
