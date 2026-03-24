"""Logging configuration for LegalDesk.

SECURITY CONTRACT:
- NEVER log: original_text, approved_text, mapping contents, LLM responses, PII values
- ALLOWED to log: counts (spans found, results count), flags (degraded), status codes
"""

import logging


def setup_logging() -> None:
    """Configure root legaldesk logger. Idempotent — safe to call multiple times."""
    logger = logging.getLogger("legaldesk")
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
