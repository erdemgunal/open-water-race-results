from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd
import pdfplumber
import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR.parents[1] / ".env")

PDF_URL = os.environ.get("ISTANBUL_2025_PDF_URL", "")
PDF_PATH = BASE_DIR / "2025_genel_tr.pdf"
CSV_PATH = BASE_DIR / "bogazici_37_dataset.csv"

YEAR = 2025
RACE_NAME = "Bosphorus Cross-Continental Swimming Race (37th)"

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/18.6 Safari/605.1.15"
    ),
}

ROW_RE = re.compile(
    r"^(?P<rank>\d+)\s+"
    r"(?P<bib>\d+)\s+"
    r"(?P<name>.*?)\s+"
    r"(?P<category>(?:E|K)\s+[A-Z]\s+\([^)]*\)|Para)\s+"
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?)$"
)

AGE_RANGE_RE = re.compile(r"(\d{1,2}\s*[-–]\s*\d{1,2}|\d{1,2}\s*\+)")

def download_pdf():
    if PDF_PATH.exists():
        print(f"PDF zaten mevcut: {PDF_PATH.name}")
        return
    print(f"PDF indiriliyor: {PDF_URL}")
    resp = requests.get(PDF_URL, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    PDF_PATH.write_bytes(resp.content)
    print(f"PDF kaydedildi: {PDF_PATH.name} ({len(resp.content)} bayt)")

def gender_from_title(title):
    return "Female" if "Women" in title else "Male"

def extract_age_group(category):
    if category == "Para":
        return "Para"
    m = re.search(r"\(([^()]*)\)", category)
    inner = m.group(1) if m else category
    mm = AGE_RANGE_RE.search(inner)
    return mm.group(1).replace(" ", "") if mm else inner.strip()

def parse_time_to_minutes(text):
    parts = text.split(":")
    if len(parts) == 3:
        h, m, s = (int(p) for p in parts)
        return h * 60 + m + s / 60.0
    m, s = (int(p) for p in parts)
    return m + s / 60.0

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

def build_dataset(rows):
    df = pd.DataFrame(rows)

    df["Finish Time (min)"] = df["Finish Time (min)"].round(3)

    df = df.sort_values(["Finish Time (min)", "Bib Number"]).reset_index(drop=True)
    df["Overall Position"] = (
        df["Finish Time (min)"].rank(method="min").astype("Int64")
    )

    df["Relative Position"] = df["Finish Time (min)"].rank(pct=True).round(4)

    df["Year"] = YEAR
    df["Race"] = RACE_NAME

    columns = [
        "Name",
        "Bib Number",
        "Gender",
        "Age Group",
        "Gender Position",
        "Overall Position",
        "Finish Time (raw)",
        "Finish Time (min)",
        "Relative Position",
        "Year",
        "Race",
    ]
    df = df[columns].sort_values("Overall Position").reset_index(drop=True)
    df["Bib Number"] = df["Bib Number"].astype(int)
    df["Gender Position"] = df["Gender Position"].astype(int)
    return df

def summarize(df):
    bar = "=" * 66
    print(bar)
    print(f"{RACE_NAME} ({YEAR}) — veri seti özeti")
    print(bar)
    print(f"Toplam yarışmacı       : {len(df):,}")
    print(df["Gender"].value_counts().to_string())
    if not df.empty:
        fastest = df.iloc[0]
        print(
            f"En hızlı genel         : {fastest['Name']} "
            f"({fastest['Finish Time (raw)']}, {fastest['Gender']}, "
            f"{fastest['Age Group']})"
        )
    print(bar)

def main():
    download_pdf()
    rows = extract_rows()
    if not rows:
        raise RuntimeError("PDF'ten hiç yarışmacı satırı ayrıştırılamadı.")

    df = build_dataset(rows)
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")

    summarize(df)
    print(f"CSV kaydedildi: {CSV_PATH}")
    print(f"   {len(df)} yarışmacı, {len(df.columns)} sütun")

if __name__ == "__main__":
    main()