# AgentsView 0.44.0 qualification — 2026-09-27

**Hold the 0.43.0 pin.** The build's live release check on 2026-09-27 identified
v0.44.0 as the latest published stable release. Its official Linux amd64 asset passed the
published checksum check and several archive checks, but the complete
qualification procedure did not pass. No pin, production recipe, PATH, host
configuration or installed AgentsView archive changed.

This record follows the full-save plan's qualification steps 2–5. The host switch
(step 6) was outside the unit's scope. [qualification.json](qualification.json)
contains the gate decision, [native-checks.json](native-checks.json) the sanitized
observations, and [upstream-tests.json](upstream-tests.json) the distinct upstream
test attempts. [returned-output.txt](returned-output.txt) retains selected actual
returned lines; it is not a generated replacement for the failed test record.

## Source and installation

The candidate is [kenn-io/agentsview v0.44.0](https://github.com/kenn-io/agentsview/releases/tag/v0.44.0),
commit `413a87f7bfbd67b2815b1119ac51abc1efbeeaba`. The installed baseline reports
v0.43.0, commit `9be7745ad1906ee24e04eb05bb86c872ef0939a1`.

The release asset and SHA256SUMS were downloaded with upstream's GitHub release
channel into a new unit prefix, then extracted there. The archive SHA-256 is
`037ea7a46d52e06b20363b4aa7cd7f28e32f31d8215803d6e9a0c96bac5818e3`.
The verification used `sha256sum --ignore-missing --check SHA256SUMS`.
The [tagged installer](https://github.com/kenn-io/agentsview/blob/v0.44.0/scripts/install.sh)
documents the same release archive and checksum channel. No installer was allowed
to select a host bin directory.

Go 1.27.0 was installed into that prefix and verified against the
[official Go download digest](https://go.dev/dl/?mode=json&include=all), matching
the candidate's [go.mod](https://github.com/kenn-io/agentsview/blob/v0.44.0/go.mod).
Test commands used its explicit executable with isolated GOPATH/GOCACHE. The
upstream tracked source was unchanged.

## Evidence classes and results

| Evidence class | Observation | Limit |
| --- | --- | --- |
| Unchanged upstream tests | Coordinator broad runs outside the Codex sandbox: v0.44.0 passes 4,575 top-level tests; v0.43.0 passes 4,387; each skips 32, with zero failures across three packages. The original #1855 parser/DB selectors pass 4 top-level tests / 13 events; the coordinator's serve-runtime selector passes 5 more top-level tests. | Selected package scope; no full `./...`, frontend or cross-platform acceptance. Counts from overlapping runs are never summed. |
| Unchanged upstream tests, environmental failures preserved | The first runnable in-sandbox MCP/parser/DB attempt has 21 failing top-level parser tests, 25 failing events. The confirming subprocess run reports the same failures. | The coordinator controls discriminate the environmental failure; the confirming run's raw bytes were not retained, only its in-session summary. |
| Local integration over copied historical logs | Two exact authorized log copies, 381,416 bytes: one Claude session and one Codex session. Both pins preserve 2 inclusive sessions, 1 project and 2 bounded FTS hits. | No child sessions in these retained inputs; no new provider run. |
| Local integration, usage | Both pins' inclusive CLI totals agree with ccusage 20.0.24: 20,965 uncached input + 58,752 cache read + 556 output = 80,273 tokens. | Reasoning output 64 is a subset of output. No cost-parity claim. |
| Synthetic fixture | Five controlled populations, including both child types and an interactive control, are visible with all three inclusion flags. Expected automated counts: 0 at baseline, 2 at candidate. All 23 retained fixture files now have hashes in native-checks.json. | Hashes and explicit expectations were captured during repair, not prospectively before the trial. The local fixture's ccusage report is zero; fixture usage parity failed and remains recorded. |
| Local integration, port control | With an owned listener occupying 17384, baseline succeeds on 17385; candidate exits 1. The candidate gives an explicit choose-another-port diagnostic. | Only the owned scratch listeners and daemons were used. |
| Local measurement | One full sync over the same two copied logs: 0.407672 seconds on baseline; 0.358587 seconds on candidate. | Too small and unreplicated for an efficiency or throughput conclusion. |
| Provider execution / review | The only GPT-6 review activity is two Codex launches, each exit 1 before provider execution; both JSONL captures are empty and neither final-message target exists. The build session stopped the stalled Claude review with SIGINT, exit 130; usage is unknown. | Four fresh native lanes and both independent reviews remain unaccepted. |
| Structural validation | Repository unittests check receipt consistency and sanitization, including planted home-path, UUID and forbidden-key violations through the same publication checks. Since 2026-09-28 they also classify every tracked file outside the dated evidence paths that names the pinned version and reject a location list with any entry removed. | These checks establish no upstream or provider execution. |

The initial upstream test attempts failed to build because the generated pricing
snapshot was absent. The supported
[CI prerequisite](https://github.com/kenn-io/agentsview/blob/v0.44.0/.github/workflows/ci.yml#L233),
`go run ./internal/pricing/cmd/litellm-snapshot -restore`, resolved that build
prerequisite. Later parser failures were environmental: all 25 failed events
return project `tmp` where another name is expected, consistent with the Codex
sandbox's empty `/tmp/.git`. The interpreter's differing filesystem view did
not exclude that marker's effect on native subprocesses.

The coordinator ran the same unchanged broad command at both tags with Go
1.27.0, isolated GOPATH/GOCACHE, `GOTOOLCHAIN=local`, `GOTELEMETRY=off` and
`TMPDIR=/var/tmp/claude-w3-agentsview-go`, outside the Codex sandbox. Both pass;
both tracked checkouts were clean before and after. Its additional
`./cmd/agentsview -run 'TestPrepareRunServeRuntimeConfig|TestWaitForBackendReady'`
selection closes the original #1855 `serve_runtime_test.go` omission. Retained
JSONL hashes, first/last event times (14:04–14:09Z), stderr references and counts
are in [upstream-tests.json](upstream-tests.json). The repair recomputed those
hashes and counts; it did not rerun the upstream tests.

## MCP usage decision and required future recipe

Use inclusive `agentsview usage daily` and native ccusage over identical selected
source logs for accounting. MCP `get_usage_summary` cannot include automated
sessions: its [input type and request](https://github.com/kenn-io/agentsview/blob/v0.44.0/internal/mcp/tools.go#L705)
lack that option, whereas the [CLI filter](https://github.com/kenn-io/agentsview/blob/v0.44.0/cmd/agentsview/usage.go#L163)
includes them. On the two copied logs, candidate MCP returns zero Codex usage
while CLI and ccusage agree. The chosen accounting boundary accommodates this
known limitation; it does not fix the MCP tool.

A future qualifying pin PR must rewire the AgentsView block in `recipes/README.md#history-and-usage` and
the mirrored `install`, `install_note` and `use` entries in
`docs/token-efficiency-stack.json` (lines 1583–1591), the input to
`scripts/build_ecosystem.py`. The same PR must change every other location
under `repository_pin_locations.repin_targets` in
[qualification.json](qualification.json), including the `agentsview` install row
of the `recipes/README.md` component table. The recipe line range
has shifted from the plan's older range. Search/list intended to include workers must use
`--include-automated --include-one-shot --include-children`, preserving selected
source roots and the cwd allowlist. Sources:
[tagged command reference](https://github.com/kenn-io/agentsview/blob/v0.44.0/docs/commands.md)
and [#1855](https://github.com/kenn-io/agentsview/pull/1855).

Treat an occupied explicit port as a startup failure and stop dependent reads.
Choose another free explicit port or the supported `--port 0` deliberately.
The [tagged implementation](https://github.com/kenn-io/agentsview/blob/v0.44.0/cmd/agentsview/serve_runtime.go#L57)
makes this behavior intentional. Successful scratch recipe sequences used a
free explicit port; the occupied control used the recipe's literal 17384.

The native sync/serve/projects/search/usage/stop sequence was exercised against
both versions using isolated scratch data. The unchanged runner of the 2026-09-26
returned-results E2E (its `rr/agentsview/run.sh`, which the full-save plan's
qualification procedure designates) was not
executed: it hardcodes writable locations outside this unit and direct native
source roots. Its command sequence was adapted, not presented as unchanged
upstream tests.

## Dated corrections and residuals

The unit research log retains the failed setup/probe attempts. Corrections on
2026-09-27: the upstream installer is `scripts/install.sh`; unsupported provider
`homes`/`dirs` entries were removed before any successful sync; synthetic child
identities were corrected to the upstream layout; versioned capture filenames
now append extensions rather than replacing them. Attempt 3's overwritten raw
captures are not used as accepted evidence.

The platform pins files currently have no AgentsView entry. On 2026-09-28,
`git grep -n -I -E '0\.43\.0|v0\.43\.0'` over the tracked tree matched 68 files.
Thirty-nine lie under the dated `evidence/artifacts/` and `evidence/hosts/`
records. Of the other 29, nine hold the 18 current references a re-pin must
change, all still at 0.43.0:

- the pin in `manifests/stack.json`;
- three mirrors that existing checks compare with it:
  `blueprints/token-native-focus/saturation-audit.json`
  (`tests/test_stack_lifecycle.py:28-32`),
  `catalogs/landscape/upstream-snapshot.json` (`scripts/landscape.py:1373-1381`,
  which CI runs) and the `scripts/native_token_ci.py` pin (its run-time check at
  lines 1740–1742);
- the install references in `recipes/README.md` and
  `docs/token-efficiency-stack.json` (the two `install` lines; the same file's per-tool
  `card` blocks also name 0.43.0 on 12 lines as dated card facts, which the registry
  counts and a re-pin leaves alone);
- version-specific guidance in `recipes/README.md#history-and-usage`,
  `docs/native-dashboards.md`, `docs/native-dashboard-data.md`, the
  `scripts/native_token_ci.py` telemetry citation and a
  `tests/test_native_token_ci.py` comment.

The remaining 20 are dated records or an unrelated package and keep their
values. `docs/stack.md` is one of them: its header dates it September 19, 2026,
and no earlier re-pin changed it. Measured on 2026-09-28, 14 of its 47 rows
already differ from the manifest by version (15 when the repository URL is compared). [qualification.json](qualification.json)
records each location and the basis for each classification. The test fails
when a matching file is unclassified or a recorded location no longer matches,
and only while the pin holds: once `manifests/stack.json` is re-pinned it skips,
because the list describes the hold. Until then, a new tracked file outside the
dated evidence paths that mentions `0.43.0` for another tool fails it until that
file is classified as `unrelated_package` or `dated_record` in `qualification.json`.
The upstream ccusage source is
[ccusage/ccusage at ecb676cc](https://github.com/ccusage/ccusage/tree/ecb676cce27cb5dd0090c7804a5cecc35e8ba805/rust/adapters/codex),
whose maintained adapter is Rust. The guessed older TypeScript path was a 404,
not evidence of a missing capability.

**2026-09-27 review erratum:** the former completed GPT-6 review and its hold
verdict had no retained returned report. Those claims are withdrawn. The only
recorded GPT-6 attempts are the two exit-1 launches. A GPT-6 child of the GPT-6
builder would not satisfy independent cross-family review. Claude was launched
inside the builder's Codex sandbox with `--model opus --effort xhigh`,
`--permission-mode plan --tools Read,Agent --strict-mcp-config --output-format json`;
the build session stopped it. The next Claude qualification review must run
outside the Codex sandbox. [qualification.json](qualification.json) retains
the launch references and explicit interruption conditions.

**2026-09-27 prior-record reconciliation:** the
[2026-09-23 receipt](../sota-refresh-20260923/pins-tools/agentsview.json) calls
this upgrade `qualified` / `native_proven`. Its own `limits[0]` and `limits[2]`
restrict that verdict to checksum verification and the first lines of
`--version` / `--help`, without full sync/serve E2E. The qualified wording in
[its README](../sota-refresh-20260923/pins-tools/README.md) and
[the convergence catalog](../../../catalogs/sota-convergence/manifest-20260923.json)
inherits that narrower boundary. It does not satisfy the full qualification
procedure; **this 2026-09-27 hold governs any re-pin**. The old receipt is unchanged.

Other repair corrections: repository tests are structural validation and this
qualification is a summary of multiple evidence classes. The old five
FileNotFoundError errors were not a discriminating sanitization test. The
confirming broad rerun's raw bytes were not retained, despite the old blanket
retention claim; its printed hash identifies no available raw file. The new
coordinator runs retain their JSONL and stderr. Fixture hashes and expectations
are retrospective repair additions, with original observations preserved.

**2026-09-28 location-list repair:** the 2026-09-27 re-pin list named five
files. It missed the checked mirrors, the `recipes/README.md` install row and
the version-specific guidance, and it wrongly included `docs/stack.md`. The
classification above replaces it. The 2026-09-27 erratum reason no longer calls
its evidence review independent: no retained record names that reviewer, and
its returned report is not retained. The same holds for this repair's review.

Requalification needs four fresh native lanes, both completed independent
reviews, execution of the unchanged full-save E2E runner and the final recipe
controls in the same pin PR. The selected upstream tests now pass; no upstream
bug fix is required for the environmental failures. No complete-history,
savings, model-run or performance claim is
made. Full private logs and scratch binaries remain in the unit. Only aggregate
whitelist projections are published; native identities and transcript content
are excluded. Historical repository receipts were not rewritten.

The coordinator harness registers this branch's files in `manifests/evidence.json`
in the branch's last commit, following the `docs/lanes.md` hot-file protocol; there
were no generated-report changes. Repair registration, generated reports and
repository-wide validation belong to that harness. Private `units/w3/agentsview/`
references identify retained coordinator scratch records, not public checkout
files. Recommended label: `lane:foundation`.
