import os
import tempfile
import unittest

from steam_workshop import (
    item_download_progress,
    item_ready,
    item_record,
    parse_keyvalues,
    validate_mod_folder,
)


MANIFEST = '''
"AppWorkshop"
{
    "WorkshopItemsInstalled"
    {
        "123456" { "size" "10" "manifest" "current" }
    }
    "WorkshopItemDetails"
    {
        "123456"
        {
            "manifest" "current"
            "subscribedby" "42"
            "latest_manifest" "current"
            "BytesDownloaded" "5"
            "BytesToDownload" "10"
        }
    }
}
'''


class SteamWorkshopManifestTests(unittest.TestCase):
    def test_parses_nested_keyvalues(self):
        parsed = parse_keyvalues(MANIFEST)
        details = parsed["AppWorkshop"]["WorkshopItemDetails"]["123456"]
        self.assertEqual(details["latest_manifest"], "current")

    def test_reports_subscription_progress_and_ready_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = os.path.join(tmp, "appworkshop_221100.acf")
            with open(manifest, "w", encoding="utf-8") as handle:
                handle.write(MANIFEST)
            item_dir = os.path.join(tmp, "content", "123456")
            os.makedirs(item_dir)
            with open(os.path.join(item_dir, "meta.cpp"), "w", encoding="utf-8") as handle:
                handle.write("name = test;")
            with open(os.path.join(item_dir, "content.pbo"), "wb") as handle:
                handle.write(b"PBO")

            record = item_record([manifest], "123456")
            self.assertTrue(record["subscribed"])
            self.assertEqual(item_download_progress([manifest], "123456"), (5, 10))
            self.assertTrue(item_ready([manifest], [os.path.join(tmp, "content")], "123456"))

    def test_rejects_folder_without_pbo_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "meta.cpp"), "w", encoding="utf-8") as handle:
                handle.write("name = incomplete;")

            valid, reason = validate_mod_folder(tmp)

            self.assertFalse(valid)
            self.assertIn("PBO", reason)

    def test_accepts_mod_cpp_and_nested_pbo(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "mod.cpp"), "w", encoding="utf-8") as handle:
                handle.write("name = valid;")
            addons = os.path.join(tmp, "Addons")
            os.makedirs(addons)
            with open(os.path.join(addons, "content.PBO"), "wb") as handle:
                handle.write(b"payload")

            self.assertEqual(validate_mod_folder(tmp), (True, ""))


if __name__ == "__main__":
    unittest.main()
