# Native token CI extension: local runs (2026-09-26)

Local evidence for the six tools added to
[`scripts/native_token_ci.py`](../../../scripts/native_token_ci.py) on 2026-09-26
(MarkItDown, ast-grep, ccusage, codebase-memory-mcp, Headroom and jCodeMunch, with a
pinned MCPorter bridge). Host: `nativestack-5975wx-20260925` (WSL2, x86_64, CPU only).

**Evidence class: local integration evidence of upstream native operations.** Each
fixture runs the pinned tool's own CLI or MCP commands, and this repository's checks
assert on what they return, so every receipt labels itself `local_integration`. The one
upstream test in the harness is `rtk verify --require-all`: the inline tests of RTK's
built-in TOML filters, compiled into its release binary (154 of 154 passed in each run
below). No other pinned tool documents an offline self-test command; `runs.json`
`upstream_self_test_survey` lists what was checked. Upstream test-suite qualification of
a component belongs in its per-host receipts,
`evidence/hosts/<host>/<host>--<component>--<stage>--<date>.json`, recorded with
[`scripts/host_receipts.py`](../../../scripts/host_receipts.py) and summarized in
[the component evidence matrix](../../../docs/component-evidence-matrix.md). The
receipts recorded so far for these eleven tools run install and use commands, not
upstream suites. The controls driver and both wrappers here are this repository's own
scripts, and ccusage reads a committed synthetic usage log. None of this is a hosted
GitHub Actions result; the workflow's first hosted run for this change is a separate
record.

| File | What it is |
| --- | --- |
| [`runs.json`](runs.json) | Every run, control and check below, with hashes |
| [`final-harness-run-1.receipt.json`](final-harness-run-1.receipt.json), [`final-harness-run-2.receipt.json`](final-harness-run-2.receipt.json) | The final harness's own receipts, unchanged |
| [`controls.json`](controls.json) | The controls driver's own report, unchanged |
| [`controls_driver.py`](controls_driver.py) | The driver that ran the controls |
| [`clean_env_run.sh`](clean_env_run.sh) | The wrapper that started the final runs and the controls; every location is an argument |
| [`local-install-run-1.receipt.json`](local-install-run-1.receipt.json), [`local-install-run-2.receipt.json`](local-install-run-2.receipt.json) | Receipts of the two passing runs of the pre-polish harness, with one key reshaped (see below) |
| [`pre-polish-native_token_ci.py`](pre-polish-native_token_ci.py) | That pre-polish harness, byte for byte (sha256 `3cec918f…`) |
| [`install_run.sh`](install_run.sh) | The wrapper that started the pre-polish runs, kept unchanged; it does not run from this directory |

## Final harness runs

Two consecutive `--install` runs of the final harness (sha256 `14212050…`), started by
`clean_env_run.sh`. The wrapper cleared the environment and used a `PATH` holding only
the Node 24 runtime and system directories. It refused to start if any measured tool,
MCPorter or uv resolved on that `PATH`, as on a fresh hosted runner. Each run got a new
empty `HOME` and a new empty `TMPDIR`. A third run of the same harness, minutes
earlier, had the same outcome and is recorded in `runs.json` without its receipt.

Each run: 83 commands, and 30 of 30 checks passed. Each receipt still says `failed`,
with one failure: codebase-memory-mcp. This round could write only inside the checkout
and one long session directory, so `TMPDIR` was 126 bytes long. codebase-memory-mcp's
rendezvous socket must fit a Unix socket address, which allows at most 36 bytes of
`TMPDIR` with a 4-digit uid. The harness's own `require_cbm_socket_fits` therefore
refused that fixture, as designed, after installation and the `--version` check but
before any other codebase-memory-mcp command.

So codebase-memory-mcp last ran in the pre-polish runs below. Between that harness and
the final one, the fixture, its helpers and constants, and every `Run` method it uses
are byte-identical. Only `Run.__init__` changed: its limits text, the `mcporter_error`
attribute and the `source_files` list. `runs.json` lists each of these definitions'
sha256 in both revisions, and a unit test recomputes the pre-polish digests from
[`pre-polish-native_token_ci.py`](pre-polish-native_token_ci.py).

