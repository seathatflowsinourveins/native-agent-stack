"""Offline tests for the pre-2020 delisting coverage collector.

No network access: exercises form.idx parsing, form-type filtering
(including amendments), accession-level dedupe, security-class
classification, company-name normalization, the bars-continue-after-
delisting trading-day check, and receipt-shape assembly against small
in-memory fixtures.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import date
from pathlib import Path

MODULE_PATH = (Path(__file__).resolve().parent.parent / "blueprints" / "us-equities" /
               "delisting-coverage" / "collect.py")

spec = importlib.util.spec_from_file_location("delisting_collect", MODULE_PATH)
collect = importlib.util.module_from_spec(spec)
sys.modules["delisting_collect"] = collect
spec.loader.exec_module(collect)

FIXTURE_HEADER = (
    "Description:           Master Index of EDGAR Dissemination Feed by Form Type\n"
    "Last Data Received:    March 31, 2016\n"
    "Comments:              webmaster@sec.gov\n"
    "Anonymous FTP:         ftp://ftp.sec.gov/edgar/\n"
    "\n\n\n"
    "Form Type   Company Name                                                  CIK         Date Filed  File Name\n"
    "---------------------------------------------------------------------------------------------------------------------------------------------\n"
)

FIXTURE_ROWS = [
    "25-NSE           AFFYMETRIX INC                                                913077      2016-03-31  edgar/data/913077/0001354457-16-000336.txt          \n",
    "25-NSE           ALCATEL LUCENT                                                886125      2016-02-25  edgar/data/886125/0000876661-16-000838.txt          \n",
    "25-NSE/A         ALCATEL LUCENT                                                886125      2016-03-01  edgar/data/886125/0000876661-16-000900.txt          \n",
    "25               SOME OTHER CO INC                                             222333      2016-04-15  edgar/data/222333/0001234567-16-000001.txt          \n",
    "25-NSE           ALPS ETF Trust                                                1414040     2016-03-30  edgar/data/1414040/0001143362-16-000260.txt         \n",
    "1-A              360 Sports, Inc.                                              1652577     2016-01-22  edgar/data/1652577/0001652577-16-000020.txt         \n",
    "10-K             Some Big Filer Corp                                           4455667     2016-02-01  edgar/data/4455667/0001112223-16-000005.txt         \n",
    "253G2            Some Reg A Filer                                              7788990     2016-01-05  edgar/data/7788990/0001112223-16-000006.txt         \n",
]


def write_fixture(tmp_path: Path) -> Path:
    idx_path = tmp_path / "2016QTR1.form.idx"
    idx_path.write_text(FIXTURE_HEADER + "".join(FIXTURE_ROWS), encoding="latin-1")
    return idx_path


class ParseFormIdxTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_parses_wanted_forms_only(self):
        idx_path = write_fixture(self.tmp_path)
        records = collect.parse_form_idx(idx_path, set(collect.DELISTING_FORMS))
        forms = sorted(r["form"] for r in records)
        self.assertEqual(forms, ["25", "25-NSE", "25-NSE", "25-NSE", "25-NSE/A"])

    def test_excludes_non_delisting_forms(self):
        idx_path = write_fixture(self.tmp_path)
        records = collect.parse_form_idx(idx_path, set(collect.DELISTING_FORMS))
        companies = {r["company"] for r in records}
        self.assertNotIn("360 Sports, Inc.", companies)
        self.assertNotIn("Some Big Filer Corp", companies)
        self.assertNotIn("Some Reg A Filer", companies)

    def test_field_values_extracted_correctly(self):
        idx_path = write_fixture(self.tmp_path)
        records = collect.parse_form_idx(idx_path, set(collect.DELISTING_FORMS))
        affy = next(r for r in records if r["cik"] == 913077)
        self.assertEqual(affy["form"], "25-NSE")
        self.assertEqual(affy["company"], "AFFYMETRIX INC")
        self.assertEqual(affy["date_filed"], "2016-03-31")
        self.assertEqual(affy["filename"], "edgar/data/913077/0001354457-16-000336.txt")
        self.assertEqual(affy["accession"], "0001354457-16-000336")

    def test_amendment_form_type_preserved(self):
        idx_path = write_fixture(self.tmp_path)
        records = collect.parse_form_idx(idx_path, set(collect.DELISTING_FORMS))
        amendment = next(r for r in records if r["form"] == "25-NSE/A")
        self.assertEqual(amendment["cik"], 886125)
        self.assertEqual(amendment["date_filed"], "2016-03-01")

    def test_variable_column_width_line_still_parses(self):
        # A line whose company-name field is padded to a different width than
        # the header's nominal column positions (observed on live EDGAR data).
        line = "25          A SHORT CO                     55555   2017-06-01  edgar/data/55555/0000000000-17-000001.txt\n"
        idx_path = self.tmp_path / "variant.idx"
        idx_path.write_text(FIXTURE_HEADER + line, encoding="latin-1")
        records = collect.parse_form_idx(idx_path, set(collect.DELISTING_FORMS))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["cik"], 55555)
        self.assertEqual(records[0]["company"], "A SHORT CO")

    def test_zero_wanted_rows_raises(self):
        # A file with a valid header/separator but no delisting-form rows at
        # all must fail loudly, not silently return an empty result.
        idx_path = self.tmp_path / "empty.idx"
        idx_path.write_text(FIXTURE_HEADER, encoding="latin-1")
        with self.assertRaises(RuntimeError):
            collect.parse_form_idx(idx_path, set(collect.DELISTING_FORMS))

    def test_missing_header_separator_raises(self):
        idx_path = self.tmp_path / "malformed.idx"
        idx_path.write_text("not a real index file\njust some text\n", encoding="latin-1")
        with self.assertRaises(RuntimeError):
            collect.parse_form_idx(idx_path, set(collect.DELISTING_FORMS))


class DedupeByAccessionTests(unittest.TestCase):
    def test_keeps_multiple_filings_per_cik_across_years(self):
        # A CIK filing two distinct deregistrations (different classes,
        # different years) must NOT be collapsed to one row.
        records = [
            {"form": "25-NSE", "cik": 1, "date_filed": "2016-05-01", "company": "A", "filename": "f1",
             "accession": "0000000000-16-000001"},
            {"form": "25-NSE", "cik": 1, "date_filed": "2018-02-01", "company": "A", "filename": "f2",
             "accession": "0000000000-18-000002"},
            {"form": "25-NSE/A", "cik": 1, "date_filed": "2016-06-01", "company": "A", "filename": "f3",
             "accession": "0000000000-16-000003"},
            {"form": "25", "cik": 2, "date_filed": "2017-01-01", "company": "B", "filename": "f4",
             "accession": "0000000000-17-000004"},
        ]
        base, amendments, raw_count, duplicates, fallback_stats = collect.dedupe_by_accession(records)
        self.assertEqual(len(base), 3)
        self.assertEqual(len(amendments), 1)
        self.assertEqual(raw_count, 4)
        self.assertEqual(duplicates, 0)
        self.assertEqual(fallback_stats["groups_using_name_fallback"], 0)
        years = sorted(r["date_filed"][:4] for r in base)
        self.assertEqual(years, ["2016", "2017", "2018"])

    def test_literal_duplicate_accession_collapsed(self):
        records = [
            {"form": "25-NSE", "cik": 1, "date_filed": "2016-05-01", "company": "A", "filename": "f1",
             "accession": "0000000000-16-000001"},
            {"form": "25-NSE", "cik": 1, "date_filed": "2016-05-01", "company": "A", "filename": "f1-dup",
             "accession": "0000000000-16-000001"},
        ]
        base, amendments, raw_count, duplicates, fallback_stats = collect.dedupe_by_accession(records)
        self.assertEqual(len(base), 1)
        self.assertEqual(raw_count, 2)
        self.assertEqual(duplicates, 1)

    def test_exchange_self_reference_duplicate_prefers_issuer_row(self):
        # 25-NSE is filed by the exchange on the issuer's behalf; EDGAR's
        # index cross-lists the same accession under both the exchange's
        # own CIK (== the accession's filer-CIK prefix) and the delisted
        # issuer's CIK. Dedup must keep the issuer row, not the exchange's
        # self-referential one.
        records = [
            {"form": "25-NSE", "cik": 1606180, "date_filed": "2019-11-12", "company": "AAC Holdings, Inc.",
             "filename": "edgar/data/1606180/0000876661-19-001129.txt", "accession": "0000876661-19-001129"},
            {"form": "25-NSE", "cik": 876661, "date_filed": "2019-11-12", "company": "NEW YORK STOCK EXCHANGE LLC",
             "filename": "edgar/data/876661/0000876661-19-001129.txt", "accession": "0000876661-19-001129"},
        ]
        base, amendments, raw_count, duplicates, fallback_stats = collect.dedupe_by_accession(records)
        self.assertEqual(len(base), 1)
        self.assertEqual(duplicates, 1)
        self.assertEqual(base[0]["cik"], 1606180)
        self.assertEqual(base[0]["company"], "AAC Holdings, Inc.")
        self.assertEqual(fallback_stats["groups_using_name_fallback"], 0)

    def test_filer_cik_from_accession(self):
        self.assertEqual(collect.filer_cik_from_accession("0000876661-19-001129"), 876661)

    def test_dedupe_fallback_used_when_no_row_matches_filer_cik(self):
        # Neither row's CIK equals the accession's filer-CIK prefix (e.g. an
        # amendment filed under yet another CIK). Dedup must fall back to
        # identifying the exchange row by name rather than picking
        # arbitrarily.
        records = [
            {"form": "25-NSE", "cik": 1354457, "date_filed": "2019-11-12", "company": "The Nasdaq Stock Market LLC",
             "filename": "edgar/data/1354457/0009999999-19-000001.txt", "accession": "0009999999-19-000001"},
            {"form": "25-NSE", "cik": 1606180, "date_filed": "2019-11-12", "company": "Some Issuer Inc.",
             "filename": "edgar/data/1606180/0009999999-19-000001.txt", "accession": "0009999999-19-000001"},
        ]
        base, amendments, raw_count, duplicates, fallback_stats = collect.dedupe_by_accession(records)
        self.assertEqual(len(base), 1)
        self.assertEqual(base[0]["cik"], 1606180)
        self.assertEqual(fallback_stats["groups_using_name_fallback"], 1)
        self.assertEqual(fallback_stats["groups_where_fallback_changed_the_pick"], 1)

    def test_is_exchange_row(self):
        self.assertTrue(collect.is_exchange_row({"company": "New York Stock Exchange LLC"}))
        self.assertTrue(collect.is_exchange_row({"company": "The Nasdaq Stock Market LLC"}))
        self.assertTrue(collect.is_exchange_row({"company": "Cboe BZX Exchange, Inc."}))
        self.assertFalse(collect.is_exchange_row({"company": "Dover Motorsports Inc"}))


class CountsTests(unittest.TestCase):
    def test_counts_by_year_form_is_true_per_year(self):
        records = [
            {"form": "25-NSE", "date_filed": "2016-01-01"},
            {"form": "25-NSE", "date_filed": "2016-06-01"},
            {"form": "25", "date_filed": "2016-01-01"},
            {"form": "25-NSE", "date_filed": "2017-01-01"},
        ]
        counts = collect.counts_by_year_form(records)
        self.assertEqual(counts["2016"]["25-NSE"], 2)
        self.assertEqual(counts["2016"]["25"], 1)
        self.assertEqual(counts["2017"]["25-NSE"], 1)

    def test_distinct_ciks_by_year(self):
        records = [
            {"cik": 1, "date_filed": "2016-01-01"},
            {"cik": 1, "date_filed": "2016-06-01"},
            {"cik": 2, "date_filed": "2016-06-01"},
            {"cik": 3, "date_filed": "2017-01-01"},
        ]
        counts = collect.distinct_ciks_by_year(records)
        self.assertEqual(counts["2016"], 2)
        self.assertEqual(counts["2017"], 1)


class ClassifySecurityTests(unittest.TestCase):
    def _cls(self, description, company_name):
        security_class, _rule = collect.classify_security(description, company_name)
        return security_class

    def test_common_stock(self):
        self.assertEqual(self._cls("Common Stock", "Some Co"), "common_ordinary_equity")

    def test_common_stock_with_attached_warrants_is_warrant_right_unit(self):
        # Round-3 fix: warrant/right/unit keywords are checked BEFORE common
        # equity keywords, so a compound description naming both common
        # stock and warrants no longer defaults to common equity.
        self.assertEqual(
            self._cls("Common Stock, par value $0.005 per share and Series A Warrants", "Axion"),
            "warrant_right_unit")

    def test_common_stock_purchase_rights_is_warrant_right_unit_not_common(self):
        # Round-3 fix: this is the measured DVD/ROG misclassification --
        # "Common Stock Purchase Rights" (a shareholder-rights/"poison
        # pill" plan) contains the literal substring "common stock" but is
        # not equity.
        self.assertEqual(self._cls("Common Stock Purchase Rights", "Dover Motorsports Inc"), "warrant_right_unit")

    def test_units_prefixed_is_warrant_right_unit_even_with_ordinary_share(self):
        self.assertEqual(
            self._cls("Units, each consisting of one Class A ordinary share and one-third of one warrant",
                       "SPAC Co"),
            "warrant_right_unit")

    def test_preferred(self):
        self.assertEqual(
            self._cls("6.25% Non-cumulative Guaranteed Trust Preferred Securities", "Bank Co"), "preferred")

    def test_preference_share_ads_is_preferred(self):
        self.assertEqual(self._cls("Preference Share ADS", "Foreign Bank Co"), "preferred")

    def test_debt(self):
        self.assertEqual(self._cls("6.25% Senior Notes Due 2019", "Some Co"), "debt")

    def test_bond_inside_etf_name_is_fund_not_debt(self):
        self.assertEqual(
            self._cls("PIMCO Global Advantage Inflation-Linked Bond Active Exchange-Traded Fund",
                       "PIMCO ETF Trust"),
            "fund_etf")

    def test_beneficial_interest_from_fund_style_issuer_is_fund_etf(self):
        # Round-3 fix: fund-style issuers (fund/trust/income/municipal/
        # closed-end/portfolio) whose class is "Common Shares of
        # Beneficial Interest" are fund/ETF, not common equity, even
        # though "common" appears in the text.
        self.assertEqual(
            self._cls("Common Shares of Beneficial Interest", "XYZ Municipal Income Trust"), "fund_etf")

    def test_beneficial_interest_without_fund_style_issuer_stays_common(self):
        # The beneficial-interest rule requires a fund-style issuer signal;
        # it must not fire on an unrelated company name.
        self.assertEqual(self._cls("Common Shares of Beneficial Interest", "Acme Manufacturing Co"),
                          "common_ordinary_equity")

    def test_warrant_only(self):
        self.assertEqual(self._cls("Class B Warrants", "Some Co"), "warrant_right_unit")

    def test_ordinary_shares(self):
        self.assertEqual(self._cls("Ordinary Shares", "Foreign Co"), "common_ordinary_equity")

    def test_unknown_when_no_description(self):
        self.assertEqual(self._cls("", "Some Co"), "unknown")

    def test_other_fallback(self):
        self.assertEqual(self._cls("Some unrecognized instrument type", "Some Co"), "other")

    def test_matched_rule_is_reported(self):
        security_class, rule = collect.classify_security("Common Stock", "Some Co")
        self.assertEqual(security_class, "common_ordinary_equity")
        self.assertEqual(rule, "common_keyword")


class ExtractDescriptionTests(unittest.TestCase):
    def test_xml_format(self):
        text = "<XML><descriptionClassSecurity>Common Stock</descriptionClassSecurity></XML>"
        self.assertEqual(collect.extract_description(text), "Common Stock")

    def test_html_format_takes_text_before_caption(self):
        text = ("<P>Common Stock, par value $0.005 per share and Series A Warrants</P>"
                "<P>(Description of class of securities)</P>")
        description = collect.extract_description(text)
        self.assertIn("Common Stock", description)

    def test_no_match_returns_empty(self):
        self.assertEqual(collect.extract_description("<P>nothing relevant here</P>"), "")


class NormalizeCompanyNameTests(unittest.TestCase):
    def test_strips_suffix_words_and_punctuation(self):
        self.assertEqual(collect.normalize_company_name("Boston Private Financial Holdings, Inc."),
                          "BOSTON PRIVATE FINANCIAL")

    def test_normalizes_consistently_for_matching(self):
        a = collect.normalize_company_name("Acme Corp.")
        b = collect.normalize_company_name("ACME CORPORATION")
        self.assertEqual(a, b)


class CountTradingDaysTests(unittest.TestCase):
    def test_same_day_is_zero(self):
        self.assertEqual(collect.count_trading_days(date(2018, 6, 14), date(2018, 6, 14)), 0)

    def test_counts_weekdays_only(self):
        # 2018-06-14 is a Thursday; through 2018-06-25 (Monday) is 8 weekdays
        # (Fri 15, Mon 18, Tue 19, Wed 20, Thu 21, Fri 22, Mon 25 -> 7) plus
        # verify no weekend days are counted.
        count = collect.count_trading_days(date(2018, 6, 14), date(2018, 6, 25))
        self.assertEqual(count, 7)

    def test_end_before_start_is_zero(self):
        self.assertEqual(collect.count_trading_days(date(2018, 6, 14), date(2018, 6, 1)), 0)


class SelectClassificationTargetsTests(unittest.TestCase):
    def _records(self):
        records = []
        for year, n in (("2016", 5), ("2017", 5), ("2018", 5), ("2019", 5)):
            for i in range(n):
                records.append({"cik": i, "date_filed": f"{year}-01-0{i+1}", "company": f"C{i}",
                                 "form": "25-NSE", "filename": f"f{year}{i}", "accession": f"acc-{year}-{i}"})
        return records

    def test_full_classification_returns_everything(self):
        targets, method, population, sampled = collect.select_classification_targets(
            self._records(), seed=1, sample_2016_2018=False)
        self.assertEqual(len(targets), 20)
        self.assertEqual(method, "full_classification")

    def test_sampled_mode_keeps_all_2019_and_caps_others(self):
        targets, method, population, sampled = collect.select_classification_targets(
            self._records(), seed=1, sample_2016_2018=True, sample_size=3)
        self.assertEqual(method, "all_2019_plus_seeded_400_sample_2016_2018")
        self.assertEqual(sampled["2019"], 5)  # full year, not sampled
        self.assertEqual(sampled["2016"], 3)  # capped by sample_size
        self.assertEqual(len(targets), 5 + 3 + 3 + 3)


class ReceiptShapeTests(unittest.TestCase):
    def test_build_receipt_has_required_keys(self):
        base = [{"cik": 1, "company": "A", "date_filed": "2016-01-01", "form": "25-NSE", "filename": "f",
                 "accession": "acc-1"}]
        amendments = []
        sources = [{"url": "https://example.test/x", "sha256": "abc", "bytes": 10, "cache_path": None,
                     "fetched_at": "2026-09-22T00:00:00+00:00"}]
        probe = {
            "sample_size_requested": 1, "sample_size_used": 1, "seed": 1,
            "ticker_resolution_rate": 1.0, "unresolved_fraction": 0.0,
            "resolution_method_counts": {}, "alpaca_bars_checked": False,
            "coverage_confirmed_rate": None, "events": [],
        }
        classification = {"scope": "x", "method": "full_classification", "classify_seed": 1,
                           "documents_classified": 0, "nse_population_by_year": {}, "sampled_counts_by_year": {},
                           "class_counts_by_year": {}, "common_ordinary_equity_by_year": {}}
        dedupe_fallback_stats = {"groups_using_name_fallback": 0, "groups_where_fallback_changed_the_pick": 0}
        reclass_diff = {"documents_compared": 0, "documents_moved": 0, "transitions": {}}
        extraction_method_counts = {}
        artifact_path = "evidence/artifacts/pre-2020-delisting/classifications-2016-2019.json"
        receipt = collect.build_receipt(base, amendments, sources, probe, 2016, 1, 2019, 4, raw_count=1,
                                         duplicate_count=0, classification=classification,
                                         dedupe_fallback_stats=dedupe_fallback_stats, reclass_diff=reclass_diff,
                                         extraction_method_counts=extraction_method_counts,
                                         artifact_path=artifact_path)
        for key in ("id", "kind", "evidence_class", "claim", "method", "sources", "counts",
                    "equity_classification", "sample_probe", "limitations", "observed_utc"):
            self.assertIn(key, receipt)
        self.assertEqual(receipt["evidence_class"], "open_regulator_source_measured")
        self.assertEqual(receipt["counts"]["deduped_base_filings"], 1)
        self.assertEqual(receipt["counts"]["raw_filing_rows_before_dedupe"], 1)
        self.assertEqual(receipt["equity_classification"]["artifact_path"], artifact_path)
        self.assertIn("reclassification_from_round2", receipt["equity_classification"])
        self.assertIsInstance(receipt["limitations"], list)
        self.assertGreater(len(receipt["limitations"]), 0)
        self.assertNotIn("not an implementation gap", " ".join(receipt["limitations"]))
        # The classification pass must not be called "exhaustive" as a
        # positive claim (residual misclassification risk is real); it is
        # fine for a limitation to say the rules are NOT exhaustive.
        self.assertNotIn("is exhaustive", " ".join(receipt["limitations"]))
        self.assertIn("NOT an exhaustive", " ".join(receipt["limitations"]))
        # No sampled events resolved a ticker in this fixture, so the claim
        # must not assert any bars were confirmed to stop.
        self.assertIn("No sampled events resolved a ticker", receipt["claim"])

    def test_claim_states_confirmed_count_honestly_when_some_confirmed(self):
        base = [{"cik": 1, "company": "A", "date_filed": "2016-01-01", "form": "25-NSE", "filename": "f",
                 "accession": "acc-1"}]
        probe = {
            "sample_size_requested": 1, "sample_size_used": 1, "seed": 1,
            "ticker_resolution_rate": 1.0, "unresolved_fraction": 0.0,
            "resolution_method_counts": {}, "alpaca_bars_checked": True,
            "coverage_confirmed_rate": 1.0,
            "events": [{"ticker": "ABC", "coverage_confirmed": True}],
        }
        classification = {"scope": "x", "method": "full_classification", "classify_seed": 1,
                           "documents_classified": 0, "nse_population_by_year": {}, "sampled_counts_by_year": {},
                           "class_counts_by_year": {}, "common_ordinary_equity_by_year": {}}
        receipt = collect.build_receipt(base, [], [], probe, 2016, 1, 2019, 4, raw_count=1, duplicate_count=0,
                                         classification=classification,
                                         dedupe_fallback_stats={"groups_using_name_fallback": 0,
                                                                 "groups_where_fallback_changed_the_pick": 0},
                                         reclass_diff={"documents_compared": 0, "documents_moved": 0,
                                                       "transitions": {}},
                                         extraction_method_counts={}, artifact_path="x.json")
        self.assertIn("1/1 resolved sampled events", receipt["claim"])


class RateLimiterTests(unittest.TestCase):
    def test_rate_limiter_enforces_minimum_interval(self):
        import time
        limiter = collect.RateLimiter(max_per_second=50)  # min_interval = 0.02s, fast for tests
        start = time.monotonic()
        limiter.wait()
        limiter.wait()
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, limiter.min_interval)


if __name__ == "__main__":
    unittest.main()
