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
    HEADERS,
    build_dataset,
    download_pdf,
    gender_from_title,
    parse_time_to_minutes,
    save_dataset,
    summarize,
)

PDF_URL = os.environ.get("ISTANBUL_2025_PDF_URL", "")
PDF_PATH = BASE_DIR / "2025_genel_tr.pdf"
CSV_PATH = BASE_DIR / "bogazici_37_dataset.csv"

YEAR = 2025
RACE_NAME = "Bosphorus Cross-Continental Swimming Race (37th)"

ROW_RE = re.compile(
    r"^(?P<rank>\d+)\s+"
    r"(?P<bib>\d+)\s+"
    r"(?P<name>.*?)\s+"
    r"(?P<category>(?:E|K)\s+[A-Z]\s+\([^)]*\)|Para)\s+"
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?)$"
)

AGE_RANGE_RE = re.compile(r"(\d{1,2}\s*[-–]\s*\d{1,2}|\d{1,2}\s*\+)")

def extract_age_group(category):
    if category == "Para":
        return "Para"
    m = re.search(r"\(([^()]*)\)", category)
    inner = m.group(1) if m else category
    mm = AGE_RANGE_RE.search(inner)
    return mm.group(1).replace(" ", "") if mm else inner.strip()

def extract_rows():
    rows: list[dict] = []
    with pdfplumber.open(PDF_PATH) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.splitlines()
            if len(lines) < 4:
                continue
            gender = gender_from_title(lines[1])
            for line in lines[3:]:
                if "Printed at" in line:
                    continue
                m = ROW_RE.match(line)
                if not m:
                    continue
                rows.append(
                    {
                        "Name": re.sub(r"\s+", " ", m["name"]).strip(),
                        "Bib Number": int(m["bib"]),
                        "Gender": gender,
                        "Age Group": extract_age_group(m["category"]),
                        "Gender Position": int(m["rank"]),
                        "Finish Time (raw)": m["time"],
                        "Finish Time (min)": parse_time_to_minutes(m["time"]),
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