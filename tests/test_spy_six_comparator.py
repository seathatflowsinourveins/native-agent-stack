"""Independent comparator mutation controls on synthetic complete mark streams."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1]/'blueprints/us-equities/engine-nautilus/spy-parity'
spec = importlib.util.spec_from_file_location('spy_six_comparison_test',SOURCE/'compare_six.py')
CMP = importlib.util.module_from_spec(spec);spec.loader.exec_module(CMP)
LIMITS = json.loads((SOURCE/'tolerances.json').read_text())['limits']


def fixture():
    rows = [{'ts_event_ns':(1000+i*3600)*10**9,'c':'321.86','o':'321.86'} for i in range(725)]
    audit = [{'kind':'mark','utc_seconds':r['ts_event_ns']//10**9,'quantity':'0', 'price':'321.86',
              'equity':'100000','cash':'100000','margin_used':'0','margin_remaining':'100000',
              'peak':'100000','drawdown':'0','gross':'0'} for r in rows]
    marks = [{**m,'economic_ts_event_ns':r['ts_event_ns'],'observation_ts_event_ns':r['ts_event_ns']+1,
              'maintenance_authority':'frozen_LEAN_fixture_policy','native_balance_total':'100000',
              'native_balance_free':'100000','native_initial_margin':'0','native_maintenance_diagnostic':'0'}
             for m,r in zip(audit,rows)]
    init = {'type':'OrderInitialized','client_order_id':'SPY-POLICY-1','ts_event':1000*10**9+1}
    denied = {**init,'type':'OrderDenied',
              'reason':'INITIAL_MARGIN_EXCEEDS_FREE_BALANCE: free=100000.00 USD, margin=195851.81 USD'}
    intents = [{'order_ref':1,'utc_seconds':1000,'quantity':1217,'reason':'entry','decision_clock_ns':1000*10**9+1}]
    oracle = {'id':'over_limit','intents':intents,'fills':[],'fees_usd':'0','dividends_usd':'0',
              'end_cash_usd':'100000','margin_calls':[],'reductions':[]}
    run = {'case':'over_limit','bars_seen':725,'engine_iterations':725,'engine_run_end_ns':rows[-1]['ts_event_ns']+2,
           'errors':[],'observer_errors':[],'engine_log_scan':{'error_lines':0},
           'distribution_module_record':{'errors':[],'pending':[]},'final_quantity':'0','intents':intents,
           'fills':[],'fees_usd':'0','dividend_cash_usd':'0','cash':'100000','native_final_balance_total':'100000',
           'marks':marks,'phase_alerts_registered':[{} for _ in rows],
           'phase_alerts_fired':[{'ts_event_ns':r['ts_event_ns']+1} for r in rows],
           'margin_calls':[],'margin_warnings':[],'latch_events':[],'distribution_ledger':[],
           'native_callback_events':[init,denied],'native_order_events':[init,denied],
           'native_orders':[{'client_order_id':'SPY-POLICY-1','type':'MARKET','status':'DENIED',
                             'side':'BUY','quantity':'1217','filled_qty':'0'}],
           'native_fills':[], 'fill_model_calls':[],'oco_pairs':[]}
    run.update(native_account_type='MARGIN',native_default_leverage='2',
               native_instrument={'margin_init':'0.5','margin_maint':'0.5'},
               native_commissions_by_order={'SPY-POLICY-1':{}})
    return run,oracle,audit,rows


def failed(run,oracle,audit,rows):
    return [c['field'] for c in CMP.compare_case(run,oracle,audit,rows,LIMITS) if not c['pass']]


class CompleteEconomicControlTests(unittest.TestCase):
    def test_complete_synthetic_control_and_missing_or_changed_mark(self):
        run,o,a,rows=fixture();self.assertEqual(failed(run,o,a,rows),[])
        run['marks'].pop();self.assertIn('all_725_marks',failed(run,o,a,rows))
        run,o,a,rows=fixture();run['marks'][300]['cash']='99999'
        self.assertIn('mark.300.cash',failed(run,o,a,rows))
        self.assertIn('mark.300.reconciled_cash',failed(run,o,a,rows))

    def test_missing_reordered_or_wrong_reason_native_callbacks_fail(self):
        for mutate in [lambda r:r.update(native_callback_events=[]),
                       lambda r:r['native_callback_events'].reverse(),
                       lambda r:r['native_callback_events'][1].update(reason='synthetic Invalid')]:
            run,o,a,rows=fixture();mutate(run)
            self.assertTrue(failed(run,o,a,rows))

    def test_final_timer_early_or_missing_completion_is_not_qualified(self):
        run,o,a,rows=fixture();run['engine_run_end_ns']=rows[-1]['ts_event_ns']
        self.assertIn('native_end_includes_final_observation',failed(run,o,a,rows))
        run,o,a,rows=fixture();run['phase_alerts_fired'].pop()
        self.assertIn('phase_firing_instants',failed(run,o,a,rows))
        run,o,a,rows=fixture();run['marks'][-1]['observation_ts_event_ns']=rows[-1]['ts_event_ns']
        self.assertIn('observation_exact_plus_one',failed(run,o,a,rows))

    def test_missing_call_latch_and_warning_events_cannot_pass_counts(self):
        run,o,a,rows=fixture();o['margin_calls']=[{'utc_seconds':1000,'count':1,'equity':'100000','margin_remaining':'-1000'}]
        self.assertIn('margin_calls.count',failed(run,o,a,rows))
        o['reductions']=[{'utc_seconds':1000,'equity':'95000','peak':'100000','drawdown':'0.05'}]
        self.assertIn('latch_events.count',failed(run,o,a,rows))
        a.append({'kind':'margin_warning','utc_seconds':1000,'equity':'100000','margin_remaining':'1'})
        self.assertIn('margin_warnings.count',failed(run,o,a,rows))

    def test_native_maintenance_is_retained_and_never_relabelled_as_policy(self):
        run,o,a,rows=fixture();run['marks'][10]['native_maintenance_diagnostic']='12345'
        self.assertEqual(failed(run,o,a,rows),[])
        del run['marks'][10]['native_maintenance_diagnostic']
        self.assertIn('mark.10.native_diagnostic_retained',failed(run,o,a,rows))

    def test_denied_quantity_or_synthetic_fill_cannot_pass_native_refusal(self):
        run,o,a,rows=fixture();run['native_orders'][0]['quantity']='1218'
        self.assertIn('native_denied_order_quantity',failed(run,o,a,rows))
        run,o,a,rows=fixture();run['native_fills']=[{'synthetic':'fill'}]
        self.assertIn('no_native_refusal_fills',failed(run,o,a,rows))


if __name__=='__main__':unittest.main()
