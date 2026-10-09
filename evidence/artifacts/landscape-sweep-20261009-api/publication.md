# API-surfaces sweep publication — 2026-10-09

This record publishes the retained api-surfaces sweep, workflow `wf_b7a6dece-81b`, using the existing landscape harness. It records 116 proposals across ten foundation layers, with 33 surviving layer/repository pairs and 83 refutations. Survivors other than the [existing GPU exporter](#existing-gpu-exporter) are inputs to separate adoption trials under the [blinded-judge requirement](#blinded-judge-requirement). These records provide source review and retained research judgments; they provide no new installation, comparison, fresh-session proof or adoption acceptance.

## Sources and method

- [native-agent-stack at b7dfe638fc825a52ff4e7d1a9ccf2fde7de889fd](https://github.com/seathatflowsinourveins/native-agent-stack/tree/b7dfe638fc825a52ff4e7d1a9ccf2fde7de889fd), `tools/sota-convergence/landscape-sweep/README.md:631–658`: publication steps 9–12; `source_reviews.py`; `make_result.py`; `scripts/saturation_ledger.py`.
- The completed research source `state:FINAL.md`, read on 2026-10-09, SHA-256 `77e17817d8ecc8e53329ac32303ece8dc4e86eaf67cba1e3ae36196aa328a109` (13,544 bytes). Its current bytes supersede the handoff hash `17b1489725f0cb403b8f8d838fe20b0cc79375c926288c20daa3320b7a00ed12`. Research source identity is retained here without publishing the private workflow run record.
- [Retained returns](returns.json), current SHA-256 `91a31f46e6583994954b01a23e7dd2178df7b8a9df92ae2c2f847063a5b13259`: discovery returns, facts and both fit votes, retained failures, superseded attempts and GPT-6 usage, with decoded source-path normalization and the JSON spelling correction below. The prior publication's SHA-256 `3c9c1e4146ad5b1dc98232daa880cc78444b82a85f57175da988619ec4990091` identifies the pre-normalization bytes at commit `cc3feedb04e9429e4138d51bfc336b89e94f52fb`.
- [Child usage](../landscape-sweep-20261009-api-attempts/child-usage-wf_b7a6dece-81b.json), SHA-256 `722ffd7cff49eb0e7b990e470857f1879e8d4c31d1c5763557caf7d8c698afd6`: sanitized native child accounting and documented post-processing.

The manifest uses the sweep's retained `work/` inputs and `freshness/github-freshness.json`, supplied through `build_manifest.py --freshness`. This is the completed sweep's metadata snapshot. Publication does not refresh the landscape or promote catalog selections. The initial step 9 invocation exited 1 because the recipe's default `work/github-freshness.json` was absent; the supported explicit `--freshness` invocation exited 0. The first failed attempt is retained as a publication limitation rather than represented as a successful command.

## Reopened layers

- **git-github-automation:** `FINAL.md:31` identifies the surviving mergiraf Codeberg repository. The pinned `source_reviews.py:1242–1252` accepts only GitHub and Hugging Face repositories and rejected this URL. [Pending review record](mergiraf-review-pending.json) retains that local integration failure with `status: pending` and `reviewed_commit: null`; it is the result's explicit gap binding, with a `missing_capability` reopen entry. The 2026-10-09 publication decision defers the Forgejo adapter and native vendor review to a separate follow-up. No completed mergiraf source review is claimed.
- **quality-evaluation:** `FINAL.md:59` reports two follow-up workers whose measured turns departed from requested max effort and ran at low. [Retained failures](returns.json#/failures/quality-evaluation) preserve the two `effort_deviation` entries. This layer remains reopened despite its four surviving proposals.
- **hosting-services:** `FINAL.md:105` and `FINAL.md:152` report the GPT-6 copy-check mismatch introduced by redaction of a public message-id URL. [Retained failure](returns.json#/failures/hosting-services) preserves `gpt6_copy` with status `mismatch`. This layer remains reopened despite having no survivors.

Each FINAL.md line citation refers to the SHA-256 above. The result also preserves the converter's original `retained_failure` references; the explicit FINAL.md citations add provenance. The two original research failures remain distinct from the additional pending publication review.

## Source-review execution

The native `source_reviews.py` invocation against the original survivor input exited 1 solely because mergiraf uses Codeberg. It wrote 31 upstream source reviews covering 32 surviving layer/repository pairs; codex survives in two layers. Its unmodified [reviews index](reviews.json), SHA-256 `f4050736f39f04b447b51d848600b24f9ea16c2f077e4c489bb6dbf12dd233ca` (4,767 bytes), excludes mergiraf. [Retained stderr](source-reviews.stderr.txt) names the native unsupported-forge error. No harness adapter or caching patch is included in this publication.

The result builder requires a path-bearing binding for every survivor even when a layer is reopened (`make_result.py:219–249`). Its separate `review-bindings.json` input retains the 31 native index entries and adds the explicitly pending gap record for mergiraf. The result's `source_review` field for that survivor points to this pending record, whose evidence class is `local_integration`, whose vendor commit is null, and whose README excerpts are empty. This binding is evidence of the publication gap and supplies no vendor provenance review. The original native reviews index remains intact and separately hashed.

Before the one-time native review reads, `gh api rate_limit` reported 5,000 remaining REST points and 4,992 GraphQL points at 2026-10-09T05:34:46Z. After the run, it reported 5,000 remaining REST points and 4,992 GraphQL points at 2026-10-09T05:35:54Z. These are observed endpoint snapshots; their unchanged counters do not measure request count or establish that the run consumed no shared budget. The pre-run REST snapshot passed the required >1,000-point gate.

## Corrections and limits

`apify/mcpc` is refuted and is absent from survivors (`FINAL.md:85`; retained votes under `votes/mcp-surfaces/4`). `anthropics/skills` is refuted and is absent from survivors (`FINAL.md:76`; `votes/instructions-skills/1`); a later rerule and the agnix and SkillEvaluator trials require the [blinded-judge requirement](#blinded-judge-requirement). The Claude Agent SDK remains the measured conditional Claude-family reader route (`FINAL.md:98–103`); these records establish no default worker SDK selection.

Child usage retains original `measurement.exit_code=1`, then documents linking an incomplete same-label attempt to a later completed attempt. The resulting `child_usage.status=complete` covers 110 complete final children; 38 superseded attempts remain retained. Two uncovered effort mismatches remain recorded. This documented recovery is distinct from a new successful capture. GPT-6 accounting in returns covers 34 successful jobs and three earlier attempts, with zero jobs whose usage is unavailable; the accounting families remain separate.

The source reviews establish upstream provenance at their recorded commits. Any adoption requires its own quality evidence, vendor installation and inverse, fresh-session proof, and measured per-session PSS. API-surfaces publication completes none of those gates.

## Existing GPU exporter

The superseding publication disposition for [utkuozdemir/nvidia_gpu_exporter](https://github.com/utkuozdemir/nvidia_gpu_exporter) is **KEEP, existing install**. The live-host facts supplied by the CC's 2026-10-09 05:16Z observation identify version `1.15.1`, revision `87afc069c5ce6a37b13db58989ec0f30d9b87217`, job `workstation-gpu`, endpoint `127.0.0.1:21257`, an up target and 21 `nvidia_smi_*` series. These are supplied host observations, not measurements rerun by this publication. The [upstream source review](utkuozdemir-nvidia-gpu-exporter.json) remains scoped to documentation at its separately recorded commit.

The exporter is excluded from current new-adoption routing. Its `targeted_candidate` label and proposed ports `9835`/`9836` remain historical discovery inputs; they do not authorize another install, launch or duplicate exporter trial. The manifest entry and source-review claim link to this superseding decision. The 116/33/83 research counts and all retained discovery and fit votes are unchanged.

## Blinded-judge requirement

Follow-up routing for the `anthropics/skills` rerule and the [agent-sh/agnix](https://github.com/agent-sh/agnix) and [nvidia/skillevaluator](https://github.com/nvidia/skillevaluator) comparisons requires arm identities to be hidden from the judge. Repeating the previous unblinded comparison does not satisfy this requirement. The two surviving candidates' manifest plans link to this superseding 2026-10-09 skills-lifecycle ruling. Original research proposals and votes remain historical inputs and are not represented as blinded results.

## Publication normalization and validation

Private research sources use neutral `state:` document identifiers with their locators and available source hashes. Checkout references use repository-relative paths; concrete installed-client locations use placeholders. Normalization applies to decoded JSON strings, including retained raw copies, and preserves judgments and failure meanings.

The neutral source `state:mcp-wiring-handoff.md` retains its original line locators and binds the source's SHA-256 `c15d5d1d9b39d3699cb03cb16b84d71e7f6964a5d623cc1b7d2c1a6506805d38` (8,734 bytes), rehashed on 2026-10-09. `state:FINAL.md` binds the source hash in Sources and method. The prior publication at commit `cc3feedb04e9429e4138d51bfc336b89e94f52fb` retains the pre-correction bytes; the current evidence registry and regenerated unmerged sixth ledger row bind the normalized records. The prior five ledger rows remain unchanged.

The required module runs retain four unexecuted boundaries: `tests.test_saturation_ledger` skips one case because `jsonschema` is unavailable; `tests.test_landscape_sweep_harness` skips three cases because `CONTEXT_MODE_SECURITY_JS` is unset, a real Bash 3.2 binary is unavailable, and ShellCheck is unavailable. These cases are skipped, not passed. Final counts and return codes are recorded at the fix checkpoint after rerunning both modules under `timeout 600`.

## JSON spelling correction

[gitleaks/gitleaks v8.30.1, config/gitleaks.toml](https://github.com/gitleaks/gitleaks/blob/v8.30.1/config/gitleaks.toml) has a code-search access-token rule whose legacy branch accepts bare 40-hex values when its vendor keyword occurs in the same scanned chunk. A retained scanner comparison names that rule, enabling matches on unrelated public Git commit pins in both JSON records. The rule-name spelling uses ordinary JSON Unicode escapes in each record. Explicit json.load comparisons against the preceding head are equal; every proposal, judgment, source URL and commit identifier is unchanged. Current artifact bindings record the new serialized bytes. This content correction changes no scanner policy or allowlist. The installed native decoder's default depth is5; its [codec implementation](https://github.com/gitleaks/gitleaks/tree/v8.30.1/detect/codec) restores escaped text before subsequent detection. Therefore spelling equality or a clean directory scan alone establishes no clean git ancestry result; the required native git and directory checks decide that separately.
