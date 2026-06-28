import os
import tempfile
import unittest

from dayz_runtime import ModSetupError, mod_link_name, setup_mod_links


class DayZRuntimeTests(unittest.TestCase):
    def test_workshop_id_encoding_matches_existing_launcher(self):
        self.assertEqual(mod_link_name("3748338087"), "@pxlr3w")
        self.assertEqual(mod_link_name("1559212036"), "@BLDvXA")

    def test_setup_validates_and_creates_relative_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = os.path.join(tmp, "steamapps", "common", "DayZ")
            workshop = os.path.join(tmp, "workshop")
            mod = os.path.join(workshop, "123")
            os.makedirs(game)
            os.makedirs(os.path.join(mod, "Addons"))
            with open(os.path.join(mod, "meta.cpp"), "w", encoding="utf-8") as handle:
                handle.write("name = test;")
            with open(os.path.join(mod, "Addons", "test.pbo"), "wb") as handle:
                handle.write(b"payload")
            cfg = {"steam_root": tmp, "mods_dir": workshop}

            links = setup_mod_links(cfg, ["123", "123"])

            self.assertEqual(links, [mod_link_name("123")])
            link = os.path.join(game, links[0])
            self.assertTrue(os.path.islink(link))
            self.assertEqual(os.path.realpath(link), mod)

    def test_setup_rejects_incomplete_mod(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = os.path.join(tmp, "steamapps", "common", "DayZ")
            workshop = os.path.join(tmp, "workshop")
            os.makedirs(game)
            os.makedirs(os.path.join(workshop, "123"))
            cfg = {"steam_root": tmp, "mods_dir": workshop}

            with self.assertRaises(ModSetupError):
                setup_mod_links(cfg, ["123"])


if __name__ == "__main__":
    unittest.main()
