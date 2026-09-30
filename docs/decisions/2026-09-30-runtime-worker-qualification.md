# Source-pinned runtime worker qualification

The requested change is a source-backed candidate framework for bounded native
workers: coding/planning, research, review, browser extraction and GitHub work,
with task-scoped skills, native recovery and honest usage accounting. It is
implemented as supported upstream recipes and thin integration adapters rather
than a new agent loop. Existing default SDKs and global client/gateway settings
are not promoted by this record.

The primary references are OpenHands/software-agent-sdk v1.50.0 at
`dcf401af7a9a302ef92cb7d092e1df9bb659daa5` (native skills, LLM dispatcher,
TaskToolSet, goal review and server lifecycle); openai/codex rust-v0.159.2 at
`ff6aec96948b70d94983af2641a6b67c94faeff5` (`sdk/python`, SDK CI and custom
model-provider config); GPT Researcher v3.7.0 at
`0957c301ed06c2a5857b834358c7227c739041d4` (native context filter, LLM kwargs,
CLI and selected tests); DeerFlow v2.1.0 at
`345f08be00c8a9495079b732a39b46aa9af1584e` (backend model factory, extensions,
client and native dependency override); Crawl4AI v0.9.4 at
`133e1d92e37885dfccc03ea2e3687d06c98b7ceb` (REST jobs, extraction and
regression tests); and Vercel skills v1.7.0 at
`7407f3893ad4dceab546ac002c3ef806e4000c73`. Recipes and the skill snapshot name
their exact source files, artifact hashes and current/historical distinctions.

[The roster guide](../../blueprints/runtime-workers/README.md) maps each task
to its candidate and unresolved gates. [Native research receipts](../../evidence/artifacts/runtime-roster-20260930/README.md)
retain selected unchanged test commands and actual returned output. OpenHands'
[native upgrade outputs](../../blueprints/runtime-workers/openhands/evidence/upgrade-150-commands.json)
and [image triage](../../blueprints/runtime-workers/openhands/evidence/image-triage-20260930.json)
are separate. No native test total is a whole-roster quality result.

The full OpenHands image remains unaccepted. The native Grype report has 56
fixable High/Critical matches. Source triage distinguishes possible extension
identity collisions from bundled runtime findings; none is excluded without
image-byte confirmation. The unchanged Dockerfile retains the Python pin and
OpenVSCode's bundled Node, so a full rebuild alone is not an evidenced fix.
Supported capability removal would change the feature set and needs separate
acceptance. Astra/Max research was used for this consequential conflict, and
returned no accepted remediation. No OpenHands worker was launched.

Codex's native dynamic lookup tool and new-process thread resume through the
clean OmniRoute Responses route ran in a separate owned branch/home. Overall
class is local integration. The final cumulative 52,286-token snapshot is
counted once, cache/reasoning subsets are not added, and provider/gateway and
whole-task usage remain unknown. [Direct Claude cooperation](2026-09-30-runtime-worker-coordination.md)
reserves global pin promotion to its live owner. The original two-commit SDK
handoff has been augmented by the accounting repair described below and stays
on a separate branch pending the owner's pin merge and fresh shared-lane
review. No Gate A/P3 or trusted-observer acceptance is inferred from a peer's
scope acknowledgement.

The SDK follow-up also repairs a downstream accounting defect: merely tagging
the cumulative scope did not stop the Collector from adding start and resume
snapshots. Astra/Max verification followed the consequential accounting defect
left after a bounded Sol repair. The isolated native pipeline reproduced 78,331 and then excluded
these unbaselined totals; private results remain unchanged and native Claude
OTLP counters passed a separate positive control. The follow-up's additional
Collector paths need fresh shared-lane review. The current published follow-up
head is `404b821cd3af25800ea418dc6145cc5cb6fe33c5`, with its
`evidence/artifacts/runtime-sdk-20260930/usage-scope-receipt.json`; the historical
two-commit/ten-path replies do not acknowledge this larger diff.
Its unchanged full upstream SDK
suite retains one formatter-expectation failure, separate from the successful
native tool/resume execution and local integration fixtures.

