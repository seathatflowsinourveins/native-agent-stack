# Hook coverage and frozen extraction limitations

Date: 2026-10-05. PR #722 repair, based on retained originals only. Evidence class: independent observation of native audit decisions, original command arguments and returns; the recorded exposure flags remain local integration extraction. No trial, model call, configuration, label or statistical result changed.

## The frozen flag is broader than the amendment

Amendment 1 intended the relevant marker-matched discovery grep to determine `hook_fired`; its smoke expectation was A=true, B=false, C=false. The final frozen extractor does not implement marker matching. It filters native audit lines for the word `grep`, then asks whether any has the exact rewrite delimiter and `rtk grep` in the final pipe-separated field. It also labels any grep-containing line as invocation, including a deferred Python command with a comment mentioning grep. These implementation predicates explain the published flags; they do not redefine the amendment.

Original `<state>/measure.py` SHA256: `5be7e131c0d5da45e14275ababe93e442b28da4e8121fdf851f5b92767c8200b`. Relevant original lines:

```text
150:     audit_grep = [line for line in audit.splitlines() if re.search(r"\bgrep\b", line)]
151:     reward = ((result.get("verifier_result") or {}).get("rewards") or {}).get("reward")
152:     ar = result.get("agent_result") or {}
153:     return {"job": trial.parent.name, "trial": trial.name, "task": task, "arm": arm,
154:             "reward": reward, "exception": (result.get("exception_info") or {}).get("exception_type"),
155:             "hook_fired": any(" | rewrite | " in line and "rtk grep" in line.split(" | ")[-1] for line in audit_grep),
156:             "grep_hook_invoked": bool(audit_grep), "grep_hook_audit": audit_grep, "fold_observed": bool(folds),
```

The source hash is unchanged between reporting freezes v4 and v5. This publication preserves `hook_fired`, `grep_hook_invoked` and `fold_observed` exactly as extracted, and records the intention/implementation mismatch as an exposure limitation.

## Every B discovery spelling is observed unrewritten

[grep-audit.csv](grep-audit.csv) reports all 24 B discovery greps, ten direct non-file-list follow-up rewrites and three successful Python-child greps. Each row identifies the public job, native task-trial key, outer call ID, one-based index within that trial's grep-containing audit records, flag spelling, discovery/follow-up phase, file-list status and hook action. Patterns are replaced by placeholders where needed; command operands, timestamps, full audit lines and returns are omitted. No host paths are published. Multiple greps inside one outer call retain that call's ID.

| Discovery spelling | Tasks | Calls | Native hook decision | Independent return observation |
| --- | --- | ---: | --- | --- |
| `grep -rl` | fold-01, fold-06, fold-07, fold-08 | 12 | `skip:no_rewrite` | exit 0; exact unfolded 12-target list in each call |
| `grep -lr` | fold-02 | 3 | `skip:no_rewrite` | same |
| `grep -l -r` | fold-03 | 3 | `skip:no_rewrite` | same |
| `grep -r -l` | fold-04 | 3 | `skip:no_rewrite` | same |
| `grep -l` | fold-05 | 3 | `skip:no_rewrite` | same |

These are the five registered spellings covered by B's four literal exclusions. The configuration and [pinned RTK prefix matcher](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/discover/registry.rs#L1553-L1581), together with every original discovery audit and unfolded return, support exclusion coverage for these hook-handled calls. No discovery file-list rewrite leaked in this sample. Broader remedy coverage remains **unresolved** for other bundles, option orders, `-R`, long options, explicit `rtk grep` and other invocation modalities. Successful Python-child checks do not qualify the Bash exclusion mechanism, because the child greps bypass it.

## B's eight true flags come from follow-ups

All ten direct rewrites occur after discovery and request content rather than a file list. None has `-l`. They are eligible for RTK under the frozen exclusion configuration; a repeated marker used as a content pattern does not turn a follow-up into the discovery call.

| Task | Trials with a follow-up rewrite | Rewritten spelling(s), with event counts |
| --- | ---: | --- |
| fold-03 | 1/3 | `grep -nH` × 1 |
| fold-05 | 2/3 | `grep -nE` × 1; `grep -n -e <marker> -e <assignment>` × 1 |
| fold-06 | 3/3 | `grep -n -E` × 2; `grep -n` × 3 |
| fold-08 | 2/3 | `grep -nE` × 1; `grep -nFx` × 1 |

The other four tasks have 0/3 rewrite flags. The cluster is explained by task-specific verification choices, including before/after content checks in fold-06. It supplies no evidence of a missed discovery exclusion. The exact observed follow-up spellings outside the discovery set are `grep -nH`, `grep -nE`, `grep -n -e <marker> -e <assignment>`, `grep -n -E`, `grep -n` and `grep -nFx`. The frozen B rate is eight trials because two trials each contain two rewrites, yielding ten events. Its retained fold flag is 0/24.

Five additional audit records use `skip:defer` on an outer Python command rather than a direct grep. The original arguments and returns distinguish them:

