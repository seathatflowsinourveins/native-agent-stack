# Bootstrap integrity: socraticode's ignore_scripts and headroom's pinned wheel (2026-09-26)

Retained evidence for the `adoption/bootstrap-linux.sh` fix of the two #299 review findings:

1. socraticode's Linux pin sets `ignore_scripts: true`, but `install_pin` never read the field and
   `install_npm` never passed `--ignore-scripts`, so npm ran every install script in the package's
   dependency tree;
2. headroom's pin names a wheel `url` and `sha256` that `install_uv_tool` never read: uv resolved
   `headroom-ai[mcp]==0.37.0` from its index, so a wrong pinned hash still installed.

The fixed script reads `ignore_scripts` as `adoption/bootstrap-macos.sh` does, and for a uv-tool pin
whose `url` is a wheel it checks the filename's version against the pin, downloads the wheel with
`fetch()` (sha256 verified, exit 1 on a mismatch before uv runs) and installs it as
`<package> @ file://<path>`, each path segment percent-encoded with jq's `@uri`.

## Evidence class and provenance

- **The change's acceptance is `local_integration` by nature.** The change under test is this
  repository's own `adoption/bootstrap-linux.sh`. No upstream project owns a test or an end-to-end
  check of that script, so no upstream E2E exists to run for it, and none is claimed. Its acceptance
  rests on the end-to-end scenarios below, which run it against the real pinned upstream artifacts
  with two discriminating controls (fixed-bad-hash and head-bad-hash).
