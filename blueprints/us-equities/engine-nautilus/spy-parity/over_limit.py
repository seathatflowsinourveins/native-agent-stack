"""Prospective, refusal-only native rc5 mapping for frozen SPY over_limit.

One native MARKET request reaches the real RiskEngine at the decision close.
Its original DENIED state/reason remain in the exports. No MOO fill equivalence,
maintenance valuation or liquidation equivalence is claimed by this mapping.
"""
from datetime import datetime, timezone
from decimal import Decimal
import argparse
import importlib.util
import json
from pathlib import Path
import random
import re
import sys
import time

SOURCE = Path(__file__).resolve().parent
REVIEW_SCHEMA = 'spy-over-limit-native-refusal-review/1'
MANIFEST = 'mapping-manifest-over-limit-20261002.json'
PREREGISTRATION = 'PREREGISTRATION-over-limit-20261002.md'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUN = _load('spy_over_limit_runner', SOURCE / 'run.py')
CMP = _load('spy_over_limit_comparator', SOURCE / 'compare.py')


def configuration():
    case, instrument, _ = RUN.case_settings('one_stress')
    case.pop('oco_trigger_increment')
    return {'case': {**case, 'id': 'over_limit', 'target': '4', 'reject': True, 'adaptive': False},
            'instrument': {**instrument, 'margin_init': '0.5', 'margin_maint': '0.5'},
            'venue': {**RUN.VENUE, 'account_type': 'MARGIN', 'default_leverage': '2',
                      'margin_model': 'StandardMarginModel', 'liquidation_enabled': True,
                      'fill_model': 'TwentyBasisPointFillModel',
                      'fee_model': 'FixedFeeModel(1.00 USD,charge_commission_once=true)',
                      'support_contingent_orders': False,
                      'liquidation_trigger_ratio': '1', 'liquidation_cancel_open_orders': True},
            'risk': {'bypass': False, 'max_notional_per_order': {}}}


def decision_intent(rows):
    case = configuration()['case']
    selected = RUN.FIXTURE.decision_rows(rows, [case['entry_decision_date']])
    row = selected[case['entry_decision_date']]
    index = next(i for i, item in enumerate(rows) if item is row)
    RUN.FIXTURE.check_decision_bar_is_session_final(rows, index)
    quantity = RUN.FIXTURE.target_quantity(Decimal(case['initial_cash_usd']), Decimal(case['target']),
                                         Decimal(case['sizing_buffer']), Decimal(row['c']))
    return {'utc_seconds': row['ts_event_ns'] // 10**9, 'ts_event_ns': row['ts_event_ns'],
            'quantity': quantity, 'target': case['target'], 'reason': 'entry',
            'decision_price': row['c'], 'client_order_id': 'SPY-OVER-LIMIT-1'}


def reviewed_files():
    return (*RUN.stress_reviewed_files(), 'over_limit.py', MANIFEST, PREREGISTRATION)


def require_review(review, hashes, started_utc, revision):
    if not isinstance(review, dict) or review.get('schema_version') != REVIEW_SCHEMA:
        raise ValueError('over_limit_independent_review_required_before_engine')
    if (review.get('case') != 'over_limit' or review.get('independent_review') is not True
            or review.get('unresolved_findings') != 0 or review.get('reviewed_commit') != revision
            or review.get('reviewed_local_source_sha256') != hashes):
        raise ValueError('over_limit_review_identity_or_source_mismatch')
    completed = datetime.fromisoformat(review['completed_utc'].replace('Z', '+00:00'))
    started = datetime.fromisoformat(started_utc.replace('Z', '+00:00'))
    if completed.tzinfo is None or started.tzinfo is None or completed >= started:
        raise ValueError('over_limit_review_must_precede_engine')


def isolation_checks(observed):
    namespaces = observed.get('namespaces') or {}
    uid_map = namespaces.get('uid_map')
    return {
        'loopback_only': [list(i) for i in observed.get('network_interfaces', [])] == [[1, 'lo']],
        'cleared_environment': not (set(observed.get('environment_names', [])) - CMP.ISOLATED_ENVIRONMENT),
        'documented_environment_values': observed.get('environment_values') == RUN.ISOLATED_ENVIRONMENT_VALUES,
        'read_only_source_data_runtime': observed.get('read_only') == {
            'harness_source': True, 'data_root': True, 'python_prefix': True},
        'isolated_python': type(observed.get('python_flags_isolated')) is int and observed['python_flags_isolated'] == 1,
        'user_namespace': isinstance(uid_map, str) and bool(uid_map.split())
                          and uid_map.split() != CMP.INITIAL_USER_NAMESPACE_UID_MAP,
        'pid_namespace': namespaces.get('pid1_comm') == 'bwrap',
    }


