import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'blueprints/us-equities/research-efficiency/experiment.py'


class ResearchEfficiencyTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(PATH.is_file(), 'research efficiency adapter is not implemented')
        spec = importlib.util.spec_from_file_location('research_efficiency', PATH)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def test_codex_usage_does_not_double_count_cache_or_reasoning(self):
        got = self.m.normalize_usage('codex', {'total': {'inputTokens': 100, 'cachedInputTokens': 80, 'outputTokens': 20, 'reasoningOutputTokens': 10, 'totalTokens': 120}})
        self.assertEqual((got['uncached_input'], got['cache_read'], got['output'], got['reasoning_in_output'], got['total']), (20, 80, 20, 10, 120))
        self.assertIsNone(got['cache_creation'])

    def test_claude_usage_uses_only_terminal_sum(self):
        got = self.m.normalize_usage('claude', {'input_tokens': 2, 'cache_creation_input_tokens': 100, 'cache_read_input_tokens': 80, 'output_tokens': 20, 'output_tokens_details': {'thinking_tokens': 10}})
        self.assertEqual(got['total'], 202)
        self.assertEqual(got['reasoning_in_output'], 10)
        self.assertIsNone(got['retries'])

    def test_missing_or_invalid_usage_is_not_zero(self):
        self.assertIsNone(self.m.normalize_usage('codex', None)['total'])
        for usage in [{'inputTokens': True, 'cachedInputTokens': 0, 'outputTokens': 2}, {'inputTokens': 1, 'cachedInputTokens': 2, 'outputTokens': 3}]:
            with self.assertRaises(ValueError):
                self.m.normalize_usage('codex', {'total': usage})

    def test_prompt_treatment_only_changes_source_blocks(self):
        full = self.m.prompt('A', [{'id': 'S01', 'text': 'alpha'}, {'id': 'S02', 'text': 'beta'}])
        focused = self.m.prompt('A', [{'id': 'S01', 'text': 'alpha'}])
        self.assertEqual(full.split('\nSOURCE_DOCUMENTS\n')[0], focused.split('\nSOURCE_DOCUMENTS\n')[0])
        self.assertNotIn('focused', focused)

    def test_report_requires_present_citations_and_preserves_unknowns(self):
        report = {'answer': 'Bounded evidence only.', 'claims': [{'claim': 'Unknown historical eligibility.', 'citations': ['S01']}], 'unknowns': ['Historical eligibility remains unknown.']}
        self.m.validate_report(report, ['S01'])
        with self.assertRaises(ValueError):
            self.m.validate_report(report, ['S02'])
        report['unknowns'] = []
        with self.assertRaises(ValueError):
            self.m.validate_report(report, ['S01'])

    def test_native_action_or_duplicate_terminal_is_rejected(self):
        with self.assertRaises(ValueError):
            self.m.codex_result({'status': 'completed', 'configured_model':'gpt-6-astra','configured_provider':'openai','items': [{'type': 'mcpToolCall'}]})
        with self.assertRaisesRegex(ValueError,'tool/action'):
            self.m.codex_result({'status':'completed','configured_model':'gpt-6-astra','configured_provider':'openai','final_response':'{}'})
        with self.assertRaises(ValueError):
            self.m.claude_result([{'type': 'result', 'subtype': 'success', 'is_error': False}] * 2)

    def test_quota_failure_stops_only_matching_provider(self):
        runs = [{'provider': 'claude', 'provider_blocked': True}]
        self.assertFalse(self.m.may_submit('claude', runs))
        self.assertTrue(self.m.may_submit('codex', runs))
        self.assertFalse(self.m.may_submit('codex', [{'provider': 'codex'}] * 8))
        self.assertFalse(self.m.may_submit('codex', [{'provider': 'codex', 'receipt_present': False}]))

    def test_historical_quota_prose_does_not_stop_successful_provider(self):
        native = [{'type':'result','subtype':'success','is_error':False,'result':'A dated quota failure preceded accepted inference.'}]
        self.assertFalse(self.m.provider_refusal('claude',native,''))
        native[0].update(subtype='error_during_execution',is_error=True,result='Usage limit reached')
        self.assertTrue(self.m.provider_refusal('claude',native,''))

    def test_frozen_payload_hashes_refuse_tamper_and_extra_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / 'source.txt').write_text('frozen')
            manifest = {'files': [self.m.digest('source.txt', (p / 'source.txt').read_bytes())]}
            self.m.verify_files(p, manifest['files'])
            (p / 'source.txt').write_text('changed')
            with self.assertRaises(ValueError):
                self.m.verify_files(p, manifest['files'])

    def test_failure_keeps_usage_and_raw_answers(self):
        result = self.m.summarize_native('claude', [{'type': 'result', 'subtype': 'error_max_turns', 'is_error': True, 'usage': {'input_tokens': 5, 'cache_creation_input_tokens': 0, 'cache_read_input_tokens': 0, 'output_tokens': 2}, 'result': 'partial'}], [])
        self.assertEqual(result['usage']['total'], 7)
        self.assertFalse(result['completed'])

    def test_word_limit_counts_all_prose_but_not_citation_ids(self):
        report={'answer':'word '*247,'claims':[{'claim':'fact','citations':['S01']}],'unknowns':['unknown']}
        self.m.validate_report(report,['S01'])
        report['answer'] += 'word word '
        with self.assertRaisesRegex(ValueError,'word bound'):
            self.m.validate_report(report,['S01'])

    def test_named_index_uri_keeps_collection_and_source_scope(self):
        self.assertEqual(self.m.source_id('qmd://research-corpus/s01.md?index=research-efficiency'),'S01')
        for uri in ['qmd://other/s01.md?index=research-efficiency','qmd://research-corpus/s01.md?index=private','qmd://research-corpus/../s01.md']:
            with self.assertRaises(ValueError):
                self.m.source_id(uri)

    def review_fixture(self, root):
        source=root/'experiment';source.mkdir()
        report={'answer':'Bounded observation.','claims':[{'claim':'Historical membership unknown.','citations':['S01']}],'unknowns':['Historical membership.']}
        native={'status':'completed','configured_model':'gpt-6-astra','configured_provider':'openai','items':[], 'final_response':json.dumps(report),'usage':{'total':{'inputTokens':100,'cachedInputTokens':80,'outputTokens':20,'reasoningOutputTokens':0,'totalTokens':120}}}
        prompt=b'frozen prompt'
        plan={'tasks':{'A':{'question':'What remains unknown?'}},'rubric':{'dimensions':{'facts':1}},'corpus':[{'id':'S01','repo_path':'public.md','sha256':self.m.sha(b'source')}],'runtime':{'commands':{'codex':{'sha256':self.m.sha(self.m.encode(['mock-native']))}}}}
        for name,raw in [('plan.json',self.m.encode(plan)),('experiment.py',PATH.read_bytes()),('corpus/s01.md',b'source'),('prompts/A-full.txt',prompt)]:
            self.m.write(source/name,raw)
        files=[self.m.digest(str(p.relative_to(source)),p.read_bytes()) for p in source.rglob('*') if p.is_file()]
        self.m.write(source/'freeze.json',self.m.encode({'files':files}))
        anchor=self.m.sha((source/'freeze.json').read_bytes());run=source/'runs'/'codex-A-full'
        reservation={'provider':'codex','task':'A','condition':'full'}
        receipt=self.m.summarize_native('codex',native,['S01'])|reservation|{'source_ids':['S01'],'freeze_sha256':anchor,'prompt_sha256':self.m.sha(prompt),'prompt_bytes':len(prompt),'process_exit_code':0,'process_timeout':False}
        for name,value in [('reservation.json',reservation),('receipt.json',receipt),('command.json',{'argv':['mock-native']}),('native.stdout',native)]:
            self.m.write(run/name,self.m.encode(value))
        return source,anchor

    def test_blind_export_excludes_mapping_usage_and_replays_native(self):
        review=self.m.module(PATH.with_name('review.py'),'efficiency_review_test')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,anchor=self.review_fixture(root)
            result=review.export(source,anchor,root/'blind')
            self.assertEqual(result['answers'],1)
            answer=json.loads((root/'blind/answer-01.json').read_bytes())
            self.assertEqual(set(answer),{'id','task','response'})
            self.assertNotIn('usage',answer)
            self.assertTrue((source/'blind-mapping.json').is_file())
            self.assertFalse((root/'blind/blind-mapping.json').exists())

    def test_changed_native_receipt_is_not_a_valid_blind_answer(self):
        review=self.m.module(PATH.with_name('review.py'),'efficiency_review_negative')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,anchor=self.review_fixture(root)
            path=source/'runs/codex-A-full/receipt.json';value=json.loads(path.read_bytes());value['usage']['total']=1;path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'replay mismatch'):
                review.export(source,anchor,root/'blind')

    def test_blind_export_rejects_expanded_receipt_citation_scope(self):
        review=self.m.module(PATH.with_name('review.py'),'efficiency_review_scope')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,anchor=self.review_fixture(root)
            path=source/'runs/codex-A-full/receipt.json';value=json.loads(path.read_bytes());value['source_ids'].append('S99');path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'source scope mismatch'):
                review.export(source,anchor,root/'blind')

    def test_blind_export_rejects_fabricated_report_for_malformed_native(self):
        review=self.m.module(PATH.with_name('review.py'),'efficiency_review_malformed')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,anchor=self.review_fixture(root)
            run=source/'runs/codex-A-full'
            (run/'native.stdout').write_text('not JSON')
            path=run/'receipt.json';value=json.loads(path.read_bytes());value['completed']=False;value['usage']['total']=None;path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'unsupported success/usage/report'):
                review.export(source,anchor,root/'blind')


if __name__ == '__main__':
    unittest.main()
