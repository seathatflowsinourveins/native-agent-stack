# Require an explicit provider for model-executing Codex tools

Several repository callers constructed `codex exec` while leaving the provider
to the host account. The 2026-10-08 coordination sweep was a discovery lead:
its nearby-text heuristic also found parsers, version checks and static app-server
operations. The call sites and their environment construction were checked
directly before choosing a change.

The installed client is Codex CLI 0.161.0. Its unchanged `exec --help` documents
`-c` TOML overrides, the fallback for literal string values, the single profile
layer, and `--ignore-user-config` skipping user configuration while keeping the
authentication home. The corresponding upstream is
[openai/codex rust-v0.161.0](https://github.com/openai/codex/tree/979011409de0a60b52f179721948e65531d26144),
commit `979011409de0a60b52f179721948e65531d26144`:
`codex-rs/model-provider-info/src/lib.rs` defines custom provider tables, and
`codex-rs/config/src/loader/mod.rs` loads configuration layers, and
`codex-rs/core/config.schema.json` declares the fast-tier setting. Official
[advanced configuration](https://developers.openai.com/codex/config-advanced)
and [configuration reference](https://developers.openai.com/codex/config-reference)
document provider definitions and command-line overrides. The existing pinned
repository implementation is `tools/sota-convergence/landscape-sweep/codex_job.py`
at base `be7273a43c35f25002be8b481683c475482d661c`: its transport-only branch
already composes a provider table through supported `-c` overrides.

The native proof, blind convergence, adjudication, landscape runner, token
judge and capability gate now require an explicit provider choice before model execution. Native
selects the built-in `openai` provider. A keyless OmniRoute run selects an
explicit HTTP loopback endpoint with a port and `/v1`, using a public `local`
placeholder rather than inspecting an inherited gateway credential. All new
constructors pass the standing fast tier and retain their model and effort pins.

The blind and proof routes use the existing inline-provider pattern. Blind
runs deliberately ignore user configuration, and the proof's one profile slot
is occupied by the stack-worker/control comparison. Loading the gateway profile
there would change those contracts. Empty HOME, scoped CODEX_HOME, disabled
hooks/web, restricted PATH, audits and native-home lifecycle remain in place.
Their existing native-auth home preflight remains a separate prerequisite even
when an explicitly selected gateway will carry the model call.

The landscape runner's explicitly staged gateway home retains its own provider,
profile, MCP and environment contract. Static version/features/app-server probes,
recorded-event parsers and private coordinator scripts are outside the changed
model constructors. Private script leads remain with their coordinator owner.

The capability gate carries validated public provider metadata through Promptfoo
to its existing SDK/profile launcher. A conditional branch delegates the native
provider overrides while retaining SDK arguments and the prompt's standard-input
pipe. The original branch remains for legacy credential-canary consumers outside
this assignment; no broader account-routing closure is claimed for those callers.

Acceptance here is offline integration: native constructors, preflight refusals,
synthetic process observation, and existing bounded fixture suites. It is not a
new model, provider, account or gateway acceptance run. Existing receipts are
not promoted. The first fixture attempt under a temporary directory with a
Git ancestor marker failed the existing blind boundary; rerunning with a clean
non-repository temporary root preserves that failure condition. An initial
TOML-only assertion incorrectly parsed the existing unquoted effort override;
the installed CLI's documented literal fallback explains it, and the test now
parses the actual provider tables while checking the effort separately.

The inverse is a source revert of this dedicated change; it needs no host
configuration or credential mutation. A supported upstream execution interface
that both preserves blind isolation and proves the selected provider could
replace this glue. Compare the same constructor/environment and missing-choice
tests before changing it.
