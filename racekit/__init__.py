import logging
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

__version__ = "0.3.0"

if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

from racekit.api import fetch_event
from racekit.config import EventConfig, ListSpec