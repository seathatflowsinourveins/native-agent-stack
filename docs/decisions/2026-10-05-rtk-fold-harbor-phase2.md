# RTK fold Harbor study: retain the default within the measured grep scope

Date: 2026-10-05. Lane: foundation. Status: historical study published; default retained within scope.

North-star action: keep grep-discovered file paths reliable for coding agents building complex systems and the research stack. The question was whether RTK 0.51.0's default file-list folding increases wrong-path actions, and whether its supported `exclude_commands` remedy should replace the default.

The preregistered overturn rule did not fire: `remedy_triggered=false`. Across 72 measured Codex trials, all three arms had zero adjudicated wrong-path actions and reward 1.0 in every trial. Retain arm A for the studied grep scope. The eight-task null result supplies no equivalence or universal safety claim. This publication ran no new trials or model calls and changes no installed configuration.

## Sources, protocol and phase 1

The study reused upstream Harbor 0.23.0 at `harbor-framework/harbor@1e5c5c6db929a10a140d05e606882c671ae20729`, its native tasks, installed Codex agent, verifier lifecycle, ATIF trajectories and `harbor run -c` command. The task fixtures, installation/configuration bridge and offline measurement/analysis adapter are local integration. The tasks are synthetic; they are not an unchanged upstream test suite. The pinned [Harbor task format](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/docs/content/docs/tasks/index.mdx) and [Codex agent](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/installed/codex.py) define the reused harness.

