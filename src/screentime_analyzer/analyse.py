"""
General iPhone screen time analysis.
Produces a multi-page PDF report.
"""

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates
from matplotlib.backends.backend_pdf import PdfPages
import seaborn as sns
import numpy as np
from scipy import stats

DEFAULT_PDF = "screentime_report.pdf"

CATEGORIES = {
    "Social": [
        "com.burbn.instagram", "com.zhiliaoapp.musically", "com.facebook.Facebook",
        "com.twitter.twitter", "com.reddit.reddit", "com.linkedin.LinkedIn",
        "com.snapchat.snapchat", "com.toyopagroup.picaboo", "ph.telegra.Telegraph",
        "com.atebits.Tweetie2",
    ],
    "Messaging": [
        "com.apple.MobileSMS", "com.apple.facetime", "com.facebook.Messenger",
        "com.whatsapp.WhatsApp", "org.whispersystems.signal", "ph.telegra.Telegraph",
    ],
    "Entertainment": [
        "com.google.ios.youtube", "com.netflix.Netflix", "com.spotify.client",
        "com.apple.Music", "com.apple.tv", "com.disney.disneyplus",
        "com.amazon.PrimeVideo", "com.apple.Podcasts",
    ],
    "Productivity": [
        "com.goodnotesapp.x", "com.apple.Notes", "com.microsoft.Office.Word",
        "com.microsoft.Office.Excel", "com.microsoft.Office.Outlook",
        "com.apple.mobilemail", "com.apple.reminders", "com.apple.mobilecal",
        "com.notion.id", "com.culturedcode.ThingsTodayWidget",
    ],
    "Browser": [
        "com.apple.mobilesafari", "com.google.chrome.ios", "org.mozilla.ios.Firefox",
    ],
    "Health & Fitness": [
        "com.apple.Health", "com.apple.workout", "com.strava.stravaride",
    ],
    "Games": ["com.apple.gamecenter"],
    "Photos & Camera": ["com.apple.mobileslideshow", "com.apple.camera"],
    "Maps & Navigation": ["com.apple.Maps", "com.google.Maps"],
}

APP_NAMES = {
    "com.burbn.instagram": "Instagram",
    "com.google.ios.youtube": "YouTube",
    "com.apple.MobileSMS": "Messages",
    "com.goodnotesapp.x": "GoodNotes",
    "com.apple.mobileslideshow": "Photos",
    "com.apple.mobilesafari": "Safari",
    "com.netflix.Netflix": "Netflix",
    "com.spotify.client": "Spotify",
    "com.apple.facetime": "FaceTime",
    "com.whatsapp.WhatsApp": "WhatsApp",
    "com.apple.camera": "Camera",
    "com.apple.Health": "Health",
    "com.apple.Maps": "Maps",
    "com.apple.Notes": "Notes",
    "com.apple.mobilemail": "Mail",
    "com.apple.reminders": "Reminders",
    "com.apple.mobilecal": "Calendar",
    "com.notion.id": "Notion",
    "com.apple.Podcasts": "Podcasts",
    "com.apple.Music": "Music",
    "com.twitter.twitter": "Twitter/X",
    "com.reddit.reddit": "Reddit",
    "ph.telegra.Telegraph": "Telegram",
    "com.zhiliaoapp.musically": "TikTok",
}

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TOD_ORDER = ["Early Morning", "Morning", "Afternoon", "Evening", "Night"]

sns.set_theme(style="whitegrid", font_scale=0.95)
plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "#f9f9f9"})
PALETTE = sns.color_palette("husl", 12)


def categorise(bundle_id: str) -> str:
    for cat, bundles in CATEGORIES.items():
        if bundle_id in bundles:
            return cat
    return "Other"


def friendly_name(bundle_id: str) -> str:
    return APP_NAMES.get(bundle_id, bundle_id.split(".")[-1].title())


