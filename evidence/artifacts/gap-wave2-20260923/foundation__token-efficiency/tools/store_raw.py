"""Copy the existing raw outputs cited by the token-efficiency gap-wave-2 receipts into raw/ (reconciliation round).

No check is re-run. Host home path -> $HOME, the Claude project slug of $HOME -> $HOME_SLUG, UUID session ids ->
session-<first 12 hex of sha256(uuid)> (stable, so the two ccusage snapshots stay comparable). Records source and
committed sha256 plus each source's mtime, the only surviving wall-clock evidence of when an output was written.
Outputs that were never retained are listed with the reason, so no receipt value is presented as a stored output."""
import datetime, glob, hashlib, json, os, re, sys
HOME = os.path.expanduser("~")
HOME_SLUG = HOME.replace("/", "-")
LAYER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(LAYER, "raw")
SCRATCH = sys.argv[1]  # coordinator scratchpad that holds the two ccusage snapshots
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
def sha(b): return hashlib.sha256(b).hexdigest()
def mtime(p): return datetime.datetime.fromtimestamp(os.stat(p).st_mtime, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
def sanitize(text):
    n = len(UUID.findall(text))
    text = UUID.sub(lambda m: "session-" + sha(m.group(0).lower().encode())[:12], text)
    return text.replace(HOME, "$HOME").replace(HOME_SLUG, "$HOME_SLUG"), n
entries = []
copies = {  # source file in the scratchpad -> (committed path, gaps, attribution)
    "ccusage_session.json": ("raw/gap3/ccusage-claude-session-snapshot-a.json", [3, 0],
        "Attributed to receipt 3's `ccusage claude session --json --offline --no-cost` run by exact match of all four "
        "wf_f4b0c001-b52 per-model counters quoted in receipt 3 (sonnet 1758/606436/1644279/97461208, opus "
        "166/95840/369862/5225670); no cost fields, consistent with --no-cost. Receipt 0's excerpt also quoted its "
        "session count (325) and first-session cacheCreationTokens (23630420)."),
    "ccsess0.json": ("raw/gap0/ccusage-claude-session-snapshot-b.json", [0, 3],
        "Attributed to receipt 0's fix-round `ccusage claude session --json --offline --no-cost` run by name and timing "
        "(written 8 s before receipt 0's last write) and by the first-session inputTokens (20082) quoted in receipt 0. "
        "Also shows wf_f4b0c001-b52 still growing after snapshot a (used by receipt 3's reconciliation)."),
}
for src, (rel, gaps, why) in copies.items():
    p = os.path.join(SCRATCH, src); raw = open(p, "rb").read()
    text, n = sanitize(raw.decode("utf-8"))
    out = os.path.join(LAYER, rel); os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(text)
    entries.append({"gap_indexes": gaps, "source": "<coordinator scratchpad>/" + src, "source_sha256": sha(raw),
        "source_bytes": len(raw), "source_mtime_utc": mtime(p), "committed_path": rel,
        "committed_sha256": sha(text.encode()), "attribution": why,
        "sanitized": {"home_path_to_$HOME": HOME in raw.decode(), "home_slug_to_$HOME_SLUG": HOME_SLUG in raw.decode(),
                      "uuid_session_ids_pseudonymized": n}})
for p in sorted(glob.glob(os.path.join(DST, "gap2-rerun", "*.json"))):
    b = open(p, "rb").read()
    entries.append({"gap_indexes": [2], "committed_path": os.path.relpath(p, LAYER), "committed_sha256": sha(b),
        "committed_bytes": len(b), "worktree_mtime_utc": mtime(p),
        "note": "committed unchanged in f796901; mtime is when the file was written into this worktree (an upper bound on when the response existed)"})
J = glob.glob(os.path.join(HOME, ".claude/projects", HOME_SLUG + "-code-agent-lab", "*", "subagents/workflows/wf_f4b0c001-b52/journal.jsonl"))
if J:
    b = open(J[0], "rb").read(); lines = b.decode().splitlines()
    entries.append({"gap_indexes": [3], "source": "$HOME/.claude/projects/$HOME_SLUG-code-agent-lab/<session>/subagents/workflows/wf_f4b0c001-b52/journal.jsonl",
        "source_sha256_at_reconciliation": sha(b), "source_lines_at_reconciliation": len(lines), "source_mtime_utc": mtime(J[0]),
        "committed_path": None,
        "not_committed_reason": "another session's workflow journal; its result entries carry that session's task output. Hash, line count and mtime only.",
        "observation": "27 lines when the review read it (line 27 an unmatched 'started' for exec:worktree-diff); 37 lines and a 02:23:55Z mtime at reconciliation, so the workflow was still running during and after receipt 3's reads"})
not_retained = [
    (3, "`node .claude/workflows/child-usage.mjs --latest` output for wf_f4b0c001-b52", "never saved; the receipt's child-usage figures are transcriptions with no stored output"),
    (2, "isolated OmniRoute server log for the rerun", "scratch tree $HOME/.cache/gap-wave2-20260923/token-efficiency/ is empty (checked at reconciliation); the quoted 'Loaded env from ...' line cannot be verified"),
    (2, "`stat` outputs for $HOME/.omniroute/.env before/after", "not saved; only the transcribed epoch 1789995647 remains (equal to the file's current mtime, 2026-09-21T13:00:47Z)"),
    (1, "`headroom proxy --help` output", "not saved; receipt 1's proxy_help field was a paraphrase, now replaced by source-line citations"),
    (5, "gap-5 fixture.json, its generator, and the headroom_compress/headroom_retrieve responses", "fixture, generator and disposable workspace were deleted; the receipt's generator command is a placeholder"),
    (5, "`stat` outputs for $HOME/.headroom before/after", "not saved; transcribed epochs match the files' current mtimes (ccr_store.db 2026-09-22T23:47:55Z, update_check.json 2026-09-23T01:44:37Z)"),
]
for gap, what, why in not_retained:
    entries.append({"gap_indexes": [gap], "output": what, "committed_path": None, "not_retained_reason": why})
os.makedirs(DST, exist_ok=True)
json.dump({"generated_by": "tools/store_raw.py during the 2026-09-23 reconciliation round (copies existing files only; no check re-run)",
    "sanitization": "$HOME = the host home directory; $HOME_SLUG = $HOME with '/' replaced by '-', as Claude Code names project directories",
    "files": entries}, open(os.path.join(DST, "raw-manifest.json"), "w"), indent=2)
open(os.path.join(DST, "raw-manifest.json"), "a").write("\n")
print(len(entries), "entries")
