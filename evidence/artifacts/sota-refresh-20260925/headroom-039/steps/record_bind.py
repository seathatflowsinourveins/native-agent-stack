"""Bind an installed wheel to the sha256-verified wheel file via its RECORD.

Usage: python3 -B record_bind.py <verified.whl> <site-packages dir>
Every RECORD row with a sha256 is recomputed on the installed file. Exit 0 only
when every headroom/ row matches and no row is missing.
"""

import base64
import csv
import hashlib
import io
import os
import sys
import zipfile

whl, site = sys.argv[1], sys.argv[2]
z = zipfile.ZipFile(whl)
rec = [n for n in z.namelist() if n.endswith(".dist-info/RECORD")][0]
rows = list(csv.reader(io.TextIOWrapper(z.open(rec), "utf-8")))


def digest_of(path: str) -> str:
    d = hashlib.sha256(open(path, "rb").read()).digest()
    return "sha256=" + base64.urlsafe_b64encode(d).rstrip(b"=").decode()


pkg_total = pkg_mis = other_total = other_mis = missing = 0
for path, digest, _size in rows:
    if not digest:
        continue
    f = os.path.join(site, path)
    if not os.path.exists(f):
        missing += 1
        print("MISSING", path)
        continue
    ok = digest_of(f) == digest
    if path.startswith("headroom/"):
        pkg_total += 1
        pkg_mis += not ok
    else:
        other_total += 1
        other_mis += not ok
    if not ok:
        print("MISMATCH", path)
print(
    f"headroom/ rows with sha256: {pkg_total}, mismatches: {pkg_mis}; "
    f"other rows: {other_total}, mismatches: {other_mis}; missing: {missing}"
)
sys.exit(0 if (pkg_mis == 0 and missing == 0 and pkg_total > 0) else 1)
