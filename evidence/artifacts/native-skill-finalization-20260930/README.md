# Native selected-skill evaluation, 2026-09-30

All 29 fresh native runs returned outer exit 0. In the original frozen set, 23 of 25 runs passed all outcome checks; four separately preregistered follow-ups passed. Outcomes and instruction loading remain separate evidence.

This is a local integration evaluation of two selected global skills. The prompt design follows [OpenAI's skill evaluation recipe](https://developers.openai.com/blog/eval-skills) and the [pinned Anthropic skill-creator workflow](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/SKILL.md). It is not an unchanged upstream test suite or qualification of every installed skill.

| Condition | Observed result |
| --- | --- |
| Ten focused writing cases, both clients; four search cases; one Claude baseline | 25 original runs, 23 outcome passes |
| Original Codex implicit writing proposals w02/w04 | Correct task outputs; selected instruction loads missed |
| Original Claude implicit writing positives w02–w05 | Four successful native Skill invocations with complete matching bodies |
| Original Codex implicit writing w03/w05 and search s01 | Complete selected SKILL.md reads with matching hashes |
| Twelve original adjacent negatives | No selected skill loads observed |
| Three original explicit CLI expansions | Outcomes passed; full instruction load not observable |
| Four follow-ups | Outcomes passed; explicit Claude search invocation and both actual Codex file edits loaded complete instructions; native structured JSON passed |

The two original outcome failures are retained. Claude w05 returned 152 words including commentary; its replacement section contained 39 words and passed the content checks. The frozen grader counted the complete answer, although the task limited the replacement section. Claude w10 returned correct field values inside a code fence and failed strict JSON parsing. The native `--json-schema` follow-up used the unchanged prompt and produced valid `result.structured_output`; it does not erase the original failure.

The actual-edit follow-ups used disposable AGENTS.md and CLAUDE.md fixtures with native Codex `workspace-write`. Both loaded the complete writing skill and produced correct file changes, independently inspected with native diff (exit 1 means changed). The owned workspaces were removed and the retained after-file hashes checked. These are separate editing conditions, not reclassification of the original read-only misses.

Codex 0.159.2 requested `gpt-6.1-sol / ultra`; its resolved model identifier was not exposed. Claude 2.1.285 requested `opus / max` and reported `claude-opus-5-5`. Capability checks used installed help, the [Codex release](https://github.com/openai/codex/releases/tag/rust-v0.159.2), and the [pinned Claude changelog](https://github.com/anthropics/claude-code/blob/ec44ca97dc86c33d934c8d55b24959aabf076871/CHANGELOG.md). Private supported diagnostics improved load visibility; instrumentation and scoped permission changes remain recorded.

The frozen sources were [writing-for-agents at c55ee460](https://github.com/mattpocock/skills/blob/c55ee46073ed923f86ce59a5eb3b6d895095d1b7/skills/productivity/writing-for-agents/SKILL.md) and [search-first at c70874fa](https://github.com/affaan-m/ECC/blob/c70874fae9eb0e5ad0365beb7e2955899fd1d30f/skills/search-first/SKILL.md). The writing trigger covers skills and AGENTS.md/CLAUDE.md instructions; ordinary human prose mentioning those names was negative. Claude search-first stayed name-only and was tested explicitly. Selected source bytes and named instruction/settings hashes remained stable across all runs.

The matched Claude baseline used the real native `--disable-slash-commands`: startup skills were empty and the Skill tool absent. Prompt hash, model, effort, and remaining native controls matched. Candidate and baseline both passed, so no quality improvement is established. This disables all skills rather than one selected skill; project instructions and hooks remain active.

[results.json](results.json) retains the original returned final outputs, checks, load hashes, native controls, input snapshots, independent diffs, raw-capture hashes, and inner failures. [usage-summary.json](usage-summary.json) counts exactly one cumulative native result for each of 14 Codex and 15 Claude runs. Main, cache, reasoning, and advisor scopes are kept separate; native costs are list estimates. Coordinator and evaluator orchestration usage is excluded. No efficiency gain is claimed.

[preregistered-cases.json](preregistered-cases.json) and [preregistration.md](preregistration.md) froze the original plan before calls. [followup-preregistration.json](followup-preregistration.json) and [edit-followup-preregistration.json](edit-followup-preregistration.json) froze each follow-up before calls. [operations.json](operations.json) records source checks, corrections, original failures, cleanup, and limits.

There is one repetition per condition. Complete effective system prompts and import paths were not captured; native Claude resolves project skill roots through the main checkout while the named worktree instruction files were frozen. Eight inner tool errors, six inner command failures, and one failed native collaboration diagnostic remain recorded. The three explicit-load observation limits remain unresolved. Raw JSONL, diagnostics, instruction bodies, provider signatures, host paths, and session identifiers stay private.
