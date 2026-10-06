# Skill identity reconciliation and native catalog budgets

Recorded 2026-10-06. This implements S4 of the round-two workflow decision: upstream installation stays native, while the repository records the installed identity and keeps metadata checks separate from model discovery.

## Decision

`tools/adoption/install_skills.py --record` reconciles the public Skills CLI lock and installed skill folders into an owned manifest. It resolves a public commit, verifies that its skill-directory tree equals the installed tree, and records the SKILL.md digest, byte count, description count and invocation declarations. A prior immutable pin remains a valid fallback when HEAD has already moved and that prior tree still matches. Missing source, ref, parser or tree evidence is reported as unverified; the earlier entry is preserved. The command never installs a skill or changes a host lock or client configuration. New and moved pins retain Unknown audits rather than inheriting an older pin's audit results, and changed pins keep their prior identity.

`--retire NAME` uses the unchanged native `skills remove NAME -g -y -a claude-code codex`, checks the actual folders and lock afterward, then moves the complete last pin into `excluded[]`. Native exit zero with a retained canonical folder or lock is a retained removal limit. The HF generated form has an explicit unsupported-native-remove result in this adapter; it is never deleted by a locally authored remover.

`scripts/skills_status.py --metadata-only --ledger PATH --json` is the S3 recorder's bounded read-only interface. It reads public skill metadata and the ledger without client settings, subprocesses, full supporting-file tree scans or model sessions. `--home` is preserved; metadata-only uses the caller's cwd for project skill roots unless `--project-dir` selects another root. Shared aliases collapse to one physical SKILL.md. An extra needs the latest non-removal `skill_state_change` v1 row for its scope/name with the current SKILL.md digest; a stale hash or removal row does not cover it. This is a metadata check, not an adoption decision.

The tree comparator ignores `__pycache__` and `*.pyc`; native skill use must not turn a pinned source tree into a different source identity merely by importing Python. Other supporting-file drift remains observable. Known missing installed-role preloads are reported. With `--workflow-manifest`, S7's `rows[].lanes.ultracode_stage` and inert rows' planned stages also feed that report. Missing inert preloads stay pending; plugin cache presence carries unknown activation rather than claiming a loaded plugin.

Tool-coupled guidance is advisory: `--tool-releases` supplies retained binary-release metadata for comparison. Without it, release alignment is unknown. A mismatch carries the supported upstream restore/update proposal; it adds no installer deny or automatic host restoration.

The first-pass review tightened three boundaries. Reconciliation compares the full source/URL/path/ref/tree/SKILL-digest identity: a same-ref fork cannot inherit official origin, license or passing audits, and the prior evidence stays with its original identity. Retirement also checks the native legacy Codex root and retains the manifest entry if that copy survives. Metadata reads use the accepted S3 descriptor contract: required nonzero O_NOFOLLOW/O_NONBLOCK, regular-file fstat before I/O, bounded reads and explicit nonredirected roots. Canonical Claude directory aliases into those roots remain supported; external final-file symlinks, redirected roots and FIFOs stay unknown and are never hashed. Unknown digests cannot cover an extra through a missing ledger row. This assumes trusted parent directories/cooperating writers; no regular-file latency or power-loss guarantee is claimed. Synthetic controls contain harmless external files, never credential files.

Ledger coverage also binds S3's `state_key`: SHA256 over the compact, sorted JSON array containing the verified canonical SKILL.md path. Scope/name alone cannot distinguish two native client profiles. The latest row for that exact physical key must carry the current SKILL.md digest; another profile's add, change or removal does not overwrite its coverage. Canonical shared/Claude aliases have the same physical key. Legacy rows lacking supported canonical identity remain unbound/unknown; an absent key is never a wildcard removal.

## Live budget evidence

Static manifest description totals remain metadata. The historical 10,500-character trial ceiling is retired as a gate. Missing retained native catalog data is unknown, never proof that a catalog fits.

`--claude-listing PATH` accepts retained native listing text (`listing` or `content`), `contextWindow`, `skillListingBudgetFraction`, `bytesPerToken` and `truncatedSkills`. The check charges JavaScript UTF-16 string units against `floor(window × client bytesPerToken × fraction)` and fails on the client's truncation signal. A 200K window at 0.05 and three bytes per token has a 30,000-character budget; substituting four would incorrectly grant 40,000. The 1M/200K scenario rows reuse that same retained listing; they are arithmetic scenarios, not new child sessions.

`--codex-catalog PATH` accepts retained rendered catalog text with its observed truncation/warning metadata and current `max_context_tokens`. Each native metadata line plus its newline costs `ceil(UTF-8 bytes / 4)`; the configured budget is capped at 10,000. Native file, executor-package, cloud-package and custom-resource locators all count. An unparsed native entry is unknown rather than silently omitted. Known description truncation or the native budget-removal warning remains a failure even if the catalog body is unavailable or cannot be parsed.

