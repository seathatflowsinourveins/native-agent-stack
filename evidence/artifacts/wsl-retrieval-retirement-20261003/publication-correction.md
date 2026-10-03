# Empty-output publication correction, 2026-10-03

Independent artifact review found that ten published stdout files contained one newline while the original native outputs were empty. The declared zero-byte lengths and SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` correctly described the originals but did not describe those draft copies. This was a publication error, not a new execution result.

Affected files: the eight `npm-*.stdout.txt` files and the first-attempt `prospective-archive.stdout.json` and `expired-archive.stdout.json`. The coordinator independently inspected each original capture, verified that all ten were zero bytes, and restored each published file to those exact empty bytes. The failed scanner attempts and their stderr/configuration records remain retained.

Verification path: compare every `output_files` length and SHA-256 in `controls.json` against the actual published bytes, then run repository evidence validation. Do not normalize native empty output into a newline when copying evidence. Hash checks establish artifact identity, not native success or archival scanner eligibility.
