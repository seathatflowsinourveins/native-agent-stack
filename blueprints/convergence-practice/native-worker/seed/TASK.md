# Dependency planner repair

Implement `order_tasks(dependencies)` in `planner.py` using only the Python
standard library. Input is a mapping from task-name strings to lists of
prerequisite task-name strings. Return every declared task exactly once, after
all its prerequisites. At each step choose the lexicographically smallest
currently ready task. Duplicate prerequisite names count once. Raise `ValueError`
for an undeclared prerequisite or any cycle, including a disconnected cycle.
Do not mutate the mapping or its lists. Empty input returns an empty list.

You own only `planner.py`. Preserve this specification and `test_planner.py`.
Run `python3 -m unittest -v test_planner` and report the actual result, source
revision, working directory and changed paths. Do not commit, change settings,
install dependencies, contact external services, write durable memory or create
another subagent. The test oracle is visible; this is an integration acceptance
fixture, not a blinded benchmark or an efficiency comparison.
