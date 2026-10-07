# Codex code-navigation parity: proposed native startup and skill delivery

Date: 2026-10-06. Status: **proposal for F9/template owners; no host apply or
default-owner promotion**. Baseline: `ecfa112764c664d35377dd66b8cfcb67e5a94d60`.

The native navigation layer supports complex engineering and the research
system. A registered MCP server needs to be visible before a fresh task can
choose it. Codex 0.160.0's optional-startup grace can omit pending servers from
the first catalog even when those servers initialize and return calls later.
The existing J-MCP investigation owns that diagnosis; this decision reuses it.

The [sanitized snapshot](../../evidence/artifacts/codenav-parity-20261006/summary.json)
records five enabled stdio registrations and current resumed-turn discovery.
Historical lane rollouts contain 59 completed Serena calls, five Semble calls
and three codebase-memory calls, with one separate failed Serena call. The
scope includes 12 registered roots and 72 native-linked descendants. It contains
zero completed jcodemunch or SocratiCode calls. Transport counts establish
neither organic choice nor task success. They exclude pilot/unregistered
sessions, unfinished calls and CLI transports.

All five pins explicitly support Codex. The first-turn MCP catalog is absent
from the inspected root turn-context metadata. Current discovery and later
calls do not establish fresh intended-profile first-turn readiness. Functional
retrieval and graph/index qualification remain separate gates.

## Proposed F9 template delta

Let F9 select the adopted first-turn server set. For the retained diagnosed
Serena/codebase-memory rows, merge these fields into
`adoption/templates/codex.config.template.toml`, preserving their commands,
pins, timeout values, approval policies and other existing environment names:

```toml
[mcp_servers.serena]
required = true
startup_readiness = "connection"

[mcp_servers.codebase-memory]
required = true
startup_readiness = "connection"
env_vars = ["CBM_CACHE_DIR", "CBM_RUNTIME_DIR"]
```

This is an exact proposal, not an additional consumed configuration file.
Shared templates and the F9 renderer already have live owners; this PR hands
off the rows under `docs/lanes.md` rather than editing those files. No client
settings, approval mode or host installation changes in this PR.

