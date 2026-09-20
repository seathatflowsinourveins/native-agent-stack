"""Deterministic namespace/mount/ownership preflight; no backup password or restic run."""
import argparse
import errno
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from run import sandbox_command, save
from verify import HERE, digest

PROGRAM = '''#!/usr/bin/python3
import errno
from pathlib import Path
assert Path('/secret/password').read_text() == 'deterministic-nonsecret'
for path in [Path('/secret/password'), Path('/repository/config')]:
    try:
        path.write_text('unexpected')
    except OSError as error:
        assert error.errno == errno.EROFS
    else:
        raise AssertionError('required read-only mount was writable')
p = Path('/out/synthetic-file'); p.write_bytes(b'ok'); p.chmod(0o600)
assert not Path('/home').exists()
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix='native-offhost-contract-', dir='/tmp'))
    report = {'scope':'Deterministic namespace preflight only; not native snapshot restoration.',
              'source_sha256':digest(Path(__file__)), 'status':'started'}
    try:
        repo=root/'repository';repo.mkdir();(repo/'config').write_text('synthetic')
        key=root/'password';key.write_text('deterministic-nonsecret');key.chmod(0o600)
        output=root/'output';output.mkdir(mode=0o755)
        probe=root/'probe.py';shutil.copyfile(HERE/'probe.py',probe);probe.chmod(0o644)
        fake=root/'restic';fake.write_text(PROGRAM);fake.chmod(0o755)
        command=sandbox_command(fake,repo,key,output,probe,[])
        result=subprocess.run(command,capture_output=True,text=True,timeout=15)
        report.update(command=[v.replace(str(root),'$OWNED_CONTRACT') for v in command],
                      exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr)
        if result.returncode: raise ValueError('namespace/secret-mode/read-only contract failed')
        namespace=json.loads((output/'namespace.json').read_text())
        if (namespace['network_namespace']==os.readlink('/proc/self/ns/net')
                or namespace['mount_namespace']==os.readlink('/proc/self/ns/mnt')
                or namespace['uid']!=1000
                or set(namespace['environment_keys'])!={'HOME','LANG','PATH','PWD','PYTHONDONTWRITEBYTECODE'}
                or (output/'synthetic-file').stat().st_uid!=0):
            raise ValueError('namespace/environment/ownership contract differs')
        report.update(status='passed-deterministic-contract',namespace=namespace,
                      distinct_network_and_mount_namespaces=True,read_only_input_mounts=True,
                      mode0600_key_readable_only_in_mapped_owned_scope=True,outside_output_uid=0)
    except Exception as error:
        report.update(status='failed',failure={'type':type(error).__name__,'message':str(error).replace(str(root),'$OWNED_CONTRACT')})
    finally:
        shutil.rmtree(root)
        report['owned_contract_removed']=not root.exists()
        save(args.output,report)
    print(json.dumps({'status':report['status'],'owned_contract_removed':report['owned_contract_removed']}))
    return report['status'] != 'passed-deterministic-contract'


if __name__ == '__main__': raise SystemExit(main())
