# security-audit host install and M5b gate 1 (2026-09-28)

**Scope.**
- On one host, this receipt records the plan's M5a install of
  `cloudflare/security-audit-skill` at `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8`.
  The trial row came from PR #448, merged as `8315274f`.
- It also records the first of the three M5b suitability gates.
- `~` stands for the operator's home directory.

**Evidence classes:**
- **upstream-unchanged:**
  - the skill's own validator tests;
  - Claude Code's own `/skill-doctor`.
- **our-integration:**
  - `install_skills.py`, `skills_status.py` and the settings edits.

Historical receipts do not certify another host.

## Result

| Step | Command | Result |
| --- | --- | --- |
| Claude listing | single-key `jq` edit of `~/.claude/settings.json`, after a backup | Only `skillOverrides["security-audit"] = "name-only"` added; the 87 deny entries are unchanged |
| Dry run | `install_skills.py --only security-audit --dry-run --json` | exit 0, `planned` |
| Install | `install_skills.py --only security-audit --json` (skills CLI 1.7.0) | exit 0, `installed` |
| Codex disable | append the `security-audit` block from `--print-codex-config` | Read back with `tomllib`: `enabled = false` |
| Status | `scripts/skills_status.py --json` | `pass: true`. Every check is `ok`: canonical, link, listing (`name-only`), Codex disable, tree and lock |
| Native listing | `skill_usage.py --run-skill-doctor --json` (Claude Code 2.1.283) | `name-only`, 20 context tokens, 0 uses |
| M5b gate 1 | `node --test validate-findings.test.cjs validate-coverage-ledger.test.cjs` (Node v24.21.0) | exit 0, 65 of 65 pass ([node-test.txt](node-test.txt)) |

**How the tests ran.**
- The tests ran in a copy of the installed folder. Every file's sha256 matched the install.
- The two test files and the two validators each match `gh api` raw content at the pin.
- The copy's `SKILL.md` sha256 equals the manifest's `skill_md_sha256`.

## M5b and M5c status

- **Gate 1**, the unchanged upstream tests at the pin: passed.
- **Gate 2**, a labelled fixture: open.
  - No upstream labelled set has been checked yet.
  - No pre-registered seeded copy has been built.
- **Gate 3**, the budget:
  - The user set a high budget on 2026-09-27, but only after Gate A (token saving end to end) and Gate B (a settled GPT-6 route) pass.
  - On 2026-09-28 the owning session reported that neither gate has passed.
- **M5c** stays queued.

## Deviation

The trial decision puts the Codex table into `~/.codex/config.toml` before the install. It went in 10 s after it: the install ran at 09:08:33Z and the append at 09:08:43Z. The Claude override went in first, as planned.

## Still pending

- **Invocation reach.** Two things were not probed:
  - whether a typed `/security-audit` runs;
  - whether Claude invokes the skill unprompted.

  The skills docs list `name-only` as available in the `/` menu.
- M5b gates 2 and 3, and M5c.
- The sandbox measurement (open gate `claude-code-sandbox-profile`).

## Reproduce

```sh
python3 tools/adoption/install_skills.py --only security-audit --skills-bin <skills 1.7.0> --dry-run --json
python3 scripts/skills_status.py --json
python3 tools/skill-usage/skill_usage.py --run-skill-doctor --json
cd <copy of ~/.agents/skills/security-audit> && node --test validate-findings.test.cjs validate-coverage-ledger.test.cjs
for f in validate-findings.test.cjs validate-coverage-ledger.test.cjs validate-findings.cjs validate-coverage-ledger.cjs; do
  gh api -H 'Accept: application/vnd.github.raw' "repos/cloudflare/security-audit-skill/contents/skills/security-audit/$f?ref=c1c8a8c1471069fb0e188eeaff69b8e8db6564a8" | sha256sum
done
```
