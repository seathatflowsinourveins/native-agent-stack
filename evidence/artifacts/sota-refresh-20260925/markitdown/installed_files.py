"""Per-file comparison of an installed markitdown distribution with its wheel (read-only).

Usage: python3 -B installed_files.py WHEEL SITE_PACKAGES > installed-files.json
Added 2026-09-26 beside verify_installed.py, which prints counts only. For every wheel
member this lists the wheel RECORD digest, the digest of the wheel member, the digest of
the installed file and whether the installed bytes equal the wheel member. Digests use the
RECORD form (sha256=<urlsafe base64, no padding>) from the PyPA "Recording installed
projects" specification, so each row can be compared with the RECORD inside the PyPI wheel.
Paths are relative to SITE_PACKAGES; the installer rewrites RECORD, so it is listed but not
compared. Exit 0 only when every compared member is present and byte-identical.
"""
import base64
import hashlib
import json
import os
import sys
import zipfile


def digest(data):
    return "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()


wheel, site = sys.argv[1], sys.argv[2]
with open(wheel, "rb") as handle:
    wheel_sha256 = hashlib.sha256(handle.read()).hexdigest()
zf = zipfile.ZipFile(wheel)
names = [n for n in zf.namelist() if not n.endswith("/")]
record_name = next(n for n in names if n.endswith(".dist-info/RECORD"))
record = {}
for line in zf.read(record_name).decode().splitlines():
    if line.strip():
        path, value, _size = line.rsplit(",", 2)
        record[path] = value
rows = []
failures = 0
for n in sorted(names):
    member = zf.read(n)
    p = os.path.join(site, n)
    installed = None
    if os.path.isfile(p):
        with open(p, "rb") as handle:
            installed = handle.read()
    row = {"path": n, "record": record.get(n, ""), "wheel_member": digest(member),
           "installed": digest(installed) if installed is not None else None}
    if n == record_name:
        row["compared"] = False
    else:
        row["identical"] = installed == member
        failures += 0 if row["identical"] else 1
    rows.append(row)
distinfo = record_name.rsplit("/", 1)[0]
added = sorted(set(os.listdir(os.path.join(site, distinfo)))
               - {n.rsplit("/", 1)[1] for n in names if n.startswith(distinfo + "/")})
json.dump({"wheel": os.path.basename(wheel), "wheel_sha256": wheel_sha256, "members": len(names),
           "compared": len(names) - 1, "identical": sum(1 for r in rows if r.get("identical")),
           "installer_added_distinfo_files": added, "files": rows}, sys.stdout, indent=1)
sys.stdout.write("\n")
raise SystemExit(0 if failures == 0 else 1)
