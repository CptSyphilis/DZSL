import unittest

from dzsl.lifecycle import cancel_active_downloads


class Progress:
    def __init__(self):
        self.cancelled = False

    def request_cancel(self):
        self.cancelled = True


class App:
    pass


class LifecycleTests(unittest.TestCase):
    def test_cancel_active_download(self):
        app = App()
        app._active_progress = Progress()

        cancel_active_downloads(app)

        self.assertTrue(app._active_progress.cancelled)

    def test_cancel_without_active_download(self):
        cancel_active_downloads(App())
