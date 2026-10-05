# Round 2 installation plan: agent messaging (2026-10-04)

This bounded change serves the north-star action of coordinating native Claude
Code and Codex research/build sessions for complex projects and US-equities
research. It implements the `workers/agent-messaging` owner already adopted by
round 2 and the coordinator's wave5; it makes no new selection or local trial.
The owner and pin come from
[the adopted decision](2026-10-04-final-architecture-round2.md) and the
`workers/agent-messaging` record in
[the verdict extract](../../evidence/artifacts/final-architecture-round2-20261004/verdicts.json).

## Sources, comparison and boundary

hcom 0.7.27 is pinned to
`aannoo/hcom@2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b`.
The alternatives already judged in round 2 were agmsg, AgentRelay, MCP Agent
Mail Rust, Relaycast and Swarmail, plus the existing native facilities. This
builder preserves that comparison. Reconsider with the verdict's paired Harbor
comparison against a released agmsg, a release closing hcom issue 151, or native
cross-client ingress documented by both clients. None is a new adoption gate.
[Pinned release and supported installer](https://github.com/aannoo/hcom/releases/tag/v0.7.27),
[open issue 151](https://github.com/aannoo/hcom/issues/151).

hcom owns Claude Code <-> Codex transport only. Claude <-> Claude remains native
SendMessage/ListAgents with `crossSessionInbound=accept`, and Codex-internal work
keeps multi_agent and queue. The command-center ledger remains the authorization
record for transported `[cc-msg v1]` items. The accepted posture is the October 3
r1, SHA-256 `ef8e934c827e73cfd87d35f6a3497ba66c58c7fd349af63a9c8baadff350a556`,
with the root's three source corrections accepted in
[PR 608](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5972504465).
The user's OS-sandbox change in posture 3.3 is outside this job.

## Install and native configuration

The plan verifies the installer SHA-256
`3bc057fcd763748c32fae0ae25e150abf2b1df0d4c9451432c28f4ddde176a98`
against the published release API digest, then executes that installer. The
installer checks the GNU Linux x86_64 archive against its embedded SHA-256
`8ae97ff6fef63c637d66ddf882651aadd035bd74ae26c0787743869c20a5391d`.
Its documented environment controls select `~/.local/bin` and leave PATH
modification to the existing client setup. This row requires Python for the
repository's configuration adapter and no sudo, service, Docker, GPU or Node.
[Release digests](https://api.github.com/repos/aannoo/hcom/releases/tags/v0.7.27),
[installer:51,313,375,777](https://github.com/aannoo/hcom/releases/download/v0.7.27/hcom-installer.sh),
[published archive checksum](https://github.com/aannoo/hcom/releases/download/v0.7.27/hcom-x86_64-unknown-linux-gnu.tar.gz.sha256).

`adoption/new-wsl/client-config-map.json` holds the slot's hcom configuration,
Claude deny literals, Codex rule-file source and peer-message hints. The existing
mapper enumerates pieces already present in shared templates; it cannot create
additional permission-list entries or a rules file. An adapter in this slot's
`config/` directory reads the map extension and reuses the mapper's existing
settings merge, managed instruction blocks and atomic writer, leaving shared
templates under their original ownership. It resolves `crossSessionInbound`
through the mapper's existing authorization entry and preserves a different
existing user choice. This is repository integration glue, with native formats
from the cited upstreams, rather than a new permissions engine.
Source: this PR, `tools/adoption/new_wsl_client_config.py:549,577,1623,2289`;
this PR, `tools/adoption/apply_claude_settings.py:191`;
this PR, `tools/adoption/managed_block.py:104`.
[Claude permissions](https://code.claude.com/docs/en/permissions),
[Codex rules](https://developers.openai.com/codex/rules),
[hcom configuration fields:126-152](https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/src/config.rs#L126).

The mapped posture keeps `title_mode=off`, `relay.enabled=false`,
`auto_trust_workspace=false` and `auto_approve=true`. Peer text carries no user
authority, including `bigboss`. Both clients receive that instruction. Claude
gets the posture's hcom and uvx-hcom denies, including equals-joined `send --from`
and its middle `claude-pty` wildcard. Codex gets four `forbidden` prefix rules,
each with native `match`/`not_match` examples, in a separate `hcom-deny.rules`;
upstream retains ownership of `hcom.rules`. The adapter checks the native rule
source before writing and the installed file during acceptance with the
mandatory `codex execpolicy check --pretty --rules <file> -- hcom term inject luna hi`.
[Upstream safe list:46-72](https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/src/hooks/common.rs#L46),
[Codex forbidden branch:394-406](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/src/exec_policy.rs#L394).

The prefixes retain the accepted posture's limits: reordered or equals-joined
global flags, Codex's single-token `--from=bigboss`, numbered Claude PTY launches,
other executable wrappers (including RTK) and shell scripts the client does not
split remain outside their coverage. Parsing failure and `--ignore-rules` remain
separate limitations. Deny rules are not an OS security boundary, and the peer
instruction does not promote them to one.
[Router:264](https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/src/router.rs#L264),
[Codex fallback:645](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/src/exec_policy.rs#L645),
[native shell matching documentation](https://developers.openai.com/codex/rules).

## Acceptance and correction

Post-install acceptance parameterizes the upstream `status_json_in_fresh_dir`
and `list_json_empty` assertions against the installed binary, using a disposable
HCOM_DIR. It then checks mapped client files and native rule parsing/matching.
The smoke is an upstream-test-derived CLI integration observation; it is not an
execution of the unchanged Cargo suite or cross-client E2E.
[CLI smoke tests:129-146](https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/tests/cli_smoke.rs#L129).

Repository-quality evidence was re-read from the tag's successful
[CI run 36803903267](https://github.com/aannoo/hcom/actions/runs/36803903267).
The Linux real-Claude and real-Codex jobs' pinned-tool installation and native
test steps both succeeded. Their command is
`cargo test --locked --test <real_tool_claude|real_tool_codex> -- --ignored --nocapture --test-threads=1`.
These are upstream executions, not new host runs or evidence that our narrowed
plain-Claude posture has automatic idle delivery.
[Pinned CI:121-122,185](https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/.github/workflows/ci.yml#L121).

**Correction and verification path:** installing deny rules and peer hints into
a plain Claude launch does not activate hcom automatic receive. The release
notes explicitly move hooks to hcom-launched sessions, and the pinned Claude
hook handler returns silently without `HCOM_PROCESS_ID`. This row creates no
Claude hcom launcher or global hooks: plain Claude joins with `hcom start` and
reads through `hcom listen`. Idle plain-Claude wake remains unqualified. Codex
retains upstream `hcom codex` transport launches. This closes the tempting but
unsupported inference that upstream real-tool CI proves the requested launch
posture end to end.
[Release change](https://github.com/aannoo/hcom/releases/tag/v0.7.27),
[Claude hook guard:135-141](https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/src/hooks/claude.rs#L135),
[supported delivery routes:234-246](https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/README.md#L234).

The installed builder client reported `codex-cli 0.159.3`; its native policy
check returned `decision: forbidden` for the source rule file and validated all
inline examples. The plan still targets Codex 0.160.0. This result establishes
local syntax/matching on 0.159.3, not live loading or a new 0.160.0 test run.
The installed release's
[changelog](https://github.com/openai/codex/releases/tag/rust-v0.159.3)
was checked before relying on the pinned policy source. hcom was not found on
the builder's PATH, so no hcom install or smoke was run here.

## User inputs and integration handoff

The row records native client sign-ins, user-granted lane-folder trust and a
Codex close/restart as `needs_user`. The adapter retains differing pre-existing
hcom configuration or a deny file and reports that review without displaying
values. It compares an existing hcom config by digest rather than parsing it,
because relay credentials may live there.
[Relay fields:201-208](https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/src/config.rs#L201).

No existing hcom pin moved: this base had no hcom stack/profile/architecture pin.
The complete new pin and its two artifact checksums live in the owned plan row.
Shared install/accept headers and README counts need the coordinator's combined
refresh. `owners.json` is a historical generated inventory outside this job's
allowed files; its messaging owner/install flag needs regeneration at integration.
The checker continues reporting that drift rather than suppressing it.

## Returned builder verification

These are checks of repository integration in this builder's sandbox, separate
from the upstream CI evidence and the unrun NativeStack2604 hcom smoke.

- `check_plan.py`: exit 1, six problems. Four other owners have no plan row;
  the browser row retains its old measurement-only state; the generated
  `owners.json` needs its messaging owner/install flag refreshed. No reported
  problem names `agent-messaging`, and its new contract checks pass.
- `bash -n install.sh accept.sh`: exit 0.
- `new_wsl_client_config.py --check`: exit 0 (`check passed`). The scoped
  messaging adapter's `--check-map` also exited 0.
- `codex execpolicy check --pretty --rules config/hcom-deny.rules -- hcom term inject luna hi`:
  exit 0, returned `decision: forbidden`; all four rules' inline positive and
  negative examples validated when the native parser loaded the file.
- `build_new_wsl_handbook.py --check`: exit 0, returned `status: passed`.
  Neither the profile nor handbook recipe inputs changed, so no regeneration
  or digest update was needed.
- The four requested unittest modules, with the requested out-of-checkout
  TMPDIR set: `Ran 347 tests in 88.084s`, `FAILED (failures=25)`, exit 1.
  Ten failures are the native shell fixture's read-only TMPDIR; thirteen are
  pre-wave5 owner-count/state assertions; two are plan-copy tests blocked by
  the shared integration drift above. An archived copy of the supplied base
  returned 28 failures, and every current failing test also failed there.
  The archive lacks checkout metadata, so its three additional local-model
  fixture failures are not presented as an improvement from this change.
- `scripts/validate.py`: exit 1, 124 publication-registry drift messages
  (hash/byte mismatches and unlisted evidence files), with no non-registry
  diagnostic. The coordinator owns the registry update.
- `git diff --check`: exit 0.

An early checker revision looked up the map beside a copied `--plan-dir` and
added two fixture failures. It now reads the canonical map beside the source
checker, while checking the rules and adapter from the selected plan directory.
The final four-module run has no added failing test compared with the base.
This is the correction and its verification path, not a claim that the shared
suite or the read-only TMPDIR has been repaired.

Completeness critic: installer integrity, CLI behavior, both clients' native
settings/instructions, rule parsing/matching, upstream real-tool quality and
restart/trust/credential boundaries have distinct sources. Uncovered candidate
classes are native ExternalMessage ingress and future released agmsg; revisit
them in the messaging layer's next landscape sweep. Remaining modality gap is
idle plain-Claude delivery without hcom launch hooks. No local runner, parser
hook, model trial or OS-sandbox change is added to conceal it.
