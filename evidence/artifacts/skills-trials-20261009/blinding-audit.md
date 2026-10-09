# Blinding audit after the sealed return

The independent evidence review raised a specific question: does retaining
`[QUALITY-LOW]` and `[SCHEMA-HIGH]` in finding text violate the preregistration's
omission of rule identifiers?

At the exact NVIDIA pin, [models/result.py:80](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/src/skillevaluator/models/result.py#L80)
defines a finding with category, severity and message. Its
[tag property:126](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/src/skillevaluator/models/result.py#L126)
formats the category and severity into `[CATEGORY-SEVERITY]`. These retained
labels group schema/quality findings by severity; they are not individual
rule identifiers. The runner retains their native message text as the protocol
requires, while omitting the agnix individual rule identifiers, source names,
pins and source paths from the judge packet. No comparison or judging rerun
was made to address this question.

The anonymous packet contains five such category/severity labels:
`[QUALITY-HIGH]`, `[QUALITY-LOW]`, `[QUALITY-MEDIUM]`, `[SCHEMA-HIGH]` and
`[SCHEMA-MEDIUM]`. A byte scan finds none of the four source identities. The
judge saw only anonymous arms, expected task labels and native finding text.
The full model event record contains only reasoning and the final agent
message, with a completed turn; there are no native tool-call items. The
sealed judge reports `origin_leak_detected=false`. Native wording and
category styles could still permit source inference by a judge familiar with
the tools, so no fingerprint-resistant or double-blind claim is made.

The preregistration lock and source-map hash preceded native execution. The
judge return was hashed at seal before the private map was read for metric
calculation and copied as `arm-map-reveal.json`; that copy matches the original
locked hash. `native-session-retention.json` binds the complete private event
files to the published files, with recorded thread-ID and home-prefix redactions.
The fresh judge launched with `--ignore-user-config`, `--ignore-rules`, no MCP
configuration and an empty non-git working directory, at the same specified
model and profile-equivalent effort. Its prompt did not include the
preregistration's source section, private mapping, source reviews, verdicts or
prior outcome labels. The first CLI setup failure produced no model event or
judgement, and is retained as such.
