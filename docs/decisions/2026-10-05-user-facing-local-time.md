# Decision: times shown to the user are local first, with UTC beside them; records stay UTC (2026-10-05)

**Decided by:** the user's request of 2026-10-05, described here rather than quoted. Times that agents show the user
should be in the user's local time, settled at the root of the harness, not by a memory note or by per-host edits. The
coordinator relayed it in a bounded unit brief with the measured facts below; this unit wrote the change in an owned
worktree.

**North-star action served:** the foundation's work and the US-equities lane report status, schedules, CI runs and
paper-session times to the user. They should read in the user's own zone, while ledgers, receipts and evidence keep one
UTC timeline across hosts and clients.

## Context

- The coordination convention writes UTC `Z` times: ledger rows, receipts, and `date -u` in the standing-delegation
  checks. Those are records and stay UTC.
- The coordinator measured on 2026-10-05:
  - Windows is on "Eastern Standard Time";
  - all three WSL distributions resolve `/etc/localtime` to `America/New_York`.
- Agents relayed record times to the user as they were written, in UTC. No managed instruction told them to convert.
- On NativeStack2604, each client's user-level file holds an interim local-time line dated 2026-10-05, after the
  managed block's end marker (read 2026-10-05). This change leaves host files alone.
- NativeStack2604's `/etc/wsl.conf` held `[time] useWindowsTimezone=false` with no repository record, and the coordinator
  set it to `true` on that host. The distribution recipe wrote no `[time]` key, so a new host relied on the default and
  nothing read the value back.

## Decision

1. **One instruction sentence at user level, in both clients, with one wording:**

   > When you tell the user a time, give it first in the host's local time zone (read it with `timedatectl` or
   > `date`), with UTC beside it, for example "4:00 PM EDT (20:00Z)"; keep UTC in ledger rows, receipts, evidence and
   > commits.

   - **Claude.** [`examples/claude-native/CLAUDE.md`](../../examples/claude-native/CLAUDE.md) carries it as a Core rule
     bullet after the concise-handoff bullet, the existing rule about reporting to the user.
   - **Codex.** [`adoption/templates/codex.AGENTS.template.md`](../../adoption/templates/codex.AGENTS.template.md) carries
     it as the last line of the `session-lanes` block. That keeps it outside the top-rule block, which
     `adoption/scaffold/AGENTS.md` copies byte for byte into new repositories.
   - **Rendering.** F9 renders both templates into every host's managed block. The regenerated carriers
     `adoption/new-wsl/claude-user-instructions.md` and `codex-user-instructions.md` hold the sentence once each.
   - **A user-level rule, not a standing clause.** The repository `AGENTS.md` and the scaffold do not repeat it. The
     [three-surface record](2026-09-30-rule-text-every-layer.md) requires all three surfaces only for the standing
     clauses that `StandingRuleSurfacesTests.SHARED` lists; its one-wording rule still holds here, on both client
     templates and both carriers, and a new test in that class checks it. This sentence is a personal display
     preference:
     - Claude's memory documentation lists `~/.claude/CLAUDE.md` as "Personal preferences for all projects".
     - The Codex guide puts persistent defaults in the Codex home "so every repository inherits your working
       agreements".
     - Both clients load their user-level file in every project, this repository included, so a root copy would load
       twice here and count twice against each fixed startup ceiling.
2. **The WSL zone follows Windows, explicitly.**
   - **Path A.** The cloud-init user-data appends `[time]` with `useWindowsTimezone=true` to `/etc/wsl.conf`, before
     `[user]`.
   - **Path B.** W6 appends the same key.
   - **Read-back.** W5 reads the key back, and the first-boot checklist and the recipe record's command table follow.
   - **The source.** Microsoft documents the key as a boolean that defaults to `true`: "Setting this key will make WSL use
     and sync to the timezone set in Windows."
   - **Why write it.** Writing the key leaves the default's behavior unchanged. It makes the value part of the recipe and
     its proof, so a later `false` shows up as a failed W5 check instead of the silent drift found on NativeStack2604.
   - **First run.** The 26.04.1 image's `wsl-setup` 0.6.3 only appends or completes `[user]`, so the section survives its
     first run.
   - **Claude Code's UI clock.** Claude Code's own UI times follow the system zone by default (below), so this key also
     makes them local.
