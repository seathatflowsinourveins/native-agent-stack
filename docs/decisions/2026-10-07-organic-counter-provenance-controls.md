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

## Amendment (2026-10-07): Named prose and conflicting command originals

The source review of #820 at `77d35e41911c0f8c28a5561790cd8d8a8cd68175`
identified two gaps in the proposed controls. A configured name followed by
sentence punctuation must still exclude the named tool. Match names at prose
boundaries while retaining punctuation internal to a valid configured name;
`Use serena.` and `Use rtk:` are directed turns, not organic selections.

Two completed command originals sharing a proven native identity must agree on
their complete command representation. A contradictory command leaves attribution
incomplete and counts unknown. This does not prevent supported enrichment of a
request with its completion or deduplication of identical originals. Preserve
the actual contradictory observations rather than selecting the last command.

The repair evidence is separate in
[`ns2604-catalog-fix2-20261007.json`](../../evidence/receipts/ns2604-catalog-fix2-20261007.json).
Its deterministic controls are synthetic fixtures; they do not supply a native
organic result or replace the prior receipt's recorded source and outcomes.
Actual native input qualification and the equivalent Claude evidence remain open.

Sources: `native-agent-stack@77d35e41911c0f8c28a5561790cd8d8a8cd68175:tools/invocation-monitoring/codex_counter.py:299-307,405-425,577-657`
and `examples/claude-native/workflows/child-usage.mjs:2854-2878`;
the [Python 3.12 regular-expression reference](https://docs.python.org/3.12/library/re.html)
for literal escaping and boundary assertions; the pinned Codex native protocol
sources listed above for original request/completion identities.

## Amendment (2026-10-07): Explicit native identity groups

The completeness review found that comparing completed commands only under the
same storage key missed explicit response-ID/call-ID aliases. A discriminating
fixture also confirmed that sibling response IDs sharing a request's call ID
could carry conflicting completions. Apply the same completion-command/status
agreement rule to the exact one-hop identity groups used by the existing
controlled projection. Incomplete attribution stays incomplete for every member,
including after duplicate records. This adds no transitive alias inference.

Retain the first repair at `5530276d1df426db36ce2ddbd0f92e59105c0f1e` and
its receipt. The separately dated
[`alias supplement`](../../evidence/receipts/ns2604-catalog-fix2-alias-20261007.json)
records each subsequent failed condition, passing counterpart and source binding.
Native organic proof remains pending; these checks are synthetic fixtures.

Sources: `native-agent-stack@5530276d1df426db36ce2ddbd0f92e59105c0f1e:tools/invocation-monitoring/codex_counter.py:350-360,440-455,615-640`
and the existing native call/result ledger at
`native-agent-stack@77d35e41911c0f8c28a5561790cd8d8a8cd68175:examples/claude-native/workflows/child-usage.mjs:2854-2878`.
The Codex protocol's required call ID and optional response item ID are pinned
in the upstream sources above; matching names or timestamps do not create an alias.

## Amendment (2026-10-07): Case and command representation controls

The delta review at `dee7cae97c74a6657cb40c7bf8324ccbd41f9111` found two
remaining variants. Case-fold both extracted prompt names and configured names
before exact token comparison. Capitalized or mixed-case names followed by prose
punctuation exclude the tool, while internal punctuation and distinct longer
names retain their existing boundaries.

Completed-command agreement must preserve the original representation. Native
argv and shell text can flatten to the same string while naming different
executables or skill reads. Keep their representation kinds and contents apart;
without demonstrated equivalence, different completed representations conflict
and leave attribution incomplete and counts unknown. The same rule applies
within the existing explicit native identity groups. Requests may still enrich
completions, and identical completed originals still deduplicate.

The supported cross-representation forms remain narrow: an exact three-element
Sh/Bash/Zsh `-c` or `-lc` wrapper carries its declared script, and a bare external
RTK argv can agree with precisely its `shlex.join`-escaped shell string.
Additional shell arguments and unproved argv forms retain their own identities.
Distinct argv vectors retain their executables and flags even when their script
text matches. Require pairwise agreement among all completed representations;
a compatible shell-text record must not bridge two conflicting argv originals.
This verifies declared command compatibility for the controlled projection;
it does not prove external execution or shell environment equivalence.

The historical raw/provisional prompt filter remains unchanged. Its older
case-sensitive extraction is not the controlled oracle: qualification rebuilds
complete owner/turn names through the repaired original-record path. Do not
publish the provisional filter's output as qualified organic counts.

The new [`fix3 supplement`](../../evidence/receipts/ns2604-catalog-fix3-20261007.json)
preserves the red controls and repaired outcomes separately from the earlier
receipts. These are synthetic counter controls, not actual organic use, upstream
acceptance or adoption. The final catalog remains pending synthesis.

Sources: `native-agent-stack@dee7cae97c74a6657cb40c7bf8324ccbd41f9111:tools/invocation-monitoring/codex_counter.py:49-99,299-309,405-432,611`
and `tools/skill-usage/skill_usage.py:926-936`; the
[Python 3.12 case-folding reference](https://docs.python.org/3.12/library/stdtypes.html#str.casefold)
and [subprocess argument semantics](https://docs.python.org/3.12/library/subprocess.html#frequently-used-arguments),
checked on 2026-10-07; the pinned native Codex protocol sources above.
The supported representation seam follows
`openai/codex@d27764b82f7118f674371e6d6e76271d9d606edb:codex-rs/core/src/shell.rs:20-30`,
the [Python 3.12 shell-token serialization reference](https://docs.python.org/3.12/library/shlex.html#shlex.join),
and `rtk-ai/rtk@v0.51.0:README.md:6,313`. The unchanged provisional paths are
`native-agent-stack@dee7cae97c74a6657cb40c7bf8324ccbd41f9111:tools/invocation-monitoring/codex_counter.py:198-224,788-799,874`.