The checks added or changed in the review repair round passed in both runs with the
real tools:

- `rtk-upstream-inline-filter-tests-pass`: `rtk verify --require-all` exited 0 and
  printed `154/154 tests passed`. Its hook-integrity step reads `$CLAUDE_CONFIG_DIR`,
  here the committed ccusage fixture directory, found no hook and skipped, so no client
  configuration was read.
- `headroom-compress-json-records-saves-tokens`: `headroom_compress` on
  [`fixtures/headroom-records.json`](../../../fixtures/headroom-records.json), a compact
  JSON array of 24 records (2,969 bytes), returned 511 tokens for 826 (315 saved,
  38.1%) through `router:smart_crusher:0.42`, with a changed text. SmartCrusher is
  Headroom's JSON compressor.
- `headroom-retrieve-exact-original-records`: `headroom_retrieve`, in a new server
  process, returned the original bytes exactly.
- `headroom-short-note-stored-unchanged`: the 49-token note, under the 250-token minimum
  of Headroom's `compress()`, came back unchanged (`router:noop`, 0 saved). This is the
  in-run negative control of the saving check. Every earlier run gave Headroom only this
  note, so none of them exercised compression.
- `jcodemunch-get-symbol-source-exact-content`: now compared with a frozen oracle, the
  symbol's identity, 1-based bounds and complete source in the harness
  (`JCODEMUNCH_SYMBOL`), which a unit test checks against Python's own parser. The
  earlier check sliced the expected text with the bounds the response reported, so an
  empty source at `line=end_line=999`, or the body line alone at `line=end_line=2`,
  passed.

The two checks rewritten in the polish pass passed too. ast-grep returned lines 9 and 13
of [`fixtures/ast_grep_calls.py`](../../../fixtures/ast_grep_calls.py), and grep's text
baseline returned lines 9, 16 and 17. jCodeMunch's own index file
(`local-wt-ws2b-f056036f.db`) was under `CODE_INDEX_PATH` and not under the server's
`HOME`.

Headroom counts tokens with tiktoken's `o200k_base` vocabulary, which tiktoken
downloaded into the run's `TMPDIR` on first use (`headroom-tiktoken-cache`: one file,
named after the SHA-1 of its URL). tiktoken checks the download against its own pinned
SHA-256. MarkItDown runs the ONNX file-type classifier bundled in its `magika`
dependency. No LLM or embedding model is used.

After each run, independently of the harness:

- the throwaway `HOME` and `TMPDIR` were empty;
- no process was left running from the run's directory;
- the checkout's `git status` was unchanged;
- the entry names in the account-default codebase-memory-mcp rendezvous
  (`/tmp/cbm-daemon-<uid>`) were unchanged.

Headroom's and jCodeMunch's MCP servers were started from the absolute path of the copy
just installed, shown as `<TOOL:headroom>` and `<TOOL:jcodemunch-mcp>` in each receipt's
`mcporter call --stdio` arguments.

## Discriminating controls

**Controls for the new checks** ([`controls.json`](controls.json)). The driver installs
MCPorter, RTK, Headroom, jCodeMunch, ccusage and MarkItDown once, with the harness's own
methods and pins. It then runs the harness's own fixture functions in fourteen arms under
the same wrapper. Every arm, and the installation, runs with a `HOME` inside its own work
directory; the caller's `HOME` is never passed to a tool. Each as-harness arm must pass.
Each control changes one setting or input and must fail exactly the check it targets.
All fourteen arms ended as expected. The wrapper's throwaway `HOME`, which stands in for
the caller's, was empty afterwards. The polish pass's controls run had left
`.headroom/ccr_store.db` and `session_stats.jsonl` in it.

