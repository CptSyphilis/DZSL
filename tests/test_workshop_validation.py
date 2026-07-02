import os
import tempfile
import unittest

from dzsl.steam.workshop import item_staging_signature, validate_mod_folder


class WorkshopValidationTests(unittest.TestCase):
    def test_staging_signature_reads_download_activity(self):
        with tempfile.TemporaryDirectory() as directory:
            workshop = os.path.join(directory, "workshop")
            manifest = os.path.join(workshop, "appworkshop_221100.acf")
            staging = os.path.join(workshop, "downloads", "221100", "123", "Addons")
            os.makedirs(staging)
            payload = os.path.join(staging, "example.pbo")
            with open(payload, "wb") as handle:
                handle.write(b"payload")

            allocated, modified = item_staging_signature([manifest], "123")

            self.assertGreater(allocated, 0)
            self.assertGreater(modified, 0)

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
