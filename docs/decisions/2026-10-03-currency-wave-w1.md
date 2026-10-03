# Currency wave W1 — 2026-10-03

## Decision and north-star action

Integrate the nine qualified foundation release pins from the W1 build contract.
This maintains the native tooling used to build complex projects and conduct the
north-star US-equities research and historical simulation. It changes repository
selections and supported installation recipes; host installation, service
replacement, broker operation and sealed landscape verdicts have separate scopes.

The worktree base is published main commit
`dcae68bd08a191f37ba564eceda9fc4a9d6d4a6e`, on
`foundation/currency-w1-20261003`. The coordinator owns committing and pushing.
The qualification input is `W1-moves.json`, workflow
`wf_a95468d8-3af`; each receipt retains its SHA256 and the original qualification
commands, returned output, exit codes and explicit not-run sentinels. The Opus
judgments supplied with that packet are research leads. Current canonical
release/source metadata and local artifact rehashes corroborate the selected
identities; they do not expand the scope of the recorded functional evidence.

## Moves and evidence

| Component | Previous pin | Selected pin and upstream source | Qualification receipt |
| --- | --- | --- | --- |
| jcodemunch-mcp | 1.108.319 | [v1.108.327](https://github.com/jgravelle/jcodemunch-mcp/releases/tag/v1.108.327), commit `6d5ae86c130f96624e2ca2d797fa3b853c210b9d` | [Version and get_session_stats](../../evidence/receipts/jcodemunch-1108327-qualification-20261003.json) |
| playwright-cli | 0.1.21 | [v0.1.22](https://github.com/microsoft/playwright-cli/releases/tag/v0.1.22), commit `b85c7a736bb473bf55b584e54a09ffa698d6d871`; bundled Playwright `1.64.0-alpha-1790635538000` | [Version and help](../../evidence/receipts/playwright-cli-0122-qualification-20261003.json) |
| openresearch | 0.2.7 | [v0.2.15](https://github.com/alphaXiv/OpenResearch/releases/tag/v0.2.15), commit `ee36ef0333ca3c533eace915f1bec322a1efde1c` | [Archive integrity and isolated version](../../evidence/receipts/openresearch-0215-qualification-20261003.json) |
| mcp-inspector | 2.8.0 | [2.9.0](https://github.com/modelcontextprotocol/inspector/releases/tag/2.9.0), commit `ae865a19178ddf6f375780a02e9c77c4cf4da184` | [Version, help and new functional stdio runs](../../evidence/receipts/mcp-inspector-290-qualification-20261003.json) |
| claude-hud | 0.8.0 | [v0.10.0](https://github.com/jarrodwatts/claude-hud/releases/tag/v0.10.0), commit `75683c6de1ac07f6bbef00d739001679dba0740c` | [Manifest versions and two synthetic stdin renders](../../evidence/receipts/claude-hud-0100-qualification-20261003.json) |
| opentelemetry-collector-contrib | 0.161.0 | [v0.162.0](https://github.com/open-telemetry/opentelemetry-collector-contrib/releases/tag/v0.162.0), commit `ae8c507510f48f433ab47dd1c6b01a59d6c388b5`; [distribution release](https://github.com/open-telemetry/opentelemetry-collector-releases/releases/tag/v0.162.0) | [Archive, version and configuration validation](../../evidence/receipts/otelcol-contrib-0162-qualification-20261003.json) |
| worktrunk | 0.79.0 | [v0.80.0](https://github.com/max-sixty/worktrunk/releases/tag/v0.80.0), commit `b49ca7eea9b03145791a5b94eccaf9c59412ed37` | [Version and synthetic repository list](../../evidence/receipts/worktrunk-0800-qualification-20261003.json) |
| mcporter | 0.14.1 | [v0.14.2](https://github.com/openclaw/mcporter/releases/tag/v0.14.2), commit `aa0f55f9bffcde9d2070c86145f37d4dd3525f6c` | [Version and new ad-hoc stdio canary](../../evidence/receipts/mcporter-0142-qualification-20261003.json) |
| syft | 1.52.0 | [v1.54.0](https://github.com/anchore/syft/releases/tag/v1.54.0), commit `cc326e45a6213360266dda4b30cc68095946d676` | [Version and recorded SDK inventory](../../evidence/receipts/syft-1540-qualification-20261003.json) |

The integration worker rehashed all nine retained downloads and matched every
SHA256 in the W1 packet. The hashes have different upstream integrity bases:
publisher checksums, npm registry integrity/provenance, PyPI metadata, or—in
the HUD case—Git tree identity and a locally recorded archive digest. The
individual receipts preserve those distinctions and unverified signatures.

For each component, the worker ran four fresh native `gh api` reads following
the upstream snapshot's methodology: repository metadata, `releases/latest`,
the selected exact source commit, and the latest stable release tag's commit.
All 36 commands exited zero. All nine latest stable tags matched their selected
candidate at collection time. The snapshot retains the original checks and
selected fields as dated `historical_observations`, and records genuine start/end
timestamps and SHA256s of raw API stdout for the new checks. Version-only stack
pins retain their pin semantics; resolving a commit for verification does not
silently change their installation format. HUD additionally records its exact
reviewed commit as the selected source pin.

The additional Inspector gate used its existing scratch installation with a
temporary stdio config pointing to the documented jCodeMunch server. The
repository's `tools/list` and `tools/call` recipe flags were kept, substituting
that server and its documented `order/get_session_stats` request. Both calls
exited zero with `--stored-auth-only`: the list contained six tool names and
the call returned the six-tool counter surface. A deliberately unknown tool
returned `tool_not_found` with exit 5. This stdio server requires no stored
credentials, so the flag did not exercise OAuth. The new mcporter 0.14.2
ad-hoc stdio call returned the same counter surface with exit zero, without
using an existing daemon. Actual output and the independent `last_seen_version`
observation are retained in [native-checks.json](../../evidence/artifacts/currency-wave-w1-20261003/native-checks.json).

The recorded OpenResearch functional smoke is explicitly not run. Its
`native_cli_e2e` receipt follows the build contract's required receipt kind,
but the claim is limited to the version output and does not establish live
discovery or paper retrieval. Playwright's help/version acceptance does not
establish browser operation. The Collector's configuration validation does not
establish live traffic or a host service switch. Syft's recorded inventory does
not establish signature verification or SPDX output on the new release.

## HUD integration and M14 amendment

The template now filters cached plugin directories for `dist/index.js` before
sorting versions and invoking Node. It selects the newest complete installation,
including an older complete version beside an incomplete newer directory, as in upstream
[scripts/statusline.mjs at the selected commit](https://github.com/jarrodwatts/claude-hud/blob/75683c6de1ac07f6bbef00d739001679dba0740c/scripts/statusline.mjs#L35).
The previous command could resolve a missing plugin to the open project's
`dist/index.js`. The regression test invokes the rendered command with an
instrumented Node fixture for absent plugin, missing entry, incomplete newer
installation beside a complete older version, and newest installed entry
conditions; it does not execute arbitrary project code. The same test against
the original unguarded template failed both missing-plugin conditions (exit 1,
two subtest failures), and passed against the guarded template (exit 0). Both
results are retained beside the native checks. Template-managed hosts
keep their reviewed statusLine command when adopting the plugin: upstream setup
backs up settings and replaces a statusLine containing `claude-hud`, with its
runtime selected from PATH ([setup source](https://github.com/jarrodwatts/claude-hud/blob/75683c6de1ac07f6bbef00d739001679dba0740c/scripts/setup.mjs)).

The September 24/28 M14 decisions retain their bytes and their 0.8.0 observations.
At 0.10.0, [dist/git.js](https://github.com/jarrodwatts/claude-hud/blob/75683c6de1ac07f6bbef00d739001679dba0740c/dist/git.js)
uses `git --no-optional-locks status --porcelain=v2 --branch -z`, and requests
`diff --numstat` only on a dirty tree when line diffs are requested. An idle
interactive-session check remains open; synthetic formatting does not close it.
Upstream [PR #795](https://github.com/jarrodwatts/claude-hud/pull/795), merge commit
`c0c4866780b101f0ee281f2ddd356b7ebf649879`, fixes hyperlink wrapping after
v0.10.0 and remains a follow-up. [Issue #796](https://github.com/jarrodwatts/claude-hud/issues/796)
is open for `showDiskUsage`; the supplied judge found that field absent in the
old tagged pin as well. These source-review residuals are separate from the
observed fixture render.

## Holds and cooldown waiver

The user ended the seven-day cooldown for clean releases on 2026-10-03.
This removes an age-only delay; it does not waive qualification, known
regressions, functional gates or recipe compatibility. Alternatives were to
retain the nine previous pins for the remaining cooldown, adopt the qualified
releases within their measured scopes, or skip ahead to unqualified releases.
Adopt the qualified set; retain each previous pin as the rollback reference.

The W1 `holds_not_in_scope` entries stay out of this integration:

| Component | Hold reason and next unit |
| --- | --- |
| beads | v1.3.1 has the known upstream regression #7030 in the `bd close` path, so it does not meet the clean-release waiver. The supplied hold retains the normal cooldown through 2026-10-07T23:37:36Z; a cooldown ending alone does not fix the regression. |
| agentsview | 0.44.0 passes release/integrity/version checks but its behavior changes require a recipe rewire and functional qualification. That work has a separate owner. |
| grafana | The supplied hold records no observed release status, download/hash, installed candidate or smoke. Requalification is running separately. |
| agent-browser | The supplied hold records placeholder stable-release metadata and missing artifact/install/smoke/release-note qualification. Requalification is running separately. |
| headroom | The supplied hold records no verified 0.39.1 wheel, binary or smoke. Requalification is running separately; this is not evidence of a release defect. |
| dagu | The supplied hold records no verified 2.18.1 archive, installed version or behavior review. Requalification is running separately. |
| rtk | The supplied hold records no candidate artifact, observed version or qualified release metadata. Requalification is running separately. |

## Completeness critic and next sweep

Search-first used the existing native recipes and upstream snapshot method; no
custom installer or acceptance runner was added. Scoped ai-memory CLI searches
used limit 2: the task-filtered query returned no hits, and the widened query
returned unrelated release notes, so no retrieved memory claim was adopted. The
installed CLI help did not expose pin-priority arguments, and the template MCP
endpoint did not provide a usable schema. The initial Inspector help lookup
used a local npm binary layout and failed with exit 127; the packet's global
installation path corrected it, and native help plus the functional runs
verified that correction. The failure and recovery remain in native-checks.json.

The worker compared every supplied `pin_sites` list with its own full `git grep`
results and classified current installation pins separately from historical
source anchors, recorded outputs, unrelated dependency versions and sealed
verdicts. The latest source identities are verified by original API responses.
Existing Linux pin entries were updated for `orx` and `mcporter`; the other seven
components have no entries in that file, and their supported recipe formats
remain in use. The two generated report pairs are rebuilt by their own write
commands. `build_ecosystem.py` is check-only.

The remaining modalities for the next lifecycle-keyed sweep are real browser
operation, authenticated public-literature retrieval, Inspector HTTP/SSE/OAuth
and UI paths, mcporter daemon/serve/OAuth/recovery, HUD live interactive and idle
rendering, Collector traffic/restart, Worktrunk create/remove/dirty-refusal, Syft
SPDX/signature verification, and independent macOS qualification. Source
currency, local artifact identity and native fixture execution remain distinct
from unchanged upstream test suites and full host lifecycle acceptance. Those
gaps do not become passed through older receipts. The five separate
requalification units, beads regression repair and AgentsView recipe rewire
are the next candidate classes; this bounded wave does not establish complete
ecosystem saturation or a model-quality improvement.

Hosted evidence remains separate: W1 exercised jCodeMunch 1.108.327 through
`get_session_stats`; it did not repeat `index_folder`, `search_symbols` or
`get_symbol_source` against a frozen source oracle. The coordinator must retain
the `native-token-e2e` result for the committed repair head to close that gap.
Syft 1.54.0's first hosted `sbom-vuln` run against the reproduced
`nautilus_trader` environment also remains a hosted qualification gap; the W1
inventory comparison covered the equity-worker SDK. `publish-catalog` runs on
dispatch or a `v*` tag, so PR CI does not exercise its updated Syft installation
path. Its next dispatch/tag result must be retained as that path's first
execution. This repair neither dispatches those workflows nor infers their
results from local structural checks.

Off-limit configuration-owner files, including `adoption/new-wsl-profile.json`,
all `blueprints/us-equities/` files, historical receipts, prior decisions,
dated catalogs and sweep manifests retain their bytes. The trading-owned
`observability/paper-trading-live/collector-paper-trading.yaml` comment is
restored to its base 0.161.0 text in R642. Reports may display the intentional
difference between current stack pins and older sealed landscape winners.

Owner handoffs for the next unit:

- The configuration owner must reconcile `adoption/new-wsl-profile.json`:
  it carries Inspector 2.9.0, Worktrunk 0.80.0 and Collector 0.162.0, while
  mcporter 0.14.1, playwright-cli 0.1.21 and Syft 1.52.0 remain older than
  the W1 selections. This file is outside the repair's edit scope.
- The trading owner must update the canonical
  `blueprints/us-equities/supply-chain/README.md` recipe for Syft 1.54.0,
  including its 1.52.0 archive/hash instructions, using the W1 receipt's
  publisher checksum URL and `54a87372498168b2d033e876fd41fa4e8035b872699e525a57046e1f2f09c860`.
  The trading owner also owns the Collector version comment in
  `observability/paper-trading-live/collector-paper-trading.yaml`.
- The coordinator supplies the required CI buckets, macOS result, hosted
  secret scans, PR labels/body and any required trading acknowledgement for
  the committed repair head. No commit, push or PR metadata mutation is part
  of this repair.

## Supplemental test environment correction

The additional pin-consistency modules initially hit two native `npm pack`
fixture-setup errors (exit 226). A minimal native pack reproduced `EROFS`
against the inherited home npm cache. A first scratch-cache attempt also used
`/dev/null` for both npm configuration layers; npm rejected that double-loaded
path with exit 1. Distinct empty scratch user/global files and a writable cache
restored native packaging (exit 0). This follows the distinct npm config paths
in the W1 installation records, preserves both failed attempts and does not
change host configuration or repository test behavior. The retained
four-module supplemental run reports 253 tests and `OK (skipped=33)` with
the isolated configuration. Its complete returned totals are retained in
native-checks.json; no separate 25-test result was retained, and the earlier
claim that every original build-contract check passed lacked retained command
output. Those unsupported specifics are withdrawn. R642's new checks retain
their own command lines, exit codes and returned output in
[review-repair-checks.json](../../evidence/artifacts/currency-wave-w1-20261003/review-repair-checks.json).

## R642 bounded repair and completeness critic

This review repair serves the same foundation maintenance and north-star
research action as W1. Search-first selected the existing repository unittest
and validation commands. No new installer, dependency or acceptance runner was
needed. The installed Collector's help/version and the pinned HUD launcher
source were checked before changing their integration paths. The alternative
of leaving tests bound to 0.161.0 would continue to skip the current installed
pin; hard-coding 0.162.0 would repeat the drift on the next move. The three
current Collector selectors now read the component version from
`manifests/stack.json`; `OTELCOL_TEST_BIN` permits a scratch binary without a
host installation. SDK usage tests inherit that same selector.

The selector variant search started with the exact stale tool-names selector,
then widened the same path pattern to the repository root and checked skip
messages. It found the run-correlation and writer-identity selectors and the
inherited SDK guard. The 0.161.0 fake binary in
`tests/test_observability_writer_identity_host.py` belongs to a copied, dated
host-apply fixture, not the current native Collector pipeline, and is retained.
Source review and historical receipt citations likewise keep their dates.

Receipt command paths were restored from the hashed W1 packet before
sanitization. Distinct npm user/global files, XDG directories and HUD config
paths now survive as distinct scratch placeholders. Stack command citations
use a component id and the component-relative JSON pointer `/commands`.
Each archive/package receipt names its primary published digest URL; HUD
explicitly has no publisher archive checksum and instead names its exact
upstream source-tree integrity URL. The earlier review's DNS failure was a
review-environment limitation; no mismatch was established and no pin or
digest is changed for it.

The new HUD mixed-install regression failed against the pre-repair template
and passed after filtering entries before sorting. Those returned results are
retained as local fixture evidence. This session exposed no scoped ai-memory
MCP tool. Installed CLI help supports a scoped search with limit 2 but no
pin-priority option; the initial R642 search returned HTTP 404 because the
requested project was absent from the default workspace. This is a scope
lookup failure, not evidence that the service is unavailable. The repair used
the recipe's `local` workspace on retry and received no hits. It then used
the exact decision and original source packet
and adopted no memory claim. Completeness checks cover all requested findings,
current selectors, canonical recipe entry points, reproducible receipt paths,
component-relative citations and owner boundaries. Remaining source/runtime
modalities feed the lifecycle sweep above; hosted and owner work is handed off.

The staged publication check uses Git 2.43.0's documented
[`GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY` and read-only alternate objects](https://github.com/git/git/blob/v2.43.0/Documentation/git.txt)
in writable repair scratch, so the ordinary worktree index remains untouched.
Native `read-tree HEAD`, `git add -A` and `git reset -- .` provide the stage and
cleanup. The installed Gitleaks wrapper could not create its host runtime lock
in this sandbox; the bounded staged scan uses the pinned upstream Gitleaks
8.30.1 executable. Its result does not qualify host-local guarded containment.

## Overturn condition and rollback

Reopen a move on a regression in its documented command path, an advisory
affecting the selected artifact or dependency tree, a failed new-host/runtime
qualification, changed upstream artifacts, or better primary evidence from a
matched qualification. Specific open conditions include the HUD hyperlink fix,
Inspector OAuth migration and profile isolation, mcporter's bundled-client/server
dependency mismatch, and Syft's unverified new Sigstore bundle format.
Revert the selected stack/audit/snapshot row, supported recipe, artifact hash
and affected CI pin together, preserving the failed receipt and observations.
Inspector rollback after an OAuth-store migration may need a fresh sign-in;
this wave exercised stdio only. Host rollback, service swaps and sealed verdict
refreshes remain separately owned operations.
