import logging
import os
from logging.handlers import RotatingFileHandler
from dzsl.paths import CONFIG_DIR

LOG_DIR = str(CONFIG_DIR)

_level = logging.INFO
_configured = set()


def setup_logging(level=logging.INFO):
    global _level
    _level = level


def get_logger(name):
    logger = logging.getLogger(f"dzsl.{name}")
    if name not in _configured:
        try:
            os.makedirs(LOG_DIR, mode=0o700, exist_ok=True)
            os.chmod(LOG_DIR, 0o700)
        except OSError:
            pass
        logger.setLevel(_level)
        logger.propagate = False
        fmt = logging.Formatter(
            "%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        )
        try:
            file_handler = RotatingFileHandler(
                os.path.join(LOG_DIR, f"{name}.log"),
                maxBytes=2 * 1024 * 1024,
                backupCount=3,
            )
            os.chmod(file_handler.baseFilename, 0o600)
            file_handler.setFormatter(fmt)
            logger.addHandler(file_handler)
        except OSError:
            pass
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(fmt)
        logger.addHandler(stream_handler)
        _configured.add(name)
    return logger
