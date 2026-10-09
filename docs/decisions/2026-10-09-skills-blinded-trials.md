# Blinded instructions and skills trials (2026-10-09)

agnix remains a trial candidate, SkillEvaluator remains keep-but-compare, and
openai/skills remains stale under the 90-day default-branch maintenance rule.
Neither candidate qualifies for ADOPT-NOW. This decision proposes no host
configuration apply and does not replace a whole skills repository.

## Sources and frozen method

This trial followed the maintained vendor implementations:

- [agent-sh/agnix v0.57.0](https://github.com/agent-sh/agnix/tree/2c0e4efede3181599eca37619e8067ae2d941c00),
  its release install, native efficacy harness and Codex-target JSON validator.
- [NVIDIA/SkillEvaluator v0.5.0](https://github.com/NVIDIA/SkillEvaluator/tree/7304d76cde371287b67ea99653409d014b6b9c85),
  its pinned uv install and native offline Tier 1 schema/quality checks.
- [openai/skills](https://github.com/openai/skills/tree/49f948faa9258a0c61caceaf225e179651397431)
  and [anthropics/skills](https://github.com/anthropics/skills/tree/683bc88e56f3e09ba94f7055977f3d3aa499f202),
  their unmodified reference quick validators as controls.
- The [Agent Skills specification](https://agentskills.io/specification),
  for independent format labels and the reference-resource integrity cases.

The [preregistration](../../evidence/artifacts/skills-trials-20261009/PREREGISTRATION.md)
froze the same twelve skill cases, two separate instruction cases, metric,
judge, thresholds and adoption gates before native outcomes. Its lock retains
the protocol, corpus and private arm-map hashes. A fresh standard-tier
`cx/gpt-6.1-sol` native session judged anonymous reports with no parent history,
user configuration, project rules or tool calls. Its sealed return reports no
origin leak. The map was revealed only afterward. The complete native events
are retained with a recorded thread-identifier redaction. No previous
unblinded scores were reused.

## Measured static result

The strict preregistered metric counts seeded detections and unsupported
defect assertions. The case labels, formula and full reports are retained in
[RESULT.json](../../evidence/artifacts/skills-trials-20261009/RESULT.json).

| Arm after reveal | Seeded defects detected | Unsupported assertions | Clean cases accepted | F1 |
| --- | ---: | ---: | ---: | ---: |
| agnix | 9/9 | 0 | 3/3 | 1.000 |
| SkillEvaluator, schema plus quality | 8/9 | 95 | 0/3 | 0.143 |
| OpenAI reference validator | 7/9 | 1 | 2/3 | 0.824 |
| Anthropic reference validator | 7/9 | 0 | 3/3 | 0.875 |

agnix passes the shared static threshold and gains 0.125 F1 over the stronger
reference control, exceeding the frozen 0.10 gain threshold. It detects a
missing local instruction reference, but warns that the clean AGENTS fixture
needs a project-context section. The judge labels that warning unsupported
under the valid-control rubric, so the separate instruction gate fails.

SkillEvaluator's quality mode applies a richer template than the minimal
format specification. Its warnings about examples, purpose, prerequisites,
limitations and troubleshooting, plus repeated structured/legacy findings,
drive the strict assertion-count penalty. This diagnostic establishes a
mismatch for a format-integrity gate, not poor semantic evaluation or security
quality. Tier 2 overlap, Tier 3 live evaluation and a schema-only arm were not
run. Neither reference validator detects the absent local resource or empty
description; the OpenAI control also rejects the valid compatibility field.

## Adoption stages and maintenance re-rule

Both vendor installs ran in lane-owned prefixes at exact pins. agnix's official
release archive hash matched the vendor sidecar and GitHub digest, and its
native efficacy harness passed 61/61 cases. SkillEvaluator's installed Git
revision matched the pin; 51 schema, 144 quality and 20 CLI-defaults upstream
tests passed in the vendor dev-extra environment. This is targeted upstream
reproduction rather than a full-extras hosted-CI reproduction. Both inverses
executed and verified that their scoped executable/tool environment was absent.

The unnamed fresh native request reached Codex's built-in skill-creator
validator. It did not reach either candidate. The supplied launcher PATH did
not establish discovery in the child's login shell. agnix's project-skill add
route is host-policy blocked; SkillEvaluator does not ship a native routing
skill/plugin for its validator at this pin. These are unproved stages, not
permission to write a local substitute. Native command-child PSS samples are
retained; incremental per-session PSS remains unmeasured. ADOPT-NOW is withheld.

For openai/skills, REST reported `default_branch=main`, `archived=false`, and
zero commits since `2026-07-11T05:20:15Z`. Its latest default-branch commit is
still `49f948faa9258a0c61caceaf225e179651397431` at 2026-06-24T02:36:12Z.
The slot's proposed maintenance rule is **stale-not-maintenance-qualified**:
static quality cannot clear staleness or preserve an incumbency-based claim
of best standing. Existing installed skills retain their pins while the
whole-source comparison remains unresolved. The Anthropic reference result
is a control, not an adoption or a fresh live-task re-rule. The sealed landscape
winner ledger is left for the separately routed catalog disposition.

## Limits and publication gates

This is one small synthetic corpus, one fresh host/model session and one
independent judge. No confidence interval, published independent benchmark or
whole-skill task advantage is claimed. Recorded setup/API-path failures,
controller correction and the dated maintenance-test expectation update are
retained. The frozen corpus, thresholds and judge were not changed after
outcomes, and no outcome-driven rerun was performed.

Both designated reads must review the exact draft PR head. Hosted required CI,
the designated pre-cue tool, the CC's cue, and owner configuration decisions
remain gates. This trial PR authorizes none of those steps or any host apply.
The lane parks after its publication CHECKPOINT; the CC and 5f own landing.
