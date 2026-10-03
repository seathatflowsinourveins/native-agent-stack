# Empty-output publication correction, 2026-10-03

Independent artifact review found that ten published stdout files contained one newline while the original native outputs were empty. The declared zero-byte lengths and SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` correctly described the originals but did not describe those draft copies. This was a publication error, not a new execution result.

Affected files: the eight `npm-*.stdout.txt` files and the first-attempt `prospective-archive.stdout.json` and `expired-archive.stdout.json`. The coordinator independently inspected each original capture, verified that all ten were zero bytes, and restored each published file to those exact empty bytes. The failed scanner attempts and their stderr/configuration records remain retained.

Verification path: compare every `output_files` length and SHA-256 in `controls.json` against the actual published bytes, then run repository evidence validation. Do not normalize native empty output into a newline when copying evidence. Hash checks establish artifact identity, not native success or archival scanner eligibility.

The completion candidate's first publication validation also reported `integrated-osv-tests.stdout.txt`. An initial inference that this was an eleventh newline-only copy was wrong: direct byte/hash inspection found both original and public files already empty. Its evidence-registry row was stale instead. Refresh that row from the existing empty bytes; do not describe this as a new output-copy repair. The failed validation output is retained in the completion checks, and this correction records the verification path.
