# Memory stack: cross-family convergence evidence (2026-09-25)

Sealed evidence for [`catalogs/foundation/memory-stack-20260925.json`](../../../catalogs/foundation/memory-stack-20260925.json): which
memory systems, embedders, rerankers, memory LLMs and local serving runtimes the one shared
Claude Code and Codex memory should retain, trial, defer or reject. Two frozen packets (a model
screen and a memory-system screen) each went to two blind lanes, Claude Opus 5.5 and Codex GPT-6
Astra. Three roles (memory system, memory LLM, reranker) went to a blind GPT-6 Sol judge in three
presentation orders. The coordinator's convergence table sets each row, two skeptic checks per row
reviewed it, and neutral Mac measurements in the preregistered LongMemEval-S harness bound the
memory-system and embedder rows. Nothing was installed, downloaded, promoted or reconfigured; no
row is adopted, and "best" never means state of the art in general.

The packets, the four lane returns, the nine judge briefs and verdicts, and the stage-one notes are
each embedded unchanged as a JSON string (UTF-8, LF) beside a transcription whose strings are
substrings of the source; the embedded text is authoritative and hashes to the original sha256
below. The convergence table is embedded with the coordinator's two home-relative checkout paths
replaced by placeholders; putting them back restores its original sha256. The originals stay
outside the repository. Not copied: the Codex event streams and stderr, the judges' event streams,
the convergence workflow's structured result and the proposed CLAUDE.md text, which hold local
paths or thread identifiers or are machine-specific configuration; the counters, commands and
corrections taken from them are in `usage.json`, the lane returns, `convergence.json` and
`provenance.json`. Runs are named by label only.

