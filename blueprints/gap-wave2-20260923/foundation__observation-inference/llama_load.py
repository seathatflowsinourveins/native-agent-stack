#!/usr/bin/env python3
"""llama.cpp route: --parallel 4 concurrency across several fixtures, SIGKILL mid-load, restart and recovery.

Uses the pinned runtime (b11057 CUDA 13.3, llama-server sha256 7740775d...) and model
(ggml-org/Qwen3.8-27B-GGUF@efbb3b1f, Qwen3.8-27B-Q4_K_M.gguf sha256 c600de03...) from the frozen
plan in blueprints/convergence-practice/gpu-inference/plan.json, keeping its partial-offload profile
(32 GPU layers, batch/ubatch 128, 8 threads, --fit off, no web UI/agent tools) except
--parallel 4 and --ctx-size 8192 (2048 per slot). Loopback only, private cache dir, owned
process only. Admission requires >= 16384 MiB free device memory (plan admission_free_mib); a
sampler kills only the owned server if free memory drops below 3072 MiB (plan minimum_free_mib).
Requests use temperature 0 / top_k 1, thinking disabled, max_tokens capped (concurrency and
recovery are measured here, not answer quality).
"""
import argparse
import concurrent.futures as cf
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import isostack  # noqa: E402

REPO = isostack.REPO
LANE = Path.home() / '.cache/gap-wave2-20260923/observation-inference/llama-b11057'
FIXTURES = {
    'planner-repair': (REPO / 'blueprints/convergence-practice/gpu-inference/prompt.txt').read_text(),
    'fib': 'Write a Python function fib(n) that returns the nth Fibonacci number iteratively. Code only.',
    'primes': 'List the first five prime numbers separated by commas.',
    'summary': 'In one sentence, explain what a topological sort of a dependency graph is.',
}


def gpu_free():
    out = subprocess.run(['nvidia-smi', '--query-gpu=memory.free,memory.used,memory.total', '--format=csv,noheader,nounits'],
                         capture_output=True, text=True).stdout.strip().split(',')
    return {'free_mib': int(out[0]), 'used_mib': int(out[1]), 'total_mib': int(out[2])}


class Server:
    def __init__(self, port, log, ctx, parallel):
        self.port, self.log, self.ctx, self.parallel, self.p = port, log, ctx, parallel, None

    def start(self):
        rt = LANE / 'runtime'
        cmd = [str(rt / 'llama-b11057/llama-server'), '--model', str(LANE / 'dl/Qwen3.8-27B-Q4_K_M.gguf'),
               '--alias', 'local-qwen38-frozen', '--host', '127.0.0.1', '--port', str(self.port),
               '--ctx-size', str(self.ctx), '--parallel', str(self.parallel), '--n-gpu-layers', '32',
               '--batch-size', '128', '--ubatch-size', '128', '--threads', '8', '--n-predict', '1536',
               '--fit', 'off', '--no-webui', '--no-agent', '--jinja', '--perf']
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(LANE), 'CUDA_VISIBLE_DEVICES': '0',
               'LD_LIBRARY_PATH': str(rt / 'cudart-llama-b11057-bin-ubuntu-cuda-13.3-x64')}
        self.t_start = time.monotonic()
        self.p = subprocess.Popen(cmd, stdout=open(self.log, 'ab'), stderr=subprocess.STDOUT, env=env, start_new_session=True)
        return cmd

    def wait_healthy(self, timeout=180):
        t = time.monotonic()
        while time.monotonic() - t < timeout:
            if self.p.poll() is not None:
                return None
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{self.port}/health', timeout=2) as r:
                    if r.status == 200:
                        return round(time.monotonic() - self.t_start, 3)
            except Exception:
                pass
            time.sleep(0.2)
        return None

    def kill(self, sig=signal.SIGKILL):
        if self.p and self.p.poll() is None:
            os.killpg(self.p.pid, sig)
        if self.p:
            try:
                self.p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(self.p.pid, signal.SIGKILL)
                self.p.wait(timeout=10)
            return self.p.returncode


def request(port, fixture, max_tokens, timeout):
    body = {'model': 'local-qwen38-frozen', 'messages': [{'role': 'user', 'content': FIXTURES[fixture]}],
            'temperature': 0.0, 'top_p': 1.0, 'top_k': 1, 'seed': 0, 'max_tokens': max_tokens,
            'chat_template_kwargs': {'enable_thinking': False}}
    t = time.monotonic()
    try:
        st, r = isostack.http(f'http://127.0.0.1:{port}/v1/chat/completions', body, timeout=timeout)
        u = r.get('usage') or {}
        txt = (r['choices'][0]['message'].get('content') or '')
        return {'fixture': fixture, 'ok': st == 200 and bool(txt.strip()), 'http': st, 'latency_s': round(time.monotonic() - t, 3),
                'completion_tokens': u.get('completion_tokens'), 'prompt_tokens': u.get('prompt_tokens'),
                'finish_reason': r['choices'][0].get('finish_reason'), 't_end': time.monotonic()}
    except Exception as e:
        return {'fixture': fixture, 'ok': False, 'error': type(e).__name__, 'detail': str(e)[:160],
                'latency_s': round(time.monotonic() - t, 3), 't_end': time.monotonic()}


