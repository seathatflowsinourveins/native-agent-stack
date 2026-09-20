"""Dependency planner: deterministic topological ordering of declared tasks."""

import heapq


def order_tasks(dependencies):
    """Return every declared task once, each after all of its prerequisites.

    ``dependencies`` maps a task name to a list of prerequisite task names.
    Among the tasks that are ready at a given step, the lexicographically
    smallest name is emitted first. Duplicate prerequisites count once. A
    prerequisite that is not itself a declared task, or any dependency cycle
    (including one in a disconnected component), raises ``ValueError``.

    The mapping and its lists are never mutated.
    """
    prerequisites = {}
    for task, prereqs in dependencies.items():
        unique = set(prereqs)
        unknown = unique - dependencies.keys()
        if unknown:
            raise ValueError(
                "task {!r} requires undeclared prerequisite(s): {}".format(
                    task, ", ".join(repr(name) for name in sorted(unknown))
                )
            )
        prerequisites[task] = unique

    remaining = {task: len(prereqs) for task, prereqs in prerequisites.items()}
    dependents = {task: [] for task in prerequisites}
    for task, prereqs in prerequisites.items():
        for prereq in prereqs:
            dependents[prereq].append(task)

    ready = [task for task, count in remaining.items() if count == 0]
    heapq.heapify(ready)

    order = []
    while ready:
        task = heapq.heappop(ready)
        order.append(task)
        for dependent in dependents[task]:
            remaining[dependent] -= 1
            if remaining[dependent] == 0:
                heapq.heappush(ready, dependent)

    if len(order) != len(prerequisites):
        blocked = sorted(task for task in prerequisites if remaining[task] > 0)
        raise ValueError(
            "dependency cycle among: {}".format(
                ", ".join(repr(name) for name in blocked)
            )
        )
    return order
