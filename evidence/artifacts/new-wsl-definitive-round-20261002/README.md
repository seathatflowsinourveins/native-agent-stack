# Clean-room definitive round of the new-WSL architecture (2026-10-02)

One pick per open slot of the new-WSL definitive defaults (#591), decided by both model families in a clean room after a
deep dive of every candidate's upstream code and README. It continues #591's decision rule and replaces nothing in
#591's or #589's folders.

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
| `run_round.py`, `freeze.py` | The runner (clone, dossiers, packets, decide, critic, adjudicate) and the preregistration writer |
| `preregistration.json` | The sha256 of every frozen file, recorded before the first dossier |

Private originals (clones, raw returns, event streams) stay outside the repository; the assembled record lists their
sha256. This is source review by model judges with adversarial critics: no candidate is installed or measured here.
