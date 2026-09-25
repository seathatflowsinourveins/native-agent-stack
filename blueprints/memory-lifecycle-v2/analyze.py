"""Check the v2 lifecycle fixture against blueprints/memory-lifecycle-v2/PREREGISTRATION.md
without treating a protocol error as an empty successful retrieval. Standard library only,
like v1's analyze.py (blueprints/us-equities/memory-lifecycle/analyze.py), whose payload()
shape-check this reuses by attribution.
"""
import json
from pathlib import Path
import sys

EXPECTED_ERRORS_PRE = {'missing_scope', 'invalid_combined_scope', 'invalid_expiry'}
EXPECTED_ERRORS_POST = {'revision_deleted_direct_read'}
PROJECT_WORKSPACE = {'alpha': 'lifecycle-v2', 'beta': 'lifecycle-v2', 'gamma': 'lifecycle-v2',
                     'delta': 'lifecycle-v2-secondary'}
TERM = {
    'alpha': 'Marigoldpixel', 'beta': 'Driftwoodlantern', 'gamma': 'Cinderfoxglove',
    'delta': 'Thistlebronze',
}


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


def protocol_error(response):
    error = response.get('error')
    return error if isinstance(error, dict) and isinstance(error.get('code'), int) else None


def hit_paths(entry):
    return sorted(h['path'] for h in entry.get('hits', []))


def global_hit_paths(entry):
    """global=true responses put their results in `global_hits`, not `hits` (`hits` comes
    back empty `[]`), confirmed by direct observation of a live 2.3.2 response -- this is
    the DIFFERENT, FTS-only response shape the memory_query schema text (PREREGISTRATION.md
    section 3) already documents for cross-project global search."""
    return sorted(h['path'] for h in entry.get('global_hits', []))


def hit_origin(hit):
    """Best-effort extraction of a hit's annotated origin workspace/project. `workspace_name`
    / `project_name` is the confirmed live shape on a `global_hits` entry; the other key
    shapes are kept as a fallback in case a different binary/mode annotates differently, and
    (None, None) -- a real, recordable FAIL against the documented claim -- if none match."""
    for ws_key, pj_key in (('workspace_name', 'project_name'), ('workspace', 'project'),
                           ('workspace_id', 'project_id')):
        if ws_key in hit and pj_key in hit:
            return hit[ws_key], hit[pj_key]
    scope = hit.get('scope')
    if isinstance(scope, dict) and 'workspace' in scope and 'project' in scope:
        return scope['workspace'], scope['project']
    return None, None


