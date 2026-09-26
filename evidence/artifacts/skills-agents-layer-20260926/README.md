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
| New skills worth a trial slot | Three added (below); 23 candidates reviewed individually, the rest dispositioned as named groups. | Source review, repository measurement, synthetic comparison |

## Changes in this branch

- `adoption/skills/manifest.json`: trial additions `variant-analysis` (trailofbits@0cc1c73, on),
  `writing-for-agents` (mattpocock@c55ee46, on, Codex on) and `skill-security`
  (superagent-ai@0da315b, name-only); three `description_chars` values corrected to one stated
  method; budget 7,409 of 8,000 on-listed characters and 3,054 Codex-enabled; 13 excluded groups;
  a `cli.notes` line on skills.sh API access. The settings template mirrors `skillOverrides`.
- `scripts/skills_status.py`: a per-skill, informational on-disk git tree check (`ok`,
  `runtime_artifacts`, `drift`) with tests that use `git write-tree` as the oracle.
- `tests/test_install_claude_profile.py`: shipped agents must use documented frontmatter fields
  and values and an explicit model, since the native validator does not check them.

`skill-security` won its capability over `getsentry/skills` `skill-scanner` on six fixtures
authored for this check (`scanner_comparison` in `delta.json`): both left the benign fixture
clean; it flagged 5 of 5 malicious fixtures at high or critical, `skill-scanner` 3 of 5 (it missed
environment-variable harvesting and instruction-only memory poisoning). On the 26 installed pinned
skills each flagged 4 at high, all in documentation text (SKILL.md or references), bundled tests or
the `.venv` above, which is what each skill's second, judgment stage is for. This is a small
synthetic diagnostic, not a general ranking.

## Not done here

- No skill or agent was installed, removed or reconfigured on the host; the coordinator applies
  the manifest and template after merge.
- The invoke-rate run is not recorded as a host receipt; `tools/skill-usage/README.md` names the
  `scripts/host_receipts.py record ... --component-id skills-trial` command for that.
- Proposals P1 to P7 in `delta.json` (P8 is applied here) wait for the verdict wave or a user
  decision: re-scope the `semgrep` gap or pin `semgrep-rule-creator` (neither `semgrep` nor
  `codeql` is installed here), record raw audit risks in rule 3, an upstream fix for the `uv run`
  side effect, a version-matched EdgarTools skill, `backtest-expert` on a frozen research task,
  and pruning `AGENTS.md` with the user's approval.

## Reproduce

```sh
python3 scripts/skills_status.py --skills-bin <tools-root>/skills-1.7.0/bin/skills --json
python3 tools/skill-usage/skill_usage.py --run-skill-doctor --codex-root ~/.codex/sessions --json --out <outside-checkout>/rate.json
DISABLE_TELEMETRY=1 <tools-root>/skills-1.7.0/bin/skills find "<query>" < /dev/null
curl -s 'https://add-skill.vercel.sh/audit?source=trailofbits%2Fskills&skills=agentic-actions-auditor'
gh api 'repos/<owner>/<repo>/contents/<parent-path>?ref=<commit>'   # folder tree SHA at a commit
uv run --no-project --with jsonschema --with pyyaml python -m unittest \
  tests.test_skills_status tests.test_skills_manifest tests.test_install_claude_profile
```
