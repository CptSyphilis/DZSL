import unittest
from unittest.mock import patch

from connect import Connector
from dayz_runtime import ModSetupError


class ConnectorLauncherTests(unittest.TestCase):
    def setUp(self):
        self.connector = Connector.__new__(Connector)
        self.connector.cfg = {"extra_mods": ""}

    @patch("connect.setup_mod_links", return_value=[])
    def test_setup_only_returns_successful_completed_process(self, _setup):
        result = self.connector._run_launcher({}, mod_ids=[], launch=False)

        self.assertEqual(result.args, [])
        self.assertEqual(result.returncode, 0)

    @patch("connect.setup_mod_links", side_effect=ModSetupError("invalid mod"))
    def test_setup_failure_returns_failed_completed_process(self, _setup):
        result = self.connector._run_launcher({}, mod_ids=[], launch=False)

        self.assertEqual(result.args, [])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "invalid mod")


if __name__ == "__main__":
    unittest.main()
