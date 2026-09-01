import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from event import EVENT
from racekit.api import fetch_event

def main():
    parser = argparse.ArgumentParser(description=f"{EVENT.name} — veri çekme")
    parser.add_argument("--offline", action="store_true",
                        help="sağlayıcı yerine arşivlenmiş *_raw.json dosyalarını kullan")
    args = parser.parse_args()

    fetch_event(EVENT, offline=args.offline)

if __name__ == "__main__":
    main()