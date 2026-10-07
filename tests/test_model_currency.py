"""Fixed-date policy fixtures; no model, credential or network operation."""

import copy
import hashlib
import json
from datetime import date
from pathlib import Path
import subprocess
import sys
import unittest

from scripts.validate import model_currency_problems

if __package__:
    from . import test_validate as publication_fixtures
else:
    import test_validate as publication_fixtures


TODAY = date(2026, 10, 7)


def inventory():
    return {
        "schema_version": 1, "inventory_status": "complete",
        "policy": {"max_release_age_days": 42, "max_landscape_age_days": 7, "refresh_lead_days": 2},
        "packages": [],
        "models": [{"id": "reader", "role": "document reading", "consumer": "native fixture",
                    "model_id": "vendor/model", "revision": "a" * 40,
                    "release_date": "2026-10-01", "release_source": "https://huggingface.co/vendor/model/commit/" + "a" * 40,
                    "checked_at": "2026-10-07", "status": "in_use",
                    "release_line": {"kind": "huggingface", "repository": "vendor/model", "ref": "main"}}],
    }


def landscape():
    return {"date": "2026-10-01", "sources": ["https://example.org/vendor/release"],
            "newer_candidates": [{"model_id": "vendor/new", "revision": "b" * 40,
                                  "source": "https://example.org/vendor/new", "reason": "Incompatible upstream package contract."}],
            "reason": "The supported upstream consumer does not yet qualify this replacement."}


def package_bound_inventory():
    data = inventory()
    data["packages"] = [{"id": "reader-tool", "latest_version": "4.0.10", "release_date": "2026-10-01",
                         "release_source": "https://pypi.org/project/reader-tool/4.0.10/", "checked_at": "2026-10-07",
                         "release_line": {"kind": "pypi", "package": "reader-tool"}}]
    data["models"][0].update(status="package_bound", release_date="2025-01-01",
                             package={"id": "reader-tool", "version": "4.0.10"})
    return data


