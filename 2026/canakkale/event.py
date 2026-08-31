from racekit.config import EventConfig, ListSpec
from pathlib import Path
import os

RACE_DIR = Path(__file__).resolve().parent

EVENT = EventConfig(
    key="canakkale_2026",
    name="Çanakkale Boğaz Yüzme Yarışması 2026",
    event_id=410255,
    year=2026,
    distance_m=5000.0,
    data_dir=RACE_DIR / "raceresult_data",
    output_dir=RACE_DIR / "output",
    dataset_name="canakkale_2026_dataset",
    lists=(
        ListSpec("participants", "participants", "Online|Participants", "1"),
        ListSpec("overall", "results", "Online|OverallRankList", "1"),
        ListSpec("gender", "results", "Online|GenderRankList", "1"),
        ListSpec("agegroup", "results", "Online|AgeGroupRankList", "1"),
        ListSpec("disabled", "results", "Online|DisabledRank", "1"),
    ),
    result_role="overall",
    default_bib=230,
    owner_highlight=("M", "19-24"),
    known_key=os.environ.get("CANAKKALE_2026_KEY"),
)