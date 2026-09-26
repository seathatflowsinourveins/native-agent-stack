"""Run the unchanged upstream test file against a stdlib-only detector shim (argv[2] prepended to sys.path)."""
import hashlib, importlib.util, inspect, sys
test, shim = sys.argv[1], sys.argv[2]
sys.path.insert(0, shim)
spec = importlib.util.spec_from_file_location('vt_shim', test)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
import headroom.transforms.content_detector as cd
src = open(cd.__file__, 'rb').read()
print('detector_blob', hashlib.sha1(b'blob %d\0' % len(src) + src).hexdigest(), 'from_shim', cd.__file__.startswith(shim))
p = 0; n = 0
for name, fn in inspect.getmembers(m, inspect.isfunction):
    if name.startswith('test_') and fn.__module__ == m.__name__:
        n += 1
        try:
            fn(); p += 1; print('PASS', name)
        except AssertionError:
            print('FAIL', name)
print(f'total={n} passed={p}')
