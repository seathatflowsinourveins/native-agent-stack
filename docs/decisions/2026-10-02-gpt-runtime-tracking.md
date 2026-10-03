# Decision: track GPT runtime workers, SDKs, the gateway, harnesses and pi in the daily catalog report (2026-10-02)

Lane: foundation. North-star action: keep the GPT-route runtime that the foundation and the trading north star run
on compared with upstream every day, so a new release, a dormant upstream or a moved pin record shows up without a
manual sweep.

## Request and gap

The user asked on 2026-10-02, and again on 2026-10-03, to keep tracking the GPT-powered runtime workers, the SDKs,
pi and related tools.

The [catalog-freshness workflow](../../.github/workflows/catalog-freshness.yml) (daily since the
[currency decision](2026-10-02-daily-catalog-currency.md)) compares pins with upstream for what
`tools/sota-convergence/extract_layers.py` extracts: the `manifests/stack.json` components, the selected
`catalogs/us-equities` cards and the three `TRADING_PIN_SOURCES`. At `56473e4b` it read no runtime record of the new
distribution, so none of the target pins of the GPT route was compared. By row kind:

| Row kind at `56473e4b` | GPT-route repositories |
| --- | --- |
| Pinned foundation component (drift table) | `openai/codex` (`codex`, 0.159.3), `diegosouzapw/OmniRoute` (`omniroute`, 3.8.50), `promptfoo/promptfoo`, `openai/codex-plugin-cc` |
| Selected trading card (drift and trading tables) | `codex-native-sdk` and `inspect-ai` (`default`); `codex-acp`, `omniroute`, `deerflow` and `langgraph` (`conditional`) |
| Fetched, no pin row (alternative card or star list) | `openai/openai-agents-python` and `anthropics/claude-agent-sdk-python` (`alternative` cards), `earendil-works/pi`, `assafelovic/gpt-researcher`, `OpenHands/OpenHands`, `can1357/oh-my-pi` (star list) |
| Not fetched | `OpenHands/software-agent-sdk`, `harbor-framework/harbor`, `openai/openai-python`, `openai/openai-agents-js` |

A card's pin is the catalog's, not the runtime record's: the OmniRoute card says v3.8.50 while the install plan
installs v3.8.51. The architecture edition's hand-written `upstream_currency` cells (checked 2026-10-01T07:41Z) were
already behind upstream for the OpenHands SDK (v1.49.6 against v1.50.1), OmniRoute (3.8.50 against v3.8.51) and
Codex (0.159.2 against rust-v0.159.3) in `catalogs/foundation/new-wsl-architecture-20261001.json`.

## Decision

Extend the existing job's inputs; add no tool, service, schedule or job. The change follows the reviewed
`TRADING_PIN_SOURCES` precedent of the same pipeline:

- `extract_layers.py` declares `RUNTIME_PIN_SOURCES` (12 pins read from their source records at extraction time,
  never copied) and `RUNTIME_WATCH_SOURCES` (7 upstreams that no install or runtime record on `main` pins) and
  writes `runtime-pins.json`. A pin source reads its record in one of three forms: an RFC 6901 pointer (as the
  trading pins do), a row of a JSON array selected by key (the install plan's `owners[]` by `slot`, so an inserted
  or reordered row does not retarget it; a composite row is split on `;` and its part chosen by repository), or a
  `name==version` line of a pip constraints file (PEP 503 names). A declaration error raises, because only a code
  edit can cause one. A record that moved does not: the entry is written with `"pin": null` and an `error`, so the
  daily job keeps its foundation and trading report.
- `github_freshness.py` fetches the repositories of `runtime-pins.json` with the other working files.
- `build_manifest.py --runtime-freshness-out` writes the report-only `runtime-freshness.json` (schema
  `runtime-freshness/1`) with the manifest's own `compute_upstream`, `classify_pin` and `compute_dormancy`. Watch-only
  and unresolved rows are `not_compared`. The manifest and the trading sidecar are byte-identical with or without
  the flag. If a runtime upstream's own data trips the leak gate, only this sidecar is withheld (no entries and a
  fixed `gate_error`); the manifest's and the trading sidecar's leak checks stay fatal.
