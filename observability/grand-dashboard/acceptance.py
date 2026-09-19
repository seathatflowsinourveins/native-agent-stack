#!/usr/bin/env python3
"""Native Loki queries and isolated synthetic generation deletion/readdition check."""
import argparse
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request
import uuid
from progress import payload
from render import dashboard, latest


def query(expression):
    url='http://127.0.0.1:13100/loki/api/v1/query?'+urllib.parse.urlencode({'query':expression})
    with urllib.request.urlopen(url,timeout=10) as response:
        value=json.load(response)
    if value['status']!='success':raise ValueError('native query failed')
    return value['data']['result']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result={'scope':'local native Loki; synthetic generation fixture in unique separate service stream','queries':[],'fixture':[]}
    for panel in dashboard()['panels']:
        if panel['type'] in ['stat','table']:
            expression=panel['targets'][0]['expr'].replace('$__range','6h')
            values=query(expression)
            result['queries'].append({'panel_id':panel['id'],'expression':expression,'series':len(values),'status':'success'})
    service='progress-acceptance-'+uuid.uuid4().hex
    for phase,state in [('initial','first'),('removed',None),('readded','changed')]:
        rows=[dict(record_kind='summary',entity_id='snapshot',state='recorded')]
        if state:rows.append(dict(record_kind='lane',entity_id='fixture',state=state))
        now=time.time_ns();body=payload(rows,now)
        for stream in body['streams']:stream['stream']['service_name']=service
        request=urllib.request.Request('http://127.0.0.1:13100/loki/api/v1/push',json.dumps(body).encode(),{'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=10) as response:
            if response.status!=204:raise ValueError('fixture push failed')
        values=query(latest('lane').replace('agent-stack-progress',service))
        states=[x['metric']['state'] for x in values]
        if states!=([state] if state else []):raise ValueError('generation replacement failed')
        result['fixture'].append({'phase':phase,'states':states,'passed':True})
    result['completed_at_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({'native_queries':len(result['queries']),'generation_checks':len(result['fixture']),'status':'passed'}))


if __name__=='__main__':main()