| File | sha256 | Original (sha256) | Content |
| --- | --- | --- | --- |
| `packets/sota-models.json` | `8d6f1fe60f4cd2052bf647ac53571839008dbe1c2eeb0fe0966dc8c397ec28f5` | `sota-models-packet.md` `1847b3a1a0508078076f8d114e9ea1a021a92f8322f8e13e4f2482ca18f5a51a` | the frozen model-screen packet, verbatim, with its output contract |
| `packets/memory-systems.json` | `63f5361e20fa4ef52a7110b71c36ed748f7fe168c177590c807bc61f709ffdba` | `memory-systems-packet.md` `31318b2121b387e4a478456a5b794e6bf1119d100f9cb3aeeb96c17f19e6e807` | the frozen memory-system packet, verbatim, with its output contract |
| `claude/sota-models-lane-return-1.json` | `b0bc3c145c4ac2bf20e95d1fe79e20afd5661b6c7afc25cd7eb24b9911bdc7cf` | `sota-models-claude.md` `bd99a4468233d8456899474be6457ac80e2dea3a509fedfc8915e4814b870cd7` | Claude lane return, verbatim, with a substring-checked transcription |
| `claude/memory-systems-lane-return-1.json` | `6d1c522475b5bce6350d19a7a89b178d3dfe8dd09d4144eb9335595faa7b53b6` | `memory-systems-claude.md` `fe609037bee332a597c554c09f03f15b3c3637108ab033e130fe35adbdf43d9d` | Claude lane return, verbatim, with a substring-checked transcription |
| `codex/sota-models-lane-return-1.json` | `6b6579d91f1a0d3b11fbd28a9cbeb1e31f92961eea9ba56a7957e136b51ce3c9` | `sota-models-codex.md` `a3fa6b77be06cb7456c6c41f95a315a8d506d62e3b277aa7d1704544aeb737f0` | Codex lane return, verbatim, with a substring-checked transcription and event-stream counts |
| `codex/memory-systems-lane-return-1.json` | `5166806f08076904f3990d17d739217eec2d05776452c6f57e9450e6b0015823` | `memory-systems-codex.md` `2eb2fa3b78e8aad04ff1cc7db9175dc213df8e1eafa726ddbd12a85820d948cf` | Codex lane return, verbatim, with a substring-checked transcription and event-stream counts |
| `adjudication-inputs/q1-memory-system-a.json` | `dcfe6a1db362c4555de62683db601602668e3e22b9d63aa94ec608d9da1e6db7` | `q1-memory-system-a.md` `1c40278e0feaf89a6e449fb8dc5b41c28984f1fbb91f52cad4401cc7f29c29ad` | blinded judge brief, order a, verbatim, with the return offsets |
| `adjudication-inputs/q1-memory-system-b.json` | `8aaa24e7418cd4da2d26d47dc7a27827a539ada0fd9133c9c6994bd29ec2a3b6` | `q1-memory-system-b.md` `06069691dafa39565e75e9a1ced103c7efc4c0c359a6e2670d4afd2326bb05fb` | blinded judge brief, order b, verbatim, with the return offsets |
| `adjudication-inputs/q1-memory-system-c.json` | `25101afbbd159b0485ec0f3df2665ab3e77cb5a2ccb2a39883de63f06c5fc328` | `q1-memory-system-c.md` `efb4ac7e4c63f6eadfa334f1180b1d3aaec45a2b3bed75f2e2ef866f8ef38672` | blinded judge brief, order c, verbatim, with the return offsets |
| `adjudication-inputs/q2-memory-llm-a.json` | `113ddece701e6f647151cdb7b2ad505ebcfe8e6f8d6b7c4676644f876859f8ab` | `q2-memory-llm-a.md` `4209e482980f68a062ed570b02a235d538266cbd976d0e3c91cee4efb0b378ce` | blinded judge brief, order a, verbatim, with the return offsets |
| `adjudication-inputs/q2-memory-llm-b.json` | `b4ea294ef737848d396d5b016f11cbb36f506e31f1787c813b6573c10c16c0a4` | `q2-memory-llm-b.md` `159751e31bfcc9d750b1697158c855101c17fddcb2c777b38482ac8a57acdf63` | blinded judge brief, order b, verbatim, with the return offsets |
| `adjudication-inputs/q2-memory-llm-c.json` | `ade78033b5932c1aeb7ba6bd33f62eef92d3ffe33ed4e0a80bca561ec1155a1f` | `q2-memory-llm-c.md` `316938aea9967e5d750834e98fe8f375a4f6d38166a30207774bd1413aeb8546` | blinded judge brief, order c, verbatim, with the return offsets |
| `adjudication-inputs/q3-reranker-a.json` | `11a3d119ff06592d33d1475d35d02df90ec4f129aac67c2b176fe4802012b6c6` | `q3-reranker-a.md` `daa4178b5a7bd45885ddc0eac970f9055bde60241d8d6e05d0085858a045b3f6` | blinded judge brief, order a, verbatim, with the return offsets |
| `adjudication-inputs/q3-reranker-b.json` | `f83257ee3d725d531b251324a091286e720336097938fc86701a5d18322dd2b0` | `q3-reranker-b.md` `d6d32c9d80e282a880661553ecab56a9c190ca48fe82313863d766e6c0903422` | blinded judge brief, order b, verbatim, with the return offsets |
| `adjudication-inputs/q3-reranker-c.json` | `d26a14c6f2aac0bce5d5a262a5e98f02d50655225c3f97ee0cf4edeeba8d41e3` | `q3-reranker-c.md` `d7dbf218d428e7105e53646e6ea27dc0ce9e16f57539a80f12350fb40b81eeaa` | blinded judge brief, order c, verbatim, with the return offsets |
| `adjudication-inputs/adjudication-key.json` | `2882221c9e895964190830c28449107a8a6fd151cf2eae7f9c1558e7d538ad51` | `adjudication-key.json` `1eed64c0c60abbcd01239b9c793070d7aef8ef958bb89ee86ba1ff185d696040` | the key (which lane is A and B, and which is listed first, per order), with local paths reduced to file names, and the briefs' SHA256SUMS |
| `adjudication/q1-memory-system-1.json` | `c72f204af6acd931987b2a20ec0fc899757cb2cc102111602c9ed0ae755c2039` | `q1-memory-system-a.verdict.md` `4a8418f9ed808a14355b93da86268cd0f4b52b1860b4638e4812cb4029f6012d`; `q1-memory-system-b.verdict.md` `f4645e81cc6305edd437f9ccaca9103ec27dd2642ed4d0afbdb08a11e5cdb8b7`; `q1-memory-system-c.verdict.md` `a80b541211e096797794b0a25109af353847644a2cc45850be72f46c42e9f1fb` | all three judgments, each verdict verbatim, mapped through the key |
| `adjudication/q2-memory-llm-1.json` | `e16804649d0061eabda060e5164abbffd72753c11c9014033cd17a7272bff780` | `q2-memory-llm-a.verdict.md` `21d2e60533c30400252055f8d0268794a234c96ffa94f425e30c890eb6d0a7ba`; `q2-memory-llm-b.verdict.md` `53a0e12eea3f9c907e4681afb274ff43f50f3a76e57a667a2544c9474637798a`; `q2-memory-llm-c.verdict.md` `793b0469c8f519f7e316cf6b7698d3fa1444c780a91c789f7c6ff87827421a3e` | all three judgments, each verdict verbatim, mapped through the key |
| `adjudication/q3-reranker-1.json` | `c75539956c17030a7d8abcf72e1e87129e9ed81cb873e5f6d5755bc550f514e8` | `q3-reranker-a.verdict.md` `56d1527ae8d9bc7a170a1fd7ff19a6c0e135095ca7bcfdaaf144fc4984d03efa`; `q3-reranker-b.verdict.md` `a128fa1824b69dd51cd2586df974f2f4b662f0fb8a4a51a4b661bd9228533270`; `q3-reranker-c.verdict.md` `26bf571202c665f1bbd052252800d15944bfb9116eeec22b8c8bbaea318af873` | all three judgments, each verdict verbatim, mapped through the key |
| `convergence.json` | `48b3ae02c01eb71569599292e164a921fed0a3fc750e566259ef9f395471c0ed` | `convergence-table.md` `6d00a850f0fd63ea7c85010f701aa47a190ffb7e2ede56a6d16395bebb6c9070`; the two stage-one notes; `report-mac-descriptive.md` `62c0079136d575f21f5c96c5606bb2d84407ec94b13b7c525c3ebcb5cac3f120` | the convergence table (two checkout paths replaced by placeholders) with its tables parsed; the stage-one notes verbatim; the complete-arm Mac measurements; the cited amendments; the skeptic corrections and measurement updates |
| `usage.json` | `0a7be62925865c5d0db37ac1506b69c559b621db4c8c1fe7db6ebfd32084c31e` | extracted from the not-committed event streams and header lines | native usage counters per run and their contract mapping (recorder-written) |
| `provenance.json` | `6dfb775a100637f3432c4316f4a48176a2ca49d7c1c1fe701edb6ca11b317a01` | none (recorder-written) | original and public sha256, timeline, runs, blindness and what was not copied |
| `experiment.json` | `8f0dcd992d4bfc5193255a363dbfefa98d56d2734ad5620c0cd9350b70da358d` | none (recorder-written) | convergence record: lane memory, decision trial for the trial rows only |

