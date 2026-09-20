"""Install one verified restic release into a new, owned directory; no PATH change."""
from __future__ import annotations
import argparse
import bz2
import hashlib
import json
from pathlib import Path
import subprocess
import time

VERSION = '0.19.1'
COMMIT = '6aa3a516ce654808a1f28f9fa21e9b7c8e6e90bf'
FINGERPRINT = 'CF8F18F2844575973F79D4E191A6868BD3F7A907'
ASSETS = {
    'restic_0.19.1_linux_amd64.bz2': 'f415415624dcc452f2a02b8c33641791a8c6d6d3b65bbb3543fcf9a25151585c',
    'SHA256SUMS': 'fb520966ee01d2a3d4219c66762c66efa56300833b6f639f36082b7462f91cb8',
    'SHA256SUMS.asc': '649f3a48d322c3d7a457ef58e2dc4c5094b1f823192cdbac3f092ea23e194d9a',
}
LICENSE_SHA = '6f08a01a9fab5b24e139a09f15cc24a73087c7bc09e3bacf099fdf2d767bf897'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    root = args.destination.expanduser().absolute()
    root.mkdir(mode=0o700)
    (root/'gpg').mkdir(mode=0o700)
    report = {'version': VERSION, 'source_commit': COMMIT, 'commands': [], 'artifacts': [], 'status': 'started'}

    def call(argv, timeout=100):
        started = time.monotonic()
        try:
            p = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            report['commands'].append({'argv': [str(v).replace(str(root), '$TOOL_DIR') for v in argv],
                                       'exit_code': None, 'timeout': True})
            raise RuntimeError('bounded upstream operation timed out') from e
        report['commands'].append({'argv': [str(v).replace(str(root), '$TOOL_DIR') for v in argv],
                                   'exit_code': p.returncode, 'seconds': round(time.monotonic()-started, 3),
                                   'stdout': p.stdout.replace(str(root), '$TOOL_DIR'),
                                   'stderr': p.stderr.replace(str(root), '$TOOL_DIR')})
        if p.returncode: raise RuntimeError('upstream download/verification command failed')
        return p.stdout

    def download(url, name, expected=None):
        dest=root/name
        call(['curl','--fail','--location','--silent','--show-error','--connect-timeout','15','--max-time','90','--output',str(dest),url])
        raw=dest.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
        if expected is not None and digest != expected: raise ValueError('upstream digest mismatch')
        report['artifacts'].append({'name':name,'url':url,'bytes':len(raw),'sha256':digest,'expected_digest_verified':expected is not None})
        return raw

    try:
        for name,digest in ASSETS.items():
            download(f'https://github.com/restic/restic/releases/download/v{VERSION}/{name}',name,digest)
        download('https://restic.net/gpg-key-alex.asc','signing-key.asc')
        download(f'https://raw.githubusercontent.com/restic/restic/{COMMIT}/LICENSE','LICENSE',LICENSE_SHA)
        shown=call(['gpg','--batch','--homedir',str(root/'gpg'),'--with-colons','--show-keys',str(root/'signing-key.asc')])
        fingerprints=[line.split(':')[9] for line in shown.splitlines() if line.startswith('fpr:')]
        if FINGERPRINT not in fingerprints: raise ValueError('official signing-key fingerprint differs')
        call(['gpg','--batch','--homedir',str(root/'gpg'),'--dearmor','--output',str(root/'keyring.gpg'),str(root/'signing-key.asc')])
        verified=call(['gpgv','--homedir',str(root/'gpg'),'--keyring',str(root/'keyring.gpg'),'--status-fd','1',str(root/'SHA256SUMS.asc'),str(root/'SHA256SUMS')])
        if not any('VALIDSIG' in line and FINGERPRINT in line for line in verified.splitlines()):
            raise ValueError('signed checksum did not verify against the pinned primary key')
        archive='restic_0.19.1_linux_amd64.bz2'
        sums={line.split()[1].lstrip('*'):line.split()[0] for line in (root/'SHA256SUMS').read_text().splitlines()}
        if sums[archive] != ASSETS[archive]: raise ValueError('signed checksum and release metadata disagree')
        raw=bz2.decompress((root/archive).read_bytes()); binary=root/'restic'; binary.write_bytes(raw); binary.chmod(0o755)
        report['binary']={'name':'restic','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        report['native_version']=call([str(binary),'version']).strip()
        if not report['native_version'].startswith('restic '+VERSION+' '): raise ValueError('native version differs')
        report['status']='verified-project-local-installation'
    except Exception as e:
        report['status']='failed'; report['error_type']=type(e).__name__
        raise
    finally:
        (root/'installation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'version':report['native_version'],'binary_sha256':report['binary']['sha256']}))

if __name__ == '__main__': main()
