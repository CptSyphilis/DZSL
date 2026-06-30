import os
import tempfile
import unittest

from dzsl.core.config import _steam_pipe_ready


class SteamReadinessTests(unittest.TestCase):
    def test_missing_pipe_is_not_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(_steam_pipe_ready((os.path.join(directory, "missing"),)))

    def test_pipe_without_reader_is_not_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "steam.pipe")
            os.mkfifo(path)
            self.assertFalse(_steam_pipe_ready((path,)))

    def test_listening_pipe_is_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "steam.pipe")
            os.mkfifo(path)
            reader = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            try:
                self.assertTrue(_steam_pipe_ready((path,)))
            finally:
                os.close(reader)
