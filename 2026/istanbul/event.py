from racekit.config import EventConfig, ListSpec
from pathlib import Path
import os

RACE_DIR = Path(__file__).resolve().parent

EVENT = EventConfig(
    key="istanbul_2026",
    name="Boğaziçi Kıtalararası Yüzme Yarışı 2026 (38.)",
    event_id=413831,
    year=2026,
    distance_m=6500.0,
    data_dir=RACE_DIR / "raceresult_data",
    output_dir=RACE_DIR / "output",
    dataset_name="bogazici_38_dataset",
    lists=(
        ListSpec("participants", "participants", "Online|Participants", "0"),
        ListSpec("live", "live", "Online|Live", "1"),
    ),
    result_role="live",
    default_bib=1831,
    owner_highlight=("M", "19-24"),
    auto_lookup={"gender": "M", "gender_rank": 348, "age_group_rank": 32},
    known_key=os.environ.get("ISTANBUL_2026_KEY"),
)