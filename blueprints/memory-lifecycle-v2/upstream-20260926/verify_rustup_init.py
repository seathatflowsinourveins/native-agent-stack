#!/usr/bin/env python3
"""Check the rustup-init that setup.sh ran against rustup's published checksum.

Hashes the binary, reads the `.sha256` sidecar downloaded with it, and fetches the official
checksum for the stated rustup version from
https://static.rust-lang.org/rustup/archive/<version>/x86_64-unknown-linux-gnu/rustup-init.sha256.
The binary passes only when its sha256 equals both. As a discriminating control, the same
comparison runs on the binary's bytes with the last byte flipped in memory and must fail.
Prints JSON with the scratch root as `<scratch>`. Standard library only.

    python3 verify_rustup_init.py --binary PATH --sidecar PATH --rustup-version 1.29.1 --scratch ROOT
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

TARGET = 'x86_64-unknown-linux-gnu'


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def mtime(path):
    return datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--sidecar', required=True, type=Path)
    parser.add_argument('--rustup-version', required=True)
    parser.add_argument('--scratch', required=True, type=Path)
    args = parser.parse_args()
    scratch = str(args.scratch.resolve())

    def public(text):
        return str(text).replace(scratch, '<scratch>')

    started = now()
    data = args.binary.read_bytes()
    binary_sha256 = hashlib.sha256(data).hexdigest()
    sidecar = args.sidecar.read_text().strip()
    url = f'https://static.rust-lang.org/rustup/archive/{args.rustup_version}/{TARGET}/rustup-init.sha256'
    request = urllib.request.Request(url, headers={'User-Agent': 'memory-lifecycle-v2-verify'})
    with urllib.request.urlopen(request, timeout=60) as response:
        status, official = response.status, response.read().decode().strip()
    official_sha256 = official.split()[0]
    flipped = hashlib.sha256(data[:-1] + bytes([data[-1] ^ 0xFF])).hexdigest()
    matches_sidecar = binary_sha256 == sidecar.split()[0]
    matches_official = binary_sha256 == official_sha256
    result = {
        'argv': [public(arg) for arg in [Path(sys.argv[0]).name] + sys.argv[1:]],
        'rustup_version': args.rustup_version,
        'started_utc': started,
        'binary': public(args.binary.resolve()), 'binary_bytes': len(data), 'binary_mtime_utc': mtime(args.binary),
        'binary_sha256': binary_sha256,
        'sidecar': public(args.sidecar.resolve()), 'sidecar_mtime_utc': mtime(args.sidecar), 'sidecar_line': sidecar,
        'official_url': url, 'official_http_status': status, 'official_line': official,
        'binary_matches_sidecar': matches_sidecar,
        'binary_matches_official_archive': matches_official,
        'control': {'mutation': 'last byte of the binary flipped in memory', 'sha256': flipped,
                    'matches_official_archive': flipped == official_sha256,
                    'failed_as_expected': flipped != official_sha256},
        'verdict': 'passed' if matches_sidecar and matches_official and flipped != official_sha256 else 'failed',
        'finished_utc': now(),
    }
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['verdict'] == 'passed' else 1)


if __name__ == '__main__':
    main()
