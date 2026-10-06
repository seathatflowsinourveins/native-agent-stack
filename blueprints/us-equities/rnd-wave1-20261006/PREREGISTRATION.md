# North-star R&D wave 1 (2026-10-06): inspection registry and as-of mover replay on NativeStack2604

Status: **preregistered, not run.** The commit that adds this file and [`plan.json`](plan.json) is the freeze. Both
files stay byte-identical afterwards; any later change is a dated deviation record beside them. Execution starts only
after the command center's read. Base commit: `ecfa112764c664d35377dd66b8cfcb67e5a94d60`.

North-star action served: the selected direction, daily and intraday catalyst research including historical +200%
mover discovery ([AGENTS.md:41-44](../AGENTS.md)). This wave makes the first empirical read of that direction legitimate
and reproducible on the 2604 host. It makes no strategy, paper or broker claim.

## Why this wave first

- Catalyst v1 requires a per-security, per-event and per-date inspection registry **before any empirical read**
  ([`catalyst-experiment/protocol.json`](../catalyst-experiment/protocol.json), `chronology.inspection_registry`). Its
  reserved access refuses any case without a registry record that says *not inspected* and carries a hash
  ([`contract.py:144-152`](../catalyst-experiment/contract.py)). No registry exists.
- Earlier waves already read data inside v1's windows. Those windows are development 2022–2023, validation 2024 and
  reserved 2025. The reads include:
  - broad-universe's reserved segment;
  - mover-early-entry's 2024–2025 validation;
  - the extreme-gainer price audit's 957 events;
  - E2's 715 events from 2021–2025.

  Without a registry, nobody can say which v1 cases are still fresh.
- NativeStack2604 holds no retained trading dataset today. The only verified mover dataset is E2's as-of run on
  NativeStack: 9 files, about 30 MB, each pinned by sha256 in
  [`summary-asof-20260929.json`](../mover-coverage-asof/evidence/summary-asof-20260929.json).

R1 is therefore offline and comes first. R2 reproduces E2 on 2604, and only after R1 profiles the +200% events, as
description.

## R1: exposure and inspection registry for catalyst v1

**Question.** Which securities, events and dates inside v1's chronology does this repository record as read or as
inspected? Which v1 sessions stay eligible for each segment?

**Inputs.** Repository receipts, plans, run READMEs and commit history at the base commit. No data, no network.

**Method.**
1. Enumerate every recorded read that touches 2021-01-01..2026-09-30. `plan.json` `R1.known_reads` is the minimum
   list. The search covers the whole trading tree: receipts, evidence summaries, run sections of READMEs, deviation
   files and the decision index.
2. Each registry entry records:
   - the scope kind: one security on one date, one event, or a universe over a date range;
   - the identifiers or universe definition as recorded;
   - the date range;
   - the access kind: `data_read`, `result_inspected` or `outcome_selected`;
   - the purpose;
   - the source commit, the source `path:line`, and the sha256 of the cited record.
3. A deterministic stdlib builder writes `inspection-registry.json`. It also provides a lookup that maps a case id to
   `{inspected, registry_hash}`, in the form `contract.reserved_access` consumes. A universe-wide read over a date
   range marks every case in that range as inspected (the conservative reading).
4. A model may draft entries from the receipts. An entry is kept only if the builder confirms its path, line and hash
   at the base commit.

**Hypotheses and decision rule.** All are mechanical.
- **H1.1 completeness.** Every read in `R1.known_reads` has at least one entry. A cross-family completeness critic
  searches for missed reads. A miss found after the freeze is added as a dated deviation, never silently.
- **H1.2 refusal.** In synthetic tests (at least one per entry kind), `contract.reserved_access` refuses every case
  that an inspected entry covers. It admits a synthetic uninspected case that carries a valid hash.
- **H1.3 unchanged protocol.** `catalyst-experiment/protocol.json` and `contract.py` are byte-identical to the base
  commit.
- **D1 segment eligibility.** A v1 session whose eligible universe any inspected entry covers is ineligible for
  reserved evaluation, with no substitute dates (`chronology.inspection_registry`). The registry reports eligible
  session counts per segment. It makes no performance claim. If no 2025 session stays eligible, catalyst work needs
  a prospective holdout, and that is a separate, later preregistration.

**Receipts.**
- the registry and its sha256;
- the builder;
- the synthetic tests;
- a summary of entry counts by kind and eligible sessions per segment;
- a `scripts/validate.py` pass.

## R2a: replay E2 offline on NativeStack2604

**Question.** Does 2604 reproduce the committed E2 classification from the retained snapshots?

**Inputs.**
- The retained run `research/asof-20260929`, under the private state root. The coordinator copies it from NativeStack
  into a fresh 0700 directory on 2604.
- Before any run, each of the 9 files must match `E2.private_files_sha256` in the committed summary.
- The package zip must match `extreme-gainer-audit/plan.json:8`.