def load_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=["start_time", "end_time"])
    df = df[df["duration_seconds"] > 2].copy()

    df["hour"] = df["start_time"].dt.hour
    df["day_of_week"] = df["start_time"].dt.dayofweek
    df["day_name"] = df["start_time"].dt.day_name()
    df["date"] = df["start_time"].dt.date
    df["duration_min"] = df["duration_seconds"] / 60
    df["category"] = df["app"].apply(categorise)
    df["app_name"] = df["app"].apply(friendly_name)
    df["is_weekend"] = df["day_of_week"] >= 5

    def tod(h):
        if 5 <= h < 9:   return "Early Morning"
        if 9 <= h < 12:  return "Morning"
        if 12 <= h < 17: return "Afternoon"
        if 17 <= h < 21: return "Evening"
        return "Night"
    df["time_of_day"] = df["hour"].apply(tod)

    return df


def interpret(df: pd.DataFrame) -> str:
    lines = []
    total_h = df["duration_seconds"].sum() / 3600
    days = (df["date"].max() - df["date"].min()).days + 1
    daily_avg = total_h / days

    lines.append("═" * 70)
    lines.append("  PATTERN ANALYSIS — KEY FINDINGS")
    lines.append("═" * 70)

    lines.append(f"\n▸ OVERALL  ({days} days, {df['date'].min()} to {df['date'].max()})")
    lines.append(f"  Total screen time : {total_h:.1f} h")
    lines.append(f"  Daily average     : {daily_avg:.1f} h  ({daily_avg*60:.0f} min/day)")
    lines.append(f"  Total sessions    : {len(df):,}")
    lines.append(f"  Avg session length: {df['duration_min'].mean():.1f} min  (median {df['duration_min'].median():.1f} min)")

    lines.append("\n▸ TOP APPS BY TIME")
    totals = df.groupby("app_name")["duration_min"].sum().sort_values(ascending=False)
    for app, mins in totals.head(8).items():
        pct = mins / (total_h * 60) * 100
        lines.append(f"  {app:<20} {mins/60:5.1f} h  ({pct:.0f}%)")

    lines.append("\n▸ CATEGORY BREAKDOWN")
    cat = df.groupby("category")["duration_min"].sum().sort_values(ascending=False)
    for c, mins in cat.items():
        lines.append(f"  {c:<20} {mins/60:5.1f} h  ({mins/(total_h*60)*100:.0f}%)")

    lines.append("\n▸ WEEKDAY vs WEEKEND")
    wd = df[~df["is_weekend"]].groupby("date")["duration_min"].sum().mean() / 60
    we = df[df["is_weekend"]].groupby("date")["duration_min"].sum().mean() / 60
    diff = we - wd
    lines.append(f"  Weekday avg : {wd:.2f} h/day")
    lines.append(f"  Weekend avg : {we:.2f} h/day")
    lines.append(f"  You use your phone {abs(diff):.2f} h {'more' if diff > 0 else 'less'} on weekends.")

    lines.append("\n▸ DAILY PHONE HABITS")
    first_hour = df.sort_values("start_time").groupby("date")["hour"].first()
    last_hour = df.sort_values("start_time").groupby("date")["hour"].last()
    sessions_per_day = df.groupby("date").size()
    lines.append(f"  Typical first pickup : {first_hour.median():.0f}:00  (median)")
    lines.append(f"  Typical last use     : {last_hour.median():.0f}:00  (median)")
    lines.append(f"  Avg sessions/day     : {sessions_per_day.mean():.0f}")

    hourly = df.groupby("hour")["duration_min"].sum()
    peak_h = hourly.idxmax()
    lines.append(f"\n▸ PEAK USAGE HOUR: {peak_h:02d}:00–{peak_h+1:02d}:00  "
                 f"({hourly[peak_h]/60:.1f} h total across all days)")

    binge = df[df["duration_min"] > 20]
    binge_pct = len(binge) / len(df) * 100
    binge_time_pct = binge["duration_min"].sum() / (total_h * 60) * 100
    lines.append(f"\n▸ BINGE SESSIONS (>20 min each)")
    lines.append(f"  {len(binge)} sessions ({binge_pct:.0f}% of all sessions)")
    lines.append(f"  Account for {binge_time_pct:.0f}% of total screen time")
    top_binge = binge.groupby("app_name")["duration_min"].sum().sort_values(ascending=False).head(3)
    lines.append(f"  Most binge-watched: " + ", ".join(f"{a} ({m/60:.1f}h)" for a, m in top_binge.items()))

    daily_totals = df.groupby("date")["duration_min"].sum().reset_index()
    daily_totals["day_n"] = range(len(daily_totals))
    slope, intercept, r, p, _ = stats.linregress(daily_totals["day_n"], daily_totals["duration_min"])
    trend_dir = "increasing" if slope > 0 else "decreasing"
    sig = "statistically significant (p<0.05)" if p < 0.05 else "not statistically significant"
    lines.append(f"\n▸ USAGE TREND over {days} days")
    lines.append(f"  Direction : {trend_dir}  ({slope*7/60:+.1f} h/week change)")
    lines.append(f"  Trend is  : {sig}  (p={p:.2f})")

    lines.append("\n▸ HABIT APPS (used consistently every day)")
    app_daily = df.groupby(["date", "app_name"])["duration_min"].sum().unstack(fill_value=0)
    coverage = (app_daily > 0).sum() / len(app_daily)
    top_coverage = coverage[coverage > 0.7].sort_values(ascending=False)
    for app, cov in top_coverage.head(5).items():
        avg_min = app_daily[app][app_daily[app] > 0].mean()
        lines.append(f"  {app:<20} used {cov*100:.0f}% of days  (avg {avg_min:.0f} min on days used)")

    night = df[df["hour"].isin([22, 23, 0, 1, 2])]
    night_h = night["duration_min"].sum() / 60
    lines.append(f"\n▸ NIGHT USE (10pm–3am)")
    lines.append(f"  {night_h:.1f} h total  ({night_h/days*60:.0f} min/day avg)")
    if len(night) > 0:
        top_night = night.groupby("app_name")["duration_min"].sum().sort_values(ascending=False).head(3)
        lines.append(f"  Top apps at night: " + ", ".join(f"{a}" for a in top_night.index))

    lines.append("\n" + "═" * 70)
    return "\n".join(lines)


