---
status: proposed
date: 2026-10-07
decision-makers: [command-center]
review_by: 2027-01-05
---

# Pin the counter source and separate controlled invocation evidence

## Context and drivers

The Codex counter prototype and test were untracked in their source worktree.
Its retained fixture bound an earlier code hash, so that result could not
establish the current implementation. Commit
`7d20f02732f85ede3521f324efd4a11c5d250413` pins the unchanged prototype, test
and a new source manifest. The old manifest, fixture and observations remain
historical; they are not rewritten or attributed to the new code.

Raw tool events and source-path heuristics cannot establish organic use.
The existing prototype does not cover all directed runs, first turns or named
command/skill uses, and its identity loop covers fewer records than the
maintained native adapter. The catalog's reference validator checks declared
consistency rather than the truth of those classifications.

## Proposed decision

Reuse the existing native record adapter and shared call/result ledger. Retain
the complete record stream for joining before applying classification masks;
filtering individual protocol records first can detach requests from outcomes.
Add an explicit, versioned control input to the existing counter, with the
catalog's canonical reference shape: `path`, `pointer`, `sha256` and
`source_commit`. This is project provenance glue, not another collector,
agent-trial runner or installation.

Common run controls exclude requested executions and smokes. Source-complete
history identifies the first native turn independently of a measurement
window; relaunch masks supplement it. A tool's name anywhere in its complete
task turn excludes that tool's calls across MCP, commands and skill-read
attempts, including names recovered after a call. Referenced context and
parent-turn attribution must be resolved before a remaining call is eligible.
Missing flags, references, history or native identities remain unknown.

Deduplication uses scoped native owner/call identities and preserved outcomes.
Different representations join only when retained native fields demonstrate
their relationship. Caller assertions, matching names or timestamps alone
cannot establish that relationship. Copied history contributes no fresh use.
The outer code-mode call and its distinct native child calls remain separate
unless their identities prove they are the same call.

Keep raw/provisional output separate from the controlled projection. A skill
read attempt is not a successful skill load or activation. Fixture success
establishes local code behavior, not organic native execution, an owner-defined
working day, adoption or readiness. Actual receipt counts require the relevant
original records and complete provenance. The Claude oracle still needs its
own equivalent control evidence; this code unit covers Codex only.

## Alternatives considered

- Rebind the old fixture to current hashes: rejected because that would change
  the recorded source of an earlier result.
- Count a missing marker as an undirected invocation: rejected because absence
  of provenance cannot distinguish a requested run from organic selection.
- Reimplement the native call/result parser: rejected in favor of the existing
  adapter, copied-history rules and ledger interfaces.
- Add another collection or evaluation runtime: unnecessary for this bounded
  classification layer; owner collection and actual qualification stay separate.

## Validation and open items

Each control needs both eligible and excluded or unknown fixture cases:
requested runs, smokes, native/relaunch first turns, names across every relevant
tool class, late context, parent attribution, copied history, native-ID aliases,
duplicate files and missing IDs. Preserve the prototype baseline and every
failed condition. No fixture is labelled upstream acceptance or native use.

Qualification is pending until the completed code and matching fixtures are
registered. Actual counter receipts additionally need their retained native
inputs, resolved controls and independent observation. The daily report must
then use #820's typed policy/report references; zero through the owner's
completed measurement day becomes a wiring item or a supported dated exclusion,
with no automatic exclusion from absence. The adoption synthesis remains pending.

Reopen this design if a supported native format cannot preserve call identity,
turn/context provenance or copied-history boundaries. Compare it with the
maintained native adapter at the same client pin using retained counterexamples;
never retune historical outcomes or substitute an invented identity.

## SOTA sources

- `native-agent-stack@a40a083172af588f4b97646db87dfc8ef3c0b60e:tools/skill-usage/skill_usage.py:775-781,921-934,1221-1227,1314-1655`: existing shell/owner helpers, normalization, copied-history/window rules and private native call ledger.
- At that pin, `examples/claude-native/workflows/child-usage.mjs:2854-2878` and `tests/test_skill_usage.py:1838-1851,3259-3278`: native call/result identity and retained regression seams.
- `openai/codex@d27764b82f7118f674371e6d6e76271d9d606edb:codex-rs/protocol/src/models.rs:1061-1155`, `protocol.rs:1408,1417,1948-1960,2179-2184,2667-2737,3301-3307` and `items.rs:46-76`: response/native completion and explicit turn/root identities at the installed `rust-v0.160.1` pin. Optional or empty turn bindings remain unresolved. [Official release](https://github.com/openai/codex/releases/tag/rust-v0.160.1), published 2026-10-05T18:29:37Z; installed version check returned `codex-cli 0.160.1`.
- `native-agent-stack@6eb5ed83914f37c3f0baca40cba89c8172cfa9e3:scripts/validate_foundation.py:79-196,457-611`: typed references and separate daily report qualification.
- `native-agent-stack@7d20f02732f85ede3521f324efd4a11c5d250413:tools/invocation-monitoring/codex-counter-prototype-manifest.json`: exact source/dependency hashes and historical fixture binding. This local source commit awaits the retained publication path.
