# Sources for the ColPali and MIRIX repairs (2026-09-26)

These changes preserve historical trial evidence and repair local reproduction
glue. They do not qualify a new model run or a MIRIX server operation.

- ColPali's exact environment comes from the original lock and installed freeze
  at repository revision `603027b617b4561363a7a79995c9d349de3ea5de`: 94 pins,
  1834 bytes, SHA-256
  `0eafa4e618aa234903b76ea3a529f1ed07ef4874e1f7502b34188c80cea166f9`.
  There were no `--hash` options. The replacement
  [environment record](colpali/reproduction/environment-record.json) preserves
  every line, name, version and empty hash list. Its advisory inventory cites
  the [retained OSV-Scanner 2.6.0 output](colpali/native-outputs/osv-scanner-requirements-lock-20260926T130641Z.txt).
  The dependency bounds are independently recorded from
  [ColPali's pinned pyproject.toml](https://github.com/illuin-tech/colpali/blob/174055b00d4a36f672c6f915f2bdd0002e4fc9ee/pyproject.toml)
  and [ViDoRe's pinned pyproject.toml](https://github.com/illuin-tech/vidore-benchmark/blob/d167f9ce6be840c5d887aa5cb1c01d2060485c93/pyproject.toml).
- Regeneration and installation reuse Python's documented
  [temporary-directory lifecycle](https://docs.python.org/3/library/tempfile.html#tempfile.mkdtemp)
  and uv's supported [requirements installation](https://docs.astral.sh/uv/pip/packages/)
  and [freeze](https://docs.astral.sh/uv/pip/inspection/) interfaces.
  The only new glue enforces explicit advisory acceptance, checks the recorded
  bytes, and keeps the generated lock in a private temporary directory.
- MIRIX's helper remains an awaited adaptation of
  [samples/generate_demo_api_key.py](https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/samples/generate_demo_api_key.py).
  Its async manager methods are cited in
  [source-review.json](mirix/source-review.json). File creation follows
  Python's [os.open](https://docs.python.org/3/library/os.html#os.open) and
  [os.fchmod](https://docs.python.org/3/library/os.html#os.fchmod) interfaces:
  exclusive creation, no symlink following, and mode 0600. Key values and
  upstream exception details are kept out of output, following the
  [CodeQL clear-text logging guidance](https://codeql.github.com/codeql-query-help/python/py-clear-text-logging-sensitive-data/).
  The as-run helper printed the key to the terminal; those unsafe source bytes
  are not retained in this tree. Its historical hash remains provenance only.
- Discovery used the installed search-first and find-skills guidance and the
  public [skills catalog](https://skills.sh/). Security-review skills were
  available, but no package or skill installation was needed: the selected
  upstream APIs and the repository's existing evidence registration procedure
  cover this bounded repair. Popularity was not treated as acceptance evidence.

The lock and key checks are local integration checks. MIRIX uses dummy values
and stub modules only; the CPU-script checks stub uv and stop before a model
run. Historical receipts retain their original scope. Evidence hashes are
registered with `scripts/host_receipts.py:register_file`, and the repository's
requested unit tests and validators check the resulting working tree.

## Verification

- The [final ColPali transcript](colpali/native-outputs/lock-regeneration-check-20260926-final.txt)
  shows byte identity with the original Git blob, all advisory IDs, refusal
  without opt-in, record tamper rejection, workspace cleanup, and both outcomes
  of the installed-environment comparison using synthetic uv.
- The [MIRIX transcript](mirix/native-outputs/gen-key-main-check-20260926.txt)
  records 19/19 dummy-only expectations, including suppression of an exception
  containing the generated dummy value.
- The requested `tests.test_osv_lockfile_coverage`, `tests.test_validate` and
  `tests.test_evidence_manifest` run passed all 73 tests using `ci-venv/bin/python`.
  `scripts/validate.py` and `scripts/evidence_manifest.py --check` passed with
  6773 registered files. `git diff --check HEAD` passed.
- A repository-wide reference search found no broken links to the changed
  files. Remaining retired lock/freeze names describe historical artifacts or
  files created at runtime. All ColPali/MIRIX retained paths, source fragments
  and published hashes resolve and match. The original advisory IDs all occur
  in the retained scanner output. Every changed/new trial evidence file was
  re-registered; the two removed installable files are absent from the evidence
  manifest and Git index. Changed files contain no home paths or UUID-shaped IDs.
- Independent source review found no blocker. No OSV ignore or macOS bootstrap
  change was made, and no package/model/server acceptance run is claimed here.

Only working-tree files were edited. The inherited index still has the MIRIX
helper's deletion staged; the repaired helper exists at the same path as an
untracked replacement. Staging was deliberately left to the caller, alongside
the other uncommitted files. The ColPali lock/freeze deletions remain staged.
