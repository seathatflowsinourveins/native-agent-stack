"""Read-only parent observations; no checkpoint or final effect writes."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent


def alive(marker):
    try:
        fields=Path('/proc/'+str(marker['pid'])+'/stat').read_text().rsplit(')',1)[1].split()
        return fields[0]!='Z' and fields[19]==marker['start_ticks']
    except (FileNotFoundError, ProcessLookupError):
        return False


def main(action):
    deadline=time.monotonic()+120
    if action=='await-cancel-wait':
        while not (ROOT/'cancel-wait.json').exists():
            if time.monotonic()>deadline: raise TimeoutError('cancel_wait_not_ready')
            time.sleep(.1)
        assert alive(json.loads((ROOT/'cancel-wait.json').read_text()))
    elif action=='verify-cancelled':
        marker=json.loads((ROOT/'cancel-wait.json').read_text())
        while alive(marker):
            if time.monotonic()>deadline: raise TimeoutError('cancelled_wait_still_alive')
            time.sleep(.1)
        assert [json.loads(x)['action'] for x in (ROOT/'actions.jsonl').read_text().splitlines()]==['checkpoint','cancel-wait']
    elif action=='await-crash-wait':
        while not (ROOT/'crash-wait.json').exists():
            if time.monotonic()>deadline: raise TimeoutError('crash_wait_not_ready')
            time.sleep(.1)
        assert alive(json.loads((ROOT/'crash-wait.json').read_text()))
    elif action=='supervisor-hold':
        time.sleep(300)
        raise TimeoutError('supervisor_did_not_interrupt')
    else:
        raise ValueError('unknown_control')
    print(json.dumps({'action':action,'passed':True}))


if __name__=='__main__': main(sys.argv[1])
