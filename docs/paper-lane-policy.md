# Paper lane authorization and acceptance

The user explicitly authorizes broker-specific IBKR and Alpaca paper E2E after
the current foundation work. This includes the bounded native connections and
paper orders needed to measure submit, fill/cancel, reconciliation and recovery.
Continue that authorized work without repeated human permission requests.
Progression depends on actual measured performance and operational results.
This policy records authority; it is not evidence that paper execution has run.

Paper and live are separate configurations. Live credentials have not been
provided and are not a prerequisite for paper. Verify the selected native paper
endpoint and account before enabling execution; never substitute a live endpoint.
Necessary native paper sign-in or unavailable paper configuration is a concrete
input to resolve, not a request to reauthorize the paper lane. Future live trading
requires its own explicit user authorization and readiness; no paper result grants
it. Paid hosting and purchases are also outside this paper authorization.

The coordinator freezes each bounded paper trial before execution:

- The strategy, instruments, native paper account/endpoint, adapter, session and
  data feed, including current broker entitlements and acceptable data age.
  Optional paid or advanced features are prerequisites only for cases using them.
- Numeric paper capital, order count, quantity/notional, exposure, loss, request
  rate, timeouts and observation window, plus outstanding-order and position
  disposition at the boundary. Use the user's objectives and existing settings;
  label assumptions and resolve material missing inputs before affected orders.
- Deterministic risk enforcement, a durable intent/order/fill journal, one writer
  per account, stable identities, idempotency, reconciliation, alerts and a kill
  switch. Pass the relevant offline failure cases before broker execution.
- Strategy-specific performance and operational criteria: net returns and costs,
  drawdown, fills/slippage, duplicate effects, unexplained account differences,
  reconnect/restart recovery and the evidence needed for each required case.

Do not replace these inputs with another approval gate, invent a universal
profitability threshold or lower frozen criteria after seeing results. Record
actual pass, fail and inconclusive outcomes, including unsuccessful trials and
unobserved broker events. A working connection or synthetic test does not prove
strategy quality; paper results do not guarantee live safety or future profits.
Models support research and review; deterministic code owns risk and order state.

Apply the [broker acceptance plan](../blueprints/us-equities/engine-nautilus/acceptance-plan.md)
and [architecture](../blueprints/us-equities/architecture/README.md) for the
selected adapter. Keep historical no-order receipts and frozen research protocols
unchanged. Their dated authorization wording records that earlier scope; this
policy governs current paper authority without changing their numeric criteria,
source bindings or observed results. Catalog inclusion does not accept a candidate
or authorize unsafe entrypoints, and one broker's result does not qualify another.
