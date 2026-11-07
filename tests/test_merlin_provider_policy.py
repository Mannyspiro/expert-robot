import unittest

from merlin.app import _select_chat_provider


class ChatProviderPolicyTests(unittest.TestCase):
    def test_auto_is_local_even_when_cloud_is_configured(self):
        # Provider selection is independent of remote endpoint configuration.
        self.assertEqual(_select_chat_provider("auto"), "local")

    def test_local_is_local(self):
        self.assertEqual(_select_chat_provider("local"), "local")

    def test_cloud_requires_explicit_selection(self):
        self.assertEqual(_select_chat_provider("cloud"), "cloud")

    def test_unknown_provider_is_rejected(self):
        with self.assertRaises(ValueError):
            _select_chat_provider("fallback")


if __name__ == "__main__":
    unittest.main()
