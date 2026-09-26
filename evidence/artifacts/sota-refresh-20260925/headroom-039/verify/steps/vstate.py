"""Verifier's read-only state check for one workspace: ledger vs savings JSON, telemetry, CCR store.
Usage: python3 -B vstate.py WS OUTDIR"""
import json
import os
import sqlite3
import stat
import sys

ws, outdir = sys.argv[1], sys.argv[2]
res = {}
sp = os.path.join(outdir, 'savings.json')
if os.path.exists(sp):
    s = json.load(open(sp))
    lt = s['lifetime']
    ev = [json.loads(line) for line in open(os.path.join(ws, 'savings_events.jsonl')) if line.strip()]
    res['savings'] = {
        'schema_version': s['schema_version'],
        'lifetime': {k: lt.get(k) for k in ('calls', 'tokens_before', 'tokens_saved', 'basis', 'cost_effective_usd', 'new_input_tokens')},
        'ledger_lines': len(ev),
        'ledger_v': sorted({e.get('v') for e in ev}),
        'ledger_saved': [e.get('saved') for e in ev],
        'ledger_keys': sorted(set().union(*[set(e) for e in ev])) if ev else [],
        'check_saved_sum': lt['tokens_saved'] == sum(e['saved'] for e in ev),
        'check_calls_eq_lines': lt['calls'] == len(ev),
        'check_ts_and_saved_every_line': all('ts' in e and 'saved' in e for e in ev),
        'tokens_saved_is_int': isinstance(lt['tokens_saved'], int),
        'path_is_str': isinstance(s.get('path'), str),
    }
tp = os.path.join(outdir, 'telemetry.json')
if os.path.exists(tp):
    t = json.load(open(tp))
    res['telemetry'] = {k: t.get(k) for k in ('beacon_enabled', 'schema_version', 'install_id')}
db = os.path.join(ws, 'ccr_store.db')
res['ws_files'] = sorted(os.listdir(ws))
if os.path.exists(db):
    res['db_mode'] = oct(stat.S_IMODE(os.stat(db).st_mode))
    c = sqlite3.connect('file:' + db + '?mode=ro&immutable=1', uri=True)
    res['indexes'] = sorted(r[0] for r in c.execute("select name from sqlite_master where type='index' and tbl_name='ccr_entries'"))
    res['columns'] = [r[1] for r in c.execute('pragma table_info(ccr_entries)')]
    res['rows'] = c.execute('select count(*) from ccr_entries').fetchone()[0]
    res['hashes'] = sorted(r[0] for r in c.execute('select hash from ccr_entries'))
    c.close()
res['has_install_id'] = os.path.exists(os.path.join(ws, 'config', 'install_id'))
res['has_update_check'] = os.path.exists(os.path.join(ws, 'update_check.json'))
print(json.dumps(res, indent=1, sort_keys=True))
