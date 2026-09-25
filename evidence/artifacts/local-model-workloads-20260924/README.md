# Local-model workloads: cross-family discovery evidence (2026-09-24)

Sealed evidence for [`catalogs/us-equities/local-model-workloads-20260924.json`](../../../catalogs/us-equities/local-model-workloads-20260924.json): which local-model
workloads beyond memory and RAG are worth measuring on the 64 GB M5 Pro for the
US-equities north star and native agent engineering. Two blind lanes (Claude Opus 5.5
and Codex GPT-6 Astra) answered one frozen packet; their one disagreement went to a
blind GPT-6 Sol judge in three presentation orders (original, label-swapped, and a
reversed listing that put the skip return first); the coordinator's convergence table
sets each catalog decision. This is discovery evidence only: nothing was installed,
downloaded or executed for these items, and inclusion selects nothing.

The packet, both lane returns, all three judge inputs and verdicts, and the convergence
table are each embedded unchanged as a JSON string (UTF-8, LF) beside a parsed
transcription whose strings are substrings of the source; the embedded text is
authoritative and hashes to the original sha256 below. The originals stay outside
the repository. Not copied: the Codex lane's JSONL event stream and stderr, and
the judges' run logs, which hold a local working directory and session
identifiers; the counters, settings and prompt taken from them are in
`usage.json`, `provenance.json` and the judge inputs. Runs are named by label only.

| File | sha256 | Original (sha256) | Content |
| --- | --- | --- | --- |
| `packet.json` | `c72fc158ae8f74a1fb33dc606bd94ba16159a75c7cb111d71c47effa01435a02` | `local-uses-packet.md` `38586709f488bcbe0d2488f4d8c0fdbb8c41a99e1a0286c67ba6d6103ace5eb7` | the frozen packet, verbatim, with its output contract |
| `claude/lane-return-1.json` | `b30696c8e8720ae2d3bc04ca850304098f603874c8f2e79516b7f655185f6196` | `local-uses-claude.md` `e2c859abce553857ca3acd1e0cc754b9959644ef9c6acc4ff858805724b6f0b4` | Claude lane return, verbatim, with a substring-checked transcription |
| `codex/lane-return-1.json` | `5122de310479d12d674aaa49bbab09d7a61c4624fbce2a66b36405a50df21f77` | `local-uses-codex.md` `7b91aec490960d3734c34b8eed5f2c72a348b3701c2126d4bd68862915fd32e0` | Codex lane return, verbatim, with a substring-checked transcription and event-stream counts |
| `adjudication-inputs/a.json` | `43487581f6d0dc5f7e9b093121d16cc6c74aae473dd43071e333a0193c3ea5bc` | `tabular-question.md` `e48d77db14a6e8062498fa252d0a74c9e4a891c32e0e2a07bf1b611a592ead0b` | scrubbed judge input, original order (trial listed first), verbatim, with the judge prompt |
| `adjudication-inputs/b.json` | `dc1afd18b206521fa578d51c5d9f72f803d05eb3ff677f6575a1e9eab89d8058` | `tabular-question-swapped.md` `ac382709be36a34225e5dee1fa7e9a60d35b6ecb002f927faff622557df7b23f` | scrubbed judge input, label-swapped order (trial still listed first), verbatim, with the judge prompt |
| `adjudication-inputs/c.json` | `5ada31de5eeb9058ec79424a1df29f656f2c6fbd1cc0d77001daf22364e790f2` | `tabular-question-reversed.md` `4b21cc4f0c2a808c165b0e6ada943fb0a44e0da8a1b6c7747a41d05aa5bc74a5` | scrubbed judge input, reversed listing (skip listed first), verbatim, with the judge prompt |
| `adjudication-inputs/adjudication-key.json` | `631fdb341681d10cc139a8b888a032dcc2775e27fd15bbdba1c68b5f94f8ce0f` | none (recorder-written) | which lane is A and B, and which return is listed first, in each order (recorder-written) |
| `adjudication/tabular-skip-1.json` | `cfbfb077d09ef85a75edd583b0ff22bcfab07bc8c26d43c8113dc56aff54f546` | `tabular-question.verdict.md` `bc9d19d8b268915b7e298890f4e472376a3b1c95adfa386919378e13b42c0a15`; `tabular-question-swapped.verdict.md` `d9ad27c203b999f44796da38ce3947ea47efdff501cc73a0b58f51c6cc3f5dd9`; `tabular-question-reversed.verdict.md` `7c8d443a13adc191258e1fc6aa7929f532bc27b70836bc3b508e541756432865` | all three judgments, each verdict verbatim, in the layer-verdict judgments[] shape |
| `convergence.json` | `18768da848d2b5c114a0fc0922703d542298ab0a67a0a4c324900c14616d5675` | `local-uses-convergence.md` `78c79af25b46614abe0ea9aadfadbbfe296efefcc8493546ff3f21151e9553d2` | the coordinator's convergence table, verbatim, with its tables parsed |
| `usage.json` | `eea0ecfdfd6c022208f0c812dd634c7ba6fff4b0455e875dce017d051ba4ab73` | extracted from the not-committed event stream and run logs | native usage counters per run and their contract mapping (recorder-written) |
| `provenance.json` | `fb4ebf2dd0ede2c0c1c3f3dba1c1e7dbba6e75e7941048e6149d1543e2429ca9` | none (recorder-written) | original and public sha256, requested and resolved model and effort, run labels |
| `experiment.json` | `aa5ee859a6d49a125bfec54bb644cd96374d10274ecb936edb0f07b0717e4339` | none (recorder-written) | convergence record: lane local-inference, decision trial for the converged workloads |

Findings the record keeps: the Codex lane's stream shows no search naming the
excluded repositories; the label-swapped input still listed the trial return first,
so a third, reversed-listing judgment (run on a different ChatGPT account) put the
skip return first, and skip won in both listing positions; the convergence table
predates that run and carries a dated addendum; only the Codex lane's usage
categories are known, so the Claude and judge totals stay native in `usage.json`;
and the lanes' exit statuses were not retained.

`SHA256SUMS` lists every file here except itself, with repository-relative paths
(`shasum -a 256 -c evidence/artifacts/local-model-workloads-20260924/SHA256SUMS`
from the repository root).
