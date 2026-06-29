import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote

from dzsl.core.environment import load_environment
from dzsl.http import RequestError, get_json
from dzsl.runtime import is_flatpak
from dzsl.services.dayz import build_launch_uri


class FlatpakRuntimeTests(unittest.TestCase):
    def test_detects_flatpak_environment(self):
        with patch.dict(os.environ, {"FLATPAK_ID": "com.dayzlinux.dzsl"}):
            self.assertTrue(is_flatpak())

    def test_builds_encoded_steam_launch_uri(self):
        uri = build_launch_uri(
            "203.0.113.10:2302",
            ["@example"],
            "Survivor Name",
            ["-nosplash"],
        )
        self.assertTrue(uri.startswith("steam://run/221100//"))
        arguments = unquote(uri.split("//", 2)[2][:-1])
        self.assertIn("-connect=203.0.113.10:2302", arguments)
        self.assertIn("-mod=@example", arguments)
        self.assertIn("Survivor Name", arguments)

    def test_environment_file_does_not_override_process(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("DZSL_TEST_VALUE=file\n", encoding="utf-8")
            with patch.dict(os.environ, {"DZSL_TEST_VALUE": "process"}):
                load_environment(path)
                self.assertEqual(os.environ["DZSL_TEST_VALUE"], "process")

    def test_http_client_rejects_non_https_urls(self):
        with self.assertRaises(RequestError):
            get_json("file:///etc/passwd")


if __name__ == "__main__":
    unittest.main()
