# Decision: the NativeStack gateways keep true GPT-6.1 Sol max: published v3.8.51 content plus upstream #15167 and the cited affinity patch, not the published-only package (2026-10-05)

Lane: shared. North-star action served: the GPT lane runs GPT-6.1 Sol and GPT-6 Astra at max through the gateway for engineering and US-equities research, with prompt-cache hits kept.
Status: no change to a running gateway. A swap to the published `omniroute@3.8.51` was planned for 15:00Z and cancelled before any unit changed; this record states what runs, why it stays,
and when each carried change goes. Evidence: `evidence/artifacts/omniroute-wire-effort-20261005/`.

## Decision

Keep the composition that runs on 20128 (the Codex lane's gateway). 20129 (`omniroute-fw`, framework-only, no Codex accounts of its own) runs the published content plus #13788 only and is unchanged:

| Part | Commit | What it does | Why it stays | Removal or re-pin condition |
| --- | --- | --- | --- | --- |
| Base: upstream `release/v3.8.51` | `2f42a9ac19d1a247ec9ce5473b790843724b3061`, tree `0f58d8df20c0c2ae4336b432b3f39837119b6eed` | the released content: the tree equals the tree of the `v3.8.51` tag commit `c1e30b7676975feb298b49eff6ff58923c04b89e` (`git diff` is empty; the commits differ: the tag commit's parent is `443d66996`) and so the content of npm `omniroute@3.8.51` (published 2026-09-30T02:54Z, `dist/BUILD_SHA` `c1e30b7`) | it is the published release | the next official release that carries the two parts below |
| Upstream PR 15167 | head `0585aba5589d5a1f49243a13a8db249558e7c9e3` (GitHub `refs/pull/15167/head`, read 2026-10-05); the running 20128 build carries the PR's earlier head `f5d8e150b79e0901fa18241c7f29bff889b87c14` (recorded in `2026-09-30-omniroute-rebuild.md`), and the build kept for the second host carries `0585aba55` | adds `gpt-6.1-sol` to the Codex registry and both alias sets: the `-max`, `-ultra` suffixes split to the base model, and `max` is allowed for Sol | without it `cx/gpt-6.1-sol-max` is not recognised and `max` clamps to `xhigh` (evidence below) | **re-pin trigger: the first official release that carries it**, with `max` observed upstream by the probe and the live columns below |
| Local session-affinity patch | `045aa81f30cb9a1fc4f6b426ed940c1956cceda2` (cited glue, authored here; the commit is on no GitHub ref, so its `git format-patch` is published as `evidence/artifacts/omniroute-wire-effort-20261005/patches/045aa81f3.patch`, sha256 `e1006768090218fdac18edb0f9732e9e2ef892fbbadfb7aa8afc8e96e4993c69`) | a reused session pin outranks the OAuth session-occupancy re-pick (`getProviderCredentials`, `selectSessionAffinityConnection`); the published code lets that re-pick replace a pinned account, which upstream issue #8939 and PR #8940 say must not happen (open PR #13102 is the related flag-and-skip) | the Codex lane pools 7 OAuth accounts at a 93.2% prompt-cache share, and the cache is held per account (the premise of #8939), so a pin that moves loses it | **removal condition: upstream makes a reused pin outrank occupancy** (check: `tests/unit/affinity-outranks-occupancy-8940.test.ts`, the patch's own test, passes on the candidate release without the patch) |
| Upstream PR 13788 | two commits, `24bbadbad15eec0d598c908416e4b01be4e37671` and the head `6c7990058c4ce9677de79452c8cefb10b4bf1b3d` (GitHub `refs/pull/13788/head`, read 2026-10-05); the running builds carry local cherry-picks of both with the same patch-ids (`b9f0d76eb`, `dd6e9607e` and `46c77c83b`, `c3fa5a15e` are two such sets in the kept carry bundle) | `/v1/alpha/search` for Codex native web search | no request to any `/alpha` path exists in the store (0 calls, all time); it is harmless | drop it at the next rebuild (no rebuild now); the PR is open upstream |

The running build ids are `cf6748d04` (20128) and `87c4c488d` (20129).

**Reproducing the composition from public refs.** Apply `patches/045aa81f3.patch` to the `v3.8.51` tag commit (tree `cdbac0178bb18f5043f9cdaf7f90d540595e9061`, the tree of the cherry-pick `e14d1e8e0`), then PR 15167's
commit `0585aba55` (tree `f1336dfd6c8ebd81586dd6c71e7ef668ef8c949f`, the tree of `5f4b3d577`; `checks/composition-trees.txt`), then build with upstream's scripts (`checks/build-notes.txt`). That build exists: tarball
`omniroute-3.8.51.tgz`, sha256 `d3fda90c297ed1ecbaa82ca42298735ce0b393db9a07bad0b4b79efce118ebe2` (131 MiB), `dist/BUILD_SHA` `5f4b3d577`, kept on the workstation (it is not in the repository) so the second host installs the same bytes.
The 2604 gateways (21128/21129) take that tarball after #713; it carries #15167 and the affinity patch and not #13788, so both hosts deliver max.

## Context: the user's choices (relayed by the command center; the writing session heard none of them)

At 2026-10-05T13:22:24Z the user picked the option "Published 3.8.51 (Recommended)" in a choice that, as the command center relayed it, called the running build "release/v3.8.52 plus PRs 13788 and 15167" and named only the
`xhigh` limit as its cost. The running build is `release/v3.8.51`-based and also carries the affinity patch; this session read the facts below and asked for a choice among A (published only),
B (published plus the affinity patch) and C (keep). The user picked "Published + affinity patch (Recommended)" and then, in the command center's verbatim relay: "we need highest quality resolution
and interms ofthe never rebuilt rule, never build with sota reference and evidances, in this case we have them so our actions is not gated and the sota resolution is needed for seamless workflow".
Read with its context, the never-rebuild rule forbids building without SOTA references and evidence; here each carried change is a cited upstream PR or cited glue with a removal condition, so the
current composition is allowed and max quality is wanted. The relay is the basis of this record and the user may withdraw it.

## What the published-only swap would have changed (read-only measurements, 2026-10-05)

Last 7 days of `/v1/responses` on 20128 (`checks/usage-7d.json`): 20,371 successful calls, 1,576,063,034 input tokens, 93.2% of them cache reads, 7 connections at 92.5-93.8% each.
- #13788: 0 calls ever on any `/alpha` path.
- #15167: 4,423 calls (21.7%) use `-max` or `-ultra` model names; 3,131 of them are Sol names (`gpt-6.1-sol-max` 3,124, `-ultra` 5, `-xhigh` 1, `-high` 1), whose suffix split exists only with #15167.
  The 1,294 Astra names are unaffected.
- Affinity patch: the cache effect of removing it was not measured, because the patched or unpatched alternative was never deployed; the patch (two source files, 72 changed lines) is `checks/affinity-patch-source.diff`.

## Evidence that #15167 delivers max on the wire

1. **The live call log, a before/after at the restart of 2026-09-30T06:32:50Z onto the build with #15167** (`checks/live-effort.json`; the effort in the provider request the attempt captured, rows with
   encrypted reasoning only): `gpt-6.1-sol` requested `max`: upstream `xhigh` in 1,165 rows from 2026-09-30T00:47Z to 06:29Z, upstream `max` in 7,550 rows from 06:33Z to 2026-10-05T06:02Z, and no
   `max` to `xhigh` row after 06:29:46Z. `gpt-6.1-sol-max` requested `max`: upstream `max` in 2,728 rows (09-30T17:14Z to 10-05T14:09Z, including two fresh probe rows at 14:07-14:10Z; a client `low` is
   overridden to `max` by the suffix in 34 rows); `gpt-6.1-sol-ultra`: upstream `max` (5 rows); Astra `max`: `max`. The stored client request of the 19 fresh probe calls carries `reasoning.effort` `max`.
2. **The executor's upstream body, with and without the PR** (`checks/wire-probe-*.txt`; `transformRequest` on the tag plus the affinity patch, with and without `0585aba55`):

   | request | with #15167: wire model, effort | without #15167 (published behaviour) |
   | --- | --- | --- |
   | `gpt-6.1-sol-max`, client `max` | `gpt-6.1-sol`, `max` | `gpt-6.1-sol-max` (not split), `xhigh` |
   | `gpt-6.1-sol-max`, no client effort | `gpt-6.1-sol`, `max` | `gpt-6.1-sol-max`, `medium` |
   | `gpt-6.1-sol`, client `max` | `gpt-6.1-sol`, `max` | `gpt-6.1-sol`, `xhigh` |
   | `gpt-6.1-sol`, client `xhigh` | `gpt-6.1-sol`, `xhigh` | `gpt-6.1-sol`, `xhigh` |
   | `gpt-6.1-sol-ultra` | `gpt-6.1-sol`, `max` | `gpt-6.1-sol-ultra`, `medium` |
   | `gpt-6-astra-max` / `gpt-6-astra`, client `max` (controls) | `gpt-6-astra`, `max` | `gpt-6-astra`, `max` |

   So the published-only package would not merely clamp to `xhigh`: it would send the unknown model name `gpt-6.1-sol-max` upstream and break the `cx/gpt-6.1-sol-max` route, the SDK worker's
   default. (An earlier executor-level record on the 2026-09-30 builds, `evidence/artifacts/omniroute-sol-max-20260930/checks/effort-wire-*.json`, shows the same effort mapping.)
3. **The deployed code is the probed code** (`checks/source-identity.json`): `open-sse/executors/codex.ts`, `codex/reasoningSuffix.ts`, the Codex registry and `codexFastTier.ts` of the 20128 prefix are byte-identical to the
   probe tree; the live compiled bundle has 40 files with the literal `gpt-6.1-sol` and 8 with `pickMoreAvailableOAuthPeer`, the clean npm bundle has 0 and 0.
4. Two builds with upstream's own release scripts, neither deployed (`checks/build-notes.txt`): alternative B (the tag plus the affinity patch, `e14d1e8e0`) and the composition (the tag, the patch and #15167: `5f4b3d577`,
   tree `f1336dfd6c8ebd81586dd6c71e7ef668ef8c949f`). For both, `build:release`, `OMNIROUTE_ALLOW_CANARY_BUILD=1 npm run check:pack-artifact` and `npm pack` exit 0, and upstream's `npm run check:pack-boot` installs the packed
   tarball into a clean prefix, boots it and proves disk persistence (exit 0). The composition's first `check:pack-boot` run failed before any request because the script's random port was already held by another process; its rerun
   passed (both are in the notes). `check:pack-boot` boots its own pack of the tree; a fresh `npm pack --dry-run` of that tree reproduces the kept tarball exactly (same sha1 and sha512 integrity, size 137,823,643 bytes, 26,762 entries), so the kept file is the packed content that was booted.
   B's patch test passes (7 of 7), and the clean npm package and B boot on a scratch port with an empty data directory. B's artifacts were deleted; the composition's tarball is kept.

