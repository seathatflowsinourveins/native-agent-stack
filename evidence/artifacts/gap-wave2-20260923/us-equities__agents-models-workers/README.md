# Gap wave 2: us-equities / agents-models-workers (2026-09-23)

This directory holds one receipt per open gap for this layer, plus `results.json`. The gaps use the
crosswalk indices from main `92bb279` (crosswalk PR #85). The work ran from worktree base
`41d39b3`. Preregistrations were committed before any check ran: commit `5480a9c` at
07:23:50Z. Two amendments were added later and are labelled as late: `bd53077` for gap 2 and
`52bef05` for gap 5. A fix-round preregistration for gap 6 (`06d5548`, 07:52:54Z) was written
after an independent review and before the fix-round runs. A later source-review correction (round 3, 2026-09-23, no check re-run) fixed the gap-11 description of the QMD baseline corpus. Fix round 2 (2026-09-23, after a second independent review) added three gap-0 trust-probe preregistrations, all written before their runs (`prereg/0-worker-backend-head-to-head.trust-probe*.fix-round2.json`). It corrected the gap-0 shared-config disclosure, committed the main-round service start/stop evidence and extended redaction. No outcome changed. Helper scripts, sealed query sets and prompts are in
`blueprints/gap-wave2-20260923/us-equities__agents-models-workers/`. Raw outputs are in `raw/`,
with host paths replaced by `$HOME`. Each receipt lists sha256 hashes for the raw files it cites.

| Gap | Outcome | Receipt | One-line result |
| ---: | --- | --- | --- |
| 0 | advanced | `0-worker-backend-head-to-head.json` | Same task, same `head -c` read: SDK 6/6 facts, 41,039 tokens. DeerFlow/ACP 6/6 facts, 43,313 tokens. OmniRoute blocked (no Linux gateway with a Codex OAuth connection). |
| 2 | advanced | `2-mcp-allowlist-order-block.json` | Synthetic broker mock under a read-only sandbox. Without an allowlist, `submit_order` reached the mock. With `enabled_tools`, it was not exposed. The real Alpaca paper arm belongs to sota-workflow-resolution. |
| 4 | settled | `4-socraticode-holdout-recall.json` | Sealed set of 32 queries against SocratiCode, limit 10: hit@10 0.9375, MRR 0.7618. A peer run with 35 questions corroborates it. |
| 5 | settled | `5-fomc-dated-retrieval.json` | 31 federalreserve.gov pages in a disposable Qdrant, 30 dated queries. Dense retrieval scored 30/30, but only because each page carries a dateline. With datelines removed it scored 2/30. A date filter scored 30/30 in both cases. |
| 6 | advanced | `6-ai-memory-pin-and-features.json` | Fix round: the upstream v2.4.0 suite ran in an isolated network namespace. Result: 3,515 passed, 0 failed, 14 ignored upstream. Two failures, caused by where this unit put the build directory, passed on a diagnostic rerun. The CLI surface, MCP tools, configs and status lines were captured against isolated 2.3.2 and 2.4.0 servers. Remaining: the catalog pin text, which the coordinator owns, and the live service's state. |
| 7 | advanced | `7-winner-readiness-today.json` | Re-run today: SDK readiness (32% of the weekly window used), SDK task, SocratiCode search, and Codex and Claude MCP `memory_status` against an isolated server. The native Codex exec shape failed until MCP tool approval was set. The live service was not re-observed. |
| 9 | settled | `9-composed-sdk-worker-restart-handoff.json` | One SDK worker ran with isolated ai-memory and SocratiCode MCPs and was SIGKILLed after its handoff. A fresh worker accepted the handoff and finished. Answers matched gold (6/6 and 3/3). Run 1's usage is unavailable because it was killed before reporting, so whole-task usage is at least 166,882 tokens. |
| 11 | settled | `11-twelve-query-per-lane.json` | Twelve fixed queries, recall@3: SocratiCode 11/12 and ai-memory FTS 11/12, both over the 18 eligible documents. The recorded QMD result, 8/12, returned from the same 18 documents but scored BM25 over 33, so the scoring statistics differ. |
| 12 | settled | `12-exhaustive-source-recovery.json` | 32 queries with 176 exhaustive gold lines: hit@10 0.9375, mean completeness@10 0.762, fully complete for 14/32 queries. |
| 15 | advanced | `15-artifact-reduction-whole-task.json` | Codex only: the Context Mode arm used about 2.1x the tokens of the plain arm, with equal accuracy and no failures. The Claude child-usage.mjs arm is deferred because the shared account is reserved. |
| 16 | advanced | `16-non-adopted-candidate-comparison.json` | LoopX 1.1.0 governed Turn on the same task: 0/6 facts. The typed result replaced the requested JSON, so the validator failed. SDK: 6/6. LoopX's restart and quota claims were not tested. |

## Isolation and disclosures

- **Services started for this run.** A disposable Qdrant ran on 127.0.0.1:27333/27334 and an
  isolated ai-memory 2.3.2 server on 127.0.0.1:27374, with a temporary data directory and
  temporary HOME. `AI_MEMORY_SERVER_URL` pointed at that server for the gap-9 and gap-11 CLI
  calls. Both processes were stopped at the end, and the ports were checked to confirm they were free.
  Correction from the fix round: the first-round gap-6 CLI calls did not point at that server. They
  ran either with no URL set or with a closed port (127.0.0.1:1). They were re-run against isolated
  2.3.2 (27374) and 2.4.0 (27375) servers started and stopped for that purpose. Upstream tests ran
  under `unshare -rn`, where only a private loopback exists, so host services were unreachable.
  Fix round 2: the exact start, config-edit and stop commands for the main-round Qdrant and
  ai-memory 2.3.2 services, with their outputs, redacted log heads and the edited config lines
  (`bind = "127.0.0.1:27374"`, `embedding_provider = "none"`), are committed as
  `raw/services-main-round.txt` (retained host-local and not published since the privacy sweep; see the coordinator notes below). They were exported from this unit's own session transcript by
  `services/export_main_round_services.py` and not re-run. Receipts 4, 5, 9, 11 and 12 cite that file.
- **Side effect on shared Codex configuration (gap 0, corrected in fix round 2).** The
  DeerFlow/codex-acp arm left a persistent project-trust entry in the shared
  `$HOME/.codex/config.toml` (lines 41-42):
  `[projects."$HOME/.cache/gap-wave2-20260923/agents-models-workers/runs/g0-deerflow/runtime/acp-workspace"]`
  with `trust_level = "trusted"`. The earlier receipt said the writer was undetermined, which was wrong.
  codex-acp 1.12.0 adds `trust_level = "trusted"` for every session root to the thread config.
  The native codex app-server it spawned then persisted that entry during or at the end of the
  turn: the file mtime is 3 ms after `turn/completed`, and codex-acp sent no config write. An
  isolated probe (temporary CODEX_HOME, no auth) found that `thread/start` alone does not persist
  it, and a positive control showed that the probe detects a persisted write. The exact call that
  persists the entry is therefore unconfirmed. The entry trusts only a directory in this unit's
  cache. This unit did not edit the shared file; removing the entry is the coordinator's decision.
  The probe's unauthenticated app-servers each attempted a websocket to api.openai.com and
  received HTTP 401. No credential was used and no inference ran.
- **Hooks.** Every Codex run set `features.hooks=false` and `features.plugin_hooks=false`, so
  native ai-memory hooks could not reach the live store. The single Claude call used
  `--setting-sources project` from a temporary working directory, so user hooks did not load, and
  `--strict-mcp-config`.
- **Embeddings.** Embedding requests went to the running Nemotron vLLM endpoint on 127.0.0.1:8231
  as read-only `/v1/embeddings` calls. The service was not restarted or reconfigured.
- **Network downloads.**
  - About 2.8 MB of FOMC calendar and statement HTML from federalreserve.gov.
  - The LoopX 1.1.0 wheel from PyPI (6.2 MB, no dependencies), installed into a venv under
    `$HOME/.cache/gap-wave2-20260923/agents-models-workers/`.
  - Fix round, gap 6, all under the same cache:
    - Rust 1.95.0 via rustup (614 MB unpacked).
    - The ai-memory v2.4.0 shallow clone (24 MB).
    - 492 crates (85 MB of archives).
    - all-MiniLM-L6-v2 from huggingface.co (91.3 MB), fetched by an isolated 2.4.0 server.
    - Heavy steps ran through `ecosystem-bounded-run`.
- **Redaction.** Fix round 2: `redact_raw.py` now also replaces `ls -l` owner and group columns and
  this host's name. It was re-applied to `raw/6-default-embedding.txt` and to the new probe outputs.
- **Model usage.**
  - Codex account, one call at a time: 15 runs (turns) across gaps 0, 2, 7, 9, 15 and 16. This
    includes one failed attempt caused by a prompt error, which is recorded in gap 7.
  - Claude account: one bounded Sonnet call for gap 7.
  - No paid API was used, and no credentials were read. There was no broker contact.
- **DeerFlow adapter log.** Fix round: the log is now committed in redacted form as
  `raw/0-deerflow-adapter-log.redacted.log`, using `workers/redact_adapter_log.py`. The payloads
  of account, config, skills, remote-control and rate-limit messages are withheld. E-mail,
  host name, user paths and UUIDs are replaced. The tokenUsage, sandbox, approval and command
  lines remain verbatim. `raw/0-deerflow-adapter-log-extract.json` keeps the private original's
  sha256.

## Coordinator note (2026-09-23): privacy sweep, second pass

Moved out of the repository: every remaining conversation-derived record (transcript extracts and transcript tool-call/tool-result captures). Each file is kept byte for byte in host-local, owner-only storage (directories 0700, files 0600) outside the repository and is not published. Every reference keeps its relative name and sha256 and is marked not published with a `retention` note; the receipts' own published fields (`cmd`, `exit`, `output_excerpt`, and `output_sha256` where present) remain the published support:

- `raw/services-main-round.txt`: sha256 `d1109be89f5b...`, 8440 bytes

Pins updated: the `raw_artifacts` entry for `raw/services-main-round.txt` in receipts 4, 5, 9, 11 and 12 (`published: false`, `retention`, sha256 unchanged). `make_receipts.py` now emits that entry with the retained file's sha256 instead of hashing a repository copy.
