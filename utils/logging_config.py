import logging
from pathlib import Path

from config.settings import PROJECT_ROOT, settings


def configure_logging() -> None:
    settings.ensure_directories()
    (PROJECT_ROOT / "logs").mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
