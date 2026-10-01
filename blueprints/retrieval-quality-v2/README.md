# Retrieval quality v2: BM25 vs. hybrid

This blueprint compares QMD 2.8.3's lexical `search` (Arm A, "BM25") with its hybrid `query`
(Arm B, on CPU) on 30 sealed held-out queries over 33 pinned documents, under the frozen
protocol in [PREREGISTRATION.md](PREREGISTRATION.md). All runs below used the same sealed
[`queries.json`](queries.json) (sha256 `4d0a0eaf0f6fc48b899f6139e7e98a6c1edf4798b1f17ddfbf5ec3e1cc6c5c7a`),
the same 33 files at commit `3e4054d02eac06ae8ac995c5e96fe8a75c0824c8`, `-n 10`, the same metrics,
decision rule, bootstrap seed and resample count.

| Run | Runner | Arm A nDCG@10 | Arm B nDCG@10 | Gain | 95% bootstrap CI | Decision |
| --- | --- | ---: | ---: | ---: | --- | --- |
| [2026-09-25](results-20260925.json) | `run.py` as merged in #293 | 0.2228 | 0.7139 | 0.4912 | [0.3673, 0.6185] | Hybrid (Arm B) selected over BM25 |
| [2026-09-26, attempt 1](report-20260926T022931Z.md) | repaired `run.py` (`efba31d53c4a`); stopped by SIGINT, see Amendment 2 and its later correction | 0.2228 | not scored | n/a | n/a | none |
| [2026-09-26, restart](report-20260926T024558Z.md) | repaired `run.py` (`efba31d53c4a`), `--arm-b-query-timeout 1800` | 0.2228 | 0.7281 | 0.5053 | [0.3813, 0.6329] | Hybrid (Arm B) selected over BM25 |

**The decision did not change.** The 2026-09-25 run and the 2026-09-26 restart both reached "Hybrid (Arm B) selected over BM25". In the restart, Arm B scored nDCG@10 0.7281 (2026-09-25: 0.7139), recall@5 0.8500 (0.8500) and MRR 0.7454 (0.7283); Arm A's scores were identical in every run. Condition 1 (gain 0.5053 >= 0.05) and condition 2 (CI lower bound 0.3813 > 0) both held. No Arm B query errored or timed out. Arm B queries took 43 to 153 s (2026-09-25: 33 to 66 s). The retained stderr shows QMD skipped query expansion for 8 of 30 Arm B queries.

**Which `run.py` produced what.** Every committed result, both 2026-09-26 receipts included, was
produced by an earlier runner revision: the 2026-09-26 runs by `run.py` efba31d5 (sha256
`efba31d53c4a36ac482e71d796146d600c76299952055c72005b5b27196f6004`), the 2026-09-25 run by the
`run.py` merged in #293. The committed `run.py` (sha256
`7a04a37842674b9494e3cb37b2915c5269847445d437e63a4192ebe0ed32ecd1`) came later, in two steps, and
has made no run against the real qmd:

1. `run.py` 0792745e (sha256 `0792745e7262dfed2488e50b090560598582f523a1ebfdb76d998e539a490ad7`)
   added signal handling and reads QMD's cached ETag from the file QMD writes. The three real-qmd
   checks and the discriminating controls in
   [`repair-review-20260926.json`](repair-review-20260926.json) ran this revision.
2. The committed revision changes three behaviours. It records empty or incomplete `qmd bench`
   output as `incomplete` rather than accepting it as a completed benchmark. It sanitizes the
   reasons recorded for rejected hits, and the other strings a receipt copies from qmd's output.
   It also corrects the interruption bookkeeping: a receipt now names the qmd call that was running
   when a signal arrived apart from any call the stop cut short, records the decision's
   limitations before the benchmark starts, and records a failure that follows a stop together
   with the stop. Its receipts carry schema 4 for the renamed and added interruption fields, and
   their `qmd bench` limitation is reworded. No other behaviour changed (see
   [`verification-review-20260926.json`](verification-review-20260926.json)).

