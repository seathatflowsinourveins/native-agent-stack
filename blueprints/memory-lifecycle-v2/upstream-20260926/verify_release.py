#!/usr/bin/env python3
"""Check that each installed ai-memory binary this blueprint runs is the one in the
official GitHub release asset for its tag.

For every tag: fetch the release record from the GitHub REST API, download
`ai-memory-linux-x86_64.tar.gz` and its `.sha256` sidecar, require the local
download digest to equal both the sidecar value and the API asset `digest`,
extract the tarball in memory and compare the `ai-memory` member's sha256 with
the installed binary's. Standard library only. Writes JSON to stdout; paths
under the home directory are printed as `~`.

    python3 verify_release.py --work DIR v2.3.2=PATH v2.4.0=PATH ...
"""
import argparse
import datetime
import hashlib
import io
import json
from pathlib import Path
import tarfile
import urllib.request

REPO = 'akitaonrails/ai-memory'
ASSET = 'ai-memory-linux-x86_64.tar.gz'


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'memory-lifecycle-v2-verify'})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def tilde(path):
    home = str(Path.home())
    text = str(path)
    return '~' + text[len(home):] if text.startswith(home + '/') else text


def verify(tag, installed, work):
    release = json.loads(fetch(f'https://api.github.com/repos/{REPO}/releases/tags/{tag}'))
    assets = {a['name']: a for a in release['assets']}
    asset, sidecar_asset = assets[ASSET], assets[ASSET + '.sha256']
    tarball = fetch(asset['browser_download_url'])
    sidecar = fetch(sidecar_asset['browser_download_url']).decode()
    (work / f'{tag}-{ASSET}').write_bytes(tarball)
    (work / f'{tag}-{ASSET}.sha256').write_text(sidecar)
    download_digest = sha256(tarball)
    sidecar_digest = sidecar.split()[0].lower()
    release_record_digest = (asset.get('digest') or '').removeprefix('sha256:')
    members = {}
    with tarfile.open(fileobj=io.BytesIO(tarball), mode='r:gz') as archive:
        for member in archive.getmembers():
            if member.isfile() and Path(member.name).name == 'ai-memory':
                members[member.name] = sha256(archive.extractfile(member).read())
    installed_digest = sha256(Path(installed).read_bytes())
    return {
        'tag': tag,
        'release_published_at': release['published_at'],
        'release_draft': release['draft'], 'release_prerelease': release['prerelease'],
        'release_immutable': release.get('immutable'),
        'asset': asset['browser_download_url'], 'asset_bytes': len(tarball),
        'asset_sha256_download': download_digest,
        'asset_sha256_sidecar': sidecar_digest,
        'asset_sha256_github_release_record': release_record_digest,
        'asset_digests_agree': download_digest == sidecar_digest == release_record_digest,
        'tarball_ai_memory_members_sha256': members,
        'installed_binary': tilde(installed),
        'installed_binary_sha256': installed_digest,
        'installed_equals_release_binary': installed_digest in members.values(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('pairs', nargs='+', help='TAG=INSTALLED_BINARY')
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    results = [verify(*pair.split('=', 1), args.work) for pair in args.pairs]
    print(json.dumps({'started_utc': started,
                      'finished_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      'repository': f'https://github.com/{REPO}', 'results': results,
                      'all_verified': all(r['asset_digests_agree'] and r['installed_equals_release_binary']
                                          for r in results)}, indent=2))
    raise SystemExit(0 if all(r['asset_digests_agree'] and r['installed_equals_release_binary']
                              for r in results) else 1)


if __name__ == '__main__':
    main()
