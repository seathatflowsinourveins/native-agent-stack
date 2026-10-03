Author a frozen retrieval test set for a local QMD markdown index. Do NOT run qmd or any search engine over the index. Read the markdown files directly with the shell (rg, sed) or with context-mode.

The index has four collections, each over `**/*.md` in a read-only checkout:
- us-equities-catalog = ~/code/native-agent-stack-live/catalogs/us-equities
- us-equities-foundation = ~/code/native-agent-stack-live/blueprints/us-equities
- foundation-adoption = ~/code/native-agent-stack-live/adoption
- foundation-docs = ~/code/native-agent-stack-live/docs, excluding docs/ecosystem/**

A document's id is qmd://<collection>/<path relative to the collection root>, for example qmd://foundation-adoption/update.md.

Write exactly 10 queries. For each query:
- It is a question an engineer would ask. At least one indexed document answers it, and the answer is a specific fact, step or value.
- `expected_docs` lists EVERY indexed document that contains the answer (usually one or two). Verify this by grepping the whole collection tree for the key terms and synonyms, so that no second answering document is missed.
- `evidence` gives the answering line(s) as path:line with a short quote (at most 200 chars).
- `style` mix: 3 'lexical' (shares distinctive terms with the answer text), 4 'paraphrase' (the same need in different words, avoiding the document's distinctive terms), 3 'conceptual' (describes the situation or goal, not the terms).
- Spread across all four collections: at least 2 per collection.
- Stay DISJOINT from the frozen E2E tasks in $SCRATCH/qmd-ab/prereg381-qmd-tasks.json. No query may target the same information need or the same answering document as any of those tasks. Also avoid adoption/update.md's "pin a release on a new machine" need, which is an earlier, known test item.
- Avoid questions whose answer depends on today's date or is likely to change within days.

Return only the JSON object.