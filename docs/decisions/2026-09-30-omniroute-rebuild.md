# Decision: rebuild both OmniRoute gateways on release/v3.8.51 2f42a9ac1, announce Codex 0.159.1, and enable ten of the twelve shipped compression engines on 20129 at upstream's per-engine settings (2026-09-30)

**Status: gateway build and settings selected from upstream source on 2026-09-29 and 2026-09-30, and switched on the
NativeStack WSL2 workstation on 2026-09-30 between 00:02:41Z and 00:03:00Z. The settings were applied at 00:06Z (nine
steps) and 00:43Z (one step). This change records it and touches no host.** It supersedes
[the 2026-09-27 record](2026-09-27-omniroute-account-pool.md) only where that record names the build, the pinned Codex
client version and the compression settings; the account pool, the keyless loopback posture, the Codex wiring and the
`codex/*` exclusion on 20128 stand.

**Scope:**
- new: this record; [`evidence/artifacts/omniroute-rebuild-20260930/`](../../evidence/artifacts/omniroute-rebuild-20260930/README.md)
  (receipt, the two installed units, plans, operation scripts, qualification extract, read-back, checks and probes);
  `tools/omniroute/gateway_record.py`; the values-free unit template `adoption/templates/systemd/omniroute-fw.service`.
- changed: `adoption/templates/systemd/omniroute.service` (header and the `@CODEX_CLIENT_VERSION@` semantics; the
  directives are unchanged); `tests/test_omniroute_gateway_unit.py` (both templates against their recorded units);
  `docs/foundation-stack.md` ("What runs"); `docs/decisions/2026-09-27-omniroute-account-pool.md` (one dated addendum
  line on the client version); `manifests/evidence.json` (registration of the files above through the hot-file
  protocol, in the last commit).
- not in this change: the omniroute row of `manifests/stack.json` (its `freshness` and `command_scope` text still
  describe the 2026-09-27 builds). It is a shared hot file, so changing what it says is a separate `lane:shared` change
  that needs the trading lane's acknowledgement; until it merges, this record and `docs/foundation-stack.md` are the
  current statement of the running builds. The component pin stays npm 3.8.50 either way, and there is no second row
  for the 20129 unit.
- untouched: the host; every other component's row.

Every claim carries the evidence class used in the receipt (`receipt.json`, `evidence_classes`).

## Context

- **What ran before.** Two builds of `release/v3.8.51` at `81c9b6da` (20128: `5fc47d970`; 20129: `c3fa5a15e`) since
  2026-09-29 00:42Z, and before them `a58000c7` builds. A receipt package for the `81c9b6da` build was written but never
  published; this record replaces it as the published account.
- **Selection chronology.** (2026-09-29 20:00Z) reconcile the build and token-save features against
  [OmniRoute at 2f42a9ac19d1a247ec9ce5473b790843724b3061](https://github.com/diegosouzapw/OmniRoute/commit/2f42a9ac19d1a247ec9ce5473b790843724b3061); about 22:55Z, the pi-practice session relayed the GPT-6.1 Sol route selection.
  About 00:15Z, the configuration review selected shipped compression implementations and their per-engine values;
  the applied switches below remain local choices, distinct from upstream's disabled-by-default state.
- **GPT-6.1 Sol.** Released 2026-09-29. It was absent from the gateway's live codex catalog while the gateway announced
  `CODEX_CLIENT_VERSION=0.157.1`; after 0.159.1 was announced it appeared (`cx/gpt-6.1-sol`, `codex/gpt-6.1-sol`,
  context_length 872000) and answered 200. The static registry of upstream `release/v3.8.51` (2f42a9ac1) and
  `release/v3.8.52` (a1a2dce1a) has no `gpt-6.1` entry, so the live catalog is the only source. A real Codex 0.157.1
  client is refused by the backend for that model (reported by the pi-practice session).

## Decision

1. **Target.** Upstream `release/v3.8.51` tip `2f42a9ac1` (when it was chosen no `v3.8.51` tag existed and npm latest was 3.8.50;
   both changed later that day, see item 5), frozen for the window. It is three commits past the first target `0e290809`: #15128 (the idempotency replay key is namespaced by the
   calling API key), #15145 (e2e specs) and #15147 (the pack-boot check derives its CLI token against the smoke's
   DATA_DIR). With #15147, upstream's own `check:pack-boot` runs green on both builds' tarballs (the 20129 tarball on its third attempt: see Evidence). At `0e290809` upstream's
   pack check was red on the failure #15147 fixes (seen in the scope research, not reproduced here: our first run there
   stopped earlier, on the `HUSKY=0` line our isolation put into `npm pack --json` output). No file of the three
   commits overlaps a carry.
