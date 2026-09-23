# Gap wave 2: foundation/quality-evaluation

Branch `claude/g2-quality-evaluation-20260923`, base `41d39b3`. This is the fix
round after an independent review of the first round (commit `b37df23`). A
second fix round (see "Fix round 2" below) reran gaps 0 and 2 and corrected
the gap-5 hook-detection claim under `preregistrations-fixround2.json`,
committed in `1fcd1fe` before any fix-round-2 command. Every
gap was rerun under new preregistrations. Those were committed in `ebf6ac1`
(`preregistrations-fixround.json`, written 2026-09-23T02:42:37Z) before any
fix-round command ran. The round-1 `written_at` values were reconstructed after
their runs. Each receipt marks them late and sets them to `null`. The round-1
support files are superseded and kept only in git history at `b37df23`.

`results.json` is generated from the receipts by
`blueprints/gap-wave2-20260923/foundation__quality-evaluation/gen_results.py`.

## Outcomes

| gap | outcome | reason |
|---|---|---|
| 0 | settled | Two frozen 30-case sets ran through `promptfoo eval` with per-case scores retained. The second set has same-topic hard negatives and was written by one Codex call, not by this agent (sha256 `be64ae45…`, committed in `2557b2f` before any embedding call). Nemotron, called as its model card does (separate query/document requests with `input_type`), scored 30/30 on both sets; bge-small-en-v1.5 scored 30/30 and 28/30. A constant control passed only the 6 label-0 cases. The earlier 26/30 came from a call without `input_type`, which scores 13/30 on the hard set. |
| 1 | settled | The whole upstream `examples/todomvc` suite at Playwright `v1.63.0` (24 tests: six spec directories plus `seed.spec.ts`) passed 24/24 against demo.playwright.dev. |
| 2 | settled | Each winner's own project fixture returned exit codes 0, then non-zero, then 0 (original / mutant / restored). Promptfoo ran `examples/promptfoo-nemotron-upstream` with two documents swapped in its assertion target: 0 / 100 / 0. ShellCheck ran `shellcheck fixtures/example.sh` with an unquoted `$1`: 0 / 1 / 0 (SC2086). Playwright ran the project's application with its frozen `ledger.spec.ts` and an update that no longer records history: 0 / 1 / 0. The app ran in a private network namespace, because a running service holds host port 18080. |
| 3 | settled | ShellCheck exited 1 on the warning fixture (code SC2086) and 0 on a clean fixture. `difft --exit-code` exited 1 on a changed file and 0 on identical files. A content assertion found the changed token in the diff output and did not find it in the identical-file output. |
| 4 | settled | inspect-ai 0.3.268 and mlflow 3.16.1 were pinned into a fresh prefix. Promptfoo and Inspect ran the identical frozen cases: 26/30 each, with identical predictions on 30/30 cases. Runtime was recorded. Token usage was 2040 in each harness, matching the vLLM meter delta. |
| 5 | advanced | The set was extended to 20 cases with labels frozen before inference. Codex and one bounded Claude call both returned schema-validated verdicts: Codex matched 20/20 labels and Claude 17/20. The prompt was not blind on C4 (the C15–C17 excerpt discloses the earlier C4 correction), so C4 agreement is not independent. Not done: TypeSafe on C9–C20, because it needs an API credential this brief forbids reading. |
| 7 | advanced | The upstream four-query assertion was rerun with `-o results.json` and passed 4/4. Its promptfoo counters are zero placeholders; the vLLM meter shows +336 tokens. The independently authored queries report tokenUsage 2040 inside promptfoo. Cost is still unreported, because the local endpoint has no price source. |
| 9 | advanced | Two unmodified upstream Inspect examples ran from a pinned fresh prefix against a temporary loopback vLLM chat server (the resident vLLM serves embeddings only; its chat endpoint returned 404). Each run was logged to a temporary loopback MLflow server, and three runs were retrieved as FINISHED by REST. Both servers were stopped. Not addressed: CI failure repair and security finding quality. |
| 10 | advanced | The baseline is only partly matched: schema-validated Codex and Claude reviews ran on the identical eight cases, but the same prompt disclosed the reference C4 label (C15–C17) and TypeSafe's 7/8 aggregate (C18–C20). Agreement is Codex 8/8 and Claude 6/8 with the source-review labels, and 7/8 each with TypeSafe; the C4 entries are contaminated. The C4 split remains: TypeSafe and Claude say `contradicted`; Codex and the frozen label say `insufficient`. |

## Layout

