# SOTA convergence practice

The operating recipe for keeping [`catalogs/sota-convergence/`](../catalogs/sota-convergence/README.md)
current using [`tools/sota-convergence/`](../tools/sota-convergence/README.md). It replaces the
2026-09-22 wave's two hardcoded, host-path scripts with CLI-driven steps.

## When to rerun

- **Monthly**, as a bounded freshness check (steps 1, 2, 4 -- skip a full lane
  re-review if no selection changed). The open `saturation-tracking` issue,
  updated weekly by `.github/workflows/saturation-tracking.yml`, lists the
  layers due for a landscape sweep; run it with
  [the saturation sweep recipe](saturation-sweep.md).
- **When a layer decision changes**: a component is added/removed/promoted in
  `catalogs/foundation/decisions.json` or a `catalogs/us-equities/*.json` card
  changes `decision`, or the taxonomy in a prior dated manifest is edited.
- **When a reconciliation needs updating**: the destination engine, broker
  path, or an in-use-but-unpinned tool (like ripgrep) changes; edit
  `tools/sota-convergence/reconciliations-20260922.json` (or point
  `build_manifest.py --reconciliations` at a new dated copy) before rerunning.

Do not rerun merely because a dependent upstream shipped a release; a newer
release is information, not a reason to upgrade (see "what would overturn a
selection" below).

## The six commands, in order

```sh
# 1. Extract the working files (deterministic, no network)
python3 tools/sota-convergence/extract_layers.py --repo-root . --out "$WORK_DIR"

# 2. Authenticated GitHub metadata (network; gh must already be signed in)
python3 tools/sota-convergence/github_freshness.py --work-dir "$WORK_DIR" --workers 6

# 3. Review lanes -- an agent-lab saved workflow, not a manual step and not a
#    CLI command. In Claude Code, with ultracode on (see .claude/settings.json),
#    run the saved workflow by name "sota-convergence" with args:
#      {work_dir, repo, lanes?, refuters?, budgets?, max_proposals_per_lane?}
#    The workflow itself writes nothing to disk: it reads the working files and
#    the freshness snapshot from $WORK_DIR and returns one top-level object
#    {lanes, critic, lost} (the same shape build_manifest.py --lanes consumes:
#    lanes: [{lane, result: {layers: [...], calls, limits}, proposals: [...]}],
#    critic, lost). The coordinator -- not the workflow -- must persist that
#    returned object verbatim to "$WORK_DIR/lanes.json" before step 4 runs.

# 4. Merge into the dated manifest (no network; refuses to write on a leak)
python3 tools/sota-convergence/build_manifest.py \
  --work-dir "$WORK_DIR" --lanes "$WORK_DIR/lanes.json" \
  --out "$WORK_DIR/manifest-$(date +%Y%m%d).json" \
  --checked-at "$(date +%Y-%m-%d)" --id "sota-convergence-$(date +%Y%m%d)"

# 5. Codex foreground review of the manifest diff (cross-family; separate account/quota)
#    see recipes/claude-codex-foreground-review.md
claude -p '/codex:review --wait --scope branch --base BASE_COMMIT --json' \
  --output-format stream-json --verbose --max-turns 8

# 6. Publish: copy the reviewed manifest into catalogs/sota-convergence/,
#    update catalogs/sota-convergence/README.md's summary line, open a PR,
#    and run scripts/validate.py before merging (see "PR/CI step" below).
```

`$WORK_DIR` is a private, host-local scratch directory (never committed); it
holds the working files, `github-freshness.json`, `lanes.json` and the
generated manifest before publication.

## Layer-verdict lanes

A separate, independent pipeline from the six commands above -- it records a
per-layer winner onto the landscape ledger's schema v2 rows
(`catalogs/landscape/{foundation,us-equities}.json`), not the dated sota
manifest. Full contract in `tools/sota-convergence/README.md`'s "Record
verdicts" section; the same evidence-class distinctions above apply to every
lane's `winner_evidence_class`.

```sh
# Layout: WORK_DIR, BLIND_DIR and KEYS_DIR sit outside every repository, KEYS_DIR outside WORK_DIR and
# BLIND_DIR (no lane may read it), and BLIND_DIR/export is at least four
# directories deep (not /, /home, /tmp or a home directory itself). The lane runners, adjudicate and
# blind_checkout.py refuse an export or work dir that breaks this (the shared root rule in
# tools/sota-convergence/codex_lane.py), and lane_packets.py refuses an --out or --keys-out inside a repository;
# keeping KEYS_DIR apart from WORK_DIR and BLIND_DIR is the operator's (round 7, OPR7-5). CATALOG is this checkout; AL is a clean agent-lab
# checkout whose .claude/workflows/layer-verdict-lane.js and .claude/agents/blind-*.md are the vendored
# examples/claude-native/ copies, installed as ~/.claude/agents/blind-*.md.
CATALOG=$(pwd -P)

# 1. Packets, blind: labels, popularity and recency withheld, registered receipts attached, and the candidates'
#    manifest-only fields (component_id, pin, upstream, recipe_ref, decisions) sealed into a packet-keys document
#    that each packet commits to (sealed_candidates_sha256). Never pass --gap-receipts in a blind wave (it names
#    the previous winner; refused with --withhold-labels). A model worker runs as this user and can read any file
#    it names, so the keys document never exists while one runs: it is deleted here, and rebuilt (the build is
#    deterministic) and checked against these packets for the trusted steps 5 and 6. The wave's date and
#    manifest are fixed once and kept in KEYS_DIR/wave.env (never in packets/ or the export: the seed fixes the
#    candidate order), so a resume in a new shell on another day rebuilds the same packets (round 7, OPR7-1).
mkdir -p "$KEYS_DIR"
printf 'WAVE_DATE=%s\nWAVE_MANIFEST=%s\n' "$(date +%Y-%m-%d)" catalogs/sota-convergence/manifest-YYYYMMDD.json \
  > "$KEYS_DIR/wave.env"
packets_args() {  # the wave's fixed build arguments, from KEYS_DIR/wave.env
  . "$KEYS_DIR/wave.env"
  PACKETS_ARGS=(--root . --manifest "$WAVE_MANIFEST" --trading-candidates manifest --withhold-labels
    --registered-receipts --checked-at "$WAVE_DATE" --seed "${WAVE_DATE//-/}")
}
packets_args
python3 tools/sota-convergence/lane_packets.py "${PACKETS_ARGS[@]}" --out "$WORK_DIR" \
  --keys-out "$KEYS_DIR/packet-keys.json"
rm "$KEYS_DIR/packet-keys.json"
keys() {  # rebuild the keys document for these packets; it replaces any earlier one only when the rebuilt
          # packets are byte-identical, so a failed call leaves no document
  packets_args
  rm -rf "$KEYS_DIR/rebuild" "$KEYS_DIR/rebuild-keys" "$KEYS_DIR/packet-keys.json" \
    && python3 tools/sota-convergence/lane_packets.py "${PACKETS_ARGS[@]}" --out "$KEYS_DIR/rebuild" \
      --keys-out "$KEYS_DIR/rebuild-keys/packet-keys.json" >/dev/null \
    && cmp "$KEYS_DIR/rebuild/packets/SHA256SUMS" "$WORK_DIR/packets/SHA256SUMS" \
    && mv "$KEYS_DIR/rebuild-keys/packet-keys.json" "$KEYS_DIR/packet-keys.json"
}
#    Resume (any later shell): set CATALOG, WORK_DIR, BLIND_DIR, KEYS_DIR and AL again, cd "$CATALOG", and
#    define packets_args and keys as above (never rewrite wave.env); every step below then runs unchanged.

# 2. Blind export: only what the packets reference, labels stripped, no .git.
#    Both lanes and the adjudication read this one export; record_verdicts.py refuses lanes on two trees.
python3 tools/sota-convergence/blind_checkout.py --source . --rev HEAD \
  --dest "$BLIND_DIR/checkout" --export "$BLIND_DIR/export" --allow-from-packets "$WORK_DIR/packets"
git worktree remove --force "$BLIND_DIR/checkout"

# 3. Claude lane. $AL must be a clean agent-lab checkout at, or descending from, the commit
#    examples/claude-native/workflows/vendored-lanes.json names (agentlab_commit, e070125 for the current workflow),
#    with no uncommitted .claude/, CLAUDE.md or AGENTS.md changes; claude_lane.py refuses anything else. Install the
#    two vendored blind roles user-level from this catalog first, and only those two (install_claude_profile.py
#    --only agents would replace all seven catalog agents, including user-level copies of the others):
install -D -m 0644 adoption/agents/claude/blind-lane-reviewer.md ~/.claude/agents/blind-lane-reviewer.md
install -D -m 0644 adoption/agents/claude/blind-adjudicator.md ~/.claude/agents/blind-adjudicator.md
#    Args carry the launch identity {repo, repo_tree_sha256, agent_sha256} and lane-prompt.md,
#    which the workflow echoes; run it headless from the export root with hooks disabled (every stage runs as
#    blind-lane-reviewer), then collect. claude_lane.py refuses a result whose launch or prompt does not match.
python3 tools/sota-convergence/claude_lane_args.py --work-dir "$WORK_DIR" --repo "$BLIND_DIR/export" \
  --agent-file ~/.claude/agents/blind-lane-reviewer.md --agentlab-root "$AL" > "$WORK_DIR/claude-args.json"
(cd "$BLIND_DIR/export" && claude -p --settings '{"disableAllHooks": true}' --output-format json "Use a workflow. \
Run the saved workflow at scriptPath $AL/.claude/workflows/layer-verdict-lane.js with the Workflow tool, passing the \
JSON object in $WORK_DIR/claude-args.json exactly as args, then copy its task output file byte for byte to \
$WORK_DIR/claude-workflow-output.json." > "$WORK_DIR/claude-session.json")
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); json.dump(d.get("result", d), open(sys.argv[2], "w"))' \
  "$WORK_DIR/claude-workflow-output.json" "$WORK_DIR/claude-result.json"
#    Each layer's return is audited on what its agents opened (the run's transcripts; a read outside the export and
#    its packet voids the layer).
python3 tools/sota-convergence/claude_lane.py --result "$WORK_DIR/claude-result.json" --work-dir "$WORK_DIR" \
  --agentlab-root "$AL" --agent-file ~/.claude/agents/blind-lane-reviewer.md --repo "$BLIND_DIR/export" \
  --transcripts "$(python3 tools/sota-convergence/transcript_audit.py locate --cwd "$BLIND_DIR/export" \
    --session-json "$WORK_DIR/claude-session.json")" --resolved-model claude-opus-5-5
#    The resolved child model, read from the session the lane ran in:
#    (cd "$BLIND_DIR/export" && node "$AL/.claude/workflows/child-usage.mjs" --latest)

# 4. Codex lane on the same export (a separate account/quota, resumable; codex_lane.py refuses a --repo below
#    any .git). A deliberately non-blind run passes --allow-git-history --repo . instead.
python3 tools/sota-convergence/codex_lane.py --work-dir "$WORK_DIR" --repo "$BLIND_DIR/export" \
  --model <openai model> --effort high --jobs 2

# 5. Two-family adjudication of the layers whose lanes disagree (README "Two-family adjudication"). inputs exits
#    1 whenever it skips a layer (listed on stderr, for example a missing lane return); when it indexes no
#    disagreeing layer, the rest of this step has nothing to judge and can be skipped.
keys && python3 tools/sota-convergence/adjudicate.py inputs --work-dir "$WORK_DIR" \
  --lane-repo-root "$BLIND_DIR/export" --packet-keys "$KEYS_DIR/packet-keys.json"
rm "$KEYS_DIR/packet-keys.json"   # before any judge runs
python3 tools/sota-convergence/adjudicate.py codex --work-dir "$WORK_DIR" --repo "$BLIND_DIR/export" \
  --model <openai model> --jobs 2
python3 tools/sota-convergence/adjudicate.py claude-args --work-dir "$WORK_DIR" --repo "$BLIND_DIR/export" \
  --run-dir "$BLIND_DIR/export" > "$WORK_DIR/adjudication-claude-args.json"
#    Run $CATALOG/tools/sota-convergence/adjudication-lane.js (the export has no tools/) headless from the
#    export root as in step 3 (its --output-format json to adjudication-session.json), with
#    adjudication-claude-args.json as args, and write the workflow's result to adjudication-claude-result.json.
#    claude-collect audits each judgment on what its agents opened, from that run's transcripts.
python3 tools/sota-convergence/adjudicate.py claude-collect --work-dir "$WORK_DIR" \
  --result "$WORK_DIR/adjudication-claude-result.json" --model claude-opus-5-5 \
  --transcripts "$(python3 tools/sota-convergence/transcript_audit.py locate --cwd "$BLIND_DIR/export" \
    --session-json "$WORK_DIR/adjudication-session.json")"
python3 tools/sota-convergence/adjudicate.py assemble --work-dir "$WORK_DIR" --out "$WORK_DIR/adjudications"

# 6. Record: validate every lane file (a rejected file is reported and treated as absent, never aborts the
#    run), seal the accepted ones and the adjudications, and write the ledger rows. Pass the same
#    --adjudications to --check. --run-id is required; the grandfathered 20260922 wave is never re-recorded.
#    --lane-repo-root must name the export adjudicate inputs got: the adjudication binds the sealed form of
#    each return, whose sources_read are relativized against it. Every worker has finished, so the rebuilt keys
#    document may stay; the wave retains it as packet-keys.json. --write also measures the wave's prose exposure
#    against the ledger before its rows (the incumbents the export showed the lanes), over that export, and seals
#    it as prose-exposure.json; each row records lanes.prose_exposed (round 7, BL7-2).
keys && python3 tools/sota-convergence/record_verdicts.py --root . --work-dir "$WORK_DIR" \
  --lane-repo-root "$BLIND_DIR/export" --checked-at "$WAVE_DATE" --run-id "${WAVE_DATE//-/}" \
  --adjudications "$WORK_DIR/adjudications" --packet-keys "$KEYS_DIR/packet-keys.json" --write \
&& python3 tools/sota-convergence/record_verdicts.py --root . --work-dir "$WORK_DIR" \
  --lane-repo-root "$BLIND_DIR/export" --checked-at "$WAVE_DATE" --run-id "${WAVE_DATE//-/}" \
  --adjudications "$WORK_DIR/adjudications" --packet-keys "$KEYS_DIR/packet-keys.json" --check

# 7. Refresh the derived catalogs, register the newly sealed files and rehash only the listed files this wave
#    changed, then run every check CI runs (.github/workflows/validate.yml). Start step 6 from a clean checkout,
#    so the working tree's changes are exactly the wave's: a rehash of every listed file would also hide unrelated
#    tampering from scripts/validate.py (independent review of #145, round 6, OPR6-2). A changed winner also needs
#    the handbook's "Foundation selection by layer" table and any handbook display entry for a new component id
#    (tests/test_handbook_summary.py checks them): make those edits first. After any later edit, a remedy below
#    included, run the registration block and evidence_manifest.py --write again before the checks (round 7,
#    OPR7-6).
python3 scripts/component_matrix.py --write
python3 tools/sota-convergence/build_verdicts.py --write --root . --run-id "${WAVE_DATE//-/}" \
  --checked-at "$WAVE_DATE" --manifest "$WAVE_MANIFEST"
python3 scripts/new_host_grand_list.py --write   # its check runs in CI (round 6, OPR6-1)
python3 - <<'EOF'
import hashlib, json, pathlib, subprocess
status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                        check=True).stdout.splitlines()
changed = {line[3:].split(" -> ")[-1].strip('"') for line in status}
path = pathlib.Path("manifests/evidence.json"); doc = json.loads(path.read_text(encoding="utf-8"))
listed = {entry["path"]: entry for entry in doc["files"]}
for relative in sorted(changed):
    file = pathlib.Path(relative)
    if not file.is_file():
        continue
    data = file.read_bytes()
    if relative in listed:  # a listed file the wave rewrote (the ledgers, the handbook)
        listed[relative].update(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
    elif relative.startswith("evidence/artifacts/"):  # a newly sealed file
        doc["files"].append({"path": relative, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
EOF
python3 scripts/evidence_manifest.py --write
#    The next wave's pre-check: the recorded winners are its incumbents, so check an export against them before
#    opening the PR (round 4, OPS-3). This wave's own exposure is already sealed by step 6. Build it in new
#    directories, never over this wave's packets or keys (lane_packets.py refuses an existing --out/packets or
#    --keys-out; round 6, OPR6-3). Only two hit kinds fail (exit 1); resolve each, then re-check the same way:
#    - role_label_hits, an isolating container outside an evidence record: a role key in blind_checkout.py for a
#      real label; a REVIEWED_EVIDENCE_PATHS entry, with its reason, in export_isolation_check.py for an evidence
#      list; REMOVE_GLOBS last, listing the evidence references the rebuilt packets then drop (their withheld);
#    - packet_role_label_hits, a packet field on exactly the winners: withhold it in lane_packets.py.
#    record_label_hits, evidence_role_word_hits, packet_evidence_field_hits and the prose exposure are reported,
#    not failed (round 7, OPR7-2: intrinsic fields such as license isolate a new winner by coincidence); note any
#    real label among them in the PR. tests/test_blind_checkout.py runs the failing check in CI.
CHECK_DIR=$(mktemp -d "$(dirname "$BLIND_DIR")/isolation-check.XXXXXX")
packets_args
python3 tools/sota-convergence/lane_packets.py "${PACKETS_ARGS[@]}" --out "$CHECK_DIR/work" \
  --keys-out "$CHECK_DIR/keys/packet-keys.json"
python3 tools/sota-convergence/blind_checkout.py --source . --rev HEAD --dest "$CHECK_DIR/hosts/blind/checkout" \
  --export "$CHECK_DIR/hosts/blind/export" --allow-from-packets "$CHECK_DIR/work/packets"
python3 tools/sota-convergence/export_isolation_check.py "$CHECK_DIR/hosts/blind/export" "$CHECK_DIR/work/packets" . \
  --packet-keys "$CHECK_DIR/keys/packet-keys.json"
git worktree remove --force "$CHECK_DIR/hosts/blind/checkout"
#    The validate job's offline steps, in its order (zizmor, actionlint, the secret scan and the network checks
#    run in CI only; round 7, OPR7-4):
(cd examples/claude-native/workflows && sha256sum --check --strict SHA256SUMS)
python3 scripts/release_due.py --strict-if-repinned origin/main
python3 scripts/validate.py
python3 scripts/host_receipts.py validate
python3 scripts/validate_catalogs.py
python3 scripts/validate_foundation.py --root . --json
python3 scripts/landscape.py --root .
python3 blueprints/blind-catalog-convergence/audit_reports.py --check
python3 scripts/validate_convergence.py --all-recorded --root . --json
python3 tools/sota-convergence/build_verdicts.py --check
python3 scripts/component_matrix.py --check
python3 scripts/new_host_grand_list.py --check
python3 tools/sota-convergence/gap_crosswalk.py build --check
python3 tools/sota-convergence/gap_wave_ledger.py --wave gap-wave2-20260923 --wave gap-wave3-20260923 \
  --owner gap-resolution --check
python3 scripts/build_ecosystem.py --check
python3 scripts/verdict_flip_candidates.py
python3 -m unittest
node --test blueprints/native-skill-practice/test-contract.cjs
#    The verdict-review-gate job runs the base commit's gate against the committed wave, so commit first:
git worktree add --detach "$CHECK_DIR/gate-base" origin/main
python3 "$CHECK_DIR/gate-base/scripts/verdict_review_gate.py" --root . --base origin/main
git worktree remove --force "$CHECK_DIR/gate-base"
```

A lane disagreement (different winner component-id sets) stays
`pending_lanes` with the open gap recorded unless an adjudication file is
placed at `<adjudications-dir>/<catalog>__<layer_id>.json` and passed via
`--adjudications`; agreement between lanes alone never promotes a candidate
that neither lane actually selected as its winner (the same never-promote
rule as the six-command pipeline above, applied per layer instead of per
candidate). The disagreement's open gap names the two lanes' winner
*component_ids*, not the packet-local candidate keys, since only component
identity is meaningful once the packet itself is not part of the retained
record. A recorded winner's `pin` is the packet's manifest-joined pin, else
the winning candidate's own v1 pin text if any (`source_pin`, else
`revision` -- see `catalogs/landscape/{foundation,us-equities}.json`'s real
`candidates[]` fields), else `"unpinned"`.

