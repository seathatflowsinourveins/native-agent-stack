# Local models of the new WSL: the preregistered measurement and its records

The two local-model slots of the definitive manifest, `local-generation-model` and `embedding-model`, were split to a named
measurement. It ran on 2026-10-02 and 2026-10-03 in a throwaway Ubuntu 26.04.1 distribution on the workstation (RTX 4090,
24 GB), under a preregistration that was written before any trial and hashed at every amendment. Its results settle both
slots: the decision record is [`docs/decisions/2026-10-03-new-wsl-local-models.md`](../../../docs/decisions/2026-10-03-new-wsl-local-models.md),
the settlements are in [`../new-wsl-definitive-defaults-20261001/settlements.json`](../new-wsl-definitive-defaults-20261001/settlements.json),
and the install rows are in [`../new-wsl-install-plan-20261002/`](../new-wsl-install-plan-20261002/README.md).

| Slot | Measured default | Deciding result |
| --- | --- | --- |
| `local-generation-model` | Swift-1.5-Qwen3.8-27B IQ3_S on Ollama 0.35.0 as `swift-iq3s-s2o-64k` (context 64,000) | first-pass valid tool calls 200 of 200 against 175 of 200 for gpt-oss:20b; difference 0.125, 95% interval 0.065 to 0.19 |
| `embedding-model` | qwen3-embedding:0.6b (Q8_0) on Ollama 0.35.0 as `qwen3-embedding-8k` (context 8,192) | nDCG@10 0.49827 on CQADupstackUnixRetrieval; minus EmbeddingGemma 0.084331 [0.067738, 0.100656]; Nemotron-3-Embed-1B ties (0.003124 [-0.012194, 0.018141]) and needs a second server |

Both are local integration checks on one workstation, not acceptances on the destination distribution. The limits are in
each receipt's `limitations` and in the preregistration.

## Files

| File | What it is |
| --- | --- |
| `PREREGISTRATION-local-models.md` | The preregistration with every amendment, deviation and result, as a sanitized copy ([COPY-NOTES.md](COPY-NOTES.md)) |
| `PREREGISTRATION-local-models.sha256` | Its hash chain: 16 entries, each posted before the step it names |
| `COPY-NOTES.md` | The original's and the copy's sha256 and every replacement |
| `part-a-receipt.json` | Receipt for the generation slot (Part A and its extension): arms, gates, A2 results, decision statistic, deviations, limitations |
| `part-b-receipt.json` | Receipt for the embedding slot (Part B): arms, gates, nDCG@10, decision statistics, deviation 4, limitations |
| `part-a/logs/<run>/validity.jsonl` | Per-case results of the four scored A2 runs (`s2o-chat`, `c-chat`, `s2o-responses`, `c-responses`): case id, valid, reason, number of tool calls, the package's own score, error flag, seconds; the last line is the run's summary |
| `part-a/bootstrap.txt` | The A2 decision statistic as the measurement printed it (`raw/M18-bootstrap.txt`) |
| `part-b/runs/<run>/per-query.jsonl`, `per-query-summary.json` | Per-query nDCG@10 of E1, E2 and E3 over the 1,072 queries, and gate C's summary |
| `part-b/bootstrap.txt` | The Part B decision statistics as the measurement printed them (`raw/PB-bootstrap.txt`) |
| `scripts/a2/` | The frozen A2 scorer (`a2_validity.py`), statistic (`a2_bootstrap.py`), runners (`a2_run_bfcl.sh`, `a2_run_client.sh`) and client tasks (`a2_tasks.py`) |
| `scripts/partb/` | The Part B arm builder, runner, fit gate, per-query scorer, statistic and two self-tests of amendment 4a |
| `scripts/steps/` | The steps that ran A1 (`M6-a1.py`), A1b (`M6-a1b.py`), G0 (`M10-g0-setup.sh`, `M11-g0-run.sh`, `M11p-precheck.sh`), A1 of the extension (`M14-a1-ext.py`), both statistics (`M18-bootstrap.sh`, `M23-partb-bootstrap.sh`) and the Part B window (`W-partb-window.sh`) |
| `reconstruct_s2o_modelfile.py` | Rebuilds the measured Swift Modelfile from the Ollama library's blobs and writes or checks the install plan's copy |
| `files.json` | Every file of the measurement folder: the published copies with both hashes, and the 196 private files by path, size and sha256 |

The step scripts and runners name the measurement distribution's own paths (`$HOME/measure/...`) and its services; they
document what ran and are not meant to run elsewhere unchanged. The two statistics are pure standard-library programs and do
run on the published copies.

## Reproducing the decision statistics

From this folder, on the published records alone (no model, no network):

