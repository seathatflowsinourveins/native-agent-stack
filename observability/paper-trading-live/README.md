# Paper trading live view

A live record of an adaptive paper run, fed into the host's existing upstream stack
(OpenTelemetry Collector, Loki, Prometheus, Grafana). Paper endpoint only; nothing here
talks to the broker or writes a ledger.

- `runner.py paper --live-dir DIR` appends every decision and intent to `DIR/events.jsonl`
  as it happens and turns on NautilusTrader's own JSON file logger in `DIR/nautilus/`
  (`LoggerConfig(file_config=FileWriterConfig(file_format="json"))`, INFO and above).
  Without `--live-dir` the run is unchanged.
- `blueprints/us-equities/adaptive-paper/live_manifest.py` serves a loopback page, the
  same state as JSON and Prometheus `/metrics`, from that directory, the durable ledger
  (`sqlite3` read-only) and the STOP file, both bound to the run through the `run.json` the
  runner writes (otherwise the most recently written ledger and `<state-root>/STOP`). Account ids, fingerprints and balances are not
  shown (NautilusTrader logs each AccountState with balances at INFO; `balances=[...]` and
  `margins=[...]` are redacted); the ledger carries deltas from its baseline. Ledger intent
  counts cover every trial in the ledger; decision and intent counts cover the run directory.
- `collector-paper-trading.yaml`: two `file_log` receivers (run events, NautilusTrader
  log) and a pipeline into Loki that keeps bodies and redacts account identifiers. The
  ecosystem's privacy transform is not used here because it blanks bodies.
- `prometheus-job.yml`: a 5 s scrape of the manifest's `/metrics`.
- `paper-trading-live.json`: the Grafana dashboard (`uid` `paper-trading-live`), with
  stat and time-series panels from Prometheus and two Loki log panels.

NautilusTrader 2.0.0rc5 ships no live dashboard: its tearsheets take a `BacktestEngine`
or `BacktestResult`, its `ReportProvider` returns DataFrames, and the hosted "Nautilus
Cloud" dashboards are commercial and not yet available (checked 2026-09-23). Its JSON file
logger is the upstream live record used here.
