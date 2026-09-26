#!/usr/bin/env python3
"""Discriminating controls for the regression tests added after the 2026-09-26 independent
review of this blueprint's repair.

Each control re-introduces one reviewed defect, or one verification gap the review named,
in a temporary copy of the files the tests read (tests/test_memory_lifecycle_v2.py, this
blueprint, scripts/ and the grand-dashboard state). It runs the tests that must catch it,
requires them to fail there and to pass again once the file is restored. The checkout
itself is never modified. Prints JSON lines: the unmodified run of every listed test, one
line per control and a summary; exits 1 if the unmodified run fails or any control fails
to discriminate. The output is retained as review-repair-controls-20260926.txt.
Standard library only.

    python3 blueprints/memory-lifecycle-v2/history/review_repair_controls_20260926.py
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
BLUEPRINT = 'blueprints/memory-lifecycle-v2'
ASSEMBLER = f'{BLUEPRINT}/assemble_results.py'
TESTS = 'tests.test_memory_lifecycle_v2.'
COPIED = ('tests/__init__.py', 'tests/test_memory_lifecycle_v2.py', BLUEPRINT, 'scripts',
          'observability/grand-dashboard/state.json')


def replace(old, new):
    def mutate(text):
        if text.count(old) != 1:
            raise SystemExit(f'control pattern not found exactly once: {old!r}')
        return text.replace(old, new, 1)
    return mutate


def restamp(text):
    stamp = json.loads(text)['recorded_at_utc']
    return replace(f'"recorded_at_utc": "{stamp}"', '"recorded_at_utc": "2026-09-26T02:49:33Z"')(text)


def first_recheck_one_check_short(text):
    runs = json.loads(text)
    runs[0]['passed_checks'] -= 1
    return json.dumps(runs, indent=2) + '\n'


# (reviewed defect or gap, file, mutation, tests that must fail)
CONTROLS = [
    ('defect 1: control runs listed as upstream test runs', ASSEMBLER,
     replace("upstream.glob('v*/*.receipt.json')", "upstream.glob('*/*.receipt.json')"),
     ['ResultsAssemblyTests.test_upstream_runs_are_only_unchanged_tag_suites',
      'ResultsAssemblyTests.test_results_file_is_current']),
    ('defect 2: dashboard checkpoint older than the evidence it cites (the pre-review 02:49:33Z)',
     'observability/grand-dashboard/state.json', restamp,
     ['DashboardCheckpointTests.test_checkpoint_is_not_older_than_the_results_it_cites']),
    ('defect 3.1: an unexpected success read as a code and message', ASSEMBLER,
     replace("{**{key: r[key] for key in ('code', 'message', 'unexpected_success') if key in r},",
             "{**{key: r[key] for key in ('code', 'message')},"),
     ['ResultsAssemblyTests.test_unexpected_success_is_recorded_without_a_code']),
    ('defect 3.2: the native expiry used unguarded', ASSEMBLER,
     replace("'seconds_answered_before_expiry': seconds_between(answered, expiry),",
             "'seconds_answered_before_expiry': round((instant(expiry) - instant(answered)).total_seconds(), 3),"),
     ['ResultsAssemblyTests.test_missing_native_expiry_leaves_the_ttl_timing_unestablished']),
    ('defect 3.2: an analysis error left to stop the assembly', ASSEMBLER,
     replace('except Exception as error:  # noqa: BLE001', 'except ZeroDivisionError as error:  # noqa: BLE001'),
     ['ResultsAssemblyTests.test_analysis_error_is_reported_and_compared_with_the_run_time_error']),
    ('defect 3.2: a phase that never ran read unguarded', ASSEMBLER,
     replace("command = read_optional(run / f'phase-{phase}/command.json')",
             "command = read(run / f'phase-{phase}/command.json')"),
     ['ResultsAssemblyTests.test_attempt_that_stopped_in_phase_pre_is_reported']),
    ('defect 3.3: attempts built from the per-version map', ASSEMBLER,
     replace('            for record in attempts],', '            for record in binaries.values()],'),
     ['ResultsAssemblyTests.test_every_attempt_of_a_version_is_reported_in_order',
      'ResultsAssemblyTests.test_attempt_that_stopped_in_phase_pre_is_reported']),
    ('defect 3.3: attempts ordered as text (attempt-10 before attempt-2)', ASSEMBLER,
     replace("glob('ai-memory-*/attempt-*'), key=attempt_key)", "glob('ai-memory-*/attempt-*'))"),
     ['ResultsAssemblyTests.test_every_attempt_of_a_version_is_reported_in_order']),
    ('defect 3.3: status taken from each version\'s last attempt only', ASSEMBLER,
     replace("verdicts_reproduced_from_published_responses']\n"
             "                                    for record in attempts)",
             "verdicts_reproduced_from_published_responses']\n"
             "                                    for record in binaries.values())"),
     ['ResultsAssemblyTests.test_every_attempt_of_a_version_is_reported_in_order',
      'ResultsAssemblyTests.test_attempt_that_stopped_in_phase_pre_is_reported']),
    ('defect 4: setup.log edited without a declaration (the pre-review <upstream-scratch> text)',
     f'{BLUEPRINT}/upstream-20260926/setup.log', lambda text: text.replace('<scratch>', '<upstream-scratch>'),
     ['UpstreamPublicationTests.test_every_retained_upstream_file_is_bound_to_its_private_source']),
    ('review gap 3: the retained recheck output edited (first run, one passed check fewer)',
     f'{BLUEPRINT}/history/recheck-20260925.json', first_recheck_one_check_short,
     ['HistoryTests.test_recheck_of_the_20260925_responses_matches_its_retained_output']),
    ('review gap 4: the retained rustup-init comparison edited',
     f'{BLUEPRINT}/upstream-20260926/rustup-init-verification.json',
     replace('"official_line": "dda72343', '"official_line": "0da72343'),
     ['UpstreamPublicationTests.test_rustup_verification_is_consistent_with_its_recorded_hashes']),
    ('review gap 6: one fixture check made vacuous (old_now_zero always true)', f'{BLUEPRINT}/analyze.py',
     replace("checks['old_now_zero'] = hit_paths(data['old_now']) == []", "checks['old_now_zero'] = True"),
     ['DiscriminatingControlTests.test_every_check_fails_under_its_own_mutation']),
]


def run(root, tests):
    completed = subprocess.run([sys.executable, '-m', 'unittest', *[TESTS + test for test in tests]],
                               cwd=root, capture_output=True, text=True)
    lines = [line for line in completed.stderr.splitlines() if line.startswith(('Ran ', 'OK', 'FAILED'))]
    return {'exit': completed.returncode, 'summary': lines}


def main():
    discriminating = 0
    with tempfile.TemporaryDirectory() as holder:
        root = Path(holder)
        for relative in COPIED:
            source, target = ROOT / relative, root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__'))
            else:
                shutil.copy2(source, target)
        baseline = run(root, sorted({test for _label, _path, _mutate, tests in CONTROLS for test in tests}))
        print(json.dumps({'baseline_of_all_listed_tests': baseline}), flush=True)
        for label, relative, mutate, tests in CONTROLS:
            path = root / relative
            original = path.read_text()
            path.write_text(mutate(original))
            try:
                mutated = run(root, tests)
            finally:
                path.write_text(original)
            restored = run(root, tests)
            ok = mutated['exit'] != 0 and restored['exit'] == 0
            discriminating += ok
            print(json.dumps({'control': label, 'file': relative, 'tests': tests, 'with_defect': mutated,
                              'restored': restored, 'discriminates': ok}), flush=True)
    print(json.dumps({'controls': len(CONTROLS), 'discriminating': discriminating,
                      'baseline_passed': baseline['exit'] == 0}))
    raise SystemExit(0 if discriminating == len(CONTROLS) and baseline['exit'] == 0 else 1)


if __name__ == '__main__':
    main()