**Arms.** Both use no network, no credential, nice 19 and TMPDIR outside /tmp. Each runs on its own fresh copy, with
`results`, `labels`, `summary` and `verify` removed, then `classify` and `classify --verify`.
- **Arm A (exact).** `refetch.py` at `99dfec7cf6bdd2bc49f0099206ed84fc1d88ebb1`, the revision whose offline rerun
  matched the unit byte for byte ([README:122-127](../mover-coverage-asof/README.md)). Its imports are unchanged at
  the base commit.
- **Arm B (current).** `refetch.py` at the base commit.

Both use Python 3.12.3 with numpy 2.5.3 ([mover-early-entry/README.md:44](../mover-early-entry/README.md)), from
2604's research runtime project.

**Hypotheses.**
- **H2.1.** Arm A reproduces `results.json` (`406f582c…`) and `labels.json` (`19e27666…`) byte for byte, and its
  verify passes.
- **H2.2.** Both arms give 715 package events in range and N2 = 594. At a close-to-close gain of 1.5×, 2× and 3× they
  give 507, 261 and 97 events.
- **H2.3.** Arm B's output hashes are reported. A difference from Arm A is a code-revision effect, described field by
  field. It is not a replay failure.

An input-hash mismatch or an Arm A mismatch is a FAIL and is retained as is. There is no retry with changed inputs.

**Receipts.** A totals-only host receipt, with no paths, symbols or dates, and both arms' output hashes.

## R2b: descriptive profile of the +200% events (after R1)

**Start condition.** R2b starts only after R1's registry records E2's events as inspected, and after it adds this
profile as a further inspection with the purpose "descriptive profile".

**Question.** How do the 97 events with a close-to-close gain of at least 3×, and the 261 at 2×, break down? The
dimensions are year, price bucket, dollar-volume bucket, session timing and the package's catalyst tag.

**Rules.**
- Description only. The set holds gainers only and was selected by outcome, so it has no negatives. Any recall,
  precision or predictive claim is `insufficient_evidence`. The protocol needs at least 30 positives and 100 negatives
  per label per segment (`promotion.extreme_label_claim`).
- Catalyst tags are the third-party package's unverified claims (`extreme-gainer-audit/plan.json`, `not_measured`).
  They are reported as such.
- The results may feed hypothesis generation for a later catalyst design, as development only. They never choose
  thresholds for an evaluation segment.

**Receipts.** Totals-only bucket counts, published through the existing schema scan. Per-event tables stay private.

## R3 (optional, in parallel): cross-family pre-outcome review of mover-v3

The first freeze precondition of the mover-v3 core draft is an independent review by another model family
(`mover-v3/protocol-core-draft.json`, `freeze_preconditions`). A Codex review records its findings in the draft's
review record, and needs no data. The synthetic suite needs uv-managed CPython 3.13.15
(`mover-v3/study/runtime.lock:3-4`), installed in user space on 2604 if the suite is run. Otherwise the review is
read-only.

## Not in this wave

- **Catalyst v1 on historical data.** It is blocked as frozen. Availability needs separately evidenced original
  timestamps (`protocol.json:21`), and there is no historical Item parser or CIK map. A v2 availability basis is a
  separate design that follows R1.
- **Simulation-research continuation and identity readiness.** Both are blocked on as-known universe and availability
  data that neither host holds.
- **Data gates.** The three open ones stay open, and this wave does not advance them: pre-2020-delisting,
  dated-security-identity and pit-news-filings (`catalogs/us-equities/gates-20260922.json`).
- **Acquisition.** None: no broker or market-data request, and no credential, on 2604. A later fetch from 2604 needs
  that host's own acceptance ([AGENTS.md:32-33](../AGENTS.md)) and a research identity without broker access
  ([north-star.md:89-92](../north-star.md)).

## Refusals preserved

These stay as recorded: the SEC HTTP 403, E1's `inputs_missing` refusal, the `feed=otc` 403, the immutable failed
identity receipt, the preregistered audit overturn, the paid-data gates, the SSRN 403, and mover-v3's refusal to run
before its freeze. Locations are in `plan.json` under `refusals_preserved`. The inspected 2021 control segment is
never a fresh holdout.

## Execution and review

- **Executors.**
  - The co-op's Codex lanes (GPT-6.1 Sol), through OmniRoute with an explicit `--base-url` on the 2604 gateway until
    the worker default changes.
  - Bounded runtime workers, at nice 19, outside the paper windows (10:35–13:45Z and 19:50Z–00:10Z).
- **Division of work.** Deterministic code holds every count, hash and decision. Models draft registry entries and
  descriptions only.
- **Coordinator (trading custody).**
  - Copies the R2 inputs.
  - Has GPT-built outputs read cross-family (Claude Opus) before publication.
  - Publishes sanitized, totals-only receipts through a trading PR, after `scripts/validate.py`.
- **Records.** Every attempt, failures included, is kept with its exit code and time.
