#!/usr/bin/env python3
"""Render a Grafana dashboard using the already provisioned native datasources."""
import argparse
import json
from pathlib import Path


def latest(kind, field='observed_unix'):
    selector = '{service_name="agent-stack-progress",record_kind="' + kind + '"}'
    # Preserve current labels by choosing the newest observation, not a lexical state.
    marker = '{service_name="agent-stack-progress",record_kind="summary"} | json | entity_id="snapshot" | unwrap observed_unix | __error__="" [24h]'
    return 'last_over_time(' + selector + ' | json | unwrap ' + field + ' | __error__="" [24h]) == on() group_left() max(last_over_time(' + marker + '))'


def dashboard():
    panels = []
    def panel(pid, title, typ, x, y, w, h, expr=None, source='ecosystem-loki', **extra):
        value = dict(id=pid, title=title, type=typ, gridPos=dict(x=x,y=y,w=w,h=h), options={})
        if expr:
            value.update(datasource={'uid':source},targets=[{'refId':'A','expr':expr,'queryType':'instant' if typ in ('stat','table') else 'range'}])
        value.update(extra)
        panels.append(value)
        return value
    panel(1, 'Research control room', 'text', 0,0,24,5,
          options={'mode':'markdown','content':'# US equities · research control room\nHistorical simulation and broker-specific paper acceptance are tracked below. Live trading has no authority.\n\n**Observed:** service health, exported usage and bounded native workflow history. **Recorded:** lanes, decisions, gates and worker checkpoints, refreshed from public files. Emission age does not prove source freshness or an active worker. Unknown usage is not zero; counters are not savings.\n\n[Native telemetry](/d/ecosystem-native) · [Workflow evidence](https://github.com/seathatflowsinourveins/native-agent-stack/tree/main/adoption/paired) · [Architecture](https://github.com/seathatflowsinourveins/native-agent-stack/tree/main/blueprints/us-equities/convergence-program)'})
    panel(2,'Last progress emission', 'stat',0,5,8,4,
          '1000 * max(last_over_time({service_name="agent-stack-progress",record_kind="summary"} | json | entity_id="snapshot" | unwrap observed_unix | __error__="" [24h]))',
          description='Relative age of the last emitted snapshot. Checkpoint UTC in each table records source age separately. More than 12 minutes suggests an emitter/backend failure.',
          fieldConfig={'defaults':{'unit':'dateTimeFromNow','noValue':'No observations','color':{'mode':'fixed','fixedColor':'blue'}},'overrides':[]})
    base=json.loads((Path(__file__).parents[1]/'backends/templates/ecosystem-dashboard.json.example').read_text())
    for old,new,x,title in [(20,3,8,'SDK reported tokens / selected range'),(24,4,16,'SDK receipts without usage')]:
        item=next(p for p in base['panels'] if p['id']==old)
        item.update(id=new,title=title,gridPos={'x':x,'y':5,'w':8,'h':4}); panels.append(item)
    for pid,kind,title,y,h in [(5,'lane','Lane readiness · recorded',9,7),(6,'gate','Acceptance gates · recorded',26,10),(7,'worker','Worker checkpoints · recorded',36,7),(8,'wave','Research waves · recorded',43,7),(9,'decision','Repository decisions · recorded',50,14),(13,'experiment','Historical stress results · initial equity USD 100000',16,10)]:
        panel(pid,title,'table',0,y,24,h,latest(kind),
              description='Recorded metadata. Historical stress results use hourly SPY data and fixed parameters; no strategy profitability or broker execution is established. Exact values and assumptions remain in linked receipts.' if kind=='experiment' else 'Recorded coordinator checkpoint; consult evidence for native scope and source dates.',
              transformations=[{'id':'labelsToFields','options':{'mode':'columns'}},
                {'id':'organize','options':{'excludeByName':{'Time':True,'Value':True,'Value #A':True,'record_kind':True,'record_kind_extracted':True,'detected_level':True,'service_name':True,'number':True,'entity_id':True},'indexByName':{'title':0,'equity_usd':1,'drawdown_pct':2,'fees_usd':3,'margin_call_count':4,'fill_count':5,'state':6,'source_updated_at':7,'evidence_ref':8},'renameByName':{'title':'Item','state':'Decision / state','source_updated_at':'Checkpoint UTC','evidence_ref':'Evidence path','equity_usd':'Final equity USD','drawdown_pct':'Observed drawdown %','fees_usd':'Fees USD','margin_call_count':'Margin calls','fill_count':'Fills'}}}],
              options={'showHeader':True,'cellHeight':'sm','footer':{'show':False}},
              fieldConfig={'defaults':{'custom':{'align':'auto','cellOptions':{'type':'auto'},'wrapText':True}},'overrides':[{'matcher':{'id':'byName','options':'Evidence path'},'properties':[{'id':'links','value':[{'title':'Open evidence','url':'https://github.com/seathatflowsinourveins/native-agent-stack/blob/main/${__value.raw}','targetBlank':True}]}]}]})
    panel(10,'Live service scrape health','timeseries',0,64,12,8,'up',source='ecosystem-prometheus')
    panel(11,'Live host memory usage','timeseries',12,64,12,8,'ecosystem_system_memory_usage_bytes',source='ecosystem-prometheus')
    panel(12,'Progress history · recorded checkpoints','logs',0,72,24,9,'{service_name="agent-stack-progress",record_kind=~"wave|lane|worker"}', options={'showTime':True,'sortOrder':'Descending','wrapLogMessage':True})
    panel(14,'Native agent activity · sanitized telemetry','logs',0,81,24,9,'{service_name=~"Codex Desktop|codex-app-server|claude-code|codex-sdk-receipt"}',options={'showTime':True,'sortOrder':'Descending','wrapLogMessage':True})
    panel(15,'Native workflow history · research pair','table',0,9,24,9,latest('workflow'),
          description='Read-only local Dagu history: up to 10 research-pair runs within 30 days. Native times and statuses describe stored runs, not a process heartbeat or new model acceptance. Counts cover only this returned sample. Missing configuration or failed observation is unknown; an empty successful query reports zero. Entry numbers are display positions, not run identifiers.',
          transformations=[{'id':'labelsToFields','options':{'mode':'columns'}},
            {'id':'organize','options':{'excludeByName':{'Time':True,'Value':True,'Value #A':True,'record_kind':True,'record_kind_extracted':True,'detected_level':True,'service_name':True,'entity_id':True,'source_updated_at':True},
              'indexByName':{'title':0,'state':1,'started_at':2,'finished_at':3,'duration_seconds':4,'history_count':5,'succeeded_count':6,'failed_count':7,'running_count':8,'evidence_ref':20},
              'renameByName':{'title':'Workflow / sample','state':'Native state / observation','started_at':'Native started UTC','finished_at':'Native finished UTC','duration_seconds':'Elapsed seconds','history_count':'Sample runs','succeeded_count':'Succeeded','failed_count':'Failed','running_count':'Running','evidence_ref':'Evidence path'}}}],
          options={'showHeader':True,'cellHeight':'sm','footer':{'show':False}},
          fieldConfig={'defaults':{'noValue':'—','custom':{'align':'auto','cellOptions':{'type':'auto'},'wrapText':True}},
            'overrides':[{'matcher':{'id':'byName','options':'Evidence path'},'properties':[{'id':'links','value':[{'title':'Open workflow evidence','url':'https://github.com/seathatflowsinourveins/native-agent-stack/blob/main/${__value.raw}','targetBlank':True}]}]}]})
    panels[0]['gridPos']['h']=7
    for item in panels[1:]:
        if item['id'] != 15 and item['gridPos']['y'] >= 9:item['gridPos']['y']+=9
        item['gridPos']['y']+=2
    return dict(uid='research-grand',title='Research grand dashboard',schemaVersion=39,version=5,editable=False,
                timezone='browser',refresh='30s',time={'from':'now-6h','to':'now'},tags=['ecosystem','research'],panels=panels)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(dashboard(),indent=2)+'\n')
    print('Rendered research-grand dashboard.')
