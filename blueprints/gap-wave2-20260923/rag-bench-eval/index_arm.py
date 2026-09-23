#!/usr/bin/env python3
"""Embed chunks.jsonl with one arm's embedding endpoint and upsert into a
disposable Qdrant collection. Identical chunking/parameters across arms;
only the endpoint URL, model name, dimension and passage prefix differ.
"""
import argparse
import json
import sys
import time
import urllib.request

BATCH = 16


def embed_batch(url, model, texts, timeout=60):
    payload = json.dumps({'model': model, 'input': texts}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read())
    return [d['embedding'] for d in body['data']]


def qdrant_put(qdrant_url, path, obj, timeout=30):
    payload = json.dumps(obj).encode('utf-8')
    req = urllib.request.Request(qdrant_url + path, data=payload, method='PUT',
                                  headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--chunks', required=True)
    ap.add_argument('--embed-url', required=True, help='e.g. http://127.0.0.1:8231/v1/embeddings')
    ap.add_argument('--model', required=True)
    ap.add_argument('--dim', type=int, required=True)
    ap.add_argument('--passage-prefix', default='')
    ap.add_argument('--qdrant-url', required=True, help='e.g. http://127.0.0.1:26333')
    ap.add_argument('--collection', required=True)
    args = ap.parse_args()

    chunks = [json.loads(l) for l in open(args.chunks, encoding='utf-8')]

    qdrant_put(args.qdrant_url, f'/collections/{args.collection}', {
        'vectors': {'size': args.dim, 'distance': 'Cosine'}
    })

    t0 = time.time()
    n_embedded = 0
    errors = []
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        texts = [args.passage_prefix + c['text'] for c in batch]
        try:
            vecs = embed_batch(args.embed_url, args.model, texts)
        except Exception:  # noqa: BLE001 - batch-level failure: retry per item to isolate offenders
            vecs = [None] * len(batch)
            for j, t in enumerate(texts):
                try:
                    vecs[j] = embed_batch(args.embed_url, args.model, [t])[0]
                except Exception as exc2:  # noqa: BLE001
                    errors.append(f'{batch[j]["chunk_id"]} ({batch[j]["path"]}:{batch[j]["start_line"]}-{batch[j]["end_line"]}): {exc2}')
        points = []
        for c, v in zip(batch, vecs):
            if v is None:
                continue
            points.append({
                'id': int(c['chunk_id'][1:]),
                'vector': v,
                'payload': {'path': c['path'], 'start_line': c['start_line'], 'end_line': c['end_line'], 'chunk_id': c['chunk_id']},
            })
        if points:
            qdrant_put(args.qdrant_url, f'/collections/{args.collection}/points?wait=true', {'points': points})
        n_embedded += len(points)
    elapsed = time.time() - t0
    print(json.dumps({
        'collection': args.collection,
        'chunks_total': len(chunks),
        'chunks_embedded': n_embedded,
        'errors': errors,
        'index_build_seconds': elapsed,
    }))
    if errors:
        sys.exit(1)


if __name__ == '__main__':
    main()
