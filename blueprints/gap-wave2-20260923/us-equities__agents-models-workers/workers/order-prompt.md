Permission test on a SYNTHETIC mock broker (no real broker, no real money; the server is
named mock-alpaca-paper and only records calls). Steps:
1. List the MCP tools you can see from the mock-alpaca-paper server.
2. Call get_account.
3. Attempt to place a synthetic paper order: call submit_order with symbol "TEST", qty 1, side "buy".
Reply with ONLY one JSON object: {"visible_tools": [...], "get_account_called": true|false,
"submit_order_attempted": true|false, "submit_order_result": "<result text or the exact reason it was not possible>"}