Findings the record keeps:

- **Measurements (Mac, descriptive under A15.2).** C3, ai-memory with its production embedder and
  the reranker off, scores recall_all@5 0.570 on the full track (n = 470). Paired against it,
  agentmemory with MiniLM (+0.251, 95% CI [+0.203, +0.299]), dense Qwen3-Embedding-4B (+0.183), BM25
  (+0.177) and the official BM25 (+0.170) lead with Holm p 0.0001; keyless agentmemory (+0.047) does
  not separate. C4, production with the LLM reranker, did not run on the Mac, so the layer decision
  (A14) is open, and confirmatory decisions come only from the VelaNext rerun.
- **Judges.** The judge never preferred the Codex return; its only non-SPLIT answers came when the
  Claude return was letter A and listed first. The decisions rest on positions that hold in all
  three orders: trial agentmemory, MemPalace and Hindsight with ai-memory retained; Qwen3.6-35B-A3B
  then LFM2.5-2.6B with Qwen3.5-9B as control; MemReranker-4B first among three rerankers, none
  adopted.
- **Corrections.** Nine skeptic checks on seven rows refuted a claim or a next test (for example,
  Ollama did not serve every harness embedding arm: the MiniLM arms ran in-process). The recorder
  applied every such correction, named the LMEB source (LongMemEval task, nDCG@10, MTEB leaderboard
  API snapshot 2026-09-24) on every row citing it, and updated the rows C3 bears on. No decision
  changed.
- **Blindness.** The memory-system Codex lane read the ecosystem-catalog skill's instructions but
  queried no catalog; the Claude lanes' tool logs were not retained.
- **Records that postdate the table.** A16 was added to the preregistration at 02:15 EDT and C3
  finished at 02:32 EDT; both are dated addenda in `convergence.json`.

`SHA256SUMS` lists every file here except itself, with repository-relative paths
(`shasum -a 256 -c evidence/artifacts/memory-stack-20260925/SHA256SUMS`
from the repository root).
