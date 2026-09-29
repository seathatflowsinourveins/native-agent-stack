# Freeze snapshot for the #381 window W

The #381 protocol freezes the environment before the run and forbids changes while a run window is open
([README "Procedure", step 2](../../evidence/artifacts/token-adoption-e2e-20260926/README.md#procedure--aa-84) and
[RUNBOOK "Freeze and preflight"](../../evidence/artifacts/token-adoption-e2e-20260926/RUNBOOK.md#freeze-and-preflight--aa-7-81-84-steps-12)).
[`freeze_snapshot.py`](freeze_snapshot.py) makes that list mechanical: it captures the frozen state as items (hashes,
versions, counts, booleans, unit states), compares two captures and checks a capture against the sealed expectations that
Amendment 4 publishes, so any session can test its own change against the frozen set without a run.

It is glue over existing commands and file hashes, not a measurement instrument, and it decides nothing: it reports.
Written for Python 3.9 or newer (the tests ran on 3.12.3 and 3.13.15), standard library only, Linux first. It writes only the two capture files, edits no host state, opens
no credential store, and never prints or stores an environment value, a token, a host name or a user name.

## Commands

```sh
T=tools/token-e2e/freeze_snapshot.py
python3 -B $T capture --label seal --out "$FREEZE_DIR" [--repo <checkout>] [--config freeze.json] [--no-usage-probe]
python3 -B $T compare <a.json> <b.json> [--full]
python3 -B $T check <capture.json> --expected <expected.json> [--quiet]
python3 -B $T list-frozen [--config freeze.json] [--repo <checkout>] [--all] [--json]
```

- `capture` writes `freeze-<label>.json` (mode 0600: every item plus the `~/...` or `<repo>/...` path its value was read
  from) and `freeze-<label>.sanitized.json` (the same items with no path field and no path character in any string). The
  checkout defaults to the one holding the current directory; the output directory must lie outside it, is created with
  mode 0700 when new, and an existing capture of the same label is never overwritten. It prints one summary line
  (`items`, `ok`, `missing`, `error`, `not_applicable`, `frozen_not_ok`).
- `compare` prints one line for every item that differs: `DRIFT` (a frozen value or status changed), `MISSING` (a frozen
  item exists in one capture only), `ERROR` (a frozen item is in error on either side, so it attests nothing) and `INFO`
  (an informational item changed or exists once). Identical items print nothing. Hashes print as twelve characters unless
  `--full`. Either capture may be the private or the sanitized file.
- `check` compares the frozen items of a capture with the sealed expectations. A sanitized capture is the expectations
  format, so the owner captures at the seal and publishes that file. It prints `PASS <id>` or `FAIL <id> <reason>` per
  frozen id and `check: pass=N fail=M`; `--quiet` drops the PASS lines. A frozen id missing from either side fails, so an
  added hook or block is a failure, and so is an item that is in error. A sealed absence (`missing`) passes while the
  capture is absent too.
- `list-frozen` prints `<id><TAB><how to check>` for every frozen item and family (`--all` adds the informational ones,
  `--json` prints id, class, family, owner and how). It runs no capture and needs no checkout; without `--repo` it checks
  the paths of a configuration against the home directory only.

Exit status: `0` done (compare: no frozen drift; check: all pass), `1` a frozen item drifted or failed, `2` a usage, input
or configuration error, `3` the privacy guard refused the output (nothing was written).

An item is `{"id", "class": "frozen" | "informational", "status": "ok" | "missing" | "error" | "not_applicable",
"value", "method"}`, plus a `reason` token when the status is not `ok` and, in the private file only, a `path`. Items
are sorted by id. A frozen item that is `missing` or `not_applicable` is part of the frozen set: the seal records the
absence and `check` fails when it changes.

## Use in the #381 protocol

| Moment | Command | What it settles |
| --- | --- | --- |
| Seal (the merged Amendment 4 revision, tracked tree clean, nothing installing) | `capture --label seal` | The private file stays with the owner; the sanitized file is the sealed expectations. Record its sha256 in the amendment, because a hash proves byte identity of that file. |
| Any time, any session | `list-frozen` | The frozen ids and their how-to-check lines, without a capture. |
| Before changing anything, and after | `capture`, then `check <capture> --expected <seal.sanitized.json>` | Whether the change touches a frozen item, by id. |
| W open, before the first arm | `check <open capture> --expected <seal.sanitized.json>` | Every frozen item still equals the seal. The owner decides what a failure means. |
| W start and W end | `capture --label w-start`, `capture --label w-end`, then `compare w-start w-end` | Whether a frozen item moved while the window was open: exit `1` on any drift, missing item or error; informational items are listed and never fail. |

Capture at these boundaries, not inside a window: `claude mcp list` connects to (and starts) every configured MCP server,
and the usage probe is one model call.

## Catalogue

`list-frozen --all` is the authority; this table groups it. Ids use `.` between parts and `:` where a relative path has
a slash. `<unit>` is one of `ecosystem-otelcol`, `ecosystem-loki`, `ecosystem-prometheus`, `ecosystem-grafana`,
`omniroute`, `omniroute-fw`, `hindsight-live`, `cognee-live`, `ai-memory`, plus any unit the configuration adds (frozen unless it says informational).

| Ids | Class | Value and how it is read |
| --- | --- | --- |
| `repo.head`, `repo.tree_clean` | frozen | `git rev-parse HEAD`; whether `git status --porcelain --untracked-files=no` is empty (tracked files only). Every git call uses `--no-optional-locks`, so the checkout's index is not rewritten. |
| `repo.sealed.<file>` (5) | frozen | sha256 of `preregistration.json`, `token-e2e-run.mjs`, `RUNBOOK.md`, `fixtures/table.json` and `fixtures/events.jsonl` under `evidence/artifacts/token-adoption-e2e-20260926/`. |
| `repo.carrier.*` | frozen | sha256 of each `adoption/hooks/claude/token-lanes-block*.md` and of `token-lanes-subagent-start.py`. |
| `repo.capability_gate.*` | frozen | sha256 of every file under `tools/capability-gate/` except its `README.md`. |
| `repo.workflow.<file>` (3), `repo.tool.skill_usage.py` | frozen | sha256 of `child-usage.mjs`, `shell-parser.pin.json`, `SHA256SUMS` under `examples/claude-native/workflows/` and of `tools/skill-usage/skill_usage.py`. |
| `roles.<role>.{adoption,examples,project,user}`, `roles.<role>.identical_across_copies` | frozen | For `stack-verifier`, `isolated-builder`, `source-scout`, `stack-researcher` and `evidence-reviewer`: sha256 of the body in `adoption/agents/claude`, `examples/claude-native/agents`, the project `.claude/agents` and `~/.claude/agents`; true when all four exist and are byte-identical. |
| `hooks.installed.*`, `hooks.carriers_match_repo` | frozen | sha256 of each file in `~/.claude/hooks` (names containing `.bak` are skipped) and of each carrier the checkout ships, so a missing installed carrier is a `missing` item; true when every carrier the checkout ships has a byte-identical installed copy. |
| `claude.version`; `claude.launcher.{sha256,size}`; `claude.binary.{version_name,size,sha256}` | frozen | First line of `claude --version`; the launcher `~/.local/share/codex-ecosystem/bin/claude`; the file `~/.local/bin/claude` resolves to and its `versions/<name>` name. |
| `claude.user_claude_md.sha256`, `claude.user_rtk_md.sha256` | frozen | sha256 of `~/.claude/CLAUDE.md` and `~/.claude/RTK.md`. |
| `claude.settings.{user,project,local}.sha256` and `claude.settings.{user,project,local}.{effort_level_env_unset, agent_teams_env, subagent_model_env, has_model_settings, has_effort_level, advisor_model}` | frozen | sha256 of `~/.claude/settings.json`, the checkout's `.claude/settings.json` and `.claude/settings.local.json`, and values derived from the whole parsed file: no `CLAUDE_CODE_EFFORT_LEVEL` key in its `env` block; class of `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` (`1`, `other`, `unset`); `CLAUDE_CODE_SUBAGENT_MODEL` and `advisorModel` as a model alias, `other` or `unset`; `modelSettings` and `effortLevel` present. An unparsable file keeps its hash and reports `error` for the derived items. |
| `claude.process.{effort_level_unset, agent_teams_env, subagent_model_env}` | frozen | The same three, read from the environment of the process running the capture. |
| `claude.mcp.*`, `claude.mcp_count` | frozen | From `claude mcp list` run in the checkout: one item per server name, true when it reports `Connected`, and the number of servers. |
| `codex.version`; `codex.config.sha256`; `codex.stack_worker_profile.{sha256,present}`; `codex.agents_md.sha256`; `codex.rtk_md.sha256` | frozen | `codex --version`; sha256 of `~/.codex/config.toml`, `~/.codex/stack-worker.config.toml` (present: the file exists), `AGENTS.md` and `RTK.md` in `~/.codex`. |
| `wiring.complete`, `claude.wiring.*`, `codex.wiring.*` | frozen | Booleans and counts (hook events, trusted events) from `scripts/adoption_status.py --client-wiring --json` in the checkout; strings are never taken. |
| `tools.pinned.<component>`, `tools.pinned_versions_match` | frozen | Pinned version, checked flag and match flag per component, and the overall flag, from `scripts/adoption_status.py --profile token-efficiency --pinned-versions --json`. |
| `tools.{rtk,node,python}.version`, `tools.rtk.config.sha256` | frozen | First line of `rtk --version`, `node --version`, `python3 --version`; sha256 of `~/.config/rtk/config.toml`. |
| `tools.tokenizer.{version, o200k_base.sha256, o200k_bpe_ranks.sha256}` | frozen | `gpt-tokenizer` package version and the sha256 of `cjs/encoding/o200k_base.js` and `cjs/bpeRanks/o200k_base.js` under the tokenizer prefix. |
| `tools.token_manifest.sha256`, `tools.token_manifest_test.sha256`, `tools.token_manifest_template.sha256`, `tools.token_manifest_full_template.sha256` | frozen | sha256 of `tools/token-report/token_manifest.py`, its test file and its two HTML templates. |
| `tools.qmd.{documents,vectors,pending,orphaned}` | frozen | Counts from the `Documents` block of `qmd --index native-agent-stack-catalog status`; the Orphaned and Pending lines are absent when zero. |
| `tools.parser.file.*`, `tools.parser.all_match_pin` | frozen | sha256 of each file `examples/claude-native/workflows/shell-parser.pin.json` names, read from the installed parser directory (the pin's `install.default_directory` under the home directory, or the configured `parser_dir`); true when every one equals the pinned value. Without the pin file (it ships with U1) the flag is `missing`. |
| `services.<unit>.{load_state, active_state, main_pid, n_restarts, config_sha256}` | frozen | One `systemctl --user show <unit> -p LoadState -p ActiveState -p MainPID -p NRestarts -p ExecStart` per unit. A unit that is not loaded reports `load_state` and `missing` for the rest. `config_sha256` is the sha256 of the file named by `--config`, `--config.file` or `-config.file` in `ExecStart` (a `file:` scheme is dropped), `not_applicable` when the unit names none. The unit's environment is never requested. |
| `gateways.<gateway>.route.<route>`, `gateways.<gateway>.build_id` | frozen | Only with a configured gateway: see below. |
| `extra.<id>` | frozen or informational | Only with a configured file: its sha256. |
| `capacity.codex.weekly_{used_percent,resets_at_utc}` | informational | The weekly (10080 minute) window of `scripts/codex_quota.py --json`. |
| `capacity.claude.{five_hour,seven_day}_{utilization_fraction,resets_at_utc}` | informational | `unifiedWindows` of the `rate_limit_event` returned by one headless Haiku call. |
| `capacity.host.{load_average,memory_available_mib}` | informational | `os.getloadavg()` and `MemAvailable` from `/proc/meminfo` (`not_applicable` off Linux). |
| `time.{capture_start_utc,capture_end_utc,tool_version,tool_revision,tool_sha256}` | informational | The capture's UTC start and end, the tool's version, the git revision of the checkout holding the tool, and the sha256 of the tool file. |

The usage probe is `claude -p OK --model haiku --output-format json --verbose --no-session-persistence --setting-sources
project`, run in a temporary directory without `OTEL_RESOURCE_ATTRIBUTES` and `RTK_DB_PATH`. The brief's command reads the
same event; `--verbose` makes the output the event array whatever the user's settings say, and the other flags keep the
call from running the user's hooks or MCP servers or leaving a transcript. `--no-usage-probe` skips it and reports the
four items as `missing` with reason `skipped`.

## Configuration

`freeze.json` is optional and every key is optional; unknown keys are an error.

```json
{
  "files": [
    {"id": "token-report-config", "path": "~/.local/state/native-token-report/config.json"},
    {"id": "token-report-timer", "path": "~/.config/systemd/user/token-report-refresh.timer", "class": "informational"},
    {"id": "socraticode-package", "path": "~/.local/share/codex-ecosystem/tools/socraticode-1.15.0/lib/node_modules/socraticode/package.json"}
  ],
  "units": ["token-report-refresh", {"name": "paper-rth-20260929", "class": "informational"}],
  "qmd_index": "native-agent-stack-catalog",
  "parser_dir": "~/.local/share/codex-ecosystem/tools/tree-sitter-bash-0.25.1",
  "tokenizer_prefix": "~/.local/share/native-token-report/tokenizer",
  "gateways": [{
    "id": "omniroute",
    "base_url": "http://127.0.0.1:20128",
    "routes": [{"id": "models", "path": "/v1/models"},
               {"id": "health", "path": "/health", "ignore_keys": ["uptime"]}],
    "build_id": {"route": "health", "field": "build"}
  }]
}
```

- `files`: extra files by id and path (`~/...`, absolute, or relative to the checkout); `class` defaults to `frozen`. Use
  it for what the catalogue does not hash: the token-report configuration, service and timer, and the installed package of a
  component that `scripts/adoption_status.py --pinned-versions` reports as unchecked (on the workstation host `context-mode`
  and `socraticode`, whose probes are not run).
- `units`: extra systemd user units, added to the nine defaults. An entry is a unit name (frozen) or
  `{"name", "class"}`; `informational` records a unit that may run inside a run window, such as a paper-trading unit, without
  failing `compare`. A default unit is always frozen: naming one as informational is an error.
- `gateways`: a plain `http` origin on `127.0.0.1`, `localhost` or `[::1]`, and the paths to fetch. Each route is one
  unauthenticated GET without proxy or redirect; its value is `sha256(json.dumps(body, sort_keys=True))` with the
  route's `ignore_keys` removed at every depth. `build_id` reads one JSON field (dotted for nested) or one response
  header of a route. A non-2xx answer, a body that is not JSON or an unreachable gateway is `error` with the token
  (`http_401`, `not_json`, `timeout`, `unreachable`) as its value; the tool sends and reads no credential, so an
  authentication failure is an error and never a bypass. The owner supplies the endpoints and the rules.
- A path outside the checkout and the home directory is refused, symlinks included. The three credential stores
  (`~/.claude.json`, `~/.claude/.credentials.json`, `~/.codex/auth.json`) are refused by name, by symlink and by inode, in
  the configuration and in any path read from a unit file. No error message names a path.

## Privacy

- Collectors derive booleans, counts, hashes, versions and model aliases. A model alias prints only when it is a short
  lower-case token; anything else is the class `other`. Settings and unit files are read whole and in process; their values
  are never copied.
- The private capture stores paths as `~/...` or `<repo>/...`, never as an absolute path. The sanitized capture has no path
  field, no path character and no user name.
- A last guard refuses the whole capture (exit 3, nothing written) if any string carries an environment value of eight
  characters or more (except the model alias of `CLAUDE_CODE_SUBAGENT_MODEL`), the home or checkout path, or the user or
  host name. A value or name that the tool's own catalogue text already contains is not listed, so a host whose user is
  called `claude` can still capture. The refusal names the items (a host-derived family member by its family) and the
  environment variable names involved, never a value.
- Every scanner is a linear character scan; no regular expression is used.

## Limits

- A hash proves byte identity, not behaviour. `sha256` of a file says the bytes are the sealed bytes, nothing about what a
  running process loaded earlier or does later.
- Informational capacity items (time, Codex and Claude windows, load, memory) are not frozen. They describe whichever
  account the client was signed into when the capture ran, and `check` never reads them.
- A capture is one instant. A unit that stopped and returned to the same state between two captures shows only through
  `main_pid` and `n_restarts`; a file changed and changed back shows nothing.
- `tools.qmd.*` counts move when anything updates the index. On the workstation host the index changed on its own between
  the amendment notes and this unit's captures (285 files and no pending in the notes, 288 files and 15 pending later), so
  the seal is only meaningful when no update, embed or cleanup runs, as the freeze already requires.
- `claude mcp list` starts each configured server to test it, so a `claude.mcp.<name>` flag can flip between W-start and
  W-end without any file changing (a slow start, a server that needs a network). Read such a drift before treating it as a
  change of configuration; `claude.mcp_count` and the file hashes tell the two apart.
- `ai-memory` and `cognee-live` are not systemd user units on the workstation host (`load_state` is `not-found`), so the
  seal freezes their absence. Name the real unit in `units` if a host runs them as units.
- A gateway's build identifier is read from its HTTP answer (a JSON field or a header), because the tool never requests a
  unit's `Environment`; a build id kept only in a unit's environment is not captured.
- `shell-parser.pin.json` ships with U1, so `tools.parser.*` are `missing` on a checkout that predates it, and the seal
  then freezes that absence.
- `unifiedWindows` in the `rate_limit_event` (the five-hour and seven-day windows) is observed on claude 2.1.284, not
  documented: a client update may drop it, and the four Claude capacity items then read `missing`. The Agent SDK reference
  documents only the single-window fields `status`, `resets_at`, `rate_limit_type` and `utilization`.
- Only the first configuration flag of a unit's `ExecStart` is hashed. A unit that reads its configuration from an
  environment variable or from arguments the flags above do not name reports `not_applicable`.
- macOS: `services.*` and the memory item report `not_applicable`; the other items are unverified there because no macOS
  host ran them. Windows is unsupported.
- The tests below are integration checks of this glue against a synthetic host, not upstream acceptance and not a
  statement about any real host; only a `capture` on the host does that.

## Tests

```sh
TMPDIR=<private dir> python3 -B -m unittest tests.test_freeze_snapshot
```

The suite builds a temporary host (a git checkout, a home directory, fake `claude`, `codex`, `rtk`, `node`, `python3`,
`qmd`, `systemctl` and `git` on a private `PATH`, canned repo scripts and a loopback HTTP server) whose canned outputs
copy the shapes read from the real commands on 2026-09-29. `MutationControlTests` writes a mutant of the tool for each
property (an environment leak with and without the guard, a variant that prints `os.environ`, a collector blind to each
item class, informational drift that fails, a check that always passes, credential refusal off, a missing tool that
raises) and requires the test for that property to fail on it. `FREEZE_SNAPSHOT_TOOL` points the suite at another copy of the tool and `FREEZE_MUTANT_DIR` keeps
the mutants and each one's exit code and failing assertion.

## Sources

There is no upstream implementation of this glue. The closest maintained tools were checked on 2026-09-29 and not
adopted: osquery (`specs/linux/systemd_units.table` has no `MainPID` or `NRestarts` column and `specs/hash.table` covers
files, and it needs the osquery binary), AIDE (a file-integrity hash database) and Ansible or InSpec (frameworks that check
declared state). None reads `claude`, `codex` or `qmd`, derives values from a settings file, digests a gateway answer or
carries the redaction rules above. Each rule follows its own source:

- The #381 [README "Procedure"](../../evidence/artifacts/token-adoption-e2e-20260926/README.md) and
  [RUNBOOK freeze rules](../../evidence/artifacts/token-adoption-e2e-20260926/RUNBOOK.md) in this repository: the frozen
  list and the rule that nothing changes while a run window is open.
- [`systemctl show`](https://www.freedesktop.org/software/systemd/man/255/systemctl.html) (systemd 255: "To select
  specific properties to show, use `--property=`. This command is intended to be used whenever computer-parsable output
  is required"), and the configuration flag each default unit's own binary lists in its `--help` (otelcol `--config`,
  Loki `-config.file`, Prometheus `--config.file`, Grafana `server --config`), read on 2026-09-29.
- [git](https://git-scm.com/docs/git) `--no-optional-locks` ("Do not perform optional operations that require locks") and
  [git-status](https://git-scm.com/docs/git-status) `--porcelain --untracked-files=no`.
- The [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference) for the probe flags: `--no-session-persistence`
  ("Disable session persistence so sessions are not saved to disk and cannot be resumed. Print mode only") and
  `--setting-sources` ("Comma-separated list of setting sources to load (user, project, local)"), with `--output-format`,
  `--verbose` and `--model`.
- [proc_meminfo(5)](https://man7.org/linux/man-pages/man5/proc_meminfo.5.html): `MemAvailable` ("An estimate of how much
  memory is available for starting new applications, without swapping").
- Output shapes read on 2026-09-29 and kept as fixtures in `tests/test_freeze_snapshot.py`: `claude mcp list` and
  `claude -p ... --output-format json` (claude 2.1.284), `qmd status` (qmd 2.8.3, whose `Documents` block prints the
  Orphaned and Pending lines only above zero), `scripts/adoption_status.py --client-wiring --json`,
  `--pinned-versions --json` and `scripts/codex_quota.py --json` (this repository), and the tools' `--version` lines.
  `claude mcp list` has no documented machine-readable form, and the Agent SDK reference documents `RateLimitInfo` without
  `unifiedWindows`, so both shapes are observed, not specified.