def require_isolation(observed):
    failures = [key for key, passed in isolation_checks(observed).items() if not passed]
    if failures:
        raise ValueError('over_limit_strict_fence_required:' + ','.join(failures))


def initial_margin_denial(reason):
    return isinstance(reason, str) and re.fullmatch(
        r'INITIAL_MARGIN_EXCEEDS_FREE_BALANCE: free=[0-9]+\.[0-9]{2} USD, margin=[0-9]+\.[0-9]{2} USD',
        reason) is not None


def native_instrument():
    from nautilus_trader.model import Currency, Equity, InstrumentId, Price, Quantity, Symbol
    instrument = configuration()['instrument']
    return Equity(InstrumentId.from_str(instrument['instrument_id']), Symbol(instrument['symbol']),
                  Currency.from_str('USD'), instrument['price_precision'],
                  Price.from_str(instrument['price_increment']), 0, 0,
                  lot_size=Quantity.from_int(1), margin_init=Decimal('0.5'), margin_maint=Decimal('0.5'))


def native_market_order(trader_id, strategy_id, quantity, timestamp):
    from nautilus_trader.core import UUID4
    from nautilus_trader.model import (ClientOrderId, InstrumentId, MarketOrder, OrderSide,
                                     Quantity, StrategyId, TimeInForce, TraderId)
    return MarketOrder(TraderId(str(trader_id)), StrategyId(str(strategy_id)),
                       InstrumentId.from_str('SPY.SIM'), ClientOrderId('SPY-OVER-LIMIT-1'),
                       OrderSide.BUY, Quantity.from_int(quantity), UUID4(), timestamp,
                       TimeInForce.DAY, False, False)


def _money(value):
    amount, currency = str(value).split()
    if currency != 'USD':
        raise ValueError('non_usd_native_money')
    number = Decimal(amount)
    if not number.is_finite():
        raise ValueError('non_finite_native_money')
    return number


