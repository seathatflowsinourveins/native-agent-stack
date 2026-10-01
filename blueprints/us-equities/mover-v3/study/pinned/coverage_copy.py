"""Byte-for-byte copies of definitions from blueprints/us-equities/broad-universe/coverage.py at aa6fc79 (git blob d08c5ec2f11a70717f6e7470d611ab307c6efd63).

Listed in study/pinned_copies.json and checked against that blob by tests/test_pinned_copies.py.
Nothing else from the source module is copied, so its module-level code never runs here.
"""
from collections import defaultdict


DUPLICATE_SERIES_MIN_SESSIONS = 20


DUPLICATE_SERIES_MIN_SPAN_COVERAGE = 0.98


CONTINUITY_RATIO = 1.5


def _rename_terminus(members, rename_pairs):
    """Follow retained old->new rename records inside one duplicate component to the
    terminal current ticker. A pair recorded in BOTH directions is no evidence and its
    edge is dropped. Returns the single terminus, or None when the records are absent,
    branching or cyclic."""
    member_set = set(members)
    edges = defaultdict(set)
    for old, new in rename_pairs:
        if old in member_set and new in member_set and (new, old) not in rename_pairs:
            edges[old].add(new)
    if not edges:
        return None
    termini = set()
    for member in members:
        seen = {member}
        current = member
        while True:
            following = edges.get(current)
            if not following:
                break
            if len(following) > 1:
                return None  # branching rename records: ambiguous
            current = next(iter(following))
            if current in seen:
                return None  # cycle: ambiguous
            seen.add(current)
        termini.add(current)
    return termini.pop() if len(termini) == 1 else None


def _components(pairs):
    """Connected components over duplicate pairs (rename chains A->B->C, three-way
    duplicates), so one survivor is chosen per group instead of pair by pair."""
    parent = {}

    def find(symbol):
        parent.setdefault(symbol, symbol)
        while parent[symbol] != symbol:
            parent[symbol] = parent[parent[symbol]]
            symbol = parent[symbol]
        return symbol

    for sym_a, sym_b in pairs:
        root_a, root_b = find(sym_a), find(sym_b)
        if root_a != root_b:
            parent[root_b] = root_a
    groups = defaultdict(set)
    for symbol in parent:
        groups[find(symbol)].add(symbol)
    return [sorted(members) for _, members in sorted(groups.items())]


