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


class FailedRunCaptureTests(unittest.TestCase):
    """Actual driver control flow with dependency-free protocol doubles only."""
    def failed_driver(self, directory, *, broken_writer=False, broken_dispose=False, lost_log=False, missing_report=False):
        import json
        module=load('six_run');trace=[];original=ValueError('pending_observation_at_end')
        out=Path(directory)/'failed-run';log=out/'engine.log'
        class Output:
            def __init__(self,path):self.path=path
            def __enter__(self):self.path.write_text('')
            def __exit__(self,*args):return False
        class Report:
            def to_json(self,orient):trace.append('report_json');return '[]'
            def to_csv(self,path):trace.append('report_csv');Path(path).write_text('raw-report\n')
        def fail_phase():raise original
        def fail_free(currency):raise RuntimeError('free_balance_unavailable')
        account=NS(balance_total=lambda c:'100000.00 USD',balance_free=fail_free,
                   initial_margin=lambda i:None,maintenance_margin=lambda i:None)
        order=NS(client_order_id='RAW-1',to_dict=lambda:{'client_order_id':'RAW-1','status':'ACCEPTED'},
                 events=lambda:[NS(to_dict=lambda:{'type':'OrderInitialized','client_order_id':'RAW-1'})],
                 commissions=lambda:{})
        def orders():trace.append('orders_before_dispose');return [order]
        class ProtocolBackend:
            def __init__(self):
                self.cache=NS(orders=orders,positions_open=lambda:[],account_for_venue=lambda v:account)
            def add_venue(self,*args,**kwargs):pass
            def add_instrument(self,*args):pass
            def add_data(self,*args):pass
            def add_strategy(self,*args):pass
            def run(self,**kwargs):trace.append('protocol_run_only')
            def get_result(self):return NS(iterations=1)
            def generate_account_report(self,**kwargs):return Report()
            def generate_positions_report(self):return Report()
            def generate_order_fills_report(self):return Report()
            def dispose(self):
                trace.append('dispose')
                strategy.native_callback_events.clear()
                if broken_dispose:raise RuntimeError('dispose_failed')
        if missing_report:del ProtocolBackend.generate_positions_report
        backend=ProtocolBackend()
        strategy=NS(phase=NS(finish=fail_phase),errors=[],bars_seen=1,marks=[],phase_alerts_fired=[],
                    fills=[],intents=[],native_callback_events=[{'type':'OrderInitialized','client_order_id':'RAW-1'}],
                    order_events=[],margin_calls=[],
                    margin_warnings=[],latch_events=[],position=0,cash=Decimal('100000'))
        distribution=NS(emissions=[],acknowledgements=[],errors=[],pending=[])
        observer=NS(pending=None,errors=[],acknowledgements=[])
        adapter=NS(build_strategy=lambda *args,**kwargs:lambda:strategy,
                   build_observer=lambda get:observer)
        costs=NS(build_models=lambda *args:(NS(calls=[]),object()))
        def get_source(name,path):
            return adapter if path.name=='margin_strategy.py' else costs if path.name=='cost_models.py' else object()
        def save(path,value):
            trace.append('snapshot_write')
            if broken_writer:raise RuntimeError('snapshot_write_failed')
            Path(path).write_text(json.dumps(value))
        def write_log(level,color,component,text):
            if not lost_log:log.write_text(log.read_text()+text+'\n')
        model=ModuleType('nautilus_trader.model')
        for name in ('ClientOrderId','Symbol','Venue'):setattr(model,name,lambda value:value)
        for name in ('Currency','InstrumentId','Price'):setattr(model,name,NS(from_str=lambda value:value))
        model.Quantity=NS(from_int=lambda value:value)
        model.AccountType=NS(MARGIN='MARGIN');model.OmsType=NS(NETTING='NETTING')
        model.Money=lambda *args:args
        model.Equity=lambda *args,**kwargs:NS(id='SPY.SIM',to_dict=lambda:{'id':'SPY.SIM'})
        modules={
            'nautilus_trader.backtest':NS(BacktestEngine=lambda config:backend),
            'nautilus_trader.common':NS(LogColor=NS(NORMAL='NORMAL'),LogLevel=NS(INFO='INFO'),
                                      logger_flush=lambda:None,logger_log=write_log),
            'nautilus_trader.config':NS(BacktestEngineConfig=lambda **k:k,LoggerConfig=lambda **k:k,
                                      RiskEngineConfig=lambda **k:k),
            'nautilus_trader.accounting':NS(StandardMarginModel=lambda:object()),
            'nautilus_trader.model':model}
        base=NS(CASE={'initial_cash_usd':'100000'},INSTRUMENT={'bar_type':'bar'},_load=get_source,
                DISTRIBUTION=NS(build_module=lambda *args:distribution),FIXTURE=object(),
                CONVERT=NS(to_bars=lambda *args:[]),CapturedOutput=Output,save=save,
                account_events=lambda account,currency:[])
        clock=iter([0,31])
        with patch.dict(sys.modules,modules), patch.object(module.time,'monotonic',side_effect=lambda:next(clock)):
            try:
                module.run_once([{'ts_event_ns':1000}],[],out,'failed-run',
                                {'cases':{'one_zero':{}},'native':{}},'one_zero',base)
            except BaseException as error:
                observed=error
            else:raise AssertionError('failed phase was accepted')
        return observed,original,trace,out

    def test_incomplete_native_snapshot_is_retained_before_dispose_with_independent_errors(self):
        import json,tempfile
        with tempfile.TemporaryDirectory() as temp:
            observed,original,trace,out=self.failed_driver(temp)
            self.assertIs(observed,original)
            path=out/'failed-native-state.private.json'
            self.assertTrue(path.is_file(),'phase failure lost its raw cache/account snapshot')
            record=json.loads(path.read_text())
            self.assertEqual(record['status'],'FAILED')
            self.assertEqual(record['captures']['native_orders']['status'],'captured')
            self.assertEqual(record['captures']['native_account_balance_free']['status'],'error')
            self.assertIn('free_balance_unavailable',record['captures']['native_account_balance_free']['error'])
            self.assertEqual(record['captures']['native_fills_report']['status'],'captured')
            self.assertEqual(record['captures']['strategy_native_callback_events']['value'],
                             [{'type':'OrderInitialized','client_order_id':'RAW-1'}])
            self.assertLess(trace.index('snapshot_write'),trace.index('dispose'))
            self.assertLess(trace.index('orders_before_dispose'),trace.index('dispose'))
            self.assertTrue((out/'failed-fills.csv').is_file())

    def test_log_timeout_does_not_replace_original_phase_failure(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            observed,original,trace,out=self.failed_driver(temp,lost_log=True)
            self.assertIs(observed,original,'log timeout replaced the original failed phase')
            self.assertTrue(any('six_native_log_capture_incomplete' in n for n in original.__notes__))

    def test_failed_snapshot_writer_and_disposal_preserve_original_and_attempt_log(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            observed,original,trace,out=self.failed_driver(temp,broken_writer=True,broken_dispose=True)
            self.assertIs(observed,original)
            self.assertIn('snapshot_write',trace)
            self.assertTrue(any('snapshot_write_failed' in n for n in original.__notes__))
            self.assertTrue(any('dispose_failed' in n for n in original.__notes__))
            self.assertIn('spy-six-case capture end failed-run',(out/'engine.log').read_text())

    def test_missing_report_api_is_independent_and_cannot_mask_primary_failure(self):
        import json,tempfile
        with tempfile.TemporaryDirectory() as temp:
            observed,original,trace,out=self.failed_driver(temp,missing_report=True)
            self.assertIs(observed,original,'missing capture API masked primary failure')
            record=json.loads((out/'failed-native-state.private.json').read_text())
            self.assertEqual(record['captures']['native_positions_report']['status'],'error')
            self.assertEqual(record['captures']['native_fills_report']['status'],'captured')
            self.assertEqual(record['captures']['native_account_initial_margin']['status'],'unavailable')