def summarize_pre(outcomes):
    if len(outcomes) != 69:
        raise ValueError(f'expected exactly 69 phase-pre native tool calls, got {len(outcomes)}')
    data, errors = {}, {}
    for label, response in outcomes.items():
        if label in EXPECTED_ERRORS_PRE:
            error = protocol_error(response)
            if error is None:
                raise ValueError(f'{label}: expected a native protocol rejection')
            errors[label] = {'code': error['code'], 'message': error['message']}
        else:
            data[label] = payload(response)

    checks = {}
    names = ('alpha', 'beta', 'gamma', 'delta')
    for n in names:
        checks[f'write_{n}_ok'] = 'page_id' in data[f'write_{n}']
        checks[f'{n}_read_matches'] = data[f'{n}_read']['body'] == (
            f'# {n.capitalize()} routing\n{TERM[n]} is a {n} fixture only.\n')
        checks[f'{n}_search_self_one_hit'] = hit_paths(data[f'{n}_search_self']) == ['notes/routing.md']
    for me in names:
        for other in names:
            if me != other:
                checks[f'{me}_search_{other}_zero'] = hit_paths(data[f'{me}_search_{other}']) == []
    checks['missing_scope_error'] = 'missing_scope' in errors
    checks['invalid_combined_scope_error'] = 'invalid_combined_scope' in errors

    checks['scopes_ws1_three_count3'] = len(data['scopes_ws1_three'].get('hits', [])) == 3
    checks['scopes_ws1_three_all_routing'] = hit_paths(data['scopes_ws1_three']) == ['notes/routing.md'] * 3
    checks['scopes_excludes_delta_zero'] = hit_paths(data['scopes_excludes_delta']) == []
    for n in names:
        entry = data[f'global_finds_{n}']
        checks[f'global_finds_{n}_one_hit'] = global_hit_paths(entry) == ['notes/routing.md']
        hits = entry.get('global_hits', [])
        origin = hit_origin(hits[0]) if len(hits) == 1 else (None, None)
        checks[f'global_finds_{n}_origin_annotated'] = origin == (PROJECT_WORKSPACE[n], n)

    checks['ttl_before_expiry_one_hit'] = hit_paths(data['ttl_before_expiry']) == ['notes/ttl-short.md']
    checks['ttl_after_expiry_default_zero'] = hit_paths(data['ttl_after_expiry_default']) == []
    checks['ttl_after_expiry_explicit_one_hit'] = hit_paths(data['ttl_after_expiry_explicit']) == ['notes/ttl-short.md']
    checks['ttl_after_expiry_direct_read_ok'] = 'Emberquokka' in data['ttl_after_expiry_direct_read']['body']
    checks['durable_after_expiry_wait_one_hit'] = hit_paths(data['durable_after_expiry_wait']) == ['notes/durable.md']

    preview, applied = data['sweep_preview'], data['sweep_apply']
    expired_paths = {'notes/expired.md', 'notes/ttl-short.md'}
    checks['sweep_preview_dry_run_true'] = preview['dry_run'] is True
    checks['sweep_preview_expired_set_correct'] = ({e['path'] for e in preview['expired']} == expired_paths
        and all(e['deleted'] is False for e in preview['expired']) and len(preview['expired']) == 2)
    checks['expired_past_after_preview_one_hit'] = hit_paths(data['expired_past_after_preview']) == ['notes/expired.md']
    checks['ttl_after_preview_one_hit'] = hit_paths(data['ttl_after_preview']) == ['notes/ttl-short.md']
    checks['sweep_apply_dry_run_false'] = applied['dry_run'] is False
    checks['sweep_apply_expired_set_correct'] = ({e['path'] for e in applied['expired']} == expired_paths
        and all(e['deleted'] is True for e in applied['expired']) and len(applied['expired']) == 2)
    checks['expired_past_after_sweep_zero'] = hit_paths(data['expired_past_after_sweep']) == []
    checks['ttl_after_sweep_zero'] = hit_paths(data['ttl_after_sweep']) == []
    checks['future_after_sweep_one_hit'] = hit_paths(data['future_after_sweep']) == ['notes/future.md']
    checks['durable_after_sweep_one_hit'] = hit_paths(data['durable_after_sweep']) == ['notes/durable.md']

    checks['write_expired_past_ok'] = 'page_id' in data['write_expired_past']
    checks['expired_past_default_zero'] = hit_paths(data['expired_past_default']) == []
    checks['expired_past_explicit_one_hit'] = hit_paths(data['expired_past_explicit']) == ['notes/expired.md']
    checks['expired_past_direct_read_body_and_pinned'] = ('Palewinterlynx' in data['expired_past_direct_read']['body']
        and data['expired_past_direct_read']['frontmatter']['pinned'] is True)
    checks['write_future_ok'] = 'page_id' in data['write_future']
    checks['future_default_one_hit'] = hit_paths(data['future_default']) == ['notes/future.md']
    checks['invalid_expiry_error'] = 'invalid_expiry' in errors

    old_id, new_id = data['write_old']['page_id'], data['write_new']['page_id']
    checks['write_old_new_distinct_ids'] = old_id != new_id
    checks['old_now_zero'] = hit_paths(data['old_now']) == []
    checks['new_now_one_hit'] = hit_paths(data['new_now']) == ['notes/revision.md']
    checks['old_as_of_matches_old_id_and_fts_active'] = (hit_paths(data['old_as_of']) == ['notes/revision.md']
        and data['old_as_of']['hits'][0]['id'] == old_id and 'fts' in data['old_as_of']['streams_active'])
    checks['new_as_of_zero'] = hit_paths(data['new_as_of']) == []
    checks['delete_revision_true'] = data['delete_revision']['deleted'] is True
    checks['deleted_now_zero'] = hit_paths(data['deleted_now']) == []
    checks['deleted_as_of_zero'] = hit_paths(data['deleted_as_of']) == []
    checks['beta_unaffected_by_alpha'] = data['beta_after_alpha_mutations']['body'] == data['beta_read']['body']

    old2_id, new2_id = data['write_old2']['page_id'], data['write_new2']['page_id']
    checks['write_old2_new2_distinct_ids'] = old2_id != new2_id
    checks['old2_as_of_one_hit_matches_id'] = (hit_paths(data['old2_as_of']) == ['notes/revision2.md']
        and data['old2_as_of']['hits'][0]['id'] == old2_id)
    checks['new2_now_one_hit_matches_id'] = (hit_paths(data['new2_now']) == ['notes/revision2.md']
        and data['new2_now']['hits'][0]['id'] == new2_id)

    status_counts = data['status_pre']['counts']
    checks['status_pre_no_imported_history'] = status_counts['sessions'] == 0 and status_counts['observations'] == 0

    return {'passed': all(checks.values()), 'tool_calls': len(outcomes), 'checks': checks,
            'expected_protocol_rejections': errors,
            'sweep': {'preview_expired': preview['expired'], 'apply_expired': applied['expired'],
                      'native_hard_deleted_counter': applied.get('hard_deleted')},
            'status_counts': status_counts,
            'page_ids': {'old_id': old_id, 'new_id': new_id, 'old2_id': old2_id, 'new2_id': new2_id}}