## Alternatives

(A) Published `omniroute@3.8.51` only: cancelled; it breaks the Sol `-max`/`-ultra` names, lowers every Sol `max` to `xhigh` and drops the affinity patch. (B) Published plus the affinity patch: built and
qualified, not deployed; it still lacks #15167. (C) Keep the running composition: chosen. A rebuild on the published content without #13788 is deferred to the next re-pin on the first host; that build exists as the kept tarball and goes to the second host. Native Codex still delivers Sol max
without the gateway.

## Limits

The upstream-effort column comes from the provider request the attempt captured and is NULL where the response had no encrypted reasoning (1,643 `gpt-6.1-sol` and 881 `gpt-6.1-sol-max` rows of the week); whether
the backend applies `max` is not observable from our side; the gateway's pipeline capture is off and was left off. The probe applies the PR's head of 2026-10-05 (`0585aba55`) to the tag, while the running build carries the
PR's head of 2026-09-30 (`f5d8e150b`) on its own base; the five files compared are identical except the pricing constants (`src/shared/constants/pricing/oauth-subscriptions.ts`, 11 lines), which do not touch the wire.
The cache cost of dropping the affinity patch is unmeasured.

## Overturn

Move to an official release when one carries #15167, then re-run `wire-probe.mts` on it and the live columns (the published tree must produce `max` for `gpt-6.1-sol-max` and for `gpt-6.1-sol` with client `max`).
Drop the affinity patch when upstream fixes the interplay (its own test passes without the patch). Drop #13788 at the next rebuild or when it merges.

