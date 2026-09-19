import importlib.util
import json
import os
import tempfile
import hashlib
import subprocess
import sys
import signal
import time
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / 'blueprints/us-equities/research-runtime/run_worker.py'


class ResearchWorkflowTests(unittest.TestCase):
    def implementation(self):
        self.assertTrue(MODULE.is_file(), 'Native research supervisor is not implemented')
        spec = importlib.util.spec_from_file_location('research_worker', MODULE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_claude_usage_does_not_double_count_cache_or_thinking(self):
        m = self.implementation()
        result = {'usage': {'input_tokens': 4, 'cache_creation_input_tokens': 20,
                           'cache_read_input_tokens': 30, 'output_tokens': 9,
                           'output_tokens_details': {'thinking_tokens': 7}}}
        self.assertEqual(m.claude_usage(result)['total_tokens'], 63)
        self.assertIsNone(m.claude_usage({'usage': {'input_tokens': 4}}))
        result['usage']['output_tokens'] = -1
        with self.assertRaises(ValueError):
            m.claude_usage(result)

    def test_native_terminal_error_cannot_pass_with_successful_process_exit(self):
        m = self.implementation()
        with self.assertRaises(ValueError):
            m.claude_result([{'type': 'result', 'subtype': 'success', 'is_error': True}])
        with self.assertRaises(ValueError):
            m.claude_result([{'type': 'result', 'subtype': 'success', 'is_error': False}] * 2)

    def test_report_rejects_future_cutoff_and_invented_citation(self):
        m = self.implementation()
        packet = {'status': 'ready', 'as_of': '2026-09-19T00:00:00Z',
                  'numerical_facts': [{'citation_id': 'filing-1', 'value': '100.25', 'unit': 'USD'}]}
        report = {'status': 'research_only', 'as_of': packet['as_of'],
                  'evidence': [{'citation_id': 'filing-1', 'value': '100.25', 'unit': 'USD'}],
                  'findings': [{'claim': 'A reported fact.', 'citations': ['filing-1']}],
                  'limitations': ['Current snapshot only.'], 'trading_authorized': False}
        m.validate_report(report, packet)
        report['as_of'] = '2027-01-01T00:00:00Z'
        with self.assertRaises(ValueError):
            m.validate_report(report, packet)
        report['as_of'] = packet['as_of']
        report['findings'][0]['citations'] = ['invented']
        with self.assertRaises(ValueError):
            m.validate_report(report, packet)

    def test_report_rejects_changed_units_and_numbers(self):
        m = self.implementation()
        packet = {'status': 'ready', 'as_of': '2026-09-19T00:00:00Z',
                  'numerical_facts': [{'citation_id': 'f', 'value': '9007199254740993', 'unit': 'USD'}]}
        report = {'status': 'research_only', 'as_of': packet['as_of'],
                  'evidence': [{'citation_id': 'f', 'value': '9007199254740992', 'unit': 'USD'}],
                  'findings': [{'claim': 'Fact.', 'citations': ['f']}],
                  'limitations': ['Snapshot.'], 'trading_authorized': False}
        with self.assertRaises(ValueError):
            m.validate_report(report, packet)
        report['evidence'][0].update(value='9007199254740993', unit='shares')
        with self.assertRaises(ValueError):
            m.validate_report(report, packet)

    def test_minimal_environment_excludes_credentials_and_injection(self):
        m = self.implementation()
        from unittest.mock import patch
        with patch.dict(os.environ, {'HF_TOKEN': 'sentinel', 'OPENAI_API_KEY': 'sentinel',
                                     'APCA_API_SECRET_KEY': 'sentinel', 'BASH_ENV': '/bad',
                                     'PYTHONPATH': '/bad', 'NODE_OPTIONS': '--bad'}):
            env = m.child_environment(Path('/native/codex'), '/usr/bin', Path('/workspace'))
        for key in ('HF_TOKEN', 'OPENAI_API_KEY', 'APCA_API_SECRET_KEY', 'BASH_ENV',
                    'PYTHONPATH', 'NODE_OPTIONS'):
            self.assertNotIn(key, env)

    def test_duplicate_role_is_rejected_without_overwriting_receipt(self):
        m = self.implementation()
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'receipt.json'
            m.exclusive_json(p, {'status': 'first'})
            with self.assertRaises(FileExistsError):
                m.exclusive_json(p, {'status': 'second'})
            self.assertEqual(json.loads(p.read_text()), {'status': 'first'})

    def test_nonready_packet_and_duplicate_citations_fail_closed(self):
        m = self.implementation()
        with self.assertRaises(ValueError):
            m.packet_facts({'status': 'incomplete', 'as_of': 'now', 'numerical_facts': []})
        with self.assertRaises(ValueError):
            m.packet_facts({'status': 'ready', 'as_of': 'now',
                            'numerical_facts': [{'citation_id': 'x'}, {'citation_id': 'x'}]})

    def test_modified_handoff_fails_before_dispatch(self):
        m = self.implementation()
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            raw = b'{"changed":true}'
            (p / 'astra.report.json').write_bytes(raw)
            m.exclusive_json(p / 'astra.receipt.json', {'status': 'completed',
                'packet_sha256': 'original-packet', 'report_sha256': hashlib.sha256(b'original report').hexdigest()})
            with self.assertRaisesRegex(ValueError, 'exact source packet'):
                m.verified_handoff(p, {}, 'changed-packet')
            with self.assertRaisesRegex(ValueError, 'report changed'):
                m.verified_handoff(p, {}, 'original-packet')

    def test_unexpected_tool_and_similar_model_name_rejected(self):
        m = self.implementation()
        with self.assertRaises(ValueError):
            m.verify_astra_items([{'type': 'mcpToolCall'}])
        self.assertFalse(m.is_opus5('claude-opus-50'))
        self.assertTrue(m.is_opus5('claude-opus-5[1m]'))

    def test_independent_claude_is_explicit_and_cannot_silently_skip_handoff(self):
        m = self.implementation()
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            with self.assertRaises(FileNotFoundError):
                m.prior_report('claude', False, p, {}, 'hash')
            self.assertIsNone(m.prior_report('claude', True, p, {}, 'hash'))
            with self.assertRaises(ValueError):
                m.prior_report('astra', True, p, {}, 'hash')

    def test_timeout_retires_term_ignoring_descendant(self):
        m = self.implementation()
        code = ('import subprocess,sys,time; '
                'p=subprocess.Popen([sys.executable,"-c",'
                '"import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)"]);'
                'print(p.pid,flush=True);time.sleep(60)')
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            env = m.child_environment(p, os.environ['PATH'], p)
            _, timed_out = m.command_run([sys.executable, '-c', code], '', p, 'test', env, 0.5)
            self.assertTrue(timed_out)
            pid = int((p / 'test.stdout').read_text().strip())
            self.assert_retired(pid)

    def test_supervisor_signal_retires_child_group(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            child = 'import os,time;print(os.getpid(),flush=True);time.sleep(60)'
            script = (
                'import importlib.util,pathlib,os,sys;'
                f's=importlib.util.spec_from_file_location("worker",{str(MODULE)!r});'
                'm=importlib.util.module_from_spec(s);s.loader.exec_module(m);'
                f'p=pathlib.Path({directory!r});'
                f'm.command_run([sys.executable,"-c",{child!r}],"",p,"cancel",'
                'm.child_environment(p,os.environ["PATH"],p),30)')
            supervisor = subprocess.Popen([sys.executable, '-c', script], stderr=subprocess.DEVNULL)
            try:
                output = p / 'cancel.stdout'
                for _ in range(100):
                    if output.exists() and output.stat().st_size:
                        break
                    time.sleep(0.05)
                self.assertTrue(output.exists() and output.stat().st_size)
                pid = int(output.read_text().strip())
                supervisor.send_signal(signal.SIGTERM)
                supervisor.wait(timeout=8)
                self.assert_retired(pid)
            finally:
                if supervisor.poll() is None:
                    supervisor.kill()
                    supervisor.wait()

    def assert_retired(self, pid):
        for _ in range(30):
            stat = Path(f'/proc/{pid}/stat')
            if not stat.exists() or stat.read_text().split()[2] == 'Z':
                return
            time.sleep(0.05)
        self.fail(f'Test descendant {pid} survived cleanup')


if __name__ == '__main__':
    unittest.main()
