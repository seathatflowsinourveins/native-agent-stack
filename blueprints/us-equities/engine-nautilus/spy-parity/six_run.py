"""Prospective six-case native driver. No engine is constructed before review.

Native MARGIN/StandardMarginModel/RiskEngine handles admission, fills, fees,
positions, account states and distributions. LEAN maintenance/partial calls
and the adaptive latch are separately labelled fixture policy.
"""
from datetime import datetime, timezone
from decimal import Decimal
import importlib.metadata
import json
from pathlib import Path
import sys
import time

SOURCE = Path(__file__).resolve().parent


def engine_end(rows):
    if not rows:
        raise ValueError('six_empty_bar_window')
    return int(rows[-1]['ts_event_ns']) + 2


def case_configuration(mapping, case_id, base):
    spec = mapping['cases'][case_id]
    case = {**base.CASE, **spec}
    instrument = {**base.INSTRUMENT, 'price_precision':6, 'price_increment':'0.000001',
                  'margin_init':'0.5', 'margin_maint':'0.5'}
    return case, instrument


def finalize_run(failure, captures, persist_snapshot, dispose, finish_log):
    """Capture incomplete native evidence before teardown without masking failure.

    Each callable is independent. The failed snapshot is evidence of an incomplete
    run, never an acceptance receipt. This helper needs no native dependencies.
    """
    snapshot = None
    primary = failure
    def note(stage, error):
        if primary is not None:
            try: primary.add_note(stage + ' also failed: ' + repr(error))
            except BaseException: pass  # A secondary diagnostic cannot mask primary.
    def persist(stage):
        try: persist_snapshot(snapshot)
        except BaseException as error:
            snapshot['snapshot_write_errors'].append({'stage':stage, 'error':repr(error)})
            note('failed_native_state_snapshot_' + stage, error)
    if failure is not None:
        snapshot = {'schema_version':'spy-six-case-failed-native-state/1',
                    'status':'FAILED', 'qualification':'NOT_ACCEPTED',
                    'failure':{'type':type(failure).__name__, 'message':str(failure)},
                    'capture_phase':'before_dispose', 'captures':{},
                    'snapshot_write_errors':[], 'finalization':{}}
        for name, capture in captures.items():
            try:
                value = capture()
                # Freeze borrowed histories before dispose/reset can clear them.
                value = json.loads(json.dumps(value, allow_nan=False))
                snapshot['captures'][name] = {'status':'unavailable' if value is None else 'captured',
                                             'value':value}
            except BaseException as error:
                snapshot['captures'][name] = {'status':'error', 'error':repr(error)}
                note('failed_native_state_capture_' + name, error)
        persist('before_dispose')
    for name, action in (('dispose', dispose), ('log_capture', finish_log)):
        try:
            action()
            if snapshot is not None: snapshot['finalization'][name] = {'status':'complete'}
        except BaseException as error:
            if snapshot is not None:
                snapshot['finalization'][name] = {'status':'error', 'error':repr(error)}
            if primary is None: primary = error
            else: note(name, error)
    if snapshot is not None: persist('after_finalization')
    if failure is None and primary is not None: raise primary
    return snapshot


