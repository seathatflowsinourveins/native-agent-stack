#!/usr/bin/env python3
"""Discriminating controls for the regression tests added after the 2026-09-26 verification
review, which followed the controls in review-repair-controls-20260926.txt.

The method and helpers are those of review_repair_controls_20260926.py. Each control puts one
reviewed defect, or a gap found while fixing them, back into a temporary copy of the files the
tests read, requires the listed tests to fail there, and requires them to pass once the file
is restored. For the upstream scripts the defect is the script as it ran, retained under
upstream-scripts-as-run-20260926/.
The checkout itself is never modified. Prints JSON lines: the unmodified run of every listed
test, one line per control and a summary; exits 1 if the unmodified run fails or any control
fails to discriminate. The output is retained as verification-repair-controls-20260926.txt.
Standard library only.

    python3 blueprints/memory-lifecycle-v2/history/verification_repair_controls_20260926.py
"""
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_repair_controls_20260926 import BLUEPRINT, COPIED, ROOT, replace, run  # noqa: E402

UPSTREAM = f'{BLUEPRINT}/upstream-20260926'
AS_RUN = f'{BLUEPRINT}/history/upstream-scripts-as-run-20260926'
RUNNER_TESTS = ['UpstreamRunnerTests.test_a_rerun_with_the_same_out_and_label_is_refused_and_the_earlier_files_are_kept',
                'UpstreamRunnerTests.test_reparse_prints_the_recomputed_receipt_and_never_rewrites_it']
CONTROL_TESTS = ['UpstreamControlTests.test_four_failing_runs_exit_nonzero_and_keep_the_summary',
                 'UpstreamControlTests.test_mutations_that_survive_exit_nonzero',
                 'UpstreamControlTests.test_the_expected_sequence_exits_zero_and_restores_the_file',
                 'UpstreamControlTests.test_a_failed_restore_is_a_problem_even_when_every_run_was_as_expected',
                 'UpstreamControlTests.test_existing_output_is_refused_before_the_checkout_is_touched',
                 'UpstreamControlTests.test_the_retained_control_run_meets_this_bar']
HISTORY_TESTS = ['HistoryPublicationTests.test_every_history_file_is_accounted_for',
                 'HistoryPublicationTests.test_the_hash_log_and_the_as_run_scripts_are_listed_copies']


def as_run(name):
    """The committed script replaced by the retained copy of the script as it ran."""
    return lambda _text: (ROOT / AS_RUN / name).read_text()


def without_hash_log_entry(text):
    record = json.loads(text)
    record['published_files'] = [entry for entry in record['published_files']
                                 if entry['path'] != 'preregistration-sha256-20260925.txt']
    return json.dumps(record, indent=2) + '\n'


# (reviewed defect, file, mutation, tests that must fail)
CONTROLS = [
    ('defect 1: run_upstream_tests.py as it ran (a rerun into the same --out and --label truncates the '
     'earlier log and replaces its receipt; --reparse rewrites the receipt)',
     f'{UPSTREAM}/run_upstream_tests.py', as_run('run_upstream_tests.py'), RUNNER_TESTS),
    ('defect 2: control.py as it ran (exits 0 whatever the four runs and the restore gave)',
     f'{UPSTREAM}/control.py', as_run('control.py'), CONTROL_TESTS),
    ('defect 3: the <scratch> substitution in the historical hash log without a publication record entry',
     f'{BLUEPRINT}/history/publication.json', without_hash_log_entry, HISTORY_TESTS),
    ('defect 4: setup.sh as it ran (its header claims a rustup-init checksum check before the script)',
     f'{UPSTREAM}/setup.sh', as_run('setup.sh'),
     ['UpstreamScriptTests.test_setup_sh_header_does_not_claim_an_unrecorded_checksum_check']),
    ('consequence of defects 1 and 2: the results compare the receipts with the committed runner',
     f'{BLUEPRINT}/assemble_results.py',
     replace("runner = digest(root / AS_RUN / 'run_upstream_tests.py')",
             "runner = digest(upstream / 'run_upstream_tests.py')"),
     ['ResultsAssemblyTests.test_results_file_is_current',
      'ResultsAssemblyTests.test_upstream_runs_are_only_unchanged_tag_suites']),
    ('gap found with defects 1 and 2: an as-run copy that is not what ran (the committed control.py in place '
     'of the copy whose sha256 the final-round driver logged)',
     f'{AS_RUN}/control.py', lambda _text: (ROOT / UPSTREAM / 'control.py').read_text(),
     ['HistoryPublicationTests.test_the_as_run_copies_match_what_was_recorded_when_they_ran']),
]


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
