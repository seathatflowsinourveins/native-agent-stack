#!/usr/bin/env python3
"""Owned Linux retrieval qualification; explicit fixtures and no model commands."""
import argparse
import ast
import datetime
import hashlib
import json
import os
import platform
import shutil
import sqlite3
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def hashes(path):
    return {str(p.relative_to(path)): sha(p) for p in sorted(path.rglob('*')) if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['source', 'qmd'], required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--rg', type=Path)
    parser.add_argument('--ast-grep', type=Path)
    parser.add_argument('--node', type=Path)
    parser.add_argument('--package-prefix', type=Path)
    args = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise ValueError('Linux x86_64 required')
    os.umask(0o077)
    run = args.run_dir.expanduser().absolute()
    repo = next((p for p in HERE.parents if (p/'.git').exists()), HERE)
    if run == Path.home() or run.is_relative_to(repo) or any(p.is_symlink() for p in [run, *run.parents]):
        raise ValueError('new private run directory outside repository required')
    run.mkdir(mode=0o700)
    frozen = run/'frozen'
    frozen.mkdir()
    for name in ['run.py', 'oracle.json', 'pins.json', 'package.json', 'package-lock.json']:
        shutil.copyfile(HERE/name, frozen/name)
    shutil.copytree(HERE/'seed', frozen/'seed')
    frozen_hashes = hashes(frozen)
    save(run/'frozen-inputs.json', frozen_hashes)
    oracle = json.loads((frozen/'oracle.json').read_text())
    pins = json.loads((frozen/'pins.json').read_text())
    for name in ['tmp', 'cache', 'config']:
        (run/name).mkdir()
    checks, facts = {}, []
    result: dict[str, Any] = {'schema_version': 1, 'mode': args.mode, 'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'platform': {'system': platform.system(), 'architecture': platform.machine(), 'python': platform.python_version()},
              'checks': checks, 'facts': facts, 'frozen_inputs': frozen_hashes,
              'global_or_client_changes': False, 'inference_invoked': False,
              'whole_task_provider_usage': None, 'os_confinement_established': False,
              'cleanup': {'persistent_services_started': 0, 'timed_out_commands': 0}}
    env = {'HOME': os.environ['HOME'], 'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8',
           'TMPDIR': str(run/'tmp'), 'NO_COLOR': '1'}

    def check(name, condition):
        if name in checks:
            raise ValueError('duplicate check')
        checks[name] = bool(condition)
        save(run/'receipt.partial.json', result)
        if not condition:
            raise AssertionError(name)

    def command(label, argv, extra_env=None):
        try:
            out = subprocess.run([str(x) for x in argv], cwd=run, env=env | (extra_env or {}),
                                 text=True, capture_output=True, timeout=30, check=False)
        except subprocess.TimeoutExpired:
            result['cleanup']['timed_out_commands'] += 1
            raise
        (run/(label+'.stdout')).write_text(out.stdout)
        (run/(label+'.stderr')).write_text(out.stderr)
        fact = {'label': label, 'exit_code': out.returncode, 'stdout_bytes': len(out.stdout.encode()),
                'stdout_sha256': sha(run/(label+'.stdout')), 'stderr_sha256': sha(run/(label+'.stderr'))}
        facts.append(fact)
        save(run/'receipt.partial.json', result)
        return out, fact

    def ok(label, argv, extra_env=None):
        out, fact = command(label, argv, extra_env)
        check(label+'_exit', out.returncode == 0)
        return out, fact

    try:
        if args.mode == 'source':
            if not all([args.source, args.rg, args.ast_grep]):
                raise ValueError('source and exact search binaries required')
            check('canonical_source_hash', sha(args.source) == oracle['source_sha256'])
            fixture = Path('frozen/seed/planner.py')
            source = (run/fixture).read_bytes()
            check('frozen_source_hash', hashlib.sha256(source).hexdigest() == oracle['source_sha256'])
            for key, binary in [('ripgrep', args.rg), ('ast-grep', args.ast_grep)]:
                check(key+'_binary_hash', sha(binary) == pins[key]['binary_sha256'])
                out, fact = ok(key+'-version', [binary, '--version'])
                fact['version_output'] = out.stdout.strip()
                check(key+'_version', pins[key]['version'] in out.stdout.splitlines()[0])
            expected_lines = [i for i, line in enumerate(source.decode().splitlines(), 1) if oracle['source_literal'] in line]
            check('independent_literal_oracle', expected_lines == oracle['source_expected_line_numbers'])
            out, fact = ok('rg-positive', [args.rg, '--no-config', '--json', '-n', '-F', oracle['source_literal'], fixture])
            matches = [x['data'] for line in out.stdout.splitlines() if (x := json.loads(line))['type'] == 'match']
            fact['matches'] = [{'path': x['path']['text'], 'line': x['line_number'], 'line_text': x['lines']['text'],
                                'spans': [{'start': s['start'], 'end': s['end'], 'text': s['match']['text']} for s in x['submatches']]} for x in matches]
            check('rg_positive_exact_lines', [x['line_number'] for x in matches] == expected_lines)
            check('rg_positive_exact_spans', all(x['path']['text'] == str(fixture) and len(x['submatches']) == 1
                  and x['lines']['text'].encode()[x['submatches'][0]['start']:x['submatches'][0]['end']] == oracle['source_literal'].encode() for x in matches))
            out, fact = command('rg-negative', [args.rg, '--no-config', '--json', '-n', '-F', oracle['source_negative_marker'], fixture])
            fact['match_count'] = sum(json.loads(line)['type'] == 'match' for line in out.stdout.splitlines())
            check('rg_negative_exit_and_empty', out.returncode == 1 and fact['match_count'] == 0)
            expected_ast = sorted([{'start_line': n.lineno, 'start_column': n.col_offset, 'end_line': n.end_lineno, 'end_column': n.end_col_offset}
                for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call)
                and isinstance(n.exc.func, ast.Name) and n.exc.func.id == 'ValueError'], key=lambda x: x['start_line'] or 0)
            check('independent_ast_oracle', expected_ast == oracle['source_ast_spans'])
            out, fact = ok('ast-positive', [args.ast_grep, 'run', '--lang', 'python', '--pattern', oracle['source_ast_pattern'], '--json=compact', fixture])
            matches = json.loads(out.stdout)
            fact['matches'] = [{'file': m['file'], 'text': m['text'], 'range': m['range']} for m in matches]
            spans = [{'start_line': m['range']['start']['line']+1, 'start_column': m['range']['start']['column'],
                      'end_line': m['range']['end']['line']+1, 'end_column': m['range']['end']['column']} for m in matches]
            check('ast_exact_spans', spans == expected_ast)
            check('ast_bounded_exact_source_text', all(m['file'] == str(fixture) and len(m['text'].encode()) <= 512
                  and source[m['range']['byteOffset']['start']:m['range']['byteOffset']['end']] == m['text'].encode() for m in matches))
            out, fact = command('ast-negative', [args.ast_grep, 'run', '--lang', 'python', '--pattern', 'raise AssertionError($$$ARGS)', '--json=compact', fixture])
            fact['matches'] = json.loads(out.stdout)
            check('ast_negative_empty', out.returncode in [0, 1] and fact['matches'] == [])
            check('canonical_source_unchanged', sha(args.source) == oracle['source_sha256'])
            check('source_binaries_unchanged', sha(args.rg) == pins['ripgrep']['binary_sha256'] and sha(args.ast_grep) == pins['ast-grep']['binary_sha256'])
        else:
            if not args.node or not args.package_prefix:
                raise ValueError('exact node and owned package prefix required')
            check('node_binary_hash', sha(args.node) == pins['node']['binary_sha256'])
            node_out, node_fact = ok('node-version', [args.node, '--version'])
            node_fact['version_output'] = node_out.stdout.strip()
            check('node_version', node_out.stdout.strip() == 'v'+pins['node']['version'])
            package = args.package_prefix.resolve()
            qmd = package/'node_modules/@tobilu/qmd'
            check('qmd_package_version', json.loads((qmd/'package.json').read_text())['version'] == pins['qmd']['version'])
            check('qmd_license_hash', sha(qmd/'LICENSE') == pins['qmd']['license_sha256'])
            check('qmd_entrypoint_hash', sha(qmd/'bin/qmd') == pins['qmd']['entrypoint_sha256'])
            check('package_lock_hash', sha(package/'package-lock.json') == sha(frozen/'package-lock.json'))
            check('no_optional_llama_backends', not (package/'node_modules/@node-llama-cpp').exists() or not any((package/'node_modules/@node-llama-cpp').iterdir()))
            shutil.copytree(frozen/'seed/corpus', run/'corpus')
            qenv = {'PATH': str(args.node.parent)+':/usr/bin:/bin', 'QMD_CONFIG_DIR': str(run/'config'),
                    'XDG_CACHE_HOME': str(run/'cache'), 'QMD_FORCE_CPU': '1'}
            argv = [args.node, qmd/'bin/qmd', '--index', oracle['qmd_index']]
            out, fact = ok('qmd-version', [args.node, qmd/'bin/qmd', '--version'], qenv)
            fact['version_output'] = out.stdout.strip()
            check('native_qmd_version', '2.8.3' in out.stdout)
            for folder, collection in [('primary', oracle['qmd_collection']), ('decoy', oracle['qmd_decoy_collection'])]:
                ok('qmd-add-'+folder, argv+['collection', 'add', run/'corpus'/folder, '--name', collection, '--mask', '**/*.md'], qenv)

            def search(label, query, expected_file, expected_body=None):
                out, fact = ok(label, argv+['search', query, '-c', oracle['qmd_collection'], '-n', '3', '--json', '--full'], qenv)
                rows = json.loads(out.stdout)
                fact['query'] = query
                fact['rows'] = rows
                uris = [urlsplit(x['file']) for x in rows]
                check(label+'_uri_scope', all(u.scheme == 'qmd' and u.netloc == oracle['qmd_collection']
                      and parse_qs(u.query) == {'index': [oracle['qmd_index']]} and not u.fragment for u in uris))
                expected_paths = [] if expected_file is None else [expected_file]
                check(label+'_paths', [unquote(u.path).removeprefix('/') for u in uris] == expected_paths)
                if expected_file is not None:
                    body = expected_body if expected_body is not None else oracle['corpus']['primary/'+expected_file]
                    check(label+'_body', rows[0]['body'] == body)
                    check(label+'_bound', len(out.stdout.encode()) <= 2048 and len(rows) <= 3)
                return rows

            for i, item in enumerate(oracle['queries']):
                search('qmd-positive-'+str(i), item['query'], item['file'])
            for i, query in enumerate(oracle['negative_queries']):
                search('qmd-negative-'+str(i), query, None)
            target = 'qmd://'+oracle['qmd_collection']+'/recovery.md'
            out, fact = ok('qmd-bounded-get', argv+['get', target+':2:1', '--no-line-numbers'], qenv)
            fact['output'] = out.stdout
            line = oracle['corpus']['primary/recovery.md'].splitlines()[1]
            check('qmd_get_exact_bounded_line', target in out.stdout and line in out.stdout.splitlines() and len(out.stdout.encode()) <= 1024
                  and oracle['corpus']['primary/recovery.md'].splitlines()[2] not in out.stdout)
            search('qmd-reopen', 'Cobaltcheckpoint', 'recovery.md')
            (run/'corpus/primary/recovery.md').write_text(oracle['updated_recovery'])
            (run/'corpus/primary'/oracle['deleted_path']).unlink()
            ok('qmd-update', argv+['update'], qenv)
            search('qmd-updated', oracle['after_update_marker'], 'recovery.md', oracle['updated_recovery'])
            search('qmd-old-marker', 'Cobaltcheckpoint', None)
            search('qmd-deleted', 'Amberproject', None)
            dbs = list((run/'cache').rglob('*.sqlite'))
            check('single_owned_database', len(dbs) == 1)
            with sqlite3.connect(dbs[0].as_uri()+'?mode=ro', uri=True) as db:
                tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                vector_rows = db.execute('SELECT count(*) FROM content_vectors').fetchone()[0] if 'content_vectors' in tables else 0
                result['database'] = {'integrity': db.execute('PRAGMA integrity_check').fetchone()[0],
                                      'active_documents': db.execute('SELECT count(*) FROM documents WHERE active=1').fetchone()[0],
                                      'content_vectors_table': 'content_vectors' in tables, 'content_vector_rows': vector_rows}
            check('qmd_database_integrity', result['database']['integrity'] == 'ok')
            check('qmd_active_scope_count', result['database']['active_documents'] == 3)
            check('qmd_no_embedding_rows', vector_rows == 0)
            model_files = [str(p.relative_to(run)) for p in run.rglob('*') if p.is_file() and p.suffix in oracle['no_model_files_suffixes']]
            result['model_files_in_run'] = model_files
            check('qmd_no_model_files', model_files == [])
            check('qmd_entrypoint_and_lock_unchanged', sha(qmd/'bin/qmd') == pins['qmd']['entrypoint_sha256'] and sha(package/'package-lock.json') == sha(frozen/'package-lock.json'))
        check('frozen_inputs_unchanged', hashes(frozen) == frozen_hashes)
        check('owned_commands_completed', result['cleanup']['timed_out_commands'] == 0)
        result['passed'] = True
    except Exception as exc:  # noqa: BLE001 - retain the one attempted native run and its raw logs
        result['passed'] = False
        result['failure'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        result['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        result['native_commands'] = len(facts)
        save(run/'receipt.json', result)
        print(json.dumps({'mode': args.mode, 'passed': result['passed'], 'checks': len(checks),
                          'failed_checks': [k for k, value in checks.items() if not value],
                          'native_commands': len(facts), 'failure': result.get('failure')}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