- `N-<slug>.json`: one receipt per gap.
- `preregistrations-fixround.json`: the fix-round preregistrations.
- `preregistrations-fixround2.json`: the fix-round-2 preregistrations (gaps 0, 2 and 5).
- `support/fixround2/`: fix-round-2 raw outputs. It holds the hard-negative authoring packet and Codex output, the frozen `hardneg-cases.json`, the `g0-out/` and `g2-out/` runs, and `setup/` logs. It has its own `COLLECTED.json` with the same substitution rules. The 1.6 MB PostgreSQL build log is published as a tail with the full log's sha256.
- `support/fixround/`: raw outputs, grouped by the helper script that produced them. `COLLECTED.json` gives each file's raw and published sha256 and its publication substitutions: the host home directory replaced by `$HOME`, CRLF normalised to LF (vLLM logs only), and UUID-shaped ids replaced by `<uuid-redacted>` (promptfoo result ids, the Claude session id and the Codex thread id). The validator rejects UUID-shaped strings.
- `support/typesafe-extension/`: the 20-case packet, frozen labels, schema and prompt, committed in `1b85ad8` before either model call.
- `support/reconciliation/`: the read-only round-1 hook determination (Codex source excerpt and hook registration, host home shown as `$HOME`).
- Helper scripts: `blueprints/gap-wave2-20260923/foundation__quality-evaluation/`. After the runs, the host paths hard-coded in five helpers were rewritten to `$HOME` or to script-relative paths; no logic changed. Rerunning `build_typesafe_extension.py` reproduces the four frozen packet hashes.

## Isolation and downloads

- Installs went only under `$HOME/.cache/gap-wave2-20260923/quality-evaluation/`. The pinned venv used its own uv cache: 141 packages from PyPI, 831 MB unpacked. Heavy commands ran through `ecosystem-bounded-run`.
- Other network downloads:
  - a blobless sparse clone of `inspect_ai` `examples/` at tag 0.3.268 (4 MB);
  - the pinned NVIDIA model card README, which matches the local copy's sha256;
  - four TodoMVC static files from demo.playwright.dev (about 1 MB).
- A temporary vLLM ran on `127.0.0.1:18431` from the existing vLLM 0.25.0 environment, using the existing local Qwen2.5-7B-Instruct-AWQ weights, with its caches in the work directory. A temporary MLflow server ran on `127.0.0.1:15005` with a temp sqlite store, and a TLS mirror on `127.0.0.1:18443`. All three were stopped. Afterwards the MLflow and vLLM listener counts were 0 and no MLflow server process remained, and the mirror refused connections (curl exit 7). Connects to the stopped MLflow port and to an unused control port timed out instead; that difference is unexplained, so shutdown rests on the listener counts and process checks.
- The resident embedding vLLM (`:8231`) received only inference, `/v1/models`, a 404 chat probe and `/metrics` reads.
- The Codex call ran with `--ignore-user-config --disable hooks`. The Claude call ran with `--setting-sources project --strict-mcp-config --tools ""` from an empty directory. Hooks are ruled out on three grounds. First, both CLIs had hooks disabled by configuration. Second, neither call made a tool call: Claude had no tools, and `codex-events.jsonl` holds only thread, turn and agent-message events. Third, every hook process the poller sampled was a pre-tool-use or post-tool-use event, which a call without tool calls cannot emit. No session-start, user-prompt-submit or stop hook appeared. The earlier per-session attribution ("none in either call's session") is withdrawn (fix round 2). Every sampled hook was its own session leader, so a hook spawned by the call would not have shared its session. Parent-pid ancestry was not captured.
- Fix round 2 used the same isolation rules. It made one more Codex call (`run_codex_author.sh`, same flags, no tool items) to author the hard-negative set. Installs went under `$HOME/.cache/gap-wave2-20260923/quality-evaluation/fixround2/`:
  - a venv with `fastembed==0.8.1` (28 PyPI packages, 178 MB);
  - Qdrant's bge-small-en-v1.5 ONNX export (65 MB);
  - three Ubuntu noble .deb files (flex, m4, bison), sha256-checked against `ubuntu-packages.json` and extracted with `dpkg-deb -x` into a task sysroot;
  - the PostgreSQL 18.6 source tarball (21.6 MB, sha256-checked by the Makefile) and its build, through `ecosystem-bounded-run`;
  - pnpm 12.4.2 through corepack with `COREPACK_HOME` in the prefix;
  - the app's locked pnpm (62) and uv (28) packages;
  - a Next production build.

  PostgreSQL, the API, Next and Chromium ran in an `unshare` user+network namespace whose only interface was `lo`. Afterwards no listener remained in the namespace and none on host ports 15432/18081. The host's ntfy on `127.0.0.1:18080` was not touched.
- No broker, paper-account or gate work was done; none of these gaps names it.

## Unresolved

