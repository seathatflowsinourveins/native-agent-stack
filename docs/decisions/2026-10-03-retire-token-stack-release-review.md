# Decision: retire PR #509, the token-stack release review, unmerged, and keep its unique facts (2026-10-03)

**Decided by:** Claude session `native-agent-stack-0c`, under its custody of PRs that have no
owner, after the two-hour objection window on [its #509 custody notice][notice] passed
without objection in the comments read on 2026-10-03. The notice was created at
2026-10-03T08:22:05Z; the window ended at 2026-10-03T10:22:05Z. This is the session's
custody decision, not a user decision. The coordinator must re-read #509's comments and
confirm its unchanged OPEN head immediately before merging this record; an objection or
ownership claim stops the retirement.

**Scope:** this record only, with its evidence-registry entry. No pin, script, setting,
carrier, install or new-WSL change. Lane: `lane:foundation`.

## Decision

Retire [#509](https://github.com/seathatflowsinourveins/native-agent-stack/pull/509),
"Token stack release review: upstream integration paths and pin sequencing (decision
record)", unmerged after this record lands. The Mac session `os-b4` opened it on
2026-09-29 at 15:30:15Z: head `f33dc2c90679e14b282291d63a11c25b73ff943a`, base
`df4123684fb55655b885a8dc6431a263c18b4c4c`, one added file, no reviews, with checks
passing on that old base (inapplicable jobs were skipped). Its head remained OPEN and
unchanged when read for this record.

Keep the [full original at the head permalink][original] and the
[author's handoff comment of 2026-09-29T15:30:33Z][handoff] reachable. Do not delete its
branch, `claude/token-stack-release-review-20260929`. Close it only after this record
merges, with a comment linking the merged record.

The north-star action served is preserving the token-stack source evidence for the
existing workstation qualifications that support complex projects, US-equities research
and historical simulation. This retirement performs no component qualification or
installation. The sibling #508, head `b7fcc219`, has its own ownership and outcome;
nothing here depends on that outcome. A 2026-10-02 Codex coordination note said
"PR508/509 ... remain owned" without naming the owner, which the notice explicitly
invited to claim custody.

## What superseded it

Repository citations below were read at main
`9b0b8d6d25f9e3fb8f71770500e774170423315e`. PR states are observations on 2026-10-03;
open PRs are proposals rather than main's accepted pins. In particular, #642's current
record holds mcporter, superseding the earlier description of W1 as a 0.14.2 move.

| #509 item | Record or PR that overtook it, with the source location |
| --- | --- |
| SocratiCode 1.16.0 qualification | [#523](https://github.com/seathatflowsinourveins/native-agent-stack/pull/523) merged 2026-09-30. [docs/decisions/2026-09-25-workstation-sota-refresh.md:437][socraticode-qualified] records qualification, with `evidence/receipts/socraticode-1160-qualification-20260929.json` at line 440; the Linux pin stays 1.15.0. This retires the unperformed qualification recommendation, not the separate cutover gate. |
| Codex version and Mac catch-up target | [#580](https://github.com/seathatflowsinourveins/native-agent-stack/pull/580) merged 2026-10-01 with Codex 0.159.3; [adoption/pins-linux-x86_64.json:53][linux-codex] and [tests/test_adoption_bootstrap_macos.py:264][lag-table] now record Linux 0.159.3 / Mac 0.155.1. [#626](https://github.com/seathatflowsinourveins/native-agent-stack/pull/626), OPEN at `75a2ada1`, proposes 0.160.0. #509's 0.157.1 Mac target and latest-release survey are dated. |
| mcporter and jcodemunch | [#642](https://github.com/seathatflowsinourveins/native-agent-stack/pull/642), OPEN at `1b9d0927`: [docs/decisions/2026-10-03-currency-wave-w1.md:26][w1-moves] selects jcodemunch 1.108.327, while [the same record:127][w1-mcporter] holds mcporter at 0.14.1 after a 0.14.2 compatibility attempt with dependency and persistent-role gaps. The Mac keeps 0.13.13 (lines 135–136); W1 does not qualify that Mac. |
| headroom | [docs/decisions/2026-10-01-definitive-sota-wsl-program.md:299][release-table] records 0.37.0 as "a deliberate hold". Main already qualified 0.39.0 and did not switch: [docs/decisions/2026-09-25-workstation-sota-refresh.md:519][headroom-qualified] reads "0.39.0 qualified, not switched (2026-09-25)", with the receipt [`evidence/receipts/headroom-039-qualification-20260925.json`][headroom-receipt] at line 523. Lines 524–545 keep 0.37.0 as the pin, first because "The omission notice counts the wrong lines." (line 526), and [lines 549–550][headroom-overturn] set the overturn condition: "upstream counts levels over the omitted lines only, or a measured answer-quality comparison on log inputs shows net value for 0.39.0's log routing". [catalogs/foundation/new-wsl-architecture-20261001.json:704][architecture-headroom], checked at 2026-10-01T07:41Z, records "0.39.0 was qualified but not switched, and 0.39.1 changes only the proxy rate limiter"; [evidence/artifacts/layer-closure-assessment-20261001/foundation.json:1421][closure-headroom] adds "so the omission-count hold stands". Neither is evidence of a new 0.39.1 host run. #642's [W1 record:148][w1-holds] says "Requalification is running separately". |
| RTK | #642's [W1 record:150][w1-holds] also says "Requalification is running separately". The existing Codex hold in [docs/decisions/2026-09-26-token-practice-f1-f9.md:60][rtk-hold] requires native unwrapping or `updatedInput` without `allow`, followed by qualification. |
| Integration paths in #509's step 4 | [evidence/artifacts/new-wsl-clean-install-selection-20261001/selection.json:237][selection-serena] records Serena's install command; lines [267][selection-socraticode], [318][selection-qmd] and [442][selection-rtk] cover SocratiCode, QMD and RTK. These are clean-install recommendations. [docs/token-efficiency-stack.json:2217][qmd-note] retains the standalone QMD registration for an already-wired stack; [the same file:2984][socraticode-note] and line 2989 describe MCP-only and plugin alternatives. None proves the Mac's present registration. Context Mode's dated Codex paths are kept below. |
| Latest-release survey | The dated assessor table in [docs/decisions/2026-10-01-definitive-sota-wsl-program.md:281][release-table] overtook the September 29 survey; its method is explicitly attributed to the October 1 assessors at lines 283–285. #580, #626 and #642 subsequently cover their named versions. No current upstream-wide survey is claimed here. |
| Mac catch-up rule | [tests/test_adoption_bootstrap_macos.py:259][lag-table] keeps `MAC_PIN_LAGS_LINUX`, with version pairs and Linux qualification receipts for ai-memory (line 260), mcporter (261), Codex (264) and SocratiCode (266). The two pin files still record Serena `c6fbd1c5`, headroom 0.37.0, SocratiCode Linux 1.15.0 / Mac 1.14.0, and mcporter Linux 0.14.1 / Mac 0.13.13 ([Linux:131][linux-mcporter], [278][linux-context-pins], [Mac:105][mac-mcporter], [207][mac-socraticode], [307][mac-context-pins]). The table and its receipts preserve the rule without landing #509. |
| Context Mode cache-heal hook | [adoption/templates/claude.settings.template.json:204][cache-heal] already names `context-mode-cache-heal.mjs` in SessionStart. #509's account of upstream deployment stays dated source review; this template citation is repository wiring, not a fresh installed-client check. |

## Facts kept

The following are **#509's claims**, read there in full at `f33dc2c9` and attributed
to its upstream source review on **2026-09-29**, at the tags it names. Evidence class:
`source_review`. They were not re-run or re-established as host behavior for this
retirement. Quoted passages come from that record; the one new upstream read is marked
separately in (b).

**(a) Serena, v1.7.0 compared with `c6fbd1c5`.** #509, lines 34–37:

> The recipe says "Upstream declares `2.0.0.dev0`; the commit is the
> identity" and records no reason for a dev commit (`recipes/README.md:109`).
>
> the pinned commit has one tool class more than v1.7.0 (`SerenaReplTool`), and it adds an `EditApiMixin` base to the editing
> tools, an internal change this comparison does not characterize. All 24 Serena tools a session here uses exist at v1.7.0.

The recipe's current [Serena row:109][serena-recipe] still records the dev commit's
identity; this does not settle the channel on existing hosts. "[L]atest release v1.7.0"
(#509 line 31) is #509's September 29 observation, not a new latest-release claim.

**(b) headroom, target 0.39.1, never 0.39.0.** #509, lines 102–103:

> Its proxy token-rate limiter could refuse
> large-context requests indefinitely, fixed in 0.39.1. The target is 0.39.1, never 0.39.0. Linux qualifies first.

**Re-read 2026-10-03:** `gh release view v0.39.1 -R headroomlabs-ai/headroom`,
exit **0**. The [official v0.39.1 release notes][headroom-release] say:

> **proxy:** stop the 0.39.0 TPM limiter from refusing large-context requests forever

The release links [#3806](https://github.com/headroomlabs-ai/headroom/issues/3806) and
fix commit [`7968122658c31c06ef3e5b1fe7911c8cb0a79ade`](https://github.com/headroomlabs-ai/headroom/commit/7968122658c31c06ef3e5b1fe7911c8cb0a79ade).
This corroborates the defect and fix in the release notes, which list it as the release's
only entry, under "Bug Fixes". It does not qualify 0.39.1 on either host or overturn the
deliberate 0.37.0 hold, whose overturn condition concerns the omission-count notice and
log routing (see the headroom row in the supersession table).

**(c) QMD on the Mac, 2026-09-29.** #509, lines 62–65:

> QMD is registered as an MCP server for Codex only. It is not in the Claude user-scope
> MCP registry or the plugin list on this Mac (project-scoped `.mcp.json` files were not inspected), although
> `adoption/agents/claude/stack-researcher.md:4` grants `mcp__qmd__*` and the token carrier tells agents to load it. That is a candidate cause
> for low Claude-side QMD use, to be tested in the root-cause step.

This remains a dated, untested causal lead about that Mac, not an absence claim about
all scopes or the other host. Main's QMD registration note concerns its separately
recorded already-wired stack.

**(d) RTK versus Context Mode on Codex hooks.** #509, lines 76–77:

> RTK documents `updatedInput` for Codex, while Context Mode's compatibility table lists Codex hooks as unable to modify
> arguments. Only a test on the installed Codex decides whether the explicit-command adaptation stays.

This conflict remains unverified on a host in this retirement. Main's related finding
is [token-practice-f1-f9.md:60][rtk-hold]; [codex-worker-lane.md:29][codex-instructions]
separately records that the RTK-generated `@` instruction reference did not expand.
An instruction-loading finding does not itself settle hook argument rewriting.

**(e) Context Mode on Codex.** #509, lines 83–85:

> for Codex a plugin with `plugin_hooks`, or a manual fallback (`npm install -g context-mode`, `[features] hooks =
> true`, `[mcp_servers.context-mode]`, and a `hooks.json` calling `context-mode hook codex ...`).

This preserves the integration options read at Context Mode v1.0.169; it is not an
instruction to install them or a claim that today's Codex accepts every option.

**(f) Upstream test and eval commands.** These quotations preserve #509's inventory,
not results from executing the suites in this retirement:

- **SocratiCode v1.16.0**, #509 lines 53–54: "vitest unit, integration and e2e suites
  (`npm run test:unit`, `test:integration`, `test:e2e`); e2e needs Docker, Qdrant and
  Ollama."
- **QMD v2.8.3**, line 66: "`npm test` (types, vitest on Node, tests on Bun) and
  `npm run test:package`, a packaging smoke test."
- **RTK v0.50.0**, line 78: "Rust unit tests via `cargo`; upstream CI runs
  `cargo build --release` and `cargo audit`."
- **Context Mode v1.0.169**, lines 88–89: "`npm test` (vitest, with a build first) and
  `npm run benchmark`, `test:use-cases`, `test:compare`, `test:ecosystem`; its
  `BENCHMARK.md` lists 21 scenarios."
- **Serena v1.7.0 / `c6fbd1c5`**, lines 32–33: "Its `docs/04-evaluation` holds an
  evaluation methodology, prompts and results for Claude Code, Codex and other clients."

## Open leads (not decisions)

| Lead | Named holder and next evidence |
| --- | --- |
| Serena channel on the existing hosts | The next workstation qualification or currency wave owns the release-versus-dev comparison and any recorded reason to retain `c6fbd1c5`. The new-WSL install recommendation does not decide the existing-host channel. |
| headroom "never 0.39.0" | The separate headroom requalification named in #642 W1 owns the next headroom pin decision. By main's own records, qualifying 0.39.1 alone would not lift the hold: main qualified 0.39.0 on 2026-09-25 and kept 0.37.0 (see the headroom row above), and its 2026-10-01 reads say 0.39.1 "changes only the proxy rate limiter" ([architecture:704][architecture-headroom]), "so the omission-count hold stands" ([layer closure:1421][closure-headroom]). The requalification must therefore address main's overturn condition at [workstation-sota-refresh.md:549–550][headroom-overturn] (upstream counts levels over the omitted lines only, or a measured answer-quality comparison on log inputs shows net value for 0.39.0's log routing), while keeping the release-note defect/fix distinction for the proxy limiter. |
| QMD's Claude registration on the Mac | The session on the other host owns the Mac's user, plugin and project-scope inspection and the causal test for low QMD use. |
| RTK Codex hook test | The RTK requalification named in #642 W1 owns the installed-Codex argument-rewriting test and the independent instruction-loading checks. |

## Alternatives considered

- **Land #509 as is.** Its Codex and latest-release facts are stale, and its pin
  sequence conflicts with newer qualification and hold records.
- **Port its recommendations as live work.** Live owners already exist in #642 and
  its separate requalifications, #626, and the new-WSL selection. This record preserves
  leads for those holders instead of assigning their operational work here.
- **Close without a record.** Facts (a)–(f) would lose a main-branch locator even
  though the original PR head remains reachable.

## What would overturn this

- An owner named for #509 objects within the notice window; that lane keeps the PR.
  Any objection or ownership claim found on the required pre-merge re-read also stops
  this custody action.
- A later record decides the Serena channel on existing hosts or QMD's registration
  on the Mac; it supersedes the matching open lead here.

## Limitations

- Historical source review, repository wiring, recorded qualification receipts and
  live host acceptance remain distinct. Only the headroom v0.39.1 release notes were
  re-read upstream for this retirement; no component was installed or executed.
- The Serena comparison counts source tool classes without characterizing the new
  mixin or proving runtime equivalence. QMD's original project scopes were not
  inspected, and its proposed effect on use remains untested.
- Main's lag table names Linux qualification receipts; it does not qualify the Mac.
  New-WSL selection and architecture files are dated recommendations and snapshots,
  and are cited without edits. Open #626 and #642 do not change main merely by being
  open.
- **Completeness critic:** the comparison covers every #509 pin-sequence item,
  integration-path step, cache-heal hook, Mac lag rule, and all six unique-fact groups.
  Missing modalities are existing-host Serena behavior, Mac registration/use, RTK
  hook rewriting, and a native headroom requalification that meets main's omission-count
  overturn condition. Those become the four named holders' next lifecycle qualification
  sweeps; this record supplies no new winner or convergence claim.

## Sources

- [#509 at `f33dc2c90679e14b282291d63a11c25b73ff943a`][original], all 152 lines;
  its [author handoff][handoff] and [custody notice][notice]. Original repository
  base: `df4123684fb55655b885a8dc6431a263c18b4c4c`.
- Upstream tags **as read by #509 on 2026-09-29**, not newly re-read here:
  [RTK v0.50.0](https://github.com/rtk-ai/rtk/tree/v0.50.0),
  [Context Mode v1.0.169](https://github.com/mksglu/context-mode/tree/v1.0.169),
  [Serena v1.7.0](https://github.com/oraios/serena/tree/v1.7.0) and
  [`c6fbd1c5932df2494ffa0020af5a9fbe80b82143`](https://github.com/oraios/serena/commit/c6fbd1c5932df2494ffa0020af5a9fbe80b82143),
  [SocratiCode v1.16.0](https://github.com/giancarloerra/SocratiCode/tree/v1.16.0)
  (`CHANGELOG.md`), [QMD v2.8.3](https://github.com/tobi/qmd/tree/v2.8.3),
  [headroom v0.39.1][headroom-release], and
  [mcporter v0.14.1](https://github.com/openclaw/mcporter/releases/tag/v0.14.1).
- The headroom release read on 2026-10-03: `gh release view v0.39.1 -R
  headroomlabs-ai/headroom`, exit 0, quoted in (b).
- [Main at `9b0b8d6d25f9e3fb8f71770500e774170423315e`](https://github.com/seathatflowsinourveins/native-agent-stack/tree/9b0b8d6d25f9e3fb8f71770500e774170423315e),
  with the exact paths and line numbers in the supersession table, including
  [recipes/README.md:109][serena-recipe] and
  [docs/decisions/2026-09-28-ecosystem-roadmap.md:334][roadmap].
- PR #523 (merge `be91e1f8`), #580 (merge `85543efe`), #626 (OPEN, head
  `75a2ada1eb4db08568b75c5457d2a0b61a949bbb`), #642 (OPEN, head
  `1b9d09273be764d1cb26993ed9b5138b16bd7ce6`), and #508 (OPEN, head `b7fcc219`),
  read on 2026-10-03. #508's outcome is not an input to this retirement.

[original]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/f33dc2c90679e14b282291d63a11c25b73ff943a/docs/decisions/2026-09-29-token-stack-release-review.md
[handoff]: https://github.com/seathatflowsinourveins/native-agent-stack/pull/509#issuecomment-5893372924
[notice]: https://github.com/seathatflowsinourveins/native-agent-stack/pull/509#issuecomment-5967135605
[headroom-release]: https://github.com/headroomlabs-ai/headroom/releases/tag/v0.39.1
[socraticode-qualified]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-25-workstation-sota-refresh.md#L437-L453
[linux-codex]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/adoption/pins-linux-x86_64.json#L53-L56
[lag-table]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/tests/test_adoption_bootstrap_macos.py#L255-L267
[w1-moves]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/1b9d09273be764d1cb26993ed9b5138b16bd7ce6/docs/decisions/2026-10-03-currency-wave-w1.md#L24-L26
[w1-mcporter]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/1b9d09273be764d1cb26993ed9b5138b16bd7ce6/docs/decisions/2026-10-03-currency-wave-w1.md#L127-L138
[w1-holds]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/1b9d09273be764d1cb26993ed9b5138b16bd7ce6/docs/decisions/2026-10-03-currency-wave-w1.md#L148-L150
[release-table]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-10-01-definitive-sota-wsl-program.md#L281-L299
[architecture-headroom]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/catalogs/foundation/new-wsl-architecture-20261001.json#L704
[headroom-qualified]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-25-workstation-sota-refresh.md#L519-L550
[headroom-overturn]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-25-workstation-sota-refresh.md#L549-L550
[headroom-receipt]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/receipts/headroom-039-qualification-20260925.json
[closure-headroom]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/artifacts/layer-closure-assessment-20261001/foundation.json#L1421
[rtk-hold]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-26-token-practice-f1-f9.md#L52-L65
[codex-instructions]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-26-codex-worker-lane.md#L28-L30
[selection-serena]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/artifacts/new-wsl-clean-install-selection-20261001/selection.json#L234-L240
[selection-socraticode]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/artifacts/new-wsl-clean-install-selection-20261001/selection.json#L264-L270
[selection-qmd]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/artifacts/new-wsl-clean-install-selection-20261001/selection.json#L315-L321
[selection-rtk]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/artifacts/new-wsl-clean-install-selection-20261001/selection.json#L439-L445
[qmd-note]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/token-efficiency-stack.json#L2217
[socraticode-note]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/token-efficiency-stack.json#L2984-L2989
[linux-mcporter]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/adoption/pins-linux-x86_64.json#L131-L132
[linux-context-pins]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/adoption/pins-linux-x86_64.json#L278-L318
[mac-mcporter]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/adoption/pins-macos-arm64.json#L105-L106
[mac-socraticode]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/adoption/pins-macos-arm64.json#L207-L208
[mac-context-pins]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/adoption/pins-macos-arm64.json#L307-L347
[cache-heal]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/adoption/templates/claude.settings.template.json#L199-L205
[serena-recipe]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/recipes/README.md#L109
[roadmap]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-28-ecosystem-roadmap.md#L334
