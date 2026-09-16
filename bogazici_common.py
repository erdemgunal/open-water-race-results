"""Boğaziçi (İstanbul) 2022–2025 PDF ayrıştırma scriptleri için ortak yardımcılar.

racekit paketinden bağımsızdır; yıllara göre tekrarlanan sabitleri ve
fonksiyonları tek yerde toplar.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

# Tüm yıllardaki istek başlıklarının birleşimi (2023 ek başlıklar gönderir;
# bunlar diğer yıllar için zararsızdır).
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/18.6 Safari/605.1.15"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Priority": "u=0, i",
}

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


def download_pdf(pdf_url, pdf_path, headers=HEADERS, timeout=60):
    """PDF'i indirir (zaten mevcutsa yeniden indirmez)."""
    pdf_path = Path(pdf_path)
    if pdf_path.exists():
        print(f"PDF zaten mevcut: {pdf_path.name}")
        return
    print(f"PDF indiriliyor: {pdf_url}")
    resp = requests.get(pdf_url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    pdf_path.write_bytes(resp.content)
    print(f"PDF kaydedildi: {pdf_path.name} ({len(resp.content)} bayt)")


def gender_from_title(title):
    """Sayfa başlığından cinsiyeti çıkarır (Women → Female, diğer → Male)."""
    return "Female" if "Women" in title else "Male"


def parse_time_to_minutes(text):
    """'HH:MM:SS' veya 'MM:SS' biçimindeki süreyi dakikaya çevirir."""
    parts = text.split(":")
    if len(parts) == 3:
        h, m, s = (int(p) for p in parts)
        return h * 60 + m + s / 60.0
    m, s = (int(p) for p in parts)
    return m + s / 60.0


def build_dataset(rows, year, race_name):
    """Satır sözlüklerinden ortak şemada bir DataFrame üretir.

    'Status' sütunu varsa (2022–2024) sıra yalnızca FINISHED için hesaplanır;
    yoksa (2025) tüm satırlar bitirmiş kabul edilir.
    """
    df = pd.DataFrame(rows)

    df["Finish Time (min)"] = df["Finish Time (min)"].round(3)

    has_status = "Status" in df.columns

    if has_status:
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
    else:
        df = df.sort_values(["Finish Time (min)", "Bib Number"]).reset_index(drop=True)
        df["Overall Position"] = df["Finish Time (min)"].rank(method="min").astype("Int64")
        df["Relative Position"] = df["Finish Time (min)"].rank(pct=True).round(4)

    df["Year"] = year
    df["Race"] = race_name

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
    for col in ("Nation", "Birth Year", "Category Position", "Status"):
        if col in df.columns:
            columns.append(col)

    df = df[columns]
    if has_status:
        df = df.reset_index(drop=True)  # 2022–2024: PDF sırası korunur.
    else:
        df = df.sort_values("Overall Position").reset_index(drop=True)  # 2025

    df["Bib Number"] = df["Bib Number"].astype(int)
    df["Gender Position"] = pd.to_numeric(df["Gender Position"], errors="coerce").astype("Int64")
    df["Overall Position"] = pd.to_numeric(df["Overall Position"], errors="coerce").astype("Int64")
    if "Category Position" in df.columns:
        df["Category Position"] = pd.to_numeric(df["Category Position"], errors="coerce").astype("Int64")
    if "Birth Year" in df.columns:
        df["Birth Year"] = pd.to_numeric(df["Birth Year"], errors="coerce").astype("Int64")
    return df


def summarize(df, year, race_name):
    """Veri seti özetini konsola yazar."""
    bar = "=" * 66
    print(bar)
    print(f"{race_name} ({year}) — veri seti özeti")
    print(bar)
    print(f"Toplam yarışmacı       : {len(df):,}")
    print(df["Gender"].value_counts().to_string())

    has_status = "Status" in df.columns
    if has_status:
        print("\nDurum dağılımı:")
        print(df["Status"].value_counts().to_string())
        fin = df[df["Status"] == "FINISHED"]
    else:
        fin = df

    if not fin.empty:
        fastest = fin.sort_values("Overall Position").iloc[0]
        prefix = "\n" if has_status else ""
        print(
            f"{prefix}En hızlı genel         : {fastest['Name']} "
            f"({fastest['Finish Time (raw)']}, {fastest['Gender']}, "
            f"{fastest['Age Group']})"
        )
    print(bar)


def save_dataset(df, csv_path):
    """DataFrame'i CSV olarak kaydeder ve kayıt özet satırını yazar."""
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"CSV kaydedildi: {csv_path}")
    print(f"   {len(df)} yarışmacı, {len(df.columns)} sütun")
