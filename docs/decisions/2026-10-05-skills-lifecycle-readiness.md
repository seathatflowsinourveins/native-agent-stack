# Skills lifecycle readiness and inherited holds — 2026-10-05

Status: bounded integration correction and inventory; survivor adoption and
native model acceptance pending the command center's existing sweep and PR review.
Lane: foundation. Base: `4c897418fe35a030a1188ae447eaf31c893f8eff`.

North-star action: provision the same reviewed lifecycle skills for research,
implementation and runtime workers without releasing a central hold or
confusing a catalog with accepted model capability.

## Decision and sources

Keep the shared Vercel Skills installation path. A reused entry inherits central
`held`/`pruned` status; eligible central status never promotes a worker trial
or releases its local hold. OpenHands resolves its expected installed set with
that same module and records both controlling manifest hashes.

Sources:
[Vercel Skills 1.7.0 at 7407f389, README](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md),
[Agent Skills client integration](https://agentskills.io/client-implementation/adding-skills-support),
[Python direct-file import](https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly),
and the existing repository [lifecycle](../../adoption/skills/lifecycle.md).
The client-specific interpretation follows
[Codex rust-v0.160.0 rendering](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/ext/skills/src/render.rs#L126)
and [Claude's skill visibility documentation](https://code.claude.com/docs/en/skills#skill-descriptions-are-cut-short).
The source/pin/license ledger for unchanged skills is in the
[readiness inventory](../../evidence/artifacts/skills-lifecycle-readiness-20261005/inventory.json).

## Comparison and alternatives

Leaving worker trials independent of central holds allowed the held browser
entry to install. Copying a second exclusion rule into OpenHands would let
installation and discovery drift. Resolving both through the existing reader
keeps the native upstream installer and the repository's central control.
Using runpy was considered and replaced with the documented direct-file import;
no extra dependency or custom installation runner is needed.

Negative fixture controls reproduced two inherited-status failures and a worker
discovery failure before the fix. Eight focused checks then passed. The broader
six-module run completed 452 tests successfully, with three skips, after correcting the test
temporary-directory location and adding the shared installer to a synthetic
stack fixture. The original failed run is retained separately. Native
`--check-only` verified the existing 24 installations; an explicit held worker
selection was refused before source lookup. These are local integration,
synthetic and native read-only observations, not upstream skill-quality or
provider-backed acceptance.

A listing-budget increase was considered. Current Codex rendering includes
every active selected description. Claude's 44-name overlap compares an init
list with model recall; it does not establish eviction. Retain settings and
propose changes only if a fresh diagnostic establishes a concrete omission.
No removal follows from zero baseline invocations because exposure and counters
are not comparable. No sweep lead is adopted before its review and upstream
paired benchmark.

## Overturn conditions and next gate

Replace this integration if a maintained upstream lifecycle supplies equivalent
central hold inheritance and one authoritative eligible-set API, demonstrated
with the same negative controls and native install/discovery receipts.
Reconsider client settings after full post-budget diagnostics for the reviewed
survivor set. Reconsider selections only with a pinned source review and a paired
native benchmark establishing better task outcomes under comparable costs.

Completeness critic: add native worker skill sources, Inspect/Harbor consumers,
plugin/bundled and host-only skills, user-only/implicit gates, and broad intake,
architecture and review gaps to the next lifecycle-keyed landscape inputs.
The existing command-center sweep remains authoritative research input; its
initial discovery is not a completed survivor decision.
