#!/usr/bin/env python3
"""Download pinned official archives; verify publisher SHA256; extract isolated prefixes.
No services, profile changes, dependency installers, or client settings are touched.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tools-root', type=Path, required=True)
    p.add_argument('--evidence-dir', type=Path, required=True)
    a = p.parse_args()
    a.tools_root.mkdir(parents=True, exist_ok=True)
    a.evidence_dir.mkdir(parents=True, exist_ok=True)
    pins = json.loads(Path(__file__).with_name('pins.json').read_text())
    results = []
    for item in pins['components']:
        target = a.tools_root / f"ecosystem-{item['id']}-{item['version']}"
        archive = a.evidence_dir / item['url'].rsplit('/', 1)[1]
        if not archive.exists():
            part = archive.with_suffix(archive.suffix + '.part')
            urllib.request.urlretrieve(item['url'], part)
            part.rename(archive)
        with archive.open('rb') as f:
            actual = hashlib.file_digest(f, 'sha256').hexdigest()
        if actual != item['sha256']:
            raise SystemExit(f"Checksum mismatch: {archive.name}")
        proof = a.evidence_dir / f"{item['id']}-published-checksums.txt"
        if not proof.exists():
            urllib.request.urlretrieve(item['checksum_source'], proof)
        if item['sha256'] not in proof.read_text():
            raise SystemExit(f"Publisher checksum not found for {item['id']}")
        if target.exists():
            raise SystemExit(f"Refusing to overwrite existing prefix: {target}")
        with tempfile.TemporaryDirectory(prefix='ecosystem-unpack-', dir=a.tools_root) as tmp:
            unpack = Path(tmp)
            if archive.name.endswith('.zip'):
                with zipfile.ZipFile(archive) as z:
                    for name in z.namelist():
                        member = Path(name)
                        if member.is_absolute() or '..' in member.parts:
                            raise ValueError('Unsafe archive member')
                    z.extractall(unpack)
                (unpack/'loki-linux-amd64').chmod(0o755)
            else:
                with tarfile.open(archive) as t:
                    t.extractall(unpack, filter='data')
            if item['strip_root']:
                children = list(unpack.iterdir())
                if len(children) != 1 or not children[0].is_dir():
                    raise ValueError(f"Unexpected archive layout: {item['id']}")
                children[0].rename(target)
            else:
                # Prefix remains isolated; temporary path is otherwise empty after move.
                target.mkdir()
                for child in unpack.iterdir():
                    shutil.move(str(child), target / child.name)
        if 'license_file' in item:
            license_pin = item['license_file']
            license_bytes = urllib.request.urlopen(license_pin['url']).read()
            if hashlib.sha256(license_bytes).hexdigest() != license_pin['sha256']:
                raise SystemExit('License checksum mismatch')
            (target / 'LICENSE').write_bytes(license_bytes)
        results.append({**item, 'verified_sha256': actual, 'prefix': str(target)})
        (a.evidence_dir/'installation.json').write_text(json.dumps(results, indent=2)+'\n')
        print(f"Verified and installed {item['id']} {item['version']}", flush=True)


if __name__ == '__main__':
    main()
