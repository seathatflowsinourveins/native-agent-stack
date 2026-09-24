"""Bounded provider-news and market-snapshot shadow watchlist on the one
configured data feed. No order, account or model API paths."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
from html import unescape
import importlib.metadata
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from credential_guard import (CredentialGuardError, MAX_CREDENTIAL_BYTES as GUARD_MAX_CREDENTIAL_BYTES,
                              REASON_ENCODING, open_verified)
from feeds import DATA_FEEDS, is_qualified_feed

SDK_VERSION = "0.44.0"
SDK_COMMIT = "cc4cb3b7ba50ae250e621983c2779047fb16bb28"
ORIGIN = "https://data.alpaca.markets"
SYMBOL = re.compile(r"[A-Z][A-Z0-9.\-]{0,14}\Z")
TAXONOMY = {
    "earnings": r"\b(earnings|eps|quarterly results|financial results)\b",
    "guidance": r"\b(guidance|outlook|forecast|raises? guidance|lowers? guidance)\b",
    "regulatory": r"\b(fda|approval|regulator|regulatory|antitrust|sec investigation|clinical trial)\b",
    "capital": r"\b(offering|buyback|repurchase|dividend|capital raise|debt financing|stock split)\b",
    "merger": r"\b(merger|acquisition|acquires?|takeover|buyout)\b",
}
CATEGORY_WEIGHT = {"earnings": 3, "guidance": 3, "regulatory": 3, "capital": 2, "merger": 3, "other": 0}


class ResearchError(RuntimeError):
    """Only bounded reason codes are exposed outside the private request process."""


def data_feed(value):
    """Return the one configured feed name; refuse any unqualified value.

    Only a plain ``str`` is accepted; a ``DataFeed`` enum member is refused
    because it formats as ``DataFeed.IEX`` rather than as its value.
    """
    if not is_qualified_feed(value):
        raise ResearchError("unqualified_data_feed")
    return value


def utc(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ResearchError("invalid_timestamp") from None
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ResearchError("timezone_required")
    return value.astimezone(timezone.utc)


def iso(value):
    return utc(value).isoformat().replace("+00:00", "Z")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def plain(value, limit):
    if not isinstance(value, str):
        raise ResearchError("invalid_text")
    return " ".join(unescape(re.sub(r"<[^>]*>", " ", value)).split())[:limit]


def decimal(value, *, positive=False):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ResearchError("invalid_numeric") from None
    if (not number.is_finite() or abs(number) > Decimal("1e15")
            or number.as_tuple().exponent < -18 or (positive and number <= 0)):
        raise ResearchError("invalid_numeric")
    return number


def fixed(value):
    value = format(value, "f")
    return value.rstrip("0").rstrip(".") if "." in value else value


def stock_price(value):
    value = decimal(value, positive=True)
    if value < Decimal("0.0001"):
        raise ResearchError("stock_price_below_supported_floor")
    return value


def stock_volume(value, *, positive=False):
    value = decimal(value, positive=positive)
    if value < 0 or value != value.to_integral_value():
        raise ResearchError("equity_volume_must_be_nonnegative_integer")
    return value


def _safe_url(value):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 2048:
        raise ResearchError("invalid_source_url")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ResearchError("invalid_source_url")
    return value


class ReadOnlySession:
    """Shared hard request count plus a two-path GET-only native SDK boundary."""
    def __init__(self, observed_now):
        import requests
        self._session = requests.Session()
        self._session.trust_env = False
        for adapter in self._session.adapters.values():
            adapter.max_retries = requests.adapters.Retry(total=0, connect=0, read=0, redirect=0)
        self.clock = observed_now
        self.requests = []
        self.news_observed = {}
        self.latest_news_has_more = None
        self.news_calls = 0
        self.snapshot_calls = 0

    def request(self, method, url, **kwargs):
        parsed = urlsplit(url)
        if (method.upper() != "GET" or f"{parsed.scheme}://{parsed.netloc}" != ORIGIN
                or parsed.query or parsed.fragment or parsed.username or parsed.password
                or parsed.path not in {"/v1beta1/news", "/v2/stocks/snapshots"}):
            raise ResearchError("readonly_endpoint_rejected")
        is_news = parsed.path == "/v1beta1/news"
        if len(self.requests) >= 3 or (is_news and self.news_calls >= 2) or (not is_news and self.snapshot_calls >= 1):
            raise ResearchError("request_budget_exhausted")
        if is_news:
            self.news_calls += 1
        else:
            self.snapshot_calls += 1
        observation = {"kind": "news" if is_news else "snapshot", "status": None}
        self.requests.append(observation)
        kwargs.update(timeout=(5, 5), allow_redirects=False, verify=True, proxies={})
        response = self._session.request(method, url, **kwargs)
        observed = iso(self.clock())
        observation.update(status=response.status_code, observed_at=observed,
                           rate_headers={key.lower(): value for key, value in response.headers.items()
                                         if key.lower() in {"x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset"}})
        if 300 <= response.status_code < 400:
            raise ResearchError("redirect_rejected")
        if response.status_code != 200:
            raise ResearchError("http_" + str(response.status_code))
        if len(response.content) > 2_000_000:
            raise ResearchError("response_too_large")
        if is_news:
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("news"), list):
                raise ResearchError("invalid_news_response")
            self.latest_news_has_more = bool(payload.get("next_page_token"))
            for row in payload["news"]:
                self.news_observed.setdefault(digest(row), observed)
        return response

    def close(self):
        self._session.close()


def normalize_news(raw, observed_at, as_of, requested_symbols):
    if not isinstance(raw, dict) or type(raw.get("id")) is not int or raw["id"] < 0:
        raise ResearchError("invalid_news_identity")
    created, updated, observed, cutoff = map(utc, (raw.get("created_at"), raw.get("updated_at"), observed_at, as_of))
    if updated < created:
        raise ResearchError("updated_before_created")
    if created > cutoff or updated > cutoff:
        raise ResearchError("future_news_at_request_cutoff")
    symbols = raw.get("symbols")
    if not isinstance(symbols, list) or any(not isinstance(s, str) or not SYMBOL.fullmatch(s) for s in symbols):
        raise ResearchError("invalid_news_symbols")
    matching = sorted(set(symbols) & set(requested_symbols))
    if not matching:
        raise ResearchError("outside_requested_universe")
    headline, summary = plain(raw.get("headline", ""), 500), plain(raw.get("summary", ""), 2000)
    if not headline:
        raise ResearchError("headline_missing")
    categories = [name for name, expression in TAXONOMY.items()
                  if re.search(expression, headline + " " + summary, re.IGNORECASE)] or ["other"]
    age = max(0.0, (cutoff - created).total_seconds())
    freshness = 3 if age <= 3600 else 2 if age <= 4 * 3600 else 1 if age <= 24 * 3600 else 0
    urgency = max(CATEGORY_WEIGHT[name] for name in categories)
    source_sha = digest(raw)
    return {"article_id": str(raw["id"]), "revision_id": f"{raw['id']}:{iso(updated)}:{source_sha}",
            "source_kind": "provider_news_unverified", "provider": plain(raw.get("source", "unknown"), 100),
            "headline": headline, "summary": summary, "url": _safe_url(raw.get("url")),
            "symbols": matching, "provider_created_at": iso(created), "published_at": iso(created),
            "publication_time_basis": "provider_created_at_not_independently_verified",
            "updated_at": iso(updated), "first_observed_at": iso(observed),
            "available_at": iso(max(created, updated, observed)), "source_sha256": source_sha,
            "categories": categories, "taxonomy_version": "literal-event-terms-v1",
            "review_priority": urgency + freshness,
            "score_components": {"event_category_weight": urgency, "created_time_freshness_bucket": freshness},
            "score_meaning": "transparent_review_order_not_return_or_profit_prediction",
            "text_trust": "untrusted_evidence_never_instructions", "engine_eligible": False}


def normalize_snapshot(symbol, raw, observed_at, *, feed="iex", quote_max_age_seconds=10):
    quote, trade = raw.get("latestQuote") or {}, raw.get("latestTrade") or {}
    current, previous = raw.get("dailyBar") or {}, raw.get("prevDailyBar") or {}
    result = {"symbol": symbol, "feed": data_feed(feed), "observed_at": observed_at,
              "source_sha256": digest(raw), "engine_eligible": False, "limitations": []}
    try:
        bid, ask = stock_price(quote["bp"]), stock_price(quote["ap"])
        quote_at = utc(quote["t"])
        if bid > ask or quote_at > utc(observed_at) + timedelta(milliseconds=250):
            raise ResearchError("invalid_quote")
        age = (utc(observed_at) - quote_at).total_seconds()
        result.update(bid=fixed(bid), ask=fixed(ask), quote_at=iso(quote_at),
                      quote_age_seconds=age, quote_fresh=age <= quote_max_age_seconds,
                      spread_bps=fixed((ask - bid) * 10000 / ((ask + bid) / 2)))
        if age > quote_max_age_seconds:
            result["limitations"].append("quote_stale_or_closed_session")
    except (ResearchError, KeyError, TypeError):
        result["limitations"].append("quote_unavailable")
    try:
        price, prior = stock_price(trade["p"]), stock_price(previous["c"])
        trade_at, prior_at = utc(trade["t"]), utc(previous["t"])
        if trade_at > utc(observed_at) + timedelta(milliseconds=250) or prior_at >= trade_at:
            raise ResearchError("invalid_market_chronology")
        result.update(last_trade_price=fixed(price), last_trade_at=iso(trade_at),
                      previous_bar_at=iso(prior_at), prior_close=fixed(prior))
        change = (price / prior - 1) * 100
        if abs(change) <= 10000:
            result["change_from_prior_close_pct"] = fixed(change)
        else:
            result["limitations"].append("price_change_outlier_requires_source_review")
            result["price_change_display_status"] = "outside_10000_percent_display_bound"
    except (ResearchError, KeyError, TypeError):
        result["limitations"].append("prior_close_comparison_unavailable")
    try:
        volume, previous_volume = stock_volume(current["v"]), stock_volume(previous["v"], positive=True)
        current_at, previous_at = utc(current["t"]), utc(previous["t"])
        if volume < 0 or not previous_at < current_at <= utc(observed_at):
            raise ResearchError("invalid_volume_chronology")
        result.update(current_bar_at=iso(current_at), current_bar_volume=fixed(volume),
                      previous_bar_volume=fixed(previous_volume))
        volume_ratio = volume / previous_volume
        if volume_ratio <= 1000:
            result["partial_day_to_prior_full_day_volume_ratio"] = fixed(volume_ratio)
        else:
            result["limitations"].append("volume_ratio_outlier_requires_source_review")
            result["volume_ratio_display_status"] = "outside_1000_times_display_bound"
        result["limitations"].append("volume_ratio_not_time_normalized_or_consolidated_market_rvol")
    except (ResearchError, KeyError, TypeError):
        result["limitations"].append("volume_comparison_unavailable")
    return result


def collect(key, secret, symbols, *, now, lookback_hours=24, max_items=50,
            include_snapshots=True, observed_now=None, feed="iex"):
    """Return a dated shadow artifact; at most two news GETs and one snapshot GET."""
    as_of = utc(now)
    feed = data_feed(feed)
    symbols = sorted(set(symbols))
    if (not symbols or len(symbols) > 30 or any(not SYMBOL.fullmatch(s) for s in symbols)
            or type(lookback_hours) is not int or not 1 <= lookback_hours <= 72
            or type(max_items) is not int or not 1 <= max_items <= 50):
        raise ResearchError("invalid_collection_bounds")
    if not key or not secret:
        raise ResearchError("explicit_credentials_required")
    if importlib.metadata.version("alpaca-py") != SDK_VERSION:
        raise ResearchError("sdk_version_mismatch")
    from alpaca.data.historical import NewsClient, StockHistoricalDataClient
    from alpaca.data.requests import NewsRequest, StockSnapshotRequest
    from alpaca.data.enums import DataFeed
    observed_now = observed_now or (lambda: datetime.now(timezone.utc))
    boundary = ReadOnlySession(observed_now)
    news = NewsClient(key, secret, raw_data=True, url_override=ORIGIN)
    stocks = StockHistoricalDataClient(key, secret, raw_data=True, url_override=ORIGIN)
    for client in (news, stocks):
        client._retry = 0
        client._session.close()
        client._session = boundary
    artifact = {"schema_version": 1, "lane": "shadow_market_research", "engine_eligible": False,
                "request_as_of": iso(as_of), "requested_start": iso(as_of - timedelta(hours=lookback_hours)),
                "symbols": symbols, "max_news_items": max_items, "feed": feed, "items": [], "quarantined": [],
                "market_context": [], "errors": [], "http_observations": boundary.requests,
                "sdk": {"name": "alpaca-py", "version": SDK_VERSION, "reviewed_commit": SDK_COMMIT},
                "model_advisory": {"status": "not_executed_unqualified", "engine_eligible": False,
                                   "pilot_reference": "agent-lab/tools/ecosystem/typesafe-pilot",
                                   "next_use": "independent_source_support_review_only"},
                "limitations": ["Provider news is not independently verified primary filing evidence.",
                                "Observed now; not original historical point-in-time availability.",
                                "Request window coverage is bounded, not a comprehensive market scan.",
                                "No order authority, pre-positioning claim or measured strategy profitability."]}
    try:
        try:
            payload = news.get_news(NewsRequest(symbols=",".join(symbols), start=as_of - timedelta(hours=lookback_hours),
                                               end=as_of, sort="desc", limit=max_items,
                                               include_content=False, exclude_contentless=False))
            raw_news = payload.get("news", [])
            if not isinstance(raw_news, list) or len(raw_news) > max_items:
                raise ResearchError("news_item_bound_exceeded")
            revisions, conflicted_articles = {}, set()
            for raw in raw_news:
                try:
                    source_sha = digest(raw)
                    row = normalize_news(raw, boundary.news_observed[source_sha], as_of, symbols)
                    key = (row["article_id"], row["updated_at"])
                    previous = revisions.get(key)
                    if previous and previous["source_sha256"] != row["source_sha256"]:
                        artifact["quarantined"].append({"reason": "conflicting_same_revision", "article_id": row["article_id"]})
                        revisions[key] = None
                        conflicted_articles.add(row["article_id"])
                    elif key not in revisions:
                        revisions[key] = row
                except (ResearchError, KeyError, TypeError, ValueError) as exc:
                    artifact["quarantined"].append({"reason": str(exc) if isinstance(exc, ResearchError) else "invalid_news_row"})
            latest = {}
            for row in revisions.values():
                if row is not None and row["article_id"] not in conflicted_articles and (
                        row["article_id"] not in latest or utc(row["updated_at"]) > utc(latest[row["article_id"]]["updated_at"])):
                    latest[row["article_id"]] = row
            artifact["items"] = sorted(latest.values(), key=lambda row: (-row["review_priority"], row["article_id"]))
            artifact["news_window_status"] = "capped_more_available" if boundary.latest_news_has_more else "returned_provider_window"
        except Exception as exc:
            artifact["errors"].append({"stage": "news", "code": str(exc) if isinstance(exc, ResearchError) else "news_request_failed"})
            artifact["news_window_status"] = "incomplete"
        if include_snapshots:
            try:
                snapshots = stocks.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=symbols, feed=DataFeed(feed)))
                observed = boundary.requests[-1]["observed_at"]
                for symbol in symbols:
                    if symbol not in snapshots:
                        artifact["market_context"].append({"symbol": symbol, "feed": feed, "engine_eligible": False,
                                                          "limitations": ["snapshot_missing"]})
                    else:
                        artifact["market_context"].append(normalize_snapshot(symbol, snapshots[symbol], observed, feed=feed))
            except Exception as exc:
                artifact["errors"].append({"stage": "snapshot", "code": str(exc) if isinstance(exc, ResearchError) else "snapshot_request_failed"})
        artifact["finished_at"] = iso(observed_now())
        artifact["status"] = "complete_bounded_shadow" if not artifact["errors"] else "partial_or_failed_shadow"
        artifact["review_queue"] = [{"article_id": row["article_id"], "revision_id": row["revision_id"],
                                    "priority": row["review_priority"], "source_sha256": row["source_sha256"],
                                    "required_review": "verify_entity_event_and_source_support", "engine_eligible": False}
                                   for row in artifact["items"]]
        artifact["artifact_sha256"] = digest(artifact)
        return artifact
    finally:
        boundary.close()


MAX_CREDENTIAL_BYTES = GUARD_MAX_CREDENTIAL_BYTES  # single source of truth: credential_guard.MAX_CREDENTIAL_BYTES


def credentials(path):
    """Fail closed on a paper-credential env file with unsafe permissions,
    ownership, or location before any content is read; then parse only
    explicit Alpaca variables, never execute an environment file.

    The ownership/mode/worktree-location rules and their fd-traversal-bound
    open live in `credential_guard.open_verified()`, shared with
    `runner.credentials()` so the two loaders cannot drift; this keeps
    `follow_symlinks=False`, i.e. a symlinked path is refused outright,
    matching this loader's prior O_NOFOLLOW behavior.

    The size cap is enforced by reading at most `MAX_CREDENTIAL_BYTES + 1`
    bytes from the already-open descriptor and rejecting a longer result,
    rather than trusting a separate `fstat` size observed earlier: nothing
    stops a writer with access to the file from appending to it between an
    earlier size check and the actual read, so the only size fact that can
    be trusted is how many bytes this exact read call returns.

    The file's `KEY=value` lines are required to be plain ASCII (see
    `runner.credentials`'s docstring for the same rule and rationale); a
    byte outside that range is refused before any line is parsed.
    """
    try:
        with open_verified(path, follow_symlinks=False) as handle:
            raw = handle.read(MAX_CREDENTIAL_BYTES + 1)
    except CredentialGuardError as error:
        raise ResearchError(str(error)) from None
    if len(raw) > MAX_CREDENTIAL_BYTES:
        raise ResearchError("invalid_credential_file")
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError:
        raise ResearchError(REASON_ENCODING) from None
    found = {}
    for line in lines:
        name, separator, value = line.strip().removeprefix("export ").partition("=")
        if separator and name in {"APCA_API_KEY_ID", "APCA_API_SECRET_KEY"}:
            if name in found:
                raise ResearchError("duplicate_credential_variable")
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if not value or any(c.isspace() for c in value) or "$" in value or "`" in value:
                raise ResearchError("invalid_credential_value")
            found[name] = value
    if len(found) != 2:
        raise ResearchError("required_credentials_missing")
    return found["APCA_API_KEY_ID"], found["APCA_API_SECRET_KEY"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--symbols", required=True, help="Comma-separated explicit research universe")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--now", help="UTC request-window end; defaults to current UTC")
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--max-items", type=int, default=50)
    parser.add_argument("--no-snapshots", action="store_true")
    parser.add_argument("--feed", default="iex", choices=list(DATA_FEEDS))
    args = parser.parse_args(argv)
    try:
        key, secret = credentials(args.env_file)
        artifact = collect(key, secret, args.symbols.split(","), now=args.now or datetime.now(timezone.utc),
                           lookback_hours=args.lookback_hours, max_items=args.max_items,
                           include_snapshots=not args.no_snapshots, feed=args.feed)
        args.out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(artifact, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        print(json.dumps({"status": artifact["status"], "items": len(artifact["items"]),
                          "quarantined": len(artifact["quarantined"]), "http_calls": len(artifact["http_observations"]),
                          "engine_eligible": False, "artifact_sha256": artifact["artifact_sha256"]}))
        return 0 if not artifact["errors"] else 1
    except Exception as exc:
        print(json.dumps({"status": "failed", "engine_eligible": False,
                          "error": str(exc) if isinstance(exc, ResearchError) else "research_failed"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
