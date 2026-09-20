#!/usr/bin/env python3
"""Build the qualified minimal macOS Poppler in a new explicit private prefix.

Requires Python 3.14 (stdlib Zstandard), Apple developer tools and exact recorded
bundled dylibs. No global installation, model downloads, account changes or PATH
writes. This recipe was reconstructed from the retained successful native build;
its offline checks are not a second native build qualification.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile

HERE=Path(__file__).resolve().parent


def validate_workspace(path):
    path=path.expanduser().resolve()
    repo=HERE.parents[2]
    if path.is_relative_to(repo) or path.is_relative_to(Path.home()/'Documents'):
        raise ValueError('Use a new private qualification directory outside the repository and Documents.')
    if path.exists():
        raise ValueError('Workspace must be new; previous failures and builds must be retained.')
    return path


def fetch(pin, destination):
    request=urllib.request.Request(pin['url'],headers={'User-Agent':'native-agent-stack-document-qualification/1'})
    with urllib.request.urlopen(request,timeout=60) as response:
        data=response.read(pin['bytes']+1)
    if len(data)!=pin['bytes'] or hashlib.sha256(data).hexdigest()!=pin['sha256']:
        raise ValueError('Pinned package size/hash mismatch; nothing was extracted.')
    destination.write_bytes(data)
    return data


def build(work, bundle, jobs=4):
    if platform.system()!='Darwin' or platform.machine()!='arm64':
        raise ValueError('This recipe is qualified for macOS arm64 only.')
    from compression import zstd
    pins=json.loads((HERE/'build-pins.json').read_text())
    work=validate_workspace(work)
    # Verify the exact approved local library bytes before network/build work.
    for item in pins['reused_dylibs']:
        if hashlib.sha256((bundle/'lib'/item['name']).read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError('Bundled dependency mismatch; qualify this host before substituting libraries.')
    work.mkdir(parents=True)
    prefix=work/'prefix';(prefix/'lib').mkdir(parents=True);(prefix/'bin').mkdir()
    for item in pins['reused_dylibs']:
        shutil.copy2(bundle/'lib'/item['name'],prefix/'lib'/item['name'])
    for key, filename in [('poppler','poppler.tar.xz'),('cmake','cmake.tar.gz')]:
        fetch(pins[key],work/filename)
        with tarfile.open(work/filename) as archive:archive.extractall(work,filter='data')
    fetch(pins['freetype_headers'],work/'freetype.conda')
    with zipfile.ZipFile(work/'freetype.conda') as archive:
        name=next(n for n in archive.namelist() if n.startswith('pkg-') and n.endswith('.tar.zst'))
        with tarfile.open(fileobj=io.BytesIO(zstd.decompress(archive.read(name)))) as files:
            files.extractall(work/'headers',members=[m for m in files if m.name.startswith('include/')],filter='data')
    fetch(pins['pkgconf'],work/'pkgconf.whl')
    with zipfile.ZipFile(work/'pkgconf.whl') as archive:
        (work/'pkgconf').write_bytes(archive.read('pkgconf/.bin/pkgconf'))
    (work/'pkgconf').chmod(0o755)
    cmake=work/'cmake-4.4.3-macos-universal/CMake.app/Contents/bin/cmake'
    source=work/'poppler-26.09.0'
    command=[str(cmake),'-S',str(source),'-B',str(work/'build'),'-G','Unix Makefiles','-DPKG_CONFIG_EXECUTABLE='+str(work/'pkgconf'),'-DFREETYPE_INCLUDE_DIRS='+str(work/'headers/include/freetype2'),'-DFREETYPE_LIBRARY_RELEASE='+str(prefix/'lib/libfreetype.6.dylib'),'-DCMAKE_INSTALL_PREFIX='+str(prefix)]+['-D'+v for v in pins['build_flags']]
    status={'kind':'private_bootstrap','status':'started','commands_completed':[]}
    try:
        for label,args,timeout in [('configure',command,120),('build',[str(cmake),'--build',str(work/'build'),'--target','pdftotext','pdfinfo','--parallel',str(jobs)],300)]:
            with (work/(label+'.log')).open('w') as log:
                result=subprocess.run(args,cwd=work,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
            status['commands_completed'].append({'stage':label,'exit_code':result.returncode})
            if result.returncode:raise RuntimeError(f'{label} failed; private log retained')
        for name in ('pdftotext','pdfinfo'):shutil.copy2(work/'build/utils'/name,prefix/'bin'/name)
        # Source notices stay with the private build. This repository ships no binary.
        shutil.copy2(source/'COPYING',prefix/'COPYING.poppler')
        shutil.copytree(HERE,work/'fixture',ignore=shutil.ignore_patterns('accepted','__pycache__'))
        result=subprocess.run([str(prefix/'bin/pdftotext'),'-v'],cwd=work,capture_output=True,text=True,timeout=10)
        status.update(status='built_not_yet_qualified',version=(result.stderr+result.stdout).splitlines()[0])
    except Exception as error:
        status.update(status='failed',error_type=type(error).__name__)
        raise
    finally:
        (work/'bootstrap-status.json').write_text(json.dumps(status,indent=2)+'\n')
    return status


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',required=True,type=Path)
    p.add_argument('--bundle',required=True,type=Path,help='Existing exact Poppler dependency prefix with lib/. Read-only source.')
    p.add_argument('--jobs',type=int,choices=range(1,9),default=4)
    args=p.parse_args();print(json.dumps(build(args.workspace,args.bundle.resolve(),args.jobs),indent=2))
