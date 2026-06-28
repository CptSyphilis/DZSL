import os
import tempfile
import unittest

from ui.download import ModDownloadManager


class DownloadStagingTests(unittest.TestCase):
    def setUp(self):
        self.manager = ModDownloadManager.__new__(ModDownloadManager)

    def test_commit_replaces_old_mod_only_after_staging_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "123")
            staging = dest + ".dzsl-partial"
            os.makedirs(dest)
            os.makedirs(staging)
            with open(os.path.join(dest, "old.pbo"), "wb") as handle:
                handle.write(b"old")
            with open(os.path.join(staging, "new.pbo"), "wb") as handle:
                handle.write(b"new")

            self.manager._commit_staged_mod(staging, dest)

            self.assertTrue(os.path.isfile(os.path.join(dest, "new.pbo")))
            self.assertFalse(os.path.exists(os.path.join(dest, "old.pbo")))
            self.assertFalse(os.path.exists(dest + ".dzsl-backup"))

    def test_recovery_restores_interrupted_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "123")
            backup = dest + ".dzsl-backup"
            os.makedirs(backup)
            with open(os.path.join(backup, "content.pbo"), "wb") as handle:
                handle.write(b"content")

            self.manager._recover_staged_mod(dest)

            self.assertTrue(os.path.isfile(os.path.join(dest, "content.pbo")))
            self.assertFalse(os.path.exists(backup))


if __name__ == "__main__":
    unittest.main()
