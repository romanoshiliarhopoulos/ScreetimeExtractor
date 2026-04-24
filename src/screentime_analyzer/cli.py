"""
Command-line interface for screentime-analyzer.

Usage:
  screentime extract           Extract data from macOS Biome → CSV
  screentime analyze           Generate full screen time PDF report
  screentime instagram         Generate Instagram doomscroll PDF report
  screentime agent             LLM-powered narrative analysis
  screentime submit            Package your CSV for submission to the project author
"""

import sys
import os
import shutil
import zipfile
import datetime
from pathlib import Path

try:
    import click
except ImportError:
    print("ERROR: 'click' is not installed. Run: pip install click")
    sys.exit(1)


@click.group()
@click.version_option()
def cli():
    """iPhone Screen Time Analyzer — extract, visualise, and understand your phone habits."""
    pass


# ── extract ───────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--output", "-o", default="screentime.csv", show_default=True,
              help="Path for the output CSV file.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress progress output.")
def extract(output, quiet):
    """Extract screen time sessions from the macOS Biome database to CSV."""
    from screentime_analyzer.extract import extract as _extract
    try:
        n = _extract(output=output, verbose=not quiet)
        click.echo(f"Extracted {n:,} sessions → {output}")
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)


# ── analyze ───────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--csv", "-c", "csv_path", default="screentime.csv", show_default=True,
              help="Path to the screen time CSV.")
@click.option("--output", "-o", default="screentime_report.pdf", show_default=True,
              help="Output PDF path.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress progress output.")
def analyze(csv_path, output, quiet):
    """Generate a full screen time PDF report with charts and statistics."""
    from screentime_analyzer.analyse import generate_report
    if not Path(csv_path).exists():
        click.echo(f"ERROR: CSV not found: {csv_path}\n"
                   "Run 'screentime extract' first, or pass --csv path/to/file.csv", err=True)
        sys.exit(1)
    generate_report(csv_path=csv_path, output_pdf=output, verbose=not quiet)


# ── instagram ─────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--csv", "-c", "csv_path", default="screentime.csv", show_default=True,
              help="Path to the screen time CSV.")
@click.option("--output", "-o", default="instagram_report.pdf", show_default=True,
              help="Output PDF path.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress progress output.")
def instagram(csv_path, output, quiet):
    """Generate an Instagram doomscrolling pattern analysis PDF."""
    from screentime_analyzer.instagram import generate_report
    if not Path(csv_path).exists():
        click.echo(f"ERROR: CSV not found: {csv_path}", err=True)
        sys.exit(1)
    generate_report(csv_path=csv_path, output_pdf=output, verbose=not quiet)


# ── agent ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--csv", "-c", "csv_path", default="screentime.csv", show_default=True,
              help="Path to the screen time CSV.")
@click.option("--app", "-a", "app_id", default="com.burbn.instagram", show_default=True,
              help="Bundle ID of the app to analyse (default: Instagram).")
@click.option("--output", "-o", default=None,
              help="Write the report to a text file instead of stdout.")
@click.option("--model", "-m", default="claude-opus-4-6", show_default=True,
              help="Claude model to use.")
def agent(csv_path, app_id, output, model):
    """
    LLM doomscrolling analysis: computes stats locally, sends only numbers to Claude.

    Analyses session types, reopen loop, session escalation, doom streaks, morning
    habit, and night usage for one app. Raw session data never leaves your machine —
    only aggregated statistics are sent to the Claude API.

    Requires ANTHROPIC_API_KEY to be set in your environment.
    """
    from screentime_analyzer.agent import run_agent
    if not Path(csv_path).exists():
        click.echo(f"ERROR: CSV not found: {csv_path}", err=True)
        sys.exit(1)
    try:
        run_agent(csv_path=csv_path, app_id=app_id, output_file=output, model=model)
    except (ImportError, EnvironmentError) as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)


# ── submit ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--csv", "-c", "csv_path", default="screentime.csv", show_default=True,
              help="Path to the screen time CSV to submit.")
@click.option("--output", "-o", default=None,
              help="Output zip filename (default: screentime_submission_<date>.zip).")
def submit(csv_path, output):
    """
    Package your CSV for submission to the project author for report generation.

    This creates a zip archive containing your raw CSV data. You can then share
    this archive with the project author who will generate a personalised report
    and send it back to you.

    NOTE: This shares your raw session-level data. If you prefer to keep your
    data private, use 'screentime analyze' or 'screentime agent' instead.
    """
    if not Path(csv_path).exists():
        click.echo(f"ERROR: CSV not found: {csv_path}", err=True)
        sys.exit(1)

    if output is None:
        date_str = datetime.date.today().isoformat()
        output = f"screentime_submission_{date_str}.zip"

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(csv_path, arcname=Path(csv_path).name)
        # Include a metadata file
        meta = (
            f"Submission date: {datetime.datetime.now().isoformat()}\n"
            f"Source file: {csv_path}\n"
            f"Records: {_count_lines(csv_path) - 1} sessions\n"
        )
        zf.writestr("submission_info.txt", meta)

    size_kb = Path(output).stat().st_size / 1024
    click.echo(f"Submission package created: {output}  ({size_kb:.0f} KB)")
    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Open a GitHub issue at: https://github.com/romanosam/screentime-analyzer/issues/new")
    click.echo("  2. Use the title: 'Report Request'")
    click.echo("  3. Attach the zip file to the issue")
    click.echo("  4. You will receive a personalised PDF report within a few days.")
    click.echo()
    click.echo("Alternatively, email the zip to the address listed in the README.")


def _count_lines(path: str) -> int:
    with open(path) as f:
        return sum(1 for _ in f)
