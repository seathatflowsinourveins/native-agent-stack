# LongMemEval-S retrieval harness: the v4 driver (D2h, C4, the A16 arms) for the VelaNext rerun

This directory holds, byte-exact, the LongMemEval-S harness v4 driver and its supporting pins,
protocol and lock files, committed for host request
[#274](https://github.com/seathatflowsinourveins/native-agent-stack/issues/274) and
[#384](https://github.com/seathatflowsinourveins/native-agent-stack/issues/384), so the
workstation's amendment A17 rerun has this code in Git rather than only in the private
agent-ecosystem repository. It follows the pattern of #380 (the Mac's v3 harness, merged to
`main` since this PR opened): the same per-file provenance table, the same non-portable
labelling, and the same "copied files are frozen" rule.

- **Source.** The private `agent-ecosystem` repository, branch
  `claude/longmemeval-velanext-lane-20260925`, commit `576689a`
  (`576689af6f5e5f4d85013c7c4bed3b8f7c92f57d`; re-fetched and confirmed to still resolve there
  before this commit). Every file below comes from `evals/longmemeval/<path>` at that commit,
  extracted with `git show 576689a:evals/longmemeval/<path>`, which is byte-exact by
  construction; the table gives each file's blob id. For the six files this directory stores as
  `<name>.frozen` (below), `<path>` in that command is the plain name without `.frozen`.
- **Nothing was run for this commit.** No arm, model or embedding server ran. This is a code
  transfer only.
- **The copied files are frozen.** Every file in `SHA256SUMS` except `README.md` and `.gitignore`
  is a record; both of those were written for this commit, not transferred (see below). A fix or
  a later revision lands as a new file or a new PR; an edit here breaks the pinned hashes this
  commit is accepted against.
- **v4 is the harness A15.2 names**, distinct from the v3 harness #380 carries (`lme_harness.py`
  there; `reference/lme_harness_v3.py` here, byte-identical to it, sha256
  `b59ee6f5ada7392e4c250ad54dd1ec75e2e30921bca8ae4265807f587716f751`). v4 keeps v3's logic for
  every existing arm and adds environment-configurable paths (defaults are the Mac layout,
  unchanged), the A15 arms, a document prefix for the dense baseline, a configurable dense batch
  size, an agentmemory slot pool shared across processes, and the A16 memory-system arms and
  pooled-store mode.

## Shared-host warning

Read before running anything here. Findings below come from reading the actual teardown code at
576689a, not from its docstrings.

- **`reference/lme_harness_v3.py` is unchanged from v3 and keeps v3's behavior**, which #380
  already warns about: it sends `SIGKILL` to *every* process listening on a slot's ports, before
  the slot starts and at its teardown, with no ownership check. Each slot has a REST port at
  `3611 + 100 × slot`, the stream port one above it and the engine port `46023` above that. Do not
  run it where anything else uses those ports.
