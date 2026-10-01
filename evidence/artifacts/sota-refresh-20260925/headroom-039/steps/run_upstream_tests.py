"""Run every test_* function of one unchanged upstream test file, in definition order.

Usage: <tool python> -s -B run_upstream_tests.py <test file read at the tag>
The functions take no fixtures, so no pytest is needed; this runner only calls them
and reports PASS/FAIL. It also prints which installed content_detector was imported
and that module's git blob id, so the result binds to a specific release.
"""

import hashlib
import importlib.util
import inspect
import sys


def git_blob(path: str) -> str:
    data = open(path, "rb").read()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


test_path = sys.argv[1]
print("test_file_blob", git_blob(test_path))
spec = importlib.util.spec_from_file_location("upstream_timestamp_test", test_path)
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except Exception as exc:  # an import failure is a recorded result, not a crash
    print("IMPORT_ERROR", type(exc).__name__, exc)
    sys.exit(2)

import importlib.metadata as md  # noqa: E402

import headroom.transforms.content_detector as cd  # noqa: E402

print("headroom-ai", md.version("headroom-ai"), "content_detector_blob", git_blob(cd.__file__))
passed = failed = 0
for name, fn in list(vars(mod).items()):
    if not (name.startswith("test_") and inspect.isfunction(fn) and fn.__module__ == mod.__name__):
        continue
    try:
        fn()
    except Exception as exc:
        failed += 1
        print("FAIL", name, type(exc).__name__, str(exc)[:160].replace("\n", " "))
    else:
        passed += 1
        print("PASS", name)
print(f"passed={passed} failed={failed}")
sys.exit(0 if failed == 0 else 1)
