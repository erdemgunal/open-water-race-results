from __future__ import annotations

"""
Çıktılar:
  2026/output/common_2026_dataset.csv   -> ortak yarışmacılar (yan yana)

Grafikler (canakkale_vs_istanbul_common_pace.png,
age_group_kruskal_wallis.png) bu dosyada üretilmez; aynı veriyi kullanıp
grafikleri basan ayrı script: common_2026_charts.py

Not: time_gap_seconds / time_gap_percent sütunları HAM bitiş süresi farkıdır
mesafeler (5 km vs 6.5 km) farklı olduğundan korelasyon için tempo sütunlarını
(pace_*_s100m) kullanın.

Kullanım:
  python3 common_2026_dataset.py         # özet + CSV
  python3 common_2026_dataset.py --list  # ortakların tamamını konsola da yazar
"""

import argparse
import importlib.util
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

CANAKKALE_CSV = BASE_DIR / "canakkale" / "raceresult_data" / "canakkale_2026_dataset.csv"
ISTANBUL_CSV = BASE_DIR / "istanbul" / "raceresult_data" / "bogazici_38_dataset.csv"
OUT_DIR = BASE_DIR / "output"
COMMON_CSV = OUT_DIR / "common_2026_dataset.csv"

def normalize_full_name(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = unicodedata.normalize("NFKC", str(value)).strip().upper()
    s = s.replace("İ", "I")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^A-Z]", "", s)

def read_dataset(path):
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]
    df["status"] = df["status"].fillna("").astype(str).str.strip().str.upper()
    df["swim_seconds"] = pd.to_numeric(df["swim_seconds"], errors="coerce")
    df["overall_rank"] = pd.to_numeric(df["overall_rank"], errors="coerce")
    df["birth_year"] = pd.to_numeric(df["birth_year"], errors="coerce")
    return df

def add_match_key(df):
    df = df.copy()
    name = df["full_name"].map(lambda v: normalize_full_name(v if pd.notna(v) else ""))
    nation = df["nation"].map(lambda v: str(v).strip().upper() if pd.notna(v) else "")
    year = df["birth_year"].map(lambda v: "" if pd.isna(v) else str(int(v)))
    df["_match_key"] = name + "|" + nation + "|" + year
    return df

