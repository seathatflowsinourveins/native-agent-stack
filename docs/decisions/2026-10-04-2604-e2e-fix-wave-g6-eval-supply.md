# NativeStack2604 E2E plan fixes: evaluation, usage and supply inventory

Date: 2026-10-04. Bounded builder: `fix-wave-g6-eval-supply`, GPT Sol at max.
Base: PR #684's token-layer head. This unit serves the foundation's north-star
action: qualify real gateway regressions, observe native usage and inventory
SDK dependencies before the
US-equities research, historical simulation and independently qualified paper
lanes use the stack. No distribution was launched, installed into or tested.

## Authority and original evidence

The supplied job selects `quality-evaluation/promptfoo`,
`token-efficiency/ccusage` and `ci-supply-chain/syft` as FINAL slots and limits
edits to their plan rows and allowed pins. Original inputs were read from
`review-observe-eval-2.json`, `review-context-3.json`, `review-delivery-1.json`,
their executor JSON files and `units.json` in the provided coordination directory.
`adjudication.json` has no entry for any of these three slots. The named
`fixes.json` was absent; the slot-specific reviews and original executor records
supplied the defects. The older install-repair patch and its report have no hunk
for any owned slot, so no unrelated repair was ported.

The installed clients/tools were checked first: ccusage 20.0.26 has both
`claude daily` and `codex daily`; Promptfoo 0.123.1 has `mcp --transport stdio`;
Codex 0.159.3 and Claude Code 2.1.289 expose their native `mcp add` commands.
Tagged release/changelog identities were then checked with `gh api`, followed
by original tagged sources and official documentation. The ai-memory read was
unavailable under this job's approval policy; no approval bypass was attempted.
The fetched OpenAI MCP page and tagged source supplied the Codex evidence.
The web search/open interface failed; direct primary-source HTTPS retrieval
succeeded. Claude's official documentation URL returned 403 here; its installed
`mcp add --help` verified the registration syntax.

The diagnosis is bounded artifact reconciliation: the live-host reproduction
already exists in the executor evidence and this job forbids a distribution run.
No new live-host reproduction or speculative repair loop was substituted.

## Promptfoo 0.123.1

Install the verified npm release in its owned ecosystem prefix and include
optional dependencies, because the upstream MCP SDK is optional. Register
`promptfoo mcp --transport stdio` with Claude Code's user scope and Codex's native
MCP command. Forward only the name `GATEWAY_API_KEY` through Codex `env_vars`;
reuse the existing repository's preserving TOML merge and atomic writer.

The positive and failing upstream smoke fixtures are copied unchanged from
`promptfoo/promptfoo@34f74d34e140b5e17d23770dfb2340057b1936b8`:
`test/smoke/fixtures/configs/basic.yaml:1` and
`test/smoke/fixtures/configs/failing-assertion.yaml:1`. Run them with the pinned
CLI's native `eval --no-cache`, inspect returned JSON, and require the negative
control's exit 100. This is an integration observation using upstream fixtures,
not execution of the unchanged Vitest suite and not a model-route qualification.

The real acceptance stage adopts
`examples/openai-compatible-gateway/promptfooconfig.yaml:1-24` and its
`README.md:15-27`, parameterizing it for the existing loopback gateway and two
distinct GPT/Claude routes. The owner must fill the exact served model IDs and,
if different, `apiBaseUrl`, and expose the existing credential through
`GATEWAY_API_KEY`. No credential value is read, displayed or copied by this
repair. Fresh native client sign-ins remain native prerequisites.

After that setup, `after_sign_in` runs an uncached two-provider CLI evaluation
and requires both fresh clients to invoke the upstream `run_evaluation` tool
with caching and sharing disabled. Native tool-call/result events, returned
statistics, two distinct OpenAI-compatible provider IDs and successful
assertions are required. Agent prose and an exit 0 by itself do not pass.
Session observations stay in private user configuration state.

