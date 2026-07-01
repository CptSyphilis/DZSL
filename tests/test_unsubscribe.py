import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from dzsl.ui.helpers import unsubscribe_mod_ids


class UnsubscribeTests(unittest.TestCase):
    def test_success_unsubscribes_before_removing_local_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            mod_dir = os.path.join(directory, "123")
            os.makedirs(mod_dir)
            result = subprocess.CompletedProcess([], 0, "", "")

            with patch("dzsl.ui.helpers.subprocess.run", return_value=result) as run:
                removed, error = unsubscribe_mod_ids(["123"], {"mods_dir": directory})

            self.assertEqual((removed, error), (["123"], ""))
            self.assertFalse(os.path.exists(mod_dir))
            self.assertIn("unsubscribe", run.call_args.args[0])

    def test_failed_unsubscribe_preserves_local_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            mod_dir = os.path.join(directory, "123")
            os.makedirs(mod_dir)
            result = subprocess.CompletedProcess([], 1, "", "Steam failed")

            with patch("dzsl.ui.helpers.subprocess.run", return_value=result):
                removed, error = unsubscribe_mod_ids(["123"], {"mods_dir": directory})

            self.assertEqual(removed, [])
            self.assertEqual(error, "Steam failed")
            self.assertTrue(os.path.isdir(mod_dir))


if __name__ == "__main__":
    unittest.main()