- **`lme_harness.py` (v4) matches process names; it does not check ownership.** (Corrected after
  the GPT-6 review at `97697b81`, which reproduced all three cases below with inert probes; this
  README previously said the empty-command-line case was the only gap, which understated it.)
  `_ours()` (`lme_harness.py:698-701`) treats a foreign PID as "ours" to kill whenever its command
  line merely **contains** the substring `agentmemory` anywhere, or contains the configured `iii`
  binary's path, or its argv[0] basename equals the `iii` binary's name — a substring match, not a
  check that the process is this run's own engine or worker. `am_teardown()`
  (`lme_harness.py:730-756`) also treats an **empty** `ps -o command=` result for a foreign PID
  (`:749`; a race where it exited between the port scan and the `ps` call, or a permission failure
  reading another user's process) as "ours" and kills it. And `am_start()`
  (`lme_harness.py:797-800`) calls `am_teardown(None, ports)` **before it has started anything of
  its own**, solely to clear a slot's ports for its own use — so on that first call alone, whatever
  is already listening on the slot's ports gets SIGKILLed the moment it matches `_ours()` or `ps`
  cannot read it, with nothing yet started that could be "owned." `mp_kill_mines()` (MemPalace, M2,
  `lme_harness.py:1149-1154`) has the same shape of gap: `mp_mine_pids()` (`:1045-1056`) keeps a PID
  only when `_pid_alive()` (`:1035-1042`, `os.kill(pid, 0)`; a `PermissionError` also counts as
  alive) succeeds, with no check that the live process is actually the one that wrote that pid
  file, and `mp_kill_mines()` then calls `os.killpg(pid, signal.SIGKILL)` — the whole process
  group, not just the pid — so a PID the OS reused for an unrelated process after the original
  miner exited receives it too.
- **`run_velanext.sh`'s `stop_bg`/`cleanup` is ownership-guarded on the single-process path, not
  on the process group it also signals.** It records each background service's pid, start-tick
  count, boot id and resolved executable when it starts it (`pid_record`), and `same_process()`
  re-checks all four (`owned_pid`) before `stop_bg` (`:145`) sends its first `TERM`/`KILL` pair. A
  pid file whose process no longer matches is dropped, unsignalled, as "stale". But in group mode
  — the CPU stream only, via `cleanup`'s `stop_bg cpu-stream group` (`:181`) — `stop_bg` also sends
  `kill -TERM -- "-$pid"` and, after a pause, `kill -9 -- "-$pid"` **unconditionally** (`:153-157`):
  no `same_process` check guards either group signal, precisely because the group leader may
  already have exited while its group lives on. It never scans a port for holders.
- **`setup_velanext.sh`'s Ollama readiness has no server-identity check either.** After
  backgrounding its own `ollama serve` (`:216-219`), the loop at `:220` only polls `curl -sf
  http://127.0.0.1:11438/api/version` until something answers; it never checks that the answer
  comes from the `oll_pid` process just started, and never checks `oll_pid` is even still alive. If
  that process fails to bind port 11438 (for example, another Ollama server already holds it), the
  curl succeeds against that other server instead and setup proceeds as if its own were ready.
  `:222-224` then runs `ollama pull` for every pinned model, and `:228-229` runs `ollama create` for
  every `ollama/*.Modelfile`, against `OLLAMA_HOST=127.0.0.1:11438` — whichever server actually
  answered — writing into a model store this run does not own. `:231`'s `kill "$oll_pid"` cleanup
  targets only the PID this run itself started, but only while that PID is still that process: in
  the failed-bind case just described, that process has already exited (and may already be
  reaped) well before `:231` or the `EXIT` trap at `:219` runs, so the signal can land on whatever
  the OS has since reused that PID for — the same PID-reuse gap this section attributes to
  `mp_kill_mines()` above.
- **Net effect: these are name and liveness checks, not ownership checks, and the gaps above are
  real.** They are still real improvements on v3's blind port sweep (which has no check at all, see
  above), and `run_velanext.sh`'s own `pid_record`/`same_process()` pairing is closer to a genuine
  ownership check than anything in `lme_harness.py`. But **do not run `lme_harness.py`,
  `run_velanext.sh`, `setup_velanext.sh` or `lane_tools.py`'s `v3-shim`/`fetch-hf --pin-main`
  subcommands on a shared host** — not "with one gap to watch for," but at all. The workstation's
  A17 runner is where isolated ports, isolated stores and identity-checked cleanup belong; this
  frozen code does not provide them.
- **`lane_tools.py`'s `v3-shim` and `fetch-hf --pin-main` mutate shared state outside this
  directory when run outside their wrapping scripts' lane-owned paths.** `v3-shim HOME`
  (`:804-816`) unlinks (`:812-813`) and replaces with symlinks
  `HOME/.local/share/agent-ecosystem/{src/LongMemEval, tools/ai-memory-2.5.0-19b6429/ai-memory,
  bench/agentmemory}` — the second of those is the Mac's production ai-memory binary path
  (`lme_harness.py:86,117`). `fetch-hf --pin-main` (`:110-120`) rewrites `refs/main` in whatever
  `HF_HUB_CACHE` is active, changing which snapshot every program that loads that model by name
  resolves. The shipped call paths are safe (`run_velanext.sh:479` passes a lane-owned `HOME`;
  `setup_velanext.sh:320` passes a lane-owned `HF_HOME`); the risk is calling either subcommand
  directly with the real home or the real `HF_HOME` active.
- **Two third-party vendor harnesses launch with the operator's full environment, not `env -i`.**
  `run_velanext.sh:563` (`./node_modules/.bin/tsx benchmark/longmemeval-bench.ts`, in the
  agentmemory checkout) and `:596-597` (`./target/release/ai-memory-eval retrieval --fetch`) run
  in a plain subshell. Every other third-party launch in this file uses `env -i` with an explicit
  allowlist (`:361-363` Ollama, `:383-388` Hindsight, `:608-609` MemPalace M1, `:712-716` AMB), and
  the harness starts its own servers under a cleaned environment too (`lme_harness.py:326-327`).
  Whether either vendor reads an ambient provider credential from the operator's shell was not
  checked here.

## Files