| Check | Control | Observed |
| --- | --- | --- |
| `rtk-upstream-inline-filter-tests-pass` | A project filter whose one inline test expects the wrong output, added to the fixture repository just before `rtk verify` and trusted through RTK's CI override (`RTK_TRUST_PROJECT_FILTERS=1` while `CI` is set) | `rtk verify` printed `154/155 tests passed`, reported the failing test and exited 1, which fails the harness before the check parses the count |
| `headroom-compression-store-inside-run` | `HEADROOM_WORKSPACE_DIR` removed from the MCP server's environment | Failed; the store went to `.headroom` in the arm's own `HOME` |
| `headroom-compress-json-records-saves-tokens` | Compression disabled: in that arm's MCP server, Headroom's `compress()` becomes its documented `optimize=False` passthrough ("False = passthrough for A/B testing"), loaded as a `sitecustomize` module from the server's `PYTHONPATH`. Input, server and call are unchanged | Failed; the records came back unchanged, with 0 tokens and no transforms. The passthrough's marker shows it loaded in that arm and in neither other Headroom arm |
| `jcodemunch-index-inside-run` | `CODE_INDEX_PATH` removed from the MCP server's environment | Failed; the index was under the server `HOME`'s `.code-index`, and `CODE_INDEX_PATH` held only the harness's `config.jsonc`. The pre-polish check, "the directory is not empty", would have passed |
| `ccusage-synthetic-fixture-token-totals` | One `output_tokens` value 300 → 301 in a copy of the log | Failed; `outputTokens` 381, `totalTokens` 2431, cost unchanged |
| `ccusage-synthetic-fixture-cost-total` | One `costUSD` value 0.0271 → 0.0371 in a copy of the log | Failed; `totalCost` 0.0428, token totals unchanged |
| both ccusage checks | Empty `CLAUDE_CONFIG_DIR` | ccusage exited 1 ("No valid Claude data directories found") before either check |
| `markitdown-html-heading-present` | The fixture's `<h1>` turned into a `<p>` in a copy | Failed; no `# Local browser command check` line |
| `markitdown-txt-passthrough-unchanged` | The same plain text given as a `.csv` file | Failed; MarkItDown returned a Markdown table |

**Unit tests.** Against every file of this change as the polish pass left it (the new
fixture added), the final `tests/test_native_token_ci.py` fails 5 of its 26 tests: the
RTK upstream tests, the Headroom saving and recovery, the jCodeMunch source oracle, the
driver's `HOME` and the retained comparison. The jCodeMunch test reproduces the review's
finding: the earlier check accepted the empty and the body-only responses. Against the
final files, all 26 pass, on Python 3.13 and 3.12. `runs.json` lists each result.

**Secret scan.** gitleaks 8.30.1 with the repository's `.gitleaks.toml` reports two
`generic-api-key` findings in each unreshaped pre-polish receipt: the path-keyed hash
lines for `scripts/native_token_ci.py` and `.github/workflows/native-token-e2e.yml`. It
reports none in any file of this change. `runs.json` keeps per-definition digests as a
list of objects for the same reason.

**Earlier controls of this port.**

- **Bare server names.** The first draft passed MCPorter bare `--stdio` names. Run with no
  ambient copy on `PATH`, both of its MCP fixtures failed: `spawn headroom ENOENT` and
  `spawn jcodemunch-mcp ENOENT`. The unit test for this fails against that draft harness
  and passes against the final one.
- **Publication scan.** Two runs of an intermediate harness passed, but their receipts
  kept a run directory named `home/jcodemunch-mcp`, which `scripts/validate.py` rejects
  as a personal home path. The directory was renamed. A unit test fails against the old
  name and passes against the new one.

**Checks without a recorded failing control.** No failing run is recorded for
`codebase-memory-mcp-settings-and-rendezvous-inside-run` or
`codebase-memory-mcp-lists-only-the-fixture-project`. codebase-memory-mcp could not run
in the polish pass or this round, and the draft's runs predate both checks. A control
would point `CBM_CACHE_DIR` and `CBM_RUNTIME_DIR` at another run-owned directory, never
at the account-wide defaults. The remaining exact-content and status checks have no
separate failing run of the real tools, but each fixture's own negative control (a bogus
hash, the unchanged short note, a nonexistent symbol or call) runs beside them. The unit
tests fail the Headroom retrieval and jCodeMunch source checks on stand-in responses,
and the RTK check itself on failed, empty and zero-count outputs. `runs.json` lists
them.

