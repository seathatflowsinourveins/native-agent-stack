#!/usr/bin/env python3
"""Bounded native extraction with explicit source hashes and table coordinates.

No OCR, model inference, service registration, discovery scan or persistent memory.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
NS = {'x': 'http://www.w3.org/1999/xhtml'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def normalized(text):
    return ' '.join(text.split())


def check_frozen(root=HERE):
    root = root.resolve()
    frozen = read(root / 'freeze.json')
    files, sources = frozen.get('files'), frozen.get('sources')
    if not isinstance(files, dict) or not files or not isinstance(sources, list) or not sources:
        raise ValueError('nonempty frozen files and sources required')
    for name, expected in files.items():
        if (not isinstance(name, str) or not name or name.startswith('/')
                or any(part in {'', '.', '..'} for part in name.split('/'))
                or '\\' in name or ':' in name):
            raise ValueError('frozen file path must be canonical and relative')
        path = root
        for part in name.split('/'):
            path = path / part
            if path.is_symlink():
                raise ValueError('frozen symlink refused')
        if (not path.is_file() or not path.resolve().is_relative_to(root)
                or not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected)
                or digest(path) != expected):
            raise ValueError(f'frozen source mismatch: {name}')
    ids, paths = set(), set()
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError('frozen source must be an object')
        identifier, name = source.get('id'), source.get('path')
        if (not isinstance(identifier, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', identifier)
                or identifier in ids):
            raise ValueError('source identifier must be unique and safe')
        if not isinstance(name, str) or name not in files or not name.endswith('.pdf') or name in paths:
            raise ValueError('source must select a unique hash-listed PDF')
        ids.add(identifier); paths.add(name)
    return frozen


def parse_bbox(raw, document, source_sha256, layout):
    """Keep each page and word box; table geometry is supplied, not inferred."""
    tree = ET.fromstring(raw)
    pages = []
    for number, node in enumerate(tree.findall('.//x:page', NS), 1):
        width, height = float(node.attrib['width']), float(node.attrib['height'])
        words = []
        for word in node.findall('.//x:word', NS):
            box = [float(word.attrib[k]) for k in ('xMin', 'yMin', 'xMax', 'yMax')]
            if not all(math.isfinite(x) for x in box) or not (0 <= box[0] <= box[2] <= width and 0 <= box[1] <= box[3] <= height):
                raise ValueError('invalid word coordinates')
            words.append({'text': normalized(''.join(word.itertext())), 'bbox': box})
        # The born-digital fixture uses one font size on each line. General mixed
        # baseline/multi-column reading-order reconstruction is outside scope.
        groups = []
        for word in sorted(words, key=lambda w: (w['bbox'][1], w['bbox'][0])):
            if not groups or abs(groups[-1][0]['bbox'][1] - word['bbox'][1]) > 1.0:
                groups.append([])
            groups[-1].append(word)
        lines = []
        for group in groups:
            group.sort(key=lambda w: w['bbox'][0])
            lines.append({'text': ' '.join(w['text'] for w in group), 'bbox': [min(w['bbox'][0] for w in group), min(w['bbox'][1] for w in group), max(w['bbox'][2] for w in group), max(w['bbox'][3] for w in group)]})
        tables = []
        for region in layout.get(document, []):
            if region['page'] != number:
                continue
            edges, baselines = region['columns'], region['row_baselines']
            cells = [[[] for _ in edges[:-1]] for _ in baselines]
            for word in words:
                x0, y0, x1, y1 = word['bbox']
                if region['top'] <= (y0+y1)/2 <= region['bottom'] and edges[0] <= (x0+x1)/2 < edges[-1]:
                    row = min(range(len(baselines)), key=lambda i: abs(baselines[i]-(y0+y1)/2))
                    if abs(baselines[row]-(y0+y1)/2) > 10:
                        raise ValueError('word outside declared table row')
                    col = next(i for i in range(len(edges)-1) if edges[i] <= (x0+x1)/2 < edges[i+1])
                    if x0 < edges[col] or x1 > edges[col+1]:
                        raise ValueError('word crosses declared column boundary')
                    cells[row][col].append(word)
            values = [[' '.join(w['text'] for w in sorted(cell, key=lambda w: w['bbox'][0])) for cell in row] for row in cells]
            if any(not cell for row in values for cell in row):
                raise ValueError('missing table cell')
            tables.append({'headers': values[0], 'rows': values[1:], 'bbox': [edges[0], region['top'], edges[-1], region['bottom']]})
        pages.append({'document': document, 'source_sha256': source_sha256, 'page': number, 'width': width, 'height': height, 'word_count': len(words), 'lines': lines, 'tables': tables})
    if not pages:
        raise ValueError('no pages extracted')
    return pages


def records(pages):
    result = []
    for page in pages:
        base = {k: page[k] for k in ('document', 'source_sha256', 'page')}
        for line in page['lines']:
            if any(t['bbox'][1] <= (line['bbox'][1]+line['bbox'][3])/2 <= t['bbox'][3] for t in page['tables']):
                continue
            result.append({**base, **line, 'kind': 'line'})
        for table in page['tables']:
            for row in table['rows']:
                result.append({**base, 'text': '; '.join(f'{k}={v}' for k, v in zip(table['headers'], row)), 'bbox': table['bbox'], 'kind': 'table_row'})
    return result


def retrieve(index, document, terms, page=None, limit=3, max_chars=240):
    """Exact phrase AND search within one explicit source; empty means no evidence.

    This does not answer arbitrary natural-language questions or resolve aliases.
    An oversized match fails closed rather than truncating a value/citation.
    """
    if not terms or any(not t.strip() for t in terms) or not (1 <= limit <= 3) or not (1 <= max_chars <= 240):
        raise ValueError('invalid retrieval bounds')
    found = [r for r in index if r['document'] == document and (page is None or r['page'] == page) and all(t.casefold() in r['text'].casefold() for t in terms)]
    found.sort(key=lambda r: (r['page'], r['bbox'][1], r['bbox'][0], r['text']))
    if len(found) > limit or any(len(r['text']) > max_chars for r in found):
        raise ValueError('retrieval bound exceeded; narrow the query')
    return found


def quality(pages, answers, oracle):
    texts = defaultdict(dict)
    tables = defaultdict(dict)
    for p in pages:
        texts[p['document']][str(p['page'])] = [normalized(x['text']) for x in p['lines']]
        if p['tables']:
            tables[p['document']][str(p['page'])] = {k:p['tables'][0][k] for k in ('headers','rows')}
    positive = [q for q in oracle['questions'] if q['expected'] is not None]
    negative = [q for q in oracle['questions'] if q['expected'] is None]
    by_id = {a['id']:a['hits'] for a in answers}
    checks = {'exact_page_text': dict(texts) == oracle['page_lines'], 'exact_table_cells': dict(tables) == oracle['tables']}
    checks['positive_retrieval'] = all(len(by_id[q['id']]) == 1 and by_id[q['id']][0]['text'] == q['expected'] for q in positive)
    checks['negative_retrieval'] = all(not by_id[q['id']] for q in negative)
    checks['positive_provenance'] = all(all(h['document'] == q['document'] and h['page'] == q['page'] and re.fullmatch(r'[0-9a-f]{64}', h['source_sha256']) and len(h['bbox']) == 4 for h in by_id[q['id']]) for q in positive)
    checks['bounded_output'] = all(len(a['hits']) <= oracle['max_hits'] and all(len(h['text']) <= oracle['max_excerpt_chars'] for h in a['hits']) for a in answers)
    return checks


def run(executable, output, root=HERE, attempt=1):
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        raise ValueError("positive attempt number required")
    frozen = check_frozen(root)
    if output.exists():
        raise ValueError('output directory must be new; preserve prior attempts')
    output.mkdir(parents=True)
    started = time.monotonic()
    version = subprocess.run([str(executable), '-v'], capture_output=True, text=True, timeout=10)
    version_line = (version.stderr + version.stdout).splitlines()[0]
    if version.returncode != 0 or version_line != 'pdftotext version 26.09.0':
        raise ValueError('candidate version must be exactly 26.09.0')
    pages, commands = [], []
    layout, oracle = read(root/'layout.json'), read(root/'oracle.json')
    for source in frozen['sources']:
        path = root/source['path']
        # No glob or implicit collection; only the two frozen sources.
        result = subprocess.run([str(executable), '-bbox-layout', '-enc', 'UTF-8', str(path), '-'], capture_output=True, timeout=30)
        commands.append({'source':source['id'], 'argv':['pdftotext','-bbox-layout','-enc','UTF-8',source['path'],'-'], 'exit_code':result.returncode,'stderr':result.stderr.decode('utf-8','replace')})
        (output/(source['id']+'.xhtml')).write_bytes(result.stdout)
        if result.returncode != 0 or len(result.stdout) > 2_000_000:
            raise ValueError('native extraction failed or exceeded output bound')
        pages.extend(parse_bbox(result.stdout, source['id'], digest(path), layout))
    index = records(pages)
    answers = [{'id':q['id'],'hits':retrieve(index, q['document'], q['terms'], q['page'],oracle['max_hits'],oracle['max_excerpt_chars'])} for q in oracle['questions']]
    checks = quality(pages, answers, oracle)
    # A valid hash never promises the bytes are a valid PDF; exercise native refusal.
    with tempfile.TemporaryDirectory(prefix='invalid-pdf-') as scratch:
        invalid = Path(scratch)/'invalid.pdf';invalid.write_bytes(b'This is not a PDF.\n')
        refusal = subprocess.run([str(executable),'-bbox-layout',str(invalid),'-'], capture_output=True, timeout=10)
    checks['invalid_pdf_native_refusal'] = refusal.returncode != 0 and not refusal.stdout
    checks['frozen_inputs_unchanged'] = check_frozen(root) == frozen
    write(output/'extraction.json',pages);write(output/'retrieval.json',answers)
    receipt={'kind':'historical_native_document_qualification','evidence_class':'native_cli_execution','attempt':attempt,'status':'passed' if all(checks.values()) else 'failed','version':version_line,'executable_sha256':digest(executable),'commands':commands,'checks':checks,'pages':len(pages),'data_cells':sum(len(row) for p in pages for t in p['tables'] for row in t['rows']),'query_count':len(answers),'positive_queries':8,'negative_queries':4,'elapsed_seconds':round(time.monotonic()-started,4),'native_invalid_input':{'exit_code':refusal.returncode,'stdout_bytes':len(refusal.stdout),'stderr':refusal.stderr.decode('utf-8','replace')},'usage':{'model_calls':0,'embedding_calls':0,'provider_tokens':0,'scope':'This deterministic runner only; coordinator/research token usage excluded and unknown.'},'artifacts':{n:digest(output/n) for n in ('extraction.json','retrieval.json','lumen.xhtml','w3c.xhtml')},'freeze_sha256':digest(root/'freeze.json')}
    write(output/'receipt.json',receipt)
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pdftotext',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--attempt',type=int,default=1)
    args=p.parse_args();r=run(args.pdftotext.resolve(),args.output.resolve(),attempt=args.attempt);print(json.dumps({'status':r['status'],'checks':r['checks']}));raise SystemExit(0 if r['status']=='passed' else 1)