This candidate PR is `lane:shared` because it adds a pending gate and worker
checkpoint to the shared grand-dashboard state. Foundation recipes remain
foundation-owned. The dashboard state and fresh shared hash index are placed
in the last commit, and a trading-lane acknowledgement on the final PR is
required before merge; earlier SDK scope replies do not supply it.

Corrections verified in this turn:

- The recipe-family test loaders shared generic module names and failed a
  combined run. Isolated import caches fixed the collision; the five-family
  integration run returned 226 tests, exit 0, with four dependency/opt-in skips.
- The stale SocraticCode 1.14.0 path was replaced with canonical Linux 1.15.0;
  1.16.0 remains a separately recorded candidate.
- Crawl4AI's default was legacy Chat Completions extraction. Pinned source and
  the default-dispatch regression fixture verify the correction to model-free
  crawl, with no unused route/model claim. Original native job metadata is
  retained by hash rather than rewritten.
- The foundation validator requires exactly three ranked top gaps. The first
  attempt added a fourth and failed. The new runtime gate replaces the
  previously addressed catalog-separation slot; historical catalog boundaries
  remain unchanged, and the sandbox/recovery entries are retained.
- The SDK receipt's detailed native-attempt labels lacked the canonical
  overall `local_integration` field. The separate SDK branch now adds it and
  documents the example's new default-openai max-effort setting, following the
  trading owner's conditional acknowledgement.
- The skills writer initially worked on bounded files in the coordinator
  checkout. After that work stopped, all eleven owned files were copied
  byte-identically into a separate worktree, and subsequent writing moved
  there. The coordinator retains the completed copy for integration.
- Registering the new locks exposed the existing global NLTK suppression
  guard. Fresh installed-source checks found no affected-symbol mentions
  outside NLTK or direct calls from the two current recipes. The source-only
  scope now binds the two exact lock hashes; no new advisory ID or expiry was
  added. The initial OpenHands lock also regressed PyJWT and had other scanner
  findings; those are retained for the bounded source-supported repair and
  live lock-owner review, rather than hidden by a new suppression.
- The repaired OpenHands Linux/Python 3.13.15 wheel lock passes native hashed
  installation, compatibility/import and twelve integration fixtures. Its
  native OSV scan moves from exit 1 to exit 0 with only the two existing OAuth
  suppressions. The fresh exact-lock caller review records re-exports and a
  five-line Python-2 helper's initial parse failure, with a fallback limited
  to its exact reviewed bytes. bc's independent candidate-head review was
  pending at that checkpoint and is now cited below for the corrected lock.
  The mixed worker receipt also needed a canonical overall class;
  `local_integration` now accompanies separate native/source/fixture labels,
  with its original description and receipt hash retained.
- The final inventory check found the retained compile-constraints artifact
  unlisted. The first cross-directory `covered_by_lockfile` entry failed the
  inventory's same-directory rule. Under the existing captured-fixture policy,
  the frozen reproducibility input is now explicitly classified as evidence,
  with its original hash/command and a reasoned exclusion. No recipe installs
  it; all nine active runtime locks remain scanned. The inventory rules were
  preserved, and the artifact was not renamed to evade them.
  The new main-reconciliation fixture follows the same reasoned policy. Its
  first integration check ran before Git tracked the new file and failed the
  inventory's tracked-file assertion; after staging the unchanged bytes, all
  37 inventory/classification/workflow guard tests returned exit 0.
- The native pre-commit secret gate flagged a SHA256 beside a test filename
  containing `tokens`, rather than a credential. All six values were
  independently matched against the unchanged pinned test bytes. The receipt
  now uses explicit `path`/`sha256` records, preserving every value and output;
  no allowlist or hook bypass was added. The two refused commit attempts
  returned exit 1. Dependent Git steps initially continued after refusal;
  publication now checks each exit before advancing, and the final complete
  head is verified separately.
