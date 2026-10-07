# Skills PR fold overlaps — 2026-10-07

Retained PR: #795. The frozen source heads and exact byte comparisons are in [comparison.json](comparison.json). The final retained push head is reported in the PR and lane completion record; this artifact records the source unions.

| Original | Frozen head | Non-hot paths | Identical in staged keeper | Missing |
| --- | --- | ---: | ---: | ---: |
| #719 | 876010fbadfcb2b6846f9aa97f0841e829a81ff4 | 203 | 193 | 0 |
| #792 | ae17e43dea30d747b1742ffbfcd847495b526a65 | 11 | 4 | 0 |
| #793 | 401d98b96fb887055124c3f248621116736c6298 | 7 | 7 | 0 |
| #794 | 7a3a6c7f5245a185dd2178e02b33747c0b723b4f | 22 | 20 | 0 |
| #817 | 2a017e52659e34e1c6ddb4bf9666846292dc6088 | 5 | 3 | 0 |

Counts exclude manifests/evidence.json and catalogs/saturation/ledger.json. Native git three-way application preserved every source path. Counts reflect the approved A26 amendment and current-carrier repairs. All 177 #719 artifact paths and its six dated records are byte-identical; other incoming historical observations and decisions are unchanged.

## Exact unions and source adaptations

- adoption/skills/manifest.json: retain both native-stack-research and hf-cli objects byte-for-byte semantically, preserve the existing client-budget prose and append the dated A26 amendment, regenerate derived totals. The union has 27 rows, 26 Codex-eligible entries, Claude description metadata 10,645 and Codex 10,326. A26 sets both repository policy mirrors to the exact sum 10,645; its dated amendment preserves the native 0.05 setting and all pinned descriptions. The separate 15,000 proposal remains unapproved.
- adoption/templates/claude.settings.template.json: retain #795's statusLine executable guards and original tail, add #719's native-stack-research on entry. This is repository text only.
- adoption/templates/codex.config.template.toml: retain #792's lifecycle record/retire configuration and #719's research entry, with corrected derived eligibility prose. Native visibility remains a separate gate.
- tools/adoption/install_skills.py, tests/test_install_skills.py and tests/test_skills_status.py: union central held/pruned inheritance with record/retire and native-generated lifecycle support. Retain assertions from both sources. A fixture home lacking native budget data stays unknown, not a fabricated 6,000-token observation. tests/test_skills_manifest.py retains the review-window fields, equates the trial policy mirror to the canonical ceiling, binds both measured sums and the approved ceiling, and checks catalog-eligible prose without claiming fresh visibility. The lifecycle recipe points to the new amendment.
- catalogs/landscape/skills-lifecycle.json: retain the new source rows and four pending tasks, #719's research mapping, and #817's held browser gap with an empty installed list. Map active hf-cli to model-hub and state the remaining worker/use qualifications. Each new task retains a contended-choice comparison condition.
- tools/sota-convergence/landscape-sweep/schemas/discover-skills.json and tests/test_landscape_sweep_skills.py: extend the current enum from 13 to 17 approved tasks, align the dated catalog and exact OpenAI source consumers. Frozen historical 13-layer outputs and observations are untouched.
- blueprints/runtime-workers/skills/manifest.json: preserve all 134 selected rows and add an explicit source-bound hf-cli exclusion, because its native-generated central recipe does not support the worker/project installer. This is not a hand-copied payload or a central retirement.
- tests/test_runtime_worker_skills.py: preserve payload-copy prohibitions; recognize only the native JSON manifest transaction inside record/retire branches. No general payload-write exception is introduced.
- docs/harness-defaults.md: retain all keeper correction rows and append the three distinct lifecycle rows.
- .github/osv-scanner-lockfiles.json and tests/test_osv_lockfile_coverage.py: retain both the PyYAML validation lock and routing fixture lock, with the separate assertions from #795 and #794; 60 locks and two dependency-free entries remain.
- SDK overlay: exact openai-codex and paired runtime pins move to 0.160.1 through the worker's supported UV lock generation; SDK_VERSION remains an exact-match guard. Current carriers are updated and the existing dated SDK decision receives an appended amendment. Earlier results and baseline read-back inputs are not rewritten.

Pending workflow routes remain inert until Tier B recording and the named native consumers exist, even when the central store row is present. S3 recorder and S9 routing hook are PR-only; S9's upstream A/B-before-live hold remains. No host configuration, install, retirement, hook registration or role-grant application is included.

## Hot files and publication

Registry entries are rebuilt with scripts/host_receipts.py register_file from the frozen main registry; never hand-merged. The three lane ledger rows are appended by scripts/saturation_ledger.py and checked natively. Final shared hot files are committed last. Required checks precede the single retained #795 push, then final FOLDED and Q23-QUALIFIED headers name the pushed head. Co-op byte/range-diff verification precedes its closure of originals; their branches remain.

Process sources: native-agent-stack@d9eb68750311d5f888adec140723da174f9fe10c:docs/lanes.md:94-98; the five frozen source heads above; direct FOLDS-RULED CC review023012Z; A26 at 2026-10-07T04:20:17Z in the lane questions file, and [the bounded amendment](../../../docs/decisions/2026-10-07-skills-fold-budget-amendment.md).
