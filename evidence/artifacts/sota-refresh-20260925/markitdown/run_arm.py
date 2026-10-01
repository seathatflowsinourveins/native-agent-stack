"""Run the refuter's corrected markitdown acceptance legs against one executable (one arm).

Usage: python3 -B run_arm.py ARM M PIP_PY RUN_DIR REPO CHECKER OUT.json
  ARM      label (candidate-0.1.8 | baseline-0.1.7)
  M        markitdown executable of the arm
  PIP_PY   interpreter of the arm's tool env (for `uv pip list --python`)
  RUN_DIR  NEW output dir for this arm (must not exist)
Legs mirror corrected_acceptance_check (install leg is recorded separately for the candidate).
Every leg is recorded (not fail-fast); overall pass = all legs pass for the 0.1.8 expectations.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time

ARM, M, PIP_PY, RUN_DIR, REPO, CHECKER, OUT = sys.argv[1:8]
HOME = os.path.expanduser("~")
IMPL = os.path.dirname(os.path.abspath(__file__))
SCRATCH_ROOT = IMPL.split("/sota-refresh/")[0]

EXP_VERSION = "markitdown 0.1.8"
EXP_8K_STDOUT = "a27f0f27487e634d2eb2ae8d10720845cbbff3ce3fccc8878ee0283eca3ef28b"
EXP_DISC_HTML = "932d7f622c511667e6ae4c745a05c24184c5009450824a84b58485f17b8c879e"
EXP_SET = {
    "beautifulsoup4": "4.15.0", "certifi": "2026.7.22", "charset-normalizer": "3.5.1", "click": "8.5.0",
    "defusedxml": "0.7.1", "flatbuffers": "25.12.19", "idna": "3.20", "magika": "0.6.3",
    "markdownify": "1.2.3", "markitdown": "0.1.8", "numpy": "2.5.3", "onnxruntime": "1.30.0",
    "packaging": "26.3", "protobuf": "7.36.2", "python-dotenv": "1.2.3", "requests": "2.34.2",
    "six": "1.17.0", "soupsieve": "2.10", "typing-extensions": "4.16.0", "urllib3": "2.8.0",
}
EXTRAS_RE = re.compile(r"^(pdfminer-six|pdfplumber|mammoth|lxml|openpyxl|python-pptx|pandas|olefile|xlrd) ", re.I | re.M)

ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", UV_PYTHON_DOWNLOADS="never",
           UV_CACHE_DIR=os.path.join(IMPL, "uv-cache"), RUN_DIR=RUN_DIR)


def san(s):
    s = s.replace(IMPL, "$IMPL").replace(SCRATCH_ROOT, "<scratchpad>")
    return s.replace(HOME, "~")


def run(argv, stdout_file=None, stderr_file=None, shell=False):
    t = time.monotonic()
    so = open(stdout_file, "wb") if stdout_file else subprocess.PIPE
    se = open(stderr_file, "wb") if stderr_file else subprocess.PIPE
    p = subprocess.run(argv, stdout=so, stderr=se, env=ENV, shell=shell, cwd=IMPL,
                       executable="/bin/bash" if shell else None)
    return p.returncode, (p.stdout if not stdout_file else b""), (p.stderr if not stderr_file else b""), round(time.monotonic() - t, 2)


steps = []


def rec(name, cmd, rc, ok, excerpt, secs):
    steps.append({"name": name, "arm": ARM, "cmd": san(cmd), "exit": rc, "pass": bool(ok),
                  "output_excerpt": san(excerpt)[:600], "seconds": secs})
    print(f"{'PASS' if ok else 'FAIL'} [{ARM}] {name} exit={rc} :: {san(excerpt)[:300]}")


def sha_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


assert not os.path.exists(RUN_DIR), "RUN_DIR must be new"
os.makedirs(RUN_DIR)
K = os.path.join(REPO, "blueprints/us-equities/catalyst-provenance/upstream-8k.html")
G = os.path.join(REPO, "fixtures/greeting.html")
PDF = os.path.join(REPO, "blueprints/convergence-practice/document-ingestion/corpus/lumen-qualification.pdf")

# L1 version
rc, out, err, s = run([M, "--version"])
v = out.decode().strip()
rec("L1 version == 'markitdown 0.1.8'", f'"{M}" --version', rc, rc == 0 and v == EXP_VERSION, f"stdout={v!r}", s)

# L2 greeting -o
gm = os.path.join(RUN_DIR, "greeting.md")
rc, out, err, s = run([M, G, "-o", gm])
rec("L2 greeting.html -o greeting.md", f'"{M}" "{G}" -o "{gm}"', rc, rc == 0 and os.path.isfile(gm),
    f"sha256={sha_file(gm) if os.path.isfile(gm) else None} bytes={os.path.getsize(gm) if os.path.isfile(gm) else None} stderr={err.decode()[-200:]!r}", s)

# L3 8-K -o
km = os.path.join(RUN_DIR, "8k.md")
rc, out, err, s = run([M, K, "-o", km])
rec("L3 upstream-8k.html -o 8k.md", f'"{M}" "{K}" -o "{km}"', rc, rc == 0 and os.path.isfile(km),
    f"sha256={sha_file(km) if os.path.isfile(km) else None} bytes={os.path.getsize(km) if os.path.isfile(km) else None} stderr={err.decode()[-200:]!r}", s)

# L4 8-K stdout hash tied to the retained repository hash
rc, out, err, s = run([M, K])
h = hashlib.sha256(out).hexdigest()
open(os.path.join(RUN_DIR, "8k.stdout.md"), "wb").write(out)
rec("L4 8-K stdout sha256 == a27f0f27 (retained at evidence/receipts/token-practice-artifacts-20260920.json:217)",
    f'"{M}" "{K}" | sha256sum', rc, rc == 0 and h == EXP_8K_STDOUT, f"sha256={h} bytes={len(out)}", s)

# L5 discriminator input (exact printf from the corrected check)
printf = ("printf '%s\\n' '<!doctype html><html><body>' '<p>First<u>word</u>Last</p>' "
          "'<p><a href=\"https://example.com/items/a%2Fb\">example</a></p>' '<p><strike>gone</strike></p>' "
          "'<p><img src=\"data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBTAA7\" "
          "data-src=\"https://example.com/photo.jpg\" alt=\"A photo\"></p>' '</body></html>' > \"$RUN_DIR/disc.html\"")
rc, out, err, s = run(printf, shell=True)
dh = os.path.join(RUN_DIR, "disc.html")
dsha = sha_file(dh) if os.path.isfile(dh) else None
rec("L5 disc.html sha256 == 932d7f62", printf.replace("$RUN_DIR", RUN_DIR), rc, rc == 0 and dsha == EXP_DISC_HTML,
    f"sha256={dsha} bytes={os.path.getsize(dh) if os.path.isfile(dh) else None}", s)

# L6 disc -o
dm = os.path.join(RUN_DIR, "disc.md")
rc, out, err, s = run([M, dh, "-o", dm])
body = open(dm, encoding="utf-8").read() if os.path.isfile(dm) else ""
rec("L6 disc.html -o disc.md", f'"{M}" "{dh}" -o "{dm}"', rc, rc == 0 and os.path.isfile(dm),
    f"sha256={sha_file(dm) if os.path.isfile(dm) else None} content={body!r}", s)

# L7 PDF refusal on the base prefix
pm, pe = os.path.join(RUN_DIR, "pdf.md"), os.path.join(RUN_DIR, "pdf.err")
rc, out, err, s = run([M, PDF, "-o", pm], stderr_file=pe)
perr = open(pe, encoding="utf-8", errors="replace").read()
last = [l for l in perr.splitlines() if l.strip()][-3:]
rec("L7 PDF refused (exit!=0, stderr names markitdown[pdf])", f'"{M}" "{PDF}" -o "{pm}" 2>"{pe}"', rc,
    rc != 0 and "markitdown[pdf]" in perr, f"stderr_tail={last!r} pdf.md_exists={os.path.exists(pm)}", s)

# L8 reviewer checker (12 checks)
rc, out, err, s = run(["python3", "-B", CHECKER, RUN_DIR])
lines = out.decode().splitlines()
npass = sum(1 for l in lines if l.startswith("PASS "))
nfail = sum(1 for l in lines if l.startswith("FAIL "))
rec("L8 check_outputs.py: 12 PASS, exit 0", f'python3 "{CHECKER}" "{RUN_DIR}"', rc, rc == 0 and npass == 12 and nfail == 0,
    f"PASS={npass} FAIL={nfail} failed={[l[5:] for l in lines if l.startswith('FAIL ')]}", s)

# L9 uv pip list: recorded set and no extras
pl = os.path.join(RUN_DIR, "pip-list.txt")
rc, out, err, s = run(["uv", "pip", "list", "--python", PIP_PY], stdout_file=pl)
txt = open(pl).read()
got = {}
for l in txt.splitlines()[2:]:
    parts = l.split()
    if len(parts) >= 2:
        got[parts[0].lower()] = parts[1]
extras = EXTRAS_RE.findall(txt)
diff = {k: (EXP_SET.get(k), got.get(k)) for k in sorted(set(EXP_SET) | set(got)) if EXP_SET.get(k) != got.get(k)}
rec("L9 uv pip list == recorded 20-package set, no extras", f'uv pip list --python "{PIP_PY}" > "{pl}"', rc,
    rc == 0 and not extras and not diff, f"packages={len(got)} extras_found={extras} diff_vs_recorded={diff}", s)

# L10 optional consumer leg (content not saved; only markers and hash)
doc = os.path.join(HOME, ".local/state/nativestack/final-acceptance/document.html")
if os.path.isfile(doc):
    rc, out, err, s = run([M, doc])
    t = out.decode("utf-8", "replace")
    ok = rc == 0 and "# NativeStack evidence" in t and "Scoped memory" in t
    rec("L10 optional consumer leg: document.html has '# NativeStack evidence' and 'Scoped memory'", f'"{M}" "{doc}"', rc, ok,
        f"has_heading={'# NativeStack evidence' in t} has_scoped_memory={'Scoped memory' in t} stdout_sha256={hashlib.sha256(out).hexdigest()} bytes={len(out)} input_sha256={sha_file(doc)}", s)
else:
    rec("L10 optional consumer leg", f'test -f "{doc}"', 1, False, "document.html absent; leg not run", 0)

overall = all(x["pass"] for x in steps)
json.dump({"arm": ARM, "overall_pass": overall, "steps": steps}, open(OUT, "w"), indent=1)
print(f"ARM {ARM} overall_pass={overall} legs={len(steps)} passed={sum(x['pass'] for x in steps)}")
