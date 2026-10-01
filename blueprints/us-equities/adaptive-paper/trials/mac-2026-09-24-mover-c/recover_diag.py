"""Run `mover_runner.py recover` unchanged, printing each TransportError's fixed internal message and raise site.

transport.py's TransportError messages are literal strings (no provider text or credentials); this
wrapper only reports them, because the receipts keep the error type alone by design.
"""
import sys
import traceback

sys.path.insert(0, ".")
import transport  # noqa: E402

_original = transport.TransportError.__init__


def _report(self, *args, **kwargs):
    frame = traceback.extract_stack(limit=4)[-2]
    print(f"DIAG TransportError({args[0] if args else ''!r}) at {frame.filename.rsplit('/', 1)[-1]}:{frame.lineno}",
          file=sys.stderr, flush=True)
    _original(self, *args, **kwargs)


transport.TransportError.__init__ = _report
import mover_runner  # noqa: E402

sys.exit(mover_runner.main(sys.argv[1:]))
