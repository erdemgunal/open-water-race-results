from racekit.api import visualize_event
from pathlib import Path
from event import EVENT
import argparse
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

def main():
    parser = argparse.ArgumentParser(description=f"{EVENT.name} — görselleştirme")
    parser.add_argument("--bib", type=int, default=None,
                        help="senin bib numaran (varsayılan: event.py default_bib)")
    parser.add_argument("--time", type=float, default=None,
                        help="senin süren saniye cinsinden (--bib'i ezer)")
    parser.add_argument("--min-entries", type=int, default=5,
                        help="ülke grafiği için minimum katılımcı sayısı")
    parser.add_argument("--max-nations", type=int, default=15,
                        help="ülke grafiğinde gösterilecek maksimum ülke")
    parser.add_argument("--show", action="store_true",
                        help="grafikleri interaktif olarak da aç")
    args = parser.parse_args()

    visualize_event(EVENT, bib=args.bib, time_override=args.time,
                    min_entries=args.min_entries, max_nations=args.max_nations,
                    show=args.show)

if __name__ == "__main__":
    main()