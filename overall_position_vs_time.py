import argparse
import sys
from pathlib import Path

import pandas as pd

import matplotlib

if "--show" not in sys.argv:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

matplotlib.rcParams.update({
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linestyle": "--",
    "font.size": 12,
    "axes.titlesize": 17,
    "axes.labelsize": 14,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
    "legend.fontsize": 12,
    "legend.title_fontsize": 12,
})

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "output"

ISTANBUL_CSVS = {
    2022: BASE_DIR / "2022" / "istanbul" / "bogazici_34_dataset.csv",
    2023: BASE_DIR / "2023" / "istanbul" / "bogazici_35_dataset.csv",
    2024: BASE_DIR / "2024" / "istanbul" / "bogazici_36_dataset.csv",
    2025: BASE_DIR / "2025" / "istanbul" / "bogazici_37_dataset.csv",
    2026: BASE_DIR / "2026" / "istanbul" / "raceresult_data" / "bogazici_38_dataset.csv",
}

CHART_PNG = OUT_DIR / "overall_position_vs_time_by_sex.png"
CHART_CSV = OUT_DIR / "overall_position_vs_time_by_sex.csv"

GENDER_LABEL = {"Male": "Male", "M": "Male", "Female": "Female", "F": "Female"}

GENDER_COLORS = {"Male": "#1f77b4", "Female": "#d62728"}

def normalize_gender(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        s = ""
    else:
        s = str(value).strip()
    return GENDER_LABEL.get(s, s or "Unknown")

def load_year(year, path):
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]

    if year == 2026:
        gender = df["gender"].map(normalize_gender)
        position = pd.to_numeric(df["overall_rank"], errors="coerce")
        time_min = pd.to_numeric(df["swim_seconds"], errors="coerce") / 60.0
        status = df["status"].fillna("").astype(str).str.strip().str.upper()
    else:
        gender = df["Gender"].map(normalize_gender)
        position = pd.to_numeric(df["Overall Position"], errors="coerce")
        time_min = pd.to_numeric(df["Finish Time (min)"], errors="coerce")
        if "Status" in df.columns:
            status = df["Status"].fillna("").astype(str).str.strip().str.upper()
        else:
            status = pd.Series(["FINISHED"] * len(df), index=df.index)

    out = pd.DataFrame({
        "Year": year,
        "Sex": gender,
        "Overall Position": position,
        "Finish Time (min)": time_min,
    })

    finished = status == "FINISHED"
    valid_pos = out["Overall Position"].notna() & (out["Overall Position"] > 0)
    valid_time = out["Finish Time (min)"].notna() & (out["Finish Time (min)"] > 0)
    return out[finished & valid_pos & valid_time].reset_index(drop=True)

def build_table():
    frames = [load_year(year, path) for year, path in sorted(ISTANBUL_CSVS.items())]
    return pd.concat(frames, ignore_index=True)

def fmt_minutes(value, _pos):
    total_seconds = int(round(float(value) * 60))
    m, s = divmod(total_seconds, 60)
    return f"{m}:{s:02d}"

def plot(df, show):
    fig, ax = plt.subplots(figsize=(9, 7))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    for sex, color in GENDER_COLORS.items():
        sub = df[df["Sex"] == sex]
        ax.scatter(
            sub["Overall Position"],
            sub["Finish Time (min)"],
            s=8,
            alpha=0.30,
            color=color,
            edgecolors="none",
            label=sex,
            rasterized=True,
        )

    ax.set_xlabel("Overall Position")
    ax.set_ylabel("Finish Time (min:sec)")
    ax.yaxis.set_major_formatter(FuncFormatter(fmt_minutes))
    ax.set_title(
        "Overall Position vs Time by Sex\nİstanbul Boğaziçi 2022–2026",
        pad=12,
    )
    ax.set_axisbelow(True)
    ax.margins(x=0.01, y=0.02)

    # Tek lejant: cinsiyet (sol üst).
    ax.legend(title="Sex", frameon=True, loc="upper left")

    fig.tight_layout()

    if show:
        plt.show()
    else:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        fig.savefig(CHART_PNG, dpi=300, bbox_inches="tight", facecolor="white")
        print(f"Grafik kaydedildi: {CHART_PNG}")
    plt.close(fig)

def main():
    parser = argparse.ArgumentParser(
        description="İstanbul Boğaziçi yarışlarının (2022–2026) bitirenler için "
                    "Overall Position vs Time dağılımını cinsiyete göre renklendirir."
    )
    parser.add_argument("--show", action="store_true",
                        help="grafiği pencere olarak aç (kaydetmez)")
    args = parser.parse_args()

    df = build_table()

    bar = "=" * 66
    print(bar)
    print("İSTANBUL BOĞAZİÇİ YARIŞI — GENEL SIRA vs SÜRE (CİNSİYETE GÖRE)")
    print(bar)
    summary = (df.groupby(["Year", "Sex"], observed=True)["Overall Position"].count().unstack(fill_value=0))
    for col in ("Male", "Female"):
        if col not in summary.columns:
            summary[col] = 0
    summary["Total"] = summary["Male"] + summary["Female"]
    print(summary[["Male", "Female", "Total"]].to_string())
    print(bar)
    print(f"Toplam bitiren: {len(df):,}")
    print(bar)

    plot(df, show=args.show)

    if not args.show:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(CHART_CSV, index=False, encoding="utf-8-sig")
        print(f"Özet kaydedildi: {CHART_CSV}")

if __name__ == "__main__":
    main()