"""Check the v2 lifecycle fixture against blueprints/memory-lifecycle-v2/PREREGISTRATION.md
without treating a protocol error, a missing field or a malformed hit list as an empty
successful retrieval. Standard library only, like v1's analyze.py
(blueprints/us-equities/memory-lifecycle/analyze.py), whose payload() shape-check this reuses
by attribution.

Two kinds of failure stay distinct. A response the analyzer cannot interpret -- an
unexpected protocol error, a missing or non-list `hits`/`global_hits`, a hit without a string
`path` -- raises ValueError, so nothing is concluded from it. A well-formed response that
misses its pass bar is a failed check, and its observed value is kept: this includes an
expected rejection that succeeded, or that carried another code or message.
"""
import datetime
import json
from pathlib import Path
import re
import sys

PRE_CALLS, POST_CALLS = 71, 18
WS1, WS2 = 'lifecycle-v2', 'lifecycle-v2-secondary'
PROJECT_WORKSPACE = {'alpha': WS1, 'beta': WS1, 'gamma': WS1, 'delta': WS2}
NAMES = ('alpha', 'beta', 'gamma', 'delta')
TERM = {
    'alpha': 'Marigoldpixel', 'beta': 'Driftwoodlantern', 'gamma': 'Cinderfoxglove',
    'delta': 'Thistlebronze',
}


def missing_page(path):
    return -32603, rf'page {re.escape(path)} not found in resolved scope lifecycle-v2/alpha'


