"""
Social media doomscrolling analysis.
Produces a focused PDF report on compulsive usage patterns.
Supports multiple apps configured via apps.yaml.
"""

import warnings
warnings.filterwarnings("ignore")

import os
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
from matplotlib.backends.backend_pdf import PdfPages
import seaborn as sns
import numpy as np
from scipy import stats
import calendar

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

DEFAULT_PDF    = "instagram_report.pdf"
DEFAULT_CONFIG = Path(__file__).parent.parent.parent / "apps.yaml"

# Fallback single-app config (original Instagram behaviour)
FALLBACK_CONFIG = {
    "report_title": "Instagram Doomscrolling Report",
    "apps": [{"name": "Instagram", "bundle_id": "com.burbn.instagram", "color": "#E1306C"}],
    "glance_max_min": 1,
    "doomscroll_min": 5,
    "binge_min": 20,
    "streak_gap_min": 60,
}

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

sns.set_theme(style="whitegrid", font_scale=1.0)
plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "#fafafa"})


# ── Config loading ────────────────────────────────────────────────────────────

def load_config(config_path: str | None = None) -> dict:
    """Load apps.yaml config. Falls back gracefully if yaml not installed or file missing."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG
    if not HAS_YAML:
        print("  Warning: PyYAML not installed — using default Instagram config.")
        print("  Run: pip install pyyaml   to enable apps.yaml support.")
        return FALLBACK_CONFIG
    if not path.exists():
        return FALLBACK_CONFIG
    with open(path) as f:
        cfg = yaml.safe_load(f)
    # Merge defaults
    cfg.setdefault("report_title", "Social Media Doomscrolling Report")
    cfg.setdefault("glance_max_min", 1)
    cfg.setdefault("doomscroll_min", 5)
    cfg.setdefault("binge_min", 20)
    cfg.setdefault("streak_gap_min", 60)
    return cfg


# ── Data loading ──────────────────────────────────────────────────────────────

def load_apps(csv_path: str, cfg: dict) -> pd.DataFrame:
    """Load and combine all configured apps into one DataFrame."""
    df = pd.read_csv(csv_path, parse_dates=["start_time", "end_time"])

    app_cfgs = cfg["apps"]
    # Build a lookup: bundle_id → (name, color)
    id_to_meta = {a["bundle_id"]: a for a in app_cfgs}

    combined = []
    for app_cfg in app_cfgs:
        bid = app_cfg["bundle_id"]
        sub = df[(df["app"] == bid) & (df["duration_seconds"] > 3)].copy()
        if len(sub) == 0:
            print(f"  Warning: no sessions found for '{app_cfg['name']}' ({bid}) — skipping.")
            continue
        sub["app_name"]  = app_cfg["name"]
        sub["app_color"] = app_cfg["color"]
        combined.append(sub)

    if not combined:
        raise ValueError("No sessions found for any configured app. Check your bundle IDs in apps.yaml.")

    ig = pd.concat(combined, ignore_index=True)
    ig["duration_min"] = ig["duration_seconds"] / 60
    ig["hour"]         = ig["start_time"].dt.hour
    ig["date"]         = ig["start_time"].dt.date
    ig["day_name"]     = ig["start_time"].dt.day_name()
    ig["dow"]          = ig["start_time"].dt.dayofweek
    ig["is_weekend"]   = ig["dow"] >= 5

    doom_min  = cfg["doomscroll_min"]
    binge_min = cfg["binge_min"]
    glance_max = cfg["glance_max_min"]

    def classify(d):
        if d < glance_max:  return "Glance"
        if d < doom_min:    return "Scroll"
        if d < binge_min:   return "Doomscroll"
        return "Binge"

    ig["session_type"] = ig["duration_min"].apply(classify)
    ig["is_doom"]      = ig["duration_min"] >= doom_min

    def tod(h):
        if 5  <= h < 9:  return "Early Morning\n(5–9am)"
        if 9  <= h < 12: return "Morning\n(9am–12pm)"
        if 12 <= h < 17: return "Afternoon\n(12–5pm)"
        if 17 <= h < 21: return "Evening\n(5–9pm)"
        return "Night\n(9pm–5am)"
    ig["time_of_day"] = ig["hour"].apply(tod)

    return ig.sort_values("start_time").reset_index(drop=True)


def find_doom_streaks(ig: pd.DataFrame, gap_min: int = 60) -> pd.DataFrame:
    ig_sorted = ig.sort_values("start_time").reset_index(drop=True)
    streaks = []
    streak = [0]
    for i in range(1, len(ig_sorted)):
        gap = (ig_sorted.loc[i, "start_time"] - ig_sorted.loc[i-1, "end_time"]).total_seconds() / 60
        if gap <= gap_min:
            streak.append(i)
        else:
            if len(streak) > 1:
                rows = ig_sorted.loc[streak]
                streaks.append({
                    "start":      rows["start_time"].min(),
                    "end":        rows["end_time"].max(),
                    "sessions":   len(streak),
                    "total_min":  rows["duration_min"].sum(),
                    "hour":       int(rows["start_time"].min().hour),
                    "date":       rows["start_time"].min().date(),
                    "day_name":   rows["start_time"].min().day_name(),
                    "is_weekend": rows["start_time"].min().dayofweek >= 5,
                })
            streak = [i]
    if len(streak) > 1:
        rows = ig_sorted.loc[streak]
        streaks.append({
            "start":      rows["start_time"].min(),
            "end":        rows["end_time"].max(),
            "sessions":   len(streak),
            "total_min":  rows["duration_min"].sum(),
            "hour":       int(rows["start_time"].min().hour),
            "date":       rows["start_time"].min().date(),
            "day_name":   rows["start_time"].min().day_name(),
            "is_weekend": rows["start_time"].min().dayofweek >= 5,
        })
    return pd.DataFrame(streaks)


# ── App colour helpers ────────────────────────────────────────────────────────

def _app_colors(ig: pd.DataFrame) -> dict:
    """Return {app_name: color} dict."""
    return ig.drop_duplicates("app_name").set_index("app_name")["app_color"].to_dict()


def _primary_color(ig: pd.DataFrame) -> str:
    return list(_app_colors(ig).values())[0]


# ── Text summary ──────────────────────────────────────────────────────────────

def interpret(ig: pd.DataFrame, streaks: pd.DataFrame, cfg: dict) -> str:
    total_h   = ig["duration_min"].sum() / 60
    days      = (ig["date"].max() - ig["date"].min()).days + 1
    doom_time = ig[ig["is_doom"]]["duration_min"].sum()

    app_names = ig["app_name"].unique()
    title = cfg.get("report_title", "Doomscrolling Analysis")

    lines = ["═" * 68, f"  {title.upper()}", "═" * 68]

    lines.append(f"\n▸ OVERVIEW ({days} days) — {', '.join(app_names)}")
    lines.append(f"  Total time    : {total_h:.1f} h  ({total_h/days*60:.0f} min/day avg)")
    lines.append(f"  Sessions      : {len(ig):,}  ({len(ig)/days:.0f}/day avg)")
    lines.append(f"  Median session: {ig['duration_min'].median():.1f} min")
    lines.append(f"  Longest       : {ig['duration_min'].max():.0f} min")

    for name in app_names:
        sub = ig[ig["app_name"] == name]
        lines.append(f"  {name}: {sub['duration_min'].sum()/60:.1f} h  ({len(sub):,} sessions)")

    glance_n = (ig["session_type"] == "Glance").sum()
    scroll_n = (ig["session_type"] == "Scroll").sum()
    doom_n   = (ig["session_type"] == "Doomscroll").sum()
    binge_n  = (ig["session_type"] == "Binge").sum()

    lines.append(f"\n▸ SESSION BREAKDOWN")
    lines.append(f"  Glance    (<{cfg['glance_max_min']} min) : {glance_n:4d} ({glance_n/len(ig)*100:.0f}%)")
    lines.append(f"  Scroll    (1–{cfg['doomscroll_min']} min): {scroll_n:4d} ({scroll_n/len(ig)*100:.0f}%)")
    lines.append(f"  Doomscroll({cfg['doomscroll_min']}–{cfg['binge_min']} min): {doom_n:4d} ({doom_n/len(ig)*100:.0f}%)")
    lines.append(f"  Binge     (>{cfg['binge_min']} min) : {binge_n:4d} ({binge_n/len(ig)*100:.0f}%)")
    lines.append(f"  → Doomscroll+Binge = {(doom_n+binge_n)/len(ig)*100:.0f}% of sessions "
                 f"but {doom_time/ig['duration_min'].sum()*100:.0f}% of time")

    peak_h   = ig.groupby("hour")["duration_min"].sum().idxmax()
    night_h  = ig[ig["hour"].isin([22, 23, 0, 1, 2])]["duration_min"].sum() / 60
    wd = ig[~ig["is_weekend"]].groupby("date")["duration_min"].sum().mean()
    we = ig[ ig["is_weekend"]].groupby("date")["duration_min"].sum().mean()
    lines.append(f"\n▸ PATTERNS")
    lines.append(f"  Peak hour : {peak_h:02d}:00–{peak_h+1:02d}:00")
    lines.append(f"  Night use : {night_h:.1f} h total (after 10pm)")
    lines.append(f"  Weekday   : {wd:.0f} min/day  |  Weekend: {we:.0f} min/day")

    if len(streaks):
        lines.append(f"\n▸ DOOM STREAKS  (back-to-back within 60 min)")
        lines.append(f"  Total: {len(streaks)}   Avg: {streaks['total_min'].mean():.0f} min   "
                     f"Longest: {streaks['total_min'].max():.0f} min")

    lines.append("\n" + "═" * 68)
    return "\n".join(lines)


# ── Chart functions ───────────────────────────────────────────────────────────

def _fig_title(ig, cfg):
    total_h = ig["duration_min"].sum() / 60
    days    = (ig["date"].max() - ig["date"].min()).days + 1
    app_names = list(ig["app_name"].unique())
    colors    = _app_colors(ig)
    title     = cfg.get("report_title", "Social Media Doomscrolling Report")

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.axis("off")
    bg = "#fdf0f5" if len(app_names) == 1 else "#f0f4fd"
    ax.set_facecolor(bg); fig.patch.set_facecolor(bg)

    ax.text(0.5, 0.84, title, ha="center", fontsize=30, fontweight="bold",
            color=list(colors.values())[0], transform=ax.transAxes)

    # App badges
    badge_x = np.linspace(0.5 - 0.12*(len(app_names)-1), 0.5 + 0.12*(len(app_names)-1), len(app_names))
    for x, name in zip(badge_x, app_names):
        ax.text(x, 0.68, name, ha="center", fontsize=15, fontweight="bold",
                color=colors[name], transform=ax.transAxes,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                          edgecolor=colors[name], linewidth=1.5))

    ax.text(0.5, 0.50,
            f"{ig['date'].min()}  →  {ig['date'].max()}  ({days} days)",
            ha="center", fontsize=12, color="#555", transform=ax.transAxes)
    ax.text(0.5, 0.38,
            f"{total_h:.0f} h total  ·  {len(ig):,} sessions  ·  "
            f"{total_h/days*60:.0f} min/day average",
            ha="center", fontsize=13, color="#333", transform=ax.transAxes)

    # Per-app line
    if len(app_names) > 1:
        per_app = ig.groupby("app_name")["duration_min"].sum() / 60
        parts = [f"{n}: {per_app.get(n, 0):.0f} h" for n in app_names]
        ax.text(0.5, 0.26, "  ·  ".join(parts),
                ha="center", fontsize=11, color="#666", transform=ax.transAxes)

    return fig


def _fig_daily(ig, cfg):
    colors = _app_colors(ig)
    app_names = list(colors.keys())
    daily_all = ig.groupby("date")["duration_min"].sum().reset_index()
    daily_all["date"] = pd.to_datetime(daily_all["date"])
    daily_all["rolling5"] = daily_all["duration_min"].rolling(5, min_periods=1).mean()

    fig, ax = plt.subplots(figsize=(13, 4.5))

    if len(app_names) == 1:
        c = list(colors.values())[0]
        ax.bar(daily_all["date"], daily_all["duration_min"], color=c, alpha=0.5, label="Daily")
        ax.plot(daily_all["date"], daily_all["rolling5"], color=c, lw=2.5, label="5-day avg")
        ax.axhline(daily_all["duration_min"].mean(), color="#aaa", lw=1.2, ls="--", label="Overall avg")
    else:
        # Stacked bars per app
        bottom = np.zeros(len(daily_all))
        date_idx = daily_all["date"].values
        for name in app_names:
            sub = ig[ig["app_name"] == name].groupby("date")["duration_min"].sum().reset_index()
            sub["date"] = pd.to_datetime(sub["date"])
            merged = daily_all[["date"]].merge(sub, on="date", how="left").fillna(0)
            ax.bar(date_idx, merged["duration_min"], bottom=bottom,
                   color=colors[name], alpha=0.75, label=name)
            bottom += merged["duration_min"].values
        ax.plot(daily_all["date"], daily_all["rolling5"], color="#333", lw=2, ls="--", label="5-day avg")

    ax.set_ylabel("Minutes")
    ax.set_title("Daily Screen Time" + (f" — {app_names[0]}" if len(app_names) == 1 else " (stacked by app)"))
    ax.legend()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.autofmt_xdate()
    return fig


def _fig_weekly(ig, cfg):
    """Weekly totals with trend — zooms out from daily noise."""
    ig2 = ig.copy()
    ig2["date"] = pd.to_datetime(ig2["date"])
    ig2["week"] = ig2["date"].dt.to_period("W").apply(lambda r: r.start_time)
    colors = _app_colors(ig)
    app_names = list(colors.keys())

    weekly_all = ig2.groupby("week")["duration_min"].sum().reset_index()
    weekly_all.columns = ["week", "total_min"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: weekly totals (stacked if multi-app)
    if len(app_names) == 1:
        c = list(colors.values())[0]
        axes[0].bar(weekly_all["week"], weekly_all["total_min"] / 60,
                    color=c, alpha=0.7, width=5)
        axes[0].plot(weekly_all["week"], weekly_all["total_min"].rolling(2, min_periods=1).mean() / 60,
                     color=c, lw=2.5)
    else:
        bottom = np.zeros(len(weekly_all))
        for name in app_names:
            sub = ig2[ig2["app_name"] == name].groupby("week")["duration_min"].sum().reset_index()
            sub.columns = ["week", "total_min"]
            merged = weekly_all[["week"]].merge(sub, on="week", how="left").fillna(0)
            axes[0].bar(weekly_all["week"], merged["total_min"] / 60, bottom=bottom,
                        color=colors[name], alpha=0.75, label=name, width=5)
            bottom += merged["total_min"].values / 60
        axes[0].legend()

    axes[0].set_ylabel("Hours")
    axes[0].set_title("Weekly Total Screen Time")
    axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.autofmt_xdate()

    # Right: rolling 7-day average session length
    ig2_sorted = ig2.sort_values("start_time")
    ig2_sorted["rolling_med"] = (
        ig2_sorted["duration_min"]
        .rolling(50, min_periods=5)
        .median()
    )
    for name in app_names:
        sub = ig2_sorted[ig2_sorted["app_name"] == name]
        axes[1].plot(sub["start_time"], sub["rolling_med"],
                     color=colors[name], lw=2, label=name, alpha=0.85)
    axes[1].axhline(ig["duration_min"].median(), color="#aaa", lw=1, ls="--", label="Overall median")
    axes[1].set_ylabel("Minutes")
    axes[1].set_title("Rolling Median Session Length (50-session window)")
    axes[1].legend(fontsize=8)
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.autofmt_xdate()

    fig.tight_layout()
    return fig


def _fig_session_types(ig, cfg):
    glance_max = cfg["glance_max_min"]
    doom_min   = cfg["doomscroll_min"]
    binge_min  = cfg["binge_min"]
    labels = [f"Glance\n<{glance_max} min", f"Scroll\n{glance_max}–{doom_min} min",
              f"Doomscroll\n{doom_min}–{binge_min} min", f"Binge\n>{binge_min} min"]
    type_order = ["Glance", "Scroll", "Doomscroll", "Binge"]

    colors = _app_colors(ig)
    app_names = list(colors.keys())
    primary   = list(colors.values())[0]
    palette   = ["#FCAF45", "#F77737", primary, "#833AB4"]

    counts = ig["session_type"].value_counts().reindex(type_order, fill_value=0)
    times  = ig.groupby("session_type", observed=False)["duration_min"].sum().reindex(type_order, fill_value=0)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].bar(labels, counts.values, color=palette)
    axes[0].set_title("Sessions by Type")
    axes[0].set_ylabel("Session count")
    for i, v in enumerate(counts.values):
        axes[0].text(i, v + 1, str(v), ha="center", fontsize=10)

    if len(app_names) > 1:
        # Grouped bars per app
        x = np.arange(len(type_order))
        w = 0.8 / len(app_names)
        for idx, name in enumerate(app_names):
            sub = ig[ig["app_name"] == name]
            t = sub.groupby("session_type", observed=False)["duration_min"].sum().reindex(type_order, fill_value=0)
            axes[1].bar(x + idx*w - 0.4 + w/2, t.values / 60,
                        width=w, color=colors[name], label=name, alpha=0.85)
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(labels)
        axes[1].legend()
    else:
        axes[1].bar(labels, times.values / 60, color=palette)
        for i, v in enumerate(times.values):
            axes[1].text(i, v/60 + 0.05, f"{v/60:.1f}h", ha="center", fontsize=10)

    axes[1].set_title("Hours by Session Type" + (" (per app)" if len(app_names) > 1 else ""))
    axes[1].set_ylabel("Hours")
    fig.tight_layout()
    return fig


def _fig_app_comparison(ig, cfg):
    """Side-by-side app stats — only shown if ≥2 apps configured."""
    colors    = _app_colors(ig)
    app_names = list(colors.keys())
    if len(app_names) < 2:
        return None

    days = (ig["date"].max() - ig["date"].min()).days + 1
    metrics = ["Total hours", "Min/day avg", "Sessions/day", "Median session (min)", "% time in binges"]
    data = {}
    for name in app_names:
        sub = ig[ig["app_name"] == name]
        doom_frac = sub[sub["is_doom"]]["duration_min"].sum() / sub["duration_min"].sum() * 100 if len(sub) else 0
        data[name] = [
            round(sub["duration_min"].sum() / 60, 1),
            round(sub["duration_min"].sum() / days, 1),
            round(len(sub) / days, 1),
            round(sub["duration_min"].median(), 1),
            round(doom_frac, 1),
        ]

    n_metrics = len(metrics)
    fig, axes = plt.subplots(1, n_metrics, figsize=(15, 5))
    for i, (metric, ax) in enumerate(zip(metrics, axes)):
        vals = [data[n][i] for n in app_names]
        bars = ax.bar(app_names, vals, color=[colors[n] for n in app_names], width=0.5)
        ax.set_title(metric, fontsize=9, fontweight="bold")
        ax.set_xticks(range(len(app_names)))
        ax.set_xticklabels(app_names, fontsize=8)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(vals)*0.02,
                    str(val), ha="center", fontsize=9, fontweight="bold")
        ax.set_ylim(0, max(vals) * 1.25 if max(vals) > 0 else 1)

    fig.suptitle("App-by-App Comparison", fontsize=14, fontweight="bold")
    fig.tight_layout()
    return fig


def _fig_hourly(ig, cfg):
    colors    = _app_colors(ig)
    app_names = list(colors.keys())
    primary   = list(colors.values())[0]

    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)

    if len(app_names) == 1:
        hourly_s = ig.groupby("hour").size()
        hourly_t = ig.groupby("hour")["duration_min"].sum()
        axes[0].bar(hourly_s.index, hourly_s.values, color=primary, alpha=0.8)
        axes[1].bar(hourly_t.index, hourly_t.values / 60, color=primary, alpha=0.8)
    else:
        x = np.arange(24)
        w = 0.8 / len(app_names)
        for idx, name in enumerate(app_names):
            sub = ig[ig["app_name"] == name]
            hs = sub.groupby("hour").size().reindex(range(24), fill_value=0)
            ht = sub.groupby("hour")["duration_min"].sum().reindex(range(24), fill_value=0)
            axes[0].bar(x + idx*w - 0.4 + w/2, hs.values, width=w, color=colors[name], label=name, alpha=0.85)
            axes[1].bar(x + idx*w - 0.4 + w/2, ht.values / 60, width=w, color=colors[name], alpha=0.85)
        axes[0].legend()

    axes[0].set_ylabel("Number of sessions")
    axes[0].set_title("Opens by Hour of Day")
    axes[1].set_ylabel("Hours spent")
    axes[1].set_title("Time Spent by Hour of Day")
    axes[1].set_xlabel("Hour")
    axes[1].set_xticks(range(24))
    axes[1].set_xticklabels([f"{h:02d}:00" for h in range(24)], rotation=45, ha="right")
    fig.tight_layout()
    return fig


def _fig_heatmap(ig, cfg):
    pivot = ig.groupby(["day_name", "hour"])["duration_min"].sum().unstack(fill_value=0)
    pivot = pivot.reindex([d for d in DAY_ORDER if d in pivot.index])
    fig, ax = plt.subplots(figsize=(14, 5))
    sns.heatmap(pivot / 60, ax=ax, cmap="RdPu", linewidths=0.3,
                cbar_kws={"label": "Hours"}, annot=False)
    ax.set_xticks(range(24))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(24)], rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("")
    title = "Usage Heatmap — Day × Hour"
    if len(ig["app_name"].unique()) > 1:
        title += " (all apps combined)"
    ax.set_title(title)
    return fig


def _fig_session_dist(ig, cfg):
    primary = _primary_color(ig)
    purple  = "#833AB4"
    orange  = "#F77737"

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    clipped = ig["duration_min"].clip(upper=75)
    axes[0].hist(clipped, bins=80, color=primary, edgecolor="white", linewidth=0.2)
    axes[0].axvline(cfg["doomscroll_min"], color=orange, lw=1.5, ls="--",
                    label=f"{cfg['doomscroll_min']} min (doomscroll)")
    axes[0].axvline(cfg["binge_min"], color=purple, lw=1.5, ls="--",
                    label=f"{cfg['binge_min']} min (binge)")
    axes[0].set_xlabel("Session length (min)")
    axes[0].set_ylabel("Count")
    axes[0].set_title("Session Length Distribution")
    axes[0].legend(fontsize=8)

    sorted_s = np.sort(ig["duration_min"].values)
    cumtime  = np.cumsum(sorted_s) / sorted_s.sum() * 100
    axes[1].plot(sorted_s, cumtime, color=primary, lw=2)
    axes[1].axvline(cfg["doomscroll_min"], color=orange, lw=1.5, ls="--",
                    label=f"{cfg['doomscroll_min']} min")
    axes[1].axvline(cfg["binge_min"], color=purple, lw=1.5, ls="--",
                    label=f"{cfg['binge_min']} min")
    axes[1].set_xlabel("Session length (min)")
    axes[1].set_ylabel("Cumulative % of total time")
    axes[1].set_title("What % of Your Time Do Long Sessions Consume?")
    axes[1].set_xlim(0, 75)
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    return fig


def _fig_monthly_calendar(ig, cfg):
    """GitHub-style calendar: each cell = one day, colour = minutes used."""
    primary = _primary_color(ig)
    daily = ig.groupby("date")["duration_min"].sum()
    all_dates = pd.date_range(
        start=pd.to_datetime(ig["date"].min()),
        end=pd.to_datetime(ig["date"].max())
    )
    daily_full = daily.reindex([d.date() for d in all_dates], fill_value=0)

    months = sorted(set((d.year, d.month) for d in all_dates))
    n_months = len(months)
    n_cols = min(4, n_months)
    n_rows = (n_months + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols * 3.5, n_rows * 3.2))
    if n_rows == 1 and n_cols == 1:
        axes = np.array([[axes]])
    elif n_rows == 1:
        axes = axes.reshape(1, -1)
    elif n_cols == 1:
        axes = axes.reshape(-1, 1)

    vmax = daily_full.max()

    for idx, (year, month) in enumerate(months):
        row, col = divmod(idx, n_cols)
        ax = axes[row][col]
        _, n_days = calendar.monthrange(year, month)
        first_dow = calendar.monthrange(year, month)[0]  # 0=Mon

        ax.set_xlim(-0.5, 6.5)
        ax.set_ylim(-0.5, 5.5)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(f"{calendar.month_abbr[month]} {year}", fontsize=10, fontweight="bold")

        for day_n in range(1, n_days + 1):
            d = pd.Timestamp(year, month, day_n).date()
            minutes = daily_full.get(d, 0)
            dow = (first_dow + day_n - 1) % 7
            week = (first_dow + day_n - 1) // 7
            intensity = minutes / vmax if vmax > 0 else 0

            cmap = plt.cm.get_cmap("RdPu")
            color = cmap(0.1 + 0.9 * intensity)
            rect = mpatches.FancyBboxPatch(
                (dow - 0.45, 4.45 - week), 0.9, 0.9,
                boxstyle="round,pad=0.05", facecolor=color, edgecolor="white", linewidth=0.8
            )
            ax.add_patch(rect)
            ax.text(dow, 4.9 - week, str(day_n), ha="center", va="center",
                    fontsize=6.5, color="white" if intensity > 0.5 else "#555")
            if minutes > 0:
                ax.text(dow, 4.55 - week, f"{int(minutes)}m", ha="center", va="center",
                        fontsize=4.5, color="white" if intensity > 0.5 else "#888")

        for d_idx, d_name in enumerate(["M", "T", "W", "T", "F", "S", "S"]):
            ax.text(d_idx, 5.3, d_name, ha="center", va="center", fontsize=7, color="#999")

    # Hide unused subplots
    for idx in range(len(months), n_rows * n_cols):
        row, col = divmod(idx, n_cols)
        axes[row][col].axis("off")

    fig.suptitle("Daily Usage Calendar (darker = more time)", fontsize=13, fontweight="bold", y=1.01)
    fig.tight_layout()
    return fig


def _fig_streaks(ig, streaks, cfg):
    if len(streaks) == 0:
        return None
    primary = _primary_color(ig)
    purple  = "#833AB4"
    orange  = "#F77737"

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    axes[0].hist(streaks["total_min"], bins=25, color=primary, edgecolor="white")
    axes[0].axvline(streaks["total_min"].mean(), color=purple, lw=2, ls="--",
                    label=f"Mean: {streaks['total_min'].mean():.0f} min")
    axes[0].set_xlabel("Streak duration (min)")
    axes[0].set_ylabel("Count")
    axes[0].set_title("Doom Streak Duration Distribution")
    axes[0].legend()

    streak_hourly = streaks.groupby("hour")["total_min"].sum()
    axes[1].bar(streak_hourly.index, streak_hourly.values / 60, color=purple, alpha=0.8)
    axes[1].set_xlabel("Hour of day")
    axes[1].set_ylabel("Hours in streaks")
    axes[1].set_title("When Doom Streaks Happen")
    axes[1].set_xticks(range(0, 24, 2))

    streak_day = streaks.groupby("day_name")["total_min"].sum().reindex(DAY_ORDER).fillna(0)
    bar_colors = [orange if d in ["Saturday", "Sunday"] else primary for d in streak_day.index]
    axes[2].bar(range(len(streak_day)), streak_day.values / 60, color=bar_colors)
    axes[2].set_xticks(range(len(streak_day)))
    axes[2].set_xticklabels([d[:3] for d in streak_day.index])
    axes[2].set_ylabel("Hours in streaks")
    axes[2].set_title("Doom Streaks by Day of Week\n(orange = weekend)")
    fig.tight_layout()
    return fig


def _fig_streak_calendar(ig, streaks, cfg):
    """Calendar showing which days had doom streaks and how intense."""
    if len(streaks) == 0:
        return None
    primary = _primary_color(ig)

    streak_days = streaks.groupby("date").agg(
        total_min=("total_min", "sum"),
        count=("total_min", "count")
    )

    all_dates  = pd.date_range(
        start=pd.to_datetime(ig["date"].min()),
        end=pd.to_datetime(ig["date"].max())
    )
    months = sorted(set((d.year, d.month) for d in all_dates))
    n_cols = min(4, len(months))
    n_rows = (len(months) + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols * 3.5, n_rows * 3.2))
    if n_rows == 1 and n_cols == 1:
        axes = np.array([[axes]])
    elif n_rows == 1:
        axes = axes.reshape(1, -1)
    elif n_cols == 1:
        axes = axes.reshape(-1, 1)

    vmax = streak_days["total_min"].max() if len(streak_days) else 1

    for idx, (year, month) in enumerate(months):
        row, col = divmod(idx, n_cols)
        ax = axes[row][col]
        _, n_days = calendar.monthrange(year, month)
        first_dow  = calendar.monthrange(year, month)[0]

        ax.set_xlim(-0.5, 6.5); ax.set_ylim(-0.5, 5.5)
        ax.set_aspect("equal"); ax.axis("off")
        ax.set_title(f"{calendar.month_abbr[month]} {year}", fontsize=10, fontweight="bold")

        for day_n in range(1, n_days + 1):
            d     = pd.Timestamp(year, month, day_n).date()
            dow   = (first_dow + day_n - 1) % 7
            week  = (first_dow + day_n - 1) // 7
            has_streak = d in streak_days.index

            if has_streak:
                intensity = streak_days.loc[d, "total_min"] / vmax
                cmap  = plt.cm.get_cmap("Oranges")
                color = cmap(0.25 + 0.75 * intensity)
                edge  = "#cc4400"
            else:
                color = "#f0f0f0"
                edge  = "white"

            rect = mpatches.FancyBboxPatch(
                (dow - 0.45, 4.45 - week), 0.9, 0.9,
                boxstyle="round,pad=0.05", facecolor=color, edgecolor=edge, linewidth=0.8
            )
            ax.add_patch(rect)
            ax.text(dow, 4.9 - week, str(day_n), ha="center", va="center",
                    fontsize=6.5, color="white" if has_streak and intensity > 0.5 else "#555")
            if has_streak:
                n_st = streak_days.loc[d, "count"]
                ax.text(dow, 4.55 - week, f"{n_st}×", ha="center", va="center",
                        fontsize=4.5, color="white" if intensity > 0.5 else "#884400")

        for d_idx, d_name in enumerate(["M", "T", "W", "T", "F", "S", "S"]):
            ax.text(d_idx, 5.3, d_name, ha="center", fontsize=7, color="#999")

    for idx in range(len(months), n_rows * n_cols):
        row, col = divmod(idx, n_cols)
        axes[row][col].axis("off")

    fig.suptitle("Doom Streak Calendar (orange = streak day, number = streak count)",
                 fontsize=13, fontweight="bold", y=1.01)
    fig.tight_layout()
    return fig


def _fig_first_open(ig, cfg):
    primary = _primary_color(ig)
    purple  = "#833AB4"

    first = ig.sort_values("start_time").groupby("date").first().reset_index()
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].hist(first["hour"], bins=range(0, 25), color=primary, edgecolor="white")
    axes[0].axvspan(22, 24, color="navy", alpha=0.08, label="Late night")
    axes[0].axvspan(0, 7,  color="navy", alpha=0.08)
    axes[0].axvspan(5, 9,  color="gold", alpha=0.10, label="Early morning")
    axes[0].set_xlabel("Hour")
    axes[0].set_ylabel("Days")
    axes[0].set_title("First App Open of the Day")
    axes[0].set_xticks(range(0, 24, 2))
    axes[0].legend(fontsize=8)

    slope, intercept, r, p, _ = stats.linregress(first["hour"], first["duration_min"].clip(upper=30))
    x = np.linspace(first["hour"].min(), first["hour"].max(), 100)
    axes[1].scatter(first["hour"], first["duration_min"].clip(upper=30),
                    alpha=0.5, color=primary, edgecolors="white", s=40)
    axes[1].plot(x, slope*x + intercept, color=purple, lw=2,
                 label=f"Trend (r={r:.2f}, p={p:.2f})")
    axes[1].set_xlabel("Hour of first open")
    axes[1].set_ylabel("Duration of first session (min, capped 30)")
    axes[1].set_title("Does Opening Time Predict Session Length?")
    axes[1].legend()
    fig.tight_layout()
    return fig


def _fig_weekday_vs_weekend(ig, cfg):
    colors    = _app_colors(ig)
    app_names = list(colors.keys())
    primary   = list(colors.values())[0]
    orange    = "#F77737"

    ig2 = ig.copy()
    ig2["type"] = ig2["is_weekend"].map({True: "Weekend", False: "Weekday"})

    daily  = ig2.groupby(["date", "type"])["duration_min"].sum().reset_index()
    avg    = daily.groupby("type")["duration_min"].mean()
    hourly = ig2.groupby(["type", "hour"])["duration_min"].mean().reset_index()

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].bar(avg.index, avg.values, color=[orange, primary], width=0.5)
    axes[0].set_ylabel("Avg min/day")
    axes[0].set_title("Weekday vs Weekend — Daily Average")
    for i, (lbl, val) in enumerate(avg.items()):
        axes[0].text(i, val + 0.5, f"{val:.0f} min", ha="center", fontweight="bold")

    for label, color in [("Weekday", primary), ("Weekend", orange)]:
        sub = hourly[hourly["type"] == label]
        axes[1].plot(sub["hour"], sub["duration_min"], label=label, color=color,
                     lw=2, marker="o", markersize=4)
    axes[1].set_xlabel("Hour of day")
    axes[1].set_ylabel("Avg min/hour")
    axes[1].set_title("Hourly Profile — Weekday vs Weekend")
    axes[1].legend()
    axes[1].set_xticks(range(0, 24, 2))
    fig.tight_layout()
    return fig


def _fig_reopen_loop(ig, cfg):
    primary = _primary_color(ig)
    purple  = "#833AB4"
    orange  = "#F77737"

    ig_sorted = ig.sort_values("start_time").reset_index(drop=True)
    gaps = (ig_sorted["start_time"].iloc[1:].values - ig_sorted["end_time"].iloc[:-1].values)
    gap_min = pd.Series(gaps).dt.total_seconds() / 60
    gap_min = gap_min[(gap_min >= 0) & (gap_min <= 120)]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].hist(gap_min.clip(upper=60), bins=60, color=primary, edgecolor="white", linewidth=0.2)
    axes[0].axvline(5,  color=orange, lw=1.5, ls="--", label="5 min")
    axes[0].axvline(15, color=purple, lw=1.5, ls="--", label="15 min")
    axes[0].set_xlabel("Gap between sessions (min, capped at 60)")
    axes[0].set_ylabel("Count")
    axes[0].set_title("How Long Before You Reopen?")
    axes[0].legend(fontsize=8)

    sorted_gaps = np.sort(gap_min.values)
    cum_pct = np.arange(1, len(sorted_gaps) + 1) / len(sorted_gaps) * 100
    axes[1].plot(sorted_gaps, cum_pct, color=primary, lw=2)
    axes[1].axvline(5,  color=orange, lw=1.5, ls="--", label="5 min")
    axes[1].axvline(15, color=purple, lw=1.5, ls="--", label="15 min")
    axes[1].axvline(60, color="#aaa", lw=1,   ls=":",  label="1 hour")
    axes[1].set_xlabel("Gap (min)")
    axes[1].set_ylabel("Cumulative % of reopens")
    axes[1].set_title("Cumulative Reopen Rate")
    axes[1].set_xlim(0, 120)
    axes[1].legend(fontsize=8)

    within_1  = (gap_min <= 1).mean()  * 100
    within_5  = (gap_min <= 5).mean()  * 100
    within_15 = (gap_min <= 15).mean() * 100
    axes[1].text(0.98, 0.30,
                 f"≤1 min:  {within_1:.0f}%\n≤5 min:  {within_5:.0f}%\n≤15 min: {within_15:.0f}%",
                 transform=axes[1].transAxes, ha="right", va="bottom", fontsize=9, color="#333",
                 bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="#ccc"))
    fig.tight_layout()
    return fig


def _fig_session_escalation(ig, cfg):
    primary = _primary_color(ig)
    purple  = "#833AB4"

    ig2 = ig.copy()
    ig2["rank_in_day"] = ig2.groupby("date").cumcount() + 1
    multi = ig2[ig2.groupby("date")["rank_in_day"].transform("max") >= 3].copy()

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    jitter = np.random.default_rng(42).uniform(-0.25, 0.25, len(multi))
    axes[0].scatter(multi["rank_in_day"] + jitter, multi["duration_min"].clip(upper=40),
                    alpha=0.25, color=primary, s=18, edgecolors="none")
    if len(multi) > 10:
        slope, intercept, r, p, _ = stats.linregress(
            multi["rank_in_day"], multi["duration_min"].clip(upper=40))
        x = np.linspace(1, multi["rank_in_day"].max(), 100)
        axes[0].plot(x, slope*x + intercept, color=purple, lw=2,
                     label=f"Trend  r={r:.2f}  p={p:.2f}")
        axes[0].legend(fontsize=8)
    axes[0].set_xlabel("Session rank within the day")
    axes[0].set_ylabel("Session duration (min, capped 40)")
    axes[0].set_title("Does Each Reopen Get Longer?\n(Session Escalation)")

    avg_by_rank = (
        multi[multi["rank_in_day"] <= 10]
        .groupby("rank_in_day")["duration_min"]
        .mean()
    )
    axes[1].bar(avg_by_rank.index, avg_by_rank.values, color=primary, alpha=0.8)
    axes[1].set_xlabel("Session rank within the day")
    axes[1].set_ylabel("Avg duration (min)")
    axes[1].set_title("Average Session Length by Open Number")
    axes[1].set_xticks(avg_by_rank.index)
    fig.tight_layout()
    return fig


def _fig_night_usage(ig, cfg):
    """Night usage deep-dive: trend over time, and how it distributes by hour."""
    primary = _primary_color(ig)
    purple  = "#833AB4"

    night = ig[ig["hour"].isin([22, 23, 0, 1, 2])].copy()
    night["date_ts"] = pd.to_datetime(night["date"])

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Rolling weekly night usage
    nightly = night.groupby("date")["duration_min"].sum().reset_index()
    nightly["date_ts"] = pd.to_datetime(nightly["date"])
    nightly = nightly.sort_values("date_ts")
    nightly["rolling7"] = nightly["duration_min"].rolling(7, min_periods=1).mean()

    axes[0].fill_between(nightly["date_ts"], nightly["duration_min"],
                         alpha=0.3, color=primary)
    axes[0].plot(nightly["date_ts"], nightly["rolling7"], color=primary, lw=2)
    axes[0].set_ylabel("Minutes after 10pm")
    axes[0].set_title("Night Usage Over Time (7-day rolling avg)")
    axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.autofmt_xdate()

    # Distribution by hour within night window
    night_h = night.groupby("hour")["duration_min"].sum().reindex([22, 23, 0, 1, 2], fill_value=0)
    hour_labels = ["10pm", "11pm", "12am", "1am", "2am"]
    axes[1].bar(hour_labels, night_h.values / 60, color=[primary, primary, purple, purple, purple], alpha=0.8)
    axes[1].set_ylabel("Hours")
    axes[1].set_title("Night Usage by Hour\n(total across all days)")
    for i, v in enumerate(night_h.values):
        if v > 0:
            axes[1].text(i, v/60 + 0.01, f"{v/60:.1f}h", ha="center", fontsize=9)

    fig.suptitle("Night Usage Analysis (10pm – 3am)", fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


def _fig_recovery_days(ig, cfg):
    """Shows low-usage days — how often do you actually take a break?"""
    primary = _primary_color(ig)
    orange  = "#F77737"

    daily = ig.groupby("date")["duration_min"].sum()
    all_dates = pd.date_range(
        start=pd.to_datetime(ig["date"].min()),
        end=pd.to_datetime(ig["date"].max())
    )
    daily_full = daily.reindex([d.date() for d in all_dates], fill_value=0)

    thresholds = [0, 15, 30]
    labels = ["Zero usage", "< 15 min", "< 30 min"]
    counts = [(daily_full == 0).sum(),
              ((daily_full > 0) & (daily_full < 15)).sum(),
              ((daily_full >= 15) & (daily_full < 30)).sum()]
    total = len(daily_full)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Bar chart of low-usage day counts
    bar_colors = ["#4CAF50", "#8BC34A", orange]
    bars = axes[0].bar(labels, counts, color=bar_colors, width=0.5)
    axes[0].set_ylabel("Days")
    axes[0].set_title("Low-Usage Days — How Often Do You Take a Break?")
    for bar, count in zip(bars, counts):
        pct = count / total * 100
        axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                     f"{count} days\n({pct:.0f}%)", ha="center", fontsize=9, fontweight="bold")
    axes[0].set_ylim(0, max(counts) * 1.35 if max(counts) > 0 else 5)

    # Daily usage sorted — show the distribution
    sorted_daily = daily_full.sort_values().values
    axes[1].barh(range(len(sorted_daily)), sorted_daily,
                 color=[("#4CAF50" if v == 0 else ("#8BC34A" if v < 15 else (orange if v < 30 else primary)))
                        for v in sorted_daily],
                 height=1.0, edgecolor="none")
    axes[1].axvline(30, color="#888", lw=1, ls="--", label="30 min")
    axes[1].set_xlabel("Minutes")
    axes[1].set_ylabel("Days (sorted by usage)")
    axes[1].set_title("All Days Sorted by Usage\n(green = low use, pink = heavy)")
    axes[1].legend(fontsize=8)

    fig.tight_layout()
    return fig


def _fig_daily_intensity(ig, cfg):
    daily = ig.groupby("date")["duration_min"].sum().reset_index()
    daily["date"] = pd.to_datetime(daily["date"])
    primary = _primary_color(ig)

    fig, ax = plt.subplots(figsize=(13, 3.5))
    sc = ax.scatter(daily["date"], [1]*len(daily),
                    c=daily["duration_min"], cmap="RdPu",
                    s=daily["duration_min"] * 2, alpha=0.85, vmin=0)
    plt.colorbar(sc, ax=ax, label="Minutes")
    ax.set_yticks([])
    ax.set_title("Daily Intensity (dot size & colour = minutes)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.autofmt_xdate()
    return fig


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_report(
    csv_path: str,
    output_pdf: str = DEFAULT_PDF,
    config_path: str | None = None,
    verbose: bool = True,
) -> None:
    cfg = load_config(config_path)
    if verbose:
        app_names = [a["name"] for a in cfg["apps"]]
        print(f"Loading data for: {', '.join(app_names)}")

    ig = load_apps(csv_path, cfg)
    if verbose:
        print(f"  {len(ig):,} sessions after filtering accidental taps (<3s)")

    streaks = find_doom_streaks(ig, gap_min=cfg["streak_gap_min"])
    if verbose:
        print(f"  {len(streaks)} doom streaks identified")
        print(interpret(ig, streaks, cfg))
        print(f"\nGenerating PDF → {output_pdf}")

    pages = [
        ("Title",                  _fig_title,              (ig, cfg)),
        ("Daily Usage",            _fig_daily,              (ig, cfg)),
        ("Weekly Trends",          _fig_weekly,             (ig, cfg)),
        ("Session Types",          _fig_session_types,      (ig, cfg)),
        ("App Comparison",         _fig_app_comparison,     (ig, cfg)),
        ("Hourly Patterns",        _fig_hourly,             (ig, cfg)),
        ("Day×Hour Heatmap",       _fig_heatmap,            (ig, cfg)),
        ("Session Dist / CDF",     _fig_session_dist,       (ig, cfg)),
        ("Monthly Calendar",       _fig_monthly_calendar,   (ig, cfg)),
        ("Doom Streaks",           _fig_streaks,            (ig, streaks, cfg)),
        ("Streak Calendar",        _fig_streak_calendar,    (ig, streaks, cfg)),
        ("First Open",             _fig_first_open,         (ig, cfg)),
        ("Weekday vs Weekend",     _fig_weekday_vs_weekend, (ig, cfg)),
        ("Reopen Loop",            _fig_reopen_loop,        (ig, cfg)),
        ("Session Escalation",     _fig_session_escalation, (ig, cfg)),
        ("Night Usage",            _fig_night_usage,        (ig, cfg)),
        ("Recovery Days",          _fig_recovery_days,      (ig, cfg)),
        ("Daily Intensity",        _fig_daily_intensity,    (ig, cfg)),
    ]

    with PdfPages(output_pdf) as pdf:
        for label, fig_fn, args in pages:
            if verbose:
                print(f"  Plotting: {label}")
            try:
                fig = fig_fn(*args)
                if fig:
                    pdf.savefig(fig, bbox_inches="tight")
                    plt.close(fig)
            except Exception as e:
                if verbose:
                    print(f"    Warning: {label} failed — {e}")

    if verbose:
        print(f"\nDone → {output_pdf}")