2. **Carries.** [#13788](https://github.com/diegosouzapw/OmniRoute/pull/13788) (`/v1/alpha/search`, which Codex's
   standalone `web.run` calls) as its two upstream commits `24bbadbad` (patch-id `d6cb98ecd2c4aed3`) and `6c7990058`
   (`cbb7d8fb78ed0dcf`) on both gateways; the local affinity patch `045aa81f3` (patch-id `132ad5e91380a1d2`, "a reused
   session pin outranks OAuth session occupancy") on 20128 only. Builds: 20128 `ae5539a56` (B2 in the artifacts), 20129 `87c4c488d` (A2).
3. **Announced Codex version.** `Environment=CODEX_CLIENT_VERSION=0.159.1` as a literal in both units, while the
   installed Codex stays 0.157.1 until Gate A's grading is over. Source: `open-sse/config/codexClient.ts` and
   `src/shared/constants/codexClient.ts` are byte-identical at a58000c7 and 2f42a9ac1; `open-sse/executors/codex.ts`
   changed between them only in #15119 (the `/v1/responses` subpath), not in `buildHeaders`; the catalog query's
   `client_version` is set at `src/app/api/providers/[id]/models/discovery/codex.ts:82`. The value is used for that
   query, for the gateway's own backend calls, and for callers that report no Codex version; a Codex client that
   reports one keeps it on inference. The pi-practice session first applied it as a systemd drop-in at 22:57:27Z
   (reversible); the switch absorbed it into the unit files and removed the drop-in.
4. **Settings.** A nine-step plan (context-length override for `sharedgw/gpt-6-astra-max`, three stored context combos,
   one confinement write on 20128 (the Codex app-server flag off, T05), an interception rule, the prompt-cache
   declaration and 1200 s hop timeout on the `sharedgw` connection, fixed hop headers, and the 20129 compression
   settings) was applied first. Then one delta (T10), grounded in pinned upstream compression types and request policy,
   moved the 20129 compression settings to upstream's per-engine settings with ten of
   the twelve catalog engines enabled (headroom stays off as a defect mitigation, scoped below; omniglyph is off because it
   cannot act on GPT-6 routes). **That is not upstream's shipped state.** Upstream ships the master switch off,
   `defaultMode` off and every engine disabled (`open-sse/services/compression/types.ts:421-443` at 2f42a9ac1), and its
   documented default lane once compression is on is `[session-dedup, lite]` (`lossyRequestPolicy.ts:19`, the seeded
   "Standard Savings" combo at `src/lib/db/compressionCombos.ts:33-39`, `docs/compression/COMPRESSION_GUIDE.md:233-239`).
   Result on 20129: master ON; engines ON: session-dedup, ccr, lite, rtk (minimal), codex-responses, relevance, caveman
   (lite), aggressive, llmlingua, ultra; OFF: headroom, omniglyph. A request with no header runs the plan upstream's code
   derives from that engines map, stacked `[session-dedup, ccr, lite]` (upstream's default pipeline plus ccr, which the
   engine catalog counts as a safe default: `engineCatalog.ts`, `lossy: false`; confirmed on the live build's code path
   offline, `source=default`); there is no output style; `off` gives no engine. The lossy engines still run only when a
   request names them (an `x-omniroute-compression` header or a stored combo), which is upstream's own lossy request
   policy (`lossyRequestPolicy.ts`). 20128 was unchanged when the record was frozen: master off, `codex/*` excluded.
   Stored combos on 20129 at that time: ours from T04 (`gpt6-agent-safe`, `gpt6-memory-safe`, `gpt6-safe-lossy`), the peer-owned rows
   `allow-lossy`, `fw-ccr`, `fw-codex-responses`, `fw-headroom`, `fw-lite`, `fw-rtk` and `fw-session-dedup`, and the seeded
   `Standard Savings` `[session-dedup, lite]` (not marked default); 20128 has only `Standard Savings`. A header that names a stored
   combo selects it (`planResolution.ts:56-57` at 2f42a9ac1), so on 20129 the header `allow-lossy` selects the peer combo of that
   name, eleven engines including headroom, and not the ten engines of the engines map
   ([`checks/effective-plan-20260930.json`](../../evidence/artifacts/omniroute-rebuild-20260930/checks/effective-plan-20260930.json)).
5. **Upstream released 3.8.51 after the rebuild (checked 2026-09-30T04:53:59Z, git protocol and the npm registry; output as printed in
   `evidence/artifacts/omniroute-rebuild-20260930/checks/upstream-release-check-20260930.json`).** The annotated tag `v3.8.51`
   (tagger time 2026-09-30T01:41:23Z) points at commit `c1e30b767` "Release v3.8.51" (author time 2026-09-29T22:58:13Z, parent
   `443d66996`), and npm `omniroute@3.8.51` was published at 2026-09-30T02:54:04Z (`latest`). That commit is not a descendant of
   `2f42a9ac1`, but **its tree is the same tree**: both are `0f58d8df20c0c2ae4336b432b3f39837119b6eed`. So the running builds are the
   released 3.8.51 tree plus the carries, and no rebuild is needed for the tree. #13788 is still open upstream (its title now starts
   with `[defer]`), so the carry stays; `release/v3.8.52` (`a1a2dce1a`) exists and `main` was two commits past the tag
   (`fc5e2bccd`, Electron release fixes). The repo's component pin (`manifests/stack.json`, npm 3.8.50) is unchanged by this record: it
   is a shared hot file, and moving it needs its own qualification and change.
   **Qualification of the published package (2026-09-30, after the rebuild).** The npm package itself was installed with the recipe's commands (version changed to 3.8.51) into a
   fresh prefix and booted twice in a network-less namespace with the real `lsof` and no shim (health 200 after 3 s and 4 s, the store identical across the
   restart, SIGTERM exit 143, no orphan); the registry's SLSA provenance names upstream's `v3.8.51` tag commit `c1e30b767` and the tarball's sha512, and
   `npm audit signatures` verified 1156 of 1156 registry signatures and 233 attestations. The package has neither carry (0 alpha/search route
   files, 0 affinity-function occurrences), so it does not replace either gateway. The pin stays 3.8.50 here; the
   receipt [`omniroute-3851-npm-qualification-20260930`](../../evidence/receipts/omniroute-3851-npm-qualification-20260930.json) has the limitations, including the 7-day cooldown question for the pin move.