Correction to the review's registration recipe: `codex mcp add` alone does not
forward arbitrary credential variables. Verified at
`openai/codex@rust-v0.159.3:codex-rs/rmcp-client/src/utils.rs:16-26` and the
[official MCP documentation](https://developers.openai.com/codex/mcp).
The added name-only allowlist is native configuration, not secret persistence.

The coordinator's `owners.json` and definitive manifest still record the
historical exclusion. `check_plan.py` applies an exact Promptfoo-only override
carried by `plan_fix`; it requires this job, this decision, the named owner,
repository, release and both stages. Other rows retain their canonical checks.
The coordinator must reconcile those generated inventories when integrating.

Sources:

- [Installation, line 19](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/site/docs/installation.md#L19).
- [MCP prerequisites and STDIO command, lines 13-35](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/site/docs/integrations/mcp-server.md#L13).
- [Upstream eval smoke, lines 65-88](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/test/smoke/eval.test.ts#L65).
- [MCP result and native options, line 103](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/commands/mcp/tools/runEvaluation.ts#L103).
- [MCP response envelope, lines 11-38](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/commands/mcp/lib/utils.ts#L11).
- `native-agent-stack@PR #684's head:tools/adoption/new_wsl_client_config.py:1623,1735,2343` and `tools/adoption/apply_codex_lane.py:271` (reused preserving merge and compare-and-swap writer).
- [Claude MCP registration](https://code.claude.com/docs/en/mcp), verified with installed `claude mcp add --help`.
- [Codex native result fields, line 263](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/exec/src/exec_events.rs#L263).

## ccusage 20.0.26

PR #684 already supplies the verified tarball, native-build dependency and
owned-prefix npm install. Keep both install commands and the pin unchanged.
Its version-only post-install check was the missing functional acceptance.

The new check runs the documented Claude/Codex daily reports against unchanged
upstream log fixtures in a temporary scoped home, offline and with costs hidden.
It asserts 1,240 Claude tokens and 4,200 Codex tokens, their input/output/cache
subsets and the absence of costs. Cache-read subsets are not added again.
These are upstream fixture bytes exercised by the installed CLI, not a new
model run or execution of the Rust source suite.

The CLI meter needs no MCP registration or hook. Its ecosystem executable is
invoked by absolute path from both native clients. `after_sign_in` requires fresh
Claude/Codex sessions to invoke the meter, successful native shell events and
non-empty current-day finalized reports from both sources. Existing native
client sign-ins are needed on a clean host; no new provider credential is needed
by ccusage. Native finalized accounting remains authoritative.

Sources: `ccusage/ccusage@d9821088b98aa536c7a385aa1a4579d6fa02269b`:

- [Global install and verification](https://github.com/ccusage/ccusage/blob/d9821088b98aa536c7a385aa1a4579d6fa02269b/docs/guide/installation.md#L58), verification at line 133.
- [Native Claude/Codex commands, lines 65-67](https://github.com/ccusage/ccusage/blob/d9821088b98aa536c7a385aa1a4579d6fa02269b/apps/ccusage/README.md#L65).
- `apps/ccusage/test/fixtures/claude/projects/project-alpha/session-alpha/chat.jsonl:1`, `project-beta/session-beta/chat.jsonl:1`, and `apps/ccusage/test/fixtures/codex/sessions/project-alpha/session-alpha.jsonl:1`.
- [Native scoped CLI fixture pattern, line 63](https://github.com/ccusage/ccusage/blob/d9821088b98aa536c7a385aa1a4579d6fa02269b/rust/crates/ccusage/tests/claude_cli.rs#L63), and [Codex test, line 130](https://github.com/ccusage/ccusage/blob/d9821088b98aa536c7a385aa1a4579d6fa02269b/rust/crates/ccusage/tests/codex_cli.rs#L130).
- [Codex shell execution result, line 161](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/exec/src/exec_events.rs#L161).

## Syft 1.54.0

Keep the plan's working `mise use -g syft@1.54.0`. Move only the allowed stack,
new-WSL profile and foundation architecture pin to that release and source
commit `cc326e45a6213360266dda4b30cc68095946d676`. The Linux archive's upstream
SHA256 is `54a87372498168b2d033e876fd41fa4e8035b872699e525a57046e1f2f09c860`.
The profile now names the supported user install and documented image scan.

Keep upstream's `syft alpine:latest` acceptance, checking the returned Syft JSON
contains an image inventory and `alpine-baselayout`. Check the exact executable
release/source separately. This CLI has no MCP/hook requirement and the slot
defines no fresh-session gate. No model account, identity or privacy decision
is needed. The public image is mutable, as the plan already records.

The trading catalog's historical 1.52.0 selection and receipts remain historical.
The three workflows named by the review (`supply-chain.yml`,
`publish-catalog.yml`, `catalog-freshness.yml`) and coordinator unit metadata
are outside this builder's allowed paths and still need their 1.52.0 references
reconciled by their owners. Do not describe that remaining integration gap as
fixed by this plan/pin patch.

Sources:

- [Syft README, line 48](https://github.com/anchore/syft/blob/cc326e45a6213360266dda4b30cc68095946d676/README.md#L48).
- [mise registry at v2026.10.0, line 1](https://github.com/jdx/mise/blob/v2026.10.0/registry/syft.toml#L1).
- [v1.54.0 checksums](https://github.com/anchore/syft/releases/download/v1.54.0/syft_1.54.0_checksums.txt).
- [v1.54.0 release](https://github.com/anchore/syft/releases/tag/v1.54.0), published 2026-10-01T20:54:29Z; live `releases/latest` returned this release on 2026-10-04.

## Alternatives and completeness critic

Keeping Promptfoo excluded conflicts with the wave-4 owner default (the owner's
repository-quality rule) and leaves
gateway/LLM A/B without its selected native harness. A version check cannot
replace returned evaluator results. Replacing the native MCP server with a
custom bridge would add an unnecessary implementation. Reinstalling ccusage
would duplicate PR #684; its gap is acceptance and fresh use. Downgrading Syft
to 1.52.0 would align historical references but discard the already working
clean-install release and its maintained fixes. Changing the workflow pins here
would exceed file ownership.

This bounded completeness critic covered CLI presence, provider evaluation,
STDIO wiring in both clients, optional MCP runtime dependencies, gateway
credential forwarding by name, native usage formats, cache subsets, fresh
native invocation, SBOM content, historical records and generated inventories.
No tool/plugin modality or account setup was treated as passed by help/version
output. The next landscape/integration sweep must include the remaining Syft
workflow pins, regenerated Promptfoo inventories and independent live-host
observation of both tools' `after_sign_in` stages. No child agent or cross-family
lane was launched by this bounded builder.

Overturn this choice if a pinned native source removes either named ccusage
source, the tagged Promptfoo MCP cannot return successful uncached evaluations
through both clients, or the selected Syft release fails its upstream scan on a
clean host. That comparison must use the existing upstream executables and
actual returned receipts, with native-session observation kept separate from
source tests and fixtures.

## Bounded acceptance

Local Linux observations, separate from destination WSL acceptance: installed
ccusage 20.0.26 returned the expected unchanged-fixture totals; installed
Promptfoo 0.123.1 passed the upstream positive fixture and returned 100 with one
assertion failure for its negative control; the downloaded verified Syft 1.54.0
binary returned its pinned source identity and successfully scanned Alpine into
a non-empty SBOM. No live provider evaluation or fresh model session was run
by this job. Required repository-check results are recorded in the handoff.

All repository acceptance commands used
`TMPDIR=.bounded-fix-wave-g6-eval-supply/tmp`, outside `/tmp` in the owned
checkout. `check_plan.py` returned 0: 80 rows, 57 installed (55 default and two
named-only), three measurement-only, 20 excluded, 122 commands and 81 acceptance
entries. Both scripts passed `bash -n`; the generated handbook passed `--check`;
`git diff --check` returned 0. `scripts/validate.py` returned 1 with only registry
hash/byte drift and the nine new config files awaiting hash registration. The
coordinator owns `manifests/evidence.json` and the shared inventory counts.

The exact requested four-module unittest command ran 324 tests and returned 1:
86 failures and 12 errors. An independent clean checkout of PR #684's head ran
the same 324 tests with the same relative TMPDIR and returned 1: 84 failures and
12 errors. Every baseline failure/error identity reproduced in the owned tree.
The inherited stale `adoption/new-wsl/codex-user-instructions.md` accounts for
83 client-config failures and 12 errors; the inherited RTK 0.50.0 definitive
owner versus stack 0.51.0 accounts for the remaining baseline failure. Those
unowned files were retained.

The two additional failures are disclosed integration gaps, not inherited:
`ManifestRuleTests.test_the_rule_selects_the_rows_the_plan_installs_and_the_two_on_demand_rows`
still sees the historical Promptfoo exclusion and its fixed 56-row expectation;
`NewWslProfileCliTests.test_existing_public_generator_preserves_the_native_profile_pointer`
rejects the stale Syft source pin in the freshness snapshot. Updating that
snapshot, the definitive inventory and the test's shared row count exceeds this
builder's allowed files. The freshness equality gate is verified at
`native-agent-stack@PR #684's head:scripts/landscape.py:1365,1373-1378`.

Correction retained from the initial acceptance: the Syft profile first used
the architecture's acceptance class, which the profile schema does not accept.
It now uses `documented_upstream_example_not_executed`; the final suite passes
the profile schema checks, with only the separate freshness failure above.
No failing check is represented as passed, and neither `after_sign_in` stage
is claimed as a real provider or fresh-session acceptance.

> **Coordinator note, 2026-10-05.** Two statements above are superseded. "The supplied job selects ... as FINAL slots" was the builder's reading of the coordinator's brief, not an owner decision; the Promptfoo row's authority is the wave-4 owner default on the owner's repository-quality rule (docs/decisions/2026-10-04-2604-e2e-fix-wave.md). The checker no longer applies a plan_fix override (job-058 removed it), and owners.json and the manifest both carry Promptfoo.

> **Coordinator note (2026-10-05).** The host stack pin move named here was withdrawn from PR #704 before landing: `manifests/stack.json` keeps its receipted pin until the currency PR moves it with a qualification receipt. See "Host stack pins withdrawn from this PR" in `docs/decisions/2026-10-04-2604-e2e-fix-wave.md`.
