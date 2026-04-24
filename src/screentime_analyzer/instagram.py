"""
Instagram doomscrolling analysis.
Produces a focused PDF report on compulsive usage patterns.
"""

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_pdf import PdfPages
import seaborn as sns
import numpy as np
from scipy import stats

DEFAULT_PDF = "instagram_report.pdf"

IG_PINK   = "#E1306C"
IG_PURPLE = "#833AB4"
IG_ORANGE = "#F77737"
IG_YELLOW = "#FCAF45"

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TOD_ORDER = ["Early Morning\n(5–9am)", "Morning\n(9am–12pm)",
             "Afternoon\n(12–5pm)", "Evening\n(5–9pm)", "Night\n(9pm–5am)"]

sns.set_theme(style="whitegrid", font_scale=1.0)
plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "#fafafa"})


def load_instagram(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=["start_time", "end_time"])
    ig = df[df["app"] == "com.burbn.instagram"].copy()
    ig = ig[ig["duration_seconds"] > 3].copy()
    ig["duration_min"] = ig["duration_seconds"] / 60
    ig["hour"]         = ig["start_time"].dt.hour
    ig["date"]         = ig["start_time"].dt.date
    ig["day_name"]     = ig["start_time"].dt.day_name()
    ig["dow"]          = ig["start_time"].dt.dayofweek
    ig["is_weekend"]   = ig["dow"] >= 5

    def tod(h):
        if 5  <= h < 9:  return "Early Morning\n(5–9am)"
        if 9  <= h < 12: return "Morning\n(9am–12pm)"
        if 12 <= h < 17: return "Afternoon\n(12–5pm)"
        if 17 <= h < 21: return "Evening\n(5–9pm)"
        return "Night\n(9pm–5am)"
    ig["time_of_day"] = ig["hour"].apply(tod)
    ig["is_doom"] = ig["duration_min"] > 5
    return ig


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
                    "start":     rows["start_time"].min(),
                    "end":       rows["end_time"].max(),
                    "sessions":  len(streak),
                    "total_min": rows["duration_min"].sum(),
                    "hour":      rows["start_time"].min().hour,
                    "date":      rows["start_time"].min().date(),
                    "day_name":  rows["start_time"].min().day_name(),
                    "is_weekend": rows["start_time"].min().dayofweek >= 5,
                })
            streak = [i]
    if len(streak) > 1:
        rows = ig_sorted.loc[streak]
        streaks.append({
            "start":     rows["start_time"].min(),
            "end":       rows["end_time"].max(),
            "sessions":  len(streak),
            "total_min": rows["duration_min"].sum(),
            "hour":      rows["start_time"].min().hour,
            "date":      rows["start_time"].min().date(),
            "day_name":  rows["start_time"].min().day_name(),
            "is_weekend": rows["start_time"].min().dayofweek >= 5,
        })
    return pd.DataFrame(streaks)


