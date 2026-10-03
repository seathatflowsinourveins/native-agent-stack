"""Authored native-protocol doubles, not execution of the installed engine."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch
from decimal import Decimal

SOURCE = Path(__file__).resolve().parents[1] / 'blueprints/us-equities/engine-nautilus/spy-parity'


def load(name):
    spec = importlib.util.spec_from_file_location('six_test_'+name, SOURCE / (name+'.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class MarketCostProtocolTests(unittest.TestCase):
    def test_market_liquidation_book_is_adverse_before_native_fill(self):
        execution, model = ModuleType('nautilus_trader.execution'), ModuleType('nautilus_trader.model')
        class Fill:
            pass
        class Fee:
            def __init__(self, money, charge_commission_once):
                self.money, self.once = money, charge_commission_once
        class Book:
            def __init__(self, *args): self.orders = []
            def add(self, order, *args): self.orders.append(order)
        execution.FillModel, execution.FixedFeeModel = Fill, Fee
        model.BookOrder = lambda side, price, quantity, order_id: NS(side=side, price=price, quantity=quantity)
        model.BookType = NS(L2_MBP='L2_MBP'); model.Currency = NS(from_str=lambda x:x)
        model.Money = lambda amount,currency:(amount,currency)
        model.OrderBook = Book; model.OrderSide = NS(BUY='BUY', SELL='SELL')
        model.Price = NS(from_str=lambda x:x)
        with patch.dict(sys.modules, {'nautilus_trader.execution': execution, 'nautilus_trader.model': model}):
            fill, fee = load('cost_models').build_models({'fee_usd':'1','currency':'USD','slippage':'0.002'},
                                                       {'price_precision':6})
            order = NS(order_type=NS(name='MARKET'), side=NS(name='SELL'), quantity=65,
                       client_order_id='LIQ-1')
            book = fill.get_orderbook_for_fill_simulation(NS(id='SPY.SIM',price_precision=6),
                                                          order, '100.000000','101.000000')
        self.assertEqual(book.orders[0].price, '99.800000')
        self.assertEqual(book.orders[0].quantity, 65)
        self.assertEqual(fill.calls[0]['reference_price'], '100.000000')
        self.assertTrue(fee.once)


class ObservationProtocolTests(unittest.TestCase):
    def test_process_is_inert_until_adjustment_acknowledgement(self):
        module = ModuleType('nautilus_trader.backtest')
        module.SimulationModule = type('SimulationModule', (), {})
        seen = []
        strategy = NS(after_module_ack=lambda ns:seen.append(ns))
        with patch.dict(sys.modules, {'nautilus_trader.backtest': module}):
            observer = load('margin_strategy').build_observer(lambda:strategy)
        self.assertEqual(observer.process(1000, object()), [])
        self.assertEqual(seen, [])
        observer.acknowledge([])
        self.assertEqual(seen, [1000])
        with self.assertRaisesRegex(ValueError, 'duplicate|missing'):
            observer.acknowledge([])

    def test_observer_retains_callback_error_and_refuses_future_work(self):
        module = ModuleType('nautilus_trader.backtest')
        module.SimulationModule = type('SimulationModule', (), {})
        def failed(ns): raise ValueError('native timing failure')
        with patch.dict(sys.modules, {'nautilus_trader.backtest': module}):
            observer = load('margin_strategy').build_observer(lambda:NS(after_module_ack=failed))
        observer.process(1000, object())
        with self.assertRaisesRegex(ValueError, 'native timing failure'): observer.acknowledge([])
        self.assertEqual(len(observer.errors), 1)
        with self.assertRaisesRegex(ValueError, 'observer_failed'): observer.process(1001, object())

    def test_explicit_engine_end_includes_final_observation_timer(self):
        self.assertEqual(load('six_run').engine_end([{'ts_event_ns':1000}]), 1002)


def protocol_strategy():
    class Clock:
        def __init__(self):self.ns=1000;self.alerts=[]
        def timestamp_ns(self):return self.ns
        def set_time_alert_ns(self,name,stamp,callback,allow_past):
            self.alerts.append((name,stamp,callback));assert allow_past is False
    class Base:
        def __init__(self):
            self.position=Decimal(0);self.cash=Decimal('100000');self.bars_seen=0
            self.order_ref=0;self.errors=[];self.fills=[];self.intents=[];self.latch_events=[]
            self.clock=Clock();self.oco_submitted=[]
            account=NS(balance_total=lambda c:'100000.00 USD',balance_free=lambda c:'100000.00 USD',
                       initial_margin=lambda i:None,maintenance_margin=lambda i:None)
            self.cache=NS(positions_open=lambda **k:[],account_for_venue=lambda v:account)
        def _record(self,callback,error):self.errors.append(str(error))
        def _submit_oco(self,ref,quantity,close,row):
            self.oco_submitted.append((ref,quantity,close,row,self.clock.ns))
    rows=[{'session_date':'2019-12-31','local_start':'15:00','c':'321.86','ts_event_ns':1000},
          {'session_date':'2020-01-02','local_start':'09:00','c':'323.58','ts_event_ns':2000}]
    fixture=NS(build_strategy=lambda *a,**k:Base,posted_distribution_ledger=lambda *a:[],
               target_quantity=lambda e,t,b,p:int((e*t*b/p).to_integral_value(rounding='ROUND_FLOOR')),
               check_decision_bar_is_session_final=lambda rows,index:None)
    case={'initial_cash_usd':'100000','target':'1','sizing_buffer':'0.98','fee_usd':'0',
          'adaptive':False,'reject':False,'entry_decision_date':'2019-12-31','exit_decision_date':'2020-04-29'}
    model=ModuleType('nautilus_trader.model')
    model.ClientOrderId=lambda x:x;model.OrderSide=NS(BUY='BUY',SELL='SELL')
    model.Quantity=NS(from_int=lambda x:x);model.TimeInForce=NS(DAY='DAY')
    with patch.dict(sys.modules,{'nautilus_trader.model':model}):
        cls=load('margin_strategy').build_strategy(fixture,load('margin_policy'),
                      NS(emissions=[],acknowledgements=[]),'SPY.SIM','SIM','USD','bar',rows,case)
    return cls(),rows


class NativePhaseAdapterTests(unittest.TestCase):
    def test_ack_does_not_mark_or_decide_before_actual_completion(self):
        s,rows=protocol_strategy();s._handle_bar(NS(ts_event=1000,close='321.86'))
        s.after_module_ack(1000)
        self.assertEqual(s.marks,[]);self.assertEqual(s.oco_submitted,[])
        name,stamp,callback=s.clock.alerts[0];self.assertEqual(stamp,1001)
        s.clock.ns=stamp;callback(NS(name=name,ts_event=stamp))
        self.assertEqual(s.marks[0]['economic_ts_event_ns'],1000)
        self.assertEqual(s.marks[0]['observation_ts_event_ns'],1001)
        self.assertEqual(s.oco_submitted[0][1],304)
        self.assertEqual(s.oco_submitted[0][4],1001)
        s.phase.finish()

    def test_wrong_native_alert_identity_is_retained_and_refused(self):
        s,rows=protocol_strategy();s._handle_bar(NS(ts_event=1000,close='321.86'));s.after_module_ack(1000)
        s.clock.ns=1001
        with self.assertRaisesRegex(ValueError,'observation_alert_name'):
            s._on_observation(NS(name='other_alert',ts_event=1001))
        self.assertEqual(s.marks,[]);self.assertEqual(len(s.errors),1)

    def test_next_bar_before_completion_fails_closed(self):
        s,rows=protocol_strategy();s._handle_bar(NS(ts_event=1000,close='321.86'));s.after_module_ack(1000)
        with self.assertRaisesRegex(ValueError,'previous_bar_observation_missing'):
            s._handle_bar(NS(ts_event=2000,close='323.58'))
        with self.assertRaisesRegex(ValueError,'pending_observation'):s.phase.finish()


if __name__ == '__main__': unittest.main()
