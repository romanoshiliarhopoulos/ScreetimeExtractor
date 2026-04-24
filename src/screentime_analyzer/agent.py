"""
LLM-powered doomscrolling analysis agent.

Computes doomscrolling statistics locally from your screen time CSV, then sends
only the aggregated numbers to Claude for narrative analysis.
No raw session data leaves your machine.

Requires: ANTHROPIC_API_KEY environment variable.
"""

import os
import json
from pathlib import Path

import pandas as pd
import numpy as np
from scipy import stats as scipy_stats

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore

SYSTEM_PROMPT_PATH = Path(__file__).parent.parent.parent / "agent_prompt.md"

DOOM_THRESHOLD_MIN = 5    # sessions >= this are doomscrolls
BINGE_THRESHOLD_MIN = 20  # sessions >= this are binges
STREAK_GAP_MIN = 60       # max gap between sessions to be considered same streak


def build_doomscroll_stats(csv_path: str, app_id: str = "com.burbn.instagram") -> dict:
    """
    Compute doomscrolling statistics for one app.
    Returns a JSON-serialisable dict of aggregated metrics only.
    """
    df = pd.read_csv(csv_path, parse_dates=["start_time", "end_time"])
    ig = df[(df["app"] == app_id) & (df["duration_seconds"] > 3)].copy()
    if len(ig) < 5:
        raise ValueError(f"Not enough sessions found for app '{app_id}' (found {len(ig)}).")

    ig["duration_min"] = ig["duration_seconds"] / 60
    ig["hour"]         = ig["start_time"].dt.hour
    ig["date"]         = ig["start_time"].dt.date
    ig["day_name"]     = ig["start_time"].dt.day_name()
    ig["dow"]          = ig["start_time"].dt.dayofweek
    ig["is_weekend"]   = ig["dow"] >= 5
    ig = ig.sort_values("start_time").reset_index(drop=True)

    days = (ig["date"].max() - ig["date"].min()).days + 1
    total_min = ig["duration_min"].sum()

    # ── Session type counts ───────────────────────────────────────────────────
    n_glance    = int((ig["duration_min"] < 1).sum())
    n_scroll    = int(((ig["duration_min"] >= 1) & (ig["duration_min"] < DOOM_THRESHOLD_MIN)).sum())
    n_doom      = int(((ig["duration_min"] >= DOOM_THRESHOLD_MIN) & (ig["duration_min"] < BINGE_THRESHOLD_MIN)).sum())
    n_binge     = int((ig["duration_min"] >= BINGE_THRESHOLD_MIN).sum())
    doom_time   = ig[ig["duration_min"] >= DOOM_THRESHOLD_MIN]["duration_min"].sum()

    # ── Hourly / day-of-week ──────────────────────────────────────────────────
    hourly = (
        ig.groupby("hour")["duration_min"].sum()
        .reindex(range(24), fill_value=0)
        .apply(lambda x: round(x / 60, 3))
        .to_dict()
    )
    dow_hours = (
        ig.groupby("day_name")["duration_min"].sum()
        .apply(lambda x: round(x / 60, 2))
        .to_dict()
    )

    # ── Weekday vs weekend ────────────────────────────────────────────────────
    wd_avg = ig[~ig["is_weekend"]].groupby("date")["duration_min"].sum().mean()
    we_avg = ig[ig["is_weekend"]].groupby("date")["duration_min"].sum().mean()

    # ── Doom streaks ──────────────────────────────────────────────────────────
    streaks = _find_streaks(ig, STREAK_GAP_MIN)
    streak_stats: dict = {"total": 0}
    if len(streaks):
        sdf = pd.DataFrame(streaks)
        we_streak_count = int(sdf["is_weekend"].sum())
        peak_streak_h = int(sdf.groupby("hour")["total_min"].sum().idxmax())
        streak_by_dow = (
            sdf.groupby("day_name")["total_min"].sum()
            .apply(lambda x: round(x / 60, 2))
            .to_dict()
        )
        streak_stats = {
            "total": len(sdf),
            "avg_duration_min": round(float(sdf["total_min"].mean()), 1),
            "avg_sessions_per_streak": round(float(sdf["sessions"].mean()), 1),
            "longest_streak_min": round(float(sdf["total_min"].max()), 1),
            "pct_on_weekends": round(we_streak_count / len(sdf) * 100, 1),
            "peak_hour": peak_streak_h,
            "hours_by_day_of_week": streak_by_dow,
        }

    # ── Reopen loop ───────────────────────────────────────────────────────────
    gaps = (ig["start_time"].iloc[1:].values - ig["end_time"].iloc[:-1].values)
    gap_min = pd.Series(gaps).dt.total_seconds() / 60
    gap_min = gap_min[gap_min >= 0]  # drop negative gaps (data artefacts)
    reopen_stats = {
        "median_gap_min": round(float(gap_min.median()), 1),
        "mean_gap_min": round(float(gap_min.mean()), 1),
        "pct_reopened_within_1min": round(float((gap_min <= 1).mean() * 100), 1),
        "pct_reopened_within_5min": round(float((gap_min <= 5).mean() * 100), 1),
        "pct_reopened_within_15min": round(float((gap_min <= 15).mean() * 100), 1),
    }

    # ── Session escalation (rank within day vs duration) ─────────────────────
    ig2 = ig.copy()
    ig2["rank_in_day"] = ig2.groupby("date").cumcount() + 1
    # Only days with ≥3 sessions for meaningful correlation
    multi = ig2[ig2.groupby("date")["rank_in_day"].transform("max") >= 3]
    esc_r, esc_p = 0.0, 1.0
    if len(multi) > 10:
        esc_r, esc_p = scipy_stats.pearsonr(multi["rank_in_day"], multi["duration_min"])
    escalation_stats = {
        "pearson_r": round(float(esc_r), 3),
        "p_value": round(float(esc_p), 3),
        "significant": bool(esc_p < 0.05),
        "interpretation": (
            "sessions tend to get longer as the day goes on"
            if esc_r > 0.05
            else "sessions tend to get shorter as the day goes on"
            if esc_r < -0.05
            else "no clear escalation pattern through the day"
        ),
    }

    # ── Morning habit ─────────────────────────────────────────────────────────
    first_daily = ig.sort_values("start_time").groupby("date").first().reset_index()
    morning_stats = {
        "median_first_open_hour": int(first_daily["hour"].median()),
        "pct_days_before_9am": round(float((first_daily["hour"] < 9).mean() * 100), 1),
        "pct_days_before_7am": round(float((first_daily["hour"] < 7).mean() * 100), 1),
        "avg_first_session_min": round(float(first_daily["duration_min"].mean()), 1),
    }

    # ── Night usage (10pm–3am) ────────────────────────────────────────────────
    night = ig[ig["hour"].isin([22, 23, 0, 1, 2])]
    night_stats = {
        "total_hours": round(float(night["duration_min"].sum() / 60), 2),
        "avg_min_per_day": round(float(night["duration_min"].sum() / days), 1),
        "pct_of_total_time": round(float(night["duration_min"].sum() / total_min * 100), 1),
    }

    # ── Trend ─────────────────────────────────────────────────────────────────
    daily = ig.groupby("date")["duration_min"].sum().reset_index()
    daily["day_n"] = range(len(daily))
    slope, _, _, p_val, _ = scipy_stats.linregress(daily["day_n"], daily["duration_min"])
    trend_stats = {
        "direction": "increasing" if slope > 0 else "decreasing",
        "change_per_week_min": round(float(slope * 7), 1),
        "p_value": round(float(p_val), 3),
        "significant": bool(p_val < 0.05),
    }

    return {
        "app_id": app_id,
        "date_range": {
            "start": str(ig["date"].min()),
            "end": str(ig["date"].max()),
            "days": days,
        },
        "overview": {
            "total_hours": round(float(total_min / 60), 2),
            "daily_avg_min": round(float(total_min / days), 1),
            "total_sessions": len(ig),
            "sessions_per_day": round(float(len(ig) / days), 1),
            "median_session_min": round(float(ig["duration_min"].median()), 1),
            "longest_session_min": round(float(ig["duration_min"].max()), 1),
        },
        "session_types": {
            "glance_under_1min":       {"count": n_glance,  "pct": round(n_glance / len(ig) * 100, 1)},
            "scroll_1_to_5min":        {"count": n_scroll,  "pct": round(n_scroll / len(ig) * 100, 1)},
            "doomscroll_5_to_20min":   {"count": n_doom,    "pct": round(n_doom / len(ig) * 100, 1)},
            "binge_over_20min":        {"count": n_binge,   "pct": round(n_binge / len(ig) * 100, 1)},
            "doomscroll_plus_binge_pct_of_time": round(float(doom_time / total_min * 100), 1),
        },
        "hourly_usage_hours": {str(k): v for k, v in hourly.items()},
        "day_of_week_hours": dow_hours,
        "weekday_vs_weekend": {
            "weekday_avg_min": round(float(wd_avg), 1),
            "weekend_avg_min": round(float(we_avg), 1),
            "delta_min": round(float(we_avg - wd_avg), 1),
        },
        "doom_streaks": streak_stats,
        "reopen_loop": reopen_stats,
        "session_escalation": escalation_stats,
        "morning_habit": morning_stats,
        "night_usage_10pm_3am": night_stats,
        "trend": trend_stats,
    }


