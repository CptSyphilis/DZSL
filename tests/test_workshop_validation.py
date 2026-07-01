import os
import tempfile
import unittest

from dzsl.steam.workshop import validate_mod_folder


class WorkshopValidationTests(unittest.TestCase):
    def test_nonempty_pbo_is_valid_without_optional_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            addons = os.path.join(directory, "Addons")
            os.makedirs(addons)
            with open(os.path.join(addons, "example.pbo"), "wb") as handle:
                handle.write(b"payload")

            self.assertEqual(validate_mod_folder(directory), (True, ""))

    def test_metadata_without_pbo_is_not_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            with open(os.path.join(directory, "meta.cpp"), "w", encoding="utf-8") as handle:
                handle.write('name = "Example";')

            self.assertEqual(validate_mod_folder(directory), (False, "no PBO payload files were found"))


if __name__ == "__main__":
    unittest.main()
