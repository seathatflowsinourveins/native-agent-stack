# Claude MCP template alignment — 2026-10-08

The portable Claude template used a Node launch for SocratiCode while the live
host uses the vendor's `npx` form. The client-config map also overrode arguments
with a 1.15.0 path. This change projects the same-command user/plugin pairing
chosen in [the clean-install decision](2026-10-07-clean-upstream-install-finalizes-a-candidate.md#what-this-amends).
The live Claude registration was already working as one server; this corrects
the repository's projection.

## Primary sources and configuration

SocratiCode v1.16.0 peels to
`3d3a4a4d427cb0f29de4f5dd1360da52896f62df` (annotated tag object
`a50f72c5b79dcb8f69ac9bc68b21fe744d82d45b`). Its
[plugin manifest](https://github.com/giancarloerra/SocratiCode/blob/v1.16.0/.claude-plugin/plugin.json)
selects the
[Claude-specific MCP file](https://github.com/giancarloerra/SocratiCode/blob/v1.16.0/.claude-plugin/mcp.json),
which supplies:

```text
npx -y --prefer-online ${SOCRATICODE_SPEC:-socraticode@latest}
```

The shared `.mcp.json` is a different file; it does not provide this Claude
override. The vendor's [README at the tag](https://github.com/giancarloerra/SocratiCode/blob/v1.16.0/README.md)
documents the package specification in user settings. The portable settings
template sets `SOCRATICODE_SPEC=socraticode@1.16.0`, enables
`socraticode@socraticode` and names the tagged vendor marketplace. The map gates
those three settings to the SocratiCode owner of `slot:code-search`. Existing
host-local package specifications remain host-owned.

The manual registration retains the name `socraticode`, preserving existing
`mcp__socraticode__*` consumers. Its template escapes the native argument as
`$${SOCRATICODE_SPEC:-socraticode@latest}`. The existing Python `string.Template`
installer consumes `$$` once; the new-WSL renderer leaves this shared argument
untouched. An argument override in the map would undergo an earlier substitution
and is therefore removed. No production renderer changes.

Claude receives seventeen environment names. The three additions use portable
defaults: empty `QDRANT_COLLECTION_PREFIX` preserves the vendor's legacy
collection naming; `SOCRATICODE_AUTO_RESUME=off` follows the observed live setting;
`TMPDIR=/tmp` avoids copying a private host-specific temporary path. Endpoint
overrides still come from the selected host. Codex retains its independently
selected `${SOCRATICODE_VERSION}` Node package path; its stale fixed map override
is removed, and its carrier receives the same three defaults. Configuration
parity does not establish those older platform engines' runtime interpretation.

The canonical code-graph registration is `codebase-memory-mcp`, following
[DeusData/codebase-memory-mcp v0.11.0, Manual MCP Configuration](https://github.com/DeusData/codebase-memory-mcp/blob/v0.11.0/README.md).
Claude/Codex templates, map matches, worker profile, carrier namespaces and their
documentation use that registration name. The component slot owner remains
`codebase-memory`. The vendor's installer and this profile's registration
projection have separate ownership; the template no longer prohibits the native
installer. Carrier sums were regenerated from the actual bytes.

## Client evidence and its limits

Installed Claude Code is 2.1.295; native binary SHA256 is
`4503bfe11a6c7fcc1e0b39b5e0d347c04248f750b03b0977b3ad6b531fe6f358`.
The reader checkout at `anthropics/claude-code`
`71cdddec623889d38af14b7a489670a03186f659` documents only through 2.1.294;
the 2.1.295 implementation was inspected in the installed binary instead.
The client's [MCP documentation](https://code.claude.com/docs/en/mcp#environment-variable-expansion-in-mcp-json)
documents native variable expansion and default tokens.

Embedded source expands user-scope and plugin arguments before comparing them.
Manual/plugin matching fingerprints command plus arguments and ignores server
environment differences. Plugin/plugin matching also considers environment;
the changelog's older environment correction must not be applied to the
manual/plugin comparison. The relevant native byte offsets are:

| Native path | Byte offsets in the installed 2.1.295 binary |
| --- | --- |
| Manual loading and expansion | `Up` 217030774; `W5t` 217030878; `Evt` 217039761; `H0o` 217024337 |
| Plugin loading and expansion | `Bbt` 217004769; `y0o` 217002255 |
| Shared expander | `vK` 215128525 |
| Aggregate loading, then suppression | `pk` 217033314; suppression call 217035992 |
| Accepted settings environment application/filter | 210520164; 210515660 |
| Fingerprint/suppression implementation | 217015224–217015606 |

Both loaders use the same accepted `process.env` value. An absent Spec takes
the fallback; an explicitly empty value remains present. This is source review,
not a new session or fresh-host acceptance run.

The existing private CC builder facts record has SHA256
`e7a6879335c71395736216347d133e9e944627f965ab738aeae391ec33a243fd`.
It reports a native 2.1.295 session, one connected manual server and this client
diagnostic twice:

```text
Suppressing plugin MCP server "plugin:socraticode:socraticode": duplicates manually-configured "socraticode"
```

That record does not name the original debug file. Q129 requests its existing
pathname so the event can be read directly and cited with its original line
number. The documented `~/.claude/debug/latest` alias was absent; no directory
scan or new debug session was performed. **The direct event-file citation is
pending.** This quoted reported measurement is not a substitute for that gate.

## Draft reconciliation

The comparison is against these retained draft heads:

| Draft | Head | Disposition |
| --- | --- | --- |
| #776 | `cda3e5089f28d3839d5a5a1fc7fb0d5001e07ff7` | Folded: canonical registration-name hunks overlapping #834, plus the native-installer/profile ownership correction. Unverified historical provenance and a slot-owner rename are omitted. |
| #810 | `db9301440f0e363f17a1bad8c7d065bdb2861def` | Superseded: standalone SocratiCode metadata lacks the current plugin/Spec pairing; QMD stdio/CPU changes conflict with the accepted shared HTTP baseline. |
| #834 | `256ece4f3ce8a04908f8bb3c49082a0329b78e90` | Folded: canonical alias in Claude/Codex templates, map, worker profile, token carriers, bootstrap documentation and associated expectations. |

The old drafts remain untouched. The new draft lands only on the explicit
coordinator cue. Draft #897 changes the guard note in the same map; if both
drafts remain open, rebase this draft once after #897 lands.

## Local evidence and changed expectations

Eleven existing unittest modules ran through the native unittest CLI, each
bounded by `timeout 600` under `nice -n 10 ionice -c2 -n7`: installer, subagent
carrier, session carrier, task routing, adoption-document consistency, new-WSL
client configuration, gateway composition, settings application, config
rendering, Codex agents and worker lane. The retained matching outputs report
674 cases: 660 passed and 14 existing skips, with zero failures/errors. These
are local integration checks with fixture clients, not unchanged vendor tests
or model/provider acceptance. Earlier failures are retained privately, including
the log wrapper's restrictive umask mismatch; the test subprocess was corrected
to ordinary 022 without weakening any production permission guard.

Existing test expectations changed as follows:

- `test_install_claude_profile.py`: canonical server/carrier identities; the
  documented Claude `npx` versus Codex Node launch difference; preservation of
  only the intended native token. Added controls reject wrong commands/args,
  and final-argv coverage verifies all seventeen environment names and defaults.
- `test_new_wsl_client_config.py`: canonical server/worker/stub identities;
  expanded owner-switch coverage for the Spec, plugin and marketplace; portable
  registry pin and tagged marketplace; destination marketplace merge and the
  two-stage native-token rendering boundary.
- `test_codex_worker_lane.py`: canonical table lookup for startup timeout and
  lookup-error fixtures.
- `test_task_model_routing.py` and `test_token_lanes_subagent_start.py`:
  canonical graph-tool namespace in resolution and injected carrier fixtures.

The existing dated projection test already reads the last addendum; its code
is unchanged. The repository-only map check reports 409 pieces, 369 wired
(212 practice, 157 through a slot), 24 not wired, zero through a noninstalling
slot, 24 by their own entry and 16 authorization pieces. The append-only
addendum preserves previous projections as historical. Hash re-registration
uses `scripts/host_receipts.py:register_file`; final validator output is retained
privately and reported in the draft PR.

## Completeness and overturn condition

The read-only critic found the stale template comment, which is corrected, and
confirmed namespace, owner gates, token rendering and generated carrier hashes.
Remaining evidence boundaries are the pending original suppression-log citation,
a fresh host's registry/plugin acquisition and a fresh native client session.
No host configuration, plugin/MCP state, credentials, running paper session or
N2 bundle was changed. No fresh-host success is claimed.

Revisit this projection if the vendor changes its Claude manifest or command,
the installed client's expansion/suppression order changes, or a direct native
session with these exact effective commands connects two SocratiCode servers.
The native plugin plus same-command manual entry preserves the host environment
and existing manual tool names. Plugin-only registration would change those
names; the former Node/manual pairing does not match the selected plugin.