def failed_native_captures(engine, strategy, observer, module, fill_model, equity, venue, usd, out, base):
    """Independent raw-state readers; no admission, account or cache mutation."""
    account = lambda: engine.cache.account_for_venue(venue)
    def csv_report(name, report):
        path = out / ('failed-' + name + '.csv')
        report().to_csv(path)
        return {'path':path.name, 'sha256':base.digest(path)}
    reports = {'account':lambda:engine.generate_account_report(venue=venue),
               'positions':lambda:engine.generate_positions_report(),
               'fills':lambda:engine.generate_order_fills_report()}
    def margin_money(reader):
        value = reader()
        return None if value is None else str(value)
    captures = {
        'native_orders':lambda:[o.to_dict() for o in engine.cache.orders()],
        'native_order_events':lambda:[e.to_dict() for o in engine.cache.orders() for e in o.events()],
        'native_positions_open':lambda:[p.to_dict() for p in engine.cache.positions_open()],
        'native_commissions_by_order':lambda:{str(o.client_order_id):{
            str(k):str(v) for k,v in o.commissions().items()} for o in engine.cache.orders()},
        'native_account_event_rows':lambda:base.account_events(account(), usd),
        'native_account_balance_total':lambda:str(account().balance_total(usd)),
        'native_account_balance_free':lambda:str(account().balance_free(usd)),
        'native_account_initial_margin':lambda:margin_money(lambda:account().initial_margin(equity.id)),
        'native_account_maintenance_margin':lambda:margin_money(lambda:account().maintenance_margin(equity.id)),
        'native_account_type':lambda:account().account_type.name,
        'native_account_default_leverage':lambda:str(account().default_leverage),
        'native_instrument':lambda:equity.to_dict(),
        'economic_ledger':lambda:{'cash':str(strategy.cash),'quantity':str(strategy.position)},
        'settlement_handshake':lambda:{'pending':strategy.phase.pending,'last':strategy.phase.last},
        'observer':lambda:{'pending':observer.pending,'errors':observer.errors,
                          'acknowledgements':observer.acknowledgements},
        'distribution_module':lambda:{'emissions':module.emissions,'acknowledgements':module.acknowledgements,
                                      'errors':module.errors,'pending':[e['ex_date'] for e in module.pending]},
        'fill_model_calls':lambda:fill_model.calls,
        'engine_iterations':lambda:engine.get_result().iterations}
    for name in ('errors','bars_seen','intents','fills','marks','native_callback_events','order_events',
                 'margin_calls','margin_warnings','latch_events','phase_alerts_registered','phase_alerts_fired'):
        captures['strategy_' + name] = lambda name=name:getattr(strategy,name)
    for name, report in reports.items():
        captures['native_' + name + '_report'] = lambda report=report:json.loads(report().to_json(orient='records'))
        captures['native_' + name + '_csv'] = lambda name=name,report=report:csv_report(name, report)
    return captures