def interpret(ig: pd.DataFrame, streaks: pd.DataFrame) -> str:
    total_h   = ig["duration_min"].sum() / 60
    days      = (ig["date"].max() - ig["date"].min()).days + 1
    daily_avg = ig.groupby("date")["duration_min"].sum().mean()
    doom_time = ig[ig["is_doom"]]["duration_min"].sum()

    quick  = (ig["duration_min"] < 1).sum()
    medium = ((ig["duration_min"] >= 1) & (ig["duration_min"] < 5)).sum()
    long_  = ((ig["duration_min"] >= 5) & (ig["duration_min"] < 20)).sum()
    binge  = (ig["duration_min"] >= 20).sum()

    lines = []
    lines.append("═" * 68)
    lines.append("  INSTAGRAM DOOMSCROLLING ANALYSIS")
    lines.append("═" * 68)

    lines.append(f"\n▸ OVERVIEW ({days} days)")
    lines.append(f"  Total Instagram time : {total_h:.1f} h  ({total_h/days*60:.0f} min/day avg)")
    lines.append(f"  Sessions             : {len(ig):,}  ({len(ig)/days:.0f}/day avg)")
    lines.append(f"  Median session       : {ig['duration_min'].median():.1f} min")
    lines.append(f"  Longest session      : {ig['duration_min'].max():.0f} min")

    lines.append(f"\n▸ SESSION BREAKDOWN")
    lines.append(f"  Glance    (<1 min)  : {quick:4d} sessions  ({quick/len(ig)*100:.0f}%)")
    lines.append(f"  Scroll    (1–5 min) : {medium:4d} sessions  ({medium/len(ig)*100:.0f}%)")
    lines.append(f"  Doomscroll(5–20 min): {long_:4d} sessions  ({long_/len(ig)*100:.0f}%)")
    lines.append(f"  Binge     (>20 min) : {binge:4d} sessions  ({binge/len(ig)*100:.0f}%)")
    lines.append(f"  → Doomscroll+Binge account for "
                 f"{(long_+binge)/len(ig)*100:.0f}% of sessions "
                 f"but {doom_time/ig['duration_min'].sum()*100:.0f}% of time")

    peak_h = ig.groupby("hour")["duration_min"].sum().idxmax()
    night_h = ig[ig["hour"].isin([22, 23, 0, 1, 2])]["duration_min"].sum() / 60
    morning_h = ig[ig["hour"].isin([5, 6, 7, 8])]["duration_min"].sum() / 60
    lines.append(f"\n▸ WHEN YOU DOOMSCROLL")
    lines.append(f"  Peak hour     : {peak_h:02d}:00–{peak_h+1:02d}:00")
    lines.append(f"  Night use     : {night_h:.1f} h total  (after 10pm)")
    lines.append(f"  Morning use   : {morning_h:.1f} h total  (5–9am)")

    wd = ig[~ig["is_weekend"]].groupby("date")["duration_min"].sum().mean()
    we = ig[ig["is_weekend"]].groupby("date")["duration_min"].sum().mean()
    lines.append(f"\n▸ WEEKDAY vs WEEKEND")
    lines.append(f"  Weekday avg : {wd:.0f} min/day")
    lines.append(f"  Weekend avg : {we:.0f} min/day  ({'more' if we>wd else 'less'} by {abs(we-wd):.0f} min)")

    if len(streaks):
        lines.append(f"\n▸ DOOM STREAKS (back-to-back sessions within 60 min)")
        lines.append(f"  Total streaks      : {len(streaks)}")
        lines.append(f"  Avg streak length  : {streaks['total_min'].mean():.0f} min  "
                     f"({streaks['sessions'].mean():.1f} sessions)")
        lines.append(f"  Longest streak     : {streaks['total_min'].max():.0f} min")
        we_streaks = streaks["is_weekend"].sum()
        lines.append(f"  Weekend streaks    : {we_streaks} ({we_streaks/len(streaks)*100:.0f}%)")

    first_daily = ig.sort_values("start_time").groupby("date").first().reset_index()
    early_morning_ig = (first_daily["hour"] < 9).sum()
    lines.append(f"\n▸ FIRST OPEN OF THE DAY")
    lines.append(f"  Typical first Instagram: {first_daily['hour'].median():.0f}:00  (median)")
    lines.append(f"  Opened before 9am      : {early_morning_ig} of {len(first_daily)} days "
                 f"({early_morning_ig/len(first_daily)*100:.0f}%)")

    daily_totals = ig.groupby("date")["duration_min"].sum().reset_index()
    daily_totals["day_n"] = range(len(daily_totals))
    slope, _, _, p, _ = stats.linregress(daily_totals["day_n"], daily_totals["duration_min"])
    lines.append(f"\n▸ TREND")
    lines.append(f"  Usage is {'increasing' if slope > 0 else 'decreasing'} "
                 f"({slope*7:+.0f} min/week), p={p:.2f} "
                 f"({'significant' if p < 0.05 else 'not significant'})")

    lines.append("\n" + "═" * 68)
    return "\n".join(lines)