def _fig_daily_totals(df):
    daily = df.groupby("date")["duration_min"].sum().reset_index()
    daily["date"] = pd.to_datetime(daily["date"])
    daily["rolling7"] = daily["duration_min"].rolling(7, min_periods=1).mean()
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.bar(daily["date"], daily["duration_min"] / 60, color="#4a9eca", alpha=0.7, label="Daily total")
    ax.plot(daily["date"], daily["rolling7"] / 60, color="#e05c2a", lw=2, label="7-day rolling avg")
    ax.set_ylabel("Hours")
    ax.set_title("Daily Screen Time")
    ax.legend()
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %d"))
    fig.autofmt_xdate()
    return fig


def _fig_top_apps(df):
    totals = df.groupby("app_name")["duration_min"].sum().sort_values(ascending=False).head(12)
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = sns.color_palette("Blues_r", len(totals))
    bars = ax.barh(totals.index[::-1], totals.values[::-1] / 60, color=colors[::-1])
    for bar, val in zip(bars, totals.values[::-1]):
        ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
                f"{val/60:.1f}h", va="center", fontsize=9)
    ax.set_xlabel("Hours")
    ax.set_title("Top 12 Apps — Total Time")
    return fig


def _fig_category_pie(df):
    cat_totals = df.groupby("category")["duration_min"].sum().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.pie(cat_totals.values, labels=cat_totals.index,
           autopct=lambda p: f"{p:.0f}%" if p > 3 else "",
           colors=sns.color_palette("pastel", len(cat_totals)),
           startangle=140, pctdistance=0.82)
    ax.set_title("Time by Category")
    return fig


def _fig_hourly_heatmap(df):
    pivot = df.groupby(["day_name", "hour"])["duration_min"].sum().unstack(fill_value=0)
    pivot = pivot.reindex([d for d in DAY_ORDER if d in pivot.index])
    fig, ax = plt.subplots(figsize=(14, 5))
    sns.heatmap(pivot / 60, ax=ax, cmap="YlOrRd", linewidths=0.3,
                cbar_kws={"label": "Hours"}, annot=False)
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("")
    ax.set_title("Phone Usage Heatmap — Day × Hour")
    ax.set_xticks(range(24))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(24)], rotation=45, ha="right", fontsize=7)
    return fig


