"""Check this specific native fixture without treating errors as empty retrieval."""
import json
from pathlib import Path
import sys

EXPECTED_ERRORS = {'missing_scope', 'invalid_combined_scope', 'invalid_expiry'}
EMPTY = ['alpha_search_beta', 'beta_search_alpha', 'expired_default', 'old_now',
         'new_as_of', 'expired_after_sweep', 'deleted_now', 'deleted_as_of']
ONE = {'expired_explicit': 'notes/expired.md', 'future_default': 'notes/future.md',
       'new_now': 'notes/revision.md', 'old_as_of': 'notes/revision.md',
       'expired_after_preview': 'notes/expired.md', 'future_after_sweep': 'notes/future.md'}


def payload(response):
    if 'error' in response or response.get('result', {}).get('isError') is True:
        raise ValueError('native failure is not a successful empty result')
    content = response['result']['content']
    if len(content) != 1 or content[0]['type'] != 'text':
        raise ValueError('unexpected native content shape')
    value = json.loads(content[0]['text'])
    if not isinstance(value, dict):
        raise ValueError('expected native object')
    return value


def summarize(outcomes):
    if len(outcomes) != 31:
        raise ValueError('expected all 31 native tool calls')
    data = {}
    errors = {}
    for label, response in outcomes.items():
        if label in EXPECTED_ERRORS:
            error = response.get('error')
            if not isinstance(error, dict) or not isinstance(error.get('code'), int):
                raise ValueError(f'{label}: expected native protocol rejection')
            errors[label] = {'code': error['code'], 'message': error['message']}
        else:
            data[label] = payload(response)
    checks = {}
    for label in EMPTY:
        checks[label] = data[label].get('hits') == []
    for label, expected_path in ONE.items():
        checks[label] = [h['path'] for h in data[label]['hits']] == [expected_path]
    checks['explicit_project_bodies'] = (data['alpha_read']['body'] == '# Alpha routing\nCobaltquartz is an alpha fixture only.\n'
        and data['beta_read']['body'] == '# Beta routing\nAmbermeadow is a beta fixture only.\n'
        and data['beta_after_alpha_mutations']['body'] == data['beta_read']['body'])
    checks['expired_direct_read_still_available'] = 'Violetcedar' in data['expired_direct_read']['body']
    checks['expired_is_pinned'] = data['expired_direct_read']['frontmatter']['pinned'] is True
    old_id = data['write_old']['page_id']
    new_id = data['write_new']['page_id']
    checks['as_of_selects_original_version'] = (old_id != new_id and data['old_as_of']['hits'][0]['id'] == old_id
                                               and data['new_now']['hits'][0]['id'] == new_id)
    checks['as_of_fts_active'] = 'fts' in data['old_as_of']['streams_active']
    preview, applied = data['sweep_preview'], data['sweep_apply']
    checks['sweep_preview_preserves_expired'] = (preview['dry_run'] is True
        and [(e['path'], e['deleted']) for e in preview['expired']] == [('notes/expired.md', False)])
    checks['sweep_deletes_expired_pinned'] = (applied['dry_run'] is False
        and [(e['path'], e['deleted']) for e in applied['expired']] == [('notes/expired.md', True)])
    checks['explicit_delete'] = data['delete_revision']['deleted'] is True
    checks['no_imported_observations'] = data['status']['counts']['sessions'] == 0 and data['status']['counts']['observations'] == 0
    return {'passed': all(checks.values()), 'tool_calls': len(outcomes),
            'checks': checks, 'expected_protocol_rejections': errors,
            'retrieval_hit_counts': {label: len(data[label]['hits']) for label in EMPTY + list(ONE)},
            'sweep': {'preview_expired_deleted': preview['expired'][0]['deleted'],
                      'apply_expired_deleted': applied['expired'][0]['deleted'],
                      'native_hard_deleted_counter': applied['hard_deleted']},
            'expired_direct_read_available_before_sweep': checks['expired_direct_read_still_available'],
            'status_counts_native_scope': data['status']['counts']}


if __name__ == '__main__':
    result = summarize(json.loads(Path(sys.argv[1]).read_text()))
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
