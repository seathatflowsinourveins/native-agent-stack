#!/usr/bin/env python3
"""Build 8 blind judge packets (4 languages x 2 tools) with tool identity
stripped (no label saying which tool produced the diff; each packet is
presented only as 'Diff A' or 'Diff B' per language, order fixed by a stable
hash so it is not chosen post-hoc)."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEY = json.loads((HERE / 'expected_edit_key.json').read_text())

LANG_MAP = {'python': 'py', 'javascript': 'js', 'go': 'go', 'rust': 'rs'}

packets_dir = HERE / 'judge_packets'
packets_dir.mkdir(exist_ok=True)

manifest = []
for lang_name, prefix in LANG_MAP.items():
    info = KEY['languages'][lang_name]
    difft_text = (HERE / 'packets' / f'{prefix}_difft.txt').read_text()
    gitdiff_text = (HERE / 'packets' / f'{prefix}_gitdiff.txt').read_text()
    # Stable, non-cherry-picked order: hash of language name decides A/B assignment.
    h = hashlib.sha256(lang_name.encode()).hexdigest()
    difft_is_a = int(h[0], 16) % 2 == 0
    order = [('A', 'difft', difft_text), ('B', 'gitdiff', gitdiff_text)] if difft_is_a \
        else [('A', 'gitdiff', gitdiff_text), ('B', 'difft', difft_text)]
    for label, tool, text in order:
        prompt = f"""You are reviewing a code diff blind, with no knowledge of which tool produced it.

Below is the ENTIRE output of a diff tool comparing a 'before' and 'after' version of a small {lang_name} function. Do not assume anything about the code beyond what is shown.

--- DIFF START ---
{text}
--- DIFF END ---

Question: Does this diff clearly show the following change: {info['surfacing_question']}

Answer with EXACTLY this format, two lines:
ANSWER: YES or NO
EXPLANATION: one sentence, based only on the diff text shown above, describing what you can see changed."""
        packet_id = f'{prefix}_{label}'
        (packets_dir / f'{packet_id}.txt').write_text(prompt)
        manifest.append({'packet_id': packet_id, 'language': lang_name, 'label': label,
                         'actual_tool': tool, 'surfacing_question': info['surfacing_question']})

(HERE / 'judge_packets_manifest.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest, indent=2))