def refusal_checks(run, rows, expected):
    """Independent economic checks over retained native records, without rewriting."""
    checks = []
    def check(field, wanted, actual):
        def serializable(value):
            if isinstance(value, Decimal):
                return str(value)
            if isinstance(value, list):
                return [serializable(item) for item in value]
            if isinstance(value, dict):
                return {key: serializable(item) for key, item in value.items()}
            return value
        checks.append({'field': field, 'expected': serializable(wanted),
                       'observed': serializable(actual), 'pass': wanted == actual})
    def decimal_value(value):
        try:
            return Decimal(str(value))
        except Exception:
            return None
    derived = decision_intent(rows)
    projection = [{k: i[k] for k in ('utc_seconds', 'quantity', 'reason')} for i in run.get('intents', [])]
    check('intents', expected['intents'], projection)
    check('derived_intent', [derived], run.get('intents'))
    orders = run.get('native_orders', [])
    check('native_order_count', 1, len(orders))
    check('native_order_status', ['DENIED'], [o.get('status') for o in orders])
    check('native_order_type', ['MARKET'], [o.get('type') for o in orders])
    check('native_order_side', ['BUY'], [o.get('side') for o in orders])
    check('native_order_quantity', [Decimal(derived['quantity'])], [decimal_value(o.get('quantity')) for o in orders])
    check('native_filled_quantity', [Decimal(0)], [decimal_value(o.get('filled_qty')) for o in orders])
    check('native_order_ids', [derived['client_order_id']], [o.get('client_order_id') for o in orders])
    events = run.get('native_order_events', [])
    check('native_event_types', ['OrderInitialized', 'OrderDenied'], [e.get('type') for e in events])
    denied = [e for e in events if e.get('type') == 'OrderDenied']
    check('native_denial_count', 1, len(denied))
    check('native_denial_timestamps', [derived['ts_event_ns']], [e.get('ts_event') for e in denied])
    check('native_denial_ids', [derived['client_order_id']], [e.get('client_order_id') for e in denied])
    check('native_initial_margin_denial', [True], [initial_margin_denial(e.get('reason')) for e in denied])
    if len(denied) == 1 and initial_margin_denial(denied[0].get('reason')):
        free, margin = re.findall(r'([0-9]+\.[0-9]{2}) USD', denied[0]['reason'])
        check('denial_free_balance', Decimal('100000'), Decimal(free))
        check('denial_margin_exceeds_free', True, Decimal(margin) > Decimal(free))
        price = Decimal(derived['decision_price'])
        # Money in the native risk check rounds to USD currency precision.
        check('denial_half_notional_within_currency_rounding', True,
              abs(Decimal(margin) - Decimal(derived['quantity']) * price * Decimal('0.5')) <= Decimal('0.005'))
    check('no_native_fills', [], run.get('native_fills'))
    check('no_native_commissions', {}, run.get('native_fee_commissions'))
    check('no_fill_model_calls', [], run.get('fill_model_calls'))
    check('no_callback_errors', [], run.get('errors'))
    check('no_native_engine_errors', [], run.get('engine_error_lines'))
    check('no_distribution_module_errors', [], run.get('distribution_module_record', {}).get('errors'))
    check('all_bars_received', len(rows), run.get('bars_seen'))
    check('all_native_iterations', len(rows), run.get('engine_iterations'))
    check('native_account_type', 'MARGIN', run.get('native_account_type'))
    check('native_default_leverage', Decimal(2), decimal_value(run.get('native_default_leverage')))
    for field in ('native_final_balance_total', 'native_final_balance_free'):
        try:
            final = _money(run[field])
        except (KeyError, ValueError):
            final = None
        check(field, Decimal('100000'), final)
    check('open_orders', 0, run.get('open_orders'))
    check('open_positions', 0, run.get('open_positions'))
    marks = run.get('native_marks', [])
    check('mark_timestamps', [r['ts_event_ns'] for r in rows], [m.get('ts_event_ns') for m in marks])
    for field, amount in [('balance_total', Decimal('100000')), ('balance_free', Decimal('100000')),
                          ('initial_margin', Decimal(0)), ('maintenance_margin', Decimal(0))]:
        try:
            actual = [_money(mark[field]) for mark in marks]
        except (KeyError, ValueError):
            actual = []
        check('native_mark_' + field, [amount] * len(rows), actual)
    check('native_mark_flat', [0] * len(rows), [m.get('position_count') for m in marks])
    # With zero native fills/commissions/positions, independently reconstructed
    # cash is the initial100000; the unchanged frozen allowance is unnecessary.
    check('frozen_end_cash', expected['end_cash_usd'], Decimal('100000'))
    check('frozen_fees', Decimal(0), expected['fees_usd'])
    check('frozen_distributions', Decimal(0), expected['dividends_usd'])
    check('frozen_final_quantity', 0, expected['final_quantity'])
    return checks


def _build_strategy(rows, instrument_id, venue, usd, alerts):
    from nautilus_trader.config import StrategyConfig
    from nautilus_trader.model import BarType
    from nautilus_trader.trading import Strategy
    intent = decision_intent(rows)
    bar_type = BarType.from_str(configuration()['instrument']['bar_type'])
    class OverLimitRefusal(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig())
            self.intents, self.native_marks, self.callback_events, self.errors = [], [], [], []
            self.alerts_registered, self.alerts_fired = [], []
            self.bars_seen = 0
        def on_start(self):
            try:
                self.subscribe_bars(bar_type)
                for instant in alerts:
                    name = 'ex_date_' + str(instant)
                    self.clock.set_time_alert_ns(name, instant, self._on_ex_date_alert, allow_past=False)
                    self.alerts_registered.append({'name': name, 'alert_time_ns': instant})
            except BaseException as error:
                self.errors.append('on_start:' + type(error).__name__ + ':' + str(error))
                raise
        def _on_ex_date_alert(self, event):
            # Native clock wakeup lets the existing venue module run at midnight;
            # the callback records its event without changing cash, orders or state.
            try:
                self.alerts_fired.append({'name': str(event.name), 'ts_event_ns': int(event.ts_event)})
            except BaseException as error:
                self.errors.append('_on_ex_date_alert:' + type(error).__name__ + ':' + str(error))
                raise
        def on_bar(self, bar):
            try:
                row = rows[self.bars_seen]
                self.bars_seen += 1
                if bar.ts_event != row['ts_event_ns']:
                    raise ValueError('over_limit_bar_timestamp_mismatch')
                account = self.cache.account_for_venue(venue)
                self.native_marks.append({
                    'ts_event_ns': bar.ts_event, 'balance_total': str(account.balance_total(usd)),
                    'balance_free': str(account.balance_free(usd)),
                    'initial_margin': str(account.total_initial_margin(usd)),
                    'maintenance_margin': str(account.total_maintenance_margin(usd)),
                    'position_count': len(self.cache.positions_open())})
                if bar.ts_event == intent['ts_event_ns']:
                    if self.intents:
                        raise ValueError('duplicate_over_limit_submission')
                    self.intents.append(dict(intent))
                    self.submit_order(native_market_order(self.trader_id, self.strategy_id, intent['quantity'],
                                                          self.clock.timestamp_ns()))
            except BaseException as error:
                self.errors.append('on_bar:' + type(error).__name__ + ':' + str(error))
                raise
        def on_order_event(self, event):
            try:
                self.callback_events.append(event.to_dict())
            except BaseException as error:
                self.errors.append('on_order_event:' + type(error).__name__ + ':' + str(error))
                raise
    return OverLimitRefusal


