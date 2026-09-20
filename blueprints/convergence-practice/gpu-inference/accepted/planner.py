import heapq


def order_tasks(dependencies):
    """Return task names in a valid topological order.

    Chooses the lexicographically smallest ready task at each step.
    Raises ValueError for undeclared prerequisites or cycles.
    Does not mutate the input mapping or its lists.
    """
    if not dependencies:
        return []

    # Build in-degree map and adjacency list (prereq -> dependents)
    in_degree = {}
    dependents = {}

    for task in dependencies:
        in_degree[task] = 0
        dependents[task] = []

    for task, prereqs in dependencies.items():
        # Deduplicate prerequisites
        seen = set()
        for p in prereqs:
            if p in seen:
                continue
            seen.add(p)
            if p not in dependencies:
                raise ValueError(f"Undeclared prerequisite: {p}")
            in_degree[task] += 1
            dependents[p].append(task)

    # Initialize heap with all tasks that have in-degree 0
    heap = []
    for task, deg in in_degree.items():
        if deg == 0:
            heapq.heappush(heap, task)

    result = []
    while heap:
        task = heapq.heappop(heap)
        result.append(task)
        for dependent in dependents[task]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                heapq.heappush(heap, dependent)

    if len(result) != len(dependencies):
        raise ValueError("Cycle detected")

    return result
