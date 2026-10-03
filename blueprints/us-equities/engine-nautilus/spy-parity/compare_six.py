"""Independent six-case comparison against unchanged LEAN receipt and audit.

No oracle enters the execution strategy. All 725 original marks are supplied by
the hash-pinned original audit, not inferred from a receipt's extrema/counts.
"""
from decimal import Decimal
import json
from pathlib import Path
import re
import sys

SOURCE = Path(__file__).resolve().parent


def number(value):
    value = Decimal(str(value).split()[0])
    if not value.is_finite(): raise ValueError('six_nonfinite_economic_value')
    return value


def require_isolation(observed, base):
    if ([list(i) for i in observed.get('network_interfaces', [])] != [[1,'lo']]
        or set(observed.get('environment_names', []))-set(base.ISOLATED_ENVIRONMENT_VALUES)
        or observed.get('environment_values') != base.ISOLATED_ENVIRONMENT_VALUES
        or observed.get('read_only') != {'harness_source':True, 'data_root':True, 'python_prefix':True}
        or type(observed.get('python_flags_isolated')) is not int
        or observed.get('python_flags_isolated') != 1):
        raise ValueError('six_isolation_not_qualified')
    ns = observed.get('namespaces') or {}
    uid = ns.get('uid_map')
    if (ns.get('pid1_comm') != 'bwrap' or not isinstance(uid, str) or not uid.split()
        or uid.split() == ['0','0','4294967295']):
        raise ValueError('six_namespace_not_qualified')


def economic_projection(run):
    # Artifact hashes/labels identify raw captures and are independently checked.
    # Every economic/native event, mark, diagnostic and phase timestamp remains.
    artifact = {'label','raw_report_sha256','raw_reports_json_sha256','engine_log_sha256','engine_log_scan'}
    return {k:v for k,v in run.items() if k not in artifact}


