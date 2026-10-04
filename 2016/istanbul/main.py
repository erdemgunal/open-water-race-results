import os
import re
import sys
from collections import defaultdict
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

PDF_URL = os.environ.get("ISTANBUL_2016_PDF_URL", "")
PDF_PATH = BASE_DIR / "2016_genel_tr.pdf"
CSV_PATH = BASE_DIR / "bogazici_28_dataset.csv"

YEAR = 2016
RACE_NAME = "Bosphorus Cross-Continental Swimming Race (28th)"

# 2016 "Overall Results" olarak karma (kadın/erkek bir arada) sıralanır; bu yüzden
# S/P sütunu cinsiyet içi sıra değil, genel sıradır. Ayrıca bazı satırlarda doğum
# yılı (YOB) boştur.
FINISHER_RE = re.compile(
    r"^(?P<pos>\d+)\s+(?P<bib>\d+)\s+"
    r"(?P<letter>[A-Z])\s+"
    r"(?P<gender>Erkek|Kadın)\s+(?P<name>.+?)\s+"
    r"(?P<nation>[A-Z]{2,4})\s+(?:(?P<yob>\d{4})\s+)?"
    r"(?P<time>\d{1,2}:\d{2}:\d{2})$"
)

DNF_RE = re.compile(
    r"^(?P<bib>\d+)\s+(?P<letter>[A-Z])\s+"
    r"(?P<gender>Erkek|Kadın)\s+(?P<name>.+?)\s+"
    r"(?P<nation>[A-Z]{2,4})\s+(?P<yob>\d{4})\s+"
    r"DNF$"
)

def extract_rows():
    rows = []
    with pdfplumber.open(PDF_PATH) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                if not line or not line[0].isdigit():
                    continue

                m = FINISHER_RE.match(line) or DNF_RE.match(line)
                if not m:
                    continue

                if m.re is FINISHER_RE:
                    status = "FINISHED"
                    pos = int(m["pos"])
                    time = m["time"]
                    yob = m["yob"]
                else:
                    status = "DNF"
                    pos = None
                    time = None
                    yob = m["yob"]

                rows.append(
                    {
                        "Name": re.sub(r"\s+", " ", m["name"]).strip(),
                        "Bib Number": int(m["bib"]),
                        "Gender": GENDER_MAP[m["gender"]],
                        "Age Group": AGE_GROUP_BY_LETTER.get(m["letter"], m["letter"]),
                        "Gender Position": None,  # genel sıradan aşağıda hesaplanır
                        "Finish Time (raw)": time if time else "",
                        "Finish Time (min)": parse_time_to_minutes(time) if time else None,
                        "Nation": m["nation"],
                        "Birth Year": int(yob) if yob else None,
                        "Status": status,
                    }
                )

    # Genel sıra (S/P) cinsiyet içi sıraya dönüştürülür: bitirenler süreye göre
    # sıralanıp her cinsiyet içinde 1'den başlayarak numaralandırılır.
    finishers = [r for r in rows if r["Status"] == "FINISHED"]
    finishers.sort(key=lambda r: (r["Finish Time (min)"], r["Bib Number"]))
    counter = defaultdict(int)
    for r in finishers:
        counter[r["Gender"]] += 1
        r["Gender Position"] = counter[r["Gender"]]

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
