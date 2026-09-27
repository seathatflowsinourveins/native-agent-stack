# Compact integer ranges

Implement `compress_ranges(values)` in `range_utils.py`. Accept a finite iterable
of integers. Return a list of inclusive `(start, end)` tuples in ascending order,
merging consecutive integers, ignoring duplicates, and preserving gaps. An empty
input produces `[]`. Do not mutate the input. For example,
`[8, 2, 1, 3, 5, 5, 7]` produces `[(1, 3), (5, 5), (7, 8)]`.

This is a self-contained synthetic coding task. Only `range_utils.py` may change.
The test and this README are frozen. First run the existing failing test, then
repair the implementation, then run the same test again. Do not delete, skip or
edit tests; do not add files, install dependencies or use Git.

Run: `python -B -m unittest discover -s tests -v`
