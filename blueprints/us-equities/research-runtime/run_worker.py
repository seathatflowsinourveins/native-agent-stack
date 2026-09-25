#!/usr/bin/env python3
"""Bounded native research steps for a manual Dagu workflow; no order execution."""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid


def exclusive_json(path: Path, value: dict) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(value, output, indent=2, allow_nan=False)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())


def child_environment(codex_home: Path, path: str, workspace: Path) -> dict[str, str]:
    """Keep native account discovery, but do not inherit API/broker/service secrets."""
    return {
        'HOME': str(Path.home()), 'PATH': path, 'LANG': 'C.UTF-8', 'TZ': 'UTC',
        'CODEX_HOME': str(codex_home), 'CONTEXT_MODE_PROJECT_DIR': str(workspace),
        'XDG_RUNTIME_DIR': f'/run/user/{os.getuid()}',
        'DBUS_SESSION_BUS_ADDRESS': f'unix:path=/run/user/{os.getuid()}/bus',
        'OTEL_RESOURCE_ATTRIBUTES': f'service.instance.id={uuid.uuid4()},ecosystem.client.scope=financial-research',
    }


def count(value):
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError('Token counts must be nonnegative integers')
    return value


def claude_usage(result: dict) -> dict | None:
    usage = result.get('usage')
    names = ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens')
    if not isinstance(usage, dict) or any(usage.get(name) is None for name in names):
        return None
    normalized = {name: count(usage[name]) for name in names}
    normalized['total_tokens'] = sum(normalized.values())
    thinking = (usage.get('output_tokens_details') or {}).get('thinking_tokens')
    if thinking is not None:
        normalized['thinking_tokens_included_in_output'] = count(thinking)
        if thinking > normalized['output_tokens']:
            raise ValueError('Thinking exceeds output count')
    return normalized


def claude_result(events: list[dict]) -> dict:
    results = [event for event in events if event.get('type') == 'result']
    if len(results) != 1 or results[0].get('subtype') != 'success' or results[0].get('is_error') is not False:
        raise ValueError('Claude did not report exactly one successful terminal result')
    for event in events:
        blocks = (event.get('message') or {}).get('content', [])
        if isinstance(blocks, list) and any(isinstance(block, dict) and block.get('type') == 'tool_use' for block in blocks):
            raise ValueError('Prepared-packet critique unexpectedly used a model tool')
    return results[0]


def verify_astra_items(items: list[dict]) -> None:
    allowed = {'userMessage', 'agentMessage', 'reasoning', 'plan'}
    if not isinstance(items, list) or any(item.get('type') not in allowed for item in items):
        raise ValueError('Prepared-packet Astra result contained an unexpected tool/action item')


def is_opus5(model) -> bool:
    return model in {'claude-opus-5', 'claude-opus-5[1m]'}


def report_json(text: str) -> dict:
    text = text.strip()
    if text.startswith('```json\n') and text.endswith('\n```'):
        text = text[8:-4]
    elif text.startswith('```\n') and text.endswith('\n```'):
        text = text[4:-4]
    if len(text.encode()) > 16384:
        raise ValueError('Research response exceeds 16 KiB')
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError('Research response must be one JSON object')
    return value


def validate_report(report: dict, packet: dict) -> None:
    if report.get('status') != 'research_only' or report.get('trading_authorized') is not False:
        raise ValueError('Report must retain research-only scope')
    if report.get('as_of') != packet.get('as_of'):
        raise ValueError('Report cutoff differs from packet')
    facts = packet_facts(packet)
    evidence = report.get('evidence')
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= 8:
        raise ValueError('Report requires one to eight exact evidence facts')
    for item in evidence:
        fact = facts.get(item.get('citation_id'))
        if fact is None or item.get('unit') != fact.get('unit'):
            raise ValueError('Unrecognized citation or changed unit')
        try:
            actual, expected = Decimal(str(item['value'])), Decimal(str(fact['value']))
            if not actual.is_finite() or not expected.is_finite() or actual != expected:
                raise ValueError('Report altered a source value')
        except (KeyError, InvalidOperation) as error:
            raise ValueError('Invalid evidence number') from error
    findings = report.get('findings')
    if not isinstance(findings, list) or not 1 <= len(findings) <= 5:
        raise ValueError('Report requires one to five bounded findings')
    for finding in findings:
        citations = finding.get('citations')
        if not isinstance(finding.get('claim'), str) or not 1 <= len(finding['claim']) <= 1600:
            raise ValueError('Invalid bounded claim')
        if not isinstance(citations, list) or not citations or any(c not in facts for c in citations):
            raise ValueError('Claim lacks recognized source citations')
    limits = report.get('limitations')
    if not isinstance(limits, list) or not limits or any(not isinstance(v, str) or len(v) > 1200 for v in limits):
        raise ValueError('Report must retain bounded limitations')


