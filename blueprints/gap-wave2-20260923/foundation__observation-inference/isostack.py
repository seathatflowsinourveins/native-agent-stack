#!/usr/bin/env python3
"""Isolated, loopback-only copy of the local observation stack for bounded checks.

Starts the installed upstream binaries (otelcol-contrib 0.161.0, Prometheus 3.14.0,
Loki 3.7.8, Alertmanager 0.34.1, ntfy 2.28.0) as child processes with freshly
chosen free 127.0.0.1 ports and a private temporary data root. It never talks to
the live ecosystem-* user services, never touches systemd, ~/.config or any live
store, and stops every process it started (see Stack.stop).

The collector configuration is the repository's observability/collector/collector.yaml
with only listener/exporter ports rewritten and the two live-probe pipelines
(metrics/health, metrics/host) removed; every processor definition, including
transform/privacy, is kept byte-identical. Extra overlay files may be merged with
otelcol's native multi --config support.
"""
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOLS = Path(os.environ.get('STACK_TOOLS_ROOT', str(Path.home() / '.local/share/codex-ecosystem/tools')))
BIN = {
    'otelcol': TOOLS / 'otelcol-contrib-0.161.0/otelcol-contrib',
    'prometheus': TOOLS / 'ecosystem-prometheus-3.14.0/prometheus',
    'loki': TOOLS / 'ecosystem-loki-3.7.8/loki-linux-amd64',
    'alertmanager': TOOLS / 'ecosystem-alertmanager-0.34.1/alertmanager',
    'ntfy': TOOLS / 'ecosystem-ntfy-2.28.0/ntfy',
}
LIVE_PORTS = {14317, 14318, 14333, 18888, 18889, 13100, 19095, 19090, 19093, 18080, 13000, 49374}


def free_port():
    while True:
        s = socket.socket()
        s.bind(('127.0.0.1', 0))
        p = s.getsockname()[1]
        s.close()
        if p not in LIVE_PORTS:
            return p


def http(url, body=None, method=None, headers=None, timeout=10, raw=False):
    h = dict(headers or {})
    if body is not None and not isinstance(body, (bytes, bytearray)):
        body = json.dumps(body).encode()
        h.setdefault('Content-Type', 'application/json')
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        if raw:
            return r.status, data
        return r.status, (json.loads(data) if data else None)


def render_collector(dst, ports, loki_url, data_root):
    text = (REPO / 'observability/collector/collector.yaml').read_text()
    repl = [
        ('127.0.0.1:14317', f"127.0.0.1:{ports['otlp_grpc']}"),
        ('127.0.0.1:14318', f"127.0.0.1:{ports['otlp_http']}"),
        ('endpoint: 127.0.0.1:14333', f"endpoint: 127.0.0.1:{ports['col_health']}"),
        ('127.0.0.1:18889', f"127.0.0.1:{ports['col_prom']}"),
        ('port: 18888', f"port: {ports['col_self']}"),
        ('http://127.0.0.1:13100/otlp', loki_url + '/otlp'),
    ]
    for a, b in repl:
        assert text.count(a) == 1, a
        text = text.replace(a, b)
    # Drop the pipelines that probe live services or the host.
    for name in ('metrics/health', 'metrics/host'):
        text, n = re.subn(r'\n    %s:\n(      .*\n){3}' % re.escape(name), '\n', text)
        assert n == 1, name
    dst.write_text(text)
    return text


