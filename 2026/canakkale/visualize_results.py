from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib

if "--show" not in sys.argv:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import colormaps
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.ticker import FuncFormatter

def age_band(age_group):
    s = "" if age_group is None else str(age_group)
    m = re.search(r"\(([^()]*)\)", s)
    inner = m.group(1) if m else s
    mm = re.search(r"(\d{1,2}\s*[-–]\s*\d{1,2}|\d{1,2}\s*\+)", inner)
    if mm:
        return mm.group(1).replace(" ", "")
    return inner.strip()

def band_sort_key(band):
    m = re.match(r"\s*(\d{1,3})", str(band))
    return int(m.group(1)) if m else 999

def fmt_time(seconds):
    seconds = int(round(float(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def fmt_pace(sec_per_100m):
    m, s = divmod(int(round(float(sec_per_100m))), 60)
    return f"{m}:{s:02d}"

def _fmt_time_ticks(value, _pos):
    return fmt_time(value)

def _fmt_pace_ticks(value, _pos):
    return fmt_pace(value)

def load_results(cfg):
    path = cfg.data_dir / f"{cfg.dataset_stem()}.csv"
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [c.strip().lstrip("\ufeff") for c in df.columns]
    df["swim_seconds"] = pd.to_numeric(df["swim_seconds"], errors="coerce")
    df["status"] = df["status"].fillna("").astype(str).str.strip().str.upper()
    df = df[df["status"] == "FINISHED"].copy()
    df = df.dropna(subset=["swim_seconds"])
    df = df[df["swim_seconds"] > 0]
    return df.reset_index(drop=True)

def resolve_user(df, cfg, bib, time_override):
    if time_override is not None:
        return {"seconds": float(time_override), "rank": None,
                "label": "explicit --time", "mode": "override"}
    target_bib = bib if bib is not None else cfg.default_bib
    if target_bib is not None:
        rows = df[df["bib"].astype(str).str.strip() == str(int(target_bib))]
        if len(rows) >= 1:
            r = rows.iloc[0]
            rank = None if pd.isna(r["overall_rank"]) else int(r["overall_rank"])
            return {"seconds": float(r["swim_seconds"]), "rank": rank,
                    "label": f"bib {r['bib']} - {r['full_name']} ({r['time_text']})",
                    "row": r, "mode": "bib"}
    if cfg.auto_lookup:
        cond = df
        for col, val in cfg.auto_lookup.items():
            cond = cond[cond[col] == val]
        if len(cond) == 1:
            r = cond.iloc[0]
            return {"seconds": float(r["swim_seconds"]), "rank": int(r["overall_rank"]),
                    "label": f"auto bib {r['bib']} - {r['full_name']} ({r['time_text']})",
                    "row": r, "mode": "auto"}
    med = float(df["swim_seconds"].median())
    return {"seconds": med, "rank": None, "label": "fallback (medyan)",
            "row": None, "mode": "median"}

def gaussian_kde_pdf(x_grid, sample, bw=None):
    sample = np.asarray(sample, dtype=float).ravel()
    x_grid = np.asarray(x_grid, dtype=float)
    if sample.size == 0:
        return np.zeros_like(x_grid)
    sd = float(np.std(sample))
    if bw is None:
        bw = 1.06 * sd * sample.size ** (-1 / 5) if sd > 0 else 1.0
    bw = max(float(bw), 1e-6)
    diff = (x_grid[:, None] - sample[None, :]) / bw
    pdf = np.exp(-0.5 * diff * diff).sum(axis=1)
    return pdf / (bw * np.sqrt(2.0 * np.pi) * sample.size)

matplotlib.rcParams.update({
    "figure.facecolor": "white",
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.size": 10,
})

def view1_distribution(df, cfg, user, out_dir, show):
    times = df["swim_seconds"].to_numpy(dtype=float)
    n = times.size
    median = float(np.median(times))
    top_decile = float(np.percentile(times, 10))
    mean = float(np.mean(times))
    p25, p75 = np.percentile(times, [25, 75])
    my_seconds = user["seconds"]

    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    ax.xaxis.set_major_formatter(FuncFormatter(_fmt_time_ticks))
    ax.hist(times, bins=45, density=True, alpha=0.55, color="#4C72B0",
            edgecolor="white", linewidth=0.6, label="finishers (histogram)")
    x = np.linspace(times.min(), times.max(), 800)
    ax.plot(x, gaussian_kde_pdf(x, times), color="#C44E52", lw=2.2,
            label="Gaussian KDE")

    y_top = float(np.max(ax.get_ylim()))
    refs = [
        (median,     "#DD8452", f"median  {fmt_time(median)}", 0.985),
        (top_decile, "#55A868", f"top decile  {fmt_time(top_decile)}", 0.930),
        (my_seconds, "#B07AA1", f"you  {fmt_time(my_seconds)}", 0.875),
    ]
    for val, color, lab, yf in refs:
        ax.axvline(val, color=color, ls="--", lw=1.6, alpha=0.9)
        ax.text(val, y_top * yf, lab, color=color, ha="center", va="top",
                fontsize=9, fontweight="bold")

    pct_my = 100.0 * float((times <= my_seconds).mean())
    stats = (
        f"n = {n:,} finishers\n"
        f"mean {fmt_time(mean)}   median {fmt_time(median)}\n"
        f"IQR {fmt_time(p25)} - {fmt_time(p75)}\n"
        f"fastest {fmt_time(times.min())} / slowest {fmt_time(times.max())}\n\n"
        f"your time {fmt_time(my_seconds)} is faster than\n"
        f"{pct_my:.1f}% of the field"
    )
    ax.text(0.02, 0.03, stats, transform=ax.transAxes, ha="left", va="bottom",
            fontsize=9, bbox=dict(boxstyle="round", facecolor="#FBF7E8",
                                  edgecolor="#C9B458", alpha=0.95))

    ax.set_xlabel("finish time (minutes:seconds)")
    ax.set_ylabel("density")
    ax.set_title(f"{cfg.name} - overall finish-time distribution "
                 "(top decile = fastest 10% = P10)")
    ax.legend(loc="upper right", frameon=True)
    ax.margins(x=0.01)
    fig.tight_layout()

    path = out_dir / "01_finish_time_distribution.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    print(f"  [1/5] {path.name}  (median {fmt_time(median)}, "
          f"top decile {fmt_time(top_decile)})")
    return path

def _draw_violin(ax, data, pos, color, width):
    data = np.asarray(data, dtype=float)
    if data.size >= 2 and np.unique(data).size >= 2:
        parts = ax.violinplot([data], positions=[pos], widths=width,
                              showmeans=False, showmedians=True, showextrema=True)
        body = parts["bodies"][0]
        body.set_facecolor(color)
        body.set_edgecolor("#2A2A2A")
        body.set_alpha(0.75)
        body.set_linewidth(0.8)
        for key in ("cmedians", "cmins", "cmaxes", "cbars"):
            parts[key].set_color("#2A2A2A")
            parts[key].set_linewidth(0.9)
        return parts
    ax.plot(pos, data, marker="o", color=color, ms=5, alpha=0.9,
            linestyle="none", zorder=5)
    ax.plot([pos], [np.mean(data)], marker="_", color="#2A2A2A", ms=10, zorder=6)
    return None

def view2_age_gender(df, cfg, out_dir, show):
    d = df.copy()
    d["band"] = d["age_group"].map(age_band)
    bands = sorted(d["band"].unique(), key=band_sort_key)

    male_c, female_c, hl_c = "#4C72B0", "#DD8452", "#C44E52"
    fig, ax = plt.subplots(figsize=(12.5, 6.4))
    ax.yaxis.set_major_formatter(FuncFormatter(_fmt_time_ticks))
    for i, band in enumerate(bands):
        for g, color in (("M", male_c), ("F", female_c)):
            grp = d[(d["band"] == band) & (d["gender"] == g)]["swim_seconds"]
            if grp.empty:
                continue
            pos = i - 0.17 if g == "M" else i + 0.17
            is_hl = bool(cfg.owner_highlight) and (g == cfg.owner_highlight[0]
                                                   and band == cfg.owner_highlight[1])
            parts = _draw_violin(ax, grp.to_numpy(dtype=float), pos,
                                 hl_c if is_hl else color, width=0.30)
            if parts is not None and is_hl:
                parts["bodies"][0].set_edgecolor("#000000")
                parts["bodies"][0].set_linewidth(2.2)
                ax.plot([pos], [np.median(grp)], marker="*", ms=15,
                        color="#000000", zorder=9)
            ax.text(pos, -0.055, str(int(grp.size)),
                    transform=ax.get_xaxis_transform(), ha="center", va="top",
                    fontsize=7.5, color="#555555")

    ax.set_xticks(range(len(bands)))
    ax.set_xticklabels(bands)
    ax.set_xlabel("age band")
    ax.set_ylabel("finish time (minutes:seconds)")
    ax.set_title(f"{cfg.name} - finish time by age band and gender   "
                 "(count under each violin)")

    hl_label = ""
    if cfg.owner_highlight:
        hl_gender, hl_band = cfg.owner_highlight
        hl_label = {"M": "Male", "F": "Female"}.get(hl_gender, hl_gender) + f" {hl_band}"
    handles = [mpatches.Patch(color=male_c, label="Male"),
               mpatches.Patch(color=female_c, label="Female")]
    if cfg.owner_highlight:
        handles.append(mpatches.Patch(color=hl_c, label=f"{hl_label} \u25c6"))
    note = f"\u25c6 = {hl_label}, the owner's bracket" if cfg.owner_highlight else ""
    ax.text(0.985, 0.03, note, transform=ax.transAxes, ha="right", va="bottom",
            fontsize=9, bbox=dict(boxstyle="round", facecolor="#F5E8E8",
                                  edgecolor="#C44E52", alpha=0.95))
    ax.legend(handles=handles, loc="upper left", frameon=True)
    ax.set_ylim(bottom=0)
    fig.tight_layout()

    path = out_dir / "02_age_group_gender.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    print(f"  [2/5] {path.name}")
    return path

def view3_ecdf(df, cfg, user, out_dir, show):
    times = np.sort(df["swim_seconds"].to_numpy(dtype=float))
    n = times.size
    y = np.arange(1, n + 1) / n
    my_seconds = user["seconds"]

    fig, ax = plt.subplots(figsize=(10.5, 6.0))
    ax.xaxis.set_major_formatter(FuncFormatter(_fmt_time_ticks))
    ax.plot(times, y, color="#4C72B0", lw=2.4, drawstyle="steps-post",
            label="ECDF")
    ax.fill_between(times, y, step="post", color="#4C72B0", alpha=0.10)

    cnt_le = int(np.searchsorted(times, my_seconds, side="right"))
    cnt_lt = int(np.searchsorted(times, my_seconds, side="left"))
    pct_my = 100.0 * cnt_le / n
    rank_my = user["rank"] if user["rank"] else cnt_lt + 1
    ax.plot([my_seconds, my_seconds], [0, cnt_le / n], color="#B07AA1",
            ls="--", lw=1.5)
    ax.plot([my_seconds], [cnt_le / n], "o", color="#B07AA1", ms=7, zorder=6)
    ax.annotate(f"you: {fmt_time(my_seconds)}\nfaster than {pct_my:.1f}% "
                f"(~rank {rank_my:,} / {n:,})",
                xy=(my_seconds, cnt_le / n),
                xytext=(my_seconds + 130, max(0.05, cnt_le / n - 0.20)),
                fontsize=9, color="#8E5A74",
                arrowprops=dict(arrowstyle="->", color="#8E5A74", lw=1.1))

    for delta, color, lab in ((50, "#55A868", "up 50"),
                              (100, "#C44E52", "up 100")):
        target_rank = max(1, rank_my - delta)
        target_time = float(times[target_rank - 1])
        need = my_seconds - target_time
        pct_t = target_rank / n
        ax.axhline(pct_t, color=color, ls=":", lw=1.2, alpha=0.9)
        ax.axvline(target_time, color=color, ls=":", lw=1.2, alpha=0.9)
        ax.annotate(f"{lab}: need {fmt_time(target_time)}\n({need:.0f}s faster, "
                    f"rank {target_rank:,})",
                    xy=(target_time, pct_t),
                    xytext=(target_time + 120, min(0.95, pct_t + 0.12)),
                    fontsize=8.5, color=color,
                    arrowprops=dict(arrowstyle="->", color=color, lw=1.0))

    ax.set_xlabel("finish time (minutes:seconds)")
    ax.set_ylabel("cumulative fraction of finishers")
    ax.set_ylim(0, 1.02)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.set_title(f"{cfg.name} - ECDF: finish time to percentile "
                 "(steeper = tighter pack)")
    q25, q75 = np.percentile(times, [25, 75])
    ax.text(0.985, 0.03,
            f"50% of finishers between {fmt_time(q25)} and {fmt_time(q75)}",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=9,
            bbox=dict(boxstyle="round", facecolor="#EDF2F7",
                      edgecolor="#4C72B0", alpha=0.95))
    ax.legend(loc="lower right", frameon=True)
    fig.tight_layout()

    path = out_dir / "03_ecdf.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)

    r50, r100 = max(1, rank_my - 50), max(1, rank_my - 100)
    t50, t100 = float(times[r50 - 1]), float(times[r100 - 1])
    print(f"  [3/5] {path.name}")
    print(f"        rank ~{rank_my:,} -> up 50  needs {fmt_time(t50)} "
          f"({my_seconds - t50:.0f}s faster)")
    print(f"        rank ~{rank_my:,} -> up 100 needs {fmt_time(t100)} "
          f"({my_seconds - t100:.0f}s faster)")
    return path

def view4_nations(df, cfg, out_dir, show):
    d = df.copy()
    d["nation"] = d["nation"].fillna("").astype(str).str.strip().str.upper()
    d.loc[d["nation"] == "", "nation"] = "N/A"

    distance = cfg.distance_m
    g = (d.groupby("nation", sort=False)
          .agg(count=("bib", "count"),
               med_pace100=("swim_seconds",
                            lambda s: np.median(s) / (distance / 100.0)))
          .reset_index())
    meaningful = g[g["count"] >= 5].copy()
    show_all = len(meaningful) <= 15
    if not show_all:
        meaningful = meaningful.sort_values("count", ascending=False).head(15)
    order = meaningful.sort_values("count", ascending=True)["nation"].tolist()
    m2 = meaningful.set_index("nation").loc[order]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 0.42 * len(order) + 2.6))
    ax2.xaxis.set_major_formatter(FuncFormatter(_fmt_pace_ticks))
    for axx in (ax1, ax2):
        axx.spines["top"].set_visible(False)
        axx.spines["right"].set_visible(False)
    ax1.barh(order, m2["count"], color="#4C72B0", edgecolor="white")
    ax1.set_xlabel("finishers")
    ax1.set_title("Participation")
    ax1.tick_params(axis="y", labelsize=9)
    for i, v in enumerate(m2["count"]):
        ax1.text(v, i, f"  {int(v)}", va="center", fontsize=8, color="#333333")

    cmap = colormaps["plasma"]
    pace_vals = m2["med_pace100"].to_numpy(dtype=float)
    norm = Normalize(float(pace_vals.min()), float(pace_vals.max()))
    ax2.barh(order, pace_vals, color=[cmap(norm(v)) for v in pace_vals],
             edgecolor="white")
    ax2.set_xlabel("median pace  (min:sec per 100 m)")
    ax2.set_title("Median pace")
    ax2.tick_params(axis="y", labelleft=False)
    overall_pace = float(np.median(d["swim_seconds"]) / (distance / 100.0))
    ax2.axvline(overall_pace, color="#2A2A2A", ls="--", lw=1.2)
    ax2.text(overall_pace, len(order) - 0.45, f"field median {fmt_pace(overall_pace)}",
             ha="center", va="bottom", fontsize=8, color="#2A2A2A")
    for i, v in enumerate(pace_vals):
        ax2.text(v, i, f"  {fmt_pace(v)}", va="center", fontsize=8, color="#333333")

    sm = ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax2, fraction=0.05, pad=0.02)
    cbar.set_label("median pace (s per 100 m)")

    scope = f"{len(meaningful)} nations with >= 5 finishers"
    if not show_all:
        scope = f"top 15 nations (of {len(g)} with entries)"
    fig.suptitle(f"{cfg.name} - participation & median pace by nation  "
                 f"({scope})", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    path = out_dir / "04_nation_participation_pace.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    print(f"  [4/5] {path.name}  ({len(meaningful)} nations shown)")
    return path

def view5_gender_kde(df, cfg, user, out_dir, show):
    x = np.linspace(df["swim_seconds"].min(), df["swim_seconds"].max(), 800)
    male_c, female_c, my_c = "#4C72B0", "#DD8452", "#B07AA1"
    groups = []
    for lab, g, color in (("men", "M", male_c), ("women", "F", female_c)):
        t = df.loc[df["gender"] == g, "swim_seconds"].to_numpy(dtype=float)
        if t.size > 0:
            groups.append((lab, t, color, gaussian_kde_pdf(x, t)))
    if not groups:
        raise ValueError("no gender data available to plot view 5")
    my_seconds = user["seconds"]

    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    ax.xaxis.set_major_formatter(FuncFormatter(_fmt_time_ticks))
    for _, _, color, pdf in groups:
        ax.fill_between(x, pdf, color=color, alpha=0.30, linewidth=0, zorder=2)
    for lab, t, color, pdf in groups:
        ax.plot(x, pdf, color=color, lw=2.2, zorder=3,
                label=f"{lab}  n={t.size:,}")

    for lab, t, color, pdf in groups:
        med = float(np.median(t))
        ax.axvline(med, color=color, ls="--", lw=1.8, alpha=0.9, zorder=4)
        y_at = float(np.interp(med, x, pdf))
        offset = -18 if lab == "men" else 18
        ha = "right" if lab == "men" else "left"
        ax.text(med + offset, y_at, f"{lab} median  {fmt_time(med)}",
                color=color, ha=ha, va="bottom", fontsize=9,
                fontweight="bold", zorder=5)

    ax.axvline(my_seconds, color=my_c, ls=":", lw=2.0, alpha=0.6, zorder=4)
    y_you = max(float(np.interp(my_seconds, x, pdf)) for _, _, _, pdf in groups)
    ax.text(my_seconds, y_you, f"you  {fmt_time(my_seconds)}", color=my_c,
            ha="center", va="bottom", fontsize=9, fontstyle="italic", zorder=5)

    pcts = {lab: 100.0 * float((t <= my_seconds).mean())
            for lab, t, _, _ in groups}
    stats_lines = [f"{lab:<6s} n={t.size:,}   median {fmt_time(np.median(t))}"
                   for lab, t, _, _ in groups]
    if len(groups) == 2:
        gap = float(np.median(groups[1][1])) - float(np.median(groups[0][1]))
        stats_lines.append(f"median gap: women {gap:.0f}s slower")
    stats_lines.append("")
    stats_lines.append(f"your time {fmt_time(my_seconds)} is faster than")
    stats_lines.append("   ".join(f"{pcts[lab]:.1f}% of {lab}"
                                  for lab, _, _, _ in groups))
    ax.text(0.985, 0.03, "\n".join(stats_lines), transform=ax.transAxes,
            ha="right", va="bottom", fontsize=9,
            bbox=dict(boxstyle="round", facecolor="#F5F8FB",
                      edgecolor="#4C72B0", alpha=0.95))

    ax.set_xlabel("finish time (minutes:seconds)")
    ax.set_ylabel("density")
    ax.set_title(f"{cfg.name} - men vs. women finish-time density\n"
                 "(semi-transparent KDEs dashed = group median, "
                 "dotted = your time)")
    ax.legend(loc="upper right", frameon=True)
    ax.margins(x=0.01)
    fig.tight_layout()

    path = out_dir / "05_gender_kde.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    med_txt = "  vs  ".join(f"{lab} {fmt_time(float(np.median(t)))}"
                            for lab, t, _, _ in groups)
    print(f"  [5/5] {path.name}  ({med_txt})")
    return path

