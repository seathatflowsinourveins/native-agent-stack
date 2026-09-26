"""Verifier's runner for one unchanged upstream test file (fixture-free test_* functions)."""
import hashlib, importlib.metadata as md, importlib.util, inspect, sys, traceback
path = sys.argv[1]
data = open(path, 'rb').read()
print('test_blob', hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest())
spec = importlib.util.spec_from_file_location('vt_upstream', path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
import headroom.transforms.content_detector as cd
src = open(cd.__file__, 'rb').read()
print('headroom-ai', md.version('headroom-ai'), 'detector_blob', hashlib.sha1(b'blob %d\0' % len(src) + src).hexdigest(), 'from_prefix', 'tools/headroom-ai-0.39.0' in cd.__file__, 'python-tools' in cd.__file__)
res = {}
for name, fn in inspect.getmembers(m, inspect.isfunction):
    if name.startswith('test_') and fn.__module__ == m.__name__:
        try:
            fn(); res[name] = 'PASS'
        except AssertionError:
            res[name] = 'FAIL'
        except Exception as e:
            res[name] = 'ERROR ' + type(e).__name__
for k, v in res.items():
    print(v, k)
p = sum(v == 'PASS' for v in res.values())
print(f'total={len(res)} passed={p} not_passed={len(res) - p}')
sys.exit(0 if p == len(res) else 1)
