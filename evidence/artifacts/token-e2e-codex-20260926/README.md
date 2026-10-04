# Token-efficiency stack inside native Codex sessions (2026-09-26)

This is the Codex side of [the Claude subagent run](../token-e2e-ultracode-20260925/README.md) (#296). On the Claude side, Codex workers could not run while the Codex account was at its usage limit. After the account was re-logged, this run used codex-cli 0.155.1 with `gpt-6-astra` at reasoning effort `max`.

- Host: `nativestack-5975wx-20260925`.
- Workers ran from 01:26Z to 02:00Z, with two reruns from 13:43Z to 13:51Z.
- Catalog revision: `c09dd6df`.
- Machine-readable record: [`receipt.json`](receipt.json).

## Method

Each tool had its own `codex exec` session. Each session:
- ran in a fresh dedicated worktree at `origin/main`, so `rtk gain --project` isolates the RTK count;
- ran with `--json` and a strict `--output-schema`, and with stdin closed;
- used only Codex's native wiring for the tools:
  - RTK through its standing instructions (`~/.codex/AGENTS.md` referencing `RTK.md`), because RTK has no Codex hook;
  - the Context Mode plugin;
  - the user-scope MCP servers from #289: Serena, SocratiCode, ai-memory, Headroom (with `HEADROOM_OFFLINE=1`), codebase-memory and QMD;
  - the CLIs;
- did the same task as the Claude run, wrote the plain baseline only through a shell redirect, read only the tool's output, and ran a deterministic check of its answer against the baseline.

Usage is Codex-returned, from the `turn.completed` events. The exact comparisons use `token_manifest.py compare` with `o200k_base`.

## Results

11 of 15 tools worked inside Codex with a passing check. The four that did not are real limits of the tool or its wiring. Two of them were rerun once, with the same outcome.

| Tool | Channel in Codex | Result | Baseline → tool output (tokens) | Removed |
| --- | --- | --- | --- | --- |
| RTK | standing instructions (no hook) | PASS | 25,386 → 4,278 | 83.1% |
| Context Mode | native MCP `ctx_execute_file` | PASS | 97,952 → 204 | 99.8% |
| Headroom | native MCP (offline), compress plus exact retrieve | PASS | 210,316 → 14,611 | 93.1% |
| Serena | native MCP | PASS | 22,445 → 7,810 | 65.2% |
| SocratiCode | native MCP | PASS | 16,096 → 1,505 | 90.6% |
| codebase-memory-mcp | native MCP | PASS | 22,445 → 16,109 | 28.2% |
| ast-grep | CLI | PASS | 112,899 → 11,508 | 89.8% |
| MarkItDown | CLI | PASS | 505,768 → 29,471 | 94.2% |
| TOON | CLI, strict round trip | PASS | 1,642 → 907 | 44.8% |
| ai-memory | native MCP (HTTP) | PASS, 10 relevant hits | no baseline | none |
| agentsview | CLI | PASS, observed 51 Codex sessions on 2026-09-25 | observation only | none |
| jCodeMunch | expected native MCP | **not exposed** in a fresh worktree (2 attempts) | none | none |
| QMD | native MCP | **wrong scope**: the question's answer is in `adoption/update.md`, which the catalog index does not include (2 attempts) | none | none |
| Repomix | CLI `--compress` | **lossy**: dropped the declaration of `status_body` while keeping a reference to it | none | none |
| Context Hub | CLI | **content gap**: its `stripe/api` entries lack the idempotency header name and retention | none | none |

### Counters

- `rtk gain --project`, for this run's worktree only, attributable to this run: 0 → 41 commands and 0 → **17,782** estimated saved (39.1%).
- Headroom lifetime and Context Mode (Codex) stats also moved, but the after snapshot was taken about 12 hours after the runs, while other sessions were working. Those deltas are host-wide and are recorded as such in `receipt.json`; they are not credited to this run.

### Codex-returned usage

The 17 sessions (15 tools plus 2 reruns) used:

| Input | Cached | Output | Reasoning |
| --- | --- | --- | --- |
| 7,085,015 | 6,253,312 | 164,906 | 91,997 |

Per-session numbers are in `receipt.json`.

## Findings that change practice

- **jCodeMunch** is project-scoped by #240, so Codex in a fresh worktree does not have it. Workers that need it must run in a checkout whose project config registers it.
- **QMD's catalog index** holds only the two us-equities collections. Questions about adoption or new machines are outside its scope.
- **Repomix `--compress`** can drop declarations. Check exact declaration coverage before relying on a compressed pack for API or structure questions.
- **Context Hub** coverage varies by entry. Verify facts against the upstream page it cites.

## Correction to #296

#296's QMD row passed a check that only confirmed the quoted text existed in the retrieved document. That document, `catalogs/us-equities/engines-strategies.md`, does not describe how a new machine pins a release. The run retrieved a wrong document for this question. The dated note in that README records the correction.

## Retained limits

- No Codex subagent fan-out was tested; each tool ran in one top-level `codex exec` session.
- `gpt-6-astra` usage is Codex-returned. Billing is not verified.
- Codex hooks for ai-memory are still untrusted until the user trusts them in `/hooks`, so Codex capture into ai-memory was not exercised.