- **Upstream tests of the two installed tools: not run, so unverified.** Neither installed package
  ships its test suite; both suites run only from a repository checkout
  ([Upstream-owned checks](#upstream-owned-checks-upstream-checkstxt)).
- **Upstream-owned operations of the two tools: run.** After a pinned install by the fixed script,
  the cheapest upstream-owned checks that run offline ran in a network namespace: headroom's own
  `headroom evals adversarial`, twice, and socraticode's documented MCP stdio launch answering
  `initialize` and `tools/list`, with a failing control (`upstream-checks.txt`). These fall in the
  "upstream example or native operation" class of `docs/acceptance-evidence-policy.md`. They show
  that the installed tools run. They cannot tell the fixed script's install from HEAD's, so they do
  not accept the script change.

Everything else here is `local_integration`: self-written drivers ([`drivers/`](drivers/)) run on the
workstation `nativestack-5975wx-20260925` (WSL2, Ubuntu 24.04.5, x86_64) on 2026-09-26. It is not CI
and not an upstream test suite. The end-to-end runs and the upstream checks use the real network and
the real pinned upstream artifacts; the uv form trials and the new unit tests use locally built
fixtures.

- Times: the six recorded bootstrap runs ran from 04:52:31Z to 04:53:19Z (their own start and end
  lines in `e2e-check.txt`). `uv-forms.txt`, `lint-and-tests.txt` and `checker-runs/` hold no times
  of their own; the modification times of their scratch originals, which are not published, fall
  between 04:50Z and 05:23Z. `upstream-checks.txt` and `work-guard-tests.txt` record their own start
  and end times and exit statuses, between 10:03Z and 10:05Z.
- Checkout: `origin/main` at `5c1961e49b89dd56ef5626950a5448735caabe4c` plus this change's working
  tree. The fixed `adoption/bootstrap-linux.sh` has sha256
  `eb68717b4bf3f95bdfbba40c12a342d939ba4388dca7fd1584e7c90d9d423135`; HEAD's copy
  (`git show HEAD:adoption/bootstrap-linux.sh`) has
  `458fb9c4329d54ca206ceda75d2d2a7d063a7b707897af0857e2a890930ef456`. The pins file the runs used
  has sha256 `af8a2486915d911ea2430150e57278e54d53715bf43d2316d8e40e86760ed339`, and its copy with
  headroom's sha256 set to 64 zeros has `07daebf5b6e843d9598c8c1ce00891a3a38a2b2c7bd96ac29eaf4a32d3df849e`.
- Tools: the end-to-end runs, the native probe, the uv form trials and the upstream checks used the
  uv 0.12.17, node 24.21.0 (with its bundled npm) and gh 2.101.0 that each install put in place from
  their verified tarballs. The optional real-uv and real-npm unit tests executed this host's own
  installs of the same pinned uv and node under `~/.local/share/codex-ecosystem`. jq 1.7, GNU bash
  5.2.21, ShellCheck 0.11.0, util-linux 2.39.3 (`unshare`) and Python 3.13.15 came from the host.
- Isolation: each bootstrap ran from a scratch checkout skeleton with a one-profile
  `adoption/manifest.json`, with its own scratch `HOME`, XDG directories, `ECO_INSTALL_ROOT`, npm
  cache and empty npm user config, and with `UV_NO_CONFIG=1` and `UV_PYTHON_DOWNLOADS=never`. uv found
  the host's uv-managed CPython 3.13.15 through `PATH` and only read it; the scratch `HOME` of the
  pass run was still empty afterwards. One uv cache was shared by the six recorded runs. Every
  upstream operation and help text in `upstream-checks.txt` ran in a new network namespace
  (`unshare --map-current-user --net`) whose only interface, `lo`, is down, with `HOME`, the XDG
  directories and `TMPDIR` under its work directory.
- Sanitization: each scratch work directory is printed as `<work>`, and the checkout as `<tree>` in
  `upstream-checks.txt` and `work-guard-tests.txt`. In `work-guard-tests.txt` the tests' temporary
  directories are `<tmp>` and the upstream checks' work directory is `<upstream-checks work>`. A test's
  failure message keeps only the tail of a driver's output, which can begin inside a path; such a path
  keeps its last segments, such as the last characters of a test's random temporary-directory name.
  Nothing else was changed.

## Files

| File | What it holds |
| --- | --- |
| [`e2e-check.txt`](e2e-check.txt) | The as-run `drivers/e2e.sh` output (script and pins hashes, start and end times, exit codes), then `drivers/check.py`'s checks over the same work directory, including `drivers/native_probe.cjs` |
| [`bootstrap-runs.log`](bootstrap-runs.log) | The six bootstrap runs' own stdout and stderr, in run order |
| [`uv-forms.txt`](uv-forms.txt) | The as-run `drivers/uv_forms.sh`: 22 offline `uv tool install` trials of the direct-reference forms |
| [`lint-and-tests.txt`](lint-and-tests.txt) | `bash -n` and ShellCheck on both scripts, red checks of the 14 new tests, the green module run, a bash 3.2.57 run and the adoption test modules |
| [`checker-runs/`](checker-runs/) | The outputs of `check.py` runs 2, 3 and 4 (`run-2.txt`, `run-3.txt`, `run-4.txt`); see [Checker runs](#checker-runs-and-what-was-not-retained) |
| [`upstream-checks.txt`](upstream-checks.txt) | `drivers/upstream_checks.sh`: a fresh install by the fixed script; what the installed packages hold and which of their checks apply offline; headroom's `evals adversarial` twice; socraticode's MCP `initialize` and `tools/list` with its own log, and a control. Every run of an installed tool after the install was in a network namespace |
| [`work-guard-tests.txt`](work-guard-tests.txt) | Lint of the drivers; `tests/test_bootstrap_integrity_drivers.py` red against the as-run drivers, red against the guard's first revision (with the diff that fixed it) and green; then the guarded `e2e.sh` (checked by `check.py`) and `uv_forms.sh` rerun and compared with `e2e-check.txt` and `uv-forms.txt` |
| [`drivers/`](drivers/) | `check.py` and `native_probe.cjs` as run; `bootstrap_once.sh`, `e2e.sh` and `uv_forms.sh` with the WORK guard of `work_guard.sh`, added after the recorded runs; `upstream_checks.sh` and `mcp_list_tools.mjs`, which produced `upstream-checks.txt` |
| [`drivers/as-run/`](drivers/as-run/) | `bootstrap_once.sh`, `e2e.sh` and `uv_forms.sh` byte-for-byte as run. They are the record, not for running (mode 0644) |

**The WORK guard.** The shell drivers delete and rewrite paths under the WORK directory they are
given. As run, `e2e.sh` and `uv_forms.sh` began with `rm -rf` on WORK, and `bootstrap_once.sh`
deleted its root, home and npm-cache paths under WORK, so an existing checkout or home directory
passed as WORK would have been destroyed. The four shell drivers in `drivers/` now source
`work_guard.sh` and call its `claim_work` before anything else, each with `|| exit 2`. `claim_work`
accepts only a WORK that does not exist, is an empty directory, or holds the
`.bootstrap-integrity-work` marker file that each driver writes into a WORK it creates. Anything else
ends the driver with exit status 2 before it deletes, downloads or writes anything: a non-empty
directory without the marker, a symbolic link, a file, a directory that cannot be listed, and a WORK
that begins with `-`, which `rm`, `mkdir` and `find` would read as an option. A driver copied without
`work_guard.sh`, or beside one that defines no `claim_work`, exits 2 as well. `check.py` has no guard.
The only path it deletes is an existing `WORK/probe-scratch`, which it then recreates for its probe,
and it gets there only after reading files that `e2e.sh` writes into WORK, starting with
`WORK/pass.log`; in a WORK without them it stops with `FileNotFoundError` first.

The guard's first revision had three holes. A driver copied without `work_guard.sh` carried on past
the failed `.` to its `rm -rf WORK`, because bash outside POSIX mode does not stop a script when `.`
fails. A WORK named
`-delete` made `claim_work` run `find -delete …` in the current directory, which deleted a file
there. A non-empty directory named `!` read as empty, because `find` takes a lone `!` as part of its
expression; the guard now lists a relative WORK as `./WORK`. In `work-guard-tests.txt` the new tests
fail on that revision (red 2) and pass on this one.

`e2e-check.txt`, `bootstrap-runs.log` and `uv-forms.txt` came from the as-run drivers, kept
byte-for-byte in `drivers/as-run/`, and `checker-runs/` came from `check.py` over their work
directory:

| As-run driver | sha256 |
| --- | --- |
| `bootstrap_once.sh` | `867f4f163571bc94b3c35c36e21315b436fbfa2ca62917ec0cf3c7e738464cf0` |
| `e2e.sh` | `6324b2d6cffacd018b91325a6f59b46b5fe86a9bbf9d2c9f6703dc7b5d458314` |
| `uv_forms.sh` | `706260004cdbab2bde23d30e1bc39e422cb7c8876dea38a4611399a72cefe701` |

Each guarded driver is its as-run original plus inserted guard lines, and nothing else changed.
`tests/test_bootstrap_integrity_drivers.py` checks that, the guard itself, each driver's refusal and
each driver's refusal without a working guard. The guarded drivers reproduce the recorded outputs
apart from timings and the fixture wheel's hash
([Guard tests and guarded reruns](#guard-tests-and-guarded-reruns-work-guard-teststxt)).

**Reading `e2e-check.txt`:** the negative checks print their label followed by the raw `exists()`
value, so `PASS no headroom tool environment: False` means the environment does not exist, which is
what the check requires.

## Results

The end-to-end scenarios (`e2e-check.txt`, `bootstrap-runs.log`):

- **pass** (fixed script, the checkout's pins, profile {headroom, socraticode}): exit 0, and the
  version report ends `summary: 5 verified, 0 failed`. The downloaded wheel's sha256 equals the pin.
  uv's receipt records `{name = "headroom-ai", extras = ["mcp"], path = <that wheel>}`, and
  `direct_url.json` names the wheel's file URL. The tool environment reports headroom-ai 0.37.0 and
  mcp 1.30.0 (the `[mcp]` extra), and all 547 hashed RECORD entries of the wheel match the installed
  files (`check.py` skips RECORD entries that carry no hash, such as RECORD itself).
  The upstream `headroom --version` prints `headroom, version 0.37.0`, and `npm ls` of the prefix
  shows `socraticode@1.14.0`. npm's own debug log shows it received `--ignore-scripts` and ran no
  lifecycle script (0 `info run` lines). Of the 187 installed packages, 18 declare install scripts:
  16 `@ast-grep/lang-*` postinstalls, `@parcel/watcher` and `tree-sitter-gdscript`. All 18 still
  work natively under the pinned node:
  - the 16 grammars register in one `registerDynamicLanguage` batch with socraticode's own
    `@ast-grep/napi`, as socraticode's `ensureDynamicLanguages` does, and each then parses a
    snippet with 0 `ERROR` nodes from its `prebuilds/prebuild-Linux-X64/parser.so`;
  - socraticode's own `dist/services/gdscript-preflight.cjs` prints
    `PREFLIGHT: OK node_modules/tree-sitter-gdscript/prebuilds/linux-x64/tree-sitter-gdscript.node`;
  - `@parcel/watcher` subscribes to a scratch directory and unsubscribes through its native binding.

  The control shows the grammar check loads the library rather than looking up a path. A copy of
  `@ast-grep/lang-bash` whose `parser.so` is cut to 64 bytes is refused: the child process aborts
  with `OpenLib(DlOpen { … cannot read file data })`. The gdscript and watcher checks have no such
  control (see [Limits](#limits)).
- **fixed-bad-hash** (fixed script, headroom's pinned sha256 set to 64 zeros): exit 1 with
  `Checksum mismatch: <the wheel url>`. No headroom tool environment was created, no verified wheel
  was left in `downloads/`, and no `Installed headroom` line was printed.
- **head-bad-hash** (HEAD's script, the same zeroed pins, profile {headroom, socraticode}): exit 0.
  HEAD's script installed headroom although the pinned hash is wrong, never downloaded the wheel, and
  its receipt records `specifier = "==0.37.0"` (an index install). npm received no
  `--ignore-scripts` and ran 18 install scripts (18 `info run` lines). npm's own
  `warn install-scripts` block lists the same 18 packages.
- **transition** (one install root, profile {headroom}): HEAD's script installed headroom-ai from the
  index. The fixed script then printed `Uninstalled 1 package` and
  `+ headroom-ai==0.37.0 (from file://…/downloads/headroom_ai-0.37.0-cp310-abi3-manylinux_2_28_x86_64.whl)`.
  A second fixed run printed `… is already installed`, and the final receipt records the wheel's path.

The uv form trials (`uv-forms.txt`) use the pinned uv 0.12.17 against 10 install-root names:

- The bare-path form `<package> @ /abs/path.whl` fails for 4 of the 10:
  - `eco#1` exits 1 with `Distribution not found at: file://…/eco#1/…`;
  - `eco ;1` exits 2 with `Failed to parse … Expected a quoted string or a valid marker name`;
  - `eco #1` and `eco #1 ;%é` each exit 1 with `Distribution not found at: file://…/eco`.
- The percent-encoded `file://` form installs from all 10 roots. Each receipt records the decoded
  path, and each repeated install reports `is already installed`.
- An unencoded `file://` URL fails for `eco#1`.
- uv still refuses a package name that the wheel's filename does not carry
  (``Requested package name `demo` does not match `demo-tool` in the distribution filename``).

Lint and tests (`lint-and-tests.txt`):

- `bash -n` and ShellCheck 0.11.0 both return 0 on the fixed script and on HEAD's.
- Against HEAD's script, 8 of the 11 new behaviour tests fail (7 failures and 1 error). The 3 new
  pins-data tests pass, and so do the 3 behaviour tests that pin unchanged behaviour: npm without the
  flag, the sdist index path, and the real npm control.
- Against a variant that keeps the bare-path form, 4 fail: the file-URL argv, the encoded install
  root, and both real-uv tests.
- The whole module passes: `Ran 72 tests`, `OK`, with no skips on this host.
- The 11 new `install_pin` tests also pass with bash 3.2.57 first on `PATH`.
- The 10 adoption test modules on this change's code and documents:
  - `Ran 446 tests`, `OK (skipped=16)` by default;
  - `OK (skipped=1)` with ShellCheck and a bash 3.2.57 binary (`BASH32_BINARY`);
  - the ShellCheck-gated macOS, launchd and guarded-runner modules alone: `Ran 225 tests`, `OK`.

### Upstream-owned checks (`upstream-checks.txt`)

`drivers/upstream_checks.sh` ran from 10:03:13Z to 10:03:39Z and exited 0. Near its start the record
gives the sha256 of the driver, `mcp_list_tools.mjs`, `bootstrap_once.sh` and `work_guard.sh`, which
equal the published files. The fixed script (sha256 `eb68717b…`, the same pins) installed profile
{headroom, socraticode} afresh over the network: exit 0 and `summary: 5 verified, 0 failed`, and
npm's own debug log shows `--ignore-scripts` in the install argv and 0 `info run` lines. Everything
after the install that runs an installed tool ran in the network namespace, where a TCP connect to
1.1.1.1:443 fails with `ENETUNREACH`.

Which upstream checks apply offline, from the installed packages' own files and help texts (all
printed in the record):

- **headroom-ai 0.37.0** ships no test suite. The wheel has 548 entries, and the only ones whose paths
  look like tests are `headroom/testing/README.md`, `__init__.py` and `harness.py`. Its README gives
  `uv sync --extra dev && uv run pytest`, which needs a repository checkout.
  `headroom evals adversarial --help` says "Offline and deterministic - no LLM, no API key, no model
  download". The other candidates do not apply to an offline fresh install. `headroom evals probes` requires recordings
  from a proxy run with `HEADROOM_PROBE_RECORD_DIR`. `headroom doctor` checks "that the Headroom proxy
  and client routing are working" and exits 2 when the proxy is down. The README's benchmark
  reproduction `python -m headroom.evals suite --tier 1` calls a model: `--model` defaults to
  `gpt-4o-mini`, and the help prices tier 1 at about $3.
- **socraticode 1.14.0** ships no tests either. The `files` of its `package.json` are `dist`,
  `.claude-plugin`, `skills`, `agents`, `hooks`, `.mcp.json`, the licences, the README and a logo.
  Its test scripts run vitest in a repository checkout (`vitest run`, and `vitest run` over
  `tests/unit/`, `tests/integration/` and `tests/e2e/`), and the package ships no `tests/`. Its README
  configures MCP clients to start the package as a server command
  (`npx -y --prefer-online socraticode@latest`, or `node /absolute/path/to/socraticode/dist/index.js`).
  Its documented health check, the `codebase_health` MCP tool, runs `docker info` and checks Qdrant and
  the embedding provider, and `codebase_about` includes an infrastructure status summary. Neither was
  called (see [Limits](#limits)).

The two operations:

- **headroom 0.37.0:** `headroom evals adversarial` exited 0 in both runs. Each printed the same
  compression-robustness grid, 7 payload classes of 30 cells over 10 carriers at 3 positions, with
  one line `FLAG fake_system_tag: suppressed compression of its carrier in 15 cell(s) (possible
  compression immunity)`, and on stderr `Native content detection requires ONNX Runtime 1.24+; using
  pure-Python detection for this process.` The two JSON reports are byte-identical (sha256
  `127ceb9c3d96c4299126dfe7203e7da6a9aea15900561bba78159c6a699268ad`, 67,373 bytes). The grid is
  headroom's own measurement of its compressor, not a pass or a fail.
- **socraticode 1.14.0:** its installed `socraticode` bin, started over stdio through the MCP
  TypeScript SDK 1.30.1 from socraticode's own dependency tree (`drivers/mcp_list_tools.mjs`), answered
  `initialize` as `socraticode 1.14.0` and `tools/list` with 26 tools: the 26 `codebase_*` names in
  the installed README's tool tables, none missing and none extra. It wrote nothing to stderr. Its
  own log, written to a file through `SOCRATICODE_LOG_FILE`, records
  `Auto-resume: disabled by SOCRATICODE_AUTO_RESUME=off` and then its graceful shutdown on stdin EOF.
  The driver sets that variable, and `dist/services/startup.js` checks it before its Docker and Qdrant
  checks (the record prints those lines). The control, the same client with a node process that exits
  at once as its server, fails with `MCP error -32000: Connection closed` (exit 1).

Neither operation tells the fixed script's install from HEAD's. They show that the pinned wheel's
headroom runs its own evaluation and that socraticode, installed without its 18 install scripts,
starts and serves its tools. They say nothing about the hash check.

### Guard tests and guarded reruns (`work-guard-tests.txt`)

One scratch script produced this record, and `upstream-checks.txt`, from 10:03Z to 10:05Z. In order:

- ShellCheck 0.11.0 (`-x`) and `bash -n` on `work_guard.sh` and the four shell drivers, and
  `node --check` on `mcp_list_tools.mjs`: every one exits 0.
- Red 1, in a scratch copy of this change's tree with the three as-run drivers in place of the guarded
  ones: `Ran 11 tests`, `FAILED (failures=15)`. The as-run drivers do not refuse a WORK they did not
  create, with or without a guard file beside them, and they lack the guard lines.
- The diff from the guard's first revision to this one, then red 2, with that revision in place:
  `Ran 11 tests`, `FAILED (failures=18)`. Among the failures are the three cases the revision got
  wrong (`-delete` deletes the file beside WORK; `-new` and `!` are accepted) and all 8 cases of a
  driver with a missing or empty guard file.
- Green, on this change's tree: `Ran 11 tests`, `OK`.
- The guarded `e2e.sh`, over a new work directory, gave the six scenarios the recorded exit codes
  (0, 1, 0, 0, 0, 0), and `check.py` over it reported `0 check(s) failed`. Its output differs from
  the `check.py` part of `e2e-check.txt` only in uv's millisecond timings, on 8 lines.
- The guarded `uv_forms.sh`, with the uv 0.12.17 of the upstream checks' install, reproduced
  `uv-forms.txt` line for line apart from the fixture wheel's sha256, which changes with every build:
  `ZipFile.writestr` with a name stamps each entry with the current time.

## Why the percent-encoded file URL

The PyPA dependency specifier grammar gives a direct reference as
`urlspec = '@' wsp* <URI_reference>`, with the URI as RFC 3986 defines it, and it gives
`url_req = name wsp* extras? wsp* urlspec (wsp+ quoted_marker?)?` with
`quoted_marker = ';' wsp* marker`. The source is `source/specifications/dependency-specifiers.rst`
in pypa/packaging.python.org at `3200c49f0ba03f5973a6655cf2e9a9631caa1d2f`. So in a bare path, an
unescaped `#` starts a URI fragment, and whitespace followed by `;` starts an environment marker.
Those are the two failures the bare form shows above. uv's own documentation at the pinned tag
(`docs/pip/packages.md` in astral-sh/uv `0.12.17`, commit
`635500036e1705961315e86447f0fab0a8ddb309`) shows the local form `uv pip install "ruff @ ./projects/ruff"`.
The file URL keeps that form's name and extras check (the last trial above) without those
delimiters.

## Checker runs, and what was not retained

`drivers/check.py` ran five times over the one work directory of the recorded end-to-end runs, which
were not repeated for it. `check.py` was edited in place between runs, so only the fifth run's
revision is kept (`drivers/check.py`, with `drivers/native_probe.cjs`); the revisions behind runs 1
to 4 are not.

**Not retained: the two failed attempts.** Neither the command nor the output of either failed
attempt was kept: the first `check.py` run, which reported 2 FAIL lines, and the first trial of
`native_probe.cjs`, run in-process, which ended with exit 134. The code revisions they ran were not
kept either. A search of this change's scratch directories on 2026-09-26 found no copy of either
output. Items 1 and 4 below therefore describe them from the author's account, not from a record.
The outputs of runs 2, 3 and 4 are in `checker-runs/`, and the fifth run's is the `check.py` part of
`e2e-check.txt`.

1. The first run reported 2 FAIL lines, `version report (headroom)` and
   `version report (socraticode)`. The cause was the checker's own parser, which looked for a
   `<id> --` block prefix where `installed-versions.txt` writes `<id> <version>: …`.
2. After that fix, the second run reported `0 check(s) failed`
   ([`checker-runs/run-2.txt`](checker-runs/run-2.txt)).
3. The third run added a load check for the 18 packages whose install scripts npm skipped. It
   reported `0 check(s) failed`, but for the 16 grammars it only read `libraryPath`
   ([`checker-runs/run-3.txt`](checker-runs/run-3.txt), its 16 `INFO … libraryPath` lines). That
   getter checks that the prebuilt `parser.so` exists and never loads it. An independent read-only
   Codex review of this change found the gap.
4. `drivers/native_probe.cjs` replaced that check. Its first direct trial passed all 18 packages,
   but its in-process control killed node with exit 134: `@ast-grep/napi` panics on the failed
   `dlopen` instead of throwing. The control therefore runs in a child process. With that probe,
   the fourth run of `check.py` reported `0 check(s) failed`
   ([`checker-runs/run-4.txt`](checker-runs/run-4.txt)).
5. The fifth run, after an edit to `check.py`'s docstring, printed output byte-identical to the
   fourth's. It is the part of `e2e-check.txt` after its `----- check.py` line.

## Runs not published

These runs on this host on 2026-09-26 are not published:

- From 06:40Z to 06:51Z, with the guard's first revision: two runs of `upstream_checks.sh` (the
  driver was edited in place after the first to add its npm debug-log lines, and was changed again
  afterwards), one guarded rerun of `e2e.sh` with `check.py` and of `uv_forms.sh`, and a red and a
  green run of the first revision of the guard tests.
- From 09:50Z to 09:53Z: one trial run each of the final `upstream_checks.sh`, `e2e.sh` with
  `check.py`, and `uv_forms.sh`.
- From 09:55Z to 10:02Z: three runs of the script that produced `upstream-checks.txt` and
  `work-guard-tests.txt`. The first stopped at its own check for host paths, because a test's failure
  message had cut a path mid-string. After each of the three, the new tests or the script's
  sanitizing changed. A refusal's failure message now keeps 400 characters of the driver's output
  instead of 1500, and a missing guard line no longer prints the driver's whole text. Each case of the
  syntax test now gets its own directory: on the first revision, two of its cases had failed only
  because an earlier case had deleted a file they compared. The sanitizing now keeps `TMPDIR=`. The
  fourth run of that script, from 10:03Z to 10:05Z, produced both published records.

## Limits

- No unchanged upstream test suite ran, so the two tools' upstream tests are unverified here.
  Neither installed package ships its suite; both suites run only from a repository checkout (see
  [Upstream-owned checks](#upstream-owned-checks-upstream-checkstxt)).
- The upstream checks are one published run on this host, in a network namespace. They do not run
  headroom's proxy or MCP server, or socraticode's indexing, search and graph tools, and they cannot
  tell the fixed script's install from HEAD's. `codebase_health` and `codebase_about` were not
  called: offline they can only report that Docker, Qdrant and the embedding provider are missing,
  and on a host with Docker they would query its daemon, whose Unix socket a network namespace does
  not isolate.
- This is one Linux host with glibc. musl and glibc older than 2.28 were not tried; the pinned wheel
  is `manylinux_2_28_x86_64`.
- Only the headroom wheel is hash-verified. The other 72 of the 73 packages uv resolves come from
  its index without hash pinning.
- uv's receipt records the wheel's path under `ECO_INSTALL_ROOT/downloads`. Deleting that file
  breaks `uv tool upgrade` or a reinstall until the bootstrap fetches the wheel again.
- A host whose bootstrap installed socraticode from `v2026.09.26`, or from `main` between #299 and
  this change, ran those 18 install scripts, and nothing here revisits such an install. A headroom
  that came from the index is replaced on the next fixed run, as the transition shows.
- CI's `bootstrap-linux` job installs only the `foundation-cpu` profile, and the optional real-uv
  and real-npm tests skip where no pinned uv or node is installed. On this host they ran.
- The native checks parse one snippet per grammar. They do not index a project or exercise a whole
  grammar; socraticode's MCP server was only started and asked for its tools (`upstream-checks.txt`).
- Only the grammar check has a failing control (the cut `parser.so`). The gdscript preflight and the
  `@parcel/watcher` subscription have none, so those two passes were never shown to be able to fail.
- `lint-and-tests.txt` records its checks' results and unittest summaries, but not their exact
  argument vectors, working directories or times. `uv-forms.txt` and `checker-runs/` record no times
  either (see Times above).
- The WORK guard covers WORK only. `bootstrap_once.sh` does not check its LABEL, which it uses in
  paths under WORK, or its ECO and UV_CACHE paths. `e2e.sh` and `upstream_checks.sh` pass fixed
  labels and paths under WORK; a hand-run call with an ECO outside WORK installs into that ECO.
- These are install-stage observations plus the two upstream operations. They are not a `use`
  receipt for headroom or socraticode.
