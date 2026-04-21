from __future__ import annotations

import logging


def get_analysis_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not any(getattr(handler, "_analysis_handler", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler._analysis_handler = True  # type: ignore[attr-defined]
        handler.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def quiet_external_loggers() -> None:
    logging.getLogger().setLevel(logging.WARNING)
    for name in ("langgraph", "langchain", "httpx", "httpcore", "groq", "urllib3", "psycopg"):
        logging.getLogger(name).setLevel(logging.WARNING)