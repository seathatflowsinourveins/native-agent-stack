"""Discover modules without importing or constructing any memory system."""

import importlib
import pkgutil

from ..types import MemoryAdapter


def list_arms() -> list[str]:
    return sorted(
        item.name for item in pkgutil.iter_modules(__path__)
        if not item.ispkg and not item.name.startswith("_")
    )


def build(name: str) -> MemoryAdapter:
    if name not in list_arms():
        raise ValueError(f"Unknown memory arm: {name!r}; available: {', '.join(list_arms())}")
    return importlib.import_module(f"{__name__}.{name}").build()
