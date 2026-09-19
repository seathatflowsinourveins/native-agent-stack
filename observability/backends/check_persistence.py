#!/usr/bin/env python3
"""Bounded local persistence acceptance. Restarts only the five new backend units.
Writes a labeled synthetic log/notification and a temporary silence; never fails
an application service, submits a model call, or sends an external notification.
"""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import time
import urllib.parse
import urllib.request


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--grafana-env',type=Path,required=True)
    p.add_argument('--evidence-dir',type=Path,required=True)
    a=p.parse_args(); a.evidence_dir.mkdir(parents=True,exist_ok=True)
    if any(a.evidence_dir.glob('persistence-*.json')):
        raise SystemExit('Use a fresh evidence directory; prior persistence attempts are preserved.')
    with (a.evidence_dir/'persistence-attempt.json').open('x') as attempt:
        json.dump({'status':'started','scope':'private backend persistence acceptance'},attempt)
    env=dict(line.split('=',1) for line in a.grafana_env.read_text().splitlines() if '=' in line)
    auth=base64.b64encode((env['GF_SECURITY_ADMIN_USER']+':'+env['GF_SECURITY_ADMIN_PASSWORD']).encode()).decode()
    def call(url,body=None,method=None,grafana=False):
        headers={}
        if body is not None: body=json.dumps(body).encode(); headers['Content-Type']='application/json'
        if grafana: headers['Authorization']='Basic '+auth
        req=urllib.request.Request(url,data=body,headers=headers,method=method)
        with urllib.request.urlopen(req,timeout=10) as r:
            raw=r.read(); return {'http_status':r.status,'body':json.loads(raw) if raw else None}
    now=datetime.now(timezone.utc); stamp=str(time.time_ns())
    fixture='ecosystem-backend-persistence-'+str(int(time.time()))
    silence=call('http://127.0.0.1:19093/api/v2/silences',{
      'matchers':[{'name':'alertname','value':'EcosystemPersistenceFixture','isRegex':False,'isEqual':True}],
      'startsAt':now.isoformat(),'endsAt':(now+timedelta(minutes=10)).isoformat(),
      'createdBy':'local-backend-acceptance','comment':'Synthetic backend persistence acceptance; no application alert muted.'})['body']['silenceID']
    call('http://127.0.0.1:13100/loki/api/v1/push',{'streams':[{'stream':{'service_name':'ecosystem-persistence-fixture','scope':'synthetic-acceptance'},'values':[[stamp,fixture,{'synthetic':'true'}]]}]})
    note=call('http://127.0.0.1:18080',{'topic':'ecosystem-persistence-fixture','message':fixture,'title':'Synthetic local persistence check'})['body']
    fixed_time=time.time()
    prom_url='http://127.0.0.1:19090/api/v1/query?'+urllib.parse.urlencode({'query':'up{job="prometheus"}','time':str(fixed_time)})
    loki_url='http://127.0.0.1:13100/loki/api/v1/query_range?'+urllib.parse.urlencode({'query':'{service_name="ecosystem-persistence-fixture"}','start':str(int(stamp)-1000000000),'end':str(int(stamp)+1000000000)})
    ntfy_url='http://127.0.0.1:18080/ecosystem-persistence-fixture/json?poll=1&since=all'
    # Poll returns newline-delimited JSON; only one fixture on initial run.
    def notifications():
        with urllib.request.urlopen(ntfy_url,timeout=5) as r: return [json.loads(x) for x in r.read().decode().splitlines() if x]
    def snapshot():
        return {'prometheus':call(prom_url),'loki':call(loki_url),'ntfy':notifications(),
          'alertmanager':call('http://127.0.0.1:19093/api/v2/silence/'+silence),
          'grafana_dashboard':call('http://127.0.0.1:13000/api/dashboards/uid/ecosystem-native',grafana=True),
          'grafana_datasources':call('http://127.0.0.1:13000/api/datasources',grafana=True)}
    before=snapshot(); (a.evidence_dir/'persistence-before.json').write_text(json.dumps(before,indent=2)+'\n')
    units=['ecosystem-'+n+'.service' for n in ['prometheus','loki','grafana','alertmanager','ntfy']]
    restart=subprocess.run(['systemctl','--user','restart',*units],text=True,capture_output=True)
    (a.evidence_dir/'persistence-restart.json').write_text(json.dumps({'command':['systemctl','--user','restart',*units],'exit_code':restart.returncode,'stdout':restart.stdout,'stderr':restart.stderr},indent=2)+'\n')
    if restart.returncode: raise SystemExit('Backend restart failed')
    ready=['http://127.0.0.1:'+port+path for port,path in [('19090','/-/ready'),('13100','/ready'),('13000','/api/health'),('19093','/-/ready'),('18080','/v1/health')]]
    for attempt in range(45):
        try:
            for url in ready:
                with urllib.request.urlopen(url,timeout=2) as r: assert r.status==200
            break
        except Exception:
            if attempt==44: raise
            time.sleep(1)
    after=snapshot(); (a.evidence_dir/'persistence-after.json').write_text(json.dumps(after,indent=2)+'\n')
    checks={
      'prometheus_historical_sample':bool(before['prometheus']['body']['data']['result']) and before['prometheus']==after['prometheus'],
      'loki_log':fixture in json.dumps(after['loki']['body']['data']['result']),
      'ntfy_message':any(x.get('id')==note['id'] and x.get('message')==fixture for x in after['ntfy']),
      'alertmanager_silence':after['alertmanager']['body']['id']==silence,
      'grafana_dashboard':after['grafana_dashboard']['body']['dashboard']['uid']=='ecosystem-native',
      'grafana_datasources':{x['uid'] for x in after['grafana_datasources']['body']}=={'ecosystem-prometheus','ecosystem-loki','ecosystem-alertmanager'},
    }
    call('http://127.0.0.1:19093/api/v2/silence/'+silence,method='DELETE')
    result={'kind':'native_backend_persistence','synthetic_fixture':True,'restart_exit_code':restart.returncode,'checks':checks,'passed':all(checks.values()),'scope':'Only five observability backends restarted. Historical Prometheus sample and synthetic Loki/ntfy data persisted; temporary test silence expired afterward. Retention settings are configured, not aged out during this bounded check.'}
    (a.evidence_dir/'persistence-result.json').write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2))
    if not result['passed']: raise SystemExit(1)


if __name__=='__main__': main()
