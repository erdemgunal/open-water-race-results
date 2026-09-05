from __future__ import annotations

"""
Çıktılar:
  2026/output/common_2026_dataset.csv   -> ortak yarışmacılar (yan yana)
  2026/output/canakkale_vs_istanbul_common_pace.png -> tempo korelasyon grafiği
     (sahibin noktası bib 230 / bib 1831 - Hakkı Erdem Günal, M, 2004 -
     koyu kalın mavi nokta ile vurgulanır)
  2026/output/age_group_kruskal_wallis.png  -> yaş grubu × tempo + K-W testi

Not: time_gap_seconds / time_gap_percent sütunları HAM bitiş süresi farkıdır;
mesafeler (5 km vs 6.5 km) farklı olduğundan korelasyon için tempo sütunlarını
(pace_*_s100m) kullanın.

Kullanım:
  python3 common_2026.py            # özet + CSV (+ grafik)
  python3 common_2026.py --list     # ortakların tamamını konsola da yazar
  python3 common_2026.py --no-chart # grafik üretme
  python3 common_2026.py --show     # grafiği pencere olarak aç (kaydetmez)
"""

import argparse
import importlib.util
import math
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib

if "--show" not in sys.argv:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
from matplotlib.patches import Patch

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

CANAKKALE_CSV = BASE_DIR / "canakkale" / "raceresult_data" / "canakkale_2026_dataset.csv"
ISTANBUL_CSV = BASE_DIR / "istanbul" / "raceresult_data" / "bogazici_38_dataset.csv"
OUT_DIR = BASE_DIR / "output"
COMMON_CSV = OUT_DIR / "common_2026_dataset.csv"
CHART_PNG = OUT_DIR / "canakkale_vs_istanbul_common_pace.png"
KW_CHART_PNG = OUT_DIR / "age_group_kruskal_wallis.png"

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

# --------------------------------------------------------------------------
# istatistik yardımcıları
# --------------------------------------------------------------------------

def _p_two_sided(r, n):
    """H0: gerçek korelasyon = 0 için iki kuyruklu yaklaşık p-değeri.

    t = r * sqrt((n - 2) / (1 - r^2))  büyük n'de yaklaşık standart normaldir.
    scipy bağımlılığı olmasın diye normal CDF (erfc) ile hesaplanır.
    """
    if n <= 3 or not -1.0 < r < 1.0:
        return float("nan")
    t = r * math.sqrt((n - 2) / (1.0 - r * r))
    return math.erfc(abs(t) / math.sqrt(2.0))

def _pearson_ci95(r, n):
    """Pearson r için Fisher z dönüşümüyle %95 güven aralığı."""
    if n <= 3 or not -1.0 < r < 1.0:
        return float("nan"), float("nan")
    z = math.atanh(r)
    se = 1.0 / math.sqrt(n - 3)
    return math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)

def _fmt_p(p):
    if p != p:
        return "n/a"
    return "< 0.0001" if p < 0.0001 else f"{p:.4f}"

def age_band_of(value):
    """Age_group etiketinden yaş bandını çıkarır.

    'Male 19-24' ve 'Male B(19-24)' -> '19-24''Male 70+' -> '70+'.
    """
    s = "" if value is None or pd.isna(value) else str(value)
    m = re.search(r"\(([^()]*)\)", s)
    inner = m.group(1) if m else s
    mm = re.search(r"(\d{1,2}\s*[-–]\s*\d{1,2}|\d{1,2}\s*\+)", inner)
    return mm.group(1).replace(" ", "") if mm else inner.strip()

def band_sort_key(band):
    """Yaş bandını sıralamak için: '19-24' -> 19, '70+' -> 70."""
    m = re.match(r"\s*(\d{1,2})", str(band))
    return int(m.group(1)) if m else 999