| File | sha256 | Bytes | Source blob | Role |
| --- | --- | --- | --- | --- |
| `lme_harness.py` | `b9bcb545d66e1dd296479ce1bee638980f66c28e534e9d289f57d68a0767c9e8` | 91,367 | `ff9e034d` | Harness v4: every v3 arm, the A15 arms, the A16 memory-system arms (D2h, M2, K1), the pooled-store mode |
| `lane_tools.py` | `954f00c96f74719188c9a2f4aa78c673df5348afc987d4e7f026cec89ff83fb9` | 59,483 | `a5ba4e7e` | VelaNext-lane tools: verification, gate and cache checks, row status, the K1 subset pick, LLM placement/RAM checks, fail-closed sanitizing, the receipt |
| `lme_summarize.py` | `3d2da1d71437f385108101771c5c570ae5a876a368e2299627b04b21dd3a8c49` | 60,498 | `40b371de` | Summarizer v4: A15.2's and A16's families, precedence, the `--confirmatory`/`--platform VelaNext` gate; imports `lme_harness.py` |
| `pins.json` | `bd9e865a6d73b7d60a0e11a26d51e8951f4a17e981244018d527e47c9ecbccf3` | 55,869 | `c7c13266` | Every version, commit, checksum and digest the lane installs or loads |
| `reference/lme_harness_v3.py` | `b59ee6f5ada7392e4c250ad54dd1ec75e2e30921bca8ae4265807f587716f751` | 31,991 | `7d54dae2` | Verbatim v3 harness (byte-identical to #380's `lme_harness.py`), kept for the A15.2 v4=v3 equivalence check |
| `rerank_stage.py` | `0500e0dc4c8d193fe28dc5fc7ac4b8f41a980ce9991f3ef389ec157b217ccea4` | 8,632 | `28b81215` | The exploratory **X arms**: a cross-encoder stage (ettin-400m, MemReranker-4B, Qwen3-Reranker-4B, KaLM-small) over an existing arm's top 50; imports `lme_harness.py` |
| `embed_server_st.py` | `7b5b5018fb0d24203e5c2fa8832ffa21baac91f89646df24a65a3c686f14028b` | 22,254 | `e4c6277d` | OpenAI-compatible embedding server over a model's reference implementation (BF16, dynamic batching, reference-output/invariance gates) |
| `gguf_embed_front.py` | `5fe0f4778f024162f0893f869b950401905d27c4dcfba9e19a2156e285acc7d1` | 11,179 | `619c10ad` | 4,096-token cap in front of llama.cpp's `llama-server` for the GGUF embedders; imports `embed_server_st.py` |
| `mteb_lmeb.py` | `f69910beb07dcd220c9c8eaa2088a1789a1a779ffadda213d79307c5a5abab0e` | 6,428 | `ae674e4b` | Upstream `mteb` on LMEB's LongMemEval task for every embedder, against the published leaderboard (first-line check; decides nothing) |
| `run_velanext.sh` | `1632c32f21e25b1ccdad8926d293400c13d267ddee65cc21f299afdd3f784c8b` | 53,849 | `d174a308` | The VelaNext run driver: gates, cpu/mteb/arms/a16/x/amb/pooled/report/collect/status/all |
| `setup_velanext.sh` | `024152e3f96425cbcc1e422ec4efcc184dff4bba3760f442d7af069b926289de` | 19,559 | `c64c7c5f` | Pinned, checksum-verified setup of the lane on VelaNext (WSL2 Ubuntu 24.04, RTX 4090) |
| `ollama/qwen3.5-9b-64k.Modelfile` | `60dbf344e5c374eabda289e7b379c1642bd523a2b4f4f387eb00ce021afcc318` | 476 | `de951c96` | C4's reranker-LLM Modelfile (`FROM qwen3.5:9b`, `num_ctx 65536`): `pins.json:146`'s role field, `run_velanext.sh:654`'s `llm_up qwen3.5-9b-64k aimem-qwen3-rerank`. Added per the GPT-6 review at `97697b81`; also used by the A15.2 F reranking arms and the pooled `aimem-qwen3-rerank` stage (`run_velanext.sh:664,727`) |
| `PREREGISTRATION.md` | `a9b1db335eee1ff99d1883e048bcd8e443ca2afee3505a34fd874dd1ef412d5b` | 37,885 | `8ac3d6f5` | The frozen protocol, amendments A1-A16.3 (verified against the required hash; see below) |
| `k1-subset.json` | `273b1f339a10a6b36dd6dd2235a4cd4e0bc5c6cab0b2cc93754232379addb97d` | 9,791 | `e8788fb1` | K1's preregistered 100-question subset (question ids and stratification metadata only, no question or session text) |
| `requirements/build.in` | `e39ff10a9d989e86461dd152f26fbfc39681f4fb43b68b2849ac87cf3a30cd06` | 333 | `a6dca7bd` | uv build-constraints source: setuptools/wheel for the one sdist-only package in the locks |
| `requirements/build.lock.txt.frozen` | `161a6bf821bf23084e34b2bf195628acfc7bb88f9a2270b27fa459cb9e8a75bc` | 763 | `878878df` | Hash-locked (`uv pip compile --generate-hashes`), Linux x86_64-manylinux_2_35, Python 3.11 |
| `requirements/embed.in` | `48bee7cfa04999d83dc15fc8e98937471e96974df6fb221918d65d1c255a7fa8` | 675 | `9a146767` | uv source for the GPU venv: `embed_server_st.py`, `rerank_stage.py`, `mteb_lmeb.py` |
| `requirements/embed.lock.txt.frozen` | `b96c2dab63348998dc19cc2960106d2ea77d672c3fdb3a245044db3f70f0a444` | 179,864 | `03535162` | Hash-locked, Linux x86_64-manylinux_2_28, Python 3.11 |
| `requirements/hindsight.in` | `622601e56eb38ffb6c6faf633c2ac96de8c7e481337c1ad785ea4516e6f46fbb` | 240 | `fd432719` | uv source: `hindsight-api==0.10.1` (K1, A16) |
| `requirements/hindsight.lock.txt.frozen` | `3cf398e5c82e77a294f433123e86920696804f50a48aad8ef7a6d66f22f98d8b` | 342,760 | `b7cab956` | Hash-locked, Linux x86_64-manylinux_2_35, Python 3.11 |
| `requirements/mempalace.in` | `851cecd084c0fb21f9ebb58c84b41ae3f1cbab1796ba5e7dda7fc7893431c7e2` | 310 | `7465dcc1` | uv source: `mempalace==3.10.0` (M1, M2, A16) |
| `requirements/mempalace.lock.txt.frozen` | `c6821b18d0d93cf55ab5d4be37771c82b1fbcabcffbafc624c8a098f1def42a5` | 193,706 | `be75fcef` | Hash-locked, Linux x86_64-manylinux_2_35, Python 3.11 |
| `requirements/official.in` | `87999b21c9784f431fee47df76678d59361ceec3af805c264e66e2781fc86a45` | 913 | `9c8428e6` | uv source: LongMemEval 9e0b455's own pins minus the vLLM/serving build packages the harness never imports |
| `requirements/official.lock.txt.frozen` | `a866d967cc74e00d59ef18696444078576de6e26197278eafe5570ef51c6d14c` | 103,671 | `f5789350` | Hash-locked, Linux x86_64-manylinux_2_28, Python 3.11; pins `nltk==3.9.1` |
| `vendor/agentmemory-repo-package-lock.json.frozen` | `93d3bc4cdf39abbd721ed905e6daa5adfad53f11391fbcbcaa8caf0b5caa306b` | 197,870 | `0e702367` | npm lockfile v3 of the agentmemory repository itself (`@agentmemory/agentmemory` 0.9.29, 381 packages) — distinct from the smaller install-prefix lock already frozen in #380 |

`README.md`, `.gitignore` and `SHA256SUMS` were written for this commit. `.gitignore` keeps a
run's `data`, `models`, `cache`, `logs`, `official-logs*`, `results*`, generated reports and
per-purpose venvs out of Git, the same paths `lme_harness.py`, `lme_summarize.py` and
`run_velanext.sh` resolve next to themselves or under `$LME_BENCH_ROOT`.

### Why the requirements locks are `.frozen`

`tests/test_osv_lockfile_coverage.py`'s `TRACKED` pattern matches any tracked file ending in
`.lock.txt`, regardless of its base name, so all five `requirements/*.lock.txt` files would need
an entry in `.github/osv-scanner-lockfiles.json` under their plain names — either scanned (and
`requirements/official.lock.txt` pins `nltk==3.9.1`, which this repository's `osv-scanner.toml`
carries a repo-wide, no-fix-available ignore for outside one named Lumibot lock, so a scanned copy
here would also fail `test_repo_wide_ignores_hide_nothing_outside_their_allowed_lock`), or excluded
(which the same test only allows for a reasoned test fixture, which these are not). This is the
same reasoning
[`docs/decisions/2026-09-25-longmemeval-frozen-npm-lock.md`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/main/docs/decisions/2026-09-25-longmemeval-frozen-npm-lock.md)
gives for the npm lock in #380, applied to these Python locks: they are records of exactly what
five isolated venvs installed for specific measured or to-be-measured runs, not floating
dependencies to keep current, so they are kept unchanged under names no dependency scanner reads.
The `.in` files keep their plain names and are **not** frozen, but not because they are unpinned
or unreadable in principle: scanning plain-named scratch copies with no explicit
`--lockfile=requirements.txt:<path>` override returns "No package sources found" — OSV-Scanner
does not auto-detect a bare `.in`/`.lock.txt` extension by name — and separately, `TRACKED`'s
`requirements[^/]*\.(?:txt|in)` alternative matches only a *basename* starting with
`requirements`; `requirements/official.in`'s basename is `official.in`, so it escapes that
alternative on a technicality of the regex, not because the file is clean. It is not unpinned
either: `requirements/official.in` alone pins 25 of its 28 lines (`Jinja2==3.1.3`, `nltk==3.9.1`,
`pillow==10.2.0`, `torch==2.3.1`, `transformers==4.43.3` among them); `embed.in` pins its whole
GPU-venv set (`torch`, `transformers`, `sentence-transformers`, `mteb`, `openai`, `httpx`,
`rank-bm25`); `mempalace.in` and `hindsight.in` pin the one package each names
(`mempalace==3.10.0`, `hindsight-api==0.10.1`); only `build.in` pins none (bare
`setuptools`/`wheel`, hash-locked solely in `build.lock.txt`). What each `.in` file pins is
exactly what its matching `.lock.txt.frozen` resolves, hashes and is scanned for below.

`requirements/build.in` and `.lock.txt` are the exception in spirit but not in mechanism: they pin
only `setuptools`/`wheel` as build constraints, not a runtime dependency set, but `build.lock.txt`
still ends in `.lock.txt` and is frozen for the same mechanical reason.

`vendor/agentmemory-repo-package-lock.json` does not itself match `TRACKED` (`package-lock.json`
in that pattern requires the whole file name, and `agentmemory-repo-package-lock.json` is not that
name), so this specific file would not trip that inventory test under its plain name. It is still
stored as `.frozen`, per this task's directive and the same decision record's rationale: it is an
npm-lockfile-format record of a fixed, historical dependency set (a different, larger lock than
the install-prefix pair #380 already freezes — the agentmemory repository's own 381-package lock,
not the 1-dependency install lock), not something meant to be reinstalled or rescanned as shipped.

**This PR adds a dated addendum to the 2026-09-25 decision record**, extending its scope to these
six `.frozen` files with the same kind of evidence the record used for the npm pair: a scan of
plainly named scratch copies, the advisory list, and a discriminating control against the
`.frozen` names (`osv-scanner scan source --config .github/osv-scanner.toml --no-resolve` over
`.frozen`-named copies: "No package sources found", exit 128, same as the original record). #380
has merged, so the record is on `main`: see [the 2026-09-27
addendum](https://github.com/seathatflowsinourveins/native-agent-stack/blob/main/docs/decisions/2026-09-25-longmemeval-frozen-npm-lock.md#addendum-2026-09-27-extending-scope-to-the-longmemeval-v4-drivers-six-locks)
for the full counts. In short: `official.lock.txt` alone carries 114 unique advisories across 9
of its 64 packages (concentrated in `nltk`, `pillow`, `torch` and `transformers`);
`mempalace.lock.txt`'s `chromadb` 1.5.9 carries 4, including a pre-authentication code-injection
advisory; `embed.lock.txt` carries 2; `agentmemory-repo-package-lock.json` (376 packages) repeats
the same 2 the 2026-09-25 decision already found in the smaller install-prefix lock; and
`hindsight.lock.txt` (223 packages) and `build.lock.txt` (3 packages) show none at scan time.

## Which arms this driver implements

- **D2h (`am-minilm-hooks`)**: `lme_harness.py`'s `am_hook_session()` replays a haystack session
  through agentmemory 0.9.29's own shipped Claude Code hooks (`SessionStart` → `session/start`,
  each user turn → `observe`, each assistant turn and `SessionEnd` → `session/end`), instead of
  driving agentmemory's plain ingest API as the other `am-*` arms do.
- **C4 (`aimem-qwen3-rerank`) is implemented in `lme_harness.py` itself, not in
  `rerank_stage.py`.** C4 is ai-memory's dense retrieval with an LLM reranking pass over its
  results, reached through `LLM_URL` (env `LME_LLM_URL`, "the reranker LLM endpoint for C4", A12)
  and the `RERANK_FALLBACK` handling next to it; the A15.2 `F`/`H` arms are C4 with only the
  embedder or the reranker LLM swapped, in the same file. **`rerank_stage.py` implements a
  different, separate set of arms**: the exploratory "X" arms, a cross-encoder stage
  (`sentence-transformers` `CrossEncoder`, four HF reranker models) over an *existing* arm's top
  50 results. Its own docstring states this is "reported, never decided: no memory system accepts
  these models as shipped, so X is outside every Holm family" — unlike C4, which is inside the
  confirmatory family structure. The coordinator's brief for this task named `rerank_stage.py` as
  "the C4 reranker stage"; that does not match what the code does, and this README follows the
  code. One of the four X rerankers, `kalm-small` (KaLM-Embedding/KaLM-Reranker-V1-Small),
  loads with `trust_remote_code=True` (`rerank_stage.py:40`), so that arm executes Python shipped
  in the model repository. Mitigations already in place: the revision is pinned
  (`pins.json`/`revision_of`, `:48-49`), the load uses `local_files_only=True` (`:98-100`),
  `lane_tools.py`'s `fetch-hf` hash-verifies the files (`:110-133`), and `run_velanext.sh:757`
  sets `HF_HUB_OFFLINE=1` for every X-arm invocation.
- **The A16 arms** (`mempalace-palace`, M2; `hindsight-qwen3.6`, K1, on `k1-subset.json`) are also
  dispatched from `lme_harness.py`, which drives both systems over HTTP (`LME_MEMPALACE_VENV`/
  `LME_MEMPALACE_ONNX`, `LME_HINDSIGHT_URL`) the same way it drives ai-memory and agentmemory; D2h
  joins this family at α = 0.0167 per-arm. M2's teardown (`mp_kill_mines`) is covered in the
  shared-host section above.
- Diagnostics that are not decided by any arm above: `mteb_lmeb.py` (first-line embedder check),
  and MemPalace's own raw-mode benchmark and Hindsight's `agent-memory-benchmark`, both run from
  the vendors' own pip-installed packages (`run_velanext.sh`'s `amb` command), not from files in
  this directory.

