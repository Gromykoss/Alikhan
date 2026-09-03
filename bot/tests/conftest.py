"""Pytest setup for tests under bot/tests."""

from pathlib import Path
import sys


BOT_DIR = Path(__file__).resolve().parents[1]
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))
