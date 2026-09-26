# Skills and agents layer delta, 2026-09-26

Host `nativestack-5975wx-20260925` (WSL2), Claude Code 2.1.283, Codex CLI 0.155.1, skills CLI
1.7.0, base commit `d78d2de9`. Day 1 of the skills trial recorded in
[the trial decision](../../../docs/decisions/2026-09-25-skills-trial-and-usage.md) (see its
2026-09-26 addendum). Every number below is in [`delta.json`](delta.json), with its source,
commit and read date. Installs and stars there are discovery only, never merit.

## Results

| Question | Result | Evidence class |
| --- | --- | --- |
| Has upstream moved past any of the 26 pins? | No. Each pinned folder has the same git tree SHA at its source's default-branch HEAD; 8 of 9 sources have not moved at all, and `affaan-m/ECC` moved to `e482e57` without touching its two skills. No pin moves. | Source review (`gh api` trees at the pin and at HEAD) |
| Did any skills.sh audit change? | No. All 26 page labels read as on 2026-09-25. The audit API behind them rates `agentic-actions-auditor`'s Socket result `critical` (1 alert) while the page shows Warn. | Independent observation (skills.sh page and audit API) |
| Invoke rate, day 1 | Claude `/skill-doctor` (0 turns, $0, checked by the tool): `verification-before-completion` 32 uses, `search-first` 29, `supply-chain-risk-auditor` 29, `iterative-retrieval` 25, `fp-check` 10, `property-based-testing` 2, `mcp-builder` 1; the other 19 at 0. Codex (194 rollouts): `verification-before-completion` 59 SKILL.md reads, `search-first` 53, `security-best-practices` 23, `iterative-retrieval` 11, 7 or fewer for five others. No prune candidate and no verdict recheck (trial skills are 0.26 days old). | Local observation, not a receipt |
| Are the installed skill folders the pinned trees? | 25 of 26 hash to their pinned tree. `supply-chain-risk-auditor`'s own `uv run` created `scripts/.venv` and `__pycache__` and rewrote the pinned `scripts/uv.lock`; the status script passed it. | Local check (git tree recomputed from disk) |
| Agent frontmatter against the 2.1.283 docs | No defect. All 7 use only documented fields and values, declare `effort: max` with an explicit model (`opus` or `sonnet`), and match `~/.claude/agents` byte for byte. | Source review plus local check |
| Does `claude plugin validate` catch bad agent frontmatter? | No. With `--strict` it passed unparseable YAML, misspelled fields and undocumented values in every layout tried. | Native execution with negative controls |
| New skills worth a trial slot | Two added (below) and one deferred after review; 23 candidates reviewed individually, the rest dispositioned as named groups. | Source review, repository measurement, native execution on synthetic fixtures |

## Changes in this branch

- `adoption/skills/manifest.json`: trial additions `variant-analysis` (trailofbits@0cc1c73, on)
  and `writing-for-agents` (mattpocock@c55ee46, on, Codex on; gap limited to `AGENTS.md` and
  `CLAUDE.md`); three `description_chars` values corrected to one stated method; budget 7,409 of
  8,000 on-listed characters and 3,054 Codex-enabled; 14 new excluded entries, one of them
  `skill-security`, deferred after review; a `cli.notes` line on skills.sh API access. The settings
  template mirrors `skillOverrides`.
- `scripts/skills_status.py`: a per-skill, informational on-disk git tree check (`ok`,
  `runtime_artifacts`, `drift`) with tests that use `git write-tree` as the oracle.
- `tests/test_install_claude_profile.py`: shipped agents must parse as a YAML mapping, use only
  documented frontmatter fields with documented types and values, and name an explicit model,
  since the native validator does not check them. The YAML half skips where PyYAML is absent, like
  the repository's other YAML checks.
- `scanner_compare.py` here rebuilds the scanner fixtures from `delta.json` and runs both pinned
  scanners under an `open()` trace.

## Local skill scanners: none adopted

The first round added `superagent-ai/skills` `skill-security` for the gap that no local content
scan precedes a pin. Review removed it before any install, and `scanner_comparison` in `delta.json`
now holds eight fixtures authored for this check (native execution of both pinned scanners, each
under an `open()` audit trace):

