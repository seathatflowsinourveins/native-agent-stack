#!/usr/bin/env python3
"""Install only pinned official archives into an exclusively created prefix."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import tarfile
import urllib.request

HERE = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check_digest(data, expected):
    if digest(data) != expected:
        raise ValueError("SHA256 mismatch")


def checked_members(archive):
    members = archive.getmembers()
    for item in members:
        path = PurePosixPath(item.name)
        if path.is_absolute() or '..' in path.parts or not (item.isdir() or item.isfile()):
            raise ValueError("Unsafe archive member")
    return members


def check_publisher_checksum(text, filename, expected):
    matches = [line.split()[0] for line in text.splitlines()
               if len(line.split()) == 2 and line.split()[1].lstrip('*') == filename]
    if matches != [expected]:
        raise ValueError("Publisher checksum missing, duplicated or mismatched")


def download(item, path):
    with urllib.request.urlopen(item['url'], timeout=60) as response:
        data = response.read()
    check_digest(data, item['sha256'])
    path.write_bytes(data)
    return data


def install(prefix):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise ValueError('This qualification is pinned to Linux x86_64')
    prefix = prefix.absolute()
    prefix.mkdir(mode=0o700)  # Refuse every existing destination, including symlinks.
    downloads = prefix / 'downloads'
    downloads.mkdir()
    pins = json.loads((HERE / 'pins.json').read_text())
    (prefix / 'pins.json').write_text(json.dumps(pins, indent=2) + '\n')
    receipt = {'schema_version': 1, 'platform': platform.platform(),
               'python': platform.python_version(), 'components': [],
               'scope': 'New private versioned prefix only; no PATH, shell, Git or service changes'}
    for tool in pins['components']:
        archive_path = downloads / tool['archive']['name']
        archive_bytes = download(tool['archive'], archive_path)
        checksum_bytes = download(tool['checksums'], downloads / tool['checksums']['name'])
        check_publisher_checksum(checksum_bytes.decode(), archive_path.name, digest(archive_bytes))
        license_bytes = download({'url': tool['license_url'], 'sha256': tool['license_sha256']},
                                 downloads / (tool['name'] + '-LICENSE'))
        destination = prefix / 'tools' / tool['name'] / tool['version']
        destination.mkdir(parents=True)
        with tarfile.open(archive_path) as archive:
            members = checked_members(archive)
            archive.extractall(destination, members=members, filter='data')
        binaries = list(destination.rglob(tool['executable']))
        licenses = list(destination.rglob('LICENSE'))
        if len(binaries) != 1 or len(licenses) != 1 or licenses[0].read_bytes() != license_bytes:
            raise ValueError('Expected exactly one executable and matching upstream license')
        binary = binaries[0]
        binary.chmod(0o755)
        receipt['components'].append({
            'name': tool['name'], 'version': tool['version'],
            'source_commit': tool['source_commit'], 'license': tool['license'],
            'archive_sha256': digest(archive_bytes),
            'publisher_checksum_verified': True, 'github_asset_digest_verified': True,
            'license_matches_pinned_source': True,
            'binary': str(binary.relative_to(prefix)), 'binary_sha256': digest(binary.read_bytes()),
            'archive_members': [m.name for m in members],
        })
        (prefix / 'installation.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(install(args.prefix), indent=2))
