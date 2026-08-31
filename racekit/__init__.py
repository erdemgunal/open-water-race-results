import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

__version__ = "0.2.0"

from racekit.api import fetch_event, visualize_event
from racekit.config import EventConfig, ListSpec