## Non-portable paths and drivers

- **`run_velanext.sh` and `setup_velanext.sh` are VelaNext-specific**, not portable to another
  host as-is: they default to `$LME_BENCH_ROOT` (`~/.local/share/lme-bench`), call `nvidia-smi`
  for the GPU-idle gate, resolve `mise`-managed `node` and a CUDA `llama.cpp` build, and drive
  Ollama from a Linux layout.
- **`requirements/*.lock.txt.frozen` are locked for Linux x86_64** (`manylinux_2_28`/
  `manylinux_2_35`), i.e. VelaNext, not the Mac's arm64 (the Mac's own venv, per #380's README,
  was never lock-filed at all).
- **`lme_harness.py`, `lane_tools.py`, `lme_summarize.py` and `rerank_stage.py` are portable by
  design** (every install and data path is environment-variable overridable: `LME_HOME`,
  `LME_OFFICIAL_DIR`, `LME_AIMEM_BIN`, `LME_AM_ROOT`, `LME_MINILM_DIR`, `LME_MEMPALACE_VENV`,
  `LME_MEMPALACE_ONNX`, `LME_HINDSIGHT_URL`, `LME_NODE`, and more), but not every *default* points
  the same way. `LME_HOME` itself defaults to `HERE`, this directory (`lme_harness.py:87`; its
  docstring at `:34` says "default: this directory"), so the paths derived from it — `DATA`
  (`:102`), `MINILM_DIR` (`:120`), `MP_VENV` and `MP_ONNX` (`:182-183`) — resolve inside
  `blueprints/memory-stack/longmemeval/v4/` when unconfigured. Only the paths derived from `AE =
  Path.home() / ".local/share/agent-ecosystem"` (`:86`) — `LME_OFFICIAL_DIR`'s default (`:88`),
  `AIMEM_BIN` (`:117`) and `AM_ROOT` (`:121`) — default under `Path.home()`, the Mac's layout.
  `lane_tools.py` defaults separately, to its own lane's `.local/share/lme-bench` layout.
  Unconfigured, a run assumes some mix of this directory and one of those two home layouts
  exists; `run_velanext.sh` is what sets the environment variables that repoint every one of them
  at VelaNext's prefix.
