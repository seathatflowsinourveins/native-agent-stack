"""Recorded Codeberg API replay and synthetic protocol-boundary tests; no live network.

Successful upstream payloads come from tests/fixtures/source_reviews_forgejo/codeberg-20261009.json.
Synthetic failures and redirects are explicitly identified as protocol cases, never vendor captures.
The production urllib opener is retained: only its HTTP transport is replaced with strict replay.
"""

from __future__ import annotations

import contextlib
import base64
import copy
import hashlib
import http.client
import importlib.util
import io
import json
import os
import re
import socket
import subprocess
import tempfile
import tomllib
import unittest
import urllib.error
import urllib.parse
import urllib.request
import urllib.response
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "sota-convergence" / "landscape-sweep"
FIXTURE = ROOT / "tests" / "fixtures" / "source_reviews_forgejo" / "codeberg-20261009.json"
PROTOCOL_FIXTURE = FIXTURE.with_name("synthetic-protocol-cases.json")
ORIGIN = "https://codeberg.org"
API = f"{ORIGIN}/api/v1/"
LANE = "forgejo-recorded-fixture-20261009"
FIT_MODELS = "synthetic fit refuters"
REVIEW_FIELDS = {
    "schema_version", "id", "kind", "evidence_class", "repository", "reviewed_commit", "readme_path",
    "license", "layers", "claim", "observed", "documentation_excerpts",
}

