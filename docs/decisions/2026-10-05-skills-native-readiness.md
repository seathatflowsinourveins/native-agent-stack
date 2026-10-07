# Native skills readiness evidence — 2026-10-05

Status: jobs 1–3 and fresh native authoring evidence recorded, including
failed upstream checks, synthetic assertion failures and interrupted analysis.
Lane: foundation. This decision serves the native skills foundation used by
complex-system work and north-star research workers. It changes no selection,
installation or client configuration.

## Decision and primary sources

Retain the native test failures at the reviewed pins. Passing subsets establish
their checked properties; they do not establish whole-slot readiness.

At [Trail of Bits 82fe8226](https://github.com/trailofbits/skills/blob/82fe8226252622fa807643bdca1710901198553a/.github/workflows/validate.yml#L31),
the unchanged metadata self-test passes 113 assertions, the frontmatter check
covers 85 skills, and metadata and Codex loadability checks pass. Its CI selects
latest Claude. The observed 2.1.289 CLI rejects
`claude-in-chrome-troubleshooting` during strict marketplace validation, before
installation. Retain that incompatibility without changing the upstream name
or downgrading the native client.

At [Skills CLI 7407f389 / v1.7.0](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/.github/workflows/ci.yml#L35),
the native frozen install, build, format and type-check pass. The first suite
run fails on a missing nested `pnpm` PATH entry and a missing `GitCloneError`
mock export. Supported Corepack enablement repairs the demonstrated PATH
issue. The unchanged rerun still fails one of 875 tests, with 874 passes and
zero skips. The observed failure is the missing mock export at
[private-repo-add-security.test.ts:45](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/tests/private-repo-add-security.test.ts#L45),
reported when
[add.ts:2317](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/add.ts#L2317)
checks that class. The failure does not establish the cause of the exception
that reached this catch block or a security vulnerability.

At [mattpocock/skills d81f3a18](https://github.com/mattpocock/skills/blob/d81f3a183412e71a5b1e84ca21bc1a35eea03a60/package.json#L11),
the checked package scripts, release-only workflow and tracked source tree
provide no runnable behavioral suite. The version metadata checker remains
available. Record this bounded unavailability under
[acceptance policy lines 37–38](../acceptance-evidence-policy.md#identify-what-each-check-proves)
without substituting an easier demonstration. The README install command is
at line 52; line 55 describes chooser/setup guidance.

The source and actual returned output are retained in
[skills-readiness-20261005](../../evidence/artifacts/skills-readiness-20261005/README.md).
The raw hashes and declared public sanitizations remain separate from success
claims. Source clean-state observations corroborate that upstream tests and
locks were unchanged. Other operating systems and Node matrix legs were not
run.

## Alternatives and overturn conditions

We compared retaining the native failures with locally patching tests or plugin
metadata, bypassing strict validation, or changing client versions to obtain a
pass. Retention follows the user's upstream-first rule and preserves the
upstream requirement. A maintained upstream fix at a reviewed pin followed by
the same unchanged native suite/loadability checks would overturn the current
failure disposition. The command center owns any remaining readiness-criterion
interpretation; no slot is promoted here.

The fresh authoring check uses the existing pinned
[Anthropic creator](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/SKILL.md#L163)
and the byte-identical official
[Codex rust-v0.160.0 creator](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/skills/src/assets/samples/skill-creator/SKILL.md).
Its fictional Cedar format checks the pipeline,
with three paired Claude cases and a separate Codex creation/validation leg.
Both Claude arms receive the same contract. Invalid structural input and an
intentionally wrong answer must fail their native checks. Its score cannot
select a landscape survivor or establish production skill quality. Candidate
qualification still requires source review, paired task comparisons, PR review
and lifecycle-only installation.

The fresh Codex session read the exact built-in creator, used its native
initializer and created the fixture in non-git scratch. The unchanged quick
validator returned 0 for the valid fixture and 1 for the invalid-name control.
Both actual native command completions and resulting artifacts were inspected.
The initial missing profile environment variable was repaired using the
repository's documented inert keyless-loopback placeholder and model-effort
qualifier, preserving the failed attempt and frozen inputs. Native turn usage
is retained once, with cached and reasoning subsets separate from totals;
provider billing and actual served model/effort are not inferred.

Claude's initial native process exited 1 before creation, with `is_error: true`
despite the result's `success` subtype. After the reported 11:30Z reset, the
same frozen input produced six paired executor runs. Exact preserved child
transcripts record `claude-opus-5-5` and `effort: max`, match their native
originals and contain no oracle-file reads. Both arms received the same case
and contract; only the with-skill arms read the created skill. Native timing
files match the completion notifications.

The unchanged graders report 13/15 passing assertions with the skill and
12/15 without it. Five outputs keep the full `Cedar C-…` label where the frozen
oracle expects `C-…`; the fixture wording is ambiguous. Preserve those failures
and draw no quality-uplift conclusion from this single-repetition sample.
Both structural controls behave as expected, and the separate wrong-answer
control fails its deliberately incorrect status and invented owner checks.
Unchanged aggregation and the static viewer exit 0 and include six actual
runs. Hardcoded repetition metadata, model placeholders and default tool/error
counters are recorded as defaults; actual native counters stay separate.
Native advisor results also differ between runs: cases 2 and 3 with the skill
contain rate-limit errors. Opaque advisor contributions remain unqualified.
This adds a runtime confound to the ambiguous, small comparison.

The later analyzer/critic workflow has no terminal results and its two child
transcripts end with interruption markers. A successful CLI exit does not
establish those stages completed. Retain the attempt and complete only the
missing analysis through sequential foreground native calls; see the separate
completion receipt. The historical grader workflow also lacks the repository's
required general-purpose dispatch annotation. Neither limitation is erased
from the execution record. Raw conversations and the private viewer remain
outside Git, with bounded outputs and hashes retained in the public receipt.

## Completeness critic and next gate

Keep isolated native loadability, actual model-side invocation and behavior
benchmarks distinct. Retain the unresolved Claude compatibility and Skills CLI
mock failure, unrun OS/Node matrix legs, and engineering suite unavailability
as lifecycle-sweep inputs. A future snapshot also needs upstream fixes,
current plugin naming rules and headless child-completion coverage. A future
fixture should explicitly delimit the asset identifier before any run; this
run's oracle and failures remain unchanged. The native paired outputs and
discriminating controls prove pipeline execution; aggregation placeholders
cannot prove execution or usage. MinerU registration and the Dagu skill
disposition remain gated on #719's owner/merge dependency. The twelve reopened
lifecycle tasks still await the co-op's bounded follow-up sweep packages.
