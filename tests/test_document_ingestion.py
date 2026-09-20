"""Deterministic fixture/evidence contracts; no native binary or model invocation."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'blueprints/convergence-practice/document-ingestion'
spec=importlib.util.spec_from_file_location('document_ingestion',FIXTURE/'ingest.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class DocumentIngestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages=m.read(FIXTURE/'accepted/extraction.json')
        cls.answers=m.read(FIXTURE/'accepted/retrieval.json')
        cls.oracle=m.read(FIXTURE/'oracle.json')
        cls.index=m.records(cls.pages)

    def test_frozen_source_bytes_and_retained_outputs(self):
        m.check_frozen(FIXTURE)
        receipt=m.read(FIXTURE/'accepted/receipt.json')
        self.assertEqual(m.digest(FIXTURE/'freeze.json'),receipt['freeze_sha256'])
        for name, expected in receipt['artifacts'].items():
            self.assertEqual(m.digest(FIXTURE/'accepted'/name),expected)

    def test_native_bbox_replay_and_full_page_oracle(self):
        pages=[]
        for source in m.read(FIXTURE/'freeze.json')['sources']:
            pages+=m.parse_bbox((FIXTURE/'accepted'/(source['id']+'.xhtml')).read_bytes(),source['id'],m.digest(FIXTURE/source['path']),m.read(FIXTURE/'layout.json'))
        self.assertEqual(pages,self.pages)
        self.assertTrue(all(m.quality(pages,self.answers,self.oracle).values()))

    def test_two_tables_preserve_all_24_data_cells(self):
        self.assertEqual(sum(len(r) for p in self.pages for t in p['tables'] for r in t['rows']),24)
        altered=copy.deepcopy(self.pages)
        altered[0]['tables'][0]['rows'][0][1]='90'
        self.assertFalse(m.quality(altered,self.answers,self.oracle)['exact_table_cells'])

    def test_wrong_source_and_page_do_not_leak(self):
        self.assertEqual(m.retrieve(self.index,'w3c',['CP-417']),[])
        self.assertEqual(m.retrieve(self.index,'lumen',['Timeout (s)=90'],page=1),[])
        self.assertEqual(m.retrieve(self.index,'unselected',['Dummy']),[])

    def test_retrieval_has_explicit_absent_answers(self):
        for q in self.oracle['questions']:
            hits=m.retrieve(self.index,q['document'],q['terms'],q['page'])
            if q['expected'] is None:self.assertEqual(hits,[])
            else:
                self.assertEqual([h['text'] for h in hits],[q['expected']])
                self.assertEqual(hits[0]['page'],q['page'])

    def test_excessive_and_empty_queries_fail_closed(self):
        for terms,kwargs in [([],{}),([''],{}),(['Service'],{}),(['release'],{'limit':0})]:
            with self.assertRaises(ValueError):m.retrieve(self.index,'lumen',terms,**kwargs)
        with self.assertRaises(ValueError):m.retrieve([{'document':'lumen','page':1,'text':'x'*241,'bbox':[1,1,2,2]}],'lumen',['x'])

    def test_hash_refusal_precedes_process_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'source.pdf').write_bytes(b'tampered')
            (root/'freeze.json').write_text(json.dumps({'files':{'source.pdf':'0'*64},'sources':[]}))
            with patch.object(m.subprocess,'run') as process:
                with self.assertRaises(ValueError):m.run(Path('unavailable'),root/'out',root)
                process.assert_not_called()

    def test_invalid_geometry_and_missing_cells_rejected(self):
        raw=(FIXTURE/'accepted/lumen.xhtml').read_bytes()
        tree=m.ET.fromstring(raw);tree.find('.//x:word',m.NS).set('xMin','-1')
        with self.assertRaises(ValueError):m.parse_bbox(m.ET.tostring(tree),'lumen','0'*64,m.read(FIXTURE/'layout.json'))
        # Move an otherwise real table region away from its content.
        layout=m.read(FIXTURE/'layout.json');layout['lumen'][0]['top']=500;layout['lumen'][0]['bottom']=600
        with self.assertRaises(ValueError):m.parse_bbox(raw,'lumen','0'*64,layout)

    def test_usage_and_scope_are_not_provider_savings(self):
        receipt=m.read(FIXTURE/'accepted/receipt.json')
        self.assertEqual(receipt['usage']['model_calls'],0)
        self.assertEqual(receipt['usage']['embedding_calls'],0)
        self.assertIn('coordinator',receipt['usage']['scope'])
        self.assertTrue(receipt['native_invalid_input']['exit_code']!=0)
        self.assertEqual(receipt['native_invalid_input']['stdout_bytes'],0)

if __name__=='__main__':unittest.main()