- **`reference/lme_harness_v3.py` hardcodes the Mac's home layout** with no environment override
  for the official checkout or the ai-memory/agentmemory paths (only `LME_EMBED_URL`,
  `LME_AM_SLOTS` and `LME_LLM_URL` are configurable there) — the same non-portability #380 already
  documents for this file under its own name.
- No file in this directory contains a literal `/Users/...` or `/home/...` path; every home
  reference is a runtime `Path.home()` call. `"VelaNext"` and `"VelaNext (WSL2)"` appear only as a
  `--platform` string value `lme_summarize.py --confirmatory` checks (`lane_tools.py`'s own
  environment-record label), not as a hostname lookup.

## Not transferred, and why

None of the files below failed the private-content scan; they are out of this PR's requested
scope. Sizes and hashes are of the source blob at 576689a.

- **`LANE.md`** (20,655 bytes, sha256 `bfa6a52b927f621c00f09a8542ebea24ba3005850603509b7122361820168dda`):
  the operational brief for a live VelaNext agent session (run order, stop conditions, arms and
  vendor harnesses beyond D2h/C4). Not needed to run or understand this driver; superseded here by
  this README for that purpose.
- **`README.md`** (6,273 bytes, sha256 `1b1dde4d7e9efa8eda9bc63a32fc555d957e15453fc81be1dceb4d5f4bec0710`):
  the source directory's own README, describing the full VelaNext lane (every arm family, every
  vendor). Superseded here by this file, scoped to the transferred subset.
