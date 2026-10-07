# Keep the OmniRoute workhorse on Lite; isolate hosted search in an opt-in profile

Date: 2026-10-06. Lane: foundation. Status: source-reviewed decision;
opt-in application and native search acceptance pending.

The north-star action is reliable web discovery for engineering and US-equities
R&D without changing the established GPT workhorse's behavior on every turn.

The workhorse profile keeps its bundled Responses Lite model metadata, both
standalone-search switches false, and the new-WSL map's `web_search = "disabled"`.
A separate `omniroute-search` profile selects hosted search with
`web_search = "live"`, both standalone switches false and an absolute
`model_catalog_json` path. Its catalog copies the installed CLI's bundled export
and changes only `use_responses_lite` to false. The CC applies that opt-in profile
and runs one native known-answer search after review; currency prepares the
packet and records. This decision supersedes the earlier proposal to disable
Lite on the workhorse profile.

## Why the profiles are separate

At [openai/codex@a956835d, rust-v0.160.0,
`core/src/tools/spec_plan.rs:626-648`](https://github.com/openai/codex/blob/a956835d/codex-rs/core/src/tools/spec_plan.rs#L626-L648),
Lite omits hosted tools. At
[`spec_plan.rs:1038-1046`](https://github.com/openai/codex/blob/a956835d/codex-rs/core/src/tools/spec_plan.rs#L1038-L1046),
Lite selects the standalone executor whenever that executor is available.
The provider's `supports_standalone_web_search` flag controls its availability
for this custom provider
([`ext/web-search/src/extension.rs:42-53`](https://github.com/openai/codex/blob/a956835d/codex-rs/ext/web-search/src/extension.rs#L42-L53)).
Standalone search targets the provider-relative `alpha/search`
([`codex-api/src/endpoint/search.rs:14-15`](https://github.com/openai/codex/blob/a956835d/codex-rs/codex-api/src/endpoint/search.rs#L14-L15)).

Lite also changes ordinary turns: reasoning context is `all_turns`, while
non-Lite omits the parameter and uses the server's current default;
instructions and tools move into developer input items; and parallel tool calls
are disabled. The exact sources are
[`core/src/client.rs:863-882`](https://github.com/openai/codex/blob/a956835d/codex-rs/core/src/client.rs#L863-L882),
[`client.rs:902-938`](https://github.com/openai/codex/blob/a956835d/codex-rs/core/src/client.rs#L902-L938)
and [`client.rs:989-995`](https://github.com/openai/codex/blob/a956835d/codex-rs/core/src/client.rs#L989-L995).
The model configuration override function exposes no independent override for
the Lite flag
([`models-manager/src/model_info.rs:19-60`](https://github.com/openai/codex/blob/a956835d/codex-rs/models-manager/src/model_info.rs#L19-L60)).
Changing that flag on the workhorse would therefore make an unmeasured change
to every turn. The opt-in profile confines that change to discovery sessions.

The latest official OmniRoute release observed on 2026-10-06 is
[v3.8.51](https://github.com/diegosouzapw/OmniRoute/releases/tag/v3.8.51),
published 2026-09-30. At its selected source pin
`c1e30b7676975feb298b49eff6ff58923c04b89e`, hosted `web_search` and
`web_search_preview` are retained by tool normalization
([`open-sse/executors/codex/tools.ts:6-21`](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/executors/codex/tools.ts#L6-L21),
[`tools.ts:194-206`](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/executors/codex/tools.ts#L194-L206)).
The clean gateway's missing `/v1/alpha/search` route was independently observed
as HTTP 404 with `not_found` / `unknown_route`; that matches the pinned
[catch-all route:16-42](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/src/app/api/v1/%5B...omnirouteCatchAll%5D/route.ts#L16-L42).
[PR #13788](https://github.com/diegosouzapw/OmniRoute/pull/13788) remains OPEN
with zero submitted reviews at the observation. Its proposed standalone route
is not a shipped-release capability. The patched legacy gateway is separate
evidence and does not establish that capability on the clean release.

## Catalog provenance and upgrade condition

The installed CLI is 0.160.1. Its
[release notes](https://github.com/openai/codex/releases/tag/rust-v0.160.1)
describe the Windows remote-MCP environment fix. The cited transport and
catalog source files retain the 0.160.0 behavior; the bundled source JSON has
SHA256 `fd219bd9f061278275f528939f82f54d2eb97df4b25c23b022adbe48813d920b`
and was found byte-for-byte in the installed binary.

Use the supported `codex debug models --bundled` command for regeneration.
The branch calls `bundled_models_response()` before any config/auth loading
([`cli/src/main.rs:2068-2095`, rust-v0.160.1](https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/cli/src/main.rs#L2068-L2095));
that function reads the embedded JSON
([`models-manager/src/lib.rs:12-16`](https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/models-manager/src/lib.rs#L12-L16)).
The unchanged upstream test seam is
[`cli/tests/debug_models.rs:12-24`](https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/cli/tests/debug_models.rs#L12-L24);
this lane inspected it and did not run that upstream test suite.

The native command serializes the deserialized `ModelsResponse`, rather than
returning the embedded file's original bytes. It normalizes legacy fields and
emits compatibility instructions
([`protocol/src/openai_models.rs:840-943`](https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/protocol/src/openai_models.rs#L840-L943)).
An initial equality check against the old raw-source projection exited 1;
the native export was then used as the regeneration baseline. No normalization
is reimplemented locally. The regenerated projection preserves every native
export field except the Lite flags.

| Artifact | SHA256 | Scope |
| --- | --- | --- |
| Embedded raw catalog | `fd219bd9f061278275f528939f82f54d2eb97df4b25c23b022adbe48813d920b` | Source JSON, verified inside installed binary |
| Native `--bundled` export | `262dc36e0e7beb290aef8196bd59f42acf51647b8f7b68dafa533ae7742019e6` | Installed CLI serialization |
| Opt-in projection | `252a88f068e37d646281fce36982876274c0c483012cba83b048c11dde463419` | 11 models; only 10 true Lite flags changed |

`model_catalog_json` loads a complete catalog at startup
([`core/src/config/mod.rs:2143-2171`](https://github.com/openai/codex/blob/a956835d/codex-rs/core/src/config/mod.rs#L2143-L2171)),
and the static manager keeps that catalog authoritative
([`models-manager/src/manager.rs:757-827`](https://github.com/openai/codex/blob/a956835d/codex-rs/models-manager/src/manager.rs#L757-L827)).
In that cited a956835d implementation, the static manager's refresh methods
are no-ops. This source-scoped observation requires running the
[currency upgrade checklist](../codex-currency-upgrade-checklist.md) at every
Codex upgrade, before reusing the opt-in profile; record the new version and
both export/projection hashes. The workhorse does not reference this projection.

The planned new-WSL map's opt-in profile row is metadata under
`slot_configs.gpt-gateway`, with the CC as its application owner and the native
known-answer search pending. It does not claim that the producer writes this
file: the current producer enumerates only the three existing Codex config
groups and rejects unmatched map entries
([native-agent-stack@9f3af37d: new_wsl_client_config.py:552-592](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9f3af37dd4659d8686c454d8ac727a3de73452a4/tools/adoption/new_wsl_client_config.py#L552-L592)),
and renders only its existing two profiles
([:1158-1162](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9f3af37dd4659d8686c454d8ac727a3de73452a4/tools/adoption/new_wsl_client_config.py#L1158-L1162)).
The metadata row is deferred until main includes
[#771](https://github.com/seathatflowsinourveins/native-agent-stack/pull/771),
whose owner also changes the map. Proposed follow-up: the live template owners
[#716](https://github.com/seathatflowsinourveins/native-agent-stack/pull/716)
and [#770](https://github.com/seathatflowsinourveins/native-agent-stack/pull/770)
fold the opt-in profile/catalog into executable producer wiring after their
cross-family review. This records PR does not edit their producer or templates.

## Alternatives, acceptance and overturn condition

Keeping standalone search enabled against the clean release retains the 404.
Disabling Lite on the workhorse changes ordinary turns without a quality
comparison. Rebuilding the gateway with an open PR duplicates upstream work.
The opt-in profile uses the vendor CLI's existing catalog/profile interfaces
and the gateway's existing hosted-tool handling.

The CC's pending native check must start a fresh, ephemeral, read-only
`-p omniroute-search` session outside a Git directory, with
`--skip-git-repo-check`. It requests exactly one search for
`site:docs.python.org/3/library/hashlib.html sha256`, then the official URL and
constructor. Acceptance requires one actual completed search event and the
correct official reference, with no standalone-route 404. A correct answer
without a search event does not pass. Retain returned events, exit code, usage
and any failure; missing usage remains unknown.

The decision reopens when an official OmniRoute release ships
`/v1/alpha/search`. Before the main profile enables standalone, measure that
release's search quality against hosted search on a declared matched task set,
including source correctness, failures and usage. Release notes or one route
response alone do not overturn the decision.

Evidence classes remain separate: source inspection and metadata are
`source_review`; the installed bundled export is a native metadata operation;
JSON/TOML, hash and flag-difference checks are `local_integration`. Neither the
projection nor the workhorse's configuration realignment proves hosted search
acceptance. That result remains pending CC application and native execution.

Completeness check: the review covered client transport selection, ordinary
Lite turns, both search switches, clean versus patched gateways, profile
precedence, startup-only catalog loading, native serializer normalization,
upgrade staleness and the pending search oracle. The next currency sweep must
check the shipped standalone route and its quality comparison, not merely the
open PR's age or status.
