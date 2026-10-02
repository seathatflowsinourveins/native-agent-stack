# Preregistration: the local model server's first gate (pass or fail)

Written before the first model call. Time stamp (`date -u`): 2026-10-01T23:12:24Z

## Question

One critic defined the first gate, verbatim:

> First gate, pass or fail: Ollama replaces llama.cpp if the Codex MCP tool call fails on llama-server (its log shows
> 'unsupported Responses tool type 'namespace' skipped') and succeeds on Ollama. Source at the pins checked predicts that
> result unless llama.cpp merges namespace support (PR #23235) first.

This file fixes how that gate is run on this workstation: the same fixed Codex task, which must call one tool from one
MCP server, against (A) llama.cpp's `llama-server` and (B) Ollama, both serving the same GGUF file. Nothing beyond the
gate is measured (no speed, no quality).

Evidence class: local integration check on the current workstation (WSL2), not on the new machine. The arm wrappers
(`gate_env.sh`, `gate_setup.sh`, `gate_run.sh`), the scoring script (`gate_score.py`) and the prompt are local. The two
servers, the Codex client and the MCP server are unchanged upstream releases.

## Pins

| Part | Version | Commit | Artifact and sha256 |
| --- | --- | --- | --- |
| llama.cpp | release `v0.5.0` (GitHub `releases/latest`, published 2026-09-23T20:50:06Z); its asset `nightly-tag.txt` names build tag `b11146` | `7fe450e19305b828c199d602c23a8337aaa1f03b` (both tags) | `llama-b11146-bin-ubuntu-cuda-12.8-x64.tar.gz` `c2ab9e19838513ff69d1af8d999ad717dd3c7ee4714ac04c7ed5ab9077c50e4e`; `cudart-llama-b11146-bin-ubuntu-cuda-12.8-x64.tar.gz` `1466daea60aad1144819e151b2bae19d54556cf1da6c129c4f55a5ded2637c25`; extracted `llama-server` `376626f953efd7bbf16dee112747196d2b1de26717bcd1d37e203340dc5c043c` |
| Ollama | release `v0.35.0` (published 2026-09-28T21:23:22Z) | `cc4069396f3ad2c370c53eed2e4a42ac13adab84` | `ollama-linux-amd64.tar.zst` `1c114a6b220c5efca2ef2b1e5f01d1e535e26f6cd6d1678c8489325d2835e525` (equals the release's `sha256sum.txt`); extracted `bin/ollama` `0b0650a962dda61ec0598141ea11e3b688d225e926c9c00bc2c299d0ed34c4f8` |
| Codex | `codex-cli 0.159.3` (tag `rust-v0.159.3`) | `01fc69f4026735edfdf6789820549727a4867b11` | the workstation's installed standalone binary (`x86_64-unknown-linux-musl`) `8bf204b36a2f6dd0dab73aa2f639892e67ef9ac8befccb4a05b1496ebf25c479`, called directly, not through the workstation's telemetry launcher script |
| Model | `Qwen/Qwen3-8B-GGUF`, file `Qwen3-8B-Q4_K_M.gguf` (4-bit, 8.2B parameters, 5,027,783,488 bytes) | repository revision `7c41481f57cb95916b40956ab2f0b139b296d974` | `https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/7c41481f57cb95916b40956ab2f0b139b296d974/Qwen3-8B-Q4_K_M.gguf` `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785` (equals the repository's LFS object id) |
| MCP server | `mcp-server-time` 2026.8.18 (reference time server, PyPI), `mcp` SDK 1.30.0, Python 3.13.15 virtual environment | not applicable | wheel `mcp_server_time-2026.8.18-py3-none-any.whl` `1407583af42dc0163909d855c9ef20114a12b4981c3975033721a7906cdd212a`; resolved packages in `setup/mcp-venv-freeze.txt` |
| Ollama template and parameters | library `qwen3:8b` registry layers | not applicable | template `sha256:ae370d884f108d16e7cc8fd5259ebc5773a0afa6e078b11f4ed7e39a27e0dfc4`, parameters `sha256:cff3f395ef3756ab63e58b0ad1b32bb6f802905cae1472e6a12034e4246fbbdb` |

The `llama-server` already on this workstation's PATH reports `version: 0.5.0-dev (build 11146, commit 7fe450e19)` and has
the same sha256 as the freshly extracted binary: it is the same build as the latest release, not an older one. The gate
uses the fresh copy under the state directory. Newer llama.cpp builds exist only as prereleases (`b11327`, published
2026-10-01T20:55:49Z, `prerelease: true`); they are not releases and are not run. llama.cpp PR #23235 ("server : implement
namespaced tools in responses API") is open and unmerged (last update 2026-05-17).

The Ollama tarball was unpacked without `sudo` into the state directory. `zstd` is not installed on this workstation,
so the archive was streamed through the Python `zstandard` 0.25.0 package into `tar x`.

## Serving settings (same on both arms)

- The same file `Qwen3-8B-Q4_K_M.gguf` on both servers. Model name `gate-qwen3-8b` on both.
- Context 32768 tokens on both (the model's own limit is 40960). One slot. Ollama's Codex page asks for at least 64k;
  this model cannot provide that, which is a recorded limitation.
- Sampling: temperature 0.6, top_k 20, top_p 0.95, repeat_penalty 1 on both (the library `qwen3:8b` parameters).
- CPU only on both (`CUDA_VISIBLE_DEVICES=-1`; llama-server also gets `--device none -ngl 0`). Reason, observed during
  setup: with 16 GiB reported free by `nvidia-smi`, llama-server could not allocate more than about 4.5 GiB on the GPU
  (`cudaMalloc failed: out of memory` on the 4455 MiB weight buffer at 32k context, and on the 576 MiB KV buffer at 4k
  context, three attempts). Other services use the GPU and are not stopped. The gate is a function check, so the device
  does not enter the pass rule.
- llama-server: `llama-server -m <STATE>/models/Qwen3-8B-Q4_K_M.gguf --alias gate-qwen3-8b --host 127.0.0.1 --port 20231
  -c 32768 -np 1 --device none -ngl 0 --jinja --temp 0.6 --top-k 20 --top-p 0.95 --repeat-penalty 1.0 --verbose`
- Ollama: `ollama serve` with `OLLAMA_HOST=127.0.0.1:20232 OLLAMA_MODELS=<STATE>/ollama-models OLLAMA_NO_CLOUD=1
  OLLAMA_CONTEXT_LENGTH=32768 OLLAMA_NUM_PARALLEL=1 OLLAMA_DEBUG=1`; the model was imported with
  `ollama create gate-qwen3-8b -f Modelfile` (`Modelfile` in this folder: `FROM` the same GGUF, the library template,
  the library parameters, `num_ctx 32768`). The created template layer has the library digest `ae370d88…`.
- Every process runs under `env -i` with `HOME=<STATE>/scratch-home`, `CODEX_HOME=<STATE>/scratch-home/.codex`,
  `TZ=UTC`, `PATH=<STATE>/bin:/usr/bin:/bin`. Loopback only, ports 20231 and 20232.

## Codex configuration (same client settings on both arms)

- `codex-config/config.toml.tmpl` (shared base config): `approval_policy = "never"`, `sandbox_mode = "read-only"`,
  `web_search = "disabled"`, analytics off, and the one MCP server `time` (stdio, `mcp-server-time --local-timezone UTC`)
  with `enabled_tools = ["get_current_time"]` and `default_tools_approval_mode = "approve"`. The approval mode is needed
  in a non-interactive run: at this Codex tag an MCP call that needs approval is denied when the approval policy is
  `never`.
- Arm B profile `codex-config/ollama-launch.config.toml` and model catalog `codex-config/model.json`: written by
  upstream's launcher, `ollama launch codex --model gate-qwen3-8b --yes -- --version` (it writes both files, then runs
  `codex ... --version`, no model call). The launcher resolves the Codex directory from `HOME`, which is why `HOME`
  points into the state directory.
- Arm A profile `codex-config/llamacpp-gate.config.toml`: the launcher's profile with only the provider id, the provider
  name and the base URL changed (`http://127.0.0.1:20231/v1/`, `wire_api = "responses"`). Both arms use the same model
  catalog, so Codex sends the same instructions and tool list to both servers.
- Command, per run: `codex exec --profile <llamacpp-gate|ollama-launch> --json --skip-git-repo-check -C <STATE>/work
  -o last-message.txt "<prompt>"`, stdin from `/dev/null`, with the dummy `OPENAI_API_KEY=ollama` that the launcher
  itself sets (a literal from upstream's source, not a credential), under a 300 second wall limit.

## Task

One fixed prompt:

> Use the MCP tool get_current_time from the MCP server named time, with the argument timezone set to "UTC". Do not run any shell command. After the tool returns, reply with exactly the datetime value it returned and nothing else.

The tool is deterministic in behaviour (its result is fixed by its argument and the clock) and its value, a time stamp
with seconds, cannot be known to the model without the tool. The event log carries the returned value, so each run is
checked against its own tool result.

## Runs

1. One unscored warm-up per arm with the same command and prompt (`warmup-A`, then `warmup-B`). Its only purpose is to
   find faults of the local wrappers (a server that does not start, a rejected config, an MCP server that does not
   start). A wrapper fault may be repaired and is then listed as a deviation. The prompt, the pass rule, the pins, the
   model and the serving settings do not change after this file is written.
2. Three scored runs per arm, alternating: `A1 B1 A2 B2 A3 B3` (A = llama-server, B = Ollama). One server process per
   run: start, wait for `/health` (A) or `/api/version` (B), run Codex once, stop the server. Only one server is up at
   a time. Every started PID is recorded in `pids.tsv`.

## Pass rule (frozen)

A run passes when both hold in its `codex exec --json` event log:

1. there is an `item.completed` event whose item has `type = mcp_tool_call`, `server = time`,
   `tool = get_current_time`, `status = completed`, no error, and a result that carries a `datetime` string;
2. the text of the last `agent_message` item contains that `datetime` string as a substring.

An arm passes the gate when all three of its scored runs pass. `gate_score.py` applies this rule; the Codex exit code
is recorded but is not part of it. Gate outcome, in the critic's terms: "Ollama replaces llama.cpp" holds when arm A
fails and arm B passes. Any other combination is reported as it is.

Each failed run gets one reason: `timeout` (wall limit), `codex_or_server_error` (an error event and no MCP call),
`tool_not_called` (no MCP call item), `approval_denied`, `tool_call_failed`, `no_final_answer`, `answer_mismatch`
(call completed, final answer lacks the value). Separately, for every run the server log lines about tools are
recorded: for llama-server whether it logged `unsupported Responses tool type '...' skipped`, and for both servers what
the retained request shows about the tool types Codex sent.

## Setup observations before this file (no model call was made)

Requests made so far: Ollama `/api/version`, `/api/create`, `/api/show`, `/api/tags`, `/api/status` and the launcher's
model listing; llama-server `/health`, `/v1/models`, `/props`. No completion, chat or Responses request.

- GPU allocation failed as described above; both arms were switched to CPU before any run.
- `ollama launch codex --config --model gate-qwen3-8b --yes` wrote the profile and catalog and then started the Codex
  terminal UI, which exited with `stdin is not a terminal`. The `-- --version` form above was used instead.
- The first wrapper started servers through a shell function, so the recorded PID was a subshell. This was fixed
  before any run; one probe server left behind by it (PID 3225038, started by this work) was stopped.

## Upstream sources read

- `https://api.github.com/repos/ggml-org/llama.cpp/releases/latest`, `.../releases/tags/b11146`,
  `https://github.com/ggml-org/llama.cpp/releases/download/v0.5.0/nightly-tag.txt`: the release, its build tag, the
  Linux CUDA assets and their digests. `.../pulls/23235`: open, unmerged.
- llama.cpp at `7fe450e1`: `tools/server/server-chat.cpp:273-279` (a Responses tool whose type is not `function` is
  skipped with the warning quoted in the gate); `tools/server/README.md:1461` (`POST /v1/responses`);
  `llama-server --help` of the pinned binary (`--jinja` default enabled, `--alias`, `-np`, `--device`, `--verbose`).
- Ollama at `cc406939`: `docs/linux.mdx:13-25` (manual install from `ollama-linux-amd64.tar.zst`);
  `docs/integrations/codex.mdx` (`ollama launch codex`, `--config`, `codex --oss`, the profile-based setup, the 64k
  context note); `docs/faq.mdx:178` and `envconfig/config.go:237-238,332` (`OLLAMA_NO_CLOUD`: "Disable Ollama cloud
  features (remote inference and web search)"); `docs/api/openai-compatibility.mdx:318-347` (`/v1/responses`,
  stateless only); `openai/responses.go:490-499,894-920` (a `namespace` tool is expanded into its member functions);
  `cmd/launch/codex.go:38-80,177-188,211-239,690-760` (what the launcher writes and runs); `docs/gpu.mdx:45-46`
  (an invalid GPU id forces CPU).
- Codex at `01fc69f4`: `codex --help` and `codex exec --help` of 0.159.3 (`--oss`, `--local-provider`, `-p/--profile`
  layering `$CODEX_HOME/<name>.config.toml`, `--json`, `--skip-git-repo-check`);
  `codex-rs/model-provider-info/src/lib.rs:732-739` (`CODEX_OSS_PORT`, `CODEX_OSS_BASE_URL` for `--oss`);
  `codex-rs/config/src/mcp_types.rs:27-34,282-298` (MCP server keys and approval modes);
  `codex-rs/core/src/mcp_tool_call.rs:1486-1540,1620-1626,2457-2488` and `codex-rs/codex-mcp/src/mcp/mod.rs:91-110`
  (MCP approval); `codex-rs/exec/src/exec_events.rs:138-140,203-208,286-294` (event shapes);
  `codex-rs/tools/src/tool_spec.rs:26,95-137` (the `namespace` tool spec). The config keys were read from the source
  at the tag rather than from the hosted config reference.
- `https://huggingface.co/api/models/Qwen/Qwen3-8B-GGUF` and `.../tree/7c41481f57cb95916b40956ab2f0b139b296d974`
  (public, not gated, LFS sha256); `https://registry.ollama.ai/v2/library/qwen3/manifests/8b` (template and parameter
  layers); `https://pypi.org/pypi/mcp-server-time/json` (version and wheel digest); the installed
  `mcp_server_time/server.py:145-146,173-174` (both tools declare `readOnlyHint=True`).

## Prediction on record

The critic's prediction: arm A fails with the `namespace` warning in the llama-server log, arm B passes.
