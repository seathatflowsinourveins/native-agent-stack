"""Validate retained command metadata; this does not rerun a component."""
import argparse,json,pathlib
p=argparse.ArgumentParser();p.add_argument('component');a=p.parse_args();root=pathlib.Path(__file__).parent
rows={r['id']:r for r in json.loads((root/'execution-ledger.json').read_text())['commands']}
checks=json.loads((root/'retained-checks.json').read_text())[a.component]
for item in checks['checks']:
 r=rows[item['id']]
 if r['actual_exit']!=item['expected_exit']:raise SystemExit('Retained command exit differs from declared expectation: '+item['id'])
 if not all(len(s['sha256'])==64 for s in r['streams'].values()):raise SystemExit('Missing raw stream digest')
print(json.dumps({'component':a.component,'metadata_checked':len(checks['checks']),'scope':checks['scope'],'native_execution_repeated':False}))
