"""Offline assessment of frozen inputs and selected native retrieval results."""
import ast
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parent

# Fixed acceptance names from the preserved runner versions, never from a receipt.
REQUIRED_FROZEN_INPUTS = {
    'oracle.json', 'package-lock.json', 'package.json', 'pins.json', 'run.py',
    'seed/planner.py', 'seed/corpus/decoy/other.md',
    'seed/corpus/primary/notes/aéé.md', 'seed/corpus/primary/recovery.md',
    'seed/corpus/primary/scope.md',
}
SOURCE_CHECKS = {
    'canonical_source_hash', 'frozen_source_hash', 'ripgrep_binary_hash',
    'ripgrep-version_exit', 'ripgrep_version', 'ast-grep_binary_hash',
    'ast-grep-version_exit', 'ast-grep_version', 'independent_literal_oracle',
    'rg-positive_exit', 'rg_positive_exact_lines', 'rg_positive_exact_spans',
    'rg_negative_exit_and_empty', 'independent_ast_oracle', 'ast-positive_exit',
    'ast_exact_spans', 'ast_bounded_exact_source_text', 'ast_negative_empty',
    'canonical_source_unchanged', 'source_binaries_unchanged',
    'frozen_inputs_unchanged', 'owned_commands_completed',
}
QMD_INITIAL_CHECKS = {
    'node_binary_hash', 'node-version_exit', 'node_version', 'qmd_package_version',
    'qmd_license_hash', 'qmd_entrypoint_hash', 'package_lock_hash',
    'no_optional_llama_backends', 'qmd-version_exit', 'native_qmd_version',
    'qmd-add-primary_exit', 'qmd-add-decoy_exit',
}
FAILED_QMD_CHECKS = QMD_INITIAL_CHECKS | {'qmd-positive-0_exit', 'qmd-positive-0_paths'}
QMD_CHECKS = QMD_INITIAL_CHECKS | {
    'qmd-bounded-get_exit', 'qmd_get_exact_bounded_line', 'qmd-update_exit',
    'single_owned_database', 'qmd_database_integrity', 'qmd_active_scope_count',
    'qmd_no_embedding_rows', 'qmd_no_model_files', 'qmd_entrypoint_and_lock_unchanged',
    'frozen_inputs_unchanged', 'owned_commands_completed',
}
QMD_CHECKS |= {label + '_' + suffix
               for label in ['qmd-positive-' + str(i) for i in range(5)]
                            + ['qmd-reopen', 'qmd-updated']
               for suffix in ['exit', 'uri_scope', 'paths', 'body', 'bound']}
