from __future__ import annotations

"""
Charts analyzing the 2026 common-athlete data (5 km Çanakkale + 6.5 km
Bosphorus race) with first-order differential-equation applications from
Ross Chapter 3.  Companion to common_2026_charts.py.

Outputs:
  2026/output/de_mechanics_newton_quadratic_drag.png  -> Section 3.2 Mechanics
      dv/dt = a - b v^2  (Newton + quadratic water drag, terminal speed v_inf)
      - analytic solution verified against Euler / RK4 numeric solutions
      - (a, b) calibration from the two race points of a prototype athlete;
        the s(t) curve passes through the observed (T1,S1) and (T2,S2)
      - regime chart of all common athletes' (v1, v2) points vs the band that
        the rest-start quadratic-drag model can explain (gap %14-30)
      - fitted terminal speed v_inf for the athletes inside the model band

  2026/output/de_rate_exponential_2026.png            -> Section 3.3 Rate
      dv/dS = -a v   =>   v_bar(S) = v0 e^{-a S}   =>   T(S) = (S/v0) e^{aS}
      - per-athlete coefficient a (per km) from the two distances S1, S2
      - distribution of a by gender / age group
      - 6.5 km time prediction: constant-pace model (M0) vs exponential-rate
        model (M1); RMSE / MAPE and error-vs-speed analysis

Input: 2026/output/common_2026_dataset.csv (athletes who finished both races)
Usage:
  python3 common_2026_de_charts.py          # generate and save the charts
  python3 common_2026_de_charts.py --show   # open the charts in windows

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

matplotlib.rcParams.update({"axes.grid": True, "grid.alpha": 0.3, "grid.linestyle": "--"})

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "output"
DATA_CSV = OUT_DIR / "common_2026_dataset.csv"

CHART_MECH = OUT_DIR / "de_mechanics_newton_quadratic_drag.png"
CHART_RATE = OUT_DIR / "de_rate_exponential_2026.png"

# Yüzme mesafeleri (m)
S1 = 5000.0          # Çanakkale
S2 = 6500.0          # İstanbul (Bosphorus)
DS = S2 - S1         # ek mesafe 1500 m
RSTAR = S2 / S1      # sabit tempoda süre oranı = 1.3

COL_M = "#4C72B0"
COL_F = "#C44E52"

# ---------------------------------------------------------------------------
# Veri yükleme ve türetilmiş büyüklükler
# ---------------------------------------------------------------------------

def load_common():
    """common_2026_dataset.csv okur iki yarışı da geçerli tempoyla bitiren ortakların yüzme geometrisi (S,T,v,pace) sütunlarını ekler."""
    df = pd.read_csv(DATA_CSV, encoding="utf-8-sig")
    num_cols = ["swim_seconds_canakkale", "swim_seconds_istanbul", "pace_canakkale_s100m", "pace_istanbul_s100m", "time_gap_seconds", "time_gap_percent"]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    fin = df.dropna(subset=["swim_seconds_canakkale", "swim_seconds_istanbul", "pace_canakkale_s100m", "pace_istanbul_s100m"]).copy()
    fin = fin[(fin.swim_seconds_canakkale > 0) & (fin.swim_seconds_istanbul > 0)]

    fin["name"] = fin["full_name_canakkale"].fillna(
        fin["full_name_istanbul"]).astype(str).str.strip()
    fin["gender"] = fin["gender"].fillna("").astype(str).str.strip().str.upper()
    fin["T1"] = fin["swim_seconds_canakkale"].to_numpy(float)   # 5 km süresi (s)
    fin["T2"] = fin["swim_seconds_istanbul"].to_numpy(float)    # 6.5 km süresi (s)
    fin["v1"] = S1 / fin["T1"]                                  # ort. hız 5 km (m/s)
    fin["v2"] = S2 / fin["T2"]                                  # ort. hız 6.5 km (m/s)
    fin["pace1"] = fin["pace_canakkale_s100m"].to_numpy(float)  # sn/100m
    fin["pace2"] = fin["pace_istanbul_s100m"].to_numpy(float)
    fin["gap_pct"] = (fin["T2"] - fin["T1"]) / fin["T1"] * 100.0

    # Sabit tempoda T2 = 1.3*T1 olurdu (boşluk %30) gözlenen boşluk: %30'dan az  => 6.5 km'de metre başına daha hızlı ort. tempo %30'dan çok => 6.5 km'de daha yavaş ort. tempo (yorgunluk benzeri)
    fin["q"] = fin["v2"] / fin["v1"]

    # Üstel oran modeli için sporcu bazında katsayı:
    #   v_bar(S) = v0 e^{-a S}  =>  a = ln(v1/v2)/(S2-S1)  (1/m)
    # km başına: a_km = ln(v1/v2) / 1.5  (ΔS = 1.5 km)
    fin["alpha_km"] = np.log(fin["v1"] / fin["v2"]) / ((S2 - S1) / 1000.0)
    return fin.reset_index(drop=True)

# ---------------------------------------------------------------------------
# Yaş grubu yardımcıları
# ---------------------------------------------------------------------------

def age_band_of(value):
    """'Male 19-24' / 'Male B(19-24)' -> '19-24' 'Male 70+' -> '70+'."""
    s = "" if value is None or pd.isna(value) else str(value)
    m = re.search(r"\(([^()]*)\)", s)
    inner = m.group(1) if m else s
    mm = re.search(r"(\d{1,2}\s*[-–]\s*\d{1,2}|\d{1,2}\s*\+)", inner)
    return mm.group(1).replace(" ", "") if mm else inner.strip()

def band_low(band):
    m = re.match(r"\s*(\d{1,2})", str(band))
    return int(m.group(1)) if m else 999

def broad_age(band):
    """3 geniş kategoride topla: '<30', '30-44', '45+'."""
    lo = band_low(band)
    if lo < 30:
        return "<30"
    if lo <= 44:
        return "30-44"
    return "45+"

BROAD_ORDER = ["<30", "30-44", "45+"]

def add_age_cols(fin):
    fin = fin.copy()
    band = fin["age_group_canakkale"].map(age_band_of)
    empty = band.map(lambda b: (b or "").strip() == "")
    if empty.any():
        band.loc[empty] = fin.loc[empty, "age_group_istanbul"].map(age_band_of)
    fin["band"] = band
    fin["broad"] = fin["band"].map(broad_age)
    return fin

# ---------------------------------------------------------------------------
# Küçük istatistik yardımcıları (scipy'siz)
# ---------------------------------------------------------------------------

def _fmt_p(p):
    if p != p:
        return "n/a"
    return "< 0.0001" if p < 0.0001 else f"{p:.4f}"

def _chi2_sf(x, df):
    """Ki-kare(df) üst kuyruk olasılığı P(X > x)"""
    if df <= 0 or x <= 0.0:
        return 1.0 if x <= 0.0 else float("nan")
    a = df / 2.0
    x2 = x / 2.0

    def gser(aa, xx):
        ap, s, d = aa, 1.0 / aa, 1.0 / aa
        for _ in range(300):
            ap += 1.0
            d *= xx / ap
            s += d
            if abs(d) < abs(s) * 1e-14:
                break
        return s * math.exp(-xx + aa * math.log(xx) - math.lgamma(aa))

    def gcf(aa, xx):
        eps, fpmin = 3e-14, 1e-300
        b = xx + 1.0 - aa
        c = 1.0 / fpmin
        d = 1.0 / b
        h = d
        for i in range(300):
            an = -(i + 1) * (i + 1 - aa)
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
        return math.exp(-xx + aa * math.log(xx) - math.lgamma(aa)) * h
    p = gser(a, x2) if x2 < a + 1.0 else gcf(a, x2)
    if x2 < a + 1.0:
        p = 1.0 - p
    return max(0.0, min(1.0, p))

def kruskal_wallis(groups):
    """Kruskal-Wallis H bağ (ties) düzeltmeli. -> (H, df, p)"""
    cleaned = [np.asarray(g, dtype=float) for g in groups]
    cleaned = [g[~np.isnan(g)] for g in cleaned]
    cleaned = [g for g in cleaned if g.size]
    k = len(cleaned)
    n = int(sum(len(g) for g in cleaned))
    if k < 2 or n < 3:
        return float("nan"), k - 1, float("nan")
    pooled = pd.Series(np.concatenate(cleaned))
    ranks = pooled.rank(method="average").to_numpy()
    start, h = 0, 0.0
    for g in cleaned:
        ni = g.size
        h += (float(ranks[start:start + ni].sum()) ** 2) / ni
        start += ni
    h = 12.0 / (n * (n + 1.0)) * h - 3.0 * (n + 1.0)
    counts = pooled.value_counts().to_numpy()
    tie = 1.0 - float(np.sum(counts ** 3 - counts)) / (n ** 3 - n)
    if tie > 0:
        h /= tie
    return float(h), k - 1, _chi2_sf(h, k - 1)

# ---------------------------------------------------------------------------
# Bölüm 3.2 - Mechanics: dv/dt = a - b v^2  (Newton + kuadratik direnç)
# ---------------------------------------------------------------------------
# Yorum: Sürtünme kuvveti ~ v^2 varsayılırsa hareket denklemi (birim kütle) dv/dt = a - b v^2 ,  a = F/m (itme),  b = k/m (direnç katsayısı). v(0)=0 için analitik  çözüm:  v(t) = v_inf tanh(a t / v_inf), v_inf = sqrt(a/b) terminal (limit) hızdır ve konum: s(t) = (v_inf^2 / a) ln cosh(a t / v_inf) = (v_inf/c) ln cosh(c t), c = a/v_inf.  İki yarış toplam süresi (T1,T2) ve mesafesi (S1,S2) verildiğinde (v_inf, c) bu kapalı çözümle kalibre edilir.

def lncosh(x):
    """ln cosh(x) - küçük ve büyük x için sayısal olarak kararlı."""
    x = np.abs(np.asarray(x, dtype=float))
    small = x < 0.08
    out = np.empty_like(x)
    x2 = x[small] * x[small]
    out[small] = (x2 / 2.0 - x2 * x2 / 12.0 + x2 ** 3 / 45.0 - x2 ** 4 / 252.0)
    big = ~small
    if big.any():
        out[big] = x[big] - np.log(2.0) + np.log1p(np.exp(-2.0 * x[big]))
    return float(out) if out.ndim == 0 else out

def solve_mechanics_c(T1, T2):
    """v(0)=0 kuadratik-direnç modelinde c = a/v_inf kökünü bulur.

    ln cosh(c T2) / ln cosh(c T1) = S2/S1 = 1.3 denkleminin pozitif kökü. R(c) monoton azalır: c->0+ için (T2/T1)^2, c->oo için T2/T1. Dolayısıyla model ancak T2/T1 in (1.3, (T2/T1)^2 aralığı?) ... Yani boşluk %14.02 (balistik, sürtünmesiz) ile %30 (sabit tempo) arasında olan sporcularda anlamlı bir c>0 kökü vardır. Dönüş: c (1/s) veya uygun değilse None.
    """
    t2t1 = T2 / T1
    if not (t2t1 * t2t1 > RSTAR > t2t1):
        return None
    lo, hi = 1e-9, 1e-9
    # R(hi) < 1.3 olana dek hi'yi büyüt
    for _ in range(80):
        if lncosh(hi * T2) / lncosh(hi * T1) < RSTAR:
            break
        hi *= 2.0
    else:
        return None
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if lncosh(mid * T2) / lncosh(mid * T1) > RSTAR:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)

def fit_mechanics(T1, T2):
    """(T1,S1) ve (T2,S2) noktalarını birebir üreten (a,b,v_inf) parametreleri

    Dönüş dict: c, v_inf, a, b ya da None (bant dışı sporcu)
    """
    c = solve_mechanics_c(T1, T2)
    if c is None:
        return None
    lc1 = lncosh(c * T1)
    v_inf = c * S1 / lc1
    a = c * v_inf
    b = c / v_inf
    return {"c": c, "v_inf": v_inf, "a": a, "b": b}

def numeric_drag(a, b, t_end, dt, method="rk4"):
    """dv/dt = a - b v^2, v(0)=0, ds/dt = v DE'sini Euler/RK4 ile çözer

    Dönüş: (t, v, s) dizileri noktalar 0..t_end aralığında dt adımlı.
    """
    n = int(math.ceil(t_end / dt)) + 1
    t = np.linspace(0.0, n * dt, n)
    v = np.zeros(n)
    s = np.zeros(n)
    for i in range(n - 1):
        vv, h = v[i], dt
        if method == "euler":
            k1 = a - b * vv * vv
            v[i + 1] = vv + h * k1
        else:  # classical RK4
            def f(u):
                return a - b * u * u
            k1 = f(vv)
            k2 = f(vv + 0.5 * h * k1)
            k3 = f(vv + 0.5 * h * k2)
            k4 = f(vv + h * k3)
            v[i + 1] = vv + h / 6.0 * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        s[i + 1] = s[i] + h * v[i]
    return t, v, s

def analytic_drag(a, b, t):
    """v(0)=0, dv/dt=a-bv^2 analitik çözümü: v(t) ve s(t)."""
    v_inf = math.sqrt(a / b)
    c = a / v_inf
    v = v_inf * np.tanh(c * np.asarray(t, dtype=float))
    s = (v_inf / c) * np.array([lncosh(c * tt) for tt in t])
    return v, s

# ---------------------------------------------------------------------------
# Bölüm 3.3 - Rate / yorgunluk:  v(S) = v0 e^{-a S}  modeli
# ---------------------------------------------------------------------------
# Ortalama hızın mesafeyle değişimi birinci mertebe oran denklemi olarak modellenir: dv_bar/dS = -a v_bar => v_bar(S) = v0 e^{-a S} Her sporcuda iki örnek (S1 ve S2 mesafelerindeki ortalama hızlar) olduğu için per-athlete katsayı kapalı formda: a_i = ln(v1/v2)/(S2-S1) (a_i > 0 => v mesafeyle azalır = yorgunluk) Grup düzeyinde ortak eğim, per-athlete katsayıların ortalamasıdır. Tahmin protokolü (M1): sporcunun kendi v1'i sabitlenir grup ortalaması (LOO) a katsayısı 6.5 km'ye taşınır: v2_hat = v1 e^{-a_loo (S2-S1)}, T2_hat = S2 / v2_hat Karşılaştırma modeli M0 (sabit tempo): T2_hat = (S2/S1) T1 = 1.3 T1.

def add_rate_cols(fin, group_col="gender"):
    """Grup-bazlı LOO ortak a katsayısı ile 6.5 km süre tahminlerini ekler."""
    fin = fin.copy()
    fin["T2hat_m0"] = fin["T1"] * RSTAR            # sabit tempo (boşluk %30)
    fin["T2hat_m1"] = np.nan
    fin["a_loo_per_m"] = np.nan
    alpha_per_m = fin["alpha_km"].to_numpy() / 1000.0   # 1/m
    for _, idx in fin.groupby(group_col).groups.items():
        idx = np.asarray(idx)
        tot = alpha_per_m[idx].sum()
        n = idx.size
        for j in idx:
            ag = (tot - alpha_per_m[j]) / (n - 1) if n > 1 else alpha_per_m[j]
            fin.loc[j, "a_loo_per_m"] = ag
            v2hat = fin.loc[j, "v1"] * math.exp(-ag * DS)
            fin.loc[j, "T2hat_m1"] = S2 / v2hat
    for m in ("T2hat_m0", "T2hat_m1"):
        fin[f"err_{m}"] = (fin[m] - fin["T2"]) / fin["T2"] * 100.0   # % hata
    return fin

def rmse_map_metrics(pred_col, obs):
    rmse = float(np.sqrt(np.mean((pred_col - obs) ** 2)))
    mape = float(np.mean(np.abs((pred_col - obs) / obs)) * 100.0)
    return rmse, mape

def group_summary(df, val):
    """val sütununun cinsiyete göre n/ortanca/ortalama/standart sapması."""
    return df.groupby("gender")[val].agg(["count", "median", "mean", "std"]).round(4)

# ---------------------------------------------------------------------------
# Grafik 1: Bölüm 3.2 Mechanics - Newton + kuadratik direnç
# ---------------------------------------------------------------------------

def _choose_prototype(fin, feasible_mask, gender="M"):
    """Temsilci (prototype) sporcu seçimi.

    Tercih sırası: (1) veri setindeki 'sabit-tempo' bölgesinde kalibre edilebilen örnek isimler (önce Kaan Yalın Çullu), (2) değilse uyum yapılabilen sporcular arasında cinsiyet içi median q'ya en yakın olan.
    """
    names = ["Kaan Yalın Çullu", "Ögeday Samatlı", "Egor Tropeano"]
    cand = fin[feasible_mask].copy()
    for nm in names:
        hit = cand[cand["name"] == nm]
        if not hit.empty:
            return hit.iloc[0]
    if cand.empty:
        return fin.iloc[0]
    if (cand["gender"] == gender).any():
        cand = cand[cand["gender"] == gender]
    med_q = cand["q"].median()
    idx = (cand["q"] - med_q).abs().idxmin()
    return cand.loc[idx]

def _build_mechanics_figure(fin, show):
    feas = fin["mech_v_inf"].notna().to_numpy()
    n_feas = int(feas.sum())
    proto = _choose_prototype(fin, feas)

    fig, axes = plt.subplots(2, 2, figsize=(13.5, 11.0))
    ax = axes[0, 0]
    axS = axes[0, 1]
    axR = axes[1, 0]
    axV = axes[1, 1]

    # --- temsilci sporcu parametreleri ---
    p = fit_mechanics(float(proto["T1"]), float(proto["T2"]))
    v_inf, a, b, c = p["v_inf"], p["a"], p["b"], p["c"]
    t_dense = np.linspace(0.0, float(proto["T2"]), 1200)
    v_an, s_an = analytic_drag(a, b, t_dense)

    # Euler/RK4 için adım: yarış süresini ~24 parçaya böl
    dt = max(30.0, math.floor(float(proto["T2"]) / 24.0 / 10.0) * 10.0)
    t_e, v_e, s_e = numeric_drag(a, b, float(proto["T2"]), dt, method="euler")
    t_r, v_r, s_r = numeric_drag(a, b, float(proto["T2"]), dt, method="rk4")
    v_an_at_e = v_inf * np.tanh(c * t_e)
    rmse_e = float(np.sqrt(np.mean((v_e - v_an_at_e) ** 2)))
    rmse_r = float(np.sqrt(np.mean((v_r - v_an_at_e) ** 2)))

    # ---- (a) analitik vs sayısal çözümler ----
    ax.plot(t_dense, v_an, "-", color="#1f77b4", lw=2.2, label="analytic  $v(t)=v_\\infty\\tanh(at/v_\\infty)$")
    ax.plot(t_e, v_e, "x", ms=6, color="#d62728", alpha=0.85, label=f"Euler  ($\\Delta t={dt:.0f}$ s)")
    ax.plot(t_r, v_r, "o", ms=4, mfc="none", color="#2ca02c", label=f"RK4  ($\\Delta t={dt:.0f}$ s)")
    ax.axhline(v_inf, ls="--", lw=1, color="gray")
    ax.text(0.02, v_inf + 0.04 * max(1.0, v_inf), f"$v_\\infty$ = {v_inf:.2f} m/s", fontsize=9, color="gray")
    box = (f"{proto['name']}  ({proto['gender']}, {proto['band']})\n"
           f"$a$ = {a:.4f} m/s²,  $b$ = {b:.5f} 1/m\n"
           f"RMS error  Euler {rmse_e:.3f}  |  RK4 {rmse_r:.4f} m/s")
    ax.text(0.97, 0.03, box, transform=ax.transAxes, ha="right", va="bottom", fontsize=9, bbox=dict(boxstyle="round", facecolor="#F5F8FB", edgecolor="#1f77b4"))
    ax.set_xlabel("$t$ (s)")
    ax.set_ylabel("$v$ (m/s)")
    ax.set_title("(a)  Newton + quadratic drag:  "
                 "$\\mathrm{d}v/\\mathrm{d}t = a - b v^2$,  $v(0)=0$\n"
                 "analytic solution verified with Euler / RK4")
    ax.legend(loc="lower right", fontsize=8)

    # ---- (b) s(t) kalibrasyonu ----
    axS.plot(t_dense, s_an, "-", color="#1f77b4", lw=2.2, label="$s(t)=\\frac{v_\\infty}{c}\\,\\ln\\cosh(ct)$")
    axS.scatter([proto["T1"], proto["T2"]], [S1, S2], s=120, zorder=5, facecolor="white", edgecolor="black", linewidths=2, label="observed $(T_1,S_1)$ and $(T_2,S_2)$")
    for tx, sx, lab in ((proto["T1"], S1, "5 km"), (proto["T2"], S2, "6.5 km")):
        axS.annotate(f"{lab}: {tx:.0f} s", xy=(tx, sx), xytext=(tx - 0.12 * proto["T2"], sx - 900), fontsize=9,arrowprops=dict(arrowstyle="->", lw=0.8, color="black"))
    axS.axhline(S1, ls=":", lw=1, color="gray", alpha=0.8)
    axS.axhline(S2, ls=":", lw=1, color="gray", alpha=0.8)
    t95 = float(np.arctanh(0.95)) / c
    note = (f"fit: $v_\\infty$={v_inf:.2f} m/s,  $a$={a:.4f} m/s²,  "
            f"$b$={b:.5f} 1/m\n"
            f"$c=a/v_\\infty$={c:.4f} 1/s  95% of the terminal speed is reached in "
            f"{t95:.0f} s")
    axS.text(0.03, 0.97, note, transform=axS.transAxes, va="top", fontsize=9, bbox=dict(boxstyle="round", facecolor="#F5F8FB", edgecolor="#1f77b4"))
    axS.set_xlabel("$t$ (s)")
    axS.set_ylabel("$s$ (m)")
    axS.set_title("(b)  Calibrating $(a,b)$ from the two race points\n model passes through $(T_1,S_1)$ and $(T_2,S_2)$")
    axS.legend(loc="lower right", fontsize=8)
    axS.set_xlim(0, float(proto["T2"]) * 1.02)

    # ---- (c) veri bölgeleri: gözlemler modelin bandında mı? ----
    r_bal = math.sqrt(RSTAR)          # sürtünmesiz sınır oranı √1.3 ≈ 1.140
    x = fin["v1"].to_numpy()
    y = fin["v2"].to_numpy()
    lim = (min(x.min(), y.min()) * 0.94, max(x.max(), y.max()) * 1.05)
    grid = np.linspace(lim[0], lim[1], 60)
    for gkey, gcol, glab in (("M", COL_M, "Men"), ("F", COL_F, "Women")):
        m = fin["gender"] == gkey
        axR.scatter(x[m], y[m], s=22, alpha=0.6, edgecolors="none", color=gcol, label=glab)
    axR.fill_between(grid, grid, r_bal * grid, color="#55A868", alpha=0.16, label="rest-start quadratic-drag band\n ($v_2/v_1 \\in [1,\\sqrt{1.3}]$, gap %14-30)")
    axR.plot(grid, grid, "-", color="gray", lw=1.6, label="constant pace  ($v_2=v_1$, gap %30)")
    axR.plot(grid, r_bal * grid, "--", color="k", lw=1.4, label="frictionless limit  ($v_2=\\sqrt{1.3}\\,v_1$, gap≈%14)")
    n_fat = int((y < x * 0.999).sum())
    n_bal = int((y > r_bal * x * 1.001).sum())
    tb = ("$v_2/v_1$ regions (n = %d):\n"
          "  above the band (n = %d): speed boost — current / course effect\n"
          "  inside the band (n = %d): explained by the model, $(a,b)$ can be calibrated\n"
          "  below the band (n = %d): fatigue-like (%s)" %
          (len(fin), n_bal, n_feas, n_fat, "<1"))
    axR.text(0.03, 0.97, tb, transform=axR.transAxes, va="top", fontsize=9, bbox=dict(boxstyle="round", facecolor="#F5F8FB", edgecolor="#55A868"))
    axR.set_xlim(lim)
    axR.set_ylim(lim)
    axR.set_xlabel("Çanakkale mean speed $v_1$ (m/s)")
    axR.set_ylabel("Istanbul mean speed $v_2$ (m/s)")
    axR.set_title("(c)  Common athletes' $(v_1, v_2)$ points and model bands\n (the two races are on different days/courses: above the band is not fatigue on its own)")
    axR.legend(loc="lower right", fontsize=8)

    # ---- (d) uyum yapılabilenlerde terminal hız ----
    sub = fin[feas]
    med_ratio = float((sub["mech_v_inf"] / sub["v1"]).median())
    for gkey, gcol, glab in (("M", COL_M, "Men"), ("F", COL_F, "Women")):
        m = sub["gender"] == gkey
        axV.scatter(sub["v1"][m], sub["mech_v_inf"][m], s=26, alpha=0.7, edgecolors="none", color=gcol, label=f"{glab} (n={int(m.sum())})")
    axV.plot(grid, grid, "--", color="gray", lw=1.3, label="$v_\\infty = v_1$ (reference)")
    med_vm = sub.loc[sub["gender"] == "M", "mech_v_inf"].median()
    med_vf = sub.loc[sub["gender"] == "F", "mech_v_inf"].median()
    note2 = (f"fitted athletes: {n_feas}/{len(fin)}\n"
             f"median $v_\\infty/v_1$ = {med_ratio:.2f}\n"
             f"median $v_\\infty$:  M {med_vm:.2f}  |  "
             f"F {med_vf:.2f} m/s\n"
             f"($v_\\infty$ axis truncated at the 90th percentile: near the %14 gap\n"
             f" extreme values occur — frictionless limit)")
    axV.text(0.03, 0.97, note2, transform=axV.transAxes, va="top", fontsize=9, bbox=dict(boxstyle="round", facecolor="#F5F8FB", edgecolor="gray"))
    cap = float(np.quantile(sub["mech_v_inf"], 0.90))
    axV.set_xlim(lim)
    axV.set_ylim(lim[0], cap * 1.05)
    axV.set_xlabel("observed $v_1$ (m/s)")
    axV.set_ylabel("fitted terminal speed $v_\\infty$ (m/s)")
    axV.set_title("(d)  Terminal speeds from the quadratic-drag fits\n"
                  "(athletes in the valid model band)")
    axV.legend(loc="lower right", fontsize=8)

    fig.suptitle(
        "Section 3.2 – Problems in Mechanics   ·   2026 common athletes "
        "(5 km Çanakkale + 6.5 km Bosphorus)\n"
        "$m\\frac{\\mathrm{d}v}{\\mathrm{d}t}=F-kv^2$  "
        "$\\Rightarrow$  $\\frac{\\mathrm{d}v}{\\mathrm{d}t}=a-bv^2$,  "
        "$v_\\infty=\\sqrt{a/b}$   —   separable DE with numerical "
        "verification (preparation for Section 8)",
        fontsize=12.5, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return fig

# ---------------------------------------------------------------------------
# Grafik 2: Bölüm 3.3 Rate / yorgunluk - üstel oran modeli
# ---------------------------------------------------------------------------

def _gmean_serr(vals):
    lv = np.log(np.asarray(vals, dtype=float))
    return float(np.exp(lv.mean())), float(lv.std(ddof=1) / math.sqrt(lv.size))

def _build_rate_figure(fin, show):
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 11.0))
    axM = axes[0, 0]
    axA = axes[0, 1]
    axP = axes[1, 0]
    axE = axes[1, 1]

    # ---- (a) üstel oran modeli: geometrik-ortalama hızlar vs mesafe ----
    alpha_all = []
    for gkey, gcol, glab in (("M", COL_M, "Men"), ("F", COL_F, "Women")):
        sub = fin[fin["gender"] == gkey]
        if len(sub) < 2:
            continue
        gm1, se1 = _gmean_serr(sub["v1"])
        gm2, se2 = _gmean_serr(sub["v2"])
        a_mean = float(sub["alpha_km"].mean())          # 1/km
        yerr_lo = [gm1 - math.exp(math.log(gm1) - se1),
                   gm2 - math.exp(math.log(gm2) - se2)]
        yerr_hi = [math.exp(math.log(gm1) + se1) - gm1,
                   math.exp(math.log(gm2) + se2) - gm2]
        axM.errorbar([S1, S2], [gm1, gm2], yerr=[yerr_lo, yerr_hi],
                     fmt="o", ms=7, color=gcol, capsize=4,
                     label=f"{glab}:  $\\bar a$ = {a_mean:+.3f} /km "
                           f"({a_mean*100:+.1f}%/km)")
        axM.plot([S1, S2], [gm1, gm2], "-", color=gcol, lw=2.0)
        alpha_all.append(sub["alpha_km"].to_numpy())
    axM.set_yscale("log")
    axM.set_xticks([S1, S2])
    axM.set_xticklabels(["5 km\n(Çanakkale)", "6.5 km\n(Bosphorus)"])
    axM.set_xlim(S1 - 400, S2 + 400)
    axM.set_ylabel("geometric mean speed  $\\bar v(S)$  (m/s, log scale)")
    axM.set_title("(a)  Rate model  $\\mathrm{d}\\bar v/\\mathrm{d}S = -a\\,\\bar v$  "
                  "$\\Rightarrow$  $\\bar v(S)=v_0 e^{-aS}$\n"
                  "group means at the two race distances (a straight line on log scale)")
    axM.text(0.03, 0.05, "$T(S)=S/\\bar v(S)=(S/v_0)\\,e^{aS}$\n ($a>0$: speed decays with distance = fatigue;  $a<0$: mean speed is higher on the longer race)", transform=axM.transAxes, va="bottom", fontsize=9, bbox=dict(boxstyle="round", facecolor="#F5F8FB", edgecolor="gray"))
    axM.legend(loc="upper right", fontsize=9)

    # ---- (b) a katsayısı dağılımı: cinsiyet x geniş yaş grubu ----
    order = (["M", "<30"], ["M", "30-44"], ["M", "45+"], ["F", "<30"], ["F", "30-44"], ["F", "45+"])
    pos = np.arange(len(order))
    cols = [COL_M, COL_M, COL_M, COL_F, COL_F, COL_F]
    alphas_g = [0.45, 0.62, 0.8, 0.45, 0.62, 0.8]
    data = []
    labels = []
    for i, (gkey, brd) in enumerate(order):
        vals = fin[(fin["gender"] == gkey) & (fin["broad"] == brd)]["alpha_km"].to_numpy()
        data.append(vals)
        labels.append(f"{gkey} {brd}\n(n={vals.size})")
    bp = axA.boxplot(data, positions=pos, widths=0.62, patch_artist=True, showfliers=False, medianprops=dict(color="black", lw=1.5), whiskerprops=dict(color="#555555"), capprops=dict(color="#555555"))
    for patch, col, aa in zip(bp["boxes"], cols, alphas_g):
        patch.set(facecolor=to_rgba(col, aa), edgecolor=col)
    axA.axhline(0.0, color="black", lw=1.0, ls=":")
    H, dfree, p = kruskal_wallis(alpha_all)
    axA.text(0.03, 0.97,
             f"Kruskal-Wallis (Men vs Women):\nH({dfree}) = {H:.2f},  "
             f"p {_fmt_p(p)}\n$a$>0 fatigue  ·  $a$<0 speed boost",
             transform=axA.transAxes, va="top", fontsize=9,
             bbox=dict(boxstyle="round", facecolor="#F5F8FB",
                       edgecolor="black"))
    axA.set_xticks(pos)
    axA.set_xticklabels(labels, fontsize=8)
    axA.set_ylabel("$a$ (1/km)  —  per-athlete  "
                   "$a=\\ln(v_1/v_2)/1.5$ km")
    axA.set_title("(b)  Distribution of the speed-distance rate coefficient\n"
                  "(per-athlete coefficient determined from the two points of the exponential model)")
    axA.set_ylim(-0.45, 0.18)

    # ---- (c) 6.5 km süre tahminleri: sabit tempo (M0) vs üstel (M1) ----
    r0, m0 = rmse_map_metrics(fin["T2hat_m0"], fin["T2"])
    r1, m1 = rmse_map_metrics(fin["T2hat_m1"], fin["T2"])
    imp = 100.0 * (1.0 - r1 / r0)
    lim = (min(fin["T2"].min(), fin["T2hat_m0"].min(), fin["T2hat_m1"].min()) * 0.97, max(fin["T2"].max(), fin["T2hat_m0"].max(), fin["T2hat_m1"].max()) * 1.03)
    for gkey, gcol in (("M", COL_M), ("F", COL_F)):
        m = fin["gender"] == gkey
        axP.scatter(fin["T2"][m], fin["T2hat_m1"][m], s=16, alpha=0.5, color=gcol, edgecolors="none", label=f"M1 exponential  {gkey}")
    axP.scatter(fin["T2"], fin["T2hat_m0"], s=13, marker="^", alpha=0.35, color="#FF7F0E", edgecolors="none", label="M0 constant pace (1.3·T1)")
    axP.plot([lim[0], lim[1]], [lim[0], lim[1]], "--", color="black", lw=1.2, label="perfect prediction")
    boxP = (f"n = {len(fin)}\n"
            f"M0 (constant pace): RMSE = {r0:.0f} s, MAPE = {m0:.2f}%\n"
            f"M1 (exponential rate, group-$a$): RMSE = {r1:.0f} s, "
            f"MAPE = {m1:.2f}%\n"
            f"M1 RMSE improvement: %{imp:.1f}")
    axP.text(0.03, 0.97, boxP, transform=axP.transAxes, va="top", fontsize=9, bbox=dict(boxstyle="round", facecolor="#F5F8FB", edgecolor="#1f77b4"))
    axP.set_xlim(lim)
    axP.set_ylim(lim)
    axP.set_xlabel("observed $T_2$ (s)")
    axP.set_ylabel("predicted $T_2$ (s)")
    axP.set_title("(c)  6.5 km time prediction — model comparison\n"
                  "M1: athlete's $v_1$ + common $a$ of their gender group "
                  "(LOO)")
    axP.legend(loc="lower right", fontsize=8)

    # ---- (d) tahmin hatalarının hız dilimlerine göre dağılımı ----
    try:
        dec = pd.qcut(fin["v1"], 10, labels=False, duplicates="drop")
    except (ValueError, IndexError):
        dec = pd.qcut(fin["v1"], 5, labels=False, duplicates="drop")
    data0, data1, tick_lab = [], [], []
    for k in sorted(dec.dropna().unique()):
        m = dec == k
        data0.append(fin.loc[m, "err_T2hat_m0"].to_numpy())
        data1.append(fin.loc[m, "err_T2hat_m1"].to_numpy())
        lo = float(fin.loc[m, "v1"].min())
        hi = float(fin.loc[m, "v1"].max())
        tick_lab.append(f"{lo:.2f}-{hi:.2f}\n(n={int(m.sum())})")
    xx = np.arange(len(data0))
    for off, dd, col, lab in ((+0.0, data0, "#FF7F0E", "M0 constant pace"),
                              (0.35, data1, "#1f77b4", "M1 exponential rate")):
        bp = axE.boxplot(dd, positions=xx + off, widths=0.32, patch_artist=True, showfliers=False, medianprops=dict(color="black", lw=1.4), whiskerprops=dict(color="#555555"), capprops=dict(color="#555555"))
        for patch in bp["boxes"]:
            patch.set(facecolor=to_rgba(col, 0.75), edgecolor=col)
    med0 = float(np.median(np.concatenate(data0)))
    med1 = float(np.median(np.concatenate(data1)))
    boxE = (f"median relative error\n"
            f"M0: %{med0:+.1f}   M1: %{med1:+.1f}\n"
            f"(+) overestimate  (−) underestimate")
    axE.text(0.03, 0.97, boxE, transform=axE.transAxes, va="top", fontsize=9, bbox=dict(boxstyle="round", facecolor="#F5F8FB", edgecolor="#1f77b4"))
    axE.axhline(0.0, color="black", lw=1.0)
    axE.set_xticks(xx + 0.175)
    axE.set_xticklabels(tick_lab, fontsize=7)
    axE.set_xlabel("Çanakkale mean-speed bins (m/s)")
    axE.set_ylabel("prediction error  $(\\hat T_2-T_2)/T_2$  (%)")
    axE.set_title("(d)  Prediction error by speed (performance)\n"
                  "the constant-pace model systematically overestimates, while the "
                  "exponential rate model corrects this")
    from matplotlib.patches import Patch as _Patch
    axE.legend(handles=[_Patch(facecolor="#FF7F0E", alpha=0.8, label="M0 constant pace"), _Patch(facecolor="#1f77b4", alpha=0.8, label="M1 exponential rate")], loc="lower right", fontsize=8)

    fig.suptitle(
        "Section 3.3 – Rate Problems  ·  2026 common athletes: "
        "speed-distance rate (fatigue) analysis\n"
        "$\\dfrac{\\mathrm{d}\\bar v}{\\mathrm{d}S}=-a\\,\\bar v$  "
        "$\\Rightarrow$  $\\bar v(S)=v_0 e^{-aS}$,  "
        "$T(S)=(S/v_0)\\,e^{aS}$   —   for predicting the 6.5 km time, "
        "comparison of the constant-pace (M0) and the exponential-rate (M1) models",
        fontsize=12.5, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return fig

# ---------------------------------------------------------------------------
# Genel akış: veri -> mekanik uyum -> oran modeli -> grafikler
# ---------------------------------------------------------------------------

def add_mechanics_fits(fin):
    """Tüm sporcular için dur-duraksız kuadratik-direnç uyumunu dener."""
    fin = fin.copy()
    v_inf = np.full(len(fin), np.nan)
    a_arr = np.full(len(fin), np.nan)
    b_arr = np.full(len(fin), np.nan)
    c_arr = np.full(len(fin), np.nan)
    for i, row in enumerate(fin.itertuples()):
        p = fit_mechanics(float(row.T1), float(row.T2))
        if p is not None:
            v_inf[i], a_arr[i], b_arr[i], c_arr[i] = (
                p["v_inf"], p["a"], p["b"], p["c"])
    fin["mech_v_inf"] = v_inf
    fin["mech_a"] = a_arr
    fin["mech_b"] = b_arr
    fin["mech_c"] = c_arr
    return fin

def run(show):
    bar = "=" * 70
    print(bar)
    print("ROSS CHAPTER 3 APPLICATIONS — 2026 common athletes, differential-equation analysis")
    print(f"  {S1:.0f} m Çanakkale  vs  {S2:.0f} m Bosphorus")
    print(bar)

    if not DATA_CSV.exists():
        print(f"ERROR: {DATA_CSV} not found. Run common_2026_dataset.py "
              "first.")
        return 1

    fin = load_common()
    fin = add_age_cols(fin)
    fin = fin[fin["gender"].isin(["M", "F"])].copy()
    fin = add_mechanics_fits(fin)
    fin = add_rate_cols(fin, group_col="gender")
    if len(fin) < 10:
        print("Not enough data (n<10).")
        return 1

    # ---- konsol özeti ----
    n_fatigue = int((fin["alpha_km"] > 0).sum())
    n_boost = int((fin["alpha_km"] < 0).sum())
    print(f"Sample: {len(fin)}  (M {int((fin.gender=='M').sum())}, "
          f"F {int((fin.gender=='F').sum())})")
    print(f"Exponential-rate coefficient a: >0 (fatigue-like) {n_fatigue} athletes, "
          f"<0 (speed boost on the longer race) {n_boost} athletes")
    print()
    print("Coefficient a (1/km) by gender:")
    print(group_summary(fin, "alpha_km").to_string())
    print()
    print("M0 constant pace vs M1 exponential rate - 6.5 km time prediction:")
    r0, m0 = rmse_map_metrics(fin["T2hat_m0"], fin["T2"])
    r1, m1 = rmse_map_metrics(fin["T2hat_m1"], fin["T2"])
    print(f"  M0: RMSE {r0:.1f} s, MAPE %{m0:.2f}")
    print(f"  M1: RMSE {r1:.1f} s, MAPE %{m1:.2f}   "
          f"(improvement %{100*(1-r1/r0):.1f})")
    print()
    n_feas = int(fin["mech_v_inf"].notna().sum())
    print(f"Mechanics (dv/dt=a-bv²) fit: {n_feas}/{len(fin)} athletes feasible "
          f"(gap %14-30 band).")
    sub = fin[fin["mech_v_inf"].notna()]
    if len(sub):
        print("  median terminal speed v∞: M %.2f, F %.2f m/s  "
              "median v∞/v1: %.2f" % (
                  sub.loc[sub.gender == "M", "mech_v_inf"].median(),
                  sub.loc[sub.gender == "F", "mech_v_inf"].median(),
                  (sub["mech_v_inf"] / sub["v1"]).median()))
        proto = _choose_prototype(fin, fin["mech_v_inf"].notna().to_numpy())
        pp = fit_mechanics(float(proto["T1"]), float(proto["T2"]))
        print(f"  Prototype athlete (panels a,b): {proto['name']} — "
              f"a={pp['a']:.4f} m/s², b={pp['b']:.6f} 1/m, "
              f"v∞={pp['v_inf']:.2f} m/s")

    fig1 = _build_mechanics_figure(fin, show=show)
    fig2 = _build_rate_figure(fin, show=show)

    if show:
        plt.show()
    else:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        fig1.savefig(CHART_MECH, dpi=150, bbox_inches="tight")
        fig2.savefig(CHART_RATE, dpi=150, bbox_inches="tight")
        print(bar)
        print(f"Charts saved:")
        print(f"  {CHART_MECH}")
        print(f"  {CHART_RATE}")
    plt.close(fig1)
    plt.close(fig2)
    return 0

def main():
    parser = argparse.ArgumentParser(
        description="Analyze 2026 Çanakkale/Istanbul common athletes via Ross "
                    "Chapter 3 differential-equation applications; produce the charts "
                    "as follows:\n  - de_mechanics_newton_quadratic_drag.png "
                    "(3.2 Newton + quadratic drag)\n  - "
                    "de_rate_exponential_2026.png (3.3 exponential rate / fatigue)")
    parser.add_argument("--show", action="store_true",
                        help="open the charts in windows (no saving)")
    args = parser.parse_args()
    sys.exit(run(show=args.show))

if __name__ == "__main__":
    main()