"""Regression tests for blueprints/memory-lifecycle-v2 (foundation lane).

The retained native responses of the 2026-09-26 rerun must pass and must reproduce the
verdicts recorded at run time. Every mutation below is a discriminating control: the
2026-09-26 cross-family review showed that the 2026-09-25 analyzer passed its first four,
and each must now fail or raise. per_check_mutations() adds one control for each of the
82 + 19 checks, so no check can pass vacuously.

The later tests keep the published files consistent with what produced them: the results
file must equal what assemble_results.py builds from the retained evidence (including failed
attempts), every retained upstream and history file must be bound to its private source or
otherwise accounted for, and the dashboard checkpoint that cites the results must not
predate them. The upstream runner must never overwrite an earlier attempt's log or receipt,
the upstream control must fail unless its expected results occurred, and the retained copies
of the upstream scripts as they ran must match the hashes logged when they ran.
"""
import contextlib
import copy
import datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import uuid

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'blueprints/memory-lifecycle-v2'
UPSTREAM = FOLDER / 'upstream-20260926'
HISTORY_DIR = FOLDER / 'history'
AS_RUN = HISTORY_DIR / 'upstream-scripts-as-run-20260926'
# The script that ran the final upstream round and the control, and its output.
DRIVER_SH, DRIVER_LOG = 'upstream-final-round-driver-20260926.sh', 'upstream-final-round-driver-20260926.log'
RUNS = sorted((FOLDER / 'runs-20260926').glob('ai-memory-*/attempt-*'))
HISTORY = sorted((FOLDER / 'runs-20260925').glob('ai-memory-*/attempt-*'))


