#!/usr/bin/env python3
"""Scoped rg baseline: for each sealed question, extract salient keywords
(quoted identifiers / longest alnum tokens from the question text), run
ripgrep over the same include dirs as the chunker, and take the first 5
distinct (path, matched-line window) hits in rg's own ranking order
(file order, then line order) as the top-5. This is a literal-match
baseline, not a semantic one, and is scored with the same overlap rule.
"""
import json
import os
import re
import subprocess
from pathlib import Path

REPO = Path(os.path.expanduser('~/code/agent-lab'))
THIS_DIR = Path(__file__).resolve().parent
INCLUDE = ['tools', '.claude/workflows', 'tests', 'docs']
STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'of', 'to', 'in', 'is', 'does', 'what', 'how', 'which', 'that',
    'for', 'on', 'this', 'each', 'both', 'do', 'be', 'are', 'as', 'from', 'not', 'it', 'its', 'by',
    'when', 'name', 'at', 'least', 'two', 'than', 'with', 'one', 'used', 'use', 'file', 'files', 'exact',
}


def keywords(text):
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", text)
    seen = []
    for w in words:
        lw = w.lower()
        if lw in STOPWORDS:
            continue
        if w not in seen:
            seen.append(w)
    # Longest/most specific identifiers first (camelCase / snake_case / long words).
    seen.sort(key=lambda w: (-len(w), w))
    return seen[:6]


def rg_search(pattern):
    args = ['rg', '-n', '--no-heading', '-i', '-e', pattern] + INCLUDE
    proc = subprocess.run(args, cwd=REPO, capture_output=True, text=True, timeout=20)
    hits = []
    for line in proc.stdout.splitlines():
        parts = line.split(':', 2)
        if len(parts) < 2:
            continue
        path, lineno = parts[0], parts[1]
        try:
            lineno = int(lineno)
        except ValueError:
            continue
        hits.append((path, lineno))
    return hits


def top5_for_question(qtext):
    kws = keywords(qtext)
    seen_paths = []
    hits = []
    for kw in kws:
        for path, lineno in rg_search(re.escape(kw)):
            key = (path, lineno // 20)
            if key in seen_paths:
                continue
            seen_paths.append(key)
            hits.append({'path': path, 'start_line': max(1, lineno - 10), 'end_line': lineno + 10, 'matched_keyword': kw})
            if len(hits) >= 5:
                return hits
    return hits


def overlaps(gold_spans, path, start, end):
    for g in gold_spans:
        if g['path'] == path and g['start_line'] <= end and start <= g['end_line']:
            return True
    return False


def main():
    qs = json.load(open(THIS_DIR / 'questions.json'))['questions']
    hits5 = 0
    mrr_sum = 0.0
    detail = []
    for q in qs:
        top5 = top5_for_question(q['text'])
        rank = None
        for i, h in enumerate(top5, start=1):
            if overlaps(q['gold_spans'], h['path'], h['start_line'], h['end_line']):
                rank = i
                break
        hit = rank is not None
        if hit:
            hits5 += 1
            mrr_sum += 1.0 / rank
        detail.append({'id': q['id'], 'hit_at_5': hit, 'rank': rank, 'top5': top5, 'keywords': keywords(q['text'])})
    n = len(qs)
    result = {'baseline': 'rg_keyword', 'n_questions': n, 'recall_at_5': hits5 / n, 'recall_at_5_hits': hits5, 'mrr': mrr_sum / n, 'detail': detail}
    print(json.dumps({k: v for k, v in result.items() if k != 'detail'}))
    with open(os.path.expanduser('~/codex-ecosystem/state/gap-wave2-20260923/rag-bench/rg_baseline_eval.json'), 'w') as f:
        json.dump(result, f, indent=2)


if __name__ == '__main__':
    main()
