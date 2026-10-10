"""Publication privacy applies to Architecture text before HTML/JSON encoding."""
import base64
import copy
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("architecture_privacy_view", ROOT / "tools/local-pages/architecture_view.py")
VIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VIEW)
PAGES_SPEC = importlib.util.spec_from_file_location("architecture_privacy_pages", ROOT / "tools/local-pages/build_pages.py")
PAGES = importlib.util.module_from_spec(PAGES_SPEC)
PAGES_SPEC.loader.exec_module(PAGES)


class PublishedDOM(HTMLParser):
    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.tags, self.values = [], []
        self.feed(markup)
    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.values.extend(value for _, value in attrs if value is not None)
    def handle_data(self, data):
        self.values.append(data)


class ArchitecturePrivacyTests(unittest.TestCase):
    def fixture(self, private):
        tool = {"name": "fixture-tool", "repository": "https://github.com/upstream/tool", "pin": "a" * 40,
                "reason": private, "quality_evidence": {private: [private]}, "primary_sources": [private],
                "invoke": {"status": "unmeasured", "reason": private},
                "e2e": {"path": private, "sha256": "b" * 64, "kind": "native_cli_e2e", "verified": False, "reason": private, "command": private}}
        layer = {"key": "foundation:fixture", "catalog": "foundation", "layer_id": "fixture", "title": private,
                 "current_choice": private, "rationale": private, "checked_at": "2026-10-09T20:00:00Z",
                 "candidates": [tool], "winners": [tool], "alternatives": [tool], "rejected": [tool],
                 "g5_candidates": [tool], "source_quality": [{private: private}], "source_refs": [private]}
        model = {"layers": [layer], "adoption_observation": {"generated_utc": "2026-10-09T20:00:00Z", "sha256": "c" * 64},
                 "design": {"path": private, "source": private, "ref": "d" * 40},
                 "sources": [{"path": private, "sha256": "e" * 64}],
                 "host_receipts": {"items": [{"title": private, "path": private, "sha256": "f" * 64}], "sources": [{"path": private}]},
                 "adoption_program": {"global_stages": [private]}}
        inventory = {"items": [{"kind": "skill", "name": private, "path": private, "layer_keys": ["foundation/fixture"], "mapping_source": private, "sha256": "1" * 64},
                               {"kind": "skill-directory", "name": private, "path": private, "status": "UNAPPROVED", "unmapped_reason": private}],
                     "sources": [{"path": private, "sha256": "2" * 64}],
                     "coverage": {"client_hook_wiring": private, "cron_status": private, "automation_limits": [private]}}
        return model, inventory

    def test_main_and_all_published_detail_dom_project_private_values_without_mutating_sources(self):
        home = Path('/home') / 'synthetic-person'
        private_path = str(home / 'code/input.json')
        encoded = [quote(private_path, safe=''), private_path.encode().hex(), base64.b64encode(private_path.encode()).decode(), ''.join('\\u' + format(ord(char), '04x') for char in private_path)]
        private = ' '.join([private_path, str(Path('/Users') / 'synthetic-person' / 'source.md'), 'worker_synthetic-person_read', 'https://chatgpt.com/c/synthetic-account', *encoded])
        model, inventory = self.fixture(private)
        original_model, original_inventory = copy.deepcopy(model), copy.deepcopy(inventory)
        outputs = {}
        with patch.object(Path, 'home', return_value=home):
            body, receipt = VIEW.render(model, inventory, detail_outputs=outputs)
            documents = {'architecture.html': PAGES.document('architecture', 'Architecture', 'Fixture', 'Synthetic', body, '2026-10-09T20:00:00Z', '3' * 64, [])}
            for name, content in outputs.items():
                detail = '<div id="architecture-detail-content">' + content.decode() + '</div>'
                documents[name] = PAGES.document('architecture', 'Architecture detail', 'Fixture', 'Synthetic', detail, '2026-10-09T20:00:00Z', '3' * 64, [])
        with tempfile.TemporaryDirectory() as temporary:
            for name, raw in documents.items():
                path = Path(temporary) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                dom = PublishedDOM(path.read_text())
                values = '\n'.join(dom.values)
                self.assertNotIn('synthetic-person', values)
                self.assertNotIn('/home/', values)
                self.assertNotIn('/Users/', values)
                self.assertNotIn('https://chatgpt.com/', values)
                for token in encoded:
                    self.assertNotIn(token, values)
                self.assertIn('html', dom.tags)
                self.assertIn('link', dom.tags)
                self.assertIn('main', dom.tags)
        self.assertGreaterEqual(len(outputs), 3)
        self.assertEqual(receipt['rendered_layer_count'], 1)
        self.assertEqual(model, original_model)
        self.assertEqual(inventory, original_inventory)
        self.assertIn('b' * 64, b''.join(outputs.values()).decode())
        self.assertIn('a' * 40, b''.join(outputs.values()).decode())

    def test_nested_json_values_and_keys_are_projected_before_serialization(self):
        home = Path('/home') / 'synthetic-person'
        data = {str(home / 'private-key'): {'path': str(home / 'private-input'), 'account': 'https://claude.ai/artifact/private-item', 'pin': 'a' * 40},
                'items': [base64.b64encode(str(home / 'encoded-input').encode()).decode(), 0, None]}
        original = copy.deepcopy(data)
        with patch.object(Path, 'home', return_value=home):
            raw = VIEW.value(data)
        self.assertNotIn('synthetic-person', raw)
        self.assertNotIn('/home/', raw)
        self.assertNotIn('https://claude.ai/artifact/', raw)
        projected = json.loads(raw)
        self.assertIn('${USER_HOME}/private-key', projected)
        self.assertEqual(projected['${USER_HOME}/private-key']['pin'], 'a' * 40)
        self.assertEqual(projected['items'][1:], [0, None])
        self.assertEqual(data, original)

    def test_private_layer_identifiers_are_projected_in_attributes_and_detail_filenames(self):
        model, inventory = self.fixture('Safe source text')
        layer = model['layers'][0]
        layer.update(key='foundation:synthetic-person', catalog='synthetic-person', layer_id='synthetic-person-fixture')
        inventory['items'][0]['layer_keys'] = ['foundation:synthetic-person']
        outputs = {}
        with patch.object(Path, 'home', return_value=Path('/home') / 'synthetic-person'):
            body, _ = VIEW.render(model, inventory, detail_outputs=outputs)
        dom = PublishedDOM(body + b''.join(outputs.values()).decode())
        self.assertNotIn('synthetic-person', '\n'.join(dom.values))
        self.assertNotIn('synthetic-person', '\n'.join(outputs))
        self.assertIn('section', dom.tags)
        self.assertIn('details', dom.tags)
        self.assertIn('table', dom.tags)

    def test_short_home_names_and_private_labels_preserve_html_structure(self):
        home = Path('/home') / 'li'
        with patch.object(Path, 'home', return_value=home):
            model, inventory = self.fixture(str(home / 'input.json') + ' <script>bad()</script>')
            body, _ = VIEW.render(model, inventory)
            markup = PAGES.document('architecture', 'Architecture', 'Fixture', 'Synthetic', body, '2026-10-09T20:00:00Z', '4' * 64, []).decode()
        dom = PublishedDOM(markup)
        self.assertIn('link', dom.tags)
        self.assertIn('li', dom.tags)
        self.assertIn('table', dom.tags)
        self.assertEqual(dom.tags.count('script'), 1)
        self.assertNotIn(str(home) + '/', '\n'.join(dom.values))
        self.assertIn('&lt;script&gt;bad()', markup)


if __name__ == '__main__':
    unittest.main()
