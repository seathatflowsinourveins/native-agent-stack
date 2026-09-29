# Decision: the #381 frozen-check grader is standard-library Python with a unittest suite and blind second-family judges (2026-09-29)

**Decided by:** the U9 build of Gate A (#381), on the Gate A owner's design of 2026-09-29 (units U9 stages 1 to 3, branch
`claude/pra-u9-frozen-checks-2d-20260929`). Checked against promptfoo 0.123.1 (npm, last modified 2026-09-18), inspect-ai 0.3.272
(PyPI), the TOON spec 4.1.1 and Claude Code 2.1.285, all read on 2026-09-29. The promptfoo installed-distribution findings in the
table below come from the design's stage 0 review of the same day and were not re-run in stage 3.

**Scope:** `tools/token-e2e/{frozen_checks,evidence,judge,grade}.py`, `node_bridge.mjs`, the two schemas, the judge template and Workflow,
`calibration/`, `tests/test_token_e2e_grader.py` and the README section. It changes no preregistration byte, no agent definition and no
setting. The grader is a local integration check, not upstream acceptance; the judge calls are separate model runs and did not run
in this build (see Limits).

## Decision

Grade the E2E with deterministic oracles written against the sealed preregistration and pinned Git content (classes A, B and C), and
settle each semantic clause (class D) with a blind judge from the other model family, kept apart from the answer's author by packet
scrubbing, isolation and verbatim-quote checks. Upstream parts run unchanged: CPython `ast`, `tokenize`, `json`, `hashlib` and
`unicodedata`; `git`; the TOON CLI 4.1.1 strict decode; `scripts/native_token_ci.py` `markdown_elements`; the packaged Codex lane
(`codex_lane.build_command`, `ISOLATION_ARGS`, `isolated_codex_home`, `child_env`) and `transcript_audit`; and the saved-Workflow
pattern of `adjudication-lane.js` for the `blind-lane-reviewer` role. No dependency is added.

## Framework comparison

| Criterion | promptfoo 0.123.1 (incl. `llm-rubric`, `g-eval`) | Inspect (`model_graded_fact`, `model_graded_qa`) | stdlib + unittest |
| --- | --- | --- | --- |
| No model call for classes A, B, C | yes (echo provider; `--assertions --model-outputs`) | yes (mockllm) | yes |
| Byte-identical results | no: the sanitizer, `randomUUID` ids, `latencyMs` and a timestamp (installed dist) | no: timestamped log names; re-scoring works on Inspect logs only | yes |
| Keys survive in results | no: the sanitizer redacts hex values of 64 or more characters and token or session keys; keeping keys in a `file://` Python assertion avoids vars, but stored results still redact matching values | not verified | yes |
| Blind cross-family judge with isolation, zero-tool audit, verbatim quotes and calibration | `llm-rubric` asks the model for `{"reason", "score"}` and `g-eval` returns a normalized score against a threshold; neither verifies quotes or audits isolation | grading uses a template and a grader model; no blind isolation of a Codex judge | built from `codex_lane` and `transcript_audit` |
| Mutation controls | outside the harness | custom | natural (the `test_token_e2e_receipt_checks` precedent) |

Rejected scorers, by name: promptfoo `llm-rubric` and `g-eval` ([llm-rubric](https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/llm-rubric/),
[g-eval](https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/g-eval/)) and Inspect `model_graded_fact` and
`model_graded_qa` ([scorers](https://inspect.aisi.org.uk/scorers.html): "have another model assess whether the output contains the fact
set out in target"). They grade with one model that sees the answer and its context; the E2E needs a judge that sees only a scrubbed
packet, from the other family than the answer's author, whose quotes are checked byte for byte, whose calls are audited for tool items
and hook rows, and whose route is calibrated with planted answers first. Inspect's scoring workflow re-scores Inspect logs
("defer scoring, re-score logs with `inspect score`"), not outputs supplied from another harness, and the grader must re-grade
retained evidence offline (`regrade`) with byte-identical results.

## Choices inside the grader

- **Decided readings.** Each ambiguity of the preregistration's register takes the harder reading, named in the spec's `grading` block;
  production code has no default, and the other readings are computed and published under `alternatives`. R2-06 is built: the decided
  reading grades the answer as Markdown (the ten `markdown_elements` checks), and the alternative reads the content of the same ten
  elements (parsed from the exec-revision fixture) as whole words wherever they sit in the answer.
- **Judge effort and models.** Claude answers go to `gpt-6-astra` at literal `max` effort (never the lane's default, which is `high` at
  this base); Codex answers go to Opus at `max` through the Workflow with agent type `blind-lane-reviewer`, whose user-scope copy must
  be byte-identical to the repository's (`E_JUDGE_ROLE`).
- **What a judgment must carry.** Verbatim quotes, no leak, a refuter that does not overturn a pass, an isolation audit and calibration
  controls of the template and route that came out right. A failure is `unknown` with its reason, never a guessed verdict. Retries are
  for infrastructure failures only (one retry); a usage limit pauses (exit 75) and resumes.
- **M9 use.** U4's join lanes are the eight required tool lanes and carry no repomix or markitdown state, so the optional block reads
  the lane from the attempt's own calls and the call ledger's state. It is reported beside correctness and never gates.
- **Calibration alignment (2026-09-29).** The class D controls are rendered through the same `source_sections` a real packet uses, so a
  control shows the judge the section labels a real packet shows; T13's packet also carries the recorded conversion facts (call state,
  converted bytes, scope terms missing) without the tool name.

## Overturn conditions

- promptfoo becomes eligible with a deterministic export, a switch that stops redaction of var values, per-config disabling of `file://`
  loading and of templating, and byte agreement with this grader on the planted controls (`grade.py controls`).
- Inspect becomes eligible with re-scoring of externally supplied outputs and deterministic logs.
- Any upstream harness that ships frozen-check oracles qualifies, compared on the same planted controls.
- A route's judge is replaced when its calibration controls fail on a real run (`judge_calibration`) or its transcripts show a tool item
  or hook row (`judge_audit`, `judge_hook_rows`) that the audit cannot exclude.

## Evidence classes and limits

- Measured here: the unittest module (synthetic hosts, a scripted `codex`, recorded Workflow results, planted controls and mutants of
  the tool) and the T0 differential against the retained checks of two earlier runs. These are our integration checks.
- Not run: the real `gpt-6-astra` and Opus judge routes. The rehearsal commands (`grade.py judge rehearse --route codex|claude`) are the
  acceptance step and need real judge model calls, which the build's brief did not allow (read-only document fetches only). A real
  `spec` and `keys` run waits for Amendment 4.
- Recorded residual: a judged answer is screened for identifiers and the canary, not for hit text it quotes from a retrieval.

## Sources

- promptfoo 0.123.1 (`npm view promptfoo`, 2026-09-29) and its [llm-rubric](https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/llm-rubric/)
  and [g-eval](https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/g-eval/) documents.
- inspect-ai 0.3.272 ([PyPI](https://pypi.org/project/inspect-ai/)) and its [scorers](https://inspect.aisi.org.uk/scorers.html) document.
- [TOON specification](https://github.com/toon-format/spec/blob/main/SPEC.md) 4.1.1, strict decode.
- `tools/sota-convergence/codex_lane.py`, `transcript_audit.py` and `adjudication-lane.js` in this repository (used unchanged).
- The sealed preregistration and README of `evidence/artifacts/token-adoption-e2e-20260926` (R5 register, M9, the gates).
