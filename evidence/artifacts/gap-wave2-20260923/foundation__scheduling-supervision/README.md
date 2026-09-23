# Gap wave 2 (2026-09-23): foundation / scheduling-supervision

Crosswalk index at main 92bb279 (crosswalk PR #85). Branch
`claude/g2-scheduling-supervision-20260923`, base `41d39b3`. Six gaps were
assigned: 1, 2, 3, 4, 6 and 11. Preregistrations were committed in
`preregistrations/` (commit 7802cab, written 2026-09-22T22:42:40-04:00) before any
check ran. `results.json` is generated from the receipts by
`blueprints/gap-wave2-20260923/foundation__scheduling-supervision/make_results.py`.

An independent review of commit b7aec6b led to fix round 1. Its reruns are
preregistered in `preregistrations/fix-round-1.json`. That file was written at
about 23:26-04:00, after the original runs and the review, and is labelled as
such. It was committed in fdaf6f4 before any rerun started.

| Gap | Outcome | Receipt | Evidence class |
| --- | --- | --- | --- |
| 1 | advanced | `1-provider-cancel-broker-exactly-once.json` | local_integration |
| 2 | settled | `2-real-workflow-scheduled-recovered.json` | local_integration |
| 3 | covered_elsewhere | `3-dagu-2170-requalify.json` | source_review |
| 4 | advanced (was settled before fix round 1) | `4-challenger-harness.json` | local_integration |
| 6 | advanced | `6-executed-challenger-comparison.json` | local_integration |
| 11 | advanced | `11-reboot-real-workload-plus-upstream-retry.json` | local_integration |

## Coordinator note (2026-09-23)

The incident decision that the sections below leave open has since been
recorded. `incidents/2026-09-22-fix-round-heredoc-substitution.json` now reads
`"decision": "removed"`, and its `decision_note` gives the details:
- **Checked first:** the coordinator (agent-lab-17) re-ran `incident_observe.sh`
  read-only at 17:10Z. The default Dagu data dir held only its pre-incident
  `auth/` and `contexts/`, plus the five top-level directories the incident
  created. Nothing was modified after 23:26:00. The only running `dagu` used
  the `dagu-equities` home.
- **Removed:** those five directories (27 archive entries), at
  2026-09-23T17:11:09Z. They were archived first to a host-local backup,
  sha256 prefix `04abb941`.
- **After:** the data dir lists only `auth/` and `contexts/` again.

The four wildcard `:8090` binds from the original round stay disclosed. The
integration commit was scanned by the guarded gitleaks with `.gitleaks.toml`
and found no leaks. That scan covers `raw/fix3/`, the gap that Reconciliation 4
names below.

## What ran

- **Gap 1.** One bounded `codex exec --json` request ran as a Dagu 2.16.6 step.
  `dagu stop` was issued 5 s after `turn.started`. Dagu reported `aborted`, and
  the local client process tree was gone 150 ms later. The client emitted only
  `thread.started` and `turn.started`, with no usage object. The same detector
  finds usage in the completed gap-2 call. This shows the client was terminated
  locally and surfaced no usage. It does not show that the provider cancelled
  anything server-side. That, and when billing stops, cannot be observed without
  console access. The broker exactly-once arm is deferred to its owner,
  sota-workflow-resolution.
- **Gap 2.** The native `dagu scheduler` triggered a real maintenance workflow
  from a one-shot cron: `scripts/validate.py` and one Codex triage call at
  checkpoint, then `scripts/build_ecosystem.py --check` and `validate.py` at
  finalize, all on a `git archive` snapshot of 41d39b3. `dagu stop` produced
  `aborted` (triggerType 1, scheduler). `dagu retry --step finalize` produced
  `succeeded` under the same run id (triggerType 5, retry). The checkpoint and the
  model call each ran exactly once. Outputs equal a direct reference run.
  - The reported run is the fix-round rerun
    (`raw/fix1-F3-gap2-real-scheduled-rerun/`). It used a private config with
    `scheduler.port: 0`. The scheduler logged `Health check server disabled`, and
    14 `ss` samples found no listener in its process tree.
  - Before the model call, a Codex concurrency gate found 0 other `codex exec`
    processes.
  - The original run also passed. It is kept as superseded because its scheduler
    bound `:8090` on all interfaces.
- **Gap 3.** Covered by the #87 pin-qualification wave
  (`evidence/artifacts/sota-refresh-20260923/pins-runtime/dagu.json`). The
  receipt names the arms that wave did not run.
- **Gaps 4 and 6.** `challenger/compare.py` ran the unchanged job-recovery
  fixture on Dagu 2.16.6, Prefect 3.8.6 and a Temporal 1.9.1 dev server
  (temporalio 1.33.0). All three passed stop, retry and checkpoint reuse. The
  SIGKILL results depend on the protocol:

  | Engine | SIGKILL, preregistered protocol and 150 s bound | SIGKILL, post-hoc variant (270 s window) |
  | --- | --- | --- |
  | Dagu | fail: with no scheduler, retries were refused for 150.8 s (fix-round F1) | pass once a scheduler was started after the kill: 181.4 s (original run) and 182.6 s (F2), both beyond 150 s |
  | Prefect | fail: the run stayed `RUNNING` | fail: still `RUNNING` at 287.7 s |
  | Temporal | pass: 15.1 s, by starting a new worker | pass |

  - **Deviation, labelled late.** The original run used the Dagu scheduler and
    the 270 s window, but neither was preregistered. The scheduler was in the
    harness from the first Dagu debug iteration. The window was raised after that
    iteration's result was seen.
  - **Unequal recovery setups.** Temporal had its 5 s activity heartbeat timeout
    and Dagu (in the variant) had its scheduler. Prefect did not have its
    zombie-flow detection (heartbeats plus an automation), so Prefect's SIGKILL
    failure applies to this configuration only.
  - **Not run.** Restate (named in gap 4's text) and Dagster. Gap 4 is therefore
    advanced, not settled. A Restate comparison still needs a Restate adapter, a
    pinned restate-server and SDK, and its native verbs.
  - `raw/fix1-case-table-both-bounds.json` scores every run under both bounds.
- **Gap 11.** One `reboot_analog.py` invocation ran two oracles together:
  - The unchanged upstream `TestRetryCommand` tests at v2.16.6 passed with Go
    1.27.0: 15 pass records, 0 failures, and the source tree was unchanged.
  - The real workflow was carried through an orderly-restart analog made from
    two user+pid+mount namespaces. Status went from `aborted` to `succeeded`
    under the same run id, and the checkpoint ran once.

  The QEMU guest-reboot protocol itself was not reproduced. The binding blocker
  is the protocol driver's guard, which refuses any runner except a disposable
  GitHub-hosted one (`run.py` lines 149-150), together with the no-push rule.
  The missing qemu packages and kvm group are why a local port was not
  attempted; rootless routes exist and are named in the receipt. A first full run failed because the kernel recycled the
  pid-namespace inode number; that attempt is retained.

## Raw outputs

Everything a receipt cites is under `raw/`. Each subdirectory has a
`MANIFEST.json` with the raw and committed sha256 of every file. Committed copies
replace the host home path with `$HOME` and replace UUID-shaped identifiers with
`<uuid-N>` placeholders. The originals remain under
`$HOME/.cache/gap-wave2-20260923/scheduling-supervision/work/`.

Fix round 1 changed several helpers, so two reports relate executed scripts to
committed ones:

- `raw/executed-vs-committed-helpers.json` checks the original runs against the
  helpers committed at b7aec6b.
- `raw/fix1-executed-vs-committed-helpers.json` checks the fix-round runs
  against the helpers committed at 0889055. Fix round 3 later changed
  `dagu_common.py` (the Codex gate), so for that file the executed revision is
  0889055, not HEAD.

In both reports each helper is identical, or becomes identical once the
post-run home-path substitution is reversed. `raw/fix1-probe-controls.json`
holds the positive and negative controls for the listener probe and the
`codex exec` matcher. `raw/0-prior-interrupted-attempt/` keeps the logs of the
interrupted earlier session. That attempt used a manual `dagu start` with no
oracle, and it is superseded.

## Isolation and disclosures

- Installs went only into `$HOME/.cache/gap-wave2-20260923/scheduling-supervision/`.
  The network downloads were:
  - Prefect 3.8.6 and temporalio 1.33.0 wheel trees (PyPI, via uv). Prefect
    resolved to 104 distributions, 207.9 MB installed, and was **not** installed
    through `ecosystem-bounded-run`, although the heavy-build rule applied.
    temporalio resolved to 5 distributions, 56.6 MB installed. The download
    sizes were not recorded. Fix round 3 recorded both resolved sets
    (`raw/fix3/venv-*-freeze.txt`).
  - Temporal CLI 1.9.1 (45 MB, sha256 matches `checksums.txt` and the GitHub
    asset digest)
  - Go 1.27.0 (70.5 MB, sha256 pinned from go.dev)
  - the Dagu v2.16.6 source archive (sha256 pinned)
  - the Go module cache (2.1 GB, through `ecosystem-bounded-run`)

  Fix round 1 downloaded nothing.
- **Wildcard port binds (loopback-only rule broken).** In the original round,
  each Dagu scheduler started its `/health` server on `:8090` on all interfaces:
  - the gap-2 dry run, about 87 s
  - the gap-2 real run, about 85 s
  - debug iteration cmp-debug-p3, 30 s
  - the comparison's Dagu SIGKILL arm, about 3 minutes

  Fix round 1 set `scheduler.port: 0`. Dagu 2.16.6 treats an explicit 0 as
  disabled. All fix-round schedulers logged `Health check server disabled` and
  held no listener in any sample. Prefect and Temporal servers bound loopback
  ports only.
- **Incident in fix round 1** (`incidents/2026-09-22-fix-round-heredoc-substitution.json`).
  An unquoted shell heredoc used to write the fix-round preregistration executed
  the backquoted command names in its prose:
  - A `dagu scheduler` ran against the host's default Dagu home
    (`$HOME/.local/share/dagu/data`) for about 2 min 15 s. It bound `:8090` on
    all interfaces and created 27 scheduler, notification, incident and
    service-registry paths there. Fix round 2 showed that this is **not** the
    store of the running `dagu server` (pid 366, the dagu-equities service),
    which uses `DAGU_HOME=$HOME/.local/share/codex-ecosystem/dagu-equities`.
    The original record had wrongly inferred that it was.
  - No DAG run was created.
  - A `codex exec` was started and killed while it was still waiting for a
    prompt on stdin.
  - The unit did not delete the created files. The incident record lists them,
    with birth times for all of them, for a coordinator or user decision.
    **That decision is still open (`"decision": null`); integration of this
    branch should wait for it and record it in the incident file.**
  - The commands the unit used to assess the damage, and their outputs, are
    stored in `raw/incident-1/damage-assessment-tool-results.txt` (retained host-local and not published since the privacy sweep; see the coordinator note below).
- Apart from that incident, no PATH binary, `~/.config` file, systemd unit or
  live service was touched. The incident wrote no `~/.config` path. The
  accidental scheduler's log names the default home, not the running
  service's store, and a find over that store showed no path modified in the
  incident window (lock directories that the server keeps re-touching are
  outside what that check can see).
- **Model use.** Three `codex exec` calls ran one at a time: gap 1's aborted
  request, the original gap-2 triage call and the fix-round gap-2 triage call.
  Only the fix-round call recorded the rule "wait while 2 or more real
  `codex exec` processes run" (0 others). The first two calls had no recorded
  process-count check. The unintended incident `codex exec` never received a
  prompt. There were no Claude runs, no paid API calls, no credential reads and
  no broker contact.
- Every process these checks started was stopped. The result files list only
  their own driver, plus this unit's wait loop in fix round 1, as leftovers.

## Reconciliation 1 (2026-09-22, after the fix-round review)

The review of fix round 1 (head b1fb530) returned four findings. This pass ran no
new check. It corrected the records against evidence already on disk, stored the
raw outputs that existed but were not committed, and regenerated `results.json`
with `make_results.py`. The outcomes are unchanged: gap 1 advanced, gap 2
settled, gap 3 covered_elsewhere, gaps 4, 6 and 11 advanced.

1. **Major: the heredoc incident is an unresolved hard-rule breach.** Supported.
   The live Dagu data directory is still modified, and cleaning it up is not
   this unit's decision. The incident record now has `"status": "unresolved"`
   and `"decision": null`, and the incident bullet above says integration should
   wait for the decision. The pass also found and corrected errors in the
   incident's own claims:
   - Birth times were recorded (`stat %w`) for only 11 of the listed paths. For
     the other entries only the mtime is recorded, and for a directory an mtime
     in the window shows only that an entry changed. The statement that all
     listed paths were created in the window, and were absent before 23:22:42,
     now applies to those 11 paths only. Anyone removing files should first
     check the birth times of the others.
   - The Codex rollout check (`find ... | head`) returned exactly 10 lines,
     which is the `head` default, so its list may be truncated. The claim that
     no new rollout file was created is therefore not established. It is now
     marked that way.
   - The SIGTERM of the stray `codex exec` was sent at 23:25:10, not "about
     23:25:00", so the process ran for about 14 s.
   - That the running `dagu server` (pid 366) uses the same data directory is
     an inference. Both processes run with the default configuration, but the
     server's environment was not inspected. The record now says so.
   - The `grep schedule` in the find command was replaced by the RTK hook's
     usage text, so the schedules of the five DAGs were not recorded. The claim
     that no DAG run was created rests on two things: the find list, which is
     complete (28 entries, under its cap of 40), has no dag-runs path, and
     `state.json` shows no scheduled time.
   - `written_at` of the incident is now 23:26:12, the time of the editor call
     that created it (from the transcript). The earlier value, 23:26:05, was 7 s
     too early.
2. **Minor: the incident's damage-assessment observations had no stored raw
   output.** Supported. The 12 commands run from 23:22:42 to 23:25:55 are now
   committed as `raw/incident-1/damage-assessment-tool-results.txt`, together
   with their outputs. They were extracted verbatim from the fix-round unit's
   Claude transcript, since no other copy existed on disk. The source file is
   in the work cache, the home path is replaced by `$HOME`, UUIDs are replaced
   by placeholders, and both sha256 values are in `raw/incident-1/MANIFEST.json`.
   The outputs passed through the RTK hook, and one `ls -la` listing in them is
   condensed. `rtk recall` returned only its directory headers, and the record
   discloses this.
3. **Minor: the Codex concurrency matcher misses `codex <global options> exec`.**
   Supported. `codex_exec_processes()` checks only `argv[1] == "exec"`, or
   `argv[2]` after a node launcher, and the probe controls test only the plain
   form and a `timeout` wrapper. The helper was not changed. The committed and
   executed helpers must stay identical, and no rerun was authorized. Instead,
   receipt 2 now says the gate's "0 others" is a lower bound: it rules out only
   plain-form calls. This limit is also listed among the receipt's limits. Gap 2
   stays settled because none of its criteria depend on the gate. The wave's
   concurrency rule is shown only as far as this matcher can see.
4. **Minor: the first case-table line in receipts 4 and 6 read as the
   preregistered result.** Supported. That line and the Dagu SIGKILL line now
   begin by naming the original run under the post-hoc variant (scheduler
   started after the kill, 270 s window). They also state that under the
   preregistered protocol and the 150 s bound, Dagu's SIGKILL result is false.

Also noted, with no record change: the fix-round preregistration says it was
written at about 23:26:00. The transcript shows the editor write at 23:25:51.
The stated time is 9 s later than the write, so it is not back-dated, and the
commit (fdaf6f4, 23:26:19) still came before any rerun.

## Fix round 2 (2026-09-23, after the second review)

The second review (head 736a152) returned one blocker and two minor findings.
The preregistration is `preregistrations/fix-round-2.json`, written at 08:49:00,
before the observation ran at 08:49:14. Its `written_at` was first written as a
guessed 08:49:30 and was corrected to the file's birth time; the correction is
labelled in the file. No gap check was re-run, and all outcomes are unchanged.
`results.json` was regenerated with `make_results.py`.

1. **Blocker: the incident's live-store decision is open.** Supported. The
   review named two prerequisites for the decision, and both are now done.
   Neither involved a write:
   - The running `dagu server`, pid 366, uses
     `DAGU_HOME=$HOME/.local/share/codex-ecosystem/dagu-equities`. This comes
     from a filtered environ read that printed only home, dir and XDG
     variables. The same value is in the `dagu-equities.service` unit and in
     its open lock files. The accidental scheduler therefore wrote the idle
     default Dagu home, not the running service's store.
   - `stat %w` birth times now exist for all 28 listed paths. The data
     directory and its `auth/` and `contexts/` subdirectories date from
     2026-09-19. The other 27 paths were all born between 23:22:42 and
     23:24:00 on 2026-09-22. A full listing shows no other path.

   The incident record now describes both options exactly: leave the paths,
   or remove the five top-level paths that hold the 27 created ones. The
   decision stays `null`, because it belongs to the coordinator or the user.
   **The branch should not be integrated until that decision is recorded.**
   The raw outputs are in `raw/incident-1/fix-round-2-*.txt`, with their sha256
   values in `MANIFEST.json`.
2. **Minor: the per-receipt isolation statements did not mention the
   incident.** Supported. Every receipt (1, 2, 3, 4, 6 and 11) now has a limit
   that scopes its isolation claims to its own runs and points to the incident
   file. In receipt 2, the dagu-equities sentence now applies to the gap-2 runs
   only. Receipt 4's loopback sentence points to the new limit.
3. **Minor: receipt 11 did not name its executed helper revision.** Supported.
   Receipt 11 now has `executed_helper_revision: b7aec6b` and a matching limit.
   A hash table from b7aec6b to HEAD shows that four of the six g11 freeze-input
   helpers changed in fix round 1: `codex_cancel_probe.py`, `dagu_common.py`,
   `real_scheduled_recovery.py` and `real_steps.py`. The other two,
   `ns_init.py` and `reboot_analog.py`, are identical. The table is in
   `raw/incident-1/fix-round-2-equities-store-and-helper-revisions.txt`. To
   reproduce gap 11, use the b7aec6b helpers.

## Fix round 3 (2026-09-23, after the third review)

The third review (head 91fa4a4) returned one blocker and four minor findings.
The preregistration is `preregistrations/fix-round-3.json`, written at
10:15:57, before any fix-round-3 observation. No gap check was re-run and all
outcomes are unchanged. `results.json` was regenerated with `make_results.py`.
Raw outputs are in `raw/fix3/`, with sha256 values in `raw/fix3/MANIFEST.json`.

1. **Blocker: the incident decision is open.** Supported, and not resolvable by
   this unit: the review itself says the unit may not make the decision. A
   read-only re-run of `incident_observe.sh` at 10:16:05 found the default Dagu
   home unchanged since fix round 2: `auth/`, `contexts/` and the same five
   top-level created paths, nothing born or modified after 2026-09-22 23:26:00.
   So the recorded remove command still covers exactly the incident-created
   paths. `"decision"` stays `null`. **The coordinator must record leave or
   remove in the incident file before integrating this branch.**
2. **Minor: receipt 11 overstated the reboot blockers.** Supported. The receipt
   now names the driver's hosted-runner guard (`run.py` lines 149-150), together
   with the no-push rule, as the binding blocker. It describes the absent qemu
   packages and the kvm group as the reason a local port was not attempted, and
   names the rootless routes (`apt-get download` and `dpkg -x` into the cache,
   QEMU TCG without `/dev/kvm`). Such a port would also have to bypass the
   guard, so it would no longer be the unchanged protocol.
3. **Minor: the challenger venvs had no lock and no size.** Supported.
   `uv pip freeze` of both venvs is now committed. Prefect has 104
   distributions and 207.9 MB installed; temporalio has 5 and 56.6 MB. Every
   dist-info directory was born at the 22:51:50-22:51:51 install (corrected in
   the reconciliation below), and the newest dist-info birth equals the
   install time, so these are the sets that ran. The preregistered expectation that
   Prefect stays below 200 MB installed was wrong. Receipts 4 and 6 now state
   that the heavy-build rule applied and was not followed. The download size
   is not recoverable.
4. **Minor: `codex_gate()` proceeded after its timeout.** Supported and fixed.
   It now raises `CodexGateTimeout` when 2 or more other `codex exec` processes
   still run at `max_wait`, so no caller reaches the model call. The matcher
   now also counts `codex <global options> exec` and the `e` alias. The
   synthetic test `test_codex_gate.py` passes 3 of 3 on the fixed helper. On the
   pre-fix helper (git 91fa4a4) it fails the timeout case and the global-options
   and alias case, which shows that the test detects both defects. The unit's
   one gated call (F3) waited 0 s with 0 others, so no executed result changes.
   Receipts 1, 2, 4, 6 and 11 now carry a helper-change limit.
5. **Minor: receipt 3's covering artifact is not in this branch.** Supported.
   The file exists at 43bb931 (#87), sha256 `246f4b7c...8bbb8b`. 43bb931 is an
   ancestor of origin/main but not of this branch. Receipt 3 now records this
   in `covering_artifact` and a limit. **The integration target must contain
   43bb931.**

## Reconciliation 4 (2026-09-23, after the fourth review)

The fourth review (head a5cc403) returned one blocker and two minor findings.
This round ran no new check, made no model call, broker contact or download,
and changed no outcome. It only corrects records to match the evidence already
on disk. `results.json` was regenerated with `make_results.py`.

1. **Blocker: the incident decision is still open.** Supported, and still not
   resolvable by this unit. `"decision"` in
   `incidents/2026-09-22-fix-round-heredoc-substitution.json` stays `null`.
   The fix-round-3 read-only observation (`raw/fix3/incident-observe.txt`,
   10:16:05) is the latest evidence. It shows the same five top-level created
   paths and nothing born or modified after 2026-09-22 23:26:00, so the
   recorded remove command still covers exactly the 27 created paths. **Before
   merging, the coordinator or the user must record leave or remove, who
   decided, when, and for removal the command output (re-run
   `incident_observe.sh` first).** The four wildcard `:8090` binds from the
   original round remain disclosed and cannot be undone.
2. **Minor: the fix-3 handoff misreported the guarded gitleaks wrapper.**
   Supported. The wrapper exists as
   `$HOME/codex-ecosystem/bin/gitleaks-guarded`. Fix round 3 tried only
   `bin/gitleaks`, which does not exist (exit 127), and wrongly concluded that
   the wrapper was missing. That claim was only in the handoff, not in any file
   here. This round was told not to run new checks, so `raw/fix3/` is still
   **not gitleaks-scanned**. The reason is that no scan was run, not that the
   wrapper is missing. The reviewer's regex pass found no key, token, password
   or host-path strings, but that is not a gitleaks scan. Scan command for the
   coordinator: `gitleaks-guarded dir raw/fix3`.
3. **Minor: the install-time wording and the 600 s check were overstated.**
   Supported. The receipts' `resolved_dependency_sets.set_is_the_executed_set`
   field (receipts 4 and 6) and item 3 of the fix-round-3 section above now
   state the following:
   - Prefect dist-info births are 1790131910 (22:51:50-04:00). temporalio
     dist-info births are 1790131911 (22:51:51-04:00).
   - The heading says "epoch + iso", but the raw files print three unlabelled
     epoch-only lines.
   - The empty section "any file in venv modified after newest dist-info
     birth + 600 s" has no recorded exit status, file filter or detection
     control. Its window runs to about 23:01:51, which covers the first debug
     iteration (`cmp-debug-t-1790132113`, 22:55:13). It does not show that no
     file changed after the install.

   The executed-set conclusion rests only on the dist-info births: a
   reinstall would create a later dist-info directory, and the newest birth
   equals the install time. Both receipts have a `reconciliation_after_review_4`
   entry.

Raw-output check: every file in the fix-round-3 source directory
(`$HOME/.cache/gap-wave2-20260923/scheduling-supervision/work/fix-round-3`) is
committed in `raw/fix3/`, except `dagu_common_91fa4a4.py`. That file is an
input to the detection control, not an output. Its sha256 `7e47c8d6...5b664b4`
equals `git show 91fa4a4:blueprints/.../dagu_common.py`, so git already holds
it.

Outcomes are unchanged: 1 advanced, 2 settled, 3 covered_elsewhere, 4 advanced,
6 advanced, 11 advanced.

## Coordinator note (2026-09-23): privacy sweep

The catalog rule is: "Evidence belongs in compact sanitized receipts; no raw conversations, tokens, personal paths or machine-specific active client configuration." The PR #132 review found the host username, Claude transcript and plugin-data locations, worktree names and the active session environment in conversation-derived raw files, and the username in several command outputs.

Moved out of the repository (conversation-derived records). Each file is kept byte for byte in host-local, owner-only storage (directories 0700, files 0600) outside the repository and is not published. Every reference keeps its relative name and sha256 and is marked `"published": false` with a `retention` note:

- `raw/incident-1/damage-assessment-tool-results.txt`: sha256 `c53879ff5ad1...`, 42523 bytes

Host username replaced by `<user>` (`-home-<name>-` project slugs become `-home-<user>-`). Raw command outputs are otherwise unchanged; metadata files also had the text changes listed under "Pins updated":

- `raw/4-6-three-engine-comparison/temporal__sigkill__native__final-history.stdout`: 1 replacement(s), sha256 `adea93df749d...` -> `e1244c41d4d8...`
- `raw/4-6-three-engine-comparison/temporal__stop-retry__native__final-history.stdout`: 2 replacement(s), sha256 `f4135f78b17c...` -> `8f49dc5d3276...`
- `raw/4-6-three-engine-comparison/temporal__stop-retry__native__history.stdout`: 2 replacement(s), sha256 `4f5817d25765...` -> `cbb3cdf4f59e...`
- `raw/fix3/incident-observe.txt`: 11 replacement(s), sha256 `c2d4b3b13ccb...` -> `860c6822b8ed...`
- `raw/fix3/receipt-3-11-checks.txt`: 1 replacement(s), sha256 `572711696a5f...` -> `58b78fa07a02...`
- `raw/incident-1/fix-round-2-incident-observe.txt`: 11 replacement(s), sha256 `4a20109b538c...` -> `2162432fb375...`

Pins updated: `raw/incident-1/MANIFEST.json` (the damage-assessment entry is marked not published; the fix-round-2 observation's `committed_sha256` is updated; `raw_sha256` and the raw `bytes` value are unchanged), `incidents/2026-09-22-fix-round-heredoc-substitution.json` (new `raw_output_unpublished` entry), `raw/fix3/MANIFEST.json` and `raw/4-6-three-engine-comparison/MANIFEST.json` (`committed_sha256` and `bytes`, and the `substitution` text). `collect.py` now applies the same username replacement.

## Coordinator note (2026-09-23): privacy sweep, second pass

Host name replaced by `<host>` in these command outputs; the outputs are otherwise unchanged. The redaction was checked by rerunning `collect.py` from the retained cache sources for `2-real-scheduled-run`, `4-6-three-engine-comparison`, `fix1-F2-dagu-sigkill-scheduler-variant` and `fix1-F3-gap2-real-scheduled-rerun`: every committed file and each `MANIFEST.json` came out byte-identical. `incident-1` was assembled from several sources and was not rerun:

- `raw/2-real-scheduled-run/native__scheduler.stderr`: 6 replacement(s), sha256 `5ed69c89e845...` -> `cedd4fd9b02e...`
- `raw/4-6-three-engine-comparison/dagu__sigkill__native__scheduler.stderr`: 6 replacement(s), sha256 `9a9ddb766102...` -> `1e16202649cc...`
- `raw/4-6-three-engine-comparison/temporal-server__server.stderr`: 2 replacement(s), sha256 `1b31608b2e22...` -> `5f145fdf0d14...`
- `raw/4-6-three-engine-comparison/temporal__sigkill__native__final-history.stdout`: 13 replacement(s), sha256 `e1244c41d4d8...` -> `1ccd7c982afb...`
- `raw/4-6-three-engine-comparison/temporal__stop-retry__native__final-history.stdout`: 14 replacement(s), sha256 `8f49dc5d3276...` -> `c978c20c46bc...`
- `raw/4-6-three-engine-comparison/temporal__stop-retry__native__history.stdout`: 17 replacement(s), sha256 `cbb3cdf4f59e...` -> `2dbe55f8a619...`
- `raw/fix1-F2-dagu-sigkill-scheduler-variant/dagu__sigkill__native__scheduler.stderr`: 6 replacement(s), sha256 `cd3f95d17ef0...` -> `ba7fc6aa6a25...`
- `raw/fix1-F3-gap2-real-scheduled-rerun/native__scheduler.stderr`: 6 replacement(s), sha256 `b3e03aa70622...` -> `eed0f21fb219...`
- `raw/incident-1/background-shell-output.txt`: 6 replacement(s), sha256 `60ab7b004cf8...` -> `626b01eb1378...`

Pins updated: `committed_sha256` and `bytes` in the `MANIFEST.json` of `raw/2-real-scheduled-run`, `raw/4-6-three-engine-comparison`, `raw/fix1-F2-dagu-sigkill-scheduler-variant`, `raw/fix1-F3-gap2-real-scheduled-rerun` and `raw/incident-1`, plus their `substitution` text. `collect.py` now replaces the host name as well, and names the username and host-name substitutions in `substitution` only when they occurred.