```sh
python3 -B scripts/a2/a2_bootstrap.py S2o C \
  chat=part-a/logs/s2o-chat/validity.jsonl,part-a/logs/c-chat/validity.jsonl \
  responses=part-a/logs/s2o-responses/validity.jsonl,part-a/logs/c-responses/validity.jsonl
cd part-b/runs
python3 -B ../../scripts/partb/partb_bootstrap.py --challenger E1-pb1 --baseline E2-pb1
python3 -B ../../scripts/partb/partb_bootstrap.py --challenger E3-pb2 --baseline E1-pb1
python3 -B ../../scripts/partb/partb_bootstrap.py --challenger E3-pb2 --baseline E2-pb1
```

On 2026-10-03 (Python 3.13.15) each printed the same line as the corresponding line of `part-a/bootstrap.txt` and
`part-b/bootstrap.txt`. That shows the published records and scripts give the recorded statistic; it does not re-measure
anything.

## The Modelfiles of the install plan

The install plan creates both models from Modelfiles carried in this repository
(`../new-wsl-install-plan-20261002/models/`):

| Modelfile | sha256 | Relation to the measured file |
| --- | --- | --- |
| `swift-iq3s-s2o.Modelfile` | `f6522bf4934aaa4f60231a042a8dfb781a7f5b3b1abc5053757f37169772ea9e` | the measured file (sha256 `8911245e…`) with its FROM line, an absolute path in the throwaway distribution, replaced by `FROM ./Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_S.gguf` (relative to the Modelfile, as Ollama's Modelfile reference allows) |
| `swift-iq3s-s2o-64k.Modelfile` | `6d15fee40e089b73961262647352c3443a03fa643122a92ca7a0b59376793d8e` | byte-identical to what the measurement's `printf` wrote (`FROM swift-iq3s-s2o`, `PARAMETER num_ctx 64000`) |
| `qwen3-embedding-8k.Modelfile` | `a1e149022bb8bb7030eda3350d0e768ae92e2a0c8581408dbb2746aaa6f7fe06` | byte-identical to what the measurement's `printf` wrote (`FROM qwen3-embedding:0.6b`, `PARAMETER num_ctx 8192`) |

The measured Swift Modelfile was not retained, so `reconstruct_s2o_modelfile.py` rebuilds it: it fetches the library model
`qwen3.8:27b`'s manifest and its config, params and licence blobs from `registry.ollama.ai`, checks each against the digest the
measurement recorded (manifest `aaee06c3…`), renders `ollama show --modelfile` as Ollama v0.35.0's source renders it (the
lines are cited in the program) with the parameter order the measurement's own call printed, and removes the lines that
begin with `FROM ` or `# FROM `, as the measurement did. Run with the measurement's original FROM line (a private path) it
gives `8911245e…`, the recorded sha256; run with `--check` it confirms that the install plan's copy is the reconstruction.
The licence block in that Modelfile is the library model's Apache-2.0 text; the Swift file's own licence is the
publisher's (Swift Open License v1.0, with the original Qwen parts under Apache-2.0). It is recorded, not judged.

## What stays private

Raw model outputs and everything that names the workstation stay in the private measurement folder and are listed by
sha256 in `files.json`: the Inspect evaluation logs (`.eval`, up to 444 KB each), the client tasks' run records, the server
logs, the window log, the run records of Part B (whose error texts carry the throwaway's paths) and the three prediction
files of about 31 MB each. The retained copy of the throwaway's outputs (`retained-throwaway/`) has the combined digest
`bfd683a89316c30b58a598c44c7e135da9c523c3e47322e5bab04b59cca719d4`, recomputed for this folder.

The artifact map that the other lane's read asked for is private as well:
`wsl-architecture-design-local-models-artifact-map-20261003.md`, 32,231 bytes, sha256
`bd269c02545d39a23bedaf1893de254b572065108d2f8a6581942b8f15d0237f`. It gives the locator, hash, time window and exit
lines of 175 artifacts; `files.json` lists every file of the folder, including those the map leaves out.

## Evidence class

Both receipts are local integration checks in the sense of
[`docs/acceptance-evidence-policy.md`](../../../docs/acceptance-evidence-policy.md): the cases (BFCL through inspect-evals,
CQADupstack through MTEB) and the runners (Inspect AI, MTEB) are upstream and unchanged; the validity scorer, the per-query
scorer, the bootstrap programs and the client tasks are this measurement's own code, published here. They are not
upstream tests and not an acceptance on the destination distribution. The install plan's checks of the two model rows (the
created models' layers, `ollama show`, one short generation, one embedding call) have not run there, and they do not test
whether the two models are resident together on the GPU.
