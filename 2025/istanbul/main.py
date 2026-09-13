"""
37. Boğaziçi Kıtalararası Yüzme Yarışı (2025) — PDF sonuçlarından veri seti.

Resmî PDF sıralama listesini indirir, tabloyu ayrıştırır ve feature engineering
uygulayarak tüm yarışmacıları tek bir CSV dosyasına yazar.

Üretilen sütunlar (feature engineering sonrası):
    Name                -> PDF'teki Name (ham, büyük harf)
    Bib Number          -> PDF'teki Bib -> int
    Gender              -> sayfa başlığından ("Men"->Male, "Women"->Female)
    Age Group           -> category içindeki parantez ifadesi ("25-29", "70+"; "Para" özel)
    Gender Position     -> PDF'teki mevcut Rank (cinsiyet içi sıra)
    Overall Position    -> Men+Women birleştirilip Time'a göre yeniden sıralanır
    Finish Time (raw)   -> PDF'teki Time string'i
    Finish Time (min)   -> "H:MM:SS" / "MM:SS" karışık formatı ondalık dakikaya çevrilir
    Relative Position   -> rank(pct=True) ile percentile
    Year / Race         -> ileride birden fazla yılın PDF'ini birleştirmek için

Çıktı: 2025/istanbul/bogazici_37_dataset.csv
"""

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

# Satır formatı:  Rank Bib Name category Time
# category örnekleri: "E C (Men 25-29)", "K L (Woman 70+)", "Para"
ROW_RE = re.compile(
    r"^(?P<rank>\d+)\s+"
    r"(?P<bib>\d+)\s+"
    r"(?P<name>.*?)\s+"
    r"(?P<category>(?:E|K)\s+[A-Z]\s+\([^)]*\)|Para)\s+"
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?)$"
)

# "Men 25-29" / "Woman 70+" içinden yaş aralığını ayıklar
AGE_RANGE_RE = re.compile(r"(\d{1,2}\s*[-–]\s*\d{1,2}|\d{1,2}\s*\+)")



def download_pdf() -> None:
    """PDF'i bir kez indirir; zaten varsa tekrar indirmez (offline kullanım)."""
    if PDF_PATH.exists():
        print(f"PDF zaten mevcut: {PDF_PATH.name}")
        return
    print(f"PDF indiriliyor: {PDF_URL}")
    resp = requests.get(PDF_URL, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    PDF_PATH.write_bytes(resp.content)
    print(f"PDF kaydedildi: {PDF_PATH.name} ({len(resp.content)} bayt)")


def gender_from_title(title: str) -> str:
    """Sayfa başlığından cinsiyet: 'Men' -> Male, 'Women' -> Female."""
    return "Female" if "Women" in title else "Male"


def extract_age_group(category: str) -> str:
    """Category içindeki parantez ifadesinden yaş grubunu ayıklar."""
    if category == "Para":
        return "Para"
    m = re.search(r"\(([^()]*)\)", category)
    inner = m.group(1) if m else category
    mm = AGE_RANGE_RE.search(inner)
    return mm.group(1).replace(" ", "") if mm else inner.strip()


def parse_time_to_minutes(text: str) -> float:
    """'MM:SS' veya 'H:MM:SS' formatını ondalık dakikaya çevirir."""
    parts = text.split(":")
    if len(parts) == 3:
        h, m, s = (int(p) for p in parts)
        return h * 60 + m + s / 60.0
    m, s = (int(p) for p in parts)
    return m + s / 60.0


def extract_rows() -> list[dict]:
    """PDF'ten tüm yarışmacı satırlarını ham kayıt olarak döndürür."""
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


def build_dataset(rows: list[dict]) -> pd.DataFrame:
    """Feature engineering: overall sıra ve relative position ekler."""
    df = pd.DataFrame(rows)

    # Finish Time (min) ondalık dakika, 3 hane yeterli (0.001 dk = 0.06 sn).
    df["Finish Time (min)"] = df["Finish Time (min)"].round(3)

    # Men+Women birleştirilip Time'a göre yeniden sıralanır.
    # Aynı süreye sahip yarışmacılar aynı sırayı alır (rank method="min").
    df = df.sort_values(["Finish Time (min)", "Bib Number"]).reset_index(drop=True)
    df["Overall Position"] = (
        df["Finish Time (min)"].rank(method="min").astype("Int64")
    )

    # Percentile: en hızlı ~0'a, en yavaş 1'e yaklaşır (rank(pct=True)).
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


def summarize(df: pd.DataFrame) -> None:
    """Konsola kısa bir özet basar."""
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


