#!/usr/bin/env python3
"""Reproduce documentary coverage and screening accounting; never rank quality.

Print the derived ledger; --check compares it with the retained public artifact.
The original reviewer outputs remain unchanged, including their contradictions.
"""
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / 'evidence/artifacts/blind-catalog-convergence-20260921'


def read(name):
    return json.loads((ARTIFACTS / name).read_text())


def norm(value):
    if isinstance(value, dict):
        value = value['repository_url']
    return value.lower().rstrip('/').removesuffix('.git')


def derive():
    compact = read('claude-source-review.json')
    coverage = read('claude-coverage-review.json')
    repair = read('claude-screening-repair.json')
    index = json.loads((ROOT / 'catalogs/us-equities/decision-index.json').read_text())
    identities = {norm(row['repository']) for row in index['records']}
    aliases = {norm('https://github.com/' + k): norm('https://github.com/' + v)
               for k, v in index['aliases'].items()}
    # The sealed merit report used the former owner; retain that URL in each row.
    aliases['https://github.com/robcarver17/pysystemtrade'] = 'https://github.com/pst-group/pysystemtrade'
    def canonical(url):
        return aliases.get(norm(url), norm(url))
    repaired = {}
    for group in repair['repaired']:
        for row in group['dispositions']:
            key = (group['sublayer'], norm(row['repository_url']))
            assert key not in repaired, key
            repaired[key] = row
    fields = ['stars', 'pushed_at', 'license', 'latest_release',
              'has_tests', 'has_ci', 'archived', 'open_issues']
    rows = []
    for group in compact['sublayers']:
        short = {norm(x) for x in group['merit']['shortlist']}
        dropped = {norm(x['repository_url']): x for x in group['merit']['dropped']}
        metadata = {canonical(x['repository_url']): x for x in group['merit']['rows']}
        for candidate in group['merged']:
            url = norm(candidate['repository_url'])
            drop = dropped.get(url)
            reason = drop['why'] if drop else None
            annotation = bool(drop and ('NOT dropped mechanically' in reason or url in short))
            cap = bool(drop and not annotation and any(t in reason.lower() for t in
                       ['stars-desc', 'shortlist cap', '12-slot shortlist']))
            status = ('shortlisted' if url in short else 'eligible_annotation_only' if annotation
                      else 'star_cap_excluded' if cap else 'recorded_rule_exclusion' if drop
                      else 'no_disposition')
            later = repaired.get((group['key'], url))
            assert (later is not None) == (status == 'no_disposition'), (group['key'], url)
            meta = metadata[canonical(url)]
            rows.append({'group': group['key'], 'repository_url': url,
                         'original_status': status, 'original_drop_reason': reason,
                         'shortlist_drop_overlap': url in short and drop is not None,
                         'metadata_missing_keys': [k for k in fields if k not in meta],
                         'metadata_null_fields': [k for k in fields if k in meta and meta[k] is None],
                         'metadata_unknown_fields': [k for k in fields if meta.get(k) == 'unknown'],
                         'original_metadata_repository': meta['repository_url'],
                         'later_repair': later,
                         'canonical_repository': canonical(url),
                         'in_current_identity_index': canonical(url) in identities,
                         'acceptance_effect': 'none; screening is not runtime or quality acceptance'})
    policies = {
        'add-candidate-row': 'covered_by_current_identity_index; consult its typed source pointers; no adoption',
        'schedule-comparison': 'conditional_future_comparison; execute only for a demonstrated requirement under the layer gate',
        'refresh-pin': 'review_required_before_upgrade; retained tested pins remain; supporting locks and dated historical rows are separate',
        'flag-maintenance': 'attributed_source_flag; version age, heuristic fields and score do not establish failure',
        'flag-license': 'check_pinned_terms_for_actual_deployment; GitHub null/NOASSERTION is not absence of terms',
        'no-action': 'no_adoption_change; preserve original claims and coordinator corrections',
    }
    actions = []
    for group in coverage['diffs']:
        for action in group['recommended_catalog_actions']:
            url = canonical(action['repository_url'])
            actions.append({'group': group['sublayer'].split(' ')[0],
                            'repository_url': url, 'action': action['action'],
                            'in_current_identity_index': url in identities,
                            'coordinator_disposition': policies[action['action']],
                            'original_recommendation': action,
                            'corrections_ref': 'docs/claude-blind-adjudication-20260921.md'})
    counts = dict(Counter(x['original_status'] for x in rows))
    assert counts == {'shortlisted': 120, 'recorded_rule_exclusion': 169,
                      'no_disposition': 159, 'star_cap_excluded': 65, 'eligible_annotation_only': 1}
    assert len(repaired) == 159 and not repair['missing']
    assert all(x['in_current_identity_index'] for x in rows + actions)
    return {'schema_version': 1, 'scope': 'Reproducible source-report accounting, not candidate execution or ranking',
            'original_partition': counts,
            'later_repair_counts': dict(Counter(x['disposition'] for x in repaired.values())),
            'metadata_missing_or_null_or_unknown_rows': sum(bool(x['metadata_missing_keys'] or x['metadata_null_fields'] or x['metadata_unknown_fields']) for x in rows),
            'parsed_coverage_counts': {k: sum(len(d[k]) for d in coverage['diffs']) for k in
                ['blind_found_absent_from_catalog', 'catalog_selected_not_surfaced_blind', 'disposition_disagreements', 'recommended_catalog_actions']},
            'actions_by_type': dict(Counter(x['action'] for x in actions)),
            'rows': rows, 'actions': actions}


if __name__ == '__main__':
    result = derive()
    if sys.argv[1:] == ['--check']:
        assert result == read('screening-ledger.json'), 'retained screening ledger is stale'
        print('PASS: 514 original rows, 159 later repairs, 125 action joins; no adoption inferred')
    else:
        assert not sys.argv[1:], 'only --check is supported'
        print(json.dumps(result, indent=2))
