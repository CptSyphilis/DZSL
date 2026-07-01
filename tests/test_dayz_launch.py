import unittest
from unittest.mock import patch
from urllib.parse import unquote

from dzsl.services.dayz import build_launch_command, build_launch_uri


class DayZLaunchTests(unittest.TestCase):
    def setUp(self):
        self.server = "203.0.113.10:2302"
        self.mods = ["@first", "@second"]
        self.profile = "Survivor Name"
        self.params = ["-password=secret value", "-nosplash", "-noPause"]

    def assert_client_uri(self, uri):
        prefix = "steam://run/221100//"
        self.assertTrue(uri.startswith(prefix), uri)
        encoded = uri[len(prefix):-1]
        arguments = unquote(encoded)
        self.assertIn("-mod=@first;@second", arguments)
        self.assertIn("-connect=203.0.113.10:2302", arguments)
        self.assertIn("-nolauncher", arguments)
        self.assertIn("-world=empty", arguments)
        self.assertIn('"-name=Survivor Name"', arguments)
        self.assertIn('"-password=secret value"', arguments)
        self.assertIn("-nosplash", arguments)
        self.assertIn("-noPause", arguments)

    def test_flatpak_uri_preserves_client_arguments(self):
        uri = build_launch_uri(self.server, self.mods, self.profile, self.params)
        self.assert_client_uri(uri)

    def test_native_command_uses_applaunch_without_external_uri(self):
        with patch("dzsl.services.dayz.steam_launch_prefix", return_value=["/usr/bin/steam"]):
            command = build_launch_command(self.server, self.mods, self.profile, self.params)

        self.assertEqual(command, [
            "/usr/bin/steam", "-applaunch", "221100",
            "-mod=@first;@second", "-connect=203.0.113.10:2302",
            "-nolauncher", "-world=empty", "-name=Survivor Name",
            "-password=secret value", "-nosplash", "-noPause",
        ])


if __name__ == "__main__":
    unittest.main()