Both revisions parse, verify and score responses exactly as efba31d5 did: those functions are
unchanged apart from docstrings, and `run_arm` differs only by keeping the queries an interrupted
arm scored and by sanitizing a rejected hit's reason. [`restore-0792745e.patch`](restore-0792745e.patch)
turns the committed `run.py` and its tests back into 0792745e and that revision's tests (sha256
`75cde97957787ef99b80d2d453f0e452885739b09ec58b78bdbbcdee688c4a83`). [`run-efba31d5.patch`](run-efba31d5.patch)
then turns `run.py` 0792745e into efba31d5, byte for byte. In a copy of the checkout, run
`git apply` with the first patch at the checkout root, then with the second next to `run.py`.

## What each file shows

| File | Evidence class | What it shows |
| --- | --- | --- |
| `results-<run>.json`, `report-<run>.md` | Local integration | This repository's harness (`run.py`) scoring upstream CLI output: per-query metrics, the bootstrap CI and the decision. Not an upstream test. |
| `native-<run>.json` | Native CLI output | Every qmd call of the run that returned: sanitized argv, working directory, start and end time, exit code, stdout, stderr and their sha256. Each scored query names the record and stdout hash it was scored from. Attempt 1's file lacks the call that was running when it was stopped (`nl-07`); the committed `run.py` also keeps a call that a stop or an error cut short. |
| `native_bench` in `results-<run>.json` | Upstream native operation | QMD's own benchmark command, `qmd bench`, and its scorer on the same index. |
| [`chronology-20260926.json`](chronology-20260926.json) | Independent observation | The order of the query author's result and the runner's start in the 2026-09-25 workflow's native records, which stay private on the authoring host. |
| [`review-293-repro-20260926.json`](review-293-repro-20260926.json) | Synthetic fixture (F2 to F6, stub qmd), local integration (F1, real qmd) and structural validation (F7) | Each finding of the review of #293 reproduced against the 2026-09-25 `run.py`, and the discriminating controls for `run.py` efba31d5, which can no longer be re-run. The driver, the stub qmd and the eight scenario files that the stub runs used are in [`review-293-repro-20260926/`](review-293-repro-20260926/), and the receipt's `inputs` field lists their hashes. The receipt's `corrections` field records what this labelling changed. |
| [`repair-review-20260926.json`](repair-review-20260926.json) | Synthetic fixture (the discriminating controls), local integration (the real-qmd checks), independent observation (the attempt-1 timing, the ETags and the package comparison) and structural validation (the response counts and the patch check) | The review of the repaired runner, efba31d5: its five defects and how each was resolved. It also holds the discriminating controls for `run.py` 0792745e and its tests, with each mutant's patch and the passing baseline, and three runs of `run.py` 0792745e against the real qmd. Their outputs and drivers are in [`repair-review-20260926/`](repair-review-20260926/). It compares QMD's cached ETags with Hugging Face's own listing and the installed QMD package with the pinned npm tarball, and it times attempt 1. |
| [`verification-review-20260926.json`](verification-review-20260926.json) | Synthetic fixture (the stub-qmd tests and controls), structural validation (the benchmark rule applied to committed output, the patch checks) and independent observation (upstream QMD source) | The final review of `run.py` 0792745e: its findings and how each was resolved. The new tests fail against 0792745e and pass against the committed `run.py`, and the record holds the discriminating controls for the committed `run.py` and tests. It applies the new benchmark rule to the restart's retained `qmd bench` output, checks both patches and re-derives the committed real-qmd receipts from their native files. It also reads the upstream QMD source behind the cache wording below. The controls tool and the two check scripts are in [`verification-review-20260926/`](verification-review-20260926/). |
| [`run-efba31d5.patch`](run-efba31d5.patch) | Structural | Applied to `run.py` 0792745e, it reproduces `run.py` efba31d5, the harness that both 2026-09-26 receipts name. |
| [`restore-0792745e.patch`](restore-0792745e.patch) | Structural | Applied to the committed `run.py` and tests, it reproduces `run.py` 0792745e and its tests, the revision the real-qmd checks and the controls in `repair-review-20260926.json` ran. |
| [`tests/test_retrieval_quality_v2.py`](../../tests/test_retrieval_quality_v2.py) | Local contract tests and structural validation | The runner's isolation, fail-closed, validation, timeout, interrupt, output, retention, sanitization and benchmark-completeness rules against a stub qmd, with real signals sent to a child process. It also checks that every committed receipt of schema 2 or later at the top of this directory re-derives its rankings, docids and metrics from its own native file. Not evidence about QMD. |

