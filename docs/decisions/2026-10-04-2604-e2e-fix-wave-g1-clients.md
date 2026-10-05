# NativeStack2604 G1 client plan repairs

Date: 2026-10-04. Bounded job: `fix-wave-g1-clients`. Base:
`PR #684's head`.

This repair makes the install plan reject the three client defects found by the
NativeStack2604 E2E. It serves the north-star action of using native agent SDKs
and engineering and skill-authoring workflows for complex systems and
US-equities research and historical simulation. It changes only the three owned
plan rows, their functions, the scoped checker, their documentation and one
settings fragment. The selected component and per-skill pins stay unchanged.
Nothing ran on a WSL distribution, no credential file or value was read, and no
commit was made.

## Inputs and source verification

The coordinator's `clients-1.json`, `review-clients-1.json`, `clients-2.json` and
`review-clients-2.json` supply the bounded findings. `adjudication.json` overrides
the SDK review and assigns the shared excluded-skill cleanup to the engineering
row. The engineering and authoring reviews agree with their executors and have
no slot-specific overriding adjudication. `fixes.json` was absent when inspected;
the original reviews and adjudications were read directly. The earlier
`job-030-2604-install-repair` patch and report supplied the JSON-capture lead;
only the authoring row's capture change was ported by hand.

The installed writer-host Codex 0.159.3 exposes both `debug app-server
send-message-v2` and `debug prompt-input` in its native help. These help reads do
not qualify the destination's selected 0.160.0. The
[0.160.0 release](https://github.com/openai/codex/releases/tag/rust-v0.160.0)
and [Skills 1.7.0 release](https://github.com/vercel-labs/skills/releases/tag/v1.7.0)
were read through GitHub's release API. Original Codex source was read from a
clean checkout at `a956835d020762cb2b570053af06f643a11c0ecc`, tag
`rust-v0.160.0`; the other cited files were fetched at their exact pins. Official
[SDK](https://developers.openai.com/codex/sdk),
[app-server](https://developers.openai.com/codex/app-server) and
[Claude skills](https://code.claude.com/docs/en/skills.md) pages were also fetched.
The scoped ai-memory query was unavailable under the tool's approval policy;
exact repository files and primary sources supplied the evidence.

## Selected repairs and alternatives

**SDK, exec and app-server.** Preserve the documented `new Codex()` quickstart,
including its default bundled-binary lookup. Add a separate native app-server
check in the same `after_sign_in` stage. It uses `codex debug app-server
send-message-v2`, requires initialize, thread/start and turn/start responses,
requires the exact `Completed` status, and checks the requested reply. Capture
output before grep so the upstream client can finish printing its trace summary.
Require both stage result lines to pass. The native test client starts a
short-lived stdio child; the background daemon selection stays unchanged.
Sources: `openai/codex@rust-v0.160.0`:
[sdk/typescript/README.md:15,110](https://github.com/openai/codex/blob/rust-v0.160.0/sdk/typescript/README.md#L15),
[codex-rs/cli/src/main.rs:923](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/cli/src/main.rs#L923),
[codex-rs/app-server-test-client/src/lib.rs:1072,1624,1994](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/app-server-test-client/src/lib.rs#L1072).

Rejected alternatives are help/version-only acceptance, treating an SDK exec
turn as app-server evidence, or a custom app-server protocol runner. The SDK uses
exec, and the native client returns success after a failed turn. The selection
is overturned by an upstream supported client/test that provides a better
behavioral oracle, or a release that changes the selected protocol/output
contract, followed by source review and actual host acceptance.

**Engineering process skills.** Before delegating the existing pinned manifest
install, upstream Skills CLI 1.7.0 removes exactly `domain-modeling`,
`setup-matt-pocock-skills`, `grill-me`, `improve-codebase-architecture` and
`semgrep`. The existing settings writer merges a three-name fragment marking
the retired names as `off`. Run the installation from the operator shell outside
a Claude session; native deny rules remain enforced. Acceptance retains the
selected-skill hash/lock integration check and rejects excluded listing names,
remaining placements or dangling links, stale lock entries and incorrect retired
overrides. Sources: `vercel-labs/skills@7407f3893ad4dceab546ac002c3ef806e4000c73`:
[src/remove.ts:40,182,209,247,323](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/remove.ts#L182),
[src/list.ts:113](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/list.ts#L113),
[Claude's skillOverrides](https://code.claude.com/docs/en/skills.md#override-skill-visibility-from-settings),
and `seathatflowsinourveins/native-agent-stack@PR #684's head`:
[tools/adoption/apply_claude_settings.py:191](https://github.com/seathatflowsinourveins/native-agent-stack/pull/684/files).

Notes-only cleanup and disabling descriptions leave installed content behind;
removing every unselected user skill exceeds this job's ownership. The exact
five-name cleanup follows the recorded retirement and exclusion decisions. A
new maintained selection or retirement changes this list only after a dated
source-backed decision and a native lifecycle check. The held browser selection
and unrelated personal skills retain their existing states.

**Skill authoring.** Provision `PyYAML==6.0.3` through upstream uv into the
selected mise Python. Retain the Claude-only copy, pinned tree, unfiltered
listing and no-shared-copy guards. A separate additional check initializes the
embedded Codex cache through native `codex debug prompt-input` with stdout
discarded, then runs both unchanged upstream validators through the session's
default `python -B` against the pinned installed `find-skills`. Sources:
`anthropics/skills@8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4`:
[skills/skill-creator/scripts/quick_validate.py:9,96](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/scripts/quick_validate.py#L9),
[scripts/package_skill.py:17](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/scripts/package_skill.py#L17),
`openai/codex@rust-v0.160.0`:
[codex-rs/skills/src/assets/samples/skill-creator/scripts/quick_validate.py:10,120](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/skills/src/assets/samples/skill-creator/scripts/quick_validate.py#L10),
[codex-rs/cli/src/main.rs:2044](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/cli/src/main.rs#L2044),
[codex-rs/ext/skills/src/host_service.rs:125](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/ext/skills/src/host_service.rs#L125),
`astral-sh/uv@0.12.22`:
[docs/pip/environments.md:100](https://github.com/astral-sh/uv/blob/0.12.22/docs/pip/environments.md#L100),
and [PyYAML 6.0.3](https://pypi.org/project/PyYAML/6.0.3/).

Using an unrelated system Python would leave native sessions broken. A custom
venv launcher would require changing the upstream skills' documented commands.
The selected interpreter provisioning preserves those commands. This choice is
overturned if the maintained native skills remove the dependency or supply a
supported runtime that passes the same default-session checks.

Both owned Skills CLI listings write JSON to a regular temporary file before jq
reads it. Skills forces process exit, while Node's POSIX pipe writes can remain
pending; file writes are synchronous. Sources:
`vercel-labs/skills@7407f3893ad4dceab546ac002c3ef806e4000c73`:
[src/cli.ts:419](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/cli.ts#L419),
`nodejs/node@v24.21.0`:
[doc/api/process.md:4228](https://github.com/nodejs/node/blob/v24.21.0/doc/api/process.md#L4228).

## Evidence and corrections

Unchanged upstream operations in an owned disposable Python environment:
both pinned validators exited 1 with `ModuleNotFoundError: No module named
'yaml'` before provisioning, exited 0 with `Skill is valid!` on the pinned
find-skills after provisioning, and exited 1 with `SKILL.md not found` on an
empty input. These six calls prove the validator dependency and input guards on
the writer runtime. They are separate from native client invocation, authoring
quality and destination readiness. Bytecode stayed disabled.

Local integration fixtures exercised the new glue: four protocol-output
fixtures (Completed, Failed, missing initialize, wrong reply), a real settings
merge into synthetic settings preserving adjacent values, five additional-check
consistency controls, and nineteen supplementary engineering-guard cases. These
are 29 synthetic checks, with real implementation calls and explicit positive
and absent-condition controls. They are not upstream E2E or model runs.

The first combined authoring program failed its inventory-only fixture because
that fixture supplies no Python validators. The final schema keeps the original
inventory check and declares the separate native operation under
`additional_checks`. Slot-owned helpers produce independent result lines, and
the scoped checker verifies their stage, source, command and actual call from
the owning function. The existing inventory fixtures retain their original
meaning; they do not claim to cover the Python operation.

The first config-copy command used a literal newline. Bash accepted it, but
the original checker's install-command parser reads one line at a time and
raised `No closing quotation`. The corrected command keeps mkdir and install
on one line; the checker then passed. Original failed output is retained in the
job's ignored temporary directory.

One source correction: the older row note grouped writing-for-agents with the
`d81f3a18` engineering pin. The actual manifest and fetched original show
writing-for-agents at `mattpocock/skills@c55ee46073ed923f86ce59a5eb3b6d895095d1b7`:
`skills/productivity/writing-for-agents/SKILL.md:1`. Other selected engineering
skills use `d81f3a183412e71a5b1e84ca21bc1a35eea03a60`; no pin changed.

## Acceptance and completeness critic

The prescribed four-module unittest command ran with TMPDIR in this job's
workspace, outside `/tmp`: 324 tests, 84 failures and 12 errors, exit 1. An
independent clean local clone of the exact base ran the same command with the
same counts and identical failing-test multiset. There are no new failing test
names. The inherited defects are a stale generated Codex instruction block and
the definitive manifest's RTK 0.50.0 versus the stack pin's 0.51.0. Those files
are outside this job's ownership. The client-config check also independently
reported the stale block at the unchanged base.

`check_plan.py`, Bash syntax, handbook `--check` and `git diff --check` passed.
Publication validation reports only expected registry hash/byte drift and the
new config's missing hash registration. `manifests/evidence.json` belongs to the
coordinator and was retained. Handbook outputs and digests need no rewrite.
The install-command count is 122 instead of 118; stage entries remain 78, with
two additional native operations. Shared script headers and counts were not
edited.

The completeness critic checked each missed modality: default SDK bundled
binary versus the host override; the app-server protocol versus exec and daemon
state; native and legacy skill placements, dangling links, locks and effective
retired overrides; the session-default Python versus system Python; and the
embedded cache on a clean Codex home. The next client lifecycle sweep must retain
those distinctions. A passing inventory or validator does not close creation
and evaluation. Fresh native tdd use and absence of retired skills remain the
engineering gate. Fresh skill creation and the pinned Claude creator's paired
with-skill/baseline benchmark, aggregate_benchmark and static eval viewer remain
the authoring gate; Codex retains its embedded creator's workflow. Source:
[anthropics/skills@8a1541c4:skills/skill-creator/SKILL.md:163,229,247](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/SKILL.md#L163).

No new destination READY status is claimed. The host coordinator must run the
revised native acceptance and fresh-session gates and record sanitized returned
output. No additional user sign-in, identity or privacy choice is needed for
this bounded plan repair.
