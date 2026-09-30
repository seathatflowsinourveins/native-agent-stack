"""Offline recipe contracts, not upstream or provider acceptance.

Sources inspected before authoring: unclecode/crawl4ai v0.9.4 release,
pyproject.toml, utils.py:1820-1837, extraction_strategy.py:556-691,
docs/examples/llm_extraction_openai_pricing.py, docs/md_v2/core/fit-markdown.md;
adoption/templates/codex{,.stack-worker}.config.toml. Public seams and
fail-first workflow were specified in the user's runtime-worker task.
"""

import json
import hashlib
import importlib.util
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import io
from contextlib import redirect_stdout
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "blueprints/runtime-workers/crawl4ai"


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, RECIPE / relative)
    imported = importlib.util.module_from_spec(spec)
    path = RECIPE / relative
    with patch.dict(sys.modules), patch.object(sys, "path", [str(path.parent), *sys.path]):
        for key, value in list(sys.modules.items()):
            location = getattr(value, "__file__", None)
            if location and Path(location).is_relative_to(ROOT / "blueprints/runtime-workers") \
                    and not Path(location).is_relative_to(RECIPE):
                del sys.modules[key]
        spec.loader.exec_module(imported)
    return imported


class Crawl4AIRecipeTests(unittest.TestCase):
    def test_default_dispatch_crawls_without_gateway_model_or_extraction(self):
        dispatch = module('crawl4ai_default_dispatch', 'dispatch.py')
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            state = Path(directory)
            with patch.object(dispatch, 'locations', return_value=(state / 'prefix', state)), \
                    patch.object(dispatch, 'arm_settings', side_effect=AssertionError('gateway unused')), \
                    patch.object(dispatch.subprocess, 'Popen'):
                self.assertEqual(dispatch.main(['start', '--run-id', 'default-crawl', '--url', 'https://example.com/']), 0)
            run = state / 'runs/default-crawl'
            self.assertEqual(json.loads((run / 'request.json').read_text())['kind'], 'crawl')
            with patch.object(dispatch, 'locations', return_value=(state / 'prefix', state)), \
                    patch.object(dispatch, 'arm_settings', side_effect=AssertionError('gateway unused')), \
                    patch.object(dispatch, 'crawl_job', return_value=({'passed': True}, 0)):
                self.assertEqual(dispatch.execute(run, 'control'), 0)
            receipt = json.loads((run / 'receipt.json').read_text())
            self.assertFalse(receipt['llm_used'])
            self.assertEqual(receipt['route_applicability'], 'separate_responses_caller_only')
            self.assertNotIn('model', receipt)
            self.assertNotIn('base_url', receipt)

    def test_rest_job_dispatch_uses_native_status_and_never_exposes_job_ids(self):
        with patch.dict(sys.modules, {'host': module('crawl4ai_host', 'host.py'),
                                     'worker': module('crawl4ai_worker', 'worker.py')}):
            dispatch = module('crawl4ai_dispatch', 'dispatch.py')
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            replies = [({'task_id':'crawl_1234abcd'},202), ({'status':'processing'},200),
                       ({'status':'completed','result':{'success':True,'results':[{'success':True,'markdown':'content'}]}},200)]
            with patch.object(dispatch,'api_request',side_effect=replies) as api, patch.object(dispatch.time,'sleep'):
                receipt, code = dispatch.crawl_job(work, ['https://example.com/'])
            self.assertEqual(code,0)
            self.assertTrue(receipt['passed'])
            self.assertNotIn('crawl_1234abcd',json.dumps(receipt))
            self.assertEqual(api.call_args_list[0].args, ('/crawl/job', {'urls':['https://example.com/']}))
            self.assertEqual(api.call_args_list[1].args, ('/crawl/job/crawl_1234abcd',))
            self.assertEqual(json.loads((work/'result.json').read_text())['success'],True)
            for response, expected in [({'status':'failed','error':'PRIVATE'},3),
                                       ({'status':'completed','result':{}},4),
                                       ({'status':'completed','result':{'success':False,'results':[{'success':False}]}},3)]:
                with patch.object(dispatch,'api_request',side_effect=[({'task_id':'crawl_1234abcd'},202),(response,200)]):
                    result, code = dispatch.crawl_job(work, ['https://example.com/'])
                self.assertEqual(code,expected)
                self.assertNotIn('PRIVATE',json.dumps(result))
            with patch.object(dispatch,'api_request',side_effect=[({'task_id':'crawl_1234abcd'},202),OSError('private network detail')]):
                result, code = dispatch.crawl_job(work, ['https://example.com/'])
            self.assertEqual(code,4)
            self.assertEqual(result['native_status'],'unobserved_after_enqueue')
            self.assertNotIn('private network detail',json.dumps(result))

    def test_mcp_registration_uses_explicit_sse_and_dynamic_private_headers(self):
        with patch.dict(sys.modules, {'host': module('crawl4ai_host', 'host.py')}):
            mcp = module('crawl4ai_mcp_config', 'mcp-config.py')
        with patch.object(mcp,'load_host',return_value={'api_port':3730}), \
                patch.object(mcp,'locations',return_value=(Path('/owned/prefix'),Path('/owned/state'))):
            config = mcp.configuration()
        self.assertEqual(config['type'],'sse')
        self.assertEqual(config['url'],'http://127.0.0.1:3730/mcp/sse')
        self.assertEqual(config['timeout'],180000)
        self.assertIn('mcp-config.py headers',config['headersHelper'])
        self.assertNotIn('headers',config)

    def test_e2e_setup_failure_writes_receipt_before_host_resources(self):
        with patch.object(sys, 'path', [str(RECIPE/'e2e'), str(RECIPE), *sys.path]):
            run = module('crawl4ai_run', 'e2e/run.py')
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()), \
                patch.object(run, 'load_host', side_effect=ValueError('private details')), \
                patch.object(run.subprocess, 'run') as external:
            self.assertEqual(run.main(['--run-dir', directory, '--arm', 'engines-on']), 2)
            status = json.loads((Path(directory)/'status.json').read_text())
            receipt = json.loads((Path(directory)/'receipt.json').read_text())
            self.assertEqual(status['arm'], 'engines-on')
            self.assertEqual(status['state'], 'finished')
            self.assertEqual(receipt['outcome'], 'setup_failure')
            self.assertNotIn('private details', json.dumps(receipt))
            self.assertEqual([a['arm'] for a in receipt['arms']], ['engines-on'])
            external.assert_not_called()

    def test_damaged_config_still_leaves_a_setup_receipt(self):
        with patch.object(sys, 'path', [str(RECIPE/'e2e'), str(RECIPE), *sys.path]):
            run = module('crawl4ai_run', 'e2e/run.py')
        read = Path.read_text
        def unreadable_config(path, *args, **kwargs):
            if path == RECIPE / 'config/worker.json':
                raise ValueError('damaged configuration')
            return read(path, *args, **kwargs)
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()), \
                patch.object(Path,'read_text',unreadable_config):
            self.assertEqual(run.main(['--run-dir',directory,'--arm','control']),2)
            self.assertEqual(json.loads((Path(directory)/'receipt.json').read_text())['outcome'],'setup_failure')

    def test_dispatch_has_deterministic_status_and_distinct_verdicts(self):
        with patch.dict(sys.modules, {'host': module('crawl4ai_host', 'host.py'),
                                     'worker': module('crawl4ai_worker', 'worker.py')}):
            dispatch = module('crawl4ai_dispatch', 'dispatch.py')
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            root = Path(directory)
            with patch.object(dispatch, 'locations', return_value=(root / 'prefix', root)), \
                    patch.object(dispatch.subprocess, 'Popen', side_effect=FileNotFoundError):
                code = dispatch.main(['start', '--run-id', 'child-001', '--arm', 'engines-on'])
            self.assertEqual(code, 2)
            run = root / 'runs/child-001'
            status = json.loads((run / 'status.json').read_text())
            self.assertEqual(status['arm'], 'engines-on')
            self.assertEqual(status['receipt_path'], str(run / 'receipt.json'))
            self.assertEqual(json.loads((run / 'receipt.json').read_text())['outcome'], 'setup_failure')
            for outcome, expected in [('setup_failure',2),('negative_verdict',3),('incomplete_evidence',4),('pass',0)]:
                dispatch.finish(run, {'outcome':outcome,'passed':expected==0}, expected)
                with patch.object(dispatch, 'locations', return_value=(root/'prefix', root)):
                    self.assertEqual(dispatch.main(['result','--run-id','child-001','--arm','engines-on']),expected)
                    self.assertEqual(dispatch.main(['wait','--run-id','child-001','--arm','engines-on','--timeout','0']),expected)
            with patch.object(dispatch, 'locations', return_value=(root/'prefix',root)), patch.object(dispatch.subprocess,'Popen') as spawn:
                self.assertEqual(dispatch.main(['start','--run-id','child-001','--arm','engines-on']),0)
                spawn.assert_not_called()
                self.assertEqual(dispatch.main(['result','--run-id','child-001','--arm','control']),2)
                self.assertEqual(dispatch.main(['start','--run-id','../escape','--arm','control']),2)

    def test_engines_usage_comes_from_its_entry_database_only(self):
        with patch.dict(sys.modules, {'grade': module('crawl4ai_grade', 'e2e/grade.py')}):
            receipt = module('crawl4ai_receipt', 'e2e/receipt.py')
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            databases = {}
            for arm, tokens in [('control',9999),('engines-on',120)]:
                database = work / (arm + '.sqlite')
                databases[arm] = database
                with closing(sqlite3.connect(database)) as db, db:
                    db.execute('CREATE TABLE call_logs (timestamp, path, status, model, reasoning_effort_requested, reasoning_effort_upstream, tokens_in, tokens_cache_read, tokens_reasoning, correlation_id)')
                    for second in (1,2,3):
                        db.execute('INSERT INTO call_logs VALUES (?,?,?,?,?,?,?,?,?,?)',
                            (f'2026-09-27T12:00:0{second}Z','/v1/chat/completions',200,'gpt-6-astra-max',
                             'max','max',tokens,0,5,'PRIVATE'))
            (work/'run.json').write_text(json.dumps({'selected_arms':['engines-on'], 'arms':{
                'engines-on':{'model':'sharedgw/gpt-6-astra-max','start':'2026-09-27T12:00:00Z','end':'2026-09-27T12:00:10Z'}}}))
            result = receipt.make_receipt(work, databases)
            rows = result['arms'][0]['gateway']['rows']
            self.assertEqual([row['tokens_in'] for row in rows],[120,120,120])
            self.assertNotIn('9999',json.dumps(result))


    def test_grader_install_uses_integrity_lock_without_lifecycle_scripts(self):
        installer = (RECIPE / 'install.sh').read_text()
        self.assertIn('npm ci --ignore-scripts', installer)
        self.assertNotIn('npm install --global', installer)
        package = json.loads((RECIPE / 'grader/package.json').read_text())
        lock_path = RECIPE / 'grader/package-lock.json'
        lock = json.loads(lock_path.read_text())
        self.assertEqual(package['dependencies'], {'promptfoo': '0.123.1'})
        self.assertEqual(lock['packages']['']['dependencies'], package['dependencies'])
        self.assertEqual(lock['packages']['node_modules/promptfoo']['version'], '0.123.1')
        for name, entry in lock['packages'].items():
            if name:
                self.assertRegex(entry['integrity'], r'^sha512-')
                self.assertTrue(entry['resolved'].startswith('https://registry.npmjs.org/'))
        pins = json.loads((RECIPE / 'pins.json').read_text())
        self.assertEqual(pins['grader']['lock_sha256'], hashlib.sha256(lock_path.read_bytes()).hexdigest())
        self.assertIn('/grader/node_modules/.bin/promptfoo', (RECIPE / 'common.sh').read_text())

    def test_container_hardening_and_arm_base_url_are_effective(self):
        compose = (RECIPE / 'config/compose.yaml').read_text()
        for setting in ['cap_drop: [ALL]', 'no-new-privileges:true', 'read_only: true', 'tmpfs:',
                        '${CRAWL4AI_CONTAINER_BASE_URL:?']:
            self.assertIn(setting, compose)
        self.assertNotIn('http://10.0.2.2:20128/v1', compose)
        self.assertIn('--field container_base_url', (RECIPE / 'container.sh').read_text())
        supervisor = (RECIPE / 'config/supervisord.conf').read_text()
        self.assertEqual(supervisor.count('user=appuser'), 2)
        self.assertIn('PYTHONDONTWRITEBYTECODE', compose)
        entrypoint = (RECIPE / 'container-entrypoint.sh').read_text()
        self.assertLess(entrypoint.index('chown 0:0'), entrypoint.index('chmod 0700'))
        self.assertLess(entrypoint.index('chmod 0700'), entrypoint.index('chown appuser:appuser'))

    def test_response_correlation_is_captured_without_exporting_other_headers(self):
        from types import SimpleNamespace
        worker = module('crawl4ai_worker', 'worker.py')
        ids = []
        hook = worker.correlation_hook(ids)
        hook(SimpleNamespace(headers={'x-correlation-id': 'entry-123', 'Authorization': 'PRIVATE'}))
        hook(SimpleNamespace(headers={}))
        self.assertEqual(ids, ['entry-123', None])
        args = worker.extraction_args(json.loads((RECIPE / 'config/worker.json').read_text()),
                                      'engines-on', {}, 'session', client='native-client')
        self.assertEqual(args['client'], 'native-client')

    def test_entry_gateway_filters_correlations_and_reports_conditional_effort(self):
        with patch.dict(sys.modules, {'grade': module('crawl4ai_grade', 'e2e/grade.py')}):
            receipt = module('crawl4ai_receipt', 'e2e/receipt.py')
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'entry.sqlite'
            with closing(sqlite3.connect(database)) as db, db:
                db.execute('CREATE TABLE call_logs (timestamp, path, status, model, tokens_in, tokens_cache_read, tokens_reasoning, correlation_id, reasoning_effort_requested, reasoning_effort_upstream, prompt)')
                for cid, model, path, tokens, effort in [('own-1','gpt-6-astra-max','/v1/chat/completions',10,'max'),
                        ('own-2','sharedgw/gpt-6-astra-max','/v1/chat/completions',0,None),
                        ('other','gpt-6-astra-max','/v1/chat/completions',999,'low'),
                        ('own-1','gpt-6-astra-max','/v1/models',0,None)]:
                    db.execute('INSERT INTO call_logs VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                               ('2026-09-27T12:00:05Z',path,200,model,120,None,tokens,cid,effort,effort,'PRIVATE'))
            before = database.read_bytes()
            observed = receipt.gateway_rows(database,'2026-09-27T12:00:00Z','2026-09-27T12:00:10Z',
                models=['gpt-6-astra-max','sharedgw/gpt-6-astra-max'], correlations=['own-1','own-2'])
            self.assertEqual(len(observed['rows']), 2)
            self.assertEqual(observed['attribution'], 'entry gateway correlation + window + model + path')
            self.assertNotIn('correlation_id', json.dumps(observed))
            self.assertNotIn('PRIVATE', json.dumps(observed))
            self.assertEqual(database.read_bytes(), before)
            effort = receipt.effort_observation(observed['rows'], 'max')
            self.assertTrue(effort['passed'])
            self.assertEqual(effort['no_returned_reasoning_count'], 1)
            observed['rows'][0]['reasoning_effort_requested'] = 'low'
            self.assertFalse(receipt.effort_observation(observed['rows'], 'max')['passed'])
            observed['rows'][0]['reasoning_effort_requested'] = None
            self.assertFalse(receipt.effort_observation(observed['rows'], 'max')['passed'])
            absent = receipt.gateway_rows(Path(directory)/'absent.sqlite','2026-09-27T12:00:00Z',
                '2026-09-27T12:00:10Z',models=['gpt-6-astra-max'])
            self.assertEqual(absent['status'],'unavailable')
            self.assertFalse((Path(directory)/'absent.sqlite').exists())

    def test_explicit_arms_route_and_effort_are_bound_together(self):
        worker = module('crawl4ai_worker', 'worker.py')
        config = json.loads((RECIPE / 'config/worker.json').read_text())
        schema = json.loads((RECIPE / 'e2e/schema.json').read_text())
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(worker.selected_arm(), 'control')
            for arm, port, model in [('control', 20128, 'cx/gpt-6-astra-max'),
                                     ('engines-on', 20129, 'sharedgw/gpt-6-astra-max')]:
                route = worker.arm_settings(config, arm)
                self.assertEqual(route['base_url'], f'http://127.0.0.1:{port}/v1')
                self.assertEqual(route['container_base_url'], f'http://10.0.2.2:{port}/v1')
                self.assertEqual(route['model'], model)
                args = worker.extraction_args(config, arm, schema, 'session')
                self.assertEqual(args['reasoning_effort'], 'max')
                self.assertEqual(args['allowed_openai_params'], ['reasoning_effort'])
                self.assertEqual(args['max_retries'], 0)
                self.assertEqual(args['extra_headers'].get('x-omniroute-compression'),
                                 'allow-lossy' if arm == 'engines-on' else None)
            for bad in ['sharedgw/cx/gpt-6-astra-max', 'sharedgw/gpt-6-sol', 'cx/claude-opus-5-5']:
                with patch.dict(os.environ, {'CRAWL4AI_MODEL': bad}):
                    with self.assertRaises(ValueError):
                        worker.arm_settings(config, 'engines-on')
            for bad in ['http://127.0.0.1:20128/v1', 'https://example.com/v1',
                        'http://127.0.0.1:20129/v1?secret=x', 'http://user@127.0.0.1:20129/v1']:
                with patch.dict(os.environ, {'CRAWL4AI_BASE_URL': bad}):
                    with self.assertRaises(ValueError):
                        worker.arm_settings(config, 'engines-on')
        with patch.dict(os.environ, {'CRAWL4AI_ARM': 'engines-on'}, clear=True):
            self.assertEqual(worker.selected_arm(), 'engines-on')

    def test_recipe_is_reviewable_and_pinned(self):
        for name in ("README.md", "install.sh", "run-e2e.sh", "e2e/check.py",
                     "e2e/receipt.py", "config/worker.json", "pins.json",
                     "requirements.lock", "research.md"):
            self.assertTrue((RECIPE / name).is_file(), name)
        pins = json.loads((RECIPE / "pins.json").read_text())
        self.assertEqual(pins["version"], "0.9.4")
        self.assertEqual(pins['grader']['version'], '0.123.1')
        self.assertEqual(pins['grader']['repository'], 'https://github.com/promptfoo/promptfoo')
        installer = (RECIPE / 'install.sh').read_text()
        self.assertIn('--prefix "$NAS_CRAWL4AI_PREFIX/grader"', installer)
        self.assertIn('grader/package-lock.json', installer)
        self.assertRegex(pins["commit"], r"^[0-9a-f]{40}$")
        self.assertRegex(pins["image"], r"^unclecode/crawl4ai@sha256:[0-9a-f]{64}$")
        self.assertIn(pins["image"], (RECIPE / "config/compose.yaml").read_text())
        self.assertEqual(hashlib.sha256((RECIPE / "requirements.lock").read_bytes()).hexdigest(), pins["requirements_lock_sha256"])

    def test_gateway_model_is_configurable_and_has_no_sampling_default(self):
        config = json.loads((RECIPE / "config/worker.json").read_text())
        self.assertEqual(config["arms"]["control"]["base_url"], "http://127.0.0.1:20128/v1")
        self.assertEqual(config["arms"]["control"]["container_base_url"], "http://10.0.2.2:20128/v1")
        self.assertEqual(config["arms"]["control"]["model"], "cx/gpt-6-astra-max")
        self.assertEqual(config["arms"]["control"]["model_env"], "CRAWL4AI_MODEL")
        self.assertEqual(config["llm"]["api_token"], "local-loopback")
        self.assertEqual(config["arms"]["comparison"]["model"], "cx/gpt-6-sol")
        self.assertEqual(config["arms"]["comparison"]["expected_effort"], "medium")
        source = (RECIPE / "worker.py").read_text()
        self.assertNotIn('"cx/gpt-6-astra-max"', source)
        self.assertNotIn('"temperature": 0', source)
        self.assertIn('"temperature": None', source)
        self.assertIn("x-omniroute-session", source)
        self.assertIn("Idempotency-Key", source)
        self.assertIn("fit_markdown", source)

    def test_structured_requests_close_schemas_and_bind_logical_calls(self):
        worker = module('crawl4ai_worker', 'worker.py')
        config = json.loads((RECIPE / 'config/worker.json').read_text())
        schema = json.loads((RECIPE / 'e2e/schema.json').read_text())
        first = worker.extraction_args(config, 'primary', schema, 'conversation-a')
        second = worker.extraction_args(config, 'primary', schema, 'conversation-a')
        third = worker.extraction_args(config, 'comparison', schema, 'conversation-b')
        for args in (first, second, third):
            self.assertEqual(args['response_format']['type'], 'json_schema')
            response = args['response_format']['json_schema']
            self.assertIs(response['strict'], True)
            self.assertEqual(response['schema'], schema)
            self.assertTrue(args.get('temperature') is None or args['temperature'] > 0.1)
        def closed(value):
            if isinstance(value, dict):
                if value.get('type') == 'object':
                    self.assertIs(value.get('additionalProperties'), False)
                    self.assertEqual(set(value['required']), set(value['properties']))
                for child in value.values():
                    closed(child)
            elif isinstance(value, list):
                for child in value:
                    closed(child)
        closed(schema)
        headers = [args['extra_headers'] for args in (first, second, third)]
        self.assertEqual([h['x-omniroute-session'] for h in headers],
                         ['conversation-a', 'conversation-a', 'conversation-b'])
        self.assertEqual(len({h['Idempotency-Key'] for h in headers}), 3)
        self.assertEqual(third['reasoning_effort'], 'medium')

    def test_gateway_refuses_non_gpt6_model_overrides(self):
        worker = module('crawl4ai_worker', 'worker.py')
        config = json.loads((RECIPE / 'config/worker.json').read_text())
        for arm, key in (('primary', 'CRAWL4AI_MODEL'), ('comparison', 'CRAWL4AI_COMPARISON_MODEL')):
            for model in ('claude-opus-5-5', 'cx/claude-opus-5-5', 'cx/gpt-5', ''):
                with patch.dict(os.environ, {key: model}):
                    with self.assertRaises(ValueError):
                        worker.model_for(config, arm)

    def test_private_host_ports_refuse_other_lanes(self):
        host = module('crawl4ai_host', 'host.py')
        data = json.loads((RECIPE / 'config/host.example.json').read_text())
        data = {k: v.replace('${HOME}', '/tmp/worker') if isinstance(v, str) else v for k, v in data.items()}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'host.json'
            path.touch(mode=0o600)
            # This mandated test scratch directory itself has a Git ancestor;
            # exercise the real port parser with only location policy substituted.
            with patch.object(host, 'locations', return_value=(Path(directory), Path(directory))), \
                    patch.object(host, 'outside_repository'):
                for port in (3730, 3799):
                    data['api_port'] = port
                    path.write_text(json.dumps(data))
                    self.assertEqual(host.load_host()['api_port'], port)
                for port in (3710, 3729, 3800, 3819, 5433, 5439, 3731):
                    data['api_port'] = port
                    path.write_text(json.dumps(data))
                    with self.assertRaises(ValueError):
                        host.load_host()

    def test_docker_objects_have_owned_names_and_labels(self):
        compose = (RECIPE / 'config/compose.yaml').read_text()
        owner = 'com.native-agent-stack.owner: gpt6-omniroute-framework-integration'
        self.assertIn('container_name: rw-crawl4ai-', compose)
        self.assertIn('name: rw-crawl4ai-${NAS_CRAWL4AI_STORE', compose)
        self.assertEqual(compose.count(owner), 2)  # container + network; bind mounts only
        lifecycle = (RECIPE / 'container.sh').read_text()
        self.assertNotIn('nas-crawl4ai', lifecycle)
        self.assertNotIn('prune', lifecycle)
        self.assertIn('container rm --force "$NAS_CRAWL4AI_CONTAINER"', lifecycle)
        self.assertIn('network rm "$NAS_CRAWL4AI_NETWORK"', lifecycle)

    def test_skills_documentation_uses_coordinator_install_lifecycle(self):
        readme = (RECIPE / 'README.md').read_text()
        self.assertIn('tools/adoption/install_skills.py', readme)
        self.assertIn('--manifest blueprints/runtime-workers/skills/manifest.json', readme)
        self.assertIn('--project-dir "$NAS_CRAWL4AI_WORKSPACE" --agent universal', readme)
        self.assertIn('pending the skills PR', readme)
        self.assertIn('skill-load', readme)

    def test_mcp_limits_are_explicit_and_not_claimed_as_loaded(self):
        policy = json.loads((RECIPE / "config/mcp-policy.json").read_text())
        self.assertEqual(policy["loaded_servers"], [])
        self.assertEqual(policy["role"], "mcp-server")
        limits = policy["consumer_limits"]
        self.assertEqual(set(limits["context-mode"]["disabled_tools"]), {"ctx_upgrade", "ctx_purge"})
        self.assertEqual(set(limits["ai-memory"]["enabled_tools"]), {
            "memory_query", "memory_read_page", "memory_recent", "memory_status", "memory_briefing"})
        self.assertEqual(set(limits["socraticode"]["enabled_tools"]), {
            "codebase_search", "codebase_status", "codebase_list_projects", "codebase_health"})
        self.assertEqual(limits["socraticode"]["env"]["SOCRATICODE_WATCHER"], "manual")
        self.assertEqual(set(limits["headroom"]["enabled_tools"]), {
            "headroom_compress", "headroom_retrieve", "headroom_stats"})
        self.assertEqual(set(limits["qmd"]["collections"]), {
            "foundation-docs", "foundation-adoption", "us-equities-foundation", "us-equities-catalog"})

    def test_install_is_scoped_hash_checked_and_loopback_only(self):
        source = (RECIPE / "install.sh").read_text()
        self.assertIn("set -euo pipefail", source)
        self.assertIn("--require-hashes", source)
        self.assertIn("--only-binary", source)
        self.assertNotIn("--with-deps", source)
        self.assertNotRegex(source, r"\bsudo\b")
        for name in ("install.sh", "run-e2e.sh", "config/compose.yaml", "container.sh"):
            text = (RECIPE / name).read_text()
            self.assertNotIn("0.0.0.0", text, name)
        compose = (RECIPE / "config/compose.yaml").read_text()
        self.assertIn("127.0.0.1:", compose)
        self.assertIn("/run/secrets/api_token", compose)
        self.assertNotRegex(compose, r"(?im)^\s*(api_token|SECRET_KEY):\s*[A-Za-z0-9]{10}")

    def test_adapter_transports_correct_wrong_and_malformed_outputs_unchanged(self):
        check = RECIPE / "e2e/check.py"
        correct = (RECIPE / "e2e/expected.json").read_text()
        wrong = correct.replace('24.90', '999.00')
        with tempfile.TemporaryDirectory() as directory:
            result = Path(directory) / "result.json"
            for payload in (correct, wrong, '{"records": [BROKEN', ''):
                result.write_text(payload)
                run = subprocess.run([sys.executable, str(check), str(result)], capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertEqual(json.loads(run.stdout), [payload])
            result.unlink()
            run = subprocess.run([sys.executable, str(check), str(result)], capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(run.stdout, '')

    def test_three_frozen_pages_and_both_arms(self):
        self.assertEqual(len(list((RECIPE / "e2e/fixtures").glob("*.html"))), 3)
        config = json.loads((RECIPE / "config/worker.json").read_text())
        self.assertEqual(config["e2e"]["arms"], ["control", "engines-on"])
        source = (RECIPE / "e2e/run.py").read_text()
        self.assertIn('config["e2e"]["arms"]', source)
        self.assertIn("receipt", source)

    def test_receipt_uses_only_allowed_rows_and_never_exports_private_fields(self):
        executable = shutil.which('promptfoo')
        if executable is None:
            self.skipTest('Promptfoo 0.123.1 required for real grader receipt input')
        grader = module('crawl4ai_grader', 'e2e/grade.py')
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            grader.run_controls(work / 'controls', executable)
            database = work / "gateway.sqlite"
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.execute("""CREATE TABLE call_logs (
                    timestamp TEXT, path TEXT, status INTEGER, model TEXT,
                    reasoning_effort_requested TEXT, reasoning_effort_upstream TEXT,
                    tokens_in INTEGER, tokens_cache_read INTEGER, tokens_reasoning INTEGER,
                    prompt TEXT, correlation_id TEXT, email TEXT)""")
                for second, model, effort in (
                    (3, "cx/gpt-6-astra-max", "max"), (5, "cx/gpt-6-astra-max", "max"), (7, "cx/gpt-6-astra-max", "max"),
                    (23, "sharedgw/gpt-6-astra-max", "max"), (25, "sharedgw/gpt-6-astra-max", "max"), (27, "sharedgw/gpt-6-astra-max", "max"),
                ):
                    connection.execute("INSERT INTO call_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                        f"2026-09-27T12:00:{second:02d}+00:00", "/v1/chat/completions", 200, model,
                        effort, effort, 120, None, 15,
                        "PRIVATE_PROMPT", "PRIVATE_ID", "PRIVATE_EMAIL"))
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            for arm in ("control", "engines-on"):
                (work / arm).mkdir()
                (work / arm / "result.json").write_text((RECIPE / "e2e/expected.json").read_text())
                (work / arm / "native.log").write_text("PRIVATE_PATH PRIVATE_EMAIL PRIVATE_ID")
                grader.grade(work / arm, executable)
            (work / "container.log").write_text(
                "INFO Processing request of type CallToolRequest\nPOST /md HTTP/1.1 200\nPRIVATE_ID")
            info = {
                "framework_version": "0.9.4", "cleanup_passed": True, "compression": {"before": {"totalRequests": 2, "totalTokensSaved": 10}, "after": {"totalRequests": 5, "totalTokensSaved": 40}},
                "probes": {key: True for key in ("auth_/mcp/sse", "auth_/mcp/ws", "auth_/crawl", "api_fit", "sse", "websocket")},
                "arms": {
                    "control": {"model": "cx/gpt-6-astra-max", "start": "2026-09-27T12:00:00+00:00", "end": "2026-09-27T12:00:10+00:00"},
                    "engines-on": {"model": "sharedgw/gpt-6-astra-max", "start": "2026-09-27T12:00:20+00:00", "end": "2026-09-27T12:00:30+00:00"},
                },
            }
            (work / "run.json").write_text(json.dumps(info))
            output = work / "receipt.json"
            command = [sys.executable, str(RECIPE / "e2e/receipt.py"), "--run-dir", str(work),
                       "--db", str(database), "--engines-db", str(database), "--output", str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads(output.read_text())
            self.assertTrue(receipt["passed"])
            self.assertEqual(receipt["mcp_observation"]["tool_names_inferred_from_routes"], [])
            self.assertEqual(receipt["compression"]["delta"], {"totalRequests": 3, "totalTokensSaved": 30})
            self.assertEqual([a["gateway_port"] for a in receipt["arms"]], [20128, 20129])
            self.assertTrue(all(a['grader']['passed'] for a in receipt['arms']))
            self.assertTrue(receipt['grader_controls_passed'])
            self.assertEqual(before, hashlib.sha256(database.read_bytes()).hexdigest())
            for marker in ("PRIVATE_", str(work), '"prompt":', '"request_id":', '"email":'):
                # Human-readable sanitization text may name emails, but no DB fields escape.
                self.assertNotIn(marker, json.dumps(receipt["arms"]))
            allowed = {"timestamp", "path", "status", "model", "reasoning_effort_requested",
                       "reasoning_effort_upstream", "tokens_in", "tokens_cache_read", "tokens_reasoning"}
            for arm in receipt["arms"]:
                self.assertEqual(len(arm["gateway"]["rows"]), 3)
                self.assertEqual(set(arm["gateway"]["rows"][0]), allowed)
                self.assertIsNone(arm["gateway"]["rows"][0]["tokens_cache_read"])
            # Fail closed if either model's own deterministic result is empty.
            (work / "engines-on/result.json").write_text('{"records": []}')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 4, result.stderr)
            self.assertFalse(json.loads(output.read_text())["passed"])
            (work / "engines-on/result.json").write_text((RECIPE / "e2e/expected.json").read_text())
            native_log_text = (work / "container.log").read_text()
            (work / "container.log").unlink()
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 4, result.stderr)
            missing_log_receipt = json.loads(output.read_text())
            self.assertEqual(missing_log_receipt["mcp_observation"]["native_call_tool_request_count"], 0)
            self.assertTrue(all(a["grader"]["passed"] and a["routing_observed_in_window"] for a in missing_log_receipt["arms"]))
            (work / "container.log").write_text(native_log_text)
            # Every page must have the requested upstream effort, not merely one.
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.execute("UPDATE call_logs SET reasoning_effort_upstream='low' WHERE timestamp='2026-09-27T12:00:25+00:00'")
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 4, result.stderr)
            wrong_effort = json.loads(output.read_text())
            self.assertFalse(wrong_effort["passed"])
            self.assertTrue(all(a["grader"]["passed"] for a in wrong_effort["arms"]))
            self.assertFalse(wrong_effort["arms"][1]["routing_observed_in_window"])

    def test_receipt_cannot_certify_absent_db_or_missing_native_mcp_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            arms = {}
            for arm, model in (("control", "cx/gpt-6-astra-max"), ("engines-on", "sharedgw/gpt-6-astra-max")):
                (work / arm).mkdir()
                (work / arm / "result.json").write_text((RECIPE / "e2e/expected.json").read_text())
                arms[arm] = {"model": model, "start": "2026-09-27T12:00:00+00:00", "end": "2026-09-27T12:01:00+00:00"}
            (work / "container.log").write_text("Processing request of type CallToolRequest\nPOST /md HTTP/1.1 200\n")
            probes = {key: True for key in ("auth_/mcp/sse", "auth_/mcp/ws", "auth_/crawl", "api_fit", "sse", "websocket")}
            (work / "run.json").write_text(json.dumps({"framework_version": "0.9.4", "arms": arms, "cleanup_passed": True, "probes": probes}))
            output = work / "receipt.json"
            result = subprocess.run([sys.executable, str(RECIPE / "e2e/receipt.py"), "--run-dir", str(work),
                "--db", str(work / "absent.sqlite"), "--engines-db", str(work / "absent.sqlite"), "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 4, result.stderr)
            self.assertFalse(json.loads(output.read_text())["passed"])
            self.assertTrue(all(a["gateway"]["status"] == "unavailable" for a in json.loads(output.read_text())["arms"]))
            self.assertFalse((work / "absent.sqlite").exists())

    def test_upstream_grader_controls_and_type_strictness(self):
        """Real unchanged Promptfoo assertions, with local synthetic controls."""
        executable = shutil.which("promptfoo")
        if executable is None:
            self.skipTest("Promptfoo 0.123.1 unavailable; upstream controls NOT RUN")
        spec = importlib.util.spec_from_file_location("crawl4ai_grader", RECIPE / "e2e/grade.py")
        grader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(grader)
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            controls = grader.run_controls(work, executable)
            self.assertEqual({name: info['exit_code'] for name, info in controls.items()},
                             {'known-pass': 0, 'known-fail': 100, 'malformed-output': 100})
            for name, passed in (('known-pass', True), ('known-fail', False), ('malformed-output', False)):
                report = json.loads((work / name / 'promptfoo.json').read_text())
                self.assertEqual(report['results']['results'][0]['success'], passed)
                self.assertEqual(grader.observation(work / name, controls[name])['passed'], passed)
            positive = work / 'known-pass'
            report_path = positive / 'promptfoo.json'
            saved = report_path.read_text()
            report_path.write_text('{}')
            self.assertFalse(grader.observation(positive, controls['known-pass'])['passed'])
            report_path.write_text(saved)
            (positive / 'result.json').write_text('{"records": []}')
            self.assertFalse(grader.observation(positive, controls['known-pass'])['passed'])
            payload = json.loads((RECIPE / 'e2e/expected.json').read_text())
            payload['records'][0]['in_stock'] = 1
            (work / 'result.json').write_text(json.dumps(payload))
            info = grader.grade(work, executable)
            self.assertEqual(info['exit_code'], 100)
            self.assertFalse(grader.observation(work, info)['passed'])


if __name__ == "__main__":
    unittest.main()
