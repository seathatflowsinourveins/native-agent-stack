# Cross-family half of the clean-install selection, 2026-10-01

The blind GPT-6.1 Sol run on the 21 frozen packets, criteria and prompts of this folder's parent run
(`wf_c2377ebb-65c`), requested by `docs/decisions/2026-10-01-new-wsl-clean-install-selection.md` ("Cross-family
status"). `scripts/final_catalog.py` compares it with the blind Claude record in
`catalogs/foundation/final-catalog-20261001.json`, which records what each half named and is not an install list; the
install record is the definitive manifest (#602). The decision record is `docs/decisions/2026-10-01-final-catalog.md`.

| File | What it is |
| --- | --- |
| `preregistration-addendum.json` | The sha256 of the parent's verified inputs and of every file added below, recorded at 2026-10-01T20:44:31Z. The first process started five seconds later by the coordinator's private run log; no committed file carries a process start time. The global instruction file the processes loaded is not in its inventory (see `instruction-probe.json`). Committed as a scanner-safe rendering with identical values (its file-to-hash maps written as lists, because names such as `secrets-credentials.json` beside a hex digest trip gitleaks' generic-api-key rule); `original_sha256` is the recorded file's digest, and the original stays with the private records |
| `agreement-rule.txt` | How a GPT pick set and the Claude pick set compare and fold, frozen before any GPT return existed; the final catalog's fold extends it in two places, which its decision record discloses |
| `adapter.txt` | The tool mapping prepended to the frozen prompts (web search for the Context Mode tools; captured GitHub API facts) |
| `assignment.json` | Which judge read which packets; 11 judges in 3 groups, one critic per group |
| `judge-schema.json`, `critic-schema.json` | The output schemas `codex exec --output-schema` enforced, encoding the returns the frozen prompts ask for |
| `facts/` | The three GitHub API endpoints the judge prompt names (repository, latest release, last default-branch commit) for all 209 candidates, captured before the run without popularity fields |
| `run_xfam.py` | The runner: one independent `codex exec` per judge and critic (GPT-6.1 Sol, effort max, read-only sandbox, live web search, ephemeral), one retry per process, every attempt kept |
| `build_record.py` | Builds the two files below from the private originals and audits every web search, opened page and command |
| `selection-gpt.json` | Per layer: the GPT picks after the critic, the judge's picks where the critic revised them, reasons, exclusions, failed fact checks and the critic's issues |
| `run-record.json` | Every process attempt with exit, duration and returned usage (no start or end timestamps), the contamination audit, and the sha256 of each private original, the run log among them |
| `instruction-probe.json` | The 2026-10-02 probe showing that `codex exec` loads `$CODEX_HOME/AGENTS.md`; the run's default home named eight packet candidates, so its judges were not instruction-blind. The file's sha256 here is the probe's, taken the next day, not a frozen input of the run |

The private originals (prompts with local paths, event streams, raw returns and stderr) stay outside the repository with
the coordinator's private records. This is source review by model judges: no candidate was installed or measured. The judges' instructions included the user's global Codex `AGENTS.md`, which names eight of the candidates (`instruction-probe.json`).