def run_once(rows, events, out, label, mapping, case_id, base):
    # This entry is reached only from the prospective checks in main().
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogColor, LogLevel, logger_flush, logger_log
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, RiskEngineConfig
    from nautilus_trader.accounting import StandardMarginModel
    from nautilus_trader.model import (AccountType, ClientOrderId, Currency, Equity, InstrumentId,
                                      Money, OmsType, Price, Quantity, Symbol, Venue)
    case, instrument = case_configuration(mapping, case_id, base)
    policy = base._load('spy_six_margin_policy', SOURCE/'margin_policy.py')
    adapter = base._load('spy_six_margin_strategy', SOURCE/'margin_strategy.py')
    costs = base._load('spy_six_native_costs', SOURCE/'cost_models.py')
    fill_model, fee_model = costs.build_models(case, instrument)
    usd, venue = Currency.from_str('USD'), Venue('SIM')
    equity = Equity(InstrumentId.from_str('SPY.SIM'), Symbol('SPY'), usd, 6,
                    Price.from_str('0.000001'), 0, 0, lot_size=Quantity.from_int(1),
                    margin_init=Decimal('0.5'), margin_maint=Decimal('0.5'))
    module = base.DISTRIBUTION.build_module(events, 'SPY.SIM', 'USD')
    strategy_class = adapter.build_strategy(base.FIXTURE, policy, module, equity.id, venue, usd,
                 instrument['bar_type'], rows, case, [e['ex_instant_ns'] for e in events])
    strategy = strategy_class()
    observer = adapter.build_observer(lambda:strategy)
    bars = base.CONVERT.to_bars(rows, instrument['bar_type'], 6, 0)
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    log = out/'engine.log'
    failure = None
    with base.CapturedOutput(log):
        engine = BacktestEngine(BacktestEngineConfig(
            logging=LoggerConfig(stdout_level=LogLevel.INFO, is_colored=False),
            risk_engine=RiskEngineConfig(bypass=False, max_notional_per_order={})))
        try:
            engine.add_venue(venue, OmsType.NETTING, AccountType.MARGIN,
                  [Money(Decimal(case['initial_cash_usd']), usd)], base_currency=usd,
                  default_leverage=Decimal('2'), margin_model=StandardMarginModel(),
                  fill_model=fill_model, fee_model=fee_model, latency_model=None,
                  modules=[module, observer], reject_stop_orders=True, support_contingent_orders=True,
                  use_random_ids=False, use_reduce_only=True, use_message_queue=True,
                  frozen_account=False, bar_execution=True, bar_adaptive_high_low_ordering=False,
                  liquidation_enabled=False)
            engine.add_instrument(equity)
            engine.add_data(bars)
            engine.add_strategy(strategy)
            # Include the final +1ns completion timer explicitly, before end().
            engine.run(end=engine_end(rows))
            result = engine.get_result()
            strategy.phase.finish()
            if observer.pending is not None or observer.errors:
                raise ValueError('six_observer_not_complete:' + ';'.join(observer.errors))
            base.FIXTURE.check_run_integrity(strategy.errors, strategy.bars_seen, len(rows), result.iterations)
            if len(strategy.marks) != len(rows) or len(strategy.phase_alerts_fired) != len(rows):
                raise ValueError('six_marks_or_final_observation_missing')
            account = engine.cache.account_for_venue(venue)
            orders = engine.cache.orders()
            native_orders = [order.to_dict() for order in orders]
            native_events = [event.to_dict() for order in orders for event in order.events()]
            known = set(strategy.submitted)
            if set(str(order.client_order_id) for order in orders) != known:
                raise ValueError('six_unexpected_native_order_or_automatic_liquidation')
            base.FIXTURE.check_final_state(None, len(engine.cache.orders_open()),
                                           len(engine.cache.positions_open()), strategy.position)
            reports = {'account':engine.generate_account_report(venue=venue),
                       'positions':engine.generate_positions_report(),
                       'fills':engine.generate_order_fills_report()}
            raw = {}
            for name, report in reports.items():
                report.to_csv(out/(name+'.csv'))
                raw[name] = json.loads(report.to_json(orient='records'))
            base.save(out/'reports.private.json', raw)
            oco_views = {str(order.client_order_id):base.FIXTURE.engine_order_view(order.to_dict())
                         for order in orders if str(order.client_order_id) in strategy.accepted_orders}
            ledger = base.FIXTURE.posted_distribution_ledger(module.emissions, module.acknowledgements)
            record = {'case':case_id, 'label':label, 'bars_seen':strategy.bars_seen,
                      'engine_iterations':result.iterations, 'engine_run_end_ns':engine_end(rows),
                      'configuration':{'case':case, 'instrument':instrument, 'native':mapping['native']},
                      'intents':strategy.intents, 'fills':strategy.fills,
                      'marks':strategy.marks, 'margin_calls':strategy.margin_calls,
                      'margin_warnings':strategy.margin_warnings, 'latch_events':strategy.latch_events,
                      'oco_pairs':base.FIXTURE.attach_engine_views(strategy.oco_pairs, strategy.accepted_orders, oco_views),
                      'order_events':strategy.order_events, 'native_orders':native_orders,
                      'native_order_events':native_events, 'native_callback_events':strategy.native_callback_events,
                      'native_account_event_rows':base.account_events(account, usd),
                      'native_account_type':account.account_type.name,
                      'native_default_leverage':str(account.default_leverage),
                      'native_instrument':equity.to_dict(),
                      'native_commissions_by_order':{str(o.client_order_id):{
                          str(k):str(v) for k,v in o.commissions().items()} for o in orders},
                      'native_final_balance_total':str(account.balance_total(usd)),
                      'native_final_balance_free':str(account.balance_free(usd)),
                      'native_final_maintenance_diagnostic':str(account.maintenance_margin(equity.id)),
                      'final_quantity':str(strategy.position), 'cash':str(strategy.cash),
                      'fees_usd':str(sum((Decimal(f['fee']) for f in strategy.fills), Decimal(0))),
                      'distribution_ledger':ledger,
                      'dividend_cash_usd':str(sum((Decimal(d['amount']) for d in ledger), Decimal(0))),
                      'fill_model_calls':fill_model.calls, 'errors':strategy.errors,
                      'observer_errors':observer.errors, 'observer_acknowledgements':observer.acknowledgements,
                      'alerts_registered':strategy.alerts_registered, 'alerts_fired':strategy.alerts_fired,
                      'phase_alerts_registered':strategy.phase_alerts_registered,
                      'phase_alerts_fired':strategy.phase_alerts_fired,
                      'distribution_module_record':{'emissions':module.emissions, 'acknowledgements':module.acknowledgements,
                         'errors':module.errors, 'pending':[e['ex_date'] for e in module.pending]},
                      'native_fills':raw['fills'], 'raw_report_sha256':{
                          name:base.digest(out/(name+'.csv')) for name in reports},
                      'raw_reports_json_sha256':base.digest(out/'reports.private.json')}
        except BaseException as error:
            failure = error
            raise
        finally:
            def finish_log():
                logger_flush()
                sentinel = 'spy-six-case capture end '+label
                logger_log(LogLevel.INFO, LogColor.NORMAL, 'SpySixCaseRunner', sentinel)
                logger_flush()
                deadline = time.monotonic()+30
                while sentinel not in log.read_text(errors='replace'):
                    if time.monotonic()>deadline: raise ValueError('six_native_log_capture_incomplete')
                    time.sleep(0.01)
            finalize_run(failure, failed_native_captures(engine, strategy, observer, module,
                         fill_model, equity, venue, usd, out, base),
                         lambda snapshot:base.save(out/'failed-native-state.private.json', snapshot),
                         lambda:engine.dispose(), finish_log)
    record['engine_log_scan'] = base.scan_engine_log(log.read_text(errors='replace'))
    record['engine_log_sha256'] = base.digest(log)
    base.save(out/'native-export.json', record)
    return record