3. **Records stay UTC.** Ledger rows, receipts, evidence, commits and dated records keep UTC, written as RFC 3339
   date-times with `Z` or a numeric offset.

## Alternatives considered

- **A memory note.** The user rejected it. Memory is retrieved per project as evidence, not loaded as a standing
  instruction, so it would not reach every session or client.
- **Per-host private lines in each client's user-level file.** Kept as the interim only:
  - they cannot be reproduced on a new host and can drift from the managed source;
  - after the hosts re-render with this rule, they duplicate it.
- **The system zone alone** (`useWindowsTimezone=true`, `/etc/localtime`). It is needed so that `date`, `timedatectl`
  and the client UI clocks report the user's zone. It cannot change how an agent words a time: an agent relaying a UTC
  ledger row still writes UTC. It is the second half of this decision, not a substitute for the first.
- **Records in local time.** Rejected:
  - an Eastern local time repeats an hour when daylight saving ends;
  - zones differ between hosts and contributors, while ledgers merge rows from several distributions and Codex lanes;
  - RFC 3339 §4.1 gives the reason for UTC. §4.2 defines numeric offsets as local time minus UTC and notes that
    alphabetic zone labels have interoperated poorly, so a label such as `EDT` is for people and always has the UTC
    time beside it. §4.3 reads `Z` as UTC being the preferred reference point, and §5.6 gives the grammar
    `time-offset = "Z" / time-numoffset`.
- **Native client settings instead of a sentence.**
  - **Claude Code.** Claude Code 2.1.257 added `timeFormat` and `timeZone` (changelog at v2.1.289). The installed 2.1.289
    describes them as settings "for times shown in the UI", with defaults `auto` and the "system time zone". They do not
    reach text the model writes, so the defaults stay. No template sets them, because a fixed IANA zone in a portable
    template would be wrong for other users.
  - **Model-written times.** No setting that localizes times the model writes was found in `claude --help` (2.1.289), the
    changelog through v2.1.289, `codex --help` (0.160.0), the rust-v0.160.0 release notes or the Codex configuration
    reference. That reference has `timezone` only in the `location` of `tools.web_search`.
  - **A pointer or a skill.** Either would need a startup trigger identical to the rule itself, since any reply may hold
    a time.
- **The repository `AGENTS.md` and the scaffold as further surfaces.** Not chosen, for the reasons in Decision 1. The
  overturn condition below says when to add them.

## Startup bytes (the dated comparison the budget record requires)

These are measured with `PortableTopRuleTests.startup_files`, which uses the renderer's committed carriers. Base is main
`e8c1edec`.

| File or scope | Before | After |
| --- | ---: | ---: |
| `examples/claude-native/CLAUDE.md` and its carrier | 11,575 | 11,805 (+230) |
| Claude rendered user block | 11,841 | 12,071 |
| `adoption/templates/codex.AGENTS.template.md` (local check: under 8,192) | 7,307 | 7,535 (+228) |
| Codex rendered carrier | 8,373 | 8,601 |
| Claude startup scope (fixed ceiling 24,458) | 23,566 | 23,796; headroom 662 |
| Codex startup scope (fixed ceiling 20,103) | 19,332 | 19,560; headroom 543 |
| Claude post-gate projection (scope − 680; ceiling = ×1.05, rounded up) | 22,886; 24,031 | 23,116; 24,272 |
| Codex post-gate projection | 18,652; 19,585 | 18,880; 19,824 |

The constants stay at 24,458 and 20,103; nothing is re-baselined. When the routing host gate passes, the
[budget record](2026-10-05-harness-context-budget.md) still requires lowering both constants to the measured post-gate
scopes plus 5%. For these inputs that is 24,272 and 19,824, replacing its earlier projection of 24,031 and 19,585. The
sentence is 227 bytes. The budget record has a dated addendum pointing here.

## Pins amended in the same change

- **The local-time wording.** `StandingRuleSurfacesTests` gains a check that the sentence appears once in both
  templates and both F9 carriers. It failed first, as the Checks table shows.
- **`TOP_RULE_SHA256`** in `tests/test_codex_worker_lane.py` covers the Codex block up to the RTK marker, the
  `session-lanes` lines included. It was re-derived with the module's `template_segments()` as
  `82e23b68466ed8b96566a229582f0c99fa1456a393e635f18cc5e65f601f4d09`, and the budget record's addendum names the new
  value beside the old one. The size comments there and in `tools/adoption/new_wsl_client_config.py` now give 7,535
  and 8,601 bytes.
