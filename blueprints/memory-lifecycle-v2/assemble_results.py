#!/usr/bin/env python3
"""Assemble results-20260926.json from the retained, published evidence only.

Every number comes from a file in this directory: phase timestamps and exit codes from
each retained execution receipt (runs-20260926/*/attempt-*/phase-*/command.json), verdicts
recomputed by analyze.py from the retained native responses and compared with the verdicts
recorded at run time, protocol facts from the retained records.json, release provenance
from upstream-20260926/release-verification.json, and upstream results from the retained
upstream receipts, property map and publication record. Standard library only.

Every retained attempt is reported, passing or failing (PREREGISTRATION.md section 6).
`attempts` lists every attempt directory in order; `binaries` gives the full record of each
version's last attempt and names the earlier ones. An attempt that stopped in a phase, that
the analyzer cannot interpret, that met an expected rejection with a success, or that has
no native expiry is recorded as it is. None of these stops the assembly. `status` is
`passed` only when every retained attempt passed and its verdicts were reproduced from the
published responses. A failed or stopped attempt keeps it `failed` even when a later
attempt of the same version passes: the preregistration makes a missed bar a documented
FAIL, never a reason to rerun silently.

The upstream `runs` hold only the unchanged suites at the release tags (upstream-20260926/v*/),
run with the upstream CI command. The discriminating control runs a filtered command on a
mutated checkout, so it is reported only under `discriminating_control`.

    python3 assemble_results.py [--check]
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze  # noqa: E402

RESULTS = 'results-20260926.json'
CONTROLS = (('control-0-unmodified', 'passed'), ('control-1-empty-fragment', 'failed'),
            ('control-2-filter-always-true', 'failed'), ('control-3-restored', 'passed'))
# The upstream scripts as they ran; the committed ones in upstream-20260926/ changed afterwards.
AS_RUN = 'history/upstream-scripts-as-run-20260926'
# The script that ran the final upstream round and the control, and its output.
DRIVER = ('history/upstream-final-round-driver-20260926.sh', 'history/upstream-final-round-driver-20260926.log')


def read(path):
    return json.loads(Path(path).read_text())


def read_optional(path):
    path = Path(path)
    return read(path) if path.is_file() else None


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def instant(text):
    return datetime.datetime.fromisoformat(text.replace('Z', '+00:00'))


def seconds_between(earlier, later):
    if earlier is None or later is None:
        return None
    return round((instant(later) - instant(earlier)).total_seconds(), 3)


def dig(value, *keys):
    """value[key1][key2]..., or None when a step is missing or has the wrong type."""
    for key in keys:
        try:
            value = value[key]
        except (KeyError, IndexError, TypeError):
            return None
    return value


def version_key(version):
    return [(0, int(part), '') if part.isdigit() else (1, 0, part) for part in re.split(r'[.-]', version)]


def attempt_key(run):
    number = run.name.removeprefix('attempt-')
    return (version_key(run.parent.name.removeprefix('ai-memory-')),
            int(number) if number.isdigit() else float('inf'), run.name)


def phase_record(run, phase, result):
    """A phase's execution receipt, plus its checks when the attempt could be analyzed.
    None when the phase never ran because an earlier phase stopped the attempt."""
    command = read_optional(run / f'phase-{phase}/command.json')
    if command is None:
        return None
    outcomes = read_optional(run / f'phase-{phase}/outcomes.json')
    record = {
        'started_utc': command['started_utc'], 'finished_utc': command['finished_utc'],
        'duration_seconds': seconds_between(command['started_utc'], command['finished_utc']),
        'exit_code': command.get('exit_code'), 'bwrap_version': command['bwrap_version'],
        'binary_sha256_unchanged': command['binary_sha256_before'] == command['binary_sha256_after'],
        'reported_version': dig(read_optional(run / f'phase-{phase}/version.json'), 'version'),
        'tool_calls': len(outcomes) if isinstance(outcomes, dict) else None,
        'checks_total': None, 'checks_passed': None, 'failed_checks': None,
        'expected_protocol_rejections': None,
    }
    if 'timeout_seconds' in command:
        record['timeout_seconds'] = command['timeout_seconds']
    if result is not None:
        record.update(
            checks_total=len(result['checks']), checks_passed=sum(result['checks'].values()),
            failed_checks=result['failed_checks'],
            # An unexpected success carries its result instead of a code and message.
            expected_protocol_rejections={
                label: {**{key: r[key] for key in ('code', 'message', 'unexpected_success') if key in r},
                        'meets_bar': r['meets_bar']}
                for label, r in result['expected_protocol_rejections'].items()})
    return record


def ttl_record(result, timeline):
    expiry = dig(result, 'pre', 'ttl_native_expired_at')
    answered = dig(timeline, 'ttl_before_expiry', 'received_utc')
    sent = dig(timeline, 'ttl_after_expiry_default', 'sent_utc')
    return {
        'server_expired_at': expiry,
        'ttl_before_expiry_received_utc': answered,
        'first_post_expiry_call_sent_utc': sent,
        'seconds_answered_before_expiry': seconds_between(answered, expiry),
        'seconds_sent_after_expiry': seconds_between(expiry, sent),
    }


def attempt_record(root, run, release):
    """What one retained attempt establishes, whether it passed, failed or stopped early."""
    state = read_optional(run / 'run.json') or {}
    recorded = read_optional(run / 'acceptance.json')
    result = analysis_error = None
    if recorded is not None:  # the attempt reached analysis at run time: repeat it on the published files
        try:
            result = analyze.summarize(run)
        except Exception as error:  # noqa: BLE001 -- the same fail-closed rule run.py applies
            analysis_error = f'{type(error).__name__}: {error}'.replace(str(run), '<run>')
    if recorded is None:
        reproduced = None
    elif result is not None and 'pre' in recorded and 'post' in recorded:
        reproduced = (result['pre']['checks'] == recorded['pre']['checks']
                      and result['post']['checks'] == recorded['post']['checks'])
    else:
        reproduced = analysis_error is not None and analysis_error == recorded.get('analysis_error')
    records = read_optional(run / 'phase-pre/records.json')
    tools = dig(records, 1, 'response', 'result', 'tools')
    private = {entry['source']: entry['sha256'] for entry in read(run / 'publication.json')['private_only_files']}
    listings = private.get('phase-pre/tools.json'), private.get('phase-post/tools.json')
    return {
        'evidence_dir': str(run.relative_to(root)),
        'binary': run.parent.name.removeprefix('ai-memory-'),
        'attempt': run.name,
        'stage_reached': state.get('stage'),
        'stopped_by': state.get('failure'),
        'analysis_error_at_run_time': dig(recorded, 'analysis_error'),
        'analysis_error': analysis_error,
        'binary_sha256': dig(recorded, 'binary_sha256') or state.get('binary_sha256'),
        'official_release': {key: release[key] for key in (
            'tag', 'asset_sha256_download', 'asset_digests_agree', 'installed_equals_release_binary')},
        'negotiated_initialize_protocolVersion': dig(records, 0, 'response', 'result', 'protocolVersion'),
        'advertised_tool_count': len(tools) if isinstance(tools, list) else None,
        'private_only_sha256': private,
        'tools_list_stable_across_restart': None if None in listings else listings[0] == listings[1],
        'verdicts_reproduced_from_published_responses': reproduced,
        'phase_pre': phase_record(run, 'pre', dig(result, 'pre')),
        'phase_post': phase_record(run, 'post', dig(result, 'post')),
        'ttl_real_time': ttl_record(result, read_optional(run / 'phase-pre/timeline.json')),
        'sweep': dig(result, 'pre', 'sweep'),
        'status_counts_pre': dig(result, 'post', 'status_counts_pre'),
        'status_counts_post': dig(result, 'post', 'status_counts_post'),
        'passed': bool(result and result['passed']),
    }


def verdict(receipt):
    totals = receipt['totals']
    if receipt['exit_code'] != 0 or totals['failed']:
        return 'failed'
    if totals['passed'] + totals['failed'] == 0:
        return 'untested: zero tests selected'
    return 'passed'


def scripts_as_run(root, upstream):
    """The as-run copies: whether each differs from the committed script, and whether its sha256
    equals the one logged when it ran (None when no hash was logged; history/publication.json
    then states the basis for the copy)."""
    entries = {entry['path']: entry for entry in read(root / 'history/publication.json')['published_files']}
    copies = sorted(path for path in (root / AS_RUN).iterdir() if path.suffix in ('.py', '.sh'))
    logged = {}
    for path in copies:
        pointer = entries[f'{AS_RUN.removeprefix("history/")}/{path.name}']['run_time_sha256']
        if pointer is None:
            logged[path.name] = None
        else:
            line = (root / 'history' / pointer['record']).read_text().splitlines()[pointer['line'] - 1]
            logged[path.name] = line.split()[0] == digest(path)
    return {
        'directory': f'{AS_RUN}/',
        'note': 'The upstream runs, the control and the setup used these copies; history/publication.json binds '
                'each to its private source. The final-round driver logged the sha256 of the runner and of '
                'control.py when the round started (sha256_logged_when_run_matches). No hash of setup.sh was '
                'logged when it ran; its publication entry states the basis for the copy. The committed scripts '
                'listed in committed_script_differs changed afterwards (see changes_after_the_verification_review).',
        'committed_script_differs': sorted(path.name for path in copies if digest(path) != digest(upstream / path.name)),
        'sha256_logged_when_run_matches': logged,
        'final_round_driver': list(DRIVER),
    }


def upstream_record(root):
    upstream = root / 'upstream-20260926'
    runner = digest(root / AS_RUN / 'run_upstream_tests.py')
    runs = {}
    # Only the release-tag groups: control/ holds filtered runs on a mutated checkout.
    for receipt_path in sorted(upstream.glob('v*/*.receipt.json')):
        receipt = read(receipt_path)
        runs[str(receipt_path.relative_to(upstream))] = {
            'tag': receipt['tag'], 'commit': receipt['commit'],
            'tracked_files_modified': receipt['tracked_files_modified'],
            'upstream_command': ' '.join(receipt['upstream_command']),
            'toolchain_in_sandbox': receipt['toolchain_in_sandbox'],
            'runner_matches_as_run_copy': receipt['runner_sha256'] == runner,
            'started_utc': receipt['started_utc'], 'finished_utc': receipt['finished_utc'],
            'duration_seconds': receipt['duration_seconds'], 'exit_code': receipt['exit_code'],
            'totals': receipt['totals'], 'failed_tests': receipt['failed_tests'],
            'verdict': verdict(receipt),
            'log': str(receipt_path.with_name(receipt['log']).relative_to(root)), 'log_sha256': receipt['log_sha256'],
        }
    superseded = {}
    for receipt_path in sorted(upstream.glob('superseded-round-1/*/*.receipt.json')):
        receipt = read(receipt_path)
        superseded[str(receipt_path.relative_to(upstream))] = {
            'upstream_command': ' '.join(receipt['upstream_command']), 'started_utc': receipt['started_utc'],
            'exit_code': receipt['exit_code'], 'totals': receipt['totals'], 'failed_tests': receipt['failed_tests'],
            'verdict': verdict(receipt)}
    control = {}
    for label, expected in CONTROLS:
        receipt = read(upstream / 'control' / f'{label}.receipt.json')
        lines = (upstream / 'control' / receipt['log']).read_text().splitlines()
        panic = next((i for i, line in enumerate(lines) if 'panicked at' in line), None)
        control[label] = {'expected': expected, 'observed': verdict(receipt), 'as_expected': verdict(receipt) == expected,
                          'upstream_command': ' '.join(receipt['upstream_command']),
                          'runner_matches_as_run_copy': receipt['runner_sha256'] == runner,
                          'started_utc': receipt['started_utc'], 'finished_utc': receipt['finished_utc'],
                          'exit_code': receipt['exit_code'],
                          'tests_selected': receipt['totals']['passed'] + receipt['totals']['failed'],
                          'tracked_files_modified': receipt['tracked_files_modified'],
                          'failure_message': lines[panic:panic + 2] if panic is not None else None,
                          'failed_on_the_expiry_assertion': panic is not None and any(
                              'expired hidden' in line for line in lines[panic:panic + 2])}
    property_map = read(upstream / 'property-map.json')
    publication = read(upstream / 'publication.json')
    rustup = read(upstream / 'rustup-init-verification.json')
    return {
        'evidence_class': 'native_proven',
        'acceptance_policy_class': 'upstream test (docs/acceptance-evidence-policy.md): unchanged upstream '
                                   'suites at the release tags, upstream CI command',
        'runs': runs,
        'superseded_round_1': superseded,
        'discriminating_control': {
            'evidence_class': 'local_integration',
            'note': 'A control, not an upstream test: a filtered upstream command on a checkout whose '
                    'reader.rs was mutated and then restored.',
            'summary': read(upstream / 'control/control-summary.json'), 'runs': control,
            'mutation_diffs': ['upstream-20260926/control/control-1-empty-fragment.diff',
                               'upstream-20260926/control/control-2-filter-always-true.diff']},
        'property_map_counts': {key: {prop: value['counts'] for prop, value in run['properties'].items()}
                                for key, run in property_map['runs'].items()},
        'property_map': 'upstream-20260926/property-map.json',
        'publication': {
            'record': 'upstream-20260926/publication.json',
            'published_files': len(publication['published_files']),
            'changed_by_transform': sorted(entry['path'] for entry in publication['published_files']
                                           if entry.get('changed_by_transform')),
            'private_only_files': sorted(entry['name'] for entry in publication['private_only_files'])},
        'rustup_init': {key: rustup[key] for key in (
            'rustup_version', 'started_utc', 'finished_utc', 'binary_sha256', 'binary_matches_sidecar',
            'binary_matches_official_archive', 'official_url', 'verdict', 'control')},
        'scripts_as_run': scripts_as_run(root, upstream),
    }


def build(root=HERE):
    """The results document for the evidence under root (this directory by default)."""
    root = Path(root)
    upstream = root / 'upstream-20260926'
    releases = {r['tag']: r for r in read(upstream / 'release-verification.json')['results']}
    runs = sorted((root / 'runs-20260926').glob('ai-memory-*/attempt-*'), key=attempt_key)
    attempts = [attempt_record(root, run, releases['v' + run.parent.name.removeprefix('ai-memory-')])
                for run in runs]
    by_version = {}
    for record in attempts:
        by_version.setdefault(record['binary'], []).append(record)
    binaries = {version: {**records[-1], 'earlier_attempts': [r['evidence_dir'] for r in records[:-1]]}
                for version, records in by_version.items()}
    phases = [record[phase] for record in attempts for phase in ('phase_pre', 'phase_post') if record[phase]]
    starts, ends = [p['started_utc'] for p in phases], [p['finished_utc'] for p in phases]
    freeze = (root / 'history/preregistration-freeze-20260926.txt').read_text().split()
    frozen = dict(zip(freeze[2::2], freeze[1::2]))
    harness = {name: digest(root / name) for name in ('exercise.py', 'analyze.py', 'run.py')}
    run_states = [read_optional(root / record['evidence_dir'] / 'run.json') or {} for record in attempts]
    upstream_results = upstream_record(root)
    rustup = upstream_results['rustup_init']
    hash_log = next(entry for entry in read(root / 'history/publication.json')['published_files']
                    if entry['path'] == 'preregistration-sha256-20260925.txt')
    # Every attempt counts: a later pass does not erase an earlier failed or stopped attempt.
    passed = bool(attempts) and all(record['passed'] and record['verdicts_reproduced_from_published_responses']
                                    for record in attempts)
    return {
        'schema_version': 1,
        'claim_id': 'memory-lifecycle-v2-20260926',
        'evidence_class': 'local_integration',
        'acceptance_policy_class': 'local integration check (docs/acceptance-evidence-policy.md): a locally '
                                   'authored fixture driving the official binaries over native stdio MCP; '
                                   'not an upstream test',
        'observed_at_utc': {'first_phase_started': min(starts, default=None),
                            'last_phase_finished': max(ends, default=None),
                            'source': 'the retained execution receipts phase-*/command.json'},
        'status': 'passed' if passed else 'failed',
        'scope': 'Disposable stores only, one per binary: a TTL crossing in real wall-clock time, scoped routing '
                 'across 4 projects in 2 workspaces (scopes[] and global=true), restart durability with a second '
                 'native process on the same store, direct reads of swept and deleted pages, and v1 regressions.',
        'not_established': [
            'The memory-lifecycle gate in catalogs/us-equities/convergence-review.json stays open: live-store '
            'policy, scoped retrieval quality and evaluated learning were not exercised.',
            'Store migration between binaries, concurrent clients, tenant authorization, secure erasure, '
            'retrieval ranking, embeddings and LLM features (PREREGISTRATION.md section 8).',
        ],
        'supersedes': 'results-20260925.json (its analyzer accepted malformed and misattributed responses; its '
                      'retained responses are under runs-20260925/)',
        'preregistration': {
            'path': 'blueprints/memory-lifecycle-v2/PREREGISTRATION.md',
            'sha256': digest(root / 'PREREGISTRATION.md'),
            'frozen_utc': freeze[0],
            'sha256_at_freeze': frozen['PREREGISTRATION.md'],
            'freeze_record': 'history/preregistration-freeze-20260926.txt',
            'executed_harness_unchanged_since_freeze': all(frozen[name] == value for name, value in harness.items()),
            'executed_harness_recorded_by_each_run': bool(run_states) and all(
                state.get(key) == frozen[name] for state in run_states
                for key, name in (('exercise_sha256', 'exercise.py'), ('analyze_sha256', 'analyze.py'))),
            'publish_py_changed_after_freeze': digest(root / 'publish.py') != frozen['publish.py'],
            'publish_py_change': 'After the runs, publish.py also lists protocol.jsonl among the private-only '
                                 'files and records a sha256 over the store\'s final file listing. It '
                                 'post-processes retained files and does not affect any verdict.',
            'recorded_before_the_first_fixture_run': bool(starts) and instant(freeze[0]) < instant(min(starts)),
        },
        'errata_against_the_frozen_preregistration': [
            'Section 7 says no upstream result was read before the freeze. A progress check before the freeze '
            'showed two passing v2.3.2 test lines (admin::tests::auto_improve_buckets_an_oidc_operator_by_'
            'qualified_identity and admin::tests::merge_workspace_folds_projects_and_deletes_empty_source; the '
            'second matches the workspace and delete patterns). The v2.3.2 first-round run finished at '
            '02:17:42Z, 46 s before the freeze, and was read after it.',
            'The upstream commands were all rerun after the freeze (final round). The first round had put the '
            'sandbox HOME under /home, which the repository private-content scanner flags. Its receipts are '
            'retained under upstream-20260926/superseded-round-1/ and its results are listed below. The final '
            'runner also creates HOME and /tmp fresh per run, records its own sha256 and the in-sandbox toolchain '
            'versions, and parses a status line that a spawned process\'s output separated from its test name.',
            'Control mutation 2 (the expiry condition always true, placeholder kept) was added after the freeze. '
            'The preregistered empty fragment unbinds a positional SQL placeholder, so its failure need not come '
            'from the expiry semantics. Both mutations ran and both are reported.',
            'Section 7 lists four deviations from the CI environment. In addition, the sandbox clears every other '
            'variable and sets HOME, USER, LANG, TZ and PATH; each receipt records the full environment.',
            'Section 7\'s pass bar did not anticipate a step that selects no test. v2.4.1\'s cargo test --workspace '
            '--doc ran 11 doc-test harnesses containing 0 doc tests, so per docs/acceptance-evidence-policy.md it is '
            'recorded as untested (vacuous), not passed.',
            'Section 6 says the 2026-09-25 attempts are recorded in results-20260925.json. The details are in '
            'history/attempts-20260925.json, which results-20260925.json links.',
            'Section 2 cites release verification run before the freeze (02:05:28Z). The retained '
            'upstream-20260926/release-verification.json is a rerun at 02:58:31Z, made after one field was renamed '
            '(asset_sha256_github_api to asset_sha256_github_release_record) because gitleaks\' generic-api-key rule '
            'flagged the public digest. Both runs gave identical digests and verdicts; the first run stays private '
            'and upstream-20260926/publication.json lists its sha256.',
            'Section 7 says rustup-init was checked against its published sha256; no record of that check was '
            f'retained. The comparison was made from {rustup["started_utc"]} to {rustup["finished_utc"]}, after '
            'the runs, on the private rustup-init that setup.sh ran: upstream-20260926/rustup-init-verification.json.',
        ],
        'changes_after_the_independent_review': [
            'upstream_verification.runs holds only the unchanged suites at the release tags. It had also listed '
            'the four discriminating-control runs, which ran a filtered command and, twice, a mutated checkout; '
            'they now appear only under discriminating_control.',
            'assemble_results.py reports every retained attempt, passing or failing, in attempts, and names each '
            'version\'s earlier attempts in binaries. An unexpected success, an analysis error, a phase that never '
            'ran or a missing native expiry is recorded instead of stopping the assembly.',
            'upstream-20260926/setup.log had its scratch root replaced without a declaration. publish_upstream.py '
            'now publishes it and writes upstream-20260926/publication.json, which binds every retained upstream '
            'file to the sha256 of its private source and declares each transformation. setup.log now uses the '
            '<scratch> placeholder of the other upstream files instead of <upstream-scratch>.',
            'status is passed only when every retained attempt passed and its verdicts were reproduced. A '
            'later pass of the same version no longer outweighs an earlier failed or stopped attempt.',
            'history/recheck-20260925.json retains the output of history/recheck_20260925.py.',
            'tests/test_memory_lifecycle_v2.py adds a discriminating control for each of the 82 phase-pre and '
            '19 phase-post checks, on each retained run: one change to a response, a per-call instant or a '
            'handoff value that must turn that check false. The earlier controls covered only the repaired rules.',
            'history/review_repair_controls_20260926.py re-introduces each reviewed defect in a temporary copy of '
            'the files and requires the matching regression tests to fail with it and pass without it. Its '
            'output is retained in history/review-repair-controls-20260926.txt.',
            'The grand-dashboard checkpoint that cites this file (observability/grand-dashboard/state.json '
            'recorded_at_utc) is dated after the evidence it cites.',
        ],
        'changes_after_the_verification_review': [
            'upstream-20260926/run_upstream_tests.py refuses to start when its log or receipt already exists and '
            'creates both exclusively. A rerun, such as the section 7 --no-fail-fast follow-up to a failed run, '
            'needs its own --label or --out, so it can no longer truncate an earlier log or replace its receipt. '
            '--reparse prints the recomputed receipt instead of rewriting it.',
            'upstream-20260926/control.py judges each run from the runner exit status and the receipt (a build '
            'error, an empty selection or a missing receipt is neither pass nor fail) and refuses existing '
            'output. Once the four runs are done it writes its summary, whether or not they were as expected, '
            'and exits 1 unless they gave pass, fail, fail, pass and the file was restored byte-for-byte. The '
            'retained control run meets that bar.',
            f'The upstream runs, the control and the setup used the earlier run_upstream_tests.py, control.py and '
            f'setup.sh, retained byte-for-byte under {AS_RUN}/. Every retained upstream and control receipt '
            f'records the as-run runner\'s sha256 (runner_matches_as_run_copy). The final round\'s driver script '
            f'and its log are retained as {DRIVER[0]} and {DRIVER[1]}: the log recorded the sha256 of the runner '
            f'and of control.py when the round started, and both equal the as-run copies. No hash of setup.sh was '
            f'recorded when it ran; history/publication.json states the basis for its copy.',
            'upstream-20260926/setup.sh said in its header that the rustup-init checksum was verified before the '
            'script ran. No record of such a check was kept (see the rustup-init erratum), and the header now '
            'says so and names the later comparison. Only that comment changed.',
            f'history/preregistration-sha256-20260925.txt had the private scratch root replaced by <scratch> on '
            f'lines {" and ".join(map(str, hash_log["placeholder_lines"]))} without a declaration. '
            f'history/publication.json now binds it ({hash_log["bytes"]:,} bytes) to its private source '
            f'({hash_log["source_bytes"]:,} bytes, sha256 {hash_log["source_sha256"]}) and declares that '
            'substitution. It also binds the retained freeze record, the as-run scripts and the final-round '
            'driver files to the files they copy, and says what binds every other file under history/.',
            'tests/test_memory_lifecycle_v2.py covers each of these changes. '
            'history/verification_repair_controls_20260926.py puts each reviewed defect back in a temporary copy '
            'and shows the matching tests failing with it and passing without it; its output is retained in '
            'history/verification-repair-controls-20260926.txt.',
        ],
        'binaries': binaries,
        'attempts': [{key: record[key] for key in (
            'binary', 'attempt', 'evidence_dir', 'stage_reached', 'stopped_by', 'analysis_error_at_run_time',
            'analysis_error', 'verdicts_reproduced_from_published_responses', 'passed')}
            | {'failed_checks': {phase: dig(record, f'phase_{phase}', 'failed_checks') for phase in ('pre', 'post')}}
            for record in attempts],
        'upstream_verification': upstream_results,
        'isolation': {
            'mechanism': 'bubblewrap --unshare-all --clearenv --die-with-parent --new-session --cap-drop ALL; '
                         'only the binary, system runtime and driver read-only and a fresh run directory writable',
            'network_interfaces': sorted({interface for record in attempts
                                          for interface in (dig(read_optional(root / record['evidence_dir'] /
                                                                              'phase-pre/namespace.json'),
                                                                'external_network_interfaces') or [])}),
            'embedding_provider': 'none', 'llm': 'not configured', 'watcher': False,
            'real_memory_or_authentication_stores_mounted': False,
        },
    }


def render(results):
    return json.dumps(results, indent=2) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--check', action='store_true', help=f'fail if {RESULTS} is stale')
    args = parser.parse_args()
    results = build()
    text, out = render(results), HERE / RESULTS
    if args.check:
        if not out.is_file() or out.read_text() != text:
            raise SystemExit(f'{RESULTS} is stale; rerun assemble_results.py')
        return
    out.write_text(text)
    print(json.dumps({'status': results['status'],
                      'attempts': [(a['binary'], a['attempt'], a['passed']) for a in results['attempts']],
                      'observed_at_utc': results['observed_at_utc'], 'preregistration': results['preregistration']}))


if __name__ == '__main__':
    main()
