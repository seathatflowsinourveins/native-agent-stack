# Historical corrected-source qualification

These three files are byte-exact Git blobs from
`e73af98d5eea2325113a64fc62d7981303757287`. Their hashes also match the earlier
stress qualification at `ae6778e850d5fd05e510d9cef65c0988ec849ef2`.
They preserve the mutable sources referenced by the immutable
`receipt-stress-review-fixes-20261003.json` and
`receipt-over-limit-review-fixes-20261003.json` beside this directory.

Publication tests resolve only these three historical source names here; the
remaining unchanged bound files stay beside the receipts. Missing or mutated
archive bytes fail those tests. For a complete runnable historical tree, check
out the exact original Git commit and reproduce its original admission steps.
This directory is an evidence archive, not a standalone runtime bundle.

The six-case successor changes the active copies of these files. Historical
142/142 stress and 98/98 refusal results do not qualify the successor. Its
source, native runtime, review, original LEAN audits and commands require their
own destination acceptance.