def _chi_square_sf(x, df):
    """Ki-kare (df) dağılımının üst kuyruk olasılığı P(X > x).

    df/2 şeklindeki serbestlik derecesiyle eksik gama oranı Q(a, x/2)'ye
    eşittirscipy'siz olarak seri + sürekli kesir (gser/gcf) ile hesaplanır.
    """
    if df <= 0:
        return float("nan")
    if x <= 0.0:
        return 1.0
    a = df / 2.0
    x2 = x / 2.0
    if x2 < a + 1.0:
        p = _gamma_p_series(a, x2)
        return max(0.0, min(1.0, 1.0 - p))
    return max(0.0, min(1.0, _gamma_q_cf(a, x2)))

def _gamma_p_series(a, x):
    """Alt eksik gama oranı P(a, x) - x < a+1 için seri açılımı."""
    if x <= 0.0:
        return 0.0
    ap, s, d = a, 1.0 / a, 1.0 / a
    for _ in range(200):
        ap += 1.0
        d *= x / ap
        s += d
        if abs(d) < abs(s) * 1e-14:
            break
    return s * math.exp(-x + a * math.log(x) - math.lgamma(a))

def _gamma_q_cf(a, x):
    """Üst eksik gama oranı Q(a, x) - x >= a+1 için Lentz sürekli kesri."""
    eps, fpmin = 3e-14, 1e-300
    b = x + 1.0 - a
    c = 1.0 / fpmin
    d = 1.0 / b
    h = d
    for i in range(1, 200):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < fpmin:
            d = fpmin
        c = b + an / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        dl = d * c
        h *= dl
        if abs(dl - 1.0) < eps:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h

def _kruskal_wallis(groups):
    """Kruskal-Wallis H testi (bağ/ties düzeltmeli).

    groups: her biri bir grup için değerler içeren liste/array'ler.
    Dönüş: (H, serbestlik derecesi = k-1, üst kuyruk p-değeri).
    """
    cleaned = [np.asarray(g, dtype=float) for g in groups]
    cleaned = [g[~np.isnan(g)] for g in cleaned]
    cleaned = [g for g in cleaned if g.size]
    k = len(cleaned)
    n = int(sum(len(g) for g in cleaned))
    if k < 2 or n < 3:
        return float("nan"), k - 1, float("nan")

    pooled = pd.Series(np.concatenate(cleaned))
    ranks = pooled.rank(method="average").to_numpy()

    start = 0
    h = 0.0
    for g in cleaned:
        ni = g.size
        ri = float(ranks[start:start + ni].sum())
        h += ri * ri / ni
        start += ni
    h = 12.0 / (n * (n + 1.0)) * h - 3.0 * (n + 1.0)

    # Bağ (ties) düzeltmesi: h /= (1 - Σ(t^3-t) / (n³-n))
    counts = pooled.value_counts().to_numpy()
    tie_corr = 1.0 - float(np.sum(counts ** 3 - counts)) / (n ** 3 - n)
    if tie_corr > 0:
        h /= tie_corr

    dfree = k - 1
    return float(h), dfree, _chi_square_sf(h, dfree)

