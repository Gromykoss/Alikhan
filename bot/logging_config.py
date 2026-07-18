"""
logging_config.py — Structured logging for Alikhan bot (AUDIT-014).
Replaces scattered print() calls with rotating file logger + JSON format option.

Usage:
    from logging_config import get_logger
    log = get_logger(__name__)
    log.info("Processing message from %s", sender)
    log.error("Failed to send: %s", error)
"""
import logging
import logging.handlers
import os
import sys
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# ── Formatters ──
SIMPLE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
JSON_FORMAT = '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'

# ── Root logger setup ──

def setup_logging(level=logging.INFO, json_format=False):
    """Configure root logger with rotation and console output. Call once at startup."""
    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers to avoid duplicates on reload
    root.handlers.clear()

    fmt = JSON_FORMAT if json_format else SIMPLE_FORMAT
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S")

    # File handler with rotation (10 MB, keep 5 backups)
    log_path = os.path.join(LOG_DIR, "bot.log")
    fh = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    fh.setLevel(level)
    fh.setFormatter(formatter)
    root.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(level)
    ch.setFormatter(formatter)
    root.addHandler(ch)

    return root


def get_logger(name):
    """Get a logger for a specific module."""
    return logging.getLogger(name)


# Auto-initialize on import
if not logging.getLogger().handlers:
    setup_logging()
