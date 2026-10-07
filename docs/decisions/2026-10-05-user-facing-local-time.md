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
- On NativeStack2604, each client's user-level file holds the user's own local-time rule, dated 2026-10-05, after the
  managed block's end marker (read 2026-10-05). This change leaves host files alone.
- NativeStack2604's `/etc/wsl.conf` held `[time] useWindowsTimezone=false` with no repository record; a private host plan
  had pinned it because Windows' automatic time zone setting was on. The coordinator set it to `true` on that host. The
  distribution recipe wrote no `[time]` key, so a new host relied on the default and nothing read the value back.

## Decision

1. **One instruction sentence at user level, in both clients, with one wording:**

   > When you tell the user a time, give it first in the host's local time zone (read it with `timedatectl` or
   > `date`), with UTC beside it, for example "4:00 PM EDT (20:00Z)". Write timestamps in ledger rows, receipts, evidence
   > and commit messages in UTC (RFC 3339 with `Z`); Git author/committer metadata retains its native format.

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
     templates and both carriers, and a new test in that class checks it. The sentence is a display rule (how an agent
      words a time it tells the user) plus a records rule (UTC timestamps in ledger rows, receipts, evidence and commit
      messages; Git metadata keeps its native format). The user
     keeps both at user level, the level both clients document for a person's standing working agreements:
     - Claude's memory documentation lists `~/.claude/CLAUDE.md` as "Personal preferences for all projects".
     - The Codex guide puts persistent defaults in the Codex home "so every repository inherits your working
       agreements".
     - Both clients load their user-level file in every project, this repository included, so a root copy would load
       twice here and count twice against each fixed startup ceiling.
     - The records rule also governs this repository's artifacts, which a session without the managed block can write;
       the overturn conditions below watch both halves.
2. **The recipe writes WSL's time-zone default explicitly.**
   - **Path A.** The cloud-init user-data appends `[time]` with `useWindowsTimezone=true` to `/etc/wsl.conf`, before
     `[user]`.
   - **Path B.** W6 uses Python's maintained ConfigParser read/set/write API to set the actual key to `true`, updating
     an existing `false` value or missing key and adding `[time]` only if absent. It preserves other section values and
     key case, with INI formatting/comments normalized on serialization.
   - **Read-back.** W5 reads the key back, and the first-boot checklist and the recipe record's command table follow.
   - **The source.** Microsoft documents the key as a boolean that defaults to `true`: "Setting this key will make WSL use
     and sync to the timezone set in Windows." The WSL 3.0.1 source holds the same default (Sources).
   - **What writing it does.** The key restates WSL's default, so the distribution's behavior does not change. It records
     the intent in the recipe, and W5 fails when the first boot finds a value other than `true` or no `[time]` section.
     W5 runs once, at the first boot; path B repeats its checks once, after W6. Nothing in the repository reads
     `/etc/wsl.conf` after provisioning, so a later change of the key, like the `false` found on NativeStack2604, is not
     detected. Detecting it would need a recurring read in a host probe.
   - **The zone itself.** The read-back proves the file's text, not the zone. W5 therefore also pairs the zone the
     distribution reports, `timedatectl show -p Timezone --value`, with the Windows zone, `tzutil /g`. They agree when
     the IANA zone is CLDR's `windowsZones` mapping of the Windows zone for the Windows region; WSL maps the zone with
     the ICU that Windows ships. Both outputs go to the receipt. A mismatch is recorded and stops the run for review
     without the failed-proof export and unregister: WSL leaves `/etc/localtime` unchanged when the mapping is empty or
     the zone's file is missing, so the remedy lies in the Windows region and zone or the image's `tzdata`, and
     unregistering the new distribution would change neither.
   - **Two paths set the zone.** While the key was `true` when an instance started, WSL links `/etc/localtime` to the
     mapped zone on two paths (Sources): at each instance start, and in every running instance when the WSL service
     receives a Windows `WM_TIMECHANGE` broadcast. A Windows time-zone change therefore reaches a running distribution
     mid-session, not only at its next start. A change of the key itself takes effect only at the next start, because
     init reads `/etc/wsl.conf` once, when the instance starts.
   - **First run.** The 26.04.1 image's `wsl-setup` 0.6.3 only appends or completes `[user]`, so the section survives its
     first run.
   - **Claude Code's UI clock.** Claude Code's own UI times follow the system zone by default (below), so they show the
     Windows zone while the distribution follows it.