def run(show_list, make_chart, show):
    can_cfg = load_event("canakkale")
    ist_cfg = load_event("istanbul")

    can = add_match_key(read_dataset(CANAKKALE_CSV))
    ist = add_match_key(read_dataset(ISTANBUL_CSV))

    bar = "=" * 66
    print(bar)
    print("2026 ORTAK YARIŞMACILAR - " + can_cfg.name + " / " + ist_cfg.name)
    print(bar)
    print(f"{can_cfg.name}: {len(can)} kayıtlı  ({can_cfg.distance_m:g} m)")
    print(f"{ist_cfg.name}: {len(ist)} kayıtlı  ({ist_cfg.distance_m:g} m)")

    # ayni kisinin bir yarista birden fazla kaydi olursa ilkini al
    for label, df in (("Çanakkale", can), ("İstanbul", ist)):
        dups = int(df["_match_key"].duplicated().sum())
        if dups:
            print(f"  !! {label}: {dups} kopya anahtar var, ilk kayıt tutuluyor.")

    can = can.drop_duplicates("_match_key", keep="first")
    ist = ist.drop_duplicates("_match_key", keep="first")

    merged = can.merge(ist, on="_match_key", how="inner", suffixes=("_can", "_ist"))
    merged = merged.reset_index(drop=True)

    n = len(merged)
    print(bar)
    print(f"Ortak kayıtlı (iki yarışta da): {n}")
    if n:
        print(f"  Çanakkale'nin %{100.0 * n / len(can):.1f}'i "
              f"İstanbul'a da katılmış")
        print(f"  İstanbul'un %{100.0 * n / len(ist):.1f}'i "
              f"Çanakkale'ye de katılmış")

    # Cinsiyet / ülke tutarlılığını raporla.
    for col in ("gender", "nation", "birth_year"):
        mism = int((merged[f"{col}_can"].astype(str) != merged[f"{col}_ist"].astype(str)).sum())
        if mism:
            print(f"  !! {col} uyuşmazlığı (aynı anahtar, farklı değer): {mism}")

    # Status çapraz tablosu.
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

    # ----- çıktı tablosunu kur -----
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

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.drop(columns=["bib_canakkale", "bib_istanbul"]).to_csv(COMMON_CSV, index=False, encoding="utf-8-sig")

    fin = out.dropna(subset=["pace_canakkale_s100m", "pace_istanbul_s100m"])
    fin = fin[fin["pace_canakkale_s100m"] > 0]
    fin = fin[fin["pace_istanbul_s100m"] > 0]

    print(bar)
    print("İSTATİSTİKSEL ÖZET - her iki yarışı da bitiren ortaklar")
    print(f"  örneklem  n = {len(fin)}")
    if len(fin) >= 2:
        x = fin["pace_canakkale_s100m"].to_numpy(float)
        y = fin["pace_istanbul_s100m"].to_numpy(float)
        pear = float(np.corrcoef(x, y)[0, 1])

        # pace ranki yaris ici resmi genel siralamayla (overall_rank) aynı sirayi verdigi icin bu deger "rank consistency" olcusudur
        spear = float(fin["pace_canakkale_s100m"].rank().corr(fin["pace_istanbul_s100m"].rank(), method="pearson"))
        r2 = pear ** 2
        lo, hi = _pearson_ci95(pear, len(fin))
        slope, intercept = np.polyfit(x, y, 1)
        can_med = float(np.median(x))
        ist_med = float(np.median(y))

        print()
        print("  Pacing linearity  (Pearson) - tempo ilişkisinin doğrusallığı")
        print(f"      r  = {pear:.3f}   R² = {r2:.3f}   "
              f"%95 GA [{lo:.3f}, {hi:.3f}]   "
              f"p {_fmt_p(_p_two_sided(pear, len(fin)))}")
        print(f"      doğrusal uyum: İstanbul tempo = {slope:.2f} × "
              f"Çanakkale tempo {intercept:+.1f}  (sn/100m)")
        print()
        print("  Rank consistency  (Spearman) - sıralama tutarlılığı")
        print(f"      ρ = {spear:.3f}   p {_fmt_p(_p_two_sided(spear, len(fin)))}")
        print(f"      (pace sıralaması = yarışın resmî genel sıralaması"
              f"n = {len(fin)})")
        print()
        print(f"  medyan tempo  Çanakkale {can_med:.1f} sn/100m, "
              f"İstanbul {ist_med:.1f} sn/100m "
              f"(fark {ist_med - can_med:+.1f} sn/100m)")

    _age_group_analysis(fin, make_chart=make_chart, show=show)

    if show_list:
        show_cols = ["full_name_canakkale", "gender", "birth_year", "status_canakkale", "time_canakkale", "status_istanbul", "time_istanbul", "pace_canakkale_s100m", "pace_istanbul_s100m"]
        print(bar)
        print(f"ORTAKLAR ({len(out)} kişi) - tam liste:")
        with pd.option_context("display.max_rows", None, "display.width", 200, "display.colheader_justify", "left"):
            print(out[show_cols].round(2).to_string(index=False))

    if make_chart and len(fin) >= 2:
        _save_chart(fin, can_cfg, ist_cfg, show)
    elif make_chart:
        print(bar)
        print("Grafik atlandı: ikisini de bitiren yeterli ortak yok.")

    print(bar)
    print(f"Ortaklar listesi kaydedildi: {COMMON_CSV}")
    return COMMON_CSV

