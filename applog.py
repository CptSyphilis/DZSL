import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.expanduser("~/.config/dzsl")

_level = logging.INFO
_configured = set()


def setup_logging(level=logging.INFO):
    global _level
    _level = level


def get_logger(name):
    logger = logging.getLogger(f"dzsl.{name}")
    if name not in _configured:
        os.makedirs(LOG_DIR, exist_ok=True)
        logger.setLevel(_level)
        logger.propagate = False
        handler = RotatingFileHandler(
            os.path.join(LOG_DIR, f"{name}.log"), maxBytes=2 * 1024 * 1024, backupCount=3,
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(handler)
        _configured.add(name)
    return logger
