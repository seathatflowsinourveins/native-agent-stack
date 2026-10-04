# PR #685 monotonicity baselines

These are byte-for-byte snapshots of this repository's
`scripts/hooks/secret_path_guard.py`, used only as imported test oracles:

- `f77a35eb2/secret_path_guard.py`: main baseline
  `f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5`.
- `a7888d31/secret_path_guard.py`: round-one baseline
  `a7888d3107d5d5cec1868ca08b67522a026dda83`.

The test pins both hashes and compares `check()` on inert command strings.
It never runs a refused command or reads a credential file. Keeping the
original source here makes the check independent of Git history and network
access in shallow CI checkouts. These snapshots are local integration
fixtures; they are not upstream acceptance or copies of the installed hook.

`monotonicity.json` preserves the six R1–R5b commands and prefixes from the
coordinator-provided Sonnet allow-path oracle, with its source hash. The
permanent test checks these commands, variants, fixture tables, local blocked
dictionaries and literal `guard.check()` inputs against both baselines.
