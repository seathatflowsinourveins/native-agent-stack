# Decide round 2: repository quality replaces "measured gain" for documented gaps (2026-10-04)

**Status:** accepted on the user's directive. Round 2's per-slot results and their Opus verification land with the final-architecture data PR. The first slot this rule changes, `promptfoo`, is recorded in `docs/decisions/2026-10-04-2604-e2e-fix-wave.md` (consensus batch `wave4`).

## Context

Round 1 (2026-10-04, 11 packets, 48 proposed jobs) applied the 2026-10-01 rule: "no extra install unless measured evidence shows a challenger's gain". The user had also said not to rerun tests, so no candidate could show a measured gain. Round 1 adopted no new tool: 38 jobs were not adopted and 10 only configured existing owners. That included jobs whose need the deciders agreed was real, such as Codex in CI.

A side note put two options to the user: allow small targeted tests, or let clearly documented gaps be filled without a test. The user answered at about 20:50Z:

> "with the repos quality itself resolute our architecture with the sota repos's own quality and finalize for the architecture for us to clean install"

## Decision

Round 2 re-decides the same 48 jobs, plus the 4 slots deferred on a decision (agent messaging, browser automation ownership, credential custody, research-skill activation), under the round's criteria file (`criteria-quality.txt`, published with the round's data):

- **(A) Requirement gate.** The job is in the north-star or foundation scope, or round 1 or its Opus check agreed the need is real, or a user decision names it. A security gap still needs a concrete threat.
- **(B) Candidate gates.**
  - maintained (a commit within 90 days, a release within 180 days);
  - an upstream install for Linux/WSL2;
  - self-hosted;
  - documented Claude Code/Codex integration where the job is client-facing;
  - no overlap, unless the candidate wins against the existing owner.
- **(C) Quality checklist.** Cited to the repository's own evidence:
  - tests and CI at the release tag;
  - release discipline;
  - integration docs;
  - maintenance health;
  - published evaluation, independent over vendor.
- **(D) Choice.** Adopt the strongest candidate that passes every gate; no new local trial. Ties go to fewer moving parts.

**Method** (unchanged from round 1):
1. Two blind GPT Sol deciders, with the candidate order reversed. They see the packet and the new rule only.
2. One GPT Astra critic. It also sees round 1's verdict and the Opus check, and must label every difference as the rule change or a factual disagreement.
3. An Opus cross-family verification of every adopt-true verdict against live upstream, refuting by default.
4. A completeness critic over the not-adopted set.

**Outside this round:** the memory owner and code search. Both have preregistered measured runs in progress (D3r4 and the sealed code-search confirmatory run). Naming a quality winner now would break D3r4's no-pre-selection rule and the executor's blind-isolation condition. On the clean install they stay the recorded interim (ai-memory and semble), and those runs are their settling measurements. The user can overrule this explicitly.

**"Clean install" tonight** means the finalised list, the install plan and the evidence page, then the plan run to completion with acceptance on NativeStack2604. It does not mean a new distribution import, which needs its own go.

## Overturn

A measured run showing that an adopted tool regresses its job's metric against the next candidate, or a gate failure at install time (G-class: install, acceptance, or native wiring), replaces that adoption.

## Alternatives

- Allow small targeted tests: slower, and against the user's no-retest directive.
- Keep round 1: leaves documented gaps unfilled.
