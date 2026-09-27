# Historical RTK coverage method and publication boundary

Study date: **2026-09-26**. Publication and source recheck: **2026-09-27**.
The source is the full-save RTK study's aggregate files and method report,
requested by the full-save plan section 3.1 PR-EV and section 4.1. Only public
upstream sources and the supplied scratch results were needed for publication.
No commands, paths or content from the private sample are included.

## Revisions and primary source checks

| Revision in the original study | Tag target verified on 2026-09-27 | Role |
| --- | --- | --- |
| v0.50.0 | `1d87b8e719ce0a50c223cd93ca64dd16921f9aec` | Stable baseline. |
| dev-0.51.0-rc.467 | `a89a31494670fcec8ffa20d939dd94c64bd998fb` | Prerelease comparison only. |

Tag targets were returned by GitHub's
[stable ref endpoint](https://api.github.com/repos/rtk-ai/rtk/git/ref/tags/v0.50.0)
and [prerelease ref endpoint](https://api.github.com/repos/rtk-ai/rtk/git/ref/tags/dev-0.51.0-rc.467).
The installed client returned `rtk 0.50.0`; its `hook check --help` calls the
operation a dry run, and `discover --help` identifies Claude Code history.
These are current version/help observations, not new coverage results.

At v0.50.0, [src/main.rs](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/main.rs)
dispatches hook checks, and
[src/hooks/decision.rs](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/hooks/decision.rs)
defines `decide_for_agent`, identity suppression, permission decisions and
configuration-dependent rewrite behavior. The supported native dry run is
`rtk hook check --agent claude -- <synthetic command>`; the native classifier is
`rtk discover`. These generic method invocations are not private sample commands.

The source review also checked
[src/discover/mod.rs](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/mod.rs)
and [src/discover/registry.rs](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/registry.rs).
The discover source explicitly distinguishes measured hook-log coverage from
estimated fallback coverage and reuses the original call's hook decision for
its split parts. Registry classification is not evidence that output was
lossless. The historical fixture comparisons exercise the filters directly.

## Population and replay

The study scanned 1,945 transcript files. Of these, 1,606 were modified in the
window, including 1,594 subagent transcripts. It counted 59,041 Bash calls,
53,895 from subagents. The window starts with the first hook-log row at
2026-09-24T03:50:41Z and ends at 2026-09-26T18:38Z.

Four evidence classes are kept separate:

1. **Historical local measurement:** a read-only copy of RTK's `hook_decisions`
   table was joined to transcript calls. The retained totals are 22,080 `ask`,
   36,494 `defer`, 292 `deny` and 175 without a row. The report attributes 106
   missing rows to calls after the snapshot, 57 to foreground sleep calls and
   12 to other calls; this publication does not independently inspect those rows.
2. **Historical local replay/integration:** RTK's native hook dry run examined
   the same population using the host configuration and working directory,
   then the no-config comparison. Whole-call rewrite counts are in table A:
   21,957 for v0.50.0, 21,752 for rc.467, and 22,262 for v0.50.0 without config.
   None of these counts are added to the recorded hook counts.
3. **Historical local classifier measurement:** native discover classified
   one-call synthetic transcript wrappers around the historical calls. The
   wrappers changed input shape, not the private source content. Only aggregate
   supported-part counts are published in frame-summary.txt.
4. **Historical synthetic fixture/local integration:** the exactness study used
   a disposable repository with isolated RTK data/cache directories. Its returned
   output is exactness.out. It is independent of the private sample.

No live provider execution is claimed. The original report also mentions native
`rtk verify` runs; their returned stdout is not part of this publication, so this
receipt does not assert unchanged upstream-test acceptance. Cargo tests were
not rerun by the publisher. Whole-call output bytes are **not token savings**,
provider usage, billed cost or isolated filter effects.

## Sample classification

The study drew 611 missed-command observations, stratified by command family
in proportion to misses, with random seed 20260926 and minimum stratum size 6.
There were 539 subagent and 72 main-thread observations. Table E retains every
stratum count. Each sampled observation was checked as a full call, as its
clause including the pipeline, and as the command alone, both with the host
config and with no config. The first blocking rule determines its class.

Table C's `C rewritten` columns refer to the whole call; the clause/unit columns
are counterfactual dry runs. They do not authorize splitting a dependent shell
command or filtering data passed to another program. For example, the pipeline
class contains 181 observations whose whole calls did not rewrite, while all
181 isolated command units did. This is a shape observation, not an estimate of
safe optimization opportunities.

The published confidence intervals assume simple random sampling. Minimum-size
strata were oversampled; the historical report says post-stratification changes
each class by at most 0.7 percentage points. This qualification is retained;
neither the private classifications nor the weighting calculation is reproduced
by the public artifacts.

## Synthetic exactness fixture

The original fixture script builds a synthetic repository with a 400-line blob,
branches and a linked worktree, a merge-containing history, differing/missing
files, and a nested file-list search. It compares native commands with explicit
RTK invocation, then queries the host-config hook dry run. T7 separately compares
60 synthetic rows, seven longer than 120 characters, with v0.50.0 and v0.49.0.

| Case | Returned observation retained in exactness.out |
| --- | --- |
| T1 / T1b | Blob output is truncated by both tested filters, including the global-option form. |
| T2 / T2b | Missing-file diff returns 2 natively, 1 on v0.50.0 and 2 on rc.467; ordinary differences return 1. |
| T3 | Linked-worktree and remote branch presentation differ from native output. |
| T4 / T4b | Merge visibility and default log length differ; default RTK output contains ten lines. |
| T5 | Missing-directory find changes the native nonzero result to zero on both tested revisions. |
| T6 / T6b | rc.467 folds the returned file list and changes pipeline output. |
| T7 | Both tested jq filters report 42 lines versus 60 natively, with a 120-character maximum versus 162. |

These are historical returned observations, not a fresh run or a universal
behavior guarantee. Synthetic fixture paths such as `src/deep/pkg/f1.txt`,
`/r/.git` and `/w` are retained because they are fixture operands, not private
sample paths. Captured digests and fixture commit subjects are data, not account
or credential identifiers. The local recall handle alone is replaced with
`<omitted>`.

## 2026-09-27 erratum: discover coverage is not M-R1

The original frame has 15,623 missed and 25,954 covered supported parts, or
62.4% covered. Preserve that recorded result. It is **not M-R1**, the later
full-save eligible-part coverage metric. A whole-call rewrite can coexist with
an unrewritten eligible sibling part; upstream discover's measured classification
can give both parts the same recorded call decision. The plan's section 4.1
revision records this distinction, and the upstream discover implementation
above corroborates the whole-call-to-parts relationship.

The later five-exclusion replay reported 21,848 rewritten calls. It is a separate
plan observation, not the 21,957 host-config replay retained in tables.txt, and
has no returned aggregate artifact in this publication. Likewise, broader
discover windows, cumulative gain counters and Codex prefix ratios from the
plan are not merged into this study's denominator. Historical config changes
and the v0.49-to-v0.50 transition can explain replay/log disagreement; replay
does not silently replace recorded hook outcomes.

## Retention and verification limits

The scratch report exists at publication time; the plan's earlier statement
that its write was refused describes an earlier state. This publication uses
the available method report but does not retain its private examples. Original
scratch-file SHA256 values identify which supplied inputs were read:

| Input basename | Original SHA256 | Public treatment |
| --- | --- | --- |
| tables.txt | `39fc4685afb0a955610ab74f389dd6a24ddda7116dc911769e1568ad0e4a74d2` | Byte-for-byte aggregate table copy. |
| frame-summary.txt | `3acec61e484ab03080a0750a4a5b499e9e91b2171fb935e185b4aeb84f6b8294` | Keep decision and supported-family aggregates; remove the entire final unsupported-key list. |
| exactness.out | `b582c6c912708d0b102b4a62f604131c3eee69cd3ef15289e93d5b406698e029` | Preserve output except the local recall handle. |
| REPORT.md | `6673be45da20150050afbf0c73d60681286458fcd0effa4d260fdcf38adfe8e8` | Method summarized here; private examples and paths omitted. |
| exactness.sh | `7fff6ef1a6f5500a5ce13ac0bdb2adbe6313cc401eb4f4158cf2d12456b4a4bf` | Fixture design summarized; host-specific script not published. |

The repository permits arithmetic and source/fixture-result inspection later.
It cannot regenerate the private population, joins, individual classifications
or original binaries from these aggregates alone. The fixture script and raw
upstream-test output are also not public artifacts here. These are deliberate
reproduction limits, not passing acceptance for another host.