- Gap 5: TypeSafe on C9–C20 needs `TYPESAFE_API_KEY`, which is outside this brief. The C9–C20 labels were written by this agent and were not independently reviewed.
- Gap 0 (settled; remaining limits): Nemotron reaches the ceiling on both 30-case sets, so they cannot rank it against a stronger model. The Codex-written hard-set labels were not re-reviewed beyond the two bge-small failures.
- Gap 7: monetary cost for the local endpoint has no price source.
- Gap 9: CI failure repair and security finding quality are untested.
- Gap 10: C4 needs an explicit labelling rule or an independent adjudicator, and a C4-blind rerun (Codex on C1–C8 alone, or a packet without C15–C20). The Claude arm cannot be rerun under the one-call limit and stays contaminated on C4.
- Round-1 Codex probe: it ran with the user's ai-memory hooks registered, but it never reached session start, so no hook wrote to the live store (see Reconciliation).

## Fix round 2

This section answers the second independent review (Opus). All three findings are supported.

1. **Major: gap 0 was not a held-out evaluation of model quality.** Supported,
   and confirmed by the rerun. `heldout_common.predict()` sent the query and
   candidates in one request without `input_type`. The model card's call sends
   them separately with `input_type` "query" and "document". With that call
   (`predict_typed()`), the four fix-round-1 failures pass, and the easy set
   scores 30/30. Also run:
   - A 30-case hard-negative set, written by one Codex call and frozen before
     use. Nemotron scored 30/30 on it, bge-small-en-v1.5 28/30, and the
     untyped call 13/30.
   - A constant control, which passed exactly the six label-0 cases.

   Every preregistered arm ran, so gap 0 is `settled`. Limits:
   - Nemotron hits the ceiling on both sets, so the set cannot rank it against
     a stronger model.
   - The hard-set labels were not re-reviewed beyond the two bge failures.

   `predict()` is unchanged. The gap-4 harness comparison used that call in
   both harnesses, so it stands; receipt 4 now says so.
2. **Major: the hook poller could not detect what it reported absent.**
   Supported. Every sampled hook process was its own session leader, so the
   session filter was true by construction. The claim is withdrawn in
   receipt 5 and above. The conclusion now rests on three grounds: hooks were
   disabled by configuration, neither call made a tool call, and every sampled
   event was a tool-use event. Parent-pid ancestry was not captured.
   `run_review_call.sh` is unchanged apart from a header note. Gap 5 stays
   `advanced`.
3. **Minor: gap 2 used substitute fixtures.** Supported. Gap 2 was rerun on
   the project's own fixtures:
   - the Promptfoo upstream-retrieval example;
   - the manifest's `shellcheck fixtures/example.sh`;
   - the `application-delivery` app under its frozen browser oracle.

   All nine exit codes matched. The fix-round-1 substitute runs are kept as
   supporting evidence only.

`results.json` was regenerated from the receipts by `gen_results.py`. The
outcomes are unchanged: gaps 0 and 2 stay `settled`, now on evidence that
closes the named clauses.

## Reconciliation

This section answers the latest independent review. No new checks were run.
The only new evidence comes from read-only inspection of files already on this
host, plus one fetch of the upstream Codex source file (85 KB; its sha256
is recorded).

1. **Major: the "blind" reviews were not blind to the C4 label.** Supported.
   `support/typesafe-extension/prompt.txt` asks for C4 at lines 86–96. The
   C15–C17 source excerpt (lines 193–215) says the earlier native reviews
   "corrected C4 to `insufficient`", and the C18–C20 excerpt (lines 217–239)
   gives TypeSafe's 7/8 aggregate. What changed:
   - Receipt 10 no longer says the baseline is blind or that the
     unmatched-baseline clause is closed. It says the matched-blind-baseline
     clause is only partly closed.
   - Both reviewers' C4 verdicts are marked contaminated. Codex's C4 answer
     (and its 8/8 and 20/20 counts) cannot count as independent agreement with
     the frozen label.
   - The Claude arm cannot be rerun under the one-call limit and is recorded as
     contaminated on C4. The Codex rerun on C1–C8 alone is named as remaining
     work.
   - Receipt 5 gains a `blindness` result and a matching limit. Gaps 5 and 10
     stay `advanced`, because neither was claimed settled.
2. **Minor: the shutdown explanations contradict each other.** Supported. The
   stopped mirror on port 18443 refused its connection (curl https, exit 7).
   At 02:52Z, the curl http connect to 15005 timed out (exit 28), and Python
   socket connects to 15005 and 15999 raised TimeoutError. What changed:
   - The general claim ("any closed loopback port times out on this host") is
     withdrawn from receipt 9 and from this README. The cause of the timeouts
     was not determined.
   - Shutdown still rests on 0 listeners on :15005 and :18431, the process
     recheck, and GPU memory returning to 5540 MiB.
   - The raw `mlflow-stop-verification.txt` is left unchanged, because it is a
     raw output. Its note is superseded by receipt 9.