- `scripts/freshness_propose.py` appends a "GPT runtime workers, SDKs and agents" table to `drift.md`. The table
  never changes `drift-status.txt`, the drift table, a receipt or the propose job.
- The workflow passes the flag, prints the runtime counts and uploads the sidecar with the other artifact files.

| id | group | pin source at `56473e4b` | pin |
| --- | --- | --- | --- |
| `new-wsl:codex` | native-client | install plan, slot `codex` (`version_pinned` false: the reviewed release of a self-updating client) | rust-v0.160.0 |
| `new-wsl:codex-sdk` | agent-sdk | install plan, slot `codex-sdk-and-codex-exec-app-server` | rust-v0.160.0 |
| `new-wsl:claude-agent-sdk` | agent-sdk | install plan, slot `claude-agent-sdk` | v0.2.163 |
| `new-wsl:omniroute` | gateway | install plan, slot `gpt-gateway` | v3.8.51 |
| `new-wsl:openhands-sdk` | runtime-worker | install plan, slot `agent-runtime-worker` | v1.50.1 |
| `new-wsl:gpt-researcher` | runtime-worker | install plan, slot `research-harnesses`, first part | v3.7.0 |
| `new-wsl:deer-flow` | runtime-worker | install plan, slot `research-harnesses`, second part | v2.1.0 |
| `new-wsl:harbor` | evaluation-harness | install plan, slot `harbor-containerized-agent-e2e-runner` | v0.23.0 |
| `new-wsl:inspect-ai` | evaluation-harness | install plan, slot `inspect-ai` | 0.3.273 |
| `recipe:openhands-sdk` | runtime-worker | `blueprints/runtime-workers/openhands/pins.json` `/tag` | v1.49.6 |
| `sdk-lock:openai-codex` | agent-sdk | `adoption/sdk/accepted-constraints.txt` | 0.159.3 |
| `sdk-lock:openai` | model-sdk | `adoption/sdk/accepted-constraints.txt` | 3.16.2 |
| `watch:pi` | coding-agent | none on `main` (trial pin on PR #524) | none |
| `watch:oh-my-pi` | coding-agent | none | none |
| `watch:openai-agents-python` | agent-sdk | none (its `alternative` card records an evaluated v0.22.3) | none |
| `watch:openai-agents-js` | agent-sdk | none (named in this record) | none |
| `watch:crawl4ai` | runtime-worker | none on `main` (recipe on PR #428) | none |
| `watch:deepagents` | runtime-worker | none on `main` (recipe on PR #566) | none |
| `watch:codex-action` | ci-action | none on `main` (PR #550) | none |

## Pin of record

The install plan (`evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json`) is the new distribution's
reviewed record of what it installs, so its rows are the target pins. A test reads `PLAN_REL` from
`tools/adoption/new_wsl_client_config.py` and requires the tracker's path to equal it, so a new plan revision moves
the client configuration tool and the tracker together. The open layer-consensus pull request #620 revises the
plan in place (64 to 69 rows); at its head `fd111e59` the eight tracked slots keep their repositories and releases
and no slot repeats.

The recipe pin record and the SDK constraints are the older host's records; they stay tracked as separate rows
because their pins differ from the plan's (OpenHands v1.49.6 against v1.50.1, `openai-codex` 0.159.3 against
0.160.0). The open pull request #626 moves the constraints to 0.160.0; the row reads the file by requirement name,
so it follows. On this distribution (2026-10-03) the installed versions matched the plan: OpenHands SDK 1.50.1,
Codex SDK 0.160.0, Claude Agent SDK 0.2.163, GPT Researcher v3.7.0, DeerFlow v2.1.0, OmniRoute 3.8.51, Harbor 0.23.0
and Inspect AI 0.3.273, read from the tool root's environments and checkouts. That is one host's local observation,
not acceptance.

## Ownership and the neighbouring runtime catalog

The Codex maintenance task owns material upstream detection (`catalogs/foundation/automation.json`, the gh-aw
entry), and each dependency has one updater (`docs/github-automation.md`). This table is a deterministic report that
the owner and the user read; it opens no pull request and changes no pin.

The open pull request #633 (Codex lane) adds `catalogs/foundation/runtime-jobs.json`, eight runtime jobs with the
source pins their reviews read (pi v1.0.0, Inspect AI 0.3.276 and others), and has the runtime-worker freshness
workflow fetch their repositories' metadata daily with `github_freshness.py`. That workflow compares no pin and
renders no table; this record's table compares install and runtime records. When #633 lands, its catalog is a pin
record on `main`, so `watch:pi` and other watch-only rows can be promoted to `RUNTIME_PIN_SOURCES` with a pointer
into it, if its owner agrees that its source pins are the ones to compare.

## Search-first

When the tool choice was made (2026-10-02, about 23:50Z) `search-first` and `find-skills` were not installed on this
distribution: the Skill tool answered "Unknown skill" and `~/.claude/skills` held neither, so the alternatives were
compared directly (Renovate, Dependabot, updatecli, nvchecker). Another session installed both at about 01:15Z on
2026-10-03, and `search-first` then ran in full mode on the built change (workflow `wf_21fc37c5-123`: three
discovery lanes, an evaluator that re-verified every claim it used, and a completeness critic). Its decision:
extend the existing job. Trials ran on copies of the real records and installed nothing outside a scratch directory:

- [updatecli](https://github.com/updatecli/updatecli) v0.122.0 (Apache-2.0): `updatecli pipeline diff` reads every
  pin shape in place (a dasel selector on `owners`, the composite row through a templated target, `file`
  `matchpattern` on the constraints) and has `pypi`, `npm`, `gittag` and `vulnerability/osv` sources. It adds a
  137 MB Go binary to a stdlib-only job, reported a failed source as "Skipped" with exit 0, and none of the 37 resource
  kinds at v0.122.0 emits an archived flag or commit-based dormancy.
- [Renovate](https://github.com/renovatebot/renovate) 44.132.2 (AGPL-3.0-only): `renovate --platform=local` with
  `--report-type=file` read the records through JSONata custom managers and found the same pins behind. It needs
  Node ^24.11.0 with 123 direct dependencies or a container, a GitHub token for its GitHub datasources, and has no
  archived flag.
- [nvchecker](https://github.com/lilydjwg/nvchecker) 2.22 (MIT) reads pins only from its own `oldver` file, failed
  on the `@openai/codex` npm packument (its npm source reads the first 1,024 bytes), and has no archived flag.
- Dependabot outputs pull requests, which a report-only job must not open, and it reads no install-plan row.
- Hosted services and other classes were checked and add nothing here: Repology, release-monitoring.org,
  libraries.io, newreleases.io, endoflife.date (none of the 19 components), package-version MCP servers,
  Dependency-Track and GUAC (recorded `discovery_only` on 2026-09-21), zeitgeist and pip-abandoned (references for a
  declared inventory and a batched archived query, not replacements). deps.dev and ecosyste.ms offer registry
  versions and advisories, which this table leaves to the follow-ups under "Limits and open findings".

The sweep measured one verdict that this table misses: Inspect AI has no GitHub release, the tag fallback returns
the first tag in name order (`release/2025-11-28`), so the row is not compared, while its newest version tag and its
PyPI release are 0.3.276 against the pin 0.3.273. The declared tag patterns (see "Limits and open findings") close
that gap. A local run on 2026-10-03 at 05:13Z (this distribution, read-only `gh`, a work directory holding only
`runtime-pins.json`, then `build_runtime_freshness`) listed 274 Inspect AI tags, 269 of which match its pattern, and
compared the pin 0.3.273 with 0.3.276: behind. The same run selected v1.12 for `watch:codex-action` (13 matching tags)
and `deepagents==0.7.21` for `watch:deepagents` (76), which stay watch-only and not compared. That is one local
run, not a hosted scheduled run.

Overturn: adopt updatecli or Renovate instead of this extension only if the stdlib-only constraint is relaxed and,
on the same 19 rows plus 10 deliberately outdated canaries and 10 current controls over 7 daily runs, the tool
reproduces every behind and not-compared verdict, reports no silently skipped source, and supplies the archived flag
and 180-day release-or-commit dormancy. Revisit the REST fetch if the daily run returns rate-limit errors.

## First run

Evidence class: local integration. An independent verifier ran the workflow's own steps on this distribution at
`6bc1199b` against live GitHub metadata on 2026-10-03 (`checked_at` 2026-10-03): `extract_layers.py`, then
`github_freshness.py` (488 repositories, 0 errors, 0 partial errors), then `build_manifest.py` with both sidecar
flags, then `build_drift_report`. That is not a hosted scheduled run.

| id | pin | upstream latest | behind |
| --- | --- | --- | --- |
| `new-wsl:codex` | rust-v0.160.0 | rust-v0.160.0 | no |
| `new-wsl:codex-sdk` | rust-v0.160.0 | rust-v0.160.0 | no |
| `new-wsl:claude-agent-sdk` | v0.2.163 | v0.2.163 | no |
| `new-wsl:omniroute` | v3.8.51 | v3.8.51 | no |
| `new-wsl:openhands-sdk` | v1.50.1 | v1.50.1 | no |
| `new-wsl:gpt-researcher` | v3.7.0 | v3.7.0 | no |
| `new-wsl:deer-flow` | v2.1.0 | v2.1.0 | no |
| `new-wsl:harbor` | v0.23.0 | v0.23.0 | no |
| `new-wsl:inspect-ai` | 0.3.273 | none (tag `release/2025-11-28` withheld) | not compared (unversioned) |
| `recipe:openhands-sdk` | v1.49.6 | v1.50.1 | yes |
| `sdk-lock:openai-codex` | 0.159.3 | rust-v0.160.0 | yes |
| `sdk-lock:openai` | 3.16.2 | v3.24.0 | yes |
| `watch:pi` | none | v1.0.0 | not compared (watch-only) |
| `watch:oh-my-pi` | none | v18.5.0 | not compared (watch-only) |
| `watch:openai-agents-python` | none | v0.23.1 | not compared (watch-only) |
| `watch:openai-agents-js` | none | v0.18.0 | not compared (watch-only) |
| `watch:crawl4ai` | none | v0.9.4 | not compared (watch-only) |
| `watch:deepagents` | none | `deepagents==0.7.21` | not compared (watch-only) |
| `watch:codex-action` | none | v1.12 (tag listing; no releases) | not compared (watch-only) |

Counts: 19 entries, 12 pin sources, 7 watch-only, 0 unresolved, 3 behind, 8 not compared, 0 dormant, 0 archived.
The three rows behind are the older host's records. The new distribution's install-plan pins equal upstream's
latest release, except Inspect AI, which this run could not compare (see "Search-first"). `drift-status.txt` was
`true` from the 40 drifted manifest rows and was the same with and without the runtime sidecar; rebuilt without the
new flag, the manifest and the trading sidecar were byte-identical.

## Verification

All commands ran on this distribution (Claude Code 2.1.288, Python 3.13). Builds came from a written contract; an
independent verifier re-ran each claim, and evidence and security reviewers read the diff against source.

- `python3 -m unittest tests.test_catalog_freshness_runtime -v`: 53 tests OK, none skipped. The
  `watch:openai-agents-js` `named_in` check, skipped until this record existed, now runs against it and passes.
- `python3 -m unittest tests.test_catalog_freshness_trading tests.test_catalog_freshness_propose
  tests.test_catalog_freshness_pins tests.test_sota_convergence tests.test_practice_references`: 308 tests; before the
  evidence registration its only failure was the publication validator's hash check of the six edited registered
  files.
- The three builder registry tests: OK, none skipped (zizmor 1.30.1 on `PATH`). `actionlint` 1.17.0 and `zizmor`
  on the workflow: no findings, the same 3 suppressed as at the base.
- Full suite at `6bc1199b`: 9,846 tests, 26 failures. Rerun at the base `56473e4b`, the same failures recur
  (adoption bootstrap and macOS tests that need tools this distribution lacks, and a cross-device `git clone
  --local` from this worktree into tmpfs), except the hash check above.
- Mutation checks: each new test failed when the behaviour it names was removed (a swapped slot, unnormalized
  requirement names, an unreserved trading id, the runtime-only leak catch removed or widened to the trading
  sidecar, the report ignoring the withheld marker, a caught exception printed to stderr).
- Review: no blocking or major finding; the minor findings (leak-gate isolation, a slot test that could not see a
  swap, the watch-only wording) and the nits were fixed and re-reviewed.

## Limits and open findings

- Report-only. The runtime rows are not in the manifest, so the saturation ledger, the landscape sweep, the
  receipts and the propose pull request never see them. They live in `drift.md`, the run's step summary and the
  30-day artifact.
- Tag-only upstreams. When a repository has no release, `github_freshness.py` takes the first tag in the API's name
  order, and a monorepo's latest release can be another package's. That withheld Inspect AI and left
  `watch:codex-action` and `watch:deepagents` on name order or on whichever package released last. These three rows
  now declare a literal tag prefix and an anchored pattern with one capture group: `new-wsl:inspect-ai` over all
  tags (so a future 1.x is not missed), `watch:codex-action` over `v` and `watch:deepagents` over `deepagents==`.
  `github_freshness.py` lists those tags through GitHub's `git/matching-refs` endpoint, and `build_runtime_freshness`
  keeps the names the pattern fully matches and takes the highest version by its parsed capture, never by name
  order (the API's order puts 0.3.99 after 0.3.276), as
  [nvchecker's GitHub source](https://github.com/lilydjwg/nvchecker/blob/v2.22/nvchecker_source/github.py)
  (`use_max_tag` with `include_regex`) and Renovate's `github-tags` datasource do. The pattern drops prereleases and
  other packages' tags, and its capture strips a prefix such as `deepagents==`. Every other row keeps the
  release-or-first-tag rule until it declares a pattern. A failed `matching-refs` call is a partial error of that
  repository, as a failed release or tag call is, so that run blanks the row and does not open the propose pull
  request.
- Registry versions and advisories are outside this table. A registry identity per row (the PyPI simple JSON API,
  which also carries PEP 792 project status) would compare Inspect AI and `openai-codex` by their own stream; note
  that `gpt-researcher` is 0.16.1 on PyPI while its pinned tag is v3.7.0. Advisories stay with OSV-Scanner, the
  repository's single alert path; a generated purl SBOM of the runtime pins is the way to cover the URL-pinned
  OpenHands SDK.
- One runtime-only upstream whose data trips the leak gate withholds the whole runtime table for that run; the
  drift table and `drift-status.txt` are unaffected.
- Watch-only rows report upstream activity and are never compared. Promote an entry to `RUNTIME_PIN_SOURCES` when an
  install or runtime record on `main` pins it (#524 for pi, #428 for crawl4ai, #566 for Deep Agents, #550 for
  codex-action, or #633's runtime-job catalog). The `alternative` trading card `openai-agents-sdk` records an
  evaluated v0.22.3, which no table compares, because the manifest rows only `default` and `conditional` cards.
- Cross-stream rows: `sdk-lock:openai-codex` compares the PyPI SDK version with openai/codex's Rust release tags,
  and `new-wsl:codex-sdk` follows the same tags. The numbers line up at 0.159.3 and 0.160.0 (`adoption/sdk/README.md`;
  the npm `@openai/codex-sdk@0.160.0` of the plan's command) but are separate streams.
- Model routes (`gpt-6.1-sol`, `gpt-6-astra`) are not GitHub repositories and are not tracked here. The gateway's
  running source build with local patches has no version field; the row tracks the plan's release.
- Pre-existing and unchanged here: `manifest_component_rows` in `scripts/freshness_propose.py` keys rows by id, so
  the trading `omniroute` row shadows the foundation `omniroute` row in the drift comparison.
- The architecture edition's `upstream_currency` cells stay dated snapshots. The daily table supersedes them as an
  observation; it does not edit them.
- The first hosted run is unobserved until after merge: the next 06:17 UTC schedule on `main`. No scheduled daily run
  had executed when this record was written; the last scheduled run was on 2026-09-28.

## Correction recorded

During this unit a coverage statement named pi, the OpenAI Agents SDK and DeerFlow as tracked only as starred
names or not at all. DeerFlow is a selected (`conditional`) trading card with a pin row, and
`openai/openai-agents-python` is an `alternative` card that the job fetches without a pin row. The completeness
critic found it. The row-kind table above is the corrected statement, and the anti-pattern log in
[`docs/harness-defaults.md`](../harness-defaults.md#anti-pattern-log) records the lesson.

## Sources

- Precedent: `tools/sota-convergence/extract_layers.py` `TRADING_PIN_SOURCES` and `resolve_trading_pins`,
  `build_manifest.py` `build_trading_freshness`, `scripts/freshness_propose.py` `render_trading_markdown`, all at
  `56473e4b840f0e6940c031801d866e7e9bf29baf`.
- Pin records at `56473e4b`: `evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json` (rows by `slot`),
  `blueprints/runtime-workers/openhands/pins.json`, `adoption/sdk/accepted-constraints.txt`.
- Tracked upstreams: [openai/codex](https://github.com/openai/codex),
  [anthropics/claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python),
  [diegosouzapw/OmniRoute](https://github.com/diegosouzapw/OmniRoute),
  [OpenHands/software-agent-sdk](https://github.com/OpenHands/software-agent-sdk),
  [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher),
  [bytedance/deer-flow](https://github.com/bytedance/deer-flow),
  [harbor-framework/harbor](https://github.com/harbor-framework/harbor),
  [UKGovernmentBEIS/inspect_ai](https://github.com/UKGovernmentBEIS/inspect_ai),
  [openai/openai-python](https://github.com/openai/openai-python),
  [earendil-works/pi](https://github.com/earendil-works/pi), [can1357/oh-my-pi](https://github.com/can1357/oh-my-pi),
  [openai/openai-agents-python](https://github.com/openai/openai-agents-python),
  [openai/openai-agents-js](https://github.com/openai/openai-agents-js),
  [unclecode/crawl4ai](https://github.com/unclecode/crawl4ai),
  [langchain-ai/deepagents](https://github.com/langchain-ai/deepagents),
  [openai/codex-action](https://github.com/openai/codex-action).
- Alternatives at the versions trialed: [updatecli v0.122.0](https://github.com/updatecli/updatecli/releases/tag/v0.122.0),
  [Renovate 44.132.2](https://github.com/renovatebot/renovate/releases/tag/44.132.2) and its
  [local platform](https://github.com/renovatebot/renovate/blob/44.132.2/lib/modules/platform/local/readme.md),
  [nvchecker v2.22](https://github.com/lilydjwg/nvchecker/tree/v2.22).
- [GitHub REST: get the latest release](https://docs.github.com/en/rest/releases/releases#get-the-latest-release) and
  [list matching references](https://docs.github.com/en/rest/git/refs#list-matching-references);
  [PEP 503 normalized names](https://peps.python.org/pep-0503/#normalized-names);
  [PEP 691](https://peps.python.org/pep-0691/) and [PEP 792](https://peps.python.org/pep-0792/);
  [RFC 6901](https://www.rfc-editor.org/rfc/rfc6901).
