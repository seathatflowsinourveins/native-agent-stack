Complete one research-and-code task using DeerFlow's native task delegation.
Read the search-first and verification-before-completion SKILL.md files with
read_file before using them; discover their canonical paths with describe_skill.
Use at most two task calls: delegate research to one child, then code/review to
one child. Return only their concise findings to the lead. Tools discovered
through tool_search retain their full server-name prefixes.

The lead must make the two named context-mode calls itself so its own native
stream records research use; children may add further research.

Research https://api.github.com/repos/bytedance/deer-flow/commits/345f08be00c8a9495079b732a39b46aa9af1584e
using context-mode_ctx_fetch_and_index and context-mode_ctx_search. This is the
release commit of DeerFlow v2.1.0, NOT the complete diff since the prior release.
Fetch the original API JSON with Python urllib if needed to retain exact numeric
fields. Save files.json containing ONLY the API files array projected to filename,
status, additions, deletions, changes. No author information or patch contents.

Write a standalone standard-library summarize.py that takes a JSON file path as
its sole argument, reads that projected array, and prints one JSON object with:
file_count, additions, deletions, changes, by_status (status -> count), paths
(sorted filenames). It must work on arbitrary arrays of this schema, including an
empty array. Run it against files.json and save its exact parsed JSON as report.json.

Put all three final files in /mnt/user-data/outputs/ of the lead thread. A child
must give the lead the precise paths or content needed to materialize final files.
Run the script and inspect its output before claiming completion. Do not install
packages, modify configuration, invoke ctx_upgrade/ctx_purge, write memory, or
build shared indexes. For QMD, explicitly name collections from foundation-docs,
foundation-adoption, us-equities-foundation, us-equities-catalog; retrieve using
qmd://collection/path and use bounded results. QMD queries must use explicit
searches with type=lex and rerank=false; the worker does not download QMD models. The worker's coding project is /work.
