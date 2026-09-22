# Landscape catalog finalization

## Outcome and acceptance

Finalize the current published foundation and US-equities landscape with a
machine-readable comparison ledger and an offline HTML view. Every foundation
layer and all four domain research layers must explain the requirement, current
choice, named alternatives, evidence depth, limits and the result that would
reopen the choice. Preserve actual failures; an untested alternative is not a
failed test. Preserve historical pins and recorded results.

Acceptance: exact layer coverage, resolvable evidence and repository identities,
all existing domain candidate cards retained, deterministic HTML rebuild, relevant
catalog and regression checks, browser inspection, and independent review.
This work does not claim a new full-stack install, model benchmark, second-PC
acceptance or universal SOTA ranking.

## Base and ownership

The integration branch is `codex/landscape-evidence-finalization-20260921`, based
on published `fb04bf702ea67b14163405f0ebe132e393ebbd8a`. Existing unpublished work
on the original checkout remains separate and untouched.

- Coordinator: shared comparison schema, generator, HTML, validation, canonical
  summary reconciliation and integration.
- Foundation worker: `catalogs/landscape/foundation.json` and
  `docs/landscape-foundation-notes.md` in its own branch/worktree.
- Domain worker: `catalogs/landscape/us-equities.json` and
  `docs/landscape-domain-notes.md` in its own branch/worktree.
- Freshness worker: `catalogs/landscape/upstream-snapshot.json` and
  `docs/landscape-freshness-notes.md` in its own branch/worktree.

Workers inherit the parent model/effort; provider usage is unavailable to this
record. One coordinator integrates; at most three independent workers.

## Initial evidence and decisions

The existing catalog has 68 component records, 16 foundation layers, four domain
research layers, 152 domain candidate cards and 513 repository identities.
Foundation decisions total 46, although one convergence summary still says 44.
Existing generator and validators are reused. Fresh metadata checks are separate
from native runtime acceptance and do not automatically justify upgrading pins.

## Progress

Integrated the three independently produced data changes. All 20 layers now have
168 comparison rows, and all 152 historical domain candidate cards remain intact.
Fresh primary-source checks cover all 68 selected components and 343 public stars.
Six missing identities were reconciled into the 519-repository shared index,
including the newly starred Cua candidate. Headroom's transferred repository was
normalized without changing its selected version. Five newer stable releases
remain comparison candidates; metadata alone does not establish runtime fitness.

The offline explorer now exposes searchable layer choices, alternative outcomes,
evidence, limits, reopening conditions, a combined manifest download and lazily
expanded historical cards. Stale HUD and foundation-count summaries were
reconciled against retained native evidence without rewriting historical receipts.

Independent review found no unsupported claims in sampled evidence. Its source
pin freshness finding was fixed by binding snapshot records to selected versions,
source pins and alias-normalized repository identities. The focused regression
suite passed 121 tests. Layer, foundation, domain and decision-index validation
passed. The deterministic HTML rebuild passed. Integrity hashes await refresh
after final browser inspection; the first integrity run correctly reported the
changed files as mismatches.

## Verification and corrections

The full suite initially found three stale lifecycle joins: catalog counts,
Headroom's transferred identity and the HUD use-stage expectation. These were
reconciled with the current index and retained foundation-closure evidence.
The full rerun passed: 761 tests, 41 optional/environment skips. A deliberately
missing quickstart in a failure-mode fixture printed a failure receipt as expected;
the test suite itself exited successfully.

Native browser checks passed for a 1-layer Cua search, catalog/outcome filters,
reset, the downloadable JSON (20 layers, 168 comparisons, 152 historical cards),
and lazy expansion of the 42-card worker archive. Desktop width 1280 and mobile
width 390 had no document overflow. Mobile inspection found an oversized wrapped
navigation bar; horizontal navigation reduced its header to 128 pixels. The page
reported no browser errors, console messages or resource requests. These are local
HTML integration checks, not upstream tool or second-PC acceptance.

Independent read-only evidence and implementation review resolved the source-pin
finding and reported no remaining actionable findings within its reviewed scope.
The five questioned source links existed with matching bytes at both the former
link base and the current published base. Workflow security inspection returned
zero findings, and the whitespace check passed. Convergence discovery correctly
refused stale integrity hashes before their planned final refresh.

## Final local validation

- `python3 scripts/validate.py`: passed; 68 components, 4 profiles, 128 receipts
  and 1,434 hashed files. This is integrity/scope validation, not native execution.
- `python3 scripts/validate_catalogs.py`: passed; all 152 historical cards remain.
- `python3 scripts/validate_foundation.py --root . --json`: passed; 16 layers and
  46 decisions with their scoped receipt joins.
- `python3 scripts/landscape.py --root .`: passed; 20 layers, 168 comparisons,
  343 current public stars and 519 research identities.
- `python3 scripts/catalog_decisions.py --check`: passed; 1,241 typed references.
  Its original 342-star audit remains dated, separate from the current snapshot.
- `python3 scripts/validate_convergence.py --all-recorded --root . --json`:
  all 14 recorded experiments valid after integrity refresh.
- `python3 scripts/build_ecosystem.py --check`: exact rebuild passed.
- `python3 -m unittest`: 761 tests passed, with 41 environment-dependent skips.
- Native `zizmor --offline --no-config --no-ignores --no-progress --persona regular
  --strict-collection --format json .github/workflows`: zero findings.
- Native actionlint 1.7.12: passed after verifying the workflow-pinned release
  archive checksum. It was absent from PATH; the isolated temporary binary was used.
- `git diff --check`: passed.
- `gitleaks dir . --redact --no-banner`: nonzero with 206 pre-existing findings.
  Of these, 205 occur in 18 files byte-identical to the published base; the one
  generated HTML finding is the unchanged `openapi_sha256` checksum. No finding
  was introduced by this change. This is a baseline comparison, not a claim that
  the unfiltered scanner returned zero findings.

The reviewed artifact is ready for integration. A destination PC must still
perform its selected profile's native sign-in, installation and acceptance steps;
this publication does not certify another machine or universal superiority.

The final independent pass caught another stale current limitation: the lifecycle
summary still said Context Mode PreCompact was unforced. The original September
20 attempt remains dated, while current use and remaining boundaries now cite the
later successful manual compaction observation. Automatic compaction, every-fact
preservation, new host/session acceptance and desktop hot reload remain unqualified.
