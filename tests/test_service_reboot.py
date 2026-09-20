"""Contract/failure tests only: no guest, installation, reboot or native Dagu."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'blueprints/convergence-practice/service-reboot'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


DRIVER = module('service_reboot_driver', HERE / 'run.py')
FIXTURE = module('service_reboot_original_fixture', HERE.parent / 'job-recovery/fixture.py')


class LauncherArgumentsTests(unittest.TestCase):
    def test_serial_is_on_native_device_with_same_persistent_disk(self):
        # Regression against QEMU8.2.2 virtio-blk.c's serial device property and
        # its virtio-blk-test.c separate if=none/id backend pattern.
        private = Path('/owned/private')
        args = DRIVER.qemu_arguments(private / 'persistent.qcow2', private, Path('/owned/serial.log'), 2222)
        drives = [args[i + 1] for i, value in enumerate(args) if value == '-drive']
        devices = [args[i + 1] for i, value in enumerate(args) if value == '-device']
        disk = next(value for value in drives if 'persistent.qcow2' in value)
        self.assertIn('file=/owned/private/persistent.qcow2', disk)
        self.assertIn('if=none,id=service-reboot-disk', disk)
        self.assertNotIn('serial=', disk)
        self.assertIn('virtio-blk-pci,drive=service-reboot-disk,serial=native-reboot-disk', devices)
        self.assertIn('user,id=net0,restrict=on,hostfwd=tcp:127.0.0.1:2222-:22', args)
        self.assertEqual(sum('readonly=on' in value for value in drives), 2)
        self.assertNotIn('-snapshot', args)

    def test_missing_native_device_property_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'serial'):
            DRIVER.verify_block_device_help('virtio-blk-pci options:\n  drive=<str>\n')

    @unittest.skipUnless(shutil.which('qemu-system-x86_64'), 'QEMU unavailable locally; hosted preflight is mandatory')
    def test_native_device_help_exposes_backend_and_serial_without_boot(self):
        result = subprocess.run(['qemu-system-x86_64', '-device', 'virtio-blk-pci,help'],
                                capture_output=True, text=True, timeout=10, check=True)
        DRIVER.verify_block_device_help(result.stdout + result.stderr)


class ServiceRebootTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        (self.work / 'source').mkdir()
        for name, kind in [('planner.py', 'accepted'), ('test_planner.py', 'seed')]:
            shutil.copyfile(HERE.parent / 'native-worker' / kind / name, self.work / 'source' / name)
        FIXTURE.exclusive(self.work / 'expected.json', FIXTURE.source_hashes(self.work))
        FIXTURE.checkpoint(self.work)
        self.before = {'boot_id': 'initial-boot', 'machine_id_sha256': 'same-machine',
                       'filesystem_uuid': 'same-filesystem', 'disk_token': 'same-disk',
                       'run_id': 'same-native-run', 'checkpoint_sha256': DRIVER.digest(self.work / 'checkpoint.json'),
                       'claim_sha256': DRIVER.digest(self.work / 'checkpoint-started.json'),
                       'native_status': 'running', 'effect_count': 0}
        (self.work / 'release-finalize').touch()
        FIXTURE.finalize(self.work)
        self.after = dict(self.before, boot_id='later-boot', native_status='succeeded', effect_count=1,
                          completed_sha256=DRIVER.digest(self.work / 'completed.json'))
        self.observations = []
        for phase, value in [('before', self.before), ('after', self.after)]:
            DRIVER.write_json(self.work / (phase + '.json'), value)
            DRIVER.write_json(self.work / ('history-' + phase + '.stdout'),
                              [{'dagRunId': value['run_id'], 'status': value['native_status']}])
            self.observations.append({'phase': phase, 'boot_id': value['boot_id'],
                                      'record_sha256': DRIVER.digest(self.work / (phase + '.json')),
                                      'linger': True, 'user_manager': 'active'})
        self.host = {'disk_before': [1, 2], 'disk_after': [1, 2],
                     'qemu_before': [10, '100'], 'qemu_after': [10, '100'],
                     'events': {'before_observed': 1, 'reboot_requested': 2,
                                'after_observed': 3, 'postboot_ssh_started': 4}}
        self.frozen = {'payload_hashes': FIXTURE.source_hashes(self.work)}
        (self.work / 'reboot.yaml').write_text('frozen test workflow\n')
        (self.work / 'config.yaml').write_text('check_updates: false\n')
        DRIVER.write_json(self.work / 'freeze.json', {'source_hashes': self.frozen['payload_hashes'],
                          'workflow_sha256': DRIVER.digest(self.work / 'reboot.yaml'),
                          'config_sha256': DRIVER.digest(self.work / 'config.yaml')})
        (self.work / 'retry.exit').write_text('0\n')

    def check(self):
        return DRIVER.check_evidence(self.before, self.after, self.observations, self.host)

    def audit(self):
        return DRIVER.audit_guest(self.work, self.observations, self.host, self.frozen)

    def test_complete_contract_accepts_original_oracle_and_exclusive_effect(self):
        result = self.audit()
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['checkpoint_tests'], 12)
        self.assertEqual(result['final_tests'], 12)
        self.assertFalse(result['token_savings_claim'])

    def test_same_kernel_boot_is_rejected(self):
        self.after['boot_id'] = self.before['boot_id']
        with self.assertRaisesRegex(ValueError, 'boot ID'):
            self.check()

    def test_replacement_disk_guest_or_run_is_rejected(self):
        for key in ('machine_id_sha256', 'filesystem_uuid', 'disk_token', 'run_id'):
            with self.subTest(key=key):
                changed = dict(self.after, **{key: 'replacement'})
                with self.assertRaisesRegex(ValueError, 'Persistent identity'):
                    DRIVER.check_evidence(self.before, changed, self.observations, self.host)

    def test_replaced_disk_inode_and_reused_qemu_pid_are_rejected(self):
        for key, value in [('disk_after', [1, 3]), ('qemu_after', [10, '101'])]:
            host = copy.deepcopy(self.host)
            host[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'replaced'):
                DRIVER.check_evidence(self.before, self.after, self.observations, host)

    def test_ssh_before_automatic_recovery_is_rejected(self):
        self.host['events']['postboot_ssh_started'] = 2.5
        with self.assertRaisesRegex(ValueError, 'SSH preceded'):
            self.check()

    def test_missing_linger_or_inactive_manager_is_rejected(self):
        for key, value in [('linger', False), ('user_manager', 'inactive')]:
            records = copy.deepcopy(self.observations)
            records[1][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'lingering'):
                DRIVER.check_evidence(self.before, self.after, records, self.host)

    def test_missing_or_duplicate_completion_observation_is_rejected(self):
        for records in (self.observations[:1], self.observations + [self.observations[1]]):
            with self.assertRaisesRegex(ValueError, 'observation missing'):
                DRIVER.check_evidence(self.before, self.after, records, self.host)

    def test_finished_preboot_and_missing_final_effect_are_rejected(self):
        self.before['effect_count'] = 1
        with self.assertRaisesRegex(ValueError, 'unfinished'):
            self.check()
        self.before['effect_count'] = 0
        self.after['effect_count'] = 0
        with self.assertRaisesRegex(ValueError, 'one effect'):
            self.check()

    def test_native_history_cannot_substitute_another_run(self):
        DRIVER.write_json(self.work / 'history-after.stdout', [{'dagRunId': 'different-run', 'status': 'succeeded'}])
        with self.assertRaisesRegex(ValueError, 'Native history'):
            self.audit()

    def test_native_failed_status_is_not_accepted(self):
        DRIVER.write_json(self.work / 'history-after.stdout', [{'dagRunId': 'same-native-run', 'status': 'failed'}])
        with self.assertRaisesRegex(ValueError, 'Native history'):
            self.audit()

    def test_changed_oracle_bytes_and_truncated_test_log_are_rejected(self):
        (self.work / 'final-tests.log').write_text('OK\n')
        with self.assertRaisesRegex(ValueError, '12-test oracle'):
            self.audit()
        (self.work / 'source/test_planner.py').write_text('# removed tests\n')
        with self.assertRaisesRegex(ValueError, 'oracle changed'):
            self.audit()

    def test_duplicate_checkpoint_and_effect_fail_exclusively(self):
        before = (self.work / 'checkpoint.json').read_bytes()
        with self.assertRaises(FileExistsError):
            FIXTURE.checkpoint(self.work)
        with self.assertRaises(FileExistsError):
            FIXTURE.finalize(self.work)
        self.assertEqual((self.work / 'checkpoint.json').read_bytes(), before)

    def test_forged_count_and_changed_native_configuration_are_rejected(self):
        checkpoint = json.loads((self.work / 'checkpoint.json').read_text())
        checkpoint['execution_count'] = 2
        DRIVER.write_json(self.work / 'checkpoint.json', checkpoint)
        with self.assertRaisesRegex(ValueError, 'execution count'):
            self.audit()

    def test_changed_native_configuration_is_rejected(self):
        (self.work / 'reboot.yaml').write_text('replacement workflow\n')
        with self.assertRaisesRegex(ValueError, 'configuration changed'):
            self.audit()

    def test_changed_serial_record_and_failed_retry_are_rejected(self):
        self.observations[1]['record_sha256'] = 'wrong-hash'
        with self.assertRaisesRegex(ValueError, 'Serial observation'):
            self.audit()
        self.observations[1]['record_sha256'] = DRIVER.digest(self.work / 'after.json')
        (self.work / 'retry.exit').write_text('1\n')
        with self.assertRaisesRegex(ValueError, 'Native retry failed'):
            self.audit()

    def test_partial_serial_line_cannot_trigger_reconnection(self):
        self.assertEqual(DRIVER.observer_records('boot logs\nNATIVE_REBOOT_OBSERVER {"phase":'), [])

    def test_driver_refuses_existing_desktop_before_creating_state(self):
        destination = self.work / 'refused'
        with mock.patch.dict('os.environ', {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'disposable GitHub-hosted'):
                DRIVER.run(destination)
        self.assertFalse(destination.exists())

    def test_driver_refuses_reused_directory(self):
        with self.assertRaisesRegex(ValueError, 'new absolute path'):
            DRIVER.run(self.work)


if __name__ == '__main__':
    unittest.main()