## QMD's own benchmark (`qmd bench`)

QMD's documented benchmark command, `qmd bench <fixture.json> --json`, ran on the restart's index
after both arms (native record `native_bench`, stdout sha256
`ae961ec2f7b5f968f1165ce286005dc6802b952bf616348ce3cb03e20e8a8744`). Its fixture is derived mechanically from `queries.json`: each query's
grade-2 files, expected in the top 5 (fixture sha256 `0559c6fb31c588568e692de32cc093bf69a79b510c843dd8f1e85692fb8d932f`). Native columns are
QMD's own returned averages. Exact columns re-score the same returned rankings with exact path
identity, because QMD's scorer accepts suffix matches in either direction.

| Backend | What it runs | Native recall@5 | Native MRR | Native P@k | Exact recall@5 | Exact MRR | Queries where native and exact recall@5 differ |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `bm25` | lexical, as Arm A | 0.2667 | 0.2667 | 0.2667 | 0.2667 | 0.2667 | 0 |
| `vector` | vector only | 0.7667 | 0.7214 | 0.7667 | 0.7333 | 0.6645 | 1 |
| `hybrid` | expansion + fusion, no rerank | 0.8333 | 0.7100 | 0.8333 | 0.8000 | 0.6609 | 1 |
| `full` | hybrid with rerank, as Arm B | 0.8500 | 0.7170 | 0.8500 | 0.8500 | 0.6753 | 0 |

