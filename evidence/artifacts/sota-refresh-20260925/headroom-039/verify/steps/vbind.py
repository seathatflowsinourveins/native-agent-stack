"""Verifier's independent RECORD binding. Usage: python3 -B vbind.py WHEEL SITE_PACKAGES
Recomputes every wheel RECORD sha256 on the installed files, and lists installed files
under headroom/ and the dist-info that the wheel RECORD does not name (extra files)."""
import base64, csv, hashlib, io, os, sys, zipfile
whl, site = sys.argv[1], sys.argv[2]
z = zipfile.ZipFile(whl)
rec_name = next(n for n in z.namelist() if n.endswith('.dist-info/RECORD'))
rows = list(csv.reader(io.TextIOWrapper(z.open(rec_name), 'utf-8')))
named = {r[0] for r in rows}
def b64(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return 'sha256=' + base64.urlsafe_b64encode(h.digest()).rstrip(b'=').decode()
stats = {'pkg_rows': 0, 'pkg_mismatch': 0, 'other_rows': 0, 'other_mismatch': 0, 'missing': 0, 'no_digest_rows': 0}
# also check the wheel's own zip members against RECORD (wheel self-consistency)
wheel_self_mismatch = 0
for path, digest, size in rows:
    if not digest:
        stats['no_digest_rows'] += 1
        continue
    zd = 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(z.read(path)).digest()).rstrip(b'=').decode()
    wheel_self_mismatch += zd != digest
    f = os.path.join(site, path)
    key = 'pkg' if path.startswith('headroom/') else 'other'
    if not os.path.isfile(f):
        stats['missing'] += 1; print('MISSING', path); continue
    stats[key + '_rows'] += 1
    if b64(f) != digest:
        stats[key + '_mismatch'] += 1; print('MISMATCH', path)
extra = []
dist = rec_name.split('/')[0]
for top in ('headroom', dist):
    for d, dirs, files in os.walk(os.path.join(site, top)):
        for fn in files:
            rel = os.path.relpath(os.path.join(d, fn), site)
            if rel not in named:
                extra.append(rel)
pycache = sum(1 for d, dirs, files in os.walk(os.path.join(site, 'headroom')) if os.path.basename(d) == '__pycache__')
print('wheel RECORD rows:', len(rows), 'wheel self-consistency mismatches:', wheel_self_mismatch)
print('stats:', stats)
print('installed files not named by wheel RECORD:', sorted(extra))
print('__pycache__ dirs under headroom/:', pycache)
ok = stats['pkg_mismatch'] == 0 and stats['other_mismatch'] == 0 and stats['missing'] == 0 and stats['pkg_rows'] > 0 and wheel_self_mismatch == 0
print('BIND', 'OK' if ok else 'FAIL')
sys.exit(0 if ok else 1)