## The workstation's default Headroom workspace

A Headroom control without `HEADROOM_WORKSPACE_DIR` writes `ccr_store.db`,
`session_stats.jsonl` and, when it saves tokens, `savings_events.jsonl` into
`~/.headroom` of whatever `HOME` it gets. The workstation's own `~/.headroom` was
inspected read-only on 2026-09-26 (names and times, no content):

- nothing there was created on 2026-09-26, and nothing changed after 02:33:08Z;
- every controls run, the polish pass's three and this round's two, went through
  `clean_env_run.sh` with a throwaway `HOME`, the first at 06:50:13Z, so the driver
  never wrote there, and nothing was removed.

The first draft's six `--install` runs that reached Headroom (01:51 to 02:32Z) had no
`HEADROOM_WORKSPACE_DIR` and kept the native `HOME`. The store and session statistics
there were last modified at 02:32:52Z, during the last of those runs. So the draft most
likely added entries to these pre-existing files. They belong to the workstation's own
Headroom and were left unchanged. `runs.json` lists every entry's times.

## Upstream behaviour the checks rely on

These were read in upstream artifacts: the jcodemunch-mcp 1.108.319 wheel (PyPI
sha256) and the MCPorter 0.14.1 package (npm sha1 and sha512), whose copies read in
earlier passes are byte-identical to them, and, in the repair round, the Headroom 0.37.0
wheel and sdist (PyPI sha256) and RTK's v0.50.0 tag source archive (sha256 in
`runs.json`).

- Headroom's `headroom_compress` runs `compress()` on the content as one tool message.
  `compress()` leaves content under `min_tokens_to_compress` (250) unchanged, and
  documents `optimize=False` as a passthrough. SmartCrusher compresses JSON arrays of
  objects.
- `rtk verify` runs RTK's inline filter tests; `--require-all` also fails when a filter
  has none. Without `--filter`, it first checks the hook at `$CLAUDE_CONFIG_DIR`, or
  `~/.claude`, and skips when none is installed.
- jCodeMunch keeps a repository's index at `{CODE_INDEX_PATH}/{owner}-{name}.db`, each
  part sanitized (`storage/sqlite_store.py`). The harness's `jcodemunch_index_file`
  reproduces that name.
- jCodeMunch sends its compact MUNCH text only when that is at least 15% smaller than
  the JSON (`encoding/gate.py`); otherwise it sends JSON text. Measured offline with its
  own encoder, the MUNCH form of the zero-result response every local run received was
  larger than the JSON (350 against 227 bytes). So was the MUNCH form of a minimal
  zero-result response (145 against 31). The text branch that the harness still accepts
  has never been observed.
- MCPorter's `--output json` prints JSON text as the parsed object, and falls back to the
  raw result, content list included, when nothing parses as JSON.

## Pre-polish runs

The port's two passing `--install` runs of the pre-polish harness (sha256 `3cec918f…`,
kept here as `pre-polish-native_token_ci.py`) had 89 commands and 36 of 36 checks each,
codebase-memory-mcp included, with `TMPDIR` unset. That harness wrote source hashes as a
map keyed by file path. gitleaks' `generic-api-key` rule reports that shape under the
repository's configuration. The committed receipts hold the same entries as the
`source_files` list of `{path, sha256}` objects that the final harness writes itself, at
the same position. Nothing else differs. `runs.json` records both hashes, and
`tests/test_native_token_ci.py` rebuilds the map and checks the original's hash.

`install_run.sh` is the wrapper that started these runs, kept unchanged. It hardcodes the
scratch layout it was written in (`../wt-ws2b` as the checkout and `../ci-venv` as the
interpreter) and writes its outputs next to itself. So it does not run from this
directory; `clean_env_run.sh` is the form that takes every location as an argument.

## Superseded runs

The review repair round superseded these runs, which `runs.json` keeps by hash:

