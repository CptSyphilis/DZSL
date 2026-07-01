import subprocess
import unittest
from unittest.mock import Mock, patch

from dzsl.steam.api import SteamWorkshopAPI
from dzsl.ui.subscribe import SteamSubscriptionManager


class SubscriptionTests(unittest.TestCase):
    def test_native_helper_subscribes_before_install_uri(self):
        manager = SteamSubscriptionManager(
            lambda: {}, lambda: None, lambda _message: None,
            lambda: True, lambda **_kwargs: True, lambda: None,
        )
        result = subprocess.CompletedProcess([], 0, "", "")

        with patch("dzsl.ui.subscribe.is_flatpak", return_value=False), \
             patch("dzsl.ui.subscribe.subprocess.run", return_value=result) as run, \
             patch.object(manager, "forward_steam_uri", return_value=True) as forward:
            self.assertTrue(manager.subscribe_mod_steam("123", "Example"))

        self.assertIn("subscribe", run.call_args.args[0])
        forward.assert_called_once_with("steam://installworkshop/221100/123")

    def test_subscribe_api_does_not_request_download_while_initialized(self):
        api = SteamWorkshopAPI()
        api.ugc = object()
        api.lib = Mock()
        api.lib.SteamAPI_ISteamUGC_SubscribeItem.return_value = 1

        self.assertTrue(api.subscribe("123"))
        api.lib.SteamAPI_ISteamUGC_SubscribeItem.assert_called_once()
        api.lib.SteamAPI_ISteamUGC_DownloadItem.assert_not_called()

    def test_wait_does_not_fail_after_one_hour(self):
        manager = SteamSubscriptionManager(
            lambda: {}, lambda: None, lambda _message: None,
            lambda: True, lambda **_kwargs: True, lambda: None,
        )
        progress = Mock()
        progress.is_cancelled.side_effect = [False] * 1800 + [True]

        with patch("dzsl.ui.subscribe.mod_subscribed", return_value=True), \
             patch("dzsl.ui.subscribe.mod_installed", return_value=False), \
             patch("dzsl.ui.subscribe.mod_download_progress", return_value=(0, 0)), \
             patch("dzsl.ui.subscribe.time.sleep"), \
             patch("dzsl.ui.subscribe.time.time", side_effect=range(0, 10000, 2)):
            self.assertFalse(manager.wait_for_mod_installed("123", progress, "Large mod"))

        self.assertEqual(progress.is_cancelled.call_count, 1801)


if __name__ == "__main__":
    unittest.main()
