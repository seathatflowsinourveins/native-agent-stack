# Runtime source convergence follow-up — 2026-09-30

Decision: retain the accepted native defaults and the unresolved runtime
acceptance gates; finish the exact-lock citation cleanup and prepare a
supported, bounded image trial. Source-only changes preserve the separate
client/SDK qualification scopes. No host deployment or
model run is implied. This follows
[the convergence architecture](../convergence-architecture.md), the
[acceptance evidence policy](../acceptance-evidence-policy.md) and the
[coordination receipt](2026-09-30-runtime-worker-coordination.md).

## Completed source review

[PR #537](https://github.com/seathatflowsinourveins/native-agent-stack/pull/537)
merged at `11227bfdf25b55b0481a9e78985c3fed26052472`. Its independent
[receipt](../../evidence/artifacts/openhands-oauthlib-review-535-head6a7b16-20260930/receipt.json)
has SHA256 `c7473105255cc38bac1da6c7a490f99d863b58d865e82529d221b2a2e759908f`
and binds the OpenHands lock
`383ccc5b87702174e471732872f002f1621186710402d048acc2b1910306e106`.
It covers the corrected main-version comparison, Linux x86_64/CPython
3.13.15 installation, static OAuth callers and native scanner controls.
It excludes worker/dispatch code, images, provider/observer behavior and task
quality, and approves no merge, exception, pin or promotion. The suppression
guard and recipe now cite this exact review; the lock, advisory IDs and expiry
dates remain unchanged. Earlier records retain their original dates and bytes.

## Primary research and remaining tests

The [v1.50.0 release](https://github.com/OpenHands/software-agent-sdk/releases/tag/v1.50.0)
is the inspected stable source. A native registry manifest inspection returned
the unchanged full-image digest recorded in
[the triage receipt](../../blueprints/runtime-workers/openhands/evidence/image-triage-20260930.json).
Its historical report returned native exit 0 and 56 fixable high/critical
matches; the command did not request a severity threshold. The acceptance
rule remains unmet, distinct from that successful report generation. The
[subsequent source comparison](https://github.com/OpenHands/software-agent-sdk/compare/dcf401af7a9a302ef92cb7d092e1df9bb659daa5...230115adcf4b06ccab20a932bf632cd79dd13bef)
has no Dockerfile repair. The native
[builder](https://github.com/OpenHands/software-agent-sdk/blob/dcf401af7a9a302ef92cb7d092e1df9bb659daa5/openhands-agent-server/openhands/agent_server/docker/build.py)
supports a browser-only composition; its
[Dockerfile](https://github.com/OpenHands/software-agent-sdk/blob/dcf401af7a9a302ef92cb7d092e1df9bb659daa5/openhands-agent-server/openhands/agent_server/docker/Dockerfile)
still installs CPython 3.13.15 and a separate managed interpreter.
Removing optional capability packages or overriding the base image alone
does not establish a complete remedy. The
[planned experiment](../../blueprints/convergence-practice/runtime-image-browser-20260930/README.md)
therefore has no observations, qualifications or usage claim. It freezes
the supported source, current inputs and quality rules before an eventual
isolated, model-free native build/scan. The full-image gate remains open.

The maintained
[benchmark source](https://github.com/OpenHands/benchmarks/tree/405bae7140d7e961a75f4910a0b2e7069731db96)
supplies native SWE-bench and GAIA grading paths, with a different pinned SDK
that requires compatibility qualification. In-process Laminar telemetry is
not independent observation. Installed server help and the inspected tag
source did not reveal a turnkey host-owned observer for this contract;
[remote local-workspace issue #4187](https://github.com/OpenHands/software-agent-sdk/issues/4187)
closed without establishing that capability. Observer and task-quality
acceptance remain separate from source/install acceptance.

The stable Codex Python SDK at `rust-v0.159.2`, commit
`ff6aec96948b70d94983af2641a6b67c94faeff5`, retains a disagreement between
[the formatter](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/scripts/format.py#L43)
and [its artifact test](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/tests/test_artifact_workflow_and_binaries.py#L241).
Both files are byte-identical in inspected upstream main
`67727e7cf114cf3e1b71db368d74b24e32f6cb12`. No supported repair was found
in those sources. The unchanged native result stays one failure, 266 passes
and 38 skips, exit 1; local lint/format success cannot replace that outcome.
No test is patched or filtered to claim full-suite acceptance.

## Coordination and publication boundary

The owned native Opus/max relay obtained actual replies from the client-pin,
dependency, trading and measurement owners and the other runtime session.
The other runtime session reports no owned files, branch, service or gate in
this work, so there is no implementation overlap to hold. These reported
ownership statements are coordination evidence, not upstream acceptance.

The client-pin owner's [PR #542](https://github.com/seathatflowsinourveins/native-agent-stack/pull/542)
actually merged at `2026-09-30T19:54:23Z` as
`1f2cdce5a3cdf3f965d45196d8158d12431394d2`, independently verified through
native GitHub metadata. The SDK source at
`404b821cd3af25800ea418dc6145cc5cb6fe33c5` is retained unchanged while a new
isolated publication worktree uses that merged base. Rebuild shared evidence last, open the separate
`lane:shared` draft and obtain trading-owner acknowledgement and measurement
owner source-scope review. Preserve the example's explicit Astra model and
the cumulative-usage repair. Its Collector change is repository source only;
deployed private configuration and native OTLP counters remain separate.

The measurement owner's actual second reply permits source-only cleanup
and the separately sequenced SDK draft. It accepts a Docker/one-worker/
12-iteration/frozen-ID plan now, with no build or run. Eventual execution
requires its host-load agreement, an existing rootless Docker context,
native Codex capacity of 40–45 free weekly points at that preflight, bc's
gateway agreement and start/end notices. The sealed Codex arms retain
explicit `gpt-6-astra` unless the user changes the sealed runbook through
an amendment. No model-choice intake is needed for this source work.

Collector deploy/restart needs a separately dated notice at least six hours
before the seal announcement or must wait until all windows close; it never
occurs inside a window. Source review/merge gives no deployment authority.
The owner will notify live peers, publish a dated U6 Amendment 4 PR comment
and record the sealed README pre-run notice. No U6 date was supplied and
both owners require PR #542 to merge before that cut. Historical host-actor
attribution remains unknown and does not block source-only work. Timestamp
coincidence is not attribution. No account capacity, authentication store or
historical private conversation is fetched here.

The framework PR changes guard/documentation semantics beyond its earlier
acknowledged head. Obtain a fresh trading-owner acknowledgement and the
measurement owner's deterministic source-scope check on its published head.
An incoming shared-state PR and this PR must each rebase if the other lands
first. Neither peer acknowledgement nor passing repository CI supplies
image, live provider, Gate A/P3, task-quality or token-saving acceptance.

## New advisory repair and bounded consensus

The source cleanup published as PR #535 head
`00aa6c25fe6f27e9f5974e9f6a5592aa31683479` passes the original hosted
[Linux validation](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/36737145600/job/109963925887)
and [macOS validation](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/36737133650/job/109961678810).
The older Linux run was canceled by the description update; its cancellation
does not replace the later successful job. The
[native OSV job](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/36737133691/job/109961678725)
returns exit 1 with three urllib3 advisories and a frozen macOS Next advisory.
Historical scan success is not current dependency acceptance.

bc owns [PR #546](https://github.com/seathatflowsinourveins/native-agent-stack/pull/546)
for the main lock and frozen-artifact policy. The official
[urllib3 2.8.0 release](https://github.com/urllib3/urllib3/releases/tag/2.8.0)
and [PyPI files](https://pypi.org/pypi/urllib3/2.8.0/json) supply the fix;
their September 15 uploads are beyond the pinned source's seven-day cutoff.
The [separate Linux candidate receipt](../../blueprints/runtime-workers/openhands/evidence/urllib3-relock-20260930.json)
retains both pristine compile controls, a fresh hashed installation and
12 unchanged compatibility fixtures without skips. It changes only urllib3
and its two hashes, retaining 176 requirements and SDK/tools 1.50.0.
Its intermediate lock SHA256 is
`bd1cbbe864b20cdd33b4c580846ef75451db3aca82a4e5305207890bb6b0d072`.
bc actually endorsed that bounded delta and requires a new exact-head
artifact-only review; the old PR #537 review remains bound to `383ccc…`.

Consequential exception enforcement triggered an independent Astra/Max
review of PR #546's exact initial head
`09d5371d71d3127db3144a0ce3c444a1af696b7f`. The unchanged 153-test suite,
declared mutation controls, manifest checks and full native 49-lock scan
return exit 0. The broad fail-closed Next-reader claim is nevertheless
refuted: quoted affected pnpm keys can disappear beside a recognized fixed
key; pnpm 5 keys and non-pnpm npm locks also escape the new assertion.
These are local adversarial probes of unchanged source, distinct from
upstream tests. The maintained
[OSV-SCALIBR parser linked by the scanner](https://github.com/google/osv-scalibr/blob/3090dbb7aaa24ce7a807899e7f16baa8b802a828/extractor/filesystem/language/javascript/pnpmlock/pnpmlock.go#L277)
supports the relevant mapping representations. bc acknowledged the failures
and is repairing its own guard. A reported local repair is not a new public
head or acceptance; recheck the actual corrected revision before integrating.

The global database subsequently adds
[PyJWT GHSA-42vr-xj54-vc7v](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-42vr-xj54-vc7v),
fixed by 2.15.0. The maintainer's confirmed impact is pre-verification
payload parsing that can raise an uncaught request-level exception; it does
not establish a process crash or authentication bypass. The candidate's
15:51 backend scan returned exit 0; its retained 16:09:27–28Z rescan returns
exit 1 with this advisory alone. Keep both results and their actual times.
The intermediate `bd1…` lock is explicitly unaccepted.

[PyPI's 2.15.0 metadata](https://pypi.org/pypi/PyJWT/2.15.0/json)
records the wheel at `2026-09-23T16:55:59.241512Z` and sdist at
`2026-09-23T16:56:00.689307Z`. Both clear the existing seven-day cutoff
after `2026-09-30T16:56:00.689307Z`; the owner uses 16:57 UTC conservatively.
[2.15.1's metadata](https://pypi.org/pypi/PyJWT/2.15.1/json) keeps it outside
that cutoff until October 5. Follow issue #518's
overturn condition and native relative cutoff; an absolute override that
changes lock options or the selected closure is a failed condition to retain,
not a supported shortcut. Predicted digests await native regeneration.

The owner sequence is now: corrected PR #546 published and independently
rechecked; actual merge; proper candidate reconciliation preserving its
SDK/tools 1.50 and target-specific lock, main's Next/macOS policy and all
captured-input fixture classifications; fresh evidence registration last;
native checks and actual candidate-head review. The client-pin owner has
published PR #542 head `a3a276ac7280655d66b4279f2a4f42de8b17d2fb` and
also waits for that main repair before its final rebase/merge. The SDK draft
still follows the actual pin merge, preserving its full-suite limitation.

2d actually accepts the durable PR #535 thread and
`codex/runtime-qualification-20260930` contact, followed by the SDK PR.
Its scripted source reads find no Gate A scope objection/leak at `00aa…`;
this is no code/model/merge acceptance. The trading owner is absent from
the fresh native roster and the lead knows no successor. A fresh final-head
acknowledgement remains required; no liveness or acknowledgement is inferred.
The F1 owner acknowledged the builder-tag and report-exit corrections for
its owned anti-pattern log. Historical host/memory-write attribution remains
unknown; the coordinator did not issue those commands or edit those main
paths. No timer, memory service, host settings or deployment is changed here.

The independent Astra/Max follow-up found no additional material correction
in intermediate source commit `6ca5863516d0b07748f41be2a2635fbe0211d1c3`.
It recomputed 73 artifact, six source and 62 command-output bindings with
no mismatch, and confirmed that only urllib3's block changed while the
other 175 blocks stayed byte-identical. It inspected retained install,
import, source and 12-fixture outputs rather than rerunning those commands.
Its fresh value-free publication scan of all 77 changed paths returned
exit 0. Its full validator returned exit 1 for the two expected lock/pins
index mismatches; final shared registration is still the coordinator's
responsibility. This review preserves the intermediate candidate's
unaccepted status and both time-bound scan results.

The coordinator's native clock returned `2026-09-30 16:57:15 UTC` before
dispatching the bounded PyJWT 2.15.0 repair. The worker must preserve the
native relative seven-day cutoff and the other 175 selected declarations,
then compare its actual lock digest to the predicted value. Dispatch is
not execution or acceptance; actual returned results follow separately.

The next published dependency head is
`bd48d924026635dccc18d30be8f56a2dc476fa89`. Independent Astra/Max review
confirms the old bypasses, actual affected range and frozen digest are
repaired, and the new main lock changes only urllib3 and PyJWT. The 157
unchanged repository tests, supplied mutants, validator and full 49-lock
native scan return exit 0. Acceptance of the broader guard is still
refuted: a tagged top-level `!!str packages:` mapping and a YAML merge
supplied through `<<: *base` both return an empty guard finding list.
The unmodified pinned scanner actually finds the affected Next package
and filters its advisory in each case. These are reproduced counterexamples
to the guard's unknown-syntax claim, distinct from today's clean inventory.
The owner receives the actual inputs and is asked for a bounded source-backed
repair before integration. Passing current CI supplies no approval for it.

This review also corrects the earlier SCALIBR source citation: the scanner's
reported `0.5.2` label does not identify the linked source. Its native binary
dependency metadata and [OSV-Scanner v2.6.0 go.mod](https://github.com/google/osv-scanner/blob/v2.6.0/go.mod#L14)
pin `v0.5.3-0.20260911142458-3090dbb7aaa2`. The
[actual pinned YAML decoder](https://github.com/google/osv-scalibr/blob/3090dbb7aaa24ce7a807899e7f16baa8b802a828/extractor/filesystem/language/javascript/pnpmlock/pnpmlock.go#L277)
corroborates the native counterexamples. Use that revision for subsequent
verification instead of assuming the reported version's tag is identical.

The same independent reviewer verifies a maintained native alternative.
Installed `scan source --help` and the v2.6.0 release API both return exit 0;
[configuration.md](https://github.com/google/osv-scanner/blob/v2.6.0/docs/configuration.md#L23)
and the [config manager](https://github.com/google/osv-scanner/blob/v2.6.0/internal/config/manager.go#L24)
define explicit config precedence for all inputs in one invocation. With
only the Next ignore removed from an anonymous-memory copy of the config,
the actual tagged and merged probe inputs each produce native exit 1 and
the affected Next advisory. Under the unchanged config each produces exit 0
and the filtered advisory. Every other ignore field and expiry is preserved.
This demonstrates a supported integration option, not a repaired workflow.

The proposed boundary uses two native scans: an exhaustive disjoint ordinary
partition with no Next ignore, and only the frozen SHA-bound macOS artifact
under its dated exception config. The current dependency PR has 48 ordinary
plus one frozen input; derive the count from the actual inventory rather than
hardcoding it. Preserve parser arguments and both native exits, failing the
combined check on either nonzero result. Exact frozen-path/digest and dated
exception assertions remain necessary. This option is sent to the owner;
implementation, actual-head review and hosted acceptance remain outstanding.

At the owner's explicit interim-versus-split decision request, a consequential
Astra/Max architecture review independently reads actual head
`fba387496ca264e878e03283f32c499aee0fd366` and recommends holding PR #546
until the native boundary lands before or with it. Its observed workflow
still gives all 49 inputs one explicit config. This is an architecture
judgment, not a claim of another verified bypass in that head. The coordinator
sends the hold decision and its concrete partition/hash/exit/report controls
to the source owner, who retains implementation ownership.

The separate subagent follow-up is platform-flagged and supplies no final
verdict. The coordinator instead directly runs the owner's unchanged native
checks at `fba3874`: 157 integration tests, original mutation controls,
validator and evidence-index check all return exit 0. Their actual returned
outputs and hashes are retained in the
[independent local-check receipt](../../evidence/artifacts/osv-scope-followup-20260930/receipt.json).
These are repository integration/integrity checks, not upstream tests or
exhaustive parser acceptance. Their success does not remove the outstanding
native boundary, hosted acceptance or broader runtime gates.

bc subsequently gives an actual ownership acknowledgement: the native split
will land inside PR #546, and the interim reader head will not merge first.
Its selected frozen config contains only the same Next exception; ordinary
inputs preserve the unrelated ignores. Both native exits, both report/SARIF
outputs, actual partition/digest controls and native negative controls must
be exercised on the implemented final revision. Keep obsolete-reader failed
conditions as historical evidence. The earlier reconciliation instruction
to preserve those custom readers is superseded. No replacement public head
or completed implementation is inferred from this agreement.

The later completed artifact-review handback confirms the new candidate
commit `e3d18df79c7018ebbe61e1d113fd042badbe3a2a`: 176 package blocks,
only PyJWT changed from the intermediate candidate, all 62 artifact and
53 command-output bindings match, and the fresh publication scan of its
66 changed paths returns exit 0. Install/tests/scans remain retained native
execution inspected independently, rather than rerun by that reviewer.
Native scanner recognition is 174 entries, distinct from the 176 declarations.

That handback also supplies a completed native counterexample from the
historical `fba3874` review. Literal apostrophes in a decoded package key
are trimmed by the [linked extractor](https://github.com/google/osv-scalibr/blob/3090dbb7aaa24ce7a807899e7f16baa8b802a828/extractor/filesystem/language/javascript/pnpmlock/pnpmlock.go#L109),
while the old reader misses the affected package. The actual native scanner
finds one affected package and filters its advisory; the guard returns no
finding. This further refutes that old scope claim and belongs in failed
condition history. It requires no new custom-reader repair under the agreed
native design. Original inputs/argv/outputs remain independently retained.

The owner publishes the native-split candidate as actual PR #546 head
`4a09c9c5f1e5fdb5555d4c916666f12e089cf09f`, pushed at 17:59Z against
unchanged `11227bfd…`. Independent native replay of the actual workflow,
233-test suite and supplied split controls is requested. The owner commits
to all eight required checks and its independent workflow review before
merge, followed by the actual merge SHA. Publication is not completed
acceptance, and no merge is inferred from its reported local execution.

Independent replay now confirms that exact native-split head. The unchanged
repository suite returns exit 0 with 233 tests and two explicit skips; the
original split controls, validator and evidence-index check return exit 0.
The ordinary and frozen partitions contain 48 and one inputs. Non-PR mode
scans those same inputs again for SARIF, rather than adding 49 unique inputs.
Both generated SARIF files contain one run and zero results. Hosted upload
was not exercised locally. Original native streams and the bounded verdict
are retained in the [native-split receipt](../../evidence/artifacts/osv-scope-followup-20260930/native-split-review.json).

Two further controls execute the unchanged workflow and digest assertion in
disposable fixtures. Removing only the ordinary config produces native scan
exits 127 and 0, and the combined workflow exits 127. Appending one LF byte to
the frozen lock makes its original digest test exit 1; restoring the exact
reviewed bytes makes that test exit 0. Inputs are restored and the review
worktree is clean. The bounded independent review finds no outstanding
material source defect. This is repository integration evidence, not an
upstream test, merged change, hosted-upload check or runtime qualification.

The coordinator imports candidate commits `e3d18df…` and `8ea8542e…` into its
isolated source branch. The current target-specific requirements SHA256 is
`83293867247323c4d8fc463096e8a9c01dbee2ada5898112bbbb7d1a62a8b47a`.
PyJWT 2.15.0 joins urllib3 2.8.0 while SDK/tools 1.50 and the reviewed OAuthlib
closure remain intact. The worker's retained native install, dependency check,
unchanged PyJWT regression controls and scans are classified separately from
the independent artifact-binding review. A new review of the actual published
candidate head is still required; PR #537's older lock review does not carry.

Native GitHub observation then confirms PR #546 merged as
`8fc86119eacfd5be9b8a139e1ed167d85748091b`, with final head `4a09c9c5…`
and hosted macOS validation successful. The coordinator rebases its isolated
runtime branch onto that actual main revision. Main's ordinary/frozen configs,
native split workflow and frozen digest policy remain intact. The target-specific
832938 closure and its allowed row change together; its new artifact-only
review remains pending. Only required captured constraints fixtures are
classified by the current native inventory schema; compiler inputs whose names
do not match that schema are not spuriously added. The planned image experiment
refreshes its base and pins digest without adding an observation or running it.

The reconciled source checks return exit 0: 360 repository integration tests
with six explicit skips, 35 convergence tests, and the unchanged native scan
step for all 56 current inputs. Its step SHA matches the independent review;
the table-mode check is a separate execution on the expanded runtime inventory.
Original streams, hashes and two corrected setup/registration failures are
bound in the [source reconciliation receipt](../../evidence/artifacts/osv-scope-followup-20260930/source-reconciliation.json).
This adds no worker, model, image or provider observation.

bc's actual review of public head `7c0df369…` finds no blocking issue for the
832938 lock's bounded OAuthlib reachability exception. Its reported fresh
install/scanner/test execution is a lead until the independent original-output
receipt is published. It supplies no merge, image, observer or task-quality
acceptance. Two requested P2 clarifications are accepted and implemented:

- Preserve the 17:23 PyJWT relock receipt's original pre-PR #546 workflow
  binding. The [dated addendum](../../evidence/artifacts/osv-scope-followup-20260930/workflow-binding-addendum.json)
  names that historical source and separately binds the current native split;
  no old observation is overwritten or promoted to current workflow acceptance.
- The canonical inventory description now explicitly permits captured native
  resolver/probe inputs retained with original hash/command evidence and not
  consumed by shipped installation recipes, alongside deliberately vulnerable
  test fixtures. This documents the existing captured-fixture policy, including
  the four OpenHands constraints files and earlier probe fixtures. It does not
  exclude an active runtime lock or the frozen application lock, add an advisory
  exception, extend an expiry or claim runtime qualification.

The final artifact audit also corrects a literal-byte claim: five explanatory
NLTK comments distinguish the ordinary config from merged main. Parsed policy,
IDs and expiries match; the frozen config and workflow are byte-identical.
The current lock, all nine reviewed OAuth source identities and runtime code
remain unchanged by these clarifications. Hosted checks and the independent
review's public receipt are separate outstanding gates.

The source-link audit corrects the addendum's historical workflow URL: local
baseline `6ca58635…` is not available through the inspected GitHub commit API
(exit 1), while public head `00aa6c25…` resolves (exit 0). Its workflow is the
same 9,268 bytes with SHA256 `88a47e2c…`. The public citation now uses that
head; the original observation's baseline and receipt stay unchanged. The
owned branch history also folds shared evidence and dashboard changes into
its final commit, following the [hot-file protocol](../lanes.md#hot-file-protocol).
These corrections add no execution or runtime acceptance.

At 20:21 UTC, native GitHub metadata confirms the independent review is
published in open [PR #558](https://github.com/seathatflowsinourveins/native-agent-stack/pull/558),
head `54d09ee8810ed98059347097277fcd9f8432de36`. Its
[receipt](https://github.com/seathatflowsinourveins/native-agent-stack/blob/54d09ee8810ed98059347097277fcd9f8432de36/evidence/artifacts/openhands-oauthlib-review-535-head7c0df3-20260930/receipt.json)
is 12,992 bytes with SHA256
`b0742663250afe8eff4692ad7be26b1b894d9977c80154ee3fa71e878efbe880`.
Independent original-source inspection verifies all 32 published file hashes,
the 832938 lock/pins and retained nine OAuth identities, 62 artifact / 53
command bindings, hashed install/dependency/import exits 0, configured scan
exit 0 and empty-config exit 1 for the two retained OAuth advisories. Recorded
checks are 245 total tests, five skips, exit 0; they remain separate from this
lane's 360/6 record. This audit replays no install, scan, model or tests.

The static method's symlink/read-error exclusions and restricted name search
retain dynamic and semantic reachability uncertainty; its exit is not separately
retained. Public sanitized output fidelity to private originals is unverified,
and SARIF files are summarized rather than included. The workflow evidence is
bound to `1df67c92…` / step `bc092b63…`, not a future #555 revision. The owner's
[public P2 closure](https://github.com/seathatflowsinourveins/native-agent-stack/pull/535#issuecomment-5918675360)
applies at `f764a315…`; citation/comment/history changes still receive the next
published-head check. This independently citable static evidence approves no
merge or broader runtime qualification. The SDK follow-up is separately
published as [draft PR #560](https://github.com/seathatflowsinourveins/native-agent-stack/pull/560)
at `f4f0d61e…`, preserving the 404 source bytes on the actual #542 merge base.

## Later dependency-index change and supported repair

BC's [final f722 check](https://github.com/seathatflowsinourveins/native-agent-stack/pull/535#issuecomment-5919401614)
closes the two P2 clarifications at that exact head with 40 public-object
checks and no failures. Its scope remains the old 832938 lock and bounded
static review. At 21:11 UTC, GitHub's advisory database publishes
[GHSA-3cv6-jpf6-8222 / CVE-2026-84377](https://github.com/advisories/GHSA-3cv6-jpf6-8222):
LiteLLM `>=1.93.0,<1.93.2` is affected and `1.93.2` is patched. The later
SDK749 hosted scan returns exit 1 for unchanged main's 1.93.0. Earlier green
scans retain their original dates and inputs; they are not current-database
acceptance. No advisory ignore or expiry changes.

Independent Astra/Max research resolves the conflicting cutoff and patch
provenance before the repair. The trigger is the legacy July 20 cutoff,
the later patched release and divergent original advisory staging ancestry.
[OpenHands' introducing change](https://github.com/OpenHands/software-agent-sdk/commit/395b94b0c3c4994f6c530f1e3bf3196f71fab950)
explicitly permits bumping or removing the LiteLLM-specific cutoff when
upgrading past 1.93.0; its [independent global seven-day rule](https://github.com/OpenHands/software-agent-sdk/commit/fa571e35b784de471e220abf5b7c874c2c9b9f19)
remains. Official PyPI dates the selected 1.93.0 files to July 19 and
[1.93.2's CPython 3.13 Linux wheel and sdist](https://pypi.org/pypi/litellm/1.93.2/json)
to August 9. The [maintained backport](https://github.com/BerriAI/litellm/pull/36318)
is in tag `cd1bd0f4b8af865f8d05fbd938392fdd4703babc`; native comparison
confirms actual backport `29be951c…` is its ancestor, ahead seven/behind zero.
No ancestry claim is made for the original staging commit.

The source-accepted method uses the published packages' supported requirements,
an exact 1.93.2 constraint, unchanged other pins and LMNR cutoff, and the
global seven-day policy. [Pinned uv 0.12.17 resolution rules](https://github.com/astral-sh/uv/blob/0.12.17/docs/concepts/resolution.md)
also support a per-package seven-day override. Both OpenHands root workspaces
pin 1.93.0, while both [1.49.6](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/pyproject.toml#L18)
and [1.50](https://github.com/OpenHands/software-agent-sdk/blob/dcf401af7a9a302ef92cb7d092e1df9bb659daa5/openhands-sdk/pyproject.toml#L18)
SDK packages permit `>=1.93.0`. Untouched workspace relocking fails on that
exact-pin conflict; it does not establish published-package incompatibility.
No upstream workspace patch is made.

MAIN335 stays with its live Claude owner. The [durable handoff](https://github.com/seathatflowsinourveins/native-agent-stack/pull/535#issuecomment-5920193968)
requests its repair or explicit bounded delegation; existing main recipe,
guard and docs remain untouched. Private native candidate preparation retains
the original scanner failure and a corrected same-lock empty-TOML control.
The initial no-package-sources exit 128 is a preserved setup failure, excluded
from acceptance. MAIN335 means 335 unique packages and 336 physical blocks;
native Linux resolution qualifies only its selected 176 packages, while
unchanged other-platform branches gain no native qualification.

SDK draft #560 is separately repaired at `74902ff1…`: its historical inventory
remains the oracle for all 34 non-SDK packages, with current SDK/client guards
bound independently to the selected pin and unchanged qualification receipt.
The [hosted Linux result](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/36779328526/job/110105352672)
is 8,702 tests, 807 explicit skips, exit 0; macOS validation also succeeds.
Its security gate remains blocked by unchanged main's LiteLLM lock. The
original 14 SDK files, historical upstream failure and non-additive counter
stay unchanged. No new SDK/model run or Collector deployment follows.

The supported Claude relay's new first turn hits its native session quota
before sending. New-head requests are undelivered; earlier source and trading
acknowledgements retain their reviewed heads. A replacement lock needs fresh
candidate evidence and owner acknowledgement. Image/Python, trusted observer,
frozen task quality, provider/Gate A/P3, compression comparisons and complete
task accounting remain separate open gates.

The coordinator imports the stopped, clean worker source patch into its own
isolated draft. The new requirements SHA256 is
`38c20c899b8d7b08e03a04624daa17ba1fc353533fbff450bb0ac2bddd0832eb`;
only LiteLLM changes, leaving all 175 other package blocks byte-identical.
The [new native packet](../../blueprints/runtime-workers/openhands/evidence/litellm-relock-20260930.json)
retains the original July-cutoff reproduction, explicit no-config recompile,
hashed installs, dependency checks, 12 real-SDK fixtures, 68 unchanged tagged
upstream URL tests and fresh whole-candidate caller/source review. The nine
old identities alone are not its new closure proof. Full-wheel 2,104 Python
file comparison and bounded caller methods retain semantic/dynamic uncertainty.
The 68-test result is one upstream module, not the proxy/full-workspace suite.

After registration, 280 affected repository checks pass with five explicit
skips. A fresh [workflow recheck](../../evidence/artifacts/osv-scope-followup-20260930/litellm-workflow-recheck.json)
executes the unchanged step through the pinned native scanner: all 56 current
inputs, exit 0, `WRITE_SARIF=false`. Original historical outputs are preserved;
this adds no hosted upload, model, image, provider or task-quality run. Initial
reconciled integrity checks pass for 8,951 hashed files. The planned image
experiment refreshes the package-pins digest and captured base, keeps zero
observations and explicitly records that the upstream frozen workspace/image
still targets LiteLLM 1.93.0. This package repair is not an image remedy.

Independent Astra/Max review accepts the stopped local source patch's bounded
exception retention: all 39 public bindings, 36 ledger commands, 41 private
records and 82 original streams match, including returned-output fidelity
after declared substitutions. Its fresh guard replay passes 38 tests with no
skips. The trigger is the consequential security fix and new exception digest;
the acceptance result is bounded source approval with no binding defect,
retaining dynamic/semantic and compiled-extension uncertainty. The immutable
worker packet is left unchanged; the coordinator recheck records this later
verdict separately. No Claude acknowledgement or broader runtime acceptance
is inferred from that independent source review.

The separately reviewed private MAIN335 candidate `d160c826…` preserves all
334 other unique packages / 335 physical blocks. Its fresh 1.49.6 environment
also supplies candidate-specific whole-caller and source-identity evidence,
independently checked with all four additional native exits 0. Existing main
remains clean and unmodified; the owner still needs to adopt the lock, pins
digest, exact-lock guard and registered evidence together.
