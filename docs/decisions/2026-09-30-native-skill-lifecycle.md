# Native skill maintenance and lifecycle, 2026-09-30

Provenance: pre-existing uncommitted changes observed in the main checkout; original
author not established (snapshot r2, `tracked.diff` sha256 `314bd1b260da0939`). The fold
briefs' earlier attribution to the Codex coordinator lane rested on a process census of
file writes, which does not establish document authorship, and the lane concerned asked
for this neutral wording. Folded unchanged below these two paragraphs; every re-pin it
describes was re-verified from blobless clones of the source repositories. Its
`convergence.json` was not folded: it froze the
hashes of that uncommitted tree, which no commit reproduces, so
`scripts/validate_convergence.py --all-recorded` could not accept it.

2026-09-30, later: the listing states and budget sums under "Evidence boundaries" predate
the [LLM-native listing record](2026-09-30-skills-llm-native-listing.md) and the
`resolving-merge-conflicts` retirement; the current states and sums are in
[the manifest](../../adoption/skills/manifest.json) and that record.

The user requested current, high-quality LLM-native practice with seamless skill
invocation, then explicitly requested installation from maintained SOTA
repositories through the full lifecycle. This is bounded foundation maintenance;
it does not select every catalog candidate or establish universal superiority.

## Sources and selection

