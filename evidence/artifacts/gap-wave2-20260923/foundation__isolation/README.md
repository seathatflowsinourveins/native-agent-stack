# foundation / isolation — gap-wave-2 (2026-09-23)

Unit `gap-wave-2`, layer `foundation/isolation`, crosswalk index at main `92bb279`
(crosswalk PR #85). Worktree `~/code/nas-wt-g2-isolation`, branch
`claude/g2-isolation-20260923`, base `origin/main` at `41d39b3`.

Three passes produced this directory:

1. First pass, commit `e112454` (checks ran 2026-09-23 00:37Z to 00:50Z).
2. Fix round after the first independent review, commit `9874beb` (checks ran 01:01Z to 01:28Z).
3. Reconciliation after the second independent review (this commit). It ran
   no new checks. It matched every receipt to the raw worker record, corrected
   records, timestamps and descriptions, changed outcomes where the evidence
   was weaker than claimed, and committed the raw outputs.

Components: `sandbox-runtime` 0.0.77 (package.json of the resolved install;
`srt --version` prints the CLI version 1.0.0), Worktrunk `wt` v0.79.0
(`wt --version`), and for gap 5 the Rust toolchain 1.97.0 pinned by
Worktrunk's `rust-toolchain.toml`.

## Outcomes

`results.json` and `_index.json` are generated from the receipts by a script
(`gap_index -> outcome, receipt`); the table below is generated the same way.

<!-- outcomes-table:start -->
| gap | outcome | receipt | reason |
|---|---|---|---|
| 0 | advanced | `0-network-fixture-extension.json` | TLS, SOCKS5 and remote host allow/deny ran; IPv6 allow only; DNS rebinding not tested live (cause of failed lookups undetermined) |
| 1 | settled | `1-filesystem-fixture-versioned.json` | filesystem permit/deny rerun at 0.0.77 with version and sha256 recorded; fixture hashes reconcile |
| 2 | settled | `2-readiness-race-quantified.json` | 8/8 first requests failed without retries at 0.0.77 (latest); no upstream fix found |
| 3 | settled | `3-overlapping-denyread-write-reproduced.json` | overlapping denyRead+allowWrite reproduced: write exit 0, host unchanged |
| 4 | advanced | `4-resource-limit-workloads.json` | srt alone set no memory/fork limit on small workloads; disk, CPU-rate and a workload-reaching fork cap not shown |
| 5 | advanced | `5-worktrunk-0-79-0-cargo-test.json` | cargo test passed through the wrapper at 1.97.0; merge (fast-forward), unmerged deletion and bash integration ran; picker and user-repo workflows not |
| 6 | advanced | `6-worktrunk-lifecycle-rerun-versioned.json` | 0.79.0 lifecycle rerun with version recorded, but not the historical harness steps |
| 7 | settled | `7-worktrunk-dirty-removal-refused.json` | dirty removal refused (exit 1), files byte-identical, at v0.79.0 |
| 8 | advanced | `8-worktrunk-crash-cleanup-fixture.json` | crash and selective prune ran in separate repositories; stage_refs not updated |
| 10 | not_settled | `10-podman-boundary-deferred.json` | static Podman installed, podman info failed (conmon); blockers not established, isolated routes untried |
| 12 | advanced | `12-worktrunk-crash-cleanup-fixture-dup.json` | crash transcript with a no-op prune; the first clause not tested |
| 13 | advanced | `13-network-and-resource-limits-combined.json` | union of gaps 0 and 4 |
| 14 | covered_elsewhere | `14-readiness-race-quantified-dup.json` | subset of gap 2 (settled) |
| 15 | advanced | `15-overlapping-denyread-write-reproduced-dup.json` | three configurations gave no direct denial; question narrowed, not closed |
| 17 | not_settled | `17-podman-comparison-deferred.json` | no working Podman (gap 10), so no comparison ran |
| 18 | advanced | `18-worktrunk-lifecycle-rerun-versioned-dup.json` | 0.79.0 rerun compared with the historical pass; fixtures differ |
<!-- outcomes-table:end -->

## Raw evidence

`raw/` holds the raw record every receipt cites. Each receipt's
`raw_evidence` lists the file, its sha256 and the call ids (`original#N`,
`fix#N`) it relies on; `raw/SHA256SUMS` and `raw/provenance.json` list every
raw file with its source.

- `raw/original-session-tool-calls.txt` and `raw/fix-session-tool-calls.txt`:
  every tool call of the first-pass and fix-round worker sessions after the
  initial reads, with call and result timestamps, the exact input and the
  output as the worker saw it. They were extracted from the Claude Code
  subagent transcripts. The source transcript sha256 values are in
  `raw/provenance.json`. (retained host-local and not published since the privacy sweep; see the coordinator note below)
- `raw/fix38-persisted-output.txt`: the full fix#38 output that Claude Code
  saved separately because of its size. (retained host-local and not published since the privacy sweep; see the coordinator note below)
- `raw/original63-background-output.txt`: the background output of
  original#63. That call was a second, unwrapped `cargo test` plus
  `cargo build --release`.
- `raw/rtk-recall-*.txt`: two grep outputs over the cargo logs, recovered
  with `rtk recall HASH --full`.

Redactions: host home becomes `$HOME`, the session scratchpad becomes
`$SCRATCHPAD`, UUIDs become `<uuid>`, srt per-session proxy tokens and Basic
proxy credentials become `<redacted>`, and `/Users/<name>` in upstream help
text becomes `/Users/<user>`. The RTK Bash hook condensed some outputs (for
example `ls`, `find`, `grep` and the first-pass cargo summary) before the
worker saw them, so those blocks show the condensed text. The untransformed
logs under `/tmp/gapfix` and `~/.cache/gap-wave2-20260923/isolation` were
deleted at teardown (original#86, fix#72). They are gone from disk (checked
during reconciliation) and cannot be recovered.

## Reconciliation (2026-09-23, no new checks)

### Second-review findings

1. **results.json and _index.json disagreed with the receipts (major).**
   Supported. Both files are now generated from the receipts by a script, and
   the outcome table above comes from the same source. Gaps 5 and 6 are now
   `advanced` in the maps and 8 is `advanced` everywhere (see finding 5).
   Gap 15's stale `covered_elsewhere` in `_index.json` is gone.
2. **Gap 1's retained denyRead fixture did not match its recorded sha256
   (major).** Supported. The fix round had rewritten the host home path to `~` in the
   retained file after the run. The file now contains the literal `$HOME`.
   Reversing that substitution reproduces the as-run sha256 `b67c149d...`,
   which was checked during reconciliation by hashing only. The receipt's
   `fixtures` block records both hashes and the transform. Gap 1 stays
   `settled`.
3. **Gap 6's shell-integration step could not follow the merge (major).**
   Supported. The raw record (fix#22) shows that the shell-integration
   `wt switch feat-merge` ran *before* the merge in the same call, while the
   worktree still existed. The receipt had moved it to the end. These steps
   now live in gap 5, in the recorded order. The merge was only a
   fast-forward (`no commit/squash/rebase needed`), and the squash/rebase
   claim is removed. The raw record also shows two steps the receipt had left
   out: `wt remove -D` through `-C` failed with exit 1 (fix#23), and
   `wt config shell install` was attempted under the real HOME (fix#19). That
   attempt was cancelled at the prompt, and a grep of `~/.bashrc` afterwards
   found no `wt` lines.
4. **Gap 6 no longer held its own versioned lifecycle pass; gaps 6 and 18
   cited each other (major).** Supported. Gap 6 and gap 18 each carry the
   0.79.0 lifecycle calls (original#53, #55, #56, #59). The historical pass's
   recorded fields are compared with the rerun using the files on disk. The
   rerun created 1 worktree where the historical pass created 2, on `master`
   instead of `main`, and made no hooks-disabled assertion. Gap 6 stays
   `advanced`, now with that reason; the earlier reason, the picker, belongs
   to gap 5. Gap 18 changes from `covered_elsewhere` to `advanced`.
5. **Gap 8 was settled without the kill-mid-write step (major).** Supported.
   The crash (original#57) and a selective prune (fix#30, fix#32) happened in
   different repositories. The prune after the crash had no candidate
   (`No merged worktrees to remove`), so it could not show a preservation
   failure. The `stage_refs` update was not made. Gap 8 changes from
   `settled` to `advanced`. Gap 12 now holds its own crash transcript and
   changes from `covered_elsewhere` to `advanced`. The gap 12 limit copied
   from gap 8 is removed.
6. **Preregistration and checked_at timestamps (major).** Supported, and
   worse than reported. The transcript shows that every original
   `preregistration.written_at` was invented. The texts were written at
   00:52:08Z (gaps 0-4) and 00:53:17Z (gaps 5-18), after the commands, and
   the recorded values ran from 00:35Z to 02:20Z, some later than the commit
   that introduced them. The fix-round blocks were written between 01:27Z and
   01:38Z, after the fix-round commands had run (01:01Z to 01:28Z), but were
   given placeholder times from 01:10Z to 01:40Z. Every block now carries its
   real write time from the transcript, `late: true`, and a note naming the
   replaced value. Gaps 14 and 15 are now `late: true`. `checked_at` is now
   the result time of the last cited call, and `checked_at_note` gives the
   window. The earlier README sentence claiming the fix-round blocks were
   written before their checks was false and is removed.
7. **Gaps 7 and 18 could not show the "fresh independent repository"
   claim (minor).** Supported, and the claim itself was false. Gaps 6, 7, 12
   and 18 all cite one continuous repository session (original#53-#59).
   Their commands now start with that session's `git init` and
   `wt --version` (original#53). The false independence limit is replaced by
   a description of the session.
8. **Gap 0 attributed the DNS result to nip.io policy without a test
   (minor).** Supported. The cause is now recorded as undetermined. Public
   encodings resolved, and private and loopback encodings did not, through
   the WSL resolver. No lookup bypassed that resolver, so resolver filtering
   and provider behaviour were not separated. Other corrections from the raw
   record: `vcap.me`, not `lvh.me`, resolved to 103.224.182.214. Names that
   were tried but missing from the receipt are added. IPv6 was tested for
   allow only. Gap 0 stays `advanced`.
9. **Gap 10's conmon blocker rested on a filtered listing (minor).**
   Supported. The grep pattern had no `conmon` term, and extraction was
   limited to `usr/local/bin`, so it is unknown whether the archive ships
   conmon (podman searches `/usr/local/lib/podman/conmon`). The raw record
   also shows that passwordless sudo exists (original#48, fix#4). The missing
   `newuidmap`/`newgidmap` are therefore blocked by this unit's install scope,
   not by host capability. Gap 10 changes from `deferred` to `not_settled`,
   and the untried isolated routes are named. Gap 17 depends on gap 10 and
   also changes from `deferred` to `not_settled`.
10. **Gap 4's grep count and gap 5's per-suite quote (minor).** Supported.
    Gap 4 now lists the three commands that ran (fix#51, fix#52). The rlimit
    search covered `.js` files only, and the native apply-seccomp helper was
    not searched. Gap 5 quotes the ten `test result:` lines verbatim.

### Further corrections found in the raw record

- **Gap 4, TasksMax=20:** the limit stopped srt's own startup
  (`apply-seccomp: fork(worker)`) before the Python fork loop ran, so the
  case does not show the outer cap stopping the workload. For the CPU case,
  `exit=0 elapsed=6s` is recorded without `LOOP_COMPLETED`. For the memory
  kill, no OOM log was captured.
- **Gap 5:** attempt 1 used `ECOSYSTEM_JOB_TASKS_MAX=512`, not 256 (fix#29).
  The first pass also ran a second unwrapped `cargo test` and a release build
  (original#63). The network downloads are now disclosed. The fix-round Rust
  work took about 24 minutes (01:04Z to 01:28Z), not "under 10 minutes";
  each single attempt stayed under the 20-minute time-box.
- **Gap 15:** the note said the work "settles" the question while the
  outcome was `advanced`. The note now says the question was narrowed: three
  configurations cannot show that no configuration gives a direct denial.
- **Gap 2:** #257 is a pull request, and the exact eight-run loop replaces
  the `for i in 1..8` pseudocode.
- **Commands:** every receipt with executed calls now lists the exact
  command text of each cited call, with its call id and timestamp.
- **Shared cache deleted:** the first-pass worker ran
  `rm -rf ~/.cache/gap-wave2-20260923` (original#86, 00:56:57Z). That
  removed the whole 9.6G wave cache root, not just `isolation/`. Other units
  kept directories there, so this went beyond the unit's install scope. It
  was not reported before. The coordinator should check whether sibling
  units lost cached state at that time.

No finding was judged unsupported.

## What remains open

- **Gap 0/13:** an IPv6 deny case; a live DNS-rebinding case (untried
  isolated route: srt inside `unshare --user --map-root-user --mount` with a
  loopback-only resolver bind-mounted over `/etc/resolv.conf`, if bwrap works
  there); general escape resistance.
- **Gap 4/13:** disk quota, CPU-rate limits, a fork case with a TasksMax that
  lets srt start, the native helpers, and VM-boundary or hostile-workload
  probes.
- **Gap 5:** the interactive picker, user-repository workflows, hooks-enabled
  flows, and the squash/rebase merge path.
- **Gap 6/18:** rerun the historical lifecycle fixture's exact steps at
  0.79.0 and compare field by field.
- **Gap 8/12:** one fixture that kills a writer mid-write and then prunes with
  a real candidate present, then the `stage_refs` update.
- **Gap 10/17:** list and extract the full podman-static archive into the
  cache prefix and point podman at its helpers; check rootless single-ID
  mapping without newuidmap; then run the fixtures in a container and
  compare.
- **Gap 15:** other denyRead/denyWrite combinations, or a reading of how srt
  builds the bwrap mounts.

## Hard-rule notes

- No file under `catalogs/landscape/*.json`, `catalogs/sota-convergence/*`,
  `catalogs/us-equities/gates-*.json`, `docs/grand-catalog-handbook.md` or
  `evidence/artifacts/layer-verdicts-*` was modified.
- No broker, paper-account, ai-memory or model-service call was made in any
  pass (the raw record mentions ai-memory and `codex exec` only in a
  directory listing and in Worktrunk help text). Network use: GitHub API and
  npm registry reads, the example.com allow/deny fixture, DNS lookups of the
  wildcard names in gap 0, and the downloads listed in gaps 5 and 10.
- Deviations recorded in the raw record: the first pass ran rustup and
  `cargo test`/`cargo build --release` without `ecosystem-bounded-run`
  (superseded by the fix round); fix#19 attempted a shell-integration install
  under the real HOME (cancelled at the prompt); original#86 deleted the
  whole wave cache root.

## Coordinator note (2026-09-23): privacy sweep

The catalog rule is: "Evidence belongs in compact sanitized receipts; no raw conversations, tokens, personal paths or machine-specific active client configuration." The PR #132 review found the host username, Claude transcript and plugin-data locations, worktree names and the active session environment in conversation-derived raw files, and the username in several command outputs.

Moved out of the repository (conversation-derived records). Each file is kept byte for byte in host-local, owner-only storage (directories 0700, files 0600) outside the repository and is not published. Every reference keeps its relative name and sha256 and is marked `"published": false` with a `retention` note:

- `raw/original-session-tool-calls.txt`: sha256 `880d0b807550...`, 185882 bytes
- `raw/fix-session-tool-calls.txt`: sha256 `b1a1bce67008...`, 189243 bytes
- `raw/fix38-persisted-output.txt`: sha256 `660b1f6470ba...`, 36888 bytes

Host username replaced by `<user>` (`-home-<name>-` project slugs become `-home-<user>-`). Raw command outputs are otherwise unchanged; metadata files also had the text changes listed under "Pins updated":

- `raw/provenance.json`: 3 replacement(s), sha256 `472912db3699...` -> `bf8519ecb057...`

Pins updated: the `raw_evidence` entries of the 16 receipts that cite the session files, `raw/provenance.json` (its three session entries, and its `redactions` text) and `raw/SHA256SUMS` (the three session lines are removed; `provenance.json`'s line is updated).

## Coordinator note (2026-09-23): privacy sweep, third pass

RFC 1918 addresses replaced by `<lan-ip>` (loopback and 0.0.0.0 unchanged):

- `0-network-fixture-extension.json`: 1 replacement(s), sha256 `d37cf8c6c700...` -> `d8e729dc99eb...`

Pins updated: none (the receipt's hash is pinned only in `manifests/evidence.json`). The DNS-rebinding test encodings `10.0.0.1` and `192.168.1.1` (the `*.nip.io` names the check resolved) are synthetic test inputs, not addresses of this host or LAN, and are kept.
