"""Check selected synthetic native facts and preserve the failed first attempt."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def audit(receipt, attempts, root=ROOT):
    if receipt['passed'] is not False or receipt['decision'] != 'retain_2.3.1_pending_functional_acceptance':
        raise ValueError('incomplete preflight must not promote the candidate')
    if receipt['checks']['sandbox_network_and_write_guards'] is not False:
        raise ValueError('preserve the failed guard')
    if receipt['native_memory_processes_started'] != 0 or receipt['native_mcp_calls'] != 0:
        raise ValueError('this receipt did not execute native memory')
    if receipt['production_promoted'] or receipt['production_state_opened'] or receipt['model_invocation']:
        raise ValueError('unsupported production or model claim')
    if receipt['signature_assessment']['gatekeeper_accepted'] or receipt['signature_assessment']['overrides_or_signature_changes']:
        raise ValueError('retain the rejected assessment and unchanged protections')
    if receipt['signature_assessment']['integrity_exit'] != 0 or receipt['signature_assessment']['gatekeeper_exit'] != 3:
        raise ValueError('signature integrity and Gatekeeper outcome must remain distinct')
    if not attempts['attempts'] or attempts['attempts'][0]['status'] != 'failed':
        raise ValueError('preserve the failed attempt')
    for name, expected in receipt['frozen_inputs'].items():
        actual = hashlib.sha256((root/name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError('frozen input changed: '+name)
    return {'evidence_consistent': True, 'functional_acceptance': False,
            'production_promotion': False, 'frozen_inputs': len(receipt['frozen_inputs'])}


def audit_functional(receipt, native, oracle, root=ROOT):
    facts = native['facts']
    if len(facts) != 36 or receipt['passed'] is not True or not all(receipt['checks'].values()):
        raise ValueError('full native functional acceptance required')
    if receipt['production_promoted'] or receipt['production_state_opened']:
        raise ValueError('synthetic acceptance cannot establish production qualification')
    if receipt['signature_assessment']['gatekeeper_accepted'] or receipt['signature_assessment']['overrides_or_signature_changes']:
        raise ValueError('retain security assessment and unchanged protections')
    if receipt['os_filesystem_network_confinement'] != 'not established; prior restricted-profile attempt failed':
        raise ValueError('OS confinement was not established')
    for name, expected in receipt['frozen_inputs'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest() != expected:
            raise ValueError('changed frozen input: '+name)
    cleanup = receipt['cleanup']
    if len(cleanup) != 3 or any(x['exit_code'] != 0 or x['forced_termination'] or
        not x['owned_process_exited'] or not x['reader_closed'] for x in cleanup):
        raise ValueError('unclean owned process exit')
    for key in ['baseline_database', 'candidate_database']:
        db = receipt[key]
        if db['integrity'] != 'ok' or not db['v62_present'] or db['missing_page_windows'] != 0 or any(db['forbidden_population'].values()):
            raise ValueError('migration or no-capture/no-embedding evidence failed')

    def find(phase, tool, project='alpha', **args):
        wanted = dict(workspace=oracle['workspace'], project=project, **args)
        found = [f for f in facts if f['phase'] == phase and f['tool'] == tool and f['arguments'] == wanted]
        if len(found) != 1:
            raise ValueError('missing or duplicate native call')
        return found[0]

    def value(fact):
        if 'error' in fact or 'tool_error' in fact or 'value' not in fact:
            raise ValueError('native error is not a successful empty result')
        return fact['value']

    def expect_error(fact, expected):
        error = fact.get('error')
        if not isinstance(error, dict) or error.get('code') != -32603 or expected not in error.get('message', ''):
            raise ValueError('wrong reason for native rejection')

    for phase in ['baseline', 'candidate', 'candidate-restart']:
        alpha = oracle['updated_alpha'] if phase == 'candidate-restart' else oracle['alpha']
        for key, item in [('alpha', alpha), ('beta', oracle['beta'])]:
            path = oracle[key]['path']
            body = value(find(phase, 'memory_read_page', project=key, path=path))['body']
            if body != item['body']:
                raise ValueError('wrong exact scoped body')
            q = value(find(phase, 'memory_query', project=key, query=item['marker'], explain=True))
            if q['hits'] != [{'path': path}] or 'fts' not in q['streams_active']:
                raise ValueError('positive FTS mismatch')
            other = 'beta' if key == 'alpha' else 'alpha'
            q = value(find(phase, 'memory_query', project=other, query=item['marker']))
            if q['hits'] != []:
                raise ValueError('cross-scope retrieval leakage')
            expect_error(find(phase, 'memory_read_page', project=other, path=path),
                         'not found in resolved scope '+oracle['workspace']+'/'+other)
        counts = value(find(phase, 'memory_status'))['counts']
        if counts != {'sessions': 0, 'observations': 0}:
            raise ValueError('capture population appeared')
    for key in ['alpha', 'beta']:
        item = oracle[key]
        if value(find('baseline', 'memory_write_page', project=key, path=item['path'], body=item['body'])) != {'acknowledged': True}:
            raise ValueError('baseline write did not succeed')
    item = oracle['unicode']
    if value(find('candidate', 'memory_write_page', path=item['path'], body=item['body'])) != {'acknowledged': True}:
        raise ValueError('Unicode write failed')
    for phase in ['candidate', 'candidate-restart']:
        if value(find(phase, 'memory_read_page', path=item['path']))['body'] != item['body']:
            raise ValueError('Unicode persistence mismatch')
    if value(find('candidate', 'memory_write_page', path=oracle['alpha']['path'], body=oracle['updated_alpha']['body'])) != {'acknowledged': True}:
        raise ValueError('update write failed')
    expect_error(find('candidate', 'memory_write_page', path=oracle['reserved_path'], body='Synthetic rejected page.\n'),
                 'is reserved by Git')
    q = value(find('candidate-restart', 'memory_query', query=item['marker'], explain=True))
    if q['hits'] != [{'path': item['path']}] or 'fts' not in q['streams_active']:
        raise ValueError('Unicode FTS mismatch')
    if value(find('candidate-restart', 'memory_query', query=oracle['alpha']['marker']))['hits'] != []:
        raise ValueError('superseded marker remains visible')
    return {'evidence_consistent': True, 'functional_acceptance': True,
            'native_tool_calls': len(facts), 'production_promotion': False,
            'os_confinement_established': False}


if __name__ == '__main__':
    first = audit(json.loads((ROOT/'receipt-attempt-1.json').read_text()),
                  json.loads((ROOT/'prior-attempts.json').read_text()))
    current = audit_functional(json.loads((ROOT/'receipt.json').read_text()),
                  json.loads((ROOT/'native-facts.json').read_text()),
                  json.loads((ROOT/'oracle-functional.json').read_text()))
    print(json.dumps({'failed_attempt_preserved': first, 'functional_attempt': current}, indent=2))
