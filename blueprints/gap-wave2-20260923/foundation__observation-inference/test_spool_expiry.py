#!/usr/bin/env python3
"""Offline tests for spool_expiry.plan/run (no Loki; confirmation set injected)."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spool_expiry as se  # noqa: E402


def E(name, age, now, size=4096):
    return {'name': name, 'mtime': now - age, 'size': 300, 'blocks_bytes': size}


class PlanTests(unittest.TestCase):
    def test_ttl_deletes_only_confirmed_old(self):
        now = 1000.0
        entries = [E('a.json', 500, now), E('b.json', 50, now), E('c.json', 500, now)]
        d, u, o = se.plan(entries, {'a', 'b'}, now, ttl_s=100, free_bytes=10**9, min_free_bytes=0)
        self.assertEqual([x['name'] for x in d], ['a.json'])
        self.assertEqual([x['name'] for x in u], ['c.json'])
        self.assertEqual(o, [])

    def test_pressure_deletes_confirmed_oldest_first_never_unconfirmed(self):
        now = 1000.0
        entries = [E('new.json', 10, now), E('old.json', 90, now), E('mid.json', 50, now), E('unc.json', 999, now)]
        d, u, _ = se.plan(entries, {'new', 'old', 'mid'}, now, ttl_s=10**6, free_bytes=0, min_free_bytes=8192)
        self.assertEqual([x['name'] for x in d], ['old.json', 'mid.json'])
        self.assertEqual([x['name'] for x in u], ['unc.json'])

    def test_pressure_cannot_satisfy_keeps_unconfirmed(self):
        now = 1000.0
        entries = [E('x.json', 10, now), E('y.json', 10, now)]
        d, u, _ = se.plan(entries, set(), now, ttl_s=1, free_bytes=0, min_free_bytes=10**9)
        self.assertEqual(d, [])
        self.assertEqual(len(u), 2)

    def test_orphan_pending_after_grace(self):
        now = 1000.0
        entries = [E('p1.pending', 5000, now), E('p2.pending', 5, now)]
        _, _, o = se.plan(entries, set(), now, ttl_s=1, free_bytes=0, min_free_bytes=0, pending_grace_s=3600)
        self.assertEqual([x['name'] for x in o], ['p1.pending'])


class RunTests(unittest.TestCase):
    def test_run_deletes_files_and_dry_run_does_not(self):
        with tempfile.TemporaryDirectory() as d:
            for n in ('k1', 'k2', 'k3'):
                p = Path(d) / f'{n}.json'
                p.write_text('{}\n')
                os.utime(p, (time.time() - 500, time.time() - 500))
            r = se.run(d, None, ttl_s=100, min_free_bytes=0, dry_run=True, confirmed={'k1', 'k2'})
            self.assertEqual(r['deleted'], 2)
            self.assertEqual(len(list(Path(d).iterdir())), 3)
            r = se.run(d, None, ttl_s=100, min_free_bytes=0, confirmed={'k1', 'k2'})
            self.assertEqual(sorted(p.name for p in Path(d).iterdir()), ['k3.json'])
            self.assertEqual(r['unconfirmed_kept'], 1)

    def test_loki_error_aborts_without_deleting(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'z.json'
            p.write_text('{}\n')
            os.utime(p, (0, 0))
            with self.assertRaises(Exception):
                se.run(d, 'http://127.0.0.1:9', ttl_s=1, min_free_bytes=0)
            self.assertTrue(p.exists())


if __name__ == '__main__':
    unittest.main()