The execution pins were Codex 0.160.0, the `cx/gpt-6.1-sol-max` route at max effort, and `rtk-ai/rtk@e001f773f80b22b7dc4c7a79521b30e35aaef026` (v0.51.0). The RTK musl release archive SHA256 was `5028d3b19a8f0990d30fec9fbb07e32782bc5698e618fb1861aad8a9ccba4eb5`. Pins came from [stack revision 38ac9aca](https://github.com/seathatflowsinourveins/native-agent-stack/blob/38ac9aca114ad9ef4a15d8620d947eb5c2f518c3/adoption/pins-linux-x86_64.json). The [RTK installation source](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/README.md#installation), [Codex hook integration](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/hooks/codex/README.md), and [Codex trust option](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/utils/cli/src/shared_options.rs#L63) are the upstream authority for the recorded configuration. Source hashes and original-file locators are in [source-hashes.json](../../evidence/artifacts/rtk-fold-harbor-20261004/source-hashes.json).

The [effective preregistration](../../evidence/artifacts/rtk-fold-harbor-20261004/PREREGISTRATION.md), [Amendment 1](../../evidence/artifacts/rtk-fold-harbor-20261004/AMENDMENT-2026-10-04.md), and [historical phase-1 decision draft](../../evidence/artifacts/rtk-fold-harbor-20261004/phase1-decision-draft.md) retain the preparation and its failures. Amendment 1 repaired offline decoding of nested Codex executor arguments and Harbor text representations, kept the outer tool-call counting unit and original call IDs, and separated automatic candidates from adjudicated labels. It also defined `hook_fired` as grep rewriting, with invocation tracked separately. Preparation exposed installer/config-type, container environment, redaction and login-PATH failures; those remain historical integration failures, outside the measured sample.

Amendment 2 prospectively installed the same checksummed RTK binary at `/usr/local/bin/rtk` for A/B through [Harbor's native root helper](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/installed/base.py#L973), and dropped D after incomplete Claude-client transport attempts. It retained C, the seeded A/B/C schedule, model/task pins and statistical rules. New A/B smokes plus retained C passed the readiness gate. The original A PATH exit 127 and the later smoke wrapper exit 97 on an opaque-reasoning substring remain disclosed; the reporting correction reused completed native results without another model run. Historical Harbor oracle calibration passed all 8 tasks, while nop failed all 8, providing a discriminating verifier control on these fixtures. These are supported native harness operations with locally authored oracles, not upstream test-suite acceptance.

**Freeze correction.** The requested `FREEZE-v4.*` is an earlier reporting freeze, not the final pre-measurement freeze. Its manifest SHA256 is `6522f2289afb28360aae14b5d51f5b37e29cd9c6ee63c11e01d545e6ea5961f8`, covering 596 inputs; all 596 archived v4 originals were rehashed. The effective `FREEZE.json` is version 5, dated 2026-10-05T01:08:21.666831+00:00, with manifest SHA256 `819f87338f079bded755071bba299244fa2d63dda2884d258e9eb8a64c4bed3f` and 604 inputs. All 604 current input hashes match. `README.md`, `PHASE1.json`, `run_phase2.sh` and the 604 successful entries in `logs/phase2-freeze-check.txt` verify this correction. Both [v4 metadata](../../evidence/artifacts/rtk-fold-harbor-20261004/FREEZE-v4.json) and [final metadata](../../evidence/artifacts/rtk-fold-harbor-20261004/FREEZE.json) are published with sanitized manifests. The final reporting/operational refinement preceded every measured trial and changed no task, installer, hook, client, verifier or seeded schedule. Both amended A/B smokes preceded that final reporting freeze. The effective preregistration's original SHA256 is `260238de8e1c2318766996eeb5355322dafc5939ff73049020ae16e87f2d6f65`.

## Arms and preregistered measures

The sample was 8 tasks × 3 repetitions × 3 arms = 72 trials, 24 per arm. Seed 20261004 fixed randomized task/repetition blocks and A/B/C order; concurrency was one. Smoke, oracle/nop, install-only and interrupted D attempts were excluded. D supplied no measured estimate. Each task contained 39 initial files and 12 marker-matching targets, with shared-prefix nested files and existing decoys. The verifier checked the complete expected byte map and rejected unrelated changes, extra entries, symlinks and special files.

| Arm | Recorded configuration |
| --- | --- |
| A | RTK 0.51.0 default folding, native `rtk init -g --codex`, default awareness and the pinned native hook trust setting |
| B | Same installation and initialization, with upstream-native `[hooks] exclude_commands = ["grep -l", "grep -rl", "grep -lr", "grep -r -l"]` |
| C | Fresh container without RTK binary, hook or awareness |

These exclusions cover the five registered spellings, including `grep -l -r`; literal matching uses an escaped prefix followed by whitespace or end. They do not establish coverage for arbitrary flags, bundles, `-R`, long options or explicit `rtk grep`. The matching rule is verified in [RTK's pinned matcher](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/discover/registry.rs#L1553).

The primary metric was wrong-path actions per trial, counted once per outer tool call when any access/edit uses a nonexistent required path or a trajectory-supported mistaken folded-prefix reconstruction. Repeated wrong calls count again. Existing decoys require evidence of mistaken reconstruction; ordinary valid exploration, patterns, URLs, option values and intentional existence checks do not automatically count. Passing verification alone cannot label path errors. Secondary outcomes were verifier reward, identical-command retries after adjudicated path failure, and input/output/cache token categories. Hook invocation, rewriting and observed folding were separate exposure measures; missing coverage or labels blocked scoring.

The confirmatory A-C analysis used eight paired task means over three repetitions, exact one-sided sign flips through SciPy `permutation_test(permutation_type="samples", n_resamples=inf)`: wrong-path A > C and reward A < C. The two p-values formed one Holm family at alpha 0.05 through statsmodels. Task-cluster percentile bootstrap intervals used 10,000 resamples and seed 20261004. A-B and B-C were exploratory paired comparisons with unadjusted p-values. Assignment, rather than successful folding alone, determined analysis membership. The retained analysis reports SciPy 1.18.1 and statsmodels 0.15.0; neither analysis nor model execution was rerun for publication.

## Added adjudication protocol

The [frozen protocol](../../evidence/artifacts/rtk-fold-harbor-20261004/PROTOCOL.frozen.md) added a concrete multi-reader plan and independent audit to the preregistered single-reviewer procedure, after execution and before any labels. Its original SHA256 is `a45f6b868ae65e1289de00021e6f9dd8a631ed1de50f5a08c982da07aa24f77b`, recorded in `batches.json` at 2026-10-05T04:37:29Z. This addition changed no metric, confirmatory family, stopping rule or overturn criterion.

Six Claude Opus 5.5 readers at max effort each covered one batch of 12 trials. Their packets omitted arms, verifier rewards and arm manifests, retained original arguments, and exposed automatic candidates only as hints. Renderings marked middle truncation and retained error/missing-path lines; batch JSON was available for lookup. The protocol acknowledges that visible output and awareness reads can reveal exposure, so blinding was imperfect.

A blind GPT-6.1 Sol audit at max independently labelled every primary positive plus a seeded 20% negative sample: `ceil(0.2 × 264) = 53` negatives, seed 20261004. The audit did not see primary labels. A disagreement would require a fresh blind third Opus reader and majority resolution; negative agreement below 85% would extend the audit to remaining negatives. Unknowns would block scoring. The published counts and joins, including independent reproduction of the seeded sample, are in [adjudication-summary.json](../../evidence/artifacts/rtk-fold-harbor-20261004/adjudication-summary.json). Reader identities follow the retained protocol and label metadata, not new provider attestation.

## Results and evidence classes

| Arm | Trials | Adjudicated wrong-path actions | Reward in every trial | Fold observed | hook_fired | grep_hook_invoked | Identical retries after path failure |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 24 | 0 | 1.0 | 23/24 | 24/24 | 24/24 | 0 |
| B | 24 | 0 | 1.0 | 0/24 | 8/24 | 24/24 | 0 |
| C | 24 | 0 | 1.0 | 0/24 | 0/24 | 0/24 | 0 |


The exposure and token fields come from the recorded native harness results and offline extraction. `hook_fired` records at least one grep rewrite recognized in the audit, while `grep_hook_invoked` records invocation. B's 8/24 rewrite flag therefore differs from its 24/24 invocation flag. B and C had no observed fold; A had folds in 23/24. All 72 retained trials have trajectories, reconciled native/ATIF call IDs and no recorded exception. Original per-trial results independently match rewards and token fields. The phase-2 log records 72 Harbor exits 0, 72 token-scan exits 0 and driver exit 0; measured execution ran from 2026-10-05T01:13:29.537098Z through 2026-10-05T04:31:56.164729Z.

Primary labels covered 264/264 calls, with 0 positives and 0 unknowns. All 80 automatic candidates were rejected (A 31, B 29, C 20). The audit agreed on 53/53 rows, with 0 disagreements and no unknowns. No primary positives existed, so the recorded positive agreement `0/0` is not sensitivity evidence. Original actions, primary labels, filled CSV and audit labels were joined by call ID; all coverage and label joins match. The [public CSV](../../evidence/artifacts/rtk-fold-harbor-20261004/phase2-measures.adjudications.csv) retains call IDs, labels and short review-status notes, omitting original arguments, paths, rationales and observations.

| Confirmatory A-C metric | A mean | C mean | Difference | One-sided p | Holm p | Task bootstrap 95% interval |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Wrong-path actions | 0.0 | 0.0 | 0.0 | 1.0 | 1.0 | [0.0, 0.0] |
| Reward | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 | [0.0, 0.0] |

A-B and B-C also have zero differences and unadjusted p=1.0 for both metrics; these are exploratory. Degenerate bootstrap intervals describe the identical observed task differences, not uncertainty about rare errors on new tasks. The [analysis projection](../../evidence/artifacts/rtk-fold-harbor-20261004/phase2-analysis.json) preserves the original comparison results and version metadata.

Token means and medians below are **secondary, exploratory only**, with means rounded to two decimals. Exact derived values are in [per-arm-summary.csv](../../evidence/artifacts/rtk-fold-harbor-20261004/per-arm-summary.csv).

| Arm | Input mean | Input median | Output mean | Output median | Cache mean | Cache median |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 54,688.17 | 58,168.50 | 3,469.58 | 3,484.00 | 44,218.67 | 45,632.00 |
| B | 57,812.83 | 58,868.00 | 3,427.29 | 3,279.00 | 47,402.67 | 47,680.00 |
| C | 54,346.62 | 46,718.50 | 3,298.17 | 2,959.50 | 42,874.67 | 38,208.00 |


These are the original Harbor `n_input_tokens`, `n_output_tokens` and `n_cache_tokens` fields. Codex cache tokens are a subset of input, so the categories are not added together. Cache conditions and enclosing preparation/reviewer usage are not controlled or completely metered. This record makes no token, cost or time saving claim.

Under [acceptance-evidence-policy.md](../acceptance-evidence-policy.md), the native Harbor/Codex execution is an upstream native operation on local synthetic fixtures; the bridge, extraction, adjudication and analysis are local integration evidence. Original-result/log inspection and label/sample joins are independent observations. The new publication checks establish structural consistency and privacy-pattern hygiene only. The initial validator and both freeze-manifest scans exited 1 on retained UUID session identifiers in locators; those locators were redacted with the existing validator pattern while preserving input hashes. The failed checks are retained separately from the corrected acceptance, as documented in the artifact README. No unchanged upstream test suite or new live acceptance is claimed.

The [receipt](../../evidence/receipts/rtk-fold-harbor-20261004.json) uses `native_model_e2e`, allowed by `scripts/validate.py` and defined in [evidence.md](../evidence.md#evidence-levels): the retained native client made live provider calls, used tools and produced verified task results. This preserves that execution class while identifying its historical date and synthetic workload. It is neither a fresh model run nor a host-install qualification. `historical_inventory` would describe imported inventory rather than these retained executed task results; `native_cli_e2e` would omit the model-driven part.

## Decision, alternatives and overturn conditions

Retain A within the registered plain newline-separated GNU grep file-list scope. A had no adjudicated wrong-path action, and its reward was not significantly lower than C, so neither preregistered overturn condition held. B remains the supported upstream-native remedy if that rule fires on evidence within an appropriately frozen scope.

The alternatives were adopting B now, disabling RTK through C, or changing/forking the fold format. The measured outcomes supply no trigger to promote B. C removes awareness and other RTK filtering as well as folding, so A-C cannot isolate every RTK effect. A custom fork or output-expansion shim was unnecessary while the supported exclusions existed; a self-written runner was excluded by the study contract. No alternative is promoted on exploratory token values.

Overturn this decision if A has any adjudicated wrong-path action, even if its paired count test is not significant, or if A's pass rate is significantly lower than C under the preregistered Holm rule. Verify B's relevant wiring and lack of folding before recommending it; demonstrated bypass or remedy failure leaves remedy coverage unresolved. A new RTK/client pin, changed fold format, new command spelling or wider task/model/path population reopens the bounded comparison rather than inheriting this result. A maintained upstream decoder that faithfully covers the retained executor representations could replace the local adapter after original-source replay.

## Limitations and completeness critique

- Only 8 related synthetic task clusters were sampled; 3 repetitions do not make 72 independent tasks. Rare errors and broader repository behavior remain unmeasured.
- Only the pinned Codex 0.160.0 client and one GPT-6.1 Sol route were measured. Dropped D leaves no Claude-client or second task-model behavioral estimate.
- A/B used `/usr/local/bin/rtk` in containers so default login shells could resolve it. Earlier home-directory installation failed in a login shell; neither host PATH behavior nor another installation location is qualified by these results.
- Scope is the five registered GNU grep spellings, plain ASCII newline path lists and one shared topology. Unicode/whitespace names, uneven depths, `../` roots, changed working directories, NUL/count/JSON output, built-in search tools and arbitrary explicit RTK/option orders were not qualified.
- Blinding was imperfect, as preregistered. Six primary model readers and an added audit may share systematic errors. Rendered truncation and lookup access do not prove every untruncated observation was inspected; this publication performed no new semantic re-review.
- B's `hook_fired` was only 8/24 even though invocation was 24/24 and folds were 0/24. These are distinct observables, and the sparse rewrite rate limits a claim about uniform handler-rewrite exposure or broader exclusion coverage.
- The 53-row audit covers a seeded negative sample and no positive examples. Agreement does not establish detection sensitivity or correctness of unaudited negatives.
- All rewards were 1.0, both confirmatory Holm p-values were 1.0, and empirical difference intervals collapsed to zero. This cannot establish equivalence or universal safety.
- Token figures are exploratory; provider billing, enclosing-workflow usage and cache conditions do not support a saving claim. Public hashes and validation are not provider attestation, ciphertext authentication or proof of absence of every secret format.

The completeness critique identifies the missing task/model/client classes, wider path/output modalities, real command orders, remedy bypasses and maintained executor-decoder candidates as the next scoped landscape sweep. Future authorized work should preregister those additions, retain discriminating oracle/nop controls, reconcile original call IDs, and separate invocation, rewrite, fold exposure and adjudicated actions. No such sweep or new trial was launched by this publication. The [artifact README](../../evidence/artifacts/rtk-fold-harbor-20261004/README.md) explains the sanitizations, original/public hash distinction and recoverable source locators.