- **`eligible-manifest.json`** (13,607 bytes, sha256
  `871f5da108b2901204aa01315b87d91cdee8d4e61dea96f4499916cbc19a05b7`): the frozen question-id
  manifest `lme_harness.py` resolves at `HERE / "eligible-manifest.json"`. Byte-identical to the
  copy #380 already carries at the same sha256; not duplicated here.
- **`agentmemory/package.json`** (113 bytes, sha256
  `f735eef9db3d00f08dcacf74d5057a5a662d620856fce836ca1ad07ac67ec76e`) and
  **`agentmemory/package-lock.json`** (114,313 bytes, sha256
  `e45aa62e9a2b6897e7024d138945b5c5a3bcc50f2e0d1ba548ecc5b6a73c8a27`): the agentmemory
  install-prefix lock D1/D2/D2h restore. Byte-identical to #380's `agentmemory/package.json.frozen`
  and `package-lock.json.frozen`; not duplicated here.
- **`run_official_oracle.py`** (472 bytes, sha256
  `fc2c4e2e88032412a37cabf1dadace1c0e4e54265e65fa0374f9545e60e1ad67`): the Mac's device-count shim
  for the official oracle on a host without CUDA. Byte-identical to #380's copy; VelaNext has CUDA
  and does not need it.
- **`embed_cache_proxy.py`** (14,077 bytes, sha256
  `e08e11f871be151ade7d59b4dff5b7835746b1166fac31fe6681b9bfc58df5e3`, blob `b83281ab`): a v4
  revision of the A13 byte-exact embedding cache (its own directory README describes it as
  "fingerprinted by upstream and device... A16.3"). **Not byte-identical to #380's frozen v3 copy**
  (different size and hash). Not in this task's requested file list, so it is not transferred here;
  an arm that needs the byte-exact cache (C3 and beyond) cannot run from this directory alone
  until it, or a decision to omit it, is confirmed.