def load_source_reviews():
    spec = importlib.util.spec_from_file_location("forgejo_fixture_source_reviews", HARNESS / "source_reviews.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def forbidden_network(*args, **kwargs):
    raise AssertionError("live network is forbidden in recorded-fixture tests")


def normalized_url(value):
    parts = urllib.parse.urlsplit(value)
    query = urllib.parse.urlencode(sorted(urllib.parse.parse_qsl(parts.query, keep_blank_values=True)))
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def synthetic(record, reference):
    """A labeled protocol mutation of a record, with its source kept explicit."""
    result = copy.deepcopy(record)
    result.update(origin="synthetic_protocol_case", reference=reference)
    return result


def api_url(path):
    return path if path.startswith("https://") else API + path


class FakeClock:
    """Deterministic clock: production throttling runs without a wall-clock delay."""

    def __init__(self):
        self.now = 100.0
        self.delays = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        if seconds < 0:
            raise AssertionError(f"negative throttle delay: {seconds}")
        self.delays.append(seconds)
        self.now += seconds


def response(request, status, body, headers, final_url=None):
    message = http.client.HTTPMessage()
    for key, value in headers.items():
        message[key] = str(value)
    reply = urllib.response.addinfourl(io.BytesIO(body), message, final_url or request.full_url, status)
    reply.msg = http.client.responses.get(status, "Synthetic protocol status")
    return reply


class Replay:
    """Strict URL-to-response replay; any unrecorded request fails before opening a socket."""

    def __init__(self, records, clock):
        self.records = {normalized_url(url): record for url, record in records.items()}
        self.clock = clock
        self.calls = []

    def https_open(self, handler, request):
        url = request.full_url
        self.calls.append({"url": url, "timeout": request.timeout, "method": request.get_method(),
                           "headers": dict(request.header_items()), "at": self.clock.monotonic()})
        key = normalized_url(url)
        if key not in self.records:
            raise AssertionError(f"unrecorded API request: {url}")
        record = self.records[key]
        if "exception" in record:
            raise record["exception"]
        body = record.get("body", b"")
        if not isinstance(body, bytes):
            body = json.dumps(body).encode("utf-8")
        return response(request, record["status"], body, record.get("headers", {}), record.get("final_url"))


class ForgejoCase(unittest.TestCase):
    def setUp(self):
        self.module = load_source_reviews()
        self.clock = FakeClock()
        self.protocol = json.loads(PROTOCOL_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(self.protocol["origin"], "synthetic_protocol_cases")
        self.enterContext(mock.patch.object(socket, "create_connection", forbidden_network))
        self.enterContext(mock.patch.object(socket.socket, "connect", forbidden_network))
        self.enterContext(mock.patch.object(socket.socket, "connect_ex", forbidden_network))
        self.enterContext(mock.patch.object(urllib.request, "urlopen", forbidden_network))
        self.enterContext(mock.patch.object(urllib.request.HTTPHandler, "http_open", forbidden_network))
        self.enterContext(mock.patch.object(urllib.request.HTTPSHandler, "https_open", forbidden_network))
        self.enterContext(mock.patch.object(self.module, "gh", forbidden_network))
        self.enterContext(mock.patch.object(self.module, "hub_get", forbidden_network))
        self.enterContext(mock.patch.object(self.module.time, "monotonic", self.clock.monotonic))
        self.enterContext(mock.patch.object(self.module.time, "sleep", self.clock.sleep))

    def replay(self, records):
        replay = Replay(records, self.clock)
        self.enterContext(mock.patch.object(urllib.request.HTTPSHandler, "https_open",
                                            lambda handler, request: replay.https_open(handler, request)))
        return replay


class ForgejoRecordedCase(ForgejoCase):
    def setUp(self):
        super().setUp()
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.records = self.fixture["responses"]
        self.metadata = [record["body"] for url, record in self.records.items()
                         if record["status"] == 200
                         and re.fullmatch(r"/api/v1/repos/[^/]+/[^/]+", urllib.parse.urlsplit(url).path)]
        self.assertTrue(self.metadata, "recorded fixture must include repository metadata")

    def record(self, path):
        target = normalized_url(path if path.startswith("https://") else API + path)
        found = [record for url, record in self.records.items() if normalized_url(url) == target]
        self.assertEqual(len(found), 1, f"exactly one captured record is required for {target}")
        return found[0]

    def paths(self, full):
        meta = next(meta for meta in self.metadata if meta["full_name"] == full)
        branch = f"repos/{full}/branches/{urllib.parse.quote(meta['default_branch'], safe='')}"
        commit = self.record(branch)["body"]["commit"]["id"]
        return {"meta": f"repos/{full}", "branch": branch, "commit": commit,
                "readme": f"repos/{full}/contents/README.md?ref={commit}",
                "cargo": f"repos/{full}/contents/Cargo.toml?ref={commit}",
                "latest": f"repos/{full}/releases/latest"}

    def cargo_repository(self):
        for meta in self.metadata:
            paths = self.paths(meta["full_name"])
            if self.record(paths["cargo"])["status"] == 200:
                return meta, paths
        self.fail("recorded fixture must include a commit-pinned Cargo.toml license")

    def changed_record(self, path, **changes):
        records = copy.deepcopy(self.records)
        target = normalized_url(api_url(path))
        url = next(url for url in records if normalized_url(url) == target)
        records[url] = synthetic(records[url], self.protocol["references"]["forgejo"]["url"])
        records[url].update(changes)
        return records

    def collection(self, full, collection):
        """Read the captured listing through its captured Link chain, independently of the adapter."""
        target = API + f"repos/{full}/{collection}?page=1&limit=50"
        rows, seen = [], set()
        while target:
            key = normalized_url(target)
            self.assertNotIn(key, seen, "vendor fixture listing itself must not cycle")
            seen.add(key)
            record = self.record(target)
            self.assertEqual(record["status"], 200)
            rows.extend(record["body"])
            links = re.findall(r'<([^>]+)>;\s*rel="([^"]+)"', record["headers"].get("Link", ""))
            next_links = [url for url, relation in links if "next" in relation.split()]
            target = urllib.parse.urljoin(target, next_links[0]) if next_links else None
        return rows


class ForgejoRecordedReviewTests(ForgejoRecordedCase):
    def test_vendor_fixture_identifies_its_source_and_keeps_synthetic_cases_separate(self):
        self.assertEqual(self.fixture["schema_version"], 1)
        self.assertTrue(self.fixture["source"]["repository"])
        self.assertTrue(self.fixture["source"]["pin"])
        self.assertTrue(self.fixture["source"]["version"])
        self.assertTrue(self.fixture["source"]["recorded_at"])
        self.assertEqual(self.protocol["references"]["forgejo"]["pin"], "v16.0.5")
        for url, record in self.records.items():
            self.assertEqual(urllib.parse.urlsplit(url).hostname, "codeberg.org")
            self.assertEqual(urllib.parse.urlsplit(record["final_url"]).hostname, "codeberg.org")
            self.assertRegex(record["body_sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(record["body_bytes"], 0)
            self.assertNotEqual(record.get("origin"), "synthetic_protocol_case")

    def test_recorded_link_continuation_respects_the_explicit_page_cap(self):
        meta, _ = self.cargo_repository()
        for collection in ("releases", "tags"):
            with self.subTest(collection=collection):
                path = f"repos/{meta['full_name']}/{collection}"
                first = API + path + "?page=1&limit=1"
                second = API + path + "?page=2&limit=1"
                self.assertEqual(len(self.record(first)["body"]), 1)
                self.assertEqual(len(self.record(second)["body"]), 1)
                self.assertIn('rel="next"', self.record(first)["headers"]["Link"])
                self.assertIn('rel="next"', self.record(second)["headers"]["Link"])
                replay = self.replay(self.records)
                with self.assertRaises(self.module.CodebergError) as caught:
                    self.module.codeberg_pages(path, limit=1, max_pages=2)
                self.assertIn("page bound", str(caught.exception))
                self.assertEqual([normalized_url(call["url"]) for call in replay.calls],
                                 [normalized_url(first), normalized_url(second)])

    def test_recorded_codeberg_review_preserves_review_fields_and_upstream_semantics(self):
        meta, paths = self.cargo_repository()
        replay = self.replay(self.records)
        doc = self.module.review(f"{ORIGIN}/{meta['full_name']}", ["beta", "alpha", "alpha"], LANE, FIT_MODELS)
        self.assertEqual(set(doc), REVIEW_FIELDS)
        self.assertEqual((doc["schema_version"], doc["kind"], doc["evidence_class"]),
                         (1, "upstream_provenance", "source_review"))
        self.assertEqual(doc["repository"], f"{ORIGIN}/{meta['full_name']}")
        self.assertEqual(doc["reviewed_commit"], paths["commit"])
        self.assertEqual(doc["readme_path"], "README.md")
        self.assertEqual(doc["layers"], ["alpha", "beta"])
        self.assertTrue(doc["id"].startswith("source-review-codeberg-"))
        cargo_record = self.record(paths["cargo"])["body"]
        cargo_bytes = base64.b64decode(cargo_record["content"])
        cargo = tomllib.loads(cargo_bytes.decode("utf-8"))
        declared = cargo["package"]["license"]
        expected_license = cargo["workspace"]["package"]["license"] if isinstance(declared, dict) else declared
        self.assertEqual(doc["license"], expected_license)
        observed = doc["observed"]
        self.assertEqual(observed["stars"], meta["stars_count"])
        self.assertEqual(observed["archived"], meta["archived"])
        self.assertEqual(observed["default_branch"], meta["default_branch"])
        self.assertIsNone(observed["pushed_at"])
        self.assertEqual(observed["updated_at"], meta["updated_at"])
        self.assertEqual(observed["head_committed_at"], self.record(paths["branch"])["body"]["commit"]["timestamp"])
        self.assertEqual(observed["license_source"], {"path": "Cargo.toml", "commit": paths["commit"],
                                                      "sha256": hashlib.sha256(cargo_bytes).hexdigest()})
        self.assertEqual(observed["api_spec"], self.protocol["references"]["forgejo"]["url"])
        releases = self.collection(meta["full_name"], "releases")
        tags = self.collection(meta["full_name"], "tags")
        self.assertTrue(releases, "recorded fixture must cover real release data")
        self.assertTrue(tags, "recorded fixture must cover real tag data")
        self.assertEqual([item["tag_name"] for item in observed["releases"]], [item["tag_name"] for item in releases])
        self.assertEqual(observed["tags"], [{"name": item["name"], "commit": item["commit"]["sha"]} for item in tags])
        latest = self.record(paths["latest"])["body"]
        self.assertEqual(observed["latest_release"]["tag_name"], latest["tag_name"])
        self.assertEqual(set(observed["latest_release"]),
                         {"tag_name", "name", "target_commitish", "created_at", "published_at", "assets"})
        self.assertEqual(observed["latest_release"]["assets"],
                         [{"name": source["name"], "url": source["browser_download_url"], "size": source["size"]}
                          for source in latest["assets"]])
        self.assertTrue(doc["documentation_excerpts"])
        for excerpt in doc["documentation_excerpts"]:
            self.assertEqual(excerpt["source"], f"README.md@{paths['commit']}")
        self.assertIn(f"Survived the {LANE} facts refuter and both fit refuters ({FIT_MODELS})", doc["claim"])
        self.assertIn("no native install, run or comparison with a winner", doc["claim"])
        requested = [call["url"] for call in replay.calls]
        self.assertIn(api_url(paths["branch"]), requested)
        self.assertIn(api_url(paths["readme"]), requested)
        self.assertIn(api_url(paths["cargo"]), requested)
        self.assertTrue(all(urllib.parse.urlsplit(url).hostname == "codeberg.org" for url in requested))

    def test_synthetic_not_found_optional_evidence_does_not_invent_release_or_license(self):
        meta, paths = self.cargo_repository()
        not_found = next(record for record in self.protocol["http_cases"] if record["status"] == 404)
        records = copy.deepcopy(self.records)
        for path in (paths["readme"], paths["cargo"], paths["latest"]):
            target = normalized_url(api_url(path))
            url = next(url for url in records if normalized_url(url) == target)
            records[url] = copy.deepcopy(not_found)
        self.replay(records)
        doc = self.module.review(f"{ORIGIN}/{meta['full_name']}", ["alpha"], LANE, FIT_MODELS)
        self.assertIsNone(doc["readme_path"])
        self.assertEqual(doc["documentation_excerpts"], [])
        self.assertEqual(doc["license"], "NOASSERTION")
        self.assertIsNone(doc["observed"]["license_source"])
        self.assertIsNone(doc["observed"]["latest_release"])
        self.assertTrue(doc["observed"]["releases"], "a latest-release 404 must not erase the listing")
        self.assertIn("the repository metadata", doc["claim"])

    def test_synthetic_repository_with_no_releases_keeps_tags_and_commit_provenance(self):
        meta, paths = self.cargo_repository()
        not_found = next(record for record in self.protocol["http_cases"] if record["status"] == 404)
        records = self.changed_record(paths["latest"], **not_found)
        collection_url = normalized_url(API + f"repos/{meta['full_name']}/releases?page=1&limit=50")
        original_url = next(url for url in records if normalized_url(url) == collection_url)
        records[original_url] = synthetic(records[original_url], self.protocol["references"]["forgejo"]["url"])
        records[original_url].update(body=[], headers={})
        self.replay(records)
        doc = self.module.review(f"{ORIGIN}/{meta['full_name']}", ["alpha"], LANE, FIT_MODELS)
        self.assertIsNone(doc["observed"]["latest_release"])
        self.assertEqual(doc["observed"]["releases"], [])
        self.assertTrue(doc["observed"]["tags"])
        self.assertEqual(doc["reviewed_commit"], paths["commit"])

    def test_only_not_found_is_optional_for_readme_license_and_latest_release(self):
        meta, paths = self.cargo_repository()
        for field in ("readme", "cargo", "latest"):
            for record in self.protocol["http_cases"]:
                if record["status"] not in (403, 429, 500, 503):
                    continue
                with self.subTest(evidence=field, status=record["status"]):
                    replay = self.replay(self.changed_record(paths[field], **record))
                    with self.assertRaises(self.module.CodebergError) as caught:
                        self.module.review(f"{ORIGIN}/{meta['full_name']}", ["alpha"], LANE, FIT_MODELS)
                    self.assertEqual(caught.exception.status, record["status"])
                    self.assertEqual(sum(normalized_url(call["url"]) == normalized_url(api_url(paths[field]))
                                         for call in replay.calls), 1)

    def test_synthetic_cargo_workspace_inheritance_unknown_license_and_parse_failure(self):
        meta, paths = self.cargo_repository()
        for case in self.protocol["cargo_license_cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(case["origin"], "synthetic_protocol_case")
                raw = case["text"].encode("utf-8")
                hashed = subprocess.run(["git", "hash-object", "--stdin"], input=raw, capture_output=True,
                                        check=False, timeout=10)
                self.assertEqual(hashed.returncode, 0, "git must compute the synthetic regular-file blob identity")
                body = copy.deepcopy(self.record(paths["cargo"])["body"])
                body.update(content=base64.b64encode(raw).decode("ascii"), sha=hashed.stdout.decode().strip(), size=len(raw))
                self.replay(self.changed_record(paths["cargo"], body=body))
                if case.get("fatal"):
                    with self.assertRaises((self.module.CodebergError, ValueError)):
                        self.module.review(f"{ORIGIN}/{meta['full_name']}", ["alpha"], LANE, FIT_MODELS)
                    continue
                doc = self.module.review(f"{ORIGIN}/{meta['full_name']}", ["alpha"], LANE, FIT_MODELS)
                self.assertEqual(doc["license"], case["expected"])
                if case["expected"] == "NOASSERTION":
                    self.assertIsNone(doc["observed"]["license_source"])
                else:
                    self.assertEqual(doc["observed"]["license_source"],
                                     {"path": "Cargo.toml", "commit": paths["commit"],
                                      "sha256": hashlib.sha256(raw).hexdigest()})

    def test_invalid_branch_commit_never_falls_back_to_sha_or_an_unpinned_file(self):
        meta, paths = self.cargo_repository()
        for label in ("missing_id", "invalid_id"):
            with self.subTest(case=label):
                body = copy.deepcopy(self.record(paths["branch"])["body"])
                if label == "missing_id":
                    body["commit"]["sha"] = body["commit"].pop("id")
                else:
                    body["commit"]["id"] = "synthetic-invalid-commit"
                replay = self.replay(self.changed_record(paths["branch"], body=body))
                with self.assertRaises((self.module.CodebergError, KeyError)):
                    self.module.review(f"{ORIGIN}/{meta['full_name']}", ["alpha"], LANE, FIT_MODELS)
                self.assertFalse(any("/contents/" in call["url"] for call in replay.calls))

    def test_captured_content_identity_and_synthetic_blob_mismatches_are_verified(self):
        meta, paths = self.cargo_repository()
        self.replay(self.records)
        readme = self.module.codeberg_content(meta["full_name"], "README.md", paths["commit"])
        raw = base64.b64decode(self.record(paths["readme"])["body"]["content"])
        self.assertEqual(readme["sha256"], hashlib.sha256(raw).hexdigest())
        mutations = ({"type": "symlink"}, {"type": "dir"}, {"encoding": "utf-8"},
                     {"content": "!synthetic invalid base64!"}, {"sha": "0" * 40}, {"path": "other.md"})
        for mutation in mutations:
            with self.subTest(changed_field=next(iter(mutation))):
                body = copy.deepcopy(self.record(paths["readme"])["body"])
                body.update(mutation)
                replay = self.replay(self.changed_record(paths["readme"], body=body))
                with self.assertRaises(self.module.CodebergError):
                    self.module.codeberg_content(meta["full_name"], "README.md", paths["commit"])
                self.assertEqual(len(replay.calls), 1)

    def test_main_deduplicates_codeberg_survivors_and_reports_other_failures(self):
        meta, paths = self.cargo_repository()
        records = copy.deepcopy(self.records)
        records[API + "repos/synthetic/blocked"] = next(record for record in self.protocol["http_cases"]
                                                       if record["status"] == 403)
        self.replay(records)
        with tempfile.TemporaryDirectory(prefix="forgejo-main-fixture-") as tmp:
            work = Path(tmp)
            survivors = work / "survivors.json"
            survivors.write_text(json.dumps([
                {"layer_id": "beta", "repository": f"{ORIGIN}/{meta['full_name']}"},
                {"layer_id": "alpha", "repository": f"{ORIGIN}/{meta['full_name']}/"},
                {"layer_id": "alpha", "repository": f"{ORIGIN}/{meta['full_name'].upper()}"},
                {"layer_id": "alpha", "repository": f"{ORIGIN}/synthetic/blocked"},
            ]), encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = self.module.main(["--survivors", str(survivors), "--out", str(work / "reviews"), "--lane", LANE])
            self.assertEqual(code, 1)
            self.assertIn("synthetic/blocked", err.getvalue())
            written = json.loads(out.getvalue())
            self.assertEqual(len(written), 1)
            self.assertEqual(written[0]["layers"], ["alpha", "beta"])
            self.assertEqual(written[0]["repository"], f"{ORIGIN}/{meta['full_name']}")
            self.assertTrue(written[0]["path"].startswith("codeberg-"))
            doc = json.loads((work / "reviews" / written[0]["path"]).read_text(encoding="utf-8"))
            self.assertEqual(doc["reviewed_commit"], paths["commit"])

    def test_main_reports_an_unsafe_codeberg_identity_and_still_writes_the_valid_review(self):
        meta, paths = self.cargo_repository()
        replay = self.replay(self.records)
        valid = f"{ORIGIN}/{meta['full_name']}"
        invalid = f"http://codeberg.org/{meta['full_name']}"
        with tempfile.TemporaryDirectory(prefix="forgejo-invalid-identity-fixture-") as tmp:
            work = Path(tmp)
            survivors = work / "survivors.json"
            survivors.write_text(json.dumps([
                {"layer_id": "alpha", "repository": invalid},
                {"layer_id": "beta", "repository": valid},
            ]), encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = self.module.main(["--survivors", str(survivors), "--out", str(work / "reviews"), "--lane", LANE])
            self.assertEqual(code, 1)
            self.assertIn(invalid, err.getvalue())
            written = json.loads(out.getvalue())
            self.assertEqual(len(written), 1)
            self.assertEqual((written[0]["repository"], written[0]["layers"]), (valid, ["beta"]))
            doc = json.loads((work / "reviews" / written[0]["path"]).read_text(encoding="utf-8"))
            self.assertEqual(doc["reviewed_commit"], paths["commit"])
            self.assertTrue(replay.calls)
            self.assertTrue(all(call["url"].startswith(API) for call in replay.calls))
            self.assertNotIn(invalid, [call["url"] for call in replay.calls])


class ForgejoIdentityTests(ForgejoCase):
    def test_codeberg_identity_deduplicates_layers_without_colliding_with_other_providers(self):
        self.assertEqual(self.module.codeberg_repo("https://codeberg.org/owner/project"), "owner/project")
        first = self.module.repository_key("https://codeberg.org/Owner/Project")
        self.assertEqual(first, "codeberg:owner/project")
        self.assertEqual(first, self.module.repository_key("https://codeberg.org/owner/project/"))
        self.assertNotEqual(first, self.module.repository_key("https://github.com/owner/project"))
        self.assertNotEqual(first, self.module.repository_key("https://huggingface.co/owner/project"))

    def test_other_hosts_are_not_codeberg_repositories(self):
        for value in ("https://github.com/owner/project", "https://gitlab.com/owner/project",
                      "https://codeberg.org.collector.invalid/owner/project", None):
            with self.subTest(repository=value):
                self.assertIsNone(self.module.codeberg_repo(value))

    def test_unsafe_or_malformed_codeberg_repository_urls_fail_before_any_request(self):
        replay = self.replay({})
        for value in ("https://user@codeberg.org/owner/project", "http://codeberg.org/owner/project",
                      "https://codeberg.org:8443/owner/project", "https://codeberg.org:invalid/owner/project",
                      "https://codeberg.org/owner", "https://codeberg.org/owner/project/tree/main",
                      "https://codeberg.org/owner/project?ref=main", "https://codeberg.org/owner/project#readme",
                      "https://codeberg.org/../project", "https://codeberg.org/owner/%2e%2e"):
            with self.subTest(repository=value):
                with self.assertRaises(self.module.CodebergError):
                    self.module.review(value, ["alpha"], LANE, FIT_MODELS)
        self.assertEqual(replay.calls, [])


class ForgejoProtocolTests(ForgejoCase):
    def test_anonymous_requests_use_native_opener_ignore_proxies_and_throttle(self):
        path = "repos/synthetic/protocol"
        url = API + path
        record = {"origin": "synthetic_protocol_case", "status": 200, "body": {"synthetic": "protocol"},
                  "headers": {"Content-Type": "application/json", "x-total-count": "1",
                              "Link": '<https://codeberg.org/api/v1/repos/synthetic/protocol?page=1>; rel="last"'}}
        replay = self.replay({url: record})
        proxy_env = {"https_proxy": "http://proxy.invalid:3128", "HTTPS_PROXY": "http://proxy.invalid:3128",
                     "CODEBERG_TOKEN": "synthetic-unused", "GITHUB_TOKEN": "synthetic-unused"}
        headers = {}
        with mock.patch.dict(os.environ, proxy_env):
            self.assertEqual(self.module.codeberg_get(path, response_headers=headers), record["body"])
            self.assertEqual(self.module.codeberg_get(url), record["body"])
        self.assertEqual(set(headers), {"Link", "x-total-count"})
        self.assertEqual(headers["x-total-count"], "1")
        self.assertEqual(len(replay.calls), 2)
        self.assertGreaterEqual(replay.calls[1]["at"] - replay.calls[0]["at"], 1.0)
        for call in replay.calls:
            self.assertEqual((call["url"], call["method"], call["timeout"]), (url, "GET", 60))
            self.assertEqual(call["headers"].get("Accept"), "application/json")
            self.assertTrue(call["headers"].get("User-agent"))
            self.assertFalse({name.lower() for name in call["headers"]} & {"authorization", "cookie"})

    def test_absolute_requests_outside_the_origin_or_api_fail_before_transport(self):
        replay = self.replay({})
        for target in self.protocol["redirect_cases"]["blocked_targets"] + [
                "https://codeberg.org/owner/project/raw/branch/main/README.md"]:
            with self.subTest(target=target):
                with self.assertRaises(self.module.CodebergError):
                    self.module.codeberg_get(target)
        self.assertEqual(replay.calls, [])

    def test_synthetic_http_errors_keep_status_and_do_not_retry(self):
        url = API + "repos/synthetic/protocol"
        for record in self.protocol["http_cases"]:
            with self.subTest(status=record["status"]):
                self.assertEqual(record["origin"], "synthetic_protocol_case")
                replay = self.replay({url: record})
                with self.assertRaises(self.module.CodebergError) as caught:
                    self.module.codeberg_get("repos/synthetic/protocol")
                self.assertEqual(caught.exception.status, record["status"])
                self.assertIn(str(record["status"]), str(caught.exception))
                if record["status"] == 429:
                    self.assertIn("retry-after", str(caught.exception).lower())
                    self.assertIn("30", str(caught.exception))
                self.assertEqual([call["url"] for call in replay.calls], [url])

    def test_synthetic_transport_and_json_errors_are_reported_without_retries(self):
        url = API + "repos/synthetic/protocol"
        cases = (
            ("connection", {"origin": "synthetic_protocol_case", "exception": urllib.error.URLError("synthetic")}),
            ("truncated", {"origin": "synthetic_protocol_case", "exception": http.client.IncompleteRead(b"{}")}),
            ("status_line", {"origin": "synthetic_protocol_case", "exception": http.client.BadStatusLine("synthetic")}),
            ("bad_json", {"origin": "synthetic_protocol_case", "status": 200, "body": b"synthetic invalid JSON"}),
        )
        for label, record in cases:
            with self.subTest(case=label):
                self.assertEqual(record["origin"], "synthetic_protocol_case")
                replay = self.replay({url: record})
                with self.assertRaises(self.module.CodebergError) as caught:
                    self.module.codeberg_get("repos/synthetic/protocol")
                self.assertIsNone(caught.exception.status)
                self.assertEqual(len(replay.calls), 1)

    def test_synthetic_body_bound_is_reported_as_an_error(self):
        url = API + "repos/synthetic/protocol"
        replay = self.replay({url: {"origin": "synthetic_protocol_case", "status": 200,
                                   "body": b" " * 129}})
        with mock.patch.object(self.module, "CODEBERG_MAX_BODY", 128), self.assertRaises(self.module.CodebergError):
            self.module.codeberg_get("repos/synthetic/protocol")
        self.assertEqual(len(replay.calls), 1)

    def test_synthetic_redirects_cannot_send_a_request_outside_the_codeberg_origin(self):
        url = API + "repos/synthetic/protocol"
        for status in self.protocol["redirect_cases"]["statuses"]:
            for target in self.protocol["redirect_cases"]["blocked_targets"]:
                with self.subTest(status=status, target=target):
                    record = {"origin": "synthetic_protocol_case", "status": status,
                              "headers": {"Location": target}, "body": b""}
                    replay = self.replay({url: record})
                    with self.assertRaises(self.module.CodebergError) as caught:
                        self.module.codeberg_get("repos/synthetic/protocol")
                    self.assertEqual([call["url"] for call in replay.calls], [url])

    def test_synthetic_same_origin_redirects_are_followed_and_throttled(self):
        url = API + "repos/synthetic/protocol"
        for target in self.protocol["redirect_cases"]["allowed_targets"]:
            with self.subTest(target=target):
                absolute = urllib.parse.urljoin(url, target)
                replay = self.replay({
                    url: {"origin": "synthetic_protocol_case", "status": 302,
                          "headers": {"Location": target}, "body": b""},
                    absolute: {"origin": "synthetic_protocol_case", "status": 200,
                               "body": {"synthetic": "same-origin redirect"}},
                })
                self.assertEqual(self.module.codeberg_get("repos/synthetic/protocol"),
                                 {"synthetic": "same-origin redirect"})
                self.assertEqual([call["url"] for call in replay.calls], [url, absolute])
                self.assertGreaterEqual(replay.calls[1]["at"] - replay.calls[0]["at"], 1.0)

    def test_synthetic_redirect_cycle_fails_without_an_unbounded_followup(self):
        url = API + "repos/synthetic/protocol"
        replay = self.replay({url: {"origin": "synthetic_protocol_case", "status": 302,
                                   "headers": {"Location": url}, "body": b""}})
        with self.assertRaises(self.module.CodebergError):
            self.module.codeberg_get("repos/synthetic/protocol")
        self.assertLessEqual(len(replay.calls), 5)

    def test_synthetic_final_response_url_cannot_escape_the_origin(self):
        url = API + "repos/synthetic/protocol"
        replay = self.replay({url: {"origin": "synthetic_protocol_case", "status": 200, "body": {},
                                   "final_url": "https://collector.invalid/api/v1/repos/synthetic/protocol"}})
        with self.assertRaises(self.module.CodebergError):
            self.module.codeberg_get("repos/synthetic/protocol")
        self.assertEqual([call["url"] for call in replay.calls], [url])


class ForgejoPaginationTests(ForgejoCase):
    def page(self, body, headers=None):
        return {"origin": "synthetic_protocol_case", "status": 200, "body": body, "headers": headers or {}}

    def test_link_next_survives_server_clamping_and_a_full_final_page(self):
        fixture = self.protocol["pagination_cases"]
        self.assertEqual(fixture["origin"], "synthetic_protocol_case")
        base = API + fixture["path"]
        final = base + "?page=2&limit=2"
        for requested_limit in (50, 2):
            with self.subTest(requested_limit=requested_limit):
                first = base + f"?page=1&limit={requested_limit}"
                relative_next = urllib.parse.urlsplit(final).path + "?page=2&limit=2"
                replay = self.replay({
                    first: self.page(fixture["first"], {"Link": f'<{relative_next}>; rel="next", <{final}>; rel="last"',
                                                        "x-total-count": "4"}),
                    final: self.page(fixture["second"], {"Link": f'<{first}>; rel="prev", <{final}>; rel="last"',
                                                         "x-total-count": "4"}),
                })
                rows = self.module.codeberg_pages(fixture["path"], limit=requested_limit)
                self.assertEqual(rows, fixture["first"] + fixture["second"])
                self.assertEqual([normalized_url(call["url"]) for call in replay.calls],
                                 [normalized_url(first), normalized_url(final)])

    def test_short_page_fallback_keeps_an_existing_query(self):
        fixture = self.protocol["pagination_cases"]
        path = fixture["path"] + "?filter=synthetic"
        first = API + path + "&page=1&limit=2"
        final = API + path + "&page=2&limit=2"
        replay = self.replay({first: self.page(fixture["first"]), final: self.page(fixture["short_final"])})
        self.assertEqual(self.module.codeberg_pages(path, limit=2), fixture["first"] + fixture["short_final"])
        self.assertEqual([normalized_url(call["url"]) for call in replay.calls],
                         [normalized_url(first), normalized_url(final)])

    def test_wrong_collection_shapes_are_fatal(self):
        fixture = self.protocol["pagination_cases"]
        url = API + fixture["path"] + "?page=1&limit=2"
        for body in fixture["wrong_shapes"]:
            with self.subTest(shape=type(body).__name__):
                replay = self.replay({url: self.page(body)})
                with self.assertRaises(self.module.CodebergError):
                    self.module.codeberg_pages(fixture["path"], limit=2)
                self.assertEqual(len(replay.calls), 1)

    def test_page_limit_and_cycles_fail_without_silent_truncation(self):
        fixture = self.protocol["pagination_cases"]
        first = API + fixture["path"] + "?page=1&limit=2"
        for label, headers in (("cycle", {"Link": f'<{first}>; rel="next"'}),
                               ("linked_bound", {"Link": f'<{first}&next=synthetic>; rel="next"'}),
                               ("unlinked_bound", {})):
            with self.subTest(case=label):
                replay = self.replay({first: self.page(fixture["first"], headers)})
                with self.assertRaises(self.module.CodebergError):
                    self.module.codeberg_pages(fixture["path"], limit=2, max_pages=2 if label == "cycle" else 1)
                self.assertEqual(len(replay.calls), 1)

    def test_unsafe_and_malformed_next_links_never_reach_transport(self):
        fixture = self.protocol["pagination_cases"]
        first = API + fixture["path"] + "?page=1&limit=2"
        targets = self.protocol["redirect_cases"]["blocked_targets"] + ["https://codeberg.org/synthetic/outside-api"]
        links = [f'<{target}>; rel="next"' for target in targets] + ['missing-angle-brackets; rel="next"']
        for link in links:
            with self.subTest(link=link):
                replay = self.replay({first: self.page(fixture["first"], {"Link": link})})
                with self.assertRaises(self.module.CodebergError):
                    self.module.codeberg_pages(fixture["path"], limit=2)
                self.assertEqual([call["url"] for call in replay.calls], [first])

    def test_invalid_pagination_arguments_fail_before_transport(self):
        replay = self.replay({})
        for limit, max_pages in ((0, 1), (51, 1), (2, 0)):
            with self.subTest(limit=limit, max_pages=max_pages):
                with self.assertRaises(ValueError):
                    self.module.codeberg_pages(self.protocol["pagination_cases"]["path"],
                                               limit=limit, max_pages=max_pages)
        self.assertEqual(replay.calls, [])


if __name__ == "__main__":
    unittest.main()
