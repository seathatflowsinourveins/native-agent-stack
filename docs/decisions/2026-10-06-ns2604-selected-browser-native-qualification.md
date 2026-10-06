# Qualify the selected Chrome browser under the legacy playwright-cli slot

Date: 2026-10-06. Native-bar slot: `web-research/playwright-cli`. Decision:
**READY for the current plan's declared browser fixture acceptance on
NativeStack2604**, with the evidence and scope below.

The north-star action is browser navigation, accessibility inspection and
console observation for R&D. Both native clients now return the required
fixture results through the selected Chrome DevTools MCP server, and the
unchanged six-file upstream subset passes 129 tests with no failures or skips.
The earlier sudo/sign-in gate is superseded by these current observations.

## Identity and previous gate

The install plan preserves the `playwright-cli` slot id but selects Chrome
DevTools MCP 1.10.1 at `e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df`, one stdio
registration in each client
([native-agent-stack@0d5e6506: install-plan.json:1425](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0d5e6506434fab598dee861c749a22e628beb75a/evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json#L1425)).
The old operational census still reported blocked sudo/sign-in dependencies
and a failed after-sign-in stage. Its historical observations remain retained;
the new qualification uses the current selected owner and recipe.

Microsoft's optional Playwright CLI entry is a separate historical catalog
component. Its upstream describes a coding-agent browser automation workflow
([microsoft/playwright-cli@74354ecc: README.md:7-11](https://github.com/microsoft/playwright-cli/blob/74354ecc7a43da16d91a9bc54fa8db8283a3fcf5/README.md#L7-L11)).
A text-retrieval exclusion would not qualify the Chrome browser selected by
this slot. This decision leaves that optional component and the unstarted
20-task Harbor comparison unchanged; it makes no comparative-quality claim.

## Actual acceptance

The compact record is
[qualification.json](../../evidence/artifacts/ns2604-playwright-cli-20261006/qualification.json).
Original native JSONL, stderr and test output remain in the coordinator's
private durable state, identified by hashes in that record. Public sanitization
omits raw conversations, session identifiers and personal paths.

Google Chrome stable is installed at version `154.0.8037.97`, package
`154.0.8037.97-1` on amd64. Read-only package/source checks confirm the installed
version appears in Google's authenticated stable apt origin, the required
Signed-By fingerprint is present and the conflicting legacy source files are
absent. This satisfies the plan's installation prerequisite without a new
install or sudo invocation.

The existing Chrome MCP source checkout and prepared build are at the selected
e52c6b59 pin and its tracked source remains clean. The native command was:

```sh
NODE_TEST_REPORTER=spec PUPPETEER_EXECUTABLE_PATH=/usr/bin/google-chrome-stable \
  npm run test:no-build -- tests/index.test.ts tests/tools/pages.test.ts \
  tests/tools/snapshot.test.ts tests/tools/console.test.ts \
  tests/tools/network.test.ts tests/tools/performance.test.ts
```

It returned exit 0: **129 tests, 27 suites, 129 pass, zero fail/cancel/skip/todo**.
These are six unchanged upstream files through the upstream runner, using the
already installed browser and prepared build. The initial identical subset
also exited 0 with the native dot reporter; its output was retained before
the supported reporter setting was used to obtain explicit totals. The
upstream runner maps `.ts` inputs to existing built `.js` tests, supports this
reporter setting and returns the child test exit code
([ChromeDevTools/chrome-devtools-mcp@e52c6b59: scripts/test.js](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/scripts/test.js#L19)).
No rebuild or installation ran during this qualification.

Fresh Claude Code 2.1.291 and Codex 0.160.1 sessions each performed actual
`new_page`, `navigate_page`, `take_snapshot`, `list_console_messages` and
`close_page` calls through their configured `chrome-devtools` server. The
native streams establish successful returned navigation to the existing
fixture, its title `NativeStack Chrome MCP acceptance`, and the console marker
`native-stack-chrome-devtools-ready`. Each created page was closed and the
pre-existing blank page preserved; both native CLI processes exited 0.

The existing fixture has SHA256
`2480db42f335e809cfbdfeedb8e1789f3f0cf9de4c43e03e8b0606a8836d650f`.
An independent native MCP control navigated the owned page to `about:blank`:
the title/console predicate failed. The same check passed after navigation to
the fixture. A remembered answer without successful returned tool results
does not satisfy the checks.

The page-creation step supplies the required `pageId` for the later methods
and confines the trial to an owned isolated context. These are supported
interfaces at the selected pin:
[`new_page`:240-248](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/docs/tool-reference.md#L240-L248),
[`navigate_page`:223-235](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/docs/tool-reference.md#L223-L235)
and [`take_snapshot`:462-472](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/docs/tool-reference.md#L462-L472).
The observed recipe variation adds supported creation/cleanup; the three
required returned-result predicates and original fixture remain unchanged.

Claude ran under the shared fresh-session lock, with requested Opus/max and
an eight-turn bound; its reported model was `claude-opus-5-5`. Codex requested
`gpt-6.1-sol`/max with a fresh standalone, ephemeral read-only session, stdin
closed, `--skip-git-repo-check` and a non-Git working directory. Its native
events report completion and usage, but no actual model-name field; that
absence remains explicit. Neither client required a new sign-in.

Native registration readbacks confirm `npx` with the exact pinned version,
headless/isolated flags and both usage-statistics/CrUX opt-outs. Only the
selected command/argument metadata was retained. Codex's plaintext reader
uses upstream's masked environment formatter
([openai/codex@rust-v0.160.1: mcp_cmd.rs:1017-1037](https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/cli/src/mcp_cmd.rs#L1017-L1037),
[format_env_display.rs:3-24](https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/utils/cli/src/format_env_display.rs#L3-L24)).
The approved presence-only credential checker reported both native stores
present and `values_read=false`. No credential value or credential file was
inspected, and no client configuration was changed by this lane.

## Scope, alternatives and reopening

This closes the named native-bar browser slot under its current selected
owner and declared local fixture. Unchanged upstream tests, native client
integration and the synthetic fixture retain their separate evidence classes.
The record is not authenticated-site, broker, full upstream-suite or global
platform acceptance. The separate browser-diagnostic slot keeps its own owner
and required evidence.

Alternatives were retaining the historical blocked state or issuing a narrow
legacy text-retrieval exclusion. Current installed-browser, registration and
native returned-result evidence supports qualification of the actual selected
browser. Public text retrieval and opt-in hosted search keep their separate
routes; #790's hosted-search application/search result still belongs to the CC.

Reopen this decision if a native client loses the registration, the pinned
server/browser prerequisite changes, or the required fixture calls fail.
A new authenticated or interactive R&D workload needs its own scoped native
qualification. A change of browser default requires a declared comparison
through the upstream harnesses, including the retained unstarted Harbor
comparison; this record does not establish a winner for that task set.

Completeness critic: source identity, old versus current gate, both native
clients, artifact/browser binding, unchanged test selection, a missing-fixture
control, page cleanup and actual usage are all covered. Broader website tasks
and the remaining upstream files are explicit next-sweep boundaries. Native
usage is retained once per client; coordinator/source-review usage is unknown,
and no enclosing efficiency or savings claim is made.
