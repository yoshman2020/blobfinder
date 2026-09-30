import logging
import time
from pathlib import Path


def purge_old_files(
    directories: list[Path],
    ttl: int,
    logger: logging.Logger,
):
    now = time.time()

    for directory in directories:
        for file in directory.iterdir():
            if now - file.stat().st_mtime > ttl:
                file.unlink(missing_ok=True)
                logger.info("purged %s", file.name)