- `bm25` returned the same top-10 ranking as Arm A's CLI output for 30 of 30 queries.
- `full` returned the same top-10 ranking as Arm B's CLI output for 26 of 30 queries.
- Why `full` and Arm B ranked `kw-05`, `pa-02`, `pa-04` and `pa-08` differently was not investigated, and nothing retained explains it.
- QMD's LLM cache held 787 rows before the benchmark and 787 after it. That is consistent with the benchmark reusing Arm B's cached expansion and rerank results, but it does not show it, and it does not show that the benchmark made no model call. At the pinned commit, [`setCachedResult`](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/store.ts#L2651-L2657) rewrites an existing key in place (`INSERT OR REPLACE`). [`expandQuery`](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/store.ts#L4505-L4507) caches only an expansion that is not empty, and the hybrid pipeline [drops a cached expansion](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/store.ts#L5562-L5573) whose sub-queries all came back empty. The row count can therefore stay the same while models run. Which of the benchmark's results came from the cache was not recorded.
- On QMD's own scorer, `full` beats `bm25` by 0.5833 recall@5 and 0.4503 MRR. This is corroboration only; the preregistered decision uses nDCG@10 from `run.py`.

## What the review of #293 found and what changed

An independent cross-family review of #293 found eight defects. Each was reproduced before it
was fixed; the tests fail when any fix is reverted.

| Finding | Reproduced on the 2026-09-25 `run.py` | Repair |
| --- | --- | --- |
| Inherited `INDEX_PATH`/`QMD_CONFIG_DIR` override the scratch index and configuration | With the real qmd and decoy "host" paths, the index build wrote 33 documents into the decoy database and a new configuration file into the decoy configuration directory; only then did the document count check abort the run (35 instead of 33) | Each qmd call gets a minimal environment built from scratch: `INDEX_PATH` and `QMD_CONFIG_DIR` bound to the scratch tree, the scratch HOME as working directory, `--index` on every call including `--version` and `pull`. The index's own `documents` table must hold exactly the 33 pinned hashes before any arm runs. |
| An unresolved HF revision did not stop Arm B | With Hugging Face unreachable, all three revisions were `null` and Arm B still ran and decided | A revision counts only when Hugging Face lists the pulled file at that revision with the same sha256 and size; otherwise Arm B is not evaluated. |
| A wrong or empty docid was still credited | A wrong-docid response scored nDCG@10 = 1.0 with no error | A hit counts only when its path is pinned and its docid is the first six hex characters of that file's pinned sha256. One hit that fails this check rejects the query's whole response: it scores 0 and records the rejected hits (PREREGISTRATION.md, the correction after the review of the repaired runner). |
| Wrong-shaped JSON aborted the run or passed as empty | `{}` and `[42]` aborted the whole run; `null` counted as a clean empty result | Output must be an array of hits with string `file` and `docid`; anything else scores 0 for that query and the arm continues. |
| A pull or embed timeout crashed the run | Both left an aborted receipt with no decision and a `TypeError` while rendering | Setup timeouts record Arm B as not evaluated. A timeout kills qmd's whole process group, because the launcher's child node process would otherwise keep running. The report renders partial and aborted receipts. |
| Every run overwrote `results-20260925.json` | A run whose seal check failed replaced `results-20260925.json` with its aborted receipt (on a copy of the directory) | Each run writes new `results-`, `native-` and `report-<UTC start>` files, refuses existing names and reserves its receipt first. `run.py` no longer writes this README. |
| qmd's output was discarded after scoring | The receipt kept only derived paths and metrics | `native-<run>.json` keeps every call's output with hashes, linked from each scored query. |
| The preregistration's ordering claim cited a journal absent from the checkout | The journal is not in the repository; `results-20260925.json` only repeats the sentence | Bound to a sanitized extract of the native records; see the dated correction in PREREGISTRATION.md. |

## What the review of the repaired runner found

A second independent review read the repaired runner (efba31d5), both 2026-09-26 attempts and
this directory's documents. It confirmed the eight repairs and found five further defects, all
resolved here; [`repair-review-20260926.json`](repair-review-20260926.json) keeps the checks.

| Defect | Verified | Resolution |
| --- | --- | --- |
| A stopped run was recorded misleadingly and could leave qmd running (medium) | Attempt 1's receipt says `started`, with Arm B `not_run` and no reason, although it pulled, embedded and ran `nl-01` to `nl-06`. The call that was running when it stopped, `nl-07`, had run for about 102 s and has no native record. efba31d5 had no SIGTERM or SIGHUP handler, so either signal would have skipped every output and left qmd running in its own session | `run.py` 0792745e turns SIGINT, SIGTERM and SIGHUP into a stop request. It kills the process group of a qmd call that is still running and keeps that call's record. It marks the arm `interrupted` and the run `aborted_interrupted`, writes all three files and, as a script, ends by the signal. A signal the caller ignored stays ignored. Stub tests send real signals. Three runs of 0792745e against the real qmd, now committed in [`repair-review-20260926/`](repair-review-20260926/), checked three cases. The first used a decoy environment. In the second, a SIGTERM arrived while a `qmd search` ran; the call finished first and the run stopped before the next one, but that receipt wrongly said no call "was in flight", which the final review below corrects. In the third, a SIGTERM arrived during `qmd pull`, and its launcher and node child were killed. PREREGISTRATION.md corrects Amendment 2's account |
| `hf_content_store_etag` was always `null` | QMD writes `<model cache>/<URI file name>.etag`; efba31d5 looked for `<downloaded file name>.etag`, which never exists. Both 2026-09-26 run homes hold the three files QMD wrote | `run.py` reads the file QMD writes and records its path. The cached values are Hugging Face's `xetHash` for each file, not its sha256. The three comparison receipts keep `null` |
| Amendment 1 did not state the whole-response rejection rule | One unverifiable hit zeroes the whole query in `run_arm` | A dated correction in PREREGISTRATION.md states the rule; a regression test covers a response with one good and one unverifiable hit |
| The grand-dashboard gate still cited the 2026-09-25 run | `observability/grand-dashboard/state.json` | The gate cites the restart |
| The repair's handoff misstated four facts | In `review-293-repro-20260926.json` the decoy database grew from 122,880 to 1,552,384 bytes and the overwritten receipt's new sha256 is `bd6ca838…`; in `run.py` a hit without an `?index=` parameter is accepted and a Hugging Face lookup makes three attempts, that is two retries | Every fact here is quoted from the committed receipts and code; `resolve_repository_path` documents its index rule |

## What the final review found

A cross-family verification of `run.py` 0792745e confirmed that the eight #293 findings are
resolved and found two medium and three low defects. An independent session's review of the same
change found one more low defect, and unbacked or mislabelled evidence in three files. All of them
are resolved in the committed `run.py` and here.
[`verification-review-20260926.json`](verification-review-20260926.json) keeps each finding, the
new tests failing against 0792745e and the discriminating controls.

| Finding | Verified | Resolution |
| --- | --- | --- |
| Empty `qmd bench` output counted as a completed benchmark (medium) | 0792745e accepted `{"summary": {}, "results": []}` as a completed run of all four backends over zero queries | Output must hold exactly one result for each fixture query, with a `top_files` list for each of QMD's four backends, and a summary for each backend. Anything less is recorded as `incomplete`, with no summary or audit. The restart's retained output passes this rule (30 results, four summaries), so its `completed` status stands |
| A rejected hit's reason was not sanitized (medium) | A stub hit naming `/home/example-user/private/report.md` kept that path in `rejected_hits[].reason` | The reason is sanitized like the hit's file and docid. So are the version banner, `qmd pull`'s URIs, sizes and notes, and `qmd embed`'s duration. The retention test plants host paths in rejected hits, the version banner and a pull note |
| A run stopped during the benchmark kept its decision but lost the decision's limitations (low) | Limitations were assigned only after `qmd bench` returned | They are recorded right after the decision. Only the benchmark's own caveat waits for the benchmark |
| The receipt said "no qmd call was in flight" while a call was running (low) | In real-qmd check `20260926T050511Z`, `arm_a:nl-01` ran from 05:05:13.400Z to 05:05:13.556Z, across the SIGTERM received at 05:05:13.420Z | The receipt names the call running when the signal arrived (`interruption.qmd_call_running_when_received`, and `qmd_call` in each `signals_received` entry), apart from the call the stop cut short (`cut_short_native_record_id`, which replaces schema 3's `in_flight_native_record_id`) |
| An Arm B setup failure that followed a stop was dropped (low; independent session) | A Hugging Face lookup that failed after a SIGTERM left only "stopped by SIGTERM" | The failure is kept in `abort_reason` as part of the stop |
| This README read the cache count as proof of cache reuse (low) | QMD's cache code (above) lets models run without changing the count | Reworded above as an inference. The ranking differences are left unexplained |
| Evidence that could not be checked (independent session) | `review-293-repro-20260926.json` depended on an uncommitted stub, uncommitted scenarios and an uncommitted driver, and labelled its stub runs local integration. The real-qmd checks' outputs and drivers stayed in scratch, yet this README called them retained. It also cited a check of the host's default QMD directories that nothing retained | The stub, scenarios, driver, outputs and drivers are committed and hashed. F2 to F6 are labelled synthetic fixtures. The default-directory claim is withdrawn. Both review records say, in their `corrections` fields, what changed and give the sha256 of the version as recorded |

## History and corrections

- [`results-20260925.json`](results-20260925.json) is the original run's receipt, unchanged.
  Two of its fields were added by hand after that run and were never written by `run.py`:
  `seal.ordering_evidence` and `decision.interpretation`.
- The routing defect did not redirect that run's index: its own `qmd status` output names the
  scratch index (`<SCRATCH_HOME>/.cache/qmd/retrieval-quality-v2.sqlite`). Nothing retained shows
  where its collection configuration was written. The 2026-09-26 callers set neither variable (their
  receipts list `PWD`, `WSL_DISTRO_NAME` and `WSL_INTEROP` as the only QMD-relevant caller
  variables). The 2026-09-25 run resolved all three model revisions but never
  checked them against the downloaded bytes. Both 2026-09-26 attempts pinned the same three
  revisions with the same sha256 values and sizes, and verified each against Hugging Face's LFS
  listing at that revision, so the 2026-09-25 pins do hold those bytes.
- It discarded qmd's output, so its rankings cannot be re-derived from upstream output, and the
  earlier README's statement that expansion skips were "observed directly in this run's stderr"
  cannot be checked. The 2026-09-26 runs keep that output.
- Before its official invocation, the 2026-09-25 runner sent sealed queries to qmd by hand
  (`kw-02` through both arms' commands) and ran `run.py` twice with `--skip-arm-b`; those two
  receipts were not kept. [`chronology-20260926.json`](chronology-20260926.json) lists every
  call, and PREREGISTRATION.md records the deviation in its 2026-09-26 corrections. The extract
  itself was generated at 02:38:37Z, after attempt 1 had hashed a PREREGISTRATION.md that already
  cited it; whether an earlier generation existed was not recorded.
- The first 2026-09-26 attempt ([report](report-20260926T022931Z.md)) was stopped with SIGINT after
  query `nl-06` hit the runner's 240-second hang guard while the host carried unrelated load. Its
  receipt, native records and report are kept as a failed attempt, and it decided nothing. They
  under-report what ran: the receipt says `started` and shows Arm B as `not_run` without a reason,
  although the attempt pulled and pinned the models, embedded the index and ran `nl-01` to `nl-06`,
  and the native file lacks the `nl-07` call that was running (PREREGISTRATION.md, Amendment 2,
  its erratum and the correction after the review of the repaired runner). The restart used an
  1800-second guard and changed nothing else.
- [`review-293-repro-20260926.json`](review-293-repro-20260926.json) keeps the reproductions of
  the #293 review's findings against the 2026-09-25 `run.py`, and the discriminating controls for
  efba31d5. Those controls cannot be re-run. The test file they ran (sha256 `8fbd6c42…`) and the
  tool that applied their mutants were never committed, and the receipt does not record the
  mutants' patches. [`repair-review-20260926.json`](repair-review-20260926.json) keeps the
  controls for `run.py` 0792745e and its tests, which `restore-0792745e.patch` recovers.
  [`verification-review-20260926.json`](verification-review-20260926.json) keeps the controls for
  the committed `run.py` and tests.
- The earlier README was generated for the 2026-09-25 run and then edited by hand. This index
  replaces it; that run's numbers are in the table above and in its receipt.

## Upstream sources

QMD 2.8.3 is commit `facd35e01359e59d938bc9418e93fb9318addee3` (tag `v2.8.3`). On 2026-09-26 the
pinned npm tarball, fetched again from the registry, matched its pin (sha256
`2e60829913a0c646234a905cefd61043167a1392fdcfd19bc54f890af89ca0f0`, in
[`adoption/pins-linux-x86_64.json`](../../adoption/pins-linux-x86_64.json)), and each of its 53
files was byte-identical to the installed package's copy; `repair-review-20260926.json` keeps
that comparison. Each receipt also records the installed modules' sha256.

- Benchmark: `qmd --help` lists `qmd bench <fixture.json>`; see the README's
  [Benchmarking](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/README.md#L1058) section, the [CLI dispatch](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/cli/qmd.ts#L4715),
  [`runBenchmark`](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/bench/bench.ts#L325) and the scorer's
  [`normalizePath`/`pathsMatch`](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/bench/score.ts#L12).
- Environment precedence: [`getDefaultDbPath`](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/store.ts#L636) reads `INDEX_PATH` before
  the `--index` name, and [`getConfigDir`](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/collections.ts#L112) reads `QMD_CONFIG_DIR`
  before `XDG_CONFIG_HOME`.
- Docid: [`getDocid`](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/store.ts#L2341) is the first six hex characters of the content
  sha256.
- Model cache: [`pullModels`](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/llm.ts#L495) takes the file name from the model URI's last
  path segment and caches the ETag of that file's `resolve/main` URL as `<model cache>/<file name>.etag`
  ([lines 508 to 547](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/llm.ts#L508-L547)).
- Process model: the [`bin/qmd` launcher](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/bin/qmd#L175) spawns a child node process, so a
  timeout or a stop must kill the whole process group.

## How to run

```sh
python3 blueprints/retrieval-quality-v2/run.py --repo "$STACK_REPO" --scratch-home "$SCRATCH_HOME"
python3 -m unittest tests.test_retrieval_quality_v2   # offline contract tests, stub qmd only
```

The runner needs QMD 2.8.3 from the official npm package `@tobilu/qmd` on `PATH` (pinned in
[`manifests/stack.json`](../../manifests/stack.json)) and, for Arm B's first pull, access to
Hugging Face. It writes new `results-`, `native-` and `report-<UTC start>` files next to itself
and never overwrites one. Each run's report lists the exact qmd commands and environment.
`--arm-b-query-timeout` (default 240 seconds) is only a hang guard; on a busy host, raise it before
the run starts, as the 2026-09-26 restart did. Ctrl-C (SIGINT), SIGTERM or SIGHUP stops a run: the
runner kills a qmd call that is still running, writes all three files with status
`aborted_interrupted` and then ends by that signal.

## Known limitations

- Arm A is QMD's lexical `search` command as research workers call it, not BM25 in general. It
  returned no candidates for 22 of the 30 queries in every run. The decision compares QMD's hybrid
  `query` with QMD's lexical `search`; a relaxed or disjunctive BM25 baseline over the same index
  is a separate comparison that has not been run.
- 30 queries over 33 short documents, judged by one rater. This measures retrieval quality only,
  not answer quality, latency at scale or provider-token cost.
- Arm B ran on CPU on a shared host. The 2026-09-26 latencies reflect unrelated load on that host
  (Amendment 2) and are not a latency measurement.
- `qmd bench` is QMD's own command and scorer, but its fixture is derived here, its scorer
  lowercases paths and accepts suffix matches in either direction, and its precision@k divides by
  min(k, expected files). It ran after Arm B on the same index, so QMD's LLM cache may have served
  its expansion and rerank results. Its latencies may therefore be warm, and its `full` backend is
  not an independent replication of Arm B's model calls. QMD records a backend call that throws
  as an empty result with every score zero
  ([`runQuery`](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/bench/bench.ts#L177-L196)),
  so neither the output nor `run.py`'s completeness rule can tell a failed backend call from one
  that found nothing.
- The chronology evidence is an attested extract of private records on the authoring host.
- The 2026-09-25 runner saw Arm A's results for all 30 queries, and Arm B's for `kw-02`, before
  its official run (PREREGISTRATION.md, 2026-09-26 corrections).
- The three comparison receipts (`results-20260925.json` and both 2026-09-26 receipts) record
  `hf_content_store_etag` as `null`, because the runners that wrote them looked for QMD's ETag file
  under the wrong name.
- The committed `run.py` has made no run against the real qmd, and neither revision after efba31d5
  has made a full comparison run. The committed revision's behaviour was checked only with a stub
  qmd; the tests also send real signals to a child process. `run.py` 0792745e made three real-qmd
  runs, committed in `repair-review-20260926/`, that stopped before any model was loaded. Killing
  a real qmd query or embed that is still running was not exercised.
- QMD's own test suite was not run. `test/eval.test.ts` and `test/eval-harness.ts` (over
  `test/eval-docs/`) and `finetune/eval_retrieval.py` evaluate QMD on QMD's own six-document
  corpus from a git checkout; they are not part of the npm package and say nothing about this
  corpus.
