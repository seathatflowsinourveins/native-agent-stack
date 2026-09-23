# Gap wave 2: foundation/workers

Unit: gap-wave-2 (branch `claude/g2-workers-20260923`), base origin/main 41d39b3, worktree
`<worktree-root>/nas-wt-g2-workers`. Nine gaps for layer_id `workers` (crosswalk PR #85, index 92bb279).

History (times UTC, taken from the unit transcripts and git):

- First round: 00:36:49Z to 00:51:01Z, commit 1a4448c at 00:50:10Z.
- Fix round: 00:52:46Z to 01:09:47Z, commit ddf4b2e at 01:08:43Z.
- Reconciliation pass: 2026-09-23 02:19Z onward. It ran no new gap checks and aligned every claim with the evidence on disk. See "Reconciliation" below.

Current outcomes (generated into `results.json` by `make_results.py` from the receipts):

| gap | outcome | receipt |
| --- | --- | --- |
| 0 | deferred | `0-head-to-head-comparison-deferred.json` |
| 1 | advanced | `1-wt-model-child-dispatch.json` |
| 2 | deferred | `2-workflow-crash-deferred.json` |
| 3 | advanced | `3-child-usage-accounting-advanced.json` |
| 4 | deferred | `4-restricted-role-recovery-deferred.json` |
| 5 | advanced | `5-worktrunk-dirty-sibling-crash-probe.json` |
| 6 | deferred | `6-review-workflow-project-settings-deferred.json` |
| 7 | deferred | `7-sealed-oracle-deferred.json` |
| 8 | advanced | `8-beads-kill-restart-integrity.json` |

No gap is settled.

## What was executed and what remains

- **Gap 1** (advanced): one Codex child (`codex exec --sandbox workspace-write --ephemeral`) ran in a worktree created by wt v0.79.0 `wt switch --create ... --format=json`. It reported that worktree's own branch and path and created `owned-change.txt`, which was verified independently after the child exited. `wt remove` without `--force` refused the dirty worktree, and `--force --foreground` then removed it. Remaining: the next_check's wording reconciliation between `docs/token-native-saturation.md:121` ("optional") and `catalogs/foundation/decisions.json` owned-worktrees ("default").
- **Gap 3** (advanced): the tracked `examples/claude-native/workflows/child-usage.mjs` passes its 16 bundled tests. The recovery run's published residual splits into 205454 tokens for claude-fable-5-1 (202569 of them cache_read) and 247 for claude-opus-5. Remaining: the per-request-ID run. That run is executable on this host, because the recovery journal and main transcript exist under `$HOME/.claude/projects/` with matching sha256 values.
- **Gap 5** (advanced): across 10 scripted process-group SIGKILLs of `wt remove --foreground`, the dirty sibling worktree was never touched. Remaining: a probe that can observe partial `.git/worktrees` state, and a completed worktrunk Rust suite from this unit. The isolation unit reports its own suite run, which is not yet integrated.
- **Gap 8** (advanced): one targeted SIGKILL of `bd create` and several exploratory kills left no partial issue and a working embedded-dolt store. Remaining: a write-in-progress signal, a store-consistency check, and the companion-session clause.
- **Gaps 0, 2, 4, 6, 7** (deferred): each needs a Claude multi-agent or multi-session run. The unit rules defer those while the shared Claude account is reserved for another session's long-horizon comparison, and they allow one bounded single call. A temp HOME, `unshare` or a loopback-only instance changes host state, not account use, so none of them makes these checks executable here. A Codex substitute would not test the Claude-specific claim in any of the five.

Raw evidence (`raw/`, host paths replaced by `$HOME`/`$SCRATCHPAD`, sha256 in `manifests/evidence.json`):

- `gap{1,3,5,6,8}-transcript-extract.json` (retained host-local and not published since the privacy sweep; see the coordinator notes below): exact tool-call inputs and returned outputs, copied from the unit's native transcripts. The gap 5 file also includes the isolation unit's `rm -rf` call. Each entry has its own `output_sha256`, and receipt commands point to entries with `raw_output`.
- `gap5-cargo-test-rtk-recall-b8772aefe188.txt`: the full cargo output recovered from the RTK store (the transcript held a condensed copy).
- `probe.py`, `probe-output.json`: the gap 5 probe and its output, sanitized. Before sanitization their sha256 values were 57ea19c6... and 1aa7a1c2..., which match the live files. The live scratch copies were deleted with the shared prefix.
- `reconciliation-readonly-disk-lookups.txt`: read-only lookups made in this pass.

## Reconciliation

Source: the latest independent review of ddf4b2e (verdict `fix_required`, seven findings). Evidence used: the unit transcripts and files on disk. No gap check was re-run.

1. **Major, gap 1 overclaimed as settled.** Supported. The gap text and next_check include the wording reconciliation, and it was not done. Outcome changed from settled to advanced, with the wording reconciliation named as the remainder. Also corrected:
   - The claimed reason for not editing was false. Neither file was on the forbidden list, and there was no assigned-path limit.
   - The claim that the refusal was "previously only verified on 0.78.0" was false. The existing `worktrunk-0-79-0-requalify.json` already recorded `dirty_removal_refused=true` on 0.79.0.
   - Commands now match the transcript exactly.
   - Disclosed: the rerun used workspace-write rather than the rules' preferred read-only sandbox.
2. **Major, gap 5 cargo isolation and command accuracy.** Mostly supported, one part corrected.
   - (a) Supported. The build ran as `timeout 900 cargo test --release` without `ecosystem-bounded-run`. This is disclosed as a rule violation, together with the network downloads: rustup-init, the stable minimal toolchain, toolchain 1.97.0 auto-installed from worktrunk's pin, and 429 crates.io downloads.
   - (b) Supported as a recording error. The transcript shows `export CARGO_HOME=... RUSTUP_HOME=...` before the pipeline, and the installer printed the prefix's `cargo-home/bin`. The install therefore went into the prefix, which fits `~/.rustup` and `~/.cargo` being absent now. The receipt now carries the exact command, and its duration is corrected from 90 s to 14 s.
   - (c) Partly unsupported. The review was right that the receipt proved nothing about the deletion. The transcripts now do. The foundation/isolation unit in the same workflow ran `rm -rf $HOME/.cache/gap-wave2-20260923` at 00:56:57.790Z, inside this unit's build window (00:55:41Z to 00:57:33Z). This unit's own deletions were fix5 subdirectories at 00:54:54Z and `fix1` at 01:08:50Z. The `fix1` deletion explains the empty `workers/` directory with mtime 01:08:50Z that the review observed. The receipt names the isolation unit instead of speculating, and states that per-unit directories under a shared prefix did not isolate concurrent units.
3. **Major, gap 5 probe could not detect torn state.** Supported. The claims "no torn state reproduced" and "closes that hole" are withdrawn. The receipt now states the detection method and its limits: directory presence and worktree-list paths only, with the target reused across trials. It also explains that `killed_process_group: true` is uninformative, because killpg succeeds on an unreaped zombie. Sibling safety stays the narrowed clause. The status check can detect deletion of the sibling directory, its file, its `.git` file or its admin entry. Outcome stays advanced.
4. **Major, gap 3 circular "fully accounted".** Supported. The receipt now describes a decomposition of the recorded residual, not an accounting of it, and notes that the split was already published. It keeps advanced, as the review allowed. The disk check also found that the stated blocker was false for this host. The recovery journal (`f7c29223...`) and main transcript (`175115de...`) exist under `$HOME/.claude/projects/` with matching hashes. The remaining per-request-ID run is therefore executable here and is named as the remainder.
5. **Minor, gap 5 two hashes for one file.** Supported with an explanation. `1aa7a1c2...` is the live output before host-path sanitization, and `437e855f...` is the committed sanitized file. Both were recomputed from the transcript text. Each hash now carries its label.
6. **Minor, gap 6 id and outcome.** Supported. The source reading did not narrow the executed claim. Outcome changed from advanced to deferred with the account-reservation blocker. The file was renamed back to `-deferred.json`, the id fixed, and the manifest path updated.
7. **Minor, gap 8 companion clause without a blocker.** Supported. The named blocker: the clause needs two concurrent Claude Code sessions driving the Codex companion. The unit rules defer multi-session Claude use while the account is reserved and allow at most one concurrent Codex call. Neither an isolated HOME nor a namespace changes that. Also disclosed: the exploratory kills and the unread `kill_target.log`.

Other corrections found in the transcripts:

- **Timestamps.** Every receipt carried a fictitious time. The first-round generator hard-coded `00:55:00Z`, later than its own write (00:47:23Z) and the commit (00:50:10Z). The fix round wrote `01:20:00Z`, later than its commit (01:08:43Z). Each `preregistration.written_at` now holds the actual write time and is labelled post hoc. Each `checked_at` now holds the time of the check's last command.
- **Deferral wording.** The stated reasons for gaps 4 and 7 were replaced with the real blocker. The old gap 4 reason ("no mechanism to interrupt asynchronously") was false. The old gap 7 reason cited the 20-minute time-box, which is a stop rule, not a reason to defer.
- **Gap 3 command.** One command did not appear in the transcript and was replaced with the actual one.
- **ai-memory.** No ai-memory CLI or HTTP call was made in either round or in this pass.

Forbidden paths (catalogs/landscape, catalogs/sota-convergence, catalogs/us-equities/gates-*, docs/grand-catalog-handbook.md, evidence/artifacts/layer-verdicts-*) were not modified. There was no broker or paper contact.

## Coordinator note (2026-09-23)

The final verification found that this layer's `codex exec` child ran the user-level Codex hooks. Those hooks are ai-memory lifecycle hooks aimed at the live store (default data dir, live service on 127.0.0.1:49374), so the child's prompt and answer were probably captured as session observations, like any Codex session on this host. That breaks this wave's hard rule that no unit may write to the live ai-memory store. The receipts' statement that no ai-memory call was made is therefore not supported for the Codex child: its compliance check searched only Claude transcripts. No page was written. Future lane and gap runs should launch `codex exec` with hooks disabled or with an isolated `CODEX_HOME`.

## Coordinator note (2026-09-23): privacy sweep

The catalog rule is: "Evidence belongs in compact sanitized receipts; no raw conversations, tokens, personal paths or machine-specific active client configuration." The PR #132 review found the host username, Claude transcript and plugin-data locations, worktree names and the active session environment in conversation-derived raw files, and the username in several command outputs.

Moved out of the repository (conversation-derived records). Each file is kept byte for byte in host-local, owner-only storage (directories 0700, files 0600) outside the repository and is not published. Every reference keeps its relative name and sha256 and is marked `"published": false` with a `retention` note:

- `raw/gap8-transcript-extract.json`: sha256 `2fa5e907122d...`, 16243 bytes

Pins updated: `8-beads-kill-restart-integrity.json`: each command whose `raw_output` points into the extract carries `raw_output_published: false`, and a new `raw_evidence` entry records the extract's sha256 and size. The claim's published support is each command's `cmd`, `exit`, `output_excerpt` and `output_sha256`.

## Coordinator note (2026-09-23): privacy sweep, second pass

Moved out of the repository: every remaining conversation-derived record (transcript extracts and transcript tool-call/tool-result captures). Each file is kept byte for byte in host-local, owner-only storage (directories 0700, files 0600) outside the repository and is not published. Every reference keeps its relative name and sha256 and is marked not published with a `retention` note; the receipts' own published fields (`cmd`, `exit`, `output_excerpt`, and `output_sha256` where present) remain the published support:

- `raw/gap1-transcript-extract.json`: sha256 `d15fbaf53787...`, 8917 bytes
- `raw/gap3-transcript-extract.json`: sha256 `9bc6bf6a904b...`, 14206 bytes
- `raw/gap5-transcript-extract.json`: sha256 `7d36a67a2cd3...`, 29761 bytes
- `raw/gap6-transcript-extract.json`: sha256 `530f91e83ae6...`, 10877 bytes

Pins updated: receipts 1, 3, 5 and 6: each command whose `raw_output` points into an extract carries `raw_output_published: false`; a new `raw_evidence` entry records each extract's sha256, size and `published: false`; `limits` names the published support.
