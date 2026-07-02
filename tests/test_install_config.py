import json
import os
import tempfile
import unittest

from dzsl.core.install_config import merge_install_config, update_install_config


class InstallConfigTests(unittest.TestCase):
    def test_upgrade_preserves_existing_steam_and_user_settings(self):
        result = merge_install_config(
            {
                "steam_root": "/games/custom-steam",
                "profile_name": "Survivor",
                "window_mode": True,
                "launcher_path": "/obsolete/launcher",
            },
            "/auto/detected-steam",
        )

        self.assertEqual(result["steam_root"], "/games/custom-steam")
        self.assertEqual(result["profile_name"], "Survivor")
        self.assertTrue(result["window_mode"])
        self.assertNotIn("launcher_path", result)

    def test_clean_install_uses_detected_steam_root(self):
        self.assertEqual(
            merge_install_config({}, "/auto/detected-steam")["steam_root"],
            "/auto/detected-steam",
        )

    def test_update_writes_private_atomic_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"steam_root": "/existing", "extra_args": "-window"}, handle)

            result = update_install_config(path, "/detected")

            with open(path, encoding="utf-8") as handle:
                written = json.load(handle)
            self.assertEqual(written, result)
            self.assertEqual(written["steam_root"], "/existing")
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
