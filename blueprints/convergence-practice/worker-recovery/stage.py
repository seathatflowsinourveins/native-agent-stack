"""Owned local writing effects; native worker is the only effect writer."""
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time

EXPECTED = b'{"ids":["a","b"],"total":12}\n'
ORDER = ['checkpoint', 'cancel-wait', 'crash-wait', 'finalize']


def durable(path, data):
    with path.open('xb') as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())


def actions(root):
    path = Path(root) / 'actions.jsonl'
    return [json.loads(x)['action'] for x in path.read_text().splitlines()] if path.exists() else []


def execute(root, action):
    root = Path(root)
    before = actions(root)
    if action not in ORDER or before != ORDER[:ORDER.index(action)]:
        raise ValueError('effect_order_violation')
    if action == 'checkpoint':
        records = json.loads((root / 'input.json').read_text())['records']
        payload = (json.dumps({'ids':sorted(x['id'] for x in records), 'total':sum(x['value'] for x in records)}, separators=(',', ':'))+'\n').encode()
        if payload != EXPECTED:
            raise ValueError('input_oracle_mismatch')
        durable(root / 'checkpoint.json', payload)
    elif action == 'finalize':
        if not (root / 'resume-authorized.json').is_file():
            raise ValueError('supervisor_authorization_missing')
        if (root / 'checkpoint.json').read_bytes() != EXPECTED:
            raise ValueError('checkpoint_changed')
        durable(root / 'final.json', (json.dumps({'checkpoint_sha256':hashlib.sha256(EXPECTED).hexdigest(), 'execution_count':1, 'status':'complete'},sort_keys=True)+'\n').encode())
    with (root / 'actions.jsonl').open('a') as out:
        out.write(json.dumps({'action':action})+'\n'); out.flush(); os.fsync(out.fileno())
    if action in ('cancel-wait', 'crash-wait'):
        stat = Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
        durable(root / (action+'.json'), (json.dumps({'pid':os.getpid(),'start_ticks':stat[19]})+'\n').encode())
        def stopped(number, _frame):
            durable(root / (action+'-interrupted.json'), (json.dumps({'signal':number})+'\n').encode())
            raise SystemExit(128+number)
        signal.signal(signal.SIGINT, stopped); signal.signal(signal.SIGTERM, stopped)
        time.sleep(300)
        raise RuntimeError('wait_was_not_interrupted')
    return {'action':action, 'execution_count':actions(root).count('checkpoint')}


if __name__ == '__main__':
    print(json.dumps(execute(Path(__file__).resolve().parent, sys.argv[1])))
