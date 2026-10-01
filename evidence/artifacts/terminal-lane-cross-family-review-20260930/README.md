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
| `shell_loop_control.py`, `signal_order_probe.py` | Two measurements behind the signal handling of the pty probes (post-merge read, F1 and F4): whether a bash loop goes on after a child that exits 130 and stops after a child that ends BY SIGINT, and in which order CPython runs the handlers of signals that are pending together (ascending number). Each exits 0 when the measured behaviour is the one the documents state. |
| `tmux_identity_mutant.py` | Deletes the command-line clause of `server_identity` from a copy of a tmux probe and requires its `--selftest` to fail in the shutdown-failure control (F7). |
| `post-merge-read.json` | The sanitized record of the post-merge read: its 11 findings, how each was verified and what repaired it. |
| `tmux_sync_probe.py` | Whether tmux 3.4 writes DEC mode 2026 pairs to its outer terminal with and without `terminal-features xterm*:sync` (finding u484-B-1); its private server is verified gone before the socket directory is removed, and `--selftest` runs the same shutdown-failure controls as `tmux_bell_probe.py`. |
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
- **Verification before repair.** `shell_loop_control.py` (F1, with its control), a mutated copy of the probe that the sweep still passed (F2), the count of unswept lines (F3), `signal_order_probe.py` (F4) and `tmux_identity_mutant.py` (F7) reproduced five of the findings; the others were confirmed by reading and are covered by new cases and mutants. `recorded/` holds their outputs.
- **Release drift.** Claude Code 2.1.286 was installed and 2.1.283 pruned while the record pass was prepared: `recorded/` holds scans of 2.1.284, 2.1.285 and 2.1.286 (17 types each) and the reader mutants against them; `notification_types_scan_2.1.283.json` is retained from the earlier record pass (its binary no longer exists, so it is not among the commands of `exit_codes.txt`). The colour rerun (`recorded/color_capture.txt`) shows the earlier pattern with other exact counts.
- **Not repeated.** No reader saw the repairs of this round; they are checked by the recorded selftests, the 22 mutant runs and the native reruns.
