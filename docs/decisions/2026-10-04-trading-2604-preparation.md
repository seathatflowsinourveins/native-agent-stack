# 2026-10-04 — Package the NativeStack2604 offline research runtime

North-star action: retain the selected NautilusTrader 2.0.0rc5 research and
historical-simulation runtime as a portable, source-cited recipe with truthful
host-local evidence, preserving separate IBKR and Alpaca paper qualification.

## Historical round-1 decision and sources

Package job-031's repaired scripts under
`blueprints/us-equities/runtime-2604/`, with their required sibling
`trading-2604-runtime/` project. Follow existing feature recipes such as
`blueprints/us-equities/research-runtime/` and the retained native rc5 receipt
`evidence/receipts/native-nautilus-v2-20260920.json`. Reuse the repository's
`scripts/host_receipts.py`, `adoption/host-receipt.schema.json`, publication
validators and evidence registration helper at packaging base
`38ac9aca114ad9ef4a15d8620d947eb5c2f518c3`; no new recorder or test runner is added.

The bounded search-first pass found those existing packaging and recording
interfaces sufficient. No package, skill or runtime replacement is selected and
no network discovery or new trial is needed for this archival unit. The exact
upstream pins and file locators inherited from the preparation are in the
[runtime README](../../blueprints/us-equities/runtime-2604/README.md) and scripts.
They include [uv 0.12.17's project workflow](https://github.com/astral-sh/uv/blob/0.12.17/docs/guides/projects.md)
and [lock semantics](https://github.com/astral-sh/uv/blob/0.12.17/docs/concepts/projects/sync.md),
the [unchanged rc5 quickstart at 1b0a49d2](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/getting_started/quickstart.py),
the [Alpaca source at dca821cc](https://github.com/seathatflowsinourveins/native-agent-stack/blob/dca821cca85dce3647fa7b488d5a23fbe5b85d4a/blueprints/us-equities/adaptive-paper/native_adapter.py),
[Git 2.43.0 sparse checkout](https://github.com/git/git/blob/v2.43.0/Documentation/git-sparse-checkout.txt),
[Docker v29.8.1 context inspection](https://github.com/docker/cli/blob/v29.8.1/docs/reference/commandline/context_inspect.md)
and [Bubblewrap v0.9.0](https://github.com/containers/bubblewrap/blob/v0.9.0/bubblewrap.c).

Keep CPython **3.12.3**, uv **0.12.17**, all 14 direct requirements, the MCP and
pandas extras, source pins and immutable OCI image indexes as delivered. The
515-byte project and 353,069-byte lock remain byte-identical to the staged copies:

| File | SHA256 |
| --- | --- |
| `pyproject.toml` | `581bbb38a265068791c1a8c92435f9859876fd613d3c2c87d618a223376b01e0` |
| `uv.lock` | `c6b5f25cd3198c1b847c1cb602fe5441dce7e038aa16976c46ecf5f0beb7b086` |

The 242-entry lock retains cutoff `2026-10-06T04:00:00Z`. Delivering and checking
the actual lock prevents a fresh resolution against that future cutoff. The
canonical runtime target remains a selected engine plus Python compatibility
range; this receipt does not ratify an exact patch or complete canonical matrix.

Alternatives were a global install, a fresh target-host resolution, the
foundation's 3.13.15 supplemental Python pin, a newer arbitrary 3.12 patch,
replacement analysis tools, or treating a container pull as a replacement LEAN
oracle. The retained approach follows the requested scope and the
[adapter's tested Python 3.12 line](https://github.com/seathatflowsinourveins/native-agent-stack/blob/dca821cca85dce3647fa7b488d5a23fbe5b85d4a/blueprints/us-equities/adaptive-paper/requirements.txt)
and earlier rc5 execution on 3.12.3. A frozen same-input 3.12.3-versus-3.13
comparison with better upstream support and passing engine/adapter behavior would
overturn this supplemental choice, with a new verified lock and trading-lane
ratification. A newer release or successful import alone is insufficient.

## Preparation, review and corrections

The staged decision and readiness documents record a preparation phase without
runtime execution. Its initial 3.13.15, 203-entry lock was superseded by repaired
3.12.3 metadata and the delivered 242-entry lock with `mlflow[mcp]==3.16.1`.
The supplied r1 Claude verdict contains two P1 findings, one P2 finding and 15
residuals. Repaired code uses an indexed pinned sparse checkout before checking
cleanliness, preserves the selected rootless Docker endpoint across `env -i`,
and calls core utilities natively. It also gates acceptance on completion and
both exact images, verifies adapter source before import and cleans pending
temporaries through its final status handler.

The preparation records public checkout, trap-fragment and dependency-metadata
proofs. Those scratch artifacts were not staged for packaging and are not
promoted into newly verified public execution. The supplied handoff reports the
second Claude read of r2 as PASS; its verdict file was not supplied. That review
of prepared files is separate from independent observation of the later run.

Two coordinator corrections are substantiated by the retained host logs:

- The host default uv **0.12.22** fails the required **0.12.17** version gate at
  exit **69**. `mise exec uv@0.12.17` supplies the pinned tool; the next attempt's
  native version output reports 0.12.17. Exact uv source guidance is linked above.
- `uv python find --managed-python` conflicts with the already supplied
  `UV_PYTHON_PREFERENCE=only-managed`: native output reports the argument conflict
  and install exit **2**. The final command keeps `--system --no-project
  --no-python-downloads` and removes the redundant flag. The final install exits
  **0**. Both corrections are preserved in the scripts and dated run receipt.

The original export concern was corrected during preparation by reading the
complete [Rust/PyO3 registration](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/adapters/interactive_brokers/src/python/mod.rs#L98)
behind the Python facade. The offline `ibkr_adapter` row later passes its named
imports; that is config/export acceptance, not a broker connection.

## Historical evidence and publication

The [companion receipt](../../evidence/receipts/native-trading-runtime-2604-20261004.json)
is `native_cli_e2e`, retaining all 25 rows, software pins, exact staged summary,
sanitized outer logs and both unsuccessful attempts. The separate
`host_acceptance` receipt follows the one-component/one-host/one-stage schema for
the landscape winner **nautilustrader**, scoped to native offline engine use.
It records the combined successful install/accept batch at stage `use`, because
the staged timestamps measure that batch rather than each script separately.
The normalized sequential command display and the combined **373 s** duration
are explicitly bounded; individual script durations and the outer coordinator
argv were not staged. No install-only host receipt with an invented duration is
created. The host is another WSL distribution, with no evidence of a second
physical machine; `second_physical_machine` is false.

Host class `native_proven` covers the unchanged native engine example. Local
import/version/hash/isolation probes and transcribed examples are separately
labelled `local_integration`; synthetic FX/three-row inputs and bundled SP500
fixtures retain their input limitations. Structural publication checks do not
repeat the run. No broker, paper account, market-data request, provider inference,
container execution, strategy merit or new upstream-suite pass is claimed.

Publication replaces five home-path occurrences in the successful outer log
with `~`, preserves native status/exit lines and all public source/image hashes,
and hashes only published sanitized output. Private source-job state paths,
account identifiers and raw review conversations are excluded. Every touched
publication file is scanned explicitly and registered last with `register_file`;
derived host reports use only their supported `--write` commands. The dated
runtime-target followup records evidence without moving selections or gates.

Packaging correction: the first transcription assertion failed at exit 1 because
its status-name character class admitted a newline. Anchoring each row with a
non-whitespace name corrected that parser; the second import exited 0 and checked
all 25 named native rows against the staged summary. This was an archival parsing
correction, not a new failed or successful host acceptance attempt.

The first full publication validation also exited 1: its home-path pattern
mistook the synthetic sandbox cache path for a personal user directory. The
published acceptance script now names its existing synthetic home through
`sandbox_home` and expands that variable in the same mount/environment arguments.
The actual sandbox argv is unchanged. The validator is preserved, and this
source-representation change is covered by renewed syntax and publication scans.

The guarded Gitleaks launcher exited 1 before scanning because it opens the
existing per-user runtime lock for writing in a read-only directory. The installed
8.30.1 native `dir --help` and launcher source were read. A native retry retained
that same lock through a read-only descriptor, but exited 2 before scanning:
a 4 GiB virtual-address cap could not accommodate RE2/WASM's 4 GiB reservation
plus the runtime. Raising that process cap to 6 GiB, matching the launcher's
maximum, preserved the exclusive lock, 60-second native timeout and nice 19;
the scan of the isolated 21-file publication copy exited 0, scanned about
3.78 MB and found no leaks. No host launcher, lock file or configuration changed.
This reuses [Gitleaks v8.30.1](https://github.com/gitleaks/gitleaks/blob/v8.30.1/README.md)
and the repository's [documented bounded directory-scan practice](../../adoption/tools/README.md).
Both failed scan conditions remain distinct from runtime acceptance.

The staged result summary has no final newline; its bytes are preserved. All
published new files have zero trailing whitespace. The separate `git diff
--no-index --check /dev/null FILE` checks returned the expected difference exit 1
for each new file with no whitespace diagnostics; the working-tree
`git diff --check` passed at 0.

The required scoped ai-memory lookup was attempted with `pin_first=true,
limit=2` and rejected by automatic approval review: the tool requires approval
while this session's policy is `never`. No memory result is claimed. Current
canonical files and original staged artifacts supply this packaging evidence.

## Historical round-1 open comparisons and completeness critic

Ratifying **Python 3.12.3 against 3.13** remains open. The **EdgarTools 5.59.1
overturn test** also remains open before changing catalog 5.58.0. It must examine
the relevant 10-K/10-Q section boundaries and 10-K breadcrumb regression, as
identified by the preparation's
[5.59.0](https://github.com/dgunning/edgartools/releases/tag/v5.59.0) and
[5.59.1](https://github.com/dgunning/edgartools/releases/tag/v5.59.1) references
and definitive source supplement. This offline run exercises neither filings
nor that comparison. Canonical matrix ratification, point-in-time data, realistic
chronological evaluation, LEAN oracle parity and separate rc5 IBKR/Alpaca paper
risk, recovery and operational qualification remain open.

Completeness critic: preserve failed attempts as well as the green summary;
separate the synthetic/bundled input modality from actual native execution;
retain the delivered lock rather than treating the future cutoff as a freeze;
and distinguish pre-run review from missing post-run observation. The next
trading-lane qualification should target the Python and EdgarTools comparisons,
per-check native logs, missing discriminating controls for local smoke checks,
domain data, broker recovery and source-to-image/oracle parity. Packaging performs
no new landscape convergence comparison, broker/provider call or runtime trial.
Independent review of the imported host receipt remains explicitly requested.


## 2026-10-04 — EdgarTools 5.58.0 to 5.60.0

North-star action: use the accepted current release for source-identified SEC
filing research while preserving historical native execution, point-in-time
limitations and separate paper/strategy qualification. This directed pin move
uses the existing uv project commands, publication validators, recipe/version
checks and evidence-registration helper. The bounded search-first and
modern-python skills supply workflow guidance; upstream release metadata and
returned native output supply the evidence. No custom test runner or CI job is
added.

The [v5.60.0 tag](https://github.com/dgunning/edgartools/tree/1e7a61b3a142dbf5d19bc82444f85239c1786348)
is **1e7a61b3a142dbf5d19bc82444f85239c1786348**, confirming the command center's
1e7a61b prefix. The release was published **2026-10-02T18:29:57Z**. The
[PyPI version metadata](https://pypi.org/pypi/edgartools/5.60.0/json) records:

| Artifact | SHA256 | Upload time (UTC) |
| --- | --- | --- |
| `edgartools-5.60.0-py3-none-any.whl` | `4db917f3833f6b105fe78d22639172410c800ad6da260432884d86b53b88439b` | 2026-10-02T18:28:56.985693Z |
| `edgartools-5.60.0.tar.gz` | `0ce57d5b08484313e564af6c0f40b1bc43a8b90b68b96d017a62b62d80836677` | 2026-10-02T18:28:58.846406Z |

Both files are unyanked. The retained
[release evidence](../../evidence/artifacts/edgartools-5600-20261004/release-evidence.json)
contains exact GitHub issue queries/counts/hits and all check suites at the tag.
The searches cover every open issue from October 2 (conservatively the entire
release day), plus open bug/regression-labelled issues naming 5.59, 5.59.0,
5.59.1 or 5.60.0 in title/body/comments. The one recent hit,
[issue 1413](https://github.com/dgunning/edgartools/issues/1413), concerns MCP
Registry launch metadata referencing 5.21.1; it does not report a defect in this
runtime's native SEC APIs. No requested-version regression was found in those
searches. This is a dated query result, not proof that every API is defect-free.

### CI assessment and the initial stop

Release-day push CI on the tag commit was green:
[Build and Test 37032606429](https://github.com/dgunning/edgartools/actions/runs/37032606429)
and [Regression Tests 37032606490](https://github.com/dgunning/edgartools/actions/runs/37032606490),
both October 2. The October 3
[scheduled Build and Test 37122012086](https://github.com/dgunning/edgartools/actions/runs/37122012086)
failed on the same commit. The first packaging attempt correctly stopped under
the release gate, because inspecting all check suites exposed that failure even
though the eleven-context `statusCheckRollup` was SUCCESS.

The coordinator subsequently diagnosed the failure and explicitly authorized
continuation. The same two tests appear in all three failed jobs:
`tests/issues/regression/test_issue_893_ttm_staleness.py::test_goog_ttm_revenue_tracks_recent_window`
and `::test_amzn_ttm_revenue_matches_reference`. In `test-strict-errors`, the
assertion `ttm.is_stale is False` fails: recorded periods end at Q1 2026, whereas
the default staleness check reads today's clock. In `test-fast` on 3.10 and 3.13,
the offline audit identifies these two fast-marked tests as needing SEC access.
The GitHub failed-job logs were read and corroborate both the assertion/periods
and the identical two audit names. The cassette recording date is July 9; the
March 31 quarter crosses the 185-day age boundary on the scheduled run date.

The [first test-clock fix](https://github.com/dgunning/edgartools/commit/9ea5def31b73816a12fe6ce1a2f3ff68cbdbb33b)
and [calculator-only fix](https://github.com/dgunning/edgartools/commit/156c45b327a65e4c86ebfc7652edb778de5cecd8)
each modify only `tests/issues/regression/test_issue_893_ttm_staleness.py`.
Both exact commit file lists were verified with GitHub REST, which was available
for these calls despite the earlier quota concern. The first fix freezes the
process clock; the second confines the patch to the calculator because a frozen
process clock also affects the HTTP rate limiter. These are test-only repairs.
`Company.get_facts().get_ttm_revenue()` staleness lies outside the filing index,
filing documents, SGML headers, company/CIK lookup and XBRL fact extraction that
this runtime relies on. The coordinator's assessment is therefore a
clock-dependent cassette test failure, not a library regression in those paths.

[Scheduled Build and Test 37204026582](https://github.com/dgunning/edgartools/actions/runs/37204026582)
on October 4 succeeded at main
`237e866a80ab3013cf5aa25a2557cf73c4eb61e4`. The
[tag-to-main comparison](https://github.com/dgunning/edgartools/compare/1e7a61b3a142dbf5d19bc82444f85239c1786348...237e866a80ab3013cf5aa25a2557cf73c4eb61e4)
also contains library changes to `edgar/documents/utils/section_slicer.py` and
`edgar/httprequests.py`, **neither of which is in 5.60.0**. That later success
corroborates the test repair; it is separate from release-day tag CI and does not
claim those library changes are shipped in this runtime.

### SEC behavior, offline fixtures and native acceptance

The [5.59.0 notes](https://github.com/dgunning/edgartools/releases/tag/v5.59.0)
fix table-of-contents section boundaries and adjacent-cell rendering, preserve
SGML HTTP failures instead of caching empty headers, and correct XBRL debt and
dimension handling. The [5.59.1 notes](https://github.com/dgunning/edgartools/releases/tag/v5.59.1)
repair the 5.59.0 10-K breadcrumb regression and the MCP 13F holdings section.
The [5.60.0 notes](https://github.com/dgunning/edgartools/releases/tag/v5.60.0)
add current-filings timeouts, preserve combined 10-K items, normalize paragraph
whitespace and correct document/exhibit matching, 8-K signatures, XBRL liability
fallbacks, ownership and BDC totals. These can alter text spans and derived
values, so research artifacts retain their parser version and input hashes.
The MCP-specific fixes are release context, not an MCP acceptance claim here.

The coordinator's supplied offline outputs are retained under
`evidence/artifacts/edgartools-5600-20261004/`, with their artifact hashes and
scope in the [pin-move receipt](../../evidence/receipts/edgartools-5600-pin-move-20261004.json).
They ran on NativeStack in a scratch 42-package uv environment without a SEC
identity. `native_edgar --fixture` completed with cohort 2; `native_document`
completed on the pinned upstream HTML fixture. Markdown is **5,308 bytes** at
5.60.0 versus **5,325** at 5.58.0 and 5.59.1. The retained diff removes only
source-HTML soft line breaks; the coordinator's comparison reports identical
whitespace-normalized text at **5,218 characters**. The old Markdown SHA256 is
`0c7253e2ffaf1937296fdccf9b297994e86ecae233b13b5a9c4dd438859117f8`;
the new one is
`84b950871931d894596224602d5aa7fe4fcd73f765c5cff2f80dbffcc9767143`.
These are **local offline-fixture** results, not SEC network acceptance or
historical information availability. Full Markdown inputs were not supplied to
this builder, so the 5,218-character comparison remains attributed to the
coordinator rather than a newly reproduced comparison.

The separate, supplied
[native-sec-edgartools-5600-20261004 receipt](../../blueprints/us-equities/catalyst-provenance/native-network-edgartools-5600-20261004.json)
records native SEC acceptance on **NativeStack**, not NativeStack2604, at
22:29Z: CPython 3.12.3, one GET answered 200, zero automatic retries, 371 index
rows, and the same five selected CIK/accession rows as September 19 and September
24. Its measured content and the accepted 42-package `requirements.lock` remain
byte-for-byte as provided. That freeze moves EdgarTools 5.58.0 to 5.60.0,
filelock 4.0.1 to 4.0.10, MarkupSafe 3.0.3 to 3.0.4 and soupsieve 2.9.2 to 2.10;
those are the supplied environment's observations, not requirements imposed by
the runtime relock. The native request did not run `catalyst.py acquire/packet`,
remeasure unique-accession counts or accept a historical trading universe.

This accepted release supersedes the proposed **5.59.1 overturn test**. The
`data-edgartools` catalog, stack selection, current architecture plan and runtime
bundle move together to 5.60.0. The runtime-target open item is resolved with
receipt id `native-sec-edgartools-5600-20261004`, without advancing data, strategy,
paper or broker gates. Historical 5.58.0 receipts, dated review records, frozen
experiments and SOTA verdict waves remain unchanged. Current code/recipe version
checks move with their existing tests; newly generated evidence must use new
anchors. The classification inventory identifies each preserved historical pin
and each current pin that moved.

### Runtime reproduction and remaining scope

The runtime retains **CPython 3.12.3**, uv **0.12.17**, prerelease mode
**if-necessary** and cutoff **2026-10-06T04:00:00Z**. The cutoff appears in the
installer and lock options; it already includes October 2's 5.60.0 publication,
so it is unchanged. Only EdgarTools is permitted to upgrade during this relock.
The runtime already locks filelock 4.0.10, MarkupSafe 3.0.4 and soupsieve 2.10;
its dependency movement is recorded independently from the supplied SEC freeze.

The [complete lock comparison](../../evidence/artifacts/edgartools-5600-20261004/runtime-lock-change.json)
records these changed entries:

| Entry | Old | New | Reason |
| --- | --- | --- | --- |
| edgartools | 5.58.0 | 5.60.0 | Directed upgrade to the verified release; existing dependencies satisfy it. |
| us-equities-runtime | 0.1.0 | 0.1.0 | Only the direct requirement metadata changes; project version stays unchanged. |

All other **240 entries are unchanged**, with no added or removed package.
The new lock SHA256 is
`6b4e6a4d4fc61cbda56c36d1ee0c65c263a5e938d968ce2806cc32330a8335f1`;
the new project SHA256 is
`f71b08811eb580cf5c3772da7327ec5554154b81839b80c6259d69eae6bd1338`.

The requested `mise exec uv@0.12.17 -- uv lock` invocation exits **127** on
this worker: no Linux mise executable was found. The installed native
**uv 0.12.17** performs `lock --upgrade-package edgartools` and `lock --check`,
both exit **0**, with Python request 3.12.3, no interpreter download, prerelease
if-necessary, the PyPI default index and the unchanged cutoff. This records the
route difference explicitly; verification through the prescribed mise wrapper
remains pending. The target-host recipe retains that wrapper and its uv version
gate. No replacement shim was created.

The [this-host import smoke](../../evidence/artifacts/edgartools-5600-20261004/this-host-import-smoke.json)
exports the locked EdgarTools dependency closure with uv, builds a throwaway
CPython 3.12.3 venv under TMPDIR and syncs 42 applicable Linux distributions
with `--require-hashes --only-binary :all:`. Its universal export has 44 entries;
colorama and tzdata have Windows markers. In an environment cleared by
Bubblewrap with networking disabled and home masked, the exact import/version
probe from acceptance prints **5.60.0**, exit **0**. The same probe expecting
5.58.0 fails with the observed version pair, exit **1**. Project-environment
`uv pip check` passes, exit **0**; the two affected recipe test modules pass
26 tests, 5 skipped, including the native 5.60.0 HTML/SGML test. This is local
integration evidence on this worker, not NativeStack2604 acceptance.

The first Bubblewrap smoke attempt could not create a bind destination under
the read-only root (exit **1**); putting the bind inside private `/tmp` resolves
it. The first dependency-check attempt used a read-only default uv cache
(exit **2**); setting UV_CACHE_DIR under TMPDIR resolves it. These setup failures
and the discriminating version control remain recorded next to the passing
probe. Neither setup failure reached a library import or SEC request.

The installer removes its stale unpinned source-snapshot header, cites the
5.60.0 tag commit, verifies the current bundle's hashes, and accepts migration
only from the exact previously recorded project/lock hashes. It checks both
files before replacing either; mixed old/new verified files allow recovery from
an interrupted atomic replacement. Unknown edits, symlinks and unowned files
fail closed. A new completion marker is shared with acceptance, so the previous
completed install cannot satisfy the new preconditions. The existing mise route
supplies pinned uv for `lock --check`, `sync --locked --no-dev` and project-env
`pip check`, with errors stopping installation. No host guard is bypassed.

The earlier **NativeStack2604** install and 25/25 offline run used **5.58.0** and
lock SHA256
`c6b5f25cd3198c1b847c1cb602fe5441dce7e038aa16976c46ecf5f0beb7b086`.
Its receipt retains those measured facts and adds current-bundle/pending-rerun
metadata separately. The command center will rerun the 5.60.0 runtime on that
host and record a separate receipt. This builder performs only the requested
this-host import smoke and publication/code checks; it makes no SEC, broker or
provider request.

Alternatives were retaining 5.58.0, taking only 5.59.1, or adopting unreleased
main to incorporate its later library changes. The directed 5.60.0 release with
bounded native SEC acceptance meets the latest-clean-release rule without
adopting main. A reproducible failure in the selected SEC paths, mismatched
release artifacts or failed NativeStack2604 rerun would overturn readiness and
require a new reviewed pin/receipt; unrelated CI success cannot substitute for
that evidence. CPython **3.12.3 versus 3.13** ratification remains open.

Completeness critic: distinguish tag CI from later-main CI and test defects from
library changes; keep offline fixtures, native SEC access and a this-host import
separate; preserve the previous host run's version and hashes; keep frozen
reviews/experiments intact; inventory code pins and generated views as well as
catalog rows. The next unit is the NativeStack2604 rerun and its own receipt,
with all existing data, strategy, oracle and broker qualifications still separate.

Packaging correction: the first nested-output hash check appended a newline
that the upstream `json_bytes` serialization does not write, and failed at exit
1. Removing that invented byte matches the supplied receipt's declared SHA256;
the corrected consistency check exits 0. The supplied measured files were not
changed. The installed uv command is a native executable, so CLI help is its
capability reference; reading it as a text launcher produced unusable binary
output and was abandoned. Scoped ai-memory remains unavailable under the
session's never-approval policy; current canonical files and original source
artifacts supply the evidence.

Packaging correction: the first recipe test run exited 1 (72 tests; 15 errors,
1 failure, 7 skipped). It exposed that the dated local-inference acquisition
recipe is a frozen experiment input, hash-bound by its plan and ledger. Its
code and README were restored byte-for-byte from the round-1 base and the pin
inventory now classifies them as historical. The private-output guard also
refused test outputs because this worker has empty `.git` directories above
TMPDIR. Re-running the unchanged unittest harness in Bubblewrap with a fresh
private `/tmp` and no network preserves the production guard and passes all
72 tests (6 skipped), exit 0. No Git environment variable caused the refusal.
The installed uv 0.12.17 help lists both `--frozen` and `--no-sync`, but their
combination is rejected (exit 2); `uv add --frozen` alone changes only the
direct pin without a preliminary resolution or sync (exit 0).

## Hash-pinned legacy build and shared sync — 2026-10-04, round c

This implements trading unit T's PR-1 build closure for the research and
historical-simulation runtime. The round-b2 base is `c435671f8`; its 5.60.0 lock
SHA256 is `6b4e6a4d4fc61cbda56c36d1ee0c65c263a5e938d968ce2806cc32330a8335f1`.
The final lock SHA256 is
`4c98672d14147a1be712bf788b495cf318705631cbf5e04ebe230c8a13c516c2`.
All **242 package entries and their archive metadata remain unchanged**; the
relock only adds the manifest's hashed build constraint.

`antlr4-python3-runtime==4.9.3` is the one nonvirtual distribution without a
wheel. Its sdist has no project build-system declaration, so
[uv 0.12.17's legacy backend](https://github.com/astral-sh/uv/blob/0.12.17/crates/uv-build-frontend/src/lib.rs#L53-L60)
would separately resolve `setuptools>=40.8.0`. Following the
[project build-hash documentation](https://github.com/astral-sh/uv/blob/0.12.17/docs/concepts/projects/build.md#L61-L79)
and [schema](https://github.com/astral-sh/uv/blob/0.12.17/uv.schema.json#L788-L815),
the project's constraint pins `setuptools==84.0.0` with exactly the existing
runtime lock entry's wheel and sdist hashes. The lock records that constraint,
[checks it against the project](https://github.com/astral-sh/uv/blob/0.12.17/crates/uv-lock/src/lock/mod.rs#L4162-L4190),
and [applies it during builds](https://github.com/astral-sh/uv/blob/0.12.17/crates/uv/src/commands/project/sync.rs#L860-L896).
The explicitly authorized native **uv 0.12.17** performs this relock because
mise is unavailable here. Managed CPython **3.12.3**, `--no-config`, prerelease
`if-necessary`, the PyPI default index and `exclude-newer=2026-10-06T04:00:00Z`
are retained. No other package may move under this change.

[tests.test_trading_2604_lock](../../tests/test_trading_2604_lock.py) validates
the normalized manifest/project constraint, its exact runtime-backend pin and
archive hashes, and the one-sdist census, excluding virtual project metadata.
Four planted fixtures each fail: a second package without a wheel, a different
backend version, missing hashes and a mismatched manifest. The host/CI vector
is now defined once in
[sync-trading-2604.sh](../../blueprints/us-equities/runtime-2604/sync-trading-2604.sh),
following [validate.yml's install-command pin reuse](../../.github/workflows/validate.yml#L196-L225).
The installer verifies that file's hash, sources it and calls the function;
future PR-2 CI can call the same source with its own clean environment and
managed-interpreter/project paths. Tests compare every argv byte, reject copied
or altered installer steps and a stale source digest, and prove that each of the
three failures stops the sequence. No workflow is added in this round.

The [build-constraint proof](../../evidence/artifacts/trading-runtime-2604-20261004/build-constraint-proof.json)
retains native results and controls from scratch copies on this worker. The
shared function's lock check, cold-cache locked/no-dev sync and dependency check
all exit **0**; 238 applicable distributions install on Linux, and antlr4's
installed WHEEL reads **`Generator: setuptools (84.0.0)`**. NC-1 changes one
project digest and exits **1** at `lock --check`. A fresh NC-2 resolution with
only an invalid digest exits **1**, with a setuptools hash mismatch. NC-3 puts
that same invalid-only allowlist in project and manifest while preserving all
runtime package hashes; cold-cache locked sync exits **2**, with no overlapping
setuptools hashes. These are local integration and structural evidence, with no
host installer, SEC request, paper run, broker or provider operation.

Control correction: the first NC-2 and NC-3 mutations kept the correct sdist
hash beside the incorrect wheel hash; both exited **0**. That was an allowed
alternative, rather than an invalid-only allowlist. The native
[hash combination rules](https://github.com/astral-sh/uv/blob/0.12.17/crates/uv-types/src/hash.rs#L577-L620)
verify a matching allowed archive and intersect runtime/constraint hashes.
The corrected controls permit only the incorrect digest; NC-2 also removes its
scratch lock to force backend artifact resolution. Those preliminary results
are retained alongside the final controls. A WHEEL read issued before a yielded
sync finished exited **1** with missing distribution metadata; waiting for
completion and reading the installed metadata returned **0**. It was a premature
observation, not a sync or library failure.

Alternatives were leaving the legacy backend unconstrained or creating a second
pip lock. A constraint in the existing lock closes the one demonstrated build
gap with one dependency source. A new no-wheel distribution, changed backend
requirement, mismatched hash/manifest or reproducible failure of the final
NativeStack2604 rerun would overturn this closure and require a reviewed update.
The current installer recognizes only the final and exact approved round-1/b2
metadata hashes and uses a new completion marker shared with acceptance.

The original **25/25 summary is pre-relock evidence** at EdgarTools 5.58.0 and
its original lock hash; every measured receipt field remains unchanged. The
NativeStack2604 install/offline rerun on the final 5.60.0 lock is now recorded
in [native-trading-runtime-2604-rerun-d02c0827-20261005](../../evidence/receipts/native-trading-runtime-2604-rerun-20261005.json):
install PASS and 25/25 offline acceptance PASS at `d02c0827`, lock
`4c98672d14147a1be712bf788b495cf318705631cbf5e04ebe230c8a13c516c2`,
on **2026-10-05, 01:00:17Z–01:01:07Z**, through `mise exec uv@0.12.17`.
This dated follow-up resolves the rerun and target-host mise verification
pending in the earlier preparation sections. Independent review remains
pending. The supplied native SEC acceptance at 5.60.0 remains separate and
valid; catalog selections and gate status do not change here.
Python 3.12.3 versus 3.13 ratification and the earlier independent-receipt-review
qualification remain open.

The rerun receipt scopes `native_proven` to the unchanged `nautilus_quickstart`
row and `local_integration` to the other 24 destination-host rows. Its per-row
status lines remain private on the host; a sanitized row artifact is requested
from the operator. The outer summary is retained without inventing row data.

Resume after storage interruption: the coordinator removed the earlier scratch
state. The four completed proof results and output were already recorded, and
their project/lock/shared-source hashes still match; those results are reused.
Subsequent scratch uses `~/.cache/t2604-c`, with sequential proof operations,
at least 60 GiB free before cold sync, and immediate scratch cleanup after each
recorded outcome. No full cold-cache runtime sync was repeated. The targeted
contract tests pass 11/11, and catalyst-dataset passes 14/14 without skips in
an offline CPython 3.12.3 scratch environment using the lock's DuckDB/pytz hashes.

Test setup correction: native uv 0.12.17 rejected `--prerelease` on `pip sync`
(exit **2**); its installed `pip sync --help` (exit **0**) supplies the supported
test-only command. The first dataset run skipped four checks without DuckDB;
the next DuckDB-only run exited **1**, with three missing-`pytz` import errors.
Adding already locked, hash-verified pytz to that scratch environment passes
all 14 tests, exit **0**. Every scratch environment/cache was removed after its
result was recorded. These corrections change no runtime dependency or sync flag.
