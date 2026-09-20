#!/usr/bin/env python3
"""Replay retained extraction evidence offline; this is not a new native run."""
import argparse
import json
from pathlib import Path
from ingest import HERE, check_frozen, digest, parse_bbox, read, records, retrieve, quality


def audit(root=HERE):
    frozen = check_frozen(root)
    receipt = read(root/'accepted/receipt.json')
    assert digest(root/'freeze.json') == receipt['freeze_sha256'], 'freeze changed'
    for name, expected in receipt['artifacts'].items():
        assert digest(root/'accepted'/name) == expected, 'retained output changed'
    pages=[]
    for source in frozen['sources']:
        pages += parse_bbox((root/'accepted'/(source['id']+'.xhtml')).read_bytes(),source['id'],digest(root/source['path']),read(root/'layout.json'))
    assert pages == read(root/'accepted/extraction.json'), 'native output replay differs'
    oracle=read(root/'oracle.json');index=records(pages)
    answers=[{'id':q['id'],'hits':retrieve(index,q['document'],q['terms'],q['page'],oracle['max_hits'],oracle['max_excerpt_chars'])} for q in oracle['questions']]
    assert answers == read(root/'accepted/retrieval.json'), 'retrieval differs'
    checks=quality(pages,answers,oracle)
    assert all(checks.values()), 'oracle failed'
    assert receipt['status']=='passed' and all(receipt['checks'].values()), 'native receipt failed'
    assert receipt['version']=='pdftotext version 26.09.0'
    assert receipt['usage']['model_calls']==receipt['usage']['embedding_calls']==receipt['usage']['provider_tokens']==0
    return {'evidence_class':'offline_artifact_check','checks':checks,'pages':len(pages),'queries':len(answers),'native_execution_repeated':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=HERE);print(json.dumps(audit(p.parse_args().root),indent=2))
