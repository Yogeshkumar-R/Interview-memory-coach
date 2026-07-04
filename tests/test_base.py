import importlib
import os
import unittest

from agents import base


class BaseClientTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("GROQ_API_KEY", None)

    def test_import_without_api_key_does_not_crash(self):
        module = importlib.reload(base)
        self.assertIsNotNone(module)
        self.assertIsNone(module.client)

    def test_chat_without_api_key_returns_fallback(self):
        module = importlib.reload(base)
        response = module.chat([], system="")
        self.assertIn("API key", response)


if __name__ == "__main__":
    unittest.main()
