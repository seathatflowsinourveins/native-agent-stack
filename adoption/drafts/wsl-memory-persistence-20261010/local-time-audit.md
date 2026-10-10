# Scoped local-time audit (2026-10-10)

`local-time-audit.json` retains every classified candidate, search commands with home paths aliased to `~`, and ref SHAs. Expand `~` to the runtime user's home before reproducing the commands. The two repository scans use `origin/main`; local files are read-only point snapshots. `coordination/cc-tools` is absent; the scoped directory used is `coordination/command-center/cc-tools`. Direct calls are classified by Python AST and reviewed source context. This is a bounded literal/static audit, not a claim about all runtime-generated calls or aliases.

The semantics used in the classification follow Python's `datetime.now(tz=None)`, `datetime.fromtimestamp(timestamp, tz=None)` and `astimezone(tz=None)` documentation (https://docs.python.org/3.13/library/datetime.html), `time.localtime`/`time.strftime` (https://docs.python.org/3.13/library/time.html), GNU `date(1)` (`-u`, `TZ`, `%s`), and systemd 259.5 `systemd.time(7)` Calendar Events. A chained `now().astimezone().isoformat()` includes an offset and preserves its instant; its formatting still depends on the guest zone.

| Root | Revision or observed scope |
| --- | --- |
| nas | 15d82bcc8871206476dc8c4c7bf45d347e74b2b7 |
| uet | ff659ab6a8ded697c4aa1bb9af7e99315899c081 |
| cc-tools | ~/.local/state/native-agent-stack/coordination/command-center/cc-tools |
| local-bin | ~/.local/bin |
| user-units | ~/.config/systemd/user |