def _fig_title(ig):
    total_h = ig["duration_min"].sum() / 60
    days = (ig["date"].max() - ig["date"].min()).days + 1
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.axis("off")
    ax.set_facecolor("#fdf0f5")
    fig.patch.set_facecolor("#fdf0f5")
    ax.text(0.5, 0.80, "Instagram Doomscrolling", ha="center", fontsize=34,
            fontweight="bold", color=IG_PINK, transform=ax.transAxes)
    ax.text(0.5, 0.65, "Pattern Analysis Report", ha="center", fontsize=18,
            color=IG_PURPLE, transform=ax.transAxes)
    ax.text(0.5, 0.48,
            f"{ig['date'].min()}  →  {ig['date'].max()}  ({days} days)  |  "
            f"{total_h:.0f} h total  |  {len(ig):,} sessions",
            ha="center", fontsize=12, color="#555", transform=ax.transAxes)
    return fig


def _fig_daily(ig):
    daily = ig.groupby("date")["duration_min"].sum().reset_index()
    daily["date"] = pd.to_datetime(daily["date"])
    daily["rolling5"] = daily["duration_min"].rolling(5, min_periods=1).mean()
    fig, ax = plt.subplots(figsize=(13, 4.5))
    ax.bar(daily["date"], daily["duration_min"], color=IG_PINK, alpha=0.5, label="Daily")
    ax.plot(daily["date"], daily["rolling5"], color=IG_PURPLE, lw=2.5, label="5-day avg")
    ax.axhline(daily["duration_min"].mean(), color="#aaa", lw=1.2, ls="--", label="Overall avg")
    ax.set_ylabel("Minutes")
    ax.set_title("Daily Instagram Time")
    ax.legend()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.autofmt_xdate()
    return fig


def _fig_session_types(ig):
    bins   = [0, 1, 5, 20, ig["duration_min"].max() + 1]
    labels = ["Glance\n<1 min", "Scroll\n1–5 min", "Doomscroll\n5–20 min", "Binge\n>20 min"]
    ig = ig.copy()
    ig["stype"] = pd.cut(ig["duration_min"], bins=bins, labels=labels)
    counts = ig["stype"].value_counts().reindex(labels)
    times  = ig.groupby("stype", observed=True)["duration_min"].sum().reindex(labels)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    colors = [IG_YELLOW, IG_ORANGE, IG_PINK, IG_PURPLE]
    axes[0].bar(labels, counts.values, color=colors)
    axes[0].set_title("Sessions by Type")
    axes[0].set_ylabel("Session count")
    for i, v in enumerate(counts.values):
        axes[0].text(i, v + 1, str(v), ha="center", fontsize=10)
    axes[1].bar(labels, times.values / 60, color=colors)
    axes[1].set_title("Hours Spent by Session Type")
    axes[1].set_ylabel("Hours")
    for i, v in enumerate(times.values):
        axes[1].text(i, v/60 + 0.1, f"{v/60:.1f}h", ha="center", fontsize=10)
    fig.tight_layout()
    return fig


def _fig_hourly(ig):
    hourly_sessions = ig.groupby("hour").size()
    hourly_time     = ig.groupby("hour")["duration_min"].sum()
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    axes[0].bar(hourly_sessions.index, hourly_sessions.values, color=IG_PINK, alpha=0.8)
    axes[0].set_ylabel("Number of sessions")
    axes[0].set_title("Instagram Opens by Hour of Day")
    axes[1].bar(hourly_time.index, hourly_time.values / 60, color=IG_PURPLE, alpha=0.8)
    axes[1].set_ylabel("Hours spent")
    axes[1].set_title("Instagram Time Spent by Hour of Day")
    axes[1].set_xlabel("Hour")
    axes[1].set_xticks(range(24))
    axes[1].set_xticklabels([f"{h:02d}:00" for h in range(24)], rotation=45, ha="right")
    fig.tight_layout()
    return fig


def _fig_heatmap(ig):
    pivot = ig.groupby(["day_name", "hour"])["duration_min"].sum().unstack(fill_value=0)
    pivot = pivot.reindex([d for d in DAY_ORDER if d in pivot.index])
    fig, ax = plt.subplots(figsize=(14, 5))
    sns.heatmap(pivot / 60, ax=ax, cmap="RdPu", linewidths=0.3,
                cbar_kws={"label": "Hours"}, annot=False)
    ax.set_xticks(range(24))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(24)], rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("")
    ax.set_title("Instagram Usage Heatmap — Day × Hour")
    return fig


