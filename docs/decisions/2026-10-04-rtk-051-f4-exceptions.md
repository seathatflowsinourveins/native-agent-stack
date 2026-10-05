# 2026-10-04: Reconcile Codex F4 exceptions with RTK 0.51.0

Lane: foundation. Base: `3b8f9c8a`. This bounded instruction correction serves
exact source and history reads by Codex workers building the north-star R&D
systems. No stack pin, host configuration, commit or push changes here.

The installed client is `rtk 0.51.0`, exit 0, at the selected
[rtk-ai/rtk v0.51.0](https://github.com/rtk-ai/rtk/releases/tag/v0.51.0)
revision `e001f773f80b22b7dc4c7a79521b30e35aaef026`
([Cargo.toml:3](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/Cargo.toml#L3)). Installed help, the release and tag APIs, and the
pinned source archive were checked in the preceding builder turn. The scoped
ai-memory query was unavailable under this session's approval policy; current
CLI output and original pinned source supply the evidence.

## Evidence and correction

Our [unchanged-probe rerun](../../evidence/artifacts/rtk-f4-remeasurement-20261004/rtk-behaviour-probe.json) and
[scratch hook and explicit-prefix remeasurement](../../evidence/artifacts/rtk-f4-remeasurement-20261004/hook-and-prefix-probe.json)
are recorded next to [PR #701 README](https://github.com/seathatflowsinourveins/native-agent-stack/blob/e3ed1fe36703c6f08044b5d81fdd8d1b5f93e9d6/evidence/artifacts/token-stack-fresh-session-e2e-20261004/README.md#L67), [peer probe](https://github.com/seathatflowsinourveins/native-agent-stack/blob/e3ed1fe36703c6f08044b5d81fdd8d1b5f93e9d6/evidence/artifacts/token-stack-fresh-session-e2e-20261004/rtk_behaviour_probe.py), [peer JSON](https://github.com/seathatflowsinourveins/native-agent-stack/blob/e3ed1fe36703c6f08044b5d81fdd8d1b5f93e9d6/evidence/artifacts/token-stack-fresh-session-e2e-20261004/rtk-behaviour-probe.json), [exclusions fixture](https://github.com/seathatflowsinourveins/native-agent-stack/blob/e3ed1fe36703c6f08044b5d81fdd8d1b5f93e9d6/fixtures/rtk-hook-exclusions.toml).
Those peer paths land on main with #701; the links pin its measured head
`e3ed1fe36703c6f08044b5d81fdd8d1b5f93e9d6`.

The peer's `rtk_behaviour_probe.py` ran unchanged with an explicit output file
under `.tmp-build`, exit 0. It constructed two scratch HOMEs and XDG trees,
one with upstream defaults and one with the fixture's five exclusions, and a
16-commit repository with one merge. Its returned JSON is byte-identical to
the peer JSON. All 11 native/RTK execution comparisons have equal exit codes.
The supplemental native commands reuse that probe's fixture/environment helpers;
their runner exited 0 and retained 58 command results. Temporary paths are
replaced with `<scratch>`; large synthetic outputs have observed counts and
sanitized hashes in the public record, with exact returned output in
`.tmp-build/rtk-f4-scratch-supplement.json`. These are local integration and
synthetic fixture observations, with no model run, token-savings claim or
unchanged upstream RTK test acceptance.

The preceding draft observed the host's exclusions and could be read as saying
RTK leaves the four commands alone by default. The two scratch configurations
correct that inference: defaults rewrite them; the installed exclusions leave
them alone. Both `rtk rewrite` and the invoked Codex hook use those parameters
([src/core/config.rs:263](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/core/config.rs#L263), [src/hooks/decision.rs:143](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/hooks/decision.rs#L143),
[src/hooks/hook_cmd.rs:911](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/hooks/hook_cmd.rs#L911)). No live Codex trust interaction ran in
this unit; #701 records that separate client qualification.

`git diff --exit-code` is still rewritten in both configurations. The fixture
excludes standalone `diff`; its literal pattern anchors at the command's start
([src/discover/registry.rs:1553](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/discover/registry.rs#L1553)). The F4 bullet therefore names
`diff`. Calling the configuration "bootstrap-installed" uses the requested
role label and conditions the instruction on its presence. At this base,
`adoption/bootstrap-linux.sh:1065` and `adoption/bootstrap-macos.sh:1232` print
reminders and explicitly say they do not write it; the Linux script at #701's
head does the same. This unit does not assert an automatic installer write.

## Decision and source for every instruction

Use five exceptions. Put the four configured exclusions first, then the log
guidance. Explicit prefixes bypass those exclusions; complete history or
merges require an explicit count or native git. Retire the find bullet and
both role sentences' find clauses. Keep all ten carriers verbatim, their two
checksum files and independent test/README rows synchronized. The historical
upstream awareness text and its v0.50.0 marker stay byte-identical to v0.51.0's
[hooks/rtk-awareness-full.md:1](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/hooks/rtk-awareness-full.md#L1) (SHA-256
`278274ef3d08c858d4247cc91419c4d74ef922b95719e987b22e896aef10e1fc`).

| Instruction | RTK v0.51.0 source | Own remeasurement, alongside the peer evidence above |
| --- | --- | --- |
| Exclusions require the installed config; an explicit prefix bypasses them | [src/discover/registry.rs:1553](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/discover/registry.rs#L1553), [src/discover/registry.rs:1704](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/discover/registry.rs#L1704), [src/hooks/decision.rs:143](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/hooks/decision.rs#L143) | Default rewrite calls for blob show, standalone diff, jq and branch return 3 and a replacement; configured calls return 1 and no replacement. All hook payloads exit 0: replacements under defaults, none for the four exclusions. Echo and the bash wrapper remain untouched in both arms. Explicit blob prefixes still truncate in both arms. |
| Blob show keeps about 8 KiB, including the git -C form | [src/cmds/git/git_cmd.rs:989](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/cmds/git/git_cmd.rs#L989), [src/cmds/git/git_cmd.rs:1047](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/cmds/git/git_cmd.rs#L1047) | Native text blob: 48,000 bytes, 500 lines. Both explicit RTK forms, in both configurations: 8,160 content bytes, 85 lines plus recovery hint; every exit 0. |
| Diff read errors exit 2 at 0.51.0 | [src/cmds/git/diff_cmd.rs:38](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/cmds/git/diff_cmd.rs#L38), [src/cmds/git/diff_cmd.rs:64](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/cmds/git/diff_cmd.rs#L64); [bf23cff](https://github.com/rtk-ai/rtk/commit/bf23cff467aa3b4aa314d6a4b956630f1e275a5f) | Native and RTK missing-file calls return 2 in both configurations; diagnostics differ. The retained 0.50.0 note is historical, not a new old-version execution. |
| Branch output can misclassify a branch in another worktree | [src/cmds/git/git_cmd.rs:3194](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/cmds/git/git_cmd.rs#L3194), [src/cmds/git/git_cmd.rs:3227](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/cmds/git/git_cmd.rs#L3227) | With the same-name remote ref and 50 other remote refs, native shows + aa-sibling; both explicit RTK arms also put aa-sibling under remote-only (51). Every exit 0. |
| Jq keeps 40 lines of width 120 when lossy recovery is available | [src/filters/jq.toml:8](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/filters/jq.toml#L8), [src/filters/jq.toml:9](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/filters/jq.toml#L9), [src/main.rs:1656](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/main.rs#L1656) | Native: 100 content lines of width 182. Explicit RTK with scratch recovery enabled: 40 lines of width 120 in both arms. Every exit 0. The source falls back to raw output if recovery is unavailable. |
| Bare log caps at 10 silently; stat caps at 10 with a notice; count requests retain merges | [src/cmds/git/git_cmd.rs:1550](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/cmds/git/git_cmd.rs#L1550), [src/cmds/git/git_cmd.rs:1784](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/cmds/git/git_cmd.rs#L1784), [src/cmds/git/git_cmd.rs:1816](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/cmds/git/git_cmd.rs#L1816), [src/cmds/git/git_cmd.rs:1842](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/cmds/git/git_cmd.rs#L1842) | See the 16-commit table below; all native and RTK calls exit 0. The guidance makes no claim that a 16-commit fixture proves unlimited history. |
| Retire the missing-path find exception | [src/cmds/system/find_cmd.rs:147](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/cmds/system/find_cmd.rs#L147), [src/cmds/system/find_cmd.rs:417](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/cmds/system/find_cmd.rs#L417) | The peer's absolute missing path and four additional explicit path forms return 1 natively and with RTK. Under LC_ALL=C the four diagnostics match. A bare missing name still selects legacy pattern syntax and returns 0; that grammar distinction is recorded, not promoted into universal native-find equivalence. |
| Keep shell builtins in their calling shell | [src/main.rs:1701](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/main.rs#L1701), [src/main.rs:1722](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/main.rs#L1722) | Explicit rtk cd, export and source each return 127. A failed command halts a shell && chain. |
| Preserve the positional-expansion guidance | [src/core/shell.rs:182](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/core/shell.rs#L182) | Installed rtk test --help exits 0 and lists --shell; pinned source selects direct argv unless shell mode is requested. |

## Log observations on the peer's fixture

Our unchanged rerun, cited beside the #701 README, probe, JSON and exclusions
fixture above, has 16 commits including one merge. The native forms return all
16. Every compared command in this table exits 0.

| Explicit RTK form | Commits | Merge retained | Stderr |
| --- | ---: | --- | --- |
| git log | 10 one-line summaries | no | empty |
| git log --stat | 10 | yes | [rtk] capped at 10 commits; pass -n <count> for more |
| git log --oneline | 15 | no | empty |
| git log --format=%s | 15 | no | empty |
| git log --graph --oneline | 15 | no | empty |
| git log -n 16 | 16 | yes | empty |
| git log --stat -n 16 | 16 | yes | empty |

## Pins, budget and completion

All active RTK pins are 0.51.0: `manifests/stack.json` (components/27),
`adoption/pins-linux-x86_64.json` (tools/6), and
`adoption/pins-macos-arm64.json` (tools/12). The prior scan of all 42 tracked
JSON filenames containing pin found no other RTK installation pin. Historical
receipts stay at their recorded versions; macOS execution was not run here.

The template is 8,190 UTF-8 bytes against 8,192.
`tests/test_codex_worker_lane.py:438` enforces the stricter local <8192 bound.
The current carrier hashes are f531430b620c852228365ddfc43deec11a5d942ea3c988487ca44464954c6a82
(researcher) and 55d021a13430980c0acbea1fdecfa87c62f874947de1f3ab6525602692c9f7dc
(verifier). WSL --write-blocks exits 0; RTK is unwired in this distribution's
map, so the generated Codex file finishes byte-identical to main. The current
record projection is regenerated with --check --markdown, exit 0.

The earlier focused run exited 1 with three stale-anchor/projection failures;
the repaired run exited 0 (382 tests, 12 skips). The coordinator subsequently
narrowed acceptance to the requested focused suite, validate.py, evidence
manifest check, diff check and byte count; CI owns the full suite. Interrupted
full-suite logs are retained privately and are not claimed as acceptance.
Final targeted command exit codes belong to the builder's JSON handoff.

Register changed covered files and the new compact evidence records last with
scripts/host_receipts.py::register_file. Never hand-merge manifests/evidence.json;
the coordinator owns the final hot-file commit and rebase. No commit or push is
made by this builder.

## Alternatives, overturn condition and completeness critique

Keeping the unconditional hook wording confuses a host configuration with
upstream defaults. Keeping six exceptions retains stale explicit-path find
guidance. A template-only edit breaks verbatim carriers, role sentences and
hashes. Adopt the conditional five-exception block and explicit log count advice.

Reopen when a stack RTK pin, fixture, hook dispatch or named command's measured
behavior changes. Compare native and RTK output on the same fixture under both
configurations, with a positive hook control. The completeness critique found
that a 16-commit fixture cannot prove unlimited formatted history, standalone
diff must be distinguished from git diff, bare-name find has legacy grammar,
and small branch or unavailable-recovery fixtures can hide lossy behavior.
The next RTK sweep should cover those conditions. Native macOS and a live Codex
trust interaction remain separate qualifications.
