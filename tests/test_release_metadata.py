import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("check_release", ROOT / "bin/check-release.py")
CHECK_RELEASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK_RELEASE)


class ReleaseMetadataTests(unittest.TestCase):
    def test_release_versions_match(self):
        versions = CHECK_RELEASE.release_versions()
        self.assertEqual(set(versions.values()), {"0.9.0"})


if __name__ == "__main__":
    unittest.main()