QMD_CHECKS |= {label + '_' + suffix
               for label in ['qmd-negative-0', 'qmd-negative-1', 'qmd-old-marker', 'qmd-deleted']
               for suffix in ['exit', 'uri_scope', 'paths']}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(source, qmd, failed, inventory, root=ROOT):
    oracle = json.loads((root/'oracle.json').read_text())
    code = (root/'seed/planner.py').read_bytes()
    require(hashlib.sha256(code).hexdigest() == oracle['source_sha256'], 'changed source oracle')
    for receipt, declared_mapping, runner in [
            (source, {'run.py': 'run-initial.py.txt'}, 'run-initial.py.txt'),
            (failed, {'run.py': 'run-initial.py.txt'}, 'run-initial.py.txt'),
            (qmd, {}, 'run-qmd-attempt-2.py.txt')]:
        require(receipt['frozen_file_mapping'] == declared_mapping, 'wrong executed runner provenance')
        # The original QMD receipt had no remapping. Its run.py bytes are now archived.
        mapping = {'run.py': runner}
        require(set(receipt['frozen_inputs']) == REQUIRED_FROZEN_INPUTS, 'required frozen input names changed')
        for name, digest in receipt['frozen_inputs'].items():
            require(hashlib.sha256((root/mapping.get(name, name)).read_bytes()).hexdigest() == digest,
                    'changed frozen input: '+name)
        require(receipt['cleanup'] == {'persistent_services_started': 0, 'timed_out_commands': 0}, 'incomplete cleanup')
        for claim in ['global_or_client_changes', 'inference_invoked', 'os_confinement_established']:
            require(receipt[claim] is False, 'unsupported claim: '+claim)
        require(receipt['whole_task_provider_usage'] is None, 'whole-task usage is unknown')
        require(receipt['platform']['system'] == 'Linux' and receipt['platform']['architecture'] == 'x86_64', 'wrong native target')
    for receipt, names in [(source, SOURCE_CHECKS), (qmd, QMD_CHECKS), (failed, FAILED_QMD_CHECKS)]:
        require(set(receipt['checks']) == names, 'required check names changed')
    require(all(value is (name != 'qmd-positive-0_paths') for name, value in failed['checks'].items()),
            'initial failure check outcomes changed')
    for receipt, mode, commands in [(source, 'source', 6), (qmd, 'qmd', 17)]:
        require(receipt['passed'] is True and receipt['mode'] == mode
                and all(v is True for v in receipt['checks'].values()), 'required native checks incomplete')
        require(receipt['native_commands'] == commands and len(receipt['facts']) == commands, 'native commands missing')

    def named(receipt):
        items = {f['label']: f for f in receipt['facts']}
        require(len(items) == len(receipt['facts']), 'duplicate command label')
        return items

    src = named(source)
    require(set(src) == {'ripgrep-version', 'ast-grep-version', 'rg-positive', 'rg-negative', 'ast-positive', 'ast-negative'}, 'source command set changed')
    require(all(f['exit_code'] == 0 for label, f in src.items() if label not in ['rg-negative', 'ast-negative']), 'source command failed')
    require(src['rg-negative']['exit_code'] == 1 and src['rg-negative']['match_count'] == 0, 'wrong rg negative')
    require(src['ast-negative']['exit_code'] in [0, 1] and src['ast-negative']['matches'] == [], 'wrong AST negative')
    require(src['ripgrep-version']['version_output'].startswith('ripgrep 15.2.0 '), 'wrong rg version')
    require(src['ast-grep-version']['version_output'] == 'ast-grep 0.45.3', 'wrong AST version')
    lines = code.decode().splitlines(keepends=True)
    expected = [i for i, line in enumerate(lines, 1) if oracle['source_literal'] in line]
    matches = src['rg-positive']['matches']
    require([m['line'] for m in matches] == expected == oracle['source_expected_line_numbers'], 'wrong lexical lines')
    for match in matches:
        require(match['path'] == 'frozen/seed/planner.py' and match['line_text'] == lines[match['line']-1], 'wrong lexical source')
        raw = match['line_text'].encode()
        start = raw.index(oracle['source_literal'].encode())
        require(match['spans'] == [{'start': start, 'end': start+len(oracle['source_literal'].encode()), 'text': oracle['source_literal']}], 'wrong literal byte span')
    expected_ast = sorted([{'start_line': n.lineno, 'start_column': n.col_offset, 'end_line': n.end_lineno, 'end_column': n.end_col_offset}
            for n in ast.walk(ast.parse(code)) if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call)
            and isinstance(n.exc.func, ast.Name) and n.exc.func.id == 'ValueError'], key=lambda x: x['start_line'] or 0)
    matches = src['ast-positive']['matches']
    spans = [{'start_line': m['range']['start']['line']+1, 'start_column': m['range']['start']['column'],
              'end_line': m['range']['end']['line']+1, 'end_column': m['range']['end']['column']} for m in matches]
    require(spans == expected_ast == oracle['source_ast_spans'], 'wrong AST ranges')
    for match in matches:
        byte_range = match['range']['byteOffset']
        require(match['file'] == 'frozen/seed/planner.py' and len(match['text'].encode()) <= 512
                and code[byte_range['start']:byte_range['end']] == match['text'].encode(), 'wrong AST source bytes or bound')
    qfacts = named(qmd)
    expected_labels = {'node-version', 'qmd-version', 'qmd-add-primary', 'qmd-add-decoy', 'qmd-bounded-get',
                       'qmd-reopen', 'qmd-update', 'qmd-updated', 'qmd-old-marker', 'qmd-deleted'}
    expected_labels |= {'qmd-positive-'+str(i) for i in range(5)} | {'qmd-negative-'+str(i) for i in range(2)}
    require(set(qfacts) == expected_labels and all(f['exit_code'] == 0 for f in qfacts.values()), 'QMD command missing or failed')
    require(qfacts['node-version']['version_output'] == 'v24.21.0' and '2.8.3' in qfacts['qmd-version']['version_output'], 'wrong QMD runtime')

    def query(label, text, path, body=None):
        fact = qfacts[label]
        require(fact['query'] == text, 'query substituted')
        rows = fact['rows']
        if path is None:
            require(rows == [], 'negative query returned content')
            return
        require(len(rows) == 1 and fact['stdout_bytes'] <= 2048, 'result count or byte bound exceeded')
        uri = urlsplit(rows[0]['file'])
        require(uri.scheme == 'qmd' and uri.netloc == oracle['qmd_collection'] and unquote(uri.path) == '/'+path
                and parse_qs(uri.query) == {'index': [oracle['qmd_index']]} and not uri.fragment, 'wrong source collection/path/index URI')
        require(rows[0]['body'] == (body if body is not None else oracle['corpus']['primary/'+path]), 'wrong exact source body')
        require(rows[0]['line'] == 2, 'wrong returned source line')

    for i, case in enumerate(oracle['queries']):
        query('qmd-positive-'+str(i), case['query'], case['file'])
    for i, text in enumerate(oracle['negative_queries']):
        query('qmd-negative-'+str(i), text, None)
    query('qmd-reopen', 'Cobaltcheckpoint', 'recovery.md')
    query('qmd-updated', oracle['after_update_marker'], 'recovery.md', oracle['updated_recovery'])
    query('qmd-old-marker', 'Cobaltcheckpoint', None)
    query('qmd-deleted', 'Amberproject', None)
    fact = qfacts['qmd-bounded-get']
    header, body = fact['output'].split('\n---\n\n', 1)
    require(header.startswith('qmd://'+oracle['qmd_collection']+'/recovery.md  #')
            and body == oracle['corpus']['primary/recovery.md'].splitlines()[1]+'\n'
            and fact['stdout_bytes'] <= 1024, 'get escaped its exact one-line provenance bound')
    require(qmd['database'] == {'integrity': 'ok', 'active_documents': 3, 'content_vectors_table': True, 'content_vector_rows': 0}, 'QMD state or embedding scope changed')
    require(qmd['model_files_in_run'] == [] and inventory['model_files_under_owned_prefix'] == []
            and inventory['installed_optional_llama_backends'] == [], 'model/backend artifact appeared')
    require(inventory['installed_qmd'] == '2.8.3' and inventory['installed_better_sqlite3'] == '13.0.3'
            and inventory['installed_sqlite_vec_linux_x64'] == '0.1.9' and inventory['all_registry_payloads_have_integrity'] is True, 'locked native dependency scope changed')
    require(inventory['lock_sha256'] == hashlib.sha256((root/'package-lock.json').read_bytes()).hexdigest(), 'dependency lock changed')
    require(failed['passed'] is False and failed['native_commands'] == 5 and len(failed['facts']) == 5
            and failed['checks']['qmd-positive-0_paths'] is False
            and failed['failure'] == {'type': 'AssertionError', 'message': 'qmd-positive-0_paths'}, 'initial native failure erased or relabeled')
    failed_row = named(failed)['qmd-positive-0']['rows']
    require(failed_row == qfacts['qmd-positive-0']['rows'], 'initial failure was not the documented URI format assumption')
    return {'evidence_consistent': True, 'source_checks': 22, 'qmd_checks': 70,
            'status': 'incomplete_historical_reference', 'native_acceptance_established': False,
            'recorded_successful_attempt_commands': 23, 'retained_failed_commands': 5,
            'whole_task_provider_usage': None, 'semantic_rag_or_client_integration': False}


if __name__ == '__main__':
    load = lambda name: json.loads((ROOT/name).read_text())
    print(json.dumps(audit(load('source-receipt.json'), load('qmd-receipt.json'),
                           load('qmd-attempt-1.json'), load('install-inventory.json')), indent=2))