The co-op forwards this proposal to the command center, which picks the
carrying PR and application order after #752 and #770. This lane does not
contact the template owners. The separate routing-text proposal is
overlap-token Q2 / [draft #749](https://github.com/seathatflowsinourveins/native-agent-stack/pull/749).
Its exact/graph/conceptual AGENTS-template bullets and these startup rows need
one consistent owner integration. This PR carries no routing text.

F9 startup or routing changes are **harness configuration evidence**, not U1
native-arm evidence. The fields remain upstream-supported Codex controls;
that does not make an altered profile an unchanged U1 arm or satisfy the
exclusion rule's required own-native routing fix/rerun.

## Row patches and evidence classes

Each independent hunk is against `origin/main` as read at
`ecfa112764c664d35377dd66b8cfcb67e5a94d60`. The owner combines overlapping
codebase-memory hunks while preserving its intervening edits; these are
review proposals, not instructions to apply all hunks blindly in sequence.

Classes requested by CODENAV-PARITY: **(a)** registered configuration;
**(b)** first-turn exposure; **(c)** actual rollout invocation counts;
**(d)** pinned upstream Codex integration. None is organic task grading.

**S1 — Serena live first-turn readiness.** (a) Native registration is enabled;
the baseline template has a 60 s timeout but no required/readiness fields;
live effective readiness values are unobserved. (b) J-MCP's native omission
record 1339169 precedes initialization record 1339188 by 374.015 ms. This is
the measured historical gap; the 12 lane first catalogs remain unretained.
(c) 59 completed lane calls demonstrate later use, not initial exposure.
(d) Source: Codex rust-v0.160.0 readiness types and catalog wait branch linked
below; Serena's own Codex integration is linked in the integration table.

```diff
--- a/adoption/templates/codex.config.template.toml
+++ b/adoption/templates/codex.config.template.toml
@@ -68,6 +68,8 @@
 command = "${ECO_ROOT}/bin/serena"
 args = ["start-mcp-server", "--transport", "stdio", "--project-from-cwd", "--context", "codex", "--enable-web-dashboard", "true", "--open-web-dashboard", "false", "--enable-gui-log-window", "false"]
 startup_timeout_sec = 60
+required = true
+startup_readiness = "connection"

 [mcp_servers.serena.env]
 RTK_TELEMETRY_DISABLED = "1"
```

**S2 — codebase-memory live first-turn readiness.** (a) Enabled registration;
the baseline global table has neither required nor readiness fields, and
effective live values are unobserved. (b) Native omission record 1339168
precedes initialization record 1339174 by 258.946 ms. (c) Three completed
lane calls establish later transport use. (d) Same pinned Codex readiness
contract; codebase-memory's own Codex registration is linked below. This
closes the supported startup-wait gap if F9 adopts it, not a measured task
quality or first-turn acceptance gap in this new snapshot.

```diff
--- a/adoption/templates/codex.config.template.toml
+++ b/adoption/templates/codex.config.template.toml
@@ -129,6 +129,8 @@

 [mcp_servers.codebase-memory]
 command = "${ECO_ROOT}/bin/codebase-memory-mcp"
+required = true
+startup_readiness = "connection"

 [mcp_servers.qmd]
 command = "${ECO_ROOT}/bin/qmd"
```

**S3 — codebase-memory cache/runtime forwarding parity.** (a) Native
environment-name read-back is empty; the baseline global table omits both
names. (d) v0.11.0's own installer forwards them unconditionally if present,
at cli.c:3754–3784 below. This is a measured registration/source mismatch,
not an attributed (b) initialization failure. (c) Existing completed calls
remain observed; no regression or index-identity failure is claimed.

```diff
--- a/adoption/templates/codex.config.template.toml
+++ b/adoption/templates/codex.config.template.toml
@@ -129,6 +129,7 @@

 [mcp_servers.codebase-memory]
 command = "${ECO_ROOT}/bin/codebase-memory-mcp"
+env_vars = ["CBM_CACHE_DIR", "CBM_RUNTIME_DIR"]

 [mcp_servers.qmd]
 command = "${ECO_ROOT}/bin/qmd"
```

## Native source for the proposed rows

Codex supplies both fields natively. Connection readiness requires the live
server; cached catalog readiness does not prove a live call, and a required
connection failure can fail session startup. See
[Codex readiness types](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/config/src/mcp_types.rs#L216)
and the
[catalog wait branch](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/codex-mcp/src/connection_manager/tool_catalog.rs#L278).
The pin is `rust-v0.160.0`, commit
`a956835d020762cb2b570053af06f643a11c0ecc`, matching the installed client.

The codebase-memory forwarding row follows its own installer exactly:
[DeusData/codebase-memory-mcp v0.11.0, cli.c:3754–3784](https://github.com/DeusData/codebase-memory-mcp/blob/v0.11.0/src/cli/cli.c#L3754).
The upstream forwards both names unconditionally if present, preventing a
configured cache/runtime from selecting a different daemon identity in Codex.
The examined native read-back and global template omit those explicit names.
No observed initialization failure is attributed to that omission here; current
transport discovery and historical calls work. This restores documented parity
when custom values are present without inventing new paths or reading values.

Alternative: a profile intended to wait for every optional server can set
`mcp_optional_startup_grace_ms = 0`. The
[pinned config documentation](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/config/src/config_toml.rs#L318)
and catalog implementation specify zero's per-server startup-timeout semantics.
Prefer targeted required-server readiness where unrelated optional services
should stay optional. Neither an unmeasured timeout increase nor server rebuild
is justified by the current diagnosis.

## Own Codex integrations and routing levers

| Candidate / pin | Native integration and lever | Proposal boundary |
|---|---|---|
| Serena `2.0.0.dev0`, `c6fbd1c5932df2494ffa0020af5a9fbe80b82143` | [Codex setup](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/docs/02-usage/030_clients.md#L302); [own Codex context](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/resources/config/contexts/codex.yml#L1) supplies symbolic navigation instructions. | Existing read-back already has Codex context and project-from-cwd. Apply startup readiness through F9, then qualify a fresh task. |
| jcodemunch `1.108.319`, `8f7b34abe16fb459e0bf1c04747d584216dfe32e` | [Codex binary registration](https://github.com/jgravelle/jcodemunch-mcp/blob/8f7b34abe16fb459e0bf1c04747d584216dfe32e/CLIENTS.md#L34); [own server instructions](https://github.com/jgravelle/jcodemunch-mcp/blob/8f7b34abe16fb459e0bf1c04747d584216dfe32e/src/jcodemunch_mcp/server.py#L359) and route/menu/order surface. | Current resolved binary conforms. Installed 1.108.327 remains explicit runtime drift from the task pin. Its installer targets real home `.codex`; verify isolated-home profiles through Codex, not an assumed installer override. |
| Semble `0.6.1`, `24497845460960db1839c8485319df189a889225` | [Own Codex integration](https://github.com/MinishLab/semble/blob/24497845460960db1839c8485319df189a889225/docs/installation.md#L82); [MCP-only selection](https://github.com/MinishLab/semble/blob/24497845460960db1839c8485319df189a889225/docs/installation.md#L28); [native instructions](https://github.com/MinishLab/semble/blob/24497845460960db1839c8485319df189a889225/src/semble/mcp.py#L71). | Already registered. No measured integration defect warrants reinstalling. Similarity is not semantic reference completeness. |
| codebase-memory `v0.11.0` | [CODEX_HOME-aware installer](https://github.com/DeusData/codebase-memory-mcp/blob/v0.11.0/src/cli/cli.c#L2644), own environment forwarding and [graph instructions](https://github.com/DeusData/codebase-memory-mcp/blob/v0.11.0/src/mcp/mcp.c#L1316). | Startup/forwarding proposal above. The co-op's new-index report is not a new index qualification by this lane. |
| SocratiCode `1.15.0`, `f6191f076a42405f0d5508139f3a8b505cfef93a` | [Own Codex plugin/MCP docs](https://github.com/giancarloerra/SocratiCode/blob/f6191f076a42405f0d5508139f3a8b505cfef93a/README.md#L222), [own exploration skill](https://github.com/giancarloerra/SocratiCode/blob/f6191f076a42405f0d5508139f3a8b505cfef93a/skills/codebase-exploration/SKILL.md#L3). | Its own skill was not found in the nine installed native plugin entries or the supplied turn skill catalog. Standalone skill installation elsewhere remains unverified. |

If SocratiCode remains adopted, its owner can retain a pinned native plugin's
skills while disabling the bundled server and keeping the existing pinned
top-level engine. This split is explicitly supported by
[README:244–259](https://github.com/giancarloerra/SocratiCode/blob/f6191f076a42405f0d5508139f3a8b505cfef93a/README.md#L244).
Use the exact commit with Codex's supported marketplace `--ref`; do not adopt
the README's floating main or bundled `@latest` launcher. Start a **new task**
and verify exactly one server plus the own skill. Upstream says reopening an
existing task does not load newly installed plugin skills (README:232).
Installing the engine alone does not install the plugin skills (README:108).
This PR does not install or select the plugin.

AGENTS.md/CLAUDE.md routing would be a harness intervention and cannot qualify
the original U1 native arm. Use each upstream's own MCP instructions,
descriptions, skills or hooks, with the intervention type recorded. Do not
replace maintained servers with local wrappers or duplicate server registration.

## Owner acceptance and overturn conditions

F9 incorporates the concrete rows in its owned templates, renders the intended
profile through its existing supported workflow, and verifies effective
enabled/required/live readiness. Then the organic/confirmatory owner runs a
fresh native task with unchanged U1 prompts and retained first-catalog metadata,
returned calls, source/index identity and functional oracles. Startup latency,
fail-start behavior, tool approval and unprompted selection are separate metrics.
That altered-profile check is a harness intervention, not a U1 native-arm
result. The run owner must separately freeze/rebaseline any eligible native arm.
Use the existing upstream promptfoo/Inspect harness for a contested A/B; no
new runner or trials are supplied here.

Replace targeted readiness with the shared grace alternative if a matched
upstream-harness comparison shows better first-turn coverage under the profile's
latency/failure contract. Drop a proposed required server when the organic owner
map excludes or supersedes it. Do not claim that native skill delivery improved
routing without its fresh-task matched rerun.

The original full-run exclusion rule still requires zero unprompted selections,
a chosen covering owner, and a failed own-native routing fix/rerun, per client.
These lane counts supply none of that completed conjunction. No owner, catalog
adoption status or exclusion changes in this proposal. Semantic-search quality
remains with the frozen confirmatory's owner.

## Evidence and completeness

Installed CLI registration/plugin metadata is an installed observation; pinned
files are source review; native terminal records are historical transport
telemetry. A completed item is not an `isError=false` or task-success verdict.
Current model-side discovery is not an earlier first-turn catalog.

Remaining sweep inputs: earlier first-catalog retention, unfinished and
out-of-scope calls, effective startup scalars, native-skill availability, cache/
daemon/index identity and freshness, useful task contribution and actual
provider/latency accounting. None is silently passed by this snapshot.