def summarize_post(outcomes, handoff):
    if len(outcomes) != 16:
        raise ValueError(f'expected exactly 16 phase-post native tool calls, got {len(outcomes)}')
    data, errors = {}, {}
    for label, response in outcomes.items():
        if label in EXPECTED_ERRORS_POST:
            error = protocol_error(response)
            if error is None:
                raise ValueError(f'{label}: expected a native protocol rejection')
            errors[label] = {'code': error['code'], 'message': error['message']}
        else:
            data[label] = payload(response)

    checks = {}
    expected_bodies = handoff['bodies']
    for n in ('alpha', 'beta', 'gamma', 'delta'):
        checks[f'{n}_read_persisted'] = data[f'{n}_read']['body'] == expected_bodies[n]
    checks['durable_persisted'] = hit_paths(data['durable_search']) == ['notes/durable.md']
    checks['old2_as_of_persisted_same_id'] = (hit_paths(data['old2_as_of']) == ['notes/revision2.md']
        and data['old2_as_of']['hits'][0]['id'] == handoff['old2_id'])
    checks['new2_now_persisted_same_id'] = (hit_paths(data['new2_now']) == ['notes/revision2.md']
        and data['new2_now']['hits'][0]['id'] == handoff['new2_id'])
    checks['revision_deletion_persisted_current'] = hit_paths(data['revision_deleted_current']) == []
    checks['revision_deletion_persisted_as_of'] = hit_paths(data['revision_deleted_as_of']) == []
    checks['revision_deleted_direct_read_still_errors'] = 'revision_deleted_direct_read' in errors
    checks['ttl_sweep_persisted'] = hit_paths(data['ttl_short_gone']) == []
    checks['expired_past_sweep_persisted'] = hit_paths(data['expired_past_gone']) == []
    checks['future_persisted'] = hit_paths(data['future_present']) == ['notes/future.md']

    post_counts = data['status_post']['counts']
    pre_counts = handoff['status_pre_counts']
    checks['status_post_no_imported_history'] = post_counts['sessions'] == 0 and post_counts['observations'] == 0
    checks['status_stable_across_restart'] = (post_counts['pages_latest'] == pre_counts['pages_latest']
        and post_counts['pages_all'] == pre_counts['pages_all'])
    checks['post_restart_write_ok'] = 'page_id' in data['post_restart_write_readback']
    checks['post_restart_readback_one_hit'] = hit_paths(data['post_restart_readback_search']) == ['notes/post-restart.md']

    return {'passed': all(checks.values()), 'tool_calls': len(outcomes), 'checks': checks,
            'expected_protocol_rejections': errors,
            'status_counts_post': post_counts, 'status_counts_pre': pre_counts}


if __name__ == '__main__':
    pre = json.loads(Path(sys.argv[1]).read_text())
    post_outcomes = json.loads(Path(sys.argv[2]).read_text())
    handoff = json.loads(Path(sys.argv[3]).read_text())
    pre_result = summarize_pre(pre)
    post_result = summarize_post(post_outcomes, handoff)
    result = {'passed': pre_result['passed'] and post_result['passed'],
              'pre': pre_result, 'post': post_result}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
