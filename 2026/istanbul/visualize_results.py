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
from matplotlib.ticker import FuncFormatter

def age_band(age_group):
    s = "" if age_group is None else str(age_group)
    m = re.search(r"\(([^()]*)\)", s)
    inner = m.group(1) if m else s
    mm = re.search(r"(\d{1,2}\s*[-–]\s*\d{1,2}|\d{1,2}\s*\+)", inner)
    if mm:
        return mm.group(1).replace(" ", "")
    return inner.strip()

def band_sort_key(band) -> int:
    m = re.match(r"\s*(\d{1,3})", str(band))
    return int(m.group(1)) if m else 999

def fmt_time(seconds):
    seconds = int(round(float(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def _fmt_time_ticks(value, _pos):
    return fmt_time(value)

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
    median = float(np.median(times))
    p5 = float(np.percentile(times, 5))
    p10 = float(np.percentile(times, 10))
    p25 = float(np.percentile(times, 25))
    my_seconds = user["seconds"]

    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    ax.xaxis.set_major_formatter(FuncFormatter(_fmt_time_ticks))
    ax.hist(times, bins=45, density=True, alpha=0.55, color="#4C72B0",
            edgecolor="white", linewidth=0.6, label="finishers (histogram)")
    x = np.linspace(times.min(), times.max(), 800)
    ax.plot(x, gaussian_kde_pdf(x, times), color="#C44E52", lw=2.2,
            label="Gaussian KDE")

    refs = [
        (median,     "#DD8452", f"median  {fmt_time(median)}"),
        (p25,        "#55A868", f"Top 25% / P25  {fmt_time(p25)}"),
        (p10,        "#3C7A89", f"Top 10% / P10  {fmt_time(p10)}"),
        (p5,         "#8172B2", f"Top 5% / P5  {fmt_time(p5)}"),
        (my_seconds, "#D81B60", f"me  {fmt_time(my_seconds)}"),
    ]
    for val, color, lab in refs:
        ax.axvline(val, color=color, ls="--", lw=1.8, alpha=0.95, label=lab)

    ax.set_xlabel("finish time (minutes:seconds)")
    ax.set_ylabel("density")
    ax.set_title(f"{cfg.name} - overall finish-time distribution")
    ax.legend(loc="upper right", frameon=True, fontsize=8)
    ax.margins(x=0.01)
    fig.tight_layout()

    path = out_dir / "01_finish_time_distribution.png"
    if not show:
        fig.savefig(path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    status = "saved" if not show else "shown (not saved)"
    print(f"  [1/5] {path.name}  [{status}]  (median {fmt_time(median)}, "
          f"P5 {fmt_time(p5)}, P10 {fmt_time(p10)}, P25 {fmt_time(p25)})")
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

def view2_age_gender(df, cfg, user, out_dir, show):
    d = df.copy()
    d["band"] = d["age_group"].map(age_band)
    bands = sorted(d["band"].unique(), key=band_sort_key)

    row = user.get("row")
    if row is not None:
        hl = (str(row["gender"]).strip().upper(), age_band(row["age_group"]))
        hl_label = {"M": "Male", "F": "Female"}.get(hl[0], hl[0]) + f" {hl[1]}"
        hl_note = f"\u25c6 = {hl_label}, my bracket"
    elif cfg.owner_highlight:
        hl = cfg.owner_highlight
        hl_label = {"M": "Male", "F": "Female"}.get(hl[0], hl[0]) + f" {hl[1]}"
        hl_note = f"\u25c6 = {hl_label}, the owner's bracket"
    else:
        hl, hl_label, hl_note = None, "", ""

    male_c, female_c, hl_c = "#4C72B0", "#DD8452", "#C44E52"
    fig, ax = plt.subplots(figsize=(12.5, 6.4))
    ax.yaxis.set_major_formatter(FuncFormatter(_fmt_time_ticks))
    for i, band in enumerate(bands):
        for g, color in (("M", male_c), ("F", female_c)):
            grp = d[(d["band"] == band) & (d["gender"] == g)]["swim_seconds"]
            if grp.empty:
                continue
            pos = i - 0.17 if g == "M" else i + 0.17
            is_hl = bool(hl) and (g == hl[0] and band == hl[1])
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
    ax.set_title(f"{cfg.name} - finish time by age band and gender")

    handles = [mpatches.Patch(color=male_c, label="Male"),
               mpatches.Patch(color=female_c, label="Female")]
    if hl:
        handles.append(mpatches.Patch(color=hl_c, label=f"{hl_label} \u25c6"))
    if hl_note:
        ax.text(0.985, 0.03, hl_note, transform=ax.transAxes, ha="right",
                va="bottom", fontsize=9,
                bbox=dict(boxstyle="round", facecolor="#F5E8E8",
                          edgecolor="#C44E52", alpha=0.95))
    ax.legend(handles=handles, loc="upper left", frameon=True)
    ax.set_ylim(bottom=0)
    fig.tight_layout()

    path = out_dir / "02_age_group_gender.png"
    if not show:
        fig.savefig(path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    status = "saved" if not show else "shown (not saved)"
    print(f"  [2/5] {path.name}  [{status}]")
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
    ax.set_title(f"{cfg.name} - ECDF: finish time to percentile")
    q25, q75 = np.percentile(times, [25, 75])
    ax.text(0.985, 0.03,
            f"50% of finishers between {fmt_time(q25)} and {fmt_time(q75)}",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=9,
            bbox=dict(boxstyle="round", facecolor="#EDF2F7",
                      edgecolor="#4C72B0", alpha=0.95))
    ax.legend(loc="lower right", frameon=True)
    fig.tight_layout()

    path = out_dir / "03_ecdf.png"
    if not show:
        fig.savefig(path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)

    r50, r100 = max(1, rank_my - 50), max(1, rank_my - 100)
    t50, t100 = float(times[r50 - 1]), float(times[r100 - 1])
    status = "saved" if not show else "shown (not saved)"
    print(f"  [3/5] {path.name}  [{status}]")
    print(f"        rank ~{rank_my:,} -> up 50  needs {fmt_time(t50)} "
          f"({my_seconds - t50:.0f}s faster)")
    print(f"        rank ~{rank_my:,} -> up 100 needs {fmt_time(t100)} "
          f"({my_seconds - t100:.0f}s faster)")
    return path

def view4_nations(df, cfg, out_dir, show):
    d = df.copy()
    d["nation"] = d["nation"].fillna("").astype(str).str.strip().str.upper()
    d.loc[d["nation"] == "", "nation"] = "N/A"

    g = (d.groupby("nation", sort=False).agg(count=("bib", "count"), male=("gender", lambda s: int((s == "M").sum())), female=("gender", lambda s: int((s == "F").sum()))).reset_index())
    meaningful = g[g["count"] >= 5].copy()
    show_all = len(meaningful) <= 15
    if not show_all:
        meaningful = meaningful.sort_values("count", ascending=False).head(15)
    order = meaningful.sort_values("count", ascending=True)["nation"].tolist()
    m2 = meaningful.set_index("nation").loc[order]

    male_c, female_c = "#4C72B0", "#DD8452"
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 0.42 * len(order) + 2.6))
    for axx in (ax1, ax2):
        axx.spines["top"].set_visible(False)
        axx.spines["right"].set_visible(False)

    male_vals = m2["male"].to_numpy(dtype=float)
    female_vals = m2["female"].to_numpy(dtype=float)
    total_vals = male_vals + female_vals
    with np.errstate(divide="ignore", invalid="ignore"):
        male_pct = np.where(total_vals > 0, 100.0 * male_vals / total_vals, 0.0)
        female_pct = np.where(total_vals > 0, 100.0 * female_vals / total_vals, 0.0)
    ax1.barh(order, female_pct, color=female_c, edgecolor="white", label="Female")
    ax1.barh(order, male_pct, left=female_pct, color=male_c,
             edgecolor="white", label="Male")
    ax1.set_xlim(0, 100)
    ax1.set_xticks([0, 25, 50, 75, 100])
    ax1.set_xlabel("share of finishers (%)")
    ax1.set_title("Gender distribution")
    ax1.tick_params(axis="y", labelsize=9)
    ax1.legend(loc="lower right", frameon=True, fontsize=8)

    # right: finishers
    ax2.barh(order, m2["count"], color="#808080", edgecolor="white")
    ax2.set_xlabel("finishers")
    ax2.set_title("Participation")
    ax2.tick_params(axis="y", labelleft=False)
    for i, v in enumerate(m2["count"]):
        ax2.text(v, i, f"  {int(v)}", va="center", fontsize=8, color="#333333")

    scope = f"{len(meaningful)} nations with >= 5 finishers"
    if not show_all:
        scope = f"top 15 nations (of {len(g)} with entries)"
    fig.suptitle(f"{cfg.name} - gender distribution & participation by nation  "
                 f"({scope})", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    path = out_dir / "04_nation_gender_participation.png"
    if not show:
        fig.savefig(path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    status = "saved" if not show else "shown (not saved)"
    print(f"  [4/5] {path.name}  [{status}]  ({len(meaningful)} nations shown)")
    return path

def view5_gender_kde(df, cfg, user, out_dir, show):
    x = np.linspace(df["swim_seconds"].min(), df["swim_seconds"].max(), 800)
    male_c, female_c, my_c = "#4C72B0", "#DD8452", "#B07AA1"
    groups = []
    for lab, g, color in (("Male", "M", male_c), ("Female", "F", female_c)):
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
        offset = -18 if lab == "Male" else 18
        ha = "right" if lab == "Male" else "left"
        ax.text(med + offset, y_at, f"{lab} median  {fmt_time(med)}",
                color=color, ha=ha, va="bottom", fontsize=9,
                fontweight="bold", zorder=5)

    ax.axvline(my_seconds, color=my_c, ls=":", lw=2.0, alpha=0.6, zorder=4)
    y_me = max(float(np.interp(my_seconds, x, pdf)) for _, _, _, pdf in groups)
    ax.text(my_seconds, y_me, f"me  {fmt_time(my_seconds)}", color=my_c,
            ha="center", va="bottom", fontsize=9, fontstyle="italic", zorder=5)

    pcts = {lab: 100.0 * float((t <= my_seconds).mean())
            for lab, t, _, _ in groups}
    stats_lines = [f"{lab:<6s} n={t.size:,}   median {fmt_time(np.median(t))}"
                   for lab, t, _, _ in groups]
    if len(groups) == 2:
        gap = float(np.median(groups[1][1])) - float(np.median(groups[0][1]))
        stats_lines.append(f"median gap: Female {gap:.0f}s slower")
    stats_lines.append("")
    stats_lines.append(f"my time {fmt_time(my_seconds)} is faster than")
    stats_lines.append("   ".join(f"{pcts[lab]:.1f}% of {lab}"
                                  for lab, _, _, _ in groups))
    ax.text(0.985, 0.03, "\n".join(stats_lines), transform=ax.transAxes,
            ha="right", va="bottom", fontsize=9,
            bbox=dict(boxstyle="round", facecolor="#F5F8FB",
                      edgecolor="#4C72B0", alpha=0.95))

    ax.set_xlabel("finish time (minutes:seconds)")
    ax.set_ylabel("density")
    ax.set_title(f"{cfg.name} - male vs female finish-time density")
    ax.legend(loc="upper right", frameon=True)
    ax.margins(x=0.01)
    fig.tight_layout()

    path = out_dir / "05_gender_kde.png"
    if not show:
        fig.savefig(path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    med_txt = "  vs  ".join(f"{lab} {fmt_time(float(np.median(t)))}"
                            for lab, t, _, _ in groups)
    status = "saved" if not show else "shown (not saved)"
    print(f"  [5/5] {path.name}  [{status}]  ({med_txt})")
    return path

def run(cfg, bib, time_override, show):
    df = load_results(cfg)
    user = resolve_user(df, cfg, bib, time_override)

    print("=" * 66)
    print(cfg.name + " - visualization summary")
    print("=" * 66)
    print(f"finishers (FINISHED, valid time) : {len(df):,}")
    print(df["gender"].value_counts().to_string())
    print(f"my result : {user['label']}   ->   {fmt_time(user['seconds'])}")

    out_dir = cfg.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        view1_distribution(df, cfg, user, out_dir, show=show),
        view2_age_gender(df, cfg, user, out_dir, show=show),
        view3_ecdf(df, cfg, user, out_dir, show=show),
        view4_nations(df, cfg, out_dir, show=show),
        view5_gender_kde(df, cfg, user, out_dir, show=show),
    ]
    print("=" * 66)
    if show:
        print("Interactive mode: nothing was auto-saved.")
        print("Zoom each window as you like, then use its toolbar save")
        print("button to keep the exact view you see on screen.")
    else:
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