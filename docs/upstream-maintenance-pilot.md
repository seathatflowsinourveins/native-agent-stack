# Bounded upstream maintenance pilot

Decision on 2026-09-20: the existing **Maintain native foundation and trading
catalogs** Codex task remains the sole agentic maintainer. Its active daily 09:00
America/New_York schedule already covers changed-source research, both catalogs,
acceptance, rollback and quiet operation unless actionable. This pilot is a manual
read-only research result under that ownership, not another scheduled writer.

## One material finding: Nautilus catalog migration and interval safety

The accepted NautilusTrader source remains `v2.0.0rc5`,
`1b0a49d2792a9432a3aca3fcb617ce7a630d905e`. Two later primary-source changes
justify a focused proposal before a future historical-catalog upgrade:

- [Parquet/Arrow rewrite a2032f9, September 17](https://github.com/nautechsystems/nautilus_trader/commit/a2032f9f4f7f6adb4c2eb9902ae1b04b2c11dc29)
  changes encoding, rejects legacy runtime schemas and provides migration to a
  separate destination.
- [Interval safety 1750eb7, September 19](https://github.com/nautechsystems/nautilus_trader/commit/1750eb7a7676d199569679947e800bf30d05f5e3)
  validates proposed filename intervals before renaming, rejects overlapping or
  reversed bounds and adds checked arithmetic and recovery regressions.

Separate source inspection found existing-interval validation at
[store.rs lines 117–119](https://github.com/nautechsystems/nautilus_trader/blob/1750eb7a7676d199569679947e800bf30d05f5e3/crates/persistence/src/backend/parquet/catalog/store.rs#L117),
proposed-interval validation at lines 141–145, then rename at line 148. The pinned
[integration tests](https://github.com/nautechsystems/nautilus_trader/blob/1750eb7a7676d199569679947e800bf30d05f5e3/crates/persistence/tests/integration/test_catalog.rs)
add ten regression functions and nine file-snapshot equality assertions.
These observations support relevance; source inspection is not executed behavior.

Proposed update: retain this candidate and require migration plus
rejection-without-mutation acceptance before changing the accepted runtime. The
GitHub source comparison was **diverged**, with 103 commits ahead; this is not a
drop-in release bump. Neither change qualifies IBKR, the separate Alpaca adapter,
paper operation, broker orders or a strategy's historical usefulness.

In a separate upstream checkout pinned to
`1750eb7a7676d199569679947e800bf30d05f5e3`, the matching commands are:

```sh
cargo test --locked -p nautilus-persistence --test integration test_rust_extend
cargo test --locked -p nautilus-persistence --test integration test_rust_record_empty_coverage_validates_before_extending
cargo test --locked -p nautilus-persistence --test test_parquet_migration
```

These commands are **proposed, not run** here. Retain selected test names/counts,
failures and skips; zero matched tests is not acceptance. For owned fixture data,
the pinned [upstream migration guide](https://github.com/nautechsystems/nautilus_trader/blob/1750eb7a7676d199569679947e800bf30d05f5e3/docs/how_to/migrate_parquet_catalog.md)
documents `cargo run --locked -p nautilus-cli -- catalog migrate-parquet SOURCE DESTINATION --dry-run`
followed by the same command without `--dry-run`. Require unchanged source hashes,
expected decoded values and representative offline replay outcomes, not only row
counts. Keep original data with its compatible runtime for rollback: no reverse
migration is supported. The foundation/native runtime owner decides qualification;
this automation task did not install, migrate or change trading work.

## Measured result and retained failure

At `2026-09-20T22:02:36.464Z`, two native GitHub API reads took 0.723 seconds
and returned exit 0. Retrieved upstream test-source SHA-256:
`61e970ad289226c54872d867a05b4d9244da352b932301fbcfb2ca9bcccd5d38`.
An earlier large comparison read failed with Node `ENOBUFS`; a read-only retry
with a bounded 32 MiB buffer recovered it. The GitHub latest-release endpoint
returned legacy `v1.231.0`, while our accepted channel is `v2.0.0rc5`; a future
detector must inspect explicit tags/prereleases instead of blindly using latest.

Pilot usefulness: one source-backed, material, bounded proposal with relevant
acceptance commands and rollback. Independent source checks support the reported
interval ordering and regression coverage. Detection recall and false-positive
rate cannot be established by this one case. The 0.723 seconds measures retrieval
only. Complete agent elapsed time and provider usage were not isolated, and no
session/lifetime savings or runtime qualification are claimed.

## Maintained alternatives and selection

| Candidate / reviewed revision | Supported interface and decision |
| --- | --- |
| [GitHub gh-aw v0.88.7, bde3679](https://github.com/github/gh-aw/tree/bde367913adeb3132f0a171594c88a17f4b7d08c) | Supported Markdown-to-locked-workflow compiler and native engine interface. Defer hosted execution because an existing maintainer owns this task and no measured benefit justifies another engine/account. |
| [githubnext/agentics, 4bc8419](https://github.com/githubnext/agentics/tree/4bc8419fad05e6b032741cbfd189986700bcf71c) | Reuse its research/report pattern selectively. Pinned weekly-research source creates a Discussion while its prose says issue; it also requests all GitHub toolsets and `min-integrity: none`. Do not copy unchanged. |
| Dependabot configuration version 2, GitHub-managed service | Adopt weekly grouped Action updates in `.github/dependabot.yml`; no auto-merge, credential transfer or catalog-runtime adoption. There is no repository-controlled server commit to pin. |
| [Renovate 44.104.0, 6a1a69c](https://github.com/renovatebot/renovate/tree/6a1a69c3efdfb3dbb534b970f08b7f49524cec8b) | Its [JSONata manager](https://docs.renovatebot.com/modules/manager/jsonata/) fits structured custom pins. Defer until a separate candidate-pin manifest and exclusive ownership show reduced work. Accepted catalog pins bind to receipts and cannot be mechanically promoted. |

If a hosted agent becomes justified, the pinned [gh-aw CLI reference](https://github.com/github/gh-aw/blob/bde367913adeb3132f0a171594c88a17f4b7d08c/docs/src/content/docs/setup/cli.md)
supports `gh extension install github/gh-aw --pin v0.88.7`, `gh aw init`,
`gh aw add`, `gh aw compile --validate --strict`, `gh aw run`, `gh aw audit RUN_ID`
and `gh aw logs`. Review its maintained
[workflow-review skill](https://github.com/github/gh-aw/blob/bde367913adeb3132f0a171594c88a17f4b7d08c/.github/skills/review-agentic-workflows/SKILL.md).
The extension is not installed by this task. Generated `github/gh-aw-actions/*`
pins belong to `gh aw compile`/`gh aw update-actions`; exclude them from Dependabot
if this integration is adopted later.

The concrete alternative is manual dispatch, read-only access, a fixed source
allowlist and one report artifact, with no PR writer or recurring schedule.
Its new hosted-model spending boundary is **$0: disabled**. Before activation,
declare a provider budget and submission limit, then compare source-correct useful
reports, reliability, elapsed time and complete available usage against the
existing owner. A runtime timeout is not a monetary spending cap.

The [pinned authentication guide](https://github.com/github/gh-aw/blob/bde367913adeb3132f0a171594c88a17f4b7d08c/docs/src/content/docs/reference/auth.mdx)
and [cost FAQ](https://github.com/github/gh-aw/blob/bde367913adeb3132f0a171594c88a17f4b7d08c/docs/src/content/docs/reference/faq.md)
separate engine inference billing from free workflow software. Hosted Codex needs
its supported API credentials; hosted Claude uses supported API/workload identity,
not native subscription OAuth stores. No new account, key or subscription was
created. Rollback for this pilot is to withdraw the proposal; accepted pins and
the existing maintenance schedule remain intact.
