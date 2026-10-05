# Research-skill round 2: BY_DESIGN, with unchanged lifecycle registration

Date: 2026-10-05. Slot: `instructions-skills/research-skill`.
North-star action: useful, verified public research from both native clients for
foundation engineering and US-equities R&D.

## Decision

Record **BY_DESIGN for the new vendor candidates**. Two blind Sol decisions
recommended configuring the existing research owner, with
`adopt_new_candidate=false`. Astra found no material split and did not require
the conditional Opus verification. A separate final completeness critic allowed
bounded non-adoption closure with no blocking omission. These are source-quality
decisions, not candidate acceptance or a new paired skill benchmark.
The exact returned reports and native execution proof are retained in
[the round-2 artifacts](../../evidence/artifacts/research-skill-round2-decision-20261005/README.md).

Register the already-installed `native-stack-research` entry through the central
skills manifest, with `claude_listing: on` and `codex_enabled: true`. This is an
administrative ownership repair: package the landed plan-of-record file unchanged,
including its existing embedded-DeerFlow contract. The package, original source
and both installed client copies have the same 1,602 bytes and SHA256
`313f41cbbb7ba5cbe9733d7b9c4caf85bd4fabf4c7a4cb5b40731f5449b941eb`.
It is repository-owned glue with an MIT license; `official: false` identifies
that provenance. The three audit verdicts remain `Unknown`; the prospective
skills.sh locator does not establish a registry listing or returned audit.

