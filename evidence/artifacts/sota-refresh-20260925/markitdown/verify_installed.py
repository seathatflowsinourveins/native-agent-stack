"""Compare an installed markitdown distribution with a hash-verified wheel (read-only).

Usage: python3 -B verify_installed.py WHEEL SITE_PACKAGES
1. wheel self-consistency: every RECORD entry's sha256 (urlsafe b64) matches the zip member
2. every non-RECORD wheel member is byte-identical to the installed file
3. lists installer-added files in the installed dist-info
Exit 0 only when 1 and 2 hold for every member.
"""
import base64
import hashlib
import os
import sys
import zipfile

wheel, site = sys.argv[1], sys.argv[2]
zf = zipfile.ZipFile(wheel)
names = [n for n in zf.namelist() if not n.endswith("/")]
record_name = next(n for n in names if n.endswith(".dist-info/RECORD"))
distinfo = record_name.rsplit("/", 1)[0]

bad_record = 0
recorded = 0
for line in zf.read(record_name).decode().splitlines():
    if not line.strip():
        continue
    path, digest, _size = line.rsplit(",", 2)
    if not digest:
        continue
    algo, b64 = digest.split("=", 1)
    got = base64.urlsafe_b64encode(hashlib.new(algo, zf.read(path)).digest()).rstrip(b"=").decode()
    recorded += 1
    if got != b64:
        bad_record += 1
        print("RECORD-MISMATCH", path)

same = diff = missing = 0
for n in names:
    if n == record_name:
        continue
    p = os.path.join(site, n)
    if not os.path.isfile(p):
        missing += 1
        print("MISSING", n)
        continue
    if open(p, "rb").read() == zf.read(n):
        same += 1
    else:
        diff += 1
        print("DIFFERS", n)

inst_di = os.path.join(site, distinfo)
extra = sorted(set(os.listdir(inst_di)) - {n.rsplit("/", 1)[1] for n in names if n.startswith(distinfo + "/")})
print(f"wheel_members={len(names)} record_entries_checked={recorded} record_mismatches={bad_record}")
print(f"installed_identical={same} installed_differs={diff} installed_missing={missing} (RECORD excluded)")
print("installer_added_distinfo_files=" + ",".join(extra))
raise SystemExit(0 if bad_record == 0 and diff == 0 and missing == 0 else 1)
