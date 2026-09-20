"""A deliberately incorrect dependency planner for the frozen repair fixture."""


def order_tasks(dependencies):
    """Return task names; the seed ignores prerequisite and validation rules."""
    return sorted(dependencies)