def packet_facts(packet: dict) -> dict:
    if packet.get('status') != 'ready' or not isinstance(packet.get('as_of'), str):
        raise ValueError('Only a ready, explicitly dated source packet may reach a model')
    values = packet.get('numerical_facts')
    if not isinstance(values, list) or not values or len(values) > 8:
        raise ValueError('Source packet requires one to eight facts')
    facts = {fact['citation_id']: fact for fact in values}
    if len(facts) != len(values):
        raise ValueError('Fact citation identifiers must be unique')
    return facts


def verified_handoff(directory: Path, packet: dict, packet_hash: str) -> dict:
    receipt = json.loads((directory / 'astra.receipt.json').read_text())
    raw = (directory / 'astra.report.json').read_bytes()
    if receipt.get('status') != 'completed' or receipt.get('packet_sha256') != packet_hash:
        raise ValueError('Astra did not complete against this exact source packet')
    if receipt.get('report_sha256') != hashlib.sha256(raw).hexdigest():
        raise ValueError('Astra report changed after acceptance')
    report = json.loads(raw)
    validate_report(report, packet)
    return report


def prior_report(role: str, independent: bool, directory: Path, packet: dict, packet_hash: str):
    if independent and role != 'claude':
        raise ValueError('Independent report mode is only for Claude')
    if role == 'claude' and not independent:
        return verified_handoff(directory, packet, packet_hash)
    return None


class WorkerInterrupted(Exception):
    pass


