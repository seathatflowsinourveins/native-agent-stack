# Decision: retire the unrun GPT-6 lane compression A/B in PR #431 (2026-10-03)

**Decided by:** Claude session `native-agent-stack-0c`, under its dated
[custody notice of 2026-10-03T08:21:58Z][notice].

**Scope:** the obsolete preregistration instrument at
`73fc873e1da52ac68a731d33e482a7ae0444f6b2`, its custody and its references.
This record makes no gateway setting change and authorizes no experiment.
The foundation action it serves is keeping native runtime-worker decisions and
recoverable evidence current for complex builds and research.

**Source-review base:** main at `9b0b8d6d25f9e3fb8f71770500e774170423315e`.
Every main file and line below refers to that revision. Pinned PR files and
the two 2026-09-28 comments are historical evidence; source reads reported by
the draft are dated 2026-09-27 and are not re-verified here.

## Decision and custody

0c retires #431 **unrun** after the custody notice's two-hour objection window,
which ended at 2026-10-03T10:21:58Z. The build's read-only check at 10:30:43Z
found the original head and three comments, no objection on #431 or in #608,
and no returning owner or objection in the scoped coordination search.
Closing follows merge of this record, independent review and a fresh check of
those surfaces and the head/comment-count gate. The original branch is kept.
The [notice][notice] and its [08:22:22Z counterpart in #608][notice608] establish
the disposition and the objection rule.

The drafting session `token-save-practice-gpt6` had ended by the
[2026-09-28T20:51:13Z custody comment][custody]. That comment assigned custody
to `token-save-practice-e2e-status` and required handing #431 back if the original
owner returned with in-flight state. 0c's planning census at 2026-10-03 05:57 UTC
reported that the 2026-09-28 custodian was absent from LANES-BOARD; the
[2026-10-03 notice][notice] records that neither named session was on that day's
board. The census time is the dated custody-planning observation, not a new
reproduction of an old board. Neither appears on the board inspected at 09:58
UTC. A return with in-flight state still stops this disposition.

This follows the [Vela/VelaNext retirement precedent][vela]: preserve dated
facts and recovery locators, distinguish history from current status, and require
a new preregistration for work whose bindings have changed.

## Scope: the instrument only. It does not decide compression on 20128.

Main's open decision (a) is unchanged. The relevant wording in
[2026-09-30-omniroute-rebuild.md L276-279][decision-a-quote] is:

> **Open user decisions.** (a) Compression on 20128 (the Codex lane itself; it would rewrite real Codex CLI traffic). The
> user's conditional answer of 2026-09-30 about 02:25Z, relayed by another session and not seen first-hand here, was "yes
> if SOTA converged, the quality itself needs to be maintained at suitable high output": a reproduced saving on real
> traffic and no output regression. It is **not applied**.

The unchanged [foundation-stack.md L250][foundation-l250] says:

> On 20128, the global switch is off and `codex/*` is excluded: our choice for byte-identical passthrough of native Codex traffic. Upstream's own comment ([`chatCore.ts` L1429-1449](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore.ts#L1429-L1449) at `a58000c7`, the same comment above `isCompressionExcluded` at `2f42a9ac1`) says native Codex passthrough is deliberately not part of the exclusion, compresses through an adapter with Codex tool-output guards when compression is on, and that operators who want byte-identical passthrough can add `codex/*`. Turning it on is an open user decision: the pi-practice session's 3-arm measurement on real Codex jobs found the headerless lane compressed 0 tokens (see the 2026-09-30 record).

## Why it is obsolete

The right-hand column is **documented state at the source-review base**, not a
live gateway or installed-client observation by this retirement build. Retargeting
the instrument would change its treatments, harness qualification and scope.

| Binding | Value at `73fc873e` | Main now (file and line) |
| --- | --- | --- |
| Build | OmniRoute 3.8.51, per the [#431 PR body](https://github.com/seathatflowsinourveins/native-agent-stack/pull/431) (its line 27) and the [20:51:13Z comment][custody]; installed build `dd6e9607e` and pinned source `a58000c7` ([JSON L38-65][old-build]); the 2026-09-28 custodian identifies the installed build as `a58000c7` + #14904 + #13788 ([20:51:13Z comment][custody]). | Rebuilt on release/v3.8.51 `2f42a9ac1` ([rebuild L1][rebuild]); 20128 carries upstream PR 15167 since 2026-09-30T06:32Z ([foundation-stack.md L246][effort-carry], [#534](https://github.com/seathatflowsinourveins/native-agent-stack/pull/534)). |
| D0/D1 | Headerless `[session-dedup, ccr, lite, headroom]`; registered-key 60-minute live zone; output styles on for D1 ([JSON L1197-1238][cells-d], [PREREGISTRATION.md L135-146][old-cell-engines]). | Headerless `[session-dedup, ccr, lite]`, headroom off in the engines map, no output style; live-zone scoping removed ([rebuild L64-85][settings], [L117][removed-scoping], [foundation-stack.md L251][foundation-l251]). Stored combos can still name headroom; this is not a claim that every header-selected route has it off. |
| A0/A1 | Twelve engines including omniglyph; `allow-lossy` header; styles on for A1 ([JSON L1239-1296][cells-a]). | Omniglyph off and inert on GPT-6 ([rebuild L115][omniglyph-off]); `allow-lossy` selects the stored peer combo, not the engines map ([foundation-stack.md L251][foundation-l251], [rebuild L81-85][stored-combos]). |
| 2026-09-28 W2-W15 digests | Applied and read back, then unchanged at 20:48:28Z ([03:51:17Z apply comment][apply], [20:51:13Z custody comment][custody]). | Historical configuration superseded by the rebuild's settings and T10 ([rebuild L64-85][settings], especially L68). |
| Model | Canonical `gpt-6-astra-max` targets; Harbor emits that bare argument ([JSON L943-998][old-client], [cells][cells]). | For unpinned work, `gpt-6.1-sol` is the primary coordinator/worker policy ([AGENTS.md L38][model-policy]); this is a dispatch policy, not a replacement model result. |
| Clients | Codex 0.157.1; Harbor 0.23.0 ([JSON L943-944][old-client-version], [PREREGISTRATION.md L33-49][old-runner-choice]). | The rebuild announces Codex 0.159.1 ([rebuild L1][rebuild]). This states the rebuild's announced version, not the installed client's current version or a claim that Harbor changed. |
| Bases | [PR body](https://github.com/seathatflowsinourveins/native-agent-stack/pull/431) says `e82e6be7`; JSON L9 says `0f76651d` ([JSON][old-json]). The actual parent of the original authoring commit `e33a0717` is `55fc8d17f530851a3a4dff0564eef3e450967231`. | Read-only git inspection found `git rev-list --count 73fc873e..dcae68bd0` = 163; that is the planning comparison, not the count against this record's later `9b0b8d6d2` base. |

## What main already records about the question

The following retain the evidence qualifications in
[2026-09-30-omniroute-rebuild.md L276-295][decision-a]. These are a reading of
main's dated record, not a new model run or a rerun of its probes:

- **Headerless:** 0 compressed tokens in all 115 joined rows of the three-arm
  Codex jobs (**reported, not reproduced here**). Cache-read shares were 0.906,
  0.902 and 0.896. L284-285 attributes non-application to Codex tool-output
  content-part arrays, which lite does not rewrite.
- **Lossy header:** 0.36% of the input over 55 rows with `gpt6-safe-lossy`
  through 20129 (**reported, not reproduced here**, L285-287). This is not a
  measurement of #431's `allow-lossy` cell.
- **Offline real bodies:** on eight of those jobs' real request bodies, the
  lossy lane saved 0.34% (908 of 265,483 tokens) while, by that record's regex
  count, losing 47 file-path occurrences, 1 hex id and 1 error line; the
  headerless lane changed 0 items of 60 to 78 per body (L287-291). This is the
  recorded offline gateway-step probe, distinct from the reported live arms.
- Main's conclusion is **"neither lane meets the condition"**: a reproduced
  saving with no exact value lost (L292-293). String-shaped shell outputs of
  older models and very long sessions with large tool outputs remain untested
  (L293-294). Nothing in retiring #431 alters that conclusion or the open
  decision.

## Unique facts to preserve

### Objective and ceiling

[PREREGISTRATION.md L9-15][objective] compares all-attempt entry-gateway input
plus output tokens, subject to paired quality, exact-record and transport gates.
Its ceiling is the six named task domains per role. It cannot authorize moving
a production builder, reviewer or researcher role. Reviewer/researcher
output-style conclusions cover JSON-only records; prose verdicts, research
narrative and evidence-writing need representative frozen tasks in a new
preregistration. JSON L3040 identifies the optimization objective as minimum
total billed tokens among non-inferior cells ([decision rule][old-rule]).

### Cells at the pinned head

These are **proposed, unqualified cells**, not effective host settings. Their
canonical models are not the arguments Harbor emits. Every
`observed_effective_plan` is `null` and every
`canonical_model_is_runner_argument` is `false`
([JSON L1183-1297][cells], [L943-998][old-client]).

| Cell | Base URL | Canonical model | Engines | Compression header | Output styles | Principal | `env_key` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C | `http://127.0.0.1:20128/v1` | `cx/gpt-6-astra-max` | `[]` (off) | Omitted (`null`) | Off | `keyless` | Omitted; C template omits it (JSON L992) |
| D0 | `http://127.0.0.1:20129/v1` | `sharedgw/gpt-6-astra-max` | `[session-dedup, ccr, lite, headroom]` | Omitted (`null`) | Off | `registered-lane-key` | `OMNIROUTE_FW_API_KEY` |
| D1 | `http://127.0.0.1:20129/v1` | `sharedgw/gpt-6-astra-max` | `[session-dedup, ccr, lite, headroom]` | Omitted (`null`) | On | `registered-lane-key` | `OMNIROUTE_FW_API_KEY` |
| A0 | `http://127.0.0.1:20129/v1` | `sharedgw/gpt-6-astra-max` | `[session-dedup, ccr, lite, rtk, codex-responses, headroom, relevance, caveman, aggressive, llmlingua, ultra, omniglyph]` | `x-omniroute-compression: allow-lossy` | Off | `registered-lane-key` | `OMNIROUTE_FW_API_KEY` |
| A1 | `http://127.0.0.1:20129/v1` | `sharedgw/gpt-6-astra-max` | `[session-dedup, ccr, lite, rtk, codex-responses, headroom, relevance, caveman, aggressive, llmlingua, ultra, omniglyph]` | `x-omniroute-compression: allow-lossy` | On | `registered-lane-key` | `OMNIROUTE_FW_API_KEY` |

D/A use a proposed 60-minute live zone. Styles-on means `terse-prose`,
`less-code`, `ponytail`, `i-have-adhd`, all full; styles-off clears the explicit
styles and disables legacy caveman output mode. The downstream D/A model is
`gpt-6-astra-max`, and the proposed wire format is Responses to Responses
([PREREGISTRATION.md L126-158][old-cell-prose]).

### Sealing gates

All eleven gates have **`passed: null`** at `73fc873e`. The following keeps
their identifiers and requirement strings, verbatim from
[JSON L3430-3486][gates], as a checklist for any future gateway A/B, without
accepting their obsolete pins or authorizing a run.

| Gate id | Requirement, verbatim | `passed` |
| --- | --- | --- |
| `runner-route` | Supported 20129 slashless route preserving canonical native metadata, five-item/full prompt equivalence and coordinator live 200 at max; C route equivalence too. No mapping has been found/qualified. | `null` |
| `merged-profile` | Materialize/hash native semantic base+stack-worker merge; no profile/profiles keys; same resolved config and prompt-input versus -p reference before/after Harbor forced flags. | `null` |
| `network-containment` | Hash extra_docker_compose overlay; prove actual container reachability and separately qualify upstream-supported containment of passwordless admin APIs; trusted-task constraints alone are not a security boundary. | `null` |
| `header-capture` | Materialize/hash upstream-hook response-header observer, qualify privacy/SSE/cache semantics and X-Correlation-Id entry joins including failures; demonstrate a separate exact second-hop effort join. | `null` |
| `effort-detail` | Qualify detail-API selectors and inspect only reasoning.effort at joined hops; null corroboration columns are allowed, missing body stays unknown. | `null` |
| `two-hop` | Freeze Responses wire format and prove three native steps, genuine call IDs/encrypted reasoning replay, prompt_cache_key, session/account affinity and arm account spread/cache rate. | `null` |
| `effective-config` | Read back C off/exclusions; keyed D/A engine/style plans, 60-minute live zone, optional dependencies and safety compaction. Existing key/TTL are facts, reuse is not accepted. | `null` |
| `native-harnesses` | Harbor 0.23.0, Codex 0.157.1, chosen observer, statistics, actual task dependencies/images and exact build/config hashes through supported upstream commands. | `null` |
| `native-controls` | Materialize/hash three-turn wrappers and graders; native known-pass/fail/malformed controls, four numeric output shapes, rebuilt Chat collision plus separately observed native reachability. | `null` |
| `pilot-power-resources` | Complete excluded pre-confirmatory pilot; calibrate NI at margin, simulate power and operational stops; freeze powered n, complete token budget, reserve, wall time and schedule. | `null` |
| `usage-sensitivity` | Confirm usage fields and finalization, missing-row input/output bounds, all-corner sensitivity and simultaneous cost bounds; actual dollar prices remain unknown. | `null` |

### Source reads dated 2026-09-27, not re-verified

These preserve the draft's dated source findings, with their original upstream
pins; they are not claims about today's installed clients or latest upstream.
The draft's [runner section L31-112][old-runner], its [JSON source inventory][old-sources]
and the [PR body's SOTA sources](https://github.com/seathatflowsinourveins/native-agent-stack/pull/431)
are the historical reporting sources.

- Harbor `codex.py` runs `model = self.model_name.split("/")[-1]` and passes
  the last segment to `--model`, at [v0.23.0 `1e5c5c6d` L1339-1449][harbor-pin]
  and inspected [main `3c823808` L1502-1605][harbor-main]. No `-p` forwarding
  was found in those inspected sources; the draft does not establish a working
  bare-model route.
- promptfoo 0.123.1 [codex-sdk.ts L1034-1134 at `34f74d34`][promptfoo-sdk]
  passes `config.model` intact. The Codex SDK [exec.ts L91-178 at
  `36650394`][codex-exec] pushes the model to `--model` unchanged. These are
  source findings, not successful alternate-runner qualification.
- Codex rust-v0.157.1 [manager.rs L763-780][codex-manager] and
  [model_info.rs L99-150][codex-model-info] support the draft's one-slash
  canonical-model rule. [config/src/loader/mod.rs L286-340 at
  `36650394`][codex-loader] is the profile-loader read; the draft requires
  native semantic merging and resolved-config/prompt-input equivalence.
- inspect_swe 0.2.71 [codex_cli.py L483-637 at `7eb8dd64`][inspect-swe]
  resolves a model slug and uses its own OpenAI bridge; that is a runner
  alternative needing transport and profile qualification, not a drop-in result.

### Review and repair

The [PR body](https://github.com/seathatflowsinourveins/native-agent-stack/pull/431)
reports one `gpt-6-astra`/max repair round after an independent Claude review.
The pinned [repair record, JSON L3558 onward][repair] and
[PREREGISTRATION.md L387-419][old-review] retain 23 findings: B1-B5,
M1-M10 and m1-m8. Eleven were **fixed**, twelve **fixed by gating**, and none
was declined whole. Gating corrected the protocol while native qualification
remained open. M9 declines only request size as a bound on total input plus
output usage ([JSON L3724-3731][m9]). The two coordinator corrections are the
one-slash engines-on model and effort evidence from the request body rather
than the `call_logs` effort columns (PR body; JSON L994-998 and the B4 row).

The structural test went from **`FAILED (failures=12)`** to **`OK` over 10
tests**. This is **synthetic structural evidence**, not gateway or model
acceptance. The pinned repair's required registry regression run had **57
tests and 11 errors** because its sandboxed TMPDIR contained a read-only
`.git` sentinel; the PR body records **57 OK outside that sandbox**. Both
results stay distinct. The repair JSON also states `model_inference_performed:
false`; its stored checks are not a new model run or a usage receipt.
Sources: [PREREGISTRATION.md L441 onward][old-checks], [repair checks][repair],
and the PR body's sandbox note and local-commands section.

### Anti-pattern entries, verbatim at `73fc873e`

The ten general `anti_pattern_log` entries below retain their exact text and
pin context. B, M and m entries remain available in
[JSON L3184-3414][anti-patterns-review] and the
[repair disposition rows][repair]. The first eight general entries are
[JSON L3143-3183][anti-patterns-general]; the last two are
[L3415-3428][anti-patterns-late]. Paths and line numbers inside the quotes are
historical verification locators, not instructions to inspect host state.

1. **Mistake:** Treating safe-default classification as proven losslessness.
   **Correction:** Session-dedup index collision and lite truncation paths are visible; all cells require exactness checks.
   **Verification:** or-engine-labels; or-dedup 291-345; or-lite 148-168; or-adapter 116-145; or-strategy 367-386.
2. **Mistake:** Treating explicit output styles and legacy caveman output mode as additive, or clearing only styles to disable them.
   **Correction:** Explicit nonempty styles win; disable legacy fallback too.
   **Verification:** or-styles 13-28; D0/A0 config contract.
3. **Mistake:** Assuming promptfoo --help is read-only.
   **Correction:** Research preflight attempted logging/DB migration and failed with EROFS/SQLITE_CANTOPEN, exit 1; no successful host write observed. Use package metadata/source under no-host-change scope.
   **Verification:** promptfoo-startup src/main.ts 63-64 before parse at 147; src/logger.ts 224-247.
4. **Mistake:** Assuming direct-shell gh failure means upstream research unavailable.
   **Correction:** Installed research tool gh api succeeded; source byte comparisons and pin checks retained here.
   **Verification:** Seventeen installed compression files compared byte-for-byte to OmniRoute a58000c7, all gh calls exit 0. Repair recomputed 17/17 installed hashes against retained pinned-source hashes.
5. **Mistake:** Assuming a configurable Harbor CODEX_HOME proves arbitrary parent-home or -p forwarding.
   **Correction:** Superseded in repair: use native semantic merged-config profile route through Harbor config; require resolved-config and prompt-input equivalence, not literal -p forwarding.
   **Verification:** harbor-codex 81,1352-1359,1432-1448; harbor-options 50-70.
6. **Mistake:** Leaving the peer-reported Responses-to-lite path untraced.
   **Correction:** Installed bodyAdapter maps function_call_output to role tool; strategySelector invokes lite through it, and lite truncates eligible string content without consulting codex-responses metadata. This is source reachability, not observed live application.
   **Verification:** or-adapter 116-145,205-221; or-strategy 367-386; or-lite 148-168,259-262.
7. **Mistake:** Applying a binomial gate to a fixed balanced heterogeneous task schedule.
   **Correction:** Independent task draws remain, but a harmful-discordance-only bound has near-zero power for equal arms at .95 success. Use pilot-sized paired net difference and exact harmful-minus-beneficial fallback.
   **Verification:** Repair recomputed n=240, alpha=.05/24: at most 3 harmful discordances, pass probability .003102 for identical independent .95 arms. Sources: scipy, scipy-exact; B5 structural red-first test.
8. **Mistake:** Guessing affinity-header names for the draft checklist.
   **Correction:** Earlier correction was wrong: x-omniroute-connection pins a connection; session affinity comes from three session headers, body identifiers, prompt_cache_key, then input hash.
   **Verification:** https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/sse/services/sessionAffinityPin.ts#L197-L221; tests.test_gpt6_lane_compression_ab_preregistration.test_sensitivity_affinity_and_scope_are_explicit failed before repair.
9. **Mistake:** Assuming the requested alternate TMPDIR avoided all repository sentinels.
   **Correction:** The required regression command found an existing read-only .git in /var/tmp/claude-431 too. Preserve the 11 export-refusal errors; do not remove metadata or weaken tests. Repository classification passes independently.
   **Verification:** ls -ld showed dr-xr-xr-x for the sentinel; blind_checkout.py:970-973 directly checks ancestor/.git existence; 57 tests returned FAILED (errors=11).
   **Enforced by:** Existing blind export ancestor guard, unchanged.
10. **Mistake:** Describing tokens_compressed as selected compression plus reactive savings could imply addition.
    **Correction:** The reactive path assigns tokensCompressed at chatCore.ts L2164, replacing the earlier selected-pipeline estimate. Label the row as latest recorded compression estimate; never sum stages.
    **Verification:** Read installed chatCore.ts L1916-1919 and L2157-2164; source hash matches pinned upstream.
    **Citation:** https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore.ts#L2157-L2164

**In the canonical log.** Entries 1-8 and 10 are now rows dated 2026-09-27 at
the end of the [anti-pattern log][log], in its five columns, with host paths
left out and this section as their source. Entry 9 adds no row. Main's row
"Assuming a temporary directory is outside every Git repository" (2026-09-27)
records the same mistake, the same 11 export-guard errors and the same rule
(`TMPDIR` outside every repository, and keep the guard's refusal), so it stays
unchanged. One observation in entry 9 is not in that row: in the draft's
sandbox the alternate location also had a read-only `.git` sentinel, so that
row's `/var/tmp` is an example, not a guarantee. The draft's two coordinator
corrections under Review and repair already have 2026-09-27 rows on main:
"Using a two-slash model slug on a chained gateway" and "Reading a null
call_logs effort column as "effort not sent"".

### 2026-09-28 20129 apply record: historical and superseded

The [2026-09-28T03:51:17Z apply comment][apply] records W1 at
01:22:13Z and W2-W15 from **03:49:59.685Z to 03:49:59.882Z**: fourteen
writes, each HTTP 200/201, each read back through its matching GET. W16 was
deferred to the A/B window. The post-apply read at 03:50:11Z recorded combined
digest `952425561c250e57900559b294003a0859d289ab54898bd67e8f3846633267a7`;
the before-state compression digest was `a08dde080d887f59` at 03:22:05Z and
03:49:04Z. This was **not a seal digest**, because W16 was not applied.

The [2026-09-28T20:51:13Z custody comment][custody] preserves four per-route
digests, all unchanged on the **20:48:28Z GET-only re-read**:

| Route | Historical SHA-256 |
| --- | --- |
| `/api/settings/compression` | `ed38086bee1e2e94bd10c1108a2420a182ed097f91656d7e5e3f05cfb8772f30` |
| `/api/model-capability-overrides` | `4be3a94ee28697c47cd9f1fc8196c3a1ac97f3a3eb8f1a84399f585b3303aef3` |
| `/api/context/combos` | `b249cec33f0f0f386f316cc3ea92407dfa57ae423d887f9f53ed97f495e3d4b9` |
| `/api/resilience` | `3ce8a52205a0b58260aa339727de71ba939e8f1007e6504d61045e081528816e` |

That comment explicitly says the configuration did not match the proposed
cells: headerless D0/D1 had no engine compression, A0/A1 used eleven stored
steps without omniglyph, and the live zone was off. The amendment was held
pending containment evidence. These observations were superseded by the
2026-09-30 rebuild and T10 ([rebuild L64-85][settings]); this retirement neither
re-reads the management API nor treats the old digests as current settings.

### Key-variable name, CI and unknown usage

The [PR body's key-variable note](https://github.com/seathatflowsinourveins/native-agent-stack/pull/431)
records that the proposed variable name `OMNIROUTE_20129_API_KEY` triggered
gitleaks' `generic-api-key` rule through its digits. It was renamed
`OMNIROUTE_FW_API_KEY` without an exemption; it names a variable, not a key
value. Main's lane builder still hard-codes `OMNIROUTE_API_KEY` at
[build_args.py L116][builder-key], so the draft's configuration-equivalence
gate was not resolved by renaming.

The eight latest required CI check contexts on #431 passed on **2026-09-27**,
against its old main: validate, verdict-review-gate, sota-sources, secret-scan,
validate-macos, osv-scanner, token-report and dependency-review. The read-only
`gh pr checks 431 --required --json name,bucket,completedAt,link` inspection
returned eight `pass` buckets and that date. The raw rollup also contains
superseded cancelled and auxiliary skipped runs; saying every historical run
passed would overstate it. Source: [#431 checks][old-ci], including the
[final validation run][old-validation].

**Usage: unknown.** Neither the PR nor `repair_round_20260927` records model
usage. No A/B ran: JSON L3-6 has `status: DRAFT`, `frozen: false`,
`run_started: false`, `execution_authorized: false`, and L11 has
`results: null` ([JSON][old-json]). Historical checks and this source review
do not supply missing usage or any quality/cost outcome.

## Where the content stays

The original PR, its branch, both 2026-09-28 comments and its full content are
kept. At **2026-10-03T10:30:43Z**, read-only `git ls-remote origin
refs/pull/431/head` returned
`73fc873e1da52ac68a731d33e482a7ae0444f6b2`.

| File at `73fc873e` | Git blob | Proposed manifest SHA-256 | Bytes |
| --- | --- | --- | ---: |
| `blueprints/gpt6-lane-compression-ab/PREREGISTRATION.md` | `e2a04fb03e7e48d2391ad4cde168feb8434e7e4a` | `a005e3193ba3b16592cfea273294a9210cc1f7ab5af327e2b6f24307ddb9f2fd` | 52,252 |
| `blueprints/gpt6-lane-compression-ab/preregistration.json` | `ca6020bcb8aef3c04e41298114f65b1e15c6211d` | `34554a57569d8cbaff2fccf101b488eb743be19e14f6d7e623c90fc9ce582206` | 272,524 |
| `tests/test_gpt6_lane_compression_ab_preregistration.py` | `4804d999b140c527feeff55ea4c7533a9cd33530` | Not a proposed manifest row here | — |

Blob IDs were read with `git rev-parse 73fc873e:<path>`; SHA-256 and byte sizes
were independently recomputed over those blobs and match
[the proposed manifest at `73fc873e`, L6884-6893][old-manifest].

**Persistence is observed on this repository.** The read-only comparison at
10:30:43Z queried both `refs/pull/554/head` and
`refs/heads/dependabot/npm_and_yarn/evidence/artifacts/macos-application-20260924/variant/next-16.3.6`.
It returned only
`6eb35af2f98dbd32c2f58394dfa5df11a73b969e refs/pull/554/head`.
[#554](https://github.com/seathatflowsinourveins/native-agent-stack/pull/554)
was closed unmerged at 2026-09-30T18:45:08Z, with `mergedAt: null`, and its
branch ref is absent. That establishes a retained PR ref after the close and
branch deletion in this repository, not a guarantee of indefinite retention.

GitHub's [Checking out pull requests locally][github-docs] says:
"After a pull request is opened, GitHub stores all of the changes remotely."
It documents fetching `pull/ID/head`; the page read on 2026-10-03 does not
explicitly promise persistence after closing. The #554 observation supplies
that narrower evidence.

Recovery commands for a future authorized checkout use plain git and the
page's documented form, `git fetch origin pull/ID/head:BRANCH_NAME`, which
creates a local branch (here `retired-pr-431`); the retirement builder does
not run the fetch or alter git state:

```sh
git fetch origin pull/431/head:retired-pr-431
git show 73fc873e1da52ac68a731d33e482a7ae0444f6b2:blueprints/gpt6-lane-compression-ab/PREREGISTRATION.md
git show 73fc873e1da52ac68a731d33e482a7ae0444f6b2:blueprints/gpt6-lane-compression-ab/preregistration.json
git show 73fc873e1da52ac68a731d33e482a7ae0444f6b2:tests/test_gpt6_lane_compression_ab_preregistration.py
```

## References on main to #431

At the source-review base, `git grep -n -w '#431'` finds thirteen lines in
ten files. This change updates only one of them, the control-default sentence
in [blueprints/runtime-workers/openhands/README.md L148-151][openhands].
The engines-on arm and its implementation remain available. Making it the
default needs a completed qualifying comparison under a new preregistration on
the current gateway build. That is a policy, not a code gate:
`environment_selection()` in the recipe still accepts an explicit `engines-on`
selection and routes it to 20129. The anti-pattern log rows this change adds
also name #431 and link this record.

The other twelve stay unchanged as dated, frozen or convergence-bound records:

- `blueprints/runtime-workers/openhands/research.md:555`, a row in the dated
  section "Takeover phase 2 corrections (2026-09-28)" that says "Control
  stays the default arm until the #431 A/B." It carries the same contingency
  as the README sentence; the updated README sentence and this record give the
  current condition.
- `blueprints/convergence-practice/omniroute-routing-20260928/README.md:161`
  and `experiment.json:502`. Their conditional "#431 cache comparison"
  clause goes moot; neither convergence-pinned file changes and no rebind is
  needed.
- `docs/decisions/2026-09-28-ecosystem-roadmap.md:201` and `:225`, both in
  that dated snapshot.
- Frozen receipts in `evidence/artifacts/omniroute-routing-20260928/`:
  `ab-requirements.md` (L31, L34, L40), `adjudication.json` (L1, six
  mentions) and `decisions.json` (L147), each pinned by SHA-256 in the bound
  record's `experiment.json` (L75, L309 and L190), and the directory's dated
  `README.md` (L33).
- `evidence/artifacts/delegated-decisions-20260928/coordination.md:35`,
  coordination evidence retained on 2026-09-28.

Related decision text that does not name #431 also stays unchanged:
[2026-09-30-omniroute-rebuild.md L276-295][decision-a] and
[foundation-stack.md L249-252][foundation-compression], including open
decision (a) and every "reported, not reproduced here" qualification.

The [lane protocol L94-149][lanes] supplies the evidence-registration and
report-regeneration procedure. Registration does not change what historical
receipts prove; the PR remains `lane:foundation`.

## Alternatives and the overturn condition

- **Land or repair the old draft:** rejected. The comparison table shows that
  retargeting the build, cells, model and harness qualification is a redesign,
  not preservation of this preregistration.
- **Make retirement a new user decision:** rejected. Open decision (a) stays
  untouched, and the PR ref, branch, comments and exact files remain recoverable.
- **Port the old instrument:** rejected. The lasting content is its facts,
  source locators and gates, which this record and the retained ref preserve.

Reopen the comparison only through a **new preregistration on the then-current
build**, if upstream rewrites Codex content-part-array tool outputs, a measured
saving appears on main's untested boundaries (string-shaped shell outputs or
very long sessions), or the user asks. The comparison that would overturn
retirement is a current, qualified treatment demonstrating savings while
meeting the frozen quality and exact-value gates. Main's [L276-295][decision-a]
remains the acceptance condition for decision (a); an obsolete or unrun draft
cannot supply it.

## Completeness critic

AGENTS.md asks a coordinator to end every substantive research or adoption
unit with a completeness critic. This one was added at review, from this
record's own evidence, with no new source read. The unit checked the custody
surfaces (the #431 head and comment count, #608, the scoped coordination search
and LANES-BOARD), main's dated records at the source-review base, the pinned
draft files with recomputed blob, SHA-256 and byte identities, the retained-ref
evidence with GitHub's documentation, the eight required check contexts and
every `#431` reference on main at the source-review base.

- **Missed modality.** Nothing live was read. The bindings table's right-hand
  column is documented state, the management API was not re-read, no installed
  client version was observed, no model ran and no usage was measured. A new
  preregistration starts from live read-backs of the then-current gateway build
  and clients.
- **Missed sources.** The draft's 2026-09-27 upstream reads (Harbor, promptfoo,
  the Codex SDK and CLI, inspect_swe) were not re-verified. OmniRoute after the
  rebuild's `2f42a9ac1` was not read for a change in how Codex
  content-part-array tool outputs are compressed, which is this record's first
  reopen trigger.
- **Missed candidate classes.** Every proposed cell is a gateway configuration.
  Main's reported cache-read shares of about 0.9 on the three-arm jobs put
  native prompt caching beside compression as a candidate class; the draft
  holds cache behaviour as a condition (its `two-hop` gate names
  `prompt_cache_key` and the arms' cache rate), not as a treatment. Its runner
  survey was source reading only (Harbor's last-segment model argument,
  promptfoo's intact `config.model`, inspect_swe's own bridge), and its ceiling
  leaves prose verdicts, research narrative and evidence-writing outside the
  output-style question.
- **Where the findings go.** The `token-efficiency` layer's next landscape sweep
  takes the OmniRoute content-part-array check, main's two untested boundaries
  (string-shaped shell outputs and very long sessions with large tool outputs)
  and caching as a candidate class beside compression. The `quality-evaluation`
  layer's next sweep takes runner qualification for a one-slash canonical model
  and a merged native profile, re-read at current upstream. The eleven sealing
  gates above remain the checklist for any such comparison. These are
  requirements for a future comparison, not grounds for a run here.

[log]: ../harness-defaults.md#anti-pattern-log
[notice]: https://github.com/seathatflowsinourveins/native-agent-stack/pull/431#issuecomment-5967134814
[notice608]: https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5967137495
[custody]: https://github.com/seathatflowsinourveins/native-agent-stack/pull/431#issuecomment-5878290260
[apply]: https://github.com/seathatflowsinourveins/native-agent-stack/pull/431#issuecomment-5863011729
[vela]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-25-retire-vela-velanext.md
[rebuild]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-30-omniroute-rebuild.md#L1
[decision-a]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-30-omniroute-rebuild.md#L276-L295
[decision-a-quote]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-30-omniroute-rebuild.md#L276-L279
[settings]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-30-omniroute-rebuild.md#L64-L85
[stored-combos]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-30-omniroute-rebuild.md#L81-L85
[omniglyph-off]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-30-omniroute-rebuild.md#L115
[removed-scoping]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-30-omniroute-rebuild.md#L117
[foundation-compression]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/foundation-stack.md#L249-L252
[foundation-l250]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/foundation-stack.md#L250
[foundation-l251]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/foundation-stack.md#L251
[effort-carry]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/foundation-stack.md#L246
[model-policy]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/AGENTS.md#L38
[builder-key]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/tools/sota-convergence/landscape-sweep/build_args.py#L116
[openhands]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/blueprints/runtime-workers/openhands/README.md#L148-L151
[lanes]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/lanes.md#L94-L149
[old-json]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/preregistration.json
[old-build]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/preregistration.json#L38-L65
[old-client]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/preregistration.json#L943-L998
[old-client-version]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/preregistration.json#L943-L944
[cells]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/preregistration.json#L1183-L1297
[cells-d]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/preregistration.json#L1197-L1238
[cells-a]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/preregistration.json#L1239-L1296
[old-cell-prose]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/PREREGISTRATION.md#L126-L158
[old-cell-engines]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/PREREGISTRATION.md#L135-L146
[objective]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/PREREGISTRATION.md#L9-L15
[old-rule]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/preregistration.json#L3040
[gates]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/preregistration.json#L3430-L3486
[old-runner]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/PREREGISTRATION.md#L31-L112
[old-runner-choice]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/PREREGISTRATION.md#L33-L49
[old-sources]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/preregistration.json#L36-L942
[old-review]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/PREREGISTRATION.md#L387-L419
[old-checks]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/PREREGISTRATION.md#L441
[repair]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/preregistration.json#L3558
[m9]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/preregistration.json#L3724-L3731
[anti-patterns-general]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/preregistration.json#L3143-L3183
[anti-patterns-review]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/preregistration.json#L3184-L3414
[anti-patterns-late]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/blueprints/gpt6-lane-compression-ab/preregistration.json#L3415-L3428
[old-manifest]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/73fc873e1da52ac68a731d33e482a7ae0444f6b2/manifests/evidence.json#L6884-L6893
[old-ci]: https://github.com/seathatflowsinourveins/native-agent-stack/pull/431/checks
[old-validation]: https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/36353719576/job/108717193576
[github-docs]: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/checking-out-pull-requests-locally
[harbor-pin]: https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/installed/codex.py#L1339-L1449
[harbor-main]: https://github.com/harbor-framework/harbor/blob/3c82380859d187957cfd5cd64802b076d9779550/src/harbor/agents/installed/codex.py#L1502-L1605
[promptfoo-sdk]: https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/providers/openai/codex-sdk.ts#L1034-L1134
[codex-exec]: https://github.com/openai/codex/blob/36650394c5b38c2990ccf2a3457165ca3e9d9726/sdk/typescript/src/exec.ts#L91-L178
[codex-manager]: https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/models-manager/src/manager.rs#L763-L780
[codex-model-info]: https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/models-manager/src/model_info.rs#L99-L150
[codex-loader]: https://github.com/openai/codex/blob/36650394c5b38c2990ccf2a3457165ca3e9d9726/codex-rs/config/src/loader/mod.rs#L286-L340
[inspect-swe]: https://github.com/meridianlabs-ai/inspect_swe/blob/7eb8dd64309db4cd0f6bdf1d0ffd9786a74a4088/src/inspect_swe/_codex_cli/codex_cli.py#L483-L637
