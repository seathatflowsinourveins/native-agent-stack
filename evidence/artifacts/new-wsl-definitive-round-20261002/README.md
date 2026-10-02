# Clean-room definitive round of the new-WSL architecture (2026-10-02)

A clean-room audit of the definitive manifest (#602) on the 43 slots that #591 left open, plus a deep-dive dossier of
every candidate's upstream code and README. Both model families decide each slot in a clean room under #591's decision
rule, and `compare.py` sets each result against the manifest row the slot maps to: agree, contest, nominates (a row
waiting for its measurement), cross-check (a measurement row), pin agree or conflict, or not settled. The manifest is
the install record; this round changes none of its rows and publishes no architecture of its own. A contest is a
hand-off to the manifest's owner and a pin conflict goes to the user (amendment 2, which retargeted the round after
#602 merged and before any decision ran). It replaces nothing in #591's, #589's or #602's folders.

Why a clean room: `codex exec` loads `$CODEX_HOME/AGENTS.md`, and workflow subagents receive the global `CLAUDE.md`;
both files name candidates of this field, so the earlier two-family agreement on those layers was not independent
(`evidence/artifacts/new-wsl-clean-install-selection-20261001/cross-family/instruction-probe.json`). Here no judge, writer or verifier
sees an instruction file, hook, skill or MCP server (`clean-room.json`, with its probes).

| File | What it is |
| --- | --- |
| `units.json`, `contenders.json`, `build_units.py` | 19 units, 43 open slots asked as neutral function questions, and every candidate of each unit's field (the frozen #589 packets, plus the runtime rows' fields written for this round); prior picks and labels are left out |
| `criteria.txt` | #591's frozen criteria, byte-identical |
| `dossier-*.json/txt`, `verify-*` | The deep-dive dossier (README read in full, code, packaging, tests and CI, claim checks against code, cited as path:line at the revision) and its verification |
| `decide-*`, `critic-*`, `adjudicate-*` | #591's decision rules, applied per unit with several slots, to dossiers and cloned sources |
| `decision-rule.txt` | When a slot is definitive, how splits are adjudicated, and what happens when adjudication does not settle |
| `clean-room.json` | The exact flags and isolated configuration of both clients, and the probes that show no instruction file reaches them |
| `run_round.py`, `freeze.py` | The runner (clone, dossiers, packets, decide, critic, adjudicate) and the preregistration writer; `freeze.py --check` verifies the frozen files through the amendment chain |
| `audit-observations.json` | A byte-identical copy of the upstream audit's observations frozen in the preregistration; the packets state its sampling limits (the first five release assets queried for attestations, one page of check runs) |
| `compare.py` | The comparison with the definitive manifest at #602's merge commit (pinned by sha256); writes `audit-of-manifest.json` |
| `preregistration.json` | The sha256 of every frozen file, recorded before the first dossier |
| `preregistration-amendment-1.json`, `preregistration-amendment-2.json` | The runner's prompt fix (before the decide stage), and the retargeting to an audit of #602 with the comparison rule, the row mapping, the audit labels and the run notes (before any packet or decision) |

Private originals (clones, raw returns, event streams) stay outside the repository; the assembled record lists their
sha256. This is source review by model judges with adversarial critics: no candidate is installed or measured here.
