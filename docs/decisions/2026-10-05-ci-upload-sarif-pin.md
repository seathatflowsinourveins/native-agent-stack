---
status: proposed
date: 2026-10-05
decision-makers: [GitHub estate campaign command center]
consulted: [github-ci-finalize source readers, GPT Astra repair judgment]
informed: [ns2604-coop coordination record]
review_by: 2026-10-12
evidence_class: source_review
overturn_when: Source or tag identity differs, the upload interface changes, or required checks fail at the submitted head.
---

# Pin existing SARIF uploads to official CodeQL action v4.38.2

The four existing SARIF uploads use official v4.38.1. Campaign r2 A8/R4 assigns their replacement for Dependabot #690; the command center owns subsequent landing and C02 owns closing the bot PR.

Keep the existing workflows, inputs, permissions and guards, and update only the four full commit pins to `2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2` (`v4.38.2`). Keeping v4.38.1 is the alternative. The official September 24 release updates its default CodeQL bundle to 2.27.1, while both pins expose the identical upload action descriptor. No additional reporting runtime is needed.

Primary sources: [official release](https://github.com/github/codeql-action/releases/tag/v4.38.2), [github/codeql-action@2892aa5e:upload-sarif/action.yml:43](https://github.com/github/codeql-action/blob/2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2/upload-sarif/action.yml#L43), and [MADR4.0.0 template metadata](https://github.com/adr/madr/blob/2475fe1973f66a12aaf58a91d8fa7b42c0f5ea3d/template/adr-template.md#L2). Mandatory metadata and review/overturn fields follow the campaign's new-record policy; upstream MADR makes metadata optional.

The [sanitized receipt](../../evidence/artifacts/github-ci-r4-20261005.json) retains native SDK request/usage snapshots, both failed conditions, source identity and returned local check output. The original public source reads and vendor CI census are source review: 223 successes and 3 skips at the upstream pin, kept distinct. The local workflow linter and 39 repository contract tests pass as integration checks. They do not establish hosted seven-check acceptance or upstream-native test execution.

This remains proposed while the draft awaits the command center's Claude read. Observe the seven required checks at the submitted head and later at the landed head. Revisit the choice if the pinned source/tag differs, the supported SARIF interface changes, or a required check fails; identify the failure's owner before changing scope. Review by October 12. No repository settings or bot-PR state change follows from this record.

PR gates do not exercise the four uploads: Scorecard has no PR trigger; OSV/zizmor uploads exclude PR events. Actual SARIF upload execution remains unobserved until an applicable push, schedule or dispatch run. This record requests no scan rerun.
