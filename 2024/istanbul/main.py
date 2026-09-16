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
    HEADERS,
    build_dataset,
    download_pdf,
    gender_from_title,
    parse_time_to_minutes,
    save_dataset,
    summarize,
)

PDF_URL = os.environ.get("ISTANBUL_2024_PDF_URL", "")
PDF_PATH = BASE_DIR / "2024_genel_tr.pdf"
CSV_PATH = BASE_DIR / "bogazici_36_dataset.csv"

YEAR = 2024
RACE_NAME = "Bosphorus Cross-Continental Swimming Race (36th)"

ROW_RE = re.compile(
    r"^(?P<rank>\d+|DNF|DSQ|DNS)\s+"
    r"(?P<catrank>\d+|DNF|DSQ|DNS)\s*/\s*(?P<letter>[A-Z])\s+"
    r"(?P<bib>\d+)\s+"
    r"(?P<name>.*?)\s+"
    r"(?P<nation>[A-Z]{2,3})\s+"
    r"(?P<birth>\d{4})"
    r"(?:\s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?))?$"
)

def extract_rows():
    rows: list[dict] = []
    with pdfplumber.open(PDF_PATH) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.splitlines()
            if len(lines) < 5:
                continue
            gender = gender_from_title(lines[2])
            for line in lines[4:]:
                if "Printed at" in line:
                    continue
                m = ROW_RE.match(line)
                if not m:
                    continue
                status = "FINISHED" if m["rank"].isdigit() else m["rank"]
                rows.append(
                    {
                        "Name": re.sub(r"\s+", " ", m["name"]).strip(),
                        "Bib Number": int(m["bib"]),
                        "Gender": gender,
                        "Age Group": AGE_GROUP_BY_LETTER.get(m["letter"], m["letter"]),
                        "Gender Position": int(m["rank"]) if status == "FINISHED" else None,
                        "Category Position": int(m["catrank"]) if status == "FINISHED" else None,
                        "Finish Time (raw)": m["time"] if m["time"] else "",
                        "Finish Time (min)": (
                            parse_time_to_minutes(m["time"]) if m["time"] else None
                        ),
                        "Nation": m["nation"],
                        "Birth Year": int(m["birth"]),
                        "Status": status,
                    }
                )
    return rows

def main():
    download_pdf(PDF_URL, PDF_PATH, headers=HEADERS)
    rows = extract_rows()
    if not rows:
        raise RuntimeError("PDF'ten hiç yarışmacı satırı ayrıştırılamadı.")

    df = build_dataset(rows, YEAR, RACE_NAME)
    summarize(df, YEAR, RACE_NAME)
    save_dataset(df, CSV_PATH)

if __name__ == "__main__":
    main()