# Round-2 install plan: browser owner on NativeStack2604 (2026-10-04)

The `web-research/playwright-cli` slot installs **Chrome DevTools MCP 1.10.1**
by default through one stdio server, `chrome-devtools`, in each native client.
Browser diagnostics use that same registration. This implements the wave-5
owner recorded in [the round-2 decision](2026-10-04-final-architecture-round2.md)
and the `web-research/playwright-cli` and `browser-debugging` verdicts in
`evidence/artifacts/final-architecture-round2-20261004/verdicts.json`.

This unit serves complex-system engineering and the north-star R&D by making
browser automation and rendered-page diagnostics available to both native
coding clients. It performs bounded source review and install-plan production;
the owner's repository-quality rule excludes a new local selection trial.
The requested Sol/max builder lane is preserved. No child or cross-family
judgment, browser run, model run, destination install or other-distribution
command was launched.

## Source and installation

The npm package is `chrome-devtools-mcp@1.10.1`; GitHub tag
`chrome-devtools-mcp-v1.10.1` resolves to
`e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df`, also the npm `gitHead`. The
[release changelog](https://github.com/ChromeDevTools/chrome-devtools-mcp/releases/tag/chrome-devtools-mcp-v1.10.1)
and the pinned source were read. [npm metadata](https://registry.npmjs.org/chrome-devtools-mcp/1.10.1)
publishes the SHA512 SRI retained in the plan, stack and profile. The installer
checks the downloaded archive against that frozen digest and checks registry
integrity before the documented npx warmup. No builder install is inferred from
metadata or the source checkout.

The [tagged client setup](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/docs/client-configurations.md#L71)
documents Claude Code at line 71 and Codex at line 109. Both clients use
`npx -y chrome-devtools-mcp@1.10.1 --headless --isolated
--no-usage-statistics --no-performance-crux`; the native `--` separator forwards those options.
Installed `claude mcp add --help` and `codex mcp add --help` confirm that syntax.
[Concurrent sessions](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/docs/advanced-usage.md#L22)
require isolated temporary profiles. The MCP interface is adopted; the
experimental CLI and Claude plugin are not registered.

The upstream WSL section requires Linux-side stable amd64 Chrome. Repair
2026-10-05 uses [Google's signed apt repository](https://www.google.com/linuxrepositories/)
instead of an unchecked current .deb. The helper checks the active primary
fingerprint EB4C1BFD4F042F6DDDCCEC917721F63BD38B4796, restricts Signed-By to
that fingerprint and its legitimate signing subkeys, updates authenticated apt
metadata, and installs exactly google-chrome-stable=154.0.8037.97-1.
[Published package metadata](https://dl.google.com/linux/chrome/deb/dists/stable/main/binary-amd64/Packages)
held that version on 2026-10-05. If it is no longer available, fail clearly;
never fall back to the current package. Privilege remains in the declared helper.
No package installation ran in this repair. Node 24.21.0 satisfies the MCP pin.
The downloaded MCP artifact's SHA256 is
012cbcf6e832d4f6709dad0c21d7bef17089e94adee9cf33179d15ea0a9adf2b;
its SHA512 matches the frozen published SRI. The destination npx route checks
registry dist.integrity; it no longer downloads an unused archive. That checks
the direct pin, with no claim that transitive npm dependencies are locked.

The stable component identifier `playwright-cli` is retained so historical
receipt references do not become unknown components. Its repository, runtime
pin, role and commands now describe Chrome DevTools MCP. Historical Playwright
receipts do not accept that replacement. `agent-browser` retains its historical
pin as an optional reference and is superseded for this slot; `playwright-test`
remains the separate regression runner. Only browser pin cells and profile
membership change; shared row order and headers are left to integration.

## Acceptance and READY

The [release CI](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/.github/workflows/run-tests.yml#L30)
provides source submodules, `PUPPETEER_SKIP_DOWNLOAD=true npm ci`, the pinned
Puppeteer Chrome installation, bundle preparation and `npm run test:no-build`.
The [upstream runner](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/scripts/test.js#L28)
accepts explicit original test filenames. `post_install` selects six unchanged
files: `tests/index.test.ts` and
`tests/tools/{pages,snapshot,console,network,performance}.test.ts`. It records
actual output in private per-run state and propagates failure. The subset selects installed Google Chrome stable through the documented
`PUPPETEER_EXECUTABLE_PATH` (puppeteer/puppeteer@puppeteer-v25.11.0:
packages/puppeteer/src/getConfiguration.ts:140-145 and the MCP tests/utils.ts:89-92).
The unused Chrome for Testing download is removed; these tests use the installed stable Chrome. This is not
the whole OS/Node matrix,
notices suite, publication process or memory-leak job.

`after_sign_in` implements the verdict's native operations with this PR's local
synthetic HTML fixture. Both clients must return successful
[`navigate_page`](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/docs/tool-reference.md#L223),
[`take_snapshot`](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/docs/tool-reference.md#L462)
and [`list_console_messages`](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/docs/tool-reference.md#L431)
results containing the actual local URL, expected title and console marker.
The existing main-source Serena check in this install plan supplies the native
event/result correlation pattern. This is a local integration check with a
synthetic fixture, separately labelled from the unchanged upstream tests.

Native client sign-ins remain `needs_user`. The native approval policy must
also permit browser calls: at this Chrome pin, `src/tools/pages.ts:159-161` and
`src/tools/snapshot.ts:17-20` annotate navigation and snapshots with
`readOnlyHint: false`. Under a Codex `never` policy with restricted filesystem permissions, the map's
scoped authorization setting below permits these calls through the recipe's
existing `--with-authorization-settings` path. The pinned native implementation
also auto-approves MCP prompts under `never` with disabled/external sandboxing
or full disk write permissions; the destination's configured permission profile
must be read alongside its approval policy. Sources: openai/codex@rust-v0.160.0:
codex-rs/codex-mcp/src/mcp/mod.rs:91-109 and core/src/mcp_tool_call.rs:1515-1530,1619-1624. No sign-in or credential store is copied
or read here. READY requires both acceptance stages to succeed on the
destination, with the single registration and required flags active.

[README.md:35-55](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df/README.md#L35)
documents usage-statistics and CrUX opt-outs separately. The required statistics
opt-out is installed. `--no-performance-crux` is required in both client registrations to disable
performance trace URL lookups; this local navigation/snapshot/console check
does not invoke a trace lookup.

## Client map integration boundary

`tools/adoption/new_wsl_client_config.py:491-498,551-553,1136-1141` only wires
keys already present in its templates. Neither
`adoption/new-wsl/templates/claude-user.mcp.additions.json` nor
`adoption/new-wsl/templates/codex.config.additions.toml` contains this server.
The bounded job's allowed-file list excludes both files. The scope question is
pending; no answer is inferred from elapsed time. Until the coordinator adds
the following entries, the row uses the tagged native CLI registration commands.
Those commands reach the native configs on a clean host, but the map ownership
requirement remains an integration item. Remove those two commands from the row
and the matching shell function once the map takes ownership.

Add this single server to the Claude additions' existing `mcpServers` object:

```json
"chrome-devtools": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "chrome-devtools-mcp@1.10.1", "--headless", "--isolated", "--no-usage-statistics", "--no-performance-crux"]
}
```

Append the equivalent Codex server, keeping authorization a distinct piece:

```toml
[mcp_servers.chrome-devtools]
command = "npx"
args = ["-y", "chrome-devtools-mcp@1.10.1", "--headless", "--isolated", "--no-usage-statistics", "--no-performance-crux"]
default_tools_approval_mode = "approve"
```

Insert the two map entries below before a broader matching entry, with the
authorization entry first. Their `owner` matches the wave-5 manifest exactly:

```json
[
  {
    "match": ["codex/config/mcp_servers.chrome-devtools.default_tools_approval_mode"],
    "wiring": "authorization:allow the selected browser MCP tools under the destination's never policy",
    "slot": "playwright-cli",
    "owner": "Chrome DevTools MCP 1.10.1 (one stdio MCP server, chrome-devtools, in both clients; it also serves browser diagnostics)",
    "source": "openai/codex@rust-v0.160.0:codex-rs/core/src/mcp_tool_call.rs:1515-1530,1619-1624; codex-rs/codex-mcp/src/mcp/mod.rs:91-109; ChromeDevTools/chrome-devtools-mcp@e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df:src/tools/pages.ts:159-161 and src/tools/snapshot.ts:17-20"
  },
  {
    "match": ["claude/mcp/server/chrome-devtools", "codex/config/mcp_servers.chrome-devtools.*"],
    "wiring": "slot:playwright-cli",
    "owner": "Chrome DevTools MCP 1.10.1 (one stdio MCP server, chrome-devtools, in both clients; it also serves browser diagnostics)",
    "names": ["chrome-devtools"],
    "source": "ChromeDevTools/chrome-devtools-mcp@e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df:docs/client-configurations.md:71,109; docs/advanced-usage.md:22; README.md:45"
  }
]
```

The native source for Codex's targeted JSON readback is
[openai/codex@rust-v0.160.0:codex-rs/cli/src/mcp_cmd.rs:937-980](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/cli/src/mcp_cmd.rs#L937),
verified after the installed `codex mcp get --help` and the
[official MCP guide](https://developers.openai.com/codex/mcp). The map entries
must pass `new_wsl_client_config.py --check` after template integration.

## Alternatives, overturn condition and completeness review

Playwright CLI 0.1.22 and agent-browser remain the alternatives named by the
round-2 evidence. Their earlier comparison never started. The retained removal
check uses upstream Harbor on the same 20 browser tasks, comparing the adopted
MCP interface against Playwright CLI 0.1.22. The verdict's replacement condition
is a paired 95% interval for Playwright minus Chrome verified completion wholly
above zero, with no higher median time. It reports to the owner and removes
nothing automatically. This job does not reopen that choice with a new trial.

The completeness review checked browser diagnostics, independent sessions,
headless workers, both native clients, the Chrome prerequisite, published npm
integrity, actual tool-result acceptance, sign-in and authorization. It found
the missing template keys and navigation/snapshot approval annotations; those
feed the coordinator's client-integration sweep. Desktop control, Android and
OpenHands's SDK BrowserToolSet are outside this slot. Upstream fixture Chrome
for Testing is test preparation, not a second client registration. The next
browser sweep must distinguish publication evidence, source tests, destination
execution and the still-unstarted Harbor removal check.

Corrections verified in this unit: the base's measurement-only row conflicts
with wave 5 and is replaced; the plan's line-based `run_commands` parser needs
single physical command lines, so multiline install command literals were
changed to sequential `&&` chains (`check_plan.py:46-55`). The source filename
for Codex MCP commands is `mcp_cmd.rs` at the pinned release. An npm metadata
read using the read-only default cache failed and was retried with a writable
task cache outside the checkout. The ai-memory read was rejected because the
MCP tool required approval under the session's `never` policy; canonical
decision and verdict files were read directly, without treating memory as
authority.

Shared integration items: regenerate `owners.json` from the final plan, update
shared row/stage/default/measurement counts after all groups, and synchronize
the handbook outputs and receipt digests after profile changes. The browser
delta is one more default installed row, one fewer measurement-only row, and
one more primary acceptance stage; no row is added or reordered.

Correction from original pinned source: `approval_policy = never` alone does not
imply every browser mutation is denied. The MCP auto-approval helper at
openai/codex@rust-v0.160.0:codex-rs/codex-mcp/src/mcp/mod.rs:91-109 also checks the
permission profile. The restricted-profile wording above replaces the initial
over-broad inference; `approve` remains a supported explicit per-server setting.

Returned local validation: the required four-module unittest command ran 347
tests and failed on 27 entries. A separate checkout of the provided base ran
the identical command and failed on 25 entries. Two additional integration
failures are retained: the central landscape lacks a Chrome DevTools MCP role
entry (`scripts/landscape.py:1286-1290`, outside this job's edit boundary), and
the handbook receipt's shared projected-tool count remains 82 while the source
projection now has 83. Both are coordinator integration work, not hidden by
loosening tests. The named TMPDIR was used; its read-only mount also causes the
base's skill-authoring `mktemp` failure. No credential value was involved.

`check_plan.py` exits 1 with seven integration problems, none naming this slot:
four other groups' missing rows, two agent-messaging disagreements, and the
shared owners.json export. Both shell syntax checks, the client-config check,
the rebuilt handbook check and git diff --check pass. Publication validation
exits 1 with 120 registry errors only: 35 SHA-256 mismatches, 35 byte-count
mismatches and 50 unregistered artifacts. Shared headers and
counts were not hand-edited; generated handbook outputs and their receipt
digests were refreshed through the requested generator path.

The final rerun after selecting installed Chrome for upstream tests returned
the same 347 tests and 27 failure entries, retaining exactly the two additional
integration failures above. The architecture pin locator was corrected to the
actual version cell, `manifests/stack.json:689`; the handbook was regenerated
and its output digests refreshed after that correction. An original-base JSON
comparison confirms only the `playwright-cli` plan row changed, row order and
plan header fields are unchanged, and stack component changes are confined to
`playwright-cli` and its superseded `agent-browser` reference. HEAD remains the
provided base; the proposed commit message is in the job's requested handoff
file. The client map check passes for the existing templates; it does not
establish the still-pending Chrome map wiring.

## Integrator correction, 2026-10-05

The builder's proposed reuse of the host `playwright-cli` component ID for
Chrome DevTools MCP is withdrawn. `manifests/stack.json` and the upstream
snapshot remain byte-identical to the integration base; the host Playwright
pin, profile membership and receipts remain their original selection. A host
Chrome replacement, central-landscape registration or agent-browser role/profile
change belongs to the currency PR with a saturation-audit row and qualification
receipt. Source: this PR:tests/test_stack_lifecycle.py:21; this PR:manifests/stack.json:689.

The architecture uses `name: Chrome DevTools MCP`, pin 1.10.1, citing the actual
round-2 pin at this PR:docs/decisions/2026-10-04-final-architecture-round2.md:24.
Extra source-pin, supersession and usage details stay in the row's notes and
this decision. The retained agent-browser winner explicitly serves as the host
reference; this follows the catalog's durable-memory host-reference role and
its retained LEAN comparison-oracle cell, without making it a second 2604
browser owner. Source: this PR:catalogs/foundation/new-wsl-architecture-20261001.json
(the durable-memory and backtesting-engine rows).

The map now renders the single chrome-devtools stdio server from both client
additions, with --headless --isolated --no-usage-statistics --no-performance-crux. Its Codex approval
piece remains scoped to the existing authorization-settings option. The two
installer CLI registration commands were removed to keep one writer. Source:
ChromeDevTools/chrome-devtools-mcp@e52c6b59b476c5e04d8dd9fd4bd017ba3b3d65df:
docs/client-configurations.md:71,109; docs/advanced-usage.md:22; and
https://developers.openai.com/codex/mcp. These are configuration and structural
checks; destination browser and native-client execution remain owed.
