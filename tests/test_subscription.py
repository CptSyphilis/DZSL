import unittest
from unittest.mock import Mock, patch

from dzsl.steam.api import SteamWorkshopAPI
from dzsl.ui.subscribe import (
    SteamSubscriptionManager,
    effective_progress,
    steam_progress_phase,
)


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
        self.assertEqual(
            steam_progress_phase(10, 100, 2, steam_state=8),
            "Steam is paused in Steam",
        )

    def test_subscription_uses_helper_subprocess(self):
        manager = SteamSubscriptionManager(
            lambda: {}, lambda: None, lambda _message: None,
            lambda: True, lambda **_kwargs: True, lambda: None,
        )
        with patch("dzsl.ui.subscribe.run_workshop_helper", return_value=(True, "")) as helper, \
             patch.object(manager, "forward_steam_uri", return_value=True) as forward:
            self.assertTrue(manager.subscribe_mod_steam("123", "Example"))

        helper.assert_called_once_with("download", ["123"])
        forward.assert_not_called()

    def test_subscribe_api_queues_download_after_subscribe(self):
        api = SteamWorkshopAPI()
        api.ugc = object()
        api.lib = Mock()
        api.lib.SteamAPI_ISteamUGC_SubscribeItem.return_value = 1
        api.lib.SteamAPI_ISteamUGC_DownloadItem.return_value = True
        api.lib.SteamAPI_ISteamUGC_SuspendDownloads.return_value = None

        self.assertTrue(api.queue_download("123", subscribe=True))
        api.lib.SteamAPI_ISteamUGC_SubscribeItem.assert_called_once()
        api.lib.SteamAPI_ISteamUGC_SuspendDownloads.assert_called_once_with(api.ugc, False)
        api.lib.SteamAPI_ISteamUGC_DownloadItem.assert_called_once_with(api.ugc, 123, True)

    def test_failed_helper_subprocess_reports_failure(self):
        manager = SteamSubscriptionManager(
            lambda: {}, lambda: None, lambda _message: None,
            lambda: True, lambda **_kwargs: True, lambda: None,
        )
        with patch("dzsl.ui.subscribe.run_workshop_helper", return_value=(False, "Steam rejected the request")) as helper, \
             patch.object(manager, "forward_steam_uri", return_value=True) as forward:
            self.assertFalse(manager.subscribe_mod_steam("123", "Example"))

        helper.assert_called_once_with("download", ["123"])
        forward.assert_not_called()

    def test_suspend_downloads_calls_steamworks_pause(self):
        api = SteamWorkshopAPI()
        api.ugc = object()
        api.lib = Mock()
        api.lib.SteamAPI_ISteamUGC_SuspendDownloads.return_value = None

        self.assertTrue(api.suspend_downloads(True))
        api.lib.SteamAPI_ISteamUGC_SuspendDownloads.assert_called_once_with(api.ugc, True)

    def test_wait_does_not_fail_after_one_hour(self):
        manager = SteamSubscriptionManager(
            lambda: {}, lambda: None, lambda _message: None,
            lambda: True, lambda **_kwargs: True, lambda: None,
        )
        progress = Mock()
        progress.is_cancelled.side_effect = [False] * 1800 + [True]

        with patch("dzsl.ui.subscribe.mod_subscribed", return_value=True), \
            patch("dzsl.ui.subscribe.mod_installed", return_value=False), \
             patch.object(manager, "steam_item_status", return_value=(0, (0, 0))), \
             patch("dzsl.ui.subscribe.mod_download_progress", return_value=(0, 0)), \
             patch("dzsl.ui.subscribe.mod_staging_signature", return_value=(0, 0)), \
             patch("dzsl.ui.subscribe.time.sleep"), \
            patch("dzsl.ui.subscribe.time.time", side_effect=range(0, 10000, 2)):
            self.assertFalse(manager.wait_for_mod_installed("123", progress, "Large mod"))

        self.assertEqual(progress.is_cancelled.call_count, 1801)

    def test_wait_marks_steam_pause_state_as_paused(self):
        manager = SteamSubscriptionManager(
            lambda: {}, lambda: None, lambda _message: None,
            lambda: True, lambda **_kwargs: True, lambda: None,
        )
        progress = Mock()
        progress.is_cancelled.side_effect = [False, False, True]

        with patch("dzsl.ui.subscribe.mod_subscribed", return_value=True), \
             patch("dzsl.ui.subscribe.mod_installed", return_value=False), \
             patch.object(manager, "steam_item_status", return_value=(8, (0, 0))), \
             patch("dzsl.ui.subscribe.mod_download_progress", return_value=(0, 0)), \
             patch("dzsl.ui.subscribe.mod_staging_signature", return_value=(0, 0)), \
             patch("dzsl.ui.subscribe.time.sleep"), \
             patch("dzsl.ui.subscribe.time.time", side_effect=range(0, 100, 2)):
            self.assertFalse(manager.wait_for_mod_installed("123", progress, "Paused mod"))

        progress.set_mod_status.assert_any_call("123", "Paused in Steam", "active")
        progress.set_action_prompt.assert_any_call("Paused in Steam: Paused mod")


if __name__ == "__main__":
    unittest.main()