def _run_once(rows, events, out, preflight):
    require_review(preflight['review'], preflight['source_hashes'], preflight['started_utc'], preflight['revision'])
    require_isolation(preflight['isolation'])
    # All review/input/argument/fence checks and their frozen receipt precede
    # this first engine import/construction. Tests exercise native components only.
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogColor, LogLevel, logger_flush, logger_log
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig
    from nautilus_trader.model import AccountType, Currency, Money, OmsType, StandardMarginModel, Venue
    from nautilus_trader.risk import RiskEngineConfig
    config = configuration()
    random.seed(RUN.SEED)
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    usd, venue = Currency.from_str('USD'), Venue('SIM')
    instrument = native_instrument()
    fill, fee = RUN.COSTS.build_models(config['case'], config['instrument'])
    module = RUN.DISTRIBUTION.build_module(events, 'SPY.SIM', 'USD')
    strategy_class = _build_strategy(rows, instrument.id, venue, usd,
                                     [event['ex_instant_ns'] for event in events])
    bars = RUN.CONVERT.to_bars(rows, config['instrument']['bar_type'], 6, 0)
    with RUN.CapturedOutput(out / 'engine.log'):
        engine = BacktestEngine(BacktestEngineConfig(
            logging=LoggerConfig(stdout_level=LogLevel.INFO, is_colored=False),
            risk_engine=RiskEngineConfig(bypass=False, max_notional_per_order={})))
        failure = None
        try:
            engine.add_venue(venue, OmsType.NETTING, AccountType.MARGIN,
                             [Money(Decimal('100000'), usd)], base_currency=usd,
                             default_leverage=Decimal('2'), margin_model=StandardMarginModel(),
                             fill_model=fill, fee_model=fee, modules=[module],
                             latency_model=None, reject_stop_orders=True, support_contingent_orders=False,
                             use_random_ids=False, frozen_account=False, bar_execution=True,
                             bar_adaptive_high_low_ordering=False, liquidation_enabled=True,
                             liquidation_trigger_ratio=1.0, liquidation_cancel_open_orders=True)
            engine.add_instrument(instrument)
            engine.add_data(bars)
            strategy = strategy_class()
            engine.add_strategy(strategy)
            engine.run()
            result = engine.get_result()
            account = engine.cache.account_for_venue(venue)
            orders = engine.cache.orders()
            reports = {'account': engine.generate_account_report(venue=venue),
                       'positions': engine.generate_positions_report(),
                       'fills': engine.generate_order_fills_report()}
            for name, report in reports.items():
                report.to_csv(out / (name + '.csv'))
            run = {'intents': strategy.intents, 'bars_seen': strategy.bars_seen,
                   'engine_iterations': result.iterations,
                   'errors': strategy.errors, 'native_marks': strategy.native_marks,
                   'alerts_registered': strategy.alerts_registered, 'alerts_fired': strategy.alerts_fired,
                   'native_callback_events': strategy.callback_events,
                   'native_orders': [order.to_dict() for order in orders],
                   'native_order_events': [event.to_dict() for order in orders for event in order.events()],
                   'native_fills': json.loads(reports['fills'].to_json(orient='records')),
                   'native_fee_commissions': {str(key): str(value) for order in orders
                                              for key, value in order.commissions().items()},
                   'native_account_type': account.account_type.name,
                   'native_default_leverage': str(account.default_leverage),
                   'native_final_balance_total': str(account.balance_total(usd)),
                   'native_final_balance_free': str(account.balance_free(usd)),
                   'native_account_events': RUN.account_events(account, usd),
                   'native_instrument': instrument.to_dict(),
                   'fill_model_calls': fill.calls,
                   'distribution_module_record': {'emissions': module.emissions,
                                                  'acknowledgements': module.acknowledgements,
                                                  'errors': module.errors},
                   'open_orders': len(engine.cache.orders_open()),
                   'open_positions': len(engine.cache.positions_open())}
        except BaseException as error:
            failure = error
            raise
        finally:
            try:
                engine.dispose()
            except Exception as error:
                if failure is None:
                    raise
                failure.add_note('engine.dispose also failed:' + repr(error))
            logger_flush()
            sentinel = 'spy-over-limit capture end ' + out.name
            logger_log(LogLevel.INFO, LogColor.NORMAL, 'SpyOverLimitRunner', sentinel)
            logger_flush()
            deadline = time.monotonic() + 30
            while sentinel not in (out / 'engine.log').read_text(errors='replace'):
                if time.monotonic() > deadline:
                    raise ValueError('over_limit_engine_log_capture_incomplete')
                time.sleep(0.01)
    RUN.FIXTURE.check_run_integrity(strategy.errors, strategy.bars_seen, len(rows), result.iterations)
    if module.errors:
        raise ValueError('over_limit_distribution_module_failed:' + ';'.join(module.errors))
    run['engine_error_lines'] = [line for line in (out / 'engine.log').read_text(errors='replace').splitlines()
                                 if '[ERROR]' in line]
    RUN.save(out / 'native-export.json', run)
    return run