- **`embed_gates.json`** (11,846 bytes, sha256
  `20cd902a1c689e554df8227c33ba771ed4d29ed9cd5b8d6548ff9357e1241d8a`): reference-output gate
  fixtures (model cards' example texts and published similarities). Not requested; not imported by
  any transferred file at module load.
- **`ruff.toml`** (584 bytes, sha256 `df5c5ce6449b66d433f511fdb4f071abbe31c67baa687257607ef5df6ae0c5be`):
  lint configuration, not part of the driver's runtime contract.
- **`reference/v3-check-ids.txt`** (180 bytes, 20 ids, sha256
  `4731681ecd355ebf39b8c7eef9d0fbe661fec44b5fe10295f0491ad6232365c3`): the question-id subset for
  the A15.2 v4=v3 equivalence check. Not requested.
- **`reference/mac-rows/aimem-fts.jsonl`** (21,509 bytes, sha256
  `92c00c4e2a59a7827f5c3b3e3715355564047b269bd0e77a6fe8135f9c2de4ab`) and
  **`reference/mac-rows/bm25-full.jsonl`** (23,493 bytes, sha256
  `a8d30256bbb16630206b09d3b7661f3a02943468c586a647fbe1e3d8c09a60bb`): recorded result rows from
  the Mac's v3 run. Results are out of scope for this PR.
- **`ollama/*.Modelfile`, three of the original four excluded.** `qwen3.5-9b-64k.Modelfile` is
  **now transferred** (Files table above): the GPT-6 review at `97697b81` found it is a C4
  prerequisite (`pins.json:146`'s role field, `run_velanext.sh:654`'s `llm_up qwen3.5-9b-64k
  aimem-qwen3-rerank`), not outside D2h/C4 as this README wrongly said; it is also the reranker LLM
  for the A15.2 F arms and the pooled `aimem-qwen3-rerank` stage. The other three are not
  themselves D2h's or C4's own reranker LLM — each is the reranker LLM for one H arm
  (`lme_harness.py`'s `H_RERANK_MODELS`/`run_velanext.sh`'s matching loop), and
  `qwen3.6-35b-a3b-64k` doubles as K1's LLM (`run_velanext.sh:68`'s `H1_BUILD`) — but that does
  not make them optional for a D2h, C4 or K1 run *from this directory*: `run_velanext.sh gates`
  is mandatory before any arm (`require_gates`, `:229-233`, called by `cmd_cpu` at `:573` for D2h,
  `cmd_arms` at `:691` for C4, and `cmd_a16` at `:695` for K1), and `cmd_gates` (`:458`)
  smoke-tests all four reranker-LLM tags, including these three, and runs the K1 smoke on
  `$H1_BUILD` (`:528-535`) before it writes `logs/gates/passed.json`; the two llama-served tags
  among them are read from `$LANE/ollama/$tag.Modelfile` at `:338`. **So no D2h, C4 or K1 run
  through this driver can pass its gates from this directory without all three of the files
  below — they stay excluded from the transferred file list, not from what a run needs** (see
  "Before anything runs" below):
  - **`lfm2.5-2.6b-64k.Modelfile`** (411 bytes, sha256
    `f22a2c27d5401968b86d4eff044f5eed8e4a6299a468dd369714d733cd7ed6a1`, blob `d8a1d230`): H3's
    reranker LLM.
  - **`nemotron-3.5-lightning-30b-a3b-64k.Modelfile`** (403 bytes, sha256
    `5ae40dcb5c124dbf9c9b2abcec711799661e4c78e6b1d0545ec238868174c768`, blob `bdbf2946`): H2's
    reranker LLM.
  - **`qwen3.6-35b-a3b-64k.Modelfile`** (388 bytes, sha256
    `861c2be0691282ae47e240c1775a3afc0ab64d604e2c294af9fc509331697bc3`, blob `cbef3bff`): H1's
    reranker LLM, and (via `H1_BUILD`) K1's LLM too.

Also excluded, per this task's scope, regardless of size: the dataset, any run's results, caches,
logs and model weights. None of those are tracked at 576689a under `evals/longmemeval/`.

## Before anything runs

