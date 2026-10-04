# Cross-family review of the terminal lane, and its repairs (2026-09-30)

The record behind the "Update 2026-09-30: cross-family review" section of [the terminal decision](../../../docs/decisions/2026-09-28-terminal-experience.md) and its
[receipt](../../receipts/cross-family-review-terminal-lane-20260930.json). Four merged pull requests of the terminal lane (#484 tab titles and the alert probes, #498 the login-shell contract,
#510 the repository-carried defaults, #519 the model's own push notification) had passed Claude review rounds; the Codex cross-family round could not run on 2026-09-29 (every GPT-6 account was at
its weekly limit). On 2026-09-30 it ran through the packaged Codex lane on the local OmniRoute gateway, on `gpt-6.1-sol` at effort `max`, and every finding was then checked by an independent
Claude verifier or by the coordinator before anything was changed.

## How the run went

- **Lane.** The packaged landscape-sweep GPT-6 lane (`tools/sota-convergence/landscape-sweep`: `build_args.stage_lane_home`, `codex_call.sh`, `codex_job.py`), staged with `stage_review_lane.py`: a lane-local
  Codex home whose provider is the local OmniRoute gateway (`http://127.0.0.1:20128/v1`, model `cx/gpt-6.1-sol`, effort `max`, read-only sandbox, live web search, the token MCP servers of the stack-worker
  profile; the two project-note servers switched off so a reviewer reads only what its prompt names). Codex CLI 0.159.2. The gateway's compression stays at its recorded settings (the Codex route is
  unchanged: its headerless lane compressed 0 tokens on real Codex jobs). The lane's token practice is the prompt cache (95.0% of input tokens were cache reads) with RTK and context-mode in the lane home; the
  savings of the last two were not measured separately.
- **Units.** Nine jobs, each with the change's own evidence claims and a lens: behaviour and tests (A) or claims and evidence (B) for each of the four pull requests, #519 split in three. `build_review_prompts.py`
  writes the prompts (no model-family names in them) and the strict output schema.
- **Result.** Nine jobs, all exit 0, 46 findings (3 high, 34 medium, 9 low), 41 with a command the reviewer ran. 24.47M input tokens, 23.24M of them cached, 0.36M output; 71 minutes of wall clock; four
  points of the gateway pool's hundred used (cached aggregate figures, 7 before and 11 after; other sessions may have used points in between).
- **Verification.** `make_verify_briefs.py` wrote a brief per unit; a Claude Workflow ran one `stack-verifier` (Opus, effort max, read-only) per unit, three waves. 23 findings were graded by a verifier
  (17 confirmed, 4 partly, 2 refuted), 11 are duplicates of a graded or already repaired finding, and 12 were checked by the coordinator (8 against the code or the upstream source, 3 concerning a code path
  that no longer exists, 1 convention). 39 led to a repair, 2 were refuted, 3 were closed by removing the path, 2 duplicates of one convention (the host id in receipts) were kept. `findings.json` has the row of
  every finding; `verification.json` the verifiers' evidence; `results.json` the reviewer's.
- **Repairs.** Per finding in `findings.json`; the checks are in `recorded/`. Two of the 46 findings were refuted, and one refutation also showed that the coordinator's own earlier correction was wrong (the
  permission prompt's notification is timed by inactivity in a terminal; the fixed-delay timer is the Agent SDK path).

## Files

