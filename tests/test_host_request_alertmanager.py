"""Alertmanager notice transport on ephemeral loopback fixtures, not live delivery.

No production backend, Telegram receiver, GitHub request or credential is used.
"""

from __future__ import annotations

import contextlib
import http.server
import io
import json
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

from scripts import host_requests as hr


class AlertmanagerTransportTests(unittest.TestCase):
    @contextlib.contextmanager
    def server(self, status=200, redirect=False):
        received = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                received.append((self.path, dict(self.headers), body))
                self.send_response(302 if redirect else status)
                if redirect:
                    self.send_header('Location', '/redirected')
                self.end_headers()
                self.wfile.write(b'{}')

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f'http://127.0.0.1:{server.server_port}/api/v2/alerts', received
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_notice_is_api_v2_json_with_owner_routing_labels(self):
        with self.server() as (url, received):
            hr.send_alertmanager_notice(url, '#23 queued from fixture-host (model qualification)')
        self.assertEqual(len(received), 1)
        path, headers, body = received[0]
        self.assertEqual(path, '/api/v2/alerts')
        self.assertEqual(headers['Content-Type'], 'application/json')
        alerts = json.loads(body)
        self.assertEqual(len(alerts), 1)
        labels = alerts[0]['labels']
        self.assertEqual(labels['alertname'], 'NativeStackHostRequest')
        self.assertEqual(labels['severity'], 'critical')
        self.assertEqual(labels['unit'], 'host-requests-workstation')
        self.assertEqual(labels['host'], 'NativeStack2604')
        self.assertEqual(len(labels['notice']), 16)
        self.assertEqual(alerts[0]['annotations']['summary'],
                         '#23 queued from fixture-host (model qualification)')
        self.assertNotIn('Authorization', headers)

    def test_non_schema_acknowledgement_is_an_error(self):
        with self.server(status=202) as (url, received):
            with self.assertRaises(OSError):
                hr.send_alertmanager_notice(url, '#23 queued')
        self.assertEqual(len(received), 1)

    def test_redirect_is_not_followed(self):
        with self.server(redirect=True) as (url, received):
            with self.assertRaises(OSError):
                hr.send_alertmanager_notice(url, '#23 queued')
        self.assertEqual(len(received), 1)

    def test_proxy_environment_is_not_used(self):
        with self.server() as (url, received):
            with mock.patch.dict('os.environ', {'http_proxy': 'http://127.0.0.1:1',
                                                'HTTP_PROXY': 'http://127.0.0.1:1', 'no_proxy': ''}):
                hr.send_alertmanager_notice(url, '#23 queued')
        self.assertEqual(len(received), 1)

    def test_url_contract_rejects_off_host_and_wrong_route(self):
        urls = ('http://example.invalid/api/v2/alerts', 'https://localhost/api/v2/alerts',
                'http://127.0.0.1:21093/api/v2/status', 'http://localhost/api/v2/alerts?query=1',
                'http://localhost:99999/api/v2/alerts', 'http://localhost/api/v2/alerts#fragment')
        for url in urls:
            with self.subTest(url=url), self.assertRaises(hr.UsageError):
                hr.check_alertmanager_url(url)

    def test_ntfy_and_alertmanager_are_distinct_mutually_exclusive_modes(self):
        parser = hr.build_parser()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(['poll', '--role', 'workstation', '--notify-url', 'http://localhost/topic',
                               '--notify-alertmanager-url', 'http://localhost/api/v2/alerts'])
        with self.assertRaises(hr.UsageError):
            hr.check_notify_url('http://localhost/api/v2/alerts')
        self.assertEqual(hr.check_notify_url('http://localhost/topic'), 'http://localhost/topic')

    def test_runtime_copy_can_select_the_live_role_repository(self):
        root = Path('/synthetic/stack')
        with mock.patch.object(hr, 'load_roles', return_value={}) as roles, \
                mock.patch.object(hr, 'cmd_poll', return_value=0) as poll:
            result = hr.main(['poll', '--role', 'workstation', '--stack-root', str(root)])
        self.assertEqual(result, 0)
        roles.assert_called_once_with(root)
        self.assertEqual(poll.call_args.args[1]['gh'].cwd, root)

    def test_poll_dispatches_a_changed_event_to_only_the_selected_transport(self):
        event = {'number': 23, 'state': 'queued', 'event': 'state', 'requesting_host': 'fixture-host',
                 'task_class': 'model qualification', 'trusted': True}
        args = SimpleNamespace(role='workstation', state_file='/synthetic/state.json', notify_url=None,
                               notify_alertmanager_url='http://127.0.0.1:21093/api/v2/alerts')
        ntfy, alerts = mock.Mock(), mock.Mock()
        context = {'gh': object(), 'roles': {}, 'now': None, 'notify': ntfy, 'notify_alertmanager': alerts}
        report = {'items': [], 'host_id': 'fixture', 'generated_at': '2026-10-06T05:00:00Z',
                  'truncated': False}
        with mock.patch.object(hr, 'role_status', return_value=report), \
                mock.patch.object(hr, 'load_state', return_value={}), \
                mock.patch.object(hr, 'diff_states', return_value=[event]), \
                mock.patch.object(hr, 'write_state'), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            result = hr.cmd_poll(args, context)
        self.assertEqual(result, 0)
        alerts.assert_called_once_with(args.notify_alertmanager_url, hr.notice(event))
        ntfy.assert_not_called()


if __name__ == '__main__':
    unittest.main()