Native app-server `SkillsListResponse` is also accepted, as a labelled unaliased upper bound over enabled entries. Its schema omits implicit-invocation policy and renderer warnings. Over-budget upper bounds or potentially capped descriptions therefore remain unknown rather than alleging native truncation. Neither input path starts a model, app-server or fresh CLI session automatically. A retained metadata input does not itself prove freshness or model-side invocation.

## HF registration and distinct provenance

The only new skill entry in this change is the already installed `hf-cli`. The ecfa1127 baseline has 25 entries; this change has 26. The other entries keep their source and selection fields.

The vendor's native 2.1.1 generator writes 33,972 bytes with SHA256 `5fa67d3f5b5e071d026c13a029544220f077d9651ed96f5e4ed546981e2c19c5`. Native `hf version --format json` returned 2.1.1, and `hf skills preview` returned the same generated bytes plus its `print()` newline. That newline is output framing, not an edit to the installed skill.

The official mirror at `huggingface/skills@ca0325bb20b2d0a1b2efa893670c4c72f79e707b:skills/hf-cli` instead has 33,973 bytes, SHA256 `91dddd0303b2a3c5b6a38aa240d29cb2c93b118c98a6aafe46461df8f7a163bb` and Git tree `6f293e30d665bc0447a46af7831e386f3ab84bdb`. Its bytes equal the generated file plus one LF. These mirror fields are retained separately and are never claimed as the installed file's Git identity.

`source_type: native_generated` permits `tree_sha: null` only for the fully declared HF generator form. The generator is pinned at `huggingface/huggingface_hub@bd4a76030582d118e28dc9ad6c7a5911ea76176b`, v2.1.1, and installation/update dispatch uses that vendor's supported `hf skills` commands. This form needs no fabricated Skills CLI lock. Project and runtime-worker installation remain explicitly unsupported by this adapter. All external audit verdicts remain Unknown.

Correction verified during this unit: `.hf-skill-manifest.json` is an intentionally empty managed presence marker, not malformed JSON. The upstream installer writes SKILL.md and touches that marker. No marker or installed skill was repaired or normalized.

## Sources and comparison

- [Vercel Skills CLI v1.7.0, source identity and native removal](https://github.com/vercel-labs/skills/tree/7407f3893ad4dceab546ac002c3ef806e4000c73): `src/skill-lock.ts:168-171`, `src/local-lock.ts`, `src/remove.ts:209,293-340`. Repository integration starts from native-agent-stack@ecfa1127:tools/adoption/install_skills.py.
- [HF generator and native commands](https://github.com/huggingface/huggingface_hub/blob/bd4a76030582d118e28dc9ad6c7a5911ea76176b/src/huggingface_hub/cli/skills.py): lines 308, 323-327, 363-366 and 442-470; [native generated-file/marker implementation](https://github.com/huggingface/huggingface_hub/blob/bd4a76030582d118e28dc9ad6c7a5911ea76176b/src/huggingface_hub/cli/_skills.py#L65), lines 65-94; [release v2.1.1](https://github.com/huggingface/huggingface_hub/releases/tag/v2.1.1).
- [Codex native renderer](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/ext/skills/src/render.rs): lines 19-29, 126-160 and native metadata-line rendering; [native SkillsListResponse schema](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/app-server-protocol/schema/json/v2/SkillsListResponse.json).
- [Claude settings reference](https://code.claude.com/docs/en/settings-reference), `skillListingBudgetFraction` and `skillListingMaxDescChars`; installed Claude Code 2.1.291's listing builder reports bytesPerToken and truncatedSkills. [Native role preloads](https://code.claude.com/docs/en/sub-agents#preload-skills-into-subagents), integrated through native-agent-stack@920526ba:tools/adoption/workflow_variants.py.
- Codex implicit-policy metadata uses the existing reviewed native reader, native-agent-stack@ecfa1127:tools/sota-convergence/landscape-sweep/source_reviews.py:448-464; it distinguishes a plain false from YAML's broader string/boolean coercions. This records declarations, not a new model invocation.

Keeping only the upstream CLI's lock cannot reconcile an installed generator or a lock without a ref. Replacing native installers or re-authoring a vendor skill would duplicate upstream. Treating manifest sums as client acceptance misses the live catalogs and native truncation signals. These alternatives are therefore not the chosen integration.

Overturn this glue when an upstream native interface ships equivalent source reconciliation, removal/read-back or complete catalog-budget signals. Reuse that interface and remove the redundant adapter. Local fixture and integration tests remain separate from unchanged upstream acceptance and fresh model discovery.