class ModelCurrencyTests(unittest.TestCase):
    def assert_valid(self, document):
        self.assertEqual(model_currency_problems(document, TODAY), [])

    def assert_invalid(self, document, needle):
        self.assertTrue(any(needle in e for e in model_currency_problems(document, TODAY)))

    def test_fresh_and_exact_42_day_boundary_pass(self):
        data = inventory()
        self.assert_valid(data)
        data["models"][0]["release_date"] = "2026-08-26"
        self.assert_valid(data)

    def test_stale_without_landscape_fails(self):
        data = inventory()
        data["models"][0]["release_date"] = "2026-08-25"
        self.assert_invalid(data, "older than 42")

    def test_fresh_sourced_exception_and_seven_day_boundary_pass(self):
        data = inventory()
        row = data["models"][0]
        row.update(release_date="2026-08-01", landscape_check=landscape(), overturn="Consumer qualifies a current candidate.")
        self.assert_valid(data)
        row["landscape_check"]["date"] = "2026-09-30"
        self.assert_valid(data)

    def test_expired_exception_fails(self):
        data = inventory()
        row = data["models"][0]
        row.update(release_date="2026-08-01", landscape_check=landscape(), overturn="Upstream qualifies replacement.")
        row["landscape_check"]["date"] = "2026-09-29"
        self.assert_invalid(data, "within 7 days")

    def test_exception_needs_sources_reason_candidates_and_overturn(self):
        for field in ("sources", "reason", "newer_candidates"):
            with self.subTest(field=field):
                data = inventory()
                data["models"][0].update(release_date="2026-08-01", landscape_check=landscape(), overturn="A qualified replacement.")
                del data["models"][0]["landscape_check"][field]
                self.assertTrue(model_currency_problems(data, TODAY))
        data["models"][0]["landscape_check"] = landscape()
        del data["models"][0]["overturn"]
        self.assert_invalid(data, "overturn")

    def test_package_bound_joins_latest_package_and_uses_package_release(self):
        data = package_bound_inventory()
        row = data["models"][0]
        self.assert_valid(data)
        row["package"]["version"] = "4.0.9"
        self.assert_invalid(data, "recorded latest")
        row["package"] = {"id": "absent", "version": "4.0.10"}
        self.assert_invalid(data, "join a package")

    def test_package_bound_hub_model_keeps_exact_origin_revision(self):
        data = package_bound_inventory()
        self.assert_valid(data)
        data["models"][0]["revision"] = "main"
        self.assert_invalid(data, "exact Hugging Face commit SHA")

    def test_package_bound_model_requires_its_origin_release_line(self):
        data = package_bound_inventory()
        self.assert_valid(data)
        del data["models"][0]["release_line"]
        self.assert_invalid(data, "release_line")

    def test_old_shipping_package_also_requires_exception(self):
        data = inventory()
        data["packages"] = [{"id": "tool", "latest_version": "1", "release_date": "2026-08-01",
                             "release_source": "https://example.org/release", "checked_at": "2026-10-07",
                             "release_line": {"kind": "github_release", "repository": "vendor/tool"}}]
        data["models"][0].update(status="package_bound", package={"id": "tool", "version": "1"})
        self.assert_invalid(data, "older than 42")

    def test_malformed_dates_and_missing_source_fail(self):
        for field, value in (("release_date", "2026-02-30"), ("checked_at", "today"), ("release_date", "20261001"),
                             ("release_source", None), ("release_source", "not-a-url")):
            with self.subTest(field=field, value=value):
                data = inventory()
                data["models"][0][field] = value
                self.assertTrue(model_currency_problems(data, TODAY))

    def test_future_dates_unknown_status_and_nonexact_hf_revision_fail(self):
        for field, value in (("release_date", "2026-10-08"), ("status", "pending"), ("status", {}), ("revision", "main")):
            data = inventory()
            data["models"][0][field] = value
            self.assertTrue(model_currency_problems(data, TODAY))

    def test_pending_empty_scaffold_is_not_a_complete_inventory(self):
        data = inventory()
        data.update(models=[], inventory_status="pending")
        self.assert_valid(data)
        data["inventory_status"] = "complete"
        self.assert_invalid(data, "complete inventory")

    def test_latest_hub_line_cannot_be_an_immutable_pin_or_tag(self):
        for ref in ("a" * 40, "v1.0.0"):
            with self.subTest(ref=ref):
                data = inventory()
                data["models"][0]["release_line"]["ref"] = ref
                self.assert_invalid(data, "default main branch")

    def test_policy_cannot_relax_limits_and_duplicate_ids_fail(self):
        data = inventory()
        data["policy"]["max_release_age_days"] = 180
        self.assert_invalid(data, "policy")
        data = inventory()
        data["models"].append(copy.deepcopy(data["models"][0]))
        self.assert_invalid(data, "duplicate id")

    def test_misspelled_extra_fields_fail_at_every_inventory_object_level(self):
        cases = (
            ((), "schema_verion"),
            (("policy",), "refresh_leed_days"),
            (("packages", 0), "latest_verion"),
            (("models", 0), "landscape_chek"),
            (("models", 0, "package"), "verion"),
            (("models", 0, "landscape_check"), "newer_canddates"),
            (("models", 0, "landscape_check", "newer_candidates", 0), "reasion"),
        )
        for path, typo in cases:
            with self.subTest(path=path, typo=typo):
                data = package_bound_inventory()
                data["models"][0].update(landscape_check=landscape(), overturn="Upstream qualifies a replacement.")
                self.assert_valid(data)
                target = data
                for key in path:
                    target = target[key]
                target[typo] = "unrecognized"
                self.assert_invalid(data, typo)

    def test_release_line_kinds_accept_known_fields_and_reject_extra_fields(self):
        lines = (
            {"kind": "huggingface", "repository": "vendor/model", "ref": "main"},
            {"kind": "github_release", "repository": "vendor/tool"},
            {"kind": "pypi", "package": "reader-tool"},
            {"kind": "vendor_page", "url": "https://example.org/releases"},
        )
        for line in lines:
            for parent_path in (("packages", 0), ("models", 0)):
                with self.subTest(kind=line["kind"], parent_path=parent_path):
                    data = package_bound_inventory()
                    target = data[parent_path[0]][parent_path[1]]
                    target["release_line"] = copy.deepcopy(line)
                    self.assert_valid(data)
                    target["release_line"]["unrecognized_line_field"] = "typo"
                    self.assert_invalid(data, "unrecognized_line_field")

    def test_valid_https_sources_include_ipv6_ports_and_encoded_space(self):
        urls = (
            "https://example.org/release",
            "https://example.org:443/release",
            "https://example.org:8443/release?version=1.2#notes",
            "https://[2001:db8::1]/release",
            "https://[::1]:8443/release",
            "https://example.org/release?name=encoded%20space",
        )
        for url in urls:
            with self.subTest(url=url):
                data = package_bound_inventory()
                row = data["models"][0]
                row.update(landscape_check=landscape(), overturn="Upstream qualifies a replacement.")
                row["release_source"] = url
                data["packages"][0]["release_source"] = url
                row["landscape_check"]["sources"] = [url]
                row["landscape_check"]["newer_candidates"][0]["source"] = url
                row["release_line"] = {"kind": "vendor_page", "url": url}
                self.assert_valid(data)

    def test_malformed_https_authorities_whitespace_and_controls_fail_for_each_source(self):
        urls = (
            "https://example.org:not-a-port/release",
            "https://example.org:65536/release",
            "https://example.org:-1/release",
            "https://exa mple.org/release",
            "https://example.org/re lease",
            "https://example.org/\trelease",
            "https://example.org/\nrelease",
            "https://example.org/\x00release",
            "https://example.org/\x1frelease",
            "https://example.org/\x7frelease",
            "https://example.org/\x80release",
            "https://example.org/\u00a0release",
            "https://[::1]:not-a-port/release",
        )
        paths = (
            ("models", 0, "release_source"),
            ("packages", 0, "release_source"),
            ("models", 0, "landscape_check", "sources", 0),
            ("models", 0, "landscape_check", "newer_candidates", 0, "source"),
            ("models", 0, "release_line", "url"),
        )
        for url in urls:
            for path in paths:
                with self.subTest(url=url, path=path):
                    data = package_bound_inventory()
                    data["models"][0].update(landscape_check=landscape(), overturn="Upstream qualifies a replacement.")
                    data["models"][0]["release_line"] = {"kind": "vendor_page", "url": "https://example.org/releases"}
                    self.assert_valid(data)
                    target = data
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = url
                    self.assert_invalid(data, "HTTPS source URL")

    def test_stale_exception_cannot_be_qualified_by_a_malformed_landscape_source(self):
        for url in ("https://example.org:not-a-port/release", "https://exa mple.org/release"):
            with self.subTest(url=url):
                data = inventory()
                data["models"][0].update(release_date="2026-08-01", landscape_check=landscape(),
                                         overturn="Consumer qualifies a current candidate.")
                self.assert_valid(data)
                data["models"][0]["landscape_check"]["sources"] = [url]
                self.assert_invalid(data, "HTTPS source URL")

    def test_schema_closes_complete_objects_and_retains_model_origin_requirement(self):
        path = Path(__file__).resolve().parents[1] / "catalogs/foundation/model-currency.schema.json"
        schema = json.loads(path.read_text())
        model_schema = schema["properties"]["models"]["items"]
        objects = (
            (schema, {"schema_version", "inventory_status", "policy", "packages", "models"}),
            (schema["properties"]["policy"], {"max_release_age_days", "max_landscape_age_days", "refresh_lead_days"}),
            (schema["properties"]["packages"]["items"],
             {"id", "latest_version", "release_date", "release_source", "checked_at", "release_line"}),
            (model_schema, {"id", "role", "consumer", "model_id", "revision", "release_date", "release_source",
                            "checked_at", "status", "release_line", "package", "landscape_check", "overturn"}),
            (model_schema["properties"]["package"], {"id", "version"}),
            (model_schema["properties"]["landscape_check"], {"date", "sources", "newer_candidates", "reason"}),
            (model_schema["properties"]["landscape_check"]["properties"]["newer_candidates"]["items"],
             {"model_id", "revision", "source", "reason"}),
        )
        for object_schema, keys in objects:
            with self.subTest(keys=keys):
                self.assertEqual(object_schema["type"], "object")
                self.assertIs(object_schema.get("additionalProperties"), False)
                self.assertEqual(set(object_schema["properties"]), keys)
        line_keys = {
            "huggingface": {"kind", "repository", "ref"},
            "github_release": {"kind", "repository"},
            "pypi": {"kind", "package"},
            "vendor_page": {"kind", "url"},
        }
        for object_schema in schema["$defs"]["release_line"]["oneOf"]:
            kind = object_schema["properties"]["kind"]["const"]
            with self.subTest(kind=kind):
                self.assertIs(object_schema.get("additionalProperties"), False)
                self.assertEqual(set(object_schema["properties"]), line_keys[kind])
        self.assertIn("release_line", model_schema["required"])

    def test_daily_shape_check_can_report_stale_rows_without_hiding_invalid_source(self):
        data = inventory()
        data["models"][0]["release_date"] = "2026-08-01"
        self.assertEqual(model_currency_problems(data, TODAY, enforce_age=False), [])
        data["models"][0]["release_source"] = None
        self.assertTrue(model_currency_problems(data, TODAY, enforce_age=False))

    def test_existing_validate_cli_enforces_the_inventory_at_an_injected_date(self):
        fixture = publication_fixtures.PublicationValidationTests(methodName="runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        data = inventory()
        data["models"][0]["release_date"] = "2026-08-25"
        path = "catalogs/foundation/model-currency.json"
        fixture.write_json(path, data)
        content = (fixture.root / path).read_bytes()
        fixture.evidence["files"].append({"path": path, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)})
        fixture.save()
        script = Path(__file__).resolve().parents[1] / "scripts/validate.py"
        result = subprocess.run([sys.executable, str(script), "--root", str(fixture.root), "--today", "2026-10-07"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("older than 42", result.stdout)
        result = subprocess.run([sys.executable, str(script), "--root", str(fixture.root), "--today", "2026-09-01"],
                                capture_output=True, text=True)
        # A past clock cannot silently accept future checked_at or release evidence.
        self.assertEqual(result.returncode, 1)
        self.assertIn("future date", result.stdout)


if __name__ == "__main__":
    unittest.main()