def _fig_session_length_dist(df):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    clipped = df["duration_min"].clip(upper=60)
    axes[0].hist(clipped, bins=60, color="#5b8db8", edgecolor="white", linewidth=0.3)
    axes[0].set_xlabel("Session length (min, capped at 60)")
    axes[0].set_ylabel("Count")
    axes[0].set_title("Session Length Distribution")
    top_apps = df.groupby("app_name")["duration_min"].sum().sort_values(ascending=False).head(8).index
    sub = df[df["app_name"].isin(top_apps)]
    order = sub.groupby("app_name")["duration_min"].median().sort_values(ascending=False).index
    sns.boxplot(data=sub, x="app_name", y="duration_min", order=order, ax=axes[1],
                palette="pastel", showfliers=False)
    axes[1].set_xticklabels(axes[1].get_xticklabels(), rotation=30, ha="right")
    axes[1].set_ylabel("Session length (min)")
    axes[1].set_ylim(0, 60)
    axes[1].set_xlabel("")
    axes[1].set_title("Session Length by App (top 8, no outliers)")
    fig.tight_layout()
    return fig


def _fig_weekday_vs_weekend(df):
    df2 = df.copy()
    df2["type"] = df2["is_weekend"].map({True: "Weekend", False: "Weekday"})
    daily = df2.groupby(["date", "type"])["duration_min"].sum().reset_index()
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    avg = daily.groupby("type")["duration_min"].mean() / 60
    axes[0].bar(avg.index, avg.values, color=["#5b8db8", "#e8834a"], width=0.5)
    axes[0].set_ylabel("Average hours/day")
    axes[0].set_title("Weekday vs Weekend — Daily Average")
    for i, (lbl, val) in enumerate(avg.items()):
        axes[0].text(i, val + 0.03, f"{val:.2f}h", ha="center", fontsize=11)
    hourly = df2.groupby(["type", "hour"])["duration_min"].mean().reset_index()
    for label, color in [("Weekday", "#5b8db8"), ("Weekend", "#e8834a")]:
        sub = hourly[hourly["type"] == label]
        axes[1].plot(sub["hour"], sub["duration_min"], label=label, color=color, lw=2, marker="o", markersize=4)
    axes[1].set_xlabel("Hour of day")
    axes[1].set_ylabel("Avg min/hour")
    axes[1].set_title("Hourly Usage Profile — Weekday vs Weekend")
    axes[1].legend()
    axes[1].set_xticks(range(0, 24, 2))
    fig.tight_layout()
    return fig


def _fig_pickup_patterns(df):
    first = df.sort_values("start_time").groupby("date").first().reset_index()
    last = df.sort_values("start_time").groupby("date").last().reset_index()
    pickups_per_day = df.groupby("date").size().reset_index(name="sessions")
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    axes[0].hist(first["hour"], bins=range(0, 25), color="#4a9eca", edgecolor="white")
    axes[0].set_xlabel("Hour")
    axes[0].set_title("First Phone Pickup (hour)")
    axes[0].set_xticks(range(0, 24, 2))
    axes[1].hist(last["hour"], bins=range(0, 25), color="#9b59b6", edgecolor="white")
    axes[1].set_xlabel("Hour")
    axes[1].set_title("Last Phone Use (hour)")
    axes[1].set_xticks(range(0, 24, 2))
    axes[2].hist(pickups_per_day["sessions"], bins=20, color="#2ecc71", edgecolor="white")
    axes[2].set_xlabel("Number of sessions")
    axes[2].set_title("Sessions per Day")
    fig.tight_layout()
    return fig