- `p2-fold-04-r3-B`, call `call_7UYMTrAgbIRPDs5W7UzU6vrx`: one follow-up file-list `grep -r -l` executes through Python subprocess before the successful verification summary; the outer call exits 0.
- `p2-fold-07-r1-B`, call `call_MTt1J3D6LkCAkZuJnFKxU8TS`: successful Python verification executes file-list `grep -rl` and content `grep -n -E`; its outer return exits 0. Both are included in the table, without assigning a separate hook decision to either child.
- `p2-fold-07-r1-B`, earlier call `call_noODKm7vl4jhT9SNjWgDFYax`: the Python script fails a preceding workspace check with exit 1. Its planned `grep -n -E` is not reached and is not counted as an observed grep event.
- `p2-fold-06-r1-B`, call `call_WkMtFT9w6V1kmPzL8RFqccN5`, and `p2-fold-08-r2-B`, call `call_4K4VJUvockCDyLfMdInCVLaq`: grep appears only in a Python comment about initial discovery. These records add no executed grep.

Thus the 39 grep-containing native audit records in B comprise 24 discovery skips, ten direct rewrites and five deferred Python records. The table's 37 observed grep events comprise 24 discoveries, ten direct follow-ups and three successful child greps. It excludes the unreached grep and comment-only mentions.

## Why fold-08-r3-A records a rewrite without a fold

In `p2-fold-08-r3-A`, original call `call_62hlbo2HG6b39QY4LdyskSuX` performs discovery and reads RTK instructions through `Promise.allSettled`. The native audit rewrites `grep -rl`. The labeled `matching_filenames` result has status `fulfilled`, an exit code of 0 and an output at `result.value.output` containing one fold header and 12 tails. Joining the header and each tail reproduces all 12 frozen targets. The instruction read is a separate labeled result; command/result pairing does not rely on concurrent emission order.

Harbor retained this as a Python representation of text blocks containing JSON. The frozen decoder handles lists, top-level `output` and top-level `text`, but does not descend through a `label/result/value/output` object. It reserializes that object, escaping newlines. The multiline-anchored fold regex then sees no header line in the extracted string. This is a false-negative extraction flag, not a native failure to fold.

Original `<state>/trajectory_decode.py` SHA256: `7ad6b51ec8e6efcbbb3c3bbcfaabac826f5f159f7c5b84a04cb05237f65c40d3`. Relevant original lines:

```text
81:     if isinstance(value, dict):
82:         if isinstance(value.get("output"), str):
83:             record = {k: value.get(k) for k in ["output", "exit_code", "session_id"]}
84:             return value["output"], [record]
85:         if isinstance(value.get("text"), str):
86:             return observation(value["text"], depth + 1)
87:         return json.dumps(value), []
```

The corresponding fold search in `<state>/measure.py` is:

```text
21: FOLD = re.compile(r"^(.+/) \((\d+) files\)$", re.M)
141:         for match in FOLD.finditer(call["output"]):
142:             header, count = match.group(1), int(match.group(2))
143:             tails = call["output"][match.end():].lstrip("\n").splitlines()[:count]
144:             rebuilt = {normalized(header + t, cwd) for t in tails}
145:             folds.append({"call_id": call["call_id"], "header": header, "tails": tails,
146:                           "reconstructs_ground_truth": rebuilt == targets})
```

The recorded `fold_observed=false` for this trial and A's aggregate 23/24 remain untouched in the analysis, receipt and per-arm CSV. This bounded original-return observation explains the anomaly; it is not a reanalysis or a change to wrong-path labels.

## Inspection method, correction and completeness

Each per-trial audit's grep-containing lines exactly match the retained `grep_hook_audit` arrays in both measures files. Direct spellings were joined to the native original arguments; dynamic follow-ups were identified from native arguments and audit records, not only the flat literal-command projection. Python-child invocations were read from the retained scripts and successful returns. Safe JSON/Python literal decoding was used only to inspect data; no retrieved code was executed. B discovery outputs were compared with the hidden frozen target sets and A's nested fold was reconstructed independently. [source-hashes.json](source-hashes.json) lists the private original hashes and sanitized source locators, including all 24 B audits, the anomalous A audit, extractor and decoder. Raw evidence remains private and read-only.

Inspection correction / anti-pattern log, 2026-10-05: an initial inference that B's fold-07-r1 used explicit RTK grep was rejected. The original arguments of `call_MTt1J3D6LkCAkZuJnFKxU8TS` identify `rg --files --hidden`, a filesystem check and Python verification. Searching all B native original argument strings for explicit `rtk grep` found zero candidates. A file-list-looking return must be paired with its own original command before attributing it to grep or folding. This correction changed no recorded result.

The missed wrapper is a known local decoder gap. Checking the B grep returns directly avoids treating an extractor's absent-fold flag as complete native coverage. Other wrappers, dynamically constructed commands and deeper result shapes remain future replay candidates; no repaired decoder, new scoring, semantic re-adjudication or broader trial was introduced. A broader remedy would require a newly frozen command/path scope and independent exposure checks.