- **The cloud-init check.** `tests/test_wsl_new_distro_recipe.py` requires `[time]` and `useWindowsTimezone=true` in
  the render. It has two new mutants that the check rejects, a lost section and `false`.
- **The new W6 command.** It has its row in the recipe record's command table and its entry in the receipt example.
- **The client-configuration record.** It takes the tool's regenerated listing (59 and 70 lines) in a dated addendum.
- **The new-WSL handbook.** It is regenerated; it holds the recipe's SHA-256. Its receipt's `outputs` follow, with a
  `regenerations` entry.
- **The registry.** `manifests/evidence.json` takes the new hashes of the 20 changed files it lists and the five new
  files under `evidence/artifacts/user-facing-local-time-20261005/`.
- **The passwordless-sudo criterion moved from recipe line 624 to 627.** The two live citations of it,
  `tools/adoption/host_baseline_probe.py` and `tools/adoption/host-baseline.md`, follow. Dated records keep their own
  line citations.
- **Unchanged.** The startup constants (`STARTUP_BUDGET_BYTES`), the scaffold, the moves fixture of the Codex top-rule
  section and the RTK block do not change.

## Overturn condition

- **A native setting.** A client release adds a setting that localizes times the model writes. Adopt it and drop the
  sentence.
- **Sessions without the managed user block.** Cloud sessions, CI agents or a host not yet re-rendered are shown
  reporting times to the user in UTC only. Then add the sentence to the repository `AGENTS.md` and the scaffold, under
  the three-surface test, with a dated byte comparison.
- **The user changes the format,** for example to local time only or a 24-hour clock.
- **A host's zone is not the user's,** for example a remote or cloud host on UTC. Reword "the host's local time zone"
  to name the user's zone.
- **Microsoft changes `useWindowsTimezone`'s meaning or default.**
- **A missed rule at its trigger.** After the hosts re-render, an agent shows the user a UTC-only time. Sharpen the
  sentence, as the budget record's reopening rule says.

## Evidence classes and limits

- **Evidence classes.** This is source review and local integration: unit tests, the F9 check and render, cloud-init's
  own `schema -c` on the rendered user-data, and two synthetic `/etc/wsl.conf` simulations in a scratch directory. No
  first boot, import, host re-render or model run happened. No model run measured whether agents follow the sentence.
- **Host work.** The NativeStack2604 change to `useWindowsTimezone=true` was the coordinator's host action and is not
  part of this commit. The host re-render that delivers the sentence comes after landing. A re-render replaces only
  the text between the managed markers, so it keeps the interim lines; removing them changes the user's own
  user-level files and is left to the user.
- **The experiment's frozen inputs.** The WSL image experiment
  (`blueprints/convergence-practice/wsl-new-distro-image-20261001/experiment.json`) froze four files that this change
  edits. Their recorded bytes moved to `evidence/artifacts/user-facing-local-time-20261005/frozen-inputs/` with
  unchanged hashes, following the 2026-10-04 fix-wave precedent.
- **No decision index.** The repository keeps no index of decision records: `ls docs/decisions | grep -v '^20'`
  prints nothing. `catalogs/foundation/decisions.json` lists component selections per capability, and
  `catalogs/us-equities/decision-index.json` indexes repositories; neither lists decision records.
  `manifests/evidence.json` takes the changed files it already lists and the new files under `evidence/`
  (`docs/lanes.md`, hot-file protocol); like the context-budget record, this record is not registered there.

## Checks

