"""Prospective over-limit refusal mapping; no BacktestEngine is constructed here."""
import ast
import copy
from decimal import Decimal
import importlib.util
import inspect
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'blueprints/us-equities/engine-nautilus/spy-parity'


class OverLimitTests(unittest.TestCase):
    def module(self):
        path = SOURCE / 'over_limit.py'
        self.assertTrue(path.exists(), 'isolated over-limit mapping is not implemented')
        spec = importlib.util.spec_from_file_location('spy_over_limit_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def rows(self):
        return [{'session_date': '2019-12-31', 'local_start': '15:00',
                 'ts_event_ns': 1577826000 * 10**9, 'c': '322.00'},
                {'session_date': '2020-01-02', 'local_start': '09:00',
                 'ts_event_ns': 1577977200 * 10**9, 'c': '324.00'}]

    def refusal_record(self, module):
        # Synthetic data is confined to this mutation test, never an engine export.
        return {'intents': [module.decision_intent(self.rows())], 'bars_seen': 2, 'engine_iterations': 2,
                'errors': [], 'native_fills': [], 'open_orders': 0, 'open_positions': 0,
                'engine_error_lines': [], 'distribution_module_record': {'errors': [], 'emissions': [], 'acknowledgements': []},
                'fill_model_calls': [], 'native_account_type': 'MARGIN',
                'native_default_leverage': '2', 'native_fee_commissions': {},
                'native_final_balance_total': '100000.00 USD', 'native_final_balance_free': '100000.00 USD',
                'native_orders': [{'client_order_id': 'SPY-OVER-LIMIT-1', 'type': 'MARKET',
                                   'side': 'BUY', 'quantity': '1217', 'filled_qty': '0', 'status': 'DENIED'}],
                'native_order_events': [
                    {'type': 'OrderInitialized', 'client_order_id': 'SPY-OVER-LIMIT-1'},
                    {'type': 'OrderDenied', 'client_order_id': 'SPY-OVER-LIMIT-1',
                     'ts_event': 1577826000 * 10**9,
                     'reason': 'INITIAL_MARGIN_EXCEEDS_FREE_BALANCE: free=100000.00 USD, margin=195937.00 USD'}],
                'native_marks': [{'ts_event_ns': row['ts_event_ns'], 'balance_total': '100000.00 USD',
                                  'balance_free': '100000.00 USD', 'initial_margin': '0.00 USD',
                                  'maintenance_margin': '0.00 USD', 'position_count': 0}
                                 for row in self.rows()]}

    def test_configuration_uses_standard_fixed_half_margin_without_bypass(self):
        config = self.module().configuration()
        self.assertEqual(config['venue']['account_type'], 'MARGIN')
        self.assertEqual(config['venue']['margin_model'], 'StandardMarginModel')
        self.assertEqual(config['venue']['default_leverage'], '2')
        self.assertEqual(config['instrument']['margin_init'], '0.5')
        self.assertEqual(config['instrument']['margin_maint'], '0.5')
        self.assertFalse(config['risk']['bypass'])
        self.assertEqual(config['risk']['max_notional_per_order'], {})

    def test_on_start_schedules_both_frozen_ex_dates_as_native_noop_alerts(self):
        module = self.module()
        historical = json.loads((SOURCE / 'receipt.json').read_text())
        events = [{'ex_instant_ns': event['utc_seconds'] * 10**9}
                  for event in historical['derived_distributions']]
        instants = [1576818000 * 10**9, 1584676800 * 10**9]
        self.assertEqual([event['ex_instant_ns'] for event in events], instants)
        scheduled = []

        class FakeStrategy:
            def __init__(self, config):
                self.clock = SimpleNamespace(set_time_alert_ns=lambda name, instant, callback, **kwargs:
                                             scheduled.append((name, instant, callback, kwargs)))
                self.subscriptions = []

            def subscribe_bars(self, bar_type):
                self.subscriptions.append(bar_type)

        native_interfaces = {
            'nautilus_trader.config': SimpleNamespace(StrategyConfig=lambda: None),
            'nautilus_trader.model': SimpleNamespace(BarType=SimpleNamespace(from_str=lambda value: value)),
            'nautilus_trader.trading': SimpleNamespace(Strategy=FakeStrategy),
        }
        # Exercise the real construction call without constructing an engine:
        # alerts must use the same frozen events as DistributionModule.
        tree = ast.parse(inspect.getsource(module._run_once))
        call = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == '_build_strategy')
        with patch.dict(sys.modules, native_interfaces):
            strategy_class = eval(compile(ast.Expression(call), '<native-strategy-construction>', 'eval'),
                                  {'_build_strategy': module._build_strategy, 'rows': self.rows(),
                                   'instrument': SimpleNamespace(id='SPY.SIM'), 'venue': 'SIM',
                                   'usd': 'USD', 'events': events})
            strategy = strategy_class()
        strategy.on_start()
        self.assertEqual(strategy.subscriptions, [module.configuration()['instrument']['bar_type']])
        self.assertEqual([(name, instant, kwargs) for name, instant, _, kwargs in scheduled],
                         [('ex_date_' + str(instant), instant, {'allow_past': False}) for instant in instants])
        before = (strategy.intents.copy(), strategy.native_marks.copy(), strategy.callback_events.copy(),
                  strategy.errors.copy(), strategy.bars_seen)
        for name, instant, callback, _ in scheduled:
            callback(SimpleNamespace(name=name, ts_event=instant))
        self.assertEqual((strategy.intents, strategy.native_marks, strategy.callback_events,
                          strategy.errors, strategy.bars_seen), before)
        self.assertEqual(strategy.alerts_fired,
                         [{'name': name, 'ts_event_ns': instant} for name, instant, _, _ in scheduled])

    def test_one_intent_is_sized_from_decision_bar_not_expected_quantity(self):
        module = self.module()
        first = module.decision_intent(self.rows())
        self.assertEqual((first['quantity'], first['utc_seconds'], first['target']),
                         (1217, 1577826000, '4'))
        changed = self.rows()
        changed[0]['c'] = '400.00'
        self.assertEqual(module.decision_intent(changed)['quantity'], 980)

    def test_native_clock_startup_and_callback_failures_are_retained_for_guard(self):
        module = self.module()

        def fail_registration(*args, **kwargs):
            raise RuntimeError('native_alert_registration_failure')

        class FakeStrategy:
            def __init__(self, config):
                self.clock = SimpleNamespace(set_time_alert_ns=fail_registration)

            def subscribe_bars(self, bar_type):
                pass

        class FailedNativeAlert:
            name = 'ex_date_1576818000000000000'

            @property
            def ts_event(self):
                raise RuntimeError('native_alert_callback_failure')

        native_interfaces = {
            'nautilus_trader.config': SimpleNamespace(StrategyConfig=lambda: None),
            'nautilus_trader.model': SimpleNamespace(BarType=SimpleNamespace(from_str=lambda value: value)),
            'nautilus_trader.trading': SimpleNamespace(Strategy=FakeStrategy),
        }
        with patch.dict(sys.modules, native_interfaces):
            strategy = module._build_strategy(self.rows(), 'SPY.SIM', 'SIM', 'USD',
                                             [1576818000000000000, 1584676800000000000])()
        with self.assertRaisesRegex(RuntimeError, 'native_alert_registration_failure'):
            strategy.on_start()
        self.assertEqual(strategy.errors, ['on_start:RuntimeError:native_alert_registration_failure'])
        with self.assertRaisesRegex(RuntimeError, 'native_alert_callback_failure'):
            strategy._on_ex_date_alert(FailedNativeAlert())
        self.assertEqual(strategy.errors,
                         ['on_start:RuntimeError:native_alert_registration_failure',
                          '_on_ex_date_alert:RuntimeError:native_alert_callback_failure'])
        run = self.refusal_record(module)
        run['errors'] = strategy.errors
        oracle = module.CMP.oracle_case(json.loads((ROOT / 'blueprints/us-equities/historical-simulation/receipt.json').read_text()), 'over_limit')
        self.assertFalse(next(check for check in module.refusal_checks(run, self.rows(), oracle)
                              if check['field'] == 'no_callback_errors')['pass'])

    def test_decision_requires_session_final_bar(self):
        rows = self.rows()
        rows.insert(1, {**rows[0], 'local_start': '16:00'})
        with self.assertRaisesRegex(ValueError, 'decision_bar_not_session_final'):
            self.module().decision_intent(rows)

    def test_missing_or_duplicate_decision_refuses(self):
        module = self.module()
        with self.assertRaises(ValueError):
            module.decision_intent(self.rows()[1:])
        with self.assertRaises(ValueError):
            module.decision_intent([self.rows()[0], *self.rows()])

    def test_review_must_cover_new_case_and_exact_sources_before_run(self):
        module = self.module()
        hashes = {'over_limit.py': 'a' * 64}
        review = {'schema_version': module.REVIEW_SCHEMA, 'case': 'over_limit',
                  'reviewed_commit': 'b' * 40, 'reviewed_local_source_sha256': hashes,
                  'independent_review': True, 'completed_utc': '2026-10-02T12:00:00Z',
                  'unresolved_findings': 0}
        module.require_review(review, hashes, '2026-10-02T13:00:00+00:00', 'b' * 40)
        for field, value in [('case', 'one_stress'), ('independent_review', False),
                             ('unresolved_findings', 1),
                             ('reviewed_local_source_sha256', {}),
                             ('reviewed_commit', 'c' * 40),
                             ('completed_utc', '2026-10-02T14:00:00Z')]:
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    module.require_review({**review, field: value}, hashes,
                                          '2026-10-02T13:00:00+00:00', 'b' * 40)

    def test_strict_fence_refuses_network_writable_mounts_and_initial_namespace(self):
        module = self.module()
        good = {'network_interfaces': [[1, 'lo']], 'environment_names': list(module.RUN.ISOLATED_ENVIRONMENT_VALUES),
                'environment_values': module.RUN.ISOLATED_ENVIRONMENT_VALUES,
                'python_flags_isolated': 1,
                'read_only': {'harness_source': True, 'data_root': True, 'python_prefix': True},
                'namespaces': {'uid_map': '0 1000 1', 'pid1_comm': 'bwrap'}}
        module.require_isolation(good)
        for field, value in [('network_interfaces', [[1, 'lo'], [2, 'eth0']]),
                             ('read_only', {'harness_source': False}),
                             ('python_flags_isolated', 0),
                             ('environment_names', ['OPENAI_API_KEY']),
                             ('namespaces', {'uid_map': '0 0 4294967295', 'pid1_comm': 'bwrap'})]:
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    module.require_isolation({**good, field: value})

    def test_native_denial_reason_is_preserved_and_specific(self):
        module = self.module()
        reason = 'INITIAL_MARGIN_EXCEEDS_FREE_BALANCE: free=100000.00 USD, margin=195937.00 USD'
        self.assertTrue(module.initial_margin_denial(reason))
        for reason in ['buying power rejected by harness', 'NO_MARKET_PRICE',
                       'NOTIONAL_EXCEEDS_MAX_PER_ORDER', 'insufficient cash']:
            self.assertFalse(module.initial_margin_denial(reason))

    def test_comparator_rejects_accepted_fill_or_multiple_native_refusals(self):
        module = self.module()
        run = self.refusal_record(module)
        oracle = module.CMP.oracle_case(json.loads((ROOT / 'blueprints/us-equities/historical-simulation/receipt.json').read_text()), 'over_limit')
        self.assertFalse([c for c in module.refusal_checks(run, self.rows(), oracle) if not c['pass']])
        for mutation in ['fill', 'accepted', 'extra_denial', 'cash', 'final_cash', 'wrong_reason', 'wrong_quantity', 'module_error', 'engine_error', 'iterations']:
            changed = copy.deepcopy(run)
            if mutation == 'fill': changed['native_orders'][0]['filled_qty'] = '1'
            if mutation == 'accepted': changed['native_order_events'].append({'type': 'OrderAccepted'})
            if mutation == 'extra_denial': changed['native_order_events'].append(changed['native_order_events'][-1])
            if mutation == 'cash': changed['native_marks'][-1]['balance_total'] = '99999.99 USD'
            if mutation == 'final_cash': changed['native_final_balance_total'] = '99999.99 USD'
            if mutation == 'wrong_reason': changed['native_order_events'][-1]['reason'] = 'NO_MARKET_PRICE'
            if mutation == 'wrong_quantity': changed['native_orders'][0]['quantity'] = '1216'
            if mutation == 'module_error': changed['distribution_module_record']['errors'] = ['unapplied_distribution']
            if mutation == 'engine_error': changed['engine_error_lines'] = ['[ERROR] unexpected native failure']
            if mutation == 'iterations': changed['engine_iterations'] = 1
            with self.subTest(mutation=mutation):
                self.assertTrue([c for c in module.refusal_checks(changed, self.rows(), oracle) if not c['pass']])

    def test_no_synthetic_native_record_builder_in_production(self):
        module = self.module()
        self.assertNotIn('test_refusal_record', Path(module.__file__).read_text())

    def test_native_configuration_and_market_order_api_without_engine(self):
        module = self.module()
        try:
            from nautilus_trader.backtest import BacktestEngineConfig, BacktestVenueConfig
            from nautilus_trader.model import Currency, StandardMarginModel
            from nautilus_trader.risk import RiskEngineConfig
        except ImportError:
            self.skipTest('official task-private native wheel required for API component check')
        equity = module.native_instrument()
        self.assertEqual(equity.margin_init, Decimal('0.5'))
        self.assertEqual(equity.margin_maint, Decimal('0.5'))
        venue = BacktestVenueConfig(name='SIM', oms_type='NETTING', account_type='MARGIN',
                                   starting_balances=['100000 USD'], base_currency=Currency.from_str('USD'),
                                   default_leverage=Decimal('2'), margin_model=StandardMarginModel())
        self.assertIsInstance(venue.margin_model, StandardMarginModel)
        config = BacktestEngineConfig(risk_engine=RiskEngineConfig(bypass=False, max_notional_per_order={}))
        self.assertFalse(config.risk_engine.bypass)
        order = module.native_market_order('TESTER-001', 'OVER-LIMIT-001', 1217, 1577826000 * 10**9)
        self.assertEqual(order.to_dict()['type'], 'MARKET')
        self.assertEqual(order.to_dict()['filled_qty'], '0')
        self.assertEqual([event.to_dict()['type'] for event in order.events()], ['OrderInitialized'])

    def test_native_empty_margin_account_api_and_double_discount_trap(self):
        module = self.module()
        try:
            from nautilus_trader.core import UUID4
            from nautilus_trader.model import (AccountBalance, AccountId, AccountState, AccountType,
                                               Currency, MarginAccount, Money, Price, Quantity)
        except ImportError:
            self.skipTest('official task-private native wheel required for account component check')
        usd = Currency.from_str('USD')
        total, zero = Money(Decimal('100000'), usd), Money(Decimal(0), usd)
        state = AccountState(AccountId('SIM-001'), AccountType.MARGIN,
                             [AccountBalance(total, zero, total)], [], True, UUID4(), 0, 0,
                             base_currency=usd)
        account = MarginAccount(state, True)
        self.assertEqual(str(account.balance_total(usd)), '100000.00 USD')
        self.assertEqual(str(account.balance_free(usd)), '100000.00 USD')
        self.assertEqual(str(account.total_initial_margin(usd)), '0.00 USD')
        self.assertEqual(str(account.total_maintenance_margin(usd)), '0.00 USD')
        # Standalone accounts use LeveragedMarginModel. This demonstrates why
        # the engine must explicitly select Standard for rates.5/leverage2.
        first = account.calculate_initial_margin(module.native_instrument(), Quantity.from_int(1217), Price.from_str('322.000000'))
        account.set_default_leverage(Decimal('2'))
        discounted = account.calculate_initial_margin(module.native_instrument(), Quantity.from_int(1217), Price.from_str('322.000000'))
        self.assertEqual(str(first), '195937.00 USD')
        self.assertEqual(str(discounted), '97968.50 USD')


if __name__ == '__main__':
    unittest.main()
