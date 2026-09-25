"""Shared paths, module loading, clock helpers and the append-only journal.

Standard library only. The study's pure rules (``news_signal.py``) are loaded by path
from ``../news-llm`` so research and the live runner execute one code path; nothing in
that directory is copied or modified here.
"""

import hashlib
import importlib.util
import json
import os
import sys
import threading
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
NEWS_LLM = os.path.abspath(os.path.join(HERE, "..", "news-llm"))
NEWS_REVERSAL = os.path.abspath(os.path.join(HERE, "..", "news-reversal"))
REVERSAL_PROTOCOL = os.path.join(NEWS_REVERSAL, "forward-protocol.json")
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
CALENDAR_FILE = os.path.join(REPO, "blueprints/us-equities/mover-v3/data/session-calendar.json")
CREDENTIAL_GUARD = os.path.join(REPO, "blueprints/us-equities/adaptive-paper/credential_guard.py")
ORDER_CONTRACT = os.path.join(REPO, "blueprints/us-equities/order-contract/order_contract.py")

STATE_ROOT = os.path.expanduser("~/.local/state/native-agent-stack/research/sota-mover/news-forward")
SECRETS_DIR = os.path.expanduser("~/.config/codex-ecosystem/secrets")
TRADING_ENV = os.path.join(SECRETS_DIR, "alpaca-paper-3.env")
# Coordinator update 2026-09-25 01:46 ET: paper-3 is both the trading and the data key.
DATA_ENV = TRADING_ENV
# paper-2 belongs to other studies: never used here except to refuse a copied key id.
PAPER2_ENV = os.path.join(SECRETS_DIR, "alpaca-paper-2.env")
PAPER3_ENV = TRADING_ENV
PAPER4_ENV = os.path.join(SECRETS_DIR, "alpaca-paper-4.env")
# config.json "account": the one paper account a runtime may trade, and the accounts it must refuse (by file name
# and by a copied key id). Since 2026-09-25 the incentive engine owns paper-3; the counted rth_reversal test runs
# rev-only on its own paper-4 (coordinator runtime decision), which refuses paper-2 and paper-3.
ACCOUNTS = {
    "paper-3": {"env": "alpaca-paper-3.env", "refuse": ("alpaca-paper-2.env",)},
    "paper-4": {"env": "alpaca-paper-4.env", "refuse": ("alpaca-paper-2.env", "alpaca-paper-3.env")},
}
DEFAULT_ACCOUNT = "paper-3"


def account_envs(cfg):
    """(trading env path, [refused env paths], data env path) for a config's "account" and "data_env"."""
    name = (cfg or {}).get("account", DEFAULT_ACCOUNT)
    if name not in ACCOUNTS:
        raise ValueError(f"unknown account {name!r}")
    spec = ACCOUNTS[name]
    trading = os.path.join(SECRETS_DIR, spec["env"])
    data = os.path.join(SECRETS_DIR, (cfg or {}).get("data_env") or spec["env"])
    return trading, [os.path.join(SECRETS_DIR, r) for r in spec["refuse"]], data
MODEL_STORAGE = os.path.expanduser("~/.local/share/native-agent-stack/models/chronogpt-instruct")

NY = ZoneInfo("America/New_York")
UTC = timezone.utc
EVIDENCE_LABEL = "pilot"  # execution shakedown; not counted as forward-study evidence
STRATEGY_ID = "news-llm-forward-v0-pilot"
# Days on which the RTH window runs the preregistered rth_reversal arm (config rth_reversal.from).
# Whether such a day is a counted session is decided only by news-reversal/analyze.py (freeze and
# deployment records, code pins), never by this label.
REVERSAL_RUN_LABEL = "reversal_forward"
REVERSAL_STRATEGY_ID = "news-reversal-forward-v1"


def load_by_path(name, path):
    """Import a module from an explicit file (idempotent per module name)."""
    if name in sys.modules and getattr(sys.modules[name], "__file__", None) == path:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def news_signal():
    return load_by_path("news_signal", os.path.join(NEWS_LLM, "news_signal.py"))


def order_contract():
    return load_by_path("order_contract", ORDER_CONTRACT)


def credential_guard():
    return load_by_path("credential_guard", CREDENTIAL_GUARD)


def load_calendar(path=CALENDAR_FILE):
    sig = news_signal()
    with open(path, encoding="utf-8") as handle:
        return sig.Calendar.from_calendar_json(json.load(handle))


def utc_now():
    return datetime.now(UTC)


def iso(dt):
    return None if dt is None else dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class Journal:
    """Append-only JSONL, one file per trade date; each line is fsynced.

    Records never carry credentials. ``kind`` names the record type (news, eligibility,
    score, decision, order_intent, order_submitted, order_refused, fill, shadow_quote,
    close_mark, reconciliation, risk, lifecycle). ``evidence_label`` is the run's label:
    "pilot" before the reversal switch date, REVERSAL_RUN_LABEL from it.
    """

    def __init__(self, root, trade_date, clock=utc_now, evidence_label=EVIDENCE_LABEL):
        self.root = root
        self.dir = os.path.join(root, "journal")
        os.makedirs(self.dir, exist_ok=True)
        self.path = os.path.join(self.dir, f"{trade_date.isoformat()}.jsonl")
        self.clock = clock
        self.evidence_label = evidence_label
        self.lock = threading.Lock()
        self.counts = {}

    def write(self, kind, **fields):
        row = {"kind": kind, "at": iso(self.clock()), "evidence_label": self.evidence_label, **fields}
        line = json.dumps(row, sort_keys=True, default=str)
        with self.lock:
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            self.counts[kind] = self.counts.get(kind, 0) + 1
        return row


def read_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue  # a torn final line from a crash is skipped, never repaired
    return rows


def append_jsonl(path, row):
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