3. **Minor: the round-1 ai-memory exposure was stated only as a possibility.**
   Supported, and now determined read-only. The answer is **no**: the call did
   not write to the live store. The evidence is in
   `support/reconciliation/codex-round1-session-start.txt` and
   `support/reconciliation/codex-user-hooks-registration.txt`:
   - `$HOME/.codex/hooks.json`, unchanged since 2026-09-21T14:35Z, does
     register ai-memory SessionStart, UserPromptSubmit and other hooks against
     the live store at `127.0.0.1:49374`. So the round-1 call was exposed.
   - The round-1 process never reached session start. Its only stderr line is
     "Reading additional input from stdin...", its stdout is empty, and it was
     reaped by `timeout 300`.
   - In the codex-cli 0.155.1 source (tag `rust-v0.155.1`,
     `codex-rs/exec/src/lib.rs`), that message comes just before a blocking
     `read_to_end` on stdin. This happens inside `resolve_root_prompt` (line
     941), which runs before the in-process app server starts (line 973) and
     before `thread/start`. Hooks run inside that app server.
   - Limits: this relies on the installed version string matching the upstream
     tag. `config.toml` was modified after round 1, so its hooks feature flag
     at that time is not shown directly. This does not change the answer,
     because no session started.
   - The live store was not queried, per the rules.
   - One read-only query of Codex's local log database found no new Codex
     process in the round-1 window. That log was not shown to record blocked
     `codex exec` processes, so it is not used as evidence.

`results.json` was regenerated from the receipts by `gen_results.py`. The
outcomes are unchanged.

## Coordinator note (2026-09-23): CodeQL fix

CodeQL flagged `serve_mirror.py` (py/insecure-protocol) because its server context still allowed TLS 1.0 and 1.1. It now sets `minimum_version = TLSv1_2`. The loopback mirror's receipts are unchanged, and the script's hash is not pinned by a receipt.

## Coordinator note (2026-09-23): privacy sweep

The catalog rule is: "Evidence belongs in compact sanitized receipts; no raw conversations, tokens, personal paths or machine-specific active client configuration." The PR #132 review found the host username, Claude transcript and plugin-data locations, worktree names and the active session environment in conversation-derived raw files, and the username in several command outputs.

Host username replaced by `<user>` (`-home-<name>-` project slugs become `-home-<user>-`). Raw command outputs are otherwise unchanged; metadata files also had the text changes listed under "Pins updated":

- `support/fixround/g9/mlflow-run-2d1037033bff45b5ba8970b90ebd9d10.json`: 2 replacement(s), sha256 `33738ea525b5...` -> `5a13c089721a...`
- `support/fixround/g9/mlflow-run-4b176a82717c4de79d631d2aeae7efca.json`: 2 replacement(s), sha256 `809d740434ab...` -> `255069a832a3...`
- `support/fixround/g9/mlflow-run-c2c725db27ef4b488101f86e759e47c4.json`: 2 replacement(s), sha256 `eca30bc1d409...` -> `3aac5a2756e6...`
- `support/fixround2/g2-out/app-pg-init.log`: 1 replacement(s), sha256 `8fba3210d17e...` -> `0e72a00b3f33...`

Pins updated: `support/fixround/COLLECTED.json` and `support/fixround2/COLLECTED.json` (`published_sha256`, plus a `user_replacements` count; `raw_sha256` is unchanged). `collect_evidence.py` now applies the same username replacement.

## Coordinator note (2026-09-23): privacy sweep, third pass

RFC 1918 addresses replaced by `<lan-ip>` (loopback and 0.0.0.0 unchanged):

- `support/fixround/g9/vllm-chat.attempt1-uva.log`: 1 replacement(s), sha256 `6f62d4e98ee1...` -> `829e88035e51...`
- `support/fixround/g9/vllm-chat.attempt2-nvcc.log`: 1 replacement(s), sha256 `a18bd07bf2dc...` -> `89cc8aa809cc...`
- `support/fixround/g9/vllm-chat.attempt3.log`: 1 replacement(s), sha256 `4dcf5ee3ccd2...` -> `60c65f131225...`

Pins updated: `support/fixround/COLLECTED.json` (`published_sha256`, plus a `lan_ip_replacements` count). `collect_evidence.py` now applies the same replacement; rerunning it from the cache sources reproduced the three logs and `COLLECTED.json` byte for byte.
