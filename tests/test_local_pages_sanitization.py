"""One sanitizer preserves the native portable recipe and omits account URLs."""

import ast
import importlib.util
from pathlib import Path
import re
from typing import Any
import unittest


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_HOME = "/".join(["", "home", "synthetic-user"])
SYNTHETIC_MAC_HOME = "/".join(["", "Users", "synthetic-user"])
SYNTHETIC_SESSION = "-".join(["01234567", "89ab", "cdef", "0123", "456789abcdef"])
SYNTHETIC_TASK = "-".join(["task", "abcd1234", "ef5678"])


def load_helper():
    spec = importlib.util.spec_from_file_location("local_pages_sanitization_tests", ROOT / "tools/local-pages/sanitization.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SanitizationTests(unittest.TestCase):
    def test_native_reference_recipe_remains_exact_without_loading_reader(self):
        syntax = ast.parse((ROOT / "tools/north-star/build_readiness.py").read_text())
        render = next(node for node in syntax.body if isinstance(node, ast.FunctionDef) and node.name == "render")
        portable = next(node for node in render.body if isinstance(node, ast.FunctionDef) and node.name == "portable")
        namespace = {"Any": Any, "re": re}
        exec(compile(ast.Module(body=[portable], type_ignores=[]), "native portable reference", "exec"), namespace)
        home_text = SYNTHETIC_HOME + "/code/project " + SYNTHETIC_MAC_HOME + "/notes"
        data = {"home": home_text, "identities": ["before " + SYNTHETIC_SESSION + " after", SYNTHETIC_TASK.upper(), 5, False, None], "nested": {"value": SYNTHETIC_HOME + "/private/" + SYNTHETIC_TASK}}
        self.assertEqual(load_helper().sanitize(data), namespace["portable"](data))
        self.assertEqual(data["home"], home_text)

    def test_account_artifact_filter_applies_recursively(self):
        helper = load_helper()
        values = {"links": ["See https://claude.ai/artifact/private-item", "https://chatgpt.com/c/private-item", "https://chat.openai.com/c/private-item"], "keep": "https://example.org/public"}
        result = helper.sanitize(values)
        self.assertTrue(all(value.endswith("[account artifact omitted]") for value in result["links"]))
        self.assertEqual(result["keep"], values["keep"])

    def test_url_classification_uses_supported_url_parser(self):
        helper = load_helper()
        for value in ["https://claude.ai/artifact/id", "HTTPS://CHATGPT.COM/c/id", "https://chat.openai.com/c/id", "https://chatgpt.com", "https://%63hatgpt.com/c/id"]:
            with self.subTest(value=value):
                self.assertTrue(helper.is_account_url(value))
        for value in ["https://platform.openai.com/docs", "https://example.org/chatgpt.com/c/id", "https://chatgpt.com.example.org/c/id", None]:
            with self.subTest(value=value):
                self.assertFalse(helper.is_account_url(value))

    def test_text_normalizes_scalars_and_keeps_native_placeholders(self):
        helper = load_helper()
        self.assertEqual(helper.text(None), "Unspecified in source")
        self.assertEqual(helper.text(4), "4")
        self.assertEqual(helper.text(SYNTHETIC_HOME + "/project"), "${USER_HOME}/project")
        self.assertEqual(helper.text(SYNTHETIC_SESSION), "${LOCAL_SESSION_ID}")
        self.assertEqual(helper.text(SYNTHETIC_TASK), "${LOCAL_TASK_HANDLE}")

    def test_sanitization_is_idempotent_for_rendered_source_values(self):
        helper = load_helper()
        source = {"path": SYNTHETIC_HOME + "/research", "account": "https://chatgpt.com/c/private-id", "task": SYNTHETIC_TASK, "number": 1}
        first = helper.sanitize(source)
        self.assertEqual(helper.sanitize(first), first)

    def test_text_projects_keys_and_other_stringified_container_values(self):
        rendered = load_helper().text({SYNTHETIC_HOME + "/key": (SYNTHETIC_MAC_HOME + "/value", SYNTHETIC_TASK)})
        self.assertNotIn(SYNTHETIC_HOME, rendered)
        self.assertNotIn(SYNTHETIC_MAC_HOME, rendered)
        self.assertNotIn(SYNTHETIC_TASK, rendered)


if __name__ == "__main__":
    unittest.main()