def _fig_session_dist(ig):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    clipped = ig["duration_min"].clip(upper=75)
    axes[0].hist(clipped, bins=80, color=IG_PINK, edgecolor="white", linewidth=0.2)
    axes[0].axvline(5,  color=IG_ORANGE, lw=1.5, ls="--", label="5 min (doomscroll threshold)")
    axes[0].axvline(20, color=IG_PURPLE, lw=1.5, ls="--", label="20 min (binge threshold)")
    axes[0].set_xlabel("Session length (min)")
    axes[0].set_ylabel("Count")
    axes[0].set_title("Session Length Distribution")
    axes[0].legend(fontsize=8)
    sorted_sessions = np.sort(ig["duration_min"].values)
    cumtime = np.cumsum(sorted_sessions) / sorted_sessions.sum() * 100
    axes[1].plot(sorted_sessions, cumtime, color=IG_PINK, lw=2)
    axes[1].axvline(5,  color=IG_ORANGE, lw=1.5, ls="--", label="5 min")
    axes[1].axvline(20, color=IG_PURPLE, lw=1.5, ls="--", label="20 min")
    axes[1].set_xlabel("Session length (min)")
    axes[1].set_ylabel("Cumulative % of total time")
    axes[1].set_title("What % of Your Time Do Long Sessions Consume?")
    axes[1].set_xlim(0, 75)
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    return fig


def _fig_streaks(ig, streaks):
    if len(streaks) == 0:
        return None
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    axes[0].hist(streaks["total_min"], bins=25, color=IG_PINK, edgecolor="white")
    axes[0].axvline(streaks["total_min"].mean(), color=IG_PURPLE, lw=2, ls="--",
                    label=f"Mean: {streaks['total_min'].mean():.0f} min")
    axes[0].set_xlabel("Streak duration (min)")
    axes[0].set_ylabel("Count")
    axes[0].set_title("Doom Streak Duration Distribution")
    axes[0].legend()
    streak_hourly = streaks.groupby("hour")["total_min"].sum()
    axes[1].bar(streak_hourly.index, streak_hourly.values / 60, color=IG_PURPLE, alpha=0.8)
    axes[1].set_xlabel("Hour of day")
    axes[1].set_ylabel("Hours in streaks")
    axes[1].set_title("When Doom Streaks Happen")
    axes[1].set_xticks(range(0, 24, 2))
    streak_day = streaks.groupby("day_name")["total_min"].sum().reindex(DAY_ORDER).fillna(0)
    colors = [IG_ORANGE if d in ["Saturday", "Sunday"] else IG_PINK for d in streak_day.index]
    axes[2].bar(range(len(streak_day)), streak_day.values / 60, color=colors)
    axes[2].set_xticks(range(len(streak_day)))
    axes[2].set_xticklabels([d[:3] for d in streak_day.index])
    axes[2].set_ylabel("Hours in streaks")
    axes[2].set_title("Doom Streaks by Day of Week\n(orange = weekend)")
    fig.tight_layout()
    return fig


def _fig_first_open(ig):
    first = ig.sort_values("start_time").groupby("date").first().reset_index()
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].hist(first["hour"], bins=range(0, 25), color=IG_PINK, edgecolor="white")
    axes[0].set_xlabel("Hour")
    axes[0].set_ylabel("Days")
    axes[0].set_title("First Instagram Open of the Day")
    axes[0].set_xticks(range(0, 24, 2))
    axes[0].axvspan(22, 24, color="navy", alpha=0.08, label="Late night")
    axes[0].axvspan(0, 7, color="navy", alpha=0.08)
    axes[0].axvspan(5, 9, color="gold", alpha=0.10, label="Early morning")
    axes[0].legend(fontsize=8)
    slope, intercept, r, p, _ = stats.linregress(first["hour"], first["duration_min"].clip(upper=30))
    x = np.linspace(first["hour"].min(), first["hour"].max(), 100)
    axes[1].scatter(first["hour"], first["duration_min"].clip(upper=30),
                    alpha=0.5, color=IG_PINK, edgecolors="white", s=40)
    axes[1].plot(x, slope * x + intercept, color=IG_PURPLE, lw=2,
                 label=f"Trend (r={r:.2f}, p={p:.2f})")
    axes[1].set_xlabel("Hour of first open")
    axes[1].set_ylabel("Duration of first session (min, capped 30)")
    axes[1].set_title("Does Opening Time Predict Session Length?")
    axes[1].legend()
    fig.tight_layout()
    return fig


