# Held skill-routing prototype and native B13 preparation (2026-10-06)

Status: PR-only, inactive, untested. Source review converges on a bounded gap,
not a complete adopted framework. No host hook/configuration/trust change,
installer, benchmark or model job ran. This preserves the user's October 4
[hold-out order](2026-10-04-claude-template-holds-out-token-lane-carriers.md).

The action served is sourced task selection for public research and complex
system implementation, supporting the US-equities research/historical-simulation
foundation while deterministic code owns numeric/risk/order state. Source:
`native-agent-stack@ecfa1127:blueprints/us-equities/AGENTS.md:57`.

## Sources, alternatives and gap

Vendor org searches preceded community discovery: scoped `skill-activation`
code searches returned no Anthropic matches and OpenAI NVIDIA benchmark/card
references. This is bounded discovery, not an absence claim about either vendor.
Native official interfaces are [Claude hooks](https://code.claude.com/docs/en/hooks)
and [Codex hooks](https://developers.openai.com/codex/hooks). Codex's immutable
schema pin is `a956835d020762cb2b570053af06f643a11c0ecc`, generated
UserPromptSubmit/PostToolUse/SubagentStart command output schemas. Each has an
event-specific `hookSpecificOutput` with `additionalContext`.

The closest reviewed maintained comparator is
[alex-macra/claude-codex-skills-assembly@aba8bed](https://github.com/alex-macra/claude-codex-skills-assembly/tree/aba8bedadd83998cd2004838683ee41eaa449c1f).
LICENSE at pin is MIT; README documents native Linux/macOS Python installation,
catalog overlays and opt-in hooks. Its Python tests and Ubuntu/macOS CI exist
at this pin; five checks reported success. Releases/tags queries returned empty,
so release discipline is unqualified. Activation is prompt-only at
`hooks/skill-activation.py:644`; the supported installer bundles unrelated
guards and catalog caps. Preserve the executable and its supported registry
unchanged in a separate comparator root, without running the installer here.

[Diet's showcase@07f75ce](https://github.com/diet103/claude-code-infrastructure-showcase/tree/07f75ce3c301259e857343596e7883b8ce5a9f50)
has a Codex adapter, contrary to a Claude-only assumption. It synthesizes Edit
events and may block; optional activation paths call models. No release was
returned and the pinned GitHub workflow path was unavailable. The older
disler/hooks-mastery head `052ad1cbd5aeb1ec4a1def22012d1293c6225625`
is a reference outside the 90-day maintenance criterion, not a selection.

No reviewed candidate supplies all three requested events, the parent's runtime
workflow rows, verified role grants and blind/Skill-less suppression. This
prototype fills only that combination; it does not fork or rebuild a maintained
framework. Official schema serialization and the existing native
`token-lanes-subagent-start.py:35-45` are its references. Context-mode 1.0.169's
formatter hardcodes PreToolUse and cannot serialize these events unchanged.

## Bound behavior and information limits

The consumer reads the actual S1 `sota_workflow_manifest`, requiring the
`python_regex` trigger contract and canonical pin stores. Kept/trial eligibility,
pending row/lane dependencies, central native listing/implicit policy and
coordinator-only refs remain intact. Input, regex work and output are capped;
output contains safe registered names, never prompts, commands or paths.
No session state store or transcript read is introduced.

Source review corrected a lane gap: kept/trial status alone cannot activate an
empty/missing main lane or an inert child stage. Main events now require their
actual native channel list, and child events require the actual active stage.
Malformed trigger/measure containers are silent; each trigger list is capped
and every attempt uses the remaining shared match deadline. Optional canonical
`triggers.skill_intents` filters CI and review-request outcomes per skill rather
than emitting both row skills for either outcome.

Path matching uses unchanged Python 3.13
[`glob.translate`](https://docs.python.org/3.13/library/glob.html#glob.translate),
with recursive complete `**` segments, hidden paths and case-sensitive `/`
separators. The explicit subset is literal components, `*` and whole `**`;
unsupported extensions/older runtimes stay silent. This corrects fnmatch's
separator behavior and internal zero-directory mismatch without a custom glob
parser. Native path-rule parity remains an execution prerequisite.

Another source correction replaced the invented Codex patch `input`/`patch`
fixture with its native `tool_input.command` envelope, verified in
`openai/codex@a956835d020762cb2b570053af06f643a11c0ecc:codex-rs/core/src/tools/handlers/apply_patch.rs:290-295,437-450`.
That fixture is authored source-shape evidence, not a fresh native callback.
Relative targets require the event's actual validated cwd within the project.
Explicit owned roots and nonredirected parents precede regular-file opens;
unknown redirects are never resolved into newly trusted roots. Filesystem checks
assume cooperating processes and do not form a race-proof sandbox or bound I/O.

Claude child hints require explicit Skill in matching registered/native role
metadata. Wildcard/inherited/unknown tools and preloads alone are not inferred
grants. Already-preloaded refs receive no redundant hint. Blind contexts are
silent. Codex child capability awaits S10 and remains silent; a same-named
Claude role is not a native Codex capability contract.
Project definitions have native priority; the global fallback uses the selected
CLAUDE_CONFIG_DIR, never another profile's default role. Public root locators
are inspected without settings/authentication reads. Effective CLI/runtime
overrides remain a qualification limit, so on-disk grants are source evidence
until native role/capability controls run.

PostToolUse does not carry the original user intent. A PR-comment/log fetch
cannot distinguish address/repair from list/summarize. The conservative stateless
choice suppresses fetch-only events, including --log-failed reads. Explicit
outcome intents and clear edits/matched actions can hint. Frozen read-only
negatives remain in B13; they are not removed to inflate gain. An alternative
with measured benefit can overturn this choice.

## Native authentication/network prerequisite, not acceptance

Harbor source reviewed at `b53b8134e1241686dca7759af188f987ecc48e8b` supports
native inline `config` (`src/harbor/agents/installed/codex.py:1536`) through
`--agent-kwarg`/`--ak` (`src/harbor/cli/jobs.py:603`). Explicit agent environment
entries shadow inherited entries (`src/harbor/agents/base.py:258`). A custom
keyless Responses provider can be configured without copying native account
files. Harbor still generates an empty sandbox auth file when no key exists
(`codex.py:1718`). Source/configuration support is not authentication acceptance.

Harbor's model slash stripping at `codex.py:1668` needs a real bare-alias or
supported-path proof; namespaced IDs in the gateway models metadata do not settle
acceptance. Promptfoo 0.123.1's Codex SDK provider passes configured model unchanged
to native threadOptions, so its namespaced route is a static alternative.

The root reported Docker 29.8.2/rootlesskit 3.1.0 metadata. Docker's
[current documentation](https://docs.docker.com/engine/security/rootless/troubleshoot/#--nethost-doesnt-listen-ports-on-the-host-network-namespace)
limits historical rootless host-mode isolation to versions before 29.5. Harbor
respects task `services.main.network_mode: host` in compose overlays
(`docker.py:358-417`); task TOML network policy is separately `public`, not `host`.
Neither metadata proves container loopback nor a fresh model answer. Installed
Harbor remains 0.23; native 0.24 qualification belongs to currency/isolated setup.
No rootful daemon, sudo, sysconfig or restart is proposed by this lane.

## Frozen comparison and overturn

Native harness preparation is in `tools/skill-routing-b13/`. Both arms retain
the same fixture, skill catalog, tools and recorded effort. Three repetitions
per case/arm, actual hook-firing positive controls and native instruction reads
are required. The Codex SDK trust/apply ticket remains open; a skipped hook
treatment is untested, not zero gain. B13 needs load gain above zero, adjacent
false hints at most 10%, and no pass-rate regression. Failed attempts, unknown
usage and provider identities remain separate.

Default production channels remain description/native discovery and pointers.
B13 plus command-center ACK is required before registration. A failed acceptance
bar, source/role drift or a maintained complete framework replacing the gap
overturns the prototype. Completeness follow-up includes native Codex child
capabilities, prompt-only comparators, SDK middleware/skill-search approaches,
marketplace skill finders and signal loss from stateless fetch suppression.
