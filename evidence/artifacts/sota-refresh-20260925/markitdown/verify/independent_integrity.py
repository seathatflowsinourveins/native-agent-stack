"""Independent read-only integrity check of the markitdown 0.1.8 qualification prefix.

Usage: python3 -B independent_integrity.py WHEEL PREFIX BASELINE_ENV
  WHEEL         hash-verified markitdown-0.1.8 wheel (fresh download by the verifier)
  PREFIX        ~/.local/share/codex-ecosystem/tools/markitdown-0.1.8
  BASELINE_ENV  ~/.local/share/codex-ecosystem/python-tools/markitdown (production 0.1.7, read only)
Opens every file read-only; writes nothing.
"""
import base64
import glob
import hashlib
import json
import os
import stat
import sys
import zipfile

wheel, prefix, base_env = sys.argv[1:4]
env = os.path.join(prefix, "uv-tools", "markitdown")
sp = glob.glob(os.path.join(env, "lib", "python3.*", "site-packages"))
assert len(sp) == 1, sp
sp = sp[0]
base_sp = glob.glob(os.path.join(base_env, "lib", "python3.*", "site-packages"))[0]
out = {}


def b64sha(data, algo="sha256"):
    return base64.urlsafe_b64encode(hashlib.new(algo, data).digest()).rstrip(b"=").decode()


def read(p):
    with open(p, "rb") as f:
        return f.read()


# 1. wheel members vs installed files (byte equality), RECORD excluded
zf = zipfile.ZipFile(wheel)
members = [n for n in zf.namelist() if not n.endswith("/")]
rec_name = next(n for n in members if n.endswith(".dist-info/RECORD"))
same = differ = missing = 0
for n in members:
    if n == rec_name:
        continue
    p = os.path.join(sp, n)
    if not os.path.isfile(p):
        missing += 1
    elif read(p) == zf.read(n):
        same += 1
    else:
        differ += 1
out["wheel_vs_installed"] = {"members": len(members), "compared": same + differ + missing,
                             "identical": same, "differ": differ, "missing": missing}

# 2. every dist's installed RECORD: hash of each listed file, and files not covered by any RECORD
covered = set()
dists = {}
for di in sorted(x for x in os.listdir(sp) if x.endswith(".dist-info")):
    rows = [l for l in read(os.path.join(sp, di, "RECORD")).decode().splitlines() if l.strip()]
    ok = bad = nohash = 0
    for l in rows:
        path, digest, _size = l.rsplit(",", 2)
        full = os.path.normpath(os.path.join(sp, path))
        covered.add(full)
        if not digest:
            nohash += 1
            continue
        algo, want = digest.split("=", 1)
        if os.path.isfile(full) and b64sha(read(full), algo) == want:
            ok += 1
        else:
            bad += 1
    dists[di] = {"ok": ok, "bad": bad, "nohash": nohash}
out["installed_record_check"] = {
    "dists": len(dists), "entries_ok": sum(d["ok"] for d in dists.values()),
    "entries_bad": sum(d["bad"] for d in dists.values()),
    "bad_dists": [k for k, d in dists.items() if d["bad"]],
}
uncovered = []
pyc = 0
for dp, dn, fn in os.walk(sp):
    for f in fn:
        full = os.path.normpath(os.path.join(dp, f))
        if f.endswith(".pyc"):
            pyc += 1
        if full not in covered:
            uncovered.append(os.path.relpath(full, sp))
out["site_packages_files_not_in_any_RECORD"] = sorted(uncovered)
out["site_packages_pyc"] = pyc
all_pyc = 0
for dp, dn, fn in os.walk(prefix):
    all_pyc += sum(1 for f in fn if f.endswith(".pyc"))
out["prefix_pyc_total"] = all_pyc

# 3. transitive set: candidate RECORD vs baseline RECORD for every non-markitdown dist (site-packages paths only)
def rmap(spath, di):
    m = {}
    for l in read(os.path.join(spath, di, "RECORD")).decode().splitlines():
        if not l.strip():
            continue
        path, digest, _ = l.rsplit(",", 2)
        if path.startswith("../") or not digest:
            continue
        m[path] = digest
    return m


cand = sorted(x for x in os.listdir(sp) if x.endswith(".dist-info") and not x.startswith("markitdown-"))
base = sorted(x for x in os.listdir(base_sp) if x.endswith(".dist-info") and not x.startswith("markitdown-"))
eq = 0
neq = []
files = 0
for di in cand:
    if di not in base:
        neq.append(di + " (absent in baseline)")
        continue
    a, b = rmap(sp, di), rmap(base_sp, di)
    files += len(a)
    if a == b:
        eq += 1
    else:
        neq.append(di)
out["transitive_vs_baseline"] = {"candidate_dists": len(cand), "baseline_dists": len(base),
                                 "same_names": cand == base, "record_equal": eq, "unequal": neq,
                                 "site_packages_files": files}

# 4. entry point script and interpreter link
ep = os.path.join(env, "bin", "markitdown")
out["entry_point_script"] = read(ep).decode()
out["bin_link"] = os.readlink(os.path.join(prefix, "bin", "markitdown"))
out["python_link"] = os.readlink(os.path.join(env, "bin", "python"))
out["python_link_resolved"] = os.path.realpath(os.path.join(env, "bin", "python"))
home = os.path.expanduser("~")
print(json.dumps(out, indent=1).replace(home, "~"))
