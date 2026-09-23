#!/usr/bin/env python3
"""Identical chunker for both embedder arms of the rag-bench recall benchmark.
Reads a fixed file list under the agent-lab repo (read-only) and emits
line-window chunks (40 lines, 10-line overlap) to a JSONL file.
"""
import argparse
import hashlib
import json
from pathlib import Path

WINDOW = 20
OVERLAP = 5
EXTS = {'.py', '.mjs', '.js', '.md'}
INCLUDE_DIRS = ['tools', '.claude/workflows', 'tests', 'docs']
EXCLUDE_SUBSTR = ['node_modules', '__pycache__', '/.git/']


def iter_files(repo_root):
    root = Path(repo_root)
    for d in INCLUDE_DIRS:
        base = root / d
        if not base.exists():
            continue
        for p in sorted(base.rglob('*')):
            if not p.is_file():
                continue
            if p.suffix not in EXTS:
                continue
            s = str(p)
            if any(x in s for x in EXCLUDE_SUBSTR):
                continue
            yield p


def chunk_file(path, repo_root):
    rel = str(path.relative_to(repo_root))
    try:
        text = path.read_text(encoding='utf-8')
    except (UnicodeDecodeError, OSError):
        return []
    lines = text.split('\n')
    n = len(lines)
    chunks = []
    start = 0
    while start < n:
        end = min(start + WINDOW, n)
        body = '\n'.join(lines[start:end])
        if body.strip():
            chunks.append({
                'path': rel,
                'start_line': start + 1,
                'end_line': end,
                'text': body,
            })
        if end >= n:
            break
        start = end - OVERLAP
    return chunks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    repo_root = Path(args.repo).resolve()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    all_chunks = []
    for f in iter_files(repo_root):
        all_chunks.extend(chunk_file(f, repo_root))
    for i, c in enumerate(all_chunks):
        c['chunk_id'] = f'c{i:05d}'
    with out_path.open('w', encoding='utf-8') as fh:
        for c in all_chunks:
            fh.write(json.dumps(c, ensure_ascii=False) + '\n')
    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
    print(json.dumps({'chunks': len(all_chunks), 'out': str(out_path), 'sha256': digest}))


if __name__ == '__main__':
    main()
