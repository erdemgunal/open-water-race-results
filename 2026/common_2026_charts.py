from __future__ import annotations

"""
Çıktılar:
  2026/output/canakkale_vs_istanbul_common_pace.png -> tempo korelasyon grafiği
     (sahibin noktası bib 230 / bib 1831 - Hakkı Erdem Günal, M, 2004 -
     koyu kalın mavi nokta ile vurgulanır)
  2026/output/age_group_kruskal_wallis.png  -> yaş grubu x tempo + K-W testi

Veri, common_2026_dataset modülündeki load_common() ile HAM datasetlerden
yeniden kurulur; yani önce common_2026_dataset.py çalıştırılması gerekmez
(common_2026_dataset.csv bu grafiklerin girdisi değildir).

Not: Mesafeler (5 km vs 6.5 km) farklı olduğundan korelasyon için tempo
sütunlarını (pace_*_s100m) kullanın.

Kullanım:
  python3 common_2026_charts.py         # grafikleri üretir (kaydeder)
  python3 common_2026_charts.py --show  # grafiği pencere olarak aç (kaydetmez)
"""

import argparse
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib

if "--show" not in sys.argv:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
from matplotlib.patches import Patch

from common_2026_dataset import load_common

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "output"
CHART_PNG = OUT_DIR / "canakkale_vs_istanbul_common_pace.png"
KW_CHART_PNG = OUT_DIR / "age_group_kruskal_wallis.png"

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

def _finished_common(out):
    """Her iki yarışı da bitiren, tempo sütunları geçerli ortakları filtreler."""
    fin = out.dropna(subset=["pace_canakkale_s100m", "pace_istanbul_s100m"])
    fin = fin[fin["pace_canakkale_s100m"] > 0]
    fin = fin[fin["pace_istanbul_s100m"] > 0]
    return fin

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

def _age_group_analysis(fin, show):
    """Yaş grupları arasında tempo farkını Kruskal-Wallis H ile test eder

    Cinsiyete göre katmanlar (yaş kategorileri M/F ayrıdır) ve her yarış için ayrı ayrı H testi yapar. Konsola özet tablosunu basar ve yaş grubu x tempo kutu grafiğini üretir (age_group_kruskal_wallis.png).
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

def run(show):
    d = load_common()
    can_cfg, ist_cfg = d["can_cfg"], d["ist_cfg"]
    out = d["out"]
    fin = _finished_common(out)

    bar = "=" * 66
    print(bar)
    print("2026 ORTAK YARIŞMACI GRAFİKLERİ - " + can_cfg.name + " / " + ist_cfg.name)
    print(f"{can_cfg.name}: {len(d['can_raw'])} kayıtlı  ({can_cfg.distance_m:g} m)")
    print(f"{ist_cfg.name}: {len(d['ist_raw'])} kayıtlı  ({ist_cfg.distance_m:g} m)")
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
        print(f"      doğrusal uyum: İstanbul tempo = {slope:.2f} x "
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

    _age_group_analysis(fin, show=show)

    if len(fin) >= 2:
        _save_chart(fin, can_cfg, ist_cfg, show)
    else:
        print(bar)
        print("Tempo grafiği atlandı: ikisini de bitiren yeterli ortak yok.")

def main():
    parser = argparse.ArgumentParser(
        description="2026 Çanakkale / İstanbul ortak yarışmacılarının tempo "
                    "korelasyon (canakkale_vs_istanbul_common_pace.png) ve "
                    "yaş grubu x tempo (age_group_kruskal_wallis.png) "
                    "grafiklerini üretir.")
    parser.add_argument("--show", action="store_true",
                        help="grafiği pencere olarak aç (kaydetmez)")
    args = parser.parse_args()
    run(show=args.show)

if __name__ == "__main__":
    main()