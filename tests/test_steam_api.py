import os
import unittest
from unittest.mock import patch

from steam_api import SteamWorkshopAPI


class _FakeSteamLibrary:
    def __init__(self):
        self.shutdown_calls = 0

    def SteamAPI_Shutdown(self):
        self.shutdown_calls += 1


class SteamWorkshopAPITests(unittest.TestCase):
    def test_close_restores_missing_app_environment(self):
        api = SteamWorkshopAPI()
        lib = _FakeSteamLibrary()
        with patch.dict(os.environ, {}, clear=True):
            api._set_app_environment()
            api.lib = lib
            api.ugc = object()

            api.close()

            self.assertNotIn("SteamAppId", os.environ)
            self.assertNotIn("SteamGameId", os.environ)
            self.assertEqual(lib.shutdown_calls, 1)

    def test_close_restores_existing_app_environment(self):
        api = SteamWorkshopAPI()
        original = {"SteamAppId": "480", "SteamGameId": "480"}
        with patch.dict(os.environ, original, clear=True):
            api._set_app_environment()

            api.close()

            self.assertEqual(os.environ["SteamAppId"], "480")
            self.assertEqual(os.environ["SteamGameId"], "480")


if __name__ == "__main__":
    unittest.main()
