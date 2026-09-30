import logging
import logging.handlers
import os
from pathlib import Path


def setup_logging(base_dir: Path):
    # ログ設定: 1MB x 3世代
    # ログレベルは環境変数 LOG_LEVEL で変更可能 (DEBUG/INFO/WARNING/ERROR)
    level = getattr(
        logging,
        os.environ.get("LOG_LEVEL", "INFO").upper(),
        logging.INFO,
    )

    handler = logging.handlers.RotatingFileHandler(
        base_dir / "app.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )

    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )

    logging.basicConfig(
        level=level,
        handlers=[
            handler,
            logging.StreamHandler(),
        ],
    )

    return logging.getLogger("blobfinder")