### How each setting relates to upstream's shipped defaults

| Setting | Class | Basis |
| --- | --- | --- |
| 20129 master switch ON (upstream ships off) | locally selected switch using the shipped implementation, not an upstream default | `types.ts:421-443`: `enabled: false`, `defaultMode: "off"`; a request with no header is compressed only while the master is on (`COMPRESSION_GUIDE.md:226`) |
| Ten of twelve engines enabled (upstream ships every engine disabled), each at upstream's per-engine values except the two mitigations below | locally selected engine set using pinned vendor values, not an upstream default | `types.ts:436`; the per-engine values (rtk minimal, caveman lite, headroom minRows 8, cacheMinutes 5, liveZone off, fuzzy false) were compared with `types.ts` by two independent reviews of this branch |
| ccr in the headerless lane (upstream's default pipeline is `[session-dedup, lite]`) | derived from our engines map | the derived plan adds every enabled engine the catalog counts as safe; ccr is lossless (`engineCatalog.ts`, `lossy: false`) |
| Codex app-server flag off on 20128 (T05) | local confinement write, plan item GC8 | upstream's default is `"true"` (`src/shared/constants/featureFlagDefinitions.ts:564-570`); no Codex connection uses the transport |
| Lossy engines only on a header or combo opt-in | upstream-native control, kept | `lossyRequestPolicy.ts` strips them from headerless requests whatever the engines map holds |
| `sessionDedup.minBlockChars` 512 (upstream 80) | mitigation of a verified upstream defect | composite-key collision overwrote an unrelated text part (chat body whose first non-system message has two or more `text` parts); reproduced offline; Responses input and string-content chat are immune |
| `lite.compressToolResults` false (upstream true) | mitigation of a verified upstream defect | head-only truncation of tool results drops error and exit tails; the current-turn guard misses Responses tool loops |
| headroom OFF in the engines map | mitigation of a verified upstream defect, scoped: it still runs where a stored combo names it | re-encodes JSON integers above 2^53 and fixed-scale decimals; a stored combo runs its pipeline as given (`strategySelector.ts:812-816`), so `gpt6-safe-lossy` (step `minRows` 16) and the peer combos `allow-lossy` and `fw-headroom` (global `minRows`, 8 since T10) still run headroom for a caller that names them |
| omniglyph OFF | selected from the pi-practice session's upstream image-transport comparison | inert on GPT-6: skipped for every GPT-6 route (`imageTransportPolicy.ts:17-33`; PLAN.md) |
| contextBudget off | upstream default | escalation overrides an explicit `off` (reproduced) |
| headerless plan `[ccr]` only, output style `terse-prose:lite`, liveZone on | local scoping without an upstream basis, removed on 2026-09-30 | measured on our own fixtures, not an upstream-documented defect; the screen's finding that lite folds whitespace in code-bearing text was confirmed again on 2026-09-30 and is a residual below, not a removed-with-the-scoping claim |
| 20128: master off, `codex/*` excluded | local setting from 2026-09-27, upstream default is also `enabled: false` | open user decision below |

## Non-upstream deltas

| Delta | Where | Purpose | Retire when |
| --- | --- | --- | --- |
| #13788 (two commits) | both builds | `/v1/alpha/search` for Codex `web.run` | a release carries it (open upstream PR at the time of writing) |
| affinity patch `045aa81f3` | 20128 | keeps a reused session pin ahead of OAuth occupancy | upstream ships an equivalent |
| upstream PR 15167 (`f5d8e150b`, one commit) | 20128 | `gpt-6.1-sol` in the Codex registry and both alias sets, so `max` and the `-max` suffix reach the wire | a release carries it (open upstream PR at the time of writing) |
| `lsof` shim v2 (`b6ae900224df3dc7`) | 20128's new prefix | keeps a client's dead connection from blocking a restart (upstream's bind-probe fallback becomes the preflight guard) | upstream's preflight counts only listeners |
| `lsof` shim on `PATH` | both units | port preflight on a free port | redundant now: upstream #14812 (`8183e9b79`, `resolveServeBusyPids`) is in 2f42a9ac1; drop at the next rebuild after a free-port start passes without it |
| settings above (512, `compressToolResults` false, headroom off in the engines map) | 20129 | defect mitigations | upstream fixes the defects |

While the affinity patch runs, create no OAuth (Codex) routing combo on 20128, nor (extended 2026-10-05, `2026-10-05-omniroute-gateway-composition.md`) on 21128 and 21129 for as long as the composition runs there (standing constraint F1, the same rule as
in `docs/foundation-stack.md`). Basis: the patch changes what the combo availability check does to session pins (its
commit message, on `chat.ts:1096-1108`: the check "passes no reserveOAuthSession, and the dispatch reuses the pin it
writes"); its regression test (e) covers that path with a fixture only, and no routing combo over Codex accounts has
been run on the patched build, so the constraint is conservative. F1 was set when the patch was first built (the
`81c9b6da` package, never published); this record and `docs/foundation-stack.md` are its published statement.

## Evidence

Receipt and index: [`evidence/artifacts/omniroute-rebuild-20260930/`](../../evidence/artifacts/omniroute-rebuild-20260930/README.md).
Classes are kept apart.
- **Unchanged upstream checks.** `check:pack-artifact` rc 0 on both builds; `check:pack-boot` rc 0 on both ("the packed
  tarball boots AND persists"; the 20129 tarball on its third attempt); the upstream `test:unit` on the pristine tip and on the 20128 build (44,863 tests, 14
  failing at the pristine tip: the models.dev live-API, remote-image-fetch and pindns tests need network, which our
  namespace lacks, and the remaining failures are not classified; 44,824 tests, 18 failing on the 20128 build).
- **Our integration checks.** Boot smoke on both installed prefixes (health 200 in 3-4 s, clean stop); 69/69 and 62/62
  targeted tests; classification of the four failures only the 20128 build shows: one introduced by the #13788 carry
  (`hard-session-lease-bypass-inventory` lists the new `alpha/search` route; the carry has no test update), two that
  fail only when a built `dist/` exists in the worktree (they pass with `dist/` moved aside and in the unbuilt pristine
  tree), one timing flake (passes alone). The two failed `check:pack-boot` attempts on the 20129 build (A2) and the third,
  passing attempt on other CPUs are retained. Their causes are not established: attempt 1 reported its random port already in use
  by an unidentified process, and attempt 2 booted healthy and then failed on 30 s outbound timeouts while our pristine-tree
  suite ran on the same CPUs at load about 40. The result is "passes on the third attempt".
- **The 39 fewer results in the 20128 full run.** Accounted for, by name: the pristine run printed 41 more result lines than the
  20128 run (46,815 against 46,774; 39 tests and 2 suites), which is the 115 lines only it printed, less 57 lines only the 20128 run
  printed, less 17 lines that are the carries' own tests (10 in `issue-8674-alpha-search.test.ts`, 7 in
  `affinity-outranks-occupancy-8940.test.ts`) and exist only in the 20128 tree. The other 172 lines (115 and 57) are results that
  one of the two full runs did not print, across 18 test files, 0 unmapped; we attribute them to upstream's `--test-force-exit`
  (an observed effect of that flag on other files, not isolated for these). Run alone without the flag, in two batches (11 and 7
  files) per tree, those 18 files print identical names on both trees: 654 result lines, 0 failing, on each. The trees are not
  identical apart from the carries: the 20128 tree was built in place (`dist/`, 31 regenerated tracked files under
  `bin/cli/api-commands`, 94 untracked build outputs) and the pristine tree is unbuilt. The reruns are in
  [`qualification-extract.json`](../../evidence/artifacts/omniroute-rebuild-20260930/qualification-extract.json),
  `full_suite_reconciliation`.
- **Live model calls (one synthetic payload each, not savings figures).** After the switch: `cx/gpt-6-sol` 200,
  `cx/gpt-6.1-sol` 200 (served `gpt-6.1-sol`), a made-up id 400, a request with UA `codex_exec/0.157.1` and
  `Version: 0.157.1` 200 with all nine `response.*` event types parsed; `sharedgw/cx/gpt-6.1-sol` 200 through 20129.
  After the delta: a repeated read in history, headerless, 2712 to 1464 prompt tokens (chat) and 2675 to 1427
  (Responses); a 480-line retry loop with `gpt6-agent-safe` 8573 to 1745; every answer correct. The payloads were log
  and read-back text, not diffs or edits (see the lite residual below); their input sizes, 595 to 8,573 tokens, are in
  `qualification-extract.json` (`token_effect_synthetic`).
- **Provenance of the operation scripts.** T01-T09 (00:05:57Z-00:06:17Z) ran through `gateway_apply.py` as it stood at
  00:05:53Z, and its `plan.json` and `post_apply_checks.py` of that time; those versions are **not retained** (no script
  digest was logged). The published `scripts/*.txt` and `plan.json.txt` are later text: a design workflow's fix stage
  rewrote `gateway_apply.py` at 00:33:23Z, edited it five times between 00:43:06Z and 00:43:19Z
  (transport-error handling), rewrote `post_apply_checks.py` at 00:40:42Z and edited `plan.json` and
  `test_gateway_apply.py` until 00:45:44Z. **T10, the delta (dry run 00:43:38Z, apply 00:43:52Z), ran through that
  unreviewed edit of the applier**, 19 s to 33 s after its last write; the offline module ran on it at 00:46:17Z (20
  tests, OK). `plan-delta.json` was built by the coordinator at 00:43:32Z from T09's step and the pi-practice session's
  `delta-20260930-upstream-defaults.json`. Read-backs against the consuming gateway, not the scripts' text, are the
  evidence for T01-T10; they are values-free per-step records under `apply-logs/`.
- **The applier's checks, as printed.** At 00:05:47Z `post_apply_checks.py --phase pre`: `checks=36 failed=0`. At
  00:06:17Z `gateway_apply.py plan.json --verify`: T01-T09 `OK`, exit 0, and `--phase post`: `checks=36 failed=0`. At
  00:44:04Z `gateway_apply.py plan-delta.json --verify` after the delta: T10 `OK`, exit 0. These are transcribed from the
  coordinator session's record of the returned results, with the command text as typed (their own `tail`, `cut` and `head`
  shortened the output; times are UTC except the host-local `ls` columns of section D), in
  [`checks/recorded-outputs.txt`](../../evidence/artifacts/omniroute-rebuild-20260930/checks/recorded-outputs.txt). The
  current `post_apply_checks.py` no longer reproduces them: its `post` phase encodes T01-T15, including drafts that were
  never applied, and its later phases encode the superseded T09 settings. The negative controls for `--verify` and for a
  failed read-back are the offline module's `test_verify_detects_drift` and
  `test_failed_readback_rolls_back_exactly_and_stops`; they run against the applier as it stands, not against the
  unretained version that printed the T01-T09 results.
- **Owner record for Gate A.** [`tools/omniroute/gateway_record.py`](../../tools/omniroute/gateway_record.py) prints unit
  hashes, drop-ins, `MainPID`, `NRestarts`, `BUILD_SHA`, three route digests and the sorted override rows as JSON,
  read-only. The Gate A owner runs it at each window start and end; a window is void when a unit hash, a drop-in, the
  process identity, the build, or the compression, combos or resilience digest changes, or an override row present at
  the start changes or disappears (a new automatic row is informational: the gateway's own reconciler writes them). The reported Gate A
  freeze of the record taken at 00:48:58Z has no retained artifact proof here and is not independently established by this record. A
  fresh record taken while this record was reviewed equals the published copy on every path that both carry but `taken_utc`,
  with the digests compared in full and `exec_main_start` compared after converting the host's local-time string to UTC (the
  published copy shows UTC):
  [`checks/recorded-outputs.txt`](../../evidence/artifacts/omniroute-rebuild-20260930/checks/recorded-outputs.txt), section F (its
  time and counts). The record cannot see what T05-T08 wrote (20128's digests did not change across T05).

## Rollback

- **Units.** The prior unit files and the drop-in text were saved in a private switch directory; restore them, run
  `systemctl --user daemon-reload`, restart 20129, restart `hindsight-live.service`, then 20128 (the port preflight
  counts a client socket in CLOSE_WAIT as the port's owner).
- **Stores.** The switch applied three migrations (190 to 193 rows in `_omniroute_migrations`) that repointing a unit does
  not undo. Verified SQLite online-backup copies of both stores (integrity_check ok) were taken at 2026-09-30T00:02:33Z;
  to go back, stop the unit, restore the copy, delete the stale WAL and SHM files, start. A restore discards everything
  written since: the T01-T10 settings, usage logs, and any OAuth tokens the gateway rotated; a restored stale refresh
  token can force a native re-sign-in.
- **Settings.** Each apply step captured its keys first and carries a rollback; `gateway_apply.py --rollback` restores
  the captured values. Two caveats from the plan (PLAN.md, residual risks): a rollback writes back prior values for keys
  that had no row, so a GET is identical afterwards but exact row absence returns only from the store copy, and T01's
  rollback check compares the whole override list including `refreshedAt`, so a concurrent refresh can print
  NOT-VERIFIED after a correct restore. No live rollback has been run; only the offline module exercises it. The delta's
  rollback restores the nine-step state.

## Alternatives considered

- **Keep the `0e290809` builds** (built, installed, smoke-tested). Rejected: upstream's pack check was red on that
  commit until #15147 and #15128 was missing; three small commits were cheaper than carrying a known red.
- **Wait for a `v3.8.51` tag.** Rejected: no date; the tip is what the gateway would be rebuilt from anyway (the tag came at
  2026-09-30T01:41Z with the same tree as the tip, so waiting would have cost a day for the same code).
- **Keep `CODEX_CLIENT_VERSION` as the installed Codex version.** Rejected for now: it hides a model released after the
  installed client; the literal is one line in the unit and reverts with one edit.
- **Headerless `[ccr]` only** (the first plan, from our fixtures). Superseded by the pinned upstream request policy.
- **Compression on 20128.** Not applied; see below.

## Update 2026-09-30, 06:32Z: 20128 carries upstream PR 15167 (gpt-6.1-sol at max)

**Why.** The rebuild's residual said `max` clamps to `xhigh` for `gpt-6.1-sol`. The live cost was measured before the restart: 1154 of 1495 `gpt-6.1-sol`
rows since 00:00Z had `max` requested and `xhigh` sent ([`checks/calllog-effort-counts-before-switch.json`](../../evidence/artifacts/omniroute-sol-max-20260930/checks/calllog-effort-counts-before-switch.json)),
native Codex callers included, and the `-max` suffix of the new base was an unknown model id (HTTP 400 with the prefix, 401 without it). Preserve requested max effort for GPT-6.1 Sol
through the vendor effort normalization change below; this selection is separate from a task-quality comparison.

**Source.** Upstream PR [#15167](https://github.com/diegosouzapw/OmniRoute/pull/15167), head `f5d8e150b79e0901fa18241c7f29bff889b87c14`, one commit, 5 files +23/-0 on release/v3.8.52 (same practice as
the #13788 carry: a cited upstream change, no self-written patch). It applies cleanly, its stable patch-id equals the cherry-pick's, and its registry entries use the capabilities
block whose context (872000) equals the live catalog's. Codex 0.159.2's bundled catalog lists `max` for `gpt-6.1-sol`.

**Decision.** Carry it on 20128 only. The clamp and the suffix parser are in the Codex executor, which runs only on 20128; 20129's sharedgw node forwards to it. One restart, no
hindsight-live restart, 20129 unchanged (the Gate A owner's conditions). Alternatives: both builds (a second restart for no effect); wait for a release (upstream's release/v3.8.52 and
main lack it); use the body effort only (`max` in the body is the clamped path, the defect itself; the suffix ids `-max` and `-xhigh` were rejected with HTTP 400 before the carry).

**A hazard found on the way, and its fix in the new prefix only.** `omniroute serve` refuses to start while any client holds a dead connection to its port: its preflight runs
`lsof -ti :PORT`, which lists client sockets, and hindsight-api held such a CLOSE-WAIT socket to 20128 (this is why the 00:02Z switch restarted hindsight-live). Upstream main and
release/v3.8.52 still do it. Shim v2 (`b6ae900224df3dc73fff2a50b3d7206d78895c6147e93e80b62e66d423e69854`; v1 was `b12c64614c54bc86...`) answers that one query with exit status 2, which upstream's own fallback for an unusable discovery tool
(`resolveServeBusyPids`, #14518) turns into a bind probe. Tests with kept outputs: control with shim v1, real `omniroute serve` of the candidate prefix: restart refused; shim v2: same restart
reaches health in 5 s; a second real instance is still refused. The previous prefix and 20129's prefix keep v1 (residual).

**Applied.** 2026-09-30T06:32:50Z, `switch_gateways.py --only 20128`: three unit lines changed (Description, the PATH shim segment, ExecStart), MainPID 950031 to 3262255, 20129 and hindsight-live
untouched, no settings write, rollback copy in the switch directory. Probe gate before and after: `gpt-6.1-sol` with body `max` went from `xhigh` to `max` upstream, the suffix ids and the
bare id answer 200 with the right effort, astra stays `max`, a 0.157.1 client request answers 200. The gateway's context-window reconciler removed one automatic override row on restart
(same 872000 now in the registry). Everything is in [`evidence/artifacts/omniroute-sol-max-20260930/`](../../evidence/artifacts/omniroute-sol-max-20260930/receipt.json).

**Also recorded.** The sharedgw connection expiry of 05:50Z to 05:55Z (claim C9): my baseline probe sent `sharedgw/gpt-6.1-sol-max` before the carry; 20128 answered 401 and 20129 parked the node's
only connection as expired for all callers until the dashboard's Test connection restored it. Upstream has no fix; the probe script now sends a lane request only after the bare id answered 200.

## Update 2026-10-05, 20:12Z: the serve supervisor drops the server child's console output unless `--log` or `OMNIROUTE_SHOW_LOG=1` is set

`bin/cli/runtime/processSupervisor.mjs` (blob-identical in release/v3.8.52 `23a114848`) starts the server with `stdio: showLog ? "inherit" : ["ignore", "pipe", "pipe"]`, where `showLog` is `OMNIROUTE_SHOW_LOG === "1"` (the `--log` option of `omniroute serve`).
Without it the child's output is drained into an in-memory ring of the last 50 lines, printed when the child exits and is restarted or given up (`dumpCrashLog`) or when a readiness timeout asks for it (`getRecentLog`, `serve.mjs`); only a `[STARTUP] Fatal:` boot diagnostic and the Android
instrumentation-hook hint are printed at once. The server has no console capture into its application log, so a `console.error` of the running server such as `[callLogs] Failed to save call log` reaches neither journald nor `app.log`. Both units (`omniroute.service` for 20128, `omniroute-fw.service` for 20129) now carry a drop-in `Environment=OMNIROUTE_SHOW_LOG=1` (`~/.config/systemd/user/<unit>.d/show-log.conf`), applied by restarting 20129 at 20:12:04Z and
20128 at 20:12:12Z (both healthy at once, 5f's GPT lane told beforehand, a live streaming request logged afterwards). Rollback: remove the two drop-ins, `systemctl --user daemon-reload`, restart 20129 then 20128. Found while diagnosing the missing call-log
rows on 2604; their cause is in `2026-10-05-omniroute-gateway-composition.md` (update of the evening).

## Comparison that would overturn it

- The tip's `check:pack-boot` or a later unit run shows a defect the carries cause; then rebuild without the carry.
- Upstream merges #13788 into a release or `main`: drop the carry. Upstream ships an equivalent of the affinity patch:
  drop it. Upstream fixes the session-dedup key collision, the integer re-encoding or the Responses tool-loop truncation:
  restore the upstream default of the matching setting (80, headroom on, `compressToolResults` true).
- Upstream merges PR 15167 into a release: drop that carry (20128 carries it since 2026-09-30T06:32:50Z).
- A measured drop of the cache-read share on 20128 traffic that arrives through the `sharedgw` hop (baseline 93.8% over
  573 rows, reported by the pi-practice session, not reproduced here) after headerless dedup, beyond what the user accepts.
- A first-time `apply_patch` failure, or another exact-match failure, traced to lite's whitespace folding on traffic through either
  gateway: turn lite off (one engine toggle in the stored engines map).

## Limitations and residuals

- **Open qualification gate.** (a) Compression on 20128 (the Codex lane itself; it would rewrite real Codex CLI traffic).
  The 2026-09-30 review at about 02:25Z retained a conditional selection: use the shipped request policy only after
  a matched run shows a reproduced saving on real traffic and no output regression, including exact tool-text checks.
  It is **not applied**. The pi-practice session's 3-arm measurement the same morning
  (reported, not reproduced here: four identical Codex 0.159.2 jobs per arm on gpt-6.1-sol with web search and MCP; direct
  20128, via 20129 with the header off, via 20129 on the headerless lane) found 0 compressed tokens in all 115 joined rows,
  a cache-read share of 0.906, 0.902 and 0.896, per-proposal vote agreement 25/31, 26/31 and 28/31 between the arm pairs (the
  route-to-route noise), and 9 of 9 first-try `apply_patch` hunks across two blank context lines in all three routes.
  The lane never fired on that traffic (GPT-6 Codex sessions send tool output as content-part arrays, which lite does
  not rewrite), so the saving condition is not met. A fourth arm with the lossy combo header (`gpt6-safe-lossy`, through 20129)
  saved 0.36% of the input over 55 rows, with vote agreement of 26/31, 27/31 and 24/31 against 25/31 for the two uncompressed
  routes (the noise), and 3 of 3 first-try patches (reported, not reproduced here). An offline run of the gateway's own compression
  step on eight of those jobs' real request bodies (counts only,
  [`checks/real-codex-bodies-lane-probe-20260930.json`](../../evidence/artifacts/omniroute-rebuild-20260930/checks/real-codex-bodies-lane-probe-20260930.json))
  agrees: the headerless lane changed 0 items of 60 to 78 per body, and the lossy lane saved 0.34% (908 of 265,483 tokens)
  while, by our regex count, losing 47 file-path occurrences, 1 hex id and 1 error line, and the gateway's own validation printed
  'inline code changed or missing' in all four. So neither lane meets the condition (a reproduced saving with no exact value
  lost) on real Codex traffic; the lever that pays there is the prompt cache (share about 0.90). Untested: string-shaped shell
  outputs of older models and very long sessions with large tool outputs. The Gate A owner's stated preference is off through the
  windows, and any change must land at least 6 h before the seal announcement with a new owner record. (b) `blockedProviders` and `noAuthFallbackDisabledProviders`,
  which the apply contract cannot read back.
- `max` effort on `gpt-6.1-sol` clamped to `xhigh` on the rebuild (static alias sets in `reasoningSuffix.ts`); 20128 carries upstream PR 15167
  since 2026-09-30T06:32:50Z and sends `max` (update below); 20129 forwards and never had the clamp.
- The live canary of the token-save settings (12 requests) waits for Codex capacity (2026-10-04T00:35Z); the output style
  it would have measured is now off. The cache-share effect of headerless dedup is unmeasured until the pi runs report.
- The Opus review of the first plan returned twelve defects (three medium); the workflow was stopped in its fix stage,
  and its partial edits to the applier (transport errors; 20 offline tests pass) and to the check script are in the
  artifacts as they are. Its drafted steps for 20128 and for an output-mode flag were not applied.
- The full-suite totals differ by 39 between the pristine-tip and the 20128 run; the difference is accounted for above
  (17 carry tests; results lost under `--test-force-exit`, identical when the files run alone). Upstream's e2e and
  integration suites were not run, and the security-relevant files that lost their results in the 20128 full run
  (`security/live-server-allowlist`, `private-host-special-ranges`, `route-guard-cli-tools-settings-local-only`) were
  run alone on that build only in the reruns above.
- **lite folds whitespace in code-bearing text (verified 2026-09-30, live build's code path, no model).**
  `open-sse/services/compression/lite.ts:50-53` replaces three or more newlines with two and strips trailing spaces and
  tabs on every line of a message whose content is a string. On a Codex-shaped Responses body (its tool outputs are plain strings, the shape of older models' shell calls; the
  pi-practice session reports that 625 of 625 tool outputs and 300 of 300 messages in its real Codex 0.159.2 sessions on GPT-6 are
  content-part arrays, not reproduced here) it changed the
  `function_call_output` of `shell` and `shell_command` calls (a file with PEP8 double blank lines lost one blank line per
  pair, 9 to 5 blank lines, and its trailing spaces) and left `apply_patch` calls and message items with parts arrays
  untouched; a dry-run POST to 20129's `/api/compression/preview` showed the same on a unified diff, a fenced code block
  and a tool-result diff, with tabs and in-line double spaces preserved. Upstream's Codex eligibility guard is read only
  by the codex-responses engine (`engines/codexResponses/index.ts:251,281`), so it does not shield shell outputs from lite.
  lite is part of upstream's own default lane, and its measured saving here is small (192 of 413,153 input tokens
  across 28 real pi tasks on 20129, reported by the pi-practice session), but a hunk whose context spans two blank lines
  written from a folded view may not apply. The earlier plan screen (`PLAN.md`) recorded the same risk and moved lite to
  opt-in; the pinned upstream-policy delta put it back. Untested: an actual `apply_patch` round trip through the lane.
- **headroom and the stored combos.** headroom is off in the engines map, yet `gpt6-safe-lossy` (ours, step `minRows` 16; its
  description says it can round large-JSON numbers) and the peer combos `allow-lossy` and `fw-headroom` (global `minRows`, 8 since
  T10) run it for a caller that names them, with the integer and decimal re-encoding the mitigation is about. Restoring `minRows`
  16 globally, or dropping headroom from those combos, would narrow it; both are gateway writes that need the Gate A owner's
  timing (and the peers' consent for their rows), so this record does not make them.
- **The applier's secret-route guard is narrower than the gateway's anonymous surface.** `gateway_apply.py` refuses to retain a GET body of
  `/api/settings`, `/api/providers*` or `/api/keys*` unless the capture names the non-secret paths to keep (its `SECRET_GET` pattern),
  and `post_apply_checks.py` forbids those three families and `/api/settings/cache-config`. Session 88's source read of both builds
  (blob-identical to upstream `2f42a9ac1` for the 25 files it cited; nothing was called) found credentials also on
  `/api/settings/cache-config`, `/api/sync/*` and `/api/cli-tools/keys` while `requireLogin` is false (the keyless loopback posture of
  the 2026-09-27 record). The plans here read `/api/providers/<connection id>` only through `keep` lists of named non-secret paths,
  and name none of the three routes 88 lists; the owner record reads four non-secret routes. A future plan that reads more must extend
  the guard first. That surface, and what to do about it, are session 88's decision with the Gate A owner, not this record's.
- The context-window reconciler rewrites automatic override rows without any write, so the raw overrides route digest
  drifts; the owner record uses the sorted rows without `refreshedAt`.
