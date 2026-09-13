import argparse
import sys
from pathlib import Path

import pandas as pd

import matplotlib

if "--show" not in sys.argv:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt

matplotlib.rcParams.update({
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
})

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "output"

ISTANBUL_CSVS: dict[int, Path] = {
    2022: BASE_DIR / "2022" / "istanbul" / "bogazici_34_dataset.csv",
    2023: BASE_DIR / "2023" / "istanbul" / "bogazici_35_dataset.csv",
    2024: BASE_DIR / "2024" / "istanbul" / "bogazici_36_dataset.csv",
    2025: BASE_DIR / "2025" / "istanbul" / "bogazici_37_dataset.csv",
    2026: BASE_DIR / "2026" / "istanbul" / "raceresult_data" / "bogazici_38_dataset.csv",
}

CHART_PNG = OUT_DIR / "participation_over_years_by_gender.png"
CHART_CSV = OUT_DIR / "participation_over_years_by_gender.csv"

GENDER_LABEL = {"Male": "Male", "M": "Male", "Female": "Female", "F": "Female"}
GENDER_COLORS = {"Male": "#4C72B0", "Female": "#C44E52"}

def normalize_gender(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        s = ""
    else:
        s = str(value).strip()
    return GENDER_LABEL.get(s, s or "Unknown")

def count_gender(year, path):
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]

    gender_col = "gender" if "gender" in df.columns else "Gender"
    counts = df[gender_col].map(normalize_gender).value_counts()

    return {
        "Year": year,
        "Male": int(counts.get("Male", 0)),
        "Female": int(counts.get("Female", 0)),
        "Unknown": int(counts.get("Unknown", 0)),
    }

def build_table():
    rows = [count_gender(year, path) for year, path in sorted(ISTANBUL_CSVS.items())]
    df = pd.DataFrame(rows)
    df["Total"] = df["Male"] + df["Female"] + df["Unknown"]
    df["Female %"] = (100.0 * df["Female"] / df["Total"]).round(1)
    return df

def plot(df, show):
    years = df["Year"].to_numpy()
    male = df["Male"].to_numpy()
    female = df["Female"].to_numpy()

    fig, ax = plt.subplots(figsize=(9.0, 6.0))

    ax.stackplot(
        years,
        male,
        female,
        labels=("Male", "Female"),
        colors=(GENDER_COLORS["Male"], GENDER_COLORS["Female"]),
        alpha=0.85,
    )

    ax.set_xticks(list(years))
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of Participants")
    ax.set_title("Participation Over Years by Gender", fontsize=13)
    ax.legend(title="Gender", frameon=True)
    ax.set_axisbelow(True)
    ax.margins(y=0.08)

    fig.tight_layout()

    if show:
        plt.show()
    else:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        fig.savefig(CHART_PNG, dpi=150, bbox_inches="tight")
        print(f"Grafik kaydedildi: {CHART_PNG}")
    plt.close(fig)

def main():
    parser = argparse.ArgumentParser(
        description="İstanbul Boğaziçi yarışlarının yıllara göre cinsiyet bazında "
                    "katılım grafiğini üretir."
    )
    parser.add_argument("--show", action="store_true", help="grafiği pencere olarak aç (kaydetmez)")
    args = parser.parse_args()

    df = build_table()

    bar = "=" * 66
    print(bar)
    print("İSTANBUL BOĞAZİÇİ YARIŞI — YILLARA GÖRE CİNSİYET KATILIMI")
    print(bar)
    print(df.to_string(index=False))
    print(bar)

    plot(df, show=args.show)

    if not args.show:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(CHART_CSV, index=False, encoding="utf-8-sig")
        print(f"Özet kaydedildi: {CHART_CSV}")

if __name__ == "__main__":
    main()