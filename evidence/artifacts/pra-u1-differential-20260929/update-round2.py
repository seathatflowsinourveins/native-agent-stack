"""Round 2 of the U1 pivot's differential evidence: re-run the shape scan, the whole-record identity check and the scaling measurement,
and splice them into counts.json. Every other section of counts.json (the differential, the oracle over fresh seeds, the M4 identity,
the timing and the transcript states) stays as round 1 measured it, on the kernel whose sha256 `kernels.new_sha256` names.

    python3 update-round2.py --repo <checkout> --scanner <0c421c66 child-usage.mjs> --baseline <33dcfd24 child-usage.mjs> --work <private dir> \\
        --real <real-commands.json> --real-until <instant> [--until-reconstructed] [--identity NAME=PATH ...] \\
        [--differential NAME=INPUTS[:VALID] ...] [--sizes 2000,4000,8000,16000,32000] [--limit-ms 10000] [--counts <counts.json>]

--scanner is the scanner reading of commit 0c421c66 (a second opinion in the shape scan) and --baseline the kernel that round 1 measured
(`git show 33dcfd24:examples/claude-native/workflows/child-usage.mjs`, sha256 a9126a77...): the identity check compares its whole
commandInvocations and cli_lanes records with the kernel of --repo on every --identity corpus (JSON arrays of shell texts, none filtered
by bash -n), and scaling.mjs times both. --differential re-runs differential.mjs (no reduction) of --scanner against the kernel on a corpus
(INPUTS a JSON array of shell texts, VALID the optional bash -n validity list of round 1) and records its totals with `equal_to_round1`: whether
they equal round 1's record of the same corpus (`distinct_witnesses`, which needs a reduction, is not compared; null when round 1 has no record).
--work holds copies of the two kernels beside the pin file and must stay outside every checkout.
--real is the output of real-commands.mjs (--real-until its cutoff; --until-reconstructed says the cutoff was recovered rather than
recorded). Why not the driver of round 1: it captures the covering tests again (which now hold new fixtures, so their count of 728
would change), and recounts the live transcript store (which has grown, so the 5,074 files would not repeat).
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--repo", required=True)
parser.add_argument("--scanner", required=True)
parser.add_argument("--baseline", required=True)
parser.add_argument("--work", required=True)
parser.add_argument("--real", required=True)
parser.add_argument("--real-until")
parser.add_argument("--until-reconstructed", action="store_true")
parser.add_argument("--identity", nargs="*", default=[], help="NAME=PATH of a list of shell texts")
parser.add_argument("--differential", nargs="*", default=[], help="NAME=INPUTS[:VALID]: a corpus for the differential of --scanner against the kernel")
parser.add_argument("--sizes", default="2000,4000,8000,16000,32000")
parser.add_argument("--limit-ms", default="10000")
parser.add_argument("--counts")
args = parser.parse_args()
here = Path(__file__).resolve().parent
repo = Path(args.repo).resolve()
work = Path(args.work).resolve()
work.mkdir(parents=True, exist_ok=True)
counts_path = Path(args.counts) if args.counts else here / "counts.json"
kernel = repo / "examples/claude-native/workflows/child-usage.mjs"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def node(script, *argv):
    done = subprocess.run(["node", str(here / script), *map(str, argv)], capture_output=True, text=True, check=False)
    if done.returncode:
        sys.exit(script + " failed: " + done.stderr[-600:])
    return json.loads(done.stdout)


# The baseline and the scanner run from copies beside the pin file: a kernel that loads the parser reads its pin next to itself.
shutil.copy(kernel.parent / "shell-parser.pin.json", work / "shell-parser.pin.json")
baseline, scanner = work / "baseline-kernel.mjs", work / "scanner-kernel.mjs"
shutil.copy(args.baseline, baseline)
shutil.copy(args.scanner, scanner)

real = Path(args.real)
corpus = {"source": "real-commands.mjs", "until": args.real_until, "until_reconstructed": bool(args.until_reconstructed),
          "distinct_shell_texts": len(json.loads(real.read_text()))}
shapes = node("shape-counts.mjs", "--kernel", kernel, "--inputs", real, "--scanner", scanner)
identity = {"baseline_sha256": sha(baseline), "kernel_sha256": sha(kernel), "corpora": {}}
for spec in args.identity:
    name, path = spec.split("=", 1)
    identity["corpora"][name] = node("m4-identity.mjs", "--a", baseline, "--b", kernel, "--inputs", path, "--fields", "lanes")
scaling = {which: node("scaling.mjs", "--kernel", path, "--sizes", args.sizes, "--limit-ms", args.limit_ms) for which, path in (("baseline", baseline), ("kernel", kernel))}

counts = json.loads(counts_path.read_text())
rerun = {}
for spec in args.differential:
    name, paths = spec.split("=", 1)
    inputs, _, valid = paths.partition(":")
    totals = node("differential.mjs", "--old", scanner, "--new", kernel, "--inputs", inputs, *(["--valid", valid] if valid else []))
    before = counts.get("differential", {}).get(name)
    same = None if before is None else all(before.get(k) == v for k, v in totals.items())
    rerun[name] = {**totals, "equal_to_round1": same}
sections = ["corpus", "shapes", "lanes_identity", "scaling"] + (["differential_rerun"] if rerun else [])
counts.update({"corpus": corpus, "shapes": shapes, "lanes_identity": identity, "scaling": scaling, **({"differential_rerun": rerun} if rerun else {}),
               "round2": {"sections": sections,
                          "other_sections_measured_on_kernel_sha256": counts.get("kernels", {}).get("new_sha256")}})
counts_path.write_text(json.dumps(counts, indent=1) + "\n")
print(json.dumps({"written": str(counts_path.name), "kernel_sha256": identity["kernel_sha256"][:12],
                  "identity_different": {k: v["different"] for k, v in identity["corpora"].items()},
                  "overturn_1_met": shapes["overturn_1"]["met_by_the_upper_bound"]}))
