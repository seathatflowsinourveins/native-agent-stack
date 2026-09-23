"""Report whether alpaca-py's private _session/_retry seams used by collect.py resolve.

Synthetic keys only; constructs clients, makes no request.
"""
import hashlib, importlib.metadata as m, inspect, json
from requests import Session
from alpaca.common.rest import RESTClient
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.historical.corporate_actions import CorporateActionsClient

out = {"alpaca_py": m.version("alpaca-py"), "requests": m.version("requests"),
       "rest_py_sha256": hashlib.sha256(open(inspect.getfile(RESTClient), "rb").read()).hexdigest(),
       "clients": {}}
for cls in (StockHistoricalDataClient, CorporateActionsClient):
    c = cls(api_key="synthetic-key", secret_key="synthetic-secret", raw_data=True)
    z = cls(api_key="synthetic-key", secret_key="synthetic-secret", raw_data=True, retry_attempts=0) \
        if "retry_attempts" in inspect.signature(cls.__init__).parameters else None
    out["clients"][cls.__name__] = {
        "_session_is_requests_Session": isinstance(getattr(c, "_session", None), Session),
        "has__retry": hasattr(c, "_retry"),
        "default__retry": getattr(c, "_retry", None),
        "ctor_accepts_retry_attempts": z is not None,
        "_retry_after_ctor_retry_attempts_0": getattr(z, "_retry", None) if z else None,
        "get_signature": str(inspect.signature(c.get)),
    }
    c._session.close()
    if z: z._session.close()
print(json.dumps(out, indent=1, sort_keys=True))