def load_event(cfg_name: str):
    path = BASE_DIR / cfg_name / "event.py"
    spec = importlib.util.spec_from_file_location(f"event_{cfg_name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(PROJECT_ROOT))
    spec.loader.exec_module(mod)
    return mod.EVENT

def load_common():
    can_cfg = load_event("canakkale")
    ist_cfg = load_event("istanbul")

    can_raw = add_match_key(read_dataset(CANAKKALE_CSV))
    ist_raw = add_match_key(read_dataset(ISTANBUL_CSV))

    can = can_raw.drop_duplicates("_match_key", keep="first")
    ist = ist_raw.drop_duplicates("_match_key", keep="first")

    merged = can.merge(ist, on="_match_key", how="inner", suffixes=("_can", "_ist"))
    merged = merged.reset_index(drop=True)

    can_fin = merged["status_can"] == "FINISHED"
    ist_fin = merged["status_ist"] == "FINISHED"
    both_fin = can_fin & ist_fin

    out = pd.DataFrame({
        "full_name_canakkale": merged["full_name_can"],
        "full_name_istanbul": merged["full_name_ist"],
        "gender": merged["gender_can"],
        "nation": merged["nation_can"],
        "birth_year": merged["birth_year_can"],
        "age_group_canakkale": merged["age_group_can"],
        "overall_rank_canakkale": merged["overall_rank_can"],
        "status_canakkale": merged["status_can"],
        "time_canakkale": merged["time_text_can"],
        "swim_seconds_canakkale": merged["swim_seconds_can"],
        "age_group_istanbul": merged["age_group_ist"],
        "overall_rank_istanbul": merged["overall_rank_ist"],
        "status_istanbul": merged["status_ist"],
        "time_istanbul": merged["time_text_ist"],
        "swim_seconds_istanbul": merged["swim_seconds_ist"],
        "bib_canakkale": merged["bib_can"],
        "bib_istanbul": merged["bib_ist"],
    })

    # pace (sn/100m): mesafelere farkli oldugundan sure dogrudan karsilastirilmaz tempo uzerinden kiyaslanir !!!
    out["pace_canakkale_s100m"] = (out["swim_seconds_canakkale"] / (can_cfg.distance_m / 100.0))
    out["pace_istanbul_s100m"] = (out["swim_seconds_istanbul"] / (ist_cfg.distance_m / 100.0))
    out["time_gap_seconds"] = np.where(both_fin.to_numpy(), out["swim_seconds_istanbul"] - out["swim_seconds_canakkale"], np.nan)
    out["time_gap_percent"] = (out["time_gap_seconds"] / out["swim_seconds_canakkale"] * 100.0)

    out["_both"] = (~np.isnan(out["swim_seconds_canakkale"])) & (~np.isnan(out["swim_seconds_istanbul"]))
    out["_sort_t"] = out["swim_seconds_canakkale"].fillna(np.inf)
    out = out.sort_values(["_both", "_sort_t"], ascending=[False, True])
    out = out.drop(columns=["_both", "_sort_t"]).reset_index(drop=True)

    return {"can_cfg": can_cfg, "ist_cfg": ist_cfg,"can_raw": can_raw, "ist_raw": ist_raw, "can": can, "ist": ist, "merged": merged, "out": out}

def run(show_list):
    d = load_common()
    can_cfg, ist_cfg = d["can_cfg"], d["ist_cfg"]
    can_raw, ist_raw = d["can_raw"], d["ist_raw"]
    can, ist = d["can"], d["ist"]
    merged, out = d["merged"], d["out"]

    bar = "=" * 66
    print(bar)
    print("2026 ORTAK YARIŞMACILAR - " + can_cfg.name + " / " + ist_cfg.name)
    print(bar)
    print(f"{can_cfg.name}: {len(can_raw)} kayıtlı  ({can_cfg.distance_m:g} m)")
    print(f"{ist_cfg.name}: {len(ist_raw)} kayıtlı  ({ist_cfg.distance_m:g} m)")

    # ayni kisinin bir yarista birden fazla kaydi olursa ilkini al
    for label, df in (("Çanakkale", can_raw), ("İstanbul", ist_raw)):
        dups = int(df["_match_key"].duplicated().sum())
        if dups:
            print(f"  !! {label}: {dups} kopya anahtar var, ilk kayıt tutuluyor.")

    n = len(merged)
    print(bar)
    print(f"Ortak kayıtlı (iki yarışta da): {n}")
    if n:
        print(f"  Çanakkale'nin %{100.0 * n / len(can):.1f}'i "
              f"İstanbul'a da katılmış")
        print(f"  İstanbul'un %{100.0 * n / len(ist):.1f}'i "
              f"Çanakkale'ye de katılmış")

    # Cinsiyet / ülke tutarlılığını raporla
    for col in ("gender", "nation", "birth_year"):
        mism = int((merged[f"{col}_can"].astype(str) != merged[f"{col}_ist"].astype(str)).sum())
        if mism:
            print(f"  !! {col} uyuşmazlığı (aynı anahtar, farklı değer): {mism}")

    # Status çapraz tablosu
    can_fin = merged["status_can"] == "FINISHED"
    ist_fin = merged["status_ist"] == "FINISHED"
    both_fin = can_fin & ist_fin
    print(bar)
    print("Ortaklarda durum: "
          f"ikisi de bitirdi={int(both_fin.sum())}, "
          f"sadece Çanakkale bitirdi={int((can_fin & ~ist_fin).sum())}, "
          f"sadece İstanbul bitirdi={int((~can_fin & ist_fin).sum())}, "
          f"ikisi de bitirmedi={int((~can_fin & ~ist_fin).sum())}")
    if merged["gender_can"].notna().any():
        vc = merged["gender_can"].value_counts().reindex(["M", "F"], fill_value=0)
        vc.index = ["  Erkek", "  Kadın"]
        print(vc.to_string())

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.drop(columns=["bib_canakkale", "bib_istanbul"]).to_csv(COMMON_CSV, index=False, encoding="utf-8-sig")

    if show_list:
        show_cols = ["full_name_canakkale", "gender", "birth_year", "status_canakkale",
                     "time_canakkale", "status_istanbul", "time_istanbul",
                     "pace_canakkale_s100m", "pace_istanbul_s100m"]
        print(bar)
        print(f"ORTAKLAR ({len(out)} kişi) - tam liste:")
        with pd.option_context("display.max_rows", None, "display.width", 200,
                               "display.colheader_justify", "left"):
            print(out[show_cols].round(2).to_string(index=False))

    print(bar)
    print(f"Ortaklar listesi kaydedildi: {COMMON_CSV}")
    return COMMON_CSV

def main():
    parser = argparse.ArgumentParser(
        description="2026 Çanakkale ve İstanbul açık su yarışlarının ortak "
                    "yarışmacılarını çıkarır ve 2026/output/common_2026_dataset.csv "
                    "olarak kaydeder. (Grafikler: common_2026_charts.py)")
    parser.add_argument("--list", action="store_true",
                        help="ortakların tamamını konsola yaz")
    args = parser.parse_args()
    run(show_list=args.list)

if __name__ == "__main__":
    main()