- Another worktree advanced the shared `origin/main` ref while this checkout
  was still based on the prior main. A provisional index rebuild on that
  mismatched base failed publication validation on peer receipt metadata and
  missing peer files. The branch was rebased onto the new main before taking
  its fresh index. The registration helper now requires that the captured
  main SHA is an ancestor of the checkout and pins every read to that SHA;
  no peer receipt deletion was committed or published. This follows the
  repository's existing hot-file protocol rather than hand-merging hashes.
- Earlier unqualified `git diff --check` results covered unstaged changes.
  The full staged/branch check returns exit 2 for whitespace in retained
  native/source-output text artifacts. Those original bytes and their hashes
  are preserved under the evidence policy. The code/configuration check,
  excluding only the named captured-output paths, returns exit 0. No source
  output was silently trimmed to manufacture a clean full-diff result.
  The reconciled head has eight such output files, including its new
  OAuthlib caller listing.
- Claude's independent PR-head review found that the first lock repair used
  the unreviewed candidate as its comparison baseline, leaving three versions
  below the reviewed main lock despite no dependency forcing those decreases.
  The candidate/native scan passes remain valid within their recorded scope;
  they do not justify that source-convergence choice. Astra/Max reconciliation
  retains main's compatible Linux versions and records both baselines, with
  a fresh exact-lock installation/scan/caller review before final-head review.
  [The reconciliation receipt](../../blueprints/runtime-workers/openhands/evidence/main-reconcile-20260930.json)
  records a byte-identical pristine reproduction and 176 selected requirements:
  no additions, removals or downgrades relative to main's target-specific
  closure; only SDK/tools advance to 1.50.0. Click 8.5.0, pypdf 6.19.0 and
  Soup Sieve 2.9.2 are retained. OSV recognizes 174 requirements, omitting the
  two hash-verified direct wheel URLs. Native current-config scan is exit 0;
  empty-config control is exit 1 with exactly the two OAuthlib advisories.
  The exception scope is Linux x86_64 / CPython 3.13.15 only; the installer
  consumes the lock inside its pinned linux/amd64 image, not a native Mac venv.
  The prior candidate repair and scan remain historical evidence with their
  original bytes. The [separate review of the corrected SHA](../../evidence/artifacts/openhands-oauthlib-review-535-head6a7b16-20260930/receipt.json)
  is merged in [PR #537](https://github.com/seathatflowsinourveins/native-agent-stack/pull/537).
  Its receipt SHA256 is `c7473105255cc38bac1da6c7a490f99d863b58d865e82529d221b2a2e759908f`;
  it completes bounded source/install/scanner review, excluding worker code,
  images, provider/observer behavior and task quality. It approves no merge,
  exception, pin or promotion. The new evidence pointer preserves the lock
  bytes, existing advisory IDs and expiry dates.
- 2d corrected the earlier observer wording: no Gate A instrument was applied
  to these candidates. Its issue #381 instruments were not reclassified as
  local integration. The actual PR review checks are deterministic source
  scope/leak checks, distinct from Gate A or model acceptance.
- PR #535's [first hosted macOS validation](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/36690153586/job/109805172026)
  returned exit 1 with one recovery
  fixture failure: `interrupt` returned 3 instead of 0. The fixture passed an
  unresolved temporary path through macOS's `/var` alias, while the production
  worker correctly rejects symlinked result paths. The fixture now resolves
  its state root, following the existing `tests/test_render_config.py` pattern
  and Python 3.13's [Path.resolve reference](https://docs.python.org/3.13/library/pathlib.html#pathlib.Path.resolve).
  The production guard is unchanged; final-head hosted checks verify the
  platform result separately from the local regression run (12 tests, exit 0,
  three explicit dependency skips).
  Its [complete log artifact](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/36690153586/artifacts/11085959275)
  records 8,728 tests, one failure and 1,122 skips; uncompressed log SHA256 is
  `ba7d68e9886c778bcc7cec0ce7030967d9563f2a861de741b6e38469c5ebff4f`.

Broader adoption is contingent on maintained image remediation, a trusted
host-owned observer, frozen task-quality controls and complete attempt/judge
metering. A matched comparison can overturn the retained SDK default; this
implementation makes no convergence-superiority or token-saving claim.