def load(name, folder=FOLDER):
    """Load a blueprint script under a private name. The scripts put their folder on sys.path
    and `import analyze`; both are undone afterwards so no other test module sees them."""
    spec = importlib.util.spec_from_file_location(f'memory_lifecycle_v2_{Path(name).name}', folder / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    saved_path, saved_analyze = list(sys.path), sys.modules.pop('analyze', None)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = saved_path
        sys.modules.pop('analyze', None)
        if saved_analyze is not None:
            sys.modules['analyze'] = saved_analyze
    return module


analyze = load('analyze')
publish = load('publish')
assemble = load('assemble_results')
NAMES = ('alpha', 'beta', 'gamma', 'delta')
PRE_CHECKS = (
    [f'{label}_rejected_as_expected' for label in (
        'missing_scope', 'invalid_combined_scope', 'invalid_expiry', 'ttl_after_sweep_direct_read',
        'expired_past_after_sweep_direct_read')]
    + ['routing_page_ids_distinct']
    + [f'{kind.format(n=n)}' for n in NAMES
       for kind in ('write_{n}_ok', '{n}_read_matches', '{n}_search_self_own_page')]
    + [f'{a}_search_{b}_zero' for a in NAMES for b in NAMES if a != b]
    + ['scopes_ws1_three_one_page_per_project', 'scopes_ws1_three_all_routing',
       'scopes_ws1_three_hits_carry_own_terms', 'scopes_excludes_delta_zero']
    + [f'global_finds_{n}_{suffix}' for n in NAMES for suffix in ('one_hit', 'origin_annotated', 'own_term')]
    + ['ttl_before_expiry_one_hit', 'ttl_after_expiry_default_zero', 'ttl_after_expiry_explicit_one_hit',
       'ttl_after_expiry_direct_read_ok', 'durable_after_expiry_wait_one_hit',
       'ttl_before_expiry_answered_before_native_expiry', 'ttl_after_expiry_calls_sent_after_native_expiry']
    + ['sweep_preview_dry_run_true', 'sweep_preview_expired_set_correct', 'expired_past_after_preview_one_hit',
       'ttl_after_preview_one_hit', 'sweep_apply_dry_run_false', 'sweep_apply_expired_set_correct',
       'expired_past_after_sweep_zero', 'ttl_after_sweep_zero', 'future_after_sweep_one_hit',
       'durable_after_sweep_one_hit']
    + ['write_expired_past_ok', 'expired_past_default_zero', 'expired_past_explicit_one_hit',
       'expired_past_direct_read_body_and_pinned', 'write_future_ok', 'future_default_one_hit',
       'write_old_new_distinct_ids', 'old_now_zero', 'new_now_one_hit',
       'old_as_of_matches_old_id_and_fts_active', 'new_as_of_zero', 'delete_revision_true',
       'deleted_now_zero', 'deleted_as_of_zero', 'beta_unaffected_by_alpha', 'write_old2_new2_distinct_ids',
       'old2_as_of_one_hit_matches_id', 'new2_now_one_hit_matches_id', 'status_pre_no_imported_history'])
POST_CHECKS = (
    [f'{label}_rejected_as_expected' for label in (
        'revision_deleted_direct_read', 'ttl_short_direct_read_gone', 'expired_past_direct_read_gone')]
    + [f'{n}_read_persisted' for n in NAMES]
    + ['durable_persisted', 'old2_as_of_persisted_same_id', 'new2_now_persisted_same_id',
       'revision_deletion_persisted_current', 'revision_deletion_persisted_as_of', 'ttl_sweep_persisted',
       'expired_past_sweep_persisted', 'future_persisted', 'status_post_no_imported_history',
       'status_stable_across_restart', 'post_restart_write_ok', 'post_restart_readback_one_hit'])


def text_response(value):
    return {'jsonrpc': '2.0', 'id': 0, 'result': {'content': [{'type': 'text', 'text': json.dumps(value)}],
                                                  'isError': False}}


def error_response(code, message):
    return {'jsonrpc': '2.0', 'id': 0, 'error': {'code': code, 'message': message}}


def body(response):
    return json.loads(response['result']['content'][0]['text'])


INTRUDER = {'id': 'fixture-id-intruder', 'path': 'notes/intruder.md', 'title': 'Intruder', 'snippet': 'intruder',
            'rank': 0.0}


def edit(outcomes, label, change):
    """Rewrite one successful response: change() edits its parsed JSON body in place."""
    value = body(outcomes[label])
    change(value)
    outcomes[label] = text_response(value)


def assign(key, new):
    return lambda value: value.__setitem__(key, new)


def no_hits(value):
    value['hits'] = []


def extra_hit(value):
    value['hits'].append(dict(INTRUDER))


def other_id(value):
    value['hits'][0]['id'] = INTRUDER['id']


def drop_expired_past(value):
    value['expired'] = [entry for entry in value['expired'] if entry['path'] != 'notes/expired.md']


def native_expiry(state):
    return next(entry['expired_at'] for entry in body(state['pre']['sweep_preview'])['expired']
                if entry['path'] == 'notes/ttl-short.md')


def per_check_mutations():
    """check -> (phase, mutate(state)) for every one of the 82 + 19 checks. Each mutation is one
    small change to a retained response, per-call instant or handoff value, and it must turn
    that check false; other checks may fail with it. `state` holds the phase outcomes ('pre',
    'post'), the phase-pre 'timeline' and the 'handoff'."""
    table = {}

    def response(phase, check, label, change):
        table[check] = (phase, lambda state: edit(state[phase], label, change))

    def same_id_as(phase, check, label, source):
        table[check] = (phase, lambda state: edit(
            state[phase], label, assign('page_id', body(state[phase][source])['page_id'])))

    def unrelated_error(phase, label):
        table[f'{label}_rejected_as_expected'] = (phase, lambda state: state[phase].__setitem__(
            label, error_response(-32603, 'storage unavailable')))

    for label in analyze.EXPECTED_REJECTIONS_PRE:
        unrelated_error('pre', label)
    for label in analyze.EXPECTED_REJECTIONS_POST:
        unrelated_error('post', label)
    same_id_as('pre', 'routing_page_ids_distinct', 'write_beta', 'write_alpha')
    for n in NAMES:
        response('pre', f'write_{n}_ok', f'write_{n}', assign('page_id', None))
        response('pre', f'{n}_read_matches', f'{n}_read', assign('body', 'edited'))
        response('pre', f'{n}_search_self_own_page', f'{n}_search_self', no_hits)
        for other in NAMES:
            if other != n:
                response('pre', f'{n}_search_{other}_zero', f'{n}_search_{other}', extra_hit)
        response('pre', f'global_finds_{n}_one_hit', f'global_finds_{n}',
                 lambda value: value.update(hits=copy.deepcopy(value['global_hits'])))
        response('pre', f'global_finds_{n}_origin_annotated', f'global_finds_{n}',
                 lambda value: value['global_hits'][0].update(project_name='intruder'))
        response('pre', f'global_finds_{n}_own_term', f'global_finds_{n}',
                 lambda value: value['global_hits'][0].update(snippet='intruder'))
        response('post', f'{n}_read_persisted', f'{n}_read', assign('body', 'edited'))
    response('pre', 'scopes_ws1_three_one_page_per_project', 'scopes_ws1_three',
             lambda value: value.update(hits=[dict(value['hits'][0]) for _hit in value['hits']]))
    response('pre', 'scopes_ws1_three_all_routing', 'scopes_ws1_three',
             lambda value: value['hits'][0].update(path='notes/intruder.md'))
    response('pre', 'scopes_ws1_three_hits_carry_own_terms', 'scopes_ws1_three',
             lambda value: value['hits'][0].update(snippet='intruder'))
    response('pre', 'scopes_excludes_delta_zero', 'scopes_excludes_delta', extra_hit)
    response('pre', 'ttl_before_expiry_one_hit', 'ttl_before_expiry', no_hits)
    response('pre', 'ttl_after_expiry_default_zero', 'ttl_after_expiry_default', extra_hit)
    response('pre', 'ttl_after_expiry_explicit_one_hit', 'ttl_after_expiry_explicit', no_hits)
    response('pre', 'ttl_after_expiry_direct_read_ok', 'ttl_after_expiry_direct_read', assign('body', 'edited'))
    response('pre', 'durable_after_expiry_wait_one_hit', 'durable_after_expiry_wait', no_hits)
    table['ttl_before_expiry_answered_before_native_expiry'] = ('pre', lambda state: state['timeline'][
        'ttl_before_expiry'].update(received_utc=native_expiry(state)))
    table['ttl_after_expiry_calls_sent_after_native_expiry'] = ('pre', lambda state: state['timeline'][
        'ttl_after_expiry_direct_read'].update(sent_utc=native_expiry(state)))
    response('pre', 'sweep_preview_dry_run_true', 'sweep_preview', assign('dry_run', False))
    response('pre', 'sweep_preview_expired_set_correct', 'sweep_preview', drop_expired_past)
    response('pre', 'expired_past_after_preview_one_hit', 'expired_past_after_preview', no_hits)
    response('pre', 'ttl_after_preview_one_hit', 'ttl_after_preview', no_hits)
    response('pre', 'sweep_apply_dry_run_false', 'sweep_apply', assign('dry_run', True))
    response('pre', 'sweep_apply_expired_set_correct', 'sweep_apply', drop_expired_past)
    response('pre', 'expired_past_after_sweep_zero', 'expired_past_after_sweep', extra_hit)
    response('pre', 'ttl_after_sweep_zero', 'ttl_after_sweep', extra_hit)
    response('pre', 'future_after_sweep_one_hit', 'future_after_sweep', no_hits)
    response('pre', 'durable_after_sweep_one_hit', 'durable_after_sweep', no_hits)
    response('pre', 'write_expired_past_ok', 'write_expired_past', assign('page_id', None))
    response('pre', 'expired_past_default_zero', 'expired_past_default', extra_hit)
    response('pre', 'expired_past_explicit_one_hit', 'expired_past_explicit', no_hits)
    response('pre', 'expired_past_direct_read_body_and_pinned', 'expired_past_direct_read',
             lambda value: value['frontmatter'].update(pinned=False))
    response('pre', 'write_future_ok', 'write_future', assign('page_id', None))
    response('pre', 'future_default_one_hit', 'future_default', no_hits)
    same_id_as('pre', 'write_old_new_distinct_ids', 'write_new', 'write_old')
    response('pre', 'old_now_zero', 'old_now', extra_hit)
    response('pre', 'new_now_one_hit', 'new_now', no_hits)
    response('pre', 'old_as_of_matches_old_id_and_fts_active', 'old_as_of', other_id)
    response('pre', 'new_as_of_zero', 'new_as_of', extra_hit)
    response('pre', 'delete_revision_true', 'delete_revision', assign('deleted', False))
    response('pre', 'deleted_now_zero', 'deleted_now', extra_hit)
    response('pre', 'deleted_as_of_zero', 'deleted_as_of', extra_hit)
    response('pre', 'beta_unaffected_by_alpha', 'beta_after_alpha_mutations', assign('body', 'edited'))
    same_id_as('pre', 'write_old2_new2_distinct_ids', 'write_new2', 'write_old2')
    response('pre', 'old2_as_of_one_hit_matches_id', 'old2_as_of', other_id)
    response('pre', 'new2_now_one_hit_matches_id', 'new2_now', other_id)
    response('pre', 'status_pre_no_imported_history', 'status_pre', lambda value: value['counts'].update(sessions=1))
    response('post', 'durable_persisted', 'durable_search', no_hits)
    response('post', 'old2_as_of_persisted_same_id', 'old2_as_of', other_id)
    response('post', 'new2_now_persisted_same_id', 'new2_now', other_id)
    response('post', 'revision_deletion_persisted_current', 'revision_deleted_current', extra_hit)
    response('post', 'revision_deletion_persisted_as_of', 'revision_deleted_as_of', extra_hit)
    response('post', 'ttl_sweep_persisted', 'ttl_short_gone', extra_hit)
    response('post', 'expired_past_sweep_persisted', 'expired_past_gone', extra_hit)
    response('post', 'future_persisted', 'future_present', no_hits)
    response('post', 'status_post_no_imported_history', 'status_post',
             lambda value: value['counts'].update(observations=1))
    response('post', 'status_stable_across_restart', 'status_post',
             lambda value: value['counts'].update(pages_all=value['counts']['pages_all'] + 1))
    response('post', 'post_restart_write_ok', 'post_restart_write_readback', assign('page_id', None))
    response('post', 'post_restart_readback_one_hit', 'post_restart_readback_search', no_hits)
    return table


class RetainedRunTests(unittest.TestCase):
    def test_three_binaries_were_retained(self):
        self.assertEqual([run.parent.name for run in RUNS], ['ai-memory-2.3.2', 'ai-memory-2.4.0', 'ai-memory-2.4.1'])

    def test_retained_native_responses_pass_and_reproduce_recorded_verdicts(self):
        for run in RUNS:
            with self.subTest(run=run.parent.name):
                result = analyze.summarize(run)
                recorded = json.loads((run / 'acceptance.json').read_text())
                self.assertTrue(result['passed'])
                self.assertEqual(result['pre']['checks'], recorded['pre']['checks'])
                self.assertEqual(result['post']['checks'], recorded['post']['checks'])

    def test_check_names_are_the_preregistered_list(self):
        result = analyze.summarize(RUNS[-1])
        self.assertEqual(sorted(result['pre']['checks']), sorted(PRE_CHECKS))
        self.assertEqual(sorted(result['post']['checks']), sorted(POST_CHECKS))
        self.assertEqual((len(PRE_CHECKS), len(POST_CHECKS)), (82, 19))

    def test_publication_manifest_binds_every_retained_file(self):
        for run in RUNS + HISTORY:
            manifest = json.loads((run / 'publication.json').read_text())
            listed = {entry['path'] for entry in manifest['published_files']}
            on_disk = {str(p.relative_to(run)) for p in run.rglob('*') if p.is_file()} - {'publication.json'}
            self.assertEqual(listed, on_disk, run)
            for entry in manifest['published_files']:
                data = (run / entry['path']).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'], entry['path'])


class DiscriminatingControlTests(unittest.TestCase):
    def setUp(self):
        run = RUNS[-1]
        read = lambda relative: json.loads((run / relative).read_text())  # noqa: E731
        self.pre, self.timeline = read('phase-pre/outcomes.json'), read('phase-pre/timeline.json')
        self.post, self.handoff = read('phase-post/outcomes.json'), read('handoff/fixture-state.json')

    def pre_result(self):
        return analyze.summarize_pre(self.pre, self.timeline)

    def post_result(self):
        return analyze.summarize_post(self.post, self.handoff)

    def test_restart_queries_replaced_by_empty_objects_raise(self):
        for label in ('revision_deleted_current', 'revision_deleted_as_of', 'ttl_short_gone', 'expired_past_gone'):
            self.post[label] = text_response({})
        with self.assertRaisesRegex(ValueError, "'hits' is NoneType, not a list"):
            self.post_result()

    def test_non_list_hits_and_pathless_hits_raise(self):
        self.pre['alpha_search_beta'] = text_response({'hits': 'none'})
        with self.assertRaises(ValueError):
            self.pre_result()
        self.setUp()
        self.pre['alpha_search_beta'] = text_response({'hits': [{'id': 'x'}]})
        with self.assertRaises(ValueError):
            self.pre_result()

    def test_global_response_without_global_hits_raises(self):
        self.pre['global_finds_beta'] = text_response({'hits': []})
        with self.assertRaisesRegex(ValueError, 'global_hits'):
            self.pre_result()

    def test_unrelated_error_does_not_satisfy_scope_conflict(self):
        self.pre['invalid_combined_scope'] = error_response(-32603, 'storage unavailable')
        result = self.pre_result()
        self.assertFalse(result['passed'])
        self.assertEqual(result['failed_checks'], ['invalid_combined_scope_rejected_as_expected'])
        self.assertEqual(result['expected_protocol_rejections']['invalid_combined_scope']['message'],
                         'storage unavailable')

    def test_method_not_found_does_not_satisfy_deleted_page_read(self):
        self.post['revision_deleted_direct_read'] = error_response(-32601, 'method not found')
        self.assertEqual(self.post_result()['failed_checks'], ['revision_deleted_direct_read_rejected_as_expected'])

    def test_wrong_code_with_right_message_fails(self):
        self.pre['missing_scope'] = error_response(-32603, "project 'absent' not found in workspace 'lifecycle-v2'")
        self.assertEqual(self.pre_result()['failed_checks'], ['missing_scope_rejected_as_expected'])

    def test_unexpected_success_is_a_failed_check_with_its_result_kept(self):
        self.pre['missing_scope'] = copy.deepcopy(self.pre['alpha_read'])
        result = self.pre_result()
        self.assertEqual(result['failed_checks'], ['missing_scope_rejected_as_expected'])
        self.assertIn('unexpected_success', result['expected_protocol_rejections']['missing_scope'])

    def test_three_copies_of_alpha_fail_the_multi_project_check(self):
        alpha_hit = body(self.pre['alpha_search_self'])['hits'][0]
        self.pre['scopes_ws1_three'] = text_response({'hits': [alpha_hit] * 3})
        self.assertIn('scopes_ws1_three_one_page_per_project', self.pre_result()['failed_checks'])

    def test_another_projects_page_at_the_same_path_fails_self_search(self):
        self.pre['alpha_search_self'] = copy.deepcopy(self.pre['beta_search_self'])
        self.assertEqual(self.pre_result()['failed_checks'], ['alpha_search_self_own_page'])

    def test_misattributed_global_hit_fails(self):
        self.pre['global_finds_beta'] = copy.deepcopy(self.pre['global_finds_alpha'])
        failed = self.pre_result()['failed_checks']
        self.assertIn('global_finds_beta_origin_annotated', failed)
        self.assertIn('global_finds_beta_own_term', failed)

    def test_duplicate_routing_page_ids_fail(self):
        value = body(self.pre['write_beta'])
        value['page_id'] = body(self.pre['write_alpha'])['page_id']
        self.pre['write_beta'] = text_response(value)
        self.assertIn('routing_page_ids_distinct', self.pre_result()['failed_checks'])

    def test_swept_page_still_directly_readable_after_sweep_fails(self):
        self.pre['ttl_after_sweep_direct_read'] = copy.deepcopy(self.pre['ttl_after_expiry_direct_read'])
        self.assertEqual(self.pre_result()['failed_checks'], ['ttl_after_sweep_direct_read_rejected_as_expected'])

    def test_swept_page_directly_readable_after_restart_fails(self):
        self.post['expired_past_direct_read_gone'] = copy.deepcopy(self.post['alpha_read'])
        self.assertEqual(self.post_result()['failed_checks'], ['expired_past_direct_read_gone_rejected_as_expected'])

    def test_ttl_calls_on_the_wrong_side_of_the_native_expiry_fail(self):
        expiry = self.pre_result()['ttl_native_expired_at']
        self.timeline['ttl_after_expiry_default']['sent_utc'] = expiry
        self.assertEqual(self.pre_result()['failed_checks'], ['ttl_after_expiry_calls_sent_after_native_expiry'])
        self.setUp()
        self.timeline['ttl_before_expiry']['received_utc'] = expiry
        self.assertEqual(self.pre_result()['failed_checks'], ['ttl_before_expiry_answered_before_native_expiry'])

    def test_every_check_fails_under_its_own_mutation(self):
        """A discriminating control for each of the 82 + 19 checks on each retained run, not only
        for the repaired rules: the analysis completes, and the targeted check is false."""
        table = per_check_mutations()
        self.assertEqual(sorted(table), sorted(PRE_CHECKS + POST_CHECKS))
        for run in RUNS:
            retained = {name: json.loads((run / relative).read_text()) for name, relative in (
                ('pre', 'phase-pre/outcomes.json'), ('timeline', 'phase-pre/timeline.json'),
                ('post', 'phase-post/outcomes.json'), ('handoff', 'handoff/fixture-state.json'))}
            for check, (phase, mutate) in sorted(table.items()):
                with self.subTest(run=run.parent.name, check=check):
                    state = copy.deepcopy(retained)
                    mutate(state)
                    result = (analyze.summarize_pre(state['pre'], state['timeline']) if phase == 'pre'
                              else analyze.summarize_post(state['post'], state['handoff']))
                    self.assertIs(result['checks'][check], False)
                    self.assertFalse(result['passed'])

    def test_missing_call_and_unexpected_protocol_error_raise(self):
        del self.post['future_present']
        with self.assertRaises(ValueError):
            self.post_result()
        self.setUp()
        self.pre['alpha_search_beta'] = error_response(-32603, 'database unavailable')
        with self.assertRaises(ValueError):
            self.pre_result()


class FailedAttemptRetentionTests(unittest.TestCase):
    def test_uninterpretable_response_is_recorded_as_an_analysis_error(self):
        run_module = load('run')
        source = RUNS[-1]
        umask = os.umask(0o022)
        os.umask(umask)
        self.addCleanup(os.umask, umask)  # run.main() tightens the process umask
        with tempfile.TemporaryDirectory() as scratch:
            scratch = Path(scratch)
            (scratch / 'install').mkdir()
            binary = scratch / 'install' / 'ai-memory'
            binary.write_bytes(b'not a real binary')
            output = scratch / 'attempt'

            def fake_phase(phase, _binary, _script, out, _data, handoff):
                target = out / f'phase-{phase}'
                target.mkdir()
                for name in ('outcomes.json', 'timeline.json'):
                    if (source / f'phase-{phase}' / name).is_file():
                        (target / name).write_text((source / f'phase-{phase}' / name).read_text())
                if phase == 'pre':
                    (handoff / 'fixture-state.json').write_text((source / 'handoff/fixture-state.json').read_text())
                else:
                    outcomes = json.loads((target / 'outcomes.json').read_text())
                    outcomes['ttl_short_gone'] = text_response({})
                    (target / 'outcomes.json').write_text(json.dumps(outcomes))
                return target

            argv = ['run.py', '--binary', str(binary), '--out', str(output)]
            with mock.patch.object(run_module, 'run_phase', fake_phase), mock.patch.object(sys, 'argv', argv), \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    run_module.main()
            acceptance = json.loads((output / 'acceptance.json').read_text())
            state = json.loads((output / 'run.json').read_text())
            self.assertFalse(acceptance['passed'])
            self.assertIn("'hits' is NoneType", acceptance['analysis_error'])
            self.assertEqual((state['stage'], state['passed']), ('complete', False))


class PublicationSanitizerTests(unittest.TestCase):
    def test_aliases_keep_equality_and_distinctness(self):
        aliases = publish.Aliases()
        # UUID-shaped values are generated so none is committed (validate.py PRIVATE_CONTENT).
        first, second = str(uuid.UUID(int=0x01a0da44 << 96 | 1)), str(uuid.UUID(int=0x01a0da44 << 96 | 2))
        text = aliases.apply(f'{first} {second} {first} ' + 'a' * 40)
        self.assertEqual(text, 'fixture-id-1 fixture-id-2 fixture-id-1 fixture-checkpoint-1')
        self.assertEqual(aliases.apply('b' * 64), 'b' * 64)

    def test_run_and_scratch_roots_are_replaced_before_ids(self):
        run_dir, scratch = Path(f'/tmp/x/{uuid.UUID(int=7)}/runs/a'), Path('/tmp/x')
        text = publish.sanitize(f'{run_dir}/data {scratch}/other', run_dir, scratch, publish.Aliases())
        self.assertEqual(text, '<run>/data <scratch>/other')


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def rerecord(run):
    """Write acceptance.json from the attempt's (mutated) files the way run.py does."""
    try:
        acceptance = analyze.summarize(run)
    except Exception as error:  # noqa: BLE001 -- run.py's fail-closed rule
        acceptance = {'passed': False, 'analysis_error': f'{type(error).__name__}: {error}'}
    acceptance['binary_sha256'] = json.loads((run / 'run.json').read_text())['binary_sha256']
    write_json(run / 'acceptance.json', acceptance)
    return acceptance


class ResultsAssemblyTests(unittest.TestCase):
    """assemble_results.py must build the committed results file, list only unchanged tag suites
    as upstream tests, and report every attempt, including the ones that fail or stop early."""

    def scratch_root(self):
        """A blueprint-shaped directory whose runs-20260926/ holds only the attempts a test adds."""
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        root = Path(holder.name)
        for name in ('upstream-20260926', 'history', 'PREREGISTRATION.md', 'exercise.py', 'analyze.py',
                     'run.py', 'publish.py'):
            (root / name).symlink_to(FOLDER / name)
        return root

    def attempt(self, root, number, version='2.4.1'):
        target = root / 'runs-20260926' / f'ai-memory-{version}' / f'attempt-{number}'
        shutil.copytree(FOLDER / 'runs-20260926' / f'ai-memory-{version}' / 'attempt-1', target)
        return target

    def mutate(self, run, phase, label, response):
        outcomes = json.loads((run / f'phase-{phase}/outcomes.json').read_text())
        outcomes[label] = response
        write_json(run / f'phase-{phase}/outcomes.json', outcomes)

    def test_results_file_is_current(self):
        self.assertEqual((FOLDER / 'results-20260926.json').read_text(), assemble.render(assemble.build()),
                         'run blueprints/memory-lifecycle-v2/assemble_results.py')

    def test_upstream_runs_are_only_unchanged_tag_suites(self):
        section = assemble.build()['upstream_verification']
        self.assertEqual(sorted(section['runs']), ['v2.3.2/workspace-all-targets.receipt.json',
                                                   'v2.4.0/workspace-all-targets.receipt.json',
                                                   'v2.4.1/workspace-all-targets.receipt.json',
                                                   'v2.4.1/workspace-doc.receipt.json'])
        for label, run in section['runs'].items():
            with self.subTest(run=label):
                self.assertFalse(run['tracked_files_modified'])
                self.assertTrue(run['runner_matches_as_run_copy'])
                self.assertIn(run['upstream_command'], ('cargo test --workspace --all-targets',
                                                        'cargo test --workspace --doc'))
        controls = section['discriminating_control']
        self.assertEqual(controls['evidence_class'], 'local_integration')
        self.assertEqual(sorted(controls['runs']), sorted(label for label, _expected in assemble.CONTROLS))
        self.assertTrue(all(run['as_expected'] for run in controls['runs'].values()))
        self.assertEqual(section['scripts_as_run']['sha256_logged_when_run_matches'],
                         {'control.py': True, 'run_upstream_tests.py': True, 'setup.sh': None})

    def test_every_attempt_of_a_version_is_reported_in_order(self):
        root = self.scratch_root()
        runs = [self.attempt(root, number) for number in (1, 2, 10)]
        self.mutate(runs[0], 'pre', 'missing_scope', text_response({'page_id': 'unexpected'}))
        rerecord(runs[0])
        results = assemble.build(root)
        self.assertEqual([(a['binary'], a['attempt'], a['passed']) for a in results['attempts']],
                         [('2.4.1', 'attempt-1', False), ('2.4.1', 'attempt-2', True), ('2.4.1', 'attempt-10', True)])
        final = results['binaries']['2.4.1']
        self.assertEqual(final['attempt'], 'attempt-10')
        self.assertEqual(final['earlier_attempts'], ['runs-20260926/ai-memory-2.4.1/attempt-1',
                                                     'runs-20260926/ai-memory-2.4.1/attempt-2'])
        self.assertEqual(results['attempts'][0]['failed_checks']['pre'], ['missing_scope_rejected_as_expected'])
        self.assertTrue(results['attempts'][0]['verdicts_reproduced_from_published_responses'])
        self.assertTrue(results['preregistration']['executed_harness_recorded_by_each_run'])
        self.assertTrue(final['passed'])
        self.assertEqual(results['status'], 'failed')  # the later passes do not erase the failed attempt-1

    def test_unexpected_success_is_recorded_without_a_code(self):
        root = self.scratch_root()
        run = self.attempt(root, 1)
        self.mutate(run, 'post', 'ttl_short_direct_read_gone',
                    copy.deepcopy(json.loads((run / 'phase-post/outcomes.json').read_text())['alpha_read']))
        rerecord(run)
        record = assemble.build(root)['binaries']['2.4.1']
        rejection = record['phase_post']['expected_protocol_rejections']['ttl_short_direct_read_gone']
        self.assertFalse(rejection['meets_bar'])
        self.assertIn('unexpected_success', rejection)
        self.assertNotIn('code', rejection)
        self.assertFalse(record['passed'])

    def test_missing_native_expiry_leaves_the_ttl_timing_unestablished(self):
        root = self.scratch_root()
        run = self.attempt(root, 1)
        preview = json.loads((run / 'phase-pre/outcomes.json').read_text())['sweep_preview']
        body = json.loads(preview['result']['content'][0]['text'])
        body['expired'] = [entry for entry in body['expired'] if entry['path'] != 'notes/ttl-short.md']
        preview['result']['content'][0]['text'] = json.dumps(body)
        self.mutate(run, 'pre', 'sweep_preview', preview)
        rerecord(run)
        results = assemble.build(root)
        ttl = results['binaries']['2.4.1']['ttl_real_time']
        self.assertIsNone(ttl['server_expired_at'])
        self.assertIsNone(ttl['seconds_answered_before_expiry'])
        self.assertIn('ttl_before_expiry_answered_before_native_expiry',
                      results['attempts'][0]['failed_checks']['pre'])
        self.assertEqual(results['status'], 'failed')

    def test_analysis_error_is_reported_and_compared_with_the_run_time_error(self):
        root = self.scratch_root()
        run = self.attempt(root, 1)
        self.mutate(run, 'post', 'ttl_short_gone', text_response({}))
        recorded = rerecord(run)
        self.assertIn("'hits' is NoneType", recorded['analysis_error'])
        record = assemble.build(root)['binaries']['2.4.1']
        self.assertEqual(record['analysis_error'], recorded['analysis_error'])
        self.assertTrue(record['verdicts_reproduced_from_published_responses'])
        self.assertFalse(record['passed'])
        self.assertIsNone(record['phase_post']['checks_total'])
        self.assertEqual(record['phase_post']['tool_calls'], 18)

    def test_attempt_that_stopped_in_phase_pre_is_reported(self):
        root = self.scratch_root()
        run = self.attempt(root, 1)
        shutil.rmtree(run / 'phase-post')
        (run / 'acceptance.json').unlink()
        command = json.loads((run / 'phase-pre/command.json').read_text())
        write_json(run / 'phase-pre/command.json', {**command, 'exit_code': 1})
        state = json.loads((run / 'run.json').read_text())
        write_json(run / 'run.json', {**state, 'stage': 'phase-pre', 'passed': False,
                                      'failure': 'SystemExit: phase pre failed or binary changed on disk'})
        self.attempt(root, 2)
        results = assemble.build(root)
        stopped = results['attempts'][0]
        self.assertEqual((stopped['stage_reached'], stopped['passed']), ('phase-pre', False))
        self.assertIsNone(stopped['verdicts_reproduced_from_published_responses'])
        self.assertEqual(stopped['failed_checks'], {'pre': None, 'post': None})
        self.assertTrue(results['binaries']['2.4.1']['passed'])  # the final attempt passed ...
        self.assertEqual(results['status'], 'failed')  # ... and the stopped first attempt still counts
        self.assertEqual(results['binaries']['2.4.1']['earlier_attempts'], [stopped['evidence_dir']])

    def test_committed_results_pass_on_the_first_attempt_of_each_binary(self):
        results = assemble.build()
        self.assertEqual(results['status'], 'passed')
        self.assertEqual([(a['binary'], a['attempt'], a['passed']) for a in results['attempts']],
                         [('2.3.2', 'attempt-1', True), ('2.4.0', 'attempt-1', True), ('2.4.1', 'attempt-1', True)])
        for version, record in results['binaries'].items():
            with self.subTest(binary=version):
                self.assertEqual(record['earlier_attempts'], [])
                self.assertTrue(record['verdicts_reproduced_from_published_responses'])
                self.assertEqual([(record[p]['tool_calls'], record[p]['checks_passed'], record[p]['checks_total'])
                                  for p in ('phase_pre', 'phase_post')], [(71, 82, 82), (18, 19, 19)])


class UpstreamPublicationTests(unittest.TestCase):
    SCRIPTS = {'control.py', 'publish_upstream.py', 'run_upstream_tests.py', 'setup.sh', 'verify_release.py',
               'verify_rustup_init.py'}

    def test_every_retained_upstream_file_is_bound_to_its_private_source(self):
        manifest = json.loads((UPSTREAM / 'publication.json').read_text())
        listed = {entry['path']: entry for entry in manifest['published_files']}
        on_disk = {p.relative_to(UPSTREAM).as_posix() for p in UPSTREAM.rglob('*') if p.is_file()
                   and '__pycache__' not in p.parts}
        self.assertEqual(set(listed), on_disk - self.SCRIPTS - {'publication.json'})
        for path, entry in listed.items():
            with self.subTest(path=path):
                data = (UPSTREAM / path).read_bytes()
                self.assertEqual((hashlib.sha256(data).hexdigest(), len(data)), (entry['sha256'], entry['bytes']))
                self.assertTrue(entry['transform'])
                if entry['source'] is not None:
                    self.assertTrue(entry['source'].startswith('<scratch>/'))
                    self.assertEqual(entry['changed_by_transform'], entry['source_sha256'] != entry['sha256'])
        self.assertIn('setup.log', listed)
        self.assertTrue(listed['setup.log']['changed_by_transform'])

    def test_retained_logs_match_their_receipts(self):
        for receipt_path in sorted(UPSTREAM.glob('**/*.receipt.json')):
            with self.subTest(receipt=receipt_path.relative_to(UPSTREAM).as_posix()):
                receipt = json.loads(receipt_path.read_text())
                self.assertEqual(hashlib.sha256((receipt_path.parent / receipt['log']).read_bytes()).hexdigest(),
                                 receipt['log_sha256'])

    def test_rustup_verification_is_consistent_with_its_recorded_hashes(self):
        record = json.loads((UPSTREAM / 'rustup-init-verification.json').read_text())
        official = record['official_line'].split()[0]
        self.assertEqual(record['binary_matches_official_archive'], record['binary_sha256'] == official)
        self.assertEqual(record['binary_matches_sidecar'], record['binary_sha256'] == record['sidecar_line'].split()[0])
        self.assertNotEqual(record['control']['sha256'], official)
        self.assertEqual(record['verdict'], 'passed')


FAILING_RUN = ('     Running tests/lifecycle.rs (target/debug/deps/lifecycle-0)\n\nrunning 1 test\n'
               'test ttl_case ... FAILED\n\ntest result: FAILED. 0 passed; 1 failed; 0 ignored; 0 measured; '
               '0 filtered out; finished in 0.01s\n')
PASSING_RUN = FAILING_RUN.replace('... FAILED', '... ok').replace(
    'test result: FAILED. 0 passed; 1 failed', 'test result: ok. 1 passed; 0 failed')
FAILED_KEY = 'tests/lifecycle.rs (target/debug/deps/lifecycle-0) :: ttl_case'


class FakeSandbox:
    """subprocess for run_upstream_tests.py: answers its git and toolchain probes and runs no
    sandbox. 'cargo test' writes the given output to the log stream and returns the given code."""
    DEVNULL, STDOUT, TimeoutExpired = subprocess.DEVNULL, subprocess.STDOUT, subprocess.TimeoutExpired

    def __init__(self, output, returncode):
        self.output, self.returncode, self.cargo_runs = output, returncode, 0

    def run(self, command, **kwargs):
        if command[0] == 'git':
            return subprocess.CompletedProcess(command, 0, stdout='' if 'status' in command else '0' * 40 + '\n')
        if command[-3:-1] == ['sh', '-c']:
            return subprocess.CompletedProcess(command, 0, stdout='rustc 1.95.0\ncargo 1.95.0\n')
        self.cargo_runs += 1
        kwargs['stdout'].write(self.output)
        return subprocess.CompletedProcess(command, self.returncode)


class UpstreamRunnerTests(unittest.TestCase):
    """run_upstream_tests.py never truncates an earlier attempt's log or replaces its receipt."""

    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.scratch, self.out = Path(holder.name) / 'scratch', Path(holder.name) / 'out'
        (self.scratch / 'tags' / 'v2.4.1').mkdir(parents=True)
        (self.scratch / 'rust').mkdir()
        self.runner = load('run_upstream_tests', UPSTREAM)

    def run_once(self, output, returncode, *extra):
        sandbox = FakeSandbox(output, returncode)
        argv = ['run_upstream_tests.py', '--scratch', str(self.scratch), '--tag', 'v2.4.1', '--out', str(self.out),
                *extra]
        with mock.patch.object(self.runner, 'subprocess', sandbox), mock.patch.object(sys, 'argv', argv), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as stopped:
            self.runner.main()
        return stopped.exception.code, sandbox.cargo_runs

    def test_a_rerun_with_the_same_out_and_label_is_refused_and_the_earlier_files_are_kept(self):
        self.assertEqual(self.run_once(FAILING_RUN, 101), (1, 1))
        kept = {path: path.read_bytes() for path in (self.out / 'workspace-all-targets.log',
                                                     self.out / 'workspace-all-targets.receipt.json')}
        self.assertEqual(json.loads(kept[self.out / 'workspace-all-targets.receipt.json'])['failed_tests'],
                         [FAILED_KEY])
        # The preregistered --no-fail-fast follow-up, given the same --out and the default label:
        # refused before the sandbox runs anything, and the first attempt's files stay as they were.
        code, cargo_runs = self.run_once(PASSING_RUN, 0, '--no-fail-fast')
        self.assertNotIn(code, (0, None))
        self.assertIn('exists', str(code))
        self.assertEqual(cargo_runs, 0)
        self.assertEqual({path: path.read_bytes() for path in kept}, kept)
        # Under its own label the follow-up runs, and the first attempt is still untouched.
        self.assertEqual(self.run_once(PASSING_RUN, 0, '--no-fail-fast', '--label', 'no-fail-fast'), (0, 1))
        self.assertEqual({path: path.read_bytes() for path in kept}, kept)
        self.assertEqual(json.loads((self.out / 'no-fail-fast.receipt.json').read_text())['totals']['passed'], 1)

    def test_reparse_prints_the_recomputed_receipt_and_never_rewrites_it(self):
        self.run_once(FAILING_RUN, 101)
        receipt = self.out / 'workspace-all-targets.receipt.json'
        earlier = json.loads(receipt.read_text())
        earlier.update(failed_tests=[], totals={**earlier['totals'], 'failed': 0})  # as an older parser left it
        write_json(receipt, earlier)
        before, printed = receipt.read_bytes(), io.StringIO()
        with mock.patch.object(sys, 'argv', ['run_upstream_tests.py', '--reparse', str(receipt)]), \
                contextlib.redirect_stdout(printed):
            self.runner.main()
        self.assertEqual(receipt.read_bytes(), before)
        recomputed = json.loads(printed.getvalue())
        self.assertEqual((recomputed['failed_tests'], recomputed['totals']['failed']), ([FAILED_KEY], 1))


class FakeRunner:
    """subprocess for control.py: each call stands in for one run_upstream_tests.py run. It
    writes the log and receipt that run would leave and returns the runner's exit status."""

    def __init__(self, outcomes):
        self.outcomes, self.labels = outcomes, []

    def run(self, command, **_kwargs):
        out, label = Path(command[command.index('--out') + 1]), command[command.index('--label') + 1]
        self.labels.append(label)
        passed = self.outcomes[label] == 'pass'
        (out / f'{label}.log').write_text(PASSING_RUN if passed else FAILING_RUN)
        write_json(out / f'{label}.receipt.json', {'exit_code': 0 if passed else 101, 'totals': {
            'passed': int(passed), 'failed': int(not passed), 'ignored': 0, 'test_binaries': 1}})
        return subprocess.CompletedProcess(command, 0 if passed else 1)


EXPECTED_CONTROL = {'control-0-unmodified': 'pass', 'control-1-empty-fragment': 'fail',
                    'control-2-filter-always-true': 'fail', 'control-3-restored': 'pass'}


class UpstreamControlTests(unittest.TestCase):
    """control.py exits nonzero unless it saw pass, fail, fail, pass and restored the file."""

    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.control = load('control', UPSTREAM)
        self.scratch, self.out = Path(holder.name) / 'scratch', Path(holder.name) / 'out'
        self.source = self.scratch / 'tags' / 'v2.4.1' / self.control.TARGET
        self.source.parent.mkdir(parents=True)
        self.source.write_text('use std::fmt;\n\n' + self.control.ORIGINAL + '\n')
        self.original = self.source.read_bytes()

    def run_control(self, outcomes):
        runner = FakeRunner(outcomes)
        argv = ['control.py', '--scratch', str(self.scratch), '--out', str(self.out)]
        with mock.patch.object(self.control, 'subprocess', runner), mock.patch.object(sys, 'argv', argv), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                self.control.main()
                code = 0
            except SystemExit as stop:
                code = stop.code
        return code, runner.labels

    def summary(self):
        return json.loads((self.out / 'control-summary.json').read_text())

    def test_four_failing_runs_exit_nonzero_and_keep_the_summary(self):
        code, labels = self.run_control(dict.fromkeys(EXPECTED_CONTROL, 'fail'))
        self.assertNotIn(code, (0, None))
        self.assertEqual(labels, list(EXPECTED_CONTROL))
        self.assertFalse(self.summary()['as_expected'])
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_mutations_that_survive_exit_nonzero(self):
        code, _labels = self.run_control(dict.fromkeys(EXPECTED_CONTROL, 'pass'))
        self.assertNotIn(code, (0, None))
        self.assertEqual(len(self.summary()['problems']), 2)

    def test_the_expected_sequence_exits_zero_and_restores_the_file(self):
        code, labels = self.run_control(EXPECTED_CONTROL)
        self.assertIn(code, (0, None))
        self.assertEqual(labels, list(EXPECTED_CONTROL))
        summary = self.summary()
        self.assertEqual((summary['as_expected'], summary['problems'], summary['restored_sha256_matches']),
                         (True, [], True))
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_a_failed_restore_is_a_problem_even_when_every_run_was_as_expected(self):
        verdicts = {label: {'pass': 'passed', 'fail': 'failed'}[value] for label, value in EXPECTED_CONTROL.items()}
        self.assertEqual(self.control.problems({'verdicts': verdicts, 'restored_sha256_matches': True}), [])
        self.assertEqual(len(self.control.problems({'verdicts': verdicts, 'restored_sha256_matches': False})), 1)

    def test_existing_output_is_refused_before_the_checkout_is_touched(self):
        self.assertIn(self.run_control(EXPECTED_CONTROL)[0], (0, None))
        before = self.summary()
        code, labels = self.run_control(dict.fromkeys(EXPECTED_CONTROL, 'fail'))
        self.assertNotIn(code, (0, None))
        self.assertEqual(labels, [])
        self.assertEqual((self.summary(), self.source.read_bytes()), (before, self.original))

    def test_the_retained_control_run_meets_this_bar(self):
        retained = json.loads((UPSTREAM / 'control/control-summary.json').read_text())
        verdicts = {label: self.control.verdict(UPSTREAM / 'control', label, code)
                    for label, code in retained['runs'].items()}
        self.assertEqual(verdicts, self.control.EXPECTED)
        self.assertEqual(self.control.problems({'verdicts': verdicts,
                                                'restored_sha256_matches': retained['restored_sha256_matches']}), [])


def comment_lines(path):
    """The leading comment block of a shell script (the shebang included)."""
    lines = path.read_text().splitlines()
    return lines[:next(i for i, line in enumerate(lines) if not line.startswith('#'))]


class UpstreamScriptTests(unittest.TestCase):
    """The runs used the scripts retained under history/upstream-scripts-as-run-20260926/."""

    def test_every_upstream_and_control_receipt_records_the_as_run_runner(self):
        runner = hashlib.sha256((AS_RUN / 'run_upstream_tests.py').read_bytes()).hexdigest()
        receipts = sorted(UPSTREAM.glob('v*/*.receipt.json')) + sorted(UPSTREAM.glob('control/*.receipt.json'))
        self.assertEqual(len(receipts), 8)
        for path in receipts:
            with self.subTest(receipt=path.relative_to(UPSTREAM).as_posix()):
                self.assertEqual(json.loads(path.read_text())['runner_sha256'], runner)

    def test_setup_sh_differs_from_its_as_run_copy_only_in_comments(self):
        def commands(path):
            return [line for line in path.read_text().splitlines() if not line.lstrip().startswith('#')]
        self.assertEqual(commands(UPSTREAM / 'setup.sh'), commands(AS_RUN / 'setup.sh'))

    def test_setup_sh_header_does_not_claim_an_unrecorded_checksum_check(self):
        header = '\n'.join(comment_lines(UPSTREAM / 'setup.sh'))
        self.assertNotRegex(header, r'(?i)verified before')
        self.assertIn('rustup-init-verification.json', header)
        self.assertRegex('\n'.join(comment_lines(AS_RUN / 'setup.sh')), r'checksum verified before this script')


class HistoryPublicationTests(unittest.TestCase):
    """history/publication.json binds each history file copied from a private file to that
    source and declares its substitution; every other history file is accounted for."""

    def setUp(self):
        self.record = json.loads((HISTORY_DIR / 'publication.json').read_text())

    def test_every_history_file_is_accounted_for(self):
        named = [entry['path'] for entry in self.record['published_files']] + list(self.record['other_files'])
        on_disk = [p.relative_to(HISTORY_DIR).as_posix() for p in HISTORY_DIR.rglob('*')
                   if p.is_file() and '__pycache__' not in p.parts and p.name != 'publication.json']
        self.assertEqual(sorted(named), sorted(on_disk))

    def test_each_copy_is_bound_to_its_private_source_and_declares_its_substitution(self):
        root_length = self.record['scratch_root_characters']
        for entry in self.record['published_files']:
            with self.subTest(path=entry['path']):
                data = (HISTORY_DIR / entry['path']).read_bytes()
                self.assertEqual((hashlib.sha256(data).hexdigest(), len(data)), (entry['sha256'], entry['bytes']))
                self.assertTrue(entry['source'].startswith('<scratch>/'))
                self.assertTrue(entry['transform'])
                self.assertEqual(entry['changed_by_transform'], entry['source_sha256'] != entry['sha256'])
                if entry['changed_by_transform']:
                    lines = [n for n, line in enumerate(data.decode().splitlines(), 1) if '<scratch>' in line]
                    self.assertEqual(lines, entry['placeholder_lines'])
                    self.assertEqual(entry['source_bytes'] - entry['bytes'],
                                     data.count(b'<scratch>') * (root_length - len('<scratch>')))
                else:
                    self.assertEqual(entry['source_bytes'], entry['bytes'])

    def test_the_hash_log_and_the_as_run_scripts_are_listed_copies(self):
        changed = {entry['path']: entry['changed_by_transform'] for entry in self.record['published_files']}
        self.assertIs(changed.get('preregistration-sha256-20260925.txt'), True)
        for name in ('control.py', 'run_upstream_tests.py', 'setup.sh'):
            self.assertIs(changed.get(f'upstream-scripts-as-run-20260926/{name}'), False)
        for name in (DRIVER_SH, DRIVER_LOG):  # their paths name the private scratch root
            self.assertIs(changed.get(name), True)

    def test_the_as_run_copies_match_what_was_recorded_when_they_ran(self):
        """The final round's driver logged the runner's and control.py's sha256 when the round
        started, then ran both from those paths; its last summary line is the retained control
        summary. No hash of setup.sh was recorded when it ran, so its entry states the basis:
        the private source was last modified before setup.log's first line."""
        entries = {entry['path']: entry for entry in self.record['published_files']}
        driver = (HISTORY_DIR / DRIVER_SH).read_text()
        log = (HISTORY_DIR / DRIVER_LOG).read_text().splitlines()
        for name in ('run_upstream_tests.py', 'control.py'):
            with self.subTest(script=name):
                entry = entries[f'upstream-scripts-as-run-20260926/{name}']
                self.assertEqual(entry['run_time_sha256']['record'], DRIVER_LOG)
                recorded, path = log[entry['run_time_sha256']['line'] - 1].split()
                self.assertEqual(recorded, hashlib.sha256((AS_RUN / name).read_bytes()).hexdigest())
                self.assertEqual(path, entry['source'])
                self.assertIn(f'{path} --scratch', driver)
        self.assertEqual(next(json.loads(line) for line in log if line.startswith('{"target"')),
                         json.loads((UPSTREAM / 'control/control-summary.json').read_text()))
        setup = entries['upstream-scripts-as-run-20260926/setup.sh']
        self.assertIsNone(setup['run_time_sha256'])
        self.assertTrue(setup['as_run_basis'])
        parse = lambda text: datetime.datetime.fromisoformat(text.replace('Z', '+00:00'))  # noqa: E731
        first_setup_line = (UPSTREAM / 'setup.log').read_text().split(maxsplit=1)[0]
        self.assertLess(parse(setup['source_modified_utc']), parse(first_setup_line))

    def test_the_recovered_preregistrations_carry_the_hashes_the_log_recorded(self):
        log = (HISTORY_DIR / 'preregistration-sha256-20260925.txt').read_text().splitlines()
        digest = lambda name: hashlib.sha256((HISTORY_DIR / name).read_bytes()).hexdigest()  # noqa: E731
        self.assertEqual(log[0].split()[0], digest('PREREGISTRATION-20260925-original.md'))
        self.assertEqual(log[5].split()[0], digest('PREREGISTRATION-20260925-amended.md'))


class HistoryTests(unittest.TestCase):
    def test_recheck_of_the_20260925_responses_matches_its_retained_output(self):
        recheck = load('history/recheck_20260925')
        retained = json.loads((FOLDER / 'history/recheck-20260925.json').read_text())
        self.assertEqual([recheck.recheck(run) for run in HISTORY], retained)
        self.assertEqual([(r['evaluated_checks'], r['passed_checks']) for r in retained], [(95, 95), (95, 95)])

    def test_retained_review_repair_controls_cover_every_listed_control(self):
        self.check_retained_controls('review_repair_controls_20260926', 'review-repair-controls-20260926.txt')

    def test_retained_verification_repair_controls_cover_every_listed_control(self):
        self.check_retained_controls('verification_repair_controls_20260926',
                                     'verification-repair-controls-20260926.txt')

    def check_retained_controls(self, script, output):
        controls = load(f'history/{script}').CONTROLS
        lines = [json.loads(line) for line in (HISTORY_DIR / output).read_text().splitlines()]
        self.assertEqual(lines[0]['baseline_of_all_listed_tests']['exit'], 0)
        self.assertEqual([(line['control'], line['file'], line['tests']) for line in lines[1:-1]],
                         [(label, path, tests) for label, path, _mutate, tests in controls])
        for line in lines[1:-1]:
            with self.subTest(control=line['control']):
                self.assertNotEqual(line['with_defect']['exit'], 0)
                self.assertEqual(line['restored']['exit'], 0)
                self.assertTrue(line['discriminates'])
        self.assertEqual(lines[-1], {'controls': len(controls), 'discriminating': len(controls),
                                     'baseline_passed': True})


TIMESTAMP = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})')


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


class DashboardCheckpointTests(unittest.TestCase):
    def test_checkpoint_is_not_older_than_the_results_it_cites(self):
        state = json.loads((ROOT / 'observability/grand-dashboard/state.json').read_text())
        row = next(row for row in state['gates'] if row['id'] == 'memory-lifecycle-v2')
        if row['evidence_ref'] != 'blueprints/memory-lifecycle-v2/results-20260926.json':
            self.skipTest('the dashboard row cites other evidence')
        parse = lambda text: datetime.datetime.fromisoformat(text.replace('Z', '+00:00'))  # noqa: E731
        results = json.loads((ROOT / row['evidence_ref']).read_text())
        latest = max(parse(stamp) for text in strings(results) for stamp in TIMESTAMP.findall(text))
        self.assertGreaterEqual(parse(state['recorded_at_utc']), latest)


if __name__ == '__main__':
    unittest.main()
