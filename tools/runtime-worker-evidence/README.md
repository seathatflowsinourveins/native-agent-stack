# Owned worker gateway observation

This optional acceptance observer uses [mitmproxy v12.2.3](https://github.com/mitmproxy/mitmproxy/tree/6c09d56e4c29a92f5ad01b03199977584b8ea14f), its supported [reverse mode](https://docs.mitmproxy.org/stable/concepts/modes/#reverse-proxy), and the native [`responseheaders` streaming callback](https://github.com/mitmproxy/mitmproxy/blob/6c09d56e4c29a92f5ad01b03199977584b8ea14f/examples/addons/http-stream-modify.py). It observes a dedicated worker's loopback HTTP traffic. It is a local integration check; it is not an upstream acceptance test or backend identity attestation.

Set `STACK_WORKER_OBSERVATION` to a new private JSONL file outside the checkout, select an unused loopback port, and run:

```sh
rtk uv tool run --from mitmproxy==12.2.3 mitmdump --version
rtk uv tool run --from mitmproxy==12.2.3 mitmdump --quiet \
  --mode reverse:http://127.0.0.1:20128 --listen-host 127.0.0.1 \
  --listen-port <owned-port> --set confdir=<owned-private-state> \
  --set flow_detail=0 --scripts tools/runtime-worker-evidence/gateway_observer.py
```

For that acceptance run alone, point the worker's scoped gateway URL to the observer. Keep existing client and gateway settings. Do not use flow recording, local capture, TLS interception or another session's traffic. Stop only the owned observer process after the run.

The addon records model, effort, tool names/count, body length/hash, cache-key hash, status and selected Responses usage counters. It retains no credential values, request content, tool arguments or returned text, and returns response chunks unchanged. Request and flow IDs stay private. A frame over 2 MiB marks usage capture incomplete. Missing usage stays unknown. Gateway/provider counters are not a savings measurement; reasoning and cached-token counters are subsets and must not be added to totals.

Run the authored observer checks in the same pinned dependency environment:

```sh
rtk uv run --with mitmproxy==12.2.3 python -m unittest discover \
  -s tools/runtime-worker-evidence -p 'test_*.py'
```

Bare system Python does not supply mitmproxy; that invocation failed on import.
The checks preserve every fragmented streaming byte, reject unrelated endpoints,
retain unknown/overflow usage and observe native ResponsesLite tools under
`input[].type=additional_tools`. The namespace count is not a leaf-tool count.