def _bound_manifest():
    mapping = json.loads((SOURCE / MANIFEST).read_text())
    inherited, effective = RUN.load_bound_manifests('one_stress')
    if RUN.digest(SOURCE / RUN.MANIFEST_STRESS) != mapping['inherits']['sha256']:
        raise ValueError('over_limit_inherited_stress_manifest_changed')
    if configuration() != mapping['configuration']:
        raise ValueError('over_limit_configuration_differs_from_preregistered')
    for name, digest in mapping['sealed_stress_source_sha256'].items():
        if RUN.digest(SOURCE / name) != digest:
            raise ValueError('qualified_stress_source_changed:' + name)
    return mapping, inherited, effective


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    replay = sub.add_parser('run')
    replay.add_argument('--lean-data', type=Path, required=True)
    replay.add_argument('--out', type=Path, required=True)
    replay.add_argument('--review-record', type=Path, required=True)
    replay.add_argument('--harness-commit', required=True)
    compare = sub.add_parser('compare')
    compare.add_argument('--lean-data', type=Path, required=True)
    compare.add_argument('--receipt', type=Path, required=True)
    compare.add_argument('--out', type=Path, required=True)
    compare.add_argument('--oracle', type=Path, default=RUN.HISTORICAL / 'receipt.json')
    args = parser.parse_args()
    mapping, inherited, effective = _bound_manifest()
    conversion = RUN.CONVERT.convert(args.lean_data, **RUN.WINDOW,
                                     known_short_sessions=RUN.known_short_sessions(effective))
    if conversion['input_hashes'] != inherited['inputs']['frozen_sha256']:
        raise ValueError('over_limit_frozen_inputs_changed')
    source_hashes = {name: RUN.digest(SOURCE / name) for name in reviewed_files()}
    if args.operation == 'run':
        started = datetime.now(timezone.utc).isoformat()
        review = json.loads(args.review_record.read_text())
        require_review(review, source_hashes, started, args.harness_commit)
        if list(sys.argv) not in review.get('authorized_run_argvs', []):
            raise ValueError('over_limit_run_argv_not_preregistered')
        isolation = RUN.isolation_evidence(args.lean_data)
        require_isolation(isolation)
        extension = RUN.check_engine_binary(inherited)
        RUN.check_frozen_plan()
        events = RUN.distribution_events(args.lean_data)
        args.out.mkdir(mode=0o700, parents=True, exist_ok=False)
        frozen = {'argv': list(sys.argv), 'configuration': configuration(),
                  'input_sha256': conversion['input_hashes'], 'source_sha256': source_hashes,
                  'mapping_sha256': RUN.digest(SOURCE / MANIFEST),
                  'review_sha256': RUN.digest(args.review_record), 'isolation': isolation}
        RUN.save(args.out / 'frozen-arguments.private.json', frozen)
        preflight = {'review': review, 'source_hashes': source_hashes, 'started_utc': started,
                     'revision': args.harness_commit, 'isolation': isolation}
        runs = [_run_once(conversion['rows'], events, args.out / label, preflight)
                for label in ('run-1', 'run-2')]
        # Only declared UUID4 init/event IDs are normalized, in a separate
        # comparison value; native exports remain byte-for-byte retained.
        normalized = [RUN.normalize(run, {}) for run in runs]
        receipt = {'schema_version': 'spy-over-limit-native-refusal/1', 'case': 'over_limit',
                   'started_utc': started, 'harness_commit': args.harness_commit,
                   'frozen_arguments': frozen, 'engine_extension': extension,
                   'review_record_path': str(args.review_record), 'review': review,
                   'runs': runs, 'deterministic': normalized[0] == normalized[1],
                   'raw_exports': [{'path': str(args.out / label / 'native-export.json'),
                                    'sha256': RUN.digest(args.out / label / 'native-export.json'),
                                    'engine_log_sha256': RUN.digest(args.out / label / 'engine.log')}
                                   for label in ('run-1', 'run-2')],
                   'frozen_arguments_sha256': RUN.digest(args.out / 'frozen-arguments.private.json'),
                   'normalized_sha256': [RUN.digest_text(json.dumps(run, sort_keys=True)) for run in normalized]}
        RUN.save(args.out / 'receipt.json', receipt)
        print(json.dumps({'receipt': str(args.out / 'receipt.json'), 'engine_runs': 2}))
        return
    receipt = json.loads(args.receipt.read_text())
    frozen = receipt['frozen_arguments']
    frozen_path = args.receipt.parent / 'frozen-arguments.private.json'
    if RUN.digest(frozen_path) != receipt['frozen_arguments_sha256'] or json.loads(frozen_path.read_text()) != frozen:
        raise ValueError('over_limit_preengine_argument_record_changed')
    review_path = Path(receipt['review_record_path'])
    review = json.loads(review_path.read_text())
    require_review(review, source_hashes, receipt['started_utc'], receipt['harness_commit'])
    require_isolation(frozen['isolation'])
    if list(sys.argv) not in review.get('authorized_compare_argvs', []):
        raise ValueError('over_limit_compare_argv_not_preregistered')
    for field, expected in [('source_sha256', source_hashes), ('mapping_sha256', RUN.digest(SOURCE / MANIFEST)),
                            ('review_sha256', RUN.digest(review_path)), ('input_sha256', conversion['input_hashes']),
                            ('configuration', configuration())]:
        if frozen[field] != expected:
            raise ValueError('over_limit_comparison_binding_changed:' + field)
    if frozen['argv'] not in review.get('authorized_run_argvs', []):
        raise ValueError('over_limit_recorded_run_argv_not_preregistered')
    if RUN.digest(args.oracle) != mapping['oracle']['sha256']:
        raise ValueError('over_limit_frozen_oracle_changed')
    expected = CMP.oracle_case(json.loads(args.oracle.read_text()), 'over_limit')
    checks = []
    for index, run in enumerate(receipt['runs']):
        exported = receipt['raw_exports'][index]
        path = Path(exported['path'])
        if (RUN.digest(path) != exported['sha256'] or json.loads(path.read_text()) != run
                or RUN.digest(path.parent / 'engine.log') != exported['engine_log_sha256']):
            raise ValueError('over_limit_raw_native_export_or_log_changed')
        checks.extend({'run': index + 1, **check} for check in refusal_checks(run, conversion['rows'], expected))
    normalized = [RUN.normalize(run, {}) for run in receipt['runs']]
    checks.append({'field': 'exactly_two_native_runs', 'pass': len(receipt['runs']) == 2})
    checks.append({'field': 'equal_normalized_native_exports', 'pass': len(normalized) == 2 and normalized[0] == normalized[1]})
    checks.append({'field': 'official_native_binary', 'pass': receipt['engine_extension'] == RUN.check_engine_binary(inherited)})
    checks.append({'field': 'frozen725bars', 'pass': len(conversion['rows']) == 725})
    verdict = {'verdict': 'PASS' if all(check['pass'] for check in checks) else 'FAIL',
               'checks': checks, 'pass': sum(check['pass'] for check in checks),
               'fail': sum(not check['pass'] for check in checks), 'skipped': 0,
               'case': 'over_limit', 'scope': mapping['scope']}
    RUN.save(args.out, verdict)
    print(json.dumps({key: verdict[key] for key in ('verdict', 'pass', 'fail', 'skipped')}))
    if verdict['fail']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
