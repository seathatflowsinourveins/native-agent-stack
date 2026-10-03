"""Explicit prospective successor selection; old v2 evidence stays immutable."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

SOURCE = Path(__file__).resolve().parent
REPO = SOURCE.parents[3]
HISTORICAL = SOURCE.parent.parent / 'historical-simulation'
MANIFEST = 'mapping-manifest-six-cases-20261003.json'
PREREGISTRATION = 'PREREGISTRATION-six-cases-20261003.md'
SCHEMA = 'spy-six-case-successor/1'
REVIEW_SCHEMA = 'spy-six-case-harness-review/1'
CASES = ('one_zero', 'one_stress', 'two_zero', 'two_stress', 'adaptive_stress', 'over_limit')
CODE_FILES = ('run.py', 'compare.py', 'convert.py', 'fixture_strategy.py',
              'distribution_module.py', 'cost_models.py', 'margin_policy.py',
              'margin_strategy.py', 'six_bindings.py', 'six_run.py', 'compare_six.py')
LOCAL_FILES = ('mapping-manifest.json', 'mapping-manifest-v2.json', 'tolerances.json',
               'requirements-stress-linux-arm64-py313.lock')
V1_SHA = '43f510494a970d235f27e5676120ee749b45eb6b060cf74f0b768374b8177909'
V2_SHA = '1b821d7ba42ea6121002a26a5082df08ed7a79f9a50b2edc9959503e1088ac67'
PLAN_SHA = '60959a050a3b004abf5346d376930b3b2f563096c725dc96e5427703ea203632'
ORACLE_SHA = '06ec065647abd91a0ca2b13da25dd75c3ccd159a3244a241a3207c58b36f95d9'
TOLERANCES_SHA = 'c8bc72317fb4de83f2b0b7e71888828c7dd15a5a7eb2f60b68f87d54e751c15a'
RUNTIME = {'package': 'nautilus_trader', 'version': '2.0.0rc5',
           'upstream_commit': '1b0a49d2792a9432a3aca3fcb617ce7a630d905e',
           'python_version': '3.13.16',
           'official_image': 'docker.io/library/python@sha256:110e8d1de526341568b8fcdb1773b0d47ad63309df21980c6028803226a2dab0',
           'extension_sha256': {'_libnautilus.cpython-313-aarch64-linux-gnu.so':
                                'd03e4ac01a3675f91a3c7edde999735fefcc89bfb910f1fdaab946ab5e0beed3'}}
NATIVE = {'account_type': 'MARGIN', 'oms_type': 'NETTING', 'margin_init': '0.5',
          'margin_maint': '0.5', 'margin_model': 'StandardMarginModel', 'default_leverage': '2',
          'risk_bypass': False, 'liquidation_enabled': False, 'use_random_ids': False,
          'bar_adaptive_high_low_ordering': False, 'support_contingent_orders': True}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_bindings():
    if digest(HISTORICAL / 'plan.json') != PLAN_SHA or digest(HISTORICAL / 'receipt.json') != ORACLE_SHA:
        raise ValueError('six_frozen_plan_or_oracle_changed')
    old = json.loads((SOURCE / 'mapping-manifest-v2.json').read_text())
    if digest(SOURCE / 'mapping-manifest-v2.json') != V2_SHA:
        raise ValueError('six_inherited_v2_seal_changed')
    return {'plan_sha256': PLAN_SHA, 'oracle_sha256': ORACLE_SHA,
            'tolerances_sha256': TOLERANCES_SHA,
            'input_sha256': old['inputs']['frozen_sha256']}


def case_specs():
    if digest(HISTORICAL / 'plan.json') != PLAN_SHA:
        raise ValueError('six_frozen_plan_changed')
    return {c['id']: c for c in json.loads((HISTORICAL / 'plan.json').read_text())['cases']}


def load_mapping(path, *, source=None):
    source = SOURCE if source is None else Path(source)
    path = Path(path)
    if (path.is_symlink() or not path.is_file() or path.name != MANIFEST
            or path.parent.resolve() != source.resolve() or source.is_symlink()):
        raise ValueError('six_mapping_selection_invalid')
    mapping = json.loads(path.read_text())
    native = mapping.get('native')
    if (not isinstance(native, dict) or any(type(native.get(k)) is not type(v)
                                          for k, v in NATIVE.items())):
        raise ValueError('six_native_configuration_type_changed')
    if (mapping.get('schema_version') != SCHEMA or mapping.get('native') != NATIVE
            or mapping.get('runtime') != RUNTIME or mapping.get('cases') != case_specs()
            or mapping.get('frozen') != frozen_bindings()
            or mapping.get('base') != {'mapping-manifest.json': V1_SHA, 'mapping-manifest-v2.json': V2_SHA}):
        raise ValueError('six_successor_policy_or_frozen_binding_changed')
    seal = mapping.get('source_seal_sha256')
    if not isinstance(seal, dict) or set(seal) != set(CODE_FILES + LOCAL_FILES):
        raise ValueError('six_source_seal_incomplete')
    for name, expected in seal.items():
        p = source / name
        if p.is_symlink() or not p.is_file() or digest(p) != expected:
            raise ValueError('six_source_seal_changed:' + name)
    if seal['mapping-manifest.json'] != V1_SHA or seal['mapping-manifest-v2.json'] != V2_SHA:
        raise ValueError('six_base_source_seal_changed')
    if seal['tolerances.json'] != TOLERANCES_SHA:
        raise ValueError('six_tolerances_source_seal_changed')
    prereg = source / PREREGISTRATION
    if (prereg.is_symlink() or not prereg.is_file()
            or mapping.get('preregistration') != {'path': PREREGISTRATION, 'sha256': digest(prereg)}):
        raise ValueError('six_preregistration_binding_changed')
    return mapping, {**seal, MANIFEST: digest(path), PREREGISTRATION: digest(prereg)}


def _stamp(text):
    value = datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('six_timestamp_timezone_missing')
    return value


def require_review(review, hashes, mapping, case, revision, started, argv, *, operation='run'):
    if not isinstance(review, dict) or review.get('schema') != REVIEW_SCHEMA:
        raise ValueError('six_prospective_independent_review_required')
    if (review.get('independent_review') is not True or type(review.get('unresolved_findings')) is not int
            or review['unresolved_findings'] != 0 or review.get('reviewed_commit') != revision
            or review.get('case') != case or case not in CASES
            or review.get('reviewed_local_source_sha256') != hashes
            or review.get('mapping_manifest') != {'path': MANIFEST, 'sha256': hashes[MANIFEST]}
            or review.get('runtime') != mapping['runtime'] or review.get('frozen') != mapping['frozen']):
        raise ValueError('six_review_identity_source_or_scope_mismatch')
    if _stamp(review.get('completed_utc')) >= _stamp(started):
        raise ValueError('six_review_must_precede_engine')
    if list(argv) not in review.get('authorized_' + operation + '_argvs', []):
        raise ValueError('six_argv_not_prospectively_reviewed')
    fence = review.get('fence') or {}
    if fence.get('status') != 'pass' or not re.fullmatch('[0-9a-f]{64}', str(fence.get('sha256'))):
        raise ValueError('six_review_fence_binding_missing')
    for name in ('source_snapshot_sha256', 'full_wrapper_freeze_sha256'):
        if not re.fullmatch('[0-9a-f]{64}', str(review.get(name))):
            raise ValueError('six_review_' + name + '_missing')


def read_review(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(REPO):
        raise ValueError('six_review_record_outside_checkout_or_symlink')
    return json.loads(path.read_text()), {'path': str(path.resolve().relative_to(REPO)), 'sha256': digest(path)}