def _find_streaks(ig: pd.DataFrame, gap_min: int) -> list:
    streaks = []
    streak = [0]
    for i in range(1, len(ig)):
        gap = (ig.loc[i, "start_time"] - ig.loc[i-1, "end_time"]).total_seconds() / 60
        if gap <= gap_min:
            streak.append(i)
        else:
            if len(streak) > 1:
                rows = ig.loc[streak]
                streaks.append({
                    "sessions":   len(streak),
                    "total_min":  rows["duration_min"].sum(),
                    "hour":       int(rows["start_time"].min().hour),
                    "day_name":   rows["start_time"].min().day_name(),
                    "is_weekend": bool(rows["start_time"].min().dayofweek >= 5),
                })
            streak = [i]
    if len(streak) > 1:
        rows = ig.loc[streak]
        streaks.append({
            "sessions":   len(streak),
            "total_min":  rows["duration_min"].sum(),
            "hour":       int(rows["start_time"].min().hour),
            "day_name":   rows["start_time"].min().day_name(),
            "is_weekend": bool(rows["start_time"].min().dayofweek >= 5),
        })
    return streaks


def run_agent(
    csv_path: str,
    app_id: str = "com.burbn.instagram",
    output_file: str | None = None,
    model: str = "claude-opus-4-6",
) -> str:
    """
    Compute doomscrolling statistics locally and send them to Claude for narrative analysis.
    Raw session data is never sent to the API — only aggregated statistics.
    """
    if anthropic is None:
        raise ImportError(
            "The 'anthropic' package is required.\n"
            "Install it with:  pip install 'screentime-analyzer[agent]'"
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY environment variable not set.\n"
            "Get your key at https://console.anthropic.com/ and run:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-..."
        )

    print(f"Computing doomscrolling statistics for '{app_id}'...")
    stats = build_doomscroll_stats(csv_path, app_id=app_id)
    stats_json = json.dumps(stats, indent=2)

    system_text = (
        SYSTEM_PROMPT_PATH.read_text()
        if SYSTEM_PROMPT_PATH.exists()
        else _fallback_prompt()
    )

    user_message = (
        "Here are my doomscrolling statistics. Please write the full analysis report.\n\n"
        f"```json\n{stats_json}\n```"
    )

    print(f"Sending statistics to {model}...")
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_text,
        messages=[{"role": "user", "content": user_message}],
    )

    report = response.content[0].text

    if output_file:
        Path(output_file).write_text(report, encoding="utf-8")
        print(f"Report saved to {output_file}")
    else:
        print("\n" + "═" * 70 + "\n")
        print(report)
        print("\n" + "═" * 70)

    return report


def _fallback_prompt() -> str:
    return (
        "You are a digital wellness analyst specialising in compulsive phone use. "
        "You receive doomscrolling statistics as JSON and write a detailed, honest, "
        "and actionable narrative report focused entirely on doomscrolling behaviour."
    )