def _fig_app_time_of_day(df):
    top_apps = df.groupby("app_name")["duration_min"].sum().sort_values(ascending=False).head(8).index
    sub = df[df["app_name"].isin(top_apps)]
    pivot = sub.groupby(["app_name", "time_of_day"])["duration_min"].sum().unstack(fill_value=0)
    pivot = pivot[[c for c in TOD_ORDER if c in pivot.columns]]
    pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100
    fig, ax = plt.subplots(figsize=(12, 6))
    pivot_pct.plot(kind="bar", stacked=True, ax=ax,
                   color=sns.color_palette("coolwarm", len(pivot_pct.columns)))
    ax.set_ylabel("% of total time")
    ax.set_title("When Each App Is Used — Time-of-Day Breakdown")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=30, ha="right")
    ax.legend(title="Time of day", bbox_to_anchor=(1.01, 1), loc="upper left")
    fig.tight_layout()
    return fig


def _fig_binge_sessions(df):
    binge = df[df["duration_min"] > 20].copy()
    top = binge.groupby("app_name")["duration_min"].sum().sort_values(ascending=False).head(8)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].barh(top.index[::-1], top.values[::-1] / 60,
                 color=sns.color_palette("Reds_r", len(top))[::-1])
    axes[0].set_xlabel("Hours in binge sessions (>20 min)")
    axes[0].set_title("Binge Time by App")
    binge_hourly = binge.groupby("hour")["duration_min"].sum()
    axes[1].bar(binge_hourly.index, binge_hourly.values / 60, color="#e74c3c", alpha=0.8)
    axes[1].set_xlabel("Hour of day")
    axes[1].set_ylabel("Hours")
    axes[1].set_title("Binge Sessions by Hour of Day")
    axes[1].set_xticks(range(0, 24, 2))
    fig.tight_layout()
    return fig


def _add_title_page(pdf, df):
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.axis("off")
    days = (df["date"].max() - df["date"].min()).days + 1
    total_h = df["duration_seconds"].sum() / 3600
    daily_avg = total_h / days
    ax.text(0.5, 0.82, "iPhone Screen Time", ha="center", va="center",
            fontsize=36, fontweight="bold", transform=ax.transAxes, color="#1a1a2e")
    ax.text(0.5, 0.73, "Pattern Analysis Report", ha="center", va="center",
            fontsize=20, transform=ax.transAxes, color="#444")
    ax.text(0.5, 0.60,
            f"{df['date'].min()}  →  {df['date'].max()}  ({days} days)",
            ha="center", va="center", fontsize=14, transform=ax.transAxes, color="#666")
    stats_text = (
        f"Total screen time: {total_h:.1f} h    |    "
        f"Daily average: {daily_avg:.1f} h    |    "
        f"Sessions: {len(df):,}"
    )
    ax.text(0.5, 0.50, stats_text, ha="center", va="center",
            fontsize=13, transform=ax.transAxes, color="#333",
            bbox=dict(boxstyle="round,pad=0.6", facecolor="#e8f4f8", edgecolor="#aad4e8"))
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def generate_report(csv_path: str, output_pdf: str = DEFAULT_PDF, verbose: bool = True) -> None:
    """Load CSV and generate the full screen time PDF report."""
    if verbose:
        print("Loading data...")
    df = load_data(csv_path)
    if verbose:
        print(f"  {len(df):,} sessions loaded.")
        print(interpret(df))
        print(f"\nGenerating PDF report → {output_pdf} ...")

    with PdfPages(output_pdf) as pdf:
        _add_title_page(pdf, df)
        for label, fig_fn in [
            ("Daily Screen Time",  _fig_daily_totals),
            ("Top Apps",           _fig_top_apps),
            ("Category Breakdown", _fig_category_pie),
            ("Hourly Heatmap",     _fig_hourly_heatmap),
            ("Session Length",     _fig_session_length_dist),
            ("Weekday vs Weekend", _fig_weekday_vs_weekend),
            ("Pickup Patterns",    _fig_pickup_patterns),
            ("App Time-of-Day",    _fig_app_time_of_day),
            ("Binge Sessions",     _fig_binge_sessions),
        ]:
            if verbose:
                print(f"  Plotting: {label}")
            fig = fig_fn(df)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

    if verbose:
        print(f"\nDone. Report saved to {output_pdf}")
