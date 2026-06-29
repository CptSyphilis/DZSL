"""Process-wide guard preventing overlapping Workshop operations."""

import threading


_lock = threading.Lock()
_active_label = ""


def try_begin(label):
    global _active_label
    with _lock:
        if _active_label:
            return False, _active_label
        _active_label = str(label)
        return True, ""


def finish():
    global _active_label
    with _lock:
        _active_label = ""


def active_label():
    with _lock:
        return _active_label