def _find_highlight_row(fin, can_cfg, ist_cfg):
    if fin is None or fin.empty:
        return None
    if ("bib_canakkale" not in fin.columns or "bib_istanbul" not in fin.columns):
        return None
    if can_cfg.default_bib is None or ist_cfg.default_bib is None:
        return None
    can_bib = str(int(can_cfg.default_bib))
    ist_bib = str(int(ist_cfg.default_bib))
    mask = ((fin["bib_canakkale"].astype(str).str.strip() == can_bib) & (fin["bib_istanbul"].astype(str).str.strip() == ist_bib))
    if not mask.any():
        return None
    return fin.loc[mask].iloc[0]

def _save_chart(fin, can_cfg, ist_cfg, show):
    x = fin["pace_canakkale_s100m"].to_numpy(float)
    y = fin["pace_istanbul_s100m"].to_numpy(float)
    pear = float(np.corrcoef(x, y)[0, 1])
    r2 = pear ** 2

    spear = float(fin["pace_canakkale_s100m"].rank().corr(
        fin["pace_istanbul_s100m"].rank(), method="pearson"))

    fig, ax = plt.subplots(figsize=(8.2, 7.0))
    colors = {"M": "#4C72B0", "F": "#C44E52", "O": "#55A868"}
    for g, grp in fin.groupby(fin["gender"].fillna("O")):
        ax.scatter(grp["pace_canakkale_s100m"], grp["pace_istanbul_s100m"], s=22, alpha=0.55, edgecolors="none", color=colors.get(g, "#55A868"), label={"M": "Men", "F": "Women"}.get(g, g))

    lim = (min(x.min(), y.min()) - 5, max(x.max(), y.max()) + 5)
    ax.plot(lim, lim, ":", color="gray", lw=1.2,
            label="equal pace (y = x)")
    if len(fin) >= 2:
        b, a = np.polyfit(x, y, 1)
        xs = np.linspace(*lim, 100)
        ax.plot(xs, a + b * xs, "-", color="k", lw=1.4, label=f"linear fit  y = {b:.2f}x {a:+.1f}   " f"(R² = {r2:.2f})")

    hl = _find_highlight_row(fin, can_cfg, ist_cfg)
    if hl is not None:
        hx = float(hl["pace_canakkale_s100m"])
        hy = float(hl["pace_istanbul_s100m"])
        ax.scatter([hx], [hy], s=95, color="#00008B", edgecolors="none", alpha=1.0, zorder=7)
        print(f"  Grafikte koyu kalın mavi vurgulanan: "
              f"{hl['full_name_canakkale'] or hl['full_name_istanbul']} "
              f"(Çanakkale bib {int(can_cfg.default_bib)}, "
              f"İstanbul bib {int(ist_cfg.default_bib)})")

    stats = [f"n = {len(fin)}  (finished both races)",
             f"Pacing linearity  - Pearson  r = {pear:.3f}   (R² = {r2:.2f})",
             f"Rank consistency  - Spearman ρ = {spear:.3f}",
             f"median pace: Çanakkale {np.median(x):.1f} s/100m, "
             f"İstanbul {np.median(y):.1f} s/100m"]
    ax.text(0.97, 0.04, "\n".join(stats), transform=ax.transAxes, ha="right", va="bottom", fontsize=9, bbox=dict(boxstyle="round", facecolor="#F5F8FB", edgecolor="#4C72B0", alpha=0.95))

    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel(f"Çanakkale pace (s/100m) - {can_cfg.distance_m:g} m")
    ax.set_ylabel(f"İstanbul pace (s/100m) - {ist_cfg.distance_m:g} m")
    ax.set_title("2026 common athletes - pace relationship\n Pearson = pacing linearity · Spearman = rank consistency\n")
    ax.legend(loc="upper left", frameon=True)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if show:
        plt.show()
    else:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        fig.savefig(CHART_PNG, dpi=150, bbox_inches="tight")
        print(f"Grafik kaydedildi: {CHART_PNG}")
    plt.close(fig)

