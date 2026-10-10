"""The single qualified market data feed vocabulary for this paper lane.

Both the trading transport and the shadow research lane import this module, so
the qualified set is defined once and cannot drift between them. It has no SDK,
credential, network, account or order surface, so importing it adds no execution
capability to either caller.
"""
from __future__ import annotations

# alpaca-py 0.44.0, cc4cb3b7ba50ae250e621983c2779047fb16bb28,
# alpaca/data/enums.py:56-73: BOATS is the venue feed; OVERNIGHT is derived.
# Naming a feed does not establish entitlement or streaming acceptance.
DATA_FEEDS = ("iex", "sip", "boats")


def is_qualified_feed(value):
    """Accept only a plain ``str`` naming a qualified feed.

    ``type(value) is str`` is deliberate rather than ``isinstance``. An
    ``alpaca.data.enums.DataFeed`` member is a ``str`` subclass that compares
    equal to its value but formats as ``DataFeed.IEX``, which would silently
    build a malformed ``.../v2/DataFeed.IEX`` endpoint. Enum members are
    therefore refused; callers pass the configured plain string and convert to
    the SDK enum themselves.
    """
    return type(value) is str and value in DATA_FEEDS