3. **Recorded timestamps stay UTC.** Timestamps written in ledger rows, receipts, evidence and commit messages use
   RFC 3339 date-times with `Z`. This implementation scope does not alter Git author/committer dates: Git stores those
   as Unix seconds plus a numeric UTC offset, and preserves original authorship when reusing commits. It is not a
   claim that a Git commit object stores RFC 3339 text. See Git 2.53.0's
   [date formats](https://github.com/git/git/blob/v2.53.0/Documentation/date-formats.adoc#L4) and
   [authorship reuse](https://github.com/git/git/blob/v2.53.0/Documentation/git-commit.adoc#L81).

## Alternatives considered

- **A memory note.** The user rejected it. Memory is retrieved per project as evidence, not loaded as a standing
  instruction, so it would not reach every session or client.
- **Per-host lines in each client's user-level file, outside the managed block,** as the harness mechanism. Not
  chosen:
  - they cannot be reproduced on a new host and can drift from the managed source;
  - NativeStack2604 holds such a line, the user's own dated rule. After that host re-renders with this rule, the rule
    loads there twice, in the managed block and in the user's line, until the user decides (Evidence classes and
    limits).
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
`ecfa1127`. After the rebase onto it, both columns were measured again in code (the before column from main's startup
files, extracted to a scratch directory), and every value equals the first measurement, made on main `e8c1edec`.
This table and the sentence size below precede the review repair (`0df3f0dc`), which added 100 bytes to the
sentence; the 2026-10-06 addendum at the end of this record gives the measurements after it.

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
  and 8,601 bytes. These values precede the review repair; the 2026-10-06 addendum gives the current pin and sizes.
- **The cloud-init check.** `tests/test_wsl_new_distro_recipe.py` requires `[time]` and `useWindowsTimezone=true` in
  the render, and reads the appended `/etc/wsl.conf` text by section: `[time]` holds only that key and comes before
  `[user]`, which holds only the default user. Its new mutants are a lost section, `false`, the key moved under
  `[user]` (every line still present, so only the section reading rejects it) and `[user]` before `[time]`.
- **The new W6 command.** It has its row in the recipe record's command table and its entry in the receipt example. The
  row's proof says what the guard shows: a `[time]` section exists, and W5's repeated read-back confirms the value.
- **The W5 zone pair.** `timedatectl show -p Timezone --value` and `tzutil /g` have their rows in the command table,
  their entries in the receipt example and their place in the checklist's W5 line. `TimeZonePairTests` checks them
  with seven mutants, and with seven more checks what a mismatch does (recorded, a stop for review without the
  failed-proof export and unregister, on both paths), the failure rule's exception, the remedy, and the CLDR and
  tzutil pins.
- **The client-configuration record.** It takes the tool's regenerated listing (59 and 70 lines) in a dated addendum.
- **The new-WSL handbook.** It is regenerated on the rebased tree; it holds the recipe's SHA-256. Its receipt's
  `outputs` follow, with this change's `regenerations` entry after the one #703 added on main.
- **The registry.** `manifests/evidence.json` takes the new hashes of the 20 changed files it lists and the five new
  files under `evidence/artifacts/user-facing-local-time-20261005/`.
- **The passwordless-sudo criterion moved from recipe line 624 to 645.** The two live citations of it,
  `tools/adoption/host_baseline_probe.py` and `tools/adoption/host-baseline.md`, follow. Dated records keep their own
  line citations.
- **Unchanged.** The startup constants (`STARTUP_BUDGET_BYTES`), the scaffold, the moves fixture of the Codex top-rule
  section and the RTK block do not change.

## Overturn condition

- **A native setting.** A client release adds a setting that localizes times the model writes. Raise it to the user,
  who decides whether it replaces the display half. The records half stays in force whatever display setting is
  adopted, because no display setting keeps records in UTC.
- **Sessions without the managed user block.** Cloud sessions, CI agents or a host not yet re-rendered are shown
  reporting times to the user in UTC only. Then add the sentence to the repository `AGENTS.md` and the scaffold, under
  the three-surface test, with a dated byte comparison.
- **A non-UTC record.** A ledger row, receipt or evidence file in this repository carries a timestamp that is not UTC,
  written by a session without the managed block. Then add the records half to the repository `AGENTS.md`, under the
  three-surface test.
- **The user changes the format,** for example to local time only or a 24-hour clock.
- **A host's zone is not the user's,** for example a remote or cloud host on UTC. Raise it to the user, who decides the
  wording; a fixed zone in the portable templates would be wrong for other users (Alternatives).
- **WSL changes `useWindowsTimezone`'s meaning or default,** in Microsoft's documentation or in the WSL source
  (`src/linux/init/WslDistributionConfig.h` at the installed release).
- **A missed rule at its trigger.** After the hosts re-render, an agent shows the user a UTC-only time. Sharpen the
  sentence, as the budget record's reopening rule says.

## Evidence classes and limits

- **Evidence classes.** This is source review and local integration: unit tests, the F9 check and render, cloud-init's
  own `schema -c` on the rendered user-data, and two synthetic `/etc/wsl.conf` simulations in a scratch directory. No
  first boot, import, host re-render or model run happened. No model run measured whether agents follow the sentence.
- **The zone pair has no W5 output yet.** No first boot ran for this change. A host read on NativeStack2604 on
  2026-10-05, not a W5 run, gave `America/New_York` from `timedatectl show -p Timezone --value` and
  `Eastern Standard Time` from `tzutil /g`, both with exit 0; `/etc/localtime` links to the same zone.
- **Host work.** The NativeStack2604 change to `useWindowsTimezone=true` was the coordinator's host action and is not
  part of this change. The host re-render that delivers the sentence comes after landing. A re-render replaces only
  the text between the managed markers and keeps every byte outside them (`tools/adoption/managed_block.py:106-113`),
  so the user's own dated rule after the end markers stays, and the rule loads twice on NativeStack2604 until the user
  decides. Whether to remove the user's copy is the user's call; this change does not touch it.
- **Commit scope clarified in the review repair.** The managed records sentence covers timestamps written in commit
  messages/text. Native Git author/committer metadata keeps its Unix-time-plus-offset format (for example `-0400`);
  this patch supplies no metadata override or history rewrite. A future requirement to normalize metadata offsets
  needs a separate user decision and a mechanism that preserves original author instants. This narrows the
  implementation's previously ambiguous term; it is not a new assertion of the user's intent about metadata.
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

The first three rows are the first round's fail-first checks, on main `e8c1edec`. Every other row was run after the
rebase, at base `ecfa1127`, on NativeStack2604 (2026-10-05 and 2026-10-06 UTC). The review's third round changed:
- the recipe's and the checklist's prose;
- the 2026-10-01 record and this record;
- `tests/test_wsl_new_distro_recipe.py`;
- the probe's citation of the recipe;
- the regenerated handbook, receipt and registry.

Rows whose result starts "round 3" ran again on that final tree. The others ran on the round-2 tree, `608c5266`. The
third round changed no template, carrier, user-data or startup file. Only this record's prose changed after the last
checks. Every row precedes the review repair (`0df3f0dc`); the 2026-10-06 addendum lists the checks run after it.

| Command | Exit | Result |
| --- | ---: | --- |
| `python3 -m unittest tests.test_install_claude_profile.StandingRuleSurfacesTests`, before the template edits | 1 | 4 failures: `0 != 1` on each of the four surfaces (fail first) |
| `python3 -m unittest tests.test_wsl_new_distro_recipe.UserDataTemplateTests`, before the user-data edit | 1 | 3 failures: the two new `[time]` patterns, and the two new mutants were not yet mutations (fail first) |
| The same two checks, run in process against main `e8c1edec`'s four instruction files and user-data template | n/a | the same 4 and 3 failures (fail first, repeated) |
| `python3 -m unittest` (the full suite) | 1 | round 2: 10,347 tests in 1,719 s, 903 skipped, 11 failures and 18 errors, none in a test module this change edits. All 29 are the classes the first round found recurring unchanged in a clean clone of `e8c1edec`: a missing `exchange_calendars` module (the 18 errors, and the 5 `test_adaptive_paper_credential_race` failures, whose pristine baseline imports it), `dirname: command not found` (3), a systemd scope state (1), the installed Claude Code's `auth_storage_failure` notification type (1), and `test_token_e2e_grader` F27c (1), whose `git clone --local` cannot hard-link from this worktree into `/tmp`, another file system (it passed in that clone) |
| `python3 -m unittest tests.test_install_claude_profile tests.test_codex_worker_lane tests.test_wsl_new_distro_recipe` | 0 | round 3: 334 tests, 13 skipped (round 2: 333) |
| `python3 -m unittest tests.test_new_wsl_handbook tests.test_new_wsl_client_config tests.test_new_wsl_profile tests.test_host_baseline_probe` | 0 | round 3: 309 tests, the modules that read the recipe, the receipt or the probe |
| `python3 -m unittest` over the 19 other modules that pin the touched files (`test_new_wsl_handbook`, `test_new_wsl_client_config`, `test_new_wsl_profile`, `test_host_baseline_probe`, `test_managed_block`, `test_codex_agents`, `test_codex_roles`, `test_scaffold_repo`, `test_bootstrap_full_profile`, `test_token_e2e_grader`, `test_landscape_sweep_harness`, `test_landscape_sweep_skills`, `test_freeze_snapshot`, `test_blind_checkout`, `test_runtime_worker_openhands_push_gate`, `test_runtime_worker_openhands_resolver`, `test_upstream_surface_watch`, `test_catalog_freshness_runtime`, `test_new_wsl_definitive_defaults`) | 1 | round 2: 2,237 tests, 15 skipped, 1 failure: F27c, as above (`Invalid cross-device link` at the clone, before any check; the suite's `TMPDIR` guard refuses a directory inside the repository) |
| `node test-envelope.mjs` and `node test-contract-mutations.mjs`, in `examples/claude-native/workflows` | 0 | round 2: 254 and 74 passed |
| `python3 scripts/validate.py` | 0 | round 3: 10,277 hashed files, 212 receipts |
| `python3 scripts/evidence_manifest.py --check` | 0 | round 3: passed |
| `python3 scripts/validate_convergence.py blueprints/convergence-practice/wsl-new-distro-image-20261001/experiment.json` | 0 | round 3: the record is valid with the relocated frozen inputs |
| `python3 -B tools/adoption/new_wsl_client_config.py --check` | 0 | round 3: check passed, with two warnings, both about slot `mcp-inspector`, from inputs this change does not touch (round 2 reported one: it read only the output's last two lines) |
| `python3 -B tools/adoption/new_wsl_client_config.py --render --host nativestack2604 --out <scratch>/user-times-render` | 0 | round 2: each rendered carrier holds the sentence once and equals the committed carrier byte for byte; `managed_block`'s merge of each gives 12,071 and 8,601 bytes with one copy |
| `python3 scripts/build_new_wsl_handbook.py --check` | 0 | round 3: current outputs |
| Startup bytes: `PortableTopRuleTests.startup_files` on this tree, and on main `ecfa1127`'s startup files in a scratch directory | 0 | round 2: the Startup bytes table, unchanged from the first round |
| P2's render, then `cloud-init schema -c` (26.1-0ubuntu3~26.04.1, on NativeStack2604) | 0 | round 2: `Valid schema` |
| Path A simulation: `[boot]` and `systemd=true`, then the user-data's `write_files` content as cloud-init's YAML gives it, then wsl-setup 0.6.3's own `set_user_as_default` with only its file path changed | 0 | round 2: six lines, each once; wsl-setup changes nothing |
| Path B simulation: W6's `[user]` and `[time]` lines, run twice on `[boot]` and `systemd=true` | 0 | round 2: six lines, each once |
| Host read: `timedatectl show -p Timezone --value`; `tzutil.exe /g` (not a W5 run) | 0; 0 | round 2: `America/New_York`; `Eastern Standard Time` |
| `git diff --check` | 0 | round 3: clean |

## Sources

- **Microsoft wsl-config, "Time settings"** ([learn.microsoft.com](https://learn.microsoft.com/en-us/windows/wsl/wsl-config#time-settings),
  read 2026-10-05):
  - pinned source MicrosoftDocs/WSL `7ea1c6f9e25f1c89a05a0e97e5325a02a66ac6cd`, `WSL/wsl-config.md:152-158`, which was
    still that file's latest commit on 2026-10-05;
  - section `[time]`, key `useWindowsTimezone`, boolean, default `true`.
- **microsoft/WSL** `91f161fa240dc355c1a88daabc8aac4273e35ba5` (tag 3.0.1, the release W1 requires), read 2026-10-05;
  the running-instance lines re-read 2026-10-06 UTC:
  - `src/linux/init/WslDistributionConfig.h:25` (`time.useWindowsTimezone`) and `:58` (`bool AutoUpdateTimezone =
    true;`), registered at `WslDistributionConfig.cpp:42`;
  - `src/linux/init/timezone.cpp:22-110` (`UpdateTimezone`): no change when the key is off (`:49-52`), the mapping is
    empty (`:54-58`) or the zoneinfo file is missing (`:66-70`); otherwise it relinks `/etc/localtime` and rewrites
    `/etc/timezone` (`:76-106`);
  - at instance start: `ConfigInitializeCommon` reads `/etc/wsl.conf` once (`src/linux/init/config.cpp:532`), and
    `config.cpp:882` calls `UpdateTimezone`;
  - in a running instance: the service's window receives broadcast messages
    (`src/windows/service/exe/LxssUserSession.cpp:607-647`, whose comment at `:619` names `WM_TIMECHANGE`). On
    `WM_TIMECHANGE` (`:4294-4305`) it calls `_TimezoneUpdated`, which logs "Received timezone change notification" and
    updates every running instance (`:3835-3846`). Each instance sends the mapped zone to its init
    (`src/windows/service/exe/WslCoreInstance.cpp:349-362`), whose message loops in `InitEntryUtilityVm` and
    `InitEntryWsl` call `UpdateTimezone` with the configuration read at start (`src/linux/init/init.cpp:2559-2561` and
    `:2745-2747`). That a Windows time-zone change raises `WM_TIMECHANGE` rests on WSL's own comment and log text; no
    Microsoft document was read for it;
  - `src/windows/common/helpers.cpp:358-413` (`GetLinuxTimezone`): the Windows zone from `GetDynamicTimeZoneInformation`
    and the region from `GetUserDefaultGeoName`, mapped by `ucal_getTimeZoneIDForWindowsID`, with Windows' own ICU
    (`src/windows/common/precomp.h:40` includes `<icu.h>`; `CMakeLists.txt:386` links `icu.lib`).
- **ICU** `release-78.3` (`21d1eb0f306e1141c10931e914dfc038c06121da`), read 2026-10-05, for the API's meaning only (the
  data version Windows ships is not established here): `icu4c/source/i18n/unicode/ucal.h:1644-1674`
  (`ucal_getTimeZoneIDForWindowsID`, a Windows zone ID to a system zone ID for a region) and
  `icu4c/source/i18n/timezone.cpp:1698-1719` (the first zone of the region's row, else the `001` row).
- **CLDR** `release-48-2` (`11299982335beb974c1c63c45265184e759c0f41`), `common/supplemental/windowsZones.xml:130` and
  `:133`, read 2026-10-05: `Eastern Standard Time` maps to `America/New_York` for `001` and first for `US`.
- **Microsoft tzutil** ([learn.microsoft.com](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/tzutil),
  read 2026-10-05; MicrosoftDocs/windowsserverdocs `48fd05321fd0fe328b1977597b554d884ca5e35d`,
  `WindowsServerDocs/administration/windows-commands/tzutil.md:18` and `:25`): `/g` "Displays the current time zone
  ID."
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

## Addendum (2026-10-06): measurements after the review repair

The review repair (`0df3f0dc`) gave the sentence the records half that Decision 1 quotes, in both templates and both
F9 carriers. The sentence grew from 227 to 327 bytes, and each of those four files by 100 bytes. The Startup bytes
table, the sentence size, the pin and size comments under "Pins amended in the same change" and every Checks row above
precede that repair; they stay as the record of the earlier tree. The repair left `TOP_RULE_SHA256` and those comments
stale (a review finding of 2026-10-06), and this addendum's change repairs them.

These values were measured on 2026-10-06 UTC on NativeStack2604 with `PortableTopRuleTests.startup_files` on the
repaired tree. The two earlier columns were computed again with the same file set, reading the startup files and
carriers from `ecfa1127` and from `a10ad2c0`, the branch head before the repair; both reproduce the table above. No
startup file other than the two carriers changed between `ecfa1127` and the repaired tree.

| File or scope | Main `ecfa1127` | Before the repair, `a10ad2c0` | After the repair |
| --- | ---: | ---: | ---: |
| `examples/claude-native/CLAUDE.md` and its carrier | 11,575 | 11,805 | 11,905 (+330 against main) |
| Claude rendered user block | 11,841 | 12,071 | 12,171 |
| `adoption/templates/codex.AGENTS.template.md` (local check: under 8,192) | 7,307 | 7,535 | 7,635 (+328) |
| Codex rendered carrier | 8,373 | 8,601 | 8,701 |
| Claude startup scope (fixed ceiling 24,458) | 23,566 | 23,796; headroom 662 | 23,896; headroom 562 |
| Codex startup scope (fixed ceiling 20,103) | 19,332 | 19,560; headroom 543 | 19,660; headroom 443 |
| Claude post-gate projection (scope − 680; ceiling = ×1.05, rounded up) | 22,886; 24,031 | 23,116; 24,272 | 23,216; 24,377 |
| Codex post-gate projection | 18,652; 19,585 | 18,880; 19,824 | 18,980; 19,929 |

- **The constants.** They stay at 24,458 and 20,103; nothing is re-baselined. When the routing host gate passes,
  lowering both constants to the measured post-gate scopes plus 5% gives 24,377 and 19,929 for these inputs, replacing
  24,272 and 19,824 above. The budget record has a matching dated addendum.
- **The pin.** `TOP_RULE_SHA256` moves from `82e23b68466ed8b96566a229582f0c99fa1456a393e635f18cc5e65f601f4d09` to
  `d21bb3bc0a2e68fb362af1d085da3761a08cc5ccec18ebd7ed16dd83d80bb3cd`. It was re-derived with the module's
  `template_segments()`, whose top-rule segment, ending at the RTK marker, is now 6,360 bytes, and it equals the value
  the review computed.
- **The size comments.** Those in `tests/test_codex_worker_lane.py` and `tools/adoption/new_wsl_client_config.py` now
  give 7,635 and 8,701 bytes.
- **One wording.** The sentence is byte-identical in both templates and both F9 carriers. The repair changed all four
  together with `StandingRuleSurfacesTests.LOCAL_TIME`, which checks that wording once on each, so no surface besides
  the pin and these records needed a change.
- **Erratum.** "No decision index" above says this record, like the context-budget record, is not registered in
  `manifests/evidence.json`. This branch lists both in its `files[]` (main does not), so their edits here are
  re-registered, with the test and the renderer, in the branch's last commit.

These checks ran on 2026-10-06 UTC on NativeStack2604. The tests ran before this table was written; `validate.py`, the
manifest order check and `git diff --check` ran again after it.

| Command | Exit | Result |
| --- | ---: | --- |
| `python3 -B -m unittest tests.test_codex_worker_lane.TemplateTests.test_top_rule_is_pinned_and_rendered_rtk_is_the_unchanged_pinned_source`, before the pin repair (`563eedab`) | 1 | the segment hashed to `d21bb3bc…` against the pinned `82e23b68…` (the review's finding, reproduced) |
| The same test, after it | 0 | 1 test |
| `python3 -B -m unittest` on 13 modules (the first 13 below), before the pin repair | 1 | 1,297 tests; the only failure is the test above |
| `python3 -B -m unittest`, one run per module, after the repair: `test_codex_worker_lane`, `test_install_claude_profile`, `test_managed_block`, `test_new_wsl_client_config`, `test_codex_agents`, `test_codex_roles`, `test_scaffold_repo`, `test_bootstrap_full_profile`, `test_wsl_new_distro_recipe`, `test_new_wsl_handbook`, `test_landscape_sweep_harness`, `test_runtime_worker_openhands_push_gate`, `test_runtime_worker_openhands_resolver`, `test_catalog_freshness_runtime`, `test_freeze_snapshot`, `test_new_wsl_definitive_defaults`, `test_upstream_surface_watch` | 0 each | 1,754 tests, 26 skipped: every module that names the two templates or carriers, or reads the test, the renderer or these two records |
| `python3 -B tools/adoption/new_wsl_client_config.py --check` | 0 | check passed, with the same two warnings about slot `mcp-inspector` |
| `python3 -B tools/adoption/new_wsl_client_config.py --render --host nativestack2604 --out <scratch>` | 1 | stopped before rendering: this worktree has no host value file (`adoption/hosts/nativestack2604.json` is not tracked); the block sizes above come from `startup_files`' own `managed_block` merge of the committed carriers |
| `python3 -B scripts/build_new_wsl_handbook.py --check` | 0 | current outputs (MD `4480fe88…`, JSON `0bf0583e…`); none of the four changed files is a handbook source |
| `python3 scripts/validate.py` | 0 | 10,322 hashed files, 212 receipts |
| `python3 scripts/evidence_manifest.py --check` | 0 | passed |
| `git diff --check` | 0 | clean |
