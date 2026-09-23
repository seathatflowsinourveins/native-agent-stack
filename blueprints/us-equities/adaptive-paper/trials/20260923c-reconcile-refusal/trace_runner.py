"""Run the frozen runner's `paper` command unchanged, but print the traceback of any
exception raised inside run_native before the runner's own handler records only its type."""
import sys, traceback
sys.path.insert(0, ".")
import runner
original = runner.run_native
async def traced(*a, **kw):
    try:
        return await original(*a, **kw)
    except BaseException:
        traceback.print_exc(file=sys.stderr)
        raise
runner.run_native = traced
sys.argv = ["runner.py"] + sys.argv[1:]
raise SystemExit(runner.main())