def run(cfg, bib, time_override, show):
    df = load_results(cfg)
    user = resolve_user(df, cfg, bib, time_override)

    print("=" * 66)
    print(cfg.name + " - visualization summary")
    print("=" * 66)
    print(f"finishers (FINISHED, valid time) : {len(df):,}")
    print(df["gender"].value_counts().to_string())
    print(f"your result : {user['label']}   ->   {fmt_time(user['seconds'])}")

    out_dir = cfg.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        view1_distribution(df, cfg, user, out_dir, show=show),
        view2_age_gender(df, cfg, out_dir, show=show),
        view3_ecdf(df, cfg, user, out_dir, show=show),
        view4_nations(df, cfg, out_dir, show=show),
        view5_gender_kde(df, cfg, user, out_dir, show=show),
    ]
    print("=" * 66)
    print("Saved figures:")
    for p in sorted(out_dir.glob("*.png")):
        print(f"   {p}")
    return paths

def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from event import EVENT

    parser = argparse.ArgumentParser(description=f"{EVENT.name} — görselleştirme")
    parser.add_argument("--bib", type=int, default=None,
                        help="senin bib numaran (varsayılan: event.py default_bib)")
    parser.add_argument("--time", type=float, default=None,
                        help="senin süren saniye cinsinden (--bib'i ezer)")
    parser.add_argument("--show", action="store_true",
                        help="grafikleri interaktif olarak da aç")
    args = parser.parse_args()

    run(EVENT, bib=args.bib, time_override=args.time, show=args.show)

if __name__ == "__main__":
    main()