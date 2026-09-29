# Cloudflare security-audit skill trial row, stale-upstream flags and sandbox gate, 2026-09-27

Base and `catalog_revision`: `ba1700adc6557b03d3c9336c4d3a951791fc8de5` (a `main` commit).
Upstream reads ran on 2026-09-28 from 02:03Z to 02:18Z (UTC), the evening of 2026-09-27 on the
host (EDT). Tools: gh 2.101.0, git 2.43.0, jq 1.7, Python 3.13.15, PyYAML 6.0.3 (already in the
host's uv cache; nothing was downloaded or installed), Node v24.21.0 for page fetches inside
Context Mode `ctx_execute`. `ctx_fetch_and_index` is not granted to this worker, so pages were
fetched with `fetch()` in `ctx_execute`. Raw bytes stayed outside the checkout. Only their size,
sha256 and quoted lines are here, in [`delta.json`](delta.json).

A review repair round ran from about 03:05Z to 03:17Z on 2026-09-28 (UTC), still 2026-09-27 on the
host. It read again the pinned `SKILL.md` (same sha256) and `report-schema.json` (same size as the
tree listing), the settings reference, the sandboxing page and the Trust Hub audit page (each the
same bytes and sha256 as the first read), and read `claude plugin eval --help` from the local
Claude Code 2.1.283. `delta.json` `quoted_passages` and `repair_round` hold what it added.

A second repair round, at 07:07Z on 2026-09-28 (03:07 EDT, so 2026-09-28 on the host), answered a
cross-family review finding on the invocation claims. It fetched the skills page, the settings
reference and the commands reference again with curl 8.5.0, each the same bytes and sha256 as the
first read. `delta.json` `checks.repair_round_2` holds its record, and the new docs lines are under
`native_docs`.

The decision and its reasoning are in the
[2026-09-27 addendum](../../../docs/decisions/2026-09-25-skills-trial-and-usage.md#addendum-2026-09-27-security-audit-trial-row-stale-upstream-flags-sandbox-gate).
Nothing was installed and no host setting changed.

## Results

| Question | Result | Evidence class |
| --- | --- | --- |
| Is the pin current upstream? | Yes. `c1c8a8c` is `main`'s HEAD (committed 2026-09-14). `skills/security-audit` is tree `ccbc33ed119b28c3ef7b44a7e2081ab191ad63af` at the pin and at HEAD, and the contents API agrees: 20 files, 314,670 bytes. `SKILL.md` is 22,026 bytes, sha256 `5e3e96a1…6dac85`, and its git blob `92178da` was recomputed locally. Frontmatter: `name`, `description` only; 359 characters. License: MIT (repository `LICENSE` at the pin). | upstream-unchanged |
| Audit gate (rule 3) | skills.sh page: Gen Agent Trust Hub Pass, Socket Pass, Snyk Warn. Audit pages: SAFE; Pass; MEDIUM "W011: Third-party content exposure detected (indirect prompt injection risk)". Audit API: `ath` safe, `socket` safe (0 alerts, score 90), `snyk` medium. All analyzed 2026-09-15, after the pin became HEAD; no page names a revision. A Warn does not exclude. | upstream-unchanged (independent observation) |
| `official` | True. The manifest's convention is owner-scoped, and skills.sh/official lists the `cloudflare` owner. The owners of the manifest's `official: true` rows (`openai`, `anthropics`, `vercel-labs`) are listed, and the owners of its `official: false` rows (5) are absent. | upstream-unchanged |
| Does the 2026-09-23 `not_adopted` stand? | No. It was refuted 2 of 2 on 2026-09-23. Gap restated: `/security-review` "Reviews the diff between your branch and origin's default branch"; `/code-review` reviews "the current diff, or a PR number, branch, or path you pass, for correctness bugs". There is no whole-repository coverage ledger or verdict contract. Whether the skill closes the qualification gap is unknown until M5c. | upstream-unchanged (docs quotes) |
| Issue #20 | Open. Filed by an account with no association to the repository. n = 3 per arm, one target. Precision median 90%. Quick profile median $29.95 vs single-agent $2.06, with equal median recall (0.467). The author ran a competing pipeline and names no commit. | upstream-unchanged (weak third-party report) |
| `openai/skills` | `main`'s HEAD is still `49f948f` (2026-06-24T02:36:12Z), our pin. 0 commits on `main` since 2026-06-29. Flagged: the next verdict wave fields a challenger for `security-best-practices` (kept) and `security-threat-model` (trial). | upstream-unchanged |
| `praetorian-inc/noseyparker` | Archived 2026-04-24T16:25:50Z; last release v0.24.0 (2025-05-08). README: "Nosey Parker is now Replaced by Titus. Nosey Parker is Officially Retired". No current catalog names it. The 2026-09-26 dated sweep records and the append-only saturation ledger carry it as a `secrets-credentials` survivor, so the correction is in the addendum. | upstream-unchanged |
| Sandbox gate | Foundation open gate `claude-code-sandbox-profile` added (owner: foundation coordinator; re-check 2026-10-11). Its measurement list carries the deferral's three controls, including the `credentials.files` deny for the store (a `sandbox.credentials.files` entry with mode `deny`); a credentials arm that reads a store file through `~/` and through its absolute path; and a separate `strictAllowlist` arm. `adoption/manifest.json` lists it in `continuation.next_action_refs`. | our-integration |

## Changes in this branch

- `adoption/skills/manifest.json`: trial row `security-audit` (cloudflare/security-audit-skill@c1c8a8c,
  `name-only`, Codex off, `added` 2026-09-27), appended last; `checked_at` set to 2026-09-27. Budget
  sums are unchanged, because name-only and Codex-disabled rows count toward neither. Its gap text
  records stage-only use as a usage policy that `name-only` does not enforce (repair round 2).
- `adoption/templates/claude.settings.template.json`: `skillOverrides` gains
  `"security-audit": "name-only"`, as `tests/test_skills_manifest.py` requires.
- `docs/decisions/2026-09-25-skills-trial-and-usage.md`: the 2026-09-27 addendum.
- `catalogs/foundation/manifest.json`: top gap `claude-code-sandbox-profile` (priority 2, `open`) and
  its open gate. `scripts/validate_foundation.py` allows exactly three ranked gaps, and a gate must name
  an open or partial gap. The new row therefore takes the priority-2 slot of
  `worker-cancellation-crash-resume` (`accepted_within_scope`). That row's scope sentence is the
  `evidence_scope` of decision `native-child-interruption-recovery` verbatim, so no claim is lost;
  the other two rows are untouched. `checked_at` stays 2026-09-21, because the validator ties it to
  `decisions.json` and no decision was re-checked. The gap's `source_paths` add
  `docs/secret-storage.md` and `docs/harness-rules-convergence-20260922.md` (PS-1).
- `adoption/manifest.json`: `continuation.next_action_refs` lists `claude-code-sandbox-profile`, as it
  listed each open foundation gate before (`d17b3cff` and `49c094d9` changed the two lists together).
  `tests/test_adoption_contract.py` checks only that the list is a subset, so no test fails without
  it; the listing rests on that precedent.
- `manifests/evidence.json`: hashes for every changed listed file and this receipt.

## Checks (our-integration)

Each new check was first run with its condition absent, and it failed:

- **Manifest test.** `tests.test_skills_manifest` with the row but no template key: exit 1, failing
  only `TemplateSkillOverridesConsistencyTests`. With the key: 21 tests OK.
- **Evidence manifest.** `scripts/validate.py` before registration: exit 1, with SHA-256 and byte
  mismatches on the 4 changed listed files and "evidence file is not hash-listed" for this
  receipt's 2 files. After registration: exit 0, 7,375 hashed files.
- **Foundation gate.** `scripts/validate_foundation.py --root` on a throwaway copy of the tracked
  tree passes as-is. It fails with "open_gates: must reference exactly the unfinished gaps" both
  when the new gap is closed with its gate kept and when the gate is removed with the gap open.

Module results, from `python3 -m unittest`:

| Module | Tests | Result |
| --- | --- | --- |
| `test_skills_manifest` | 21 | OK |
| `test_install_skills` | 19 | OK |
| `test_skills_status` | 43 | OK |
| `test_install_claude_profile` | 58 | OK, 3 skipped without PyYAML; 0 skipped with the cached PyYAML |
| `test_render_config` | 25 | OK |
| `test_foundation_catalog` | 18 | OK |
| `test_adoption_contract` | 12 | OK |
| `test_apply_claude_settings` | 23 | OK |
| `test_ecosystem_manifest` | 56 | OK |

`component_matrix.py --write` and `new_host_grand_list.py --write` changed no tracked file.

**Failed attempt, retained.** The first commit was blocked by the gitleaks pre-commit hook: a
`generic-api-key` finding on a `delta.json` key named `contents_api_dir_sha`, which held the public
40-hex tree SHA. The cause was the key name, not a credential. The key was renamed, with no
allowlist and no `--no-verify`, and the rerun found no leaks (`checks.failed_attempts`).

**Repair round** (`checks.repair_round`, our-integration):

- `scripts/validate.py` before registering the five changed files: exit 1, with SHA-256 and
  byte-count mismatches on exactly those files. After registration: exit 0, 7,375 hashed files.
- `scripts/validate_foundation.py`: exit 0.
- The nine modules above: exit 0 with the same counts. `test_install_claude_profile` with the cached
  PyYAML: 58 tests OK.
- `component_matrix.py --write` and `new_host_grand_list.py --write` changed no tracked file.
- Quote checks (local integration): each new quote matched its source when read again, and every
  quoted passage in the addendum (31) and in this README (8) is in `delta.json`.
- The `next_action_refs` listing has no failing control, because `tests/test_adoption_contract.py`
  checks only that the list is a subset of the open gates.

**Repair round 2** (`checks.repair_round_2`, our-integration). A cross-family GPT-6 review found
that the addendum and the manifest gap overstated what `name-only` does.

- Reproduced: `jq -r '.native_docs.skills.L811'` on this receipt prints the `name-only` row with
  `Yes` in the `/` menu column, and the in-memory `check_claude_listing` probe accepts `name-only`
  (`ok`). The status check compares the listing string only.
- Correction: `name-only` removes the description from Claude's listing. Claude can still invoke
  the skill by name, and a user can still type `/security-audit`. Stage-only use is a usage policy
  that the stage prompts carry. No `skillOverrides` state hides the `/` entry and keeps the skill
  listed to Claude: only `off` hides the entry, and it hides the skill from Claude too.
- Residual: the frontmatter field `user-invocable: false` would remove only the user trigger. With
  it, "Claude still can" invoke the skill, so stage-only use stays a usage policy even then. The
  field is absent at the pin, and a local edit would break the pin. `install_skills.py` counts an installed `SKILL.md` as
  current only when its sha256 matches, and rolls back an add that does not.
- `scripts/validate.py` before registering the four changed files: exit 1, with SHA-256 and
  byte-count mismatches on exactly those files. After registration: exit 0, 7,375 hashed files.
- `scripts/validate_foundation.py`: exit 0. The nine modules above: exit 0 with the same counts.
  `test_install_claude_profile` with the cached PyYAML: 58 tests OK.
- `component_matrix.py --write` and `new_host_grand_list.py --write` changed no tracked file.
- Quote checks (local integration): 17 docs-line comparisons against the fresh fetch, 0 failed.
  Every quoted passage in the addendum (39) and in this README (6) is in `delta.json`.
- After the fix, a grep for the overstated phrases finds none (exit 1) in the decision record, the
  manifest, this README or `delta.json` outside `checks.repair_round_2`, which records the finding
  in those words. The listing stays `name-only`, so the probe still returns `ok`.

## Not done here (live-run-pending)

- The skill install, the settings apply, the Codex disable table and the host read-back belong to
  the coordinator. If the skill is installed before the `name-only` override and the Codex table are
  live, every session lists its full description until they are, so apply both first.
- A native probe of `name-only` invocation reach: whether a typed `/security-audit` runs, and
  whether the model invokes the skill unprompted.
- Removing the user trigger stays a residual. `user-invocable: false` needs a new upstream pin, then
  a native probe together with the `name-only` override. Stage-only use stays a usage policy
  either way, because the field leaves Claude's own invocation on.
- M5b's unchanged upstream `node --test` at the pin, the labelled fixture and the budget.
- M5c is queued behind Gate A and Gate B.
- The sandbox profile measurement, due for re-check 2026-10-11.

## Coordinator hand-back, in order

```sh
# 1. Settings first, so the name-only override is live before the skill exists
python3 tools/adoption/render_config.py --host <host> --out "$RUN_DIR/rendered"
python3 tools/adoption/apply_claude_settings.py --template "$RUN_DIR/rendered/settings.json" --dry-run
python3 tools/adoption/apply_claude_settings.py --template "$RUN_DIR/rendered/settings.json"
# 2. Codex off: append the security-audit table from this output to ~/.codex/config.toml
python3 tools/adoption/install_skills.py --print-codex-config
# 3. Install only this skill
python3 tools/adoption/install_skills.py --only security-audit --skills-bin <tools-root>/skills-1.7.0/bin/skills --dry-run --json
python3 tools/adoption/install_skills.py --only security-audit --skills-bin <tools-root>/skills-1.7.0/bin/skills --json
# 4. Read back
python3 scripts/skills_status.py --skills-bin <tools-root>/skills-1.7.0/bin/skills --json
claude -p --no-session-persistence --output-format stream-json --verbose "/skill-doctor" < /dev/null
#    the system/init event must list security-audit; /skill-doctor shows its listing state
```

## Reproduce

```sh
gh api 'repos/cloudflare/security-audit-skill/git/trees/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8?recursive=1'
gh api 'repos/cloudflare/security-audit-skill/contents/skills?ref=c1c8a8c1471069fb0e188eeaff69b8e8db6564a8'
gh api -H 'Accept: application/vnd.github.raw' 'repos/cloudflare/security-audit-skill/contents/skills/security-audit/SKILL.md?ref=c1c8a8c1471069fb0e188eeaff69b8e8db6564a8' | sha256sum
gh api repos/cloudflare/security-audit-skill/issues/20
curl -s 'https://add-skill.vercel.sh/audit?source=cloudflare%2Fsecurity-audit-skill&skills=security-audit'
gh api 'repos/openai/skills/commits?sha=main&since=2026-06-29T00:00:00Z&per_page=100' --jq length
gh api graphql -f query='{repository(owner:"praetorian-inc",name:"noseyparker"){isArchived archivedAt latestRelease{tagName publishedAt}}}'
# repair round: quoted skill and schema lines, sandbox docs, native eval help
gh api -H 'Accept: application/vnd.github.raw' 'repos/cloudflare/security-audit-skill/contents/skills/security-audit/SKILL.md?ref=c1c8a8c1471069fb0e188eeaff69b8e8db6564a8' | sed -n '12p;21p;24p;40p;60p;82p;172p;175p'
gh api -H 'Accept: application/vnd.github.raw' 'repos/cloudflare/security-audit-skill/contents/skills/security-audit/report-schema.json?ref=c1c8a8c1471069fb0e188eeaff69b8e8db6564a8' | sed -n '12p;252p;369p'
curl -s https://code.claude.com/docs/en/sandboxing.md | sed -n '299p;525p'
curl -s https://code.claude.com/docs/en/settings-reference.md | sed -n '2176p;2188p;2587p'
claude plugin eval --help
# repair round 2: name-only visibility, invocation and the enforcement residual
jq -r '.native_docs.skills.L811' evidence/artifacts/cloudflare-audit-skill-trial-20260927/delta.json
curl -s https://code.claude.com/docs/en/skills.md | sed -n '360p;523p;527p;766p;768p;808,813p;817p'
curl -s https://code.claude.com/docs/en/settings-reference.md | sed -n '4163p;4167,4170p'
python3 -m unittest tests.test_skills_manifest tests.test_install_skills tests.test_skills_status
python3 -m unittest tests.test_foundation_catalog tests.test_adoption_contract
python3 scripts/validate_foundation.py
python3 scripts/validate.py
# repair round 2 verification: the user-trigger residual (skills docs L796, L799)
curl -s https://code.claude.com/docs/en/skills.md | sed -n '796p;799p'
```
