# NativeStack2604 readiness currency upkeep — 2026-10-05

This unit serves portable engineering and US-equities R&D through the accepted
native foundation. It follows the currency jobs in readiness workflow
`wf_cfa1d860-ebd`, in order, from main
`c148e049efee75f8ea8a9a009e7b96b1e97f5c28`. Currency observations do not promote
the roadmap's readiness statuses or replace another owner's qualification.

## Default-protectBinfmt upstream gate

Hold the base-distribution gate. On the dated official-source read, Microsoft's
latest stable release remains [WSL 3.0.1](https://github.com/microsoft/WSL/releases/tag/3.0.1),
published 2026-09-29T17:18:57Z at
`91f161fa240dc355c1a88daabc8aac4273e35ba5`. The installed client independently
reports 3.0.1.0 and kernel 6.18.40.1-1. Canonical's installed package reports
`wsl-setup 0.6.3ubuntu~26.04.1`. These are version observations, not fresh tests.

Canonical's latest version tag is
[0.6.3](https://github.com/ubuntu/wsl-setup/tree/73418e32bb48d514c2c2853fa7e5cacdcaf3dfe8).
Its GitHub release endpoint returns 404; do not describe the tag as a published
GitHub Release. The tag and main
`86a561d5149a9d76ec3c9b3ce2745e7ebca5f2ad` have byte-identical
`test/systemd-assertions.sh`: 1,354 bytes, SHA256
`83f2d89c00e70e994218ed3bed4ae19aee3539934dbe109aff76f9c57cfd2e83`.
[Lines 6–8](https://github.com/ubuntu/wsl-setup/blob/73418e32bb48d514c2c2853fa7e5cacdcaf3dfe8/test/systemd-assertions.sh#L6-L8)
require `systemctl is-system-running` to return `running`, otherwise exit 1.

WSL's tagged source retains
[`BootProtectBinfmt = true`](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/WslDistributionConfig.h#L62)
and invokes
[`LockBinfmtStatusReadOnly()`](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/init.cpp#L2430-L2435)
at its default. No supported qualifying release was found, so this watch does
not trigger another acceptance run or retire F1. The recorded upstream systemd
exit 1 stays a failure, separate from the local integration exception.

Rejected alternatives remain changing the user's `protectBinfmt` setting and
relabeling the deployed distribution as excluded by design. The existing
[G8 decision](2026-10-04-2604-e2e-fix-wave-g8-base-gateway.md#decisions-alternatives-and-overturn-conditions)
requires target proof before retiring the exception. Reopen this gate when a
supported Microsoft/Canonical release changes the relevant behavior, then run
`accept.sh --only base-distribution --stage post_install </dev/null` and retain
the unchanged Canonical scripts' actual exits. A source change alone cannot
establish exit 0 on the target host. No restart, setting change or native
assertion run occurred in this review.

The next watch must include official stable WSL releases and Canonical source
package revisions, since a package- or kernel-level fix need not coincide with
a new repository tag. Unreleased or community workarounds remain leads.

## Selected engineering skills

Retain the four existing per-skill pins. Official
[v1.3.1](https://github.com/mattpocock/skills/releases/tag/v1.3.1) resolves to
`24fe0ef7737efae15c87225755e9f6f5965e4888`, published
2026-10-04T12:48:18Z. At the 2026-10-05T11:53:08Z comparison it was less than
24 hours old; that hold expires at 12:48:18Z. Independently of release age,
each selected **whole directory tree**, including supporting files, is identical
at its existing pin and v1.3.1:

| Skill directory | Retained commit | Identical Git tree |
| --- | --- | --- |
| `skills/engineering/diagnosing-bugs` | `d81f3a183412e71a5b1e84ca21bc1a35eea03a60` | `de4236cf34757c4e9ea7afe78d46c023213ff254` |
| `skills/engineering/tdd` | `d81f3a183412e71a5b1e84ca21bc1a35eea03a60` | `bf1bf5ffcd63aa8abce830f2955a853c121fb463` |
| `skills/engineering/codebase-design` | `d81f3a183412e71a5b1e84ca21bc1a35eea03a60` | `07ba1cd60efc12d0d3a083005c1d9651cf15e39a` |
| `skills/productivity/writing-for-agents` | `c55ee46073ed923f86ce59a5eb3b6d895095d1b7` | `ad2925850efb8973a72d2e666f7a975f9a2d4a9b` |

The [patch changelog](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/CHANGELOG.md#L7)
corrects stale handoff wording in diagnosing-bugs documentation and the
unselected ask-matt router. It changes no selected skill directory. Updating
these pins would adopt identical artifacts, so no install or activation follows.

The reviewed [release workflow](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/.github/workflows/release.yml#L26)
performs release automation; no upstream skill-quality test suite was found in
that revision's workflows. Git tree and content-hash comparisons are source
review, not upstream acceptance. Skills CLI listing and fresh native activation
remain separate operations owned by the readiness plan's skills-lifecycle/co-op
jobs. Reopen when an eligible release changes a selected directory. The next
sweep also checks newly introduced, restored or retired skills and native client
invocation metadata, along with the upstream plugin-update and remaining documentation
reports [#1164](https://github.com/mattpocock/skills/issues/1164) and
[#1165](https://github.com/mattpocock/skills/issues/1165); these reports do not
establish a regression in the unchanged selected trees.

## Claude SDK example

Retain the example's 0.2.162 pin at
`f2204bb956bab02907aaf3cb88eb9dead28eaa35` for this wave. Candidate
[v0.2.163](https://github.com/anthropics/claude-agent-sdk-python/releases/tag/v0.2.163)
was published 2026-09-30T19:47:45Z at
`1ef6d8c71bb0e44a6b33fe61497864f21e17fdb7`. Its Python client, query,
subprocess transport and types are byte-identical to 0.2.162. The behavioral
dependency changes from bundled
[CLI 2.1.285](https://github.com/anthropics/claude-agent-sdk-python/blob/f2204bb956bab02907aaf3cb88eb9dead28eaa35/src/claude_agent_sdk/_cli_version.py#L3)
to [2.1.286](https://github.com/anthropics/claude-agent-sdk-python/blob/1ef6d8c71bb0e44a6b33fe61497864f21e17fdb7/src/claude_agent_sdk/_cli_version.py#L3).

The unresolved [CLI report #98747](https://github.com/anthropics/claude-code/issues/98747)
describes context loss through idle compaction beginning in 2.1.286, observed in
interactive macOS sessions. Applicability to this Linux, headless, single-query
example is unverified. Under the latest-clean release rule, hold until upstream
resolution or verified adjudication that the report is not a release regression.
Route-only evidence does not waive that rule. This is a conservative
source-review decision, not a reproduced SDK regression or a claim that the
retained version is globally clean. The Linux headless crash report
[#98843](https://github.com/anthropics/claude-code/issues/98843) spans 2.1.284 and
2.1.286 and likewise does not establish causality for this upgrade.

The Python late-hook report
[#1340](https://github.com/anthropics/claude-agent-sdk-python/issues/1340) is not
evidence that 0.2.163 introduced a regression: its relevant implementation is
unchanged, and this example supplies no Python hooks or permission callbacks.
Native hooks loaded through client settings or plugins remain a separate path.
Do not add a local SDK wrapper or patch to work around these reports.

The downloaded official Linux x86_64 wheel matches
[PyPI's published digest](https://pypi.org/pypi/claude-agent-sdk/0.2.163/json):
103,197,060 bytes, SHA256
`260cb955d237b7e1897f1dbf9ee5efbf815d8622d0c7459a05409c56432d8501`.
Its dependency declarations are unchanged. The inspected public SDK/CLI
advisories and PyPI metadata supplied no matching advisory for this version
pair; this is not a transitive dependency audit or a behavioral qualification.
Wheel integrity does not resolve the CLI report.

Preserve `worker.py`, its generated lock and the current README at their pin.
Preserve the dated `verification.md` and `examples/omniroute-codex-sdk/checks.json`
bytes: their commands, source closure and 110 recorded attempts describe earlier
runs. An eventual pin change needs a new scoped receipt, native `uv lock --script`
generation and the existing offline checks; it must not relabel those historical
results. Offline checks alone cannot qualify the changed bundled CLI. Preserve
the separate native behavior and SDK-selection gates in the
[example README](../../examples/claude-runtime-sdk/README.md#validation-scope).
The next sweep checks both SDK and bundled CLI releases and the dispositions
of their regression reports. No SDK suite, live provider query or fresh model
run occurred here.

## OpenHands declared currency amendment

Declare amendment `readiness-openhands-currency-20261005`: compare two new
source-review arms with the frozen v1.50.1 baseline, keeping that baseline and
all historical judgments immutable. No runtime experiment was run and no new
convergence or adoption claim is made.

| Arm | Exact commit | Published UTC | Decision |
| --- | --- | --- | --- |
| [v1.50.1](https://github.com/OpenHands/software-agent-sdk/releases/tag/v1.50.1) | `1e1390acc8788346ba4804c34323284009bf3f5e` | 2026-09-30T19:31:33Z | Retained selected baseline |
| [v1.51.0](https://github.com/OpenHands/software-agent-sdk/releases/tag/v1.51.0) | `a955aa5d3188d4b0a44ad7eb4e5c4bba6e6238d9` | 2026-10-03T07:38:03Z | Hold pending qualification and advisory disposition |
| [v1.52.0](https://github.com/OpenHands/software-agent-sdk/releases/tag/v1.52.0) | `229b2b920d4541eab7a34b051a1f6f2bca5ebabf` | 2026-10-05T04:10:05Z | Also held by the 24-hour rule until 2026-10-06T04:10:05Z |

The 1.51.0 release changes proxied-provider cache-key handling, OpenRouter
support, profile tool/persona control and sub-agent MCP scoping. The 1.52.0
release adds lost-create retry/deduplication and terminal lifecycle changes.
Its [UUID tmux sockets](https://github.com/OpenHands/software-agent-sdk/blob/229b2b920d4541eab7a34b051a1f6f2bca5ebabf/openhands-tools/openhands/tools/terminal/terminal/tmux_pane_pool.py#L122-L124)
and [example socket-path correction](https://github.com/OpenHands/software-agent-sdk/pull/5494)
continue to require Unix sockets. Neither removes srt 0.0.78's documented
[Linux AF_UNIX restriction](https://github.com/anthropic-experimental/sandbox-runtime/blob/6f0ce155ccb136bda33a8a72201fe7f54fe47d9b/README.md#L816).
Do not describe SDK currency as a repair of that separate readiness gate.

All three immutable workspace `uv.lock` files contain LiteLLM 1.93.0 and
PyJWT 2.14.0. These versions match
[GHSA-3cv6-jpf6-8222](https://github.com/BerriAI/litellm/security/advisories/GHSA-3cv6-jpf6-8222)
(LiteLLM proxy routing; the
[reviewed branch range](https://github.com/advisories/GHSA-3cv6-jpf6-8222)
lists patch 1.93.2) and
[GHSA-42vr-xj54-vc7v](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-42vr-xj54-vc7v)
(pre-verification JWT parsing; patch 2.15.0). Neither candidate establishes a
clean frozen-dependency upgrade. Exact native package-export membership and
deployment reachability were not assessed. Retaining the comparison baseline
does not exempt it from these same conditions or assert that it is secure.
No custom dependency patch, audit tool or suppression is introduced.

All six official SDK/tools wheels match their PyPI-published SHA256 and size;
the [scoped source receipt](../../evidence/artifacts/ns2604-readiness-currency-20261005/source-review.json)
retains the exact digests. This proves artifact integrity, not execution.
Before a later re-pin, resolve release age and advisory applicability with the
owner, then use upstream's frozen setup and unchanged applicable SDK/cross
[CI harness](https://github.com/OpenHands/software-agent-sdk/blob/a955aa5d3188d4b0a44ad7eb4e5c4bba6e6238d9/.github/workflows/tests.yml#L96).
For 1.52, also qualify the unchanged terminal isolation and cleanup regressions.
Record omitted workspace/server/browser/provider suites when selecting a subset.
Use an isolated tool root or throwaway host; the shared host stays on its plan
of record. Fresh sandboxed example, dispatch, fresh-client use, recovery and
closed-port negative remain separate runtime gates owned by the repair/co-op
jobs. No upstream suite or native worker ran in this amendment.

The next sweep must cover the exact installed/exported dependency graph,
advisory-function applicability, socket recovery/path length and the upstream
example harness's scratch policy. Its short socket path currently uses `/tmp`;
do not run that harness under this lane's no-`/tmp` rule without resolving the
conflict through supported upstream controls. Provider, remote-workspace,
browser, TypeScript and GHCR modalities require their own applicable evidence.

## Convergence metadata and owner boundaries

Convergence-validator release metadata is requested at `v2026.10.05.1`, while
the checkout-based `repository-recipe` row still says `v2026.09.26.2`.
[Open #713](https://github.com/seathatflowsinourveins/native-agent-stack/pull/713)
and [open #723](https://github.com/seathatflowsinourveins/native-agent-stack/pull/723)
both edit `install-plan.json`. Hand the one-row amendment to those owners;
keep their live-owned plan untouched until custody is settled. The exact proposed
amendment is only `release: v2026.09.26.2 → v2026.10.05.1` for
`cross:convergence-practice/convergence-validators`, retaining the route, empty
install commands, source locators and acceptance command. Current
`adoption/manifest.json` already names release commit
`77d7516d81a94b1cb0e77a7b6c910c28c8104dc9`; the official
[immutable release](https://github.com/seathatflowsinourveins/native-agent-stack/releases/tag/v2026.10.05.1)
was published 2026-10-05T07:08:36Z. Its metadata read is not a new artifact
attestation verification. The old row label remains temporarily because another
live owner controls this shared plan. The checkout-based route validates the
current checkout, so that old label does not prove an old installed binary.
This is metadata coordination, not a new install or host-acceptance claim.

The Codex profile job remains unstarted while #713 is unmerged, exactly as the
dispatch requires. Neither the current plan's 0.160.0 pin nor an earlier native
SDK run makes that dependency complete.

## Evidence boundary

The source receipt retains selected native returned observations and artifact
digests. Release/source review, native version output and repository structural
checks are separate classes; none is new upstream acceptance or fresh client
use. No host receipt, catalog enrollment, component pin or readiness status is
changed. The completeness findings above feed the next source watch, not an
automatic expansion of this task.