def dedupe_identity(con, rename_pairs, active_symbols=frozenset(), rename_stats=None):
    """Remove bars served twice under two tickers (the provider answers an old ticker
    with its successor's history). Table `joined` is edited in place; returns a report.

    Everything is decided from an immutable snapshot taken before the first DELETE, so a
    symbol that a chain already dropped can never make a later lookup fail.

    A pair is a duplicate-series candidate when >= DUPLICATE_SERIES_MIN_SESSIONS sessions
    carry identical raw OHLCV (volume > 0) under both symbols AND those sessions cover at
    least DUPLICATE_SERIES_MIN_SPAN_COVERAGE of one side's rows inside the shared span.
    A pair that clears the session count but not the coverage is reported under
    partial_overlap_not_deduped and BOTH symbols are left untouched.

    Candidate pairs are grouped into connected components and ONE survivor is chosen per
    component, in order: retained rename records (chains followed to the terminal
    new_symbol); price continuity after the shared span; active asset-master status; then
    the lexicographic fallback, which is reported with identity_unresolved=true.

    For each non-survivor, its rows inside a shared span are removed - not only the
    byte-identical ones, so no sparse phantom series is left behind - but ONLY on sessions
    where a higher-ranked member it is paired with has a row. A survivor that lacks bars
    for an early part of a rename chain therefore never erases that history; it stays, once,
    under the latest-trading predecessor. Non-identical removed rows are reported as residue."""
    con.execute("""
        CREATE OR REPLACE TEMP TABLE dup_rows AS
        SELECT a.symbol AS sym_a, b.symbol AS sym_b, a.session_date
        FROM joined a JOIN joined b
          ON a.session_date = b.session_date AND a.symbol < b.symbol
         AND a.raw_o = b.raw_o AND a.raw_h = b.raw_h AND a.raw_l = b.raw_l
         AND a.raw_c = b.raw_c AND a.raw_v = b.raw_v
        WHERE a.raw_v > 0
    """)
    # Immutable snapshot: every decision below reads this, never the table being edited.
    con.execute("CREATE OR REPLACE TEMP TABLE identity_snapshot AS "
                "SELECT symbol, session_date, raw_c FROM joined")
    candidates = con.execute(f"""
        SELECT sym_a, sym_b, count(*) AS n, min(session_date), max(session_date)
        FROM dup_rows GROUP BY 1, 2 HAVING count(*) >= {DUPLICATE_SERIES_MIN_SESSIONS} ORDER BY 1, 2
    """).fetchall()

    def rows_in_span(symbol, first, last):
        return con.execute(
            "SELECT count(*) FROM identity_snapshot WHERE symbol = ? AND session_date BETWEEN ? AND ?",
            [symbol, first, last]).fetchone()[0]

    qualified = []
    partial = []
    for sym_a, sym_b, shared, first, last in candidates:
        rows_a, rows_b = rows_in_span(sym_a, first, last), rows_in_span(sym_b, first, last)
        ratio_a = shared / rows_a if rows_a else 0.0
        ratio_b = shared / rows_b if rows_b else 0.0
        entry = {"sym_a": sym_a, "sym_b": sym_b, "identical_sessions": shared,
                 "first": str(first), "last": str(last),
                 "span_coverage_sym_a": round(ratio_a, 6), "span_coverage_sym_b": round(ratio_b, 6),
                 "rows_in_span_sym_a": rows_a, "rows_in_span_sym_b": rows_b}
        if max(ratio_a, ratio_b) >= DUPLICATE_SERIES_MIN_SPAN_COVERAGE:
            qualified.append((sym_a, sym_b))
        else:
            entry["stage"] = "pair"
            entry["reason"] = ("identical sessions cover neither symbol's history inside the shared span; "
                               "coincidental matches are not identity evidence")
            partial.append(entry)

    # Only pairs that cleared BOTH tests are identity evidence; every query below reads
    # this restriction, so a disqualified coincidence can never widen a deletion span.
    con.execute("CREATE OR REPLACE TEMP TABLE qualified_pairs (sym_a VARCHAR, sym_b VARCHAR)")
    if qualified:
        con.executemany("INSERT INTO qualified_pairs VALUES (?, ?)", qualified)
    con.execute("""
        CREATE OR REPLACE TEMP TABLE qualified_dup AS
        SELECT d.sym_a, d.sym_b, d.session_date FROM dup_rows d
        JOIN qualified_pairs q ON d.sym_a = q.sym_a AND d.sym_b = q.sym_b
    """)

    report = []
    unresolved = 0
    components = _components(qualified)
    for members in components:
        member_set = set(members)
        pair_rows = con.execute(f"""
            SELECT max(session_date) FROM qualified_dup
            WHERE sym_a IN ({','.join('?' * len(members))}) AND sym_b IN ({','.join('?' * len(members))})
        """, members + members).fetchone()
        last = pair_rows[0]
        close_row = con.execute(f"""
            SELECT max(raw_c) FROM identity_snapshot
            WHERE session_date = ? AND raw_c IS NOT NULL AND symbol IN ({','.join('?' * len(members))})
        """, [last] + members).fetchone()
        last_close = close_row[0] if close_row else None

        def continues(symbol):
            row = con.execute(
                "SELECT raw_c FROM identity_snapshot WHERE symbol = ? AND session_date > ? "
                "AND raw_c IS NOT NULL ORDER BY session_date LIMIT 1", [symbol, last]).fetchone()
            if not row or not last_close:
                return False
            ratio = row[0] / last_close
            return 1 / CONTINUITY_RATIO <= ratio <= CONTINUITY_RATIO

        keep = _rename_terminus(members, rename_pairs)
        rule = "rename_record" if keep else None
        if keep is None:
            continuing = [m for m in members if continues(m)]
            if len(continuing) == 1:
                keep, rule = continuing[0], "price_continuity"
        if keep is None:
            actives = [m for m in members if m in active_symbols]
            if len(actives) == 1:
                keep, rule = actives[0], "active_status"
        if keep is None:
            keep, rule = min(members), "lexicographic_fallback"

        # Preference order inside the component: the survivor, then the members that trade
        # latest. Winners are resolved PER SESSION through transitive qualified links: on a
        # session where A~B and B~C are both in force, A, B and C are one security and only
        # the highest-ranked stays, even if A and C never qualified as a direct pair. A
        # session the survivor has no bar for keeps exactly one copy under the best-ranked
        # member that does, so a staggered rename chain never loses history.
        marks = ",".join("?" * len(members))
        last_seen = dict(con.execute(
            f"SELECT symbol, max(session_date) FROM identity_snapshot WHERE symbol IN ({marks}) GROUP BY 1",
            members).fetchall())
        ranked = [keep] + sorted((m for m in members if m != keep),
                                 key=lambda m: (-(last_seen[m].toordinal() if last_seen.get(m) else 0), m))
        rank_of = {m: i for i, m in enumerate(ranked)}
        dup_sessions = con.execute(
            f"SELECT sym_a, sym_b, session_date FROM qualified_dup WHERE sym_a IN ({marks}) AND sym_b IN ({marks})",
            members + members).fetchall()
        pair_span, identical_rows = {}, set()
        for sym_a, sym_b, day in dup_sessions:
            first, last_day = pair_span.get((sym_a, sym_b), (day, day))
            pair_span[(sym_a, sym_b)] = (min(first, day), max(last_day, day))
            identical_rows.update({(sym_a, day), (sym_b, day)})
        span_first = min(v[0] for v in pair_span.values())
        span_last = max(v[1] for v in pair_span.values())
        present = defaultdict(set)
        for symbol, day in con.execute(
                f"SELECT symbol, session_date FROM identity_snapshot WHERE symbol IN ({marks}) "
                "AND session_date BETWEEN ? AND ?", members + [span_first, span_last]).fetchall():
            present[day].add(symbol)

        entries, protected = {}, set()
        for drop in ranked[1:]:
            mine = [(k, v) for k, v in pair_span.items() if drop in k]
            first_shared = min(v[0] for _, v in mine)
            last_shared = max(v[1] for _, v in mine)
            identical = len({day for symbol, day in identical_rows
                             if symbol == drop and first_shared <= day <= last_shared})
            span_rows = rows_in_span(drop, first_shared, last_shared)
            ratio = identical / span_rows if span_rows else 0.0
            entry = {"kept": keep, "dropped": drop, "rule": rule, "identical_sessions": identical,
                     "first": str(first_shared), "last": str(last_shared),
                     "span_coverage": round(ratio, 6), "rows_in_span": span_rows,
                     "component_size": len(members),
                     "identity_unresolved": rule == "lexicographic_fallback"}
            if ratio < DUPLICATE_SERIES_MIN_SPAN_COVERAGE:
                entry["stage"] = "component"
                entry["reason"] = ("shared sessions do not cover this symbol's history inside the span; "
                                   "left untouched")
                partial.append(entry)
                protected.add(drop)
                continue
            entries[drop] = entry

        doomed = defaultdict(list)
        for day, symbols in present.items():
            linked = {m: {m} for m in symbols}
            for (sym_a, sym_b), (first, last_day) in pair_span.items():
                if sym_a in linked and sym_b in linked and first <= day <= last_day:
                    merged = linked[sym_a] | linked[sym_b]
                    for member in merged:
                        linked[member] = merged
            for group in {frozenset(v) for v in linked.values() if len(v) > 1}:
                winner = min(group, key=lambda m: rank_of[m])
                for member in group:
                    if member != winner and member not in protected:
                        doomed[member].append(day)

        for drop, entry in entries.items():
            days = doomed.get(drop, [])
            if days:
                # One bulk parameter: a per-session INSERT made multi-year duplicates ~20x slower.
                con.execute("DELETE FROM joined WHERE symbol = ? AND session_date IN "
                            "(SELECT unnest(CAST(? AS DATE[])))", [drop, days])
            entry["rows_removed"] = len(days)
            # Zero-volume halts and all-series-only rows are never byte-identical; count them
            # among the rows ACTUALLY removed, not across the whole component span.
            entry["residue_rows_removed"] = sum(1 for d in days if (drop, d) not in identical_rows)
            entry["rows_retained_without_survivor_row"] = max(0, entry["rows_in_span"] - len(days))
            if entry["identity_unresolved"]:
                unresolved += 1
            report.append(entry)

    rules = defaultdict(int)
    for item in report:
        rules[item["rule"]] += 1
    out = {"min_identical_sessions": DUPLICATE_SERIES_MIN_SESSIONS,
           "min_span_coverage": DUPLICATE_SERIES_MIN_SPAN_COVERAGE,
           "candidate_pairs": len(candidates), "qualified_pairs": len(qualified),
           "components": len(components),
           "pairs": len(report),
           "rows_removed": sum(item.get("rows_removed") or 0 for item in report),
           "residue_rows_removed": sum(item.get("residue_rows_removed") or 0 for item in report),
           "identity_unresolved_pairs": unresolved,
           "partial_overlap_not_deduped": partial,
           "by_rule": dict(rules), "detail": report}
    out.update(rename_stats or {})
    return out
