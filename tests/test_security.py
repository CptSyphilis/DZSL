import json
import os
import stat
import tempfile
import unittest

from dzsl.core.config import save_json
from dzsl.core.uri import validate_host_port
from dzsl.services.server_api import ServerAPIError, _https_url
from dzsl.steam.web_api import _workshop_ids
from dzsl.ui.helpers import forward_steam_uri


class InputValidationTests(unittest.TestCase):
    def test_accepts_valid_server(self):
        self.assertEqual(validate_host_port("dayz.example.net", "2302"), ("dayz.example.net", 2302))

    def test_rejects_host_path_injection(self):
        with self.assertRaises(ValueError):
            validate_host_port("example.net/../../admin", 2302)

    def test_rejects_invalid_port(self):
        with self.assertRaises(ValueError):
            validate_host_port("example.net", "2302/path")

    def test_rejects_non_https_api_url(self):
        with self.assertRaises(ServerAPIError):
            _https_url("http://example.net/servers")

    def test_rejects_api_url_credentials(self):
        with self.assertRaises(ServerAPIError):
            _https_url("https://user:password@example.net/servers")

    def test_rejects_workshop_path_injection(self):
        with self.assertRaises(ValueError):
            _workshop_ids(["../../important"])

    def test_rejects_non_steam_forwarding_uri(self):
        self.assertFalse(forward_steam_uri("https://example.net/"))


class PrivateStorageTests(unittest.TestCase):
    def test_json_is_private_and_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "favorites.json")
            save_json(path, {"saved_password": "test-only"})
            mode = stat.S_IMODE(os.stat(path).st_mode)
            self.assertEqual(mode, 0o600)
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), {"saved_password": "test-only"})


if __name__ == "__main__":
    unittest.main()
