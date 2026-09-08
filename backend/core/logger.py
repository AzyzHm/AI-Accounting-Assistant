import logging
import sys

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    """Configures the root logger to write to stdout, once per process.

    Safe to call multiple times (for example from both `main.py` and a
    test module), only the first call has any effect.
    """
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Returns a logger for `name`, configuring terminal logging on first use.

    Usage: `logger = get_logger(__name__)` at the top of a module, then
    `logger.info(...)`, `logger.warning(...)`, `logger.error(...)` wherever
    something worth debugging happens.
    """
    configure_logging()
    return logging.getLogger(name)
