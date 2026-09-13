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

PDF_URL = os.environ.get("ISTANBUL_2023_PDF_URL", "")
PDF_PATH = BASE_DIR / "2023_genel_tr.pdf"
CSV_PATH = BASE_DIR / "bogazici_35_dataset.csv"

YEAR = 2023
RACE_NAME = "Bosphorus Cross-Continental Swimming Race (35th)"

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/18.6 Safari/605.1.15"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Priority": "u=0, i",
}

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

AGE_GROUP_BY_LETTER = {
    "A": "14-18",
    "B": "19-24",
    "C": "25-29",
    "D": "30-34",
    "E": "35-39",
    "F": "40-44",
    "G": "45-49",
    "H": "50-54",
    "I": "55-59",
    "J": "60-64",
    "K": "65-69",
    "L": "70+",
}

GENDER_MAP = {"Erkek": "Male", "Kadın": "Female"}

def download_pdf():
    if PDF_PATH.exists():
        print(f"PDF zaten mevcut: {PDF_PATH.name}")
        return
    print(f"PDF indiriliyor: {PDF_URL}")
    resp = requests.get(PDF_URL, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    PDF_PATH.write_bytes(resp.content)
    print(f"PDF kaydedildi: {PDF_PATH.name} ({len(resp.content)} bayt)")


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

def build_dataset(rows):
    df = pd.DataFrame(rows)

    df["Finish Time (min)"] = df["Finish Time (min)"].round(3)

    fin = df["Status"] == "FINISHED"
    fin_df = df.loc[fin].sort_values(["Finish Time (min)", "Bib Number"])

    df["Overall Position"] = pd.Series([None] * len(df), index=df.index, dtype="Int64")
    df["Relative Position"] = pd.Series([None] * len(df), index=df.index, dtype="float64")
    if not fin_df.empty:
        df.loc[fin, "Overall Position"] = (
            fin_df["Finish Time (min)"].rank(method="min").astype("Int64")
        )
        df.loc[fin, "Relative Position"] = (
            fin_df["Finish Time (min)"].rank(pct=True).round(4)
        )

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
        "Birth Year",
        "Category Position",
        "Status",
    ]
    df = df[columns].reset_index(drop=True)
    df["Bib Number"] = df["Bib Number"].astype(int)
    df["Gender Position"] = pd.to_numeric(df["Gender Position"], errors="coerce").astype("Int64")
    df["Overall Position"] = pd.to_numeric(df["Overall Position"], errors="coerce").astype("Int64")
    df["Category Position"] = pd.to_numeric(df["Category Position"], errors="coerce").astype("Int64")
    df["Birth Year"] = pd.to_numeric(df["Birth Year"], errors="coerce").astype("Int64")
    return df

def summarize(df):
    bar = "=" * 66
    print(bar)
    print(f"{RACE_NAME} ({YEAR}) — veri seti özeti")
    print(bar)
    print(f"Toplam yarışmacı       : {len(df):,}")
    print(df["Gender"].value_counts().to_string())
    print("\nDurum dağılımı:")
    print(df["Status"].value_counts().to_string())
    fin = df[df["Status"] == "FINISHED"]
    if not fin.empty:
        fastest = fin.sort_values("Overall Position").iloc[0]
        print(
            f"\nEn hızlı genel         : {fastest['Name']} "
            f"({fastest['Finish Time (raw)']}, {fastest['Gender']}, "
            f"{fastest['Age Group']})"
        )
    print(bar)

def main() -> None:
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