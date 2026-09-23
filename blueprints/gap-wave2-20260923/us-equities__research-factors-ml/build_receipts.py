#!/usr/bin/env python3
"""Write the research-factors-ml gap-wave-2 receipts, then results.json derived from them.

Usage: build_receipts.py UNITS_JSON
The gap text comes from the wave's unit list (data); preregistration entries are
copied verbatim from preregistration.json; raw-file hashes come from raw/MANIFEST.json.
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
EV = REPO / "evidence/artifacts/gap-wave2-20260923/us-equities__research-factors-ml"
BP = "blueprints/gap-wave2-20260923/us-equities__research-factors-ml"
CHECKED_AT = "2026-09-23T07:09:07Z"
# The last check output (run-fcmp-merged-r2/results.json) has mtime 2026-09-23T07:09:07Z; an earlier
# value, 07:15:00Z, post-dated the 07:11:23Z commit that carried it and was corrected on 2026-09-23 (after 13:37Z).
CHECKED_AT_NOTE = ("mtime of the last check output, $CACHE/run-fcmp-merged-r2/results.json. Corrected from 07:15:00Z, "
                   "which post-dated its own commit 01e6054 (07:11:23Z); correction written 2026-09-23 after 13:37Z.")
PRE = json.loads((EV / "preregistration.json").read_text())
MAN = {Path(f["path"]).name: f for f in json.loads((EV / "raw/MANIFEST.json").read_text())["files"]}
FIX1, FIX2, FIX3, FIX4, FIX5 = PRE["fix_rounds"]
L = "$HOME/.local/share/codex-ecosystem/tools/lean-985ef30"
C = "$HOME/.cache/gap-wave2-20260923/research-factors-ml"


def raw(*names):
    return [{"path": "raw/" + MAN[n]["path"].split("raw/", 1)[1], "committed_sha256": MAN[n]["committed_sha256"],
             "original_sha256": MAN[n]["original_sha256"], "uuids_redacted": MAN[n]["uuids_redacted"]} for n in names]


def prereg(gap, extra=None):
    entry = {"written_at": PRE["written_at"], "written_at_note": PRE["written_at_note"], "source": "preregistration.json gaps." + gap,
             "expectation": PRE["gaps"][gap]["expectation"], "criteria": PRE["gaps"][gap]["criteria"]}
    if extra:
        entry["fix_rounds"] = extra
    return entry


INSTALL = [
    "uv venv --python $HOME/.local/share/codex-ecosystem/python/cpython-3.13.15-linux-x86_64-gnu/bin/python3.13 " + C + "/venv",
    "ECOSYSTEM_JOB_SECONDS=900 ECOSYSTEM_JOB_MEMORY_MAX=8G ECOSYSTEM_JOB_MEMORY_HIGH=6G $HOME/codex-ecosystem/bin/ecosystem-bounded-run uv pip install --python " + C + "/venv/bin/python -r " + C + "/requirements.in   # skfolio==1.2.9 statsmodels==0.15.0 arch==8.0.0 statsforecast==2.1.1 chronos-forecasting==2.3.2 torch==2.13.0 einops huggingface_hub safetensors tqdm; exit 0 (third attempt: pandas==3.0.6 and alphalens were dropped because alphalens-reloaded 0.4.6 and statsforecast 2.1.1 require pandas<3; resolved pandas 2.3.3)",
    "uv venv ... " + C + "/venv-al && uv pip install --python " + C + "/venv-al/bin/python alphalens-reloaded==0.4.6   # exit 0; pandas 2.3.3, statsmodels 0.15.0",
    "uv venv ... " + C + "/venv-extra && uv pip install --python " + C + "/venv-extra/bin/python sktime==1.1.0 tsfresh==0.21.2 river==0.26.1 arcticdb==6.26.0   # exit 0",
    "uv venv ... " + C + "/venv-lock && uv pip sync --python " + C + "/venv-lock/bin/python --offline --require-hashes blueprints/us-equities/research-evaluation/requirements.lock   # exit 0",
]
DOWNLOADS = ("Network downloads: PyPI packages not already in the shared uv cache (uv reported 'Prepared 10', 'Prepared 20' and 'Prepared 9' packages for the three installs; torch 2.13.0 came from the cache); "
             "Hugging Face snapshots amazon/chronos-bolt-small@772f3d25, NeoQuasar/Kronos-small@901c26c1 and NeoQuasar/Kronos-Tokenizer-base@0e011738 into an isolated HF_HOME (" + C + "/hf, 292 MB total, each file under 200 MB); "
             "git clones of shiyu-coder/Kronos@67b630e6 (26 MB) and tradermonty/claude-trading-skills@bc551564 (102 MB). No credentials were read.")

# Fix round 4 (gap 5 only): the six remaining candidates, run by extra_arms.py.
X4 = "f161e6cb34c0ce81acb367691a254d112897e4611f59cc29ea193f49f715edd7"
R4_CHECKED_AT = "2026-09-23T16:03:25Z"
R4_CHECKED_AT_NOTE = ("time of the last fix-round-5 observation, the Hugging Face tree API retrieval recorded in $CACHE/r5/weights.txt. "
                      "Fix round 4 was preregistered at 15:36:22Z (commit 4d82f63) and fix round 5 at 15:59:30Z (commit 8ac240d); "
                      "fix-round-4 outputs were written 15:37:54Z-15:45:24Z by extra_arms.py as committed in 332b0e2 (sha256 d8fcad4ebf4a780c5b4598fec62907a2267ac297b91cd1fc0e8d19e2d2fc62fa).")
BR = "ECOSYSTEM_JOB_SECONDS=1200 ECOSYSTEM_JOB_MEMORY_MAX=8G ECOSYSTEM_JOB_MEMORY_HIGH=6G $HOME/codex-ecosystem/bin/ecosystem-bounded-run "
EA = BP + "/extra_arms.py"
R4_INSTALL = [
    "uv venv --python <cpython-3.13.15> " + C + "/venv-r4-{haystack,st,ray,docling,timesfm}; uv venv --python <cpython-3.11.16> " + C + "/venv-r4-qlib",
    BR + "uv pip install --python " + C + "/venv-r4-haystack/bin/python haystack-ai==3.1.1   # exit 0",
    BR + "uv pip install --python " + C + "/venv-r4-st/bin/python sentence-transformers==6.1.0 torch==2.13.0   # exit 0",
    BR + "uv pip install --python " + C + "/venv-r4-ray/bin/python 'ray[serve]==2.58.0'   # exit 0",
    "uv pip install --python " + C + "/venv-r4-ray/bin/python jinja2   # exit 0; added after ray attempt 1 (see results.c17_ray_serve)",
    BR + "uv pip install --python " + C + "/venv-r4-qlib/bin/python pyqlib==0.9.7 fire loguru   # exit 0 (resolved pandas 3.0.6, numpy 2.4.6)",
    BR + "uv pip install --python " + C + "/venv-r4-docling/bin/python docling==2.129.0 torch==2.13.0   # exit 0",
    BR + "uv pip install --python " + C + "/venv-r4-timesfm/bin/python 'timesfm[torch] @ git+https://github.com/google-research/timesfm@v3.0.0' torch==2.13.0   # exit 0; tag v3.0.0 resolved to 331c6d33cb1ac2611de3056d0ac7164aab6301eb",
    "curl -sL -o " + C + "/r4/dump_bin.py https://raw.githubusercontent.com/microsoft/qlib/v0.9.7/scripts/dump_bin.py   # sha256 b8f34c57ce1ef4b1772f3909735e66058f21b25bd7ab8a5f16318822401fe53f",
]
R4_COMMANDS = [
    C + "/venv/bin/python " + EA + " --arm export --lean-source " + L + " --export " + C + "/r4/frozen_ohlcv.json   # exit 0, export sha256 " + X4,
    BR + C + "/venv-r4-haystack/bin/python " + EA + " --arm haystack --export " + C + "/r4/frozen_ohlcv.json --export-sha256 " + X4 + "   # exit 0",
    "HF_HOME=" + C + "/hf " + BR + C + "/venv-r4-st/bin/python " + EA + " --arm st --device cpu --export ... --export-sha256 " + X4 + "   # exit 0",
    BR + C + "/venv-r4-qlib/bin/python " + EA + " --arm qlib --tmp " + C + "/r4/qlib-tmp --export ... --export-sha256 " + X4 + "   # exit 0",
    "RAY_USAGE_STATS_ENABLED=0 ECOSYSTEM_JOB_TASKS_MAX=2048 " + BR + C + "/venv-r4-ray/bin/python " + EA + " --arm ray --tmp /tmp/claude-1000/r4ray ...   # attempt 1: exit 1, ModuleNotFoundError: No module named 'jinja2' at 'from ray import serve' (before ray.init)",
    "(same, after installing jinja2)   # attempt 2: exit 0, passed, but Ray's node_ip_address was the host LAN address, not loopback (preregistration deviation)",
    "RAY_USAGE_STATS_ENABLED=0 ECOSYSTEM_JOB_TASKS_MAX=2048 " + BR + "unshare -rn sh -c 'ip link set lo up && ip -brief addr > " + C + "/r4/ray-netns.txt && exec " + C + "/venv-r4-ray/bin/python " + EA + " --arm ray --tmp /tmp/claude-1000/r4ray3 ...'   # attempt 3 (result of record): exit 0 inside a loopback-only network namespace",
    BR + "unshare -rn sh -c 'ip link set lo up && exec " + C + "/venv-r4-docling/bin/python " + EA + " --arm docling --tmp " + C + "/r4/docling-tmp ...'   # exit 0 with no network access",
    "HF_HOME=" + C + "/hf ECOSYSTEM_JOB_MEMORY_MAX=12G ECOSYSTEM_JOB_MEMORY_HIGH=10G ... ecosystem-bounded-run " + C + "/venv-r4-timesfm/bin/python " + EA + " --arm timesfm --fcmp-forecasts " + C + "/run-fcmp-merged-r2/forecasts.json --export ... --export-sha256 " + X4 + "   # exit 0, 100 s including the weight download",
    "cd " + C + " && " + C + "/venv-r4-haystack/bin/python " + BP + "/haystack_diag.py " + BP + " > r4/haystack-diag.json   # post-hoc diagnostic, not preregistered",
]
R4_RESULTS = {
    "fix_round_4_export": "frozen_ohlcv.json: 1824 sessions 2014-01-02..2021-03-31 for SPY/QQQ/IWM, sha256 " + X4 + "; every arm checked this hash before running.",
    "c9_haystack": "haystack-ai 3.1.1, 216 documents, InMemoryBM25Retriever top_k=1: 182/216 keyed queries return the matching (asset, month) document. PRECONDITION FAILED: the preregistered pass criterion was 216/216. The absent-key query 'SPY 1999-01' returned 'SPY 2019-01'; that control cannot fail (no document carries the key) and is not counted as detection evidence. Fix round 5 permuted-meta control (each document labelled with the next document's key): 2/216 keyed hits (criterion <= 5), so the keyed check detects wrong labels; the main result reproduced at 182/216. Post-hoc diagnostic (not preregistered): the default BM25 tokenizer (?u)\\b\\w+\\b splits '2015-10' into '2015' and '10' and also tokenizes the numbers in each text ('-6.10%' gives '10'), so number fragments in other documents outscore the true document; this is a document-design weakness of the test, reported as observed and not rescored.",
    "c14_docling": "docling 2.129.0 converted an HTML and a CSV table of SPY 2020 month-end closes (13x3 including the header) with DocumentConverter inside a network namespace with no external interface: 0 cell mismatches in both formats; the perturbed-copy negative control reports exactly 1 mismatch in each. Passed.",
    "c17_ray_serve": "ray 2.58.0 Serve deployment on the momentum20 rule: 40/40 DeploymentHandle responses equal the in-process computation; in fix round 5 they also equal 40/40 decisions from evaluate.weights(panel, t, 'momentum20') computed with Decimal arithmetic in the plan venv (expected_momentum20.json, sha256 230a1561...), an implementation independent of the deployment's helper; one loopback HTTP request (2015-12-22) returned 'cash' = expected; the lookback-19 negative control disagrees on 4/40 dates, so the comparison can detect a wrong rule. Picks: IWM 14, QQQ 16, SPY 3, cash 7. Cleanup (fix round 5, retained in raw/r5/r5__ray-pgrep.txt): pgrep -x raylet and pgrep -x gcs_server counted 1 and 1 inside the run before shutdown (positive control, in r5__ray.json) and 0 and 0 five seconds after exit. A first fix-round-5 cleanup probe used pgrep -f with the pattern in the calling shell's own command line and counted 2 before and after (self-matches); it is retained as r5__attempt1-ray-pgrep.txt and not used. Passed (attempt 3 in fix round 4, rerun in fix round 5). Attempt 1 failed at import: ray[serve]==2.58.0 metadata does not require jinja2 but ray/serve/_private/haproxy.py imports it. Attempt 2 passed functionally but Ray's node_ip_address was <lan-ip> (the host LAN address); its GcsServer started listening at 11:39:44.583 local time (15:39:44Z) per the retained log, and their bind address and shutdown time were not logged (the job had exited before the 11:40:36 evidence copy), so the preregistered loopback-only condition was not met; attempt 3 ran in an unprivileged network namespace containing only lo, where node_ip_address was 127.0.1.1.",
    "c18_timesfm": "timesfm 3.0.0 (source tag v3.0.0, 331c6d33) with google/timesfm-2.5-200m-pytorch@1d952420 on cuda:0: 783/783 forecasts finite, keys and targets identical to run-fcmp-merged-r2. Dev mean fold MAE: timesfm 0.018658, naive 0.018682, chronos-bolt-small 0.018623; reserved MAE 0.021511 / 0.020570 / 0.022224. Paired fold bootstrap: timesfm vs naive -0.0000233, 95% CI [-0.000382, 0.000334], better in 12/20 folds; timesfm vs chronos +0.0000354, CI [-0.000653, 0.000727], 9/20. No difference resolved. Fix round 5 rerun (HF_HUB_OFFLINE=1) reproduced forecasts_sha256 fab9e681...; its offset-key control (decision index t+1) fails the key/target check, as required. Weight file: 925,181,104 bytes, sha256 2f776efe..., equal to the Hugging Face tree API LFS oid at the pinned revision (raw/r5/r5__weights.txt). Passed (execution criterion; the comparison was reported, not scored).",
    "c21_sentence_transformers": "sentence-transformers 6.1.0 with all-MiniLM-L6-v2@1110a243 on CPU: dimension 384, repeat-encode max abs diff 0.0; keyed top-1 accuracy by cosine 29/216 (0.134) vs BM25 182/216 on the same documents and queries. Fix round 5 perturbed-text control: max abs embedding difference 0.0231 (> 1e-5), so the drift check can detect a change. model.safetensors 90,868,376 bytes, sha256 53aa5117..., equal to the LFS oid. Passed (the accuracy was a measured report, not a criterion).",
    "c24_qlib": "pyqlib 0.9.7 on CPython 3.11.16, data dumped with the v0.9.7 scripts/dump_bin.py: D.features for IWM/QQQ/SPY returned 4533 rows; 9066 values ($close and $close/Ref($close,20)-1) were compared with the pandas computation. FAILED ITS PREREGISTERED CRITERION: the criterion was rtol 1e-5 with no absolute tolerance, and fix round 5 counts 294 mismatches under it. The fix-round-4 script had added atol=1e-6 for the momentum expression, an unpreregistered deviation found by review; under that deviation all 9066 values agree, so every one of the 294 differences is within 1e-6 absolute. The one-session-shift negative control reports 9048 mismatches under both rules.",
    "fix_round_4_tally": "After fix round 5, four of six arms met their preregistered pass criteria (c14, c17, c18, c21). c9 executed but failed its 216/216 retrieval criterion (182/216). c24 executed but failed its rtol-only equality criterion (294 of 9066 values; all within 1e-6 absolute). All 15 listed candidates now have a retained execution on the frozen data.",
}
R4_RAW = ["r4__frozen_ohlcv.json", "logs__r4-export.json", "r4__haystack.json", "r4__haystack.err", "r4__haystack-diag.json", "r4__docling.json", "r4__docling.err",
          "r4__ray-attempt1.json", "r4__ray-attempt1.err", "r4__ray-attempt2.json", "r4__ray-attempt2.err", "r4__ray-attempt2-binds.txt",
          "r4__ray.json", "r4__ray.err", "r4__ray-netns.txt", "r4__ray-attempt3-binds.txt", "r4__timesfm.json", "r4__timesfm.err",
          "r4__st.json", "r4__st.err", "r4__qlib.json", "r4__qlib.err",
          "logs__install-r4-haystack.log", "logs__install-r4-st.log", "logs__install-r4-ray.log", "logs__install-r4-ray-jinja2.log",
          "logs__install-r4-qlib.log", "logs__install-r4-docling.log", "logs__install-r4-timesfm.log"]
R4_DETECTION = ("Fix-round-4/5 arms, each with a control that must register a failure (the fix-round-5 controls were added after review found the absent-key haystack query could not fail, "
                "TimesFM and MiniLM had no injected control, and Ray's expected values shared the deployment's helper): BM25 keyed top-1 plus a permuted-meta store (2/216 hits); "
                "docling cells vs the source strings plus a one-cell perturbed copy (exactly 1 mismatch); Serve responses vs evaluate.weights Decimal decisions plus a lookback-19 rule (4/40 disagreements); "
                "Qlib values vs pandas plus a one-session shift (9048 mismatches); TimesFM keys/targets vs the sha256-pinned fcmp file plus an offset-key control (fails); "
                "MiniLM repeat-encode drift plus a perturbed-text control (0.0231). Ray cleanup uses pgrep -x with an in-run positive control (1 raylet, 1 gcs_server). "
                "Ray loopback was checked from Ray's own session logs (node_ip_address), which is how attempt 2's LAN binding was found.")
R4_REMAINING = ("All 15 listed candidates now have a retained execution on the frozen data (c2, c3, c4, c5, c6, c10, c12, c15, c20 in rounds 1-3; c9, c14, c17, c18, c21, c24 in fix round 4). "
                "Outcome stays advanced under the preregistered rule: the c9 haystack arm failed its 216/216 keyed-retrieval criterion (182/216), and the c24 Qlib arm failed its rtol-only equality criterion (294 of 9066 values; all within 1e-6 absolute). "
                "A redesigned retrieval test (for example a tokenizer or document text without numeric fragments) and a Qlib tolerance suited to float32 storage would each need their own preregistration. "
                "These executions show only that each library runs on the frozen data; they are not accuracy, RAG-quality or alpha acceptance.")
R4_LIMITS = [
    "Fix round 4 downloads: PyPI wheels not already in the shared uv cache (uv 'Prepared' 5, 13, 85, 22 and 1 packages for haystack, ray, qlib, docling and timesfm; its large-file lines list 446 MiB; pyqlib 0.9.7 pulls mlflow and jupyter components); jinja2 and markupsafe; the timesfm v3.0.0 git source; google/timesfm-2.5-200m-pytorch model.safetensors (925,181,104 bytes, sha256 2f776efe... equal to the Hugging Face LFS oid) and all-MiniLM-L6-v2 into the isolated HF_HOME $CACHE/hf; qlib v0.9.7 scripts/dump_bin.py. No credentials were read.",
    "Deviations from the fix-round-4 preregistration: jinja2 was added to the ray venv after attempt 1; Ray temp dirs were /tmp/claude-1000/r4ray and r4ray3 (short socket paths), not under $CACHE, and were removed after the bind evidence was copied; attempt 2 ran Ray with the host LAN address as node_ip_address (under a minute; exact duration not logged) before the network-namespace rerun; TimesFM ran on the GPU, while chronos in receipt 6 ran on the CPU.",
    "Fix round 5 reran haystack, sentence-transformers, Qlib, Ray (twice; the first cleanup probe self-matched) and TimesFM into $CACHE/r5; docling was not rerun.",
    "Qlib resolved pandas 3.0.6 (no pandas<3 constraint in pyqlib 0.9.7); only $close and one expression were checked, not Alpha158, a model or qrun, and the US region was set without a reviewed calendar or benchmark.",
    "docling was tested on HTML and CSV tables only; PDF layout and OCR models were not downloaded or run.",
    "The TimesFM comparison uses the fcmp folds and bootstrap (serially dependent folds, one target, 20 folds).",
]

R5_COMMANDS = [
    C + "/venv/bin/python " + EA + " --arm expected --lean-source " + L + " --export " + C + "/r4/frozen_ohlcv.json --export-sha256 " + X4 + " --expected " + C + "/r5/expected_momentum20.json   # fix round 5, exit 0, sha256 230a15612e49d154d9eaaf4ec72c0a9a562c485bd810e8a51c130c3190a8e079",
    "(fix round 5) same haystack, st (HF_HUB_OFFLINE=1) and qlib (--tmp " + C + "/r5/qlib-tmp) commands with outputs in " + C + "/r5   # each exit 0",
    "(fix round 5) same unshare -rn ray command with --expected " + C + "/r5/expected_momentum20.json --expected-sha256 230a1561...   # attempt 1 exit 0 (its pgrep -f cleanup probe self-matched); attempt 2 adds in-run pgrep -x counts, exit 0, result of record",
    "(fix round 5) HF_HUB_OFFLINE=1 same timesfm command, outputs in " + C + "/r5   # exit 0",
    "stat -L -c %s / sha256sum on the snapshot files and curl -s https://huggingface.co/api/models/<id>/tree/<revision> for both models > " + C + "/r5/weights.txt",
]
R5_RAW = ["r5__expected.json", "r5__expected.err", "r5__expected_momentum20.json", "r5__haystack.json", "r5__haystack.err", "r5__st.json", "r5__st.err",
          "r5__qlib.json", "r5__qlib.err", "r5__attempt1-ray.json", "r5__attempt1-ray.err", "r5__attempt1-ray-pgrep.txt", "r5__attempt1-ray-binds.txt", "r5__attempt1-ray-netns.txt",
          "r5__ray.json", "r5__ray.err", "r5__ray-pgrep.txt", "r5__ray-binds.txt", "r5__ray-netns.txt", "r5__timesfm.json", "r5__timesfm.err", "r5__weights.txt"]

RECEIPTS = {
 0: dict(slug="nautilus-frozen-selections", outcome="advanced", evidence_class="local_integration",
   prereg=prereg("0", [FIX1]),
   commands=[
     "$HOME/.local/share/codex-ecosystem/tools/nautilus-2.0.0rc5/bin/python " + BP + "/nautilus_rerun.py --lean-source " + L + " --folds " + C + "/run-purge/results.json --out " + C + "/run-nautilus-round1   # round 1, exit 0, audit v1",
     "$HOME/.local/share/codex-ecosystem/tools/nautilus-2.0.0rc5/bin/python " + BP + "/nautilus_rerun.py --lean-source " + L + " --folds " + C + "/run-purge/results.json --out " + C + "/run-nautilus   # round 2 after fix round 1, exit 0, audit v2"],
   results={
     "round1_verbatim": "RAW development/reserved reconciled: true. ADJ development problems: ['cash sequence mismatch', 'final cash 89651.82 != independent 89651.9250', 'realized pnl -10348.11 != cash delta -10348.0750']; ADJ reserved: ['cash sequence mismatch', 'final cash 100814.92 != independent 100814.9167', 'realized pnl 814.91 != cash delta 814.9167'].",
     "round2": [
       "RAW development: 249 episodes (138 invested, 111 cash), 276 fills, fees 27073.48 USD, ending cash 87359.71 (engine 87359.71), realized-PnL check 138/138 exact, reconciled true, strategy momentum recomputation 249 checked / 0 mismatches, parity fill ratio == evaluate gross_price_label 138/138, dividends entitled but not credited 2542.51 USD over 10 ex-dates, max daily-volume participation 0.0000812.",
       "ADJ development (dividend-inclusive back-adjusted prices): 276 fills, fees 27407.36, ending cash 89651.82 (engine 89651.82), realized-PnL 136/138 exact, max abs diff 0.01, sum residual 0.07 USD, reconciled true; adjusted-price momentum would differ from the frozen raw decision at 6 of 249 decisions (diagnostic; the frozen schedule was traded).",
       "RAW reserved 2021Q1 (momentum20): 11 episodes (10 invested), 20 fills, fees 2079.93, ending cash 100808.61, net 808.61, 11/11 decisions match, 10/10 parity exact, dividends entitled 0 (no held position spans a record close).",
       "ADJ reserved: 20 fills, fees 2080.04, ending cash 100814.92, reconciled true.",
       "ADJ minus RAW development ending cash = 2292.11 USD vs 2542.51 USD of independently computed RAW-equivalent dividends: same sign and magnitude; not equal because ADJ reinvests through prices and trades different share counts.",
       "inputs_unchanged true; engine nautilus_trader 2.0.0rc5."]},
   raw_files=["run-nautilus-round1__summary.json", "logs__nautilus-round1.stdout", "run-nautilus-round1__development-ADJ.reports.json",
              "run-nautilus__summary.json", "logs__nautilus.stdout", "run-nautilus__development.schedule.json", "run-nautilus__reserved.schedule.json",
              "run-nautilus__development-RAW.reports.json", "run-nautilus__development-ADJ.reports.json", "run-nautilus__reserved-RAW.reports.json", "run-nautilus__reserved-ADJ.reports.json"],
   detection="The audit compares every fill, commission and account-report cash total against independent Decimal arithmetic and fails on any difference. It demonstrably fires: round 1 flagged the ADJ sub-cent notional rounding. RAW parity compares Decimal fill-price ratios to evaluate.label exactly; the strategy recomputes momentum from its own ticks and is compared to the frozen weights.",
   remaining="Selected ETF sample, not a point-in-time universe; evaluate.py labels remain raw-price (total-return labels were not added to evaluate.py); 11 reserved episodes; no alpha claim. The engine does not credit dividend cash: RAW dividends are computed outside the engine and ADJ embeds them in back-adjusted prices that were not tradable historically. In-engine dividend crediting belongs to the peer-owned dividend SimulationModule (sota-workflow-resolution).",
   limits=["Fills are at the session open trade tick with no spread, queue or impact; the synthetic tick size is the whole session volume.",
           "The Nautilus CASH account and 10 bp per side fee are declared conventions, not a broker fee schedule.",
           "Dividend amounts come from LEAN factor files (ref_close * (1 - pf_D/pf_next)), not from an independent corporate-action source.",
           "The ADJ half-even notional rounding rule was fitted on round-1 development-ADJ output; the reserved-ADJ arm (20 fills) was not used for fitting."]),
 1: dict(slug="purge-embargo-fold-boundary", outcome="advanced", evidence_class="local_integration",
   prereg=prereg("1", [FIX3]),
   commands=[C + "/venv-lock/bin/python " + BP + "/evaluate_purge.py --lean-source " + L + " --out " + C + "/run-purge   # exit 0, 3.8 s",
             C + "/venv-lock/bin/python " + BP + "/evaluate_purge.py --lean-source " + L + " --out " + C + "/run-purge-r2   # fix round 3 (adds Z-choose and P6-assert), exit 0",
             C + "/venv/bin/python " + BP + "/ljung_box.py " + C + "/run-purge/results.json > " + C + "/logs/ljungbox.json   # exit 0"],
   results={
     "arms": "Z-check (purge 0, embargo 0, training labels from the truncated prefix): raised 'ValueError: incomplete training label', the check evaluate.main also performs; this fires before evaluate.choose runs. Z-leaky: 20 folds, 6615 records, reserved momentum20, 120 training labels crossing the test start. P6 (plan): 20 folds, 6605 records, reserved momentum20 with mean_net_cost_proxy_label 0.001184071666615635470939591764; per-fold chosen candidate and test_first equal the accepted receipt for all 20 folds. P6E5 (purge 6, 5-session embargo, fold-boundary censoring): 20 folds, 6500 records, enforced assertions passed (0 crossings, minimum 5 sessions between the last training exit and the cutoff), reserved momentum20 with the same mean.",
     "fix_round_3_negative_controls": "run-purge-r2: Z-choose (purge 0, full-segment training panel, unmodified evaluate.choose) raised 'ValueError: training label overlap with evaluation decision'; P6-assert (plan P6 with the fold-boundary assertion enforced, no censoring) raised 'AssertionError: development label window crosses a fold boundary: development-1'. Z-check, Z-leaky, P6 and P6E5 outputs are identical to run-purge.",
     "detector_evidence": "Report-mode audit before censoring found 115 evaluation labels crossing their fold end in P6 and P6E5 and 120 training labels crossing the test start in Z-leaky; P6 minimum training-exit gap was 0 sessions.",
     "selection_comparison": "Per-fold chosen candidate differs in 0/20 folds between Z-leaky and P6 and 0/20 between P6E5 and P6; reserved selection is momentum20 in all three completed arms.",
     "ljung_box_reserved_training_labels": "P6E5 (n=49): momentum60 p=0.121/0.0035/0.0052/0.008 at lags 1-4; momentum120 p=0.603/0.0256/0.0436/0.0519; momentum20 p=0.151/0.300/0.105/0.112; cash constant. P6 (n=50) is similar. For momentum60, the null of no serial correlation is rejected at cumulative lags 2-4 at the 1% level."},
   raw_files=["run-purge__results.json", "logs__purge.stdout", "logs__ljungbox.json", "run-purge-r2__results.json", "logs__purge-r2.stdout"],
   detection="The fold-boundary audit counts label windows crossing the test start, the embargo, or the fold end; it reports 115-120 crossings on arms that have them, so a zero on P6E5 is informative. The enforced assertion raises on P6 (P6-assert), and unmodified evaluate.choose raises its overlap error under zero purge (Z-choose); both were added in fix round 3 after review found that round 1 had shown only report-mode counts and the incomplete-label check.",
   remaining="Independent samples are not established: Ljung-Box rejects no serial correlation for momentum60 at lags 2-4 (p<0.01) and borderline for momentum120, even with purge and embargo. The embargo is implemented as a 5-session training-tail drop, because a post-test embargo is vacuous when training never follows test. The frozen plan.json and evaluate.py were not changed.",
   limits=["Wrapper imports evaluate.py helpers unchanged; the Z-leaky arm bypasses evaluate.choose's overlap check by design.",
           "Ljung-Box on 49-50 episodes has low power; non-rejection does not show independence."]),
 5: dict(slug="factor-forecast-econometrics-executions", outcome="advanced", evidence_class="local_integration",
   prereg=prereg("5", [FIX2, FIX3, FIX4, FIX5]),
   checked_at=R4_CHECKED_AT, checked_at_note=R4_CHECKED_AT_NOTE,
   commands=INSTALL + R4_INSTALL + R4_COMMANDS + R5_COMMANDS + [
     "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 " + C + "/venv/bin/python " + BP + "/libs_run.py --arm {statsmodels|arch|statsforecast} --lean-source " + L + "   # each exit 0",
     C + "/venv-al/bin/python " + BP + "/libs_run.py --arm alphalens --lean-source " + L + "   # exit 0",
     C + "/venv-extra/bin/python " + BP + "/libs_run.py --arm {sktime|tsfresh|river} --lean-source " + L + "   # each exit 0",
     "OPENBLAS_NUM_THREADS=1 " + C + "/venv/bin/python " + BP + "/libs_run.py --arm statsmodels_lb_df2 --lean-source " + L + "   # fix round 3, exit 0",
     C + "/venv-extra/bin/python " + BP + "/libs_run.py --arm arcticdb --lean-source " + L + " --tmp " + C + "/arctic-tmp   # exit 0",
     "chronos-bolt-small: see receipt 6 (fcmp part A)"],
   results={
     "c20_statsmodels": "ARIMA(1,1,1) on SPY log close (last 252 development sessions): ar.L1 -0.554985, ma.L1 0.262383, AIC -1242.8696, 5-step forecast 5.92264..5.923058 vs last 5.923935; residual Ljung-Box p lag5 0.0624, lag10 0.0 with model_df=0. Fix round 3 with model_df=2 (AR1+MA1): lag5 p=0.014798, lag10 p<1e-6, so residual autocorrelation is rejected at 5% at lag 5 as well. sha256 17c335da... and libs__statsmodels_lb_df2.json",
     "c15_arch": "GARCH(1,1) on 1511 SPY daily % log returns: omega 0.038823, alpha 0.242925, beta 0.735408, convergence_flag 0, 5-step variance 0.311237..0.435446. sha256 1444824e...",
     "c12_statsforecast": "AutoARIMA on 252 log closes, h=5: SPY 5.922154.., QQQ 5.747813.., IWM 5.28083... sha256 1dac4866...",
     "c4_alphalens": "Spearman IC over 1506 sessions x 3 ETFs: momentum20 1D 0.0428 / 5D 0.0183; momentum60 0.0501 / 0.0820; momentum120 0.0551 / 0.1019 (IC std about 0.73-0.76). sha256 473ee5d3...",
     "c3_sktime": "ThetaForecaster(sp=1) SPY 5-step log close 5.923831..5.925659. sha256 345da5ac...",
     "c6_tsfresh": "MinimalFCParameters on 252 values per ETF: 251 daily log returns plus one leading zero placeholder from fillna(0) (10 features each). sha256 209d69d1...",
     "c10_river": "Progressive StandardScaler|LinearRegression on 5 lagged SPY returns: MAE 0.77118635 vs zero-forecast MAE 0.00686633 over 1757 steps. The online model diverged in this untuned configuration; recorded as observed, not tuned after the fact. sha256 70256539...",
     "c2_arcticdb": "LMDB write/read of the 1824x3 close panel: DataFrame.equals False but values, index and columns equal and pandas assert_frame_equal passed (diagnostic file). sha256 605d691b...",
     "c5_chronos": "chronos-bolt-small produced all 783 origin-by-asset forecasts across 261 decision origins (receipt 6).",
     **R4_RESULTS},
   raw_files=["libs__statsmodels.json", "libs__statsmodels_lb_df2.json", "libs__arch.json", "libs__statsforecast.json", "libs__alphalens.json", "libs__sktime.json", "libs__tsfresh.json",
              "libs__river.json", "libs__arcticdb.json", "libs__arcticdb-diagnostic.txt", "logs__install.log", "logs__install-al.log", "logs__install-extra.log",
              "requirements.in", "requirements-alphalens.in", "requirements-extra.in"] + R4_RAW + R5_RAW,
   detection=R4_DETECTION + " Earlier arms: each fails with a nonzero exit if the library import, pinned version or fit raises; stderr files are retained, all empty. evaluate.verify_inputs checks the plan input hashes before each arm.",
   remaining=R4_REMAINING,
   limits=["pandas resolved to 2.3.3 in these venvs (alphalens-reloaded 0.4.6 and statsforecast 2.1.1 require pandas<3), not the plan's lock at 3.0.6.",
           "sktime is at pin 1.1.0 while PyPI latest is 1.2.0.",
           DOWNLOADS] + R4_LIMITS),
 6: dict(slug="statsforecast-vs-chronos-folds", outcome="advanced", evidence_class="local_integration",
   prereg=prereg("6", [FIX2, FIX3]),
   commands=[
     "ECOSYSTEM_JOB_SECONDS=1200 $HOME/codex-ecosystem/bin/ecosystem-bounded-run env HF_HOME=" + C + "/hf CUDA_VISIBLE_DEVICES= " + C + "/venv/bin/python " + BP + "/fcmp.py --lean-source " + L + " --kronos-src " + C + "/src/kronos --out " + C + "/run-fcmp   # attempt 1, all arms on CPU; stopped at the 1200 s limit during the Kronos stage, no results",
     "ECOSYSTEM_JOB_SECONDS=1200 $HOME/codex-ecosystem/bin/ecosystem-bounded-run env HF_HOME=" + C + "/hf HF_HUB_OFFLINE=1 CUDA_VISIBLE_DEVICES= OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 " + C + "/venv/bin/python " + BP + "/fcmp.py --lean-source " + L + " --kronos-src " + C + "/src/kronos --out " + C + "/run-fcmp-A --models naive,statsforecast_autoarima,statsmodels_arima111,chronos_bolt_small --sf-jobs 4   # exit 0, 43 s",
     "(same env, GPU visible) " + C + "/venv/bin/python " + BP + "/fcmp.py ... --out " + C + "/run-fcmp-B --models kronos_small --kronos-device cuda:0   # exit 0, 119 s",
     C + "/venv/bin/python " + BP + "/fcmp.py ... --out " + C + "/run-fcmp-merged --models none --merge " + C + "/run-fcmp-A/forecasts.json " + C + "/run-fcmp-B/forecasts.json   # exit 0",
     "(fix round 3) same merge into " + C + "/run-fcmp-merged-r2 with per-source execution metadata   # exit 0; per_fold, pairwise and forecasts_sha256 identical to run-fcmp-merged"],
   results={
     "design": "20 skfolio WalkForward development folds (11-13 origins each, 250 in total) plus reserved 2021Q1 (11 origins); 783 origin-by-asset forecasts over 261 decision origins; target 5-session log return; primary metric per-fold MAE.",
     "dev_mean_fold_mae": {"naive": 0.018682, "statsforecast_autoarima": 0.019455, "statsmodels_arima111": 0.018630, "chronos_bolt_small": 0.018623, "kronos_small": 0.043356},
     "reserved_mae": {"naive": 0.020570, "statsforecast_autoarima": 0.023407, "statsmodels_arima111": 0.021075, "chronos_bolt_small": 0.022224, "kronos_small": 0.122386},
     "chronos_vs_statsforecast": "mean per-fold MAE diff -0.000832, 95% bootstrap CI [-0.001787, 0.0000076], chronos better in 14/20 folds: no difference resolved (interval touches zero).",
     "chronos_vs_naive": "-0.0000586, CI [-0.000660, 0.000583], 13/20: no difference resolved.",
     "statsforecast_vs_naive": "+0.000773, CI [-0.0000094, 0.001929], better in 9/20: no difference resolved.",
     "per_fold_table": "raw/fcmp/run-fcmp-merged-r2__results.json per_fold (identical to run-fcmp-merged)",
     "merge_metadata_note": "run-fcmp-merged__results.json records kronos_device 'cpu' (the merge CLI default); the r2 merge records the per-source metadata (part A cpu without Kronos, part B cuda:0)."},
   raw_files=["run-fcmp-merged-r2__results.json", "logs__fcmp-merge-r2.stdout", "run-fcmp-merged__results.json", "run-fcmp-merged__forecasts.json", "run-fcmp-A__results.json", "run-fcmp-A__forecasts.json", "logs__fcmp-A.stdout", "logs__fcmp-A.stderr",
              "logs__fcmp-merge.stdout", "logs__fcmp-attempt1.stderr", "logs__fcmp-attempt1.stdout"],
   detection="The merge step fails if the origin keys or targets of the two forecast files differ; the bootstrap reports a resolved difference whenever the interval excludes zero, as it does for Kronos (receipt 7), so a no-difference result is not a blind spot.",
   remaining="The comparison now exists and was run as specified, but it shows no resolved difference between the two adopted candidates (c5, c12), so it does not turn the winner set into a performance ranking. Mapping this result into the layer verdict belongs to the ledger owner.",
   limits=["One target (5-session log return), one context length (252), three ETFs, 20 folds; the bootstrap resamples folds, which are serially dependent.",
           "chronos ran on CPU in float32, and statsforecast used n_jobs=4 in attempt 2. Attempt 1 was stopped at 1200 s during Kronos and is retained as a stopped attempt."]),
 7: dict(slug="kronos-small-vs-naive", outcome="advanced", evidence_class="local_integration",
   prereg=prereg("7", [FIX2]),
   commands=["see receipt 6: fcmp part B (--models kronos_small --kronos-device cuda:0) and merge"],
   results={
     "kronos_small": "dev mean per-fold MAE 0.043356 vs naive 0.018682 (ratio 2.75); reserved MAE 0.122386 vs 0.020570; Kronos minus naive per-fold MAE diff +0.02467, 95% CI [0.01788, 0.03185], Kronos better in 2/20 folds: naive better (resolved).",
     "diagnostic": "Kronos 5-session forecasts have mean -0.0229 and sd 0.0575 vs realized sd 0.0281; the largest forecasts are about 0.32 in magnitude on IWM, i.e. strong mean reversion toward the context window mean.",
     "c16_evidence_ref_candidate": "evidence/artifacts/gap-wave2-20260923/us-equities__research-factors-ml/7-kronos-small-vs-naive.json",
     "c13": "see receipt 14 (seeded-defect run)."},
   raw_files=["run-fcmp-B__results.json", "run-fcmp-B__forecasts.json", "logs__fcmp-B.stdout", "logs__fcmp-B.stderr", "run-fcmp-merged-r2__results.json"],
   detection="The same bootstrap resolves a difference when one exists; here it does (naive better). Harness review: the predictor call follows the upstream predict_batch (ordered outputs, upstream per-series denormalization).",
   remaining="Receipts for c16 (this one) and c13 (receipt 14) now exist, but the packet's evidence_refs cannot be added here because layer-verdict artifacts are read-only for this unit; the ledger owner must link them. One Kronos configuration only (daily bars, 252 context, sample_count 20, T=1.0, top_p=0.9, no fine-tuning), run on GPU instead of the preregistered CPU (fix round 2).",
   limits=["The GPU device and sampled decoding mean the result is seeded but not bit-reproducible across hardware.",
           "The daily ETF context may be outside Kronos-small's main training distribution; the result is not a general Kronos verdict."]),
 9: dict(slug="alpaca-paper-pipeline", outcome="deferred", evidence_class="source_review",
   prereg=prereg("9"),
   commands=[],
   results={"not_executed": "Requires contacting the Alpaca paper account and changing gate rows. Those lanes are owned by peer session sota-workflow-resolution. Receipt 0 supplies only the historical Nautilus leg (no broker adapter, no RiskEngine limit configuration beyond the default pre-trade balance check)."},
   raw_files=[],
   detection="n/a (not executed).",
   remaining="Blocker: broker contact and paper-account calls are reserved to peer session sota-workflow-resolution (owner). No isolated alternative exists here, because a loopback-only instance cannot reconcile against the real Alpaca paper account API.",
   limits=["Deferred; no broker, paper-account or gate action was taken."]),
 10: dict(slug="nautilus-dividend-fee-cash", outcome="advanced", evidence_class="local_integration",
   prereg=prereg("10", [FIX1]),
   commands=["see receipt 0 (same nautilus_rerun.py rounds 1 and 2)"],
   results={"summary": "The skfolio study's frozen selections ran through Nautilus 2.0.0rc5 with dividend-inclusive back-adjusted bars (ADJ arm) and MakerTakerFeeModel 10 bp per side; portfolio cash reconciled exactly in all four arms under audit v2 (development ADJ: 276 fills, fees 27407.36 USD, ending cash 89651.82). Participation at most 0.0000844 of session volume (1% admission rule met). Financing is zero by construction (cash account, no margin or short).",
            "details": "receipt 0 results.round2"},
   raw_files=["run-nautilus__summary.json", "run-nautilus__development-ADJ.reports.json", "run-nautilus__reserved-ADJ.reports.json", "run-nautilus-round1__summary.json"],
   detection="As receipt 0: the exact cash audit caught the sub-cent rounding in round 1.",
   remaining="Realistic fills (spread, queue, impact, partial fills), capacity beyond a volume-participation ratio, and financing models are not exercised. Dividend-inclusive bars are back-adjusted, so their prices were not tradable historically. In-engine dividend cash crediting is peer-owned (dividend SimulationModule, sota-workflow-resolution).",
   limits=["Same limits as receipt 0."]),
 13: dict(slug="forecast-econometric-matched-comparison", outcome="advanced", evidence_class="local_integration",
   prereg=prereg("13", [FIX2]),
   commands=["see receipt 6 (fcmp parts A and B and merge)"],
   results={"pairwise_dev_bootstrap": {
     "chronos_vs_statsforecast": "-0.000832 [-0.001787, 0.0000076] no difference resolved",
     "statsmodels_arima111_vs_statsforecast": "-0.000825 [-0.002049, 0.0000176] no difference resolved (11/20 folds)",
     "chronos_vs_statsmodels_arima111": "-0.0000066 [-0.000653, 0.000691] no difference resolved (13/20)",
     "statsmodels_arima111_vs_naive": "-0.0000520 [-0.000142, 0.0000318] no difference resolved",
     "kronos_vs_chronos": "+0.02473 [0.01782, 0.03197] chronos better"},
     "reading": "No superiority is established among statsforecast, chronos-bolt-small and statsmodels ARIMA, or of any of them over the naive random walk; Kronos-small is worse than all."},
   raw_files=["run-fcmp-merged-r2__results.json", "run-fcmp-merged__forecasts.json"],
   detection="As receipt 6.",
   remaining="The gap also names feature-extraction (tsfresh, c6) and financial-NLP alternatives, which were not compared (tsfresh only executed, receipt 5). The forecasting/econometric comparison shows no resolved superiority.",
   limits=["As receipt 6."]),
 14: dict(slug="kronos-and-trading-skills-seeded-defects", outcome="advanced", evidence_class="local_integration",
   prereg=prereg("14", [FIX2]),
   commands=["python3 " + BP + "/c13_run.py " + C + "/src/cts " + C + "/c13-work " + C + "/run-c13   # exit 0; runs codex exec --sandbox read-only --ephemeral --skip-git-repo-check -C " + C + "/c13-work -o <run>.last.txt - sequentially, waiting while >=2 codex exec processes run",
             "Kronos: see receipt 7"],
   results={
     "c13_runs": "control-1: 5/5 seeded defects detected, 14 findings, 7 out-of-range, 140.3 s, 12,582 tokens; skill-1: 5/5, 11 findings, 4 out-of-range, 192.4 s, 19,917 tokens; control-2: 5/5, 14 findings, 6 out-of-range, 121.2 s, 11,970 tokens; skill-2: 5/5, 13 findings, 6 out-of-range, 147.0 s, 23,020 tokens. Model reported by codex: gpt-6-astra, reasoning effort ultra.",
     "c13_reading": "Ceiling effect: both arms found every seeded defect, so this fixture cannot discriminate the backtest-expert skill from the control. Skill runs produced slightly fewer out-of-range findings (4 and 6 vs 7 and 6) at 1.6-1.9x the tokens; with n=2 per arm this is not a superiority claim (the preregistered rule required every skill run to beat every control run).",
     "c16": "Kronos-small worse than naive (receipt 7)."},
   raw_files=["run-c13__scores.json", "logs__c13.stdout", "run-c13__prompt-control.txt", "run-c13__prompt-skill.txt",
              "run-c13__control-1.last.txt", "run-c13__skill-1.last.txt", "run-c13__control-2.last.txt", "run-c13__skill-2.last.txt",
              "run-c13__control-1.stderr.txt", "run-c13__skill-1.stderr.txt", "run-c13__control-2.stderr.txt", "run-c13__skill-2.stderr.txt"],
   detection="The scorer was self-tested before the runs: a finding with a matching line but the wrong category scores 0/5, and a synthetic all-correct list scores 5/5 with one out-of-range. Fixture and defects.json were committed in 99efc32 before any run (sha256 4f606a21... and 94b2b032...).",
   remaining="Both executions exist as receipts, but they are not linked as packet evidence_refs (read-only here). The c13 fixture hit a ceiling, so a harder fixture or more runs would be needed to separate the skill from the control. The skill ran under Codex, not in its native Claude harness.",
   limits=["The c13 skill text (SKILL.md plus references/*.md) was inlined into the prompt; the skill's scripts were not run.",
           "The categories were offered to both arms, which may make detection easier."]),
}


def main():
    units = json.loads(Path(sys.argv[1]).read_text())
    unit = next(u for u in units if u["layer_id"] == "research-factors-ml")
    texts = {g["index"]: g["text"] for g in unit["gaps"]}
    if set(texts) != set(RECEIPTS):
        raise SystemExit("gap set mismatch")
    written = []
    for idx, r in sorted(RECEIPTS.items()):
        name = "%d-%s.json" % (idx, r["slug"])
        body = {"id": "gap-wave2-20260923-research-factors-ml-%d-%s" % (idx, r["slug"]), "layer_id": "research-factors-ml", "catalog": "us-equities",
                "gap_index": idx, "gap_text_sha256": hashlib.sha256(texts[idx].encode()).hexdigest(), "gap_text": texts[idx],
                "preregistration": r["prereg"], "commands": r["commands"], "results": r["results"], "outcome": r["outcome"],
                "evidence_class": r["evidence_class"], "detection_method": r["detection"], "remaining": r["remaining"], "limits": r["limits"],
                "raw_outputs": raw(*r["raw_files"]), "checked_at": r.get("checked_at", CHECKED_AT), "checked_at_note": r.get("checked_at_note", CHECKED_AT_NOTE),
                "base_commit": "41d39b3", "branch": "claude/g2-research-factors-ml-20260923"}
        (EV / name).write_text(json.dumps(body, indent=2) + "\n")
        written.append(name)
    # results.json is derived from the receipts on disk, never typed by hand.
    results = {}
    for name in sorted(p.name for p in EV.glob("[0-9]*-*.json")):
        rec = json.loads((EV / name).read_text())
        results[str(rec["gap_index"])] = {"outcome": rec["outcome"], "receipt": "evidence/artifacts/gap-wave2-20260923/us-equities__research-factors-ml/" + name,
                                          "receipt_sha256": hashlib.sha256((EV / name).read_bytes()).hexdigest()}
    (EV / "results.json").write_text(json.dumps({"layer_id": "research-factors-ml", "generated_from": "receipts on disk by " + BP + "/build_receipts.py",
                                                 "results": dict(sorted(results.items(), key=lambda kv: int(kv[0])))}, indent=2) + "\n")
    print(json.dumps({k: v["outcome"] for k, v in results.items()}))


if __name__ == "__main__":
    main()
