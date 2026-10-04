# Retire PR #392: macOS token-efficiency receipts

Decision date: 2026-10-03.

Decided by: Claude session native-agent-stack-0c, under its custody of unowned
PRs, after the two-hour objection window in the [custody notice][notice]. The
notice was posted at 2026-10-03T08:21:53Z; its window ended at
2026-10-03T10:21:53Z. The PR, coordination channel and #608 had no objection or
ownership claim in the builder's post-window reads.

Scope: [PR #392][pr392] only. No pin, winner, `platform_status`, profile or receipt
on main changes. This preserves foundation evidence custody for the two-host
research architecture; it does not alter the Mac's own profile.

Verification base: main `9b0b8d6d25f9e3fb8f71770500e774170423315e`.
PR head checked: `34b878771b3d1e040c74cb957ff8b4118169ece8`.

## Decision

#392 closes unmerged after this record lands. Its 17 receipts for 10 components,
three child/worker E2E artifact files and generated component-matrix report
changes are not published to main. This record preserves their bounded historical
facts and a fresh Mac re-record path; it does not transfer their execution claims
to the verification base. The file counts were re-derived from the files added
by the pinned PR head, using its merge base with main.

## Why

- **Parked work needs a Mac session.** The native-agent-stack-10 review comments
  parked #392 on 2026-09-29 and said the Mac coordinator must re-record. The
  [04:46 review][review-parked] and [05:15 follow-up][review-followup] remain the
  disposition evidence; the custody window produced no new owner.
- **The roadmap assignment did not resolve it.** The September 28 roadmap put
  #392 in the near-term landing work at line 178, assigned row F-2W-6 to the Mac
  coordinator, depending on a Mac session, at line 206, and kept it in “Rebase,
  then land” at line 235. The later parked review and the blockers below leave
  that work outstanding. See the [roadmap at the verification base][roadmap].
- **The pinned head still has two material recording blockers.** A script loaded
  only the PR's 17 added receipt blobs and printed counts, never receipt bodies
  or output excerpts. The two blocker counts (10 of 17 and 31 of 48) match the
  [custody notice][notice]; the distinct-revision count (6) matches the six
  `receipt-revision/*` tags in the [September 29 review][review-parked]:

  | Property checked against the verification base | Result |
  | --- | --- |
  | Receipts whose `catalog_revision` is not an ancestor of main | 10 of 17 |
  | Distinct catalog revisions behind those receipts | 6; reachable through `receipt-revision/*` tags, outside main's ancestry |
  | Recorded commands whose `output_sha256` differs from the SHA-256 of their published `output_excerpt` | 31 of 48 |

  Revision ancestry was checked with `git merge-base --is-ancestor`; tag
  reachability was checked separately. The digest comparison used the published
  excerpt bytes only. The mismatches are the pre-#492 recording basis, not a new
  recording failure under the current recorder: [#492][pr492], merged as
  `c0ca46d1294ea2b286f629aa9550a7cae3be9e6b`, changed new recordings to hash the
  published, sanitized excerpt. The current implementation explains this at
  [host_receipts.py lines 1012–1019][digest-source].
- **Minor review findings also require fresh recordings.** The September 29
  reviewer attributed minor findings to the headroom generation-3 text, the RTK
  generation-3 `supersedes` field versus its prose, and mcporter's self-description.
  This record attributes those findings to the [review][review-parked] without
  repeating receipt text. Receipts are append-only: every repair requires a
  fresh recording on `mac-coordinator-64gb-20260925`, preserving the earlier
  receipt unchanged. See [the recording policy around line 243][append-only].
- **The value must stay within the target's scope.** This retirement changes none
  of the macOS pins. At the verification base, the [foundation landscape][landscape]
  still marks `macos-arm64: untested` for serena, markitdown, rtk, headroom,
  ccusage and mcporter. The new target's [decided defaults][new-target] and
  [install-plan rows][install-plan] select no context-supply layer and do not
  install ccusage; native client usage and OpenTelemetry own metering. The exact
  current rows are `owners[26]` (ccusage) and `owners[27]` (context-supply), each
  with no installation commands. The decided-defaults file's older context-supply
  prose at [line 292][new-target-prose] still keeps ccusage as the usage meter:
  `git blame` at the verification base attributes it to #591, which precedes the
  decided rows (#602) and the install plan (#606). The [token-skills-orchestration entry][open-work]
  treats legacy-host token observations as a separate scope. This concerns the
  new target. The Mac's own profile is not changed here.

## Alternatives and why not now

| Alternative | Why it is not the present action |
| --- | --- |
| Land after a Mac re-record | It needs an owning Mac session and fresh receipt evidence. It remains available through a new PR, as described below. |
| Port the E2E artifact alone | It describes one run whose returned workflow status was not kept. Its verifier tally is preserved here instead of publishing an incomplete acceptance artifact. |
| Wait for an owner decision | The custody notice found no live owner and invited an ownership claim or objection. None arrived in the checked window. |

The alternatives follow the [custody notice][notice], the [parked review][review-parked]
and the PR body's Findings and Round 3 sections. Closing #392 does not close the
fresh-recording alternative or issue #276.

## Preserved facts

**Observed 2026-09-27 on mac-coordinator-64gb-20260925; historical reference, not
current host status.** The versions and evidence classes below come from #392's
SOTA sources and Evidence-class tables. They describe what was exercised then,
not acceptance on a new checkout or the current host.

| Component | Version exercised | Evidence class recorded in #392 |
| --- | --- | --- |
| rtk | 0.50.0 | `native_proven` |
| serena | 2.0.0.dev0 at upstream commit `c6fbd1c5932df2494ffa0020af5a9fbe80b82143` | `native_proven` |
| jcodemunch-mcp | 1.108.319 | `native_proven` |
| ccusage | 20.0.24 | `native_proven` |
| mcporter | 0.13.13 | `native_proven` |
| repomix | 1.18.1 | `local_integration` |
| headroom | 0.37.0 | `local_integration` |
| toon | 4.1.1 | `local_integration` |
| markitdown | 0.1.8 | `local_integration` |
| context-mode | 1.0.169 | `local_integration`; generation 1 recorded `fail`, generation 2 `pass` |

RTK 0.50.0 and markitdown 0.1.8 were recorded with
`--allow-unbound-version`, against the then winner pins 0.49.0 and 0.1.7. They
therefore did not supply pin-bound Mac evidence for those winners. These are not
claimed as the first macOS receipts: RTK already had a receipt on
`macos-m5pro-20260924`. jcodemunch-mcp was adjacent to the token-efficiency profile,
rather than one of its members. These boundaries come from [#392's Scope,
tables and Findings][pr392].

### Issue #276 coverage and configuration

The PR body's Coverage and configuration section records all 13 token-efficiency
commands present. The overall result was `prerequisites_missing` only because
the platform was reported unsupported for `macos-arm64`. It records
`client_wiring.complete: true` through the either-scope rule, without requiring
both configuration scopes to provide every entry.

It also records `pinned_versions_match: false`: Codex was pinned at 0.155.1
against installed 0.158.0-alpha.2.1, and ai-memory at 2.3.2 against 2.4.0.
`MCP_AUTO_OPEN_ENABLED` was false in both required places. This record repeats no
configuration inventory. These are [the September 27 coverage findings][pr392].
For the later Mac client snapshot, use the [October 2 architecture table,
lines 109–111][mac-clients]: Codex 0.160.0, Claude Code 2.1.287 and ai-memory
2.5.2. That dated snapshot does not make the September 27 check a current run.

### Mac findings and the child/worker exercise

The PR body's Findings section records that mise's RTK 0.49.0 shim resolved first
on a plain PATH, and that Codex's RTK instructions were inlined and not enforced
by a hook. Those are historical observations, not new inspection of the Mac's
configuration. It also records that codebase-memory-mcp had no macOS pin and
that mcporter's Mac pin was 0.13.13 while `manifests/stack.json` had 0.14.1.
At the verification base, [the Mac pin file][mac-pins] still has no
codebase-memory-mcp entry and still pins mcporter at 0.13.13; the [stack
manifest][stack] still records mcporter 0.14.1. No pin is reconciled here.

The bounded readiness-audit child/worker run used copies of issue bodies as its
inputs, not synthetic fixtures: #392's Round 3 section calls them synthetic, and
a nit in the [September 29 review][review-parked] flagged that word against
copies of issue bodies. The run's retained verifier tally was **88 verdicts: 83
confirmed, 4 corrected, 1 unverifiable and 0 refuted**, as reported in [the
September 27 Round 3 review][review-round3] and the PR body's Round 3 section.
The run's returned workflow status was not kept. The [workflow at the
verification base][workflow-status] still assigns `unverified` or `incomplete`
when an unverifiable verdict is present; that tally cannot establish
`complete`, and the actual unsaved status cannot be reconstructed as a retained
result.

### Lessons on receipt practice

- Prose explaining a withdrawn disclosure can repeat it. Describe the type of
  correction without restating the private value; #392's Scope and Round 3
  sections preserve the correction history.
- `host_receipts.py` can reuse a freed identifier after withdrawal. A recording
  history must say when an identifier was reassigned, rather than imply an
  uninterrupted generation chain. See the [September 27 coordinator
  decision][review-coordinator], #392's Scope and Round 3, and the current
  [next-free generation implementation][free-id].
- Raw-output digests let a reader confirm a guessed user name. #492 fixed that
  basis for new recordings by hashing only the published sanitized excerpt;
  see [the current implementation][digest-source] and the [September 29
  follow-up][review-followup]. It does not repair the older receipt bytes.
- Set `catalog_revision` to a commit on main: a squash merge does not retain
  PR-branch commits as main ancestors. Making a revision reachable through a
  receipt tag does not satisfy that rule. The [September 29 review][review-parked]
  and this record's ancestry count explain the remaining gap.
- Assert comparisons, instead of only printing them. The RTK generation-3
  comparison repair is documented in #392's Round 3 and the [Round 3
  review][review-round3].
- Give a real-log check a synthetic positive control. The ccusage generation-2
  positive control in #392's Scope and Evidence-class table supplies an oracle
  for log interpretation without publishing the real private totals.

## History exposure

Closing #392 leaves its commits and `refs/pull/392/head` readable. GitHub's
[sensitive-data removal guidance][github-removal], read live for this decision,
explains that PR references can retain sensitive history, that `refs/pull/` is
read-only, and that complete removal requires separate handling. Closing is not
that handling; the head branch and its history are preserved.

The user-delegated decision on 2026-09-27 was **no purge**, recorded in the
[14:23 coordinator comment][review-coordinator]. The digest finding was reported
later, on 2026-09-29. Whether it changes the earlier no-purge decision remains an
owner item, not a builder action. This record contains no withdrawn file names
or leaking historical commit identifiers; the [PR body][pr392] remains the
location for the history discussion.

## Re-record path and overturn

A Mac owner can record fresh receipts in a new PR for components still selected
for the Mac. Record from a main checkout at or after
`c0ca46d1294ea2b286f629aa9550a7cae3be9e6b` (#492), and set `catalog_revision` to a
commit on main. Preserve the native returned results and the scope of each
evidence class under the [receipt policy][append-only] and [acceptance evidence
policy][acceptance-policy].

[Issue #276][issue276] stays open for that work. When fresh, selected-component
Mac receipts land and resolve these recording gaps, this record becomes history.
A timely objection or ownership claim within the custody window would prevent
this record from being written or landed; the coordinator must stop if such a
claim is found before completing the disposition.

[notice]: https://github.com/seathatflowsinourveins/native-agent-stack/pull/392#issuecomment-5967134206
[pr392]: https://github.com/seathatflowsinourveins/native-agent-stack/pull/392
[review-coordinator]: https://github.com/seathatflowsinourveins/native-agent-stack/pull/392#issuecomment-5856682298
[review-round3]: https://github.com/seathatflowsinourveins/native-agent-stack/pull/392#issuecomment-5857083744
[review-parked]: https://github.com/seathatflowsinourveins/native-agent-stack/pull/392#issuecomment-5883822009
[review-followup]: https://github.com/seathatflowsinourveins/native-agent-stack/pull/392#issuecomment-5884120039
[pr492]: https://github.com/seathatflowsinourveins/native-agent-stack/pull/492
[issue276]: https://github.com/seathatflowsinourveins/native-agent-stack/issues/276
[roadmap]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-28-ecosystem-roadmap.md#L178-L235
[digest-source]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/scripts/host_receipts.py#L1012-L1019
[append-only]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/contributing-evidence.md#L243-L259
[landscape]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/catalogs/landscape/foundation.json
[new-target]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-10-01-new-wsl-definitive-defaults.md#L78-L79
[new-target-prose]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-10-01-new-wsl-definitive-defaults.md#L292
[install-plan]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json#L1060-L1105
[open-work]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/blueprints/convergence-practice/clean-resolution-20261002/open-work.json#L38-L42
[mac-clients]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-10-02-two-host-north-star-architecture.md#L109-L111
[mac-pins]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/adoption/pins-macos-arm64.json
[stack]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/manifests/stack.json
[workflow-status]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/examples/claude-native/workflows/readiness-audit.js#L161-L162
[free-id]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/scripts/host_receipts.py#L840-L847
[acceptance-policy]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/acceptance-evidence-policy.md
[github-removal]: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
