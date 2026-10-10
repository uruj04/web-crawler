"""Logging setup: short messages on the console, full detail in the log file."""

import logging
import sys
from pathlib import Path


def setup_logging(log_file: Path) -> logging.Logger:
    logger = logging.getLogger("webcrawler")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(console)

    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(file_handler)
    except OSError:
        logger.warning("Could not open log file %s; logging to console only.", log_file)
    return logger
