from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pdfplumber
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from bogazici_common import (
    AGE_GROUP_BY_LETTER,
    GENDER_MAP,
    HEADERS,
    build_dataset,
    download_pdf,
    parse_time_to_minutes,
    save_dataset,
    summarize,
)

PDF_URL = os.environ.get("ISTANBUL_2023_PDF_URL", "")
PDF_PATH = BASE_DIR / "2023_genel_tr.pdf"
CSV_PATH = BASE_DIR / "bogazici_35_dataset.csv"

YEAR = 2023
RACE_NAME = "Bosphorus Cross-Continental Swimming Race (35th)"

FINISHER_RE = re.compile(
    r"^(?P<pos>\d+)\s+(?P<pos2>\d+)\s+(?P<bib>\d+)\s+"
    r"(?P<letter>[A-Z])\s+/\s+(?P<catrank>\d+)\s+"
    r"(?P<gender>Erkek|Kadın)\s+(?P<name>.+?)\s+(?P<yob>\d{4})\s+"
    r"(?P<time>\d{1,2}:\d{2}:\d{2})$"
)

DNF_RE = re.compile(
    r"^(?P<pos>\d+)\s+(?P<bib>\d+)\s+"
    r"(?P<letter>[A-Z])\s+/\s+"
    r"(?P<gender>Erkek|Kadın)\s+(?P<name>.+?)\s+(?P<yob>\d{4})\s+"
    r"DNF$"
)

DQ_RE = re.compile(
    r"^(?P<pos>\d+)\s+(?P<bib>\d+)\s+"
    r"(?P<letter>[A-Z])\s+/\s+"
    r"(?P<gender>Erkek|Kadın)\s+(?P<name>.+?)\s+(?P<yob>\d{4})\s+"
    r"DQ\s+(?P<time>\d{1,2}:\d{2}:\d{2})$"
)

def extract_rows():
    rows: list[dict] = []
    with pdfplumber.open(PDF_PATH) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                if "Timing and ranking" in line or "Printed at" in line:
                    continue
                if line.startswith(("Erkekler", "Kadınlar", "S/P")):
                    continue

                m = FINISHER_RE.match(line) or DNF_RE.match(line) or DQ_RE.match(line)
                if not m:
                    continue

                if m.re is FINISHER_RE:
                    status = "FINISHED"
                    catrank = int(m["catrank"])
                    pos = int(m["pos"])
                    time = m["time"]
                elif m.re is DNF_RE:
                    status = "DNF"
                    catrank = None
                    pos = None
                    time = None
                else:  # DQ_RE
                    status = "DQ"
                    catrank = None
                    pos = None
                    time = m["time"]

                rows.append(
                    {
                        "Name": re.sub(r"\s+", " ", m["name"]).strip(),
                        "Bib Number": int(m["bib"]),
                        "Gender": GENDER_MAP[m["gender"]],
                        "Age Group": AGE_GROUP_BY_LETTER.get(m["letter"], m["letter"]),
                        "Gender Position": pos,
                        "Category Position": catrank,
                        "Finish Time (raw)": time if time else "",
                        "Finish Time (min)": parse_time_to_minutes(time) if time else None,
                        "Birth Year": int(m["yob"]),
                        "Status": status,
                    }
                )
    return rows

def main() -> None:
    download_pdf(PDF_URL, PDF_PATH, headers=HEADERS)
    rows = extract_rows()
    if not rows:
        raise RuntimeError("PDF'ten hiç yarışmacı satırı ayrıştırılamadı.")

    df = build_dataset(rows, YEAR, RACE_NAME)
    summarize(df, YEAR, RACE_NAME)
    save_dataset(df, CSV_PATH)

if __name__ == "__main__":
    main()