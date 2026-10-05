# Decision: the new distribution's default holds out this repository's own token-lane carriers (2026-10-04)

**Decided by:** the owner's directive of 2026-10-04, relayed by the command center (session `wsl-architecture-design`)
and carried out by session native-agent-stack-99's unit U5-CARVE. It narrows Decision 3 of
`docs/decisions/2026-10-04-new-wsl-token-layer-default.md` (the token-lane carrier installed whole) for this
distribution only.

**Scope:**

- the token-lane carrier entry of `adoption/new-wsl/client-config-map.json`;
- the expectations of `tests/test_new_wsl_client_config.py` that named the carrier as wired, and the new test that
  states the hold-out;
- the counts and tables of `docs/decisions/2026-10-02-new-wsl-client-configuration.md` (recounted with the builder's
  own `--check`).

## Requirement

The owner, on 2026-10-04, answering the report that the full token stack cost 1.12 times the no-token arm in the
repository's own harness: "WE NEED THE CLEAN SOTA INSTALL, THE A/B TEST ITSELF SHOULD BE SOTA EXECUTE WITH
UPSTREAMCOMMANDS, YOUR ADAPTION AND TESTING METHODS MAYNOT BE SOTA ALIGNED WITH UPSTREMA REPOS FOR FULL RESOLUTION,
PLEASE FINALIZE OUR ECOSYSTEM WSL AS SOON AS POSSIBILE AT FULL SPEED RESOLUTED AT HIGEST QUALIY".

The command center read it as follows: every token-layer piece on NativeStack2604 installs by its upstream installer
with upstream default configuration, and what is this repository's own adaptation and not an upstream feature stays
out of the default. Context Mode's own Agent-prompt rewrite is an upstream feature and stays.

## Decision

The map entry for the token-lane carriers goes from `practice` to `not_wired:`. The entry matches eleven pieces: the
SubagentStart hook entry and the SessionStart hook entry of the Claude settings template, and the nine files that
`install_claude_profile.py` copies (`token-lanes-subagent-start.py`, `token-lanes-session-start.py`, the default block
and the five role blocks). The builder renders only wired pieces, so the new distribution's `settings.json` no longer
runs a carrier file and `--apply` no longer copies one.

The record's counts move from 392 pieces, 356 wired, 23 not wired and 13 authorization to 392 pieces, 345 wired, 34 not
wired and 13 authorization.

Not changed:

- the carrier files stay in the repository, byte-pinned in `adoption/hooks/claude/SHA256SUMS`, and the shared Claude
  settings template keeps both hook entries, so a host that renders the shared template (NativeStack among them) is
  unchanged and an adopter of the carrier opts in by wiring the entry back;
- the upstream pieces of the token layer (RTK, Context Mode, Headroom, Serena, qmd, jCodeMunch, codebase-memory,
  SocratiCode, Context Hub, ai-memory) keep their wiring.

## Evidence

- `python3 tools/adoption/new_wsl_client_config.py --check`: exit 0 on the CC's head `a8ccd21b` and after the change
  (local integration check).
- `--apply --dry-run --host example` on a scratch home: 9 plan lines name `token-lanes` before the change and none after.
- `--render --host example --with-authorization-settings`: `settings.json` and the instruction files hold no
  `token-lanes`; only `wiring.json`, which records what is not wired, names it. The test
  `RenderTests.test_the_token_lane_carriers_are_held_out_of_the_clean_default` asserts both.

These are builder-level checks of what the distribution would be configured with. They are not a measurement of token
use, which is the command center's upstream-harness A/B below.

## Alternatives considered

- **Keep the carrier wired until the A/B finishes.** Rejected: the owner's directive is a clean install now, and the
  repository's own harness, which produced the 1.12 times figure, is retired as an A/B instrument.
- **Delete the carrier files and template entries.** Not done: other hosts render the shared template, and the files
  are the byte-pinned reference an adopter would use.
- **Filter the carrier to the installed lanes** (the follow-up of Decision 3). Not done: a filtered carrier is more of
  this repository's own adaptation.

## What would overturn it

The command center's A/B on the frozen Harbor 0.23.0 setup at the operating point (Opus 5.5 at max effort, Claude Code
2.1.289, current tool releases) decides which tools stay default. If it measures a net saving for a carrier arm under
that upstream protocol, the entry goes back to `practice` in one edit and the eleven pieces are wired again; the new
test then states the opposite.