def compare_case(run, oracle, audit, rows, limits):
    checks = []
    def exact(field, wanted, actual):
        checks.append({'field':field, 'expected':wanted, 'observed':actual, 'pass':wanted==actual})
    def money(field, wanted, actual, key='cash_usd_abs'):
        try: ok = abs(number(wanted)-number(actual)) <= number(limits[key])
        except (ValueError, TypeError, KeyError): ok = False
        checks.append({'field':field, 'expected':str(wanted), 'observed':str(actual), 'pass':ok})
    def records(field, actual, expected, fields):
        exact(field+'.count', len(expected), len(actual))
        for i,(a,e) in enumerate(zip(actual,expected)):
            for name,key in fields:
                if key: money(field+'.'+str(i)+'.'+name, e.get(name),a.get(name),key)
                else: exact(field+'.'+str(i)+'.'+name,e.get(name),a.get(name))
    exact('case',oracle['id'],run.get('case'))
    exact('all_725_rows',725,len(rows))
    exact('all_725_bars',725,run.get('bars_seen'))
    exact('all_725_native_iterations',725,run.get('engine_iterations'))
    exact('native_account_type','MARGIN',run.get('native_account_type'))
    money('native_default_leverage',2,run.get('native_default_leverage'),'fill_quantity_abs')
    native_instrument = run.get('native_instrument') or {}
    for rate in ('margin_init','margin_maint'):
        money('native_instrument.'+rate,'0.5',native_instrument.get(rate),'fill_quantity_abs')
    exact('native_end_includes_final_observation',rows[-1]['ts_event_ns']+2,run.get('engine_run_end_ns'))
    for name in ('errors','observer_errors'):
        exact(name,[],run.get(name))
    exact('native_engine_error_lines',0,(run.get('engine_log_scan') or {}).get('error_lines'))
    module = run.get('distribution_module_record') or {}
    exact('distribution_errors',[],module.get('errors'))
    exact('distribution_pending',[],module.get('pending'))
    exact('flat_final_quantity',0,number(run.get('final_quantity','NaN')))
    intents = run.get('intents',[])
    records('intents',intents,oracle['intents'], [('utc_seconds','event_seconds_abs'),
            ('quantity','fill_quantity_abs'),('reason',None)])
    fills = run.get('fills',[])
    expected_fills = [{'utc_seconds':number(f['time']), 'quantity':number(f['fillQuantity']),
                       'price':number(f['fillPrice']), 'fee':number(f['orderFeeAmount'])}
                      for f in oracle['fills']]
    records('fills',fills,expected_fills,[('utc_seconds','event_seconds_abs'),('quantity','fill_quantity_abs'),
                                       ('price','fill_price_usd_abs'),('fee','fees_usd_abs')])
    money('total_fees',oracle['fees_usd'],run.get('fees_usd'),'fees_usd_abs')
    money('total_distributions',oracle['dividends_usd'],run.get('dividend_cash_usd'),'dividend_usd_abs')
    money('economic_end_cash',oracle['end_cash_usd'],run.get('cash'),'end_cash_usd_abs')
    money('native_end_balance',oracle['end_cash_usd'],run.get('native_final_balance_total'),'end_cash_usd_abs')
    expected_marks = [e for e in audit if e.get('kind')=='mark']
    marks = run.get('marks',[])
    exact('oracle_all_725_marks',725,len(expected_marks))
    exact('all_725_marks',725,len(marks))
    exact('mark_native_economic_instants',[r['ts_event_ns'] for r in rows],
          [m.get('economic_ts_event_ns') for m in marks])
    exact('observation_exact_plus_one',[r['ts_event_ns']+1 for r in rows],
          [m.get('observation_ts_event_ns') for m in marks])
    exact('phase_registration_count',725,len(run.get('phase_alerts_registered',[])))
    exact('phase_firing_instants',[r['ts_event_ns']+1 for r in rows],
          [e.get('ts_event_ns') for e in run.get('phase_alerts_fired',[])])
    for i,(m,e) in enumerate(zip(marks,expected_marks)):
        for name in ('utc_seconds','quantity','price'):
            key = {'utc_seconds':'event_seconds_abs','quantity':'fill_quantity_abs','price':'fill_price_usd_abs'}[name]
            money('mark.'+str(i)+'.'+name,e[name],m.get(name),key)
        for name in ('equity','cash','margin_used','margin_remaining','peak'):
            money('mark.'+str(i)+'.'+name,e[name],m.get(name))
        for name in ('gross','drawdown'):
            money('mark.'+str(i)+'.'+name,e[name],m.get(name),'fill_quantity_abs')
        exact('mark.'+str(i)+'.policy_label','frozen_LEAN_fixture_policy',m.get('maintenance_authority'))
        exact('mark.'+str(i)+'.native_diagnostic_retained',True,
              all(k in m for k in ('native_balance_total','native_balance_free','native_initial_margin',
                                    'native_maintenance_diagnostic')))
        # Recompute full-precision cash and exposure from actual native fills and
        # acknowledged distribution amounts before this economic bar timestamp.
        ts = number(m['utc_seconds'])
        before = [f for f in fills if number(f['utc_seconds'])<=ts]
        ledger = [d for d in run.get('distribution_ledger',[]) if number(d['utc_seconds'])<=ts]
        q = sum((number(f['quantity']) for f in before),Decimal(0))
        cash = Decimal('100000')+sum((-number(f['quantity'])*number(f['price'])-number(f['fee'])
                                    for f in before),Decimal(0))+sum((number(d['amount']) for d in ledger),Decimal(0))
        money('mark.'+str(i)+'.reconciled_quantity',q,m.get('quantity'),'fill_quantity_abs')
        money('mark.'+str(i)+'.reconciled_cash',cash,m.get('cash'))
        money('mark.'+str(i)+'.reconciled_equity',cash+q*number(m['price']),m.get('equity'))
    records('margin_calls',run.get('margin_calls',[]),oracle['margin_calls'],
            [('utc_seconds','event_seconds_abs'),('count',None),('equity','cash_usd_abs'),
             ('margin_remaining','cash_usd_abs')])
    expected_warnings = [e for e in audit if e.get('kind')=='margin_warning']
    records('margin_warnings',run.get('margin_warnings',[]),expected_warnings,
            [('utc_seconds','event_seconds_abs'),('equity','cash_usd_abs'),('margin_remaining','cash_usd_abs')])
    records('latch_events',run.get('latch_events',[]),oracle['reductions'],
            [('utc_seconds','event_seconds_abs'),('equity','cash_usd_abs'),('peak','cash_usd_abs'),
             ('drawdown','fill_quantity_abs')])
    expected_dividends = [e for e in audit if e.get('kind')=='dividend']
    records('distributions',run.get('distribution_ledger',[]),expected_dividends,
            [('utc_seconds','event_seconds_abs'),('quantity','fill_quantity_abs'),
             ('per_share','dividend_usd_abs'),('amount','dividend_usd_abs')])
    callbacks, archived = run.get('native_callback_events'),run.get('native_order_events')
    exact('native_callbacks_present',True,isinstance(callbacks,list) and bool(callbacks))
    callbacks = callbacks if isinstance(callbacks,list) else []
    archived = archived if isinstance(archived,list) else []
    def group(events):
        found = {}
        for e in events: found.setdefault(e.get('client_order_id'),[]).append(e)
        return found
    exact('native_callback_stream_matches_cached_events',group(archived),group(callbacks))
    orders = run.get('native_orders',[])
    native_filled = [e for e in archived if e.get('type')=='OrderFilled']
    exact('native_fill_events_cover_every_fill',len(fills),len(native_filled))
    cached_orders = {o.get('client_order_id'):o for o in orders}
    for fill in fills:
        native = [e for e in native_filled if e.get('client_order_id')==fill['client_order_id']]
        exact('one_cached_native_fill.'+fill['client_order_id'],1,len(native))
        if len(native)==1:
            event = native[0]
            sign = 1 if cached_orders.get(fill['client_order_id'],{}).get('side')=='BUY' else -1
            money('cached_native_fill_quantity',abs(fill['quantity']),event.get('last_qty'),'fill_quantity_abs')
            money('cached_native_fill_price',fill['price'],event.get('last_px'),'fill_price_usd_abs')
            money('cached_native_fill_commission',fill['fee'],event.get('commission'),'fees_usd_abs')
            exact('cached_native_fill_side',fill['quantity']>0,sign>0)
            exact('cached_native_fill_timestamp',fill['ts_event_ns'],event.get('ts_event'))
    known = {leg['client_order_id'] for pair in run.get('oco_pairs',[]) for leg in pair['legs']}
    known.update('SPY-POLICY-'+str(c['order_ref']) for c in run.get('margin_calls',[]))
    if run['case']=='over_limit': known.update('SPY-POLICY-'+str(i['order_ref']) for i in intents)
    exact('no_unexpected_native_order',sorted(known),sorted(o.get('client_order_id') for o in orders))
    by_ref = {i['order_ref']:i for i in intents}
    for f in fills:
        intent = by_ref.get(f.get('order_ref'))
        if f.get('leg')=='MARKET':
            call = next((c for c in run.get('margin_calls',[]) if c['order_ref']==f['order_ref']),None)
            exact('market_call_at_original_bar',True,call is not None and f['ts_event_ns']==call['economic_ts_event_ns'])
            exact('market_reduction_quantity',call['quantity'] if call else None,f['quantity'])
        else:
            exact('discretionary_fill_strictly_after_actual_decision',True,
                  intent is not None and f['ts_event_ns']>intent['decision_clock_ns'])
        model = [c for c in run.get('fill_model_calls',[]) if c.get('client_order_id')==f['client_order_id']]
        exact('one_native_fill_model_call.'+f['client_order_id'],1,len(model))
        if len(model)==1:
            row = next((r for r in rows if r['ts_event_ns']==f['ts_event_ns']),None)
            reference = row['c'] if f.get('leg')=='MARKET' else row['o'] if row else None
            money('native_model_reference',reference,model[0]['reference_price'],'fill_price_usd_abs')
            money('native_model_fill',f['price'],model[0]['fill_price'],'fill_price_usd_abs')
            money('native_model_quantity',abs(number(f['quantity'])),model[0]['quantity'],'fill_quantity_abs')
    if run['case']=='over_limit':
        exact('one_native_market_denial',['MARKET'],[o.get('type') for o in orders])
        exact('native_denied_status',['DENIED'],[o.get('status') for o in orders])
        exact('native_denied_side',['BUY'],[o.get('side') for o in orders])
        exact('no_native_refusal_fills',[],run.get('native_fills'))
        exact('no_native_refusal_commissions',True,
              not any(run.get('native_commissions_by_order',{}).values()))
        if len(orders)==1 and len(intents)==1:
            money('native_denied_order_quantity',intents[0]['quantity'],orders[0].get('quantity'),'fill_quantity_abs')
            money('native_denied_filled_quantity',0,orders[0].get('filled_qty'),'fill_quantity_abs')
        exact('native_refusal_event_sequence',['OrderInitialized','OrderDenied'],[e.get('type') for e in callbacks])
        exact('zero_fill_model_calls',[],run.get('fill_model_calls'))
        denied = [e for e in callbacks if e.get('type')=='OrderDenied']
        exact('native_initial_margin_reason',True,len(denied)==1 and bool(re.fullmatch(
            r'INITIAL_MARGIN_EXCEEDS_FREE_BALANCE: free=100000\.00 USD, margin=[0-9]+\.[0-9]{2} USD',
            str(denied[0].get('reason')))))
        if len(denied)==1 and intents:
            exact('native_denial_keeps_observation_timestamp',intents[0]['decision_clock_ns'],denied[0].get('ts_event'))
            match = re.fullmatch(r'INITIAL_MARGIN_EXCEEDS_FREE_BALANCE: free=100000\.00 USD, margin=([0-9]+\.[0-9]{2}) USD',str(denied[0].get('reason')))
            if match:
                # Currency precision is part of the native admission diagnostic,
                # not a changed economic tolerance or a synthetic Invalid label.
                price = next(r['c'] for r in rows if r['ts_event_ns']//10**9==intents[0]['utc_seconds'])
                expected = number(intents[0]['quantity'])*number(price)*Decimal('0.5')
                exact('native_initial_margin_exceeds_free',True,number(match[1])>Decimal('100000'))
                exact('native_initial_margin_matches_half_notional',True,abs(number(match[1])-expected)<=Decimal('0.005'))
    else:
        exact('no_native_denial_or_rejection',[],[e for e in callbacks if e.get('type') in ('OrderDenied','OrderRejected')])
        by_id = {o.get('client_order_id'):o for o in orders}
        for call in run.get('margin_calls',[]):
            o = by_id.get('SPY-POLICY-'+str(call['order_ref']),{})
            exact('native_market_reduce_only',('MARKET','SELL',True,'FILLED'),
                  (o.get('type'),o.get('side'),o.get('is_reduce_only'),o.get('status')))
            money('native_market_call_quantity',abs(call['quantity']),o.get('quantity'),'fill_quantity_abs')
        for pair in run.get('oco_pairs',[]):
            legs = pair.get('legs',[])
            exact('native_oco_two_legs',2,len(legs))
            if len(legs)!=2: continue
            for leg in legs:
                view = leg.get('engine_at_accept') or {}
                sibling = next(l['client_order_id'] for l in legs if l is not leg)
                exact('native_oco_links',('OCO',pair['order_list_id'],[sibling]),
                      (view.get('contingency_type'),view.get('order_list_id'),view.get('linked_order_ids')))
            final = [leg.get('engine_final') or {} for leg in legs]
            exact('native_oco_filled_and_canceled',['CANCELED','FILLED'],sorted(v.get('status','') for v in final))
    return checks


def main(args, base):
    binding = base._load('spy_six_compare_bindings',SOURCE/'six_bindings.py')
    if args.lean_data is None or args.oracle_audit is None or args.verdict is None:
        raise ValueError('six_comparison_requires_lean_data_original_audit_and_fresh_verdict')
    if args.source_dir is not None and (args.source_dir.is_symlink() or args.source_dir.resolve()!=SOURCE):
        raise ValueError('six_comparison_requires_current_nonsymlink_source')
    mapping, hashes = binding.load_mapping(args.mapping_manifest)
    receipt = json.loads(args.receipt.read_text())
    case = receipt['case']
    if case not in binding.CASES or args.case != case or receipt.get('schema_version')!='spy-six-case-native/1':
        raise ValueError('six_receipt_case_or_schema_changed')
    if receipt.get('id')!='spy-parity-'+case.replace('_','-')+'-six-cases-20261003':
        raise ValueError('six_receipt_identity_changed')
    frozen = receipt['frozen_arguments']
    frozen_path = args.receipt.parent/'frozen-arguments.private.json'
    if base.digest(frozen_path)!=receipt['frozen_arguments_sha256'] or json.loads(frozen_path.read_text())!=frozen:
        raise ValueError('six_preengine_frozen_arguments_changed')
    for key, wanted in [('source_sha256',hashes),('mapping_manifest',{'path':binding.MANIFEST,'sha256':hashes[binding.MANIFEST]}),
                        ('case',case),('runtime',mapping['runtime']),('frozen',mapping['frozen'])]:
        if frozen.get(key)!=wanted: raise ValueError('six_recorded_binding_changed:'+key)
    review_path = binding.REPO/receipt['review_record']['path']
    review, observed_review = binding.read_review(review_path)
    if observed_review!=receipt['review_record'] or frozen.get('review_record')!=observed_review:
        raise ValueError('six_prospective_review_bytes_changed')
    binding.require_review(review,hashes,mapping,case,receipt['harness_commit'],receipt['started_utc'],sys.argv,operation='compare')
    binding.require_review(review,hashes,mapping,case,receipt['harness_commit'],receipt['started_utc'],frozen['argv'])
    require_isolation(frozen['isolation'],base)
    if base.digest(args.oracle)!=binding.ORACLE_SHA or base.digest(args.plan)!=binding.PLAN_SHA or base.digest(args.tolerances)!=binding.TOLERANCES_SHA:
        raise ValueError('six_oracle_plan_or_tolerance_changed')
    oracle = next(c for c in json.loads(args.oracle.read_text())['cases'] if c['id']==case)
    if base.digest(args.oracle_audit)!=oracle['audit_sha256']:
        raise ValueError('six_original_full_lean_audit_hash_changed')
    audit = [json.loads(line) for line in args.oracle_audit.read_text().splitlines() if line.strip()]
    old = base.load_manifest(SOURCE/'mapping-manifest-v2.json')
    effective = base.effective_manifest(old,base.load_manifest(SOURCE/'mapping-manifest.json'))
    converted = base.CONVERT.convert(args.lean_data,'SPY','2019-12-02','2020-04-30',base.known_short_sessions(effective))
    if converted['input_hashes']!=mapping['frozen']['input_sha256'] or converted['input_hashes']!=frozen.get('input_sha256'):
        raise ValueError('six_inputs_changed_at_comparison')
    extension = base.check_engine_binary({'engine':mapping['runtime']})
    if receipt['engine_extension_sha256']!=extension:
        raise ValueError('six_native_extension_changed_at_comparison')
    limits = json.loads(args.tolerances.read_text())['limits']
    checks = []
    runs = receipt.get('runs',[])
    if len(runs)!=2 or len(receipt.get('raw_exports',[]))!=2:
        raise ValueError('six_exactly_two_native_runs_required')
    for i,run in enumerate(runs):
        driver = base._load('spy_six_compare_case_configuration',SOURCE/'six_run.py')
        expected_case, expected_instrument = driver.case_configuration(mapping,case,base)
        if run.get('configuration') != {'case':expected_case, 'instrument':expected_instrument,
                                       'native':mapping['native']}:
            raise ValueError('six_run_configuration_drift')
        export = receipt['raw_exports'][i]
        p = args.receipt.parent/export['path']
        if (p.is_symlink() or not p.resolve().is_relative_to(args.receipt.parent.resolve())
            or base.digest(p)!=export['sha256'] or json.loads(p.read_text())!=run
            or base.digest(p.parent/'engine.log')!=run['engine_log_sha256']
            or base.digest(p.parent/'reports.private.json')!=run['raw_reports_json_sha256']):
            raise ValueError('six_retained_native_export_or_log_changed')
        for name, sha in run['raw_report_sha256'].items():
            if name not in ('account','positions','fills') or base.digest(p.parent/(name+'.csv'))!=sha:
                raise ValueError('six_raw_native_csv_changed')
        checks.extend({'run':i+1,**c} for c in compare_case(run,oracle,audit,converted['rows'],limits))
    normalized = [base.normalize(economic_projection(r),{}) for r in runs]
    checks.append({'field':'two_native_economic_records_equal','pass':normalized[0]==normalized[1]})
    verdict = {'schema_version':'spy-six-case-verdict/1','case':case,
               'verdict':'PASS' if all(c['pass'] for c in checks) else 'FAIL',
               'pass':sum(c['pass'] for c in checks),'fail':sum(not c['pass'] for c in checks),
               'skipped':0,'checks':checks,'source_sha256':hashes,
               'scope':'frozen retained-sample fixture policy/native execution only; no paper or host promotion'}
    if args.verdict.exists(): raise ValueError('six_preserve_existing_verdict')
    base.save(args.verdict,verdict)
    print(json.dumps({k:verdict[k] for k in ('case','verdict','pass','fail','skipped')}))
    return 0 if verdict['verdict']=='PASS' else 1