Committing this code is not the same as being able to run it from this directory. Beyond
`embed_cache_proxy.py` (above, blocking C3 and beyond), none of `setup_velanext.sh`'s steps or
`run_velanext.sh gates` succeed here without also supplying:

| Missing or renamed | Read at | Available from |
| --- | --- | --- |
| `eligible-manifest.json` | `lme_harness.py:103,1710`; `setup_velanext.sh:130`; `run_velanext.sh:472`; `lane_tools.py:697` | Byte-identical to `../eligible-manifest.json` (#380, now on `main`): `cp ../eligible-manifest.json .` |
| `agentmemory/package.json`, `agentmemory/package-lock.json` | `setup_velanext.sh:156` (D2h's `npm ci`) | Byte-identical to `../agentmemory/package.json.frozen`/`package-lock.json.frozen` (#380): `mkdir -p agentmemory && cp ../agentmemory/package.json.frozen agentmemory/package.json && cp ../agentmemory/package-lock.json.frozen agentmemory/package-lock.json` |
| `embed_gates.json` | `embed_server_st.py:381,388`; `run_velanext.sh:511` (the reference-output gate loop); hashed by `lane_tools.py:697`'s receipt | Not present anywhere in this repository (not requested for transfer, and not byte-identical to any file #380 carries); fetch it from `evals/longmemeval/embed_gates.json` at `agent-ecosystem@576689a` |
| `reference/v3-check-ids.txt` | `lane_tools.py:54`; `run_velanext.sh:469,489,492,503` (the v3=v4 equivalence gate) | Not present anywhere in this repository; fetch it from the same commit's `evals/longmemeval/reference/v3-check-ids.txt` |
| The five `requirements/*.lock.txt` (plain names) and `vendor/agentmemory-repo-package-lock.json` (plain name) | `setup_velanext.sh:95` (`venv()`), `:130` area's sibling installs, `:278`; `pins.json`'s `python_locks`/`vendor_bench.lockfile` fields | Restore each `.frozen` copy under its plain name **only in an isolated prefix**, never in this checkout (the coverage test reads the plain names here): e.g. `cp requirements/official.lock.txt.frozen /isolated/prefix/requirements/official.lock.txt` for each of the five, and `cp vendor/agentmemory-repo-package-lock.json.frozen /isolated/prefix/vendor/agentmemory-repo-package-lock.json`; point `setup_velanext.sh`'s `$LANE` at that prefix |
| `ollama/lfm2.5-2.6b-64k.Modelfile`, `ollama/nemotron-3.5-lightning-30b-a3b-64k.Modelfile`, `ollama/qwen3.6-35b-a3b-64k.Modelfile` | `run_velanext.sh:338` (the two llama-served tags), `setup_velanext.sh:228-229` (`ollama create`); required by `cmd_gates` (`:528-535`) before `require_gates` passes for any arm | Excluded from this PR (sizes, hashes and source blobs above); fetch them from the same commit before `gates` can run |

None of this changes what is committed here. It is the gap between "the driver's code is in
Git" and "a run can start from this directory alone," and this PR does not close it.

## Verifying

```sh
cd blueprints/memory-stack/longmemeval/v4
shasum -a 256 -c SHA256SUMS
```

`SHA256SUMS` lists every file here except itself. The same files are registered in
`manifests/evidence.json`, and `python3 scripts/validate.py` checks their sha256 and size.

| Claim | Evidence class | How |
| --- | --- | --- |
| The 25 copied files match `evals/longmemeval/<path>` at agent-ecosystem commit 576689a, byte-exact | `source_review` | `git rev-parse 576689a:evals/longmemeval/<path>` against the blob column above, and sha256 against `SHA256SUMS` |
| `PREREGISTRATION.md` matches the required hash `a9b1db335eee1ff99d1883e048bcd8e443ca2afee3505a34fd874dd1ef412d5b` | `source_review` | sha256, checked before this commit was written |
| Which code implements which arm (D2h, C4, X, A16) | `source_review` | reading `lme_harness.py` and `rerank_stage.py` directly, not their docstrings alone |
| The shared-host warning's claims about `_ours`, `am_teardown`, `am_start`, `mp_mine_pids`/`_pid_alive`/`mp_kill_mines` in `lme_harness.py`, `stop_bg`/`same_process` in `run_velanext.sh`, and the Ollama readiness loop in `setup_velanext.sh` | `source_review` | reading each function directly at the line numbers cited above |
| The three `lme_harness.py` teardown gaps above (`_ours`, `am_teardown`, `am_start`), reproduced rather than only read | independent observation | GPT-6 cross-family review at `97697b81` ([PR comment](https://github.com/seathatflowsinourveins/native-agent-stack/pull/386#issuecomment-5853228279)): "An inert reproduction confirmed SIGKILL in all three cases" |
| `--help` for `lme_harness.py` and `lme_summarize.py` from a clean clone | `local_integration` | see the PR body for the exact commands and results |
| Any benchmark result | none new | no arm ran for this commit |