def batch(port, fixtures, concurrency, max_tokens, timeout, kill_after=None, server=None):
    out, killed = [], {}
    with cf.ThreadPoolExecutor(concurrency) as ex:
        t0 = time.monotonic()
        futs = [ex.submit(request, port, f, max_tokens, timeout) for f in fixtures]
        if kill_after is not None:
            time.sleep(kill_after)
            killed['at_s'] = round(time.monotonic() - t0, 3)
            killed['done_before_kill'] = sum(1 for f in futs if f.done())
            killed['t_kill'] = time.monotonic()
            killed['exit'] = server.kill(signal.SIGKILL)
        for f in futs:
            out.append(f.result())
        wall = round(time.monotonic() - t0, 3)
    for r in out:
        r.pop('t_end', None)
    ok = [r for r in out if r['ok']]
    return {'requests': len(out), 'ok': len(ok), 'failed': len(out) - len(ok), 'success_rate': round(len(ok) / len(out), 3),
            'wall_s': wall, 'latency_ok_s': sorted(r['latency_s'] for r in ok),
            'completion_tokens_ok': sum(r.get('completion_tokens') or 0 for r in ok),
            'errors': sorted({r.get('error', '') for r in out if not r['ok']}), 'rows': out}, killed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True)
    ap.add_argument('--max-tokens', type=int, default=32)
    ap.add_argument('--ctx', type=int, default=8192)
    ap.add_argument('--parallel', type=int, default=4)
    a = ap.parse_args()
    root = LANE / ('run-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    root.mkdir()
    R = {'started_at': datetime.now(timezone.utc).isoformat(), 'profile': {'parallel': a.parallel, 'ctx': a.ctx, 'max_tokens': a.max_tokens},
         'fixtures': sorted(FIXTURES), 'gpu_before': gpu_free()}
    if R['gpu_before']['free_mib'] < 16384:
        R['status'] = 'not_admitted_insufficient_free_device_memory'
        Path(a.out).write_text(json.dumps(R, indent=2) + '\n')
        print(json.dumps(R))
        return 3
    port = isostack.free_port()
    srv = Server(port, root / 'server.log', a.ctx, a.parallel)
    samples, stop, guard = [], threading.Event(), []

    def sampler():
        while not stop.is_set():
            g = gpu_free()
            samples.append(g)
            if g['free_mib'] < 3072 and srv.p and srv.p.poll() is None:
                guard.append({'t': datetime.now(timezone.utc).isoformat(), **g})
                srv.kill(signal.SIGKILL)
            time.sleep(1)
    th = threading.Thread(target=sampler, daemon=True)
    th.start()
    fx = list(FIXTURES)
    try:
        R['command'] = [x.replace(str(Path.home()), '$HOME') for x in srv.start()]
        R['cold_start_healthy_s'] = srv.wait_healthy()
        if R['cold_start_healthy_s'] is None:
            raise RuntimeError('server did not become healthy')
        # Phase 1: 12 requests over 4 fixtures, 8 client threads (> 4 slots, so queueing is exercised)
        R['phase1_concurrent'], _ = batch(port, fx * 3, 8, a.max_tokens, 400)
        # Phase 2: 8 requests in flight, SIGKILL after 8 s
        R['phase2_kill_midload'], killed = batch(port, fx * 2, 8, a.max_tokens, 400, kill_after=8.0, server=srv)
        R['phase2_kill_midload']['kill'] = {k: v for k, v in killed.items() if k != 't_kill'}
        # Restart and recovery
        t_k = killed['t_kill']
        srv.start()
        R['restart_healthy_after_start_s'] = srv.wait_healthy()
        first = request(port, 'primes', a.max_tokens, 400)
        first.pop('t_end', None)
        R['restart_first_request'] = first
        R['recovery_kill_to_first_success_s'] = round(time.monotonic() - t_k, 3) if first['ok'] else None
        # Phase 3: 8 requests after restart
        R['phase3_after_restart'], _ = batch(port, fx * 2, 8, a.max_tokens, 400)
        R['server_exit_final'] = srv.kill(signal.SIGTERM)
    except Exception as e:
        R['error'] = f'{type(e).__name__}: {e}'
    finally:
        srv.kill(signal.SIGKILL)
        stop.set()
        th.join(timeout=5)
        R['gpu_after'] = gpu_free()
        R['gpu_min_free_mib'] = min((s['free_mib'] for s in samples), default=None)
        R['gpu_max_used_mib'] = max((s['used_mib'] for s in samples), default=None)
        R['memory_guard_events'] = guard
        R['stopped_at'] = datetime.now(timezone.utc).isoformat()
        log = (root / 'server.log').read_text(errors='replace')
        R['server_log_signals'] = {k: log.count(k) for k in ('offloaded', 'CUDA0', 'error', 'slot launch_slot_', 'all slots are idle')}
        R['server_log_offload_lines'] = [l.strip()[:200] for l in log.splitlines() if 'offloaded' in l or 'model buffer size' in l][:8]
    Path(a.out).write_text(json.dumps(R, indent=2) + '\n')
    print(json.dumps({k: R.get(k) for k in ('cold_start_healthy_s', 'restart_healthy_after_start_s', 'recovery_kill_to_first_success_s', 'error')}))
    for ph in ('phase1_concurrent', 'phase2_kill_midload', 'phase3_after_restart'):
        if ph in R:
            print(ph, {k: R[ph][k] for k in ('requests', 'ok', 'failed', 'success_rate', 'wall_s', 'errors')})
    return 0 if 'error' not in R else 1


if __name__ == '__main__':
    sys.exit(main())
