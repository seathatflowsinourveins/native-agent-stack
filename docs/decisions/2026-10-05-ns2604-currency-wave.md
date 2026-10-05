# NativeStack2604 currency wave (2026-10-05)

Status: six scoped destination installs and defined acceptance stages passed;
repository validation passed; ready for command-center review.

North-star action: keep the native research harness current and qualified for
US-equities research and historical simulation before broker paper acceptance.
This work starts from `4c897418fe35a030a1188ae447eaf31c893f8eff` and serves only
the foundation lane. The command center reviews and lands the PR.

## Scope and source contract

The user's 2026-10-05 currency brief authorizes scoped installation and every
defined acceptance stage on NativeStack2604. Releases must be at least 24 hours
old and have no unresolved release regression. Historical receipts do not
certify this host. An existing qualification hold remains a hold until its
required evidence exists.

Maintained source inputs are the install plan, owner metadata, installation and
acceptance recipes, adoption pins and canonical stack records. The plan checker
checks agreement among those inputs. Derived handbook, component matrix and
grand-list outputs use their repository generators; generated files are not
hand-edited. Source and qualification evidence remain separate, following
`docs/acceptance-evidence-policy.md` and the host-pin requirement in
`docs/decisions/2026-10-04-2604-e2e-fix-wave.md#coordinator-follow-up-2026-10-04`.

## Release decisions

