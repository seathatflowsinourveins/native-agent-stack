# Daily native skill use and Claude parent routing

Pin the installed official Claude API skill in the existing 30-day trial,
schedule the repository's three native collectors on the live main clone,
and show only skill names and counts by native lane group on the Fleet page.
Seven on-listed skills have zero baseline Claude uses and positive Codex
skill-file reads. Native BEFORE measurements establish that six are wired;
only security-audit needs a proposed invocation cue. No skill is pruned here.

## SOTA sources

- `anthropics/skills` at `dbd4588f9e1033efb41dad4bef2f7947c8993d44`:
  [marketplace entry](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/.claude-plugin/marketplace.json#L46)
  defines `claude-api@anthropic-agent-skills` and `skills/claude-api`;
  [SKILL.md](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/claude-api/SKILL.md#L3)
  supplies the unchanged description, and `LICENSE.txt` supplies Apache-2.0.
  Its 105146 bytes hash to
  `40537cca17c4aa86e4ce83ced39efcbfb1204905e3cf4c4ff98f2eab011e4b7f`;
  public upstream and the installed native cache agree. The manifest records
  the upstream directory tree SHA, description's 1068 Unicode code points,
  plugin identity and native skill name `claude-api:claude-api`.
- Installed Claude Code 2.1.296 and
  `anthropics/claude-code@2301018b1f61073c501a8e7a4813ef48c239163b`:
  [release history](https://github.com/anthropics/claude-code/blob/2301018b1f61073c501a8e7a4813ef48c239163b/CHANGELOG.md),
  [skill discovery](https://code.claude.com/docs/en/skills#where-skills-live),
  [description/invocation control](https://code.claude.com/docs/en/skills#frontmatter-reference),
  [visibility settings](https://code.claude.com/docs/en/skills#override-skill-visibility-from-settings)
  and [native evals](https://code.claude.com/docs/en/plugin-evals), read 2026-10-10.
  Native `installed_plugins.json` uses `installedAt`, `gitCommitSha` and
  `installPath`. Registry/pin and SKILL.md checks attest plugin provenance;
  they do not claim its enabled state. The doctor capture measures listing/use.
- Existing collector reference implementation at main
  `e1c88ff3d7edc71052d6fb4eed8422438b06efaf`: `tools/skill-usage/skill_usage.py`
  and `examples/claude-native/workflows/child-usage.mjs`. Reuse their parsers,
  native cost/turn checks, timestamp windows, group aggregation and privacy
  boundary. The daily adapter introduces no competing event collector.
- `systemd/systemd` v259.5 at
  `b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a`:
  [timer semantics](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.timer.xml)
  and [user verification](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/src/analyze/analyze-verify.c).
  Adopt the repository's `@REPOSITORY@` live-clone rendering convention,
  daily calendar, persistent catch-up and randomized start. Unit verification
  uses a fixture runtime directory, without starting or installing units.

## What the measurements mean

The host collector requests `--run-skill-doctor --codex-root <explicit-root>
--window 7 --json`. Claude doctor `uses` is lifetime; its seven-day token
column does not convert it into a seven-day invocation count. The existing
collector also includes the trial's 30-day window. Native plugin installation
age comes from `installedAt`, not a guessed date or the Vercel skill lock.

The Codex group collector requests `--lanes --since <seven-days-ago>
--until <now> --json` over the same explicit root. Its skill-file reads are
a usage proxy, labeled as reads. The Claude collector requests
`child-usage.mjs --lanes-sweep --root <explicit-root> --since <seven-days-ago>
--until <now>` and counts native `Skill` calls by spawn path and agent type.
Group views overlap and are not summed. Missing or failed sources remain
UNKNOWN. The latest private projection stores names, counts, timestamps and
measurement flags; prompts, paths, session IDs and account fields are dropped.

## Raw reads and de-inflated use

Retain raw SKILL.md path-read and `$name` mention counts. The new `use_counts`
counts at most once per native session and skill from the union of its own
windowed read/mention signals. Inherited copied records add no use. Sessions
reading more than **N = 26 distinct SKILL.md names** in that window are omitted
from use, including their mentions. Native session metadata identities join
duplicate rollout parts in memory; identities are never published.

Measured the shipped collector first-hand at `2026-10-10T15:24:25Z`, seven-day
window, 2799 rollout files, zero parse errors. Its distinct-read distribution
is: 0:885, 1:910, 2:447, 3:181, 4:107, 5:58, 6:39, 7:30, 8:26, 9:30,
10:9, 11:9, 12:20, 13:17, 14:11, 15:3, 16:6, 17:5, 18:2, 22:1,
36:1, 37:1, 41:1. The zero bin includes scanned sessions without a windowed
read. N=26 lies in the observed gap between 22 and 36 and excludes the three
broadest sessions while retaining the next observed tier. It is a transparent
bulk-scan heuristic, not proof of research intent or native skill activation.
Future distributions and known legitimate broad sessions can overturn it.

An initial exploratory histogram used the last metadata header and joined
inherited headers; it is superseded by the shipped scanner's first-header
rule from the pinned main reference implementation. The calibrated report
uses the actual implementation and its regression-tested session join.

| Skill | Raw reads (7d) | Use (7d) |
| --- | ---: | ---: |
| security-audit | 109 | 69 |
| gh-fix-ci | 101 | 71 |
| gh-address-comments | 87 | 53 |
| frontend-design | 60 | 20 |
| typesafe-ai | 17 | 11 |
| security-best-practices | 8 | 4 |
| security-threat-model | 6 | 3 |

Every listed skill had zero explicit `$name` mentions in this sample. The
synthetic bulk-scan regression demonstrates two raw reads per skill and zero
use; repeated ordinary reads plus mentions count as one use. It failed before
the new metric existed. The page's primary Codex count and zero-use list use
use; raw reads remain beside it. Trial zero-use flags also use this metric.

The baseline files remain outside the repository. Their supplied SHA-256s are
`f9bb0dfc164223fd5bcccaccd0895871f843de3166c4e5de495f71bb1675ad95`
for the host report and
`3963beb88ba0c03fd5a9a493c8870637b8b8ce33178374c4ab2ae1cbe18a391c`
for the Codex group report. Their seven target rows are present/on-listed,
with Claude uses zero and last_used never. This is measured usage/discovery,
not a causal model-trigger test.

## Wiring and untested boundary

Native `skillOverrides` controls visibility, has no description replacement,
and does not govern plugin skills. Preserve the selected vendor files.
The authored `native-skill-routing` skill adds only a security-audit invocation
description and directs the parent to call that target before Bash or repository
search. Existing read-only security-reviewer already preloads
security-best-practices and has no Skill tool; preload guidance is not an
invocation event. No worker tool grant is widened.

The project `.claude/skills/native-skill-routing/SKILL.md` is the single
authored source. Native project skill discovery can therefore reproduce
AFTER routing from a worktree of this PR, before any user-profile application.
The twenty-four `trigger-cases-v4.json` requests give cc-native-practice seven
initial positives, seven near-miss negatives, three additional security-audit
phrasings, one actual repository-relative source-path request and six indirect
requests for its native BEFORE/AFTER harness. Its comparability base stays
`60004bb1dd581e00e3303c54d93435bb72f76952`; the PR's assigned base is separate.

The CC-owned BEFORE receipt at 2026-10-10T15:44:29Z measured 21 runs on
Claude Code 2.1.296. gh-fix-ci, gh-address-comments, frontend-design,
typesafe-ai, security-best-practices and security-threat-model each invoked
3/3; security-audit invoked 1/3. The public baseline holds only those skill
names/counts and dispositions. The private summary's SHA-256 is
`36b7e6b39df077def1d5ce2408fc079d6d313f3d01a4fc8d7bb184f01f0662dc`.
It is a real native trigger observation for explicit task prompts, not a
general success-rate estimate. The page labels zero baseline use on the six
as wired, no demand; their descriptions and routes are unchanged.

The original [Cloudflare description](https://github.com/cloudflare/security-audit-skill/blob/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8/skills/security-audit/SKILL.md#L3)
is pinned at `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8`.
Compared the unchanged Cloudflare description's broad security-question and
full-workflow branches with the explicit request language of the two OpenAI
security skills. The smallest supported change without mutating pinned vendor
bytes is an authored description that names vulnerability/injection review and
directs an immediate `security-audit` Skill call before code exploration.
Native visibility settings cannot override vendor description text. This
project skill is therefore a proposed invocation cue, not a replacement of the
vendor skill. Expanded BEFORE/AFTER measurements can reject or refine it.

The settled CC security-audit BEFORE observation is 16/23 invoked (Wilson 95%
0.49–0.84) and 6/23 in turn one, compared with 17/18 in turn one for the six
other initial targets. A six-turn repeat set invokes 8/10. Preserve those
definitions: loading after exploration differs from loading before it.
The explicit trigger/exclusion phrasing follows the sibling descriptions at
`openai/skills@49f948faa9258a0c61caceaf225e179651397431`:
[security-best-practices](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/security-best-practices/SKILL.md#L3)
and [security-threat-model](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/security-threat-model/SKILL.md#L3).
Anthropic's
[skill-creator description guidance](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/skill-creator/SKILL.md#L67)
at `anthropics/skills@dbd4588f9e1033efb41dad4bef2f7947c8993d44:skills/skill-creator/SKILL.md:67`
identifies the description as the primary trigger and requires specific use
contexts; line 52 asks which phrases/contexts should trigger. The local mirror
HEAD and live upstream HEAD were both verified at that same pin. Only the
authored security-audit cue changes; the actual vendor file remains pinned.

Fixture tests verify native plugin namespace/age, unchanged plugin hashes,
profile discovery and preservation, native collector command lines, private
count projection, Fleet rendering and unit rendering. Namespace, profile and
page regressions failed before the fixes. They establish wiring contracts,
not semantic AFTER selection. Seven native plugin-eval cases and the expanded
CC case file are prepared. cc-native-practice's AFTER result and the optional
post-install personal profile read-back remain explicitly unmeasured here.

The CC installs/enables the timer and applies the parent routing skill after
landing. Real Claude probes, accounts and credentials are never read by this
lane. The task's designated GPT read and CC landing remain separate gates.