## SOTA sources

- OmniRoute upstream, https://github.com/diegosouzapw/OmniRoute: tag `v3.8.51` (commit `c1e30b7676975feb298b49eff6ff58923c04b89e`, tree `0f58d8df20c0c2ae4336b432b3f39837119b6eed`), `release/v3.8.51` at `2f42a9ac19d1a247ec9ce5473b790843724b3061`;
  PR 15167 (`0585aba5589d5a1f49243a13a8db249558e7c9e3`), PR 13788, PR 8940 and issue 8939, open PR 13102; the executor `open-sse/executors/codex.ts` (`clampEffort`, `transformRequest`), `open-sse/executors/codex/reasoningSuffix.ts`;
  npm metadata for `omniroute@3.8.51` (integrity `sha512-VwwSt+bP9lJiPJXFJMz0nNGGuoewPZU3nFe1SLuO11ADgdSwTegGCxhg8Ov75+31m/cocPxHiO63zygn1XQ0MQ==`).
- The earlier records: `docs/decisions/2026-09-30-omniroute-rebuild.md` (the carry practice and the 09-30 update for #15167), `docs/decisions/2026-10-03-omniroute-3851-pin.md` (the release pin),
  `evidence/artifacts/omniroute-sol-max-20260930/` (the call-log effort read and the executor-level check, whose scripts this record reuses).
- Upstream's own build and checks, unchanged: `npm ci`, `npm run build:release`, `check:pack-artifact`, `check:pack-boot`.