| File | What it is |
| --- | --- |
| `stage_review_lane.py` | Stages the packaged lane home for an ad-hoc review batch with the checkout's own `build_args.stage_lane_home`; switches the two project-note MCP servers off; writes `staged.json`. |
| `build_review_prompts.py` | The common preamble, one packet per unit (merged commit, changed files, the pull request's own evidence claims) and the lens tasks; the output schema. |
| `collect_reviews.py` | Reads every job through the runner's own `result` command and writes the consolidated private results. |
| `make_verify_briefs.py` | One brief per review unit for the verifiers (the reviewer's evidence, failure scenario and proposed fix, labelled as claims to test). |
| `build_findings_record.py` | Builds `results.json`, `verification.json` and `findings.json` from the private files and the disposition table; the sanitizer is `record_sanitizer.py`. |
| `sanitize_results.py` | The sanitizer on its own (replacement counts, never values). |
| `record_sanitizer.py` | The sanitizer rules that every record builder shares: this host's paths and user name, the review's private work directories and two private project labels are replaced, and `assert_clean` refuses a record that still holds one. The labels are read from a private file outside every checkout (the builders refuse to run without it), so no file of the repository names them. |
| `build_final_prompts.py`, `make_final_briefs.py`, `merge_partials.py` | The final round's prompts (three lenses, each run on two models), one brief per verifier unit from `final_units.json`, and the merge of the per-job outputs into one consolidated file. |
| `build_final_record.py`, `final_dispositions.json` | Builds `final-results.json`, `final-verification.json` and `final-findings.json`; the table holds, for each of the 37 findings, how it was checked, its disposition and where the repair is (written by the coordinator after reading the verifiers' evidence). |
| `check_receipt_hashes.py` | Compares the SHA-256 values a receipt's provenance lists with the files of a checkout and lists the scripts of this directory that the receipt does not list. |
| `shell_loop_control.py`, `signal_order_probe.py` | Two measurements behind the signal handling of the pty probes (post-merge read F1 and F4, post-merge GPT read U9 to U11): whether a bash or a dash loop goes on after a child that exits 130 or stops after one that ends BY SIGINT, with SIGINT sent to the whole process group (Ctrl-C) or to the child only, with a readiness handshake, asserted shell exit statuses, a private temporary directory and a rejecting control (a child that kills its parent shell with SIGTERM); and in which order CPython runs the handlers of signals that are pending together (ascending number: the check compares with the exact pair, and `--selftest` rejects a recorder that records nothing and one that records only the first handler). Each exits 0 when the measured behaviour is the one the documents state. |
| `tmux_identity_mutant.py` | Five mutated copies of a tmux probe (the comparison of the command line removed, the socket argument compared as a substring, the servers of a failing control not stopped, the socket directories of a failing control not removed, the removal not scoped to the probe's own directories), each of which must make the copy's `--selftest` fail in the named control while the unmutated selftest passes (F7, U1, U12 and the review bot's finding B3); a mutant that removes a cleanup leaves what the cleanup removes, so the script stops the servers on, and removes, the socket directories its mutants made. |
| `post-merge-read.json` | The sanitized record of the post-merge read of 2026-09-30: its 11 findings, how each was verified and what repaired it. |
| `build_post_gpt_prompts.py`, `make_post_units.py`, `build_postgpt_record.py`, `postgpt_dispositions.json`, `postgpt_units.json`, `postgpt_prompts_sha256.txt` | The post-merge GPT read of 2026-10-01: the prompts of its three lenses (derived from `build_final_prompts.py`), the grouping of its 38 findings into 16 distinct issues, the builder of the record and the disposition table (how each finding was checked and where its repair is). |
| `postgpt-results.json`, `postgpt-verification.json`, `postgpt-findings.json` | The sanitized record of that read: the six jobs and their findings, the coordinator's reproduction of each distinct issue (no verifier agent ran: the shared Claude meter read 89%), and a row for each of the 38 findings. |
| `verify_post_gpt_findings.py` | The reproductions of those findings, run on the code as merged in #563 (`recorded/post_gpt_verification.txt` holds their output before the repairs; check out `c99a482e` to re-run them). |
| `verify_codex_bot_findings.py`, `codex-bot-read.json`, `build_codex_bot_record.py`, `second-head-read.json` | The reproductions of the three findings that the Codex review bot left on the first push (`recorded/codex_bot_verification.txt` holds their output before the repairs and `recorded/codex_bot_verification_after.txt` after them; run it on a detached worktree of `66283fe8` to see the defects), and the sanitized record of the three threads, how each was reproduced and what repaired it (the builder reads a private raw file saved from GitHub's GraphQL API); `second-head-read.json` is the record of the independent Opus read of the repairs before the second head was pushed (nine findings). |
| `tmux_sync_probe.py` | Whether tmux 3.4 writes DEC mode 2026 pairs to its outer terminal with and without `terminal-features xterm*:sync` (finding u484-B-1); its private server is verified gone before the socket directory is removed, and `--selftest` runs the same shutdown-failure, cleanup and scope controls as `tmux_bell_probe.py`. |
| `results.json`, `verification.json`, `findings.json` | The sanitized record of the first review. |
| `recheck-*.json`, `recheck_prompts_sha256.txt` | The same for the re-check. |
| `final-*.json`, `final_prompts_sha256.txt`, `final_units.json` | The same for the final read. |
| `recorded/` | The returned output of every check run on the repaired files: scans of the three installed releases, the reader, replacement-tool and probe controls, mutants and selftests, the unit tests, the practice repository's checks. |

The repaired scripts themselves are in the three earlier artifact directories (`terminal-experience-20260928`, `login-shell-contract-20260929`, `wsl-terminal-defaults-20260929`,
`notification-types-20260929`); each row of their READMEs says what the script now does.

Not retained: the private work directory (the reviewers' event streams, the prompts with this host's checkout path, the verifiers' transcripts). The prompts' SHA-256 values are in the receipt.

## Re-check of the repairs (2026-09-30)

- **Jobs.** Three read-only jobs of the same lane and model (`R1` the tool and the probes, `R2` the scan, tests and scripts, `R3` the claims and the evidence; `build_recheck_prompts.py` wrote the prompts from the pull
  request's head, its body's evidence claims and the round-1 record) and one job of `cx/gpt-6-astra-ultra` (`U1`, an adversarial second opinion, highest-risk items first). The prompts' SHA-256 values are in
  `recheck_prompts_sha256.txt`.
- **Result.** 33 findings (1 high, 24 medium, 8 low): 12 duplicates of another finding, 2 coordinator checks and 19 findings graded by three Claude verifier waves (`stack-verifier`, Opus, effort max, read-only): 16 confirmed,
  3 partly, none refuted. `build_recheck_record.py` writes `recheck-results.json`, `recheck-verification.json` and `recheck-findings.json` (sanitized, with the rules of `record_sanitizer.py`).
  Every finding was repaired in round 5; the first-round repairs proved incomplete in several places (see the decision record's re-check subsection).
## Final read of the re-check's repairs (2026-09-30)

- **Jobs.** Six read-only jobs of the same lane: three lenses (`F1` the tool and the probes, `F2` the scan, tests and scripts, `F3` the claims and the evidence; `build_final_prompts.py` wrote the prompts from the merged
  main and the earlier records), each on `cx/gpt-6.1-sol` and on `cx/gpt-6-astra-ultra`, effort `max`, Codex 0.159.2, all exit 0. The prompts' SHA-256 values are in `final_prompts_sha256.txt`.
- **Result.** 37 findings (1 high, 30 medium, 6 low; each with a command the reviewer ran): 16 duplicates of another finding and 21 graded by four Claude verifier units (`make_final_briefs.py`, `final_units.json`;
  `stack-verifier`, Opus, effort max, read-only): 17 confirmed, 4 partly, none refuted. 26.26M input tokens (95.7% cache reads), 0.33M output, 50 minutes; the pool 36 to 52 points (other sessions may have used points in
  between). `merge_partials.py` merged the per-job outputs; `build_final_record.py` writes `final-results.json`, `final-verification.json` and `final-findings.json`. All 37 findings were repaired in one round. One reviewer sentence in `final-results.json` has its punctuation changed (`..., definitions_identical=True.` became `... (definitions_identical=True).`) because the repository's secret gate (gitleaks `generic-api-key`) read it as a key; `build_final_record.py` applies that one exact pattern and asserts it applies once, so any other secret-shaped text still reaches the gate.
- **Not repeated here.** The repairs of this round are checked by the recorded controls, mutants, a signal sweep and native reruns (`recorded/`); see the decision record for what a reviewer did not read.

## Post-merge read (2026-09-30)

- **Reader.** One read-only `evidence-reviewer` agent (Claude Opus, effort max, no shell) read the merged signal handling and shutdown code on `origin/main` 29458b43 (the two pty probes, the two tmux probes, `pty_probe_mutants.py` and the documents that describe them). No GPT read: the gateway pool's only usable account read 83 of 100 points. It returned 11 findings (3 medium, 8 low, none high); `post-merge-read.json` has the row of each, how it was verified and what repaired it.
- **Verification before repair.** Five of the findings were reproduced: `shell_loop_control.py` (F1, with its control), `signal_order_probe.py` (F4) and `tmux_identity_mutant.py` (F7) have recorded outputs in `recorded/`; the mutated copy that the sweep still passed (F2) and the count of unswept lines (F3) were measured ad hoc and their outputs were NOT retained (the repairs record them differently: the sweep's detail in the recorded selftests states the lines swept of the lines with code, and the runner's spawn mutant must fail through the client-start observation); the others were confirmed by reading and are covered by new cases and mutants.
- **Release drift.** Claude Code 2.1.286 was installed and 2.1.283 pruned while the record pass was prepared: `recorded/` holds scans of 2.1.284, 2.1.285 and 2.1.286 (17 types each) and the reader mutants against them; `notification_types_scan_2.1.283.json` is retained from the earlier record pass (its binary no longer exists, so it is not among the commands of `exit_codes.txt`). The colour rerun (`recorded/color_capture.txt`) shows the earlier pattern with other exact counts.
- **Not repeated.** No reader saw the repairs of this round when it was written; they were checked by the recorded selftests, the 22 mutant runs and the native reruns, and the post-merge GPT read below read them.

## Post-merge GPT read (2026-10-01)

- **Jobs.** Six read-only jobs of the packaged Codex lane on `origin/main` through the local OmniRoute gateway: three lenses (`P1` the two pty probes and the mutant runner, `P2` the tmux probes, the new scripts and the recorded outputs, `P3` claims, evidence
  and hygiene; `build_post_gpt_prompts.py` wrote the prompts from the merged #563, its patch and its pull request's evidence claims), each on `cx/gpt-6.1-sol` and on `cx/gpt-6-astra-ultra`, effort `max`, Codex 0.159.3, all exit 0. The user had asked to keep
  going with the highest-quality GPT lane, and the pool's one usable account had reset (30 of 100 points used at the start, 67 after; other sessions may have used points in between). The prompts' SHA-256 values are in `postgpt_prompts_sha256.txt`.
- **Result.** 38 findings (5 high, 31 medium, 2 low; each with a command the reviewer ran): 16 distinct issues and 22 duplicates (`make_post_units.py`), 27.69M input tokens (96.1% cache reads), 0.36M output, 47 minutes of wall clock. No verifier agent was
  started (the shared Claude five-hour meter read 89% when the findings arrived): the coordinator reproduced each distinct issue with `verify_post_gpt_findings.py` (13 by execution, 3 by reading) and confirmed all 16; its severities are lower than the
  reviewers' for the tmux identity and the temporary path. All 38 were repaired in one round. `build_postgpt_record.py` writes `postgpt-results.json`, `postgpt-verification.json` and `postgpt-findings.json`.
- **Not repeated here.** The repairs of this round were checked by the new cases, the mutant runs and the native reruns (`recorded/`), not by a reviewer when this section was written; the Codex review bot then read them (next section).

## Codex review bot's read of the first push (2026-10-01)

- **Reader.** GitHub's Codex review bot (`chatgpt-codex-connector`) read the first push of this pull request (`5c484647`) at 07:27Z and left three P2 threads on the repairs of the GPT read. The repository's ruleset refuses a merge while a review thread is unresolved, so each was a merge gate.
- **Verification before repair.** The coordinator reproduced each on a detached worktree of the pushed head (`66283fe8`) with `verify_codex_bot_findings.py`: a SIGTERM that lands right after the snapshot of the latch exits 0 and the signal is lost (both pty probes); a probe whose stdout is a full pipe that nobody reads is still
  running after 6 s with a SIGTERM latched; each tmux selftest leaves two socket directories. The output is `recorded/codex_bot_verification.txt`; `codex-bot-read.json` holds the threads (author, commit, path, line, text), the reproductions and the repairs.
- **Repairs.** The handoff ends the latch's life (block, read, die BY the first signal or give the handlers back to the default action), nothing is written while the latch is installed (`say` and `emit_report`), the controls remove and count their socket directories and have a scope control, and the sweep covers the handoff
  and requires death BY SIGTERM. After them the same script gives -15 four times and no directory left (`recorded/codex_bot_verification_after.txt`); the new cases and five new mutants per pty probe, and two more identity mutants per tmux probe, fail without each repair.
- **Independent read before the push.** One read-only Claude Opus reader read the repairs of the three findings before the second head was pushed and returned nine findings (`second-head-read.json`): the sweep's driver repeated the handoff call that hid its window, two expected sets of new mutants were wrong, the flush case failed under PYTHONUNBUFFERED=1, and more; the coordinator confirmed O1 to O4 and O8 by execution and the rest by reading, and repaired all nine.
- **Not repeated here.** The repairs of the bot's findings and of the reader's findings are checked by the new cases, 50 mutant runs and the native reruns (`recorded/`), not by a second reviewer; no further read is commissioned inside this change.