def main(args, base):
    binding = base._load('spy_six_bindings', SOURCE/'six_bindings.py')
    started = datetime.now(timezone.utc).isoformat()
    if args.review_record is None or not args.harness_commit:
        raise ValueError('six_prospective_review_and_commit_required_before_native_import')
    mapping, hashes = binding.load_mapping(args.mapping_manifest)
    review, review_binding = binding.read_review(args.review_record)
    binding.require_review(review, hashes, mapping, args.case, args.harness_commit, started, sys.argv)
    if importlib.metadata.version('nautilus_trader') != mapping['runtime']['version']:
        raise ValueError('six_native_version_mismatch')
    if sys.version.split()[0] != mapping['runtime']['python_version']:
        raise ValueError('six_official_python_version_mismatch')
    extension = base.check_engine_binary({'engine':mapping['runtime']})
    isolation = base.isolation_evidence(args.lean_data)
    comparator = base._load('spy_six_comparator', SOURCE/'compare_six.py')
    comparator.require_isolation(isolation, base)
    if base.digest(args.tolerances) != binding.TOLERANCES_SHA:
        raise ValueError('six_frozen_tolerances_changed')
    old = base.load_manifest(SOURCE/'mapping-manifest-v2.json')
    effective = base.effective_manifest(old, base.load_manifest(SOURCE/'mapping-manifest.json'))
    conversion = base.CONVERT.convert(args.lean_data, 'SPY', '2019-12-02', '2020-04-30',
                                      base.known_short_sessions(effective))
    if len(conversion['rows']) != 725 or conversion['input_hashes'] != mapping['frozen']['input_sha256']:
        raise ValueError('six_frozen_inputs_or_725_rows_changed')
    events = base.distribution_events(args.lean_data)
    args.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    base.save(args.out/'converted-rows.private.json', conversion['rows'])
    frozen = {'argv':list(sys.argv), 'source_sha256':hashes, 'mapping_manifest':{
                  'path':binding.MANIFEST, 'sha256':hashes[binding.MANIFEST]},
              'review_record':review_binding, 'input_sha256':conversion['input_hashes'],
              'runtime':mapping['runtime'], 'case':args.case, 'isolation':isolation,
              'frozen':mapping['frozen']}
    base.save(args.out/'frozen-arguments.private.json', frozen)
    runs = [run_once(conversion['rows'], events, args.out/label, label, mapping, args.case, base)
            for label in ('run-1','run-2')]
    receipt = {'schema_version':'spy-six-case-native/1',
               'id':'spy-parity-'+args.case.replace('_','-')+'-six-cases-20261003',
               'case':args.case, 'evidence_class':'HIST', 'started_utc':started,
               'observed_utc':datetime.now(timezone.utc).isoformat(), 'harness_commit':args.harness_commit,
               'frozen_arguments':frozen, 'frozen_arguments_sha256':base.digest(args.out/'frozen-arguments.private.json'),
               'engine_extension_sha256':extension, 'review_record':review_binding, 'runs':runs,
               'raw_exports':[{'path':label+'/native-export.json',
                    'sha256':base.digest(args.out/label/'native-export.json')} for label in ('run-1','run-2')]}
    base.save(args.out/'receipt.json', receipt)
    print(json.dumps({'case':args.case, 'native_receipt_written':True,
                      'qualification':'pending_independent_strict_comparison'}))