| Source file:line | Severity | Dependency / disposition |
| --- | --- | --- |
| nas:adoption/templates/systemd/codex-broker-reaper.timer:16 | machine-schedule | calendar uses guest local zone |
| nas:adoption/templates/systemd/stack-currency.timer:14 | machine-schedule | calendar uses guest local zone |
| nas:adoption/templates/systemd/token-report-refresh.service:142 | machine-control | date command without -u or explicit TZ |
| nas:adoption/templates/systemd/token-report-refresh.timer:20 | machine-schedule | calendar uses guest local zone |
| nas:blueprints/gap-wave2-20260923/foundation__scheduling-supervision/dagu_common.py:163 | machine-record | aware local offset conversion; instant is preserved, serialized zone/offset changes |
| nas:blueprints/gap-wave2-20260923/foundation__scheduling-supervision/incident_observe.sh:5 | machine-record | date command without -u or explicit TZ |
| nas:blueprints/gap-wave2-20260923/foundation__scheduling-supervision/incident_observe.sh:28 | machine-record | date command without -u or explicit TZ |
| nas:blueprints/gap-wave2-20260923/foundation__scheduling-supervision/probe_controls.py:53 | machine-record | aware local offset conversion; instant is preserved, serialized zone/offset changes |
| nas:blueprints/gap-wave2-20260923/foundation__scheduling-supervision/real_scheduled_recovery.py:65 | machine-record | aware local offset conversion; instant is preserved, serialized zone/offset changes |
| nas:blueprints/gap-wave2-20260923/foundation__scheduling-supervision/real_scheduled_recovery.py:65 | machine-record | naive local datetime.now() |
| nas:blueprints/memory-stack/longmemeval/embed_cache_proxy.py:32 | machine-record | implicit localtime in strftime |
| nas:blueprints/memory-stack/longmemeval/embed_cache_proxy.py:130 | machine-record | implicit localtime in strftime |
| nas:blueprints/memory-stack/longmemeval/mac-drivers/run_c3_resume.sh:8 | display-only | console progress timestamp; deployment on this WSL host not measured |
| nas:blueprints/memory-stack/longmemeval/mac-drivers/run_d3.sh:9 | display-only | console progress timestamp; deployment on this WSL host not measured |
| nas:blueprints/memory-stack/longmemeval/mac-drivers/run_d3.sh:21 | display-only | console progress timestamp; deployment on this WSL host not measured |
| nas:blueprints/memory-stack/longmemeval/mac-drivers/run_d3.sh:23 | display-only | console progress timestamp; deployment on this WSL host not measured |
| nas:blueprints/memory-stack/longmemeval/mac-drivers/run_queue.sh:12 | display-only | console progress timestamp; deployment on this WSL host not measured |
| nas:blueprints/memory-stack/longmemeval/v4/embed_server_st.py:400 | machine-record | implicit localtime in strftime |
| nas:blueprints/memory-stack/longmemeval/v4/gguf_embed_front.py:220 | machine-record | implicit localtime in strftime |
| nas:blueprints/memory-stack/longmemeval/v4/lme_harness.py:779 | machine-record | aware local offset conversion; instant is preserved, serialized zone/offset changes |
| nas:blueprints/memory-stack/longmemeval/v4/lme_harness.py:779 | machine-record | naive local datetime.now() |
| nas:blueprints/memory-stack/longmemeval/v4/run_velanext.sh:85 | machine-record | date command without -u or explicit TZ |
| nas:blueprints/memory-stack/longmemeval/v4/run_velanext.sh:174 | machine-record | date command without -u or explicit TZ |
| nas:blueprints/memory-stack/longmemeval/v4/run_velanext.sh:200 | machine-record | date command without -u or explicit TZ |
| nas:blueprints/memory-stack/longmemeval/v4/run_velanext.sh:237 | machine-record | date command without -u or explicit TZ |
| nas:blueprints/memory-stack/longmemeval/v4/run_velanext.sh:248 | machine-record | date command without -u or explicit TZ |
| nas:blueprints/memory-stack/longmemeval/v4/run_velanext.sh:250 | machine-record | date command without -u or explicit TZ |
| nas:blueprints/memory-stack/longmemeval/v4/run_velanext.sh:296 | machine-record | date command without -u or explicit TZ |
| nas:blueprints/memory-stack/longmemeval/v4/setup_velanext.sh:35 | display-only | console setup log timestamp |
| nas:blueprints/us-equities/adaptive-paper/native-faults/evidence/observe-native-faults-20260924.py:24 | machine-record | aware local offset conversion; instant is preserved, serialized zone/offset changes |
| nas:blueprints/us-equities/adaptive-paper/native-faults/evidence/observe-native-faults-20260924.py:24 | machine-record | naive local datetime.now() |
| nas:blueprints/us-equities/adaptive-paper/trials/ladder-1x-20260924a-needs-attention/observe_ladder_trial.py:63 | machine-record | aware local offset conversion; instant is preserved, serialized zone/offset changes |
| nas:blueprints/us-equities/adaptive-paper/trials/ladder-1x-20260924a-needs-attention/observe_ladder_trial.py:63 | machine-record | naive local datetime.now() |
| nas:blueprints/us-equities/order-throughput/evidence/observe-capacity-20260924.py:24 | machine-record | aware local offset conversion; instant is preserved, serialized zone/offset changes |
| nas:blueprints/us-equities/order-throughput/evidence/observe-capacity-20260924.py:24 | machine-record | naive local datetime.now() |
| nas:evidence/artifacts/sota-refresh-20260926/prometheus/gate_rehearsal.py:55 | machine-record | implicit localtime in strftime |
| nas:evidence/artifacts/sota-refresh-20260926/prometheus/switch_gated.py:285 | machine-record | local timezone conversion |
| nas:evidence/artifacts/sota-refresh-20260926/prometheus/switch.py:130 | machine-record | local timezone conversion |
| uet:.agents/skills/backtest-expert/scripts/evaluate_backtest.py:373 | display-only | Generated label in Markdown report; no zone in label |
| uet:.agents/skills/backtest-expert/scripts/evaluate_backtest.py:424 | machine-record | JSON/Markdown output filename stem uses local clock without offset |
| uet:.claude/skills/backtest-expert/scripts/evaluate_backtest.py:373 | display-only | Generated label in Markdown report; no zone in label |
| uet:.claude/skills/backtest-expert/scripts/evaluate_backtest.py:424 | machine-record | JSON/Markdown output filename stem uses local clock without offset |
| user-units:git-maintenance@daily.timer:9 | machine-schedule | calendar uses guest local zone |
| user-units:git-maintenance@hourly.timer:9 | machine-schedule | calendar uses guest local zone |
| user-units:git-maintenance@weekly.timer:9 | machine-schedule | calendar uses guest local zone |
| user-units:native-agent-pages-refresh.timer:5 | machine-schedule | explicit named-file read catches symlink omitted by rg default; implicit guest zone |
| user-units:restic-backup-nativestack2604.timer:5 | machine-schedule | calendar uses guest local zone |
| user-units:restic-prune-nativestack2604.timer:5 | machine-schedule | calendar uses guest local zone |
| user-units:wu-watch-20261006.timer:5 | machine-schedule | calendar uses guest local zone |