- Its two final-harness runs (harness `02afd5b2…`, 28 of 28 checks each). That harness
  gave Headroom only the short note, took the jCodeMunch expected text from the
  response's own bounds, and ran no upstream test.
- Its controls run (eleven arms, all as expected). Its `HEADROOM_WORKSPACE_DIR` control
  let Headroom fall back to the caller's `HOME`, and it had no compression control.
- This round's first controls run (twelve arms, all as expected), before the driver
  gained the two RTK arms.

Six more `--install` runs by the port passed and are kept in `runs.json`, but they are
not the record:

- Two used an intermediate harness whose receipts kept `home/jcodemunch-mcp` (above).
- Two used harness `ab722d78…` while the checkout still carried the first draft's
  `timeout-minutes` edit to the workflow. `tests/test_workflow_hardening.py` pins that
  workflow's bytes to retained evidence, so the edit was reverted.
- Two used the same harness `ab722d78…` with the committed workflow. That harness, like
  the four runs before it, had renamed the report key `rtk_archive_sha256`, which the
  retained reproduction
  [`native_token_ci_rtk_only.py`](../sota-refresh-20260925/rtk/native_token_ci_rtk_only.py)
  reads. The key is back, with a unit test that fails without it, and a rerun of that
  reproduction printed the archive hash again. During the second of these runs the
  workstation's own codebase-memory-mcp daemon, started at 05:01:09Z, exited, and its
  entries left the account-default rendezvous; it did not belong to the run.

Three attempts of the polish pass are kept in `runs.json` with their reasons:

- An `--install` run of an intermediate harness. It had the same outcome as that pass's
  final runs, but the limits text and one comment changed after it.
- A first controls run with six arms. Its only ccusage control stopped at ccusage's exit
  before either check, and it had no MarkItDown arm.
- A second controls run with eleven arms, ten as expected. Its MarkItDown pass-through
  control gave the plain text as an `.html` file. MarkItDown's HTML conversion returned
  that text unchanged, so the check passed and the control did not discriminate. The
  control now uses a `.csv` file.

## Draft runs with the account-default codebase-memory-mcp state

The first draft left codebase-memory-mcp's cache and rendezvous at the account-wide
defaults, `~/.cache/codebase-memory-mcp` and `/tmp/cbm-daemon-<uid>`. The workstation's
own codebase-memory-mcp daemon listens in that rendezvous directory, and the endpoint
names inside it do not depend on the directory: each run-owned rendezvous held the same
names. So the draft's processes shared one endpoint with every other codebase-memory-mcp
process of the account. In the draft's six local `--install` runs, `index_repository`
failed three times with the upstream message "CBM daemon endpoint is held by pid N but
that process answered no rendezvous within 30000 ms". It passed in the other three
`--install` runs and in both runs that reused installed executables. Whether the process
holding the endpoint was the workstation's own daemon or one left by an earlier draft run
was not recorded.

That draft's `config set ui_enabled false` also rewrote the workstation's default
`~/.cache/codebase-memory-mcp/config.json`, which now reads `ui_enabled: false`. Its
earlier value was not recorded, and it was not changed back.

The harness now sets the documented `CBM_CACHE_DIR` and `CBM_RUNTIME_DIR`
([upstream configuration reference](https://github.com/DeusData/codebase-memory-mcp/blob/v0.11.0/docs/CONFIGURATION.md))
to directories inside each run. All eleven of the port's local `--install` runs with
that setting passed without a codebase-memory-mcp failure: three from an earlier pass,
whose `PATH` was not retained, the six superseded runs and the two pre-polish runs.
`runs.json` records the setting and `index_repository`'s exit for each. The cause of the
draft's three failures was not isolated beyond the shared endpoint, and eleven passing
runs do not establish a failure rate.

The draft's other failures are kept in `runs.json` as well: an ast-grep and grep count
mismatch, ast-grep's exit 1 on zero matches, jCodeMunch's JSON zero-result response
where the draft expected text, and, in the two runs that reused installed executables,
the installed MCPorter 0.14.1 against the draft's 0.13.13 pin.
