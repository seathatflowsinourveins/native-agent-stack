# Mover early-entry study (v1, preregistered)

Can long-only rules that use only information available by an early time t select US-equity symbol-days whose
post-entry return is positive net of realistic costs? For each degree of eventual move, what share of movers do they
catch, and how early? `protocol.json` is the preregistration (`mover-early-entry-v1-20260924`). It was committed
before any post-entry return was computed or any quote was sampled, and revised from an adversarial pre-freeze review.

| File | Role |
| --- | --- |
| `candidates.py` | the provably complete candidate superset (the day's high >= 1.20 x the previous day's low), selection fields only |
| `collect.py` | 1-minute SIP bars 04:00-20:00 ET, official auctions and news timestamps per session (`asof` = session), every page hashed into a ledger, resumable |
| `sessions_io.py` | deterministic readers and the official open/close rule shared with the price audit |
| `protocol.json` | rules, exits, costs, statistics, pass criteria, leverage schedule, splits and data-quality gates |

All collected data and per-trade results stay private (SIP redistribution terms). Only aggregate results and hashes
are committed.