def _fig_weekday_vs_weekend(ig):
    ig2 = ig.copy()
    ig2["type"] = ig2["is_weekend"].map({True: "Weekend", False: "Weekday"})
    daily = ig2.groupby(["date", "type"])["duration_min"].sum().reset_index()
    avg = daily.groupby("type")["duration_min"].mean()
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].bar(avg.index, avg.values, color=[IG_ORANGE, IG_PINK], width=0.5)
    axes[0].set_ylabel("Avg min/day")
    axes[0].set_title("Weekday vs Weekend — Daily Average")
    for i, (lbl, val) in enumerate(avg.items()):
        axes[0].text(i, val + 0.5, f"{val:.0f} min", ha="center", fontweight="bold")
    hourly = ig2.groupby(["type", "hour"])["duration_min"].mean().reset_index()
    for label, color in [("Weekday", IG_PINK), ("Weekend", IG_ORANGE)]:
        sub = hourly[hourly["type"] == label]
        axes[1].plot(sub["hour"], sub["duration_min"], label=label, color=color, lw=2,
                     marker="o", markersize=4)
    axes[1].set_xlabel("Hour of day")
    axes[1].set_ylabel("Avg min/hour")
    axes[1].set_title("Hourly Instagram Profile — Weekday vs Weekend")
    axes[1].legend()
    axes[1].set_xticks(range(0, 24, 2))
    fig.tight_layout()
    return fig


def _fig_reopen_loop(ig):
    """Histogram of gaps between consecutive sessions — the 'just one more' loop."""
    ig_sorted = ig.sort_values("start_time").reset_index(drop=True)
    gaps = (ig_sorted["start_time"].iloc[1:].values - ig_sorted["end_time"].iloc[:-1].values)
    gap_min = pd.Series(gaps).dt.total_seconds() / 60
    gap_min = gap_min[(gap_min >= 0) & (gap_min <= 120)]  # clip to 2 hours for readability

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    axes[0].hist(gap_min.clip(upper=60), bins=60, color=IG_PINK, edgecolor="white", linewidth=0.2)
    axes[0].axvline(5,  color=IG_ORANGE, lw=1.5, ls="--", label="5 min")
    axes[0].axvline(15, color=IG_PURPLE, lw=1.5, ls="--", label="15 min")
    axes[0].set_xlabel("Gap between sessions (min, capped at 60)")
    axes[0].set_ylabel("Count")
    axes[0].set_title("How Long Before You Reopen Instagram?")
    axes[0].legend(fontsize=8)

    # Cumulative — what % of reopens happen within X minutes?
    sorted_gaps = np.sort(gap_min.values)
    cum_pct = np.arange(1, len(sorted_gaps) + 1) / len(sorted_gaps) * 100
    axes[1].plot(sorted_gaps, cum_pct, color=IG_PINK, lw=2)
    axes[1].axvline(5,  color=IG_ORANGE, lw=1.5, ls="--", label="5 min")
    axes[1].axvline(15, color=IG_PURPLE, lw=1.5, ls="--", label="15 min")
    axes[1].axvline(60, color="#aaa",    lw=1,   ls=":",  label="1 hour")
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
                 transform=axes[1].transAxes, ha="right", va="bottom",
                 fontsize=9, color="#333",
                 bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="#ccc"))

    fig.tight_layout()
    return fig


