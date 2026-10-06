---
status: proposed
date: 2026-10-06
review_by: 2027-01-01
decision-makers: command center
consulted: ns2604-coop, grand-catalog lane
informed: Phase 1 operators
---

# Carry a portable NativeStack2604 Terminal fragment

## Context and problem statement

The approved Phase 1 transfer needs repository-carried Terminal profiles that
future hosts can inspect and roll back. The observed live fragment contains
machine paths and session bindings unsuitable for publication. This unit serves
recoverable native engineering sessions used to build complex projects.

## Decision drivers

Preserve native Terminal identities, client titles, measured quiet bells and
Claude truecolor; keep private session binding native; avoid host changes in a
repository lane; preserve the old distribution through R2; separate repository
checks from Windows deployment acceptance.

## Considered options

1. Copy the live fragment verbatim.
2. Carry a portable fragment, with private bindings in owner-supplied launchers.
3. Leave the fragment and its checker only in private host state.

## Decision outcome

Choose option 2, following the co-op's A19/A20 source and custody rulings. Carry
`windows/nativestack2604.json`; keep the `NativeStack` folder and the existing
names and derive explicit GUIDs with Microsoft's supported recipe. Direct resume
profiles use native pickers; special-role launchers live outside Git. Deploy is
blocked until their owner verifies replacement session continuity, especially
the Co-op resume profile used after restarts. Librarium's clone/vault cwd remains
DEFERRED to P1-CLI, with its profile hidden. Librarium course stays distinct.

Port the maintained checker, retaining its policy and JSONC fixture parser,
while making repository files the default and removing discovery of host client
configuration. Add only the demonstrated gaps: explicit identity checks and the
known host-launcher classifications. A narrow publication exception masks only
a correctly derived, unique `profile.guid` in `nativestack2604.json`; all other
UUID, path and credential scans remain active, including duplicate and escaped
JSON controls. The inherited GUID helper supports these ASCII profile names;
other names fail explicitly rather than receiving a guessed identity.

Keep the four lane profiles in their own commit because the pending orchestration
decision may supersede them. HTTP 21128 and WebSocket 21129 are listeners of the
same running OmniRoute process. Old HTTP `omniroute-fw` 20129 has no established
2604 equivalent; its prompt references remain deferred to Phase 3. No prompt
body, gateway change or client configuration is authored here.

### Consequences

The fragment is reproducible and reviewable without reading sign-in or session
files. Operations reuses the byte-identical maintained entry script; Operations
and Local Chat still depend on P1-CLI's installed native command. Host launcher
contracts are prerequisites, not evidence that those launchers exist or work.
Windows settings, fragments and all deployment changes remain the co-op's work.

## Validation

The receipt separates source review, local integration and synthetic controls.
Run the port, the touched validator/client-default modules, publication validation
and whitespace checks. HTTP status/listener observations qualify only the port
roles, not Terminal deployment or UI behavior. Independent review and host
apply/read-back remain pending. `windows/README.md` supplies exact apply, read-back
and byte-restoring rollback commands; those commands have not been executed here.

## More information

- `native-agent-stack@ecfa11276:docs/decisions/2026-09-28-terminal-experience.md:57-64,292`
  supplies the adopted visual/bell policy; its old release state is historical.
- `nativestack-practice@a7b8018524575cabbd979e6f2e1c84ee6e94700f:checks/check-terminal-profiles.py:39-44`
  and `:windows/nativestack.json:67,79`, plus `:ops-entry.sh:1-6`, supply the port and
  native Operations/Local Chat launch contracts.
- [Microsoft fragment extensions](https://learn.microsoft.com/en-us/windows/terminal/json-fragment-extensions),
  updated 2025-11-12 and checked 2026-10-06, supply identity and UTF-8 deployment.
- `microsoft/terminal@dc8ae365847d41f62d1ebca93815bb00959bc12f:src/cascadia/TerminalSettingsModel/Profile.cpp:307-318`
  and `:doc/cascadia/profiles.schema.json` match
  [v1.25.2733.0](https://github.com/microsoft/terminal/releases/tag/v1.25.2733.0),
  published 2026-10-02. This corrects any inference that the decision's older tag
  is today's latest stable release; no installation was performed.
- The dated source hash/transformations receipt retains co-op A19/A20 and the
  live fragment/lanes source locators without their private values.

Overturn this format if an independently reviewed native deployment demonstrates
identity collision, loss of intended session binding, or a maintained upstream
format replacing fragments. Revisit the lane-profile commit when the command
center's tab-orchestration decision arrives, and the Librarium declaration when
P1-CLI establishes its clone/vault path. Native UI acceptance must be retained
separately before any deployed-state claim.