| Owner | Destination baseline | Candidate | Review result and primary source |
| --- | --- | --- | --- |
| jCodeMunch | 1.108.319 | 1.108.327 | Qualified scoped installation and unchanged full upstream harness. [Release](https://github.com/jgravelle/jcodemunch-mcp/releases/tag/v1.108.327) fixes unsafe local embedding-model paths; 1.108.328, published 2026-10-04T14:25:17Z, is held below 24 hours. |
| Headroom | 0.37.0 | 0.39.1 | Hold: open Windows scheduled-task regression [#3969](https://github.com/headroomlabs-ai/headroom/issues/3969). Stdio MCP route applicability does not waive the user's release-regression rule. |
| SocratiCode | 1.15.0 | 1.16.0 | Source-eligible suggestion; hold pin move pending healthy target-host retrieval/client qualification. Earlier 1.16 upstream tests are dated other-host evidence; current backend listeners are absent. The interim confirmatory remains open under `docs/decisions/2026-10-04-token-full-stack-owner-default.md:129-140`. The old workstation freeze is superseded by `2026-10-01-definitive-sota-wsl-program.md:12,29-30`; it is not this hold's authority. |
| AgentsView | 0.43.0 | 0.44.0 | Hold: `evidence/artifacts/agentsview-044-qualification-20260927/qualification.json` retains unmet native-lane, runner, review and usage-parity gates. |
| Inspect AI | 0.3.273 | 0.3.276 | Hold pending resolution of the open retry/sample-selection report [#5659](https://github.com/UKGovernmentBEIS/inspect_ai/issues/5659). The reported defect also appears in baseline source; this wave does not call the candidate unconditionally clean. GitHub's releases endpoint returned no release objects; publication evidence comes from PyPI and the tagged changelog. |
| mise | 2026.10.0 | 2026.10.1 | Qualified native doctor and binary digest: [release](https://github.com/jdx/mise/releases/tag/v2026.10.1). Newer [2026.10.2](https://github.com/jdx/mise/releases/tag/v2026.10.2), published Oct 4 12:31:22Z, stays below 24 hours until Oct 5 12:31:22Z. |
| Dagu | 2.18.1 | 2.18.2 | Qualified native service/CLI fixture operations: [release](https://github.com/dagucloud/dagu/releases/tag/v2.18.2). The host stack baseline was separately 2.16.6. |
| sandbox-runtime | Plan 0.0.78; stack 0.0.77 | 0.0.78 | Qualified Linux smoke and native Claude policy controls: [release](https://github.com/anthropics/sandbox-runtime/releases/tag/v0.0.78). Interactive resize report #642 has the same relevant launcher behavior at both pins; a new regression was not established. Windows, interactive resize and Codex route remain unqualified. |
| Worktrunk | Plan 0.80.0; stack 0.79.0 | 0.80.0 | Qualified native operations, dirty-removal control and fresh Claude/Codex tool events: [release](https://github.com/max-sixty/worktrunk/releases/tag/v0.80.0). |
| Syft | Plan 1.54.0; stack 1.52.0 | 1.54.0 | Qualified native Alpine inventory and empty-SBOM control: [release](https://github.com/anchore/syft/releases/tag/v1.54.0). |
| Collector Contrib | Plan 0.162.0; stack 0.161.0 | 0.162.0 | Hold stack move: release-tag [build-and-test run](https://github.com/open-telemetry/opentelemetry-collector-contrib/actions/runs/36550319609) failed. Existing destination plan is not promoted to qualified by metadata. |
| Grafana | Plan 13.2.3; stack 13.2.2 | 13.2.3 | Hold stack move pending regression disposition. [#133856](https://github.com/grafana/grafana/issues/133856) affects the 13.2 series, while [#133835](https://github.com/grafana/grafana/issues/133835) reports APT/RPM publication. A destination rollback to 13.2.2 would lose [security fixes](https://grafana.com/security/security-advisories/cve-2026-13719/) without resolving the reported series regression. |
| Ollama | 0.35.0 | 0.35.1 | Completeness lead: [release](https://github.com/ollama/ollama/releases/tag/v0.35.1). Hold pending runtime/model qualification; `2026-10-03-new-wsl-local-models.md:249-253` binds the measured model-install gate to server 0.35.0. |
| OpenHands worker | 1.50.1 | 1.51.0 | Completeness lead: [release](https://github.com/OpenHands/software-agent-sdk/releases/tag/v1.51.0). Hold pending the comparison and declared amendment in `2026-10-04-2604-e2e-fix-wave-g2-mcp-workers.md:60-63,102-107`. |
| Selected mattpocock skills | Displayed bundle 1.2.3; immutable selected skill trees | 1.3.1 | [Release](https://github.com/mattpocock/skills/releases/tag/v1.3.1) published Oct 4 12:48:18Z remains below 24 hours until Oct 5 12:48:18Z. The installed selections in `adoption/skills/manifest.json` need a skill lifecycle comparison, not a bundle-wide replacement. |

## Evidence and alternatives

Release notes, advisory records, issue/source comparisons and downloaded artifact
digests are source review and integrity evidence. The baseline plan checker and
validator passed; they establish structural consistency. Native installation,
unchanged upstream tests, native operations and local integration checks are
recorded separately in [the qualification receipt](../../evidence/receipts/ns2604-currency-qualification-20261005.json),
with failed attempts retained. All three plan stage selectors ran with stdin
closed; undefined stages are skipped, not passed. Five stack owners carry the
same qualification reference in their saturation rows; mise is a prerequisite
without a stack/saturation component.

Only jCodeMunch ran an unchanged complete upstream harness: 14,210 passed,
28 skipped, 83% coverage. Dagu uses unchanged upstream fixtures and native CLI
operations with local assertions; no Go suite or retry/crash recovery was run.
Worktrunk and SRT use native model event assertions and synthetic fixtures;
their upstream Rust/Bun suites were not run. Syft is a native example with a
synthetic negative control; mise is native doctor plus binary read-back.

The Worktrunk argument repair follows installed `claude --help` and the
[official CLI reference](https://code.claude.com/docs/en/cli-reference).
Its first prompt was consumed by variadic `--allowedTools`; the next native
run reached a six-turn limit. The twelve-turn retry passed. Codex executes
from a non-Git owned directory with `--skip-git-repo-check`, per the user's
trust-entry boundary and [0.160.0 source](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/exec/src/cli.rs#L33).
The earlier four-turn SRT failure is unclassified because its old trap removed
the stream; its twelve-turn retry passed, without claiming a causal diagnosis.
Failed SRT streams are now retained. No account, permission, model or effort
configuration was changed.

Independent read-back observed mise drift from 2026.10.1 to 2026.10.0; after
reapplication, native doctor and the exact binary digest passed. The cause is
unconfirmed. Host observations are dated, not a guarantee against other writers.
Final recipe hashes bind the qualification to this branch's bytes; the native
collector's base revision alone does not identify uncommitted edits.

A second independent read-back at 05:05Z again found the official 2026.10.0
binary. One final authorized reapplication passed install/doctor and immediate
version/digest read-back at 05:07:28Z, retained in
`evidence/artifacts/ns2604-currency-20261005/mise-final-observation.json`.
Durable shared-host state needs coordinator serialization; no other lane's
files were edited. Mise's four original collector outputs remain byte-identical
prerequisite artifacts: the catalog host validator cannot enroll its uncatalogued
ID. This limitation is separate from the actual native command outcomes.

The unchanged manifest assembler consumes the consensus source row, and the
unchanged table renderer projects its current default beside the original
owner-decision date. The October 1 record's non-generated currency note preserves
the initial October 4 pin 1.108.319 and the October 5 qualified pin 1.108.327.
No family vote or historical authority date was changed. Generated defaults,
tables, handbook, matrix and grand list use their native generators.

Validation: `check_plan.py`, `scripts/validate.py`, `host_receipts.py validate`,
`build_ecosystem.py --check` and `git diff --check` passed. The initial affected
suite ran 538 tests with five failures and four skips; a scoped 271-test rerun
cleared the source/generator failures, leaving one stale inventory count. Its
final isolated receipt test passed after that metadata correction. Passing
unaffected suites were reused; these local checks are not upstream acceptance.

Alternatives are keeping the current pin, moving to the latest eligible clean
release, or holding a newer release until its age, regression or qualification
gate clears. An upstream regression or failed destination operation overturns a
proposed move. A fixed release plus the outstanding qualification evidence
reopens a hold. The Windows-only Headroom route is a separate future comparison,
not a reason to ignore the current explicit release rule.

## Completeness critic

Read-only release, source-mirror and final evidence critics completed. The
installed-owner intersection covered 53 pinned installed plan rows; it did not
treat 90 stale catalog entries as authorization to install alternatives. The
summary missed Ollama, OpenHands and selected-skill release leads present in its
retained primary metadata. Those holds are now explicit. ai-memory 2.5.2 is
already the destination interim, while stack 2.4.1 is separately qualified
historical evidence; OmniRoute's composed 3.8.52 canary retains its qualification
and 3.8.51 stable rollback. Neither is a metadata-only upgrade.

The CLI variant sweep found the same positional-prompt defect in the unchanged
Difftastic after_sign_in row (`accept.sh:1481`); it remains a follow-up outside
this currency wave. SRT is not that variant because `--max-turns` terminates the
variadic tools option before the prompt. No additional affected runnable call
was found in the bounded repository sweep.

Next lifecycle sweep: runtime/model and worker comparison gates; selected-skill
refresh; aging releases; registry publication without GitHub release objects;
platform-specific regressions; full-history checkout prerequisites; retained
failure streams; host drift; release-tag CI; transitive advisory coverage and
signed provenance; and security fixes whose rollback leaves a series defect.
Scoped ai-memory returned unrelated observability sessions and supplied no
currency authority. A patch-generation mistake appended fields outside the
architecture JSON; this lane's edit was restored, reapplied with context and
parsed successfully before validation. The current defaults were then regenerated
from their source rather than maintained as hand-edited output. The earlier
SocratiCode freeze claim was corrected against the October 1 decision and current
target-host gates. Final source/receipt critic found no remaining material blocker
after the explicit projection note; shared-host mise serialization remains open.