# label -> (JSON-RPC code, full-match pattern for the message). These are the codes and
# message formats of the tested versions' own source (PREREGISTRATION.md section 3): scope
# resolution errors map to invalid_params (-32602), the other rejections to internal_error
# (-32603). A method-not-found (-32601) or any other failure does not satisfy them.
EXPECTED_REJECTIONS_PRE = {
    'missing_scope': (-32602, r"project 'absent' not found in workspace 'lifecycle-v2'"),
    'invalid_combined_scope': (-32603, r'global cannot be combined with workspace/project/scopes'),
    'invalid_expiry': (-32603, r'invalid expires_at in frontmatter for notes/invalid-expiry\.md '
                               r'\(want RFC3339 or YYYY-MM-DD\): not-a-date'),
    'ttl_after_sweep_direct_read': missing_page('notes/ttl-short.md'),
    'expired_past_after_sweep_direct_read': missing_page('notes/expired.md'),
}
EXPECTED_REJECTIONS_POST = {
    'revision_deleted_direct_read': missing_page('notes/revision.md'),
    'ttl_short_direct_read_gone': missing_page('notes/ttl-short.md'),
    'expired_past_direct_read_gone': missing_page('notes/expired.md'),
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


def rejection(response, code, pattern):
    """Return (meets_bar, observed). An unexpected success is a failed check whose
    observed result is kept, not an analysis error."""
    error = response.get('error')
    if not isinstance(error, dict):
        return False, {'unexpected_success': response.get('result')}
    observed = {'code': error.get('code'), 'message': error.get('message')}
    meets = (type(error.get('code')) is int and error['code'] == code
             and isinstance(error.get('message'), str)
             and re.fullmatch(pattern, error['message']) is not None)
    return meets, observed


def hit_list(entry, key='hits'):
    hits = entry.get(key)
    if not isinstance(hits, list):
        raise ValueError(f'malformed native response: {key!r} is {type(hits).__name__}, not a list')
    for hit in hits:
        if not isinstance(hit, dict) or not isinstance(hit.get('path'), str):
            raise ValueError(f'malformed native hit in {key!r}: {hit!r}')
    return hits


def hit_paths(entry):
    return sorted(h['path'] for h in hit_list(entry))


def hit_ids(entry):
    return [h.get('id') for h in hit_list(entry)]


def hit_origin(hit):
    """A `global_hits` entry names its origin as `workspace_name` / `project_name` (the shape
    both 2.3.2 and 2.4.0 returned on 2026-09-25, retained under runs-20260925/). (None, None)
    is a recordable failure against the documented annotation claim."""
    if isinstance(hit.get('workspace_name'), str) and isinstance(hit.get('project_name'), str):
        return hit['workspace_name'], hit['project_name']
    return None, None


def instant(text):
    return datetime.datetime.fromisoformat(text.replace('Z', '+00:00'))


def classify(outcomes, expected_rejections, count, phase):
    if len(outcomes) != count:
        raise ValueError(f'expected exactly {count} phase-{phase} native tool calls, got {len(outcomes)}')
    data, rejections = {}, {}
    for label, response in outcomes.items():
        if label in expected_rejections:
            meets, observed = rejection(response, *expected_rejections[label])
            rejections[label] = {'meets_bar': meets, 'expected_code': expected_rejections[label][0],
                                 'expected_message_pattern': expected_rejections[label][1], **observed}
        else:
            data[label] = payload(response)
    missing = set(expected_rejections) - set(rejections)
    if missing:
        raise ValueError(f'missing expected-rejection calls: {sorted(missing)}')
    return data, rejections


def summarize_pre(outcomes, timeline):
    data, rejections = classify(outcomes, EXPECTED_REJECTIONS_PRE, PRE_CALLS, 'pre')
    checks = {label + '_rejected_as_expected': r['meets_bar'] for label, r in rejections.items()}

    written = {n: data[f'write_{n}'].get('page_id') for n in NAMES}
    project_of = {page_id: n for n, page_id in written.items()}
    checks['routing_page_ids_distinct'] = (all(isinstance(i, str) for i in written.values())
                                           and len(set(written.values())) == len(NAMES))
    for n in NAMES:
        checks[f'write_{n}_ok'] = isinstance(written[n], str)
        checks[f'{n}_read_matches'] = data[f'{n}_read'].get('body') == (
            f'# {n.capitalize()} routing\n{TERM[n]} is a {n} fixture only.\n')
        checks[f'{n}_search_self_own_page'] = (hit_paths(data[f'{n}_search_self']) == ['notes/routing.md']
                                               and hit_ids(data[f'{n}_search_self']) == [written[n]])
    for me in NAMES:
        for other in NAMES:
            if me != other:
                checks[f'{me}_search_{other}_zero'] = hit_paths(data[f'{me}_search_{other}']) == []

    # scopes[] hits carry an id but no scope annotation: each id must be the page written
    # to that explicit (workspace, project), one per named project, with its own term.
    scope_hits = hit_list(data['scopes_ws1_three'])
    origins = [project_of.get(h['id']) if isinstance(h.get('id'), str) else None for h in scope_hits]
    checks['scopes_ws1_three_one_page_per_project'] = (
        checks['routing_page_ids_distinct'] and sorted(map(str, origins)) == ['alpha', 'beta', 'gamma'])
    checks['scopes_ws1_three_all_routing'] = hit_paths(data['scopes_ws1_three']) == ['notes/routing.md'] * 3
    checks['scopes_ws1_three_hits_carry_own_terms'] = bool(scope_hits) and all(
        origin is not None and TERM[origin] in str(hit.get('snippet', ''))
        for origin, hit in zip(origins, scope_hits))
    checks['scopes_excludes_delta_zero'] = hit_paths(data['scopes_excludes_delta']) == []
    for n in NAMES:
        entry = data[f'global_finds_{n}']
        found = hit_list(entry, 'global_hits')
        checks[f'global_finds_{n}_one_hit'] = (hit_list(entry) == []
                                               and [h['path'] for h in found] == ['notes/routing.md'])
        checks[f'global_finds_{n}_origin_annotated'] = (len(found) == 1
                                                        and hit_origin(found[0]) == (PROJECT_WORKSPACE[n], n))
        checks[f'global_finds_{n}_own_term'] = len(found) == 1 and TERM[n] in str(found[0].get('snippet', ''))

    checks['ttl_before_expiry_one_hit'] = hit_paths(data['ttl_before_expiry']) == ['notes/ttl-short.md']
    checks['ttl_after_expiry_default_zero'] = hit_paths(data['ttl_after_expiry_default']) == []
    checks['ttl_after_expiry_explicit_one_hit'] = hit_paths(data['ttl_after_expiry_explicit']) == ['notes/ttl-short.md']
    checks['ttl_after_expiry_direct_read_ok'] = 'Emberquokka' in str(data['ttl_after_expiry_direct_read'].get('body'))
    checks['durable_after_expiry_wait_one_hit'] = hit_paths(data['durable_after_expiry_wait']) == ['notes/durable.md']

    preview, applied = data['sweep_preview'], data['sweep_apply']
    expired_paths = {'notes/expired.md', 'notes/ttl-short.md'}
    checks['sweep_preview_dry_run_true'] = preview.get('dry_run') is True
    checks['sweep_preview_expired_set_correct'] = (
        isinstance(preview.get('expired'), list) and len(preview['expired']) == 2
        and {e.get('path') for e in preview['expired']} == expired_paths
        and all(e.get('deleted') is False for e in preview['expired']))
    checks['expired_past_after_preview_one_hit'] = hit_paths(data['expired_past_after_preview']) == ['notes/expired.md']
    checks['ttl_after_preview_one_hit'] = hit_paths(data['ttl_after_preview']) == ['notes/ttl-short.md']
    checks['sweep_apply_dry_run_false'] = applied.get('dry_run') is False
    checks['sweep_apply_expired_set_correct'] = (
        isinstance(applied.get('expired'), list) and len(applied['expired']) == 2
        and {e.get('path') for e in applied['expired']} == expired_paths
        and all(e.get('deleted') is True for e in applied['expired']))
    checks['expired_past_after_sweep_zero'] = hit_paths(data['expired_past_after_sweep']) == []
    checks['ttl_after_sweep_zero'] = hit_paths(data['ttl_after_sweep']) == []
    checks['future_after_sweep_one_hit'] = hit_paths(data['future_after_sweep']) == ['notes/future.md']
    checks['durable_after_sweep_one_hit'] = hit_paths(data['durable_after_sweep']) == ['notes/durable.md']

    # Real-time TTL ordering against the server's own reported expiry instant.
    native_expiry = [e.get('expired_at') for e in (preview.get('expired') or [])
                     if e.get('path') == 'notes/ttl-short.md']
    expiry = instant(native_expiry[0]) if len(native_expiry) == 1 else None
    checks['ttl_before_expiry_answered_before_native_expiry'] = (
        expiry is not None and instant(timeline['ttl_before_expiry']['received_utc']) < expiry)
    checks['ttl_after_expiry_calls_sent_after_native_expiry'] = expiry is not None and all(
        instant(timeline[label]['sent_utc']) > expiry
        for label in ('ttl_after_expiry_default', 'ttl_after_expiry_explicit', 'ttl_after_expiry_direct_read'))

    checks['write_expired_past_ok'] = isinstance(data['write_expired_past'].get('page_id'), str)
    checks['expired_past_default_zero'] = hit_paths(data['expired_past_default']) == []
    checks['expired_past_explicit_one_hit'] = hit_paths(data['expired_past_explicit']) == ['notes/expired.md']
    checks['expired_past_direct_read_body_and_pinned'] = (
        'Palewinterlynx' in str(data['expired_past_direct_read'].get('body'))
        and (data['expired_past_direct_read'].get('frontmatter') or {}).get('pinned') is True)
    checks['write_future_ok'] = isinstance(data['write_future'].get('page_id'), str)
    checks['future_default_one_hit'] = hit_paths(data['future_default']) == ['notes/future.md']

    old_id, new_id = data['write_old'].get('page_id'), data['write_new'].get('page_id')
    checks['write_old_new_distinct_ids'] = isinstance(old_id, str) and isinstance(new_id, str) and old_id != new_id
    checks['old_now_zero'] = hit_paths(data['old_now']) == []
    checks['new_now_one_hit'] = hit_paths(data['new_now']) == ['notes/revision.md']
    checks['old_as_of_matches_old_id_and_fts_active'] = (
        hit_paths(data['old_as_of']) == ['notes/revision.md'] and hit_ids(data['old_as_of']) == [old_id]
        and 'fts' in (data['old_as_of'].get('streams_active') or []))
    checks['new_as_of_zero'] = hit_paths(data['new_as_of']) == []
    checks['delete_revision_true'] = data['delete_revision'].get('deleted') is True
    checks['deleted_now_zero'] = hit_paths(data['deleted_now']) == []
    checks['deleted_as_of_zero'] = hit_paths(data['deleted_as_of']) == []
    checks['beta_unaffected_by_alpha'] = data['beta_after_alpha_mutations'].get('body') == data['beta_read'].get('body')

    old2_id, new2_id = data['write_old2'].get('page_id'), data['write_new2'].get('page_id')
    checks['write_old2_new2_distinct_ids'] = (isinstance(old2_id, str) and isinstance(new2_id, str)
                                             and old2_id != new2_id)
    checks['old2_as_of_one_hit_matches_id'] = (hit_paths(data['old2_as_of']) == ['notes/revision2.md']
                                               and hit_ids(data['old2_as_of']) == [old2_id])
    checks['new2_now_one_hit_matches_id'] = (hit_paths(data['new2_now']) == ['notes/revision2.md']
                                             and hit_ids(data['new2_now']) == [new2_id])

    status_counts = data['status_pre'].get('counts') or {}
    checks['status_pre_no_imported_history'] = (status_counts.get('sessions') == 0
                                                and status_counts.get('observations') == 0)

    return {'passed': all(checks.values()), 'tool_calls': len(outcomes), 'checks': checks,
            'failed_checks': sorted(k for k, v in checks.items() if not v),
            'expected_protocol_rejections': rejections,
            'sweep': {'preview_expired': preview.get('expired'), 'apply_expired': applied.get('expired'),
                      'native_hard_deleted_counter': applied.get('hard_deleted')},
            'ttl_native_expired_at': native_expiry[0] if len(native_expiry) == 1 else None,
            'status_counts': status_counts,
            'page_ids': {'routing': written, 'old_id': old_id, 'new_id': new_id,
                         'old2_id': old2_id, 'new2_id': new2_id}}


def summarize_post(outcomes, handoff):
    data, rejections = classify(outcomes, EXPECTED_REJECTIONS_POST, POST_CALLS, 'post')
    checks = {label + '_rejected_as_expected': r['meets_bar'] for label, r in rejections.items()}
    expected_bodies = handoff['bodies']
    for n in NAMES:
        checks[f'{n}_read_persisted'] = data[f'{n}_read'].get('body') == expected_bodies[n]
    checks['durable_persisted'] = hit_paths(data['durable_search']) == ['notes/durable.md']
    checks['old2_as_of_persisted_same_id'] = (hit_paths(data['old2_as_of']) == ['notes/revision2.md']
                                              and hit_ids(data['old2_as_of']) == [handoff['old2_id']])
    checks['new2_now_persisted_same_id'] = (hit_paths(data['new2_now']) == ['notes/revision2.md']
                                            and hit_ids(data['new2_now']) == [handoff['new2_id']])
    checks['revision_deletion_persisted_current'] = hit_paths(data['revision_deleted_current']) == []
    checks['revision_deletion_persisted_as_of'] = hit_paths(data['revision_deleted_as_of']) == []
    checks['ttl_sweep_persisted'] = hit_paths(data['ttl_short_gone']) == []
    checks['expired_past_sweep_persisted'] = hit_paths(data['expired_past_gone']) == []
    checks['future_persisted'] = hit_paths(data['future_present']) == ['notes/future.md']

    post_counts = data['status_post'].get('counts') or {}
    pre_counts = handoff['status_pre_counts']
    checks['status_post_no_imported_history'] = (post_counts.get('sessions') == 0
                                                 and post_counts.get('observations') == 0)
    checks['status_stable_across_restart'] = all(
        pre_counts.get(key) is not None and post_counts.get(key) == pre_counts[key]
        for key in ('pages_latest', 'pages_all'))
    checks['post_restart_write_ok'] = isinstance(data['post_restart_write_readback'].get('page_id'), str)
    checks['post_restart_readback_one_hit'] = hit_paths(data['post_restart_readback_search']) == ['notes/post-restart.md']

    return {'passed': all(checks.values()), 'tool_calls': len(outcomes), 'checks': checks,
            'failed_checks': sorted(k for k, v in checks.items() if not v),
            'expected_protocol_rejections': rejections,
            'status_counts_post': post_counts, 'status_counts_pre': pre_counts}


def summarize(run_dir):
    """Analyze one run directory laid out as run.py writes it (and as publish.py retains it)."""
    run_dir = Path(run_dir)
    read = lambda relative: json.loads((run_dir / relative).read_text())  # noqa: E731
    pre = summarize_pre(read('phase-pre/outcomes.json'), read('phase-pre/timeline.json'))
    post = summarize_post(read('phase-post/outcomes.json'), read('handoff/fixture-state.json'))
    return {'passed': pre['passed'] and post['passed'], 'pre': pre, 'post': post}


if __name__ == '__main__':
    result = summarize(sys.argv[1])
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
