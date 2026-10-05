# Skills lifecycle landscape publication — 2026-10-05

This is a **stopped, partially source-reviewed sweep**, not adoption or skill
quality acceptance. It serves lifecycle coverage for the stack's complex-system
and north-star research workers. Workflow `wf_b786bea1-429` covered all 13 tasks
in `catalogs/landscape/skills-lifecycle.json`; the original converted artifacts
retain 140 proposal occurrences and all 48 vote survivors. Every lane decision
has `selected=[]` and `alternatives_keep_but_compare=[]`.

`SHA256SUMS` is the co-op's original checksum file. `returns.json`, `lanes.json`,
`layers.json` and `survivors.json` are byte-identical to that converted handoff.
Raw workflow conversations remain outside Git. The full native child-usage
record and the smoke attempt are retained separately in the adjacent
`skills-lifecycle-landscape-20261005-attempts` directory.

## Provenance gates

Native `source_reviews.py` returned exit 1: 37 successful reviews and 11 stopped
leads, all retained in `source-review-index.json`. Five stops have no judged
SKILL.md SHA256; the other six have CLI discovery or exact-byte/tree proof
failures. The stops are neither successful source reviews nor merit refutations.
Native `make_result.py` refused a completed RESULT (exit 2).

`RESULT-input.json` follows the manual stopped-record route. It retains all
140 proposals, original vote pointers and reopen entries, while binding only
the 37 successful source reviews. The native `skill_review_problem` check was
also applied to all 37: zero pin/hash/tree-binding problems. The original 48
vote survivors remain available for reconciliation; eleven unbound leads are
left unadjudicated in the stopped ledger record. Source-review stops reopen
six affected tasks; together with the converter's eleven reopened tasks,
twelve tasks are reopened (all except `skills-implement`).

The recipe's `votes: not_returned` stopped example describes interrupted votes.
This run has retained returned votes, so its stopped record uses the native
ledger's `votes: retained` contract with discovery and vote pointers. Stopped
status with `lower_bound_usage=true` neither counts nor resets saturation.

These receipts verify source identity, the reviewed commit and judged SKILL.md
bytes. They do not approve license terms, audit supporting executable code, or
prove installation, invocation, task performance or model discovery. Candidate
qualification still requires official-upstream and engineering-quality review,
license review, Claude skill-creator paired benchmarks (or promptfoo), the
command center's cross-family PR read, lifecycle-only installation and fresh
client/worker model discovery.

## Retained limits and usage scopes

GPT-6 was degraded: 42 jobs, 28 ok, 13 late `file_only` returns and one timeout
(exit 124). Fourteen jobs have unknown usage; three earlier attempts remain
separate in `returns.json#/gpt6_usage/earlier_attempts`. Sixteen proposals have
missing GPT fit votes; their original `votes_note` explains that the serialized
refuted placeholder is not a merit refutation or completed adjudication.

Claude's native record has 106 complete children and one retained effort
deviation in the skills-test follow-up (`max` and `low`). `usage_record.py` exit 1
is retained, with the exact deviation mapped to `returns.json#/failures/skills-test`.
There are no incomplete Claude children; late GPT wrapper jobs are not relabelled
as missing Claude workers. Claude native counters, GPT counters, the co-op's
16.5M UI token estimate, parent usage and billing are distinct scopes. Cache
and reasoning counters are subsets where the provider defines them that way;
no overlapping totals are added and unknown usage remains unknown.

The co-op's converter first exited 3 for thirteen personal home-path strings,
which it redacted to `/home/<user>/`. Its final exit 4 retains the late-file
limit. Native private-content checks of the retained converted outputs, usage
and reviews found zero findings. The initial publication source-review call
used a misspelled input directory and failed before reading survivors; its
corrected retry is the exit-1 review result above. No source claim came from
the failed first call.

The merged research manifest is
`catalogs/sota-convergence/manifest-20261005-skills-ns2604.json`. Its foundation
and trading baselines were freshly extracted at main
`ec0b8fd821a7b2004c331d2185b33d9e5ed47896`; the freshness input was retained. Reused
freshness is dated 2026-10-05 02:31 metadata, not a new live acceptance run.
Catalog inclusion installs nothing. The smoke artifacts are earlier-attempt
evidence and are not added to full-run usage or skill benchmark evidence.

Freshness coverage is limited to the retained snapshot's own metadata. Native
`source_reviews.py:100` parses the 137 distinct skill references into 73
underlying repositories; native `build_manifest.py:227` finds 24 of those in
the snapshot and no record for 49. Its direct lookup resolves zero literal
owner/repo@skill identities. Thus complete baseline URL coverage is not full
skill-source currency. These are snapshot lookup limits, not absence claims
about other evidence in the converted researchers/refuters. The 37 source
reviews independently bind their exact pins and judged bytes; current release
and engineering-quality qualification remains a follow-up/adoption gate.

## Local publication checks

Native ledger append and `--check --base origin/main` passed: six sweep records,
chain intact and bindings verified. Repository validation passed before adding
the retained check logs and is repeated on the final registry. Native unittest
ran 452 skill/worker tests (three skips), 655 ledger/landscape/convergence tests
(six skips) and 61 documentation/release tests (one skip), all successfully.
Actual returned outputs are retained as `tests-*.txt`, `ledger-check.txt`,
`validation-initial.txt` and `manifest-build.txt`; `checks.json` binds their
scope. These are local integration and synthetic fixture checks, distinct from
unchanged upstream skill tests or provider-backed paired/model acceptance.

Completeness critic: the independent publication read verified the stopped
schema, preserved vote/proposal requirements, per-layer review binding and
usage scopes against the native source. The root then ran the stronger native
judged-pin/hash/tree binding check for every included survivor. Remaining
coverage gaps are the eleven provenance stops, missing GPT votes, supporting
executable content and license terms, measured skill performance, trigger
visibility and fresh discovery across both native clients and runtime workers.
They feed the co-op's agreed twelve-task follow-up in sequential two-task runs
after readiness dispatch and the paper window, with no overlapping GPT-heavy
workflow. No follow-up is launched by this publication lane.

## SOTA sources

- native-agent-stack@4af7417b7d4db8936c0136235a86717f31d16f27:
  `tools/sota-convergence/landscape-sweep/README.md` (publication steps 9–12;
  shared GPT quota and bounded queued jobs at lines 957–966).
- Same pin: `tools/sota-convergence/landscape-sweep/source_reviews.py:1210`
  (pinned skill source receipt and its limited evidence class),
  `make_result.py:160` (judged-byte binding) and `make_result.py:244`
  (completed-result refusal on a stopped source review).
- Same pin: `recipes/saturation-sweep.md:112` (manual RESULT and computed fields),
  `recipes/saturation-sweep.md:152` (stopped saturation behavior),
  `scripts/saturation_ledger.py:1025` (retained votes), `:1077` (review binding)
  and `:1091` (retained-failure reopen references).
- `adoption/skills/lifecycle.md` and `docs/acceptance-evidence-policy.md` define
  the remaining adoption and acceptance gates. This publication changes neither
  an installation manifest nor client settings.
