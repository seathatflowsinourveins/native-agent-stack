# Codex worker lane on the workstation, 2026-09-27

The coordinator applied the lane to the workstation's real `~/.codex` through
the watcher at **2026-09-27T07:51:52Z**, the first quiet moment with no Codex
process. `apply.txt` independently reports that no Codex processes were running
and that the three lane files were written/read back or installed. The exact
watcher timestamp is coordinator-supplied context; it is not in that text file.

**2026-09-27 revision erratum:** the local `apply_codex_lane.py` / `prove_codex_lane.py` revision was **main before #395; exact commit not retained**; the [#395 start-up allowances](../../../docs/decisions/2026-09-26-codex-worker-lane.md#addendum-2026-09-27-start-up-allowances-the-gateway-profile-and-four-base-keys) are not part of this apply and remain pending until a dry run and apply at the current revision.

The first proof retained a project-binding failure. Afterwards the coordinator
privately backed up the main checkout's untracked `.codex/config.toml` and removed
the three tables identified by `dry-run-project.txt`:

- `[plugins."context-mode@context-mode".mcp_servers.context-mode]`
- `[mcp_servers.context-mode]`
- `[mcp_servers.context-mode.env]`

The next proof passed **7/7 static checks**. The historical `--live` proof passed
**12/12 checks**, including **five real model calls**. This records the completed
workstation adoption step. The evidence classes remain those below; these
summaries are neither unchanged upstream tests nor portable host acceptance.

## Records

These are sanitized copies of the coordinator's six supplied text outputs,
retained with their original names. File names are not an execution timeline:
the project dry run reports an already installed profile and the remaining host
step. The failed proof remains visible.

| Record | Evidence class | Retained observation |
| --- | --- | --- |
| [dry-run.txt](dry-run.txt) | Local integration: real Codex home inspected; private-copy rehearsal | Profile initially absent; one active Codex process warned; native writer rehearsal passed. No real-home apply in this command. |
| [dry-run-project.txt](dry-run-project.txt) | Local integration: real Codex home and project configuration inspected; private-copy rehearsal | Profile already installed; three project tables identified for the manual host step; rehearsal passed. |
| [apply.txt](apply.txt) | Local integration on the real Codex home | No Codex processes; config/AGENTS read back and stack-worker profile installed. Private recovery record retained by the coordinator. |
| [prove.txt](prove.txt) | Local integration on the real Codex home | 6 pass, 1 fail: project context-mode still used the plugin launcher and checkout-bound directory. |
| [prove2.txt](prove2.txt) | Local integration on the real Codex home after the host step | 7 pass, 0 fail; both binding read-backs use the user launcher, no fixed cwd, one server registration. |
| [prove-live.txt](prove-live.txt) | Local integration on the real Codex home; live provider execution for five worker calls | 12 pass, 0 fail: two worker directories, profile approval and its expected-refusal control, and the worker's RTK/exact-blob behavior. |

`prove-live.txt` is the five-call run made before the installed-skill check was
added to `tools/adoption/prove_codex_lane.py`. Its 12/12 total is historical and
does **not** prove that new check. **2026-09-27 check-count correction:** the
updated live worker suite always reports the thirteenth `skill-worker` check;
it fails without an installed SKILL.md (or with an invalid `--skill-file`). A
valid installed skill adds the sixth call. Its result records
`context-mode ctx_execute_file` or `shell (rtk cat)` and compares actual tool
output with the selected file's real first line. A project-boundary refusal
alone does not pass the check. Synthetic tests are in
[`tests/test_codex_worker_skill.py`](../../../tests/test_codex_worker_skill.py).

## Retention and sanitization

Home prefixes are rendered as `~`. Private scratch directories, run-directory
suffixes, process IDs, private file hashes and config version tokens are replaced
with descriptive placeholders. The public pinned launcher hash is retained.
The scratch worker directory suffixes are preserved to show that the two
observations differ. No account/connection identifiers, UUIDs, email addresses,
bearer values, request bodies or credential stores are included.

These text outputs retain the integration runner's returned observations and
success/failure summaries. They do not contain the workers' full native JSONL
events, complete model outputs, full invocation records or outer shell exit
statuses. The runner declares `host_acceptance: false` under the
[acceptance policy](../../../docs/acceptance-evidence-policy.md). Retaining its
text output does not upgrade that class or accept another host. The RTK blob
comparison uses a synthetic repository payload with actual local execution;
its bytes are not model-task quality evidence. No unchanged upstream test suite
was run for this record, and no token-saving measurement is claimed.

## SOTA sources

- [openai/codex `rust-v0.157.1` release](https://github.com/openai/codex/releases/tag/rust-v0.157.1),
  installed as codex-cli 0.157.1 in the supplied outputs;
  [profile layering](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/config/src/loader/mod.rs#L286-L334),
  [layer precedence](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/config/src/config_layer_source.rs),
  [native exec events](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/exec/src/exec_events.rs),
  and the [app-server config API](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/app-server/README.md).
- [mksglu/context-mode `v1.0.169`, containment implementation](https://github.com/mksglu/context-mode/blob/v1.0.169/src/security.ts#L766)
  (`evaluateProjectContainment`, compiled to `security.js`) and
  [project-boundary guard](https://github.com/mksglu/context-mode/blob/v1.0.169/src/server.ts#L1165-L1200),
  invoked by the [file-read handler](https://github.com/mksglu/context-mode/blob/v1.0.169/src/server.ts#L2114-L2123),
  following [issue #852](https://github.com/mksglu/context-mode/issues/852).
  A skill outside the worker's project may be refused by this MCP tool; the
  permitted native shell read requires no change to that boundary.
- [rtk-ai/rtk `v0.50.0` instructions](https://github.com/rtk-ai/rtk/blob/v0.50.0/hooks/rtk-awareness-full.md)
  and the existing [lane decision](../../../docs/decisions/2026-09-26-codex-worker-lane.md)
  for the RTK exactness exceptions and supported install/apply procedure.
- [Official Codex skill locations](https://developers.openai.com/codex/skills/),
  read 2026-09-27: user skills under `~/.agents/skills`; the shell recognizer
  reuses [CPython's shlex POSIX parsing](https://docs.python.org/3.12/library/shlex.html#improved-compatibility-with-shells).

The separate [tiering receipt](../gpt6-family-tiering-20260927/README.md) records
A0 (`gpt-6-astra`, max) with 25 successful calls on the same date. Its live
provider execution is a different experiment from the five worker-lane calls.

**2026-09-27 source-label erratum:** `server.ts` L1165-1200 defines the
project-boundary guard; the file-read handler calls it at L2114-2123. Both
ranges were checked at `v1.0.169` during review repair.
