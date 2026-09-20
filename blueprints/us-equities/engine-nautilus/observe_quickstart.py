"""Run unchanged upstream quickstart, then retain its public native reports."""
import importlib.metadata
import json
from pathlib import Path
import runpy
import socket
import sys

out = Path('/out')
isolation = {'network_namespace': str(Path('/proc/self/ns/net').readlink()), 'interfaces': socket.if_nameindex(), 'home_exists': Path('/home').exists(), 'environment_names': sorted(__import__('os').environ)}
(out / 'isolation.json').write_text(json.dumps(isolation, indent=2) + '\n')
source_lines = Path('/input/quickstart.py').read_text().splitlines()
dispose_lines = [n for n, line in enumerate(source_lines, 1) if line == 'engine.dispose()']
assert len(dispose_lines) == 1
captured = False
def observe(frame, event, arg):
    global captured
    if frame.f_code.co_filename != '/input/quickstart.py':
        return None
    if event == 'line' and frame.f_lineno == dispose_lines[0] and not captured:
        captured = True
        namespace = frame.f_globals
        engine = namespace['engine']
        result = engine.get_result()
        reports = {
            'account': engine.generate_account_report(venue=namespace['SIM']),
            'positions': engine.generate_positions_report(),
            'fills': engine.generate_order_fills_report(),
        }
        summary = {'version': importlib.metadata.version('nautilus_trader'), 'generated_bars': len(namespace['bars']), 'seed': 42, 'instrument': str(namespace['EURUSD'].id), 'native_result': {name: getattr(result, name) for name in ('iterations','total_events','total_orders','total_positions','backtest_start','backtest_end','stats_pnls','stats_general')}, 'reports': {}}
        for name, report in reports.items():
            report.to_csv(out / (name + '.csv'))
            summary['reports'][name] = {'rows': len(report), 'columns': [str(c) for c in report.columns], 'last_row': json.loads(report.tail(1).to_json(orient='records', date_format='iso'))}
        (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        assert result.iterations == 10000, 'Native engine did not process expected bars'
        assert all(len(r) > 0 for r in reports.values()), 'Native report unexpectedly empty'
        print(json.dumps(summary, sort_keys=True))
    return observe
sys.settrace(observe)
try:
    namespace = runpy.run_path('/input/quickstart.py', run_name='__main__')
finally:
    sys.settrace(None)
assert captured
(out / 'cleanup.json').write_text(json.dumps({'upstream_script_completed_after_dispose': True, 'account_rows_after_dispose': len(namespace['engine'].generate_account_report(venue=namespace['SIM']))}, indent=2)+'\n')
