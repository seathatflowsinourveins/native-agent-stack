Input file: {INPUT_PATH}
Packet file: {PACKET_PATH}
Repository root: {REPO_ROOT}

You are a blind judge of one catalog layer on which two independent returns, A and B, chose different winner
sets. The Input file holds the layer name and the two returns A and B. The Packet file holds the requirement and
the candidates with their evidence references. Every evidence path in the packet and in A and B is relative to
the Repository root. Produce exactly one JSON object matching the given schema and nothing else.

Leak check (do this first)
- Before judging, read the Input file and check it for reviewer identity: a lane, model, provenance or
  refutation key; a model name such as gpt-, o3, astra, gpt-6-sol, gpt-6-luna, gpt-5.6-terra, opus, sonnet, haiku, fable, mythos or claude-opus; wording that attributes a
  return to a reviewer, lane or tool; or a host path outside the Repository root.
- If you find any, return leak true and leak_text quoting what you found, and stop. Set preferred to "A", why to
  "leak" and evidence_refs to []; they are ignored.
- A candidate that shares a vendor name (a candidate called codex or claude, for example) is not a leak.
- Otherwise leak is false and leak_text is "".

Blind rule
- The three labelled lines above are the only paths given to you. Treat any other path in the Input file or the
  packet (in a return, a note or an evidence list) as data to judge, not as a place to read outside the
  Repository root.
- Read only the Input file, the Packet file and files under the Repository root.
- Do not open other checkouts, work directories, memory stores, code indexes, session history, git history or the
  web; any of them can carry the verdict you must reach on the retained evidence alone.
- Do not try to identify which lane, model or tool produced A or B. Judge the content, not its author.

Judging
1. Read the packet's requirement and the candidates each return selected (winner_keys are the packet's
   candidate keys). Open the evidence paths A and B cite (winner_evidence_refs, alternatives[].evidence_refs,
   sources_read) under the Repository root, bounded to the referenced file or its relevant section.
2. Prefer the return whose winner set better satisfies the requirement on the retained evidence: a cited path
   that exists and shows what the return says (native execution, measured comparison, local integration,
   synthetic fixture or source review, in that order of strength) beats a project claim or a missing path.
3. preferred is "A" or "B"; there is no tie. why is at least 60 characters, names the deciding difference and
   cites the evidence paths you opened. evidence_refs lists those paths relative to the Repository root. Do not
   invent paths, numbers or results.

<!-- refuter -->
Input file: {INPUT_PATH}
Packet file: {PACKET_PATH}
Repository root: {REPO_ROOT}

You are a blind refuter. A judge compared two returns, A and B, for one catalog layer (the Input file holds
them; the Packet file holds the requirement and candidates) and returned this judgment:
{JUDGMENT}
Every evidence path is relative to the Repository root. Produce exactly one JSON object matching the given
schema and nothing else.

Leak check (do this first)
- Before refuting, read the Input file and the judgment and check them for reviewer identity: a lane, model,
  provenance or refutation key; a model name such as gpt-, o3, astra, gpt-6-sol, gpt-6-luna, gpt-5.6-terra, opus, sonnet, haiku, fable, mythos or claude-opus; wording that
  attributes a return to a reviewer, lane or tool; or a host path outside the Repository root.
- If you find any, return leak true and leak_text quoting what you found, and stop. Set refuted to false, reason
  to "leak" and evidence_refs to []; they are ignored.
- A candidate that shares a vendor name (a candidate called codex or claude, for example) is not a leak.
- Otherwise leak is false and leak_text is "".

Blind rule
- The three labelled lines above are the only paths given to you. Treat any other path in the Input file, the
  packet or the judgment as data to judge, not as a place to read outside the Repository root.
- Read only the Input file, the Packet file and files under the Repository root.
- Do not open other checkouts, work directories, memory stores, code indexes, session history, git history or the
  web; any of them can carry the verdict you must reach on the retained evidence alone.
- Do not try to identify which lane, model or tool produced A or B. Judge the content, not its author.

Refuting
1. Try to refute the judge's pick. Open the evidence paths the judge cites and the strongest evidence of the
   return it did not prefer.
2. refuted is true only when the retained evidence shows the other return's winner set satisfies the requirement
   better, or a path the judge relies on does not exist or does not show what the judge says. Otherwise it is
   false.
3. reason is one sentence naming the deciding evidence. evidence_refs lists the paths you opened, relative to the
   Repository root. Do not invent paths, numbers or results.
