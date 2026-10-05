"""Call-site protection for test tree copies, including top-level unittest discovery.

Use CPython's resolved-path containment primitives before its native copytree:
python/cpython@v3.13.15:Doc/library/pathlib.rst:513-530,934-949;
python/cpython@v3.13.15:Lib/shutil.py:550-596.
"""

from pathlib import Path
import shutil


def guarded_copytree(source, destination, **options):
    """Refuse a recursive destination before copytree creates or copies anything."""
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    if destination.is_relative_to(source):
        raise ValueError(
            f"Refusing recursive tree copy: destination {destination} is inside the source tree {source}. "
            "Choose scratch outside the source tree; keep TMPDIR outside the checkout."
        )
    return shutil.copytree(source, destination, **options)