| Command | Exit | Result |
| --- | ---: | --- |
| `python3 -m unittest tests.test_install_claude_profile.StandingRuleSurfacesTests`, before the template edits | 1 | 4 failures: `0 != 1` on each of the four surfaces (fail first) |
| `python3 -m unittest tests.test_wsl_new_distro_recipe.UserDataTemplateTests`, before the user-data edit | 1 | 3 failures: the two new `[time]` patterns, and the two new mutants were not yet mutations (fail first) |
| The same two checks, run in process against main `e8c1edec`'s four instruction files and user-data template | n/a | the same 4 and 3 failures (fail first, repeated) |
| `python3 -m unittest` (the full suite, with every code, test, template and registry change in place; only this record's prose changed afterwards) | 1 | 10,326 tests, 903 skipped, 11 failures and 18 errors, none in a test module this change edits. Every module this change edits, and every module that pins the two instruction templates, their carriers or the WSL recipe files, passes. 28 of the 29 recur unchanged in a clean clone of `e8c1edec`: a missing `exchange_calendars` module (the 18 errors, and the 5 `test_adaptive_paper_credential_race` failures, whose pristine baseline imports it), `dirname: command not found` (3), a systemd scope state (1) and the installed Claude Code's `auth_storage_failure` notification type (1). The 29th, `test_token_e2e_grader` F27c, passes in that clone; here `git clone --local` cannot hard-link from this worktree into `/tmp`, another file system |
| `node test-envelope.mjs` and `node test-contract-mutations.mjs`, in `examples/claude-native/workflows` | 0 | 254 and 74 passed |
| `python3 scripts/validate.py` | 0 | 10,217 hashed files, 208 receipts |
| `python3 scripts/evidence_manifest.py --check` | 0 | passed |
| `python3 scripts/validate_convergence.py blueprints/convergence-practice/wsl-new-distro-image-20261001/experiment.json` | 0 | the record is valid with the relocated frozen inputs |
| `python3 -B tools/adoption/new_wsl_client_config.py --check` | 0 | check passed |
| `python3 -B tools/adoption/new_wsl_client_config.py --render --host nativestack2604 --out <scratch>/user-times-render` | 0 | each rendered carrier holds the sentence once and equals the committed carrier byte for byte; `managed_block`'s merge of each gives 12,071 and 8,601 bytes with one copy |
| `python3 scripts/build_new_wsl_handbook.py --check` | 0 | current outputs |
| P2's render, then `cloud-init schema -c` (26.1-0ubuntu3~26.04.1, on NativeStack2604) | 0 | `Valid schema` |
| Path A simulation: `[boot]` and `systemd=true`, the user-data's appended content, then the logic of wsl-setup 0.6.3's `set_user_as_default` | 0 | six lines, each once; wsl-setup changes nothing |
| Path B simulation: W6's `[user]` and `[time]` lines, run twice on `[boot]` and `systemd=true` | 0 | six lines, each once |
| `git diff --check` | 0 | clean |

## Sources

- **Microsoft wsl-config, "Time settings"** ([learn.microsoft.com](https://learn.microsoft.com/en-us/windows/wsl/wsl-config#time-settings),
  read 2026-10-05):
  - pinned source MicrosoftDocs/WSL `7ea1c6f9e25f1c89a05a0e97e5325a02a66ac6cd`, `WSL/wsl-config.md:152-158`, which was
    still that file's latest commit on 2026-10-05;
  - section `[time]`, key `useWindowsTimezone`, boolean, default `true`.
- **ubuntu/wsl-setup** `73418e32bb48d514c2c2853fa7e5cacdcaf3dfe8` (0.6.3), `wsl-setup:55-73` (`set_user_as_default`).
- **[RFC 3339](https://www.rfc-editor.org/rfc/rfc3339)**, read 2026-10-05: §4.1 (UTC, because daylight-saving rules
  are convoluted and change by local law), §4.2 (numeric offsets; alphabetic labels interoperated poorly), §4.3 (`Z`
  makes UTC the preferred reference point) and §5.6 (`time-offset = "Z" / time-numoffset`).
- **[Claude Code memory](https://code.claude.com/docs/en/memory)**, read 2026-10-05: the user instructions file
  `~/.claude/CLAUDE.md`, "Personal preferences for all projects".
- **[Codex AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md)**, read 2026-10-05:
  - global scope in the Codex home (`~/.codex`, or `CODEX_HOME`);
  - "Create persistent defaults in your Codex home directory so every repository inherits your working agreements".
- **Claude Code** [CHANGELOG at v2.1.289](https://github.com/anthropics/claude-code/blob/v2.1.289/CHANGELOG.md): the
  2.1.257 entry adds `timeFormat` and `timeZone`. The installed 2.1.289 binary holds the setting descriptions quoted
  above.
- **Codex** [configuration reference](https://developers.openai.com/codex/config-reference), read 2026-10-05:
  `timezone` appears only in `tools.web_search` (`location = { country, region, city, timezone }`).
- **cloud-init 26.1** (installed `26.1-0ubuntu3~26.04.1`): `cloud-init schema -c` on the rendered user-data, P2's
  check.