def _fig_session_escalation(ig):
    """Do sessions get longer as the day goes on? Scatter: rank-in-day vs duration."""
    ig2 = ig.copy()
    ig2["rank_in_day"] = ig2.groupby("date").cumcount() + 1
    # Only include days with ≥3 sessions
    multi = ig2[ig2.groupby("date")["rank_in_day"].transform("max") >= 3].copy()

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Scatter with regression line
    jitter = np.random.default_rng(42).uniform(-0.25, 0.25, len(multi))
    axes[0].scatter(multi["rank_in_day"] + jitter,
                    multi["duration_min"].clip(upper=40),
                    alpha=0.25, color=IG_PINK, s=18, edgecolors="none")
    from scipy import stats as _stats
    if len(multi) > 10:
        slope, intercept, r, p, _ = _stats.linregress(multi["rank_in_day"], multi["duration_min"].clip(upper=40))
        x = np.linspace(1, multi["rank_in_day"].max(), 100)
        axes[0].plot(x, slope * x + intercept, color=IG_PURPLE, lw=2,
                     label=f"Trend  r={r:.2f}  p={p:.2f}")
        axes[0].legend(fontsize=8)
    axes[0].set_xlabel("Session rank within the day (1st, 2nd, 3rd open…)")
    axes[0].set_ylabel("Session duration (min, capped at 40)")
    axes[0].set_title("Does Each Reopen Get Longer?\n(Session Escalation)")

    # Average duration by rank (up to rank 10)
    avg_by_rank = (
        multi[multi["rank_in_day"] <= 10]
        .groupby("rank_in_day")["duration_min"]
        .mean()
    )
    axes[1].bar(avg_by_rank.index, avg_by_rank.values, color=IG_PINK, alpha=0.8)
    axes[1].set_xlabel("Session rank within the day")
    axes[1].set_ylabel("Avg duration (min)")
    axes[1].set_title("Average Session Length by Open Number")
    axes[1].set_xticks(avg_by_rank.index)

    fig.tight_layout()
    return fig


def _fig_daily_intensity(ig):
    daily = ig.groupby("date")["duration_min"].sum().reset_index()
    daily["date"] = pd.to_datetime(daily["date"])
    fig, ax = plt.subplots(figsize=(13, 3.5))
    sc = ax.scatter(daily["date"], [1]*len(daily),
                    c=daily["duration_min"], cmap="RdPu",
                    s=daily["duration_min"] * 2, alpha=0.85, vmin=0)
    plt.colorbar(sc, ax=ax, label="Minutes")
    ax.set_yticks([])
    ax.set_title("Daily Instagram Intensity (dot size & colour = minutes)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.autofmt_xdate()
    return fig


def generate_report(csv_path: str, output_pdf: str = DEFAULT_PDF, verbose: bool = True) -> None:
    """Load CSV, filter to Instagram, and generate doomscroll PDF report."""
    if verbose:
        print("Loading Instagram data...")
    ig = load_instagram(csv_path)
    if verbose:
        print(f"  {len(ig):,} sessions after filtering accidental taps (<3s)")

    streaks = find_doom_streaks(ig)
    if verbose:
        print(f"  {len(streaks)} doom streaks identified")
        print(interpret(ig, streaks))
        print(f"\nGenerating PDF → {output_pdf}")

    with PdfPages(output_pdf) as pdf:
        for label, fig_fn, args in [
            ("Title",              _fig_title,              (ig,)),
            ("Daily Usage",        _fig_daily,              (ig,)),
            ("Session Types",      _fig_session_types,      (ig,)),
            ("Hourly Patterns",    _fig_hourly,             (ig,)),
            ("Day×Hour Heatmap",   _fig_heatmap,            (ig,)),
            ("Session Dist / CDF", _fig_session_dist,       (ig,)),
            ("Doom Streaks",       _fig_streaks,            (ig, streaks)),
            ("First Open",          _fig_first_open,          (ig,)),
            ("Weekday vs Weekend",  _fig_weekday_vs_weekend,  (ig,)),
            ("Reopen Loop",         _fig_reopen_loop,         (ig,)),
            ("Session Escalation",  _fig_session_escalation,  (ig,)),
            ("Daily Intensity",     _fig_daily_intensity,     (ig,)),
        ]:
            if verbose:
                print(f"  Plotting: {label}")
            fig = fig_fn(*args)
            if fig:
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)

    if verbose:
        print(f"\nDone → {output_pdf}")
