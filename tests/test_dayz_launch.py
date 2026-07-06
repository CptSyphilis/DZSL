import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote

from dzsl.services.dayz import (
    ModSetupError,
    build_launch_command,
    build_launch_uri,
    mod_link_name,
    setup_mod_links,
)


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


class ModLinkGuardTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.game_dir = os.path.join(self.root, "game")
        self.workshop = os.path.join(self.root, "workshop")
        os.makedirs(self.game_dir)
        os.makedirs(self.workshop)
        self.cfg = {"steam_root": self.root, "mods_dir": self.workshop}

    def make_mod(self, mod_id, pbo_bytes=b"payload"):
        addons = os.path.join(self.workshop, str(mod_id), "addons")
        os.makedirs(addons)
        with open(os.path.join(addons, "core.pbo"), "wb") as fh:
            fh.write(pbo_bytes)

    def run_setup(self, mod_ids):
        with patch("dzsl.services.dayz.dayz_dir", return_value=self.game_dir):
            return setup_mod_links(self.cfg, mod_ids)

    def test_valid_mod_gets_resolvable_link(self):
        self.make_mod(123)
        links = self.run_setup(["123"])
        self.assertEqual(links, [mod_link_name("123")])
        link_path = os.path.join(self.game_dir, links[0])
        self.assertTrue(os.path.islink(link_path))
        self.assertTrue(os.path.isfile(os.path.join(link_path, "addons", "core.pbo")))

    def test_link_not_reaching_content_is_refused(self):
        self.make_mod(123)
        source = os.path.join(self.workshop, "123")

        def by_path(path):
            return (True, "") if path == source else (False, "no PBO payload files were found")

        with patch("dzsl.services.dayz.validate_mod_folder", side_effect=by_path):
            with self.assertRaisesRegex(ModSetupError, "does not reach usable mod content"):
                self.run_setup(["123"])

    def test_stale_link_is_repointed_and_validated(self):
        self.make_mod(123)
        link_path = os.path.join(self.game_dir, mod_link_name("123"))
        os.symlink("../nowhere", link_path)
        links = self.run_setup(["123"])
        self.assertEqual(links, [mod_link_name("123")])
        self.assertTrue(os.path.isfile(os.path.join(link_path, "addons", "core.pbo")))

    def test_missing_mod_points_at_custom_folder_setting(self):
        steam_content = os.path.join(
            self.root, "steamapps", "workshop", "content", "221100", "123", "addons"
        )
        os.makedirs(steam_content)
        with open(os.path.join(steam_content, "core.pbo"), "wb") as fh:
            fh.write(b"payload")
        with self.assertRaisesRegex(ModSetupError, "Custom Mods Folder"):
            self.run_setup(["123"])

    def test_missing_mod_without_steam_copy_keeps_plain_error(self):
        with self.assertRaisesRegex(ModSetupError, "^Missing Workshop mod 123$"):
            self.run_setup(["123"])


if __name__ == "__main__":
    unittest.main()
