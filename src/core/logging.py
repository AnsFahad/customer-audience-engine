import logging
import sys
from src.core.config import get_settings

settings = get_settings()


def setup_logging() -> logging.Logger:
    """Configures centralized structured logging for the application."""
    log_format = (
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s"
    )

    logging.basicConfig(
        level=settings.LOG_LEVEL.upper(),
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    logger = logging.getLogger(settings.APP_NAME)
    return logger


logger = setup_logging()
