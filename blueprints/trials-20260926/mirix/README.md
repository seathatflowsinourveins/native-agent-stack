# MIRIX trial (2026-09-26)

**Measured result:** no memory was persisted through MIRIX's documented
add/retrieve path against this host's local OpenAI-compatible endpoints, at the
v0.1.6 release tag or at `main@8cb06a62`. Six upstream defects (F1-F6) account
for every add/retrieve failure observed; two documentation defects (F7, F8)
were also found. The layer decision is not made here (see [Verdict](#verdict)).

Machine-readable record: [`results-20260926.json`](results-20260926.json).
Every retained file, with its sha256, evidence class and sanitization, is listed
in [`retained-outputs.json`](retained-outputs.json). Pinned source lines behind
each finding are in [`source-review.json`](source-review.json). The batch-level
rules (evidence classes, why there are no host receipts, host cleanup) are in
[`../README.md`](../README.md).

## What it is

[MIRIX](https://github.com/Mirix-AI/MIRIX) (Apache-2.0,
[arXiv:2507.07957](https://arxiv.org/abs/2507.07957)) is a multi-agent memory
system: six memory stores (core, episodic, semantic, procedural, resource,
knowledge vault), each written by an LLM-driven sub-agent under a meta agent,
behind a FastAPI REST server on PostgreSQL + pgvector with a thin REST client.

## Pins

| Pin | Value | Verified by |
| --- | --- | --- |
| Release tag (primary) | `v0.1.6` = `0f3fbdb5e085ccceb6254e2a4a128a8957dac55a` | fresh tag clone, `git rev-parse` |
| `main` (secondary, only to test whether main fixes v0.1.6) | `8cb06a62bbb7c478beb33dd4f2815696a72df482` (still the main tip on 2026-09-26) | fetch by commit id |
| PyPI `mirix` 0.1.7 (REST client only; no `v0.1.7` tag exists) | wheel `ead9e0ec…af45`, sdist `d6650d24…b5a5` | PyPI-reported and downloaded sha256 |

All three rows come from
[`../provenance/run-20260926T045856Z/verify-pins.log`](../provenance/run-20260926T045856Z/verify-pins.log).
"REST client only" comes from the listing of that wheel, read from the first
pass's download before its tree was deleted
([wheel contents](native-outputs/pypi-mirix-0.1.7-wheel-contents.txt)). Its
summary is "Mirix Client - Lightweight Python client for Mirix server". Its 62
files hold only the `client`, `helpers` and `schemas` subpackages, with no
server, agent, services or ORM module.

## Setup

- Chat: host llama.cpp on `127.0.0.1:18232` (`qwen3.8-27b-local`), embeddings:
  host vLLM on `127.0.0.1:18231` (`nvidia/Nemotron-3-Embed-1B-BF16`), both
  read-only inference, configured through MIRIX's documented
  `model_endpoint_type: "openai"` with a custom endpoint
  ([configs](local-integration/), keys redacted).
- Database: a private PostgreSQL 16.2 + pgvector 0.6.2 from the `pgserver`
  PyPI package (no Docker, no sudo), on a Unix socket in the session runtime
  directory. The versions were read from the v0.1.6 venv before its deletion
  ([versions](native-outputs/pgserver-bundled-versions.txt)): pgserver 0.1.4's
  bundled `postgres --version`, the cluster's `PG_VERSION`, and the `vector`
  extension's `default_version`. The `pgvector` 0.5.0 in the venv is only the
  Python client binding.
- v0.1.6: `git clone --branch v0.1.6 --depth 1`, `uv venv` (Python 3.11.16),
  `uv pip install -r requirements.txt`, `uv pip install pgserver`,
  `uv pip install -e . --no-deps`; that console output was not retained. main:
  a second venv ([install log](native-outputs/install-main-8cb06a62.log)).
- Servers: `python scripts/start_server.py --port 18531` (v0.1.6),
  `--port 18000` (v0.1.6, test re-run), `--port 18533` (main, which needs a
  `postgresql+asyncpg://` URI).

The first pass kept all of this in the session scratch directory
`<scratch>/trial-mirix`. Its recorder reached the same directory through the
alias symlink `/tmp/nas-mirix-trial` so that receipt commands would not carry the
session id; that is why the withdrawn receipts name `/tmp/nas-mirix-trial` while
the first pass's README named the scratch directory. Both paths are the same
files. The port's cleanup removed the alias, and the first polish pass deleted
the scratch directory after capturing the facts above from it
([`../host-cleanup-20260926/first-pass-scratch-trees/`](../host-cleanup-20260926/first-pass-scratch-trees/)).
Nothing cited here depends on either.

## Results

Times are UTC. "Local integration" rows ran our own thin wrapper or check around
the unmodified upstream client (sources in [`local-integration/`](local-integration/));
their pass/fail rules are ours, not upstream's.

| Check | Evidence class | Exit | Result | Retained |
| --- | --- | --- | --- | --- |
| Upstream suite at v0.1.6 (`python -m pytest -v`, as `tests/README.md` documents), fresh DB, no API key, no Redis | upstream test | 1 | 193 collected: **88 passed, 1 failed, 88 skipped, 16 errors**, 5 warnings. Failed: `test_queue.py::…::test_concurrent_enqueue` (`assert 57 == 100`). Skipped: gated on `GEMINI_API_KEY` or Redis. Errors: all 16 `test_search_all_users.py` tests, `api_key is required` | [log](native-outputs/pytest-v0.1.6-full.log) |
| Same file again with `MIRIX_API_KEY`/`MIRIX_API_URL` set and a fresh server | upstream test | 1 | 16 errors: `initialize_meta_agent() got an unexpected keyword argument 'config_path'` (**F6**) | [log](native-outputs/pytest-v0.1.6-test_search_all_users-rerun.log) |
| README Option B quick start, v0.1.6, embeddings on | local integration | 1 | `initialize_meta_agent` → HTTP 400, `text-embedding-ada-002 does not exist` (**F2**) | [log](native-outputs/quickstart-v0.1.6-attempt1-embeddings-on.log) |
| Same, `build_embeddings_for_memory: false` | local integration | 0 (HTTP only) | add 200 "queued", retrieve 200 with all counts 0; server side every attempt fails on **F1** until "Retries exhausted" (01:37:15Z → 01:47:42Z); nothing written | [client](native-outputs/quickstart-v0.1.6-attempt2-bm25.log), [server](native-outputs/server-v0.1.6-port18531.log) |
| Bounded check, v0.1.6 (add, then poll retrieve ≤ 280 s; pass only if a count > 0) | local integration | 1 | first poll hit the client's 60 s read timeout; server: **F1** at 02:08Z, then a 503 "Loading model" final error when the host llama.cpp service restarted at 02:15Z | [log](native-outputs/check-v0.1.6-bounded-poll.log) |
| main, README call shape (no `await`) | local integration | not retained | every call returned an un-awaited coroutine; no request made (**F3**) | [log](native-outputs/quickstart-main-run1-sync-calls.log) |
| main, README content shape (list of `{type: text}` parts) | local integration | 1 | `POST /memory/add` → 500, `can only concatenate str (not "dict") to str` (**F5**) | [log](native-outputs/quickstart-main-run2-list-content.log) |
| main, plain-string content | local integration | 0 (HTTP only) | topic extracted (01:53:22Z), `trigger_memory_update` for episodic + semantic (01:56:13Z); `semantic_memory_insert` fails with `NotFoundError … text-embedding-ada-002` (02:03:47Z, **F2**). The recorder's rerun (03:07Z) also shows `episodic_memory_insert` failing the same way (03:15Z, 03:18Z). Nothing persisted | [client](native-outputs/quickstart-main-run3-string-content.log), [server](native-outputs/server-main-8cb06a62-port18533.log) |
| PyPI install instruction | registry observation | 0 | `mirix` 0.1.7 says `pip install mirix-client`; that project has no files (**F7**) | [check](native-outputs/pypi-mirix-client-check.txt) |

### The two v0.1.6 attempts the first pass skipped

The first pass's recorder recorded a receipt only when every dry-run command
exited 0, and silently skipped two v0.1.6 use specs: the quickstart plus bounded
check (dry-run exits 0 and 1) and the pinned-tag pytest (exit 1). Both are kept in
[`skipped-receipt-specs.json`](skipped-receipt-specs.json) with their commands,
claims and the retained outputs of the same commands at the same pin. The
skipped quickstart dry run's own server trace is in the v0.1.6 server log: add at
03:18Z, **F1** at every attempt, "Retries exhausted" at 03:35Z. Its console
output was not written to a file.

## Findings

Each finding is backed by retained native output and by pinned source lines
(`source-review.json#<id>`).

1. **F1 (v0.1.6; fixed on main).** `PromptTokensDetails.audio_tokens` is a
   non-Optional `int`; llama.cpp sends `usage.prompt_tokens_details.audio_tokens:
   null`, so every local completion fails validation. main's `UsageStatistics`
   has no such nested field.
2. **F2 (both pins).** `embedding_model()` builds llama_index's
   `OpenAIEmbedding` without `config.embedding_model`, so any
   OpenAI-compatible embedding server is asked for `text-embedding-ada-002`.
   `build_embeddings_for_memory: false` skips the init-time check but not the
   semantic and episodic memory inserts.
3. **F3 (main).** The README quick start calls the async client methods without
   `await`. `samples/run_client.py` at main awaits them; the first pass wrongly
   listed it as affected.
4. **F4 (main).** `samples/generate_demo_api_key.py` calls async manager
   methods without `await`. The as-shipped run's output was not retained, so
   this rests on source review; the awaited copy
   ([`gen_key_main.py`](local-integration/gen_key_main.py)) issued the key the
   main runs used.
5. **F5 (main; not v0.1.6).** `add_memory` concatenates a string with each dict
   part of list content, so the README's own message shape returns 500. v0.1.6
   extends list content unchanged, so this is a regression after the tag.
6. **F6 (v0.1.6).** `tests/test_search_all_users.py` passes `config_path=` to a
   client method that has no such parameter in the same release.
7. **F7 (PyPI 0.1.7).** The description's `pip install mirix-client` installs
   nothing.
8. **F8 (v0.1.6).** `tests/README.md` describes two test files (18 + 4 tests);
   the tag ships 14 `test_*.py` files and pytest collects 193 tests.

## Blocked and not evaluated

- **Upstream LongMemEval-S / MemoryAgentBench harness**
  (`evals/mab/run_mab_longmem_eval.sh`): main only; its documented prerequisite
  is an OpenAI API key and its only profile targets `api.openai.com` for chat,
  topic extraction and embeddings with `build_embeddings_for_memory: true`. No
  cloud key is used on this host, and against local endpoints its memory writes
  would hit F2, which the main runs above already show. Not run.
- Not evaluated: cloud backends, the full main-branch suite (the first pass's
  `--collect-only` count was not retained), Redis tests, the desktop-agent
  branch.

## Withdrawn receipts

The first pass recorded two host receipts
([`withdrawn-host-receipts/`](withdrawn-host-receipts/), byte-for-byte). They are
not in `evidence/hosts/` because `scripts/host_receipts.py validate` rejects a
`component_id` that is neither a `manifests/stack.json` component nor a
landscape winner (see [`../README.md`](../README.md#why-there-are-no-host-receipts)).
The use receipt was also wrong on its own terms: it recorded `result: pass` from
the HTTP-level exit code of a self-written wrapper while its claim says the
memory write failed.

## Corrections to the first pass

- The full suite's 16 errors are the missing API key; the `config_path`
  TypeError (F6) appears once the key is set. The first pass reported F6 for the
  full run.
- F3 does not apply to `samples/run_client.py`; F5 is main-only (verified at
  v0.1.6); the open question whether `episodic_memory_insert` needs an
  embedding is answered by the retained server log: it fails on F2 too.
- The first pass's results file carried a raw internal agent id; retained copies
  replace UUID-shaped ids with `<uuid>`.
- The first pass left its three MIRIX servers running (ports 18531, 18000 and
  18533 on all interfaces); they were stopped by the cleanup. Two things are
  still on the host: `~/.mirix`, which MIRIX created (`mirix_dir` default), and
  pgserver's runtime directory `/run/user/<uid>/python_PostgresServer`. The
  `trial-mirix` scratch tree, including its 85 MB PostgreSQL data directory, was
  deleted by the first polish pass. See [`../README.md`](../README.md#host-state).
- "PostgreSQL 16.2 + pgvector 0.6.2" and "mirix 0.1.7 is a REST client only"
  had no retained output behind them. Both now cite captures made before the
  trees were deleted (Setup, Pins). The first pass's "753 of 899" main-suite
  collection count had none either and is no longer stated.

## Verdict

- **Measured:** no persisted memory through the documented path against local
  endpoints at either pin. v0.1.6: F1 fails every local completion; F2 fails
  initialization with embeddings on. main: F1 is fixed and the local model
  produced a well-formed topic, tool call and memory object, but both inserts fail
  on F2, and the README quick start also hits F3 and F5. The tag's own suite: 88
  passed, 1 failed, 88 skipped, 16 errors (F6 once the API key is set).
- **Blockers:** F1 (v0.1.6), F2 (both pins), F3 and F5 (main quick start); the
  upstream evaluation harness requires a cloud key and exists only on main.
- **Layer decision:** not made here. The foundation durable-memory layer is
  re-recorded by its own verdict wave
  (`tools/sota-convergence/record_verdicts.py`); this trial supplies the measured
  results and blockers above.
- **Re-trial trigger:** a MIRIX release that forwards `embedding_model` for
  OpenAI-compatible embedding endpoints and parses a null `audio_tokens`; then
  rerun the local-endpoint add/retrieve check and the upstream LongMemEval-S
  harness against local endpoints.
