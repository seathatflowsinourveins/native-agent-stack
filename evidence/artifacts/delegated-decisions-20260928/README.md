# Delegated decisions, 2026-09-28: retained lane evidence

This directory holds the returned output for the decision record
[`docs/decisions/2026-09-28-delegated-decisions.md`](../../../docs/decisions/2026-09-28-delegated-decisions.md).
It is local judgment evidence, not a behavior test and not an upstream acceptance
([evidence classes](../../../docs/acceptance-evidence-policy.md)).

## Lanes

Each item went to two model families. Every lane read one frozen packet, used no network, and edited nothing.

| Item | Lane | Client, model, effort | Returned | Usage (provider-returned) |
| --- | --- | --- | --- | --- |
| M4 | GPT-6 | `codex exec -s read-only`, codex-cli 0.157.1, requested `gpt-6-astra`, `model_reasoning_effort=max` | [`m4/gpt6-return.md`](m4/gpt6-return.md): "VERDICT: conflict", "Disposition: remove now" | input 86,361 (cached 62,720), output 6,422 (reasoning 5,176) |
| M1/M2 | GPT-6 | as above | [`m12/gpt6-return.md`](m12/gpt6-return.md): "DECISION: keep" | input 21,535 (cached 17,792), output 2,898 (reasoning 2,588) |
| M1/M2 | Claude | Agent tool, `evidence-reviewer`, `model: opus`, one Read | [`m12/claude-return.md`](m12/claude-return.md): "DECISION: keep" | 45,415 subagent tokens (Agent tool total; split not reported) |
| M3 | GPT-6 | as above | [`m3/gpt6-return.md`](m3/gpt6-return.md): "DECISION: latest-opus" | input 21,206 (cached 0), output 2,173 (reasoning 1,899) |
| M3 | Claude | Agent tool, `evidence-reviewer`, `model: opus`, one Read | [`m3/claude-return.md`](m3/claude-return.md): "DECISION: latest-opus" | 42,529 subagent tokens (Agent tool total; split not reported) |

The Claude side of M4 is not a lane on this packet:
- the independent `evidence-reviewer` stage of workflow `wf_811a77e9-a4e` flagged the untested trial rule and the L20/L28 "surface tension" with `AGENTS.md:16`;
- the coordinator and the skills-trial owner session then each read the full pinned `SKILL.md` and found a conflict ([coordination](coordination.md)).

The Codex event stream records no model field. The model above is the pinned `-m` request, not an observed resolution.

## Packets

- `*/packet.redacted.md` is each frozen packet with the user-level `~/.claude/CLAUDE.md` lines replaced by `<… sha256 …>` placeholders. The digest is over the line text only.
- `gpt6-runs.json` gives:
  - the original and published SHA256 of each packet and each return;
  - the returned usage;
  - the digests of M4's three input files: the pinned `SKILL.md` (`2befe7fc…`, obra/superpowers@8ca22dba), `AGENTS.md` at `3058b237`, and the skills-trial excerpt (`docs/decisions/2026-09-25-skills-trial-and-usage.md` lines 270-300 and 825-845 at `3058b237`).
- Paths in the returns are normalised to repository-relative or `~`.
- `m12/claude-return.md` quoted two fragments of user-level lines 15 and 16. They are replaced by `<… fragment, redacted>` placeholders, the same redaction the packet uses.
- `gpt6-runs.json` separates `original_*` digests, over the unredacted local files, from `published_*` digests, over the files here. M4's return differs between the two only by path normalisation.

## Coordination

The peer positions, the #444 acknowledgement permalink and the Gate A liveness observations are in [`coordination.md`](coordination.md).

## Host read-back (M3)

A fresh headless session was run from a scratch directory outside the repository:
`claude -p '<quote the effort-max bullet>' --model sonnet --output-format json --no-session-persistence`.

- Client: Claude Code 2.1.283.
- Result: exit 0, a message array whose last element is `subtype: success` with `is_error: false`.
- Model: `claude-sonnet-5` (from `modelUsage`).
- Returned text: "The latest Opus at effort max for design, build, research, review, verification and synthesis."

Before the edit the file held one "Opus 5.5 at effort max" and no "The latest Opus at effort max". After it, the counts were 0 and 1, and a diff against the backup showed only line 40 changed.

## Research and review workflows

These are counts from the Workflow tool, one per run. They are not summed with the rows above.

| Run | Agents | Subagent tokens |
| --- | --- | --- |
| `wf_c661631a-1be` (status sweep and next-move refutation) | 6 | 1,357,422 |
| `wf_811a77e9-a4e` (five decision researchers and five refuters) | 10 | 1,821,605 |
