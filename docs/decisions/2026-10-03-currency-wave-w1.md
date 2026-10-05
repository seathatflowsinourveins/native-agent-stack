# Currency wave W1 — 2026-10-03

## Decision and north-star action

Amended 2026-10-04: after merging main 14048b84 this PR integrates seven W1 moves; claude-hud, RTK and mcporter follow main's #693; see [Merge with main 14048b84, 2026-10-04](#merge-with-main-14048b84-2026-10-04).

Integrate eight qualified foundation release pins from the W1 build contract;
hold mcporter at 0.14.1 after R642b review.
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
| syft | 1.52.0 | [v1.54.0](https://github.com/anchore/syft/releases/tag/v1.54.0), commit `cc326e45a6213360266dda4b30cc68095946d676` | [Version and recorded SDK inventory](../../evidence/receipts/syft-1540-qualification-20261003.json) |

The integration worker rehashed all nine retained downloads and matched every
SHA256 in the W1 packet. The hashes have different upstream integrity bases:
publisher checksums, npm registry integrity/provenance, PyPI metadata, or—in
the HUD case—Git tree identity and a locally recorded archive digest. The
individual receipts preserve those distinctions and unverified signatures.

For each component, the worker ran four fresh native `gh api` reads following
the upstream snapshot's methodology: repository metadata, `releases/latest`,
the selected exact source commit, and the latest stable release tag's commit.
All 36 commands exited zero. All nine latest stable tags matched their W1
candidates at collection time; R642b retains eight moves and holds mcporter
at 0.14.1. The snapshot retains the original checks and
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
credentials, so the flag did not exercise OAuth. The mcporter 0.14.2
ad-hoc stdio call returned the same counter surface with exit zero, without
using an existing daemon; it is compatibility-attempt evidence for the hold,
not acceptance of the selected pin. Actual output and the independent `last_seen_version`
observation are retained in [native-checks.json](../../evidence/artifacts/currency-wave-w1-20261003/native-checks.json).

R642b re-ran those exact four commands from the W1 scratch installs with a
fresh configuration and home. Each shell captured its start and end with
`date -u +%Y-%m-%dT%H:%M:%SZ`. The artifact's
`commands/inspector-tools-list-r642b-timed` (08:23:59–08:24:00 UTC),
`commands/inspector-tools-call-r642b-timed` (08:24:00–08:24:01 UTC) and
`commands/inspector-negative-r642b-timed` (08:24:01–08:24:02 UTC) returned
the same six tool names, a successful counter call and the expected
`tool_not_found` exit 5 on 2026-10-03. The
`commands/mcporter-call-r642b-timed` (08:24:02–08:24:03 UTC) returned
`visible_tools: 6` with exit 0; it supports only the compatibility-attempt hold.
The final timed commands ran after every current mcporter pin site and PR count was repaired. The interim timed entries are also retained under `-r642b-timed-earlier`. The four original entries remain labelled `earlier_untimed_attempt`, with their
unknown times preserved. Each affected receipt points to the fresh timed entries.

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
retain the previous pins for the remaining cooldown, adopt eight qualified
releases within their measured scopes while holding mcporter, or adopt all nine
despite the mcporter dependency and daemon gaps. Adopt the eight qualified moves;
retain each previous pin as the rollback reference.

R642b holds mcporter at the accepted Linux 0.14.1 pin. Its
[0.14.2 compatibility attempt](../../evidence/receipts/mcporter-0142-qualification-20261003.json)
retains the ELSPROBLEMS finding: bundled core 2.2.0 beside resolved server 2.3.0.
The ad-hoc stdio canary does not qualify the persistent daemon and `serve` roles
used by `foundation-cpu` and `token-efficiency`. Reopen the move only after a
consistent resolved dependency tree (`npm ls --all` succeeds) and isolated
qualification of that persistent role, including use, restart and recovery.
A fresh read-only `npm ls --global --prefix <qualification-root>/mcporter/prefix --all --json` check also returned exit 1 and `ELSPROBLEMS` on 2026-10-03; the receipt retains its native `problems` field, stderr, timestamps and original stdout hash. The stack, audit, Linux artifact and install rows return to their `origin/main`
0.14.1 values; macOS retains its independently held 0.13.13 pin and its Linux
comparison returns to 0.14.1. No current pin links the attempt receipt. The
upstream snapshot keeps the W1 0.14.2 observation as a dated compatibility
attempt and still reports that newer release, while selecting 0.14.1.

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

**Judgment custody.** The complete reviewer outputs behind this record, and the
repair replies that answered them, are retained under
`evidence/artifacts/currency-wave-w1-20261003/judgments/`, sanitized only of
host paths:
[move-hold-judges.json](../../evidence/artifacts/currency-wave-w1-20261003/judgments/move-hold-judges.json)
(the nine Opus move judges of `W1-moves.json`, workflow `wf_a95468d8-3af`; its
seven `holds_not_in_scope` strings are kept as the packet recorded them,
already cut at 600 characters),
[review-round-findings.json](../../evidence/artifacts/currency-wave-w1-20261003/judgments/review-round-findings.json)
(the start events and results of the Opus `approve` and Sol `repair` #642
reviewers, workflow `wf_267d65f8-7f6`),
[repair-round-replies.md](../../evidence/artifacts/currency-wave-w1-20261003/judgments/repair-round-replies.md)
(R642) and
[repair-round-2-replies.md](../../evidence/artifacts/currency-wave-w1-20261003/judgments/repair-round-2-replies.md)
(R642b).

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
The Linux `orx` pin was updated; mcporter remains at 0.14.1 after R642b's hold.
The other seven moved components have no entries in that file, and their supported recipe formats
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

**Dated history (2026-10-03 W1 repair scope and handoff).** The following text is retained as written; its current-tense configuration-owner statements are superseded by the October 5 merge record below.

> Off-limit configuration-owner files, including `adoption/new-wsl-profile.json`,
> all `blueprints/us-equities/` files, historical receipts, prior decisions,
> dated catalogs and sweep manifests retain their bytes. The trading-owned
> `observability/paper-trading-live/collector-paper-trading.yaml` comment is
> restored to its base 0.161.0 text in R642. Reports may display the intentional
> difference between current stack pins and older sealed landscape winners.
>
> Owner handoffs for the next unit:
>
> - The configuration owner must reconcile `adoption/new-wsl-profile.json`:
>   it carries Inspector 2.9.0, Worktrunk 0.80.0 and Collector 0.162.0, while
>   playwright-cli 0.1.21 and Syft 1.52.0 remain older than the W1 selections.
>   Its mcporter 0.14.1 agrees with R642b's hold. This file is outside the repair's edit scope.

**Configuration-owner handoff after merges 2 and 3 (2026-10-05):**

- Only the profile's playwright-cli 0.1.21 remains older than the stack's 0.1.22 selection. Syft 1.54.0 and mcporter 0.14.2 now match through main #684/#704. This PR sets the jcodemunch-mcp entry to 1.108.327. The other owner handoffs below retain their separate scopes.
- The trading owner must update the canonical
  `blueprints/us-equities/supply-chain/README.md` recipe for Syft 1.54.0,
  including its 1.52.0 archive/hash instructions, using the W1 receipt's
  publisher checksum URL and `54a87372498168b2d033e876fd41fa4e8035b872699e525a57046e1f2f09c860`.
  The trading owner also owns the Collector version comment in
  `observability/paper-trading-live/collector-paper-trading.yaml`.
- The coordinator supplies the required CI buckets, macOS result, hosted
  secret scans, PR labels/body and any required trading acknowledgement for
  the committed repair head. No commit or push is part of this repair;
  R642b authorizes correcting the PR's component count to eight.

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

## R642b review-bot repair and completeness critic

R642b serves the W1 foundation maintenance action for the north-star research
runtime. The five threads were checked against head `2d6f49233fa1` before edits.
The Collector live row incorrectly attributed deployed 0.161.0 runtime evidence
to selected 0.162.0; it now separates the deployed and selected versions, with
the W1 receipt limiting 0.162.0 to scratch validation. mcporter's pin move was
also withdrawn: its canary did not settle the dependency-tree and persistent
role gaps. The hold and its specific overturn condition are recorded above.

The HUD transition now follows the installed Claude Code 2.1.288 help,
[tagged changelog](https://github.com/anthropics/claude-code/blob/v2.1.288/CHANGELOG.md),
[official update instructions](https://code.claude.com/docs/en/plugins/install#update-plugins-now),
[marketplace CLI reference](https://code.claude.com/docs/en/plugins/cli-reference#plugin-marketplace-update)
and [source synchronization rules](https://code.claude.com/docs/en/plugins/loading#plugins-and-marketplaces-that-arent-on-disk-at-session-start).
First retarget the declared marketplace source to `v0.10.0`, let the next native
session synchronize that changed source, run `claude plugin marketplace update
claude-hud`, then `claude plugin update claude-hud@claude-hud --scope user`,
reload and check the installed commit. Refreshing a source still pinned to
`v0.8.0` keeps that tag. Status: **documented, host verification pending**.
Only native version/help commands ran, using an absolute native executable,
scratch cwd, temporary `HOME` and temporary `CLAUDE_CONFIG_DIR`; the actual
outputs are retained in `native-checks.json#/r642b_claude_hud_upgrade`.
No safe offline GitHub-tag transition was verified and no host update ran.

R642 already added current OpenResearch and Worktrunk notes to the dated upgrade
document, but their canonical map still selected its historical installation
section. The canonical `recipe_map` entries for OpenResearch, Worktrunk and
Syft now select `recipes/README.md`, which carries 0.2.15, 0.80.0 and 1.54.0,
their primary sources and rollback versions. The audit's three
`native_integration.recipe_document` mirrors match. Syft's foundation recipe
uses the archive/checksum/extraction commands retained in its W1 receipt and
installed `gh release download` help. Its trading-owned 1.52.0 recipe stays a
dated owner handoff and is no longer the canonical current map.

Search-first used maintained native commands and existing repository checks;
no installer or acceptance runner was added. The first scoped ai-memory search
returned HTTP 404 in workspace `default`; retrying workspace `local` with limit
2 returned `decisions/workstation-sota-refresh-20260925.md`. That historical
0.14.1 lead was checked against the exact repository decision, the current base
rows, and the upstream v0.14.1 release and commit API responses. Installed CLI
help provides no pin-priority flag. Official documentation was read with native
`curl` after the web tool rejected `open`; no absence claim follows that failure.

The completeness critic covers all five threads, every current mcporter pin
site, reciprocal receipt links, recipe-map mirrors, generated reports, actual
timed outputs and owner boundaries. The next lifecycle sweep must qualify a
consistent mcporter dependency tree and persistent daemon/serve behavior; for
HUD it must cover declared/cached source synchronization, registry revision,
reload and rollback on an isolated host. Collector 0.162.0 traffic, restart and
retained storage remain pending. Source review, command help, ad-hoc stdio and
repository consistency checks retain their separate evidence scopes.

The independent completeness review found three additional current mcporter
sites: the native token CI pin, the token-report install/PATH recipe, and the
macOS/Linux lag test's current receipt link. Each now restores its `origin/main`
0.14.1 value while preserving the other W1 component changes. The snapshot's
retained-versus-latest classification now agrees with its 0.14.1 selection and
reported v0.14.2 release; its selected-commit API check was refreshed to
`93e0916cafe2d624b94271e31b75ca681a016514`. PR #642's title and description
now count eight moves and list mcporter as held, with the repair still awaiting
the coordinator's commit and push.

The required unchanged suite first exposed an environment boundary: its blind
exports were correctly refused under the existing Git markers in the available
temporary roots. The first Sol repair chose another writable root, which also
had a marker. That unresolved bounded repair triggered one Astra judgment at
`max`; it accepted installed Bubblewrap 0.9.0's supported private tmpfs after
both an unchanged successful-export test and an unchanged inside-repository
refusal test passed. The coordinator verified installed help, the
[release](https://github.com/containers/bubblewrap/releases/tag/v0.9.0) and
[tagged mount option reference](https://github.com/containers/bubblewrap/blob/v0.9.0/bwrap.xml#L273-L315).
The first full isolated run kept the worktree read-only and exposed the render
tests' legitimate temporary fixture writes. The final native wrapper keeps the
host read-only, binds the owned worktree and task cache writable, retains the
worktree `.git` as read-only, and provides a fresh `/tmp`. The tests and export
guard keep their bytes. The native `uv run --python 3.13 --with PyYAML==6.0.3`
environment repeats R642's dependency setup with a private cache and disabled
Python downloads. All failed conditions and the final returned results are
retained in [review-bot-repair-checks.json](../../evidence/artifacts/currency-wave-w1-20261003/review-bot-repair-checks.json); none is promoted to host or provider E2E. The final unchanged suite passed 325 tests with three optional skips. The eight repository validation/report checks and the three pre-push registry tests passed; the staged publication scan uses a temporary native Git index and pinned Gitleaks 8.30.1.

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

## Merge with main 14048b84, 2026-10-04

Main reached claude-hud 0.10.0 through #693 first, so this PR no longer moves
claude-hud. Its current stack, snapshot, token-efficiency and saturation rows and
installation recipe follow main's
[2026-10-04 qualification receipt](../../evidence/receipts/claude-hud-0100-qualification-20261004.json).
W1's [2026-10-03 HUD receipt](../../evidence/receipts/claude-hud-0100-qualification-20261003.json)
remains dated history, outside the component's current `evidence_ids`.

This merge also retains three W1 claude-hud integration edits: the guarded
`statusLine` command in `adoption/templates/claude.settings.template.json`,
the 0.8.0-to-0.10.0 existing-installation upgrade block in
`adoption/bootstrap.md`, and the guarded-template/M14 amendment link in
`docs/community-native-practice.md`. These edits have their W1 fixture and
source-review scopes; main's 2026-10-04 receipt remains the current selection
evidence. The bootstrap upgrade block still names host verification as pending.

RTK follows main at 0.51.0 and mcporter follows main at 0.14.2. W1 retains its
seven unique moves and their original 2026-10-03 receipts: jcodemunch-mcp
1.108.327, mcp-inspector 2.9.0, openresearch 0.2.15,
opentelemetry-collector-contrib 0.162.0, playwright-cli 0.1.22 (Playwright
1.64.0-alpha-1790635538000), syft 1.54.0 and worktrunk 0.80.0.
This merge maintains the foundation tools used to build complex projects and
support the north-star US-equities research and historical simulation.

W1's 2026-10-03 mcporter 0.14.2 hold reason remains recorded history: an
inconsistent resolved tree (bundled core 2.2.0 beside resolved server 2.3.0;
`npm ls --all` returned `ELSPROBLEMS`) and no persistent daemon/`serve`
qualification. The [compatibility-attempt receipt](../../evidence/receipts/mcporter-0142-qualification-20261003.json)
remains unchanged and outside mcporter's current `evidence_ids`. Whether #693's
2026-10-04 receipt addresses that hold belongs to that receipt's owner. This
merge follows main's selection without judging that qualification. Its
[mcporter receipt](../../evidence/receipts/mcporter-0142-qualification-20261004.json)
states these limitations verbatim:

- "No macOS execution and no upstream test suite run. The npm tarball hash is artifact evidence and does not pin the transitive dependency tree or rolldown platform binding."
- "Configured-server list/call failures are retained. The stale daemon was not recovered and keep-alive transport acceptance is not claimed; dist/daemon/client.js was recorded byte-identical across 0.14.1 and 0.14.2."
- "npm audit signatures --global failed with EAUDITGLOBAL (exit 1); only the later scratch-project audit succeeded. The ad-hoc MCP statistics are self-reports, not provider counts or savings."
- "The Mac keeps its separately qualified MCPorter 0.13.13 pin until a Mac qualifies 0.14.2. The platform-independent tarball artifact check is not Mac execution or Mac qualification."

The source comparison uses this worktree's merge-index stages 1, 2 and 3,
with PR head `4367dd46addc8fa424a754ee84b0167cfa8365b1` and main
`14048b840425c2569e0df60a6596e94e601da15b`. Component rows follow the policy
above; other changes retain both branches' nonconflicting edits. Summary
counters use main plus the check-entry delta contributed by the retained W1
rows: `api_commands` is 274 + 3 = 277, and
`selected_component_api_commands` is 257 + 3 = 260. The 2026-10-04 review
repair below records the correction to the original field-delta calculation.

Generated projections use the merged repository's supported generators and
documented default inputs. Correction to the receipt-generation assumption:
`build_new_wsl_handbook.py --help`, its `OUTPUTS` tuple and `main()` publish
only the Markdown and JSON handbook. The adjacent receipt's generator/profile
hashes, output hashes and inventory are refreshed from those generated outputs,
following `tests/test_new_wsl_handbook.py`'s committed-output receipt assertions;
its historical validation results retain their original scope.

Completeness critic: compare all three main-moved rows against stage 3 across
all four component sources, retain all seven W1 rows and receipt bytes from
stage 2, union the writer-identity test's dynamic collector selection with
main's lane assertions, regenerate dependent projections, and preserve main's
manifest registrations before registering every file differing from main.
No new upstream adoption or landscape judgment is made in this bounded offline
merge; the dated mcporter hold and main receipt limitations remain inputs to
their owners' next qualification sweep.


## Merge review repair, 2026-10-04

The review of `4c468bb38305166129bf15ac03a309efdd047fb9` found stale current
mcporter wording in the W1 bootstrap paragraph, outdated HUD selection
attribution in the community row, and missing W1 command-count deltas. The
bootstrap paragraph now states W1's 2026-10-03 hold as history and points to
main's 2026-10-04 mcporter selection and receipt limitations. The community
row credits main's #693 HUD selection and keeps the W1 link for the guarded
template and M14 amendment. Both 2026-10-03 receipts retain their original
bytes and dated scopes. This repair supports the same foundation tooling and
north-star research action named above.

Correction and verification path: the first merge used changes in the summary
counter fields as the W1 delta, although W1 had not updated those fields.
Read `catalogs/landscape/upstream-snapshot.json` directly with `git show` at
W1 `4367dd46addc8fa424a754ee84b0167cfa8365b1`, main
`14048b840425c2569e0df60a6596e94e601da15b`, and their common base
`59f8a1e36e1f2870d9de18a16c42f1e72cdae1c6`. The mcp-inspector,
opentelemetry-collector-contrib and playwright-cli rows already match W1
exactly: each has four checks in W1 and three in main and the base. Their
fourth `commits/<tag>` checks resolve release tags to commits and originated
in W1, rather than in the merge.
Main did not change those rows. Retain those exact W1 rows and add their
three checks to main's counters, producing 277 and 260. No new API calls
were made for this repair.

At the October 4 review repair, the retained arrays contained 261 check
entries, compared with 258 at main `14048b84`. Main's [#637 recount](https://github.com/seathatflowsinourveins/native-agent-stack/pull/637)
subsequently reconciled the earlier one-entry discrepancy. At main
`4c897418f`, selected-component commands are 264 and all recorded API commands
are 281. Retaining W1's three checks gives 264 + 3 = 267 and 281 + 3 = 284.
The current selected-component array contains 267 checks and matches its
summary; the earlier discrepancy is historical, not carried forward.

Completeness critic: inspect the 55 pre-repair paths, plus
`docs/harness-defaults.md` added by this repair, for the same
current-tense pin contradiction, while recognizing dated decisions and
qualification artifacts as history. The operational mcporter paragraph and
HUD row were the remaining matching statements. Compare all seven retained
snapshot rows to W1 and main's moved rows to main, regenerate the handbook
from its supported default inputs, verify its receipt hashes, run the named
acceptance checks, and report the names and reasons of any skipped tests.
The general lesson is to compare native check entries before trusting unchanged
summary fields, and to review current guide wording alongside selection rows.


## Merge with main 38ac9aca, 2026-10-04

The landing merge incorporates main
`38ac9aca114ad9ef4a15d8620d947eb5c2f518c3` into PR head
`7969c61479566bc5ee3a0c4ea7d4549c94e67544`. The anti-pattern table keeps
W1's two rows first and main's ten newly inserted rows immediately after,
with every row intact. The handbook uses the merged sources and the supported
default generator inputs; its receipt preserves historical validation scope
while following the generated output hashes. The nine W1 receipt registrations
are restored alongside all of main's registrations. This maintains the native
foundation tooling for the north-star research action named above.

The October 4 amendment under the decision headline points readers from the
original eight-move/hold decision to the seven retained W1 moves and main's
#693 selections. The bootstrap HUD upgrade block cites the observed
2026-10-04 host remove/add/install path and that receipt's limitations, while
keeping W1's marketplace-update/plugin-update path explicitly unverified.

Correction verification: read the fourth check's `endpoint` in the original
W1 snapshot at `4367dd46addc8fa424a754ee84b0167cfa8365b1`. The three endpoints
use release tags (`2.9.0`, `v0.162.0` and `v0.1.22`), so the review repair now
names `commits/<tag>` and describes the tag-to-commit lookup. The preceding
repair inspected 55 pre-repair paths and added `docs/harness-defaults.md`,
producing 56 paths against `14048b84` at `7969c614`; its completeness wording
now states both parts of that scope.

Completeness critic: retain both sets of exact anti-pattern rows, preserve
all main evidence registrations and all nine W1 receipt records, check the
seven W1 moves and main's component selections, regenerate stale projections
from merged sources, and run the named acceptance checks with skipped tests
reported by name and reason. Historical host observations and the unverified
W1 update path retain their original qualification limits.

## Merge with main e871259ea and 4c897418f (2026-10-05)

Merge 2 incorporated main `e871259ea` and was committed as `66c94a37f`;
merge 3 incorporated main `4c897418f` and was committed as `f640b5309`.
PR head `64c410699` has the same tree as the merge-3 commit. These merges
retain the seven W1 currency moves while following main for its newer
selections and the NativeStack2604 fix wave. This record serves the same
native foundation for the north-star research action named above.

The code-index owner rows now follow jcodemunch-mcp **1.108.327**, source
`6d5ae86c130f96624e2ca2d797fa3b853c210b9d`, selected by W1. Merge 2's
`test_owner_pins_are_the_repository_pins` failure forced the alignment:
[tests/test_new_wsl_definitive_defaults.py:1336](../../tests/test_new_wsl_definitive_defaults.py#L1336)
requires owner rows to name the pin in `manifests/stack.json`. Main already
uses this precedent for RTK: the dated owner record's row at
[docs/decisions/2026-10-04-token-full-stack-owner-default.md:108](2026-10-04-token-full-stack-owner-default.md#L108)
names 0.50.0, while its "Refresh onto main after PR #693" section and main's
owner row follow 0.51.0. The older decision stays historical. The configuration
owner's decision record is unchanged by this repair; its wording and any
acknowledgement remain with that owner and the coordinator.

This PR now edits these configuration-owner files, superseding the earlier
scope statement retained above as dated history:

- `adoption/new-wsl-profile.json`: the jcodemunch-mcp entry.
- `evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json`: the wave3 code-index owner row; main's wave4 Promptfoo owner is preserved.
- `evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json`: regenerated from the merged consensus.
- `docs/decisions/2026-10-01-new-wsl-definitive-defaults.md`: the tables rendered from that manifest.
- `evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json`, `owners.json`, `install.sh` and `accept.sh`: the code-index owner, install/list/version commands and source citations.
- `evidence/artifacts/new-wsl-install-plan-20261002/README.md` and `SOURCES.md`: the current code-index pin, wave-3 refresh and verified source locations.

Main's 25 fix-wave slot repairs and wave4 Promptfoo 0.123.1 owner survive.
The current configuration-owner handoff is only playwright-cli **0.1.21** in
the profile against **0.1.22** in the stack. Syft **1.54.0** and mcporter
**0.14.2** now match through main #684/#704; this PR sets the jcodemunch-mcp
entry to **1.108.327**. These are selection and scope statements, not new
host acceptance.

Main's [#637 recount](https://github.com/seathatflowsinourveins/native-agent-stack/pull/637)
reconciled the old summary discrepancy. Main supplies 264 selected-component
commands and 281 total API commands; W1 retains three additional checks.
The merged counters are **264 + 3 = 267** and **281 + 3 = 284**, and the
selected-component array has exactly 267 checks. No API refresh ran here.

The handbook receipt's two merge entries are retained: validation[6] records
merge 2's `--write` at `2026-10-05T01:51:22.461149+00:00`, and validation[7]
records merge 3's `--write` at `2026-10-05T03:39:08.219114+00:00`. Both
recorded exit 0 and status `written`; those historical codes are unchanged.
Each `date_utc` now follows its own UTC timestamp, **2026-10-05**. Their
scopes describe regeneration, rather than claiming a check from `--write`.
A separate validation[8] records today's actual `--check`, with its returned
status, exit code and output hashes; the date is taken from `date -u`.

The jcodemunch README read on 2026-10-05 at 6d5ae86c and prior pin 8f7b34ab
confirms identical install, version and session-stats lines 91, 113 and 141;
these anchors did not move. The plan now cites the ecosystem root and
`--python 3.13` at `recipes/README.md:554-559`, plus `--version` at line 560,
at the immutable merge-3 commit. The profile and executable source anchors
remain unchanged because the read verified them.

Completeness critic: distinguish historical scope from the files the PR now
edits; preserve the configuration owner's reserved record; verify current
pins and source anchors, main's repair slots and Promptfoo owner, reconciled
command counts, actual receipt dates and returned generator statuses. Rebuild
the manifest, tables and handbook with their own generators, run the named
local acceptance checks, and re-register changed files after all mutations.
