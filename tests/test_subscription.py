import unittest
from unittest.mock import Mock, patch

from dzsl.steam.api import SteamWorkshopAPI
from dzsl.ui.subscribe import SteamSubscriptionManager, steam_progress_phase


class SubscriptionTests(unittest.TestCase):
    def test_steam_progress_phase_tracks_manifest_state(self):
        self.assertEqual(steam_progress_phase(0, 0, 0), "Waiting for Steam progress")
        self.assertEqual(steam_progress_phase(10, 100, 2), "Steam is staging download")
        self.assertEqual(
            steam_progress_phase(10, 100, 10, manifest_delayed=True),
            "Steam is downloading (live progress in Steam)",
        )
        self.assertEqual(steam_progress_phase(10, 100, 30), "Steam is paused or waiting")
        self.assertEqual(
            steam_progress_phase(10, 100, 30, manifest_delayed=True),
            "Steam is paused or waiting",
        )
        self.assertEqual(steam_progress_phase(100, 100, 2), "Steam is installing files")

    def test_install_uri_does_not_initialize_dayz_steam_api(self):
        manager = SteamSubscriptionManager(
            lambda: {}, lambda: None, lambda _message: None,
            lambda: True, lambda **_kwargs: True, lambda: None,
        )
        with patch("dzsl.ui.subscribe.subprocess.run") as run, \
             patch.object(manager, "forward_steam_uri", return_value=True) as forward:
            self.assertTrue(manager.subscribe_mod_steam("123", "Example"))

        run.assert_not_called()
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
             patch("dzsl.ui.subscribe.mod_staging_signature", return_value=(0, 0)), \
             patch("dzsl.ui.subscribe.time.sleep"), \
             patch("dzsl.ui.subscribe.time.time", side_effect=range(0, 10000, 2)):
            self.assertFalse(manager.wait_for_mod_installed("123", progress, "Large mod"))

        self.assertEqual(progress.is_cancelled.call_count, 1801)


if __name__ == "__main__":
    unittest.main()
