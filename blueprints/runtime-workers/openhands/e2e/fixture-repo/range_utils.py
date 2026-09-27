"""Synthetic fixture: intentionally fails the frozen range-coalescing test."""


def compress_ranges(values):
    return [(value, value) for value in sorted(set(values))]
