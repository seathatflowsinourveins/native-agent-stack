# Headless and SDK (`agent-sdks`)

Client 2.1.295, checked 2026-10-09. Index: [slots.md](slots.md).

## headless-sdk

**Status:** default (scoped). **Default:** `claude -p` with every fence on the command line

- **Route:** An explicit `--permission-mode dontAsk` with an explicit `--allowedTools` list for unattended workers (never inherit: an inheriting `-p` run on this host starts in bypassPermissions); `--strict-mcp-config` with `--mcp-config`; `--setting-sources` or `--restricted` (then carry the deny list and guard hooks through `--settings`, or keep code-running tools out of `--tools`); `--tools`, `--max-turns` (documented in cli-reference, absent from `--help`), `--max-budget-usd`, `--json-schema`; bound the post-final-turn wait with `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`; `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` for child processes; the Claude Agent SDK (Python) as the measured reader and extraction worker
- **Alternatives, ranked:** 1. claude-agent-sdk-python for hosted workers; 2. claude-agent-sdk-typescript
- **Rejected:** `--bare` on OAuth subscription lanes (it never reads OAuth); `--bare` for reader jobs (it drops Glob and Grep; measured on 2.1.295); Relying on the built-in starting mode
- **Evidence:** headless.md; headless-sdk-O2, O3, O4, O5, O12; Measured: --bare leaves only Read of Read/Glob/Grep (client-behaviour-2.1.295 record)
- **Notes:** HOST-07 required `--bare` outside trusted checkouts; on this OAuth host the documented fence is `--restricted` with `--permission-prompts none` and `--strict-mcp-config`. Two call sites lack fences (skill_usage.py).
- **Supersedes:** M6 (the fence for non-bare lanes); HOST-07 on OAuth hosts; M46 (`-p` start mode can be auto)
- **Overturn when:** A release changes `-p` defaults or `--bare` authentication, or a measured fence gap.
- **Primary sources** (read 2026-10-09; 4 of 4 practices the refuters kept, measured first; fetch time and sha256 of the bytes read in the record's reading file):
  - [Non-interactive mode](https://developers.openai.com/codex/noninteractive) (unknown; asserted; extends): When a script consumes the run, use a machine-readable event stream, so every event and its per-turn token usage can be captured and measured.
  - [Non-interactive mode](https://developers.openai.com/codex/noninteractive) (unknown; asserted; extends): Split multi-stage headless work, such as review then fix, into runs where the second stage resumes the first session instead of starting cold.
  - [Non-interactive mode](https://developers.openai.com/codex/noninteractive) (unknown; asserted; extends): A headless run that depends on an MCP server should fail when that server does not start, rather than quietly finishing without the tool.
  - [Non-interactive mode](https://developers.openai.com/codex/noninteractive) (unknown; asserted; agrees): When later steps need stable fields, require the final response to match a JSON Schema instead of parsing free text.