Step 7's `build_verdicts.py --write` is the only step that regenerates
`docs/grand-catalog-handbook.md`'s generated block (tables and per-layer
narrative). `build_verdicts.py --check` fails whenever that block differs from
the checked-in handbook: after rows were recorded, and also after any change to
the generator itself, even while every row is still `pending_lanes`. Run
`--write` and commit the regenerated handbook in the same change as the rows
or the generator edit.

## Evidence classes

Keep these distinguished in the record and in review comments, per the
[acceptance evidence policy](../docs/acceptance-evidence-policy.md).
`review_status` and `evidence_level` are two independent axes, not one:
`review_status` records whether a *selection or pin change* survived
adversarial review; `evidence_level` records what was actually *executed*. A
component or entry can carry a `confirmed_*`/`_confirmed` `review_status` and
still be `source_review` -- the published 2026-09-22 manifest's `inspect-ai`
and `quantstats` rows are exactly that case (see
`catalogs/sota-convergence/README.md`'s "Method and limits").

- **Metadata** -- `github-freshness.json` and the manifest's `upstream`
  fields: GitHub REST facts only (stars, `pushed_at`, latest release/tag,
  license, archived, rename). Not a behavioral or compatibility claim.
- **`review_status`** (selection/pin confirmation, not execution) -- whether
  a lane's proposed change to a `selected`/`new_candidates` status survived
  two adversarial refuters. A `confirmed_*` prefix means the *proposal* was
  checked, not that the underlying tool ran: **`review_status` never
  establishes native execution**, regardless of prefix. A missing verdict
  (`survives: null`) stays `<status>_unverified`, never `confirmed_*` (see
  `disposition()`/the selected-status branch in `build_manifest.py`'s
  `merge_lanes`).
- **`evidence_level`** (execution classification, from the catalog card) --
  the field that actually classifies execution evidence: `source_review`
  means a lane read documentation/source and reasoned about fit, nothing was
  installed, built or run; `native_proven` (or anything the manifest cites to
  a receipt under `evidence/` or `manifests/evidence.json`) means an actual,
  reproducible execution exists, separately dated and scoped from this
  manifest. `build_manifest.py` carries `evidence_level` into each manifest
  trading entry row whenever the source `catalogs/us-equities/*.json` card
  sets it (`extract_layers.py` already reads it verbatim); foundation
  components (`manifests/stack.json`) do not currently carry the field.

## The never-promote rule

`disposition()` in `build_manifest.py` encodes it directly: a lane proposes a
label, two independent refuters try to break the proposal, and **survival
never upgrades a label**. A `not_adopted` newcomer that survives refutation
becomes `not_adopted_confirmed`, not `default`. Only `keep_but_compare` and
`targeted_candidate` are reachable outcomes for a newcomer; nothing is ever
promoted straight to `default`/`conditional` by this pipeline. A promotion
requires a separate, explicit edit to the source catalog decision, with its
own dated evidence -- never a side effect of a convergence run.

## Cross-family review and PR/CI

Run the [Codex foreground review](claude-codex-foreground-review.md) on the
manifest diff before publication; it is a separate account and quota from the
lane review above, and its absence (as in the 2026-09-22 wave, when the
account's usage limit was exhausted) must be recorded as "not established",
not silently skipped. Open the publication as a normal PR; CI runs
`scripts/validate.py` (publication hygiene: no host paths, no secret
prefixes, duplicate-key and receipt-kind checks) and `git diff --check`. Do
not merge a manifest that fails either.

## What would overturn a selection

Each `keep_but_compare` alternative and every refuted newcomer carries its own
`comparison_that_would_overturn` in the manifest -- read that field first. The
recurring shapes are: a measured same-task provider-token comparison (token
efficiency), a dated identity dataset that resolves known ticker collisions
(identity), a completed SPY/LEAN parity run (engine), a broker-specific
recovery case passed by a community adapter (execution), and an adversarial
recovery fixture passed by a compression tool (context tools). A newer
GitHub release, a higher star count, or lane agreement alone overturns
nothing.
