import unittest
from unittest.mock import patch

from dzsl.core.config import mod_installed
from dzsl.ui.subscribe import SteamSubscriptionManager


class SteamDownloadStateTests(unittest.TestCase):
    @patch("dzsl.core.config.validate_mod_folder", return_value=(True, ""))
    @patch("dzsl.core.config.item_record")
    @patch("dzsl.core.config.item_download_progress", return_value=(25, 100))
    @patch("dzsl.core.config.workshop_acf_paths", return_value=["manifest.acf"])
    def test_partial_download_is_not_installed(
        self,
        _manifest_paths,
        _download_progress,
        item_record,
        _validate,
    ):
        self.assertFalse(mod_installed({}, "123"))
        item_record.assert_not_called()

    @patch("dzsl.ui.subscribe.is_flatpak", return_value=False)
    @patch("dzsl.ui.subscribe.subprocess.run")
    @patch("dzsl.ui.subscribe.forward_steam_uri", return_value=True)
    def test_native_subscribe_helper_exits_before_polling(self, forward_uri, run, _flatpak):
        run.return_value.returncode = 0
        manager = SteamSubscriptionManager(
            lambda: {},
            lambda: None,
            lambda _message: None,
            lambda: True,
            lambda **_kwargs: True,
            lambda: None,
        )
        self.assertTrue(manager.subscribe_mod_steam("123", "Test Mod"))
        run.assert_called_once()
        forward_uri.assert_not_called()

    @patch("dzsl.ui.subscribe.is_flatpak", return_value=True)
    @patch("dzsl.ui.subscribe.forward_steam_uri", return_value=True)
    def test_flatpak_subscribe_uses_uri(self, forward_uri, _flatpak):
        manager = SteamSubscriptionManager(
            lambda: {}, lambda: None, lambda _message: None,
            lambda: True, lambda **_kwargs: True, lambda: None,
        )
        self.assertTrue(manager.subscribe_mod_steam("123", "Test Mod"))
        forward_uri.assert_called_once_with("steam://installworkshop/221100/123")


if __name__ == "__main__":
    unittest.main()