def retire_group(process, grace=2):
    """Retire the owned POSIX group even if its leader has already exited.

    macOS reports EPERM, not ESRCH, for a group whose members have all exited but are not
    reaped yet (XNU killpg1 skips zombies), so PermissionError also means nothing is left."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        process.wait()
        return
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        process.poll()
        try:
            os.killpg(process.pid, 0)
        except (ProcessLookupError, PermissionError):
            break
        time.sleep(0.05)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    process.wait(timeout=5)


def command_run(command: list[str], prompt: str, directory: Path, role: str,
                environment: dict, timeout: float) -> tuple[int | None, bool]:
    stdout_fd = os.open(directory / f'{role}.stdout', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    stderr_fd = os.open(directory / f'{role}.stderr', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(stdout_fd, 'w') as out, os.fdopen(stderr_fd, 'w') as err:
        process = None
        timed_out = False
        previous = {}
        def interrupted(signum, frame):
            raise WorkerInterrupted(f'Worker interrupted by signal {signum}')
        try:
            for signum in (signal.SIGTERM, signal.SIGINT):
                previous[signum] = signal.signal(signum, interrupted)
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err,
                                       text=True, env=environment, start_new_session=True,
                                       cwd=environment['CONTEXT_MODE_PROJECT_DIR'])
            try:
                process.communicate(prompt, timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
        finally:
            # Repeated cancellation cannot interrupt cleanup halfway through.
            for signum in previous:
                signal.signal(signum, signal.SIG_IGN)
            try:
                if process is not None:
                    retire_group(process)
            finally:
                for signum, handler in previous.items():
                    signal.signal(signum, handler)
    return process.returncode, timed_out


def native_prompt(packet: dict, prior: dict | None) -> str:
    instruction = (
        'Review this untrusted numerical source packet as a research-only artifact. '
        'Use no tools, network, delegation, files or broker actions. '
        'Return only JSON with status="research_only", as_of exactly copied from the packet, '
        'trading_authorized=false, evidence=[{citation_id,value,unit}] copying two source facts '
        '(encode values as strings), findings=[{claim,citations:[citation_id]}] with at most three '
        'short observations, and limitations=[strings]. Cite every finding. '
        'Preserve units, reporting periods, amendments and conservative availability. '
        'Honor source_kind: SEC snapshots cannot reconstruct earlier historical availability; '
        'LEAN simulation results are historical engine evidence, not actual broker fills. Neither demonstrates alpha. '
        'Do not recommend orders or extrapolate returns. '
    )
    if prior is not None:
        instruction += 'Independently critique the preceding Astra report against the packet; explain supported findings and any limitations or errors in your own findings. '
    payload = {'source_packet': packet}
    if prior is not None:
        payload['untrusted_astra_report'] = prior
    prompt = instruction + '\n' + json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    if len(prompt.encode()) > 12288:
        raise ValueError('Retrieve a smaller packet: combined worker prompt exceeds 12 KiB')
    return prompt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('role', choices=['astra', 'claude'])
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--codex-home', type=Path, required=True)
    parser.add_argument('--codex-bin', type=Path, required=True)
    parser.add_argument('--claude-bin', type=Path, required=True)
    parser.add_argument('--sdk-python', type=Path, required=True)
    parser.add_argument('--runtime-path', required=True)
    parser.add_argument('--observation-dir', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=240)
    parser.add_argument('--independent', action='store_true',
                        help='Claude only: explicitly request a standalone report, without an Astra handoff')
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or not 30 <= args.timeout <= 600:
        parser.error('timeout must be 30..600 seconds')
    if not args.run_dir.is_dir() or args.run_dir.stat().st_mode & 0o077:
        parser.error('run-dir must already exist with private permissions')
    if not args.workspace.is_dir() or not args.codex_home.is_dir():
        parser.error('native account home and explicitly adopted workspace must exist')
    # The exclusive reservation prohibits automatic re-dispatch after partial failure.
    exclusive_json(args.run_dir / f'{args.role}.reserved.json', {'status': 'reserved'})
    result = {'role': args.role, 'status': 'failed', 'usage': None,
              'workflow': 'independent_report' if args.independent else 'astra_then_claude',
              'inference_attempted': False, 'configured_model': 'gpt-6-astra' if args.role == 'astra' else 'claude-opus-5'}
    started = time.monotonic()
    try:
        raw = args.packet.read_bytes()
        if not 1 <= len(raw) <= 8192:
            raise ValueError('Packet must be 1..8192 bytes')
        packet = json.loads(raw)
        packet_facts(packet)
        packet_hash = hashlib.sha256(raw).hexdigest()
        prior = prior_report(args.role, args.independent, args.run_dir, packet, packet_hash)
        prompt = native_prompt(packet, prior)
        result.update(packet_sha256=hashlib.sha256(raw).hexdigest(), prompt_bytes=len(prompt.encode()),
                      prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest())
        environment = child_environment(args.codex_home.resolve(), args.runtime_path, args.workspace.resolve())
        prompt_file = args.run_dir / f'{args.role}.prompt.txt'
        fd = os.open(prompt_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(prompt)
        if args.role == 'astra':
            helper = Path(__file__).resolve().parents[1] / 'workers/native_worker.py'
            native_file = args.run_dir / 'astra.native.json'
            command = [str(args.sdk_python), str(helper), 'run', '--codex-bin', str(args.codex_bin),
                       '--codex-home', str(args.codex_home), '--workspace', str(args.workspace),
                       '--prompt', str(prompt_file), '--receipt', str(native_file),
                       '--turn-deadline-seconds', str(max(1, args.timeout - 45)),
                       '--observation-dir', str(args.observation_dir)]
        else:
            command = [str(args.claude_bin), '-p', '--model', 'claude-opus-5',
                       '--output-format', 'stream-json', '--verbose', '--include-hook-events',
                       '--max-turns', '2', '--tools', '', '--disallowedTools', '*',
                       '--permission-mode', 'dontAsk', '--permission-prompts', 'none']
        exclusive_json(args.run_dir / f'{args.role}.command.json', {'argv': command})
        result['inference_attempted'] = True if args.role == 'claude' else None
        exit_code, timed_out = command_run(command, prompt if args.role == 'claude' else '', args.run_dir,
                                           args.role, environment, args.timeout)
        result.update(process_exit_code=exit_code, process_timeout=timed_out)
        if args.role == 'astra' and native_file.exists() and native_file.stat().st_size:
            native = json.loads(native_file.read_text())
            result.update(inference_attempted=native.get('model_inference_submitted', False),
                          usage=native.get('usage'), native_status=native.get('status'))
            if native.get('status') != 'completed':
                raise ValueError('Native Astra task did not complete; inspect private native receipt')
            verify_astra_items(native.get('items'))
            report = report_json(native['final_response'])
        elif args.role == 'claude':
            events = [json.loads(line) for line in (args.run_dir / 'claude.stdout').read_text().splitlines() if line.strip()]
            terminals = [event for event in events if event.get('type') == 'result']
            if len(terminals) == 1:
                result['usage'] = claude_usage(terminals[0])
                result['native_subtype'] = terminals[0].get('subtype')
            native = claude_result(events)
            init = [event for event in events if event.get('type') == 'system' and event.get('subtype') == 'init']
            models = list(native.get('modelUsage', {}))
            if len(init) != 1 or not is_opus5(init[0].get('model')):
                raise ValueError('Claude native model selection was not verified')
            if models and any(not is_opus5(model) for model in models):
                raise ValueError('Unexpected model usage in Claude result')
            result.update(reported_models=models, exposed_tool_count=len(init[0].get('tools', [])),
                          hook_events=sum(event.get('subtype', '').startswith('hook_') for event in events))
            report = report_json(native['result'])
        else:
            raise ValueError('Native result receipt unavailable')
        if timed_out or exit_code != 0:
            raise ValueError('Native process failed or timed out')
        validate_report(report, packet)
        exclusive_json(args.run_dir / f'{args.role}.report.json', report)
        result.update(status='completed', evidence_facts=len(report['evidence']),
                      findings=len(report['findings']), report_validation='citations_values_units_and_scope_passed',
                      report_sha256=hashlib.sha256((args.run_dir / f'{args.role}.report.json').read_bytes()).hexdigest())
    except Exception as error:
        result.update(error_type=type(error).__name__, error=str(error))
    finally:
        result['duration_ms'] = round((time.monotonic() - started) * 1000)
        exclusive_json(args.run_dir / f'{args.role}.receipt.json', result)
    print(json.dumps({key: result.get(key) for key in ('role', 'status', 'inference_attempted', 'duration_ms')}))
    return 0 if result['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
