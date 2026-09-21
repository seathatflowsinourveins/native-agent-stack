# Current landscape: choices and alternatives

Open the [offline comparison view](../../docs/ecosystem/index.html#landscape) for
the requirement, current choice, named competitors, evidence and reopening
condition in **all 16 foundation layers and all four domain research layers**.
Download its combined JSON from the page, or start with [manifest.json](manifest.json).

The current comparison joins [foundation.json](foundation.json) and
[us-equities.json](us-equities.json). The existing 152 domain candidate cards
remain available in each corresponding layer with their original dates, pins,
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
python3 scripts/build_ecosystem.py --write
python3 scripts/build_ecosystem.py --check
```

The landscape checker verifies complete layer coverage, required comparisons,
safe existing source references and canonical repository identities. It rejects
source screening mislabeled as an observed execution failure. It does not prove
the truth of narrative claims; independent source review remains necessary.
The HTML embeds all comparison data without background network calls, hashes its
inputs and derives displayed counts from the current records.