# --------------------------------------------------------------------------
# yaş grupları - Kruskal-Wallis
# --------------------------------------------------------------------------

def _age_group_analysis(fin, make_chart, show):
    """Yaş grupları arasında tempo farkını Kruskal-Wallis H ile test eder.

    Cinsiyete göre katmanlar (yaş kategorileri M/F ayrıdır) ve her yarış
    için ayrı ayrı H testi yapar. Konsola özet tablosunu basar, istenirse
    kutu grafiğini üretir.
    """
    bar = "=" * 66
    if fin is None or fin.empty:
        return
    df = fin.copy()
    df["band"] = df["age_group_canakkale"].map(age_band_of)
    empty = df["band"].map(lambda b: (b or "").strip() == "")
    if empty.any():
        df.loc[empty, "band"] = df.loc[empty, "age_group_istanbul"].map(age_band_of)
    df = df[df["band"].map(lambda b: (b or "").strip() != "")].copy()
    if df.empty:
        return

    print(bar)
    print("YAŞ GRUPLARI ARASI FARK - Kruskal-Wallis H testi")
    print("  H0: yaş gruplarının tempo (sn/100m) dağılımları aynı "
          "(p < 0.05 → gruplar arasında fark var).")
    print("  Cinsiyete göre ayrı analiz (yaş kategorileri M/F ayrıdır)"
          "en az 2 kişilik gruplar test edilir.")

    testable = 0
    for gkey, glabel in (("M", "Erkek"), ("F", "Kadın")):
        sub = df[df["gender"] == gkey]
        if len(sub) < 3:
            continue
        bands = sorted(sub["band"].unique(), key=band_sort_key)
        print(f"\n{glabel} (n = {len(sub)})")
        rows = []
        for b in bands:
            d = sub[sub["band"] == b]
            rows.append([b, len(d), float(d["pace_canakkale_s100m"].median()), float(d["pace_istanbul_s100m"].median())])
        print(pd.DataFrame(rows, columns=["yaş grubu", "n", "Çanakkale", "İstanbul (sn/100m)"]).round(1).to_string(index=False))

        for rkey, rlabel in (("canakkale", "Çanakkale"), ("istanbul", "İstanbul")):
            col = f"pace_{rkey}_s100m"
            groups = [sub.loc[sub["band"] == b, col].to_numpy(float) for b in bands]
            groups = [g for g in groups if g.size >= 2]
            if len(groups) < 2:
                print(f"  {rlabel}: test için yeterli yaş grubu yok.")
                continue
            H, dfree, p = _kruskal_wallis(groups)
            k = len(groups)
            n_used = int(sum(len(g) for g in groups))
            print(f"  {rlabel}: H({dfree}) = {H:.2f}   p {_fmt_p(p)}   "
                  f"(k = {k} grup, n = {n_used})")
            testable += 1

    if make_chart:
        if testable >= 1:
            _save_agegroup_chart(df, show)
        else:
            print(bar)
            print("Yaş grubu grafiği atlandı: test edilebilir grup yok.")

