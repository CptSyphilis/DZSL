import unittest

from dzsl.paths import ASSETS_DIR, PACKAGE_DIR, asset_path


class ProjectPathTests(unittest.TestCase):
    def test_packaged_assets_exist(self):
        self.assertTrue(asset_path("icon.png").is_file())
        self.assertTrue(asset_path("dzsl-bg.png").is_file())

    def test_assets_are_inside_package(self):
        self.assertEqual(ASSETS_DIR, PACKAGE_DIR / "assets")


if __name__ == "__main__":
    unittest.main()
