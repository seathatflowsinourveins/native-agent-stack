# Results of the frozen 8-K item-extraction comparison (2026-09-26)

**Evidence class.** Native execution on host `nativestack-5975wx-20260925` (WSL2,
RTX 4090, llama.cpp b11146), one run per arm, under the frozen protocol in
[`../plan.json`](../plan.json). The unchanged [`../analyze.py`](../analyze.py), whose SHA-256 equals
the frozen value in `plan.json`, wrote [`decision.json`](decision.json) from the
retained private state. A second run of it reproduced that file byte for byte. Speed and memory numbers
are this host's, under its load at the time: a shared WSL2 desktop with the
Windows-side GPU applications closed for each window. They are not isolated
benchmarks, and no arm was run twice, so run-to-run variance is unmeasured.

## Decision

`final: true`. **C2 is selected, with outcome `change_serving_profile`.** C1 and
C2 both met all four criteria, and C2 is the faster of the two. M failed
criterion (1), so its outcome is `retain_control`. The coordinator then moved
production to the C2 profile at 11:05:40Z; see the
[operations record](#operations-record).

## Per-arm results

360 filings per arm. All three Qwen3.8-27B arms (C0, C1 and C2) run the same
file. Peak device memory is the whole device from 1 Hz `nvidia-smi` samples,
which includes the embeddings service and the Windows side.

| Arm | Window | Micro-F1 | Macro-F1 | Exact match | JSON-valid | Median decode tokens/s | Median TTFT ms | Peak device MiB (min free) | Cold load s | Outcome |
|---|---|---|---|---|---|---|---|---|---|---|
| C0 control | `w-20260926T050938Z` | 0.9909 | 0.9867 | 0.975 (351) | 1.000 | 5.25 | 11,378 | 16,345 (7,798) | 3.950 | control, failure-free |
| C1 | `w-20260926T093317Z` | 0.9909 | 0.9867 | 0.975 (351) | 1.000 | 8.40 | 4,492 | 20,083 (4,060) | 3.662 | `change_serving_profile`, not selected |
| C2 | `w-20260926T102638Z` | 0.9909 | 0.9867 | 0.975 (351) | 1.000 | 26.28 | 4,355 | 20,314 (3,829) | 3.135 | **`change_serving_profile`, selected** |
| M | `w-20260926T093317Z` | 0.9670 | 0.9512 | 0.947 (341) | 1.000 | 80.16 | 434 | 15,621 (8,522) | 12.335 | `retain_control` |

Macro-F1 averages the 12 codes that at least five filings declare. The decision
file keeps full precision and the per-code F1.

**Paired bootstrap** of micro-F1(arm) − micro-F1(C0): 10,000 resamples, seed
20260926, nearest-rank 2.5th and 97.5th percentiles.

| Arm | Lower | Point | Upper | Lower ≥ −0.02 |
|---|---|---|---|---|
| C1 | 0.0 | 0.0 | 0.0 | yes |
| C2 | 0.0 | 0.0 | 0.0 | yes |
| M | −0.0560 | −0.0240 | −0.0049 | **no** |

C1 and C2 predicted the same item set as C0 for every one of the 360 filings,
so every resampled difference is zero. M's prediction differed from C0's on 11
filings.

| Arm | (1) non-inferior micro-F1 | (2) faster median decode | (3) JSON-valid ≥ 0.98 | (4) no memory or deadline failure |
|---|---|---|---|---|
| C1 | pass | pass | pass | pass |
| C2 | pass | pass | pass | pass |
| M | **fail** | pass | pass | pass |

### Why M failed

M missed only the quality criterion, but it missed it clearly. Its micro-F1 was
0.9670 against C0's 0.9909. The bootstrap lower bound of −0.0560 is well below
the −0.02 margin, and even the upper bound (−0.0049) is below zero, so M was
worse than C0 on this workload at the 95% level. It matched fewer filings
exactly (341 against 351 of 360). It predicted more spurious codes (mean
precision 0.9805 against 0.9949) and missed more declared ones (mean recall
0.9886 against 0.9937). Its per-code F1 was lower on 10 of the 12 macro codes,
for example 2.01 (0.880 against 1.000), 2.03 (0.857 against 1.000) and 3.03
(0.889 against 0.941), and equal on 2.02 and 5.03. M was by far the fastest arm
(80.16 median decode tokens/s, 434 ms median TTFT) and every reply was valid
JSON. Under the rule, speed alone does not pass.

### Counts from the retained metrics

These come from each arm's `eval/metrics.json`, which holds accession numbers,
item codes and timings but no document text.

| Arm | Prompt tokens | Completion tokens | MTP drafted / accepted | Request time, sum s | Request time, median s |
|---|---|---|---|---|---|
| C0 | 726,255 | 6,048 | – | 6,175 | 14.26 |
| C1 | 726,255 | 6,048 | – | 2,741 | 6.28 |
| C2 | 726,255 | 6,048 | 4,737 / 4,735 | 2,145 | 4.94 |
| M | 725,535 | 6,240 | – | 255 | 0.64 |

In every arm, all 360 requests returned HTTP 200 with `finish_reason` stop and
a JSON-valid reply. No arm had a context overflow, an unattempted filing, or a
guard, server-error or deadline event. There was no prompt-cache reuse, since
the frozen request sets `cache_prompt: false`. C0 finished in one segment,
rather than the two the plan expected.

## Acquisition

[`acquisition-summary.json`](acquisition-summary.json) is the run's own summary,
copied unchanged. It holds counts and hashes only, with no contact identity.

- `acq-20260926` ran from 05:02:27Z to 05:06:02Z and finished `complete`. The
  daily-index SHA-256
  `5865f91e3d68590389b08760ea256fbaa1693fbc1b0e1350142fc3634a9c3383` and the
  cohort counts (371 rows, 360 accessions, 362 8-K and 9 8-K/A rows) match the
  plan.
- It made 721 requests at no more than 5 per second, with no automatic retries.
- All 360 accessions were eligible: 0 acquisition failures, 0 empty primary
  documents and 0 zero-item headers. As a diagnostic, EdgarTools' own choice of
  primary document matched the extracted document for all 360.
- 11 inputs were cut to the 16,000-character cap. The capped inputs hold
  1,893,730 characters in total. Before the cap, the median input was 3,941
  characters and the longest was 29,508. `inputs_sha256` is
  `2a5c8c9bd1650bc20a3e7364defef2d725904f6eb1ef509a511a49526a32bfe0`.
- **The first attempt was refused** with `state_dir_must_be_owner_only` before
  any SEC request, because the existing state directory was not owner-only. The
  refusal comes before `acquire.py` creates the run directory. The coordinator
  set the directory to 0700 and reran with the same run id. That attempt's exit
  status was not retained.

## Windows

[`runs/`](runs/) holds each window's `window-summary.json` and each arm's
`window.json`, copied unchanged.

| Window | Arms | UTC | Free MiB before / after production stop / after restore | Production |
|---|---|---|---|---|
| `w-20260926T050938Z` | C0 | 05:09:38–06:52:50 | 7,808 / 17,334 / 7,930 | restored, health ok, restore timer cancelled |
| `w-20260926T093317Z` | C1, C2, M | 09:33:17–10:23:41 | 16,928 / 17,366 / 7,930 | restored, health ok, restore timer cancelled |
| `w-20260926T102638Z` | C2 | 10:26:38–11:02:50 | 8,559 / 17,995 / 8,559 | restored, health ok, restore timer cancelled |

Admission, from each arm's `window.json`:

| Arm | Window | Needed MiB | Free MiB | Result |
|---|---|---|---|---|
| C0 | 1 | 16,384 | 17,334 | completed |
| C1 | 2 | 17,151 | 17,366 | completed |
| C2 | 2 | 17,535 | 17,366 | **refused** |
| M | 2 | 16,384 | 17,366 | completed |
| C2 | 3 | 17,535 | 17,995 | completed |

Every started segment finished with server exit 0, `MemoryMax` 20G verified and
no guard events.

**The C2 admission refusal in window 2 is retained.** At the window start,
production was idle-sleeping (`--sleep-idle-seconds 600` unloads the model),
with about 438 MiB loaded. Stopping it therefore freed far less than the
9,478 MiB that the window's start prediction adds, and the measured check
before loading refused C2. Per the plan, a refusal starts nothing and may be
retried. C2 ran in window 3, after more Windows-side applications were closed.

## Not run: B and X

These follow [`../plan.json`](../plan.json). **B** (PrismML Ternary Bonsai 2 27B,
PTQ1_0) and **X** (Xing4.0-29B-A4B, IQ4_NL) are `runtime_unsupported` on b11146.
The pinned runtime has no `ptq1_0` or `pq2_0` tensor type, and B's card requires
the PrismML fork. It also has no `xing4_0` architecture. Neither was downloaded,
and `decision.json` lists both under `arms_not_run` with no attempts. They
re-enter only under a new frozen plan with a pinned runtime that supports them.

Three candidates were never arms, and none has a result:

- Qwen3.8-Flash-Next is `resource_infeasible`.
- The tasked C1 profile (`--gpu-layers 99` without FFN offload) is
  `resource_infeasible_on_host`.
- The tasked C2 profile (the same plus the MTP draft file) is also
  `resource_infeasible_on_host`.

## Operations record

This is from the coordinator's dated log. Paths are relative to the systemd user
configuration directory.

- **05:01Z.** M was downloaded at the pinned revision: 9,527,498,048 bytes,
  SHA-256 `de6dae10334e088876358ef9f574835bb3b401ea2ecf5d6a9473f37894df6b73`,
  equal to the pin. Before window 1, `verify-arms` (C0 and M), `verify-frozen`
  and `verify-inputs` (360 filings) passed.
- **05:02–05:06Z.** Acquisition, after the refused first attempt above.
- **05:08:35Z–05:09:12Z.** Windows-side GPU memory was freed, from the README's
  frozen image list only:
  - A graceful `taskkill /IM` for chrome.exe, wallpaper64.exe, wallpaperui.exe
    and MuMuVMMHeadless.exe closed wallpaperui (6 processes).
  - `taskkill /F /IM` then closed chrome.exe (155 processes at enumeration),
    wallpaper64.exe (1) and MuMuVMMHeadless.exe (1).
  - dwm, explorer, WindowsTerminal, vmwp and TradingView were kept.
  - Device use fell from 19,759 to 16,335 MiB, and free memory rose from 4,384
    to 7,808 MiB.
  - **Deviation:** README step 3 says to close each process by PID. These were
    closed by image name, and the second pass was forced.
- **Window 1 (C0), 05:09:38Z–06:52:50Z.** The log does not record the checkout
  revision. `window.sh` verified every frozen hash before it started, and the
  metrics record the plan and prompt hashes, which `analyze.py` checks.
- **Window 2 (C1, C2, M), 09:33:17Z–10:23:41Z,** from origin/main `b5c6313b`,
  where the experiment files equal those merged in #323 and #326. The
  frozen-list applications were still closed.
- **10:24:10Z–10:26:16Z.** More Windows-side applications were closed for C2.
  - **Deviation:** these were outside README step 3's list. The log records the
    user's approval ("all can be closed").
  - Closed: ChatGPT.exe (11 processes), cloudmusic.exe (3), steam.exe (1),
    steamwebhelper.exe (8), and then TradingView.exe (32; it was Saturday, with
    the markets closed).
  - The Claude desktop app, dwm, explorer, WindowsTerminal, vmwp and the
    embeddings service were kept.
  - Device use fell from 16,213 to 15,584 MiB, and free memory rose from 7,930
    to 8,559 MiB.
- **Window 3 (C2), 10:26:38Z–11:02:50Z.** Predicted free memory was 18,037 MiB
  against the 17,535 MiB needed.
- **About 11:03Z.** `analyze.py` (origin/main `b5c6313b`) returned final, with
  C2 selected.
- **11:05:40Z, production switch.** A drop-in,
  `nativestack-generation.service.d/li26-c2-serving-profile.conf` (mode 0600),
  resets `ExecStart` and sets it again. Relative to the base unit, it makes
  exactly four changes:
  - `--gpu-layers` changes from 36 to 99;
  - `--n-cpu-ffn 20` is added;
  - `--spec-type draft-mtp` is added;
  - `--spec-draft-n-max 3` is added.

  The other 23 options are unchanged. They include the model, `--ctx-size 8192`,
  `--sleep-idle-seconds 600`, the API key file and the unit's sampling and
  reasoning defaults. A read-only comparison of the two `ExecStart` lines,
  made after the switch and before the receipts below, confirmed this without
  printing their values.
- **After the switch.** The coordinator ran `systemctl --user daemon-reload` and
  restarted the unit. `/health` returned 200 after about 6 s. `checks.py
  llama-cpp` returned the structured answer 42 (usage 20 + 7 tokens) in 0.99 s.
  The device showed 20,256 MiB used and 3,887 MiB free, with `NRestarts` 0.
- **Rollback.** Remove the drop-in, run `systemctl --user daemon-reload`,
  restart `nativestack-generation.service`, and check that `/health` returns
  200. The base unit file (36 GPU layers) is unchanged, and the model file stays
  installed.
- **11:26Z.** The llama-cpp install and use host receipts were recorded read-only
  under `evidence/hosts/nativestack-5975wx-20260925/`. The use receipt re-reads
  the served profile and the model hash, and runs `analyze.py` again, which
  reproduces `decision.json`. The switch is recorded in
  [`evidence/receipts/local-inference-c2-serving-switch-20260926.json`](../../../../evidence/receipts/local-inference-c2-serving-switch-20260926.json).

## Retained private state

The private state lives under `$LI26_STATE`
(`~/.local/state/native-agent-stack/local-inference-latest-20260926/`, with 0700
directories and 0600 files) and is not in the repository. The table gives the
metrics and memory files that `analyze.py` read; they hold no document text.

| File | Bytes | SHA-256 |
|---|---|---|
| `runs/w-20260926T050938Z/C0/eval/metrics.json` | 240,815 | `9ec68be7f4b7ce635615719eeb48308b947d61ed5dec88b451b53882e44984c1` |
| `runs/w-20260926T050938Z/C0/memory.csv` | 146,250 | `4dbaaa521d150da111471c8f10ff49e5fcca67f67ef1133e3a28a98acb0cc6fa` |
| `runs/w-20260926T093317Z/C1/eval/metrics.json` | 240,306 | `4fe790258b655ed8ca4de464e05fd6f0c50fc111d35fb8c933aa326ec0637351` |
| `runs/w-20260926T093317Z/C1/memory.csv` | 64,350 | `cbb2a01fd505f3510a24b42135ff384609e9c768a6a19b4aeeddc51809e41d83` |
| `runs/w-20260926T093317Z/M/eval/metrics.json` | 239,543 | `7cb9046ac80551a279006fe75cfc69ce932a3632d9b70c7a3d7661ca5c8077a1` |
| `runs/w-20260926T093317Z/M/memory.csv` | 6,250 | `085a4fa44cd76a91724556ff75fb70b2224e6b5fd851865ad676ac5575a7eb9a` |
| `runs/w-20260926T102638Z/C2/eval/metrics.json` | 238,700 | `0e0ebd71090180d905bb7e6fdce435d00e86d5cccba8233164419ef1cdad83a2` |
| `runs/w-20260926T102638Z/C2/memory.csv` | 50,475 | `36fbc6c7b79d73bce98e7eb5a34cb3f753ad0f2fcfe4db02ea6b358714692052` |

The acquisition's `manifest.json` and model inputs are pinned by the
`manifest_sha256` and `inputs_sha256` fields of the summary. Eight
`*.private.*` files, holding raw replies and server logs, stay private and are
not summarized here.

## What these results do not establish

- **Other workloads.** They do not establish quality or speed for production's
  own requests. The unit keeps its sampling and reasoning defaults, while every
  arm here decoded greedily with thinking disabled and replied with about 17
  tokens.
- **MTP beyond this protocol.** MTP accepted 4,735 of 4,737 drafted tokens on
  these short JSON replies. Sampled or thinking replies may accept fewer, so
  C2's decode gain is established only for this protocol.
- **Device memory in normal use.** C2 left at least 3,829 MiB of the device free
  while Windows-side applications were closed. Production has no free-memory
  guard like the window's 3,072 MiB reserve, so Windows-side GPU applications
  reopened later can exhaust device memory.
- **Other claims.** They do not establish frontier parity, accuracy against
  hand-checked labels, catalyst or trading value, historical availability,
  long-context quality, isolated throughput, or any saving.
- **The tasked profiles, B and X.** There is no result for the tasked C1 and C2
  profiles, or for B and X.

## Files

| File | What it is |
|---|---|
| [`decision.json`](decision.json) | The frozen analysis output, copied unchanged. It declares `no_document_text`, and its only long string is the rule text from `plan.json`. |
| [`acquisition-summary.json`](acquisition-summary.json) | The acquisition summary, copied unchanged. |
| `runs/<window>/window-summary.json` | Each window's summary, copied unchanged. |
| `runs/<window>/<arm>/window.json` | Each arm segment's record, including the refused C2 attempt, copied unchanged. |