| Fixture | skill-security: findings, score, default verdict | skill-scanner: findings |
| --- | --- | --- |
| b1 benign | none, 0, LIKELY SAFE | none |
| m1 instruction override, credential reads, piped remote script | 7 high, 1 medium; 100, DO NOT INSTALL | 2 critical, 1 high, 1 medium |
| m2 memory poisoning plus a `settings.json` permission grant | 1 high (EA5, from the grant clause); 22, REVIEW MANUALLY | none |
| m3 environment-variable harvesting | 1 high (EX2), 1 medium; 39, REVIEW MANUALLY | none |
| m4 base64 and zero-width text | 2 high; 42, REVIEW MANUALLY | 2 high |
| m5 load-time `!` command | 1 high; 24, REVIEW MANUALLY | 1 high |
| m6 memory poisoning only (m2 without the grant clause) | none, 0, LIKELY SAFE | none |
| m7 `references/example.md` linked to a file outside the skill | 2 high, read from the outside file; 46, REVIEW MANUALLY; no symlink finding | 2 critical: the outside symlink, and an instruction override read from the outside file |

At least one high or critical finding: `skill-security` 6 of 7 malicious fixtures, `skill-scanner`
4 of 7. That is a per-finding count; `skill-security`'s own verdict band says DO NOT INSTALL only
for m1. Neither deterministic scanner flags instruction-only memory poisoning (m6). On m7 both
opened the outside file and printed its canary marker on stdout, so either one, run on a skill that
links to a readable credential file, can print a line of it into the transcript. That fails the
credential rule, so both stay excluded until an upstream pin, or an enforced wrapper, rejects
symlinks that resolve outside the target (proposal P9). On the 26 installed pinned skills each
flagged 4 at high, all in documentation text, bundled tests or the `.venv` above. This is a small
synthetic diagnostic, not a general ranking.

`writing-for-agents` shares its skill-editing trigger with the synced
`anthropic-skills:skill-creator` and Codex's `.system/skill-creator`. It is admitted only for
`AGENTS.md` and `CLAUDE.md`, which no skill-creator file mentions, and proposal P10 counts only
those uses toward its gap at the review (`dispositions.added_for_trial` in `delta.json`).

## Not done here

- No skill or agent was installed, removed or reconfigured on the host; the coordinator applies
  the manifest and template after merge.
- The invoke-rate run is not recorded as a host receipt; `tools/skill-usage/README.md` names the
  `scripts/host_receipts.py record ... --component-id skills-trial` command for that.
- Proposals P1 to P7, P9 and P10 in `delta.json` (P8 is applied here) wait for the verdict wave
  or a user decision: re-scope the `semgrep` gap or pin `semgrep-rule-creator` (neither `semgrep`
  nor `codeql` is installed here), record raw audit risks in rule 3, an upstream fix for the
  `uv run` side effect, a version-matched EdgarTools skill, `backtest-expert` on a frozen research
  task, pruning `AGENTS.md` with the user's approval, a local scanner that passes m7, and
  attributing each `writing-for-agents` use to the file it served.
- The review round's four findings, their verdicts and fixes are in `review_repair_2026_09_26`.

## Reproduce

```sh
python3 scripts/skills_status.py --skills-bin <tools-root>/skills-1.7.0/bin/skills --json
python3 tools/skill-usage/skill_usage.py --run-skill-doctor --codex-root ~/.codex/sessions --json --out <outside-checkout>/rate.json
DISABLE_TELEMETRY=1 <tools-root>/skills-1.7.0/bin/skills find "<query>" < /dev/null
curl -s 'https://add-skill.vercel.sh/audit?source=trailofbits%2Fskills&skills=agentic-actions-auditor'
python3 evidence/artifacts/skills-agents-layer-20260926/scanner_compare.py \
  evidence/artifacts/skills-agents-layer-20260926/delta.json \
  <getsentry/skills@c2f99a5>/skills/skill-scanner <superagent-ai/skills@0da315b>/skills/skill-security \
  <scratch-dir> <scratch-dir>/results.json   # needs uv; compare with scanner_comparison.fixture_results
gh api 'repos/<owner>/<repo>/contents/<parent-path>?ref=<commit>'   # folder tree SHA at a commit
uv run --no-project --with jsonschema --with pyyaml python -m unittest \
  tests.test_skills_status tests.test_skills_manifest tests.test_install_claude_profile
```