- Installed Codex 0.159.2 and Claude Code 2.1.285 match the latest stable upstream
  releases observed on September 30:
  [Codex](https://github.com/openai/codex/releases/tag/rust-v0.159.2),
  [Claude](https://github.com/anthropics/claude-code/releases/tag/v2.1.285).
- Skills CLI 1.7.0 is the current npm/latest and upstream stable release:
  [vercel-labs/skills `7407f389`](https://github.com/vercel-labs/skills/tree/7407f3893ad4dceab546ac002c3ef806e4000c73).
  Reuse its isolated installation and the existing repository installer.
- Update `search-first` to
  [ECC `c70874fa`, `skills/search-first/SKILL.md`](https://github.com/affaan-m/ECC/blob/c70874fae9eb0e5ad0365beb7e2955899fd1d30f/skills/search-first/SKILL.md).
  Upstream clarified the activation description for features, dependencies,
  integrations and potentially reusable utilities. The body is unchanged.
- Update `diagnosing-bugs` and `tdd` to
  [Matt Pocock `d81f3a18`, debugging](https://github.com/mattpocock/skills/blob/d81f3a183412e71a5b1e84ca21bc1a35eea03a60/skills/engineering/diagnosing-bugs/SKILL.md)
  and [TDD](https://github.com/mattpocock/skills/blob/d81f3a183412e71a5b1e84ca21bc1a35eea03a60/skills/engineering/tdd/SKILL.md).
  Their optional context reference changed from `CONTEXT.md` to `GLOSSARY.md`.
  This is source maintenance, not a measured debugging or TDD improvement.
- Retain the inspected, byte-identical directories for the four selected
  [OpenAI skills at `49f948fa`](https://github.com/openai/skills/tree/49f948faa9258a0c61caceaf225e179651397431/skills/.curated),
  ECC `iterative-retrieval` and Matt Pocock `writing-for-agents`.
- Preserve `supply-chain-risk-auditor`'s previously accepted `uv.lock` exception.
  [Trail of Bits `82fe8226`](https://github.com/trailofbits/skills/blob/82fe8226252622fa807643bdca1710901198553a/plugins/supply-chain-risk-auditor/skills/supply-chain-risk-auditor/SKILL.md)
  retains the pinned skill tree and still uses plain `uv run`; its recorded
  `uv run --no-project` overturn condition has not arrived.

The compact task-to-skill rule in the repository and portable instructions follows
[OpenAI's September 11 Astra guidance](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra),
[native Codex skills](https://developers.openai.com/codex/skills), and
[native Claude skills](https://code.claude.com/docs/en/skills). It loads the selected
skill before using it and discloses supporting material on demand. Detailed
installation, activation, updates, recovery and removal are in
[the lifecycle guide](../../adoption/skills/lifecycle.md).

## Evidence boundaries

The 28-skill installation remains the existing 30-day trial, with the original
October 25 review. Its native listing controls remain deliberate: 20 Claude
descriptions on, five name-only and three user-invocable-only; Codex enables 11.
The updated manifest budget is 7,184 Claude description characters and 3,016
Codex characters, each below its 8,000-character manifest cap. Those totals
exclude plugins and built-in skills.

The runtime-worker manifest's three `reuse_ref` entries now match the adoption
selection. Its catalog totals are 137 skills, 1,021,146 source bytes and 36,926
description characters. Its original discovery-source table and historical
validation inputs retain their original revisions; neither is a new model run.

Representative activation cases and their outcome rule were saved before model
execution in [probes.json](../../evidence/artifacts/native-skill-lifecycle-20260930/probes.json),
following [OpenAI's skill evaluation reference](https://developers.openai.com/blog/eval-skills).
Installation, deterministic integration tests and actual native model activation
are separate observations. No token-saving or across-model quality claim follows
from these checks. Raw native logs and recovery backups stay in private owned
lifecycle state outside the checkout.

## Corrections and failed conditions

| Finding | Correction and verification |
| --- | --- |
| The first bundled skill read exceeded the output budget. | Recovered full instructions through context-mode indexing; later retrieval uses scoped processing. A truncated read was not treated as complete. |
| Initial path guesses for the Claude instruction template and a skills README failed. | `rg --files` identified `examples/claude-native/CLAUDE.md` and the existing manifest/update guide. No missing-path output was treated as an absence claim. |
| A full runtime-worker manifest read exceeded the output budget. | Recovered the three relevant entries through context-mode; patched only their pin fields, source references and catalog totals. |
| Bare `skills` and the default installer invocation exited 1. | The selected isolated executable reports 1.7.0; lifecycle commands use `--skills-bin` explicitly. PATH absence was not interpreted as an absent installation. |
| Curated discovery marked shared installed skills as uninstalled. | Its flag examines the Codex skills directory, whereas native loading also uses shared roots. The value-free host status checks the selected roots and lock. |
| Metadata passed while one supporting-file tree differed. | Metadata success is narrower than full-tree integrity; retain the documented `uv.lock` exception and its per-blob check. |
| GitHub API exhausted its rate limit during source re-checks. | Exact immutable raw-source downloads returned 200 and matched the reported file hashes; API failure did not imply an unchanged source. |
| The first local integration run failed on downstream `reuse_ref` identities. | Repaired all three declarative consumers and reran the relevant seven modules: 268 passed and 11 were skipped, 279 total. The original three failures and one error remain in the receipt. |
| Progress shorthand described all 279 tests as passing while also mentioning skips. | The actual native result is `Ran 279 tests` and `OK (skipped=11)`: 268 passed, 11 skipped. The receipt retains that exact returned summary. |
| The first observed convergence record numbered separate scopes as separate attempts. | The validator groups attempts by task, role and condition; assigned unique chronological native-CLI attempt numbers and revalidated all seven observations. This is recorded consistency, not a new execution. |
| Publication validation rejected pre-existing `:memory:.ses` as a noncanonical path. | Moved that file and the pre-existing `hook.err`/`hook.out` outputs, unchanged and unread, into the owned private lifecycle backup. Their September 27 timestamps predate this maintenance; the move is reversible. |

## Observed result

[The compact receipt](../../evidence/artifacts/native-skill-lifecycle-20260930/receipt.json)
retains actual returned native results, model outputs and usage. Three updated
skills were installed through the selected upstream CLI; 25 matching
installations were reused. All 28 selected metadata checks pass. The independent
per-blob check passes with exactly the previously allowed `scripts/uv.lock`
difference, no missing/extra source blobs and no other differences.

The disposable project installed `search-first`, removed it through the native
CLI, recovered it from the immutable source, passed project pin/list checks and
removed it again. The owned project was cleaned up; the global installation
remains. This tests local install/removal/recovery, not client sign-in recovery
or restoration on another host.

All three fresh read-only Codex cases completed with outer process exit 0.
The explicit research case read the complete updated `search-first` instructions;
the implicit AGENTS.md case read the complete `writing-for-agents` instructions.
Their task outputs meet the frozen rules. The adjacent spelling case called no
tools and returned the exact expected sentence. Independent review checks
original tool outputs rather than skill-name mentions.

Claude's native `/skill-doctor` also returned exit 0, `num_turns: 0`, no error and
zero model-token usage/cost. It lists the selected skills. Its historical use
counts are not new implicit activation evidence.

The global user-instruction updater dry run separately returned exit 2: it
requires Codex 0.157.1, while the installed current stable client is 0.159.2.
Twelve running Codex processes were also observed. No global user instructions,
client config or active session were changed. The portable rule is prepared and
the repository rule was present in the fresh probes; a future global rollout
needs a qualified updater for the selected client and its required idle state.
The three skill installations themselves are active independently of that step.

## Recovery and reopening

The selected three original folders, public lock metadata and previous manifest
are retained privately. Recover an old revision through its immutable source and
the existing installer, then recheck native listing and activation. Disposable
project install/removal/recovery checks are separate from the accepted global
installation. Reopen selection when a relevant source changes, a realistic
positive misses, an adjacent negative over-triggers, or a qualified comparison
overturns the current trial. Other hosts collect their own acceptance.
