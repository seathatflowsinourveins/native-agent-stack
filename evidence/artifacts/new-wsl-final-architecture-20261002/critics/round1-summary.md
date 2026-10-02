# Contested slots: Claude critics' verdicts (handoff 2), by session 80 (written 2026-10-02T04:03:56Z from date -u)

Method: plan section 4.4. Per layer two Opus critics with page access, blind to which record came from which model family (your manifest rows with the family fields removed were "the single record"; the two blind Sol-ultra order results were "the two-pass record"), record labels swapped between the two critics. Rules given: one owner per job; the no-install default; gates, then performance evidence, then seamlessness, then fewer moving parts; criteria.txt unchanged. Workflow wf_d8e68ea6-cf6, 6 agents, all returned. Full returns with every URL and quote: session-80-20261002/critic/critics-result.json (journal copy beside it).

**Both critics agree on every item.**

| Layer | Item | Verdict (critic 1 / critic 2) | Reason in one line |
|---|---|---|---|
| code-navigation | ast-grep beside Serena | install / install (high, medium) | two jobs: AST-pattern structural search has no other owner; Serena owns symbols and references |
| code-navigation | Claude Code LSP plugins beside Serena | do not install / do not install (high, high) | same job as Serena, Claude Code only, no measured gain |
| ci-supply-chain | Dependabot | install / install (medium, high) | none of zizmor, actionlint, Syft, attest moves a pin or opens update PRs; it is a hosted service configured by .github/dependabot.yml, nothing on the host |
| ci-supply-chain | CodeQL SARIF upload as its own slot | do not install / do not install (high, high) | transport, not a scanner; zizmor-action already embeds the pinned upload step; keep it as zizmor's integration step, not a slot |
| cross:wsl-distro | Ubuntu 26.04.1 | install / install (high, high) | the single default; registry default, support to April 2031 |
| cross:wsl-distro | Ubuntu 24.04.5 as co-finalist | do not install / do not install (medium, high) | a second owner of one job; named rollback only, returns only on a release-caused 26.04 failure with no in-release remedy |

Resulting layers: code-navigation = Serena + ast-grep; ci-supply-chain = zizmor, actionlint (kjanat), Syft, attest, Dependabot; base distribution = Ubuntu 26.04.1.

Each verdict carries its overturn measurement (in the JSON). The ones worth scheduling:
- Serena in Claude Code: upstream's own docs say Claude Code rarely calls Serena without its system-prompt override and reminder hooks. The acceptance check on the new host must assert real Serena calls per session; if the call rate is near zero the LSP plugins take the Claude side.
- ast-grep: sealed syntax-shaped questions, with and without it, precision and recall plus session tokens.

Install notes the critics verified upstream today:
- ast-grep 0.45.3: `pip install ast-grep-cli` ships a prebuilt manylinux wheel; npm also works; call `ast-grep`, never `sg` (Linux has `sg` for setgroups).
- Serena v1.7.0: the complete sequence ends with `serena setup claude-code` and `serena setup codex`; one of the two order results stops at `serena init`, which registers neither agent.
- Dependabot: commit .github/dependabot.yml with a cooldown (zizmor audits a missing one); never dependabot-core or its CLI.
- zizmor-action defaults to upload mode (needs security-events: write and does not fail on findings); choose that or advanced-security: false on purpose.
- Ubuntu 26.04: rust-coreutils (20 CVEs listed in the release notes, remedy coreutils-from-gnu), sudo-rs, apt-key removed (skip NVIDIA's apt-key del step), /tmp is tmpfs; install as Ubuntu-26.04 or the checksum-verified file, because the name Ubuntu follows the newest LTS.
- Manifest hygiene: installs_nothing_extra is false on attest, Dependabot and codeql-sarif although each is a GitHub-hosted feature; the base-distribution row's repository field points at ubuntu.com/download/server, not the image source (releases.ubuntu.com, registered in microsoft/WSL DistributionInfo.json).
