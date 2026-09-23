#!/usr/bin/env python3
"""Score Recall@5 and MRR for one indexed arm against the sealed question set.
A hit counts if the returned chunk's (path, line-range) overlaps by >=1 line
with any gold span for that question, after normalizing paths to be
repo-relative (both sides already are).
"""
import argparse
import json
import time
import urllib.request

K = 5


def embed_one(url, model, text, timeout=30):
    payload = json.dumps({'model': model, 'input': [text]}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read())
    return body['data'][0]['embedding']


def qdrant_search(qdrant_url, collection, vector, limit, timeout=30):
    payload = json.dumps({'vector': vector, 'limit': limit, 'with_payload': True}).encode('utf-8')
    req = urllib.request.Request(f'{qdrant_url}/collections/{collection}/points/search', data=payload,
                                  headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())['result']


def overlaps(gold_spans, path, start, end):
    for g in gold_spans:
        if g['path'] == path and g['start_line'] <= end and start <= g['end_line']:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--questions', required=True)
    ap.add_argument('--embed-url', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--query-prefix', default='')
    ap.add_argument('--qdrant-url', required=True)
    ap.add_argument('--collection', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    qs = json.load(open(args.questions, encoding='utf-8'))['questions']
    hits5 = 0
    mrr_sum = 0.0
    latencies = []
    detail = []
    for q in qs:
        t0 = time.time()
        vec = embed_one(args.embed_url, args.model, args.query_prefix + q['text'])
        results = qdrant_search(args.qdrant_url, args.collection, vec, K)
        latencies.append(time.time() - t0)
        rank = None
        for i, r in enumerate(results, start=1):
            p = r['payload']
            if overlaps(q['gold_spans'], p['path'], p['start_line'], p['end_line']):
                rank = i
                break
        hit = rank is not None
        if hit:
            hits5 += 1
            mrr_sum += 1.0 / rank
        detail.append({
            'id': q['id'],
            'hit_at_5': hit,
            'rank': rank,
            'top5': [{'path': r['payload']['path'], 'start_line': r['payload']['start_line'], 'end_line': r['payload']['end_line'], 'score': r['score']} for r in results],
        })
    n = len(qs)
    result = {
        'collection': args.collection,
        'n_questions': n,
        'recall_at_5': hits5 / n,
        'recall_at_5_hits': hits5,
        'mrr': mrr_sum / n,
        'mean_query_latency_s': sum(latencies) / len(latencies) if latencies else None,
        'detail': detail,
    }
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(result, fh, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != 'detail'}))


if __name__ == '__main__':
    main()
