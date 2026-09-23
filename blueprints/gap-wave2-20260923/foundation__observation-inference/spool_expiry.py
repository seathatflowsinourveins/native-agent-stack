#!/usr/bin/env python3
"""Expiry policy for the SDK receipt spool ($STACK_DATA_ROOT/sdk-receipts).

Rule: a completed receipt file (<observation_id>.json) may be deleted only when its
observation_id is confirmed present in Loki, and either
  (a) its mtime is older than --ttl-seconds, or
  (b) free space on the spool filesystem is below --min-free-bytes; then confirmed
      receipts are deleted oldest first until the threshold is met.
Unconfirmed receipts are never deleted: they are reported (count, oldest age) so an
operator can act. '.pending' files older than --pending-grace-seconds are orphans of a
crashed writer (the helper unlinks them itself on any exception) and are removed.
Confirmation queries Loki's native query_range over its retention window; a Loki
error aborts without deleting anything. --dry-run reports without deleting.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


def confirmed_ids_from_loki(loki_url, lookback_s=72 * 3600, limit=5000, timeout=10):
    end = time.time_ns()
    start = end - lookback_s * 10**9
    q = urllib.parse.urlencode({'query': '{service_name="codex-sdk-receipt"}', 'start': str(start), 'end': str(end),
                                'limit': str(limit), 'direction': 'forward'})
    with urllib.request.urlopen(f'{loki_url}/loki/api/v1/query_range?{q}', timeout=timeout) as r:
        body = json.loads(r.read())
    ids = set()
    for s in body['data']['result']:
        oid = s['stream'].get('observation_id') or s['stream'].get('receipt_id')
        if oid:
            ids.add(oid)
    return ids


def plan(entries, confirmed, now, ttl_s, free_bytes, min_free_bytes, pending_grace_s=3600):
    """Pure policy. entries: list of dicts {name, mtime, size, blocks_bytes}. Returns (delete, keep_unconfirmed, orphans)."""
    receipts = [e for e in entries if e['name'].endswith('.json')]
    orphans = [e for e in entries if e['name'].endswith('.pending') and now - e['mtime'] > pending_grace_s]
    delete = []
    unconfirmed = []
    for e in receipts:
        oid = e['name'][:-5]
        if oid not in confirmed:
            unconfirmed.append(e)
        elif now - e['mtime'] > ttl_s:
            delete.append(e)
    freed = free_bytes + sum(e['blocks_bytes'] for e in delete + orphans)
    if min_free_bytes and freed < min_free_bytes:
        extra = sorted((e for e in receipts if e['name'][:-5] in confirmed and e not in delete), key=lambda e: e['mtime'])
        for e in extra:
            if freed >= min_free_bytes:
                break
            delete.append(e)
            freed += e['blocks_bytes']
    return delete, unconfirmed, orphans


def scan(spool):
    out = []
    for p in Path(spool).iterdir():
        if p.is_file() and (p.name.endswith('.json') or p.name.endswith('.pending')):
            st = p.stat()
            out.append({'name': p.name, 'mtime': st.st_mtime, 'size': st.st_size, 'blocks_bytes': st.st_blocks * 512})
    return out


def run(spool, loki_url, ttl_s, min_free_bytes, pending_grace_s=3600, dry_run=False, confirmed=None):
    entries = scan(spool)
    if confirmed is None:
        confirmed = confirmed_ids_from_loki(loki_url)
    vfs = os.statvfs(spool)
    free = vfs.f_bavail * vfs.f_frsize
    now = time.time()
    delete, unconfirmed, orphans = plan(entries, confirmed, now, ttl_s, free, min_free_bytes, pending_grace_s)
    if not dry_run:
        for e in delete + orphans:
            (Path(spool) / e['name']).unlink(missing_ok=True)
    vfs2 = os.statvfs(spool)
    return {'scanned': len(entries), 'confirmed_known': len(confirmed), 'deleted': len(delete),
            'deleted_names': sorted(e['name'] for e in delete), 'orphans_removed': len(orphans),
            'unconfirmed_kept': len(unconfirmed),
            'oldest_unconfirmed_age_s': round(now - min(e['mtime'] for e in unconfirmed), 1) if unconfirmed else None,
            'free_bytes_before': free, 'free_bytes_after': vfs2.f_bavail * vfs2.f_frsize, 'dry_run': dry_run}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--spool', required=True)
    ap.add_argument('--loki-url', required=True)
    ap.add_argument('--ttl-seconds', type=int, default=72 * 3600)
    ap.add_argument('--min-free-bytes', type=int, default=0)
    ap.add_argument('--pending-grace-seconds', type=int, default=3600)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    print(json.dumps(run(a.spool, a.loki_url, a.ttl_seconds, a.min_free_bytes, a.pending_grace_seconds, a.dry_run), indent=2))


if __name__ == '__main__':
    sys.exit(main())
