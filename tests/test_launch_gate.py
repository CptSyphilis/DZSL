import unittest

from dzsl.services.launch_gate import launch_block_reason


class LaunchGateTests(unittest.TestCase):
    def test_blocks_when_steam_is_not_ready(self):
        reason = launch_block_reason({}, [], ready_check=lambda: False)
        self.assertEqual(reason, "Steam is not ready")

    def test_blocks_incomplete_mod(self):
        reason = launch_block_reason(
            {},
            ["123"],
            ready_check=lambda: True,
            subscribed_check=lambda cfg, mid: True,
            installed_check=lambda cfg, mid: False,
        )
        self.assertIn("not fully downloaded", reason)

    def test_allows_complete_mods(self):
        reason = launch_block_reason(
            {},
            ["123", "456"],
            ready_check=lambda: True,
            subscribed_check=lambda cfg, mid: True,
            installed_check=lambda cfg, mid: True,
        )
        self.assertEqual(reason, "")