class Stack:
    def __init__(self, root, components=('otelcol', 'prometheus', 'loki'), overlays=(), log_dir=None,
                 prom_scrape='2s', spool_dir=None, collector_env=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.components = list(components)
        self.overlays = list(overlays)
        self.procs = {}
        self.log_dir = Path(log_dir or self.root / 'logs')
        self.log_dir.mkdir(exist_ok=True)
        self.prom_scrape = prom_scrape
        self.collector_env = dict(collector_env or {})
        self.ports = {k: free_port() for k in (
            'otlp_grpc', 'otlp_http', 'col_health', 'col_prom', 'col_self', 'prom', 'loki', 'loki_grpc', 'am',
            'am_cluster', 'ntfy')}
        self.data = self.root / 'data'
        (self.data / 'collector/queue').mkdir(parents=True, exist_ok=True)
        self.spool = Path(spool_dir) if spool_dir else self.data / 'sdk-receipts'
        self.spool.mkdir(parents=True, exist_ok=True)
        if spool_dir:
            link = self.data / 'sdk-receipts'
            if not link.exists():
                link.symlink_to(self.spool)
        self.cfg = self.root / 'config'
        self.cfg.mkdir(exist_ok=True)
        self.loki_url = f"http://127.0.0.1:{self.ports['loki']}"
        self.prom_url = f"http://127.0.0.1:{self.ports['prom']}"
        self.am_url = f"http://127.0.0.1:{self.ports['am']}"
        self.ntfy_url = f"http://127.0.0.1:{self.ports['ntfy']}"
        self.otlp_http = f"http://127.0.0.1:{self.ports['otlp_http']}"
        self.col_prom_url = f"http://127.0.0.1:{self.ports['col_prom']}"

    # ---------- configuration ----------
    def _write_configs(self):
        render_collector(self.cfg / 'collector.yaml', self.ports, self.loki_url, self.data)
        (self.cfg / 'prometheus.yml').write_text(
            'global:\n  scrape_interval: %s\n  evaluation_interval: %s\nscrape_configs:\n'
            '  - job_name: collector-native\n    honor_labels: true\n    static_configs:\n'
            "      - targets: ['127.0.0.1:%d']\n" % (self.prom_scrape, self.prom_scrape, self.ports['col_prom']))
        loki = (REPO / 'observability/backends/templates/ecosystem-loki.yml.example').read_text()
        loki = loki.replace('@DATA_ROOT@', str(self.data)).replace('http_listen_port: 13100', f"http_listen_port: {self.ports['loki']}")
        loki = loki.replace('grpc_listen_port: 19095', f"grpc_listen_port: {self.ports['loki_grpc']}")
        (self.cfg / 'loki.yml').write_text(loki)
        am = (REPO / 'observability/backends/templates/ecosystem-alertmanager.yml.example').read_text()
        am = am.replace('http://127.0.0.1:18080/', self.ntfy_url + '/')
        (self.cfg / 'alertmanager.yml').write_text(am)
        tdir = self.cfg / 'ntfy-templates'
        tdir.mkdir(exist_ok=True)
        shutil.copy(REPO / 'observability/backends/templates/ecosystem-ntfy-alertmanager.yml.example', tdir / 'alertmanager.yml')
        ntfy = (REPO / 'observability/backends/templates/ecosystem-ntfy.yml.example').read_text()
        ntfy = ntfy.replace('@DATA_ROOT@', str(self.data)).replace('@CONFIG_ROOT@/ecosystem-ntfy-templates', str(tdir))
        ntfy = ntfy.replace('http://127.0.0.1:18080', self.ntfy_url).replace('127.0.0.1:18080', f"127.0.0.1:{self.ports['ntfy']}")
        (self.data / 'ecosystem-ntfy').mkdir(exist_ok=True)
        (self.cfg / 'ntfy.yml').write_text(ntfy)

    def _cmd(self, name):
        d = self.data
        if name == 'otelcol':
            args = [str(BIN['otelcol']), f"--config={self.cfg / 'collector.yaml'}"]
            args += [f'--config={o}' for o in self.overlays]
            return args
        if name == 'prometheus':
            return [str(BIN['prometheus']), f"--config.file={self.cfg / 'prometheus.yml'}",
                    f"--storage.tsdb.path={d / 'prometheus'}", f"--web.listen-address=127.0.0.1:{self.ports['prom']}",
                    '--log.level=warn']
        if name == 'loki':
            return [str(BIN['loki']), f"-config.file={self.cfg / 'loki.yml'}"]
        if name == 'alertmanager':
            return [str(BIN['alertmanager']), f"--config.file={self.cfg / 'alertmanager.yml'}",
                    f"--storage.path={d / 'alertmanager'}", f"--web.listen-address=127.0.0.1:{self.ports['am']}",
                    '--cluster.listen-address=', '--log.level=warn']
        if name == 'ntfy':
            return [str(BIN['ntfy']), 'serve', f"--config={self.cfg / 'ntfy.yml'}"]
        raise KeyError(name)

    def _ready_url(self, name):
        return {
            'otelcol': f"http://127.0.0.1:{self.ports['col_health']}/",
            'prometheus': self.prom_url + '/-/ready',
            'loki': self.loki_url + '/ready',
            'alertmanager': self.am_url + '/-/ready',
            'ntfy': self.ntfy_url + '/v1/health',
        }[name]

    def start_one(self, name, timeout=90):
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(self.root), 'ECOSYSTEM_OBSERVABILITY_DATA': str(self.data)}
        if name == 'otelcol':
            env.update(self.collector_env)
        log = open(self.log_dir / f'{name}.log', 'ab')
        p = subprocess.Popen(self._cmd(name), stdout=log, stderr=subprocess.STDOUT, env=env, cwd=self.root,
                             start_new_session=True)
        self.procs[name] = p
        deadline = time.time() + timeout
        url = self._ready_url(name)
        while time.time() < deadline:
            if p.poll() is not None:
                raise RuntimeError(f'{name} exited {p.returncode}; see {self.log_dir / (name + ".log")}')
            try:
                st, _ = http(url, timeout=2, raw=True)
                if st == 200:
                    return time.time()
            except Exception:
                pass
            time.sleep(0.25)
        raise TimeoutError(name)

    def start(self):
        self._write_configs()
        order = [c for c in ('loki', 'ntfy', 'alertmanager', 'prometheus', 'otelcol') if c in self.components]
        for c in order:
            self.start_one(c)
        return self

    def stop_one(self, name, sig=signal.SIGTERM):
        p = self.procs.pop(name, None)
        if not p:
            return None
        try:
            os.killpg(p.pid, sig)
        except ProcessLookupError:
            pass
        try:
            p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait(timeout=10)
        return p.returncode

    def stop(self):
        for name in list(self.procs)[::-1]:
            self.stop_one(name)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    # ---------- queries ----------
    def prom_query(self, q):
        st, body = http(self.prom_url + '/api/v1/query?' + urllib.parse.urlencode({'query': q}))
        return body['data']['result']

    def prom_federate_text(self):
        st, raw = http(self.prom_url + '/federate?' + urllib.parse.urlencode({'match[]': '{__name__=~".+"}'}), raw=True)
        return raw.decode()

    def prom_metadata_text(self):
        st, raw = http(self.prom_url + '/api/v1/metadata', raw=True)
        return raw.decode()

    def loki_dump(self, start_ns, end_ns, query='{service_name=~".+"}'):
        st, raw = http(self.loki_url + '/loki/api/v1/query_range?' + urllib.parse.urlencode(
            {'query': query, 'start': str(start_ns), 'end': str(end_ns), 'limit': '5000', 'direction': 'forward'}), raw=True)
        return raw.decode()

    def loki_labels_text(self, start_ns, end_ns):
        out = []
        st, body = http(self.loki_url + '/loki/api/v1/labels?' + urllib.parse.urlencode({'start': str(start_ns), 'end': str(end_ns)}))
        out.append(json.dumps(body))
        for lab in body.get('data') or []:
            st, b2 = http(self.loki_url + f'/loki/api/v1/label/{urllib.parse.quote(lab)}/values?' + urllib.parse.urlencode({'start': str(start_ns), 'end': str(end_ns)}))
            out.append(json.dumps(b2))
        return '\n'.join(out)

    def events_text(self):
        p = self.data / 'collector/events.jsonl'
        return p.read_text() if p.exists() else ''
