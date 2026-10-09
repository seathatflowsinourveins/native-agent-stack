"""Reproduce CC findings at the Fleet adapter's actual public collection seam."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

from tests import test_local_pages_fleet_data as fixtures

fleet_data = fixtures.fleet_data


class FleetReviewRegressionTests(unittest.TestCase):
    setUp = fixtures.FleetDataTests.setUp
    write_json = fixtures.FleetDataTests.write_json
    collect = fixtures.FleetDataTests.collect
    def test_regular_long_lane_names_survive_an_individually_invalid_row(self):
        names = ['risk-limits', 'desk-review', 'disk-pressure', 'us-equities-strategy-gate-review']
        self.direct['lanes_live'] = [{'lane': name, 'status': 'active'} for name in names]
        self.direct['lanes_live'].append({'lane': 'ghp_' + 'X' * 40, 'status': 'active'})
        self.direct['lanes_parked'] = names + ['github_pat_' + 'X' * 40]
        self.direct['claude_sessions'] = [{'name': name, 'status': 'active'} for name in names] + [{'name': 'sk-' + 'X' * 40}]
        view = self.collect()
        self.assertEqual([row['lane'] for row in view['lanes_live']], names)
        self.assertEqual([row['lane'] for row in view['lanes_parked']], names)
        self.assertEqual([row['name'] for row in view['claude_sessions']], names)
        self.assertNotIn('X' * 40, json.dumps(view))
        for key in ['lanes_live', 'lanes_parked', 'claude_sessions']:
            self.assertEqual(view['availability'][key]['status'], 'reported')

    def test_native_ledger_event_amounts_sum_actuals_separately_from_reserved_caps(self):
        path = self.state / 'coordination/api-actions-20261008/api-actions-ledger.jsonl'
        path.parent.mkdir(parents=True)
        path.write_text('\n'.join(json.dumps(row) for row in [{'actual_usd': 1.25, 'max_usd': 10}, {'actual_usd': 2.5, 'max_usd': 20}, {'event': 'queued', 'prompt': 'private fixture prompt'}]))
        sdk = self.collect()['sdk']
        self.assertEqual(sdk['spend_usd'], 3.75)
        self.assertEqual(sdk.get('reserved_max_usd'), 30)
        self.assertIsNone(sdk['ceiling_usd'])
        self.assertNotIn('private fixture prompt', json.dumps(sdk))

    def test_empty_valid_ledger_is_dated_no_spend_but_missing_and_bad_are_unknown(self):
        path = self.state / 'coordination/api-actions-20261008/api-actions-ledger.jsonl'
        path.parent.mkdir(parents=True)
        path.write_text('\n \n')
        sdk = self.collect()['sdk']
        self.assertEqual(sdk['status'], 'no spend yet')
        self.assertEqual(sdk['spend_usd'], 0)
        self.assertIsNotNone(sdk['read_utc'])
        path.write_text('{broken')
        self.assertIsNone(self.collect()['sdk']['spend_usd'])
        path.unlink()
        self.assertIsNone(self.collect()['sdk']['spend_usd'])

    def test_native_empty_ledger_is_zero_with_direct_or_snapshot_dates(self):
        empty = {'rows': 0, 'last': None, 'sums': {}}
        self.direct['api_spend_ledger'] = empty
        direct = self.collect()['sdk']
        self.assertEqual(direct['status'], 'no spend yet')
        self.assertEqual(direct['spend_usd'], 0)
        self.assertEqual(direct['reserved_max_usd'], 0)
        self.assertEqual(direct['read_utc'], self.direct['at'])
        self.snapshot['api_spend_ledger'] = empty
        self.write_json('coordination/ns2604-coop/watchers/fleet-now.json', self.snapshot)
        self.runner.fleet_fail = True
        snapshot = self.collect()['sdk']
        self.assertEqual(snapshot['status'], 'no spend yet')
        self.assertEqual(snapshot['spend_usd'], 0)
        self.assertEqual(snapshot['read_utc'], self.snapshot['at'])
        self.runner.fleet_fail = False
        self.direct['api_spend_ledger'] = {'rows': None, 'sums': {}}
        self.assertIsNone(self.collect()['sdk']['spend_usd'])

    def test_native_max_reservations_remain_separate_from_credit_ceiling(self):
        self.direct['api_spend_ledger'] = {'rows': 2, 'sums': {'actual_usd': 3.75, 'max_usd': 30}}
        sdk = self.collect()['sdk']
        self.assertEqual(sdk['spend_usd'], 3.75)
        self.assertEqual(sdk['reserved_max_usd'], 30)
        self.assertIsNone(sdk['ceiling_usd'])

    def test_unknown_policy_with_a_fast_list_does_not_assign_parked_tiers(self):
        self.write_json('coordination/command-center/lane-tiers.json', {'schema': 'unknown/1', 'default': 'standard', 'fast': ['grand-catalog']})
        view = self.collect()
        self.assertEqual(view['tiers']['availability'], 'not reported')
        self.assertIsNone(view['tiers']['default'])
        self.assertIsNone(view['tiers']['fast'])
        self.assertTrue(all(row['tier'] is None for row in view['lanes_parked']))
        self.assertEqual(view['lanes_live'][0]['tier'], 'standard')

    def test_unicode_and_punctuation_workflow_names_match_the_native_run_rows(self):
        names = ['Build & audit!', 'Review #1 — naïve 東京']
        directory = self.root / '.github/workflows'
        for index, name in enumerate(names):
            (directory / f'unicode-{index}.yml').write_text(f'name: "{name}"\njobs:\n  audit:\n    steps:\n      - uses: anthropics/claude-code-action@pin\n')
        self.runner.runs = [{'workflowName': name, 'status': 'queued', 'databaseId': index + 1} for index, name in enumerate(names)]
        view = self.collect()['actions']
        self.assertEqual([row['workflowName'] for row in view['runs']], names)

    def test_punctuation_delimited_secret_prefixes_cannot_enter_workflow_cache(self):
        secret = 'ghp_' + 'X' * 40
        names = [f'Build ({secret})', f'Review:{secret}']
        directory = self.root / '.github/workflows'
        for index, name in enumerate(names):
            (directory / f'private-{index}.yml').write_text(f'name: "{name}"\njobs:\n  audit:\n    steps:\n      - uses: anthropics/claude-code-action@pin\n')
        self.runner.runs = [{'workflowName': name, 'status': 'queued', 'databaseId': index + 1} for index, name in enumerate(names)]
        view = self.collect()
        self.assertNotIn(secret, json.dumps(view))
        self.assertNotIn(secret, (self.cache / 'fleet-actions.json').read_text())

    def test_source_policy_rejects_regular_protected_files_before_read(self):
        for relative in ['credentials.json', 'nested/.env', 'nested/settings.json', 'nested/config.toml', 'nested/e2e-truth-fixture/source.json']:
            with self.subTest(relative=relative):
                path = self.state / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('SYNTHETIC-PROTECTED-CONTENT')
                sources = {}
                with patch.object(fleet_data.os, 'open', wraps=os.open) as opened:
                    raw, receipt = fleet_data._read_source(path, self.state, sources)
                self.assertFalse(any(call.args[0] == path.name for call in opened.call_args_list), 'A protected source must be refused before opening its content.')
                self.assertIsNone(raw)
                self.assertEqual(receipt['status'], 'unavailable')
                self.assertIsNone(receipt['sha256'])
                self.assertEqual(sources[str(path)], receipt)

    def test_actions_refreshes_before_ten_minute_timer_boundary(self):
        self.collect()
        self.collect(539)
        self.assertEqual(sum(command[0] == 'gh' for command in self.runner.commands), 1)
        view = self.collect(540)
        self.assertEqual(sum(command[0] == 'gh' for command in self.runner.commands), 2)
        self.assertEqual(view['actions']['cache_ttl_seconds'], 540)

    def test_cache_attempt_and_read_times_are_taken_after_lock_acquisition(self):
        self.cache.mkdir()
        completed_lock = threading.Event()
        def acquire(descriptor, operation):
            if operation == fleet_data.fcntl.LOCK_EX:
                completed_lock.set()
        def clock():
            return self.now + 50 if completed_lock.is_set() else self.now
        with patch.object(fleet_data.fcntl, 'flock', side_effect=acquire), patch.object(fleet_data.time, 'time', side_effect=clock):
            view = fleet_data.collect(self.state, self.cache, self.root, self.runner)
        cached = json.loads((self.cache / 'fleet-actions.json').read_text())
        self.assertEqual(cached['attempt_epoch'], self.now + 50)
        self.assertEqual(view['actions']['read_utc'], fleet_data._utc(self.now + 50))

    def test_a_refresh_started_before_a_completed_peer_reuses_the_newer_cache(self):
        self.collect(50)
        self.runner.commands.clear()
        acquired = threading.Event()
        def lock(descriptor, operation):
            if operation == fleet_data.fcntl.LOCK_EX:
                acquired.set()
        def clock():
            return self.now + 51 if acquired.is_set() else self.now
        with patch.object(fleet_data.fcntl, 'flock', side_effect=lock), patch.object(fleet_data.time, 'time', side_effect=clock):
            view = fleet_data.collect(self.state, self.cache, self.root, self.runner)
        self.assertFalse(any(command[0] == 'gh' for command in self.runner.commands))
        cached = json.loads((self.cache / 'fleet-actions.json').read_text())
        self.assertEqual(cached['attempt_epoch'], self.now + 50)
        self.assertEqual(view['actions']['cache_age_seconds'], 1)

    def test_underscore_and_hyphen_delimited_prefixes_are_private_workflow_labels(self):
        names = ['Review_ghp_fixture', 'Review-sk-fixture']
        directory = self.root / '.github/workflows'
        for index, name in enumerate(names):
            (directory / f'secret-boundary-{index}.yml').write_text(f'name: "{name}"\njobs:\n  audit:\n    steps:\n      - uses: anthropics/claude-code-action@pin\n')
        self.runner.runs = [{'workflowName': name, 'status': 'queued', 'databaseId': index + 1} for index, name in enumerate(names)]
        view = self.collect()
        for name in names:
            self.assertNotIn(name, json.dumps(view['actions']))
            self.assertNotIn(name, (self.cache / 'fleet-actions.json').read_text())

    def test_all_rejected_nonempty_rosters_are_unknown_when_no_fallback_exists(self):
        (self.state / 'coordination/ns2604-coop/watchers/fleet-now.json').unlink()
        rejected = {
            'lanes_live': [{'lane': 'not a publishable lane'}],
            'lanes_parked': ['not a publishable lane'],
            'claude_sessions': [{'name': 'not a publishable session'}],
            'pool_accounts': [{'account': 'not a publishable account'}],
        }
        for field, values in rejected.items():
            with self.subTest(field=field):
                original = self.direct[field]
                self.direct[field] = values
                try:
                    view = self.collect()
                    self.assertIsNone(view[field])
                    self.assertEqual(view['availability'][field]['status'], 'not reported')
                    self.assertIsNotNone(view['availability'][field]['reason'])
                    if field in view['section_counts']:
                        self.assertIsNone(view['section_counts'][field])
                finally:
                    self.direct[field] = original

    def test_rejected_direct_roster_can_use_a_valid_dated_snapshot(self):
        self.direct['lanes_live'] = [{'lane': 'not a publishable lane'}]
        view = self.collect()
        self.assertEqual(view['lanes_live'][0]['lane'], 'g5-stars-gap')
        self.assertEqual(view['availability']['lanes_live']['status'], 'snapshot fallback')
        self.assertEqual(view['availability']['lanes_live']['read_utc'], self.snapshot['at'])

    def test_all_rejected_named_subagent_groups_do_not_claim_a_known_count(self):
        self.direct['claude_subagents_running']['cc'] = ['not a publishable name']
        self.snapshot['claude_subagents_running']['cc'] = ['not a publishable name']
        self.write_json('coordination/ns2604-coop/watchers/fleet-now.json', self.snapshot)
        native = self.collect()['claude_subagents_running']['native_cc']
        self.assertIsNone(native['names'])
        self.assertIsNone(native['count'])
        self.assertIsNone(native['read_utc'])
        self.assertEqual(native['source'], 'unavailable')

    def test_overflowing_native_run_and_cache_dates_leave_other_observations_available(self):
        low = '0001-01-01T00:00:00+00:01'
        high = '9999-12-31T23:59:59-00:01'
        self.direct['at'] = low
        self.runner.runs = [{'workflowName': 'harness-audit', 'status': 'queued', 'databaseId': 123, 'startedAt': low, 'updatedAt': high}]
        self.cache.mkdir()
        (self.cache / 'fleet-actions.json').write_text(json.dumps({'schema': 'local-fleet-actions/1', 'attempt_epoch': self.now, 'read_utc': low, 'runs': self.runner.runs}))
        view = self.collect()
        self.assertEqual(view['fleet_source'], 'direct native')
        self.assertIsNone(view['at'])
        self.assertEqual(view['lanes_live'][0]['lane'], 'g5-stars-gap')
        self.assertIsNone(view['actions']['read_utc'])
        self.assertIsNone(view['actions']['cache_age_seconds'])
        self.assertEqual(len(view['actions']['runs']), 1)
        self.assertIsNone(view['actions']['runs'][0]['startedAt'])
        self.assertIsNone(view['actions']['runs'][0]['updatedAt'])
        self.assertEqual(fleet_data._stamp('0001-01-01T00:00:00Z'), '0001-01-01T00:00:00Z')
        self.assertEqual(fleet_data._stamp('2026-10-08T23:10:00+01:00'), '2026-10-08T22:10:00Z')
        cached = json.loads((self.cache / 'fleet-actions.json').read_text())
        cached['read_utc'] = '0001-01-01T00:00:00Z'
        (self.cache / 'fleet-actions.json').write_text(json.dumps(cached))
        supported = self.collect()['actions']
        self.assertEqual(supported['read_utc'], '0001-01-01T00:00:00Z')
        self.assertGreater(supported['cache_age_seconds'], 1_000_000_000)

    def test_cache_age_timestamp_overflow_is_unknown_without_dropping_cache_rows(self):
        self.runner.runs = [{'workflowName': 'harness-audit', 'status': 'queued', 'databaseId': 123}]
        self.collect()
        real_datetime = fleet_data.datetime
        class TimestampUnavailable:
            def __init__(self, parsed):
                self.parsed = parsed
            @property
            def tzinfo(self):
                return self.parsed.tzinfo
            def astimezone(self, zone):
                return self.parsed.astimezone(zone)
            def timestamp(self):
                raise OverflowError('Synthetic platform timestamp boundary')
        class DateFacade:
            fromtimestamp = staticmethod(real_datetime.fromtimestamp)
            @staticmethod
            def fromisoformat(value):
                return TimestampUnavailable(real_datetime.fromisoformat(value))
        with patch.object(fleet_data, 'datetime', DateFacade):
            view = self.collect(1)
        self.assertEqual(view['actions']['read_utc'], self.direct['at'])
        self.assertIsNone(view['actions']['cache_age_seconds'])
        self.assertEqual(view['actions']['runs'][0]['databaseId'], 123)
        self.assertEqual(view['fleet_source'], 'direct native')
        self.assertEqual(sum(command[0] == 'gh' for command in self.runner.commands), 1)

    def test_actions_observation_completes_before_a_timed_out_producer(self):
        def transport(command, **kwargs):
            if command[0] == sys.executable:
                self.assertTrue((self.cache / 'fleet-actions.json').exists(), 'Actions observation was deferred behind the producer.')
                self.assertEqual(sum(previous[0] == 'gh' for previous in self.runner.commands), 1)
                raise subprocess.TimeoutExpired(command, kwargs['timeout'])
            return self.runner(command, **kwargs)
        with patch.object(fleet_data.time, 'time', return_value=self.now):
            view = fleet_data.collect(self.state, self.cache, self.root, transport)
        self.assertEqual(view['fleet_source'], 'snapshot fallback')
        self.assertEqual(view['actions']['read_utc'], self.direct['at'])
        producer = next(row for row in view['source_inputs'] if row['type'] == 'native Fleet producer')
        self.assertEqual(producer['execution']['status'], 'timed out')


class FleetProducerReviewRegressionTests(unittest.TestCase):
    def test_actual_cwd_tokenize_shadow_does_not_execute_in_verified_child(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / 'approved' / 'fleet_block.py'
            source.parent.mkdir()
            (source.parent / 'sibling.py').write_text('VALUE = 17\n')
            cwd = base / 'cwd'
            cwd.mkdir()
            sentinel = base / 'shadow-executed'
            (cwd / 'tokenize.py').write_text(f'from pathlib import Path\nPath({str(sentinel)!r}).write_text("shadow executed")\nraise RuntimeError("CWD shadow")\n')
            raw = b'import json\nfrom sibling import VALUE\nprint(json.dumps({"verified": VALUE}))\n'
            receipt = {}
            def transport(command, **kwargs):
                return subprocess.run(command, cwd=cwd, **kwargs)
            result = fleet_data._execute_producer(source, raw, receipt, transport)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(sentinel.exists())
            self.assertEqual(json.loads(result.stdout), {'verified': 17})
            self.assertEqual(receipt['execution']['status'], 'completed')

    def test_producer_timeout_cleans_up_a_real_descendant_process_group(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            sentinel = base / 'descendant-pid'
            raw = (
                'import subprocess, sys, time\n'
                'from pathlib import Path\n'
                'child = subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(120)"])\n'
                f'Path({str(sentinel)!r}).write_text(str(child.pid))\n'
                'time.sleep(120)\n'
            ).encode()
            receipt = {}
            runner = getattr(fleet_data, '_run_producer', subprocess.run)
            started = time.monotonic()
            try:
                with patch.object(fleet_data, 'PRODUCER_TIMEOUT_SECONDS', 0.4, create=True):
                    with self.assertRaises(subprocess.TimeoutExpired):
                        fleet_data._execute_producer(base / 'fleet_block.py', raw, receipt, runner)
                self.assertLess(time.monotonic() - started, 3)
                self.assertTrue(sentinel.exists(), 'The actual producer must have spawned its descendant.')
                pid = int(sentinel.read_text())
                status = Path(f'/proc/{pid}/stat')
                active = status.exists() and status.read_text().split()[2] != 'Z'
                self.assertFalse(active, 'The producer descendant survived timeout.')
            finally:
                if sentinel.exists():
                    try:
                        os.kill(int(sentinel.read_text()), 9)
                    except ProcessLookupError:
                        pass


if __name__ == '__main__':
    unittest.main()