Freeze the origin at
[native-agent-stack@c148e049:research-harnesses-skill.md](https://github.com/seathatflowsinourveins/native-agent-stack/blob/c148e049efee75f8ea8a9a009e7b96b1e97f5c28/evidence/artifacts/new-wsl-install-plan-20261002/config/research-harnesses-skill.md#L1).
The immutable lifecycle directory is
[native-agent-stack@05e3ead0:adoption/skills/native-stack-research](https://github.com/seathatflowsinourveins/native-agent-stack/tree/05e3ead094d09a55e4652296d3d305edc2d10888/adoption/skills/native-stack-research),
tree `2d233cad78ad1d2da70721fd46fbe20088909558`.
The original plan file remains authoritative; this directory is its frozen
lifecycle snapshot. Source freeze was resolved after the native model stages;
their original pending-source wording remains in the returned reports. Never
register unlanded #723 content. When its native-headless contract lands, perform
a normal lifecycle re-pin, new hash and changed-skill validation.

## Method and retained limits

Follow the repository-quality rule: A, an actual user need; B, commit within
90 days, release within 180 days, Linux/WSL and documented client integration,
with overlap justified by a measured win; C, engineering and published evaluation
evidence; D, the strongest gate-passing choice with fewer parts for a tie and no
new local trial. The method is two blind Sol deciders with reversed candidate
order, an Astra difference critic, conditional live Opus refutation for an
adopt-true verdict or material split, and a final completeness critic over the
non-adopted set.
Source: [native-agent-stack@c148e049:repository-quality-rule.md:17](https://github.com/seathatflowsinourveins/native-agent-stack/blob/c148e049efee75f8ea8a9a009e7b96b1e97f5c28/docs/decisions/2026-10-04-repository-quality-rule.md#L17).

Reuse the converged input pack and its actual isolated uvx probes rather than
rerunning a local trial:
[native-agent-stack@cb55ae1c:research-skill-round-2-input-pack.md](https://github.com/seathatflowsinourveins/native-agent-stack/blob/cb55ae1c69674b43d5e4a52b31044566c5d906bf/docs/decisions/2026-10-05-research-skill-round-2-input-pack.md).
Each model ran sequentially after the paper window using installed
[Codex 0.160.0](https://github.com/openai/codex/releases/tag/rust-v0.160.0),
native `exec --json --skip-git-repo-check`, a read-only sandbox, frozen schema
and separate non-Git scratch directory with an isolated public provider profile.
The reviewed native dispatch pattern is
[native-agent-stack@46c00618:codex_job.py:686](https://github.com/seathatflowsinourveins/native-agent-stack/blob/46c006186f15abfe282376643df235060b2dac10/tools/sota-convergence/landscape-sweep/codex_job.py#L686).
No self-written model runner was used.

Both deciders requested `cx/gpt-6.1-sol-max` at max through OmniRoute; Astra
requested `cx/gpt-6-astra-max` at max; the final completeness critic requested
Sol at max. All four native commands exited 0, and each exported report's JSON
values equal its actual final native agent-message event; publication adds only
a terminal LF. Served model and effort are not
independently attested. Native counter snapshots are retained separately per
stage; provider billing is unknown. Cached input and reasoning output are
subsets, not additional usage. Astra's public profile copy has one extra trailing
newline; parsed controls match and the blind decider profiles are byte-identical.
The original hashes preserve that whitespace-only correction.

Public-source access failed inside the isolated sessions: unsupported open,
search timeout/502, and shell DNS failures. Those are retained source-access
limits, not candidate runtime failures. Successful root GitHub API source
observations are classified separately; they do not retroactively repair the
models' failed fetches. The unstable standalone-web-search warning is retained
even though every native turn completed. The historical direct-consensus
activation hold is not a retained blind round-1 or Opus verdict; no research-skill
result was found in the scoped historical blind layer/critic artifacts.
A bounded preparation helper returned no conclusion before interruption and is
not counted as a completed critic.

Sol A names the existing owner and Sol B leaves `chosen_candidate` null while
recommending that owner in its reasoning. Astra classifies this as a
representation difference, not conflicting adoption decisions. Other differences
concern old activation criteria versus the new quality rule, dependency currency,
and the distinction between a vendor plugin, external MCP dependency, HTTP entry
and internal methodology. The final critic's closure applies to this bounded
non-adoption decision; the incumbent remains uncertified for useful research and
both-client discovery.

## Alternatives and primary sources

| Candidate | Gate consequence |
| --- | --- |
| GPT Researcher vendor plugin, v3.7.0 | The root MCP descriptor executes `uvx gpt-researcher`; the existing input-pack probes find no executable in current PyPI 0.16.1 or explicit 0.16.0. Plugin metadata does not prove a runnable MCP service. |
| Separate gptr-mcp dependency | Its observed latest commit is 2025-11-07 and release v0.0.1 is 2025-03-30, outside the quality-rule currency windows. Original source also prints ordinary stdout before STDIO service and retains a busy loop. |
| DeerFlow HTTP skill, v2.1.0 | A real gateway/threads/stream entry, distinct from the installed embedded route. It adds runtime surface without a gate-passing comparison or documented both-client/worker result in this evidence. |
| DeerFlow internal deep-research skill, v2.1.0 | A research-methodology skill, distinct from the HTTP entry. Its presence does not prove native client invocation, worker handoff or useful research. |
| Existing native-stack-research owner | Avoids a duplicate entry and repairs central lifecycle ownership with unchanged bytes. Existing installation alone does not certify runtime, lock state or model visibility. |

The root verified the original sources, not worker summaries:

- [assafelovic/gpt-researcher@0957c301:.mcp.json](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/.mcp.json),
  [plugin.json](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/.codex-plugin/plugin.json),
  and [pyproject.toml](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/pyproject.toml).
  The MCP file is at repository root, correcting the mistaken plugin-directory locator.
- [assafelovic/gptr-mcp@63884773:server.py:277](https://github.com/assafelovic/gptr-mcp/blob/63884773685b1f12c7f0d9e283b3d71a5b9b5fda/server.py#L277),
  [commit metadata](https://api.github.com/repos/assafelovic/gptr-mcp/commits?per_page=1)
  and [release metadata](https://api.github.com/repos/assafelovic/gptr-mcp/releases?per_page=100).
- [bytedance/deer-flow@345f08be:claude-to-deerflow/SKILL.md](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/skills/public/claude-to-deerflow/SKILL.md),
  [chat.sh:55](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/skills/public/claude-to-deerflow/scripts/chat.sh#L55)
  and [deep-research/SKILL.md](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/skills/public/deep-research/SKILL.md).
  The original chat script sets pro subagents false and ultra true, correcting
  the broader pro-mode claim.

No new vendor is adopted, replaced or benchmarked. The unchanged packaged skill
passed the pinned upstream metadata validator:
[anthropics/skills@8a1541c4:quick_validate.py](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/scripts/quick_validate.py).
This is a metadata result, not a behavioral A/B or runtime acceptance. A future
changed or newly selected skill must use skill-creator's paired benchmark or
promptfoo under the repository's existing skill gate.

## Listing and lifecycle consequences

The declared Claude description sum becomes 9,637 and the Codex eligible sum
9,318 across 25 catalog-eligible manifest skills. The repository templates retain
Claude's existing 0.05 listing fraction and Codex's 6,000-token catalog budget;
only the new Claude override and corresponding Codex count/budget commentary
change. No new per-skill Codex disable is added. These sums and eligibility flags
do not prove fresh-session model visibility, especially with system and plugin
skills. Sources:
[native-agent-stack@c148e049:skills-llm-native-listing.md](https://github.com/seathatflowsinourveins/native-agent-stack/blob/c148e049efee75f8ea8a9a009e7b96b1e97f5c28/docs/decisions/2026-09-30-skills-llm-native-listing.md)
and [tests/test_skills_manifest.py:304](https://github.com/seathatflowsinourveins/native-agent-stack/blob/c148e049efee75f8ea8a9a009e7b96b1e97f5c28/tests/test_skills_manifest.py#L304).

Templates are a draft proposal. No live client settings are applied. The co-op's
readiness-runner is the sole shared-host plan-apply writer under ruling 10; this
lane runs no `install.sh`, lifecycle installation or restart. After review,
that owner must use the repository lifecycle and retain native lock/tree
observations and fresh Claude/Codex discovery evidence. Worker availability is
still its own manifest and runtime gate. Matching installed SKILL.md bytes does
not prove the new pinned directory matches an existing installation lock.
Source: [native-agent-stack@c148e049:adoption/skills/lifecycle.md:54](https://github.com/seathatflowsinourveins/native-agent-stack/blob/c148e049efee75f8ea8a9a009e7b96b1e97f5c28/adoption/skills/lifecycle.md#L54).

The worker manifest explicitly excludes this native-host entry with an
`adoption_ref`, reason and overturn condition, as its existing central contract
requires. The frozen skill calls host-owned XDG scripts; no supported worker
bridge or useful worker research result is qualified by this unit. Exclusion
records that open gate without claiming a worker failure or universal absence.
Sources: [native-agent-stack@05e3ead0:SKILL.md:8](https://github.com/seathatflowsinourveins/native-agent-stack/blob/05e3ead094d09a55e4652296d3d305edc2d10888/adoption/skills/native-stack-research/SKILL.md#L8)
and [native-agent-stack@c148e049:worker skills README, Gates of reused adoption skills](https://github.com/seathatflowsinourveins/native-agent-stack/blob/c148e049efee75f8ea8a9a009e7b96b1e97f5c28/blueprints/runtime-workers/skills/README.md#gates-of-reused-adoption-skills).

## Completeness inputs and overturn conditions

The final completeness critic reopens these bounded questions for the next
task-scoped sweep: the landed CLI/SDK owner contract and exact invocation; plugin
versus separate MCP dependency; HTTP versus embedded and internal methodology
routes; overlap and worker handoff; both-client discovery; and research across
primary papers, PDFs and tables rather than only software documentation.

Overturn BY_DESIGN when a maintained upstream entry passes the A-D gates and
provides a credible published or upstream-native comparison that justifies the
additional runtime and wins the named research task. Correct the missing console
entry or stale dependency with a current supported release before reconsidering
the GPT MCP route. A landed #723 contract change triggers the incumbent's normal
lifecycle re-pin and changed-skill validation; it does not certify useful research
by itself. A failed native discovery, lock or worker check reopens that gate
without inventing a quality win or treating source review as runtime acceptance.