Each additional candidate is listed below so epoch-only calls, fixtures, and rejected literal matches do not disappear from the audit.

| Source file:line | Classification | Disposition |
| --- | --- | --- |
| cc-tools:tools-window/rehearsal-claude-20261006-rev3/relaunch-e2e-harness.sh:67 | zone-independent-epoch | generated date +%s command; %% escapes printf, epoch is zone-independent |
| cc-tools:tools-window/rehearsal-claude-20261006-rev3/relaunch-e2e-harness.sh:71 | zone-independent-epoch | generated date +%s command; %% escapes printf, epoch is zone-independent |
| cc-tools:tools-window/rehearsal-claude-20261006-rev3b/relaunch-e2e-harness.sh:73 | zone-independent-epoch | generated date +%s command; %% escapes printf, epoch is zone-independent |
| cc-tools:tools-window/rehearsal-claude-20261006-rev3b/relaunch-e2e-harness.sh:77 | zone-independent-epoch | generated date +%s command; %% escapes printf, epoch is zone-independent |
| cc-tools:tools-window/run-claude-20261006T2119Z/relaunch-cc.sh:3 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/run-claude-20261006T2119Z/relaunch-cc.sh:7 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/selftest-relaunch/e2e-20261006T203012Z/harness.sh:67 | zone-independent-epoch | generated date +%s command; %% escapes printf, epoch is zone-independent |
| cc-tools:tools-window/selftest-relaunch/e2e-20261006T203012Z/harness.sh:71 | zone-independent-epoch | generated date +%s command; %% escapes printf, epoch is zone-independent |
| cc-tools:tools-window/selftest-relaunch/e2e-20261006T203012Z/rerun-rev3b/harness.sh:73 | zone-independent-epoch | generated date +%s command; %% escapes printf, epoch is zone-independent |
| cc-tools:tools-window/selftest-relaunch/e2e-20261006T203012Z/rerun-rev3b/harness.sh:77 | zone-independent-epoch | generated date +%s command; %% escapes printf, epoch is zone-independent |
| cc-tools:tools-window/selftest-relaunch/e2e-20261006T203012Z/rerun-rev3b/run/relaunch-cc.sh:3 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/selftest-relaunch/e2e-20261006T203012Z/rerun-rev3b/run/relaunch-cc.sh:7 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/selftest-relaunch/e2e-20261006T203012Z/run/relaunch-cc.sh:3 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/selftest-relaunch/e2e-20261006T203012Z/run/relaunch-cc.sh:7 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/selftest-relaunch/slot-test.sh:8 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/selftest-relaunch/slot-test.sh:13 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/tools-window-claude.rev1.sh:196 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/tools-window-claude.rev1.sh:204 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/tools-window-claude.rev2.sh:252 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/tools-window-claude.rev2.sh:260 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/tools-window-claude.rev3.sh:210 | zone-independent-epoch | generated date +%s command; %% escapes printf, epoch is zone-independent |
| cc-tools:tools-window/tools-window-claude.rev3.sh:214 | zone-independent-epoch | generated date +%s command; %% escapes printf, epoch is zone-independent |
| cc-tools:tools-window/tools-window-claude.rev3.sh:288 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/tools-window-claude.rev3.sh:297 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/tools-window-claude.rev3b.sh:218 | zone-independent-epoch | generated date +%s command; %% escapes printf, epoch is zone-independent |
| cc-tools:tools-window/tools-window-claude.rev3b.sh:222 | zone-independent-epoch | generated date +%s command; %% escapes printf, epoch is zone-independent |
| cc-tools:tools-window/tools-window-claude.rev3b.sh:297 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/tools-window-claude.rev3b.sh:306 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/tools-window-claude.sh:83 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/tools-window-claude.sh:221 | zone-independent-epoch | generated date +%s command; %% escapes printf, epoch is zone-independent |
| cc-tools:tools-window/tools-window-claude.sh:225 | zone-independent-epoch | generated date +%s command; %% escapes printf, epoch is zone-independent |
| cc-tools:tools-window/tools-window-claude.sh:300 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/tools-window-claude.sh:309 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/tools-window-codex-r2.sh:114 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/tools-window-codex-r2.sh:122 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/tools-window-codex-r3resume.sh:119 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/tools-window-codex-r3resume.sh:127 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/tools-window-codex.sh:114 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/tools-window-codex.sh:122 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/tools-window.sh:155 | zone-independent-epoch | epoch-only; zone-independent output |
| cc-tools:tools-window/tools-window.sh:163 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/convergence-practice/local-inference-latest-20260926/window.sh:162 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/convergence-practice/local-inference-latest-20260926/window.sh:219 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/convergence-practice/local-inference-latest-20260926/window.sh:356 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/convergence-practice/local-inference-latest-20260926/window.sh:431 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/convergence-practice/local-inference-latest-20260926/window.sh:450 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/convergence-practice/local-inference-latest-20260926/window.sh:459 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/convergence-practice/local-inference-latest-20260926/window.sh:507 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-resolution-20260922/upstream-currency-sweep/currency_sweep.py:53 | explicit-UTC-naive | naive UTC (zone-independent, not local) |
| nas:blueprints/gap-wave2-20260923/foundation__observation-inference/private_user_manager.sh:104 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/foundation__observation-inference/private_user_manager.sh:105 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/foundation__observation-inference/private_user_manager.sh:106 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/foundation__observation-inference/private_user_manager.sh:114 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/foundation__observation-inference/private_user_manager.sh:115 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/foundation__quality-evaluation/run_codex_author.sh:15 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/foundation__quality-evaluation/run_g0_g4_g7.sh:17 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/foundation__quality-evaluation/run_review_call.sh:34 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/us-equities__agents-models-workers/aimem/r1b_default_embedding.sh:18 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/us-equities__agents-models-workers/aimem/r1b_default_embedding.sh:25 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/us-equities__agents-models-workers/aimem/r1b_default_embedding.sh:26 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/us-equities__agents-models-workers/lane/run_arm.sh:13 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/us-equities__evaluation-experiments/arb_rerun.sh:39 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/us-equities__evaluation-experiments/arb_rerun.sh:46 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/us-equities__observability-hosting/dagu_arm.sh:102 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/us-equities__observability-hosting/dagu_arm.sh:140 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/us-equities__observability-hosting/paper_arm.sh:157 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/us-equities__security-supply-chain/gitleaks_fix_round.sh:19 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/us-equities__security-supply-chain/gitleaks_fix_round.sh:24 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/us-equities__security-supply-chain/gitleaks_scans.sh:14 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/us-equities__security-supply-chain/gitleaks_scans.sh:20 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/us-equities__security-supply-chain/gitleaks_scans.sh:63 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/us-equities__security-supply-chain/gitleaks_scans.sh:70 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/us-equities__security-supply-chain/scanner_comparison.sh:18 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/gap-wave2-20260923/us-equities__security-supply-chain/syft_binary_coverage.sh:15 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/memory-stack/longmemeval/v4/run_velanext.sh:402 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/trials-20260926/colpali/local-integration/recorder-colpali_use_dryrun.sh:6 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/trials-20260926/colpali/local-integration/recorder-colpali_use_dryrun.sh:9 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:blueprints/trials-20260926/colpali/local-integration/recorder-colpali_use_dryrun.sh:13 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:evidence/artifacts/actionlint-successor-parity-20260927/parity_driver.sh:35 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:evidence/artifacts/actionlint-successor-parity-20260927/parity_driver.sh:39 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:evidence/artifacts/adoption-status-truth-20260926/host-scripts/host_scripts_fixture.sh:127 | not-a-time-call | literal tool-name list, not a date execution |
| nas:evidence/artifacts/adoption-status-truth-20260926/review-2/as-reviewed/host_scripts_fixture.sh:110 | not-a-time-call | literal tool-name list, not a date execution |
| nas:evidence/artifacts/betterleaks-parity-20260927/harness/final_checks.sh:17 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:evidence/artifacts/betterleaks-parity-20260927/harness/final_checks.sh:20 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:evidence/artifacts/betterleaks-parity-20260927/harness/run_bl_git2.sh:23 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:evidence/artifacts/betterleaks-parity-20260927/harness/run_repair_scans.sh:31 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:evidence/artifacts/betterleaks-parity-20260927/harness/run_scans.sh:36 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:evidence/artifacts/prompt-audit-20260927/x9-round2/run_arm.sh:14 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:evidence/artifacts/prompt-audit-20260927/x9-round2/run_arm.sh:18 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:evidence/artifacts/prompt-audit-20260927/x9-round3/probe_r3.sh:31 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:evidence/artifacts/prompt-audit-20260927/x9-round3/probe_r3.sh:37 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:evidence/artifacts/prompt-audit-20260927/x9-round3/run_arm_r3.sh:30 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:evidence/artifacts/prompt-audit-20260927/x9-round3/run_arm_r3.sh:36 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:evidence/artifacts/tool-invoke-rates-20260926/scratch-replay/replay-test.sh:50 | zone-independent-epoch | epoch-only; zone-independent output |
| nas:tests/test_osv_lockfile_coverage.py:303 | synthetic/test | local calendar date/time |
| nas:tests/test_osv_lockfile_coverage.py:321 | synthetic/test | local calendar date/time |
| nas:tests/test_osv_lockfile_coverage.py:472 | synthetic/test | local calendar date/time |
| nas:tests/test_osv_lockfile_coverage.py:473 | synthetic/test | local calendar date/time |
| nas:tests/test_osv_lockfile_coverage.py:592 | synthetic/test | local calendar date/time |
| nas:tests/test_osv_lockfile_coverage.py:660 | synthetic/test | local calendar date/time |
| nas:tests/test_osv_lockfile_coverage.py:736 | synthetic/test | local calendar date/time |
| nas:tests/test_osv_lockfile_coverage.py:1007 | synthetic/test | local calendar date/time |
| nas:tests/test_osv_lockfile_coverage.py:1016 | synthetic/test | local calendar date/time |
| nas:tests/test_workflow_hardening.py:796 | synthetic/test | local calendar date/time |

Explicit-zone display and record calls are also retained in JSON. In particular, `~/.local/bin/cc-clock-context:9` emits UTC and `:10` emits New York display time with an explicit `TZ`. These keep working under either guest-zone option; the owner's shell-wide `TZ` is unmeasured because startup files are outside the named roots.

Only the seven user-calendar drop-ins are proposed here. The repository template `token-report-refresh.service:142` uses a local weekday/hour in an `ExecCondition`; moving the guest zone would change this guard if installed without an explicit `TZ`. The three repository timer templates also inherit a local zone. Their deployed status is unmeasured, and peer-owned production files are left for their owners. The selected NY guest zone preserves these current dependencies while making the observed user calendars explicit.

No local-time dependency found here proves a time-sync defect. The host snapshot selects PHC0 and reports synchronized time. Logs without offsets and local filename stems are follow-up ownership findings, not edits made by this PR.