def _save_agegroup_chart(df, show):
    races = (("canakkale", "Çanakkale"), ("istanbul", "İstanbul"))
    genders = (("M", "Men", "#4C72B0"), ("F", "Women", "#C44E52"))
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9.5))
    rng = np.random.default_rng(2026)

    all_pace = pd.concat([df["pace_canakkale_s100m"], df["pace_istanbul_s100m"]])
    ymin = float(all_pace.min()) - 5
    ymax = float(all_pace.max()) + 5

    for i, (rkey, rlabel) in enumerate(races):
        col = f"pace_{rkey}_s100m"
        for j, (gkey, glabel, color) in enumerate(genders):
            ax = axes[i][j]
            sub = df[df["gender"] == gkey]
            bands = sorted(sub["band"].unique(), key=band_sort_key)
            ticks, labels, groups = [], [], []
            for idx, b in enumerate(bands):
                vals = sub.loc[sub["band"] == b, col].to_numpy(float)
                vals = vals[~np.isnan(vals) & (vals > 0)]
                if vals.size == 0:
                    continue
                ticks.append(idx)
                labels.append(f"{b}\n(n={vals.size})")
                if vals.size >= 2:
                    bp = ax.boxplot([vals], positions=[idx], widths=0.55, patch_artist=True, showfliers=False, medianprops=dict(color="black", lw=1.6), whiskerprops=dict(color=color, lw=1.2), capprops=dict(color=color, lw=1.2))
                    bp["boxes"][0].set(facecolor=to_rgba(color, 0.35), edgecolor=color)
                    groups.append(vals)

                xj = idx + rng.uniform(-0.16, 0.16, size=vals.size)
                ax.scatter(xj, vals, s=14, color=to_rgba(color, 0.6), edgecolors="none", alpha=0.7, zorder=3)

            ax.set_xticks(ticks)
            ax.set_xticklabels(labels, fontsize=8)
            ax.set_ylim(ymin, ymax)
            ax.grid(True, axis="y", alpha=0.3)

            if len(groups) >= 2:
                H, dfree, p = _kruskal_wallis(groups)
                note = (f"n = {sum(len(g) for g in groups)}\n"
                        f"Kruskal-Wallis: H({dfree}) = {H:.1f}, "
                        f"p {_fmt_p(p)}")
            else:
                note = "not enough groups to test"
            ax.text(0.03, 0.97, note, transform=ax.transAxes, va="top",
                    ha="left", fontsize=9,
                    bbox=dict(boxstyle="round", facecolor="#F5F8FB",
                              edgecolor=color, alpha=0.95))
            ax.set_title(f"{rlabel} - {glabel}", fontsize=11)
            if i == 1:
                ax.set_xlabel("age group")
            if j == 0:
                ax.set_ylabel("pace (s/100m)")

    fig.suptitle("2026 common athletes - pace by age group\n (box: IQR, line: medianKruskal-Wallis H test)", fontsize=13, y=0.99)
    fig.legend(handles=[Patch(facecolor="#4C72B0", alpha=0.7, label="Men"), Patch(facecolor="#C44E52", alpha=0.7, label="Women")], loc="lower center", ncol=2, frameon=True)
    fig.tight_layout(rect=(0, 0.045, 1, 0.95))

    if show:
        plt.show()
    else:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        fig.savefig(KW_CHART_PNG, dpi=150, bbox_inches="tight")
        print(f"Grafik kaydedildi: {KW_CHART_PNG}")
    plt.close(fig)

def main():
    parser = argparse.ArgumentParser(
        description="2026 Çanakkale ve İstanbul açık su yarışlarının ortak "
                    "yarışmacılarını çıkarırtempo korelasyonunu ve yaş "
                    "grupları arasındaki farkı (Kruskal-Wallis) özetler.")
    parser.add_argument("--list", action="store_true",
                        help="ortakların tamamını konsola yaz")
    parser.add_argument("--no-chart", action="store_true",
                        help="korelasyon grafiğini üretme")
    parser.add_argument("--show", action="store_true",
                        help="grafiği pencere olarak aç (kaydetmez)")
    args = parser.parse_args()
    run(show_list=args.list, make_chart=not args.no_chart, show=args.show)

if __name__ == "__main__":
    main()